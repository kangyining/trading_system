from __future__ import annotations

from datetime import datetime
from typing import Any, Callable, Iterable

from .account import account_context_status
from .config import AppConfig
from .commentary_onboarding import build_commentary_onboarding_plan
from .db import REQUIRED_TABLES, get_database_status
from .insider_activity import (
    build_insider_source_status_text,
    insider_source_status_report,
    insider_statuses,
)
from .intraday_health import intraday_health
from .news_catalyst_sources import (
    build_news_catalyst_provider_backfill_status_text,
    build_news_catalyst_provider_upgrade_status_text,
    build_news_catalyst_source_status_text,
    news_catalyst_provider_backfill_apply_status,
    news_catalyst_provider_upgrade_status,
    news_catalyst_source_status_report,
)
from .news_catalysts import news_catalyst_statuses
from .options import (
    option_chain_availability_statuses,
    option_chain_coverage_plan,
    option_provider_status,
)
from .revision_evidence import build_revision_evidence, build_revision_evidence_report
from .revision_sources import (
    build_revision_provider_status_text,
    build_revision_source_status_text,
    revision_provider_statuses,
    revision_source_status_report,
)
from .short_interest import (
    build_short_interest_provider_status_text,
    build_short_interest_source_status_text,
    build_short_interest_status_text,
    short_interest_provider_status,
    short_interest_source_status_report,
    short_interest_statuses,
)
from .storage import (
    count_rows_by_table,
    latest_pipeline_run,
    latest_price_date,
    latest_quote_timestamp,
    latest_range_snapshot_timestamp,
    list_assets,
    list_research_recommendation_candidates,
    range_statuses,
    regime_signal_statuses,
    signal_statuses,
    technical_signal_statuses,
    trader_commentary_statuses,
)
from .technical import build_regime_status_text, build_technical_status_text
from .tom_loop import tom_loop_status
from .trader_commentary import build_trader_commentary_status_text


SIGNAL_LANE_KEYS = (
    "analyst_revisions",
    "news_catalyst",
    "insider_activity",
    "short_interest",
    "trader_commentary",
    "technical_regime",
    "ranges",
)

COVERAGE_GROUP_KEYS = (
    "operational_freshness",
    "account_options_context",
    "signal_evidence_lanes",
    "research_queue",
    "api_ui_runtime",
)

_BLOCKING_STATUS_ORDER = (
    "provider_key_or_export_required",
    "source_data_required",
    "user_review_required",
    "evidence_gated",
    "disabled_by_choice",
    "operator_start",
)


def _generated_at() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _unique(values: Iterable[str | None]) -> tuple[str, ...]:
    output: list[str] = []
    for value in values:
        if value is None:
            continue
        cleaned = str(value).strip()
        if cleaned and cleaned not in output:
            output.append(cleaned)
    return tuple(output)


def _split_tokens(value: str | None) -> tuple[str, ...]:
    if not value:
        return ()
    normalized = str(value).replace(";", ",")
    return _unique(part.strip() for part in normalized.split(","))


def _field(source: object, name: str, default: Any = None) -> Any:
    if isinstance(source, dict):
        return source.get(name, default)
    return getattr(source, name, default)


def _safe_count(config: AppConfig, table_name: str) -> int:
    try:
        existing_tables = set(get_database_status(config.database_path).existing_tables)
        if table_name not in existing_tables:
            return 0
        return count_rows_by_table(config.database_path, table_name)
    except Exception:
        return 0


def _asset_counts(config: AppConfig) -> dict[str, int]:
    try:
        assets = list_assets(config.database_path)
    except Exception:
        assets = []
    active = [asset for asset in assets if asset.active_flag == 1]
    scoreable = [asset for asset in active if (asset.asset_role or "scoreable") == "scoreable"]
    active_equities = [
        asset for asset in scoreable if (asset.asset_type or "equity").strip().lower() == "equity"
    ]
    return {
        "active_assets": len(active),
        "scoreable_assets": len(scoreable),
        "active_equities": len(active_equities),
    }


def _coverage_label(covered: int | None, total: int | None) -> str:
    if covered is None or total is None:
        return "unknown"
    return f"{covered}/{total}"


