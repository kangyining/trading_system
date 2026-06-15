from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

from .config import AppConfig
from .db import initialize_database
from .ibkr_provider import update_etf_navs_from_ibkr
from .market_data import update_prices
from .ranges import compute_range_snapshots
from .scoring import compute_scores
from .storage import (
    Asset,
    AssetChangeEvent,
    MissingTickerCandidate,
    MissingTickerResolutionEvent,
    insert_asset_change_event,
    insert_missing_ticker_resolution_event,
    latest_asset,
    latest_missing_ticker_candidate,
    list_missing_ticker_candidates,
    list_research_recommendation_candidates,
    list_trader_commentary_claims,
    normalize_asset_role,
    normalize_ticker,
    update_missing_ticker_candidate_status,
    upsert_asset,
    upsert_missing_ticker_candidate,
)
from .valuation import compute_targets
from .watchlist import upsert_watchlist_asset


MISSING_TICKER_STATUSES = {
    "detected",
    "metadata_resolved",
    "ready_to_onboard",
    "onboarded",
    "hydrated",
    "blocked",
    "ignored",
}

SOURCE_ACCOUNT_CONTEXT = "account_context"
SOURCE_RESEARCH_RECOMMENDATIONS = "research_recommendations"
SOURCE_TRADER_COMMENTARY = "trader_commentary"

# Small, explicit fallback for currently observed source-backed account holdings.
# These rows still need provider-backed prices/NAVs after onboarding.
KNOWN_ACCOUNT_ETF_METADATA: dict[str, dict[str, str]] = {
    "BIL": {
        "name": "SPDR Bloomberg 1-3 Month T-Bill ETF",
        "exchange": "NYSEARCA",
        "currency": "USD",
        "sector": "Fixed Income",
        "industry": "Treasury Bills",
        "country": "US",
    },
    "DBC": {
        "name": "Invesco DB Commodity Index Tracking Fund",
        "exchange": "NYSEARCA",
        "currency": "USD",
        "sector": "Commodities",
        "industry": "Broad Commodities",
        "country": "US",
    },
}


@dataclass(frozen=True)
class MissingTickerStatus:
    total_candidates: int
    pending_candidates: int
    ready_to_onboard: int
    onboarded: int
    hydrated: int
    blocked: int
    account_context_candidates: int
    candidates: tuple[MissingTickerCandidate, ...]
    next_actions: tuple[str, ...]


@dataclass(frozen=True)
class MissingTickerResolveResult:
    source: str
    detected_count: int
    resolved_count: int
    ready_to_onboard_count: int
    blocked_count: int
    candidates: tuple[MissingTickerCandidate, ...]
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class MissingTickerOnboardingResult:
    applied: bool
    onboarded_count: int
    skipped_count: int
    candidates: tuple[MissingTickerCandidate, ...]
    account_apply_ready: bool
    account_blocked_reason: str | None
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class MissingTickerHydrationResult:
    ticker: str
    status: str
    asset_type: str | None
    price_loaded_count: int
    target_count: int
    score_count: int
    range_count: int
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class MissingTickerAutomationResult:
    source: str
    detected_count: int
    ready_to_onboard_count: int
    onboarded_count: int
    hydrated_count: int
    onboarded_tickers: tuple[str, ...]
    hydrated_tickers: tuple[str, ...]
    account_apply_ready: bool
    account_blocked_reason: str | None
    warnings: tuple[str, ...]


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _today() -> str:
    return date.today().isoformat()


def _split_codes(value: str | None) -> list[str]:
    return [item.strip() for item in (value or "").split(",") if item.strip()]


def _join_codes(values: list[str] | tuple[str, ...] | set[str]) -> str | None:
    cleaned = [str(value).strip() for value in values if str(value).strip()]
    return ",".join(dict.fromkeys(cleaned)) if cleaned else None


