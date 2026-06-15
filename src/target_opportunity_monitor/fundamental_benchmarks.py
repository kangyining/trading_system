from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from statistics import median

from .config import AppConfig
from .sec_fundamentals import load_cik_map
from .storage import (
    Asset,
    AssetChangeEvent,
    FundamentalBenchmarkSnapshot,
    FundamentalComparisonSnapshot,
    insert_asset_change_event,
    is_scoreable_asset,
    latest_estimate,
    latest_price_feature,
    list_assets,
    list_fundamentals,
    list_scores,
    list_targets,
    normalize_asset_role,
    normalize_ticker,
    upsert_asset,
    upsert_fundamental_benchmark_snapshot,
    upsert_fundamental_comparison_snapshot,
)
from .valuation import build_inputs, compute_ratios, normalize_fundamentals
from .watchlist import upsert_watchlist_asset


UNIVERSE_CANDIDATE_COLUMNS = (
    "ticker",
    "name",
    "asset_type",
    "exchange",
    "currency",
    "sector",
    "industry",
    "country",
    "intended_role",
    "cik",
    "source",
    "notes",
)

SECTOR_BENCHMARK_COLUMNS = (
    "sector",
    "benchmark_ticker",
    "benchmark_type",
    "source",
    "notes",
)

VALID_ASSET_TYPES = {"equity", "stock", "common_stock", "etf", "fund", "index_etf"}
VALID_ROLES = {"scoreable", "commentary_validation", "regime_proxy", "inactive"}
EQUITY_TYPES = {"equity", "stock", "common_stock"}
ETF_TYPES = {"etf", "fund", "index_etf"}

GICS_SECTORS = {
    "Communication Services",
    "Consumer Discretionary",
    "Consumer Staples",
    "Energy",
    "Financials",
    "Health Care",
    "Industrials",
    "Information Technology",
    "Materials",
    "Real Estate",
    "Utilities",
}

DEFAULT_SECTOR_BENCHMARKS = (
    ("Overall", "SPY", "overall", "phase13a_default", "Broad US equity benchmark"),
    ("Nasdaq 100", "QQQ", "overall", "phase13a_default", "Growth/mega-cap benchmark"),
    ("Information Technology", "XLK", "sector", "phase13a_default", "Technology sector ETF proxy"),
    ("Communication Services", "XLC", "sector", "phase13a_default", "Communication services sector ETF proxy"),
    ("Consumer Discretionary", "XLY", "sector", "phase13a_default", "Consumer discretionary sector ETF proxy"),
    ("Consumer Staples", "XLP", "sector", "phase13a_default", "Consumer staples sector ETF proxy"),
    ("Financials", "XLF", "sector", "phase13a_default", "Financials sector ETF proxy"),
    ("Health Care", "XLV", "sector", "phase13a_default", "Health care sector ETF proxy"),
    ("Industrials", "XLI", "sector", "phase13a_default", "Industrials sector ETF proxy"),
    ("Energy", "XLE", "sector", "phase13a_default", "Energy sector ETF proxy"),
    ("Utilities", "XLU", "sector", "phase13a_default", "Utilities sector ETF proxy"),
    ("Materials", "XLB", "sector", "phase13a_default", "Materials sector ETF proxy"),
    ("Real Estate", "XLRE", "sector", "phase13a_default", "Real estate sector ETF proxy"),
)

SECTOR_BENCHMARK_ASSET_META = {
    "SPY": ("SPDR S&P 500 ETF Trust", "Overall", "Broad Market"),
    "QQQ": ("Invesco QQQ Trust", "Nasdaq 100", "Broad Market"),
    "XLK": ("Technology Select Sector SPDR Fund", "Information Technology", "Sector ETF"),
    "XLC": ("Communication Services Select Sector SPDR Fund", "Communication Services", "Sector ETF"),
    "XLY": ("Consumer Discretionary Select Sector SPDR Fund", "Consumer Discretionary", "Sector ETF"),
    "XLP": ("Consumer Staples Select Sector SPDR Fund", "Consumer Staples", "Sector ETF"),
    "XLF": ("Financial Select Sector SPDR Fund", "Financials", "Sector ETF"),
    "XLV": ("Health Care Select Sector SPDR Fund", "Health Care", "Sector ETF"),
    "XLI": ("Industrial Select Sector SPDR Fund", "Industrials", "Sector ETF"),
    "XLE": ("Energy Select Sector SPDR Fund", "Energy", "Sector ETF"),
    "XLU": ("Utilities Select Sector SPDR Fund", "Utilities", "Sector ETF"),
    "XLB": ("Materials Select Sector SPDR Fund", "Materials", "Sector ETF"),
    "XLRE": ("Real Estate Select Sector SPDR Fund", "Real Estate", "Sector ETF"),
}


@dataclass(frozen=True)
class UniverseCandidate:
    ticker: str
    name: str | None
    asset_type: str
    exchange: str | None
    currency: str
    sector: str | None
    industry: str | None
    country: str
    intended_role: str
    cik: str | None
    source: str | None
    notes: str | None
    row_number: int


@dataclass(frozen=True)
class UniverseExpansionPlan:
    candidate_path: Path
    sector_benchmark_path: Path
    valid_candidates: tuple[UniverseCandidate, ...]
    invalid_candidates: tuple[str, ...]
    already_active_tickers: tuple[str, ...]
    missing_sector_benchmark_tickers: tuple[str, ...]
    missing_sector_benchmark_price_tickers: tuple[str, ...]
    apply_ready: bool
    blocked_reason: str | None


