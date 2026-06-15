from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import UTC, date, datetime
import json
import os
from pathlib import Path
from urllib.error import URLError
from urllib.request import Request, urlopen

from .config import AppConfig
from .fundamental_benchmarks import read_sector_benchmarks
from .sec_fundamentals import load_cik_map
from .storage import (
    Asset,
    AssetChangeEvent,
    EtfFeature,
    Estimate,
    FundamentalComparisonSnapshot,
    OptionChainSnapshot,
    fundamental_comparison_statuses,
    insert_asset_change_event,
    is_scoreable_asset,
    latest_asset,
    latest_etf_feature,
    latest_estimate,
    latest_price_feature,
    latest_range_snapshot,
    list_option_chain_snapshots,
    list_stored_option_income_reviews,
    list_fundamentals,
    list_scores,
    list_targets,
    normalize_asset_role,
    normalize_ticker,
    upsert_asset,
)
from .watchlist import upsert_watchlist_asset


SEC_COMPANY_TICKERS_EXCHANGE_URL = "https://www.sec.gov/files/company_tickers_exchange.json"
FMP_PROFILE_URL = "https://financialmodelingprep.com/api/v3/profile/{ticker}?apikey={api_key}"
FOREIGN_EQUITY_IDENTITY_SOURCE = "research_foreign_equity_identity"
FOREIGN_EQUITY_IDENTITY_HEADERS = (
    "ticker",
    "name",
    "exchange",
    "currency",
    "country",
    "sector",
    "industry",
    "isin",
    "source",
    "source_url",
    "as_of_date",
    "effective_date",
    "notes",
)


@dataclass(frozen=True)
class ResearchTickerMetadata:
    ticker: str
    name: str | None = None
    cik: str | None = None
    exchange: str | None = None
    currency: str = "USD"
    sector: str | None = None
    industry: str | None = None
    country: str = "US"
    isin: str | None = None
    source_url: str | None = None
    sources: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class ResearchTickerPlan:
    ticker: str
    metadata: ResearchTickerMetadata
    existing_asset: Asset | None
    asset_type: str
    research_path: str
    apply_ready: bool
    blocked_reason: str | None
    readiness_blockers: tuple[str, ...]
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class ResearchTickerApplyResult:
    ticker: str
    dry_run: bool
    applied: bool
    blocked_reason: str | None
    warnings: tuple[str, ...]
    asset_type: str = "equity"
    research_path: str = "equity"
    readiness_blockers: tuple[str, ...] = ()


@dataclass(frozen=True)
class ResearchTickerStatus:
    ticker: str
    asset: Asset | None
    asset_type: str | None
    cik: str | None
    price_available: bool
    fundamental_count: int
    estimate_available: bool
    target_available: bool
    score_available: bool
    comparison: FundamentalComparisonSnapshot | None
    readiness_blockers: tuple[str, ...]
    etf_feature_available: bool = False
    etf_nav_available: bool = False
    range_available: bool = False
    option_chain_available: bool = False
    foreign_identity_available: bool = False
    foreign_identity_isin: str | None = None
    foreign_identity_source_url: str | None = None


@dataclass(frozen=True)
class EtfStrategyAlternative:
    key: str
    label: str
    status: str
    score: float | None = None
    action: str | None = None
    current_price: float | None = None
    target_price: float | None = None
    nav_per_share: float | None = None
    nav_gap: float | None = None
    option_expiration: str | None = None
    option_strike: float | None = None
    premium: float | None = None
    breakeven: float | None = None
    max_loss: float | None = None
    premium_yield: float | None = None
    annualized_yield: float | None = None
    downside_buffer_pct: float | None = None
    assignment_notional: float | None = None
    source: str | None = None
    blockers: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class EtfStrategyReview:
    ticker: str
    asset_type: str | None
    decision: str
    share: EtfStrategyAlternative
    long_call: EtfStrategyAlternative
    sell_put: EtfStrategyAlternative
    warnings: tuple[str, ...] = ()


def _resolve_project_path(config: AppConfig, path: Path) -> Path:
    return path if path.is_absolute() else config.project_root / path


def _clean(value: object) -> str | None:
    if value is None:
        return None
    cleaned = str(value).strip()
    return cleaned or None


def _clean_cik(value: object) -> str | None:
    cleaned = _clean(value)
    if not cleaned:
        return None
    return cleaned.zfill(10)


def _clean_isin(value: object) -> str | None:
    cleaned = _clean(value)
    if not cleaned:
        return None
    return cleaned.upper().replace(" ", "")


def _foreign_identity_path(config: AppConfig) -> Path:
    return _resolve_project_path(config, config.foreign_equity_identity_path)


def ensure_foreign_equity_identity_csv(path: Path) -> None:
    if path.exists():
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as output_file:
        writer = csv.DictWriter(output_file, fieldnames=FOREIGN_EQUITY_IDENTITY_HEADERS)
        writer.writeheader()


def _read_foreign_equity_identity_rows(config: AppConfig) -> list[dict[str, str]]:
    path = _foreign_identity_path(config)
    ensure_foreign_equity_identity_csv(path)
    with path.open("r", encoding="utf-8-sig", newline="") as input_file:
        return [dict(row) for row in csv.DictReader(input_file)]


def _foreign_equity_identity_row(config: AppConfig, ticker: str) -> dict[str, str] | None:
    normalized = normalize_ticker(ticker)
    for row in _read_foreign_equity_identity_rows(config):
        if normalize_ticker(row.get("ticker", "")) == normalized:
            return row
    return None


def _foreign_identity_source_label(row: dict[str, str]) -> str:
    return _clean(row.get("source")) or FOREIGN_EQUITY_IDENTITY_SOURCE


def _foreign_identity_blockers(row: dict[str, str] | None) -> tuple[str, ...]:
    if row is None:
        return ("missing_foreign_equity_identity_row",)
    blockers: list[str] = []
    required = (
        "name",
        "exchange",
        "currency",
        "country",
        "sector",
        "industry",
        "isin",
        "source",
        "source_url",
        "as_of_date",
        "effective_date",
    )
    for field in required:
        if not _clean(row.get(field)):
            blockers.append(f"missing_{field}")
    isin = _clean_isin(row.get("isin"))
    if isin and len(isin) != 12:
        blockers.append("invalid_isin")
    source_url = _clean(row.get("source_url"))
    if source_url and not source_url.lower().startswith(("http://", "https://")):
        blockers.append("invalid_source_url")
    return tuple(dict.fromkeys(blockers))