def _unique_candidates_by_ticker(
    candidates: list[MissingTickerCandidate] | tuple[MissingTickerCandidate, ...],
) -> tuple[MissingTickerCandidate, ...]:
    unique: dict[str, MissingTickerCandidate] = {}
    for candidate in candidates:
        if candidate.ticker not in unique:
            unique[candidate.ticker] = candidate
    return tuple(unique.values())


def _account_files(config: AppConfig) -> list[Path]:
    files: list[Path] = []
    for path in (
        config.portfolio_positions_path,
        config.account_source_exports_dir,
    ):
        if isinstance(path, Path) and path.is_file():
            files.append(path)
        elif isinstance(path, Path) and path.exists():
            files.extend(sorted(path.glob("*.csv")))
    return list(dict.fromkeys(files))


def _is_account_position_file(path: Path) -> bool:
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as input_file:
            reader = csv.DictReader(input_file)
            headers = set(reader.fieldnames or [])
    except UnicodeDecodeError:
        return False
    return {"ticker", "quantity", "account", "position_date", "source"}.issubset(headers)


def _read_account_position_rows(config: AppConfig) -> list[tuple[Path, int, dict[str, str]]]:
    rows: list[tuple[Path, int, dict[str, str]]] = []
    for path in _account_files(config):
        if not _is_account_position_file(path):
            continue
        with path.open("r", encoding="utf-8-sig", newline="") as input_file:
            reader = csv.DictReader(input_file)
            for row_number, row in enumerate(reader, start=2):
                if not any((value or "").strip() for value in row.values()):
                    continue
                rows.append((path, row_number, dict(row)))
    return rows


def _asset_type_from_row(ticker: str, row: dict[str, str]) -> tuple[str | None, list[str]]:
    warnings: list[str] = []
    if ticker in KNOWN_ACCOUNT_ETF_METADATA:
        warnings.append("metadata_curated_account_etf_fallback")
        return "etf", warnings
    row_type = (row.get("asset_type") or "").strip().lower()
    if row_type in {"equity", "stock", "stk"}:
        return "equity", warnings
    if row_type in {"etf", "fund"}:
        return "etf", warnings
    return None, warnings


def _metadata_for_account_candidate(
    ticker: str,
    row: dict[str, str],
    detected_asset_type: str | None,
) -> tuple[dict[str, str], list[str], list[str], str, float]:
    blockers: list[str] = []
    warnings: list[str] = []
    metadata: dict[str, str] = {}
    confidence = 0.65
    recommended_role = "account_holding_review"

    if detected_asset_type == "etf":
        metadata = dict(KNOWN_ACCOUNT_ETF_METADATA.get(ticker, {}))
        metadata.setdefault("currency", (row.get("currency") or "USD").strip().upper())
        metadata.setdefault("country", "US")
        recommended_role = "scoreable"
        confidence = 0.9 if ticker in KNOWN_ACCOUNT_ETF_METADATA else 0.75
        if ticker not in KNOWN_ACCOUNT_ETF_METADATA:
            warnings.append("etf_metadata_partial")
            blockers.append("missing_etf_metadata")
    elif detected_asset_type == "equity":
        recommended_role = "scoreable"
        metadata.setdefault("currency", (row.get("currency") or "USD").strip().upper())
        metadata.setdefault("country", "US")
        for key in ("sector", "industry"):
            value = (row.get(key) or "").strip()
            if value:
                metadata[key] = value
        blockers.extend(
            code
            for code, key in (
                ("missing_sector_metadata", "sector"),
                ("missing_industry_metadata", "industry"),
                ("missing_cik_metadata", "cik"),
            )
            if not metadata.get(key)
        )
    else:
        blockers.append("missing_asset_type_metadata")

    return metadata, blockers, warnings, recommended_role, confidence


