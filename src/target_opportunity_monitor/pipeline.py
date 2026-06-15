from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Callable

from .alerts import compute_alerts
from .browser_commentary import ingest_browser_captured_commentary
from .commentary_onboarding import load_commentary_instrument_aliases
from .config import AppConfig
from .dashboard import build_dashboard
from .discord_commentary import ingest_discord_captured_commentary
from .etf_data import ensure_etf_csv_headers, load_etf_holdings_csv, load_etf_navs_csv
from .fundamental_data import load_estimates_csv
from .fundamental_benchmarks import compute_fundamental_benchmarks
from .ibkr_provider import update_etf_navs_from_ibkr, update_quote_snapshots
from .insider_activity import compute_insider_signals, fetch_insider_transactions
from .intraday import compute_intraday_gaps
from .market_data import update_prices
from .missing_tickers import SOURCE_ACCOUNT_CONTEXT, run_missing_ticker_automation
from .news_catalysts import compute_news_catalyst_signals, load_news_catalysts_csv
from .news_catalyst_sources import (
    aggregate_news_catalyst_sources,
    compute_news_catalyst_text_backfill,
    fetch_news_catalyst_sources,
    import_news_catalyst_source_exports,
)
from .notifications import deliver_notifications
from .outcomes import update_alert_outcomes
from .options import (
    compute_options_income,
    compute_options_lifecycle,
    compute_options_outcomes,
    compute_options_risk,
    fetch_options_chain,
    load_options_chain_csv,
    load_options_positions_csv,
)
from .portfolio import load_portfolio_csvs, compute_portfolio_context
from .ranges import compute_range_snapshots
from .readiness import verify_universe
from .reporting import write_daily_report
from .revision_sources import (
    aggregate_revision_sources,
    fetch_revision_sources,
    import_revision_source_exports,
)
from .scoring import compute_scores
from .sec_fundamentals import seed_sec_fundamentals
from .signal_validation import (
    validate_insider_signals,
    validate_news_catalyst_signals,
    validate_revision_signals,
    validate_short_interest_signals,
)
from .signals import compute_revision_signals, load_analyst_revisions_csv
from .technical import compute_regime_signals, compute_technical_signals
from .trader_commentary import (
    load_trader_commentary_csv,
    parse_trader_commentary_claims,
    validate_trader_commentary_claims,
)
from .short_interest import (
    compute_short_interest_signals,
    fetch_short_interest_sources,
    import_short_interest_source_exports,
    load_short_interest_csv,
)
from .storage import (
    QuoteSnapshot,
    finish_pipeline_run,
    insert_pipeline_step_result,
    latest_price_feature,
    list_assets,
    normalize_ticker,
    start_pipeline_run,
    upsert_quote_snapshot,
)
from .valuation import compute_targets
from .watchlist import load_watchlist


@dataclass(frozen=True)
class PipelineStepSummary:
    step_name: str
    status: str
    rows_loaded: int
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class PipelineExecutionResult:
    pipeline_run_id: int
    run_type: str
    status: str
    steps: tuple[PipelineStepSummary, ...]
    summary: str


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _run_step(
    config: AppConfig,
    pipeline_run_id: int,
    step_name: str,
    action: Callable[[], tuple[int, tuple[str, ...]]],
    required: bool,
) -> PipelineStepSummary:
    started_at = _now_iso()
    try:
        rows_loaded, warnings = action()
        status = "warning" if warnings else "ok"
    except Exception as error:
        rows_loaded = 0
        warnings = (str(error),)
        status = "error" if required else "warning"
    finished_at = _now_iso()
    insert_pipeline_step_result(
        config.database_path,
        pipeline_run_id=pipeline_run_id,
        step_name=step_name,
        status=status,
        rows_loaded=rows_loaded,
        warnings=", ".join(warnings) if warnings else None,
        source="pipeline",
        started_at=started_at,
        finished_at=finished_at,
    )
    return PipelineStepSummary(
        step_name=step_name,
        status=status,
        rows_loaded=rows_loaded,
        warnings=warnings,
    )