def _metadata_cache_path(config: AppConfig) -> Path:
    return _resolve_project_path(config, config.fundamental_cache_dir) / "sec_company_tickers_exchange.json"


def _load_or_fetch_sec_company_tickers(
    config: AppConfig,
    *,
    refresh_metadata: bool = False,
) -> dict[str, object]:
    path = _metadata_cache_path(config)
    if path.exists() and not refresh_metadata:
        return json.loads(path.read_text(encoding="utf-8"))
    request = Request(
        SEC_COMPANY_TICKERS_EXCHANGE_URL,
        headers={"User-Agent": config.sec_user_agent, "Accept": "application/json"},
    )
    with urlopen(request, timeout=30) as response:
        payload = json.loads(response.read().decode("utf-8"))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return payload


def _sec_metadata_for_ticker(
    payload: dict[str, object],
    ticker: str,
) -> ResearchTickerMetadata | None:
    normalized = normalize_ticker(ticker)
    fields = payload.get("fields")
    data = payload.get("data")
    if isinstance(fields, list) and isinstance(data, list):
        field_lookup = {str(field).strip().lower(): index for index, field in enumerate(fields)}
        ticker_index = field_lookup.get("ticker")
        cik_index = field_lookup["cik"] if "cik" in field_lookup else field_lookup.get("cik_str")
        name_index = field_lookup["name"] if "name" in field_lookup else field_lookup.get("title")
        exchange_index = field_lookup.get("exchange")
        if ticker_index is not None:
            for row in data:
                if not isinstance(row, list) or ticker_index >= len(row):
                    continue
                if normalize_ticker(str(row[ticker_index])) != normalized:
                    continue
                return ResearchTickerMetadata(
                    ticker=normalized,
                    name=_clean(row[name_index]) if name_index is not None and name_index < len(row) else None,
                    cik=(
                        _clean_cik(row[cik_index])
                        if cik_index is not None and cik_index < len(row)
                        else None
                    ),
                    exchange=(
                        _clean(row[exchange_index])
                        if exchange_index is not None and exchange_index < len(row)
                        else None
                    ),
                    sources=("sec_company_tickers_exchange",),
                )

    for value in payload.values():
        if not isinstance(value, dict):
            continue
        row_ticker = _clean(value.get("ticker"))
        if row_ticker and normalize_ticker(row_ticker) == normalized:
            return ResearchTickerMetadata(
                ticker=normalized,
                name=_clean(value.get("title") or value.get("name")),
                cik=_clean_cik(value.get("cik_str") or value.get("cik")),
                sources=("sec_company_tickers",),
            )
    return None


def _fmp_key() -> str | None:
    return os.environ.get("FMP_API_KEY") or os.environ.get("FINANCIAL_MODELING_PREP_API_KEY")


def _fetch_fmp_profile(ticker: str) -> tuple[dict[str, object] | None, tuple[str, ...]]:
    key = _fmp_key()
    if not key:
        return None, ("missing_profile_api_key",)
    url = FMP_PROFILE_URL.format(ticker=normalize_ticker(ticker), api_key=key)
    request = Request(url, headers={"Accept": "application/json"})
    try:
        with urlopen(request, timeout=20) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (OSError, URLError, json.JSONDecodeError) as error:
        return None, (f"profile_provider_failed:{type(error).__name__}",)
    if not isinstance(payload, list) or not payload:
        return None, ("profile_provider_empty",)
    first = payload[0]
    if not isinstance(first, dict):
        return None, ("profile_provider_malformed",)
    return first, ()


def _metadata_from_profile(ticker: str, profile: dict[str, object]) -> ResearchTickerMetadata:
    return ResearchTickerMetadata(
        ticker=normalize_ticker(ticker),
        name=_clean(profile.get("companyName") or profile.get("company_name") or profile.get("name")),
        exchange=_clean(profile.get("exchangeShortName") or profile.get("exchange")),
        currency=_clean(profile.get("currency")) or "USD",
        sector=_clean(profile.get("sector")),
        industry=_clean(profile.get("industry")),
        country=_clean(profile.get("country")) or "US",
        sources=("fmp_profile",),
    )


def _merge_sources(*values: tuple[str, ...]) -> tuple[str, ...]:
    ordered: list[str] = []
    for group in values:
        for value in group:
            if value and value not in ordered:
                ordered.append(value)
    return tuple(ordered)


def _merge_warnings(*values: tuple[str, ...]) -> tuple[str, ...]:
    ordered: list[str] = []
    for group in values:
        for value in group:
            if value and value not in ordered:
                ordered.append(value)
    return tuple(ordered)


