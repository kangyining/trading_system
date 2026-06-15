from __future__ import annotations

from argparse import Namespace
from contextlib import redirect_stdout
from datetime import date, datetime, timedelta
from pathlib import Path
import io
import sys
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
TEST_TMP_ROOT = PROJECT_ROOT / ".tmp_tests"
sys.path.insert(0, str(SRC_PATH))

from target_opportunity_monitor.cli import (
    command_add_asset,
    command_deactivate_asset,
    command_range_status,
)
from target_opportunity_monitor.config import AppConfig, load_config
from target_opportunity_monitor.dashboard import build_dashboard
from target_opportunity_monitor.db import REQUIRED_TABLES, initialize_database
from target_opportunity_monitor.notifications import deliver_notifications
from target_opportunity_monitor.ranges import compute_range_snapshots
from target_opportunity_monitor.reporting import build_daily_report_rows, write_daily_report
from target_opportunity_monitor.storage import (
    Asset,
    EtfFeature,
    PriceFeature,
    QuoteSnapshot,
    Score,
    Target,
    count_rows_by_table,
    latest_asset,
    list_notification_events,
    pending_notification_count,
    range_statuses,
    upsert_asset,
    upsert_etf_feature,
    upsert_price_feature,
    upsert_quote_snapshot,
    upsert_score,
    upsert_target,
)


def make_config(database_path: Path) -> AppConfig:
    return AppConfig(
        project_root=TEST_TMP_ROOT,
        config_path=TEST_TMP_ROOT / "phase11a.toml",
        database_path=database_path,
        reports_dir=TEST_TMP_ROOT / "reports_phase11a",
        watchlist_path=TEST_TMP_ROOT / "watchlist_phase11a.csv",
        market_data_dir=TEST_TMP_ROOT / "market_data_phase11a",
        manual_prices_dir=TEST_TMP_ROOT / "market_data_phase11a" / "manual",
        market_data_primary_source="stooq",
        market_data_secondary_source="yahoo_chart",
        market_data_mode="csv",
        market_data_lookback_days=800,
        market_data_stale_after_days=7,
        market_data_minimum_history_days=252,
        universe_mode="manual_watchlist",
        run_mode="daily_scoring",
        report_title="Target Opportunity Monitor Daily Report",
        realtime_quote_stale_after_seconds=900,
        realtime_notification_cooldown_minutes=60,
    )


