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
TEST_TMP_ROOT = PROJECT_ROOT / ".tmp_tests" / "phase12a"
sys.path.insert(0, str(SRC_PATH))

from target_opportunity_monitor.cli import command_options_status, command_status
from target_opportunity_monitor.config import AppConfig, load_config
from target_opportunity_monitor.dashboard import build_dashboard
from target_opportunity_monitor.db import REQUIRED_TABLES, initialize_database
from target_opportunity_monitor.options import (
    OPTIONS_CHAIN_HEADERS,
    compute_options_income,
    ensure_options_chain_csv_header,
    load_options_chain_csv,
    parse_options_chain_csv,
)
from target_opportunity_monitor.reporting import REPORT_CSV_COLUMNS, write_daily_report
from target_opportunity_monitor.storage import (
    Asset,
    PriceFeature,
    RangeSnapshot,
    TraderCommentaryClaim,
    count_rows_by_table,
    count_scoreable_assets,
    list_option_chain_snapshots,
    list_option_income_reviews,
    option_income_statuses,
    upsert_asset,
    upsert_price_feature,
    upsert_range_snapshot,
    upsert_trader_commentary_claim,
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
        config_path=TEST_TMP_ROOT / f"phase12a_{database_path.stem}.toml",
        database_path=database_path,
        reports_dir=TEST_TMP_ROOT / "reports_phase12a",
        watchlist_path=TEST_TMP_ROOT / "watchlist_phase12a.csv",
        market_data_dir=TEST_TMP_ROOT / "market_data_phase12a",
        manual_prices_dir=TEST_TMP_ROOT / "market_data_phase12a" / "manual",
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
                "default_min_dte = 7",
                "default_max_dte = 60",
                "min_annualized_premium_yield = 0.10",
                "min_open_interest = 100",
                "min_volume = 10",
                "assignment_buffer_pct = 0.10",
                "use_range_filter = true",
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


def write_options_csv(config: AppConfig, rows: list[dict[str, object]]) -> None:
    config.options_chain_path.parent.mkdir(parents=True, exist_ok=True)
    with config.options_chain_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=OPTIONS_CHAIN_HEADERS)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def option_row(
    ticker: str = "AAPL",
    *,
    strike: float = 90.0,
    bid: float = 1.8,
    ask: float = 2.2,
    mark: float | None = None,
    volume: float = 25,
    open_interest: float = 150,
    option_type: str = "put",
    expiration_days: int = 30,
    source: str = "fixture_chain",
) -> dict[str, object]:
    return {
        "ticker": ticker,
        "snapshot_timestamp": datetime.now().isoformat(timespec="seconds"),
        "expiration_date": (date.today() + timedelta(days=expiration_days)).isoformat(),
        "option_type": option_type,
        "strike": strike,
        "bid": bid,
        "ask": ask,
        "last": "",
        "mark": "" if mark is None else mark,
        "volume": volume,
        "open_interest": open_interest,
        "implied_volatility": 0.35,
        "delta": -0.25,
        "gamma": "",
        "theta": "",
        "vega": "",
        "source": source,
        "source_url": "https://example.com/options",
        "as_of_date": date.today().isoformat(),
        "effective_date": date.today().isoformat(),
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


class Phase12AOptionsTests(unittest.TestCase):
    def test_config_defaults_and_schema_include_options_tables(self) -> None:
        default_config = load_config(PROJECT_ROOT / "configs" / "default.toml")
        self.assertEqual(default_config.options_chain_path.name, "options_chain.csv")
        self.assertEqual(default_config.options_model_version, "options_sell_put_mvp_v1")
        self.assertIn("option_chain_snapshots", REQUIRED_TABLES)
        self.assertIn("option_income_reviews", REQUIRED_TABLES)

        database_path = fresh_database_path("phase12a_schema.sqlite")
        initialize_database(database_path)

        self.assertEqual(count_rows_by_table(database_path, "option_chain_snapshots"), 0)
        self.assertEqual(count_rows_by_table(database_path, "option_income_reviews"), 0)

    def test_default_options_chain_header_is_created(self) -> None:
        database_path = fresh_database_path("phase12a_header.sqlite")
        config = make_config(database_path)

        ensure_options_chain_csv_header(config.options_chain_path)

        self.assertTrue(config.options_chain_path.exists())
        self.assertEqual(
            config.options_chain_path.read_text(encoding="utf-8").strip(),
            ",".join(OPTIONS_CHAIN_HEADERS),
        )

    def test_loader_accepts_valid_rows_and_rejects_bad_rows(self) -> None:
        database_path = fresh_database_path("phase12a_loader.sqlite")
        config = make_config(database_path)
        initialize_database(database_path)
        seed_underlying(database_path)
        write_options_csv(config, [option_row()])

        result = load_options_chain_csv(config)
        second = load_options_chain_csv(config)

        self.assertEqual(result.loaded_count, 1)
        self.assertEqual(second.loaded_count, 1)
        self.assertEqual(len(list_option_chain_snapshots(database_path)), 1)

        bad_missing = ",".join(header for header in OPTIONS_CHAIN_HEADERS if header != "ask") + "\n"
        with self.assertRaisesRegex(ValueError, "missing required columns"):
            parse_options_chain_csv(bad_missing, config)

        bad_type = option_row(option_type="straddle")
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=OPTIONS_CHAIN_HEADERS)
        writer.writeheader()
        writer.writerow(bad_type)
        with self.assertRaisesRegex(ValueError, "unsupported option_type"):
            parse_options_chain_csv(output.getvalue(), config)

        bad_ticker = option_row(ticker="MISSING")
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=OPTIONS_CHAIN_HEADERS)
        writer.writeheader()
        writer.writerow(bad_ticker)
        with self.assertRaisesRegex(ValueError, "unsupported or inactive ticker"):
            parse_options_chain_csv(output.getvalue(), config)

    def test_sell_put_review_math_and_commentary_linking(self) -> None:
        database_path = fresh_database_path("phase12a_compute.sqlite")
        config = make_config(database_path)
        initialize_database(database_path)
        seed_underlying(database_path, current_price=100, range_level=95)
        upsert_trader_commentary_claim(
            database_path,
            TraderCommentaryClaim(
                claim_key="fixture:aapl:sell-put:90",
                claim_date=date.today().isoformat(),
                claim_type="options_income_idea",
                source="fixture",
                ticker="AAPL",
                strike_price=90,
                premium=2.0,
            ),
        )
        write_options_csv(config, [option_row(strike=90, bid=1.8, ask=2.2)])
        load_options_chain_csv(config)

        result = compute_options_income(config, ticker="AAPL")
        reviews = list_option_income_reviews(database_path, ticker="AAPL")

        self.assertEqual(result.computed_count, 1)
        self.assertEqual(len(reviews), 1)
        review = reviews[0]
        self.assertEqual(review.review_category, "eligible_watch")
        self.assertAlmostEqual(review.mid_premium or 0, 2.0)
        self.assertAlmostEqual(review.breakeven or 0, 88.0)
        self.assertAlmostEqual(review.premium_yield or 0, 2.0 / 90.0, places=6)
        self.assertGreater(review.annualized_yield or 0, 0.10)
        self.assertAlmostEqual(review.downside_buffer_pct or 0, (100 / 90) - 1, places=6)
        self.assertEqual(review.assignment_notional, 9000.0)
        self.assertEqual(review.commentary_claim_count, 1)

    def test_review_classifications_and_reference_instrument_boundary(self) -> None:
        database_path = fresh_database_path("phase12a_classifications.sqlite")
        config = make_config(database_path)
        initialize_database(database_path)
        seed_underlying(database_path, ticker="AAPL", current_price=100, range_level=95)
        seed_underlying(
            database_path,
            ticker="SOXL",
            asset_type="etf",
            asset_role="commentary_validation",
            current_price=40,
            range_level=35,
        )
        self.assertEqual(count_scoreable_assets(database_path), 1)
        write_options_csv(
            config,
            [
                option_row(ticker="AAPL", strike=90, volume=0, open_interest=5),
                option_row(ticker="AAPL", strike=99, source="fixture_chain_2"),
                option_row(ticker="SOXL", strike=35, bid=0.9, ask=1.1),
            ],
        )
        load_options_chain_csv(config)
        compute_options_income(config)

        reviews = list_option_income_reviews(database_path)
        by_ticker_strike = {(review.ticker, review.strike): review for review in reviews}

        self.assertEqual(by_ticker_strike[("AAPL", 90.0)].review_category, "illiquid_option")
        self.assertEqual(by_ticker_strike[("AAPL", 99.0)].review_category, "too_close_to_price")
        self.assertEqual(by_ticker_strike[("SOXL", 35.0)].review_category, "reference_only")
        self.assertEqual(count_scoreable_assets(database_path), 1)

    def test_cli_reports_csv_and_dashboard_expose_options_fields(self) -> None:
        database_path = fresh_database_path("phase12a_outputs.sqlite")
        config = make_config(database_path)
        write_config(config)
        initialize_database(database_path)
        seed_underlying(database_path)
        write_options_csv(config, [option_row()])
        load_options_chain_csv(config)
        compute_options_income(config)

        self.assertIn("option_review_category", REPORT_CSV_COLUMNS)
        report = write_daily_report(config)
        markdown = report.path.read_text(encoding="utf-8")
        csv_text = report.csv_path.read_text(encoding="utf-8") if report.csv_path else ""
        dashboard = build_dashboard(config)
        html = dashboard.path.read_text(encoding="utf-8")
        data = dashboard_data(html)
        aapl_row = next(row for row in data["rows"] if row["ticker"] == "AAPL")

        self.assertIn("Options/Sell-Put Advisory", markdown)
        self.assertIn("eligible_watch", csv_text)
        self.assertEqual(aapl_row["option_review_category"], "eligible_watch")
        self.assertEqual(data["health"]["option_chain_rows"], 1)
        self.assertIn("Sell-Put Review", html)

        status_output = io.StringIO()
        with redirect_stdout(status_output):
            self.assertEqual(command_status(Namespace(config=config.config_path)), 0)
        self.assertIn("Options chain rows: 1", status_output.getvalue())

        options_output = io.StringIO()
        with redirect_stdout(options_output):
            self.assertEqual(command_options_status(Namespace(config=config.config_path)), 0)
        self.assertIn("Options/Sell-Put Advisory Status", options_output.getvalue())
        self.assertIn("eligible_watch", options_output.getvalue())


if __name__ == "__main__":
    unittest.main()
