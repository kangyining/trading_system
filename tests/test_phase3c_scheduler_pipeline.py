from __future__ import annotations

from argparse import Namespace
from contextlib import redirect_stdout
from datetime import date
from pathlib import Path
import io
import sys
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
TEST_TMP_ROOT = PROJECT_ROOT / ".tmp_tests"
sys.path.insert(0, str(SRC_PATH))

from target_opportunity_monitor.cli import (
    command_probe_market,
    command_verify_ticker,
    command_verify_universe,
)
from target_opportunity_monitor.config import AppConfig
from target_opportunity_monitor.db import REQUIRED_TABLES, initialize_database
from target_opportunity_monitor.ibkr_provider import check_ibkr_status
from target_opportunity_monitor.intraday import compute_intraday_gaps
from target_opportunity_monitor.readiness import verify_ticker, verify_universe
from target_opportunity_monitor.storage import (
    Asset,
    Estimate,
    Fundamental,
    PriceFeature,
    QuoteSnapshot,
    Target,
    count_rows_by_table,
    latest_intraday_gap_timestamp,
    latest_pipeline_run,
    latest_quote_timestamp,
    upsert_asset,
    upsert_estimate,
    upsert_fundamental,
    upsert_price_feature,
    upsert_quote_snapshot,
    upsert_target,
)


def make_config(database_path: Path) -> AppConfig:
    return AppConfig(
        project_root=TEST_TMP_ROOT,
        config_path=TEST_TMP_ROOT / "phase3c.toml",
        database_path=database_path,
        reports_dir=TEST_TMP_ROOT / "reports_phase3c",
        watchlist_path=TEST_TMP_ROOT / "watchlist_phase3c.csv",
        market_data_dir=TEST_TMP_ROOT / "market_data_phase3c",
        manual_prices_dir=TEST_TMP_ROOT / "market_data_phase3c" / "manual",
        market_data_primary_source="stooq",
        market_data_secondary_source="yahoo_chart",
        market_data_mode="csv",
        market_data_lookback_days=800,
        market_data_stale_after_days=7,
        market_data_minimum_history_days=252,
        universe_mode="manual_watchlist",
        run_mode="daily_scoring",
        report_title="Target Opportunity Monitor Daily Report",
        fundamentals_path=TEST_TMP_ROOT / "fundamentals_phase3c.csv",
        estimates_path=TEST_TMP_ROOT / "estimates_phase3c.csv",
        etf_navs_path=TEST_TMP_ROOT / "etf_navs_phase3c.csv",
        etf_holdings_path=TEST_TMP_ROOT / "etf_holdings_phase3c.csv",
        ibkr_paper_port=9,
        ibkr_timeout_seconds=1,
    )


def write_config(config: AppConfig) -> None:
    config.config_path.write_text(
        "\n".join(
            (
                "[paths]",
                f'database = "{config.database_path.as_posix()}"',
                f'reports = "{config.reports_dir.as_posix()}"',
                f'watchlist = "{config.watchlist_path.as_posix()}"',
                f'fundamentals = "{config.fundamentals_path.as_posix()}"',
                f'estimates = "{config.estimates_path.as_posix()}"',
                f'etf_navs = "{config.etf_navs_path.as_posix()}"',
                f'etf_holdings = "{config.etf_holdings_path.as_posix()}"',
                "",
                "[market_data]",
                'mode = "csv"',
                "stale_after_days = 7",
                "minimum_history_days = 252",
                "",
                "[ibkr]",
                f'host = "{config.ibkr_host}"',
                f"paper_port = {config.ibkr_paper_port}",
                f"timeout_seconds = {config.ibkr_timeout_seconds}",
                "",
                "[run]",
                'universe_mode = "manual_watchlist"',
                'run_mode = "daily_scoring"',
                "",
                "[reports]",
                f'title = "{config.report_title}"',
                "",
            )
        ),
        encoding="utf-8",
    )


def seed_equity_ready(database_path: Path) -> None:
    initialize_database(database_path)
    today = date.today().isoformat()
    upsert_asset(database_path, Asset(ticker="AAPL", asset_type="equity"))
    upsert_price_feature(
        database_path,
        PriceFeature(
            ticker="AAPL",
            feature_date=today,
            current_price=100,
            return_1d=0.01,
            return_1m=0.02,
            return_3m=0.03,
            return_6m=0.04,
            return_12m=0.05,
            realized_volatility_20d=0.2,
            realized_volatility_60d=0.25,
            average_dollar_volume_20d=1_000_000,
            latest_price_date=today,
        ),
    )
    upsert_fundamental(
        database_path,
        Fundamental(
            ticker="AAPL",
            fiscal_period_end="2026-06-01",
            fiscal_period="FY",
            report_type="annual",
            revenue=1000,
            net_income=100,
            shares_outstanding=100,
        ),
    )
    upsert_estimate(
        database_path,
        Estimate(
            ticker="AAPL",
            estimate_date=today,
            fiscal_period_end="2027-06-01",
            metric="eps",
            consensus_mean=2.0,
        ),
    )
    upsert_target(
        database_path,
        Target(
            ticker="AAPL",
            target_date=today,
            base_target=120,
            target_low=90,
            target_high=140,
            valuation_gap=0.2,
            target_method="test",
            uncertainty_band=0.25,
        ),
    )