def run_refresh_data(
    config: AppConfig,
    ticker: str | None = None,
    daily: bool = True,
    include_quotes: bool = False,
    skip_ibkr: bool = False,
) -> PipelineExecutionResult:
    run_type = "daily_refresh" if daily else "refresh"
    pipeline_run_id = start_pipeline_run(config.database_path, run_type, source="pipeline")
    steps: list[PipelineStepSummary] = []

    steps.append(
        _run_step(
            config,
            pipeline_run_id,
            "load-watchlist",
            lambda: (load_watchlist(config.database_path, config.watchlist_path).loaded_count, ()),
            required=True,
        )
    )
    steps.append(
        _run_step(
            config,
            pipeline_run_id,
            "update-prices",
            lambda: _price_step(config, ticker),
            required=True,
        )
    )
    steps.append(
        _run_step(
            config,
            pipeline_run_id,
            "seed-fundamentals",
            lambda: _fundamental_seed_step(config, ticker),
            required=False,
        )
    )
    steps.append(
        _run_step(
            config,
            pipeline_run_id,
            "load-estimates",
            lambda: (load_estimates_csv(config.database_path, config.estimates_path).loaded_count, ()),
            required=False,
        )
    )
    steps.append(
        _run_step(
            config,
            pipeline_run_id,
            "fetch-revision-sources",
            lambda: _revision_provider_fetch_step(config, ticker),
            required=False,
        )
    )
    steps.append(
        _run_step(
            config,
            pipeline_run_id,
            "import-revision-source-exports",
            lambda: _revision_source_import_step(config),
            required=False,
        )
    )
    steps.append(
        _run_step(
            config,
            pipeline_run_id,
            "aggregate-revision-sources",
            lambda: _revision_aggregation_step(config, ticker),
            required=False,
        )
    )
    steps.append(
        _run_step(
            config,
            pipeline_run_id,
            "load-analyst-revisions",
            lambda: _analyst_revision_load_step(config),
            required=False,
        )
    )
    steps.append(
        _run_step(
            config,
            pipeline_run_id,
            "compute-revision-signals",
            lambda: _revision_signal_step(config, ticker),
            required=False,
        )
    )
    steps.append(
        _run_step(
            config,
            pipeline_run_id,
            "validate-revision-signals",
            lambda: _revision_validation_step(config, ticker),
            required=False,
        )
    )
    steps.append(
        _run_step(
            config,
            pipeline_run_id,
            "fetch-news-catalyst-sources",
            lambda: _news_catalyst_provider_fetch_step(config, ticker),
            required=False,
        )
    )
    steps.append(
        _run_step(
            config,
            pipeline_run_id,
            "import-news-catalyst-source-exports",
            lambda: _news_catalyst_source_import_step(config),
            required=False,
        )
    )
    steps.append(
        _run_step(
            config,
            pipeline_run_id,
            "compute-news-catalyst-text-backfill",
            lambda: _news_catalyst_text_backfill_step(config, ticker),
            required=False,
        )
    )
    steps.append(
        _run_step(
            config,
            pipeline_run_id,
            "aggregate-news-catalyst-sources",
            lambda: _news_catalyst_aggregation_step(config, ticker),
            required=False,
        )
    )
    steps.append(
        _run_step(
            config,
            pipeline_run_id,
            "load-news-catalysts",
            lambda: _news_catalyst_load_step(config),
            required=False,
        )
    )
    steps.append(
        _run_step(
            config,
            pipeline_run_id,
            "compute-news-catalyst-signals",
            lambda: _news_catalyst_signal_step(config, ticker),
            required=False,
        )
    )
    steps.append(
        _run_step(
            config,
            pipeline_run_id,
            "validate-news-catalyst-signals",
            lambda: _news_catalyst_validation_step(config, ticker),
            required=False,
        )
    )
    steps.append(
        _run_step(
            config,
            pipeline_run_id,
            "ingest-browser-captured-commentary",
            lambda: _browser_captured_commentary_ingest_step(config),
            required=False,
        )
    )
    steps.append(
        _run_step(
            config,
            pipeline_run_id,
            "ingest-discord-captured-commentary",
            lambda: _discord_captured_commentary_ingest_step(config),
            required=False,
        )
    )
    steps.append(
        _run_step(
            config,
            pipeline_run_id,
            "load-trader-commentary",
            lambda: _trader_commentary_load_step(config),
            required=False,
        )
    )
    steps.append(
        _run_step(
            config,
            pipeline_run_id,
            "load-commentary-instrument-aliases",
            lambda: _trader_commentary_alias_step(config),
            required=False,
        )
    )
    steps.append(
        _run_step(
            config,
            pipeline_run_id,
            "parse-trader-commentary-claims",
            lambda: _trader_commentary_parse_step(config, ticker),
            required=False,
        )
    )
    steps.append(
        _run_step(
            config,
            pipeline_run_id,
            "validate-trader-commentary-claims",
            lambda: _trader_commentary_validation_step(config, ticker),
            required=False,
        )
    )
    steps.append(
        _run_step(
            config,
            pipeline_run_id,
            "fetch-insider-transactions",
            lambda: _insider_fetch_step(config, ticker),
            required=False,
        )
    )
    steps.append(
        _run_step(
            config,
            pipeline_run_id,
            "compute-insider-signals",
            lambda: _insider_signal_step(config, ticker),
            required=False,
        )
    )
    steps.append(
        _run_step(
            config,
            pipeline_run_id,
            "validate-insider-signals",
            lambda: _insider_validation_step(config, ticker),
            required=False,
        )
    )
    steps.append(
        _run_step(
            config,
            pipeline_run_id,
            "fetch-short-interest-sources",
            lambda: _short_interest_provider_fetch_step(config, ticker),
            required=False,
        )
    )
    steps.append(
        _run_step(
            config,
            pipeline_run_id,
            "import-short-interest-source-exports",
            lambda: _short_interest_source_import_step(config),
            required=False,
        )
    )
    steps.append(
        _run_step(
            config,
            pipeline_run_id,
            "load-short-interest",
            lambda: _short_interest_load_step(config),
            required=False,
        )
    )
    steps.append(
        _run_step(
            config,
            pipeline_run_id,
            "compute-short-interest-signals",
            lambda: _short_interest_signal_step(config, ticker),
            required=False,
        )
    )
    steps.append(
        _run_step(
            config,
            pipeline_run_id,
            "validate-short-interest-signals",
            lambda: _short_interest_validation_step(config, ticker),
            required=False,
        )
    )
    steps.append(
        _run_step(
            config,
            pipeline_run_id,
            "fetch-options-chain",
            lambda: _options_chain_fetch_step(config, ticker),
            required=False,
        )
    )
    steps.append(
        _run_step(
            config,
            pipeline_run_id,
            "load-options-chain",
            lambda: _options_chain_load_step(config),
            required=False,
        )
    )
    steps.append(
        _run_step(
            config,
            pipeline_run_id,
            "compute-options-income",
            lambda: _options_income_step(config, ticker),
            required=False,
        )
    )
    steps.append(
        _run_step(
            config,
            pipeline_run_id,
            "compute-options-risk",
            lambda: _options_risk_step(config, ticker),
            required=False,
        )
    )
    steps.append(
        _run_step(
            config,
            pipeline_run_id,
            "load-options-positions",
            lambda: _options_position_load_step(config),
            required=False,
        )
    )
    steps.append(
        _run_step(
            config,
            pipeline_run_id,
            "compute-options-outcomes",
            lambda: _options_outcome_step(config, ticker),
            required=False,
        )
    )
    steps.append(
        _run_step(
            config,
            pipeline_run_id,
            "compute-options-lifecycle",
            lambda: _options_lifecycle_step(config, ticker),
            required=False,
        )
    )
    steps.append(
        _run_step(
            config,
            pipeline_run_id,
            "load-etf-navs",
            lambda: _etf_nav_csv_step(config),
            required=False,
        )
    )
    steps.append(
        _run_step(
            config,
            pipeline_run_id,
            "load-etf-holdings",
            lambda: _etf_holdings_step(config),
            required=False,
        )
    )
    if include_quotes and not skip_ibkr:
        steps.append(
            _run_step(
                config,
                pipeline_run_id,
                "update-quotes",
                lambda: _quote_step(config, ticker),
                required=False,
            )
        )
        steps.append(
            _run_step(
                config,
                pipeline_run_id,
                "update-etf-navs-ibkr",
                lambda: _ibkr_etf_nav_step(config, ticker),
                required=False,
            )
        )
    steps.append(
        _run_step(
            config,
            pipeline_run_id,
            "compute-targets",
            lambda: _target_step(config, ticker),
            required=True,
        )
    )
    steps.append(
        _run_step(
            config,
            pipeline_run_id,
            "compute-scores",
            lambda: _score_step(config, ticker),
            required=True,
        )
    )
    steps.append(
        _run_step(
            config,
            pipeline_run_id,
            "compute-fundamental-benchmarks",
            lambda: _fundamental_benchmark_step(config),
            required=False,
        )
    )
    steps.append(
        _run_step(
            config,
            pipeline_run_id,
            "compute-alerts",
            lambda: _alert_step(config, ticker),
            required=True,
        )
    )
    steps.append(
        _run_step(
            config,
            pipeline_run_id,
            "update-alert-outcomes",
            lambda: _outcome_step(config, ticker),
            required=False,
        )
    )
    steps.append(
        _run_step(
            config,
            pipeline_run_id,
            "resolve-missing-tickers",
            lambda: _missing_ticker_resolver_step(config),
            required=False,
        )
    )
    steps.append(
        _run_step(
            config,
            pipeline_run_id,
            "load-portfolio",
            lambda: _portfolio_load_step(config),
            required=False,
        )
    )
    steps.append(
        _run_step(
            config,
            pipeline_run_id,
            "compute-portfolio-context",
            lambda: _portfolio_context_step(config, ticker),
            required=False,
        )
    )
    steps.append(
        _run_step(
            config,
            pipeline_run_id,
            "compute-technical-signals",
            lambda: _technical_step(config, ticker),
            required=False,
        )
    )
    steps.append(
        _run_step(
            config,
            pipeline_run_id,
            "compute-regime-signals",
            lambda: _regime_step(config),
            required=False,
        )
    )
    steps.append(
        _run_step(
            config,
            pipeline_run_id,
            "range-monitor",
            lambda: _range_step(config, ticker),
            required=False,
        )
    )
    steps.append(
        _run_step(
            config,
            pipeline_run_id,
            "verify-universe",
            lambda: _readiness_step(config, ticker),
            required=True,
        )
    )
    steps.append(
        _run_step(
            config,
            pipeline_run_id,
            "run-daily",
            lambda: (1 if write_daily_report(config).path.exists() else 0, ()),
            required=True,
        )
    )
    steps.append(
        _run_step(
            config,
            pipeline_run_id,
            "build-dashboard",
            lambda: _dashboard_step(config),
            required=True,
        )
    )

    status = "error" if any(step.status == "error" for step in steps) else "ok"
    warning_count = sum(1 for step in steps if step.status == "warning")
    summary = (
        f"{run_type}: status={status}, steps={len(steps)}, "
        f"warnings={warning_count}, ticker={ticker or 'all'}"
    )
    finish_pipeline_run(config.database_path, pipeline_run_id, status, summary)
    return PipelineExecutionResult(
        pipeline_run_id=pipeline_run_id,
        run_type=run_type,
        status=status,
        steps=tuple(steps),
        summary=summary,
    )


