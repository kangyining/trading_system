from __future__ import annotations

import csv
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path
from typing import Iterable

from .config import AppConfig
from .commentary_onboarding import build_commentary_onboarding_plan
from .db import DatabaseStatus, get_database_status
from .insider_activity import insider_source_status_report, insider_statuses
from .intraday_health import intraday_health
from .news_catalysts import news_catalyst_statuses
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
from .revision_evidence import build_revision_evidence
from .revision_sources import revision_source_status_report
from .scheduler import audit_scheduler
from .short_interest import (
    short_interest_missing_coverage_plan,
    short_interest_provider_status,
    short_interest_source_status_report,
    short_interest_statuses,
    validate_short_interest_backfill,
)
from .storage import (
    AlertOutcomeStatus,
    AlertStatus,
    PriceStatus,
    ScoreStatus,
    SignalOutcomeStatus,
    SignalStatus,
    ValuationStatus,
    alert_statuses,
    count_assets,
    count_reference_assets,
    count_rows_by_table,
    count_scoreable_assets,
    etf_statuses,
    latest_alert_timestamp,
    latest_any_etf_holdings_date,
    latest_etf_nav_date,
    latest_fundamental_benchmark_date,
    latest_intraday_gap_timestamp,
    latest_notification_timestamp,
    latest_outcome_date,
    latest_pipeline_run,
    latest_portfolio_cash_date,
    latest_portfolio_position_date,
    latest_portfolio_review_date,
    latest_price_date,
    latest_quote_timestamp,
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
    list_option_risk_reviews,
    list_insider_transaction_source_snapshots,
    list_short_interest_source_snapshots,
    list_notification_events,
    latest_trader_commentary_capture_date,
    latest_trader_commentary_browser_capture_timestamp,
    latest_trader_commentary_discord_capture_timestamp,
    latest_trader_commentary_claim_date,
    latest_trader_commentary_outcome_date,
    list_trader_commentary_browser_capture_runs,
    list_trader_commentary_discord_capture_runs,
    latest_notification_delivery_timestamp,
    outcome_statuses,
    notification_delivery_count,
    portfolio_statuses,
    price_statuses,
    range_statuses,
    regime_signal_statuses,
    score_statuses,
    signal_statuses,
    signal_outcome_statuses,
    technical_signal_statuses,
    trader_commentary_statuses,
    valuation_statuses,
    pending_notification_count,
    fundamental_comparison_statuses,
    option_income_statuses,
    option_lifecycle_statuses,
    option_outcome_statuses,
    option_position_statuses,
    option_risk_statuses,
)


REPORT_CSV_COLUMNS = (
    "ticker",
    "asset_type",
    "current_price",
    "target_low",
    "base_target",
    "target_high",
    "valuation_gap",
    "opportunity_score",
    "confidence_score",
    "timing_score",
    "risk_score",
    "liquidity_score",
    "data_quality_score",
    "alert_type",
    "priority",
    "status",
    "main_reasons",
    "main_risks",
    "reason_codes",
    "risk_codes",
    "invalidation",
    "data_freshness",
    "range_state",
    "range_snapshot_timestamp",
    "strong_buy_below",
    "starter_buy_below",
    "add_below",
    "hold_low",
    "hold_high",
    "trim_above",
    "reduce_or_sell_above",
    "risk_review_below",
    "nav_action_discount_below",
    "nav_watch_discount_below",
    "nav_fair_value",
    "nav_premium_warning_above",
    "technical_signal_date",
    "support_low",
    "support_high",
    "resistance_low",
    "resistance_high",
    "breakout_level",
    "downside_watch_level",
    "trend_repair_level",
    "moving_average_state",
    "drawdown_state",
    "price_location_state",
    "technical_confidence",
    "regime_signal_date",
    "regime_state",
    "relative_strength",
    "sector_rotation_rank",
    "regime_confidence",
    "fundamental_benchmark_status",
    "fundamental_benchmark_latest_date",
    "fundamental_sector_peer_count",
    "fundamental_industry_peer_count",
    "fundamental_sector_benchmark_ticker",
    "fundamental_forward_pe",
    "fundamental_sector_forward_pe_median",
    "fundamental_sector_forward_pe_discount_pct",
    "fundamental_sector_forward_pe_percentile",
    "fundamental_net_margin",
    "fundamental_sector_net_margin_median",
    "fundamental_revenue_growth",
    "fundamental_sector_revenue_growth_median",
    "fundamental_valuation_gap",
    "fundamental_sector_valuation_gap_median",
    "fundamental_opportunity_score",
    "fundamental_sector_opportunity_score_median",
    "fundamental_relative_strength_vs_spy",
    "fundamental_relative_strength_vs_qqq",
    "fundamental_relative_strength_vs_sector",
    "fundamental_benchmark_warnings",
    "pending_notification_status",
    "notification_reason_codes",
    "notification_severity",
    "intraday_health_status",
    "intraday_market_session",
    "intraday_regular_market_hours",
    "intraday_health_warnings",
    "intraday_health_notes",
    "scheduler_reconciliation_status",
    "actual_heartbeat_command",
    "scheduler_warnings",
    "notification_delivery_failed_count",
    "pending_notification_count",
    "model_warnings",
    "outcome_status",
    "return_5d",
    "return_20d",
    "return_60d",
    "return_120d",
    "hit_target_flag",
    "hit_invalidation_flag",
    "max_favorable_excursion",
    "max_adverse_excursion",
    "held_flag",
    "quantity",
    "position_value",
    "position_weight",
    "sector_weight",
    "cash_available",
    "portfolio_review_category",
    "sizing_guidance",
    "max_add_value",
    "portfolio_warnings",
    "revision_score",
    "revision_signal_status",
    "revision_source_status",
    "revision_source_coverage_count",
    "revision_source_count",
    "revision_aggregate_confidence",
    "revision_source_disagreement",
    "revision_source_warnings",
    "revision_validation_status",
    "revision_evidence_decision",
    "revision_evidence_20d_hit_rate",
    "revision_evidence_warnings",
    "news_catalyst_score",
    "news_catalyst_signal_status",
    "news_catalyst_source_status",
    "news_catalyst_numeric_source_type",
    "news_catalyst_provider_native_upgrade_needed",
    "news_catalyst_provider_upgrade_status",
    "news_catalyst_source_count",
    "news_catalyst_aggregate_confidence",
    "news_catalyst_provider_numeric_coverage_count",
    "news_catalyst_text_derived_coverage_count",
    "news_catalyst_total_numeric_coverage_count",
    "news_catalyst_source_disagreement",
    "news_catalyst_source_warnings",
    "news_catalyst_coverage_priority",
    "news_catalyst_coverage_reason",
    "news_catalyst_provider_warnings",
    "news_catalyst_provider_upgrade_blockers",
    "news_catalyst_provider_native_rejected_rows",
    "news_catalyst_latest_provider_native_source_date",
    "news_catalyst_backfill_valid_rows",
    "news_catalyst_backfill_blank_placeholders",
    "news_catalyst_backfill_invalid_rows",
    "news_catalyst_projected_provider_native_coverage_count",
    "news_catalyst_provider_upgrade_still_blocked_tickers",
    "news_catalyst_backfill_apply_ready",
    "news_catalyst_valid_upgrade_tickers",
    "news_catalyst_projected_upgrade_delta",
    "news_catalyst_blocked_apply_reason",
    "news_catalyst_validation_status",
    "news_catalyst_warnings",
    "insider_activity_score",
    "insider_activity_signal_status",
    "insider_activity_source_status",
    "insider_activity_source_coverage_count",
    "insider_activity_source_rows",
    "insider_activity_latest_source_date",
    "insider_activity_validation_status",
    "insider_activity_warnings",
    "short_interest_score",
    "short_interest_signal_status",
    "short_interest_source_status",
    "short_interest_source_coverage_count",
    "short_interest_source_rows",
    "short_interest_latest_settlement_date",
    "short_interest_provider_export_valid_rows",
    "short_interest_provider_export_tickers",
    "short_interest_provider_cache_files",
    "short_interest_provider_latest_cache_timestamp",
    "short_interest_provider_fetchable_providers",
    "short_interest_provider_warnings",
    "short_interest_missing_coverage_tickers",
    "short_interest_valid_missing_row_tickers",
    "short_interest_provider_diagnostic_status",
    "short_interest_missing_coverage_blocked_apply_reason",
    "short_interest_percent_float",
    "short_interest_days_to_cover",
    "short_interest_change",
    "short_interest_validation_status",
    "short_interest_backfill_valid_rows",
    "short_interest_backfill_blank_placeholders",
    "short_interest_backfill_invalid_rows",
    "short_interest_projected_source_coverage_count",
    "short_interest_backfill_apply_ready",
    "short_interest_valid_import_tickers",
    "short_interest_blocked_import_reason",
    "short_interest_warnings",
    "trader_commentary_claim_count",
    "trader_commentary_onboarding_candidate_count",
    "trader_commentary_unmapped_instrument_count",
    "trader_commentary_alias_count",
    "trader_commentary_label_disposition_count",
    "trader_commentary_intentionally_unresolved_label_count",
    "trader_commentary_ignored_non_instrument_label_count",
    "scoreable_asset_count",
    "reference_asset_count",
    "trader_commentary_browser_capture_run_count",
    "trader_commentary_browser_capture_item_count",
    "trader_commentary_browser_capture_latest_run",
    "trader_commentary_browser_capture_warnings",
    "trader_commentary_discord_capture_run_count",
    "trader_commentary_discord_capture_item_count",
    "trader_commentary_discord_capture_latest_run",
    "trader_commentary_discord_capture_warnings",
    "trader_commentary_latest_claim_type",
    "trader_commentary_latest_claim_date",
    "trader_commentary_latest_direction",
    "trader_commentary_validation_status",
    "trader_commentary_hit_status",
    "trader_commentary_warnings",
    "option_provider_readiness",
    "option_provider_blocked_reason",
    "option_ibapi_status",
    "option_activation_status",
    "option_activation_blocked_reason",
    "minimum_option_chain_coverage",
    "minimum_option_review_count",
    "ibapi_repair_needed",
    "option_backfill_valid_rows",
    "option_projected_chain_coverage_count",
    "option_backfill_apply_ready",
    "option_backfill_blocked_reason",
    "option_chain_coverage_status",
    "option_chain_coverage_count",
    "option_chain_raw_coverage_count",
    "option_chain_missing_tickers",
    "option_chain_raw_missing_tickers",
    "option_chain_non_actionable_tickers",
    "option_chain_coverage_notes",
    "option_chain_valid_backfill_tickers",
    "option_chain_projected_coverage_count",
    "option_chain_coverage_apply_ready",
    "option_chain_coverage_blocked_reason",
    "option_chain_coverage_provider_blocked_reason",
    "option_review_category",
    "option_expiration_date",
    "option_strike",
    "option_mid_premium",
    "option_breakeven",
    "option_annualized_yield",
    "option_downside_buffer_pct",
    "option_assignment_notional",
    "option_risk_category",
    "option_cash_secured_requirement",
    "option_premium_income",
    "option_max_cash_secured_loss",
    "option_scenario_pl_5pct",
    "option_scenario_pl_10pct",
    "option_scenario_pl_20pct",
    "option_projected_assignment_weight",
    "option_cash_after_assignment",
    "option_max_contracts_advisory",
    "option_risk_warnings",
    "option_outcome_status",
    "option_expiration_status",
    "option_return_5d",
    "option_return_20d",
    "option_return_to_latest",
    "option_above_strike_flag",
    "option_above_breakeven_flag",
    "option_touched_strike_flag",
    "option_touched_breakeven_flag",
    "option_max_favorable_excursion",
    "option_max_adverse_excursion",
    "option_linked_position_count",
    "option_position_count",
    "option_lifecycle_status",
    "option_lifecycle_realized_pl",
    "option_lifecycle_open_pl_proxy",
    "option_lifecycle_assignment_notional",
    "option_lifecycle_unmatched_position_count",
    "option_lifecycle_warnings",
    "option_chain_row_count",
    "option_commentary_claim_count",
    "option_warnings",
    "advanced_signal_warnings",
)


@dataclass(frozen=True)
class ReportResult:
    path: Path
    run_date: date
    csv_path: Path | None = None


@dataclass(frozen=True)
class DailyReportRow:
    ticker: str
    asset_type: str | None
    current_price: float | None
    target_low: float | None
    base_target: float | None
    target_high: float | None
    valuation_gap: float | None
    opportunity_score: float | None
    confidence_score: float | None
    timing_score: float | None
    risk_score: float | None
    liquidity_score: float | None
    data_quality_score: float | None
    alert_type: str
    priority: str | None
    status: str | None
    main_reasons: str | None
    main_risks: str | None
    reason_codes: str | None
    risk_codes: str | None
    invalidation: str | None
    data_freshness: str
    range_state: str | None
    range_snapshot_timestamp: str | None
    strong_buy_below: float | None
    starter_buy_below: float | None
    add_below: float | None
    hold_low: float | None
    hold_high: float | None
    trim_above: float | None
    reduce_or_sell_above: float | None
    risk_review_below: float | None
    nav_action_discount_below: float | None
    nav_watch_discount_below: float | None
    nav_fair_value: float | None
    nav_premium_warning_above: float | None
    technical_signal_date: str | None
    support_low: float | None
    support_high: float | None
    resistance_low: float | None
    resistance_high: float | None
    breakout_level: float | None
    downside_watch_level: float | None
    trend_repair_level: float | None
    moving_average_state: str | None
    drawdown_state: str | None
    price_location_state: str | None
    technical_confidence: float | None
    regime_signal_date: str | None
    regime_state: str | None
    relative_strength: float | None
    sector_rotation_rank: int | None
    regime_confidence: float | None
    fundamental_benchmark_status: str | None
    fundamental_benchmark_latest_date: str | None
    fundamental_sector_peer_count: int | None
    fundamental_industry_peer_count: int | None
    fundamental_sector_benchmark_ticker: str | None
    fundamental_forward_pe: float | None
    fundamental_sector_forward_pe_median: float | None
    fundamental_sector_forward_pe_discount_pct: float | None
    fundamental_sector_forward_pe_percentile: float | None
    fundamental_net_margin: float | None
    fundamental_sector_net_margin_median: float | None
    fundamental_revenue_growth: float | None
    fundamental_sector_revenue_growth_median: float | None
    fundamental_valuation_gap: float | None
    fundamental_sector_valuation_gap_median: float | None
    fundamental_opportunity_score: float | None
    fundamental_sector_opportunity_score_median: float | None
    fundamental_relative_strength_vs_spy: float | None
    fundamental_relative_strength_vs_qqq: float | None
    fundamental_relative_strength_vs_sector: float | None
    fundamental_benchmark_warnings: str | None
    pending_notification_status: str | None
    notification_reason_codes: str | None
    notification_severity: str | None
    intraday_health_status: str | None
    intraday_market_session: str | None
    intraday_regular_market_hours: int | None
    intraday_health_warnings: str | None
    intraday_health_notes: str | None
    scheduler_reconciliation_status: str | None
    actual_heartbeat_command: str | None
    scheduler_warnings: str | None
    notification_delivery_failed_count: int | None
    pending_notification_count: int | None
    model_warnings: str | None
    outcome_status: str | None
    return_5d: float | None
    return_20d: float | None
    return_60d: float | None
    return_120d: float | None
    hit_target_flag: int | None
    hit_invalidation_flag: int | None
    max_favorable_excursion: float | None
    max_adverse_excursion: float | None
    held_flag: int | None
    quantity: float | None
    position_value: float | None
    position_weight: float | None
    sector_weight: float | None
    cash_available: float | None
    portfolio_review_category: str | None
    sizing_guidance: str | None
    max_add_value: float | None
    portfolio_warnings: str | None
    revision_score: float | None
    revision_signal_status: str | None
    revision_source_status: str | None
    revision_source_coverage_count: int | None
    revision_source_count: int | None
    revision_aggregate_confidence: float | None
    revision_source_disagreement: str | None
    revision_source_warnings: str | None
    revision_validation_status: str | None
    revision_evidence_decision: str | None
    revision_evidence_20d_hit_rate: float | None
    revision_evidence_warnings: str | None
    news_catalyst_score: float | None
    news_catalyst_signal_status: str | None
    news_catalyst_source_status: str | None
    news_catalyst_numeric_source_type: str | None
    news_catalyst_provider_native_upgrade_needed: bool | None
    news_catalyst_provider_upgrade_status: str | None
    news_catalyst_source_count: int | None
    news_catalyst_aggregate_confidence: float | None
    news_catalyst_provider_numeric_coverage_count: int | None
    news_catalyst_text_derived_coverage_count: int | None
    news_catalyst_total_numeric_coverage_count: int | None
    news_catalyst_source_disagreement: str | None
    news_catalyst_source_warnings: str | None
    news_catalyst_coverage_priority: int | None
    news_catalyst_coverage_reason: str | None
    news_catalyst_provider_warnings: str | None
    news_catalyst_provider_upgrade_blockers: str | None
    news_catalyst_provider_native_rejected_rows: int | None
    news_catalyst_latest_provider_native_source_date: str | None
    news_catalyst_backfill_valid_rows: int | None
    news_catalyst_backfill_blank_placeholders: int | None
    news_catalyst_backfill_invalid_rows: int | None
    news_catalyst_projected_provider_native_coverage_count: int | None
    news_catalyst_provider_upgrade_still_blocked_tickers: str | None
    news_catalyst_backfill_apply_ready: bool | None
    news_catalyst_valid_upgrade_tickers: str | None
    news_catalyst_projected_upgrade_delta: int | None
    news_catalyst_blocked_apply_reason: str | None
    news_catalyst_validation_status: str | None
    news_catalyst_warnings: str | None
    insider_activity_score: float | None
    insider_activity_signal_status: str | None
    insider_activity_source_status: str | None
    insider_activity_source_coverage_count: int | None
    insider_activity_source_rows: int | None
    insider_activity_latest_source_date: str | None
    insider_activity_validation_status: str | None
    insider_activity_warnings: str | None
    short_interest_score: float | None
    short_interest_signal_status: str | None
    short_interest_source_status: str | None
    short_interest_source_coverage_count: int | None
    short_interest_source_rows: int | None
    short_interest_latest_settlement_date: str | None
    short_interest_provider_export_valid_rows: int | None
    short_interest_provider_export_tickers: str | None
    short_interest_provider_cache_files: int | None
    short_interest_provider_latest_cache_timestamp: str | None
    short_interest_provider_fetchable_providers: str | None
    short_interest_provider_warnings: str | None
    short_interest_missing_coverage_tickers: str | None
    short_interest_valid_missing_row_tickers: str | None
    short_interest_provider_diagnostic_status: str | None
    short_interest_missing_coverage_blocked_apply_reason: str | None
    short_interest_percent_float: float | None
    short_interest_days_to_cover: float | None
    short_interest_change: float | None
    short_interest_validation_status: str | None
    short_interest_backfill_valid_rows: int | None
    short_interest_backfill_blank_placeholders: int | None
    short_interest_backfill_invalid_rows: int | None
    short_interest_projected_source_coverage_count: int | None
    short_interest_backfill_apply_ready: bool | None
    short_interest_valid_import_tickers: str | None
    short_interest_blocked_import_reason: str | None
    short_interest_warnings: str | None
    trader_commentary_claim_count: int | None
    trader_commentary_onboarding_candidate_count: int | None
    trader_commentary_unmapped_instrument_count: int | None
    trader_commentary_alias_count: int | None
    trader_commentary_label_disposition_count: int | None
    trader_commentary_intentionally_unresolved_label_count: int | None
    trader_commentary_ignored_non_instrument_label_count: int | None
    scoreable_asset_count: int | None
    reference_asset_count: int | None
    trader_commentary_browser_capture_run_count: int | None
    trader_commentary_browser_capture_item_count: int | None
    trader_commentary_browser_capture_latest_run: str | None
    trader_commentary_browser_capture_warnings: str | None
    trader_commentary_discord_capture_run_count: int | None
    trader_commentary_discord_capture_item_count: int | None
    trader_commentary_discord_capture_latest_run: str | None
    trader_commentary_discord_capture_warnings: str | None
    trader_commentary_latest_claim_type: str | None
    trader_commentary_latest_claim_date: str | None
    trader_commentary_latest_direction: str | None
    trader_commentary_validation_status: str | None
    trader_commentary_hit_status: str | None
    trader_commentary_warnings: str | None
    option_provider_readiness: str | None
    option_provider_blocked_reason: str | None
    option_ibapi_status: str | None
    option_activation_status: str | None
    option_activation_blocked_reason: str | None
    minimum_option_chain_coverage: str | None
    minimum_option_review_count: int | None
    ibapi_repair_needed: bool | None
    option_backfill_valid_rows: int | None
    option_projected_chain_coverage_count: int | None
    option_backfill_apply_ready: bool | None
    option_backfill_blocked_reason: str | None
    option_chain_coverage_status: str | None
    option_chain_coverage_count: str | None
    option_chain_raw_coverage_count: str | None
    option_chain_missing_tickers: str | None
    option_chain_raw_missing_tickers: str | None
    option_chain_non_actionable_tickers: str | None
    option_chain_coverage_notes: str | None
    option_chain_valid_backfill_tickers: str | None
    option_chain_projected_coverage_count: str | None
    option_chain_coverage_apply_ready: bool | None
    option_chain_coverage_blocked_reason: str | None
    option_chain_coverage_provider_blocked_reason: str | None
    option_review_category: str | None
    option_expiration_date: str | None
    option_strike: float | None
    option_mid_premium: float | None
    option_breakeven: float | None
    option_annualized_yield: float | None
    option_downside_buffer_pct: float | None
    option_assignment_notional: float | None
    option_risk_category: str | None
    option_cash_secured_requirement: float | None
    option_premium_income: float | None
    option_max_cash_secured_loss: float | None
    option_scenario_pl_5pct: float | None
    option_scenario_pl_10pct: float | None
    option_scenario_pl_20pct: float | None
    option_projected_assignment_weight: float | None
    option_cash_after_assignment: float | None
    option_max_contracts_advisory: int | None
    option_risk_warnings: str | None
    option_outcome_status: str | None
    option_expiration_status: str | None
    option_return_5d: float | None
    option_return_20d: float | None
    option_return_to_latest: float | None
    option_above_strike_flag: int | None
    option_above_breakeven_flag: int | None
    option_touched_strike_flag: int | None
    option_touched_breakeven_flag: int | None
    option_max_favorable_excursion: float | None
    option_max_adverse_excursion: float | None
    option_linked_position_count: int | None
    option_position_count: int | None
    option_lifecycle_status: str | None
    option_lifecycle_realized_pl: float | None
    option_lifecycle_open_pl_proxy: float | None
    option_lifecycle_assignment_notional: float | None
    option_lifecycle_unmatched_position_count: int | None
    option_lifecycle_warnings: str | None
    option_chain_row_count: int | None
    option_commentary_claim_count: int | None
    option_warnings: str | None
    advanced_signal_warnings: str | None