def record_missing_ticker_candidate_from_account_row(
    config: AppConfig,
    row: dict[str, str],
    source_file: str,
    source_row: str,
) -> MissingTickerCandidate | None:
    ticker = normalize_ticker(row.get("ticker", ""))
    if not ticker:
        return None
    existing = latest_asset(config.database_path, ticker)
    if existing is not None and existing.active_flag == 1:
        return None

    detected_type, type_warnings = _asset_type_from_row(ticker, row)
    metadata, blockers, metadata_warnings, recommended_role, confidence = (
        _metadata_for_account_candidate(ticker, row, detected_type)
    )
    warnings = [*type_warnings, *metadata_warnings]
    status = "ready_to_onboard" if not blockers else "blocked"
    next_command = (
        "python -m target_opportunity_monitor apply-missing-ticker-onboarding --confirm"
        if status == "ready_to_onboard"
        else "python -m target_opportunity_monitor resolve-missing-tickers --source account_context"
    )
    candidate = MissingTickerCandidate(
        ticker=ticker,
        first_seen_source=SOURCE_ACCOUNT_CONTEXT,
        source_file=source_file,
        source_row=str(source_row),
        detected_asset_type=detected_type,
        recommended_asset_role=recommended_role,
        confidence=confidence,
        blockers=_join_codes(blockers),
        warnings=_join_codes(warnings),
        status=status,
        next_command=next_command,
        metadata_name=metadata.get("name"),
        metadata_exchange=metadata.get("exchange"),
        metadata_currency=metadata.get("currency") or (row.get("currency") or "USD"),
        metadata_sector=metadata.get("sector"),
        metadata_industry=metadata.get("industry"),
        metadata_country=metadata.get("country") or "US",
        source_url=row.get("source_url") or None,
        as_of_date=row.get("as_of_date") or _today(),
        effective_date=row.get("effective_date") or _today(),
    )
    upsert_missing_ticker_candidate(config.database_path, candidate)
    return latest_missing_ticker_candidate(config.database_path, ticker, SOURCE_ACCOUNT_CONTEXT) or candidate


def detect_account_context_missing_tickers(config: AppConfig) -> list[MissingTickerCandidate]:
    detected: list[MissingTickerCandidate] = []
    for path, row_number, row in _read_account_position_rows(config):
        ticker = normalize_ticker(row.get("ticker", ""))
        if not ticker:
            continue
        asset = latest_asset(config.database_path, ticker)
        if asset is not None and asset.active_flag == 1:
            continue
        candidate = record_missing_ticker_candidate_from_account_row(
            config,
            row,
            path.name,
            str(row_number),
        )
        if candidate is not None:
            detected.append(candidate)
    return detected


def _stage_review_gated_candidate(
    config: AppConfig,
    ticker: str,
    first_seen_source: str,
    source_file: str,
    source_row: str,
    source_url: str | None = None,
    warning: str = "review_required",
) -> MissingTickerCandidate | None:
    normalized = normalize_ticker(ticker)
    if not normalized:
        return None
    asset = latest_asset(config.database_path, normalized)
    if asset is not None and asset.active_flag == 1:
        return None
    candidate = MissingTickerCandidate(
        ticker=normalized,
        first_seen_source=first_seen_source,
        source_file=source_file,
        source_row=source_row,
        detected_asset_type=None,
        recommended_asset_role="research_review",
        confidence=0.5,
        blockers="approval_required",
        warnings=warning,
        status="detected",
        next_command=f"python -m target_opportunity_monitor research-ticker-plan --ticker {normalized}",
        source_url=source_url,
        as_of_date=_today(),
        effective_date=_today(),
    )
    upsert_missing_ticker_candidate(config.database_path, candidate)
    return (
        latest_missing_ticker_candidate(config.database_path, normalized, first_seen_source)
        or candidate
    )


def detect_research_recommendation_missing_tickers(config: AppConfig) -> list[MissingTickerCandidate]:
    detected: list[MissingTickerCandidate] = []
    for candidate in list_research_recommendation_candidates(config.database_path):
        item = _stage_review_gated_candidate(
            config,
            candidate.ticker,
            SOURCE_RESEARCH_RECOMMENDATIONS,
            "research_recommendation_candidates",
            str(candidate.research_recommendation_id),
            source_url=candidate.source_url,
            warning="research_approval_required",
        )
        if item is not None:
            detected.append(item)
    return detected


