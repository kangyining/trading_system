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

from support import sqlite_connection_for_test
from target_opportunity_monitor.cli import (
    command_compute_targets,
    command_status,
    command_valuation_status,
)
from target_opportunity_monitor.config import AppConfig
from target_opportunity_monitor.db import initialize_database
from target_opportunity_monitor.fundamental_data import (
    load_estimates_csv,
    load_fundamentals_csv,
    parse_estimates_csv,
    parse_fundamentals_csv,
)
from target_opportunity_monitor.reporting import write_daily_report
from target_opportunity_monitor.storage import (
    Asset,
    Estimate,
    Fundamental,
    PriceFeature,
    count_rows_by_table,
    latest_estimate,
    latest_fundamental,
    latest_target_date,
    list_estimates,
    list_fundamentals,
    list_targets,
    upsert_asset,
    upsert_estimate,
    upsert_fundamental,
    upsert_price_feature,
)
from target_opportunity_monitor.valuation import compute_ratios, compute_targets


def make_config(database_path: Path) -> AppConfig:
    return AppConfig(
        project_root=TEST_TMP_ROOT,
        config_path=TEST_TMP_ROOT / "phase3.toml",
        database_path=database_path,
        reports_dir=TEST_TMP_ROOT / "reports_phase3",
        watchlist_path=TEST_TMP_ROOT / "watchlist_phase3.csv",
        market_data_dir=TEST_TMP_ROOT / "market_data_phase3",
        manual_prices_dir=TEST_TMP_ROOT / "market_data_phase3" / "manual",
        market_data_primary_source="stooq",
        market_data_secondary_source="yahoo_chart",
        market_data_mode="auto",
        market_data_lookback_days=800,
        market_data_stale_after_days=7,
        market_data_minimum_history_days=252,
        universe_mode="manual_watchlist",
        run_mode="daily_scoring",
        report_title="Target Opportunity Monitor Daily Report",
        fundamentals_path=TEST_TMP_ROOT / "fundamentals.csv",
        estimates_path=TEST_TMP_ROOT / "estimates.csv",
        valuation_model_version="valuation_mvp_v1",
        valuation_default_uncertainty_band=0.25,
        valuation_minimum_methods=1,
        valuation_minimum_peer_count=2,
        valuation_stale_fundamentals_after_days=550,
        valuation_stale_estimates_after_days=120,
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
                "",
                "[valuation]",
                f'model_version = "{config.valuation_model_version}"',
                f"default_uncertainty_band = {config.valuation_default_uncertainty_band}",
                f"minimum_methods = {config.valuation_minimum_methods}",
                f"minimum_peer_count = {config.valuation_minimum_peer_count}",
                f"stale_fundamentals_after_days = {config.valuation_stale_fundamentals_after_days}",
                f"stale_estimates_after_days = {config.valuation_stale_estimates_after_days}",
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


class Phase3Tests(unittest.TestCase):
    def setUp(self) -> None:
        TEST_TMP_ROOT.mkdir(exist_ok=True)

    def fresh_database_path(self, name: str) -> Path:
        path = TEST_TMP_ROOT / name
        if path.exists():
            path.unlink()
        return path

    def seed_assets_prices_and_fundamentals(self, database_path: Path) -> AppConfig:
        config = make_config(database_path)
        initialize_database(database_path)
        for asset in (
            Asset(
                ticker="AAPL",
                asset_type="equity",
                sector="Information Technology",
                industry="Consumer Electronics",
            ),
            Asset(
                ticker="MSFT",
                asset_type="equity",
                sector="Information Technology",
                industry="Software",
            ),
            Asset(
                ticker="NVDA",
                asset_type="equity",
                sector="Information Technology",
                industry="Semiconductors",
            ),
            Asset(ticker="SPY", asset_type="etf", sector="ETF", industry="Broad Market"),
        ):
            upsert_asset(database_path, asset)

        for ticker, price in (("AAPL", 100.0), ("MSFT", 200.0), ("NVDA", 150.0), ("SPY", 500.0)):
            upsert_price_feature(
                database_path,
                PriceFeature(
                    ticker=ticker,
                    feature_date=date.today().isoformat(),
                    current_price=price,
                    return_1d=None,
                    return_1m=None,
                    return_3m=None,
                    return_6m=None,
                    return_12m=None,
                    realized_volatility_20d=None,
                    realized_volatility_60d=None,
                    average_dollar_volume_20d=None,
                    latest_price_date=date.today().isoformat(),
                ),
            )

        for period_end, eps, ebitda, fcf in (
            ("2024-03-31", 4.0, 80.0, 80.0),
            ("2025-03-31", 5.0, 90.0, 90.0),
            ("2026-03-31", 5.0, 100.0, 100.0),
        ):
            upsert_fundamental(
                database_path,
                Fundamental(
                    ticker="AAPL",
                    fiscal_period_end=period_end,
                    fiscal_period="FY",
                    report_type="annual",
                    currency="USD",
                    revenue=500.0,
                    ebitda=ebitda,
                    net_income=50.0,
                    diluted_eps=eps,
                    free_cash_flow=fcf,
                    cash_and_equivalents=50.0,
                    total_debt=100.0,
                    shares_outstanding=10.0,
                    diluted_shares=10.0,
                ),
            )

        for ticker, price, eps, forward_eps, ebitda, fcf in (
            ("MSFT", 200.0, 10.0, 12.0, 200.0, 200.0),
            ("NVDA", 150.0, 10.0, 10.0, 150.0, 150.0),
        ):
            upsert_fundamental(
                database_path,
                Fundamental(
                    ticker=ticker,
                    fiscal_period_end="2026-03-31",
                    fiscal_period="FY",
                    report_type="annual",
                    currency="USD",
                    revenue=1000.0,
                    ebitda=ebitda,
                    net_income=100.0,
                    diluted_eps=eps,
                    free_cash_flow=fcf,
                    cash_and_equivalents=0.0,
                    total_debt=0.0,
                    shares_outstanding=10.0,
                    diluted_shares=10.0,
                ),
            )
            upsert_estimate(
                database_path,
                Estimate(
                    ticker=ticker,
                    estimate_date=date.today().isoformat(),
                    fiscal_period_end="2027-03-31",
                    metric="eps",
                    consensus_mean=forward_eps,
                    analyst_count=10,
                ),
            )

        upsert_estimate(
            database_path,
            Estimate(
                ticker="AAPL",
                estimate_date=date.today().isoformat(),
                fiscal_period_end="2027-03-31",
                metric="eps",
                consensus_mean=6.0,
                analyst_count=20,
            ),
        )
        return config

    def test_csv_parsers_accept_valid_rows_and_reject_bad_inputs(self) -> None:
        fundamentals = parse_fundamentals_csv(
            "\n".join(
                (
                    "ticker,fiscal_period_end,fiscal_period,report_type,revenue,source",
                    "aapl,2026-03-31,FY,annual,100,manual",
                )
            )
        )
        estimates = parse_estimates_csv(
            "\n".join(
                (
                    "ticker,estimate_date,fiscal_period_end,metric,consensus_mean",
                    "aapl,2026-06-06,2027-03-31,eps,6.5",
                )
            )
        )

        self.assertEqual(fundamentals[0].ticker, "AAPL")
        self.assertEqual(fundamentals[0].revenue, 100.0)
        self.assertEqual(estimates[0].metric, "eps")
        self.assertEqual(estimates[0].consensus_mean, 6.5)

        with self.assertRaises(ValueError):
            parse_fundamentals_csv("ticker,revenue\nAAPL,not-a-number\n")
        with self.assertRaises(ValueError):
            parse_estimates_csv(
                "ticker,estimate_date,fiscal_period_end,metric,consensus_mean\n"
                "AAPL,bad-date,2027-03-31,eps,6\n"
            )

    def test_loaders_are_idempotent_and_latest_helpers_work(self) -> None:
        database_path = self.fresh_database_path("phase3_loaders.sqlite")
        initialize_database(database_path)
        fundamentals_path = TEST_TMP_ROOT / "phase3_fundamentals.csv"
        estimates_path = TEST_TMP_ROOT / "phase3_estimates.csv"
        fundamentals_path.write_text(
            "\n".join(
                (
                    "ticker,fiscal_period_end,fiscal_period,report_type,revenue,source",
                    "AAPL,2026-03-31,FY,annual,100,manual",
                )
            ),
            encoding="utf-8",
        )
        estimates_path.write_text(
            "\n".join(
                (
                    "ticker,estimate_date,fiscal_period_end,metric,consensus_mean,source",
                    "AAPL,2026-06-06,2027-03-31,eps,6,manual",
                )
            ),
            encoding="utf-8",
        )

        load_fundamentals_csv(database_path, fundamentals_path)
        load_fundamentals_csv(database_path, fundamentals_path)
        load_estimates_csv(database_path, estimates_path)
        load_estimates_csv(database_path, estimates_path)

        self.assertEqual(count_rows_by_table(database_path, "fundamentals"), 1)
        self.assertEqual(count_rows_by_table(database_path, "estimates"), 1)
        self.assertEqual(len(list_fundamentals(database_path, "AAPL")), 1)
        self.assertEqual(len(list_estimates(database_path, "AAPL")), 1)
        self.assertEqual(latest_fundamental(database_path, "AAPL").revenue, 100.0)
        self.assertEqual(latest_estimate(database_path, "AAPL", "eps").consensus_mean, 6.0)

    def test_ratio_and_target_calculation_are_deterministic(self) -> None:
        database_path = self.fresh_database_path("phase3_targets.sqlite")
        config = self.seed_assets_prices_and_fundamentals(database_path)

        result = compute_targets(config, ticker="AAPL")
        targets = list_targets(database_path, "AAPL")

        self.assertEqual(result.computed_count, 1)
        self.assertEqual(len(targets), 1)
        target = targets[0]
        self.assertEqual(target.method_count, 6)
        self.assertAlmostEqual(target.base_target or 0, 106.25, places=2)
        self.assertAlmostEqual(target.valuation_gap or 0, 0.0625, places=4)
        self.assertGreater(target.valuation_confidence or 0, 0)
        self.assertEqual(latest_target_date(database_path), date.today().isoformat())

    def test_compute_targets_flags_missing_data_and_missing_etf_nav(self) -> None:
        database_path = self.fresh_database_path("phase3_warnings.sqlite")
        config = self.seed_assets_prices_and_fundamentals(database_path)

        result = compute_targets(config)
        by_ticker = {item.ticker: item for item in result.results}

        self.assertEqual(by_ticker["SPY"].status, "skipped")
        self.assertIn("missing_etf_nav", by_ticker["SPY"].warnings)
        self.assertNotIn("unsupported_asset_type", by_ticker["SPY"].warnings)
        self.assertEqual(by_ticker["AAPL"].status, "computed")
        self.assertGreaterEqual(count_rows_by_table(database_path, "data_quality_checks"), 4)

    def test_compute_targets_ticker_option_only_recomputes_one_asset(self) -> None:
        database_path = self.fresh_database_path("phase3_ticker.sqlite")
        config = self.seed_assets_prices_and_fundamentals(database_path)

        result = compute_targets(config, ticker="AAPL")

        self.assertEqual([item.ticker for item in result.results], ["AAPL"])
        self.assertEqual(count_rows_by_table(database_path, "targets"), 1)

    def test_cli_status_and_valuation_status_include_phase3_fields(self) -> None:
        database_path = self.fresh_database_path("phase3_cli.sqlite")
        config = self.seed_assets_prices_and_fundamentals(database_path)
        write_config(config)

        output = io.StringIO()
        with redirect_stdout(output):
            command_compute_targets(Namespace(config=config.config_path, ticker="AAPL"))
            command_valuation_status(Namespace(config=config.config_path))
            command_status(Namespace(config=config.config_path))

        text = output.getvalue()
        self.assertIn("Target computation complete: computed=1", text)
        self.assertIn("Ticker | Current Price | Base Target", text)
        self.assertIn("AAPL | 100.0000", text)
        self.assertIn("Fundamental rows:", text)
        self.assertIn("Target rows: 1", text)

    def test_run_daily_includes_valuation_status(self) -> None:
        database_path = self.fresh_database_path("phase3_report.sqlite")
        config = self.seed_assets_prices_and_fundamentals(database_path)
        compute_targets(config, ticker="AAPL")

        result = write_daily_report(config, run_date=date.today())
        body = result.path.read_text(encoding="utf-8")

        self.assertIn("## Valuation Status", body)
        self.assertIn("Target coverage:", body)
        self.assertIn("AAPL", body)

    def test_init_db_adds_target_extension_columns(self) -> None:
        database_path = self.fresh_database_path("phase3_schema.sqlite")
        initialize_database(database_path)

        with sqlite_connection_for_test(database_path) as connection:
            columns = {
                row[1] for row in connection.execute("PRAGMA table_info(targets)")
            }

        self.assertIn("valuation_score", columns)
        self.assertIn("valuation_confidence", columns)
        self.assertIn("method_count", columns)
        self.assertIn("target_reason", columns)
        self.assertIn("data_warnings", columns)


if __name__ == "__main__":
    unittest.main()
