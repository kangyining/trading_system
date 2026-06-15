from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from statistics import mean

from .config import AppConfig
from .storage import (
    AlertOutcome,
    AlertOutcomeStatus,
    Price,
    StoredAlert,
    list_alert_outcomes,
    list_prices,
    list_stored_alerts,
    outcome_statuses,
    upsert_alert_outcome,
)


EQUITY_ACTIONABLE_ALERT_TYPES = {
    "bullish_divergence",
    "watch_only_gap",
    "bearish_overvaluation",
    "risk_warning",
}
ETF_ACTIONABLE_ALERT_TYPES = {
    "etf_nav_discount_dislocation",
    "etf_nav_discount_watch",
    "etf_nav_premium_warning",
    "etf_risk_warning",
}
HORIZONS = (5, 20, 60, 120)
OUTCOME_MODEL_VERSION = "alert_outcome_mvp_v1"
EQUITY_INVALIDATION_MOVE = 0.10
ETF_INVALIDATION_MOVE = 0.03


@dataclass(frozen=True)
class OutcomeTickerResult:
    ticker: str
    alert_type: str
    status: str
    outcome_status: str | None
    rows_updated: int
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class OutcomeUpdateResult:
    updated_count: int
    skipped_count: int
    warning_count: int
    results: tuple[OutcomeTickerResult, ...]


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return None


def _price_value(price: Price) -> float | None:
    return price.adjusted_close if price.adjusted_close is not None else price.close


def _price_high(price: Price) -> float | None:
    return price.high if price.high is not None else _price_value(price)


def _price_low(price: Price) -> float | None:
    return price.low if price.low is not None else _price_value(price)


def _join(items: list[str]) -> str | None:
    return ",".join(items) if items else None


def _entry_price(
    alert: StoredAlert,
    prices: list[Price],
) -> tuple[float | None, str | None, list[str]]:
    warnings: list[str] = []
    alert_date = _parse_date(alert.alert_timestamp)
    if alert_date is None:
        warnings.append("malformed_alert_timestamp")

    if _is_etf(alert) and alert.current_price is not None:
        return alert.current_price, alert_date.isoformat() if alert_date else None, warnings

    eligible_prices: list[Price] = []
    if alert_date is not None:
        eligible_prices = [
            price
            for price in prices
            if (price_date := _parse_date(price.price_date)) is not None
            and price_date <= alert_date
            and _price_value(price) is not None
        ]

    if eligible_prices:
        entry = eligible_prices[-1]
        return _price_value(entry), entry.price_date, warnings

    if alert.current_price is not None:
        warnings.append("used_alert_current_price")
        return alert.current_price, alert_date.isoformat() if alert_date else None, warnings

    warnings.append("missing_entry_price")
    return None, alert_date.isoformat() if alert_date else None, warnings


def _future_prices(prices: list[Price], entry_price_date: str | None) -> list[Price]:
    entry_date = _parse_date(entry_price_date)
    if entry_date is None:
        return []
    return [
        price
        for price in prices
        if (price_date := _parse_date(price.price_date)) is not None
        and price_date > entry_date
    ]


def _horizon_returns(
    future_prices: list[Price],
    entry_price: float,
) -> tuple[dict[int, float | None], list[str], list[str]]:
    returns: dict[int, float | None] = {}
    completed: list[str] = []
    pending: list[str] = []
    priced_future = [price for price in future_prices if _price_value(price) is not None]
    for horizon in HORIZONS:
        label = f"{horizon}d"
        if len(priced_future) >= horizon:
            horizon_price = _price_value(priced_future[horizon - 1])
            returns[horizon] = (
                horizon_price / entry_price - 1 if horizon_price is not None else None
            )
            completed.append(label)
        else:
            returns[horizon] = None
            pending.append(label)
    return returns, completed, pending


def _target_price(alert: StoredAlert) -> float | None:
    if _is_diagnostic(alert):
        return None
    return alert.base_target


def _is_etf(alert: StoredAlert) -> bool:
    return (alert.asset_type or "").lower() == "etf"


