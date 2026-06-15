from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import ctypes
import json
import os
from pathlib import Path
import time as time_module
from typing import Callable, Mapping

from .config import AppConfig
from .db import get_database_status, initialize_database
from .intraday_health import intraday_health
from .manual_ops import (
    MANUAL_OPS_MODES,
    resolve_manual_ops_loop_mode,
    run_manual_ops_cycle,
)
from .pipeline import PipelineExecutionResult
from .storage import (
    latest_notification_delivery_timestamp,
    latest_quote_timestamp,
    latest_range_snapshot_timestamp,
    notification_delivery_count,
    pending_notification_count,
)


TOM_LOOP_DEFAULT_COMMAND = (
    "python -m target_opportunity_monitor tom-loop-start "
    "--mode auto --deliver --channel file"
)
TOM_LOOP_ONCE_COMMAND = (
    "python -m target_opportunity_monitor tom-loop-once "
    "--mode auto --deliver --channel file"
)
TOM_LOOP_CLEAR_STALE_LOCK_COMMAND = "python -m target_opportunity_monitor tom-loop-stop"
TOM_LOOP_STATE_FILE = "tom_loop_state.json"
TOM_LOOP_LOCK_FILE = "tom_loop.lock"
TOM_LOOP_HEARTBEAT_FILE = "latest_heartbeat.json"
TOM_LOOP_STOP_REQUEST_FILE = "tom_loop_stop.json"


@dataclass(frozen=True)
class TomLoopSnapshot:
    status: str
    health_status: str
    active: bool
    lock_exists: bool
    stale_lock: bool
    stop_requested: bool
    pid: int | None
    mode: str | None
    deliver: bool | None
    channel: str | None
    started_at: str | None
    stopped_at: str | None
    last_heartbeat_at: str | None
    heartbeat_age_seconds: float | None
    last_cycle_started_at: str | None
    last_cycle_finished_at: str | None
    last_cycle_mode: str | None
    last_result_status: str | None
    last_result_summary: str | None
    quote_timestamp: str | None
    quote_age_seconds: float | None
    range_snapshot_timestamp: str | None
    pending_notifications: int | None
    failed_deliveries: int | None
    latest_successful_delivery: str | None
    stale_blockers: tuple[str, ...]
    warnings: tuple[str, ...]
    notes: tuple[str, ...]
    market_session: str | None
    regular_market_hours: bool | None
    loop_dir: str
    state_path: str
    lock_path: str
    heartbeat_path: str
    recommended_command: str = TOM_LOOP_DEFAULT_COMMAND
    run_once_command: str = TOM_LOOP_ONCE_COMMAND
    clear_stale_lock_command: str = TOM_LOOP_CLEAR_STALE_LOCK_COMMAND
    recovery_status: str = "none"
    recommended_actions: tuple[str, ...] = ()
    recovery_notes: tuple[str, ...] = ()


@dataclass(frozen=True)
class TomLoopActionResult:
    status: str
    message: str
    snapshot: TomLoopSnapshot
    iterations: int = 0
    result: PipelineExecutionResult | None = None
    warnings: tuple[str, ...] = ()


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _now_iso() -> str:
    return _now().isoformat(timespec="seconds")


def _loop_dir(config: AppConfig) -> Path:
    return config.ops_loop_dir


def _paths(config: AppConfig) -> dict[str, Path]:
    loop_dir = _loop_dir(config)
    return {
        "dir": loop_dir,
        "state": loop_dir / TOM_LOOP_STATE_FILE,
        "lock": loop_dir / TOM_LOOP_LOCK_FILE,
        "heartbeat": loop_dir / TOM_LOOP_HEARTBEAT_FILE,
        "stop": loop_dir / TOM_LOOP_STOP_REQUEST_FILE,
    }


def _read_json(path: Path) -> dict[str, object]:
    if not path.exists():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _write_json(path: Path, payload: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(path.suffix + ".tmp")
    temp_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True),
        encoding="utf-8",
    )
    temp_path.replace(path)


def _remove_if_exists(path: Path) -> None:
    try:
        path.unlink()
    except FileNotFoundError:
        return


def _parse_datetime(value: object) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _age_seconds(value: object, now: datetime | None = None) -> float | None:
    parsed = _parse_datetime(value)
    if parsed is None:
        return None
    current = now or _now()
    return max(0.0, (current - parsed).total_seconds())