def _coverage_counts(covered: int | None, total: int | None) -> dict[str, object]:
    pct = None
    if covered is not None and total:
        pct = round((covered / total) * 100.0, 2)
    return {
        "covered": covered,
        "total": total,
        "coverage_pct": pct,
        "label": _coverage_label(covered, total),
    }


def _warning_tokens_from_rows(rows: Iterable[object]) -> tuple[str, ...]:
    warnings: list[str] = []
    for row in rows:
        warnings.extend(_split_tokens(_field(row, "data_warnings")))
    return _unique(warnings)


def _latest_text(rows: Iterable[object], field_name: str) -> str | None:
    values = [
        str(value)
        for value in (_field(row, field_name) for row in rows)
        if value not in {None, ""}
    ]
    return max(values) if values else None


def _signal_summary(rows: Iterable[object], latest_field: str = "latest_signal_date") -> dict[str, object]:
    materialized = tuple(rows)
    return {
        "ticker_count": len(materialized),
        "tickers": tuple(_field(row, "ticker") for row in materialized if _field(row, "ticker")),
        "latest_signal_date": _latest_text(materialized, latest_field),
        "warning_count": sum(1 for row in materialized if _field(row, "data_warnings")),
        "warnings": _warning_tokens_from_rows(materialized),
    }


def _has_signal_date(row: object, latest_field: str = "signal_date") -> bool:
    return bool(str(_field(row, latest_field, "") or "").strip())


def _ticker_set(rows: Iterable[object]) -> set[str]:
    return {
        str(_field(row, "ticker", "") or "").strip().upper()
        for row in rows
        if str(_field(row, "ticker", "") or "").strip()
    }


def _configured_regime_tickers(config: AppConfig) -> tuple[str, ...]:
    return tuple(
        dict.fromkeys(
            str(ticker).strip().upper()
            for ticker in (
                tuple(config.regime_benchmark_tickers)
                + tuple(config.regime_sector_proxy_tickers)
            )
            if str(ticker).strip()
        )
    )


def _input_blocker_tickers(
    rows: Iterable[object],
    blocker_tokens: Iterable[str],
) -> tuple[str, ...]:
    blockers = tuple(blocker_tokens)
    tickers: list[str] = []
    for row in rows:
        warnings = _split_tokens(_field(row, "data_warnings"))
        if any(token in warnings for token in blockers):
            ticker = str(_field(row, "ticker", "") or "").strip().upper()
            if ticker:
                tickers.append(ticker)
    return _unique(tickers)


def _status_from_coverage(
    total: int,
    covered: int,
    gap_status: str,
    *,
    zero_total_status: str = "ready",
) -> str:
    if total <= 0:
        return zero_total_status
    if covered >= total:
        return "ready"
    return gap_status


def _aggregate_status(statuses: Iterable[str]) -> str:
    materialized = tuple(statuses)
    for status in _BLOCKING_STATUS_ORDER:
        if status in materialized:
            return status
    return "ready"


