from __future__ import annotations

from argparse import Namespace
from contextlib import redirect_stdout
from datetime import date, datetime, timedelta
from pathlib import Path
import csv
import io
import json
import re
import sys
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
TEST_TMP_ROOT = PROJECT_ROOT / ".tmp_tests" / "phase12c"
sys.path.insert(0, str(SRC_PATH))

from target_opportunity_monitor.cli import (
    command_compute_options_risk,
    command_options_risk_report,
    command_options_risk_status,
    command_status,
)
from target_opportunity_monitor.config import AppConfig, load_config
from target_opportunity_monitor.dashboard import build_dashboard
from target_opportunity_monitor.db import REQUIRED_TABLES, initialize_database
from target_opportunity_monitor.options import (
    OPTIONS_CHAIN_HEADERS,
    compute_options_income,
    compute_options_risk,
    load_options_chain_csv,
)
from target_opportunity_monitor.reporting import REPORT_CSV_COLUMNS, write_daily_report
from target_opportunity_monitor.storage import (
    Asset,
    PortfolioReview,
    PriceFeature,
    RangeSnapshot,
    count_rows_by_table,
    count_scoreable_assets,
    list_option_risk_reviews,
    upsert_asset,
    upsert_portfolio_review,
    upsert_price_feature,
    upsert_range_snapshot,
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
        config_path=TEST_TMP_ROOT / f"phase12c_{database_path.stem}.toml",
        database_path=database_path,
        reports_dir=TEST_TMP_ROOT / "reports_phase12c",
        watchlist_path=TEST_TMP_ROOT / "watchlist_phase12c.csv",
        market_data_dir=TEST_TMP_ROOT / "market_data_phase12c",
        manual_prices_dir=TEST_TMP_ROOT / "market_data_phase12c" / "manual",
        market_data_primary_source="stooq",
        market_data_secondary_source="yahoo_chart",
        market_data_mode="csv",
        market_data_lookback_days=800,
        market_data_stale_after_days=7,
        market_data_minimum_history_days=252,
        universe_mode="manual_watchlist",
        run_mode="daily_scoring",
        report_title="Target Opportunity Monitor Daily Report",
        options_chain_path=TEST_TMP_ROOT
        / "options"
        / "manual"
        / f"{database_path.stem}_options_chain.csv",
        options_model_version="options_sell_put_mvp_v1",
        options_default_min_dte=7,
        options_default_max_dte=60,
        options_min_annualized_premium_yield=0.10,
        options_min_open_interest=100,
        options_min_volume=10,
        options_assignment_buffer_pct=0.10,
        options_use_range_filter=True,
        options_risk_model_version="options_risk_margin_mvp_v1",
        options_risk_margin_model="cash_secured_proxy",
        options_max_single_contract_notional_weight=0.05,
        options_max_total_assignment_notional_weight=0.20,
        options_minimum_cash_reserve_after_assignment=0.05,
        options_downside_scenario_pcts=(-0.05, -0.10, -0.20),
        options_reference_instrument_risk_warning=True,
    )


def write_config(config: AppConfig) -> None:
    config.config_path.parent.mkdir(parents=True, exist_ok=True)
    config.config_path.write_text(
        "\n".join(
            (
                "[paths]",
                f'project_root = "{config.project_root.as_posix()}"',
                f'database = "{config.database_path.as_posix()}"',
                f'reports = "{config.reports_dir.as_posix()}"',
                f'watchlist = "{config.watchlist_path.as_posix()}"',
                f'options_chain = "{config.options_chain_path.as_posix()}"',
                "",
                "[run]",
                'universe_mode = "manual_watchlist"',
                'run_mode = "daily_scoring"',
                "",
                "[reports]",
                f'title = "{config.report_title}"',
                "",
                "[options]",
                'model_version = "options_sell_put_mvp_v1"',
                'risk_model_version = "options_risk_margin_mvp_v1"',
                'risk_margin_model = "cash_secured_proxy"',
                "max_single_contract_notional_weight = 0.05",
                "max_total_assignment_notional_weight = 0.20",
                "minimum_cash_reserve_after_assignment = 0.05",
                "downside_scenario_pcts = [-0.05, -0.10, -0.20]",
                "reference_instrument_risk_warning = true",
                "",
            )
        ),
        encoding="utf-8",
    )


def seed_underlying(
    database_path: Path,
    ticker: str = "AAPL",
    *,
    asset_type: str = "equity",
    asset_role: str = "scoreable",
    current_price: float = 100.0,
    range_level: float | None = 95.0,
) -> None:
    today = date.today().isoformat()
    now = datetime.now().isoformat(timespec="seconds")
    upsert_asset(
        database_path,
        Asset(ticker=ticker, asset_type=asset_type, asset_role=asset_role),
    )
    upsert_price_feature(
        database_path,
        PriceFeature(
            ticker=ticker,
            feature_date=today,
            current_price=current_price,
            return_1d=0.01,
            return_1m=0.02,
            return_3m=0.04,
            return_6m=0.08,
            return_12m=0.12,
            realized_volatility_20d=0.20,
            realized_volatility_60d=0.25,
            average_dollar_volume_20d=1_000_000_000,
            latest_price_date=today,
        ),
    )
    if range_level is not None:
        upsert_range_snapshot(
            database_path,
            RangeSnapshot(
                ticker=ticker,
                snapshot_timestamp=now,
                asset_type=asset_type,
                current_price=current_price,
                starter_buy_below=range_level,
                add_below=range_level,
                hold_low=range_level,
                hold_high=current_price * 1.25,
                range_state="hold",
                source="fixture",
            ),
        )


