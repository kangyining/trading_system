from __future__ import annotations

import csv
from contextlib import closing
from dataclasses import dataclass
from datetime import UTC, date, datetime
import hashlib
import json
from pathlib import Path
import re
import shutil
import sqlite3

from .config import AppConfig
from .research_tickers import apply_research_ticker, research_ticker_plan
from .sec_fundamentals import load_cik_map
from .storage import (
    ResearchRecommendationCandidate,
    ResearchRecommendationEvidence,
    StoredResearchRecommendationCandidate,
    get_research_recommendation_candidate,
    is_scoreable_asset,
    latest_asset,
    latest_research_recommendation_date,
    list_assets,
    list_news_catalyst_source_snapshots,
    list_research_recommendation_candidates,
    list_research_recommendation_evidence,
    list_trader_commentary_browser_capture_items,
    list_trader_commentary_claims,
    list_trader_commentary_discord_capture_items,
    normalize_ticker,
    update_research_recommendation_status,
    upsert_research_recommendation_candidate,
    upsert_research_recommendation_evidence,
)


MODEL_VERSION = "research_recommendation_mvp_v1"
VALID_STATUSES = ("pending", "approved", "ignored", "promoted", "rejected")
VALID_SOURCES = (
    "all",
    "tom_internal",
    "social_local",
    "external_research_signals",
    "codex_manual",
)
MANUAL_RECOMMENDATION_COLUMNS = (
    "ticker",
    "recommendation_date",
    "source",
    "topic",
    "rationale",
    "confidence",
    "priority",
    "source_url",
    "notes",
    "status",
)
COMMON_NON_TICKERS = {
    "API",
    "AI",
    "CPI",
    "CSV",
    "ETF",
    "GDP",
    "HTTP",
    "JSON",
    "LLM",
    "MVP",
    "NAV",
    "SEC",
    "TOM",
    "URL",
    "USD",
    "VIP",
    "XML",
}
SOCIAL_NEWS_SOURCES = {
    "x_recent_search",
    "x_browser_capture",
    "discord_bot_capture",
    "truth_social_public",
    "truth_social_manual",
    "x_manual",
}


@dataclass(frozen=True)
class RecommendationGenerationResult:
    source: str
    candidate_count: int
    evidence_count: int
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class RecommendationImportResult:
    imported_count: int
    skipped_count: int
    warnings: tuple[str, ...]
    csv_path: Path


@dataclass(frozen=True)
class RecommendationStatus:
    total_count: int
    pending_count: int
    approved_count: int
    approved_not_promoted_count: int
    promoted_count: int
    rejected_count: int
    ignored_count: int
    latest_recommendation_date: str | None
    top_pending: tuple[StoredResearchRecommendationCandidate, ...]
    source_mix: tuple[tuple[str, int], ...]
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class RecommendationPromotionResult:
    recommendation: StoredResearchRecommendationCandidate | None
    confirm: bool
    promoted: bool
    blocked_reason: str | None
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class RecommendationTriageGroup:
    ticker: str
    classification: str
    candidate_count: int
    max_priority_score: float | None
    recommendation_ids: tuple[int, ...]
    representative_candidate_ids: tuple[int, ...]
    sources: tuple[str, ...]
    topics: tuple[str, ...]
    warnings: tuple[str, ...]
    promotion_blockers: tuple[str, ...]
    recommended_action: str


@dataclass(frozen=True)
class RecommendationTriagePayload:
    total_count: int
    pending_count: int
    approved_count: int
    promoted_count: int
    ignored_count: int
    rejected_count: int
    status_counts: tuple[tuple[str, int], ...]
    source_mix: tuple[tuple[str, int], ...]
    group_count: int
    groups: tuple[RecommendationTriageGroup, ...]
    classification_counts: tuple[tuple[str, int], ...]


@dataclass(frozen=True)
class RecommendationBulkStatusResult:
    requested_ids: tuple[int, ...]
    target_status: str
    reason: str
    updated_count: int
    updated_candidates: tuple[StoredResearchRecommendationCandidate, ...]
    blocked_reason: str | None = None
    warnings: tuple[str, ...] = ()


def _today() -> str:
    return date.today().isoformat()


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def _clean(value: object) -> str | None:
    if value is None:
        return None
    cleaned = str(value).strip()
    return cleaned or None


def _as_float(value: object) -> float | None:
    cleaned = _clean(value)
    if cleaned is None:
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


def _join(values: list[str] | tuple[str, ...] | set[str]) -> str | None:
    ordered: list[str] = []
    for value in values:
        cleaned = _clean(value)
        if cleaned and cleaned not in ordered:
            ordered.append(cleaned)
    return ";".join(ordered) if ordered else None


def _stable_key(*parts: object) -> str:
    text = "|".join("" if part is None else str(part) for part in parts)
    digest = hashlib.sha1(text.encode("utf-8")).hexdigest()[:16]
    return f"rr_{digest}"


