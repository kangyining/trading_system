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

from support import sqlite_connection_for_test
from target_opportunity_monitor.cli import (
    command_outcome_status,
    command_status,
    command_update_alert_outcomes,
    command_validation_report,
)
from target_opportunity_monitor.config import AppConfig
from target_opportunity_monitor.db import initialize_database
from target_opportunity_monitor.outcomes import update_alert_outcomes
from target_opportunity_monitor.reporting import REPORT_CSV_COLUMNS, write_daily_report
from target_opportunity_monitor.storage import (
    Alert,
    Asset,
    Price,
    count_rows_by_table,
    latest_outcome_date,
    list_alert_outcomes,
    list_stored_alerts,
    outcome_statuses,
    upsert_alert,
    upsert_asset,
    upsert_prices,
)


def make_config(database_path: Path) -> AppConfig:
    return AppConfig(
        project_root=TEST_TMP_ROOT,
        config_path=TEST_TMP_ROOT / "phase7a.toml",
        database_path=database_path,
        reports_dir=TEST_TMP_ROOT / "reports_phase7a",
        watchlist_path=TEST_TMP_ROOT / "watchlist_phase7a.csv",
        market_data_dir=TEST_TMP_ROOT / "market_data_phase7a",
        manual_prices_dir=TEST_TMP_ROOT / "market_data_phase7a" / "manual",
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
            )
        ),
        encoding="utf-8",
    )


def seed_alert(
    database_path: Path,
    ticker: str = "MSFT",
    alert_type: str = "bullish_divergence",
    asset_type: str = "equity",
    current_price: float = 100,
    base_target: float = 110,
    timestamp: str = "2026-01-10T09:30:00",
    alert_model: str | None = None,
    threshold_set: str | None = None,
) -> int:
    upsert_asset(database_path, Asset(ticker=ticker, asset_type=asset_type))
    alert_model = alert_model or (
        "etf_alert_mvp_v1" if asset_type == "etf" else "equity_alert_mvp_v1"
    )
    threshold_set = threshold_set or (
        "etf_liquid_index" if asset_type == "etf" else "equity_default"
    )
    upsert_alert(
        database_path,
        Alert(
            ticker=ticker,
            alert_type=alert_type,
            alert_timestamp=timestamp,
            priority="high",
            status="open",
            asset_type=asset_type,
            current_price=current_price,
            base_target=base_target,
            target_low=95,
            target_high=130,
            opportunity_score=75,
            risk_score=60,
            data_quality_score=100,
            invalidation="fixture",
            alert_model=alert_model,
            threshold_set=threshold_set,
            model_version=alert_model,
            dedupe_key=f"{timestamp}:{ticker}:{alert_type}",
        ),
    )
    return list_stored_alerts(database_path, ticker)[0].alert_id


def make_price(ticker: str, price_date: str, close: float) -> Price:
    return Price(
        ticker=ticker,
        price_date=price_date,
        open=close,
        high=close + 1,
        low=close - 1,
        close=close,
        adjusted_close=close,
        volume=1_000_000,
        source="fixture",
        as_of_date=price_date,
        effective_date=price_date,
    )


def seed_prices(
    database_path: Path,
    ticker: str,
    entry_close: float = 100,
    days: int = 120,
    direction: str = "up",
) -> None:
    entry_date = date(2026, 1, 10)
    prices = [make_price(ticker, entry_date.isoformat(), entry_close)]
    for offset in range(1, days + 1):
        current_date = entry_date + timedelta(days=offset)
        close = entry_close + offset if direction == "up" else entry_close - offset
        prices.append(make_price(ticker, current_date.isoformat(), close))
    upsert_prices(database_path, prices)


