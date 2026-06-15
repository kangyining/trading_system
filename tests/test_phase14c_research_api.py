from __future__ import annotations

import csv
import sqlite3
from dataclasses import dataclass
import json
from pathlib import Path
import sys
import unittest
from uuid import uuid4
from unittest.mock import patch


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
TEST_TMP_ROOT = PROJECT_ROOT / ".tmp_tests" / "phase14c"
sys.path.insert(0, str(SRC_PATH))

from target_opportunity_monitor.api_server import handle_api_request
from target_opportunity_monitor.config import AppConfig
from target_opportunity_monitor.db import initialize_database
from target_opportunity_monitor.storage import (
    Asset,
    ResearchRecommendationCandidate,
    latest_estimate,
    list_fundamentals,
    list_research_recommendation_candidates,
    upsert_asset,
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
        etf_navs_path=root / "data" / "etf" / "manual" / "etf_navs.csv",
        etf_holdings_path=root / "data" / "etf" / "manual" / "etf_holdings.csv",
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


def _write_empty_sec_cache(config: AppConfig) -> None:
    cache_path = config.project_root / config.fundamental_cache_dir / "sec_company_tickers_exchange.json"
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(json.dumps({"fields": ["ticker", "cik", "name", "exchange"], "data": []}), encoding="utf-8")


def _write_foreign_equity_identity_rows(
    config: AppConfig,
    rows: list[dict[str, str]],
) -> None:
    path = config.foreign_equity_identity_path
    if not path.is_absolute():
        path = config.project_root / path
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = (
        "ticker",
        "name",
        "exchange",
        "currency",
        "country",
        "sector",
        "industry",
        "isin",
        "source",
        "source_url",
        "as_of_date",
        "effective_date",
        "notes",
    )
    with path.open("w", encoding="utf-8", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def _seed_recommendation(
    config: AppConfig,
    *,
    key: str,
    ticker: str,
    score: float = 50.0,
    warnings: str | None = None,
    blockers: str | None = None,
    status: str = "pending",
) -> None:
    upsert_research_recommendation_candidate(
        config.database_path,
        ResearchRecommendationCandidate(
            recommendation_key=key,
            ticker=ticker,
            recommendation_date="2026-06-12",
            source="codex_manual",
            status=status,
            topic="API test",
            rationale=f"Test recommendation for {ticker}.",
            research_priority_score=score,
            confidence=60.0,
            source_count=1,
            evidence_count=1,
            source_mix="codex_manual",
            metadata_status="unknown",
            warning_codes=warnings,
            promotion_blockers=blockers,
        ),
    )


@dataclass(frozen=True)
class _FakeRefreshResult:
    pipeline_run_id: int = 123
    status: str = "ok"
    steps: tuple[object, ...] = ()


class Phase14CResearchApiTests(unittest.TestCase):
    def test_research_recommendation_triage_endpoint_is_read_only(self) -> None:
        config = _initialized_config("recommendation_triage")
        _seed_recommendation(config, key="dup-1", ticker="CRWD", score=72.0)
        _seed_recommendation(config, key="dup-2", ticker="CRWD", score=68.0)
        _seed_recommendation(
            config,
            key="hood-1",
            ticker="HOOD",
            score=64.0,
            warnings="missing_cik_metadata",
            blockers="missing_cik_metadata",
        )

        with sqlite3.connect(config.database_path) as connection:
            before_decisions = connection.execute(
                "SELECT COUNT(*) FROM research_recommendation_decisions"
            ).fetchone()[0]
        code, payload = handle_api_request(
            config,
            "GET",
            "/api/research/recommendations/triage",
        )
        with sqlite3.connect(config.database_path) as connection:
            after_decisions = connection.execute(
                "SELECT COUNT(*) FROM research_recommendation_decisions"
            ).fetchone()[0]

        self.assertEqual(code, 200)
        self.assertTrue(payload["ok"])
        self.assertEqual(before_decisions, after_decisions)
        triage = payload["data"]["triage"]
        self.assertEqual(triage["pending_count"], 3)
        groups = {group["ticker"]: group for group in triage["groups"]}
        self.assertEqual(groups["CRWD"]["candidate_count"], 2)
        self.assertEqual(groups["CRWD"]["classification"], "promotion_ready_after_approval")
        self.assertEqual(groups["HOOD"]["classification"], "metadata_required")

    def test_research_preparation_status_endpoint_is_read_only(self) -> None:
        config = _initialized_config("preparation_status")
        _write_empty_sec_cache(config)
        upsert_asset(
            config.database_path,
            Asset(
                ticker="XLV",
                name="XLV ETF",
                asset_type="etf",
                asset_role="scoreable",
            ),
        )
        _seed_recommendation(config, key="xlv-1", ticker="XLV", warnings="already_scoreable")

        with sqlite3.connect(config.database_path) as connection:
            before_decisions = connection.execute(
                "SELECT COUNT(*) FROM research_recommendation_decisions"
            ).fetchone()[0]
        code, payload = handle_api_request(
            config,
            "GET",
            "/api/research/preparation/status",
        )
        with sqlite3.connect(config.database_path) as connection:
            after_decisions = connection.execute(
                "SELECT COUNT(*) FROM research_recommendation_decisions"
            ).fetchone()[0]

        self.assertEqual(code, 200)
        self.assertTrue(payload["ok"])
        self.assertEqual(before_decisions, after_decisions)
        preparation = payload["data"]["preparation"]
        self.assertEqual(preparation["total_items"], 1)
        self.assertEqual(preparation["items"][0]["preparation_state"], "prepared_already_scoreable")

    def test_research_preparation_status_serializes_source_automation_fields(self) -> None:
        config = _initialized_config("preparation_sources")
        _write_empty_sec_cache(config)
        upsert_asset(
            config.database_path,
            Asset(
                ticker="SOXL",
                name="SOXL ETF",
                asset_type="etf",
                asset_role="commentary_validation",
            ),
        )
        _seed_recommendation(
            config,
            key="soxl-1",
            ticker="SOXL",
            blockers="etf_research_ticker_requires_etf_path",
        )

        code, payload = handle_api_request(
            config,
            "GET",
            "/api/research/preparation/status?ticker=SOXL",
        )

        self.assertEqual(code, 200)
        item = payload["data"]["preparation"]["items"][0]
        self.assertEqual(item["ticker"], "SOXL")
        self.assertEqual(item["automation_stage"], "source_discovery_available")
        self.assertTrue(item["can_discover_sources"])
        self.assertTrue(item["can_stage_sources"])
        self.assertEqual(item["cannot_automate_reason"], "source_backed_data_required")
        self.assertEqual(item["source_candidates"][0]["source"], "direxion_official_page")
        preparation = payload["data"]["preparation"]
        self.assertIn("autopilot", preparation)
        self.assertTrue(preparation["autopilot"]["enabled"])

    def test_research_preparation_status_serializes_manual_blocker_packets(self) -> None:
        config = _initialized_config("preparation_manual_packets")
        _write_empty_sec_cache(config)
        _seed_recommendation(
            config,
            key="sive-1",
            ticker="SIVE",
            warnings="missing_cik_metadata",
            blockers="missing_cik_metadata",
        )

        code, payload = handle_api_request(
            config,
            "GET",
            "/api/research/preparation/status?source=all",
        )

        self.assertEqual(code, 200)
        preparation = payload["data"]["preparation"]
        packets = {packet["ticker"]: packet for packet in preparation["manual_blocker_packets"]}
        self.assertEqual(packets["SIVE"]["cannot_automate_reason"], "source_backed_identity_required")
        self.assertIn("source_backed_current_listing", packets["SIVE"]["required_fields"])
        self.assertEqual(preparation["autopilot"]["manual_blocker_tickers"], ["SIVE"])

    def test_research_preparation_run_requires_confirmation_for_mutations(self) -> None:
        config = _initialized_config("preparation_requires_confirmation")

        code, payload = handle_api_request(
            config,
            "POST",
            "/api/research/preparation/run",
            body={"action": "ignore_already_scoreable"},
        )

        self.assertEqual(code, 403)
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["error_code"], "confirmation_required")

    def test_research_preparation_discover_sources_is_read_only_without_confirmation(self) -> None:
        config = _initialized_config("preparation_discover_read_only")
        _write_empty_sec_cache(config)
        upsert_asset(
            config.database_path,
            Asset(
                ticker="SOXL",
                name="SOXL ETF",
                asset_type="etf",
                asset_role="commentary_validation",
            ),
        )
        _seed_recommendation(
            config,
            key="soxl-1",
            ticker="SOXL",
            blockers="etf_research_ticker_requires_etf_path",
        )

        with patch(
            "target_opportunity_monitor.research_preparation._fetch_direxion_etf_evidence"
        ) as fetch_mock:
            fetch_mock.return_value = type(
                "Evidence",
                (),
                {
                    "nav_per_share": 101.0,
                    "holdings": ({"holding_name": "A", "weight": 1.0},),
                    "warnings": (),
                    "blockers": (),
                },
            )()
            code, payload = handle_api_request(
                config,
                "POST",
                "/api/research/preparation/run",
                body={"action": "discover_sources", "tickers": ["SOXL"]},
            )

        self.assertEqual(code, 200)
        self.assertTrue(payload["ok"])
        self.assertFalse(payload["data"]["result"]["confirm"])
        self.assertEqual(payload["data"]["result"]["discovered_tickers"], ["SOXL"])

    def test_confirmed_research_preparation_ignores_context_without_promotion(self) -> None:
        config = _initialized_config("preparation_confirmed")
        _write_empty_sec_cache(config)
        upsert_asset(
            config.database_path,
            Asset(
                ticker="XLV",
                name="XLV ETF",
                asset_type="etf",
                asset_role="scoreable",
            ),
        )
        _seed_recommendation(config, key="xlv-1", ticker="XLV", warnings="already_scoreable")

        with patch("target_opportunity_monitor.api_server.promote_research_recommendation") as promote_mock:
            code, payload = handle_api_request(
                config,
                "POST",
                "/api/research/preparation/run",
                body={"action": "ignore_already_scoreable", "confirm": True},
            )

        self.assertEqual(code, 200)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["data"]["result"]["ignored_count"], 1)
        promote_mock.assert_not_called()
        self.assertEqual(list_research_recommendation_candidates(config.database_path)[0].status, "ignored")

    def test_bulk_recommendation_status_requires_confirmation(self) -> None:
        config = _initialized_config("bulk_requires_confirmation")
        _seed_recommendation(config, key="crwd-1", ticker="CRWD")
        candidate = list_research_recommendation_candidates(config.database_path)[0]

        code, payload = handle_api_request(
            config,
            "POST",
            "/api/research/recommendations/bulk-status",
            body={
                "ids": [candidate.research_recommendation_id],
                "status": "approved",
                "reason": "test",
            },
        )

        self.assertEqual(code, 403)
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["error_code"], "confirmation_required")

    def test_bulk_recommendation_status_rejects_invalid_payloads(self) -> None:
        config = _initialized_config("bulk_invalid_payloads")
        _seed_recommendation(config, key="crwd-1", ticker="CRWD")
        candidate = list_research_recommendation_candidates(config.database_path)[0]

        cases = (
            ({"ids": [], "status": "approved", "confirm": True}, "missing_recommendation_ids", 400),
            (
                {"ids": [candidate.research_recommendation_id], "status": "promoted", "confirm": True},
                "invalid_bulk_status",
                400,
            ),
            ({"ids": [999999], "status": "approved", "confirm": True}, "unknown_recommendation_ids", 404),
            ({"ids": ["not-an-id"], "status": "approved", "confirm": True}, "invalid_recommendation_ids", 400),
        )
        for body, expected_error, expected_status in cases:
            with self.subTest(expected_error=expected_error):
                code, payload = handle_api_request(
                    config,
                    "POST",
                    "/api/research/recommendations/bulk-status",
                    body=body,
                )
                self.assertEqual(code, expected_status)
                self.assertFalse(payload["ok"])
                self.assertEqual(payload["error_code"], expected_error)

    def test_bulk_recommendation_status_updates_requested_rows_only(self) -> None:
        config = _initialized_config("bulk_updates")
        _seed_recommendation(config, key="crwd-1", ticker="CRWD", score=72.0)
        _seed_recommendation(config, key="hood-1", ticker="HOOD", score=64.0)
        candidates = list_research_recommendation_candidates(config.database_path)
        target_id = candidates[0].research_recommendation_id
        untouched_id = candidates[1].research_recommendation_id

        with patch("target_opportunity_monitor.api_server.promote_research_recommendation") as promote_mock:
            with patch("target_opportunity_monitor.api_server.apply_research_ticker") as apply_mock:
                code, payload = handle_api_request(
                    config,
                    "POST",
                    "/api/research/recommendations/bulk-status",
                    body={
                        "ids": [target_id],
                        "status": "approved",
                        "reason": "api_bulk_test",
                        "confirm": True,
                    },
                )

        self.assertEqual(code, 200)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["data"]["result"]["updated_count"], 1)
        promote_mock.assert_not_called()
        apply_mock.assert_not_called()
        refreshed = {
            candidate.research_recommendation_id: candidate
            for candidate in list_research_recommendation_candidates(config.database_path)
        }
        self.assertEqual(refreshed[target_id].status, "approved")
        self.assertEqual(refreshed[untouched_id].status, "pending")
        with sqlite3.connect(config.database_path) as connection:
            decisions = connection.execute(
                "SELECT COUNT(*) FROM research_recommendation_decisions"
            ).fetchone()[0]
        self.assertEqual(decisions, 1)

    def test_ticker_plan_accepts_etf_path_and_serializes_readiness(self) -> None:
        config = _initialized_config("ticker_plan_etf")
        upsert_asset(
            config.database_path,
            Asset(
                ticker="XLV",
                name="Health Care Select Sector SPDR",
                asset_type="etf",
                asset_role="commentary_validation",
            ),
        )

        code, payload = handle_api_request(
            config,
            "POST",
            "/api/research/ticker-plan",
            body={"ticker": "XLV", "asset_type": "etf"},
        )

        self.assertEqual(code, 200)
        self.assertTrue(payload["ok"])
        plan = payload["data"]["plan"]
        self.assertEqual(plan["asset_type"], "etf")
        self.assertEqual(plan["research_path"], "etf")
        self.assertEqual(plan["blocked_reason"], "etf_readiness_required")
        self.assertIn("missing_etf_feature", plan["readiness_blockers"])
        self.assertNotIn("missing_cik", plan["readiness_blockers"])

    def test_ticker_plan_accepts_foreign_equity_path_and_serializes_identity(self) -> None:
        config = _initialized_config("ticker_plan_foreign_equity")
        _write_foreign_equity_identity_rows(
            config,
            [
                {
                    "ticker": "SOI",
                    "name": "Soitec SA",
                    "exchange": "Euronext Paris/XPAR",
                    "currency": "EUR",
                    "country": "France",
                    "sector": "Technology",
                    "industry": "Semiconductors",
                    "isin": "FR0013227113",
                    "source": "exchange_listing_page",
                    "source_url": "https://live.euronext.com/en/product/equities/FR0013227113-XPAR",
                    "as_of_date": "2026-06-15",
                    "effective_date": "2026-06-15",
                }
            ],
        )

        code, payload = handle_api_request(
            config,
            "POST",
            "/api/research/ticker-plan",
            body={"ticker": "SOI", "asset_type": "foreign_equity"},
        )

        self.assertEqual(code, 200)
        self.assertTrue(payload["ok"])
        plan = payload["data"]["plan"]
        self.assertEqual(plan["asset_type"], "foreign_equity")
        self.assertEqual(plan["research_path"], "foreign_equity")
        self.assertTrue(plan["apply_ready"])
        self.assertIsNone(plan["blocked_reason"])
        self.assertEqual(plan["metadata"]["cik"], None)
        self.assertEqual(plan["metadata"]["isin"], "FR0013227113")
        self.assertEqual(
            plan["metadata"]["source_url"],
            "https://live.euronext.com/en/product/equities/FR0013227113-XPAR",
        )
        self.assertNotIn("missing_cik", plan["readiness_blockers"])

    def test_foreign_equity_source_status_and_apply_are_guarded(self) -> None:
        config = _initialized_config("foreign_equity_source_api")
        _write_foreign_equity_identity_rows(
            config,
            [
                {
                    "ticker": "SOI",
                    "name": "Soitec SA",
                    "exchange": "Euronext Paris/XPAR",
                    "currency": "EUR",
                    "country": "France",
                    "sector": "Technology",
                    "industry": "Semiconductors",
                    "isin": "FR0013227113",
                    "source": "exchange_listing_page",
                    "source_url": "https://live.euronext.com/en/product/equities/FR0013227113-XPAR",
                    "as_of_date": "2026-06-15",
                    "effective_date": "2026-06-15",
                }
            ],
        )
        fundamentals_path = config.foreign_equity_fundamentals_source_path
        estimates_path = config.foreign_equity_estimates_source_path
        if not fundamentals_path.is_absolute():
            fundamentals_path = config.project_root / fundamentals_path
        if not estimates_path.is_absolute():
            estimates_path = config.project_root / estimates_path
        fundamentals_path.parent.mkdir(parents=True, exist_ok=True)
        estimates_path.parent.mkdir(parents=True, exist_ok=True)
        fundamentals_path.write_text(
            "\n".join(
                (
                    "ticker,fiscal_period_end,fiscal_period,report_type,currency,revenue,diluted_eps,source,as_of_date,effective_date,source_url,notes",
                    "SOI,2025-03-31,FY,annual,EUR,1000000,1.25,issuer_annual_report,2026-06-15,2025-03-31,https://example.com/soi-report.pdf,Source-backed test row.",
                )
            ),
            encoding="utf-8",
        )
        estimates_path.write_text(
            "\n".join(
                (
                    "ticker,estimate_date,fiscal_period_end,metric,fiscal_period,currency,consensus_mean,analyst_count,source,as_of_date,effective_date,source_url,notes",
                    "SOI,2026-06-15,2027-03-31,eps,NTM,EUR,1.40,4,provider_export,2026-06-15,2026-06-15,https://example.com/soi-consensus.csv,Source-backed consensus row.",
                )
            ),
            encoding="utf-8",
        )

        status_code, status_payload = handle_api_request(
            config,
            "GET",
            "/api/research/foreign-equity-source-status",
        )
        template_code, template_payload = handle_api_request(
            config,
            "POST",
            "/api/research/foreign-equity-source-template",
            body={"confirm": True},
        )
        dry_code, dry_payload = handle_api_request(
            config,
            "POST",
            "/api/research/foreign-equity-source-apply",
            body={"dry_run": True},
        )
        rows_after_dry_run = len(list_fundamentals(config.database_path, "SOI"))
        apply_code, apply_payload = handle_api_request(
            config,
            "POST",
            "/api/research/foreign-equity-source-apply",
            body={"confirm": True},
        )

        self.assertEqual(status_code, 200)
        self.assertEqual(status_payload["data"]["validation"]["valid_fundamental_rows"], 1)
        self.assertEqual(status_payload["data"]["validation"]["valid_estimate_rows"], 1)
        self.assertEqual(status_payload["data"]["validation"]["valid_analyst_target_rows"], 0)
        self.assertIn("analyst_targets_path", status_payload["data"]["validation"])
        self.assertEqual(template_code, 200)
        self.assertIn("analyst_targets_path", template_payload["data"])
        self.assertEqual(dry_code, 200)
        self.assertFalse(dry_payload["data"]["result"]["applied"])
        self.assertEqual(rows_after_dry_run, 0)
        self.assertEqual(len(list_fundamentals(config.database_path, "SOI")), 1)
        self.assertEqual(apply_code, 200)
        self.assertTrue(apply_payload["data"]["result"]["applied"])
        self.assertEqual(latest_estimate(config.database_path, "SOI", "eps").consensus_mean, 1.4)

    def test_etf_strategy_review_endpoint_serializes_missing_call_and_put_data(self) -> None:
        config = _initialized_config("etf_strategy_review")
        upsert_asset(
            config.database_path,
            Asset(
                ticker="XLV",
                name="Health Care Select Sector SPDR",
                asset_type="etf",
                asset_role="commentary_validation",
            ),
        )

        code, payload = handle_api_request(
            config,
            "GET",
            "/api/research/etf-strategy-review?ticker=XLV",
        )

        self.assertEqual(code, 200)
        self.assertTrue(payload["ok"])
        review = payload["data"]["review"]
        self.assertEqual(review["asset_type"], "etf")
        self.assertEqual(review["long_call"]["status"], "blocked")
        self.assertIn("missing_call_option_chain", review["long_call"]["blockers"])
        self.assertIn("missing_sell_put_review", review["sell_put"]["blockers"])
        self.assertIn("ETF strategy review", payload["data"]["review_text"])

    def test_ticker_status_endpoint_is_read_only(self) -> None:
        config = _initialized_config("ticker_status")

        code, payload = handle_api_request(
            config,
            "GET",
            "/api/research/ticker-status?ticker=TSLA",
        )

        self.assertEqual(code, 200)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["data"]["ticker"], "TSLA")
        self.assertIn("asset_not_added", payload["data"]["status"]["readiness_blockers"])
        self.assertIn("Research ticker status", payload["data"]["status_text"])

    def test_fundamental_benchmark_report_endpoint_is_read_only(self) -> None:
        config = _initialized_config("benchmark_report")

        code, payload = handle_api_request(
            config,
            "GET",
            "/api/research/fundamental-benchmark-report?ticker=TSLA",
        )

        self.assertEqual(code, 200)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["data"]["ticker"], "TSLA")
        self.assertIn("Fundamental Benchmark Report: TSLA", payload["data"]["report_markdown"])

    def test_research_refresh_requires_confirmation(self) -> None:
        config = _initialized_config("refresh_requires_confirmation")

        code, payload = handle_api_request(
            config,
            "POST",
            "/api/research/refresh-ticker",
            body={"ticker": "TSLA"},
        )

        self.assertEqual(code, 403)
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["error_code"], "confirmation_required")

    def test_research_refresh_returns_blockers(self) -> None:
        config = _initialized_config("refresh_blocked")

        with patch(
            "target_opportunity_monitor.api_server.refresh_research_ticker",
            return_value=(None, ("ticker_not_scoreable",)),
        ):
            code, payload = handle_api_request(
                config,
                "POST",
                "/api/research/refresh-ticker",
                body={"ticker": "TSLA", "confirm": True},
            )

        self.assertEqual(code, 409)
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["error_code"], "research_ticker_refresh_blocked")
        self.assertIn("ticker_not_scoreable", payload["warnings"])

    def test_research_refresh_success_returns_status(self) -> None:
        config = _initialized_config("refresh_success")

        with patch(
            "target_opportunity_monitor.api_server.refresh_research_ticker",
            return_value=(_FakeRefreshResult(), ("missing_score",)),
        ):
            code, payload = handle_api_request(
                config,
                "POST",
                "/api/research/refresh-ticker",
                body={"ticker": "TSLA", "confirm": True},
            )

        self.assertEqual(code, 200)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["data"]["result"]["pipeline_run_id"], 123)
        self.assertIn("missing_score", payload["data"]["readiness_blockers"])


if __name__ == "__main__":
    unittest.main()
