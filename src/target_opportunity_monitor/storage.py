from __future__ import annotations

from contextlib import closing
from dataclasses import dataclass, fields
from datetime import date, datetime
from pathlib import Path
import sqlite3

from .db import connect


@dataclass(frozen=True)
class Asset:
    ticker: str
    name: str | None = None
    asset_type: str | None = "equity"
    exchange: str | None = None
    currency: str | None = "USD"
    sector: str | None = None
    industry: str | None = None
    country: str | None = "US"
    active_flag: int = 1
    asset_role: str = "scoreable"
    source: str = "manual"
    as_of_date: str | None = None
    effective_date: str | None = None


@dataclass(frozen=True)
class Fundamental:
    ticker: str
    fiscal_period_end: str
    fiscal_period: str
    report_type: str
    currency: str | None = None
    revenue: float | None = None
    gross_profit: float | None = None
    operating_income: float | None = None
    ebitda: float | None = None
    ebit: float | None = None
    net_income: float | None = None
    eps: float | None = None
    diluted_eps: float | None = None
    cash_from_operations: float | None = None
    capital_expenditure: float | None = None
    free_cash_flow: float | None = None
    cash_and_equivalents: float | None = None
    total_debt: float | None = None
    net_debt: float | None = None
    total_assets: float | None = None
    total_equity: float | None = None
    shares_outstanding: float | None = None
    diluted_shares: float | None = None
    source: str = "manual"
    as_of_date: str | None = None
    effective_date: str | None = None


@dataclass(frozen=True)
class Estimate:
    ticker: str
    estimate_date: str
    fiscal_period_end: str
    metric: str
    fiscal_period: str | None = None
    currency: str | None = None
    consensus_mean: float | None = None
    consensus_median: float | None = None
    consensus_high: float | None = None
    consensus_low: float | None = None
    analyst_count: int | None = None
    revision_1m: float | None = None
    revision_3m: float | None = None
    source: str = "manual"
    as_of_date: str | None = None
    effective_date: str | None = None


@dataclass(frozen=True)
class Price:
    ticker: str
    price_date: str
    open: float | None
    high: float | None
    low: float | None
    close: float | None
    adjusted_close: float | None
    volume: float | None
    source: str
    as_of_date: str | None = None
    effective_date: str | None = None


@dataclass(frozen=True)
class PriceFeature:
    ticker: str
    feature_date: str
    current_price: float | None
    return_1d: float | None
    return_1m: float | None
    return_3m: float | None
    return_6m: float | None
    return_12m: float | None
    realized_volatility_20d: float | None
    realized_volatility_60d: float | None
    average_dollar_volume_20d: float | None
    latest_price_date: str | None
    source: str = "computed"
    as_of_date: str | None = None
    effective_date: str | None = None


@dataclass(frozen=True)
class PriceStatus:
    ticker: str
    row_count: int
    latest_price_date: str | None
    current_price: float | None
    feature_available: bool
    stale: bool


@dataclass(frozen=True)
class EtfNav:
    ticker: str
    nav_date: str
    nav_per_share: float
    market_price: float | None = None
    premium_discount: float | None = None
    shares_outstanding: float | None = None
    net_assets: float | None = None
    source: str = "manual_csv"
    as_of_date: str | None = None
    effective_date: str | None = None


@dataclass(frozen=True)
class EtfHolding:
    ticker: str
    holdings_date: str
    holding_ticker: str | None = None
    holding_name: str | None = None
    holding_asset_type: str | None = None
    weight: float = 0.0
    shares: float | None = None
    market_value: float | None = None
    sector: str | None = None
    country: str | None = None
    source: str = "manual_csv"
    as_of_date: str | None = None
    effective_date: str | None = None


@dataclass(frozen=True)
class EtfFeature:
    ticker: str
    feature_date: str
    nav_per_share: float | None
    market_price: float | None
    premium_discount: float | None
    premium_discount_average_60d: float | None
    premium_discount_volatility_60d: float | None
    premium_discount_zscore: float | None
    holdings_count: int | None
    top_10_weight: float | None
    largest_holding_weight: float | None
    equity_weight: float | None
    cash_weight: float | None
    latest_nav_date: str | None
    latest_holdings_date: str | None
    source: str = "computed"
    as_of_date: str | None = None
    effective_date: str | None = None


@dataclass(frozen=True)
class EtfStatus:
    ticker: str
    current_price: float | None
    nav_per_share: float | None
    premium_discount: float | None
    premium_discount_zscore: float | None
    latest_nav_date: str | None
    latest_holdings_date: str | None
    holdings_count: int | None
    target_ready: bool
    data_warnings: str | None


@dataclass(frozen=True)
class Signal:
    ticker: str
    signal_date: str
    signal_name: str
    signal_family: str
    value: float | None = None
    score: float | None = None
    direction: str | None = None
    reason_code: str | None = None
    source: str = "signals"
    model_version: str | None = None
    confidence: float | None = None
    data_warnings: str | None = None
    source_url: str | None = None
    notes: str | None = None
    as_of_date: str | None = None
    effective_date: str | None = None


@dataclass(frozen=True)
class StoredSignal:
    signal_id: int
    ticker: str
    signal_date: str
    signal_name: str
    signal_family: str
    value: float | None
    score: float | None
    direction: str | None
    reason_code: str | None
    source: str
    model_version: str | None
    confidence: float | None
    data_warnings: str | None
    source_url: str | None
    notes: str | None
    as_of_date: str | None
    effective_date: str | None


@dataclass(frozen=True)
class SignalStatus:
    ticker: str
    asset_type: str | None
    latest_signal_date: str | None
    composite_score: float | None
    composite_direction: str | None
    signal_count: int
    confidence: float | None
    model_version: str | None
    data_warnings: str | None


@dataclass(frozen=True)
class SignalOutcome:
    ticker: str
    signal_date: str
    signal_name: str
    signal_family: str
    outcome_date: str
    signal_id: int | None = None
    signal_score: float | None = None
    signal_direction: str | None = None
    outcome_status: str | None = None
    entry_price: float | None = None
    entry_price_date: str | None = None
    latest_price: float | None = None
    latest_price_date: str | None = None
    completed_horizons: str | None = None
    pending_horizons: str | None = None
    return_5d: float | None = None
    return_20d: float | None = None
    return_60d: float | None = None
    return_120d: float | None = None
    directional_hit_flag: int | None = None
    hit_status: str | None = None
    data_warnings: str | None = None
    model_version: str = "analyst_revision_validation_mvp_v1"
    source: str = "signal_validation"
    as_of_date: str | None = None
    effective_date: str | None = None


@dataclass(frozen=True)
class SignalOutcomeStatus:
    ticker: str
    signal_name: str
    signal_date: str
    outcome_date: str | None
    outcome_status: str | None
    signal_score: float | None
    signal_direction: str | None
    return_5d: float | None
    return_20d: float | None
    return_60d: float | None
    return_120d: float | None
    directional_hit_flag: int | None
    hit_status: str | None
    completed_horizons: str | None
    pending_horizons: str | None
    data_warnings: str | None


@dataclass(frozen=True)
class AnalystRevisionSourceSnapshot:
    ticker: str
    signal_date: str
    source: str
    source_url: str | None = None
    notes: str | None = None
    capture_method: str | None = None
    provider_status: str | None = None
    eps_current: float | None = None
    eps_30d_ago: float | None = None
    eps_90d_ago: float | None = None
    eps_high: float | None = None
    eps_low: float | None = None
    eps_average: float | None = None
    analyst_count: int | None = None
    revenue_current: float | None = None
    revenue_30d_ago: float | None = None
    revenue_90d_ago: float | None = None
    target_price_current: float | None = None
    target_price_90d_ago: float | None = None
    recommendation_current_strong_buy: float | None = None
    recommendation_current_buy: float | None = None
    recommendation_current_hold: float | None = None
    recommendation_current_sell: float | None = None
    recommendation_current_strong_sell: float | None = None
    recommendation_90d_ago_strong_buy: float | None = None
    recommendation_90d_ago_buy: float | None = None
    recommendation_90d_ago_hold: float | None = None
    recommendation_90d_ago_sell: float | None = None
    recommendation_90d_ago_strong_sell: float | None = None
    eps_revision_1m: float | None = None
    eps_revision_3m: float | None = None
    revenue_revision_1m: float | None = None
    revenue_revision_3m: float | None = None
    target_price_revision_3m: float | None = None
    recommendation_revision: float | None = None
    estimate_dispersion: float | None = None
    source_confidence: float | None = None
    data_warnings: str | None = None
    as_of_date: str | None = None
    effective_date: str | None = None


@dataclass(frozen=True)
class AnalystRevisionAggregate:
    ticker: str
    signal_date: str
    eps_revision_1m: float | None = None
    eps_revision_3m: float | None = None
    revenue_revision_1m: float | None = None
    revenue_revision_3m: float | None = None
    target_price_revision_3m: float | None = None
    recommendation_revision: float | None = None
    estimate_dispersion: float | None = None
    analyst_count: int | None = None
    source_count: int = 0
    sources: str | None = None
    source_policy: str = "weighted_median"
    aggregate_confidence: float | None = None
    source_disagreement: str | None = None
    data_warnings: str | None = None
    model_version: str | None = "analyst_revision_mvp_v1"
    source: str = "analyst_revision_aggregate"
    source_url: str | None = None
    notes: str | None = None
    as_of_date: str | None = None
    effective_date: str | None = None


@dataclass(frozen=True)
class NewsCatalystSourceSnapshot:
    ticker: str
    signal_date: str
    source: str
    source_url: str
    headline_or_event: str
    article_datetime: str | None = None
    event_date: str | None = None
    topic: str | None = None
    summary: str | None = None
    capture_method: str = "api"
    provider_status: str = "ok"
    sentiment_score: float | None = None
    catalyst_score: float | None = None
    urgency_score: float | None = None
    relevance_score: float | None = None
    source_confidence: float | None = None
    data_warnings: str | None = None
    as_of_date: str | None = None
    effective_date: str | None = None


@dataclass(frozen=True)
class NewsCatalystAggregate:
    ticker: str
    signal_date: str
    sentiment_score: float | None = None
    catalyst_score: float | None = None
    urgency_score: float | None = None
    confidence: float | None = None
    source_count: int = 0
    sources: str | None = None
    source_policy: str = "weighted_median"
    aggregate_confidence: float | None = None
    source_disagreement: str | None = None
    headline_or_event: str | None = None
    topic: str | None = None
    data_warnings: str | None = None
    model_version: str | None = "news_catalyst_mvp_v1"
    source: str = "news_catalyst_aggregate"
    source_url: str | None = None
    notes: str | None = None
    as_of_date: str | None = None
    effective_date: str | None = None


@dataclass(frozen=True)
class InsiderTransactionSourceSnapshot:
    ticker: str
    cik: str
    accession_number: str
    filing_date: str
    transaction_date: str | None = None
    owner_name: str | None = None
    owner_title: str | None = None
    transaction_code: str | None = None
    acquired_disposed_code: str | None = None
    shares: float | None = None
    price: float | None = None
    transaction_value: float | None = None
    source_url: str | None = None
    provider_status: str = "ok"
    data_warnings: str | None = None
    source: str = "sec_form4"
    as_of_date: str | None = None
    effective_date: str | None = None


@dataclass(frozen=True)
class ShortInterestSourceSnapshot:
    ticker: str
    settlement_date: str
    source: str
    source_url: str
    publication_date: str | None = None
    short_interest: float | None = None
    float_shares: float | None = None
    percent_float: float | None = None
    average_daily_volume: float | None = None
    days_to_cover: float | None = None
    notes: str | None = None
    data_warnings: str | None = None
    as_of_date: str | None = None
    effective_date: str | None = None


@dataclass(frozen=True)
class OptionChainSnapshot:
    ticker: str
    snapshot_timestamp: str
    expiration_date: str
    option_type: str
    strike: float
    bid: float
    ask: float
    last: float | None = None
    mark: float | None = None
    volume: float | None = None
    open_interest: float | None = None
    implied_volatility: float | None = None
    delta: float | None = None
    gamma: float | None = None
    theta: float | None = None
    vega: float | None = None
    source: str = "manual_csv"
    source_url: str | None = None
    as_of_date: str | None = None
    effective_date: str | None = None


@dataclass(frozen=True)
class OptionIncomeReview:
    ticker: str
    review_date: str
    snapshot_timestamp: str
    expiration_date: str
    option_type: str
    strike: float
    bid: float | None = None
    ask: float | None = None
    mid_premium: float | None = None
    breakeven: float | None = None
    premium_yield: float | None = None
    annualized_yield: float | None = None
    downside_buffer_pct: float | None = None
    breakeven_buffer_pct: float | None = None
    assignment_notional: float | None = None
    open_interest: float | None = None
    volume: float | None = None
    implied_volatility: float | None = None
    delta: float | None = None
    current_price: float | None = None
    range_state: str | None = None
    range_level: float | None = None
    review_category: str = "missing_range_context"
    risk_warnings: str | None = None
    commentary_claim_count: int = 0
    model_version: str = "options_sell_put_mvp_v1"
    source: str = "options_income"
    as_of_date: str | None = None
    effective_date: str | None = None


@dataclass(frozen=True)
class StoredOptionIncomeReview(OptionIncomeReview):
    option_income_review_id: int | None = None


@dataclass(frozen=True)
class OptionRiskReview:
    option_income_review_id: int
    ticker: str
    review_date: str
    risk_review_date: str
    expiration_date: str
    option_type: str
    strike: float
    mid_premium: float | None = None
    breakeven: float | None = None
    current_price: float | None = None
    assignment_notional: float | None = None
    premium_income: float | None = None
    cash_secured_requirement: float | None = None
    max_cash_secured_loss: float | None = None
    scenario_pl_5pct: float | None = None
    scenario_pl_10pct: float | None = None
    scenario_pl_20pct: float | None = None
    projected_assignment_weight: float | None = None
    cash_after_assignment: float | None = None
    cash_reserve_after_assignment: float | None = None
    max_contracts_advisory: int | None = None
    total_portfolio_value: float | None = None
    cash_available: float | None = None
    position_weight: float | None = None
    risk_category: str = "not_reviewable"
    risk_warnings: str | None = None
    model_version: str = "options_risk_margin_mvp_v1"
    source: str = "options_risk"
    as_of_date: str | None = None
    effective_date: str | None = None


@dataclass(frozen=True)
class OptionReviewOutcome:
    option_income_review_id: int
    ticker: str
    review_date: str
    outcome_date: str
    expiration_date: str
    option_type: str
    strike: float
    option_risk_review_id: int | None = None
    mid_premium: float | None = None
    breakeven: float | None = None
    review_price: float | None = None
    latest_underlying_price: float | None = None
    latest_underlying_price_date: str | None = None
    expiration_close: float | None = None
    expiration_price_date: str | None = None
    expiration_status: str | None = None
    outcome_status: str = "pending"
    completed_horizons: str | None = None
    pending_horizons: str | None = None
    return_5d: float | None = None
    return_20d: float | None = None
    return_to_latest: float | None = None
    above_strike_flag: int | None = None
    above_breakeven_flag: int | None = None
    touched_strike_flag: int | None = None
    touched_breakeven_flag: int | None = None
    max_favorable_excursion: float | None = None
    max_adverse_excursion: float | None = None
    linked_position_count: int = 0
    data_warnings: str | None = None
    model_version: str = "options_outcome_mvp_v1"
    source: str = "options_outcome"
    as_of_date: str | None = None
    effective_date: str | None = None


@dataclass(frozen=True)
class OptionPositionLedger:
    position_key: str
    ticker: str
    open_date: str
    expiration_date: str
    option_type: str
    side: str
    strike: float
    contracts: float
    premium: float
    position_id: str | None = None
    close_date: str | None = None
    close_price: float | None = None
    assigned_flag: int | None = None
    assignment_price: float | None = None
    fees: float | None = None
    account: str | None = None
    position_status: str | None = None
    roll_from_position_id: str | None = None
    roll_to_position_id: str | None = None
    underlying_assignment_date: str | None = None
    underlying_shares: float | None = None
    underlying_cost_basis: float | None = None
    tags: str | None = None
    data_warnings: str | None = None
    model_version: str = "options_position_ledger_mvp_v1"
    source: str = "manual_csv"
    source_url: str | None = None
    notes: str | None = None
    as_of_date: str | None = None
    effective_date: str | None = None


@dataclass(frozen=True)
class OptionPositionLifecycleReview:
    position_key: str
    ticker: str
    lifecycle_review_date: str
    open_date: str
    expiration_date: str
    option_type: str
    side: str
    strike: float
    contracts: float
    premium: float
    position_id: str | None = None
    close_date: str | None = None
    close_price: float | None = None
    assigned_flag: int | None = None
    assignment_price: float | None = None
    fees: float | None = None
    lifecycle_status: str = "not_reviewable"
    realized_pl: float | None = None
    open_pl_proxy: float | None = None
    assignment_notional: float | None = None
    cash_secured_requirement: float | None = None
    premium_income: float | None = None
    latest_option_mark: float | None = None
    latest_option_mark_timestamp: str | None = None
    underlying_assignment_date: str | None = None
    underlying_shares: float | None = None
    underlying_cost_basis: float | None = None
    linked_option_income_review_id: int | None = None
    linked_option_risk_review_id: int | None = None
    linked_option_review_outcome_id: int | None = None
    roll_from_position_id: str | None = None
    roll_to_position_id: str | None = None
    risk_warnings: str | None = None
    model_version: str = "options_lifecycle_mvp_v1"
    source: str = "options_lifecycle"
    as_of_date: str | None = None
    effective_date: str | None = None


@dataclass(frozen=True)
class OptionIncomeStatus:
    ticker: str
    asset_type: str | None
    asset_role: str | None
    review_date: str | None
    snapshot_timestamp: str | None
    expiration_date: str | None
    strike: float | None
    mid_premium: float | None
    breakeven: float | None
    annualized_yield: float | None
    downside_buffer_pct: float | None
    assignment_notional: float | None
    review_category: str | None
    risk_warnings: str | None
    commentary_claim_count: int | None
    option_chain_rows: int
    latest_snapshot_timestamp: str | None
    model_version: str | None


@dataclass(frozen=True)
class OptionRiskStatus:
    ticker: str
    asset_type: str | None
    asset_role: str | None
    risk_review_date: str | None
    expiration_date: str | None
    strike: float | None
    assignment_notional: float | None
    premium_income: float | None
    cash_secured_requirement: float | None
    max_cash_secured_loss: float | None
    scenario_pl_5pct: float | None
    scenario_pl_10pct: float | None
    scenario_pl_20pct: float | None
    projected_assignment_weight: float | None
    cash_after_assignment: float | None
    cash_reserve_after_assignment: float | None
    max_contracts_advisory: int | None
    total_portfolio_value: float | None
    cash_available: float | None
    risk_category: str | None
    risk_warnings: str | None
    model_version: str | None
    risk_review_count: int


@dataclass(frozen=True)
class OptionOutcomeStatus:
    ticker: str
    asset_type: str | None
    asset_role: str | None
    outcome_date: str | None
    expiration_date: str | None
    strike: float | None
    outcome_status: str | None
    expiration_status: str | None
    latest_underlying_price: float | None
    latest_underlying_price_date: str | None
    return_5d: float | None
    return_20d: float | None
    return_to_latest: float | None
    above_strike_flag: int | None
    above_breakeven_flag: int | None
    touched_strike_flag: int | None
    touched_breakeven_flag: int | None
    max_favorable_excursion: float | None
    max_adverse_excursion: float | None
    linked_position_count: int | None
    data_warnings: str | None
    model_version: str | None
    outcome_count: int


@dataclass(frozen=True)
class OptionPositionStatus:
    ticker: str
    asset_type: str | None
    asset_role: str | None
    position_count: int
    open_position_count: int
    assigned_position_count: int
    latest_open_date: str | None
    latest_expiration_date: str | None
    total_contracts: float | None
    data_warnings: str | None


@dataclass(frozen=True)
class OptionLifecycleStatus:
    ticker: str
    asset_type: str | None
    asset_role: str | None
    lifecycle_review_date: str | None
    lifecycle_status: str | None
    position_count: int
    lifecycle_review_count: int
    open_lifecycle_count: int
    closed_lifecycle_count: int
    expired_lifecycle_count: int
    assigned_lifecycle_count: int
    rolled_lifecycle_count: int
    realized_pl_total: float | None
    open_pl_proxy_total: float | None
    assignment_notional_total: float | None
    unmatched_position_count: int
    risk_warnings: str | None
    model_version: str | None


@dataclass(frozen=True)
class TraderCommentaryRaw:
    identity_key: str
    capture_date: str
    source: str
    source_author: str
    platform: str
    permission_scope: str
    language: str | None = None
    raw_text: str | None = None
    source_url: str | None = None
    capture_id: str | None = None
    text_file: str | None = None
    notes: str | None = None
    data_warnings: str | None = None
    as_of_date: str | None = None
    effective_date: str | None = None


@dataclass(frozen=True)
class StoredTraderCommentaryRaw:
    commentary_id: int
    identity_key: str
    capture_date: str
    source: str
    source_author: str
    platform: str
    permission_scope: str
    language: str | None
    raw_text: str | None
    source_url: str | None
    capture_id: str | None
    text_file: str | None
    notes: str | None
    data_warnings: str | None
    as_of_date: str | None
    effective_date: str | None


@dataclass(frozen=True)
class TraderCommentaryBrowserCaptureRun:
    run_id: str
    provider: str
    run_date: str
    started_at: str
    status: str
    target_url: str | None = None
    completed_at: str | None = None
    raw_dir: str | None = None
    dom_text_path: str | None = None
    page_html_path: str | None = None
    item_count: int = 0
    stored_count: int = 0
    skipped_count: int = 0
    warnings: str | None = None
    source: str = "browser_capture"
    as_of_date: str | None = None
    effective_date: str | None = None


@dataclass(frozen=True)
class StoredTraderCommentaryBrowserCaptureRun(TraderCommentaryBrowserCaptureRun):
    browser_capture_run_id: int = 0


@dataclass(frozen=True)
class TraderCommentaryBrowserCaptureItem:
    run_id: str
    provider: str
    item_key: str
    content_text: str
    observed_at: str
    target_url: str | None = None
    external_id: str | None = None
    canonical_url: str | None = None
    author_text: str | None = None
    created_at_text: str | None = None
    raw_excerpt: str | None = None
    accepted_flag: int = 1
    ingested_at: str | None = None
    data_warnings: str | None = None
    source: str = "x_browser_capture"
    as_of_date: str | None = None
    effective_date: str | None = None


@dataclass(frozen=True)
class StoredTraderCommentaryBrowserCaptureItem(TraderCommentaryBrowserCaptureItem):
    browser_capture_item_id: int = 0


@dataclass(frozen=True)
class TraderCommentaryDiscordCaptureRun:
    run_id: str
    provider: str
    run_date: str
    started_at: str
    status: str
    channel_id: str | None = None
    completed_at: str | None = None
    raw_dir: str | None = None
    messages_path: str | None = None
    raw_payload_path: str | None = None
    item_count: int = 0
    stored_count: int = 0
    skipped_count: int = 0
    warnings: str | None = None
    source: str = "discord_capture"
    as_of_date: str | None = None
    effective_date: str | None = None


@dataclass(frozen=True)
class StoredTraderCommentaryDiscordCaptureRun(TraderCommentaryDiscordCaptureRun):
    discord_capture_run_id: int = 0