def resolve_research_ticker_metadata(
    config: AppConfig,
    ticker: str,
    *,
    refresh_metadata: bool = False,
    name: str | None = None,
    sector: str | None = None,
    industry: str | None = None,
    cik: str | None = None,
    exchange: str | None = None,
    currency: str | None = None,
    country: str | None = None,
) -> ResearchTickerMetadata:
    normalized = normalize_ticker(ticker)
    warnings: list[str] = []
    sec = None
    try:
        sec_payload = _load_or_fetch_sec_company_tickers(
            config,
            refresh_metadata=refresh_metadata,
        )
        sec = _sec_metadata_for_ticker(sec_payload, normalized)
    except (OSError, URLError, json.JSONDecodeError, ValueError) as error:
        warnings.append(f"sec_metadata_failed:{type(error).__name__}")
    if sec is None:
        warnings.append("sec_ticker_not_found")
        sec = ResearchTickerMetadata(ticker=normalized)

    profile_payload, profile_warnings = _fetch_fmp_profile(normalized)
    profile = _metadata_from_profile(normalized, profile_payload) if profile_payload else None
    warnings.extend(profile_warnings)
    if profile is None:
        profile = ResearchTickerMetadata(ticker=normalized)

    resolved = ResearchTickerMetadata(
        ticker=normalized,
        name=_clean(name) or sec.name or profile.name,
        cik=_clean_cik(cik) or sec.cik,
        exchange=_clean(exchange) or profile.exchange or sec.exchange,
        currency=_clean(currency) or profile.currency or sec.currency or "USD",
        sector=_clean(sector) or profile.sector,
        industry=_clean(industry) or profile.industry,
        country=_clean(country) or profile.country or "US",
        isin=None,
        source_url=None,
        sources=_merge_sources(sec.sources, profile.sources, ("manual_override",) if any((name, sector, industry, cik, exchange, currency, country)) else ()),
        warnings=_merge_warnings(tuple(warnings), sec.warnings, profile.warnings),
    )
    final_warnings = list(resolved.warnings)
    if not resolved.cik:
        final_warnings.append("missing_cik")
    if not resolved.sector:
        final_warnings.append("missing_sector")
    if not resolved.industry:
        final_warnings.append("missing_industry")
    if not resolved.exchange:
        final_warnings.append("missing_exchange")
    return ResearchTickerMetadata(
        ticker=resolved.ticker,
        name=resolved.name,
        cik=resolved.cik,
        exchange=resolved.exchange,
        currency=resolved.currency,
        sector=resolved.sector,
        industry=resolved.industry,
        country=resolved.country,
        isin=resolved.isin,
        source_url=resolved.source_url,
        sources=resolved.sources,
        warnings=_merge_warnings(tuple(final_warnings)),
    )


def resolve_foreign_equity_research_metadata(
    config: AppConfig,
    ticker: str,
    *,
    name: str | None = None,
    sector: str | None = None,
    industry: str | None = None,
    cik: str | None = None,
    exchange: str | None = None,
    currency: str | None = None,
    country: str | None = None,
) -> tuple[ResearchTickerMetadata, tuple[str, ...]]:
    normalized = normalize_ticker(ticker)
    row = _foreign_equity_identity_row(config, normalized)
    blockers = _foreign_identity_blockers(row)
    if row is None:
        metadata = ResearchTickerMetadata(
            ticker=normalized,
            name=_clean(name),
            cik=_clean_cik(cik),
            exchange=_clean(exchange),
            currency=_clean(currency) or "USD",
            sector=_clean(sector),
            industry=_clean(industry),
            country=_clean(country) or "US",
            sources=("manual_override",) if any((name, sector, industry, cik, exchange, currency, country)) else (),
            warnings=("missing_foreign_equity_identity_row",),
        )
        return metadata, blockers

    manual_override = any((name, sector, industry, cik, exchange, currency, country))
    source_label = _foreign_identity_source_label(row)
    warnings = tuple(f"foreign_identity:{blocker}" for blocker in blockers)
    metadata = ResearchTickerMetadata(
        ticker=normalized,
        name=_clean(name) or _clean(row.get("name")),
        cik=_clean_cik(cik),
        exchange=_clean(exchange) or _clean(row.get("exchange")),
        currency=_clean(currency) or _clean(row.get("currency")) or "USD",
        sector=_clean(sector) or _clean(row.get("sector")),
        industry=_clean(industry) or _clean(row.get("industry")),
        country=_clean(country) or _clean(row.get("country")) or "US",
        isin=_clean_isin(row.get("isin")),
        source_url=_clean(row.get("source_url")),
        sources=_merge_sources(
            (FOREIGN_EQUITY_IDENTITY_SOURCE, source_label),
            ("manual_override",) if manual_override else (),
        ),
        warnings=_merge_warnings(warnings),
    )
    return metadata, blockers


def _normalize_research_asset_type(value: object | None, existing: Asset | None = None) -> str:
    cleaned = _clean(value)
    if cleaned:
        normalized = cleaned.lower().replace("-", "_")
        if normalized in {"foreign_equity", "foreign", "non_us_equity", "non_us"}:
            return "foreign_equity"
        if normalized in {"etf", "fund"}:
            return "etf"
        return "equity"
    if existing and (existing.asset_type or "").strip().lower() == "etf":
        return "etf"
    return "equity"


def _resolve_etf_research_metadata(
    ticker: str,
    existing: Asset | None,
    *,
    name: str | None = None,
    sector: str | None = None,
    industry: str | None = None,
    cik: str | None = None,
    exchange: str | None = None,
    currency: str | None = None,
    country: str | None = None,
) -> ResearchTickerMetadata:
    normalized = normalize_ticker(ticker)
    manual_override = any((name, sector, industry, cik, exchange, currency, country))
    sources: tuple[str, ...] = ()
    if existing:
        sources = ("existing_asset",)
    if manual_override:
        sources = _merge_sources(sources, ("manual_override",))
    return ResearchTickerMetadata(
        ticker=normalized,
        name=_clean(name) or (existing.name if existing else None) or normalized,
        cik=_clean_cik(cik),
        exchange=_clean(exchange) or (existing.exchange if existing else None),
        currency=_clean(currency) or (existing.currency if existing else None) or "USD",
        sector=_clean(sector) or (existing.sector if existing else None),
        industry=_clean(industry) or (existing.industry if existing else None),
        country=_clean(country) or (existing.country if existing else None) or "US",
        sources=sources,
        warnings=(),
    )


def _latest_target(config: AppConfig, ticker: str):
    targets = list_targets(config.database_path, ticker)
    return targets[-1] if targets else None


def _latest_score(config: AppConfig, ticker: str):
    scores = list_scores(config.database_path, ticker)
    return scores[-1] if scores else None


def _warning_parts(value: str | None) -> tuple[str, ...]:
    if not value:
        return ()
    return tuple(part for part in (item.strip() for item in value.split(";")) if part)