def run_probe_market(
    config: AppConfig,
    source: str = "ibkr",
    ticker: str | None = None,
) -> PipelineExecutionResult:
    if source != "ibkr":
        raise ValueError(f"Unsupported probe source: {source}")

    pipeline_run_id = start_pipeline_run(
        config.database_path,
        "intraday_probe",
        source="pipeline",
    )
    steps: list[PipelineStepSummary] = []
    steps.append(
        _run_step(
            config,
            pipeline_run_id,
            "update-quotes",
            lambda: _quote_step(config, ticker),
            required=False,
        )
    )
    steps.append(
        _run_step(
            config,
            pipeline_run_id,
            "update-etf-navs-ibkr",
            lambda: _ibkr_etf_nav_step(config, ticker),
            required=False,
        )
    )
    steps.append(
        _run_step(
            config,
            pipeline_run_id,
            "compute-live-gaps",
            lambda: _gap_step(config, ticker),
            required=True,
        )
    )
    steps.append(
        _run_step(
            config,
            pipeline_run_id,
            "range-monitor",
            lambda: _range_step(config, ticker),
            required=True,
        )
    )
    steps.append(
        _run_step(
            config,
            pipeline_run_id,
            "verify-universe-intraday",
            lambda: _readiness_step(config, ticker, intraday=True),
            required=False,
        )
    )
    status = "error" if any(step.status == "error" for step in steps) else "ok"
    warning_count = sum(1 for step in steps if step.status == "warning")
    summary = (
        f"intraday_probe: status={status}, steps={len(steps)}, "
        f"warnings={warning_count}, ticker={ticker or 'all'}"
    )
    finish_pipeline_run(config.database_path, pipeline_run_id, status, summary)
    return PipelineExecutionResult(
        pipeline_run_id=pipeline_run_id,
        run_type="intraday_probe",
        status=status,
        steps=tuple(steps),
        summary=summary,
    )