def _status_counts(items: Iterable[dict[str, object]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in items:
        status = str(item.get("status") or "unknown")
        counts[status] = counts.get(status, 0) + 1
    return counts


def _lane(
    *,
    key: str,
    label: str,
    status: str,
    coverage: dict[str, object],
    blockers: Iterable[str | None] = (),
    warnings: Iterable[str | None] = (),
    notes: Iterable[str | None] = (),
    counts: dict[str, object] | None = None,
    details: dict[str, object] | None = None,
    status_text: str = "",
    commands: Iterable[str] = (),
) -> dict[str, object]:
    return {
        "key": key,
        "label": label,
        "status": status,
        "coverage": coverage,
        "coverage_label": str(coverage.get("label") or "unknown"),
        "counts": counts or {},
        "blockers": _unique(blockers),
        "warnings": _unique(warnings),
        "notes": _unique(notes),
        "details": details or {},
        "status_text": status_text,
        "commands": tuple(commands),
    }


def _safe_lane(
    key: str,
    label: str,
    builder: Callable[[AppConfig], dict[str, object]],
    config: AppConfig,
) -> dict[str, object]:
    try:
        return builder(config)
    except Exception as error:
        return _lane(
            key=key,
            label=label,
            status="source_data_required",
            coverage=_coverage_counts(None, None),
            blockers=(f"{key}_status_unavailable",),
            warnings=(f"{type(error).__name__}: {error}",),
            status_text=f"{label} status unavailable: {type(error).__name__}: {error}",
        )


def _analyst_revision_lane(config: AppConfig) -> dict[str, object]:
    source = revision_source_status_report(config)
    evidence = build_revision_evidence(config)
    signals = signal_statuses(config.database_path)
    providers = revision_provider_statuses(config)
    source_status = _status_from_coverage(
        source.active_equity_count,
        source.source_backed_ticker_count,
        "source_data_required",
    )
    status = source_status
    if source_status == "ready" and evidence.decision not in {"pass", "passed", "ready"}:
        status = "evidence_gated"
    blockers: list[str] = []
    if source.missing_source_tickers:
        blockers.append("missing_source_tickers")
    if source.missing_source_field_tickers:
        blockers.append("missing_source_fields")
    if evidence.decision not in {"pass", "passed", "ready"}:
        blockers.append(f"revision_evidence:{evidence.decision}")
    provider_warnings = tuple(
        f"{provider.provider}:{provider.status}"
        for provider in providers
        if provider.enabled and not provider.available
    )
    return _lane(
        key="analyst_revisions",
        label="Analyst Revisions",
        status=status,
        coverage=_coverage_counts(source.source_backed_ticker_count, source.active_equity_count),
        blockers=blockers,
        warnings=tuple(source.warnings) + provider_warnings,
        notes=("shadow_mode_enabled" if evidence.shadow_mode else None,),
        counts={
            "active_equity_count": source.active_equity_count,
            "source_backed_ticker_count": source.source_backed_ticker_count,
            "source_snapshot_count": source.source_snapshot_count,
            "aggregate_count": source.aggregate_count,
            "composite_signal_ticker_count": evidence.signal_ticker_count,
            "completed_20d_count": evidence.completed_20d_count,
        },
        details={
            "source_status": source,
            "evidence": evidence,
            "providers": providers,
            "signals": _signal_summary(signals),
        },
        status_text="\n\n".join(
            (
                build_revision_source_status_text(config),
                build_revision_provider_status_text(config),
                build_revision_evidence_report(config),
            )
        ),
        commands=(
            "python -m target_opportunity_monitor revision-source-status",
            "python -m target_opportunity_monitor revision-evidence-report",
        ),
    )


def _news_catalyst_lane(config: AppConfig) -> dict[str, object]:
    source = news_catalyst_source_status_report(config)
    upgrade = news_catalyst_provider_upgrade_status(config)
    backfill = news_catalyst_provider_backfill_apply_status(config)
    statuses = news_catalyst_statuses(config)
    status = _status_from_coverage(
        source.active_equity_count,
        source.provider_numeric_ticker_count,
        "provider_key_or_export_required",
    )
    coverage_complete = (
        source.active_equity_count <= 0
        or (
            source.provider_numeric_ticker_count >= source.active_equity_count
            and not source.missing_numeric_tickers
            and not source.provider_native_upgrade_tickers
        )
    )
    blockers: list[str] = []
    if source.provider_native_upgrade_tickers:
        blockers.append("provider_native_upgrade_required")
    if source.missing_numeric_tickers:
        blockers.append("missing_numeric_source_tickers")
    optional_provider_blockers = []
    if upgrade.missing_key_providers:
        optional_provider_blockers.append("missing_provider_keys")
    optional_provider_blockers.extend(upgrade.provider_blockers)
    if backfill.blocked_apply_reason:
        optional_provider_blockers.append(backfill.blocked_apply_reason)
    if not coverage_complete:
        blockers.extend(optional_provider_blockers)
    notes = ["text_derived_rows_remain_lower_confidence"]
    if coverage_complete and optional_provider_blockers:
        notes.append("optional_provider_limitations_not_blocking_coverage")
    return _lane(
        key="news_catalyst",
        label="News/Catalyst",
        status=status,
        coverage=_coverage_counts(source.provider_numeric_ticker_count, source.active_equity_count),
        blockers=blockers,
        warnings=tuple(source.warnings) + tuple(upgrade.warnings) + tuple(backfill.warnings),
        notes=notes,
        counts={
            "active_equity_count": source.active_equity_count,
            "provider_native_ticker_count": source.provider_numeric_ticker_count,
            "total_numeric_ticker_count": source.total_numeric_ticker_count,
            "text_derived_ticker_count": source.text_derived_ticker_count,
            "source_snapshot_count": source.source_snapshot_count,
            "signal_ticker_count": len(statuses),
            "optional_provider_blockers": tuple(optional_provider_blockers),
        },
        details={
            "source_status": source,
            "provider_upgrade": upgrade,
            "provider_backfill": backfill,
            "signals": _signal_summary(statuses),
        },
        status_text="\n\n".join(
            (
                build_news_catalyst_source_status_text(config),
                build_news_catalyst_provider_upgrade_status_text(config),
                build_news_catalyst_provider_backfill_status_text(config),
            )
        ),
        commands=(
            "python -m target_opportunity_monitor news-catalyst-provider-upgrade-status",
            "python -m target_opportunity_monitor news-catalyst-provider-backfill-status",
        ),
    )


def _insider_activity_lane(config: AppConfig) -> dict[str, object]:
    source = insider_source_status_report(config)
    statuses = insider_statuses(config)
    status = _status_from_coverage(
        source.active_equity_count,
        source.source_backed_ticker_count,
        "source_data_required",
    )
    blockers: list[str] = []
    if source.missing_source_tickers:
        blockers.append("missing_source_tickers")
    return _lane(
        key="insider_activity",
        label="Insider Activity",
        status=status,
        coverage=_coverage_counts(source.source_backed_ticker_count, source.active_equity_count),
        blockers=blockers,
        warnings=tuple(source.warnings),
        notes=("sec_form4_source_backed_shadow_signal",),
        counts={
            "active_equity_count": source.active_equity_count,
            "source_backed_ticker_count": source.source_backed_ticker_count,
            "source_snapshot_count": source.source_snapshot_count,
            "signal_ticker_count": len(statuses),
        },
        details={
            "source_status": source,
            "signals": _signal_summary(statuses),
        },
        status_text=build_insider_source_status_text(config),
        commands=("python -m target_opportunity_monitor insider-source-status",),
    )


def _short_interest_lane(config: AppConfig) -> dict[str, object]:
    source = short_interest_source_status_report(config)
    provider = short_interest_provider_status(config)
    statuses = short_interest_statuses(config)
    status = _status_from_coverage(
        source.active_equity_count,
        source.source_backed_ticker_count,
        "provider_key_or_export_required",
    )
    blockers: list[str] = []
    if source.missing_source_tickers:
        blockers.append("missing_source_tickers")
    if provider.provider_export_valid_row_count == 0 and source.missing_source_tickers:
        blockers.append("no_valid_provider_export_rows")
    return _lane(
        key="short_interest",
        label="Short Interest",
        status=status,
        coverage=_coverage_counts(source.source_backed_ticker_count, source.active_equity_count),
        blockers=blockers,
        warnings=tuple(source.warnings) + tuple(provider.warnings),
        notes=("source_backed_rows_required",),
        counts={
            "active_equity_count": source.active_equity_count,
            "source_backed_ticker_count": source.source_backed_ticker_count,
            "source_snapshot_count": source.source_snapshot_count,
            "provider_export_valid_row_count": provider.provider_export_valid_row_count,
            "signal_ticker_count": len(statuses),
        },
        details={
            "source_status": source,
            "provider_status": provider,
            "signals": _signal_summary(statuses),
        },
        status_text="\n\n".join(
            (
                build_short_interest_status_text(config),
                build_short_interest_source_status_text(config),
                build_short_interest_provider_status_text(config),
            )
        ),
        commands=(
            "python -m target_opportunity_monitor short-interest-missing-coverage-plan",
            "python -m target_opportunity_monitor short-interest-status",
        ),
    )


def _trader_commentary_lane(config: AppConfig) -> dict[str, object]:
    statuses = trader_commentary_statuses(config.database_path)
    raw_count = _safe_count(config, "trader_commentary_raw")
    claim_count = _safe_count(config, "trader_commentary_claims")
    outcome_count = _safe_count(config, "trader_commentary_claim_outcomes")
    onboarding_plan = build_commentary_onboarding_plan(config)
    status = "ready" if raw_count or claim_count or statuses else "disabled_by_choice"
    notes = ["x_capture_disabled_by_choice", "discord_capture_disabled_by_choice"]
    if onboarding_plan.intentionally_unresolved_count:
        notes.append("intentionally_unresolved_commentary_labels")
    if onboarding_plan.ignored_non_instrument_count:
        notes.append("ignored_non_instrument_commentary_labels")
    return _lane(
        key="trader_commentary",
        label="Trader Commentary",
        status=status,
        coverage=_coverage_counts(len(statuses), len(statuses) if statuses else 0),
        warnings=_warning_tokens_from_rows(statuses),
        notes=tuple(notes),
        counts={
            "raw_commentary_rows": raw_count,
            "parsed_claim_rows": claim_count,
            "claim_outcome_rows": outcome_count,
            "validated_ticker_count": len(statuses),
            "onboarding_candidate_count": onboarding_plan.onboardable_count,
            "unmapped_label_count": onboarding_plan.unmapped_count,
            "label_disposition_count": onboarding_plan.label_disposition_count,
            "intentionally_unresolved_label_count": (
                onboarding_plan.intentionally_unresolved_count
            ),
            "ignored_non_instrument_label_count": (
                onboarding_plan.ignored_non_instrument_count
            ),
        },
        details={
            "statuses": statuses,
            "commentary_onboarding": {
                "onboardable_count": onboarding_plan.onboardable_count,
                "unmapped_count": onboarding_plan.unmapped_count,
                "alias_count": onboarding_plan.alias_count,
                "label_disposition_count": onboarding_plan.label_disposition_count,
                "intentionally_unresolved_count": (
                    onboarding_plan.intentionally_unresolved_count
                ),
                "ignored_non_instrument_count": (
                    onboarding_plan.ignored_non_instrument_count
                ),
                "candidates": onboarding_plan.candidates,
            },
        },
        status_text=build_trader_commentary_status_text(config),
        commands=(
            "python -m target_opportunity_monitor trader-commentary-status",
            "python -m target_opportunity_monitor trader-commentary-parse-review",
            "python -m target_opportunity_monitor commentary-onboarding-status",
        ),
    )


def _technical_regime_lane(config: AppConfig) -> dict[str, object]:
    technical = technical_signal_statuses(config.database_path)
    regime = regime_signal_statuses(config.database_path)
    regime_required_tickers = _configured_regime_tickers(config)
    technical_missing_tickers = tuple(
        str(_field(row, "ticker", "") or "").strip().upper()
        for row in technical
        if not _has_signal_date(row)
        and str(_field(row, "ticker", "") or "").strip()
    )
    technical_input_blocker_tickers = _input_blocker_tickers(
        technical,
        ("missing_price_history", "insufficient_price_history"),
    )
    regime_tickers = _ticker_set(regime)
    regime_missing_tickers = tuple(
        ticker for ticker in regime_required_tickers if ticker not in regime_tickers
    )
    regime_input_blocker_tickers = _input_blocker_tickers(
        (
            row
            for row in regime
            if str(_field(row, "ticker", "") or "").strip().upper()
            in set(regime_required_tickers)
        ),
        (
            "missing_benchmark_price_history",
            "missing_sector_proxy_price_history",
            "insufficient_regime_price_history",
        ),
    )
    technical_total = len(technical)
    regime_total = len(regime_required_tickers)
    technical_covered = max(
        0,
        technical_total
        - len(technical_missing_tickers)
        - len(technical_input_blocker_tickers),
    )
    regime_covered = max(
        0,
        regime_total - len(regime_missing_tickers) - len(regime_input_blocker_tickers),
    )
    total = technical_total + regime_total
    covered = technical_covered + regime_covered
    status = _status_from_coverage(total, covered, "source_data_required")
    blockers: list[str] = []
    if technical_missing_tickers:
        blockers.append("missing_technical_signal_rows")
    if technical_input_blocker_tickers:
        blockers.append("technical_price_history_required")
    if regime_missing_tickers:
        blockers.append("missing_regime_signal_rows")
    if regime_input_blocker_tickers:
        blockers.append("regime_price_history_required")
    return _lane(
        key="technical_regime",
        label="Technical/Regime",
        status=status,
        coverage=_coverage_counts(covered, total),
        blockers=blockers,
        warnings=_warning_tokens_from_rows(technical) + _warning_tokens_from_rows(regime),
        counts={
            "active_asset_count": technical_total,
            "scoreable_assets": _asset_counts(config)["scoreable_assets"],
            "technical_ticker_count": len(technical),
            "regime_ticker_count": len(regime),
            "technical_coverage_count": technical_covered,
            "technical_required_count": technical_total,
            "technical_coverage": f"{technical_covered}/{technical_total}",
            "technical_missing_tickers": technical_missing_tickers,
            "technical_input_blocker_tickers": technical_input_blocker_tickers,
            "regime_coverage_count": regime_covered,
            "regime_required_count": regime_total,
            "regime_coverage": f"{regime_covered}/{regime_total}",
            "regime_required_tickers": regime_required_tickers,
            "regime_missing_tickers": regime_missing_tickers,
            "regime_input_blocker_tickers": regime_input_blocker_tickers,
            "latest_technical_signal_date": _latest_text(technical, "signal_date"),
            "latest_regime_signal_date": _latest_text(regime, "signal_date"),
        },
        details={
            "technical": _signal_summary(technical, latest_field="signal_date"),
            "regime": _signal_summary(regime, latest_field="signal_date"),
            "technical_missing_tickers": technical_missing_tickers,
            "technical_input_blocker_tickers": technical_input_blocker_tickers,
            "regime_required_tickers": regime_required_tickers,
            "regime_missing_tickers": regime_missing_tickers,
            "regime_input_blocker_tickers": regime_input_blocker_tickers,
        },
        status_text="\n\n".join((build_technical_status_text(config), build_regime_status_text(config))),
        commands=(
            "python -m target_opportunity_monitor technical-status",
            "python -m target_opportunity_monitor regime-status",
        ),
    )


def _ranges_lane(config: AppConfig) -> dict[str, object]:
    snapshots = range_statuses(config.database_path)
    health = intraday_health(config)
    asset_counts = _asset_counts(config)
    total = asset_counts["active_assets"]
    covered = len(snapshots)
    if health.blockers:
        status = "source_data_required"
    else:
        status = _status_from_coverage(total, covered, "source_data_required")
    blockers = tuple(health.blockers)
    if total and not snapshots:
        blockers = blockers + ("missing_range_snapshots",)
    return _lane(
        key="ranges",
        label="Ranges",
        status=status,
        coverage=_coverage_counts(covered, total),
        blockers=blockers,
        warnings=tuple(health.warnings) + _warning_tokens_from_rows(snapshots),
        notes=tuple(health.notes),
        counts={
            "scoreable_assets": total,
            "range_snapshot_count": len(snapshots),
            "latest_range_snapshot_timestamp": health.latest_range_snapshot_timestamp,
            "market_session": health.market_session,
            "regular_market_hours": health.regular_market_hours,
        },
        details={
            "health": health,
            "latest_snapshots": snapshots[:25],
        },
        status_text=(
            "Range status is sourced from the latest range snapshots and intraday "
            "health payload. Use range-status for per-ticker table output."
        ),
        commands=(
            "python -m target_opportunity_monitor range-status",
            "python -m target_opportunity_monitor intraday-health-check",
        ),
    )


def build_signal_coverage_payload(config: AppConfig) -> dict[str, object]:
    lane_specs: tuple[tuple[str, str, Callable[[AppConfig], dict[str, object]]], ...] = (
        ("analyst_revisions", "Analyst Revisions", _analyst_revision_lane),
        ("news_catalyst", "News/Catalyst", _news_catalyst_lane),
        ("insider_activity", "Insider Activity", _insider_activity_lane),
        ("short_interest", "Short Interest", _short_interest_lane),
        ("trader_commentary", "Trader Commentary", _trader_commentary_lane),
        ("technical_regime", "Technical/Regime", _technical_regime_lane),
        ("ranges", "Ranges", _ranges_lane),
    )
    lanes = tuple(_safe_lane(key, label, builder, config) for key, label, builder in lane_specs)
    return {
        "generated_at": _generated_at(),
        "status": _aggregate_status(str(lane["status"]) for lane in lanes),
        "lane_keys": SIGNAL_LANE_KEYS,
        "status_counts": _status_counts(lanes),
        "lanes": lanes,
        "lane_map": {str(lane["key"]): lane for lane in lanes},
    }


def _group(
    *,
    key: str,
    label: str,
    status: str,
    summary: str,
    blockers: Iterable[str | None] = (),
    warnings: Iterable[str | None] = (),
    notes: Iterable[str | None] = (),
    counts: dict[str, object] | None = None,
    details: dict[str, object] | None = None,
    commands: Iterable[str] = (),
) -> dict[str, object]:
    return {
        "key": key,
        "label": label,
        "status": status,
        "summary": summary,
        "blockers": _unique(blockers),
        "warnings": _unique(warnings),
        "notes": _unique(notes),
        "counts": counts or {},
        "details": details or {},
        "commands": tuple(commands),
    }


def _operational_group(config: AppConfig) -> dict[str, object]:
    health = intraday_health(config)
    loop = tom_loop_status(config)
    loop_active = bool(_field(loop, "active"))
    loop_health = str(_field(loop, "health_status", "unknown"))
    status = "ready"
    blockers = list(health.blockers)
    blockers.extend(_field(loop, "stale_blockers", ()) or ())
    if not loop_active:
        status = "operator_start"
        blockers.append("tom_loop_not_running")
    elif health.status != "healthy" or loop_health != "healthy":
        status = "source_data_required"
    return _group(
        key="operational_freshness",
        label="Operational Freshness",
        status=status,
        summary=f"Intraday health {health.status}; TOM loop {loop_health}.",
        blockers=blockers,
        warnings=tuple(health.warnings) + tuple(_field(loop, "warnings", ()) or ()),
        notes=tuple(health.notes),
        counts={
            "market_session": health.market_session,
            "regular_market_hours": health.regular_market_hours,
            "pending_notifications": health.pending_notification_count,
            "failed_deliveries": health.failed_delivery_count,
            "latest_price_date": latest_price_date(config.database_path),
            "latest_quote_timestamp": latest_quote_timestamp(config.database_path),
            "latest_range_snapshot_timestamp": latest_range_snapshot_timestamp(config.database_path),
            "latest_intraday_cycle": latest_pipeline_run(
                config.database_path,
                run_type="intraday_cycle",
            ),
        },
        details={"intraday_health": health, "loop": loop},
        commands=(
            "python -m target_opportunity_monitor intraday-health-check",
            "python -m target_opportunity_monitor tom-loop-status",
        ),
    )


def _account_options_group(config: AppConfig) -> dict[str, object]:
    account = account_context_status(config)
    option_diag = account.option_position_diagnostics
    provider = option_provider_status(config, check_connectivity=False)
    coverage = option_chain_coverage_plan(config)
    availability_statuses = option_chain_availability_statuses(config)
    blockers = list(account.blockers)
    status = "ready"
    if account.option_position_rows == 0:
        blockers.append("empty_options_positions")
    if account.option_lifecycle_rows == 0:
        blockers.append("no_option_lifecycle_rows")
    if provider.blocked_reason:
        blockers.append(str(provider.blocked_reason))
    if provider.blocked_reason:
        status = "provider_key_or_export_required"
    elif blockers:
        status = "source_data_required"
    return _group(
        key="account_options_context",
        label="Account/Options Context",
        status=status,
        summary=(
            f"Account context {account.activation_status}; option positions "
            f"{account.option_position_rows}; lifecycle rows {account.option_lifecycle_rows}."
        ),
        blockers=blockers,
        warnings=tuple(dict.fromkeys(tuple(provider.warnings) + tuple(coverage.warnings))),
        notes=tuple(coverage.notes),
        counts={
            "portfolio_position_rows": account.portfolio_position_rows,
            "portfolio_cash_rows": account.portfolio_cash_rows,
            "option_position_rows": account.option_position_rows,
            "option_lifecycle_rows": account.option_lifecycle_rows,
            "option_position_readiness_status": option_diag.readiness_status,
            "valid_option_position_rows": option_diag.valid_option_position_rows,
            "invalid_option_position_rows": option_diag.invalid_option_position_rows,
            "blank_option_position_rows": option_diag.blank_option_position_rows,
            "projected_option_position_rows": option_diag.projected_option_position_rows,
            "projected_option_lifecycle_rows": option_diag.projected_option_lifecycle_rows,
            "option_risk_missing_portfolio_context_rows": (
                account.option_risk_missing_portfolio_context_rows
            ),
            "option_provider_readiness": provider.readiness_status,
            "option_chain_coverage_status": coverage.coverage_status,
            "option_chain_coverage_count": coverage.effective_coverage_count,
            "option_chain_raw_coverage_count": coverage.raw_coverage_count,
            "option_chain_non_actionable_tickers": coverage.non_actionable_tickers,
            "option_chain_availability_unavailable_tickers": tuple(
                status.ticker
                for status in availability_statuses
                if status.availability_status == "unavailable"
            ),
            "option_chain_availability_missing_tickers": tuple(
                status.ticker
                for status in availability_statuses
                if status.availability_status == "missing"
            ),
        },
        details={
            "account": account,
            "option_position_diagnostics": option_diag,
            "option_provider": provider,
            "option_chain_coverage": coverage,
            "option_chain_availability_statuses": availability_statuses,
        },
        commands=(
            "python -m target_opportunity_monitor account-context-status",
            "python -m target_opportunity_monitor option-chain-coverage-plan",
            "python -m target_opportunity_monitor options-lifecycle-status",
        ),
    )


def _signal_group(signal_payload: dict[str, object]) -> dict[str, object]:
    lanes = tuple(signal_payload.get("lanes") or ())
    blockers: list[str] = []
    warnings: list[str] = []
    for lane in lanes:
        lane_key = str(_field(lane, "key", "unknown"))
        blockers.extend(f"{lane_key}:{item}" for item in (_field(lane, "blockers", ()) or ()))
        warnings.extend(f"{lane_key}:{item}" for item in (_field(lane, "warnings", ()) or ()))
    return _group(
        key="signal_evidence_lanes",
        label="Signal/Evidence Lanes",
        status=str(signal_payload.get("status") or "ready"),
        summary=f"{len(lanes)} signal lanes exposed through read-only API/UI coverage.",
        blockers=blockers,
        warnings=warnings,
        counts={
            "lane_count": len(lanes),
            "status_counts": signal_payload.get("status_counts") or {},
        },
        details={"signals": signal_payload},
        commands=("python -m target_opportunity_monitor signal-status",),
    )


def _research_group(config: AppConfig) -> dict[str, object]:
    pending = list_research_recommendation_candidates(
        config.database_path,
        status="pending",
    )
    approved = list_research_recommendation_candidates(
        config.database_path,
        status="approved",
    )
    status = "user_review_required" if pending else "ready"
    return _group(
        key="research_queue",
        label="Research Queue",
        status=status,
        summary=f"{len(pending)} research recommendations are pending review.",
        blockers=("pending_research_recommendations" if pending else None,),
        counts={
            "pending": len(pending),
            "approved": len(approved),
            "total": _safe_count(config, "research_recommendation_candidates"),
        },
        details={"top_pending": pending[:25]},
        commands=("python -m target_opportunity_monitor research-recommendation-status",),
    )


def _api_ui_group(config: AppConfig) -> dict[str, object]:
    database = get_database_status(config.database_path)
    missing_tables = tuple(
        table_name for table_name in REQUIRED_TABLES if table_name not in database.existing_tables
    )
    status = "ready" if not missing_tables else "source_data_required"
    return _group(
        key="api_ui_runtime",
        label="API/UI Runtime",
        status=status,
        summary="Local API is serving this read-only coverage payload.",
        blockers=("missing_required_tables" if missing_tables else None,),
        notes=("local_only_runtime", "operator_start_required_after_reboot"),
        counts={
            "existing_table_count": len(database.existing_tables),
            "required_table_count": len(REQUIRED_TABLES),
            "missing_required_table_count": len(missing_tables),
        },
        details={"missing_required_tables": missing_tables},
        commands=(
            "python -m target_opportunity_monitor serve-api --once-smoke-test",
            "npm run build",
        ),
    )


def build_phase_coverage_payload(config: AppConfig) -> dict[str, object]:
    signal_payload = build_signal_coverage_payload(config)
    groups = (
        _operational_group(config),
        _account_options_group(config),
        _signal_group(signal_payload),
        _research_group(config),
        _api_ui_group(config),
    )
    return {
        "generated_at": _generated_at(),
        "status": _aggregate_status(str(group["status"]) for group in groups),
        "group_keys": COVERAGE_GROUP_KEYS,
        "status_counts": _status_counts(groups),
        "groups": groups,
        "group_map": {str(group["key"]): group for group in groups},
    }
