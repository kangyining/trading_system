from __future__ import annotations

from argparse import Namespace
from contextlib import redirect_stdout
from datetime import date, timedelta
from pathlib import Path
import csv
import io
import json
import re
import sys
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
TEST_TMP_ROOT = PROJECT_ROOT / ".tmp_tests" / "phase12d"
sys.path.insert(0, str(SRC_PATH))

from target_opportunity_monitor.cli import (
    command_compute_options_outcomes,
    command_options_outcome_report,
    command_options_outcome_status,
    command_options_position_status,
    command_status,
)
from target_opportunity_monitor.config import AppConfig, load_config
from target_opportunity_monitor.dashboard import build_dashboard
from target_opportunity_monitor.db import REQUIRED_TABLES, initialize_database
from target_opportunity_monitor.options import (
    OPTIONS_POSITION_HEADERS,
    compute_options_outcomes,
    ensure_options_positions_csv_header,
    load_options_positions_csv,
)
from target_opportunity_monitor.reporting import REPORT_CSV_COLUMNS, write_daily_report
from target_opportunity_monitor.storage import (
    Asset,
    OptionIncomeReview,
    Price,
    count_rows_by_table,
    count_scoreable_assets,
    list_option_positions,
    list_option_review_outcomes,
    upsert_asset,
    upsert_option_income_review,
    upsert_price,
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
        config_path=TEST_TMP_ROOT / f"phase12d_{database_path.stem}.toml",
        database_path=database_path,
        reports_dir=TEST_TMP_ROOT / "reports_phase12d",
        watchlist_path=TEST_TMP_ROOT / "watchlist_phase12d.csv",
        market_data_dir=TEST_TMP_ROOT / "market_data_phase12d",
        manual_prices_dir=TEST_TMP_ROOT / "market_data_phase12d" / "manual",
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
        options_positions_path=TEST_TMP_ROOT
        / "options"
        / "manual"
        / f"{database_path.stem}_options_positions.csv",
        options_model_version="options_sell_put_mvp_v1",
        options_risk_model_version="options_risk_margin_mvp_v1",
        options_outcome_model_version="options_outcome_mvp_v1",
        options_position_model_version="options_position_ledger_mvp_v1",
        options_outcome_horizons=("5d", "20d", "expiration"),
        options_outcome_use_underlying_prices_only=True,
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
                f'options_positions = "{config.options_positions_path.as_posix()}"',
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
                'outcome_model_version = "options_outcome_mvp_v1"',
                'position_model_version = "options_position_ledger_mvp_v1"',
                'outcome_horizons = ["5d", "20d", "expiration"]',
                "outcome_use_underlying_prices_only = true",
                "",
            )
        ),
        encoding="utf-8",
    )


def seed_asset(
    database_path: Path,
    ticker: str = "AAPL",
    *,
    asset_type: str = "equity",
    asset_role: str = "scoreable",
) -> None:
    upsert_asset(
        database_path,
        Asset(ticker=ticker, asset_type=asset_type, asset_role=asset_role),
    )


def seed_income_review(
    database_path: Path,
    ticker: str = "AAPL",
    *,
    review_date: date | None = None,
    expiration_date: date | None = None,
    current_price: float = 100.0,
    strike: float = 90.0,
    premium: float = 2.0,
) -> None:
    review_day = review_date or date(2026, 1, 2)
    expiration_day = expiration_date or date(2026, 2, 13)
    upsert_option_income_review(
        database_path,
        OptionIncomeReview(
            ticker=ticker,
            review_date=review_day.isoformat(),
            snapshot_timestamp=f"{review_day.isoformat()}T16:00:00",
            expiration_date=expiration_day.isoformat(),
            option_type="put",
            strike=strike,
            bid=premium - 0.1,
            ask=premium + 0.1,
            mid_premium=premium,
            breakeven=strike - premium,
            premium_yield=premium / strike,
            annualized_yield=0.30,
            downside_buffer_pct=(current_price - strike) / current_price,
            breakeven_buffer_pct=(current_price - (strike - premium)) / current_price,
            assignment_notional=strike * 100,
            open_interest=200,
            volume=25,
            current_price=current_price,
            review_category="eligible_watch",
            model_version="options_sell_put_mvp_v1",
            source="fixture",
            as_of_date=review_day.isoformat(),
            effective_date=review_day.isoformat(),
        ),
    )


def seed_price_series(
    database_path: Path,
    ticker: str = "AAPL",
    *,
    start: date = date(2026, 1, 3),
    days: int = 32,
    close_base: float = 100.0,
    expiration_date: date = date(2026, 2, 13),
    expiration_close: float = 92.0,
) -> None:
    for index in range(days):
        price_date = start + timedelta(days=index)
        close = close_base + index
        low = close - 8.0
        high = close + 3.0
        if index == 9:
            low = 87.0
        upsert_price(
            database_path,
            Price(
                ticker=ticker,
                price_date=price_date.isoformat(),
                open=close,
                high=high,
                low=low,
                close=close,
                adjusted_close=close,
                volume=1_000_000,
                source="fixture",
            ),
        )
    upsert_price(
        database_path,
        Price(
            ticker=ticker,
            price_date=expiration_date.isoformat(),
            open=expiration_close,
            high=expiration_close + 2,
            low=expiration_close - 2,
            close=expiration_close,
            adjusted_close=expiration_close,
            volume=1_000_000,
            source="fixture",
        ),
    )