def _etf_readiness_blockers(config: AppConfig, ticker: str) -> tuple[tuple[str, ...], tuple[str, ...]]:
    normalized = normalize_ticker(ticker)
    price = latest_price_feature(config.database_path, normalized)
    feature = latest_etf_feature(config.database_path, normalized)
    target = _latest_target(config, normalized)
    score = _latest_score(config, normalized)
    range_snapshot = latest_range_snapshot(config.database_path, normalized)
    option_rows = list_option_chain_snapshots(config.database_path, normalized)

    blockers: list[str] = []
    warnings: list[str] = []
    if price is None or price.current_price is None:
        blockers.append("missing_price_feature")
    if feature is None:
        blockers.append("missing_etf_feature")
    else:
        if feature.nav_per_share is None:
            blockers.append("missing_etf_nav")
        if feature.holdings_count is None or feature.holdings_count < config.etf_minimum_holdings:
            blockers.append("missing_or_insufficient_etf_holdings")
    if target is None or target.base_target is None:
        blockers.append("missing_target")
    else:
        warnings.extend(_warning_parts(target.data_warnings))
    if score is None or score.opportunity_score is None:
        blockers.append("missing_score")
    else:
        warnings.extend(_warning_parts(score.data_warnings))
    if range_snapshot is None:
        blockers.append("missing_range_snapshot")
    else:
        warnings.extend(_warning_parts(range_snapshot.data_warnings))
    if not option_rows:
        blockers.append("missing_option_chain")
    return _merge_warnings(tuple(blockers)), _merge_warnings(tuple(warnings))


def research_ticker_plan(
    config: AppConfig,
    ticker: str,
    *,
    asset_type: str | None = None,
    refresh_metadata: bool = False,
    name: str | None = None,
    sector: str | None = None,
    industry: str | None = None,
    cik: str | None = None,
    exchange: str | None = None,
    currency: str | None = None,
    country: str | None = None,
) -> ResearchTickerPlan:
    normalized = normalize_ticker(ticker)
    existing = latest_asset(config.database_path, normalized)
    effective_asset_type = _normalize_research_asset_type(asset_type, existing)
    if asset_type is None and effective_asset_type == "equity" and _foreign_equity_identity_row(config, normalized):
        effective_asset_type = "foreign_equity"
    if effective_asset_type == "etf":
        metadata = _resolve_etf_research_metadata(
            normalized,
            existing,
            name=name,
            sector=sector,
            industry=industry,
            cik=cik,
            exchange=exchange,
            currency=currency,
            country=country,
        )
        readiness_blockers, readiness_warnings = _etf_readiness_blockers(config, metadata.ticker)
        warnings = list(readiness_warnings)
        blocked_reason = None
        if existing is None:
            blocked_reason = "etf_reference_asset_required"
        elif (existing.asset_type or "").strip().lower() != "etf":
            blocked_reason = "ticker_is_not_etf"
        elif existing.active_flag != 1:
            blocked_reason = "etf_reference_asset_inactive"
        elif is_scoreable_asset(existing):
            blocked_reason = "ticker_already_scoreable"
        elif readiness_blockers:
            blocked_reason = "etf_readiness_required"
        return ResearchTickerPlan(
            ticker=metadata.ticker,
            metadata=metadata,
            existing_asset=existing,
            asset_type="etf",
            research_path="etf",
            apply_ready=blocked_reason is None,
            blocked_reason=blocked_reason,
            readiness_blockers=readiness_blockers,
            warnings=_merge_warnings(("etf_research_path", *tuple(warnings))),
        )

    if effective_asset_type == "foreign_equity":
        metadata, identity_blockers = resolve_foreign_equity_research_metadata(
            config,
            normalized,
            name=name,
            sector=sector,
            industry=industry,
            cik=cik,
            exchange=exchange,
            currency=currency,
            country=country,
        )
        warnings = list(metadata.warnings)
        blocked_reason = None
        if existing and is_scoreable_asset(existing):
            blocked_reason = "ticker_already_scoreable"
        elif existing and (existing.asset_type or "").strip().lower() not in {"", "equity"}:
            blocked_reason = "ticker_is_not_equity"
        elif identity_blockers:
            blocked_reason = "foreign_equity_identity_required"
        elif not metadata.sector:
            blocked_reason = "missing_sector"
        elif not metadata.industry:
            blocked_reason = "missing_industry"
        elif metadata.sector.strip().lower() not in read_sector_benchmarks(config):
            warnings.append("missing_sector_benchmark_mapping")
        return ResearchTickerPlan(
            ticker=metadata.ticker,
            metadata=metadata,
            existing_asset=existing,
            asset_type="foreign_equity",
            research_path="foreign_equity",
            apply_ready=blocked_reason is None,
            blocked_reason=blocked_reason,
            readiness_blockers=identity_blockers,
            warnings=_merge_warnings(("foreign_equity_research_path", *tuple(warnings))),
        )

    metadata = resolve_research_ticker_metadata(
        config,
        normalized,
        refresh_metadata=refresh_metadata,
        name=name,
        sector=sector,
        industry=industry,
        cik=cik,
        exchange=exchange,
        currency=currency,
        country=country,
    )
    existing = latest_asset(config.database_path, metadata.ticker)
    warnings = list(metadata.warnings)
    blocked_reason = None
    if existing and is_scoreable_asset(existing):
        blocked_reason = "ticker_already_scoreable"
    elif not metadata.cik:
        blocked_reason = "missing_cik"
    elif not metadata.sector:
        blocked_reason = "missing_sector"
    elif not metadata.industry:
        blocked_reason = "missing_industry"
    elif metadata.sector.strip().lower() not in read_sector_benchmarks(config):
        warnings.append("missing_sector_benchmark_mapping")
    return ResearchTickerPlan(
        ticker=metadata.ticker,
        metadata=metadata,
        existing_asset=existing,
        asset_type="equity",
        research_path="equity",
        apply_ready=blocked_reason is None,
        blocked_reason=blocked_reason,
        readiness_blockers=(),
        warnings=_merge_warnings(tuple(warnings)),
    )


