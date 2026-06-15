from __future__ import annotations

from dataclasses import replace
from datetime import date, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
import sys
import unittest
from unittest.mock import patch


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
TEST_TMP_ROOT = PROJECT_ROOT / ".tmp_tests"
sys.path.insert(0, str(SRC_PATH))
sys.path.insert(0, str(PROJECT_ROOT / "tests"))

from support import sqlite_connection_for_test
from target_opportunity_monitor.config import load_config
from target_opportunity_monitor.db import initialize_database
from target_opportunity_monitor.intraday_health import intraday_health
from target_opportunity_monitor.notifications import deliver_notifications
from target_opportunity_monitor.pipeline import run_intraday_cycle
from target_opportunity_monitor.ranges import compute_range_snapshots
from target_opportunity_monitor.storage import (
    QuoteSnapshot,
    RangeSnapshot,
    latest_quote_snapshot,
    list_notification_events,
    notification_delivery_count,
    pending_notification_count,
    upsert_quote_snapshot,
    upsert_range_snapshot,
)
from test_phase11a_ranges import make_config, seed_equity


class Phase11D1IntradayHealthTest(unittest.TestCase):
    def fresh_database_path(self, name: str) -> Path:
        TEST_TMP_ROOT.mkdir(parents=True, exist_ok=True)
        path = TEST_TMP_ROOT / name
        if path.exists():
            path.unlink()
        return path

    def make_config(self, database_path: Path):
        return replace(
            make_config(database_path),
            notification_outbox_dir=TEST_TMP_ROOT / "phase11d1_notification_outbox",
            realtime_quote_stale_after_seconds=900,
            realtime_intraday_cycle_stale_after_seconds=1800,
            realtime_notification_pending_stale_after_seconds=1800,
        )

    def insert_pipeline_run(
        self,
        database_path: Path,
        run_type: str,
        status: str,
        started_at: str,
    ) -> None:
        with sqlite_connection_for_test(database_path) as connection:
            connection.execute(
                """
                INSERT INTO pipeline_runs (
                    run_type, status, started_at, finished_at, source,
                    summary, as_of_date, effective_date
                )
                VALUES (?, ?, ?, ?, 'test', ?, ?, ?)
                """,
                (
                    run_type,
                    status,
                    started_at,
                    started_at,
                    f"{run_type}: status={status}",
                    date.today().isoformat(),
                    started_at,
                ),
            )
            connection.commit()

    def test_health_reports_stale_quote_and_cycle_during_regular_hours(self) -> None:
        database_path = self.fresh_database_path("phase11d1_stale.sqlite")
        config = self.make_config(database_path)
        initialize_database(database_path)
        now = datetime(2026, 6, 15, 10, 0, 0)
        old = (now - timedelta(hours=2)).isoformat(timespec="seconds")
        self.insert_pipeline_run(database_path, "intraday_cycle", "ok", old)
        upsert_quote_snapshot(
            database_path,
            QuoteSnapshot(ticker="AAPL", quote_timestamp=old, last=100, source="ibkr"),
        )
        upsert_range_snapshot(
            database_path,
            RangeSnapshot(ticker="AAPL", snapshot_timestamp=old, current_price=100),
        )

        health = intraday_health(config, now=now)

        self.assertEqual(health.status, "stale")
        self.assertEqual(health.market_session, "regular")
        self.assertTrue(health.regular_market_hours)
        self.assertIn("stale_quote", health.warnings)
        self.assertIn("stale_intraday_cycle", health.warnings)
        self.assertEqual(health.notes, ())
        self.assertEqual(health.blockers, ())

    def test_health_treats_weekend_stale_quote_and_cycle_as_expected(self) -> None:
        database_path = self.fresh_database_path("phase11d1_weekend.sqlite")
        config = self.make_config(database_path)
        initialize_database(database_path)
        now = datetime(2026, 6, 14, 18, 0, 0)
        old = (now - timedelta(hours=2)).isoformat(timespec="seconds")
        self.insert_pipeline_run(database_path, "intraday_cycle", "ok", old)
        upsert_quote_snapshot(
            database_path,
            QuoteSnapshot(ticker="AAPL", quote_timestamp=old, last=100, source="ibkr"),
        )
        upsert_range_snapshot(
            database_path,
            RangeSnapshot(ticker="AAPL", snapshot_timestamp=old, current_price=100),
        )

        health = intraday_health(config, now=now)

        self.assertEqual(health.status, "healthy")
        self.assertEqual(health.market_session, "weekend")
        self.assertFalse(health.regular_market_hours)
        self.assertNotIn("stale_quote", health.warnings)
        self.assertNotIn("stale_intraday_cycle", health.warnings)
        self.assertIn("off_hours_quote_staleness_expected", health.notes)
        self.assertIn("off_hours_intraday_cycle_staleness_expected", health.notes)
        self.assertEqual(health.blockers, ())

    def test_health_still_blocks_missing_quote_and_range_off_hours(self) -> None:
        database_path = self.fresh_database_path("phase11d1_off_hours_blocked.sqlite")
        config = self.make_config(database_path)
        initialize_database(database_path)
        now = datetime(2026, 6, 14, 18, 0, 0)
        started_at = (now - timedelta(hours=2)).isoformat(timespec="seconds")
        self.insert_pipeline_run(database_path, "intraday_cycle", "ok", started_at)

        health = intraday_health(config, now=now)

        self.assertEqual(health.status, "blocked")
        self.assertEqual(health.market_session, "weekend")
        self.assertIn("missing_quote", health.blockers)
        self.assertIn("missing_range_snapshot", health.blockers)
        self.assertEqual(health.warnings, ())

    def test_health_reports_healthy_when_fresh_and_delivered(self) -> None:
        database_path = self.fresh_database_path("phase11d1_healthy.sqlite")
        config = self.make_config(database_path)
        initialize_database(database_path)
        now = datetime.now().isoformat(timespec="seconds")
        self.insert_pipeline_run(database_path, "intraday_cycle", "ok", now)
        upsert_quote_snapshot(
            database_path,
            QuoteSnapshot(ticker="AAPL", quote_timestamp=now, last=100, source="ibkr"),
        )
        upsert_range_snapshot(
            database_path,
            RangeSnapshot(ticker="AAPL", snapshot_timestamp=now, current_price=100),
        )

        health = intraday_health(config)

        self.assertEqual(health.status, "healthy")
        self.assertEqual(health.warnings, ())
        self.assertEqual(health.pending_notification_count, 0)

    def test_file_drain_marks_pending_events_delivered(self) -> None:
        database_path = self.fresh_database_path("phase11d1_drain.sqlite")
        config = self.make_config(database_path)
        initialize_database(database_path)
        seed_equity(database_path, price=90)
        compute_range_snapshots(config, ticker="AAPL")
        self.assertEqual(pending_notification_count(database_path), 1)

        result = deliver_notifications(config, channel="file")

        self.assertEqual(result.delivered_count, 1)
        self.assertEqual(pending_notification_count(database_path), 0)
        self.assertEqual(notification_delivery_count(database_path, status="delivered"), 1)
        self.assertEqual(list_notification_events(database_path, status="pending"), [])

    def test_auto_intraday_cycle_uses_daily_price_fallback_when_ibkr_empty(self) -> None:
        database_path = self.fresh_database_path("phase11d1_auto_fallback.sqlite")
        config = self.make_config(database_path)
        initialize_database(database_path)
        seed_equity(database_path, price=90)
        with sqlite_connection_for_test(database_path) as connection:
            connection.execute("DELETE FROM quote_snapshots")
            connection.commit()

        with (
            patch(
                "target_opportunity_monitor.pipeline.update_quote_snapshots",
                return_value=SimpleNamespace(
                    loaded_count=0,
                    results=(
                        SimpleNamespace(
                            ticker="AAPL",
                            warnings=("connect_failed:test",),
                        ),
                    ),
                ),
            ),
            patch(
                "target_opportunity_monitor.pipeline.update_prices",
                return_value=SimpleNamespace(loaded_count=0, results=()),
            ),
            patch(
                "target_opportunity_monitor.pipeline.compute_intraday_gaps",
                return_value=SimpleNamespace(updated_count=1, results=()),
            ),
            patch(
                "target_opportunity_monitor.pipeline.compute_range_snapshots",
                return_value=SimpleNamespace(
                    updated_count=1,
                    notification_count=0,
                    results=(),
                ),
            ),
        ):
            result = run_intraday_cycle(config, source="auto", ticker="AAPL")

        self.assertEqual(result.status, "ok")
        first_step = result.steps[0]
        self.assertEqual(first_step.rows_loaded, 1)
        self.assertIn("auto_quote_fallback_used", first_step.warnings)
        latest_quote = latest_quote_snapshot(database_path, "AAPL")
        self.assertIsNotNone(latest_quote)
        self.assertEqual(latest_quote.source, "daily_price_fallback")

    def test_config_loads_phase11d1_defaults(self) -> None:
        config = load_config(PROJECT_ROOT / "configs" / "default.toml")

        self.assertEqual(config.realtime_intraday_cycle_stale_after_seconds, 1800)
        self.assertEqual(config.realtime_notification_pending_stale_after_seconds, 1800)


if __name__ == "__main__":
    unittest.main()