@dataclass(frozen=True)
class UniverseApplyResult:
    applied_count: int
    applied_tickers: tuple[str, ...]
    invalid_candidates: tuple[str, ...]
    warnings: tuple[str, ...]
    dry_run: bool
    blocked_reason: str | None


@dataclass(frozen=True)
class FundamentalBenchmarkUpdateResult:
    benchmark_count: int
    comparison_count: int
    comparison_date: str
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class FundamentalBenchmarkStatus:
    benchmark_snapshot_count: int
    comparison_snapshot_count: int
    latest_comparison_date: str | None
    scoreable_ticker_count: int
    compared_ticker_count: int
    sector_benchmark_count: int
    missing_sector_benchmark_tickers: tuple[str, ...]
    missing_sector_benchmark_price_tickers: tuple[str, ...]
    warning_tickers: tuple[str, ...]


@dataclass(frozen=True)
class _TickerMetrics:
    ticker: str
    sector: str | None
    industry: str | None
    current_price: float | None
    forward_pe: float | None
    trailing_pe: float | None
    ev_ebitda: float | None
    p_fcf: float | None
    p_s: float | None
    revenue_growth: float | None
    net_margin: float | None
    fcf_margin: float | None
    roe: float | None
    net_debt_ebitda: float | None
    valuation_gap: float | None
    opportunity_score: float | None
    return_3m: float | None
    warnings: tuple[str, ...]


def _clean(value: str | None) -> str | None:
    cleaned = (value or "").strip()
    return cleaned or None


def _safe_float(value: object) -> float | None:
    if value is None:
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed == parsed else None


def _safe_divide(numerator: float | None, denominator: float | None) -> float | None:
    if numerator is None or denominator in (None, 0):
        return None
    return numerator / denominator


def _metric_median(metrics: list[_TickerMetrics], field_name: str) -> float | None:
    values = [
        value
        for value in (_safe_float(getattr(metric, field_name)) for metric in metrics)
        if value is not None
    ]
    return median(values) if values else None


def _first_text(*values: str | None) -> str | None:
    for value in values:
        cleaned = _clean(value)
        if cleaned:
            return cleaned
    return None


def _join_warnings(values: list[str] | tuple[str, ...]) -> str | None:
    ordered: list[str] = []
    for value in values:
        for part in str(value).split(";"):
            cleaned = part.strip()
            if cleaned and cleaned not in ordered:
                ordered.append(cleaned)
    return ";".join(ordered) if ordered else None


def ensure_sector_benchmark_csv(config: AppConfig) -> Path:
    path = config.sector_benchmarks_path
    if path.exists():
        return path
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=SECTOR_BENCHMARK_COLUMNS)
        writer.writeheader()
        for sector, ticker, benchmark_type, source, notes in DEFAULT_SECTOR_BENCHMARKS:
            writer.writerow(
                {
                    "sector": sector,
                    "benchmark_ticker": ticker,
                    "benchmark_type": benchmark_type,
                    "source": source,
                    "notes": notes,
                }
            )
    return path


def read_sector_benchmarks(config: AppConfig) -> dict[str, str]:
    path = ensure_sector_benchmark_csv(config)
    rows: dict[str, str] = {}
    with path.open("r", encoding="utf-8-sig", newline="") as input_file:
        reader = csv.DictReader(input_file)
        for row in reader:
            sector = _clean(row.get("sector"))
            ticker = _clean(row.get("benchmark_ticker"))
            if sector and ticker:
                rows[sector.strip().lower()] = normalize_ticker(ticker)
    return rows


def _sector_benchmark_tickers(config: AppConfig) -> tuple[str, ...]:
    return tuple(sorted(set(read_sector_benchmarks(config).values())))


def _read_candidate_rows(path: Path) -> list[UniverseCandidate]:
    if not path.exists():
        return []
    candidates: list[UniverseCandidate] = []
    with path.open("r", encoding="utf-8-sig", newline="") as input_file:
        reader = csv.DictReader(input_file)
        for row_number, row in enumerate(reader, start=2):
            ticker = _clean(row.get("ticker"))
            if not ticker:
                continue
            candidates.append(
                UniverseCandidate(
                    ticker=normalize_ticker(ticker),
                    name=_clean(row.get("name")),
                    asset_type=(_clean(row.get("asset_type")) or "equity").lower(),
                    exchange=_clean(row.get("exchange")),
                    currency=_clean(row.get("currency")) or "USD",
                    sector=_clean(row.get("sector")),
                    industry=_clean(row.get("industry")),
                    country=_clean(row.get("country")) or "US",
                    intended_role=normalize_asset_role(row.get("intended_role")),
                    cik=_clean(row.get("cik")),
                    source=_clean(row.get("source")),
                    notes=_clean(row.get("notes")),
                    row_number=row_number,
                )
            )
    return candidates


def export_universe_candidate_template(config: AppConfig) -> Path:
    ensure_sector_benchmark_csv(config)
    existing_assets = {asset.ticker for asset in list_assets(config.database_path)}
    rows: list[dict[str, str]] = []
    for ticker in _sector_benchmark_tickers(config):
        if ticker in existing_assets:
            continue
        name, sector, industry = SECTOR_BENCHMARK_ASSET_META.get(
            ticker,
            (f"{ticker} sector benchmark", "Benchmark", "Sector ETF"),
        )
        rows.append(
            {
                "ticker": ticker,
                "name": name,
                "asset_type": "etf",
                "exchange": "NYSEARCA",
                "currency": "USD",
                "sector": sector,
                "industry": industry,
                "country": "US",
                "intended_role": "regime_proxy",
                "cik": "",
                "source": "phase13a_sector_benchmark_template",
                "notes": "Regime/relative-strength benchmark only; not scoreable.",
            }
        )

    path = config.universe_candidates_path
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=UNIVERSE_CANDIDATE_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    return path


