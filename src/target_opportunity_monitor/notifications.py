from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
import json
import os
from pathlib import Path
import urllib.error
import urllib.request

from .config import AppConfig
from .storage import (
    NotificationDelivery,
    NotificationEvent,
    NotificationEventStatus,
    RangeSnapshot,
    list_notification_events,
    list_notification_deliveries,
    mark_notification_event_delivered,
    mark_notification_event_status,
    notification_delivery_count,
    recent_notification_exists,
    upsert_notification_delivery,
    upsert_notification_event,
)


ACTIONABLE_RANGE_STATES = {
    "strong_buy",
    "starter_buy",
    "add_candidate",
    "trim",
    "reduce_or_sell",
    "risk_review",
}


@dataclass(frozen=True)
class NotificationCreateResult:
    created_count: int
    skipped_count: int
    events: tuple[NotificationEvent, ...]


@dataclass(frozen=True)
class NotificationDeliveryResult:
    delivered_count: int
    events: tuple[NotificationEventStatus, ...]
    failed_count: int = 0
    warnings: tuple[str, ...] = ()
    outbox_paths: tuple[Path, ...] = ()


@dataclass(frozen=True)
class NotificationChannelTestResult:
    channel: str
    status: str
    warnings: tuple[str, ...] = ()
    outbox_paths: tuple[Path, ...] = ()
    details: str | None = None


def _parse_timestamp(value: str) -> datetime:
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return datetime.now()


def _severity(range_state: str) -> str:
    if range_state in {"reduce_or_sell", "risk_review"}:
        return "high"
    if range_state == "strong_buy":
        return "high"
    if range_state in {"starter_buy", "add_candidate", "trim"}:
        return "medium"
    return "low"


def _range_level(snapshot: RangeSnapshot) -> float | None:
    if snapshot.range_state == "strong_buy":
        return snapshot.strong_buy_below or snapshot.nav_action_discount_below
    if snapshot.range_state == "starter_buy":
        return snapshot.starter_buy_below or snapshot.nav_watch_discount_below
    if snapshot.range_state == "add_candidate":
        return snapshot.add_below
    if snapshot.range_state == "trim":
        return snapshot.trim_above or snapshot.nav_premium_warning_above
    if snapshot.range_state == "reduce_or_sell":
        return snapshot.reduce_or_sell_above
    if snapshot.range_state == "risk_review":
        return snapshot.risk_review_below or snapshot.etf_risk_review_level
    return None


def _event_payload(event: NotificationEventStatus) -> dict[str, object]:
    return {
        "notification_event_id": event.notification_event_id,
        "ticker": event.ticker,
        "event_timestamp": event.event_timestamp,
        "event_type": event.event_type,
        "asset_type": event.asset_type,
        "severity": event.severity,
        "previous_state": event.previous_state,
        "current_state": event.current_state,
        "trigger_price": event.trigger_price,
        "range_level": event.range_level,
        "reason_codes": event.reason_codes,
        "cooldown_until": event.cooldown_until,
        "model_version": event.model_version,
    }


def _delivery_details(event: NotificationEventStatus) -> str:
    return (
        f"{event.ticker} {event.current_state} at "
        f"{event.trigger_price if event.trigger_price is not None else 'n/a'}"
    )


def _write_file_outbox(
    config: AppConfig,
    events: tuple[NotificationEventStatus, ...],
    now: str,
    prefix: str = "notifications",
) -> tuple[Path, Path]:
    outbox_dir = config.notification_outbox_dir / date.today().isoformat()
    outbox_dir.mkdir(parents=True, exist_ok=True)
    safe_timestamp = now.replace(":", "").replace("-", "")
    jsonl_path = outbox_dir / f"{prefix}-{safe_timestamp}.jsonl"
    markdown_path = outbox_dir / f"{prefix}-{safe_timestamp}.md"

    with jsonl_path.open("w", encoding="utf-8", newline="\n") as output_file:
        for event in events:
            output_file.write(json.dumps(_event_payload(event), sort_keys=True) + "\n")

    lines = [
        "# TOM Notification Outbox",
        "",
        f"Generated: {now}",
        "",
    ]
    if not events:
        lines.append("No pending notification events.")
    for event in events:
        lines.extend(
            (
                f"## {event.ticker} - {event.current_state}",
                "",
                f"- Severity: `{event.severity or 'none'}`",
                f"- Price: `{event.trigger_price if event.trigger_price is not None else 'n/a'}`",
                f"- Range level: `{event.range_level if event.range_level is not None else 'n/a'}`",
                f"- Previous state: `{event.previous_state or 'none'}`",
                f"- Reason codes: `{event.reason_codes or 'none'}`",
                "",
            )
        )
    markdown_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return jsonl_path, markdown_path


