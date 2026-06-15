from __future__ import annotations

from argparse import Namespace
from contextlib import redirect_stdout
from datetime import date, timedelta
from pathlib import Path
import io
import sys
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
TEST_TMP_ROOT = PROJECT_ROOT / ".tmp_tests"
sys.path.insert(0, str(SRC_PATH))

from target_opportunity_monitor.cli import (
    command_range_status,
    command_regime_status,
    command_technical_status,
)
from target_opportunity_monitor.config import AppConfig, load_config
from target_opportunity_monitor.dashboard import build_dashboard
from target_opportunity_monitor.db import REQUIRED_TABLES, initialize_database
from target_opportunity_monitor.ranges import compute_range_snapshots
from target_opportunity_monitor.reporting import build_daily_report_rows, write_daily_report
from target_opportunity_monitor.storage import (
    Asset,
    Price,
    PriceFeature,
    QuoteSnapshot,
    Score,
    Target,
    count_rows_by_table,
    list_signals,
    range_statuses,
    regime_signal_statuses,
    technical_signal_statuses,
    upsert_asset,
    upsert_price_feature,
    upsert_prices,
    upsert_quote_snapshot,
    upsert_score,
    upsert_target,
)
from target_opportunity_monitor.technical import (
    compute_regime_signals,
    compute_technical_signals,
)


def make_config(database_path: Path) -> AppConfig:
    return AppConfig(
        project_root=TEST_TMP_ROOT,
        config_path=TEST_TMP_ROOT / "phase11b.toml",
        database_path=database_path,
        reports_dir=TEST_TMP_ROOT / "reports_phase11b",
        watchlist_path=TEST_TMP_ROOT / "watchlist_phase11b.csv",
        market_data_dir=TEST_TMP_ROOT / "market_data_phase11b",
        manual_prices_dir=TEST_TMP_ROOT / "market_data_phase11b" / "manual",
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
        technical_lookback_days=252,
        technical_minimum_history_days=120,
        technical_short_ma_days=20,
        technical_medium_ma_days=50,
        technical_long_ma_days=120,
        regime_relative_strength_lookback_days=63,
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
                "[technical]",
                f'model_version = "{config.technical_model_version}"',
                f"lookback_days = {config.technical_lookback_days}",
                f"minimum_history_days = {config.technical_minimum_history_days}",
                f"short_ma_days = {config.technical_short_ma_days}",
                f"medium_ma_days = {config.technical_medium_ma_days}",
                f"long_ma_days = {config.technical_long_ma_days}",
                f"pivot_window_days = {config.technical_pivot_window_days}",
                f"near_level_pct = {config.technical_near_level_pct}",
                f"breakout_buffer_pct = {config.technical_breakout_buffer_pct}",
                "",
                "[regime]",
                f'model_version = "{config.regime_model_version}"',
                'benchmark_tickers = ["SPY", "QQQ"]',
                'sector_proxy_tickers = ["XLK", "XLV"]',
                f"relative_strength_lookback_days = {config.regime_relative_strength_lookback_days}",
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
            )
        ),
        encoding="utf-8",
    )


def price_series(
    ticker: str,
    count: int,
    start_price: float,
    step: float,
    source: str = "fixture",
) -> list[Price]:
    start = date.today() - timedelta(days=count - 1)
    prices: list[Price] = []
    for index in range(count):
        price_date = (start + timedelta(days=index)).isoformat()
        close = start_price + step * index + ((index % 11) - 5) * 0.12
        prices.append(
            Price(
                ticker=ticker,
                price_date=price_date,
                open=close - 0.2,
                high=close + 1.0,
                low=close - 1.0,
                close=close,
                adjusted_close=close,
                volume=1_000_000 + index,
                source=source,
            )
        )
    return prices