def _candidate_warnings(
    candidate: UniverseCandidate,
    cik_map: dict[str, str],
) -> list[str]:
    warnings: list[str] = []
    if candidate.asset_type not in VALID_ASSET_TYPES:
        warnings.append("invalid_asset_type")
    if candidate.intended_role not in VALID_ROLES:
        warnings.append("invalid_asset_role")
    if not candidate.sector:
        warnings.append("missing_sector")
    elif candidate.asset_type in EQUITY_TYPES and candidate.sector not in GICS_SECTORS:
        warnings.append("non_gics_sector")
    if not candidate.industry:
        warnings.append("missing_industry")
    if not candidate.source:
        warnings.append("missing_source")
    if not candidate.notes:
        warnings.append("missing_notes")
    if (
        candidate.asset_type in EQUITY_TYPES
        and candidate.intended_role == "scoreable"
        and not (candidate.cik or cik_map.get(candidate.ticker))
    ):
        warnings.append("missing_cik_for_scoreable_equity")
    return warnings


def universe_expansion_plan(config: AppConfig) -> UniverseExpansionPlan:
    ensure_sector_benchmark_csv(config)
    existing_assets = {asset.ticker: asset for asset in list_assets(config.database_path)}
    cik_map = load_cik_map(config.cik_map_path)
    candidates = _read_candidate_rows(config.universe_candidates_path)
    valid: list[UniverseCandidate] = []
    invalid: list[str] = []
    already_active: list[str] = []
    seen: set[str] = set()

    for candidate in candidates:
        warnings = _candidate_warnings(candidate, cik_map)
        if candidate.ticker in seen:
            warnings.append("duplicate_candidate")
        seen.add(candidate.ticker)
        existing = existing_assets.get(candidate.ticker)
        if existing and existing.active_flag == 1:
            already_active.append(candidate.ticker)
            if normalize_asset_role(existing.asset_role) == candidate.intended_role:
                continue
        if warnings:
            invalid.append(
                f"row {candidate.row_number} {candidate.ticker}: {','.join(warnings)}"
            )
        else:
            valid.append(candidate)

    sector_benchmark_tickers = _sector_benchmark_tickers(config)
    missing_benchmark_tickers = tuple(
        ticker for ticker in sector_benchmark_tickers if ticker not in existing_assets
    )
    missing_benchmark_price_tickers = tuple(
        ticker
        for ticker in sector_benchmark_tickers
        if latest_price_feature(config.database_path, ticker) is None
    )
    blocked_reason = None
    if not config.universe_candidates_path.exists():
        blocked_reason = "missing_candidate_csv"
    elif invalid and not valid:
        blocked_reason = "no_valid_candidates"
    elif candidates and not valid:
        blocked_reason = "all_candidates_already_active"
    return UniverseExpansionPlan(
        candidate_path=config.universe_candidates_path,
        sector_benchmark_path=config.sector_benchmarks_path,
        valid_candidates=tuple(valid),
        invalid_candidates=tuple(invalid),
        already_active_tickers=tuple(sorted(set(already_active))),
        missing_sector_benchmark_tickers=missing_benchmark_tickers,
        missing_sector_benchmark_price_tickers=missing_benchmark_price_tickers,
        apply_ready=bool(valid),
        blocked_reason=blocked_reason,
    )


def _upsert_cik(path: Path, ticker: str, cik: str | None) -> None:
    if not cik:
        return
    normalized = normalize_ticker(ticker)
    cleaned_cik = cik.strip().zfill(10)
    rows: list[dict[str, str]] = []
    if path.exists():
        with path.open("r", encoding="utf-8-sig", newline="") as input_file:
            rows = [dict(row) for row in csv.DictReader(input_file)]
    updated = False
    for row in rows:
        if normalize_ticker(row.get("ticker", "")) == normalized:
            row["cik"] = cleaned_cik
            updated = True
            break
    if not updated:
        rows.append({"ticker": normalized, "cik": cleaned_cik})
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as output_file:
        writer = csv.DictWriter(output_file, fieldnames=("ticker", "cik"))
        writer.writeheader()
        for row in sorted(rows, key=lambda item: normalize_ticker(item.get("ticker", ""))):
            writer.writerow(
                {
                    "ticker": normalize_ticker(row.get("ticker", "")),
                    "cik": row.get("cik", ""),
                }
            )


def _candidate_to_asset(candidate: UniverseCandidate) -> Asset:
    return Asset(
        ticker=candidate.ticker,
        name=candidate.name,
        asset_type=candidate.asset_type,
        exchange=candidate.exchange,
        currency=candidate.currency,
        sector=candidate.sector,
        industry=candidate.industry,
        country=candidate.country,
        active_flag=0 if candidate.intended_role == "inactive" else 1,
        asset_role=candidate.intended_role,
        source=candidate.source or "universe_candidate",
        as_of_date=date.today().isoformat(),
        effective_date=date.today().isoformat(),
    )