def run_intraday_cycle(
    config: AppConfig,
    source: str = "ibkr",
    ticker: str | None = None,
    deliver: bool = False,
    channel: str = "console",
    include_options: bool = False,
    drain_first: bool = False,
) -> PipelineExecutionResult:
    if source not in {"ibkr", "auto"}:
        raise ValueError(f"Unsupported intraday source: {source}")

    pipeline_run_id = start_pipeline_run(
        config.database_path,
        "intraday_cycle",
        source="pipeline",
    )
    steps: list[PipelineStepSummary] = []
    if drain_first and deliver:
        steps.append(
            _run_step(
                config,
                pipeline_run_id,
                f"drain-pending-notifications-{channel}",
                lambda: _delivery_step(config, channel),
                required=False,
            )
        )
    steps.append(
        _run_step(
            config,
            pipeline_run_id,
            "update-quotes",
            lambda: _quote_step(config, ticker, source=source),
            required=False,
        )
    )
    steps.append(
        _run_step(
            config,
            pipeline_run_id,
            "compute-live-gaps",
            lambda: _gap_step(config, ticker),
            required=False,
        )
    )
    steps.append(
        _run_step(
            config,
            pipeline_run_id,
            "range-monitor",
            lambda: _range_step(config, ticker),
            required=False,
        )
    )
    if include_options:
        steps.append(
            _run_step(
                config,
                pipeline_run_id,
                "fetch-options-chain",
                lambda: _options_chain_fetch_step(config, ticker),
                required=False,
            )
        )
        steps.append(
            _run_step(
                config,
                pipeline_run_id,
                "compute-options-income",
                lambda: _options_income_step(config, ticker),
                required=False,
            )
        )
        steps.append(
            _run_step(
                config,
                pipeline_run_id,
                "compute-options-risk",
                lambda: _options_risk_step(config, ticker),
                required=False,
            )
        )
        steps.append(
            _run_step(
                config,
                pipeline_run_id,
                "load-options-positions",
                lambda: _options_position_load_step(config),
                required=False,
            )
        )
        steps.append(
            _run_step(
                config,
                pipeline_run_id,
                "compute-options-outcomes",
                lambda: _options_outcome_step(config, ticker),
                required=False,
            )
        )
        steps.append(
            _run_step(
                config,
                pipeline_run_id,
                "compute-options-lifecycle",
                lambda: _options_lifecycle_step(config, ticker),
                required=False,
            )
        )
    if deliver:
        steps.append(
            _run_step(
                config,
                pipeline_run_id,
                f"deliver-notifications-{channel}",
                lambda: _delivery_step(config, channel),
                required=False,
            )
        )

    status = "error" if any(step.status == "error" for step in steps) else "ok"
    warning_count = sum(1 for step in steps if step.status == "warning")
    summary = (
        f"intraday_cycle: status={status}, steps={len(steps)}, "
        f"warnings={warning_count}, ticker={ticker or 'all'}, "
        f"deliver={deliver}, channel={channel if deliver else 'none'}, "
        f"include_options={include_options}, drain_first={drain_first and deliver}"
    )
    finish_pipeline_run(config.database_path, pipeline_run_id, status, summary)
    return PipelineExecutionResult(
        pipeline_run_id=pipeline_run_id,
        run_type="intraday_cycle",
        status=status,
        steps=tuple(steps),
        summary=summary,
    )