def _post_webhook(events: tuple[NotificationEventStatus, ...]) -> tuple[bool, str]:
    webhook_url = os.environ.get("TOM_NOTIFICATION_WEBHOOK_URL")
    if not webhook_url:
        return False, "missing_webhook_url"
    payload = json.dumps(
        {
            "source": "target_opportunity_monitor",
            "event_count": len(events),
            "events": [_event_payload(event) for event in events],
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        webhook_url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            status_code = getattr(response, "status", 200)
            if 200 <= int(status_code) < 300:
                return True, f"http_{status_code}"
            return False, f"http_{status_code}"
    except urllib.error.HTTPError as error:
        return False, f"http_{error.code}"
    except Exception as error:
        return False, f"http_failed:{type(error).__name__}"


def create_range_notification(
    config: AppConfig,
    snapshot: RangeSnapshot,
    previous_state: str | None,
) -> NotificationEvent | None:
    if snapshot.range_state not in ACTIONABLE_RANGE_STATES:
        return None
    if previous_state == snapshot.range_state:
        return None

    event_timestamp = snapshot.snapshot_timestamp
    event_dt = _parse_timestamp(event_timestamp)
    cooldown = timedelta(minutes=config.realtime_notification_cooldown_minutes)
    since_timestamp = (event_dt - cooldown).isoformat(timespec="seconds")
    if recent_notification_exists(
        config.database_path,
        snapshot.ticker,
        "range_state_change",
        snapshot.range_state,
        snapshot.model_version,
        since_timestamp,
    ):
        return None

    cooldown_until = (event_dt + cooldown).isoformat(timespec="seconds")
    bucket = int(event_dt.timestamp() // max(int(cooldown.total_seconds()), 1))
    dedupe_key = (
        f"{snapshot.ticker}|range_state_change|{snapshot.range_state}|"
        f"{snapshot.model_version}|{bucket}"
    )
    event = NotificationEvent(
        ticker=snapshot.ticker,
        event_timestamp=event_timestamp,
        event_type="range_state_change",
        asset_type=snapshot.asset_type,
        severity=_severity(snapshot.range_state),
        previous_state=previous_state,
        current_state=snapshot.range_state,
        trigger_price=snapshot.current_price,
        range_level=_range_level(snapshot),
        reason_codes=snapshot.reason_codes,
        status="pending",
        cooldown_until=cooldown_until,
        dedupe_key=dedupe_key,
        model_version=snapshot.model_version,
        source="range_monitor",
        as_of_date=date.today().isoformat(),
        effective_date=event_timestamp,
    )
    upsert_notification_event(config.database_path, event)
    return event


def deliver_notifications(
    config: AppConfig,
    channel: str = "console",
) -> NotificationDeliveryResult:
    if channel not in {"console", "dashboard", "codex_scheduler", "file", "webhook"}:
        raise ValueError(f"Unsupported notification channel: {channel}")

    events = tuple(list_notification_events(config.database_path, status="pending"))
    now = datetime.now().isoformat(timespec="seconds")
    warnings: list[str] = []
    outbox_paths: tuple[Path, ...] = ()
    failed_count = 0

    if channel == "file":
        try:
            outbox_paths = _write_file_outbox(config, events, now)
        except Exception as error:
            failed_count = len(events)
            warnings.append(f"file_delivery_failed:{type(error).__name__}")

    if channel == "webhook":
        ok, detail = _post_webhook(events)
        if not ok:
            failed_count = len(events)
            warnings.append(detail)

    for event in events:
        status = "failed" if failed_count else "delivered"
        details = _delivery_details(event)
        if channel == "file" and outbox_paths:
            details = f"{details}; outbox={outbox_paths[0].name},{outbox_paths[1].name}"
        if channel == "webhook" and warnings:
            details = f"{details}; {warnings[0]}"
        delivery = NotificationDelivery(
            notification_event_id=event.notification_event_id,
            channel=channel,
            delivery_timestamp=now,
            status=status,
            details=details,
            as_of_date=date.today().isoformat(),
            effective_date=now,
        )
        upsert_notification_delivery(config.database_path, delivery)
        if status == "delivered":
            mark_notification_event_delivered(
                config.database_path,
                event.notification_event_id,
            )
        else:
            mark_notification_event_status(
                config.database_path,
                event.notification_event_id,
                "delivery_failed",
            )
    return NotificationDeliveryResult(
        delivered_count=0 if failed_count else len(events),
        events=events,
        failed_count=failed_count,
        warnings=tuple(warnings),
        outbox_paths=outbox_paths,
    )


def test_notification_channel(
    config: AppConfig,
    channel: str,
) -> NotificationChannelTestResult:
    if channel not in {"console", "file", "webhook"}:
        raise ValueError(f"Unsupported notification test channel: {channel}")
    now = datetime.now().isoformat(timespec="seconds")
    test_event = NotificationEventStatus(
        notification_event_id=0,
        ticker="TEST",
        event_timestamp=now,
        event_type="channel_test",
        asset_type="system",
        severity="low",
        previous_state=None,
        current_state="test",
        trigger_price=None,
        range_level=None,
        reason_codes="channel_test",
        status="pending",
        cooldown_until=None,
        model_version="range_monitor_mvp_v1",
    )
    if channel == "console":
        return NotificationChannelTestResult(
            channel=channel,
            status="ok",
            details="console channel available",
        )
    if channel == "file":
        paths = _write_file_outbox(config, (test_event,), now, prefix="test-notification")
        return NotificationChannelTestResult(
            channel=channel,
            status="ok",
            outbox_paths=paths,
            details="file outbox write succeeded",
        )
    ok, detail = _post_webhook((test_event,))
    return NotificationChannelTestResult(
        channel=channel,
        status="ok" if ok else "warning",
        warnings=() if ok else (detail,),
        details="webhook test completed" if ok else detail,
    )


def build_notification_delivery_report_text(config: AppConfig) -> str:
    pending_events = tuple(list_notification_events(config.database_path, status="pending"))
    delivery_failed_events = tuple(
        list_notification_events(config.database_path, status="delivery_failed")
    )
    delivered_count = notification_delivery_count(
        config.database_path,
        status="delivered",
    )
    failed_count = notification_delivery_count(
        config.database_path,
        status="failed",
    )
    recent_deliveries = tuple(list_notification_deliveries(config.database_path, limit=5))
    latest_outbox_files: list[Path] = []
    if config.notification_outbox_dir.exists():
        latest_outbox_files = sorted(
            (path for path in config.notification_outbox_dir.rglob("*") if path.is_file()),
            key=lambda path: path.stat().st_mtime,
            reverse=True,
        )[:5]

    retry_recommendations: list[str] = []
    if pending_events:
        retry_recommendations.append(
            "python -m target_opportunity_monitor drain-pending-notifications --channel file"
        )
    if delivery_failed_events:
        retry_recommendations.append(
            "rerun intraday-cycle --source auto --drain-first --deliver --channel file"
        )
    if failed_count:
        retry_recommendations.append("inspect webhook/file delivery warnings")
    if not retry_recommendations:
        retry_recommendations.append("none")

    lines = [
        "Notification delivery report",
        f"Pending notification events: {len(pending_events)}",
        f"Delivery-failed notification events: {len(delivery_failed_events)}",
        f"Delivered delivery rows: {delivered_count}",
        f"Failed delivery rows: {failed_count}",
        "Latest outbox files: "
        + (
            ", ".join(str(path) for path in latest_outbox_files)
            if latest_outbox_files
            else "none"
        ),
        "Retry recommendations: " + "; ".join(retry_recommendations),
        "",
        "Recent deliveries:",
    ]
    if recent_deliveries:
        lines.extend(
            (
                f"{delivery.delivery_timestamp} | {delivery.channel} | "
                f"{delivery.status} | {delivery.ticker or ''} | "
                f"{delivery.details or ''}"
            )
            for delivery in recent_deliveries
        )
    else:
        lines.append("none")
    return "\n".join(lines)