def detect_trader_commentary_missing_tickers(config: AppConfig) -> list[MissingTickerCandidate]:
    detected: list[MissingTickerCandidate] = []
    for claim in list_trader_commentary_claims(config.database_path):
        if not claim.ticker:
            continue
        item = _stage_review_gated_candidate(
            config,
            claim.ticker,
            SOURCE_TRADER_COMMENTARY,
            "trader_commentary_claims",
            str(claim.claim_id),
            source_url=claim.source_url,
            warning="commentary_approval_required",
        )
        if item is not None:
            detected.append(item)
    return detected


def resolve_missing_tickers(
    config: AppConfig,
    source: str | None = None,
) -> MissingTickerResolveResult:
    initialize_database(config.database_path)
    warnings: list[str] = []
    detected: list[MissingTickerCandidate] = []
    if source in {None, "all", SOURCE_ACCOUNT_CONTEXT}:
        detected.extend(detect_account_context_missing_tickers(config))
    if source in {None, "all", SOURCE_RESEARCH_RECOMMENDATIONS}:
        detected.extend(detect_research_recommendation_missing_tickers(config))
    if source in {None, "all", SOURCE_TRADER_COMMENTARY}:
        detected.extend(detect_trader_commentary_missing_tickers(config))
    if source and source not in {
        "all",
        SOURCE_ACCOUNT_CONTEXT,
        SOURCE_RESEARCH_RECOMMENDATIONS,
        SOURCE_TRADER_COMMENTARY,
    }:
        warnings.append(f"unsupported_source:{source}")

    candidates = tuple(
        list_missing_ticker_candidates(
            config.database_path,
            source=None if source in {None, "all"} else source,
        )
    )
    resolved = _unique_candidates_by_ticker(
        [item for item in candidates if item.status in {"metadata_resolved", "ready_to_onboard", "onboarded", "hydrated"}]
    )
    ready = _unique_candidates_by_ticker(
        [item for item in candidates if item.status == "ready_to_onboard"]
    )
    blocked = _unique_candidates_by_ticker(
        [item for item in candidates if item.status == "blocked"]
    )
    return MissingTickerResolveResult(
        source=source or "all",
        detected_count=len(detected),
        resolved_count=len(resolved),
        ready_to_onboard_count=len(ready),
        blocked_count=len(blocked),
        candidates=candidates,
        warnings=tuple(warnings),
    )


def missing_ticker_status(config: AppConfig) -> MissingTickerStatus:
    initialize_database(config.database_path)
    candidates = tuple(list_missing_ticker_candidates(config.database_path))
    unique_candidates = _unique_candidates_by_ticker(candidates)
    pending_statuses = {"detected", "metadata_resolved", "ready_to_onboard", "blocked"}
    next_actions: list[str] = []
    if any(item.status == "ready_to_onboard" for item in candidates):
        next_actions.append(
            "python -m target_opportunity_monitor apply-missing-ticker-onboarding --confirm"
        )
    if any(item.status == "blocked" for item in candidates):
        next_actions.append(
            "Review blocked candidates or add metadata before applying."
        )
    if not candidates:
        next_actions.append(
            "Run python -m target_opportunity_monitor resolve-missing-tickers --source account_context"
        )
    return MissingTickerStatus(
        total_candidates=len(unique_candidates),
        pending_candidates=len([item for item in unique_candidates if item.status in pending_statuses]),
        ready_to_onboard=len([item for item in unique_candidates if item.status == "ready_to_onboard"]),
        onboarded=len([item for item in unique_candidates if item.status == "onboarded"]),
        hydrated=len([item for item in unique_candidates if item.status == "hydrated"]),
        blocked=len([item for item in unique_candidates if item.status == "blocked"]),
        account_context_candidates=len(
            [item for item in unique_candidates if item.first_seen_source == SOURCE_ACCOUNT_CONTEXT]
        ),
        candidates=candidates,
        next_actions=tuple(next_actions),
    )