def write_positions_csv(config: AppConfig, rows: list[dict[str, object]]) -> None:
    config.options_positions_path.parent.mkdir(parents=True, exist_ok=True)
    with config.options_positions_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=OPTIONS_POSITION_HEADERS)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def position_row(ticker: str = "AAPL") -> dict[str, object]:
    return {
        "ticker": ticker,
        "open_date": "2026-01-02",
        "expiration_date": "2026-02-13",
        "option_type": "put",
        "side": "short_put",
        "strike": 90,
        "contracts": 1,
        "premium": 2,
        "close_date": "",
        "close_price": "",
        "assigned_flag": "",
        "assignment_price": "",
        "fees": "",
        "account": "paper",
        "source": "fixture",
        "source_url": "https://example.com/options-position",
        "notes": "",
        "as_of_date": "2026-01-02",
        "effective_date": "2026-01-02",
    }


def dashboard_data(html: str) -> dict[str, object]:
    match = re.search(
        r'<script id="tom-dashboard-data" type="application/json">(.*?)</script>',
        html,
        flags=re.DOTALL,
    )
    if not match:
        raise AssertionError("Dashboard data script not found.")
    return json.loads(match.group(1))


class Phase12DOptionsOutcomeTests(unittest.TestCase):
    def test_config_defaults_schema_and_header(self) -> None:
        default_config = load_config(PROJECT_ROOT / "configs" / "default.toml")
        self.assertEqual(
            default_config.options_outcome_model_version,
            "options_outcome_mvp_v1",
        )
        self.assertEqual(
            default_config.options_position_model_version,
            "options_position_ledger_mvp_v1",
        )
        self.assertEqual(default_config.options_outcome_horizons, ("5d", "20d", "expiration"))
        self.assertIn("option_review_outcomes", REQUIRED_TABLES)
        self.assertIn("option_position_ledger", REQUIRED_TABLES)

        database_path = fresh_database_path("phase12d_schema.sqlite")
        config = make_config(database_path)
        initialize_database(database_path)
        ensure_options_positions_csv_header(config.options_positions_path)
        self.assertEqual(count_rows_by_table(database_path, "option_review_outcomes"), 0)
        self.assertEqual(count_rows_by_table(database_path, "option_position_ledger"), 0)
        self.assertTrue(config.options_positions_path.exists())
        self.assertIn("option_outcome_status", REPORT_CSV_COLUMNS)

    def test_position_loader_validation_and_idempotent_upsert(self) -> None:
        database_path = fresh_database_path("phase12d_positions.sqlite")
        config = make_config(database_path)
        initialize_database(database_path)
        seed_asset(database_path, "AAPL")
        write_positions_csv(config, [position_row("AAPL")])

        result = load_options_positions_csv(config)
        second = load_options_positions_csv(config)
        positions = list_option_positions(database_path, ticker="AAPL")

        self.assertEqual(result.loaded_count, 1)
        self.assertEqual(second.loaded_count, 1)
        self.assertEqual(len(positions), 1)
        self.assertEqual(positions[0].position_status, "expired_or_pending_manual_close")
        self.assertEqual(count_rows_by_table(database_path, "option_position_ledger"), 1)

        invalid = position_row("AAPL")
        invalid["premium"] = "not-a-number"
        write_positions_csv(config, [invalid])
        with self.assertRaises(ValueError):
            load_options_positions_csv(config)

    def test_outcome_math_expiration_flags_and_linked_position(self) -> None:
        database_path = fresh_database_path("phase12d_outcomes.sqlite")
        config = make_config(database_path)
        initialize_database(database_path)
        seed_asset(database_path, "AAPL")
        seed_income_review(database_path, "AAPL")
        seed_price_series(database_path, "AAPL", expiration_close=92.0)
        write_positions_csv(config, [position_row("AAPL")])
        load_options_positions_csv(config)

        result = compute_options_outcomes(config, ticker="AAPL")
        second = compute_options_outcomes(config, ticker="AAPL")
        outcomes = list_option_review_outcomes(database_path, ticker="AAPL")

        self.assertEqual(result.computed_count, 1)
        self.assertEqual(second.computed_count, 1)
        self.assertEqual(len(outcomes), 1)
        outcome = outcomes[0]
        self.assertEqual(outcome.outcome_status, "completed")
        self.assertEqual(outcome.expiration_status, "above_strike")
        self.assertEqual(outcome.above_strike_flag, 1)
        self.assertEqual(outcome.above_breakeven_flag, 1)
        self.assertEqual(outcome.touched_strike_flag, 1)
        self.assertEqual(outcome.touched_breakeven_flag, 1)
        self.assertEqual(outcome.linked_position_count, 1)
        self.assertAlmostEqual(outcome.return_5d or 0, 0.04)
        self.assertAlmostEqual(outcome.return_20d or 0, 0.19)
        self.assertIn("underlying_price_proxy_only", outcome.data_warnings or "")

    def test_expiration_statuses_and_pending_outcomes(self) -> None:
        database_path = fresh_database_path("phase12d_expiration_statuses.sqlite")
        config = make_config(database_path)
        initialize_database(database_path)
        for ticker, expiration_close in (("MID", 89.0), ("LOW", 87.0)):
            seed_asset(database_path, ticker)
            seed_income_review(database_path, ticker)
            seed_price_series(database_path, ticker, expiration_close=expiration_close)
        seed_asset(database_path, "PEND")
        seed_income_review(
            database_path,
            "PEND",
            review_date=date.today(),
            expiration_date=date.today() + timedelta(days=30),
        )

        compute_options_outcomes(config)
        by_ticker = {
            outcome.ticker: outcome
            for outcome in list_option_review_outcomes(database_path)
        }

        self.assertEqual(
            by_ticker["MID"].expiration_status,
            "below_strike_above_breakeven",
        )
        self.assertEqual(by_ticker["LOW"].expiration_status, "below_breakeven")
        self.assertEqual(by_ticker["PEND"].outcome_status, "pending")
        self.assertEqual(by_ticker["PEND"].expiration_status, "pending")

    def test_reference_instrument_and_ticker_filter(self) -> None:
        database_path = fresh_database_path("phase12d_reference.sqlite")
        config = make_config(database_path)
        initialize_database(database_path)
        seed_asset(database_path, "AAPL")
        seed_asset(database_path, "SOXL", asset_type="etf", asset_role="commentary_validation")
        seed_income_review(database_path, "AAPL")
        seed_income_review(database_path, "SOXL")
        seed_price_series(database_path, "AAPL")
        seed_price_series(database_path, "SOXL")

        compute_options_outcomes(config, ticker="AAPL")
        self.assertEqual(len(list_option_review_outcomes(database_path, ticker="AAPL")), 1)
        self.assertEqual(len(list_option_review_outcomes(database_path, ticker="SOXL")), 0)

        compute_options_outcomes(config, ticker="SOXL")
        soxl = list_option_review_outcomes(database_path, ticker="SOXL")[0]
        self.assertIn("reference_instrument_only", soxl.data_warnings or "")
        self.assertEqual(count_scoreable_assets(database_path), 1)

    def test_cli_reports_csv_and_dashboard_include_phase12d_fields(self) -> None:
        database_path = fresh_database_path("phase12d_outputs.sqlite")
        config = make_config(database_path)
        write_config(config)
        initialize_database(database_path)
        seed_asset(database_path, "AAPL")
        seed_income_review(database_path, "AAPL")
        seed_price_series(database_path, "AAPL")
        write_positions_csv(config, [position_row("AAPL")])
        load_options_positions_csv(config)

        position_output = io.StringIO()
        with redirect_stdout(position_output):
            self.assertEqual(command_options_position_status(Namespace(config=config.config_path)), 0)
        self.assertIn("Position rows: 1", position_output.getvalue())

        output = io.StringIO()
        with redirect_stdout(output):
            self.assertEqual(
                command_compute_options_outcomes(
                    Namespace(config=config.config_path, ticker="AAPL")
                ),
                0,
            )
        self.assertIn("AAPL: computed", output.getvalue())

        status_output = io.StringIO()
        with redirect_stdout(status_output):
            self.assertEqual(command_options_outcome_status(Namespace(config=config.config_path)), 0)
        self.assertIn("Outcome rows: 1", status_output.getvalue())

        report_output = io.StringIO()
        with redirect_stdout(report_output):
            self.assertEqual(command_options_outcome_report(Namespace(config=config.config_path)), 0)
        self.assertIn("# Options Outcome Report", report_output.getvalue())

        status_text = io.StringIO()
        with redirect_stdout(status_text):
            self.assertEqual(command_status(Namespace(config=config.config_path)), 0)
        self.assertIn("Option review outcome rows: 1", status_text.getvalue())
        self.assertIn("Option position ledger rows: 1", status_text.getvalue())

        report = write_daily_report(config)
        csv_text = report.csv_path.read_text(encoding="utf-8") if report.csv_path else ""
        self.assertIn("option_outcome_status", csv_text)
        self.assertIn("option_position_count", csv_text)
        self.assertIn("Option review outcome rows: `1`", report.path.read_text(encoding="utf-8"))

        dashboard = build_dashboard(config)
        data = dashboard_data(dashboard.path.read_text(encoding="utf-8"))
        self.assertEqual(data["health"]["option_review_outcome_rows"], 1)
        self.assertEqual(data["health"]["option_position_ledger_rows"], 1)


if __name__ == "__main__":
    unittest.main()
