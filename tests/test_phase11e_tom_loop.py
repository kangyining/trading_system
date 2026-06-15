from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import sys
import unittest
from uuid import uuid4
from unittest.mock import patch


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
TEST_TMP_ROOT = PROJECT_ROOT / ".tmp_tests" / "phase11e"
sys.path.insert(0, str(SRC_PATH))

from target_opportunity_monitor.config import AppConfig
from target_opportunity_monitor.db import initialize_database
from target_opportunity_monitor.pipeline import PipelineExecutionResult, PipelineStepSummary
from target_opportunity_monitor.tom_loop import (
    tom_loop_once,
    tom_loop_start,
    tom_loop_status,
    tom_loop_stop,
)


def _config(name: str) -> AppConfig:
    TEST_TMP_ROOT.mkdir(parents=True, exist_ok=True)
    root = TEST_TMP_ROOT / f"{name}_{uuid4().hex}"
    root.mkdir(parents=True, exist_ok=True)
    return AppConfig(
        project_root=root,
        config_path=root / "config.toml",
        database_path=root / "tom.sqlite",
        reports_dir=root / "reports",
        watchlist_path=root / "configs" / "watchlist.csv",
        cik_map_path=root / "configs" / "cik_map.csv",
        scheduler_automations_dir=root / ".codex" / "automations",
        notification_outbox_dir=root / "data" / "notifications" / "outbox",
        ops_loop_dir=root / "data" / "ops" / "loop",
        market_data_dir=root / "data" / "market_data",
        manual_prices_dir=root / "data" / "market_data" / "manual",
        market_data_primary_source="manual",
        market_data_secondary_source="manual",
        market_data_mode="manual",
        market_data_lookback_days=30,
        market_data_stale_after_days=7,
        market_data_minimum_history_days=5,
        universe_mode="manual_watchlist",
        run_mode="test",
        report_title="Test",
        realtime_manual_ops_loop_interval_seconds=1,
        realtime_intraday_cycle_stale_after_seconds=2,
    )


def _fake_result(status: str = "ok") -> PipelineExecutionResult:
    return PipelineExecutionResult(
        pipeline_run_id=1,
        run_type="manual_ops_cycle",
        status=status,
        steps=(PipelineStepSummary("intraday-cycle", status, 1, ()),),
        summary=f"manual_ops_cycle: status={status}",
    )


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _fake_freshness() -> dict[str, object]:
    return {
        "quote_timestamp": None,
        "quote_age_seconds": None,
        "range_snapshot_timestamp": None,
        "pending_notifications": 0,
        "failed_deliveries": 0,
        "latest_successful_delivery": None,
        "stale_blockers": (),
        "warnings": (),
        "notes": (),
        "market_session": "weekend",
        "regular_market_hours": False,
    }


