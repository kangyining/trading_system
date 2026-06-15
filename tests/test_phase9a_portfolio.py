from __future__ import annotations

from argparse import Namespace
from contextlib import redirect_stdout
from datetime import date
from pathlib import Path
import csv
import io
import json
import re
import sys
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
TEST_TMP_ROOT = PROJECT_ROOT / ".tmp_tests"
sys.path.insert(0, str(SRC_PATH))

from support import patch_refresh_pipeline_for_test
from target_opportunity_monitor.cli import (
    command_compute_portfolio_context,
    command_load_portfolio,
    command_portfolio_status,
    command_status,
)
from target_opportunity_monitor.config import AppConfig, load_config
from target_opportunity_monitor.dashboard import build_dashboard
from target_opportunity_monitor.db import REQUIRED_TABLES, get_database_status, initialize_database
from target_opportunity_monitor.pipeline import run_refresh_data
from target_opportunity_monitor.portfolio import (
    compute_portfolio_context,
    ensure_portfolio_csv_headers,
    load_portfolio_csvs,
    parse_portfolio_cash_csv,
    parse_portfolio_positions_csv,
)
from target_opportunity_monitor.reporting import write_daily_report
from target_opportunity_monitor.storage import (
    Alert,
    Asset,
    PriceFeature,
    Score,
    count_rows_by_table,
    list_portfolio_reviews,
    portfolio_statuses,
    upsert_alert,
    upsert_asset,
    upsert_price_feature,
    upsert_score,
)


def make_config(database_path: Path) -> AppConfig:
    return AppConfig(
        project_root=TEST_TMP_ROOT,
        config_path=TEST_TMP_ROOT / "phase9a.toml",
        database_path=database_path,
        reports_dir=TEST_TMP_ROOT / "reports_phase9a",
        watchlist_path=TEST_TMP_ROOT / "watchlist_phase9a.csv",
        market_data_dir=TEST_TMP_ROOT / "market_data_phase9a",
        manual_prices_dir=TEST_TMP_ROOT / "market_data_phase9a" / "manual",
        market_data_primary_source="stooq",
        market_data_secondary_source="yahoo_chart",
        market_data_mode="csv",
        market_data_lookback_days=800,
        market_data_stale_after_days=7,
        market_data_minimum_history_days=252,
        universe_mode="manual_watchlist",
        run_mode="daily_scoring",
        report_title="Target Opportunity Monitor Daily Report",
        portfolio_positions_path=TEST_TMP_ROOT / "portfolio" / "positions.csv",
        portfolio_cash_path=TEST_TMP_ROOT / "portfolio" / "cash.csv",
    )


