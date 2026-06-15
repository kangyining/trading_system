from __future__ import annotations

from argparse import Namespace
from contextlib import redirect_stdout
from dataclasses import replace
import io
import os
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

from target_opportunity_monitor.db import initialize_database
from target_opportunity_monitor.notifications import (
    deliver_notifications,
    test_notification_channel,
)
from target_opportunity_monitor.pipeline import run_intraday_cycle
from target_opportunity_monitor.ranges import compute_range_snapshots
from target_opportunity_monitor.dashboard import build_dashboard
from target_opportunity_monitor.reporting import write_daily_report
from target_opportunity_monitor.cli import command_scheduler_status
from target_opportunity_monitor.storage import (
    count_rows_by_table,
    latest_pipeline_run,
    list_notification_events,
    notification_delivery_count,
    pending_notification_count,
)
from test_phase11a_ranges import make_config, seed_equity, write_config


class Phase11CTest(unittest.TestCase):
    def fresh_database_path(self, name: str) -> Path:
        TEST_TMP_ROOT.mkdir(parents=True, exist_ok=True)
        path = TEST_TMP_ROOT / name
        if path.exists():
            path.unlink()
        return path

    def make_phase11c_config(self, database_path: Path):
        return replace(
            make_config(database_path),
            notification_outbox_dir=TEST_TMP_ROOT / "phase11c_notification_outbox",
        )

    def test_file_delivery_writes_outbox_and_marks_events_delivered(self) -> None:
        database_path = self.fresh_database_path("phase11c_file_delivery.sqlite")
        config = self.make_phase11c_config(database_path)
        initialize_database(database_path)
        seed_equity(database_path, price=90)
        compute_range_snapshots(config, ticker="AAPL")

        result = deliver_notifications(config, channel="file")

        self.assertEqual(result.delivered_count, 1)
        self.assertEqual(result.failed_count, 0)
        self.assertEqual(pending_notification_count(database_path), 0)
        self.assertEqual(notification_delivery_count(database_path, status="delivered"), 1)
        self.assertEqual(len(result.outbox_paths), 2)
        for path in result.outbox_paths:
            self.assertTrue(path.exists())
        self.assertIn("AAPL", result.outbox_paths[0].read_text(encoding="utf-8"))

    def test_webhook_missing_url_records_failed_delivery_without_exposing_secret(self) -> None:
        database_path = self.fresh_database_path("phase11c_webhook_missing.sqlite")
        config = self.make_phase11c_config(database_path)
        initialize_database(database_path)
        seed_equity(database_path, price=90)
        compute_range_snapshots(config, ticker="AAPL")
        os.environ.pop("TOM_NOTIFICATION_WEBHOOK_URL", None)

        result = deliver_notifications(config, channel="webhook")

        self.assertEqual(result.delivered_count, 0)
        self.assertEqual(result.failed_count, 1)
        self.assertIn("missing_webhook_url", result.warnings)
        self.assertEqual(pending_notification_count(database_path), 0)
        self.assertEqual(notification_delivery_count(database_path, status="failed"), 1)
        self.assertEqual(len(list_notification_events(database_path, status="delivery_failed")), 1)
        self.assertNotIn("http", ";".join(result.warnings).lower())

    def test_notification_channel_file_test_writes_test_artifacts(self) -> None:
        database_path = self.fresh_database_path("phase11c_channel_test.sqlite")
        config = self.make_phase11c_config(database_path)
        initialize_database(database_path)

        result = test_notification_channel(config, channel="file")

        self.assertEqual(result.status, "ok")
        self.assertEqual(len(result.outbox_paths), 2)
        self.assertIn("TEST", result.outbox_paths[0].read_text(encoding="utf-8"))

    def test_intraday_cycle_runs_steps_and_optional_delivery(self) -> None:
        database_path = self.fresh_database_path("phase11c_cycle.sqlite")
        config = self.make_phase11c_config(database_path)
        initialize_database(database_path)

        with (
            patch(
                "target_opportunity_monitor.pipeline.update_quote_snapshots",
                return_value=SimpleNamespace(loaded_count=1, results=()),
            ) as quote_mock,
            patch(
                "target_opportunity_monitor.pipeline.compute_intraday_gaps",
                return_value=SimpleNamespace(updated_count=1, results=()),
            ) as gap_mock,
            patch(
                "target_opportunity_monitor.pipeline.compute_range_snapshots",
                return_value=SimpleNamespace(
                    updated_count=1,
                    notification_count=1,
                    results=(),
                ),
            ) as range_mock,
            patch(
                "target_opportunity_monitor.pipeline.deliver_notifications",
                return_value=SimpleNamespace(
                    delivered_count=1,
                    failed_count=0,
                    warnings=(),
                    outbox_paths=(),
                    events=(),
                ),
            ) as delivery_mock,
        ):
            result = run_intraday_cycle(
                config,
                ticker="AAPL",
                deliver=True,
                channel="file",
            )

        self.assertEqual(result.status, "ok")
        self.assertEqual(
            tuple(step.step_name for step in result.steps),
            (
                "update-quotes",
                "compute-live-gaps",
                "range-monitor",
                "deliver-notifications-file",
            ),
        )
        quote_mock.assert_called_once()
        gap_mock.assert_called_once()
        range_mock.assert_called_once()
        delivery_mock.assert_called_once()
        latest = latest_pipeline_run(database_path, run_type="intraday_cycle")
        self.assertIsNotNone(latest)
        self.assertEqual(latest.status, "ok")
        self.assertEqual(count_rows_by_table(database_path, "pipeline_step_results"), 4)

    def test_notification_status_pending_filter_has_pending_event(self) -> None:
        database_path = self.fresh_database_path("phase11c_pending.sqlite")
        config = self.make_phase11c_config(database_path)
        initialize_database(database_path)
        seed_equity(database_path, price=90)
        compute_range_snapshots(config, ticker="AAPL")

        pending = list_notification_events(database_path, status="pending")

        self.assertEqual(len(pending), 1)
        self.assertEqual(pending[0].ticker, "AAPL")

    def test_reports_and_dashboard_include_intraday_delivery_health(self) -> None:
        database_path = self.fresh_database_path("phase11c_outputs.sqlite")
        config = self.make_phase11c_config(database_path)
        initialize_database(database_path)
        seed_equity(database_path, price=90)
        compute_range_snapshots(config, ticker="AAPL")
        deliver_notifications(config, channel="file")

        report = write_daily_report(config)
        dashboard = build_dashboard(config)

        report_text = report.path.read_text(encoding="utf-8")
        dashboard_text = dashboard.path.read_text(encoding="utf-8")
        self.assertIn("Notification delivery rows", report_text)
        self.assertIn("Latest intraday cycle", report_text)
        self.assertIn("Latest Delivery", dashboard_text)
        self.assertIn("Delivery Failures", dashboard_text)

    def test_scheduler_status_handles_no_prior_runs(self) -> None:
        database_path = self.fresh_database_path("phase11d_scheduler_empty.sqlite")
        config = self.make_phase11c_config(database_path)
        write_config(config)
        initialize_database(database_path)

        output = io.StringIO()
        with redirect_stdout(output):
            exit_code = command_scheduler_status(Namespace(config=config.config_path))

        text = output.getvalue()
        self.assertEqual(exit_code, 0)
        self.assertIn("TOM Intraday Heartbeat", text)
        self.assertIn("Latest intraday cycle: none", text)
        self.assertIn("Pending notifications: 0", text)

    def test_scheduler_status_reports_intraday_and_delivery_state(self) -> None:
        database_path = self.fresh_database_path("phase11d_scheduler_live.sqlite")
        config = self.make_phase11c_config(database_path)
        write_config(config)
        initialize_database(database_path)
        seed_equity(database_path, price=90)
        compute_range_snapshots(config, ticker="AAPL")
        deliver_notifications(config, channel="file")
        with (
            patch(
                "target_opportunity_monitor.pipeline.update_quote_snapshots",
                return_value=SimpleNamespace(loaded_count=1, results=()),
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
            run_intraday_cycle(config, ticker="AAPL")

        output = io.StringIO()
        with redirect_stdout(output):
            exit_code = command_scheduler_status(Namespace(config=config.config_path))

        text = output.getvalue()
        self.assertEqual(exit_code, 0)
        self.assertIn("Latest intraday cycle: ok", text)
        self.assertIn("Failed notification deliveries: 0", text)
        self.assertIn("Latest successful delivery:", text)


if __name__ == "__main__":
    unittest.main()