def seed_portfolio(
    database_path: Path,
    ticker: str = "AAPL",
    *,
    total_value: float = 200_000.0,
    cash: float = 100_000.0,
    position_weight: float = 0.01,
) -> None:
    today = date.today().isoformat()
    upsert_portfolio_review(
        database_path,
        PortfolioReview(
            ticker=ticker,
            review_date=today,
            held_flag=1,
            position_value=total_value * position_weight,
            position_weight=position_weight,
            cash_available=cash,
            total_portfolio_value=total_value,
            review_category="review_existing_position",
        ),
    )


def option_row(
    ticker: str = "AAPL",
    *,
    strike: float = 90.0,
    bid: float = 1.8,
    ask: float = 2.2,
    volume: float = 25,
    open_interest: float = 150,
    expiration_days: int = 30,
) -> dict[str, object]:
    return {
        "ticker": ticker,
        "snapshot_timestamp": datetime.now().isoformat(timespec="seconds"),
        "expiration_date": (date.today() + timedelta(days=expiration_days)).isoformat(),
        "option_type": "put",
        "strike": strike,
        "bid": bid,
        "ask": ask,
        "last": "",
        "mark": "",
        "volume": volume,
        "open_interest": open_interest,
        "implied_volatility": 0.35,
        "delta": -0.25,
        "gamma": "",
        "theta": "",
        "vega": "",
        "source": "fixture_chain",
        "source_url": "https://example.com/options",
        "as_of_date": date.today().isoformat(),
        "effective_date": date.today().isoformat(),
    }


def write_options_csv(config: AppConfig, rows: list[dict[str, object]]) -> None:
    config.options_chain_path.parent.mkdir(parents=True, exist_ok=True)
    with config.options_chain_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=OPTIONS_CHAIN_HEADERS)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def seed_income_review(
    config: AppConfig,
    ticker: str = "AAPL",
    *,
    asset_type: str = "equity",
    asset_role: str = "scoreable",
    current_price: float = 100.0,
    range_level: float | None = 95.0,
    strike: float = 90.0,
) -> None:
    initialize_database(config.database_path)
    seed_underlying(
        config.database_path,
        ticker,
        asset_type=asset_type,
        asset_role=asset_role,
        current_price=current_price,
        range_level=range_level,
    )
    write_options_csv(config, [option_row(ticker=ticker, strike=strike)])
    load_options_chain_csv(config)
    compute_options_income(config, ticker=ticker)


def dashboard_data(html: str) -> dict[str, object]:
    match = re.search(
        r'<script id="tom-dashboard-data" type="application/json">(.*?)</script>',
        html,
        flags=re.DOTALL,
    )
    if not match:
        raise AssertionError("Dashboard data script not found.")
    return json.loads(match.group(1))