def _extract_tickers(text: str | None) -> tuple[str, ...]:
    if not text:
        return ()
    tickers: list[str] = []
    for match in re.finditer(r"\b[A-Z][A-Z0-9]{0,4}(?:\.[A-Z])?\b", text.upper()):
        ticker = match.group(0)
        if ticker in COMMON_NON_TICKERS or ticker.isdigit():
            continue
        if ticker not in tickers:
            tickers.append(ticker)
    return tuple(tickers)


def ensure_research_recommendation_csv(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        with path.open("w", encoding="utf-8", newline="") as output:
            csv.writer(output).writerow(MANUAL_RECOMMENDATION_COLUMNS)
    return path


def export_research_recommendation_template(config: AppConfig) -> Path:
    return ensure_research_recommendation_csv(config.research_recommendations_path)


def _asset_context(config: AppConfig) -> tuple[dict[str, str], set[str], set[str]]:
    roles: dict[str, str] = {}
    scoreable: set[str] = set()
    reference: set[str] = set()
    for asset in list_assets(config.database_path):
        ticker = normalize_ticker(asset.ticker)
        roles[ticker] = asset.asset_role
        if is_scoreable_asset(asset):
            scoreable.add(ticker)
        elif asset.active_flag == 1:
            reference.add(ticker)
    return roles, scoreable, reference


def _foreign_equity_plan_resolves_missing_cik(config: AppConfig, ticker: str) -> bool:
    foreign_plan = research_ticker_plan(config, ticker, asset_type="foreign_equity")
    return (
        not foreign_plan.readiness_blockers
        and foreign_plan.blocked_reason in {None, "ticker_already_scoreable"}
    )


def _metadata_status(
    config: AppConfig,
    ticker: str,
    *,
    scoreable: set[str],
    reference: set[str],
) -> tuple[str, tuple[str, ...], tuple[str, ...]]:
    warnings: list[str] = []
    blockers: list[str] = []
    normalized = normalize_ticker(ticker)
    asset = latest_asset(config.database_path, normalized)
    if normalized in scoreable:
        warnings.append("already_scoreable")
        return "already_scoreable", tuple(warnings), tuple(blockers)
    if normalized in reference:
        warnings.append("reference_only_candidate")
    if asset and (asset.asset_type or "").lower() == "etf":
        blockers.append("etf_research_ticker_requires_etf_path")
    cik_map = load_cik_map(config.cik_map_path)
    if normalized not in cik_map:
        if _foreign_equity_plan_resolves_missing_cik(config, normalized):
            warnings.append("foreign_equity_identity_available")
            blockers.append("foreign_equity_path_required")
        else:
            warnings.append("missing_cik_metadata")
            blockers.append("missing_cik_metadata")
    return (
        "reference" if normalized in reference else "unknown",
        tuple(warnings),
        tuple(blockers),
    )


def _score_candidate(
    *,
    evidence_count: int,
    source_count: int,
    confidence: float | None,
    metadata_status: str,
    warnings: tuple[str, ...],
) -> float:
    score = 20.0 + min(evidence_count, 6) * 8.0 + min(source_count, 4) * 7.0
    if confidence is not None:
        score += max(0.0, min(confidence, 100.0)) * 0.20
    if metadata_status == "reference":
        score += 8.0
    if metadata_status == "already_scoreable":
        score -= 35.0
    if "social_text_only" in warnings:
        score -= 6.0
    if "missing_cik_metadata" in warnings:
        score -= 8.0
    if "insufficient_evidence" in warnings:
        score -= 10.0
    return round(max(0.0, min(100.0, score)), 2)


def _candidate_from_evidence(
    config: AppConfig,
    *,
    ticker: str,
    source: str,
    topic: str | None,
    rationale: str,
    evidence_rows: list[ResearchRecommendationEvidence],
    recommendation_key: str | None = None,
    confidence: float | None = None,
    status: str = "pending",
    source_url: str | None = None,
    external_id: str | None = None,
    extra_warnings: tuple[str, ...] = (),
) -> ResearchRecommendationCandidate:
    _, scoreable, reference = _asset_context(config)
    metadata_status, metadata_warnings, blockers = _metadata_status(
        config,
        ticker,
        scoreable=scoreable,
        reference=reference,
    )
    sources = sorted({row.source for row in evidence_rows} | {source})
    warnings = list(extra_warnings) + list(metadata_warnings)
    if len(evidence_rows) < 1:
        warnings.append("insufficient_evidence")
    priority = _score_candidate(
        evidence_count=len(evidence_rows),
        source_count=len(sources),
        confidence=confidence,
        metadata_status=metadata_status,
        warnings=tuple(warnings),
    )
    latest_date = max((row.evidence_date for row in evidence_rows), default=_today())
    key = recommendation_key or _stable_key(
        "research_recommendation", source, normalize_ticker(ticker), topic
    )
    return ResearchRecommendationCandidate(
        recommendation_key=key,
        ticker=normalize_ticker(ticker),
        recommendation_date=latest_date,
        source=source,
        status=status if status in VALID_STATUSES else "pending",
        topic=topic,
        rationale=rationale,
        research_priority_score=priority,
        confidence=confidence,
        source_count=len(sources),
        evidence_count=len(evidence_rows),
        source_mix=";".join(sources),
        metadata_status=metadata_status,
        warning_codes=_join(warnings),
        promotion_blockers=_join(blockers),
        promoted_asset_role=None,
        source_url=source_url,
        external_id=external_id,
        model_version=MODEL_VERSION,
    )


def _store_candidate_with_evidence(
    config: AppConfig,
    candidate: ResearchRecommendationCandidate,
    evidence_rows: list[ResearchRecommendationEvidence],
) -> None:
    upsert_research_recommendation_candidate(config.database_path, candidate)
    for evidence in evidence_rows:
        upsert_research_recommendation_evidence(config.database_path, evidence)


def _evidence(
    *,
    recommendation_key: str,
    ticker: str,
    evidence_date: str,
    source: str,
    source_type: str,
    source_id: str | None,
    source_url: str | None,
    headline_or_excerpt: str | None,
    reason: str | None,
    confidence: float | None = None,
) -> ResearchRecommendationEvidence:
    return ResearchRecommendationEvidence(
        evidence_key=_stable_key(
            "research_recommendation_evidence",
            recommendation_key,
            ticker,
            source,
            source_id,
            headline_or_excerpt,
        ),
        recommendation_key=recommendation_key,
        ticker=normalize_ticker(ticker),
        evidence_date=evidence_date,
        source=source,
        source_type=source_type,
        source_id=source_id,
        source_url=source_url,
        headline_or_excerpt=headline_or_excerpt,
        reason=reason,
        confidence=confidence,
    )


def _generate_tom_internal(config: AppConfig) -> tuple[int, int, tuple[str, ...]]:
    _, scoreable, _ = _asset_context(config)
    grouped: dict[str, list[tuple[str, str, str | None, str | None]]] = {}
    for claim in list_trader_commentary_claims(config.database_path):
        if not claim.ticker:
            continue
        ticker = normalize_ticker(claim.ticker)
        if ticker in scoreable:
            continue
        grouped.setdefault(ticker, []).append(
            (
                claim.claim_date,
                "trader_commentary_claim",
                str(claim.claim_id),
                claim.raw_excerpt or claim.condition_text or claim.claim_type,
            )
        )
    for asset in list_assets(config.database_path):
        ticker = normalize_ticker(asset.ticker)
        if ticker in scoreable or asset.active_flag != 1:
            continue
        if asset.asset_role in {"commentary_validation", "regime_proxy"}:
            grouped.setdefault(ticker, []).append(
                (
                    asset.effective_date or asset.as_of_date or _today(),
                    "reference_asset",
                    ticker,
                    f"{ticker} is active as {asset.asset_role}",
                )
            )

    candidate_count = 0
    evidence_count = 0
    for ticker, rows in grouped.items():
        key = _stable_key("research_recommendation", "tom_internal", ticker, "local_signal_gap")
        evidence_rows = [
            _evidence(
                recommendation_key=key,
                ticker=ticker,
                evidence_date=row[0],
                source="tom_internal",
                source_type=row[1],
                source_id=row[2],
                source_url=None,
                headline_or_excerpt=row[3],
                reason="unsupported_or_reference_ticker_seen_in_tom",
                confidence=60.0,
            )
            for row in rows
        ]
        candidate = _candidate_from_evidence(
            config,
            ticker=ticker,
            source="tom_internal",
            topic="Local TOM signal gap",
            rationale=f"{ticker} appears in TOM commentary/reference data but is not scoreable.",
            evidence_rows=evidence_rows,
            recommendation_key=key,
            confidence=65.0,
        )
        _store_candidate_with_evidence(config, candidate, evidence_rows)
        candidate_count += 1
        evidence_count += len(evidence_rows)
    return candidate_count, evidence_count, ()


def _generate_social_local(config: AppConfig) -> tuple[int, int, tuple[str, ...]]:
    grouped: dict[str, list[tuple[str, str, str | None, str | None, str | None]]] = {}
    for item in list_trader_commentary_browser_capture_items(config.database_path):
        for ticker in _extract_tickers(item.content_text):
            grouped.setdefault(ticker, []).append(
                (
                    item.observed_at,
                    "x_browser_capture",
                    str(item.browser_capture_item_id),
                    item.canonical_url or item.target_url,
                    item.content_text[:300],
                )
            )
    for item in list_trader_commentary_discord_capture_items(config.database_path):
        for ticker in _extract_tickers(item.content_text):
            grouped.setdefault(ticker, []).append(
                (
                    item.observed_at,
                    "discord_bot_capture",
                    str(item.discord_capture_item_id),
                    item.canonical_url,
                    item.content_text[:300],
                )
            )
    for snapshot in list_news_catalyst_source_snapshots(config.database_path):
        if snapshot.source not in SOCIAL_NEWS_SOURCES:
            continue
        grouped.setdefault(normalize_ticker(snapshot.ticker), []).append(
            (
                snapshot.signal_date,
                snapshot.source,
                snapshot.source_url,
                snapshot.source_url,
                snapshot.headline_or_event,
            )
        )

    candidate_count = 0
    evidence_count = 0
    for ticker, rows in grouped.items():
        key = _stable_key("research_recommendation", "social_local", ticker, "local_social")
        evidence_rows = [
            _evidence(
                recommendation_key=key,
                ticker=ticker,
                evidence_date=row[0],
                source=row[1],
                source_type="local_social_capture",
                source_id=row[2],
                source_url=row[3],
                headline_or_excerpt=row[4],
                reason="ticker_mentioned_in_local_social_or_news_capture",
                confidence=45.0,
            )
            for row in rows
        ]
        candidate = _candidate_from_evidence(
            config,
            ticker=ticker,
            source="social_local",
            topic="Local social/report mention",
            rationale=f"{ticker} appears in local captured social/report evidence.",
            evidence_rows=evidence_rows,
            recommendation_key=key,
            confidence=50.0,
            source_url=rows[0][3],
            extra_warnings=("social_text_only",),
        )
        _store_candidate_with_evidence(config, candidate, evidence_rows)
        candidate_count += 1
        evidence_count += len(evidence_rows)
    return candidate_count, evidence_count, ()


def _read_external_suggestions(
    db_path: Path,
    fallback_dir: Path | None = None,
) -> tuple[list[dict[str, object]], tuple[str, ...]]:
    if not db_path.exists():
        return [], ("external_research_signals_db_missing",)
    attempted_fallback = False
    current_path = db_path
    while True:
        try:
            with closing(sqlite3.connect(current_path)) as connection:
                connection.row_factory = sqlite3.Row
                table_row = connection.execute(
                    """
                    SELECT name FROM sqlite_master
                    WHERE type = 'table' AND name = 'research_suggestions'
                    """
                ).fetchone()
                if table_row is None:
                    return [], ("external_research_suggestions_table_missing",)
                rows = connection.execute("SELECT * FROM research_suggestions").fetchall()
            return [dict(row) for row in rows], ()
        except sqlite3.Error as error:
            if fallback_dir is not None and not attempted_fallback:
                attempted_fallback = True
                fallback_dir.mkdir(parents=True, exist_ok=True)
                fallback_path = fallback_dir / "external_research_signals_snapshot.sqlite"
                try:
                    shutil.copyfile(db_path, fallback_path)
                except OSError as copy_error:
                    return [], (
                        f"external_research_signals_copy_failed:{type(copy_error).__name__}",
                    )
                current_path = fallback_path
                continue
            return [], (f"external_research_signals_db_failed:{type(error).__name__}",)


def _tickers_from_external_row(row: dict[str, object]) -> tuple[str, ...]:
    raw = row.get("tickers_json") or row.get("tickers") or row.get("ticker")
    if raw is None:
        return ()
    if isinstance(raw, str):
        text = raw.strip()
        if not text:
            return ()
        try:
            parsed = json.loads(text)
            if isinstance(parsed, list):
                return tuple(normalize_ticker(str(value)) for value in parsed if str(value).strip())
        except json.JSONDecodeError:
            pass
        return _extract_tickers(text)
    if isinstance(raw, list):
        return tuple(normalize_ticker(str(value)) for value in raw if str(value).strip())
    return ()


def _generate_external_research_signals(config: AppConfig) -> tuple[int, int, tuple[str, ...]]:
    rows, warnings = _read_external_suggestions(
        config.external_research_signals_db_path,
        config.research_recommendations_path.parent / ".cache",
    )
    candidate_count = 0
    evidence_count = 0
    for row in rows:
        status = str(row.get("status") or "pending").strip().lower()
        if status not in VALID_STATUSES:
            status = "pending"
        topic = _clean(row.get("topic_title") or row.get("topic") or row.get("topic_slug"))
        rationale = _clean(row.get("rationale")) or "Imported from external research-signals suggestion queue."
        confidence = _as_float(row.get("confidence"))
        if confidence is not None and 0 <= confidence <= 1:
            confidence *= 100.0
        source_url = _clean(row.get("report_path") or row.get("source_url"))
        external_id = _clean(row.get("id") or row.get("suggestion_id") or row.get("topic_slug"))
        recommendation_date = _clean(row.get("created_at") or row.get("report_date")) or _today()
        for ticker in _tickers_from_external_row(row):
            key = _stable_key("research_recommendation", "external_research_signals", ticker, external_id or topic)
            evidence_rows = [
                _evidence(
                    recommendation_key=key,
                    ticker=ticker,
                    evidence_date=recommendation_date[:10],
                    source="external_research_signals",
                    source_type="research_suggestions",
                    source_id=external_id,
                    source_url=source_url,
                    headline_or_excerpt=topic,
                    reason=rationale,
                    confidence=confidence,
                )
            ]
            extra_warnings = (
                ("external_suggestion_pending_approval",)
                if status == "pending"
                else ()
            )
            candidate = _candidate_from_evidence(
                config,
                ticker=ticker,
                source="external_research_signals",
                topic=topic,
                rationale=rationale,
                evidence_rows=evidence_rows,
                recommendation_key=key,
                confidence=confidence,
                status=status,
                source_url=source_url,
                external_id=external_id,
                extra_warnings=extra_warnings,
            )
            _store_candidate_with_evidence(config, candidate, evidence_rows)
            candidate_count += 1
            evidence_count += len(evidence_rows)
    return candidate_count, evidence_count, warnings


def import_research_recommendations(
    config: AppConfig,
    file_path: Path | None = None,
) -> RecommendationImportResult:
    path = file_path or config.research_recommendations_path
    ensure_research_recommendation_csv(path)
    warnings: list[str] = []
    imported = 0
    skipped = 0
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        for index, row in enumerate(reader, start=2):
            ticker = _clean(row.get("ticker"))
            rationale = _clean(row.get("rationale"))
            source = _clean(row.get("source")) or "codex_manual"
            status = (_clean(row.get("status")) or "pending").lower()
            if not ticker or not rationale:
                skipped += 1
                warnings.append(f"row_{index}:missing_ticker_or_rationale")
                continue
            if status not in VALID_STATUSES:
                skipped += 1
                warnings.append(f"row_{index}:unsupported_status")
                continue
            confidence = _as_float(row.get("confidence"))
            if row.get("confidence") and confidence is None:
                skipped += 1
                warnings.append(f"row_{index}:malformed_confidence")
                continue
            priority = _as_float(row.get("priority"))
            if row.get("priority") and priority is None:
                skipped += 1
                warnings.append(f"row_{index}:malformed_priority")
                continue
            recommendation_date = _clean(row.get("recommendation_date")) or _today()
            try:
                date.fromisoformat(recommendation_date[:10])
            except ValueError:
                skipped += 1
                warnings.append(f"row_{index}:malformed_recommendation_date")
                continue
            topic = _clean(row.get("topic"))
            source_url = _clean(row.get("source_url"))
            notes = _clean(row.get("notes"))
            normalized = normalize_ticker(ticker)
            key = _stable_key("research_recommendation", "codex_manual", normalized, topic or rationale)
            evidence_rows = [
                _evidence(
                    recommendation_key=key,
                    ticker=normalized,
                    evidence_date=recommendation_date[:10],
                    source=source,
                    source_type="manual_csv",
                    source_id=f"row_{index}",
                    source_url=source_url,
                    headline_or_excerpt=topic,
                    reason=notes or rationale,
                    confidence=confidence,
                )
            ]
            candidate = _candidate_from_evidence(
                config,
                ticker=normalized,
                source="codex_manual",
                topic=topic,
                rationale=rationale,
                evidence_rows=evidence_rows,
                recommendation_key=key,
                confidence=confidence,
                status=status,
                source_url=source_url,
            )
            if priority is not None:
                candidate = ResearchRecommendationCandidate(
                    **{
                        **candidate.__dict__,
                        "research_priority_score": max(0.0, min(100.0, priority)),
                    }
                )
            _store_candidate_with_evidence(config, candidate, evidence_rows)
            imported += 1
    return RecommendationImportResult(imported, skipped, tuple(warnings), path)


def generate_research_recommendations(
    config: AppConfig,
    source: str = "all",
) -> RecommendationGenerationResult:
    if source not in VALID_SOURCES:
        return RecommendationGenerationResult(source, 0, 0, ("unsupported_source",))
    total_candidates = 0
    total_evidence = 0
    warnings: list[str] = []
    if source in {"all", "tom_internal"}:
        candidates, evidence_count, source_warnings = _generate_tom_internal(config)
        total_candidates += candidates
        total_evidence += evidence_count
        warnings.extend(source_warnings)
    if source in {"all", "social_local"}:
        candidates, evidence_count, source_warnings = _generate_social_local(config)
        total_candidates += candidates
        total_evidence += evidence_count
        warnings.extend(source_warnings)
    if source in {"all", "external_research_signals"}:
        candidates, evidence_count, source_warnings = _generate_external_research_signals(config)
        total_candidates += candidates
        total_evidence += evidence_count
        warnings.extend(source_warnings)
    if source in {"all", "codex_manual"}:
        if config.research_recommendations_path.exists():
            result = import_research_recommendations(config)
            total_candidates += result.imported_count
            total_evidence += result.imported_count
            warnings.extend(result.warnings)
        elif source == "codex_manual":
            ensure_research_recommendation_csv(config.research_recommendations_path)
            warnings.append("manual_recommendation_csv_created_empty")
    return RecommendationGenerationResult(
        source=source,
        candidate_count=total_candidates,
        evidence_count=total_evidence,
        warnings=tuple(dict.fromkeys(warnings)),
    )


def research_recommendation_status(config: AppConfig) -> RecommendationStatus:
    candidates = list_research_recommendation_candidates(config.database_path)
    counts = {status: 0 for status in VALID_STATUSES}
    source_counts: dict[str, int] = {}
    for candidate in candidates:
        counts[candidate.status] = counts.get(candidate.status, 0) + 1
        source_counts[candidate.source] = source_counts.get(candidate.source, 0) + 1
    triage = research_recommendation_triage(config)
    warnings = [
        code
        for group in triage.groups
        for code in group.promotion_blockers
    ]
    top_pending = tuple(
        candidate
        for candidate in candidates
        if candidate.status in {"pending", "approved"}
    )[:10]
    return RecommendationStatus(
        total_count=len(candidates),
        pending_count=counts.get("pending", 0),
        approved_count=counts.get("approved", 0),
        approved_not_promoted_count=sum(
            1 for candidate in candidates if candidate.status == "approved"
        ),
        promoted_count=counts.get("promoted", 0),
        rejected_count=counts.get("rejected", 0),
        ignored_count=counts.get("ignored", 0),
        latest_recommendation_date=latest_research_recommendation_date(config.database_path),
        top_pending=top_pending,
        source_mix=tuple(sorted(source_counts.items())),
        warnings=tuple(dict.fromkeys(warnings)),
    )


def _code_tuple(value: str | None) -> tuple[str, ...]:
    if not value:
        return ()
    return tuple(code for code in (part.strip() for part in value.split(";")) if code)


def _candidate_research_asset_type(
    config: AppConfig,
    candidate: StoredResearchRecommendationCandidate,
) -> str:
    blockers = _code_tuple(candidate.promotion_blockers)
    asset = latest_asset(config.database_path, candidate.ticker)
    if "etf_research_ticker_requires_etf_path" in blockers:
        return "etf"
    if "foreign_equity_path_required" in blockers:
        return "foreign_equity"
    if asset and (asset.asset_type or "").strip().lower() == "etf":
        return "etf"
    if _foreign_equity_plan_resolves_missing_cik(config, candidate.ticker):
        return "foreign_equity"
    return "equity"


def _triage_classification(
    warnings: tuple[str, ...],
    promotion_blockers: tuple[str, ...],
) -> tuple[str, str]:
    if "etf_research_ticker_requires_etf_path" in promotion_blockers:
        return (
            "etf_path_required",
            "Review through the ETF/research path before changing promotion state.",
        )
    if "foreign_equity_path_required" in promotion_blockers:
        return (
            "foreign_equity_path_required",
            "Review through the foreign-equity path before changing promotion state.",
        )
    if "missing_cik_metadata" in promotion_blockers or "missing_cik_metadata" in warnings:
        return (
            "metadata_required",
            "Add or refresh metadata before promotion; review can still ignore or reject.",
        )
    if "already_scoreable" in warnings:
        return (
            "already_scoreable_context_only",
            "Use as context for an existing scoreable ticker; promotion is usually unnecessary.",
        )
    if not promotion_blockers:
        return (
            "promotion_ready_after_approval",
            "Approve only after review, then promote one recommendation with confirmation.",
        )
    return (
        "manual_review_required",
        "Review warnings, evidence, and blockers before changing status.",
    )


def research_recommendation_triage(config: AppConfig) -> RecommendationTriagePayload:
    candidates = list_research_recommendation_candidates(config.database_path)
    status_counts = {status: 0 for status in VALID_STATUSES}
    source_counts: dict[str, int] = {}
    grouped: dict[str, list[StoredResearchRecommendationCandidate]] = {}
    for candidate in candidates:
        status_counts[candidate.status] = status_counts.get(candidate.status, 0) + 1
        source_counts[candidate.source] = source_counts.get(candidate.source, 0) + 1
        if candidate.status == "pending":
            grouped.setdefault(candidate.ticker, []).append(candidate)

    groups: list[RecommendationTriageGroup] = []
    classification_counts: dict[str, int] = {}
    for ticker, ticker_candidates in sorted(
        grouped.items(),
        key=lambda item: (
            -max(candidate.research_priority_score or 0 for candidate in item[1]),
            item[0],
        ),
    ):
        recommendation_ids = tuple(
            candidate.research_recommendation_id for candidate in ticker_candidates
        )
        representative_candidate_ids = tuple(recommendation_ids[:5])
        warnings = tuple(
            dict.fromkeys(
                code
                for candidate in ticker_candidates
                for code in _code_tuple(candidate.warning_codes)
            )
        )
        promotion_blockers = tuple(
            dict.fromkeys(
                code
                for candidate in ticker_candidates
                for code in _code_tuple(candidate.promotion_blockers)
            )
        )
        if (
            "missing_cik_metadata" in promotion_blockers
            or "missing_cik_metadata" in warnings
        ) and _foreign_equity_plan_resolves_missing_cik(config, ticker):
            warnings = tuple(code for code in warnings if code != "missing_cik_metadata")
            promotion_blockers = tuple(
                code for code in promotion_blockers if code != "missing_cik_metadata"
            )
            warnings = tuple(dict.fromkeys((*warnings, "foreign_equity_identity_available")))
            promotion_blockers = tuple(
                dict.fromkeys((*promotion_blockers, "foreign_equity_path_required"))
            )
        classification, recommended_action = _triage_classification(
            warnings,
            promotion_blockers,
        )
        classification_counts[classification] = classification_counts.get(classification, 0) + 1
        groups.append(
            RecommendationTriageGroup(
                ticker=ticker,
                classification=classification,
                candidate_count=len(ticker_candidates),
                max_priority_score=max(
                    (candidate.research_priority_score or 0 for candidate in ticker_candidates),
                    default=0,
                ),
                recommendation_ids=recommendation_ids,
                representative_candidate_ids=representative_candidate_ids,
                sources=tuple(
                    sorted({candidate.source for candidate in ticker_candidates if candidate.source})
                ),
                topics=tuple(
                    sorted({candidate.topic for candidate in ticker_candidates if candidate.topic})
                ),
                warnings=warnings,
                promotion_blockers=promotion_blockers,
                recommended_action=recommended_action,
            )
        )

    return RecommendationTriagePayload(
        total_count=len(candidates),
        pending_count=status_counts.get("pending", 0),
        approved_count=status_counts.get("approved", 0),
        promoted_count=status_counts.get("promoted", 0),
        ignored_count=status_counts.get("ignored", 0),
        rejected_count=status_counts.get("rejected", 0),
        status_counts=tuple(sorted(status_counts.items())),
        source_mix=tuple(sorted(source_counts.items())),
        group_count=len(groups),
        groups=tuple(groups),
        classification_counts=tuple(sorted(classification_counts.items())),
    )


def set_research_recommendation_status(
    config: AppConfig,
    recommendation_id: int,
    status: str,
    *,
    reason: str | None = None,
) -> StoredResearchRecommendationCandidate | None:
    if status not in VALID_STATUSES:
        return None
    return update_research_recommendation_status(
        config.database_path,
        recommendation_id,
        status,
        reason=reason,
        decision_timestamp=_now(),
    )


BULK_REVIEW_STATUSES = ("pending", "approved", "ignored", "rejected")


def bulk_set_research_recommendation_status(
    config: AppConfig,
    recommendation_ids: tuple[int, ...],
    status: str,
    *,
    reason: str | None = None,
) -> RecommendationBulkStatusResult:
    normalized_status = status.strip().lower()
    normalized_ids = tuple(dict.fromkeys(int(item) for item in recommendation_ids))
    result_reason = reason or "api_bulk_status_update"
    if not normalized_ids:
        return RecommendationBulkStatusResult(
            normalized_ids,
            normalized_status,
            result_reason,
            0,
            (),
            "missing_recommendation_ids",
        )
    if normalized_status not in BULK_REVIEW_STATUSES:
        return RecommendationBulkStatusResult(
            normalized_ids,
            normalized_status,
            result_reason,
            0,
            (),
            "invalid_bulk_status",
            ("bulk_status_cannot_promote" if normalized_status == "promoted" else "unsupported_status",),
        )

    candidates = tuple(
        get_research_recommendation_candidate(
            config.database_path,
            recommendation_id=recommendation_id,
        )
        for recommendation_id in normalized_ids
    )
    missing_ids = tuple(
        recommendation_id
        for recommendation_id, candidate in zip(normalized_ids, candidates, strict=False)
        if candidate is None
    )
    if missing_ids:
        return RecommendationBulkStatusResult(
            normalized_ids,
            normalized_status,
            result_reason,
            0,
            (),
            "unknown_recommendation_ids",
            tuple(f"unknown_recommendation_id:{recommendation_id}" for recommendation_id in missing_ids),
        )

    updated: list[StoredResearchRecommendationCandidate] = []
    for recommendation_id in normalized_ids:
        candidate = set_research_recommendation_status(
            config,
            recommendation_id,
            normalized_status,
            reason=result_reason,
        )
        if candidate is not None:
            updated.append(candidate)
    return RecommendationBulkStatusResult(
        normalized_ids,
        normalized_status,
        result_reason,
        len(updated),
        tuple(updated),
    )


def promote_research_recommendation(
    config: AppConfig,
    recommendation_id: int,
    *,
    confirm: bool = False,
) -> RecommendationPromotionResult:
    candidate = get_research_recommendation_candidate(
        config.database_path, recommendation_id=recommendation_id
    )
    if candidate is None:
        return RecommendationPromotionResult(None, confirm, False, "recommendation_not_found", ())
    warnings = tuple(candidate.warning_codes.split(";")) if candidate.warning_codes else ()
    asset_type = _candidate_research_asset_type(config, candidate)
    if not confirm:
        plan = research_ticker_plan(config, candidate.ticker, asset_type=asset_type)
        if asset_type == "foreign_equity" and not plan.blocked_reason:
            blocked = None
        else:
            blocked = plan.blocked_reason or candidate.promotion_blockers
        return RecommendationPromotionResult(candidate, confirm, False, blocked, warnings)
    if candidate.status != "approved":
        return RecommendationPromotionResult(
            candidate,
            confirm,
            False,
            "recommendation_must_be_approved_before_promotion",
            warnings,
        )
    result = apply_research_ticker(config, candidate.ticker, asset_type=asset_type, confirm=True)
    if result.blocked_reason:
        return RecommendationPromotionResult(
            candidate,
            confirm,
            False,
            result.blocked_reason,
            warnings + result.warnings,
        )
    update_research_recommendation_status(
        config.database_path,
        candidate.research_recommendation_id,
        "promoted",
        reason="phase13c_confirmed_promotion",
        decision_timestamp=_now(),
    )
    promoted = get_research_recommendation_candidate(
        config.database_path, recommendation_id=recommendation_id
    )
    return RecommendationPromotionResult(promoted or candidate, confirm, True, None, warnings)


def build_research_recommendation_status_text(config: AppConfig) -> str:
    status = research_recommendation_status(config)
    triage = research_recommendation_triage(config)
    lines = [
        "Research recommendation status",
        f"Total candidates: {status.total_count}",
        f"Pending: {status.pending_count}",
        f"Approved not promoted: {status.approved_not_promoted_count}",
        f"Promoted: {status.promoted_count}",
        f"Ignored/rejected: {status.ignored_count}/{status.rejected_count}",
        f"Latest recommendation date: {status.latest_recommendation_date or 'none'}",
        "Source mix: "
        + (", ".join(f"{source}={count}" for source, count in status.source_mix) or "none"),
        "Promotion blockers: " + (", ".join(status.warnings) if status.warnings else "none"),
        "Triage groups: "
        + (
            ", ".join(
                f"{group.ticker}={group.classification}({group.candidate_count})"
                for group in triage.groups[:8]
            )
            or "none"
        ),
        "Triage classification counts: "
        + (
            ", ".join(f"{classification}={count}" for classification, count in triage.classification_counts)
            or "none"
        ),
    ]
    if status.top_pending:
        lines.append("Top pending/approved candidates:")
        for candidate in status.top_pending:
            lines.append(
                "- "
                f"#{candidate.research_recommendation_id} {candidate.ticker} "
                f"{candidate.status} score={candidate.research_priority_score or 0:.1f} "
                f"source={candidate.source} warnings={candidate.warning_codes or 'none'}"
            )
    return "\n".join(lines)


def build_research_recommendation_report(config: AppConfig) -> str:
    candidates = list_research_recommendation_candidates(config.database_path)
    lines = [
        "# Research Recommendation Queue",
        "",
        "This is a research intake queue, not a buy/sell recommendation.",
        "",
        "| ID | Ticker | Status | Priority | Source | Evidence | Warnings | Blockers | Rationale |",
        "|---:|---|---|---:|---|---:|---|---|---|",
    ]
    if not candidates:
        lines.append("| | | | | | | | |")
    for candidate in candidates[:50]:
        rationale = (candidate.rationale or "").replace("|", "/")
        lines.append(
            "| "
            f"{candidate.research_recommendation_id} | "
            f"{candidate.ticker} | "
            f"{candidate.status} | "
            f"{candidate.research_priority_score or 0:.1f} | "
            f"{candidate.source} | "
            f"{candidate.evidence_count} | "
            f"{candidate.warning_codes or ''} | "
            f"{candidate.promotion_blockers or ''} | "
            f"{rationale[:140]} |"
        )
    return "\n".join(lines)


def build_research_recommendation_promotion_text(
    config: AppConfig,
    result: RecommendationPromotionResult,
) -> str:
    if result.recommendation is None:
        return "Research recommendation promotion\nStatus: blocked\nBlocked reason: recommendation_not_found"
    lines = [
        "Research recommendation promotion",
        f"ID: {result.recommendation.research_recommendation_id}",
        f"Ticker: {result.recommendation.ticker}",
        f"Confirm: {result.confirm}",
        f"Promoted: {result.promoted}",
        f"Blocked reason: {result.blocked_reason or 'none'}",
        "Warnings: " + (", ".join(result.warnings) if result.warnings else "none"),
    ]
    if not result.confirm:
        asset_type = _candidate_research_asset_type(config, result.recommendation)
        plan = research_ticker_plan(config, result.recommendation.ticker, asset_type=asset_type)
        lines.extend(
            [
                f"Research plan ready: {plan.apply_ready}",
                f"Research plan blocker: {plan.blocked_reason or 'none'}",
                f"Research path: {plan.research_path}",
                "Next step: approve the recommendation, then rerun with --confirm.",
            ]
        )
    return "\n".join(lines)


def evidence_for_recommendation(config: AppConfig, recommendation_key: str) -> list[ResearchRecommendationEvidence]:
    return list_research_recommendation_evidence(
        config.database_path, recommendation_key=recommendation_key
    )