def _upsert_cik(path: Path, ticker: str, cik: str | None) -> None:
    cleaned = _clean_cik(cik)
    if not cleaned:
        return
    normalized = normalize_ticker(ticker)
    rows: list[dict[str, str]] = []
    if path.exists():
        with path.open("r", encoding="utf-8-sig", newline="") as input_file:
            rows = [dict(row) for row in csv.DictReader(input_file)]
    updated = False
    for row in rows:
        if normalize_ticker(row.get("ticker", "")) == normalized:
            row["cik"] = cleaned
            updated = True
            break
    if not updated:
        rows.append({"ticker": normalized, "cik": cleaned})
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", encoding="utf-8", newline="") as output_file:
        writer = csv.DictWriter(output_file, fieldnames=("ticker", "cik"))
        writer.writeheader()
        for row in sorted(rows, key=lambda item: normalize_ticker(item.get("ticker", ""))):
            writer.writerow({"ticker": normalize_ticker(row.get("ticker", "")), "cik": row.get("cik", "")})


def apply_research_ticker(
    config: AppConfig,
    ticker: str,
    *,
    asset_type: str | None = None,
    confirm: bool = False,
    refresh_metadata: bool = False,
    name: str | None = None,
    sector: str | None = None,
    industry: str | None = None,
    cik: str | None = None,
    exchange: str | None = None,
    currency: str | None = None,
    country: str | None = None,
) -> ResearchTickerApplyResult:
    plan = research_ticker_plan(
        config,
        ticker,
        asset_type=asset_type,
        refresh_metadata=refresh_metadata,
        name=name,
        sector=sector,
        industry=industry,
        cik=cik,
        exchange=exchange,
        currency=currency,
        country=country,
    )
    if plan.blocked_reason == "ticker_already_scoreable":
        return ResearchTickerApplyResult(
            ticker=plan.ticker,
            dry_run=not confirm,
            applied=False,
            blocked_reason=None,
            warnings=("ticker_already_scoreable",),
            asset_type=plan.asset_type,
            research_path=plan.research_path,
            readiness_blockers=plan.readiness_blockers,
        )
    if not plan.apply_ready:
        return ResearchTickerApplyResult(
            ticker=plan.ticker,
            dry_run=not confirm,
            applied=False,
            blocked_reason=plan.blocked_reason,
            warnings=plan.warnings,
            asset_type=plan.asset_type,
            research_path=plan.research_path,
            readiness_blockers=plan.readiness_blockers,
        )
    if not confirm:
        return ResearchTickerApplyResult(
            ticker=plan.ticker,
            dry_run=True,
            applied=False,
            blocked_reason=None,
            warnings=plan.warnings,
            asset_type=plan.asset_type,
            research_path=plan.research_path,
            readiness_blockers=plan.readiness_blockers,
        )

    metadata = plan.metadata
    previous = plan.existing_asset
    timestamp = datetime.now(UTC).replace(microsecond=0).isoformat()
    if plan.asset_type == "etf":
        source = "phase13b_etf_research_ticker"
        stored_asset_type = "etf"
    elif plan.asset_type == "foreign_equity":
        source = FOREIGN_EQUITY_IDENTITY_SOURCE
        stored_asset_type = "equity"
    else:
        source = "phase13b_research_ticker"
        stored_asset_type = "equity"
    asset = Asset(
        ticker=metadata.ticker,
        name=metadata.name or metadata.ticker,
        asset_type=stored_asset_type,
        exchange=metadata.exchange,
        currency=metadata.currency,
        sector=metadata.sector,
        industry=metadata.industry,
        country=metadata.country,
        active_flag=1,
        asset_role="scoreable",
        source=source,
        as_of_date=date.today().isoformat(),
        effective_date=timestamp,
    )
    upsert_watchlist_asset(config.watchlist_path, asset)
    upsert_asset(config.database_path, asset)
    if plan.asset_type == "equity":
        _upsert_cik(config.cik_map_path, asset.ticker, metadata.cik)
    insert_asset_change_event(
        config.database_path,
        AssetChangeEvent(
            event_timestamp=timestamp,
            ticker=asset.ticker,
            event_type="research_ticker_apply",
            previous_active_flag=previous.active_flag if previous else None,
            new_active_flag=1,
            reason=source,
            details=(
                f"asset_type={plan.asset_type};asset_role=scoreable;"
                f"research_path={plan.research_path};sources={','.join(metadata.sources)}"
            ),
            source=source,
            as_of_date=asset.as_of_date,
            effective_date=asset.effective_date,
        ),
    )
    return ResearchTickerApplyResult(
        ticker=asset.ticker,
        dry_run=False,
        applied=True,
        blocked_reason=None,
        warnings=plan.warnings,
        asset_type=plan.asset_type,
        research_path=plan.research_path,
        readiness_blockers=plan.readiness_blockers,
    )


def _is_source_backed_foreign_equity_asset(asset: Asset | None) -> bool:
    if asset is None:
        return False
    return (
        (asset.asset_type or "equity").strip().lower() == "equity"
        and (asset.source or "").strip() == FOREIGN_EQUITY_IDENTITY_SOURCE
    )