@dataclass(frozen=True)
class TraderCommentaryDiscordCaptureItem:
    run_id: str
    provider: str
    item_key: str
    content_text: str
    observed_at: str
    channel_id: str | None = None
    guild_id: str | None = None
    message_id: str | None = None
    canonical_url: str | None = None
    author_id: str | None = None
    author_text: str | None = None
    message_timestamp: str | None = None
    raw_excerpt: str | None = None
    attachment_count: int = 0
    accepted_flag: int = 1
    ingested_at: str | None = None
    data_warnings: str | None = None
    source: str = "discord_bot_capture"
    as_of_date: str | None = None
    effective_date: str | None = None


@dataclass(frozen=True)
class StoredTraderCommentaryDiscordCaptureItem(TraderCommentaryDiscordCaptureItem):
    discord_capture_item_id: int = 0


@dataclass(frozen=True)
class TraderCommentaryClaim:
    claim_key: str
    claim_date: str
    claim_type: str
    source: str
    commentary_id: int | None = None
    ticker: str | None = None
    instrument_label: str | None = None
    direction: str | None = None
    level_low: float | None = None
    level_high: float | None = None
    target_price: float | None = None
    risk_level: float | None = None
    strike_price: float | None = None
    premium: float | None = None
    condition_text: str | None = None
    horizon_text: str | None = None
    confidence_text: str | None = None
    raw_excerpt: str | None = None
    parser_warnings: str | None = None
    source_url: str | None = None
    model_version: str | None = "trader_commentary_mvp_v1"
    as_of_date: str | None = None
    effective_date: str | None = None


@dataclass(frozen=True)
class StoredTraderCommentaryClaim:
    claim_id: int
    claim_key: str
    commentary_id: int | None
    claim_date: str
    ticker: str | None
    instrument_label: str | None
    claim_type: str
    direction: str | None
    level_low: float | None
    level_high: float | None
    target_price: float | None
    risk_level: float | None
    strike_price: float | None
    premium: float | None
    condition_text: str | None
    horizon_text: str | None
    confidence_text: str | None
    raw_excerpt: str | None
    parser_warnings: str | None
    source: str
    source_url: str | None
    model_version: str | None
    as_of_date: str | None
    effective_date: str | None


@dataclass(frozen=True)
class TraderCommentaryClaimOutcome:
    claim_key: str
    claim_type: str
    claim_date: str
    outcome_date: str
    claim_id: int | None = None
    ticker: str | None = None
    instrument_label: str | None = None
    outcome_status: str | None = None
    entry_price: float | None = None
    entry_price_date: str | None = None
    latest_price: float | None = None
    latest_price_date: str | None = None
    completed_horizons: str | None = None
    pending_horizons: str | None = None
    return_1d: float | None = None
    return_5d: float | None = None
    return_20d: float | None = None
    return_60d: float | None = None
    level_hit_flag: int | None = None
    directional_hit_flag: int | None = None
    hit_status: str | None = None
    data_warnings: str | None = None
    model_version: str = "trader_commentary_validation_mvp_v1"
    source: str = "trader_commentary_validation"
    as_of_date: str | None = None
    effective_date: str | None = None


@dataclass(frozen=True)
class TraderCommentaryStatus:
    ticker: str
    claim_count: int
    latest_claim_date: str | None
    latest_claim_type: str | None
    latest_direction: str | None
    latest_outcome_date: str | None
    latest_outcome_status: str | None
    latest_hit_status: str | None
    validation_count: int
    data_warnings: str | None


@dataclass(frozen=True)
class Target:
    ticker: str
    target_date: str
    base_target: float | None
    target_low: float | None
    target_high: float | None
    valuation_gap: float | None
    target_method: str | None
    uncertainty_band: float | None
    valuation_score: float | None = None
    valuation_confidence: float | None = None
    method_count: int | None = None
    target_reason: str | None = None
    data_warnings: str | None = None
    model_version: str = "valuation_mvp_v1"
    source: str = "valuation"
    as_of_date: str | None = None
    effective_date: str | None = None


@dataclass(frozen=True)
class ValuationStatus:
    ticker: str
    current_price: float | None
    target_date: str | None
    base_target: float | None
    target_low: float | None
    target_high: float | None
    valuation_gap: float | None
    valuation_score: float | None
    valuation_confidence: float | None
    method_count: int | None
    data_warnings: str | None


@dataclass(frozen=True)
class Score:
    ticker: str
    score_date: str
    valuation_gap_score: float | None = None
    quality_score: float | None = None
    growth_score: float | None = None
    revision_score: float | None = None
    momentum_score: float | None = None
    sentiment_score: float | None = None
    catalyst_score: float | None = None
    risk_score: float | None = None
    liquidity_score: float | None = None
    confidence_score: float | None = None
    timing_score: float | None = None
    expected_value_score: float | None = None
    opportunity_score: float | None = None
    asset_type: str | None = None
    score_model: str | None = None
    threshold_set: str | None = None
    score_reason: str | None = None
    data_warnings: str | None = None
    model_version: str = "equity_score_mvp_v1"
    source: str = "scoring"
    as_of_date: str | None = None
    effective_date: str | None = None


@dataclass(frozen=True)
class ScoreStatus:
    ticker: str
    asset_type: str | None
    current_price: float | None
    score_date: str | None
    opportunity_score: float | None
    expected_value_score: float | None
    valuation_gap_score: float | None
    revision_score: float | None
    momentum_score: float | None
    risk_score: float | None
    liquidity_score: float | None
    confidence_score: float | None
    timing_score: float | None
    score_model: str | None
    threshold_set: str | None
    data_warnings: str | None


@dataclass(frozen=True)
class Alert:
    ticker: str
    alert_type: str
    alert_timestamp: str
    priority: str | None = None
    status: str = "open"
    asset_type: str | None = None
    current_price: float | None = None
    base_target: float | None = None
    target_low: float | None = None
    target_high: float | None = None
    target_date: str | None = None
    score_date: str | None = None
    valuation_gap: float | None = None
    required_gap: float | None = None
    opportunity_score: float | None = None
    expected_value_score: float | None = None
    confidence_score: float | None = None
    timing_score: float | None = None
    risk_score: float | None = None
    liquidity_score: float | None = None
    data_quality_score: float | None = None
    main_reasons: str | None = None
    main_risks: str | None = None
    reason_codes: str | None = None
    risk_codes: str | None = None
    data_warnings: str | None = None
    invalidation: str | None = None
    alert_model: str | None = None
    threshold_set: str | None = None
    model_version: str = "equity_alert_mvp_v1"
    source: str = "alerts"
    as_of_date: str | None = None
    effective_date: str | None = None
    dedupe_key: str | None = None


@dataclass(frozen=True)
class AlertStatus:
    ticker: str
    asset_type: str | None
    alert_timestamp: str | None
    alert_type: str | None
    priority: str | None
    status: str | None
    target_date: str | None
    score_date: str | None
    current_price: float | None
    base_target: float | None
    target_low: float | None
    target_high: float | None
    valuation_gap: float | None
    opportunity_score: float | None
    expected_value_score: float | None
    confidence_score: float | None
    timing_score: float | None
    risk_score: float | None
    liquidity_score: float | None
    data_quality_score: float | None
    alert_model: str | None
    threshold_set: str | None
    main_reasons: str | None
    main_risks: str | None
    reason_codes: str | None
    risk_codes: str | None
    invalidation: str | None
    data_warnings: str | None


@dataclass(frozen=True)
class StoredAlert:
    alert_id: int
    ticker: str
    alert_type: str
    alert_timestamp: str
    priority: str | None
    status: str
    asset_type: str | None
    current_price: float | None
    base_target: float | None
    target_low: float | None
    target_high: float | None
    target_date: str | None
    score_date: str | None
    opportunity_score: float | None
    risk_score: float | None
    data_quality_score: float | None
    invalidation: str | None
    alert_model: str | None = None
    threshold_set: str | None = None


@dataclass(frozen=True)
class AlertOutcome:
    alert_id: int
    outcome_date: str
    ticker: str | None = None
    alert_type: str | None = None
    alert_timestamp: str | None = None
    asset_type: str | None = None
    alert_model: str | None = None
    threshold_set: str | None = None
    outcome_status: str | None = None
    entry_price: float | None = None
    entry_price_date: str | None = None
    latest_price: float | None = None
    latest_price_date: str | None = None
    target_price: float | None = None
    invalidation_price: float | None = None
    completed_horizons: str | None = None
    pending_horizons: str | None = None
    return_5d: float | None = None
    return_20d: float | None = None
    return_60d: float | None = None
    return_120d: float | None = None
    hit_target_flag: int | None = None
    hit_invalidation_flag: int | None = None
    max_favorable_excursion: float | None = None
    max_adverse_excursion: float | None = None
    data_warnings: str | None = None
    model_version: str | None = "alert_outcome_mvp_v1"
    user_action: str | None = None
    notes: str | None = None
    source: str = "outcomes"
    as_of_date: str | None = None
    effective_date: str | None = None


@dataclass(frozen=True)
class AlertOutcomeStatus:
    ticker: str
    alert_type: str | None
    alert_timestamp: str | None
    asset_type: str | None
    alert_model: str | None
    threshold_set: str | None
    outcome_date: str | None
    outcome_status: str | None
    entry_price: float | None
    entry_price_date: str | None
    latest_price: float | None
    latest_price_date: str | None
    target_price: float | None
    invalidation_price: float | None
    return_5d: float | None
    return_20d: float | None
    return_60d: float | None
    return_120d: float | None
    hit_target_flag: int | None
    hit_invalidation_flag: int | None
    max_favorable_excursion: float | None
    max_adverse_excursion: float | None
    completed_horizons: str | None
    pending_horizons: str | None
    data_warnings: str | None


@dataclass(frozen=True)
class PortfolioPosition:
    ticker: str
    quantity: float
    account: str = "default"
    position_date: str | None = None
    currency: str | None = "USD"
    market_price: float | None = None
    market_value: float | None = None
    base_market_value: float | None = None
    cost_basis_per_share: float | None = None
    cost_basis_total: float | None = None
    asset_type: str | None = None
    sector: str | None = None
    source: str = "manual_csv"
    as_of_date: str | None = None
    effective_date: str | None = None


@dataclass(frozen=True)
class PortfolioCash:
    cash_amount: float
    account: str = "default"
    cash_date: str | None = None
    currency: str | None = "USD"
    base_cash_amount: float | None = None
    source: str = "manual_csv"
    as_of_date: str | None = None
    effective_date: str | None = None


@dataclass(frozen=True)
class PortfolioReview:
    ticker: str
    review_date: str
    asset_type: str | None = None
    held_flag: int = 0
    quantity: float | None = None
    position_value: float | None = None
    cost_basis_total: float | None = None
    unrealized_gain_loss: float | None = None
    position_weight: float | None = None
    sector: str | None = None
    sector_weight: float | None = None
    cash_available: float | None = None
    total_portfolio_value: float | None = None
    review_category: str = "watch"
    sizing_guidance: str | None = None
    max_add_value: float | None = None
    risk_notes: str | None = None
    data_warnings: str | None = None
    model_version: str = "portfolio_context_mvp_v1"
    source: str = "portfolio"
    as_of_date: str | None = None
    effective_date: str | None = None


@dataclass(frozen=True)
class PortfolioReviewStatus:
    ticker: str
    asset_type: str | None
    review_date: str | None
    held_flag: int | None
    quantity: float | None
    position_value: float | None
    cost_basis_total: float | None
    unrealized_gain_loss: float | None
    position_weight: float | None
    sector: str | None
    sector_weight: float | None
    cash_available: float | None
    total_portfolio_value: float | None
    review_category: str | None
    sizing_guidance: str | None
    max_add_value: float | None
    risk_notes: str | None
    data_warnings: str | None
    model_version: str | None


@dataclass(frozen=True)
class QuoteSnapshot:
    ticker: str
    quote_timestamp: str
    bid: float | None = None
    ask: float | None = None
    last: float | None = None
    mark: float | None = None
    open: float | None = None
    high: float | None = None
    low: float | None = None
    close: float | None = None
    volume: float | None = None
    market_data_type: str | None = None
    source: str = "ibkr"
    as_of_date: str | None = None
    effective_date: str | None = None


@dataclass(frozen=True)
class IntradayGapSnapshot:
    ticker: str
    snapshot_timestamp: str
    current_price: float | None
    base_target: float | None
    target_low: float | None
    target_high: float | None
    gap_to_base: float | None
    gap_to_low: float | None
    gap_to_high: float | None
    etf_nav_per_share: float | None = None
    etf_nav_gap: float | None = None
    source: str = "intraday_probe"
    as_of_date: str | None = None
    effective_date: str | None = None


@dataclass(frozen=True)
class RangeSnapshot:
    ticker: str
    snapshot_timestamp: str
    asset_type: str | None = None
    current_price: float | None = None
    quote_timestamp: str | None = None
    quote_source: str | None = None
    quote_stale: int = 0
    base_target: float | None = None
    target_low: float | None = None
    target_high: float | None = None
    etf_nav_per_share: float | None = None
    etf_nav_gap: float | None = None
    opportunity_score: float | None = None
    confidence_score: float | None = None
    timing_score: float | None = None
    risk_score: float | None = None
    liquidity_score: float | None = None
    data_quality_score: float | None = None
    position_weight: float | None = None
    portfolio_review_category: str | None = None
    strong_buy_below: float | None = None
    starter_buy_below: float | None = None
    add_below: float | None = None
    hold_low: float | None = None
    hold_high: float | None = None
    trim_above: float | None = None
    reduce_or_sell_above: float | None = None
    risk_review_below: float | None = None
    nav_action_discount_below: float | None = None
    nav_watch_discount_below: float | None = None
    nav_fair_value: float | None = None
    nav_premium_warning_above: float | None = None
    etf_risk_review_level: float | None = None
    range_state: str = "no_range"
    previous_range_state: str | None = None
    reason_codes: str | None = None
    data_warnings: str | None = None
    technical_signal_date: str | None = None
    support_low: float | None = None
    support_high: float | None = None
    resistance_low: float | None = None
    resistance_high: float | None = None
    breakout_level: float | None = None
    downside_watch_level: float | None = None
    trend_repair_level: float | None = None
    moving_average_state: str | None = None
    drawdown_state: str | None = None
    price_location_state: str | None = None
    regime_signal_date: str | None = None
    regime_state: str | None = None
    relative_strength: float | None = None
    sector_rotation_rank: int | None = None
    technical_confidence: float | None = None
    regime_confidence: float | None = None
    model_version: str = "range_monitor_mvp_v1"
    source: str = "range_monitor"
    as_of_date: str | None = None
    effective_date: str | None = None


@dataclass(frozen=True)
class TechnicalSignalSnapshot:
    ticker: str
    signal_date: str
    current_price: float | None = None
    support_low: float | None = None
    support_high: float | None = None
    resistance_low: float | None = None
    resistance_high: float | None = None
    breakout_level: float | None = None
    downside_watch_level: float | None = None
    trend_repair_level: float | None = None
    short_ma: float | None = None
    medium_ma: float | None = None
    long_ma: float | None = None
    moving_average_state: str | None = None
    drawdown_pct: float | None = None
    drawdown_state: str | None = None
    price_location_state: str | None = None
    trend_score: float | None = None
    level_score: float | None = None
    confidence: float | None = None
    data_warnings: str | None = None
    model_version: str = "technical_levels_mvp_v1"
    source: str = "technical"
    as_of_date: str | None = None
    effective_date: str | None = None


@dataclass(frozen=True)
class RegimeSignalSnapshot:
    ticker: str
    signal_date: str
    proxy_type: str | None = None
    current_price: float | None = None
    benchmark_ticker: str | None = None
    benchmark_return: float | None = None
    return_lookback: float | None = None
    relative_strength: float | None = None
    trend_state: str | None = None
    risk_state: str | None = None
    sector_rotation_rank: int | None = None
    defensive_rotation_flag: int | None = None
    confidence: float | None = None
    data_warnings: str | None = None
    model_version: str = "market_regime_mvp_v1"
    source: str = "regime"
    as_of_date: str | None = None
    effective_date: str | None = None


@dataclass(frozen=True)
class FundamentalBenchmarkSnapshot:
    benchmark_date: str
    benchmark_type: str
    benchmark_key: str
    ticker_count: int = 0
    forward_pe_median: float | None = None
    trailing_pe_median: float | None = None
    ev_ebitda_median: float | None = None
    p_fcf_median: float | None = None
    p_s_median: float | None = None
    revenue_growth_median: float | None = None
    net_margin_median: float | None = None
    fcf_margin_median: float | None = None
    roe_median: float | None = None
    net_debt_ebitda_median: float | None = None
    opportunity_score_median: float | None = None
    valuation_gap_median: float | None = None
    data_warnings: str | None = None
    model_version: str = "fundamental_benchmark_mvp_v1"
    source: str = "computed"
    as_of_date: str | None = None
    effective_date: str | None = None


@dataclass(frozen=True)
class FundamentalComparisonSnapshot:
    ticker: str
    comparison_date: str
    sector: str | None = None
    industry: str | None = None
    sector_benchmark_ticker: str | None = None
    overall_peer_count: int = 0
    sector_peer_count: int = 0
    industry_peer_count: int = 0
    forward_pe: float | None = None
    sector_forward_pe_median: float | None = None
    overall_forward_pe_median: float | None = None
    sector_forward_pe_discount_pct: float | None = None
    sector_forward_pe_percentile: float | None = None
    ev_ebitda: float | None = None
    sector_ev_ebitda_median: float | None = None
    p_fcf: float | None = None
    sector_p_fcf_median: float | None = None
    net_margin: float | None = None
    sector_net_margin_median: float | None = None
    revenue_growth: float | None = None
    sector_revenue_growth_median: float | None = None
    net_debt_ebitda: float | None = None
    sector_net_debt_ebitda_median: float | None = None
    valuation_gap: float | None = None
    sector_valuation_gap_median: float | None = None
    opportunity_score: float | None = None
    sector_opportunity_score_median: float | None = None
    relative_strength_vs_spy: float | None = None
    relative_strength_vs_qqq: float | None = None
    relative_strength_vs_sector: float | None = None
    benchmark_status: str | None = None
    data_warnings: str | None = None
    model_version: str = "fundamental_benchmark_mvp_v1"
    source: str = "computed"
    as_of_date: str | None = None
    effective_date: str | None = None


@dataclass(frozen=True)
class ResearchRecommendationCandidate:
    recommendation_key: str
    ticker: str
    recommendation_date: str
    source: str
    status: str = "pending"
    topic: str | None = None
    rationale: str | None = None
    research_priority_score: float | None = None
    confidence: float | None = None
    source_count: int = 0
    evidence_count: int = 0
    source_mix: str | None = None
    metadata_status: str | None = None
    warning_codes: str | None = None
    promotion_blockers: str | None = None
    promoted_asset_role: str | None = None
    source_url: str | None = None
    external_id: str | None = None
    model_version: str = "research_recommendation_mvp_v1"
    as_of_date: str | None = None
    effective_date: str | None = None


@dataclass(frozen=True)
class StoredResearchRecommendationCandidate(ResearchRecommendationCandidate):
    research_recommendation_id: int = 0


@dataclass(frozen=True)
class ResearchRecommendationEvidence:
    evidence_key: str
    recommendation_key: str
    ticker: str
    evidence_date: str
    source: str
    source_type: str | None = None
    source_id: str | None = None
    source_url: str | None = None
    headline_or_excerpt: str | None = None
    reason: str | None = None
    confidence: float | None = None
    as_of_date: str | None = None
    effective_date: str | None = None


@dataclass(frozen=True)
class ResearchRecommendationDecision:
    recommendation_key: str
    ticker: str
    decision_timestamp: str
    new_status: str
    previous_status: str | None = None
    reason: str | None = None
    source: str = "research_recommendation"
    as_of_date: str | None = None
    effective_date: str | None = None


@dataclass(frozen=True)
class NotificationEvent:
    ticker: str
    event_timestamp: str
    event_type: str
    asset_type: str | None = None
    severity: str | None = None
    previous_state: str | None = None
    current_state: str | None = None
    trigger_price: float | None = None
    range_level: float | None = None
    reason_codes: str | None = None
    status: str = "pending"
    cooldown_until: str | None = None
    dedupe_key: str | None = None
    model_version: str = "range_monitor_mvp_v1"
    source: str = "notifications"
    as_of_date: str | None = None
    effective_date: str | None = None


@dataclass(frozen=True)
class NotificationEventStatus:
    notification_event_id: int
    ticker: str
    event_timestamp: str
    event_type: str
    asset_type: str | None
    severity: str | None
    previous_state: str | None
    current_state: str | None
    trigger_price: float | None
    range_level: float | None
    reason_codes: str | None
    status: str
    cooldown_until: str | None
    model_version: str


@dataclass(frozen=True)
class NotificationDelivery:
    notification_event_id: int
    channel: str
    delivery_timestamp: str
    status: str
    details: str | None = None
    source: str = "notifications"
    as_of_date: str | None = None
    effective_date: str | None = None


@dataclass(frozen=True)
class NotificationDeliveryStatus:
    notification_delivery_id: int
    notification_event_id: int
    ticker: str | None
    channel: str
    delivery_timestamp: str
    status: str
    details: str | None
    as_of_date: str | None
    effective_date: str | None


@dataclass(frozen=True)
class AssetChangeEvent:
    event_timestamp: str
    ticker: str
    event_type: str
    previous_active_flag: int | None = None
    new_active_flag: int | None = None
    reason: str | None = None
    details: str | None = None
    source: str = "asset_management"
    as_of_date: str | None = None
    effective_date: str | None = None


@dataclass(frozen=True)
class MissingTickerCandidate:
    ticker: str
    first_seen_source: str
    source_file: str | None = None
    source_row: str | None = None
    detected_asset_type: str | None = None
    recommended_asset_role: str | None = None
    confidence: float | None = None
    blockers: str | None = None
    warnings: str | None = None
    status: str = "detected"
    next_command: str | None = None
    metadata_name: str | None = None
    metadata_exchange: str | None = None
    metadata_currency: str | None = "USD"
    metadata_sector: str | None = None
    metadata_industry: str | None = None
    metadata_country: str | None = "US"
    source_url: str | None = None
    as_of_date: str | None = None
    effective_date: str | None = None
    missing_ticker_candidate_id: int | None = None


@dataclass(frozen=True)
class MissingTickerResolutionEvent:
    event_timestamp: str
    ticker: str
    event_type: str
    previous_status: str | None = None
    new_status: str | None = None
    source: str = "missing_ticker_resolver"
    details: str | None = None
    warnings: str | None = None
    as_of_date: str | None = None
    effective_date: str | None = None
    missing_ticker_resolution_event_id: int | None = None


@dataclass(frozen=True)
class TraderCommentaryInstrumentAlias:
    instrument_label: str
    canonical_ticker: str
    asset_type: str = "equity"
    asset_role: str = "commentary_validation"
    source: str = "manual_csv"
    notes: str | None = None
    as_of_date: str | None = None
    effective_date: str | None = None


@dataclass(frozen=True)
class PipelineRun:
    pipeline_run_id: int
    run_type: str
    status: str
    started_at: str
    finished_at: str | None
    source: str
    summary: str | None
    as_of_date: str | None
    effective_date: str | None


@dataclass(frozen=True)
class PipelineStepResult:
    pipeline_step_result_id: int
    pipeline_run_id: int
    step_name: str
    status: str
    rows_loaded: int
    warnings: str | None
    started_at: str
    finished_at: str | None
    source: str
    as_of_date: str | None
    effective_date: str | None


@dataclass(frozen=True)
class RefreshReadinessStatus:
    ticker: str
    asset_type: str
    price_ready: bool
    feature_ready: bool
    fundamentals_ready: bool
    estimates_ready: bool
    etf_nav_ready: bool
    etf_holdings_ready: bool
    target_ready: bool
    score_ready: bool
    phase4_ready: bool
    warnings: tuple[str, ...]