def _is_negative_direction(alert: StoredAlert) -> bool:
    return alert.alert_type in {"bearish_overvaluation", "etf_nav_premium_warning"}


def _is_diagnostic(alert: StoredAlert) -> bool:
    return alert.alert_type in {"risk_warning", "etf_risk_warning"}


def _invalidation_move(alert: StoredAlert) -> float:
    return ETF_INVALIDATION_MOVE if _is_etf(alert) else EQUITY_INVALIDATION_MOVE


def _invalidation_price(alert: StoredAlert, entry_price: float | None) -> float | None:
    if entry_price is None or _is_diagnostic(alert):
        return None
    move = _invalidation_move(alert)
    if _is_negative_direction(alert):
        return entry_price * (1 + move)
    return entry_price * (1 - move)


def _hit_target_flag(
    alert: StoredAlert,
    future_prices: list[Price],
    target_price: float | None,
) -> int | None:
    if target_price is None or not future_prices:
        return None
    if _is_negative_direction(alert):
        hit = any(
            low is not None and low <= target_price
            for price in future_prices
            for low in (_price_low(price),)
        )
    else:
        hit = any(
            high is not None and high >= target_price
            for price in future_prices
            for high in (_price_high(price),)
        )
    return 1 if hit else 0


def _hit_invalidation_flag(
    alert: StoredAlert,
    future_prices: list[Price],
    invalidation_price: float | None,
) -> int | None:
    if invalidation_price is None or not future_prices:
        return None
    if _is_negative_direction(alert):
        hit = any(
            high is not None and high >= invalidation_price
            for price in future_prices
            for high in (_price_high(price),)
        )
    else:
        hit = any(
            low is not None and low <= invalidation_price
            for price in future_prices
            for low in (_price_low(price),)
        )
    return 1 if hit else 0


def _excursions(
    alert: StoredAlert,
    future_prices: list[Price],
    entry_price: float | None,
) -> tuple[float | None, float | None]:
    if entry_price in (None, 0) or not future_prices:
        return None, None

    highs = [_price_high(price) for price in future_prices]
    lows = [_price_low(price) for price in future_prices]
    highs = [value for value in highs if value is not None]
    lows = [value for value in lows if value is not None]
    if not highs or not lows:
        return None, None

    if _is_negative_direction(alert):
        favorable = max((entry_price - low) / entry_price for low in lows)
        adverse = min((entry_price - high) / entry_price for high in highs)
    else:
        favorable = max(high / entry_price - 1 for high in highs)
        adverse = min(low / entry_price - 1 for low in lows)
    return favorable, adverse


def _latest_price(prices: list[Price]) -> tuple[float | None, str | None]:
    priced = [price for price in prices if _price_value(price) is not None]
    if not priced:
        return None, None
    latest = priced[-1]
    return _price_value(latest), latest.price_date


def _outcome_status(completed: list[str], pending: list[str]) -> str:
    if not completed:
        return "pending"
    if pending:
        return "partial"
    return "completed"