def _pid_running(pid: int | None) -> bool:
    if pid is None or pid <= 0:
        return False
    if os.name == "nt":
        kernel32 = ctypes.windll.kernel32
        process_query_limited_information = 0x1000
        handle = kernel32.OpenProcess(
            process_query_limited_information,
            False,
            int(pid),
        )
        if not handle:
            return False
        try:
            exit_code = ctypes.c_ulong()
            if not kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code)):
                return False
            return exit_code.value == 259
        finally:
            kernel32.CloseHandle(handle)
    try:
        os.kill(pid, 0)
    except PermissionError:
        return True
    except OSError:
        return False
    return True


def _heartbeat_stale_threshold(config: AppConfig) -> int:
    return max(
        config.realtime_intraday_cycle_stale_after_seconds,
        config.realtime_manual_ops_loop_interval_seconds * 2,
    )


def _safe_freshness(config: AppConfig) -> dict[str, object]:
    try:
        database_status = get_database_status(config.database_path)
    except Exception as error:
        return {
            "quote_timestamp": None,
            "quote_age_seconds": None,
            "range_snapshot_timestamp": None,
            "pending_notifications": None,
            "failed_deliveries": None,
            "latest_successful_delivery": None,
            "stale_blockers": (),
            "warnings": (f"database_status_failed:{error}",),
            "notes": (),
            "market_session": None,
            "regular_market_hours": None,
        }

    tables = database_status.existing_tables
    warnings: list[str] = []
    quote_timestamp = None
    range_snapshot_timestamp = None
    pending_notifications = None
    failed_deliveries = None
    latest_successful_delivery = None
    if "quote_snapshots" in tables:
        quote_timestamp = latest_quote_timestamp(config.database_path)
    if "range_snapshots" in tables:
        range_snapshot_timestamp = latest_range_snapshot_timestamp(config.database_path)
    if "notification_events" in tables:
        pending_notifications = pending_notification_count(config.database_path)
    if "notification_deliveries" in tables:
        failed_deliveries = notification_delivery_count(
            config.database_path,
            status="failed",
        )
        latest_successful_delivery = latest_notification_delivery_timestamp(
            config.database_path,
            status="delivered",
        )

    blockers: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()
    market_session = None
    regular_market_hours = None
    try:
        health = intraday_health(config)
        blockers = tuple(health.blockers)
        warnings.extend(health.warnings)
        notes = health.notes
        market_session = health.market_session
        regular_market_hours = health.regular_market_hours
    except Exception as error:
        warnings.append(f"intraday_health_failed:{error}")

    return {
        "quote_timestamp": quote_timestamp,
        "quote_age_seconds": _age_seconds(quote_timestamp),
        "range_snapshot_timestamp": range_snapshot_timestamp,
        "pending_notifications": pending_notifications,
        "failed_deliveries": failed_deliveries,
        "latest_successful_delivery": latest_successful_delivery,
        "stale_blockers": blockers,
        "warnings": tuple(warnings),
        "notes": notes,
        "market_session": market_session,
        "regular_market_hours": regular_market_hours,
    }


def _recovery_fields(
    *,
    active: bool,
    stale_lock: bool,
    state_status: str,
    stale_blockers: tuple[str, ...],
    heartbeat_age_seconds: float | None,
) -> dict[str, object]:
    if stale_lock:
        age_note = (
            f"Last heartbeat age seconds: {heartbeat_age_seconds:.1f}."
            if heartbeat_age_seconds is not None
            else "Last heartbeat age seconds: unknown."
        )
        return {
            "recovery_status": "stale_lock_clearable",
            "recommended_actions": ("clear_stale_lock", "start_loop", "run_once"),
            "recovery_notes": (
                "A stale loop lock is present and no active healthy loop heartbeat is current.",
                age_note,
                "Use tom-loop-stop to clear the stale lock, or start the loop to replace it.",
            ),
        }
    if active:
        return {
            "recovery_status": "active_loop_running",
            "recommended_actions": ("monitor_loop",),
            "recovery_notes": ("The persistent TOM loop is active; no recovery action is needed.",),
        }
    if stale_blockers:
        return {
            "recovery_status": "blocked_by_stale_inputs",
            "recommended_actions": ("run_once", "start_loop"),
            "recovery_notes": (
                "Loop freshness has blockers from intraday health or delivery state.",
                "Run one safe loop cycle or restart the persistent loop after reviewing blockers.",
            ),
        }
    if state_status == "stopped":
        return {
            "recovery_status": "stopped_start_available",
            "recommended_actions": ("start_loop", "run_once"),
            "recovery_notes": (
                "No active TOM loop is running; start the persistent loop or run one safe cycle.",
            ),
        }
    return {
        "recovery_status": "none",
        "recommended_actions": (),
        "recovery_notes": (),
    }