def normalize_ticker(ticker: str) -> str:
    return ticker.strip().upper()


def normalize_asset_role(value: str | None) -> str:
    cleaned = (value or "scoreable").strip().lower()
    if cleaned in {"commentary", "reference", "commentary_reference"}:
        return "commentary_validation"
    if cleaned in {"0", "false", "inactive", "disabled"}:
        return "inactive"
    if cleaned in {"scoreable", "commentary_validation", "regime_proxy", "inactive"}:
        return cleaned
    return "scoreable"


def is_scoreable_asset(asset: Asset) -> bool:
    return asset.active_flag == 1 and normalize_asset_role(asset.asset_role) == "scoreable"


def _dataclass_payload(instance: object) -> dict[str, object]:
    payload = {field.name: getattr(instance, field.name) for field in fields(instance)}
    if "ticker" in payload and isinstance(payload["ticker"], str):
        payload["ticker"] = normalize_ticker(payload["ticker"])
    return payload


def _upsert(
    database_path: Path,
    table: str,
    payload: dict[str, object],
    conflict_columns: tuple[str, ...],
    update_columns: tuple[str, ...],
) -> None:
    columns = tuple(payload.keys())
    placeholders = ", ".join("?" for _ in columns)
    column_list = ", ".join(columns)
    conflict_list = ", ".join(conflict_columns)
    update_list = ", ".join(f"{column} = excluded.{column}" for column in update_columns)
    if update_list:
        update_list = f"{update_list}, loaded_at = CURRENT_TIMESTAMP"
    else:
        update_list = "loaded_at = CURRENT_TIMESTAMP"

    sql = f"""
        INSERT INTO {table} ({column_list})
        VALUES ({placeholders})
        ON CONFLICT ({conflict_list})
        DO UPDATE SET {update_list}
    """

    with closing(connect(database_path)) as connection:
        connection.execute(sql, tuple(payload[column] for column in columns))
        connection.commit()


def upsert_asset(database_path: Path, asset: Asset) -> None:
    payload = _dataclass_payload(asset)
    payload["asset_role"] = normalize_asset_role(str(payload.get("asset_role") or "scoreable"))
    if payload["asset_role"] == "inactive":
        payload["active_flag"] = 0
    _upsert(
        database_path=database_path,
        table="assets",
        payload=payload,
        conflict_columns=("ticker",),
        update_columns=(
            "name",
            "asset_type",
            "exchange",
            "currency",
            "sector",
            "industry",
            "country",
            "active_flag",
            "asset_role",
            "source",
            "as_of_date",
            "effective_date",
        ),
    )


def list_assets(database_path: Path) -> list[Asset]:
    with closing(sqlite3.connect(database_path)) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            """
            SELECT ticker, name, asset_type, exchange, currency, sector, industry,
                   country, active_flag, asset_role, source, as_of_date, effective_date
            FROM assets
            ORDER BY ticker
            """
        ).fetchall()
    return [Asset(**dict(row)) for row in rows]


def count_assets(database_path: Path) -> int:
    return count_rows_by_table(database_path, "assets")


def count_active_assets(database_path: Path) -> int:
    with closing(sqlite3.connect(database_path)) as connection:
        row = connection.execute(
            "SELECT COUNT(*) FROM assets WHERE active_flag = 1"
        ).fetchone()
    return int(row[0]) if row else 0


def count_inactive_assets(database_path: Path) -> int:
    with closing(sqlite3.connect(database_path)) as connection:
        row = connection.execute(
            "SELECT COUNT(*) FROM assets WHERE active_flag != 1 OR asset_role = 'inactive'"
        ).fetchone()
    return int(row[0]) if row else 0


def latest_asset(database_path: Path, ticker: str) -> Asset | None:
    with closing(sqlite3.connect(database_path)) as connection:
        connection.row_factory = sqlite3.Row
        row = connection.execute(
            """
            SELECT ticker, name, asset_type, exchange, currency, sector, industry,
                   country, active_flag, asset_role, source, as_of_date, effective_date
            FROM assets
            WHERE ticker = ?
            LIMIT 1
            """,
            (normalize_ticker(ticker),),
        ).fetchone()
    return Asset(**dict(row)) if row else None


def set_asset_active_flag(
    database_path: Path,
    ticker: str,
    active_flag: int,
    source: str = "asset_management",
    as_of_date: str | None = None,
    effective_date: str | None = None,
) -> Asset | None:
    normalized = normalize_ticker(ticker)
    with closing(connect(database_path)) as connection:
        connection.execute(
            """
            UPDATE assets
            SET active_flag = ?, source = ?, as_of_date = ?, effective_date = ?
            WHERE ticker = ?
            """,
            (active_flag, source, as_of_date, effective_date, normalized),
        )
        connection.commit()
    return latest_asset(database_path, normalized)


def set_asset_role(
    database_path: Path,
    ticker: str,
    asset_role: str,
    source: str = "asset_management",
    as_of_date: str | None = None,
    effective_date: str | None = None,
) -> Asset | None:
    normalized = normalize_ticker(ticker)
    role = normalize_asset_role(asset_role)
    active_flag = 0 if role == "inactive" else 1
    with closing(connect(database_path)) as connection:
        connection.execute(
            """
            UPDATE assets
            SET asset_role = ?, active_flag = ?, source = ?, as_of_date = ?, effective_date = ?
            WHERE ticker = ?
            """,
            (role, active_flag, source, as_of_date, effective_date, normalized),
        )
        connection.commit()
    return latest_asset(database_path, normalized)


def list_scoreable_assets(database_path: Path) -> list[Asset]:
    return [asset for asset in list_assets(database_path) if is_scoreable_asset(asset)]


def count_scoreable_assets(database_path: Path) -> int:
    with closing(sqlite3.connect(database_path)) as connection:
        row = connection.execute(
            "SELECT COUNT(*) FROM assets WHERE active_flag = 1 AND asset_role = 'scoreable'"
        ).fetchone()
    return int(row[0]) if row else 0


def count_reference_assets(database_path: Path) -> int:
    with closing(sqlite3.connect(database_path)) as connection:
        row = connection.execute(
            """
            SELECT COUNT(*)
            FROM assets
            WHERE active_flag = 1
              AND asset_role IN ('commentary_validation', 'regime_proxy')
            """
        ).fetchone()
    return int(row[0]) if row else 0


def insert_asset_change_event(database_path: Path, event: AssetChangeEvent) -> None:
    payload = _dataclass_payload(event)
    columns = tuple(payload.keys())
    placeholders = ", ".join("?" for _ in columns)
    column_list = ", ".join(columns)
    with closing(connect(database_path)) as connection:
        connection.execute(
            f"INSERT INTO asset_change_events ({column_list}) VALUES ({placeholders})",
            tuple(payload[column] for column in columns),
        )
        connection.commit()


def upsert_missing_ticker_candidate(
    database_path: Path,
    candidate: MissingTickerCandidate,
) -> None:
    payload = _dataclass_payload(candidate)
    payload.pop("missing_ticker_candidate_id", None)
    payload["ticker"] = normalize_ticker(str(payload.get("ticker") or ""))
    _upsert(
        database_path=database_path,
        table="missing_ticker_candidates",
        payload=payload,
        conflict_columns=("ticker", "first_seen_source", "source_file", "source_row"),
        update_columns=(
            "detected_asset_type",
            "recommended_asset_role",
            "confidence",
            "blockers",
            "warnings",
            "status",
            "next_command",
            "metadata_name",
            "metadata_exchange",
            "metadata_currency",
            "metadata_sector",
            "metadata_industry",
            "metadata_country",
            "source_url",
            "as_of_date",
            "effective_date",
        ),
    )


def list_missing_ticker_candidates(
    database_path: Path,
    status: str | None = None,
    source: str | None = None,
) -> list[MissingTickerCandidate]:
    conditions: list[str] = []
    params: list[object] = []
    if status:
        conditions.append("status = ?")
        params.append(status)
    if source:
        conditions.append("first_seen_source = ?")
        params.append(source)
    where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    with closing(sqlite3.connect(database_path)) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            f"""
            SELECT missing_ticker_candidate_id, ticker, first_seen_source,
                   source_file, source_row, detected_asset_type,
                   recommended_asset_role, confidence, blockers, warnings,
                   status, next_command, metadata_name, metadata_exchange,
                   metadata_currency, metadata_sector, metadata_industry,
                   metadata_country, source_url, as_of_date, effective_date
            FROM missing_ticker_candidates
            {where_clause}
            ORDER BY
                CASE status
                    WHEN 'blocked' THEN 0
                    WHEN 'ready_to_onboard' THEN 1
                    WHEN 'metadata_resolved' THEN 2
                    WHEN 'detected' THEN 3
                    WHEN 'onboarded' THEN 4
                    WHEN 'hydrated' THEN 5
                    ELSE 6
                END,
                ticker,
                missing_ticker_candidate_id
            """,
            tuple(params),
        ).fetchall()
    return [MissingTickerCandidate(**dict(row)) for row in rows]


def latest_missing_ticker_candidate(
    database_path: Path,
    ticker: str,
    source: str | None = None,
) -> MissingTickerCandidate | None:
    params: list[object] = [normalize_ticker(ticker)]
    source_clause = ""
    if source:
        source_clause = "AND first_seen_source = ?"
        params.append(source)
    with closing(sqlite3.connect(database_path)) as connection:
        connection.row_factory = sqlite3.Row
        row = connection.execute(
            f"""
            SELECT missing_ticker_candidate_id, ticker, first_seen_source,
                   source_file, source_row, detected_asset_type,
                   recommended_asset_role, confidence, blockers, warnings,
                   status, next_command, metadata_name, metadata_exchange,
                   metadata_currency, metadata_sector, metadata_industry,
                   metadata_country, source_url, as_of_date, effective_date
            FROM missing_ticker_candidates
            WHERE ticker = ?
            {source_clause}
            ORDER BY loaded_at DESC, missing_ticker_candidate_id DESC
            LIMIT 1
            """,
            tuple(params),
        ).fetchone()
    return MissingTickerCandidate(**dict(row)) if row else None


def update_missing_ticker_candidate_status(
    database_path: Path,
    ticker: str,
    status: str,
    first_seen_source: str | None = None,
    blockers: str | None = None,
    warnings: str | None = None,
    next_command: str | None = None,
) -> int:
    conditions = ["ticker = ?"]
    params: list[object] = [status]
    update_columns = ["status = ?"]
    if blockers is not None:
        update_columns.append("blockers = ?")
        params.append(blockers)
    if warnings is not None:
        update_columns.append("warnings = ?")
        params.append(warnings)
    if next_command is not None:
        update_columns.append("next_command = ?")
        params.append(next_command)
    params.append(normalize_ticker(ticker))
    if first_seen_source:
        conditions.append("first_seen_source = ?")
        params.append(first_seen_source)
    with closing(connect(database_path)) as connection:
        cursor = connection.execute(
            f"""
            UPDATE missing_ticker_candidates
            SET {', '.join(update_columns)}, updated_at = CURRENT_TIMESTAMP
            WHERE {' AND '.join(conditions)}
            """,
            tuple(params),
        )
        connection.commit()
        return int(cursor.rowcount)


def insert_missing_ticker_resolution_event(
    database_path: Path,
    event: MissingTickerResolutionEvent,
) -> None:
    payload = _dataclass_payload(event)
    payload.pop("missing_ticker_resolution_event_id", None)
    columns = tuple(payload.keys())
    placeholders = ", ".join("?" for _ in columns)
    column_list = ", ".join(columns)
    with closing(connect(database_path)) as connection:
        connection.execute(
            f"""
            INSERT INTO missing_ticker_resolution_events ({column_list})
            VALUES ({placeholders})
            """,
            tuple(payload[column] for column in columns),
        )
        connection.commit()


def upsert_trader_commentary_instrument_alias(
    database_path: Path,
    alias: TraderCommentaryInstrumentAlias,
) -> None:
    payload = _dataclass_payload(alias)
    payload["instrument_label"] = str(payload["instrument_label"]).strip()
    payload["canonical_ticker"] = normalize_ticker(str(payload["canonical_ticker"]))
    payload["asset_role"] = normalize_asset_role(str(payload.get("asset_role") or "commentary_validation"))
    _upsert(
        database_path=database_path,
        table="trader_commentary_instrument_aliases",
        payload=payload,
        conflict_columns=("instrument_label",),
        update_columns=(
            "canonical_ticker",
            "asset_type",
            "asset_role",
            "source",
            "notes",
            "as_of_date",
            "effective_date",
        ),
    )


def list_trader_commentary_instrument_aliases(
    database_path: Path,
) -> list[TraderCommentaryInstrumentAlias]:
    with closing(sqlite3.connect(database_path)) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            """
            SELECT instrument_label, canonical_ticker, asset_type, asset_role, source,
                   notes, as_of_date, effective_date
            FROM trader_commentary_instrument_aliases
            ORDER BY instrument_label
            """
        ).fetchall()
    return [TraderCommentaryInstrumentAlias(**dict(row)) for row in rows]


def trader_commentary_alias_map(database_path: Path) -> dict[str, TraderCommentaryInstrumentAlias]:
    return {
        alias.instrument_label.strip().lower(): alias
        for alias in list_trader_commentary_instrument_aliases(database_path)
    }


def upsert_fundamental(database_path: Path, fundamental: Fundamental) -> None:
    payload = _dataclass_payload(fundamental)
    _upsert(
        database_path=database_path,
        table="fundamentals",
        payload=payload,
        conflict_columns=(
            "ticker",
            "fiscal_period_end",
            "fiscal_period",
            "report_type",
            "source",
        ),
        update_columns=tuple(
            column
            for column in payload
            if column
            not in {
                "ticker",
                "fiscal_period_end",
                "fiscal_period",
                "report_type",
                "source",
            }
        ),
    )


def upsert_estimate(database_path: Path, estimate: Estimate) -> None:
    payload = _dataclass_payload(estimate)
    _upsert(
        database_path=database_path,
        table="estimates",
        payload=payload,
        conflict_columns=("ticker", "estimate_date", "fiscal_period_end", "metric", "source"),
        update_columns=tuple(
            column
            for column in payload
            if column
            not in {"ticker", "estimate_date", "fiscal_period_end", "metric", "source"}
        ),
    )


def list_fundamentals(database_path: Path, ticker: str) -> list[Fundamental]:
    with closing(sqlite3.connect(database_path)) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            """
            SELECT ticker, fiscal_period_end, fiscal_period, report_type, currency,
                   revenue, gross_profit, operating_income, ebitda, ebit,
                   net_income, eps, diluted_eps, cash_from_operations,
                   capital_expenditure, free_cash_flow, cash_and_equivalents,
                   total_debt, net_debt, total_assets, total_equity,
                   shares_outstanding, diluted_shares, source, as_of_date,
                   effective_date
            FROM fundamentals
            WHERE ticker = ?
            ORDER BY fiscal_period_end, fiscal_period, report_type
            """,
            (normalize_ticker(ticker),),
        ).fetchall()
    return [Fundamental(**dict(row)) for row in rows]


def latest_fundamental(database_path: Path, ticker: str) -> Fundamental | None:
    fundamentals = list_fundamentals(database_path, ticker)
    if not fundamentals:
        return None
    return fundamentals[-1]


def list_estimates(database_path: Path, ticker: str) -> list[Estimate]:
    with closing(sqlite3.connect(database_path)) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            """
            SELECT ticker, estimate_date, fiscal_period_end, metric, fiscal_period,
                   currency, consensus_mean, consensus_median, consensus_high,
                   consensus_low, analyst_count, revision_1m, revision_3m,
                   source, as_of_date, effective_date
            FROM estimates
            WHERE ticker = ?
            ORDER BY estimate_date, fiscal_period_end, metric
            """,
            (normalize_ticker(ticker),),
        ).fetchall()
    return [Estimate(**dict(row)) for row in rows]


def latest_estimate(database_path: Path, ticker: str, metric: str) -> Estimate | None:
    wanted_metric = metric.strip().lower()
    estimates = [
        estimate
        for estimate in list_estimates(database_path, ticker)
        if estimate.metric.strip().lower() == wanted_metric
    ]
    if not estimates:
        return None
    return estimates[-1]


def upsert_price(database_path: Path, price: Price) -> None:
    payload = _dataclass_payload(price)
    _upsert(
        database_path=database_path,
        table="prices",
        payload=payload,
        conflict_columns=("ticker", "price_date", "source"),
        update_columns=(
            "open",
            "high",
            "low",
            "close",
            "adjusted_close",
            "volume",
            "as_of_date",
            "effective_date",
        ),
    )


def upsert_prices(database_path: Path, prices: list[Price]) -> None:
    for price in prices:
        upsert_price(database_path, price)


def list_prices(database_path: Path, ticker: str) -> list[Price]:
    with closing(sqlite3.connect(database_path)) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            """
            SELECT ticker, price_date, open, high, low, close, adjusted_close,
                   volume, source, as_of_date, effective_date
            FROM prices
            WHERE ticker = ?
            ORDER BY price_date
            """,
            (normalize_ticker(ticker),),
        ).fetchall()
    return [Price(**dict(row)) for row in rows]


def upsert_price_feature(database_path: Path, feature: PriceFeature) -> None:
    payload = _dataclass_payload(feature)
    _upsert(
        database_path=database_path,
        table="price_features",
        payload=payload,
        conflict_columns=("ticker", "feature_date", "source"),
        update_columns=tuple(
            column
            for column in payload
            if column not in {"ticker", "feature_date", "source"}
        ),
    )


def latest_price_feature(database_path: Path, ticker: str) -> PriceFeature | None:
    with closing(sqlite3.connect(database_path)) as connection:
        connection.row_factory = sqlite3.Row
        row = connection.execute(
            """
            SELECT ticker, feature_date, current_price, return_1d, return_1m,
                   return_3m, return_6m, return_12m, realized_volatility_20d,
                   realized_volatility_60d, average_dollar_volume_20d,
                   latest_price_date, source, as_of_date, effective_date
            FROM price_features
            WHERE ticker = ?
            ORDER BY feature_date DESC
            LIMIT 1
            """,
            (normalize_ticker(ticker),),
        ).fetchone()
    return PriceFeature(**dict(row)) if row else None


def upsert_quote_snapshot(database_path: Path, snapshot: QuoteSnapshot) -> None:
    payload = _dataclass_payload(snapshot)
    _upsert(
        database_path=database_path,
        table="quote_snapshots",
        payload=payload,
        conflict_columns=("ticker", "quote_timestamp", "source"),
        update_columns=tuple(
            column
            for column in payload
            if column not in {"ticker", "quote_timestamp", "source"}
        ),
    )


def latest_quote_snapshot(database_path: Path, ticker: str) -> QuoteSnapshot | None:
    with closing(sqlite3.connect(database_path)) as connection:
        connection.row_factory = sqlite3.Row
        row = connection.execute(
            """
            SELECT ticker, quote_timestamp, bid, ask, last, mark, open, high, low,
                   close, volume, market_data_type, source, as_of_date,
                   effective_date
            FROM quote_snapshots
            WHERE ticker = ?
            ORDER BY quote_timestamp DESC, loaded_at DESC
            LIMIT 1
            """,
            (normalize_ticker(ticker),),
        ).fetchone()
    return QuoteSnapshot(**dict(row)) if row else None


def latest_quote_timestamp(database_path: Path) -> str | None:
    with closing(sqlite3.connect(database_path)) as connection:
        row = connection.execute(
            "SELECT MAX(quote_timestamp) FROM quote_snapshots"
        ).fetchone()
    return row[0] if row and row[0] is not None else None


def upsert_intraday_gap_snapshot(
    database_path: Path,
    snapshot: IntradayGapSnapshot,
) -> None:
    payload = _dataclass_payload(snapshot)
    _upsert(
        database_path=database_path,
        table="intraday_gap_snapshots",
        payload=payload,
        conflict_columns=("ticker", "snapshot_timestamp", "source"),
        update_columns=tuple(
            column
            for column in payload
            if column not in {"ticker", "snapshot_timestamp", "source"}
        ),
    )


def latest_intraday_gap_timestamp(database_path: Path) -> str | None:
    with closing(sqlite3.connect(database_path)) as connection:
        row = connection.execute(
            "SELECT MAX(snapshot_timestamp) FROM intraday_gap_snapshots"
        ).fetchone()
    return row[0] if row and row[0] is not None else None


def upsert_range_snapshot(database_path: Path, snapshot: RangeSnapshot) -> None:
    payload = _dataclass_payload(snapshot)
    _upsert(
        database_path=database_path,
        table="range_snapshots",
        payload=payload,
        conflict_columns=("ticker", "snapshot_timestamp", "model_version", "source"),
        update_columns=tuple(
            column
            for column in payload
            if column not in {"ticker", "snapshot_timestamp", "model_version", "source"}
        ),
    )


def latest_range_snapshot(database_path: Path, ticker: str) -> RangeSnapshot | None:
    with closing(sqlite3.connect(database_path)) as connection:
        connection.row_factory = sqlite3.Row
        row = connection.execute(
            """
            SELECT ticker, snapshot_timestamp, asset_type, current_price,
                   quote_timestamp, quote_source, quote_stale, base_target,
                   target_low, target_high, etf_nav_per_share, etf_nav_gap,
                   opportunity_score, confidence_score, timing_score, risk_score,
                   liquidity_score, data_quality_score, position_weight,
                   portfolio_review_category, strong_buy_below, starter_buy_below,
                   add_below, hold_low, hold_high, trim_above, reduce_or_sell_above,
                   risk_review_below, nav_action_discount_below,
                    nav_watch_discount_below, nav_fair_value,
                    nav_premium_warning_above, etf_risk_review_level, range_state,
                    previous_range_state, reason_codes, data_warnings,
                    technical_signal_date, support_low, support_high,
                    resistance_low, resistance_high, breakout_level,
                    downside_watch_level, trend_repair_level,
                    moving_average_state, drawdown_state, price_location_state,
                    regime_signal_date, regime_state, relative_strength,
                    sector_rotation_rank, technical_confidence,
                    regime_confidence,
                    model_version, source, as_of_date, effective_date
            FROM range_snapshots
            WHERE ticker = ?
            ORDER BY snapshot_timestamp DESC, loaded_at DESC
            LIMIT 1
            """,
            (normalize_ticker(ticker),),
        ).fetchone()
    return RangeSnapshot(**dict(row)) if row else None


def latest_range_snapshot_timestamp(database_path: Path) -> str | None:
    with closing(sqlite3.connect(database_path)) as connection:
        row = connection.execute(
            "SELECT MAX(snapshot_timestamp) FROM range_snapshots"
        ).fetchone()
    return row[0] if row and row[0] is not None else None