def evaluate_alert_outcome(
    alert: StoredAlert,
    prices: list[Price],
    outcome_date: date | None = None,
) -> AlertOutcome:
    current_outcome_date = outcome_date or date.today()
    warnings: list[str] = []
    entry_price, entry_price_date, entry_warnings = _entry_price(alert, prices)
    warnings.extend(entry_warnings)
    latest_price, latest_price_date = _latest_price(prices)
    future_prices = _future_prices(prices, entry_price_date)

    returns = {horizon: None for horizon in HORIZONS}
    completed: list[str] = []
    pending = [f"{horizon}d" for horizon in HORIZONS]
    if entry_price not in (None, 0):
        returns, completed, pending = _horizon_returns(future_prices, entry_price)

    if not prices:
        warnings.append("missing_price_history")
    elif not future_prices:
        warnings.append("pending_future_prices")

    target_price = _target_price(alert)
    invalidation_price = _invalidation_price(alert, entry_price)
    mfe, mae = _excursions(alert, future_prices, entry_price)
    status = "missing_entry" if entry_price is None else _outcome_status(completed, pending)

    return AlertOutcome(
        alert_id=alert.alert_id,
        outcome_date=current_outcome_date.isoformat(),
        ticker=alert.ticker,
        alert_type=alert.alert_type,
        alert_timestamp=alert.alert_timestamp,
        asset_type=alert.asset_type,
        alert_model=alert.alert_model,
        threshold_set=alert.threshold_set,
        outcome_status=status,
        entry_price=entry_price,
        entry_price_date=entry_price_date,
        latest_price=latest_price,
        latest_price_date=latest_price_date,
        target_price=target_price,
        invalidation_price=invalidation_price,
        completed_horizons=_join(completed),
        pending_horizons=_join(pending),
        return_5d=returns[5],
        return_20d=returns[20],
        return_60d=returns[60],
        return_120d=returns[120],
        hit_target_flag=_hit_target_flag(alert, future_prices, target_price),
        hit_invalidation_flag=_hit_invalidation_flag(
            alert,
            future_prices,
            invalidation_price,
        ),
        max_favorable_excursion=mfe,
        max_adverse_excursion=mae,
        data_warnings=_join(warnings),
        model_version=OUTCOME_MODEL_VERSION,
        source="outcomes",
        as_of_date=current_outcome_date.isoformat(),
        effective_date=latest_price_date,
    )


def update_alert_outcomes(
    config: AppConfig,
    ticker: str | None = None,
    asset_type: str | None = None,
) -> OutcomeUpdateResult:
    results: list[OutcomeTickerResult] = []
    updated_count = 0
    skipped_count = 0
    normalized_asset_type = (asset_type or "all").lower()

    for alert in list_stored_alerts(config.database_path, ticker=ticker):
        alert_asset_type = (alert.asset_type or "equity").lower()
        if normalized_asset_type != "all" and alert_asset_type != normalized_asset_type:
            continue

        actionable_types = (
            ETF_ACTIONABLE_ALERT_TYPES
            if alert_asset_type == "etf"
            else EQUITY_ACTIONABLE_ALERT_TYPES
        )
        if alert.alert_type not in actionable_types:
            skipped_count += 1
            results.append(
                OutcomeTickerResult(
                    ticker=alert.ticker,
                    alert_type=alert.alert_type,
                    status="skipped",
                    outcome_status=None,
                    rows_updated=0,
                    warnings=(),
                )
            )
            continue

        outcome = evaluate_alert_outcome(alert, list_prices(config.database_path, alert.ticker))
        upsert_alert_outcome(config.database_path, outcome)
        updated_count += 1
        warnings = tuple(
            item.strip()
            for item in (outcome.data_warnings or "").split(",")
            if item.strip()
        )
        results.append(
            OutcomeTickerResult(
                ticker=alert.ticker,
                alert_type=alert.alert_type,
                status="updated",
                outcome_status=outcome.outcome_status,
                rows_updated=1,
                warnings=warnings,
            )
        )

    warning_count = sum(1 for result in results if result.warnings)
    return OutcomeUpdateResult(
        updated_count=updated_count,
        skipped_count=skipped_count,
        warning_count=warning_count,
        results=tuple(results),
    )


def _avg(values: list[float]) -> float | None:
    return mean(values) if values else None


def _fmt(value: float | None) -> str:
    return f"{value:.4f}" if value is not None else "none"


def _latest_available_return(outcome: AlertOutcomeStatus) -> float | None:
    for value in (
        outcome.return_120d,
        outcome.return_60d,
        outcome.return_20d,
        outcome.return_5d,
    ):
        if value is not None:
            return value
    return None


def _bucket(score: float | None) -> str:
    if score is None:
        return "unknown"
    if score < 70:
        return "<70"
    if score < 80:
        return "70-80"
    return "80+"


def _asset_type_for_outcome(
    outcome: AlertOutcomeStatus,
    alerts_by_key: dict[tuple[str, str, str], StoredAlert],
) -> str:
    if outcome.asset_type:
        return outcome.asset_type.lower()
    alert = alerts_by_key.get(
        (outcome.ticker, outcome.alert_type or "", outcome.alert_timestamp or "")
    )
    return (alert.asset_type or "unknown").lower() if alert else "unknown"


