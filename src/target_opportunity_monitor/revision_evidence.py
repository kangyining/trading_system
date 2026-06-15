from __future__ import annotations

from dataclasses import dataclass
import sqlite3

from .config import AppConfig
from .signal_validation import COMPOSITE_SIGNAL_NAME, SIGNAL_FAMILY
from .storage import (
    SignalOutcomeStatus,
    StoredSignal,
    is_scoreable_asset,
    list_analyst_revision_aggregates,
    list_assets,
    list_stored_signals,
    signal_outcome_statuses,
)


DECISION_INSUFFICIENT_SOURCE = "insufficient_source_coverage"
DECISION_COLLECTING = "collecting_evidence"
DECISION_KEEP_SHADOW = "keep_shadow"
DECISION_ELIGIBLE = "eligible_for_limited_score_trial"

RECOMMENDATION_WEIGHTS = {
    "strongBuy": 2.0,
    "buy": 1.0,
    "hold": 0.0,
    "sell": -1.0,
    "strongSell": -2.0,
}


@dataclass(frozen=True)
class RevisionEvidenceResult:
    decision: str
    source_ticker_count: int
    signal_ticker_count: int
    completed_20d_count: int
    directional_20d_count: int
    hit_rate_20d: float | None
    average_directional_return_20d: float | None
    average_confidence: float | None
    source_tickers: tuple[str, ...]
    signal_tickers: tuple[str, ...]
    completed_20d_tickers: tuple[str, ...]
    shadow_mode: bool
    warnings: tuple[str, ...]


def derive_eps_revision(
    current_eps_trend: float | None,
    prior_eps_trend: float | None,
) -> float | None:
    if current_eps_trend is None or prior_eps_trend in (None, 0):
        return None
    return current_eps_trend / prior_eps_trend - 1.0


def derive_estimate_dispersion(
    high_estimate: float | None,
    low_estimate: float | None,
    average_estimate: float | None,
) -> float | None:
    if high_estimate is None or low_estimate is None or average_estimate in (None, 0):
        return None
    return (high_estimate - low_estimate) / abs(average_estimate)


def recommendation_bull_bear_score(counts: dict[str, int | float | None]) -> float | None:
    total = 0.0
    weighted = 0.0
    for key, weight in RECOMMENDATION_WEIGHTS.items():
        value = counts.get(key)
        if value is None:
            continue
        count = float(value)
        total += count
        weighted += weight * count
    if total == 0:
        return None
    return weighted / total


def derive_recommendation_revision(
    current_counts: dict[str, int | float | None],
    prior_counts: dict[str, int | float | None],
) -> float | None:
    current_score = recommendation_bull_bear_score(current_counts)
    prior_score = recommendation_bull_bear_score(prior_counts)
    if current_score is None or prior_score is None:
        return None
    return current_score - prior_score