def latest_report_path(reports_dir: Path) -> Path | None:
    if not reports_dir.exists():
        return None
    reports = sorted(reports_dir.glob("*-daily-report.md"))
    if not reports:
        return None
    return reports[-1]


def latest_csv_report_path(reports_dir: Path) -> Path | None:
    if not reports_dir.exists():
        return None
    reports = sorted(reports_dir.glob("*-daily-report.csv"))
    if not reports:
        return None
    return reports[-1]


def _display_path(path: Path, project_root: Path) -> str:
    try:
        return str(path.resolve().relative_to(project_root.resolve()))
    except ValueError:
        return str(path)


def _none_as_empty(value: object | None) -> object:
    return "" if value is None else value


def _fmt_number(value: float | None, decimals: int = 2) -> str:
    if value is None:
        return ""
    return f"{value:.{decimals}f}"


def _fmt_percent(value: float | None) -> str:
    if value is None:
        return ""
    return f"{value:.2%}"


def _fmt_target_range(row: DailyReportRow) -> str:
    if row.target_low is None and row.base_target is None and row.target_high is None:
        return ""
    return (
        f"{_fmt_number(row.target_low)} / "
        f"{_fmt_number(row.base_target)} / "
        f"{_fmt_number(row.target_high)}"
    )


def _fmt_upside_to_base(row: DailyReportRow) -> str:
    if row.current_price in (None, 0) or row.base_target is None:
        return ""
    return _fmt_percent(row.base_target / row.current_price - 1)


def _fmt_gap_to_low(row: DailyReportRow) -> str:
    if row.current_price in (None, 0) or row.target_low is None:
        return ""
    return _fmt_percent(row.target_low / row.current_price - 1)


def _clean_cell(value: str | None) -> str:
    if not value:
        return ""
    return value.replace("|", "/").replace("\r", " ").replace("\n", " ")


def _join_unique(values: Iterable[str | None]) -> str | None:
    parts: list[str] = []
    for value in values:
        if not value:
            continue
        for item in value.split(","):
            cleaned = item.strip()
            if cleaned and cleaned not in parts:
                parts.append(cleaned)
    return ", ".join(parts) if parts else None


def _first_float(*values: float | None) -> float | None:
    for value in values:
        if value is not None:
            return value
    return None


def _first_text(*values: str | None) -> str | None:
    for value in values:
        if value:
            return value
    return None


def _news_numeric_source_type(source: str | None) -> str:
    if not source:
        return "missing"
    source_parts = {
        item.strip().lower().replace("-", "_").replace(" ", "_")
        for item in source.split(",")
        if item.strip()
    }
    has_text = "news_text_backfill" in source_parts
    has_provider = bool(source_parts - {"news_text_backfill"})
    if has_text and has_provider:
        return "mixed"
    if has_text:
        return "text_derived"
    if has_provider:
        return "provider_numeric"
    return "missing"


def _priority_rank(priority: str | None) -> int:
    return {"high": 0, "medium": 1, "low": 2, "none": 3}.get(
        (priority or "").lower(),
        4,
    )


def _build_data_freshness(
    price: PriceStatus | None,
    valuation: ValuationStatus | None,
    score: ScoreStatus | None,
    alert: AlertStatus | None,
    signal: SignalStatus | None,
    signal_outcome: SignalOutcomeStatus | None = None,
    news_catalyst_signal: object | None = None,
    insider_signal: object | None = None,
    short_interest_signal: object | None = None,
    option_income: object | None = None,
    option_outcome: object | None = None,
) -> str:
    news_signal_date = getattr(news_catalyst_signal, "latest_signal_date", None)
    news_validation_date = getattr(news_catalyst_signal, "validation_date", None)
    insider_signal_date = getattr(insider_signal, "latest_signal_date", None)
    insider_validation_date = getattr(insider_signal, "validation_date", None)
    short_interest_signal_date = getattr(short_interest_signal, "latest_signal_date", None)
    short_interest_validation_date = getattr(short_interest_signal, "validation_date", None)
    option_chain_timestamp = getattr(option_income, "latest_snapshot_timestamp", None)
    option_review_date = getattr(option_income, "review_date", None)
    option_outcome_date = getattr(option_outcome, "outcome_date", None)
    parts = [
        f"price:{price.latest_price_date if price and price.latest_price_date else 'none'}",
        f"target:{valuation.target_date if valuation and valuation.target_date else 'none'}",
        f"score:{score.score_date if score and score.score_date else 'none'}",
        f"alert:{alert.alert_timestamp if alert and alert.alert_timestamp else 'none'}",
        f"signal:{signal.latest_signal_date if signal and signal.latest_signal_date else 'none'}",
        "signal_validation:"
        f"{signal_outcome.outcome_date if signal_outcome and signal_outcome.outcome_date else 'none'}",
        f"news_catalyst:{news_signal_date or 'none'}",
        f"news_catalyst_validation:{news_validation_date or 'none'}",
        f"insider_activity:{insider_signal_date or 'none'}",
        f"insider_activity_validation:{insider_validation_date or 'none'}",
        f"short_interest:{short_interest_signal_date or 'none'}",
        f"short_interest_validation:{short_interest_validation_date or 'none'}",
        f"option_chain:{option_chain_timestamp or 'none'}",
        f"option_review:{option_review_date or 'none'}",
        f"option_outcome:{option_outcome_date or 'none'}",
    ]
    return "; ".join(parts)


def _latest_outcomes_by_ticker(
    outcomes: list[AlertOutcomeStatus],
) -> dict[str, AlertOutcomeStatus]:
    by_ticker: dict[str, AlertOutcomeStatus] = {}
    for outcome in outcomes:
        if outcome.ticker not in by_ticker:
            by_ticker[outcome.ticker] = outcome
    return by_ticker


def _latest_signal_outcomes_by_ticker(
    outcomes: list[SignalOutcomeStatus],
) -> dict[str, SignalOutcomeStatus]:
    by_ticker: dict[str, SignalOutcomeStatus] = {}
    for outcome in outcomes:
        if outcome.ticker not in by_ticker:
            by_ticker[outcome.ticker] = outcome
    return by_ticker


