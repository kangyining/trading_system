from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
import time as time_module
from typing import Callable
from zoneinfo import ZoneInfo

from .config import AppConfig
from .ibkr_provider import check_ibkr_status
from .intraday_health import intraday_health
from .missing_tickers import SOURCE_ACCOUNT_CONTEXT, run_missing_ticker_automation
from .pipeline import PipelineExecutionResult, PipelineStepSummary, run_intraday_cycle, run_refresh_data
from .readiness import verify_universe
from .research_preparation import (
    RESEARCH_PREPARATION_AUTO_STEP_NAME,
    research_preparation_autopilot_due,
    research_preparation_autopilot_warnings,
    research_preparation_run_row_count,
    run_research_preparation,
)
from .scheduler import audit_scheduler, intended_scheduler_jobs
from .storage import (
    finish_pipeline_run,
    insert_pipeline_step_result,
    latest_pipeline_run,
    latest_price_date,
    start_pipeline_run,
)


MANUAL_OPS_MODES = ("auto", "morning", "intraday", "daily-refresh", "daily-retry", "all")
MANUAL_OPS_DEFAULT_COMMAND = (
    "python -m target_opportunity_monitor manual-ops-loop "
    "--mode auto --deliver --channel file"
)
MANUAL_OPS_SINGLE_CYCLE_COMMAND = (
    "python -m target_opportunity_monitor manual-ops-cycle "
    "--mode auto --deliver --channel file"
)
TOM_AUTOMATION_IDS = tuple(job.automation_id for job in intended_scheduler_jobs())
BROWSER_CONTENT_AUTOMATION_IDS = (
    "daily-aleabitoreddit-q-a-ingestion",
    "trump-truth-social-posts-morning",
)
TORONTO_TIMEZONE = ZoneInfo("America/Toronto")


@dataclass(frozen=True)
class ManualOpsStatus:
    latest_manual_ops_cycle: str | None
    latest_manual_ops_status: str | None
    latest_manual_ops_summary: str | None
    tom_automation_states: tuple[str, ...]
    pause_recommendations: tuple[str, ...]
    excluded_automation_ids: tuple[str, ...]
    recommended_command: str


@dataclass(frozen=True)
class ManualOpsLoopResult:
    iterations: int
    status: str
    stopped_reason: str
    summaries: tuple[str, ...]


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _toronto_now(now: datetime | None = None) -> datetime:
    if now is None:
        return datetime.now(TORONTO_TIMEZONE)
    if now.tzinfo is None:
        return now.replace(tzinfo=TORONTO_TIMEZONE)
    return now.astimezone(TORONTO_TIMEZONE)


def _is_weekday(current_time: datetime) -> bool:
    return current_time.weekday() < 5


def resolve_manual_ops_mode(mode: str, now: datetime | None = None) -> str:
    if mode not in MANUAL_OPS_MODES:
        raise ValueError(f"Unsupported manual ops mode: {mode}")
    if mode != "auto":
        return mode

    current_time = _toronto_now(now)
    current_clock = current_time.time()
    if _is_weekday(current_time) and time(8, 0) <= current_clock < time(9, 40):
        return "morning"
    if _is_weekday(current_time) and time(9, 40) <= current_clock <= time(15, 50):
        return "intraday"
    if _is_weekday(current_time) and time(15, 50) < current_clock < time(20, 30):
        return "daily-refresh"
    return "daily-retry"


def resolve_manual_ops_loop_mode(mode: str, now: datetime | None = None) -> str:
    selected_mode = resolve_manual_ops_mode(mode, now=now)
    if mode == "auto" and selected_mode == "daily-refresh":
        return "daily-retry"
    return selected_mode


def _planned_step_names(selected_mode: str, deliver: bool, channel: str) -> tuple[str, ...]:
    if selected_mode == "morning":
        return (
            "ibkr-status",
            "resolve-missing-tickers",
            RESEARCH_PREPARATION_AUTO_STEP_NAME,
            "verify-universe",
            "intraday-status",
            "scheduler-audit",
        )
    if selected_mode == "intraday":
        return (f"intraday-cycle-{channel if deliver else 'no-delivery'}",)
    if selected_mode == "daily-refresh":
        return ("daily-refresh",)
    if selected_mode == "daily-retry":
        return ("daily-retry-check", RESEARCH_PREPARATION_AUTO_STEP_NAME)
    if selected_mode == "all":
        return (
            "ibkr-status",
            "resolve-missing-tickers",
            RESEARCH_PREPARATION_AUTO_STEP_NAME,
            "verify-universe",
            "intraday-status",
            "scheduler-audit",
            f"intraday-cycle-{channel if deliver else 'no-delivery'}",
            "daily-refresh",
            "daily-retry-check",
        )
    raise ValueError(f"Unsupported manual ops mode: {selected_mode}")


