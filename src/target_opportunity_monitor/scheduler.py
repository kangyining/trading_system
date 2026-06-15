from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import re
import tomllib

from .config import AppConfig
from .intraday_health import intraday_health
from .storage import latest_pipeline_run


INTRADAY_HEARTBEAT_COMMAND = (
    "python -m target_opportunity_monitor intraday-cycle "
    "--source auto --deliver --channel file"
)


@dataclass(frozen=True)
class IntendedAutomationJob:
    job_key: str
    automation_id: str
    name: str
    kind: str
    cadence: str
    timezone: str
    command: str
    required_prompt_fragments: tuple[str, ...]
    run_type: str | None = None


@dataclass(frozen=True)
class AutomationMetadata:
    automation_id: str
    name: str
    kind: str
    status: str
    rrule: str | None
    prompt: str
    path: Path
    target_thread_id: str | None = None


@dataclass(frozen=True)
class SchedulerJobAudit:
    job_key: str
    automation_id: str
    name: str
    status: str
    intended_command: str
    actual_command: str | None
    cadence: str
    timezone: str
    automation_path: Path | None
    latest_run_at: str | None
    warnings: tuple[str, ...]
    next_action: str


@dataclass(frozen=True)
class SchedulerAudit:
    status: str
    automations_dir: Path
    jobs: tuple[SchedulerJobAudit, ...]
    warnings: tuple[str, ...]
    latest_intraday_cycle_at: str | None
    latest_daily_refresh_at: str | None


def intended_scheduler_jobs() -> tuple[IntendedAutomationJob, ...]:
    return (
        IntendedAutomationJob(
            job_key="intraday_heartbeat",
            automation_id="tom-intraday-probe",
            name="TOM Intraday Heartbeat",
            kind="heartbeat",
            cadence="weekdays market hours, every 10 minutes",
            timezone="America/Toronto",
            command=INTRADAY_HEARTBEAT_COMMAND,
            required_prompt_fragments=(INTRADAY_HEARTBEAT_COMMAND,),
            run_type="intraday_cycle",
        ),
        IntendedAutomationJob(
            job_key="morning_check",
            automation_id="tom-morning-check",
            name="TOM Morning Check",
            kind="cron",
            cadence="weekdays 8:30 AM",
            timezone="America/Toronto",
            command=(
                "python -m target_opportunity_monitor ibkr-status; "
                "python -m target_opportunity_monitor verify-universe; "
                "python -m target_opportunity_monitor intraday-status"
            ),
            required_prompt_fragments=(
                "python -m target_opportunity_monitor ibkr-status",
                "python -m target_opportunity_monitor verify-universe",
                "python -m target_opportunity_monitor intraday-status",
            ),
        ),
        IntendedAutomationJob(
            job_key="daily_refresh",
            automation_id="tom-daily-refresh",
            name="TOM Daily Refresh",
            kind="cron",
            cadence="weekdays 6:30 PM",
            timezone="America/Toronto",
            command="python -m target_opportunity_monitor refresh-data --daily-only",
            required_prompt_fragments=(
                "python -m target_opportunity_monitor refresh-data --daily-only",
            ),
            run_type="daily_refresh",
        ),
        IntendedAutomationJob(
            job_key="daily_retry",
            automation_id="tom-daily-retry",
            name="TOM Daily Retry",
            kind="cron",
            cadence="weekdays 8:30 PM",
            timezone="America/Toronto",
            command=(
                "python -m target_opportunity_monitor status; "
                "python -m target_opportunity_monitor scheduler-status; "
                "conditional python -m target_opportunity_monitor refresh-data --daily-only"
            ),
            required_prompt_fragments=(
                "python -m target_opportunity_monitor status",
                "python -m target_opportunity_monitor scheduler-status",
                "python -m target_opportunity_monitor refresh-data --daily-only",
            ),
        ),
    )


def _automation_tomls(automations_dir: Path) -> tuple[Path, ...]:
    if not automations_dir.exists():
        return ()
    return tuple(sorted(automations_dir.rglob("automation.toml")))


def _load_automation_metadata(automations_dir: Path) -> dict[str, AutomationMetadata]:
    metadata: dict[str, AutomationMetadata] = {}
    for path in _automation_tomls(automations_dir):
        try:
            raw = tomllib.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        automation_id = str(raw.get("id") or path.parent.name)
        metadata[automation_id] = AutomationMetadata(
            automation_id=automation_id,
            name=str(raw.get("name") or automation_id),
            kind=str(raw.get("kind") or ""),
            status=str(raw.get("status") or ""),
            rrule=str(raw.get("rrule")) if raw.get("rrule") else None,
            prompt=str(raw.get("prompt") or ""),
            path=path,
            target_thread_id=(
                str(raw.get("target_thread_id"))
                if raw.get("target_thread_id")
                else None
            ),
        )
    return metadata