def build_daily_report_rows(
    config: AppConfig,
    database_status: DatabaseStatus,
) -> list[DailyReportRow]:
    if not config.database_path.exists() or "assets" not in database_status.existing_tables:
        return []

    price_by_ticker = {
        status.ticker: status
        for status in (
            price_statuses(config.database_path, config.market_data_stale_after_days)
            if "prices" in database_status.existing_tables
            else []
        )
    }
    valuation_by_ticker = {
        status.ticker: status
        for status in (
            valuation_statuses(config.database_path)
            if "targets" in database_status.existing_tables
            else []
        )
    }
    score_by_ticker = {
        status.ticker: status
        for status in (
            score_statuses(config.database_path)
            if "scores" in database_status.existing_tables
            else []
        )
    }
    alert_by_ticker = {
        status.ticker: status
        for status in (
            alert_statuses(config.database_path)
            if "alerts" in database_status.existing_tables
            else []
        )
    }
    outcome_by_ticker = _latest_outcomes_by_ticker(
        outcome_statuses(config.database_path)
        if "alert_outcomes" in database_status.existing_tables
        else []
    )
    portfolio_by_ticker = {
        status.ticker: status
        for status in (
            portfolio_statuses(config.database_path)
            if "portfolio_reviews" in database_status.existing_tables
            else []
        )
    }
    signal_by_ticker = {
        status.ticker: status
        for status in (
            signal_statuses(config.database_path)
            if "signals" in database_status.existing_tables
            else []
        )
    }
    signal_outcome_by_ticker = _latest_signal_outcomes_by_ticker(
        signal_outcome_statuses(
            config.database_path,
            signal_family="analyst_revision",
            signal_name="analyst_revision.composite",
        )
        if "signal_outcomes" in database_status.existing_tables
        else []
    )
    news_catalyst_by_ticker = {
        status.ticker: status
        for status in (
            news_catalyst_statuses(config)
            if "signals" in database_status.existing_tables
            else []
        )
    }
    insider_by_ticker = {
        status.ticker: status
        for status in (
            insider_statuses(config)
            if "signals" in database_status.existing_tables
            else []
        )
    }
    short_interest_by_ticker = {
        status.ticker: status
        for status in (
            short_interest_statuses(config)
            if "signals" in database_status.existing_tables
            else []
        )
    }
    option_income_by_ticker = {
        status.ticker: status
        for status in (
            option_income_statuses(config.database_path)
            if "option_income_reviews" in database_status.existing_tables
            else []
        )
    }
    option_risk_by_ticker = {
        status.ticker: status
        for status in (
            option_risk_statuses(config.database_path)
            if "option_risk_reviews" in database_status.existing_tables
            else []
        )
    }
    option_outcome_by_ticker = {
        status.ticker: status
        for status in (
            option_outcome_statuses(config.database_path)
            if "option_review_outcomes" in database_status.existing_tables
            else []
        )
    }
    option_position_by_ticker = {
        status.ticker: status
        for status in (
            option_position_statuses(config.database_path)
            if "option_position_ledger" in database_status.existing_tables
            else []
        )
    }
    option_lifecycle_by_ticker = {
        status.ticker: status
        for status in (
            option_lifecycle_statuses(config.database_path)
            if "option_position_lifecycle_reviews" in database_status.existing_tables
            else []
        )
    }
    option_fetch_tickers = tuple(
        asset.ticker for asset in option_fetch_assets(config, max_tickers=0)
    )
    option_provider = option_provider_status(config, check_connectivity=False)
    option_backfill_status = validate_options_chain_backfill(config)
    option_activation = option_chain_activation_status(config)
    option_coverage_plan = option_chain_coverage_plan(config)
    option_chain_availability = option_chain_availability_statuses(config)
    option_chain_missing_tickers = option_coverage_plan.effective_missing_tickers
    trader_commentary_by_ticker = {
        status.ticker: status
        for status in (
            trader_commentary_statuses(config.database_path)
            if "trader_commentary_claims" in database_status.existing_tables
            else []
        )
    }
    commentary_onboarding_plan = build_commentary_onboarding_plan(config)
    scoreable_asset_count = count_scoreable_assets(config.database_path)
    reference_asset_count = count_reference_assets(config.database_path)
    trader_commentary_browser_capture_run_count = (
        count_rows_by_table(config.database_path, "trader_commentary_browser_capture_runs")
        if "trader_commentary_browser_capture_runs" in database_status.existing_tables
        else 0
    )
    trader_commentary_browser_capture_item_count = (
        count_rows_by_table(config.database_path, "trader_commentary_browser_capture_items")
        if "trader_commentary_browser_capture_items" in database_status.existing_tables
        else 0
    )
    trader_commentary_browser_capture_latest_run = (
        latest_trader_commentary_browser_capture_timestamp(config.database_path)
        if "trader_commentary_browser_capture_runs" in database_status.existing_tables
        else None
    )
    trader_commentary_browser_capture_runs = (
        list_trader_commentary_browser_capture_runs(config.database_path)
        if "trader_commentary_browser_capture_runs" in database_status.existing_tables
        else []
    )
    trader_commentary_browser_capture_warnings = (
        trader_commentary_browser_capture_runs[0].warnings
        if trader_commentary_browser_capture_runs
        else None
    )
    trader_commentary_discord_capture_run_count = (
        count_rows_by_table(config.database_path, "trader_commentary_discord_capture_runs")
        if "trader_commentary_discord_capture_runs" in database_status.existing_tables
        else 0
    )
    trader_commentary_discord_capture_item_count = (
        count_rows_by_table(config.database_path, "trader_commentary_discord_capture_items")
        if "trader_commentary_discord_capture_items" in database_status.existing_tables
        else 0
    )
    trader_commentary_discord_capture_latest_run = (
        latest_trader_commentary_discord_capture_timestamp(config.database_path)
        if "trader_commentary_discord_capture_runs" in database_status.existing_tables
        else None
    )
    trader_commentary_discord_capture_runs = (
        list_trader_commentary_discord_capture_runs(config.database_path)
        if "trader_commentary_discord_capture_runs" in database_status.existing_tables
        else []
    )
    trader_commentary_discord_capture_warnings = (
        trader_commentary_discord_capture_runs[0].warnings
        if trader_commentary_discord_capture_runs
        else None
    )
    technical_by_ticker = {
        status.ticker: status
        for status in (
            technical_signal_statuses(config.database_path)
            if "technical_signal_snapshots" in database_status.existing_tables
            else []
        )
    }
    regime_by_ticker = {
        status.ticker: status
        for status in (
            regime_signal_statuses(config.database_path)
            if "regime_signal_snapshots" in database_status.existing_tables
            else []
        )
    }
    fundamental_benchmark_by_ticker = {
        status.ticker: status
        for status in (
            fundamental_comparison_statuses(config.database_path)
            if "fundamental_comparison_snapshots" in database_status.existing_tables
            else []
        )
        if status.comparison_date
    }
    range_by_ticker = {
        status.ticker: status
        for status in (
            range_statuses(config.database_path)
            if "range_snapshots" in database_status.existing_tables
            else []
        )
    }
    pending_notification_by_ticker = {
        event.ticker: event
        for event in (
            list_notification_events(config.database_path, status="pending")
            if "notification_events" in database_status.existing_tables
            else []
        )
    }
    from .tom_loop import tom_loop_status

    current_intraday_health = intraday_health(config)
    current_tom_loop = tom_loop_status(config)
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
    notification_delivery_failed_count = (
        notification_delivery_count(config.database_path, status="failed")
        if "notification_deliveries" in database_status.existing_tables
        else 0
    )
    insider_source_status = insider_source_status_report(config)
    insider_source_by_ticker = {
        status.ticker: status for status in insider_source_status.statuses
    }
    short_interest_source_status = short_interest_source_status_report(config)
    short_interest_source_by_ticker = {
        status.ticker: status for status in short_interest_source_status.statuses
    }
    short_interest_provider = short_interest_provider_status(config)
    insider_source_rows: dict[str, int] = {}
    if "insider_transaction_source_snapshots" in database_status.existing_tables:
        for snapshot in list_insider_transaction_source_snapshots(config.database_path):
            insider_source_rows[snapshot.ticker] = insider_source_rows.get(snapshot.ticker, 0) + 1
    short_interest_source_rows: dict[str, int] = {}
    if "short_interest_source_snapshots" in database_status.existing_tables:
        for snapshot in list_short_interest_source_snapshots(config.database_path):
            short_interest_source_rows[snapshot.ticker] = (
                short_interest_source_rows.get(snapshot.ticker, 0) + 1
            )
    latest_insider_source_date = (
        latest_insider_transaction_source_date(config.database_path)
        if "insider_transaction_source_snapshots" in database_status.existing_tables
        else None
    )
    latest_short_interest_source_date = (
        latest_short_interest_settlement_date(config.database_path)
        if "short_interest_source_snapshots" in database_status.existing_tables
        else None
    )
    revision_evidence = build_revision_evidence(config)
    revision_source_status = revision_source_status_report(config)
    revision_source_by_ticker = {
        status.ticker: status for status in revision_source_status.statuses
    }
    news_catalyst_source_status = news_catalyst_source_status_report(config)
    news_catalyst_plan = news_catalyst_coverage_plan(config, write_template=False)
    news_catalyst_upgrade_status = news_catalyst_provider_upgrade_status(config)
    news_catalyst_upgrade_preview = preview_news_catalyst_provider_upgrade(config)
    news_catalyst_backfill_apply_status = news_catalyst_provider_backfill_apply_status(config)
    short_interest_backfill_status = validate_short_interest_backfill(config)
    short_interest_provider = short_interest_provider_status(config)
    short_interest_missing_plan = short_interest_missing_coverage_plan(config)
    news_catalyst_plan_by_ticker = {
        item.ticker: item for item in news_catalyst_plan.items
    }
    news_catalyst_source_by_ticker = {
        status.ticker: status for status in news_catalyst_source_status.statuses
    }

    tickers = sorted(
        set(price_by_ticker)
        | set(valuation_by_ticker)
        | set(score_by_ticker)
        | set(alert_by_ticker)
        | set(outcome_by_ticker)
        | set(portfolio_by_ticker)
        | set(signal_by_ticker)
        | set(signal_outcome_by_ticker)
        | set(news_catalyst_by_ticker)
        | set(news_catalyst_source_by_ticker)
        | set(insider_by_ticker)
        | set(insider_source_by_ticker)
        | set(insider_source_rows)
        | set(short_interest_by_ticker)
        | set(option_income_by_ticker)
        | set(option_risk_by_ticker)
        | set(option_outcome_by_ticker)
        | set(option_position_by_ticker)
        | set(option_lifecycle_by_ticker)
        | set(short_interest_source_by_ticker)
        | set(short_interest_source_rows)
        | set(trader_commentary_by_ticker)
        | set(technical_by_ticker)
        | set(regime_by_ticker)
        | set(fundamental_benchmark_by_ticker)
        | set(range_by_ticker)
        | set(pending_notification_by_ticker)
    )
    rows: list[DailyReportRow] = []
    for ticker in tickers:
        price = price_by_ticker.get(ticker)
        valuation = valuation_by_ticker.get(ticker)
        score = score_by_ticker.get(ticker)
        alert = alert_by_ticker.get(ticker)
        outcome = outcome_by_ticker.get(ticker)
        portfolio = portfolio_by_ticker.get(ticker)
        signal = signal_by_ticker.get(ticker)
        signal_outcome = signal_outcome_by_ticker.get(ticker)
        news_catalyst = news_catalyst_by_ticker.get(ticker)
        news_catalyst_plan_item = news_catalyst_plan_by_ticker.get(ticker)
        insider = insider_by_ticker.get(ticker)
        insider_source = insider_source_by_ticker.get(ticker)
        short_interest = short_interest_by_ticker.get(ticker)
        option_income = option_income_by_ticker.get(ticker)
        option_risk = option_risk_by_ticker.get(ticker)
        option_outcome = option_outcome_by_ticker.get(ticker)
        option_position = option_position_by_ticker.get(ticker)
        option_lifecycle = option_lifecycle_by_ticker.get(ticker)
        short_interest_source = short_interest_source_by_ticker.get(ticker)
        trader_commentary = trader_commentary_by_ticker.get(ticker)
        technical = technical_by_ticker.get(ticker)
        regime = regime_by_ticker.get(ticker) or regime_by_ticker.get("SPY")
        fundamental_benchmark = fundamental_benchmark_by_ticker.get(ticker)
        range_status = range_by_ticker.get(ticker)
        notification = pending_notification_by_ticker.get(ticker)
        source_status = revision_source_by_ticker.get(ticker)
        news_source_status = news_catalyst_source_by_ticker.get(ticker)
        asset_type = _first_text(
            alert.asset_type if alert else None,
            score.asset_type if score else None,
            portfolio.asset_type if portfolio else None,
            range_status.asset_type if range_status else None,
            insider_source.asset_type if insider_source else None,
            short_interest_source.asset_type if short_interest_source else None,
            option_income.asset_type if option_income else None,
            option_outcome.asset_type if option_outcome else None,
            option_position.asset_type if option_position else None,
        )
        current_price = _first_float(
            range_status.current_price if range_status else None,
            alert.current_price if alert else None,
            score.current_price if score else None,
            valuation.current_price if valuation else None,
            price.current_price if price else None,
        )
        target_low = _first_float(
            alert.target_low if alert else None,
            valuation.target_low if valuation else None,
        )
        base_target = _first_float(
            alert.base_target if alert else None,
            valuation.base_target if valuation else None,
        )
        target_high = _first_float(
            alert.target_high if alert else None,
            valuation.target_high if valuation else None,
        )
        valuation_gap = _first_float(
            alert.valuation_gap if alert else None,
            valuation.valuation_gap if valuation else None,
        )

        alert_type = alert.alert_type if alert else None
        model_warnings = _join_unique(
            (
                valuation.data_warnings if valuation else None,
                score.data_warnings if score else None,
                alert.data_warnings if alert else None,
                range_status.data_warnings if range_status else None,
                option_income.risk_warnings if option_income else None,
                option_outcome.data_warnings if option_outcome else None,
                technical.data_warnings if technical else None,
                regime.data_warnings if regime else None,
            )
        )
        main_reasons = alert.main_reasons if alert else None
        main_risks = alert.main_risks if alert else None
        invalidation = alert.invalidation if alert else None

        if not alert_type:
            alert_type = "not_evaluated"

        rows.append(
            DailyReportRow(
                ticker=ticker,
                asset_type=asset_type,
                current_price=current_price,
                target_low=target_low,
                base_target=base_target,
                target_high=target_high,
                valuation_gap=valuation_gap,
                opportunity_score=_first_float(
                    alert.opportunity_score if alert else None,
                    score.opportunity_score if score else None,
                ),
                confidence_score=_first_float(
                    alert.confidence_score if alert else None,
                    score.confidence_score if score else None,
                ),
                timing_score=_first_float(
                    alert.timing_score if alert else None,
                    score.timing_score if score else None,
                ),
                risk_score=_first_float(
                    alert.risk_score if alert else None,
                    score.risk_score if score else None,
                ),
                liquidity_score=_first_float(
                    alert.liquidity_score if alert else None,
                    score.liquidity_score if score else None,
                ),
                data_quality_score=alert.data_quality_score if alert else None,
                alert_type=alert_type,
                priority=alert.priority if alert else None,
                status=alert.status if alert else None,
                main_reasons=main_reasons,
                main_risks=main_risks,
                reason_codes=alert.reason_codes if alert else None,
                risk_codes=alert.risk_codes if alert else None,
                invalidation=invalidation,
                data_freshness=_build_data_freshness(
                    price,
                    valuation,
                    score,
                    alert,
                    signal,
                    signal_outcome,
                    news_catalyst,
                    insider,
                    short_interest,
                    option_income,
                    option_outcome,
                ),
                range_state=range_status.range_state if range_status else None,
                range_snapshot_timestamp=(
                    range_status.snapshot_timestamp if range_status else None
                ),
                strong_buy_below=(
                    range_status.strong_buy_below if range_status else None
                ),
                starter_buy_below=(
                    range_status.starter_buy_below if range_status else None
                ),
                add_below=range_status.add_below if range_status else None,
                hold_low=range_status.hold_low if range_status else None,
                hold_high=range_status.hold_high if range_status else None,
                trim_above=range_status.trim_above if range_status else None,
                reduce_or_sell_above=(
                    range_status.reduce_or_sell_above if range_status else None
                ),
                risk_review_below=(
                    range_status.risk_review_below if range_status else None
                ),
                nav_action_discount_below=(
                    range_status.nav_action_discount_below if range_status else None
                ),
                nav_watch_discount_below=(
                    range_status.nav_watch_discount_below if range_status else None
                ),
                nav_fair_value=range_status.nav_fair_value if range_status else None,
                nav_premium_warning_above=(
                    range_status.nav_premium_warning_above if range_status else None
                ),
                technical_signal_date=_first_text(
                    range_status.technical_signal_date if range_status else None,
                    technical.signal_date if technical else None,
                ),
                support_low=_first_float(
                    range_status.support_low if range_status else None,
                    technical.support_low if technical else None,
                ),
                support_high=_first_float(
                    range_status.support_high if range_status else None,
                    technical.support_high if technical else None,
                ),
                resistance_low=_first_float(
                    range_status.resistance_low if range_status else None,
                    technical.resistance_low if technical else None,
                ),
                resistance_high=_first_float(
                    range_status.resistance_high if range_status else None,
                    technical.resistance_high if technical else None,
                ),
                breakout_level=_first_float(
                    range_status.breakout_level if range_status else None,
                    technical.breakout_level if technical else None,
                ),
                downside_watch_level=_first_float(
                    range_status.downside_watch_level if range_status else None,
                    technical.downside_watch_level if technical else None,
                ),
                trend_repair_level=_first_float(
                    range_status.trend_repair_level if range_status else None,
                    technical.trend_repair_level if technical else None,
                ),
                moving_average_state=_first_text(
                    range_status.moving_average_state if range_status else None,
                    technical.moving_average_state if technical else None,
                ),
                drawdown_state=_first_text(
                    range_status.drawdown_state if range_status else None,
                    technical.drawdown_state if technical else None,
                ),
                price_location_state=_first_text(
                    range_status.price_location_state if range_status else None,
                    technical.price_location_state if technical else None,
                ),
                technical_confidence=_first_float(
                    range_status.technical_confidence if range_status else None,
                    technical.confidence if technical else None,
                ),
                regime_signal_date=_first_text(
                    range_status.regime_signal_date if range_status else None,
                    regime.signal_date if regime else None,
                ),
                regime_state=_first_text(
                    range_status.regime_state if range_status else None,
                    regime.risk_state if regime else None,
                ),
                relative_strength=_first_float(
                    range_status.relative_strength if range_status else None,
                    regime.relative_strength if regime else None,
                ),
                sector_rotation_rank=(
                    range_status.sector_rotation_rank
                    if range_status and range_status.sector_rotation_rank is not None
                    else regime.sector_rotation_rank if regime else None
                ),
                regime_confidence=_first_float(
                    range_status.regime_confidence if range_status else None,
                    regime.confidence if regime else None,
                ),
                fundamental_benchmark_status=(
                    fundamental_benchmark.benchmark_status
                    if fundamental_benchmark
                    else None
                ),
                fundamental_benchmark_latest_date=(
                    fundamental_benchmark.comparison_date
                    if fundamental_benchmark
                    else None
                ),
                fundamental_sector_peer_count=(
                    fundamental_benchmark.sector_peer_count
                    if fundamental_benchmark
                    else None
                ),
                fundamental_industry_peer_count=(
                    fundamental_benchmark.industry_peer_count
                    if fundamental_benchmark
                    else None
                ),
                fundamental_sector_benchmark_ticker=(
                    fundamental_benchmark.sector_benchmark_ticker
                    if fundamental_benchmark
                    else None
                ),
                fundamental_forward_pe=(
                    fundamental_benchmark.forward_pe if fundamental_benchmark else None
                ),
                fundamental_sector_forward_pe_median=(
                    fundamental_benchmark.sector_forward_pe_median
                    if fundamental_benchmark
                    else None
                ),
                fundamental_sector_forward_pe_discount_pct=(
                    fundamental_benchmark.sector_forward_pe_discount_pct
                    if fundamental_benchmark
                    else None
                ),
                fundamental_sector_forward_pe_percentile=(
                    fundamental_benchmark.sector_forward_pe_percentile
                    if fundamental_benchmark
                    else None
                ),
                fundamental_net_margin=(
                    fundamental_benchmark.net_margin if fundamental_benchmark else None
                ),
                fundamental_sector_net_margin_median=(
                    fundamental_benchmark.sector_net_margin_median
                    if fundamental_benchmark
                    else None
                ),
                fundamental_revenue_growth=(
                    fundamental_benchmark.revenue_growth
                    if fundamental_benchmark
                    else None
                ),
                fundamental_sector_revenue_growth_median=(
                    fundamental_benchmark.sector_revenue_growth_median
                    if fundamental_benchmark
                    else None
                ),
                fundamental_valuation_gap=(
                    fundamental_benchmark.valuation_gap
                    if fundamental_benchmark
                    else None
                ),
                fundamental_sector_valuation_gap_median=(
                    fundamental_benchmark.sector_valuation_gap_median
                    if fundamental_benchmark
                    else None
                ),
                fundamental_opportunity_score=(
                    fundamental_benchmark.opportunity_score
                    if fundamental_benchmark
                    else None
                ),
                fundamental_sector_opportunity_score_median=(
                    fundamental_benchmark.sector_opportunity_score_median
                    if fundamental_benchmark
                    else None
                ),
                fundamental_relative_strength_vs_spy=(
                    fundamental_benchmark.relative_strength_vs_spy
                    if fundamental_benchmark
                    else None
                ),
                fundamental_relative_strength_vs_qqq=(
                    fundamental_benchmark.relative_strength_vs_qqq
                    if fundamental_benchmark
                    else None
                ),
                fundamental_relative_strength_vs_sector=(
                    fundamental_benchmark.relative_strength_vs_sector
                    if fundamental_benchmark
                    else None
                ),
                fundamental_benchmark_warnings=(
                    fundamental_benchmark.data_warnings
                    if fundamental_benchmark
                    else None
                ),
                pending_notification_status=(
                    notification.status if notification else None
                ),
                notification_reason_codes=(
                    notification.reason_codes if notification else None
                ),
                notification_severity=(
                    notification.severity if notification else None
                ),
                intraday_health_status=current_intraday_health.status,
                intraday_market_session=current_intraday_health.market_session,
                intraday_regular_market_hours=(
                    1 if current_intraday_health.regular_market_hours else 0
                ),
                intraday_health_warnings=_join_unique(
                    (
                        ",".join(current_intraday_health.blockers),
                        ",".join(current_intraday_health.warnings),
                    )
                ),
                intraday_health_notes=",".join(current_intraday_health.notes),
                scheduler_reconciliation_status=scheduler_audit_result.status,
                actual_heartbeat_command=(
                    heartbeat_job.actual_command if heartbeat_job else None
                ),
                scheduler_warnings=",".join(scheduler_warning_codes),
                notification_delivery_failed_count=notification_delivery_failed_count,
                pending_notification_count=current_intraday_health.pending_notification_count,
                model_warnings=model_warnings,
                outcome_status=outcome.outcome_status if outcome else None,
                return_5d=outcome.return_5d if outcome else None,
                return_20d=outcome.return_20d if outcome else None,
                return_60d=outcome.return_60d if outcome else None,
                return_120d=outcome.return_120d if outcome else None,
                hit_target_flag=outcome.hit_target_flag if outcome else None,
                hit_invalidation_flag=outcome.hit_invalidation_flag if outcome else None,
                max_favorable_excursion=(
                    outcome.max_favorable_excursion if outcome else None
                ),
                max_adverse_excursion=(
                    outcome.max_adverse_excursion if outcome else None
                ),
                held_flag=portfolio.held_flag if portfolio else None,
                quantity=portfolio.quantity if portfolio else None,
                position_value=portfolio.position_value if portfolio else None,
                position_weight=portfolio.position_weight if portfolio else None,
                sector_weight=portfolio.sector_weight if portfolio else None,
                cash_available=portfolio.cash_available if portfolio else None,
                portfolio_review_category=(
                    portfolio.review_category if portfolio else None
                ),
                sizing_guidance=portfolio.sizing_guidance if portfolio else None,
                max_add_value=portfolio.max_add_value if portfolio else None,
                portfolio_warnings=portfolio.data_warnings if portfolio else None,
                revision_score=_first_float(
                    score.revision_score if score else None,
                    signal.composite_score if signal else None,
                ),
                revision_signal_status=(
                    f"{signal.composite_direction or 'neutral'}"
                    f"@{signal.latest_signal_date}"
                    if signal and signal.latest_signal_date
                    else "missing"
                ),
                revision_source_status=(
                    f"source_backed@{source_status.signal_date}"
                    if source_status
                    and source_status.source_backed
                    and source_status.signal_date
                    else "missing"
                ),
                revision_source_coverage_count=(
                    revision_source_status.source_backed_ticker_count
                ),
                revision_source_count=source_status.source_count if source_status else None,
                revision_aggregate_confidence=(
                    source_status.aggregate_confidence if source_status else None
                ),
                revision_source_disagreement=(
                    source_status.source_disagreement if source_status else None
                ),
                revision_source_warnings=(
                    ", ".join(source_status.warnings)
                    if source_status and source_status.warnings
                    else None
                ),
                revision_validation_status=(
                    f"{signal_outcome.outcome_status or 'none'}"
                    f"@{signal_outcome.outcome_date}"
                    if signal_outcome and signal_outcome.outcome_date
                    else "missing"
                ),
                revision_evidence_decision=revision_evidence.decision,
                revision_evidence_20d_hit_rate=revision_evidence.hit_rate_20d,
                revision_evidence_warnings=", ".join(revision_evidence.warnings)
                if revision_evidence.warnings
                else None,
                news_catalyst_score=(
                    news_catalyst.composite_score if news_catalyst else None
                ),
                news_catalyst_signal_status=(
                    f"{news_catalyst.composite_direction or 'neutral'}"
                    f"@{news_catalyst.latest_signal_date}"
                    if news_catalyst and news_catalyst.latest_signal_date
                    else "missing"
                ),
                news_catalyst_source_status=(
                    f"source_backed@{news_source_status.signal_date}"
                    if news_source_status
                    and news_source_status.source_backed
                    and news_source_status.signal_date
                    else "missing"
                ),
                news_catalyst_numeric_source_type=(
                    _news_numeric_source_type(news_source_status.source)
                    if news_source_status
                    else "missing"
                ),
                news_catalyst_provider_native_upgrade_needed=(
                    news_source_status.provider_native_upgrade_needed
                    if news_source_status
                    else None
                ),
                news_catalyst_provider_upgrade_status=(
                    news_catalyst_upgrade_status.status
                ),
                news_catalyst_source_count=(
                    news_source_status.source_count if news_source_status else None
                ),
                news_catalyst_aggregate_confidence=(
                    news_source_status.aggregate_confidence if news_source_status else None
                ),
                news_catalyst_provider_numeric_coverage_count=(
                    news_catalyst_source_status.provider_numeric_ticker_count
                ),
                news_catalyst_text_derived_coverage_count=(
                    news_catalyst_source_status.text_derived_ticker_count
                ),
                news_catalyst_total_numeric_coverage_count=(
                    news_catalyst_source_status.total_numeric_ticker_count
                ),
                news_catalyst_source_disagreement=(
                    news_source_status.source_disagreement if news_source_status else None
                ),
                news_catalyst_source_warnings=(
                    ", ".join(news_source_status.warnings)
                    if news_source_status and news_source_status.warnings
                    else None
                ),
                news_catalyst_coverage_priority=(
                    news_catalyst_plan_item.priority
                    if news_catalyst_plan_item
                    else None
                ),
                news_catalyst_coverage_reason=(
                    news_catalyst_plan_item.reason
                    if news_catalyst_plan_item
                    else None
                ),
                news_catalyst_provider_warnings=(
                    ", ".join(news_catalyst_plan.provider_warning_summary)
                    if news_catalyst_plan.provider_warning_summary
                    else None
                ),
                news_catalyst_provider_upgrade_blockers=(
                    ", ".join(news_catalyst_upgrade_status.provider_blockers)
                    if news_catalyst_upgrade_status.provider_blockers
                    else None
                ),
                news_catalyst_provider_native_rejected_rows=(
                    news_catalyst_source_status.provider_native_rejected_row_count
                ),
                news_catalyst_latest_provider_native_source_date=(
                    news_catalyst_source_status.latest_provider_native_source_date
                ),
                news_catalyst_backfill_valid_rows=(
                    news_catalyst_upgrade_preview.validation.valid_row_count
                ),
                news_catalyst_backfill_blank_placeholders=(
                    news_catalyst_upgrade_preview.validation.blank_placeholder_count
                ),
                news_catalyst_backfill_invalid_rows=(
                    news_catalyst_upgrade_preview.validation.invalid_row_count
                ),
                news_catalyst_projected_provider_native_coverage_count=(
                    news_catalyst_upgrade_preview.projected_provider_native_ticker_count
                ),
                news_catalyst_provider_upgrade_still_blocked_tickers=(
                    ", ".join(news_catalyst_upgrade_preview.still_blocked_tickers)
                    if news_catalyst_upgrade_preview.still_blocked_tickers
                    else None
                ),
                news_catalyst_backfill_apply_ready=(
                    news_catalyst_backfill_apply_status.backfill_apply_ready
                ),
                news_catalyst_valid_upgrade_tickers=(
                    ", ".join(news_catalyst_backfill_apply_status.valid_upgrade_tickers)
                    if news_catalyst_backfill_apply_status.valid_upgrade_tickers
                    else None
                ),
                news_catalyst_projected_upgrade_delta=(
                    news_catalyst_backfill_apply_status.projected_upgrade_delta
                ),
                news_catalyst_blocked_apply_reason=(
                    news_catalyst_backfill_apply_status.blocked_apply_reason
                ),
                news_catalyst_validation_status=(
                    f"{news_catalyst.validation_status or 'none'}"
                    f"@{news_catalyst.validation_date}"
                    if news_catalyst and news_catalyst.validation_date
                    else "missing"
                ),
                news_catalyst_warnings=(
                    news_catalyst.data_warnings if news_catalyst else None
                ),
                insider_activity_score=(
                    insider.composite_score if insider else None
                ),
                insider_activity_signal_status=(
                    f"{insider.composite_direction or 'neutral'}"
                    f"@{insider.latest_signal_date}"
                    if insider and insider.latest_signal_date
                    else "missing"
                ),
                insider_activity_source_status=(
                    insider_source.status if insider_source else "missing_source"
                ),
                insider_activity_source_coverage_count=(
                    insider_source_status.covered_ticker_count
                ),
                insider_activity_source_rows=(
                    insider_source.source_row_count
                    if insider_source
                    else insider_source_rows.get(ticker)
                ),
                insider_activity_latest_source_date=(
                    _first_text(
                        insider_source.latest_transaction_date if insider_source else None,
                        insider_source.latest_filing_date if insider_source else None,
                        latest_insider_source_date,
                    )
                ),
                insider_activity_validation_status=(
                    f"{insider.validation_status or 'none'}"
                    f"@{insider.validation_date}"
                    if insider and insider.validation_date
                    else "missing"
                ),
                insider_activity_warnings=(
                    _join_unique(
                        (
                            insider.data_warnings if insider else None,
                            ", ".join(insider_source.warnings)
                            if insider_source and insider_source.warnings
                            else None,
                        )
                    )
                ),
                short_interest_score=(
                    short_interest.composite_score if short_interest else None
                ),
                short_interest_signal_status=(
                    f"{short_interest.composite_direction or 'neutral'}"
                    f"@{short_interest.latest_signal_date}"
                    if short_interest and short_interest.latest_signal_date
                    else "missing"
                ),
                short_interest_source_status=(
                    short_interest_source.status
                    if short_interest_source
                    else "missing_source"
                ),
                short_interest_source_coverage_count=(
                    short_interest_source_status.source_backed_ticker_count
                ),
                short_interest_source_rows=(
                    short_interest_source.source_row_count
                    if short_interest_source
                    else short_interest_source_rows.get(ticker)
                ),
                short_interest_latest_settlement_date=(
                    _first_text(
                        short_interest_source.latest_settlement_date
                        if short_interest_source
                        else None,
                        latest_short_interest_source_date,
                    )
                ),
                short_interest_provider_export_valid_rows=(
                    short_interest_provider.provider_export_valid_row_count
                ),
                short_interest_provider_export_tickers=(
                    ", ".join(short_interest_provider.provider_export_tickers)
                    if short_interest_provider.provider_export_tickers
                    else None
                ),
                short_interest_provider_cache_files=short_interest_provider.cache_file_count,
                short_interest_provider_latest_cache_timestamp=(
                    short_interest_provider.latest_cache_timestamp
                ),
                short_interest_provider_fetchable_providers=(
                    ", ".join(short_interest_provider.fetchable_providers)
                    if short_interest_provider.fetchable_providers
                    else None
                ),
                short_interest_provider_warnings=(
                    ", ".join(short_interest_provider.warnings)
                    if short_interest_provider.warnings
                    else None
                ),
                short_interest_missing_coverage_tickers=(
                    ", ".join(short_interest_missing_plan.missing_tickers)
                    if short_interest_missing_plan.missing_tickers
                    else None
                ),
                short_interest_valid_missing_row_tickers=(
                    ", ".join(short_interest_missing_plan.valid_missing_tickers)
                    if short_interest_missing_plan.valid_missing_tickers
                    else None
                ),
                short_interest_provider_diagnostic_status=(
                    ", ".join(
                        f"{item.ticker}:{item.classification}"
                        for item in short_interest_missing_plan.diagnostics
                    )
                    if short_interest_missing_plan.diagnostics
                    else None
                ),
                short_interest_missing_coverage_blocked_apply_reason=(
                    short_interest_missing_plan.blocked_apply_reason
                ),
                short_interest_percent_float=(
                    short_interest_source.percent_float if short_interest_source else None
                ),
                short_interest_days_to_cover=(
                    short_interest_source.days_to_cover if short_interest_source else None
                ),
                short_interest_change=(
                    short_interest_source.change_pct if short_interest_source else None
                ),
                short_interest_validation_status=(
                    f"{short_interest.validation_status or 'none'}"
                    f"@{short_interest.validation_date}"
                    if short_interest and short_interest.validation_date
                    else "missing"
                ),
                short_interest_backfill_valid_rows=(
                    short_interest_backfill_status.valid_row_count
                ),
                short_interest_backfill_blank_placeholders=(
                    short_interest_backfill_status.blank_placeholder_count
                ),
                short_interest_backfill_invalid_rows=(
                    short_interest_backfill_status.invalid_row_count
                ),
                short_interest_projected_source_coverage_count=(
                    short_interest_backfill_status.projected_source_backed_count
                ),
                short_interest_backfill_apply_ready=(
                    short_interest_backfill_status.apply_ready
                ),
                short_interest_valid_import_tickers=(
                    ", ".join(short_interest_backfill_status.valid_tickers)
                    if short_interest_backfill_status.valid_tickers
                    else None
                ),
                short_interest_blocked_import_reason=(
                    short_interest_backfill_status.blocked_import_reason
                ),
                short_interest_warnings=(
                    _join_unique(
                        (
                            short_interest.data_warnings if short_interest else None,
                            ", ".join(short_interest_source.warnings)
                            if short_interest_source and short_interest_source.warnings
                            else None,
                        )
                    )
                ),
                trader_commentary_claim_count=(
                    trader_commentary.claim_count if trader_commentary else None
                ),
                trader_commentary_onboarding_candidate_count=(
                    commentary_onboarding_plan.onboardable_count
                ),
                trader_commentary_unmapped_instrument_count=(
                    commentary_onboarding_plan.unmapped_count
                ),
                trader_commentary_alias_count=commentary_onboarding_plan.alias_count,
                trader_commentary_label_disposition_count=(
                    commentary_onboarding_plan.label_disposition_count
                ),
                trader_commentary_intentionally_unresolved_label_count=(
                    commentary_onboarding_plan.intentionally_unresolved_count
                ),
                trader_commentary_ignored_non_instrument_label_count=(
                    commentary_onboarding_plan.ignored_non_instrument_count
                ),
                scoreable_asset_count=scoreable_asset_count,
                reference_asset_count=reference_asset_count,
                trader_commentary_browser_capture_run_count=(
                    trader_commentary_browser_capture_run_count
                ),
                trader_commentary_browser_capture_item_count=(
                    trader_commentary_browser_capture_item_count
                ),
                trader_commentary_browser_capture_latest_run=(
                    trader_commentary_browser_capture_latest_run
                ),
                trader_commentary_browser_capture_warnings=(
                    trader_commentary_browser_capture_warnings
                ),
                trader_commentary_discord_capture_run_count=(
                    trader_commentary_discord_capture_run_count
                ),
                trader_commentary_discord_capture_item_count=(
                    trader_commentary_discord_capture_item_count
                ),
                trader_commentary_discord_capture_latest_run=(
                    trader_commentary_discord_capture_latest_run
                ),
                trader_commentary_discord_capture_warnings=(
                    trader_commentary_discord_capture_warnings
                ),
                trader_commentary_latest_claim_type=(
                    trader_commentary.latest_claim_type if trader_commentary else None
                ),
                trader_commentary_latest_claim_date=(
                    trader_commentary.latest_claim_date if trader_commentary else None
                ),
                trader_commentary_latest_direction=(
                    trader_commentary.latest_direction if trader_commentary else None
                ),
                trader_commentary_validation_status=(
                    f"{trader_commentary.latest_outcome_status or 'none'}"
                    f"@{trader_commentary.latest_outcome_date}"
                    if trader_commentary and trader_commentary.latest_outcome_date
                    else "missing"
                ),
                trader_commentary_hit_status=(
                    trader_commentary.latest_hit_status if trader_commentary else None
                ),
                trader_commentary_warnings=(
                    trader_commentary.data_warnings if trader_commentary else None
                ),
                option_provider_readiness=option_provider.readiness_status,
                option_provider_blocked_reason=option_provider.blocked_reason,
                option_ibapi_status=option_provider.ibapi_status,
                option_activation_status=option_activation.activation_status,
                option_activation_blocked_reason=option_activation.blocked_reason,
                minimum_option_chain_coverage=option_activation.minimum_option_chain_coverage,
                minimum_option_review_count=option_activation.minimum_option_review_count,
                ibapi_repair_needed=option_activation.ibapi_repair_needed,
                option_backfill_valid_rows=option_backfill_status.valid_row_count,
                option_projected_chain_coverage_count=(
                    option_backfill_status.projected_loaded_ticker_count
                ),
                option_backfill_apply_ready=option_backfill_status.apply_ready,
                option_backfill_blocked_reason=option_backfill_status.blocked_reason,
                option_chain_coverage_status=option_coverage_plan.coverage_status,
                option_chain_coverage_count=option_coverage_plan.effective_coverage_count,
                option_chain_raw_coverage_count=option_coverage_plan.raw_coverage_count,
                option_chain_missing_tickers=(
                    ", ".join(option_coverage_plan.prioritized_missing_tickers)
                    if option_coverage_plan.prioritized_missing_tickers
                    else None
                ),
                option_chain_raw_missing_tickers=(
                    ", ".join(option_coverage_plan.raw_missing_tickers)
                    if option_coverage_plan.raw_missing_tickers
                    else None
                ),
                option_chain_non_actionable_tickers=(
                    ", ".join(option_coverage_plan.non_actionable_tickers)
                    if option_coverage_plan.non_actionable_tickers
                    else None
                ),
                option_chain_coverage_notes=(
                    ", ".join(option_coverage_plan.notes)
                    if option_coverage_plan.notes
                    else None
                ),
                option_chain_valid_backfill_tickers=(
                    ", ".join(option_coverage_plan.valid_backfill_tickers)
                    if option_coverage_plan.valid_backfill_tickers
                    else None
                ),
                option_chain_projected_coverage_count=(
                    f"{option_coverage_plan.projected_loaded_ticker_count}/"
                    f"{option_coverage_plan.fetch_universe_ticker_count}"
                ),
                option_chain_coverage_apply_ready=option_coverage_plan.apply_ready,
                option_chain_coverage_blocked_reason=option_coverage_plan.blocked_reason,
                option_chain_coverage_provider_blocked_reason=(
                    option_coverage_plan.provider_blocked_reason
                ),
                advanced_signal_warnings=_join_unique(
                    (
                        ", ".join(source_status.warnings)
                        if source_status and source_status.warnings
                        else None,
                        signal.data_warnings if signal else None,
                        signal_outcome.data_warnings if signal_outcome else None,
                        ", ".join(news_source_status.warnings)
                        if news_source_status and news_source_status.warnings
                        else None,
                        news_catalyst.data_warnings if news_catalyst else None,
                        ", ".join(insider_source.warnings)
                        if insider_source and insider_source.warnings
                        else None,
                        insider.data_warnings if insider else None,
                        ", ".join(short_interest_source.warnings)
                        if short_interest_source and short_interest_source.warnings
                        else None,
                        short_interest.data_warnings if short_interest else None,
                        ", ".join(short_interest_provider.warnings)
                        if short_interest_provider.warnings
                        else None,
                        trader_commentary.data_warnings
                        if trader_commentary
                        else None,
                        trader_commentary_browser_capture_warnings,
                        trader_commentary_discord_capture_warnings,
                        fundamental_benchmark.data_warnings
                        if fundamental_benchmark
                        else None,
                        option_income.risk_warnings if option_income else None,
                        option_risk.risk_warnings if option_risk else None,
                        option_outcome.data_warnings if option_outcome else None,
                        option_position.data_warnings if option_position else None,
                    )
                ),
                option_review_category=option_income.review_category if option_income else None,
                option_expiration_date=option_income.expiration_date if option_income else None,
                option_strike=option_income.strike if option_income else None,
                option_mid_premium=option_income.mid_premium if option_income else None,
                option_breakeven=option_income.breakeven if option_income else None,
                option_annualized_yield=option_income.annualized_yield if option_income else None,
                option_downside_buffer_pct=option_income.downside_buffer_pct
                if option_income
                else None,
                option_assignment_notional=option_income.assignment_notional
                if option_income
                else None,
                option_risk_category=option_risk.risk_category if option_risk else None,
                option_cash_secured_requirement=option_risk.cash_secured_requirement
                if option_risk
                else None,
                option_premium_income=option_risk.premium_income if option_risk else None,
                option_max_cash_secured_loss=option_risk.max_cash_secured_loss
                if option_risk
                else None,
                option_scenario_pl_5pct=option_risk.scenario_pl_5pct
                if option_risk
                else None,
                option_scenario_pl_10pct=option_risk.scenario_pl_10pct
                if option_risk
                else None,
                option_scenario_pl_20pct=option_risk.scenario_pl_20pct
                if option_risk
                else None,
                option_projected_assignment_weight=option_risk.projected_assignment_weight
                if option_risk
                else None,
                option_cash_after_assignment=option_risk.cash_after_assignment
                if option_risk
                else None,
                option_max_contracts_advisory=option_risk.max_contracts_advisory
                if option_risk
                else None,
                option_risk_warnings=option_risk.risk_warnings if option_risk else None,
                option_outcome_status=(
                    option_outcome.outcome_status
                    if option_outcome and option_outcome.outcome_count
                    else None
                ),
                option_expiration_status=(
                    option_outcome.expiration_status
                    if option_outcome and option_outcome.outcome_count
                    else None
                ),
                option_return_5d=(
                    option_outcome.return_5d
                    if option_outcome and option_outcome.outcome_count
                    else None
                ),
                option_return_20d=(
                    option_outcome.return_20d
                    if option_outcome and option_outcome.outcome_count
                    else None
                ),
                option_return_to_latest=(
                    option_outcome.return_to_latest
                    if option_outcome and option_outcome.outcome_count
                    else None
                ),
                option_above_strike_flag=(
                    option_outcome.above_strike_flag
                    if option_outcome and option_outcome.outcome_count
                    else None
                ),
                option_above_breakeven_flag=(
                    option_outcome.above_breakeven_flag
                    if option_outcome and option_outcome.outcome_count
                    else None
                ),
                option_touched_strike_flag=(
                    option_outcome.touched_strike_flag
                    if option_outcome and option_outcome.outcome_count
                    else None
                ),
                option_touched_breakeven_flag=(
                    option_outcome.touched_breakeven_flag
                    if option_outcome and option_outcome.outcome_count
                    else None
                ),
                option_max_favorable_excursion=(
                    option_outcome.max_favorable_excursion
                    if option_outcome and option_outcome.outcome_count
                    else None
                ),
                option_max_adverse_excursion=(
                    option_outcome.max_adverse_excursion
                    if option_outcome and option_outcome.outcome_count
                    else None
                ),
                option_linked_position_count=(
                    option_outcome.linked_position_count
                    if option_outcome and option_outcome.outcome_count
                    else None
                ),
                option_position_count=(
                    option_position.position_count if option_position else None
                ),
                option_lifecycle_status=(
                    option_lifecycle.lifecycle_status
                    if option_lifecycle and option_lifecycle.lifecycle_review_count
                    else None
                ),
                option_lifecycle_realized_pl=(
                    option_lifecycle.realized_pl_total
                    if option_lifecycle and option_lifecycle.lifecycle_review_count
                    else None
                ),
                option_lifecycle_open_pl_proxy=(
                    option_lifecycle.open_pl_proxy_total
                    if option_lifecycle and option_lifecycle.lifecycle_review_count
                    else None
                ),
                option_lifecycle_assignment_notional=(
                    option_lifecycle.assignment_notional_total
                    if option_lifecycle and option_lifecycle.lifecycle_review_count
                    else None
                ),
                option_lifecycle_unmatched_position_count=(
                    option_lifecycle.unmatched_position_count
                    if option_lifecycle and option_lifecycle.lifecycle_review_count
                    else None
                ),
                option_lifecycle_warnings=(
                    option_lifecycle.risk_warnings
                    if option_lifecycle and option_lifecycle.lifecycle_review_count
                    else None
                ),
                option_chain_row_count=option_income.option_chain_rows if option_income else None,
                option_commentary_claim_count=option_income.commentary_claim_count
                if option_income
                else None,
                option_warnings=_join_unique(
                    (
                        option_income.risk_warnings if option_income else None,
                        option_risk.risk_warnings if option_risk else None,
                        option_outcome.data_warnings if option_outcome else None,
                        option_position.data_warnings if option_position else None,
                        option_lifecycle.risk_warnings if option_lifecycle else None,
                    )
                ),
            )
        )
    return rows