def build_missing_ticker_status_text(config: AppConfig) -> str:
    status = missing_ticker_status(config)
    lines = [
        "Missing Ticker Status",
        f"Total candidates: {status.total_candidates}",
        f"Pending candidates: {status.pending_candidates}",
        f"Ready to onboard: {status.ready_to_onboard}",
        f"Onboarded: {status.onboarded}",
        f"Hydrated: {status.hydrated}",
        f"Blocked: {status.blocked}",
        f"Account-context candidates: {status.account_context_candidates}",
    ]
    if status.candidates:
        lines.append("Candidates:")
        for item in status.candidates[:25]:
            lines.append(
                "- "
                f"{item.ticker}: status={item.status}, source={item.first_seen_source}, "
                f"type={item.detected_asset_type or 'unknown'}, role={item.recommended_asset_role or 'unknown'}, "
                f"blockers={item.blockers or 'none'}, warnings={item.warnings or 'none'}"
            )
    if status.next_actions:
        lines.append("Next actions:")
        lines.extend(f"- {action}" for action in status.next_actions)
    return "\n".join(lines)


def build_missing_ticker_plan_text(config: AppConfig, source: str | None = None) -> str:
    result = resolve_missing_tickers(config, source=source)
    lines = [
        "Missing Ticker Plan",
        f"Source: {result.source}",
        f"Detected this run: {result.detected_count}",
        f"Resolved candidates: {result.resolved_count}",
        f"Ready to onboard: {result.ready_to_onboard_count}",
        f"Blocked: {result.blocked_count}",
    ]
    if result.candidates:
        lines.append("Candidate detail:")
        for item in result.candidates[:25]:
            lines.append(
                "- "
                f"{item.ticker}: {item.status}; type={item.detected_asset_type or 'unknown'}; "
                f"role={item.recommended_asset_role or 'unknown'}; "
                f"next={item.next_command or 'none'}; blockers={item.blockers or 'none'}"
            )
    if result.warnings:
        lines.append("Warnings: " + ", ".join(result.warnings))
    return "\n".join(lines)


