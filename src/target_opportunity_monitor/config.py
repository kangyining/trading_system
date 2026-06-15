from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field
from pathlib import Path
import tomllib


def default_project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def default_scheduler_automations_dir() -> Path:
    try:
        return Path.home() / ".codex" / "automations"
    except RuntimeError:
        return Path(".codex") / "automations"


@dataclass(frozen=True)
class AppConfig:
    project_root: Path
    config_path: Path
    database_path: Path
    reports_dir: Path
    watchlist_path: Path
    market_data_dir: Path
    manual_prices_dir: Path
    market_data_primary_source: str
    market_data_secondary_source: str
    market_data_mode: str
    market_data_lookback_days: int
    market_data_stale_after_days: int
    market_data_minimum_history_days: int
    universe_mode: str
    run_mode: str
    report_title: str
    market_data_symbol_aliases_path: Path = field(
        default_factory=lambda: Path("data/market_data/source_exports/provider_symbol_aliases.csv")
    )
    fundamentals_path: Path = field(
        default_factory=lambda: Path("data/fundamentals/manual/fundamentals.csv")
    )
    estimates_path: Path = field(
        default_factory=lambda: Path("data/fundamentals/manual/estimates.csv")
    )
    etf_navs_path: Path = field(default_factory=lambda: Path("data/etf/manual/etf_navs.csv"))
    etf_holdings_path: Path = field(
        default_factory=lambda: Path("data/etf/manual/etf_holdings.csv")
    )
    portfolio_positions_path: Path = field(
        default_factory=lambda: Path("data/portfolio/manual/positions.csv")
    )
    portfolio_cash_path: Path = field(
        default_factory=lambda: Path("data/portfolio/manual/cash.csv")
    )
    analyst_revisions_path: Path = field(
        default_factory=lambda: Path("data/signals/manual/analyst_revisions.csv")
    )
    analyst_revision_source_export_path: Path = field(
        default_factory=lambda: Path(
            "data/signals/source_exports/analyst_revision_source_export.csv"
        )
    )
    analyst_revision_source_exports_dir: Path = field(
        default_factory=lambda: Path("data/signals/source_exports")
    )
    news_catalysts_path: Path = field(
        default_factory=lambda: Path("data/signals/manual/news_catalysts.csv")
    )
    trader_commentary_path: Path = field(
        default_factory=lambda: Path("data/signals/manual/trader_commentary.csv")
    )
    trader_commentary_aliases_path: Path = field(
        default_factory=lambda: Path(
            "data/signals/manual/trader_commentary_instrument_aliases.csv"
        )
    )
    trader_commentary_label_dispositions_path: Path = field(
        default_factory=lambda: Path(
            "data/signals/manual/trader_commentary_label_dispositions.csv"
        )
    )
    trader_commentary_exports_dir: Path = field(
        default_factory=lambda: Path("data/signals/source_exports/trader_commentary")
    )
    trader_commentary_browser_capture_dir: Path = field(
        default_factory=lambda: Path("data/signals/browser_captures/trader_commentary")
    )
    trader_commentary_discord_capture_dir: Path = field(
        default_factory=lambda: Path("data/signals/discord_captures/trader_commentary")
    )
    short_interest_path: Path = field(
        default_factory=lambda: Path("data/signals/manual/short_interest.csv")
    )
    options_chain_path: Path = field(
        default_factory=lambda: Path("data/options/manual/options_chain.csv")
    )
    options_positions_path: Path = field(
        default_factory=lambda: Path("data/options/manual/options_positions.csv")
    )
    options_chain_source_exports_dir: Path = field(
        default_factory=lambda: Path("data/options/source_exports")
    )
    account_source_exports_dir: Path = field(
        default_factory=lambda: Path("data/account/source_exports")
    )
    options_chain_cache_dir: Path = field(
        default_factory=lambda: Path("data/options/cache/chains")
    )
    short_interest_cache_dir: Path = field(
        default_factory=lambda: Path("data/signals/cache/short_interest")
    )
    news_catalyst_source_exports_dir: Path = field(
        default_factory=lambda: Path("data/signals/source_exports/news_catalysts")
    )
    news_catalyst_cache_dir: Path = field(
        default_factory=lambda: Path("data/signals/cache/news_catalysts")
    )
    notification_outbox_dir: Path = field(
        default_factory=lambda: Path("data/notifications/outbox")
    )
    ops_loop_dir: Path = field(default_factory=lambda: Path("data/ops/loop"))
    scheduler_automations_dir: Path = field(
        default_factory=default_scheduler_automations_dir
    )
    insider_cache_dir: Path = field(
        default_factory=lambda: Path("data/signals/cache/insider_transactions")
    )
    fundamental_cache_dir: Path = field(
        default_factory=lambda: Path("data/fundamentals/cache")
    )
    universe_candidates_path: Path = field(
        default_factory=lambda: Path("configs/universe_candidates.csv")
    )
    sector_benchmarks_path: Path = field(
        default_factory=lambda: Path("configs/sector_benchmarks.csv")
    )
    research_recommendations_path: Path = field(
        default_factory=lambda: Path("data/research/manual/research_recommendations.csv")
    )
    foreign_equity_identity_path: Path = field(
        default_factory=lambda: Path("data/research/source_exports/foreign_equity_identity.csv")
    )
    foreign_equity_fundamentals_source_path: Path = field(
        default_factory=lambda: Path(
            "data/research/source_exports/foreign_equity_fundamentals.csv"
        )
    )
    foreign_equity_estimates_source_path: Path = field(
        default_factory=lambda: Path(
            "data/research/source_exports/foreign_equity_estimates.csv"
        )
    )
    foreign_equity_analyst_targets_source_path: Path = field(
        default_factory=lambda: Path(
            "data/research/source_exports/foreign_equity_analyst_targets.csv"
        )
    )
    external_research_signals_db_path: Path = field(
        default_factory=lambda: Path("../research/research-signals/data/x_posts.sqlite")
    )
    cik_map_path: Path = field(default_factory=lambda: Path("configs/cik_map.csv"))
    stock_splits_path: Path = field(
        default_factory=lambda: Path("configs/stock_splits.csv")
    )
    valuation_model_version: str = "valuation_mvp_v1"
    valuation_default_uncertainty_band: float = 0.25
    valuation_minimum_methods: int = 1
    valuation_minimum_peer_count: int = 2
    valuation_stale_fundamentals_after_days: int = 550
    valuation_stale_estimates_after_days: int = 120
    etf_model_version: str = "etf_nav_mvp_v1"
    etf_default_premium_discount_band: float = 0.005
    etf_stale_nav_after_days: int = 7
    etf_stale_holdings_after_days: int = 14
    etf_minimum_holdings: int = 10
    etf_premium_discount_history_days: int = 60
    fundamental_seed_years: int = 3
    sec_user_agent: str = "TargetOpportunityMonitor/0.1 research@example.com"
    ibkr_host: str = "127.0.0.1"
    ibkr_paper_port: int = 4002
    ibkr_live_port: int = 4001
    ibkr_client_id: int = 930
    ibkr_timeout_seconds: int = 12
    ibkr_market_data_type: str = "delayed_frozen"
    scoring_equity_model_version: str = "equity_score_mvp_v1"
    scoring_etf_model_version: str = "etf_score_mvp_v1"
    scoring_equity_threshold_set: str = "equity_default"
    scoring_etf_threshold_set: str = "etf_liquid_index"
    alerts_equity_model_version: str = "equity_alert_mvp_v1"
    alerts_etf_model_version: str = "etf_alert_mvp_v1"
    alerts_equity_threshold_set: str = "equity_default"
    alerts_etf_threshold_set: str = "etf_liquid_index"
    alerts_minimum_bullish_valuation_gap: float = 0.10
    alerts_minimum_expected_value_score: float = 70.0
    alerts_minimum_confidence_score: float = 60.0
    alerts_minimum_liquidity_score: float = 60.0
    alerts_minimum_risk_score: float = 40.0
    alerts_minimum_data_quality_score: float = 75.0
    alerts_watch_gap_threshold: float = 0.15
    alerts_watch_opportunity_score: float = 65.0
    alerts_bearish_overvaluation_gap: float = -0.10
    alerts_risk_warning_score_below: float = 35.0
    alerts_etf_watch_nav_discount_gap: float = 0.001
    alerts_etf_action_nav_discount_gap: float = 0.005
    alerts_etf_premium_warning_gap: float = -0.005
    alerts_etf_minimum_opportunity_score: float = 65.0
    alerts_etf_minimum_liquidity_score: float = 70.0
    alerts_etf_minimum_risk_score: float = 50.0
    alerts_etf_minimum_data_quality_score: float = 75.0
    portfolio_model_version: str = "portfolio_context_mvp_v1"
    portfolio_base_currency: str = "USD"
    portfolio_default_max_position_weight: float = 0.15
    portfolio_default_starter_position_weight: float = 0.03
    portfolio_default_add_position_weight: float = 0.05
    portfolio_cash_reserve_weight: float = 0.05
    portfolio_max_sector_weight: float = 0.35
    portfolio_stale_positions_after_days: int = 14
    signals_analyst_revision_model_version: str = "analyst_revision_mvp_v1"
    signals_analyst_revision_shadow_mode: bool = True
    signals_news_catalyst_model_version: str = "news_catalyst_mvp_v1"
    signals_news_catalyst_shadow_mode: bool = True
    signals_news_catalyst_stale_after_days: int = 30
    signals_news_catalyst_provider_order: tuple[str, ...] = (
        "alpha_vantage",
        "marketaux",
        "eodhd",
        "finnhub",
        "fmp",
        "x_recent_search",
        "truth_social_public",
        "source_export",
    )
    signals_news_catalyst_enabled_providers: tuple[str, ...] = (
        "alpha_vantage",
        "marketaux",
        "eodhd",
        "finnhub",
        "fmp",
        "x_recent_search",
        "truth_social_public",
        "source_export",
    )
    signals_news_catalyst_text_backfill_enabled: bool = True
    signals_news_catalyst_text_backfill_model_version: str = "news_text_lexicon_mvp_v1"
    signals_news_catalyst_min_numeric_coverage: int = 13
    signals_news_catalyst_social_accounts: tuple[str, ...] = ("KobeissiLetter",)
    signals_news_catalyst_manual_influencer_sources: tuple[str, ...] = (
        "serenity",
        "kobeissi_letter",
    )
    signals_news_catalyst_source_policy: str = "weighted_median"
    signals_news_catalyst_lookback_days: int = 14
    signals_news_catalyst_max_items_per_ticker: int = 5
    signals_news_catalyst_disagreement_warning_threshold: float = 15.0
    signals_news_catalyst_high_disagreement_threshold: float = 30.0
    signals_news_catalyst_min_sources_for_aggregate: int = 1
    signals_news_catalyst_provider_request_budget: int = 3
    signals_news_catalyst_provider_retry_delay_seconds: float = 1.0
    signals_news_catalyst_cache_stale_hours: int = 24
    signals_news_catalyst_use_cache: bool = True
    signals_insider_activity_model_version: str = "insider_activity_mvp_v1"
    signals_insider_activity_shadow_mode: bool = True
    signals_insider_activity_lookback_days: int = 180
    signals_insider_activity_stale_after_days: int = 14
    signals_insider_activity_fetch_limit_per_ticker: int = 40
    signals_insider_activity_max_tickers_per_run: int = 13
    signals_insider_activity_use_cache: bool = True
    signals_insider_activity_sec_request_delay_seconds: float = 0.2
    signals_insider_activity_sec_rate_limit_cooldown_seconds: float = 60.0
    signals_insider_activity_stop_on_rate_limit: bool = True
    signals_insider_activity_max_live_form4_fetches_per_ticker: int = 10
    signals_insider_activity_skip_successful_fetch_same_day: bool = True
    signals_insider_activity_min_transaction_value: float = 10000.0
    signals_short_interest_model_version: str = "short_interest_mvp_v1"
    signals_short_interest_shadow_mode: bool = True
    signals_short_interest_stale_after_days: int = 45
    signals_short_interest_provider_order: tuple[str, ...] = (
        "finra",
        "nasdaq_trader",
        "provider_export",
        "exchange_manual",
        "broker_manual",
    )
    signals_short_interest_provider_timeout_seconds: int = 12
    signals_short_interest_provider_retry_delay_seconds: float = 1.0
    signals_short_interest_provider_cache_stale_hours: int = 24
    signals_short_interest_provider_max_tickers_per_run: int = 13
    signals_short_interest_provider_use_cache: bool = True
    options_model_version: str = "options_sell_put_mvp_v1"
    options_default_min_dte: int = 7
    options_default_max_dte: int = 60
    options_min_annualized_premium_yield: float = 0.10
    options_min_open_interest: int = 100
    options_min_volume: int = 10
    options_assignment_buffer_pct: float = 0.10
    options_use_range_filter: bool = True
    options_chain_source: str = "auto"
    options_option_fetch_universe: str = "scoreable_plus_commentary_options"
    options_ibkr_exchange: str = "SMART"
    options_ibkr_currency: str = "USD"
    options_chain_stale_after_minutes: int = 30
    options_max_expirations_per_ticker: int = 4
    options_max_strikes_per_expiration: int = 12
    options_strike_window_pct: float = 0.30
    options_fetch_puts_only: bool = True
    options_auto_fetch_daily: bool = True
    options_auto_fetch_intraday: bool = False
    options_max_tickers_per_run: int = 3
    options_risk_model_version: str = "options_risk_margin_mvp_v1"
    options_risk_margin_model: str = "cash_secured_proxy"
    options_max_single_contract_notional_weight: float = 0.05
    options_max_total_assignment_notional_weight: float = 0.20
    options_minimum_cash_reserve_after_assignment: float = 0.05
    options_downside_scenario_pcts: tuple[float, ...] = (-0.05, -0.10, -0.20)
    options_reference_instrument_risk_warning: bool = True
    options_outcome_model_version: str = "options_outcome_mvp_v1"
    options_position_model_version: str = "options_position_ledger_mvp_v1"
    options_lifecycle_model_version: str = "options_lifecycle_mvp_v1"
    options_realized_pl_model_version: str = "options_realized_pl_mvp_v1"
    options_option_multiplier: int = 100
    options_position_stale_after_days: int = 7
    options_assignment_tracking_enabled: bool = True
    options_outcome_horizons: tuple[str, ...] = ("5d", "20d", "expiration")
    options_outcome_use_underlying_prices_only: bool = True
    signals_trader_commentary_model_version: str = "trader_commentary_mvp_v1"
    signals_trader_commentary_shadow_mode: bool = True
    signals_trader_commentary_default_horizons: tuple[str, ...] = (
        "1d",
        "5d",
        "20d",
        "60d",
    )
    signals_trader_commentary_stale_after_days: int = 30
    commentary_browser_capture_enabled: bool = False
    commentary_browser_capture_provider: str = "x_browser"
    commentary_browser_capture_target_urls: tuple[str, ...] = ()
    commentary_browser_capture_max_scroll_batches: int = 3
    commentary_browser_capture_min_seconds_between_runs: int = 900
    commentary_browser_capture_require_operator_acknowledgement: bool = True
    commentary_discord_capture_enabled: bool = False
    commentary_discord_capture_provider: str = "discord_gateway"
    commentary_discord_capture_channel_ids: tuple[str, ...] = ()
    commentary_discord_capture_max_messages_per_run: int = 100
    commentary_discord_capture_min_seconds_between_runs: int = 900
    commentary_discord_capture_require_operator_acknowledgement: bool = True
    signals_minimum_revision_inputs: int = 1
    signals_stale_after_days: int = 45
    signals_revision_evidence_min_source_tickers: int = 3
    signals_revision_evidence_min_signal_tickers: int = 3
    signals_revision_evidence_min_completed_20d: int = 3
    signals_revision_evidence_min_hit_rate_20d: float = 0.55
    signals_revision_evidence_min_avg_return_20d: float = 0.0
    signals_revision_evidence_min_confidence: float = 60.0
    signals_revision_provider_order: tuple[str, ...] = (
        "alpha_vantage",
        "fmp",
        "business_quant",
        "finnhub",
        "yfinance",
        "ibkr",
        "source_export",
    )
    signals_revision_enabled_providers: tuple[str, ...] = (
        "alpha_vantage",
        "fmp",
        "business_quant",
        "finnhub",
        "yfinance",
        "source_export",
    )
    signals_revision_source_policy: str = "weighted_median"
    signals_revision_disagreement_warning_threshold: float = 0.05
    signals_revision_high_disagreement_threshold: float = 0.10
    signals_revision_min_sources_for_aggregate: int = 1
    realtime_source: str = "ibkr"
    realtime_quote_stale_after_seconds: int = 900
    realtime_range_model_version: str = "range_monitor_mvp_v1"
    realtime_notification_cooldown_minutes: int = 60
    realtime_monitor_active_assets_only: bool = True
    realtime_intraday_cycle_stale_after_seconds: int = 1800
    realtime_notification_pending_stale_after_seconds: int = 1800
    realtime_manual_ops_loop_interval_seconds: int = 600
    research_preparation_auto_enabled: bool = True
    research_preparation_auto_source: str = "all"
    research_preparation_auto_min_seconds_between_runs: int = 21600
    api_host: str = "127.0.0.1"
    api_port: int = 8765
    api_allowed_origins: tuple[str, ...] = (
        "http://127.0.0.1:5173",
        "http://localhost:5173",
    )
    api_require_mutation_confirmation: bool = True
    technical_model_version: str = "technical_levels_mvp_v1"
    technical_lookback_days: int = 252
    technical_minimum_history_days: int = 120
    technical_short_ma_days: int = 20
    technical_medium_ma_days: int = 50
    technical_long_ma_days: int = 200
    technical_pivot_window_days: int = 5
    technical_near_level_pct: float = 0.02
    technical_breakout_buffer_pct: float = 0.01
    regime_model_version: str = "market_regime_mvp_v1"
    regime_benchmark_tickers: tuple[str, ...] = ("SPY", "QQQ")
    regime_sector_proxy_tickers: tuple[str, ...] = (
        "XLK",
        "XLY",
        "XLV",
        "XLF",
        "XLI",
        "XLP",
        "XLU",
        "XLE",
        "XLC",
        "XLB",
        "XLRE",
    )
    regime_relative_strength_lookback_days: int = 63
    fundamental_benchmark_model_version: str = "fundamental_benchmark_mvp_v1"
    fundamental_benchmark_min_sector_peer_count: int = 3
    fundamental_benchmark_min_industry_peer_count: int = 2