def _state_with_metadata(
    config: AppConfig,
    state: Mapping[str, object],
    updates: Mapping[str, object],
) -> dict[str, object]:
    merged = dict(state)
    merged.update(updates)
    merged["updated_at"] = _now_iso()
    merged["loop_dir"] = str(_loop_dir(config))
    return merged


def _write_heartbeat(
    config: AppConfig,
    state: Mapping[str, object],
    event: str,
    extra: Mapping[str, object] | None = None,
) -> None:
    paths = _paths(config)
    timestamp = _now_iso()
    payload: dict[str, object] = {
        "event": event,
        "pid": os.getpid(),
        "timestamp": timestamp,
        "mode": state.get("mode"),
        "status": state.get("status"),
    }
    if extra:
        payload.update(extra)
    _write_json(paths["heartbeat"], payload)
    updated = _state_with_metadata(
        config,
        state,
        {
            "pid": os.getpid(),
            "last_heartbeat_at": timestamp,
            "last_heartbeat_event": event,
        },
    )
    _write_json(paths["state"], updated)


def _status_from_files(config: AppConfig, now: datetime | None = None) -> TomLoopSnapshot:
    paths = _paths(config)
    state = _read_json(paths["state"])
    lock = _read_json(paths["lock"])
    heartbeat = _read_json(paths["heartbeat"])
    stop = _read_json(paths["stop"])

    pid_value = state.get("pid") or lock.get("pid")
    try:
        pid = int(pid_value) if pid_value is not None else None
    except (TypeError, ValueError):
        pid = None

    last_heartbeat_at = (
        state.get("last_heartbeat_at")
        or heartbeat.get("timestamp")
        or lock.get("last_heartbeat_at")
    )
    heartbeat_age = _age_seconds(last_heartbeat_at, now=now)
    lock_exists = paths["lock"].exists()
    stop_requested = bool(state.get("stop_requested") or stop)
    state_status = str(state.get("status") or ("unknown" if lock_exists else "stopped"))
    threshold = _heartbeat_stale_threshold(config)
    heartbeat_is_stale = heartbeat_age is None or heartbeat_age > threshold
    pid_is_running = _pid_running(pid)
    active = (
        lock_exists
        and state_status in {"running", "cycle_running", "sleeping", "stop_requested"}
        and not stop_requested
        and (pid_is_running or not heartbeat_is_stale)
        and not heartbeat_is_stale
    )
    stale_lock = lock_exists and not active and state_status != "stopped" and not stop_requested
    if stale_lock:
        state_status = "stale_lock"
    elif active:
        state_status = "running"

    freshness = _safe_freshness(config)
    warnings = list(freshness["warnings"])
    if stale_lock:
        warnings.append("stale_loop_lock")
    if stop_requested:
        warnings.append("stop_requested")

    stale_blockers = tuple(str(item) for item in freshness["stale_blockers"])
    if stale_lock:
        health_status = "blocked"
    elif active and not stale_blockers:
        health_status = "healthy"
    elif not active and state_status == "stopped" and not stale_blockers:
        health_status = "stopped"
    else:
        health_status = "stale"
    recovery = _recovery_fields(
        active=active,
        stale_lock=stale_lock,
        state_status=state_status,
        stale_blockers=stale_blockers,
        heartbeat_age_seconds=heartbeat_age,
    )

    return TomLoopSnapshot(
        status=state_status,
        health_status=health_status,
        active=active,
        lock_exists=lock_exists,
        stale_lock=stale_lock,
        stop_requested=stop_requested,
        pid=pid,
        mode=str(state.get("mode")) if state.get("mode") else None,
        deliver=bool(state.get("deliver")) if "deliver" in state else None,
        channel=str(state.get("channel")) if state.get("channel") else None,
        started_at=str(state.get("started_at")) if state.get("started_at") else None,
        stopped_at=str(state.get("stopped_at")) if state.get("stopped_at") else None,
        last_heartbeat_at=str(last_heartbeat_at) if last_heartbeat_at else None,
        heartbeat_age_seconds=heartbeat_age,
        last_cycle_started_at=(
            str(state.get("last_cycle_started_at"))
            if state.get("last_cycle_started_at")
            else None
        ),
        last_cycle_finished_at=(
            str(state.get("last_cycle_finished_at"))
            if state.get("last_cycle_finished_at")
            else None
        ),
        last_cycle_mode=(
            str(state.get("last_cycle_mode")) if state.get("last_cycle_mode") else None
        ),
        last_result_status=(
            str(state.get("last_result_status"))
            if state.get("last_result_status")
            else None
        ),
        last_result_summary=(
            str(state.get("last_result_summary"))
            if state.get("last_result_summary")
            else None
        ),
        quote_timestamp=freshness["quote_timestamp"],
        quote_age_seconds=freshness["quote_age_seconds"],
        range_snapshot_timestamp=freshness["range_snapshot_timestamp"],
        pending_notifications=freshness["pending_notifications"],
        failed_deliveries=freshness["failed_deliveries"],
        latest_successful_delivery=freshness["latest_successful_delivery"],
        stale_blockers=stale_blockers,
        warnings=tuple(warnings),
        notes=tuple(str(item) for item in freshness.get("notes", ())),
        market_session=(
            str(freshness.get("market_session"))
            if freshness.get("market_session") is not None
            else None
        ),
        regular_market_hours=(
            bool(freshness.get("regular_market_hours"))
            if freshness.get("regular_market_hours") is not None
            else None
        ),
        loop_dir=str(paths["dir"]),
        state_path=str(paths["state"]),
        lock_path=str(paths["lock"]),
        heartbeat_path=str(paths["heartbeat"]),
        clear_stale_lock_command=TOM_LOOP_CLEAR_STALE_LOCK_COMMAND,
        recovery_status=str(recovery["recovery_status"]),
        recommended_actions=tuple(str(item) for item in recovery["recommended_actions"]),
        recovery_notes=tuple(str(item) for item in recovery["recovery_notes"]),
    )