def range_statuses(database_path: Path, ticker: str | None = None) -> list[RangeSnapshot]:
    parameters: tuple[str, ...] = ()
    ticker_filter = ""
    if ticker:
        ticker_filter = "WHERE a.ticker = ?"
        parameters = (normalize_ticker(ticker),)

    with closing(sqlite3.connect(database_path)) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            f"""
            SELECT
                COALESCE(r.ticker, a.ticker) AS ticker,
                COALESCE(r.snapshot_timestamp, '') AS snapshot_timestamp,
                COALESCE(r.asset_type, a.asset_type) AS asset_type,
                r.current_price, r.quote_timestamp, r.quote_source,
                COALESCE(r.quote_stale, 0) AS quote_stale,
                r.base_target, r.target_low, r.target_high,
                r.etf_nav_per_share, r.etf_nav_gap,
                r.opportunity_score, r.confidence_score, r.timing_score,
                r.risk_score, r.liquidity_score, r.data_quality_score,
                r.position_weight, r.portfolio_review_category,
                r.strong_buy_below, r.starter_buy_below, r.add_below,
                r.hold_low, r.hold_high, r.trim_above, r.reduce_or_sell_above,
                r.risk_review_below, r.nav_action_discount_below,
                r.nav_watch_discount_below, r.nav_fair_value,
                r.nav_premium_warning_above, r.etf_risk_review_level,
                COALESCE(r.range_state, 'not_evaluated') AS range_state,
                r.previous_range_state, r.reason_codes, r.data_warnings,
                r.technical_signal_date, r.support_low, r.support_high,
                r.resistance_low, r.resistance_high, r.breakout_level,
                r.downside_watch_level, r.trend_repair_level,
                r.moving_average_state, r.drawdown_state, r.price_location_state,
                r.regime_signal_date, r.regime_state, r.relative_strength,
                r.sector_rotation_rank, r.technical_confidence,
                r.regime_confidence,
                COALESCE(r.model_version, '') AS model_version,
                COALESCE(r.source, '') AS source,
                r.as_of_date, r.effective_date
            FROM assets a
            LEFT JOIN range_snapshots r
              ON r.range_snapshot_id = (
                SELECT latest.range_snapshot_id
                FROM range_snapshots latest
                WHERE latest.ticker = a.ticker
                ORDER BY latest.snapshot_timestamp DESC, latest.loaded_at DESC
                LIMIT 1
              )
            {ticker_filter}
            ORDER BY a.ticker
            """,
            parameters,
        ).fetchall()
    return [RangeSnapshot(**dict(row)) for row in rows]


def upsert_technical_signal_snapshot(
    database_path: Path,
    snapshot: TechnicalSignalSnapshot,
) -> None:
    payload = _dataclass_payload(snapshot)
    _upsert(
        database_path=database_path,
        table="technical_signal_snapshots",
        payload=payload,
        conflict_columns=("ticker", "signal_date", "model_version", "source"),
        update_columns=tuple(
            column
            for column in payload
            if column not in {"ticker", "signal_date", "model_version", "source"}
        ),
    )


def latest_technical_signal_snapshot(
    database_path: Path,
    ticker: str,
) -> TechnicalSignalSnapshot | None:
    with closing(sqlite3.connect(database_path)) as connection:
        connection.row_factory = sqlite3.Row
        row = connection.execute(
            """
            SELECT ticker, signal_date, current_price, support_low, support_high,
                   resistance_low, resistance_high, breakout_level,
                   downside_watch_level, trend_repair_level, short_ma, medium_ma,
                   long_ma, moving_average_state, drawdown_pct, drawdown_state,
                   price_location_state, trend_score, level_score, confidence,
                   data_warnings, model_version, source, as_of_date,
                   effective_date
            FROM technical_signal_snapshots
            WHERE ticker = ?
            ORDER BY signal_date DESC, loaded_at DESC
            LIMIT 1
            """,
            (normalize_ticker(ticker),),
        ).fetchone()
    return TechnicalSignalSnapshot(**dict(row)) if row else None


def latest_technical_signal_date(database_path: Path) -> str | None:
    with closing(sqlite3.connect(database_path)) as connection:
        row = connection.execute(
            "SELECT MAX(signal_date) FROM technical_signal_snapshots"
        ).fetchone()
    return row[0] if row and row[0] is not None else None


def technical_signal_statuses(
    database_path: Path,
    ticker: str | None = None,
) -> list[TechnicalSignalSnapshot]:
    parameters: tuple[str, ...] = ()
    ticker_filter = ""
    if ticker:
        ticker_filter = "WHERE a.ticker = ?"
        parameters = (normalize_ticker(ticker),)

    with closing(sqlite3.connect(database_path)) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            f"""
            SELECT
                COALESCE(t.ticker, a.ticker) AS ticker,
                COALESCE(t.signal_date, '') AS signal_date,
                t.current_price, t.support_low, t.support_high,
                t.resistance_low, t.resistance_high, t.breakout_level,
                t.downside_watch_level, t.trend_repair_level, t.short_ma,
                t.medium_ma, t.long_ma, t.moving_average_state,
                t.drawdown_pct, t.drawdown_state, t.price_location_state,
                t.trend_score, t.level_score, t.confidence, t.data_warnings,
                COALESCE(t.model_version, '') AS model_version,
                COALESCE(t.source, '') AS source,
                t.as_of_date, t.effective_date
            FROM assets a
            LEFT JOIN technical_signal_snapshots t
              ON t.technical_signal_snapshot_id = (
                SELECT latest.technical_signal_snapshot_id
                FROM technical_signal_snapshots latest
                WHERE latest.ticker = a.ticker
                ORDER BY latest.signal_date DESC, latest.loaded_at DESC
                LIMIT 1
              )
            {ticker_filter}
            ORDER BY a.ticker
            """,
            parameters,
        ).fetchall()
    return [TechnicalSignalSnapshot(**dict(row)) for row in rows]


def upsert_regime_signal_snapshot(
    database_path: Path,
    snapshot: RegimeSignalSnapshot,
) -> None:
    payload = _dataclass_payload(snapshot)
    _upsert(
        database_path=database_path,
        table="regime_signal_snapshots",
        payload=payload,
        conflict_columns=("ticker", "signal_date", "model_version", "source"),
        update_columns=tuple(
            column
            for column in payload
            if column not in {"ticker", "signal_date", "model_version", "source"}
        ),
    )


def latest_regime_signal_snapshot(
    database_path: Path,
    ticker: str,
) -> RegimeSignalSnapshot | None:
    with closing(sqlite3.connect(database_path)) as connection:
        connection.row_factory = sqlite3.Row
        row = connection.execute(
            """
            SELECT ticker, signal_date, proxy_type, current_price,
                   benchmark_ticker, benchmark_return, return_lookback,
                   relative_strength, trend_state, risk_state,
                   sector_rotation_rank, defensive_rotation_flag, confidence,
                   data_warnings, model_version, source, as_of_date,
                   effective_date
            FROM regime_signal_snapshots
            WHERE ticker = ?
            ORDER BY signal_date DESC, loaded_at DESC
            LIMIT 1
            """,
            (normalize_ticker(ticker),),
        ).fetchone()
    return RegimeSignalSnapshot(**dict(row)) if row else None


def latest_regime_signal_date(database_path: Path) -> str | None:
    with closing(sqlite3.connect(database_path)) as connection:
        row = connection.execute(
            "SELECT MAX(signal_date) FROM regime_signal_snapshots"
        ).fetchone()
    return row[0] if row and row[0] is not None else None


def regime_signal_statuses(
    database_path: Path,
    ticker: str | None = None,
) -> list[RegimeSignalSnapshot]:
    parameters: tuple[str, ...] = ()
    where_clause = ""
    if ticker:
        where_clause = "WHERE ticker = ?"
        parameters = (normalize_ticker(ticker),)
    with closing(sqlite3.connect(database_path)) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            f"""
            SELECT ticker, signal_date, proxy_type, current_price,
                   benchmark_ticker, benchmark_return, return_lookback,
                   relative_strength, trend_state, risk_state,
                   sector_rotation_rank, defensive_rotation_flag, confidence,
                   data_warnings, model_version, source, as_of_date,
                   effective_date
            FROM regime_signal_snapshots
            {where_clause}
            ORDER BY ticker, signal_date DESC, loaded_at DESC
            """,
            parameters,
        ).fetchall()

    latest_by_ticker: dict[str, RegimeSignalSnapshot] = {}
    for row in rows:
        snapshot = RegimeSignalSnapshot(**dict(row))
        if snapshot.ticker not in latest_by_ticker:
            latest_by_ticker[snapshot.ticker] = snapshot
    return [latest_by_ticker[ticker] for ticker in sorted(latest_by_ticker)]


def upsert_fundamental_benchmark_snapshot(
    database_path: Path,
    snapshot: FundamentalBenchmarkSnapshot,
) -> None:
    payload = _dataclass_payload(snapshot)
    _upsert(
        database_path=database_path,
        table="fundamental_benchmark_snapshots",
        payload=payload,
        conflict_columns=(
            "benchmark_date",
            "benchmark_type",
            "benchmark_key",
            "model_version",
            "source",
        ),
        update_columns=tuple(
            column
            for column in payload
            if column
            not in {
                "benchmark_date",
                "benchmark_type",
                "benchmark_key",
                "model_version",
                "source",
            }
        ),
    )


def upsert_fundamental_comparison_snapshot(
    database_path: Path,
    snapshot: FundamentalComparisonSnapshot,
) -> None:
    payload = _dataclass_payload(snapshot)
    _upsert(
        database_path=database_path,
        table="fundamental_comparison_snapshots",
        payload=payload,
        conflict_columns=("ticker", "comparison_date", "model_version", "source"),
        update_columns=tuple(
            column
            for column in payload
            if column not in {"ticker", "comparison_date", "model_version", "source"}
        ),
    )


def latest_fundamental_benchmark_date(database_path: Path) -> str | None:
    with closing(sqlite3.connect(database_path)) as connection:
        row = connection.execute(
            "SELECT MAX(comparison_date) FROM fundamental_comparison_snapshots"
        ).fetchone()
    return row[0] if row and row[0] is not None else None


def list_fundamental_benchmark_snapshots(
    database_path: Path,
    benchmark_type: str | None = None,
) -> list[FundamentalBenchmarkSnapshot]:
    parameters: tuple[str, ...] = ()
    where_clause = ""
    if benchmark_type:
        where_clause = "WHERE benchmark_type = ?"
        parameters = (benchmark_type,)
    with closing(sqlite3.connect(database_path)) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            f"""
            SELECT benchmark_date, benchmark_type, benchmark_key, ticker_count,
                   forward_pe_median, trailing_pe_median, ev_ebitda_median,
                   p_fcf_median, p_s_median, revenue_growth_median,
                   net_margin_median, fcf_margin_median, roe_median,
                   net_debt_ebitda_median, opportunity_score_median,
                   valuation_gap_median, data_warnings, model_version, source,
                   as_of_date, effective_date
            FROM fundamental_benchmark_snapshots
            {where_clause}
            ORDER BY benchmark_date DESC, benchmark_type, benchmark_key
            """,
            parameters,
        ).fetchall()
    return [FundamentalBenchmarkSnapshot(**dict(row)) for row in rows]


def fundamental_comparison_statuses(
    database_path: Path,
    ticker: str | None = None,
) -> list[FundamentalComparisonSnapshot]:
    parameters: tuple[str, ...] = ()
    ticker_filter = ""
    if ticker:
        ticker_filter = "WHERE a.ticker = ?"
        parameters = (normalize_ticker(ticker),)

    with closing(sqlite3.connect(database_path)) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            f"""
            SELECT
                COALESCE(c.ticker, a.ticker) AS ticker,
                COALESCE(c.comparison_date, '') AS comparison_date,
                COALESCE(c.sector, a.sector) AS sector,
                COALESCE(c.industry, a.industry) AS industry,
                c.sector_benchmark_ticker,
                COALESCE(c.overall_peer_count, 0) AS overall_peer_count,
                COALESCE(c.sector_peer_count, 0) AS sector_peer_count,
                COALESCE(c.industry_peer_count, 0) AS industry_peer_count,
                c.forward_pe, c.sector_forward_pe_median,
                c.overall_forward_pe_median, c.sector_forward_pe_discount_pct,
                c.sector_forward_pe_percentile, c.ev_ebitda,
                c.sector_ev_ebitda_median, c.p_fcf, c.sector_p_fcf_median,
                c.net_margin, c.sector_net_margin_median, c.revenue_growth,
                c.sector_revenue_growth_median, c.net_debt_ebitda,
                c.sector_net_debt_ebitda_median, c.valuation_gap,
                c.sector_valuation_gap_median, c.opportunity_score,
                c.sector_opportunity_score_median, c.relative_strength_vs_spy,
                c.relative_strength_vs_qqq, c.relative_strength_vs_sector,
                c.benchmark_status, c.data_warnings,
                COALESCE(c.model_version, '') AS model_version,
                COALESCE(c.source, '') AS source,
                c.as_of_date, c.effective_date
            FROM assets a
            LEFT JOIN fundamental_comparison_snapshots c
              ON c.fundamental_comparison_snapshot_id = (
                SELECT latest.fundamental_comparison_snapshot_id
                FROM fundamental_comparison_snapshots latest
                WHERE latest.ticker = a.ticker
                ORDER BY latest.comparison_date DESC, latest.loaded_at DESC
                LIMIT 1
              )
            {ticker_filter}
            ORDER BY a.ticker
            """,
            parameters,
        ).fetchall()
    return [FundamentalComparisonSnapshot(**dict(row)) for row in rows]


def upsert_research_recommendation_candidate(
    database_path: Path,
    candidate: ResearchRecommendationCandidate,
) -> int:
    payload = _dataclass_payload(candidate)
    payload["status"] = str(payload.get("status") or "pending").strip().lower()
    _upsert(
        database_path=database_path,
        table="research_recommendation_candidates",
        payload=payload,
        conflict_columns=("recommendation_key",),
        update_columns=tuple(
            column for column in payload if column != "recommendation_key"
        ),
    )
    with closing(sqlite3.connect(database_path)) as connection:
        row = connection.execute(
            """
            SELECT research_recommendation_id
            FROM research_recommendation_candidates
            WHERE recommendation_key = ?
            """,
            (candidate.recommendation_key,),
        ).fetchone()
    return int(row[0])


def list_research_recommendation_candidates(
    database_path: Path,
    status: str | None = None,
    ticker: str | None = None,
) -> list[StoredResearchRecommendationCandidate]:
    filters: list[str] = []
    parameters: list[object] = []
    if status:
        filters.append("status = ?")
        parameters.append(status.strip().lower())
    if ticker:
        filters.append("ticker = ?")
        parameters.append(normalize_ticker(ticker))
    where_clause = "WHERE " + " AND ".join(filters) if filters else ""
    with closing(sqlite3.connect(database_path)) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            f"""
            SELECT research_recommendation_id, recommendation_key, ticker,
                   recommendation_date, source, status, topic, rationale,
                   research_priority_score, confidence, source_count,
                   evidence_count, source_mix, metadata_status, warning_codes,
                   promotion_blockers, promoted_asset_role, source_url,
                   external_id, model_version, as_of_date, effective_date
            FROM research_recommendation_candidates
            {where_clause}
            ORDER BY
              CASE status
                WHEN 'approved' THEN 0
                WHEN 'pending' THEN 1
                ELSE 2
              END,
              research_priority_score DESC,
              recommendation_date DESC,
              ticker
            """,
            tuple(parameters),
        ).fetchall()
    return [StoredResearchRecommendationCandidate(**dict(row)) for row in rows]


def get_research_recommendation_candidate(
    database_path: Path,
    recommendation_id: int | None = None,
    recommendation_key: str | None = None,
) -> StoredResearchRecommendationCandidate | None:
    if recommendation_id is None and recommendation_key is None:
        return None
    if recommendation_id is not None:
        where_clause = "research_recommendation_id = ?"
        parameters: tuple[object, ...] = (recommendation_id,)
    else:
        where_clause = "recommendation_key = ?"
        parameters = (recommendation_key,)
    with closing(sqlite3.connect(database_path)) as connection:
        connection.row_factory = sqlite3.Row
        row = connection.execute(
            f"""
            SELECT research_recommendation_id, recommendation_key, ticker,
                   recommendation_date, source, status, topic, rationale,
                   research_priority_score, confidence, source_count,
                   evidence_count, source_mix, metadata_status, warning_codes,
                   promotion_blockers, promoted_asset_role, source_url,
                   external_id, model_version, as_of_date, effective_date
            FROM research_recommendation_candidates
            WHERE {where_clause}
            """,
            parameters,
        ).fetchone()
    return StoredResearchRecommendationCandidate(**dict(row)) if row else None


def upsert_research_recommendation_evidence(
    database_path: Path,
    evidence: ResearchRecommendationEvidence,
) -> None:
    payload = _dataclass_payload(evidence)
    _upsert(
        database_path=database_path,
        table="research_recommendation_evidence",
        payload=payload,
        conflict_columns=("evidence_key",),
        update_columns=tuple(column for column in payload if column != "evidence_key"),
    )


def list_research_recommendation_evidence(
    database_path: Path,
    recommendation_key: str | None = None,
    ticker: str | None = None,
) -> list[ResearchRecommendationEvidence]:
    filters: list[str] = []
    parameters: list[object] = []
    if recommendation_key:
        filters.append("recommendation_key = ?")
        parameters.append(recommendation_key)
    if ticker:
        filters.append("ticker = ?")
        parameters.append(normalize_ticker(ticker))
    where_clause = "WHERE " + " AND ".join(filters) if filters else ""
    with closing(sqlite3.connect(database_path)) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            f"""
            SELECT evidence_key, recommendation_key, ticker, evidence_date,
                   source, source_type, source_id, source_url,
                   headline_or_excerpt, reason, confidence, as_of_date,
                   effective_date
            FROM research_recommendation_evidence
            {where_clause}
            ORDER BY evidence_date DESC, source, evidence_key
            """,
            tuple(parameters),
        ).fetchall()
    return [ResearchRecommendationEvidence(**dict(row)) for row in rows]


def insert_research_recommendation_decision(
    database_path: Path,
    decision: ResearchRecommendationDecision,
) -> None:
    payload = _dataclass_payload(decision)
    columns = tuple(payload.keys())
    placeholders = ", ".join("?" for _ in columns)
    column_list = ", ".join(columns)
    with closing(connect(database_path)) as connection:
        connection.execute(
            f"""
            INSERT INTO research_recommendation_decisions ({column_list})
            VALUES ({placeholders})
            """,
            tuple(payload[column] for column in columns),
        )
        connection.commit()


def update_research_recommendation_status(
    database_path: Path,
    recommendation_id: int,
    new_status: str,
    *,
    reason: str | None = None,
    decision_timestamp: str | None = None,
) -> StoredResearchRecommendationCandidate | None:
    current = get_research_recommendation_candidate(
        database_path, recommendation_id=recommendation_id
    )
    if current is None:
        return None
    status_value = new_status.strip().lower()
    with closing(connect(database_path)) as connection:
        connection.execute(
            """
            UPDATE research_recommendation_candidates
            SET status = ?, loaded_at = CURRENT_TIMESTAMP
            WHERE research_recommendation_id = ?
            """,
            (status_value, recommendation_id),
        )
        connection.commit()
    insert_research_recommendation_decision(
        database_path,
        ResearchRecommendationDecision(
            recommendation_key=current.recommendation_key,
            ticker=current.ticker,
            decision_timestamp=decision_timestamp
            or datetime.now().replace(microsecond=0).isoformat(),
            previous_status=current.status,
            new_status=status_value,
            reason=reason,
        ),
    )
    return get_research_recommendation_candidate(
        database_path, recommendation_id=recommendation_id
    )


def latest_research_recommendation_date(database_path: Path) -> str | None:
    with closing(sqlite3.connect(database_path)) as connection:
        row = connection.execute(
            "SELECT MAX(recommendation_date) FROM research_recommendation_candidates"
        ).fetchone()
    return row[0] if row and row[0] is not None else None


def recent_notification_exists(
    database_path: Path,
    ticker: str,
    event_type: str,
    current_state: str,
    model_version: str,
    since_timestamp: str,
) -> bool:
    with closing(sqlite3.connect(database_path)) as connection:
        row = connection.execute(
            """
            SELECT 1
            FROM notification_events
            WHERE ticker = ?
              AND event_type = ?
              AND current_state = ?
              AND model_version = ?
              AND event_timestamp >= ?
              AND status != 'suppressed'
            LIMIT 1
            """,
            (
                normalize_ticker(ticker),
                event_type,
                current_state,
                model_version,
                since_timestamp,
            ),
        ).fetchone()
    return row is not None


def upsert_notification_event(
    database_path: Path,
    event: NotificationEvent,
) -> None:
    payload = _dataclass_payload(event)
    _upsert(
        database_path=database_path,
        table="notification_events",
        payload=payload,
        conflict_columns=("dedupe_key",),
        update_columns=tuple(column for column in payload if column != "dedupe_key"),
    )


def list_notification_events(
    database_path: Path,
    status: str | None = None,
    ticker: str | None = None,
) -> list[NotificationEventStatus]:
    conditions: list[str] = []
    parameters: list[str] = []
    if status:
        conditions.append("status = ?")
        parameters.append(status)
    if ticker:
        conditions.append("ticker = ?")
        parameters.append(normalize_ticker(ticker))
    where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    with closing(sqlite3.connect(database_path)) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            f"""
            SELECT notification_event_id, ticker, event_timestamp, event_type,
                   asset_type, severity, previous_state, current_state,
                   trigger_price, range_level, reason_codes, status,
                   cooldown_until, model_version
            FROM notification_events
            {where_clause}
            ORDER BY event_timestamp DESC, notification_event_id DESC
            """,
            tuple(parameters),
        ).fetchall()
    return [NotificationEventStatus(**dict(row)) for row in rows]


def pending_notification_count(database_path: Path) -> int:
    with closing(sqlite3.connect(database_path)) as connection:
        row = connection.execute(
            "SELECT COUNT(*) FROM notification_events WHERE status = 'pending'"
        ).fetchone()
    return int(row[0]) if row else 0


def latest_notification_timestamp(database_path: Path) -> str | None:
    with closing(sqlite3.connect(database_path)) as connection:
        row = connection.execute(
            "SELECT MAX(event_timestamp) FROM notification_events"
        ).fetchone()
    return row[0] if row and row[0] is not None else None


def upsert_notification_delivery(
    database_path: Path,
    delivery: NotificationDelivery,
) -> None:
    payload = _dataclass_payload(delivery)
    _upsert(
        database_path=database_path,
        table="notification_deliveries",
        payload=payload,
        conflict_columns=("notification_event_id", "channel"),
        update_columns=tuple(
            column
            for column in payload
            if column not in {"notification_event_id", "channel"}
        ),
    )


def list_notification_deliveries(
    database_path: Path,
    channel: str | None = None,
    status: str | None = None,
    limit: int | None = None,
) -> list[NotificationDeliveryStatus]:
    conditions: list[str] = []
    parameters: list[object] = []
    if channel:
        conditions.append("d.channel = ?")
        parameters.append(channel)
    if status:
        conditions.append("d.status = ?")
        parameters.append(status)
    where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    limit_clause = "LIMIT ?" if limit is not None else ""
    if limit is not None:
        parameters.append(int(limit))

    with closing(sqlite3.connect(database_path)) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            f"""
            SELECT d.notification_delivery_id, d.notification_event_id,
                   e.ticker, d.channel, d.delivery_timestamp, d.status,
                   d.details, d.as_of_date, d.effective_date
            FROM notification_deliveries d
            LEFT JOIN notification_events e
              ON e.notification_event_id = d.notification_event_id
            {where_clause}
            ORDER BY d.delivery_timestamp DESC, d.notification_delivery_id DESC
            {limit_clause}
            """,
            tuple(parameters),
        ).fetchall()
    return [NotificationDeliveryStatus(**dict(row)) for row in rows]


def notification_delivery_count(
    database_path: Path,
    status: str | None = None,
    channel: str | None = None,
) -> int:
    conditions: list[str] = []
    parameters: list[str] = []
    if status:
        conditions.append("status = ?")
        parameters.append(status)
    if channel:
        conditions.append("channel = ?")
        parameters.append(channel)
    where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    with closing(sqlite3.connect(database_path)) as connection:
        row = connection.execute(
            f"SELECT COUNT(*) FROM notification_deliveries {where_clause}",
            tuple(parameters),
        ).fetchone()
    return int(row[0]) if row else 0


