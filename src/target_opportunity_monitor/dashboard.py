from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
import json
from pathlib import Path

from .config import AppConfig
from .commentary_onboarding import build_commentary_onboarding_plan
from .db import get_database_status
from .insider_activity import insider_source_status_report
from .intraday_health import intraday_health
from .reporting import build_daily_report_rows
from .revision_evidence import build_revision_evidence
from .revision_sources import revision_source_status_report
from .scheduler import audit_scheduler
from .short_interest import (
    short_interest_missing_coverage_plan,
    short_interest_provider_status,
    short_interest_source_status_report,
    validate_short_interest_backfill,
)
from .news_catalyst_sources import (
    news_catalyst_coverage_plan,
    news_catalyst_provider_backfill_apply_status,
    preview_news_catalyst_provider_upgrade,
    news_catalyst_provider_upgrade_status,
    news_catalyst_source_status_report,
)
from .options import (
    format_option_chain_availability,
    option_chain_availability_statuses,
    option_chain_activation_status,
    option_chain_coverage_plan,
    option_fetch_assets,
    option_provider_status,
    validate_options_chain_backfill,
)
from .storage import (
    count_reference_assets,
    count_rows_by_table,
    count_scoreable_assets,
    etf_statuses,
    latest_alert_timestamp,
    latest_fundamental_benchmark_date,
    latest_notification_timestamp,
    latest_notification_delivery_timestamp,
    latest_outcome_date,
    latest_pipeline_run,
    latest_portfolio_review_date,
    latest_price_date,
    latest_range_snapshot_timestamp,
    latest_research_recommendation_date,
    latest_regime_signal_date,
    latest_score_date,
    latest_signal_date,
    latest_signal_outcome_date,
    latest_target_date,
    latest_technical_signal_date,
    latest_analyst_revision_aggregate_date,
    latest_insider_transaction_source_date,
    latest_news_catalyst_aggregate_date,
    latest_option_chain_snapshot_timestamp,
    latest_option_income_review_date,
    latest_option_position_open_date,
    latest_option_position_lifecycle_review_date,
    latest_option_review_outcome_date,
    latest_option_risk_review_date,
    latest_short_interest_settlement_date,
    latest_trader_commentary_capture_date,
    latest_trader_commentary_browser_capture_timestamp,
    latest_trader_commentary_discord_capture_timestamp,
    latest_trader_commentary_claim_date,
    latest_trader_commentary_outcome_date,
    list_alerts,
    list_notification_events,
    list_option_risk_reviews,
    notification_delivery_count,
    list_prices,
    outcome_statuses,
    option_income_statuses,
    option_lifecycle_statuses,
    option_outcome_statuses,
    option_position_statuses,
    option_risk_statuses,
    portfolio_statuses,
    range_statuses,
    regime_signal_statuses,
    signal_outcome_statuses,
    technical_signal_statuses,
    trader_commentary_statuses,
)


PRICE_HISTORY_DAYS = 180


@dataclass(frozen=True)
class DashboardResult:
    path: Path
    generated_at: str
    row_count: int


def dashboard_path(project_root: Path) -> Path:
    return project_root / "dashboard" / "index.html"


def latest_dashboard_path(project_root: Path) -> Path | None:
    path = dashboard_path(project_root)
    return path if path.exists() else None


def _price_value(price: object) -> float | None:
    adjusted_close = getattr(price, "adjusted_close", None)
    close = getattr(price, "close", None)
    return adjusted_close if adjusted_close is not None else close


def _recent_price_history(config: AppConfig, tickers: list[str]) -> dict[str, list[dict[str, object]]]:
    history: dict[str, list[dict[str, object]]] = {}
    for ticker in tickers:
        prices = list_prices(config.database_path, ticker)[-PRICE_HISTORY_DAYS:]
        history[ticker] = [
            {
                "date": price.price_date,
                "close": _price_value(price),
                "high": price.high,
                "low": price.low,
                "volume": price.volume,
            }
            for price in prices
        ]
    return history