def apply_missing_ticker_onboarding(
    config: AppConfig,
    confirm: bool = False,
    source: str | None = None,
) -> MissingTickerOnboardingResult:
    initialize_database(config.database_path)
    resolve_missing_tickers(config, source=source or SOURCE_ACCOUNT_CONTEXT)
    candidates = _unique_candidates_by_ticker(
        tuple(
            item
            for item in list_missing_ticker_candidates(
                config.database_path,
                source=None if source in {None, "all"} else source,
            )
            if item.status == "ready_to_onboard"
        )
    )
    warnings: list[str] = []
    if not confirm:
        warnings.append("dry_run_only")
        return _onboarding_result(config, False, 0, len(candidates), candidates, warnings)
    if not candidates:
        warnings.append("no_ready_missing_ticker_candidates")
        return _onboarding_result(config, False, 0, 0, candidates, warnings)

    onboarded: list[MissingTickerCandidate] = []
    for candidate in candidates:
        previous = latest_asset(config.database_path, candidate.ticker)
        if previous is not None and previous.active_flag == 1:
            update_missing_ticker_candidate_status(
                config.database_path,
                candidate.ticker,
                "onboarded",
                first_seen_source=candidate.first_seen_source,
                warnings=_join_codes([*_split_codes(candidate.warnings), "already_active_asset"]) or None,
            )
            continue
        asset_role = normalize_asset_role(candidate.recommended_asset_role or "scoreable")
        if asset_role == "inactive":
            warnings.append(f"{candidate.ticker}:inactive_role_not_onboarded")
            continue
        asset = Asset(
            ticker=candidate.ticker,
            name=candidate.metadata_name,
            asset_type=candidate.detected_asset_type or "equity",
            exchange=candidate.metadata_exchange,
            currency=candidate.metadata_currency or "USD",
            sector=candidate.metadata_sector,
            industry=candidate.metadata_industry,
            country=candidate.metadata_country or "US",
            active_flag=1,
            asset_role=asset_role,
            source="missing_ticker_resolver",
            as_of_date=_today(),
            effective_date=_now(),
        )
        upsert_watchlist_asset(config.watchlist_path, asset)
        upsert_asset(config.database_path, asset)
        insert_asset_change_event(
            config.database_path,
            AssetChangeEvent(
                event_timestamp=_now(),
                ticker=asset.ticker,
                event_type="missing_ticker_onboard",
                previous_active_flag=previous.active_flag if previous else None,
                new_active_flag=1,
                reason="source_backed_missing_ticker_candidate",
                details=f"source={candidate.first_seen_source};role={asset_role};asset_type={asset.asset_type}",
                source="missing_ticker_resolver",
                as_of_date=_today(),
                effective_date=_now(),
            ),
        )
        update_missing_ticker_candidate_status(
            config.database_path,
            candidate.ticker,
            "onboarded",
            first_seen_source=candidate.first_seen_source,
            next_command=f"python -m target_opportunity_monitor hydrate-missing-ticker --ticker {candidate.ticker}",
        )
        insert_missing_ticker_resolution_event(
            config.database_path,
            MissingTickerResolutionEvent(
                event_timestamp=_now(),
                ticker=candidate.ticker,
                event_type="onboarded",
                previous_status=candidate.status,
                new_status="onboarded",
                details=f"asset_type={asset.asset_type};asset_role={asset_role}",
                warnings=candidate.warnings,
                as_of_date=_today(),
                effective_date=_now(),
            ),
        )
        onboarded.append(candidate)

    return _onboarding_result(
        config,
        bool(onboarded),
        len(onboarded),
        len(candidates) - len(onboarded),
        tuple(onboarded),
        warnings,
    )


def _onboarding_result(
    config: AppConfig,
    applied: bool,
    onboarded_count: int,
    skipped_count: int,
    candidates: tuple[MissingTickerCandidate, ...],
    warnings: list[str],
) -> MissingTickerOnboardingResult:
    try:
        from .account import preview_account_context_activation

        preview = preview_account_context_activation(config)
        account_apply_ready = preview.apply_ready
        account_blocked_reason = preview.blocked_reason
    except Exception as error:  # pragma: no cover - defensive status surface
        account_apply_ready = False
        account_blocked_reason = f"account_preview_failed:{error}"
        warnings.append(account_blocked_reason)
    return MissingTickerOnboardingResult(
        applied=applied,
        onboarded_count=onboarded_count,
        skipped_count=skipped_count,
        candidates=candidates,
        account_apply_ready=account_apply_ready,
        account_blocked_reason=account_blocked_reason,
        warnings=tuple(warnings),
    )


