from __future__ import annotations

from dataclasses import dataclass
from contextlib import closing
from pathlib import Path
import sqlite3


REQUIRED_TABLES = (
    "assets",
    "prices",
    "fundamentals",
    "estimates",
    "price_features",
    "etf_navs",
    "etf_holdings",
    "etf_features",
    "quote_snapshots",
    "intraday_gap_snapshots",
    "range_snapshots",
    "notification_events",
    "notification_deliveries",
    "asset_change_events",
    "technical_signal_snapshots",
    "regime_signal_snapshots",
    "fundamental_benchmark_snapshots",
    "fundamental_comparison_snapshots",
    "research_recommendation_candidates",
    "research_recommendation_evidence",
    "research_recommendation_decisions",
    "missing_ticker_candidates",
    "missing_ticker_resolution_events",
    "trader_commentary_raw",
    "trader_commentary_instrument_aliases",
    "trader_commentary_browser_capture_runs",
    "trader_commentary_browser_capture_items",
    "trader_commentary_discord_capture_runs",
    "trader_commentary_discord_capture_items",
    "trader_commentary_claims",
    "trader_commentary_claim_outcomes",
    "pipeline_runs",
    "pipeline_step_results",
    "portfolio_positions",
    "portfolio_cash",
    "portfolio_reviews",
    "analyst_revision_source_snapshots",
    "analyst_revision_aggregates",
    "news_catalyst_source_snapshots",
    "news_catalyst_aggregates",
    "insider_transaction_source_snapshots",
    "short_interest_source_snapshots",
    "option_chain_snapshots",
    "option_income_reviews",
    "option_risk_reviews",
    "option_review_outcomes",
    "option_position_ledger",
    "option_position_lifecycle_reviews",
    "signals",
    "signal_outcomes",
    "targets",
    "scores",
    "alerts",
    "alert_outcomes",
    "data_quality_checks",
    "model_versions",
)

ASSET_OPTIONAL_COLUMNS = {
    "asset_role": "TEXT NOT NULL DEFAULT 'scoreable'",
}

TARGET_OPTIONAL_COLUMNS = {
    "valuation_score": "REAL",
    "valuation_confidence": "REAL",
    "method_count": "INTEGER",
    "target_reason": "TEXT",
    "data_warnings": "TEXT",
}

SCORE_OPTIONAL_COLUMNS = {
    "asset_type": "TEXT",
    "score_model": "TEXT",
    "threshold_set": "TEXT",
    "score_reason": "TEXT",
    "data_warnings": "TEXT",
}

ALERT_OPTIONAL_COLUMNS = {
    "asset_type": "TEXT",
    "alert_model": "TEXT",
    "threshold_set": "TEXT",
    "target_date": "TEXT",
    "score_date": "TEXT",
    "valuation_gap": "REAL",
    "expected_value_score": "REAL",
    "liquidity_score": "REAL",
    "data_quality_score": "REAL",
    "reason_codes": "TEXT",
    "risk_codes": "TEXT",
    "data_warnings": "TEXT",
    "dedupe_key": "TEXT",
}

ALERT_OUTCOME_OPTIONAL_COLUMNS = {
    "ticker": "TEXT",
    "alert_type": "TEXT",
    "alert_timestamp": "TEXT",
    "asset_type": "TEXT",
    "alert_model": "TEXT",
    "threshold_set": "TEXT",
    "outcome_status": "TEXT",
    "entry_price": "REAL",
    "entry_price_date": "TEXT",
    "latest_price": "REAL",
    "latest_price_date": "TEXT",
    "target_price": "REAL",
    "invalidation_price": "REAL",
    "completed_horizons": "TEXT",
    "pending_horizons": "TEXT",
    "data_warnings": "TEXT",
    "model_version": "TEXT",
}


SIGNAL_OPTIONAL_COLUMNS = {
    "model_version": "TEXT",
    "confidence": "REAL",
    "data_warnings": "TEXT",
    "source_url": "TEXT",
    "notes": "TEXT",
}


RANGE_OPTIONAL_COLUMNS = {
    "technical_signal_date": "TEXT",
    "support_low": "REAL",
    "support_high": "REAL",
    "resistance_low": "REAL",
    "resistance_high": "REAL",
    "breakout_level": "REAL",
    "downside_watch_level": "REAL",
    "trend_repair_level": "REAL",
    "moving_average_state": "TEXT",
    "drawdown_state": "TEXT",
    "price_location_state": "TEXT",
    "regime_signal_date": "TEXT",
    "regime_state": "TEXT",
    "relative_strength": "REAL",
    "sector_rotation_rank": "INTEGER",
    "technical_confidence": "REAL",
    "regime_confidence": "REAL",
}

OPTION_POSITION_OPTIONAL_COLUMNS = {
    "position_id": "TEXT",
    "roll_from_position_id": "TEXT",
    "roll_to_position_id": "TEXT",
    "underlying_assignment_date": "TEXT",
    "underlying_shares": "REAL",
    "underlying_cost_basis": "REAL",
    "tags": "TEXT",
}