def apply_universe_candidates(
    config: AppConfig,
    *,
    confirm: bool = False,
    allow_partial: bool = False,
) -> UniverseApplyResult:
    plan = universe_expansion_plan(config)
    warnings: list[str] = list(plan.invalid_candidates)
    if plan.invalid_candidates and not allow_partial:
        return UniverseApplyResult(
            applied_count=0,
            applied_tickers=(),
            invalid_candidates=plan.invalid_candidates,
            warnings=tuple(warnings),
            dry_run=not confirm,
            blocked_reason="invalid_candidates_present",
        )
    if not plan.valid_candidates:
        return UniverseApplyResult(
            applied_count=0,
            applied_tickers=(),
            invalid_candidates=plan.invalid_candidates,
            warnings=tuple(warnings),
            dry_run=not confirm,
            blocked_reason=plan.blocked_reason or "no_valid_candidates",
        )
    if not confirm:
        return UniverseApplyResult(
            applied_count=0,
            applied_tickers=tuple(candidate.ticker for candidate in plan.valid_candidates),
            invalid_candidates=plan.invalid_candidates,
            warnings=tuple(warnings),
            dry_run=True,
            blocked_reason=None,
        )

    applied: list[str] = []
    existing_assets = {asset.ticker: asset for asset in list_assets(config.database_path)}
    for candidate in plan.valid_candidates:
        previous = existing_assets.get(candidate.ticker)
        asset = _candidate_to_asset(candidate)
        upsert_watchlist_asset(config.watchlist_path, asset)
        upsert_asset(config.database_path, asset)
        if asset.asset_type in EQUITY_TYPES:
            _upsert_cik(config.cik_map_path, asset.ticker, candidate.cik)
        insert_asset_change_event(
            config.database_path,
            AssetChangeEvent(
                event_timestamp=datetime.now(UTC).replace(microsecond=0).isoformat(),
                ticker=asset.ticker,
                event_type="universe_candidate_apply",
                previous_active_flag=previous.active_flag if previous else None,
                new_active_flag=asset.active_flag,
                reason="phase13a_universe_expansion",
                details=f"asset_role={asset.asset_role};asset_type={asset.asset_type}",
                source="phase13a_universe_candidates",
                as_of_date=asset.as_of_date,
                effective_date=asset.effective_date,
            ),
        )
        applied.append(asset.ticker)

    return UniverseApplyResult(
        applied_count=len(applied),
        applied_tickers=tuple(applied),
        invalid_candidates=plan.invalid_candidates,
        warnings=tuple(warnings),
        dry_run=False,
        blocked_reason=None,
    )


def _estimate_value(config: AppConfig, ticker: str) -> float | None:
    estimate = latest_estimate(config.database_path, ticker, "eps")
    if estimate is None:
        return None
    return (
        _safe_float(estimate.consensus_mean)
        or _safe_float(estimate.consensus_median)
        or _safe_float(estimate.consensus_high)
        or _safe_float(estimate.consensus_low)
    )


def _latest_target_gap(config: AppConfig, ticker: str) -> float | None:
    targets = list_targets(config.database_path, ticker)
    return targets[-1].valuation_gap if targets else None


def _latest_score(config: AppConfig, ticker: str) -> float | None:
    scores = list_scores(config.database_path, ticker)
    return scores[-1].opportunity_score if scores else None


def _revenue_growth(fundamentals: list[object]) -> float | None:
    usable = [
        row
        for row in sorted(fundamentals, key=lambda item: item.fiscal_period_end)
        if row.revenue is not None and row.revenue > 0
    ]
    if len(usable) < 2:
        return None
    previous, latest = usable[-2], usable[-1]
    return _safe_divide(latest.revenue - previous.revenue, abs(previous.revenue))


def _ticker_metrics(config: AppConfig, asset: Asset) -> _TickerMetrics:
    warnings: list[str] = []
    feature = latest_price_feature(config.database_path, asset.ticker)
    if feature is None:
        warnings.append("missing_price_feature")
    fundamentals = list_fundamentals(config.database_path, asset.ticker)
    normalized = normalize_fundamentals(fundamentals)
    if normalized is None:
        warnings.append("missing_usable_fundamentals")
    forward_eps = _estimate_value(config, asset.ticker)
    if forward_eps is None:
        warnings.append("missing_forward_eps_estimate")
    inputs, input_warnings = build_inputs(
        feature.current_price if feature else None,
        normalized,
        forward_eps,
    )
    warnings.extend(input_warnings)
    ratios = compute_ratios(inputs) if inputs is not None else {}
    fcf = normalized.free_cash_flow if normalized else None
    if normalized and fcf is None and normalized.cash_from_operations is not None:
        capex = normalized.capital_expenditure or 0.0
        fcf = (
            normalized.cash_from_operations + capex
            if capex < 0
            else normalized.cash_from_operations - capex
        )
    return _TickerMetrics(
        ticker=asset.ticker,
        sector=asset.sector,
        industry=asset.industry,
        current_price=feature.current_price if feature else None,
        forward_pe=ratios.get("forward_pe"),
        trailing_pe=ratios.get("trailing_pe"),
        ev_ebitda=ratios.get("ev_ebitda"),
        p_fcf=ratios.get("p_fcf"),
        p_s=ratios.get("p_s"),
        revenue_growth=_revenue_growth(fundamentals),
        net_margin=_safe_divide(normalized.net_income, normalized.revenue)
        if normalized
        else None,
        fcf_margin=_safe_divide(fcf, normalized.revenue) if normalized else None,
        roe=_safe_divide(normalized.net_income, normalized.total_equity)
        if normalized
        else None,
        net_debt_ebitda=_safe_divide(normalized.net_debt, normalized.ebitda)
        if normalized
        else None,
        valuation_gap=_latest_target_gap(config, asset.ticker),
        opportunity_score=_latest_score(config, asset.ticker),
        return_3m=feature.return_3m if feature else None,
        warnings=tuple(warnings),
    )


