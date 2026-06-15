from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path
import json
import re
import shutil
import sys
import unittest
from unittest.mock import patch


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
TEST_TMP_ROOT = PROJECT_ROOT / ".tmp_tests" / "phase10g"
sys.path.insert(0, str(SRC_PATH))

from target_opportunity_monitor.config import AppConfig, load_config
from target_opportunity_monitor.dashboard import build_dashboard
from target_opportunity_monitor.db import REQUIRED_TABLES, initialize_database
from target_opportunity_monitor.reporting import write_daily_report
from target_opportunity_monitor.short_interest import (
    COMPOSITE_SIGNAL_NAME,
    SIGNAL_FAMILY,
    apply_short_interest_provider_backfill,
    build_short_interest_missing_coverage_plan_text,
    build_short_interest_provider_backfill_apply_text,
    build_short_interest_provider_diagnostics_text,
    build_short_interest_backfill_validation_text,
    build_short_interest_coverage_plan_text,
    build_short_interest_import_preview_text,
    build_short_interest_provider_status_text,
    build_short_interest_source_status_text,
    build_short_interest_missing_source_resolution_text,
    build_short_interest_status_text,
    compute_short_interest_signals,
    export_short_interest_backfill,
    export_short_interest_missing_provider_template,
    fetch_short_interest_sources,
    import_short_interest_source_exports,
    load_short_interest_csv,
    normalize_short_interest_provider_export,
    parse_short_interest_csv,
    resolve_short_interest_missing_sources,
    short_interest_missing_coverage_plan,
    short_interest_provider_diagnostics,
    short_interest_provider_status,
    short_interest_source_exports_dir,
    short_interest_source_status_report,
    short_interest_statuses,
    validate_short_interest_backfill,
)
from target_opportunity_monitor.signal_validation import (
    build_short_interest_validation_report,
    validate_short_interest_signals,
)
from target_opportunity_monitor.storage import (
    Asset,
    Price,
    PriceFeature,
    count_rows_by_table,
    list_short_interest_source_snapshots,
    list_signal_outcomes,
    list_stored_signals,
    upsert_asset,
    upsert_price_feature,
    upsert_prices,
)


def fresh_database_path(name: str) -> Path:
    TEST_TMP_ROOT.mkdir(exist_ok=True)
    path = TEST_TMP_ROOT / name
    if path.exists():
        path.unlink()
    return path


def make_config(database_path: Path) -> AppConfig:
    return AppConfig(
        project_root=TEST_TMP_ROOT,
        config_path=TEST_TMP_ROOT / f"phase10g_{database_path.stem}.toml",
        database_path=database_path,
        reports_dir=TEST_TMP_ROOT / "reports_phase10g",
        watchlist_path=TEST_TMP_ROOT / "watchlist_phase10g.csv",
        market_data_dir=TEST_TMP_ROOT / "market_data_phase10g",
        manual_prices_dir=TEST_TMP_ROOT / "market_data_phase10g" / "manual",
        market_data_primary_source="stooq",
        market_data_secondary_source="yahoo_chart",
        market_data_mode="csv",
        market_data_lookback_days=800,
        market_data_stale_after_days=7,
        market_data_minimum_history_days=252,
        universe_mode="manual_watchlist",
        run_mode="daily_scoring",
        report_title="Target Opportunity Monitor Daily Report",
        short_interest_path=TEST_TMP_ROOT / "signals" / "manual" / f"{database_path.stem}.csv",
        short_interest_cache_dir=TEST_TMP_ROOT
        / "signals"
        / "cache"
        / f"{database_path.stem}",
        signals_short_interest_model_version="short_interest_mvp_v1",
        signals_short_interest_shadow_mode=True,
        signals_short_interest_stale_after_days=45,
        signals_short_interest_provider_retry_delay_seconds=0.0,
    )


def seed_assets(config: AppConfig) -> None:
    initialize_database(config.database_path)
    upsert_asset(config.database_path, Asset(ticker="AAPL", asset_type="equity"))
    upsert_asset(config.database_path, Asset(ticker="MSFT", asset_type="equity"))
    upsert_asset(config.database_path, Asset(ticker="SPY", asset_type="etf"))