def research_ticker_status(config: AppConfig, ticker: str) -> ResearchTickerStatus:
    normalized = normalize_ticker(ticker)
    asset = latest_asset(config.database_path, normalized)
    asset_type = (asset.asset_type or "equity").strip().lower() if asset else None
    cik = load_cik_map(config.cik_map_path).get(normalized)
    foreign_metadata, foreign_blockers = resolve_foreign_equity_research_metadata(config, normalized)
    foreign_identity_available = not foreign_blockers
    price = latest_price_feature(config.database_path, normalized)
    fundamentals = list_fundamentals(config.database_path, normalized)
    estimate: Estimate | None = latest_estimate(config.database_path, normalized, "eps")
    targets = list_targets(config.database_path, normalized)
    scores = list_scores(config.database_path, normalized)
    etf_feature = latest_etf_feature(config.database_path, normalized)
    range_snapshot = latest_range_snapshot(config.database_path, normalized)
    option_rows = list_option_chain_snapshots(config.database_path, normalized)
    comparisons = [
        row
        for row in fundamental_comparison_statuses(config.database_path, normalized)
        if row.ticker == normalized
    ]
    comparison = comparisons[0] if comparisons else None
    blockers: list[str] = []
    if asset is None:
        blockers.append("asset_not_added")
    elif normalize_asset_role(asset.asset_role) != "scoreable" or asset.active_flag != 1:
        blockers.append("not_active_scoreable")
    if asset_type == "etf":
        etf_blockers, etf_warnings = _etf_readiness_blockers(config, normalized)
        blockers.extend(etf_blockers)
        blockers.extend(etf_warnings)
    else:
        if (
            asset
            and asset_type == "equity"
            and not cik
            and not foreign_identity_available
            and not _is_source_backed_foreign_equity_asset(asset)
        ):
            blockers.append("missing_cik")
        if not fundamentals:
            blockers.append("missing_fundamentals")
        if estimate is None:
            blockers.append("missing_forward_eps_estimate")
        if comparison is None or not comparison.comparison_date:
            blockers.append("missing_benchmark_comparison")
        if comparison and comparison.data_warnings:
            blockers.extend(part for part in comparison.data_warnings.split(";") if part)
    if price is None or price.current_price is None:
        blockers.append("missing_price_feature")
    if not targets:
        blockers.append("missing_target")
    if not scores:
        blockers.append("missing_score")
    return ResearchTickerStatus(
        ticker=normalized,
        asset=asset,
        asset_type=asset_type,
        cik=cik,
        price_available=price is not None,
        fundamental_count=len(fundamentals),
        estimate_available=estimate is not None,
        target_available=bool(targets),
        score_available=bool(scores),
        comparison=comparison,
        readiness_blockers=_merge_warnings(tuple(blockers)),
        etf_feature_available=etf_feature is not None,
        etf_nav_available=etf_feature is not None and etf_feature.nav_per_share is not None,
        range_available=range_snapshot is not None,
        option_chain_available=bool(option_rows),
        foreign_identity_available=foreign_identity_available,
        foreign_identity_isin=foreign_metadata.isin,
        foreign_identity_source_url=foreign_metadata.source_url,
    )


def refresh_research_ticker(config: AppConfig, ticker: str):
    status = research_ticker_status(config, ticker)
    if status.asset is None or not is_scoreable_asset(status.asset):
        return None, ("ticker_not_scoreable",)
    from .pipeline import run_refresh_data

    result = run_refresh_data(config, ticker=status.ticker, daily=True)
    refreshed_status = research_ticker_status(config, status.ticker)
    return result, refreshed_status.readiness_blockers


def _option_mid(option: OptionChainSnapshot) -> float | None:
    if option.mark is not None and option.mark > 0:
        return option.mark
    if option.bid is not None and option.ask is not None and option.bid >= 0 and option.ask > 0:
        return (option.bid + option.ask) / 2
    if option.last is not None and option.last > 0:
        return option.last
    return None


def _option_spread_warning(option: OptionChainSnapshot, premium: float | None) -> tuple[str, ...]:
    if premium is None or premium <= 0:
        return ("missing_option_premium",)
    warnings: list[str] = []
    spread = option.ask - option.bid
    if spread > 0 and spread / premium > 0.25:
        warnings.append("wide_option_spread")
    if option.open_interest is None or option.open_interest < 10:
        warnings.append("low_option_open_interest")
    if option.volume is None or option.volume < 1:
        warnings.append("low_option_volume")
    return tuple(warnings)


def _etf_share_review(
    config: AppConfig,
    ticker: str,
    feature: EtfFeature | None,
) -> EtfStrategyAlternative:
    price = latest_price_feature(config.database_path, ticker)
    target = _latest_target(config, ticker)
    score = _latest_score(config, ticker)
    range_snapshot = latest_range_snapshot(config.database_path, ticker)
    blockers: list[str] = []
    warnings: list[str] = []
    current_price = price.current_price if price else None
    target_price = target.base_target if target else None
    if current_price is None:
        blockers.append("missing_price_feature")
    if feature is None or feature.nav_per_share is None:
        blockers.append("etf_data_required")
    if target_price is None:
        blockers.append("missing_target")
    if score is None or score.opportunity_score is None:
        blockers.append("missing_score")
    if range_snapshot is None:
        blockers.append("missing_range_snapshot")
    else:
        warnings.extend(_warning_parts(range_snapshot.reason_codes))
        warnings.extend(_warning_parts(range_snapshot.data_warnings))
    if blockers:
        return EtfStrategyAlternative(
            key="share",
            label="ETF shares",
            status="blocked",
            action="insufficient_data",
            current_price=current_price,
            target_price=target_price,
            nav_per_share=feature.nav_per_share if feature else None,
            nav_gap=range_snapshot.etf_nav_gap if range_snapshot else None,
            blockers=_merge_warnings(tuple(blockers)),
            warnings=_merge_warnings(tuple(warnings)),
        )
    assert current_price is not None
    assert target_price is not None
    nav_gap = range_snapshot.etf_nav_gap if range_snapshot else None
    if nav_gap is None and feature and feature.nav_per_share is not None and current_price:
        nav_gap = (feature.nav_per_share - current_price) / current_price
    target_gap = (target_price - current_price) / current_price if current_price else 0.0
    raw_score = (score.opportunity_score if score else 50.0) + (target_gap * 25.0)
    if nav_gap is not None:
        raw_score += nav_gap * 20.0
    share_score = max(0.0, min(100.0, raw_score))
    action = "prefer_etf_shares" if share_score >= 60 else "wait_no_clean_entry"
    return EtfStrategyAlternative(
        key="share",
        label="ETF shares",
        status="available",
        score=share_score,
        action=action,
        current_price=current_price,
        target_price=target_price,
        nav_per_share=feature.nav_per_share if feature else None,
        nav_gap=nav_gap,
        source="stored_price_target_score_range_etf_feature",
        warnings=_merge_warnings(tuple(warnings)),
    )


