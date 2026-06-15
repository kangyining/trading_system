from __future__ import annotations

from argparse import Namespace
from contextlib import redirect_stdout
from datetime import date
from pathlib import Path
import csv
import io
import sys
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
TEST_TMP_ROOT = PROJECT_ROOT / ".tmp_tests"
sys.path.insert(0, str(SRC_PATH))

from target_opportunity_monitor.alerts import compute_alerts
from target_opportunity_monitor.cli import command_run_daily, command_status
from target_opportunity_monitor.config import AppConfig
from target_opportunity_monitor.db import initialize_database
from target_opportunity_monitor.reporting import REPORT_CSV_COLUMNS, write_daily_report
from target_opportunity_monitor.storage import (
    Asset,
    EtfFeature,
    PriceFeature,
    Score,
    Target,
    upsert_asset,
    upsert_etf_feature,
    upsert_price_feature,
    upsert_score,
    upsert_target,
)


def make_config(database_path: Path) -> AppConfig:
    return AppConfig(
        project_root=TEST_TMP_ROOT,
        config_path=TEST_TMP_ROOT / "phase6a.toml",
        database_path=database_path,
        reports_dir=TEST_TMP_ROOT / "reports_phase6a",
        watchlist_path=TEST_TMP_ROOT / "watchlist_phase6a.csv",
        market_data_dir=TEST_TMP_ROOT / "market_data_phase6a",
        manual_prices_dir=TEST_TMP_ROOT / "market_data_phase6a" / "manual",
        market_data_primary_source="stooq",
        market_data_secondary_source="yahoo_chart",
        market_data_mode="csv",
        market_data_lookback_days=800,
        market_data_stale_after_days=7,
        market_data_minimum_history_days=252,
        universe_mode="manual_watchlist",
        run_mode="daily_scoring",
        report_title="Target Opportunity Monitor Daily Report",
        alerts_equity_model_version="equity_alert_mvp_v1",
        alerts_equity_threshold_set="equity_default",
    )


def write_config(config: AppConfig) -> None:
    config.config_path.write_text(
        "\n".join(
            (
                "[paths]",
                f'database = "{config.database_path.as_posix()}"',
                f'reports = "{config.reports_dir.as_posix()}"',
                f'watchlist = "{config.watchlist_path.as_posix()}"',
                "",
                "[run]",
                'universe_mode = "manual_watchlist"',
                'run_mode = "daily_scoring"',
                "",
                "[reports]",
                f'title = "{config.report_title}"',
                "",
                "[alerts]",
                'equity_model_version = "equity_alert_mvp_v1"',
                'equity_threshold_set = "equity_default"',
                "minimum_bullish_valuation_gap = 0.10",
                "minimum_expected_value_score = 70",
                "minimum_confidence_score = 60",
                "minimum_liquidity_score = 60",
                "minimum_risk_score = 40",
                "minimum_data_quality_score = 75",
                "watch_gap_threshold = 0.15",
                "watch_opportunity_score = 65",
                "bearish_overvaluation_gap = -0.10",
                "risk_warning_score_below = 35",
                "",
            )
        ),
        encoding="utf-8",
    )


def seed_equity(
    database_path: Path,
    ticker: str,
    current_price: float,
    target_low: float,
    base_target: float,
    target_high: float,
    valuation_gap: float,
    opportunity_score: float,
    expected_value_score: float,
    confidence_score: float = 80,
    liquidity_score: float = 90,
    risk_score: float = 60,
) -> None:
    today = date.today().isoformat()
    upsert_asset(database_path, Asset(ticker=ticker, asset_type="equity"))
    upsert_price_feature(
        database_path,
        PriceFeature(
            ticker=ticker,
            feature_date=today,
            current_price=current_price,
            return_1d=0.01,
            return_1m=0.05,
            return_3m=0.10,
            return_6m=0.15,
            return_12m=0.20,
            realized_volatility_20d=0.20,
            realized_volatility_60d=0.25,
            average_dollar_volume_20d=1_000_000_000,
            latest_price_date=today,
        ),
    )
    upsert_target(
        database_path,
        Target(
            ticker=ticker,
            target_date=today,
            base_target=base_target,
            target_low=target_low,
            target_high=target_high,
            valuation_gap=valuation_gap,
            target_method="fixture",
            uncertainty_band=0.25,
            valuation_confidence=75,
            method_count=6,
            model_version="valuation_mvp_v1",
        ),
    )
    upsert_score(
        database_path,
        Score(
            ticker=ticker,
            score_date=today,
            valuation_gap_score=75,
            momentum_score=55,
            risk_score=risk_score,
            liquidity_score=liquidity_score,
            confidence_score=confidence_score,
            timing_score=65,
            expected_value_score=expected_value_score,
            opportunity_score=opportunity_score,
            asset_type="equity",
            score_model="equity_score_mvp_v1",
            threshold_set="equity_default",
            data_warnings="missing_revision_data",
            model_version="equity_score_mvp_v1",
            source="scoring",
        ),
    )