def _extract_actual_command(prompt: str, intended_command: str) -> str | None:
    if intended_command in prompt:
        return intended_command
    old_intraday = (
        "python -m target_opportunity_monitor intraday-cycle "
        "--source ibkr --deliver --channel file"
    )
    if old_intraday in prompt:
        return old_intraday
    match = re.search(r"python -m target_opportunity_monitor [^`\"\n]+", prompt)
    return match.group(0).strip() if match else None


def _latest_run_timestamp(config: AppConfig, run_type: str | None) -> str | None:
    if not run_type:
        return None
    try:
        latest = latest_pipeline_run(config.database_path, run_type=run_type)
    except Exception:
        return None
    return latest.started_at if latest else None


def _age_seconds(timestamp: str | None) -> float | None:
    if not timestamp:
        return None
    try:
        parsed = datetime.fromisoformat(timestamp)
    except ValueError:
        return None
    return max((datetime.now() - parsed).total_seconds(), 0.0)


def _job_status(
    config: AppConfig,
    job: IntendedAutomationJob,
    metadata: AutomationMetadata | None,
) -> SchedulerJobAudit:
    latest_run_at = _latest_run_timestamp(config, job.run_type)
    warnings: list[str] = []

    if metadata is None:
        return SchedulerJobAudit(
            job_key=job.job_key,
            automation_id=job.automation_id,
            name=job.name,
            status="missing",
            intended_command=job.command,
            actual_command=None,
            cadence=job.cadence,
            timezone=job.timezone,
            automation_path=None,
            latest_run_at=latest_run_at,
            warnings=("automation_metadata_missing",),
            next_action=f"Create Codex automation {job.automation_id}",
        )

    actual_command = _extract_actual_command(metadata.prompt, job.command)
    status = "configured"
    next_action = "none"
    if metadata.status.upper() != "ACTIVE":
        status = "disabled"
        warnings.append("automation_disabled")
        next_action = f"Enable Codex automation {job.automation_id}"
    elif metadata.kind != job.kind:
        status = "stale_command"
        warnings.append(f"kind_mismatch:{metadata.kind or 'unknown'}")
        next_action = f"Update Codex automation {job.automation_id} kind/prompt"
    elif any(fragment not in metadata.prompt for fragment in job.required_prompt_fragments):
        status = "stale_command"
        warnings.append("prompt_missing_intended_command")
        if "--source ibkr" in metadata.prompt and "--source auto" not in metadata.prompt:
            warnings.append("old_ibkr_only_heartbeat")
        next_action = f"Update Codex automation {job.automation_id} prompt"
    else:
        run_age = _age_seconds(latest_run_at)
        if (
            job.run_type == "intraday_cycle"
            and run_age is not None
            and run_age > config.realtime_intraday_cycle_stale_after_seconds
        ):
            status = "last_run_stale"
            warnings.append("latest_intraday_cycle_stale")
            next_action = "Run intraday-cycle --source auto or wait for next heartbeat"
        elif job.run_type == "daily_refresh" and latest_run_at is None:
            warnings.append("no_prior_daily_refresh_run")
        elif job.run_type and latest_run_at is None:
            warnings.append(f"no_prior_{job.run_type}_run")

    return SchedulerJobAudit(
        job_key=job.job_key,
        automation_id=job.automation_id,
        name=metadata.name or job.name,
        status=status,
        intended_command=job.command,
        actual_command=actual_command,
        cadence=job.cadence,
        timezone=job.timezone,
        automation_path=metadata.path,
        latest_run_at=latest_run_at,
        warnings=tuple(dict.fromkeys(warnings)),
        next_action=next_action,
    )