def _table_counts(config: AppConfig, existing_tables: tuple[str, ...]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for table_name in existing_tables:
        counts[table_name] = count_rows_by_table(config.database_path, table_name)
    return counts


def _revision_source_payload(source_status: object) -> dict[str, object]:
    payload = asdict(source_status)
    payload["source_export_path"] = str(payload["source_export_path"])
    payload["source_exports_dir"] = str(payload["source_exports_dir"])
    payload["analyst_revisions_path"] = str(payload["analyst_revisions_path"])
    return payload


def _news_catalyst_source_payload(source_status: object) -> dict[str, object]:
    payload = asdict(source_status)
    payload["source_exports_dir"] = str(payload["source_exports_dir"])
    payload["cache_dir"] = str(payload["cache_dir"])
    payload["news_catalysts_path"] = str(payload["news_catalysts_path"])
    return payload


def _news_catalyst_coverage_plan_payload(plan: object) -> dict[str, object]:
    payload = asdict(plan)
    payload["template_path"] = str(payload["template_path"])
    payload["missing_template_path"] = str(payload["missing_template_path"])
    payload["provider_upgrade_template_path"] = str(
        payload["provider_upgrade_template_path"]
    )
    return payload


def _insider_source_payload(source_status: object) -> dict[str, object]:
    return asdict(source_status)


def _short_interest_source_payload(source_status: object) -> dict[str, object]:
    return asdict(source_status)


def _short_interest_backfill_payload(backfill_status: object) -> dict[str, object]:
    return {
        "source_exports_dir": str(getattr(backfill_status, "source_exports_dir")),
        "source_export_files": [
            str(path) for path in getattr(backfill_status, "source_export_files")
        ],
        "current_source_backed_count": getattr(
            backfill_status, "current_source_backed_count"
        ),
        "active_equity_count": getattr(backfill_status, "active_equity_count"),
        "missing_source_tickers": list(getattr(backfill_status, "missing_source_tickers")),
        "valid_row_count": getattr(backfill_status, "valid_row_count"),
        "valid_tickers": list(getattr(backfill_status, "valid_tickers")),
        "blank_placeholder_count": getattr(backfill_status, "blank_placeholder_count"),
        "invalid_row_count": getattr(backfill_status, "invalid_row_count"),
        "projected_source_backed_count": getattr(
            backfill_status, "projected_source_backed_count"
        ),
        "blocked_import_reason": getattr(backfill_status, "blocked_import_reason"),
        "apply_ready": getattr(backfill_status, "apply_ready"),
    }


def _short_interest_provider_payload(provider_status: object) -> dict[str, object]:
    payload = asdict(provider_status)
    payload["cache_dir"] = str(payload["cache_dir"])
    return payload


def _option_chain_coverage_plan_payload(plan: object) -> dict[str, object]:
    payload = asdict(plan)
    payload["backfill_template_path"] = str(payload["backfill_template_path"])
    payload["non_actionable_template_path"] = str(
        payload["non_actionable_template_path"]
    )
    return payload


def _build_dashboard_data(config: AppConfig) -> dict[str, object]:
    from .tom_loop import tom_loop_status

    database_status = get_database_status(config.database_path)
    rows = build_daily_report_rows(config, database_status)
    tickers = [row.ticker for row in rows]
    latest_pipeline = (
        latest_pipeline_run(config.database_path)
        if "pipeline_runs" in database_status.existing_tables
        else None
    )
    latest_intraday_cycle = (
        latest_pipeline_run(config.database_path, run_type="intraday_cycle")
        if "pipeline_runs" in database_status.existing_tables
        else None
    )
    current_intraday_health = intraday_health(config)
    loop_snapshot = tom_loop_status(config)
    scheduler_audit_result = audit_scheduler(config)
    heartbeat_job = next(
        (
            job
            for job in scheduler_audit_result.jobs
            if job.job_key == "intraday_heartbeat"
        ),
        None,
    )
    scheduler_warning_codes = tuple(
        dict.fromkeys(
            warning
            for job in scheduler_audit_result.jobs
            for warning in job.warnings
            if job.status != "configured"
        )
    )
    revision_evidence = build_revision_evidence(config)
    revision_source_status = revision_source_status_report(config)
    news_catalyst_source_status = news_catalyst_source_status_report(config)
    news_catalyst_plan = news_catalyst_coverage_plan(config, write_template=False)
    news_catalyst_upgrade_status = news_catalyst_provider_upgrade_status(config)
    news_catalyst_upgrade_preview = preview_news_catalyst_provider_upgrade(config)
    news_catalyst_backfill_apply_status = news_catalyst_provider_backfill_apply_status(config)
    insider_source_status = insider_source_status_report(config)
    short_interest_source_status = short_interest_source_status_report(config)
    short_interest_backfill_status = validate_short_interest_backfill(config)
    short_interest_provider = short_interest_provider_status(config)
    short_interest_missing_plan = short_interest_missing_coverage_plan(config)
    technical_signal_rows = (
        technical_signal_statuses(config.database_path)
        if "technical_signal_snapshots" in database_status.existing_tables
        else []
    )
    regime_signal_rows = (
        regime_signal_statuses(config.database_path)
        if "regime_signal_snapshots" in database_status.existing_tables
        else []
    )
    technical_missing_signal_tickers = tuple(
        status.ticker for status in technical_signal_rows if not status.signal_date
    )
    regime_required_tickers = tuple(
        dict.fromkeys(
            tuple(config.regime_benchmark_tickers)
            + tuple(config.regime_sector_proxy_tickers)
        )
    )
    regime_present_tickers = {
        status.ticker for status in regime_signal_rows if status.signal_date
    }
    regime_missing_signal_tickers = tuple(
        ticker for ticker in regime_required_tickers if ticker not in regime_present_tickers
    )
    option_fetch_tickers = tuple(
        asset.ticker for asset in option_fetch_assets(config, max_tickers=0)
    )
    option_status_rows = (
        option_income_statuses(config.database_path)
        if "option_income_reviews" in database_status.existing_tables
        else []
    )
    option_risk_rows = (
        option_risk_statuses(config.database_path)
        if "option_risk_reviews" in database_status.existing_tables
        else []
    )
    option_outcome_rows = (
        option_outcome_statuses(config.database_path)
        if "option_review_outcomes" in database_status.existing_tables
        else []
    )
    option_position_rows = (
        option_position_statuses(config.database_path)
        if "option_position_ledger" in database_status.existing_tables
        else []
    )
    option_lifecycle_rows = (
        option_lifecycle_statuses(config.database_path)
        if "option_position_lifecycle_reviews" in database_status.existing_tables
        else []
    )
    option_risk_category_counts: dict[str, int] = {}
    for status in option_risk_rows:
        if status.risk_category:
            option_risk_category_counts[status.risk_category] = (
                option_risk_category_counts.get(status.risk_category, 0) + 1
            )
    account_missing_portfolio_context_rows = (
        sum(
            1
            for review in list_option_risk_reviews(config.database_path)
            if review.risk_category == "portfolio_context_needed"
            or "missing_portfolio_context" in (review.risk_warnings or "")
        )
        if "option_risk_reviews" in database_status.existing_tables
        else 0
    )
    account_portfolio_position_rows = (
        count_rows_by_table(config.database_path, "portfolio_positions")
        if "portfolio_positions" in database_status.existing_tables
        else 0
    )
    account_portfolio_cash_rows = (
        count_rows_by_table(config.database_path, "portfolio_cash")
        if "portfolio_cash" in database_status.existing_tables
        else 0
    )
    account_option_position_rows = (
        count_rows_by_table(config.database_path, "option_position_ledger")
        if "option_position_ledger" in database_status.existing_tables
        else 0
    )
    account_option_lifecycle_rows = (
        count_rows_by_table(config.database_path, "option_position_lifecycle_reviews")
        if "option_position_lifecycle_reviews" in database_status.existing_tables
        else 0
    )
    from .account import option_position_readiness_diagnostics

    option_position_diagnostics = option_position_readiness_diagnostics(
        config,
        current_option_position_rows=account_option_position_rows,
        current_option_lifecycle_rows=account_option_lifecycle_rows,
    )
    account_context_blockers: list[str] = []
    if account_portfolio_position_rows == 0:
        account_context_blockers.append("empty_portfolio_positions")
    if account_portfolio_cash_rows == 0:
        account_context_blockers.append("empty_portfolio_cash")
    if account_option_position_rows == 0:
        account_context_blockers.append("empty_options_positions")
    if account_option_lifecycle_rows == 0:
        account_context_blockers.append("no_option_lifecycle_rows")
    if account_missing_portfolio_context_rows:
        account_context_blockers.append("option_risk_missing_portfolio_context")
    if not account_context_blockers:
        account_context_activation_status = "active"
    elif (
        account_portfolio_position_rows
        or account_portfolio_cash_rows
        or account_option_position_rows
        or account_option_lifecycle_rows
    ):
        account_context_activation_status = "partial"
    else:
        account_context_activation_status = "not_configured"
    option_outcome_status_counts: dict[str, int] = {}
    for status in option_outcome_rows:
        if status.outcome_status and status.outcome_count:
            option_outcome_status_counts[status.outcome_status] = (
            option_outcome_status_counts.get(status.outcome_status, 0) + 1
            )
    option_lifecycle_status_counts: dict[str, int] = {}
    for status in option_lifecycle_rows:
        if status.lifecycle_status:
            option_lifecycle_status_counts[status.lifecycle_status] = (
                option_lifecycle_status_counts.get(status.lifecycle_status, 0) + 1
            )
    option_provider = option_provider_status(config, check_connectivity=False)
    option_backfill_status = validate_options_chain_backfill(config)
    option_activation = option_chain_activation_status(config)
    option_coverage_plan = option_chain_coverage_plan(config)
    option_chain_availability = option_chain_availability_statuses(config)
    option_chain_missing_tickers = option_coverage_plan.effective_missing_tickers
    trader_commentary_status = (
        trader_commentary_statuses(config.database_path)
        if "trader_commentary_claims" in database_status.existing_tables
        else []
    )
    trader_commentary_warning_tickers = [
        status.ticker for status in trader_commentary_status if status.data_warnings
    ]
    commentary_onboarding_plan = build_commentary_onboarding_plan(config)

    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "system_name": "Target Opportunity Monitor",
        "rows": [asdict(row) for row in rows],
        "price_history": _recent_price_history(config, tickers)
        if "prices" in database_status.existing_tables
        else {},
        "alert_history": [asdict(alert) for alert in list_alerts(config.database_path)]
        if "alerts" in database_status.existing_tables
        else [],
        "outcomes": [asdict(outcome) for outcome in outcome_statuses(config.database_path)]
        if "alert_outcomes" in database_status.existing_tables
        else [],
        "ranges": [asdict(status) for status in range_statuses(config.database_path)]
        if "range_snapshots" in database_status.existing_tables
        else [],
        "technical_signals": [asdict(status) for status in technical_signal_rows],
        "regime_signals": [asdict(status) for status in regime_signal_rows],
        "notification_events": [
            asdict(event) for event in list_notification_events(config.database_path)
        ]
        if "notification_events" in database_status.existing_tables
        else [],
        "signal_outcomes": [
            asdict(outcome)
            for outcome in signal_outcome_statuses(config.database_path)
        ]
        if "signal_outcomes" in database_status.existing_tables
        else [],
        "revision_evidence": asdict(revision_evidence),
        "revision_source_status": _revision_source_payload(revision_source_status),
        "news_catalyst_source_status": _news_catalyst_source_payload(
            news_catalyst_source_status
        ),
        "news_catalyst_coverage_plan": _news_catalyst_coverage_plan_payload(
            news_catalyst_plan
        ),
        "insider_source_status": _insider_source_payload(insider_source_status),
        "short_interest_source_status": _short_interest_source_payload(
            short_interest_source_status
        ),
        "short_interest_backfill_status": _short_interest_backfill_payload(
            short_interest_backfill_status
        ),
        "short_interest_provider_status": _short_interest_provider_payload(
            short_interest_provider
        ),
        "option_chain_coverage_plan": _option_chain_coverage_plan_payload(
            option_coverage_plan
        ),
        "trader_commentary_status": [
            asdict(status) for status in trader_commentary_status
        ],
        "portfolio": [asdict(status) for status in portfolio_statuses(config.database_path)]
        if "portfolio_reviews" in database_status.existing_tables
        else [],
        "etfs": [asdict(status) for status in etf_statuses(config.database_path)]
        if "etf_features" in database_status.existing_tables
        else [],
        "health": {
            "database_exists": database_status.exists,
            "required_tables_present": database_status.existing_required_table_count,
            "required_tables_total": database_status.required_table_count,
            "table_counts": _table_counts(config, database_status.existing_tables)
            if database_status.exists
            else {},
            "latest_price_date": latest_price_date(config.database_path)
            if "prices" in database_status.existing_tables
            else None,
            "latest_target_date": latest_target_date(config.database_path)
            if "targets" in database_status.existing_tables
            else None,
            "latest_score_date": latest_score_date(config.database_path)
            if "scores" in database_status.existing_tables
            else None,
            "latest_fundamental_benchmark_date": latest_fundamental_benchmark_date(
                config.database_path
            )
            if "fundamental_comparison_snapshots" in database_status.existing_tables
            else None,
            "fundamental_benchmark_rows": count_rows_by_table(
                config.database_path,
                "fundamental_benchmark_snapshots",
            )
            if "fundamental_benchmark_snapshots" in database_status.existing_tables
            else 0,
            "fundamental_comparison_rows": count_rows_by_table(
                config.database_path,
                "fundamental_comparison_snapshots",
            )
            if "fundamental_comparison_snapshots" in database_status.existing_tables
            else 0,
            "research_recommendation_rows": count_rows_by_table(
                config.database_path,
                "research_recommendation_candidates",
            )
            if "research_recommendation_candidates" in database_status.existing_tables
            else 0,
            "latest_research_recommendation_date": latest_research_recommendation_date(
                config.database_path
            )
            if "research_recommendation_candidates" in database_status.existing_tables
            else None,
            "latest_range_snapshot": latest_range_snapshot_timestamp(config.database_path)
            if "range_snapshots" in database_status.existing_tables
            else None,
            "latest_technical_signal_date": latest_technical_signal_date(
                config.database_path
            )
            if "technical_signal_snapshots" in database_status.existing_tables
            else None,
            "latest_regime_signal_date": latest_regime_signal_date(config.database_path)
            if "regime_signal_snapshots" in database_status.existing_tables
            else None,
            "technical_signal_coverage": (
                f"{len(technical_signal_rows) - len(technical_missing_signal_tickers)}/"
                f"{len(technical_signal_rows)}"
            ),
            "technical_missing_signal_tickers": list(technical_missing_signal_tickers),
            "regime_signal_coverage": (
                f"{len(regime_required_tickers) - len(regime_missing_signal_tickers)}/"
                f"{len(regime_required_tickers)}"
            ),
            "regime_missing_signal_tickers": list(regime_missing_signal_tickers),
            "latest_notification": latest_notification_timestamp(config.database_path)
            if "notification_events" in database_status.existing_tables
            else None,
            "latest_intraday_cycle_status": latest_intraday_cycle.status
            if latest_intraday_cycle
            else None,
            "latest_intraday_cycle_started_at": latest_intraday_cycle.started_at
            if latest_intraday_cycle
            else None,
            "intraday_health_status": current_intraday_health.status,
            "intraday_market_session": current_intraday_health.market_session,
            "intraday_regular_market_hours": (
                current_intraday_health.regular_market_hours
            ),
            "intraday_health_blockers": list(current_intraday_health.blockers),
            "intraday_health_warnings": list(current_intraday_health.warnings),
            "intraday_health_notes": list(current_intraday_health.notes),
            "intraday_quote_age_seconds": current_intraday_health.quote_age_seconds,
            "intraday_cycle_age_seconds": current_intraday_health.intraday_cycle_age_seconds,
            "oldest_pending_notification_age_seconds": (
                current_intraday_health.oldest_pending_notification_age_seconds
            ),
            "preferred_intraday_heartbeat_command": (
                current_intraday_health.heartbeat_command
            ),
            "scheduler_reconciliation_status": scheduler_audit_result.status,
            "tom_loop_status": loop_snapshot.status,
            "tom_loop_health": loop_snapshot.health_status,
            "tom_loop_heartbeat_age_seconds": loop_snapshot.heartbeat_age_seconds,
            "tom_loop_blockers": list(loop_snapshot.stale_blockers),
            "tom_loop_recovery_status": loop_snapshot.recovery_status,
            "tom_loop_recommended_actions": list(loop_snapshot.recommended_actions),
            "tom_loop_recovery_notes": list(loop_snapshot.recovery_notes),
            "tom_loop_clear_stale_lock_command": loop_snapshot.clear_stale_lock_command,
            "tom_loop_start_command": loop_snapshot.recommended_command,
            "tom_loop_run_once_command": loop_snapshot.run_once_command,
            "actual_heartbeat_command": (
                heartbeat_job.actual_command if heartbeat_job else None
            ),
            "scheduler_warnings": list(scheduler_warning_codes),
            "latest_notification_delivery": latest_notification_delivery_timestamp(
                config.database_path
            )
            if "notification_deliveries" in database_status.existing_tables
            else None,
            "notification_delivery_rows": count_rows_by_table(
                config.database_path,
                "notification_deliveries",
            )
            if "notification_deliveries" in database_status.existing_tables
            else 0,
            "failed_notification_deliveries": notification_delivery_count(
                config.database_path,
                status="failed",
            )
            if "notification_deliveries" in database_status.existing_tables
            else 0,
            "latest_signal_date": latest_signal_date(config.database_path)
            if "signals" in database_status.existing_tables
            else None,
            "latest_signal_validation_date": latest_signal_outcome_date(
                config.database_path
            )
            if "signal_outcomes" in database_status.existing_tables
            else None,
            "latest_revision_aggregate_date": latest_analyst_revision_aggregate_date(
                config.database_path
            )
            if "analyst_revision_aggregates" in database_status.existing_tables
            else None,
            "latest_news_catalyst_aggregate_date": latest_news_catalyst_aggregate_date(
                config.database_path
            )
            if "news_catalyst_aggregates" in database_status.existing_tables
            else None,
            "revision_evidence_decision": revision_evidence.decision,
            "revision_source_backed_ticker_count": (
                revision_source_status.source_backed_ticker_count
            ),
            "revision_source_snapshot_rows": (
                revision_source_status.source_snapshot_count
            ),
            "revision_aggregate_rows": revision_source_status.aggregate_count,
            "news_catalyst_source_backed_ticker_count": (
                news_catalyst_source_status.source_backed_ticker_count
            ),
            "news_catalyst_provider_numeric_ticker_count": (
                news_catalyst_source_status.provider_numeric_ticker_count
            ),
            "news_catalyst_text_derived_ticker_count": (
                news_catalyst_source_status.text_derived_ticker_count
            ),
            "news_catalyst_total_numeric_ticker_count": (
                news_catalyst_source_status.total_numeric_ticker_count
            ),
            "news_catalyst_missing_source_ticker_count": len(
                news_catalyst_source_status.missing_source_tickers
            ),
            "news_catalyst_missing_numeric_ticker_count": len(
                news_catalyst_source_status.missing_numeric_tickers
            ),
            "news_catalyst_provider_native_upgrade_ticker_count": len(
                news_catalyst_source_status.provider_native_upgrade_tickers
            ),
            "news_catalyst_latest_provider_native_source_date": (
                news_catalyst_source_status.latest_provider_native_source_date
            ),
            "news_catalyst_provider_native_rejected_row_count": (
                news_catalyst_source_status.provider_native_rejected_row_count
            ),
            "news_catalyst_provider_native_rejected_tickers": list(
                news_catalyst_source_status.provider_native_rejected_tickers
            ),
            "news_catalyst_backfill_valid_row_count": (
                news_catalyst_upgrade_preview.validation.valid_row_count
            ),
            "news_catalyst_backfill_blank_placeholder_count": (
                news_catalyst_upgrade_preview.validation.blank_placeholder_count
            ),
            "news_catalyst_backfill_invalid_row_count": (
                news_catalyst_upgrade_preview.validation.invalid_row_count
            ),
            "news_catalyst_projected_provider_native_ticker_count": (
                news_catalyst_upgrade_preview.projected_provider_native_ticker_count
            ),
            "news_catalyst_provider_upgrade_still_blocked_tickers": list(
                news_catalyst_upgrade_preview.still_blocked_tickers
            ),
            "news_catalyst_backfill_apply_ready": (
                news_catalyst_backfill_apply_status.backfill_apply_ready
            ),
            "news_catalyst_valid_upgrade_tickers": list(
                news_catalyst_backfill_apply_status.valid_upgrade_tickers
            ),
            "news_catalyst_projected_upgrade_delta": (
                news_catalyst_backfill_apply_status.projected_upgrade_delta
            ),
            "news_catalyst_blocked_apply_reason": (
                news_catalyst_backfill_apply_status.blocked_apply_reason
            ),
            "news_catalyst_provider_upgrade_status": (
                news_catalyst_upgrade_status.status
            ),
            "news_catalyst_provider_upgrade_blockers": list(
                news_catalyst_upgrade_status.provider_blockers
            ),
            "news_catalyst_provider_smoke_test_command": (
                "python -m target_opportunity_monitor "
                "test-news-catalyst-provider --provider all --ticker AAPL"
            ),
            "news_catalyst_provider_native_upgrade_tickers": list(
                news_catalyst_source_status.provider_native_upgrade_tickers
            ),
            "news_catalyst_coverage_plan_tickers": list(
                news_catalyst_plan.planned_tickers
            ),
            "news_catalyst_coverage_queue_tickers": list(
                news_catalyst_plan.queue_template_tickers
            ),
            "news_catalyst_coverage_queue_stale": (
                news_catalyst_plan.queue_template_stale
            ),
            "news_catalyst_missing_queue_stale": (
                news_catalyst_plan.missing_queue_template_stale
            ),
            "news_catalyst_provider_upgrade_queue_stale": (
                news_catalyst_plan.provider_upgrade_queue_template_stale
            ),
            "news_catalyst_provider_warning_summary": list(
                news_catalyst_plan.provider_warning_summary
            ),
            "news_catalyst_source_snapshot_rows": (
                news_catalyst_source_status.source_snapshot_count
            ),
            "news_catalyst_provider_numeric_snapshot_rows": (
                news_catalyst_source_status.provider_numeric_snapshot_count
            ),
            "news_catalyst_text_derived_snapshot_rows": (
                news_catalyst_source_status.text_derived_snapshot_count
            ),
            "news_catalyst_aggregate_rows": news_catalyst_source_status.aggregate_count,
            "insider_activity_source_rows": count_rows_by_table(
                config.database_path,
                "insider_transaction_source_snapshots",
            )
            if "insider_transaction_source_snapshots" in database_status.existing_tables
            else 0,
            "latest_insider_activity_source_date": latest_insider_transaction_source_date(
                config.database_path
            )
            if "insider_transaction_source_snapshots" in database_status.existing_tables
            else None,
            "insider_activity_source_covered_ticker_count": (
                insider_source_status.covered_ticker_count
            ),
            "insider_activity_source_backed_ticker_count": (
                insider_source_status.source_backed_ticker_count
            ),
            "insider_activity_source_active_equity_count": (
                insider_source_status.active_equity_count
            ),
            "latest_insider_activity_successful_fetch_date": (
                insider_source_status.latest_successful_fetch_date
            ),
            "insider_activity_sec_rate_limited_ticker_count": len(
                insider_source_status.sec_rate_limited_tickers
            ),
            "short_interest_source_rows": count_rows_by_table(
                config.database_path,
                "short_interest_source_snapshots",
            )
            if "short_interest_source_snapshots" in database_status.existing_tables
            else 0,
            "latest_short_interest_settlement_date": latest_short_interest_settlement_date(
                config.database_path
            )
            if "short_interest_source_snapshots" in database_status.existing_tables
            else None,
            "option_chain_rows": count_rows_by_table(
                config.database_path,
                "option_chain_snapshots",
            )
            if "option_chain_snapshots" in database_status.existing_tables
            else 0,
            "option_chain_source": config.options_chain_source,
            "option_chain_cache_dir": str(config.options_chain_cache_dir),
            "option_chain_source_exports_dir": str(config.options_chain_source_exports_dir),
            "option_provider_readiness": option_provider.readiness_status,
            "option_provider_blocked_reason": option_provider.blocked_reason,
            "option_ibapi_status": option_provider.ibapi_status,
            "option_activation_status": option_activation.activation_status,
            "option_activation_blocked_reason": option_activation.blocked_reason,
            "minimum_option_chain_coverage": option_activation.minimum_option_chain_coverage,
            "minimum_option_review_count": option_activation.minimum_option_review_count,
            "ibapi_repair_needed": option_activation.ibapi_repair_needed,
            "option_provider_cache_file_count": option_provider.cache_file_count,
            "latest_option_provider_cache_timestamp": option_provider.latest_cache_timestamp,
            "option_chain_fetch_universe_ticker_count": len(option_fetch_tickers),
            "option_chain_effective_fetch_universe_ticker_count": (
                option_coverage_plan.effective_fetch_universe_ticker_count
            ),
            "option_chain_missing_tickers": list(option_chain_missing_tickers),
            "option_chain_raw_missing_tickers": list(option_coverage_plan.raw_missing_tickers),
            "option_chain_non_actionable_tickers": list(
                option_coverage_plan.non_actionable_tickers
            ),
            "option_chain_availability_statuses": [
                asdict(status) for status in option_chain_availability
            ],
            "option_chain_availability_summary": format_option_chain_availability(
                option_chain_availability
            ),
            "option_chain_coverage_status": option_coverage_plan.coverage_status,
            "option_chain_coverage_count": option_coverage_plan.effective_coverage_count,
            "option_chain_raw_coverage_count": option_coverage_plan.raw_coverage_count,
            "option_chain_prioritized_missing_tickers": list(
                option_coverage_plan.prioritized_missing_tickers
            ),
            "option_chain_valid_backfill_tickers": list(
                option_coverage_plan.valid_backfill_tickers
            ),
            "option_chain_projected_coverage_count": (
                f"{option_coverage_plan.projected_loaded_ticker_count}/"
                f"{option_coverage_plan.fetch_universe_ticker_count}"
            ),
            "option_chain_coverage_apply_ready": option_coverage_plan.apply_ready,
            "option_chain_coverage_blocked_reason": option_coverage_plan.blocked_reason,
            "option_chain_coverage_provider_blocked_reason": (
                option_coverage_plan.provider_blocked_reason
            ),
            "option_chain_non_actionable_valid_decisions": (
                option_coverage_plan.non_actionable_valid_decision_count
            ),
            "option_chain_non_actionable_invalid_decisions": (
                option_coverage_plan.non_actionable_invalid_decision_count
            ),
            "option_chain_non_actionable_blank_placeholders": (
                option_coverage_plan.non_actionable_blank_placeholder_count
            ),
            "option_chain_coverage_notes": list(option_coverage_plan.notes),
            "option_backfill_valid_rows": option_backfill_status.valid_row_count,
            "option_backfill_blank_placeholders": option_backfill_status.blank_placeholder_count,
            "option_backfill_invalid_rows": option_backfill_status.invalid_row_count,
            "option_backfill_apply_ready": option_backfill_status.apply_ready,
            "option_backfill_blocked_reason": option_backfill_status.blocked_reason,
            "option_minimum_projected_chain_coverage_count": (
                option_backfill_status.minimum_projected_loaded_ticker_count
            ),
            "option_minimum_ticker_count": option_backfill_status.minimum_ticker_count,
            "option_projected_chain_coverage_count": (
                option_backfill_status.projected_loaded_ticker_count
            ),
            "option_fetch_universe_count": option_backfill_status.fetch_universe_ticker_count,
            "option_income_review_rows": count_rows_by_table(
                config.database_path,
                "option_income_reviews",
            )
            if "option_income_reviews" in database_status.existing_tables
            else 0,
            "option_risk_review_rows": count_rows_by_table(
                config.database_path,
                "option_risk_reviews",
            )
            if "option_risk_reviews" in database_status.existing_tables
            else 0,
            "option_review_outcome_rows": count_rows_by_table(
                config.database_path,
                "option_review_outcomes",
            )
            if "option_review_outcomes" in database_status.existing_tables
            else 0,
            "option_position_ledger_rows": count_rows_by_table(
                config.database_path,
                "option_position_ledger",
            )
            if "option_position_ledger" in database_status.existing_tables
            else 0,
            "option_position_lifecycle_review_rows": count_rows_by_table(
                config.database_path,
                "option_position_lifecycle_reviews",
            )
            if "option_position_lifecycle_reviews" in database_status.existing_tables
            else 0,
            "option_risk_category_counts": option_risk_category_counts,
            "option_outcome_status_counts": option_outcome_status_counts,
            "option_lifecycle_status_counts": option_lifecycle_status_counts,
            "account_context_activation_status": account_context_activation_status,
            "account_context_blockers": account_context_blockers,
            "account_portfolio_position_rows": account_portfolio_position_rows,
            "account_portfolio_cash_rows": account_portfolio_cash_rows,
            "account_option_position_rows": account_option_position_rows,
            "account_option_lifecycle_rows": account_option_lifecycle_rows,
            "account_option_position_readiness_status": (
                option_position_diagnostics.readiness_status
            ),
            "account_option_valid_backfill_rows": (
                option_position_diagnostics.valid_option_position_rows
            ),
            "account_option_invalid_backfill_rows": (
                option_position_diagnostics.invalid_option_position_rows
            ),
            "account_option_blank_backfill_rows": (
                option_position_diagnostics.blank_option_position_rows
            ),
            "account_option_projected_position_rows": (
                option_position_diagnostics.projected_option_position_rows
            ),
            "account_option_projected_lifecycle_rows": (
                option_position_diagnostics.projected_option_lifecycle_rows
            ),
            "account_option_readiness_blockers": list(
                option_position_diagnostics.blockers
            ),
            "account_option_recommended_actions": list(
                option_position_diagnostics.recommended_actions
            ),
            "account_option_risk_missing_portfolio_context_rows": (
                account_missing_portfolio_context_rows
            ),
            "option_position_ticker_count": sum(
                1 for status in option_position_rows if status.position_count
            ),
            "latest_option_chain_snapshot": latest_option_chain_snapshot_timestamp(
                config.database_path
            )
            if "option_chain_snapshots" in database_status.existing_tables
            else None,
            "latest_option_income_review": latest_option_income_review_date(
                config.database_path
            )
            if "option_income_reviews" in database_status.existing_tables
            else None,
            "latest_option_risk_review": latest_option_risk_review_date(
                config.database_path
            )
            if "option_risk_reviews" in database_status.existing_tables
            else None,
            "latest_option_outcome": latest_option_review_outcome_date(
                config.database_path
            )
            if "option_review_outcomes" in database_status.existing_tables
            else None,
            "latest_option_position_open_date": latest_option_position_open_date(
                config.database_path
            )
            if "option_position_ledger" in database_status.existing_tables
            else None,
            "latest_option_lifecycle_review": latest_option_position_lifecycle_review_date(
                config.database_path
            )
            if "option_position_lifecycle_reviews" in database_status.existing_tables
            else None,
            "short_interest_source_backed_ticker_count": (
                short_interest_source_status.source_backed_ticker_count
            ),
            "short_interest_source_active_equity_count": (
                short_interest_source_status.active_equity_count
            ),
            "short_interest_missing_source_tickers": list(
                short_interest_source_status.missing_source_tickers
            ),
            "short_interest_stale_source_tickers": list(
                short_interest_source_status.stale_source_tickers
            ),
            "short_interest_backfill_valid_rows": (
                short_interest_backfill_status.valid_row_count
            ),
            "short_interest_backfill_blank_placeholders": (
                short_interest_backfill_status.blank_placeholder_count
            ),
            "short_interest_backfill_invalid_rows": (
                short_interest_backfill_status.invalid_row_count
            ),
            "short_interest_projected_source_coverage_count": (
                short_interest_backfill_status.projected_source_backed_count
            ),
            "short_interest_backfill_apply_ready": (
                short_interest_backfill_status.apply_ready
            ),
            "short_interest_valid_import_tickers": list(
                short_interest_backfill_status.valid_tickers
            ),
            "short_interest_blocked_import_reason": (
                short_interest_backfill_status.blocked_import_reason
            ),
            "short_interest_provider_export_valid_rows": (
                short_interest_provider.provider_export_valid_row_count
            ),
            "short_interest_provider_export_tickers": list(
                short_interest_provider.provider_export_tickers
            ),
            "short_interest_provider_order": list(short_interest_provider.provider_order),
            "short_interest_fetchable_providers": list(
                short_interest_provider.fetchable_providers
            ),
            "short_interest_manual_only_providers": list(
                short_interest_provider.manual_only_providers
            ),
            "short_interest_provider_cache_files": (
                short_interest_provider.cache_file_count
            ),
            "latest_short_interest_provider_cache_timestamp": (
                short_interest_provider.latest_cache_timestamp
            ),
            "short_interest_provider_warnings": list(short_interest_provider.warnings),
            "short_interest_missing_coverage_tickers": list(
                short_interest_missing_plan.missing_tickers
            ),
            "short_interest_valid_missing_row_tickers": list(
                short_interest_missing_plan.valid_missing_tickers
            ),
            "short_interest_provider_diagnostic_status": [
                f"{item.ticker}:{item.classification}"
                for item in short_interest_missing_plan.diagnostics
            ],
            "short_interest_missing_provider_template": str(
                short_interest_missing_plan.template_path
            ),
            "short_interest_missing_coverage_blocked_apply_reason": (
                short_interest_missing_plan.blocked_apply_reason
            ),
            "trader_commentary_raw_rows": count_rows_by_table(
                config.database_path,
                "trader_commentary_raw",
            )
            if "trader_commentary_raw" in database_status.existing_tables
            else 0,
            "trader_commentary_claim_rows": count_rows_by_table(
                config.database_path,
                "trader_commentary_claims",
            )
            if "trader_commentary_claims" in database_status.existing_tables
            else 0,
            "trader_commentary_outcome_rows": count_rows_by_table(
                config.database_path,
                "trader_commentary_claim_outcomes",
            )
            if "trader_commentary_claim_outcomes" in database_status.existing_tables
            else 0,
            "trader_commentary_onboarding_candidate_count": (
                commentary_onboarding_plan.onboardable_count
            ),
            "trader_commentary_unmapped_instrument_count": (
                commentary_onboarding_plan.unmapped_count
            ),
            "trader_commentary_alias_count": commentary_onboarding_plan.alias_count,
            "trader_commentary_label_disposition_count": (
                commentary_onboarding_plan.label_disposition_count
            ),
            "trader_commentary_intentionally_unresolved_label_count": (
                commentary_onboarding_plan.intentionally_unresolved_count
            ),
            "trader_commentary_ignored_non_instrument_label_count": (
                commentary_onboarding_plan.ignored_non_instrument_count
            ),
            "scoreable_asset_count": count_scoreable_assets(config.database_path),
            "reference_asset_count": count_reference_assets(config.database_path),
            "trader_commentary_browser_capture_run_rows": count_rows_by_table(
                config.database_path,
                "trader_commentary_browser_capture_runs",
            )
            if "trader_commentary_browser_capture_runs" in database_status.existing_tables
            else 0,
            "trader_commentary_browser_capture_item_rows": count_rows_by_table(
                config.database_path,
                "trader_commentary_browser_capture_items",
            )
            if "trader_commentary_browser_capture_items" in database_status.existing_tables
            else 0,
            "latest_trader_commentary_browser_capture_timestamp": (
                latest_trader_commentary_browser_capture_timestamp(config.database_path)
            )
            if "trader_commentary_browser_capture_runs" in database_status.existing_tables
            else None,
            "trader_commentary_browser_capture_dir_exists": (
                config.trader_commentary_browser_capture_dir.exists()
            ),
            "trader_commentary_discord_capture_run_rows": count_rows_by_table(
                config.database_path,
                "trader_commentary_discord_capture_runs",
            )
            if "trader_commentary_discord_capture_runs" in database_status.existing_tables
            else 0,
            "trader_commentary_discord_capture_item_rows": count_rows_by_table(
                config.database_path,
                "trader_commentary_discord_capture_items",
            )
            if "trader_commentary_discord_capture_items" in database_status.existing_tables
            else 0,
            "latest_trader_commentary_discord_capture_timestamp": (
                latest_trader_commentary_discord_capture_timestamp(config.database_path)
            )
            if "trader_commentary_discord_capture_runs" in database_status.existing_tables
            else None,
            "trader_commentary_discord_capture_dir_exists": (
                config.trader_commentary_discord_capture_dir.exists()
            ),
            "trader_commentary_discord_capture_enabled": (
                config.commentary_discord_capture_enabled
            ),
            "latest_trader_commentary_capture_date": (
                latest_trader_commentary_capture_date(config.database_path)
            )
            if "trader_commentary_raw" in database_status.existing_tables
            else None,
            "latest_trader_commentary_claim_date": (
                latest_trader_commentary_claim_date(config.database_path)
            )
            if "trader_commentary_claims" in database_status.existing_tables
            else None,
            "latest_trader_commentary_validation_date": (
                latest_trader_commentary_outcome_date(config.database_path)
            )
            if "trader_commentary_claim_outcomes" in database_status.existing_tables
            else None,
            "trader_commentary_claim_ticker_count": len(trader_commentary_status),
            "trader_commentary_validation_ticker_count": sum(
                1 for status in trader_commentary_status if status.validation_count
            ),
            "trader_commentary_warning_tickers": trader_commentary_warning_tickers,
            "latest_alert_timestamp": latest_alert_timestamp(config.database_path)
            if "alerts" in database_status.existing_tables
            else None,
            "latest_outcome_date": latest_outcome_date(config.database_path)
            if "alert_outcomes" in database_status.existing_tables
            else None,
            "latest_portfolio_review_date": latest_portfolio_review_date(
                config.database_path
            )
            if "portfolio_reviews" in database_status.existing_tables
            else None,
            "latest_pipeline_run": asdict(latest_pipeline) if latest_pipeline else None,
        },
    }


