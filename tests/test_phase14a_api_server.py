from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import sys
import unittest
from uuid import uuid4
from unittest.mock import patch


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
TEST_TMP_ROOT = PROJECT_ROOT / ".tmp_tests" / "phase14a"
sys.path.insert(0, str(SRC_PATH))

from target_opportunity_monitor.api_server import (
    api_cors_headers,
    handle_api_request,
    serve_api_once_smoke_test,
)
from target_opportunity_monitor.config import AppConfig, load_config
from target_opportunity_monitor.db import initialize_database
from target_opportunity_monitor.storage import (
    ResearchRecommendationCandidate,
    StoredResearchRecommendationCandidate,
    upsert_research_recommendation_candidate,
)


def _config(tmpdir: str) -> AppConfig:
    root = Path(tmpdir)
    return AppConfig(
        project_root=root,
        config_path=root / "config.toml",
        database_path=root / "tom.sqlite",
        reports_dir=root / "reports",
        watchlist_path=root / "configs" / "watchlist.csv",
        market_data_dir=root / "data" / "market_data",
        manual_prices_dir=root / "data" / "market_data" / "manual",
        market_data_primary_source="manual",
        market_data_secondary_source="manual",
        market_data_mode="manual",
        market_data_lookback_days=30,
        market_data_stale_after_days=7,
        market_data_minimum_history_days=5,
        universe_mode="manual_watchlist",
        run_mode="test",
        report_title="Test",
    )


def _new_config(name: str) -> AppConfig:
    TEST_TMP_ROOT.mkdir(parents=True, exist_ok=True)
    root = TEST_TMP_ROOT / f"{name}_{uuid4().hex}"
    root.mkdir(parents=True, exist_ok=True)
    return _config(str(root))


def _initialized_config(name: str) -> AppConfig:
    config = _new_config(name)
    initialize_database(config.database_path)
    return config


def _seed_recommendation(config: AppConfig, status: str = "pending") -> int:
    return upsert_research_recommendation_candidate(
        config.database_path,
        ResearchRecommendationCandidate(
            recommendation_key="codex_manual:TSLA:test",
            ticker="TSLA",
            recommendation_date="2026-06-13",
            source="codex_manual",
            status=status,
            topic="test",
            rationale="test recommendation",
            research_priority_score=75.0,
            confidence=60.0,
            source_count=1,
            evidence_count=1,
            source_mix="codex_manual",
            metadata_status="ready",
            warning_codes="",
            promotion_blockers="",
            promoted_asset_role="scoreable",
            source_url="https://example.com/tsla",
            external_id="test",
            as_of_date="2026-06-13",
            effective_date="2026-06-13T00:00:00",
        ),
    )


@dataclass(frozen=True)
class _FakeResult:
    status: str = "ok"
    summary: str = "ok"
    steps: tuple[object, ...] = ()