def _etf_long_call_review(config: AppConfig, ticker: str) -> EtfStrategyAlternative:
    price = latest_price_feature(config.database_path, ticker)
    target = _latest_target(config, ticker)
    current_price = price.current_price if price else None
    target_price = target.base_target if target else None
    rows = [
        option
        for option in list_option_chain_snapshots(config.database_path, ticker)
        if (option.option_type or "").strip().lower() == "call"
    ]
    if not rows:
        return EtfStrategyAlternative(
            key="long_call",
            label="Long call",
            status="blocked",
            action="insufficient_data",
            current_price=current_price,
            target_price=target_price,
            blockers=("missing_call_option_chain",),
        )
    latest_timestamp = max(option.snapshot_timestamp for option in rows)
    latest_rows = [option for option in rows if option.snapshot_timestamp == latest_timestamp]
    if current_price is not None:
        otm_rows = [option for option in latest_rows if option.strike >= current_price]
        candidate_rows = otm_rows or latest_rows
        candidate_rows = sorted(
            candidate_rows,
            key=lambda option: (abs(option.strike - current_price), option.expiration_date, option.strike),
        )
    else:
        candidate_rows = sorted(latest_rows, key=lambda option: (option.expiration_date, option.strike))
    option = candidate_rows[0]
    premium = _option_mid(option)
    warnings = list(_option_spread_warning(option, premium))
    blockers: list[str] = []
    if current_price is None:
        blockers.append("missing_price_feature")
    if target_price is None:
        blockers.append("missing_target")
    if premium is None or premium <= 0:
        blockers.append("missing_call_option_premium")
    if blockers:
        return EtfStrategyAlternative(
            key="long_call",
            label="Long call",
            status="blocked",
            action="insufficient_data",
            current_price=current_price,
            target_price=target_price,
            option_expiration=option.expiration_date,
            option_strike=option.strike,
            premium=premium,
            blockers=_merge_warnings(tuple(blockers)),
            warnings=_merge_warnings(tuple(warnings)),
        )
    assert premium is not None
    assert target_price is not None
    breakeven = option.strike + premium
    intrinsic_at_target = max(target_price - option.strike, 0.0)
    target_profit = intrinsic_at_target - premium
    spread = max(option.ask - option.bid, 0.0)
    spread_penalty = (spread / premium) * 20.0 if premium else 0.0
    raw_score = 50.0 + (target_profit / premium * 20.0 if premium else 0.0) - spread_penalty
    call_score = max(0.0, min(100.0, raw_score))
    action = "prefer_long_call" if call_score >= 65 and target_profit > 0 else "wait_no_clean_entry"
    return EtfStrategyAlternative(
        key="long_call",
        label="Long call",
        status="available",
        score=call_score,
        action=action,
        current_price=current_price,
        target_price=target_price,
        option_expiration=option.expiration_date,
        option_strike=option.strike,
        premium=premium,
        breakeven=breakeven,
        max_loss=premium * 100.0,
        source=option.source,
        warnings=_merge_warnings(tuple(warnings)),
    )


def _etf_sell_put_review(config: AppConfig, ticker: str) -> EtfStrategyAlternative:
    reviews = [
        review
        for review in list_stored_option_income_reviews(config.database_path, ticker)
        if (review.option_type or "").strip().lower() == "put"
    ]
    if not reviews:
        return EtfStrategyAlternative(
            key="sell_put",
            label="Sell cash-secured put",
            status="blocked",
            action="insufficient_data",
            blockers=("missing_sell_put_review",),
        )
    latest_date = max(review.review_date for review in reviews)
    latest_reviews = [review for review in reviews if review.review_date == latest_date]
    review = sorted(
        latest_reviews,
        key=lambda item: (
            item.review_category != "eligible_watch",
            -(item.annualized_yield or 0.0),
            item.strike,
        ),
    )[0]
    warnings = _warning_parts(review.risk_warnings)
    if review.review_category != "eligible_watch":
        warnings = _merge_warnings((review.review_category, *warnings))
    raw_score = 50.0
    if review.annualized_yield is not None:
        raw_score += review.annualized_yield * 60.0
    if review.downside_buffer_pct is not None:
        raw_score += review.downside_buffer_pct * 40.0
    put_score = max(0.0, min(100.0, raw_score))
    action = (
        "prefer_sell_put"
        if review.review_category == "eligible_watch" and put_score >= 60
        else "wait_no_clean_entry"
    )
    return EtfStrategyAlternative(
        key="sell_put",
        label="Sell cash-secured put",
        status="available",
        score=put_score,
        action=action,
        current_price=review.current_price,
        option_expiration=review.expiration_date,
        option_strike=review.strike,
        premium=review.mid_premium,
        breakeven=review.breakeven,
        premium_yield=review.premium_yield,
        annualized_yield=review.annualized_yield,
        downside_buffer_pct=review.downside_buffer_pct,
        assignment_notional=review.assignment_notional,
        source=review.source,
        warnings=warnings,
    )


def etf_strategy_review(config: AppConfig, ticker: str) -> EtfStrategyReview:
    normalized = normalize_ticker(ticker)
    asset = latest_asset(config.database_path, normalized)
    asset_type = (asset.asset_type or "equity").strip().lower() if asset else None
    warnings: list[str] = []
    if asset is None:
        warnings.append("asset_not_found")
    elif asset_type != "etf":
        warnings.append("asset_is_not_etf")
    feature = latest_etf_feature(config.database_path, normalized)
    share = _etf_share_review(config, normalized, feature)
    long_call = _etf_long_call_review(config, normalized)
    sell_put = _etf_sell_put_review(config, normalized)
    alternatives = (share, long_call, sell_put)
    available = [
        alternative
        for alternative in alternatives
        if alternative.status == "available" and alternative.score is not None
    ]
    if not available:
        decision = "insufficient_data"
    else:
        best = max(available, key=lambda item: item.score or 0.0)
        decision = best.action or "wait_no_clean_entry"
        if decision.startswith("prefer_") and (best.score or 0.0) < 60.0:
            decision = "wait_no_clean_entry"
    return EtfStrategyReview(
        ticker=normalized,
        asset_type=asset_type,
        decision=decision,
        share=share,
        long_call=long_call,
        sell_put=sell_put,
        warnings=_merge_warnings(tuple(warnings)),
    )


def _format_bool(value: bool) -> str:
    return "yes" if value else "no"


