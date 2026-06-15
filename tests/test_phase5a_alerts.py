from __future__ import annotations

from argparse import Namespace
from contextlib import redirect_stdout
from datetime import date
from pathlib import Path
import io
import sys
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
TEST_TMP_ROOT = PROJECT_ROOT / ".tmp_tests"
sys.path.insert(0, str(SRC_PATH))

from support import sqlite_connection_for_test
from target_opportunity_monitor.alerts import compute_alerts
from target_opportunity_monitor.cli import command_alert_status, command_compute_alerts
from target_opportunity_monitor.config import AppConfig, load_config
from target_opportunity_monitor.db import initialize_database
from target_opportunity_monitor.reporting import build_daily_report_body
from target_opportunity_monitor.storage import (
    Alert,
    Asset,
    EtfFeature,
    PriceFeature,
    Score,
    Target,
    alert_statuses,
    count_rows_by_table,
    latest_alert_timestamp,
    list_alerts,
    upsert_alert,
    upsert_asset,
    upsert_etf_feature,
    upsert_price_feature,
    upsert_score,
    upsert_target,
)


def make_config(database_path: Path) -> AppConfig:
    return AppConfig(
        project_root=TEST_TMP_ROOT,
        config_path=TEST_TMP_ROOT / "phase5a.toml",
        database_path=database_path,
        reports_dir=TEST_TMP_ROOT / "reports_phase5a",
        watchlist_path=TEST_TMP_ROOT / "watchlist_phase5a.csv",
        market_data_dir=TEST_TMP_ROOT / "market_data_phase5a",
        manual_prices_dir=TEST_TMP_ROOT / "market_data_phase5a" / "manual",
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
                "[alerts]",
                f'equity_model_version = "{config.alerts_equity_model_version}"',
                f'equity_threshold_set = "{config.alerts_equity_threshold_set}"',
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


def seed_alert_fixture(
    database_path: Path,
    ticker: str = "AAPL",
    current_price: float = 90,
    target_low: float = 95,
    base_target: float = 120,
    target_high: float = 150,
    valuation_gap: float = 0.25,
    opportunity_score: float = 75,
    expected_value_score: float = 78,
    confidence_score: float = 80,
    liquidity_score: float = 90,
    risk_score: float = 60,
    data_warnings: str | None = "missing_revision_data",
) -> None:
    today = date.today().isoformat()
    initialize_database(database_path)
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
            risk_score=risk_score,
            liquidity_score=liquidity_score,
            confidence_score=confidence_score,
            timing_score=65,
            expected_value_score=expected_value_score,
            opportunity_score=opportunity_score,
            asset_type="equity",
            score_model="equity_score_mvp_v1",
            threshold_set="equity_default",
            data_warnings=data_warnings,
            model_version="equity_score_mvp_v1",
            source="scoring",
        ),
    )


def seed_etf_alert_fixture(
    database_path: Path,
    ticker: str = "SPY",
    nav_per_share: float = 101.0,
    etf_market_price: float = 100.0,
    price_feature_price: float = 80.0,
    premium_discount_zscore: float | None = -1.0,
    holdings_count: int | None = 10,
    opportunity_score: float = 75.0,
    liquidity_score: float = 90.0,
    risk_score: float = 65.0,
    target: bool = True,
    score: bool = True,
    feature: bool = True,
) -> None:
    today = date.today().isoformat()
    initialize_database(database_path)
    upsert_asset(database_path, Asset(ticker=ticker, asset_type="etf"))
    upsert_price_feature(
        database_path,
        PriceFeature(
            ticker=ticker,
            feature_date=today,
            current_price=price_feature_price,
            return_1d=0.001,
            return_1m=0.01,
            return_3m=0.02,
            return_6m=0.04,
            return_12m=0.08,
            realized_volatility_20d=0.08,
            realized_volatility_60d=0.10,
            average_dollar_volume_20d=2_000_000_000,
            latest_price_date=today,
        ),
    )
    if feature:
        upsert_etf_feature(
            database_path,
            EtfFeature(
                ticker=ticker,
                feature_date=today,
                nav_per_share=nav_per_share,
                market_price=etf_market_price,
                premium_discount=etf_market_price / nav_per_share - 1,
                premium_discount_average_60d=0.0 if premium_discount_zscore is not None else None,
                premium_discount_volatility_60d=0.01 if premium_discount_zscore is not None else None,
                premium_discount_zscore=premium_discount_zscore,
                holdings_count=holdings_count,
                top_10_weight=0.30,
                largest_holding_weight=0.08,
                equity_weight=0.99,
                cash_weight=0.01,
                latest_nav_date=today,
                latest_holdings_date=today,
            ),
        )
    if target:
        upsert_target(
            database_path,
            Target(
                ticker=ticker,
                target_date=today,
                base_target=nav_per_share,
                target_low=nav_per_share * 0.995,
                target_high=nav_per_share * 1.005,
                valuation_gap=nav_per_share / etf_market_price - 1,
                target_method="etf_nav",
                uncertainty_band=0.005,
                valuation_confidence=75,
                method_count=1,
                model_version="etf_nav_mvp_v1",
                source="etf_valuation",
            ),
        )
    if score:
        upsert_score(
            database_path,
            Score(
                ticker=ticker,
                score_date=today,
                valuation_gap_score=75,
                quality_score=65,
                revision_score=50,
                momentum_score=55,
                risk_score=risk_score,
                liquidity_score=liquidity_score,
                confidence_score=80,
                timing_score=65,
                expected_value_score=70,
                opportunity_score=opportunity_score,
                asset_type="etf",
                score_model="etf_score_mvp_v1",
                threshold_set="etf_liquid_index",
                data_warnings=(
                    "missing_premium_discount_zscore"
                    if premium_discount_zscore is None
                    else None
                ),
                model_version="etf_score_mvp_v1",
                source="scoring",
            ),
        )