def _price_step(config: AppConfig, ticker: str | None) -> tuple[int, tuple[str, ...]]:
    result = update_prices(config, ticker=ticker)
    warnings = tuple(
        f"{item.ticker}:{','.join(item.warnings)}"
        for item in result.results
        if item.warnings
    )
    return result.loaded_count, warnings


def _fundamental_seed_step(
    config: AppConfig,
    ticker: str | None,
) -> tuple[int, tuple[str, ...]]:
    result = seed_sec_fundamentals(config, ticker=ticker)
    return result.loaded_count, result.skipped


def _etf_nav_csv_step(config: AppConfig) -> tuple[int, tuple[str, ...]]:
    ensure_etf_csv_headers(config.etf_navs_path, config.etf_holdings_path)
    result = load_etf_navs_csv(config.database_path, config.etf_navs_path)
    return result.loaded_count, ()


def _etf_holdings_step(config: AppConfig) -> tuple[int, tuple[str, ...]]:
    ensure_etf_csv_headers(config.etf_navs_path, config.etf_holdings_path)
    result = load_etf_holdings_csv(config.database_path, config.etf_holdings_path)
    return result.loaded_count, ()


def _revision_provider_fetch_step(
    config: AppConfig,
    ticker: str | None,
) -> tuple[int, tuple[str, ...]]:
    result = fetch_revision_sources(config, provider="all", ticker=ticker)
    return result.stored_count, result.warnings


def _revision_source_import_step(config: AppConfig) -> tuple[int, tuple[str, ...]]:
    result = import_revision_source_exports(config)
    return result.imported_count, result.warnings


def _revision_aggregation_step(
    config: AppConfig,
    ticker: str | None,
) -> tuple[int, tuple[str, ...]]:
    result = aggregate_revision_sources(config, ticker=ticker)
    return result.aggregate_count, result.warnings


def _analyst_revision_load_step(config: AppConfig) -> tuple[int, tuple[str, ...]]:
    result = load_analyst_revisions_csv(config)
    return result.input_signal_count, result.warnings


def _revision_signal_step(
    config: AppConfig,
    ticker: str | None,
) -> tuple[int, tuple[str, ...]]:
    result = compute_revision_signals(config, ticker=ticker)
    warnings = tuple(
        f"{item.ticker}:{','.join(item.warnings)}"
        for item in result.results
        if item.warnings
    )
    return result.computed_count, warnings


def _revision_validation_step(
    config: AppConfig,
    ticker: str | None,
) -> tuple[int, tuple[str, ...]]:
    result = validate_revision_signals(config, ticker=ticker)
    warnings = tuple(
        f"{item.ticker}:{','.join(item.warnings)}"
        for item in result.results
        if item.warnings
    )
    return result.updated_count, warnings


def _news_catalyst_provider_fetch_step(
    config: AppConfig,
    ticker: str | None,
) -> tuple[int, tuple[str, ...]]:
    result = fetch_news_catalyst_sources(
        config,
        provider="all",
        ticker=ticker,
        coverage_plan=ticker is None,
    )
    return result.stored_count, result.warnings


def _news_catalyst_source_import_step(config: AppConfig) -> tuple[int, tuple[str, ...]]:
    result = import_news_catalyst_source_exports(config)
    return result.imported_count, result.warnings


def _news_catalyst_text_backfill_step(
    config: AppConfig,
    ticker: str | None,
) -> tuple[int, tuple[str, ...]]:
    result = compute_news_catalyst_text_backfill(config, ticker=ticker)
    return result.derived_count, result.warnings


def _news_catalyst_aggregation_step(
    config: AppConfig,
    ticker: str | None,
) -> tuple[int, tuple[str, ...]]:
    result = aggregate_news_catalyst_sources(config, ticker=ticker)
    return result.aggregate_count, result.warnings


def _news_catalyst_load_step(config: AppConfig) -> tuple[int, tuple[str, ...]]:
    result = load_news_catalysts_csv(config)
    return result.input_signal_count, result.warnings