def _expected_price_date(now: datetime | None = None) -> str:
    current_time = _toronto_now(now)
    candidate = current_time.date()
    if current_time.time() < time(16, 0):
        candidate -= timedelta(days=1)
    while candidate.weekday() >= 5:
        candidate -= timedelta(days=1)
    return candidate.isoformat()


def _daily_refresh_needed(config: AppConfig, now: datetime | None = None) -> tuple[bool, tuple[str, ...]]:
    reasons: list[str] = []
    latest_refresh = latest_pipeline_run(config.database_path, run_type="daily_refresh")
    if latest_refresh is None:
        reasons.append("no_daily_refresh_run")
    elif latest_refresh.status != "ok":
        reasons.append(f"latest_daily_refresh_{latest_refresh.status}")

    latest_price = latest_price_date(config.database_path)
    expected_price = _expected_price_date(now)
    if latest_price is None:
        reasons.append("missing_price_date")
    elif latest_price < expected_price:
        reasons.append(f"stale_price_date:{latest_price}<expected:{expected_price}")
    return bool(reasons), tuple(reasons)


def _nested_pipeline_step(result: PipelineExecutionResult) -> tuple[int, tuple[str, ...]]:
    warnings: list[str] = []
    if result.status == "error":
        raise RuntimeError(result.summary)
    if result.status != "ok":
        warnings.append(f"nested_pipeline_status:{result.status}")
    for step in result.steps:
        if step.status == "error":
            raise RuntimeError(f"{step.step_name}: {'; '.join(step.warnings)}")
        if step.warnings:
            warnings.append(f"{step.step_name}:{';'.join(step.warnings)}")
    return len(result.steps), tuple(warnings)


def _run_manual_step(
    config: AppConfig,
    pipeline_run_id: int,
    step_name: str,
    action: Callable[[], tuple[int, tuple[str, ...]]],
    required: bool = False,
) -> PipelineStepSummary:
    started_at = _now_iso()
    try:
        rows_loaded, warnings = action()
        status = "warning" if warnings else "ok"
    except Exception as error:
        rows_loaded = 0
        warnings = (str(error),)
        status = "error" if required else "warning"
    finished_at = _now_iso()
    insert_pipeline_step_result(
        config.database_path,
        pipeline_run_id=pipeline_run_id,
        step_name=step_name,
        status=status,
        rows_loaded=rows_loaded,
        warnings=", ".join(warnings) if warnings else None,
        source="manual_ops",
        started_at=started_at,
        finished_at=finished_at,
    )
    return PipelineStepSummary(
        step_name=step_name,
        status=status,
        rows_loaded=rows_loaded,
        warnings=warnings,
    )


def _ibkr_status_step(config: AppConfig) -> tuple[int, tuple[str, ...]]:
    result = check_ibkr_status(config)
    warnings = list(result.warnings)
    if not result.connected:
        warnings.append("ibkr_not_connected")
    return result.managed_account_count, tuple(warnings)


def _verify_universe_step(config: AppConfig) -> tuple[int, tuple[str, ...]]:
    result = verify_universe(config, intraday=True)
    warnings = [
        f"{status.ticker}:{';'.join(status.warnings)}"
        for status in result.statuses
        if status.warnings
    ]
    return result.ready_count, tuple(warnings)


def _intraday_status_step(config: AppConfig) -> tuple[int, tuple[str, ...]]:
    health = intraday_health(config)
    warnings = tuple(health.blockers + health.warnings)
    return health.pending_notification_count, warnings


def _scheduler_audit_step(config: AppConfig) -> tuple[int, tuple[str, ...]]:
    audit = audit_scheduler(config)
    warnings = list(audit.warnings)
    for job in audit.jobs:
        if job.status not in {"configured", "last_run_stale"}:
            warnings.append(f"{job.automation_id}:{job.status}")
    return len(audit.jobs), tuple(warnings)


def _missing_ticker_resolver_step(config: AppConfig) -> tuple[int, tuple[str, ...]]:
    result = run_missing_ticker_automation(
        config,
        source=SOURCE_ACCOUNT_CONTEXT,
        apply_ready=True,
        hydrate=True,
    )
    rows_loaded = result.detected_count + result.onboarded_count + result.hydrated_count
    warnings = list(result.warnings)
    if result.onboarded_tickers:
        warnings.append("onboarded:" + ",".join(result.onboarded_tickers))
    if result.hydrated_tickers:
        warnings.append("hydrated:" + ",".join(result.hydrated_tickers))
    return rows_loaded, tuple(dict.fromkeys(warnings))