def tom_loop_status(config: AppConfig) -> TomLoopSnapshot:
    return _status_from_files(config)


def tom_loop_health(config: AppConfig) -> TomLoopSnapshot:
    return _status_from_files(config)


def _initial_state(
    mode: str,
    deliver: bool,
    channel: str,
    interval_seconds: int | None = None,
) -> dict[str, object]:
    timestamp = _now_iso()
    return {
        "status": "running",
        "pid": os.getpid(),
        "mode": mode,
        "deliver": deliver,
        "channel": channel,
        "interval_seconds": interval_seconds,
        "started_at": timestamp,
        "last_heartbeat_at": timestamp,
        "stop_requested": False,
    }


def _prepare_loop_start(
    config: AppConfig,
    mode: str,
    deliver: bool,
    channel: str,
    interval_seconds: int | None,
) -> tuple[dict[str, object], tuple[str, ...]]:
    if mode not in MANUAL_OPS_MODES:
        raise ValueError(f"Unsupported loop mode: {mode}")
    if channel not in {"console", "file", "webhook"}:
        raise ValueError(f"Unsupported delivery channel: {channel}")
    paths = _paths(config)
    paths["dir"].mkdir(parents=True, exist_ok=True)
    snapshot = tom_loop_status(config)
    warnings: list[str] = []
    if snapshot.active:
        raise RuntimeError(
            f"TOM loop already running with pid {snapshot.pid or 'unknown'}."
        )
    if snapshot.stale_lock:
        warnings.append("stale_lock_replaced")
        _remove_if_exists(paths["lock"])
    _remove_if_exists(paths["stop"])

    state = _initial_state(
        mode=mode,
        deliver=deliver,
        channel=channel,
        interval_seconds=interval_seconds,
    )
    _write_json(paths["state"], state)
    _write_json(
        paths["lock"],
        {
            "pid": os.getpid(),
            "started_at": state["started_at"],
            "mode": mode,
            "deliver": deliver,
            "channel": channel,
        },
    )
    _write_heartbeat(config, state, "loop_started")
    return state, tuple(warnings)