def write_config(config: AppConfig) -> None:
    config.config_path.parent.mkdir(parents=True, exist_ok=True)
    config.config_path.write_text(
        "\n".join(
            (
                "[paths]",
                f'database = "{config.database_path.as_posix()}"',
                f'reports = "{config.reports_dir.as_posix()}"',
                f'watchlist = "{config.watchlist_path.as_posix()}"',
                "",
                "[realtime]",
                'source = "ibkr"',
                "quote_stale_after_seconds = 900",
                'range_model_version = "range_monitor_mvp_v1"',
                "notification_cooldown_minutes = 60",
                "monitor_active_assets_only = true",
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


def seed_equity(
    database_path: Path,
    ticker: str = "AAPL",
    price: float = 90,
    active_flag: int = 1,
) -> None:
    today = date.today().isoformat()
    now = datetime.now().isoformat(timespec="seconds")
    upsert_asset(database_path, Asset(ticker=ticker, asset_type="equity", active_flag=active_flag))
    upsert_price_feature(
        database_path,
        PriceFeature(
            ticker=ticker,
            feature_date=today,
            current_price=price,
            return_1d=0.01,
            return_1m=0.05,
            return_3m=0.10,
            return_6m=0.15,
            return_12m=0.20,
            realized_volatility_20d=0.2,
            realized_volatility_60d=0.25,
            average_dollar_volume_20d=1_000_000_000,
            latest_price_date=today,
        ),
    )
    upsert_quote_snapshot(
        database_path,
        QuoteSnapshot(ticker=ticker, quote_timestamp=now, last=price, source="ibkr"),
    )
    upsert_target(
        database_path,
        Target(
            ticker=ticker,
            target_date=today,
            base_target=120,
            target_low=100,
            target_high=150,
            valuation_gap=0.33,
            target_method="fixture",
            uncertainty_band=0.25,
        ),
    )
    upsert_score(
        database_path,
        Score(
            ticker=ticker,
            score_date=today,
            opportunity_score=80,
            expected_value_score=80,
            confidence_score=75,
            timing_score=70,
            risk_score=60,
            liquidity_score=90,
            asset_type="equity",
        ),
    )


def seed_etf(database_path: Path, ticker: str = "SPY", price: float = 497) -> None:
    today = date.today().isoformat()
    now = datetime.now().isoformat(timespec="seconds")
    upsert_asset(database_path, Asset(ticker=ticker, asset_type="etf"))
    upsert_quote_snapshot(
        database_path,
        QuoteSnapshot(ticker=ticker, quote_timestamp=now, last=price, source="ibkr"),
    )
    upsert_etf_feature(
        database_path,
        EtfFeature(
            ticker=ticker,
            feature_date=today,
            nav_per_share=500,
            market_price=price,
            premium_discount=-0.006,
            premium_discount_average_60d=None,
            premium_discount_volatility_60d=None,
            premium_discount_zscore=None,
            latest_nav_date=today,
            latest_holdings_date=today,
            holdings_count=10,
            top_10_weight=None,
            largest_holding_weight=None,
            equity_weight=None,
            cash_weight=None,
            source="fixture",
        ),
    )
    upsert_target(
        database_path,
        Target(
            ticker=ticker,
            target_date=today,
            base_target=500,
            target_low=499,
            target_high=501,
            valuation_gap=0.006,
            target_method="etf_nav",
            uncertainty_band=0.005,
            source="etf_valuation",
            model_version="etf_nav_mvp_v1",
        ),
    )
    upsert_score(
        database_path,
        Score(
            ticker=ticker,
            score_date=today,
            opportunity_score=70,
            confidence_score=70,
            timing_score=60,
            risk_score=70,
            liquidity_score=90,
            asset_type="etf",
            score_model="etf_score_mvp_v1",
            threshold_set="etf_liquid_index",
            model_version="etf_score_mvp_v1",
        ),
    )


class Phase11ATest(unittest.TestCase):
    def fresh_database_path(self, name: str) -> Path:
        TEST_TMP_ROOT.mkdir(parents=True, exist_ok=True)
        path = TEST_TMP_ROOT / name
        if path.exists():
            path.unlink()
        return path

    def test_init_db_creates_phase11a_tables(self) -> None:
        database_path = self.fresh_database_path("phase11a_schema.sqlite")
        status = initialize_database(database_path)

        self.assertIn("range_snapshots", status.existing_tables)
        self.assertIn("notification_events", status.existing_tables)
        self.assertIn("notification_deliveries", status.existing_tables)
        self.assertIn("asset_change_events", status.existing_tables)
        self.assertEqual(status.existing_required_table_count, len(REQUIRED_TABLES))

    def test_config_loads_realtime_defaults(self) -> None:
        config = load_config()

        self.assertEqual(config.realtime_source, "ibkr")
        self.assertEqual(config.realtime_quote_stale_after_seconds, 900)
        self.assertEqual(config.realtime_range_model_version, "range_monitor_mvp_v1")
        self.assertEqual(config.realtime_notification_cooldown_minutes, 60)
        self.assertTrue(config.realtime_monitor_active_assets_only)

    def test_equity_range_and_notification_are_deduped(self) -> None:
        database_path = self.fresh_database_path("phase11a_equity.sqlite")
        config = make_config(database_path)
        write_config(config)
        initialize_database(database_path)
        seed_equity(database_path, price=90)

        first = compute_range_snapshots(config, ticker="AAPL")
        second = compute_range_snapshots(config, ticker="AAPL")
        status = range_statuses(database_path, ticker="AAPL")[0]

        self.assertEqual(first.updated_count, 1)
        self.assertEqual(first.notification_count, 1)
        self.assertEqual(second.notification_count, 0)
        self.assertEqual(status.range_state, "strong_buy")
        self.assertEqual(count_rows_by_table(database_path, "notification_events"), 1)

    def test_etf_range_uses_nav_discount(self) -> None:
        database_path = self.fresh_database_path("phase11a_etf.sqlite")
        config = make_config(database_path)
        initialize_database(database_path)
        seed_etf(database_path, price=497)

        result = compute_range_snapshots(config, ticker="SPY")
        status = range_statuses(database_path, ticker="SPY")[0]

        self.assertEqual(result.updated_count, 1)
        self.assertEqual(status.range_state, "strong_buy")
        self.assertEqual(status.nav_fair_value, 500)
        self.assertIsNotNone(status.nav_action_discount_below)

    def test_inactive_assets_are_skipped(self) -> None:
        database_path = self.fresh_database_path("phase11a_inactive.sqlite")
        config = make_config(database_path)
        initialize_database(database_path)
        seed_equity(database_path, "AAPL", active_flag=1)
        seed_equity(database_path, "TSLA", active_flag=0)

        result = compute_range_snapshots(config)

        self.assertEqual(tuple(item.ticker for item in result.results), ("AAPL",))

    def test_deliver_notifications_marks_pending_events_delivered(self) -> None:
        database_path = self.fresh_database_path("phase11a_delivery.sqlite")
        config = make_config(database_path)
        initialize_database(database_path)
        seed_equity(database_path, price=90)
        compute_range_snapshots(config, ticker="AAPL")

        result = deliver_notifications(config, channel="console")

        self.assertEqual(result.delivered_count, 1)
        self.assertEqual(pending_notification_count(database_path), 0)
        self.assertEqual(count_rows_by_table(database_path, "notification_deliveries"), 1)

    def test_asset_commands_update_watchlist_and_active_flag(self) -> None:
        database_path = self.fresh_database_path("phase11a_assets.sqlite")
        config = make_config(database_path)
        write_config(config)
        initialize_database(database_path)

        with redirect_stdout(io.StringIO()):
            add_code = command_add_asset(
                Namespace(
                    config=config.config_path,
                    ticker="TSLA",
                    asset_type="equity",
                    name="Tesla Inc.",
                    exchange="NASDAQ",
                    currency="USD",
                    sector="Consumer Discretionary",
                    industry="Automobiles",
                    country="US",
                    cik="0001318605",
                    reason="test",
                )
            )
            deactivate_code = command_deactivate_asset(
                Namespace(config=config.config_path, ticker="TSLA", reason="test")
            )

        asset = latest_asset(database_path, "TSLA")
        self.assertEqual(add_code, 0)
        self.assertEqual(deactivate_code, 0)
        self.assertIsNotNone(asset)
        self.assertEqual(asset.active_flag, 0)
        self.assertIn("active", config.watchlist_path.read_text(encoding="utf-8"))
        self.assertEqual(count_rows_by_table(database_path, "asset_change_events"), 2)

    def test_reports_dashboard_and_range_status_include_phase11a_fields(self) -> None:
        database_path = self.fresh_database_path("phase11a_outputs.sqlite")
        config = make_config(database_path)
        initialize_database(database_path)
        seed_equity(database_path, price=90)
        compute_range_snapshots(config, ticker="AAPL")

        rows = build_daily_report_rows(config, initialize_database(database_path))
        report = write_daily_report(config)
        dashboard = build_dashboard(config)
        output = io.StringIO()
        with redirect_stdout(output):
            exit_code = command_range_status(
                Namespace(config=config.config_path, ticker="AAPL")
            )

        self.assertEqual(rows[0].range_state, "strong_buy")
        self.assertIn("range_state", report.csv_path.read_text(encoding="utf-8"))
        self.assertIn("Latest Range", dashboard.path.read_text(encoding="utf-8"))
        self.assertEqual(exit_code, 0)
        self.assertIn("strong_buy", output.getvalue())


if __name__ == "__main__":
    unittest.main()