def latest_notification_delivery_timestamp(
    database_path: Path,
    channel: str | None = None,
    status: str | None = None,
) -> str | None:
    conditions: list[str] = []
    parameters: list[str] = []
    if channel:
        conditions.append("channel = ?")
        parameters.append(channel)
    if status:
        conditions.append("status = ?")
        parameters.append(status)
    where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    with closing(sqlite3.connect(database_path)) as connection:
        row = connection.execute(
            f"SELECT MAX(delivery_timestamp) FROM notification_deliveries {where_clause}",
            tuple(parameters),
        ).fetchone()
    return row[0] if row and row[0] is not None else None


def mark_notification_event_delivered(
    database_path: Path,
    notification_event_id: int,
) -> None:
    mark_notification_event_status(database_path, notification_event_id, "delivered")


def mark_notification_event_status(
    database_path: Path,
    notification_event_id: int,
    status: str,
) -> None:
    with closing(connect(database_path)) as connection:
        connection.execute(
            "UPDATE notification_events SET status = ? WHERE notification_event_id = ?",
            (status, notification_event_id),
        )
        connection.commit()


def upsert_etf_nav(database_path: Path, nav: EtfNav) -> None:
    payload = _dataclass_payload(nav)
    _upsert(
        database_path=database_path,
        table="etf_navs",
        payload=payload,
        conflict_columns=("ticker", "nav_date", "source"),
        update_columns=tuple(
            column for column in payload if column not in {"ticker", "nav_date", "source"}
        ),
    )


def list_etf_navs(database_path: Path, ticker: str) -> list[EtfNav]:
    with closing(sqlite3.connect(database_path)) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            """
            SELECT ticker, nav_date, nav_per_share, market_price, premium_discount,
                   shares_outstanding, net_assets, source, as_of_date, effective_date
            FROM etf_navs
            WHERE ticker = ?
            ORDER BY nav_date
            """,
            (normalize_ticker(ticker),),
        ).fetchall()
    return [EtfNav(**dict(row)) for row in rows]


def latest_etf_nav(database_path: Path, ticker: str) -> EtfNav | None:
    navs = list_etf_navs(database_path, ticker)
    if not navs:
        return None
    return navs[-1]


def upsert_etf_holding(database_path: Path, holding: EtfHolding) -> None:
    payload = _dataclass_payload(holding)
    payload["holding_ticker"] = payload.get("holding_ticker") or ""
    payload["holding_name"] = payload.get("holding_name") or ""
    _upsert(
        database_path=database_path,
        table="etf_holdings",
        payload=payload,
        conflict_columns=(
            "ticker",
            "holdings_date",
            "holding_ticker",
            "holding_name",
            "source",
        ),
        update_columns=tuple(
            column
            for column in payload
            if column
            not in {
                "ticker",
                "holdings_date",
                "holding_ticker",
                "holding_name",
                "source",
            }
        ),
    )


def list_etf_holdings(
    database_path: Path,
    ticker: str,
    holdings_date: str | None = None,
) -> list[EtfHolding]:
    parameters: tuple[str, ...]
    where_clause = "WHERE ticker = ?"
    parameters = (normalize_ticker(ticker),)
    if holdings_date is not None:
        where_clause += " AND holdings_date = ?"
        parameters = (normalize_ticker(ticker), holdings_date)

    with closing(sqlite3.connect(database_path)) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            f"""
            SELECT ticker, holdings_date, holding_ticker, holding_name,
                   holding_asset_type, weight, shares, market_value, sector,
                   country, source, as_of_date, effective_date
            FROM etf_holdings
            {where_clause}
            ORDER BY holdings_date, weight DESC, holding_ticker, holding_name
            """,
            parameters,
        ).fetchall()
    return [EtfHolding(**dict(row)) for row in rows]


def latest_etf_holdings(database_path: Path, ticker: str) -> list[EtfHolding]:
    latest = latest_etf_holdings_date(database_path, ticker)
    if latest is None:
        return []
    return list_etf_holdings(database_path, ticker, latest)


def latest_etf_holdings_date(database_path: Path, ticker: str) -> str | None:
    with closing(sqlite3.connect(database_path)) as connection:
        row = connection.execute(
            """
            SELECT MAX(holdings_date)
            FROM etf_holdings
            WHERE ticker = ?
            """,
            (normalize_ticker(ticker),),
        ).fetchone()
    return row[0] if row and row[0] is not None else None


def upsert_etf_feature(database_path: Path, feature: EtfFeature) -> None:
    payload = _dataclass_payload(feature)
    _upsert(
        database_path=database_path,
        table="etf_features",
        payload=payload,
        conflict_columns=("ticker", "feature_date", "source"),
        update_columns=tuple(
            column
            for column in payload
            if column not in {"ticker", "feature_date", "source"}
        ),
    )


def latest_etf_feature(database_path: Path, ticker: str) -> EtfFeature | None:
    with closing(sqlite3.connect(database_path)) as connection:
        connection.row_factory = sqlite3.Row
        row = connection.execute(
            """
            SELECT ticker, feature_date, nav_per_share, market_price,
                   premium_discount, premium_discount_average_60d,
                   premium_discount_volatility_60d, premium_discount_zscore,
                   holdings_count, top_10_weight, largest_holding_weight,
                   equity_weight, cash_weight, latest_nav_date,
                   latest_holdings_date, source, as_of_date, effective_date
            FROM etf_features
            WHERE ticker = ?
            ORDER BY feature_date DESC
            LIMIT 1
            """,
            (normalize_ticker(ticker),),
        ).fetchone()
    return EtfFeature(**dict(row)) if row else None


def upsert_target(database_path: Path, target: Target) -> None:
    payload = _dataclass_payload(target)
    _upsert(
        database_path=database_path,
        table="targets",
        payload=payload,
        conflict_columns=("ticker", "target_date", "model_version", "source"),
        update_columns=tuple(
            column
            for column in payload
            if column not in {"ticker", "target_date", "model_version", "source"}
        ),
    )


def list_targets(database_path: Path, ticker: str | None = None) -> list[Target]:
    parameters: tuple[str, ...] = ()
    where_clause = ""
    if ticker:
        where_clause = "WHERE ticker = ?"
        parameters = (normalize_ticker(ticker),)

    with closing(sqlite3.connect(database_path)) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            f"""
            SELECT ticker, target_date, base_target, target_low, target_high,
                   valuation_gap, target_method, uncertainty_band,
                   valuation_score, valuation_confidence, method_count,
                   target_reason, data_warnings, model_version, source,
                   as_of_date, effective_date
            FROM targets
            {where_clause}
            ORDER BY ticker, target_date
            """,
            parameters,
        ).fetchall()
    return [Target(**dict(row)) for row in rows]


def upsert_signal(database_path: Path, signal: Signal) -> None:
    payload = _dataclass_payload(signal)
    _upsert(
        database_path=database_path,
        table="signals",
        payload=payload,
        conflict_columns=("ticker", "signal_date", "signal_name", "source"),
        update_columns=tuple(
            column
            for column in payload
            if column not in {"ticker", "signal_date", "signal_name", "source"}
        ),
    )


def list_signals(
    database_path: Path,
    ticker: str | None = None,
    signal_family: str | None = None,
) -> list[Signal]:
    filters: list[str] = []
    parameters: list[str] = []
    if ticker:
        filters.append("ticker = ?")
        parameters.append(normalize_ticker(ticker))
    if signal_family:
        filters.append("signal_family = ?")
        parameters.append(signal_family)
    where_clause = "WHERE " + " AND ".join(filters) if filters else ""

    with closing(sqlite3.connect(database_path)) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            f"""
            SELECT ticker, signal_date, signal_name, signal_family, value,
                   score, direction, reason_code, source, model_version,
                   confidence, data_warnings, source_url, notes, as_of_date,
                   effective_date
            FROM signals
            {where_clause}
            ORDER BY ticker, signal_date, loaded_at, signal_name
            """,
            tuple(parameters),
        ).fetchall()
    return [Signal(**dict(row)) for row in rows]


def latest_signal_date(database_path: Path) -> str | None:
    with closing(sqlite3.connect(database_path)) as connection:
        row = connection.execute("SELECT MAX(signal_date) FROM signals").fetchone()
    return row[0] if row and row[0] is not None else None


def upsert_analyst_revision_source_snapshot(
    database_path: Path,
    snapshot: AnalystRevisionSourceSnapshot,
) -> None:
    payload = _dataclass_payload(snapshot)
    _upsert(
        database_path=database_path,
        table="analyst_revision_source_snapshots",
        payload=payload,
        conflict_columns=("ticker", "signal_date", "source"),
        update_columns=tuple(
            column
            for column in payload
            if column not in {"ticker", "signal_date", "source"}
        ),
    )


def list_analyst_revision_source_snapshots(
    database_path: Path,
    ticker: str | None = None,
) -> list[AnalystRevisionSourceSnapshot]:
    parameters: tuple[str, ...] = ()
    where_clause = ""
    if ticker:
        where_clause = "WHERE ticker = ?"
        parameters = (normalize_ticker(ticker),)

    with closing(sqlite3.connect(database_path)) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            f"""
            SELECT ticker, signal_date, source, source_url, notes,
                   capture_method, provider_status, eps_current, eps_30d_ago,
                   eps_90d_ago, eps_high, eps_low, eps_average, analyst_count,
                   revenue_current, revenue_30d_ago, revenue_90d_ago,
                   target_price_current, target_price_90d_ago,
                   recommendation_current_strong_buy,
                   recommendation_current_buy, recommendation_current_hold,
                   recommendation_current_sell,
                   recommendation_current_strong_sell,
                   recommendation_90d_ago_strong_buy,
                   recommendation_90d_ago_buy, recommendation_90d_ago_hold,
                   recommendation_90d_ago_sell,
                   recommendation_90d_ago_strong_sell, eps_revision_1m,
                   eps_revision_3m, revenue_revision_1m, revenue_revision_3m,
                   target_price_revision_3m, recommendation_revision,
                   estimate_dispersion, source_confidence, data_warnings,
                   as_of_date, effective_date
            FROM analyst_revision_source_snapshots
            {where_clause}
            ORDER BY ticker, signal_date, source
            """,
            parameters,
        ).fetchall()
    return [AnalystRevisionSourceSnapshot(**dict(row)) for row in rows]


def upsert_analyst_revision_aggregate(
    database_path: Path,
    aggregate: AnalystRevisionAggregate,
) -> None:
    payload = _dataclass_payload(aggregate)
    _upsert(
        database_path=database_path,
        table="analyst_revision_aggregates",
        payload=payload,
        conflict_columns=("ticker", "signal_date", "source"),
        update_columns=tuple(
            column
            for column in payload
            if column not in {"ticker", "signal_date", "source"}
        ),
    )


def delete_analyst_revision_aggregate(
    database_path: Path,
    ticker: str,
    signal_date: str,
    source: str = "analyst_revision_aggregate",
) -> None:
    with closing(connect(database_path)) as connection:
        connection.execute(
            """
            DELETE FROM analyst_revision_aggregates
            WHERE ticker = ? AND signal_date = ? AND source = ?
            """,
            (normalize_ticker(ticker), signal_date, source),
        )
        connection.commit()


def list_analyst_revision_aggregates(
    database_path: Path,
    ticker: str | None = None,
) -> list[AnalystRevisionAggregate]:
    parameters: tuple[str, ...] = ()
    where_clause = ""
    if ticker:
        where_clause = "WHERE ticker = ?"
        parameters = (normalize_ticker(ticker),)

    with closing(sqlite3.connect(database_path)) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            f"""
            SELECT ticker, signal_date, eps_revision_1m, eps_revision_3m,
                   revenue_revision_1m, revenue_revision_3m,
                   target_price_revision_3m, recommendation_revision,
                   estimate_dispersion, analyst_count, source_count,
                   sources, source_policy, aggregate_confidence,
                   source_disagreement, data_warnings, model_version, source,
                   source_url, notes, as_of_date, effective_date
            FROM analyst_revision_aggregates
            {where_clause}
            ORDER BY ticker, signal_date, source
            """,
            parameters,
        ).fetchall()
    return [AnalystRevisionAggregate(**dict(row)) for row in rows]


def latest_analyst_revision_aggregate_date(database_path: Path) -> str | None:
    with closing(sqlite3.connect(database_path)) as connection:
        row = connection.execute(
            "SELECT MAX(signal_date) FROM analyst_revision_aggregates"
        ).fetchone()
    return row[0] if row and row[0] is not None else None


def upsert_news_catalyst_source_snapshot(
    database_path: Path,
    snapshot: NewsCatalystSourceSnapshot,
) -> None:
    payload = _dataclass_payload(snapshot)
    _upsert(
        database_path=database_path,
        table="news_catalyst_source_snapshots",
        payload=payload,
        conflict_columns=("ticker", "signal_date", "source", "source_url"),
        update_columns=tuple(
            column
            for column in payload
            if column not in {"ticker", "signal_date", "source", "source_url"}
        ),
    )


def list_news_catalyst_source_snapshots(
    database_path: Path,
    ticker: str | None = None,
) -> list[NewsCatalystSourceSnapshot]:
    parameters: tuple[str, ...] = ()
    where_clause = ""
    if ticker:
        where_clause = "WHERE ticker = ?"
        parameters = (normalize_ticker(ticker),)

    with closing(sqlite3.connect(database_path)) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            f"""
            SELECT ticker, signal_date, source, source_url, headline_or_event,
                   article_datetime, event_date, topic, summary, capture_method,
                   provider_status, sentiment_score, catalyst_score,
                   urgency_score, relevance_score, source_confidence,
                   data_warnings, as_of_date, effective_date
            FROM news_catalyst_source_snapshots
            {where_clause}
            ORDER BY ticker, signal_date, source, source_url
            """,
            parameters,
        ).fetchall()
    return [NewsCatalystSourceSnapshot(**dict(row)) for row in rows]


def upsert_news_catalyst_aggregate(
    database_path: Path,
    aggregate: NewsCatalystAggregate,
) -> None:
    payload = _dataclass_payload(aggregate)
    _upsert(
        database_path=database_path,
        table="news_catalyst_aggregates",
        payload=payload,
        conflict_columns=("ticker", "signal_date", "source"),
        update_columns=tuple(
            column
            for column in payload
            if column not in {"ticker", "signal_date", "source"}
        ),
    )


def delete_news_catalyst_aggregate(
    database_path: Path,
    ticker: str,
    signal_date: str,
    source: str = "news_catalyst_aggregate",
) -> None:
    with closing(connect(database_path)) as connection:
        connection.execute(
            """
            DELETE FROM news_catalyst_aggregates
            WHERE ticker = ? AND signal_date = ? AND source = ?
            """,
            (normalize_ticker(ticker), signal_date, source),
        )
        connection.commit()


def list_news_catalyst_aggregates(
    database_path: Path,
    ticker: str | None = None,
) -> list[NewsCatalystAggregate]:
    parameters: tuple[str, ...] = ()
    where_clause = ""
    if ticker:
        where_clause = "WHERE ticker = ?"
        parameters = (normalize_ticker(ticker),)

    with closing(sqlite3.connect(database_path)) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            f"""
            SELECT ticker, signal_date, sentiment_score, catalyst_score,
                   urgency_score, confidence, source_count, sources,
                   source_policy, aggregate_confidence, source_disagreement,
                   headline_or_event, topic, data_warnings, model_version,
                   source, source_url, notes, as_of_date, effective_date
            FROM news_catalyst_aggregates
            {where_clause}
            ORDER BY ticker, signal_date, source
            """,
            parameters,
        ).fetchall()
    return [NewsCatalystAggregate(**dict(row)) for row in rows]


def latest_news_catalyst_aggregate_date(database_path: Path) -> str | None:
    with closing(sqlite3.connect(database_path)) as connection:
        row = connection.execute(
            "SELECT MAX(signal_date) FROM news_catalyst_aggregates"
        ).fetchone()
    return row[0] if row and row[0] is not None else None


def upsert_insider_transaction_source_snapshot(
    database_path: Path,
    snapshot: InsiderTransactionSourceSnapshot,
) -> None:
    payload = _dataclass_payload(snapshot)
    columns = tuple(payload.keys())
    placeholders = ", ".join("?" for _ in columns)
    column_list = ", ".join(columns)
    with closing(connect(database_path)) as connection:
        connection.execute(
            """
            DELETE FROM insider_transaction_source_snapshots
            WHERE ticker = ?
              AND accession_number = ?
              AND COALESCE(owner_name, '') = COALESCE(?, '')
              AND COALESCE(transaction_date, '') = COALESCE(?, '')
              AND COALESCE(transaction_code, '') = COALESCE(?, '')
              AND COALESCE(acquired_disposed_code, '') = COALESCE(?, '')
              AND COALESCE(shares, -1.0) = COALESCE(?, -1.0)
              AND COALESCE(price, -1.0) = COALESCE(?, -1.0)
              AND source = ?
            """,
            (
                payload["ticker"],
                payload["accession_number"],
                payload.get("owner_name"),
                payload.get("transaction_date"),
                payload.get("transaction_code"),
                payload.get("acquired_disposed_code"),
                payload.get("shares"),
                payload.get("price"),
                payload["source"],
            ),
        )
        connection.execute(
            f"""
            INSERT INTO insider_transaction_source_snapshots ({column_list})
            VALUES ({placeholders})
            """,
            tuple(payload[column] for column in columns),
        )
        connection.commit()


def list_insider_transaction_source_snapshots(
    database_path: Path,
    ticker: str | None = None,
) -> list[InsiderTransactionSourceSnapshot]:
    parameters: tuple[str, ...] = ()
    where_clause = ""
    if ticker:
        where_clause = "WHERE ticker = ?"
        parameters = (normalize_ticker(ticker),)

    with closing(sqlite3.connect(database_path)) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            f"""
            SELECT ticker, cik, accession_number, filing_date, transaction_date,
                   owner_name, owner_title, transaction_code,
                   acquired_disposed_code, shares, price, transaction_value,
                   source_url, provider_status, data_warnings, source,
                   as_of_date, effective_date
            FROM insider_transaction_source_snapshots
            {where_clause}
            ORDER BY ticker, COALESCE(transaction_date, filing_date), accession_number
            """,
            parameters,
        ).fetchall()
    return [InsiderTransactionSourceSnapshot(**dict(row)) for row in rows]


def latest_insider_transaction_source_date(database_path: Path) -> str | None:
    with closing(sqlite3.connect(database_path)) as connection:
        row = connection.execute(
            """
            SELECT MAX(COALESCE(transaction_date, filing_date))
            FROM insider_transaction_source_snapshots
            """
        ).fetchone()
    return row[0] if row and row[0] is not None else None


def upsert_short_interest_source_snapshot(
    database_path: Path,
    snapshot: ShortInterestSourceSnapshot,
) -> None:
    payload = _dataclass_payload(snapshot)
    _upsert(
        database_path=database_path,
        table="short_interest_source_snapshots",
        payload=payload,
        conflict_columns=("ticker", "settlement_date", "source"),
        update_columns=tuple(
            column
            for column in payload
            if column not in {"ticker", "settlement_date", "source"}
        ),
    )


def list_short_interest_source_snapshots(
    database_path: Path,
    ticker: str | None = None,
) -> list[ShortInterestSourceSnapshot]:
    parameters: tuple[str, ...] = ()
    where_clause = ""
    if ticker:
        where_clause = "WHERE ticker = ?"
        parameters = (normalize_ticker(ticker),)

    with closing(sqlite3.connect(database_path)) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            f"""
            SELECT ticker, settlement_date, source, source_url, publication_date,
                   short_interest, float_shares, percent_float,
                   average_daily_volume, days_to_cover, notes, data_warnings,
                   as_of_date, effective_date
            FROM short_interest_source_snapshots
            {where_clause}
            ORDER BY ticker, settlement_date, source
            """,
            parameters,
        ).fetchall()
    return [ShortInterestSourceSnapshot(**dict(row)) for row in rows]


def latest_short_interest_settlement_date(database_path: Path) -> str | None:
    with closing(sqlite3.connect(database_path)) as connection:
        row = connection.execute(
            "SELECT MAX(settlement_date) FROM short_interest_source_snapshots"
        ).fetchone()
    return row[0] if row and row[0] is not None else None


def upsert_option_chain_snapshot(
    database_path: Path,
    snapshot: OptionChainSnapshot,
) -> None:
    payload = _dataclass_payload(snapshot)
    payload["option_type"] = str(payload["option_type"]).lower()
    _upsert(
        database_path=database_path,
        table="option_chain_snapshots",
        payload=payload,
        conflict_columns=(
            "ticker",
            "snapshot_timestamp",
            "expiration_date",
            "option_type",
            "strike",
            "source",
        ),
        update_columns=tuple(
            column
            for column in payload
            if column
            not in {
                "ticker",
                "snapshot_timestamp",
                "expiration_date",
                "option_type",
                "strike",
                "source",
            }
        ),
    )


def list_option_chain_snapshots(
    database_path: Path,
    ticker: str | None = None,
) -> list[OptionChainSnapshot]:
    parameters: tuple[str, ...] = ()
    where_clause = ""
    if ticker:
        where_clause = "WHERE ticker = ?"
        parameters = (normalize_ticker(ticker),)

    with closing(sqlite3.connect(database_path)) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            f"""
            SELECT ticker, snapshot_timestamp, expiration_date, option_type,
                   strike, bid, ask, last, mark, volume, open_interest,
                   implied_volatility, delta, gamma, theta, vega, source,
                   source_url, as_of_date, effective_date
            FROM option_chain_snapshots
            {where_clause}
            ORDER BY ticker, snapshot_timestamp, expiration_date, option_type, strike
            """,
            parameters,
        ).fetchall()
    return [OptionChainSnapshot(**dict(row)) for row in rows]


def latest_option_chain_snapshot_timestamp(database_path: Path) -> str | None:
    with closing(sqlite3.connect(database_path)) as connection:
        row = connection.execute(
            "SELECT MAX(snapshot_timestamp) FROM option_chain_snapshots"
        ).fetchone()
    return row[0] if row and row[0] is not None else None


def upsert_option_income_review(
    database_path: Path,
    review: OptionIncomeReview,
) -> None:
    payload = _dataclass_payload(review)
    payload["option_type"] = str(payload["option_type"]).lower()
    _upsert(
        database_path=database_path,
        table="option_income_reviews",
        payload=payload,
        conflict_columns=(
            "ticker",
            "review_date",
            "snapshot_timestamp",
            "expiration_date",
            "option_type",
            "strike",
            "model_version",
            "source",
        ),
        update_columns=tuple(
            column
            for column in payload
            if column
            not in {
                "ticker",
                "review_date",
                "snapshot_timestamp",
                "expiration_date",
                "option_type",
                "strike",
                "model_version",
                "source",
            }
        ),
    )


def list_option_income_reviews(
    database_path: Path,
    ticker: str | None = None,
) -> list[OptionIncomeReview]:
    parameters: tuple[str, ...] = ()
    where_clause = ""
    if ticker:
        where_clause = "WHERE ticker = ?"
        parameters = (normalize_ticker(ticker),)

    with closing(sqlite3.connect(database_path)) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            f"""
            SELECT ticker, review_date, snapshot_timestamp, expiration_date,
                   option_type, strike, bid, ask, mid_premium, breakeven,
                   premium_yield, annualized_yield, downside_buffer_pct,
                   breakeven_buffer_pct, assignment_notional, open_interest,
                   volume, implied_volatility, delta, current_price, range_state,
                   range_level, review_category, risk_warnings,
                   commentary_claim_count, model_version, source, as_of_date,
                   effective_date
            FROM option_income_reviews
            {where_clause}
            ORDER BY ticker, review_date, annualized_yield DESC, strike
            """,
            parameters,
        ).fetchall()
    return [OptionIncomeReview(**dict(row)) for row in rows]


