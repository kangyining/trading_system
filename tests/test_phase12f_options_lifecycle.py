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
TEST_TMP_ROOT = PROJECT_ROOT / ".tmp_tests" / "phase12f"
sys.path.insert(0, str(SRC_PATH))

from target_opportunity_monitor.cli import (
    command_compute_options_lifecycle,
    command_options_lifecycle_report,
    command_options_lifecycle_status,
    command_options_status,
    command_status,
)
from target_opportunity_monitor.config import AppConfig, load_config
from target_opportunity_monitor.dashboard import build_dashboard
from target_opportunity_monitor.db import REQUIRED_TABLES, initialize_database
from target_opportunity_monitor.options import (
    OPTIONS_POSITION_HEADERS,
    compute_options_lifecycle,
    load_options_positions_csv,
)
from target_opportunity_monitor.reporting import REPORT_CSV_COLUMNS, write_daily_report
from target_opportunity_monitor.storage import (
    Asset,
    OptionChainSnapshot,
    OptionIncomeReview,
    OptionReviewOutcome,
    OptionRiskReview,
    Price,
    count_rows_by_table,
    count_scoreable_assets,
    list_option_position_lifecycle_reviews,
    list_option_positions,
    upsert_asset,
    upsert_option_chain_snapshot,
    upsert_option_income_review,
    upsert_option_review_outcome,
    upsert_option_risk_review,
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
        config_path=TEST_TMP_ROOT / f"phase12f_{database_path.stem}.toml",
        database_path=database_path,
        reports_dir=TEST_TMP_ROOT / "reports_phase12f",
        watchlist_path=TEST_TMP_ROOT / "watchlist_phase12f.csv",
        market_data_dir=TEST_TMP_ROOT / "market_data_phase12f",
        manual_prices_dir=TEST_TMP_ROOT / "market_data_phase12f" / "manual",
        market_data_primary_source="stooq",
        market_data_secondary_source="yahoo_chart",
        market_data_mode="csv",
        market_data_lookback_days=800,
        market_data_stale_after_days=7,
        market_data_minimum_history_days=252,
        universe_mode="manual_watchlist",
        run_mode="daily_scoring",
        report_title="Target Opportunity Monitor Daily Report",
        options_positions_path=TEST_TMP_ROOT
        / "options"
        / "manual"
        / f"{database_path.stem}_options_positions.csv",
        options_model_version="options_sell_put_mvp_v1",
        options_risk_model_version="options_risk_margin_mvp_v1",
        options_outcome_model_version="options_outcome_mvp_v1",
        options_position_model_version="options_position_ledger_mvp_v1",
        options_lifecycle_model_version="options_lifecycle_mvp_v1",
        options_realized_pl_model_version="options_realized_pl_mvp_v1",
        options_option_multiplier=100,
        options_position_stale_after_days=7,
        options_assignment_tracking_enabled=True,
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
                'lifecycle_model_version = "options_lifecycle_mvp_v1"',
                'realized_pl_model_version = "options_realized_pl_mvp_v1"',
                "option_multiplier = 100",
                "position_stale_after_days = 7",
                "assignment_tracking_enabled = true",
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


def seed_price(database_path: Path, ticker: str, price_date: str, close: float) -> None:
    upsert_price(
        database_path,
        Price(
            ticker=ticker,
            price_date=price_date,
            open=close,
            high=close + 1,
            low=close - 1,
            close=close,
            adjusted_close=close,
            volume=1_000_000,
            source="fixture",
        ),
    )


def seed_income_review(
    database_path: Path,
    ticker: str = "AAPL",
    *,
    review_date: str = "2026-01-02",
    expiration_date: str = "2026-02-13",
    strike: float = 90.0,
    premium: float = 2.0,
) -> None:
    upsert_option_income_review(
        database_path,
        OptionIncomeReview(
            ticker=ticker,
            review_date=review_date,
            snapshot_timestamp=f"{review_date}T16:00:00",
            expiration_date=expiration_date,
            option_type="put",
            strike=strike,
            bid=premium - 0.1,
            ask=premium + 0.1,
            mid_premium=premium,
            breakeven=strike - premium,
            premium_yield=premium / strike,
            annualized_yield=0.30,
            downside_buffer_pct=0.10,
            breakeven_buffer_pct=0.12,
            assignment_notional=strike * 100,
            open_interest=200,
            volume=25,
            current_price=100.0,
            review_category="eligible_watch",
            model_version="options_sell_put_mvp_v1",
            source="fixture",
            as_of_date=review_date,
            effective_date=review_date,
        ),
    )


def seed_linked_risk_and_outcome(database_path: Path) -> None:
    upsert_option_risk_review(
        database_path,
        OptionRiskReview(
            option_income_review_id=1,
            ticker="AAPL",
            review_date="2026-01-02",
            risk_review_date="2026-01-02",
            expiration_date="2026-02-13",
            option_type="put",
            strike=90,
            mid_premium=2,
            risk_category="risk_review_ready",
            model_version="options_risk_margin_mvp_v1",
        ),
    )
    upsert_option_review_outcome(
        database_path,
        OptionReviewOutcome(
            option_income_review_id=1,
            ticker="AAPL",
            review_date="2026-01-02",
            outcome_date="2026-02-14",
            expiration_date="2026-02-13",
            option_type="put",
            strike=90,
            outcome_status="completed",
            expiration_status="above_strike",
            model_version="options_outcome_mvp_v1",
        ),
    )


def seed_option_mark(
    database_path: Path,
    ticker: str,
    *,
    expiration_date: str,
    strike: float,
    mark: float,
) -> None:
    upsert_option_chain_snapshot(
        database_path,
        OptionChainSnapshot(
            ticker=ticker,
            snapshot_timestamp=datetime.now().isoformat(timespec="seconds"),
            expiration_date=expiration_date,
            option_type="put",
            strike=strike,
            bid=mark - 0.05,
            ask=mark + 0.05,
            mark=mark,
            source="fixture_chain",
            source_url="https://example.com/options",
        ),
    )


def write_positions_csv(config: AppConfig, rows: list[dict[str, object]]) -> None:
    config.options_positions_path.parent.mkdir(parents=True, exist_ok=True)
    with config.options_positions_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=OPTIONS_POSITION_HEADERS)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def position_row(
    ticker: str = "AAPL",
    *,
    position_id: str = "pos-1",
    open_date: str = "2026-01-02",
    expiration_date: str = "2026-02-13",
    strike: float = 90.0,
    premium: float = 2.0,
    close_date: str = "",
    close_price: str | float = "",
    assigned_flag: str | int = "",
    assignment_price: str | float = "",
    status: str = "",
    fees: str | float = "",
    roll_from_position_id: str = "",
    roll_to_position_id: str = "",
) -> dict[str, object]:
    return {
        "position_id": position_id,
        "ticker": ticker,
        "open_date": open_date,
        "expiration_date": expiration_date,
        "option_type": "put",
        "side": "short_put",
        "strike": strike,
        "contracts": 1,
        "premium": premium,
        "close_date": close_date,
        "close_price": close_price,
        "assigned_flag": assigned_flag,
        "assignment_price": assignment_price,
        "fees": fees,
        "account": "paper",
        "status": status,
        "roll_from_position_id": roll_from_position_id,
        "roll_to_position_id": roll_to_position_id,
        "underlying_assignment_date": "",
        "underlying_shares": "",
        "underlying_cost_basis": "",
        "tags": "test",
        "source": "fixture",
        "source_url": "https://example.com/options-position",
        "notes": "",
        "as_of_date": open_date,
        "effective_date": open_date,
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


class Phase12FOptionsLifecycleTests(unittest.TestCase):
    def test_config_defaults_schema_and_position_header(self) -> None:
        default_config = load_config(PROJECT_ROOT / "configs" / "default.toml")
        self.assertEqual(
            default_config.options_lifecycle_model_version,
            "options_lifecycle_mvp_v1",
        )
        self.assertEqual(
            default_config.options_realized_pl_model_version,
            "options_realized_pl_mvp_v1",
        )
        self.assertEqual(default_config.options_option_multiplier, 100)
        self.assertEqual(default_config.options_position_stale_after_days, 7)
        self.assertTrue(default_config.options_assignment_tracking_enabled)
        self.assertIn("option_position_lifecycle_reviews", REQUIRED_TABLES)
        self.assertIn("option_lifecycle_status", REPORT_CSV_COLUMNS)

        database_path = fresh_database_path("phase12f_schema.sqlite")
        config = make_config(database_path)
        initialize_database(database_path)
        load_options_positions_csv(config)

        self.assertEqual(count_rows_by_table(database_path, "option_position_lifecycle_reviews"), 0)
        header = config.options_positions_path.read_text(encoding="utf-8").splitlines()[0]
        self.assertIn("position_id", header)
        self.assertIn("roll_from_position_id", header)
        self.assertIn("underlying_cost_basis", header)

    def test_position_loader_accepts_lifecycle_fields_and_uses_position_id(self) -> None:
        database_path = fresh_database_path("phase12f_loader.sqlite")
        config = make_config(database_path)
        initialize_database(database_path)
        seed_asset(database_path, "AAPL")
        row = position_row(
            "AAPL",
            position_id="manual-aapl-1",
            close_date="2026-01-10",
            close_price=0.5,
            fees=1,
            roll_to_position_id="manual-aapl-2",
        )
        write_positions_csv(config, [row])

        result = load_options_positions_csv(config)
        second = load_options_positions_csv(config)
        positions = list_option_positions(database_path, ticker="AAPL")

        self.assertEqual(result.loaded_count, 1)
        self.assertEqual(second.loaded_count, 1)
        self.assertEqual(len(positions), 1)
        self.assertEqual(positions[0].position_key, "manual-aapl-1")
        self.assertEqual(positions[0].position_id, "manual-aapl-1")
        self.assertEqual(positions[0].roll_to_position_id, "manual-aapl-2")

    def test_lifecycle_math_closed_expired_assigned_and_open(self) -> None:
        database_path = fresh_database_path("phase12f_math.sqlite")
        config = make_config(database_path)
        initialize_database(database_path)
        for ticker in ("AAPL", "EXP", "ASN", "OPN"):
            seed_asset(database_path, ticker)
            seed_income_review(database_path, ticker=ticker)
        seed_price(database_path, "EXP", "2026-02-13", 95)
        seed_price(database_path, "ASN", "2026-02-13", 85)
        seed_income_review(
            database_path,
            ticker="OPN",
            expiration_date=(date.today() + timedelta(days=30)).isoformat(),
        )
        seed_option_mark(
            database_path,
            "OPN",
            expiration_date=(date.today() + timedelta(days=30)).isoformat(),
            strike=90,
            mark=1.0,
        )
        write_positions_csv(
            config,
            [
                position_row("AAPL", close_date="2026-01-10", close_price=0.5, fees=1),
                position_row("EXP", position_id="exp-1"),
                position_row("ASN", position_id="asn-1", assigned_flag=1, assignment_price=88),
                position_row(
                    "OPN",
                    position_id="opn-1",
                    expiration_date=(date.today() + timedelta(days=30)).isoformat(),
                ),
            ],
        )
        load_options_positions_csv(config)

        result = compute_options_lifecycle(config)
        reviews = {
            review.position_id: review
            for review in list_option_position_lifecycle_reviews(database_path)
        }

        self.assertEqual(result.computed_count, 4)
        self.assertEqual(reviews["pos-1"].lifecycle_status, "closed")
        self.assertAlmostEqual(reviews["pos-1"].realized_pl or 0, 149.0)
        self.assertEqual(reviews["exp-1"].lifecycle_status, "expired_worthless")
        self.assertAlmostEqual(reviews["exp-1"].realized_pl or 0, 200.0)
        self.assertEqual(reviews["asn-1"].lifecycle_status, "assigned")
        self.assertAlmostEqual(reviews["asn-1"].assignment_notional or 0, 8800.0)
        self.assertAlmostEqual(reviews["asn-1"].underlying_cost_basis or 0, 86.0)
        self.assertEqual(reviews["opn-1"].lifecycle_status, "open")
        self.assertAlmostEqual(reviews["opn-1"].open_pl_proxy or 0, 100.0)

    def test_linking_reference_boundary_unmatched_and_ticker_filter(self) -> None:
        database_path = fresh_database_path("phase12f_links.sqlite")
        config = make_config(database_path)
        initialize_database(database_path)
        seed_asset(database_path, "AAPL")
        seed_asset(database_path, "SOXL", asset_type="etf", asset_role="commentary_validation")
        seed_income_review(database_path, "AAPL")
        seed_linked_risk_and_outcome(database_path)
        write_positions_csv(
            config,
            [
                position_row("AAPL", close_date="2026-01-10", close_price=1.0),
                position_row("SOXL", position_id="soxl-1", strike=20, premium=1),
            ],
        )
        load_options_positions_csv(config)

        compute_options_lifecycle(config, ticker="AAPL")
        self.assertEqual(len(list_option_position_lifecycle_reviews(database_path, ticker="AAPL")), 1)
        self.assertEqual(len(list_option_position_lifecycle_reviews(database_path, ticker="SOXL")), 0)
        aapl = list_option_position_lifecycle_reviews(database_path, ticker="AAPL")[0]
        self.assertEqual(aapl.linked_option_income_review_id, 1)
        self.assertEqual(aapl.linked_option_risk_review_id, 1)
        self.assertEqual(aapl.linked_option_review_outcome_id, 1)

        compute_options_lifecycle(config, ticker="SOXL")
        soxl = list_option_position_lifecycle_reviews(database_path, ticker="SOXL")[0]
        self.assertIn("reference_instrument_only", soxl.risk_warnings or "")
        self.assertIn("unmatched_option_review", soxl.risk_warnings or "")
        self.assertEqual(count_scoreable_assets(database_path), 1)

    def test_cli_reports_csv_and_dashboard_include_phase12f_fields(self) -> None:
        database_path = fresh_database_path("phase12f_outputs.sqlite")
        config = make_config(database_path)
        write_config(config)
        initialize_database(database_path)
        seed_asset(database_path, "AAPL")
        seed_income_review(database_path, "AAPL")
        write_positions_csv(
            config,
            [position_row("AAPL", close_date="2026-01-10", close_price=0.5)],
        )
        load_options_positions_csv(config)

        compute_output = io.StringIO()
        with redirect_stdout(compute_output):
            self.assertEqual(
                command_compute_options_lifecycle(
                    Namespace(config=config.config_path, ticker="AAPL")
                ),
                0,
            )
        self.assertIn("AAPL: computed", compute_output.getvalue())

        status_output = io.StringIO()
        with redirect_stdout(status_output):
            self.assertEqual(command_options_lifecycle_status(Namespace(config=config.config_path)), 0)
        self.assertIn("Lifecycle rows: 1", status_output.getvalue())

        report_output = io.StringIO()
        with redirect_stdout(report_output):
            self.assertEqual(command_options_lifecycle_report(Namespace(config=config.config_path)), 0)
        self.assertIn("# Options Lifecycle Report", report_output.getvalue())

        options_output = io.StringIO()
        with redirect_stdout(options_output):
            self.assertEqual(command_options_status(Namespace(config=config.config_path)), 0)
        self.assertIn("Option lifecycle rows: 1", options_output.getvalue())

        status_text = io.StringIO()
        with redirect_stdout(status_text):
            self.assertEqual(command_status(Namespace(config=config.config_path)), 0)
        self.assertIn("Option lifecycle review rows: 1", status_text.getvalue())

        report = write_daily_report(config)
        csv_text = report.csv_path.read_text(encoding="utf-8") if report.csv_path else ""
        markdown = report.path.read_text(encoding="utf-8")
        self.assertIn("option_lifecycle_status", csv_text)
        self.assertIn("Option lifecycle review rows: `1`", markdown)

        dashboard = build_dashboard(config)
        data = dashboard_data(dashboard.path.read_text(encoding="utf-8"))
        self.assertEqual(data["health"]["option_position_lifecycle_review_rows"], 1)
        aapl = next(row for row in data["rows"] if row["ticker"] == "AAPL")
        self.assertEqual(aapl["option_lifecycle_status"], "closed")


if __name__ == "__main__":
    unittest.main()