def _news_catalyst_signal_step(
    config: AppConfig,
    ticker: str | None,
) -> tuple[int, tuple[str, ...]]:
    result = compute_news_catalyst_signals(config, ticker=ticker)
    warnings = tuple(
        f"{item.ticker}:{','.join(item.warnings)}"
        for item in result.results
        if item.warnings
    )
    return result.computed_count, warnings


def _news_catalyst_validation_step(
    config: AppConfig,
    ticker: str | None,
) -> tuple[int, tuple[str, ...]]:
    result = validate_news_catalyst_signals(config, ticker=ticker)
    warnings = tuple(
        f"{item.ticker}:{','.join(item.warnings)}"
        for item in result.results
        if item.warnings
    )
    return result.updated_count, warnings


def _trader_commentary_load_step(config: AppConfig) -> tuple[int, tuple[str, ...]]:
    result = load_trader_commentary_csv(config)
    return result.loaded_count, result.warnings


def _trader_commentary_alias_step(config: AppConfig) -> tuple[int, tuple[str, ...]]:
    result = load_commentary_instrument_aliases(config)
    return result.loaded_count, result.warnings


def _browser_captured_commentary_ingest_step(
    config: AppConfig,
) -> tuple[int, tuple[str, ...]]:
    result = ingest_browser_captured_commentary(config)
    return result.imported_count, result.warnings


def _discord_captured_commentary_ingest_step(
    config: AppConfig,
) -> tuple[int, tuple[str, ...]]:
    result = ingest_discord_captured_commentary(config)
    return result.imported_count, result.warnings


def _trader_commentary_parse_step(
    config: AppConfig,
    ticker: str | None,
) -> tuple[int, tuple[str, ...]]:
    result = parse_trader_commentary_claims(config, ticker=ticker)
    return result.parsed_count, result.warnings


def _trader_commentary_validation_step(
    config: AppConfig,
    ticker: str | None,
) -> tuple[int, tuple[str, ...]]:
    result = validate_trader_commentary_claims(config, ticker=ticker)
    warnings = tuple(
        f"{item.ticker or 'unmapped'}:{','.join(item.warnings)}"
        for item in result.results
        if item.warnings
    )
    return result.updated_count, warnings


def _insider_fetch_step(
    config: AppConfig,
    ticker: str | None,
) -> tuple[int, tuple[str, ...]]:
    result = fetch_insider_transactions(
        config,
        ticker=ticker,
        max_tickers=(
            None
            if ticker
            else config.signals_insider_activity_max_tickers_per_run
        ),
        use_cache=config.signals_insider_activity_use_cache,
    )
    return result.stored_count, result.warnings


def _insider_signal_step(
    config: AppConfig,
    ticker: str | None,
) -> tuple[int, tuple[str, ...]]:
    result = compute_insider_signals(config, ticker=ticker)
    warnings = tuple(
        f"{item.ticker}:{','.join(item.warnings)}"
        for item in result.results
        if item.warnings
    )
    return result.computed_count, warnings


def _insider_validation_step(
    config: AppConfig,
    ticker: str | None,
) -> tuple[int, tuple[str, ...]]:
    result = validate_insider_signals(config, ticker=ticker)
    warnings = tuple(
        f"{item.ticker}:{','.join(item.warnings)}"
        for item in result.results
        if item.warnings
    )
    return result.updated_count, warnings


def _short_interest_load_step(config: AppConfig) -> tuple[int, tuple[str, ...]]:
    result = load_short_interest_csv(config)
    return result.loaded_count, result.warnings


def _short_interest_provider_fetch_step(
    config: AppConfig,
    ticker: str | None,
) -> tuple[int, tuple[str, ...]]:
    result = fetch_short_interest_sources(
        config,
        provider="all",
        ticker=ticker,
        use_cache=config.signals_short_interest_provider_use_cache,
    )
    return result.normalized_count, result.warnings


def _short_interest_source_import_step(config: AppConfig) -> tuple[int, tuple[str, ...]]:
    result = import_short_interest_source_exports(config)
    return result.imported_count, result.warnings


def _short_interest_signal_step(
    config: AppConfig,
    ticker: str | None,
) -> tuple[int, tuple[str, ...]]:
    result = compute_short_interest_signals(config, ticker=ticker)
    warnings = tuple(
        f"{item.ticker}:{','.join(item.warnings)}"
        for item in result.results
        if item.warnings
    )
    return result.computed_count, warnings


def _short_interest_validation_step(
    config: AppConfig,
    ticker: str | None,
) -> tuple[int, tuple[str, ...]]:
    result = validate_short_interest_signals(config, ticker=ticker)
    warnings = tuple(
        f"{item.ticker}:{','.join(item.warnings)}"
        for item in result.results
        if item.warnings
    )
    return result.updated_count, warnings


def _options_chain_fetch_step(
    config: AppConfig,
    ticker: str | None,
) -> tuple[int, tuple[str, ...]]:
    if not config.options_auto_fetch_daily:
        return 0, ("options_auto_fetch_daily_disabled",)
    result = fetch_options_chain(
        config,
        source=config.options_chain_source,
        ticker=ticker,
        max_tickers=1 if ticker else config.options_max_tickers_per_run,
    )
    warnings = tuple(
        f"{item.ticker}:{','.join(item.warnings)}"
        for item in result.results
        if item.warnings
    )
    return result.loaded_count, warnings