def _format_percent(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"{value:.1%}"


def _format_number(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"{value:.2f}"


def build_research_ticker_plan_text(plan: ResearchTickerPlan) -> str:
    metadata = plan.metadata
    return "\n".join(
        [
            "Research ticker plan",
            f"Ticker: {plan.ticker}",
            f"Research path: {plan.research_path}",
            f"Asset type: {plan.asset_type}",
            f"Existing asset role: {plan.existing_asset.asset_role if plan.existing_asset else 'none'}",
            f"Apply ready: {plan.apply_ready}",
            f"Blocked reason: {plan.blocked_reason or 'none'}",
            "Readiness blockers: "
            + (", ".join(plan.readiness_blockers) if plan.readiness_blockers else "none"),
            f"Name: {metadata.name or 'unknown'}",
            f"CIK: {metadata.cik or 'missing'}",
            f"ISIN: {metadata.isin or 'missing'}",
            f"Exchange: {metadata.exchange or 'missing'}",
            f"Sector: {metadata.sector or 'missing'}",
            f"Industry: {metadata.industry or 'missing'}",
            f"Currency: {metadata.currency}",
            f"Country: {metadata.country}",
            f"Source URL: {metadata.source_url or 'missing'}",
            "Metadata sources: " + (", ".join(metadata.sources) if metadata.sources else "none"),
            "Warnings: " + (", ".join(plan.warnings) if plan.warnings else "none"),
        ]
    )


def build_research_ticker_apply_text(result: ResearchTickerApplyResult) -> str:
    mode = "dry-run" if result.dry_run else "confirmed"
    return "\n".join(
        [
            f"Research ticker apply ({mode})",
            f"Ticker: {result.ticker}",
            f"Applied: {result.applied}",
            f"Blocked reason: {result.blocked_reason or 'none'}",
            f"Research path: {result.research_path}",
            f"Asset type: {result.asset_type}",
            "Readiness blockers: "
            + (", ".join(result.readiness_blockers) if result.readiness_blockers else "none"),
            "Warnings: " + (", ".join(result.warnings) if result.warnings else "none"),
        ]
    )


def build_research_ticker_status_text(status: ResearchTickerStatus) -> str:
    comparison = status.comparison
    lines = [
        "Research ticker status",
        f"Ticker: {status.ticker}",
        f"Asset exists: {_format_bool(status.asset is not None)}",
        f"Asset role: {status.asset.asset_role if status.asset else 'none'}",
        f"Asset type: {status.asset_type or 'unknown'}",
        f"CIK: {status.cik or 'missing'}",
        f"Foreign identity: {_format_bool(status.foreign_identity_available)}",
        f"Foreign identity ISIN: {status.foreign_identity_isin or 'missing'}",
        f"Price feature: {_format_bool(status.price_available)}",
        f"Fundamental rows: {status.fundamental_count}",
        f"Forward EPS estimate: {_format_bool(status.estimate_available)}",
        f"Target: {_format_bool(status.target_available)}",
        f"Score: {_format_bool(status.score_available)}",
        f"ETF feature: {_format_bool(status.etf_feature_available)}",
        f"ETF NAV: {_format_bool(status.etf_nav_available)}",
        f"Range snapshot: {_format_bool(status.range_available)}",
        f"Option chain: {_format_bool(status.option_chain_available)}",
        f"Benchmark comparison: {_format_bool(comparison is not None and bool(comparison.comparison_date))}",
        "Readiness blockers: "
        + (", ".join(status.readiness_blockers) if status.readiness_blockers else "none"),
    ]
    if comparison:
        lines.extend(
            [
                f"Sector: {comparison.sector or 'unknown'}",
                f"Industry: {comparison.industry or 'unknown'}",
                f"Sector benchmark: {comparison.sector_benchmark_ticker or 'missing'}",
                f"Sector peers: {comparison.sector_peer_count}",
                f"Industry peers: {comparison.industry_peer_count}",
                f"Forward P/E: {_format_number(comparison.forward_pe)}",
                f"Sector forward P/E median: {_format_number(comparison.sector_forward_pe_median)}",
                f"Sector forward P/E discount: {_format_percent(comparison.sector_forward_pe_discount_pct)}",
                f"RS vs SPY: {_format_percent(comparison.relative_strength_vs_spy)}",
                f"RS vs QQQ: {_format_percent(comparison.relative_strength_vs_qqq)}",
                f"RS vs sector ETF: {_format_percent(comparison.relative_strength_vs_sector)}",
                f"Benchmark status: {comparison.benchmark_status or 'none'}",
            ]
        )
    return "\n".join(lines)


def build_etf_strategy_review_text(review: EtfStrategyReview) -> str:
    def _alternative_lines(alternative: EtfStrategyAlternative) -> list[str]:
        return [
            f"{alternative.label}: {alternative.status}",
            f"  Action: {alternative.action or 'none'}",
            f"  Score: {_format_number(alternative.score)}",
            f"  Current price: {_format_number(alternative.current_price)}",
            f"  Target price: {_format_number(alternative.target_price)}",
            f"  NAV per share: {_format_number(alternative.nav_per_share)}",
            f"  NAV gap: {_format_percent(alternative.nav_gap)}",
            f"  Strike/expiration: {_format_number(alternative.option_strike)} / {alternative.option_expiration or 'n/a'}",
            f"  Premium: {_format_number(alternative.premium)}",
            f"  Breakeven: {_format_number(alternative.breakeven)}",
            f"  Max loss: {_format_number(alternative.max_loss)}",
            f"  Premium yield: {_format_percent(alternative.premium_yield)}",
            f"  Annualized yield: {_format_percent(alternative.annualized_yield)}",
            f"  Downside buffer: {_format_percent(alternative.downside_buffer_pct)}",
            f"  Assignment notional: {_format_number(alternative.assignment_notional)}",
            f"  Source: {alternative.source or 'n/a'}",
            f"  Blockers: {', '.join(alternative.blockers) if alternative.blockers else 'none'}",
            f"  Warnings: {', '.join(alternative.warnings) if alternative.warnings else 'none'}",
        ]

    lines = [
        "ETF strategy review",
        f"Ticker: {review.ticker}",
        f"Asset type: {review.asset_type or 'unknown'}",
        f"Decision: {review.decision}",
        "Warnings: " + (", ".join(review.warnings) if review.warnings else "none"),
    ]
    lines.extend(_alternative_lines(review.share))
    lines.extend(_alternative_lines(review.long_call))
    lines.extend(_alternative_lines(review.sell_put))
    return "\n".join(lines)
