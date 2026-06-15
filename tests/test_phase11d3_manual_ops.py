from __future__ import annotations

from dataclasses import replace
from datetime import datetime
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
from target_opportunity_monitor.db import initialize_database
from target_opportunity_monitor.manual_ops import (
    BROWSER_CONTENT_AUTOMATION_IDS,
    TOM_AUTOMATION_IDS,
    build_manual_ops_status_text,
    manual_ops_status,
    resolve_manual_ops_loop_mode,
    resolve_manual_ops_mode,
    run_manual_ops_cycle,
    run_manual_ops_loop,
)
from target_opportunity_monitor.pipeline import PipelineExecutionResult, PipelineStepSummary
from target_opportunity_monitor.research_preparation import RESEARCH_PREPARATION_AUTO_STEP_NAME
from target_opportunity_monitor.storage import (
    insert_pipeline_step_result,
    latest_pipeline_run,
    start_pipeline_run,
)
from test_phase11a_ranges import make_config


class Phase11D3ManualOpsTest(unittest.TestCase):
    def fresh_database_path(self, name: str) -> Path:
        TEST_TMP_ROOT.mkdir(parents=True, exist_ok=True)
        path = TEST_TMP_ROOT / name
        if path.exists():
            path.unlink()
        return path

    def make_config(self, database_path: Path):
        return replace(
            make_config(database_path),
            scheduler_automations_dir=TEST_TMP_ROOT / "phase11d3_automations",
            notification_outbox_dir=TEST_TMP_ROOT / "phase11d3_notification_outbox",
        )

    def pipeline_run_count(self, database_path: Path) -> int:
        with sqlite_connection_for_test(database_path) as connection:
            row = connection.execute("SELECT COUNT(*) FROM pipeline_runs").fetchone()
        return int(row[0])

    def nested_result(self, run_type: str = "intraday_cycle") -> PipelineExecutionResult:
        return PipelineExecutionResult(
            pipeline_run_id=999,
            run_type=run_type,
            status="ok",
            steps=(
                PipelineStepSummary(
                    step_name="nested-step",
                    status="ok",
                    rows_loaded=1,
                    warnings=(),
                ),
            ),
            summary=f"{run_type}: status=ok",
        )

    def test_dry_run_reports_planned_steps_without_pipeline_mutation(self) -> None:
        database_path = self.fresh_database_path("phase11d3_dry_run.sqlite")
        config = self.make_config(database_path)
        initialize_database(database_path)

        before = self.pipeline_run_count(database_path)
        result = run_manual_ops_cycle(config, mode="intraday", deliver=True, dry_run=True)
        after = self.pipeline_run_count(database_path)

        self.assertEqual(before, after)
        self.assertEqual(result.status, "planned")
        self.assertEqual(result.pipeline_run_id, 0)
        self.assertEqual(result.steps[0].status, "planned")
        self.assertIn("selected_mode=intraday", result.summary)

    def test_dry_run_morning_includes_research_preparation_auto_step(self) -> None:
        database_path = self.fresh_database_path("phase11d3_morning_dry_run.sqlite")
        config = self.make_config(database_path)
        initialize_database(database_path)

        result = run_manual_ops_cycle(
            config,
            mode="morning",
            dry_run=True,
            now=datetime(2026, 6, 10, 8, 30),
        )

        self.assertIn(
            RESEARCH_PREPARATION_AUTO_STEP_NAME,
            tuple(step.step_name for step in result.steps),
        )

    def test_manual_intraday_mode_runs_nested_intraday_cycle(self) -> None:
        database_path = self.fresh_database_path("phase11d3_intraday.sqlite")
        config = self.make_config(database_path)
        initialize_database(database_path)

        with patch(
            "target_opportunity_monitor.manual_ops.run_intraday_cycle",
            return_value=self.nested_result("intraday_cycle"),
        ) as intraday:
            result = run_manual_ops_cycle(config, mode="intraday", deliver=True, channel="file")

        intraday.assert_called_once()
        self.assertEqual(result.run_type, "manual_ops_cycle")
        self.assertEqual(result.status, "ok")
        self.assertEqual(result.steps[0].step_name, "intraday-cycle")
        self.assertIsNotNone(latest_pipeline_run(database_path, run_type="manual_ops_cycle"))

    def test_manual_daily_refresh_mode_runs_daily_refresh(self) -> None:
        database_path = self.fresh_database_path("phase11d3_refresh.sqlite")
        config = self.make_config(database_path)
        initialize_database(database_path)

        with patch(
            "target_opportunity_monitor.manual_ops.run_refresh_data",
            return_value=self.nested_result("daily_refresh"),
        ) as refresh:
            result = run_manual_ops_cycle(config, mode="daily-refresh")

        refresh.assert_called_once()
        self.assertEqual(result.status, "ok")
        self.assertEqual(result.steps[0].step_name, "daily-refresh")

    def test_daily_retry_skips_refresh_when_latest_state_is_fresh(self) -> None:
        database_path = self.fresh_database_path("phase11d3_retry_fresh.sqlite")
        config = self.make_config(database_path)
        initialize_database(database_path)
        latest_refresh = SimpleNamespace(status="ok")

        with (
            patch("target_opportunity_monitor.manual_ops.latest_pipeline_run", return_value=latest_refresh),
            patch("target_opportunity_monitor.manual_ops.latest_price_date", return_value="2026-06-10"),
            patch("target_opportunity_monitor.manual_ops.run_refresh_data") as refresh,
        ):
            result = run_manual_ops_cycle(
                config,
                mode="daily-retry",
                now=datetime(2026, 6, 10, 21, 0),
            )

        refresh.assert_not_called()
        self.assertEqual(result.status, "ok")
        self.assertEqual(result.steps[0].rows_loaded, 0)
        self.assertEqual(result.steps[0].warnings, ())

    def test_daily_retry_runs_refresh_when_price_date_is_stale(self) -> None:
        database_path = self.fresh_database_path("phase11d3_retry_stale.sqlite")
        config = self.make_config(database_path)
        initialize_database(database_path)
        latest_refresh = SimpleNamespace(status="ok")

        with (
            patch("target_opportunity_monitor.manual_ops.latest_pipeline_run", return_value=latest_refresh),
            patch("target_opportunity_monitor.manual_ops.latest_price_date", return_value="2026-06-09"),
            patch(
                "target_opportunity_monitor.manual_ops.run_refresh_data",
                return_value=self.nested_result("daily_refresh"),
            ) as refresh,
        ):
            result = run_manual_ops_cycle(
                config,
                mode="daily-retry",
                now=datetime(2026, 6, 10, 21, 0),
            )

        refresh.assert_called_once()
        self.assertEqual(result.status, "ok")
        self.assertIn("stale_price_date", result.steps[0].warnings[0])

    def test_research_preparation_auto_respects_throttle(self) -> None:
        database_path = self.fresh_database_path("phase11d3_research_auto_throttle.sqlite")
        config = self.make_config(database_path)
        initialize_database(database_path)
        now = datetime.now().isoformat(timespec="seconds")
        pipeline_run_id = start_pipeline_run(
            database_path,
            "manual_ops_cycle",
            source="manual_ops",
        )
        insert_pipeline_step_result(
            database_path,
            pipeline_run_id=pipeline_run_id,
            step_name=RESEARCH_PREPARATION_AUTO_STEP_NAME,
            status="ok",
            rows_loaded=0,
            source="manual_ops",
            started_at=now,
            finished_at=now,
        )
        latest_refresh = SimpleNamespace(status="ok")

        with (
            patch("target_opportunity_monitor.manual_ops.latest_pipeline_run", return_value=latest_refresh),
            patch("target_opportunity_monitor.manual_ops.latest_price_date", return_value="2026-06-10"),
            patch("target_opportunity_monitor.manual_ops.run_research_preparation") as preparation,
        ):
            result = run_manual_ops_cycle(
                config,
                mode="daily-retry",
                now=datetime(2026, 6, 10, 21, 0),
            )

        preparation.assert_not_called()
        auto_step = next(step for step in result.steps if step.step_name == RESEARCH_PREPARATION_AUTO_STEP_NAME)
        self.assertEqual(auto_step.status, "ok")
        self.assertEqual(auto_step.rows_loaded, 0)
        self.assertEqual(auto_step.warnings, ())

    def test_research_preparation_auto_records_manual_blockers_as_warning(self) -> None:
        database_path = self.fresh_database_path("phase11d3_research_auto_warning.sqlite")
        config = replace(
            self.make_config(database_path),
            research_preparation_auto_min_seconds_between_runs=0,
        )
        initialize_database(database_path)
        latest_refresh = SimpleNamespace(status="ok")
        manual_packet = SimpleNamespace(
            ticker="SIVE",
            cannot_automate_reason="source_backed_identity_required",
        )
        preparation_result = SimpleNamespace(
            ignored_count=0,
            applied_count=0,
            refreshed_count=0,
            discovered_count=0,
            staged_count=0,
            loaded_source_count=0,
            computed_count=0,
            warnings=(),
            applied_tickers=(),
            updated_recommendation_ids=(),
            status=SimpleNamespace(manual_blocker_packets=(manual_packet,)),
        )

        with (
            patch("target_opportunity_monitor.manual_ops.latest_pipeline_run", return_value=latest_refresh),
            patch("target_opportunity_monitor.manual_ops.latest_price_date", return_value="2026-06-10"),
            patch(
                "target_opportunity_monitor.manual_ops.run_research_preparation",
                return_value=preparation_result,
            ) as preparation,
        ):
            result = run_manual_ops_cycle(
                config,
                mode="daily-retry",
                now=datetime(2026, 6, 10, 21, 0),
            )

        preparation.assert_called_once()
        _args, kwargs = preparation.call_args
        self.assertEqual(kwargs["source"], "all")
        self.assertEqual(kwargs["action"], "all_safe")
        self.assertTrue(kwargs["confirm"])
        auto_step = next(step for step in result.steps if step.step_name == RESEARCH_PREPARATION_AUTO_STEP_NAME)
        self.assertEqual(auto_step.status, "warning")
        self.assertIn("manual_blockers:SIVE", auto_step.warnings)
        self.assertIn("cannot_automate:SIVE:source_backed_identity_required", auto_step.warnings)

    def test_auto_mode_selects_time_appropriate_operation(self) -> None:
        self.assertEqual(resolve_manual_ops_mode("auto", datetime(2026, 6, 10, 8, 30)), "morning")
        self.assertEqual(resolve_manual_ops_mode("auto", datetime(2026, 6, 10, 10, 0)), "intraday")
        self.assertEqual(resolve_manual_ops_mode("auto", datetime(2026, 6, 10, 18, 30)), "daily-refresh")
        self.assertEqual(resolve_manual_ops_mode("auto", datetime(2026, 6, 10, 21, 0)), "daily-retry")

    def test_loop_auto_after_close_uses_guarded_retry_path(self) -> None:
        self.assertEqual(
            resolve_manual_ops_loop_mode("auto", datetime(2026, 6, 10, 18, 30)),
            "daily-retry",
        )

    def test_manual_ops_loop_runs_until_max_iterations(self) -> None:
        database_path = self.fresh_database_path("phase11d3_loop.sqlite")
        config = self.make_config(database_path)
        initialize_database(database_path)
        sleeps: list[float] = []
        messages: list[str] = []

        with patch(
            "target_opportunity_monitor.manual_ops.run_manual_ops_cycle",
            return_value=self.nested_result("manual_ops_cycle"),
        ) as cycle:
            result = run_manual_ops_loop(
                config,
                mode="intraday",
                deliver=True,
                channel="file",
                interval_seconds=2,
                max_iterations=2,
                sleep_func=sleeps.append,
                output_callback=messages.append,
            )

        self.assertEqual(result.status, "ok")
        self.assertEqual(result.iterations, 2)
        self.assertEqual(result.stopped_reason, "max_iterations_reached")
        self.assertEqual(cycle.call_count, 2)
        self.assertEqual(sleeps, [2])
        self.assertTrue(any("Iteration 1" in message for message in messages))

    def test_manual_ops_loop_validates_positive_interval_and_iterations(self) -> None:
        database_path = self.fresh_database_path("phase11d3_loop_validation.sqlite")
        config = self.make_config(database_path)
        initialize_database(database_path)

        with self.assertRaises(ValueError):
            run_manual_ops_loop(config, interval_seconds=0, max_iterations=1)
        with self.assertRaises(ValueError):
            run_manual_ops_loop(config, interval_seconds=1, max_iterations=0)

    def test_manual_ops_status_recommends_only_tom_automation_pause(self) -> None:
        database_path = self.fresh_database_path("phase11d3_status.sqlite")
        config = self.make_config(database_path)
        initialize_database(database_path)

        status = manual_ops_status(config)
        text = build_manual_ops_status_text(config)

        self.assertEqual(status.pause_recommendations, TOM_AUTOMATION_IDS)
        for automation_id in BROWSER_CONTENT_AUTOMATION_IDS:
            self.assertIn(automation_id, status.excluded_automation_ids)
            self.assertNotIn(automation_id, status.pause_recommendations)
            self.assertIn(automation_id, text)
        self.assertIn("tom-intraday-probe", text)
        self.assertIn("manual-ops-loop --mode auto", text)
        self.assertIn("manual-ops-cycle --mode auto", text)


if __name__ == "__main__":
    unittest.main()
