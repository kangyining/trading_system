from __future__ import annotations

from datetime import date
from pathlib import Path
import sys
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
TEST_TMP_ROOT = PROJECT_ROOT / ".tmp_tests"
sys.path.insert(0, str(SRC_PATH))

from target_opportunity_monitor.config import AppConfig, load_config
from target_opportunity_monitor.db import REQUIRED_TABLES, get_database_status, initialize_database
from target_opportunity_monitor.reporting import (
    latest_csv_report_path,
    latest_report_path,
    write_daily_report,
)


class Phase0Tests(unittest.TestCase):
    def setUp(self) -> None:
        TEST_TMP_ROOT.mkdir(exist_ok=True)

    def fresh_database_path(self, name: str) -> Path:
        path = TEST_TMP_ROOT / name
        if path.exists():
            path.unlink()
        return path

    def fresh_reports_dir(self, name: str) -> Path:
        path = TEST_TMP_ROOT / name
        path.mkdir(exist_ok=True)
        for report in path.glob("*-daily-report.md"):
            report.unlink()
        for report in path.glob("*-daily-report.csv"):
            report.unlink()
        return path

    def test_config_loads_expected_defaults(self) -> None:
        config = load_config()

        self.assertEqual(config.project_root, PROJECT_ROOT)
        self.assertEqual(config.database_path, PROJECT_ROOT / "data" / "tom.sqlite")
        self.assertEqual(config.reports_dir, PROJECT_ROOT / "reports")
        self.assertEqual(config.watchlist_path, PROJECT_ROOT / "configs" / "watchlist.csv")
        self.assertEqual(config.market_data_dir, PROJECT_ROOT / "data" / "market_data")
        self.assertEqual(config.manual_prices_dir, PROJECT_ROOT / "data" / "market_data" / "manual")
        self.assertEqual(config.market_data_primary_source, "stooq")
        self.assertEqual(config.market_data_secondary_source, "yahoo_chart")
        self.assertEqual(config.market_data_mode, "auto")
        self.assertEqual(config.market_data_lookback_days, 800)
        self.assertEqual(config.market_data_stale_after_days, 7)
        self.assertEqual(config.market_data_minimum_history_days, 252)
        self.assertEqual(config.etf_navs_path, PROJECT_ROOT / "data" / "etf" / "manual" / "etf_navs.csv")
        self.assertEqual(
            config.etf_holdings_path,
            PROJECT_ROOT / "data" / "etf" / "manual" / "etf_holdings.csv",
        )
        self.assertEqual(config.etf_model_version, "etf_nav_mvp_v1")
        self.assertEqual(config.etf_default_premium_discount_band, 0.005)
        self.assertEqual(config.etf_stale_nav_after_days, 7)
        self.assertEqual(config.etf_stale_holdings_after_days, 14)
        self.assertEqual(config.etf_minimum_holdings, 10)
        self.assertEqual(config.etf_premium_discount_history_days, 60)
        self.assertEqual(config.alerts_etf_model_version, "etf_alert_mvp_v1")
        self.assertEqual(config.alerts_etf_threshold_set, "etf_liquid_index")
        self.assertEqual(config.alerts_etf_watch_nav_discount_gap, 0.001)
        self.assertEqual(config.alerts_etf_action_nav_discount_gap, 0.005)
        self.assertEqual(config.alerts_etf_premium_warning_gap, -0.005)
        self.assertEqual(config.alerts_etf_minimum_opportunity_score, 65)
        self.assertEqual(config.alerts_etf_minimum_liquidity_score, 70)
        self.assertEqual(config.alerts_etf_minimum_risk_score, 50)
        self.assertEqual(config.alerts_etf_minimum_data_quality_score, 75)
        self.assertEqual(config.universe_mode, "manual_watchlist")
        self.assertEqual(config.run_mode, "daily_scoring")

    def test_config_loads_utf8_bom_files(self) -> None:
        config_path = TEST_TMP_ROOT / "bom_config.toml"
        config_path.write_text(
            "\ufeff"
            + "\n".join(
                (
                    "[paths]",
                    'database = "data/bom.sqlite"',
                    'reports = "reports"',
                    'watchlist = "configs/watchlist.csv"',
                    "",
                    "[run]",
                    'universe_mode = "manual_watchlist"',
                    'run_mode = "daily_scoring"',
                    "",
                    "[reports]",
                    'title = "BOM Report"',
                    "",
                )
            ),
            encoding="utf-8",
        )

        config = load_config(config_path)

        self.assertEqual(config.database_path, PROJECT_ROOT / "data" / "bom.sqlite")
        self.assertEqual(config.report_title, "BOM Report")

    def test_database_initialization_creates_required_tables(self) -> None:
        database_path = self.fresh_database_path("creates_required_tables.sqlite")

        status = initialize_database(database_path)

        self.assertTrue(status.exists)
        self.assertEqual(status.existing_required_table_count, len(REQUIRED_TABLES))
        self.assertEqual(set(REQUIRED_TABLES), set(status.existing_tables))

    def test_database_initialization_is_idempotent(self) -> None:
        database_path = self.fresh_database_path("idempotent.sqlite")

        first_status = initialize_database(database_path)
        second_status = initialize_database(database_path)

        self.assertEqual(
            first_status.existing_required_table_count,
            second_status.existing_required_table_count,
        )
        self.assertEqual(first_status.existing_tables, second_status.existing_tables)

    def test_status_before_and_after_database_initialization(self) -> None:
        database_path = self.fresh_database_path("status.sqlite")

        before = get_database_status(database_path)
        initialize_database(database_path)
        after = get_database_status(database_path)

        self.assertFalse(before.exists)
        self.assertEqual(before.existing_required_table_count, 0)
        self.assertTrue(after.exists)
        self.assertEqual(after.existing_required_table_count, len(REQUIRED_TABLES))

    def test_run_daily_writes_report_with_today_date(self) -> None:
        database_path = self.fresh_database_path("report.sqlite")
        reports_dir = self.fresh_reports_dir("reports")
        initialize_database(database_path)
        config = AppConfig(
            project_root=TEST_TMP_ROOT,
            config_path=TEST_TMP_ROOT / "default.toml",
            database_path=database_path,
            reports_dir=reports_dir,
            watchlist_path=TEST_TMP_ROOT / "watchlist.csv",
            market_data_dir=TEST_TMP_ROOT / "market_data",
            manual_prices_dir=TEST_TMP_ROOT / "market_data" / "manual",
            market_data_primary_source="stooq",
            market_data_secondary_source="yahoo_chart",
            market_data_mode="auto",
            market_data_lookback_days=800,
            market_data_stale_after_days=7,
            market_data_minimum_history_days=252,
            universe_mode="manual_watchlist",
            run_mode="daily_scoring",
            report_title="Target Opportunity Monitor Daily Report",
        )
        run_date = date.today()

        result = write_daily_report(config, run_date=run_date)

        self.assertTrue(result.path.exists())
        self.assertTrue(result.csv_path is not None and result.csv_path.exists())
        self.assertEqual(result.path.name, f"{run_date.isoformat()}-daily-report.md")
        self.assertEqual(result.csv_path.name, f"{run_date.isoformat()}-daily-report.csv")
        self.assertEqual(latest_report_path(reports_dir), result.path)
        self.assertEqual(latest_csv_report_path(reports_dir), result.csv_path)
        report_body = result.path.read_text(encoding="utf-8")
        self.assertIn("## Data Status", report_body)
        self.assertIn("## Alert Summary", report_body)
        self.assertIn("## Watchlist Status", report_body)
        self.assertIn("## Next Steps", report_body)


if __name__ == "__main__":
    unittest.main()