def _build_report_csv_body(rows: list[DailyReportRow]) -> list[dict[str, object]]:
    output_rows: list[dict[str, object]] = []
    for row in rows:
        payload = asdict(row)
        output_rows.append(
            {column: _none_as_empty(payload.get(column)) for column in REPORT_CSV_COLUMNS}
        )
    return output_rows


def _row_table(rows: list[DailyReportRow]) -> str:
    if not rows:
        return "No alert evaluations yet."
    lines = []
    for row in rows:
        lines.append(
            "| ".join(
                (
                    row.ticker,
                    row.asset_type or "",
                    row.alert_type,
                    row.priority or "",
                    row.status or "",
                    _fmt_number(row.current_price),
                    _fmt_target_range(row),
                    _fmt_percent(row.valuation_gap),
                    _fmt_number(row.opportunity_score),
                    _fmt_number(row.confidence_score),
                    _fmt_number(row.timing_score),
                    _fmt_number(row.risk_score),
                    _clean_cell(row.reason_codes),
                    _clean_cell(row.risk_codes),
                    _clean_cell(row.model_warnings),
                )
            )
        )
    return "\n".join(lines)


def _range_levels_text(row: DailyReportRow) -> str:
    if row.asset_type == "etf":
        return (
            "action_discount<="
            f"{_fmt_number(row.nav_action_discount_below)}; "
            "watch_discount<="
            f"{_fmt_number(row.nav_watch_discount_below)}; "
            f"nav={_fmt_number(row.nav_fair_value)}; "
            "premium_warning>="
            f"{_fmt_number(row.nav_premium_warning_above)}"
        )
    return (
        f"strong<={_fmt_number(row.strong_buy_below)}; "
        f"starter<={_fmt_number(row.starter_buy_below)}; "
        f"add<={_fmt_number(row.add_below)}; "
        f"hold={_fmt_number(row.hold_low)}-{_fmt_number(row.hold_high)}; "
        f"trim>={_fmt_number(row.trim_above)}; "
        f"reduce>={_fmt_number(row.reduce_or_sell_above)}"
    )


def _range_table(rows: list[DailyReportRow]) -> str:
    range_rows = [row for row in rows if row.range_state]
    if not range_rows:
        return "No range snapshots yet."
    lines = []
    for row in sorted(range_rows, key=lambda item: item.ticker):
        notification = row.pending_notification_status or "none"
        if row.notification_severity:
            notification = f"{notification}:{row.notification_severity}"
        lines.append(
            "| ".join(
                (
                    row.ticker,
                    row.asset_type or "",
                    row.range_state or "",
                    _fmt_number(row.current_price),
                    _range_levels_text(row),
                    row.range_snapshot_timestamp or "",
                    notification,
                    _clean_cell(row.notification_reason_codes),
                    _clean_cell(row.model_warnings),
                )
            )
        )
    return "\n".join(lines)


def _technical_regime_table(rows: list[DailyReportRow]) -> str:
    signal_rows = [
        row
        for row in rows
        if row.technical_signal_date or row.regime_signal_date
    ]
    if not signal_rows:
        return "No technical or regime snapshots yet."
    lines = []
    for row in sorted(signal_rows, key=lambda item: item.ticker):
        support = (
            f"{_fmt_number(row.support_low)}-{_fmt_number(row.support_high)}"
            if row.support_low is not None or row.support_high is not None
            else ""
        )
        resistance = (
            f"{_fmt_number(row.resistance_low)}-{_fmt_number(row.resistance_high)}"
            if row.resistance_low is not None or row.resistance_high is not None
            else ""
        )
        lines.append(
            "| ".join(
                (
                    row.ticker,
                    row.asset_type or "",
                    _fmt_number(row.current_price),
                    support,
                    resistance,
                    _fmt_number(row.breakout_level),
                    _fmt_number(row.downside_watch_level),
                    _fmt_number(row.trend_repair_level),
                    row.moving_average_state or "",
                    row.price_location_state or "",
                    row.regime_state or "",
                    _fmt_number(row.relative_strength, 4),
                    str(row.sector_rotation_rank or ""),
                    _clean_cell(row.model_warnings),
                )
            )
        )
    return "\n".join(lines)


def _fundamental_benchmark_table(rows: list[DailyReportRow]) -> str:
    benchmark_rows = [
        row
        for row in rows
        if row.fundamental_benchmark_latest_date
        or row.fundamental_sector_peer_count
        or row.fundamental_benchmark_warnings
    ]
    if not benchmark_rows:
        return "No fundamental benchmark snapshots yet."
    lines = []
    for row in sorted(benchmark_rows, key=lambda item: item.ticker):
        lines.append(
            "| ".join(
                (
                    row.ticker,
                    row.fundamental_benchmark_status or "",
                    str(row.fundamental_sector_peer_count or 0),
                    row.fundamental_sector_benchmark_ticker or "",
                    _fmt_number(row.fundamental_forward_pe),
                    _fmt_number(row.fundamental_sector_forward_pe_median),
                    _fmt_percent(row.fundamental_sector_forward_pe_discount_pct),
                    _fmt_percent(row.fundamental_relative_strength_vs_spy),
                    _fmt_percent(row.fundamental_relative_strength_vs_sector),
                    _clean_cell(row.fundamental_benchmark_warnings),
                )
            )
        )
    return "\n".join(lines)


def _fmt_flag(value: int | None) -> str:
    if value is None:
        return ""
    return str(bool(value))


def _outcome_table(rows: list[DailyReportRow]) -> str:
    outcome_rows = [row for row in rows if row.outcome_status]
    if not outcome_rows:
        return "No alert outcomes yet."
    lines = []
    for row in sorted(outcome_rows, key=lambda item: item.ticker):
        lines.append(
            "| ".join(
                (
                    row.ticker,
                    row.asset_type,
                    row.alert_type,
                    row.outcome_status or "",
                    _fmt_percent(row.return_5d),
                    _fmt_percent(row.return_20d),
                    _fmt_percent(row.return_60d),
                    _fmt_percent(row.return_120d),
                    _fmt_flag(row.hit_target_flag),
                    _fmt_flag(row.hit_invalidation_flag),
                    _fmt_percent(row.max_favorable_excursion),
                    _fmt_percent(row.max_adverse_excursion),
                )
            )
        )
    return "\n".join(lines)


def _portfolio_table(rows: list[DailyReportRow]) -> str:
    portfolio_rows = [row for row in rows if row.portfolio_review_category]
    if not portfolio_rows:
        return "No portfolio reviews yet."
    lines = []
    for row in sorted(portfolio_rows, key=lambda item: item.ticker):
        lines.append(
            "| ".join(
                (
                    row.ticker,
                    row.asset_type or "",
                    str(bool(row.held_flag)) if row.held_flag is not None else "",
                    _fmt_number(row.quantity, 4),
                    _fmt_number(row.position_value),
                    _fmt_percent(row.position_weight),
                    _fmt_percent(row.sector_weight),
                    _fmt_number(row.cash_available),
                    row.portfolio_review_category or "",
                    _fmt_number(row.max_add_value),
                    _clean_cell(row.sizing_guidance),
                    _clean_cell(row.portfolio_warnings),
                )
            )
        )
    return "\n".join(lines)


def _options_table(rows: list[DailyReportRow]) -> str:
    option_rows = [
        row
        for row in rows
        if row.option_chain_row_count
        or row.option_review_category
        or row.option_outcome_status
        or row.option_position_count
        or row.option_lifecycle_status
    ]
    if not option_rows:
        return "No option-chain rows or sell-put reviews yet."
    lines = []
    for row in sorted(option_rows, key=lambda item: item.ticker):
        lines.append(
            "| ".join(
                (
                    row.ticker,
                    row.asset_type or "",
                    row.option_review_category or "not_reviewed",
                    row.option_risk_category or "not_risk_reviewed",
                    row.option_outcome_status or "not_validated",
                    row.option_lifecycle_status or "not_lifecycle_reviewed",
                    row.option_expiration_status or "",
                    row.option_expiration_date or "",
                    _fmt_number(row.option_strike),
                    _fmt_number(row.option_mid_premium),
                    _fmt_number(row.option_breakeven),
                    _fmt_percent(row.option_annualized_yield),
                    _fmt_percent(row.option_downside_buffer_pct),
                    _fmt_number(row.option_assignment_notional),
                    _fmt_number(row.option_cash_secured_requirement),
                    _fmt_number(row.option_scenario_pl_10pct),
                    _fmt_number(row.option_lifecycle_realized_pl),
                    _fmt_number(row.option_lifecycle_open_pl_proxy),
                    _fmt_number(row.option_lifecycle_assignment_notional),
                    _fmt_percent(row.option_return_5d),
                    _fmt_percent(row.option_return_20d),
                    _fmt_percent(row.option_return_to_latest),
                    str(bool(row.option_above_strike_flag))
                    if row.option_above_strike_flag is not None
                    else "",
                    str(bool(row.option_above_breakeven_flag))
                    if row.option_above_breakeven_flag is not None
                    else "",
                    str(row.option_position_count or 0),
                    str(row.option_lifecycle_unmatched_position_count or 0),
                    str(row.option_chain_row_count or 0),
                    str(row.option_commentary_claim_count or 0),
                    _clean_cell(row.option_warnings),
                )
            )
        )
    return "\n".join(lines)


def _advanced_signal_table(rows: list[DailyReportRow]) -> str:
    if not rows:
        return "No active assets."
    lines = []
    for row in sorted(rows, key=lambda item: item.ticker):
        lines.append(
            "| ".join(
                (
                    row.ticker,
                    row.asset_type or "",
                    _fmt_number(row.revision_score),
                    row.revision_signal_status or "",
                    (
                        f"{row.revision_source_status or ''}"
                        f" sources={row.revision_source_count or 0}"
                        f" confidence={_fmt_number(row.revision_aggregate_confidence) or 'none'}"
                    ),
                    row.revision_validation_status or "",
                    row.revision_evidence_decision or "",
                    _fmt_number(row.news_catalyst_score),
                    row.news_catalyst_signal_status or "",
                    (
                        f"{row.news_catalyst_source_status or ''}"
                        f" type={row.news_catalyst_numeric_source_type or 'missing'}"
                        f" sources={row.news_catalyst_source_count or 0}"
                        f" confidence={_fmt_number(row.news_catalyst_aggregate_confidence) or 'none'}"
                    ),
                    row.news_catalyst_validation_status or "",
                    _fmt_number(row.insider_activity_score),
                    row.insider_activity_signal_status or "",
                    (
                        f"{row.insider_activity_source_status or 'missing_source'}"
                        f" coverage={row.insider_activity_source_coverage_count or 0}"
                        f" sources={row.insider_activity_source_rows or 0}"
                        f" latest={row.insider_activity_latest_source_date or 'none'}"
                    ),
                    row.insider_activity_validation_status or "",
                    _fmt_number(row.short_interest_score),
                    row.short_interest_signal_status or "",
                    (
                        f"{row.short_interest_source_status or 'missing_source'}"
                        f" coverage={row.short_interest_source_coverage_count or 0}"
                        f" sources={row.short_interest_source_rows or 0}"
                        f" latest={row.short_interest_latest_settlement_date or 'none'}"
                    ),
                    row.short_interest_validation_status or "",
                    (
                        f"claims={row.trader_commentary_claim_count or 0}"
                        f" latest={row.trader_commentary_latest_claim_type or 'none'}"
                        f"@{row.trader_commentary_latest_claim_date or 'none'}"
                        f" browser_runs={row.trader_commentary_browser_capture_run_count or 0}"
                        f" browser_items={row.trader_commentary_browser_capture_item_count or 0}"
                        f" discord_runs={row.trader_commentary_discord_capture_run_count or 0}"
                        f" discord_items={row.trader_commentary_discord_capture_item_count or 0}"
                    ),
                    row.trader_commentary_validation_status or "",
                    _clean_cell(
                        _join_unique(
                            (
                                row.revision_source_disagreement,
                                row.news_catalyst_source_disagreement,
                                row.news_catalyst_source_warnings,
                                row.news_catalyst_warnings,
                                row.insider_activity_warnings,
                                row.short_interest_warnings,
                                row.trader_commentary_warnings,
                                row.advanced_signal_warnings,
                            )
                        )
                    ),
                )
            )
        )
    return "\n".join(lines)


def _executive_table(rows: list[DailyReportRow]) -> str:
    active_rows = [
        row
        for row in rows
        if row.alert_type not in {"no_alert", "not_evaluated", "skipped"}
        and (row.status or "").lower() == "open"
    ]
    if not active_rows:
        return "No active alerts."
    lines = []
    for row in sorted(
        active_rows,
        key=lambda item: (_priority_rank(item.priority), -(item.opportunity_score or 0.0)),
    ):
        lines.append(
            "| ".join(
                (
                    row.ticker,
                    row.alert_type,
                    row.priority or "",
                    _fmt_number(row.current_price),
                    _fmt_target_range(row),
                    _fmt_percent(row.valuation_gap),
                    _fmt_number(row.opportunity_score),
                    _clean_cell(row.main_reasons or row.reason_codes),
                )
            )
        )
    return "\n".join(lines)


def _equity_detail_sections(rows: list[DailyReportRow]) -> str:
    equity_rows = [row for row in rows if row.asset_type == "equity"]
    if not equity_rows:
        return "No equity alert rows yet."

    sections = []
    for row in sorted(equity_rows, key=lambda item: item.ticker):
        sections.append(
            "\n".join(
                (
                    f"### {row.ticker}",
                    "",
                    f"- Alert: `{row.alert_type}`"
                    f" / priority `{row.priority or 'none'}`"
                    f" / status `{row.status or 'none'}`",
                    f"- Price and target: `{_fmt_number(row.current_price)}`"
                    f" vs low/base/high `{_fmt_target_range(row) or 'none'}`",
                    f"- Upside/downside: base upside `{_fmt_upside_to_base(row) or 'none'}`"
                    f"; gap to target low `{_fmt_gap_to_low(row) or 'none'}`"
                    f"; valuation gap `{_fmt_percent(row.valuation_gap) or 'none'}`",
                    f"- Scores: opportunity `{_fmt_number(row.opportunity_score) or 'none'}`"
                    f"; confidence `{_fmt_number(row.confidence_score) or 'none'}`"
                    f"; timing `{_fmt_number(row.timing_score) or 'none'}`"
                    f"; risk `{_fmt_number(row.risk_score) or 'none'}`"
                    f"; liquidity `{_fmt_number(row.liquidity_score) or 'none'}`",
                    f"- Reason: `{_clean_cell(row.main_reasons) or 'none'}`",
                    f"- Risks: `{_clean_cell(row.main_risks or row.risk_codes) or 'none'}`",
                    f"- Invalidation: `{_clean_cell(row.invalidation) or 'none'}`",
                    f"- Data freshness: `{row.data_freshness}`",
                    f"- Model warnings: `{_clean_cell(row.model_warnings) or 'none'}`",
                )
            )
        )
    return "\n\n".join(sections)


def _csv_columns_text() -> str:
    return ", ".join(REPORT_CSV_COLUMNS)