def seed_etf(database_path: Path, ticker: str) -> None:
    today = date.today().isoformat()
    upsert_asset(database_path, Asset(ticker=ticker, asset_type="etf"))
    upsert_price_feature(
        database_path,
        PriceFeature(
            ticker=ticker,
            feature_date=today,
            current_price=500,
            return_1d=None,
            return_1m=None,
            return_3m=None,
            return_6m=None,
            return_12m=None,
            realized_volatility_20d=None,
            realized_volatility_60d=None,
            average_dollar_volume_20d=2_000_000_000,
            latest_price_date=today,
        ),
    )
    upsert_etf_feature(
        database_path,
        EtfFeature(
            ticker=ticker,
            feature_date=today,
            nav_per_share=500,
            market_price=500,
            premium_discount=0,
            premium_discount_average_60d=0,
            premium_discount_volatility_60d=0.01,
            premium_discount_zscore=0,
            holdings_count=10,
            top_10_weight=0.30,
            largest_holding_weight=0.08,
            equity_weight=0.99,
            cash_weight=0.01,
            latest_nav_date=today,
            latest_holdings_date=today,
        ),
    )
    upsert_target(
        database_path,
        Target(
            ticker=ticker,
            target_date=today,
            base_target=500,
            target_low=497.5,
            target_high=502.5,
            valuation_gap=0,
            target_method="etf_nav",
            uncertainty_band=0.005,
            valuation_confidence=75,
            method_count=1,
            model_version="etf_nav_mvp_v1",
            source="etf_valuation",
        ),
    )
    upsert_score(
        database_path,
        Score(
            ticker=ticker,
            score_date=today,
            valuation_gap_score=50,
            quality_score=65,
            revision_score=50,
            momentum_score=50,
            risk_score=70,
            liquidity_score=90,
            confidence_score=80,
            timing_score=50,
            expected_value_score=60,
            opportunity_score=64,
            asset_type="etf",
            score_model="etf_score_mvp_v1",
            threshold_set="etf_liquid_index",
            model_version="etf_score_mvp_v1",
            source="scoring",
        ),
    )


def seed_reporting_fixture(database_path: Path, config: AppConfig) -> None:
    initialize_database(database_path)
    seed_equity(
        database_path,
        ticker="AAPL",
        current_price=110,
        target_low=80,
        base_target=112,
        target_high=140,
        valuation_gap=0.018,
        opportunity_score=68,
        expected_value_score=66,
    )
    seed_equity(
        database_path,
        ticker="MSFT",
        current_price=90,
        target_low=95,
        base_target=120,
        target_high=150,
        valuation_gap=0.25,
        opportunity_score=75,
        expected_value_score=78,
    )
    seed_equity(
        database_path,
        ticker="NVDA",
        current_price=100,
        target_low=80,
        base_target=135,
        target_high=170,
        valuation_gap=0.35,
        opportunity_score=70,
        expected_value_score=68,
    )
    for ticker in ("QQQ", "SPY"):
        seed_etf(database_path, ticker)
    compute_alerts(config)