def list_stored_option_income_reviews(
    database_path: Path,
    ticker: str | None = None,
) -> list[StoredOptionIncomeReview]:
    parameters: tuple[str, ...] = ()
    where_clause = ""
    if ticker:
        where_clause = "WHERE ticker = ?"
        parameters = (normalize_ticker(ticker),)

    with closing(sqlite3.connect(database_path)) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            f"""
            SELECT option_income_review_id, ticker, review_date, snapshot_timestamp,
                   expiration_date, option_type, strike, bid, ask, mid_premium,
                   breakeven, premium_yield, annualized_yield,
                   downside_buffer_pct, breakeven_buffer_pct,
                   assignment_notional, open_interest, volume, implied_volatility,
                   delta, current_price, range_state, range_level,
                   review_category, risk_warnings, commentary_claim_count,
                   model_version, source, as_of_date, effective_date
            FROM option_income_reviews
            {where_clause}
            ORDER BY ticker, review_date, annualized_yield DESC, strike
            """,
            parameters,
        ).fetchall()
    return [StoredOptionIncomeReview(**dict(row)) for row in rows]


def latest_option_income_review_date(database_path: Path) -> str | None:
    with closing(sqlite3.connect(database_path)) as connection:
        row = connection.execute(
            "SELECT MAX(review_date) FROM option_income_reviews"
        ).fetchone()
    return row[0] if row and row[0] is not None else None


def upsert_option_risk_review(
    database_path: Path,
    review: OptionRiskReview,
) -> None:
    payload = _dataclass_payload(review)
    payload["option_type"] = str(payload["option_type"]).lower()
    _upsert(
        database_path=database_path,
        table="option_risk_reviews",
        payload=payload,
        conflict_columns=("option_income_review_id", "model_version"),
        update_columns=tuple(
            column
            for column in payload
            if column not in {"option_income_review_id", "model_version"}
        ),
    )


def list_option_risk_reviews(
    database_path: Path,
    ticker: str | None = None,
) -> list[OptionRiskReview]:
    parameters: tuple[str, ...] = ()
    where_clause = ""
    if ticker:
        where_clause = "WHERE ticker = ?"
        parameters = (normalize_ticker(ticker),)

    with closing(sqlite3.connect(database_path)) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            f"""
            SELECT option_income_review_id, ticker, review_date, risk_review_date,
                   expiration_date, option_type, strike, mid_premium, breakeven,
                   current_price, assignment_notional, premium_income,
                   cash_secured_requirement, max_cash_secured_loss,
                   scenario_pl_5pct, scenario_pl_10pct, scenario_pl_20pct,
                   projected_assignment_weight, cash_after_assignment,
                   cash_reserve_after_assignment, max_contracts_advisory,
                   total_portfolio_value, cash_available, position_weight,
                   risk_category, risk_warnings, model_version, source,
                   as_of_date, effective_date
            FROM option_risk_reviews
            {where_clause}
            ORDER BY ticker, risk_review_date, risk_category, strike
            """,
            parameters,
        ).fetchall()
    return [OptionRiskReview(**dict(row)) for row in rows]


def latest_option_risk_review_date(database_path: Path) -> str | None:
    with closing(sqlite3.connect(database_path)) as connection:
        row = connection.execute(
            "SELECT MAX(risk_review_date) FROM option_risk_reviews"
        ).fetchone()
    return row[0] if row and row[0] is not None else None


def upsert_option_review_outcome(
    database_path: Path,
    outcome: OptionReviewOutcome,
) -> None:
    payload = _dataclass_payload(outcome)
    payload["option_type"] = str(payload["option_type"]).lower()
    _upsert(
        database_path=database_path,
        table="option_review_outcomes",
        payload=payload,
        conflict_columns=("option_income_review_id", "model_version"),
        update_columns=tuple(
            column
            for column in payload
            if column not in {"option_income_review_id", "model_version"}
        ),
    )


def list_option_review_outcomes(
    database_path: Path,
    ticker: str | None = None,
) -> list[OptionReviewOutcome]:
    parameters: tuple[str, ...] = ()
    where_clause = ""
    if ticker:
        where_clause = "WHERE ticker = ?"
        parameters = (normalize_ticker(ticker),)

    with closing(sqlite3.connect(database_path)) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            f"""
            SELECT option_income_review_id, option_risk_review_id, ticker,
                   review_date, outcome_date, expiration_date, option_type,
                   strike, mid_premium, breakeven, review_price,
                   latest_underlying_price, latest_underlying_price_date,
                   expiration_close, expiration_price_date, expiration_status,
                   outcome_status, completed_horizons, pending_horizons,
                   return_5d, return_20d, return_to_latest, above_strike_flag,
                   above_breakeven_flag, touched_strike_flag,
                   touched_breakeven_flag, max_favorable_excursion,
                   max_adverse_excursion, linked_position_count, data_warnings,
                   model_version, source, as_of_date, effective_date
            FROM option_review_outcomes
            {where_clause}
            ORDER BY outcome_date DESC, ticker, expiration_date, strike
            """,
            parameters,
        ).fetchall()
    return [OptionReviewOutcome(**dict(row)) for row in rows]


def latest_option_review_outcome_id_for_income_review(
    database_path: Path,
    option_income_review_id: int,
) -> int | None:
    with closing(sqlite3.connect(database_path)) as connection:
        row = connection.execute(
            """
            SELECT option_review_outcome_id
            FROM option_review_outcomes
            WHERE option_income_review_id = ?
            ORDER BY outcome_date DESC, loaded_at DESC
            LIMIT 1
            """,
            (option_income_review_id,),
        ).fetchone()
    return int(row[0]) if row and row[0] is not None else None


def latest_option_review_outcome_date(database_path: Path) -> str | None:
    with closing(sqlite3.connect(database_path)) as connection:
        row = connection.execute(
            "SELECT MAX(outcome_date) FROM option_review_outcomes"
        ).fetchone()
    return row[0] if row and row[0] is not None else None


def upsert_option_position(
    database_path: Path,
    position: OptionPositionLedger,
) -> None:
    payload = _dataclass_payload(position)
    payload["option_type"] = str(payload["option_type"]).lower()
    payload["side"] = str(payload["side"]).lower()
    _upsert(
        database_path=database_path,
        table="option_position_ledger",
        payload=payload,
        conflict_columns=("position_key",),
        update_columns=tuple(column for column in payload if column != "position_key"),
    )


def list_option_positions(
    database_path: Path,
    ticker: str | None = None,
) -> list[OptionPositionLedger]:
    parameters: tuple[str, ...] = ()
    where_clause = ""
    if ticker:
        where_clause = "WHERE ticker = ?"
        parameters = (normalize_ticker(ticker),)

    with closing(sqlite3.connect(database_path)) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            f"""
            SELECT position_key, position_id, ticker, open_date, expiration_date,
                   option_type, side, strike, contracts, premium, close_date,
                   close_price, assigned_flag, assignment_price, fees, account,
                   position_status, roll_from_position_id, roll_to_position_id,
                   underlying_assignment_date, underlying_shares,
                   underlying_cost_basis, tags, data_warnings, model_version, source,
                   source_url, notes, as_of_date, effective_date
            FROM option_position_ledger
            {where_clause}
            ORDER BY ticker, open_date, expiration_date, strike
            """,
            parameters,
        ).fetchall()
    return [OptionPositionLedger(**dict(row)) for row in rows]


def upsert_option_position_lifecycle_review(
    database_path: Path,
    review: OptionPositionLifecycleReview,
) -> None:
    payload = _dataclass_payload(review)
    payload["option_type"] = str(payload["option_type"]).lower()
    payload["side"] = str(payload["side"]).lower()
    _upsert(
        database_path=database_path,
        table="option_position_lifecycle_reviews",
        payload=payload,
        conflict_columns=("position_key", "model_version"),
        update_columns=tuple(
            column for column in payload if column not in {"position_key", "model_version"}
        ),
    )


def list_option_position_lifecycle_reviews(
    database_path: Path,
    ticker: str | None = None,
) -> list[OptionPositionLifecycleReview]:
    parameters: tuple[str, ...] = ()
    where_clause = ""
    if ticker:
        where_clause = "WHERE ticker = ?"
        parameters = (normalize_ticker(ticker),)

    with closing(sqlite3.connect(database_path)) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            f"""
            SELECT position_key, position_id, ticker, lifecycle_review_date,
                   open_date, expiration_date, option_type, side, strike,
                   contracts, premium, close_date, close_price, assigned_flag,
                   assignment_price, fees, lifecycle_status, realized_pl,
                   open_pl_proxy, assignment_notional, cash_secured_requirement,
                   premium_income, latest_option_mark, latest_option_mark_timestamp,
                   underlying_assignment_date, underlying_shares,
                   underlying_cost_basis, linked_option_income_review_id,
                   linked_option_risk_review_id, linked_option_review_outcome_id,
                   roll_from_position_id, roll_to_position_id, risk_warnings,
                   model_version, source, as_of_date, effective_date
            FROM option_position_lifecycle_reviews
            {where_clause}
            ORDER BY ticker, open_date, expiration_date, strike
            """,
            parameters,
        ).fetchall()
    return [OptionPositionLifecycleReview(**dict(row)) for row in rows]


def latest_option_position_lifecycle_review_date(database_path: Path) -> str | None:
    with closing(sqlite3.connect(database_path)) as connection:
        row = connection.execute(
            "SELECT MAX(lifecycle_review_date) FROM option_position_lifecycle_reviews"
        ).fetchone()
    return row[0] if row and row[0] is not None else None


def latest_option_risk_review_id_for_income_review(
    database_path: Path,
    option_income_review_id: int,
) -> int | None:
    with closing(sqlite3.connect(database_path)) as connection:
        row = connection.execute(
            """
            SELECT option_risk_review_id
            FROM option_risk_reviews
            WHERE option_income_review_id = ?
            ORDER BY risk_review_date DESC, loaded_at DESC
            LIMIT 1
            """,
            (option_income_review_id,),
        ).fetchone()
    return int(row[0]) if row and row[0] is not None else None


def latest_option_position_open_date(database_path: Path) -> str | None:
    with closing(sqlite3.connect(database_path)) as connection:
        row = connection.execute(
            "SELECT MAX(open_date) FROM option_position_ledger"
        ).fetchone()
    return row[0] if row and row[0] is not None else None


def option_outcome_statuses(
    database_path: Path,
    ticker: str | None = None,
) -> list[OptionOutcomeStatus]:
    parameters: tuple[str, ...] = ()
    ticker_filter = ""
    if ticker:
        ticker_filter = "AND a.ticker = ?"
        parameters = (normalize_ticker(ticker),)

    with closing(sqlite3.connect(database_path)) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            f"""
            SELECT
                a.ticker,
                a.asset_type,
                a.asset_role,
                o.outcome_date,
                o.expiration_date,
                o.strike,
                o.outcome_status,
                o.expiration_status,
                o.latest_underlying_price,
                o.latest_underlying_price_date,
                o.return_5d,
                o.return_20d,
                o.return_to_latest,
                o.above_strike_flag,
                o.above_breakeven_flag,
                o.touched_strike_flag,
                o.touched_breakeven_flag,
                o.max_favorable_excursion,
                o.max_adverse_excursion,
                o.linked_position_count,
                o.data_warnings,
                o.model_version,
                (
                    SELECT COUNT(*)
                    FROM option_review_outcomes counted
                    WHERE counted.ticker = a.ticker
                ) AS outcome_count
            FROM assets a
            LEFT JOIN option_review_outcomes o
              ON o.option_review_outcome_id = (
                SELECT option_review_outcome_id
                FROM option_review_outcomes latest
                WHERE latest.ticker = a.ticker
                ORDER BY
                    latest.outcome_date DESC,
                    CASE latest.outcome_status
                        WHEN 'completed' THEN 0
                        WHEN 'partial' THEN 1
                        WHEN 'pending' THEN 2
                        ELSE 3
                    END,
                    latest.loaded_at DESC
                LIMIT 1
              )
            WHERE a.active_flag = 1
            {ticker_filter}
            ORDER BY a.ticker
            """,
            parameters,
        ).fetchall()
    return [OptionOutcomeStatus(**dict(row)) for row in rows]


def option_position_statuses(
    database_path: Path,
    ticker: str | None = None,
) -> list[OptionPositionStatus]:
    parameters: list[str] = []
    ticker_filter = ""
    if ticker:
        ticker_filter = "AND a.ticker = ?"
        parameters.append(normalize_ticker(ticker))

    with closing(sqlite3.connect(database_path)) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            f"""
            SELECT
                a.ticker,
                a.asset_type,
                a.asset_role,
                COUNT(p.position_key) AS position_count,
                SUM(CASE WHEN p.position_status = 'open' THEN 1 ELSE 0 END)
                    AS open_position_count,
                SUM(CASE WHEN p.position_status = 'assigned' THEN 1 ELSE 0 END)
                    AS assigned_position_count,
                MAX(p.open_date) AS latest_open_date,
                MAX(p.expiration_date) AS latest_expiration_date,
                SUM(p.contracts) AS total_contracts,
                GROUP_CONCAT(DISTINCT p.data_warnings) AS data_warnings
            FROM assets a
            LEFT JOIN option_position_ledger p
              ON p.ticker = a.ticker
            WHERE a.active_flag = 1
            {ticker_filter}
            GROUP BY a.ticker, a.asset_type, a.asset_role
            HAVING position_count > 0 OR ? = ''
            ORDER BY a.ticker
            """,
            tuple(parameters + ["" if ticker is None else normalize_ticker(ticker)]),
        ).fetchall()
    return [OptionPositionStatus(**dict(row)) for row in rows]


def option_lifecycle_statuses(
    database_path: Path,
    ticker: str | None = None,
) -> list[OptionLifecycleStatus]:
    parameters: list[str] = []
    ticker_filter = ""
    if ticker:
        ticker_filter = "AND a.ticker = ?"
        parameters.append(normalize_ticker(ticker))

    with closing(sqlite3.connect(database_path)) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            f"""
            SELECT
                a.ticker,
                a.asset_type,
                a.asset_role,
                MAX(r.lifecycle_review_date) AS lifecycle_review_date,
                (
                    SELECT latest.lifecycle_status
                    FROM option_position_lifecycle_reviews latest
                    WHERE latest.ticker = a.ticker
                    ORDER BY latest.lifecycle_review_date DESC, latest.loaded_at DESC
                    LIMIT 1
                ) AS lifecycle_status,
                (
                    SELECT COUNT(*)
                    FROM option_position_ledger p
                    WHERE p.ticker = a.ticker
                ) AS position_count,
                COUNT(r.position_key) AS lifecycle_review_count,
                SUM(CASE WHEN r.lifecycle_status = 'open' THEN 1 ELSE 0 END)
                    AS open_lifecycle_count,
                SUM(CASE WHEN r.lifecycle_status = 'closed' THEN 1 ELSE 0 END)
                    AS closed_lifecycle_count,
                SUM(CASE WHEN r.lifecycle_status = 'expired_worthless' THEN 1 ELSE 0 END)
                    AS expired_lifecycle_count,
                SUM(CASE WHEN r.lifecycle_status = 'assigned' THEN 1 ELSE 0 END)
                    AS assigned_lifecycle_count,
                SUM(CASE WHEN r.lifecycle_status = 'rolled' THEN 1 ELSE 0 END)
                    AS rolled_lifecycle_count,
                SUM(r.realized_pl) AS realized_pl_total,
                SUM(r.open_pl_proxy) AS open_pl_proxy_total,
                SUM(r.assignment_notional) AS assignment_notional_total,
                SUM(CASE
                    WHEN r.position_key IS NOT NULL
                     AND r.linked_option_income_review_id IS NULL THEN 1
                    ELSE 0
                END) AS unmatched_position_count,
                GROUP_CONCAT(DISTINCT r.risk_warnings) AS risk_warnings,
                (
                    SELECT latest.model_version
                    FROM option_position_lifecycle_reviews latest
                    WHERE latest.ticker = a.ticker
                    ORDER BY latest.lifecycle_review_date DESC, latest.loaded_at DESC
                    LIMIT 1
                ) AS model_version
            FROM assets a
            LEFT JOIN option_position_lifecycle_reviews r
              ON r.ticker = a.ticker
            WHERE a.active_flag = 1
            {ticker_filter}
            GROUP BY a.ticker, a.asset_type, a.asset_role
            HAVING position_count > 0 OR lifecycle_review_count > 0 OR ? = ''
            ORDER BY a.ticker
            """,
            tuple(parameters + ["" if ticker is None else normalize_ticker(ticker)]),
        ).fetchall()
    return [OptionLifecycleStatus(**dict(row)) for row in rows]


def option_income_statuses(
    database_path: Path,
    ticker: str | None = None,
) -> list[OptionIncomeStatus]:
    parameters: tuple[str, ...] = ()
    ticker_filter = ""
    if ticker:
        ticker_filter = "AND a.ticker = ?"
        parameters = (normalize_ticker(ticker),)

    with closing(sqlite3.connect(database_path)) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            f"""
            SELECT
                a.ticker,
                a.asset_type,
                a.asset_role,
                r.review_date,
                r.snapshot_timestamp,
                r.expiration_date,
                r.strike,
                r.mid_premium,
                r.breakeven,
                r.annualized_yield,
                r.downside_buffer_pct,
                r.assignment_notional,
                r.review_category,
                r.risk_warnings,
                r.commentary_claim_count,
                (
                    SELECT COUNT(*)
                    FROM option_chain_snapshots c
                    WHERE c.ticker = a.ticker
                ) AS option_chain_rows,
                (
                    SELECT MAX(snapshot_timestamp)
                    FROM option_chain_snapshots c
                    WHERE c.ticker = a.ticker
                ) AS latest_snapshot_timestamp,
                r.model_version
            FROM assets a
            LEFT JOIN option_income_reviews r
              ON r.option_income_review_id = (
                SELECT option_income_review_id
                FROM option_income_reviews latest
                WHERE latest.ticker = a.ticker
                ORDER BY
                    latest.review_date DESC,
                    CASE latest.review_category
                        WHEN 'eligible_watch' THEN 0
                        WHEN 'reference_only' THEN 1
                        WHEN 'missing_range_context' THEN 2
                        ELSE 3
                    END,
                    COALESCE(latest.annualized_yield, -1) DESC,
                    latest.loaded_at DESC
                LIMIT 1
              )
            WHERE a.active_flag = 1
            {ticker_filter}
            ORDER BY a.ticker
            """,
            parameters,
        ).fetchall()
    return [OptionIncomeStatus(**dict(row)) for row in rows]


def option_risk_statuses(
    database_path: Path,
    ticker: str | None = None,
) -> list[OptionRiskStatus]:
    parameters: tuple[str, ...] = ()
    ticker_filter = ""
    if ticker:
        ticker_filter = "AND a.ticker = ?"
        parameters = (normalize_ticker(ticker),)

    with closing(sqlite3.connect(database_path)) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            f"""
            SELECT
                a.ticker,
                a.asset_type,
                a.asset_role,
                r.risk_review_date,
                r.expiration_date,
                r.strike,
                r.assignment_notional,
                r.premium_income,
                r.cash_secured_requirement,
                r.max_cash_secured_loss,
                r.scenario_pl_5pct,
                r.scenario_pl_10pct,
                r.scenario_pl_20pct,
                r.projected_assignment_weight,
                r.cash_after_assignment,
                r.cash_reserve_after_assignment,
                r.max_contracts_advisory,
                r.total_portfolio_value,
                r.cash_available,
                r.risk_category,
                r.risk_warnings,
                r.model_version,
                (
                    SELECT COUNT(*)
                    FROM option_risk_reviews counted
                    WHERE counted.ticker = a.ticker
                ) AS risk_review_count
            FROM assets a
            LEFT JOIN option_risk_reviews r
              ON r.option_risk_review_id = (
                SELECT option_risk_review_id
                FROM option_risk_reviews latest
                WHERE latest.ticker = a.ticker
                ORDER BY
                    latest.risk_review_date DESC,
                    CASE latest.risk_category
                        WHEN 'risk_review_ready' THEN 0
                        WHEN 'reference_only_review' THEN 1
                        WHEN 'portfolio_context_needed' THEN 2
                        ELSE 3
                    END,
                    latest.loaded_at DESC
                LIMIT 1
              )
            WHERE a.active_flag = 1
            {ticker_filter}
            ORDER BY a.ticker
            """,
            parameters,
        ).fetchall()
    return [OptionRiskStatus(**dict(row)) for row in rows]


def upsert_trader_commentary_raw(
    database_path: Path,
    commentary: TraderCommentaryRaw,
) -> int:
    payload = _dataclass_payload(commentary)
    _upsert(
        database_path=database_path,
        table="trader_commentary_raw",
        payload=payload,
        conflict_columns=("identity_key",),
        update_columns=tuple(column for column in payload if column != "identity_key"),
    )
    with closing(sqlite3.connect(database_path)) as connection:
        row = connection.execute(
            "SELECT commentary_id FROM trader_commentary_raw WHERE identity_key = ?",
            (commentary.identity_key,),
        ).fetchone()
    return int(row[0])


def list_trader_commentary_raw(
    database_path: Path,
    commentary_id: int | None = None,
) -> list[StoredTraderCommentaryRaw]:
    parameters: tuple[object, ...] = ()
    where_clause = ""
    if commentary_id is not None:
        where_clause = "WHERE commentary_id = ?"
        parameters = (commentary_id,)
    with closing(sqlite3.connect(database_path)) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            f"""
            SELECT commentary_id, identity_key, capture_date, source,
                   source_author, platform, permission_scope, language,
                   raw_text, source_url, capture_id, text_file, notes,
                   data_warnings, as_of_date, effective_date
            FROM trader_commentary_raw
            {where_clause}
            ORDER BY capture_date, commentary_id
            """,
            parameters,
        ).fetchall()
    return [StoredTraderCommentaryRaw(**dict(row)) for row in rows]


def latest_trader_commentary_capture_date(database_path: Path) -> str | None:
    with closing(sqlite3.connect(database_path)) as connection:
        row = connection.execute(
            "SELECT MAX(capture_date) FROM trader_commentary_raw"
        ).fetchone()
    return row[0] if row and row[0] is not None else None


def upsert_trader_commentary_browser_capture_run(
    database_path: Path,
    run: TraderCommentaryBrowserCaptureRun,
) -> int:
    payload = _dataclass_payload(run)
    _upsert(
        database_path=database_path,
        table="trader_commentary_browser_capture_runs",
        payload=payload,
        conflict_columns=("run_id",),
        update_columns=tuple(column for column in payload if column != "run_id"),
    )
    with closing(sqlite3.connect(database_path)) as connection:
        row = connection.execute(
            """
            SELECT browser_capture_run_id
            FROM trader_commentary_browser_capture_runs
            WHERE run_id = ?
            """,
            (run.run_id,),
        ).fetchone()
    return int(row[0])


def upsert_trader_commentary_browser_capture_item(
    database_path: Path,
    item: TraderCommentaryBrowserCaptureItem,
) -> int:
    payload = _dataclass_payload(item)
    _upsert(
        database_path=database_path,
        table="trader_commentary_browser_capture_items",
        payload=payload,
        conflict_columns=("item_key",),
        update_columns=tuple(column for column in payload if column != "item_key"),
    )
    with closing(sqlite3.connect(database_path)) as connection:
        row = connection.execute(
            """
            SELECT browser_capture_item_id
            FROM trader_commentary_browser_capture_items
            WHERE item_key = ?
            """,
            (item.item_key,),
        ).fetchone()
    return int(row[0])