def hydrate_missing_ticker(config: AppConfig, ticker: str) -> MissingTickerHydrationResult:
    initialize_database(config.database_path)
    normalized = normalize_ticker(ticker)
    asset = latest_asset(config.database_path, normalized)
    if asset is None or asset.active_flag != 1:
        return MissingTickerHydrationResult(
            ticker=normalized,
            status="blocked",
            asset_type=None,
            price_loaded_count=0,
            target_count=0,
            score_count=0,
            range_count=0,
            warnings=("asset_not_onboarded_or_inactive",),
        )

    warnings: list[str] = []
    price_loaded = 0
    target_count = 0
    score_count = 0
    range_count = 0
    try:
        price_result = update_prices(config, ticker=normalized)
        price_loaded = price_result.loaded_count
        for result in price_result.results:
            warnings.extend(result.warnings)
    except Exception as error:
        warnings.append(f"price_update_failed:{error}")

    asset_type = (asset.asset_type or "").strip().lower()
    if asset_type == "etf":
        try:
            nav_result = update_etf_navs_from_ibkr(config, ticker=normalized)
            for result in nav_result.results:
                warnings.extend(result.warnings)
                if result.rows_loaded == 0:
                    warnings.append("missing_etf_nav_or_provider_subscription")
        except Exception as error:
            warnings.append(f"etf_nav_update_failed:{error}")

    try:
        target_result = compute_targets(config, ticker=normalized)
        target_count = len(target_result.results)
        for result in target_result.results:
            warnings.extend(result.warnings)
    except Exception as error:
        warnings.append(f"target_compute_failed:{error}")

    try:
        score_result = compute_scores(config, ticker=normalized)
        score_count = len(score_result.results)
        for result in score_result.results:
            warnings.extend(result.warnings)
    except Exception as error:
        warnings.append(f"score_compute_failed:{error}")

    try:
        range_result = compute_range_snapshots(config, ticker=normalized, create_notifications=False)
        range_count = len(range_result.results)
        for result in range_result.results:
            warnings.extend(result.warnings)
    except Exception as error:
        warnings.append(f"range_compute_failed:{error}")

    status = "hydrated" if price_loaded > 0 else "blocked"
    update_missing_ticker_candidate_status(
        config.database_path,
        normalized,
        status,
        warnings=_join_codes(warnings) or None,
    )
    insert_missing_ticker_resolution_event(
        config.database_path,
        MissingTickerResolutionEvent(
            event_timestamp=_now(),
            ticker=normalized,
            event_type="hydration",
            new_status=status,
            details=(
                f"price_loaded={price_loaded};targets={target_count};"
                f"scores={score_count};ranges={range_count}"
            ),
            warnings=_join_codes(warnings),
            as_of_date=_today(),
            effective_date=_now(),
        ),
    )
    return MissingTickerHydrationResult(
        ticker=normalized,
        status=status,
        asset_type=asset.asset_type,
        price_loaded_count=price_loaded,
        target_count=target_count,
        score_count=score_count,
        range_count=range_count,
        warnings=tuple(dict.fromkeys(warnings)),
    )


def run_missing_ticker_automation(
    config: AppConfig,
    *,
    source: str | None = SOURCE_ACCOUNT_CONTEXT,
    apply_ready: bool = True,
    hydrate: bool = True,
    max_hydrations: int = 5,
) -> MissingTickerAutomationResult:
    """Resolve source-backed missing tickers inside normal automation flows.

    Only account-context candidates are auto-onboarded. Commentary, social, and
    research candidates remain approval-gated even when this helper is called
    with source="all".
    """

    source_key = source or "all"
    resolve_result = resolve_missing_tickers(config, source=source_key)
    warnings: list[str] = list(resolve_result.warnings)
    if source_key == SOURCE_ACCOUNT_CONTEXT and resolve_result.blocked_count:
        warnings.append(f"missing_ticker_candidates_blocked:{resolve_result.blocked_count}")
    account_apply_ready = False
    account_blocked_reason: str | None = None
    onboarded_tickers: list[str] = []
    hydrated_tickers: list[str] = []
    onboarded_count = 0

    should_auto_apply_account = apply_ready and source_key in {
        "all",
        SOURCE_ACCOUNT_CONTEXT,
    }
    if should_auto_apply_account and resolve_result.ready_to_onboard_count:
        onboarding = apply_missing_ticker_onboarding(
            config,
            confirm=True,
            source=SOURCE_ACCOUNT_CONTEXT,
        )
        warnings.extend(onboarding.warnings)
        account_apply_ready = onboarding.account_apply_ready
        account_blocked_reason = onboarding.account_blocked_reason
        onboarded_count = onboarding.onboarded_count
        onboarded_tickers.extend(item.ticker for item in onboarding.candidates)
    else:
        try:
            from .account import preview_account_context_activation

            preview = preview_account_context_activation(config)
            account_apply_ready = preview.apply_ready
            account_blocked_reason = preview.blocked_reason
        except Exception as error:  # pragma: no cover - defensive status surface
            account_blocked_reason = f"account_preview_failed:{error}"
            warnings.append(account_blocked_reason)

    if hydrate and max_hydrations > 0:
        hydration_candidates = [
            item
            for item in list_missing_ticker_candidates(
                config.database_path,
                source=SOURCE_ACCOUNT_CONTEXT,
                status="onboarded",
            )
            if item.ticker
        ]
        seen: set[str] = set()
        for candidate in hydration_candidates:
            if candidate.ticker in seen:
                continue
            seen.add(candidate.ticker)
            if len(hydrated_tickers) >= max_hydrations:
                warnings.append("missing_ticker_hydration_budget_exhausted")
                break
            hydration = hydrate_missing_ticker(config, candidate.ticker)
            if hydration.status == "hydrated":
                hydrated_tickers.append(hydration.ticker)
            if hydration.warnings:
                warnings.append(
                    f"{hydration.ticker}:{','.join(hydration.warnings[:5])}"
                )

    return MissingTickerAutomationResult(
        source=source_key,
        detected_count=resolve_result.detected_count,
        ready_to_onboard_count=resolve_result.ready_to_onboard_count,
        onboarded_count=onboarded_count,
        hydrated_count=len(hydrated_tickers),
        onboarded_tickers=tuple(dict.fromkeys(onboarded_tickers)),
        hydrated_tickers=tuple(dict.fromkeys(hydrated_tickers)),
        account_apply_ready=account_apply_ready,
        account_blocked_reason=account_blocked_reason,
        warnings=tuple(dict.fromkeys(warnings)),
    )