def _stop_requested(config: AppConfig) -> bool:
    paths = _paths(config)
    state = _read_json(paths["state"])
    return bool(state.get("stop_requested") or paths["stop"].exists())


def _finish_loop(
    config: AppConfig,
    state: Mapping[str, object],
    status: str,
    reason: str,
    remove_lock: bool = True,
) -> TomLoopSnapshot:
    paths = _paths(config)
    finished = _state_with_metadata(
        config,
        state,
        {
            "status": status,
            "stopped_at": _now_iso(),
            "stopped_reason": reason,
            "stop_requested": False,
        },
    )
    _write_json(paths["state"], finished)
    _write_heartbeat(config, finished, "loop_stopped", {"reason": reason})
    if remove_lock:
        _remove_if_exists(paths["lock"])
    _remove_if_exists(paths["stop"])
    return tom_loop_status(config)


def _run_loop_cycle(
    config: AppConfig,
    state: Mapping[str, object],
    mode: str,
    deliver: bool,
    channel: str,
) -> tuple[PipelineExecutionResult, dict[str, object]]:
    selected_mode = resolve_manual_ops_loop_mode(mode)
    started_at = _now_iso()
    cycle_state = _state_with_metadata(
        config,
        state,
        {
            "status": "cycle_running",
            "last_cycle_started_at": started_at,
            "last_cycle_mode": selected_mode,
        },
    )
    _write_json(_paths(config)["state"], cycle_state)
    _write_heartbeat(
        config,
        cycle_state,
        "cycle_started",
        {"selected_mode": selected_mode},
    )
    result = run_manual_ops_cycle(
        config,
        mode=selected_mode,
        deliver=deliver,
        channel=channel,
    )
    finished_state = _state_with_metadata(
        config,
        cycle_state,
        {
            "status": "running",
            "last_cycle_finished_at": _now_iso(),
            "last_result_status": result.status,
            "last_result_summary": result.summary,
        },
    )
    _write_json(_paths(config)["state"], finished_state)
    _write_heartbeat(
        config,
        finished_state,
        "cycle_finished",
        {"result_status": result.status, "result_summary": result.summary},
    )
    return result, finished_state


def tom_loop_once(
    config: AppConfig,
    mode: str = "auto",
    deliver: bool = False,
    channel: str = "file",
) -> TomLoopActionResult:
    initialize_database(config.database_path)
    state, warnings = _prepare_loop_start(
        config,
        mode=mode,
        deliver=deliver,
        channel=channel,
        interval_seconds=None,
    )
    try:
        result, updated_state = _run_loop_cycle(
            config,
            state,
            mode=mode,
            deliver=deliver,
            channel=channel,
        )
    except Exception as error:
        snapshot = _finish_loop(config, state, "error", f"cycle_error:{error}")
        return TomLoopActionResult(
            status="error",
            message=str(error),
            snapshot=snapshot,
            iterations=0,
            warnings=warnings + (str(error),),
        )
    snapshot = _finish_loop(
        config,
        updated_state,
        "stopped",
        "single_cycle_complete",
    )
    return TomLoopActionResult(
        status=result.status,
        message=result.summary,
        snapshot=snapshot,
        iterations=1,
        result=result,
        warnings=warnings,
    )