def _average(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


def _directional_return(outcome: SignalOutcomeStatus) -> float | None:
    if outcome.return_20d is None:
        return None
    if outcome.signal_direction == "positive":
        return outcome.return_20d
    if outcome.signal_direction == "negative":
        return -outcome.return_20d
    return None


def _is_directional_hit(outcome: SignalOutcomeStatus) -> bool | None:
    directional_return = _directional_return(outcome)
    if directional_return is None:
        return None
    return directional_return > 0


def _source_tickers(
    signals: list[StoredSignal],
    active_equity_tickers: set[str],
    aggregate_tickers: set[str] | None = None,
) -> tuple[str, ...]:
    tickers = {
        signal.ticker
        for signal in signals
        if signal.signal_family == "analyst_revision_input"
        and signal.ticker in active_equity_tickers
        and (signal.source_url or signal.notes)
    }
    if aggregate_tickers:
        tickers.update(ticker for ticker in aggregate_tickers if ticker in active_equity_tickers)
    return tuple(sorted(tickers))


def _latest_composite_signals(
    signals: list[StoredSignal],
    active_equity_tickers: set[str],
) -> list[StoredSignal]:
    latest_by_ticker: dict[str, StoredSignal] = {}
    for signal in signals:
        if (
            signal.signal_family != SIGNAL_FAMILY
            or signal.signal_name != COMPOSITE_SIGNAL_NAME
            or signal.ticker not in active_equity_tickers
        ):
            continue
        existing = latest_by_ticker.get(signal.ticker)
        if existing is None or (signal.signal_date, signal.signal_id) > (
            existing.signal_date,
            existing.signal_id,
        ):
            latest_by_ticker[signal.ticker] = signal
    return list(latest_by_ticker.values())


def build_revision_evidence(config: AppConfig) -> RevisionEvidenceResult:
    try:
        active_equity_tickers = {
            asset.ticker
            for asset in list_assets(config.database_path)
            if is_scoreable_asset(asset)
            and (asset.asset_type or "equity").strip().lower() == "equity"
        }
        signals = list_stored_signals(config.database_path)
        outcomes = signal_outcome_statuses(config.database_path)
        aggregates = list_analyst_revision_aggregates(config.database_path)
    except (sqlite3.Error, FileNotFoundError):
        active_equity_tickers = set()
        signals = []
        outcomes = []
        aggregates = []

    aggregate_tickers = {
        aggregate.ticker
        for aggregate in aggregates
        if aggregate.source_count > 0 and aggregate.ticker in active_equity_tickers
    }
    source_tickers = _source_tickers(signals, active_equity_tickers, aggregate_tickers)
    composite_signals = _latest_composite_signals(signals, active_equity_tickers)
    signal_tickers = tuple(sorted({signal.ticker for signal in composite_signals}))
    confidences = [
        signal.confidence
        for signal in composite_signals
        if signal.confidence is not None
    ]
    completed_20d = [
        outcome
        for outcome in outcomes
        if outcome.signal_name == COMPOSITE_SIGNAL_NAME and outcome.return_20d is not None
        and outcome.ticker in active_equity_tickers
    ]
    completed_20d_tickers = tuple(sorted({outcome.ticker for outcome in completed_20d}))
    directional_returns = [
        directional_return
        for outcome in completed_20d
        for directional_return in (_directional_return(outcome),)
        if directional_return is not None
    ]
    hit_flags = [
        hit
        for outcome in completed_20d
        for hit in (_is_directional_hit(outcome),)
        if hit is not None
    ]

    hit_rate = sum(1 for hit in hit_flags if hit) / len(hit_flags) if hit_flags else None
    average_directional_return = _average(directional_returns)
    average_confidence = _average(confidences)

    warnings: list[str] = []
    if len(source_tickers) < config.signals_revision_evidence_min_source_tickers:
        warnings.append("insufficient_source_ticker_coverage")
    if len(signal_tickers) < config.signals_revision_evidence_min_signal_tickers:
        warnings.append("insufficient_signal_ticker_coverage")
    if len(completed_20d) < config.signals_revision_evidence_min_completed_20d:
        warnings.append("insufficient_completed_20d_validation")
    if average_confidence is None:
        warnings.append("missing_revision_signal_confidence")
    elif average_confidence < config.signals_revision_evidence_min_confidence:
        warnings.append("low_revision_signal_confidence")
    if config.signals_analyst_revision_shadow_mode:
        warnings.append("revision_signal_shadow_mode")

    if len(source_tickers) < config.signals_revision_evidence_min_source_tickers:
        decision = DECISION_INSUFFICIENT_SOURCE
    elif (
        len(signal_tickers) < config.signals_revision_evidence_min_signal_tickers
        or len(completed_20d) < config.signals_revision_evidence_min_completed_20d
        or not hit_flags
    ):
        decision = DECISION_COLLECTING
    elif (
        hit_rate is not None
        and hit_rate >= config.signals_revision_evidence_min_hit_rate_20d
        and average_directional_return is not None
        and average_directional_return
        >= config.signals_revision_evidence_min_avg_return_20d
        and average_confidence is not None
        and average_confidence >= config.signals_revision_evidence_min_confidence
    ):
        decision = DECISION_ELIGIBLE
    else:
        decision = DECISION_KEEP_SHADOW

    return RevisionEvidenceResult(
        decision=decision,
        source_ticker_count=len(source_tickers),
        signal_ticker_count=len(signal_tickers),
        completed_20d_count=len(completed_20d),
        directional_20d_count=len(hit_flags),
        hit_rate_20d=hit_rate,
        average_directional_return_20d=average_directional_return,
        average_confidence=average_confidence,
        source_tickers=source_tickers,
        signal_tickers=signal_tickers,
        completed_20d_tickers=completed_20d_tickers,
        shadow_mode=config.signals_analyst_revision_shadow_mode,
        warnings=tuple(dict.fromkeys(warnings)),
    )


def _fmt(value: float | None) -> str:
    return f"{value:.4f}" if value is not None else "none"


def build_revision_evidence_report(config: AppConfig) -> str:
    evidence = build_revision_evidence(config)
    return "\n".join(
        (
            "Analyst Revision Evidence Report",
            "",
            f"Decision: {evidence.decision}",
            f"Shadow mode: {evidence.shadow_mode}",
            f"Source-backed ticker coverage: {evidence.source_ticker_count}",
            f"Composite signal ticker coverage: {evidence.signal_ticker_count}",
            f"Completed 20d validation rows: {evidence.completed_20d_count}",
            f"Directional 20d validation rows: {evidence.directional_20d_count}",
            f"20d directional hit rate: {_fmt(evidence.hit_rate_20d)}",
            "20d direction-adjusted average return: "
            f"{_fmt(evidence.average_directional_return_20d)}",
            f"Average signal confidence: {_fmt(evidence.average_confidence)}",
            f"Source tickers: {', '.join(evidence.source_tickers) or 'none'}",
            f"Signal tickers: {', '.join(evidence.signal_tickers) or 'none'}",
            f"Completed 20d tickers: {', '.join(evidence.completed_20d_tickers) or 'none'}",
            f"Warnings: {', '.join(evidence.warnings) if evidence.warnings else 'none'}",
        )
    )