def _research_preparation_auto_step(
    config: AppConfig,
    now: datetime | None = None,
) -> tuple[int, tuple[str, ...]]:
    if not config.research_preparation_auto_enabled:
        return 0, ()
    if not research_preparation_autopilot_due(config, now=now):
        return 0, ()
    result = run_research_preparation(
        config,
        source=config.research_preparation_auto_source,
        action="all_safe",
        confirm=True,
    )
    return (
        research_preparation_run_row_count(result),
        research_preparation_autopilot_warnings(result),
    )


def _intraday_cycle_step(
    config: AppConfig,
    deliver: bool,
    channel: str,
) -> tuple[int, tuple[str, ...]]:
    return _nested_pipeline_step(
        run_intraday_cycle(
            config,
            source="auto",
            deliver=deliver,
            channel=channel,
            drain_first=deliver,
        )
    )


def _daily_refresh_step(config: AppConfig) -> tuple[int, tuple[str, ...]]:
    return _nested_pipeline_step(run_refresh_data(config, daily=True))


def _daily_retry_step(config: AppConfig, now: datetime | None = None) -> tuple[int, tuple[str, ...]]:
    needed, reasons = _daily_refresh_needed(config, now=now)
    if not needed:
        return 0, ()
    rows_loaded, warnings = _nested_pipeline_step(run_refresh_data(config, daily=True))
    return rows_loaded, tuple(reasons + warnings)


def _append_steps_for_mode(
    config: AppConfig,
    pipeline_run_id: int,
    selected_mode: str,
    deliver: bool,
    channel: str,
    now: datetime | None,
) -> tuple[PipelineStepSummary, ...]:
    steps: list[PipelineStepSummary] = []
    if selected_mode in {"morning", "all"}:
        steps.append(_run_manual_step(config, pipeline_run_id, "ibkr-status", lambda: _ibkr_status_step(config)))
        steps.append(
            _run_manual_step(
                config,
                pipeline_run_id,
                "resolve-missing-tickers",
                lambda: _missing_ticker_resolver_step(config),
            )
        )
        steps.append(
            _run_manual_step(
                config,
                pipeline_run_id,
                RESEARCH_PREPARATION_AUTO_STEP_NAME,
                lambda: _research_preparation_auto_step(config, now=now),
            )
        )
        steps.append(_run_manual_step(config, pipeline_run_id, "verify-universe", lambda: _verify_universe_step(config)))
        steps.append(_run_manual_step(config, pipeline_run_id, "intraday-status", lambda: _intraday_status_step(config)))
        steps.append(_run_manual_step(config, pipeline_run_id, "scheduler-audit", lambda: _scheduler_audit_step(config)))
    if selected_mode in {"intraday", "all"}:
        steps.append(
            _run_manual_step(
                config,
                pipeline_run_id,
                "intraday-cycle",
                lambda: _intraday_cycle_step(config, deliver=deliver, channel=channel),
                required=True,
            )
        )
    if selected_mode in {"daily-refresh", "all"}:
        steps.append(
            _run_manual_step(
                config,
                pipeline_run_id,
                "daily-refresh",
                lambda: _daily_refresh_step(config),
                required=True,
            )
        )
    if selected_mode == "daily-retry" or selected_mode == "all":
        steps.append(
            _run_manual_step(
                config,
                pipeline_run_id,
                "daily-retry-check",
                lambda: _daily_retry_step(config, now=now),
                required=True,
            )
        )
    if selected_mode == "daily-retry":
        steps.append(
            _run_manual_step(
                config,
                pipeline_run_id,
                RESEARCH_PREPARATION_AUTO_STEP_NAME,
                lambda: _research_preparation_auto_step(config, now=now),
            )
        )
    return tuple(steps)


def run_manual_ops_cycle(
    config: AppConfig,
    mode: str = "auto",
    deliver: bool = False,
    channel: str = "file",
    dry_run: bool = False,
    now: datetime | None = None,
) -> PipelineExecutionResult:
    selected_mode = resolve_manual_ops_mode(mode, now=now)
    if dry_run:
        steps = tuple(
            PipelineStepSummary(step_name=name, status="planned", rows_loaded=0, warnings=())
            for name in _planned_step_names(selected_mode, deliver=deliver, channel=channel)
        )
        summary = (
            f"manual_ops_cycle: status=planned, requested_mode={mode}, "
            f"selected_mode={selected_mode}, steps={len(steps)}, dry_run=True"
        )
        return PipelineExecutionResult(
            pipeline_run_id=0,
            run_type="manual_ops_cycle",
            status="planned",
            steps=steps,
            summary=summary,
        )

    pipeline_run_id = start_pipeline_run(
        config.database_path,
        "manual_ops_cycle",
        source="manual_ops",
    )
    steps = _append_steps_for_mode(
        config,
        pipeline_run_id,
        selected_mode,
        deliver=deliver,
        channel=channel,
        now=now,
    )
    status = "error" if any(step.status == "error" for step in steps) else "ok"
    warning_count = sum(1 for step in steps if step.status == "warning")
    summary = (
        f"manual_ops_cycle: status={status}, requested_mode={mode}, "
        f"selected_mode={selected_mode}, steps={len(steps)}, warnings={warning_count}, "
        f"deliver={deliver}, channel={channel if deliver else 'none'}"
    )
    finish_pipeline_run(config.database_path, pipeline_run_id, status, summary)
    return PipelineExecutionResult(
        pipeline_run_id=pipeline_run_id,
        run_type="manual_ops_cycle",
        status=status,
        steps=steps,
        summary=summary,
    )


