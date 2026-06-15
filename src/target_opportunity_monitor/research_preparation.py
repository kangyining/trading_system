from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import date, datetime
import re
from html.parser import HTMLParser
from urllib.error import URLError
from urllib.request import Request, urlopen

from .config import AppConfig
from .etf_data import (
    ETF_HOLDING_HEADERS,
    ETF_NAV_HEADERS,
    ensure_etf_csv_headers,
    load_etf_holdings_csv,
    load_etf_navs_csv,
)
from .missing_tickers import missing_ticker_status
from .ranges import compute_range_snapshots
from .research_recommendations import (
    bulk_set_research_recommendation_status,
    research_recommendation_triage,
)
from .research_tickers import (
    EtfStrategyReview,
    ResearchTickerPlan,
    ResearchTickerStatus,
    apply_research_ticker,
    etf_strategy_review,
    refresh_research_ticker,
    research_ticker_plan,
    research_ticker_status,
)
from .scoring import compute_scores
from .storage import latest_asset, latest_pipeline_step_result, normalize_ticker
from .valuation import compute_targets


PREPARATION_SOURCES = ("pending", "missing", "all")
PREPARATION_ACTIONS = (
    "scan",
    "discover_sources",
    "stage_source_rows",
    "load_staged_sources",
    "compute_ready",
    "refresh_metadata",
    "prepare_ready",
    "ignore_already_scoreable",
    "refresh_scoreable",
    "all_safe",
)
CONTEXT_IGNORE_REASON = "prepared_already_scoreable_context"
RESEARCH_PREPARATION_AUTO_STEP_NAME = "research-preparation-auto"
ACTIONABLE_MISSING_TICKER_STATUSES = frozenset(
    {"detected", "metadata_resolved", "ready_to_onboard", "blocked"}
)

DIREXION_ETF_SOURCES = {
    "SOXL": "https://www.direxion.com/product/daily-semiconductor-bull-bear-3x-etfs",
    "KORU": "https://www.direxion.com/product/daily-msci-south-korea-bull-3x-etf",
}


@dataclass(frozen=True)
class ResearchSourceCandidate:
    ticker: str
    source_type: str
    source: str
    source_url: str
    status: str
    reason: str
    as_of_date: str | None = None
    can_stage: bool = False
    warnings: tuple[str, ...] = ()
    blockers: tuple[str, ...] = ()


@dataclass(frozen=True)
class ResearchStagedSourceRow:
    ticker: str
    row_type: str
    path: str
    row_count: int
    source: str
    source_url: str
    status: str
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class DirexionEtfEvidence:
    ticker: str
    source_url: str
    nav_date: str | None
    nav_per_share: float | None
    market_price: float | None
    holdings_date: str | None
    holdings: tuple[dict[str, object], ...]
    warnings: tuple[str, ...] = ()
    blockers: tuple[str, ...] = ()


@dataclass(frozen=True)
class ResearchPreparationItem:
    ticker: str
    source: str
    asset_type: str
    research_path: str
    preparation_state: str
    candidate_count: int
    recommendation_ids: tuple[int, ...]
    representative_candidate_ids: tuple[int, ...]
    missing_candidate_ids: tuple[int, ...] = ()
    max_priority_score: float | None = None
    sources: tuple[str, ...] = ()
    topics: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    blockers: tuple[str, ...] = ()
    recommended_action: str = ""
    action_kind: str = "manual"
    can_apply: bool = False
    can_ignore_context: bool = False
    can_refresh: bool = False
    source_candidates: tuple[ResearchSourceCandidate, ...] = ()
    staged_rows: tuple[ResearchStagedSourceRow, ...] = ()
    automation_stage: str = "scan"
    can_discover_sources: bool = False
    can_stage_sources: bool = False
    can_load_sources: bool = False
    cannot_automate_reason: str | None = None
    plan: ResearchTickerPlan | None = None
    status: ResearchTickerStatus | None = None
    strategy_review: EtfStrategyReview | None = None


@dataclass(frozen=True)
class ResearchManualBlockerPacket:
    ticker: str
    state: str
    asset_type: str
    research_path: str
    pending_recommendation_rows: int
    attempted_sources: tuple[ResearchSourceCandidate, ...]
    cannot_automate_reason: str
    required_fields: tuple[str, ...]
    blockers: tuple[str, ...]
    warnings: tuple[str, ...]
    safe_next_action: str


@dataclass(frozen=True)
class ResearchPreparationAutopilotStatus:
    enabled: bool
    source: str
    throttle_seconds: int
    due: bool
    latest_status: str | None = None
    latest_started_at: str | None = None
    latest_finished_at: str | None = None
    latest_rows_loaded: int | None = None
    latest_warnings: tuple[str, ...] = ()
    seconds_since_latest: float | None = None
    manual_blocker_count: int = 0
    manual_blocker_tickers: tuple[str, ...] = ()
    cannot_automate_reasons: tuple[tuple[str, str], ...] = ()
    applied_tickers: tuple[str, ...] = ()
    ignored_context_rows: int = 0


@dataclass(frozen=True)
class ResearchPreparationStatus:
    source: str
    total_items: int
    pending_recommendation_count: int
    ready_to_apply_count: int
    already_scoreable_count: int
    manual_blocked_count: int
    state_counts: tuple[tuple[str, int], ...]
    items: tuple[ResearchPreparationItem, ...]
    warnings: tuple[str, ...] = ()
    next_actions: tuple[str, ...] = ()
    autopilot: ResearchPreparationAutopilotStatus | None = None
    manual_blocker_packets: tuple[ResearchManualBlockerPacket, ...] = ()


@dataclass(frozen=True)
class ResearchPreparationRunResult:
    source: str
    action: str
    confirm: bool
    dry_run: bool
    ignored_count: int
    applied_count: int
    refreshed_count: int
    blocked_count: int
    updated_recommendation_ids: tuple[int, ...]
    applied_tickers: tuple[str, ...]
    refreshed_tickers: tuple[str, ...]
    status: ResearchPreparationStatus
    discovered_count: int = 0
    staged_count: int = 0
    loaded_source_count: int = 0
    computed_count: int = 0
    discovered_tickers: tuple[str, ...] = ()
    staged_tickers: tuple[str, ...] = ()
    loaded_source_tickers: tuple[str, ...] = ()
    computed_tickers: tuple[str, ...] = ()
    blocked_reason: str | None = None
    warnings: tuple[str, ...] = ()


def _codes(value: str | tuple[str, ...] | None) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, tuple):
        return tuple(code for code in value if code)
    return tuple(code for code in (part.strip() for part in value.split(";")) if code)


def _merge_codes(*values: tuple[str, ...]) -> tuple[str, ...]:
    merged: list[str] = []
    for value in values:
        for code in value:
            if code and code not in merged:
                merged.append(code)
    return tuple(merged)


def _normalize_source(source: str | None) -> str:
    normalized = (source or "pending").strip().lower()
    return normalized if normalized in PREPARATION_SOURCES else "pending"