class Phase12COptionsRiskTests(unittest.TestCase):
    def test_config_defaults_and_schema_include_option_risk(self) -> None:
        default_config = load_config(PROJECT_ROOT / "configs" / "default.toml")
        self.assertEqual(
            default_config.options_risk_model_version,
            "options_risk_margin_mvp_v1",
        )
        self.assertEqual(default_config.options_risk_margin_model, "cash_secured_proxy")
        self.assertEqual(default_config.options_downside_scenario_pcts, (-0.05, -0.10, -0.20))
        self.assertIn("option_risk_reviews", REQUIRED_TABLES)

        database_path = fresh_database_path("phase12c_schema.sqlite")
        initialize_database(database_path)
        self.assertEqual(count_rows_by_table(database_path, "option_risk_reviews"), 0)

    def test_risk_review_math_and_idempotent_upsert(self) -> None:
        database_path = fresh_database_path("phase12c_math.sqlite")
        config = make_config(database_path)
        seed_income_review(config)
        seed_portfolio(database_path)

        result = compute_options_risk(config, ticker="AAPL")
        second = compute_options_risk(config, ticker="AAPL")
        reviews = list_option_risk_reviews(database_path, ticker="AAPL")

        self.assertEqual(result.computed_count, 1)
        self.assertEqual(second.computed_count, 1)
        self.assertEqual(len(reviews), 1)
        review = reviews[0]
        self.assertEqual(review.risk_category, "risk_review_ready")
        self.assertAlmostEqual(review.assignment_notional or 0, 9000.0)
        self.assertAlmostEqual(review.premium_income or 0, 200.0)
        self.assertAlmostEqual(review.cash_secured_requirement or 0, 8800.0)
        self.assertAlmostEqual(review.max_cash_secured_loss or 0, 8800.0)
        self.assertAlmostEqual(review.scenario_pl_10pct or 0, 200.0)
        self.assertAlmostEqual(review.scenario_pl_20pct or 0, -800.0)
        self.assertAlmostEqual(review.projected_assignment_weight or 0, 0.045)
        self.assertAlmostEqual(review.cash_after_assignment or 0, 91_200.0)
        self.assertEqual(review.max_contracts_advisory, 1)

    def test_missing_portfolio_context_warns_without_blocking(self) -> None:
        database_path = fresh_database_path("phase12c_missing_portfolio.sqlite")
        config = make_config(database_path)
        seed_income_review(config)

        compute_options_risk(config, ticker="AAPL")
        review = list_option_risk_reviews(database_path, ticker="AAPL")[0]

        self.assertEqual(review.risk_category, "portfolio_context_needed")
        self.assertIn("missing_portfolio_context", review.risk_warnings or "")

    def test_portfolio_fixture_categories(self) -> None:
        database_path = fresh_database_path("phase12c_portfolio_categories.sqlite")
        config = make_config(database_path)
        seed_income_review(config, ticker="CASH", current_price=100)
        seed_income_review(config, ticker="BIG", current_price=100)
        seed_income_review(config, ticker="POS", current_price=100)
        seed_portfolio(database_path, "CASH", total_value=100_000, cash=9_000, position_weight=0.0)
        seed_portfolio(database_path, "BIG", total_value=100_000, cash=100_000, position_weight=0.0)
        seed_portfolio(database_path, "POS", total_value=300_000, cash=100_000, position_weight=0.13)

        compute_options_risk(config)
        by_ticker = {review.ticker: review for review in list_option_risk_reviews(database_path)}

        self.assertEqual(by_ticker["CASH"].risk_category, "cash_reserve_breach")
        self.assertEqual(by_ticker["BIG"].risk_category, "assignment_notional_high")
        self.assertEqual(
            by_ticker["POS"].risk_category,
            "assignment_would_exceed_position_limit",
        )

    def test_reference_instrument_gets_risk_but_stays_non_scoreable(self) -> None:
        database_path = fresh_database_path("phase12c_reference.sqlite")
        config = make_config(database_path)
        seed_income_review(
            config,
            ticker="SOXL",
            asset_type="etf",
            asset_role="commentary_validation",
            current_price=100,
            range_level=None,
        )

        compute_options_risk(config, ticker="SOXL")
        review = list_option_risk_reviews(database_path, ticker="SOXL")[0]

        self.assertEqual(review.risk_category, "reference_only_review")
        self.assertIn("reference_instrument_only", review.risk_warnings or "")
        self.assertEqual(count_scoreable_assets(database_path), 0)

    def test_cli_reports_csv_dashboard_and_ticker_filter(self) -> None:
        database_path = fresh_database_path("phase12c_outputs.sqlite")
        config = make_config(database_path)
        write_config(config)
        seed_income_review(config, ticker="AAPL")
        seed_income_review(config, ticker="MSFT")
        seed_portfolio(database_path, "AAPL")
        seed_portfolio(database_path, "MSFT")

        output = io.StringIO()
        with redirect_stdout(output):
            self.assertEqual(
                command_compute_options_risk(
                    Namespace(config=config.config_path, ticker="AAPL")
                ),
                0,
            )
        self.assertIn("AAPL: computed", output.getvalue())
        self.assertEqual(len(list_option_risk_reviews(database_path, ticker="AAPL")), 1)
        self.assertEqual(len(list_option_risk_reviews(database_path, ticker="MSFT")), 0)

        compute_options_risk(config)
        status_output = io.StringIO()
        with redirect_stdout(status_output):
            self.assertEqual(command_options_risk_status(Namespace(config=config.config_path)), 0)
        self.assertIn("Risk review rows: 2", status_output.getvalue())

        report_output = io.StringIO()
        with redirect_stdout(report_output):
            self.assertEqual(command_options_risk_report(Namespace(config=config.config_path)), 0)
        self.assertIn("# Options Risk Report", report_output.getvalue())

        status_text = io.StringIO()
        with redirect_stdout(status_text):
            self.assertEqual(command_status(Namespace(config=config.config_path)), 0)
        self.assertIn("Option risk review rows: 2", status_text.getvalue())

        report = write_daily_report(config)
        csv_text = report.csv_path.read_text(encoding="utf-8") if report.csv_path else ""
        self.assertIn("option_risk_category", REPORT_CSV_COLUMNS)
        self.assertIn("option_cash_secured_requirement", csv_text)

        dashboard = build_dashboard(config)
        data = dashboard_data(dashboard.path.read_text(encoding="utf-8"))
        self.assertEqual(data["health"]["option_risk_review_rows"], 2)
        self.assertTrue(any(row.get("option_risk_category") for row in data["rows"]))


if __name__ == "__main__":
    unittest.main()
