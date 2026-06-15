from __future__ import annotations

import csv
from datetime import date, timedelta
from pathlib import Path
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
TEST_TMP_ROOT = PROJECT_ROOT / ".tmp_tests" / "phase14f"
sys.path.insert(0, str(SRC_PATH))

from target_opportunity_monitor.api_server import handle_api_request
from target_opportunity_monitor.config import AppConfig
from target_opportunity_monitor.db import initialize_database
from target_opportunity_monitor.signal_coverage import (
    COVERAGE_GROUP_KEYS,
    SIGNAL_LANE_KEYS,
    build_signal_coverage_payload,
)
from target_opportunity_monitor.storage import Asset, Price, upsert_asset, upsert_prices
from target_opportunity_monitor.technical import (
    compute_regime_signals,
    compute_technical_signals,
)


def _config(tmpdir: str) -> AppConfig:
    root = Path(tmpdir)
    return AppConfig(
        project_root=root,
        config_path=root / "config.toml",
        database_path=root / "tom.sqlite",
        reports_dir=root / "reports",
        watchlist_path=root / "configs" / "watchlist.csv",
        cik_map_path=root / "configs" / "cik_map.csv",
        account_source_exports_dir=root / "data" / "account" / "source_exports",
        portfolio_positions_path=root / "data" / "portfolio" / "manual" / "positions.csv",
        portfolio_cash_path=root / "data" / "portfolio" / "manual" / "cash.csv",
        options_positions_path=root / "data" / "options" / "manual" / "options_positions.csv",
        options_chain_source_exports_dir=root / "data" / "options" / "source_exports",
        news_catalyst_source_exports_dir=root / "data" / "signals" / "source_exports" / "news_catalysts",
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
        technical_lookback_days=80,
        technical_minimum_history_days=20,
        technical_long_ma_days=20,
        regime_benchmark_tickers=("SPY", "QQQ"),
        regime_sector_proxy_tickers=("XLK",),
        regime_relative_strength_lookback_days=20,
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


def _seed_scoreable_equity(config: AppConfig, ticker: str = "TSLA") -> None:
    upsert_asset(
        config.database_path,
        Asset(
            ticker=ticker,
            name=f"{ticker} Test",
            asset_type="equity",
            exchange="NASDAQ",
            currency="USD",
            sector="Consumer Discretionary",
            industry="Auto Manufacturers",
            country="US",
            active_flag=1,
            asset_role="scoreable",
            source="unit_test",
            as_of_date="2026-06-14",
            effective_date="2026-06-14T00:00:00",
        ),
    )


def _price_series(ticker: str, count: int = 80) -> list[Price]:
    start = date.today() - timedelta(days=count - 1)
    rows: list[Price] = []
    for index in range(count):
        price_date = (start + timedelta(days=index)).isoformat()
        close = 100 + index * 0.5 + (index % 5) * 0.05
        rows.append(
            Price(
                ticker=ticker,
                price_date=price_date,
                open=close - 0.2,
                high=close + 0.8,
                low=close - 0.8,
                close=close,
                adjusted_close=close,
                volume=1_000_000 + index,
                source="unit_test",
            )
        )
    return rows


def _seed_prices(config: AppConfig, *tickers: str) -> None:
    for ticker in tickers:
        upsert_prices(config.database_path, _price_series(ticker))


class Phase14FSignalCoverageApiTests(unittest.TestCase):
    def test_signal_and_coverage_endpoints_handle_empty_state(self) -> None:
        config = _initialized_config("empty_state")

        signal_code, signal_payload = handle_api_request(config, "GET", "/api/signals/status")
        coverage_code, coverage_payload = handle_api_request(config, "GET", "/api/coverage/status")

        self.assertEqual(signal_code, 200)
        self.assertTrue(signal_payload["ok"])
        self.assertEqual(tuple(signal_payload["data"]["lane_keys"]), SIGNAL_LANE_KEYS)
        self.assertEqual(
            set(signal_payload["data"]["lane_map"]),
            set(SIGNAL_LANE_KEYS),
        )
        for lane in signal_payload["data"]["lanes"]:
            self.assertIn("status", lane)
            self.assertIn("blockers", lane)
            self.assertIn("warnings", lane)
            self.assertIn("notes", lane)

        self.assertEqual(coverage_code, 200)
        self.assertTrue(coverage_payload["ok"])
        self.assertEqual(tuple(coverage_payload["data"]["group_keys"]), COVERAGE_GROUP_KEYS)
        self.assertEqual(
            set(coverage_payload["data"]["group_map"]),
            set(COVERAGE_GROUP_KEYS),
        )
        account_group = coverage_payload["data"]["group_map"]["account_options_context"]
        self.assertEqual(account_group["status"], "source_data_required")
        self.assertEqual(
            account_group["counts"]["option_position_readiness_status"],
            "source_data_required",
        )
        self.assertEqual(account_group["counts"]["valid_option_position_rows"], 0)
        self.assertIn("empty_options_positions", account_group["blockers"])

    def test_api_status_lists_new_read_only_routes(self) -> None:
        config = _initialized_config("api_status_routes")

        code, payload = handle_api_request(config, "GET", "/api/health")

        self.assertEqual(code, 200)
        self.assertTrue(payload["ok"])
        endpoints = payload["data"]["api"]["endpoints"]
        self.assertIn("GET /api/signals/status", endpoints)
        self.assertIn("GET /api/coverage/status", endpoints)
        self.assertIn("GET /api/research/recommendations/triage", endpoints)
        self.assertIn("GET /api/research/preparation/status", endpoints)
        self.assertIn("POST /api/research/preparation/run", endpoints)
        self.assertIn("POST /api/research/recommendations/bulk-status", endpoints)

    def test_signal_endpoint_preserves_source_blockers_for_seeded_equity(self) -> None:
        config = _initialized_config("seeded_blockers")
        _seed_scoreable_equity(config)

        code, payload = handle_api_request(config, "GET", "/api/signals/status")

        self.assertEqual(code, 200)
        self.assertTrue(payload["ok"])
        short_interest = payload["data"]["lane_map"]["short_interest"]
        self.assertEqual(short_interest["status"], "provider_key_or_export_required")
        self.assertIn("missing_source_tickers", short_interest["blockers"])
        self.assertIn(
            "TSLA",
            short_interest["details"]["source_status"]["missing_source_tickers"],
        )

    def test_coverage_endpoint_marks_research_queue_as_user_review_required(self) -> None:
        config = _initialized_config("coverage_seeded")
        _seed_scoreable_equity(config)

        code, payload = handle_api_request(config, "GET", "/api/coverage/status")

        self.assertEqual(code, 200)
        self.assertTrue(payload["ok"])
        groups = payload["data"]["group_map"]
        self.assertIn("signal_evidence_lanes", groups)
        self.assertIn(groups["research_queue"]["status"], {"ready", "user_review_required"})
        self.assertIn("api_ui_runtime", groups)

    def test_coverage_endpoint_exposes_non_actionable_option_chain_notes(self) -> None:
        config = _initialized_config("coverage_non_actionable_options")
        _seed_scoreable_equity(config, "BIL")
        path = config.options_chain_source_exports_dir / "options_chain_non_actionable.csv"
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=(
                    "ticker",
                    "decision_date",
                    "reason_code",
                    "source",
                    "source_url",
                    "as_of_date",
                    "effective_date",
                    "notes",
                ),
            )
            writer.writeheader()
            writer.writerow(
                {
                    "ticker": "BIL",
                    "decision_date": date.today().isoformat(),
                    "reason_code": "no_listed_options",
                    "source": "unit_test_provider_review",
                    "source_url": "https://example.com/bil/options",
                    "as_of_date": date.today().isoformat(),
                    "effective_date": date.today().isoformat(),
                }
            )

        code, payload = handle_api_request(config, "GET", "/api/coverage/status")

        self.assertEqual(code, 200)
        self.assertTrue(payload["ok"])
        group = payload["data"]["group_map"]["account_options_context"]
        self.assertIn("non_actionable_option_chain_excluded", group["notes"])
        self.assertEqual(group["counts"]["option_chain_non_actionable_tickers"], ["BIL"])
        self.assertEqual(group["counts"]["option_chain_coverage_count"], "0/0")
        self.assertEqual(group["counts"]["option_chain_availability_unavailable_tickers"], ["BIL"])
        availability = group["details"]["option_chain_availability_statuses"]
        self.assertEqual(availability[0]["ticker"], "BIL")
        self.assertEqual(availability[0]["availability_status"], "unavailable")
        self.assertEqual(availability[0]["reason_code"], "no_listed_options")
        self.assertEqual(availability[0]["source"], "unit_test_provider_review")
        self.assertEqual(availability[0]["source_url"], "https://example.com/bil/options")
        self.assertFalse(availability[0]["raw_chain_available"])
        self.assertFalse(availability[0]["effective_coverage_included"])

    def test_technical_regime_lane_reports_missing_tickers(self) -> None:
        config = _initialized_config("technical_missing")
        _seed_scoreable_equity(config, "TSLA")

        code, payload = handle_api_request(config, "GET", "/api/signals/status")

        self.assertEqual(code, 200)
        self.assertTrue(payload["ok"])
        lane = payload["data"]["lane_map"]["technical_regime"]
        self.assertEqual(lane["status"], "source_data_required")
        self.assertIn("missing_technical_signal_rows", lane["blockers"])
        self.assertIn("missing_regime_signal_rows", lane["blockers"])
        self.assertEqual(lane["counts"]["technical_missing_tickers"], ["TSLA"])
        self.assertEqual(lane["counts"]["regime_missing_tickers"], ["SPY", "QQQ", "XLK"])
        self.assertEqual(lane["counts"]["technical_coverage"], "0/1")
        self.assertEqual(lane["counts"]["regime_coverage"], "0/3")

    def test_technical_regime_lane_ready_when_required_universes_complete(self) -> None:
        config = _initialized_config("technical_ready")
        _seed_scoreable_equity(config, "TSLA")
        _seed_prices(config, "TSLA", "SPY", "QQQ", "XLK")
        compute_technical_signals(config)
        compute_regime_signals(config)

        code, payload = handle_api_request(config, "GET", "/api/signals/status")

        self.assertEqual(code, 200)
        self.assertTrue(payload["ok"])
        lane = payload["data"]["lane_map"]["technical_regime"]
        self.assertEqual(lane["status"], "ready")
        self.assertEqual(lane["blockers"], [])
        self.assertEqual(lane["coverage_label"], "4/4")
        self.assertEqual(lane["counts"]["technical_coverage"], "1/1")
        self.assertEqual(lane["counts"]["regime_coverage"], "3/3")

    def test_technical_regime_lane_blocks_missing_regime_price_history(self) -> None:
        config = _initialized_config("regime_input_blocked")
        _seed_scoreable_equity(config, "TSLA")
        _seed_prices(config, "TSLA", "SPY", "QQQ")
        compute_technical_signals(config)
        compute_regime_signals(config)

        code, payload = handle_api_request(config, "GET", "/api/signals/status")

        self.assertEqual(code, 200)
        self.assertTrue(payload["ok"])
        lane = payload["data"]["lane_map"]["technical_regime"]
        self.assertEqual(lane["status"], "source_data_required")
        self.assertIn("regime_price_history_required", lane["blockers"])
        self.assertEqual(lane["counts"]["technical_coverage"], "1/1")
        self.assertEqual(lane["counts"]["regime_input_blocker_tickers"], ["XLK"])
        self.assertEqual(lane["counts"]["regime_coverage"], "2/3")

    def test_completed_news_provider_coverage_keeps_optional_limits_out_of_blockers(self) -> None:
        config = _initialized_config("news_optional_limits")
        source = SimpleNamespace(
            active_equity_count=1,
            provider_numeric_ticker_count=1,
            total_numeric_ticker_count=1,
            text_derived_ticker_count=0,
            source_snapshot_count=1,
            provider_native_upgrade_tickers=(),
            missing_numeric_tickers=(),
            warnings=("provider_limited",),
        )
        upgrade = SimpleNamespace(
            missing_key_providers=("marketaux",),
            provider_blockers=("marketaux:missing_key",),
            warnings=("marketaux:missing_marketaux_api_key",),
        )
        backfill = SimpleNamespace(
            blocked_apply_reason="no_valid_provider_native_backfill_rows",
            warnings=("no_valid_provider_native_backfill_rows",),
        )
        with patch(
            "target_opportunity_monitor.signal_coverage.news_catalyst_source_status_report",
            return_value=source,
        ), patch(
            "target_opportunity_monitor.signal_coverage.news_catalyst_provider_upgrade_status",
            return_value=upgrade,
        ), patch(
            "target_opportunity_monitor.signal_coverage.news_catalyst_provider_backfill_apply_status",
            return_value=backfill,
        ), patch(
            "target_opportunity_monitor.signal_coverage.news_catalyst_statuses",
            return_value=(),
        ), patch(
            "target_opportunity_monitor.signal_coverage.build_news_catalyst_source_status_text",
            return_value="source ok",
        ), patch(
            "target_opportunity_monitor.signal_coverage.build_news_catalyst_provider_upgrade_status_text",
            return_value="upgrade optional limits",
        ), patch(
            "target_opportunity_monitor.signal_coverage.build_news_catalyst_provider_backfill_status_text",
            return_value="backfill optional",
        ):
            payload = build_signal_coverage_payload(config)

        lane = payload["lane_map"]["news_catalyst"]
        self.assertEqual(lane["status"], "ready")
        self.assertEqual(lane["coverage_label"], "1/1")
        self.assertEqual(lane["blockers"], ())
        self.assertIn("optional_provider_limitations_not_blocking_coverage", lane["notes"])
        self.assertIn("marketaux:missing_key", lane["counts"]["optional_provider_blockers"])


if __name__ == "__main__":
    unittest.main()
