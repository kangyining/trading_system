from __future__ import annotations

from argparse import Namespace
from contextlib import redirect_stdout
import csv
from datetime import date, datetime, timedelta
from pathlib import Path
import io
import json
import re
import sys
import unittest
from unittest.mock import patch


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
TEST_TMP_ROOT = PROJECT_ROOT / ".tmp_tests" / "phase12b"
sys.path.insert(0, str(SRC_PATH))

from target_opportunity_monitor.cli import (
    command_activate_options_chain_data,
    command_apply_options_chain_coverage_backfill,
    command_export_options_chain_backfill_template,
    command_export_options_chain_missing_template,
    command_fetch_options_chain,
    command_import_options_chain_source_exports,
    command_option_chain_activation_status,
    command_option_chain_coverage_plan,
    command_option_chain_minimum_backfill_plan,
    command_option_chain_status,
    command_option_provider_status,
    command_option_provider_repair_plan,
    command_status,
    command_test_options_provider,
    command_validate_options_chain_backfill,
)
from target_opportunity_monitor.account import account_context_status
from target_opportunity_monitor.config import AppConfig, load_config
from target_opportunity_monitor.dashboard import build_dashboard
from target_opportunity_monitor.db import initialize_database
from target_opportunity_monitor.ibkr_provider import (
    IbkrOptionChainFetchResult,
    IbkrOptionChainTickerResult,
)
from target_opportunity_monitor.options import (
    OPTIONS_CHAIN_NON_ACTIONABLE_HEADERS,
    activate_options_chain_data,
    apply_options_chain_coverage_backfill,
    compute_options_income,
    export_options_chain_missing_template,
    export_options_chain_backfill_template,
    fetch_options_chain,
    import_options_chain_source_exports,
    option_chain_availability_statuses,
    option_chain_activation_status,
    option_chain_coverage_plan,
    option_fetch_assets,
    option_provider_status,
    select_option_expirations,
    select_option_strikes,
    validate_option_chain_non_actionable_decisions,
    validate_options_chain_backfill,
)
from target_opportunity_monitor.reporting import REPORT_CSV_COLUMNS, write_daily_report
from target_opportunity_monitor.pipeline import run_intraday_cycle
from target_opportunity_monitor.storage import (
    Asset,
    OptionChainSnapshot,
    PriceFeature,
    RangeSnapshot,
    TraderCommentaryClaim,
    count_scoreable_assets,
    list_option_chain_snapshots,
    list_option_income_reviews,
    list_option_review_outcomes,
    list_option_risk_reviews,
    upsert_asset,
    upsert_option_chain_snapshot,
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
        config_path=TEST_TMP_ROOT / f"{database_path.stem}.toml",
        database_path=database_path,
        reports_dir=TEST_TMP_ROOT / "reports_phase12b",
        watchlist_path=TEST_TMP_ROOT / "watchlist_phase12b.csv",
        market_data_dir=TEST_TMP_ROOT / "market_data_phase12b",
        manual_prices_dir=TEST_TMP_ROOT / "market_data_phase12b" / "manual",
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
        options_chain_source_exports_dir=TEST_TMP_ROOT
        / "options"
        / "source_exports"
        / database_path.stem,
        options_chain_cache_dir=TEST_TMP_ROOT / "options" / "cache" / database_path.stem,
        account_source_exports_dir=TEST_TMP_ROOT
        / "account"
        / "source_exports"
        / database_path.stem,
        portfolio_positions_path=TEST_TMP_ROOT
        / "portfolio"
        / f"{database_path.stem}_positions.csv",
        portfolio_cash_path=TEST_TMP_ROOT
        / "portfolio"
        / f"{database_path.stem}_cash.csv",
        options_positions_path=TEST_TMP_ROOT
        / "options"
        / "manual"
        / f"{database_path.stem}_options_positions.csv",
        options_model_version="options_sell_put_mvp_v1",
        options_default_min_dte=7,
        options_default_max_dte=60,
        options_min_annualized_premium_yield=0.10,
        options_min_open_interest=100,
        options_min_volume=10,
        options_assignment_buffer_pct=0.10,
        options_use_range_filter=True,
        options_chain_source="ibkr",
        options_option_fetch_universe="scoreable_plus_commentary_options",
        options_ibkr_exchange="SMART",
        options_ibkr_currency="USD",
        options_chain_stale_after_minutes=30,
        options_max_expirations_per_ticker=2,
        options_max_strikes_per_expiration=3,
        options_strike_window_pct=0.30,
        options_fetch_puts_only=True,
        options_auto_fetch_daily=True,
        options_auto_fetch_intraday=False,
        options_max_tickers_per_run=2,
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
                f'options_chain_source_exports = "{config.options_chain_source_exports_dir.as_posix()}"',
                f'options_chain_cache = "{config.options_chain_cache_dir.as_posix()}"',
                "",
                "[options]",
                'chain_source = "ibkr"',
                'option_fetch_universe = "scoreable_plus_commentary_options"',
                "chain_stale_after_minutes = 30",
                "max_expirations_per_ticker = 2",
                "max_strikes_per_expiration = 3",
                "strike_window_pct = 0.30",
                "fetch_puts_only = true",
                "auto_fetch_daily = true",
                "auto_fetch_intraday = false",
                "max_tickers_per_run = 2",
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


def seed_underlying(
    database_path: Path,
    ticker: str,
    *,
    asset_type: str = "equity",
    asset_role: str = "scoreable",
    current_price: float = 100.0,
    range_level: float = 90.0,
) -> None:
    now = datetime.now().isoformat(timespec="seconds")
    today = date.today().isoformat()
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


def option_snapshot(ticker: str = "SOXL", strike: float = 35.0) -> OptionChainSnapshot:
    timestamp = datetime.now().isoformat(timespec="seconds")
    return OptionChainSnapshot(
        ticker=ticker,
        snapshot_timestamp=timestamp,
        expiration_date=(date.today() + timedelta(days=30)).isoformat(),
        option_type="put",
        strike=strike,
        bid=0.9,
        ask=1.1,
        mark=1.0,
        volume=50,
        open_interest=250,
        implied_volatility=0.45,
        delta=-0.20,
        source="ibkr_option_chain",
        as_of_date=date.today().isoformat(),
        effective_date=timestamp,
    )


PHASE12E_SCOREABLE_TICKERS = (
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
    "QQQ",
    "SPY",
)

PHASE12E_MISSING_TICKERS = (
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
    "QQQ",
    "SPY",
)


def seed_phase12e_option_universe(database_path: Path) -> None:
    for ticker in PHASE12E_SCOREABLE_TICKERS:
        seed_underlying(
            database_path,
            ticker,
            asset_type="etf" if ticker in {"QQQ", "SPY"} else "equity",
        )
    for ticker in ("SOXL", "KORU"):
        seed_underlying(
            database_path,
            ticker,
            asset_type="etf",
            asset_role="commentary_validation",
            current_price=40,
            range_level=35,
        )
        upsert_trader_commentary_claim(
            database_path,
            TraderCommentaryClaim(
                claim_key=f"fixture:{ticker.lower()}:sell-put",
                claim_date=date.today().isoformat(),
                claim_type="options_income_idea",
                source="fixture",
                ticker=ticker,
                strike_price=35,
                premium=1.0,
            ),
        )
    for ticker, strike in (("AAPL", 90.0), ("SOXL", 35.0), ("KORU", 35.0)):
        upsert_option_chain_snapshot(
            database_path,
            option_snapshot(ticker=ticker, strike=strike),
        )


def write_valid_options_backfill_row(
    path: Path,
    ticker: str,
    *,
    strike: float = 90.0,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(option_snapshot().__dict__.keys()))
        writer.writeheader()
        writer.writerow(
            {
                "ticker": ticker,
                "snapshot_timestamp": datetime.now().isoformat(timespec="seconds"),
                "expiration_date": (date.today() + timedelta(days=30)).isoformat(),
                "option_type": "put",
                "strike": f"{strike:.2f}",
                "bid": "0.90",
                "ask": "1.10",
                "mark": "1.00",
                "volume": "50",
                "open_interest": "250",
                "source": "broker_export",
                "source_url": f"https://example.com/options/{ticker.lower()}",
                "as_of_date": date.today().isoformat(),
                "effective_date": date.today().isoformat(),
            }
        )


def write_non_actionable_decision_rows(
    path: Path,
    rows: list[dict[str, str]],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=OPTIONS_CHAIN_NON_ACTIONABLE_HEADERS)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def dashboard_data(html: str) -> dict[str, object]:
    match = re.search(
        r'<script id="tom-dashboard-data" type="application/json">(.*?)</script>',
        html,
        flags=re.DOTALL,
    )
    if not match:
        raise AssertionError("Dashboard data script not found.")
    return json.loads(match.group(1))


class Phase12BOptionsChainTests(unittest.TestCase):
    def test_config_defaults_load_phase12b_provider_fields(self) -> None:
        config = load_config(PROJECT_ROOT / "configs" / "default.toml")

        self.assertEqual(config.options_chain_cache_dir.name, "chains")
        self.assertEqual(config.options_chain_source_exports_dir.name, "source_exports")
        self.assertEqual(config.options_chain_source, "auto")
        self.assertEqual(
            config.options_option_fetch_universe,
            "scoreable_plus_commentary_options",
        )
        self.assertEqual(config.options_ibkr_exchange, "SMART")
        self.assertTrue(config.options_fetch_puts_only)
        self.assertTrue(config.options_auto_fetch_daily)
        self.assertFalse(config.options_auto_fetch_intraday)

    def test_option_provider_status_classifies_ibapi_permission_error(self) -> None:
        database_path = fresh_database_path("phase12b1_provider_status.sqlite")
        config = make_config(database_path)
        write_config(config)
        initialize_database(database_path)
        seed_underlying(database_path, "SOXL", asset_role="commentary_validation")

        with patch(
            "target_opportunity_monitor.ibkr_provider._import_ibapi",
            return_value=(None, None, None, "Permission denied: ibapi"),
        ):
            status = option_provider_status(config, check_connectivity=True)
            output = io.StringIO()
            with redirect_stdout(output):
                exit_code = command_option_provider_status(
                    Namespace(config=config.config_path, check_connectivity=True)
                )

        self.assertEqual(exit_code, 0)
        self.assertEqual(status.ibapi_status, "ibapi_permission_denied")
        self.assertEqual(status.blocked_reason, "ibapi_permission_denied")
        self.assertIn("ibapi_permission_denied", output.getvalue())

    def test_phase12b2_activation_status_and_repair_plan_report_ibapi_permission(self) -> None:
        database_path = fresh_database_path("phase12b2_activation_permission.sqlite")
        config = make_config(database_path)
        write_config(config)
        initialize_database(database_path)
        seed_underlying(database_path, "SOXL", asset_role="commentary_validation")
        seed_underlying(database_path, "KORU", asset_role="commentary_validation")
        seed_underlying(database_path, "AAPL")

        with patch(
            "target_opportunity_monitor.ibkr_provider._import_ibapi",
            return_value=(None, None, None, "Permission denied: ibapi"),
        ):
            status = option_chain_activation_status(config)
            activation_output = io.StringIO()
            with redirect_stdout(activation_output):
                activation_exit = command_option_chain_activation_status(
                    Namespace(config=config.config_path)
                )
            repair_output = io.StringIO()
            with redirect_stdout(repair_output):
                repair_exit = command_option_provider_repair_plan(
                    Namespace(config=config.config_path, source="ibkr")
                )

        self.assertEqual(activation_exit, 0)
        self.assertEqual(repair_exit, 0)
        self.assertEqual(status.activation_status, "blocked")
        self.assertTrue(status.ibapi_repair_needed)
        self.assertEqual(status.minimum_option_chain_coverage, "0/3")
        self.assertIn("ibapi_permission_denied", activation_output.getvalue())
        self.assertIn("diagnostic only", repair_output.getvalue())
        self.assertIn("Permission denied: ibapi", repair_output.getvalue())

    def test_phase12b2_minimum_backfill_template_and_validation_summary(self) -> None:
        database_path = fresh_database_path("phase12b2_minimum_template.sqlite")
        config = make_config(database_path)
        write_config(config)
        initialize_database(database_path)
        seed_underlying(database_path, "SOXL", asset_role="commentary_validation")
        seed_underlying(database_path, "KORU", asset_role="commentary_validation")
        seed_underlying(database_path, "AAPL")
        seed_underlying(database_path, "MSFT")

        output = io.StringIO()
        with redirect_stdout(output):
            exit_code = command_export_options_chain_backfill_template(
                Namespace(config=config.config_path, ticker=None, minimum_set=True)
            )
        validation_output = io.StringIO()
        with redirect_stdout(validation_output):
            validation_exit = command_validate_options_chain_backfill(
                Namespace(config=config.config_path, dir=None)
            )
        plan_output = io.StringIO()
        with redirect_stdout(plan_output):
            plan_exit = command_option_chain_minimum_backfill_plan(
                Namespace(config=config.config_path)
            )

        self.assertEqual(exit_code, 0)
        self.assertEqual(validation_exit, 0)
        self.assertEqual(plan_exit, 0)
        self.assertIn("SOXL, KORU, AAPL", output.getvalue())
        rows = list(
            csv.DictReader(
                (config.options_chain_source_exports_dir / "options_chain_backfill_minimum_set.csv")
                .read_text(encoding="utf-8")
                .splitlines()
            )
        )
        self.assertEqual([row["ticker"] for row in rows], ["SOXL", "KORU", "AAPL"])
        self.assertIn("Minimum projected chain coverage: 0/3", validation_output.getvalue())
        self.assertIn("Minimum tickers: SOXL, KORU, AAPL", plan_output.getvalue())

    def test_phase12b2_activate_dry_run_does_not_mutate_and_confirm_allows_partial(self) -> None:
        database_path = fresh_database_path("phase12b2_activate_partial.sqlite")
        config = make_config(database_path)
        write_config(config)
        initialize_database(database_path)
        seed_underlying(
            database_path,
            "SOXL",
            asset_type="etf",
            asset_role="commentary_validation",
            current_price=40,
            range_level=35,
        )
        seed_underlying(database_path, "KORU", asset_type="etf", asset_role="commentary_validation")
        seed_underlying(database_path, "AAPL")
        export_options_chain_backfill_template(config, minimum_set=True)
        backfill_path = config.options_chain_source_exports_dir / "options_chain_backfill_minimum_set.csv"
        with backfill_path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(option_snapshot().__dict__.keys()))
            writer.writeheader()
            writer.writerow(
                {
                    "ticker": "SOXL",
                    "snapshot_timestamp": datetime.now().isoformat(timespec="seconds"),
                    "expiration_date": (date.today() + timedelta(days=30)).isoformat(),
                    "option_type": "put",
                    "strike": "35",
                    "bid": "0.90",
                    "ask": "1.10",
                    "mark": "1.00",
                    "volume": "50",
                    "open_interest": "250",
                    "source": "broker_export",
                    "source_url": "https://example.com/options/soxl",
                    "as_of_date": date.today().isoformat(),
                    "effective_date": date.today().isoformat(),
                }
            )

        dry_run = activate_options_chain_data(config, allow_partial=True)
        self.assertEqual(dry_run.status, "dry_run_ready")
        self.assertEqual(len(list_option_chain_snapshots(database_path, ticker="SOXL")), 0)

        blocked_full = activate_options_chain_data(config, confirm=True)
        self.assertFalse(blocked_full.success)
        self.assertEqual(blocked_full.blocked_reason, "minimum_option_chain_coverage_incomplete")

        confirmed = activate_options_chain_data(
            config,
            confirm=True,
            allow_partial=True,
        )
        reviews = list_option_income_reviews(database_path, ticker="SOXL")

        self.assertTrue(confirmed.success)
        self.assertEqual(confirmed.imported_count, 1)
        self.assertGreaterEqual(confirmed.minimum_option_review_count, 1)
        self.assertEqual(len(list_option_chain_snapshots(database_path, ticker="SOXL")), 1)
        self.assertEqual(len(reviews), 1)

    def test_phase12b2_activate_command_blocks_confirm_with_no_valid_rows(self) -> None:
        database_path = fresh_database_path("phase12b2_activate_empty.sqlite")
        config = make_config(database_path)
        write_config(config)
        initialize_database(database_path)
        seed_underlying(database_path, "SOXL", asset_role="commentary_validation")
        seed_underlying(database_path, "KORU", asset_role="commentary_validation")
        seed_underlying(database_path, "AAPL")
        export_options_chain_backfill_template(config, minimum_set=True)

        dry_run_output = io.StringIO()
        with redirect_stdout(dry_run_output):
            dry_run_exit = command_activate_options_chain_data(
                Namespace(
                    config=config.config_path,
                    confirm=False,
                    allow_partial=False,
                    dir=None,
                )
            )
        confirm_output = io.StringIO()
        with redirect_stdout(confirm_output):
            confirm_exit = command_activate_options_chain_data(
                Namespace(
                    config=config.config_path,
                    confirm=True,
                    allow_partial=True,
                    dir=None,
                )
            )

        self.assertEqual(dry_run_exit, 0)
        self.assertEqual(confirm_exit, 1)
        self.assertIn("Dry run only", dry_run_output.getvalue())
        self.assertIn("no_valid_option_backfill_rows", confirm_output.getvalue())

    def test_options_backfill_template_validation_and_import_flow(self) -> None:
        database_path = fresh_database_path("phase12b1_backfill.sqlite")
        config = make_config(database_path)
        write_config(config)
        initialize_database(database_path)
        seed_underlying(
            database_path,
            "SOXL",
            asset_type="etf",
            asset_role="commentary_validation",
            current_price=40,
            range_level=35,
        )
        upsert_trader_commentary_claim(
            database_path,
            TraderCommentaryClaim(
                claim_key="fixture:soxl:backfill",
                claim_date=date.today().isoformat(),
                claim_type="options_income_idea",
                source="fixture",
                ticker="SOXL",
                strike_price=35,
                premium=1.0,
            ),
        )

        export_result = export_options_chain_backfill_template(config, ticker="SOXL")
        placeholder_validation = validate_options_chain_backfill(config)

        self.assertTrue(export_result.path.exists())
        self.assertEqual(export_result.tickers, ("SOXL",))
        self.assertEqual(placeholder_validation.blank_placeholder_count, 1)
        self.assertEqual(placeholder_validation.valid_row_count, 0)

        with export_result.path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(option_snapshot().__dict__.keys()))
            writer.writeheader()
            writer.writerow(
                {
                    "ticker": "SOXL",
                    "snapshot_timestamp": datetime.now().isoformat(timespec="seconds"),
                    "expiration_date": (date.today() + timedelta(days=30)).isoformat(),
                    "option_type": "put",
                    "strike": "35",
                    "bid": "0.90",
                    "ask": "1.10",
                    "mark": "1.00",
                    "volume": "50",
                    "open_interest": "250",
                    "source": "broker_export",
                    "source_url": "https://example.com/options/soxl",
                    "as_of_date": date.today().isoformat(),
                    "effective_date": date.today().isoformat(),
                }
            )

        validation = validate_options_chain_backfill(config)
        import_result = import_options_chain_source_exports(config)
        reviews_result = compute_options_income(config, ticker="SOXL")

        self.assertTrue(validation.apply_ready)
        self.assertEqual(validation.valid_tickers, ("SOXL",))
        self.assertEqual(import_result.imported_count, 1)
        self.assertEqual(reviews_result.computed_count, 1)
        self.assertEqual(len(list_option_chain_snapshots(database_path, ticker="SOXL")), 1)

    def test_invalid_backfill_rows_block_import_command(self) -> None:
        database_path = fresh_database_path("phase12b1_invalid_backfill.sqlite")
        config = make_config(database_path)
        write_config(config)
        initialize_database(database_path)
        seed_underlying(database_path, "SOXL", asset_role="commentary_validation")
        config.options_chain_source_exports_dir.mkdir(parents=True, exist_ok=True)
        bad_path = config.options_chain_source_exports_dir / "bad_options.csv"
        with bad_path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(option_snapshot().__dict__.keys()))
            writer.writeheader()
            writer.writerow(
                {
                    "ticker": "SOXL",
                    "snapshot_timestamp": datetime.now().isoformat(timespec="seconds"),
                    "expiration_date": (date.today() + timedelta(days=30)).isoformat(),
                    "option_type": "put",
                    "strike": "35",
                    "bid": "1.10",
                    "ask": "0.90",
                    "source": "broker_export",
                    "source_url": "",
                }
            )

        output = io.StringIO()
        with redirect_stdout(output):
            validate_exit = command_validate_options_chain_backfill(
                Namespace(config=config.config_path, dir=None)
            )
        with redirect_stdout(io.StringIO()):
            import_exit = command_import_options_chain_source_exports(
                Namespace(config=config.config_path, dir=None)
            )

        self.assertEqual(validate_exit, 1)
        self.assertEqual(import_exit, 1)
        self.assertIn("missing required source_url", output.getvalue())

    def test_export_options_backfill_template_command_supports_ticker_filter(self) -> None:
        database_path = fresh_database_path("phase12b1_export_command.sqlite")
        config = make_config(database_path)
        write_config(config)
        initialize_database(database_path)
        seed_underlying(database_path, "SOXL", asset_role="commentary_validation")
        seed_underlying(database_path, "AAPL")

        output = io.StringIO()
        with redirect_stdout(output):
            exit_code = command_export_options_chain_backfill_template(
                Namespace(config=config.config_path, ticker="SOXL")
            )

        self.assertEqual(exit_code, 0)
        self.assertIn("SOXL", output.getvalue())
        rows = list(
            csv.DictReader(
                (config.options_chain_source_exports_dir / "options_chain_backfill_soxl.csv")
                .read_text(encoding="utf-8")
                .splitlines()
            )
        )
        self.assertEqual([row["ticker"] for row in rows], ["SOXL"])

    def test_test_options_provider_command_reports_bounded_fetch_warnings(self) -> None:
        database_path = fresh_database_path("phase12b1_test_provider.sqlite")
        config = make_config(database_path)
        write_config(config)
        initialize_database(database_path)
        seed_underlying(database_path, "SOXL", asset_role="commentary_validation")
        warning_result = IbkrOptionChainFetchResult(
            results=(
                IbkrOptionChainTickerResult(
                    ticker="SOXL",
                    status="warning",
                    rows_loaded=0,
                    selected_expirations=0,
                    selected_strikes=0,
                    snapshots=(),
                    warnings=("ibkr_option_subscription_missing:354:not subscribed",),
                ),
            )
        )

        output = io.StringIO()
        with patch(
            "target_opportunity_monitor.ibkr_provider.fetch_ibkr_option_chain_snapshots",
            return_value=warning_result,
        ), redirect_stdout(output):
            exit_code = command_test_options_provider(
                Namespace(config=config.config_path, source="ibkr", ticker="SOXL")
            )

        self.assertEqual(exit_code, 0)
        self.assertIn("Option Provider Test", output.getvalue())
        self.assertIn("ibkr_option_subscription_missing", output.getvalue())

    def test_expiration_and_strike_filters_are_bounded(self) -> None:
        config = make_config(fresh_database_path("phase12b_filters.sqlite"))
        expirations = (
            (date.today() + timedelta(days=3)).strftime("%Y%m%d"),
            (date.today() + timedelta(days=14)).strftime("%Y%m%d"),
            (date.today() + timedelta(days=30)).strftime("%Y%m%d"),
            (date.today() + timedelta(days=45)).strftime("%Y%m%d"),
        )
        strikes = (50, 70, 75, 80, 85, 90, 95, 100, 105)

        self.assertEqual(len(select_option_expirations(expirations, config)), 2)
        selected = select_option_strikes(strikes, 100.0, config, range_level=85.0)

        self.assertEqual(len(selected), 3)
        self.assertTrue(all(70 <= strike <= 100 for strike in selected))
        self.assertIn(85.0, selected)

    def test_fetch_universe_prioritizes_commentary_option_reference_tickers(self) -> None:
        database_path = fresh_database_path("phase12b_universe.sqlite")
        config = make_config(database_path)
        initialize_database(database_path)
        seed_underlying(database_path, "AAPL")
        seed_underlying(database_path, "MSFT")
        seed_underlying(
            database_path,
            "SOXL",
            asset_type="etf",
            asset_role="commentary_validation",
            current_price=40,
            range_level=35,
        )
        upsert_trader_commentary_claim(
            database_path,
            TraderCommentaryClaim(
                claim_key="fixture:soxl:sell-put",
                claim_date=date.today().isoformat(),
                claim_type="options_income_idea",
                source="fixture",
                ticker="SOXL",
                strike_price=35,
                premium=1.0,
            ),
        )

        selected = option_fetch_assets(config, max_tickers=2)

        self.assertEqual([asset.ticker for asset in selected], ["SOXL", "AAPL"])
        self.assertEqual(count_scoreable_assets(database_path), 2)

    def test_mocked_ibkr_fetch_stores_chain_rows_and_reviews_reference_options(self) -> None:
        database_path = fresh_database_path("phase12b_ibkr_fetch.sqlite")
        config = make_config(database_path)
        initialize_database(database_path)
        seed_underlying(
            database_path,
            "SOXL",
            asset_type="etf",
            asset_role="commentary_validation",
            current_price=40,
            range_level=35,
        )
        mocked_result = IbkrOptionChainFetchResult(
            results=(
                IbkrOptionChainTickerResult(
                    ticker="SOXL",
                    status="loaded",
                    rows_loaded=1,
                    selected_expirations=1,
                    selected_strikes=1,
                    snapshots=(option_snapshot("SOXL", 35),),
                    warnings=(),
                ),
            )
        )

        with patch(
            "target_opportunity_monitor.ibkr_provider.fetch_ibkr_option_chain_snapshots",
            return_value=mocked_result,
        ) as mocked_fetch:
            result = fetch_options_chain(
                config,
                source="ibkr",
                ticker="SOXL",
                force_refresh=True,
            )

        reviews_result = compute_options_income(config, ticker="SOXL")
        snapshots = list_option_chain_snapshots(database_path, ticker="SOXL")
        reviews = list_option_income_reviews(database_path, ticker="SOXL")

        self.assertEqual(result.loaded_count, 1)
        self.assertEqual(snapshots[0].source, "ibkr_option_chain")
        self.assertEqual(reviews_result.computed_count, 1)
        self.assertEqual(reviews[0].review_category, "reference_only")
        self.assertEqual(count_scoreable_assets(database_path), 0)
        mocked_fetch.assert_called_once()

    def test_cached_chain_skips_live_fetch_unless_forced(self) -> None:
        database_path = fresh_database_path("phase12b_cache.sqlite")
        config = make_config(database_path)
        initialize_database(database_path)
        seed_underlying(database_path, "AAPL")
        first_result = IbkrOptionChainFetchResult(
            results=(
                IbkrOptionChainTickerResult(
                    ticker="AAPL",
                    status="loaded",
                    rows_loaded=1,
                    selected_expirations=1,
                    selected_strikes=1,
                    snapshots=(option_snapshot("AAPL", 90),),
                    warnings=(),
                ),
            )
        )

        with patch(
            "target_opportunity_monitor.ibkr_provider.fetch_ibkr_option_chain_snapshots",
            return_value=first_result,
        ):
            fetch_options_chain(config, source="ibkr", ticker="AAPL", force_refresh=True)

        with patch(
            "target_opportunity_monitor.ibkr_provider.fetch_ibkr_option_chain_snapshots"
        ) as mocked_fetch:
            second = fetch_options_chain(config, source="ibkr", ticker="AAPL")

        self.assertEqual(second.results[0].status, "cached")
        self.assertIn("fresh_cached_chain", second.results[0].warnings)
        mocked_fetch.assert_not_called()

    def test_yfinance_fetch_stages_valid_provider_rows_and_imports_snapshots(self) -> None:
        database_path = fresh_database_path("phase12e1_yfinance_fetch.sqlite")
        config = make_config(database_path)
        initialize_database(database_path)
        seed_phase12e_option_universe(database_path)
        expiration = (date.today() + timedelta(days=30)).isoformat()

        class FakeFrame:
            def to_dict(self, _orient: str) -> list[dict[str, object]]:
                return [
                    {
                        "strike": 90.0,
                        "bid": 0.9,
                        "ask": 1.1,
                        "lastPrice": 1.0,
                        "volume": 25,
                        "openInterest": 250,
                        "impliedVolatility": 0.42,
                        "delta": -0.2,
                    }
                ]

        class FakeChain:
            puts = FakeFrame()

        class FakeTicker:
            options = (expiration,)

            def __init__(self, _symbol: str) -> None:
                pass

            def option_chain(self, _expiration: str) -> FakeChain:
                return FakeChain()

        class FakeYFinance:
            Ticker = FakeTicker

            @staticmethod
            def set_tz_cache_location(_path: str) -> None:
                return None

        with patch.dict("sys.modules", {"yfinance": FakeYFinance}):
            result = fetch_options_chain(
                config,
                source="yfinance",
                ticker="MSFT",
                force_refresh=True,
            )

        snapshots = list_option_chain_snapshots(database_path, ticker="MSFT")
        validation = validate_options_chain_backfill(config)

        self.assertEqual(result.source, "yfinance")
        self.assertEqual(result.loaded_count, 1)
        self.assertEqual(len(snapshots), 1)
        self.assertEqual(snapshots[0].source, "yfinance_option_chain")
        self.assertIn("MSFT", validation.valid_tickers)
        self.assertTrue((config.options_chain_cache_dir / "yfinance").exists())

    def test_yfinance_fetch_imports_etf_calls_for_strategy_without_income_reviews(self) -> None:
        database_path = fresh_database_path("phase12e1_yfinance_etf_calls.sqlite")
        config = make_config(database_path)
        initialize_database(database_path)
        seed_underlying(database_path, "XLV", asset_type="etf", current_price=100.0, range_level=92.0)
        expiration = (date.today() + timedelta(days=30)).isoformat()

        class FakePutFrame:
            def to_dict(self, _orient: str) -> list[dict[str, object]]:
                return [
                    {
                        "strike": 90.0,
                        "bid": 0.9,
                        "ask": 1.1,
                        "lastPrice": 1.0,
                        "volume": 25,
                        "openInterest": 250,
                        "impliedVolatility": 0.42,
                        "delta": -0.2,
                    }
                ]

        class FakeCallFrame:
            def to_dict(self, _orient: str) -> list[dict[str, object]]:
                return [
                    {
                        "strike": 105.0,
                        "bid": 2.4,
                        "ask": 2.6,
                        "lastPrice": 2.5,
                        "volume": 30,
                        "openInterest": 300,
                        "impliedVolatility": 0.40,
                        "delta": 0.45,
                    }
                ]

        class FakeChain:
            puts = FakePutFrame()
            calls = FakeCallFrame()

        class FakeTicker:
            options = (expiration,)

            def __init__(self, _symbol: str) -> None:
                pass

            def option_chain(self, _expiration: str) -> FakeChain:
                return FakeChain()

        class FakeYFinance:
            Ticker = FakeTicker

            @staticmethod
            def set_tz_cache_location(_path: str) -> None:
                return None

        with patch.dict("sys.modules", {"yfinance": FakeYFinance}):
            result = fetch_options_chain(
                config,
                source="yfinance",
                ticker="XLV",
                force_refresh=True,
            )

        reviews_result = compute_options_income(config, ticker="XLV")
        snapshots = list_option_chain_snapshots(database_path, ticker="XLV")
        reviews = list_option_income_reviews(database_path, ticker="XLV")

        self.assertEqual(result.loaded_count, 2)
        self.assertEqual({snapshot.option_type for snapshot in snapshots}, {"call", "put"})
        self.assertEqual(reviews_result.computed_count, 1)
        self.assertEqual(len(reviews), 1)
        self.assertEqual(reviews[0].option_type, "put")

    def test_auto_fetch_falls_back_to_yfinance_after_ibkr_zero_rows(self) -> None:
        database_path = fresh_database_path("phase12e1_auto_fallback.sqlite")
        config = make_config(database_path)
        initialize_database(database_path)
        seed_phase12e_option_universe(database_path)
        expiration = (date.today() + timedelta(days=30)).isoformat()

        class FakeFrame:
            def to_dict(self, _orient: str) -> list[dict[str, object]]:
                return [
                    {
                        "strike": 90.0,
                        "bid": 0.8,
                        "ask": 1.0,
                        "lastPrice": 0.9,
                        "volume": 12,
                        "openInterest": 120,
                    }
                ]

        class FakeChain:
            puts = FakeFrame()

        class FakeTicker:
            options = (expiration,)

            def __init__(self, _symbol: str) -> None:
                pass

            def option_chain(self, _expiration: str) -> FakeChain:
                return FakeChain()

        class FakeYFinance:
            Ticker = FakeTicker

            @staticmethod
            def set_tz_cache_location(_path: str) -> None:
                return None

        ibkr_empty = IbkrOptionChainFetchResult(
            results=(
                IbkrOptionChainTickerResult(
                    ticker="MSFT",
                    status="warning",
                    rows_loaded=0,
                    selected_expirations=0,
                    selected_strikes=0,
                    snapshots=(),
                    warnings=("missing_chain",),
                ),
            )
        )

        with patch(
            "target_opportunity_monitor.ibkr_provider.fetch_ibkr_option_chain_snapshots",
            return_value=ibkr_empty,
        ), patch.dict("sys.modules", {"yfinance": FakeYFinance}):
            result = fetch_options_chain(
                config,
                source="auto",
                ticker="MSFT",
                force_refresh=True,
            )

        snapshots = list_option_chain_snapshots(database_path, ticker="MSFT")

        self.assertEqual(result.source, "auto")
        self.assertEqual(result.loaded_count, 1)
        self.assertEqual(len(snapshots), 1)
        self.assertEqual(snapshots[0].source, "yfinance_option_chain")

    def test_provider_warnings_do_not_fail_fetch_command(self) -> None:
        database_path = fresh_database_path("phase12b_warnings.sqlite")
        config = make_config(database_path)
        write_config(config)
        initialize_database(database_path)
        seed_underlying(database_path, "SOXL", asset_role="commentary_validation")
        warning_result = IbkrOptionChainFetchResult(
            results=(
                IbkrOptionChainTickerResult(
                    ticker="SOXL",
                    status="warning",
                    rows_loaded=0,
                    selected_expirations=0,
                    selected_strikes=0,
                    snapshots=(),
                    warnings=("ibkr_unavailable",),
                ),
            )
        )

        output = io.StringIO()
        with patch(
            "target_opportunity_monitor.ibkr_provider.fetch_ibkr_option_chain_snapshots",
            return_value=warning_result,
        ), redirect_stdout(output):
            exit_code = command_fetch_options_chain(
                Namespace(
                    config=config.config_path,
                    source="ibkr",
                    ticker="SOXL",
                    max_tickers=None,
                    force_refresh=True,
                )
            )

        self.assertEqual(exit_code, 0)
        self.assertIn("ibkr_unavailable", output.getvalue())
    def test_option_chain_status_reports_provider_coverage_and_dashboard_health(self) -> None:
        database_path = fresh_database_path("phase12b_status.sqlite")
        config = make_config(database_path)
        write_config(config)
        initialize_database(database_path)
        seed_underlying(database_path, "AAPL")
        seed_underlying(database_path, "MSFT")

        output = io.StringIO()
        with redirect_stdout(output):
            self.assertEqual(command_option_chain_status(Namespace(config=config.config_path)), 0)
        self.assertIn("Option Chain Provider Status", output.getvalue())
        self.assertIn("Missing chain tickers: AAPL, MSFT", output.getvalue())

        with patch(
            "target_opportunity_monitor.ibkr_provider._import_ibapi",
            return_value=(object, object, object, None),
        ):
            dashboard = build_dashboard(config)
        data = dashboard_data(dashboard.path.read_text(encoding="utf-8"))
        self.assertEqual(data["health"]["option_chain_source"], "ibkr")
        self.assertEqual(data["health"]["option_chain_fetch_universe_ticker_count"], 2)
        self.assertEqual(data["health"]["option_chain_missing_tickers"], ["AAPL", "MSFT"])
        self.assertEqual(data["health"]["option_provider_readiness"], "blocked")
        self.assertEqual(data["health"]["option_provider_blocked_reason"], "no_chain_rows")
        self.assertEqual(data["health"]["option_backfill_valid_rows"], 0)

    def test_phase12e_coverage_plan_reports_broader_missing_tickers(self) -> None:
        database_path = fresh_database_path("phase12e_coverage_plan.sqlite")
        config = make_config(database_path)
        write_config(config)
        initialize_database(database_path)
        seed_phase12e_option_universe(database_path)

        plan = option_chain_coverage_plan(config)
        output = io.StringIO()
        with redirect_stdout(output):
            exit_code = command_option_chain_coverage_plan(Namespace(config=config.config_path))
        status_output = io.StringIO()
        with redirect_stdout(status_output):
            status_exit = command_option_chain_status(Namespace(config=config.config_path))

        self.assertEqual(exit_code, 0)
        self.assertEqual(status_exit, 0)
        self.assertEqual(plan.current_loaded_ticker_count, 3)
        self.assertEqual(plan.fetch_universe_ticker_count, 17)
        self.assertEqual(plan.prioritized_missing_tickers, PHASE12E_MISSING_TICKERS)
        self.assertEqual(plan.blocked_reason, "no_valid_option_backfill_rows")
        self.assertIn("Current chain coverage: 3/17", output.getvalue())
        self.assertIn("AMD, AMZN, AVGO", output.getvalue())
        self.assertIn("Broader chain coverage: 3/17", status_output.getvalue())

    def test_phase12e_missing_template_excludes_covered_tickers(self) -> None:
        database_path = fresh_database_path("phase12e_missing_template.sqlite")
        config = make_config(database_path)
        write_config(config)
        initialize_database(database_path)
        seed_phase12e_option_universe(database_path)

        output = io.StringIO()
        with redirect_stdout(output):
            exit_code = command_export_options_chain_missing_template(
                Namespace(config=config.config_path)
            )
        result = export_options_chain_missing_template(config)
        rows = list(
            csv.DictReader(
                (config.options_chain_source_exports_dir / "options_chain_missing_backfill.csv")
                .read_text(encoding="utf-8")
                .splitlines()
            )
        )

        self.assertEqual(exit_code, 0)
        self.assertEqual(result.row_count, 14)
        self.assertEqual([row["ticker"] for row in rows], list(PHASE12E_MISSING_TICKERS))
        self.assertNotIn("AAPL", [row["ticker"] for row in rows])
        self.assertNotIn("SOXL", [row["ticker"] for row in rows])
        self.assertIn("Rows: 14", output.getvalue())

    def test_non_actionable_blank_placeholder_keeps_missing_coverage(self) -> None:
        database_path = fresh_database_path("phase12g_blank_non_actionable.sqlite")
        config = make_config(database_path)
        write_config(config)
        initialize_database(database_path)
        seed_underlying(database_path, "BIL", asset_type="etf")

        export_options_chain_missing_template(config)
        validation = validate_option_chain_non_actionable_decisions(config)
        plan = option_chain_coverage_plan(config)
        availability = option_chain_availability_statuses(config)

        self.assertTrue(validation.file_exists)
        self.assertEqual(validation.blank_placeholder_count, 1)
        self.assertEqual(validation.valid_tickers, ())
        self.assertEqual(plan.coverage_status, "missing_coverage")
        self.assertEqual(plan.effective_missing_tickers, ("BIL",))
        self.assertEqual(plan.non_actionable_tickers, ())
        self.assertEqual(plan.raw_coverage_count, "0/1")
        self.assertEqual(plan.effective_coverage_count, "0/1")
        self.assertEqual(plan.blocked_reason, "no_valid_option_backfill_rows")
        self.assertEqual(availability[0].ticker, "BIL")
        self.assertEqual(availability[0].availability_status, "missing")
        self.assertEqual(availability[0].reason_code, "missing_option_chain")
        self.assertFalse(availability[0].raw_chain_available)
        self.assertTrue(availability[0].effective_coverage_included)

    def test_valid_non_actionable_decision_completes_effective_coverage_only(self) -> None:
        database_path = fresh_database_path("phase12g_valid_non_actionable.sqlite")
        config = make_config(database_path)
        write_config(config)
        initialize_database(database_path)
        seed_underlying(database_path, "BIL", asset_type="etf")
        write_non_actionable_decision_rows(
            config.options_chain_source_exports_dir / "options_chain_non_actionable.csv",
            [
                {
                    "ticker": "BIL",
                    "decision_date": date.today().isoformat(),
                    "reason_code": "no_listed_options",
                    "source": "unit_test_provider_review",
                    "source_url": "https://example.com/bil/options",
                    "as_of_date": date.today().isoformat(),
                    "effective_date": date.today().isoformat(),
                    "notes": "No listed options in source review.",
                }
            ],
        )

        plan = option_chain_coverage_plan(config)
        availability = option_chain_availability_statuses(config)
        account = account_context_status(config)

        self.assertEqual(plan.coverage_status, "complete")
        self.assertEqual(plan.raw_missing_tickers, ("BIL",))
        self.assertEqual(plan.effective_missing_tickers, ())
        self.assertEqual(plan.non_actionable_tickers, ("BIL",))
        self.assertEqual(plan.raw_coverage_count, "0/1")
        self.assertEqual(plan.effective_coverage_count, "0/0")
        self.assertEqual(plan.notes, ("non_actionable_option_chain_excluded",))
        self.assertEqual(len(list_option_chain_snapshots(database_path, ticker="BIL")), 0)
        self.assertEqual(availability[0].ticker, "BIL")
        self.assertEqual(availability[0].availability_status, "unavailable")
        self.assertEqual(availability[0].reason_code, "no_listed_options")
        self.assertEqual(availability[0].source, "unit_test_provider_review")
        self.assertEqual(availability[0].source_url, "https://example.com/bil/options")
        self.assertFalse(availability[0].raw_chain_available)
        self.assertFalse(availability[0].effective_coverage_included)
        self.assertIn("empty_options_positions", account.blockers)
        self.assertIn("no_option_lifecycle_rows", account.blockers)

    def test_loaded_option_chain_ticker_reports_available(self) -> None:
        database_path = fresh_database_path("phase12g_available_chain.sqlite")
        config = make_config(database_path)
        write_config(config)
        initialize_database(database_path)
        seed_underlying(database_path, "AAPL")
        upsert_option_chain_snapshot(database_path, option_snapshot("AAPL", strike=100.0))

        availability = option_chain_availability_statuses(config)

        self.assertEqual(len(availability), 1)
        self.assertEqual(availability[0].ticker, "AAPL")
        self.assertEqual(availability[0].availability_status, "available")
        self.assertEqual(availability[0].reason_code, "option_chain_rows_loaded")
        self.assertTrue(availability[0].raw_chain_available)
        self.assertTrue(availability[0].effective_coverage_included)

    def test_invalid_non_actionable_decisions_are_warnings_not_coverage(self) -> None:
        database_path = fresh_database_path("phase12g_invalid_non_actionable.sqlite")
        config = make_config(database_path)
        write_config(config)
        initialize_database(database_path)
        seed_underlying(database_path, "BIL", asset_type="etf")
        seed_underlying(database_path, "CASHX", asset_type="equity", asset_role="reference")
        write_non_actionable_decision_rows(
            config.options_chain_source_exports_dir / "options_chain_non_actionable.csv",
            [
                {
                    "ticker": "BIL",
                    "decision_date": date.today().isoformat(),
                    "reason_code": "unsupported_reason",
                    "source": "unit_test",
                    "source_url": "https://example.com/bil",
                },
                {
                    "ticker": "BIL",
                    "decision_date": date.today().isoformat(),
                    "reason_code": "no_listed_options",
                    "source": "",
                    "source_url": "https://example.com/bil",
                },
                {
                    "ticker": "CASHX",
                    "decision_date": date.today().isoformat(),
                    "reason_code": "no_listed_options",
                    "source": "unit_test",
                    "source_url": "https://example.com/cashx",
                },
            ],
        )

        validation = validate_option_chain_non_actionable_decisions(config)
        plan = option_chain_coverage_plan(config)
        availability = option_chain_availability_statuses(config)

        self.assertEqual(validation.invalid_decision_count, 3)
        self.assertEqual(validation.valid_tickers, ())
        self.assertEqual(plan.coverage_status, "missing_coverage")
        self.assertEqual(plan.effective_missing_tickers, ("BIL",))
        self.assertEqual(plan.non_actionable_tickers, ())
        self.assertEqual(availability[0].availability_status, "missing")
        self.assertEqual(availability[0].reason_code, "missing_option_chain")
        self.assertIn("invalid_non_actionable_option_chain_decisions", plan.warnings)
        self.assertTrue(
            any("ticker_not_in_options_fetch_universe:CASHX" in reason for reason in validation.invalid_reasons)
        )

    def test_phase12e_coverage_backfill_dry_run_and_confirm_allow_partial(self) -> None:
        database_path = fresh_database_path("phase12e_apply_partial.sqlite")
        config = make_config(database_path)
        write_config(config)
        initialize_database(database_path)
        seed_phase12e_option_universe(database_path)
        write_valid_options_backfill_row(
            config.options_chain_source_exports_dir / "msft_provider.csv",
            "MSFT",
            strike=90,
        )

        dry_run = apply_options_chain_coverage_backfill(config, allow_partial=True)
        self.assertTrue(dry_run.success)
        self.assertEqual(dry_run.status, "dry_run_ready")
        self.assertEqual(len(list_option_chain_snapshots(database_path, ticker="MSFT")), 0)

        blocked_full = apply_options_chain_coverage_backfill(config, confirm=True)
        self.assertFalse(blocked_full.success)
        self.assertEqual(blocked_full.blocked_reason, "option_chain_coverage_incomplete")

        confirmed = apply_options_chain_coverage_backfill(
            config,
            confirm=True,
            allow_partial=True,
        )

        self.assertTrue(confirmed.success)
        self.assertEqual(confirmed.imported_count, 1)
        self.assertEqual(confirmed.plan.current_loaded_ticker_count, 4)
        self.assertEqual(len(list_option_chain_snapshots(database_path, ticker="MSFT")), 1)
        self.assertGreaterEqual(len(list_option_income_reviews(database_path, ticker="MSFT")), 1)
        self.assertGreaterEqual(len(list_option_risk_reviews(database_path, ticker="MSFT")), 1)
        self.assertGreaterEqual(len(list_option_review_outcomes(database_path, ticker="MSFT")), 1)

    def test_phase12e_apply_command_blocks_invalid_or_non_improving_rows(self) -> None:
        database_path = fresh_database_path("phase12e_apply_command_block.sqlite")
        config = make_config(database_path)
        write_config(config)
        initialize_database(database_path)
        seed_phase12e_option_universe(database_path)
        export_options_chain_missing_template(config)

        dry_output = io.StringIO()
        with redirect_stdout(dry_output):
            dry_exit = command_apply_options_chain_coverage_backfill(
                Namespace(
                    config=config.config_path,
                    confirm=False,
                    allow_partial=True,
                    dir=None,
                )
            )
        confirm_output = io.StringIO()
        with redirect_stdout(confirm_output):
            confirm_exit = command_apply_options_chain_coverage_backfill(
                Namespace(
                    config=config.config_path,
                    confirm=True,
                    allow_partial=True,
                    dir=None,
                )
            )

        self.assertEqual(dry_exit, 0)
        self.assertEqual(confirm_exit, 1)
        self.assertIn("Status: blocked", dry_output.getvalue())
        self.assertIn("no_valid_option_backfill_rows", confirm_output.getvalue())

    def test_phase12e_reports_and_dashboard_include_broader_coverage(self) -> None:
        database_path = fresh_database_path("phase12e_outputs.sqlite")
        config = make_config(database_path)
        write_config(config)
        initialize_database(database_path)
        seed_phase12e_option_universe(database_path)

        with patch(
            "target_opportunity_monitor.ibkr_provider._import_ibapi",
            return_value=(object, object, object, None),
        ):
            dashboard = build_dashboard(config)
            report = write_daily_report(config)
        data = dashboard_data(dashboard.path.read_text(encoding="utf-8"))
        markdown = report.path.read_text(encoding="utf-8")
        csv_text = report.csv_path.read_text(encoding="utf-8") if report.csv_path else ""

        self.assertEqual(data["health"]["option_chain_coverage_count"], "3/17")
        self.assertEqual(
            data["health"]["option_chain_prioritized_missing_tickers"],
            list(PHASE12E_MISSING_TICKERS),
        )
        self.assertEqual(
            data["health"]["option_chain_coverage_blocked_reason"],
            "no_valid_option_backfill_rows",
        )
        self.assertIn("option_chain_coverage_status", REPORT_CSV_COLUMNS)
        self.assertIn("option_chain_coverage_count", REPORT_CSV_COLUMNS)
        self.assertIn("Options broader chain coverage: `3/17`", markdown)
        self.assertIn("option_chain_coverage_status", csv_text)
        status_output = io.StringIO()
        with redirect_stdout(status_output):
            status_exit = command_status(Namespace(config=config.config_path))
        self.assertEqual(status_exit, 0)
        self.assertIn("Options broader chain coverage: 3/17", status_output.getvalue())

    def test_intraday_cycle_include_options_runs_optional_steps(self) -> None:
        database_path = fresh_database_path("phase12b_intraday.sqlite")
        config = make_config(database_path)
        initialize_database(database_path)

        with patch("target_opportunity_monitor.pipeline._quote_step", return_value=(1, ())), patch(
            "target_opportunity_monitor.pipeline._gap_step",
            return_value=(1, ()),
        ), patch(
            "target_opportunity_monitor.pipeline._range_step",
            return_value=(1, ()),
        ), patch(
            "target_opportunity_monitor.pipeline._options_chain_fetch_step",
            return_value=(1, ()),
        ), patch(
            "target_opportunity_monitor.pipeline._options_income_step",
            return_value=(1, ()),
        ):
            result = run_intraday_cycle(config, include_options=True)

        step_names = [step.step_name for step in result.steps]
        self.assertIn("fetch-options-chain", step_names)
        self.assertIn("compute-options-income", step_names)
        self.assertIn("include_options=True", result.summary)


if __name__ == "__main__":
    unittest.main()