def list_trader_commentary_browser_capture_runs(
    database_path: Path,
    provider: str | None = None,
) -> list[StoredTraderCommentaryBrowserCaptureRun]:
    where_clause = ""
    parameters: tuple[object, ...] = ()
    if provider:
        where_clause = "WHERE provider = ?"
        parameters = (provider,)
    with closing(sqlite3.connect(database_path)) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            f"""
            SELECT browser_capture_run_id, run_id, provider, target_url,
                   run_date, started_at, completed_at, status, raw_dir,
                   dom_text_path, page_html_path, item_count, stored_count,
                   skipped_count, warnings, source, as_of_date, effective_date
            FROM trader_commentary_browser_capture_runs
            {where_clause}
            ORDER BY started_at DESC, browser_capture_run_id DESC
            """,
            parameters,
        ).fetchall()
    return [StoredTraderCommentaryBrowserCaptureRun(**dict(row)) for row in rows]


def list_trader_commentary_browser_capture_items(
    database_path: Path,
    accepted_only: bool = False,
    uningested_only: bool = False,
    provider: str | None = None,
) -> list[StoredTraderCommentaryBrowserCaptureItem]:
    filters: list[str] = []
    parameters: list[object] = []
    if accepted_only:
        filters.append("accepted_flag = 1")
    if uningested_only:
        filters.append("ingested_at IS NULL")
    if provider:
        filters.append("provider = ?")
        parameters.append(provider)
    where_clause = "WHERE " + " AND ".join(filters) if filters else ""
    with closing(sqlite3.connect(database_path)) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            f"""
            SELECT browser_capture_item_id, run_id, provider, target_url,
                   item_key, external_id, canonical_url, author_text,
                   content_text, created_at_text, observed_at, raw_excerpt,
                   accepted_flag, ingested_at, data_warnings, source,
                   as_of_date, effective_date
            FROM trader_commentary_browser_capture_items
            {where_clause}
            ORDER BY observed_at DESC, browser_capture_item_id DESC
            """,
            tuple(parameters),
        ).fetchall()
    return [StoredTraderCommentaryBrowserCaptureItem(**dict(row)) for row in rows]


def mark_trader_commentary_browser_capture_item_ingested(
    database_path: Path,
    item_key: str,
    ingested_at: str,
) -> None:
    with closing(connect(database_path)) as connection:
        connection.execute(
            """
            UPDATE trader_commentary_browser_capture_items
            SET ingested_at = ?, loaded_at = CURRENT_TIMESTAMP
            WHERE item_key = ?
            """,
            (ingested_at, item_key),
        )
        connection.commit()


def latest_trader_commentary_browser_capture_timestamp(database_path: Path) -> str | None:
    with closing(sqlite3.connect(database_path)) as connection:
        row = connection.execute(
            "SELECT MAX(started_at) FROM trader_commentary_browser_capture_runs"
        ).fetchone()
    return row[0] if row and row[0] is not None else None


def upsert_trader_commentary_discord_capture_run(
    database_path: Path,
    run: TraderCommentaryDiscordCaptureRun,
) -> int:
    payload = _dataclass_payload(run)
    _upsert(
        database_path=database_path,
        table="trader_commentary_discord_capture_runs",
        payload=payload,
        conflict_columns=("run_id",),
        update_columns=tuple(column for column in payload if column != "run_id"),
    )
    with closing(sqlite3.connect(database_path)) as connection:
        row = connection.execute(
            """
            SELECT discord_capture_run_id
            FROM trader_commentary_discord_capture_runs
            WHERE run_id = ?
            """,
            (run.run_id,),
        ).fetchone()
    return int(row[0])


def upsert_trader_commentary_discord_capture_item(
    database_path: Path,
    item: TraderCommentaryDiscordCaptureItem,
) -> int:
    payload = _dataclass_payload(item)
    _upsert(
        database_path=database_path,
        table="trader_commentary_discord_capture_items",
        payload=payload,
        conflict_columns=("item_key",),
        update_columns=tuple(column for column in payload if column != "item_key"),
    )
    with closing(sqlite3.connect(database_path)) as connection:
        row = connection.execute(
            """
            SELECT discord_capture_item_id
            FROM trader_commentary_discord_capture_items
            WHERE item_key = ?
            """,
            (item.item_key,),
        ).fetchone()
    return int(row[0])


def list_trader_commentary_discord_capture_runs(
    database_path: Path,
    provider: str | None = None,
) -> list[StoredTraderCommentaryDiscordCaptureRun]:
    where_clause = ""
    parameters: tuple[object, ...] = ()
    if provider:
        where_clause = "WHERE provider = ?"
        parameters = (provider,)
    with closing(sqlite3.connect(database_path)) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            f"""
            SELECT discord_capture_run_id, run_id, provider, channel_id,
                   run_date, started_at, completed_at, status, raw_dir,
                   messages_path, raw_payload_path, item_count, stored_count,
                   skipped_count, warnings, source, as_of_date, effective_date
            FROM trader_commentary_discord_capture_runs
            {where_clause}
            ORDER BY started_at DESC, discord_capture_run_id DESC
            """,
            parameters,
        ).fetchall()
    return [StoredTraderCommentaryDiscordCaptureRun(**dict(row)) for row in rows]


def list_trader_commentary_discord_capture_items(
    database_path: Path,
    accepted_only: bool = False,
    uningested_only: bool = False,
    provider: str | None = None,
) -> list[StoredTraderCommentaryDiscordCaptureItem]:
    filters: list[str] = []
    parameters: list[object] = []
    if accepted_only:
        filters.append("accepted_flag = 1")
    if uningested_only:
        filters.append("ingested_at IS NULL")
    if provider:
        filters.append("provider = ?")
        parameters.append(provider)
    where_clause = "WHERE " + " AND ".join(filters) if filters else ""
    with closing(sqlite3.connect(database_path)) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            f"""
            SELECT discord_capture_item_id, run_id, provider, channel_id, guild_id,
                   item_key, message_id, canonical_url, author_id, author_text,
                   content_text, message_timestamp, observed_at, raw_excerpt,
                   attachment_count, accepted_flag, ingested_at, data_warnings,
                   source, as_of_date, effective_date
            FROM trader_commentary_discord_capture_items
            {where_clause}
            ORDER BY observed_at DESC, discord_capture_item_id DESC
            """,
            tuple(parameters),
        ).fetchall()
    return [StoredTraderCommentaryDiscordCaptureItem(**dict(row)) for row in rows]


def mark_trader_commentary_discord_capture_item_ingested(
    database_path: Path,
    item_key: str,
    ingested_at: str,
) -> None:
    with closing(connect(database_path)) as connection:
        connection.execute(
            """
            UPDATE trader_commentary_discord_capture_items
            SET ingested_at = ?, loaded_at = CURRENT_TIMESTAMP
            WHERE item_key = ?
            """,
            (ingested_at, item_key),
        )
        connection.commit()


def latest_trader_commentary_discord_capture_timestamp(database_path: Path) -> str | None:
    with closing(sqlite3.connect(database_path)) as connection:
        row = connection.execute(
            "SELECT MAX(started_at) FROM trader_commentary_discord_capture_runs"
        ).fetchone()
    return row[0] if row and row[0] is not None else None


def upsert_trader_commentary_claim(
    database_path: Path,
    claim: TraderCommentaryClaim,
) -> int:
    payload = _dataclass_payload(claim)
    _upsert(
        database_path=database_path,
        table="trader_commentary_claims",
        payload=payload,
        conflict_columns=("claim_key",),
        update_columns=tuple(column for column in payload if column != "claim_key"),
    )
    with closing(sqlite3.connect(database_path)) as connection:
        row = connection.execute(
            "SELECT claim_id FROM trader_commentary_claims WHERE claim_key = ?",
            (claim.claim_key,),
        ).fetchone()
    return int(row[0])


def list_trader_commentary_claims(
    database_path: Path,
    ticker: str | None = None,
    commentary_id: int | None = None,
    claim_key: str | None = None,
) -> list[StoredTraderCommentaryClaim]:
    filters: list[str] = []
    parameters: list[object] = []
    if ticker:
        filters.append("ticker = ?")
        parameters.append(normalize_ticker(ticker))
    if commentary_id is not None:
        filters.append("commentary_id = ?")
        parameters.append(commentary_id)
    if claim_key:
        filters.append("claim_key = ?")
        parameters.append(claim_key)
    where_clause = "WHERE " + " AND ".join(filters) if filters else ""
    with closing(sqlite3.connect(database_path)) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            f"""
            SELECT claim_id, claim_key, commentary_id, claim_date, ticker,
                   instrument_label, claim_type, direction, level_low, level_high,
                   target_price, risk_level, strike_price, premium,
                   condition_text, horizon_text, confidence_text, raw_excerpt,
                   parser_warnings, source, source_url, model_version,
                   as_of_date, effective_date
            FROM trader_commentary_claims
            {where_clause}
            ORDER BY claim_date, claim_id
            """,
            tuple(parameters),
        ).fetchall()
    return [StoredTraderCommentaryClaim(**dict(row)) for row in rows]


def latest_trader_commentary_claim_date(database_path: Path) -> str | None:
    with closing(sqlite3.connect(database_path)) as connection:
        row = connection.execute(
            "SELECT MAX(claim_date) FROM trader_commentary_claims"
        ).fetchone()
    return row[0] if row and row[0] is not None else None


def upsert_trader_commentary_claim_outcome(
    database_path: Path,
    outcome: TraderCommentaryClaimOutcome,
) -> None:
    payload = _dataclass_payload(outcome)
    _upsert(
        database_path=database_path,
        table="trader_commentary_claim_outcomes",
        payload=payload,
        conflict_columns=("claim_key", "model_version", "source"),
        update_columns=tuple(
            column
            for column in payload
            if column not in {"claim_key", "model_version", "source"}
        ),
    )


def list_trader_commentary_claim_outcomes(
    database_path: Path,
    ticker: str | None = None,
    claim_key: str | None = None,
) -> list[TraderCommentaryClaimOutcome]:
    filters: list[str] = []
    parameters: list[object] = []
    if ticker:
        filters.append("ticker = ?")
        parameters.append(normalize_ticker(ticker))
    if claim_key:
        filters.append("claim_key = ?")
        parameters.append(claim_key)
    where_clause = "WHERE " + " AND ".join(filters) if filters else ""
    with closing(sqlite3.connect(database_path)) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            f"""
            SELECT claim_id, claim_key, ticker, instrument_label, claim_type,
                   claim_date, outcome_date, outcome_status, entry_price,
                   entry_price_date, latest_price, latest_price_date,
                   completed_horizons, pending_horizons, return_1d, return_5d,
                   return_20d, return_60d, level_hit_flag,
                   directional_hit_flag, hit_status, data_warnings,
                   model_version, source, as_of_date, effective_date
            FROM trader_commentary_claim_outcomes
            {where_clause}
            ORDER BY outcome_date DESC, ticker, claim_date DESC, claim_type
            """,
            tuple(parameters),
        ).fetchall()
    return [TraderCommentaryClaimOutcome(**dict(row)) for row in rows]


def latest_trader_commentary_outcome_date(database_path: Path) -> str | None:
    with closing(sqlite3.connect(database_path)) as connection:
        row = connection.execute(
            "SELECT MAX(outcome_date) FROM trader_commentary_claim_outcomes"
        ).fetchone()
    return row[0] if row and row[0] is not None else None


def trader_commentary_statuses(database_path: Path) -> list[TraderCommentaryStatus]:
    with closing(sqlite3.connect(database_path)) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            """
            WITH claim_counts AS (
                SELECT ticker, COUNT(*) AS claim_count, MAX(claim_date) AS latest_claim_date
                FROM trader_commentary_claims
                WHERE ticker IS NOT NULL AND ticker != ''
                GROUP BY ticker
            ),
            latest_claim AS (
                SELECT c.*
                FROM trader_commentary_claims c
                JOIN claim_counts cc
                  ON cc.ticker = c.ticker
                 AND cc.latest_claim_date = c.claim_date
                WHERE c.claim_id = (
                    SELECT MAX(c2.claim_id)
                    FROM trader_commentary_claims c2
                    WHERE c2.ticker = c.ticker
                      AND c2.claim_date = c.claim_date
                )
            ),
            outcome_counts AS (
                SELECT ticker, COUNT(*) AS validation_count, MAX(outcome_date) AS latest_outcome_date
                FROM trader_commentary_claim_outcomes
                WHERE ticker IS NOT NULL AND ticker != ''
                GROUP BY ticker
            ),
            latest_outcome AS (
                SELECT o.*
                FROM trader_commentary_claim_outcomes o
                JOIN outcome_counts oc
                  ON oc.ticker = o.ticker
                 AND oc.latest_outcome_date = o.outcome_date
                WHERE o.claim_outcome_id = (
                    SELECT MAX(o2.claim_outcome_id)
                    FROM trader_commentary_claim_outcomes o2
                    WHERE o2.ticker = o.ticker
                      AND o2.outcome_date = o.outcome_date
                )
            )
            SELECT cc.ticker, cc.claim_count, cc.latest_claim_date,
                   lc.claim_type AS latest_claim_type,
                   lc.direction AS latest_direction,
                   oc.latest_outcome_date,
                   lo.outcome_status AS latest_outcome_status,
                   lo.hit_status AS latest_hit_status,
                   COALESCE(oc.validation_count, 0) AS validation_count,
                   NULLIF(TRIM(
                       COALESCE(lc.parser_warnings, '') ||
                       CASE
                         WHEN lc.parser_warnings IS NOT NULL AND lo.data_warnings IS NOT NULL
                         THEN ','
                         ELSE ''
                       END ||
                       COALESCE(lo.data_warnings, '')
                   ), '') AS data_warnings
            FROM claim_counts cc
            LEFT JOIN latest_claim lc ON lc.ticker = cc.ticker
            LEFT JOIN outcome_counts oc ON oc.ticker = cc.ticker
            LEFT JOIN latest_outcome lo ON lo.ticker = cc.ticker
            ORDER BY cc.ticker
            """
        ).fetchall()
    return [TraderCommentaryStatus(**dict(row)) for row in rows]


def signal_statuses_for_family(
    database_path: Path,
    signal_family: str,
    composite_signal_name: str,
    quality_check_prefix: str = "signals",
) -> list[SignalStatus]:
    with closing(sqlite3.connect(database_path)) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            """
            SELECT
                a.ticker,
                a.asset_type,
                s.signal_date AS latest_signal_date,
                s.score AS composite_score,
                s.direction AS composite_direction,
                COALESCE(
                    (
                        SELECT COUNT(*)
                        FROM signals counted
                        WHERE counted.ticker = a.ticker
                          AND counted.signal_family = ?
                          AND counted.signal_date = s.signal_date
                    ),
                    0
                ) AS signal_count,
                s.confidence,
                s.model_version,
                CASE
                    WHEN s.signal_id IS NOT NULL THEN s.data_warnings
                    ELSE (
                        SELECT dqc.details
                        FROM data_quality_checks dqc
                        WHERE dqc.check_name = ? || ':' || a.ticker
                          AND dqc.status != 'ok'
                        ORDER BY dqc.check_timestamp DESC, dqc.check_id DESC
                        LIMIT 1
                    )
                END AS data_warnings
            FROM assets a
            LEFT JOIN signals s
              ON s.signal_id = (
                SELECT signal_id
                FROM signals latest
                WHERE latest.ticker = a.ticker
                  AND latest.signal_family = ?
                  AND latest.signal_name = ?
                ORDER BY latest.signal_date DESC, latest.loaded_at DESC
                LIMIT 1
              )
            WHERE a.active_flag = 1
            ORDER BY a.ticker
            """,
            (
                signal_family,
                quality_check_prefix,
                signal_family,
                composite_signal_name,
            ),
        ).fetchall()
    return [SignalStatus(**dict(row)) for row in rows]


def signal_statuses(database_path: Path) -> list[SignalStatus]:
    return signal_statuses_for_family(
        database_path,
        signal_family="analyst_revision",
        composite_signal_name="analyst_revision.composite",
    )


def list_stored_signals(
    database_path: Path,
    ticker: str | None = None,
    signal_family: str | None = None,
    signal_name: str | None = None,
) -> list[StoredSignal]:
    filters: list[str] = []
    parameters: list[str] = []
    if ticker:
        filters.append("ticker = ?")
        parameters.append(normalize_ticker(ticker))
    if signal_family:
        filters.append("signal_family = ?")
        parameters.append(signal_family)
    if signal_name:
        filters.append("signal_name = ?")
        parameters.append(signal_name)
    where_clause = "WHERE " + " AND ".join(filters) if filters else ""

    with closing(sqlite3.connect(database_path)) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            f"""
            SELECT signal_id, ticker, signal_date, signal_name, signal_family,
                   value, score, direction, reason_code, source, model_version,
                   confidence, data_warnings, source_url, notes, as_of_date,
                   effective_date
            FROM signals
            {where_clause}
            ORDER BY ticker, signal_date, loaded_at, signal_name
            """,
            tuple(parameters),
        ).fetchall()
    return [StoredSignal(**dict(row)) for row in rows]


def upsert_signal_outcome(database_path: Path, outcome: SignalOutcome) -> None:
    payload = _dataclass_payload(outcome)
    _upsert(
        database_path=database_path,
        table="signal_outcomes",
        payload=payload,
        conflict_columns=("ticker", "signal_date", "signal_name", "model_version", "source"),
        update_columns=tuple(
            column
            for column in payload
            if column not in {"ticker", "signal_date", "signal_name", "model_version", "source"}
        ),
    )


def list_signal_outcomes(
    database_path: Path,
    ticker: str | None = None,
    signal_family: str | None = None,
    signal_name: str | None = None,
) -> list[SignalOutcome]:
    filters: list[str] = []
    parameters: list[str] = []
    if ticker:
        filters.append("ticker = ?")
        parameters.append(normalize_ticker(ticker))
    if signal_family:
        filters.append("signal_family = ?")
        parameters.append(signal_family)
    if signal_name:
        filters.append("signal_name = ?")
        parameters.append(signal_name)
    where_clause = "WHERE " + " AND ".join(filters) if filters else ""

    with closing(sqlite3.connect(database_path)) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            f"""
            SELECT signal_id, ticker, signal_date, signal_name, signal_family,
                   signal_score, signal_direction, outcome_date, outcome_status,
                   entry_price, entry_price_date, latest_price, latest_price_date,
                   completed_horizons, pending_horizons, return_5d, return_20d,
                   return_60d, return_120d, directional_hit_flag, hit_status,
                   data_warnings, model_version, source, as_of_date, effective_date
            FROM signal_outcomes
            {where_clause}
            ORDER BY outcome_date DESC, ticker, signal_date DESC, signal_name
            """,
            tuple(parameters),
        ).fetchall()
    return [SignalOutcome(**dict(row)) for row in rows]


def latest_signal_outcome_date(database_path: Path) -> str | None:
    with closing(sqlite3.connect(database_path)) as connection:
        row = connection.execute(
            "SELECT MAX(outcome_date) FROM signal_outcomes"
        ).fetchone()
    return row[0] if row and row[0] is not None else None


def signal_outcome_statuses(
    database_path: Path,
    signal_family: str | None = None,
    signal_name: str | None = None,
) -> list[SignalOutcomeStatus]:
    filters: list[str] = []
    parameters: list[str] = []
    if signal_family:
        filters.append("signal_family = ?")
        parameters.append(signal_family)
    if signal_name:
        filters.append("signal_name = ?")
        parameters.append(signal_name)
    where_clause = "WHERE " + " AND ".join(filters) if filters else ""
    with closing(sqlite3.connect(database_path)) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            f"""
            SELECT ticker, signal_name, signal_date, outcome_date, outcome_status,
                   signal_score, signal_direction, return_5d, return_20d,
                   return_60d, return_120d, directional_hit_flag, hit_status,
                   completed_horizons, pending_horizons, data_warnings
            FROM signal_outcomes
            {where_clause}
            ORDER BY outcome_date DESC, ticker, signal_date DESC, signal_name
            """,
            tuple(parameters),
        ).fetchall()
    return [SignalOutcomeStatus(**dict(row)) for row in rows]


def upsert_score(database_path: Path, score: Score) -> None:
    payload = _dataclass_payload(score)
    _upsert(
        database_path=database_path,
        table="scores",
        payload=payload,
        conflict_columns=("ticker", "score_date", "model_version", "source"),
        update_columns=tuple(
            column
            for column in payload
            if column not in {"ticker", "score_date", "model_version", "source"}
        ),
    )


def list_scores(database_path: Path, ticker: str | None = None) -> list[Score]:
    parameters: tuple[str, ...] = ()
    where_clause = ""
    if ticker:
        where_clause = "WHERE ticker = ?"
        parameters = (normalize_ticker(ticker),)

    with closing(sqlite3.connect(database_path)) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            f"""
            SELECT ticker, score_date, valuation_gap_score, quality_score,
                   growth_score, revision_score, momentum_score, sentiment_score,
                   catalyst_score, risk_score, liquidity_score, confidence_score,
                   timing_score, expected_value_score, opportunity_score,
                   asset_type, score_model, threshold_set, score_reason,
                   data_warnings, model_version, source, as_of_date, effective_date
            FROM scores
            {where_clause}
            ORDER BY ticker, score_date, loaded_at
            """,
            parameters,
        ).fetchall()
    return [Score(**dict(row)) for row in rows]


def latest_target_date(database_path: Path) -> str | None:
    with closing(sqlite3.connect(database_path)) as connection:
        row = connection.execute("SELECT MAX(target_date) FROM targets").fetchone()
    return row[0] if row and row[0] is not None else None


def latest_score_date(database_path: Path) -> str | None:
    with closing(sqlite3.connect(database_path)) as connection:
        row = connection.execute("SELECT MAX(score_date) FROM scores").fetchone()
    return row[0] if row and row[0] is not None else None


def score_statuses(database_path: Path) -> list[ScoreStatus]:
    with closing(sqlite3.connect(database_path)) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            """
            SELECT
                a.ticker,
                a.asset_type,
                (
                    SELECT pf.current_price
                    FROM price_features pf
                    WHERE pf.ticker = a.ticker
                    ORDER BY pf.feature_date DESC, pf.loaded_at DESC
                    LIMIT 1
                ) AS current_price,
                s.score_date,
                s.opportunity_score,
                s.expected_value_score,
                s.valuation_gap_score,
                s.revision_score,
                s.momentum_score,
                s.risk_score,
                s.liquidity_score,
                s.confidence_score,
                s.timing_score,
                s.score_model,
                s.threshold_set,
                CASE
                    WHEN s.score_id IS NOT NULL THEN s.data_warnings
                    ELSE (
                        SELECT dqc.details
                        FROM data_quality_checks dqc
                        WHERE dqc.check_name = 'scoring:' || a.ticker
                          AND dqc.status != 'ok'
                        ORDER BY dqc.check_timestamp DESC, dqc.check_id DESC
                        LIMIT 1
                    )
                END AS data_warnings
            FROM assets a
            LEFT JOIN scores s
              ON s.score_id = (
                SELECT score_id
                FROM scores latest
                WHERE latest.ticker = a.ticker
                ORDER BY latest.score_date DESC, latest.loaded_at DESC
                LIMIT 1
              )
            WHERE a.active_flag = 1
            ORDER BY a.ticker
            """
        ).fetchall()
    return [ScoreStatus(**dict(row)) for row in rows]


def upsert_alert(database_path: Path, alert: Alert) -> None:
    payload = _dataclass_payload(alert)
    _upsert(
        database_path=database_path,
        table="alerts",
        payload=payload,
        conflict_columns=("dedupe_key",),
        update_columns=tuple(
            column
            for column in payload
            if column not in {"dedupe_key"}
        ),
    )