def audit_scheduler(config: AppConfig) -> SchedulerAudit:
    automations_dir = config.scheduler_automations_dir
    metadata_by_id = _load_automation_metadata(automations_dir)
    jobs = tuple(
        _job_status(config, job, metadata_by_id.get(job.automation_id))
        for job in intended_scheduler_jobs()
    )
    warnings: list[str] = []
    if not automations_dir.exists():
        warnings.append("automation_directory_missing")
    elif not metadata_by_id:
        warnings.append("automation_metadata_empty")

    precedence = (
        "stale_command",
        "missing",
        "disabled",
        "last_run_stale",
        "unknown_external_state",
        "configured",
    )
    job_statuses = {job.status for job in jobs}
    status = "configured"
    for candidate in precedence:
        if candidate in job_statuses:
            status = candidate
            break
    if warnings and status == "configured":
        status = "unknown_external_state"

    latest_intraday = _latest_run_timestamp(config, "intraday_cycle")
    latest_refresh = _latest_run_timestamp(config, "daily_refresh")
    return SchedulerAudit(
        status=status,
        automations_dir=automations_dir,
        jobs=jobs,
        warnings=tuple(dict.fromkeys(warnings)),
        latest_intraday_cycle_at=latest_intraday,
        latest_daily_refresh_at=latest_refresh,
    )


def _fmt_path(path: Path | None, config: AppConfig) -> str:
    if path is None:
        return "none"
    try:
        return str(path.relative_to(config.project_root))
    except ValueError:
        return str(path)


def _fmt_job(job: SchedulerJobAudit, config: AppConfig) -> str:
    warnings = ", ".join(job.warnings) if job.warnings else "none"
    return (
        f"{job.name} | {job.status} | id={job.automation_id} | "
        f"cadence={job.cadence} {job.timezone} | "
        f"actual={job.actual_command or 'none'} | "
        f"latest_run={job.latest_run_at or 'none'} | "
        f"path={_fmt_path(job.automation_path, config)} | "
        f"warnings={warnings}"
    )


def build_scheduler_audit_text(config: AppConfig) -> str:
    audit = audit_scheduler(config)
    lines = [
        "Scheduler audit",
        f"Status: {audit.status}",
        f"Automations directory: {audit.automations_dir}",
        "Warnings: " + (", ".join(audit.warnings) if audit.warnings else "none"),
        f"Latest intraday cycle: {audit.latest_intraday_cycle_at or 'none'}",
        f"Latest daily refresh: {audit.latest_daily_refresh_at or 'none'}",
        "",
        "Jobs:",
    ]
    lines.extend(_fmt_job(job, config) for job in audit.jobs)
    return "\n".join(lines)


def build_scheduler_repair_plan_text(config: AppConfig) -> str:
    audit = audit_scheduler(config)
    lines = [
        "Scheduler repair plan",
        f"Current reconciliation status: {audit.status}",
        "Warnings: " + (", ".join(audit.warnings) if audit.warnings else "none"),
        "",
        "Actions:",
    ]
    action_count = 0
    for job in audit.jobs:
        if job.status == "configured":
            continue
        action_count += 1
        lines.append(
            f"{action_count}. {job.next_action}: expected `{job.intended_command}`"
        )
        if job.actual_command:
            lines.append(f"   Current command: `{job.actual_command}`")
        if job.automation_path:
            lines.append(f"   Metadata: {_fmt_path(job.automation_path, config)}")
    if action_count == 0:
        lines.append("1. No scheduler metadata repair needed.")
    lines.extend(
        (
            "",
            "Recommended heartbeat command:",
            INTRADAY_HEARTBEAT_COMMAND,
            "",
            "Validation commands:",
            "python -m target_opportunity_monitor intraday-cycle --source auto --drain-first --deliver --channel file",
            "python -m target_opportunity_monitor scheduler-audit",
            "python -m target_opportunity_monitor notification-delivery-report",
        )
    )
    return "\n".join(lines)


def build_scheduler_automation_status_text(config: AppConfig) -> str:
    audit = audit_scheduler(config)
    health = intraday_health(config)
    lines = [
        "Scheduler automation status",
        f"Reconciliation status: {audit.status}",
        f"Intraday health: {health.status}",
        f"Actual heartbeat command: {_actual_heartbeat_command(audit) or 'none'}",
        f"Intended heartbeat command: {INTRADAY_HEARTBEAT_COMMAND}",
        "Stale/missing automation warnings: "
        + (
            ", ".join(
                warning
                for job in audit.jobs
                for warning in job.warnings
                if job.status != "configured"
            )
            or "none"
        ),
        "",
        "Jobs:",
    ]
    lines.extend(_fmt_job(job, config) for job in audit.jobs)
    return "\n".join(lines)


def _actual_heartbeat_command(audit: SchedulerAudit) -> str | None:
    for job in audit.jobs:
        if job.job_key == "intraday_heartbeat":
            return job.actual_command
    return None