SCHEMA_STATEMENTS = (
    """
    CREATE TABLE IF NOT EXISTS assets (
        asset_id INTEGER PRIMARY KEY,
        ticker TEXT NOT NULL UNIQUE,
        name TEXT,
        asset_type TEXT,
        exchange TEXT,
        currency TEXT,
        sector TEXT,
        industry TEXT,
        country TEXT,
        active_flag INTEGER NOT NULL DEFAULT 1,
        asset_role TEXT NOT NULL DEFAULT 'scoreable',
        source TEXT NOT NULL DEFAULT 'manual',
        as_of_date TEXT,
        effective_date TEXT,
        loaded_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS prices (
        price_id INTEGER PRIMARY KEY,
        ticker TEXT NOT NULL,
        price_date TEXT NOT NULL,
        open REAL,
        high REAL,
        low REAL,
        close REAL,
        adjusted_close REAL,
        volume REAL,
        source TEXT NOT NULL,
        as_of_date TEXT,
        effective_date TEXT,
        loaded_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        UNIQUE (ticker, price_date, source)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS fundamentals (
        fundamental_id INTEGER PRIMARY KEY,
        ticker TEXT NOT NULL,
        fiscal_period_end TEXT NOT NULL,
        fiscal_period TEXT NOT NULL,
        report_type TEXT NOT NULL,
        currency TEXT,
        revenue REAL,
        gross_profit REAL,
        operating_income REAL,
        ebitda REAL,
        ebit REAL,
        net_income REAL,
        eps REAL,
        diluted_eps REAL,
        cash_from_operations REAL,
        capital_expenditure REAL,
        free_cash_flow REAL,
        cash_and_equivalents REAL,
        total_debt REAL,
        net_debt REAL,
        total_assets REAL,
        total_equity REAL,
        shares_outstanding REAL,
        diluted_shares REAL,
        source TEXT NOT NULL,
        as_of_date TEXT,
        effective_date TEXT,
        loaded_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        UNIQUE (ticker, fiscal_period_end, fiscal_period, report_type, source)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS estimates (
        estimate_id INTEGER PRIMARY KEY,
        ticker TEXT NOT NULL,
        estimate_date TEXT NOT NULL,
        fiscal_period_end TEXT NOT NULL,
        metric TEXT NOT NULL,
        fiscal_period TEXT,
        currency TEXT,
        consensus_mean REAL,
        consensus_median REAL,
        consensus_high REAL,
        consensus_low REAL,
        analyst_count INTEGER,
        revision_1m REAL,
        revision_3m REAL,
        source TEXT NOT NULL,
        as_of_date TEXT,
        effective_date TEXT,
        loaded_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        UNIQUE (ticker, estimate_date, fiscal_period_end, metric, source)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS price_features (
        price_feature_id INTEGER PRIMARY KEY,
        ticker TEXT NOT NULL,
        feature_date TEXT NOT NULL,
        current_price REAL,
        return_1d REAL,
        return_1m REAL,
        return_3m REAL,
        return_6m REAL,
        return_12m REAL,
        realized_volatility_20d REAL,
        realized_volatility_60d REAL,
        average_dollar_volume_20d REAL,
        latest_price_date TEXT,
        source TEXT NOT NULL,
        as_of_date TEXT,
        effective_date TEXT,
        loaded_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        UNIQUE (ticker, feature_date, source)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS etf_navs (
        etf_nav_id INTEGER PRIMARY KEY,
        ticker TEXT NOT NULL,
        nav_date TEXT NOT NULL,
        nav_per_share REAL NOT NULL,
        market_price REAL,
        premium_discount REAL,
        shares_outstanding REAL,
        net_assets REAL,
        source TEXT NOT NULL,
        as_of_date TEXT,
        effective_date TEXT,
        loaded_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        UNIQUE (ticker, nav_date, source)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS etf_holdings (
        etf_holding_id INTEGER PRIMARY KEY,
        ticker TEXT NOT NULL,
        holdings_date TEXT NOT NULL,
        holding_ticker TEXT,
        holding_name TEXT,
        holding_asset_type TEXT,
        weight REAL NOT NULL,
        shares REAL,
        market_value REAL,
        sector TEXT,
        country TEXT,
        source TEXT NOT NULL,
        as_of_date TEXT,
        effective_date TEXT,
        loaded_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        UNIQUE (ticker, holdings_date, holding_ticker, holding_name, source)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS etf_features (
        etf_feature_id INTEGER PRIMARY KEY,
        ticker TEXT NOT NULL,
        feature_date TEXT NOT NULL,
        nav_per_share REAL,
        market_price REAL,
        premium_discount REAL,
        premium_discount_average_60d REAL,
        premium_discount_volatility_60d REAL,
        premium_discount_zscore REAL,
        holdings_count INTEGER,
        top_10_weight REAL,
        largest_holding_weight REAL,
        equity_weight REAL,
        cash_weight REAL,
        latest_nav_date TEXT,
        latest_holdings_date TEXT,
        source TEXT NOT NULL,
        as_of_date TEXT,
        effective_date TEXT,
        loaded_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        UNIQUE (ticker, feature_date, source)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS quote_snapshots (
        quote_snapshot_id INTEGER PRIMARY KEY,
        ticker TEXT NOT NULL,
        quote_timestamp TEXT NOT NULL,
        bid REAL,
        ask REAL,
        last REAL,
        mark REAL,
        open REAL,
        high REAL,
        low REAL,
        close REAL,
        volume REAL,
        market_data_type TEXT,
        source TEXT NOT NULL,
        as_of_date TEXT,
        effective_date TEXT,
        loaded_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        UNIQUE (ticker, quote_timestamp, source)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS intraday_gap_snapshots (
        intraday_gap_snapshot_id INTEGER PRIMARY KEY,
        ticker TEXT NOT NULL,
        snapshot_timestamp TEXT NOT NULL,
        current_price REAL,
        base_target REAL,
        target_low REAL,
        target_high REAL,
        gap_to_base REAL,
        gap_to_low REAL,
        gap_to_high REAL,
        etf_nav_per_share REAL,
        etf_nav_gap REAL,
        source TEXT NOT NULL,
        as_of_date TEXT,
        effective_date TEXT,
        loaded_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        UNIQUE (ticker, snapshot_timestamp, source)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS range_snapshots (
        range_snapshot_id INTEGER PRIMARY KEY,
        ticker TEXT NOT NULL,
        snapshot_timestamp TEXT NOT NULL,
        asset_type TEXT,
        current_price REAL,
        quote_timestamp TEXT,
        quote_source TEXT,
        quote_stale INTEGER NOT NULL DEFAULT 0,
        base_target REAL,
        target_low REAL,
        target_high REAL,
        etf_nav_per_share REAL,
        etf_nav_gap REAL,
        opportunity_score REAL,
        confidence_score REAL,
        timing_score REAL,
        risk_score REAL,
        liquidity_score REAL,
        data_quality_score REAL,
        position_weight REAL,
        portfolio_review_category TEXT,
        strong_buy_below REAL,
        starter_buy_below REAL,
        add_below REAL,
        hold_low REAL,
        hold_high REAL,
        trim_above REAL,
        reduce_or_sell_above REAL,
        risk_review_below REAL,
        nav_action_discount_below REAL,
        nav_watch_discount_below REAL,
        nav_fair_value REAL,
        nav_premium_warning_above REAL,
        etf_risk_review_level REAL,
        range_state TEXT NOT NULL,
        previous_range_state TEXT,
        reason_codes TEXT,
        data_warnings TEXT,
        technical_signal_date TEXT,
        support_low REAL,
        support_high REAL,
        resistance_low REAL,
        resistance_high REAL,
        breakout_level REAL,
        downside_watch_level REAL,
        trend_repair_level REAL,
        moving_average_state TEXT,
        drawdown_state TEXT,
        price_location_state TEXT,
        regime_signal_date TEXT,
        regime_state TEXT,
        relative_strength REAL,
        sector_rotation_rank INTEGER,
        technical_confidence REAL,
        regime_confidence REAL,
        model_version TEXT NOT NULL,
        source TEXT NOT NULL,
        as_of_date TEXT,
        effective_date TEXT,
        loaded_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        UNIQUE (ticker, snapshot_timestamp, model_version, source)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS technical_signal_snapshots (
        technical_signal_snapshot_id INTEGER PRIMARY KEY,
        ticker TEXT NOT NULL,
        signal_date TEXT NOT NULL,
        current_price REAL,
        support_low REAL,
        support_high REAL,
        resistance_low REAL,
        resistance_high REAL,
        breakout_level REAL,
        downside_watch_level REAL,
        trend_repair_level REAL,
        short_ma REAL,
        medium_ma REAL,
        long_ma REAL,
        moving_average_state TEXT,
        drawdown_pct REAL,
        drawdown_state TEXT,
        price_location_state TEXT,
        trend_score REAL,
        level_score REAL,
        confidence REAL,
        data_warnings TEXT,
        model_version TEXT NOT NULL,
        source TEXT NOT NULL,
        as_of_date TEXT,
        effective_date TEXT,
        loaded_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        UNIQUE (ticker, signal_date, model_version, source)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS regime_signal_snapshots (
        regime_signal_snapshot_id INTEGER PRIMARY KEY,
        ticker TEXT NOT NULL,
        signal_date TEXT NOT NULL,
        proxy_type TEXT,
        current_price REAL,
        benchmark_ticker TEXT,
        benchmark_return REAL,
        return_lookback REAL,
        relative_strength REAL,
        trend_state TEXT,
        risk_state TEXT,
        sector_rotation_rank INTEGER,
        defensive_rotation_flag INTEGER,
        confidence REAL,
        data_warnings TEXT,
        model_version TEXT NOT NULL,
        source TEXT NOT NULL,
        as_of_date TEXT,
        effective_date TEXT,
        loaded_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        UNIQUE (ticker, signal_date, model_version, source)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS fundamental_benchmark_snapshots (
        fundamental_benchmark_snapshot_id INTEGER PRIMARY KEY,
        benchmark_date TEXT NOT NULL,
        benchmark_type TEXT NOT NULL,
        benchmark_key TEXT NOT NULL,
        ticker_count INTEGER NOT NULL DEFAULT 0,
        forward_pe_median REAL,
        trailing_pe_median REAL,
        ev_ebitda_median REAL,
        p_fcf_median REAL,
        p_s_median REAL,
        revenue_growth_median REAL,
        net_margin_median REAL,
        fcf_margin_median REAL,
        roe_median REAL,
        net_debt_ebitda_median REAL,
        opportunity_score_median REAL,
        valuation_gap_median REAL,
        data_warnings TEXT,
        model_version TEXT NOT NULL,
        source TEXT NOT NULL DEFAULT 'computed',
        as_of_date TEXT,
        effective_date TEXT,
        loaded_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        UNIQUE (benchmark_date, benchmark_type, benchmark_key, model_version, source)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS fundamental_comparison_snapshots (
        fundamental_comparison_snapshot_id INTEGER PRIMARY KEY,
        ticker TEXT NOT NULL,
        comparison_date TEXT NOT NULL,
        sector TEXT,
        industry TEXT,
        sector_benchmark_ticker TEXT,
        overall_peer_count INTEGER NOT NULL DEFAULT 0,
        sector_peer_count INTEGER NOT NULL DEFAULT 0,
        industry_peer_count INTEGER NOT NULL DEFAULT 0,
        forward_pe REAL,
        sector_forward_pe_median REAL,
        overall_forward_pe_median REAL,
        sector_forward_pe_discount_pct REAL,
        sector_forward_pe_percentile REAL,
        ev_ebitda REAL,
        sector_ev_ebitda_median REAL,
        p_fcf REAL,
        sector_p_fcf_median REAL,
        net_margin REAL,
        sector_net_margin_median REAL,
        revenue_growth REAL,
        sector_revenue_growth_median REAL,
        net_debt_ebitda REAL,
        sector_net_debt_ebitda_median REAL,
        valuation_gap REAL,
        sector_valuation_gap_median REAL,
        opportunity_score REAL,
        sector_opportunity_score_median REAL,
        relative_strength_vs_spy REAL,
        relative_strength_vs_qqq REAL,
        relative_strength_vs_sector REAL,
        benchmark_status TEXT,
        data_warnings TEXT,
        model_version TEXT NOT NULL,
        source TEXT NOT NULL DEFAULT 'computed',
        as_of_date TEXT,
        effective_date TEXT,
        loaded_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        UNIQUE (ticker, comparison_date, model_version, source)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS research_recommendation_candidates (
        research_recommendation_id INTEGER PRIMARY KEY,
        recommendation_key TEXT NOT NULL UNIQUE,
        ticker TEXT NOT NULL,
        recommendation_date TEXT NOT NULL,
        source TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'pending',
        topic TEXT,
        rationale TEXT,
        research_priority_score REAL,
        confidence REAL,
        source_count INTEGER NOT NULL DEFAULT 0,
        evidence_count INTEGER NOT NULL DEFAULT 0,
        source_mix TEXT,
        metadata_status TEXT,
        warning_codes TEXT,
        promotion_blockers TEXT,
        promoted_asset_role TEXT,
        source_url TEXT,
        external_id TEXT,
        model_version TEXT NOT NULL DEFAULT 'research_recommendation_mvp_v1',
        as_of_date TEXT,
        effective_date TEXT,
        loaded_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS research_recommendation_evidence (
        research_recommendation_evidence_id INTEGER PRIMARY KEY,
        evidence_key TEXT NOT NULL UNIQUE,
        recommendation_key TEXT NOT NULL,
        ticker TEXT NOT NULL,
        evidence_date TEXT NOT NULL,
        source TEXT NOT NULL,
        source_type TEXT,
        source_id TEXT,
        source_url TEXT,
        headline_or_excerpt TEXT,
        reason TEXT,
        confidence REAL,
        as_of_date TEXT,
        effective_date TEXT,
        loaded_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS research_recommendation_decisions (
        research_recommendation_decision_id INTEGER PRIMARY KEY,
        recommendation_key TEXT NOT NULL,
        ticker TEXT NOT NULL,
        decision_timestamp TEXT NOT NULL,
        previous_status TEXT,
        new_status TEXT NOT NULL,
        reason TEXT,
        source TEXT NOT NULL DEFAULT 'research_recommendation',
        as_of_date TEXT,
        effective_date TEXT,
        loaded_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS missing_ticker_candidates (
        missing_ticker_candidate_id INTEGER PRIMARY KEY,
        ticker TEXT NOT NULL,
        first_seen_source TEXT NOT NULL,
        source_file TEXT,
        source_row TEXT,
        detected_asset_type TEXT,
        recommended_asset_role TEXT,
        confidence REAL,
        blockers TEXT,
        warnings TEXT,
        status TEXT NOT NULL DEFAULT 'detected',
        next_command TEXT,
        metadata_name TEXT,
        metadata_exchange TEXT,
        metadata_currency TEXT,
        metadata_sector TEXT,
        metadata_industry TEXT,
        metadata_country TEXT,
        source_url TEXT,
        as_of_date TEXT,
        effective_date TEXT,
        loaded_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        UNIQUE (ticker, first_seen_source, source_file, source_row)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS missing_ticker_resolution_events (
        missing_ticker_resolution_event_id INTEGER PRIMARY KEY,
        event_timestamp TEXT NOT NULL,
        ticker TEXT NOT NULL,
        event_type TEXT NOT NULL,
        previous_status TEXT,
        new_status TEXT,
        source TEXT NOT NULL DEFAULT 'missing_ticker_resolver',
        details TEXT,
        warnings TEXT,
        as_of_date TEXT,
        effective_date TEXT,
        loaded_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS notification_events (
        notification_event_id INTEGER PRIMARY KEY,
        ticker TEXT NOT NULL,
        event_timestamp TEXT NOT NULL,
        event_type TEXT NOT NULL,
        asset_type TEXT,
        severity TEXT,
        previous_state TEXT,
        current_state TEXT,
        trigger_price REAL,
        range_level REAL,
        reason_codes TEXT,
        status TEXT NOT NULL DEFAULT 'pending',
        cooldown_until TEXT,
        dedupe_key TEXT NOT NULL,
        model_version TEXT NOT NULL,
        source TEXT NOT NULL,
        as_of_date TEXT,
        effective_date TEXT,
        loaded_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        UNIQUE (dedupe_key)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS notification_deliveries (
        notification_delivery_id INTEGER PRIMARY KEY,
        notification_event_id INTEGER NOT NULL,
        channel TEXT NOT NULL,
        delivery_timestamp TEXT NOT NULL,
        status TEXT NOT NULL,
        details TEXT,
        source TEXT NOT NULL DEFAULT 'notifications',
        as_of_date TEXT,
        effective_date TEXT,
        loaded_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        UNIQUE (notification_event_id, channel),
        FOREIGN KEY (notification_event_id) REFERENCES notification_events (notification_event_id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS asset_change_events (
        asset_change_event_id INTEGER PRIMARY KEY,
        event_timestamp TEXT NOT NULL,
        ticker TEXT NOT NULL,
        event_type TEXT NOT NULL,
        previous_active_flag INTEGER,
        new_active_flag INTEGER,
        reason TEXT,
        details TEXT,
        source TEXT NOT NULL DEFAULT 'asset_management',
        as_of_date TEXT,
        effective_date TEXT,
        loaded_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS trader_commentary_raw (
        commentary_id INTEGER PRIMARY KEY,
        identity_key TEXT NOT NULL UNIQUE,
        capture_date TEXT NOT NULL,
        source TEXT NOT NULL,
        source_author TEXT NOT NULL,
        platform TEXT NOT NULL,
        permission_scope TEXT NOT NULL,
        language TEXT,
        raw_text TEXT,
        source_url TEXT,
        capture_id TEXT,
        text_file TEXT,
        notes TEXT,
        data_warnings TEXT,
        as_of_date TEXT,
        effective_date TEXT,
        loaded_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS trader_commentary_instrument_aliases (
        alias_id INTEGER PRIMARY KEY,
        instrument_label TEXT NOT NULL UNIQUE,
        canonical_ticker TEXT NOT NULL,
        asset_type TEXT NOT NULL DEFAULT 'equity',
        asset_role TEXT NOT NULL DEFAULT 'commentary_validation',
        source TEXT NOT NULL DEFAULT 'manual_csv',
        notes TEXT,
        as_of_date TEXT,
        effective_date TEXT,
        loaded_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS trader_commentary_browser_capture_runs (
        browser_capture_run_id INTEGER PRIMARY KEY,
        run_id TEXT NOT NULL UNIQUE,
        provider TEXT NOT NULL,
        target_url TEXT,
        run_date TEXT NOT NULL,
        started_at TEXT NOT NULL,
        completed_at TEXT,
        status TEXT NOT NULL,
        raw_dir TEXT,
        dom_text_path TEXT,
        page_html_path TEXT,
        item_count INTEGER NOT NULL DEFAULT 0,
        stored_count INTEGER NOT NULL DEFAULT 0,
        skipped_count INTEGER NOT NULL DEFAULT 0,
        warnings TEXT,
        source TEXT NOT NULL DEFAULT 'browser_capture',
        as_of_date TEXT,
        effective_date TEXT,
        loaded_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS trader_commentary_browser_capture_items (
        browser_capture_item_id INTEGER PRIMARY KEY,
        run_id TEXT NOT NULL,
        provider TEXT NOT NULL,
        target_url TEXT,
        item_key TEXT NOT NULL UNIQUE,
        external_id TEXT,
        canonical_url TEXT,
        author_text TEXT,
        content_text TEXT NOT NULL,
        created_at_text TEXT,
        observed_at TEXT NOT NULL,
        raw_excerpt TEXT,
        accepted_flag INTEGER NOT NULL DEFAULT 1,
        ingested_at TEXT,
        data_warnings TEXT,
        source TEXT NOT NULL DEFAULT 'x_browser_capture',
        as_of_date TEXT,
        effective_date TEXT,
        loaded_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (run_id) REFERENCES trader_commentary_browser_capture_runs (run_id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS trader_commentary_discord_capture_runs (
        discord_capture_run_id INTEGER PRIMARY KEY,
        run_id TEXT NOT NULL UNIQUE,
        provider TEXT NOT NULL,
        channel_id TEXT,
        run_date TEXT NOT NULL,
        started_at TEXT NOT NULL,
        completed_at TEXT,
        status TEXT NOT NULL,
        raw_dir TEXT,
        messages_path TEXT,
        raw_payload_path TEXT,
        item_count INTEGER NOT NULL DEFAULT 0,
        stored_count INTEGER NOT NULL DEFAULT 0,
        skipped_count INTEGER NOT NULL DEFAULT 0,
        warnings TEXT,
        source TEXT NOT NULL DEFAULT 'discord_capture',
        as_of_date TEXT,
        effective_date TEXT,
        loaded_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS trader_commentary_discord_capture_items (
        discord_capture_item_id INTEGER PRIMARY KEY,
        run_id TEXT NOT NULL,
        provider TEXT NOT NULL,
        channel_id TEXT,
        guild_id TEXT,
        item_key TEXT NOT NULL UNIQUE,
        message_id TEXT,
        canonical_url TEXT,
        author_id TEXT,
        author_text TEXT,
        content_text TEXT NOT NULL,
        message_timestamp TEXT,
        observed_at TEXT NOT NULL,
        raw_excerpt TEXT,
        attachment_count INTEGER NOT NULL DEFAULT 0,
        accepted_flag INTEGER NOT NULL DEFAULT 1,
        ingested_at TEXT,
        data_warnings TEXT,
        source TEXT NOT NULL DEFAULT 'discord_bot_capture',
        as_of_date TEXT,
        effective_date TEXT,
        loaded_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (run_id) REFERENCES trader_commentary_discord_capture_runs (run_id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS trader_commentary_claims (
        claim_id INTEGER PRIMARY KEY,
        claim_key TEXT NOT NULL UNIQUE,
        commentary_id INTEGER,
        claim_date TEXT NOT NULL,
        ticker TEXT,
        instrument_label TEXT,
        claim_type TEXT NOT NULL,
        direction TEXT,
        level_low REAL,
        level_high REAL,
        target_price REAL,
        risk_level REAL,
        strike_price REAL,
        premium REAL,
        condition_text TEXT,
        horizon_text TEXT,
        confidence_text TEXT,
        raw_excerpt TEXT,
        parser_warnings TEXT,
        source TEXT NOT NULL,
        source_url TEXT,
        model_version TEXT,
        as_of_date TEXT,
        effective_date TEXT,
        loaded_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (commentary_id) REFERENCES trader_commentary_raw (commentary_id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS trader_commentary_claim_outcomes (
        claim_outcome_id INTEGER PRIMARY KEY,
        claim_id INTEGER,
        claim_key TEXT NOT NULL,
        ticker TEXT,
        instrument_label TEXT,
        claim_type TEXT NOT NULL,
        claim_date TEXT NOT NULL,
        outcome_date TEXT NOT NULL,
        outcome_status TEXT,
        entry_price REAL,
        entry_price_date TEXT,
        latest_price REAL,
        latest_price_date TEXT,
        completed_horizons TEXT,
        pending_horizons TEXT,
        return_1d REAL,
        return_5d REAL,
        return_20d REAL,
        return_60d REAL,
        level_hit_flag INTEGER,
        directional_hit_flag INTEGER,
        hit_status TEXT,
        data_warnings TEXT,
        model_version TEXT,
        source TEXT NOT NULL DEFAULT 'trader_commentary_validation',
        as_of_date TEXT,
        effective_date TEXT,
        loaded_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (claim_id) REFERENCES trader_commentary_claims (claim_id),
        UNIQUE (claim_key, model_version, source)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS pipeline_runs (
        pipeline_run_id INTEGER PRIMARY KEY,
        run_type TEXT NOT NULL,
        status TEXT NOT NULL,
        started_at TEXT NOT NULL,
        finished_at TEXT,
        source TEXT NOT NULL DEFAULT 'system',
        summary TEXT,
        as_of_date TEXT,
        effective_date TEXT,
        loaded_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS pipeline_step_results (
        pipeline_step_result_id INTEGER PRIMARY KEY,
        pipeline_run_id INTEGER NOT NULL,
        step_name TEXT NOT NULL,
        status TEXT NOT NULL,
        rows_loaded INTEGER NOT NULL DEFAULT 0,
        warnings TEXT,
        started_at TEXT NOT NULL,
        finished_at TEXT,
        source TEXT NOT NULL DEFAULT 'system',
        as_of_date TEXT,
        effective_date TEXT,
        loaded_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (pipeline_run_id) REFERENCES pipeline_runs (pipeline_run_id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS portfolio_positions (
        portfolio_position_id INTEGER PRIMARY KEY,
        account TEXT NOT NULL DEFAULT 'default',
        ticker TEXT NOT NULL,
        position_date TEXT NOT NULL,
        quantity REAL NOT NULL,
        currency TEXT,
        market_price REAL,
        market_value REAL,
        base_market_value REAL,
        cost_basis_per_share REAL,
        cost_basis_total REAL,
        asset_type TEXT,
        sector TEXT,
        source TEXT NOT NULL DEFAULT 'manual_csv',
        as_of_date TEXT,
        effective_date TEXT,
        loaded_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        UNIQUE (account, ticker, position_date, source)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS portfolio_cash (
        portfolio_cash_id INTEGER PRIMARY KEY,
        account TEXT NOT NULL DEFAULT 'default',
        cash_date TEXT NOT NULL,
        currency TEXT,
        cash_amount REAL NOT NULL,
        base_cash_amount REAL,
        source TEXT NOT NULL DEFAULT 'manual_csv',
        as_of_date TEXT,
        effective_date TEXT,
        loaded_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        UNIQUE (account, cash_date, currency, source)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS portfolio_reviews (
        portfolio_review_id INTEGER PRIMARY KEY,
        ticker TEXT NOT NULL,
        review_date TEXT NOT NULL,
        asset_type TEXT,
        held_flag INTEGER NOT NULL DEFAULT 0,
        quantity REAL,
        position_value REAL,
        cost_basis_total REAL,
        unrealized_gain_loss REAL,
        position_weight REAL,
        sector TEXT,
        sector_weight REAL,
        cash_available REAL,
        total_portfolio_value REAL,
        review_category TEXT NOT NULL,
        sizing_guidance TEXT,
        max_add_value REAL,
        risk_notes TEXT,
        data_warnings TEXT,
        model_version TEXT,
        source TEXT NOT NULL DEFAULT 'portfolio',
        as_of_date TEXT,
        effective_date TEXT,
        loaded_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        UNIQUE (ticker, review_date, model_version, source)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS analyst_revision_source_snapshots (
        source_snapshot_id INTEGER PRIMARY KEY,
        ticker TEXT NOT NULL,
        signal_date TEXT NOT NULL,
        source TEXT NOT NULL,
        source_url TEXT,
        notes TEXT,
        capture_method TEXT,
        provider_status TEXT,
        eps_current REAL,
        eps_30d_ago REAL,
        eps_90d_ago REAL,
        eps_high REAL,
        eps_low REAL,
        eps_average REAL,
        analyst_count INTEGER,
        revenue_current REAL,
        revenue_30d_ago REAL,
        revenue_90d_ago REAL,
        target_price_current REAL,
        target_price_90d_ago REAL,
        recommendation_current_strong_buy REAL,
        recommendation_current_buy REAL,
        recommendation_current_hold REAL,
        recommendation_current_sell REAL,
        recommendation_current_strong_sell REAL,
        recommendation_90d_ago_strong_buy REAL,
        recommendation_90d_ago_buy REAL,
        recommendation_90d_ago_hold REAL,
        recommendation_90d_ago_sell REAL,
        recommendation_90d_ago_strong_sell REAL,
        eps_revision_1m REAL,
        eps_revision_3m REAL,
        revenue_revision_1m REAL,
        revenue_revision_3m REAL,
        target_price_revision_3m REAL,
        recommendation_revision REAL,
        estimate_dispersion REAL,
        source_confidence REAL,
        data_warnings TEXT,
        as_of_date TEXT,
        effective_date TEXT,
        loaded_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        UNIQUE (ticker, signal_date, source)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS analyst_revision_aggregates (
        analyst_revision_aggregate_id INTEGER PRIMARY KEY,
        ticker TEXT NOT NULL,
        signal_date TEXT NOT NULL,
        eps_revision_1m REAL,
        eps_revision_3m REAL,
        revenue_revision_1m REAL,
        revenue_revision_3m REAL,
        target_price_revision_3m REAL,
        recommendation_revision REAL,
        estimate_dispersion REAL,
        analyst_count INTEGER,
        source_count INTEGER NOT NULL DEFAULT 0,
        sources TEXT,
        source_policy TEXT NOT NULL,
        aggregate_confidence REAL,
        source_disagreement TEXT,
        data_warnings TEXT,
        model_version TEXT,
        source TEXT NOT NULL DEFAULT 'analyst_revision_aggregate',
        source_url TEXT,
        notes TEXT,
        as_of_date TEXT,
        effective_date TEXT,
        loaded_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        UNIQUE (ticker, signal_date, source)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS news_catalyst_source_snapshots (
        news_catalyst_source_snapshot_id INTEGER PRIMARY KEY,
        ticker TEXT NOT NULL,
        signal_date TEXT NOT NULL,
        source TEXT NOT NULL,
        source_url TEXT NOT NULL,
        headline_or_event TEXT NOT NULL,
        article_datetime TEXT,
        event_date TEXT,
        topic TEXT,
        summary TEXT,
        capture_method TEXT NOT NULL DEFAULT 'api',
        provider_status TEXT NOT NULL DEFAULT 'ok',
        sentiment_score REAL,
        catalyst_score REAL,
        urgency_score REAL,
        relevance_score REAL,
        source_confidence REAL,
        data_warnings TEXT,
        as_of_date TEXT,
        effective_date TEXT,
        loaded_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        UNIQUE (ticker, signal_date, source, source_url)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS news_catalyst_aggregates (
        news_catalyst_aggregate_id INTEGER PRIMARY KEY,
        ticker TEXT NOT NULL,
        signal_date TEXT NOT NULL,
        sentiment_score REAL,
        catalyst_score REAL,
        urgency_score REAL,
        confidence REAL,
        source_count INTEGER NOT NULL DEFAULT 0,
        sources TEXT,
        source_policy TEXT NOT NULL,
        aggregate_confidence REAL,
        source_disagreement TEXT,
        headline_or_event TEXT,
        topic TEXT,
        data_warnings TEXT,
        model_version TEXT,
        source TEXT NOT NULL DEFAULT 'news_catalyst_aggregate',
        source_url TEXT,
        notes TEXT,
        as_of_date TEXT,
        effective_date TEXT,
        loaded_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        UNIQUE (ticker, signal_date, source)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS insider_transaction_source_snapshots (
        insider_transaction_source_snapshot_id INTEGER PRIMARY KEY,
        ticker TEXT NOT NULL,
        cik TEXT NOT NULL,
        accession_number TEXT NOT NULL,
        filing_date TEXT NOT NULL,
        transaction_date TEXT,
        owner_name TEXT,
        owner_title TEXT,
        transaction_code TEXT,
        acquired_disposed_code TEXT,
        shares REAL,
        price REAL,
        transaction_value REAL,
        source_url TEXT,
        provider_status TEXT NOT NULL DEFAULT 'ok',
        data_warnings TEXT,
        source TEXT NOT NULL DEFAULT 'sec_form4',
        as_of_date TEXT,
        effective_date TEXT,
        loaded_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        UNIQUE (
            ticker, accession_number, owner_name, transaction_date,
            transaction_code, acquired_disposed_code, shares, price, source
        )
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS short_interest_source_snapshots (
        short_interest_source_snapshot_id INTEGER PRIMARY KEY,
        ticker TEXT NOT NULL,
        settlement_date TEXT NOT NULL,
        publication_date TEXT,
        short_interest REAL,
        float_shares REAL,
        percent_float REAL,
        average_daily_volume REAL,
        days_to_cover REAL,
        source TEXT NOT NULL,
        source_url TEXT NOT NULL,
        notes TEXT,
        data_warnings TEXT,
        as_of_date TEXT,
        effective_date TEXT,
        loaded_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        UNIQUE (ticker, settlement_date, source)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS option_chain_snapshots (
        option_chain_snapshot_id INTEGER PRIMARY KEY,
        ticker TEXT NOT NULL,
        snapshot_timestamp TEXT NOT NULL,
        expiration_date TEXT NOT NULL,
        option_type TEXT NOT NULL,
        strike REAL NOT NULL,
        bid REAL NOT NULL,
        ask REAL NOT NULL,
        last REAL,
        mark REAL,
        volume REAL,
        open_interest REAL,
        implied_volatility REAL,
        delta REAL,
        gamma REAL,
        theta REAL,
        vega REAL,
        source TEXT NOT NULL,
        source_url TEXT,
        as_of_date TEXT,
        effective_date TEXT,
        loaded_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        UNIQUE (ticker, snapshot_timestamp, expiration_date, option_type, strike, source)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS option_income_reviews (
        option_income_review_id INTEGER PRIMARY KEY,
        ticker TEXT NOT NULL,
        review_date TEXT NOT NULL,
        snapshot_timestamp TEXT NOT NULL,
        expiration_date TEXT NOT NULL,
        option_type TEXT NOT NULL,
        strike REAL NOT NULL,
        bid REAL,
        ask REAL,
        mid_premium REAL,
        breakeven REAL,
        premium_yield REAL,
        annualized_yield REAL,
        downside_buffer_pct REAL,
        breakeven_buffer_pct REAL,
        assignment_notional REAL,
        open_interest REAL,
        volume REAL,
        implied_volatility REAL,
        delta REAL,
        current_price REAL,
        range_state TEXT,
        range_level REAL,
        review_category TEXT NOT NULL,
        risk_warnings TEXT,
        commentary_claim_count INTEGER NOT NULL DEFAULT 0,
        model_version TEXT NOT NULL,
        source TEXT NOT NULL,
        as_of_date TEXT,
        effective_date TEXT,
        loaded_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        UNIQUE (
            ticker, review_date, snapshot_timestamp, expiration_date,
            option_type, strike, model_version, source
        )
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS option_risk_reviews (
        option_risk_review_id INTEGER PRIMARY KEY,
        option_income_review_id INTEGER NOT NULL,
        ticker TEXT NOT NULL,
        review_date TEXT NOT NULL,
        risk_review_date TEXT NOT NULL,
        expiration_date TEXT NOT NULL,
        option_type TEXT NOT NULL,
        strike REAL NOT NULL,
        mid_premium REAL,
        breakeven REAL,
        current_price REAL,
        assignment_notional REAL,
        premium_income REAL,
        cash_secured_requirement REAL,
        max_cash_secured_loss REAL,
        scenario_pl_5pct REAL,
        scenario_pl_10pct REAL,
        scenario_pl_20pct REAL,
        projected_assignment_weight REAL,
        cash_after_assignment REAL,
        cash_reserve_after_assignment REAL,
        max_contracts_advisory INTEGER,
        total_portfolio_value REAL,
        cash_available REAL,
        position_weight REAL,
        risk_category TEXT NOT NULL,
        risk_warnings TEXT,
        model_version TEXT NOT NULL,
        source TEXT NOT NULL,
        as_of_date TEXT,
        effective_date TEXT,
        loaded_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (option_income_review_id)
            REFERENCES option_income_reviews (option_income_review_id),
        UNIQUE (option_income_review_id, model_version)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS option_review_outcomes (
        option_review_outcome_id INTEGER PRIMARY KEY,
        option_income_review_id INTEGER NOT NULL,
        option_risk_review_id INTEGER,
        ticker TEXT NOT NULL,
        review_date TEXT NOT NULL,
        outcome_date TEXT NOT NULL,
        expiration_date TEXT NOT NULL,
        option_type TEXT NOT NULL,
        strike REAL NOT NULL,
        mid_premium REAL,
        breakeven REAL,
        review_price REAL,
        latest_underlying_price REAL,
        latest_underlying_price_date TEXT,
        expiration_close REAL,
        expiration_price_date TEXT,
        expiration_status TEXT,
        outcome_status TEXT NOT NULL,
        completed_horizons TEXT,
        pending_horizons TEXT,
        return_5d REAL,
        return_20d REAL,
        return_to_latest REAL,
        above_strike_flag INTEGER,
        above_breakeven_flag INTEGER,
        touched_strike_flag INTEGER,
        touched_breakeven_flag INTEGER,
        max_favorable_excursion REAL,
        max_adverse_excursion REAL,
        linked_position_count INTEGER NOT NULL DEFAULT 0,
        data_warnings TEXT,
        model_version TEXT NOT NULL,
        source TEXT NOT NULL,
        as_of_date TEXT,
        effective_date TEXT,
        loaded_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (option_income_review_id)
            REFERENCES option_income_reviews (option_income_review_id),
        FOREIGN KEY (option_risk_review_id)
            REFERENCES option_risk_reviews (option_risk_review_id),
        UNIQUE (option_income_review_id, model_version)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS option_position_ledger (
        option_position_id INTEGER PRIMARY KEY,
        position_key TEXT NOT NULL UNIQUE,
        position_id TEXT,
        ticker TEXT NOT NULL,
        open_date TEXT NOT NULL,
        expiration_date TEXT NOT NULL,
        option_type TEXT NOT NULL,
        side TEXT NOT NULL,
        strike REAL NOT NULL,
        contracts REAL NOT NULL,
        premium REAL NOT NULL,
        close_date TEXT,
        close_price REAL,
        assigned_flag INTEGER,
        assignment_price REAL,
        fees REAL,
        account TEXT,
        position_status TEXT,
        roll_from_position_id TEXT,
        roll_to_position_id TEXT,
        underlying_assignment_date TEXT,
        underlying_shares REAL,
        underlying_cost_basis REAL,
        tags TEXT,
        data_warnings TEXT,
        model_version TEXT NOT NULL,
        source TEXT NOT NULL,
        source_url TEXT,
        notes TEXT,
        as_of_date TEXT,
        effective_date TEXT,
        loaded_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS option_position_lifecycle_reviews (
        option_position_lifecycle_review_id INTEGER PRIMARY KEY,
        position_key TEXT NOT NULL,
        position_id TEXT,
        ticker TEXT NOT NULL,
        lifecycle_review_date TEXT NOT NULL,
        open_date TEXT NOT NULL,
        expiration_date TEXT NOT NULL,
        option_type TEXT NOT NULL,
        side TEXT NOT NULL,
        strike REAL NOT NULL,
        contracts REAL NOT NULL,
        premium REAL NOT NULL,
        close_date TEXT,
        close_price REAL,
        assigned_flag INTEGER,
        assignment_price REAL,
        fees REAL,
        lifecycle_status TEXT NOT NULL,
        realized_pl REAL,
        open_pl_proxy REAL,
        assignment_notional REAL,
        cash_secured_requirement REAL,
        premium_income REAL,
        latest_option_mark REAL,
        latest_option_mark_timestamp TEXT,
        underlying_assignment_date TEXT,
        underlying_shares REAL,
        underlying_cost_basis REAL,
        linked_option_income_review_id INTEGER,
        linked_option_risk_review_id INTEGER,
        linked_option_review_outcome_id INTEGER,
        roll_from_position_id TEXT,
        roll_to_position_id TEXT,
        risk_warnings TEXT,
        model_version TEXT NOT NULL,
        source TEXT NOT NULL,
        as_of_date TEXT,
        effective_date TEXT,
        loaded_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (linked_option_income_review_id)
            REFERENCES option_income_reviews (option_income_review_id),
        FOREIGN KEY (linked_option_risk_review_id)
            REFERENCES option_risk_reviews (option_risk_review_id),
        FOREIGN KEY (linked_option_review_outcome_id)
            REFERENCES option_review_outcomes (option_review_outcome_id),
        UNIQUE (position_key, model_version)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS signals (
        signal_id INTEGER PRIMARY KEY,
        ticker TEXT NOT NULL,
        signal_date TEXT NOT NULL,
        signal_name TEXT NOT NULL,
        signal_family TEXT NOT NULL,
        value REAL,
        score REAL,
        direction TEXT,
        reason_code TEXT,
        source TEXT NOT NULL,
        model_version TEXT,
        confidence REAL,
        data_warnings TEXT,
        source_url TEXT,
        notes TEXT,
        as_of_date TEXT,
        effective_date TEXT,
        loaded_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        UNIQUE (ticker, signal_date, signal_name, source)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS signal_outcomes (
        signal_outcome_id INTEGER PRIMARY KEY,
        signal_id INTEGER,
        ticker TEXT NOT NULL,
        signal_date TEXT NOT NULL,
        signal_name TEXT NOT NULL,
        signal_family TEXT NOT NULL,
        signal_score REAL,
        signal_direction TEXT,
        outcome_date TEXT NOT NULL,
        outcome_status TEXT,
        entry_price REAL,
        entry_price_date TEXT,
        latest_price REAL,
        latest_price_date TEXT,
        completed_horizons TEXT,
        pending_horizons TEXT,
        return_5d REAL,
        return_20d REAL,
        return_60d REAL,
        return_120d REAL,
        directional_hit_flag INTEGER,
        hit_status TEXT,
        data_warnings TEXT,
        model_version TEXT,
        source TEXT NOT NULL DEFAULT 'signal_validation',
        as_of_date TEXT,
        effective_date TEXT,
        loaded_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (signal_id) REFERENCES signals (signal_id),
        UNIQUE (ticker, signal_date, signal_name, model_version, source)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS targets (
        target_id INTEGER PRIMARY KEY,
        ticker TEXT NOT NULL,
        target_date TEXT NOT NULL,
        base_target REAL,
        target_low REAL,
        target_high REAL,
        valuation_gap REAL,
        target_method TEXT,
        uncertainty_band REAL,
        valuation_score REAL,
        valuation_confidence REAL,
        method_count INTEGER,
        target_reason TEXT,
        data_warnings TEXT,
        model_version TEXT,
        source TEXT NOT NULL,
        as_of_date TEXT,
        effective_date TEXT,
        loaded_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        UNIQUE (ticker, target_date, model_version, source)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS scores (
        score_id INTEGER PRIMARY KEY,
        ticker TEXT NOT NULL,
        score_date TEXT NOT NULL,
        valuation_gap_score REAL,
        quality_score REAL,
        growth_score REAL,
        revision_score REAL,
        momentum_score REAL,
        sentiment_score REAL,
        catalyst_score REAL,
        risk_score REAL,
        liquidity_score REAL,
        confidence_score REAL,
        timing_score REAL,
        expected_value_score REAL,
        opportunity_score REAL,
        asset_type TEXT,
        score_model TEXT,
        threshold_set TEXT,
        score_reason TEXT,
        data_warnings TEXT,
        model_version TEXT,
        source TEXT NOT NULL,
        as_of_date TEXT,
        effective_date TEXT,
        loaded_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        UNIQUE (ticker, score_date, model_version, source)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS alerts (
        alert_id INTEGER PRIMARY KEY,
        alert_timestamp TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        ticker TEXT NOT NULL,
        alert_type TEXT NOT NULL,
        priority TEXT,
        status TEXT NOT NULL DEFAULT 'open',
        asset_type TEXT,
        current_price REAL,
        base_target REAL,
        target_low REAL,
        target_high REAL,
        target_date TEXT,
        score_date TEXT,
        valuation_gap REAL,
        required_gap REAL,
        opportunity_score REAL,
        expected_value_score REAL,
        confidence_score REAL,
        timing_score REAL,
        risk_score REAL,
        liquidity_score REAL,
        data_quality_score REAL,
        main_reasons TEXT,
        main_risks TEXT,
        reason_codes TEXT,
        risk_codes TEXT,
        data_warnings TEXT,
        invalidation TEXT,
        alert_model TEXT,
        threshold_set TEXT,
        model_version TEXT,
        source TEXT NOT NULL,
        as_of_date TEXT,
        effective_date TEXT,
        dedupe_key TEXT,
        loaded_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS alert_outcomes (
        outcome_id INTEGER PRIMARY KEY,
        alert_id INTEGER NOT NULL,
        outcome_date TEXT NOT NULL,
        ticker TEXT,
        alert_type TEXT,
        alert_timestamp TEXT,
        outcome_status TEXT,
        entry_price REAL,
        entry_price_date TEXT,
        latest_price REAL,
        latest_price_date TEXT,
        target_price REAL,
        invalidation_price REAL,
        completed_horizons TEXT,
        pending_horizons TEXT,
        return_5d REAL,
        return_20d REAL,
        return_60d REAL,
        return_120d REAL,
        hit_target_flag INTEGER,
        hit_invalidation_flag INTEGER,
        max_favorable_excursion REAL,
        max_adverse_excursion REAL,
        data_warnings TEXT,
        model_version TEXT,
        user_action TEXT,
        notes TEXT,
        source TEXT NOT NULL DEFAULT 'system',
        as_of_date TEXT,
        effective_date TEXT,
        loaded_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (alert_id) REFERENCES alerts (alert_id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS data_quality_checks (
        check_id INTEGER PRIMARY KEY,
        check_timestamp TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        check_name TEXT NOT NULL,
        status TEXT NOT NULL,
        details TEXT,
        source TEXT NOT NULL DEFAULT 'system',
        as_of_date TEXT,
        effective_date TEXT,
        loaded_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS model_versions (
        model_version TEXT PRIMARY KEY,
        description TEXT,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        source TEXT NOT NULL DEFAULT 'system',
        as_of_date TEXT,
        effective_date TEXT,
        loaded_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """,
)