def list_alerts(database_path: Path, ticker: str | None = None) -> list[Alert]:
    parameters: tuple[str, ...] = ()
    where_clause = ""
    if ticker:
        where_clause = "WHERE ticker = ?"
        parameters = (normalize_ticker(ticker),)

    with closing(sqlite3.connect(database_path)) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            f"""
            SELECT ticker, alert_type, alert_timestamp, priority, status,
                   asset_type, current_price, base_target, target_low, target_high,
                   target_date, score_date, valuation_gap, required_gap,
                   opportunity_score, expected_value_score, confidence_score,
                   timing_score, risk_score, liquidity_score, data_quality_score,
                   main_reasons, main_risks, reason_codes, risk_codes,
                   data_warnings, invalidation, alert_model, threshold_set,
                   model_version, source, as_of_date, effective_date, dedupe_key
            FROM alerts
            {where_clause}
            ORDER BY alert_timestamp DESC, ticker, alert_type
            """,
            parameters,
        ).fetchall()
    return [Alert(**dict(row)) for row in rows]


def latest_alert_timestamp(database_path: Path) -> str | None:
    with closing(sqlite3.connect(database_path)) as connection:
        row = connection.execute("SELECT MAX(alert_timestamp) FROM alerts").fetchone()
    return row[0] if row and row[0] is not None else None


def alert_statuses(database_path: Path) -> list[AlertStatus]:
    with closing(sqlite3.connect(database_path)) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            """
            SELECT
                a.ticker,
                a.asset_type,
                al.alert_timestamp,
                al.alert_type,
                al.priority,
                al.status,
                al.target_date,
                al.score_date,
                COALESCE(al.current_price, (
                    SELECT pf.current_price
                    FROM price_features pf
                    WHERE pf.ticker = a.ticker
                    ORDER BY pf.feature_date DESC, pf.loaded_at DESC
                    LIMIT 1
                )) AS current_price,
                al.base_target,
                al.target_low,
                al.target_high,
                al.valuation_gap,
                al.opportunity_score,
                al.expected_value_score,
                al.confidence_score,
                al.timing_score,
                al.risk_score,
                al.liquidity_score,
                al.data_quality_score,
                al.alert_model,
                al.threshold_set,
                al.main_reasons,
                al.main_risks,
                al.reason_codes,
                al.risk_codes,
                al.invalidation,
                CASE
                    WHEN al.alert_id IS NOT NULL THEN al.data_warnings
                    ELSE (
                        SELECT dqc.details
                        FROM data_quality_checks dqc
                        WHERE dqc.check_name = 'alerts:' || a.ticker
                          AND dqc.status != 'ok'
                        ORDER BY dqc.check_timestamp DESC, dqc.check_id DESC
                        LIMIT 1
                    )
                END AS data_warnings
            FROM assets a
            LEFT JOIN alerts al
              ON al.alert_id = (
                SELECT alert_id
                FROM alerts latest
                WHERE latest.ticker = a.ticker
                ORDER BY latest.alert_timestamp DESC, latest.loaded_at DESC
                LIMIT 1
              )
            WHERE a.active_flag = 1
            ORDER BY a.ticker
            """
        ).fetchall()
    return [AlertStatus(**dict(row)) for row in rows]


def list_stored_alerts(database_path: Path, ticker: str | None = None) -> list[StoredAlert]:
    parameters: tuple[str, ...] = ()
    where_clause = ""
    if ticker:
        where_clause = "WHERE ticker = ?"
        parameters = (normalize_ticker(ticker),)

    with closing(sqlite3.connect(database_path)) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            f"""
            SELECT alert_id, ticker, alert_type, alert_timestamp, priority, status,
                   asset_type, current_price, base_target, target_low, target_high,
                   target_date, score_date, opportunity_score, risk_score,
                   data_quality_score, invalidation, alert_model, threshold_set
            FROM alerts
            {where_clause}
            ORDER BY alert_timestamp DESC, ticker, alert_type
            """,
            parameters,
        ).fetchall()
    return [StoredAlert(**dict(row)) for row in rows]


def upsert_alert_outcome(database_path: Path, outcome: AlertOutcome) -> None:
    payload = _dataclass_payload(outcome)
    _upsert(
        database_path=database_path,
        table="alert_outcomes",
        payload=payload,
        conflict_columns=("alert_id",),
        update_columns=tuple(column for column in payload if column != "alert_id"),
    )


def list_alert_outcomes(
    database_path: Path,
    ticker: str | None = None,
) -> list[AlertOutcome]:
    parameters: tuple[str, ...] = ()
    where_clause = ""
    if ticker:
        where_clause = "WHERE ao.ticker = ?"
        parameters = (normalize_ticker(ticker),)

    with closing(sqlite3.connect(database_path)) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            f"""
            SELECT ao.alert_id, ao.outcome_date, ao.ticker, ao.alert_type,
                   ao.alert_timestamp, COALESCE(ao.asset_type, al.asset_type) AS asset_type,
                   COALESCE(ao.alert_model, al.alert_model) AS alert_model,
                   COALESCE(ao.threshold_set, al.threshold_set) AS threshold_set,
                   ao.outcome_status, ao.entry_price, ao.entry_price_date,
                   ao.latest_price, ao.latest_price_date, ao.target_price,
                   ao.invalidation_price, ao.completed_horizons, ao.pending_horizons,
                   ao.return_5d, ao.return_20d, ao.return_60d, ao.return_120d,
                   ao.hit_target_flag, ao.hit_invalidation_flag,
                   ao.max_favorable_excursion, ao.max_adverse_excursion,
                   ao.data_warnings, ao.model_version, ao.user_action, ao.notes,
                   ao.source, ao.as_of_date, ao.effective_date
            FROM alert_outcomes ao
            LEFT JOIN alerts al ON al.alert_id = ao.alert_id
            {where_clause}
            ORDER BY ao.outcome_date DESC, ao.ticker, ao.alert_timestamp DESC
            """,
            parameters,
        ).fetchall()
    return [AlertOutcome(**dict(row)) for row in rows]


def latest_outcome_date(database_path: Path) -> str | None:
    with closing(sqlite3.connect(database_path)) as connection:
        row = connection.execute(
            "SELECT MAX(outcome_date) FROM alert_outcomes"
        ).fetchone()
    return row[0] if row and row[0] is not None else None


def outcome_statuses(database_path: Path) -> list[AlertOutcomeStatus]:
    with closing(sqlite3.connect(database_path)) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            """
            SELECT ao.ticker, ao.alert_type, ao.alert_timestamp,
                   COALESCE(ao.asset_type, al.asset_type) AS asset_type,
                   COALESCE(ao.alert_model, al.alert_model) AS alert_model,
                   COALESCE(ao.threshold_set, al.threshold_set) AS threshold_set,
                   ao.outcome_date, ao.outcome_status, ao.entry_price,
                   ao.entry_price_date, ao.latest_price, ao.latest_price_date,
                   ao.target_price, ao.invalidation_price, ao.return_5d,
                   ao.return_20d, ao.return_60d, ao.return_120d,
                   ao.hit_target_flag, ao.hit_invalidation_flag,
                   ao.max_favorable_excursion, ao.max_adverse_excursion,
                   ao.completed_horizons, ao.pending_horizons, ao.data_warnings
            FROM alert_outcomes ao
            LEFT JOIN alerts al ON al.alert_id = ao.alert_id
            ORDER BY ao.outcome_date DESC, ao.ticker, ao.alert_timestamp DESC
            """
        ).fetchall()
    return [AlertOutcomeStatus(**dict(row)) for row in rows]


def upsert_portfolio_position(database_path: Path, position: PortfolioPosition) -> None:
    payload = _dataclass_payload(position)
    payload["account"] = payload.get("account") or "default"
    payload["position_date"] = payload.get("position_date") or date.today().isoformat()
    payload["currency"] = payload.get("currency") or "USD"
    payload["source"] = payload.get("source") or "manual_csv"
    _upsert(
        database_path=database_path,
        table="portfolio_positions",
        payload=payload,
        conflict_columns=("account", "ticker", "position_date", "source"),
        update_columns=tuple(
            column
            for column in payload
            if column not in {"account", "ticker", "position_date", "source"}
        ),
    )


def upsert_portfolio_cash(database_path: Path, cash: PortfolioCash) -> None:
    payload = _dataclass_payload(cash)
    payload["account"] = payload.get("account") or "default"
    payload["cash_date"] = payload.get("cash_date") or date.today().isoformat()
    payload["currency"] = payload.get("currency") or "USD"
    payload["source"] = payload.get("source") or "manual_csv"
    _upsert(
        database_path=database_path,
        table="portfolio_cash",
        payload=payload,
        conflict_columns=("account", "cash_date", "currency", "source"),
        update_columns=tuple(
            column
            for column in payload
            if column not in {"account", "cash_date", "currency", "source"}
        ),
    )


def upsert_portfolio_review(database_path: Path, review: PortfolioReview) -> None:
    payload = _dataclass_payload(review)
    _upsert(
        database_path=database_path,
        table="portfolio_reviews",
        payload=payload,
        conflict_columns=("ticker", "review_date", "model_version", "source"),
        update_columns=tuple(
            column
            for column in payload
            if column not in {"ticker", "review_date", "model_version", "source"}
        ),
    )


def list_portfolio_positions(
    database_path: Path,
    ticker: str | None = None,
) -> list[PortfolioPosition]:
    parameters: tuple[str, ...] = ()
    where_clause = ""
    if ticker:
        where_clause = "WHERE ticker = ?"
        parameters = (normalize_ticker(ticker),)

    with closing(sqlite3.connect(database_path)) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            f"""
            SELECT ticker, quantity, account, position_date, currency, market_price,
                   market_value, base_market_value, cost_basis_per_share,
                   cost_basis_total, asset_type, sector, source, as_of_date,
                   effective_date
            FROM portfolio_positions
            {where_clause}
            ORDER BY ticker, account, position_date, loaded_at
            """,
            parameters,
        ).fetchall()
    return [PortfolioPosition(**dict(row)) for row in rows]


def latest_portfolio_positions(
    database_path: Path,
    ticker: str | None = None,
) -> list[PortfolioPosition]:
    latest_by_key: dict[tuple[str, str], PortfolioPosition] = {}
    for position in list_portfolio_positions(database_path, ticker):
        key = (position.account or "default", position.ticker)
        existing = latest_by_key.get(key)
        if existing is None or (position.position_date or "") >= (existing.position_date or ""):
            latest_by_key[key] = position
    return sorted(latest_by_key.values(), key=lambda item: (item.ticker, item.account))


def list_portfolio_cash(database_path: Path) -> list[PortfolioCash]:
    with closing(sqlite3.connect(database_path)) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            """
            SELECT cash_amount, account, cash_date, currency, base_cash_amount,
                   source, as_of_date, effective_date
            FROM portfolio_cash
            ORDER BY account, cash_date, currency, loaded_at
            """
        ).fetchall()
    return [PortfolioCash(**dict(row)) for row in rows]


def latest_portfolio_cash(database_path: Path) -> list[PortfolioCash]:
    latest_by_key: dict[tuple[str, str], PortfolioCash] = {}
    for cash in list_portfolio_cash(database_path):
        key = (cash.account or "default", cash.currency or "")
        existing = latest_by_key.get(key)
        if existing is None or (cash.cash_date or "") >= (existing.cash_date or ""):
            latest_by_key[key] = cash
    return sorted(latest_by_key.values(), key=lambda item: (item.account, item.currency or ""))


def list_portfolio_reviews(
    database_path: Path,
    ticker: str | None = None,
) -> list[PortfolioReview]:
    parameters: tuple[str, ...] = ()
    where_clause = ""
    if ticker:
        where_clause = "WHERE ticker = ?"
        parameters = (normalize_ticker(ticker),)

    with closing(sqlite3.connect(database_path)) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            f"""
            SELECT ticker, review_date, asset_type, held_flag, quantity,
                   position_value, cost_basis_total, unrealized_gain_loss,
                   position_weight, sector, sector_weight, cash_available,
                   total_portfolio_value, review_category, sizing_guidance,
                   max_add_value, risk_notes, data_warnings, model_version,
                   source, as_of_date, effective_date
            FROM portfolio_reviews
            {where_clause}
            ORDER BY ticker, review_date, loaded_at
            """,
            parameters,
        ).fetchall()
    return [PortfolioReview(**dict(row)) for row in rows]


def latest_portfolio_review_date(database_path: Path) -> str | None:
    with closing(sqlite3.connect(database_path)) as connection:
        row = connection.execute(
            "SELECT MAX(review_date) FROM portfolio_reviews"
        ).fetchone()
    return row[0] if row and row[0] is not None else None


def latest_portfolio_position_date(database_path: Path) -> str | None:
    with closing(sqlite3.connect(database_path)) as connection:
        row = connection.execute(
            "SELECT MAX(position_date) FROM portfolio_positions"
        ).fetchone()
    return row[0] if row and row[0] is not None else None


def latest_portfolio_cash_date(database_path: Path) -> str | None:
    with closing(sqlite3.connect(database_path)) as connection:
        row = connection.execute("SELECT MAX(cash_date) FROM portfolio_cash").fetchone()
    return row[0] if row and row[0] is not None else None


def portfolio_statuses(database_path: Path) -> list[PortfolioReviewStatus]:
    with closing(sqlite3.connect(database_path)) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            """
            SELECT
                a.ticker,
                COALESCE(pr.asset_type, a.asset_type) AS asset_type,
                pr.review_date,
                pr.held_flag,
                pr.quantity,
                pr.position_value,
                pr.cost_basis_total,
                pr.unrealized_gain_loss,
                pr.position_weight,
                COALESCE(pr.sector, a.sector) AS sector,
                pr.sector_weight,
                pr.cash_available,
                pr.total_portfolio_value,
                pr.review_category,
                pr.sizing_guidance,
                pr.max_add_value,
                pr.risk_notes,
                pr.data_warnings,
                pr.model_version
            FROM assets a
            LEFT JOIN portfolio_reviews pr
              ON pr.portfolio_review_id = (
                SELECT portfolio_review_id
                FROM portfolio_reviews latest
                WHERE latest.ticker = a.ticker
                ORDER BY latest.review_date DESC, latest.loaded_at DESC
                LIMIT 1
              )
            WHERE a.active_flag = 1
            ORDER BY a.ticker
            """
        ).fetchall()
    return [PortfolioReviewStatus(**dict(row)) for row in rows]


def valuation_statuses(database_path: Path) -> list[ValuationStatus]:
    with closing(sqlite3.connect(database_path)) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            """
            SELECT
                a.ticker,
                (
                    SELECT pf.current_price
                    FROM price_features pf
                    WHERE pf.ticker = a.ticker
                    ORDER BY pf.feature_date DESC
                    LIMIT 1
                ) AS current_price,
                t.target_date,
                t.base_target,
                t.target_low,
                t.target_high,
                t.valuation_gap,
                t.valuation_score,
                t.valuation_confidence,
                t.method_count,
                CASE
                    WHEN t.target_id IS NOT NULL THEN t.data_warnings
                    ELSE (
                        SELECT dqc.details
                        FROM data_quality_checks dqc
                        WHERE dqc.check_name = 'valuation:' || a.ticker
                          AND dqc.status != 'ok'
                        ORDER BY dqc.check_timestamp DESC, dqc.check_id DESC
                        LIMIT 1
                    )
                END AS data_warnings
            FROM assets a
            LEFT JOIN targets t
              ON t.target_id = (
                SELECT target_id
                FROM targets latest
                WHERE latest.ticker = a.ticker
                ORDER BY latest.target_date DESC, latest.loaded_at DESC
                LIMIT 1
              )
            WHERE a.active_flag = 1
            ORDER BY a.ticker
            """
        ).fetchall()
    return [ValuationStatus(**dict(row)) for row in rows]


def latest_etf_nav_date(database_path: Path) -> str | None:
    with closing(sqlite3.connect(database_path)) as connection:
        row = connection.execute("SELECT MAX(nav_date) FROM etf_navs").fetchone()
    return row[0] if row and row[0] is not None else None


def latest_any_etf_holdings_date(database_path: Path) -> str | None:
    with closing(sqlite3.connect(database_path)) as connection:
        row = connection.execute("SELECT MAX(holdings_date) FROM etf_holdings").fetchone()
    return row[0] if row and row[0] is not None else None


def etf_statuses(database_path: Path) -> list[EtfStatus]:
    with closing(sqlite3.connect(database_path)) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            """
            SELECT
                a.ticker,
                (
                    SELECT pf.current_price
                    FROM price_features pf
                    WHERE pf.ticker = a.ticker
                    ORDER BY pf.feature_date DESC
                    LIMIT 1
                ) AS current_price,
                ef.nav_per_share,
                ef.premium_discount,
                ef.premium_discount_zscore,
                ef.latest_nav_date,
                ef.latest_holdings_date,
                ef.holdings_count,
                EXISTS (
                    SELECT 1
                    FROM targets t
                    WHERE t.ticker = a.ticker
                      AND t.source = 'etf_valuation'
                ) AS target_ready,
                CASE
                    WHEN t.target_id IS NOT NULL THEN t.data_warnings
                    ELSE (
                        SELECT dqc.details
                        FROM data_quality_checks dqc
                        WHERE dqc.check_name = 'valuation:' || a.ticker
                          AND dqc.status != 'ok'
                        ORDER BY dqc.check_timestamp DESC, dqc.check_id DESC
                        LIMIT 1
                    )
                END AS data_warnings
            FROM assets a
            LEFT JOIN etf_features ef
              ON ef.etf_feature_id = (
                SELECT etf_feature_id
                FROM etf_features latest
                WHERE latest.ticker = a.ticker
                ORDER BY latest.feature_date DESC, latest.loaded_at DESC
                LIMIT 1
              )
            LEFT JOIN targets t
              ON t.target_id = (
                SELECT target_id
                FROM targets latest_target
                WHERE latest_target.ticker = a.ticker
                  AND latest_target.source = 'etf_valuation'
                ORDER BY latest_target.target_date DESC, latest_target.loaded_at DESC
                LIMIT 1
              )
            WHERE a.active_flag = 1
              AND LOWER(COALESCE(a.asset_type, '')) = 'etf'
            ORDER BY a.ticker
            """
        ).fetchall()
    statuses: list[EtfStatus] = []
    for row in rows:
        payload = dict(row)
        payload["target_ready"] = bool(payload["target_ready"])
        statuses.append(EtfStatus(**payload))
    return statuses


def insert_data_quality_check(
    database_path: Path,
    check_name: str,
    status: str,
    details: str,
    source: str = "system",
    as_of_date: str | None = None,
    effective_date: str | None = None,
) -> None:
    with closing(connect(database_path)) as connection:
        connection.execute(
            """
            INSERT INTO data_quality_checks (
                check_name, status, details, source, as_of_date, effective_date
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (check_name, status, details, source, as_of_date, effective_date),
        )
        connection.commit()


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def start_pipeline_run(
    database_path: Path,
    run_type: str,
    source: str = "system",
) -> int:
    timestamp = _now_iso()
    with closing(connect(database_path)) as connection:
        cursor = connection.execute(
            """
            INSERT INTO pipeline_runs (
                run_type, status, started_at, source, as_of_date, effective_date
            )
            VALUES (?, 'running', ?, ?, ?, ?)
            """,
            (run_type, timestamp, source, date.today().isoformat(), timestamp),
        )
        connection.commit()
        return int(cursor.lastrowid)


def finish_pipeline_run(
    database_path: Path,
    pipeline_run_id: int,
    status: str,
    summary: str,
) -> None:
    timestamp = _now_iso()
    with closing(connect(database_path)) as connection:
        connection.execute(
            """
            UPDATE pipeline_runs
            SET status = ?, finished_at = ?, summary = ?, loaded_at = CURRENT_TIMESTAMP
            WHERE pipeline_run_id = ?
            """,
            (status, timestamp, summary, pipeline_run_id),
        )
        connection.commit()


def insert_pipeline_step_result(
    database_path: Path,
    pipeline_run_id: int,
    step_name: str,
    status: str,
    rows_loaded: int = 0,
    warnings: str | None = None,
    source: str = "system",
    started_at: str | None = None,
    finished_at: str | None = None,
) -> None:
    started = started_at or _now_iso()
    finished = finished_at or _now_iso()
    with closing(connect(database_path)) as connection:
        connection.execute(
            """
            INSERT INTO pipeline_step_results (
                pipeline_run_id, step_name, status, rows_loaded, warnings,
                started_at, finished_at, source, as_of_date, effective_date
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                pipeline_run_id,
                step_name,
                status,
                rows_loaded,
                warnings,
                started,
                finished,
                source,
                date.today().isoformat(),
                finished,
            ),
        )
        connection.commit()


def latest_pipeline_run(database_path: Path, run_type: str | None = None) -> PipelineRun | None:
    where_clause = "WHERE run_type = ?" if run_type else ""
    parameters: tuple[str, ...] = (run_type,) if run_type else ()
    with closing(sqlite3.connect(database_path)) as connection:
        connection.row_factory = sqlite3.Row
        row = connection.execute(
            f"""
            SELECT pipeline_run_id, run_type, status, started_at, finished_at,
                   source, summary, as_of_date, effective_date
            FROM pipeline_runs
            {where_clause}
            ORDER BY started_at DESC, pipeline_run_id DESC
            LIMIT 1
            """,
            parameters,
        ).fetchone()
    return PipelineRun(**dict(row)) if row else None


def latest_pipeline_step_result(database_path: Path, step_name: str) -> PipelineStepResult | None:
    with closing(sqlite3.connect(database_path)) as connection:
        connection.row_factory = sqlite3.Row
        row = connection.execute(
            """
            SELECT pipeline_step_result_id, pipeline_run_id, step_name, status,
                   rows_loaded, warnings, started_at, finished_at, source,
                   as_of_date, effective_date
            FROM pipeline_step_results
            WHERE step_name = ?
            ORDER BY started_at DESC, pipeline_step_result_id DESC
            LIMIT 1
            """,
            (step_name,),
        ).fetchone()
    return PipelineStepResult(**dict(row)) if row else None


def latest_price_date(database_path: Path) -> str | None:
    with closing(sqlite3.connect(database_path)) as connection:
        row = connection.execute("SELECT MAX(price_date) FROM prices").fetchone()
    return row[0] if row and row[0] is not None else None


def price_statuses(database_path: Path, stale_after_days: int) -> list[PriceStatus]:
    from datetime import date

    today = date.today()
    with closing(sqlite3.connect(database_path)) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            """
            SELECT
                a.ticker,
                COUNT(p.price_id) AS row_count,
                MAX(p.price_date) AS latest_price_date,
                (
                    SELECT pf.current_price
                    FROM price_features pf
                    WHERE pf.ticker = a.ticker
                    ORDER BY pf.feature_date DESC
                    LIMIT 1
                ) AS current_price,
                EXISTS (
                    SELECT 1
                    FROM price_features pf
                    WHERE pf.ticker = a.ticker
                ) AS feature_available
            FROM assets a
            LEFT JOIN prices p ON p.ticker = a.ticker
            WHERE a.active_flag = 1
            GROUP BY a.ticker
            ORDER BY a.ticker
            """
        ).fetchall()

    statuses: list[PriceStatus] = []
    for row in rows:
        latest = row["latest_price_date"]
        stale = True
        if latest:
            try:
                latest_date = date.fromisoformat(latest)
                stale = (today - latest_date).days > stale_after_days
            except ValueError:
                stale = True

        statuses.append(
            PriceStatus(
                ticker=row["ticker"],
                row_count=int(row["row_count"]),
                latest_price_date=latest,
                current_price=row["current_price"],
                feature_available=bool(row["feature_available"]),
                stale=stale,
            )
        )
    return statuses


def count_rows_by_table(database_path: Path, table: str) -> int:
    with closing(sqlite3.connect(database_path)) as connection:
        row = connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()
    return int(row[0])