class Phase6AReportingTests(unittest.TestCase):
    def setUp(self) -> None:
        TEST_TMP_ROOT.mkdir(exist_ok=True)

    def fresh_database_path(self, name: str) -> Path:
        path = TEST_TMP_ROOT / name
        if path.exists():
            path.unlink()
        return path

    def test_run_daily_writes_markdown_and_csv_reports(self) -> None:
        database_path = self.fresh_database_path("phase6a_reports.sqlite")
        config = make_config(database_path)
        seed_reporting_fixture(database_path, config)

        result = write_daily_report(config, run_date=date.today())

        self.assertTrue(result.path.exists())
        self.assertTrue(result.csv_path is not None and result.csv_path.exists())
        self.assertEqual(result.path.suffix, ".md")
        self.assertEqual(result.csv_path.suffix, ".csv")

    def test_csv_contains_active_tickers_and_phase6a_columns(self) -> None:
        database_path = self.fresh_database_path("phase6a_csv.sqlite")
        config = make_config(database_path)
        seed_reporting_fixture(database_path, config)

        result = write_daily_report(config, run_date=date.today())
        with result.csv_path.open(newline="", encoding="utf-8") as csv_file:
            rows = list(csv.DictReader(csv_file))

        self.assertEqual(set(rows[0].keys()), set(REPORT_CSV_COLUMNS))
        by_ticker = {row["ticker"]: row for row in rows}
        self.assertEqual(set(by_ticker), {"AAPL", "MSFT", "NVDA", "QQQ", "SPY"})
        self.assertEqual(by_ticker["MSFT"]["alert_type"], "bullish_divergence")
        self.assertEqual(by_ticker["NVDA"]["alert_type"], "watch_only_gap")
        self.assertEqual(by_ticker["QQQ"]["alert_type"], "no_alert")
        self.assertEqual(by_ticker["SPY"]["alert_type"], "no_alert")
        self.assertNotIn("etf_alerts_gated", by_ticker["SPY"]["model_warnings"])
        self.assertIn("price:", by_ticker["AAPL"]["data_freshness"])
        self.assertIn("intraday_market_session", rows[0])
        self.assertIn("intraday_regular_market_hours", rows[0])
        self.assertIn("intraday_health_notes", rows[0])

    def test_markdown_has_executive_and_ticker_level_detail(self) -> None:
        database_path = self.fresh_database_path("phase6a_markdown.sqlite")
        config = make_config(database_path)
        seed_reporting_fixture(database_path, config)

        result = write_daily_report(config, run_date=date.today())
        body = result.path.read_text(encoding="utf-8")

        self.assertIn("## Executive Alert Summary", body)
        self.assertIn("## Equity Alert Details", body)
        self.assertIn("### AAPL", body)
        self.assertIn("### MSFT", body)
        self.assertIn("### NVDA", body)
        self.assertIn("bullish_divergence", body)
        self.assertIn("watch_only_gap", body)
        self.assertIn("Invalidation", body)
        self.assertIn("Data freshness", body)
        self.assertIn("## CSV Report Fields", body)
        self.assertIn("Intraday market session", body)
        self.assertIn("Intraday health notes", body)
        self.assertNotIn("Expected future columns", body)
        self.assertIn("News/catalyst signal coverage", body)
        self.assertIn("Phase 10D", body)
        self.assertIn("Revision evidence decision", body)
        self.assertIn("analyst revision signals in shadow mode", body)
        self.assertNotIn("prepare Phase 4", body)
        self.assertNotIn("portfolio review categories are useful", body)

    def test_status_reports_latest_markdown_and_csv_report_paths(self) -> None:
        database_path = self.fresh_database_path("phase6a_status.sqlite")
        config = make_config(database_path)
        write_config(config)
        seed_reporting_fixture(database_path, config)

        run_output = io.StringIO()
        with redirect_stdout(run_output):
            run_exit = command_run_daily(Namespace(config=config.config_path))
        status_output = io.StringIO()
        with redirect_stdout(status_output):
            status_exit = command_status(Namespace(config=config.config_path))

        self.assertEqual(run_exit, 0)
        self.assertEqual(status_exit, 0)
        self.assertIn("Daily CSV report written", run_output.getvalue())
        self.assertIn("Latest report:", status_output.getvalue())
        self.assertIn("Latest CSV report:", status_output.getvalue())
        self.assertIn("-daily-report.csv", status_output.getvalue())


if __name__ == "__main__":
    unittest.main()
