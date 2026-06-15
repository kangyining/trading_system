from __future__ import annotations

from dataclasses import replace
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

from target_opportunity_monitor.config import load_config
from target_opportunity_monitor.db import initialize_database
from target_opportunity_monitor.notifications import (
    build_notification_delivery_report_text,
)
from target_opportunity_monitor.pipeline import run_intraday_cycle
from target_opportunity_monitor.ranges import compute_range_snapshots
from target_opportunity_monitor.scheduler import (
    INTRADAY_HEARTBEAT_COMMAND,
    audit_scheduler,
    build_scheduler_repair_plan_text,
)
from target_opportunity_monitor.storage import (
    list_notification_events,
    notification_delivery_count,
    pending_notification_count,
)
from test_phase11a_ranges import make_config, seed_equity


def _automation_toml(
    automation_id: str,
    name: str,
    kind: str,
    prompt: str,
    status: str = "ACTIVE",
) -> str:
    return "\n".join(
        (
            "version = 1",
            f'id = "{automation_id}"',
            f'kind = "{kind}"',
            f'name = "{name}"',
            f'prompt = "{prompt}"',
            f'status = "{status}"',
            'rrule = "FREQ=MINUTELY;INTERVAL=10"',
            "",
        )
    )


class Phase11D2SchedulerReconciliationTest(unittest.TestCase):
    def fresh_database_path(self, name: str) -> Path:
        TEST_TMP_ROOT.mkdir(parents=True, exist_ok=True)
        path = TEST_TMP_ROOT / name
        if path.exists():
            path.unlink()
        return path

    def make_config(self, database_path: Path, automations_dir: Path | None = None):
        return replace(
            make_config(database_path),
            notification_outbox_dir=TEST_TMP_ROOT / "phase11d2_notification_outbox",
            scheduler_automations_dir=(
                automations_dir or TEST_TMP_ROOT / "phase11d2_automations"
            ),
        )

    def write_automation(
        self,
        automations_dir: Path,
        automation_id: str,
        name: str,
        kind: str,
        prompt: str,
        status: str = "ACTIVE",
    ) -> None:
        path = automations_dir / automation_id / "automation.toml"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            _automation_toml(automation_id, name, kind, prompt, status=status),
            encoding="utf-8",
        )

    def write_matching_automations(self, automations_dir: Path) -> None:
        self.write_automation(
            automations_dir,
            "tom-intraday-probe",
            "TOM Intraday Heartbeat",
            "heartbeat",
            f"Run `{INTRADAY_HEARTBEAT_COMMAND}` then status.",
        )
        self.write_automation(
            automations_dir,
            "tom-morning-check",
            "TOM Morning Check",
            "cron",
            (
                "Run `python -m target_opportunity_monitor ibkr-status`, "
                "`python -m target_opportunity_monitor verify-universe`, and "
                "`python -m target_opportunity_monitor intraday-status`."
            ),
        )
        self.write_automation(
            automations_dir,
            "tom-daily-refresh",
            "TOM Daily Refresh",
            "cron",
            "Run `python -m target_opportunity_monitor refresh-data --daily-only`.",
        )
        self.write_automation(
            automations_dir,
            "tom-daily-retry",
            "TOM Daily Retry",
            "cron",
            (
                "Run `python -m target_opportunity_monitor status`, "
                "`python -m target_opportunity_monitor scheduler-status`, and "
                "conditionally `python -m target_opportunity_monitor refresh-data --daily-only`."
            ),
        )

    def test_config_loads_scheduler_automation_default_path(self) -> None:
        config = load_config(PROJECT_ROOT / "configs" / "default.toml")

        self.assertEqual(
            config.scheduler_automations_dir,
            Path.home() / ".codex" / "automations",
        )

    def test_scheduler_audit_reports_configured_when_metadata_matches(self) -> None:
        database_path = self.fresh_database_path("phase11d2_configured.sqlite")
        automations_dir = TEST_TMP_ROOT / "phase11d2_configured_automations"
        config = self.make_config(database_path, automations_dir)
        initialize_database(database_path)
        self.write_matching_automations(automations_dir)

        audit = audit_scheduler(config)

        self.assertEqual(audit.status, "configured")
        self.assertTrue(all(job.status == "configured" for job in audit.jobs))
        heartbeat = next(job for job in audit.jobs if job.job_key == "intraday_heartbeat")
        self.assertEqual(heartbeat.actual_command, INTRADAY_HEARTBEAT_COMMAND)

    def test_scheduler_audit_reports_stale_command_for_old_ibkr_heartbeat(self) -> None:
        database_path = self.fresh_database_path("phase11d2_stale.sqlite")
        automations_dir = TEST_TMP_ROOT / "phase11d2_stale_automations"
        config = self.make_config(database_path, automations_dir)
        initialize_database(database_path)
        self.write_matching_automations(automations_dir)
        self.write_automation(
            automations_dir,
            "tom-intraday-probe",
            "TOM Intraday Heartbeat",
            "heartbeat",
            (
                "Run `python -m target_opportunity_monitor intraday-cycle "
                "--source ibkr --deliver --channel file`."
            ),
        )

        audit = audit_scheduler(config)

        self.assertEqual(audit.status, "stale_command")
        heartbeat = next(job for job in audit.jobs if job.job_key == "intraday_heartbeat")
        self.assertEqual(heartbeat.status, "stale_command")
        self.assertIn("old_ibkr_only_heartbeat", heartbeat.warnings)

    def test_scheduler_audit_reports_missing_when_no_heartbeat_metadata_exists(self) -> None:
        database_path = self.fresh_database_path("phase11d2_missing.sqlite")
        automations_dir = TEST_TMP_ROOT / "phase11d2_missing_automations"
        config = self.make_config(database_path, automations_dir)
        initialize_database(database_path)
        self.write_matching_automations(automations_dir)
        heartbeat_path = automations_dir / "tom-intraday-probe" / "automation.toml"
        heartbeat_path.unlink()

        audit = audit_scheduler(config)

        self.assertEqual(audit.status, "missing")
        heartbeat = next(job for job in audit.jobs if job.job_key == "intraday_heartbeat")
        self.assertEqual(heartbeat.status, "missing")

    def test_scheduler_repair_plan_prints_auto_source_command(self) -> None:
        database_path = self.fresh_database_path("phase11d2_repair.sqlite")
        automations_dir = TEST_TMP_ROOT / "phase11d2_repair_automations"
        config = self.make_config(database_path, automations_dir)
        initialize_database(database_path)

        text = build_scheduler_repair_plan_text(config)

        self.assertIn(INTRADAY_HEARTBEAT_COMMAND, text)
        self.assertIn("scheduler-audit", text)

    def test_intraday_cycle_drain_first_delivers_existing_pending_before_range(self) -> None:
        database_path = self.fresh_database_path("phase11d2_drain_first.sqlite")
        config = self.make_config(database_path)
        initialize_database(database_path)
        seed_equity(database_path, price=90)
        compute_range_snapshots(config, ticker="AAPL")
        self.assertEqual(pending_notification_count(database_path), 1)

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
            result = run_intraday_cycle(
                config,
                source="auto",
                ticker="AAPL",
                deliver=True,
                channel="file",
                drain_first=True,
            )

        self.assertEqual(result.status, "ok")
        self.assertEqual(
            tuple(step.step_name for step in result.steps[:2]),
            ("drain-pending-notifications-file", "update-quotes"),
        )
        self.assertEqual(pending_notification_count(database_path), 0)
        self.assertEqual(notification_delivery_count(database_path, status="delivered"), 1)
        self.assertEqual(list_notification_events(database_path, status="pending"), [])

    def test_notification_delivery_report_summarizes_outbox_and_failures(self) -> None:
        database_path = self.fresh_database_path("phase11d2_delivery_report.sqlite")
        config = self.make_config(database_path)
        initialize_database(database_path)
        seed_equity(database_path, price=90)
        compute_range_snapshots(config, ticker="AAPL")

        text_before = build_notification_delivery_report_text(config)
        self.assertIn("Pending notification events: 1", text_before)

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
            run_intraday_cycle(
                config,
                source="auto",
                ticker="AAPL",
                deliver=True,
                channel="file",
                drain_first=True,
            )
        text_after = build_notification_delivery_report_text(config)

        self.assertIn("Pending notification events: 0", text_after)
        self.assertIn("Delivered delivery rows: 1", text_after)
        self.assertIn("Latest outbox files:", text_after)


if __name__ == "__main__":
    unittest.main()