def _benchmark_snapshot(
    comparison_date: str,
    benchmark_type: str,
    benchmark_key: str,
    metrics: list[_TickerMetrics],
    model_version: str,
    warnings: tuple[str, ...] = (),
) -> FundamentalBenchmarkSnapshot:
    return FundamentalBenchmarkSnapshot(
        benchmark_date=comparison_date,
        benchmark_type=benchmark_type,
        benchmark_key=benchmark_key,
        ticker_count=len(metrics),
        forward_pe_median=_metric_median(metrics, "forward_pe"),
        trailing_pe_median=_metric_median(metrics, "trailing_pe"),
        ev_ebitda_median=_metric_median(metrics, "ev_ebitda"),
        p_fcf_median=_metric_median(metrics, "p_fcf"),
        p_s_median=_metric_median(metrics, "p_s"),
        revenue_growth_median=_metric_median(metrics, "revenue_growth"),
        net_margin_median=_metric_median(metrics, "net_margin"),
        fcf_margin_median=_metric_median(metrics, "fcf_margin"),
        roe_median=_metric_median(metrics, "roe"),
        net_debt_ebitda_median=_metric_median(metrics, "net_debt_ebitda"),
        opportunity_score_median=_metric_median(metrics, "opportunity_score"),
        valuation_gap_median=_metric_median(metrics, "valuation_gap"),
        data_warnings=_join_warnings(warnings),
        model_version=model_version,
        source="fundamental_benchmark",
        as_of_date=comparison_date,
        effective_date=comparison_date,
    )


def _percentile(values: list[float], value: float | None) -> float | None:
    if value is None or not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return 100.0
    below_or_equal = sum(1 for item in ordered if item <= value)
    return max(0.0, min(100.0, (below_or_equal - 1) / (len(ordered) - 1) * 100.0))


def _benchmark_return(config: AppConfig, ticker: str) -> float | None:
    feature = latest_price_feature(config.database_path, ticker)
    return feature.return_3m if feature else None