def seed_etf_missing_nav(database_path: Path) -> None:
    today = date.today().isoformat()
    upsert_asset(database_path, Asset(ticker="SPY", asset_type="etf"))
    upsert_price_feature(
        database_path,
        PriceFeature(
            ticker="SPY",
            feature_date=today,
            current_price=500,
            return_1d=0.01,
            return_1m=0.02,
            return_3m=0.03,
            return_6m=0.04,
            return_12m=0.05,
            realized_volatility_20d=0.1,
            realized_volatility_60d=0.12,
            average_dollar_volume_20d=2_000_000,
            latest_price_date=today,
        ),
    )


class Phase3CSchedulerPipelineTests(unittest.TestCase):
    def setUp(self) -> None:
        TEST_TMP_ROOT.mkdir(exist_ok=True)

    def fresh_database_path(self, name: str) -> Path:
        path = TEST_TMP_ROOT / name
        if path.exists():
            path.unlink()
        return path

    def test_init_db_creates_phase3c_tables(self) -> None:
        database_path = self.fresh_database_path("phase3c_schema.sqlite")

        status = initialize_database(database_path)

        self.assertIn("quote_snapshots", status.existing_tables)
        self.assertIn("intraday_gap_snapshots", status.existing_tables)
        self.assertIn("pipeline_runs", status.existing_tables)
        self.assertIn("pipeline_step_results", status.existing_tables)
        self.assertEqual(status.existing_required_table_count, len(REQUIRED_TABLES))

    def test_quote_snapshot_and_intraday_gap_storage_are_idempotent(self) -> None:
        database_path = self.fresh_database_path("phase3c_storage.sqlite")
        config = make_config(database_path)
        seed_equity_ready(database_path)

        snapshot = QuoteSnapshot(
            ticker="AAPL",
            quote_timestamp="2026-06-06T10:00:00",
            last=110,
            market_data_type="delayed",
            source="ibkr",
        )
        upsert_quote_snapshot(database_path, snapshot)
        upsert_quote_snapshot(database_path, snapshot)
        result = compute_intraday_gaps(config, ticker="AAPL")

        self.assertEqual(count_rows_by_table(database_path, "quote_snapshots"), 1)
        self.assertEqual(count_rows_by_table(database_path, "intraday_gap_snapshots"), 1)
        self.assertEqual(result.updated_count, 1)
        self.assertEqual(latest_quote_timestamp(database_path), "2026-06-06T10:00:00")
        self.assertIsNotNone(latest_intraday_gap_timestamp(database_path))

    def test_verify_universe_marks_equity_ready_and_etf_missing_nav(self) -> None:
        database_path = self.fresh_database_path("phase3c_readiness.sqlite")
        config = make_config(database_path)
        seed_equity_ready(database_path)
        seed_etf_missing_nav(database_path)

        result = verify_universe(config)
        by_ticker = {status.ticker: status for status in result.statuses}

        self.assertTrue(by_ticker["AAPL"].phase4_ready)
        self.assertFalse(by_ticker["SPY"].phase4_ready)
        self.assertIn("missing_etf_nav", by_ticker["SPY"].warnings)

    def test_ibkr_status_handles_closed_gateway(self) -> None:
        database_path = self.fresh_database_path("phase3c_ibkr.sqlite")
        config = make_config(database_path)

        result = check_ibkr_status(config)

        self.assertFalse(result.connected)
        self.assertTrue(result.warnings)

    def test_probe_market_records_pipeline_even_when_ibkr_is_unavailable(self) -> None:
        database_path = self.fresh_database_path("phase3c_probe.sqlite")
        config = make_config(database_path)
        write_config(config)
        seed_equity_ready(database_path)

        with redirect_stdout(io.StringIO()):
            exit_code = command_probe_market(
                Namespace(config=config.config_path, source="ibkr", ticker="AAPL")
            )

        self.assertEqual(exit_code, 0)
        self.assertEqual(count_rows_by_table(database_path, "pipeline_runs"), 1)
        self.assertGreaterEqual(
            count_rows_by_table(database_path, "pipeline_step_results"),
            4,
        )
        self.assertIsNotNone(latest_pipeline_run(database_path))

    def test_verify_cli_outputs_readiness_rows(self) -> None:
        database_path = self.fresh_database_path("phase3c_cli.sqlite")
        config = make_config(database_path)
        write_config(config)
        seed_equity_ready(database_path)

        output = io.StringIO()
        with redirect_stdout(output):
            exit_code = command_verify_ticker(
                Namespace(config=config.config_path, ticker="AAPL", intraday=False)
            )

        self.assertEqual(exit_code, 0)
        self.assertIn("AAPL", output.getvalue())
        self.assertIn("Pre-Alert Ready", output.getvalue())

    def test_verify_ticker_reports_missing_asset_without_crashing(self) -> None:
        database_path = self.fresh_database_path("phase3c_missing_asset.sqlite")
        config = make_config(database_path)
        initialize_database(database_path)

        status = verify_ticker(config, "MISSING")

        self.assertFalse(status.phase4_ready)
        self.assertIn("missing_asset", status.warnings)


if __name__ == "__main__":
    unittest.main()
