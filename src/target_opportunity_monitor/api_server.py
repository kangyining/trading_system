from __future__ import annotations

from dataclasses import asdict, is_dataclass
from datetime import date, datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import csv
import json
from pathlib import Path
import threading
from typing import Any, Mapping
from urllib.parse import parse_qs, urlparse

from .account import (
    account_context_status,
    account_provider_status,
    apply_account_context_backfill,
    export_account_context_template,
    fetch_account_context,
    normalize_account_export,
    preview_account_context_activation,
    validate_account_context_backfill,
)
from .config import AppConfig
from .dashboard import build_dashboard_data, latest_dashboard_path
from .db import REQUIRED_TABLES, get_database_status
from .fundamental_benchmarks import build_fundamental_benchmark_report
from .foreign_equity_sources import (
    apply_foreign_equity_sources,
    build_foreign_equity_source_apply_text,
    build_foreign_equity_source_status_text,
    export_foreign_equity_source_templates,
    validate_foreign_equity_sources,
)
from .intraday_health import (
    build_intraday_health_text,
    build_notification_outbox_status_text,
    intraday_health,
)
from .manual_ops import (
    build_manual_ops_status_text,
    manual_ops_status,
    run_manual_ops_cycle,
)
from .missing_tickers import (
    apply_missing_ticker_onboarding,
    build_missing_ticker_plan_text,
    hydrate_missing_ticker,
    missing_ticker_status,
    resolve_missing_tickers,
)
from .news_catalyst_sources import (
    PROVIDER_NATIVE_BACKFILL_EXPORT_FILE,
    PROVIDER_NATIVE_EXPORT_SOURCES,
    SOURCE_EXPORT_HEADERS,
    apply_news_catalyst_provider_backfill,
    build_news_catalyst_provider_backfill_apply_text,
    build_news_catalyst_provider_backfill_diagnostics_text,
    build_news_catalyst_provider_backfill_status_text,
    build_news_catalyst_provider_backfill_validation_text,
    build_news_catalyst_provider_upgrade_status_text,
    export_news_catalyst_provider_backfill,
    news_catalyst_provider_backfill_diagnostics,
    news_catalyst_provider_backfill_apply_status,
    provider_native_backfill_dir,
    preview_news_catalyst_provider_upgrade,
    validate_news_catalyst_provider_backfill,
)
from .notifications import build_notification_delivery_report_text, deliver_notifications
from .options import (
    OPTIONS_POSITION_HEADERS,
    apply_options_chain_coverage_backfill,
    build_option_chain_status_text,
    build_options_lifecycle_status_text,
    build_options_position_status_text,
    build_options_status_text,
    export_options_chain_missing_template,
    option_chain_availability_statuses,
    option_chain_coverage_plan,
    option_provider_status,
    validate_option_chain_non_actionable_decisions,
    validate_options_chain_backfill,
)
from .pipeline import run_intraday_cycle
from .portfolio import CASH_HEADERS, POSITION_HEADERS
from .readiness import _readiness_for_ticker
from .reporting import latest_csv_report_path, latest_report_path
from .research_recommendations import (
    bulk_set_research_recommendation_status,
    promote_research_recommendation,
    research_recommendation_triage,
    set_research_recommendation_status,
)
from .research_preparation import (
    PREPARATION_ACTIONS,
    research_preparation_status,
    run_research_preparation,
)
from .research_tickers import (
    apply_research_ticker,
    build_etf_strategy_review_text,
    build_research_ticker_status_text,
    etf_strategy_review,
    refresh_research_ticker,
    research_ticker_plan,
    research_ticker_status,
)
from .signal_coverage import (
    build_phase_coverage_payload,
    build_signal_coverage_payload,
)
from .scheduler import (
    audit_scheduler,
    build_scheduler_audit_text,
    build_scheduler_automation_status_text,
    build_scheduler_repair_plan_text,
)
from .short_interest import (
    SHORT_INTEREST_MISSING_PROVIDER_TEMPLATE,
    SHORT_INTEREST_SOURCE_EXPORT_HEADERS,
    apply_short_interest_provider_backfill,
    build_short_interest_backfill_validation_text,
    build_short_interest_missing_coverage_plan_text,
    build_short_interest_provider_diagnostics_text,
    build_short_interest_provider_status_text,
    build_short_interest_source_status_text,
    export_short_interest_missing_provider_template,
    preview_short_interest_import,
    short_interest_missing_coverage_plan,
    short_interest_source_exports_dir,
    validate_short_interest_backfill,
)
from .storage import (
    Asset,
    AssetChangeEvent,
    count_rows_by_table,
    insert_asset_change_event,
    latest_asset,
    latest_intraday_gap_timestamp,
    latest_notification_delivery_timestamp,
    latest_pipeline_run,
    latest_price_date,
    latest_quote_timestamp,
    latest_range_snapshot_timestamp,
    latest_research_recommendation_date,
    list_assets,
    list_notification_deliveries,
    list_notification_events,
    list_research_recommendation_candidates,
    normalize_asset_role,
    normalize_ticker,
    notification_delivery_count,
    pending_notification_count,
    range_statuses,
    set_asset_active_flag,
    upsert_asset,
)
from .tom_loop import (
    TomLoopActionResult,
    build_tom_loop_health_text,
    build_tom_loop_status_text,
    tom_loop_health,
    tom_loop_once,
    tom_loop_start,
    tom_loop_status,
    tom_loop_stop,
)
from .watchlist import set_watchlist_active, upsert_watchlist_asset


API_ENDPOINTS = (
    "GET /api/health",
    "GET /api/status",
    "GET /api/dashboard-data",
    "GET /api/signals/status",
    "GET /api/coverage/status",
    "GET /api/assets",
    "GET /api/assets/status",
    "POST /api/assets/add",
    "POST /api/assets/deactivate",
    "POST /api/assets/reactivate",
    "POST /api/assets/remove",
    "GET /api/research/recommendations",
    "GET /api/research/recommendations/triage",
    "GET /api/research/preparation/status",
    "POST /api/research/preparation/run",
    "POST /api/research/recommendations/bulk-status",
    "POST /api/research/recommendations/{id}/status",
    "POST /api/research/recommendations/{id}/promote",
    "POST /api/research/ticker-plan",
    "POST /api/research/apply-ticker",
    "POST /api/research/refresh-ticker",
    "GET /api/research/ticker-status",
    "GET /api/research/etf-strategy-review",
    "GET /api/research/fundamental-benchmark-report",
    "GET /api/research/foreign-equity-source-status",
    "POST /api/research/foreign-equity-source-template",
    "POST /api/research/foreign-equity-source-apply",
    "POST /api/ops/intraday-cycle",
    "GET /api/ops/intraday-status",
    "GET /api/ops/intraday-health",
    "POST /api/ops/manual-cycle",
    "GET /api/scheduler/status",
    "GET /api/scheduler/audit",
    "POST /api/notifications/drain",
    "GET /api/notifications/status",
    "GET /api/notifications/delivery-report",
    "GET /api/notifications/outbox-status",
    "GET /api/options/status",
    "GET /api/provider/status",
    "GET /api/account/context-status",
    "GET /api/account/provider-status",
    "POST /api/account/export-template",
    "GET /api/account/validate-backfill",
    "GET /api/account/preview-activation",
    "POST /api/account/apply-backfill",
    "POST /api/account/normalize-export",
    "POST /api/account/fetch-context",
    "POST /api/account/append-row",
    "GET /api/missing-tickers/status",
    "POST /api/missing-tickers/resolve",
    "POST /api/missing-tickers/apply",
    "POST /api/missing-tickers/hydrate",
    "GET /api/backfills/options/status",
    "POST /api/backfills/options/export-template",
    "GET /api/backfills/options/validate",
    "POST /api/backfills/options/apply",
    "GET /api/backfills/news/status",
    "POST /api/backfills/news/export-template",
    "GET /api/backfills/news/validate",
    "POST /api/backfills/news/append-row",
    "POST /api/backfills/news/apply",
    "GET /api/backfills/short-interest/status",
    "POST /api/backfills/short-interest/export-template",
    "GET /api/backfills/short-interest/validate",
    "POST /api/backfills/short-interest/append-row",
    "POST /api/backfills/short-interest/apply",
    "GET /api/loop/status",
    "GET /api/loop/health",
    "POST /api/loop/start",
    "POST /api/loop/stop",
    "POST /api/loop/run-once",
)
LOCAL_HOSTS = {"127.0.0.1", "localhost", "::1"}
_LOOP_THREAD: threading.Thread | None = None


