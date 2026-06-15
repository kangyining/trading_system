from __future__ import annotations

import csv
from datetime import date
from pathlib import Path
import sys
import unittest
from uuid import uuid4
from unittest.mock import patch


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
TEST_TMP_ROOT = PROJECT_ROOT / ".tmp_tests" / "phase14e"
sys.path.insert(0, str(SRC_PATH))

from target_opportunity_monitor.api_server import handle_api_request
from target_opportunity_monitor.config import AppConfig
from target_opportunity_monitor.db import initialize_database
from target_opportunity_monitor.news_catalyst_sources import (
    SOURCE_EXPORT_HEADERS as NEWS_SOURCE_EXPORT_HEADERS,
    aggregate_news_catalyst_sources,
    compute_news_catalyst_text_backfill,
    import_news_catalyst_source_exports,
)
from target_opportunity_monitor.options import OPTIONS_CHAIN_NON_ACTIONABLE_HEADERS
from target_opportunity_monitor.short_interest import load_short_interest_csv
from target_opportunity_monitor.storage import Asset, upsert_asset


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
        news_catalysts_path=root / "data" / "signals" / "manual" / "news_catalysts.csv",
        news_catalyst_cache_dir=root / "data" / "signals" / "cache" / "news_catalysts",
        short_interest_path=root / "data" / "signals" / "manual" / "short_interest.csv",
        short_interest_cache_dir=root / "data" / "signals" / "cache" / "short_interest",
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


def _seed_short_interest_gap(config: AppConfig) -> None:
    upsert_asset(config.database_path, Asset(ticker="AAPL", asset_type="equity"))
    upsert_asset(config.database_path, Asset(ticker="CRM", asset_type="equity"))
    config.short_interest_path.parent.mkdir(parents=True, exist_ok=True)
    config.short_interest_path.write_text(
        "\n".join(
            (
                "ticker,settlement_date,publication_date,short_interest,float_shares,"
                "percent_float,average_daily_volume,days_to_cover,source,source_url,"
                "notes,as_of_date,effective_date",
                "AAPL,2026-05-15,2026-05-20,1000,10000,0.10,250,4,"
                "fixture_source,https://example.com/aapl,fixture,,",
            )
        ),
        encoding="utf-8",
    )
    load_short_interest_csv(config)


def _news_source_row(**values: object) -> str:
    row = {header: "" for header in NEWS_SOURCE_EXPORT_HEADERS}
    row.update({key: str(value) for key, value in values.items() if value is not None})
    return ",".join(row[header] for header in NEWS_SOURCE_EXPORT_HEADERS)


def _seed_news_provider_native_gap(config: AppConfig) -> None:
    upsert_asset(config.database_path, Asset(ticker="AAPL", asset_type="equity"))
    upsert_asset(config.database_path, Asset(ticker="CRM", asset_type="equity"))
    source_path = config.news_catalyst_source_exports_dir / "manual.csv"
    source_path.parent.mkdir(parents=True, exist_ok=True)
    source_path.write_text(
        "\n".join(
            (
                ",".join(NEWS_SOURCE_EXPORT_HEADERS),
                _news_source_row(
                    ticker="AAPL",
                    signal_date="2026-06-12",
                    source="alpha_vantage",
                    source_url="https://example.com/aapl",
                    headline_or_event="AAPL provider native catalyst",
                    sentiment_score="75",
                ),
                _news_source_row(
                    ticker="CRM",
                    signal_date="2026-06-12",
                    source="finnhub",
                    source_url="https://example.com/crm",
                    headline_or_event="CRM headline only catalyst",
                ),
            )
        ),
        encoding="utf-8",
    )
    import_news_catalyst_source_exports(config, directory=source_path.parent)
    compute_news_catalyst_text_backfill(config)
    aggregate_news_catalyst_sources(config)