def compute_fundamental_benchmarks(config: AppConfig) -> FundamentalBenchmarkUpdateResult:
    ensure_sector_benchmark_csv(config)
    comparison_date = date.today().isoformat()
    model_version = config.fundamental_benchmark_model_version
    assets = [
        asset
        for asset in list_assets(config.database_path)
        if is_scoreable_asset(asset)
        and (asset.asset_type or "equity").strip().lower() in EQUITY_TYPES
    ]
    equity_assets = [
        asset
        for asset in assets
        if (asset.asset_type or "equity").strip().lower() in EQUITY_TYPES
    ]
    metrics = [_ticker_metrics(config, asset) for asset in equity_assets]
    warnings: list[str] = []
    if not metrics:
        warnings.append("no_scoreable_equity_metrics")
    benchmark_count = 0
    comparison_count = 0

    overall = _benchmark_snapshot(
        comparison_date,
        "overall",
        "scoreable_equities",
        metrics,
        model_version,
        tuple(["empty_overall_benchmark"] if not metrics else []),
    )
    upsert_fundamental_benchmark_snapshot(config.database_path, overall)
    benchmark_count += 1

    by_sector: dict[str, list[_TickerMetrics]] = {}
    by_industry: dict[str, list[_TickerMetrics]] = {}
    for metric in metrics:
        if metric.sector:
            by_sector.setdefault(metric.sector, []).append(metric)
        if metric.industry:
            by_industry.setdefault(metric.industry, []).append(metric)

    for sector, sector_metrics in sorted(by_sector.items()):
        sector_warnings: list[str] = []
        if len(sector_metrics) < config.fundamental_benchmark_min_sector_peer_count:
            sector_warnings.append("insufficient_sector_peer_count")
        upsert_fundamental_benchmark_snapshot(
            config.database_path,
            _benchmark_snapshot(
                comparison_date,
                "sector",
                sector,
                sector_metrics,
                model_version,
                tuple(sector_warnings),
            ),
        )
        benchmark_count += 1

    for industry, industry_metrics in sorted(by_industry.items()):
        industry_warnings: list[str] = []
        if len(industry_metrics) < config.fundamental_benchmark_min_industry_peer_count:
            industry_warnings.append("insufficient_industry_peer_count")
        upsert_fundamental_benchmark_snapshot(
            config.database_path,
            _benchmark_snapshot(
                comparison_date,
                "industry",
                industry,
                industry_metrics,
                model_version,
                tuple(industry_warnings),
            ),
        )
        benchmark_count += 1

    sector_benchmarks = read_sector_benchmarks(config)
    spy_return = _benchmark_return(config, "SPY")
    qqq_return = _benchmark_return(config, "QQQ")
    overall_forward_pe = overall.forward_pe_median
    overall_count = len(metrics)

    for metric in metrics:
        ticker_warnings = list(metric.warnings)
        sector_metrics = by_sector.get(metric.sector or "", [])
        industry_metrics = by_industry.get(metric.industry or "", [])
        sector_snapshot = _benchmark_snapshot(
            comparison_date,
            "sector",
            metric.sector or "unknown",
            sector_metrics,
            model_version,
        )
        sector_benchmark = (
            sector_benchmarks.get((metric.sector or "").strip().lower())
            if metric.sector
            else None
        )
        if not sector_benchmark:
            ticker_warnings.append("missing_sector_benchmark_mapping")
        sector_return = _benchmark_return(config, sector_benchmark) if sector_benchmark else None
        if spy_return is None:
            ticker_warnings.append("missing_spy_price_feature")
        if qqq_return is None:
            ticker_warnings.append("missing_qqq_price_feature")
        if sector_benchmark and sector_return is None:
            ticker_warnings.append("missing_sector_benchmark_price_feature")
        if len(sector_metrics) < config.fundamental_benchmark_min_sector_peer_count:
            ticker_warnings.append("insufficient_sector_peer_count")
        if len(industry_metrics) < config.fundamental_benchmark_min_industry_peer_count:
            ticker_warnings.append("insufficient_industry_peer_count")

        sector_values = [
            item.forward_pe for item in sector_metrics if item.forward_pe is not None
        ]
        sector_pe_discount = None
        if metric.forward_pe is not None and sector_snapshot.forward_pe_median not in (None, 0):
            sector_pe_discount = (
                sector_snapshot.forward_pe_median - metric.forward_pe
            ) / abs(sector_snapshot.forward_pe_median)

        status = "ok"
        if "missing_usable_fundamentals" in ticker_warnings:
            status = "missing_fundamentals"
        elif "missing_forward_eps_estimate" in ticker_warnings:
            status = "missing_estimate"
        elif "insufficient_sector_peer_count" in ticker_warnings:
            status = "sparse_sector"

        comparison = FundamentalComparisonSnapshot(
            ticker=metric.ticker,
            comparison_date=comparison_date,
            sector=metric.sector,
            industry=metric.industry,
            sector_benchmark_ticker=sector_benchmark,
            overall_peer_count=overall_count,
            sector_peer_count=len(sector_metrics),
            industry_peer_count=len(industry_metrics),
            forward_pe=metric.forward_pe,
            sector_forward_pe_median=sector_snapshot.forward_pe_median,
            overall_forward_pe_median=overall_forward_pe,
            sector_forward_pe_discount_pct=sector_pe_discount,
            sector_forward_pe_percentile=_percentile(sector_values, metric.forward_pe),
            ev_ebitda=metric.ev_ebitda,
            sector_ev_ebitda_median=sector_snapshot.ev_ebitda_median,
            p_fcf=metric.p_fcf,
            sector_p_fcf_median=sector_snapshot.p_fcf_median,
            net_margin=metric.net_margin,
            sector_net_margin_median=sector_snapshot.net_margin_median,
            revenue_growth=metric.revenue_growth,
            sector_revenue_growth_median=sector_snapshot.revenue_growth_median,
            net_debt_ebitda=metric.net_debt_ebitda,
            sector_net_debt_ebitda_median=sector_snapshot.net_debt_ebitda_median,
            valuation_gap=metric.valuation_gap,
            sector_valuation_gap_median=sector_snapshot.valuation_gap_median,
            opportunity_score=metric.opportunity_score,
            sector_opportunity_score_median=sector_snapshot.opportunity_score_median,
            relative_strength_vs_spy=(
                metric.return_3m - spy_return
                if metric.return_3m is not None and spy_return is not None
                else None
            ),
            relative_strength_vs_qqq=(
                metric.return_3m - qqq_return
                if metric.return_3m is not None and qqq_return is not None
                else None
            ),
            relative_strength_vs_sector=(
                metric.return_3m - sector_return
                if metric.return_3m is not None and sector_return is not None
                else None
            ),
            benchmark_status=status,
            data_warnings=_join_warnings(ticker_warnings),
            model_version=model_version,
            source="fundamental_benchmark",
            as_of_date=comparison_date,
            effective_date=comparison_date,
        )
        upsert_fundamental_comparison_snapshot(config.database_path, comparison)
        comparison_count += 1

    return FundamentalBenchmarkUpdateResult(
        benchmark_count=benchmark_count,
        comparison_count=comparison_count,
        comparison_date=comparison_date,
        warnings=tuple(sorted(set(warnings))),
    )


def fundamental_benchmark_status(config: AppConfig) -> FundamentalBenchmarkStatus:
    from .storage import (
        count_rows_by_table,
        fundamental_comparison_statuses,
        latest_fundamental_benchmark_date,
    )

    assets = [
        asset
        for asset in list_assets(config.database_path)
        if is_scoreable_asset(asset)
        and (asset.asset_type or "equity").strip().lower() in EQUITY_TYPES
    ]
    comparisons = [
        comparison
        for comparison in fundamental_comparison_statuses(config.database_path)
        if comparison.comparison_date
    ]
    benchmark_tickers = _sector_benchmark_tickers(config)
    active_tickers = {asset.ticker for asset in list_assets(config.database_path)}
    missing_benchmark_tickers = tuple(
        ticker for ticker in benchmark_tickers if ticker not in active_tickers
    )
    missing_price_tickers = tuple(
        ticker for ticker in benchmark_tickers if latest_price_feature(config.database_path, ticker) is None
    )
    return FundamentalBenchmarkStatus(
        benchmark_snapshot_count=count_rows_by_table(
            config.database_path,
            "fundamental_benchmark_snapshots",
        ),
        comparison_snapshot_count=count_rows_by_table(
            config.database_path,
            "fundamental_comparison_snapshots",
        ),
        latest_comparison_date=latest_fundamental_benchmark_date(config.database_path),
        scoreable_ticker_count=len(assets),
        compared_ticker_count=len({comparison.ticker for comparison in comparisons}),
        sector_benchmark_count=len(benchmark_tickers),
        missing_sector_benchmark_tickers=missing_benchmark_tickers,
        missing_sector_benchmark_price_tickers=missing_price_tickers,
        warning_tickers=tuple(
            sorted(
                {
                    comparison.ticker
                    for comparison in comparisons
                    if comparison.data_warnings
                }
            )
        ),
    )