def _to_jsonable(value: object) -> object:
    if is_dataclass(value):
        return _to_jsonable(asdict(value))
    if isinstance(value, dict):
        return {str(key): _to_jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_to_jsonable(item) for item in value]
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if hasattr(value, "__dict__"):
        return {
            key: _to_jsonable(item)
            for key, item in vars(value).items()
            if not key.startswith("_")
        }
    return value


def _ok(data: object | None = None, warnings: tuple[str, ...] = ()) -> dict[str, object]:
    payload: dict[str, object] = {"ok": True}
    if data is not None:
        payload["data"] = _to_jsonable(data)
    if warnings:
        payload["warnings"] = list(warnings)
    return payload


def _error(
    error_code: str,
    message: str,
    warnings: tuple[str, ...] = (),
) -> dict[str, object]:
    payload: dict[str, object] = {
        "ok": False,
        "error_code": error_code,
        "message": message,
    }
    if warnings:
        payload["warnings"] = list(warnings)
    return payload


def _parse_json_payload(body: object | None) -> tuple[dict[str, object], str | None]:
    if body is None or body == b"" or body == "":
        return {}, None
    if isinstance(body, dict):
        return body, None
    if isinstance(body, bytes):
        raw = body.decode("utf-8")
    else:
        raw = str(body)
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return {}, "malformed_json"
    if not isinstance(parsed, dict):
        return {}, "json_body_must_be_object"
    return parsed, None


def _header_value(headers: Mapping[str, str] | None, name: str) -> str | None:
    if not headers:
        return None
    wanted = name.lower()
    for key, value in headers.items():
        if str(key).lower() == wanted:
            return str(value)
    return None


def _mutation_confirmed(
    config: AppConfig,
    headers: Mapping[str, str] | None,
    body: Mapping[str, object],
) -> bool:
    if not config.api_require_mutation_confirmation:
        return True
    header_value = _header_value(headers, "X-TOM-Confirm")
    if header_value and header_value.strip().lower() in {"1", "true", "yes", "confirm"}:
        return True
    return bool(body.get("confirm") is True)


def _require_confirmation(
    config: AppConfig,
    headers: Mapping[str, str] | None,
    body: Mapping[str, object],
) -> tuple[bool, tuple[int, dict[str, object]] | None]:
    if _mutation_confirmed(config, headers, body):
        return True, None
    return False, (
        403,
        _error(
            "confirmation_required",
            'Mutating API calls require JSON {"confirm": true} or X-TOM-Confirm: true.',
        ),
    )


def _loop_body_args(body: Mapping[str, object]) -> dict[str, object]:
    mode = str(body.get("mode") or "auto")
    channel = str(body.get("channel") or "file")
    interval_value = body.get("interval_seconds")
    max_cycles_value = body.get("max_cycles")
    return {
        "mode": mode,
        "deliver": bool(body.get("deliver", True)),
        "channel": channel,
        "interval_seconds": int(interval_value) if interval_value not in {None, ""} else None,
        "max_cycles": int(max_cycles_value) if max_cycles_value not in {None, ""} else None,
    }


def _start_loop_thread(config: AppConfig, body: Mapping[str, object]) -> TomLoopActionResult:
    global _LOOP_THREAD
    snapshot = tom_loop_status(config)
    if snapshot.active:
        raise RuntimeError(f"TOM loop already running with pid {snapshot.pid or 'unknown'}.")
    if _LOOP_THREAD is not None and _LOOP_THREAD.is_alive():
        raise RuntimeError("TOM loop API thread is already running.")

    loop_args = _loop_body_args(body)

    def _runner() -> None:
        try:
            tom_loop_start(
                config,
                mode=str(loop_args["mode"]),
                deliver=bool(loop_args["deliver"]),
                channel=str(loop_args["channel"]),
                interval_seconds=loop_args["interval_seconds"],
                max_cycles=loop_args["max_cycles"],
            )
        except Exception:
            # The loop state file records cycle-level failures. API callers can
            # inspect /api/loop/status instead of relying on this daemon thread.
            return

    _LOOP_THREAD = threading.Thread(target=_runner, name="tom-loop", daemon=True)
    _LOOP_THREAD.start()
    return TomLoopActionResult(
        status="started",
        message="TOM loop start requested in the local API process.",
        snapshot=tom_loop_status(config),
    )


def _normalize_ticker_body(body: Mapping[str, object]) -> str | None:
    ticker = body.get("ticker")
    if ticker is None:
        return None
    cleaned = str(ticker).strip().upper()
    return cleaned or None


def _normalize_ticker_query(query: Mapping[str, list[str]]) -> str | None:
    ticker = (query.get("ticker") or [None])[0]
    if ticker is None:
        return None
    cleaned = str(ticker).strip().upper()
    return cleaned or None


def _research_ticker_kwargs(body: Mapping[str, object]) -> dict[str, object]:
    keys = ("name", "sector", "industry", "cik", "exchange", "currency", "country", "asset_type")
    kwargs: dict[str, object] = {
        key: body.get(key)
        for key in keys
        if body.get(key) not in {None, ""}
    }
    kwargs["refresh_metadata"] = bool(body.get("refresh_metadata", False))
    return kwargs


def _recommendation_id_from_path(parts: list[str]) -> int | None:
    if len(parts) != 5:
        return None
    try:
        return int(parts[3])
    except ValueError:
        return None


def _safe_count(config: AppConfig, table_name: str, existing_tables: set[str]) -> int | None:
    if table_name not in existing_tables:
        return None
    return count_rows_by_table(config.database_path, table_name)


def _optional_text(body: Mapping[str, object], key: str) -> str | None:
    value = body.get(key)
    if value is None:
        return None
    cleaned = str(value).strip()
    return cleaned or None


def _today_and_now() -> tuple[str, str]:
    return date.today().isoformat(), datetime.now().isoformat(timespec="seconds")


def _upsert_cik(config: AppConfig, ticker: str, cik: str | None) -> None:
    if not cik:
        return
    path = config.cik_map_path
    path.parent.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, str]] = []
    if path.exists():
        with path.open("r", encoding="utf-8-sig", newline="") as input_file:
            reader = csv.DictReader(input_file)
            rows = [dict(row) for row in reader]
    normalized = normalize_ticker(ticker)
    updated = False
    for row in rows:
        if normalize_ticker(row.get("ticker", "")) == normalized:
            row["cik"] = cik
            updated = True
            break
    if not updated:
        rows.append({"ticker": normalized, "cik": cik})
    with path.open("w", encoding="utf-8", newline="") as output_file:
        writer = csv.DictWriter(output_file, fieldnames=("ticker", "cik"))
        writer.writeheader()
        writer.writerows(rows)