def _resolve_project_path(project_root: Path, value: str) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    return project_root / path


def _as_tuple(value: object, default: tuple[str, ...]) -> tuple[str, ...]:
    if value is None:
        return default
    if isinstance(value, str):
        return tuple(part.strip() for part in value.split(",") if part.strip())
    if isinstance(value, (list, tuple)):
        return tuple(str(part).strip() for part in value if str(part).strip())
    return default


def load_config(config_path: str | Path | None = None) -> AppConfig:
    project_root = default_project_root()
    resolved_config_path = (
        Path(config_path).resolve()
        if config_path is not None
        else project_root / "configs" / "default.toml"
    )

    raw_config = tomllib.loads(resolved_config_path.read_text(encoding="utf-8-sig"))

    paths = raw_config.get("paths", {})
    if "project_root" in paths:
        project_root = _resolve_project_path(project_root, str(paths["project_root"]))
    market_data = raw_config.get("market_data", {})
    valuation = raw_config.get("valuation", {})
    etf = raw_config.get("etf", {})
    fundamentals = raw_config.get("fundamentals", {})
    sec = raw_config.get("sec", {})
    ibkr = raw_config.get("ibkr", {})
    scoring = raw_config.get("scoring", {})
    alerts = raw_config.get("alerts", {})
    portfolio = raw_config.get("portfolio", {})
    signals = raw_config.get("signals", {})
    options = raw_config.get("options", {})
    run = raw_config.get("run", {})
    reports = raw_config.get("reports", {})
    realtime = raw_config.get("realtime", {})
    research_preparation = raw_config.get("research_preparation", {})
    api = raw_config.get("api", {})
    technical = raw_config.get("technical", {})
    regime = raw_config.get("regime", {})
    fundamental_benchmarks = raw_config.get("fundamental_benchmarks", {})
    commentary_browser_capture = raw_config.get("commentary_browser_capture", {})
    commentary_discord_capture = raw_config.get("commentary_discord_capture", {})

    database_path = _resolve_project_path(
        project_root, paths.get("database", "data/tom.sqlite")
    )
    reports_dir = _resolve_project_path(project_root, paths.get("reports", "reports"))
    watchlist_path = _resolve_project_path(
        project_root, paths.get("watchlist", "configs/watchlist.csv")
    )
    market_data_dir = _resolve_project_path(
        project_root, paths.get("market_data", "data/market_data")
    )
    manual_prices_dir = _resolve_project_path(
        project_root, paths.get("manual_prices", "data/market_data/manual")
    )
    market_data_symbol_aliases_path = _resolve_project_path(
        project_root,
        paths.get(
            "market_data_symbol_aliases",
            "data/market_data/source_exports/provider_symbol_aliases.csv",
        ),
    )
    fundamentals_path = _resolve_project_path(
        project_root,
        paths.get("fundamentals", "data/fundamentals/manual/fundamentals.csv"),
    )
    estimates_path = _resolve_project_path(
        project_root, paths.get("estimates", "data/fundamentals/manual/estimates.csv")
    )
    etf_navs_path = _resolve_project_path(
        project_root, paths.get("etf_navs", "data/etf/manual/etf_navs.csv")
    )
    etf_holdings_path = _resolve_project_path(
        project_root, paths.get("etf_holdings", "data/etf/manual/etf_holdings.csv")
    )
    portfolio_positions_path = _resolve_project_path(
        project_root,
        paths.get("portfolio_positions", "data/portfolio/manual/positions.csv"),
    )
    portfolio_cash_path = _resolve_project_path(
        project_root, paths.get("portfolio_cash", "data/portfolio/manual/cash.csv")
    )
    analyst_revisions_path = _resolve_project_path(
        project_root,
        paths.get("analyst_revisions", "data/signals/manual/analyst_revisions.csv"),
    )
    analyst_revision_source_export_path = _resolve_project_path(
        project_root,
        paths.get(
            "analyst_revision_source_export",
            "data/signals/source_exports/analyst_revision_source_export.csv",
        ),
    )
    analyst_revision_source_exports_dir = _resolve_project_path(
        project_root,
        paths.get("analyst_revision_source_exports_dir", "data/signals/source_exports"),
    )
    news_catalysts_path = _resolve_project_path(
        project_root,
        paths.get("news_catalysts", "data/signals/manual/news_catalysts.csv"),
    )
    trader_commentary_path = _resolve_project_path(
        project_root,
        paths.get("trader_commentary", "data/signals/manual/trader_commentary.csv"),
    )
    trader_commentary_aliases_path = _resolve_project_path(
        project_root,
        paths.get(
            "trader_commentary_aliases",
            "data/signals/manual/trader_commentary_instrument_aliases.csv",
        ),
    )
    trader_commentary_label_dispositions_path = _resolve_project_path(
        project_root,
        paths.get(
            "trader_commentary_label_dispositions",
            "data/signals/manual/trader_commentary_label_dispositions.csv",
        ),
    )
    trader_commentary_exports_dir = _resolve_project_path(
        project_root,
        paths.get(
            "trader_commentary_exports",
            "data/signals/source_exports/trader_commentary",
        ),
    )
    trader_commentary_browser_capture_dir = _resolve_project_path(
        project_root,
        paths.get(
            "trader_commentary_browser_capture",
            "data/signals/browser_captures/trader_commentary",
        ),
    )
    trader_commentary_discord_capture_dir = _resolve_project_path(
        project_root,
        paths.get(
            "trader_commentary_discord_capture",
            "data/signals/discord_captures/trader_commentary",
        ),
    )
    short_interest_path = _resolve_project_path(
        project_root,
        paths.get("short_interest", "data/signals/manual/short_interest.csv"),
    )
    options_chain_path = _resolve_project_path(
        project_root,
        paths.get("options_chain", "data/options/manual/options_chain.csv"),
    )
    options_positions_path = _resolve_project_path(
        project_root,
        paths.get("options_positions", "data/options/manual/options_positions.csv"),
    )
    options_chain_source_exports_dir = _resolve_project_path(
        project_root,
        paths.get("options_chain_source_exports", "data/options/source_exports"),
    )
    account_source_exports_dir = _resolve_project_path(
        project_root,
        paths.get("account_source_exports", "data/account/source_exports"),
    )
    options_chain_cache_dir = _resolve_project_path(
        project_root,
        paths.get("options_chain_cache", "data/options/cache/chains"),
    )
    short_interest_cache_dir = _resolve_project_path(
        project_root,
        paths.get("short_interest_cache", "data/signals/cache/short_interest"),
    )
    news_catalyst_source_exports_dir = _resolve_project_path(
        project_root,
        paths.get(
            "news_catalyst_source_exports_dir",
            "data/signals/source_exports/news_catalysts",
        ),
    )
    news_catalyst_cache_dir = _resolve_project_path(
        project_root,
        paths.get(
            "news_catalyst_cache",
            "data/signals/cache/news_catalysts",
        ),
    )
    notification_outbox_dir = _resolve_project_path(
        project_root,
        paths.get("notification_outbox", "data/notifications/outbox"),
    )
    ops_loop_dir = _resolve_project_path(
        project_root,
        paths.get("ops_loop", "data/ops/loop"),
    )
    scheduler_automations_dir_value = paths.get("scheduler_automations")
    scheduler_automations_dir = (
        _resolve_project_path(project_root, str(scheduler_automations_dir_value))
        if scheduler_automations_dir_value
        else default_scheduler_automations_dir()
    )
    insider_cache_dir = _resolve_project_path(
        project_root,
        paths.get(
            "insider_cache",
            "data/signals/cache/insider_transactions",
        ),
    )
    fundamental_cache_dir = _resolve_project_path(
        project_root, paths.get("fundamental_cache", "data/fundamentals/cache")
    )
    universe_candidates_path = _resolve_project_path(
        project_root,
        paths.get("universe_candidates", "configs/universe_candidates.csv"),
    )
    sector_benchmarks_path = _resolve_project_path(
        project_root,
        paths.get("sector_benchmarks", "configs/sector_benchmarks.csv"),
    )
    research_recommendations_path = _resolve_project_path(
        project_root,
        paths.get(
            "research_recommendations",
            "data/research/manual/research_recommendations.csv",
        ),
    )
    foreign_equity_identity_path = _resolve_project_path(
        project_root,
        paths.get(
            "foreign_equity_identity",
            "data/research/source_exports/foreign_equity_identity.csv",
        ),
    )
    foreign_equity_fundamentals_source_path = _resolve_project_path(
        project_root,
        paths.get(
            "foreign_equity_fundamentals_source",
            "data/research/source_exports/foreign_equity_fundamentals.csv",
        ),
    )
    foreign_equity_estimates_source_path = _resolve_project_path(
        project_root,
        paths.get(
            "foreign_equity_estimates_source",
            "data/research/source_exports/foreign_equity_estimates.csv",
        ),
    )
    foreign_equity_analyst_targets_source_path = _resolve_project_path(
        project_root,
        paths.get(
            "foreign_equity_analyst_targets_source",
            "data/research/source_exports/foreign_equity_analyst_targets.csv",
        ),
    )
    external_research_signals_db_path = _resolve_project_path(
        project_root,
        paths.get(
            "external_research_signals_db",
            "../research/research-signals/data/x_posts.sqlite",
        ),
    )
    cik_map_path = _resolve_project_path(
        project_root, paths.get("cik_map", "configs/cik_map.csv")
    )
    stock_splits_path = _resolve_project_path(
        project_root, paths.get("stock_splits", "configs/stock_splits.csv")
    )

    return AppConfig(
        project_root=project_root,
        config_path=resolved_config_path,
        database_path=database_path,
        reports_dir=reports_dir,
        watchlist_path=watchlist_path,
        market_data_dir=market_data_dir,
        manual_prices_dir=manual_prices_dir,
        market_data_symbol_aliases_path=market_data_symbol_aliases_path,
        fundamentals_path=fundamentals_path,
        estimates_path=estimates_path,
        etf_navs_path=etf_navs_path,
        etf_holdings_path=etf_holdings_path,
        portfolio_positions_path=portfolio_positions_path,
        portfolio_cash_path=portfolio_cash_path,
        analyst_revisions_path=analyst_revisions_path,
        analyst_revision_source_export_path=analyst_revision_source_export_path,
        analyst_revision_source_exports_dir=analyst_revision_source_exports_dir,
        news_catalysts_path=news_catalysts_path,
        trader_commentary_path=trader_commentary_path,
        trader_commentary_aliases_path=trader_commentary_aliases_path,
        trader_commentary_label_dispositions_path=(
            trader_commentary_label_dispositions_path
        ),
        trader_commentary_exports_dir=trader_commentary_exports_dir,
        trader_commentary_browser_capture_dir=trader_commentary_browser_capture_dir,
        trader_commentary_discord_capture_dir=trader_commentary_discord_capture_dir,
        short_interest_path=short_interest_path,
        options_chain_path=options_chain_path,
        options_positions_path=options_positions_path,
        options_chain_source_exports_dir=options_chain_source_exports_dir,
        account_source_exports_dir=account_source_exports_dir,
        options_chain_cache_dir=options_chain_cache_dir,
        short_interest_cache_dir=short_interest_cache_dir,
        news_catalyst_source_exports_dir=news_catalyst_source_exports_dir,
        news_catalyst_cache_dir=news_catalyst_cache_dir,
        notification_outbox_dir=notification_outbox_dir,
        ops_loop_dir=ops_loop_dir,
        scheduler_automations_dir=scheduler_automations_dir,
        insider_cache_dir=insider_cache_dir,
        fundamental_cache_dir=fundamental_cache_dir,
        universe_candidates_path=universe_candidates_path,
        sector_benchmarks_path=sector_benchmarks_path,
        research_recommendations_path=research_recommendations_path,
        foreign_equity_identity_path=foreign_equity_identity_path,
        foreign_equity_fundamentals_source_path=foreign_equity_fundamentals_source_path,
        foreign_equity_estimates_source_path=foreign_equity_estimates_source_path,
        foreign_equity_analyst_targets_source_path=foreign_equity_analyst_targets_source_path,
        external_research_signals_db_path=external_research_signals_db_path,
        cik_map_path=cik_map_path,
        stock_splits_path=stock_splits_path,
        market_data_primary_source=market_data.get("primary_source", "stooq"),
        market_data_secondary_source=market_data.get("secondary_source", "yahoo_chart"),
        market_data_mode=market_data.get("mode", "auto"),
        market_data_lookback_days=int(market_data.get("lookback_days", 800)),
        market_data_stale_after_days=int(market_data.get("stale_after_days", 7)),
        market_data_minimum_history_days=int(market_data.get("minimum_history_days", 252)),
        valuation_model_version=valuation.get("model_version", "valuation_mvp_v1"),
        valuation_default_uncertainty_band=float(
            valuation.get("default_uncertainty_band", 0.25)
        ),
        valuation_minimum_methods=int(valuation.get("minimum_methods", 1)),
        valuation_minimum_peer_count=int(valuation.get("minimum_peer_count", 2)),
        valuation_stale_fundamentals_after_days=int(
            valuation.get("stale_fundamentals_after_days", 550)
        ),
        valuation_stale_estimates_after_days=int(
            valuation.get("stale_estimates_after_days", 120)
        ),
        etf_model_version=etf.get("model_version", "etf_nav_mvp_v1"),
        etf_default_premium_discount_band=float(
            etf.get("default_premium_discount_band", 0.005)
        ),
        etf_stale_nav_after_days=int(etf.get("stale_nav_after_days", 7)),
        etf_stale_holdings_after_days=int(etf.get("stale_holdings_after_days", 14)),
        etf_minimum_holdings=int(etf.get("minimum_holdings", 10)),
        etf_premium_discount_history_days=int(
            etf.get("premium_discount_history_days", 60)
        ),
        fundamental_seed_years=int(fundamentals.get("seed_years", 3)),
        sec_user_agent=sec.get(
            "user_agent", "TargetOpportunityMonitor/0.1 research@example.com"
        ),
        ibkr_host=ibkr.get("host", "127.0.0.1"),
        ibkr_paper_port=int(ibkr.get("paper_port", 4002)),
        ibkr_live_port=int(ibkr.get("live_port", 4001)),
        ibkr_client_id=int(ibkr.get("client_id", 930)),
        ibkr_timeout_seconds=int(ibkr.get("timeout_seconds", 12)),
        ibkr_market_data_type=ibkr.get("market_data_type", "delayed_frozen"),
        scoring_equity_model_version=scoring.get(
            "equity_model_version", "equity_score_mvp_v1"
        ),
        scoring_etf_model_version=scoring.get(
            "etf_model_version", "etf_score_mvp_v1"
        ),
        scoring_equity_threshold_set=scoring.get(
            "equity_threshold_set", "equity_default"
        ),
        scoring_etf_threshold_set=scoring.get(
            "etf_threshold_set", "etf_liquid_index"
        ),
        alerts_equity_model_version=alerts.get(
            "equity_model_version", "equity_alert_mvp_v1"
        ),
        alerts_etf_model_version=alerts.get("etf_model_version", "etf_alert_mvp_v1"),
        alerts_equity_threshold_set=alerts.get(
            "equity_threshold_set", "equity_default"
        ),
        alerts_etf_threshold_set=alerts.get("etf_threshold_set", "etf_liquid_index"),
        alerts_minimum_bullish_valuation_gap=float(
            alerts.get("minimum_bullish_valuation_gap", 0.10)
        ),
        alerts_minimum_expected_value_score=float(
            alerts.get("minimum_expected_value_score", 70)
        ),
        alerts_minimum_confidence_score=float(
            alerts.get("minimum_confidence_score", 60)
        ),
        alerts_minimum_liquidity_score=float(
            alerts.get("minimum_liquidity_score", 60)
        ),
        alerts_minimum_risk_score=float(alerts.get("minimum_risk_score", 40)),
        alerts_minimum_data_quality_score=float(
            alerts.get("minimum_data_quality_score", 75)
        ),
        alerts_watch_gap_threshold=float(alerts.get("watch_gap_threshold", 0.15)),
        alerts_watch_opportunity_score=float(alerts.get("watch_opportunity_score", 65)),
        alerts_bearish_overvaluation_gap=float(
            alerts.get("bearish_overvaluation_gap", -0.10)
        ),
        alerts_risk_warning_score_below=float(
            alerts.get("risk_warning_score_below", 35)
        ),
        alerts_etf_watch_nav_discount_gap=float(
            alerts.get("etf_watch_nav_discount_gap", 0.001)
        ),
        alerts_etf_action_nav_discount_gap=float(
            alerts.get("etf_action_nav_discount_gap", 0.005)
        ),
        alerts_etf_premium_warning_gap=float(
            alerts.get("etf_premium_warning_gap", -0.005)
        ),
        alerts_etf_minimum_opportunity_score=float(
            alerts.get("etf_minimum_opportunity_score", 65)
        ),
        alerts_etf_minimum_liquidity_score=float(
            alerts.get("etf_minimum_liquidity_score", 70)
        ),
        alerts_etf_minimum_risk_score=float(
            alerts.get("etf_minimum_risk_score", 50)
        ),
        alerts_etf_minimum_data_quality_score=float(
            alerts.get("etf_minimum_data_quality_score", 75)
        ),
        portfolio_model_version=portfolio.get(
            "model_version", "portfolio_context_mvp_v1"
        ),
        portfolio_base_currency=portfolio.get("base_currency", "USD"),
        portfolio_default_max_position_weight=float(
            portfolio.get("default_max_position_weight", 0.15)
        ),
        portfolio_default_starter_position_weight=float(
            portfolio.get("default_starter_position_weight", 0.03)
        ),
        portfolio_default_add_position_weight=float(
            portfolio.get("default_add_position_weight", 0.05)
        ),
        portfolio_cash_reserve_weight=float(portfolio.get("cash_reserve_weight", 0.05)),
        portfolio_max_sector_weight=float(portfolio.get("max_sector_weight", 0.35)),
        portfolio_stale_positions_after_days=int(
            portfolio.get("stale_positions_after_days", 14)
        ),
        signals_analyst_revision_model_version=signals.get(
            "analyst_revision_model_version", "analyst_revision_mvp_v1"
        ),
        signals_analyst_revision_shadow_mode=bool(
            signals.get("analyst_revision_shadow_mode", True)
        ),
        signals_news_catalyst_model_version=signals.get(
            "news_catalyst_model_version", "news_catalyst_mvp_v1"
        ),
        signals_news_catalyst_shadow_mode=bool(
            signals.get("news_catalyst_shadow_mode", True)
        ),
        signals_news_catalyst_stale_after_days=int(
            signals.get("news_catalyst_stale_after_days", 30)
        ),
        signals_news_catalyst_provider_order=_as_tuple(
            signals.get("news_catalyst_provider_order"),
            (
                "alpha_vantage",
                "marketaux",
                "eodhd",
                "finnhub",
                "fmp",
                "x_recent_search",
                "truth_social_public",
                "source_export",
            ),
        ),
        signals_news_catalyst_enabled_providers=_as_tuple(
            signals.get("news_catalyst_enabled_providers"),
            (
                "alpha_vantage",
                "marketaux",
                "eodhd",
                "finnhub",
                "fmp",
                "x_recent_search",
                "truth_social_public",
                "source_export",
            ),
        ),
        signals_news_catalyst_text_backfill_enabled=bool(
            signals.get("news_catalyst_text_backfill_enabled", True)
        ),
        signals_news_catalyst_text_backfill_model_version=signals.get(
            "news_catalyst_text_backfill_model_version",
            "news_text_lexicon_mvp_v1",
        ),
        signals_news_catalyst_min_numeric_coverage=int(
            signals.get("news_catalyst_min_numeric_coverage", 13)
        ),
        signals_news_catalyst_social_accounts=_as_tuple(
            signals.get("news_catalyst_social_accounts"),
            ("KobeissiLetter",),
        ),
        signals_news_catalyst_manual_influencer_sources=_as_tuple(
            signals.get("news_catalyst_manual_influencer_sources"),
            ("serenity", "kobeissi_letter"),
        ),
        signals_news_catalyst_source_policy=signals.get(
            "news_catalyst_source_policy", "weighted_median"
        ),
        signals_news_catalyst_lookback_days=int(
            signals.get("news_catalyst_lookback_days", 14)
        ),
        signals_news_catalyst_max_items_per_ticker=int(
            signals.get("news_catalyst_max_items_per_ticker", 5)
        ),
        signals_news_catalyst_disagreement_warning_threshold=float(
            signals.get("news_catalyst_disagreement_warning_threshold", 15.0)
        ),
        signals_news_catalyst_high_disagreement_threshold=float(
            signals.get("news_catalyst_high_disagreement_threshold", 30.0)
        ),
        signals_news_catalyst_min_sources_for_aggregate=int(
            signals.get("news_catalyst_min_sources_for_aggregate", 1)
        ),
        signals_news_catalyst_provider_request_budget=int(
            signals.get("news_catalyst_provider_request_budget", 3)
        ),
        signals_news_catalyst_provider_retry_delay_seconds=float(
            signals.get("news_catalyst_provider_retry_delay_seconds", 1.0)
        ),
        signals_news_catalyst_cache_stale_hours=int(
            signals.get("news_catalyst_cache_stale_hours", 24)
        ),
        signals_news_catalyst_use_cache=bool(
            signals.get("news_catalyst_use_cache", True)
        ),
        signals_insider_activity_model_version=signals.get(
            "insider_activity_model_version", "insider_activity_mvp_v1"
        ),
        signals_insider_activity_shadow_mode=bool(
            signals.get("insider_activity_shadow_mode", True)
        ),
        signals_insider_activity_lookback_days=int(
            signals.get("insider_activity_lookback_days", 180)
        ),
        signals_insider_activity_stale_after_days=int(
            signals.get("insider_activity_stale_after_days", 14)
        ),
        signals_insider_activity_fetch_limit_per_ticker=int(
            signals.get("insider_activity_fetch_limit_per_ticker", 40)
        ),
        signals_insider_activity_max_tickers_per_run=int(
            signals.get("insider_activity_max_tickers_per_run", 13)
        ),
        signals_insider_activity_use_cache=bool(
            signals.get("insider_activity_use_cache", True)
        ),
        signals_insider_activity_sec_request_delay_seconds=float(
            signals.get("insider_activity_sec_request_delay_seconds", 0.2)
        ),
        signals_insider_activity_sec_rate_limit_cooldown_seconds=float(
            signals.get("insider_activity_sec_rate_limit_cooldown_seconds", 60)
        ),
        signals_insider_activity_stop_on_rate_limit=bool(
            signals.get("insider_activity_stop_on_rate_limit", True)
        ),
        signals_insider_activity_max_live_form4_fetches_per_ticker=int(
            signals.get("insider_activity_max_live_form4_fetches_per_ticker", 10)
        ),
        signals_insider_activity_skip_successful_fetch_same_day=bool(
            signals.get("insider_activity_skip_successful_fetch_same_day", True)
        ),
        signals_insider_activity_min_transaction_value=float(
            signals.get("insider_activity_min_transaction_value", 10000)
        ),
        signals_short_interest_model_version=signals.get(
            "short_interest_model_version", "short_interest_mvp_v1"
        ),
        signals_short_interest_shadow_mode=bool(
            signals.get("short_interest_shadow_mode", True)
        ),
        signals_short_interest_stale_after_days=int(
            signals.get("short_interest_stale_after_days", 45)
        ),
        signals_short_interest_provider_order=_as_tuple(
            signals.get("short_interest_provider_order"),
            (
                "finra",
                "nasdaq_trader",
                "provider_export",
                "exchange_manual",
                "broker_manual",
            ),
        ),
        signals_short_interest_provider_timeout_seconds=int(
            signals.get("short_interest_provider_timeout_seconds", 12)
        ),
        signals_short_interest_provider_retry_delay_seconds=float(
            signals.get("short_interest_provider_retry_delay_seconds", 1.0)
        ),
        signals_short_interest_provider_cache_stale_hours=int(
            signals.get("short_interest_provider_cache_stale_hours", 24)
        ),
        signals_short_interest_provider_max_tickers_per_run=int(
            signals.get("short_interest_provider_max_tickers_per_run", 13)
        ),
        signals_short_interest_provider_use_cache=bool(
            signals.get("short_interest_provider_use_cache", True)
        ),
        options_model_version=options.get("model_version", "options_sell_put_mvp_v1"),
        options_default_min_dte=int(options.get("default_min_dte", 7)),
        options_default_max_dte=int(options.get("default_max_dte", 60)),
        options_min_annualized_premium_yield=float(
            options.get("min_annualized_premium_yield", 0.10)
        ),
        options_min_open_interest=int(options.get("min_open_interest", 100)),
        options_min_volume=int(options.get("min_volume", 10)),
        options_assignment_buffer_pct=float(options.get("assignment_buffer_pct", 0.10)),
        options_use_range_filter=bool(options.get("use_range_filter", True)),
        options_chain_source=options.get("chain_source", "auto"),
        options_option_fetch_universe=options.get(
            "option_fetch_universe",
            "scoreable_plus_commentary_options",
        ),
        options_ibkr_exchange=options.get("ibkr_exchange", "SMART"),
        options_ibkr_currency=options.get("ibkr_currency", "USD"),
        options_chain_stale_after_minutes=int(
            options.get("chain_stale_after_minutes", 30)
        ),
        options_max_expirations_per_ticker=int(
            options.get("max_expirations_per_ticker", 4)
        ),
        options_max_strikes_per_expiration=int(
            options.get("max_strikes_per_expiration", 12)
        ),
        options_strike_window_pct=float(options.get("strike_window_pct", 0.30)),
        options_fetch_puts_only=bool(options.get("fetch_puts_only", True)),
        options_auto_fetch_daily=bool(options.get("auto_fetch_daily", True)),
        options_auto_fetch_intraday=bool(options.get("auto_fetch_intraday", False)),
        options_max_tickers_per_run=int(options.get("max_tickers_per_run", 3)),
        options_risk_model_version=options.get(
            "risk_model_version",
            "options_risk_margin_mvp_v1",
        ),
        options_risk_margin_model=options.get(
            "risk_margin_model",
            "cash_secured_proxy",
        ),
        options_max_single_contract_notional_weight=float(
            options.get("max_single_contract_notional_weight", 0.05)
        ),
        options_max_total_assignment_notional_weight=float(
            options.get("max_total_assignment_notional_weight", 0.20)
        ),
        options_minimum_cash_reserve_after_assignment=float(
            options.get("minimum_cash_reserve_after_assignment", 0.05)
        ),
        options_downside_scenario_pcts=tuple(
            float(value)
            for value in options.get("downside_scenario_pcts", (-0.05, -0.10, -0.20))
        ),
        options_reference_instrument_risk_warning=bool(
            options.get("reference_instrument_risk_warning", True)
        ),
        options_outcome_model_version=options.get(
            "outcome_model_version",
            "options_outcome_mvp_v1",
        ),
        options_position_model_version=options.get(
            "position_model_version",
            "options_position_ledger_mvp_v1",
        ),
        options_lifecycle_model_version=options.get(
            "lifecycle_model_version",
            "options_lifecycle_mvp_v1",
        ),
        options_realized_pl_model_version=options.get(
            "realized_pl_model_version",
            "options_realized_pl_mvp_v1",
        ),
        options_option_multiplier=int(options.get("option_multiplier", 100)),
        options_position_stale_after_days=int(options.get("position_stale_after_days", 7)),
        options_assignment_tracking_enabled=bool(
            options.get("assignment_tracking_enabled", True)
        ),
        options_outcome_horizons=_as_tuple(
            options.get("outcome_horizons"),
            ("5d", "20d", "expiration"),
        ),
        options_outcome_use_underlying_prices_only=bool(
            options.get("outcome_use_underlying_prices_only", True)
        ),
        signals_trader_commentary_model_version=signals.get(
            "trader_commentary_model_version", "trader_commentary_mvp_v1"
        ),
        signals_trader_commentary_shadow_mode=bool(
            signals.get("trader_commentary_shadow_mode", True)
        ),
        signals_trader_commentary_default_horizons=_as_tuple(
            signals.get("trader_commentary_default_horizons"),
            ("1d", "5d", "20d", "60d"),
        ),
        signals_trader_commentary_stale_after_days=int(
            signals.get("trader_commentary_stale_after_days", 30)
        ),
        commentary_browser_capture_enabled=bool(
            commentary_browser_capture.get("enabled", False)
        ),
        commentary_browser_capture_provider=commentary_browser_capture.get(
            "provider", "x_browser"
        ),
        commentary_browser_capture_target_urls=_as_tuple(
            commentary_browser_capture.get("target_urls"),
            (),
        ),
        commentary_browser_capture_max_scroll_batches=int(
            commentary_browser_capture.get("max_scroll_batches", 3)
        ),
        commentary_browser_capture_min_seconds_between_runs=int(
            commentary_browser_capture.get("min_seconds_between_runs", 900)
        ),
        commentary_browser_capture_require_operator_acknowledgement=bool(
            commentary_browser_capture.get("require_operator_acknowledgement", True)
        ),
        commentary_discord_capture_enabled=bool(
            commentary_discord_capture.get("enabled", False)
        ),
        commentary_discord_capture_provider=commentary_discord_capture.get(
            "provider", "discord_gateway"
        ),
        commentary_discord_capture_channel_ids=_as_tuple(
            commentary_discord_capture.get("channel_ids"),
            (),
        ),
        commentary_discord_capture_max_messages_per_run=int(
            commentary_discord_capture.get("max_messages_per_run", 100)
        ),
        commentary_discord_capture_min_seconds_between_runs=int(
            commentary_discord_capture.get("min_seconds_between_runs", 900)
        ),
        commentary_discord_capture_require_operator_acknowledgement=bool(
            commentary_discord_capture.get("require_operator_acknowledgement", True)
        ),
        signals_minimum_revision_inputs=int(signals.get("minimum_revision_inputs", 1)),
        signals_stale_after_days=int(signals.get("stale_after_days", 45)),
        signals_revision_evidence_min_source_tickers=int(
            signals.get("revision_evidence_min_source_tickers", 3)
        ),
        signals_revision_evidence_min_signal_tickers=int(
            signals.get("revision_evidence_min_signal_tickers", 3)
        ),
        signals_revision_evidence_min_completed_20d=int(
            signals.get("revision_evidence_min_completed_20d", 3)
        ),
        signals_revision_evidence_min_hit_rate_20d=float(
            signals.get("revision_evidence_min_hit_rate_20d", 0.55)
        ),
        signals_revision_evidence_min_avg_return_20d=float(
            signals.get("revision_evidence_min_avg_return_20d", 0.0)
        ),
        signals_revision_evidence_min_confidence=float(
            signals.get("revision_evidence_min_confidence", 60)
        ),
        signals_revision_provider_order=_as_tuple(
            signals.get("revision_provider_order"),
            (
                "alpha_vantage",
                "fmp",
                "business_quant",
                "finnhub",
                "yfinance",
                "ibkr",
                "source_export",
            ),
        ),
        signals_revision_enabled_providers=_as_tuple(
            signals.get("revision_enabled_providers"),
            ("alpha_vantage", "fmp", "business_quant", "finnhub", "yfinance", "source_export"),
        ),
        signals_revision_source_policy=signals.get(
            "revision_source_policy", "weighted_median"
        ),
        signals_revision_disagreement_warning_threshold=float(
            signals.get("revision_disagreement_warning_threshold", 0.05)
        ),
        signals_revision_high_disagreement_threshold=float(
            signals.get("revision_high_disagreement_threshold", 0.10)
        ),
        signals_revision_min_sources_for_aggregate=int(
            signals.get("revision_min_sources_for_aggregate", 1)
        ),
        realtime_source=realtime.get("source", "ibkr"),
        realtime_quote_stale_after_seconds=int(
            realtime.get("quote_stale_after_seconds", 900)
        ),
        realtime_range_model_version=realtime.get(
            "range_model_version", "range_monitor_mvp_v1"
        ),
        realtime_notification_cooldown_minutes=int(
            realtime.get("notification_cooldown_minutes", 60)
        ),
        realtime_monitor_active_assets_only=bool(
            realtime.get("monitor_active_assets_only", True)
        ),
        realtime_intraday_cycle_stale_after_seconds=int(
            realtime.get("intraday_cycle_stale_after_seconds", 1800)
        ),
        realtime_notification_pending_stale_after_seconds=int(
            realtime.get("notification_pending_stale_after_seconds", 1800)
        ),
        realtime_manual_ops_loop_interval_seconds=int(
            realtime.get("manual_ops_loop_interval_seconds", 600)
        ),
        research_preparation_auto_enabled=bool(
            research_preparation.get("auto_enabled", True)
        ),
        research_preparation_auto_source=str(
            research_preparation.get("auto_source", "all")
        ),
        research_preparation_auto_min_seconds_between_runs=int(
            research_preparation.get("auto_min_seconds_between_runs", 21600)
        ),
        api_host=api.get("host", "127.0.0.1"),
        api_port=int(api.get("port", 8765)),
        api_allowed_origins=_as_tuple(
            api.get("allowed_origins"),
            ("http://127.0.0.1:5173", "http://localhost:5173"),
        ),
        api_require_mutation_confirmation=bool(
            api.get("require_mutation_confirmation", True)
        ),
        technical_model_version=technical.get(
            "model_version", "technical_levels_mvp_v1"
        ),
        technical_lookback_days=int(technical.get("lookback_days", 252)),
        technical_minimum_history_days=int(
            technical.get("minimum_history_days", 120)
        ),
        technical_short_ma_days=int(technical.get("short_ma_days", 20)),
        technical_medium_ma_days=int(technical.get("medium_ma_days", 50)),
        technical_long_ma_days=int(technical.get("long_ma_days", 200)),
        technical_pivot_window_days=int(technical.get("pivot_window_days", 5)),
        technical_near_level_pct=float(technical.get("near_level_pct", 0.02)),
        technical_breakout_buffer_pct=float(
            technical.get("breakout_buffer_pct", 0.01)
        ),
        regime_model_version=regime.get("model_version", "market_regime_mvp_v1"),
        regime_benchmark_tickers=_as_tuple(
            regime.get("benchmark_tickers"),
            ("SPY", "QQQ"),
        ),
        regime_sector_proxy_tickers=_as_tuple(
            regime.get("sector_proxy_tickers"),
            (
                "XLK",
                "XLY",
                "XLV",
                "XLF",
                "XLI",
                "XLP",
                "XLU",
                "XLE",
                "XLC",
                "XLB",
                "XLRE",
            ),
        ),
        regime_relative_strength_lookback_days=int(
            regime.get("relative_strength_lookback_days", 63)
        ),
        fundamental_benchmark_model_version=fundamental_benchmarks.get(
            "model_version",
            "fundamental_benchmark_mvp_v1",
        ),
        fundamental_benchmark_min_sector_peer_count=int(
            fundamental_benchmarks.get("minimum_sector_peer_count", 3)
        ),
        fundamental_benchmark_min_industry_peer_count=int(
            fundamental_benchmarks.get("minimum_industry_peer_count", 2)
        ),
        universe_mode=run.get("universe_mode", "manual_watchlist"),
        run_mode=run.get("run_mode", "daily_scoring"),
        report_title=reports.get("title", "Target Opportunity Monitor Daily Report"),
    )