class Phase5AAlertTests(unittest.TestCase):
    def setUp(self) -> None:
        TEST_TMP_ROOT.mkdir(exist_ok=True)

    def fresh_database_path(self, name: str) -> Path:
        path = TEST_TMP_ROOT / name
        if path.exists():
            path.unlink()
        return path

    def test_db_init_migrates_alert_metadata_columns_and_index(self) -> None:
        database_path = self.fresh_database_path("phase5a_schema.sqlite")

        initialize_database(database_path)
        initialize_database(database_path)

        with sqlite_connection_for_test(database_path) as connection:
            columns = {
                row[1]
                for row in connection.execute("PRAGMA table_info(alerts)").fetchall()
            }
            indexes = {
                row[1]
                for row in connection.execute("PRAGMA index_list(alerts)").fetchall()
            }
        self.assertIn("asset_type", columns)
        self.assertIn("alert_model", columns)
        self.assertIn("threshold_set", columns)
        self.assertIn("reason_codes", columns)
        self.assertIn("risk_codes", columns)
        self.assertIn("dedupe_key", columns)
        self.assertIn("idx_alerts_dedupe_key", indexes)

    def test_config_loads_alert_defaults(self) -> None:
        config = load_config(PROJECT_ROOT / "configs" / "default.toml")

        self.assertEqual(config.alerts_equity_model_version, "equity_alert_mvp_v1")
        self.assertEqual(config.alerts_equity_threshold_set, "equity_default")
        self.assertEqual(config.alerts_minimum_bullish_valuation_gap, 0.10)
        self.assertEqual(config.alerts_minimum_expected_value_score, 70)
        self.assertEqual(config.alerts_watch_gap_threshold, 0.15)
        self.assertEqual(config.alerts_etf_model_version, "etf_alert_mvp_v1")
        self.assertEqual(config.alerts_etf_threshold_set, "etf_liquid_index")
        self.assertEqual(config.alerts_etf_action_nav_discount_gap, 0.005)

    def test_alert_upsert_list_and_latest_are_idempotent(self) -> None:
        database_path = self.fresh_database_path("phase5a_storage.sqlite")
        initialize_database(database_path)
        alert = Alert(
            ticker="AAPL",
            alert_type="bullish_divergence",
            alert_timestamp="2026-06-07T09:30:00",
            priority="high",
            current_price=90,
            base_target=120,
            target_low=95,
            target_high=150,
            required_gap=0.10,
            opportunity_score=75,
            confidence_score=80,
            timing_score=65,
            risk_score=60,
            alert_model="equity_alert_mvp_v1",
            threshold_set="equity_default",
            model_version="equity_alert_mvp_v1",
            dedupe_key="2026-06-07:AAPL:bullish_divergence:equity_alert_mvp_v1",
        )

        upsert_alert(database_path, alert)
        upsert_alert(database_path, alert)

        alerts = list_alerts(database_path, "AAPL")
        self.assertEqual(len(alerts), 1)
        self.assertEqual(count_rows_by_table(database_path, "alerts"), 1)
        self.assertEqual(latest_alert_timestamp(database_path), "2026-06-07T09:30:00")

    def test_bullish_alert_allows_missing_revision_data_as_risk_code(self) -> None:
        database_path = self.fresh_database_path("phase5a_bullish.sqlite")
        config = make_config(database_path)
        seed_alert_fixture(database_path, ticker="MSFT")

        result = compute_alerts(config, ticker="MSFT")
        alerts = list_alerts(database_path, "MSFT")

        self.assertEqual(result.alert_count, 1)
        self.assertEqual(result.warning_count, 0)
        self.assertEqual(alerts[0].alert_type, "bullish_divergence")
        self.assertEqual(alerts[0].risk_codes, "missing_revision_data")
        self.assertIsNone(alerts[0].data_warnings)

    def test_watch_only_gap_alert(self) -> None:
        database_path = self.fresh_database_path("phase5a_watch.sqlite")
        config = make_config(database_path)
        seed_alert_fixture(
            database_path,
            ticker="NVDA",
            current_price=100,
            target_low=80,
            valuation_gap=0.40,
            opportunity_score=80,
        )

        result = compute_alerts(config, ticker="NVDA")

        self.assertEqual(result.alert_count, 1)
        self.assertEqual(list_alerts(database_path, "NVDA")[0].alert_type, "watch_only_gap")

    def test_bearish_overvaluation_alert(self) -> None:
        database_path = self.fresh_database_path("phase5a_bearish.sqlite")
        config = make_config(database_path)
        seed_alert_fixture(
            database_path,
            ticker="AAPL",
            current_price=170,
            target_low=90,
            base_target=120,
            target_high=150,
            valuation_gap=-0.20,
            opportunity_score=35,
            expected_value_score=30,
        )

        result = compute_alerts(config, ticker="AAPL")

        self.assertEqual(result.alert_count, 1)
        self.assertEqual(list_alerts(database_path, "AAPL")[0].alert_type, "bearish_overvaluation")

    def test_risk_warning_alert(self) -> None:
        database_path = self.fresh_database_path("phase5a_risk.sqlite")
        config = make_config(database_path)
        seed_alert_fixture(database_path, ticker="AAPL", risk_score=25)

        result = compute_alerts(config, ticker="AAPL")

        self.assertEqual(result.alert_count, 1)
        self.assertEqual(list_alerts(database_path, "AAPL")[0].alert_type, "risk_warning")

    def test_data_quality_warning_for_missing_required_inputs(self) -> None:
        database_path = self.fresh_database_path("phase5a_quality.sqlite")
        config = make_config(database_path)
        initialize_database(database_path)
        upsert_asset(database_path, Asset(ticker="AAPL", asset_type="equity"))

        result = compute_alerts(config, ticker="AAPL")
        alert = list_alerts(database_path, "AAPL")[0]

        self.assertEqual(result.alert_count, 1)
        self.assertEqual(alert.alert_type, "data_quality_warning")
        self.assertIn("missing_price_feature", alert.data_warnings or "")
        self.assertIsNotNone(alert.data_quality_score)
        assert alert.data_quality_score is not None
        self.assertLess(alert.data_quality_score, 75)

    def test_no_alert_and_etf_data_quality_warning(self) -> None:
        database_path = self.fresh_database_path("phase5a_no_alert.sqlite")
        config = make_config(database_path)
        seed_alert_fixture(
            database_path,
            ticker="AAPL",
            current_price=100,
            target_low=80,
            valuation_gap=0.02,
            opportunity_score=55,
            expected_value_score=55,
        )
        upsert_asset(database_path, Asset(ticker="SPY", asset_type="etf"))

        result = compute_alerts(config)
        by_ticker = {item.ticker: item for item in result.results}

        self.assertEqual(by_ticker["AAPL"].status, "no_alert")
        self.assertEqual(list_alerts(database_path, "AAPL")[0].alert_type, "no_alert")
        self.assertEqual(by_ticker["SPY"].status, "alerted")
        self.assertEqual(by_ticker["SPY"].alert_type, "data_quality_warning")
        self.assertIn("missing_etf_feature", by_ticker["SPY"].warnings)

    def test_etf_nav_discount_dislocation_alert_uses_feature_market_price(self) -> None:
        database_path = self.fresh_database_path("phase5b_etf_dislocation.sqlite")
        config = make_config(database_path)
        seed_etf_alert_fixture(
            database_path,
            ticker="SPY",
            nav_per_share=101,
            etf_market_price=100,
            price_feature_price=80,
        )

        result = compute_alerts(config, ticker="SPY")
        alert = list_alerts(database_path, "SPY")[0]

        self.assertEqual(result.alert_count, 1)
        self.assertEqual(alert.alert_type, "etf_nav_discount_dislocation")
        self.assertEqual(alert.asset_type, "etf")
        self.assertEqual(alert.alert_model, "etf_alert_mvp_v1")
        self.assertEqual(alert.threshold_set, "etf_liquid_index")
        self.assertAlmostEqual(alert.current_price or 0, 100)
        self.assertAlmostEqual(alert.valuation_gap or 0, 0.01)

    def test_etf_nav_discount_watch_alert(self) -> None:
        database_path = self.fresh_database_path("phase5b_etf_watch.sqlite")
        config = make_config(database_path)
        seed_etf_alert_fixture(
            database_path,
            ticker="QQQ",
            nav_per_share=100.2,
            etf_market_price=100,
            opportunity_score=60,
        )

        result = compute_alerts(config, ticker="QQQ")

        self.assertEqual(result.alert_count, 1)
        self.assertEqual(list_alerts(database_path, "QQQ")[0].alert_type, "etf_nav_discount_watch")

    def test_etf_nav_premium_warning_alert(self) -> None:
        database_path = self.fresh_database_path("phase5b_etf_premium.sqlite")
        config = make_config(database_path)
        seed_etf_alert_fixture(
            database_path,
            ticker="QQQ",
            nav_per_share=99,
            etf_market_price=100,
        )

        result = compute_alerts(config, ticker="QQQ")

        self.assertEqual(result.alert_count, 1)
        self.assertEqual(list_alerts(database_path, "QQQ")[0].alert_type, "etf_nav_premium_warning")

    def test_etf_risk_warning_alert(self) -> None:
        database_path = self.fresh_database_path("phase5b_etf_risk.sqlite")
        config = make_config(database_path)
        seed_etf_alert_fixture(
            database_path,
            ticker="SPY",
            nav_per_share=100,
            etf_market_price=100,
            risk_score=40,
        )

        result = compute_alerts(config, ticker="SPY")
        alert = list_alerts(database_path, "SPY")[0]

        self.assertEqual(result.alert_count, 1)
        self.assertEqual(alert.alert_type, "etf_risk_warning")
        self.assertIn("low_etf_risk_score", alert.risk_codes or "")

    def test_etf_no_alert_with_missing_premium_zscore_warning(self) -> None:
        database_path = self.fresh_database_path("phase5b_etf_no_alert.sqlite")
        config = make_config(database_path)
        seed_etf_alert_fixture(
            database_path,
            ticker="QQQ",
            nav_per_share=100,
            etf_market_price=100,
            premium_discount_zscore=None,
        )

        result = compute_alerts(config, ticker="QQQ")
        alert = list_alerts(database_path, "QQQ")[0]

        self.assertEqual(result.alert_count, 0)
        self.assertEqual(result.warning_count, 1)
        self.assertEqual(alert.alert_type, "no_alert")
        self.assertIn("missing_premium_discount_zscore", alert.data_warnings or "")

    def test_etf_missing_score_warns_without_crashing(self) -> None:
        database_path = self.fresh_database_path("phase5b_etf_missing_score.sqlite")
        config = make_config(database_path)
        seed_etf_alert_fixture(database_path, ticker="SPY", score=False)

        result = compute_alerts(config, ticker="SPY")

        self.assertEqual(result.alert_count, 1)
        self.assertEqual(list_alerts(database_path, "SPY")[0].alert_type, "data_quality_warning")
        self.assertIn("missing_score", result.results[0].warnings)

    def test_compute_alerts_filters_ticker_and_asset_type(self) -> None:
        database_path = self.fresh_database_path("phase5a_filter.sqlite")
        config = make_config(database_path)
        seed_alert_fixture(database_path, ticker="AAPL")
        seed_alert_fixture(database_path, ticker="MSFT")
        seed_etf_alert_fixture(database_path, ticker="SPY")

        ticker_result = compute_alerts(config, ticker="AAPL")
        equity_result = compute_alerts(config, asset_type="equity")
        etf_result = compute_alerts(config, asset_type="etf")

        self.assertEqual([item.ticker for item in ticker_result.results], ["AAPL"])
        self.assertEqual([item.ticker for item in equity_result.results], ["AAPL", "MSFT"])
        self.assertEqual([item.ticker for item in etf_result.results], ["SPY"])

    def test_alert_cli_status_and_report_output(self) -> None:
        database_path = self.fresh_database_path("phase5a_cli.sqlite")
        config = make_config(database_path)
        write_config(config)
        seed_alert_fixture(database_path, ticker="MSFT")

        compute_output = io.StringIO()
        with redirect_stdout(compute_output):
            compute_exit = command_compute_alerts(
                Namespace(config=config.config_path, ticker="MSFT", asset_type=None)
            )
        status_output = io.StringIO()
        with redirect_stdout(status_output):
            status_exit = command_alert_status(Namespace(config=config.config_path))
        report = build_daily_report_body(
            config,
            database_status=initialize_database(database_path),
            run_date=date.today(),
        )

        self.assertEqual(compute_exit, 0)
        self.assertEqual(status_exit, 0)
        self.assertIn("bullish_divergence", compute_output.getvalue())
        self.assertIn("Alert | Priority", status_output.getvalue())
        self.assertIn("Alert Summary", report)
        self.assertIn("bullish_divergence", report)
        self.assertTrue(alert_statuses(database_path)[0].alert_type)


if __name__ == "__main__":
    unittest.main()
