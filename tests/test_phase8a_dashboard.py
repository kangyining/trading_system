from __future__ import annotations

from argparse import Namespace
from contextlib import redirect_stdout
from datetime import date, timedelta
from pathlib import Path
import io
import json
import re
import sys
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
TEST_TMP_ROOT = PROJECT_ROOT / ".tmp_tests"
sys.path.insert(0, str(SRC_PATH))

from target_opportunity_monitor.cli import command_build_dashboard, command_status
from target_opportunity_monitor.config import AppConfig
from target_opportunity_monitor.dashboard import build_dashboard, latest_dashboard_path
from target_opportunity_monitor.db import initialize_database
from target_opportunity_monitor.pipeline import run_refresh_data
from target_opportunity_monitor.storage import (
    Alert,
    AlertOutcome,
    Asset,
    Price,
    upsert_alert,
    upsert_alert_outcome,
    upsert_asset,
    upsert_prices,
)
from support import patch_refresh_pipeline_for_test


def make_config(database_path: Path) -> AppConfig:
    return AppConfig(
        project_root=TEST_TMP_ROOT,
        config_path=TEST_TMP_ROOT / "phase8a.toml",
        database_path=database_path,
        reports_dir=TEST_TMP_ROOT / "reports_phase8a",
        watchlist_path=TEST_TMP_ROOT / "watchlist_phase8a.csv",
        market_data_dir=TEST_TMP_ROOT / "market_data_phase8a",
        manual_prices_dir=TEST_TMP_ROOT / "market_data_phase8a" / "manual",
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
                f'project_root = "{config.project_root.as_posix()}"',
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


def seed_prices(database_path: Path, ticker: str, start_price: float) -> None:
    start_date = date(2026, 1, 1)
    prices = [
        make_price(ticker, (start_date + timedelta(days=offset)).isoformat(), start_price + offset)
        for offset in range(10)
    ]
    upsert_prices(database_path, prices)


def seed_dashboard_fixture(database_path: Path) -> None:
    initialize_database(database_path)
    for ticker in ("AAPL", "MSFT", "NVDA"):
        upsert_asset(database_path, Asset(ticker=ticker, asset_type="equity"))
        seed_prices(database_path, ticker, 100)
    for ticker in ("QQQ", "SPY"):
        upsert_asset(database_path, Asset(ticker=ticker, asset_type="etf"))
        seed_prices(database_path, ticker, 400)

    upsert_alert(
        database_path,
        Alert(
            ticker="MSFT",
            alert_type="bullish_divergence",
            alert_timestamp="2026-01-10T09:30:00",
            priority="high",
            status="open",
            asset_type="equity",
            current_price=109,
            base_target=130,
            target_low=115,
            target_high=150,
            valuation_gap=0.20,
            opportunity_score=78,
            confidence_score=82,
            timing_score=65,
            risk_score=58,
            liquidity_score=90,
            data_quality_score=100,
            main_reasons="Fixture bullish gap.",
            main_risks="Fixture risk.",
            reason_codes="fixture_reason",
            risk_codes="missing_revision_data",
            invalidation="Fixture invalidation.",
            alert_model="equity_alert_mvp_v1",
            threshold_set="equity_default",
            model_version="equity_alert_mvp_v1",
            dedupe_key="2026-01-10:MSFT:bullish",
        ),
    )
    upsert_alert_outcome(
        database_path,
        AlertOutcome(
            alert_id=1,
            outcome_date=date.today().isoformat(),
            ticker="MSFT",
            alert_type="bullish_divergence",
            alert_timestamp="2026-01-10T09:30:00",
            outcome_status="pending",
            entry_price=109,
            entry_price_date="2026-01-10",
            latest_price=109,
            latest_price_date="2026-01-10",
            pending_horizons="5d,20d,60d,120d",
        ),
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


class Phase8ADashboardTests(unittest.TestCase):
    def setUp(self) -> None:
        TEST_TMP_ROOT.mkdir(exist_ok=True)

    def fresh_database_path(self, name: str) -> Path:
        path = TEST_TMP_ROOT / name
        if path.exists():
            path.unlink()
        return path

    def test_build_dashboard_writes_self_contained_html(self) -> None:
        database_path = self.fresh_database_path("phase8a_dashboard.sqlite")
        config = make_config(database_path)
        seed_dashboard_fixture(database_path)

        result = build_dashboard(config)
        html = result.path.read_text(encoding="utf-8")

        self.assertTrue(result.path.exists())
        self.assertEqual(result.path.name, "index.html")
        self.assertIn("Daily Alerts", html)
        self.assertIn("Watchlist Ranking", html)
        self.assertIn("Ticker Detail", html)
        self.assertIn("Price vs Target", html)
        self.assertIn("Outcome Status", html)
        self.assertIn("Data Health", html)
        self.assertIn("Model Health", html)
        self.assertNotIn("http://", html)
        self.assertNotIn("https://", html)

    def test_dashboard_data_contains_equities_etfs_alerts_outcomes_and_health(self) -> None:
        database_path = self.fresh_database_path("phase8a_data.sqlite")
        config = make_config(database_path)
        seed_dashboard_fixture(database_path)

        result = build_dashboard(config)
        data = dashboard_data(result.path.read_text(encoding="utf-8"))
        tickers = {row["ticker"] for row in data["rows"]}
        by_ticker = {row["ticker"]: row for row in data["rows"]}

        self.assertEqual(tickers, {"AAPL", "MSFT", "NVDA", "QQQ", "SPY"})
        self.assertEqual(by_ticker["MSFT"]["alert_type"], "bullish_divergence")
        self.assertEqual(by_ticker["MSFT"]["outcome_status"], "pending")
        self.assertEqual(by_ticker["QQQ"]["alert_type"], "not_evaluated")
        self.assertNotIn("etf_alerts_gated", by_ticker["SPY"]["model_warnings"] or "")
        self.assertTrue(data["alert_history"])
        self.assertTrue(data["outcomes"])
        self.assertIn("table_counts", data["health"])
        self.assertIn("intraday_market_session", data["health"])
        self.assertIn("intraday_regular_market_hours", data["health"])
        self.assertIn("intraday_health_notes", data["health"])
        self.assertIn("MSFT", data["price_history"])

    def test_cli_build_dashboard_and_status_report_dashboard_path(self) -> None:
        database_path = self.fresh_database_path("phase8a_cli.sqlite")
        config = make_config(database_path)
        write_config(config)
        seed_dashboard_fixture(database_path)

        build_output = io.StringIO()
        with redirect_stdout(build_output):
            build_exit = command_build_dashboard(Namespace(config=config.config_path))
        status_output = io.StringIO()
        with redirect_stdout(status_output):
            status_exit = command_status(Namespace(config=config.config_path))

        self.assertEqual(build_exit, 0)
        self.assertEqual(status_exit, 0)
        self.assertIn("Dashboard written", build_output.getvalue())
        self.assertIn("Latest dashboard:", status_output.getvalue())
        self.assertIn("dashboard", status_output.getvalue())
        self.assertEqual(latest_dashboard_path(config.project_root), config.project_root / "dashboard" / "index.html")

    def test_refresh_data_includes_build_dashboard_step(self) -> None:
        database_path = self.fresh_database_path("phase8a_pipeline.sqlite")
        config = make_config(database_path)
        initialize_database(database_path)
        config.watchlist_path.write_text("ticker,asset_type\nAAPL,equity\n", encoding="utf-8")

        with patch_refresh_pipeline_for_test():
            result = run_refresh_data(config, skip_ibkr=True)

        self.assertEqual(result.status, "ok")
        self.assertIn("build-dashboard", [step.step_name for step in result.steps])


if __name__ == "__main__":
    unittest.main()