def build_missing_ticker_automation_text(result: MissingTickerAutomationResult) -> str:
    lines = [
        "Missing ticker automation",
        f"Source: {result.source}",
        f"Detected this run: {result.detected_count}",
        f"Ready to onboard: {result.ready_to_onboard_count}",
        f"Onboarded count: {result.onboarded_count}",
        f"Hydrated count: {result.hydrated_count}",
        f"Account apply ready: {result.account_apply_ready}",
        f"Account blocked reason: {result.account_blocked_reason or 'none'}",
    ]
    if result.onboarded_tickers:
        lines.append("Onboarded tickers: " + ", ".join(result.onboarded_tickers))
    if result.hydrated_tickers:
        lines.append("Hydrated tickers: " + ", ".join(result.hydrated_tickers))
    if result.warnings:
        lines.append("Warnings: " + ", ".join(result.warnings))
    return "\n".join(lines)


def build_missing_ticker_onboarding_text(result: MissingTickerOnboardingResult) -> str:
    lines = [
        "Missing ticker onboarding",
        f"Applied: {result.applied}",
        f"Onboarded count: {result.onboarded_count}",
        f"Skipped count: {result.skipped_count}",
        f"Account apply ready: {result.account_apply_ready}",
        f"Account blocked reason: {result.account_blocked_reason or 'none'}",
    ]
    if result.candidates:
        lines.append("Candidates:")
        lines.extend(f"- {item.ticker}: {item.status}" for item in result.candidates)
    if result.warnings:
        lines.append("Warnings: " + ", ".join(result.warnings))
    return "\n".join(lines)


def build_missing_ticker_hydration_text(result: MissingTickerHydrationResult) -> str:
    lines = [
        "Missing ticker hydration",
        f"Ticker: {result.ticker}",
        f"Status: {result.status}",
        f"Asset type: {result.asset_type or 'unknown'}",
        f"Price rows loaded: {result.price_loaded_count}",
        f"Target rows: {result.target_count}",
        f"Score rows: {result.score_count}",
        f"Range rows: {result.range_count}",
    ]
    if result.warnings:
        lines.append("Warnings: " + ", ".join(result.warnings))
    return "\n".join(lines)
