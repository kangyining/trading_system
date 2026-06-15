from __future__ import annotations

import argparse
import csv
from datetime import date, datetime
from pathlib import Path
import sys

from .account import (
    account_context_status,
    account_provider_status,
    apply_account_context_backfill,
    build_account_context_fetch_text,
    build_account_provider_status_text,
    export_account_context_template,
    fetch_account_context,
    normalize_account_export,
    preview_account_context_activation,
    validate_account_context_backfill,
)
from .alerts import compute_alerts
from .api_server import api_status, serve_api, serve_api_once_smoke_test
from .config import load_config
from .dashboard import build_dashboard, latest_dashboard_path
from .db import get_database_status, initialize_database
from .browser_commentary import (
    browser_capture_commentary,
    build_browser_capture_status_text,
    ingest_browser_captured_commentary,
)
from .discord_commentary import (
    build_discord_capture_status_text,
    discord_capture_commentary,
    ingest_discord_captured_commentary,
)
from .commentary_onboarding import (
    apply_commentary_onboarding,
    build_commentary_onboarding_plan,
    build_commentary_onboarding_plan_text,
    build_commentary_onboarding_status_text,
    export_commentary_onboarding_template,
    load_commentary_instrument_aliases,
    load_commentary_label_dispositions,
)
from .etf_data import (
    ensure_etf_csv_headers,
    load_etf_holdings_csv,
    load_etf_navs_csv,
    refresh_etf_features,
)
from .fundamental_data import load_estimates_csv, load_fundamentals_csv
from .fundamental_benchmarks import (
    apply_universe_candidates,
    build_fundamental_benchmark_report,
    build_fundamental_benchmark_status_text,
    build_universe_expansion_plan_text,
    compute_fundamental_benchmarks,
    export_universe_candidate_template,
    fundamental_benchmark_status,
)
from .foreign_equity_sources import (
    apply_foreign_equity_sources,
    build_foreign_equity_source_apply_text,
    build_foreign_equity_source_status_text,
    export_foreign_equity_source_templates,
    validate_foreign_equity_sources,
)
from .ibkr_provider import (
    check_ibkr_status,
    probe_ibkr_ticker,
    update_etf_navs_from_ibkr,
    update_quote_snapshots,
)
from .intraday_health import (
    build_intraday_health_text,
    build_intraday_repair_plan_text,
    build_notification_outbox_status_text,
    intraday_health,
)
from .insider_activity import (
    build_insider_source_status_text,
    compute_insider_signals,
    fetch_insider_transactions,
    insider_source_status_report,
    insider_statuses,
)
from .market_data import update_prices
from .manual_ops import (
    build_manual_ops_status_text,
    run_manual_ops_cycle,
    run_manual_ops_loop,
)
from .news_catalysts import (
    compute_news_catalyst_signals,
    load_news_catalysts_csv,
    news_catalyst_statuses,
)
from .news_catalyst_sources import (
    aggregate_news_catalyst_sources,
    apply_news_catalyst_provider_backfill,
    build_news_catalyst_provider_backfill_apply_text,
    build_news_catalyst_provider_backfill_status_text,
    build_news_catalyst_provider_backfill_validation_text,
    build_news_catalyst_coverage_plan_text,
    build_news_catalyst_provider_smoke_test_text,
    build_news_catalyst_provider_upgrade_status_text,
    build_news_catalyst_provider_upgrade_preview_text,
    build_news_catalyst_source_status_text,
    compute_news_catalyst_text_backfill,
    export_news_catalyst_provider_backfill,
    fetch_news_catalyst_sources,
    import_news_catalyst_source_exports,
    news_catalyst_coverage_plan,
    news_catalyst_provider_backfill_apply_status,
    normalize_news_catalyst_provider_export,
    preview_news_catalyst_provider_upgrade,
    news_catalyst_provider_upgrade_status,
    news_catalyst_source_status_report,
)
from .outcomes import build_validation_report, update_alert_outcomes
from .options import (
    build_option_chain_activation_apply_text,
    build_option_chain_activation_status_text,
    build_option_chain_coverage_plan_text,
    build_option_chain_minimum_backfill_plan_text,
    build_option_chain_status_text,
    build_option_provider_repair_plan_text,
    build_options_chain_coverage_apply_text,
    build_options_chain_missing_template_text,
    build_option_provider_status_text,
    build_options_provider_diagnostics_text,
    build_options_provider_test_text,
    build_options_lifecycle_report_text,
    build_options_lifecycle_status_text,
    build_options_outcome_report_text,
    build_options_outcome_status_text,
    build_options_position_status_text,
    build_options_risk_report_text,
    build_options_risk_status_text,
    build_options_status_text,
    compute_options_income,
    compute_options_lifecycle,
    compute_options_outcomes,
    compute_options_risk,
    export_options_chain_backfill_template,
    fetch_options_chain,
    format_option_chain_availability,
    import_options_chain_source_exports,
    option_chain_availability_statuses,
    load_options_chain_csv,
    load_options_positions_csv,
    option_chain_activation_status,
    option_chain_coverage_plan,
    option_fetch_assets,
    option_provider_status,
    validate_options_chain_backfill,
)
from .pipeline import run_intraday_cycle, run_probe_market, run_refresh_data
from .portfolio import compute_portfolio_context, load_portfolio_csvs
from .ranges import compute_range_snapshots
from .readiness import verify_ticker, verify_universe
from .reporting import latest_csv_report_path, latest_report_path, write_daily_report
from .notifications import (
    build_notification_delivery_report_text,
    deliver_notifications,
    test_notification_channel,
)
from .missing_tickers import (
    apply_missing_ticker_onboarding,
    build_missing_ticker_hydration_text,
    build_missing_ticker_onboarding_text,
    build_missing_ticker_plan_text,
    build_missing_ticker_status_text,
    hydrate_missing_ticker,
    missing_ticker_status as get_missing_ticker_status,
)
from .research_tickers import (
    apply_research_ticker,
    build_etf_strategy_review_text,
    build_research_ticker_apply_text,
    build_research_ticker_plan_text,
    build_research_ticker_status_text,
    etf_strategy_review,
    refresh_research_ticker,
    research_ticker_plan,
    research_ticker_status,
)
from .research_recommendations import (
    build_research_recommendation_promotion_text,
    build_research_recommendation_report,
    build_research_recommendation_status_text,
    export_research_recommendation_template,
    generate_research_recommendations,
    import_research_recommendations,
    promote_research_recommendation,
    research_recommendation_status,
    set_research_recommendation_status,
)
from .research_preparation import (
    PREPARATION_ACTIONS,
    PREPARATION_SOURCES,
    build_research_preparation_run_text,
    research_preparation_status,
    run_research_preparation,
)
from .revision_evidence import (
    build_revision_evidence,
    build_revision_evidence_report,
)
from .revision_sources import (
    aggregate_revision_sources,
    build_revision_provider_status_text,
    build_revision_source_status_text,
    derive_analyst_revisions_from_source_export,
    fetch_revision_sources,
    import_revision_source_exports,
    revision_source_status_report,
)
from .scoring import compute_scores
from .scheduler import (
    build_scheduler_audit_text,
    build_scheduler_automation_status_text,
    build_scheduler_repair_plan_text,
    audit_scheduler,
)
from .sec_fundamentals import seed_sec_fundamentals
from .signal_validation import (
    build_insider_validation_report,
    build_news_catalyst_validation_report,
    build_revision_validation_report,
    build_short_interest_validation_report,
    validate_insider_signals,
    validate_news_catalyst_signals,
    validate_revision_signals,
    validate_short_interest_signals,
)
from .signals import compute_revision_signals, load_analyst_revisions_csv
from .technical import (
    build_regime_status_text,
    build_technical_status_text,
    compute_regime_signals,
    compute_technical_signals,
)
from .tom_loop import (
    build_tom_loop_health_text,
    build_tom_loop_status_text,
    tom_loop_once,
    tom_loop_start,
    tom_loop_status,
    tom_loop_stop,
)
from .trader_commentary import (
    build_trader_commentary_parse_review,
    build_trader_commentary_status_text,
    build_trader_commentary_validation_report,
    export_trader_commentary_template,
    load_trader_commentary_csv,
    parse_trader_commentary_claims,
    validate_trader_commentary_claims,
)
from .short_interest import (
    build_short_interest_provider_backfill_apply_text,
    build_short_interest_backfill_validation_text,
    build_short_interest_coverage_plan_text,
    build_short_interest_import_preview_text,
    build_short_interest_missing_coverage_plan_text,
    build_short_interest_missing_source_resolution_text,
    build_short_interest_provider_diagnostics_text,
    build_short_interest_provider_status_text,
    build_short_interest_source_status_text,
    build_short_interest_status_text,
    compute_short_interest_signals,
    export_short_interest_backfill,
    export_short_interest_missing_provider_template,
    fetch_short_interest_sources,
    import_short_interest_source_exports,
    load_short_interest_csv,
    normalize_short_interest_provider_export,
    short_interest_missing_coverage_plan,
    short_interest_provider_status,
    short_interest_source_status_report,
    short_interest_statuses,
    short_interest_source_exports_dir,
    validate_short_interest_backfill,
)
from .storage import (
    Asset,
    AssetChangeEvent,
    count_assets,
    count_active_assets,
    count_inactive_assets,
    count_reference_assets,
    count_rows_by_table,
    count_scoreable_assets,
    alert_statuses,
    etf_statuses,
    latest_alert_timestamp,
    latest_any_etf_holdings_date,
    latest_etf_nav_date,
    latest_intraday_gap_timestamp,
    latest_asset,
    latest_outcome_date,
    latest_pipeline_run,
    latest_portfolio_cash_date,
    latest_portfolio_position_date,
    latest_portfolio_review_date,
    latest_price_date,
    latest_quote_timestamp,
    latest_range_snapshot_timestamp,
    latest_regime_signal_date,
    latest_score_date,
    latest_signal_date,
    latest_signal_outcome_date,
    latest_insider_transaction_source_date,
    latest_short_interest_settlement_date,
    latest_target_date,
    latest_technical_signal_date,
    latest_trader_commentary_capture_date,
    latest_trader_commentary_browser_capture_timestamp,
    latest_trader_commentary_discord_capture_timestamp,
    latest_trader_commentary_claim_date,
    latest_trader_commentary_outcome_date,
    latest_analyst_revision_aggregate_date,
    latest_news_catalyst_aggregate_date,
    latest_option_chain_snapshot_timestamp,
    latest_option_income_review_date,
    latest_option_position_open_date,
    latest_option_position_lifecycle_review_date,
    latest_option_review_outcome_date,
    latest_option_risk_review_date,
    list_signal_outcomes,
    list_stored_signals,
    list_assets,
    list_notification_deliveries,
    list_notification_events,
    normalize_ticker,
    option_income_statuses,
    option_outcome_statuses,
    outcome_statuses,
    notification_delivery_count,
    latest_notification_delivery_timestamp,
    pending_notification_count,
    portfolio_statuses,
    price_statuses,
    range_statuses,
    regime_signal_statuses,
    score_statuses,
    insert_asset_change_event,
    latest_notification_timestamp,
    set_asset_active_flag,
    signal_statuses,
    technical_signal_statuses,
    upsert_asset,
    valuation_statuses,
)
from .valuation import compute_targets
from .watchlist import load_watchlist, set_watchlist_active, upsert_watchlist_asset


def safe_print(message: object = "") -> None:
    text = str(message)
    encoding = sys.stdout.encoding or "utf-8"
    safe_text = text.encode(encoding, errors="replace").decode(encoding)
    print(safe_text)


def display_path(path: Path | None, project_root: Path) -> str:
    if path is None:
        return "none"
    try:
        return str(path.resolve().relative_to(project_root.resolve()))
    except ValueError:
        return str(path)


def _add_common_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--config",
        type=Path,
        default=None,
        help="Path to a TOM config file. Defaults to configs/default.toml.",
    )