def seed_expanded_assets(config: AppConfig) -> None:
    initialize_database(config.database_path)
    for ticker in (
        "AAPL",
        "AMD",
        "AMZN",
        "AVGO",
        "COST",
        "CRM",
        "GOOGL",
        "JPM",
        "LLY",
        "META",
        "MSFT",
        "NVDA",
        "ORCL",
    ):
        upsert_asset(config.database_path, Asset(ticker=ticker, asset_type="equity"))
    upsert_asset(config.database_path, Asset(ticker="SPY", asset_type="etf"))
    upsert_asset(config.database_path, Asset(ticker="QQQ", asset_type="etf"))


def seed_current_short_interest_gap(config: AppConfig) -> None:
    covered = ("AAPL", "AMD", "AMZN", "AVGO", "COST", "GOOGL", "META", "MSFT", "NVDA")
    config.short_interest_path.parent.mkdir(parents=True, exist_ok=True)
    rows = [
        "ticker,settlement_date,publication_date,short_interest,float_shares,percent_float,average_daily_volume,days_to_cover,source,source_url,notes,as_of_date,effective_date"
    ]
    for ticker in covered:
        rows.append(
            f"{ticker},2026-05-15,2026-05-20,1000,10000,0.10,250,4,fixture_source,https://example.com/{ticker.lower()},fixture,,"
        )
    config.short_interest_path.write_text("\n".join(rows), encoding="utf-8")
    load_short_interest_csv(config)


def price_row(ticker: str, price_date: str, close: float) -> Price:
    return Price(
        ticker=ticker,
        price_date=price_date,
        open=close,
        high=close + 1,
        low=close - 1,
        close=close,
        adjusted_close=close,
        volume=1_000_000,
        source="fixture",
        as_of_date=price_date,
        effective_date=price_date,
    )


def seed_price_context(config: AppConfig, ticker: str = "AAPL") -> None:
    signal_date = date(2026, 5, 31)
    prices = [
        price_row(ticker, (signal_date + timedelta(days=index)).isoformat(), 100 + index)
        for index in range(7)
    ]
    upsert_prices(config.database_path, prices)
    upsert_price_feature(
        config.database_path,
        PriceFeature(
            ticker=ticker,
            feature_date="2026-06-06",
            current_price=106,
            return_1d=0.01,
            return_1m=0.06,
            return_3m=0.08,
            return_6m=0.12,
            return_12m=0.18,
            realized_volatility_20d=0.2,
            realized_volatility_60d=0.25,
            average_dollar_volume_20d=500_000_000,
            latest_price_date="2026-06-06",
            source="fixture",
            as_of_date="2026-06-06",
            effective_date="2026-06-06",
        ),
    )