class Phase11ETomLoopTests(unittest.TestCase):
    def setUp(self) -> None:
        self.freshness_patcher = patch(
            "target_opportunity_monitor.tom_loop._safe_freshness",
            return_value=_fake_freshness(),
        )
        self.freshness_mock = self.freshness_patcher.start()
        self.addCleanup(self.freshness_patcher.stop)

    def test_status_handles_missing_state(self) -> None:
        config = _config("missing_state")

        status = tom_loop_status(config)

        self.assertEqual(status.status, "stopped")
        self.assertFalse(status.active)
        self.assertFalse(status.lock_exists)
        self.assertEqual(status.recovery_status, "stopped_start_available")
        self.assertIn("start_loop", status.recommended_actions)
        self.assertIn("run_once", status.recommended_actions)

    def test_tom_loop_once_runs_manual_ops_and_writes_state(self) -> None:
        config = _config("once")
        initialize_database(config.database_path)

        with patch(
            "target_opportunity_monitor.tom_loop.run_manual_ops_cycle",
            return_value=_fake_result(),
        ) as run_mock:
            result = tom_loop_once(config, mode="intraday", deliver=True, channel="file")

        self.assertEqual(result.status, "ok")
        self.assertEqual(result.iterations, 1)
        run_mock.assert_called_once()
        status = tom_loop_status(config)
        self.assertEqual(status.status, "stopped")
        self.assertFalse(status.active)
        self.assertEqual(status.last_result_status, "ok")
        self.assertTrue((config.ops_loop_dir / "latest_heartbeat.json").exists())

    def test_start_rejects_duplicate_active_loop(self) -> None:
        config = _config("duplicate")
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        _write_json(
            config.ops_loop_dir / "tom_loop_state.json",
            {
                "status": "running",
                "pid": 999999,
                "mode": "auto",
                "deliver": True,
                "channel": "file",
                "started_at": now,
                "last_heartbeat_at": now,
            },
        )
        _write_json(config.ops_loop_dir / "tom_loop.lock", {"pid": 999999})
        _write_json(config.ops_loop_dir / "latest_heartbeat.json", {"timestamp": now})

        status = tom_loop_status(config)
        self.assertTrue(status.active)
        self.assertEqual(status.recovery_status, "active_loop_running")
        self.assertEqual(status.recommended_actions, ("monitor_loop",))

        with self.assertRaises(RuntimeError):
            tom_loop_start(
                config,
                mode="auto",
                deliver=True,
                channel="file",
                interval_seconds=1,
                max_cycles=1,
                sleep_func=lambda _: None,
            )

    def test_stop_requests_active_loop(self) -> None:
        config = _config("stop_active")
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        _write_json(
            config.ops_loop_dir / "tom_loop_state.json",
            {
                "status": "running",
                "pid": 999999,
                "mode": "auto",
                "deliver": True,
                "channel": "file",
                "started_at": now,
                "last_heartbeat_at": now,
            },
        )
        _write_json(config.ops_loop_dir / "tom_loop.lock", {"pid": 999999})
        _write_json(config.ops_loop_dir / "latest_heartbeat.json", {"timestamp": now})

        stopped = tom_loop_stop(config)

        self.assertEqual(stopped.status, "stop_requested")
        self.assertTrue((config.ops_loop_dir / "tom_loop_stop.json").exists())
        self.assertEqual(tom_loop_status(config).status, "stop_requested")

    def test_stale_lock_is_cleared_by_stop(self) -> None:
        config = _config("stale_lock")
        old = (datetime.now(timezone.utc) - timedelta(seconds=60)).isoformat(timespec="seconds")
        _write_json(
            config.ops_loop_dir / "tom_loop_state.json",
            {
                "status": "running",
                "pid": 999999,
                "mode": "auto",
                "started_at": old,
                "last_heartbeat_at": old,
            },
        )
        _write_json(config.ops_loop_dir / "tom_loop.lock", {"pid": 999999})
        _write_json(config.ops_loop_dir / "latest_heartbeat.json", {"timestamp": old})

        status = tom_loop_status(config)
        self.assertTrue(status.stale_lock)
        self.assertEqual(status.health_status, "blocked")
        self.assertEqual(status.recovery_status, "stale_lock_clearable")
        self.assertIn("clear_stale_lock", status.recommended_actions)
        self.assertIn("start_loop", status.recommended_actions)
        self.assertIn("run_once", status.recommended_actions)
        self.assertIn("stale_loop_lock", status.warnings)
        self.assertTrue(status.clear_stale_lock_command.endswith("tom-loop-stop"))

        stopped = tom_loop_stop(config)
        self.assertEqual(stopped.status, "stopped")
        self.assertFalse((config.ops_loop_dir / "tom_loop.lock").exists())
        post_stop_status = tom_loop_status(config)
        self.assertFalse(post_stop_status.stale_lock)
        self.assertEqual(post_stop_status.recovery_status, "stopped_start_available")

    def test_stale_input_blockers_recommend_run_once_without_lock_recovery(self) -> None:
        config = _config("stale_inputs")
        freshness = dict(_fake_freshness())
        freshness["stale_blockers"] = ("failed_delivery",)
        freshness["warnings"] = ("failed_delivery",)
        self.freshness_mock.return_value = freshness

        status = tom_loop_status(config)

        self.assertEqual(status.status, "stopped")
        self.assertFalse(status.stale_lock)
        self.assertEqual(status.health_status, "stale")
        self.assertEqual(status.recovery_status, "blocked_by_stale_inputs")
        self.assertNotIn("clear_stale_lock", status.recommended_actions)
        self.assertIn("run_once", status.recommended_actions)

    def test_bounded_start_runs_one_cycle(self) -> None:
        config = _config("bounded_start")
        initialize_database(config.database_path)

        with patch(
            "target_opportunity_monitor.tom_loop.run_manual_ops_cycle",
            return_value=_fake_result(),
        ):
            result = tom_loop_start(
                config,
                mode="intraday",
                deliver=True,
                channel="file",
                interval_seconds=1,
                max_cycles=1,
                sleep_func=lambda _: None,
            )

        self.assertEqual(result.status, "ok")
        self.assertEqual(result.iterations, 1)
        self.assertEqual(tom_loop_status(config).status, "stopped")


if __name__ == "__main__":
    unittest.main()