def build_validation_report(config: AppConfig) -> str:
    outcomes = outcome_statuses(config.database_path)
    alerts_by_key = {
        (alert.ticker, alert.alert_type, alert.alert_timestamp): alert
        for alert in list_stored_alerts(config.database_path)
    }
    equity_outcomes = [
        item for item in outcomes if _asset_type_for_outcome(item, alerts_by_key) == "equity"
    ]
    etf_outcomes = [
        item for item in outcomes if _asset_type_for_outcome(item, alerts_by_key) == "etf"
    ]
    pending_count = sum(1 for item in outcomes if item.outcome_status == "pending")
    partial_count = sum(1 for item in outcomes if item.outcome_status == "partial")
    completed_count = sum(1 for item in outcomes if item.outcome_status == "completed")
    target_evaluable = [
        item for item in outcomes if item.hit_target_flag is not None
    ]
    target_hits = sum(1 for item in target_evaluable if item.hit_target_flag == 1)
    invalidation_hits = sum(
        1 for item in outcomes if item.hit_invalidation_flag == 1
    )
    hit_rate = target_hits / len(target_evaluable) if target_evaluable else None
    false_positive_proxy = (
        sum(
            1
            for item in target_evaluable
            if item.hit_target_flag == 0 or item.hit_invalidation_flag == 1
        )
        / len(target_evaluable)
        if target_evaluable
        else None
    )

    horizon_lines = []
    for horizon in HORIZONS:
        field_name = f"return_{horizon}d"
        values = [
            value
            for outcome in outcomes
            for value in (getattr(outcome, field_name),)
            if value is not None
        ]
        horizon_lines.append(f"- Average {horizon}d return: `{_fmt(_avg(values))}`")

    by_alert_type: dict[str, list[float]] = {}
    by_bucket: dict[str, list[float]] = {}
    for outcome in outcomes:
        latest_return = _latest_available_return(outcome)
        if latest_return is None:
            continue
        by_alert_type.setdefault(outcome.alert_type or "unknown", []).append(latest_return)
        alert = alerts_by_key.get(
            (outcome.ticker, outcome.alert_type or "", outcome.alert_timestamp or "")
        )
        by_bucket.setdefault(
            _bucket(alert.opportunity_score if alert else None),
            [],
        ).append(latest_return)

    alert_type_lines = [
        f"- {alert_type}: `{_fmt(_avg(values))}`"
        for alert_type, values in sorted(by_alert_type.items())
    ]
    bucket_lines = [
        f"- {bucket}: `{_fmt(_avg(values))}`"
        for bucket, values in sorted(by_bucket.items())
    ]

    return "\n".join(
        (
            "Alert Outcome Validation Report",
            "",
            f"Outcome rows: {len(outcomes)}",
            f"Equity outcome rows: {len(equity_outcomes)}",
            f"ETF outcome rows: {len(etf_outcomes)}",
            f"Pending: {pending_count}",
            f"Partial: {partial_count}",
            f"Completed: {completed_count}",
            f"Target hit rate: {_fmt(hit_rate)}",
            f"False-positive proxy: {_fmt(false_positive_proxy)}",
            f"Invalidation hits: {invalidation_hits}",
            "",
            "Returns by horizon:",
            *(horizon_lines or ["- none"]),
            "",
            "Latest available return by alert type:",
            *(alert_type_lines or ["- none"]),
            "",
            "Latest available return by opportunity-score bucket:",
            *(bucket_lines or ["- none"]),
        )
    )


def validation_summary(config: AppConfig) -> tuple[int, int, int, int]:
    outcomes = list_alert_outcomes(config.database_path)
    pending_count = sum(1 for item in outcomes if item.outcome_status == "pending")
    partial_count = sum(1 for item in outcomes if item.outcome_status == "partial")
    completed_count = sum(1 for item in outcomes if item.outcome_status == "completed")
    return len(outcomes), pending_count, partial_count, completed_count