class Phase10GShortInterestTest(unittest.TestCase):
    def tearDown(self) -> None:
        if TEST_TMP_ROOT.exists():
            shutil.rmtree(TEST_TMP_ROOT)

    def test_config_defaults_and_schema_initialize(self) -> None:
        config = load_config(PROJECT_ROOT / "configs" / "default.toml")
        self.assertEqual(
            config.short_interest_path,
            PROJECT_ROOT / "data" / "signals" / "manual" / "short_interest.csv",
        )
        self.assertEqual(config.signals_short_interest_model_version, "short_interest_mvp_v1")
        self.assertTrue(config.signals_short_interest_shadow_mode)
        self.assertEqual(config.signals_short_interest_stale_after_days, 45)
        self.assertEqual(
            config.short_interest_cache_dir,
            PROJECT_ROOT / "data" / "signals" / "cache" / "short_interest",
        )
        self.assertIn("finra", config.signals_short_interest_provider_order)
        self.assertIn("nasdaq_trader", config.signals_short_interest_provider_order)
        self.assertEqual(config.signals_short_interest_provider_timeout_seconds, 12)

        database_path = fresh_database_path("phase10g_schema.sqlite")
        status = initialize_database(database_path)
        self.assertIn("short_interest_source_snapshots", status.existing_tables)
        self.assertEqual(status.required_table_count, len(REQUIRED_TABLES))
        self.assertEqual(count_rows_by_table(database_path, "short_interest_source_snapshots"), 0)

    def test_parser_and_loader_derive_fields_and_gate_etfs(self) -> None:
        database_path = fresh_database_path("phase10g_loader.sqlite")
        config = make_config(database_path)
        seed_assets(config)
        config.short_interest_path.parent.mkdir(parents=True, exist_ok=True)
        config.short_interest_path.write_text(
            "\n".join(
                (
                    "ticker,settlement_date,publication_date,short_interest,float_shares,percent_float,average_daily_volume,days_to_cover,source,source_url,notes,as_of_date,effective_date",
                    "AAPL,2026-05-31,2026-06-03,1000,10000,,250,,nasdaq_manual,https://example.com/aapl,fixture,,",
                    "SPY,2026-05-31,2026-06-03,1000,10000,10%,250,4,nasdaq_manual,https://example.com/spy,fixture,,",
                )
            ),
            encoding="utf-8",
        )

        parsed = parse_short_interest_csv(config.short_interest_path.read_text(encoding="utf-8"))
        self.assertEqual(parsed[0].percent_float, 0.1)
        self.assertEqual(parsed[0].days_to_cover, 4.0)
        self.assertIn("derived_percent_float", parsed[0].warnings)
        self.assertEqual(parsed[1].percent_float, 0.1)

        result = load_short_interest_csv(config)
        self.assertEqual(result.loaded_count, 1)
        self.assertEqual(result.skipped_count, 1)
        self.assertIn("SPY:etf_short_interest_gated", result.warnings)
        snapshots = list_short_interest_source_snapshots(database_path, "AAPL")
        self.assertEqual(len(snapshots), 1)
        self.assertEqual(snapshots[0].percent_float, 0.1)
        self.assertEqual(snapshots[0].days_to_cover, 4.0)

    def test_compute_short_interest_signals_scores_history_and_squeeze(self) -> None:
        database_path = fresh_database_path("phase10g_compute.sqlite")
        config = make_config(database_path)
        seed_assets(config)
        seed_price_context(config)
        config.short_interest_path.parent.mkdir(parents=True, exist_ok=True)
        config.short_interest_path.write_text(
            "\n".join(
                (
                    "ticker,settlement_date,publication_date,short_interest,float_shares,percent_float,average_daily_volume,days_to_cover,source,source_url,notes,as_of_date,effective_date",
                    "AAPL,2026-05-15,2026-05-18,1000,10000,0.10,250,4,nasdaq_manual,https://example.com/aapl-old,fixture,,",
                    "AAPL,2026-05-31,2026-06-03,900,10000,0.09,250,3.6,nasdaq_manual,https://example.com/aapl-new,fixture,,",
                )
            ),
            encoding="utf-8",
        )

        result = compute_short_interest_signals(config)
        by_ticker = {item.ticker: item for item in result.results}
        self.assertEqual(by_ticker["AAPL"].status, "computed")
        self.assertEqual(by_ticker["MSFT"].status, "skipped")
        self.assertEqual(by_ticker["SPY"].warnings, ("etf_short_interest_gated",))
        self.assertIn("squeeze_candidate_shadow_only", by_ticker["AAPL"].warnings)
        self.assertNotIn("missing_short_interest_history", by_ticker["AAPL"].warnings)

        signals = list_stored_signals(database_path, ticker="AAPL", signal_family=SIGNAL_FAMILY)
        self.assertEqual(len(signals), 5)
        composite = [signal for signal in signals if signal.signal_name == COMPOSITE_SIGNAL_NAME][0]
        self.assertEqual(composite.model_version, "short_interest_mvp_v1")
        self.assertEqual(composite.source, "short_interest")
        self.assertIn("short_interest_shadow_mode", composite.data_warnings or "")

    def test_missing_history_is_neutral_and_validation_creates_pending_outcome(self) -> None:
        database_path = fresh_database_path("phase10g_validate.sqlite")
        config = make_config(database_path)
        seed_assets(config)
        seed_price_context(config)
        config.short_interest_path.parent.mkdir(parents=True, exist_ok=True)
        config.short_interest_path.write_text(
            "\n".join(
                (
                    "ticker,settlement_date,publication_date,short_interest,float_shares,percent_float,average_daily_volume,days_to_cover,source,source_url,notes,as_of_date,effective_date",
                    "AAPL,2026-05-31,2026-06-03,900,10000,0.09,250,3.6,nasdaq_manual,https://example.com/aapl,fixture,,",
                )
            ),
            encoding="utf-8",
        )
        compute_result = compute_short_interest_signals(config, ticker="AAPL")
        self.assertIn("missing_short_interest_history", compute_result.results[0].warnings)

        validation = validate_short_interest_signals(config, ticker="AAPL")
        self.assertEqual(validation.updated_count, 1)
        outcomes = list_signal_outcomes(
            database_path,
            ticker="AAPL",
            signal_family=SIGNAL_FAMILY,
            signal_name=COMPOSITE_SIGNAL_NAME,
        )
        self.assertEqual(len(outcomes), 1)
        self.assertEqual(outcomes[0].outcome_status, "partial")
        self.assertIsNotNone(outcomes[0].return_5d)

        report = build_short_interest_validation_report(config)
        self.assertIn("Short Interest Signal Validation Report", report)
        self.assertIn("Signal outcome rows: 1", report)

    def test_backfill_export_creates_missing_equity_templates(self) -> None:
        database_path = fresh_database_path("phase10g_backfill_export.sqlite")
        config = make_config(database_path)
        seed_assets(config)

        result = export_short_interest_backfill(config)
        self.assertTrue(result.source_exports_dir.exists())
        self.assertTrue(result.backfill_path.exists())
        self.assertEqual(result.missing_tickers, ("AAPL", "MSFT"))
        self.assertEqual(result.etf_gated_tickers, ("SPY",))

        backfill_text = result.backfill_path.read_text(encoding="utf-8")
        self.assertIn("AAPL", backfill_text)
        self.assertIn("MSFT", backfill_text)
        self.assertNotIn("SPY", backfill_text)
        for template_name in ("provider_export.csv", "exchange_manual.csv", "broker_manual.csv"):
            self.assertTrue((result.source_exports_dir / template_name).exists())

        validation = validate_short_interest_backfill(config)
        self.assertEqual(validation.blank_placeholder_count, 2)
        self.assertEqual(validation.valid_row_count, 0)
        self.assertEqual(validation.projected_source_backed_count, 0)
        self.assertEqual(validation.blocked_import_reason, "no_valid_short_interest_backfill_rows")

        coverage_text = build_short_interest_coverage_plan_text(config)
        self.assertIn("Current source-backed coverage: 0/2", coverage_text)
        self.assertIn("Missing source tickers: AAPL, MSFT", coverage_text)
        source_text = build_short_interest_source_status_text(config, missing_only=True)
        self.assertIn("Missing source tickers: AAPL, MSFT", source_text)

    def test_backfill_validation_import_and_signal_consumption(self) -> None:
        database_path = fresh_database_path("phase10g_backfill_import.sqlite")
        config = make_config(database_path)
        seed_assets(config)
        seed_price_context(config)
        export_result = export_short_interest_backfill(config)
        provider_export = export_result.source_exports_dir / "provider_export.csv"
        provider_export.write_text(
            "\n".join(
                (
                    "ticker,settlement_date,publication_date,short_interest,float_shares,percent_float,average_daily_volume,days_to_cover,source,source_url,notes,as_of_date,effective_date,capture_method",
                    "AAPL,2026-05-31,2026-06-03,1000,10000,,250,,nasdaq_manual,https://example.com/aapl,fixture,,,provider_export",
                    "MSFT,2026-05-31,2026-06-03,1000,10000,0.1,250,4,nasdaq_manual,,missing url,,,provider_export",
                    "SPY,2026-05-31,2026-06-03,1000,10000,0.1,250,4,nasdaq_manual,https://example.com/spy,fixture,,,provider_export",
                )
            ),
            encoding="utf-8",
        )

        validation = validate_short_interest_backfill(config)
        self.assertEqual(validation.valid_row_count, 1)
        self.assertEqual(validation.invalid_row_count, 1)
        self.assertEqual(len(validation.etf_gated_rows), 1)
        self.assertEqual(validation.valid_tickers, ("AAPL",))
        self.assertFalse(validation.apply_ready)
        self.assertIn("missing required source_url", validation.invalid_rows[0].errors[0])
        validation_text = build_short_interest_backfill_validation_text(config)
        self.assertIn("Valid rows: 1", validation_text)
        self.assertIn("Invalid rows: 1", validation_text)

        blocked_import = import_short_interest_source_exports(config)
        self.assertEqual(blocked_import.imported_count, 0)
        self.assertIn("invalid_short_interest_backfill_rows", blocked_import.warnings)

        provider_export.write_text(
            "\n".join(
                (
                    "ticker,settlement_date,publication_date,short_interest,float_shares,percent_float,average_daily_volume,days_to_cover,source,source_url,notes,as_of_date,effective_date,capture_method",
                    "AAPL,2026-05-31,2026-06-03,1000,10000,,250,,nasdaq_manual,https://example.com/aapl,fixture,,,provider_export",
                    "MSFT,2026-05-31,2026-06-03,500,10000,5%,125,,nasdaq_manual,https://example.com/msft,fixture,,,provider_export",
                    "SPY,2026-05-31,2026-06-03,1000,10000,0.1,250,4,nasdaq_manual,https://example.com/spy,fixture,,,provider_export",
                )
            ),
            encoding="utf-8",
        )
        preview = build_short_interest_import_preview_text(config)
        self.assertIn("Projected source-backed coverage: 2/2", preview)
        result = import_short_interest_source_exports(config)
        self.assertEqual(result.imported_count, 2)
        self.assertEqual(result.written_count, 2)
        second_result = import_short_interest_source_exports(config)
        self.assertEqual(second_result.imported_count, 2)
        self.assertEqual(second_result.written_count, 2)

        loaded = load_short_interest_csv(config)
        self.assertEqual(loaded.loaded_count, 2)
        snapshots = list_short_interest_source_snapshots(database_path)
        self.assertEqual(len(snapshots), 2)
        by_ticker = {snapshot.ticker: snapshot for snapshot in snapshots}
        self.assertEqual(by_ticker["AAPL"].percent_float, 0.1)
        self.assertEqual(by_ticker["AAPL"].days_to_cover, 4.0)
        self.assertEqual(by_ticker["MSFT"].percent_float, 0.05)
        self.assertEqual(by_ticker["MSFT"].days_to_cover, 4.0)

        compute_result = compute_short_interest_signals(config)
        statuses = {item.ticker: item.status for item in compute_result.results}
        self.assertEqual(statuses["AAPL"], "computed")
        self.assertEqual(statuses["MSFT"], "computed")
        self.assertEqual(statuses["SPY"], "skipped")

    def test_missing_coverage_plan_diagnostics_and_template_focus_live_gap(self) -> None:
        database_path = fresh_database_path("phase10g_missing_coverage.sqlite")
        config = make_config(database_path)
        seed_expanded_assets(config)
        seed_current_short_interest_gap(config)

        plan = short_interest_missing_coverage_plan(config)
        self.assertEqual(plan.current_source_backed_count, 9)
        self.assertEqual(plan.active_equity_count, 13)
        self.assertEqual(plan.missing_tickers, ("CRM", "JPM", "LLY", "ORCL"))
        self.assertEqual(plan.etf_gated_tickers, ("QQQ", "SPY"))
        self.assertEqual(plan.valid_missing_tickers, ())
        self.assertEqual(plan.blocked_apply_reason, "no_valid_missing_short_interest_rows")
        self.assertEqual(
            {item.ticker: item.classification for item in plan.diagnostics},
            {
                "CRM": "provider_export_needed",
                "JPM": "provider_export_needed",
                "LLY": "provider_export_needed",
                "ORCL": "provider_export_needed",
            },
        )

        text = build_short_interest_missing_coverage_plan_text(config)
        self.assertIn("Missing source tickers: CRM, JPM, LLY, ORCL", text)
        self.assertIn("CRM | provider_export_needed", text)

        diagnostics = short_interest_provider_diagnostics(config, ticker="CRM")
        self.assertEqual(len(diagnostics), 1)
        self.assertEqual(diagnostics[0].ticker, "CRM")
        self.assertIn("finra:not_cached", diagnostics[0].attempted_paths)
        diagnostics_text = build_short_interest_provider_diagnostics_text(config, ticker="CRM")
        self.assertIn("CRM | equity | provider_export_needed", diagnostics_text)

        export_result = export_short_interest_missing_provider_template(config)
        self.assertEqual(export_result.missing_tickers, ("CRM", "JPM", "LLY", "ORCL"))
        template_text = export_result.backfill_path.read_text(encoding="utf-8")
        self.assertIn("CRM", template_text)
        self.assertNotIn("AAPL", template_text)
        self.assertNotIn("SPY", template_text)

    def test_missing_source_resolver_fetches_only_missing_tickers_and_updates_projection(self) -> None:
        database_path = fresh_database_path("phase10g_missing_resolve.sqlite")
        config = make_config(database_path)
        seed_expanded_assets(config)
        seed_current_short_interest_gap(config)
        crm_payload = {
            "data": [
                {
                    "symbolCode": "CRM",
                    "settlementDate": "2026-05-31",
                    "currentShortPositionQuantity": "2000",
                    "averageDailyVolumeQuantity": "500",
                    "daysToCoverQuantity": "4",
                }
            ]
        }

        with patch("target_opportunity_monitor.short_interest._http_json_request") as request:
            request.side_effect = [
                crm_payload,
                {"data": []},
                {"data": []},
                {"data": []},
            ]
            result = resolve_short_interest_missing_sources(
                config,
                provider="finra",
                use_cache=False,
            )

        self.assertEqual(result.requested_tickers, ("CRM", "JPM", "LLY", "ORCL"))
        self.assertEqual(request.call_count, 4)
        self.assertEqual(result.normalized_count, 1)
        self.assertEqual(result.valid_missing_tickers, ("CRM",))
        self.assertEqual(result.projected_source_backed_count, 10)
        self.assertIsNone(result.blocked_apply_reason)
        self.assertTrue(result.template_path.exists())
        provider_export_text = (
            short_interest_source_exports_dir(config) / "provider_export.csv"
        ).read_text(encoding="utf-8")
        self.assertIn("CRM", provider_export_text)
        self.assertNotIn("AAPL", provider_export_text)

        diagnostics = {item.ticker: item for item in result.diagnostics}
        self.assertEqual(diagnostics["CRM"].classification, "provider_export_needed")
        self.assertEqual(diagnostics["CRM"].valid_export_rows, 1)
        text = build_short_interest_missing_source_resolution_text(
            config,
            ticker="CRM",
            provider="finra",
            use_cache=True,
        )
        self.assertIn("Ticker filter: CRM", text)
        self.assertIn("Valid missing-row tickers: CRM", text)
        self.assertIn("Apply ready: True", text)

    def test_missing_provider_apply_requires_valid_missing_rows_and_is_idempotent(self) -> None:
        database_path = fresh_database_path("phase10g_missing_apply.sqlite")
        config = make_config(database_path)
        seed_expanded_assets(config)
        seed_current_short_interest_gap(config)

        dry_text, dry_result = build_short_interest_provider_backfill_apply_text(config)
        self.assertTrue(dry_result.dry_run)
        self.assertEqual(dry_result.blocked_apply_reason, "no_valid_missing_short_interest_rows")
        self.assertIn("Dry run only", dry_text)
        blocked = apply_short_interest_provider_backfill(config, confirm=True)
        self.assertEqual(blocked.imported_count, 0)
        self.assertEqual(blocked.blocked_apply_reason, "no_valid_missing_short_interest_rows")

        export_result = export_short_interest_missing_provider_template(config)
        provider_export = export_result.source_exports_dir / "provider_export.csv"
        provider_export.write_text(
            "\n".join(
                (
                    "ticker,settlement_date,publication_date,short_interest,float_shares,percent_float,average_daily_volume,days_to_cover,source,source_url,notes,as_of_date,effective_date,capture_method",
                    "CRM,2026-05-15,2026-05-20,2000,20000,,500,,provider_export,https://example.com/crm,fixture,,,provider_export",
                )
            ),
            encoding="utf-8",
        )
        ready_plan = short_interest_missing_coverage_plan(config)
        self.assertEqual(ready_plan.valid_missing_tickers, ("CRM",))
        self.assertIsNone(ready_plan.blocked_apply_reason)

        apply_result = apply_short_interest_provider_backfill(config, confirm=True)
        self.assertEqual(apply_result.imported_count, 1)
        self.assertEqual(apply_result.written_count, 10)
        second_apply = apply_short_interest_provider_backfill(config, confirm=True)
        self.assertEqual(second_apply.imported_count, 1)
        self.assertEqual(second_apply.written_count, 10)

        loaded = load_short_interest_csv(config)
        self.assertIn("CRM", loaded.tickers)
        source_report = short_interest_source_status_report(config)
        self.assertEqual(source_report.source_backed_ticker_count, 10)
        self.assertEqual(source_report.missing_source_tickers, ("JPM", "LLY", "ORCL"))

    def test_fetch_short_interest_sources_uses_cache_and_writes_provider_export(self) -> None:
        database_path = fresh_database_path("phase10g_provider_fetch.sqlite")
        config = make_config(database_path)
        seed_assets(config)
        payload = {
            "data": [
                {
                    "symbolCode": "AAPL",
                    "settlementDate": "2026-05-31",
                    "currentShortPositionQuantity": "1000",
                    "averageDailyVolumeQuantity": "250",
                    "daysToCoverQuantity": "4",
                    "issueName": "Apple Inc.",
                }
            ]
        }

        with patch("target_opportunity_monitor.short_interest._http_json_request") as request:
            request.return_value = payload
            result = fetch_short_interest_sources(
                config,
                provider="finra",
                ticker="AAPL",
                use_cache=False,
            )
            self.assertEqual(result.normalized_count, 1)
            self.assertEqual(result.written_count, 1)
            self.assertEqual(result.tickers, ("AAPL",))
            self.assertEqual(result.live_requests, 1)
            request.assert_called_once()

        export_text = result.output_path.read_text(encoding="utf-8")
        self.assertIn("AAPL", export_text)
        self.assertIn("finra_official", export_text)
        self.assertIn("https://www.finra.org/finra-data/browse-catalog/equity-short-interest/data", export_text)

        with patch("target_opportunity_monitor.short_interest._http_json_request") as request:
            request.side_effect = AssertionError("cache should be used")
            cached = fetch_short_interest_sources(
                config,
                provider="finra",
                ticker="AAPL",
                use_cache=True,
            )
            self.assertEqual(cached.cache_hits, 1)
            self.assertEqual(cached.normalized_count, 1)
            request.assert_not_called()

        provider_status = short_interest_provider_status(config)
        self.assertEqual(provider_status.provider_export_valid_row_count, 1)
        self.assertEqual(provider_status.provider_export_tickers, ("AAPL",))
        self.assertEqual(provider_status.cache_file_count, 1)
        status_text = build_short_interest_provider_status_text(config)
        self.assertIn("Provider export valid rows: 1", status_text)
        self.assertIn("Fetchable providers: finra, nasdaq_trader", status_text)

    def test_normalize_short_interest_provider_export_rejects_invalid_and_gates_etf(self) -> None:
        database_path = fresh_database_path("phase10g_provider_normalize.sqlite")
        config = make_config(database_path)
        seed_assets(config)
        raw_path = TEST_TMP_ROOT / "raw_short_interest_export.csv"
        raw_path.parent.mkdir(parents=True, exist_ok=True)
        raw_path.write_text(
            "\n".join(
                (
                    "ticker,settlement_date,publication_date,short_interest,float_shares,average_daily_volume,source_url",
                    "AAPL,2026-05-31,2026-06-03,1000,10000,250,https://example.com/aapl",
                    "MSFT,2026-05-31,2026-06-03,1000,10000,250,",
                    "SPY,2026-05-31,2026-06-03,1000,10000,250,https://example.com/spy",
                )
            ),
            encoding="utf-8",
        )

        result = normalize_short_interest_provider_export(
            config,
            provider="generic",
            file_path=raw_path,
        )
        self.assertEqual(result.source_row_count, 3)
        self.assertEqual(result.normalized_count, 1)
        self.assertEqual(result.skipped_count, 2)
        self.assertEqual(result.tickers, ("AAPL",))
        self.assertTrue(any("MSFT:missing_source_url" in warning for warning in result.warnings))
        self.assertTrue(any("SPY:etf_short_interest_gated" in warning for warning in result.warnings))

        provider_export = result.output_path.read_text(encoding="utf-8")
        self.assertIn("AAPL", provider_export)
        self.assertIn("provider_export", provider_export)
        self.assertNotIn("MSFT", provider_export)
        self.assertNotIn("SPY", provider_export)

    def test_status_report_markdown_csv_and_dashboard_include_short_interest(self) -> None:
        database_path = fresh_database_path("phase10g_outputs.sqlite")
        config = make_config(database_path)
        seed_assets(config)
        seed_price_context(config)
        config.short_interest_path.parent.mkdir(parents=True, exist_ok=True)
        config.short_interest_path.write_text(
            "\n".join(
                (
                    "ticker,settlement_date,publication_date,short_interest,float_shares,percent_float,average_daily_volume,days_to_cover,source,source_url,notes,as_of_date,effective_date",
                    "AAPL,2026-05-31,2026-06-03,900,10000,0.09,250,3.6,nasdaq_manual,https://example.com/aapl,fixture,,",
                )
            ),
            encoding="utf-8",
        )
        compute_short_interest_signals(config)
        validate_short_interest_signals(config, ticker="AAPL")

        source_report = short_interest_source_status_report(config)
        self.assertEqual(source_report.source_backed_ticker_count, 1)
        provider_status = short_interest_provider_status(config)
        self.assertEqual(provider_status.provider_export_valid_row_count, 0)
        statuses = short_interest_statuses(config)
        self.assertEqual({status.ticker for status in statuses}, {"AAPL", "MSFT", "SPY"})
        status_text = build_short_interest_status_text(config)
        self.assertIn("Source-backed coverage: 1/2", status_text)
        self.assertIn("SPY | etf | etf_gated", status_text)

        report_result = write_daily_report(config, run_date=date(2026, 6, 8))
        markdown = report_result.path.read_text(encoding="utf-8")
        csv_text = report_result.csv_path.read_text(encoding="utf-8")
        self.assertIn("Short interest source-backed coverage", markdown)
        self.assertIn("Short interest provider export valid rows", markdown)
        self.assertIn("Short interest provider warnings", markdown)
        self.assertIn("Short interest missing coverage tickers", markdown)
        self.assertIn("Short interest missing-coverage blocked apply reason", markdown)
        self.assertIn("short_interest_score", csv_text)
        self.assertIn("short_interest_provider_export_valid_rows", csv_text)
        self.assertIn("short_interest_provider_diagnostic_status", csv_text)
        self.assertIn("short_interest_missing_coverage_blocked_apply_reason", csv_text)
        self.assertIn("short_interest_shadow_mode", csv_text)

        dashboard_result = build_dashboard(config)
        html = dashboard_result.path.read_text(encoding="utf-8")
        self.assertIn("Short Interest Score", html)
        self.assertIn("Short Interest Backfill Valid", html)
        self.assertIn("Short Interest Provider Export", html)
        self.assertIn("Short Interest Diagnostics", html)
        match = re.search(
            r'<script id="tom-dashboard-data" type="application/json">(.*?)</script>',
            html,
        )
        self.assertIsNotNone(match)
        data = json.loads(match.group(1))
        self.assertIn("short_interest_source_status", data)
        self.assertIn("short_interest_backfill_status", data)
        self.assertIn("short_interest_provider_status", data)
        self.assertGreaterEqual(data["health"]["short_interest_source_rows"], 1)
        self.assertIn("short_interest_backfill_valid_rows", data["health"])
        self.assertIn("short_interest_provider_export_valid_rows", data["health"])
        self.assertIn("short_interest_provider_warnings", data["health"])
        self.assertIn("short_interest_provider_diagnostic_status", data["health"])
        self.assertIn("short_interest_missing_coverage_blocked_apply_reason", data["health"])


if __name__ == "__main__":
    unittest.main()