def build_dashboard_data(config: AppConfig) -> dict[str, object]:
    return _build_dashboard_data(config)


def _json_script(data: dict[str, object]) -> str:
    return json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")


def _dashboard_html(data: dict[str, object]) -> str:
    dashboard_json = _json_script(data)
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Target Opportunity Monitor</title>
<style>
:root {{
  --bg: #f5f7fa;
  --surface: #ffffff;
  --surface-2: #eef2f6;
  --text: #19202a;
  --muted: #647084;
  --border: #d8dee8;
  --blue: #2f6fdf;
  --green: #168558;
  --amber: #a86700;
  --red: #b42318;
  --ink: #0f1720;
}}
* {{ box-sizing: border-box; }}
body {{
  margin: 0;
  background: var(--bg);
  color: var(--text);
  font-family: "Segoe UI", Arial, sans-serif;
  letter-spacing: 0;
}}
button, select {{
  font: inherit;
  letter-spacing: 0;
}}
.app-shell {{
  display: grid;
  grid-template-columns: 220px minmax(0, 1fr);
  min-height: 100vh;
}}
.sidebar {{
  background: var(--ink);
  color: #f8fafc;
  padding: 18px 14px;
  position: sticky;
  top: 0;
  height: 100vh;
}}
.brand {{
  font-size: 16px;
  font-weight: 700;
  margin: 0 0 18px;
}}
.nav {{
  display: grid;
  gap: 6px;
}}
.nav button {{
  border: 1px solid rgba(255,255,255,.12);
  background: transparent;
  color: #dfe7f3;
  border-radius: 6px;
  min-height: 36px;
  padding: 8px 10px;
  text-align: left;
  cursor: pointer;
}}
.nav button.active {{
  background: #ffffff;
  color: var(--ink);
}}
.content {{
  padding: 20px;
  min-width: 0;
}}
.topbar {{
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: flex-start;
  margin-bottom: 16px;
}}
h1 {{
  font-size: 24px;
  margin: 0 0 4px;
}}
.stamp {{
  color: var(--muted);
  font-size: 13px;
}}
.ticker-select {{
  min-width: 160px;
  min-height: 36px;
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 6px 8px;
  background: #fff;
}}
.metrics {{
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
  margin-bottom: 16px;
}}
.metric {{
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 12px;
  min-height: 84px;
}}
.metric .label {{
  color: var(--muted);
  font-size: 12px;
  text-transform: uppercase;
}}
.metric .value {{
  font-size: 24px;
  font-weight: 700;
  margin-top: 8px;
}}
.grid {{
  display: grid;
  grid-template-columns: minmax(0, 1.25fr) minmax(320px, .75fr);
  gap: 14px;
}}
section {{
  display: none;
}}
section.active {{
  display: block;
}}
.panel {{
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 14px;
  margin-bottom: 14px;
  min-width: 0;
}}
.panel h2 {{
  margin: 0 0 12px;
  font-size: 16px;
}}
.panel h3 {{
  margin: 0 0 8px;
  font-size: 14px;
}}
.table-wrap {{
  overflow-x: auto;
  border: 1px solid var(--border);
  border-radius: 8px;
}}
table {{
  width: 100%;
  border-collapse: collapse;
  min-width: 760px;
  background: #fff;
}}
th, td {{
  padding: 9px 10px;
  border-bottom: 1px solid var(--border);
  text-align: left;
  vertical-align: top;
  font-size: 13px;
  white-space: nowrap;
}}
th {{
  background: var(--surface-2);
  color: #394456;
  font-weight: 700;
  position: sticky;
  top: 0;
}}
th button {{
  border: 0;
  background: transparent;
  color: inherit;
  padding: 0;
  cursor: pointer;
  font-weight: 700;
}}
td.reason {{
  white-space: normal;
  min-width: 280px;
}}
.badge {{
  display: inline-block;
  border-radius: 999px;
  padding: 2px 8px;
  font-size: 12px;
  border: 1px solid var(--border);
  background: var(--surface-2);
}}
.high, .bullish_divergence {{
  color: var(--green);
  border-color: rgba(22,133,88,.35);
  background: rgba(22,133,88,.08);
}}
.medium, .watch_only_gap, .pending {{
  color: var(--amber);
  border-color: rgba(168,103,0,.35);
  background: rgba(168,103,0,.08);
}}
.risk_warning, .bearish_overvaluation {{
  color: var(--red);
  border-color: rgba(180,35,24,.35);
  background: rgba(180,35,24,.08);
}}
.closed, .no_alert, .skipped {{
  color: var(--muted);
}}
.detail-grid {{
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
}}
.kv {{
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 10px;
  background: #fff;
  min-height: 68px;
}}
.kv span {{
  display: block;
  color: var(--muted);
  font-size: 12px;
}}
.kv strong {{
  display: block;
  margin-top: 5px;
  font-size: 15px;
}}
.chart {{
  width: 100%;
  height: 300px;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: #fff;
}}
.score-bars {{
  display: grid;
  gap: 9px;
}}
.bar-row {{
  display: grid;
  grid-template-columns: 120px 1fr 48px;
  gap: 8px;
  align-items: center;
  font-size: 13px;
}}
.bar {{
  height: 10px;
  background: var(--surface-2);
  border-radius: 999px;
  overflow: hidden;
}}
.bar-fill {{
  height: 100%;
  background: var(--blue);
}}
.gated {{
  border: 1px dashed var(--border);
  background: #fff7e6;
  color: #6b4b00;
}}
@media (max-width: 900px) {{
  .app-shell {{ grid-template-columns: 1fr; }}
  .sidebar {{ position: static; height: auto; }}
  .nav {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
  .metrics {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
  .grid, .detail-grid {{ grid-template-columns: 1fr; }}
  .topbar {{ flex-direction: column; }}
}}
</style>
</head>
<body>
<div class="app-shell">
  <aside class="sidebar">
    <div class="brand">Target Opportunity Monitor</div>
    <nav class="nav" aria-label="Dashboard sections">
      <button class="active" data-section="overview">Overview</button>
      <button data-section="ranking">Ranking</button>
      <button data-section="detail">Ticker Detail</button>
      <button data-section="history">History</button>
      <button data-section="health">Health</button>
    </nav>
  </aside>
  <main class="content">
    <div class="topbar">
      <div>
        <h1>Daily Dashboard</h1>
        <div class="stamp" id="generatedAt"></div>
      </div>
      <select class="ticker-select" id="tickerSelect" aria-label="Ticker"></select>
    </div>
    <div class="metrics" id="metrics"></div>

    <section id="overview" class="active">
      <div class="grid">
        <div class="panel">
          <h2>Daily Alerts</h2>
          <div class="table-wrap" id="alertsTable"></div>
        </div>
        <div>
          <div class="panel">
            <h2>Selected Ticker</h2>
            <div id="summaryPanel"></div>
          </div>
          <div class="panel">
            <h2>Portfolio Review</h2>
            <div id="portfolioPanel"></div>
          </div>
          <div class="panel">
            <h2>Advanced Signals</h2>
            <div id="advancedSignalsPanel"></div>
          </div>
        </div>
      </div>
    </section>

    <section id="ranking">
      <div class="panel">
        <h2>Watchlist Ranking</h2>
        <div class="table-wrap" id="rankingTable"></div>
      </div>
    </section>

    <section id="detail">
      <div class="grid">
        <div class="panel">
          <h2>Price vs Target</h2>
          <div id="chart" class="chart"></div>
        </div>
        <div class="panel">
          <h2>Score Breakdown</h2>
          <div id="scoreBars" class="score-bars"></div>
        </div>
      </div>
      <div class="panel">
        <h2>Ticker Detail</h2>
        <div id="tickerDetail"></div>
      </div>
    </section>

    <section id="history">
      <div class="panel">
        <h2>Alert History</h2>
        <div class="table-wrap" id="alertHistory"></div>
      </div>
      <div class="panel">
        <h2>Outcome Status</h2>
        <div class="table-wrap" id="outcomeTable"></div>
      </div>
    </section>

    <section id="health">
      <div class="grid">
        <div class="panel">
          <h2>Data Health</h2>
          <div class="table-wrap" id="dataHealth"></div>
        </div>
        <div class="panel">
          <h2>Model Health</h2>
          <div id="modelHealth"></div>
        </div>
      </div>
    </section>
  </main>
</div>
<script id="tom-dashboard-data" type="application/json">{dashboard_json}</script>
<script>
const DATA = JSON.parse(document.getElementById('tom-dashboard-data').textContent);
let currentTicker = DATA.rows[0]?.ticker || '';
let rankingSort = {{ key: 'opportunity_score', direction: -1 }};

const fmt = {{
  number(value, digits = 2) {{
    return value === null || value === undefined || value === '' ? '' : Number(value).toFixed(digits);
  }},
  percent(value) {{
    return value === null || value === undefined || value === '' ? '' : (Number(value) * 100).toFixed(2) + '%';
  }},
  money(value) {{
    return value === null || value === undefined || value === '' ? '' : Number(value).toFixed(2);
  }},
  text(value) {{
    return value === null || value === undefined || value === '' ? '' : String(value);
  }},
  flag(value) {{
    if (value === null || value === undefined || value === '') return '';
    return value ? 'true' : 'false';
  }}
}};

function escapeHtml(value) {{
  return fmt.text(value)
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;');
}}

function badge(value) {{
  const text = escapeHtml(value || '');
  const cls = text.replaceAll(' ', '_').replaceAll(',', '').toLowerCase();
  return text ? `<span class="badge ${{cls}}">${{text}}</span>` : '';
}}

function selectedRow() {{
  return DATA.rows.find(row => row.ticker === currentTicker) || DATA.rows[0] || {{}};
}}

function activeAlerts() {{
  return DATA.rows.filter(row =>
    row.status === 'open' &&
    !['no_alert', 'skipped', 'not_evaluated'].includes(row.alert_type)
  );
}}

function renderMetrics() {{
  const rows = DATA.rows;
  const active = activeAlerts();
  const pending = rows.filter(row => row.outcome_status === 'pending').length;
  const etfEvaluated = rows.filter(row => row.asset_type === 'etf' && row.alert_type !== 'not_evaluated').length;
  const held = rows.filter(row => row.held_flag).length;
  const metrics = [
    ['Active Alerts', active.length],
    ['Watchlist', rows.length],
    ['Pending Outcomes', pending],
    ['ETF Evaluated', etfEvaluated],
    ['Held Rows', held]
  ];
  document.getElementById('metrics').innerHTML = metrics.map(([label, value]) => `
    <div class="metric"><div class="label">${{label}}</div><div class="value">${{value}}</div></div>
  `).join('');
}}

function renderTickerSelect() {{
  const select = document.getElementById('tickerSelect');
  select.innerHTML = DATA.rows.map(row => `<option value="${{escapeHtml(row.ticker)}}">${{escapeHtml(row.ticker)}}</option>`).join('');
  select.value = currentTicker;
  select.addEventListener('change', event => {{
    currentTicker = event.target.value;
    renderTickerViews();
  }});
}}

function table(headers, rows) {{
  return `<table><thead><tr>${{headers.map(header => `<th>${{header}}</th>`).join('')}}</tr></thead><tbody>${{rows.join('')}}</tbody></table>`;
}}

function renderAlertsTable() {{
  const rows = DATA.rows
    .filter(row => row.alert_type && row.alert_type !== 'not_evaluated')
    .map(row => `<tr>
      <td>${{escapeHtml(row.ticker)}}</td>
      <td>${{escapeHtml(row.asset_type)}}</td>
      <td>${{badge(row.alert_type)}}</td>
      <td>${{badge(row.priority)}}</td>
      <td>${{fmt.money(row.current_price)}}</td>
      <td>${{fmt.money(row.target_low)}} / ${{fmt.money(row.base_target)}} / ${{fmt.money(row.target_high)}}</td>
      <td>${{fmt.percent(row.valuation_gap)}}</td>
      <td>${{fmt.number(row.opportunity_score)}}</td>
      <td class="reason">${{escapeHtml(row.main_reasons || row.reason_codes)}}</td>
    </tr>`);
  document.getElementById('alertsTable').innerHTML = table(
    ['Ticker', 'Type', 'Alert', 'Priority', 'Price', 'Target Range', 'Gap', 'Opportunity', 'Reason'],
    rows
  );
}}

function renderRankingTable() {{
  const sorted = [...DATA.rows].sort((left, right) => {{
    const a = left[rankingSort.key];
    const b = right[rankingSort.key];
    const av = a === null || a === undefined ? -Infinity : Number(a);
    const bv = b === null || b === undefined ? -Infinity : Number(b);
    return (av - bv) * rankingSort.direction;
  }});
  const header = ['ticker', 'asset_type', 'current_price', 'range_state', 'moving_average_state', 'price_location_state', 'regime_state', 'valuation_gap', 'opportunity_score', 'revision_score', 'news_catalyst_score', 'insider_activity_score', 'short_interest_score', 'option_annualized_yield', 'option_lifecycle_status', 'option_lifecycle_realized_pl', 'option_lifecycle_open_pl_proxy', 'confidence_score', 'risk_score', 'position_weight', 'portfolio_review_category', 'option_review_category', 'outcome_status'];
  const rows = sorted.map(row => `<tr>
    <td>${{escapeHtml(row.ticker)}}</td>
    <td>${{escapeHtml(row.asset_type)}}</td>
    <td>${{fmt.money(row.current_price)}}</td>
    <td>${{badge(row.range_state || 'not_evaluated')}}</td>
    <td>${{badge(row.moving_average_state || 'missing')}}</td>
    <td>${{badge(row.price_location_state || 'missing')}}</td>
    <td>${{badge(row.regime_state || 'missing')}}</td>
    <td>${{fmt.percent(row.valuation_gap)}}</td>
    <td>${{fmt.number(row.opportunity_score)}}</td>
    <td>${{fmt.number(row.revision_score)}}</td>
    <td>${{fmt.number(row.news_catalyst_score)}}</td>
    <td>${{fmt.number(row.insider_activity_score)}}</td>
    <td>${{fmt.number(row.short_interest_score)}}</td>
    <td>${{fmt.percent(row.option_annualized_yield)}}</td>
    <td>${{badge(row.option_lifecycle_status || 'none')}}</td>
    <td>${{fmt.money(row.option_lifecycle_realized_pl)}}</td>
    <td>${{fmt.money(row.option_lifecycle_open_pl_proxy)}}</td>
    <td>${{fmt.number(row.confidence_score)}}</td>
    <td>${{fmt.number(row.risk_score)}}</td>
    <td>${{fmt.percent(row.position_weight)}}</td>
    <td>${{badge(row.portfolio_review_category)}}</td>
    <td>${{badge(row.option_review_category || 'none')}}</td>
    <td>${{badge(row.outcome_status || row.alert_type)}}</td>
  </tr>`);
  document.getElementById('rankingTable').innerHTML = `<table><thead><tr>${{header.map(key =>
    `<th><button data-sort="${{key}}">${{key.replaceAll('_', ' ')}}</button></th>`
  ).join('')}}</tr></thead><tbody>${{rows.join('')}}</tbody></table>`;
  document.querySelectorAll('[data-sort]').forEach(button => {{
    button.addEventListener('click', () => {{
      const key = button.dataset.sort;
      rankingSort = {{
        key,
        direction: rankingSort.key === key ? rankingSort.direction * -1 : -1
      }};
      renderRankingTable();
    }});
  }});
}}

function renderSummaryPanel() {{
  const row = selectedRow();
  document.getElementById('summaryPanel').innerHTML = `
    <div class="detail-grid">
      <div class="kv"><span>Alert</span><strong>${{badge(row.alert_type)}}</strong></div>
      <div class="kv"><span>Range State</span><strong>${{badge(row.range_state || 'not_evaluated')}}</strong></div>
      <div class="kv"><span>Price</span><strong>${{fmt.money(row.current_price)}}</strong></div>
      <div class="kv"><span>Target</span><strong>${{fmt.money(row.target_low)}} / ${{fmt.money(row.base_target)}} / ${{fmt.money(row.target_high)}}</strong></div>
      <div class="kv"><span>Range Levels</span><strong>${{fmt.money(row.starter_buy_below || row.nav_watch_discount_below)}} / ${{fmt.money(row.hold_high || row.nav_fair_value)}} / ${{fmt.money(row.trim_above || row.nav_premium_warning_above)}}</strong></div>
      <div class="kv"><span>Support</span><strong>${{fmt.money(row.support_low)}} / ${{fmt.money(row.support_high)}}</strong></div>
      <div class="kv"><span>Resistance</span><strong>${{fmt.money(row.resistance_low)}} / ${{fmt.money(row.resistance_high)}}</strong></div>
      <div class="kv"><span>Technical State</span><strong>${{badge(row.moving_average_state || 'missing')}} ${{badge(row.price_location_state || 'missing')}}</strong></div>
      <div class="kv"><span>Regime</span><strong>${{badge(row.regime_state || 'missing')}}</strong></div>
      <div class="kv"><span>Opportunity</span><strong>${{fmt.number(row.opportunity_score)}}</strong></div>
      <div class="kv"><span>Notification</span><strong>${{badge(row.pending_notification_status || 'none')}}</strong></div>
      <div class="kv"><span>Portfolio</span><strong>${{badge(row.portfolio_review_category || 'none')}}</strong></div>
      <div class="kv"><span>Sell-Put Review</span><strong>${{badge(row.option_review_category || 'none')}}</strong></div>
      <div class="kv"><span>Option Yield</span><strong>${{fmt.percent(row.option_annualized_yield)}}</strong></div>
    </div>
  `;
}}

function renderPortfolioPanel() {{
  const rows = DATA.rows.filter(row => row.portfolio_review_category);
  if (!rows.length) {{
    document.getElementById('portfolioPanel').innerHTML = '<div class="muted">No portfolio reviews yet.</div>';
    return;
  }}
  const selected = selectedRow();
  document.getElementById('portfolioPanel').innerHTML = `
    <div class="detail-grid">
      <div class="kv"><span>Selected Category</span><strong>${{badge(selected.portfolio_review_category || 'none')}}</strong></div>
      <div class="kv"><span>Held</span><strong>${{fmt.flag(selected.held_flag)}}</strong></div>
      <div class="kv"><span>Position Value</span><strong>${{fmt.money(selected.position_value)}}</strong></div>
      <div class="kv"><span>Weight</span><strong>${{fmt.percent(selected.position_weight)}}</strong></div>
      <div class="kv"><span>Max Add</span><strong>${{fmt.money(selected.max_add_value)}}</strong></div>
      <div class="kv"><span>Cash Available</span><strong>${{fmt.money(selected.cash_available)}}</strong></div>
    </div>
    <div class="reason">${{escapeHtml(selected.sizing_guidance || '')}}</div>
  `;
}}

function renderAdvancedSignalsPanel() {{
  const selected = selectedRow();
  const evidence = DATA.revision_evidence || {{}};
  const sourceStatus = DATA.revision_source_status || {{}};
  const newsSourceStatus = DATA.news_catalyst_source_status || {{}};
  const insiderSourceStatus = DATA.insider_source_status || {{}};
  const shortInterestSourceStatus = DATA.short_interest_source_status || {{}};
  const shortInterestProviderStatus = DATA.short_interest_provider_status || {{}};
  document.getElementById('advancedSignalsPanel').innerHTML = `
    <div class="detail-grid">
      <div class="kv"><span>Revision Score</span><strong>${{fmt.number(selected.revision_score)}}</strong></div>
      <div class="kv"><span>Revision Status</span><strong>${{badge(selected.revision_signal_status || 'missing')}}</strong></div>
      <div class="kv"><span>Source Status</span><strong>${{badge(selected.revision_source_status || 'missing')}}</strong></div>
      <div class="kv"><span>Source Count</span><strong>${{fmt.text(selected.revision_source_count || 0)}}</strong></div>
      <div class="kv"><span>Aggregate Confidence</span><strong>${{fmt.number(selected.revision_aggregate_confidence)}}</strong></div>
      <div class="kv"><span>Validation Status</span><strong>${{badge(selected.revision_validation_status || 'missing')}}</strong></div>
      <div class="kv"><span>Evidence Decision</span><strong>${{badge(evidence.decision || selected.revision_evidence_decision || 'unknown')}}</strong></div>
      <div class="kv"><span>Source Coverage</span><strong>${{fmt.text(sourceStatus.source_backed_ticker_count || 0)}} / ${{fmt.text(sourceStatus.active_equity_count || 0)}}</strong></div>
      <div class="kv"><span>20d Hit Rate</span><strong>${{fmt.percent(evidence.hit_rate_20d)}}</strong></div>
      <div class="kv"><span>Source Disagreement</span><strong>${{escapeHtml(selected.revision_source_disagreement)}}</strong></div>
      <div class="kv"><span>News/Catalyst Score</span><strong>${{fmt.number(selected.news_catalyst_score)}}</strong></div>
      <div class="kv"><span>News/Catalyst Status</span><strong>${{badge(selected.news_catalyst_signal_status || 'missing')}}</strong></div>
      <div class="kv"><span>News/Catalyst Source</span><strong>${{badge(selected.news_catalyst_source_status || 'missing')}}</strong></div>
      <div class="kv"><span>News Source Count</span><strong>${{fmt.text(selected.news_catalyst_source_count || 0)}}</strong></div>
      <div class="kv"><span>News Source Type</span><strong>${{badge(selected.news_catalyst_numeric_source_type || 'missing')}}</strong></div>
      <div class="kv"><span>News Aggregate Confidence</span><strong>${{fmt.number(selected.news_catalyst_aggregate_confidence)}}</strong></div>
      <div class="kv"><span>News Source Coverage</span><strong>${{fmt.text(newsSourceStatus.source_backed_ticker_count || 0)}} / ${{fmt.text(newsSourceStatus.active_equity_count || 0)}}</strong></div>
      <div class="kv"><span>Provider Numeric News</span><strong>${{fmt.text(newsSourceStatus.provider_numeric_ticker_count || 0)}} / ${{fmt.text(newsSourceStatus.active_equity_count || 0)}}</strong></div>
      <div class="kv"><span>Text-Derived News</span><strong>${{fmt.text(newsSourceStatus.text_derived_ticker_count || 0)}} / ${{fmt.text(newsSourceStatus.active_equity_count || 0)}}</strong></div>
      <div class="kv"><span>News Missing Sources</span><strong>${{fmt.text(DATA.health.news_catalyst_missing_source_ticker_count || 0)}}</strong></div>
      <div class="kv"><span>News Missing Numeric</span><strong>${{fmt.text(DATA.health.news_catalyst_missing_numeric_ticker_count || 0)}}</strong></div>
      <div class="kv"><span>Provider Upgrade Status</span><strong>${{badge(DATA.health.news_catalyst_provider_upgrade_status || 'unknown')}}</strong></div>
      <div class="kv"><span>Provider Upgrade Needed</span><strong>${{fmt.text(DATA.health.news_catalyst_provider_native_upgrade_ticker_count || 0)}}</strong></div>
      <div class="kv"><span>Latest Provider-Native Date</span><strong>${{escapeHtml(DATA.health.news_catalyst_latest_provider_native_source_date || 'none')}}</strong></div>
      <div class="kv"><span>Rejected Provider-Native Rows</span><strong>${{fmt.text(DATA.health.news_catalyst_provider_native_rejected_row_count || 0)}}</strong></div>
      <div class="kv"><span>Backfill Valid Rows</span><strong>${{fmt.text(DATA.health.news_catalyst_backfill_valid_row_count || 0)}}</strong></div>
      <div class="kv"><span>Backfill Invalid Rows</span><strong>${{fmt.text(DATA.health.news_catalyst_backfill_invalid_row_count || 0)}}</strong></div>
      <div class="kv"><span>Projected Provider-Native</span><strong>${{fmt.text(DATA.health.news_catalyst_projected_provider_native_ticker_count || 0)}} / ${{fmt.text(newsSourceStatus.active_equity_count || 0)}}</strong></div>
      <div class="kv"><span>Still Blocked Provider-Native</span><strong>${{escapeHtml((DATA.health.news_catalyst_provider_upgrade_still_blocked_tickers || []).join(', ') || 'none')}}</strong></div>
      <div class="kv"><span>Backfill Apply Ready</span><strong>${{badge(String(Boolean(DATA.health.news_catalyst_backfill_apply_ready)))}}</strong></div>
      <div class="kv"><span>Valid Upgrade Tickers</span><strong>${{escapeHtml((DATA.health.news_catalyst_valid_upgrade_tickers || []).join(', ') || 'none')}}</strong></div>
      <div class="kv"><span>Projected Upgrade Delta</span><strong>${{fmt.text(DATA.health.news_catalyst_projected_upgrade_delta || 0)}}</strong></div>
      <div class="kv"><span>Blocked Apply Reason</span><strong>${{escapeHtml(DATA.health.news_catalyst_blocked_apply_reason || 'none')}}</strong></div>
      <div class="kv"><span>Provider Upgrade Blockers</span><strong>${{escapeHtml((DATA.health.news_catalyst_provider_upgrade_blockers || []).join(', ') || 'none')}}</strong></div>
      <div class="kv"><span>News Coverage Plan</span><strong>${{escapeHtml((DATA.health.news_catalyst_coverage_plan_tickers || []).join(', ') || 'none')}}</strong></div>
      <div class="kv"><span>News/Catalyst Validation</span><strong>${{badge(selected.news_catalyst_validation_status || 'missing')}}</strong></div>
      <div class="kv"><span>News/Catalyst Warnings</span><strong>${{escapeHtml(selected.news_catalyst_source_warnings || selected.news_catalyst_warnings)}}</strong></div>
      <div class="kv"><span>Insider Activity Score</span><strong>${{fmt.number(selected.insider_activity_score)}}</strong></div>
      <div class="kv"><span>Insider Status</span><strong>${{badge(selected.insider_activity_signal_status || 'missing')}}</strong></div>
      <div class="kv"><span>Insider Source Status</span><strong>${{badge(selected.insider_activity_source_status || 'missing_source')}}</strong></div>
      <div class="kv"><span>Insider Source Coverage</span><strong>${{fmt.text(insiderSourceStatus.covered_ticker_count || 0)}} / ${{fmt.text(insiderSourceStatus.active_equity_count || 0)}}</strong></div>
      <div class="kv"><span>Insider Source Rows</span><strong>${{fmt.text(selected.insider_activity_source_rows || 0)}}</strong></div>
      <div class="kv"><span>Insider Source Date</span><strong>${{escapeHtml(selected.insider_activity_latest_source_date)}}</strong></div>
      <div class="kv"><span>Insider Validation</span><strong>${{badge(selected.insider_activity_validation_status || 'missing')}}</strong></div>
      <div class="kv"><span>Short Interest Score</span><strong>${{fmt.number(selected.short_interest_score)}}</strong></div>
      <div class="kv"><span>Short Interest Status</span><strong>${{badge(selected.short_interest_signal_status || 'missing')}}</strong></div>
      <div class="kv"><span>Short Interest Source</span><strong>${{badge(selected.short_interest_source_status || 'missing_source')}}</strong></div>
      <div class="kv"><span>Short Interest Coverage</span><strong>${{fmt.text(shortInterestSourceStatus.source_backed_ticker_count || 0)}} / ${{fmt.text(shortInterestSourceStatus.active_equity_count || 0)}}</strong></div>
      <div class="kv"><span>Short Interest Provider Export</span><strong>${{fmt.text(shortInterestProviderStatus.provider_export_valid_row_count || 0)}} valid rows</strong></div>
      <div class="kv"><span>Short Interest Provider Cache</span><strong>${{fmt.text(shortInterestProviderStatus.cache_file_count || 0)}} files</strong></div>
      <div class="kv"><span>Percent Float Short</span><strong>${{fmt.percent(selected.short_interest_percent_float)}}</strong></div>
      <div class="kv"><span>Days To Cover</span><strong>${{fmt.number(selected.short_interest_days_to_cover)}}</strong></div>
      <div class="kv"><span>Short Interest Change</span><strong>${{fmt.percent(selected.short_interest_change)}}</strong></div>
      <div class="kv"><span>Short Interest Validation</span><strong>${{badge(selected.short_interest_validation_status || 'missing')}}</strong></div>
      <div class="kv"><span>Benchmark Status</span><strong>${{badge(selected.fundamental_benchmark_status || 'missing')}}</strong></div>
      <div class="kv"><span>Sector Peers</span><strong>${{fmt.text(selected.fundamental_sector_peer_count ?? 0)}}</strong></div>
      <div class="kv"><span>Sector ETF</span><strong>${{escapeHtml(selected.fundamental_sector_benchmark_ticker || 'none')}}</strong></div>
      <div class="kv"><span>Fwd P/E vs Sector</span><strong>${{fmt.number(selected.fundamental_forward_pe)}} / ${{fmt.number(selected.fundamental_sector_forward_pe_median)}}</strong></div>
      <div class="kv"><span>Sector P/E Discount</span><strong>${{fmt.percent(selected.fundamental_sector_forward_pe_discount_pct)}}</strong></div>
      <div class="kv"><span>Sector Percentile</span><strong>${{fmt.number(selected.fundamental_sector_forward_pe_percentile)}}</strong></div>
      <div class="kv"><span>RS vs SPY</span><strong>${{fmt.percent(selected.fundamental_relative_strength_vs_spy)}}</strong></div>
      <div class="kv"><span>RS vs Sector</span><strong>${{fmt.percent(selected.fundamental_relative_strength_vs_sector)}}</strong></div>
      <div class="kv"><span>Benchmark Warnings</span><strong>${{escapeHtml(selected.fundamental_benchmark_warnings || 'none')}}</strong></div>
      <div class="kv"><span>Sell-Put Review</span><strong>${{badge(selected.option_review_category || 'none')}}</strong></div>
      <div class="kv"><span>Option Expiration</span><strong>${{escapeHtml(selected.option_expiration_date || 'none')}}</strong></div>
      <div class="kv"><span>Option Strike</span><strong>${{fmt.money(selected.option_strike)}}</strong></div>
      <div class="kv"><span>Option Premium</span><strong>${{fmt.money(selected.option_mid_premium)}}</strong></div>
      <div class="kv"><span>Option Breakeven</span><strong>${{fmt.money(selected.option_breakeven)}}</strong></div>
      <div class="kv"><span>Option Annualized Yield</span><strong>${{fmt.percent(selected.option_annualized_yield)}}</strong></div>
      <div class="kv"><span>Option Downside Buffer</span><strong>${{fmt.percent(selected.option_downside_buffer_pct)}}</strong></div>
      <div class="kv"><span>Assignment Notional</span><strong>${{fmt.money(selected.option_assignment_notional)}}</strong></div>
      <div class="kv"><span>Option Risk Category</span><strong>${{badge(selected.option_risk_category || 'none')}}</strong></div>
      <div class="kv"><span>Cash Requirement</span><strong>${{fmt.money(selected.option_cash_secured_requirement)}}</strong></div>
      <div class="kv"><span>Scenario P/L -10%</span><strong>${{fmt.money(selected.option_scenario_pl_10pct)}}</strong></div>
      <div class="kv"><span>Max Contracts</span><strong>${{fmt.text(selected.option_max_contracts_advisory ?? 'n/a')}}</strong></div>
      <div class="kv"><span>Option Outcome</span><strong>${{badge(selected.option_outcome_status || 'none')}}</strong></div>
      <div class="kv"><span>Option Lifecycle</span><strong>${{badge(selected.option_lifecycle_status || 'none')}}</strong></div>
      <div class="kv"><span>Realized P/L</span><strong>${{fmt.money(selected.option_lifecycle_realized_pl)}}</strong></div>
      <div class="kv"><span>Open P/L Proxy</span><strong>${{fmt.money(selected.option_lifecycle_open_pl_proxy)}}</strong></div>
      <div class="kv"><span>Lifecycle Assignment</span><strong>${{fmt.money(selected.option_lifecycle_assignment_notional)}}</strong></div>
      <div class="kv"><span>Expiration Result</span><strong>${{badge(selected.option_expiration_status || 'pending')}}</strong></div>
      <div class="kv"><span>Option Return 5d</span><strong>${{fmt.percent(selected.option_return_5d)}}</strong></div>
      <div class="kv"><span>Option Return 20d</span><strong>${{fmt.percent(selected.option_return_20d)}}</strong></div>
      <div class="kv"><span>Option Latest Return</span><strong>${{fmt.percent(selected.option_return_to_latest)}}</strong></div>
      <div class="kv"><span>Above Strike</span><strong>${{fmt.flag(selected.option_above_strike_flag)}}</strong></div>
      <div class="kv"><span>Above Breakeven</span><strong>${{fmt.flag(selected.option_above_breakeven_flag)}}</strong></div>
      <div class="kv"><span>Linked Positions</span><strong>${{fmt.text(selected.option_linked_position_count ?? 0)}}</strong></div>
      <div class="kv"><span>Position Ledger Rows</span><strong>${{fmt.text(selected.option_position_count ?? 0)}}</strong></div>
      <div class="kv"><span>Unmatched Positions</span><strong>${{fmt.text(selected.option_lifecycle_unmatched_position_count ?? 0)}}</strong></div>
      <div class="kv"><span>Option Chain Rows</span><strong>${{fmt.text(selected.option_chain_row_count || 0)}}</strong></div>
      <div class="kv"><span>Option Commentary Links</span><strong>${{fmt.text(selected.option_commentary_claim_count || 0)}}</strong></div>
      <div class="kv"><span>Option Warnings</span><strong>${{escapeHtml(selected.option_warnings || selected.option_lifecycle_warnings || 'none')}}</strong></div>
      <div class="kv"><span>Trader Commentary Claims</span><strong>${{fmt.text(selected.trader_commentary_claim_count || 0)}}</strong></div>
      <div class="kv"><span>Latest Commentary Claim</span><strong>${{badge(selected.trader_commentary_latest_claim_type || 'none')}}</strong></div>
      <div class="kv"><span>Commentary Direction</span><strong>${{badge(selected.trader_commentary_latest_direction || 'neutral')}}</strong></div>
      <div class="kv"><span>Commentary Validation</span><strong>${{badge(selected.trader_commentary_validation_status || 'missing')}}</strong></div>
      <div class="kv"><span>Commentary Hit Status</span><strong>${{badge(selected.trader_commentary_hit_status || 'none')}}</strong></div>
      <div class="kv"><span>Signal Warnings</span><strong>${{escapeHtml(selected.advanced_signal_warnings || selected.revision_evidence_warnings)}}</strong></div>
    </div>
  `;
}}

function renderScoreBars() {{
  const row = selectedRow();
  const scores = [
    ['Valuation', row.valuation_gap === null || row.valuation_gap === undefined ? null : Math.max(0, Math.min(100, row.valuation_gap * 100 + 50))],
    ['Revision', row.revision_score],
    ['News/Catalyst', row.news_catalyst_score],
    ['Insider Activity', row.insider_activity_score],
    ['Short Interest', row.short_interest_score],
    ['Technical Confidence', row.technical_confidence],
    ['Regime Confidence', row.regime_confidence],
    ['Confidence', row.confidence_score],
    ['Timing', row.timing_score],
    ['Risk', row.risk_score],
    ['Liquidity', row.liquidity_score],
    ['Opportunity', row.opportunity_score]
  ];
  document.getElementById('scoreBars').innerHTML = scores.map(([label, value]) => {{
    const width = value === null || value === undefined ? 0 : Math.max(0, Math.min(100, Number(value)));
    return `<div class="bar-row"><div>${{label}}</div><div class="bar"><div class="bar-fill" style="width:${{width}}%"></div></div><div>${{fmt.number(value)}}</div></div>`;
  }}).join('');
}}

function renderTickerDetail() {{
  const row = selectedRow();
  document.getElementById('tickerDetail').innerHTML = `
    <div class="detail-grid">
      <div class="kv"><span>Reason</span><strong>${{escapeHtml(row.main_reasons || row.reason_codes)}}</strong></div>
      <div class="kv"><span>Risks</span><strong>${{escapeHtml(row.main_risks || row.risk_codes)}}</strong></div>
      <div class="kv"><span>Invalidation</span><strong>${{escapeHtml(row.invalidation)}}</strong></div>
      <div class="kv"><span>Data Freshness</span><strong>${{escapeHtml(row.data_freshness)}}</strong></div>
      <div class="kv"><span>Outcome</span><strong>${{badge(row.outcome_status || 'none')}}</strong></div>
      <div class="kv"><span>Revision Signal</span><strong>${{badge(row.revision_signal_status || 'missing')}}</strong></div>
      <div class="kv"><span>Revision Source</span><strong>${{badge(row.revision_source_status || 'missing')}}</strong></div>
      <div class="kv"><span>Revision Validation</span><strong>${{badge(row.revision_validation_status || 'missing')}}</strong></div>
      <div class="kv"><span>News/Catalyst Signal</span><strong>${{badge(row.news_catalyst_signal_status || 'missing')}}</strong></div>
      <div class="kv"><span>News/Catalyst Validation</span><strong>${{badge(row.news_catalyst_validation_status || 'missing')}}</strong></div>
      <div class="kv"><span>Insider Activity Signal</span><strong>${{badge(row.insider_activity_signal_status || 'missing')}}</strong></div>
      <div class="kv"><span>Insider Activity Validation</span><strong>${{badge(row.insider_activity_validation_status || 'missing')}}</strong></div>
      <div class="kv"><span>Short Interest Signal</span><strong>${{badge(row.short_interest_signal_status || 'missing')}}</strong></div>
      <div class="kv"><span>Short Interest Validation</span><strong>${{badge(row.short_interest_validation_status || 'missing')}}</strong></div>
      <div class="kv"><span>Trader Commentary</span><strong>${{fmt.text(row.trader_commentary_claim_count || 0)}} claims</strong></div>
      <div class="kv"><span>Commentary Validation</span><strong>${{badge(row.trader_commentary_validation_status || 'missing')}}</strong></div>
      <div class="kv"><span>Support Zone</span><strong>${{fmt.money(row.support_low)}} / ${{fmt.money(row.support_high)}}</strong></div>
      <div class="kv"><span>Resistance Zone</span><strong>${{fmt.money(row.resistance_low)}} / ${{fmt.money(row.resistance_high)}}</strong></div>
      <div class="kv"><span>Breakout</span><strong>${{fmt.money(row.breakout_level)}}</strong></div>
      <div class="kv"><span>Trend Repair</span><strong>${{fmt.money(row.trend_repair_level)}}</strong></div>
      <div class="kv"><span>Technical Date</span><strong>${{escapeHtml(row.technical_signal_date || 'none')}}</strong></div>
      <div class="kv"><span>Regime Date</span><strong>${{escapeHtml(row.regime_signal_date || 'none')}}</strong></div>
      <div class="kv"><span>Portfolio Category</span><strong>${{badge(row.portfolio_review_category || 'none')}}</strong></div>
      <div class="kv"><span>Sizing</span><strong>${{escapeHtml(row.sizing_guidance)}}</strong></div>
      <div class="kv"><span>Warnings</span><strong>${{escapeHtml(row.model_warnings)}}</strong></div>
      <div class="kv"><span>Signal Warnings</span><strong>${{escapeHtml(row.advanced_signal_warnings)}}</strong></div>
      <div class="kv"><span>Portfolio Warnings</span><strong>${{escapeHtml(row.portfolio_warnings)}}</strong></div>
    </div>
  `;
}}

function renderChart() {{
  const row = selectedRow();
  const points = DATA.price_history[row.ticker] || [];
  const chart = document.getElementById('chart');
  if (!points.length) {{
    chart.innerHTML = '<svg viewBox="0 0 640 300" width="100%" height="100%"><text x="24" y="40" fill="#647084">No price history</text></svg>';
    return;
  }}
  const values = points.map(point => point.close).filter(value => value !== null && value !== undefined);
  [row.target_low, row.base_target, row.target_high, row.support_low, row.support_high, row.resistance_low, row.resistance_high].forEach(value => {{
    if (value !== null && value !== undefined) values.push(value);
  }});
  const min = Math.min(...values);
  const max = Math.max(...values);
  const pad = Math.max((max - min) * .08, 1);
  const low = min - pad;
  const high = max + pad;
  const width = 640;
  const height = 300;
  const x = index => 42 + index * ((width - 72) / Math.max(points.length - 1, 1));
  const y = value => 260 - ((Number(value) - low) / (high - low)) * 220;
  const path = points.map((point, index) => `${{index === 0 ? 'M' : 'L'}} ${{x(index).toFixed(1)}} ${{y(point.close).toFixed(1)}}`).join(' ');
  const line = (value, cls, label) => value === null || value === undefined ? '' : `
    <line x1="42" x2="610" y1="${{y(value).toFixed(1)}}" y2="${{y(value).toFixed(1)}}" stroke="${{cls}}" stroke-dasharray="5 4" />
    <text x="614" y="${{(y(value) + 4).toFixed(1)}}" fill="${{cls}}" font-size="11">${{label}}</text>
  `;
  chart.innerHTML = `
    <svg viewBox="0 0 640 300" width="100%" height="100%" role="img" aria-label="Price and target chart">
      <rect x="0" y="0" width="640" height="300" fill="#ffffff"></rect>
      <line x1="42" x2="610" y1="260" y2="260" stroke="#d8dee8"></line>
      <line x1="42" x2="42" y1="28" y2="260" stroke="#d8dee8"></line>
      ${{line(row.target_low, '#a86700', 'low')}}
      ${{line(row.base_target, '#168558', 'base')}}
      ${{line(row.target_high, '#2f6fdf', 'high')}}
      ${{line(row.support_high, '#0f8f6f', 'support')}}
      ${{line(row.resistance_low, '#dc2626', 'resistance')}}
      <path d="${{path}}" fill="none" stroke="#19202a" stroke-width="2.4"></path>
      <text x="42" y="285" fill="#647084" font-size="11">${{escapeHtml(points[0].date)}}</text>
      <text x="540" y="285" fill="#647084" font-size="11">${{escapeHtml(points[points.length - 1].date)}}</text>
    </svg>
  `;
}}

function renderAlertHistory() {{
  const rows = DATA.alert_history.map(alert => `<tr>
    <td>${{escapeHtml(alert.ticker)}}</td>
    <td>${{badge(alert.alert_type)}}</td>
    <td>${{escapeHtml(alert.priority)}}</td>
    <td>${{escapeHtml(alert.status)}}</td>
    <td>${{escapeHtml(alert.alert_timestamp)}}</td>
    <td>${{fmt.money(alert.current_price)}}</td>
    <td>${{fmt.money(alert.base_target)}}</td>
  </tr>`);
  document.getElementById('alertHistory').innerHTML = table(
    ['Ticker', 'Alert', 'Priority', 'Status', 'Timestamp', 'Price', 'Target'],
    rows
  );
}}

function renderOutcomeTable() {{
  const rows = DATA.outcomes.map(outcome => `<tr>
    <td>${{escapeHtml(outcome.ticker)}}</td>
    <td>${{badge(outcome.alert_type)}}</td>
    <td>${{badge(outcome.outcome_status)}}</td>
    <td>${{fmt.percent(outcome.return_5d)}}</td>
    <td>${{fmt.percent(outcome.return_20d)}}</td>
    <td>${{fmt.percent(outcome.return_60d)}}</td>
    <td>${{fmt.percent(outcome.return_120d)}}</td>
    <td>${{fmt.percent(outcome.max_favorable_excursion)}}</td>
    <td>${{fmt.percent(outcome.max_adverse_excursion)}}</td>
    <td>${{escapeHtml(outcome.pending_horizons)}}</td>
  </tr>`);
  document.getElementById('outcomeTable').innerHTML = table(
    ['Ticker', 'Alert', 'Outcome', '5d', '20d', '60d', '120d', 'MFE', 'MAE', 'Pending'],
    rows
  );
}}

function renderHealth() {{
  const health = DATA.health;
  const tableRows = Object.entries(health.table_counts || {{}}).map(([name, count]) =>
    `<tr><td>${{escapeHtml(name)}}</td><td>${{count}}</td></tr>`
  );
  document.getElementById('dataHealth').innerHTML = table(['Table', 'Rows'], tableRows);
  const pipeline = health.latest_pipeline_run || {{}};
  document.getElementById('modelHealth').innerHTML = `
    <div class="detail-grid">
      <div class="kv"><span>Required Tables</span><strong>${{health.required_tables_present}} / ${{health.required_tables_total}}</strong></div>
      <div class="kv"><span>Latest Price</span><strong>${{escapeHtml(health.latest_price_date)}}</strong></div>
      <div class="kv"><span>Latest Target</span><strong>${{escapeHtml(health.latest_target_date)}}</strong></div>
      <div class="kv"><span>Latest Score</span><strong>${{escapeHtml(health.latest_score_date)}}</strong></div>
      <div class="kv"><span>Fundamental Benchmarks</span><strong>${{fmt.text(health.fundamental_benchmark_rows || 0)}} rows</strong></div>
      <div class="kv"><span>Fundamental Comparisons</span><strong>${{fmt.text(health.fundamental_comparison_rows || 0)}} rows</strong></div>
      <div class="kv"><span>Latest Fundamental Benchmark</span><strong>${{escapeHtml(health.latest_fundamental_benchmark_date || 'none')}}</strong></div>
      <div class="kv"><span>Research Queue</span><strong>${{fmt.text(health.research_recommendation_rows || 0)}} candidates</strong></div>
      <div class="kv"><span>Latest Research Recommendation</span><strong>${{escapeHtml(health.latest_research_recommendation_date || 'none')}}</strong></div>
      <div class="kv"><span>Latest Signal</span><strong>${{escapeHtml(health.latest_signal_date)}}</strong></div>
      <div class="kv"><span>Latest Signal Validation</span><strong>${{escapeHtml(health.latest_signal_validation_date)}}</strong></div>
      <div class="kv"><span>Latest Technical</span><strong>${{escapeHtml(health.latest_technical_signal_date || 'none')}}</strong></div>
      <div class="kv"><span>Technical Coverage</span><strong>${{escapeHtml(health.technical_signal_coverage || '0/0')}}</strong></div>
      <div class="kv"><span>Missing Technical</span><strong>${{escapeHtml((health.technical_missing_signal_tickers || []).join(', ') || 'none')}}</strong></div>
      <div class="kv"><span>Latest Regime</span><strong>${{escapeHtml(health.latest_regime_signal_date || 'none')}}</strong></div>
      <div class="kv"><span>Regime Coverage</span><strong>${{escapeHtml(health.regime_signal_coverage || '0/0')}}</strong></div>
      <div class="kv"><span>Missing Regime</span><strong>${{escapeHtml((health.regime_missing_signal_tickers || []).join(', ') || 'none')}}</strong></div>
      <div class="kv"><span>Revision Sources</span><strong>${{fmt.text(health.revision_source_backed_ticker_count || 0)}} backed</strong></div>
      <div class="kv"><span>Revision Source Rows</span><strong>${{fmt.text(health.revision_source_snapshot_rows || 0)}}</strong></div>
      <div class="kv"><span>Revision Aggregates</span><strong>${{fmt.text(health.revision_aggregate_rows || 0)}}</strong></div>
      <div class="kv"><span>Latest Revision Aggregate</span><strong>${{escapeHtml(health.latest_revision_aggregate_date)}}</strong></div>
      <div class="kv"><span>News Sources</span><strong>${{fmt.text(health.news_catalyst_source_backed_ticker_count || 0)}} backed</strong></div>
      <div class="kv"><span>News Provider Numeric</span><strong>${{fmt.text(health.news_catalyst_provider_numeric_ticker_count || 0)}} tickers</strong></div>
      <div class="kv"><span>News Text-Derived</span><strong>${{fmt.text(health.news_catalyst_text_derived_ticker_count || 0)}} tickers</strong></div>
      <div class="kv"><span>News Total Numeric</span><strong>${{fmt.text(health.news_catalyst_total_numeric_ticker_count || 0)}} tickers</strong></div>
      <div class="kv"><span>News Missing Sources</span><strong>${{fmt.text(health.news_catalyst_missing_source_ticker_count || 0)}}</strong></div>
      <div class="kv"><span>News Missing Numeric</span><strong>${{fmt.text(health.news_catalyst_missing_numeric_ticker_count || 0)}}</strong></div>
      <div class="kv"><span>Provider Upgrade Status</span><strong>${{badge(health.news_catalyst_provider_upgrade_status || 'unknown')}}</strong></div>
      <div class="kv"><span>Provider Upgrade Needed</span><strong>${{fmt.text(health.news_catalyst_provider_native_upgrade_ticker_count || 0)}} tickers</strong></div>
      <div class="kv"><span>Latest Provider-Native Date</span><strong>${{escapeHtml(health.news_catalyst_latest_provider_native_source_date || 'none')}}</strong></div>
      <div class="kv"><span>Rejected Provider-Native Rows</span><strong>${{fmt.text(health.news_catalyst_provider_native_rejected_row_count || 0)}}</strong></div>
      <div class="kv"><span>News Coverage Plan</span><strong>${{escapeHtml((health.news_catalyst_coverage_plan_tickers || []).join(', ') || 'none')}}</strong></div>
      <div class="kv"><span>News Queue Stale</span><strong>${{badge(String(Boolean(health.news_catalyst_coverage_queue_stale)))}}</strong></div>
      <div class="kv"><span>News Missing Queue Stale</span><strong>${{badge(String(Boolean(health.news_catalyst_missing_queue_stale)))}}</strong></div>
      <div class="kv"><span>News Upgrade Queue Stale</span><strong>${{badge(String(Boolean(health.news_catalyst_provider_upgrade_queue_stale)))}}</strong></div>
      <div class="kv"><span>News Backfill Apply Ready</span><strong>${{badge(String(Boolean(health.news_catalyst_backfill_apply_ready)))}}</strong></div>
      <div class="kv"><span>News Valid Upgrade Tickers</span><strong>${{escapeHtml((health.news_catalyst_valid_upgrade_tickers || []).join(', ') || 'none')}}</strong></div>
      <div class="kv"><span>News Projected Upgrade Delta</span><strong>${{fmt.text(health.news_catalyst_projected_upgrade_delta || 0)}}</strong></div>
      <div class="kv"><span>News Blocked Apply Reason</span><strong>${{escapeHtml(health.news_catalyst_blocked_apply_reason || 'none')}}</strong></div>
      <div class="kv"><span>News Upgrade Blockers</span><strong>${{escapeHtml((health.news_catalyst_provider_upgrade_blockers || []).join(', ') || 'none')}}</strong></div>
      <div class="kv"><span>News Smoke Test</span><strong>${{escapeHtml(health.news_catalyst_provider_smoke_test_command || 'none')}}</strong></div>
      <div class="kv"><span>News Provider Warnings</span><strong>${{escapeHtml((health.news_catalyst_provider_warning_summary || []).join(', ') || 'none')}}</strong></div>
      <div class="kv"><span>News Source Rows</span><strong>${{fmt.text(health.news_catalyst_source_snapshot_rows || 0)}}</strong></div>
      <div class="kv"><span>News Provider Numeric Rows</span><strong>${{fmt.text(health.news_catalyst_provider_numeric_snapshot_rows || 0)}}</strong></div>
      <div class="kv"><span>News Text-Derived Rows</span><strong>${{fmt.text(health.news_catalyst_text_derived_snapshot_rows || 0)}}</strong></div>
      <div class="kv"><span>News Aggregates</span><strong>${{fmt.text(health.news_catalyst_aggregate_rows || 0)}}</strong></div>
      <div class="kv"><span>Latest News Aggregate</span><strong>${{escapeHtml(health.latest_news_catalyst_aggregate_date)}}</strong></div>
      <div class="kv"><span>Insider Source Rows</span><strong>${{fmt.text(health.insider_activity_source_rows || 0)}}</strong></div>
      <div class="kv"><span>Insider Source Coverage</span><strong>${{fmt.text(health.insider_activity_source_covered_ticker_count || 0)}} / ${{fmt.text(health.insider_activity_source_active_equity_count || 0)}}</strong></div>
      <div class="kv"><span>Insider Source Backed</span><strong>${{fmt.text(health.insider_activity_source_backed_ticker_count || 0)}} backed</strong></div>
      <div class="kv"><span>Insider SEC Rate Limits</span><strong>${{fmt.text(health.insider_activity_sec_rate_limited_ticker_count || 0)}} tickers</strong></div>
      <div class="kv"><span>Latest Insider Source</span><strong>${{escapeHtml(health.latest_insider_activity_source_date)}}</strong></div>
      <div class="kv"><span>Latest Insider Fetch</span><strong>${{escapeHtml(health.latest_insider_activity_successful_fetch_date)}}</strong></div>
      <div class="kv"><span>Short Interest Sources</span><strong>${{fmt.text(health.short_interest_source_backed_ticker_count || 0)}} / ${{fmt.text(health.short_interest_source_active_equity_count || 0)}}</strong></div>
      <div class="kv"><span>Short Interest Rows</span><strong>${{fmt.text(health.short_interest_source_rows || 0)}}</strong></div>
      <div class="kv"><span>Latest Short Interest</span><strong>${{escapeHtml(health.latest_short_interest_settlement_date)}}</strong></div>
      <div class="kv"><span>Short Interest Provider Export</span><strong>${{fmt.text(health.short_interest_provider_export_valid_rows || 0)}} rows</strong></div>
      <div class="kv"><span>Short Interest Provider Tickers</span><strong>${{escapeHtml((health.short_interest_provider_export_tickers || []).join(', ') || 'none')}}</strong></div>
      <div class="kv"><span>Short Interest Fetchable Providers</span><strong>${{escapeHtml((health.short_interest_fetchable_providers || []).join(', ') || 'none')}}</strong></div>
      <div class="kv"><span>Short Interest Provider Cache</span><strong>${{fmt.text(health.short_interest_provider_cache_files || 0)}} files</strong></div>
      <div class="kv"><span>Latest Short Interest Provider Cache</span><strong>${{escapeHtml(health.latest_short_interest_provider_cache_timestamp || 'none')}}</strong></div>
      <div class="kv"><span>Short Interest Provider Warnings</span><strong>${{escapeHtml((health.short_interest_provider_warnings || []).join(', ') || 'none')}}</strong></div>
      <div class="kv"><span>Short Interest Missing Coverage</span><strong>${{escapeHtml((health.short_interest_missing_coverage_tickers || []).join(', ') || 'none')}}</strong></div>
      <div class="kv"><span>Short Interest Missing Valid Rows</span><strong>${{escapeHtml((health.short_interest_valid_missing_row_tickers || []).join(', ') || 'none')}}</strong></div>
      <div class="kv"><span>Short Interest Diagnostics</span><strong>${{escapeHtml((health.short_interest_provider_diagnostic_status || []).join(', ') || 'none')}}</strong></div>
      <div class="kv"><span>Short Interest Missing Apply Blocker</span><strong>${{escapeHtml(health.short_interest_missing_coverage_blocked_apply_reason || 'none')}}</strong></div>
      <div class="kv"><span>Missing Short Interest</span><strong>${{escapeHtml((health.short_interest_missing_source_tickers || []).join(', ') || 'none')}}</strong></div>
      <div class="kv"><span>Stale Short Interest</span><strong>${{escapeHtml((health.short_interest_stale_source_tickers || []).join(', ') || 'none')}}</strong></div>
      <div class="kv"><span>Short Interest Backfill Valid</span><strong>${{fmt.text(health.short_interest_backfill_valid_rows || 0)}}</strong></div>
      <div class="kv"><span>Short Interest Placeholders</span><strong>${{fmt.text(health.short_interest_backfill_blank_placeholders || 0)}}</strong></div>
      <div class="kv"><span>Short Interest Invalid Rows</span><strong>${{fmt.text(health.short_interest_backfill_invalid_rows || 0)}}</strong></div>
      <div class="kv"><span>Short Interest Projected Coverage</span><strong>${{fmt.text(health.short_interest_projected_source_coverage_count || 0)}} / ${{fmt.text(health.short_interest_source_active_equity_count || 0)}}</strong></div>
      <div class="kv"><span>Short Interest Import Ready</span><strong>${{badge(String(Boolean(health.short_interest_backfill_apply_ready)))}}</strong></div>
      <div class="kv"><span>Short Interest Valid Imports</span><strong>${{escapeHtml((health.short_interest_valid_import_tickers || []).join(', ') || 'none')}}</strong></div>
      <div class="kv"><span>Short Interest Blocked Reason</span><strong>${{escapeHtml(health.short_interest_blocked_import_reason || 'none')}}</strong></div>
      <div class="kv"><span>Options Chain Source</span><strong>${{escapeHtml(health.option_chain_source || 'none')}}</strong></div>
      <div class="kv"><span>Options Provider</span><strong>${{badge(health.option_provider_readiness || 'blocked')}}</strong></div>
      <div class="kv"><span>Options Blocked Reason</span><strong>${{escapeHtml(health.option_provider_blocked_reason || 'none')}}</strong></div>
      <div class="kv"><span>Options ibapi</span><strong>${{escapeHtml(health.option_ibapi_status || 'unknown')}}</strong></div>
      <div class="kv"><span>Option Activation</span><strong>${{badge(health.option_activation_status || 'blocked')}}</strong></div>
      <div class="kv"><span>Option Activation Blocker</span><strong>${{escapeHtml(health.option_activation_blocked_reason || 'none')}}</strong></div>
      <div class="kv"><span>Minimum Option Coverage</span><strong>${{escapeHtml(health.minimum_option_chain_coverage || '0/0')}}</strong></div>
      <div class="kv"><span>Minimum Option Reviews</span><strong>${{fmt.text(health.minimum_option_review_count || 0)}}</strong></div>
      <div class="kv"><span>Options ibapi Repair Needed</span><strong>${{badge(String(Boolean(health.ibapi_repair_needed)))}}</strong></div>
      <div class="kv"><span>Options Fetch Universe</span><strong>${{fmt.text(health.option_chain_fetch_universe_ticker_count || 0)}} tickers</strong></div>
      <div class="kv"><span>Options Missing Chains</span><strong>${{escapeHtml((health.option_chain_missing_tickers || []).join(', ') || 'none')}}</strong></div>
      <div class="kv"><span>Options Full Coverage</span><strong>${{escapeHtml(health.option_chain_coverage_count || '0/0')}}</strong></div>
      <div class="kv"><span>Options Raw Coverage</span><strong>${{escapeHtml(health.option_chain_raw_coverage_count || '0/0')}}</strong></div>
      <div class="kv"><span>Options Non-Actionable</span><strong>${{escapeHtml((health.option_chain_non_actionable_tickers || []).join(', ') || 'none')}}</strong></div>
      <div class="kv"><span>Options Chain Availability</span><strong>${{escapeHtml(health.option_chain_availability_summary || 'all available')}}</strong></div>
      <div class="kv"><span>Options Coverage Status</span><strong>${{badge(health.option_chain_coverage_status || 'missing_coverage')}}</strong></div>
      <div class="kv"><span>Options Projected Coverage</span><strong>${{escapeHtml(health.option_chain_projected_coverage_count || '0/0')}}</strong></div>
      <div class="kv"><span>Options Valid Backfill</span><strong>${{escapeHtml((health.option_chain_valid_backfill_tickers || []).join(', ') || 'none')}}</strong></div>
      <div class="kv"><span>Options Coverage Ready</span><strong>${{badge(String(Boolean(health.option_chain_coverage_apply_ready)))}}</strong></div>
      <div class="kv"><span>Options Coverage Blocker</span><strong>${{escapeHtml(health.option_chain_coverage_blocked_reason || 'none')}}</strong></div>
      <div class="kv"><span>Options Chain Rows</span><strong>${{fmt.text(health.option_chain_rows || 0)}}</strong></div>
      <div class="kv"><span>Option Review Rows</span><strong>${{fmt.text(health.option_income_review_rows || 0)}}</strong></div>
      <div class="kv"><span>Option Risk Rows</span><strong>${{fmt.text(health.option_risk_review_rows || 0)}}</strong></div>
      <div class="kv"><span>Option Outcome Rows</span><strong>${{fmt.text(health.option_review_outcome_rows || 0)}}</strong></div>
      <div class="kv"><span>Option Position Rows</span><strong>${{fmt.text(health.option_position_ledger_rows || 0)}}</strong></div>
      <div class="kv"><span>Option Lifecycle Rows</span><strong>${{fmt.text(health.option_position_lifecycle_review_rows || 0)}}</strong></div>
      <div class="kv"><span>Option Position Tickers</span><strong>${{fmt.text(health.option_position_ticker_count || 0)}}</strong></div>
      <div class="kv"><span>Account Context</span><strong>${{badge(health.account_context_activation_status || 'not_configured')}}</strong></div>
      <div class="kv"><span>Account Blockers</span><strong>${{escapeHtml((health.account_context_blockers || []).join(', ') || 'none')}}</strong></div>
      <div class="kv"><span>Option Readiness</span><strong>${{badge(health.account_option_position_readiness_status || 'source_data_required')}}</strong></div>
      <div class="kv"><span>Option Staged Rows</span><strong>${{fmt.text(health.account_option_valid_backfill_rows || 0)}} valid / ${{fmt.text(health.account_option_invalid_backfill_rows || 0)}} invalid / ${{fmt.text(health.account_option_blank_backfill_rows || 0)}} blank</strong></div>
      <div class="kv"><span>Option Projected Rows</span><strong>${{fmt.text(health.account_option_projected_position_rows || 0)}} positions / ${{fmt.text(health.account_option_projected_lifecycle_rows || 0)}} lifecycle</strong></div>
      <div class="kv"><span>Option Readiness Actions</span><strong>${{escapeHtml((health.account_option_recommended_actions || []).join(', ') || 'none')}}</strong></div>
      <div class="kv"><span>Portfolio Rows</span><strong>${{fmt.text(health.account_portfolio_position_rows || 0)}} / ${{fmt.text(health.account_portfolio_cash_rows || 0)}} cash</strong></div>
      <div class="kv"><span>Risk Missing Portfolio</span><strong>${{fmt.text(health.account_option_risk_missing_portfolio_context_rows || 0)}}</strong></div>
      <div class="kv"><span>Latest Option Chain</span><strong>${{escapeHtml(health.latest_option_chain_snapshot || 'none')}}</strong></div>
      <div class="kv"><span>Latest Option Review</span><strong>${{escapeHtml(health.latest_option_income_review || 'none')}}</strong></div>
      <div class="kv"><span>Latest Option Risk</span><strong>${{escapeHtml(health.latest_option_risk_review || 'none')}}</strong></div>
      <div class="kv"><span>Latest Option Outcome</span><strong>${{escapeHtml(health.latest_option_outcome || 'none')}}</strong></div>
      <div class="kv"><span>Latest Option Position</span><strong>${{escapeHtml(health.latest_option_position_open_date || 'none')}}</strong></div>
      <div class="kv"><span>Latest Option Lifecycle</span><strong>${{escapeHtml(health.latest_option_lifecycle_review || 'none')}}</strong></div>
      <div class="kv"><span>Options Backfill Valid</span><strong>${{fmt.text(health.option_backfill_valid_rows || 0)}}</strong></div>
      <div class="kv"><span>Options Backfill Ready</span><strong>${{badge(String(Boolean(health.option_backfill_apply_ready)))}}</strong></div>
      <div class="kv"><span>Options Backfill Blocker</span><strong>${{escapeHtml(health.option_backfill_blocked_reason || 'none')}}</strong></div>
      <div class="kv"><span>Trader Commentary Raw</span><strong>${{fmt.text(health.trader_commentary_raw_rows || 0)}} rows</strong></div>
      <div class="kv"><span>Trader Commentary Claims</span><strong>${{fmt.text(health.trader_commentary_claim_rows || 0)}} rows</strong></div>
      <div class="kv"><span>Trader Commentary Validations</span><strong>${{fmt.text(health.trader_commentary_outcome_rows || 0)}} rows</strong></div>
      <div class="kv"><span>Commentary Onboarding</span><strong>${{fmt.text(health.trader_commentary_onboarding_candidate_count || 0)}} candidates</strong></div>
      <div class="kv"><span>Unmapped Commentary Labels</span><strong>${{fmt.text(health.trader_commentary_unmapped_instrument_count || 0)}}</strong></div>
      <div class="kv"><span>Commentary Aliases</span><strong>${{fmt.text(health.trader_commentary_alias_count || 0)}}</strong></div>
      <div class="kv"><span>Commentary Label Dispositions</span><strong>${{fmt.text(health.trader_commentary_label_disposition_count || 0)}}</strong></div>
      <div class="kv"><span>Intentionally Unresolved Labels</span><strong>${{fmt.text(health.trader_commentary_intentionally_unresolved_label_count || 0)}}</strong></div>
      <div class="kv"><span>Ignored Non-Instrument Labels</span><strong>${{fmt.text(health.trader_commentary_ignored_non_instrument_label_count || 0)}}</strong></div>
      <div class="kv"><span>Scoreable Assets</span><strong>${{fmt.text(health.scoreable_asset_count || 0)}}</strong></div>
      <div class="kv"><span>Reference Assets</span><strong>${{fmt.text(health.reference_asset_count || 0)}}</strong></div>
      <div class="kv"><span>Commentary Browser Runs</span><strong>${{fmt.text(health.trader_commentary_browser_capture_run_rows || 0)}} rows</strong></div>
      <div class="kv"><span>Commentary Browser Items</span><strong>${{fmt.text(health.trader_commentary_browser_capture_item_rows || 0)}} rows</strong></div>
      <div class="kv"><span>Latest Browser Capture</span><strong>${{escapeHtml(health.latest_trader_commentary_browser_capture_timestamp || 'none')}}</strong></div>
      <div class="kv"><span>Browser Capture Dir</span><strong>${{badge(String(Boolean(health.trader_commentary_browser_capture_dir_exists)))}}</strong></div>
      <div class="kv"><span>Commentary Discord Runs</span><strong>${{fmt.text(health.trader_commentary_discord_capture_run_rows || 0)}} rows</strong></div>
      <div class="kv"><span>Commentary Discord Items</span><strong>${{fmt.text(health.trader_commentary_discord_capture_item_rows || 0)}} rows</strong></div>
      <div class="kv"><span>Latest Discord Capture</span><strong>${{escapeHtml(health.latest_trader_commentary_discord_capture_timestamp || 'none')}}</strong></div>
      <div class="kv"><span>Discord Capture Enabled</span><strong>${{badge(String(Boolean(health.trader_commentary_discord_capture_enabled)))}}</strong></div>
      <div class="kv"><span>Discord Capture Dir</span><strong>${{badge(String(Boolean(health.trader_commentary_discord_capture_dir_exists)))}}</strong></div>
      <div class="kv"><span>Latest Commentary Capture</span><strong>${{escapeHtml(health.latest_trader_commentary_capture_date || 'none')}}</strong></div>
      <div class="kv"><span>Latest Commentary Claim</span><strong>${{escapeHtml(health.latest_trader_commentary_claim_date || 'none')}}</strong></div>
      <div class="kv"><span>Latest Commentary Validation</span><strong>${{escapeHtml(health.latest_trader_commentary_validation_date || 'none')}}</strong></div>
      <div class="kv"><span>Commentary Warning Tickers</span><strong>${{escapeHtml((health.trader_commentary_warning_tickers || []).join(', ') || 'none')}}</strong></div>
      <div class="kv"><span>Revision Evidence</span><strong>${{badge(health.revision_evidence_decision || 'unknown')}}</strong></div>
      <div class="kv"><span>Latest Alert</span><strong>${{escapeHtml(health.latest_alert_timestamp)}}</strong></div>
      <div class="kv"><span>Latest Range</span><strong>${{escapeHtml(health.latest_range_snapshot || 'none')}}</strong></div>
      <div class="kv"><span>Intraday Health</span><strong>${{badge(health.intraday_health_status || 'unknown')}}</strong></div>
      <div class="kv"><span>Market Session</span><strong>${{badge(health.intraday_market_session || 'unknown')}}</strong></div>
      <div class="kv"><span>Regular Hours</span><strong>${{badge(String(Boolean(health.intraday_regular_market_hours)))}}</strong></div>
      <div class="kv"><span>TOM Loop</span><strong>${{badge(health.tom_loop_health || 'unknown')}}</strong></div>
      <div class="kv"><span>Loop Status</span><strong>${{escapeHtml(health.tom_loop_status || 'none')}}</strong></div>
      <div class="kv"><span>Loop Heartbeat Age</span><strong>${{fmt.text(health.tom_loop_heartbeat_age_seconds ?? 'none')}}</strong></div>
      <div class="kv"><span>Loop Recovery</span><strong>${{badge(health.tom_loop_recovery_status || 'none')}}</strong></div>
      <div class="kv"><span>Recovery Actions</span><strong>${{escapeHtml((health.tom_loop_recommended_actions || []).join(', ') || 'none')}}</strong></div>
      <div class="kv"><span>Clear Lock Command</span><strong>${{escapeHtml(health.tom_loop_clear_stale_lock_command || 'none')}}</strong></div>
      <div class="kv"><span>Scheduler Reconciliation</span><strong>${{badge(health.scheduler_reconciliation_status || 'unknown')}}</strong></div>
      <div class="kv"><span>Actual Heartbeat</span><strong>${{escapeHtml(health.actual_heartbeat_command || 'none')}}</strong></div>
      <div class="kv"><span>Scheduler Warnings</span><strong>${{escapeHtml((health.scheduler_warnings || []).join(', ') || 'none')}}</strong></div>
      <div class="kv"><span>Loop Blockers</span><strong>${{escapeHtml((health.tom_loop_blockers || []).join(', ') || 'none')}}</strong></div>
      <div class="kv"><span>Intraday Blockers</span><strong>${{escapeHtml((health.intraday_health_blockers || []).join(', ') || 'none')}}</strong></div>
      <div class="kv"><span>Intraday Warnings</span><strong>${{escapeHtml((health.intraday_health_warnings || []).join(', ') || 'none')}}</strong></div>
      <div class="kv"><span>Intraday Notes</span><strong>${{escapeHtml((health.intraday_health_notes || []).join(', ') || 'none')}}</strong></div>
      <div class="kv"><span>Intraday Cycle</span><strong>${{escapeHtml((health.latest_intraday_cycle_status || 'none') + (health.latest_intraday_cycle_started_at ? ' ' + health.latest_intraday_cycle_started_at : ''))}}</strong></div>
      <div class="kv"><span>Latest Notification</span><strong>${{escapeHtml(health.latest_notification || 'none')}}</strong></div>
      <div class="kv"><span>Latest Delivery</span><strong>${{escapeHtml(health.latest_notification_delivery || 'none')}}</strong></div>
      <div class="kv"><span>Delivery Failures</span><strong>${{fmt.text(health.failed_notification_deliveries || 0)}}</strong></div>
      <div class="kv"><span>Latest Outcome</span><strong>${{escapeHtml(health.latest_outcome_date)}}</strong></div>
      <div class="kv"><span>Latest Portfolio</span><strong>${{escapeHtml(health.latest_portfolio_review_date)}}</strong></div>
      <div class="kv"><span>Pipeline</span><strong>${{escapeHtml(pipeline.run_type)}} ${{escapeHtml(pipeline.status)}}</strong></div>
      <div class="kv"><span>ETF Status</span><strong>${{DATA.rows.filter(row => row.asset_type === 'etf' && row.alert_type === 'skipped').length}} gated</strong></div>
    </div>
  `;
}}

function renderTickerViews() {{
  renderSummaryPanel();
  renderPortfolioPanel();
  renderAdvancedSignalsPanel();
  renderScoreBars();
  renderTickerDetail();
  renderChart();
}}

function renderAll() {{
  document.getElementById('generatedAt').textContent = 'Generated ' + DATA.generated_at;
  renderMetrics();
  renderTickerSelect();
  renderAlertsTable();
  renderRankingTable();
  renderTickerViews();
  renderAlertHistory();
  renderOutcomeTable();
  renderHealth();
}}

document.querySelectorAll('.nav button').forEach(button => {{
  button.addEventListener('click', () => {{
    document.querySelectorAll('.nav button').forEach(item => item.classList.remove('active'));
    document.querySelectorAll('section').forEach(section => section.classList.remove('active'));
    button.classList.add('active');
    document.getElementById(button.dataset.section).classList.add('active');
  }});
}});

renderAll();
</script>
</body>
</html>
"""


def build_dashboard(config: AppConfig) -> DashboardResult:
    path = dashboard_path(config.project_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = _build_dashboard_data(config)
    path.write_text(_dashboard_html(data), encoding="utf-8")
    return DashboardResult(
        path=path,
        generated_at=str(data["generated_at"]),
        row_count=len(data["rows"]),
    )