def build_universe_expansion_plan_text(config: AppConfig) -> str:
    plan = universe_expansion_plan(config)
    lines = [
        "Universe expansion plan",
        f"Candidate CSV: {plan.candidate_path}",
        f"Sector benchmark CSV: {plan.sector_benchmark_path}",
        f"Valid candidates: {len(plan.valid_candidates)}",
        f"Invalid candidates: {len(plan.invalid_candidates)}",
        f"Apply ready: {plan.apply_ready}",
        f"Blocked reason: {plan.blocked_reason or 'none'}",
        "Valid candidate tickers: "
        + (", ".join(candidate.ticker for candidate in plan.valid_candidates) or "none"),
        "Already active candidate tickers: "
        + (", ".join(plan.already_active_tickers) or "none"),
        "Missing sector benchmark assets: "
        + (", ".join(plan.missing_sector_benchmark_tickers) or "none"),
        "Missing sector benchmark prices: "
        + (", ".join(plan.missing_sector_benchmark_price_tickers) or "none"),
    ]
    if plan.invalid_candidates:
        lines.append("Invalid rows:")
        lines.extend(f"- {warning}" for warning in plan.invalid_candidates)
    return "\n".join(lines)


def build_fundamental_benchmark_status_text(config: AppConfig) -> str:
    status = fundamental_benchmark_status(config)
    return "\n".join(
        [
            "Fundamental benchmark status",
            f"Benchmark snapshots: {status.benchmark_snapshot_count}",
            f"Comparison snapshots: {status.comparison_snapshot_count}",
            f"Latest comparison date: {status.latest_comparison_date or 'none'}",
            f"Compared scoreable equities: {status.compared_ticker_count}/{status.scoreable_ticker_count}",
            f"Sector benchmark mappings: {status.sector_benchmark_count}",
            "Missing benchmark assets: "
            + (", ".join(status.missing_sector_benchmark_tickers) or "none"),
            "Missing benchmark prices: "
            + (", ".join(status.missing_sector_benchmark_price_tickers) or "none"),
            "Warning tickers: " + (", ".join(status.warning_tickers) or "none"),
        ]
    )


def _latest_benchmark_by_key(
    benchmarks: list[object],
    benchmark_type: str,
    benchmark_key: str | None,
) -> object | None:
    if not benchmark_key:
        return None
    normalized_key = benchmark_key.strip().lower()
    for benchmark in benchmarks:
        if (
            getattr(benchmark, "benchmark_type", "") == benchmark_type
            and getattr(benchmark, "benchmark_key", "").strip().lower() == normalized_key
        ):
            return benchmark
    return None


