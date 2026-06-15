from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from uuid import uuid4
from unittest.mock import patch


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
TEST_TMP_ROOT = PROJECT_ROOT / ".tmp_tests" / "phase11e_api"
sys.path.insert(0, str(SRC_PATH))

from target_opportunity_monitor.api_server import handle_api_request
from target_opportunity_monitor.config import AppConfig
from target_opportunity_monitor.db import initialize_database


def _config(name: str) -> AppConfig:
    TEST_TMP_ROOT.mkdir(parents=True, exist_ok=True)
    root = TEST_TMP_ROOT / f"{name}_{uuid4().hex}"
    root.mkdir(parents=True, exist_ok=True)
    config = AppConfig(
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
    )
    initialize_database(config.database_path)
    return config


def _fake_action(status: str = "ok") -> SimpleNamespace:
    return SimpleNamespace(
        status=status,
        message="loop action ok",
        iterations=1,
        warnings=(),
        result=None,
        snapshot=SimpleNamespace(
            status="stopped",
            health_status="stopped",
            active=False,
            stale_blockers=(),
            warnings=(),
            clear_stale_lock_command="python -m target_opportunity_monitor tom-loop-stop",
            recovery_status="stopped_start_available",
            recommended_actions=("start_loop", "run_once"),
            recovery_notes=("No active TOM loop is running.",),
        ),
    )


def _fake_snapshot() -> SimpleNamespace:
    return SimpleNamespace(
        status="stopped",
        health_status="stopped",
        active=False,
        lock_exists=False,
        stale_lock=False,
        stop_requested=False,
        pid=None,
        stale_blockers=(),
        warnings=(),
        recommended_command=(
            "python -m target_opportunity_monitor tom-loop-start "
            "--mode auto --deliver --channel file"
        ),
        run_once_command=(
            "python -m target_opportunity_monitor tom-loop-once "
            "--mode auto --deliver --channel file"
        ),
        clear_stale_lock_command="python -m target_opportunity_monitor tom-loop-stop",
        recovery_status="stopped_start_available",
        recommended_actions=("start_loop", "run_once"),
        recovery_notes=("No active TOM loop is running.",),
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


class Phase11ELoopApiTests(unittest.TestCase):
    def test_loop_get_endpoints_return_json(self) -> None:
        config = _config("get")

        for path in ("/api/loop/status", "/api/loop/health"):
            with self.subTest(path=path):
                with patch(
                    "target_opportunity_monitor.api_server.tom_loop_status",
                    return_value=_fake_snapshot(),
                ), patch(
                    "target_opportunity_monitor.api_server.tom_loop_health",
                    return_value=_fake_snapshot(),
                ):
                    code, payload = handle_api_request(config, "GET", path)
                self.assertEqual(code, 200)
                self.assertTrue(payload["ok"])
                self.assertIn("loop", payload["data"])
                loop_payload = payload["data"]["loop"]
                self.assertEqual(loop_payload["recovery_status"], "stopped_start_available")
                self.assertEqual(loop_payload["recommended_actions"], ["start_loop", "run_once"])
                self.assertTrue(loop_payload["clear_stale_lock_command"].endswith("tom-loop-stop"))

    def test_loop_mutations_require_confirmation(self) -> None:
        config = _config("confirm")

        for path in ("/api/loop/run-once", "/api/loop/start", "/api/loop/stop"):
            with self.subTest(path=path):
                code, payload = handle_api_request(config, "POST", path, body={})
                self.assertEqual(code, 403)
                self.assertEqual(payload["error_code"], "confirmation_required")

    def test_loop_run_once_endpoint_calls_backend(self) -> None:
        config = _config("once")

        with patch(
            "target_opportunity_monitor.api_server.tom_loop_once",
            return_value=_fake_action(),
        ) as loop_once:
            code, payload = handle_api_request(
                config,
                "POST",
                "/api/loop/run-once",
                body={"mode": "auto", "deliver": True, "channel": "file", "confirm": True},
            )

        self.assertEqual(code, 200)
        self.assertTrue(payload["ok"])
        loop_once.assert_called_once()

    def test_loop_stop_endpoint_calls_backend(self) -> None:
        config = _config("stop")

        with patch(
            "target_opportunity_monitor.api_server.tom_loop_stop",
            return_value=_fake_action("stopped"),
        ) as stop_loop:
            code, payload = handle_api_request(
                config,
                "POST",
                "/api/loop/stop",
                body={"confirm": True},
            )

        self.assertEqual(code, 200)
        self.assertTrue(payload["ok"])
        stop_loop.assert_called_once()

    def test_loop_status_endpoint_serializes_stale_lock_recovery_plan(self) -> None:
        config = _config("stale_status")
        old = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat(timespec="seconds")
        _write_json(
            config.ops_loop_dir / "tom_loop_state.json",
            {
                "status": "running",
                "pid": 999999,
                "mode": "auto",
                "deliver": True,
                "channel": "file",
                "started_at": old,
                "last_heartbeat_at": old,
            },
        )
        _write_json(config.ops_loop_dir / "tom_loop.lock", {"pid": 999999})
        _write_json(config.ops_loop_dir / "latest_heartbeat.json", {"timestamp": old})

        with patch(
            "target_opportunity_monitor.tom_loop._safe_freshness",
            return_value=_fake_freshness(),
        ):
            code, payload = handle_api_request(config, "GET", "/api/loop/status")

        self.assertEqual(code, 200)
        self.assertTrue(payload["ok"])
        loop_payload = payload["data"]["loop"]
        self.assertEqual(loop_payload["status"], "stale_lock")
        self.assertTrue(loop_payload["stale_lock"])
        self.assertEqual(loop_payload["health_status"], "blocked")
        self.assertEqual(loop_payload["recovery_status"], "stale_lock_clearable")
        self.assertIn("clear_stale_lock", loop_payload["recommended_actions"])
        self.assertIn("stale_loop_lock", loop_payload["warnings"])

    def test_loop_stop_clears_stale_lock_fixture_without_starting_loop(self) -> None:
        config = _config("stop_stale")
        old = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat(timespec="seconds")
        _write_json(
            config.ops_loop_dir / "tom_loop_state.json",
            {
                "status": "running",
                "pid": 999999,
                "mode": "auto",
                "deliver": True,
                "channel": "file",
                "started_at": old,
                "last_heartbeat_at": old,
            },
        )
        _write_json(config.ops_loop_dir / "tom_loop.lock", {"pid": 999999})
        _write_json(config.ops_loop_dir / "latest_heartbeat.json", {"timestamp": old})

        with patch(
            "target_opportunity_monitor.tom_loop._safe_freshness",
            return_value=_fake_freshness(),
        ), patch("target_opportunity_monitor.api_server.tom_loop_start") as start_loop, patch(
            "target_opportunity_monitor.api_server.tom_loop_once"
        ) as run_once:
            code, payload = handle_api_request(
                config,
                "POST",
                "/api/loop/stop",
                body={"confirm": True},
            )

        self.assertEqual(code, 200)
        self.assertTrue(payload["ok"])
        result_payload = payload["data"]["result"]
        self.assertEqual(result_payload["status"], "stopped")
        self.assertFalse(result_payload["snapshot"]["stale_lock"])
        self.assertEqual(
            result_payload["snapshot"]["recovery_status"],
            "stopped_start_available",
        )
        self.assertFalse((config.ops_loop_dir / "tom_loop.lock").exists())
        start_loop.assert_not_called()
        run_once.assert_not_called()


if __name__ == "__main__":
    unittest.main()