class Phase14EActivationApiTests(unittest.TestCase):
    def test_activation_and_backfill_get_endpoints_are_read_only(self) -> None:
        config = _initialized_config("get_endpoints")

        for path in (
            "/api/account/context-status",
            "/api/account/validate-backfill",
            "/api/account/preview-activation",
            "/api/backfills/options/status",
            "/api/backfills/options/validate",
            "/api/backfills/news/status",
            "/api/backfills/news/validate",
            "/api/backfills/short-interest/status",
            "/api/backfills/short-interest/validate",
        ):
            with self.subTest(path=path):
                code, payload = handle_api_request(config, "GET", path)
                self.assertEqual(code, 200)
                self.assertTrue(payload["ok"])

        code, payload = handle_api_request(config, "GET", "/api/backfills/options/status")
        self.assertEqual(code, 200)
        self.assertTrue(payload["ok"])
        self.assertIn("non_actionable", payload["data"])
        self.assertIn("availability_statuses", payload["data"])
        self.assertIn("effective_coverage_count", payload["data"]["plan"])
        self.assertIn("raw_coverage_count", payload["data"]["plan"])
        self.assertIn("valid_decision_count", payload["data"]["non_actionable"])

        code, payload = handle_api_request(config, "GET", "/api/backfills/news/status")
        self.assertEqual(code, 200)
        self.assertTrue(payload["ok"])
        self.assertIn("diagnostics", payload["data"])
        self.assertIn("diagnostics_text", payload["data"])
        self.assertIn("accepted_sources", payload["data"])

        code, payload = handle_api_request(config, "GET", "/api/backfills/short-interest/status")
        self.assertEqual(code, 200)
        self.assertTrue(payload["ok"])
        self.assertIn("missing_plan", payload["data"])
        self.assertIn("missing_plan_text", payload["data"])
        self.assertIn("diagnostics", payload["data"]["missing_plan"])

        code, payload = handle_api_request(config, "GET", "/api/account/context-status")
        self.assertEqual(code, 200)
        self.assertTrue(payload["ok"])
        self.assertIn("option_position_diagnostics", payload["data"])
        diagnostics = payload["data"]["option_position_diagnostics"]
        self.assertEqual(diagnostics["readiness_status"], "source_data_required")
        self.assertIn("empty_options_positions", diagnostics["blockers"])

    def test_options_status_serializes_chain_availability_decision(self) -> None:
        config = _initialized_config("options_availability")
        upsert_asset(config.database_path, Asset(ticker="BIL", asset_type="etf"))
        path = config.options_chain_source_exports_dir / "options_chain_non_actionable.csv"
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=OPTIONS_CHAIN_NON_ACTIONABLE_HEADERS)
            writer.writeheader()
            writer.writerow(
                {
                    "ticker": "BIL",
                    "decision_date": date.today().isoformat(),
                    "reason_code": "not_options_strategy_candidate",
                    "source": "nasdaq_option_chain",
                    "source_url": "https://www.nasdaq.com/market-activity/etf/bil/option-chain",
                    "as_of_date": date.today().isoformat(),
                    "effective_date": date.today().isoformat(),
                    "notes": "Nasdaq BIL option-chain page reports option chain currently not available.",
                }
            )

        code, payload = handle_api_request(config, "GET", "/api/backfills/options/status")

        self.assertEqual(code, 200)
        self.assertTrue(payload["ok"])
        statuses = payload["data"]["availability_statuses"]
        self.assertEqual(len(statuses), 1)
        self.assertEqual(statuses[0]["ticker"], "BIL")
        self.assertEqual(statuses[0]["availability_status"], "unavailable")
        self.assertEqual(statuses[0]["reason_code"], "not_options_strategy_candidate")
        self.assertEqual(statuses[0]["source"], "nasdaq_option_chain")
        self.assertFalse(statuses[0]["raw_chain_available"])
        self.assertFalse(statuses[0]["effective_coverage_included"])

    def test_mutating_activation_endpoints_require_confirmation(self) -> None:
        config = _initialized_config("requires_confirmation")

        requests = (
            ("/api/account/export-template", {}),
            ("/api/account/append-row", {"row_type": "portfolio_cash", "row": {}}),
            ("/api/account/apply-backfill", {"allow_partial": True}),
            ("/api/account/normalize-export", {"provider": "generic", "file": "missing.csv"}),
            ("/api/backfills/options/export-template", {}),
            ("/api/backfills/options/apply", {"allow_partial": True}),
            ("/api/backfills/news/export-template", {}),
            ("/api/backfills/news/append-row", {"row": {}}),
            ("/api/backfills/news/apply", {"allow_partial": True}),
            ("/api/backfills/short-interest/export-template", {}),
            ("/api/backfills/short-interest/append-row", {"row": {}}),
            ("/api/backfills/short-interest/apply", {}),
        )
        for path, body in requests:
            with self.subTest(path=path):
                code, payload = handle_api_request(config, "POST", path, body=body)
                self.assertEqual(code, 403)
                self.assertFalse(payload["ok"])
                self.assertEqual(payload["error_code"], "confirmation_required")

    def test_account_append_row_writes_source_export_row(self) -> None:
        config = _initialized_config("append_row")

        code, payload = handle_api_request(
            config,
            "POST",
            "/api/account/append-row",
            body={
                "confirm": True,
                "row_type": "portfolio_cash",
                "row": {
                    "account": "test",
                    "cash_date": "2026-06-13",
                    "currency": "USD",
                    "cash_amount": "1000",
                    "source": "unit_test",
                },
            },
        )

        self.assertEqual(code, 200)
        self.assertTrue(payload["ok"])
        written = config.account_source_exports_dir / "ui_portfolio_cash_backfill.csv"
        self.assertTrue(written.exists())
        self.assertIn("1000", written.read_text(encoding="utf-8"))

    def test_account_append_option_row_returns_lifecycle_readiness_diagnostics(self) -> None:
        config = _initialized_config("append_option_row")
        upsert_asset(
            config.database_path,
            Asset(
                ticker="AAPL",
                asset_type="equity",
                active_flag=1,
                asset_role="scoreable",
            ),
        )

        code, payload = handle_api_request(
            config,
            "POST",
            "/api/account/append-row",
            body={
                "confirm": True,
                "row_type": "option_position",
                "row": {
                    "position_id": "aapl-put-1",
                    "ticker": "AAPL",
                    "open_date": "2026-06-12",
                    "expiration_date": "2026-07-17",
                    "option_type": "put",
                    "side": "short_put",
                    "strike": "180",
                    "contracts": "1",
                    "premium": "2.1",
                    "account": "paper",
                    "status": "open",
                    "source": "unit_test_source",
                    "source_url": "https://example.com/aapl-put",
                },
            },
        )

        self.assertEqual(code, 200)
        self.assertTrue(payload["ok"])
        written = config.account_source_exports_dir / "ui_options_positions_backfill.csv"
        self.assertTrue(written.exists())
        self.assertIn("aapl-put-1", written.read_text(encoding="utf-8"))
        result = payload["data"]["result"]
        diagnostics = result["option_position_diagnostics"]
        self.assertEqual(diagnostics["readiness_status"], "ready_for_apply")
        self.assertEqual(diagnostics["valid_option_position_rows"], 1)
        self.assertEqual(diagnostics["projected_option_position_rows"], 1)
        self.assertEqual(diagnostics["projected_option_lifecycle_rows"], 1)

    def test_news_append_row_writes_provider_native_backfill_row_only(self) -> None:
        config = _initialized_config("news_append")
        _seed_news_provider_native_gap(config)
        before_news_text = (
            config.news_catalysts_path.read_text(encoding="utf-8")
            if config.news_catalysts_path.exists()
            else ""
        )

        code, payload = handle_api_request(
            config,
            "POST",
            "/api/backfills/news/append-row",
            body={
                "confirm": True,
                "row": {
                    "ticker": "CRM",
                    "signal_date": "2026-06-12",
                    "source": "marketaux_export",
                    "source_url": "https://example.com/crm-provider",
                    "headline_or_event": "CRM provider native catalyst",
                    "sentiment_score": "82",
                    "capture_method": "ui_manual",
                },
            },
        )

        self.assertEqual(code, 200)
        self.assertTrue(payload["ok"])
        written = (
            config.news_catalyst_source_exports_dir
            / "provider_native_backfill"
            / "news_catalyst_provider_native_backfill.csv"
        )
        self.assertTrue(written.exists())
        self.assertIn("CRM,2026-06-12", written.read_text(encoding="utf-8"))
        after_news_text = (
            config.news_catalysts_path.read_text(encoding="utf-8")
            if config.news_catalysts_path.exists()
            else ""
        )
        self.assertEqual(after_news_text, before_news_text)

        status = payload["data"]["result"]["status"]
        self.assertEqual(status["preview"]["valid_backfill_tickers"], ["CRM"])
        self.assertEqual(status["preview"]["projected_provider_native_ticker_count"], 2)
        diagnostics = {item["ticker"]: item for item in status["diagnostics"]}
        self.assertEqual(
            diagnostics["CRM"]["classification"],
            "valid_provider_native_row_ready",
        )

    def test_news_append_row_surfaces_invalid_provider_native_validation(self) -> None:
        config = _initialized_config("news_append_invalid")
        _seed_news_provider_native_gap(config)

        code, payload = handle_api_request(
            config,
            "POST",
            "/api/backfills/news/append-row",
            body={
                "confirm": True,
                "row": {
                    "ticker": "CRM",
                    "signal_date": "2026-06-12",
                    "source": "finnhub",
                    "headline_or_event": "CRM unsupported provider native row",
                    "sentiment_score": "bad",
                },
            },
        )

        self.assertEqual(code, 200)
        self.assertTrue(payload["ok"])
        status = payload["data"]["result"]["status"]
        self.assertEqual(status["validation"]["invalid_row_count"], 1)
        self.assertEqual(
            status["apply_status"]["blocked_apply_reason"],
            "invalid_provider_native_backfill_rows",
        )
        diagnostics = {item["ticker"]: item for item in status["diagnostics"]}
        self.assertEqual(diagnostics["CRM"]["classification"], "invalid_provider_native_row")
        self.assertIn("unsupported_provider_native_source", diagnostics["CRM"]["warnings"])

    def test_short_interest_append_row_writes_missing_provider_row_only(self) -> None:
        config = _initialized_config("short_interest_append")
        _seed_short_interest_gap(config)

        code, payload = handle_api_request(
            config,
            "POST",
            "/api/backfills/short-interest/append-row",
            body={
                "confirm": True,
                "row": {
                    "ticker": "CRM",
                    "settlement_date": "2026-05-31",
                    "publication_date": "2026-06-03",
                    "short_interest": "2000",
                    "float_shares": "20000",
                    "average_daily_volume": "500",
                    "source": "provider_export",
                    "source_url": "https://example.com/crm",
                    "notes": "fixture",
                    "capture_method": "ui_manual",
                },
            },
        )

        self.assertEqual(code, 200)
        self.assertTrue(payload["ok"])
        written = (
            config.project_root
            / "data"
            / "signals"
            / "source_exports"
            / "short_interest"
            / "missing_provider_short_interest_backfill.csv"
        )
        self.assertTrue(written.exists())
        self.assertIn("CRM,2026-05-31", written.read_text(encoding="utf-8"))
        self.assertNotIn("CRM,2026-05-31", config.short_interest_path.read_text(encoding="utf-8"))

        status = payload["data"]["result"]["status"]
        self.assertEqual(status["missing_plan"]["valid_missing_tickers"], ["CRM"])
        self.assertEqual(status["missing_plan"]["projected_source_backed_count"], 2)

    def test_short_interest_append_row_surfaces_invalid_validation(self) -> None:
        config = _initialized_config("short_interest_append_invalid")
        _seed_short_interest_gap(config)

        code, payload = handle_api_request(
            config,
            "POST",
            "/api/backfills/short-interest/append-row",
            body={
                "confirm": True,
                "row": {
                    "ticker": "CRM",
                    "settlement_date": "2026-05-31",
                    "source": "provider_export",
                },
            },
        )

        self.assertEqual(code, 200)
        self.assertTrue(payload["ok"])
        status = payload["data"]["result"]["status"]
        self.assertEqual(status["validation"]["invalid_row_count"], 1)
        self.assertEqual(
            status["missing_plan"]["blocked_apply_reason"],
            "invalid_short_interest_backfill_rows",
        )

    def test_account_apply_blocks_when_templates_are_blank(self) -> None:
        config = _initialized_config("blank_apply")

        code, payload = handle_api_request(
            config,
            "POST",
            "/api/account/apply-backfill",
            body={"confirm": True, "allow_partial": True},
        )

        self.assertEqual(code, 409)
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["error_code"], "account_context_apply_blocked")

    def test_account_apply_success_can_be_mocked_for_valid_partial_rows(self) -> None:
        config = _initialized_config("mock_apply_success")
        fake_result = type(
            "AccountApply",
            (),
            {
                "applied": True,
                "warnings": ("partial_account_context",),
                "positions_loaded": 1,
                "cash_loaded": 1,
                "option_positions_loaded": 0,
            },
        )()

        with patch(
            "target_opportunity_monitor.api_server.apply_account_context_backfill",
            return_value=fake_result,
        ) as apply_mock:
            code, payload = handle_api_request(
                config,
                "POST",
                "/api/account/apply-backfill",
                body={"confirm": True, "allow_partial": True},
            )

        self.assertEqual(code, 200)
        self.assertTrue(payload["ok"])
        apply_mock.assert_called_once()

    def test_backfill_apply_preserves_existing_blockers(self) -> None:
        config = _initialized_config("backfill_blockers")
        fake_options = type(
            "OptionApply",
            (),
            {"success": False, "warnings": ("no_valid_option_backfill_rows",)},
        )()
        fake_news = type(
            "NewsApply",
            (),
            {"applied": False, "warnings": ("no_valid_provider_native_backfill_rows",)},
        )()
        fake_short = type(
            "ShortApply",
            (),
            {
                "blocked_apply_reason": "no_valid_missing_short_interest_rows",
                "warnings": ("no_valid_missing_short_interest_rows",),
            },
        )()

        with patch(
            "target_opportunity_monitor.api_server.apply_options_chain_coverage_backfill",
            return_value=fake_options,
        ):
            code, payload = handle_api_request(
                config,
                "POST",
                "/api/backfills/options/apply",
                body={"confirm": True, "allow_partial": True},
            )
        self.assertEqual(code, 409)
        self.assertTrue(payload["ok"])

        with patch(
            "target_opportunity_monitor.api_server.apply_news_catalyst_provider_backfill",
            return_value=fake_news,
        ), patch(
            "target_opportunity_monitor.api_server.build_news_catalyst_provider_backfill_apply_text",
            return_value="blocked",
        ):
            code, payload = handle_api_request(
                config,
                "POST",
                "/api/backfills/news/apply",
                body={"confirm": True, "allow_partial": True},
            )
        self.assertEqual(code, 409)
        self.assertTrue(payload["ok"])

        with patch(
            "target_opportunity_monitor.api_server.apply_short_interest_provider_backfill",
            return_value=fake_short,
        ):
            code, payload = handle_api_request(
                config,
                "POST",
                "/api/backfills/short-interest/apply",
                body={"confirm": True},
            )
        self.assertEqual(code, 409)
        self.assertTrue(payload["ok"])


if __name__ == "__main__":
    unittest.main()