def run_manual_ops_loop(
    config: AppConfig,
    mode: str = "auto",
    deliver: bool = False,
    channel: str = "file",
    interval_seconds: int | None = None,
    max_iterations: int | None = None,
    sleep_func: Callable[[float], None] = time_module.sleep,
    now_func: Callable[[], datetime] | None = None,
    output_callback: Callable[[str], None] | None = None,
) -> ManualOpsLoopResult:
    if max_iterations is not None and max_iterations <= 0:
        raise ValueError("max_iterations must be positive when supplied")
    interval = (
        config.realtime_manual_ops_loop_interval_seconds
        if interval_seconds is None
        else interval_seconds
    )
    if interval <= 0:
        raise ValueError("interval_seconds must be positive")

    summaries: list[str] = []
    iterations = 0
    status = "ok"
    stopped_reason = "max_iterations_reached" if max_iterations else "interrupted"
    try:
        while True:
            current_time = now_func() if now_func else None
            selected_mode = resolve_manual_ops_loop_mode(mode, now=current_time)
            result = run_manual_ops_cycle(
                config,
                mode=selected_mode,
                deliver=deliver,
                channel=channel,
                now=current_time,
            )
            iterations += 1
            summaries.append(result.summary)
            if output_callback:
                output_callback(
                    f"Iteration {iterations}: {result.summary}"
                )
            if result.status == "error":
                status = "error"
                stopped_reason = "cycle_error"
                break
            if max_iterations is not None and iterations >= max_iterations:
                stopped_reason = "max_iterations_reached"
                break
            if output_callback:
                output_callback(f"Sleeping {interval} seconds before next manual ops cycle.")
            sleep_func(interval)
    except KeyboardInterrupt:
        stopped_reason = "keyboard_interrupt"
        status = "stopped"
        if output_callback:
            output_callback("Manual ops loop stopped by keyboard interrupt.")

    return ManualOpsLoopResult(
        iterations=iterations,
        status=status,
        stopped_reason=stopped_reason,
        summaries=tuple(summaries),
    )


def manual_ops_status(config: AppConfig) -> ManualOpsStatus:
    latest = latest_pipeline_run(config.database_path, run_type="manual_ops_cycle")
    audit = audit_scheduler(config)
    states = tuple(
        f"{job.automation_id}:{job.status}" for job in audit.jobs
    )
    return ManualOpsStatus(
        latest_manual_ops_cycle=latest.started_at if latest else None,
        latest_manual_ops_status=latest.status if latest else None,
        latest_manual_ops_summary=latest.summary if latest else None,
        tom_automation_states=states,
        pause_recommendations=TOM_AUTOMATION_IDS,
        excluded_automation_ids=BROWSER_CONTENT_AUTOMATION_IDS,
        recommended_command=MANUAL_OPS_DEFAULT_COMMAND,
    )


def build_manual_ops_status_text(config: AppConfig) -> str:
    status = manual_ops_status(config)
    lines = [
        "Manual TOM ops status",
        f"Recommended command: {status.recommended_command}",
        (
            "One-shot command: "
            f"{MANUAL_OPS_SINGLE_CYCLE_COMMAND}"
        ),
        (
            "Latest manual ops cycle: "
            + (
                f"{status.latest_manual_ops_status} {status.latest_manual_ops_cycle} "
                f"{status.latest_manual_ops_summary or ''}".strip()
                if status.latest_manual_ops_cycle
                else "none"
            )
        ),
        "TOM automations to pause after verification: "
        + ", ".join(status.pause_recommendations),
        "Browser/content automations excluded: "
        + ", ".join(status.excluded_automation_ids),
        "TOM automation states: "
        + (", ".join(status.tom_automation_states) if status.tom_automation_states else "none"),
    ]
    return "\n".join(lines)