@dataclass(frozen=True)
class DatabaseStatus:
    path: Path
    exists: bool
    required_table_count: int
    existing_required_table_count: int
    existing_tables: tuple[str, ...]


def connect(database_path: Path) -> sqlite3.Connection:
    database_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(database_path)
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def initialize_database(database_path: Path) -> DatabaseStatus:
    with closing(connect(database_path)) as connection:
        for statement in SCHEMA_STATEMENTS:
            connection.execute(statement)
        _ensure_optional_columns(connection, "assets", ASSET_OPTIONAL_COLUMNS)
        _ensure_optional_columns(connection, "targets", TARGET_OPTIONAL_COLUMNS)
        _ensure_optional_columns(connection, "scores", SCORE_OPTIONAL_COLUMNS)
        _ensure_optional_columns(connection, "signals", SIGNAL_OPTIONAL_COLUMNS)
        _ensure_optional_columns(connection, "range_snapshots", RANGE_OPTIONAL_COLUMNS)
        _ensure_optional_columns(connection, "alerts", ALERT_OPTIONAL_COLUMNS)
        _ensure_optional_columns(
            connection,
            "option_position_ledger",
            OPTION_POSITION_OPTIONAL_COLUMNS,
        )
        _ensure_optional_columns(
            connection,
            "alert_outcomes",
            ALERT_OUTCOME_OPTIONAL_COLUMNS,
        )
        connection.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_alerts_dedupe_key ON alerts (dedupe_key)"
        )
        connection.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_alert_outcomes_alert_id "
            "ON alert_outcomes (alert_id)"
        )
        connection.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_signal_outcomes_identity "
            "ON signal_outcomes (ticker, signal_date, signal_name, model_version, source)"
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_range_snapshots_latest "
            "ON range_snapshots (ticker, snapshot_timestamp)"
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_technical_signal_latest "
            "ON technical_signal_snapshots (ticker, signal_date)"
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_regime_signal_latest "
            "ON regime_signal_snapshots (ticker, signal_date)"
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_fundamental_benchmark_latest "
            "ON fundamental_benchmark_snapshots (benchmark_type, benchmark_key, benchmark_date)"
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_fundamental_comparison_latest "
            "ON fundamental_comparison_snapshots (ticker, comparison_date)"
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_research_recommendation_status "
            "ON research_recommendation_candidates (status, research_priority_score)"
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_research_recommendation_ticker "
            "ON research_recommendation_candidates (ticker, recommendation_date)"
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_research_recommendation_evidence "
            "ON research_recommendation_evidence (recommendation_key, evidence_date)"
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_missing_ticker_candidates_status "
            "ON missing_ticker_candidates (status, first_seen_source, ticker)"
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_missing_ticker_events_ticker "
            "ON missing_ticker_resolution_events (ticker, event_timestamp)"
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_trader_commentary_claims_ticker "
            "ON trader_commentary_claims (ticker, claim_date)"
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_trader_commentary_alias_ticker "
            "ON trader_commentary_instrument_aliases (canonical_ticker)"
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_trader_commentary_browser_runs_latest "
            "ON trader_commentary_browser_capture_runs (provider, started_at)"
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_trader_commentary_browser_items_run "
            "ON trader_commentary_browser_capture_items (run_id, accepted_flag)"
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_trader_commentary_discord_runs_latest "
            "ON trader_commentary_discord_capture_runs (provider, started_at)"
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_trader_commentary_discord_items_run "
            "ON trader_commentary_discord_capture_items (run_id, accepted_flag)"
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_trader_commentary_outcomes_ticker "
            "ON trader_commentary_claim_outcomes (ticker, outcome_date)"
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_notification_events_status "
            "ON notification_events (status, event_timestamp)"
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_option_risk_reviews_latest "
            "ON option_risk_reviews (ticker, risk_review_date)"
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_option_review_outcomes_latest "
            "ON option_review_outcomes (ticker, outcome_date)"
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_option_position_ledger_ticker "
            "ON option_position_ledger (ticker, open_date, expiration_date)"
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_option_position_lifecycle_ticker "
            "ON option_position_lifecycle_reviews (ticker, lifecycle_review_date)"
        )
        connection.commit()
    return get_database_status(database_path)


def _ensure_optional_columns(
    connection: sqlite3.Connection,
    table_name: str,
    columns: dict[str, str],
) -> None:
    existing = {
        row[1]
        for row in connection.execute(f"PRAGMA table_info({table_name})").fetchall()
    }
    for column_name, column_type in columns.items():
        if column_name not in existing:
            connection.execute(
                f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}"
            )


def get_database_status(database_path: Path) -> DatabaseStatus:
    if not database_path.exists():
        return DatabaseStatus(
            path=database_path,
            exists=False,
            required_table_count=len(REQUIRED_TABLES),
            existing_required_table_count=0,
            existing_tables=(),
        )

    with closing(sqlite3.connect(database_path)) as connection:
        rows = connection.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type = 'table'
            ORDER BY name
            """
        ).fetchall()

    existing_tables = tuple(row[0] for row in rows)
    existing_required = tuple(table for table in REQUIRED_TABLES if table in existing_tables)

    return DatabaseStatus(
        path=database_path,
        exists=True,
        required_table_count=len(REQUIRED_TABLES),
        existing_required_table_count=len(existing_required),
        existing_tables=existing_tables,
    )