def seed_equity_for_range(database_path: Path, ticker: str = "AAPL", price: float = 92) -> None:
    today = date.today().isoformat()
    upsert_asset(database_path, Asset(ticker=ticker, asset_type="equity"))
    upsert_price_feature(
        database_path,
        PriceFeature(
            ticker=ticker,
            feature_date=today,
            current_price=price,
            return_1d=0.01,
            return_1m=0.04,
            return_3m=0.08,
            return_6m=0.12,
            return_12m=0.20,
            realized_volatility_20d=0.2,
            realized_volatility_60d=0.25,
            average_dollar_volume_20d=1_000_000_000,
            latest_price_date=today,
        ),
    )
    upsert_quote_snapshot(
        database_path,
        QuoteSnapshot(ticker=ticker, quote_timestamp=f"{today}T10:00:00", last=price),
    )
    upsert_target(
        database_path,
        Target(
            ticker=ticker,
            target_date=today,
            base_target=125,
            target_low=105,
            target_high=150,
            valuation_gap=0.35,
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
            confidence_score=75,
            timing_score=70,
            risk_score=60,
            liquidity_score=90,
            asset_type="equity",
        ),
    )


class Phase11BTechnicalRegimeTests(unittest.TestCase):
    def fresh_database_path(self, name: str) -> Path:
        TEST_TMP_ROOT.mkdir(parents=True, exist_ok=True)
        path = TEST_TMP_ROOT / name
        if path.exists():
            path.unlink()
        return path

    def test_init_db_creates_phase11b_tables(self) -> None:
        database_path = self.fresh_database_path("phase11b_schema.sqlite")

        status = initialize_database(database_path)

        self.assertIn("technical_signal_snapshots", status.existing_tables)
        self.assertIn("regime_signal_snapshots", status.existing_tables)
        self.assertEqual(status.existing_required_table_count, len(REQUIRED_TABLES))

    def test_config_loads_technical_and_regime_defaults(self) -> None:
        config = load_config(PROJECT_ROOT / "configs" / "default.toml")

        self.assertEqual(config.technical_model_version, "technical_levels_mvp_v1")
        self.assertEqual(config.technical_lookback_days, 252)
        self.assertEqual(config.regime_model_version, "market_regime_mvp_v1")
        self.assertIn("SPY", config.regime_benchmark_tickers)

    def test_compute_technical_signals_creates_levels_and_shadow_rows(self) -> None:
        database_path = self.fresh_database_path("phase11b_technical.sqlite")
        config = make_config(database_path)
        initialize_database(database_path)
        upsert_asset(database_path, Asset(ticker="AAPL", asset_type="equity"))
        upsert_prices(database_path, price_series("AAPL", 150, 80, 0.25))

        result = compute_technical_signals(config, ticker="AAPL")
        status = technical_signal_statuses(database_path, ticker="AAPL")[0]
        signals = list_signals(database_path, ticker="AAPL")

        self.assertEqual(result.computed_count, 1)
        self.assertEqual(status.moving_average_state, "bullish")
        self.assertIsNotNone(status.support_low)
        self.assertIsNotNone(status.resistance_high)
        self.assertGreaterEqual(status.confidence or 0, 70)
        self.assertIn("technical.trend", {signal.signal_name for signal in signals})
        self.assertIn("technical.levels", {signal.signal_name for signal in signals})

    def test_insufficient_price_history_warns_without_crashing(self) -> None:
        database_path = self.fresh_database_path("phase11b_insufficient.sqlite")
        config = make_config(database_path)
        initialize_database(database_path)
        upsert_asset(database_path, Asset(ticker="AAPL", asset_type="equity"))
        upsert_prices(database_path, price_series("AAPL", 30, 100, 0.1))

        result = compute_technical_signals(config, ticker="AAPL")
        status = technical_signal_statuses(database_path, ticker="AAPL")[0]

        self.assertEqual(result.warning_count, 1)
        self.assertIn("insufficient_price_history", status.data_warnings or "")

    def test_regime_signals_classify_benchmarks_and_warn_missing_sectors(self) -> None:
        database_path = self.fresh_database_path("phase11b_regime.sqlite")
        config = make_config(database_path)
        initialize_database(database_path)
        upsert_asset(database_path, Asset(ticker="SPY", asset_type="etf"))
        upsert_asset(database_path, Asset(ticker="QQQ", asset_type="etf"))
        upsert_prices(database_path, price_series("SPY", 220, 400, 0.4))
        upsert_prices(database_path, price_series("QQQ", 220, 350, 0.5))

        result = compute_regime_signals(config)
        statuses = {status.ticker: status for status in regime_signal_statuses(database_path)}

        self.assertGreaterEqual(result.computed_count, 4)
        self.assertEqual(statuses["SPY"].risk_state, "risk_on")
        self.assertEqual(statuses["XLK"].data_warnings, "missing_sector_proxy_price_history")
        self.assertIn("regime.market", {signal.signal_name for signal in list_signals(database_path, ticker="SPY")})

    def test_range_monitor_includes_technical_and_regime_context(self) -> None:
        database_path = self.fresh_database_path("phase11b_range.sqlite")
        config = make_config(database_path)
        initialize_database(database_path)
        seed_equity_for_range(database_path, "AAPL", price=92)
        upsert_asset(database_path, Asset(ticker="SPY", asset_type="etf"))
        upsert_asset(database_path, Asset(ticker="QQQ", asset_type="etf"))
        upsert_prices(database_path, price_series("AAPL", 150, 80, 0.25))
        upsert_prices(database_path, price_series("SPY", 220, 400, -0.25))
        upsert_prices(database_path, price_series("QQQ", 220, 350, -0.30))
        compute_technical_signals(config, ticker="AAPL")
        compute_regime_signals(config)

        compute_range_snapshots(config, ticker="AAPL")
        status = range_statuses(database_path, ticker="AAPL")[0]

        self.assertEqual(status.moving_average_state, "bullish")
        self.assertEqual(status.regime_state, "risk_off")
        self.assertIn("regime_risk_off", status.data_warnings or "")
        self.assertIsNotNone(status.support_low)

    def test_outputs_include_phase11b_fields(self) -> None:
        database_path = self.fresh_database_path("phase11b_outputs.sqlite")
        config = make_config(database_path)
        write_config(config)
        initialize_database(database_path)
        seed_equity_for_range(database_path, "AAPL", price=92)
        upsert_asset(database_path, Asset(ticker="SPY", asset_type="etf"))
        upsert_asset(database_path, Asset(ticker="QQQ", asset_type="etf"))
        upsert_prices(database_path, price_series("AAPL", 150, 80, 0.25))
        upsert_prices(database_path, price_series("SPY", 220, 400, 0.4))
        upsert_prices(database_path, price_series("QQQ", 220, 350, 0.5))
        compute_technical_signals(config, ticker="AAPL")
        compute_regime_signals(config)
        compute_range_snapshots(config, ticker="AAPL")

        rows = build_daily_report_rows(config, initialize_database(database_path))
        report = write_daily_report(config)
        dashboard = build_dashboard(config)
        technical_output = io.StringIO()
        regime_output = io.StringIO()
        range_output = io.StringIO()
        with redirect_stdout(technical_output):
            command_technical_status(Namespace(config=config.config_path, ticker="AAPL"))
        with redirect_stdout(regime_output):
            command_regime_status(Namespace(config=config.config_path, ticker="SPY"))
        with redirect_stdout(range_output):
            command_range_status(Namespace(config=config.config_path, ticker="AAPL"))

        self.assertEqual(rows[0].moving_average_state, "bullish")
        csv_text = report.csv_path.read_text(encoding="utf-8")
        markdown_text = report.path.read_text(encoding="utf-8")
        dashboard_text = dashboard.path.read_text(encoding="utf-8")
        self.assertIn("moving_average_state", csv_text)
        self.assertIn("Technical And Regime Status", markdown_text)
        self.assertIn("Latest Technical", dashboard_text)
        self.assertIn("MA State", technical_output.getvalue())
        self.assertIn("risk_on", regime_output.getvalue())
        self.assertIn("Technical", range_output.getvalue())

    def test_compute_technical_signals_ticker_filter(self) -> None:
        database_path = self.fresh_database_path("phase11b_filter.sqlite")
        config = make_config(database_path)
        initialize_database(database_path)
        upsert_asset(database_path, Asset(ticker="AAPL", asset_type="equity"))
        upsert_asset(database_path, Asset(ticker="MSFT", asset_type="equity"))
        upsert_prices(database_path, price_series("AAPL", 150, 80, 0.25))
        upsert_prices(database_path, price_series("MSFT", 150, 120, 0.15))

        compute_technical_signals(config, ticker="AAPL")
        statuses = technical_signal_statuses(database_path)

        self.assertEqual(
            {status.ticker for status in statuses if status.signal_date},
            {"AAPL"},
        )


if __name__ == "__main__":
    unittest.main()
