from __future__ import annotations

from pathlib import Path
import shutil
import sys
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
TEST_TMP_ROOT = PROJECT_ROOT / ".tmp_tests" / "phase10g_short_interest_backfill"
sys.path.insert(0, str(SRC_PATH))

from target_opportunity_monitor.config import AppConfig
from target_opportunity_monitor.db import initialize_database
from target_opportunity_monitor.short_interest import (
    apply_short_interest_provider_backfill,
    export_short_interest_missing_provider_template,
    load_short_interest_csv,
    short_interest_missing_coverage_plan,
    short_interest_source_status_report,
)
from target_opportunity_monitor.storage import Asset, upsert_asset


SOURCE_EXPORT_HEADER = (
    "ticker,settlement_date,publication_date,short_interest,float_shares,"
    "percent_float,average_daily_volume,days_to_cover,source,source_url,"
    "notes,as_of_date,effective_date,capture_method"
)


def fresh_database_path(name: str) -> Path:
    TEST_TMP_ROOT.mkdir(parents=True, exist_ok=True)
    path = TEST_TMP_ROOT / name
    if path.exists():
        path.unlink()
    return path


def make_config(database_path: Path) -> AppConfig:
    return AppConfig(
        project_root=TEST_TMP_ROOT,
        config_path=TEST_TMP_ROOT / f"{database_path.stem}.toml",
        database_path=database_path,
        reports_dir=TEST_TMP_ROOT / "reports",
        watchlist_path=TEST_TMP_ROOT / "watchlist.csv",
        market_data_dir=TEST_TMP_ROOT / "market_data",
        manual_prices_dir=TEST_TMP_ROOT / "market_data" / "manual",
        market_data_primary_source="manual",
        market_data_secondary_source="manual",
        market_data_mode="manual",
        market_data_lookback_days=30,
        market_data_stale_after_days=7,
        market_data_minimum_history_days=5,
        universe_mode="manual_watchlist",
        run_mode="test",
        report_title="Test",
        short_interest_path=TEST_TMP_ROOT / "signals" / "manual" / f"{database_path.stem}.csv",
        short_interest_cache_dir=TEST_TMP_ROOT / "signals" / "cache" / database_path.stem,
        signals_short_interest_provider_retry_delay_seconds=0.0,
    )


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
    upsert_asset(config.database_path, Asset(ticker="QQQ", asset_type="etf"))
    upsert_asset(config.database_path, Asset(ticker="SPY", asset_type="etf"))


def seed_current_short_interest_gap(config: AppConfig) -> None:
    covered = ("AAPL", "AMD", "AMZN", "AVGO", "COST", "GOOGL", "META", "MSFT", "NVDA")
    config.short_interest_path.parent.mkdir(parents=True, exist_ok=True)
    rows = [
        "ticker,settlement_date,publication_date,short_interest,float_shares,"
        "percent_float,average_daily_volume,days_to_cover,source,source_url,"
        "notes,as_of_date,effective_date"
    ]
    for ticker in covered:
        rows.append(
            f"{ticker},2026-05-15,2026-05-20,1000,10000,0.10,250,4,"
            f"fixture_source,https://example.com/{ticker.lower()},fixture,,"
        )
    config.short_interest_path.write_text("\n".join(rows), encoding="utf-8")
    load_short_interest_csv(config)


class Phase10GShortInterestBackfillIntakeTests(unittest.TestCase):
    def tearDown(self) -> None:
        if TEST_TMP_ROOT.exists():
            shutil.rmtree(TEST_TMP_ROOT)

    def _seed_gap_config(self, name: str) -> AppConfig:
        config = make_config(fresh_database_path(f"{name}.sqlite"))
        seed_expanded_assets(config)
        seed_current_short_interest_gap(config)
        return config

    def test_blank_missing_provider_template_keeps_apply_blocked(self) -> None:
        config = self._seed_gap_config("blank_template")

        export_result = export_short_interest_missing_provider_template(config)
        plan = short_interest_missing_coverage_plan(config)

        self.assertEqual(export_result.missing_tickers, ("CRM", "JPM", "LLY", "ORCL"))
        self.assertEqual(plan.current_source_backed_count, 9)
        self.assertEqual(plan.projected_source_backed_count, 9)
        self.assertEqual(plan.valid_missing_tickers, ())
        self.assertEqual(plan.blocked_apply_reason, "no_valid_missing_short_interest_rows")

        blocked = apply_short_interest_provider_backfill(config, confirm=True)
        self.assertEqual(blocked.imported_count, 0)
        self.assertEqual(blocked.blocked_apply_reason, "no_valid_missing_short_interest_rows")

    def test_valid_missing_provider_row_changes_projection_without_importing(self) -> None:
        config = self._seed_gap_config("valid_missing_row")
        export_result = export_short_interest_missing_provider_template(config)
        export_result.backfill_path.write_text(
            "\n".join(
                (
                    SOURCE_EXPORT_HEADER,
                    "CRM,2026-05-31,2026-06-03,2000,20000,,500,,"
                    "provider_export,https://example.com/crm,fixture,,,provider_export",
                )
            ),
            encoding="utf-8",
        )

        ready_plan = short_interest_missing_coverage_plan(config)
        self.assertEqual(ready_plan.valid_missing_tickers, ("CRM",))
        self.assertEqual(ready_plan.projected_source_backed_count, 10)
        self.assertIsNone(ready_plan.blocked_apply_reason)
        self.assertNotIn("CRM,2026-05-31", config.short_interest_path.read_text(encoding="utf-8"))

        dry_run = apply_short_interest_provider_backfill(config, confirm=False)
        self.assertEqual(dry_run.imported_count, 0)
        self.assertIn("dry_run_only", dry_run.warnings)
        self.assertNotIn("CRM,2026-05-31", config.short_interest_path.read_text(encoding="utf-8"))

        confirmed = apply_short_interest_provider_backfill(config, confirm=True)
        self.assertEqual(confirmed.imported_count, 1)
        self.assertIn("CRM,2026-05-31", config.short_interest_path.read_text(encoding="utf-8"))

        still_loaded_report = short_interest_source_status_report(config)
        self.assertEqual(still_loaded_report.source_backed_ticker_count, 9)
        loaded = load_short_interest_csv(config)
        self.assertIn("CRM", loaded.tickers)
        refreshed_report = short_interest_source_status_report(config)
        self.assertEqual(refreshed_report.source_backed_ticker_count, 10)

    def test_invalid_missing_provider_row_blocks_apply_with_diagnostics(self) -> None:
        config = self._seed_gap_config("invalid_missing_row")
        export_result = export_short_interest_missing_provider_template(config)
        export_result.backfill_path.write_text(
            "\n".join(
                (
                    SOURCE_EXPORT_HEADER,
                    "CRM,2026-05-31,2026-06-03,2000,20000,,500,,"
                    "provider_export,,missing url,,,provider_export",
                )
            ),
            encoding="utf-8",
        )

        plan = short_interest_missing_coverage_plan(config)
        diagnostics = {item.ticker: item for item in plan.diagnostics}

        self.assertEqual(plan.valid_missing_tickers, ())
        self.assertEqual(plan.blocked_apply_reason, "invalid_short_interest_backfill_rows")
        self.assertEqual(diagnostics["CRM"].classification, "malformed_source_row")
        self.assertEqual(diagnostics["CRM"].invalid_export_rows, 1)

        blocked = apply_short_interest_provider_backfill(config, confirm=True)
        self.assertEqual(blocked.imported_count, 0)
        self.assertIn("invalid_short_interest_backfill_rows", blocked.warnings)


if __name__ == "__main__":
    unittest.main()