def _options_chain_load_step(config: AppConfig) -> tuple[int, tuple[str, ...]]:
    result = load_options_chain_csv(config)
    return result.loaded_count, result.warnings


def _options_position_load_step(config: AppConfig) -> tuple[int, tuple[str, ...]]:
    result = load_options_positions_csv(config)
    return result.loaded_count, result.warnings


def _options_income_step(
    config: AppConfig,
    ticker: str | None,
) -> tuple[int, tuple[str, ...]]:
    result = compute_options_income(config, ticker=ticker)
    warnings = tuple(
        f"{item.ticker}:{','.join(item.warnings)}"
        for item in result.results
        if item.warnings
    )
    return result.computed_count, warnings


def _options_risk_step(
    config: AppConfig,
    ticker: str | None,
) -> tuple[int, tuple[str, ...]]:
    result = compute_options_risk(config, ticker=ticker)
    warnings = tuple(
        f"{item.ticker}:{','.join(item.warnings)}"
        for item in result.results
        if item.warnings
    )
    return result.computed_count, warnings


def _options_outcome_step(
    config: AppConfig,
    ticker: str | None,
) -> tuple[int, tuple[str, ...]]:
    result = compute_options_outcomes(config, ticker=ticker)
    warnings = tuple(
        f"{item.ticker}:{','.join(item.warnings)}"
        for item in result.results
        if item.warnings
    )
    return result.computed_count, warnings


def _options_lifecycle_step(
    config: AppConfig,
    ticker: str | None,
) -> tuple[int, tuple[str, ...]]:
    result = compute_options_lifecycle(config, ticker=ticker)
    warnings = tuple(
        f"{item.ticker}:{','.join(item.warnings)}"
        for item in result.results
        if item.warnings
    )
    return result.computed_count, warnings


def _target_step(config: AppConfig, ticker: str | None) -> tuple[int, tuple[str, ...]]:
    result = compute_targets(config, ticker=ticker)
    warnings = tuple(
        f"{item.ticker}:{','.join(item.warnings)}"
        for item in result.results
        if item.warnings
    )
    return result.computed_count, warnings


def _score_step(config: AppConfig, ticker: str | None) -> tuple[int, tuple[str, ...]]:
    result = compute_scores(config, ticker=ticker)
    warnings = tuple(
        f"{item.ticker}:{','.join(item.warnings)}"
        for item in result.results
        if item.warnings
    )
    return result.computed_count, warnings


def _fundamental_benchmark_step(config: AppConfig) -> tuple[int, tuple[str, ...]]:
    result = compute_fundamental_benchmarks(config)
    return result.comparison_count, result.warnings


def _alert_step(config: AppConfig, ticker: str | None) -> tuple[int, tuple[str, ...]]:
    result = compute_alerts(config, ticker=ticker)
    warnings = tuple(
        f"{item.ticker}:{','.join(item.warnings)}"
        for item in result.results
        if item.warnings
    )
    return result.stored_count, warnings


def _outcome_step(config: AppConfig, ticker: str | None) -> tuple[int, tuple[str, ...]]:
    result = update_alert_outcomes(config, ticker=ticker)
    warnings = tuple(
        f"{item.ticker}:{','.join(item.warnings)}"
        for item in result.results
        if item.warnings
    )
    return result.updated_count, warnings


def _missing_ticker_resolver_step(config: AppConfig) -> tuple[int, tuple[str, ...]]:
    result = run_missing_ticker_automation(
        config,
        source=SOURCE_ACCOUNT_CONTEXT,
        apply_ready=True,
        hydrate=True,
    )
    rows = result.detected_count + result.onboarded_count + result.hydrated_count
    warnings = list(result.warnings)
    if result.onboarded_tickers:
        warnings.append("onboarded:" + ",".join(result.onboarded_tickers))
    if result.hydrated_tickers:
        warnings.append("hydrated:" + ",".join(result.hydrated_tickers))
    return rows, tuple(dict.fromkeys(warnings))


def _portfolio_load_step(config: AppConfig) -> tuple[int, tuple[str, ...]]:
    result = load_portfolio_csvs(config)
    return result.position_count + result.cash_count, result.warnings


def _portfolio_context_step(
    config: AppConfig,
    ticker: str | None,
) -> tuple[int, tuple[str, ...]]:
    result = compute_portfolio_context(config, ticker=ticker)
    warnings = tuple(
        f"{item.ticker}:{','.join(item.warnings)}"
        for item in result.results
        if item.warnings
    )
    return result.computed_count, warnings


def _technical_step(config: AppConfig, ticker: str | None) -> tuple[int, tuple[str, ...]]:
    result = compute_technical_signals(config, ticker=ticker)
    warnings = tuple(
        f"{item.ticker}:{','.join(item.warnings)}"
        for item in result.results
        if item.warnings
    )
    return result.computed_count, warnings