def tom_loop_start(
    config: AppConfig,
    mode: str = "auto",
    deliver: bool = False,
    channel: str = "file",
    interval_seconds: int | None = None,
    max_cycles: int | None = None,
    sleep_func: Callable[[float], None] = time_module.sleep,
    output_callback: Callable[[str], None] | None = None,
) -> TomLoopActionResult:
    if max_cycles is not None and max_cycles <= 0:
        raise ValueError("max_cycles must be positive when supplied")
    interval = (
        config.realtime_manual_ops_loop_interval_seconds
        if interval_seconds is None
        else interval_seconds
    )
    if interval <= 0:
        raise ValueError("interval_seconds must be positive")

    initialize_database(config.database_path)
    state, warnings = _prepare_loop_start(
        config,
        mode=mode,
        deliver=deliver,
        channel=channel,
        interval_seconds=interval,
    )
    if output_callback:
        output_callback(
            f"TOM loop started: mode={mode}, interval={interval}s, "
            f"deliver={deliver}, channel={channel if deliver else 'none'}"
        )
    iterations = 0
    latest_result: PipelineExecutionResult | None = None
    latest_state = state
    status = "ok"
    stop_reason = "interrupted"
    try:
        while True:
            if _stop_requested(config):
                status = "stopped"
                stop_reason = "stop_requested"
                break
            try:
                latest_result, latest_state = _run_loop_cycle(
                    config,
                    latest_state,
                    mode=mode,
                    deliver=deliver,
                    channel=channel,
                )
            except Exception as error:
                status = "error"
                stop_reason = f"cycle_error:{error}"
                if output_callback:
                    output_callback(f"TOM loop cycle failed: {error}")
                break
            iterations += 1
            if output_callback:
                output_callback(f"Cycle {iterations}: {latest_result.summary}")
            if latest_result.status == "error":
                status = "error"
                stop_reason = "cycle_error"
                break
            if max_cycles is not None and iterations >= max_cycles:
                stop_reason = "max_cycles_reached"
                break

            sleep_state = _state_with_metadata(
                config,
                latest_state,
                {"status": "sleeping", "next_cycle_after_seconds": interval},
            )
            _write_json(_paths(config)["state"], sleep_state)
            _write_heartbeat(config, sleep_state, "sleeping")
            slept = 0.0
            while slept < interval:
                if _stop_requested(config):
                    status = "stopped"
                    stop_reason = "stop_requested"
                    break
                sleep_for = min(1.0, interval - slept)
                sleep_func(sleep_for)
                slept += sleep_for
            latest_state = sleep_state
            if stop_reason == "stop_requested":
                break
    except KeyboardInterrupt:
        status = "stopped"
        stop_reason = "keyboard_interrupt"
        if output_callback:
            output_callback("TOM loop stopped by keyboard interrupt.")

    snapshot = _finish_loop(config, latest_state, "stopped" if status == "ok" else status, stop_reason)
    return TomLoopActionResult(
        status=status,
        message=f"TOM loop finished: status={status}, iterations={iterations}, reason={stop_reason}",
        snapshot=snapshot,
        iterations=iterations,
        result=latest_result,
        warnings=warnings,
    )


def tom_loop_stop(config: AppConfig) -> TomLoopActionResult:
    paths = _paths(config)
    snapshot = tom_loop_status(config)
    if snapshot.active:
        stop_payload = {
            "requested_at": _now_iso(),
            "requested_by_pid": os.getpid(),
            "target_pid": snapshot.pid,
        }
        _write_json(paths["stop"], stop_payload)
        state = _read_json(paths["state"])
        _write_json(
            paths["state"],
            _state_with_metadata(
                config,
                state,
                {
                    "status": "stop_requested",
                    "stop_requested": True,
                    "stop_requested_at": stop_payload["requested_at"],
                },
            ),
        )
        updated = tom_loop_status(config)
        return TomLoopActionResult(
            status="stop_requested",
            message="Stop requested. The running loop will exit after the current cycle or sleep interval.",
            snapshot=updated,
        )

    if snapshot.stale_lock:
        _remove_if_exists(paths["lock"])
        _remove_if_exists(paths["stop"])
        state = _read_json(paths["state"])
        stopped = _state_with_metadata(
            config,
            state,
            {
                "status": "stopped",
                "stopped_at": _now_iso(),
                "stopped_reason": "stale_lock_cleared",
                "stop_requested": False,
            },
        )
        _write_json(paths["state"], stopped)
        return TomLoopActionResult(
            status="stopped",
            message="Stale loop lock cleared; no active loop was running.",
            snapshot=tom_loop_status(config),
        )

    state = _read_json(paths["state"])
    stopped = _state_with_metadata(
        config,
        state,
        {
            "status": "stopped",
            "stopped_at": _now_iso(),
            "stopped_reason": "no_active_loop",
            "stop_requested": False,
        },
    )
    _write_json(paths["state"], stopped)
    _remove_if_exists(paths["stop"])
    return TomLoopActionResult(
        status="stopped",
        message="No active TOM loop is running.",
        snapshot=tom_loop_status(config),
    )