class Phase14ApiServerTests(unittest.TestCase):
    def test_config_defaults_load(self) -> None:
        config = load_config()

        self.assertEqual(config.api_host, "127.0.0.1")
        self.assertEqual(config.api_port, 8765)
        self.assertIn("http://127.0.0.1:5173", config.api_allowed_origins)
        self.assertTrue(config.api_require_mutation_confirmation)

    def test_health_and_status_endpoints_return_json(self) -> None:
        config = _initialized_config("health_status")

        health_code, health = handle_api_request(config, "GET", "/api/health")
        status_code, status = handle_api_request(config, "GET", "/api/status")

        self.assertEqual(health_code, 200)
        self.assertTrue(health["ok"])
        self.assertEqual(status_code, 200)
        self.assertTrue(status["ok"])
        self.assertIn("rows", status["data"])

    def test_cors_allows_configured_local_dev_origin(self) -> None:
        config = _new_config("cors")

        headers = api_cors_headers(config, "http://127.0.0.1:5173")

        self.assertEqual(headers["Access-Control-Allow-Origin"], "http://127.0.0.1:5173")
        self.assertIn("X-TOM-Confirm", headers["Access-Control-Allow-Headers"])

    def test_unknown_route_and_malformed_json_return_structured_errors(self) -> None:
        config = _initialized_config("structured_errors")

        unknown_code, unknown = handle_api_request(config, "GET", "/api/nope")
        malformed_code, malformed = handle_api_request(
            config,
            "POST",
            "/api/research/ticker-plan",
            body="{bad-json",
        )

        self.assertEqual(unknown_code, 404)
        self.assertFalse(unknown["ok"])
        self.assertEqual(unknown["error_code"], "not_found")
        self.assertEqual(malformed_code, 400)
        self.assertFalse(malformed["ok"])
        self.assertEqual(malformed["error_code"], "malformed_json")

    def test_untrusted_origins_cannot_read_or_mutate(self) -> None:
        config = _initialized_config("cors_rejected")
        for origin in ("null", "https://untrusted.example", "http://localhost:9999"):
            with self.subTest(origin=origin):
                self.assertNotIn("Access-Control-Allow-Origin", api_cors_headers(config, origin))
                for method, path in (("GET", "/api/health"), ("POST", "/api/assets/add")):
                    code, payload = handle_api_request(
                        config, method, path, headers={"origin": origin, "X-TOM-Confirm": "true"},
                        body={"confirm": True, "ticker": "UNTRUSTED"},
                    )
                    self.assertEqual(code, 403)
                    self.assertEqual(payload["error_code"], "origin_forbidden")

    def test_allowed_origin_and_cli_requests_still_work(self) -> None:
        config = _initialized_config("cors_allowed")
        for headers in (None, {"Origin": "http://127.0.0.1:5173"}):
            code, payload = handle_api_request(config, "GET", "/api/health", headers=headers)
            self.assertEqual(code, 200)
            self.assertTrue(payload["ok"])
        self.assertNotIn("Access-Control-Allow-Origin", api_cors_headers(config, None))

    def test_mutating_recommendation_status_requires_confirmation(self) -> None:
        config = _initialized_config("recommendation_requires_confirmation")
        recommendation_id = _seed_recommendation(config)

        code, payload = handle_api_request(
            config,
            "POST",
            f"/api/research/recommendations/{recommendation_id}/status",
            body={"status": "approved"},
        )

        self.assertEqual(code, 403)
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["error_code"], "confirmation_required")

    def test_recommendation_status_updates_with_confirmation(self) -> None:
        config = _initialized_config("recommendation_update")
        recommendation_id = _seed_recommendation(config)

        code, payload = handle_api_request(
            config,
            "POST",
            f"/api/research/recommendations/{recommendation_id}/status",
            body={"status": "approved", "confirm": True},
        )

        self.assertEqual(code, 200)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["data"]["candidate"]["status"], "approved")

    def test_research_ticker_plan_endpoint_is_non_mutating(self) -> None:
        config = _initialized_config("ticker_plan")
        fake_plan = {"ticker": "TSLA", "apply_ready": True}

        with patch(
            "target_opportunity_monitor.api_server.research_ticker_plan",
            return_value=fake_plan,
        ) as plan_mock:
            code, payload = handle_api_request(
                config,
                "POST",
                "/api/research/ticker-plan",
                body={"ticker": "TSLA"},
            )

        self.assertEqual(code, 200)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["data"]["plan"], fake_plan)
        plan_mock.assert_called_once()

    def test_promote_endpoint_preserves_existing_blockers(self) -> None:
        config = _initialized_config("promote_blocked")
        recommendation_id = _seed_recommendation(config, status="approved")
        fake_candidate = StoredResearchRecommendationCandidate(
            research_recommendation_id=recommendation_id,
            recommendation_key="codex_manual:TSLA:test",
            ticker="TSLA",
            recommendation_date="2026-06-13",
            source="codex_manual",
            status="approved",
            topic="test",
            rationale="test recommendation",
            research_priority_score=75.0,
        )

        with patch(
            "target_opportunity_monitor.api_server.promote_research_recommendation",
            return_value=type(
                "Promotion",
                (),
                {
                    "promoted": False,
                    "blocked_reason": "missing_sector",
                    "warnings": ("missing_sector",),
                    "recommendation": fake_candidate,
                },
            )(),
        ):
            code, payload = handle_api_request(
                config,
                "POST",
                f"/api/research/recommendations/{recommendation_id}/promote",
                body={"confirm": True},
            )

        self.assertEqual(code, 409)
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["error_code"], "missing_sector")

    def test_intraday_and_notification_endpoints_can_be_mocked(self) -> None:
        config = _initialized_config("intraday_notifications")

        with patch(
            "target_opportunity_monitor.api_server.run_intraday_cycle",
            return_value=_FakeResult(),
        ) as intraday_mock:
            code, payload = handle_api_request(
                config,
                "POST",
                "/api/ops/intraday-cycle",
                body={"confirm": True, "source": "auto", "deliver": True, "channel": "file"},
            )
        self.assertEqual(code, 200)
        self.assertTrue(payload["ok"])
        intraday_mock.assert_called_once()

        with patch(
            "target_opportunity_monitor.api_server.deliver_notifications",
            return_value=type(
                "Delivery",
                (),
                {
                    "delivered_count": 0,
                    "failed_count": 0,
                    "warnings": (),
                    "events": (),
                    "outbox_paths": (),
                },
            )(),
        ):
            drain_code, drain_payload = handle_api_request(
                config,
                "POST",
                "/api/notifications/drain",
                body={"confirm": True, "channel": "file"},
            )
        self.assertEqual(drain_code, 200)
        self.assertTrue(drain_payload["ok"])

    def test_once_smoke_test_exercises_health_and_status(self) -> None:
        config = _initialized_config("once_smoke")

        result = serve_api_once_smoke_test(config)

        self.assertTrue(result["health_ok"])
        self.assertTrue(result["status_ok"])
        self.assertEqual(result["health_status_code"], 200)
        self.assertEqual(result["status_status_code"], 200)


if __name__ == "__main__":
    unittest.main()