def command_init_db(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    status = initialize_database(config.database_path)
    safe_print(f"Database initialized: {display_path(status.path, config.project_root)}")
    safe_print(
        "Required tables present: "
        f"{status.existing_required_table_count}/{status.required_table_count}"
    )
    return 0


def command_status(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    if config.database_path.exists():
        initialize_database(config.database_path)
    database_status = get_database_status(config.database_path)
    latest_report = latest_report_path(config.reports_dir)
    latest_csv_report = latest_csv_report_path(config.reports_dir)
    latest_dashboard = latest_dashboard_path(config.project_root)
    loop_snapshot = tom_loop_status(config)
    asset_count = count_assets(config.database_path) if config.database_path.exists() else 0
    active_asset_count = (
        count_active_assets(config.database_path) if config.database_path.exists() else 0
    )
    inactive_asset_count = (
        count_inactive_assets(config.database_path) if config.database_path.exists() else 0
    )
    scoreable_asset_count = (
        count_scoreable_assets(config.database_path) if config.database_path.exists() else 0
    )
    reference_asset_count = (
        count_reference_assets(config.database_path) if config.database_path.exists() else 0
    )
    price_row_count = (
        count_rows_by_table(config.database_path, "prices")
        if config.database_path.exists() and "prices" in database_status.existing_tables
        else 0
    )
    latest_price = (
        latest_price_date(config.database_path)
        if config.database_path.exists() and "prices" in database_status.existing_tables
        else None
    )
    fundamental_row_count = (
        count_rows_by_table(config.database_path, "fundamentals")
        if config.database_path.exists() and "fundamentals" in database_status.existing_tables
        else 0
    )
    estimate_row_count = (
        count_rows_by_table(config.database_path, "estimates")
        if config.database_path.exists() and "estimates" in database_status.existing_tables
        else 0
    )
    target_row_count = (
        count_rows_by_table(config.database_path, "targets")
        if config.database_path.exists() and "targets" in database_status.existing_tables
        else 0
    )
    score_row_count = (
        count_rows_by_table(config.database_path, "scores")
        if config.database_path.exists() and "scores" in database_status.existing_tables
        else 0
    )
    fundamental_benchmark = (
        fundamental_benchmark_status(config)
        if config.database_path.exists()
        and "fundamental_benchmark_snapshots" in database_status.existing_tables
        and "fundamental_comparison_snapshots" in database_status.existing_tables
        else None
    )
    fundamental_benchmark_row_count = (
        fundamental_benchmark.benchmark_snapshot_count if fundamental_benchmark else 0
    )
    fundamental_comparison_row_count = (
        fundamental_benchmark.comparison_snapshot_count if fundamental_benchmark else 0
    )
    research_recommendations = (
        research_recommendation_status(config)
        if config.database_path.exists()
        and "research_recommendation_candidates" in database_status.existing_tables
        else None
    )
    research_preparation = (
        research_preparation_status(
            config,
            source=config.research_preparation_auto_source,
        )
        if config.database_path.exists()
        and "research_recommendation_candidates" in database_status.existing_tables
        else None
    )
    missing_tickers = (
        get_missing_ticker_status(config)
        if config.database_path.exists()
        and "missing_ticker_candidates" in database_status.existing_tables
        else None
    )
    alert_row_count = (
        count_rows_by_table(config.database_path, "alerts")
        if config.database_path.exists() and "alerts" in database_status.existing_tables
        else 0
    )
    outcome_row_count = (
        count_rows_by_table(config.database_path, "alert_outcomes")
        if config.database_path.exists()
        and "alert_outcomes" in database_status.existing_tables
        else 0
    )
    portfolio_position_row_count = (
        count_rows_by_table(config.database_path, "portfolio_positions")
        if config.database_path.exists()
        and "portfolio_positions" in database_status.existing_tables
        else 0
    )
    portfolio_cash_row_count = (
        count_rows_by_table(config.database_path, "portfolio_cash")
        if config.database_path.exists()
        and "portfolio_cash" in database_status.existing_tables
        else 0
    )
    portfolio_review_row_count = (
        count_rows_by_table(config.database_path, "portfolio_reviews")
        if config.database_path.exists()
        and "portfolio_reviews" in database_status.existing_tables
        else 0
    )
    signal_row_count = (
        count_rows_by_table(config.database_path, "signals")
        if config.database_path.exists() and "signals" in database_status.existing_tables
        else 0
    )
    signal_outcome_row_count = (
        count_rows_by_table(config.database_path, "signal_outcomes")
        if config.database_path.exists()
        and "signal_outcomes" in database_status.existing_tables
        else 0
    )
    revision_source_snapshot_row_count = (
        count_rows_by_table(config.database_path, "analyst_revision_source_snapshots")
        if config.database_path.exists()
        and "analyst_revision_source_snapshots" in database_status.existing_tables
        else 0
    )
    revision_aggregate_row_count = (
        count_rows_by_table(config.database_path, "analyst_revision_aggregates")
        if config.database_path.exists()
        and "analyst_revision_aggregates" in database_status.existing_tables
        else 0
    )
    news_catalyst_source_snapshot_row_count = (
        count_rows_by_table(config.database_path, "news_catalyst_source_snapshots")
        if config.database_path.exists()
        and "news_catalyst_source_snapshots" in database_status.existing_tables
        else 0
    )
    news_catalyst_aggregate_row_count = (
        count_rows_by_table(config.database_path, "news_catalyst_aggregates")
        if config.database_path.exists()
        and "news_catalyst_aggregates" in database_status.existing_tables
        else 0
    )
    trader_commentary_raw_row_count = (
        count_rows_by_table(config.database_path, "trader_commentary_raw")
        if config.database_path.exists()
        and "trader_commentary_raw" in database_status.existing_tables
        else 0
    )
    trader_commentary_claim_row_count = (
        count_rows_by_table(config.database_path, "trader_commentary_claims")
        if config.database_path.exists()
        and "trader_commentary_claims" in database_status.existing_tables
        else 0
    )
    trader_commentary_outcome_row_count = (
        count_rows_by_table(config.database_path, "trader_commentary_claim_outcomes")
        if config.database_path.exists()
        and "trader_commentary_claim_outcomes" in database_status.existing_tables
        else 0
    )
    trader_commentary_browser_capture_run_count = (
        count_rows_by_table(config.database_path, "trader_commentary_browser_capture_runs")
        if config.database_path.exists()
        and "trader_commentary_browser_capture_runs" in database_status.existing_tables
        else 0
    )
    trader_commentary_browser_capture_item_count = (
        count_rows_by_table(config.database_path, "trader_commentary_browser_capture_items")
        if config.database_path.exists()
        and "trader_commentary_browser_capture_items" in database_status.existing_tables
        else 0
    )
    trader_commentary_discord_capture_run_count = (
        count_rows_by_table(config.database_path, "trader_commentary_discord_capture_runs")
        if config.database_path.exists()
        and "trader_commentary_discord_capture_runs" in database_status.existing_tables
        else 0
    )
    trader_commentary_discord_capture_item_count = (
        count_rows_by_table(config.database_path, "trader_commentary_discord_capture_items")
        if config.database_path.exists()
        and "trader_commentary_discord_capture_items" in database_status.existing_tables
        else 0
    )
    insider_source_snapshot_row_count = (
        count_rows_by_table(config.database_path, "insider_transaction_source_snapshots")
        if config.database_path.exists()
        and "insider_transaction_source_snapshots" in database_status.existing_tables
        else 0
    )
    short_interest_source_snapshot_row_count = (
        count_rows_by_table(config.database_path, "short_interest_source_snapshots")
        if config.database_path.exists()
        and "short_interest_source_snapshots" in database_status.existing_tables
        else 0
    )
    option_chain_row_count = (
        count_rows_by_table(config.database_path, "option_chain_snapshots")
        if config.database_path.exists()
        and "option_chain_snapshots" in database_status.existing_tables
        else 0
    )
    option_income_review_row_count = (
        count_rows_by_table(config.database_path, "option_income_reviews")
        if config.database_path.exists()
        and "option_income_reviews" in database_status.existing_tables
        else 0
    )
    option_risk_review_row_count = (
        count_rows_by_table(config.database_path, "option_risk_reviews")
        if config.database_path.exists()
        and "option_risk_reviews" in database_status.existing_tables
        else 0
    )
    option_review_outcome_row_count = (
        count_rows_by_table(config.database_path, "option_review_outcomes")
        if config.database_path.exists()
        and "option_review_outcomes" in database_status.existing_tables
        else 0
    )
    option_position_row_count = (
        count_rows_by_table(config.database_path, "option_position_ledger")
        if config.database_path.exists()
        and "option_position_ledger" in database_status.existing_tables
        else 0
    )
    option_lifecycle_row_count = (
        count_rows_by_table(config.database_path, "option_position_lifecycle_reviews")
        if config.database_path.exists()
        and "option_position_lifecycle_reviews" in database_status.existing_tables
        else 0
    )
    option_fetch_tickers = tuple(
        asset.ticker for asset in option_fetch_assets(config, max_tickers=0)
    )
    option_chain_statuses = (
        option_income_statuses(config.database_path)
        if config.database_path.exists()
        and "option_chain_snapshots" in database_status.existing_tables
        and "option_income_reviews" in database_status.existing_tables
        else []
    )
    option_chain_loaded_tickers = {
        status.ticker for status in option_chain_statuses if status.option_chain_rows
    }
    option_provider = option_provider_status(config, check_connectivity=False)
    option_backfill_status = validate_options_chain_backfill(config)
    option_activation = option_chain_activation_status(config)
    option_coverage_plan = option_chain_coverage_plan(config)
    option_chain_availability = option_chain_availability_statuses(config)
    option_chain_missing_tickers = option_coverage_plan.effective_missing_tickers
    etf_nav_row_count = (
        count_rows_by_table(config.database_path, "etf_navs")
        if config.database_path.exists() and "etf_navs" in database_status.existing_tables
        else 0
    )
    etf_holding_row_count = (
        count_rows_by_table(config.database_path, "etf_holdings")
        if config.database_path.exists() and "etf_holdings" in database_status.existing_tables
        else 0
    )
    etf_feature_row_count = (
        count_rows_by_table(config.database_path, "etf_features")
        if config.database_path.exists() and "etf_features" in database_status.existing_tables
        else 0
    )
    quote_snapshot_row_count = (
        count_rows_by_table(config.database_path, "quote_snapshots")
        if config.database_path.exists()
        and "quote_snapshots" in database_status.existing_tables
        else 0
    )
    intraday_gap_row_count = (
        count_rows_by_table(config.database_path, "intraday_gap_snapshots")
        if config.database_path.exists()
        and "intraday_gap_snapshots" in database_status.existing_tables
        else 0
    )
    range_snapshot_row_count = (
        count_rows_by_table(config.database_path, "range_snapshots")
        if config.database_path.exists()
        and "range_snapshots" in database_status.existing_tables
        else 0
    )
    technical_signal_snapshot_row_count = (
        count_rows_by_table(config.database_path, "technical_signal_snapshots")
        if config.database_path.exists()
        and "technical_signal_snapshots" in database_status.existing_tables
        else 0
    )
    regime_signal_snapshot_row_count = (
        count_rows_by_table(config.database_path, "regime_signal_snapshots")
        if config.database_path.exists()
        and "regime_signal_snapshots" in database_status.existing_tables
        else 0
    )
    notification_event_row_count = (
        count_rows_by_table(config.database_path, "notification_events")
        if config.database_path.exists()
        and "notification_events" in database_status.existing_tables
        else 0
    )
    notification_delivery_row_count = (
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
    pending_notifications = (
        pending_notification_count(config.database_path)
        if config.database_path.exists()
        and "notification_events" in database_status.existing_tables
        else 0
    )
    pipeline_run_count = (
        count_rows_by_table(config.database_path, "pipeline_runs")
        if config.database_path.exists()
        and "pipeline_runs" in database_status.existing_tables
        else 0
    )
    latest_target = (
        latest_target_date(config.database_path)
        if config.database_path.exists() and "targets" in database_status.existing_tables
        else None
    )
    latest_score = (
        latest_score_date(config.database_path)
        if config.database_path.exists() and "scores" in database_status.existing_tables
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
    latest_signal = (
        latest_signal_date(config.database_path)
        if config.database_path.exists() and "signals" in database_status.existing_tables
        else None
    )
    latest_technical = (
        latest_technical_signal_date(config.database_path)
        if config.database_path.exists()
        and "technical_signal_snapshots" in database_status.existing_tables
        else None
    )
    latest_regime = (
        latest_regime_signal_date(config.database_path)
        if config.database_path.exists()
        and "regime_signal_snapshots" in database_status.existing_tables
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
    latest_option_chain = (
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
    latest_news_catalyst_aggregate = (
        latest_news_catalyst_aggregate_date(config.database_path)
        if config.database_path.exists()
        and "news_catalyst_aggregates" in database_status.existing_tables
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
    latest_trader_commentary_outcome = (
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
    latest_insider_source = (
        latest_insider_transaction_source_date(config.database_path)
        if config.database_path.exists()
        and "insider_transaction_source_snapshots" in database_status.existing_tables
        else None
    )
    latest_short_interest_source = (
        latest_short_interest_settlement_date(config.database_path)
        if config.database_path.exists()
        and "short_interest_source_snapshots" in database_status.existing_tables
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
    latest_gap = (
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
    latest_notification = (
        latest_notification_timestamp(config.database_path)
        if config.database_path.exists()
        and "notification_events" in database_status.existing_tables
        else None
    )
    latest_notification_delivery = (
        latest_notification_delivery_timestamp(config.database_path)
        if config.database_path.exists()
        and "notification_deliveries" in database_status.existing_tables
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
    commentary_onboarding_plan = build_commentary_onboarding_plan(config)
    short_interest_exports_dir = short_interest_source_exports_dir(config)
    news_catalyst_signal_count = (
        len(
            list_stored_signals(
                config.database_path,
                signal_family="news_catalyst",
            )
        )
        if config.database_path.exists() and "signals" in database_status.existing_tables
        else 0
    )
    news_catalyst_outcome_count = (
        len(
            list_signal_outcomes(
                config.database_path,
                signal_family="news_catalyst",
                signal_name="news_catalyst.composite",
            )
        )
        if config.database_path.exists()
        and "signal_outcomes" in database_status.existing_tables
        else 0
    )
    insider_signal_count = (
        len(
            list_stored_signals(
                config.database_path,
                signal_family="insider_activity",
            )
        )
        if config.database_path.exists() and "signals" in database_status.existing_tables
        else 0
    )
    insider_outcome_count = (
        len(
            list_signal_outcomes(
                config.database_path,
                signal_family="insider_activity",
                signal_name="insider_activity.composite",
            )
        )
        if config.database_path.exists()
        and "signal_outcomes" in database_status.existing_tables
        else 0
    )
    short_interest_signal_count = (
        len(
            list_stored_signals(
                config.database_path,
                signal_family="short_interest",
            )
        )
        if config.database_path.exists() and "signals" in database_status.existing_tables
        else 0
    )
    short_interest_outcome_count = (
        len(
            list_signal_outcomes(
                config.database_path,
                signal_family="short_interest",
                signal_name="short_interest.composite",
            )
        )
        if config.database_path.exists()
        and "signal_outcomes" in database_status.existing_tables
        else 0
    )
    current_intraday_health = intraday_health(config)
    scheduler_audit_result = audit_scheduler(config)
    heartbeat_job = next(
        (
            job
            for job in scheduler_audit_result.jobs
            if job.job_key == "intraday_heartbeat"
        ),
        None,
    )

    safe_print("Target Opportunity Monitor status")
    safe_print(f"Config: {display_path(config.config_path, config.project_root)}")
    safe_print(f"Database: {display_path(config.database_path, config.project_root)}")
    safe_print(f"Database exists: {database_status.exists}")
    safe_print(
        "Required tables present: "
        f"{database_status.existing_required_table_count}/"
        f"{database_status.required_table_count}"
    )
    safe_print(f"Report directory: {display_path(config.reports_dir, config.project_root)}")
    safe_print(f"Latest report: {display_path(latest_report, config.project_root)}")
    safe_print(f"Latest CSV report: {display_path(latest_csv_report, config.project_root)}")
    safe_print(f"Latest dashboard: {display_path(latest_dashboard, config.project_root)}")
    safe_print(f"Watchlist file: {display_path(config.watchlist_path, config.project_root)}")
    safe_print(f"Watchlist exists: {config.watchlist_path.exists()}")
    safe_print(
        "Universe candidate file: "
        f"{display_path(config.universe_candidates_path, config.project_root)}"
    )
    safe_print(f"Universe candidate file exists: {config.universe_candidates_path.exists()}")
    safe_print(
        "Sector benchmark file: "
        f"{display_path(config.sector_benchmarks_path, config.project_root)}"
    )
    safe_print(f"Sector benchmark file exists: {config.sector_benchmarks_path.exists()}")
    safe_print(
        "Portfolio positions file: "
        f"{display_path(config.portfolio_positions_path, config.project_root)}"
    )
    safe_print(f"Portfolio positions file exists: {config.portfolio_positions_path.exists()}")
    safe_print(
        "Portfolio cash file: "
        f"{display_path(config.portfolio_cash_path, config.project_root)}"
    )
    safe_print(f"Portfolio cash file exists: {config.portfolio_cash_path.exists()}")
    safe_print(
        "Analyst revisions file: "
        f"{display_path(config.analyst_revisions_path, config.project_root)}"
    )
    safe_print(f"Analyst revisions file exists: {config.analyst_revisions_path.exists()}")
    safe_print(
        "Analyst revision source export: "
        f"{display_path(config.analyst_revision_source_export_path, config.project_root)}"
    )
    safe_print(
        "Analyst revision source export exists: "
        f"{config.analyst_revision_source_export_path.exists()}"
    )
    safe_print(
        "News/catalyst file: "
        f"{display_path(config.news_catalysts_path, config.project_root)}"
    )
    safe_print(f"News/catalyst file exists: {config.news_catalysts_path.exists()}")
    safe_print(
        "Trader commentary file: "
        f"{display_path(config.trader_commentary_path, config.project_root)}"
    )
    safe_print(f"Trader commentary file exists: {config.trader_commentary_path.exists()}")
    safe_print(
        "Trader commentary alias file: "
        f"{display_path(config.trader_commentary_aliases_path, config.project_root)}"
    )
    safe_print(
        "Trader commentary alias file exists: "
        f"{config.trader_commentary_aliases_path.exists()}"
    )
    safe_print(
        "Trader commentary export directory: "
        f"{display_path(config.trader_commentary_exports_dir, config.project_root)}"
    )
    safe_print(
        "Trader commentary export directory exists: "
        f"{config.trader_commentary_exports_dir.exists()}"
    )
    safe_print(
        "Trader commentary browser capture directory: "
        f"{display_path(config.trader_commentary_browser_capture_dir, config.project_root)}"
    )
    safe_print(
        "Trader commentary browser capture directory exists: "
        f"{config.trader_commentary_browser_capture_dir.exists()}"
    )
    safe_print(
        "Trader commentary browser capture enabled: "
        f"{config.commentary_browser_capture_enabled}"
    )
    safe_print(
        "Trader commentary Discord capture directory: "
        f"{display_path(config.trader_commentary_discord_capture_dir, config.project_root)}"
    )
    safe_print(
        "Trader commentary Discord capture directory exists: "
        f"{config.trader_commentary_discord_capture_dir.exists()}"
    )
    safe_print(
        "Trader commentary Discord capture enabled: "
        f"{config.commentary_discord_capture_enabled}"
    )
    safe_print(
        "Short interest file: "
        f"{display_path(config.short_interest_path, config.project_root)}"
    )
    safe_print(f"Short interest file exists: {config.short_interest_path.exists()}")
    safe_print(
        "Short interest source export directory: "
        f"{display_path(short_interest_exports_dir, config.project_root)}"
    )
    safe_print(f"Short interest source export directory exists: {short_interest_exports_dir.exists()}")
    safe_print(
        "Short interest cache directory: "
        f"{display_path(config.short_interest_cache_dir, config.project_root)}"
    )
    safe_print(f"Short interest provider cache files: {short_interest_provider.cache_file_count}")
    safe_print(
        "Latest short interest provider cache timestamp: "
        f"{short_interest_provider.latest_cache_timestamp or 'none'}"
    )
    safe_print(
        "News/catalyst source export directory: "
        f"{display_path(config.news_catalyst_source_exports_dir, config.project_root)}"
    )
    safe_print(
        "News/catalyst source export directory exists: "
        f"{config.news_catalyst_source_exports_dir.exists()}"
    )
    safe_print(
        "News/catalyst cache directory: "
        f"{display_path(config.news_catalyst_cache_dir, config.project_root)}"
    )
    safe_print(f"News/catalyst cache files: {news_catalyst_source_status.cache_file_count}")
    safe_print(
        "Latest news/catalyst cache timestamp: "
        f"{news_catalyst_source_status.latest_cache_at or 'none'}"
    )
    safe_print(
        "Insider activity cache directory: "
        f"{display_path(config.insider_cache_dir, config.project_root)}"
    )
    safe_print(f"Asset count: {asset_count}")
    safe_print(f"Active assets: {active_asset_count}")
    safe_print(f"Scoreable assets: {scoreable_asset_count}")
    safe_print(f"Reference assets: {reference_asset_count}")
    safe_print(f"Inactive assets: {inactive_asset_count}")
    safe_print(f"Price rows: {price_row_count}")
    safe_print(f"Latest price date: {latest_price or 'none'}")
    safe_print(f"Fundamental rows: {fundamental_row_count}")
    safe_print(f"Estimate rows: {estimate_row_count}")
    safe_print(f"Fundamental benchmark rows: {fundamental_benchmark_row_count}")
    safe_print(f"Fundamental comparison rows: {fundamental_comparison_row_count}")
    safe_print(
        "Fundamental benchmark coverage: "
        f"{fundamental_benchmark.compared_ticker_count if fundamental_benchmark else 0}/"
        f"{fundamental_benchmark.scoreable_ticker_count if fundamental_benchmark else scoreable_asset_count}"
    )
    safe_print(
        "Latest fundamental comparison date: "
        f"{fundamental_benchmark.latest_comparison_date if fundamental_benchmark else 'none'}"
    )
    safe_print(
        "Missing sector benchmark assets: "
        + (
            ", ".join(fundamental_benchmark.missing_sector_benchmark_tickers)
            if fundamental_benchmark and fundamental_benchmark.missing_sector_benchmark_tickers
            else "none"
        )
    )
    safe_print(
        "Missing sector benchmark prices: "
        + (
            ", ".join(fundamental_benchmark.missing_sector_benchmark_price_tickers)
            if fundamental_benchmark
            and fundamental_benchmark.missing_sector_benchmark_price_tickers
            else "none"
        )
    )
    safe_print(
        "Research recommendation candidates: "
        f"{research_recommendations.total_count if research_recommendations else 0}"
    )
    safe_print(
        "Research recommendation pending: "
        f"{research_recommendations.pending_count if research_recommendations else 0}"
    )
    safe_print(
        "Research recommendation approved not promoted: "
        f"{research_recommendations.approved_not_promoted_count if research_recommendations else 0}"
    )
    safe_print(
        "Latest research recommendation date: "
        f"{research_recommendations.latest_recommendation_date if research_recommendations else 'none'}"
    )
    safe_print(
        "Top research candidates: "
        + (
            ", ".join(
                f"{candidate.ticker}:{candidate.status}"
                for candidate in research_recommendations.top_pending[:5]
            )
            if research_recommendations and research_recommendations.top_pending
            else "none"
        )
    )
    safe_print(
        "Research preparation autopilot enabled: "
        f"{research_preparation.autopilot.enabled if research_preparation and research_preparation.autopilot else config.research_preparation_auto_enabled}"
    )
    safe_print(
        "Research preparation autopilot due: "
        f"{research_preparation.autopilot.due if research_preparation and research_preparation.autopilot else 'unknown'}"
    )
    safe_print(
        "Latest research preparation autopilot: "
        + (
            f"{research_preparation.autopilot.latest_status} "
            f"{research_preparation.autopilot.latest_started_at} "
            f"rows={research_preparation.autopilot.latest_rows_loaded}"
            if research_preparation
            and research_preparation.autopilot
            and research_preparation.autopilot.latest_started_at
            else "none"
        )
    )
    safe_print(
        "Research preparation manual blockers: "
        f"{research_preparation.manual_blocked_count if research_preparation else 0}"
    )
    safe_print(
        "Research preparation manual blocker tickers: "
        + (
            ", ".join(
                packet.ticker for packet in research_preparation.manual_blocker_packets
            )
            if research_preparation and research_preparation.manual_blocker_packets
            else "none"
        )
    )
    safe_print(f"ETF NAV rows: {etf_nav_row_count}")
    safe_print(f"ETF holding rows: {etf_holding_row_count}")
    safe_print(f"ETF feature rows: {etf_feature_row_count}")
    safe_print(f"Latest ETF NAV date: {latest_etf_nav or 'none'}")
    safe_print(f"Latest ETF holdings date: {latest_etf_holdings or 'none'}")
    safe_print(f"Quote snapshot rows: {quote_snapshot_row_count}")
    safe_print(f"Latest quote timestamp: {latest_quote or 'none'}")
    safe_print(f"Intraday health: {current_intraday_health.status}")
    safe_print(f"Intraday market session: {current_intraday_health.market_session}")
    safe_print(
        "Intraday regular market hours: "
        f"{current_intraday_health.regular_market_hours}"
    )
    safe_print(f"TOM loop status: {loop_snapshot.status}")
    safe_print(f"TOM loop health: {loop_snapshot.health_status}")
    safe_print(
        "TOM loop heartbeat age seconds: "
        f"{loop_snapshot.heartbeat_age_seconds if loop_snapshot.heartbeat_age_seconds is not None else 'none'}"
    )
    safe_print(f"TOM loop recovery status: {loop_snapshot.recovery_status}")
    safe_print(
        "TOM loop recovery actions: "
        + (
            ", ".join(loop_snapshot.recommended_actions)
            if loop_snapshot.recommended_actions
            else "none"
        )
    )
    safe_print(
        "TOM loop blockers: "
        + (
            ", ".join(loop_snapshot.stale_blockers)
            if loop_snapshot.stale_blockers
            else "none"
        )
    )
    safe_print(f"Scheduler reconciliation: {scheduler_audit_result.status}")
    safe_print(
        "Actual heartbeat command: "
        f"{heartbeat_job.actual_command if heartbeat_job else 'none'}"
    )
    scheduler_warning_codes = [
        warning
        for job in scheduler_audit_result.jobs
        for warning in job.warnings
        if job.status != "configured"
    ]
    safe_print(
        "Scheduler warnings: "
        + (
            ", ".join(dict.fromkeys(scheduler_warning_codes))
            if scheduler_warning_codes
            else "none"
        )
    )
    safe_print(
        "Intraday health blockers: "
        + (
            ", ".join(current_intraday_health.blockers)
            if current_intraday_health.blockers
            else "none"
        )
    )
    safe_print(
        "Intraday health warnings: "
        + (
            ", ".join(current_intraday_health.warnings)
            if current_intraday_health.warnings
            else "none"
        )
    )
    safe_print(
        "Intraday health notes: "
        + (
            ", ".join(current_intraday_health.notes)
            if current_intraday_health.notes
            else "none"
        )
    )
    safe_print(f"Intraday gap rows: {intraday_gap_row_count}")
    safe_print(f"Latest intraday gap timestamp: {latest_gap or 'none'}")
    safe_print(f"Range snapshot rows: {range_snapshot_row_count}")
    safe_print(f"Latest range snapshot timestamp: {latest_range or 'none'}")
    safe_print(f"Technical signal snapshot rows: {technical_signal_snapshot_row_count}")
    safe_print(f"Latest technical signal date: {latest_technical or 'none'}")
    safe_print(f"Regime signal snapshot rows: {regime_signal_snapshot_row_count}")
    safe_print(f"Latest regime signal date: {latest_regime or 'none'}")
    safe_print(f"Notification event rows: {notification_event_row_count}")
    safe_print(f"Pending notifications: {pending_notifications}")
    safe_print(f"Latest notification timestamp: {latest_notification or 'none'}")
    safe_print(f"Notification delivery rows: {notification_delivery_row_count}")
    safe_print(f"Failed notification deliveries: {failed_notification_deliveries}")
    safe_print(
        "Latest notification delivery timestamp: "
        f"{latest_notification_delivery or 'none'}"
    )
    safe_print(f"Pipeline runs: {pipeline_run_count}")
    safe_print(
        "Latest pipeline run: "
        + (
            f"{latest_pipeline.run_type} {latest_pipeline.status} "
            f"{latest_pipeline.started_at}"
            if latest_pipeline
            else "none"
        )
    )
    safe_print(
        "Latest intraday cycle: "
        + (
            f"{latest_intraday_cycle.status} {latest_intraday_cycle.started_at}"
            if latest_intraday_cycle
            else "none"
        )
    )
    safe_print(
        "Missing ticker candidates: "
        f"{missing_tickers.total_candidates if missing_tickers else 0}"
    )
    safe_print(
        "Missing ticker ready to onboard: "
        f"{missing_tickers.ready_to_onboard if missing_tickers else 0}"
    )
    safe_print(
        "Missing ticker blocked: "
        f"{missing_tickers.blocked if missing_tickers else 0}"
    )
    safe_print(f"Target rows: {target_row_count}")
    safe_print(f"Latest target date: {latest_target or 'none'}")
    safe_print(f"Score rows: {score_row_count}")
    safe_print(f"Latest score date: {latest_score or 'none'}")
    safe_print(f"Alert rows: {alert_row_count}")
    safe_print(f"Latest alert timestamp: {latest_alert or 'none'}")
    safe_print(f"Outcome rows: {outcome_row_count}")
    safe_print(f"Latest outcome date: {latest_outcome or 'none'}")
    safe_print(f"Portfolio position rows: {portfolio_position_row_count}")
    safe_print(f"Latest portfolio position date: {latest_portfolio_position or 'none'}")
    safe_print(f"Portfolio cash rows: {portfolio_cash_row_count}")
    safe_print(f"Latest portfolio cash date: {latest_portfolio_cash or 'none'}")
    safe_print(f"Portfolio review rows: {portfolio_review_row_count}")
    safe_print(f"Latest portfolio review date: {latest_portfolio_review or 'none'}")
    safe_print(f"Signal rows: {signal_row_count}")
    safe_print(f"Latest signal date: {latest_signal or 'none'}")
    safe_print(f"Signal outcome rows: {signal_outcome_row_count}")
    safe_print(f"Latest signal validation date: {latest_signal_outcome or 'none'}")
    safe_print(f"News/catalyst signal rows: {news_catalyst_signal_count}")
    safe_print(f"News/catalyst validation rows: {news_catalyst_outcome_count}")
    safe_print(
        "News/catalyst source snapshot rows: "
        f"{news_catalyst_source_snapshot_row_count}"
    )
    safe_print(
        "News/catalyst numeric source snapshot rows: "
        f"{news_catalyst_source_status.numeric_snapshot_count}"
    )
    safe_print(
        "News/catalyst provider numeric source snapshot rows: "
        f"{news_catalyst_source_status.provider_numeric_snapshot_count}"
    )
    safe_print(
        "News/catalyst text-derived numeric source snapshot rows: "
        f"{news_catalyst_source_status.text_derived_snapshot_count}"
    )
    safe_print(
        "News/catalyst numeric ticker coverage: "
        f"{news_catalyst_source_status.total_numeric_ticker_count}/"
        f"{news_catalyst_source_status.active_equity_count}"
    )
    safe_print(
        "News/catalyst provider numeric ticker coverage: "
        f"{news_catalyst_source_status.provider_numeric_ticker_count}/"
        f"{news_catalyst_source_status.active_equity_count}"
    )
    safe_print(
        "News/catalyst text-derived ticker coverage: "
        f"{news_catalyst_source_status.text_derived_ticker_count}/"
        f"{news_catalyst_source_status.active_equity_count}"
    )
    safe_print(
        "News/catalyst missing numeric tickers: "
        f"{len(news_catalyst_source_status.missing_numeric_tickers)}"
    )
    safe_print(
        "News/catalyst provider-native upgrade needed: "
        f"{len(news_catalyst_source_status.provider_native_upgrade_tickers)}"
    )
    safe_print(
        "News/catalyst provider-upgrade status: "
        f"{news_catalyst_upgrade_status.status}"
    )
    safe_print(
        "News/catalyst provider-native upgrade tickers: "
        f"{', '.join(news_catalyst_source_status.provider_native_upgrade_tickers) if news_catalyst_source_status.provider_native_upgrade_tickers else 'none'}"
    )
    safe_print(
        "Latest news/catalyst provider-native source date: "
        f"{news_catalyst_source_status.latest_provider_native_source_date or 'none'}"
    )
    safe_print(
        "News/catalyst rejected provider-native rows: "
        f"{news_catalyst_source_status.provider_native_rejected_row_count}"
    )
    safe_print(
        "News/catalyst rejected provider-native tickers: "
        f"{', '.join(news_catalyst_source_status.provider_native_rejected_tickers) if news_catalyst_source_status.provider_native_rejected_tickers else 'none'}"
    )
    safe_print(
        "News/catalyst backfill valid rows: "
        f"{news_catalyst_upgrade_preview.validation.valid_row_count}"
    )
    safe_print(
        "News/catalyst backfill blank placeholders: "
        f"{news_catalyst_upgrade_preview.validation.blank_placeholder_count}"
    )
    safe_print(
        "News/catalyst backfill invalid rows: "
        f"{news_catalyst_upgrade_preview.validation.invalid_row_count}"
    )
    safe_print(
        "News/catalyst projected provider-native coverage: "
        f"{news_catalyst_upgrade_preview.projected_provider_native_ticker_count}/"
        f"{news_catalyst_upgrade_preview.active_equity_count}"
    )
    safe_print(
        "News/catalyst still-blocked provider-native tickers: "
        f"{', '.join(news_catalyst_upgrade_preview.still_blocked_tickers) if news_catalyst_upgrade_preview.still_blocked_tickers else 'none'}"
    )
    safe_print(
        "News/catalyst backfill apply ready: "
        f"{news_catalyst_backfill_apply_status.backfill_apply_ready}"
    )
    safe_print(
        "News/catalyst valid upgrade tickers: "
        f"{', '.join(news_catalyst_backfill_apply_status.valid_upgrade_tickers) if news_catalyst_backfill_apply_status.valid_upgrade_tickers else 'none'}"
    )
    safe_print(
        "News/catalyst projected upgrade delta: "
        f"{news_catalyst_backfill_apply_status.projected_upgrade_delta}"
    )
    safe_print(
        "News/catalyst blocked apply reason: "
        f"{news_catalyst_backfill_apply_status.blocked_apply_reason or 'none'}"
    )
    safe_print(
        "News/catalyst headline-only source snapshot rows: "
        f"{news_catalyst_source_status.headline_only_snapshot_count}"
    )
    safe_print(f"News/catalyst aggregate rows: {news_catalyst_aggregate_row_count}")
    safe_print(
        "Latest news/catalyst aggregate date: "
        f"{latest_news_catalyst_aggregate or 'none'}"
    )
    safe_print(f"Trader commentary raw rows: {trader_commentary_raw_row_count}")
    safe_print(f"Trader commentary parsed claim rows: {trader_commentary_claim_row_count}")
    safe_print(f"Trader commentary claim outcome rows: {trader_commentary_outcome_row_count}")
    safe_print(
        "Trader commentary onboarding candidates: "
        f"{commentary_onboarding_plan.onboardable_count}"
    )
    safe_print(
        "Trader commentary unmapped instrument labels: "
        f"{commentary_onboarding_plan.unmapped_count}"
    )
    safe_print(f"Trader commentary alias mappings: {commentary_onboarding_plan.alias_count}")
    safe_print(
        "Trader commentary label dispositions: "
        f"{commentary_onboarding_plan.label_disposition_count}"
    )
    safe_print(
        "Trader commentary intentionally unresolved labels: "
        f"{commentary_onboarding_plan.intentionally_unresolved_count}"
    )
    safe_print(
        "Trader commentary ignored non-instrument labels: "
        f"{commentary_onboarding_plan.ignored_non_instrument_count}"
    )
    safe_print(
        "Trader commentary browser capture run rows: "
        f"{trader_commentary_browser_capture_run_count}"
    )
    safe_print(
        "Trader commentary browser capture item rows: "
        f"{trader_commentary_browser_capture_item_count}"
    )
    safe_print(
        "Trader commentary Discord capture run rows: "
        f"{trader_commentary_discord_capture_run_count}"
    )
    safe_print(
        "Trader commentary Discord capture item rows: "
        f"{trader_commentary_discord_capture_item_count}"
    )
    safe_print(
        "Latest trader commentary browser capture timestamp: "
        f"{latest_trader_commentary_browser_capture or 'none'}"
    )
    safe_print(
        "Latest trader commentary Discord capture timestamp: "
        f"{latest_trader_commentary_discord_capture or 'none'}"
    )
    safe_print(
        "Latest trader commentary capture date: "
        f"{latest_trader_commentary_capture or 'none'}"
    )
    safe_print(
        "Latest trader commentary claim date: "
        f"{latest_trader_commentary_claim or 'none'}"
    )
    safe_print(
        "Latest trader commentary validation date: "
        f"{latest_trader_commentary_outcome or 'none'}"
    )
    safe_print(
        "News/catalyst source-backed tickers: "
        f"{news_catalyst_source_status.source_backed_ticker_count}/"
        f"{news_catalyst_source_status.active_equity_count}"
    )
    safe_print(
        "News/catalyst missing source-backed tickers: "
        f"{len(news_catalyst_source_status.missing_source_tickers)}"
    )
    safe_print(
        "News/catalyst coverage-plan tickers: "
        f"{', '.join(news_catalyst_plan.planned_tickers) if news_catalyst_plan.planned_tickers else 'none'}"
    )
    safe_print(f"News/catalyst coverage queue stale: {news_catalyst_plan.queue_template_stale}")
    safe_print(
        "News/catalyst missing queue stale: "
        f"{news_catalyst_plan.missing_queue_template_stale}"
    )
    safe_print(
        "News/catalyst provider upgrade queue stale: "
        f"{news_catalyst_plan.provider_upgrade_queue_template_stale}"
    )
    safe_print(
        "News/catalyst provider-upgrade blockers: "
        f"{', '.join(news_catalyst_upgrade_status.provider_blockers) if news_catalyst_upgrade_status.provider_blockers else 'none'}"
    )
    safe_print(
        "News/catalyst provider smoke-test command: "
        "python -m target_opportunity_monitor test-news-catalyst-provider --provider all --ticker AAPL"
    )
    safe_print(
        "News/catalyst provider warnings: "
        f"{', '.join(news_catalyst_plan.provider_warning_summary) if news_catalyst_plan.provider_warning_summary else 'none'}"
    )
    safe_print(f"Insider activity source rows: {insider_source_snapshot_row_count}")
    safe_print(f"Latest insider activity source date: {latest_insider_source or 'none'}")
    safe_print(
        "Insider activity source coverage: "
        f"{insider_source_status.covered_ticker_count}/"
        f"{insider_source_status.active_equity_count}"
    )
    safe_print(
        "Insider activity source-backed tickers: "
        f"{insider_source_status.source_backed_ticker_count}/"
        f"{insider_source_status.active_equity_count}"
    )
    safe_print(
        "Insider activity SEC-rate-limited tickers: "
        f"{len(insider_source_status.sec_rate_limited_tickers)}"
    )
    safe_print(f"Insider activity signal rows: {insider_signal_count}")
    safe_print(f"Insider activity validation rows: {insider_outcome_count}")
    safe_print(f"Short interest source rows: {short_interest_source_snapshot_row_count}")
    safe_print(f"Latest short interest settlement date: {latest_short_interest_source or 'none'}")
    safe_print(
        "Short interest source-backed tickers: "
        f"{short_interest_source_status.source_backed_ticker_count}/"
        f"{short_interest_source_status.active_equity_count}"
    )
    safe_print(
        "Short interest provider order: "
        f"{', '.join(short_interest_provider.provider_order) if short_interest_provider.provider_order else 'none'}"
    )
    safe_print(
        "Short interest fetchable providers: "
        f"{', '.join(short_interest_provider.fetchable_providers) if short_interest_provider.fetchable_providers else 'none'}"
    )
    safe_print(
        "Short interest manual/export-only providers: "
        f"{', '.join(short_interest_provider.manual_only_providers) if short_interest_provider.manual_only_providers else 'none'}"
    )
    safe_print(
        "Short interest provider export valid rows: "
        f"{short_interest_provider.provider_export_valid_row_count}"
    )
    safe_print(
        "Short interest provider export tickers: "
        f"{', '.join(short_interest_provider.provider_export_tickers) if short_interest_provider.provider_export_tickers else 'none'}"
    )
    safe_print(
        "Short interest provider warnings: "
        f"{', '.join(short_interest_provider.warnings) if short_interest_provider.warnings else 'none'}"
    )
    safe_print(
        "Short interest missing source tickers: "
        f"{len(short_interest_source_status.missing_source_tickers)}"
    )
    safe_print(
        "Short interest missing coverage tickers: "
        f"{', '.join(short_interest_missing_plan.missing_tickers) if short_interest_missing_plan.missing_tickers else 'none'}"
    )
    safe_print(
        "Short interest valid missing-row tickers: "
        f"{', '.join(short_interest_missing_plan.valid_missing_tickers) if short_interest_missing_plan.valid_missing_tickers else 'none'}"
    )
    safe_print(
        "Short interest provider diagnostic status: "
        + (
            ", ".join(
                f"{item.ticker}:{item.classification}"
                for item in short_interest_missing_plan.diagnostics
            )
            if short_interest_missing_plan.diagnostics
            else "none"
        )
    )
    safe_print(
        "Short interest missing-provider template: "
        f"{display_path(short_interest_missing_plan.template_path, config.project_root)}"
    )
    safe_print(f"Short interest backfill valid rows: {short_interest_backfill_status.valid_row_count}")
    safe_print(
        "Short interest backfill blank placeholders: "
        f"{short_interest_backfill_status.blank_placeholder_count}"
    )
    safe_print(
        "Short interest backfill invalid rows: "
        f"{short_interest_backfill_status.invalid_row_count}"
    )
    safe_print(
        "Short interest projected source-backed coverage: "
        f"{short_interest_backfill_status.projected_source_backed_count}/"
        f"{short_interest_backfill_status.active_equity_count}"
    )
    safe_print(f"Short interest backfill apply ready: {short_interest_backfill_status.apply_ready}")
    safe_print(
        "Short interest valid import tickers: "
        f"{', '.join(short_interest_backfill_status.valid_tickers) if short_interest_backfill_status.valid_tickers else 'none'}"
    )
    safe_print(
        "Short interest blocked import reason: "
        f"{short_interest_backfill_status.blocked_import_reason or 'none'}"
    )
    safe_print(
        "Short interest missing-coverage blocked apply reason: "
        f"{short_interest_missing_plan.blocked_apply_reason or 'none'}"
    )
    safe_print(f"Short interest signal rows: {short_interest_signal_count}")
    safe_print(f"Short interest validation rows: {short_interest_outcome_count}")
    safe_print(f"Options chain file: {display_path(config.options_chain_path, config.project_root)}")
    safe_print(f"Options chain file exists: {config.options_chain_path.exists()}")
    safe_print(
        "Options chain source-export directory: "
        f"{display_path(config.options_chain_source_exports_dir, config.project_root)}"
    )
    safe_print(
        "Options chain source-export directory exists: "
        f"{config.options_chain_source_exports_dir.exists()}"
    )
    safe_print(f"Options chain source: {config.options_chain_source}")
    safe_print(f"Options chain cache: {display_path(config.options_chain_cache_dir, config.project_root)}")
    safe_print(f"Options provider readiness: {option_provider.readiness_status}")
    safe_print(f"Options provider blocked reason: {option_provider.blocked_reason or 'none'}")
    safe_print(f"Options ibapi status: {option_provider.ibapi_status}")
    safe_print(f"Options provider cache files: {option_provider.cache_file_count}")
    safe_print(
        "Latest options provider cache timestamp: "
        f"{option_provider.latest_cache_timestamp or 'none'}"
    )
    safe_print(f"Options chain rows: {option_chain_row_count}")
    safe_print(f"Option income review rows: {option_income_review_row_count}")
    safe_print(f"Option risk review rows: {option_risk_review_row_count}")
    safe_print(f"Option review outcome rows: {option_review_outcome_row_count}")
    safe_print(f"Option position ledger rows: {option_position_row_count}")
    safe_print(f"Option lifecycle review rows: {option_lifecycle_row_count}")
    safe_print(f"Latest option chain snapshot: {latest_option_chain or 'none'}")
    safe_print(f"Latest option income review date: {latest_option_review or 'none'}")
    safe_print(f"Latest option risk review date: {latest_option_risk_review or 'none'}")
    safe_print(f"Latest option outcome date: {latest_option_outcome or 'none'}")
    safe_print(f"Latest option position open date: {latest_option_position or 'none'}")
    safe_print(f"Latest option lifecycle review date: {latest_option_lifecycle or 'none'}")
    safe_print(
        "Options positions file: "
        f"{display_path(config.options_positions_path, config.project_root)}"
    )
    safe_print(f"Options positions file exists: {config.options_positions_path.exists()}")
    safe_print(f"Options fetch-universe tickers: {len(option_fetch_tickers)}")
    safe_print(
        "Options missing chain tickers: "
        f"{', '.join(option_chain_missing_tickers) if option_chain_missing_tickers else 'none'}"
    )
    safe_print(
        "Options raw missing chain tickers: "
        f"{', '.join(option_coverage_plan.raw_missing_tickers) if option_coverage_plan.raw_missing_tickers else 'none'}"
    )
    safe_print(
        "Options non-actionable chain tickers: "
        f"{', '.join(option_coverage_plan.non_actionable_tickers) if option_coverage_plan.non_actionable_tickers else 'none'}"
    )
    safe_print(f"Options broader coverage status: {option_coverage_plan.coverage_status}")
    safe_print(
        "Options broader chain coverage: "
        f"{option_coverage_plan.effective_coverage_count}"
    )
    safe_print(
        "Options broader raw chain coverage: "
        f"{option_coverage_plan.raw_coverage_count}"
    )
    safe_print(
        "Options broader valid backfill tickers: "
        f"{', '.join(option_coverage_plan.valid_backfill_tickers) if option_coverage_plan.valid_backfill_tickers else 'none'}"
    )
    safe_print(
        "Options broader projected chain coverage: "
        f"{option_coverage_plan.projected_loaded_ticker_count}/"
        f"{option_coverage_plan.fetch_universe_ticker_count}"
    )
    safe_print(
        "Options broader coverage notes: "
        f"{', '.join(option_coverage_plan.notes) if option_coverage_plan.notes else 'none'}"
    )
    safe_print(
        "Options chain availability: "
        f"{format_option_chain_availability(option_chain_availability)}"
    )
    safe_print(f"Options broader coverage apply ready: {option_coverage_plan.apply_ready}")
    safe_print(
        "Options broader coverage blocked reason: "
        f"{option_coverage_plan.blocked_reason or 'none'}"
    )
    safe_print(f"Options backfill valid rows: {option_backfill_status.valid_row_count}")
    safe_print(
        "Options backfill blank placeholders: "
        f"{option_backfill_status.blank_placeholder_count}"
    )
    safe_print(f"Options backfill invalid rows: {option_backfill_status.invalid_row_count}")
    safe_print(
        "Options projected chain coverage: "
        f"{option_backfill_status.projected_loaded_ticker_count}/"
        f"{option_backfill_status.fetch_universe_ticker_count}"
    )
    safe_print(f"Options backfill apply ready: {option_backfill_status.apply_ready}")
    safe_print(
        "Options backfill blocked reason: "
        f"{option_backfill_status.blocked_reason or 'none'}"
    )
    safe_print(f"Option activation status: {option_activation.activation_status}")
    safe_print(
        "Option activation blocked reason: "
        f"{option_activation.blocked_reason or 'none'}"
    )
    safe_print(
        "Minimum option chain coverage: "
        f"{option_activation.minimum_option_chain_coverage}"
    )
    safe_print(
        "Minimum option valid backfill tickers: "
        f"{', '.join(option_activation.minimum_valid_tickers) if option_activation.minimum_valid_tickers else 'none'}"
    )
    safe_print(f"Minimum option review count: {option_activation.minimum_option_review_count}")
    safe_print(f"Options ibapi repair needed: {option_activation.ibapi_repair_needed}")
    account_status = account_context_status(config)
    safe_print(f"Account context activation status: {account_status.activation_status}")
    safe_print(
        "Account context blockers: "
        f"{', '.join(account_status.blockers) if account_status.blockers else 'none'}"
    )
    safe_print(
        "Account context valid backfill rows: "
        f"positions={account_status.validation.valid_position_rows}, "
        f"cash={account_status.validation.valid_cash_rows}, "
        f"options={account_status.validation.valid_option_position_rows}"
    )
    safe_print(
        f"Account context invalid backfill rows: {account_status.validation.invalid_row_count}"
    )
    safe_print(
        "Account context projected rows: "
        f"portfolio_positions={account_status.preview.projected_portfolio_position_rows}, "
        f"portfolio_cash={account_status.preview.projected_portfolio_cash_rows}, "
        f"option_positions={account_status.preview.projected_option_position_rows}, "
        f"option_lifecycle={account_status.preview.projected_option_lifecycle_rows}"
    )
    option_diag = account_status.option_position_diagnostics
    safe_print(f"Account option readiness: {option_diag.readiness_status}")
    safe_print(
        "Account option staged rows: "
        f"valid={option_diag.valid_option_position_rows}, "
        f"invalid={option_diag.invalid_option_position_rows}, "
        f"blank={option_diag.blank_option_position_rows}"
    )
    safe_print(
        "Account option readiness blockers: "
        f"{', '.join(option_diag.blockers) if option_diag.blockers else 'none'}"
    )
    safe_print(f"Account context apply ready: {account_status.preview.apply_ready}")
    safe_print(
        "Account context blocked reason: "
        f"{account_status.preview.blocked_reason or 'none'}"
    )
    safe_print(f"Analyst revision source snapshot rows: {revision_source_snapshot_row_count}")
    safe_print(f"Analyst revision aggregate rows: {revision_aggregate_row_count}")
    safe_print(f"Latest analyst revision aggregate date: {latest_revision_aggregate or 'none'}")
    safe_print(
        "Analyst revision source-backed tickers: "
        f"{revision_source_status.source_backed_ticker_count}/"
        f"{revision_source_status.active_equity_count}"
    )
    safe_print(f"Revision evidence decision: {revision_evidence.decision}")
    safe_print(f"Universe mode: {config.universe_mode}")
    safe_print(f"Run mode: {config.run_mode}")
    return 0


def command_run_daily(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    if not config.database_path.exists():
        initialize_database(config.database_path)
    result = write_daily_report(config)
    safe_print(f"Daily report written: {display_path(result.path, config.project_root)}")
    safe_print(f"Daily CSV report written: {display_path(result.csv_path, config.project_root)}")
    return 0


def command_build_dashboard(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    initialize_database(config.database_path)
    result = build_dashboard(config)
    safe_print(
        f"Dashboard written: {display_path(result.path, config.project_root)} "
        f"rows={result.row_count}"
    )
    return 0


def command_api_status(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    status = api_status(config)
    safe_print("TOM local API status")
    safe_print(f"Host: {status['host']}")
    safe_print(f"Port: {status['port']}")
    safe_print(f"Local only: {status['local_only']}")
    safe_print(
        "Allowed origins: "
        + (", ".join(status["allowed_origins"]) if status["allowed_origins"] else "none")
    )
    safe_print(f"Mutation confirmation required: {status['require_mutation_confirmation']}")
    safe_print("Endpoints:")
    for endpoint in status["endpoints"]:
        safe_print(f"- {endpoint}")
    return 0


def command_serve_api(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    initialize_database(config.database_path)
    host = args.host or config.api_host
    port = args.port or config.api_port
    if args.once_smoke_test:
        try:
            result = serve_api_once_smoke_test(config, host=host, port=port)
        except ValueError as error:
            safe_print(str(error))
            return 1
        safe_print("TOM local API smoke test")
        safe_print(f"Host: {result['host']}")
        safe_print(f"Port: {result['port']}")
        safe_print(f"Health endpoint: {result['health_status_code']} ok={result['health_ok']}")
        safe_print(f"Status endpoint: {result['status_status_code']} ok={result['status_ok']}")
        return 0 if result["health_ok"] and result["status_ok"] else 1
    safe_print(f"Serving TOM local API at http://{host}:{port}")
    try:
        serve_api(config, host=host, port=port)
    except ValueError as error:
        safe_print(str(error))
        return 1
    except KeyboardInterrupt:
        safe_print("TOM local API stopped.")
        return 0
    return 0


def command_load_options_chain(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    initialize_database(config.database_path)
    result = load_options_chain_csv(config, path=args.file)
    safe_print(
        "Options chain loaded: "
        f"{result.loaded_count} rows from {display_path(result.path, config.project_root)}"
    )
    if result.tickers:
        safe_print("Tickers: " + ", ".join(result.tickers))
    if result.warnings:
        safe_print("Warnings: " + ", ".join(result.warnings))
    return 0


def command_load_options_positions(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    initialize_database(config.database_path)
    try:
        result = load_options_positions_csv(config, path=args.file)
    except ValueError as error:
        safe_print(f"Options positions load failed: {error}")
        return 1
    safe_print(
        "Options positions loaded: "
        f"{result.loaded_count} rows from {display_path(result.path, config.project_root)}"
    )
    if result.tickers:
        safe_print("Tickers: " + ", ".join(result.tickers))
    if result.warnings:
        safe_print("Warnings: " + ", ".join(result.warnings))
    return 0


def command_fetch_options_chain(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    initialize_database(config.database_path)
    result = fetch_options_chain(
        config,
        source=args.source,
        ticker=args.ticker,
        max_tickers=args.max_tickers,
        force_refresh=args.force_refresh,
    )
    safe_print(
        "Options chain fetch: "
        f"source={result.source}, rows_loaded={result.loaded_count}, "
        f"tickers={len(result.results)}, warnings={result.warning_count}"
    )
    if result.cache_dir:
        safe_print(f"Cache: {display_path(result.cache_dir, config.project_root)}")
    for ticker_result in result.results:
        warning_text = (
            " warnings=" + ", ".join(ticker_result.warnings)
            if ticker_result.warnings
            else ""
        )
        safe_print(
            f"{ticker_result.ticker}: {ticker_result.status} "
            f"rows={ticker_result.rows_loaded} "
            f"expirations={ticker_result.selected_expirations} "
            f"strikes={ticker_result.selected_strikes}{warning_text}"
        )
    return 0


def command_compute_options_income(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    initialize_database(config.database_path)
    result = compute_options_income(config, ticker=args.ticker)
    safe_print(
        "Option income reviews computed: "
        f"{result.computed_count} tickers, "
        f"skipped={result.skipped_count}, warnings={result.warning_count}"
    )
    for ticker_result in result.results:
        warning_text = (
            " warnings=" + ", ".join(ticker_result.warnings)
            if ticker_result.warnings
            else ""
        )
        safe_print(
            f"{ticker_result.ticker}: {ticker_result.status} "
            f"reviews={ticker_result.review_count}{warning_text}"
        )
    return 0


def command_compute_options_risk(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    initialize_database(config.database_path)
    result = compute_options_risk(config, ticker=args.ticker)
    safe_print(
        "Option risk reviews computed: "
        f"{result.computed_count} tickers, "
        f"skipped={result.skipped_count}, warnings={result.warning_count}"
    )
    for ticker_result in result.results:
        warning_text = (
            " warnings=" + ", ".join(ticker_result.warnings)
            if ticker_result.warnings
            else ""
        )
        safe_print(
            f"{ticker_result.ticker}: {ticker_result.status} "
            f"risk_reviews={ticker_result.review_count}{warning_text}"
        )
    return 0


def command_compute_options_outcomes(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    initialize_database(config.database_path)
    result = compute_options_outcomes(config, ticker=args.ticker)
    safe_print(
        "Option review outcomes computed: "
        f"{result.computed_count} tickers, "
        f"skipped={result.skipped_count}, warnings={result.warning_count}"
    )
    for ticker_result in result.results:
        warning_text = (
            " warnings=" + ", ".join(ticker_result.warnings)
            if ticker_result.warnings
            else ""
        )
        safe_print(
            f"{ticker_result.ticker}: {ticker_result.status} "
            f"outcomes={ticker_result.outcome_count}{warning_text}"
        )
    return 0


def command_compute_options_lifecycle(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    initialize_database(config.database_path)
    result = compute_options_lifecycle(config, ticker=args.ticker)
    safe_print(
        "Option lifecycle reviews computed: "
        f"{result.computed_count} tickers, "
        f"skipped={result.skipped_count}, warnings={result.warning_count}"
    )
    for ticker_result in result.results:
        warning_text = (
            " warnings=" + ", ".join(ticker_result.warnings)
            if ticker_result.warnings
            else ""
        )
        safe_print(
            f"{ticker_result.ticker}: {ticker_result.status} "
            f"lifecycle_reviews={ticker_result.lifecycle_count}{warning_text}"
        )
    return 0


def command_options_status(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    initialize_database(config.database_path)
    safe_print(build_options_status_text(config))
    return 0


def command_options_risk_status(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    initialize_database(config.database_path)
    safe_print(build_options_risk_status_text(config))
    return 0


def command_options_risk_report(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    initialize_database(config.database_path)
    safe_print(build_options_risk_report_text(config))
    return 0


def command_options_position_status(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    initialize_database(config.database_path)
    safe_print(build_options_position_status_text(config))
    return 0


def command_options_outcome_status(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    initialize_database(config.database_path)
    safe_print(build_options_outcome_status_text(config))
    return 0


def command_options_outcome_report(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    initialize_database(config.database_path)
    safe_print(build_options_outcome_report_text(config))
    return 0


def command_options_lifecycle_status(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    initialize_database(config.database_path)
    safe_print(build_options_lifecycle_status_text(config))
    return 0


def command_options_lifecycle_report(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    initialize_database(config.database_path)
    safe_print(build_options_lifecycle_report_text(config))
    return 0


def command_option_chain_status(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    initialize_database(config.database_path)
    safe_print(build_option_chain_status_text(config))
    return 0


def command_option_provider_status(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    initialize_database(config.database_path)
    safe_print(
        build_option_provider_status_text(
            config,
            check_connectivity=getattr(args, "check_connectivity", False),
        )
    )
    return 0


def command_diagnose_options_provider(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    initialize_database(config.database_path)
    safe_print(build_options_provider_diagnostics_text(config, source=args.source))
    return 0


def command_test_options_provider(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    initialize_database(config.database_path)
    safe_print(build_options_provider_test_text(config, source=args.source, ticker=args.ticker))
    return 0


def command_export_options_chain_backfill_template(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    initialize_database(config.database_path)
    result = export_options_chain_backfill_template(
        config,
        ticker=args.ticker,
        minimum_set=getattr(args, "minimum_set", False),
    )
    safe_print(
        "Options chain backfill template exported: "
        f"{display_path(result.path, config.project_root)} rows={result.row_count}"
    )
    if result.tickers:
        safe_print("Tickers: " + ", ".join(result.tickers))
    if result.warnings:
        safe_print("Warnings: " + ", ".join(result.warnings))
    return 0


def command_validate_options_chain_backfill(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    initialize_database(config.database_path)
    result = validate_options_chain_backfill(config, source_dir=args.dir)
    safe_print("Options chain backfill validation")
    safe_print(f"Source dir: {display_path(result.source_dir, config.project_root)}")
    safe_print(f"Source-export files: {len(result.source_export_files)}")
    safe_print(f"Valid rows: {result.valid_row_count}")
    safe_print(f"Blank placeholders: {result.blank_placeholder_count}")
    safe_print(f"Invalid rows: {result.invalid_row_count}")
    safe_print(
        "Valid tickers: "
        f"{', '.join(result.valid_tickers) if result.valid_tickers else 'none'}"
    )
    safe_print(
        "Projected chain coverage: "
        f"{result.projected_loaded_ticker_count}/{result.fetch_universe_ticker_count}"
    )
    safe_print(
        "Minimum projected chain coverage: "
        f"{result.minimum_projected_loaded_ticker_count}/{result.minimum_ticker_count}"
    )
    safe_print(
        "Minimum valid tickers: "
        f"{', '.join(result.minimum_valid_tickers) if result.minimum_valid_tickers else 'none'}"
    )
    safe_print(
        "Minimum missing tickers: "
        f"{', '.join(result.minimum_missing_tickers) if result.minimum_missing_tickers else 'none'}"
    )
    safe_print(f"Apply ready: {result.apply_ready}")
    safe_print(f"Blocked reason: {result.blocked_reason or 'none'}")
    if result.invalid_reasons:
        safe_print("Invalid row reasons:")
        for reason in result.invalid_reasons:
            safe_print(f"- {reason}")
    return 1 if result.invalid_row_count else 0


def command_import_options_chain_source_exports(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    initialize_database(config.database_path)
    result = import_options_chain_source_exports(config, source_dir=args.dir)
    safe_print(
        "Options chain source exports imported: "
        f"imported={result.imported_count}, valid={result.valid_row_count}, "
        f"invalid={result.invalid_row_count}, placeholders={result.blank_placeholder_count}"
    )
    safe_print(f"Source dir: {display_path(result.source_dir, config.project_root)}")
    if result.tickers:
        safe_print("Tickers: " + ", ".join(result.tickers))
    if result.warnings:
        safe_print("Warnings: " + ", ".join(result.warnings))
    return 1 if result.invalid_row_count else 0


def command_option_chain_activation_status(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    initialize_database(config.database_path)
    safe_print(build_option_chain_activation_status_text(config))
    return 0


def command_option_provider_repair_plan(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    initialize_database(config.database_path)
    safe_print(build_option_provider_repair_plan_text(config, source=args.source))
    return 0


def command_option_chain_minimum_backfill_plan(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    initialize_database(config.database_path)
    safe_print(build_option_chain_minimum_backfill_plan_text(config))
    return 0


def command_option_chain_coverage_plan(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    initialize_database(config.database_path)
    safe_print(build_option_chain_coverage_plan_text(config))
    return 0


def command_export_options_chain_missing_template(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    initialize_database(config.database_path)
    safe_print(build_options_chain_missing_template_text(config))
    return 0


def command_apply_options_chain_coverage_backfill(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    initialize_database(config.database_path)
    text, result = build_options_chain_coverage_apply_text(
        config,
        confirm=args.confirm,
        allow_partial=args.allow_partial,
        source_dir=args.dir,
    )
    safe_print(text)
    if args.confirm and not result.success:
        return 1
    return 0


def _print_account_validation(result: object, config: object) -> None:
    safe_print("Account context backfill validation")
    safe_print(f"Valid portfolio position rows: {result.valid_position_rows}")
    safe_print(f"Valid cash rows: {result.valid_cash_rows}")
    safe_print(f"Valid option position rows: {result.valid_option_position_rows}")
    safe_print(f"Blank rows: {result.blank_rows}")
    safe_print(f"Invalid rows: {result.invalid_row_count}")
    safe_print(
        "Valid portfolio tickers: "
        f"{', '.join(result.valid_position_tickers) if result.valid_position_tickers else 'none'}"
    )
    safe_print(
        "Valid option tickers: "
        f"{', '.join(result.valid_option_tickers) if result.valid_option_tickers else 'none'}"
    )
    if result.warnings:
        safe_print("Warnings: " + ", ".join(result.warnings))
    if result.invalid_rows:
        safe_print("Invalid row reasons:")
        for reason in result.invalid_rows:
            safe_print(f"- {reason}")


def _print_account_preview(preview: object) -> None:
    safe_print("Account context activation preview")
    safe_print(
        "Current rows: "
        f"portfolio_positions={preview.current_portfolio_position_rows}, "
        f"portfolio_cash={preview.current_portfolio_cash_rows}, "
        f"option_positions={preview.current_option_position_rows}, "
        f"option_lifecycle={preview.current_option_lifecycle_rows}"
    )
    safe_print(
        "Projected rows: "
        f"portfolio_positions={preview.projected_portfolio_position_rows}, "
        f"portfolio_cash={preview.projected_portfolio_cash_rows}, "
        f"option_positions={preview.projected_option_position_rows}, "
        f"option_lifecycle={preview.projected_option_lifecycle_rows}"
    )
    safe_print(
        "Option risk rows missing portfolio context: "
        f"{preview.current_missing_portfolio_context_risk_rows}"
    )
    safe_print(f"Projected improvement count: {preview.improvement_count}")
    safe_print(f"Apply ready: {preview.apply_ready}")
    safe_print(f"Blocked reason: {preview.blocked_reason or 'none'}")
    if preview.warnings:
        safe_print("Warnings: " + ", ".join(preview.warnings))


def command_account_context_status(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    initialize_database(config.database_path)
    result = account_context_status(config)
    safe_print("Account Context Status")
    safe_print(f"Activation status: {result.activation_status}")
    safe_print(f"Portfolio position rows: {result.portfolio_position_rows}")
    safe_print(f"Portfolio cash rows: {result.portfolio_cash_rows}")
    safe_print(f"Option position rows: {result.option_position_rows}")
    safe_print(f"Option lifecycle rows: {result.option_lifecycle_rows}")
    safe_print(
        "Option risk rows missing portfolio context: "
        f"{result.option_risk_missing_portfolio_context_rows}"
    )
    safe_print(f"Apply ready: {result.preview.apply_ready}")
    safe_print(f"Blocked reason: {result.preview.blocked_reason or 'none'}")
    safe_print(
        "Blockers: "
        f"{', '.join(result.blockers) if result.blockers else 'none'}"
    )
    safe_print(
        "Valid backfill rows: "
        f"positions={result.validation.valid_position_rows}, "
        f"cash={result.validation.valid_cash_rows}, "
        f"options={result.validation.valid_option_position_rows}"
    )
    safe_print(f"Invalid backfill rows: {result.validation.invalid_row_count}")
    option_diag = result.option_position_diagnostics
    safe_print(f"Option position readiness: {option_diag.readiness_status}")
    safe_print(
        "Option position staged rows: "
        f"valid={option_diag.valid_option_position_rows}, "
        f"invalid={option_diag.invalid_option_position_rows}, "
        f"blank={option_diag.blank_option_position_rows}"
    )
    safe_print(
        "Option position projected rows: "
        f"option_positions={option_diag.projected_option_position_rows}, "
        f"option_lifecycle={option_diag.projected_option_lifecycle_rows}"
    )
    safe_print(
        "Option position valid tickers: "
        f"{', '.join(option_diag.valid_option_tickers) if option_diag.valid_option_tickers else 'none'}"
    )
    safe_print(
        "Option position diagnostics blockers: "
        f"{', '.join(option_diag.blockers) if option_diag.blockers else 'none'}"
    )
    safe_print(
        "Option position recommended actions: "
        f"{', '.join(option_diag.recommended_actions) if option_diag.recommended_actions else 'none'}"
    )
    safe_print(f"Option position append target: {option_diag.append_target_path}")
    safe_print(f"Option position template: {option_diag.template_path}")
    return 0


def command_account_provider_status(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    initialize_database(config.database_path)
    safe_print(
        build_account_provider_status_text(
            config,
            check_connectivity=not args.no_connectivity_check,
        )
    )
    return 0


def command_fetch_account_context(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    initialize_database(config.database_path)
    try:
        result = fetch_account_context(
            config,
            source=args.source,
            read_only=args.read_only,
            provider=args.provider,
            path=args.file,
        )
    except (FileNotFoundError, ValueError) as error:
        safe_print(f"Account context fetch blocked: {error}")
        return 1
    safe_print(build_account_context_fetch_text(result, config))
    return 0


def command_export_account_context_template(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    initialize_database(config.database_path)
    result = export_account_context_template(config)
    safe_print("Account context templates exported")
    safe_print(f"Source dir: {display_path(result.source_dir, config.project_root)}")
    for path in result.files:
        safe_print(f"- {display_path(path, config.project_root)}")
    return 0


def command_validate_account_context_backfill(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    initialize_database(config.database_path)
    result = validate_account_context_backfill(config)
    _print_account_validation(result, config)
    return 1 if result.invalid_row_count else 0


def command_preview_account_context_activation(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    initialize_database(config.database_path)
    preview = preview_account_context_activation(config)
    _print_account_preview(preview)
    return 0


def command_apply_account_context_backfill(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    initialize_database(config.database_path)
    try:
        result = apply_account_context_backfill(
            config,
            confirm=args.confirm,
            allow_partial=args.allow_partial,
        )
    except ValueError as error:
        safe_print(f"Account context apply blocked: {error}")
        return 1
    _print_account_preview(result.preview)
    safe_print(f"Confirmed: {result.confirmed}")
    safe_print(f"Applied: {result.applied}")
    safe_print(
        "Loaded rows: "
        f"positions={result.positions_loaded}, cash={result.cash_loaded}, "
        f"option_positions={result.option_positions_loaded}"
    )
    safe_print(f"Portfolio reviews computed: {result.portfolio_reviews_computed}")
    safe_print(f"Option risk tickers: {result.option_risk_tickers}")
    safe_print(f"Option outcome tickers: {result.option_outcome_tickers}")
    safe_print(f"Option lifecycle tickers: {result.option_lifecycle_tickers}")
    if result.report_path:
        safe_print(f"Daily report written: {display_path(result.report_path, config.project_root)}")
    if result.dashboard_path:
        safe_print(f"Dashboard written: {display_path(result.dashboard_path, config.project_root)}")
    if result.warnings:
        safe_print("Warnings: " + ", ".join(result.warnings))
    return 0 if result.applied or not args.confirm else 1


def command_missing_ticker_status(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    initialize_database(config.database_path)
    safe_print(build_missing_ticker_status_text(config))
    return 0


def command_missing_ticker_plan(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    initialize_database(config.database_path)
    safe_print(build_missing_ticker_plan_text(config, source=args.source))
    return 0


def command_resolve_missing_tickers(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    initialize_database(config.database_path)
    safe_print(build_missing_ticker_plan_text(config, source=args.source))
    return 0


def command_apply_missing_ticker_onboarding(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    initialize_database(config.database_path)
    result = apply_missing_ticker_onboarding(
        config,
        confirm=args.confirm,
        source=args.source,
    )
    safe_print(build_missing_ticker_onboarding_text(result))
    return 0 if result.applied or not args.confirm else 1


def command_hydrate_missing_ticker(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    initialize_database(config.database_path)
    result = hydrate_missing_ticker(config, args.ticker)
    safe_print(build_missing_ticker_hydration_text(result))
    return 0 if result.status == "hydrated" else 1


def command_normalize_account_export(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    initialize_database(config.database_path)
    result = normalize_account_export(
        config,
        provider=args.provider,
        path=args.file,
    )
    safe_print("Account export normalized")
    safe_print(f"Provider: {result.provider}")
    safe_print(f"Input: {display_path(result.input_path, config.project_root)}")
    safe_print(
        "Rows: "
        f"positions={result.position_rows}, cash={result.cash_rows}, "
        f"options={result.option_position_rows}, skipped={result.skipped_rows}"
    )
    for path in result.output_files:
        safe_print(f"- {display_path(path, config.project_root)}")
    if result.warnings:
        safe_print("Warnings: " + ", ".join(result.warnings))
    return 0


def command_activate_options_chain_data(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    initialize_database(config.database_path)
    text, result = build_option_chain_activation_apply_text(
        config,
        confirm=args.confirm,
        allow_partial=args.allow_partial,
        source_dir=args.dir,
    )
    safe_print(text)
    if args.confirm and not result.success:
        return 1
    return 0


def command_load_watchlist(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    initialize_database(config.database_path)
    watchlist_path = args.file or config.watchlist_path
    result = load_watchlist(config.database_path, watchlist_path)
    safe_print(
        "Watchlist loaded: "
        f"{result.loaded_count} assets from "
        f"{display_path(result.path, config.project_root)}"
    )
    if result.tickers:
        safe_print("Tickers: " + ", ".join(result.tickers))
    return 0


def command_list_assets(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    initialize_database(config.database_path)
    assets = list_assets(config.database_path)
    if not assets:
        safe_print("No assets loaded.")
        return 0

    safe_print("Ticker | Name | Type | Role | Exchange | Currency | Sector | Industry | Country")
    for asset in assets:
        safe_print(
            " | ".join(
                (
                    asset.ticker,
                    asset.name or "",
                    asset.asset_type or "",
                    asset.asset_role or "scoreable",
                    asset.exchange or "",
                    asset.currency or "",
                    asset.sector or "",
                    asset.industry or "",
                    asset.country or "",
                )
            )
        )
    return 0


def command_update_prices(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    initialize_database(config.database_path)
    result = update_prices(
        config=config,
        ticker=args.ticker,
        source_mode=args.source,
    )

    safe_print(
        f"Price update complete: loaded={result.loaded_count}, failed={result.failed_count}"
    )
    for ticker_result in result.results:
        warning_text = ", ".join(ticker_result.warnings) if ticker_result.warnings else "none"
        safe_print(
            f"{ticker_result.ticker}: status={ticker_result.status}, "
            f"source={ticker_result.source or 'none'}, "
            f"rows={ticker_result.rows_loaded}, "
            f"feature={ticker_result.feature_available}, "
            f"warnings={warning_text}"
        )
    return 0


def command_price_status(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    initialize_database(config.database_path)
    statuses = price_statuses(
        config.database_path,
        stale_after_days=config.market_data_stale_after_days,
    )
    if not statuses:
        safe_print("No active assets found.")
        return 0

    safe_print("Ticker | Rows | Latest Price Date | Current Price | Stale | Feature")
    for status in statuses:
        current_price = (
            f"{status.current_price:.4f}" if status.current_price is not None else ""
        )
        safe_print(
            " | ".join(
                (
                    status.ticker,
                    str(status.row_count),
                    status.latest_price_date or "",
                    current_price,
                    str(status.stale),
                    str(status.feature_available),
                )
            )
        )
    return 0


def command_load_fundamentals(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    initialize_database(config.database_path)
    path = args.file or config.fundamentals_path
    try:
        result = load_fundamentals_csv(config.database_path, path)
    except ValueError as error:
        safe_print(f"Fundamentals load failed: {error}")
        return 1
    safe_print(
        "Fundamentals loaded: "
        f"{result.loaded_count} rows from {display_path(result.path, config.project_root)}"
    )
    if result.tickers:
        safe_print("Tickers: " + ", ".join(result.tickers))
    return 0


def command_load_estimates(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    initialize_database(config.database_path)
    path = args.file or config.estimates_path
    try:
        result = load_estimates_csv(config.database_path, path)
    except ValueError as error:
        safe_print(f"Estimates load failed: {error}")
        return 1
    safe_print(
        "Estimates loaded: "
        f"{result.loaded_count} rows from {display_path(result.path, config.project_root)}"
    )
    if result.tickers:
        safe_print("Tickers: " + ", ".join(result.tickers))
    return 0


def command_foreign_equity_source_status(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    initialize_database(config.database_path)
    safe_print(build_foreign_equity_source_status_text(validate_foreign_equity_sources(config)))
    return 0


def command_export_foreign_equity_source_template(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    initialize_database(config.database_path)
    fundamentals_path, estimates_path, analyst_targets_path = (
        export_foreign_equity_source_templates(config)
    )
    safe_print("Foreign equity source templates exported:")
    safe_print(f"- Fundamentals: {fundamentals_path}")
    safe_print(f"- Estimates: {estimates_path}")
    safe_print(f"- Analyst targets: {analyst_targets_path}")
    return 0


def command_apply_foreign_equity_source(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    initialize_database(config.database_path)
    result = apply_foreign_equity_sources(config, confirm=args.confirm)
    safe_print(build_foreign_equity_source_apply_text(result))
    if result.blocked_reason:
        return 1
    return 0


def command_export_universe_candidate_template(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    initialize_database(config.database_path)
    path = export_universe_candidate_template(config)
    safe_print(
        "Universe candidate template exported: "
        f"{display_path(path, config.project_root)}"
    )
    return 0


def command_universe_expansion_plan(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    initialize_database(config.database_path)
    safe_print(build_universe_expansion_plan_text(config))
    return 0


def command_apply_universe_candidates(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    initialize_database(config.database_path)
    result = apply_universe_candidates(
        config,
        confirm=args.confirm,
        allow_partial=args.allow_partial,
    )
    mode = "dry-run" if result.dry_run else "confirmed"
    safe_print(f"Universe candidate apply ({mode})")
    safe_print(f"Applied count: {result.applied_count}")
    safe_print(
        "Applied/planned tickers: "
        + (", ".join(result.applied_tickers) if result.applied_tickers else "none")
    )
    safe_print(f"Blocked reason: {result.blocked_reason or 'none'}")
    if result.invalid_candidates:
        safe_print("Invalid candidates:")
        for warning in result.invalid_candidates:
            safe_print(f"- {warning}")
    return 1 if args.confirm and result.blocked_reason else 0


def command_research_ticker_plan(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    initialize_database(config.database_path)
    plan = research_ticker_plan(
        config,
        args.ticker,
        asset_type=args.asset_type,
        refresh_metadata=args.refresh_metadata,
        name=args.name,
        sector=args.sector,
        industry=args.industry,
        cik=args.cik,
        exchange=args.exchange,
        currency=args.currency,
        country=args.country,
    )
    safe_print(build_research_ticker_plan_text(plan))
    return 0


def command_apply_research_ticker(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    initialize_database(config.database_path)
    result = apply_research_ticker(
        config,
        args.ticker,
        asset_type=args.asset_type,
        confirm=args.confirm,
        refresh_metadata=args.refresh_metadata,
        name=args.name,
        sector=args.sector,
        industry=args.industry,
        cik=args.cik,
        exchange=args.exchange,
        currency=args.currency,
        country=args.country,
    )
    safe_print(build_research_ticker_apply_text(result))
    return 1 if args.confirm and result.blocked_reason else 0


def command_refresh_research_ticker(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    initialize_database(config.database_path)
    result, blockers = refresh_research_ticker(config, args.ticker)
    safe_print("Research ticker refresh")
    safe_print(f"Ticker: {normalize_ticker(args.ticker)}")
    if result is None:
        safe_print("Status: blocked")
        safe_print("Blocked reason: " + (", ".join(blockers) if blockers else "unknown"))
        return 1
    safe_print(f"Pipeline run id: {result.pipeline_run_id}")
    safe_print(f"Pipeline status: {result.status}")
    safe_print(f"Steps: {len(result.steps)}")
    warning_steps = [step for step in result.steps if step.warnings]
    safe_print(f"Warning steps: {len(warning_steps)}")
    safe_print("Readiness blockers: " + (", ".join(blockers) if blockers else "none"))
    return 1 if result.status == "error" else 0


def command_research_ticker_status(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    initialize_database(config.database_path)
    safe_print(build_research_ticker_status_text(research_ticker_status(config, args.ticker)))
    return 0


def command_etf_strategy_review(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    initialize_database(config.database_path)
    safe_print(build_etf_strategy_review_text(etf_strategy_review(config, args.ticker)))
    return 0


def command_generate_research_recommendations(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    initialize_database(config.database_path)
    result = generate_research_recommendations(config, args.source)
    safe_print("Research recommendations generated")
    safe_print(f"Source: {result.source}")
    safe_print(f"Candidates touched: {result.candidate_count}")
    safe_print(f"Evidence rows touched: {result.evidence_count}")
    safe_print("Warnings: " + (", ".join(result.warnings) if result.warnings else "none"))
    return 0


def command_export_research_recommendation_template(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    initialize_database(config.database_path)
    path = export_research_recommendation_template(config)
    safe_print(
        "Research recommendation template: "
        f"{display_path(path, config.project_root)}"
    )
    return 0


def command_import_research_recommendations(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    initialize_database(config.database_path)
    result = import_research_recommendations(config, args.file)
    safe_print("Research recommendation import")
    safe_print(f"CSV: {display_path(result.csv_path, config.project_root)}")
    safe_print(f"Imported rows: {result.imported_count}")
    safe_print(f"Skipped rows: {result.skipped_count}")
    safe_print("Warnings: " + (", ".join(result.warnings) if result.warnings else "none"))
    return 1 if result.skipped_count and result.imported_count == 0 else 0


def command_research_recommendation_status(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    initialize_database(config.database_path)
    safe_print(build_research_recommendation_status_text(config))
    return 0


def command_research_preparation_run(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    initialize_database(config.database_path)
    result = run_research_preparation(
        config,
        source=args.source,
        action=args.action,
        confirm=args.confirm,
        tickers=tuple(args.ticker or ()),
    )
    safe_print(build_research_preparation_run_text(result))
    return 1 if result.blocked_reason else 0


def command_research_recommendation_report(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    initialize_database(config.database_path)
    safe_print(build_research_recommendation_report(config))
    return 0


def command_set_research_recommendation_status(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    initialize_database(config.database_path)
    candidate = set_research_recommendation_status(
        config,
        args.id,
        args.status,
        reason=args.reason,
    )
    if candidate is None:
        safe_print("Research recommendation status update failed")
        safe_print("Blocked reason: recommendation_not_found_or_invalid_status")
        return 1
    safe_print("Research recommendation status updated")
    safe_print(f"ID: {candidate.research_recommendation_id}")
    safe_print(f"Ticker: {candidate.ticker}")
    safe_print(f"Status: {candidate.status}")
    return 0


def command_promote_research_recommendation(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    initialize_database(config.database_path)
    result = promote_research_recommendation(config, args.id, confirm=args.confirm)
    safe_print(build_research_recommendation_promotion_text(config, result))
    return 1 if args.confirm and not result.promoted else 0


def command_compute_fundamental_benchmarks(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    initialize_database(config.database_path)
    result = compute_fundamental_benchmarks(config)
    safe_print(
        "Fundamental benchmarks computed: "
        f"benchmarks={result.benchmark_count}, "
        f"comparisons={result.comparison_count}, "
        f"date={result.comparison_date}"
    )
    if result.warnings:
        safe_print("Warnings: " + ", ".join(result.warnings))
    return 0


def command_fundamental_benchmark_status(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    initialize_database(config.database_path)
    safe_print(build_fundamental_benchmark_status_text(config))
    return 0


def command_fundamental_benchmark_report(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    initialize_database(config.database_path)
    safe_print(build_fundamental_benchmark_report(config, ticker=getattr(args, "ticker", None)))
    return 0


def command_load_etf_navs(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    initialize_database(config.database_path)
    if args.file is None:
        ensure_etf_csv_headers(config.etf_navs_path, config.etf_holdings_path)
    path = args.file or config.etf_navs_path
    try:
        result = load_etf_navs_csv(config.database_path, path)
    except ValueError as error:
        safe_print(f"ETF NAV load failed: {error}")
        return 1
    safe_print(
        "ETF NAVs loaded: "
        f"{result.loaded_count} rows from {display_path(result.path, config.project_root)}"
    )
    if result.tickers:
        safe_print("Tickers: " + ", ".join(result.tickers))
    return 0


def command_load_etf_holdings(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    initialize_database(config.database_path)
    if args.file is None:
        ensure_etf_csv_headers(config.etf_navs_path, config.etf_holdings_path)
    path = args.file or config.etf_holdings_path
    try:
        result = load_etf_holdings_csv(config.database_path, path)
    except ValueError as error:
        safe_print(f"ETF holdings load failed: {error}")
        return 1
    safe_print(
        "ETF holdings loaded: "
        f"{result.loaded_count} rows from {display_path(result.path, config.project_root)}"
    )
    if result.tickers:
        safe_print("Tickers: " + ", ".join(result.tickers))
    return 0


def command_load_analyst_revisions(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    initialize_database(config.database_path)
    path = args.file or config.analyst_revisions_path
    result = load_analyst_revisions_csv(config, path)
    safe_print(
        "Analyst revisions loaded: "
        f"{result.row_count} rows, {result.input_signal_count} input signals from "
        f"{display_path(result.path, config.project_root)}"
    )
    if result.tickers:
        safe_print("Tickers: " + ", ".join(result.tickers))
    if result.warnings:
        safe_print("Warnings: " + ", ".join(result.warnings))
    return 0


def command_load_news_catalysts(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    initialize_database(config.database_path)
    path = args.file or config.news_catalysts_path
    try:
        result = load_news_catalysts_csv(config, path)
    except ValueError as error:
        safe_print(f"News/catalyst load failed: {error}")
        return 1
    safe_print(
        "News/catalysts loaded: "
        f"{result.row_count} rows, {result.input_signal_count} input signals from "
        f"{display_path(result.path, config.project_root)}"
    )
    if result.tickers:
        safe_print("Tickers: " + ", ".join(result.tickers))
    if result.warnings:
        safe_print("Warnings: " + ", ".join(result.warnings))
    return 0


def command_load_trader_commentary(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    initialize_database(config.database_path)
    path = args.file or config.trader_commentary_path
    try:
        result = load_trader_commentary_csv(config, path)
    except ValueError as error:
        safe_print(f"Trader commentary load failed: {error}")
        return 1
    safe_print(
        "Trader commentary loaded: "
        f"loaded={result.loaded_count}, skipped={result.skipped_count} from "
        f"{display_path(result.path, config.project_root)}"
    )
    if result.warnings:
        safe_print("Warnings: " + ", ".join(result.warnings))
    return 0


def command_export_trader_commentary_template(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    result = export_trader_commentary_template(config)
    safe_print(
        "Trader commentary template exported: "
        f"{display_path(result.csv_path, config.project_root)}"
    )
    safe_print(
        "Trader commentary text template exported: "
        f"{display_path(result.text_path, config.project_root)}"
    )
    return 0


def command_browser_capture_commentary(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    initialize_database(config.database_path)
    try:
        result = browser_capture_commentary(
            config,
            provider=args.provider,
            target_url=args.target_url,
            dom_text_file=args.dom_text_file,
            page_html_file=args.page_html_file,
            acknowledge_terms_risk=args.acknowledge_terms_risk,
        )
    except ValueError as error:
        safe_print(f"Browser commentary capture failed: {error}")
        return 1
    safe_print(
        "Browser commentary capture complete: "
        f"run_id={result.run_id}, status={result.status}, "
        f"items={result.item_count}, stored={result.stored_count}, "
        f"skipped={result.skipped_count}, "
        f"dir={display_path(result.raw_dir, config.project_root)}"
    )
    if result.warnings:
        safe_print("Warnings: " + ", ".join(result.warnings))
    return 1 if result.status == "blocked" else 0


def command_browser_capture_commentary_status(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    initialize_database(config.database_path)
    safe_print(build_browser_capture_status_text(config))
    return 0


def command_discord_capture_commentary(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    initialize_database(config.database_path)
    try:
        result = discord_capture_commentary(
            config,
            provider=args.provider,
            channel_id=args.channel_id,
            messages_json_file=args.messages_json_file,
            max_messages=args.max_messages,
            acknowledge_permission=args.acknowledge_permission,
        )
    except ValueError as error:
        safe_print(f"Discord commentary capture failed: {error}")
        return 1
    safe_print(
        "Discord commentary capture complete: "
        f"run_id={result.run_id}, status={result.status}, "
        f"items={result.item_count}, stored={result.stored_count}, "
        f"skipped={result.skipped_count}, "
        f"dir={display_path(result.raw_dir, config.project_root)}"
    )
    if result.warnings:
        safe_print("Warnings: " + ", ".join(result.warnings))
    return 1 if result.status == "blocked" else 0


def command_discord_capture_commentary_status(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    initialize_database(config.database_path)
    safe_print(build_discord_capture_status_text(config))
    return 0


def command_ingest_browser_captured_commentary(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    initialize_database(config.database_path)
    result = ingest_browser_captured_commentary(config, provider=args.provider)
    safe_print(
        "Browser-captured commentary ingestion complete: "
        f"imported={result.imported_count}, skipped={result.skipped_count}"
    )
    if result.warnings:
        safe_print("Warnings: " + ", ".join(result.warnings))
    return 0


def command_ingest_discord_captured_commentary(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    initialize_database(config.database_path)
    result = ingest_discord_captured_commentary(config, provider=args.provider)
    safe_print(
        "Discord commentary capture ingest complete: "
        f"imported={result.imported_count}, skipped={result.skipped_count}"
    )
    if result.warnings:
        safe_print("Warnings: " + ", ".join(result.warnings))
    return 0


def command_commentary_onboarding_plan(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    initialize_database(config.database_path)
    safe_print(build_commentary_onboarding_plan_text(config))
    return 0


def command_commentary_onboarding_status(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    initialize_database(config.database_path)
    safe_print(build_commentary_onboarding_status_text(config))
    return 0


def command_export_commentary_onboarding_template(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    initialize_database(config.database_path)
    result = export_commentary_onboarding_template(config, path=args.output)
    safe_print(
        "Commentary onboarding template exported: "
        f"{display_path(result.path, config.project_root)}"
    )
    safe_print(f"Rows: {result.row_count}")
    if result.warnings:
        safe_print("Warnings: " + ", ".join(result.warnings))
    return 0


def command_apply_commentary_onboarding(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    initialize_database(config.database_path)
    result = apply_commentary_onboarding(config, path=args.file, confirm=args.confirm)
    safe_print(
        "Commentary onboarding "
        + ("applied" if result.confirmed else "dry run")
        + f": {display_path(result.path, config.project_root)}"
    )
    safe_print(f"Assets changed: {result.asset_count}")
    safe_print(f"Aliases changed: {result.alias_count}")
    safe_print(f"Rows skipped: {result.skipped_count}")
    if result.warnings:
        safe_print("Warnings: " + ", ".join(result.warnings))
    return 0


def command_load_commentary_instrument_aliases(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    initialize_database(config.database_path)
    result = load_commentary_instrument_aliases(config, path=args.file)
    safe_print(
        "Commentary instrument aliases loaded: "
        f"{display_path(result.path, config.project_root)} rows={result.loaded_count}"
    )
    if result.warnings:
        safe_print("Warnings: " + ", ".join(result.warnings))
    return 0


def command_load_commentary_label_dispositions(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    initialize_database(config.database_path)
    result = load_commentary_label_dispositions(config, path=args.file)
    safe_print(
        "Commentary label dispositions loaded: "
        f"{display_path(result.path, config.project_root)} "
        f"rows={result.loaded_count} invalid={result.invalid_count}"
    )
    if result.warnings:
        safe_print("Warnings: " + ", ".join(result.warnings))
    return 0


def command_load_short_interest(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    initialize_database(config.database_path)
    path = args.file or config.short_interest_path
    try:
        result = load_short_interest_csv(config, path)
    except ValueError as error:
        safe_print(f"Short interest load failed: {error}")
        return 1
    safe_print(
        "Short interest loaded: "
        f"rows={result.row_count}, loaded={result.loaded_count}, "
        f"skipped={result.skipped_count} from "
        f"{display_path(result.path, config.project_root)}"
    )
    if result.tickers:
        safe_print("Tickers: " + ", ".join(result.tickers))
    if result.warnings:
        safe_print("Warnings: " + ", ".join(result.warnings))
    return 0


def command_export_short_interest_backfill(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    initialize_database(config.database_path)
    result = export_short_interest_backfill(config, directory=args.dir)
    safe_print(
        "Short interest backfill exported: "
        f"missing_tickers={len(result.missing_tickers)}, "
        f"templates={len(result.template_paths) + 1}, "
        f"dir={display_path(result.source_exports_dir, config.project_root)}"
    )
    safe_print(f"Backfill template: {display_path(result.backfill_path, config.project_root)}")
    if result.missing_tickers:
        safe_print("Missing tickers: " + ", ".join(result.missing_tickers))
    if result.etf_gated_tickers:
        safe_print("ETF-gated tickers: " + ", ".join(result.etf_gated_tickers))
    return 0


def command_short_interest_coverage_plan(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    initialize_database(config.database_path)
    safe_print(build_short_interest_coverage_plan_text(config, directory=args.dir))
    return 0


def command_short_interest_missing_coverage_plan(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    initialize_database(config.database_path)
    safe_print(build_short_interest_missing_coverage_plan_text(config, directory=args.dir))
    return 0


def command_short_interest_provider_diagnostics(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    initialize_database(config.database_path)
    safe_print(
        build_short_interest_provider_diagnostics_text(
            config,
            ticker=args.ticker,
            directory=args.dir,
        )
    )
    return 0


def command_resolve_short_interest_missing_sources(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    initialize_database(config.database_path)
    safe_print(
        build_short_interest_missing_source_resolution_text(
            config,
            ticker=args.ticker,
            provider=args.provider,
            use_cache=args.use_cache,
            force_refresh=args.force_refresh,
            directory=args.dir,
        )
    )
    return 0


def command_export_short_interest_missing_provider_template(
    args: argparse.Namespace,
) -> int:
    config = load_config(args.config)
    initialize_database(config.database_path)
    result = export_short_interest_missing_provider_template(config, directory=args.dir)
    safe_print(
        "Short interest missing-provider template exported: "
        f"missing_tickers={len(result.missing_tickers)}, "
        f"path={display_path(result.backfill_path, config.project_root)}"
    )
    if result.missing_tickers:
        safe_print("Missing tickers: " + ", ".join(result.missing_tickers))
    if result.etf_gated_tickers:
        safe_print("ETF-gated tickers: " + ", ".join(result.etf_gated_tickers))
    return 0


def command_short_interest_source_status(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    initialize_database(config.database_path)
    safe_print(
        build_short_interest_source_status_text(
            config,
            missing_only=args.missing_only,
        )
    )
    return 0


def command_validate_short_interest_backfill(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    initialize_database(config.database_path)
    safe_print(build_short_interest_backfill_validation_text(config, directory=args.dir))
    return 0


def command_preview_short_interest_import(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    initialize_database(config.database_path)
    safe_print(build_short_interest_import_preview_text(config, directory=args.dir))
    return 0


def command_import_short_interest_source_exports(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    initialize_database(config.database_path)
    result = import_short_interest_source_exports(config, directory=args.dir)
    safe_print(
        "Short interest source exports imported: "
        f"valid_rows={result.validation.valid_row_count}, "
        f"imported={result.imported_count}, "
        f"written={result.written_count}, "
        f"output={display_path(result.output_path, config.project_root)}"
    )
    safe_print(
        "Projected source-backed coverage: "
        f"{result.validation.projected_source_backed_count}/"
        f"{result.validation.active_equity_count}"
    )
    if result.validation.valid_tickers:
        safe_print("Imported tickers: " + ", ".join(result.validation.valid_tickers))
    if result.validation.invalid_rows:
        safe_print("Invalid rows:")
        for row in result.validation.invalid_rows:
            safe_print(
                f"- {display_path(row.path, config.project_root)}:{row.row_number} "
                f"{row.ticker or 'none'} "
                f"{', '.join(row.errors) if row.errors else 'invalid'}"
            )
    if result.warnings:
        safe_print("Warnings: " + ", ".join(result.warnings))
    return 1 if result.validation.invalid_row_count else 0


def command_apply_short_interest_provider_backfill(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    initialize_database(config.database_path)
    text, result = build_short_interest_provider_backfill_apply_text(
        config,
        directory=args.dir,
        confirm=args.confirm,
    )
    safe_print(text)
    if args.confirm and result.blocked_apply_reason is not None:
        return 1
    return 0


def command_fetch_short_interest_sources(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    initialize_database(config.database_path)
    result = fetch_short_interest_sources(
        config,
        provider=args.provider,
        ticker=args.ticker,
        use_cache=args.use_cache,
        force_refresh=args.force_refresh,
        max_tickers=args.max_tickers,
    )
    safe_print(
        "Short interest source fetch complete: "
        f"provider={result.provider}, requested={len(result.requested_tickers)}, "
        f"fetched={result.fetched_count}, normalized={result.normalized_count}, "
        f"written={result.written_count}, output={display_path(result.output_path, config.project_root)}, "
        f"live_requests={result.live_requests}, cache_hits={result.cache_hits}, "
        f"cache_misses={result.cache_misses}, cache_writes={result.cache_writes}"
    )
    if result.requested_tickers:
        safe_print("Requested tickers: " + ", ".join(result.requested_tickers))
    if result.tickers:
        safe_print("Normalized tickers: " + ", ".join(result.tickers))
    if result.warnings:
        safe_print("Warnings: " + ", ".join(result.warnings))
    return 0


def command_normalize_short_interest_provider_export(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    initialize_database(config.database_path)
    result = normalize_short_interest_provider_export(
        config,
        provider=args.provider,
        file_path=args.file,
    )
    safe_print(
        "Short interest provider export normalized: "
        f"provider={result.provider}, rows={result.source_row_count}, "
        f"normalized={result.normalized_count}, skipped={result.skipped_count}, "
        f"written={result.written_count}, output={display_path(result.output_path, config.project_root)}"
    )
    if result.tickers:
        safe_print("Normalized tickers: " + ", ".join(result.tickers))
    if result.warnings:
        safe_print("Warnings: " + ", ".join(result.warnings))
    return 0 if result.normalized_count or not result.warnings else 1


def command_short_interest_provider_status(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    initialize_database(config.database_path)
    safe_print(build_short_interest_provider_status_text(config))
    return 0


def command_fetch_news_catalyst_sources(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    initialize_database(config.database_path)
    provider_upgrade = getattr(args, "provider_upgrade", False)
    result = fetch_news_catalyst_sources(
        config,
        provider=args.provider,
        ticker=args.ticker,
        max_tickers=getattr(args, "max_tickers", None),
        force_refresh=getattr(args, "force_refresh", False),
        use_cache=getattr(args, "use_cache", None),
        coverage_plan=getattr(args, "coverage_plan", False) or provider_upgrade,
        coverage_mode=(
            "provider-upgrade"
            if provider_upgrade
            else getattr(args, "coverage_mode", "all")
        ),
    )
    safe_print(
        "News/catalyst source fetch complete: "
        f"provider={result.provider}, fetched={result.fetched_count}, "
        f"stored={result.stored_count}, numeric_stored={result.numeric_stored_count}, "
        f"skipped={result.skipped_count}, "
        f"live_requests={result.live_requests}, cache_hits={result.cache_hits}, "
        f"cache_misses={result.cache_misses}, cache_writes={result.cache_writes}"
    )
    if provider_upgrade:
        plan = news_catalyst_coverage_plan(
            config,
            max_tickers=getattr(args, "max_tickers", None),
            write_template=False,
            mode="provider-upgrade",
        )
        upgrade = news_catalyst_provider_upgrade_status(
            config,
            max_tickers=getattr(args, "max_tickers", None),
        )
        attempted_providers = (
            tuple(
                provider
                for provider in config.signals_news_catalyst_provider_order
                if provider in config.signals_news_catalyst_enabled_providers
                and provider != "source_export"
            )
            if args.provider == "all"
            else (args.provider,)
        )
        safe_print("Provider-upgrade queue mode: provider-upgrade")
        safe_print(
            "Provider-upgrade planned tickers: "
            f"{', '.join(plan.planned_tickers) if plan.planned_tickers else 'none'}"
        )
        safe_print(
            "Provider-upgrade attempted providers: "
            f"{', '.join(attempted_providers) if attempted_providers else 'none'}"
        )
        safe_print(
            "Provider-upgrade numeric rows stored: "
            f"{result.numeric_stored_count}"
        )
        safe_print(
            "Provider-upgrade blockers: "
            f"{', '.join(upgrade.provider_blockers) if upgrade.provider_blockers else 'none'}"
        )
    if result.tickers:
        safe_print("Tickers: " + ", ".join(result.tickers))
    if result.warnings:
        safe_print("Warnings: " + ", ".join(result.warnings))
    return 0


def command_news_catalyst_coverage_plan(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    initialize_database(config.database_path)
    safe_print(
        build_news_catalyst_coverage_plan_text(
            config,
            max_tickers=getattr(args, "max_tickers", None),
            mode=getattr(args, "mode", "all"),
        )
    )
    return 0


def command_compute_news_catalyst_text_backfill(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    initialize_database(config.database_path)
    result = compute_news_catalyst_text_backfill(config, ticker=args.ticker)
    safe_print(
        "News/catalyst text backfill complete: "
        f"derived={result.derived_count}, skipped={result.skipped_count}"
    )
    if result.tickers:
        safe_print("Tickers: " + ", ".join(result.tickers))
    if result.warnings:
        safe_print("Warnings: " + ", ".join(result.warnings))
    return 0


def command_export_news_catalyst_provider_backfill(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    initialize_database(config.database_path)
    result = export_news_catalyst_provider_backfill(config, output_dir=args.dir)
    safe_print(
        "News/catalyst provider-native backfill package exported: "
        f"tickers={result.ticker_count}"
    )
    safe_print(
        "Output directory: "
        f"{display_path(result.output_dir, config.project_root)}"
    )
    safe_print(
        "Template: "
        f"{display_path(result.template_path, config.project_root)}"
    )
    safe_print(
        "Runbook: "
        f"{display_path(result.readme_path, config.project_root)}"
    )
    if result.tickers:
        safe_print("Tickers: " + ", ".join(result.tickers))
    if result.warnings:
        safe_print("Warnings: " + ", ".join(result.warnings))
    return 0


def command_validate_news_catalyst_provider_backfill(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    initialize_database(config.database_path)
    safe_print(
        build_news_catalyst_provider_backfill_validation_text(
            config,
            directory=args.dir,
        )
    )
    return 0


def command_preview_news_catalyst_provider_upgrade(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    initialize_database(config.database_path)
    safe_print(
        build_news_catalyst_provider_upgrade_preview_text(
            config,
            directory=args.dir,
        )
    )
    return 0


def command_normalize_news_catalyst_provider_export(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    initialize_database(config.database_path)
    try:
        result = normalize_news_catalyst_provider_export(
            config,
            provider=args.provider,
            source_path=args.file,
        )
    except ValueError as error:
        safe_print(f"News/catalyst provider export normalization failed: {error}")
        return 1
    safe_print(
        "News/catalyst provider export normalized: "
        f"provider={result.provider}, input_rows={result.input_row_count}, "
        f"normalized={result.normalized_count}, skipped={result.skipped_count}"
    )
    safe_print(
        "Output file: "
        f"{display_path(result.output_path, config.project_root)}"
    )
    if result.tickers:
        safe_print("Tickers: " + ", ".join(result.tickers))
    if result.warnings:
        safe_print("Warnings: " + ", ".join(result.warnings))
    return 0


def command_news_catalyst_provider_backfill_status(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    initialize_database(config.database_path)
    safe_print(
        build_news_catalyst_provider_backfill_status_text(
            config,
            allow_partial=getattr(args, "allow_partial", False),
            directory=args.dir,
        )
    )
    return 0


def command_apply_news_catalyst_provider_backfill(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    initialize_database(config.database_path)
    result = apply_news_catalyst_provider_backfill(
        config,
        confirm=args.confirm,
        allow_partial=args.allow_partial,
        directory=args.dir,
    )
    safe_print(build_news_catalyst_provider_backfill_apply_text(result))
    if args.confirm and not result.applied:
        return 1
    return 0


def command_import_news_catalyst_source_exports(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    initialize_database(config.database_path)
    try:
        result = import_news_catalyst_source_exports(config, directory=args.dir)
    except ValueError as error:
        safe_print(f"News/catalyst source import failed: {error}")
        return 1
    safe_print(
        "News/catalyst source exports imported: "
        f"files={len(result.source_files)}, source_rows={result.source_row_count}, "
        f"imported={result.imported_count}, skipped={result.skipped_count}"
    )
    if result.tickers:
        safe_print("Tickers: " + ", ".join(result.tickers))
    if result.warnings:
        safe_print("Warnings: " + ", ".join(result.warnings))
    return 0


def command_aggregate_news_catalyst_sources(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    initialize_database(config.database_path)
    result = aggregate_news_catalyst_sources(config, ticker=args.ticker)
    safe_print(
        "News/catalyst sources aggregated: "
        f"aggregates={result.aggregate_count}, "
        f"final_csv_rows={result.written_row_count}"
    )
    if result.tickers:
        safe_print("Tickers: " + ", ".join(result.tickers))
    if result.warnings:
        safe_print("Warnings: " + ", ".join(result.warnings))
    return 0


def command_news_catalyst_provider_upgrade_status(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    initialize_database(config.database_path)
    safe_print(
        build_news_catalyst_provider_upgrade_status_text(
            config,
            max_tickers=getattr(args, "max_tickers", None),
        )
    )
    return 0


def command_test_news_catalyst_provider(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    initialize_database(config.database_path)
    safe_print(
        build_news_catalyst_provider_smoke_test_text(
            config,
            provider=args.provider,
            ticker=args.ticker,
        )
    )
    return 0


def command_news_catalyst_source_status(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    initialize_database(config.database_path)
    safe_print(
        build_news_catalyst_source_status_text(
            config,
            missing_only=getattr(args, "missing_only", False),
            provider_warnings_only=getattr(args, "provider_warnings", False),
            provider_upgrade_only=getattr(args, "provider_upgrade_only", False),
        )
    )
    return 0


def command_derive_analyst_revisions(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    initialize_database(config.database_path)
    try:
        result = derive_analyst_revisions_from_source_export(config, path=args.file)
    except ValueError as error:
        safe_print(f"Analyst revision derivation failed: {error}")
        return 1
    safe_print(
        "Analyst revisions derived: "
        f"source_rows={result.source_row_count}, "
        f"derived={result.derived_row_count}, "
        f"skipped={result.skipped_count}, "
        f"written_rows={result.written_row_count}"
    )
    safe_print(
        "Source export: "
        f"{display_path(result.source_path, config.project_root)}"
    )
    safe_print(
        "Derived revisions CSV: "
        f"{display_path(result.output_path, config.project_root)}"
    )
    if result.tickers:
        safe_print("Tickers: " + ", ".join(result.tickers))
    if result.warnings:
        safe_print("Warnings: " + ", ".join(result.warnings))
    return 0


def command_revision_source_status(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    initialize_database(config.database_path)
    safe_print(build_revision_source_status_text(config))
    return 0


def command_fetch_revision_sources(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    initialize_database(config.database_path)
    result = fetch_revision_sources(
        config,
        provider=args.provider,
        ticker=args.ticker,
    )
    safe_print(
        "Revision source fetch complete: "
        f"provider={result.provider}, fetched={result.fetched_count}, "
        f"stored={result.stored_count}, skipped={result.skipped_count}"
    )
    if result.tickers:
        safe_print("Tickers: " + ", ".join(result.tickers))
    if result.warnings:
        safe_print("Warnings: " + ", ".join(result.warnings))
    return 0


def command_import_revision_source_exports(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    initialize_database(config.database_path)
    try:
        result = import_revision_source_exports(config, directory=args.dir)
    except ValueError as error:
        safe_print(f"Analyst revision source import failed: {error}")
        return 1
    safe_print(
        "Revision source exports imported: "
        f"files={len(result.source_files)}, source_rows={result.source_row_count}, "
        f"imported={result.imported_count}, skipped={result.skipped_count}"
    )
    if result.tickers:
        safe_print("Tickers: " + ", ".join(result.tickers))
    if result.warnings:
        safe_print("Warnings: " + ", ".join(result.warnings))
    return 0


def command_aggregate_revision_sources(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    initialize_database(config.database_path)
    result = aggregate_revision_sources(config, ticker=args.ticker)
    safe_print(
        "Revision sources aggregated: "
        f"aggregates={result.aggregate_count}, "
        f"final_csv_rows={result.written_row_count}"
    )
    if result.tickers:
        safe_print("Tickers: " + ", ".join(result.tickers))
    if result.warnings:
        safe_print("Warnings: " + ", ".join(result.warnings))
    return 0


def command_revision_provider_status(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    initialize_database(config.database_path)
    safe_print(build_revision_provider_status_text(config))
    return 0


def command_seed_fundamentals(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    initialize_database(config.database_path)
    try:
        result = seed_sec_fundamentals(
            config,
            ticker=args.ticker,
            years=args.years,
            refresh_cache=args.refresh_cache,
        )
    except ValueError as error:
        safe_print(f"SEC fundamentals seed failed: {error}")
        return 1

    safe_print(
        "SEC fundamentals seeded: "
        f"written={result.written_count}, loaded={result.loaded_count}, "
        f"csv={display_path(result.csv_path, config.project_root)}"
    )
    if result.tickers:
        safe_print("Tickers: " + ", ".join(result.tickers))
    if result.skipped:
        safe_print("Skipped: " + ", ".join(result.skipped))
    return 0


def command_etf_status(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    initialize_database(config.database_path)
    statuses = etf_statuses(config.database_path)
    if not statuses:
        safe_print("No active ETF assets found.")
        return 0

    safe_print(
        "Ticker | Price | NAV | Premium/Discount | PD Z-Score | "
        "NAV Date | Holdings Date | Holdings | Target Ready | Warnings"
    )
    for status in statuses:
        safe_print(
            " | ".join(
                (
                    status.ticker,
                    f"{status.current_price:.4f}"
                    if status.current_price is not None
                    else "",
                    f"{status.nav_per_share:.4f}"
                    if status.nav_per_share is not None
                    else "",
                    f"{status.premium_discount:.4%}"
                    if status.premium_discount is not None
                    else "",
                    f"{status.premium_discount_zscore:.2f}"
                    if status.premium_discount_zscore is not None
                    else "",
                    status.latest_nav_date or "",
                    status.latest_holdings_date or "",
                    str(status.holdings_count or 0),
                    str(status.target_ready),
                    status.data_warnings or "",
                )
            )
        )
    return 0


def command_compute_targets(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    initialize_database(config.database_path)
    result = compute_targets(config, ticker=args.ticker)
    safe_print(
        "Target computation complete: "
        f"computed={result.computed_count}, "
        f"skipped={result.skipped_count}, "
        f"with_warnings={result.warning_count}"
    )
    for ticker_result in result.results:
        warnings = (
            ", ".join(ticker_result.warnings) if ticker_result.warnings else "none"
        )
        target = (
            f"{ticker_result.base_target:.4f}"
            if ticker_result.base_target is not None
            else "none"
        )
        safe_print(
            f"{ticker_result.ticker}: status={ticker_result.status}, "
            f"target={target}, methods={ticker_result.method_count}, "
            f"warnings={warnings}"
        )
    return 0


def command_valuation_status(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    initialize_database(config.database_path)
    statuses = valuation_statuses(config.database_path)
    if not statuses:
        safe_print("No active assets found.")
        return 0

    safe_print(
        "Ticker | Current Price | Base Target | Target Low | Target High | "
        "Valuation Gap | Confidence | Methods | Warnings"
    )
    for status in statuses:
        safe_print(
            " | ".join(
                (
                    status.ticker,
                    f"{status.current_price:.4f}"
                    if status.current_price is not None
                    else "",
                    f"{status.base_target:.4f}"
                    if status.base_target is not None
                    else "",
                    f"{status.target_low:.4f}"
                    if status.target_low is not None
                    else "",
                    f"{status.target_high:.4f}"
                    if status.target_high is not None
                    else "",
                    f"{status.valuation_gap:.4f}"
                    if status.valuation_gap is not None
                    else "",
                    f"{status.valuation_confidence:.1f}"
                    if status.valuation_confidence is not None
                    else "",
                    str(status.method_count or 0),
                    status.data_warnings or "",
                )
            )
        )
    return 0


def command_compute_scores(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    initialize_database(config.database_path)
    result = compute_scores(
        config,
        ticker=args.ticker,
        asset_type=args.asset_type,
    )
    safe_print(
        "Score computation complete: "
        f"computed={result.computed_count}, "
        f"skipped={result.skipped_count}, "
        f"with_warnings={result.warning_count}"
    )
    for ticker_result in result.results:
        warnings = (
            ", ".join(ticker_result.warnings)
            if ticker_result.warnings
            else "none"
        )
        opportunity = (
            f"{ticker_result.opportunity_score:.2f}"
            if ticker_result.opportunity_score is not None
            else "none"
        )
        safe_print(
            f"{ticker_result.ticker}: status={ticker_result.status}, "
            f"type={ticker_result.asset_type}, opportunity={opportunity}, "
            f"model={ticker_result.score_model or 'none'}, warnings={warnings}"
        )
    return 0


def command_compute_revision_signals(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    initialize_database(config.database_path)
    result = compute_revision_signals(config, ticker=args.ticker)
    safe_print(
        "Revision signal computation complete: "
        f"computed={result.computed_count}, "
        f"skipped={result.skipped_count}, "
        f"with_warnings={result.warning_count}, "
        f"loaded_inputs={result.load_result.input_signal_count}"
    )
    for ticker_result in result.results:
        warnings = (
            ", ".join(ticker_result.warnings)
            if ticker_result.warnings
            else "none"
        )
        score = (
            f"{ticker_result.composite_score:.2f}"
            if ticker_result.composite_score is not None
            else "none"
        )
        safe_print(
            f"{ticker_result.ticker}: status={ticker_result.status}, "
            f"type={ticker_result.asset_type}, composite={score}, warnings={warnings}"
        )
    return 0


def command_compute_news_catalyst_signals(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    initialize_database(config.database_path)
    result = compute_news_catalyst_signals(config, ticker=args.ticker)
    safe_print(
        "News/catalyst signal computation complete: "
        f"computed={result.computed_count}, "
        f"skipped={result.skipped_count}, "
        f"with_warnings={result.warning_count}, "
        f"loaded_inputs={result.load_result.input_signal_count}"
    )
    for ticker_result in result.results:
        warnings = ", ".join(ticker_result.warnings) if ticker_result.warnings else "none"
        score = (
            f"{ticker_result.composite_score:.2f}"
            if ticker_result.composite_score is not None
            else "none"
        )
        safe_print(
            f"{ticker_result.ticker}: status={ticker_result.status}, "
            f"type={ticker_result.asset_type}, composite={score}, warnings={warnings}"
        )
    return 0


def command_parse_trader_commentary_claims(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    initialize_database(config.database_path)
    result = parse_trader_commentary_claims(
        config,
        commentary_id=args.commentary_id,
        ticker=args.ticker,
    )
    safe_print(
        "Trader commentary parsing complete: "
        f"parsed={result.parsed_count}, skipped={result.skipped_count}"
    )
    if result.warnings:
        safe_print("Warnings: " + ", ".join(result.warnings))
    return 0


def command_validate_trader_commentary_claims(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    initialize_database(config.database_path)
    result = validate_trader_commentary_claims(config, ticker=args.ticker)
    safe_print(
        "Trader commentary claim validation complete: "
        f"updated={result.updated_count}, skipped={result.skipped_count}, "
        f"with_warnings={len(result.warnings)}"
    )
    for item in result.results:
        warnings = ", ".join(item.warnings) if item.warnings else "none"
        safe_print(
            f"{item.ticker or 'unmapped'}: status={item.status}, "
            f"claim={item.claim_type}, outcome={item.outcome_status or 'none'}, "
            f"warnings={warnings}"
        )
    return 0


def command_fetch_insider_transactions(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    initialize_database(config.database_path)
    result = fetch_insider_transactions(
        config,
        ticker=args.ticker,
        refresh_cache=getattr(args, "refresh_cache", False)
        or getattr(args, "force_refresh", False),
        max_tickers=getattr(args, "max_tickers", None),
        use_cache=getattr(args, "use_cache", None),
    )
    safe_print(
        "Insider transaction fetch complete: "
        f"fetched_filings={result.fetched_count}, "
        f"stored_rows={result.stored_count}, skipped={result.skipped_count}"
    )
    if result.tickers:
        safe_print("Tickers: " + ", ".join(result.tickers))
    if result.warnings:
        safe_print("Warnings: " + ", ".join(result.warnings))
    return 0


def command_insider_source_status(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    initialize_database(config.database_path)
    safe_print(build_insider_source_status_text(config, verbose=getattr(args, "verbose", False)))
    return 0


def command_compute_insider_signals(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    initialize_database(config.database_path)
    result = compute_insider_signals(config, ticker=args.ticker)
    safe_print(
        "Insider activity signal computation complete: "
        f"computed={result.computed_count}, "
        f"skipped={result.skipped_count}, "
        f"with_warnings={result.warning_count}"
    )
    for ticker_result in result.results:
        warnings = ", ".join(ticker_result.warnings) if ticker_result.warnings else "none"
        score = (
            f"{ticker_result.composite_score:.2f}"
            if ticker_result.composite_score is not None
            else "none"
        )
        safe_print(
            f"{ticker_result.ticker}: status={ticker_result.status}, "
            f"type={ticker_result.asset_type}, composite={score}, warnings={warnings}"
        )
    return 0


def command_compute_short_interest_signals(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    initialize_database(config.database_path)
    result = compute_short_interest_signals(config, ticker=args.ticker)
    loaded_inputs = result.load_result.loaded_count if result.load_result else 0
    safe_print(
        "Short interest signal computation complete: "
        f"computed={result.computed_count}, "
        f"skipped={result.skipped_count}, "
        f"with_warnings={result.warning_count}, "
        f"loaded_sources={loaded_inputs}"
    )
    for ticker_result in result.results:
        warnings = ", ".join(ticker_result.warnings) if ticker_result.warnings else "none"
        score = (
            f"{ticker_result.composite_score:.2f}"
            if ticker_result.composite_score is not None
            else "none"
        )
        safe_print(
            f"{ticker_result.ticker}: status={ticker_result.status}, "
            f"type={ticker_result.asset_type}, composite={score}, warnings={warnings}"
        )
    return 0


def command_signal_status(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    initialize_database(config.database_path)
    statuses = signal_statuses(config.database_path)
    if not statuses:
        safe_print("No active assets found.")
        return 0

    safe_print(
        "Ticker | Type | Signal Date | Composite | Direction | Count | "
        "Confidence | Model | Warnings"
    )
    for status in statuses:
        safe_print(
            " | ".join(
                (
                    status.ticker,
                    status.asset_type or "",
                    status.latest_signal_date or "",
                    f"{status.composite_score:.2f}"
                    if status.composite_score is not None
                    else "",
                    status.composite_direction or "",
                    str(status.signal_count),
                    f"{status.confidence:.2f}" if status.confidence is not None else "",
                    status.model_version or "",
                    status.data_warnings or "",
                )
            )
        )
    return 0


def command_news_catalyst_status(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    initialize_database(config.database_path)
    statuses = news_catalyst_statuses(config)
    if not statuses:
        safe_print("No active assets found.")
        return 0

    safe_print(
        "Ticker | Type | Signal Date | Composite | Direction | Count | "
        "Confidence | Validation | Model | Warnings"
    )
    for status in statuses:
        safe_print(
            " | ".join(
                (
                    status.ticker,
                    status.asset_type or "",
                    status.latest_signal_date or "",
                    f"{status.composite_score:.2f}"
                    if status.composite_score is not None
                    else "",
                    status.composite_direction or "",
                    str(status.signal_count),
                    f"{status.confidence:.2f}" if status.confidence is not None else "",
                    (
                        f"{status.validation_status}@{status.validation_date}"
                        if status.validation_status and status.validation_date
                        else ""
                    ),
                    status.model_version or "",
                    status.data_warnings or "",
                )
            )
        )
    return 0


def command_insider_status(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    initialize_database(config.database_path)
    statuses = insider_statuses(config)
    if not statuses:
        safe_print("No active assets found.")
        return 0

    safe_print(
        "Ticker | Type | Signal Date | Composite | Direction | Count | "
        "Confidence | Validation | Model | Warnings"
    )
    for status in statuses:
        safe_print(
            " | ".join(
                (
                    status.ticker,
                    status.asset_type or "",
                    status.latest_signal_date or "",
                    f"{status.composite_score:.2f}"
                    if status.composite_score is not None
                    else "",
                    status.composite_direction or "",
                    str(status.signal_count),
                    f"{status.confidence:.2f}" if status.confidence is not None else "",
                    (
                        f"{status.validation_status}@{status.validation_date}"
                        if status.validation_status and status.validation_date
                        else ""
                    ),
                    status.model_version or "",
                    status.data_warnings or "",
                )
            )
        )
    return 0


def command_short_interest_status(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    initialize_database(config.database_path)
    safe_print(build_short_interest_status_text(config))
    return 0


def command_trader_commentary_status(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    initialize_database(config.database_path)
    safe_print(build_trader_commentary_status_text(config))
    return 0


def command_trader_commentary_parse_review(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    initialize_database(config.database_path)
    safe_print(build_trader_commentary_parse_review(config))
    return 0


def command_validate_revision_signals(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    initialize_database(config.database_path)
    result = validate_revision_signals(config, ticker=args.ticker)
    safe_print(
        "Revision signal validation complete: "
        f"updated={result.updated_count}, "
        f"skipped={result.skipped_count}, "
        f"with_warnings={result.warning_count}"
    )
    for item in result.results:
        warnings = ", ".join(item.warnings) if item.warnings else "none"
        safe_print(
            f"{item.ticker}: status={item.status}, "
            f"signal={item.signal_name}, "
            f"outcome={item.outcome_status or 'none'}, "
            f"warnings={warnings}"
        )
    return 0


def command_validate_news_catalyst_signals(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    initialize_database(config.database_path)
    result = validate_news_catalyst_signals(config, ticker=args.ticker)
    safe_print(
        "News/catalyst signal validation complete: "
        f"updated={result.updated_count}, "
        f"skipped={result.skipped_count}, "
        f"with_warnings={result.warning_count}"
    )
    for item in result.results:
        warnings = ", ".join(item.warnings) if item.warnings else "none"
        safe_print(
            f"{item.ticker}: status={item.status}, "
            f"signal={item.signal_name}, "
            f"outcome={item.outcome_status or 'none'}, "
            f"warnings={warnings}"
        )
    return 0


def command_validate_insider_signals(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    initialize_database(config.database_path)
    result = validate_insider_signals(config, ticker=args.ticker)
    safe_print(
        "Insider activity signal validation complete: "
        f"updated={result.updated_count}, "
        f"skipped={result.skipped_count}, "
        f"with_warnings={result.warning_count}"
    )
    for item in result.results:
        warnings = ", ".join(item.warnings) if item.warnings else "none"
        safe_print(
            f"{item.ticker}: status={item.status}, "
            f"signal={item.signal_name}, "
            f"outcome={item.outcome_status or 'none'}, "
            f"warnings={warnings}"
        )
    return 0


def command_validate_short_interest_signals(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    initialize_database(config.database_path)
    result = validate_short_interest_signals(config, ticker=args.ticker)
    safe_print(
        "Short interest signal validation complete: "
        f"updated={result.updated_count}, "
        f"skipped={result.skipped_count}, "
        f"with_warnings={result.warning_count}"
    )
    for item in result.results:
        warnings = ", ".join(item.warnings) if item.warnings else "none"
        safe_print(
            f"{item.ticker}: status={item.status}, "
            f"signal={item.signal_name}, "
            f"outcome={item.outcome_status or 'none'}, "
            f"warnings={warnings}"
        )
    return 0


def command_revision_validation_report(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    initialize_database(config.database_path)
    safe_print(build_revision_validation_report(config))
    return 0


def command_news_catalyst_validation_report(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    initialize_database(config.database_path)
    safe_print(build_news_catalyst_validation_report(config))
    return 0


def command_trader_commentary_validation_report(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    initialize_database(config.database_path)
    safe_print(build_trader_commentary_validation_report(config))
    return 0


def command_insider_validation_report(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    initialize_database(config.database_path)
    safe_print(build_insider_validation_report(config))
    return 0


def command_short_interest_validation_report(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    initialize_database(config.database_path)
    safe_print(build_short_interest_validation_report(config))
    return 0


def command_revision_evidence_report(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    initialize_database(config.database_path)
    safe_print(build_revision_evidence_report(config))
    return 0


def command_score_status(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    initialize_database(config.database_path)
    statuses = score_statuses(config.database_path)
    if not statuses:
        safe_print("No active assets found.")
        return 0

    safe_print(
        "Ticker | Type | Current Price | Score Date | Opportunity | Expected Value | "
        "Valuation | Momentum | Risk | Liquidity | Confidence | Model | Threshold | Warnings"
    )
    for status in statuses:
        safe_print(
            " | ".join(
                (
                    status.ticker,
                    status.asset_type or "",
                    f"{status.current_price:.4f}"
                    if status.current_price is not None
                    else "",
                    status.score_date or "",
                    f"{status.opportunity_score:.2f}"
                    if status.opportunity_score is not None
                    else "",
                    f"{status.expected_value_score:.2f}"
                    if status.expected_value_score is not None
                    else "",
                    f"{status.valuation_gap_score:.2f}"
                    if status.valuation_gap_score is not None
                    else "",
                    f"{status.momentum_score:.2f}"
                    if status.momentum_score is not None
                    else "",
                    f"{status.risk_score:.2f}"
                    if status.risk_score is not None
                    else "",
                    f"{status.liquidity_score:.2f}"
                    if status.liquidity_score is not None
                    else "",
                    f"{status.confidence_score:.2f}"
                    if status.confidence_score is not None
                    else "",
                    status.score_model or "",
                    status.threshold_set or "",
                    status.data_warnings or "",
                )
            )
        )
    return 0


def command_compute_alerts(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    initialize_database(config.database_path)
    result = compute_alerts(
        config,
        ticker=args.ticker,
        asset_type=args.asset_type,
    )
    safe_print(
        "Alert computation complete: "
        f"evaluated={result.evaluated_count}, "
        f"stored={result.stored_count}, "
        f"alerts={result.alert_count}, "
        f"skipped={result.skipped_count}, "
        f"with_warnings={result.warning_count}"
    )
    for ticker_result in result.results:
        warnings = (
            ", ".join(ticker_result.warnings)
            if ticker_result.warnings
            else "none"
        )
        safe_print(
            f"{ticker_result.ticker}: status={ticker_result.status}, "
            f"type={ticker_result.asset_type}, "
            f"alert={ticker_result.alert_type or 'none'}, "
            f"priority={ticker_result.priority or 'none'}, "
            f"warnings={warnings}"
        )
    return 0


def command_alert_status(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    initialize_database(config.database_path)
    statuses = alert_statuses(config.database_path)
    if not statuses:
        safe_print("No active assets found.")
        return 0

    safe_print(
        "Ticker | Type | Alert | Priority | Status | Current Price | Target Low | "
        "Base Target | Target High | Gap | Opportunity | Expected Value | "
        "Confidence | Risk | Data Quality | Model | Reasons | Risks | Warnings"
    )
    for status in statuses:
        alert_type = status.alert_type or (
            "skipped" if status.data_warnings else "no_alert"
        )
        safe_print(
            " | ".join(
                (
                    status.ticker,
                    status.asset_type or "",
                    alert_type,
                    status.priority or "",
                    status.status or "",
                    f"{status.current_price:.4f}"
                    if status.current_price is not None
                    else "",
                    f"{status.target_low:.4f}"
                    if status.target_low is not None
                    else "",
                    f"{status.base_target:.4f}"
                    if status.base_target is not None
                    else "",
                    f"{status.target_high:.4f}"
                    if status.target_high is not None
                    else "",
                    f"{status.valuation_gap:.4f}"
                    if status.valuation_gap is not None
                    else "",
                    f"{status.opportunity_score:.2f}"
                    if status.opportunity_score is not None
                    else "",
                    f"{status.expected_value_score:.2f}"
                    if status.expected_value_score is not None
                    else "",
                    f"{status.confidence_score:.2f}"
                    if status.confidence_score is not None
                    else "",
                    f"{status.risk_score:.2f}"
                    if status.risk_score is not None
                    else "",
                    f"{status.data_quality_score:.2f}"
                    if status.data_quality_score is not None
                    else "",
                    status.alert_model or "",
                    status.reason_codes or "",
                    status.risk_codes or "",
                    status.data_warnings or "",
                )
            )
        )
    return 0


def command_update_alert_outcomes(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    initialize_database(config.database_path)
    result = update_alert_outcomes(
        config,
        ticker=args.ticker,
        asset_type=getattr(args, "asset_type", "all"),
    )
    safe_print(
        "Alert outcomes updated: "
        f"updated={result.updated_count}, "
        f"skipped={result.skipped_count}, "
        f"with_warnings={result.warning_count}"
    )
    for item in result.results:
        warnings = ", ".join(item.warnings) if item.warnings else "none"
        safe_print(
            f"{item.ticker}: status={item.status}, "
            f"alert={item.alert_type}, "
            f"outcome={item.outcome_status or 'none'}, "
            f"rows={item.rows_updated}, "
            f"warnings={warnings}"
        )
    return 0


def command_outcome_status(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    initialize_database(config.database_path)
    statuses = outcome_statuses(config.database_path)
    if not statuses:
        safe_print("No alert outcomes found.")
        return 0

    safe_print(
        "Ticker | Type | Alert | Outcome | Entry Date | Entry | Latest Date | Latest | "
        "5d | 20d | 60d | 120d | Hit Target | Hit Invalidation | MFE | MAE | "
        "Completed | Pending | Warnings"
    )
    for status in statuses:
        safe_print(
            " | ".join(
                (
                    status.ticker,
                    status.asset_type or "",
                    status.alert_type or "",
                    status.outcome_status or "",
                    status.entry_price_date or "",
                    f"{status.entry_price:.4f}"
                    if status.entry_price is not None
                    else "",
                    status.latest_price_date or "",
                    f"{status.latest_price:.4f}"
                    if status.latest_price is not None
                    else "",
                    f"{status.return_5d:.4f}"
                    if status.return_5d is not None
                    else "",
                    f"{status.return_20d:.4f}"
                    if status.return_20d is not None
                    else "",
                    f"{status.return_60d:.4f}"
                    if status.return_60d is not None
                    else "",
                    f"{status.return_120d:.4f}"
                    if status.return_120d is not None
                    else "",
                    ""
                    if status.hit_target_flag is None
                    else str(bool(status.hit_target_flag)),
                    ""
                    if status.hit_invalidation_flag is None
                    else str(bool(status.hit_invalidation_flag)),
                    f"{status.max_favorable_excursion:.4f}"
                    if status.max_favorable_excursion is not None
                    else "",
                    f"{status.max_adverse_excursion:.4f}"
                    if status.max_adverse_excursion is not None
                    else "",
                    status.completed_horizons or "",
                    status.pending_horizons or "",
                    status.data_warnings or "",
                )
            )
        )
    return 0


def command_validation_report(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    initialize_database(config.database_path)
    safe_print(build_validation_report(config))
    return 0


def command_load_portfolio(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    initialize_database(config.database_path)
    result = load_portfolio_csvs(
        config,
        positions_path=args.positions_file or config.portfolio_positions_path,
        cash_path=args.cash_file or config.portfolio_cash_path,
    )
    safe_print(
        "Portfolio loaded: "
        f"positions={result.position_count} cash={result.cash_count} "
        f"positions_file={display_path(result.positions_path, config.project_root)} "
        f"cash_file={display_path(result.cash_path, config.project_root)}"
    )
    if result.tickers:
        safe_print("Tickers: " + ", ".join(result.tickers))
    if result.warnings:
        safe_print("Warnings: " + ", ".join(result.warnings))
    return 0


def command_compute_portfolio_context(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    initialize_database(config.database_path)
    result = compute_portfolio_context(config, ticker=args.ticker)
    safe_print(f"Portfolio reviews computed: {result.computed_count}")
    for item in result.results:
        warnings = ",".join(item.warnings) if item.warnings else "none"
        safe_print(
            f"{item.ticker}: status={item.status}, "
            f"category={item.review_category or 'none'}, warnings={warnings}"
        )
    return 0 if all(item.status != "error" for item in result.results) else 1


def command_portfolio_status(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    initialize_database(config.database_path)
    statuses = portfolio_statuses(config.database_path)
    if not statuses:
        safe_print("No portfolio reviews yet.")
        return 0

    safe_print(
        "Ticker | Type | Held | Quantity | Position Value | Weight | Sector | "
        "Sector Weight | Cash Available | Category | Max Add | Guidance | Warnings"
    )
    for status in statuses:
        safe_print(
            " | ".join(
                (
                    status.ticker,
                    status.asset_type or "",
                    str(bool(status.held_flag)) if status.held_flag is not None else "",
                    f"{status.quantity:.4f}" if status.quantity is not None else "",
                    f"{status.position_value:.2f}" if status.position_value is not None else "",
                    f"{status.position_weight:.4f}" if status.position_weight is not None else "",
                    status.sector or "",
                    f"{status.sector_weight:.4f}" if status.sector_weight is not None else "",
                    f"{status.cash_available:.2f}" if status.cash_available is not None else "",
                    status.review_category or "",
                    f"{status.max_add_value:.2f}" if status.max_add_value is not None else "",
                    status.sizing_guidance or "",
                    status.data_warnings or "",
                )
            )
        )
    return 0


def _print_readiness_rows(statuses: tuple[object, ...] | list[object]) -> None:
    safe_print(
        "Ticker | Type | Price | Feature | Fundamentals | Estimates | ETF NAV | "
        "ETF Holdings | Target | Score | Pre-Alert Ready | Warnings"
    )
    for status in statuses:
        safe_print(
            " | ".join(
                (
                    status.ticker,
                    status.asset_type,
                    str(status.price_ready),
                    str(status.feature_ready),
                    str(status.fundamentals_ready),
                    str(status.estimates_ready),
                    str(status.etf_nav_ready),
                    str(status.etf_holdings_ready),
                    str(status.target_ready),
                    str(status.score_ready),
                    str(status.phase4_ready),
                    ", ".join(status.warnings),
                )
            )
        )


def command_verify_universe(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    initialize_database(config.database_path)
    result = verify_universe(config, intraday=args.intraday)
    if not result.statuses:
        safe_print("No active assets found.")
        return 0
    _print_readiness_rows(result.statuses)
    safe_print(
        f"Readiness summary: ready={result.ready_count}/{len(result.statuses)}, "
        f"warnings={result.warning_count}"
    )
    return 0


def command_verify_ticker(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    initialize_database(config.database_path)
    status = verify_ticker(config, args.ticker, intraday=args.intraday)
    _print_readiness_rows((status,))
    return 0


def _print_pipeline_result(result: object) -> None:
    safe_print(
        f"Pipeline run {result.pipeline_run_id}: "
        f"type={result.run_type}, status={result.status}"
    )
    for step in result.steps:
        warnings = ", ".join(step.warnings) if step.warnings else "none"
        safe_print(
            f"{step.step_name}: status={step.status}, "
            f"rows={step.rows_loaded}, warnings={warnings}"
        )
    safe_print(result.summary)


def command_refresh_data(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    initialize_database(config.database_path)
    result = run_refresh_data(
        config,
        ticker=args.ticker,
        daily=args.daily,
        include_quotes=args.include_quotes,
        skip_ibkr=args.skip_ibkr,
    )
    _print_pipeline_result(result)
    return 0 if result.status != "error" else 1


def command_probe_market(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    initialize_database(config.database_path)
    try:
        result = run_probe_market(config, source=args.source, ticker=args.ticker)
    except ValueError as error:
        safe_print(f"Market probe failed: {error}")
        return 1
    _print_pipeline_result(result)
    return 0 if result.status != "error" else 1


def command_ibkr_status(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    result = check_ibkr_status(config, paper=not args.live)
    safe_print("IBKR status")
    safe_print(f"Available: {result.available}")
    safe_print(f"Connected: {result.connected}")
    safe_print(f"Host: {result.host}")
    safe_print(f"Port: {result.port}")
    safe_print(f"Managed account count: {result.managed_account_count}")
    safe_print(f"Server time: {result.server_time or 'none'}")
    safe_print(
        "Warnings: " + (", ".join(result.warnings) if result.warnings else "none")
    )
    return 0 if result.connected else 1


def command_ibkr_probe(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    initialize_database(config.database_path)
    result = probe_ibkr_ticker(config, args.ticker)
    safe_print(
        f"{result.ticker}: status={result.status}, "
        f"contract={result.contract_found}, historical_rows={result.historical_rows}, "
        f"quote={result.quote_loaded}, etf_nav={result.etf_nav_loaded}"
    )
    safe_print(
        "Warnings: " + (", ".join(result.warnings) if result.warnings else "none")
    )
    return 0 if result.status != "error" else 1


def command_update_quotes(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    initialize_database(config.database_path)
    if args.source != "ibkr":
        safe_print(f"Quote update failed: unsupported source {args.source}")
        return 1
    result = update_quote_snapshots(config, ticker=args.ticker)
    safe_print(
        f"Quote update complete: loaded={result.loaded_count}, "
        f"warnings={result.warning_count}"
    )
    for item in result.results:
        safe_print(
            f"{item.ticker}: status={item.status}, rows={item.rows_loaded}, "
            f"market_data_type={item.market_data_type or 'none'}, "
            f"warnings={', '.join(item.warnings) if item.warnings else 'none'}"
        )
    return 0


def command_update_etf_navs(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    initialize_database(config.database_path)
    source = args.source
    if source in {"csv", "auto"}:
        ensure_etf_csv_headers(config.etf_navs_path, config.etf_holdings_path)
    if source == "csv":
        result = load_etf_navs_csv(config.database_path, config.etf_navs_path)
        safe_print(f"ETF NAV CSV update complete: loaded={result.loaded_count}")
        return 0
    if source == "ibkr":
        result = update_etf_navs_from_ibkr(config, ticker=args.ticker)
        _print_etf_nav_provider_result(result)
        return 0
    if source == "auto":
        ibkr_result = update_etf_navs_from_ibkr(config, ticker=args.ticker)
        if ibkr_result.loaded_count > 0:
            _print_etf_nav_provider_result(ibkr_result)
            return 0
        csv_result = load_etf_navs_csv(config.database_path, config.etf_navs_path)
        refresh_etf_features(config.database_path, csv_result.tickers)
        _print_etf_nav_provider_result(ibkr_result)
        safe_print(f"ETF NAV CSV fallback complete: loaded={csv_result.loaded_count}")
        return 0
    safe_print(f"ETF NAV update failed: unsupported source {source}")
    return 1


def _print_etf_nav_provider_result(result: object) -> None:
    safe_print(
        f"ETF NAV provider update complete: loaded={result.loaded_count}, "
        f"warnings={result.warning_count}"
    )
    for item in result.results:
        nav = f"{item.nav_per_share:.4f}" if item.nav_per_share is not None else "none"
        safe_print(
            f"{item.ticker}: status={item.status}, rows={item.rows_loaded}, "
            f"nav={nav}, warnings={', '.join(item.warnings) if item.warnings else 'none'}"
        )


def _fmt(value: float | None, digits: int = 2) -> str:
    return f"{value:.{digits}f}" if value is not None else ""


def command_range_monitor(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    if args.source != "ibkr":
        safe_print(f"Unsupported range monitor source: {args.source}")
        return 1

    quote_result = update_quote_snapshots(config, ticker=args.ticker)
    if quote_result.warning_count:
        safe_print(
            "Quote refresh warnings: "
            + "; ".join(
                f"{item.ticker}:{','.join(item.warnings)}"
                for item in quote_result.results
                if item.warnings
            )
        )
    result = compute_range_snapshots(config, ticker=args.ticker)
    safe_print(
        f"Range monitor complete: updated={result.updated_count}, "
        f"notifications={result.notification_count}, warnings={result.warning_count}"
    )
    safe_print("Ticker | State | Previous | Price | Notification | Warnings")
    for item in result.results:
        safe_print(
            f"{item.ticker} | {item.range_state} | "
            f"{item.previous_range_state or ''} | {_fmt(item.current_price)} | "
            f"{item.notification_created} | {', '.join(item.warnings) if item.warnings else ''}"
        )
    return 0


def command_range_status(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    statuses = range_statuses(config.database_path, ticker=args.ticker)
    safe_print(
        "Ticker | Type | Timestamp | State | Price | Buy/Add | Hold | "
        "Trim/Sell | Technical | Regime | Quote | Warnings"
    )
    for status in statuses:
        buy_add = "/".join(
            part
            for part in (
                _fmt(status.strong_buy_below),
                _fmt(status.starter_buy_below),
                _fmt(status.add_below),
            )
            if part
        )
        hold = "/".join(
            part for part in (_fmt(status.hold_low), _fmt(status.hold_high)) if part
        )
        trim_sell = "/".join(
            part
            for part in (
                _fmt(status.trim_above),
                _fmt(status.reduce_or_sell_above),
                _fmt(status.nav_premium_warning_above),
            )
            if part
        )
        technical = "/".join(
            part
            for part in (
                status.moving_average_state or "",
                status.price_location_state or "",
            )
            if part
        )
        regime = "/".join(
            part
            for part in (
                status.regime_state or "",
                _fmt(status.relative_strength, 4),
            )
            if part
        )
        safe_print(
            f"{status.ticker} | {status.asset_type or ''} | "
            f"{status.snapshot_timestamp or 'none'} | {status.range_state} | "
            f"{_fmt(status.current_price)} | {buy_add} | {hold} | {trim_sell} | "
            f"{technical} | {regime} | {status.quote_timestamp or 'none'} | "
            f"{status.data_warnings or ''}"
        )
    return 0


def command_compute_technical_signals(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    result = compute_technical_signals(config, ticker=args.ticker)
    safe_print(
        "Technical signals computed: "
        f"{result.computed_count}; warnings={result.warning_count}"
    )
    for item in result.results:
        safe_print(
            f"{item.ticker} | {item.trend_state or ''} | "
            f"{item.price_location_state or ''} | "
            f"{', '.join(item.warnings) if item.warnings else ''}"
        )
    return 0


def command_compute_regime_signals(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    result = compute_regime_signals(config)
    safe_print(
        "Regime signals computed: "
        f"{result.computed_count}; warnings={result.warning_count}"
    )
    for item in result.results:
        safe_print(
            f"{item.ticker} | {item.proxy_type} | {item.trend_state or ''} | "
            f"{item.risk_state or ''} | {', '.join(item.warnings) if item.warnings else ''}"
        )
    return 0


def command_technical_status(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    safe_print(build_technical_status_text(config, ticker=args.ticker))
    return 0


def command_regime_status(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    safe_print(build_regime_status_text(config, ticker=args.ticker))
    return 0


def command_notification_status(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    status_filter = "pending" if getattr(args, "pending_only", False) else args.status
    events = list_notification_events(
        config.database_path,
        status=status_filter,
        ticker=args.ticker,
    )
    safe_print(f"Notification events: {len(events)}")
    safe_print("ID | Ticker | Timestamp | Severity | Previous -> Current | Price | Status")
    for event in events:
        safe_print(
            f"{event.notification_event_id} | {event.ticker} | {event.event_timestamp} | "
            f"{event.severity or ''} | {event.previous_state or ''} -> "
            f"{event.current_state or ''} | {_fmt(event.trigger_price)} | {event.status}"
        )
    return 0


def command_deliver_notifications(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    result = deliver_notifications(config, channel=args.channel)
    safe_print(
        f"Delivered notifications: {result.delivered_count}; "
        f"failed={result.failed_count}"
    )
    if result.outbox_paths:
        safe_print(
            "Outbox files: "
            + ", ".join(display_path(path, config.project_root) for path in result.outbox_paths)
        )
    if result.warnings:
        safe_print("Warnings: " + "; ".join(result.warnings))
    for event in result.events:
        safe_print(
            f"{event.ticker}: {event.current_state} "
            f"price={_fmt(event.trigger_price)} severity={event.severity or ''}"
        )
    return 0


def command_drain_pending_notifications(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    result = deliver_notifications(config, channel=args.channel)
    safe_print(
        f"Drained pending notifications: delivered={result.delivered_count}; "
        f"failed={result.failed_count}"
    )
    if result.outbox_paths:
        safe_print(
            "Outbox files: "
            + ", ".join(display_path(path, config.project_root) for path in result.outbox_paths)
        )
    if result.warnings:
        safe_print("Warnings: " + "; ".join(result.warnings))
    return 0 if result.failed_count == 0 else 1


def command_notification_outbox_status(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    safe_print(build_notification_outbox_status_text(config))
    return 0


def command_notification_delivery_report(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    safe_print(build_notification_delivery_report_text(config))
    return 0


def command_test_notification_channel(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    result = test_notification_channel(config, channel=args.channel)
    safe_print(f"Notification channel test: {result.channel} status={result.status}")
    if result.outbox_paths:
        safe_print(
            "Outbox files: "
            + ", ".join(display_path(path, config.project_root) for path in result.outbox_paths)
        )
    if result.warnings:
        safe_print("Warnings: " + "; ".join(result.warnings))
    if result.details:
        safe_print(f"Details: {result.details}")
    return 0 if result.status == "ok" else 1


def command_intraday_cycle(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    deliver = bool(args.deliver and not args.no_deliver)
    try:
        result = run_intraday_cycle(
            config,
            source=args.source,
            ticker=args.ticker,
            deliver=deliver,
            channel=args.channel,
            include_options=args.include_options,
            drain_first=args.drain_first,
        )
    except ValueError as error:
        safe_print(str(error))
        return 1
    safe_print(result.summary)
    safe_print("Step | Status | Rows | Warnings")
    for step in result.steps:
        safe_print(
            f"{step.step_name} | {step.status} | {step.rows_loaded} | "
            f"{'; '.join(step.warnings) if step.warnings else ''}"
        )
    return 0 if result.status != "error" else 1


def command_manual_ops_cycle(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    initialize_database(config.database_path)
    deliver = bool(args.deliver and not args.no_deliver)
    try:
        result = run_manual_ops_cycle(
            config,
            mode=args.mode,
            deliver=deliver,
            channel=args.channel,
            dry_run=args.dry_run,
        )
    except ValueError as error:
        safe_print(str(error))
        return 1
    safe_print(result.summary)
    safe_print("Step | Status | Rows | Warnings")
    for step in result.steps:
        safe_print(
            f"{step.step_name} | {step.status} | {step.rows_loaded} | "
            f"{'; '.join(step.warnings) if step.warnings else ''}"
        )
    return 0 if result.status != "error" else 1


def command_manual_ops_loop(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    initialize_database(config.database_path)
    deliver = bool(args.deliver and not args.no_deliver)
    safe_print(
        "Starting manual ops loop. Press Ctrl+C to stop. "
        f"mode={args.mode}, interval={args.interval_seconds or config.realtime_manual_ops_loop_interval_seconds}s"
    )
    try:
        result = run_manual_ops_loop(
            config,
            mode=args.mode,
            deliver=deliver,
            channel=args.channel,
            interval_seconds=args.interval_seconds,
            max_iterations=args.max_iterations,
            output_callback=safe_print,
        )
    except ValueError as error:
        safe_print(str(error))
        return 1
    safe_print(
        f"Manual ops loop finished: status={result.status}, "
        f"iterations={result.iterations}, reason={result.stopped_reason}"
    )
    return 0 if result.status != "error" else 1


def command_manual_ops_status(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    safe_print(build_manual_ops_status_text(config))
    return 0


def command_tom_loop_status(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    safe_print(build_tom_loop_status_text(config))
    return 0


def command_tom_loop_health(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    safe_print(build_tom_loop_health_text(config))
    return 0


def command_tom_loop_once(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    deliver = bool(args.deliver and not args.no_deliver)
    try:
        result = tom_loop_once(
            config,
            mode=args.mode,
            deliver=deliver,
            channel=args.channel,
        )
    except (RuntimeError, ValueError) as error:
        safe_print(str(error))
        return 1
    safe_print(result.message)
    if result.warnings:
        safe_print("Warnings: " + "; ".join(result.warnings))
    if result.result is not None:
        safe_print("Step | Status | Rows | Warnings")
        for step in result.result.steps:
            safe_print(
                f"{step.step_name} | {step.status} | {step.rows_loaded} | "
                f"{'; '.join(step.warnings) if step.warnings else ''}"
            )
    return 0 if result.status != "error" else 1


def command_tom_loop_start(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    deliver = bool(args.deliver and not args.no_deliver)
    try:
        result = tom_loop_start(
            config,
            mode=args.mode,
            deliver=deliver,
            channel=args.channel,
            interval_seconds=args.interval_seconds,
            max_cycles=args.max_cycles,
            output_callback=safe_print,
        )
    except (RuntimeError, ValueError) as error:
        safe_print(str(error))
        return 1
    safe_print(result.message)
    if result.warnings:
        safe_print("Warnings: " + "; ".join(result.warnings))
    return 0 if result.status != "error" else 1


def command_tom_loop_stop(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    result = tom_loop_stop(config)
    safe_print(result.message)
    safe_print(f"Status: {result.snapshot.status}")
    return 0


def command_intraday_status(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    health = intraday_health(config)
    scheduler_audit_result = audit_scheduler(config)
    latest_cycle = latest_pipeline_run(config.database_path, run_type="intraday_cycle")
    latest_probe = latest_pipeline_run(config.database_path, run_type="intraday_probe")
    pending_count = pending_notification_count(config.database_path)
    delivered_count = notification_delivery_count(config.database_path, status="delivered")
    failed_count = notification_delivery_count(config.database_path, status="failed")
    latest_delivered = latest_notification_delivery_timestamp(
        config.database_path,
        status="delivered",
    )
    latest_failed = list_notification_deliveries(
        config.database_path,
        status="failed",
        limit=1,
    )
    safe_print("Intraday status")
    safe_print(f"Health classification: {health.status}")
    safe_print(f"Market session: {health.market_session}")
    safe_print(f"Regular market hours: {health.regular_market_hours}")
    safe_print(f"Scheduler reconciliation: {scheduler_audit_result.status}")
    safe_print(
        "Blockers: " + (", ".join(health.blockers) if health.blockers else "none")
    )
    safe_print(
        "Warnings: " + (", ".join(health.warnings) if health.warnings else "none")
    )
    safe_print("Notes: " + (", ".join(health.notes) if health.notes else "none"))
    safe_print(
        "Latest intraday cycle: "
        + (
            f"{latest_cycle.status} {latest_cycle.started_at} {latest_cycle.summary or ''}"
            if latest_cycle
            else "none"
        )
    )
    safe_print(
        "Latest intraday probe: "
        + (
            f"{latest_probe.status} {latest_probe.started_at} {latest_probe.summary or ''}"
            if latest_probe
            else "none"
        )
    )
    safe_print(f"Latest quote timestamp: {latest_quote_timestamp(config.database_path) or 'none'}")
    safe_print(
        "Latest intraday gap timestamp: "
        f"{latest_intraday_gap_timestamp(config.database_path) or 'none'}"
    )
    safe_print(
        "Latest range snapshot timestamp: "
        f"{latest_range_snapshot_timestamp(config.database_path) or 'none'}"
    )
    safe_print(f"Pending notifications: {pending_count}")
    safe_print(f"Delivered notification deliveries: {delivered_count}")
    safe_print(f"Failed notification deliveries: {failed_count}")
    safe_print(f"Latest successful delivery: {latest_delivered or 'none'}")
    if latest_failed:
        failure = latest_failed[0]
        safe_print(
            f"Latest failed delivery: {failure.channel} "
            f"{failure.delivery_timestamp} {failure.details or ''}"
        )
    return 0


def command_intraday_health_check(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    safe_print(build_intraday_health_text(config))
    return 0


def command_intraday_repair_plan(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    safe_print(build_intraday_repair_plan_text(config))
    return 0


def command_scheduler_status(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    health = intraday_health(config)
    scheduler_audit_result = audit_scheduler(config)
    database_status = get_database_status(config.database_path)
    has_pipeline = config.database_path.exists() and "pipeline_runs" in database_status.existing_tables
    has_notifications = (
        config.database_path.exists()
        and "notification_events" in database_status.existing_tables
    )
    has_deliveries = (
        config.database_path.exists()
        and "notification_deliveries" in database_status.existing_tables
    )
    latest_cycle = (
        latest_pipeline_run(config.database_path, run_type="intraday_cycle")
        if has_pipeline
        else None
    )
    latest_refresh = (
        latest_pipeline_run(config.database_path, run_type="daily_refresh")
        if has_pipeline
        else None
    )
    pending_count = (
        pending_notification_count(config.database_path)
        if has_notifications
        else 0
    )
    failed_count = (
        notification_delivery_count(config.database_path, status="failed")
        if has_deliveries
        else 0
    )
    latest_delivery = (
        latest_notification_delivery_timestamp(
            config.database_path,
            status="delivered",
        )
        if has_deliveries
        else None
    )
    latest_report = latest_report_path(config.reports_dir)
    latest_csv = latest_csv_report_path(config.reports_dir)
    latest_dashboard = latest_dashboard_path(config.project_root)

    safe_print("TOM scheduler status")
    safe_print(f"Scheduler reconciliation: {scheduler_audit_result.status}")
    heartbeat_job = next(
        (
            job
            for job in scheduler_audit_result.jobs
            if job.job_key == "intraday_heartbeat"
        ),
        None,
    )
    if heartbeat_job:
        safe_print(f"Heartbeat automation id: {heartbeat_job.automation_id}")
        safe_print(f"Heartbeat automation status: {heartbeat_job.status}")
        safe_print(f"Actual heartbeat command: {heartbeat_job.actual_command or 'none'}")
        safe_print(f"Heartbeat metadata: {heartbeat_job.automation_path or 'none'}")
    if scheduler_audit_result.warnings:
        safe_print("Scheduler warnings: " + ", ".join(scheduler_audit_result.warnings))
    safe_print(f"Intraday health: {health.status}")
    safe_print(f"Intraday market session: {health.market_session}")
    safe_print(f"Intraday regular market hours: {health.regular_market_hours}")
    safe_print(
        "Intraday blockers: "
        + (", ".join(health.blockers) if health.blockers else "none")
    )
    safe_print(
        "Intraday warnings: "
        + (", ".join(health.warnings) if health.warnings else "none")
    )
    safe_print(
        "Intraday notes: "
        + (", ".join(health.notes) if health.notes else "none")
    )
    safe_print("Configured intended Codex jobs:")
    safe_print(
        "TOM Intraday Heartbeat | weekdays market hours | every 10 minutes | "
        "python -m target_opportunity_monitor intraday-cycle --source auto --deliver --channel file"
    )
    safe_print(
        "TOM Morning Check | weekdays 8:30 AM America/Toronto | "
        "ibkr-status; verify-universe; intraday-status"
    )
    safe_print(
        "TOM Daily Refresh | weekdays 6:30 PM America/Toronto | "
        "python -m target_opportunity_monitor refresh-data --daily-only"
    )
    safe_print(
        "TOM Daily Retry | weekdays 8:30 PM America/Toronto | "
        "status-first conditional refresh if latest daily refresh failed or data is stale"
    )
    safe_print(
        "Latest intraday cycle: "
        + (
            f"{latest_cycle.status} {latest_cycle.started_at} {latest_cycle.summary or ''}"
            if latest_cycle
            else "none"
        )
    )
    safe_print(
        "Latest daily refresh: "
        + (
            f"{latest_refresh.status} {latest_refresh.started_at} {latest_refresh.summary or ''}"
            if latest_refresh
            else "none"
        )
    )
    safe_print(f"Latest quote timestamp: {latest_quote_timestamp(config.database_path) or 'none'}")
    safe_print(
        "Latest range snapshot timestamp: "
        f"{latest_range_snapshot_timestamp(config.database_path) or 'none'}"
    )
    safe_print(f"Pending notifications: {pending_count}")
    safe_print(f"Failed notification deliveries: {failed_count}")
    safe_print(f"Latest successful delivery: {latest_delivery or 'none'}")
    safe_print(
        "Latest report: "
        f"{display_path(latest_report, config.project_root) if latest_report else 'none'}"
    )
    safe_print(
        "Latest CSV report: "
        f"{display_path(latest_csv, config.project_root) if latest_csv else 'none'}"
    )
    safe_print(
        "Latest dashboard: "
        f"{display_path(latest_dashboard, config.project_root) if latest_dashboard else 'none'}"
    )
    return 0


def command_scheduler_audit(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    safe_print(build_scheduler_audit_text(config))
    return 0


def command_scheduler_repair_plan(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    safe_print(build_scheduler_repair_plan_text(config))
    return 0


def command_scheduler_automation_status(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    safe_print(build_scheduler_automation_status_text(config))
    return 0


def _upsert_cik(config: object, ticker: str, cik: str | None) -> None:
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
    config: object,
    ticker: str,
    event_type: str,
    previous_active_flag: int | None,
    new_active_flag: int | None,
    reason: str | None = None,
    details: str | None = None,
) -> None:
    timestamp = datetime.now().isoformat(timespec="seconds")
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
            as_of_date=date.today().isoformat(),
            effective_date=timestamp,
        ),
    )


def command_add_asset(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    ticker = normalize_ticker(args.ticker)
    previous = latest_asset(config.database_path, ticker)
    asset_role = getattr(args, "asset_role", "scoreable")
    asset = Asset(
        ticker=ticker,
        name=args.name,
        asset_type=args.asset_type,
        exchange=args.exchange,
        currency=args.currency,
        sector=args.sector,
        industry=args.industry,
        country=args.country,
        active_flag=1,
        asset_role=asset_role,
        source="manual_cli",
        as_of_date=date.today().isoformat(),
        effective_date=datetime.now().isoformat(timespec="seconds"),
    )
    upsert_watchlist_asset(config.watchlist_path, asset)
    upsert_asset(config.database_path, asset)
    _upsert_cik(config, ticker, args.cik if args.asset_type == "equity" else None)
    _record_asset_change(
        config,
        ticker,
        "add_or_update",
        previous.active_flag if previous else None,
        1,
        args.reason,
        f"asset_type={args.asset_type};asset_role={asset_role}",
    )
    safe_print(f"Asset added/updated: {ticker}")
    if args.asset_type == "equity" and not args.cik:
        safe_print("Warning: no CIK supplied; SEC fundamental/insider readiness may need a CIK row.")
    if args.asset_type == "etf":
        safe_print("ETF added; NAV and holdings readiness must be filled separately.")
    return 0


def _set_asset_active_command(
    args: argparse.Namespace,
    active: bool,
    event_type: str,
) -> int:
    config = load_config(args.config)
    ticker = normalize_ticker(args.ticker)
    previous = latest_asset(config.database_path, ticker)
    if previous is None:
        safe_print(f"Asset not found: {ticker}")
        return 1
    set_watchlist_active(config.watchlist_path, ticker, active)
    updated = set_asset_active_flag(
        config.database_path,
        ticker,
        1 if active else 0,
        as_of_date=date.today().isoformat(),
        effective_date=datetime.now().isoformat(timespec="seconds"),
    )
    _record_asset_change(
        config,
        ticker,
        event_type,
        previous.active_flag,
        updated.active_flag if updated else (1 if active else 0),
        getattr(args, "reason", None),
    )
    safe_print(f"Asset {ticker} active={1 if active else 0}")
    return 0


def command_deactivate_asset(args: argparse.Namespace) -> int:
    return _set_asset_active_command(args, active=False, event_type="deactivate")


def command_reactivate_asset(args: argparse.Namespace) -> int:
    return _set_asset_active_command(args, active=True, event_type="reactivate")


def command_remove_asset(args: argparse.Namespace) -> int:
    if not args.soft:
        safe_print("Only soft remove is supported. Re-run with --soft.")
        return 1
    return _set_asset_active_command(args, active=False, event_type="soft_remove")


def command_asset_status(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    ticker = normalize_ticker(args.ticker)
    asset = latest_asset(config.database_path, ticker)
    if asset is None:
        safe_print(f"Asset not found: {ticker}")
        return 1
    safe_print(f"Ticker: {asset.ticker}")
    safe_print(f"Name: {asset.name or ''}")
    safe_print(f"Type: {asset.asset_type or ''}")
    safe_print(f"Exchange: {asset.exchange or ''}")
    safe_print(f"Currency: {asset.currency or ''}")
    safe_print(f"Sector: {asset.sector or ''}")
    safe_print(f"Active: {asset.active_flag}")
    safe_print(f"Asset role: {asset.asset_role}")
    readiness = verify_ticker(config, ticker)
    safe_print(f"Pre-alert ready: {readiness.phase4_ready}")
    safe_print(
        f"Readiness warnings: {', '.join(readiness.warnings) if readiness.warnings else 'none'}"
    )
    for status in range_statuses(config.database_path, ticker=ticker):
        safe_print(f"Latest range state: {status.range_state}")
        safe_print(f"Latest range timestamp: {status.snapshot_timestamp or 'none'}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="target_opportunity_monitor",
        description="Local Target Opportunity Monitor CLI.",
    )
    _add_common_options(parser)

    subparsers = parser.add_subparsers(dest="command", required=True)

    init_db_parser = subparsers.add_parser(
        "init-db", help="Create the local SQLite database and schema."
    )
    init_db_parser.set_defaults(func=command_init_db)

    status_parser = subparsers.add_parser("status", help="Show local TOM status.")
    status_parser.set_defaults(func=command_status)

    run_daily_parser = subparsers.add_parser(
        "run-daily", help="Run the daily scoring report."
    )
    run_daily_parser.set_defaults(func=command_run_daily)

    build_dashboard_parser = subparsers.add_parser(
        "build-dashboard", help="Build the local static dashboard."
    )
    build_dashboard_parser.set_defaults(func=command_build_dashboard)

    api_status_parser = subparsers.add_parser(
        "api-status", help="Show local TOM API server configuration and endpoints."
    )
    api_status_parser.set_defaults(func=command_api_status)

    serve_api_parser = subparsers.add_parser(
        "serve-api", help="Serve the local-only TOM HTTP/JSON API."
    )
    serve_api_parser.add_argument(
        "--host",
        default=None,
        help="Local bind host. Defaults to api.host from config.",
    )
    serve_api_parser.add_argument(
        "--port",
        type=int,
        default=None,
        help="Bind port. Defaults to api.port from config.",
    )
    serve_api_parser.add_argument(
        "--once-smoke-test",
        action="store_true",
        help="Run non-persistent API health/status smoke checks and exit.",
    )
    serve_api_parser.set_defaults(func=command_serve_api)

    load_options_chain_parser = subparsers.add_parser(
        "load-options-chain",
        help="Load manual option-chain rows for read-only sell-put advisory.",
    )
    load_options_chain_parser.add_argument(
        "--file",
        type=Path,
        default=None,
        help="Options chain CSV path. Defaults to data/options/manual/options_chain.csv.",
    )
    load_options_chain_parser.set_defaults(func=command_load_options_chain)

    load_options_positions_parser = subparsers.add_parser(
        "load-options-positions",
        help="Load manual read-only option position ledger rows.",
    )
    load_options_positions_parser.add_argument(
        "--file",
        type=Path,
        default=None,
        help="Options positions CSV path. Defaults to data/options/manual/options_positions.csv.",
    )
    load_options_positions_parser.set_defaults(func=command_load_options_positions)

    fetch_options_chain_parser = subparsers.add_parser(
        "fetch-options-chain",
        help="Fetch or load bounded option-chain snapshots for advisory review.",
    )
    fetch_options_chain_parser.add_argument(
        "--source",
        choices=("auto", "ibkr", "yfinance", "csv"),
        default=None,
        help="Option-chain source. Defaults to options.chain_source.",
    )
    fetch_options_chain_parser.add_argument("--ticker", type=str, default=None)
    fetch_options_chain_parser.add_argument(
        "--max-tickers",
        type=int,
        default=None,
        help="Maximum tickers to fetch when --ticker is omitted.",
    )
    fetch_options_chain_parser.add_argument("--force-refresh", action="store_true")
    fetch_options_chain_parser.set_defaults(func=command_fetch_options_chain)

    compute_options_income_parser = subparsers.add_parser(
        "compute-options-income",
        help="Compute read-only sell-put advisory reviews from loaded option chains.",
    )
    compute_options_income_parser.add_argument(
        "--ticker",
        type=str,
        default=None,
        help="Optional ticker to review. Defaults to all loaded option-chain tickers.",
    )
    compute_options_income_parser.set_defaults(func=command_compute_options_income)

    compute_options_risk_parser = subparsers.add_parser(
        "compute-options-risk",
        help="Compute read-only cash-secured option risk reviews.",
    )
    compute_options_risk_parser.add_argument(
        "--ticker",
        type=str,
        default=None,
        help="Optional ticker to risk-review. Defaults to all latest option-income reviews.",
    )
    compute_options_risk_parser.set_defaults(func=command_compute_options_risk)

    compute_options_outcomes_parser = subparsers.add_parser(
        "compute-options-outcomes",
        help="Validate read-only sell-put reviews against underlying daily prices.",
    )
    compute_options_outcomes_parser.add_argument(
        "--ticker",
        type=str,
        default=None,
        help="Optional ticker to validate. Defaults to all option-income reviews.",
    )
    compute_options_outcomes_parser.set_defaults(func=command_compute_options_outcomes)

    compute_options_lifecycle_parser = subparsers.add_parser(
        "compute-options-lifecycle",
        help="Compute read-only option position lifecycle and realized/open P/L reviews.",
    )
    compute_options_lifecycle_parser.add_argument(
        "--ticker",
        type=str,
        default=None,
        help="Optional ticker to lifecycle-review. Defaults to all manual option positions.",
    )
    compute_options_lifecycle_parser.set_defaults(func=command_compute_options_lifecycle)

    options_status_parser = subparsers.add_parser(
        "options-status",
        help="Show options/sell-put advisory coverage and latest reviews.",
    )
    options_status_parser.set_defaults(func=command_options_status)

    options_risk_status_parser = subparsers.add_parser(
        "options-risk-status",
        help="Show options risk/margin proxy coverage and latest risk reviews.",
    )
    options_risk_status_parser.set_defaults(func=command_options_risk_status)

    options_risk_report_parser = subparsers.add_parser(
        "options-risk-report",
        help="Print a read-only options risk report.",
    )
    options_risk_report_parser.set_defaults(func=command_options_risk_report)

    options_position_status_parser = subparsers.add_parser(
        "options-position-status",
        help="Show manual option position ledger coverage.",
    )
    options_position_status_parser.set_defaults(func=command_options_position_status)

    options_outcome_status_parser = subparsers.add_parser(
        "options-outcome-status",
        help="Show option review outcome validation status.",
    )
    options_outcome_status_parser.set_defaults(func=command_options_outcome_status)

    options_outcome_report_parser = subparsers.add_parser(
        "options-outcome-report",
        help="Print a read-only options review outcome report.",
    )
    options_outcome_report_parser.set_defaults(func=command_options_outcome_report)

    options_lifecycle_status_parser = subparsers.add_parser(
        "options-lifecycle-status",
        help="Show option position lifecycle and realized/open P/L status.",
    )
    options_lifecycle_status_parser.set_defaults(func=command_options_lifecycle_status)

    options_lifecycle_report_parser = subparsers.add_parser(
        "options-lifecycle-report",
        help="Print a read-only options lifecycle and P/L report.",
    )
    options_lifecycle_report_parser.set_defaults(func=command_options_lifecycle_report)

    option_chain_status_parser = subparsers.add_parser(
        "option-chain-status",
        help="Show option-chain provider/cache coverage.",
    )
    option_chain_status_parser.set_defaults(func=command_option_chain_status)

    option_provider_status_parser = subparsers.add_parser(
        "option-provider-status",
        help="Show option-chain provider health and backfill readiness.",
    )
    option_provider_status_parser.add_argument(
        "--check-connectivity",
        action="store_true",
        help="Also run a live IBKR connectivity check.",
    )
    option_provider_status_parser.set_defaults(func=command_option_provider_status)

    diagnose_options_provider_parser = subparsers.add_parser(
        "diagnose-options-provider",
        help="Run option-provider diagnostics for IBKR readiness.",
    )
    diagnose_options_provider_parser.add_argument(
        "--source",
        choices=("ibkr",),
        default="ibkr",
    )
    diagnose_options_provider_parser.set_defaults(
        func=command_diagnose_options_provider
    )

    test_options_provider_parser = subparsers.add_parser(
        "test-options-provider",
        help="Run one bounded read-only option-provider test fetch.",
    )
    test_options_provider_parser.add_argument(
        "--source",
        choices=("auto", "ibkr", "yfinance"),
        default="ibkr",
    )
    test_options_provider_parser.add_argument("--ticker", required=True)
    test_options_provider_parser.set_defaults(func=command_test_options_provider)

    export_options_chain_backfill_parser = subparsers.add_parser(
        "export-options-chain-backfill-template",
        help="Create a source-export template for option-chain backfill rows.",
    )
    export_options_chain_backfill_parser.add_argument("--ticker", type=str, default=None)
    export_options_chain_backfill_parser.add_argument(
        "--minimum-set",
        action="store_true",
        help="Export only the minimum activation tickers: SOXL, KORU, and AAPL.",
    )
    export_options_chain_backfill_parser.set_defaults(
        func=command_export_options_chain_backfill_template
    )

    validate_options_chain_backfill_parser = subparsers.add_parser(
        "validate-options-chain-backfill",
        help="Validate source-backed option-chain backfill CSV files without importing.",
    )
    validate_options_chain_backfill_parser.add_argument(
        "--dir",
        type=Path,
        default=None,
        help="Source-export directory. Defaults to data/options/source_exports.",
    )
    validate_options_chain_backfill_parser.set_defaults(
        func=command_validate_options_chain_backfill
    )

    import_options_chain_exports_parser = subparsers.add_parser(
        "import-options-chain-source-exports",
        help="Import validated source-backed option-chain source-export CSV files.",
    )
    import_options_chain_exports_parser.add_argument(
        "--dir",
        type=Path,
        default=None,
        help="Source-export directory. Defaults to data/options/source_exports.",
    )
    import_options_chain_exports_parser.set_defaults(
        func=command_import_options_chain_source_exports
    )

    option_chain_activation_status_parser = subparsers.add_parser(
        "option-chain-activation-status",
        help="Show Phase 12B.2 option-chain activation readiness.",
    )
    option_chain_activation_status_parser.set_defaults(
        func=command_option_chain_activation_status
    )

    option_provider_repair_plan_parser = subparsers.add_parser(
        "option-provider-repair-plan",
        help="Print a diagnostic-only repair plan for option provider blockers.",
    )
    option_provider_repair_plan_parser.add_argument(
        "--source",
        choices=("ibkr",),
        default="ibkr",
    )
    option_provider_repair_plan_parser.set_defaults(
        func=command_option_provider_repair_plan
    )

    option_chain_minimum_plan_parser = subparsers.add_parser(
        "option-chain-minimum-backfill-plan",
        help="Show the minimum option-chain seeding plan for activation.",
    )
    option_chain_minimum_plan_parser.set_defaults(
        func=command_option_chain_minimum_backfill_plan
    )

    option_chain_coverage_plan_parser = subparsers.add_parser(
        "option-chain-coverage-plan",
        help="Show broader option-chain coverage and source-export readiness.",
    )
    option_chain_coverage_plan_parser.set_defaults(
        func=command_option_chain_coverage_plan
    )

    export_options_chain_missing_parser = subparsers.add_parser(
        "export-options-chain-missing-template",
        help="Create a source-export template for tickers missing option chains.",
    )
    export_options_chain_missing_parser.set_defaults(
        func=command_export_options_chain_missing_template
    )

    apply_options_chain_coverage_parser = subparsers.add_parser(
        "apply-options-chain-coverage-backfill",
        help="Dry-run or confirm broader option-chain source-export backfill.",
    )
    apply_options_chain_coverage_parser.add_argument(
        "--dir",
        type=Path,
        default=None,
        help="Source-export directory. Defaults to data/options/source_exports.",
    )
    apply_options_chain_coverage_parser.add_argument(
        "--confirm",
        action="store_true",
        help="Import valid source exports and recompute option reviews.",
    )
    apply_options_chain_coverage_parser.add_argument(
        "--allow-partial",
        action="store_true",
        help="Allow coverage to improve for fewer than all missing tickers.",
    )
    apply_options_chain_coverage_parser.set_defaults(
        func=command_apply_options_chain_coverage_backfill
    )

    account_context_status_parser = subparsers.add_parser(
        "account-context-status",
        help="Show portfolio/cash/options position activation status.",
    )
    account_context_status_parser.set_defaults(func=command_account_context_status)

    account_provider_status_parser = subparsers.add_parser(
        "account-provider-status",
        help="Show read-only account provider and source-export readiness.",
    )
    account_provider_status_parser.add_argument(
        "--no-connectivity-check",
        action="store_true",
        help="Skip live IBKR socket check and inspect local import/source-export state only.",
    )
    account_provider_status_parser.set_defaults(func=command_account_provider_status)

    fetch_account_context_parser = subparsers.add_parser(
        "fetch-account-context",
        help="Fetch or normalize read-only account context into source-export files.",
    )
    fetch_account_context_parser.add_argument(
        "--source",
        choices=("ibkr", "file"),
        required=True,
        help="Read-only source to use.",
    )
    fetch_account_context_parser.add_argument(
        "--read-only",
        action="store_true",
        help="Required safety acknowledgement; this command never writes to brokers.",
    )
    fetch_account_context_parser.add_argument(
        "--provider",
        choices=("generic", "ibkr", "ibkr-flex", "ibkr-activity"),
        default="generic",
        help="Provider/export format when --source file is used.",
    )
    fetch_account_context_parser.add_argument(
        "--file",
        type=Path,
        default=None,
        help="CSV export to normalize when --source file is used.",
    )
    fetch_account_context_parser.set_defaults(func=command_fetch_account_context)

    export_account_context_template_parser = subparsers.add_parser(
        "export-account-context-template",
        help="Create fillable account-context source-export templates.",
    )
    export_account_context_template_parser.set_defaults(
        func=command_export_account_context_template
    )

    validate_account_context_parser = subparsers.add_parser(
        "validate-account-context-backfill",
        help="Validate account-context backfill rows without importing.",
    )
    validate_account_context_parser.set_defaults(
        func=command_validate_account_context_backfill
    )

    preview_account_context_parser = subparsers.add_parser(
        "preview-account-context-activation",
        help="Preview account-context row counts and blockers without importing.",
    )
    preview_account_context_parser.set_defaults(
        func=command_preview_account_context_activation
    )

    apply_account_context_parser = subparsers.add_parser(
        "apply-account-context-backfill",
        help="Dry-run or confirm account-context backfill import and recompute.",
    )
    apply_account_context_parser.add_argument(
        "--confirm",
        action="store_true",
        help="Apply valid rows, recompute portfolio/options context, and rebuild outputs.",
    )
    apply_account_context_parser.add_argument(
        "--allow-partial",
        action="store_true",
        help="Allow applying valid rows for only some account-context inputs.",
    )
    apply_account_context_parser.set_defaults(func=command_apply_account_context_backfill)

    missing_ticker_status_parser = subparsers.add_parser(
        "missing-ticker-status",
        help="Show missing ticker candidates discovered across TOM workflows.",
    )
    missing_ticker_status_parser.set_defaults(func=command_missing_ticker_status)

    missing_ticker_plan_parser = subparsers.add_parser(
        "missing-ticker-plan",
        help="Resolve and show a non-mutating plan for missing ticker candidates.",
    )
    missing_ticker_plan_parser.add_argument(
        "--source",
        choices=("all", "account_context", "research_recommendations", "trader_commentary"),
        default="all",
        help="Candidate source to inspect. Defaults to all supported sources.",
    )
    missing_ticker_plan_parser.set_defaults(func=command_missing_ticker_plan)

    resolve_missing_tickers_parser = subparsers.add_parser(
        "resolve-missing-tickers",
        help="Detect and stage missing ticker candidates from supported source rows.",
    )
    resolve_missing_tickers_parser.add_argument(
        "--source",
        choices=("all", "account_context", "research_recommendations", "trader_commentary"),
        default="all",
        help="Candidate source to resolve. Defaults to all supported sources.",
    )
    resolve_missing_tickers_parser.set_defaults(func=command_resolve_missing_tickers)

    apply_missing_ticker_parser = subparsers.add_parser(
        "apply-missing-ticker-onboarding",
        help="Confirm onboarding for ready source-backed missing ticker candidates.",
    )
    apply_missing_ticker_parser.add_argument(
        "--confirm",
        action="store_true",
        help="Write ready candidates through watchlist/assets and asset-change audit.",
    )
    apply_missing_ticker_parser.add_argument(
        "--source",
        choices=("all", "account_context"),
        default="account_context",
        help="Candidate source to apply. Defaults to account_context.",
    )
    apply_missing_ticker_parser.set_defaults(func=command_apply_missing_ticker_onboarding)

    hydrate_missing_ticker_parser = subparsers.add_parser(
        "hydrate-missing-ticker",
        help="Fetch/compute the available local data path for one onboarded ticker.",
    )
    hydrate_missing_ticker_parser.add_argument(
        "--ticker",
        required=True,
        help="Onboarded ticker to hydrate.",
    )
    hydrate_missing_ticker_parser.set_defaults(func=command_hydrate_missing_ticker)

    normalize_account_export_parser = subparsers.add_parser(
        "normalize-account-export",
        help="Normalize a generic or IBKR account export into account-context templates.",
    )
    normalize_account_export_parser.add_argument(
        "--provider",
        choices=("ibkr", "ibkr-flex", "ibkr-activity", "generic"),
        required=True,
        help="Source export format to normalize.",
    )
    normalize_account_export_parser.add_argument(
        "--file",
        type=Path,
        required=True,
        help="Provider/export CSV to normalize.",
    )
    normalize_account_export_parser.set_defaults(func=command_normalize_account_export)

    activate_options_chain_parser = subparsers.add_parser(
        "activate-options-chain-data",
        help="Dry-run or confirm source-backed option-chain activation.",
    )
    activate_options_chain_parser.add_argument(
        "--dir",
        type=Path,
        default=None,
        help="Source-export directory. Defaults to data/options/source_exports.",
    )
    activate_options_chain_parser.add_argument(
        "--confirm",
        action="store_true",
        help="Import valid source exports and recompute option-income reviews.",
    )
    activate_options_chain_parser.add_argument(
        "--allow-partial",
        action="store_true",
        help="Allow activation when at least one minimum ticker has valid rows.",
    )
    activate_options_chain_parser.set_defaults(func=command_activate_options_chain_data)

    load_watchlist_parser = subparsers.add_parser(
        "load-watchlist", help="Load assets from a manual watchlist CSV."
    )
    load_watchlist_parser.add_argument(
        "--file",
        type=Path,
        default=None,
        help="Watchlist CSV path. Defaults to configs/watchlist.csv.",
    )
    load_watchlist_parser.set_defaults(func=command_load_watchlist)

    list_assets_parser = subparsers.add_parser(
        "list-assets", help="List assets currently stored in the database."
    )
    list_assets_parser.set_defaults(func=command_list_assets)

    update_prices_parser = subparsers.add_parser(
        "update-prices", help="Load market prices for active assets."
    )
    update_prices_parser.add_argument(
        "--ticker",
        type=str,
        default=None,
        help="Optional ticker to update. Defaults to all active assets.",
    )
    update_prices_parser.add_argument(
        "--source",
        choices=("auto", "stooq", "yahoo", "csv", "ibkr"),
        default=None,
        help="Market data source mode. Defaults to config market_data.mode.",
    )
    update_prices_parser.set_defaults(func=command_update_prices)

    price_status_parser = subparsers.add_parser(
        "price-status", help="Show price history and feature coverage by ticker."
    )
    price_status_parser.set_defaults(func=command_price_status)

    load_fundamentals_parser = subparsers.add_parser(
        "load-fundamentals", help="Load manual fundamentals from CSV."
    )
    load_fundamentals_parser.add_argument(
        "--file",
        type=Path,
        default=None,
        help="Fundamentals CSV path. Defaults to data/fundamentals/manual/fundamentals.csv.",
    )
    load_fundamentals_parser.set_defaults(func=command_load_fundamentals)

    load_estimates_parser = subparsers.add_parser(
        "load-estimates", help="Load manual estimates from CSV."
    )
    load_estimates_parser.add_argument(
        "--file",
        type=Path,
        default=None,
        help="Estimates CSV path. Defaults to data/fundamentals/manual/estimates.csv.",
    )
    load_estimates_parser.set_defaults(func=command_load_estimates)

    foreign_equity_source_status_parser = subparsers.add_parser(
        "foreign-equity-source-status",
        help="Validate staged foreign-equity fundamentals and estimates source rows.",
    )
    foreign_equity_source_status_parser.set_defaults(
        func=command_foreign_equity_source_status
    )

    export_foreign_equity_source_template_parser = subparsers.add_parser(
        "export-foreign-equity-source-template",
        help="Create foreign-equity fundamentals and estimates source-export templates.",
    )
    export_foreign_equity_source_template_parser.set_defaults(
        func=command_export_foreign_equity_source_template
    )

    apply_foreign_equity_source_parser = subparsers.add_parser(
        "apply-foreign-equity-source",
        help="Dry-run or confirm import of valid foreign-equity source rows.",
    )
    apply_foreign_equity_source_parser.add_argument(
        "--confirm",
        action="store_true",
        help="Import valid foreign-equity source rows into fundamentals and estimates.",
    )
    apply_foreign_equity_source_parser.set_defaults(
        func=command_apply_foreign_equity_source
    )

    export_universe_candidate_template_parser = subparsers.add_parser(
        "export-universe-candidate-template",
        help="Create a fillable expanded-universe candidate CSV.",
    )
    export_universe_candidate_template_parser.set_defaults(
        func=command_export_universe_candidate_template
    )

    universe_expansion_plan_parser = subparsers.add_parser(
        "universe-expansion-plan",
        help="Show valid/blocked expanded-universe candidate rows.",
    )
    universe_expansion_plan_parser.set_defaults(func=command_universe_expansion_plan)

    apply_universe_candidates_parser = subparsers.add_parser(
        "apply-universe-candidates",
        help="Dry-run or confirm expanded-universe candidate application.",
    )
    apply_universe_candidates_parser.add_argument("--confirm", action="store_true")
    apply_universe_candidates_parser.add_argument("--allow-partial", action="store_true")
    apply_universe_candidates_parser.set_defaults(func=command_apply_universe_candidates)

    research_ticker_plan_parser = subparsers.add_parser(
        "research-ticker-plan",
        help="Resolve metadata and preview adding one scoreable research ticker.",
    )
    research_ticker_plan_parser.add_argument("--ticker", required=True)
    research_ticker_plan_parser.add_argument(
        "--asset-type",
        choices=("equity", "foreign_equity", "etf"),
        default=None,
        help="Research path to use. Defaults to stored asset type when available.",
    )
    research_ticker_plan_parser.add_argument("--refresh-metadata", action="store_true")
    research_ticker_plan_parser.add_argument("--name", default=None)
    research_ticker_plan_parser.add_argument("--sector", default=None)
    research_ticker_plan_parser.add_argument("--industry", default=None)
    research_ticker_plan_parser.add_argument("--cik", default=None)
    research_ticker_plan_parser.add_argument("--exchange", default=None)
    research_ticker_plan_parser.add_argument("--currency", default=None)
    research_ticker_plan_parser.add_argument("--country", default=None)
    research_ticker_plan_parser.set_defaults(func=command_research_ticker_plan)

    apply_research_ticker_parser = subparsers.add_parser(
        "apply-research-ticker",
        help="Confirm adding or promoting one scoreable research ticker.",
    )
    apply_research_ticker_parser.add_argument("--ticker", required=True)
    apply_research_ticker_parser.add_argument(
        "--asset-type",
        choices=("equity", "foreign_equity", "etf"),
        default=None,
        help="Research path to use. Defaults to stored asset type when available.",
    )
    apply_research_ticker_parser.add_argument("--confirm", action="store_true")
    apply_research_ticker_parser.add_argument("--refresh-metadata", action="store_true")
    apply_research_ticker_parser.add_argument("--name", default=None)
    apply_research_ticker_parser.add_argument("--sector", default=None)
    apply_research_ticker_parser.add_argument("--industry", default=None)
    apply_research_ticker_parser.add_argument("--cik", default=None)
    apply_research_ticker_parser.add_argument("--exchange", default=None)
    apply_research_ticker_parser.add_argument("--currency", default=None)
    apply_research_ticker_parser.add_argument("--country", default=None)
    apply_research_ticker_parser.set_defaults(func=command_apply_research_ticker)

    refresh_research_ticker_parser = subparsers.add_parser(
        "refresh-research-ticker",
        help="Run the bounded per-ticker refresh and benchmark chain.",
    )
    refresh_research_ticker_parser.add_argument("--ticker", required=True)
    refresh_research_ticker_parser.set_defaults(func=command_refresh_research_ticker)

    research_ticker_status_parser = subparsers.add_parser(
        "research-ticker-status",
        help="Show one research ticker's scoreable readiness and benchmark status.",
    )
    research_ticker_status_parser.add_argument("--ticker", required=True)
    research_ticker_status_parser.set_defaults(func=command_research_ticker_status)

    etf_strategy_review_parser = subparsers.add_parser(
        "etf-strategy-review",
        help="Show the read-only ETF shares/call/sell-put strategy comparison for one ETF.",
    )
    etf_strategy_review_parser.add_argument("--ticker", required=True)
    etf_strategy_review_parser.set_defaults(func=command_etf_strategy_review)

    generate_research_recommendations_parser = subparsers.add_parser(
        "generate-research-recommendations",
        help="Generate approval-gated ticker candidates for research.",
    )
    generate_research_recommendations_parser.add_argument(
        "--source",
        choices=("all", "tom_internal", "social_local", "external_research_signals", "codex_manual"),
        default="all",
    )
    generate_research_recommendations_parser.set_defaults(
        func=command_generate_research_recommendations
    )

    export_research_recommendation_template_parser = subparsers.add_parser(
        "export-research-recommendation-template",
        help="Create a fillable manual/Codex research recommendation CSV.",
    )
    export_research_recommendation_template_parser.set_defaults(
        func=command_export_research_recommendation_template
    )

    import_research_recommendations_parser = subparsers.add_parser(
        "import-research-recommendations",
        help="Import audited manual/Codex research recommendation rows.",
    )
    import_research_recommendations_parser.add_argument(
        "--file",
        type=Path,
        default=None,
        help="Recommendation CSV path. Defaults to data/research/manual/research_recommendations.csv.",
    )
    import_research_recommendations_parser.set_defaults(
        func=command_import_research_recommendations
    )

    research_recommendation_status_parser = subparsers.add_parser(
        "research-recommendation-status",
        help="Show pending, approved, and promoted research recommendation counts.",
    )
    research_recommendation_status_parser.set_defaults(
        func=command_research_recommendation_status
    )

    research_preparation_run_parser = subparsers.add_parser(
        "research-preparation-run",
        help="Scan or confirm safe preparation actions for pending research tickers.",
    )
    research_preparation_run_parser.add_argument(
        "--source",
        choices=PREPARATION_SOURCES,
        default="pending",
        help="Research preparation source to inspect. Defaults to pending recommendations.",
    )
    research_preparation_run_parser.add_argument(
        "--action",
        choices=PREPARATION_ACTIONS,
        default="scan",
        help="Preparation action to run. Defaults to scan, which is read-only.",
    )
    research_preparation_run_parser.add_argument(
        "--confirm",
        action="store_true",
        help="Confirm safe mutating preparation actions.",
    )
    research_preparation_run_parser.add_argument(
        "--ticker",
        action="append",
        default=None,
        help="Limit preparation to one ticker. Repeat for multiple tickers.",
    )
    research_preparation_run_parser.set_defaults(func=command_research_preparation_run)

    research_recommendation_report_parser = subparsers.add_parser(
        "research-recommendation-report",
        help="Print the latest research recommendation queue report.",
    )
    research_recommendation_report_parser.set_defaults(
        func=command_research_recommendation_report
    )

    set_research_recommendation_status_parser = subparsers.add_parser(
        "set-research-recommendation-status",
        help="Approve, ignore, or reject a research recommendation.",
    )
    set_research_recommendation_status_parser.add_argument("--id", type=int, required=True)
    set_research_recommendation_status_parser.add_argument(
        "--status",
        choices=("pending", "approved", "ignored", "rejected"),
        required=True,
    )
    set_research_recommendation_status_parser.add_argument("--reason", default=None)
    set_research_recommendation_status_parser.set_defaults(
        func=command_set_research_recommendation_status
    )

    promote_research_recommendation_parser = subparsers.add_parser(
        "promote-research-recommendation",
        help="Preview or confirm promotion into the Phase 13B research ticker flow.",
    )
    promote_research_recommendation_parser.add_argument("--id", type=int, required=True)
    promote_research_recommendation_parser.add_argument("--confirm", action="store_true")
    promote_research_recommendation_parser.set_defaults(
        func=command_promote_research_recommendation
    )

    compute_fundamental_benchmarks_parser = subparsers.add_parser(
        "compute-fundamental-benchmarks",
        help="Compute overall, sector, industry, and benchmark comparison snapshots.",
    )
    compute_fundamental_benchmarks_parser.set_defaults(
        func=command_compute_fundamental_benchmarks
    )

    fundamental_benchmark_status_parser = subparsers.add_parser(
        "fundamental-benchmark-status",
        help="Show fundamental benchmark and ticker comparison coverage.",
    )
    fundamental_benchmark_status_parser.set_defaults(
        func=command_fundamental_benchmark_status
    )

    fundamental_benchmark_report_parser = subparsers.add_parser(
        "fundamental-benchmark-report",
        help="Print the latest fundamental benchmark comparison report.",
    )
    fundamental_benchmark_report_parser.add_argument("--ticker", default=None)
    fundamental_benchmark_report_parser.set_defaults(
        func=command_fundamental_benchmark_report
    )

    load_analyst_revisions_parser = subparsers.add_parser(
        "load-analyst-revisions",
        help="Load manual analyst revision inputs from CSV.",
    )
    load_analyst_revisions_parser.add_argument(
        "--file",
        type=Path,
        default=None,
        help="Analyst revisions CSV path. Defaults to data/signals/manual/analyst_revisions.csv.",
    )
    load_analyst_revisions_parser.set_defaults(func=command_load_analyst_revisions)

    load_news_catalysts_parser = subparsers.add_parser(
        "load-news-catalysts",
        help="Load manual news/catalyst source rows from CSV.",
    )
    load_news_catalysts_parser.add_argument(
        "--file",
        type=Path,
        default=None,
        help="News/catalyst CSV path. Defaults to data/signals/manual/news_catalysts.csv.",
    )
    load_news_catalysts_parser.set_defaults(func=command_load_news_catalysts)

    load_trader_commentary_parser = subparsers.add_parser(
        "load-trader-commentary",
        help="Load manual trader commentary capture rows from CSV.",
    )
    load_trader_commentary_parser.add_argument(
        "--file",
        type=Path,
        default=None,
        help="Trader commentary CSV path. Defaults to data/signals/manual/trader_commentary.csv.",
    )
    load_trader_commentary_parser.set_defaults(func=command_load_trader_commentary)

    export_trader_commentary_template_parser = subparsers.add_parser(
        "export-trader-commentary-template",
        help="Export a ready-to-fill trader commentary CSV and text-file template.",
    )
    export_trader_commentary_template_parser.set_defaults(
        func=command_export_trader_commentary_template
    )

    load_commentary_aliases_parser = subparsers.add_parser(
        "load-commentary-instrument-aliases",
        help="Load commentary instrument-label aliases from CSV.",
    )
    load_commentary_aliases_parser.add_argument(
        "--file",
        type=Path,
        default=None,
        help="Alias CSV path. Defaults to data/signals/manual/trader_commentary_instrument_aliases.csv.",
    )
    load_commentary_aliases_parser.set_defaults(
        func=command_load_commentary_instrument_aliases
    )

    load_commentary_dispositions_parser = subparsers.add_parser(
        "load-commentary-label-dispositions",
        help="Validate reviewed commentary labels that should not map to a ticker.",
    )
    load_commentary_dispositions_parser.add_argument(
        "--file",
        type=Path,
        default=None,
        help="Disposition CSV path. Defaults to data/signals/manual/trader_commentary_label_dispositions.csv.",
    )
    load_commentary_dispositions_parser.set_defaults(
        func=command_load_commentary_label_dispositions
    )

    commentary_onboarding_plan_parser = subparsers.add_parser(
        "commentary-onboarding-plan",
        help="Show onboarding candidates from parsed trader commentary claims.",
    )
    commentary_onboarding_plan_parser.set_defaults(
        func=command_commentary_onboarding_plan
    )

    commentary_onboarding_status_parser = subparsers.add_parser(
        "commentary-onboarding-status",
        help="Show commentary onboarding and alias readiness.",
    )
    commentary_onboarding_status_parser.set_defaults(
        func=command_commentary_onboarding_status
    )

    export_commentary_onboarding_parser = subparsers.add_parser(
        "export-commentary-onboarding-template",
        help="Export a fillable commentary onboarding CSV template.",
    )
    export_commentary_onboarding_parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Output CSV path. Defaults to the trader commentary source-export directory.",
    )
    export_commentary_onboarding_parser.set_defaults(
        func=command_export_commentary_onboarding_template
    )

    apply_commentary_onboarding_parser = subparsers.add_parser(
        "apply-commentary-onboarding",
        help="Apply confirmed commentary onboarding template rows.",
    )
    apply_commentary_onboarding_parser.add_argument("--file", type=Path, required=True)
    apply_commentary_onboarding_parser.add_argument(
        "--confirm",
        action="store_true",
        help="Actually apply rows. Without this flag the command is a dry run.",
    )
    apply_commentary_onboarding_parser.set_defaults(
        func=command_apply_commentary_onboarding
    )

    browser_capture_commentary_parser = subparsers.add_parser(
        "browser-capture-commentary",
        help="Record a cautious browser-captured commentary artifact run.",
    )
    browser_capture_commentary_parser.add_argument(
        "--provider",
        choices=("x_browser",),
        default="x_browser",
        help="Browser capture provider. Defaults to x_browser.",
    )
    browser_capture_commentary_parser.add_argument(
        "--target-url",
        type=str,
        default=None,
        help="Configured public X page/list/search URL represented by the browser artifact.",
    )
    browser_capture_commentary_parser.add_argument(
        "--dom-text-file",
        type=Path,
        default=None,
        help="Rendered visible text artifact saved by Codex Browser/manual capture.",
    )
    browser_capture_commentary_parser.add_argument(
        "--page-html-file",
        type=Path,
        default=None,
        help="Optional rendered HTML artifact saved by Codex Browser/manual capture.",
    )
    browser_capture_commentary_parser.add_argument(
        "--acknowledge-terms-risk",
        action="store_true",
        help=(
            "Acknowledge that X browser capture is opt-in, low-frequency, "
            "and must not bypass login, captcha, rate limits, or restrictions."
        ),
    )
    browser_capture_commentary_parser.set_defaults(
        func=command_browser_capture_commentary
    )

    browser_capture_commentary_status_parser = subparsers.add_parser(
        "browser-capture-commentary-status",
        help="Show trader commentary browser capture run/item status.",
    )
    browser_capture_commentary_status_parser.set_defaults(
        func=command_browser_capture_commentary_status
    )

    ingest_browser_captured_commentary_parser = subparsers.add_parser(
        "ingest-browser-captured-commentary",
        help="Convert accepted browser-captured commentary items into raw commentary rows.",
    )
    ingest_browser_captured_commentary_parser.add_argument(
        "--provider",
        choices=("x_browser",),
        default="x_browser",
        help="Browser capture provider to ingest. Defaults to x_browser.",
    )
    ingest_browser_captured_commentary_parser.set_defaults(
        func=command_ingest_browser_captured_commentary
    )

    discord_capture_commentary_parser = subparsers.add_parser(
        "discord-capture-commentary",
        help="Capture authorized Discord commentary through the official bot/API route.",
    )
    discord_capture_commentary_parser.add_argument(
        "--provider",
        choices=("discord_gateway",),
        default="discord_gateway",
        help="Discord capture provider. Defaults to discord_gateway.",
    )
    discord_capture_commentary_parser.add_argument(
        "--channel-id",
        type=str,
        default=None,
        help="Discord channel ID to fetch. Defaults to the first configured channel.",
    )
    discord_capture_commentary_parser.add_argument(
        "--max-messages",
        type=int,
        default=None,
        help="Maximum messages to fetch. Defaults to configured max_messages_per_run.",
    )
    discord_capture_commentary_parser.add_argument(
        "--messages-json-file",
        type=Path,
        default=None,
        help="Optional official-API-shaped JSON fixture/export for tests or dry runs.",
    )
    discord_capture_commentary_parser.add_argument(
        "--acknowledge-permission",
        action="store_true",
        help=(
            "Acknowledge the bot is authorized for the configured channel and "
            "TOM must not bypass permissions or restrictions."
        ),
    )
    discord_capture_commentary_parser.set_defaults(
        func=command_discord_capture_commentary
    )

    discord_capture_commentary_status_parser = subparsers.add_parser(
        "discord-capture-commentary-status",
        help="Show trader commentary Discord capture run/item status.",
    )
    discord_capture_commentary_status_parser.set_defaults(
        func=command_discord_capture_commentary_status
    )

    ingest_discord_captured_commentary_parser = subparsers.add_parser(
        "ingest-discord-captured-commentary",
        help="Convert accepted Discord-captured commentary items into raw commentary rows.",
    )
    ingest_discord_captured_commentary_parser.add_argument(
        "--provider",
        choices=("discord_gateway",),
        default="discord_gateway",
        help="Discord capture provider to ingest. Defaults to discord_gateway.",
    )
    ingest_discord_captured_commentary_parser.set_defaults(
        func=command_ingest_discord_captured_commentary
    )

    load_short_interest_parser = subparsers.add_parser(
        "load-short-interest",
        help="Load source-backed short-interest rows from CSV.",
    )
    load_short_interest_parser.add_argument(
        "--file",
        type=Path,
        default=None,
        help="Short-interest CSV path. Defaults to data/signals/manual/short_interest.csv.",
    )
    load_short_interest_parser.set_defaults(func=command_load_short_interest)

    export_short_interest_backfill_parser = subparsers.add_parser(
        "export-short-interest-backfill",
        help="Export short-interest source-export templates for missing active equities.",
    )
    export_short_interest_backfill_parser.add_argument(
        "--dir",
        type=Path,
        default=None,
        help=(
            "Output directory. Defaults to "
            "data/signals/source_exports/short_interest."
        ),
    )
    export_short_interest_backfill_parser.set_defaults(
        func=command_export_short_interest_backfill
    )

    short_interest_coverage_plan_parser = subparsers.add_parser(
        "short-interest-coverage-plan",
        help="Show short-interest source coverage and projected import impact.",
    )
    short_interest_coverage_plan_parser.add_argument(
        "--dir",
        type=Path,
        default=None,
        help=(
            "Source-export directory. Defaults to "
            "data/signals/source_exports/short_interest."
        ),
    )
    short_interest_coverage_plan_parser.set_defaults(
        func=command_short_interest_coverage_plan
    )

    short_interest_missing_coverage_plan_parser = subparsers.add_parser(
        "short-interest-missing-coverage-plan",
        help="Show focused diagnostics for active equities missing short-interest rows.",
    )
    short_interest_missing_coverage_plan_parser.add_argument(
        "--dir",
        type=Path,
        default=None,
        help=(
            "Source-export directory. Defaults to "
            "data/signals/source_exports/short_interest."
        ),
    )
    short_interest_missing_coverage_plan_parser.set_defaults(
        func=command_short_interest_missing_coverage_plan
    )

    short_interest_provider_diagnostics_parser = subparsers.add_parser(
        "short-interest-provider-diagnostics",
        help="Classify provider/export readiness for a missing short-interest ticker.",
    )
    short_interest_provider_diagnostics_parser.add_argument(
        "--ticker",
        required=True,
        help="Ticker to diagnose, such as CRM.",
    )
    short_interest_provider_diagnostics_parser.add_argument(
        "--dir",
        type=Path,
        default=None,
        help=(
            "Source-export directory. Defaults to "
            "data/signals/source_exports/short_interest."
        ),
    )
    short_interest_provider_diagnostics_parser.set_defaults(
        func=command_short_interest_provider_diagnostics
    )

    resolve_short_interest_missing_sources_parser = subparsers.add_parser(
        "resolve-short-interest-missing-sources",
        help="Fetch/check only active equities missing short-interest source rows.",
    )
    resolve_short_interest_missing_sources_parser.add_argument(
        "--ticker",
        default=None,
        help="Optional missing ticker to resolve, such as CRM.",
    )
    resolve_short_interest_missing_sources_parser.add_argument(
        "--provider",
        choices=("all", "finra", "nasdaq_trader"),
        default="all",
        help="Official provider to try. Defaults to all fetchable providers.",
    )
    resolve_short_interest_missing_sources_parser.add_argument(
        "--dir",
        type=Path,
        default=None,
        help=(
            "Source-export directory. Defaults to "
            "data/signals/source_exports/short_interest."
        ),
    )
    resolve_cache_group = resolve_short_interest_missing_sources_parser.add_mutually_exclusive_group()
    resolve_cache_group.add_argument(
        "--use-cache",
        action="store_true",
        default=None,
        help="Use fresh cached provider responses when available.",
    )
    resolve_cache_group.add_argument(
        "--no-cache",
        action="store_false",
        dest="use_cache",
        help="Bypass cache and attempt live provider fetches.",
    )
    resolve_short_interest_missing_sources_parser.add_argument(
        "--force-refresh",
        action="store_true",
        help="Ignore fresh caches and refresh provider payloads.",
    )
    resolve_short_interest_missing_sources_parser.set_defaults(
        func=command_resolve_short_interest_missing_sources
    )

    export_short_interest_missing_provider_template_parser = subparsers.add_parser(
        "export-short-interest-missing-provider-template",
        help="Export a focused provider backfill template for missing short-interest tickers.",
    )
    export_short_interest_missing_provider_template_parser.add_argument(
        "--dir",
        type=Path,
        default=None,
        help=(
            "Output directory. Defaults to "
            "data/signals/source_exports/short_interest."
        ),
    )
    export_short_interest_missing_provider_template_parser.set_defaults(
        func=command_export_short_interest_missing_provider_template
    )

    short_interest_source_status_parser = subparsers.add_parser(
        "short-interest-source-status",
        help="Show short-interest source-backed coverage by ticker.",
    )
    short_interest_source_status_parser.add_argument(
        "--missing-only",
        action="store_true",
        help="Show only active equities missing source-backed short-interest rows.",
    )
    short_interest_source_status_parser.set_defaults(
        func=command_short_interest_source_status
    )

    validate_short_interest_backfill_parser = subparsers.add_parser(
        "validate-short-interest-backfill",
        help="Validate short-interest source-export CSV rows without importing.",
    )
    validate_short_interest_backfill_parser.add_argument(
        "--dir",
        type=Path,
        default=None,
        help=(
            "Source-export directory. Defaults to "
            "data/signals/source_exports/short_interest."
        ),
    )
    validate_short_interest_backfill_parser.set_defaults(
        func=command_validate_short_interest_backfill
    )

    preview_short_interest_import_parser = subparsers.add_parser(
        "preview-short-interest-import",
        help="Preview source-backed short-interest coverage after import.",
    )
    preview_short_interest_import_parser.add_argument(
        "--dir",
        type=Path,
        default=None,
        help=(
            "Source-export directory. Defaults to "
            "data/signals/source_exports/short_interest."
        ),
    )
    preview_short_interest_import_parser.set_defaults(
        func=command_preview_short_interest_import
    )

    import_short_interest_source_exports_parser = subparsers.add_parser(
        "import-short-interest-source-exports",
        help="Import validated short-interest source-export CSV rows.",
    )
    import_short_interest_source_exports_parser.add_argument(
        "--dir",
        type=Path,
        default=None,
        help=(
            "Source-export directory. Defaults to "
            "data/signals/source_exports/short_interest."
        ),
    )
    import_short_interest_source_exports_parser.set_defaults(
        func=command_import_short_interest_source_exports
    )

    apply_short_interest_provider_backfill_parser = subparsers.add_parser(
        "apply-short-interest-provider-backfill",
        help="Dry-run or confirmed apply for missing short-interest provider rows.",
    )
    apply_short_interest_provider_backfill_parser.add_argument(
        "--dir",
        type=Path,
        default=None,
        help=(
            "Source-export directory. Defaults to "
            "data/signals/source_exports/short_interest."
        ),
    )
    apply_short_interest_provider_backfill_parser.add_argument(
        "--confirm",
        action="store_true",
        help="Actually import validated rows. Without this flag, the command is a dry run.",
    )
    apply_short_interest_provider_backfill_parser.set_defaults(
        func=command_apply_short_interest_provider_backfill
    )

    fetch_short_interest_sources_parser = subparsers.add_parser(
        "fetch-short-interest-sources",
        help="Fetch official/provider short-interest source rows into provider_export.csv.",
    )
    fetch_short_interest_sources_parser.add_argument(
        "--provider",
        choices=("all", "finra", "nasdaq_trader"),
        default="all",
        help="Short-interest provider to fetch. Defaults to all fetchable providers.",
    )
    fetch_short_interest_sources_parser.add_argument(
        "--ticker",
        default=None,
        help="Optional ticker to fetch.",
    )
    fetch_short_interest_sources_parser.add_argument(
        "--max-tickers",
        type=int,
        default=None,
        help="Maximum active equity tickers to fetch. Defaults to config budget.",
    )
    cache_group = fetch_short_interest_sources_parser.add_mutually_exclusive_group()
    cache_group.add_argument(
        "--use-cache",
        action="store_true",
        default=None,
        help="Use fresh cached provider responses when available.",
    )
    cache_group.add_argument(
        "--no-cache",
        dest="use_cache",
        action="store_false",
        help="Bypass cached provider responses.",
    )
    fetch_short_interest_sources_parser.add_argument(
        "--force-refresh",
        action="store_true",
        help="Force live provider requests even when cache is fresh.",
    )
    fetch_short_interest_sources_parser.set_defaults(
        func=command_fetch_short_interest_sources
    )

    normalize_short_interest_provider_export_parser = subparsers.add_parser(
        "normalize-short-interest-provider-export",
        help="Normalize a source-backed short-interest provider export into provider_export.csv.",
    )
    normalize_short_interest_provider_export_parser.add_argument(
        "--provider",
        choices=("finra", "nasdaq_trader", "nyse", "broker", "generic"),
        required=True,
        help="Provider/export schema to normalize.",
    )
    normalize_short_interest_provider_export_parser.add_argument(
        "--file",
        type=Path,
        required=True,
        help="Provider export file path.",
    )
    normalize_short_interest_provider_export_parser.set_defaults(
        func=command_normalize_short_interest_provider_export
    )

    short_interest_provider_status_parser = subparsers.add_parser(
        "short-interest-provider-status",
        help="Show short-interest provider/cache/export readiness.",
    )
    short_interest_provider_status_parser.set_defaults(
        func=command_short_interest_provider_status
    )

    fetch_news_catalyst_sources_parser = subparsers.add_parser(
        "fetch-news-catalyst-sources",
        help="Fetch news/catalyst source snapshots from configured providers.",
    )
    fetch_news_catalyst_sources_parser.add_argument(
        "--provider",
        choices=(
            "all",
            "alpha_vantage",
            "marketaux",
            "eodhd",
            "finnhub",
            "fmp",
            "x_recent_search",
            "truth_social_public",
        ),
        default="all",
        help="Provider to fetch. Defaults to all enabled API providers.",
    )
    fetch_news_catalyst_sources_parser.add_argument(
        "--ticker",
        type=str,
        default=None,
        help="Optional equity ticker to fetch. Defaults to all active equities.",
    )
    fetch_news_catalyst_sources_parser.add_argument(
        "--max-tickers",
        type=int,
        default=None,
        help=(
            "Maximum live provider requests per provider for this run. "
            "Defaults to the configured news/catalyst provider request budget."
        ),
    )
    fetch_news_catalyst_sources_parser.add_argument(
        "--force-refresh",
        action="store_true",
        help="Ignore fresh cached provider payloads and make live provider requests.",
    )
    fetch_news_catalyst_sources_parser.add_argument(
        "--coverage-plan",
        action="store_true",
        help="Fetch only tickers selected by the news/catalyst coverage planner.",
    )
    fetch_news_catalyst_sources_parser.add_argument(
        "--provider-upgrade",
        action="store_true",
        help=(
            "Friendly alias for --coverage-plan --coverage-mode provider-upgrade."
        ),
    )
    fetch_news_catalyst_sources_parser.add_argument(
        "--coverage-mode",
        choices=("missing", "provider-upgrade", "all"),
        default="all",
        help=(
            "Coverage-plan mode to fetch. Defaults to all, which prioritizes "
            "missing numeric rows and then provider-native upgrades."
        ),
    )
    cache_group = fetch_news_catalyst_sources_parser.add_mutually_exclusive_group()
    cache_group.add_argument(
        "--use-cache",
        dest="use_cache",
        action="store_true",
        default=None,
        help="Use fresh cached provider payloads before live requests.",
    )
    cache_group.add_argument(
        "--no-cache",
        dest="use_cache",
        action="store_false",
        help="Disable provider payload cache reads for this fetch.",
    )
    fetch_news_catalyst_sources_parser.set_defaults(
        func=command_fetch_news_catalyst_sources
    )

    news_catalyst_coverage_plan_parser = subparsers.add_parser(
        "news-catalyst-coverage-plan",
        help="Plan missing/stale news/catalyst numeric source coverage work.",
    )
    news_catalyst_coverage_plan_parser.add_argument(
        "--max-tickers",
        type=int,
        default=None,
        help=(
            "Maximum tickers to put in the current coverage plan. "
            "Defaults to the configured provider request budget."
        ),
    )
    news_catalyst_coverage_plan_parser.add_argument(
        "--mode",
        choices=("missing", "provider-upgrade", "all"),
        default="all",
        help=(
            "Coverage queue to build. Use missing for no numeric rows, "
            "provider-upgrade for text-derived-only rows, or all."
        ),
    )
    news_catalyst_coverage_plan_parser.add_argument(
        "--refresh-template",
        action="store_true",
        help="Regenerate the selected source-export queue template.",
    )
    news_catalyst_coverage_plan_parser.set_defaults(
        func=command_news_catalyst_coverage_plan
    )

    import_news_catalyst_sources_parser = subparsers.add_parser(
        "import-news-catalyst-source-exports",
        help="Import audited news/catalyst source-export CSV files.",
    )
    import_news_catalyst_sources_parser.add_argument(
        "--dir",
        type=Path,
        default=None,
        help=(
            "Directory of source-export CSV files. Defaults to "
            "data/signals/source_exports/news_catalysts."
        ),
    )
    import_news_catalyst_sources_parser.set_defaults(
        func=command_import_news_catalyst_source_exports
    )

    compute_news_catalyst_text_backfill_parser = subparsers.add_parser(
        "compute-news-catalyst-text-backfill",
        help=(
            "Derive low-confidence numeric news/catalyst snapshots from "
            "source-backed text rows."
        ),
    )
    compute_news_catalyst_text_backfill_parser.add_argument(
        "--ticker",
        type=str,
        default=None,
        help="Optional equity ticker to backfill. Defaults to all eligible source rows.",
    )
    compute_news_catalyst_text_backfill_parser.set_defaults(
        func=command_compute_news_catalyst_text_backfill
    )

    export_news_catalyst_provider_backfill_parser = subparsers.add_parser(
        "export-news-catalyst-provider-backfill",
        help="Export a provider-native news/catalyst backfill CSV package.",
    )
    export_news_catalyst_provider_backfill_parser.add_argument(
        "--dir",
        type=Path,
        default=None,
        help=(
            "Output directory for the backfill package. Defaults to "
            "data/signals/source_exports/news_catalysts/provider_native_backfill."
        ),
    )
    export_news_catalyst_provider_backfill_parser.set_defaults(
        func=command_export_news_catalyst_provider_backfill
    )

    validate_news_catalyst_provider_backfill_parser = subparsers.add_parser(
        "validate-news-catalyst-provider-backfill",
        help="Dry-run validate provider-native news/catalyst backfill CSV rows.",
    )
    validate_news_catalyst_provider_backfill_parser.add_argument(
        "--dir",
        type=Path,
        default=None,
        help=(
            "Backfill package directory. Defaults to "
            "data/signals/source_exports/news_catalysts/provider_native_backfill."
        ),
    )
    validate_news_catalyst_provider_backfill_parser.set_defaults(
        func=command_validate_news_catalyst_provider_backfill
    )

    preview_news_catalyst_provider_upgrade_parser = subparsers.add_parser(
        "preview-news-catalyst-provider-upgrade",
        help="Preview provider-native news/catalyst coverage after backfill import.",
    )
    preview_news_catalyst_provider_upgrade_parser.add_argument(
        "--dir",
        type=Path,
        default=None,
        help=(
            "Backfill package directory. Defaults to "
            "data/signals/source_exports/news_catalysts/provider_native_backfill."
        ),
    )
    preview_news_catalyst_provider_upgrade_parser.set_defaults(
        func=command_preview_news_catalyst_provider_upgrade
    )

    normalize_news_catalyst_provider_export_parser = subparsers.add_parser(
        "normalize-news-catalyst-provider-export",
        help="Normalize provider/export news-catalyst rows into provider-native backfill CSV rows.",
    )
    normalize_news_catalyst_provider_export_parser.add_argument(
        "--provider",
        choices=("marketaux", "eodhd", "x", "licensed", "generic"),
        required=True,
        help="Provider/export schema to normalize.",
    )
    normalize_news_catalyst_provider_export_parser.add_argument(
        "--file",
        type=Path,
        required=True,
        help="Provider export CSV file to normalize.",
    )
    normalize_news_catalyst_provider_export_parser.set_defaults(
        func=command_normalize_news_catalyst_provider_export
    )

    news_catalyst_provider_backfill_status_parser = subparsers.add_parser(
        "news-catalyst-provider-backfill-status",
        help="Show provider-native backfill validation, projected coverage, and apply readiness.",
    )
    news_catalyst_provider_backfill_status_parser.add_argument(
        "--dir",
        type=Path,
        default=None,
        help=(
            "Backfill package directory. Defaults to "
            "data/signals/source_exports/news_catalysts/provider_native_backfill."
        ),
    )
    news_catalyst_provider_backfill_status_parser.add_argument(
        "--allow-partial",
        action="store_true",
        help="Show apply readiness if partial provider-native upgrades are allowed.",
    )
    news_catalyst_provider_backfill_status_parser.set_defaults(
        func=command_news_catalyst_provider_backfill_status
    )

    apply_news_catalyst_provider_backfill_parser = subparsers.add_parser(
        "apply-news-catalyst-provider-backfill",
        help="Dry-run or confirmed-apply provider-native news/catalyst backfill rows.",
    )
    apply_news_catalyst_provider_backfill_parser.add_argument(
        "--dir",
        type=Path,
        default=None,
        help=(
            "Backfill package directory. Defaults to "
            "data/signals/source_exports/news_catalysts/provider_native_backfill."
        ),
    )
    apply_news_catalyst_provider_backfill_parser.add_argument(
        "--confirm",
        action="store_true",
        help="Actually import, aggregate, load, compute, and validate when guards pass.",
    )
    apply_news_catalyst_provider_backfill_parser.add_argument(
        "--allow-partial",
        action="store_true",
        help="Allow confirmed apply when at least one provider-native ticker improves coverage.",
    )
    apply_news_catalyst_provider_backfill_parser.set_defaults(
        func=command_apply_news_catalyst_provider_backfill
    )

    aggregate_news_catalyst_sources_parser = subparsers.add_parser(
        "aggregate-news-catalyst-sources",
        help="Aggregate news/catalyst source snapshots into final news/catalyst rows.",
    )
    aggregate_news_catalyst_sources_parser.add_argument(
        "--ticker",
        type=str,
        default=None,
        help="Optional equity ticker to aggregate. Defaults to all source snapshots.",
    )
    aggregate_news_catalyst_sources_parser.set_defaults(
        func=command_aggregate_news_catalyst_sources
    )

    news_catalyst_source_status_parser = subparsers.add_parser(
        "news-catalyst-source-status",
        help="Show news/catalyst provider, source, and aggregate coverage.",
    )
    news_catalyst_source_status_parser.add_argument(
        "--missing-only",
        action="store_true",
        help="Show only active equities missing source-backed numeric news/catalyst rows.",
    )
    news_catalyst_source_status_parser.add_argument(
        "--provider-warnings",
        action="store_true",
        help="Show provider warning summary instead of the full ticker table.",
    )
    news_catalyst_source_status_parser.add_argument(
        "--provider-upgrade-only",
        action="store_true",
        help="Show only active equities that have text-derived numeric rows but no provider-native numeric rows.",
    )
    news_catalyst_source_status_parser.set_defaults(
        func=command_news_catalyst_source_status
    )

    news_catalyst_provider_upgrade_status_parser = subparsers.add_parser(
        "news-catalyst-provider-upgrade-status",
        help="Show provider-native news/catalyst upgrade readiness.",
    )
    news_catalyst_provider_upgrade_status_parser.add_argument(
        "--max-tickers",
        type=int,
        default=None,
        help=(
            "Maximum provider-upgrade queue tickers to display. Defaults to "
            "the configured provider request budget."
        ),
    )
    news_catalyst_provider_upgrade_status_parser.set_defaults(
        func=command_news_catalyst_provider_upgrade_status
    )

    test_news_catalyst_provider_parser = subparsers.add_parser(
        "test-news-catalyst-provider",
        help="Smoke-test provider-native news/catalyst API readiness safely.",
    )
    test_news_catalyst_provider_parser.add_argument(
        "--provider",
        choices=("all", "marketaux", "eodhd", "x_recent_search"),
        default="all",
        help="Provider to smoke test. Defaults to all provider-native upgrade providers.",
    )
    test_news_catalyst_provider_parser.add_argument(
        "--ticker",
        type=str,
        default="AAPL",
        help="Active equity ticker to test. Defaults to AAPL.",
    )
    test_news_catalyst_provider_parser.set_defaults(
        func=command_test_news_catalyst_provider
    )

    derive_analyst_revisions_parser = subparsers.add_parser(
        "derive-analyst-revisions",
        help="Derive final analyst revision rows from an audited source-export CSV.",
    )
    derive_analyst_revisions_parser.add_argument(
        "--file",
        type=Path,
        default=None,
        help=(
            "Analyst revision source-export CSV path. Defaults to "
            "data/signals/source_exports/analyst_revision_source_export.csv."
        ),
    )
    derive_analyst_revisions_parser.set_defaults(
        func=command_derive_analyst_revisions
    )

    load_etf_navs_parser = subparsers.add_parser(
        "load-etf-navs", help="Load manual ETF NAVs from CSV."
    )
    load_etf_navs_parser.add_argument(
        "--file",
        type=Path,
        default=None,
        help="ETF NAV CSV path. Defaults to data/etf/manual/etf_navs.csv.",
    )
    load_etf_navs_parser.set_defaults(func=command_load_etf_navs)

    load_etf_holdings_parser = subparsers.add_parser(
        "load-etf-holdings", help="Load manual ETF holdings from CSV."
    )
    load_etf_holdings_parser.add_argument(
        "--file",
        type=Path,
        default=None,
        help="ETF holdings CSV path. Defaults to data/etf/manual/etf_holdings.csv.",
    )
    load_etf_holdings_parser.set_defaults(func=command_load_etf_holdings)

    seed_fundamentals_parser = subparsers.add_parser(
        "seed-fundamentals",
        help="Fetch SEC companyfacts, update fundamentals CSV, and load rows.",
    )
    seed_fundamentals_parser.add_argument(
        "--ticker",
        type=str,
        default=None,
        help="Optional ticker to seed. Defaults to all tickers in configs/cik_map.csv.",
    )
    seed_fundamentals_parser.add_argument(
        "--years",
        type=int,
        default=None,
        help="Number of latest fiscal years to seed. Defaults to config fundamentals.seed_years.",
    )
    seed_fundamentals_parser.add_argument(
        "--refresh-cache",
        action="store_true",
        help="Fetch fresh SEC companyfacts JSON even when cached raw data exists.",
    )
    seed_fundamentals_parser.set_defaults(func=command_seed_fundamentals)

    compute_targets_parser = subparsers.add_parser(
        "compute-targets", help="Compute non-alerting valuation target ranges."
    )
    compute_targets_parser.add_argument(
        "--ticker",
        type=str,
        default=None,
        help="Optional ticker to compute. Defaults to all active assets.",
    )
    compute_targets_parser.set_defaults(func=command_compute_targets)

    etf_status_parser = subparsers.add_parser(
        "etf-status", help="Show ETF NAV, holdings, and target readiness by ticker."
    )
    etf_status_parser.set_defaults(func=command_etf_status)

    valuation_status_parser = subparsers.add_parser(
        "valuation-status", help="Show target range and valuation coverage by ticker."
    )
    valuation_status_parser.set_defaults(func=command_valuation_status)

    compute_revision_signals_parser = subparsers.add_parser(
        "compute-revision-signals",
        help="Compute Phase 10A analyst revision shadow signals.",
    )
    compute_revision_signals_parser.add_argument(
        "--ticker",
        type=str,
        default=None,
        help="Optional ticker to compute. Defaults to all active assets.",
    )
    compute_revision_signals_parser.set_defaults(func=command_compute_revision_signals)

    compute_news_catalyst_signals_parser = subparsers.add_parser(
        "compute-news-catalyst-signals",
        help="Compute Phase 10E news/catalyst shadow signals.",
    )
    compute_news_catalyst_signals_parser.add_argument(
        "--ticker",
        type=str,
        default=None,
        help="Optional ticker to compute. Defaults to all active assets.",
    )
    compute_news_catalyst_signals_parser.set_defaults(
        func=command_compute_news_catalyst_signals
    )

    parse_trader_commentary_claims_parser = subparsers.add_parser(
        "parse-trader-commentary-claims",
        help="Parse structured claims from stored trader commentary.",
    )
    parse_trader_commentary_claims_parser.add_argument(
        "--commentary-id",
        type=int,
        default=None,
        help="Optional raw commentary row id to parse.",
    )
    parse_trader_commentary_claims_parser.add_argument(
        "--ticker",
        type=str,
        default=None,
        help="Optional ticker filter for parsed claims.",
    )
    parse_trader_commentary_claims_parser.set_defaults(
        func=command_parse_trader_commentary_claims
    )

    fetch_insider_transactions_parser = subparsers.add_parser(
        "fetch-insider-transactions",
        help="Fetch SEC Form 4 insider activity source snapshots.",
    )
    fetch_insider_transactions_parser.add_argument(
        "--ticker",
        type=str,
        default=None,
        help="Optional equity ticker to fetch. Defaults to all active equities.",
    )
    fetch_insider_transactions_parser.add_argument(
        "--refresh-cache",
        action="store_true",
        help="Compatibility alias for --force-refresh.",
    )
    fetch_insider_transactions_parser.add_argument(
        "--force-refresh",
        action="store_true",
        help="Ignore cached SEC submissions/Form 4 documents.",
    )
    fetch_insider_transactions_parser.add_argument(
        "--max-tickers",
        type=int,
        default=None,
        help="Maximum active equity tickers to fetch this run. Defaults to config.",
    )
    insider_cache_group = fetch_insider_transactions_parser.add_mutually_exclusive_group()
    insider_cache_group.add_argument(
        "--use-cache",
        dest="use_cache",
        action="store_true",
        default=None,
        help="Use cached SEC submissions/Form 4 documents when available.",
    )
    insider_cache_group.add_argument(
        "--no-cache",
        dest="use_cache",
        action="store_false",
        help="Disable SEC cache reads for this fetch.",
    )
    fetch_insider_transactions_parser.set_defaults(
        func=command_fetch_insider_transactions
    )

    compute_insider_signals_parser = subparsers.add_parser(
        "compute-insider-signals",
        help="Compute Phase 10F SEC insider activity shadow signals.",
    )
    compute_insider_signals_parser.add_argument(
        "--ticker",
        type=str,
        default=None,
        help="Optional ticker to compute. Defaults to all active assets.",
    )
    compute_insider_signals_parser.set_defaults(func=command_compute_insider_signals)

    compute_short_interest_signals_parser = subparsers.add_parser(
        "compute-short-interest-signals",
        help="Compute Phase 10G short-interest shadow signals.",
    )
    compute_short_interest_signals_parser.add_argument(
        "--ticker",
        type=str,
        default=None,
        help="Optional ticker to compute. Defaults to all active assets.",
    )
    compute_short_interest_signals_parser.set_defaults(
        func=command_compute_short_interest_signals
    )

    signal_status_parser = subparsers.add_parser(
        "signal-status", help="Show latest advanced signal coverage by ticker."
    )
    signal_status_parser.set_defaults(func=command_signal_status)

    news_catalyst_status_parser = subparsers.add_parser(
        "news-catalyst-status",
        help="Show latest news/catalyst shadow signal coverage by ticker.",
    )
    news_catalyst_status_parser.set_defaults(func=command_news_catalyst_status)

    trader_commentary_status_parser = subparsers.add_parser(
        "trader-commentary-status",
        help="Show trader commentary source, parsed-claim, and validation coverage.",
    )
    trader_commentary_status_parser.set_defaults(func=command_trader_commentary_status)

    trader_commentary_parse_review_parser = subparsers.add_parser(
        "trader-commentary-parse-review",
        help="Review parsed commentary claims, unmapped instruments, and unsupported tickers.",
    )
    trader_commentary_parse_review_parser.set_defaults(
        func=command_trader_commentary_parse_review
    )

    insider_status_parser = subparsers.add_parser(
        "insider-status",
        help="Show latest SEC insider activity shadow signal coverage by ticker.",
    )
    insider_status_parser.set_defaults(func=command_insider_status)

    short_interest_status_parser = subparsers.add_parser(
        "short-interest-status",
        help="Show latest short-interest shadow signal coverage by ticker.",
    )
    short_interest_status_parser.set_defaults(func=command_short_interest_status)

    insider_source_status_parser = subparsers.add_parser(
        "insider-source-status",
        help="Show SEC insider source coverage and fetch health by ticker.",
    )
    insider_source_status_parser.add_argument(
        "--verbose",
        action="store_true",
        help="Show raw accession-level SEC warning details instead of compact summaries.",
    )
    insider_source_status_parser.set_defaults(func=command_insider_source_status)

    validate_revision_signals_parser = subparsers.add_parser(
        "validate-revision-signals",
        help="Validate analyst revision shadow signals against stored prices.",
    )
    validate_revision_signals_parser.add_argument(
        "--ticker",
        type=str,
        default=None,
        help="Optional ticker to validate. Defaults to all active assets.",
    )
    validate_revision_signals_parser.set_defaults(func=command_validate_revision_signals)

    validate_news_catalyst_signals_parser = subparsers.add_parser(
        "validate-news-catalyst-signals",
        help="Validate news/catalyst shadow signals against stored prices.",
    )
    validate_news_catalyst_signals_parser.add_argument(
        "--ticker",
        type=str,
        default=None,
        help="Optional ticker to validate. Defaults to all active assets.",
    )
    validate_news_catalyst_signals_parser.set_defaults(
        func=command_validate_news_catalyst_signals
    )

    validate_trader_commentary_claims_parser = subparsers.add_parser(
        "validate-trader-commentary-claims",
        help="Validate parsed trader commentary claims against stored prices.",
    )
    validate_trader_commentary_claims_parser.add_argument(
        "--ticker",
        type=str,
        default=None,
        help="Optional ticker to validate. Defaults to all parsed claims.",
    )
    validate_trader_commentary_claims_parser.set_defaults(
        func=command_validate_trader_commentary_claims
    )

    validate_insider_signals_parser = subparsers.add_parser(
        "validate-insider-signals",
        help="Validate insider activity shadow signals against stored prices.",
    )
    validate_insider_signals_parser.add_argument(
        "--ticker",
        type=str,
        default=None,
        help="Optional ticker to validate. Defaults to all active assets.",
    )
    validate_insider_signals_parser.set_defaults(func=command_validate_insider_signals)

    validate_short_interest_signals_parser = subparsers.add_parser(
        "validate-short-interest-signals",
        help="Validate short-interest shadow signals against stored prices.",
    )
    validate_short_interest_signals_parser.add_argument(
        "--ticker",
        type=str,
        default=None,
        help="Optional ticker to validate. Defaults to all active assets.",
    )
    validate_short_interest_signals_parser.set_defaults(
        func=command_validate_short_interest_signals
    )

    revision_validation_report_parser = subparsers.add_parser(
        "revision-validation-report",
        help="Print analyst revision shadow-signal validation results.",
    )
    revision_validation_report_parser.set_defaults(
        func=command_revision_validation_report
    )

    news_catalyst_validation_report_parser = subparsers.add_parser(
        "news-catalyst-validation-report",
        help="Print news/catalyst shadow-signal validation results.",
    )
    news_catalyst_validation_report_parser.set_defaults(
        func=command_news_catalyst_validation_report
    )

    trader_commentary_validation_report_parser = subparsers.add_parser(
        "trader-commentary-validation-report",
        help="Print trader commentary claim validation results.",
    )
    trader_commentary_validation_report_parser.set_defaults(
        func=command_trader_commentary_validation_report
    )

    insider_validation_report_parser = subparsers.add_parser(
        "insider-validation-report",
        help="Print insider activity shadow-signal validation results.",
    )
    insider_validation_report_parser.set_defaults(
        func=command_insider_validation_report
    )

    short_interest_validation_report_parser = subparsers.add_parser(
        "short-interest-validation-report",
        help="Print short-interest shadow-signal validation results.",
    )
    short_interest_validation_report_parser.set_defaults(
        func=command_short_interest_validation_report
    )

    revision_evidence_report_parser = subparsers.add_parser(
        "revision-evidence-report",
        help="Print analyst revision source coverage and evidence-gate decision.",
    )
    revision_evidence_report_parser.set_defaults(
        func=command_revision_evidence_report
    )

    revision_source_status_parser = subparsers.add_parser(
        "revision-source-status",
        help="Show analyst revision source-export and source-backed ticker coverage.",
    )
    revision_source_status_parser.set_defaults(func=command_revision_source_status)

    fetch_revision_sources_parser = subparsers.add_parser(
        "fetch-revision-sources",
        help="Fetch analyst revision source snapshots from configured providers.",
    )
    fetch_revision_sources_parser.add_argument(
        "--provider",
        choices=(
            "all",
            "fmp",
            "alpha_vantage",
            "business_quant",
            "finnhub",
            "yfinance",
            "ibkr",
            "google_finance",
        ),
        default="all",
        help="Provider to fetch. Defaults to all enabled API providers.",
    )
    fetch_revision_sources_parser.add_argument(
        "--ticker",
        type=str,
        default=None,
        help="Optional equity ticker to fetch. Defaults to all active equities.",
    )
    fetch_revision_sources_parser.set_defaults(func=command_fetch_revision_sources)

    import_revision_sources_parser = subparsers.add_parser(
        "import-revision-source-exports",
        help="Import audited analyst revision source-export CSV files.",
    )
    import_revision_sources_parser.add_argument(
        "--dir",
        type=Path,
        default=None,
        help="Directory of source-export CSV files. Defaults to data/signals/source_exports.",
    )
    import_revision_sources_parser.set_defaults(
        func=command_import_revision_source_exports
    )

    aggregate_revision_sources_parser = subparsers.add_parser(
        "aggregate-revision-sources",
        help="Aggregate analyst revision source snapshots into final revision rows.",
    )
    aggregate_revision_sources_parser.add_argument(
        "--ticker",
        type=str,
        default=None,
        help="Optional equity ticker to aggregate. Defaults to all source snapshots.",
    )
    aggregate_revision_sources_parser.set_defaults(
        func=command_aggregate_revision_sources
    )

    revision_provider_status_parser = subparsers.add_parser(
        "revision-provider-status",
        help="Show analyst revision provider availability without printing keys.",
    )
    revision_provider_status_parser.set_defaults(func=command_revision_provider_status)

    compute_scores_parser = subparsers.add_parser(
        "compute-scores", help="Compute explainable Phase 4 opportunity scores."
    )
    compute_scores_parser.add_argument(
        "--ticker",
        type=str,
        default=None,
        help="Optional ticker to score. Defaults to all active assets.",
    )
    compute_scores_parser.add_argument(
        "--asset-type",
        choices=("equity", "etf"),
        default=None,
        help="Optional asset type filter.",
    )
    compute_scores_parser.set_defaults(func=command_compute_scores)

    score_status_parser = subparsers.add_parser(
        "score-status", help="Show latest score coverage by ticker."
    )
    score_status_parser.set_defaults(func=command_score_status)

    compute_alerts_parser = subparsers.add_parser(
        "compute-alerts", help="Compute Phase 5A daily equity alerts."
    )
    compute_alerts_parser.add_argument(
        "--ticker",
        type=str,
        default=None,
        help="Optional ticker to evaluate. Defaults to all active assets.",
    )
    compute_alerts_parser.add_argument(
        "--asset-type",
        choices=("equity", "etf"),
        default=None,
        help="Optional asset type filter.",
    )
    compute_alerts_parser.set_defaults(func=command_compute_alerts)

    alert_status_parser = subparsers.add_parser(
        "alert-status", help="Show latest alert coverage by ticker."
    )
    alert_status_parser.set_defaults(func=command_alert_status)

    update_alert_outcomes_parser = subparsers.add_parser(
        "update-alert-outcomes",
        help="Update Phase 7A/7B alert outcome tracking rows.",
    )
    update_alert_outcomes_parser.add_argument(
        "--ticker",
        type=str,
        default=None,
        help="Optional ticker to update. Defaults to all stored alerts.",
    )
    update_alert_outcomes_parser.add_argument(
        "--asset-type",
        choices=("all", "equity", "etf"),
        default="all",
        help="Optional asset type filter. Defaults to all alert outcomes.",
    )
    update_alert_outcomes_parser.set_defaults(func=command_update_alert_outcomes)

    outcome_status_parser = subparsers.add_parser(
        "outcome-status",
        help="Show latest alert outcome tracking rows.",
    )
    outcome_status_parser.set_defaults(func=command_outcome_status)

    validation_report_parser = subparsers.add_parser(
        "validation-report",
        help="Print a simple alert outcome validation report.",
    )
    validation_report_parser.set_defaults(func=command_validation_report)

    load_portfolio_parser = subparsers.add_parser(
        "load-portfolio",
        help="Load manual portfolio positions and cash from CSV.",
    )
    load_portfolio_parser.add_argument(
        "--positions-file",
        type=Path,
        default=None,
        help="Portfolio positions CSV path. Defaults to data/portfolio/manual/positions.csv.",
    )
    load_portfolio_parser.add_argument(
        "--cash-file",
        type=Path,
        default=None,
        help="Portfolio cash CSV path. Defaults to data/portfolio/manual/cash.csv.",
    )
    load_portfolio_parser.set_defaults(func=command_load_portfolio)

    compute_portfolio_parser = subparsers.add_parser(
        "compute-portfolio-context",
        help="Compute read-only portfolio review categories and sizing guidance.",
    )
    compute_portfolio_parser.add_argument(
        "--ticker",
        type=str,
        default=None,
        help="Optional ticker to compute. Defaults to all active assets.",
    )
    compute_portfolio_parser.set_defaults(func=command_compute_portfolio_context)

    portfolio_status_parser = subparsers.add_parser(
        "portfolio-status",
        help="Show latest portfolio review and sizing guidance by ticker.",
    )
    portfolio_status_parser.set_defaults(func=command_portfolio_status)

    verify_universe_parser = subparsers.add_parser(
        "verify-universe", help="Show pre-alert readiness for all active assets."
    )
    verify_universe_parser.add_argument(
        "--intraday",
        action="store_true",
        help="Record checks as intraday readiness diagnostics.",
    )
    verify_universe_parser.set_defaults(func=command_verify_universe)

    verify_ticker_parser = subparsers.add_parser(
        "verify-ticker", help="Show pre-alert readiness for one ticker."
    )
    verify_ticker_parser.add_argument("--ticker", required=True, help="Ticker to verify.")
    verify_ticker_parser.add_argument(
        "--intraday",
        action="store_true",
        help="Record checks as intraday readiness diagnostics.",
    )
    verify_ticker_parser.set_defaults(func=command_verify_ticker)

    refresh_data_parser = subparsers.add_parser(
        "refresh-data", help="Run the scheduler-friendly daily refresh pipeline."
    )
    refresh_data_parser.add_argument(
        "--ticker",
        type=str,
        default=None,
        help="Optional ticker to refresh. Defaults to all active assets.",
    )
    refresh_data_parser.add_argument(
        "--daily",
        action="store_true",
        default=True,
        help="Run as the daily source-of-truth refresh.",
    )
    refresh_data_parser.add_argument(
        "--daily-only",
        action="store_true",
        dest="skip_ibkr",
        help="Skip optional IBKR quote/NAV steps.",
    )
    refresh_data_parser.add_argument(
        "--include-quotes",
        action="store_true",
        help="Also run optional IBKR quote and ETF NAV steps.",
    )
    refresh_data_parser.set_defaults(func=command_refresh_data)

    probe_market_parser = subparsers.add_parser(
        "probe-market", help="Run a lightweight intraday market probe."
    )
    probe_market_parser.add_argument(
        "--source",
        choices=("ibkr",),
        default="ibkr",
        help="Intraday probe source.",
    )
    probe_market_parser.add_argument(
        "--ticker",
        type=str,
        default=None,
        help="Optional ticker to probe. Defaults to all active assets.",
    )
    probe_market_parser.set_defaults(func=command_probe_market)

    ibkr_status_parser = subparsers.add_parser(
        "ibkr-status", help="Check local IBKR Gateway/TWS API connectivity."
    )
    ibkr_status_parser.add_argument(
        "--live",
        action="store_true",
        help="Use the configured live port instead of the paper port.",
    )
    ibkr_status_parser.set_defaults(func=command_ibkr_status)

    ibkr_probe_parser = subparsers.add_parser(
        "ibkr-probe", help="Run a read-only IBKR probe for one ticker."
    )
    ibkr_probe_parser.add_argument("--ticker", required=True, help="Ticker to probe.")
    ibkr_probe_parser.set_defaults(func=command_ibkr_probe)

    update_quotes_parser = subparsers.add_parser(
        "update-quotes", help="Store latest quote snapshots."
    )
    update_quotes_parser.add_argument(
        "--source",
        choices=("ibkr",),
        default="ibkr",
        help="Quote snapshot source.",
    )
    update_quotes_parser.add_argument(
        "--ticker",
        type=str,
        default=None,
        help="Optional ticker to update. Defaults to all active assets.",
    )
    update_quotes_parser.set_defaults(func=command_update_quotes)

    update_etf_navs_parser = subparsers.add_parser(
        "update-etf-navs", help="Update ETF NAV rows from IBKR or CSV."
    )
    update_etf_navs_parser.add_argument(
        "--source",
        choices=("auto", "ibkr", "csv"),
        default="auto",
        help="ETF NAV source. Auto tries IBKR then CSV fallback.",
    )
    update_etf_navs_parser.add_argument(
        "--ticker",
        type=str,
        default=None,
        help="Optional ETF ticker to update. Defaults to all active ETF assets.",
    )
    update_etf_navs_parser.set_defaults(func=command_update_etf_navs)

    compute_technical_parser = subparsers.add_parser(
        "compute-technical-signals",
        help="Compute Phase 11B support/resistance and trend signals.",
    )
    _add_common_options(compute_technical_parser)
    compute_technical_parser.add_argument("--ticker", default=None)
    compute_technical_parser.set_defaults(func=command_compute_technical_signals)

    compute_regime_parser = subparsers.add_parser(
        "compute-regime-signals",
        help="Compute Phase 11B market regime and sector-rotation signals.",
    )
    _add_common_options(compute_regime_parser)
    compute_regime_parser.set_defaults(func=command_compute_regime_signals)

    technical_status_parser = subparsers.add_parser(
        "technical-status", help="Show latest technical signal snapshots."
    )
    _add_common_options(technical_status_parser)
    technical_status_parser.add_argument("--ticker", default=None)
    technical_status_parser.set_defaults(func=command_technical_status)

    regime_status_parser = subparsers.add_parser(
        "regime-status", help="Show latest market-regime signal snapshots."
    )
    _add_common_options(regime_status_parser)
    regime_status_parser.add_argument("--ticker", default=None)
    regime_status_parser.set_defaults(func=command_regime_status)

    range_monitor_parser = subparsers.add_parser(
        "range-monitor", help="Refresh quotes and compute intraday buy/hold/trim/sell ranges."
    )
    range_monitor_parser.add_argument(
        "--ticker",
        type=str,
        default=None,
        help="Optional ticker to monitor. Defaults to all active assets.",
    )
    range_monitor_parser.add_argument(
        "--source",
        choices=("ibkr",),
        default="ibkr",
        help="Quote source for near-real-time monitoring.",
    )
    range_monitor_parser.set_defaults(func=command_range_monitor)

    range_status_parser = subparsers.add_parser(
        "range-status", help="Show latest range state by ticker."
    )
    range_status_parser.add_argument("--ticker", type=str, default=None)
    range_status_parser.set_defaults(func=command_range_status)

    notification_status_parser = subparsers.add_parser(
        "notification-status", help="Show stored range notification events."
    )
    notification_status_parser.add_argument("--ticker", type=str, default=None)
    notification_status_parser.add_argument(
        "--status",
        choices=("pending", "delivered", "delivery_failed", "suppressed"),
        default=None,
    )
    notification_status_parser.add_argument(
        "--pending-only",
        action="store_true",
        help="Show only pending notification events.",
    )
    notification_status_parser.set_defaults(func=command_notification_status)

    deliver_notifications_parser = subparsers.add_parser(
        "deliver-notifications", help="Deliver pending local notification events."
    )
    deliver_notifications_parser.add_argument(
        "--channel",
        choices=("console", "dashboard", "codex_scheduler", "file", "webhook"),
        default="console",
    )
    deliver_notifications_parser.set_defaults(func=command_deliver_notifications)

    drain_notifications_parser = subparsers.add_parser(
        "drain-pending-notifications",
        help="Deliver and drain pending notification events.",
    )
    drain_notifications_parser.add_argument(
        "--channel",
        choices=("console", "file", "webhook"),
        required=True,
    )
    drain_notifications_parser.set_defaults(func=command_drain_pending_notifications)

    notification_outbox_parser = subparsers.add_parser(
        "notification-outbox-status",
        help="Show notification outbox files and delivery state.",
    )
    notification_outbox_parser.set_defaults(func=command_notification_outbox_status)

    notification_delivery_report_parser = subparsers.add_parser(
        "notification-delivery-report",
        help="Summarize notification delivery, pending events, and outbox artifacts.",
    )
    notification_delivery_report_parser.set_defaults(
        func=command_notification_delivery_report
    )

    test_notification_parser = subparsers.add_parser(
        "test-notification-channel",
        help="Test a local notification delivery channel without creating an event.",
    )
    test_notification_parser.add_argument(
        "--channel",
        choices=("console", "file", "webhook"),
        required=True,
    )
    test_notification_parser.set_defaults(func=command_test_notification_channel)

    intraday_cycle_parser = subparsers.add_parser(
        "intraday-cycle",
        help="Run a scheduler-friendly intraday quote, range, and notification cycle.",
    )
    intraday_cycle_parser.add_argument("--ticker", type=str, default=None)
    intraday_cycle_parser.add_argument(
        "--source",
        choices=("ibkr", "auto"),
        default="ibkr",
    )
    intraday_cycle_parser.add_argument("--deliver", action="store_true")
    intraday_cycle_parser.add_argument("--no-deliver", action="store_true")
    intraday_cycle_parser.add_argument(
        "--drain-first",
        action="store_true",
        help="Deliver old pending notifications before computing new range events.",
    )
    intraday_cycle_parser.add_argument(
        "--channel",
        choices=("console", "file", "webhook"),
        default="console",
    )
    intraday_cycle_parser.add_argument(
        "--include-options",
        action="store_true",
        help="Also run bounded option-chain fetch and sell-put review steps.",
    )
    intraday_cycle_parser.set_defaults(func=command_intraday_cycle)

    manual_ops_cycle_parser = subparsers.add_parser(
        "manual-ops-cycle",
        help="Run the manual replacement for TOM Codex operational automations.",
    )
    manual_ops_cycle_parser.add_argument(
        "--mode",
        choices=("auto", "morning", "intraday", "daily-refresh", "daily-retry", "all"),
        default="auto",
    )
    manual_ops_cycle_parser.add_argument("--deliver", action="store_true")
    manual_ops_cycle_parser.add_argument("--no-deliver", action="store_true")
    manual_ops_cycle_parser.add_argument(
        "--channel",
        choices=("console", "file", "webhook"),
        default="file",
    )
    manual_ops_cycle_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show planned manual operations without writing pipeline audit rows.",
    )
    manual_ops_cycle_parser.set_defaults(func=command_manual_ops_cycle)

    manual_ops_loop_parser = subparsers.add_parser(
        "manual-ops-loop",
        help="Run the manual TOM ops cycle repeatedly until Ctrl+C.",
    )
    manual_ops_loop_parser.add_argument(
        "--mode",
        choices=("auto", "morning", "intraday", "daily-refresh", "daily-retry", "all"),
        default="auto",
    )
    manual_ops_loop_parser.add_argument("--deliver", action="store_true")
    manual_ops_loop_parser.add_argument("--no-deliver", action="store_true")
    manual_ops_loop_parser.add_argument(
        "--channel",
        choices=("console", "file", "webhook"),
        default="file",
    )
    manual_ops_loop_parser.add_argument(
        "--interval-seconds",
        type=int,
        default=None,
        help="Seconds between loop iterations. Defaults to realtime.manual_ops_loop_interval_seconds.",
    )
    manual_ops_loop_parser.add_argument(
        "--max-iterations",
        type=int,
        default=None,
        help="Optional bounded run for verification. Omit for never-ending mode.",
    )
    manual_ops_loop_parser.set_defaults(func=command_manual_ops_loop)

    manual_ops_status_parser = subparsers.add_parser(
        "manual-ops-status",
        help="Show manual TOM ops runner status and automation pause recommendations.",
    )
    manual_ops_status_parser.set_defaults(func=command_manual_ops_status)

    tom_loop_status_parser = subparsers.add_parser(
        "tom-loop-status",
        help="Show persistent local TOM loop state, lock, heartbeat, and freshness.",
    )
    tom_loop_status_parser.set_defaults(func=command_tom_loop_status)

    tom_loop_health_parser = subparsers.add_parser(
        "tom-loop-health",
        help="Classify persistent local TOM loop health and stale blockers.",
    )
    tom_loop_health_parser.set_defaults(func=command_tom_loop_health)

    tom_loop_once_parser = subparsers.add_parser(
        "tom-loop-once",
        help="Run one persistent-loop cycle without starting the forever loop.",
    )
    tom_loop_once_parser.add_argument(
        "--mode",
        choices=("auto", "morning", "intraday", "daily-refresh", "daily-retry", "all"),
        default="auto",
    )
    tom_loop_once_parser.add_argument("--deliver", action="store_true")
    tom_loop_once_parser.add_argument("--no-deliver", action="store_true")
    tom_loop_once_parser.add_argument(
        "--channel",
        choices=("console", "file", "webhook"),
        default="file",
    )
    tom_loop_once_parser.set_defaults(func=command_tom_loop_once)

    tom_loop_start_parser = subparsers.add_parser(
        "tom-loop-start",
        help="Start the persistent local TOM ops loop. Press Ctrl+C or use tom-loop-stop.",
    )
    tom_loop_start_parser.add_argument(
        "--mode",
        choices=("auto", "morning", "intraday", "daily-refresh", "daily-retry", "all"),
        default="auto",
    )
    tom_loop_start_parser.add_argument("--deliver", action="store_true")
    tom_loop_start_parser.add_argument("--no-deliver", action="store_true")
    tom_loop_start_parser.add_argument(
        "--channel",
        choices=("console", "file", "webhook"),
        default="file",
    )
    tom_loop_start_parser.add_argument(
        "--interval-seconds",
        type=int,
        default=None,
        help="Seconds between loop cycles. Defaults to realtime.manual_ops_loop_interval_seconds.",
    )
    tom_loop_start_parser.add_argument(
        "--max-cycles",
        type=int,
        default=None,
        help="Optional bounded run for verification. Omit for a persistent loop.",
    )
    tom_loop_start_parser.set_defaults(func=command_tom_loop_start)

    tom_loop_stop_parser = subparsers.add_parser(
        "tom-loop-stop",
        help="Request the persistent local TOM loop to stop and clear stale locks.",
    )
    tom_loop_stop_parser.set_defaults(func=command_tom_loop_stop)

    intraday_status_parser = subparsers.add_parser(
        "intraday-status", help="Show latest intraday cycle and delivery health."
    )
    intraday_status_parser.set_defaults(func=command_intraday_status)

    intraday_health_parser = subparsers.add_parser(
        "intraday-health-check",
        help="Classify intraday quote, cycle, range, and notification health.",
    )
    intraday_health_parser.set_defaults(func=command_intraday_health_check)

    intraday_repair_parser = subparsers.add_parser(
        "intraday-repair-plan",
        help="Show the recommended commands to repair intraday operations.",
    )
    intraday_repair_parser.set_defaults(func=command_intraday_repair_plan)

    scheduler_status_parser = subparsers.add_parser(
        "scheduler-status",
        help="Show intended Codex automation jobs and latest TOM scheduler health.",
    )
    scheduler_status_parser.set_defaults(func=command_scheduler_status)

    scheduler_audit_parser = subparsers.add_parser(
        "scheduler-audit",
        help="Compare intended TOM automations against saved Codex automation metadata.",
    )
    scheduler_audit_parser.set_defaults(func=command_scheduler_audit)

    scheduler_repair_parser = subparsers.add_parser(
        "scheduler-repair-plan",
        help="Show scheduler reconciliation fixes without mutating automation state.",
    )
    scheduler_repair_parser.set_defaults(func=command_scheduler_repair_plan)

    scheduler_automation_status_parser = subparsers.add_parser(
        "scheduler-automation-status",
        help="Show actual scheduler automation commands, ids, and blockers.",
    )
    scheduler_automation_status_parser.set_defaults(
        func=command_scheduler_automation_status
    )

    add_asset_parser = subparsers.add_parser(
        "add-asset", help="Add or update an asset in the watchlist and database."
    )
    add_asset_parser.add_argument("--ticker", required=True)
    add_asset_parser.add_argument("--asset-type", choices=("equity", "etf"), required=True)
    add_asset_parser.add_argument(
        "--asset-role",
        choices=("scoreable", "commentary_validation", "regime_proxy"),
        default="scoreable",
    )
    add_asset_parser.add_argument("--name", default=None)
    add_asset_parser.add_argument("--exchange", default=None)
    add_asset_parser.add_argument("--currency", default="USD")
    add_asset_parser.add_argument("--sector", default=None)
    add_asset_parser.add_argument("--industry", default=None)
    add_asset_parser.add_argument("--country", default="US")
    add_asset_parser.add_argument("--cik", default=None)
    add_asset_parser.add_argument("--reason", default=None)
    add_asset_parser.set_defaults(func=command_add_asset)

    deactivate_asset_parser = subparsers.add_parser(
        "deactivate-asset", help="Soft-deactivate an asset from active monitoring."
    )
    deactivate_asset_parser.add_argument("--ticker", required=True)
    deactivate_asset_parser.add_argument("--reason", default=None)
    deactivate_asset_parser.set_defaults(func=command_deactivate_asset)

    reactivate_asset_parser = subparsers.add_parser(
        "reactivate-asset", help="Reactivate an asset for monitoring."
    )
    reactivate_asset_parser.add_argument("--ticker", required=True)
    reactivate_asset_parser.add_argument("--reason", default=None)
    reactivate_asset_parser.set_defaults(func=command_reactivate_asset)

    remove_asset_parser = subparsers.add_parser(
        "remove-asset", help="Soft-remove an asset while preserving history."
    )
    remove_asset_parser.add_argument("--ticker", required=True)
    remove_asset_parser.add_argument("--soft", action="store_true")
    remove_asset_parser.add_argument("--reason", default=None)
    remove_asset_parser.set_defaults(func=command_remove_asset)

    asset_status_parser = subparsers.add_parser(
        "asset-status", help="Show asset metadata, readiness, and latest range state."
    )
    asset_status_parser.add_argument("--ticker", required=True)
    asset_status_parser.set_defaults(func=command_asset_status)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)