def build_tom_loop_status_text(config: AppConfig) -> str:
    snapshot = tom_loop_status(config)
    lines = [
        "TOM loop status",
        f"Status: {snapshot.status}",
        f"Health: {snapshot.health_status}",
        f"Active: {snapshot.active}",
        f"PID: {snapshot.pid or 'none'}",
        f"Mode: {snapshot.mode or 'none'}",
        f"Delivery: {snapshot.channel if snapshot.deliver else 'none'}",
        f"Started: {snapshot.started_at or 'none'}",
        f"Last heartbeat: {snapshot.last_heartbeat_at or 'none'}",
        f"Heartbeat age seconds: {snapshot.heartbeat_age_seconds if snapshot.heartbeat_age_seconds is not None else 'none'}",
        f"Last cycle: {snapshot.last_cycle_mode or 'none'} {snapshot.last_cycle_finished_at or ''}".strip(),
        f"Last result: {snapshot.last_result_status or 'none'} {snapshot.last_result_summary or ''}".strip(),
        f"Quote timestamp: {snapshot.quote_timestamp or 'none'}",
        f"Market session: {snapshot.market_session or 'unknown'}",
        f"Regular market hours: {snapshot.regular_market_hours if snapshot.regular_market_hours is not None else 'unknown'}",
        f"Range timestamp: {snapshot.range_snapshot_timestamp or 'none'}",
        f"Pending notifications: {snapshot.pending_notifications if snapshot.pending_notifications is not None else 'unknown'}",
        f"Failed deliveries: {snapshot.failed_deliveries if snapshot.failed_deliveries is not None else 'unknown'}",
        f"Latest successful delivery: {snapshot.latest_successful_delivery or 'none'}",
        f"State file: {snapshot.state_path}",
        f"Recovery status: {snapshot.recovery_status}",
        "Recommended actions: "
        + (", ".join(snapshot.recommended_actions) if snapshot.recommended_actions else "none"),
        f"Clear stale lock command: {snapshot.clear_stale_lock_command}",
        f"Recommended command: {snapshot.recommended_command}",
        f"One-shot command: {snapshot.run_once_command}",
    ]
    if snapshot.stale_blockers:
        lines.append("Stale blockers: " + ", ".join(snapshot.stale_blockers))
    if snapshot.warnings:
        lines.append("Warnings: " + ", ".join(snapshot.warnings))
    if snapshot.notes:
        lines.append("Notes: " + ", ".join(snapshot.notes))
    if snapshot.recovery_notes:
        lines.append("Recovery notes: " + " ".join(snapshot.recovery_notes))
    return "\n".join(lines)


def build_tom_loop_health_text(config: AppConfig) -> str:
    snapshot = tom_loop_health(config)
    lines = [
        "TOM loop health",
        f"Health: {snapshot.health_status}",
        f"Loop status: {snapshot.status}",
        f"Active: {snapshot.active}",
        f"Heartbeat age seconds: {snapshot.heartbeat_age_seconds if snapshot.heartbeat_age_seconds is not None else 'none'}",
        f"Quote age seconds: {snapshot.quote_age_seconds if snapshot.quote_age_seconds is not None else 'none'}",
        f"Market session: {snapshot.market_session or 'unknown'}",
        f"Regular market hours: {snapshot.regular_market_hours if snapshot.regular_market_hours is not None else 'unknown'}",
        f"Pending notifications: {snapshot.pending_notifications if snapshot.pending_notifications is not None else 'unknown'}",
        f"Failed deliveries: {snapshot.failed_deliveries if snapshot.failed_deliveries is not None else 'unknown'}",
        f"Recovery status: {snapshot.recovery_status}",
        "Recommended actions: "
        + (", ".join(snapshot.recommended_actions) if snapshot.recommended_actions else "none"),
    ]
    if snapshot.stale_blockers:
        lines.append("Blockers: " + ", ".join(snapshot.stale_blockers))
    if snapshot.warnings:
        lines.append("Warnings: " + ", ".join(snapshot.warnings))
    if snapshot.notes:
        lines.append("Notes: " + ", ".join(snapshot.notes))
    if snapshot.recovery_notes:
        lines.append("Recovery notes: " + " ".join(snapshot.recovery_notes))
    return "\n".join(lines)