def _normalize_ticker_filter(tickers: tuple[str, ...] | list[str] | None) -> set[str]:
    return {normalize_ticker(ticker) for ticker in tickers or () if str(ticker).strip()}


def _display_path(config: AppConfig, path) -> str:
    try:
        return str(path.relative_to(config.project_root))
    except ValueError:
        return str(path)


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        cleaned = " ".join(data.split())
        if cleaned:
            self.parts.append(cleaned)


def _html_to_lines(html: str) -> list[str]:
    parser = _TextExtractor()
    parser.feed(html)
    return parser.parts


def _parse_display_date(value: str | None) -> str | None:
    if not value:
        return None
    cleaned = " ".join(value.replace("\xa0", " ").split())
    for fmt in ("%b %d, %Y", "%B %d, %Y", "%m/%d/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(cleaned, fmt).date().isoformat()
        except ValueError:
            continue
    return None


def _money_after(label: str, text: str) -> float | None:
    pattern = re.compile(rf"{re.escape(label)}\s*\$?\s*([0-9][0-9,]*(?:\.[0-9]+)?)", re.IGNORECASE)
    match = pattern.search(text)
    if match is None:
        return None
    return float(match.group(1).replace(",", ""))


def _date_after(label: str, text: str) -> str | None:
    pattern = re.compile(
        rf"{re.escape(label)}.*?As of\s+([A-Za-z]+\s+\d{{1,2}},\s+\d{{4}})",
        re.IGNORECASE | re.DOTALL,
    )
    match = pattern.search(text)
    return _parse_display_date(match.group(1)) if match else None


def _index_top_holdings(lines: list[str]) -> tuple[dict[str, object], ...]:
    try:
        start = next(index for index, line in enumerate(lines) if line.lower() == "index top ten holdings")
    except StopIteration:
        return ()
    end = len(lines)
    for index in range(start + 1, len(lines)):
        if lines[index].lower().startswith("view all index holdings"):
            end = index
            break
    holdings: list[dict[str, object]] = []
    section = lines[start + 1 : end]
    for index, line in enumerate(section):
        weight_text = ""
        name_end = index
        if line == "%" and index > 0:
            weight_text = section[index - 1]
            name_end = index - 1
        elif line.endswith("%"):
            weight_text = line.rstrip("%")
        if not weight_text:
            continue
        try:
            weight = float(weight_text.replace(",", "")) / 100.0
        except ValueError:
            continue
        name = None
        for previous in reversed(section[:name_end]):
            lowered = previous.lower()
            if previous == "%" or previous.endswith("%") or lowered in {"% of total", "index top ten holdings"}:
                continue
            try:
                float(previous.replace(",", ""))
                continue
            except ValueError:
                pass
            if previous.startswith(".css-"):
                continue
            name = previous
            break
        if name:
            holdings.append(
                {
                    "holding_name": name,
                    "holding_asset_type": "equity",
                    "weight": weight,
                    "source": "direxion_official_index_holdings",
                }
            )
    return tuple(holdings[:10])


def _fetch_direxion_etf_evidence(config: AppConfig, ticker: str) -> DirexionEtfEvidence:
    normalized = normalize_ticker(ticker)
    source_url = DIREXION_ETF_SOURCES.get(normalized)
    if not source_url:
        return DirexionEtfEvidence(
            ticker=normalized,
            source_url="",
            nav_date=None,
            nav_per_share=None,
            market_price=None,
            holdings_date=None,
            holdings=(),
            blockers=("no_allowlisted_etf_source_adapter",),
        )
    try:
        request = Request(
            source_url,
            headers={
                "User-Agent": config.sec_user_agent,
                "Accept": "text/html,application/xhtml+xml",
            },
        )
        with urlopen(request, timeout=30) as response:
            html = response.read().decode("utf-8", "ignore")
    except (OSError, URLError) as error:
        return DirexionEtfEvidence(
            ticker=normalized,
            source_url=source_url,
            nav_date=None,
            nav_per_share=None,
            market_price=None,
            holdings_date=None,
            holdings=(),
            blockers=(f"direxion_fetch_failed:{type(error).__name__}",),
        )

    lines = _html_to_lines(html)
    text = "\n".join(lines)
    nav_per_share = _money_after("NAV (Net Asset Value)", text) or _money_after("Daily NAV", text)
    market_price = _money_after("Daily Market Price", text)
    nav_date = _date_after("NAV (Net Asset Value)", text)
    holdings = _index_top_holdings(lines)
    holdings_date_match = re.search(r"Index data as of\s+([0-9]{2}/[0-9]{2}/[0-9]{4})", text, re.IGNORECASE)
    holdings_date = _parse_display_date(holdings_date_match.group(1)) if holdings_date_match else nav_date
    blockers: list[str] = []
    warnings: list[str] = []
    if nav_per_share is None or nav_date is None:
        blockers.append("direxion_nav_not_found")
    if len(holdings) < config.etf_minimum_holdings:
        blockers.append("direxion_holdings_not_found")
    elif holdings:
        warnings.append("direxion_index_holdings_used_as_reference")
    return DirexionEtfEvidence(
        ticker=normalized,
        source_url=source_url,
        nav_date=nav_date,
        nav_per_share=nav_per_share,
        market_price=market_price,
        holdings_date=holdings_date,
        holdings=holdings,
        warnings=tuple(warnings),
        blockers=tuple(blockers),
    )


def _source_candidates_for_item(item: ResearchPreparationItem) -> tuple[ResearchSourceCandidate, ...]:
    if item.asset_type == "etf" and item.ticker in DIREXION_ETF_SOURCES:
        return (
            ResearchSourceCandidate(
                ticker=item.ticker,
                source_type="etf_issuer",
                source="direxion_official_page",
                source_url=DIREXION_ETF_SOURCES[item.ticker],
                status="available_adapter",
                reason="Allowlisted Direxion ETF source can be checked and staged with confirmation.",
                can_stage=True,
            ),
        )
    if item.asset_type == "etf":
        return (
            ResearchSourceCandidate(
                ticker=item.ticker,
                source_type="etf_issuer",
                source="manual_source_required",
                source_url="",
                status="no_adapter",
                reason="No allowlisted ETF issuer adapter exists for this ticker.",
                can_stage=False,
                blockers=("no_allowlisted_etf_source_adapter",),
            ),
        )
    if item.preparation_state in {"identity_required", "metadata_required"}:
        return (
            ResearchSourceCandidate(
                ticker=item.ticker,
                source_type="equity_metadata",
                source="sec_fmp_metadata_refresh",
                source_url="https://www.sec.gov/files/company_tickers_exchange.json",
                status="refresh_available",
                reason="SEC/FMP metadata refresh can run, but ambiguous or foreign aliases still require source-backed review.",
                can_stage=False,
            ),
        )
    return ()


def _cannot_automate_reason(item: ResearchPreparationItem) -> str | None:
    if item.can_apply or item.can_ignore_context or item.can_refresh:
        return None
    if item.asset_type == "etf" and item.ticker not in DIREXION_ETF_SOURCES:
        return "no_allowlisted_etf_source_adapter"
    if item.preparation_state == "source_data_required":
        return "source_backed_data_required"
    if item.preparation_state == "identity_required":
        return "source_backed_identity_required"
    if item.preparation_state == "metadata_required":
        return "source_backed_metadata_required"
    if item.preparation_state == "evidence_gated":
        return "evidence_gate_not_matured"
    if item.preparation_state == "manual_review_required":
        return "manual_review_decision_required"
    return None


def _required_fields_for_item(item: ResearchPreparationItem) -> tuple[str, ...]:
    if item.preparation_state == "identity_required":
        return (
            "source_backed_current_listing",
            "ticker_identity",
            "cik_or_source_backed_identity",
            "sector",
            "industry",
        )
    if item.preparation_state == "metadata_required":
        return ("source_backed_sector", "source_backed_industry")
    if item.preparation_state == "source_data_required":
        if item.asset_type == "etf":
            return (
                "source_backed_etf_nav",
                "source_backed_etf_holdings",
                "etf_feature",
                "target",
                "score",
                "range_snapshot",
                "option_chain_availability",
            )
        return ("source_backed_data",)
    if item.preparation_state == "manual_review_required":
        return ("explicit_user_review_decision",)
    if item.preparation_state == "evidence_gated":
        return ("matured_validation_evidence",)
    return item.blockers


def _manual_blocker_packets(
    items: tuple[ResearchPreparationItem, ...],
) -> tuple[ResearchManualBlockerPacket, ...]:
    packets: list[ResearchManualBlockerPacket] = []
    for item in items:
        reason = item.cannot_automate_reason
        if not reason:
            continue
        packets.append(
            ResearchManualBlockerPacket(
                ticker=item.ticker,
                state=item.preparation_state,
                asset_type=item.asset_type,
                research_path=item.research_path,
                pending_recommendation_rows=item.candidate_count
                if item.recommendation_ids
                else 0,
                attempted_sources=item.source_candidates,
                cannot_automate_reason=reason,
                required_fields=_required_fields_for_item(item),
                blockers=item.blockers,
                warnings=item.warnings,
                safe_next_action=item.recommended_action,
            )
        )
    return tuple(packets)


def _parse_step_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _split_step_warnings(value: str | None) -> tuple[str, ...]:
    if not value:
        return ()
    return tuple(part.strip() for part in value.split(",") if part.strip())


def _extract_warning_suffix(warnings: tuple[str, ...], prefix: str) -> tuple[str, ...]:
    values: list[str] = []
    for warning in warnings:
        if warning.startswith(prefix):
            values.extend(part for part in re.split(r"[|,]", warning[len(prefix) :]) if part)
    return tuple(dict.fromkeys(values))


def _autopilot_due_from_latest(
    config: AppConfig,
    latest_finished_at: str | None,
    *,
    now: datetime | None = None,
) -> tuple[bool, float | None]:
    if not config.research_preparation_auto_enabled:
        return False, None
    finished = _parse_step_datetime(latest_finished_at)
    if finished is None:
        return True, None
    current = now or datetime.now()
    if current.tzinfo is not None and finished.tzinfo is None:
        finished = finished.replace(tzinfo=current.tzinfo)
    if current.tzinfo is None and finished.tzinfo is not None:
        current = current.replace(tzinfo=finished.tzinfo)
    age = max(0.0, (current - finished).total_seconds())
    return age >= config.research_preparation_auto_min_seconds_between_runs, age


def _build_autopilot_status(
    config: AppConfig,
    source: str,
    items: tuple[ResearchPreparationItem, ...],
    manual_packets: tuple[ResearchManualBlockerPacket, ...],
    *,
    now: datetime | None = None,
) -> ResearchPreparationAutopilotStatus:
    latest = latest_pipeline_step_result(
        config.database_path,
        RESEARCH_PREPARATION_AUTO_STEP_NAME,
    )
    warnings = _split_step_warnings(latest.warnings if latest else None)
    due, seconds_since_latest = _autopilot_due_from_latest(
        config,
        latest.finished_at if latest else None,
        now=now,
    )
    blocker_tickers = tuple(packet.ticker for packet in manual_packets)
    cannot_reasons = tuple(
        (packet.ticker, packet.cannot_automate_reason) for packet in manual_packets
    )
    return ResearchPreparationAutopilotStatus(
        enabled=config.research_preparation_auto_enabled,
        source=source,
        throttle_seconds=config.research_preparation_auto_min_seconds_between_runs,
        due=due,
        latest_status=latest.status if latest else None,
        latest_started_at=latest.started_at if latest else None,
        latest_finished_at=latest.finished_at if latest else None,
        latest_rows_loaded=latest.rows_loaded if latest else None,
        latest_warnings=warnings,
        seconds_since_latest=seconds_since_latest,
        manual_blocker_count=len(manual_packets),
        manual_blocker_tickers=blocker_tickers,
        cannot_automate_reasons=cannot_reasons,
        applied_tickers=_extract_warning_suffix(warnings, "applied:"),
        ignored_context_rows=len(
            _extract_warning_suffix(warnings, "ignored_recommendation_ids:")
        ),
    )


def _existing_staged_rows_for_item(config: AppConfig, item: ResearchPreparationItem) -> tuple[ResearchStagedSourceRow, ...]:
    staged: list[ResearchStagedSourceRow] = []
    for path, row_type in (
        (config.etf_navs_path, "etf_nav"),
        (config.etf_holdings_path, "etf_holding"),
    ):
        if not path.exists():
            continue
        try:
            with path.open("r", encoding="utf-8-sig", newline="") as input_file:
                rows = [
                    row
                    for row in csv.DictReader(input_file)
                    if normalize_ticker(row.get("ticker", "")) == item.ticker
                ]
        except OSError:
            continue
        if rows:
            staged.append(
                ResearchStagedSourceRow(
                    ticker=item.ticker,
                    row_type=row_type,
                    path=_display_path(config, path),
                    row_count=len(rows),
                    source=rows[-1].get("source", "") or "unknown",
                    source_url="",
                    status="staged",
                )
            )
    return tuple(staged)


def _with_automation_fields(
    config: AppConfig,
    item: ResearchPreparationItem,
) -> ResearchPreparationItem:
    source_candidates = _source_candidates_for_item(item)
    staged_rows = _existing_staged_rows_for_item(config, item)
    can_stage = any(candidate.can_stage for candidate in source_candidates)
    can_load = bool(staged_rows)
    automation_stage = "ready_for_manual_review"
    if item.can_apply:
        automation_stage = "ready_to_apply"
    elif can_load:
        automation_stage = "staged_sources_available"
    elif can_stage:
        automation_stage = "source_discovery_available"
    elif item.can_ignore_context:
        automation_stage = "context_cleanup_available"
    elif item.action_kind == "manual":
        automation_stage = "manual_input_required"
    return ResearchPreparationItem(
        **{
            **item.__dict__,
            "source_candidates": source_candidates,
            "staged_rows": staged_rows,
            "automation_stage": automation_stage,
            "can_discover_sources": bool(source_candidates),
            "can_stage_sources": can_stage,
            "can_load_sources": can_load,
            "cannot_automate_reason": _cannot_automate_reason(item),
        }
    )


def _asset_type_for_pending_group(config: AppConfig, group) -> str:
    asset = latest_asset(config.database_path, group.ticker)
    blockers = set(group.promotion_blockers)
    if "etf_research_ticker_requires_etf_path" in blockers:
        return "etf"
    if "foreign_equity_path_required" in blockers:
        return "foreign_equity"
    if asset and (asset.asset_type or "").strip().lower() == "etf":
        return "etf"
    foreign_plan = research_ticker_plan(config, group.ticker, asset_type="foreign_equity")
    if not foreign_plan.readiness_blockers and foreign_plan.blocked_reason in {None, "ticker_already_scoreable"}:
        return "foreign_equity"
    return "equity"


def _asset_type_for_missing_candidate(config: AppConfig, candidate) -> str:
    asset = latest_asset(config.database_path, candidate.ticker)
    detected = (candidate.detected_asset_type or "").strip().lower()
    if detected in {"etf", "fund"}:
        return "etf"
    if asset and (asset.asset_type or "").strip().lower() == "etf":
        return "etf"
    return "equity"


def _classify_item(
    *,
    plan: ResearchTickerPlan,
    status: ResearchTickerStatus,
    triage_classification: str | None,
    group_warnings: tuple[str, ...],
    group_blockers: tuple[str, ...],
) -> tuple[str, str, str, bool, bool, bool]:
    if (
        plan.blocked_reason == "ticker_already_scoreable"
        or triage_classification == "already_scoreable_context_only"
        or "already_scoreable" in group_warnings
    ):
        return (
            "prepared_already_scoreable",
            "Confirm-ignore context-only recommendation rows; promotion is unnecessary.",
            "confirmable",
            False,
            True,
            bool(status.asset),
        )
    if plan.apply_ready:
        return (
            "ready_to_apply",
            "Confirm preparation apply to make this ticker scoreable; review and promotion stay separate.",
            "confirmable",
            True,
            False,
            False,
        )
    if plan.blocked_reason in {"etf_readiness_required", "etf_reference_asset_required"}:
        return (
            "source_data_required",
            "Supply source-backed ETF readiness data before preparation can continue.",
            "manual",
            False,
            False,
            False,
        )
    if plan.blocked_reason in {"missing_sector", "missing_industry"}:
        return (
            "metadata_required",
            "Add source-backed sector and industry metadata, then rerun preparation.",
            "manual",
            False,
            False,
            False,
        )
    if plan.blocked_reason == "missing_cik":
        state = "identity_required" if not plan.metadata.name and not plan.metadata.cik else "metadata_required"
        return (
            state,
            "Confirm ticker identity and source-backed equity metadata before preparation can continue.",
            "manual",
            False,
            False,
            False,
        )
    if any("evidence" in code for code in group_blockers):
        return (
            "evidence_gated",
            "Wait for configured evidence gates; preparation cannot bypass them.",
            "manual",
            False,
            False,
            False,
        )
    if group_blockers:
        return (
            "manual_review_required",
            "Review the remaining blockers before changing review or promotion state.",
            "manual",
            False,
            False,
            False,
        )
    return (
        "blocked",
        "Preparation is blocked; inspect ticker plan and status details.",
        "manual",
        False,
        False,
        False,
    )


def _pending_preparation_items(config: AppConfig) -> list[ResearchPreparationItem]:
    triage = research_recommendation_triage(config)
    items: list[ResearchPreparationItem] = []
    for group in triage.groups:
        asset_type = _asset_type_for_pending_group(config, group)
        plan = research_ticker_plan(config, group.ticker, asset_type=asset_type)
        status = research_ticker_status(config, group.ticker)
        strategy = etf_strategy_review(config, group.ticker) if plan.asset_type == "etf" else None
        group_blockers = group.promotion_blockers
        group_warnings = group.warnings
        if plan.asset_type == "foreign_equity" and plan.apply_ready:
            group_blockers = tuple(
                code for code in group_blockers if code != "missing_cik_metadata"
            )
            group_warnings = tuple(
                code for code in group_warnings if code != "missing_cik_metadata"
            )
        state, action, action_kind, can_apply, can_ignore, can_refresh = _classify_item(
            plan=plan,
            status=status,
            triage_classification=group.classification,
            group_warnings=group_warnings,
            group_blockers=group_blockers,
        )
        blockers = _merge_codes(
            (plan.blocked_reason,) if plan.blocked_reason else (),
            plan.readiness_blockers,
            group_blockers,
            status.readiness_blockers,
        )
        warnings = _merge_codes(group_warnings, plan.warnings)
        items.append(
            _with_automation_fields(
                config,
                ResearchPreparationItem(
                    ticker=group.ticker,
                    source="pending_recommendations",
                    asset_type=plan.asset_type,
                    research_path=plan.research_path,
                    preparation_state=state,
                    candidate_count=group.candidate_count,
                    recommendation_ids=group.recommendation_ids,
                    representative_candidate_ids=group.representative_candidate_ids,
                    max_priority_score=group.max_priority_score,
                    sources=group.sources,
                    topics=group.topics,
                    warnings=warnings,
                    blockers=blockers,
                    recommended_action=action,
                    action_kind=action_kind,
                    can_apply=can_apply,
                    can_ignore_context=can_ignore,
                    can_refresh=can_refresh,
                    plan=plan,
                    status=status,
                    strategy_review=strategy,
                ),
            )
        )
    return items


def _missing_preparation_items(config: AppConfig, existing_tickers: set[str]) -> list[ResearchPreparationItem]:
    status = missing_ticker_status(config)
    items: list[ResearchPreparationItem] = []
    for candidate in status.candidates:
        ticker = normalize_ticker(candidate.ticker)
        if ticker in existing_tickers:
            continue
        if candidate.status not in ACTIONABLE_MISSING_TICKER_STATUSES:
            continue
        asset_type = _asset_type_for_missing_candidate(config, candidate)
        plan = research_ticker_plan(config, ticker, asset_type=asset_type)
        ticker_status = research_ticker_status(config, ticker)
        state, action, action_kind, can_apply, can_ignore, can_refresh = _classify_item(
            plan=plan,
            status=ticker_status,
            triage_classification=None,
            group_warnings=_codes(candidate.warnings),
            group_blockers=_codes(candidate.blockers),
        )
        if can_ignore:
            can_ignore = False
            action_kind = "none"
            action = "No pending recommendation rows to update; already represented by an existing scoreable asset."
        blockers = _merge_codes(
            _codes(candidate.blockers),
            (plan.blocked_reason,) if plan.blocked_reason else (),
            plan.readiness_blockers,
            ticker_status.readiness_blockers,
        )
        warnings = _merge_codes(_codes(candidate.warnings), plan.warnings)
        missing_id = candidate.missing_ticker_candidate_id
        items.append(
            _with_automation_fields(
                config,
                ResearchPreparationItem(
                    ticker=ticker,
                    source=f"missing_tickers:{candidate.first_seen_source}",
                    asset_type=plan.asset_type,
                    research_path=plan.research_path,
                    preparation_state=state,
                    candidate_count=1,
                    recommendation_ids=(),
                    representative_candidate_ids=(),
                    missing_candidate_ids=(missing_id,) if missing_id is not None else (),
                    sources=(candidate.first_seen_source,),
                    warnings=warnings,
                    blockers=blockers,
                    recommended_action=action,
                    action_kind=action_kind,
                    can_apply=can_apply,
                    can_ignore_context=can_ignore,
                    can_refresh=can_refresh,
                    plan=plan,
                    status=ticker_status,
                    strategy_review=etf_strategy_review(config, ticker) if plan.asset_type == "etf" else None,
                ),
            )
        )
    return items


def research_preparation_status(
    config: AppConfig,
    source: str | None = None,
    tickers: tuple[str, ...] | list[str] | None = None,
    *,
    include_autopilot: bool = True,
) -> ResearchPreparationStatus:
    normalized_source = _normalize_source(source)
    ticker_filter = _normalize_ticker_filter(tickers)
    items: list[ResearchPreparationItem] = []
    if normalized_source in {"pending", "all"}:
        items.extend(_pending_preparation_items(config))
    if normalized_source in {"missing", "all"}:
        existing = {item.ticker for item in items}
        items.extend(_missing_preparation_items(config, existing))
    if ticker_filter:
        items = [item for item in items if item.ticker in ticker_filter]

    state_counts: dict[str, int] = {}
    for item in items:
        state_counts[item.preparation_state] = state_counts.get(item.preparation_state, 0) + 1
    next_actions: list[str] = []
    if any(item.can_apply for item in items):
        next_actions.append("python -m target_opportunity_monitor research-preparation-run --action prepare_ready --confirm")
    if any(item.can_ignore_context for item in items):
        next_actions.append(
            "python -m target_opportunity_monitor research-preparation-run --action ignore_already_scoreable --confirm"
        )
    if any(item.preparation_state in {"metadata_required", "identity_required"} for item in items):
        next_actions.append(
            "python -m target_opportunity_monitor research-preparation-run --action refresh_metadata --confirm"
        )
    if any(item.can_stage_sources for item in items):
        next_actions.append(
            "python -m target_opportunity_monitor research-preparation-run --action stage_source_rows --confirm"
        )
    if any(item.can_load_sources for item in items):
        next_actions.append(
            "python -m target_opportunity_monitor research-preparation-run --action load_staged_sources --confirm"
        )
    if any(item.preparation_state in {"source_data_required", "metadata_required", "identity_required"} for item in items):
        next_actions.append("Add source-backed data for manual blockers, then rerun research-preparation-run.")

    prepared_items = tuple(items)
    manual_packets = _manual_blocker_packets(prepared_items)
    autopilot = (
        _build_autopilot_status(config, normalized_source, prepared_items, manual_packets)
        if include_autopilot
        else None
    )
    return ResearchPreparationStatus(
        source=normalized_source,
        total_items=len(prepared_items),
        pending_recommendation_count=sum(item.candidate_count for item in prepared_items if item.recommendation_ids),
        ready_to_apply_count=sum(1 for item in prepared_items if item.can_apply),
        already_scoreable_count=sum(1 for item in prepared_items if item.can_ignore_context),
        manual_blocked_count=sum(1 for item in prepared_items if item.action_kind == "manual"),
        state_counts=tuple(sorted(state_counts.items())),
        items=prepared_items,
        next_actions=tuple(next_actions),
        autopilot=autopilot,
        manual_blocker_packets=manual_packets,
    )


def _apply_ready_items(config: AppConfig, items: tuple[ResearchPreparationItem, ...], *, confirm: bool) -> tuple[int, tuple[str, ...], tuple[str, ...]]:
    applied: list[str] = []
    warnings: list[str] = []
    for item in items:
        if not item.can_apply:
            continue
        if not confirm:
            warnings.append(f"dry_run_apply_ready:{item.ticker}")
            continue
        result = apply_research_ticker(config, item.ticker, asset_type=item.asset_type, confirm=True)
        if result.applied:
            applied.append(item.ticker)
        elif result.blocked_reason:
            warnings.append(f"{item.ticker}:{result.blocked_reason}")
    return len(applied), tuple(applied), tuple(warnings)


def _ignore_already_scoreable_items(
    config: AppConfig,
    items: tuple[ResearchPreparationItem, ...],
    *,
    confirm: bool,
) -> tuple[int, tuple[int, ...], tuple[str, ...]]:
    ids: list[int] = []
    for item in items:
        if item.can_ignore_context:
            ids.extend(item.recommendation_ids)
    normalized_ids = tuple(dict.fromkeys(ids))
    if not normalized_ids:
        return 0, (), ()
    if not confirm:
        return 0, (), tuple(f"dry_run_ignore_context:{recommendation_id}" for recommendation_id in normalized_ids)
    result = bulk_set_research_recommendation_status(
        config,
        normalized_ids,
        "ignored",
        reason=CONTEXT_IGNORE_REASON,
    )
    warnings = result.warnings
    if result.blocked_reason:
        warnings = _merge_codes(warnings, (result.blocked_reason,))
    return result.updated_count, tuple(candidate.research_recommendation_id for candidate in result.updated_candidates), warnings


def _refresh_scoreable_items(
    config: AppConfig,
    items: tuple[ResearchPreparationItem, ...],
    *,
    confirm: bool,
) -> tuple[int, tuple[str, ...], tuple[str, ...]]:
    refreshed: list[str] = []
    warnings: list[str] = []
    for item in items:
        if not item.can_refresh:
            continue
        if not confirm:
            warnings.append(f"dry_run_refresh_scoreable:{item.ticker}")
            continue
        result, blockers = refresh_research_ticker(config, item.ticker)
        if result is None:
            warnings.append(f"{item.ticker}:research_ticker_refresh_blocked")
            warnings.extend(f"{item.ticker}:{blocker}" for blocker in blockers)
        else:
            refreshed.append(item.ticker)
            warnings.extend(f"{item.ticker}:{blocker}" for blocker in blockers)
    return len(refreshed), tuple(refreshed), tuple(dict.fromkeys(warnings))


def _refresh_metadata_items(
    config: AppConfig,
    items: tuple[ResearchPreparationItem, ...],
    *,
    confirm: bool,
) -> tuple[int, tuple[str, ...], tuple[str, ...]]:
    refreshed: list[str] = []
    warnings: list[str] = []
    for item in items:
        if item.asset_type != "equity" or item.preparation_state not in {"metadata_required", "identity_required"}:
            continue
        if not confirm:
            warnings.append(f"dry_run_refresh_metadata:{item.ticker}")
            continue
        plan = research_ticker_plan(
            config,
            item.ticker,
            asset_type="equity",
            refresh_metadata=True,
        )
        refreshed.append(item.ticker)
        if plan.blocked_reason:
            warnings.append(f"{item.ticker}:{plan.blocked_reason}")
        warnings.extend(f"{item.ticker}:{warning}" for warning in plan.warnings)
    return len(refreshed), tuple(refreshed), tuple(dict.fromkeys(warnings))


def _read_csv_rows(path, headers: tuple[str, ...]) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as input_file:
        return [dict(row) for row in csv.DictReader(input_file)]


def _write_csv_rows(path, headers: tuple[str, ...], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as output_file:
        writer = csv.DictWriter(output_file, fieldnames=headers)
        writer.writeheader()
        for row in rows:
            writer.writerow({header: row.get(header, "") for header in headers})


def _replace_csv_rows(
    path,
    headers: tuple[str, ...],
    new_rows: list[dict[str, str]],
    key_fields: tuple[str, ...],
) -> int:
    existing = _read_csv_rows(path, headers)
    new_keys = {
        tuple(normalize_ticker(row.get(field, "")) if field == "ticker" else row.get(field, "") for field in key_fields)
        for row in new_rows
    }
    kept = [
        row
        for row in existing
        if tuple(
            normalize_ticker(row.get(field, "")) if field == "ticker" else row.get(field, "")
            for field in key_fields
        )
        not in new_keys
    ]
    _write_csv_rows(path, headers, kept + new_rows)
    return len(new_rows)


def _stage_direxion_etf_rows(
    config: AppConfig,
    item: ResearchPreparationItem,
    *,
    confirm: bool,
) -> tuple[int, tuple[str, ...], tuple[ResearchStagedSourceRow, ...], tuple[str, ...]]:
    evidence = _fetch_direxion_etf_evidence(config, item.ticker)
    warnings = [f"{item.ticker}:{warning}" for warning in evidence.warnings]
    if evidence.blockers:
        warnings.extend(f"{item.ticker}:{blocker}" for blocker in evidence.blockers)
        return 0, (), (), tuple(dict.fromkeys(warnings))
    if not confirm:
        return 0, (), (), (f"dry_run_stage_sources:{item.ticker}", *tuple(dict.fromkeys(warnings)))

    ensure_etf_csv_headers(config.etf_navs_path, config.etf_holdings_path)
    today = date.today().isoformat()
    nav_rows = [
        {
            "ticker": item.ticker,
            "nav_date": evidence.nav_date or today,
            "nav_per_share": str(evidence.nav_per_share or ""),
            "market_price": str(evidence.market_price or ""),
            "premium_discount": (
                str(evidence.market_price / evidence.nav_per_share - 1)
                if evidence.market_price is not None
                and evidence.nav_per_share is not None
                and evidence.nav_per_share > 0
                else ""
            ),
            "shares_outstanding": "",
            "net_assets": "",
            "source": "direxion_official_page",
            "as_of_date": today,
            "effective_date": today,
        }
    ]
    holding_rows = [
        {
            "ticker": item.ticker,
            "holdings_date": evidence.holdings_date or evidence.nav_date or today,
            "holding_ticker": str(holding.get("holding_ticker") or ""),
            "holding_name": str(holding.get("holding_name") or ""),
            "holding_asset_type": str(holding.get("holding_asset_type") or "equity"),
            "weight": str(holding.get("weight") or ""),
            "shares": "",
            "market_value": "",
            "sector": "",
            "country": "",
            "source": str(holding.get("source") or "direxion_official_page"),
            "as_of_date": today,
            "effective_date": today,
        }
        for holding in evidence.holdings
    ]
    nav_count = _replace_csv_rows(
        config.etf_navs_path,
        ETF_NAV_HEADERS,
        nav_rows,
        ("ticker", "nav_date", "source"),
    )
    holding_count = _replace_csv_rows(
        config.etf_holdings_path,
        ETF_HOLDING_HEADERS,
        holding_rows,
        ("ticker", "holdings_date", "holding_name", "source"),
    )
    staged_rows = (
        ResearchStagedSourceRow(
            ticker=item.ticker,
            row_type="etf_nav",
            path=_display_path(config, config.etf_navs_path),
            row_count=nav_count,
            source="direxion_official_page",
            source_url=evidence.source_url,
            status="staged",
        ),
        ResearchStagedSourceRow(
            ticker=item.ticker,
            row_type="etf_holding",
            path=_display_path(config, config.etf_holdings_path),
            row_count=holding_count,
            source="direxion_official_page",
            source_url=evidence.source_url,
            status="staged",
            warnings=tuple(evidence.warnings),
        ),
    )
    return nav_count + holding_count, (item.ticker,), staged_rows, tuple(dict.fromkeys(warnings))


def _discover_source_items(
    config: AppConfig,
    items: tuple[ResearchPreparationItem, ...],
) -> tuple[int, tuple[str, ...], tuple[str, ...]]:
    discovered: list[str] = []
    warnings: list[str] = []
    for item in items:
        if not item.can_discover_sources:
            continue
        if item.asset_type == "etf" and item.ticker in DIREXION_ETF_SOURCES:
            evidence = _fetch_direxion_etf_evidence(config, item.ticker)
            if evidence.nav_per_share is not None or evidence.holdings:
                discovered.append(item.ticker)
            warnings.extend(f"{item.ticker}:{warning}" for warning in evidence.warnings)
            warnings.extend(f"{item.ticker}:{blocker}" for blocker in evidence.blockers)
        elif item.asset_type == "equity":
            warnings.append(f"{item.ticker}:metadata_refresh_available_identity_not_staged")
    return len(tuple(dict.fromkeys(discovered))), tuple(dict.fromkeys(discovered)), tuple(dict.fromkeys(warnings))


def _stage_source_items(
    config: AppConfig,
    items: tuple[ResearchPreparationItem, ...],
    *,
    confirm: bool,
) -> tuple[int, tuple[str, ...], tuple[str, ...]]:
    staged_count = 0
    staged_tickers: list[str] = []
    warnings: list[str] = []
    if not confirm:
        return (
            0,
            (),
            tuple(f"dry_run_stage_sources:{item.ticker}" for item in items if item.can_stage_sources),
        )
    for item in items:
        if not item.can_stage_sources:
            continue
        if item.asset_type == "etf" and item.ticker in DIREXION_ETF_SOURCES:
            count, tickers, _rows, item_warnings = _stage_direxion_etf_rows(
                config,
                item,
                confirm=confirm,
            )
            staged_count += count
            staged_tickers.extend(tickers)
            warnings.extend(item_warnings)
        else:
            warnings.append(f"{item.ticker}:source_staging_not_supported")
    return staged_count, tuple(dict.fromkeys(staged_tickers)), tuple(dict.fromkeys(warnings))


def _load_staged_source_items(
    config: AppConfig,
    items: tuple[ResearchPreparationItem, ...],
    *,
    confirm: bool,
) -> tuple[int, tuple[str, ...], tuple[str, ...]]:
    load_tickers = tuple(sorted({item.ticker for item in items if item.can_load_sources}))
    if not load_tickers:
        return 0, (), ()
    if not confirm:
        return 0, (), tuple(f"dry_run_load_staged_sources:{ticker}" for ticker in load_tickers)
    warnings: list[str] = []
    loaded_tickers: list[str] = []
    loaded_count = 0
    try:
        nav_result = load_etf_navs_csv(config.database_path, config.etf_navs_path)
        holding_result = load_etf_holdings_csv(config.database_path, config.etf_holdings_path)
    except (OSError, ValueError) as error:
        return 0, (), (f"load_staged_sources_failed:{type(error).__name__}",)
    for ticker in load_tickers:
        if ticker in nav_result.tickers or ticker in holding_result.tickers:
            loaded_tickers.append(ticker)
    loaded_count = nav_result.loaded_count + holding_result.loaded_count
    if not loaded_tickers:
        warnings.append("no_selected_staged_sources_loaded")
    return loaded_count, tuple(dict.fromkeys(loaded_tickers)), tuple(dict.fromkeys(warnings))


def _compute_ready_items(
    config: AppConfig,
    items: tuple[ResearchPreparationItem, ...],
    *,
    confirm: bool,
) -> tuple[int, tuple[str, ...], tuple[str, ...]]:
    compute_tickers = tuple(sorted({item.ticker for item in items if item.asset_type == "etf"}))
    if not compute_tickers:
        return 0, (), ()
    if not confirm:
        return 0, (), tuple(f"dry_run_compute_ready:{ticker}" for ticker in compute_tickers)
    computed: list[str] = []
    warnings: list[str] = []
    for ticker in compute_tickers:
        target_result = compute_targets(config, ticker=ticker)
        score_result = compute_scores(config, ticker=ticker, asset_type="etf")
        range_result = compute_range_snapshots(config, ticker=ticker, create_notifications=False)
        target_rows = [row for row in target_result.results if row.ticker == ticker and row.status == "computed"]
        score_rows = [row for row in score_result.results if row.ticker == ticker and row.status == "computed"]
        range_rows = [row for row in range_result.results if row.ticker == ticker]
        if target_rows or score_rows or range_rows:
            computed.append(ticker)
        for result in (*target_result.results, *score_result.results, *range_result.results):
            if getattr(result, "ticker", None) != ticker:
                continue
            warnings.extend(f"{ticker}:{warning}" for warning in getattr(result, "warnings", ()) or ())
    return len(tuple(dict.fromkeys(computed))), tuple(dict.fromkeys(computed)), tuple(dict.fromkeys(warnings))


def run_research_preparation(
    config: AppConfig,
    *,
    source: str | None = None,
    action: str = "scan",
    confirm: bool = False,
    tickers: tuple[str, ...] | list[str] | None = None,
) -> ResearchPreparationRunResult:
    normalized_action = (action or "scan").strip().lower()
    if normalized_action not in PREPARATION_ACTIONS:
        status = research_preparation_status(config, source, tickers=tickers)
        return ResearchPreparationRunResult(
            source=status.source,
            action=normalized_action,
            confirm=confirm,
            dry_run=not confirm,
            ignored_count=0,
            applied_count=0,
            refreshed_count=0,
            blocked_count=status.total_items,
            updated_recommendation_ids=(),
            applied_tickers=(),
            refreshed_tickers=(),
            status=status,
            blocked_reason="invalid_preparation_action",
            warnings=(f"unsupported_action:{normalized_action}",),
        )

    status = research_preparation_status(config, source, tickers=tickers)
    ignored_count = 0
    applied_count = 0
    refreshed_count = 0
    discovered_count = 0
    staged_count = 0
    loaded_source_count = 0
    computed_count = 0
    updated_ids: tuple[int, ...] = ()
    applied_tickers: tuple[str, ...] = ()
    refreshed_tickers: tuple[str, ...] = ()
    discovered_tickers: tuple[str, ...] = ()
    staged_tickers: tuple[str, ...] = ()
    loaded_source_tickers: tuple[str, ...] = ()
    computed_tickers: tuple[str, ...] = ()
    warnings: list[str] = []

    if normalized_action == "discover_sources":
        discovered_count, discovered_tickers, discovery_warnings = _discover_source_items(
            config,
            status.items,
        )
        warnings.extend(discovery_warnings)
    if normalized_action in {"stage_source_rows", "all_safe"}:
        staged_count, staged_tickers, stage_warnings = _stage_source_items(
            config,
            status.items,
            confirm=confirm,
        )
        warnings.extend(stage_warnings)
        if confirm and staged_tickers:
            status = research_preparation_status(config, source, tickers=tickers)
    if normalized_action in {"load_staged_sources", "all_safe"}:
        loaded_source_count, loaded_source_tickers, load_warnings = _load_staged_source_items(
            config,
            status.items,
            confirm=confirm,
        )
        warnings.extend(load_warnings)
        if confirm and loaded_source_tickers:
            status = research_preparation_status(config, source, tickers=tickers)
    if normalized_action in {"compute_ready", "all_safe"}:
        computed_count, computed_tickers, compute_warnings = _compute_ready_items(
            config,
            status.items,
            confirm=confirm,
        )
        warnings.extend(compute_warnings)
        if confirm and computed_tickers:
            status = research_preparation_status(config, source, tickers=tickers)
    if normalized_action in {"refresh_metadata", "all_safe"}:
        refreshed_count, refreshed_tickers, metadata_warnings = _refresh_metadata_items(
            config,
            status.items,
            confirm=confirm,
        )
        warnings.extend(metadata_warnings)
        if confirm and refreshed_tickers:
            status = research_preparation_status(config, source, tickers=tickers)
    if normalized_action in {"prepare_ready", "all_safe"}:
        applied_count, applied_tickers, apply_warnings = _apply_ready_items(
            config,
            status.items,
            confirm=confirm,
        )
        warnings.extend(apply_warnings)
        if confirm and applied_tickers:
            status = research_preparation_status(config, source, tickers=tickers)
    if normalized_action in {"ignore_already_scoreable", "all_safe"}:
        ignored_count, updated_ids, ignore_warnings = _ignore_already_scoreable_items(
            config,
            status.items,
            confirm=confirm,
        )
        warnings.extend(ignore_warnings)
        if confirm and updated_ids:
            status = research_preparation_status(config, source, tickers=tickers)
    if normalized_action == "refresh_scoreable":
        scoreable_count, scoreable_tickers, refresh_warnings = _refresh_scoreable_items(
            config,
            status.items,
            confirm=confirm,
        )
        refreshed_count += scoreable_count
        refreshed_tickers = tuple(dict.fromkeys((*refreshed_tickers, *scoreable_tickers)))
        warnings.extend(refresh_warnings)
        if confirm and scoreable_tickers:
            status = research_preparation_status(config, source, tickers=tickers)

    return ResearchPreparationRunResult(
        source=status.source,
        action=normalized_action,
        confirm=confirm,
        dry_run=not confirm,
        ignored_count=ignored_count,
        applied_count=applied_count,
        refreshed_count=refreshed_count,
        blocked_count=sum(1 for item in status.items if item.action_kind == "manual"),
        updated_recommendation_ids=updated_ids,
        applied_tickers=applied_tickers,
        refreshed_tickers=refreshed_tickers,
        status=status,
        discovered_count=discovered_count,
        staged_count=staged_count,
        loaded_source_count=loaded_source_count,
        computed_count=computed_count,
        discovered_tickers=discovered_tickers,
        staged_tickers=staged_tickers,
        loaded_source_tickers=loaded_source_tickers,
        computed_tickers=computed_tickers,
        warnings=tuple(dict.fromkeys(warnings)),
    )


def research_preparation_autopilot_due(
    config: AppConfig,
    *,
    now: datetime | None = None,
) -> bool:
    latest = latest_pipeline_step_result(
        config.database_path,
        RESEARCH_PREPARATION_AUTO_STEP_NAME,
    )
    due, _seconds_since_latest = _autopilot_due_from_latest(
        config,
        latest.finished_at if latest else None,
        now=now,
    )
    return due


def research_preparation_run_row_count(result: ResearchPreparationRunResult) -> int:
    return (
        result.ignored_count
        + result.applied_count
        + result.refreshed_count
        + result.discovered_count
        + result.staged_count
        + result.loaded_source_count
        + result.computed_count
    )


def research_preparation_autopilot_warnings(
    result: ResearchPreparationRunResult,
) -> tuple[str, ...]:
    warnings = list(result.warnings)
    if result.applied_tickers:
        warnings.append("applied:" + "|".join(result.applied_tickers))
    if result.updated_recommendation_ids:
        warnings.append(
            "ignored_recommendation_ids:"
            + "|".join(str(item) for item in result.updated_recommendation_ids)
        )
    manual_packets = result.status.manual_blocker_packets
    if manual_packets:
        warnings.append(
            "manual_blockers:" + "|".join(packet.ticker for packet in manual_packets)
        )
        warnings.extend(
            f"cannot_automate:{packet.ticker}:{packet.cannot_automate_reason}"
            for packet in manual_packets
        )
    return tuple(dict.fromkeys(warnings))


def build_research_preparation_status_text(status: ResearchPreparationStatus) -> str:
    lines = [
        "Research preparation status",
        f"Source: {status.source}",
        f"Items: {status.total_items}",
        f"Pending recommendation rows represented: {status.pending_recommendation_count}",
        f"Ready to apply: {status.ready_to_apply_count}",
        f"Already scoreable/context-only: {status.already_scoreable_count}",
        f"Manual blockers: {status.manual_blocked_count}",
        "State counts: "
        + (", ".join(f"{state}={count}" for state, count in status.state_counts) or "none"),
    ]
    if status.autopilot:
        lines.extend(
            [
                (
                    "Autopilot: "
                    f"enabled={status.autopilot.enabled}, source={status.autopilot.source}, "
                    f"due={status.autopilot.due}, throttle_seconds={status.autopilot.throttle_seconds}"
                ),
                (
                    "Latest autopilot run: "
                    + (
                        f"{status.autopilot.latest_status} {status.autopilot.latest_started_at} "
                        f"rows={status.autopilot.latest_rows_loaded}"
                        if status.autopilot.latest_started_at
                        else "none"
                    )
                ),
                "Autopilot manual blockers: "
                + (
                    ", ".join(status.autopilot.manual_blocker_tickers)
                    if status.autopilot.manual_blocker_tickers
                    else "none"
                ),
            ]
        )
    if status.manual_blocker_packets:
        lines.append("Manual blocker packets:")
        for packet in status.manual_blocker_packets[:25]:
            lines.append(
                "- "
                f"{packet.ticker}: state={packet.state}, reason={packet.cannot_automate_reason}, "
                f"required={', '.join(packet.required_fields) or 'none'}, "
                f"action={packet.safe_next_action}"
            )
    if status.items:
        lines.append("Preparation items:")
        for item in status.items[:25]:
            lines.append(
                "- "
                f"{item.ticker}: state={item.preparation_state}, path={item.research_path}, "
                f"rows={item.candidate_count}, automation={item.automation_stage}, "
                f"action={item.recommended_action}, "
                f"blockers={', '.join(item.blockers) if item.blockers else 'none'}"
            )
            if item.source_candidates:
                lines.append(
                    "  sources: "
                    + "; ".join(
                        f"{candidate.source}:{candidate.status}"
                        for candidate in item.source_candidates
                    )
                )
            if item.staged_rows:
                lines.append(
                    "  staged: "
                    + "; ".join(
                        f"{row.row_type}:{row.row_count}@{row.path}"
                        for row in item.staged_rows
                    )
                )
            if item.cannot_automate_reason:
                lines.append(f"  cannot automate: {item.cannot_automate_reason}")
    if status.next_actions:
        lines.append("Next actions:")
        lines.extend(f"- {action}" for action in status.next_actions)
    return "\n".join(lines)


def build_research_preparation_run_text(result: ResearchPreparationRunResult) -> str:
    lines = [
        "Research preparation run",
        f"Source: {result.source}",
        f"Action: {result.action}",
        f"Confirm: {result.confirm}",
        f"Dry run: {result.dry_run}",
        f"Ignored context rows: {result.ignored_count}",
        f"Applied tickers: {result.applied_count}",
        f"Refreshed tickers: {result.refreshed_count}",
        f"Discovered source tickers: {result.discovered_count}",
        f"Staged source rows: {result.staged_count}",
        f"Loaded source rows: {result.loaded_source_count}",
        f"Computed readiness tickers: {result.computed_count}",
        f"Manual blockers remaining: {result.blocked_count}",
        "Updated recommendation IDs: "
        + (", ".join(str(item) for item in result.updated_recommendation_ids) or "none"),
        "Applied ticker symbols: " + (", ".join(result.applied_tickers) or "none"),
        "Refreshed ticker symbols: " + (", ".join(result.refreshed_tickers) or "none"),
        "Discovered ticker symbols: " + (", ".join(result.discovered_tickers) or "none"),
        "Staged ticker symbols: " + (", ".join(result.staged_tickers) or "none"),
        "Loaded source ticker symbols: " + (", ".join(result.loaded_source_tickers) or "none"),
        "Computed ticker symbols: " + (", ".join(result.computed_tickers) or "none"),
        f"Blocked reason: {result.blocked_reason or 'none'}",
        "Warnings: " + (", ".join(result.warnings) if result.warnings else "none"),
        "",
        build_research_preparation_status_text(result.status),
    ]
    return "\n".join(lines)
