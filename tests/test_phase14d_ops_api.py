from __future__ import annotations

from pathlib import Path
import sys
import unittest
from uuid import uuid4
from unittest.mock import patch


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
TEST_TMP_ROOT = PROJECT_ROOT / ".tmp_tests" / "phase14d"
sys.path.insert(0, str(SRC_PATH))

from target_opportunity_monitor.api_server import handle_api_request
from target_opportunity_monitor.config import AppConfig
from target_opportunity_monitor.db import initialize_database
from target_opportunity_monitor.storage import latest_asset


def _config(tmpdir: str) -> AppConfig:
    root = Path(tmpdir)
    return AppConfig(
        project_root=root,
        config_path=root / "config.toml",
        database_path=root / "tom.sqlite",
        reports_dir=root / "reports",
        watchlist_path=root / "configs" / "watchlist.csv",
        cik_map_path=root / "configs" / "cik_map.csv",
        scheduler_automations_dir=root / ".codex" / "automations",
        notification_outbox_dir=root / "data" / "notifications" / "outbox",
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


def _initialized_config(name: str) -> AppConfig:
    TEST_TMP_ROOT.mkdir(parents=True, exist_ok=True)
    root = TEST_TMP_ROOT / f"{name}_{uuid4().hex}"
    root.mkdir(parents=True, exist_ok=True)
    config = _config(str(root))
    initialize_database(config.database_path)
    return config


class Phase14DOpsApiTests(unittest.TestCase):
    def test_status_get_endpoints_handle_empty_state(self) -> None:
        config = _initialized_config("status_empty")

        for path in (
            "/api/ops/intraday-status",
            "/api/ops/intraday-health",
            "/api/scheduler/status",
            "/api/scheduler/audit",
            "/api/notifications/status",
            "/api/notifications/delivery-report",
            "/api/notifications/outbox-status",
        ):
            with self.subTest(path=path):
                code, payload = handle_api_request(config, "GET", path)
                self.assertEqual(code, 200)
                self.assertTrue(payload["ok"])

    def test_intraday_health_endpoint_serializes_session_fields(self) -> None:
        config = _initialized_config("intraday_health_fields")

        code, payload = handle_api_request(config, "GET", "/api/ops/intraday-health")

        self.assertEqual(code, 200)
        self.assertTrue(payload["ok"])
        health = payload["data"]["health"]
        self.assertIn("market_session", health)
        self.assertIn("regular_market_hours", health)
        self.assertIn("notes", health)
        self.assertIn(health["market_session"], {"regular", "pre_market", "after_hours", "weekend"})

    def test_asset_add_requires_confirmation(self) -> None:
        config = _initialized_config("asset_requires_confirmation")

        code, payload = handle_api_request(
            config,
            "POST",
            "/api/assets/add",
            body={"ticker": "TEST", "asset_type": "equity"},
        )

        self.assertEqual(code, 403)
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["error_code"], "confirmation_required")

    def test_asset_add_status_and_active_controls(self) -> None:
        config = _initialized_config("asset_controls")

        add_code, add_payload = handle_api_request(
            config,
            "POST",
            "/api/assets/add",
            body={
                "ticker": "TEST",
                "name": "Test Corp",
                "asset_type": "equity",
                "asset_role": "scoreable",
                "exchange": "NASDAQ",
                "currency": "USD",
                "sector": "Technology",
                "industry": "Software",
                "country": "US",
                "cik": "0000000001",
                "confirm": True,
            },
        )

        self.assertEqual(add_code, 200)
        self.assertTrue(add_payload["ok"])
        asset = latest_asset(config.database_path, "TEST")
        self.assertIsNotNone(asset)
        self.assertEqual(asset.name, "Test Corp")
        self.assertEqual(asset.active_flag, 1)

        status_code, status_payload = handle_api_request(
            config,
            "GET",
            "/api/assets/status?ticker=TEST",
        )
        self.assertEqual(status_code, 200)
        self.assertTrue(status_payload["ok"])
        self.assertEqual(status_payload["data"]["asset"]["ticker"], "TEST")

        deactivate_code, _ = handle_api_request(
            config,
            "POST",
            "/api/assets/deactivate",
            body={"ticker": "TEST", "reason": "unit_test", "confirm": True},
        )
        self.assertEqual(deactivate_code, 200)
        self.assertEqual(latest_asset(config.database_path, "TEST").active_flag, 0)

        reactivate_code, _ = handle_api_request(
            config,
            "POST",
            "/api/assets/reactivate",
            body={"ticker": "TEST", "reason": "unit_test", "confirm": True},
        )
        self.assertEqual(reactivate_code, 200)
        self.assertEqual(latest_asset(config.database_path, "TEST").active_flag, 1)

        remove_code, _ = handle_api_request(
            config,
            "POST",
            "/api/assets/remove",
            body={"ticker": "TEST", "reason": "unit_test", "confirm": True},
        )
        self.assertEqual(remove_code, 200)
        self.assertEqual(latest_asset(config.database_path, "TEST").active_flag, 0)

    def test_asset_controls_return_not_found_for_missing_ticker(self) -> None:
        config = _initialized_config("asset_missing")

        code, payload = handle_api_request(
            config,
            "POST",
            "/api/assets/deactivate",
            body={"ticker": "NOPE", "confirm": True},
        )

        self.assertEqual(code, 404)
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["error_code"], "asset_not_found")

    def test_manual_ops_cycle_confirmation_and_dry_run(self) -> None:
        config = _initialized_config("manual_ops")

        blocked_code, blocked = handle_api_request(
            config,
            "POST",
            "/api/ops/manual-cycle",
            body={"mode": "auto"},
        )
        self.assertEqual(blocked_code, 403)
        self.assertEqual(blocked["error_code"], "confirmation_required")

        dry_code, dry_payload = handle_api_request(
            config,
            "POST",
            "/api/ops/manual-cycle",
            body={"mode": "auto", "dry_run": True},
        )
        self.assertEqual(dry_code, 200)
        self.assertTrue(dry_payload["ok"])
        self.assertEqual(dry_payload["data"]["result"]["status"], "planned")

        fake_result = type(
            "ManualOpsResult",
            (),
            {"status": "ok", "summary": "manual ops ok", "steps": ()},
        )()
        with patch(
            "target_opportunity_monitor.api_server.run_manual_ops_cycle",
            return_value=fake_result,
        ) as run_mock:
            confirmed_code, confirmed_payload = handle_api_request(
                config,
                "POST",
                "/api/ops/manual-cycle",
                body={"mode": "auto", "deliver": True, "channel": "file", "confirm": True},
            )

        self.assertEqual(confirmed_code, 200)
        self.assertTrue(confirmed_payload["ok"])
        run_mock.assert_called_once()

    def test_intraday_cycle_still_requires_confirmation(self) -> None:
        config = _initialized_config("intraday_confirmation")

        code, payload = handle_api_request(
            config,
            "POST",
            "/api/ops/intraday-cycle",
            body={"source": "auto"},
        )

        self.assertEqual(code, 403)
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["error_code"], "confirmation_required")

    def test_notification_drain_requires_confirmation(self) -> None:
        config = _initialized_config("notification_confirmation")

        code, payload = handle_api_request(
            config,
            "POST",
            "/api/notifications/drain",
            body={"channel": "file"},
        )

        self.assertEqual(code, 403)
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["error_code"], "confirmation_required")


if __name__ == "__main__":
    unittest.main()