def build_daily_report_body(
    config: AppConfig,
    database_status: DatabaseStatus,
    run_date: date | None = None,
) -> str:
    report_date = run_date or date.today()
    database_state = "initialized" if database_status.exists else "missing"
    asset_count = count_assets(config.database_path) if config.database_path.exists() else 0
    price_rows = (
        count_rows_by_table(config.database_path, "prices")
        if config.database_path.exists() and "prices" in database_status.existing_tables
        else 0
    )
    latest_price = (
        latest_price_date(config.database_path)
        if config.database_path.exists() and "prices" in database_status.existing_tables
        else None
    )
    fundamental_rows = (
        count_rows_by_table(config.database_path, "fundamentals")
        if config.database_path.exists() and "fundamentals" in database_status.existing_tables
        else 0
    )
    estimate_rows = (
        count_rows_by_table(config.database_path, "estimates")
        if config.database_path.exists() and "estimates" in database_status.existing_tables
        else 0
    )
    target_rows = (
        count_rows_by_table(config.database_path, "targets")
        if config.database_path.exists() and "targets" in database_status.existing_tables
        else 0
    )
    score_rows = (
        count_rows_by_table(config.database_path, "scores")
        if config.database_path.exists() and "scores" in database_status.existing_tables
        else 0
    )
    fundamental_benchmark_rows = (
        count_rows_by_table(config.database_path, "fundamental_benchmark_snapshots")
        if config.database_path.exists()
        and "fundamental_benchmark_snapshots" in database_status.existing_tables
        else 0
    )
    fundamental_comparison_rows = (
        count_rows_by_table(config.database_path, "fundamental_comparison_snapshots")
        if config.database_path.exists()
        and "fundamental_comparison_snapshots" in database_status.existing_tables
        else 0
    )
    latest_fundamental_benchmark = (
        latest_fundamental_benchmark_date(config.database_path)
        if config.database_path.exists()
        and "fundamental_comparison_snapshots" in database_status.existing_tables
        else None
    )
    research_recommendation_rows = (
        count_rows_by_table(config.database_path, "research_recommendation_candidates")
        if config.database_path.exists()
        and "research_recommendation_candidates" in database_status.existing_tables
        else 0
    )
    research_recommendation_pending_rows = 0
    research_recommendation_approved_rows = 0
    if (
        config.database_path.exists()
        and "research_recommendation_candidates" in database_status.existing_tables
    ):
        import sqlite3
        from contextlib import closing

        with closing(sqlite3.connect(config.database_path)) as connection:
            research_recommendation_pending_rows = int(
                connection.execute(
                    "SELECT COUNT(*) FROM research_recommendation_candidates WHERE status = 'pending'"
                ).fetchone()[0]
            )
            research_recommendation_approved_rows = int(
                connection.execute(
                    "SELECT COUNT(*) FROM research_recommendation_candidates WHERE status = 'approved'"
                ).fetchone()[0]
            )
    latest_research_recommendation = (
        latest_research_recommendation_date(config.database_path)
        if config.database_path.exists()
        and "research_recommendation_candidates" in database_status.existing_tables
        else None
    )
    signal_rows = (
        count_rows_by_table(config.database_path, "signals")
        if config.database_path.exists() and "signals" in database_status.existing_tables
        else 0
    )
    signal_outcome_rows = (
        count_rows_by_table(config.database_path, "signal_outcomes")
        if config.database_path.exists()
        and "signal_outcomes" in database_status.existing_tables
        else 0
    )
    revision_source_snapshot_rows = (
        count_rows_by_table(config.database_path, "analyst_revision_source_snapshots")
        if config.database_path.exists()
        and "analyst_revision_source_snapshots" in database_status.existing_tables
        else 0
    )
    revision_aggregate_rows = (
        count_rows_by_table(config.database_path, "analyst_revision_aggregates")
        if config.database_path.exists()
        and "analyst_revision_aggregates" in database_status.existing_tables
        else 0
    )
    news_catalyst_source_snapshot_rows = (
        count_rows_by_table(config.database_path, "news_catalyst_source_snapshots")
        if config.database_path.exists()
        and "news_catalyst_source_snapshots" in database_status.existing_tables
        else 0
    )
    news_catalyst_aggregate_rows = (
        count_rows_by_table(config.database_path, "news_catalyst_aggregates")
        if config.database_path.exists()
        and "news_catalyst_aggregates" in database_status.existing_tables
        else 0
    )
    insider_source_snapshot_rows = (
        count_rows_by_table(config.database_path, "insider_transaction_source_snapshots")
        if config.database_path.exists()
        and "insider_transaction_source_snapshots" in database_status.existing_tables
        else 0
    )
    short_interest_source_snapshot_rows = (
        count_rows_by_table(config.database_path, "short_interest_source_snapshots")
        if config.database_path.exists()
        and "short_interest_source_snapshots" in database_status.existing_tables
        else 0
    )
    option_chain_rows = (
        count_rows_by_table(config.database_path, "option_chain_snapshots")
        if config.database_path.exists()
        and "option_chain_snapshots" in database_status.existing_tables
        else 0
    )
    option_income_review_rows = (
        count_rows_by_table(config.database_path, "option_income_reviews")
        if config.database_path.exists()
        and "option_income_reviews" in database_status.existing_tables
        else 0
    )
    option_risk_review_rows = (
        count_rows_by_table(config.database_path, "option_risk_reviews")
        if config.database_path.exists()
        and "option_risk_reviews" in database_status.existing_tables
        else 0
    )
    option_review_outcome_rows = (
        count_rows_by_table(config.database_path, "option_review_outcomes")
        if config.database_path.exists()
        and "option_review_outcomes" in database_status.existing_tables
        else 0
    )
    option_position_rows = (
        count_rows_by_table(config.database_path, "option_position_ledger")
        if config.database_path.exists()
        and "option_position_ledger" in database_status.existing_tables
        else 0
    )
    option_lifecycle_rows = (
        count_rows_by_table(config.database_path, "option_position_lifecycle_reviews")
        if config.database_path.exists()
        and "option_position_lifecycle_reviews" in database_status.existing_tables
        else 0
    )
    option_status_rows = (
        option_income_statuses(config.database_path)
        if config.database_path.exists()
        and "option_income_reviews" in database_status.existing_tables
        else []
    )
    option_fetch_tickers = tuple(
        asset.ticker for asset in option_fetch_assets(config, max_tickers=0)
    )
    option_provider = option_provider_status(config, check_connectivity=False)
    option_backfill_status = validate_options_chain_backfill(config)
    option_activation = option_chain_activation_status(config)
    option_coverage_plan = option_chain_coverage_plan(config)
    option_chain_availability = option_chain_availability_statuses(config)
    option_chain_missing_tickers = option_coverage_plan.effective_missing_tickers
    trader_commentary_raw_rows = (
        count_rows_by_table(config.database_path, "trader_commentary_raw")
        if config.database_path.exists()
        and "trader_commentary_raw" in database_status.existing_tables
        else 0
    )
    trader_commentary_claim_rows = (
        count_rows_by_table(config.database_path, "trader_commentary_claims")
        if config.database_path.exists()
        and "trader_commentary_claims" in database_status.existing_tables
        else 0
    )
    trader_commentary_outcome_rows = (
        count_rows_by_table(config.database_path, "trader_commentary_claim_outcomes")
        if config.database_path.exists()
        and "trader_commentary_claim_outcomes" in database_status.existing_tables
        else 0
    )
    commentary_onboarding_plan = build_commentary_onboarding_plan(config)
    scoreable_asset_count = count_scoreable_assets(config.database_path)
    reference_asset_count = count_reference_assets(config.database_path)
    trader_commentary_browser_capture_run_rows = (
        count_rows_by_table(config.database_path, "trader_commentary_browser_capture_runs")
        if config.database_path.exists()
        and "trader_commentary_browser_capture_runs" in database_status.existing_tables
        else 0
    )
    trader_commentary_browser_capture_item_rows = (
        count_rows_by_table(config.database_path, "trader_commentary_browser_capture_items")
        if config.database_path.exists()
        and "trader_commentary_browser_capture_items" in database_status.existing_tables
        else 0
    )
    trader_commentary_discord_capture_run_rows = (
        count_rows_by_table(config.database_path, "trader_commentary_discord_capture_runs")
        if config.database_path.exists()
        and "trader_commentary_discord_capture_runs" in database_status.existing_tables
        else 0
    )
    trader_commentary_discord_capture_item_rows = (
        count_rows_by_table(config.database_path, "trader_commentary_discord_capture_items")
        if config.database_path.exists()
        and "trader_commentary_discord_capture_items" in database_status.existing_tables
        else 0
    )
    alert_rows = (
        count_rows_by_table(config.database_path, "alerts")
        if config.database_path.exists() and "alerts" in database_status.existing_tables
        else 0
    )
    outcome_rows = (
        count_rows_by_table(config.database_path, "alert_outcomes")
        if config.database_path.exists()
        and "alert_outcomes" in database_status.existing_tables
        else 0
    )
    range_rows = (
        count_rows_by_table(config.database_path, "range_snapshots")
        if config.database_path.exists()
        and "range_snapshots" in database_status.existing_tables
        else 0
    )
    technical_signal_rows = (
        count_rows_by_table(config.database_path, "technical_signal_snapshots")
        if config.database_path.exists()
        and "technical_signal_snapshots" in database_status.existing_tables
        else 0
    )
    regime_signal_rows = (
        count_rows_by_table(config.database_path, "regime_signal_snapshots")
        if config.database_path.exists()
        and "regime_signal_snapshots" in database_status.existing_tables
        else 0
    )
    notification_rows = (
        count_rows_by_table(config.database_path, "notification_events")
        if config.database_path.exists()
        and "notification_events" in database_status.existing_tables
        else 0
    )
    pending_notifications = (
        pending_notification_count(config.database_path)
        if config.database_path.exists()
        and "notification_events" in database_status.existing_tables
        else 0
    )
    portfolio_position_rows = (
        count_rows_by_table(config.database_path, "portfolio_positions")
        if config.database_path.exists()
        and "portfolio_positions" in database_status.existing_tables
        else 0
    )
    portfolio_cash_rows = (
        count_rows_by_table(config.database_path, "portfolio_cash")
        if config.database_path.exists()
        and "portfolio_cash" in database_status.existing_tables
        else 0
    )
    portfolio_review_rows = (
        count_rows_by_table(config.database_path, "portfolio_reviews")
        if config.database_path.exists()
        and "portfolio_reviews" in database_status.existing_tables
        else 0
    )
    account_option_position_rows = option_position_rows
    account_option_lifecycle_rows = option_lifecycle_rows
    from .account import option_position_readiness_diagnostics

    option_position_diagnostics = option_position_readiness_diagnostics(
        config,
        current_option_position_rows=account_option_position_rows,
        current_option_lifecycle_rows=account_option_lifecycle_rows,
    )
    account_missing_portfolio_context_rows = (
        sum(
            1
            for review in list_option_risk_reviews(config.database_path)
            if review.risk_category == "portfolio_context_needed"
            or "missing_portfolio_context" in (review.risk_warnings or "")
        )
        if config.database_path.exists()
        and "option_risk_reviews" in database_status.existing_tables
        else 0
    )
    account_context_blockers = []
    if portfolio_position_rows == 0:
        account_context_blockers.append("empty_portfolio_positions")
    if portfolio_cash_rows == 0:
        account_context_blockers.append("empty_portfolio_cash")
    if account_option_position_rows == 0:
        account_context_blockers.append("empty_options_positions")
    if account_option_lifecycle_rows == 0:
        account_context_blockers.append("no_option_lifecycle_rows")
    if account_missing_portfolio_context_rows:
        account_context_blockers.append("option_risk_missing_portfolio_context")
    if not account_context_blockers:
        account_context_activation_status = "active"
    elif portfolio_position_rows or portfolio_cash_rows or account_option_position_rows or account_option_lifecycle_rows:
        account_context_activation_status = "partial"
    else:
        account_context_activation_status = "not_configured"
    etf_nav_rows = (
        count_rows_by_table(config.database_path, "etf_navs")
        if config.database_path.exists() and "etf_navs" in database_status.existing_tables
        else 0
    )
    etf_holding_rows = (
        count_rows_by_table(config.database_path, "etf_holdings")
        if config.database_path.exists() and "etf_holdings" in database_status.existing_tables
        else 0
    )
    etf_feature_rows = (
        count_rows_by_table(config.database_path, "etf_features")
        if config.database_path.exists() and "etf_features" in database_status.existing_tables
        else 0
    )
    latest_target = (
        latest_target_date(config.database_path)
        if config.database_path.exists() and "targets" in database_status.existing_tables
        else None
    )
    latest_etf_nav = (
        latest_etf_nav_date(config.database_path)
        if config.database_path.exists() and "etf_navs" in database_status.existing_tables
        else None
    )
    latest_etf_holdings = (
        latest_any_etf_holdings_date(config.database_path)
        if config.database_path.exists() and "etf_holdings" in database_status.existing_tables
        else None
    )
    latest_quote = (
        latest_quote_timestamp(config.database_path)
        if config.database_path.exists()
        and "quote_snapshots" in database_status.existing_tables
        else None
    )
    latest_intraday_gap = (
        latest_intraday_gap_timestamp(config.database_path)
        if config.database_path.exists()
        and "intraday_gap_snapshots" in database_status.existing_tables
        else None
    )
    latest_range = (
        latest_range_snapshot_timestamp(config.database_path)
        if config.database_path.exists()
        and "range_snapshots" in database_status.existing_tables
        else None
    )
    latest_technical_signal = (
        latest_technical_signal_date(config.database_path)
        if config.database_path.exists()
        and "technical_signal_snapshots" in database_status.existing_tables
        else None
    )
    latest_regime_signal = (
        latest_regime_signal_date(config.database_path)
        if config.database_path.exists()
        and "regime_signal_snapshots" in database_status.existing_tables
        else None
    )
    latest_notification = (
        latest_notification_timestamp(config.database_path)
        if config.database_path.exists()
        and "notification_events" in database_status.existing_tables
        else None
    )
    latest_trader_commentary_capture = (
        latest_trader_commentary_capture_date(config.database_path)
        if config.database_path.exists()
        and "trader_commentary_raw" in database_status.existing_tables
        else None
    )
    latest_trader_commentary_claim = (
        latest_trader_commentary_claim_date(config.database_path)
        if config.database_path.exists()
        and "trader_commentary_claims" in database_status.existing_tables
        else None
    )
    latest_trader_commentary_validation = (
        latest_trader_commentary_outcome_date(config.database_path)
        if config.database_path.exists()
        and "trader_commentary_claim_outcomes" in database_status.existing_tables
        else None
    )
    latest_trader_commentary_browser_capture = (
        latest_trader_commentary_browser_capture_timestamp(config.database_path)
        if config.database_path.exists()
        and "trader_commentary_browser_capture_runs" in database_status.existing_tables
        else None
    )
    latest_trader_commentary_discord_capture = (
        latest_trader_commentary_discord_capture_timestamp(config.database_path)
        if config.database_path.exists()
        and "trader_commentary_discord_capture_runs" in database_status.existing_tables
        else None
    )
    latest_pipeline = (
        latest_pipeline_run(config.database_path)
        if config.database_path.exists()
        and "pipeline_runs" in database_status.existing_tables
        else None
    )
    latest_intraday_cycle = (
        latest_pipeline_run(config.database_path, run_type="intraday_cycle")
        if config.database_path.exists()
        and "pipeline_runs" in database_status.existing_tables
        else None
    )
    from .tom_loop import tom_loop_status

    current_intraday_health = intraday_health(config)
    current_tom_loop = tom_loop_status(config)
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
    notification_delivery_rows = (
        count_rows_by_table(config.database_path, "notification_deliveries")
        if config.database_path.exists()
        and "notification_deliveries" in database_status.existing_tables
        else 0
    )
    failed_notification_deliveries = (
        notification_delivery_count(config.database_path, status="failed")
        if config.database_path.exists()
        and "notification_deliveries" in database_status.existing_tables
        else 0
    )
    latest_notification_delivery = (
        latest_notification_delivery_timestamp(config.database_path)
        if config.database_path.exists()
        and "notification_deliveries" in database_status.existing_tables
        else None
    )
    latest_score = (
        latest_score_date(config.database_path)
        if config.database_path.exists() and "scores" in database_status.existing_tables
        else None
    )
    latest_signal = (
        latest_signal_date(config.database_path)
        if config.database_path.exists() and "signals" in database_status.existing_tables
        else None
    )
    latest_signal_outcome = (
        latest_signal_outcome_date(config.database_path)
        if config.database_path.exists()
        and "signal_outcomes" in database_status.existing_tables
        else None
    )
    latest_revision_aggregate = (
        latest_analyst_revision_aggregate_date(config.database_path)
        if config.database_path.exists()
        and "analyst_revision_aggregates" in database_status.existing_tables
        else None
    )
    latest_news_catalyst_aggregate = (
        latest_news_catalyst_aggregate_date(config.database_path)
        if config.database_path.exists()
        and "news_catalyst_aggregates" in database_status.existing_tables
        else None
    )
    latest_insider_source_date = (
        latest_insider_transaction_source_date(config.database_path)
        if config.database_path.exists()
        and "insider_transaction_source_snapshots" in database_status.existing_tables
        else None
    )
    latest_short_interest_source_date = (
        latest_short_interest_settlement_date(config.database_path)
        if config.database_path.exists()
        and "short_interest_source_snapshots" in database_status.existing_tables
        else None
    )
    latest_option_chain_snapshot = (
        latest_option_chain_snapshot_timestamp(config.database_path)
        if config.database_path.exists()
        and "option_chain_snapshots" in database_status.existing_tables
        else None
    )
    latest_option_review = (
        latest_option_income_review_date(config.database_path)
        if config.database_path.exists()
        and "option_income_reviews" in database_status.existing_tables
        else None
    )
    latest_option_risk_review = (
        latest_option_risk_review_date(config.database_path)
        if config.database_path.exists()
        and "option_risk_reviews" in database_status.existing_tables
        else None
    )
    latest_option_outcome = (
        latest_option_review_outcome_date(config.database_path)
        if config.database_path.exists()
        and "option_review_outcomes" in database_status.existing_tables
        else None
    )
    latest_option_position = (
        latest_option_position_open_date(config.database_path)
        if config.database_path.exists()
        and "option_position_ledger" in database_status.existing_tables
        else None
    )
    latest_option_lifecycle = (
        latest_option_position_lifecycle_review_date(config.database_path)
        if config.database_path.exists()
        and "option_position_lifecycle_reviews" in database_status.existing_tables
        else None
    )
    latest_alert = (
        latest_alert_timestamp(config.database_path)
        if config.database_path.exists() and "alerts" in database_status.existing_tables
        else None
    )
    latest_outcome = (
        latest_outcome_date(config.database_path)
        if config.database_path.exists()
        and "alert_outcomes" in database_status.existing_tables
        else None
    )
    latest_portfolio_position = (
        latest_portfolio_position_date(config.database_path)
        if config.database_path.exists()
        and "portfolio_positions" in database_status.existing_tables
        else None
    )
    latest_portfolio_cash = (
        latest_portfolio_cash_date(config.database_path)
        if config.database_path.exists()
        and "portfolio_cash" in database_status.existing_tables
        else None
    )
    latest_portfolio_review = (
        latest_portfolio_review_date(config.database_path)
        if config.database_path.exists()
        and "portfolio_reviews" in database_status.existing_tables
        else None
    )
    statuses = (
        price_statuses(config.database_path, config.market_data_stale_after_days)
        if config.database_path.exists() and "prices" in database_status.existing_tables
        else []
    )
    stale_tickers = [status.ticker for status in statuses if status.stale]
    missing_tickers = [status.ticker for status in statuses if status.row_count == 0]
    feature_count = sum(1 for status in statuses if status.feature_available)
    valuation_status = (
        valuation_statuses(config.database_path)
        if config.database_path.exists() and "targets" in database_status.existing_tables
        else []
    )
    target_coverage = sum(1 for status in valuation_status if status.base_target is not None)
    missing_valuation_tickers = [
        status.ticker for status in valuation_status if status.base_target is None
    ]
    etf_status = (
        etf_statuses(config.database_path)
        if config.database_path.exists() and "etf_features" in database_status.existing_tables
        else []
    )
    etf_ready_count = sum(1 for status in etf_status if status.target_ready)
    missing_etf_targets = [status.ticker for status in etf_status if not status.target_ready]
    etf_rows = []
    for status in etf_status:
        etf_rows.append(
            "| ".join(
                (
                    status.ticker,
                    _fmt_number(status.current_price),
                    _fmt_number(status.nav_per_share),
                    _fmt_percent(status.premium_discount),
                    _fmt_number(status.premium_discount_zscore),
                    status.latest_nav_date or "",
                    status.latest_holdings_date or "",
                    str(status.holdings_count or 0),
                    str(status.target_ready),
                )
            )
        )
    etf_table = "\n".join(etf_rows) if etf_rows else "No ETF feature rows yet."
    valuation_rows = []
    for status in valuation_status:
        if status.base_target is None:
            continue
        valuation_rows.append(
            "| ".join(
                (
                    status.ticker,
                    _fmt_number(status.current_price),
                    _fmt_number(status.target_low),
                    _fmt_number(status.base_target),
                    _fmt_number(status.target_high),
                    _fmt_percent(status.valuation_gap),
                    _fmt_number(status.valuation_confidence, 1),
                    str(status.method_count or 0),
                )
            )
        )
    valuation_table = "\n".join(valuation_rows) if valuation_rows else "No target ranges yet."
    score_status = (
        score_statuses(config.database_path)
        if config.database_path.exists() and "scores" in database_status.existing_tables
        else []
    )
    scored = [status for status in score_status if status.opportunity_score is not None]
    score_coverage = len(scored)
    score_warnings = [status.ticker for status in score_status if status.data_warnings]
    score_rows_text = []
    for status in sorted(
        scored,
        key=lambda item: item.opportunity_score or 0.0,
        reverse=True,
    ):
        score_rows_text.append(
            "| ".join(
                (
                    status.ticker,
                    status.asset_type or "",
                    _fmt_number(status.opportunity_score),
                    _fmt_number(status.expected_value_score),
                    _fmt_number(status.momentum_score),
                    _fmt_number(status.timing_score),
                    _fmt_number(status.risk_score),
                    status.score_model or "",
                    status.data_warnings or "",
                )
            )
        )
    score_table = "\n".join(score_rows_text) if score_rows_text else "No scores yet."
    technical_status = (
        technical_signal_statuses(config.database_path)
        if config.database_path.exists()
        and "technical_signal_snapshots" in database_status.existing_tables
        else []
    )
    technical_signal_coverage = sum(
        1 for status in technical_status if status.signal_date
    )
    technical_missing_signal_tickers = [
        status.ticker for status in technical_status if not status.signal_date
    ]
    technical_signal_warnings = [
        status.ticker for status in technical_status if status.data_warnings
    ]
    regime_status = (
        regime_signal_statuses(config.database_path)
        if config.database_path.exists()
        and "regime_signal_snapshots" in database_status.existing_tables
        else []
    )
    regime_required_tickers = tuple(
        dict.fromkeys(
            tuple(config.regime_benchmark_tickers)
            + tuple(config.regime_sector_proxy_tickers)
        )
    )
    regime_present_tickers = {
        status.ticker for status in regime_status if status.signal_date
    }
    regime_signal_coverage = sum(
        1 for ticker in regime_required_tickers if ticker in regime_present_tickers
    )
    regime_missing_signal_tickers = [
        ticker for ticker in regime_required_tickers if ticker not in regime_present_tickers
    ]
    regime_signal_warnings = [
        status.ticker for status in regime_status if status.data_warnings
    ]
    advanced_signal_status = (
        signal_statuses(config.database_path)
        if config.database_path.exists() and "signals" in database_status.existing_tables
        else []
    )
    revision_signal_coverage = sum(
        1 for status in advanced_signal_status if status.latest_signal_date
    )
    revision_signal_warnings = [
        status.ticker for status in advanced_signal_status if status.data_warnings
    ]
    revision_validation_status_rows = (
        signal_outcome_statuses(
            config.database_path,
            signal_family="analyst_revision",
            signal_name="analyst_revision.composite",
        )
        if config.database_path.exists()
        and "signal_outcomes" in database_status.existing_tables
        else []
    )
    news_catalyst_status = (
        news_catalyst_statuses(config)
        if config.database_path.exists() and "signals" in database_status.existing_tables
        else []
    )
    news_catalyst_signal_coverage = sum(
        1 for status in news_catalyst_status if status.latest_signal_date
    )
    news_catalyst_signal_warnings = [
        status.ticker for status in news_catalyst_status if status.data_warnings
    ]
    news_catalyst_source_status = news_catalyst_source_status_report(config)
    news_catalyst_plan = news_catalyst_coverage_plan(config, write_template=False)
    news_catalyst_upgrade_status = news_catalyst_provider_upgrade_status(config)
    news_catalyst_upgrade_preview = preview_news_catalyst_provider_upgrade(config)
    news_catalyst_backfill_apply_status = news_catalyst_provider_backfill_apply_status(config)
    news_catalyst_source_warnings = [
        status.ticker for status in news_catalyst_source_status.statuses if status.warnings
    ]
    news_catalyst_validation_status_rows = (
        signal_outcome_statuses(
            config.database_path,
            signal_family="news_catalyst",
            signal_name="news_catalyst.composite",
        )
        if config.database_path.exists()
        and "signal_outcomes" in database_status.existing_tables
        else []
    )
    insider_status = (
        insider_statuses(config)
        if config.database_path.exists() and "signals" in database_status.existing_tables
        else []
    )
    insider_source_status = insider_source_status_report(config)
    insider_signal_coverage = sum(
        1 for status in insider_status if status.latest_signal_date
    )
    insider_signal_warnings = [
        status.ticker for status in insider_status if status.data_warnings
    ]
    short_interest_status = (
        short_interest_statuses(config)
        if config.database_path.exists() and "signals" in database_status.existing_tables
        else []
    )
    short_interest_source_status = short_interest_source_status_report(config)
    short_interest_backfill_status = validate_short_interest_backfill(config)
    short_interest_provider = short_interest_provider_status(config)
    short_interest_missing_plan = short_interest_missing_coverage_plan(config)
    short_interest_signal_coverage = sum(
        1 for status in short_interest_status if status.latest_signal_date
    )
    short_interest_signal_warnings = [
        status.ticker for status in short_interest_status if status.data_warnings
    ]
    trader_commentary_status = (
        trader_commentary_statuses(config.database_path)
        if config.database_path.exists()
        and "trader_commentary_claims" in database_status.existing_tables
        else []
    )
    trader_commentary_claim_coverage = sum(
        1 for status in trader_commentary_status if status.claim_count
    )
    trader_commentary_validation_status_rows = [
        status for status in trader_commentary_status if status.validation_count
    ]
    trader_commentary_warning_tickers = [
        status.ticker for status in trader_commentary_status if status.data_warnings
    ]
    insider_validation_status_rows = (
        signal_outcome_statuses(
            config.database_path,
            signal_family="insider_activity",
            signal_name="insider_activity.composite",
        )
        if config.database_path.exists()
        and "signal_outcomes" in database_status.existing_tables
        else []
    )
    short_interest_validation_status_rows = (
        signal_outcome_statuses(
            config.database_path,
            signal_family="short_interest",
            signal_name="short_interest.composite",
        )
        if config.database_path.exists()
        and "signal_outcomes" in database_status.existing_tables
        else []
    )
    revision_evidence = build_revision_evidence(config)
    revision_source_status = revision_source_status_report(config)
    pending_revision_validations = [
        status.ticker
        for status in revision_validation_status_rows
        if status.outcome_status == "pending"
    ]
    partial_revision_validations = [
        status.ticker
        for status in revision_validation_status_rows
        if status.outcome_status == "partial"
    ]
    completed_revision_validations = [
        status.ticker
        for status in revision_validation_status_rows
        if status.outcome_status == "completed"
    ]
    pending_news_catalyst_validations = [
        status.ticker
        for status in news_catalyst_validation_status_rows
        if status.outcome_status == "pending"
    ]
    partial_news_catalyst_validations = [
        status.ticker
        for status in news_catalyst_validation_status_rows
        if status.outcome_status == "partial"
    ]
    completed_news_catalyst_validations = [
        status.ticker
        for status in news_catalyst_validation_status_rows
        if status.outcome_status == "completed"
    ]
    pending_insider_validations = [
        status.ticker
        for status in insider_validation_status_rows
        if status.outcome_status == "pending"
    ]
    partial_insider_validations = [
        status.ticker
        for status in insider_validation_status_rows
        if status.outcome_status == "partial"
    ]
    completed_insider_validations = [
        status.ticker
        for status in insider_validation_status_rows
        if status.outcome_status == "completed"
    ]
    pending_short_interest_validations = [
        status.ticker
        for status in short_interest_validation_status_rows
        if status.outcome_status == "pending"
    ]
    partial_short_interest_validations = [
        status.ticker
        for status in short_interest_validation_status_rows
        if status.outcome_status == "partial"
    ]
    completed_short_interest_validations = [
        status.ticker
        for status in short_interest_validation_status_rows
        if status.outcome_status == "completed"
    ]

    report_rows = build_daily_report_rows(config, database_status)
    active_alerts = [
        row
        for row in report_rows
        if row.alert_type not in {"no_alert", "not_evaluated", "skipped"}
        and (row.status or "").lower() == "open"
    ]
    active_equity_alerts = [
        row for row in active_alerts if row.asset_type == "equity"
    ]
    active_etf_alerts = [row for row in active_alerts if row.asset_type == "etf"]
    alert_warnings = [row.ticker for row in report_rows if row.model_warnings]
    alert_table = _row_table(report_rows)
    executive_table = _executive_table(report_rows)
    range_table = _range_table(report_rows)
    technical_regime_table = _technical_regime_table(report_rows)
    fundamental_benchmark_table = _fundamental_benchmark_table(report_rows)
    equity_details = _equity_detail_sections(report_rows)
    outcome_table = _outcome_table(report_rows)
    outcome_status_rows = [row for row in report_rows if row.outcome_status]
    active_alert_outcome_rows = [
        row for row in active_alerts if row.outcome_status
    ]
    equity_outcome_status_rows = [
        row for row in outcome_status_rows if row.asset_type == "equity"
    ]
    etf_outcome_status_rows = [
        row for row in outcome_status_rows if row.asset_type == "etf"
    ]
    active_equity_alert_outcome_rows = [
        row for row in active_equity_alerts if row.outcome_status
    ]
    active_etf_alert_outcome_rows = [
        row for row in active_etf_alerts if row.outcome_status
    ]
    pending_outcomes = [
        row.ticker for row in outcome_status_rows if row.outcome_status == "pending"
    ]
    partial_outcomes = [
        row.ticker for row in outcome_status_rows if row.outcome_status == "partial"
    ]
    completed_outcomes = [
        row.ticker for row in outcome_status_rows if row.outcome_status == "completed"
    ]
    portfolio_reviewed_rows = [
        row for row in report_rows if row.portfolio_review_category
    ]
    held_rows = [row for row in portfolio_reviewed_rows if row.held_flag]
    portfolio_warning_tickers = [
        row.ticker for row in portfolio_reviewed_rows if row.portfolio_warnings
    ]
    portfolio_table = _portfolio_table(report_rows)
    option_reviewed_rows = [
        row for row in report_rows if row.option_review_category
    ]
    option_warning_tickers = [
        row.ticker for row in option_reviewed_rows if row.option_warnings
    ]
    options_table = _options_table(report_rows)
    advanced_signal_table = _advanced_signal_table(report_rows)

    return f"""# {config.report_title}

Date: {report_date.isoformat()}

## Executive Alert Summary

- Active equity alerts: `{len(active_alerts)}`
- Equity alert model: `{config.alerts_equity_model_version}`
- ETF alerts: `{config.alerts_etf_model_version}`

```text
Ticker | Alert | Priority | Price | Target Low/Base/High | Gap | Opportunity | Main Reasons
{executive_table}
```

## Range Monitor Summary

- Range snapshot rows: `{range_rows}`
- Latest range snapshot timestamp: `{latest_range or "none"}`
- Latest intraday cycle: `{latest_intraday_cycle.status + " " + latest_intraday_cycle.started_at if latest_intraday_cycle else "none"}`
- Intraday health: `{current_intraday_health.status}`
- Intraday market session: `{current_intraday_health.market_session}`
- Intraday regular market hours: `{current_intraday_health.regular_market_hours}`
- TOM loop health: `{current_tom_loop.health_status}`
- TOM loop status: `{current_tom_loop.status}`
- TOM loop heartbeat age seconds: `{current_tom_loop.heartbeat_age_seconds if current_tom_loop.heartbeat_age_seconds is not None else "none"}`
- TOM loop recovery status: `{current_tom_loop.recovery_status}`
- TOM loop recovery actions: `{", ".join(current_tom_loop.recommended_actions) if current_tom_loop.recommended_actions else "none"}`
- TOM loop clear stale lock command: `{current_tom_loop.clear_stale_lock_command}`
- TOM loop start command: `{current_tom_loop.recommended_command}`
- TOM loop one-shot command: `{current_tom_loop.run_once_command}`
- TOM loop blockers: `{", ".join(current_tom_loop.stale_blockers) if current_tom_loop.stale_blockers else "none"}`
- Intraday blockers: `{", ".join(current_intraday_health.blockers) if current_intraday_health.blockers else "none"}`
- Intraday warnings: `{", ".join(current_intraday_health.warnings) if current_intraday_health.warnings else "none"}`
- Intraday notes: `{", ".join(current_intraday_health.notes) if current_intraday_health.notes else "none"}`
- Scheduler reconciliation: `{scheduler_audit_result.status}`
- Actual heartbeat command: `{heartbeat_job.actual_command if heartbeat_job else "none"}`
- Scheduler warnings: `{", ".join(scheduler_warning_codes) if scheduler_warning_codes else "none"}`
- Pending notifications: `{pending_notifications}`
- Latest notification timestamp: `{latest_notification or "none"}`
- Notification delivery rows: `{notification_delivery_rows}`
- Failed notification deliveries: `{failed_notification_deliveries}`
- Latest notification delivery timestamp: `{latest_notification_delivery or "none"}`

```text
Ticker | Type | Range State | Price | Range Levels | Snapshot Timestamp | Notification | Notification Reasons | Warnings
{range_table}
```

## Data Status

- Run mode: `{config.run_mode}`
- Universe mode: `{config.universe_mode}`
- Database: `{_display_path(config.database_path, config.project_root)}`
- Database status: `{database_state}`
- Required tables present: `{database_status.existing_required_table_count}/{database_status.required_table_count}`
- Watchlist file: `{_display_path(config.watchlist_path, config.project_root)}`
- Watchlist exists: `{config.watchlist_path.exists()}`
- Asset count: `{asset_count}`
- Price rows: `{price_rows}`
- Latest price date: `{latest_price or "none"}`
- Fundamental rows: `{fundamental_rows}`
- Estimate rows: `{estimate_rows}`
- ETF NAV rows: `{etf_nav_rows}`
- ETF holding rows: `{etf_holding_rows}`
- ETF feature rows: `{etf_feature_rows}`
- Latest ETF NAV date: `{latest_etf_nav or "none"}`
- Latest ETF holdings date: `{latest_etf_holdings or "none"}`
- Target rows: `{target_rows}`
- Latest target date: `{latest_target or "none"}`
- Score rows: `{score_rows}`
- Latest score date: `{latest_score or "none"}`
- Fundamental benchmark rows: `{fundamental_benchmark_rows}`
- Fundamental comparison rows: `{fundamental_comparison_rows}`
- Latest fundamental comparison date: `{latest_fundamental_benchmark or "none"}`
- Research recommendation candidates: `{research_recommendation_rows}`
- Research recommendation pending: `{research_recommendation_pending_rows}`
- Research recommendation approved not promoted: `{research_recommendation_approved_rows}`
- Latest research recommendation date: `{latest_research_recommendation or "none"}`
- Universe candidate file: `{_display_path(config.universe_candidates_path, config.project_root)}`
- Universe candidate file exists: `{config.universe_candidates_path.exists()}`
- Research recommendation file: `{_display_path(config.research_recommendations_path, config.project_root)}`
- Research recommendation file exists: `{config.research_recommendations_path.exists()}`
- Sector benchmark file: `{_display_path(config.sector_benchmarks_path, config.project_root)}`
- Sector benchmark file exists: `{config.sector_benchmarks_path.exists()}`
- Signal rows: `{signal_rows}`
- Latest signal date: `{latest_signal or "none"}`
- Signal outcome rows: `{signal_outcome_rows}`
- Latest signal validation date: `{latest_signal_outcome or "none"}`
- Analyst revision source snapshot rows: `{revision_source_snapshot_rows}`
- Analyst revision aggregate rows: `{revision_aggregate_rows}`
- Latest analyst revision aggregate date: `{latest_revision_aggregate or "none"}`
- Analyst revision source export: `{_display_path(config.analyst_revision_source_export_path, config.project_root)}`
- Analyst revision source export exists: `{config.analyst_revision_source_export_path.exists()}`
- News/catalyst file: `{_display_path(config.news_catalysts_path, config.project_root)}`
- News/catalyst file exists: `{config.news_catalysts_path.exists()}`
- News/catalyst source export directory: `{_display_path(config.news_catalyst_source_exports_dir, config.project_root)}`
- News/catalyst source export directory exists: `{config.news_catalyst_source_exports_dir.exists()}`
- News/catalyst cache directory: `{_display_path(config.news_catalyst_cache_dir, config.project_root)}`
- News/catalyst cache files: `{news_catalyst_source_status.cache_file_count}`
- Latest news/catalyst cache timestamp: `{news_catalyst_source_status.latest_cache_at or "none"}`
- News/catalyst source snapshot rows: `{news_catalyst_source_snapshot_rows}`
- News/catalyst numeric source snapshot rows: `{news_catalyst_source_status.numeric_snapshot_count}`
- News/catalyst provider-numeric source snapshot rows: `{news_catalyst_source_status.provider_numeric_snapshot_count}`
- News/catalyst text-derived numeric source snapshot rows: `{news_catalyst_source_status.text_derived_snapshot_count}`
- News/catalyst headline-only source snapshot rows: `{news_catalyst_source_status.headline_only_snapshot_count}`
- News/catalyst aggregate rows: `{news_catalyst_aggregate_rows}`
- Latest news/catalyst aggregate date: `{latest_news_catalyst_aggregate or "none"}`
- News/catalyst validation rows: `{len(news_catalyst_validation_status_rows)}`
- Insider activity cache directory: `{_display_path(config.insider_cache_dir, config.project_root)}`
- Insider activity source rows: `{insider_source_snapshot_rows}`
- Latest insider activity source date: `{latest_insider_source_date or "none"}`
- Insider activity validation rows: `{len(insider_validation_status_rows)}`
- Short interest file: `{_display_path(config.short_interest_path, config.project_root)}`
- Short interest file exists: `{config.short_interest_path.exists()}`
- Short interest source rows: `{short_interest_source_snapshot_rows}`
- Latest short interest settlement date: `{latest_short_interest_source_date or "none"}`
- Short interest validation rows: `{len(short_interest_validation_status_rows)}`
- Short interest source-export directory: `{_display_path(short_interest_backfill_status.source_exports_dir, config.project_root)}`
- Short interest source-export files: `{len(short_interest_backfill_status.source_export_files)}`
- Short interest cache directory: `{_display_path(short_interest_provider.cache_dir, config.project_root)}`
- Short interest provider cache files: `{short_interest_provider.cache_file_count}`
- Latest short interest provider cache timestamp: `{short_interest_provider.latest_cache_timestamp or "none"}`
- Short interest provider export valid rows: `{short_interest_provider.provider_export_valid_row_count}`
- Short interest provider export tickers: `{", ".join(short_interest_provider.provider_export_tickers) if short_interest_provider.provider_export_tickers else "none"}`
- Options chain file: `{_display_path(config.options_chain_path, config.project_root)}`
- Options chain file exists: `{config.options_chain_path.exists()}`
- Options chain source-export directory: `{_display_path(config.options_chain_source_exports_dir, config.project_root)}`
- Options chain source-export directory exists: `{config.options_chain_source_exports_dir.exists()}`
- Options chain source: `{config.options_chain_source}`
- Options chain cache: `{_display_path(config.options_chain_cache_dir, config.project_root)}`
- Options provider readiness: `{option_provider.readiness_status}`
- Options provider blocked reason: `{option_provider.blocked_reason or "none"}`
- Options ibapi status: `{option_provider.ibapi_status}`
- Option activation status: `{option_activation.activation_status}`
- Option activation blocked reason: `{option_activation.blocked_reason or "none"}`
- Minimum option chain coverage: `{option_activation.minimum_option_chain_coverage}`
- Minimum option review count: `{option_activation.minimum_option_review_count}`
- Options ibapi repair needed: `{option_activation.ibapi_repair_needed}`
- Options provider cache files: `{option_provider.cache_file_count}`
- Latest options provider cache timestamp: `{option_provider.latest_cache_timestamp or "none"}`
- Options fetch-universe tickers: `{len(option_fetch_tickers)}`
- Options missing chain tickers: `{", ".join(option_chain_missing_tickers) if option_chain_missing_tickers else "none"}`
- Options broader coverage status: `{option_coverage_plan.coverage_status}`
- Options broader chain coverage: `{option_coverage_plan.effective_coverage_count}`
- Options broader raw chain coverage: `{option_coverage_plan.raw_coverage_count}`
- Options non-actionable chain tickers: `{", ".join(option_coverage_plan.non_actionable_tickers) if option_coverage_plan.non_actionable_tickers else "none"}`
- Options chain availability: `{format_option_chain_availability(option_chain_availability)}`
- Options prioritized missing chain tickers: `{", ".join(option_coverage_plan.prioritized_missing_tickers) if option_coverage_plan.prioritized_missing_tickers else "none"}`
- Options valid broader backfill tickers: `{", ".join(option_coverage_plan.valid_backfill_tickers) if option_coverage_plan.valid_backfill_tickers else "none"}`
- Options projected broader chain coverage: `{option_coverage_plan.projected_loaded_ticker_count}/{option_coverage_plan.fetch_universe_ticker_count}`
- Options broader coverage apply ready: `{option_coverage_plan.apply_ready}`
- Options broader coverage blocked reason: `{option_coverage_plan.blocked_reason or "none"}`
- Options broader coverage notes: `{", ".join(option_coverage_plan.notes) if option_coverage_plan.notes else "none"}`
- Options chain rows: `{option_chain_rows}`
- Option income review rows: `{option_income_review_rows}`
- Option risk review rows: `{option_risk_review_rows}`
- Option review outcome rows: `{option_review_outcome_rows}`
- Option position ledger rows: `{option_position_rows}`
- Option lifecycle review rows: `{option_lifecycle_rows}`
- Latest option chain snapshot: `{latest_option_chain_snapshot or "none"}`
- Latest option income review date: `{latest_option_review or "none"}`
- Latest option risk review date: `{latest_option_risk_review or "none"}`
- Latest option outcome date: `{latest_option_outcome or "none"}`
- Latest option position open date: `{latest_option_position or "none"}`
- Latest option lifecycle review date: `{latest_option_lifecycle or "none"}`
- Options positions file: `{_display_path(config.options_positions_path, config.project_root)}`
- Options positions file exists: `{config.options_positions_path.exists()}`
- Options backfill valid rows: `{option_backfill_status.valid_row_count}`
- Options backfill blank placeholders: `{option_backfill_status.blank_placeholder_count}`
- Options backfill invalid rows: `{option_backfill_status.invalid_row_count}`
- Options projected chain coverage: `{option_backfill_status.projected_loaded_ticker_count}/{option_backfill_status.fetch_universe_ticker_count}`
- Options minimum projected chain coverage: `{option_backfill_status.minimum_projected_loaded_ticker_count}/{option_backfill_status.minimum_ticker_count}`
- Options backfill apply ready: `{option_backfill_status.apply_ready}`
- Options backfill blocked reason: `{option_backfill_status.blocked_reason or "none"}`
- Account context activation status: `{account_context_activation_status}`
- Account context blockers: `{", ".join(account_context_blockers) if account_context_blockers else "none"}`
- Account option risk rows missing portfolio context: `{account_missing_portfolio_context_rows}`
- Account option position rows: `{account_option_position_rows}`
- Account option lifecycle rows: `{account_option_lifecycle_rows}`
- Account option readiness: `{option_position_diagnostics.readiness_status}`
- Account option staged rows: `valid={option_position_diagnostics.valid_option_position_rows}, invalid={option_position_diagnostics.invalid_option_position_rows}, blank={option_position_diagnostics.blank_option_position_rows}`
- Account option projected rows: `option_positions={option_position_diagnostics.projected_option_position_rows}, option_lifecycle={option_position_diagnostics.projected_option_lifecycle_rows}`
- Account option readiness blockers: `{", ".join(option_position_diagnostics.blockers) if option_position_diagnostics.blockers else "none"}`
- Account option recommended actions: `{", ".join(option_position_diagnostics.recommended_actions) if option_position_diagnostics.recommended_actions else "none"}`
- Trader commentary file: `{_display_path(config.trader_commentary_path, config.project_root)}`
- Trader commentary file exists: `{config.trader_commentary_path.exists()}`
- Trader commentary alias file: `{_display_path(config.trader_commentary_aliases_path, config.project_root)}`
- Trader commentary alias file exists: `{config.trader_commentary_aliases_path.exists()}`
- Trader commentary export directory: `{_display_path(config.trader_commentary_exports_dir, config.project_root)}`
- Trader commentary export directory exists: `{config.trader_commentary_exports_dir.exists()}`
- Trader commentary browser capture directory: `{_display_path(config.trader_commentary_browser_capture_dir, config.project_root)}`
- Trader commentary browser capture directory exists: `{config.trader_commentary_browser_capture_dir.exists()}`
- Trader commentary browser capture enabled: `{config.commentary_browser_capture_enabled}`
- Trader commentary Discord capture directory: `{_display_path(config.trader_commentary_discord_capture_dir, config.project_root)}`
- Trader commentary Discord capture directory exists: `{config.trader_commentary_discord_capture_dir.exists()}`
- Trader commentary Discord capture enabled: `{config.commentary_discord_capture_enabled}`
- Trader commentary raw rows: `{trader_commentary_raw_rows}`
- Trader commentary claim rows: `{trader_commentary_claim_rows}`
- Trader commentary validation rows: `{trader_commentary_outcome_rows}`
- Trader commentary onboarding candidates: `{commentary_onboarding_plan.onboardable_count}`
- Trader commentary unmapped instrument labels: `{commentary_onboarding_plan.unmapped_count}`
- Trader commentary alias mappings: `{commentary_onboarding_plan.alias_count}`
- Trader commentary label dispositions: `{commentary_onboarding_plan.label_disposition_count}`
- Trader commentary intentionally unresolved labels: `{commentary_onboarding_plan.intentionally_unresolved_count}`
- Trader commentary ignored non-instrument labels: `{commentary_onboarding_plan.ignored_non_instrument_count}`
- Scoreable assets: `{scoreable_asset_count}`
- Reference assets: `{reference_asset_count}`
- Trader commentary browser capture run rows: `{trader_commentary_browser_capture_run_rows}`
- Trader commentary browser capture item rows: `{trader_commentary_browser_capture_item_rows}`
- Trader commentary Discord capture run rows: `{trader_commentary_discord_capture_run_rows}`
- Trader commentary Discord capture item rows: `{trader_commentary_discord_capture_item_rows}`
- Latest trader commentary capture date: `{latest_trader_commentary_capture or "none"}`
- Latest trader commentary claim date: `{latest_trader_commentary_claim or "none"}`
- Latest trader commentary validation date: `{latest_trader_commentary_validation or "none"}`
- Latest trader commentary browser capture timestamp: `{latest_trader_commentary_browser_capture or "none"}`
- Latest trader commentary Discord capture timestamp: `{latest_trader_commentary_discord_capture or "none"}`
- Alert rows: `{alert_rows}`
- Latest alert timestamp: `{latest_alert or "none"}`
- Outcome rows: `{outcome_rows}`
- Latest outcome date: `{latest_outcome or "none"}`
- Portfolio position rows: `{portfolio_position_rows}`
- Portfolio cash rows: `{portfolio_cash_rows}`
- Portfolio review rows: `{portfolio_review_rows}`
- Latest portfolio position date: `{latest_portfolio_position or "none"}`
- Latest portfolio cash date: `{latest_portfolio_cash or "none"}`
- Latest portfolio review date: `{latest_portfolio_review or "none"}`
- Latest quote timestamp: `{latest_quote or "none"}`
- Intraday health: `{current_intraday_health.status}`
- Intraday market session: `{current_intraday_health.market_session}`
- Intraday regular market hours: `{current_intraday_health.regular_market_hours}`
- TOM loop health: `{current_tom_loop.health_status}`
- TOM loop status: `{current_tom_loop.status}`
- TOM loop heartbeat age seconds: `{current_tom_loop.heartbeat_age_seconds if current_tom_loop.heartbeat_age_seconds is not None else "none"}`
- TOM loop recovery status: `{current_tom_loop.recovery_status}`
- TOM loop recovery actions: `{", ".join(current_tom_loop.recommended_actions) if current_tom_loop.recommended_actions else "none"}`
- TOM loop clear stale lock command: `{current_tom_loop.clear_stale_lock_command}`
- TOM loop start command: `{current_tom_loop.recommended_command}`
- TOM loop one-shot command: `{current_tom_loop.run_once_command}`
- TOM loop blockers: `{", ".join(current_tom_loop.stale_blockers) if current_tom_loop.stale_blockers else "none"}`
- Intraday health blockers: `{", ".join(current_intraday_health.blockers) if current_intraday_health.blockers else "none"}`
- Intraday health warnings: `{", ".join(current_intraday_health.warnings) if current_intraday_health.warnings else "none"}`
- Intraday health notes: `{", ".join(current_intraday_health.notes) if current_intraday_health.notes else "none"}`
- Preferred intraday heartbeat command: `{current_intraday_health.heartbeat_command}`
- Scheduler reconciliation: `{scheduler_audit_result.status}`
- Actual heartbeat command: `{heartbeat_job.actual_command if heartbeat_job else "none"}`
- Scheduler warnings: `{", ".join(scheduler_warning_codes) if scheduler_warning_codes else "none"}`
- Latest intraday gap timestamp: `{latest_intraday_gap or "none"}`
- Range snapshot rows: `{range_rows}`
- Latest range snapshot timestamp: `{latest_range or "none"}`
- Technical signal snapshot rows: `{technical_signal_rows}`
- Latest technical signal date: `{latest_technical_signal or "none"}`
- Regime signal snapshot rows: `{regime_signal_rows}`
- Latest regime signal date: `{latest_regime_signal or "none"}`
- Notification event rows: `{notification_rows}`
- Pending notifications: `{pending_notifications}`
- Latest notification timestamp: `{latest_notification or "none"}`
- Notification delivery rows: `{notification_delivery_rows}`
- Failed notification deliveries: `{failed_notification_deliveries}`
- Latest notification delivery timestamp: `{latest_notification_delivery or "none"}`
- Latest intraday cycle: `{latest_intraday_cycle.run_type + " " + latest_intraday_cycle.status if latest_intraday_cycle else "none"}`
- Latest pipeline run: `{latest_pipeline.run_type + " " + latest_pipeline.status if latest_pipeline else "none"}`

## Data Health

- Market feature coverage: `{feature_count}/{len(statuses)}`
- Missing price tickers: `{", ".join(missing_tickers) if missing_tickers else "none"}`
- Stale price tickers: `{", ".join(stale_tickers) if stale_tickers else "none"}`
- Target coverage: `{target_coverage}/{len(valuation_status)}`
- Score coverage: `{score_coverage}/{len(score_status)}`
- Analyst revision signal coverage: `{revision_signal_coverage}/{len(advanced_signal_status)}`
- Analyst revision source-backed coverage: `{revision_source_status.source_backed_ticker_count}/{revision_source_status.active_equity_count}`
- Analyst revision validation rows: `{len(revision_validation_status_rows)}`
- Analyst revision evidence decision: `{revision_evidence.decision}`
- News/catalyst signal coverage: `{news_catalyst_signal_coverage}/{len(news_catalyst_status)}`
- News/catalyst source-backed coverage: `{news_catalyst_source_status.source_backed_ticker_count}/{news_catalyst_source_status.active_equity_count}`
- News/catalyst provider-numeric coverage: `{news_catalyst_source_status.provider_numeric_ticker_count}/{news_catalyst_source_status.active_equity_count}`
- News/catalyst text-derived numeric coverage: `{news_catalyst_source_status.text_derived_ticker_count}/{news_catalyst_source_status.active_equity_count}`
- News/catalyst total numeric coverage: `{news_catalyst_source_status.total_numeric_ticker_count}/{news_catalyst_source_status.active_equity_count}`
- News/catalyst missing numeric tickers: `{len(news_catalyst_source_status.missing_numeric_tickers)}`
- News/catalyst provider-upgrade status: `{news_catalyst_upgrade_status.status}`
- News/catalyst provider-native upgrade needed: `{len(news_catalyst_source_status.provider_native_upgrade_tickers)}/{news_catalyst_source_status.active_equity_count}`
- News/catalyst provider-native upgrade tickers: `{", ".join(news_catalyst_source_status.provider_native_upgrade_tickers) if news_catalyst_source_status.provider_native_upgrade_tickers else "none"}`
- Latest news/catalyst provider-native source date: `{news_catalyst_source_status.latest_provider_native_source_date or "none"}`
- News/catalyst rejected provider-native rows: `{news_catalyst_source_status.provider_native_rejected_row_count}`
- News/catalyst rejected provider-native tickers: `{", ".join(news_catalyst_source_status.provider_native_rejected_tickers) if news_catalyst_source_status.provider_native_rejected_tickers else "none"}`
- News/catalyst backfill valid rows: `{news_catalyst_upgrade_preview.validation.valid_row_count}`
- News/catalyst backfill blank placeholders: `{news_catalyst_upgrade_preview.validation.blank_placeholder_count}`
- News/catalyst backfill invalid rows: `{news_catalyst_upgrade_preview.validation.invalid_row_count}`
- News/catalyst projected provider-native coverage: `{news_catalyst_upgrade_preview.projected_provider_native_ticker_count}/{news_catalyst_upgrade_preview.active_equity_count}`
- News/catalyst still-blocked provider-native tickers: `{", ".join(news_catalyst_upgrade_preview.still_blocked_tickers) if news_catalyst_upgrade_preview.still_blocked_tickers else "none"}`
- News/catalyst backfill apply ready: `{news_catalyst_backfill_apply_status.backfill_apply_ready}`
- News/catalyst valid upgrade tickers: `{", ".join(news_catalyst_backfill_apply_status.valid_upgrade_tickers) if news_catalyst_backfill_apply_status.valid_upgrade_tickers else "none"}`
- News/catalyst projected upgrade delta: `{news_catalyst_backfill_apply_status.projected_upgrade_delta}`
- News/catalyst blocked apply reason: `{news_catalyst_backfill_apply_status.blocked_apply_reason or "none"}`
- Missing news/catalyst source-backed count: `{len(news_catalyst_source_status.missing_source_tickers)}`
- News/catalyst coverage-plan tickers: `{", ".join(news_catalyst_plan.planned_tickers) if news_catalyst_plan.planned_tickers else "none"}`
- News/catalyst coverage queue stale: `{news_catalyst_plan.queue_template_stale}`
- News/catalyst missing queue stale: `{news_catalyst_plan.missing_queue_template_stale}`
- News/catalyst provider upgrade queue stale: `{news_catalyst_plan.provider_upgrade_queue_template_stale}`
- News/catalyst provider-upgrade blockers: `{", ".join(news_catalyst_upgrade_status.provider_blockers) if news_catalyst_upgrade_status.provider_blockers else "none"}`
- News/catalyst provider smoke-test command: `python -m target_opportunity_monitor test-news-catalyst-provider --provider all --ticker AAPL`
- News/catalyst provider warnings: `{", ".join(news_catalyst_plan.provider_warning_summary) if news_catalyst_plan.provider_warning_summary else "none"}`
- News/catalyst validation rows: `{len(news_catalyst_validation_status_rows)}`
- Insider activity signal coverage: `{insider_signal_coverage}/{len(insider_status)}`
- Insider activity source rows: `{insider_source_snapshot_rows}`
- Insider activity validation rows: `{len(insider_validation_status_rows)}`
- Short interest signal coverage: `{short_interest_signal_coverage}/{len(short_interest_status)}`
- Short interest source-backed coverage: `{short_interest_source_status.source_backed_ticker_count}/{short_interest_source_status.active_equity_count}`
- Short interest source rows: `{short_interest_source_snapshot_rows}`
- Short interest provider export valid rows: `{short_interest_provider.provider_export_valid_row_count}`
- Short interest provider export tickers: `{", ".join(short_interest_provider.provider_export_tickers) if short_interest_provider.provider_export_tickers else "none"}`
- Short interest fetchable providers: `{", ".join(short_interest_provider.fetchable_providers) if short_interest_provider.fetchable_providers else "none"}`
- Short interest manual/export-only providers: `{", ".join(short_interest_provider.manual_only_providers) if short_interest_provider.manual_only_providers else "none"}`
- Short interest provider cache files: `{short_interest_provider.cache_file_count}`
- Latest short interest provider cache timestamp: `{short_interest_provider.latest_cache_timestamp or "none"}`
- Short interest provider warnings: `{", ".join(short_interest_provider.warnings) if short_interest_provider.warnings else "none"}`
- Short interest backfill valid rows: `{short_interest_backfill_status.valid_row_count}`
- Short interest backfill blank placeholders: `{short_interest_backfill_status.blank_placeholder_count}`
- Short interest backfill invalid rows: `{short_interest_backfill_status.invalid_row_count}`
- Short interest projected source-backed coverage: `{short_interest_backfill_status.projected_source_backed_count}/{short_interest_backfill_status.active_equity_count}`
- Short interest backfill apply ready: `{short_interest_backfill_status.apply_ready}`
- Short interest validation rows: `{len(short_interest_validation_status_rows)}`
- Options chain rows: `{option_chain_rows}`
- Option income review rows: `{option_income_review_rows}`
- Option review warning tickers: `{", ".join(option_warning_tickers) if option_warning_tickers else "none"}`
- Trader commentary claim ticker coverage: `{trader_commentary_claim_coverage}/{len(trader_commentary_status)}`
- Trader commentary validation rows: `{len(trader_commentary_validation_status_rows)}`
- Trader commentary browser capture runs: `{trader_commentary_browser_capture_run_rows}`
- Trader commentary browser capture items: `{trader_commentary_browser_capture_item_rows}`
- Trader commentary Discord capture runs: `{trader_commentary_discord_capture_run_rows}`
- Trader commentary Discord capture items: `{trader_commentary_discord_capture_item_rows}`
- Trader commentary warning tickers: `{", ".join(trader_commentary_warning_tickers) if trader_commentary_warning_tickers else "none"}`
- Alert warning tickers: `{", ".join(alert_warnings) if alert_warnings else "none"}`
- Advanced signal warning tickers: `{", ".join(sorted(set(revision_signal_warnings + news_catalyst_signal_warnings + news_catalyst_source_warnings + insider_signal_warnings + short_interest_signal_warnings + trader_commentary_warning_tickers))) if revision_signal_warnings or news_catalyst_signal_warnings or news_catalyst_source_warnings or insider_signal_warnings or short_interest_signal_warnings or trader_commentary_warning_tickers else "none"}`
- Outcome rows in report: `{len(outcome_status_rows)}`
- Active alert outcome coverage: `{len(active_alert_outcome_rows)}/{len(active_alerts)} active alerts`
- Active equity alert outcome coverage: `{len(active_equity_alert_outcome_rows)}/{len(active_equity_alerts)} active equity alerts`
- Active ETF alert outcome coverage: `{len(active_etf_alert_outcome_rows)}/{len(active_etf_alerts)} active ETF alerts`
- Pending outcome tickers: `{", ".join(pending_outcomes) if pending_outcomes else "none"}`
- Portfolio review coverage: `{len(portfolio_reviewed_rows)}/{len(report_rows)}`
- Portfolio warning tickers: `{", ".join(portfolio_warning_tickers) if portfolio_warning_tickers else "none"}`
- Technical signal coverage: `{technical_signal_coverage}/{len(technical_status)}`
- Missing technical signal tickers: `{", ".join(technical_missing_signal_tickers) if technical_missing_signal_tickers else "none"}`
- Technical warning tickers: `{", ".join(technical_signal_warnings) if technical_signal_warnings else "none"}`
- Regime signal coverage: `{regime_signal_coverage}/{len(regime_required_tickers)}`
- Missing regime signal tickers: `{", ".join(regime_missing_signal_tickers) if regime_missing_signal_tickers else "none"}`
- Regime warning tickers: `{", ".join(regime_signal_warnings) if regime_signal_warnings else "none"}`

## Model Health

- Equity score model: `{config.scoring_equity_model_version}`
- Equity alert model: `{config.alerts_equity_model_version}`
- Valuation model version: `{config.valuation_model_version}`
- ETF score model: `{config.scoring_etf_model_version}`
- ETF model version: `{config.etf_model_version}`
- Portfolio model version: `{config.portfolio_model_version}`
- Analyst revision signal model: `{config.signals_analyst_revision_model_version}`
- Analyst revision shadow mode: `{config.signals_analyst_revision_shadow_mode}`
- Analyst revision evidence decision: `{revision_evidence.decision}`
- News/catalyst signal model: `{config.signals_news_catalyst_model_version}`
- News/catalyst shadow mode: `{config.signals_news_catalyst_shadow_mode}`
- Insider activity signal model: `{config.signals_insider_activity_model_version}`
- Insider activity shadow mode: `{config.signals_insider_activity_shadow_mode}`
- Short interest signal model: `{config.signals_short_interest_model_version}`
- Short interest shadow mode: `{config.signals_short_interest_shadow_mode}`
- Options model: `{config.options_model_version}`
- Options advisory mode: `read_only_no_broker_writes`
- Trader commentary signal model: `{config.signals_trader_commentary_model_version}`
- Trader commentary shadow mode: `{config.signals_trader_commentary_shadow_mode}`
- Trader commentary Discord capture enabled: `{config.commentary_discord_capture_enabled}`
- Technical model: `{config.technical_model_version}`
- Regime model: `{config.regime_model_version}`
- Known gated paths: `revision-inflection alerts, news/catalyst score impact, short-interest score impact, broker writes`

## Market Data Status

- Feature coverage: `{feature_count}/{len(statuses)}`
- Missing price tickers: `{", ".join(missing_tickers) if missing_tickers else "none"}`
- Stale price tickers: `{", ".join(stale_tickers) if stale_tickers else "none"}`
- Market data mode: `{config.market_data_mode}`
- Primary source: `{config.market_data_primary_source}`
- Secondary source: `{config.market_data_secondary_source}`

## Valuation Status

- Target coverage: `{target_coverage}/{len(valuation_status)}`
- Missing valuation tickers: `{", ".join(missing_valuation_tickers) if missing_valuation_tickers else "none"}`
- Valuation model version: `{config.valuation_model_version}`
- ETF model version: `{config.etf_model_version}`

```text
Ticker | Price | Target Low | Base Target | Target High | Gap | Confidence | Methods
{valuation_table}
```

## Score Status

- Score coverage: `{score_coverage}/{len(score_status)}`
- Score warning tickers: `{", ".join(score_warnings) if score_warnings else "none"}`
- Equity score model: `{config.scoring_equity_model_version}`
- ETF score model: `{config.scoring_etf_model_version}`

```text
Ticker | Type | Opportunity | Expected Value | Momentum | Timing | Risk | Model | Warnings
{score_table}
```

## Technical And Regime Status

- Technical signal coverage: `{technical_signal_coverage}/{len(technical_status)}`
- Latest technical signal date: `{latest_technical_signal or "none"}`
- Missing technical signal tickers: `{", ".join(technical_missing_signal_tickers) if technical_missing_signal_tickers else "none"}`
- Regime signal coverage: `{regime_signal_coverage}/{len(regime_required_tickers)}`
- Latest regime signal date: `{latest_regime_signal or "none"}`
- Missing regime signal tickers: `{", ".join(regime_missing_signal_tickers) if regime_missing_signal_tickers else "none"}`
- Technical/regime readiness uses all active technical assets plus configured benchmark and sector proxy tickers.

```text
Ticker | Type | Price | Support | Resistance | Breakout | Downside Watch | Trend Repair | MA State | Location | Regime | Rel Strength | Rotation Rank | Warnings
{technical_regime_table}
```

## Fundamental Benchmarks

- Benchmark snapshot rows: `{fundamental_benchmark_rows}`
- Ticker comparison rows: `{fundamental_comparison_rows}`
- Latest comparison date: `{latest_fundamental_benchmark or "none"}`

```text
Ticker | Status | Sector Peers | Sector ETF | Fwd P/E | Sector Fwd P/E | Sector Discount | RS vs SPY | RS vs Sector | Warnings
{fundamental_benchmark_table}
```

## Advanced Signals

- Analyst revision signal coverage: `{revision_signal_coverage}/{len(advanced_signal_status)}`
- Analyst revision validation rows: `{len(revision_validation_status_rows)}`
- Pending revision validations: `{", ".join(pending_revision_validations) if pending_revision_validations else "none"}`
- Partial revision validations: `{", ".join(partial_revision_validations) if partial_revision_validations else "none"}`
- Completed revision validations: `{", ".join(completed_revision_validations) if completed_revision_validations else "none"}`
- Source snapshot rows: `{revision_source_snapshot_rows}`
- Aggregate rows: `{revision_aggregate_rows}`
- Source-backed ticker coverage: `{revision_evidence.source_ticker_count}/{config.signals_revision_evidence_min_source_tickers}`
- Source-export ticker coverage: `{revision_source_status.source_backed_ticker_count}/{revision_source_status.active_equity_count}`
- Source-backed tickers: `{", ".join(revision_source_status.source_backed_tickers) if revision_source_status.source_backed_tickers else "none"}`
- Missing source-backed tickers: `{", ".join(revision_source_status.missing_source_tickers) if revision_source_status.missing_source_tickers else "none"}`
- Stale source-backed tickers: `{", ".join(revision_source_status.stale_tickers) if revision_source_status.stale_tickers else "none"}`
- Skipped ETF source rows: `{", ".join(revision_source_status.skipped_etf_tickers) if revision_source_status.skipped_etf_tickers else "none"}`
- Source aggregation policy: `{config.signals_revision_source_policy}`
- Enabled revision providers: `{", ".join(config.signals_revision_enabled_providers)}`
- Composite signal ticker coverage: `{revision_evidence.signal_ticker_count}/{config.signals_revision_evidence_min_signal_tickers}`
- Completed 20d validation rows: `{revision_evidence.completed_20d_count}/{config.signals_revision_evidence_min_completed_20d}`
- 20d directional hit rate: `{_fmt_number(revision_evidence.hit_rate_20d, 4) or "none"}`
- 20d direction-adjusted average return: `{_fmt_percent(revision_evidence.average_directional_return_20d) or "none"}`
- Revision evidence decision: `{revision_evidence.decision}`
- Analyst revision model: `{config.signals_analyst_revision_model_version}`
- Shadow mode: `{config.signals_analyst_revision_shadow_mode}`
- Evidence warnings: `{", ".join(revision_evidence.warnings) if revision_evidence.warnings else "none"}`
- Warning tickers: `{", ".join(revision_signal_warnings) if revision_signal_warnings else "none"}`
- News/catalyst model: `{config.signals_news_catalyst_model_version}`
- News/catalyst shadow mode: `{config.signals_news_catalyst_shadow_mode}`
- News/catalyst signal coverage: `{news_catalyst_signal_coverage}/{len(news_catalyst_status)}`
- News/catalyst source snapshot rows: `{news_catalyst_source_snapshot_rows}`
- News/catalyst numeric source snapshot rows: `{news_catalyst_source_status.numeric_snapshot_count}`
- News/catalyst provider-numeric source snapshot rows: `{news_catalyst_source_status.provider_numeric_snapshot_count}`
- News/catalyst text-derived numeric source snapshot rows: `{news_catalyst_source_status.text_derived_snapshot_count}`
- News/catalyst headline-only source snapshot rows: `{news_catalyst_source_status.headline_only_snapshot_count}`
- News/catalyst aggregate rows: `{news_catalyst_aggregate_rows}`
- News/catalyst cache files: `{news_catalyst_source_status.cache_file_count}`
- Latest news/catalyst cache timestamp: `{news_catalyst_source_status.latest_cache_at or "none"}`
- News/catalyst source-backed coverage: `{news_catalyst_source_status.source_backed_ticker_count}/{news_catalyst_source_status.active_equity_count}`
- News/catalyst provider-numeric coverage: `{news_catalyst_source_status.provider_numeric_ticker_count}/{news_catalyst_source_status.active_equity_count}`
- News/catalyst text-derived numeric coverage: `{news_catalyst_source_status.text_derived_ticker_count}/{news_catalyst_source_status.active_equity_count}`
- News/catalyst total numeric coverage: `{news_catalyst_source_status.total_numeric_ticker_count}/{news_catalyst_source_status.active_equity_count}`
- News/catalyst missing numeric tickers: `{len(news_catalyst_source_status.missing_numeric_tickers)}`
- News/catalyst provider-upgrade status: `{news_catalyst_upgrade_status.status}`
- News/catalyst provider-native upgrade needed: `{len(news_catalyst_source_status.provider_native_upgrade_tickers)}/{news_catalyst_source_status.active_equity_count}`
- News/catalyst provider-native upgrade tickers: `{", ".join(news_catalyst_source_status.provider_native_upgrade_tickers) if news_catalyst_source_status.provider_native_upgrade_tickers else "none"}`
- Latest news/catalyst provider-native source date: `{news_catalyst_source_status.latest_provider_native_source_date or "none"}`
- News/catalyst rejected provider-native rows: `{news_catalyst_source_status.provider_native_rejected_row_count}`
- News/catalyst rejected provider-native tickers: `{", ".join(news_catalyst_source_status.provider_native_rejected_tickers) if news_catalyst_source_status.provider_native_rejected_tickers else "none"}`
- News/catalyst backfill valid rows: `{news_catalyst_upgrade_preview.validation.valid_row_count}`
- News/catalyst backfill blank placeholders: `{news_catalyst_upgrade_preview.validation.blank_placeholder_count}`
- News/catalyst backfill invalid rows: `{news_catalyst_upgrade_preview.validation.invalid_row_count}`
- News/catalyst projected provider-native coverage: `{news_catalyst_upgrade_preview.projected_provider_native_ticker_count}/{news_catalyst_upgrade_preview.active_equity_count}`
- News/catalyst still-blocked provider-native tickers: `{", ".join(news_catalyst_upgrade_preview.still_blocked_tickers) if news_catalyst_upgrade_preview.still_blocked_tickers else "none"}`
- News/catalyst backfill apply ready: `{news_catalyst_backfill_apply_status.backfill_apply_ready}`
- News/catalyst valid upgrade tickers: `{", ".join(news_catalyst_backfill_apply_status.valid_upgrade_tickers) if news_catalyst_backfill_apply_status.valid_upgrade_tickers else "none"}`
- News/catalyst projected upgrade delta: `{news_catalyst_backfill_apply_status.projected_upgrade_delta}`
- News/catalyst blocked apply reason: `{news_catalyst_backfill_apply_status.blocked_apply_reason or "none"}`
- News/catalyst source-backed tickers: `{", ".join(news_catalyst_source_status.source_backed_tickers) if news_catalyst_source_status.source_backed_tickers else "none"}`
- Missing news/catalyst source-backed tickers: `{", ".join(news_catalyst_source_status.missing_source_tickers) if news_catalyst_source_status.missing_source_tickers else "none"}`
- News/catalyst coverage-plan tickers: `{", ".join(news_catalyst_plan.planned_tickers) if news_catalyst_plan.planned_tickers else "none"}`
- News/catalyst coverage queue tickers: `{", ".join(news_catalyst_plan.queue_template_tickers) if news_catalyst_plan.queue_template_tickers else "none"}`
- News/catalyst coverage queue stale: `{news_catalyst_plan.queue_template_stale}`
- News/catalyst missing queue stale: `{news_catalyst_plan.missing_queue_template_stale}`
- News/catalyst provider upgrade queue stale: `{news_catalyst_plan.provider_upgrade_queue_template_stale}`
- News/catalyst provider-upgrade blockers: `{", ".join(news_catalyst_upgrade_status.provider_blockers) if news_catalyst_upgrade_status.provider_blockers else "none"}`
- News/catalyst provider smoke-test command: `python -m target_opportunity_monitor test-news-catalyst-provider --provider all --ticker AAPL`
- News/catalyst provider warnings: `{", ".join(news_catalyst_plan.provider_warning_summary) if news_catalyst_plan.provider_warning_summary else "none"}`
- Stale news/catalyst source-backed tickers: `{", ".join(news_catalyst_source_status.stale_tickers) if news_catalyst_source_status.stale_tickers else "none"}`
- Skipped ETF news/catalyst source rows: `{", ".join(news_catalyst_source_status.skipped_etf_tickers) if news_catalyst_source_status.skipped_etf_tickers else "none"}`
- News/catalyst source aggregation policy: `{config.signals_news_catalyst_source_policy}`
- Enabled news/catalyst providers: `{", ".join(config.signals_news_catalyst_enabled_providers)}`
- News/catalyst validation rows: `{len(news_catalyst_validation_status_rows)}`
- Pending news/catalyst validations: `{", ".join(pending_news_catalyst_validations) if pending_news_catalyst_validations else "none"}`
- Partial news/catalyst validations: `{", ".join(partial_news_catalyst_validations) if partial_news_catalyst_validations else "none"}`
- Completed news/catalyst validations: `{", ".join(completed_news_catalyst_validations) if completed_news_catalyst_validations else "none"}`
- News/catalyst warning tickers: `{", ".join(news_catalyst_signal_warnings) if news_catalyst_signal_warnings else "none"}`
- News/catalyst source warning tickers: `{", ".join(news_catalyst_source_warnings) if news_catalyst_source_warnings else "none"}`
- Insider activity model: `{config.signals_insider_activity_model_version}`
- Insider activity shadow mode: `{config.signals_insider_activity_shadow_mode}`
- Insider activity source coverage: `{insider_source_status.covered_ticker_count}/{insider_source_status.active_equity_count}`
- Insider activity source-backed tickers: `{insider_source_status.source_backed_ticker_count}/{insider_source_status.active_equity_count}`
- Insider activity signal coverage: `{insider_signal_coverage}/{len(insider_status)}`
- Insider activity source rows: `{insider_source_snapshot_rows}`
- Latest insider activity source date: `{latest_insider_source_date or "none"}`
- Latest insider activity successful fetch: `{insider_source_status.latest_successful_fetch_date or "none"}`
- No-recent insider activity tickers: `{", ".join(insider_source_status.no_recent_activity_tickers) if insider_source_status.no_recent_activity_tickers else "none"}`
- Parse-warning insider activity tickers: `{", ".join(insider_source_status.parse_warning_tickers) if insider_source_status.parse_warning_tickers else "none"}`
- SEC-rate-limited insider activity tickers: `{", ".join(insider_source_status.sec_rate_limited_tickers) if insider_source_status.sec_rate_limited_tickers else "none"}`
- Stale insider activity source tickers: `{", ".join(insider_source_status.stale_source_tickers) if insider_source_status.stale_source_tickers else "none"}`
- Missing insider activity source tickers: `{", ".join(insider_source_status.missing_source_tickers) if insider_source_status.missing_source_tickers else "none"}`
- ETF-gated insider activity tickers: `{", ".join(insider_source_status.skipped_etf_tickers) if insider_source_status.skipped_etf_tickers else "none"}`
- Insider activity validation rows: `{len(insider_validation_status_rows)}`
- Pending insider validations: `{", ".join(pending_insider_validations) if pending_insider_validations else "none"}`
- Partial insider validations: `{", ".join(partial_insider_validations) if partial_insider_validations else "none"}`
- Completed insider validations: `{", ".join(completed_insider_validations) if completed_insider_validations else "none"}`
- Insider activity warning tickers: `{", ".join(insider_signal_warnings) if insider_signal_warnings else "none"}`
- Short interest model: `{config.signals_short_interest_model_version}`
- Short interest shadow mode: `{config.signals_short_interest_shadow_mode}`
- Short interest source-backed coverage: `{short_interest_source_status.source_backed_ticker_count}/{short_interest_source_status.active_equity_count}`
- Short interest source-backed tickers: `{", ".join(short_interest_source_status.source_backed_tickers) if short_interest_source_status.source_backed_tickers else "none"}`
- Missing short interest source tickers: `{", ".join(short_interest_source_status.missing_source_tickers) if short_interest_source_status.missing_source_tickers else "none"}`
- ETF-gated short interest tickers: `{", ".join(short_interest_source_status.skipped_etf_tickers) if short_interest_source_status.skipped_etf_tickers else "none"}`
- Stale short interest source tickers: `{", ".join(short_interest_source_status.stale_source_tickers) if short_interest_source_status.stale_source_tickers else "none"}`
- Short interest provider order: `{", ".join(short_interest_provider.provider_order) if short_interest_provider.provider_order else "none"}`
- Short interest provider export valid rows: `{short_interest_provider.provider_export_valid_row_count}`
- Short interest provider export tickers: `{", ".join(short_interest_provider.provider_export_tickers) if short_interest_provider.provider_export_tickers else "none"}`
- Short interest provider cache files: `{short_interest_provider.cache_file_count}`
- Latest short interest provider cache timestamp: `{short_interest_provider.latest_cache_timestamp or "none"}`
- Short interest provider warnings: `{", ".join(short_interest_provider.warnings) if short_interest_provider.warnings else "none"}`
- Short interest missing coverage tickers: `{", ".join(short_interest_missing_plan.missing_tickers) if short_interest_missing_plan.missing_tickers else "none"}`
- Short interest valid missing-row tickers: `{", ".join(short_interest_missing_plan.valid_missing_tickers) if short_interest_missing_plan.valid_missing_tickers else "none"}`
- Short interest provider diagnostic status: `{", ".join(f"{item.ticker}:{item.classification}" for item in short_interest_missing_plan.diagnostics) if short_interest_missing_plan.diagnostics else "none"}`
- Short interest missing-provider template: `{_display_path(short_interest_missing_plan.template_path, config.project_root)}`
- Short interest missing-coverage blocked apply reason: `{short_interest_missing_plan.blocked_apply_reason or "none"}`
- Short interest backfill valid rows: `{short_interest_backfill_status.valid_row_count}`
- Short interest backfill valid tickers: `{", ".join(short_interest_backfill_status.valid_tickers) if short_interest_backfill_status.valid_tickers else "none"}`
- Short interest backfill blank placeholders: `{short_interest_backfill_status.blank_placeholder_count}`
- Short interest backfill invalid rows: `{short_interest_backfill_status.invalid_row_count}`
- Short interest projected source-backed coverage: `{short_interest_backfill_status.projected_source_backed_count}/{short_interest_backfill_status.active_equity_count}`
- Short interest blocked import reason: `{short_interest_backfill_status.blocked_import_reason or "none"}`
- Short interest signal coverage: `{short_interest_signal_coverage}/{len(short_interest_status)}`
- Short interest source rows: `{short_interest_source_snapshot_rows}`
- Latest short interest settlement date: `{latest_short_interest_source_date or "none"}`
- Short interest validation rows: `{len(short_interest_validation_status_rows)}`
- Pending short interest validations: `{", ".join(pending_short_interest_validations) if pending_short_interest_validations else "none"}`
- Partial short interest validations: `{", ".join(partial_short_interest_validations) if partial_short_interest_validations else "none"}`
- Completed short interest validations: `{", ".join(completed_short_interest_validations) if completed_short_interest_validations else "none"}`
- Short interest warning tickers: `{", ".join(short_interest_signal_warnings) if short_interest_signal_warnings else "none"}`
- Trader commentary model: `{config.signals_trader_commentary_model_version}`
- Trader commentary shadow mode: `{config.signals_trader_commentary_shadow_mode}`
- Trader commentary raw rows: `{trader_commentary_raw_rows}`
- Trader commentary claim rows: `{trader_commentary_claim_rows}`
- Trader commentary claim ticker coverage: `{trader_commentary_claim_coverage}/{len(trader_commentary_status)}`
- Trader commentary validation rows: `{trader_commentary_outcome_rows}`
- Trader commentary onboarding candidates: `{commentary_onboarding_plan.onboardable_count}`
- Trader commentary unmapped instrument labels: `{commentary_onboarding_plan.unmapped_count}`
- Trader commentary alias mappings: `{commentary_onboarding_plan.alias_count}`
- Trader commentary label dispositions: `{commentary_onboarding_plan.label_disposition_count}`
- Trader commentary intentionally unresolved labels: `{commentary_onboarding_plan.intentionally_unresolved_count}`
- Trader commentary ignored non-instrument labels: `{commentary_onboarding_plan.ignored_non_instrument_count}`
- Reference instruments: `{reference_asset_count}`
- Trader commentary browser capture runs: `{trader_commentary_browser_capture_run_rows}`
- Trader commentary browser capture items: `{trader_commentary_browser_capture_item_rows}`
- Latest trader commentary browser capture: `{latest_trader_commentary_browser_capture or "none"}`
- Latest trader commentary capture date: `{latest_trader_commentary_capture or "none"}`
- Latest trader commentary claim date: `{latest_trader_commentary_claim or "none"}`
- Latest trader commentary validation date: `{latest_trader_commentary_validation or "none"}`
- Trader commentary warning tickers: `{", ".join(trader_commentary_warning_tickers) if trader_commentary_warning_tickers else "none"}`

```text
Ticker | Type | Revision Score | Signal Status | Source Status | Validation Status | Evidence Decision | News/Catalyst Score | News/Catalyst Status | News/Catalyst Source | News/Catalyst Validation | Insider Score | Insider Status | Insider Source | Insider Validation | Short Interest Score | Short Interest Status | Short Interest Source | Short Interest Validation | Trader Commentary | Commentary Validation | Warnings
{advanced_signal_table}
```

## ETF Status

- ETF target coverage: `{etf_ready_count}/{len(etf_status)}`
- Missing ETF targets: `{", ".join(missing_etf_targets) if missing_etf_targets else "none"}`
- ETF alert reporting: `enabled through {config.alerts_etf_model_version}`

```text
Ticker | Price | NAV | Premium/Discount | PD Z-Score | NAV Date | Holdings Date | Holdings | Target Ready
{etf_table}
```

## Alert Summary

- Active alerts: `{len(active_alerts)}`
- Active equity alerts: `{len(active_equity_alerts)}`
- Active ETF alerts: `{len(active_etf_alerts)}`
- Alert warning tickers: `{", ".join(alert_warnings) if alert_warnings else "none"}`
- Equity alert model: `{config.alerts_equity_model_version}`
- ETF alerts: `{config.alerts_etf_model_version}`

```text
Ticker | Type | Alert | Priority | Status | Price | Target Low/Base/High | Gap | Opportunity | Confidence | Timing | Risk | Reasons | Risks | Warnings
{alert_table}
```

## Equity Alert Details

{equity_details}

## Outcome Validation Summary

- Outcome rows: `{len(outcome_status_rows)}`
- Equity outcome rows: `{len(equity_outcome_status_rows)}`
- ETF outcome rows: `{len(etf_outcome_status_rows)}`
- Pending outcomes: `{", ".join(pending_outcomes) if pending_outcomes else "none"}`
- Partial outcomes: `{", ".join(partial_outcomes) if partial_outcomes else "none"}`
- Completed outcomes: `{", ".join(completed_outcomes) if completed_outcomes else "none"}`

```text
Ticker | Type | Alert | Outcome | 5d | 20d | 60d | 120d | Hit Target | Hit Invalidation | MFE | MAE
{outcome_table}
```

## Portfolio Review Summary

- Portfolio review rows: `{len(portfolio_reviewed_rows)}`
- Held tickers: `{", ".join(row.ticker for row in held_rows) if held_rows else "none"}`
- Portfolio warning tickers: `{", ".join(portfolio_warning_tickers) if portfolio_warning_tickers else "none"}`
- Portfolio model version: `{config.portfolio_model_version}`
- Base currency: `{config.portfolio_base_currency}`

```text
Ticker | Type | Held | Quantity | Position Value | Weight | Sector Weight | Cash Available | Category | Max Add | Guidance | Warnings
{portfolio_table}
```

## Options/Sell-Put Advisory

- Options chain rows: `{option_chain_rows}`
- Option income review rows: `{option_income_review_rows}`
- Option risk review rows: `{option_risk_review_rows}`
- Option review outcome rows: `{option_review_outcome_rows}`
- Option position ledger rows: `{option_position_rows}`
- Option lifecycle review rows: `{option_lifecycle_rows}`
- Option position readiness: `{option_position_diagnostics.readiness_status}`
- Option staged source rows: `valid={option_position_diagnostics.valid_option_position_rows}, invalid={option_position_diagnostics.invalid_option_position_rows}, blank={option_position_diagnostics.blank_option_position_rows}`
- Option projected lifecycle rows: `{option_position_diagnostics.projected_option_lifecycle_rows}`
- Option readiness blockers: `{", ".join(option_position_diagnostics.blockers) if option_position_diagnostics.blockers else "none"}`
- Options chain source: `{config.options_chain_source}`
- Options provider readiness: `{option_provider.readiness_status}`
- Options provider blocked reason: `{option_provider.blocked_reason or "none"}`
- Option activation status: `{option_activation.activation_status}`
- Option activation blocked reason: `{option_activation.blocked_reason or "none"}`
- Minimum option chain coverage: `{option_activation.minimum_option_chain_coverage}`
- Minimum option review count: `{option_activation.minimum_option_review_count}`
- Options ibapi repair needed: `{option_activation.ibapi_repair_needed}`
- Options backfill valid rows: `{option_backfill_status.valid_row_count}`
- Options projected chain coverage: `{option_backfill_status.projected_loaded_ticker_count}/{option_backfill_status.fetch_universe_ticker_count}`
- Options minimum projected chain coverage: `{option_backfill_status.minimum_projected_loaded_ticker_count}/{option_backfill_status.minimum_ticker_count}`
- Options backfill apply ready: `{option_backfill_status.apply_ready}`
- Options broader coverage status: `{option_coverage_plan.coverage_status}`
- Options broader chain coverage: `{option_coverage_plan.effective_coverage_count}`
- Options broader raw chain coverage: `{option_coverage_plan.raw_coverage_count}`
- Options non-actionable chain tickers: `{", ".join(option_coverage_plan.non_actionable_tickers) if option_coverage_plan.non_actionable_tickers else "none"}`
- Options chain availability: `{format_option_chain_availability(option_chain_availability)}`
- Options valid broader backfill tickers: `{", ".join(option_coverage_plan.valid_backfill_tickers) if option_coverage_plan.valid_backfill_tickers else "none"}`
- Options projected broader chain coverage: `{option_coverage_plan.projected_loaded_ticker_count}/{option_coverage_plan.fetch_universe_ticker_count}`
- Options broader coverage apply ready: `{option_coverage_plan.apply_ready}`
- Options broader coverage blocked reason: `{option_coverage_plan.blocked_reason or "none"}`
- Options broader coverage notes: `{", ".join(option_coverage_plan.notes) if option_coverage_plan.notes else "none"}`
- Options fetch-universe tickers: `{len(option_fetch_tickers)}`
- Options missing chain tickers: `{", ".join(option_chain_missing_tickers) if option_chain_missing_tickers else "none"}`
- Latest option chain snapshot: `{latest_option_chain_snapshot or "none"}`
- Latest option income review date: `{latest_option_review or "none"}`
- Latest option risk review date: `{latest_option_risk_review or "none"}`
- Latest option outcome date: `{latest_option_outcome or "none"}`
- Latest option position open date: `{latest_option_position or "none"}`
- Latest option lifecycle review date: `{latest_option_lifecycle or "none"}`
- Options positions file: `{_display_path(config.options_positions_path, config.project_root)}`
- Option review warning tickers: `{", ".join(option_warning_tickers) if option_warning_tickers else "none"}`
- Mode: `read-only advisory; no broker writes or order placement`

```text
Ticker | Type | Category | Risk Category | Outcome | Lifecycle | Expiration Status | Expiration | Strike | Premium | Breakeven | Annualized Yield | Downside Buffer | Assignment Notional | Cash Requirement | P/L -10% | Realized P/L | Open P/L Proxy | Lifecycle Assignment | Return 5d | Return 20d | Latest Return | Above Strike | Above Breakeven | Positions | Unmatched Positions | Chain Rows | Commentary Claims | Warnings
{options_table}
```

## CSV Report Fields

The companion CSV report is written beside this Markdown report and contains:

```text
{_csv_columns_text()}
```

## Watchlist Status

Manual watchlist loading is available through:

```text
python -m target_opportunity_monitor load-watchlist
python -m target_opportunity_monitor list-assets
```

## Next Steps

1. Use `range-monitor` and `probe-market` for near-real-time buy/hold/trim/sell range checks; local notifications are stored and deduped, but no broker action is taken.
2. Review Phase 11B support/resistance, trend, and regime warnings inside the range table before changing exposure.
3. Keep analyst revision signals in shadow mode, along with news/catalyst, insider activity, short-interest, trader commentary, technical, and regime signals, until validation evidence matures.
4. Phase 10H.1 seeded real commentary rows; the next practical follow-up is commentary-driven asset onboarding or explicit market/index label mapping while Phase 10D remains gated.
"""


def write_daily_report(config: AppConfig, run_date: date | None = None) -> ReportResult:
    config.reports_dir.mkdir(parents=True, exist_ok=True)
    report_date = run_date or date.today()
    database_status = get_database_status(config.database_path)
    report_rows = build_daily_report_rows(config, database_status)
    report_body = build_daily_report_body(config, database_status, report_date)
    report_path = config.reports_dir / f"{report_date.isoformat()}-daily-report.md"
    csv_path = config.reports_dir / f"{report_date.isoformat()}-daily-report.csv"

    report_path.write_text(report_body, encoding="utf-8")
    with csv_path.open("w", newline="", encoding="utf-8") as output:
        writer = csv.DictWriter(output, fieldnames=REPORT_CSV_COLUMNS)
        writer.writeheader()
        writer.writerows(_build_report_csv_body(report_rows))

    return ReportResult(path=report_path, run_date=report_date, csv_path=csv_path)