def _record_asset_change(
    config: AppConfig,
    ticker: str,
    event_type: str,
    previous_active_flag: int | None,
    new_active_flag: int | None,
    reason: str | None = None,
    details: str | None = None,
) -> None:
    as_of_date, timestamp = _today_and_now()
    insert_asset_change_event(
        config.database_path,
        AssetChangeEvent(
            event_timestamp=timestamp,
            ticker=normalize_ticker(ticker),
            event_type=event_type,
            previous_active_flag=previous_active_flag,
            new_active_flag=new_active_flag,
            reason=reason,
            details=details,
            as_of_date=as_of_date,
            effective_date=timestamp,
        ),
    )


def _asset_from_body(body: Mapping[str, object]) -> Asset | None:
    ticker = _normalize_ticker_body(body)
    if not ticker:
        return None
    as_of_date, timestamp = _today_and_now()
    asset_role = normalize_asset_role(str(body.get("asset_role") or "scoreable"))
    return Asset(
        ticker=ticker,
        name=_optional_text(body, "name"),
        asset_type=_optional_text(body, "asset_type") or "equity",
        exchange=_optional_text(body, "exchange"),
        currency=_optional_text(body, "currency") or "USD",
        sector=_optional_text(body, "sector"),
        industry=_optional_text(body, "industry"),
        country=_optional_text(body, "country") or "US",
        active_flag=0 if asset_role == "inactive" else 1,
        asset_role=asset_role,
        source="api_asset_management",
        as_of_date=as_of_date,
        effective_date=timestamp,
    )


def _asset_status_payload(config: AppConfig, ticker: str) -> dict[str, object] | None:
    normalized = normalize_ticker(ticker)
    asset = latest_asset(config.database_path, normalized)
    if asset is None:
        return None
    readiness = _readiness_for_ticker(config, normalized)
    ranges = range_statuses(config.database_path, ticker=normalized)
    latest_range = ranges[0] if ranges else None
    return {
        "ticker": normalized,
        "asset": asset,
        "readiness": readiness,
        "latest_range": latest_range,
        "range_count": len(ranges),
    }


def _set_asset_active(
    config: AppConfig,
    ticker: str,
    active: bool,
    event_type: str,
    reason: str | None = None,
) -> dict[str, object] | None:
    normalized = normalize_ticker(ticker)
    previous = latest_asset(config.database_path, normalized)
    if previous is None:
        return None
    set_watchlist_active(config.watchlist_path, normalized, active)
    as_of_date, timestamp = _today_and_now()
    updated = set_asset_active_flag(
        config.database_path,
        normalized,
        1 if active else 0,
        source="api_asset_management",
        as_of_date=as_of_date,
        effective_date=timestamp,
    )
    _record_asset_change(
        config,
        normalized,
        event_type,
        previous.active_flag,
        updated.active_flag if updated else (1 if active else 0),
        reason,
    )
    return {"previous_asset": previous, "asset": updated}