class Phase7AOutcomeTests(unittest.TestCase):
    def setUp(self) -> None:
        TEST_TMP_ROOT.mkdir(exist_ok=True)

    def fresh_database_path(self, name: str) -> Path:
        path = TEST_TMP_ROOT / name
        if path.exists():
            path.unlink()
        return path

    def test_db_init_migrates_outcome_columns_and_unique_index(self) -> None:
        database_path = self.fresh_database_path("phase7a_schema.sqlite")

        initialize_database(database_path)
        initialize_database(database_path)

        with sqlite_connection_for_test(database_path) as connection:
            columns = {
                row[1]
                for row in connection.execute(
                    "PRAGMA table_info(alert_outcomes)"
                ).fetchall()
            }
            indexes = {
                row[1]
                for row in connection.execute(
                    "PRAGMA index_list(alert_outcomes)"
                ).fetchall()
            }

        self.assertIn("ticker", columns)
        self.assertIn("outcome_status", columns)
        self.assertIn("entry_price", columns)
        self.assertIn("asset_type", columns)
        self.assertIn("alert_model", columns)
        self.assertIn("threshold_set", columns)
        self.assertIn("pending_horizons", columns)
        self.assertIn("model_version", columns)
        self.assertIn("idx_alert_outcomes_alert_id", indexes)

    def test_pending_outcome_is_created_when_future_history_is_insufficient(self) -> None:
        database_path = self.fresh_database_path("phase7a_pending.sqlite")
        config = make_config(database_path)
        initialize_database(database_path)
        seed_alert(database_path, ticker="MSFT")
        seed_prices(database_path, "MSFT", days=2)

        result = update_alert_outcomes(config, ticker="MSFT")
        outcome = list_alert_outcomes(database_path, "MSFT")[0]

        self.assertEqual(result.updated_count, 1)
        self.assertEqual(outcome.outcome_status, "pending")
        self.assertIsNone(outcome.return_5d)
        self.assertEqual(outcome.pending_horizons, "5d,20d,60d,120d")

    def test_returns_target_hit_and_excursions_compute_from_prices(self) -> None:
        database_path = self.fresh_database_path("phase7a_returns.sqlite")
        config = make_config(database_path)
        initialize_database(database_path)
        seed_alert(database_path, ticker="MSFT", alert_type="bullish_divergence")
        seed_prices(database_path, "MSFT", days=120, direction="up")

        update_alert_outcomes(config, ticker="MSFT")
        outcome = list_alert_outcomes(database_path, "MSFT")[0]

        self.assertEqual(outcome.outcome_status, "completed")
        self.assertAlmostEqual(outcome.return_5d or 0, 0.05)
        self.assertAlmostEqual(outcome.return_20d or 0, 0.20)
        self.assertEqual(outcome.hit_target_flag, 1)
        self.assertEqual(outcome.hit_invalidation_flag, 0)
        self.assertAlmostEqual(outcome.max_favorable_excursion or 0, 1.21)
        self.assertAlmostEqual(outcome.max_adverse_excursion or 0, 0.00)

    def test_bearish_target_and_invalidation_rules(self) -> None:
        database_path = self.fresh_database_path("phase7a_bearish.sqlite")
        config = make_config(database_path)
        initialize_database(database_path)
        seed_alert(
            database_path,
            ticker="AAPL",
            alert_type="bearish_overvaluation",
            base_target=90,
        )
        seed_prices(database_path, "AAPL", days=20, direction="down")

        update_alert_outcomes(config, ticker="AAPL")
        outcome = list_alert_outcomes(database_path, "AAPL")[0]

        self.assertEqual(outcome.outcome_status, "partial")
        self.assertAlmostEqual(outcome.return_5d or 0, -0.05)
        self.assertEqual(outcome.hit_target_flag, 1)
        self.assertEqual(outcome.hit_invalidation_flag, 0)
        self.assertAlmostEqual(outcome.max_favorable_excursion or 0, 0.21)
        self.assertAlmostEqual(outcome.max_adverse_excursion or 0, 0.00)

    def test_updating_outcomes_is_idempotent(self) -> None:
        database_path = self.fresh_database_path("phase7a_idempotent.sqlite")
        config = make_config(database_path)
        initialize_database(database_path)
        seed_alert(database_path, ticker="NVDA", alert_type="watch_only_gap")
        seed_prices(database_path, "NVDA", days=5)

        update_alert_outcomes(config, ticker="NVDA")
        update_alert_outcomes(config, ticker="NVDA")

        self.assertEqual(count_rows_by_table(database_path, "alert_outcomes"), 1)
        self.assertEqual(latest_outcome_date(database_path), datetime.now().date().isoformat())

    def test_ticker_and_asset_type_filters_and_skips_no_alert(self) -> None:
        database_path = self.fresh_database_path("phase7a_filter.sqlite")
        config = make_config(database_path)
        initialize_database(database_path)
        seed_alert(database_path, ticker="MSFT", alert_type="bullish_divergence")
        seed_prices(database_path, "MSFT", days=5)
        seed_alert(database_path, ticker="NVDA", alert_type="watch_only_gap")
        seed_prices(database_path, "NVDA", days=5)
        seed_alert(
            database_path,
            ticker="SPY",
            alert_type="etf_nav_discount_watch",
            asset_type="etf",
        )
        seed_prices(database_path, "SPY", days=5)
        seed_alert(database_path, ticker="AAPL", alert_type="no_alert")

        ticker_result = update_alert_outcomes(config, ticker="MSFT")
        equity_result = update_alert_outcomes(config, asset_type="equity")
        etf_result = update_alert_outcomes(config, asset_type="etf")

        self.assertEqual(ticker_result.updated_count, 1)
        self.assertEqual(equity_result.updated_count, 2)
        self.assertEqual(etf_result.updated_count, 1)
        self.assertEqual(count_rows_by_table(database_path, "alert_outcomes"), 3)
        by_ticker = {item.ticker: item for item in equity_result.results}
        self.assertNotIn("SPY", by_ticker)
        self.assertEqual(by_ticker["AAPL"].status, "skipped")
        self.assertNotIn("etf_outcomes_gated", etf_result.results[0].warnings)

    def test_etf_pending_outcome_uses_alert_current_price(self) -> None:
        database_path = self.fresh_database_path("phase7b_etf_pending.sqlite")
        config = make_config(database_path)
        initialize_database(database_path)
        seed_alert(
            database_path,
            ticker="SPY",
            alert_type="etf_nav_discount_dislocation",
            asset_type="etf",
            current_price=100,
            base_target=101,
        )

        result = update_alert_outcomes(config, ticker="SPY")
        outcome = list_alert_outcomes(database_path, "SPY")[0]

        self.assertEqual(result.updated_count, 1)
        self.assertEqual(outcome.asset_type, "etf")
        self.assertEqual(outcome.alert_model, "etf_alert_mvp_v1")
        self.assertEqual(outcome.threshold_set, "etf_liquid_index")
        self.assertEqual(outcome.outcome_status, "pending")
        self.assertEqual(outcome.entry_price, 100)
        self.assertIn("missing_price_history", outcome.data_warnings or "")

    def test_etf_discount_watch_uses_positive_direction_rules(self) -> None:
        database_path = self.fresh_database_path("phase7b_etf_discount.sqlite")
        config = make_config(database_path)
        initialize_database(database_path)
        seed_alert(
            database_path,
            ticker="SPY",
            alert_type="etf_nav_discount_watch",
            asset_type="etf",
            current_price=100,
            base_target=105,
        )
        seed_prices(database_path, "SPY", days=120, direction="up")

        update_alert_outcomes(config, ticker="SPY")
        outcome = list_alert_outcomes(database_path, "SPY")[0]

        self.assertEqual(outcome.outcome_status, "completed")
        self.assertAlmostEqual(outcome.return_5d or 0, 0.05)
        self.assertEqual(outcome.hit_target_flag, 1)
        self.assertEqual(outcome.hit_invalidation_flag, 0)
        self.assertAlmostEqual(outcome.invalidation_price or 0, 97.0)

    def test_etf_premium_warning_uses_negative_direction_rules(self) -> None:
        database_path = self.fresh_database_path("phase7b_etf_premium.sqlite")
        config = make_config(database_path)
        initialize_database(database_path)
        seed_alert(
            database_path,
            ticker="QQQ",
            alert_type="etf_nav_premium_warning",
            asset_type="etf",
            current_price=100,
            base_target=95,
        )
        seed_prices(database_path, "QQQ", days=20, direction="down")

        update_alert_outcomes(config, ticker="QQQ")
        outcome = list_alert_outcomes(database_path, "QQQ")[0]

        self.assertEqual(outcome.outcome_status, "partial")
        self.assertAlmostEqual(outcome.return_5d or 0, -0.05)
        self.assertEqual(outcome.hit_target_flag, 1)
        self.assertEqual(outcome.hit_invalidation_flag, 0)
        self.assertAlmostEqual(outcome.invalidation_price or 0, 103.0)

    def test_etf_invalidation_is_tighter_than_equity_invalidation(self) -> None:
        database_path = self.fresh_database_path("phase7b_etf_invalidation.sqlite")
        config = make_config(database_path)
        initialize_database(database_path)
        seed_alert(
            database_path,
            ticker="SPY",
            alert_type="etf_nav_discount_dislocation",
            asset_type="etf",
            current_price=100,
            base_target=120,
        )
        seed_alert(
            database_path,
            ticker="MSFT",
            alert_type="bullish_divergence",
            asset_type="equity",
            current_price=100,
            base_target=120,
        )
        next_day = Price(
            ticker="SPY",
            price_date="2026-01-11",
            open=98,
            high=99,
            low=96.5,
            close=98,
            adjusted_close=98,
            volume=1_000_000,
            source="fixture",
            as_of_date="2026-01-11",
            effective_date="2026-01-11",
        )
        upsert_prices(database_path, [next_day])
        upsert_prices(database_path, [Price(**{**next_day.__dict__, "ticker": "MSFT"})])

        update_alert_outcomes(config)
        outcomes = {item.ticker: item for item in list_alert_outcomes(database_path)}

        self.assertEqual(outcomes["SPY"].hit_invalidation_flag, 1)
        self.assertEqual(outcomes["MSFT"].hit_invalidation_flag, 0)
        self.assertAlmostEqual(outcomes["SPY"].invalidation_price or 0, 97.0)
        self.assertAlmostEqual(outcomes["MSFT"].invalidation_price or 0, 90.0)

    def test_etf_risk_warning_is_diagnostic(self) -> None:
        database_path = self.fresh_database_path("phase7b_etf_risk.sqlite")
        config = make_config(database_path)
        initialize_database(database_path)
        seed_alert(
            database_path,
            ticker="QQQ",
            alert_type="etf_risk_warning",
            asset_type="etf",
            current_price=100,
            base_target=110,
        )
        seed_prices(database_path, "QQQ", days=5, direction="up")

        update_alert_outcomes(config, ticker="QQQ")
        outcome = list_alert_outcomes(database_path, "QQQ")[0]

        self.assertIsNone(outcome.target_price)
        self.assertIsNone(outcome.invalidation_price)
        self.assertIsNone(outcome.hit_target_flag)
        self.assertIsNone(outcome.hit_invalidation_flag)

    def test_cli_status_validation_report_and_daily_report_include_outcomes(self) -> None:
        database_path = self.fresh_database_path("phase7a_cli.sqlite")
        config = make_config(database_path)
        write_config(config)
        initialize_database(database_path)
        seed_alert(database_path, ticker="MSFT", alert_type="bullish_divergence")
        seed_prices(database_path, "MSFT", days=5)

        update_output = io.StringIO()
        with redirect_stdout(update_output):
            update_exit = command_update_alert_outcomes(
                Namespace(config=config.config_path, ticker=None)
            )
        outcome_output = io.StringIO()
        with redirect_stdout(outcome_output):
            outcome_exit = command_outcome_status(Namespace(config=config.config_path))
        validation_output = io.StringIO()
        with redirect_stdout(validation_output):
            validation_exit = command_validation_report(Namespace(config=config.config_path))
        status_output = io.StringIO()
        with redirect_stdout(status_output):
            status_exit = command_status(Namespace(config=config.config_path))
        report = write_daily_report(config, run_date=date.today())
        body = report.path.read_text(encoding="utf-8")

        self.assertEqual(update_exit, 0)
        self.assertEqual(outcome_exit, 0)
        self.assertEqual(validation_exit, 0)
        self.assertEqual(status_exit, 0)
        self.assertIn("Alert outcomes updated", update_output.getvalue())
        self.assertIn("Ticker | Type | Alert | Outcome", outcome_output.getvalue())
        self.assertIn("Alert Outcome Validation Report", validation_output.getvalue())
        self.assertIn("Outcome rows: 1", status_output.getvalue())
        self.assertIn("Outcome Validation Summary", body)
        self.assertIn("outcome_status", REPORT_CSV_COLUMNS)
        self.assertIn("return_5d", REPORT_CSV_COLUMNS)


if __name__ == "__main__":
    unittest.main()