def build_fundamental_benchmark_report(
    config: AppConfig,
    ticker: str | None = None,
) -> str:
    from .storage import fundamental_comparison_statuses, list_fundamental_benchmark_snapshots

    status = fundamental_benchmark_status(config)
    requested_ticker = normalize_ticker(ticker) if ticker else None
    comparisons = [
        row
        for row in fundamental_comparison_statuses(config.database_path)
        if row.comparison_date and (requested_ticker is None or row.ticker == requested_ticker)
    ]
    benchmarks = list_fundamental_benchmark_snapshots(config.database_path)
    if requested_ticker:
        row = comparisons[0] if comparisons else None
        if row is None:
            return "\n".join(
                [
                    f"# Fundamental Benchmark Report: {requested_ticker}",
                    "",
                    "No benchmark comparison row is available for this ticker.",
                    "Run `compute-fundamental-benchmarks` after price, fundamentals, estimates, targets, and scores are available.",
                ]
            )
        sector_snapshot = _latest_benchmark_by_key(benchmarks, "sector", row.sector)
        industry_snapshot = _latest_benchmark_by_key(benchmarks, "industry", row.industry)
        overall_snapshot = _latest_benchmark_by_key(benchmarks, "overall", "scoreable_equities")
        lines = [
            f"# Fundamental Benchmark Report: {requested_ticker}",
            "",
            f"- Latest comparison date: `{row.comparison_date or 'none'}`",
            f"- Sector: `{row.sector or 'unknown'}`",
            f"- Industry: `{row.industry or 'unknown'}`",
            f"- Sector benchmark ETF: `{row.sector_benchmark_ticker or 'missing'}`",
            f"- Overall peers: `{row.overall_peer_count}`",
            f"- Sector peers: `{row.sector_peer_count}`",
            f"- Industry peers: `{row.industry_peer_count}`",
            f"- Benchmark status: `{row.benchmark_status or 'none'}`",
            f"- Warnings: `{row.data_warnings or 'none'}`",
            "",
            "## Valuation And Fundamentals",
            "",
            "| Metric | Ticker | Overall Median | Sector Median | Industry Median |",
            "|---|---:|---:|---:|---:|",
            "| Forward P/E | "
            f"{_format_number(row.forward_pe)} | "
            f"{_format_number(row.overall_forward_pe_median)} | "
            f"{_format_number(row.sector_forward_pe_median)} | "
            f"{_format_number(getattr(industry_snapshot, 'forward_pe_median', None))} |",
            "| EV/EBITDA | "
            f"{_format_number(row.ev_ebitda)} | "
            f"{_format_number(getattr(overall_snapshot, 'ev_ebitda_median', None))} | "
            f"{_format_number(row.sector_ev_ebitda_median)} | "
            f"{_format_number(getattr(industry_snapshot, 'ev_ebitda_median', None))} |",
            "| P/FCF | "
            f"{_format_number(row.p_fcf)} | "
            f"{_format_number(getattr(overall_snapshot, 'p_fcf_median', None))} | "
            f"{_format_number(row.sector_p_fcf_median)} | "
            f"{_format_number(getattr(industry_snapshot, 'p_fcf_median', None))} |",
            "| Net Margin | "
            f"{_format_percent(row.net_margin)} | "
            f"{_format_percent(getattr(overall_snapshot, 'net_margin_median', None))} | "
            f"{_format_percent(row.sector_net_margin_median)} | "
            f"{_format_percent(getattr(industry_snapshot, 'net_margin_median', None))} |",
            "| Revenue Growth | "
            f"{_format_percent(row.revenue_growth)} | "
            f"{_format_percent(getattr(overall_snapshot, 'revenue_growth_median', None))} | "
            f"{_format_percent(row.sector_revenue_growth_median)} | "
            f"{_format_percent(getattr(industry_snapshot, 'revenue_growth_median', None))} |",
            "| Net Debt / EBITDA | "
            f"{_format_number(row.net_debt_ebitda)} | "
            f"{_format_number(getattr(overall_snapshot, 'net_debt_ebitda_median', None))} | "
            f"{_format_number(row.sector_net_debt_ebitda_median)} | "
            f"{_format_number(getattr(industry_snapshot, 'net_debt_ebitda_median', None))} |",
            "| Opportunity Score | "
            f"{_format_number(row.opportunity_score)} | "
            f"{_format_number(getattr(overall_snapshot, 'opportunity_score_median', None))} | "
            f"{_format_number(row.sector_opportunity_score_median)} | "
            f"{_format_number(getattr(industry_snapshot, 'opportunity_score_median', None))} |",
            "",
            "## Relative Comparison",
            "",
            f"- Sector forward P/E discount: `{_format_percent(row.sector_forward_pe_discount_pct)}`",
            f"- Sector forward P/E percentile: `{_format_percent(row.sector_forward_pe_percentile)}`",
            f"- Relative strength vs SPY: `{_format_percent(row.relative_strength_vs_spy)}`",
            f"- Relative strength vs QQQ: `{_format_percent(row.relative_strength_vs_qqq)}`",
            f"- Relative strength vs sector ETF: `{_format_percent(row.relative_strength_vs_sector)}`",
        ]
        if sector_snapshot:
            lines.append(
                f"- Sector benchmark warnings: `{getattr(sector_snapshot, 'data_warnings', None) or 'none'}`"
            )
        return "\n".join(lines)

    lines = [
        "# Fundamental Benchmark Report",
        "",
        f"- Latest comparison date: `{status.latest_comparison_date or 'none'}`",
        f"- Compared scoreable equities: `{status.compared_ticker_count}/{status.scoreable_ticker_count}`",
        f"- Benchmark snapshot rows: `{status.benchmark_snapshot_count}`",
        f"- Missing benchmark prices: `{', '.join(status.missing_sector_benchmark_price_tickers) if status.missing_sector_benchmark_price_tickers else 'none'}`",
        "",
        "## Benchmark Medians",
        "",
        "| Type | Key | Count | Fwd P/E | EV/EBITDA | Net Margin | Score | Warnings |",
        "|---|---:|---:|---:|---:|---:|---:|---|",
    ]
    for benchmark in benchmarks[:50]:
        lines.append(
            "| "
            f"{benchmark.benchmark_type} | {benchmark.benchmark_key} | "
            f"{benchmark.ticker_count} | {_format_number(benchmark.forward_pe_median)} | "
            f"{_format_number(benchmark.ev_ebitda_median)} | "
            f"{_format_percent(benchmark.net_margin_median)} | "
            f"{_format_number(benchmark.opportunity_score_median)} | "
            f"{benchmark.data_warnings or ''} |"
        )
    lines.extend(
        [
            "",
            "## Ticker Comparisons",
            "",
            "| Ticker | Sector | Peers | Fwd P/E | Sector Median | Sector Discount | RS vs SPY | RS vs Sector | Status | Warnings |",
            "|---|---|---:|---:|---:|---:|---:|---:|---|---|",
        ]
    )
    for row in sorted(comparisons, key=lambda item: item.ticker):
        lines.append(
            "| "
            f"{row.ticker} | {row.sector or ''} | {row.sector_peer_count} | "
            f"{_format_number(row.forward_pe)} | {_format_number(row.sector_forward_pe_median)} | "
            f"{_format_percent(row.sector_forward_pe_discount_pct)} | "
            f"{_format_percent(row.relative_strength_vs_spy)} | "
            f"{_format_percent(row.relative_strength_vs_sector)} | "
            f"{row.benchmark_status or ''} | {row.data_warnings or ''} |"
        )
    return "\n".join(lines)


def _format_number(value: float | None) -> str:
    return "" if value is None else f"{value:.2f}"


def _format_percent(value: float | None) -> str:
    return "" if value is None else f"{value:.1%}"