def write_config(config: AppConfig) -> None:
    config.config_path.write_text(
        "\n".join(
            (
                "[paths]",
                f'database = "{config.database_path.as_posix()}"',
                f'reports = "{config.reports_dir.as_posix()}"',
                f'watchlist = "{config.watchlist_path.as_posix()}"',
                f'portfolio_positions = "{config.portfolio_positions_path.as_posix()}"',
                f'portfolio_cash = "{config.portfolio_cash_path.as_posix()}"',
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


def fresh_database_path(name: str) -> Path:
    TEST_TMP_ROOT.mkdir(exist_ok=True)
    path = TEST_TMP_ROOT / name
    if path.exists():
        path.unlink()
    return path


def seed_asset(database_path: Path, ticker: str, sector: str = "Technology") -> None:
    upsert_asset(
        database_path,
        Asset(ticker=ticker, name=ticker, asset_type="equity", sector=sector),
    )
    upsert_price_feature(
        database_path,
        PriceFeature(
            ticker=ticker,
            feature_date="2026-01-10",
            current_price=100.0,
            return_1d=0.01,
            return_1m=0.05,
            return_3m=0.10,
            return_6m=0.15,
            return_12m=0.20,
            realized_volatility_20d=0.20,
            realized_volatility_60d=0.25,
            average_dollar_volume_20d=1_000_000_000,
            latest_price_date="2026-01-10",
        ),
    )


def seed_alert(
    database_path: Path,
    ticker: str,
    alert_type: str,
    opportunity: float = 80,
    confidence: float = 80,
    risk: float = 70,
) -> None:
    upsert_alert(
        database_path,
        Alert(
            ticker=ticker,
            alert_type=alert_type,
            alert_timestamp=f"2026-01-10T09:30:00-{ticker}",
            priority="high" if alert_type != "no_alert" else "none",
            status="open",
            asset_type="equity",
            current_price=100,
            base_target=125,
            target_low=110,
            target_high=150,
            valuation_gap=0.25,
            opportunity_score=opportunity,
            expected_value_score=opportunity,
            confidence_score=confidence,
            timing_score=65,
            risk_score=risk,
            liquidity_score=90,
            data_quality_score=100,
            main_reasons=f"{ticker} fixture reason.",
            main_risks=f"{ticker} fixture risk.",
            reason_codes="fixture_reason",
            risk_codes="fixture_risk",
            invalidation="Fixture invalidation.",
            alert_model="equity_alert_mvp_v1",
            threshold_set="equity_default",
            model_version="equity_alert_mvp_v1",
            dedupe_key=f"2026-01-10:{ticker}:{alert_type}",
        ),
    )
    upsert_score(
        database_path,
        Score(
            ticker=ticker,
            score_date="2026-01-10",
            opportunity_score=opportunity,
            expected_value_score=opportunity,
            confidence_score=confidence,
            risk_score=risk,
            liquidity_score=90,
            timing_score=65,
            asset_type="equity",
            score_model="equity_score_mvp_v1",
            threshold_set="equity_default",
            model_version="equity_score_mvp_v1",
        ),
    )


def seed_portfolio_fixture(config: AppConfig) -> None:
    initialize_database(config.database_path)
    for ticker in ("AAPL", "MSFT", "NVDA", "TSLA", "META", "GOOG", "CADX"):
        seed_asset(config.database_path, ticker)
    seed_alert(config.database_path, "AAPL", "bullish_divergence")
    seed_alert(config.database_path, "MSFT", "watch_only_gap")
    seed_alert(config.database_path, "NVDA", "bearish_overvaluation", opportunity=30, risk=30)
    seed_alert(config.database_path, "TSLA", "risk_warning", opportunity=45, risk=25)
    seed_alert(config.database_path, "META", "no_alert", opportunity=55, risk=60)
    seed_alert(config.database_path, "GOOG", "no_alert", opportunity=55, risk=60)
    seed_alert(config.database_path, "CADX", "no_alert", opportunity=55, risk=60)

    config.portfolio_positions_path.parent.mkdir(parents=True, exist_ok=True)
    config.portfolio_positions_path.write_text(
        "\n".join(
            (
                "ticker,quantity,account,position_date,currency,market_price,market_value,base_market_value,cost_basis_per_share,cost_basis_total,asset_type,sector,source,as_of_date,effective_date",
                "AAPL,10,taxable,2026-01-10,USD,100,1000,1000,80,800,equity,Technology,manual_csv,2026-01-10,2026-01-10",
                "NVDA,20,taxable,2026-01-10,USD,100,2000,2000,120,2400,equity,Technology,manual_csv,2026-01-10,2026-01-10",
                "TSLA,5,taxable,2026-01-10,USD,100,500,500,90,450,equity,Consumer,manual_csv,2026-01-10,2026-01-10",
                "META,2,taxable,2026-01-10,USD,100,200,200,75,150,equity,Communication,manual_csv,2026-01-10,2026-01-10",
                "CADX,1,taxable,2026-01-10,CAD,100,100,,70,70,equity,Technology,manual_csv,2026-01-10,2026-01-10",
                "",
            )
        ),
        encoding="utf-8",
    )
    config.portfolio_cash_path.write_text(
        "\n".join(
            (
                "account,cash_date,currency,cash_amount,base_cash_amount,source,as_of_date,effective_date",
                "taxable,2026-01-10,USD,10000,10000,manual_csv,2026-01-10,2026-01-10",
                "",
            )
        ),
        encoding="utf-8",
    )


def dashboard_data(html: str) -> dict[str, object]:
    match = re.search(
        r'<script id="tom-dashboard-data" type="application/json">(.*?)</script>',
        html,
        flags=re.DOTALL,
    )
    if not match:
        raise AssertionError("Dashboard data script not found.")
    return json.loads(match.group(1))


class Phase9APortfolioTests(unittest.TestCase):
    def test_config_and_schema_include_portfolio_defaults(self) -> None:
        config = load_config()
        self.assertEqual(
            config.portfolio_positions_path,
            PROJECT_ROOT / "data" / "portfolio" / "manual" / "positions.csv",
        )
        self.assertEqual(
            config.portfolio_cash_path,
            PROJECT_ROOT / "data" / "portfolio" / "manual" / "cash.csv",
        )
        self.assertEqual(config.portfolio_model_version, "portfolio_context_mvp_v1")
        self.assertEqual(config.portfolio_base_currency, "USD")
        self.assertEqual(config.portfolio_default_max_position_weight, 0.15)

        database_path = fresh_database_path("phase9a_schema.sqlite")
        status = initialize_database(database_path)
        self.assertEqual(status.existing_required_table_count, len(REQUIRED_TABLES))
        self.assertIn("portfolio_positions", status.existing_tables)
        self.assertIn("portfolio_cash", status.existing_tables)
        self.assertIn("portfolio_reviews", status.existing_tables)

    def test_default_portfolio_csv_headers_are_created(self) -> None:
        database_path = fresh_database_path("phase9a_headers.sqlite")
        config = make_config(database_path)
        ensure_portfolio_csv_headers(config.portfolio_positions_path, config.portfolio_cash_path)

        self.assertTrue(config.portfolio_positions_path.exists())
        self.assertTrue(config.portfolio_cash_path.exists())
        self.assertIn("ticker,quantity", config.portfolio_positions_path.read_text())
        self.assertIn("cash_amount", config.portfolio_cash_path.read_text())

    def test_portfolio_csv_parsers_validate_columns_and_values(self) -> None:
        positions = parse_portfolio_positions_csv(
            "ticker,quantity,position_date\nAAPL,10,2026-01-10\n"
        )
        cash = parse_portfolio_cash_csv("cash_amount,cash_date\n1000,2026-01-10\n")
        self.assertEqual(positions[0].ticker, "AAPL")
        self.assertEqual(cash[0].cash_amount, 1000)

        with self.assertRaises(ValueError):
            parse_portfolio_positions_csv("ticker,position_date\nAAPL,2026-01-10\n")
        with self.assertRaises(ValueError):
            parse_portfolio_positions_csv(
                "ticker,quantity,position_date\nAAPL,not-a-number,2026-01-10\n"
            )
        with self.assertRaises(ValueError):
            parse_portfolio_cash_csv("cash_amount,cash_date\n1000,not-a-date\n")

    def test_load_portfolio_is_idempotent_and_warns_on_missing_fx(self) -> None:
        database_path = fresh_database_path("phase9a_load.sqlite")
        config = make_config(database_path)
        seed_portfolio_fixture(config)

        first = load_portfolio_csvs(config)
        second = load_portfolio_csvs(config)

        self.assertEqual(first.position_count, 5)
        self.assertEqual(second.position_count, 5)
        self.assertEqual(count_rows_by_table(database_path, "portfolio_positions"), 5)
        self.assertEqual(count_rows_by_table(database_path, "portfolio_cash"), 1)
        self.assertIn("CADX:missing_fx_conversion", first.warnings)

    def test_compute_portfolio_context_review_categories_and_weights(self) -> None:
        database_path = fresh_database_path("phase9a_compute.sqlite")
        config = make_config(database_path)
        seed_portfolio_fixture(config)
        load_portfolio_csvs(config)

        result = compute_portfolio_context(config)
        statuses = {status.ticker: status for status in portfolio_statuses(database_path)}

        self.assertEqual(result.computed_count, 7)
        self.assertEqual(statuses["AAPL"].review_category, "add_candidate")
        self.assertEqual(statuses["MSFT"].review_category, "small_starter_candidate")
        self.assertEqual(statuses["NVDA"].review_category, "exit_review_candidate")
        self.assertEqual(statuses["TSLA"].review_category, "reduce_risk_review")
        self.assertEqual(statuses["META"].review_category, "review_existing_position")
        self.assertEqual(statuses["GOOG"].review_category, "watch")
        self.assertIn("missing_fx_conversion", statuses["CADX"].data_warnings)
        self.assertAlmostEqual(statuses["AAPL"].unrealized_gain_loss, 200)
        self.assertGreater(statuses["AAPL"].position_weight or 0, 0)
        self.assertGreater(statuses["AAPL"].cash_available or 0, 0)

    def test_compute_portfolio_context_ticker_filter_only_writes_requested_ticker(self) -> None:
        database_path = fresh_database_path("phase9a_ticker.sqlite")
        config = make_config(database_path)
        seed_portfolio_fixture(config)
        load_portfolio_csvs(config)

        result = compute_portfolio_context(config, ticker="AAPL")
        reviews = list_portfolio_reviews(database_path)

        self.assertEqual(result.computed_count, 1)
        self.assertEqual([review.ticker for review in reviews], ["AAPL"])

    def test_cli_status_report_dashboard_and_pipeline_include_portfolio_context(self) -> None:
        database_path = fresh_database_path("phase9a_interfaces.sqlite")
        config = make_config(database_path)
        write_config(config)
        seed_portfolio_fixture(config)

        load_output = io.StringIO()
        with redirect_stdout(load_output):
            load_exit = command_load_portfolio(Namespace(config=config.config_path, positions_file=None, cash_file=None))
        compute_output = io.StringIO()
        with redirect_stdout(compute_output):
            compute_exit = command_compute_portfolio_context(Namespace(config=config.config_path, ticker=None))
        portfolio_output = io.StringIO()
        with redirect_stdout(portfolio_output):
            portfolio_exit = command_portfolio_status(Namespace(config=config.config_path))
        status_output = io.StringIO()
        with redirect_stdout(status_output):
            status_exit = command_status(Namespace(config=config.config_path))

        report = write_daily_report(config)
        csv_text = report.csv_path.read_text(encoding="utf-8")
        dashboard = build_dashboard(config)
        dashboard_text = dashboard.path.read_text(encoding="utf-8")
        data = dashboard_data(dashboard_text)

        self.assertEqual(load_exit, 0)
        self.assertEqual(compute_exit, 0)
        self.assertEqual(portfolio_exit, 0)
        self.assertEqual(status_exit, 0)
        self.assertIn("Portfolio loaded", load_output.getvalue())
        self.assertIn("Portfolio reviews computed", compute_output.getvalue())
        self.assertIn("Portfolio position rows:", status_output.getvalue())
        self.assertIn("add_candidate", portfolio_output.getvalue())
        self.assertIn("portfolio_review_category", csv_text)
        self.assertIn("Portfolio Review Summary", report.path.read_text(encoding="utf-8"))
        self.assertIn("Portfolio Review", dashboard_text)
        self.assertNotIn("Phase 9 gated", dashboard_text)
        self.assertTrue(data["portfolio"])
        self.assertIn("latest_portfolio_review_date", data["health"])

        config.watchlist_path.write_text("ticker,asset_type\nAAPL,equity\n", encoding="utf-8")
        with patch_refresh_pipeline_for_test(
            _portfolio_load_step=(1, ()),
            _portfolio_context_step=(1, ()),
        ):
            pipeline_result = run_refresh_data(config, skip_ibkr=True)
        self.assertIn("load-portfolio", [step.step_name for step in pipeline_result.steps])
        self.assertIn(
            "compute-portfolio-context",
            [step.step_name for step in pipeline_result.steps],
        )


if __name__ == "__main__":
    unittest.main()