def _regime_step(config: AppConfig) -> tuple[int, tuple[str, ...]]:
    result = compute_regime_signals(config)
    warnings = tuple(
        f"{item.ticker}:{','.join(item.warnings)}"
        for item in result.results
        if item.warnings
    )
    return result.computed_count, warnings


def _dashboard_step(config: AppConfig) -> tuple[int, tuple[str, ...]]:
    result = build_dashboard(config)
    return (1 if result.path.exists() else 0), ()


def _readiness_step(
    config: AppConfig,
    ticker: str | None,
    intraday: bool = False,
) -> tuple[int, tuple[str, ...]]:
    result = verify_universe(config, ticker=ticker, intraday=intraday)
    warnings = tuple(
        f"{item.ticker}:{','.join(item.warnings)}"
        for item in result.statuses
        if item.warnings
    )
    return result.ready_count, warnings


def _daily_price_quote_fallback_step(
    config: AppConfig,
    ticker: str | None,
) -> tuple[int, tuple[str, ...]]:
    wanted = normalize_ticker(ticker) if ticker else None
    assets = [asset for asset in list_assets(config.database_path) if asset.active_flag == 1]
    if wanted:
        assets = [asset for asset in assets if asset.ticker == wanted]

    timestamp = datetime.now().isoformat(timespec="seconds")
    warnings: list[str] = []
    loaded = 0
    for asset in assets:
        feature = latest_price_feature(config.database_path, asset.ticker)
        if feature is None or feature.current_price is None:
            warnings.append(f"{asset.ticker}:missing_daily_price_fallback")
            continue
        stale_warning = ""
        if feature.latest_price_date:
            try:
                latest_date = date.fromisoformat(feature.latest_price_date)
                if (date.today() - latest_date).days > config.market_data_stale_after_days:
                    stale_warning = ",stale_daily_price"
            except ValueError:
                stale_warning = ",malformed_daily_price_date"
        upsert_quote_snapshot(
            config.database_path,
            QuoteSnapshot(
                ticker=asset.ticker,
                quote_timestamp=timestamp,
                last=feature.current_price,
                mark=feature.current_price,
                close=feature.current_price,
                market_data_type="daily_fallback",
                source="daily_price_fallback",
                as_of_date=date.today().isoformat(),
                effective_date=timestamp,
            ),
        )
        loaded += 1
        warnings.append(
            f"{asset.ticker}:daily_price_fallback,latest_price_date="
            f"{feature.latest_price_date or 'none'}{stale_warning}"
        )
    return loaded, tuple(warnings)


def _quote_step(
    config: AppConfig,
    ticker: str | None,
    source: str = "ibkr",
) -> tuple[int, tuple[str, ...]]:
    result = update_quote_snapshots(config, ticker=ticker)
    warnings = tuple(
        f"{item.ticker}:{','.join(item.warnings)}"
        for item in result.results
        if item.warnings
    )
    if source == "ibkr" or result.loaded_count > 0:
        return result.loaded_count, warnings

    price_result = update_prices(config, ticker=ticker)
    price_warnings = tuple(
        f"{item.ticker}:{','.join(item.warnings)}"
        for item in price_result.results
        if item.warnings
    )
    fallback_loaded, fallback_warnings = _daily_price_quote_fallback_step(config, ticker)
    return (
        fallback_loaded,
        (
            "ibkr_quote_unavailable",
            "auto_quote_fallback_used",
            *warnings,
            *price_warnings,
            *fallback_warnings,
        ),
    )


def _ibkr_etf_nav_step(config: AppConfig, ticker: str | None) -> tuple[int, tuple[str, ...]]:
    result = update_etf_navs_from_ibkr(config, ticker=ticker)
    warnings = tuple(
        f"{item.ticker}:{','.join(item.warnings)}"
        for item in result.results
        if item.warnings
    )
    return result.loaded_count, warnings


def _gap_step(config: AppConfig, ticker: str | None) -> tuple[int, tuple[str, ...]]:
    result = compute_intraday_gaps(config, ticker=ticker)
    warnings = tuple(
        f"{item.ticker}:{','.join(item.warnings)}"
        for item in result.results
        if item.warnings
    )
    return result.updated_count, warnings


def _range_step(config: AppConfig, ticker: str | None) -> tuple[int, tuple[str, ...]]:
    result = compute_range_snapshots(config, ticker=ticker)
    warnings = tuple(
        f"{item.ticker}:{','.join(item.warnings)}"
        for item in result.results
        if item.warnings
    )
    if result.notification_count:
        warnings = warnings + (f"notifications_created:{result.notification_count}",)
    return result.updated_count, warnings


def _delivery_step(config: AppConfig, channel: str) -> tuple[int, tuple[str, ...]]:
    result = deliver_notifications(config, channel=channel)
    warnings = tuple(result.warnings)
    if result.failed_count:
        warnings = warnings + (f"delivery_failed:{result.failed_count}",)
    return result.delivered_count, warnings