def _append_csv_row(path: Path, headers: tuple[str, ...], row: Mapping[str, object]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    file_exists = path.exists() and path.read_text(encoding="utf-8-sig").strip()
    with path.open("a", encoding="utf-8", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=headers)
        if not file_exists:
            writer.writeheader()
        writer.writerow({header: str(row.get(header) or "") for header in headers})
    return path


def _append_account_context_row(
    config: AppConfig,
    row_type: str,
    row: Mapping[str, object],
) -> dict[str, object]:
    kind = row_type.strip().lower()
    if kind in {"portfolio_position", "position"}:
        path = config.account_source_exports_dir / "ui_portfolio_positions_backfill.csv"
        headers = POSITION_HEADERS
        normalized_kind = "portfolio_position"
    elif kind in {"portfolio_cash", "cash"}:
        path = config.account_source_exports_dir / "ui_portfolio_cash_backfill.csv"
        headers = CASH_HEADERS
        normalized_kind = "portfolio_cash"
    elif kind in {"option_position", "options_position", "option"}:
        path = config.account_source_exports_dir / "ui_options_positions_backfill.csv"
        headers = OPTIONS_POSITION_HEADERS
        normalized_kind = "option_position"
    else:
        raise ValueError(f"Unsupported account row type: {row_type}")
    written_path = _append_csv_row(path, headers, row)
    return {
        "row_type": normalized_kind,
        "path": written_path,
        "headers": headers,
        "validation": validate_account_context_backfill(config),
        "preview": preview_account_context_activation(config),
        "option_position_diagnostics": account_context_status(
            config
        ).option_position_diagnostics,
    }


def _account_context_payload(config: AppConfig) -> dict[str, object]:
    status = account_context_status(config)
    return {
        "status": status,
        "validation": status.validation,
        "preview": status.preview,
        "option_position_diagnostics": status.option_position_diagnostics,
    }


def _options_backfill_payload(config: AppConfig) -> dict[str, object]:
    return {
        "plan": option_chain_coverage_plan(config),
        "availability_statuses": option_chain_availability_statuses(config),
        "validation": validate_options_chain_backfill(config),
        "non_actionable": validate_option_chain_non_actionable_decisions(config),
        "provider": option_provider_status(config, check_connectivity=False),
        "option_chain_status_text": build_option_chain_status_text(config),
        "options_status_text": build_options_status_text(config),
        "position_status_text": build_options_position_status_text(config),
        "lifecycle_status_text": build_options_lifecycle_status_text(config),
    }


def _news_backfill_payload(config: AppConfig) -> dict[str, object]:
    append_target_path = provider_native_backfill_dir(config) / PROVIDER_NATIVE_BACKFILL_EXPORT_FILE
    return {
        "validation": validate_news_catalyst_provider_backfill(config),
        "preview": preview_news_catalyst_provider_upgrade(config),
        "apply_status": news_catalyst_provider_backfill_apply_status(config),
        "diagnostics": news_catalyst_provider_backfill_diagnostics(config),
        "accepted_sources": tuple(sorted(PROVIDER_NATIVE_EXPORT_SOURCES)),
        "source_headers": SOURCE_EXPORT_HEADERS,
        "append_target_path": append_target_path,
        "provider_upgrade_status_text": build_news_catalyst_provider_upgrade_status_text(config),
        "backfill_status_text": build_news_catalyst_provider_backfill_status_text(config),
        "diagnostics_text": build_news_catalyst_provider_backfill_diagnostics_text(config),
        "validation_text": build_news_catalyst_provider_backfill_validation_text(config),
    }


def _append_news_catalyst_provider_native_row(
    config: AppConfig,
    row: Mapping[str, object],
) -> dict[str, object]:
    path = provider_native_backfill_dir(config) / PROVIDER_NATIVE_BACKFILL_EXPORT_FILE
    written_path = _append_csv_row(path, SOURCE_EXPORT_HEADERS, row)
    return {
        "path": written_path,
        "headers": SOURCE_EXPORT_HEADERS,
        "status": _news_backfill_payload(config),
    }


def _short_interest_backfill_payload(config: AppConfig) -> dict[str, object]:
    return {
        "validation": validate_short_interest_backfill(config),
        "preview": preview_short_interest_import(config),
        "missing_plan": short_interest_missing_coverage_plan(config),
        "provider_status_text": build_short_interest_provider_status_text(config),
        "source_status_text": build_short_interest_source_status_text(config),
        "missing_plan_text": build_short_interest_missing_coverage_plan_text(config),
        "provider_diagnostics_text": build_short_interest_provider_diagnostics_text(config),
        "validation_text": build_short_interest_backfill_validation_text(config),
    }


def _append_short_interest_missing_provider_row(
    config: AppConfig,
    row: Mapping[str, object],
) -> dict[str, object]:
    path = short_interest_source_exports_dir(config) / SHORT_INTEREST_MISSING_PROVIDER_TEMPLATE
    written_path = _append_csv_row(path, SHORT_INTEREST_SOURCE_EXPORT_HEADERS, row)
    return {
        "path": written_path,
        "headers": SHORT_INTEREST_SOURCE_EXPORT_HEADERS,
        "status": _short_interest_backfill_payload(config),
    }


def _intraday_status_payload(config: AppConfig) -> dict[str, object]:
    health = intraday_health(config)
    scheduler_audit = audit_scheduler(config)
    latest_failed = list_notification_deliveries(
        config.database_path,
        status="failed",
        limit=1,
    )
    return {
        "health": health,
        "scheduler": scheduler_audit,
        "manual_ops": manual_ops_status(config),
        "loop": tom_loop_status(config),
        "latest_intraday_cycle": latest_pipeline_run(
            config.database_path,
            run_type="intraday_cycle",
        ),
        "latest_intraday_probe": latest_pipeline_run(
            config.database_path,
            run_type="intraday_probe",
        ),
        "latest_quote_timestamp": latest_quote_timestamp(config.database_path),
        "latest_intraday_gap_timestamp": latest_intraday_gap_timestamp(config.database_path),
        "latest_range_snapshot_timestamp": latest_range_snapshot_timestamp(config.database_path),
        "pending_notifications": pending_notification_count(config.database_path),
        "delivered_notification_deliveries": notification_delivery_count(
            config.database_path,
            status="delivered",
        ),
        "failed_notification_deliveries": notification_delivery_count(
            config.database_path,
            status="failed",
        ),
        "latest_successful_delivery": latest_notification_delivery_timestamp(
            config.database_path,
            status="delivered",
        ),
        "latest_failed_delivery": latest_failed[0] if latest_failed else None,
        "status_text": build_intraday_health_text(config),
        "manual_ops_status_text": build_manual_ops_status_text(config),
    }


def _scheduler_status_payload(config: AppConfig) -> dict[str, object]:
    database_status = get_database_status(config.database_path)
    existing_tables = set(database_status.existing_tables)
    has_pipeline = config.database_path.exists() and "pipeline_runs" in existing_tables
    has_notifications = (
        config.database_path.exists() and "notification_events" in existing_tables
    )
    has_deliveries = (
        config.database_path.exists() and "notification_deliveries" in existing_tables
    )
    latest_report = latest_report_path(config.reports_dir)
    latest_csv = latest_csv_report_path(config.reports_dir)
    latest_dashboard = latest_dashboard_path(config.project_root)
    audit = audit_scheduler(config)
    heartbeat_job = next(
        (job for job in audit.jobs if job.job_key == "intraday_heartbeat"),
        None,
    )
    return {
        "health": intraday_health(config),
        "audit": audit,
        "heartbeat_job": heartbeat_job,
        "latest_intraday_cycle": latest_pipeline_run(
            config.database_path,
            run_type="intraday_cycle",
        )
        if has_pipeline
        else None,
        "latest_daily_refresh": latest_pipeline_run(
            config.database_path,
            run_type="daily_refresh",
        )
        if has_pipeline
        else None,
        "latest_quote_timestamp": latest_quote_timestamp(config.database_path),
        "latest_range_snapshot_timestamp": latest_range_snapshot_timestamp(config.database_path),
        "pending_notifications": pending_notification_count(config.database_path)
        if has_notifications
        else 0,
        "failed_notification_deliveries": notification_delivery_count(
            config.database_path,
            status="failed",
        )
        if has_deliveries
        else 0,
        "latest_successful_delivery": latest_notification_delivery_timestamp(
            config.database_path,
            status="delivered",
        )
        if has_deliveries
        else None,
        "latest_report": latest_report,
        "latest_csv_report": latest_csv,
        "latest_dashboard": latest_dashboard,
        "audit_text": build_scheduler_audit_text(config),
        "repair_plan_text": build_scheduler_repair_plan_text(config),
        "automation_status_text": build_scheduler_automation_status_text(config),
    }


def api_cors_headers(config: AppConfig, origin: str | None) -> dict[str, str]:
    if origin and origin in config.api_allowed_origins:
        return {
            "Access-Control-Allow-Origin": origin,
            "Vary": "Origin",
            "Access-Control-Allow-Headers": "Content-Type, X-TOM-Confirm",
            "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
        }
    return {
        "Access-Control-Allow-Origin": "null",
        "Vary": "Origin",
        "Access-Control-Allow-Headers": "Content-Type, X-TOM-Confirm",
        "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
    }


def api_status(config: AppConfig) -> dict[str, object]:
    return {
        "host": config.api_host,
        "port": config.api_port,
        "allowed_origins": config.api_allowed_origins,
        "require_mutation_confirmation": config.api_require_mutation_confirmation,
        "local_only": config.api_host in LOCAL_HOSTS,
        "endpoints": API_ENDPOINTS,
    }


def _health_payload(config: AppConfig) -> dict[str, object]:
    database_status = get_database_status(config.database_path)
    missing_tables = tuple(
        table_name
        for table_name in REQUIRED_TABLES
        if table_name not in database_status.existing_tables
    )
    return {
        "service": "target_opportunity_monitor_api",
        "database_path": config.database_path,
        "database_exists": config.database_path.exists(),
        "required_tables_present": not missing_tables,
        "existing_table_count": len(database_status.existing_tables),
        "missing_tables": missing_tables,
        "api": api_status(config),
    }


def _status_payload(config: AppConfig) -> dict[str, object]:
    database_status = get_database_status(config.database_path)
    existing_tables = set(database_status.existing_tables)
    latest_pipeline = (
        latest_pipeline_run(config.database_path) if "pipeline_runs" in existing_tables else None
    )
    latest_intraday = (
        latest_pipeline_run(config.database_path, run_type="intraday_cycle")
        if "pipeline_runs" in existing_tables
        else None
    )
    pending_notifications = (
        len(list_notification_events(config.database_path, status="pending"))
        if "notification_events" in existing_tables
        else None
    )
    loop_snapshot = tom_loop_status(config)
    return {
        "database": _health_payload(config),
        "rows": {
            "assets": _safe_count(config, "assets", existing_tables),
            "scores": _safe_count(config, "scores", existing_tables),
            "alerts": _safe_count(config, "alerts", existing_tables),
            "range_snapshots": _safe_count(config, "range_snapshots", existing_tables),
            "notification_events": _safe_count(config, "notification_events", existing_tables),
            "research_recommendation_candidates": _safe_count(
                config, "research_recommendation_candidates", existing_tables
            ),
            "option_chain_snapshots": _safe_count(config, "option_chain_snapshots", existing_tables),
            "option_income_reviews": _safe_count(config, "option_income_reviews", existing_tables),
        },
        "latest": {
            "price_date": latest_price_date(config.database_path)
            if "prices" in existing_tables
            else None,
            "quote_timestamp": latest_quote_timestamp(config.database_path)
            if "quote_snapshots" in existing_tables
            else None,
            "range_snapshot_timestamp": latest_range_snapshot_timestamp(config.database_path)
            if "range_snapshots" in existing_tables
            else None,
            "research_recommendation_date": latest_research_recommendation_date(
                config.database_path
            )
            if "research_recommendation_candidates" in existing_tables
            else None,
            "pipeline_run": latest_pipeline,
            "intraday_cycle": latest_intraday,
        },
        "pending_notifications": pending_notifications,
        "loop": loop_snapshot,
    }


def _recommendations_payload(config: AppConfig, query: Mapping[str, list[str]]) -> dict[str, object]:
    status = (query.get("status") or [None])[0]
    ticker = (query.get("ticker") or [None])[0]
    candidates = list_research_recommendation_candidates(
        config.database_path,
        status=status,
        ticker=ticker,
    )
    return {
        "count": len(candidates),
        "candidates": candidates,
    }


def _dispatch_get(config: AppConfig, path: str, query: Mapping[str, list[str]]) -> tuple[int, dict[str, object]]:
    if path == "/api/health":
        return 200, _ok(_health_payload(config))
    if path == "/api/status":
        return 200, _ok(_status_payload(config))
    if path == "/api/dashboard-data":
        return 200, _ok(build_dashboard_data(config))
    if path == "/api/signals/status":
        return 200, _ok(build_signal_coverage_payload(config))
    if path == "/api/coverage/status":
        return 200, _ok(build_phase_coverage_payload(config))
    if path == "/api/assets":
        return 200, _ok({"count": len(list_assets(config.database_path)), "assets": list_assets(config.database_path)})
    if path == "/api/assets/status":
        ticker = _normalize_ticker_query(query)
        if not ticker:
            return 400, _error("missing_ticker", "Query string must include ticker.")
        payload = _asset_status_payload(config, ticker)
        if payload is None:
            return 404, _error("asset_not_found", f"Asset was not found: {ticker}")
        return 200, _ok(payload)
    if path == "/api/research/recommendations/triage":
        return 200, _ok({"triage": research_recommendation_triage(config)})
    if path == "/api/research/preparation/status":
        source = (query.get("source") or [None])[0]
        tickers = tuple(query.get("ticker") or query.get("tickers") or ())
        return 200, _ok(
            {
                "preparation": research_preparation_status(
                    config,
                    source=source,
                    tickers=tickers,
                )
            }
        )
    if path == "/api/research/recommendations":
        return 200, _ok(_recommendations_payload(config, query))
    if path == "/api/research/ticker-status":
        ticker = _normalize_ticker_query(query)
        if not ticker:
            return 400, _error("missing_ticker", "Query string must include ticker.")
        status = research_ticker_status(config, ticker)
        return 200, _ok(
            {
                "ticker": ticker,
                "status": status,
                "status_text": build_research_ticker_status_text(status),
            }
        )
    if path == "/api/research/etf-strategy-review":
        ticker = _normalize_ticker_query(query)
        if not ticker:
            return 400, _error("missing_ticker", "Query string must include ticker.")
        review = etf_strategy_review(config, ticker)
        return 200, _ok(
            {
                "ticker": ticker,
                "review": review,
                "review_text": build_etf_strategy_review_text(review),
            }
        )
    if path == "/api/research/fundamental-benchmark-report":
        ticker = _normalize_ticker_query(query)
        if not ticker:
            return 400, _error("missing_ticker", "Query string must include ticker.")
        return 200, _ok(
            {
                "ticker": ticker,
                "report_markdown": build_fundamental_benchmark_report(config, ticker=ticker),
            }
        )
    if path == "/api/research/foreign-equity-source-status":
        validation = validate_foreign_equity_sources(config)
        return 200, _ok(
            {
                "validation": validation,
                "status_text": build_foreign_equity_source_status_text(validation),
            },
            validation.warnings,
        )
    if path == "/api/options/status":
        provider = option_provider_status(config, check_connectivity=False)
        return 200, _ok(
            {
                "provider": provider,
                "summary_text": build_options_status_text(config),
            }
        )
    if path == "/api/provider/status":
        return 200, _ok({"options": option_provider_status(config, check_connectivity=False)})
    if path == "/api/account/context-status":
        return 200, _ok(_account_context_payload(config))
    if path == "/api/account/provider-status":
        return 200, _ok({"provider_status": account_provider_status(config, check_connectivity=False)})
    if path == "/api/account/validate-backfill":
        return 200, _ok({"validation": validate_account_context_backfill(config)})
    if path == "/api/account/preview-activation":
        return 200, _ok({"preview": preview_account_context_activation(config)})
    if path == "/api/missing-tickers/status":
        return 200, _ok({"status": missing_ticker_status(config)})
    if path == "/api/backfills/options/status":
        return 200, _ok(_options_backfill_payload(config))
    if path == "/api/backfills/options/validate":
        return 200, _ok({"validation": validate_options_chain_backfill(config)})
    if path == "/api/backfills/news/status":
        return 200, _ok(_news_backfill_payload(config))
    if path == "/api/backfills/news/validate":
        return 200, _ok(
            {
                "validation": validate_news_catalyst_provider_backfill(config),
                "validation_text": build_news_catalyst_provider_backfill_validation_text(config),
            }
        )
    if path == "/api/backfills/short-interest/status":
        return 200, _ok(_short_interest_backfill_payload(config))
    if path == "/api/backfills/short-interest/validate":
        return 200, _ok(
            {
                "validation": validate_short_interest_backfill(config),
                "validation_text": build_short_interest_backfill_validation_text(config),
            }
        )
    if path == "/api/ops/intraday-status":
        return 200, _ok(_intraday_status_payload(config))
    if path == "/api/ops/intraday-health":
        return 200, _ok(
            {
                "health": intraday_health(config),
                "health_text": build_intraday_health_text(config),
            }
        )
    if path == "/api/loop/status":
        return 200, _ok(
            {
                "loop": tom_loop_status(config),
                "status_text": build_tom_loop_status_text(config),
            }
        )
    if path == "/api/loop/health":
        return 200, _ok(
            {
                "loop": tom_loop_health(config),
                "health_text": build_tom_loop_health_text(config),
            }
        )
    if path == "/api/scheduler/status":
        return 200, _ok(_scheduler_status_payload(config))
    if path == "/api/scheduler/audit":
        return 200, _ok(
            {
                "audit": audit_scheduler(config),
                "audit_text": build_scheduler_audit_text(config),
                "repair_plan_text": build_scheduler_repair_plan_text(config),
                "automation_status_text": build_scheduler_automation_status_text(config),
            }
        )
    if path == "/api/notifications/status":
        status = (query.get("status") or [None])[0]
        ticker = _normalize_ticker_query(query)
        events = list_notification_events(config.database_path, status=status, ticker=ticker)
        return 200, _ok(
            {
                "count": len(events),
                "events": events,
                "pending_count": pending_notification_count(config.database_path),
                "delivered_delivery_count": notification_delivery_count(
                    config.database_path,
                    status="delivered",
                ),
                "failed_delivery_count": notification_delivery_count(
                    config.database_path,
                    status="failed",
                ),
                "latest_successful_delivery": latest_notification_delivery_timestamp(
                    config.database_path,
                    status="delivered",
                ),
            }
        )
    if path == "/api/notifications/delivery-report":
        return 200, _ok({"report_text": build_notification_delivery_report_text(config)})
    if path == "/api/notifications/outbox-status":
        return 200, _ok({"status_text": build_notification_outbox_status_text(config)})
    return 404, _error("not_found", f"Unknown API route: {path}")


def _dispatch_post(
    config: AppConfig,
    path: str,
    headers: Mapping[str, str] | None,
    body: dict[str, object],
) -> tuple[int, dict[str, object]]:
    parts = [part for part in path.split("/") if part]
    if path == "/api/assets/add":
        confirmed, error = _require_confirmation(config, headers, body)
        if not confirmed and error is not None:
            return error
        asset = _asset_from_body(body)
        if asset is None:
            return 400, _error("missing_ticker", "Request body must include ticker.")
        previous = latest_asset(config.database_path, asset.ticker)
        upsert_watchlist_asset(config.watchlist_path, asset)
        upsert_asset(config.database_path, asset)
        _upsert_cik(
            config,
            asset.ticker,
            _optional_text(body, "cik") if asset.asset_type == "equity" else None,
        )
        _record_asset_change(
            config,
            asset.ticker,
            "add_or_update",
            previous.active_flag if previous else None,
            asset.active_flag,
            _optional_text(body, "reason"),
            f"asset_type={asset.asset_type};asset_role={asset.asset_role}",
        )
        warnings: list[str] = []
        if asset.asset_type == "equity" and not _optional_text(body, "cik"):
            warnings.append("missing_cik")
        if asset.asset_type == "etf":
            warnings.append("etf_nav_holdings_readiness_needed")
        return 200, _ok(
            {
                "previous_asset": previous,
                "asset": latest_asset(config.database_path, asset.ticker),
            },
            tuple(warnings),
        )

    if path in {"/api/assets/deactivate", "/api/assets/reactivate", "/api/assets/remove"}:
        confirmed, error = _require_confirmation(config, headers, body)
        if not confirmed and error is not None:
            return error
        ticker = _normalize_ticker_body(body)
        if not ticker:
            return 400, _error("missing_ticker", "Request body must include ticker.")
        active = path == "/api/assets/reactivate"
        event_type = {
            "/api/assets/deactivate": "deactivate",
            "/api/assets/reactivate": "reactivate",
            "/api/assets/remove": "soft_remove",
        }[path]
        result = _set_asset_active(
            config,
            ticker,
            active,
            event_type,
            _optional_text(body, "reason"),
        )
        if result is None:
            return 404, _error("asset_not_found", f"Asset was not found: {ticker}")
        return 200, _ok(result)

    if path == "/api/research/recommendations/bulk-status":
        confirmed, error = _require_confirmation(config, headers, body)
        if not confirmed and error is not None:
            return error
        raw_ids = body.get("ids")
        if not isinstance(raw_ids, (list, tuple)):
            return 400, _error("invalid_recommendation_ids", "Request body must include ids.")
        recommendation_ids: list[int] = []
        for item in raw_ids:
            if isinstance(item, bool):
                return 400, _error("invalid_recommendation_ids", "Recommendation ids must be integers.")
            try:
                recommendation_ids.append(int(item))
            except (TypeError, ValueError):
                return 400, _error("invalid_recommendation_ids", "Recommendation ids must be integers.")
        result = bulk_set_research_recommendation_status(
            config,
            tuple(recommendation_ids),
            str(body.get("status") or ""),
            reason=str(body.get("reason") or "api_bulk_status_update"),
        )
        if result.blocked_reason:
            status_code = 404 if result.blocked_reason == "unknown_recommendation_ids" else 400
            payload = _error(
                result.blocked_reason,
                "Research recommendation bulk status update was blocked.",
                result.warnings,
            )
            payload["data"] = _to_jsonable({"result": result})
            return status_code, payload
        return 200, _ok({"result": result})

    if (
        len(parts) == 5
        and parts[0:3] == ["api", "research", "recommendations"]
        and parts[4] == "status"
    ):
        confirmed, error = _require_confirmation(config, headers, body)
        if not confirmed and error is not None:
            return error
        recommendation_id = _recommendation_id_from_path(parts)
        if recommendation_id is None:
            return 400, _error("invalid_recommendation_id", "Recommendation id must be an integer.")
        status_value = str(body.get("status") or "").strip().lower()
        candidate = set_research_recommendation_status(
            config,
            recommendation_id,
            status_value,
            reason=str(body.get("reason") or "api_status_update"),
        )
        if candidate is None:
            return 404, _error(
                "recommendation_not_found_or_invalid_status",
                "Recommendation was not found or the requested status is invalid.",
            )
        return 200, _ok({"candidate": candidate})

    if (
        len(parts) == 5
        and parts[0:3] == ["api", "research", "recommendations"]
        and parts[4] == "promote"
    ):
        confirmed, error = _require_confirmation(config, headers, body)
        if not confirmed and error is not None:
            return error
        recommendation_id = _recommendation_id_from_path(parts)
        if recommendation_id is None:
            return 400, _error("invalid_recommendation_id", "Recommendation id must be an integer.")
        result = promote_research_recommendation(config, recommendation_id, confirm=True)
        status_code = 200 if result.promoted else 409
        payload = _ok({"promotion": result}) if result.promoted else _error(
            result.blocked_reason or "promotion_blocked",
            "Research recommendation promotion was blocked.",
            result.warnings,
        )
        if not result.promoted:
            payload["data"] = _to_jsonable({"promotion": result})
        return status_code, payload

    if path == "/api/research/ticker-plan":
        ticker = _normalize_ticker_body(body)
        if not ticker:
            return 400, _error("missing_ticker", "Request body must include ticker.")
        plan = research_ticker_plan(config, ticker, **_research_ticker_kwargs(body))
        return 200, _ok({"plan": plan})

    if path == "/api/research/apply-ticker":
        confirmed, error = _require_confirmation(config, headers, body)
        if not confirmed and error is not None:
            return error
        ticker = _normalize_ticker_body(body)
        if not ticker:
            return 400, _error("missing_ticker", "Request body must include ticker.")
        result = apply_research_ticker(
            config,
            ticker,
            confirm=True,
            **_research_ticker_kwargs(body),
        )
        if result.blocked_reason:
            return 409, _error(
                result.blocked_reason,
                "Research ticker apply was blocked.",
                result.warnings,
            )
        return 200, _ok({"result": result})

    if path == "/api/research/refresh-ticker":
        confirmed, error = _require_confirmation(config, headers, body)
        if not confirmed and error is not None:
            return error
        ticker = _normalize_ticker_body(body)
        if not ticker:
            return 400, _error("missing_ticker", "Request body must include ticker.")
        result, blockers = refresh_research_ticker(config, ticker)
        if result is None:
            return 409, _error(
                "research_ticker_refresh_blocked",
                "Research ticker refresh was blocked.",
                tuple(blockers),
            )
        status_code = 200 if getattr(result, "status", None) != "error" else 500
        warnings = tuple(blockers)
        return status_code, _ok(
            {
                "result": result,
                "readiness_blockers": blockers,
                "status": research_ticker_status(config, ticker),
            },
            warnings,
        )

    if path == "/api/research/foreign-equity-source-template":
        confirmed, error = _require_confirmation(config, headers, body)
        if not confirmed and error is not None:
            return error
        fundamentals_path, estimates_path, analyst_targets_path = (
            export_foreign_equity_source_templates(config)
        )
        return 200, _ok(
            {
                "fundamentals_path": fundamentals_path,
                "estimates_path": estimates_path,
                "analyst_targets_path": analyst_targets_path,
            }
        )

    if path == "/api/research/foreign-equity-source-apply":
        dry_run = bool(body.get("dry_run", False))
        if not dry_run:
            confirmed, error = _require_confirmation(config, headers, body)
            if not confirmed and error is not None:
                return error
        result = apply_foreign_equity_sources(config, confirm=not dry_run)
        status_code = 200 if result.applied or dry_run else 409
        return status_code, _ok(
            {
                "result": result,
                "apply_text": build_foreign_equity_source_apply_text(result),
            },
            result.warnings,
        )

    if path == "/api/research/preparation/run":
        action = str(body.get("action") or "scan").strip().lower()
        source = str(body.get("source") or "pending").strip().lower()
        raw_tickers = body.get("tickers")
        tickers: tuple[str, ...] = ()
        if isinstance(raw_tickers, (list, tuple)):
            tickers = tuple(str(item) for item in raw_tickers if str(item).strip())
        elif isinstance(raw_tickers, str) and raw_tickers.strip():
            tickers = tuple(part.strip() for part in raw_tickers.split(",") if part.strip())
        if action not in PREPARATION_ACTIONS:
            result = run_research_preparation(
                config,
                source=source,
                action=action,
                confirm=False,
                tickers=tickers,
            )
            payload = _error(
                result.blocked_reason or "invalid_preparation_action",
                "Research preparation run was blocked.",
                result.warnings,
            )
            payload["data"] = _to_jsonable({"result": result})
            return 400, payload
        if action not in {"scan", "discover_sources"}:
            confirmed, error = _require_confirmation(config, headers, body)
            if not confirmed and error is not None:
                return error
        result = run_research_preparation(
            config,
            source=source,
            action=action,
            confirm=action not in {"scan", "discover_sources"},
            tickers=tickers,
        )
        return 200, _ok({"result": result})

    if path == "/api/ops/intraday-cycle":
        confirmed, error = _require_confirmation(config, headers, body)
        if not confirmed and error is not None:
            return error
        try:
            result = run_intraday_cycle(
                config,
                source=str(body.get("source") or "auto"),
                ticker=_normalize_ticker_body(body),
                deliver=bool(body.get("deliver", False)),
                channel=str(body.get("channel") or "file"),
                include_options=bool(body.get("include_options", False)),
                drain_first=bool(body.get("drain_first", False)),
            )
        except ValueError as error_value:
            return 400, _error("invalid_intraday_cycle_request", str(error_value))
        return 200 if result.status != "error" else 500, _ok({"result": result})

    if path == "/api/ops/manual-cycle":
        dry_run = bool(body.get("dry_run", False))
        if not dry_run:
            confirmed, error = _require_confirmation(config, headers, body)
            if not confirmed and error is not None:
                return error
        try:
            result = run_manual_ops_cycle(
                config,
                mode=str(body.get("mode") or "auto"),
                deliver=bool(body.get("deliver", False)),
                channel=str(body.get("channel") or "file"),
                dry_run=dry_run,
            )
        except ValueError as error_value:
            return 400, _error("invalid_manual_ops_cycle_request", str(error_value))
        status_code = 200 if result.status != "error" else 500
        return status_code, _ok({"result": result})

    if path == "/api/loop/run-once":
        confirmed, error = _require_confirmation(config, headers, body)
        if not confirmed and error is not None:
            return error
        try:
            args = _loop_body_args(body)
            result = tom_loop_once(
                config,
                mode=str(args["mode"]),
                deliver=bool(args["deliver"]),
                channel=str(args["channel"]),
            )
        except (RuntimeError, ValueError) as error_value:
            return 400, _error("invalid_loop_run_once_request", str(error_value))
        status_code = 200 if result.status != "error" else 500
        return status_code, _ok({"result": result})

    if path == "/api/loop/start":
        confirmed, error = _require_confirmation(config, headers, body)
        if not confirmed and error is not None:
            return error
        try:
            result = _start_loop_thread(config, body)
        except (RuntimeError, ValueError) as error_value:
            return 409, _error("loop_start_blocked", str(error_value))
        return 200, _ok({"result": result})

    if path == "/api/loop/stop":
        confirmed, error = _require_confirmation(config, headers, body)
        if not confirmed and error is not None:
            return error
        result = tom_loop_stop(config)
        return 200, _ok({"result": result})

    if path == "/api/account/export-template":
        confirmed, error = _require_confirmation(config, headers, body)
        if not confirmed and error is not None:
            return error
        return 200, _ok({"result": export_account_context_template(config)})

    if path == "/api/account/append-row":
        confirmed, error = _require_confirmation(config, headers, body)
        if not confirmed and error is not None:
            return error
        row_type = str(body.get("row_type") or "").strip()
        row_payload = body.get("row")
        if not row_type:
            return 400, _error("missing_row_type", "Request body must include row_type.")
        if isinstance(row_payload, Mapping):
            row = row_payload
        else:
            row = {
                key: value
                for key, value in body.items()
                if key not in {"confirm", "row_type"}
            }
        try:
            result = _append_account_context_row(config, row_type, row)
        except ValueError as error_value:
            return 400, _error("invalid_account_context_row_type", str(error_value))
        return 200, _ok({"result": result})

    if path == "/api/account/apply-backfill":
        dry_run = bool(body.get("dry_run", False))
        if not dry_run:
            confirmed, error = _require_confirmation(config, headers, body)
            if not confirmed and error is not None:
                return error
        try:
            result = apply_account_context_backfill(
                config,
                confirm=not dry_run,
                allow_partial=bool(body.get("allow_partial", False)),
            )
        except ValueError as error_value:
            return 409, _error("account_context_apply_blocked", str(error_value))
        status_code = 200 if result.applied or dry_run else 409
        return status_code, _ok({"result": result}, result.warnings)

    if path == "/api/account/normalize-export":
        confirmed, error = _require_confirmation(config, headers, body)
        if not confirmed and error is not None:
            return error
        provider = str(body.get("provider") or "").strip()
        file_value = str(body.get("file") or body.get("path") or "").strip()
        if not provider:
            return 400, _error("missing_provider", "Request body must include provider.")
        if not file_value:
            return 400, _error("missing_file", "Request body must include file.")
        input_path = Path(file_value)
        if not input_path.is_absolute():
            input_path = config.project_root / input_path
        try:
            result = normalize_account_export(config, provider=provider, path=input_path)
        except (FileNotFoundError, ValueError) as error_value:
            return 400, _error("account_export_normalize_failed", str(error_value))
        return 200, _ok({"result": result}, result.warnings)

    if path == "/api/account/fetch-context":
        confirmed, error = _require_confirmation(config, headers, body)
        if not confirmed and error is not None:
            return error
        file_value = str(body.get("file") or body.get("path") or "").strip()
        input_path = None
        if file_value:
            input_path = Path(file_value)
            if not input_path.is_absolute():
                input_path = config.project_root / input_path
        try:
            result = fetch_account_context(
                config,
                source=str(body.get("source") or "file"),
                read_only=bool(body.get("read_only", False)),
                provider=str(body.get("provider") or "generic"),
                path=input_path,
            )
        except (FileNotFoundError, ValueError) as error_value:
            return 400, _error("account_context_fetch_blocked", str(error_value))
        status_code = 200 if result.fetched else 202
        return status_code, _ok({"result": result}, result.warnings)

    if path == "/api/missing-tickers/resolve":
        confirmed, error = _require_confirmation(config, headers, body)
        if not confirmed and error is not None:
            return error
        source = str(body.get("source") or "all")
        result = resolve_missing_tickers(config, source=source)
        return 200, _ok({"result": result}, result.warnings)

    if path == "/api/missing-tickers/apply":
        confirmed, error = _require_confirmation(config, headers, body)
        if not confirmed and error is not None:
            return error
        result = apply_missing_ticker_onboarding(
            config,
            confirm=True,
            source=str(body.get("source") or "account_context"),
        )
        status_code = 200 if result.applied else 409
        return status_code, _ok({"result": result}, result.warnings)

    if path == "/api/missing-tickers/hydrate":
        confirmed, error = _require_confirmation(config, headers, body)
        if not confirmed and error is not None:
            return error
        ticker = _normalize_ticker_body(body)
        if not ticker:
            return 400, _error("missing_ticker", "Request body must include ticker.")
        result = hydrate_missing_ticker(config, ticker)
        status_code = 200 if result.status == "hydrated" else 409
        return status_code, _ok({"result": result}, result.warnings)

    if path == "/api/backfills/options/export-template":
        confirmed, error = _require_confirmation(config, headers, body)
        if not confirmed and error is not None:
            return error
        return 200, _ok({"result": export_options_chain_missing_template(config)})

    if path == "/api/backfills/options/apply":
        confirmed, error = _require_confirmation(config, headers, body)
        if not confirmed and error is not None:
            return error
        result = apply_options_chain_coverage_backfill(
            config,
            confirm=True,
            allow_partial=bool(body.get("allow_partial", False)),
        )
        status_code = 200 if result.success else 409
        return status_code, _ok({"result": result}, result.warnings)

    if path == "/api/backfills/news/export-template":
        confirmed, error = _require_confirmation(config, headers, body)
        if not confirmed and error is not None:
            return error
        return 200, _ok({"result": export_news_catalyst_provider_backfill(config)})

    if path == "/api/backfills/news/append-row":
        confirmed, error = _require_confirmation(config, headers, body)
        if not confirmed and error is not None:
            return error
        row_payload = body.get("row")
        if isinstance(row_payload, Mapping):
            row = row_payload
        else:
            row = {
                key: value
                for key, value in body.items()
                if key != "confirm"
            }
        if not row:
            return 400, _error("missing_news_catalyst_row", "Request body must include row fields.")
        result = _append_news_catalyst_provider_native_row(config, row)
        return 200, _ok({"result": result})

    if path == "/api/backfills/news/apply":
        confirmed, error = _require_confirmation(config, headers, body)
        if not confirmed and error is not None:
            return error
        result = apply_news_catalyst_provider_backfill(
            config,
            confirm=True,
            allow_partial=bool(body.get("allow_partial", False)),
        )
        status_code = 200 if result.applied else 409
        return status_code, _ok(
            {
                "result": result,
                "apply_text": build_news_catalyst_provider_backfill_apply_text(result),
            },
            result.warnings,
        )

    if path == "/api/backfills/short-interest/export-template":
        confirmed, error = _require_confirmation(config, headers, body)
        if not confirmed and error is not None:
            return error
        return 200, _ok({"result": export_short_interest_missing_provider_template(config)})

    if path == "/api/backfills/short-interest/append-row":
        confirmed, error = _require_confirmation(config, headers, body)
        if not confirmed and error is not None:
            return error
        row_payload = body.get("row")
        if isinstance(row_payload, Mapping):
            row = row_payload
        else:
            row = {
                key: value
                for key, value in body.items()
                if key != "confirm"
            }
        if not row:
            return 400, _error("missing_short_interest_row", "Request body must include row fields.")
        result = _append_short_interest_missing_provider_row(config, row)
        return 200, _ok({"result": result})

    if path == "/api/backfills/short-interest/apply":
        confirmed, error = _require_confirmation(config, headers, body)
        if not confirmed and error is not None:
            return error
        result = apply_short_interest_provider_backfill(config, confirm=True)
        status_code = 200 if result.blocked_apply_reason is None else 409
        apply_text = "\n".join(
            (
                "Short interest provider backfill confirmed apply",
                f"Apply ready: {getattr(result, 'apply_ready', False)}",
                f"Blocked apply reason: {result.blocked_apply_reason or 'none'}",
                f"Imported rows: {getattr(result, 'imported_count', 0)}",
                f"Written rows: {getattr(result, 'written_count', 0)}",
            )
        )
        return status_code, _ok(
            {
                "result": result,
                "apply_text": apply_text,
            },
            result.warnings,
        )

    if path == "/api/notifications/drain":
        confirmed, error = _require_confirmation(config, headers, body)
        if not confirmed and error is not None:
            return error
        try:
            result = deliver_notifications(
                config,
                channel=str(body.get("channel") or "file"),
            )
        except ValueError as error_value:
            return 400, _error("invalid_notification_channel", str(error_value))
        status_code = 200 if result.failed_count == 0 else 502
        return status_code, _ok({"result": result}, result.warnings)

    return 404, _error("not_found", f"Unknown API route: {path}")


def handle_api_request(
    config: AppConfig,
    method: str,
    target: str,
    *,
    headers: Mapping[str, str] | None = None,
    body: object | None = None,
) -> tuple[int, dict[str, object]]:
    parsed = urlparse(target)
    path = parsed.path.rstrip("/") or "/"
    query = parse_qs(parsed.query)
    method_name = method.upper()
    try:
        if method_name == "GET":
            return _dispatch_get(config, path, query)
        if method_name == "POST":
            payload, parse_error = _parse_json_payload(body)
            if parse_error:
                return 400, _error(parse_error, "Request body must be valid JSON object.")
            return _dispatch_post(config, path, headers, payload)
        return 405, _error("method_not_allowed", f"Unsupported method: {method_name}")
    except Exception as error_value:
        return 500, _error(
            "internal_error",
            f"{type(error_value).__name__}: {error_value}",
        )


def _validate_local_bind(host: str) -> None:
    if host not in LOCAL_HOSTS:
        raise ValueError(
            f"Refusing non-local API bind host {host!r}. Phase 14A only supports local hosts."
        )


def serve_api(
    config: AppConfig,
    *,
    host: str | None = None,
    port: int | None = None,
) -> None:
    bind_host = host or config.api_host
    bind_port = int(port or config.api_port)
    _validate_local_bind(bind_host)

    class TomApiHandler(BaseHTTPRequestHandler):
        server_version = "TomLocalApi/14A"

        def _send_json(self, status_code: int, payload: dict[str, object]) -> None:
            response = json.dumps(_to_jsonable(payload), ensure_ascii=False).encode("utf-8")
            self.send_response(status_code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(response)))
            origin = self.headers.get("Origin")
            for key, value in api_cors_headers(config, origin).items():
                self.send_header(key, value)
            self.end_headers()
            self.wfile.write(response)

        def do_OPTIONS(self) -> None:  # noqa: N802
            self.send_response(204)
            origin = self.headers.get("Origin")
            for key, value in api_cors_headers(config, origin).items():
                self.send_header(key, value)
            self.end_headers()

        def do_GET(self) -> None:  # noqa: N802
            status_code, payload = handle_api_request(
                config,
                "GET",
                self.path,
                headers=dict(self.headers.items()),
            )
            self._send_json(status_code, payload)

        def do_POST(self) -> None:  # noqa: N802
            content_length = int(self.headers.get("Content-Length") or 0)
            body = self.rfile.read(content_length) if content_length else b""
            status_code, payload = handle_api_request(
                config,
                "POST",
                self.path,
                headers=dict(self.headers.items()),
                body=body,
            )
            self._send_json(status_code, payload)

        def log_message(self, format: str, *args: Any) -> None:
            return

    server = ThreadingHTTPServer((bind_host, bind_port), TomApiHandler)
    try:
        server.serve_forever()
    finally:
        server.server_close()


def serve_api_once_smoke_test(
    config: AppConfig,
    *,
    host: str | None = None,
    port: int | None = None,
) -> dict[str, object]:
    bind_host = host or config.api_host
    _validate_local_bind(bind_host)
    status_code, health = handle_api_request(config, "GET", "/api/health")
    status_status_code, status_payload = handle_api_request(config, "GET", "/api/status")
    return {
        "host": bind_host,
        "port": int(port or config.api_port),
        "health_status_code": status_code,
        "status_status_code": status_status_code,
        "health_ok": bool(health.get("ok")),
        "status_ok": bool(status_payload.get("ok")),
    }
