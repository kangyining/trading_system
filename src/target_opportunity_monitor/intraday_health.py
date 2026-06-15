from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from .config import AppConfig
from .storage import (
    latest_intraday_gap_timestamp,
    latest_notification_delivery_timestamp,
    latest_pipeline_run,
    latest_quote_timestamp,
    latest_range_snapshot_timestamp,
    list_notification_deliveries,
    list_notification_events,
    notification_delivery_count,
    pending_notification_count,
)

TORONTO_TIMEZONE = ZoneInfo("America/Toronto")
REGULAR_MARKET_OPEN = time(9, 30)
REGULAR_MARKET_CLOSE = time(16, 0)


def _parse_timestamp(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _age_seconds(value: str | None, now: datetime) -> float | None:
    parsed = _parse_timestamp(value)
    if parsed is None:
        return None
    if now.tzinfo is not None:
        now = now.astimezone(TORONTO_TIMEZONE).replace(tzinfo=None)
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone(TORONTO_TIMEZONE).replace(tzinfo=None)
    return max((now - parsed).total_seconds(), 0.0)


def _fmt_age(seconds: float | None) -> str:
    if seconds is None:
        return "unknown"
    if seconds < 120:
        return f"{int(seconds)}s"
    minutes = seconds / 60
    if minutes < 120:
        return f"{minutes:.1f}m"
    hours = minutes / 60
    if hours < 72:
        return f"{hours:.1f}h"
    return f"{hours / 24:.1f}d"


def _safe_call(default, callback):
    try:
        return callback()
    except Exception:
        return default


def _toronto_now(now: datetime | None = None) -> datetime:
    if now is None:
        return datetime.now(TORONTO_TIMEZONE)
    if now.tzinfo is None:
        return now.replace(tzinfo=TORONTO_TIMEZONE)
    return now.astimezone(TORONTO_TIMEZONE)


def _market_session(now: datetime) -> str:
    current = _toronto_now(now)
    if current.weekday() >= 5:
        return "weekend"
    current_clock = current.time()
    if current_clock < REGULAR_MARKET_OPEN:
        return "pre_market"
    if current_clock < REGULAR_MARKET_CLOSE:
        return "regular"
    return "after_hours"


@dataclass(frozen=True)
class IntradayHealth:
    status: str
    blockers: tuple[str, ...]
    warnings: tuple[str, ...]
    notes: tuple[str, ...]
    market_session: str
    regular_market_hours: bool
    latest_intraday_cycle: str | None
    latest_intraday_cycle_status: str | None
    latest_quote_timestamp: str | None
    latest_intraday_gap_timestamp: str | None
    latest_range_snapshot_timestamp: str | None
    pending_notification_count: int
    failed_delivery_count: int
    latest_successful_delivery: str | None
    latest_failed_delivery: str | None
    quote_age_seconds: float | None
    intraday_cycle_age_seconds: float | None
    oldest_pending_notification_age_seconds: float | None
    heartbeat_command: str


def intraday_health(config: AppConfig, now: datetime | None = None) -> IntradayHealth:
    current_time = now or datetime.now()
    current_time_toronto = _toronto_now(current_time)
    market_session = _market_session(current_time_toronto)
    regular_market_hours = market_session == "regular"
    current_time_for_age = current_time_toronto.replace(tzinfo=None)
    latest_cycle = _safe_call(
        None,
        lambda: latest_pipeline_run(config.database_path, run_type="intraday_cycle"),
    )
    latest_quote = _safe_call(None, lambda: latest_quote_timestamp(config.database_path))
    latest_gap = _safe_call(
        None,
        lambda: latest_intraday_gap_timestamp(config.database_path),
    )
    latest_range = _safe_call(
        None,
        lambda: latest_range_snapshot_timestamp(config.database_path),
    )
    pending_events = tuple(
        _safe_call(
            (),
            lambda: list_notification_events(config.database_path, status="pending"),
        )
    )
    failed_deliveries = tuple(
        _safe_call(
            (),
            lambda: list_notification_deliveries(
                config.database_path,
                status="failed",
                limit=1,
            ),
        )
    )
    failed_delivery_count = _safe_call(
        0,
        lambda: notification_delivery_count(config.database_path, status="failed"),
    )
    latest_successful_delivery = _safe_call(
        None,
        lambda: latest_notification_delivery_timestamp(
            config.database_path,
            status="delivered",
        ),
    )
    oldest_pending_timestamp = min(
        (event.event_timestamp for event in pending_events if event.event_timestamp),
        default=None,
    )

    latest_cycle_timestamp = latest_cycle.started_at if latest_cycle else None
    quote_age = _age_seconds(latest_quote, current_time_for_age)
    cycle_age = _age_seconds(latest_cycle_timestamp, current_time_for_age)
    pending_age = _age_seconds(oldest_pending_timestamp, current_time_for_age)

    blockers: list[str] = []
    warnings: list[str] = []
    notes: list[str] = []

    if latest_cycle is None:
        blockers.append("no_intraday_cycle_run")
    elif latest_cycle.status == "error":
        blockers.append("latest_intraday_cycle_failed")
    elif latest_cycle.status == "warning":
        warnings.append("latest_intraday_cycle_warning")

    if latest_quote is None:
        blockers.append("missing_quote")
    elif quote_age is not None and quote_age > config.realtime_quote_stale_after_seconds:
        if regular_market_hours:
            warnings.append("stale_quote")
        else:
            notes.append("off_hours_quote_staleness_expected")

    if latest_range is None:
        blockers.append("missing_range_snapshot")

    if (
        cycle_age is not None
        and cycle_age > config.realtime_intraday_cycle_stale_after_seconds
    ):
        if regular_market_hours:
            warnings.append("stale_intraday_cycle")
        else:
            notes.append("off_hours_intraday_cycle_staleness_expected")

    if pending_events:
        warnings.append("pending_notifications")
    if (
        pending_age is not None
        and pending_age > config.realtime_notification_pending_stale_after_seconds
    ):
        warnings.append("old_pending_notifications")

    if failed_delivery_count:
        blockers.append("failed_notification_delivery")

    status = "healthy"
    if blockers:
        status = "blocked"
    elif warnings:
        status = "stale"

    latest_failed_delivery = None
    if failed_deliveries:
        failed = failed_deliveries[0]
        latest_failed_delivery = (
            f"{failed.channel} {failed.delivery_timestamp} {failed.details or ''}".strip()
        )

    return IntradayHealth(
        status=status,
        blockers=tuple(dict.fromkeys(blockers)),
        warnings=tuple(dict.fromkeys(warnings)),
        notes=tuple(dict.fromkeys(notes)),
        market_session=market_session,
        regular_market_hours=regular_market_hours,
        latest_intraday_cycle=latest_cycle_timestamp,
        latest_intraday_cycle_status=latest_cycle.status if latest_cycle else None,
        latest_quote_timestamp=latest_quote,
        latest_intraday_gap_timestamp=latest_gap,
        latest_range_snapshot_timestamp=latest_range,
        pending_notification_count=_safe_call(
            0,
            lambda: pending_notification_count(config.database_path),
        ),
        failed_delivery_count=failed_delivery_count,
        latest_successful_delivery=latest_successful_delivery,
        latest_failed_delivery=latest_failed_delivery,
        quote_age_seconds=quote_age,
        intraday_cycle_age_seconds=cycle_age,
        oldest_pending_notification_age_seconds=pending_age,
        heartbeat_command=(
            "python -m target_opportunity_monitor intraday-cycle "
            "--source auto --deliver --channel file"
        ),
    )


def build_intraday_health_text(config: AppConfig) -> str:
    health = intraday_health(config)
    lines = [
        "Intraday health check",
        f"Status: {health.status}",
        f"Market session: {health.market_session}",
        f"Regular market hours: {health.regular_market_hours}",
        "Blockers: " + (", ".join(health.blockers) if health.blockers else "none"),
        "Warnings: " + (", ".join(health.warnings) if health.warnings else "none"),
        "Notes: " + (", ".join(health.notes) if health.notes else "none"),
        (
            "Latest intraday cycle: "
            f"{health.latest_intraday_cycle_status or 'none'} "
            f"{health.latest_intraday_cycle or 'none'} "
            f"(age={_fmt_age(health.intraday_cycle_age_seconds)})"
        ),
        (
            "Latest quote timestamp: "
            f"{health.latest_quote_timestamp or 'none'} "
            f"(age={_fmt_age(health.quote_age_seconds)})"
        ),
        (
            "Latest intraday gap timestamp: "
            f"{health.latest_intraday_gap_timestamp or 'none'}"
        ),
        (
            "Latest range snapshot timestamp: "
            f"{health.latest_range_snapshot_timestamp or 'none'}"
        ),
        f"Pending notifications: {health.pending_notification_count}",
        (
            "Oldest pending notification age: "
            f"{_fmt_age(health.oldest_pending_notification_age_seconds)}"
        ),
        f"Failed notification deliveries: {health.failed_delivery_count}",
        f"Latest successful delivery: {health.latest_successful_delivery or 'none'}",
        f"Latest failed delivery: {health.latest_failed_delivery or 'none'}",
        f"Preferred heartbeat command: {health.heartbeat_command}",
    ]
    return "\n".join(lines)


def build_intraday_repair_plan_text(config: AppConfig) -> str:
    health = intraday_health(config)
    lines = [
        "Intraday repair plan",
        f"Current status: {health.status}",
        f"Market session: {health.market_session}",
        "Current blockers: " + (", ".join(health.blockers) if health.blockers else "none"),
        "Current warnings: " + (", ".join(health.warnings) if health.warnings else "none"),
        "Current notes: " + (", ".join(health.notes) if health.notes else "none"),
        "",
        "Recommended sequence:",
    ]
    if health.pending_notification_count:
        lines.append(
            "1. Drain pending notifications: "
            "python -m target_opportunity_monitor drain-pending-notifications --channel file"
        )
        step_number = 2
    else:
        step_number = 1
    lines.append(
        f"{step_number}. Run one auto-source intraday cycle: {health.heartbeat_command}"
    )
    step_number += 1
    lines.append(
        f"{step_number}. Recheck health: "
        "python -m target_opportunity_monitor intraday-health-check"
    )
    step_number += 1
    lines.append(
        f"{step_number}. If quotes are still stale, check IBKR and daily fallback: "
        "python -m target_opportunity_monitor ibkr-status"
    )
    return "\n".join(lines)


def build_notification_outbox_status_text(config: AppConfig) -> str:
    pending_events = tuple(
        _safe_call(
            (),
            lambda: list_notification_events(config.database_path, status="pending"),
        )
    )
    failed_events = tuple(
        _safe_call(
            (),
            lambda: list_notification_events(
                config.database_path,
                status="delivery_failed",
            ),
        )
    )
    latest_file_delivery = _safe_call(
        None,
        lambda: latest_notification_delivery_timestamp(
            config.database_path,
            channel="file",
            status="delivered",
        ),
    )
    latest_failed_delivery = tuple(
        _safe_call(
            (),
            lambda: list_notification_deliveries(
                config.database_path,
                status="failed",
                limit=1,
            ),
        )
    )
    outbox_dir = config.notification_outbox_dir
    file_count = 0
    if outbox_dir.exists():
        file_count = sum(1 for path in outbox_dir.rglob("*") if path.is_file())

    lines = [
        "Notification outbox status",
        f"Outbox directory: {outbox_dir}",
        f"Outbox files: {file_count}",
        f"Pending notification events: {len(pending_events)}",
        f"Delivery-failed notification events: {len(failed_events)}",
        f"Latest file delivery: {latest_file_delivery or 'none'}",
        (
            "Latest failed delivery: "
            + (
                f"{latest_failed_delivery[0].channel} "
                f"{latest_failed_delivery[0].delivery_timestamp} "
                f"{latest_failed_delivery[0].details or ''}"
                if latest_failed_delivery
                else "none"
            )
        ),
    ]
    return "\n".join(lines)
