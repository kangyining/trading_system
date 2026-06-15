from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from statistics import mean

from .config import AppConfig
from .storage import (
    Price,
    SignalOutcome,
    StoredSignal,
    is_scoreable_asset,
    list_assets,
    list_prices,
    list_signal_outcomes,
    list_stored_signals,
    signal_outcome_statuses,
    upsert_signal_outcome,
)


COMPOSITE_SIGNAL_NAME = "analyst_revision.composite"
SIGNAL_FAMILY = "analyst_revision"
HORIZONS = (5, 20, 60, 120)
SIGNAL_VALIDATION_MODEL_VERSION = "analyst_revision_validation_mvp_v1"
NEWS_CATALYST_COMPOSITE_SIGNAL_NAME = "news_catalyst.composite"
NEWS_CATALYST_SIGNAL_FAMILY = "news_catalyst"
NEWS_CATALYST_VALIDATION_MODEL_VERSION = "news_catalyst_validation_mvp_v1"
INSIDER_ACTIVITY_COMPOSITE_SIGNAL_NAME = "insider_activity.composite"
INSIDER_ACTIVITY_SIGNAL_FAMILY = "insider_activity"
INSIDER_ACTIVITY_VALIDATION_MODEL_VERSION = "insider_activity_validation_mvp_v1"
SHORT_INTEREST_COMPOSITE_SIGNAL_NAME = "short_interest.composite"
SHORT_INTEREST_SIGNAL_FAMILY = "short_interest"
SHORT_INTEREST_VALIDATION_MODEL_VERSION = "short_interest_validation_mvp_v1"


@dataclass(frozen=True)
class SignalValidationTickerResult:
    ticker: str
    signal_name: str
    status: str
    outcome_status: str | None
    rows_updated: int
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class SignalValidationUpdateResult:
    updated_count: int
    skipped_count: int
    warning_count: int
    results: tuple[SignalValidationTickerResult, ...]


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return None


def _price_value(price: Price) -> float | None:
    return price.adjusted_close if price.adjusted_close is not None else price.close


def _join(items: list[str]) -> str | None:
    return ",".join(items) if items else None


def _entry_price(
    signal: StoredSignal,
    prices: list[Price],
) -> tuple[float | None, str | None, list[str]]:
    warnings: list[str] = []
    signal_date = _parse_date(signal.signal_date)
    if signal_date is None:
        warnings.append("malformed_signal_date")

    eligible_prices: list[Price] = []
    if signal_date is not None:
        eligible_prices = [
            price
            for price in prices
            if (price_date := _parse_date(price.price_date)) is not None
            and price_date <= signal_date
            and _price_value(price) is not None
        ]

    if eligible_prices:
        entry = eligible_prices[-1]
        return _price_value(entry), entry.price_date, warnings

    warnings.append("missing_entry_price")
    return None, signal_date.isoformat() if signal_date else None, warnings


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


def _latest_price(prices: list[Price]) -> tuple[float | None, str | None]:
    priced = [price for price in prices if _price_value(price) is not None]
    if not priced:
        return None, None
    latest = priced[-1]
    return _price_value(latest), latest.price_date


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


def _outcome_status(completed: list[str], pending: list[str]) -> str:
    if not completed:
        return "pending"
    if pending:
        return "partial"
    return "completed"


def _signal_direction(signal: StoredSignal) -> str:
    if signal.direction in {"positive", "negative", "neutral"}:
        return signal.direction
    if signal.score is None:
        return "neutral"
    if signal.score >= 60:
        return "positive"
    if signal.score <= 40:
        return "negative"
    return "neutral"


def _latest_completed_return(returns: dict[int, float | None]) -> float | None:
    for horizon in (120, 60, 20, 5):
        if returns[horizon] is not None:
            return returns[horizon]
    return None


def _hit_status(
    direction: str,
    returns: dict[int, float | None],
    completed: list[str],
) -> tuple[int | None, str]:
    if direction == "neutral":
        return None, "neutral"
    if not completed:
        return None, "pending"
    latest_return = _latest_completed_return(returns)
    if latest_return is None:
        return None, "pending"
    if direction == "positive":
        return (1, "hit") if latest_return > 0 else (0, "miss")
    if direction == "negative":
        return (1, "hit") if latest_return < 0 else (0, "miss")
    return None, "neutral"


def evaluate_signal_outcome(
    signal: StoredSignal,
    prices: list[Price],
    model_version: str,
    outcome_date: date | None = None,
) -> SignalOutcome:
    current_outcome_date = outcome_date or date.today()
    warnings: list[str] = []
    entry_price, entry_price_date, entry_warnings = _entry_price(signal, prices)
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

    direction = _signal_direction(signal)
    directional_hit_flag, hit_status = _hit_status(direction, returns, completed)
    status = "missing_entry" if entry_price is None else _outcome_status(completed, pending)

    return SignalOutcome(
        signal_id=signal.signal_id,
        ticker=signal.ticker,
        signal_date=signal.signal_date,
        signal_name=signal.signal_name,
        signal_family=signal.signal_family,
        signal_score=signal.score,
        signal_direction=direction,
        outcome_date=current_outcome_date.isoformat(),
        outcome_status=status,
        entry_price=entry_price,
        entry_price_date=entry_price_date,
        latest_price=latest_price,
        latest_price_date=latest_price_date,
        completed_horizons=_join(completed),
        pending_horizons=_join(pending),
        return_5d=returns[5],
        return_20d=returns[20],
        return_60d=returns[60],
        return_120d=returns[120],
        directional_hit_flag=directional_hit_flag,
        hit_status=hit_status,
        data_warnings=_join(warnings),
        model_version=model_version,
        source="signal_validation",
        as_of_date=current_outcome_date.isoformat(),
        effective_date=latest_price_date,
    )


def evaluate_revision_signal_outcome(
    signal: StoredSignal,
    prices: list[Price],
    outcome_date: date | None = None,
) -> SignalOutcome:
    return evaluate_signal_outcome(
        signal,
        prices,
        model_version=SIGNAL_VALIDATION_MODEL_VERSION,
        outcome_date=outcome_date,
    )


def validate_signal_family(
    config: AppConfig,
    ticker: str | None = None,
    signal_family: str = SIGNAL_FAMILY,
    composite_signal_name: str = COMPOSITE_SIGNAL_NAME,
    validation_model_version: str = SIGNAL_VALIDATION_MODEL_VERSION,
    etf_warning: str = "etf_signal_validation_gated",
    missing_warning: str = "missing_revision_signal",
) -> SignalValidationUpdateResult:
    wanted_ticker = ticker.strip().upper() if ticker else None
    active_assets = {
        asset.ticker: (asset.asset_type or "equity").lower()
        for asset in list_assets(config.database_path)
        if is_scoreable_asset(asset) and (wanted_ticker is None or asset.ticker == wanted_ticker)
    }
    signals = [
        signal
        for signal in list_stored_signals(
            config.database_path,
            ticker=ticker,
            signal_family=signal_family,
            signal_name=composite_signal_name,
        )
        if signal.ticker in active_assets
    ]
    signal_tickers = {signal.ticker for signal in signals}
    results: list[SignalValidationTickerResult] = []
    updated_count = 0
    skipped_count = 0

    for ticker_symbol, asset_type in sorted(active_assets.items()):
        if asset_type == "etf":
            skipped_count += 1
            results.append(
                SignalValidationTickerResult(
                    ticker=ticker_symbol,
                    signal_name=composite_signal_name,
                    status="skipped",
                    outcome_status=None,
                    rows_updated=0,
                    warnings=(etf_warning,),
                )
            )
        elif ticker_symbol not in signal_tickers:
            skipped_count += 1
            results.append(
                SignalValidationTickerResult(
                    ticker=ticker_symbol,
                    signal_name=composite_signal_name,
                    status="skipped",
                    outcome_status=None,
                    rows_updated=0,
                    warnings=(missing_warning,),
                )
            )

    for signal in signals:
        if active_assets.get(signal.ticker) != "equity":
            continue
        outcome = evaluate_signal_outcome(
            signal,
            list_prices(config.database_path, signal.ticker),
            model_version=validation_model_version,
        )
        upsert_signal_outcome(config.database_path, outcome)
        updated_count += 1
        warnings = tuple(
            item.strip()
            for item in (outcome.data_warnings or "").split(",")
            if item.strip()
        )
        results.append(
            SignalValidationTickerResult(
                ticker=signal.ticker,
                signal_name=signal.signal_name,
                status="updated",
                outcome_status=outcome.outcome_status,
                rows_updated=1,
                warnings=warnings,
            )
        )

    warning_count = sum(1 for result in results if result.warnings)
    return SignalValidationUpdateResult(
        updated_count=updated_count,
        skipped_count=skipped_count,
        warning_count=warning_count,
        results=tuple(sorted(results, key=lambda item: (item.ticker, item.status))),
    )


def validate_revision_signals(
    config: AppConfig,
    ticker: str | None = None,
) -> SignalValidationUpdateResult:
    return validate_signal_family(
        config,
        ticker=ticker,
        signal_family=SIGNAL_FAMILY,
        composite_signal_name=COMPOSITE_SIGNAL_NAME,
        validation_model_version=SIGNAL_VALIDATION_MODEL_VERSION,
        etf_warning="etf_signal_validation_gated",
        missing_warning="missing_revision_signal",
    )


def validate_news_catalyst_signals(
    config: AppConfig,
    ticker: str | None = None,
) -> SignalValidationUpdateResult:
    return validate_signal_family(
        config,
        ticker=ticker,
        signal_family=NEWS_CATALYST_SIGNAL_FAMILY,
        composite_signal_name=NEWS_CATALYST_COMPOSITE_SIGNAL_NAME,
        validation_model_version=NEWS_CATALYST_VALIDATION_MODEL_VERSION,
        etf_warning="etf_news_catalyst_validation_gated",
        missing_warning="missing_news_catalyst_signal",
    )


def validate_insider_signals(
    config: AppConfig,
    ticker: str | None = None,
) -> SignalValidationUpdateResult:
    return validate_signal_family(
        config,
        ticker=ticker,
        signal_family=INSIDER_ACTIVITY_SIGNAL_FAMILY,
        composite_signal_name=INSIDER_ACTIVITY_COMPOSITE_SIGNAL_NAME,
        validation_model_version=INSIDER_ACTIVITY_VALIDATION_MODEL_VERSION,
        etf_warning="etf_insider_activity_validation_gated",
        missing_warning="missing_insider_activity_signal",
    )


def validate_short_interest_signals(
    config: AppConfig,
    ticker: str | None = None,
) -> SignalValidationUpdateResult:
    return validate_signal_family(
        config,
        ticker=ticker,
        signal_family=SHORT_INTEREST_SIGNAL_FAMILY,
        composite_signal_name=SHORT_INTEREST_COMPOSITE_SIGNAL_NAME,
        validation_model_version=SHORT_INTEREST_VALIDATION_MODEL_VERSION,
        etf_warning="etf_short_interest_validation_gated",
        missing_warning="missing_short_interest_signal",
    )


def _avg(values: list[float]) -> float | None:
    return mean(values) if values else None


def _fmt(value: float | None) -> str:
    return f"{value:.4f}" if value is not None else "none"


def _bucket(score: float | None) -> str:
    if score is None:
        return "unknown"
    if score < 40:
        return "<40"
    if score < 60:
        return "40-60"
    if score < 80:
        return "60-80"
    return "80+"


def build_signal_validation_report(
    config: AppConfig,
    title: str,
    signal_family: str,
    composite_signal_name: str,
    bucket_label: str,
) -> str:
    outcomes = signal_outcome_statuses(
        config.database_path,
        signal_family=signal_family,
        signal_name=composite_signal_name,
    )
    pending_count = sum(1 for item in outcomes if item.outcome_status == "pending")
    partial_count = sum(1 for item in outcomes if item.outcome_status == "partial")
    completed_count = sum(1 for item in outcomes if item.outcome_status == "completed")
    directional = [item for item in outcomes if item.directional_hit_flag is not None]
    hit_count = sum(1 for item in directional if item.directional_hit_flag == 1)
    hit_rate = hit_count / len(directional) if directional else None

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

    by_direction: dict[str, list[float]] = {}
    by_bucket: dict[str, list[float]] = {}
    for outcome in outcomes:
        latest_return = _latest_completed_return(
            {
                5: outcome.return_5d,
                20: outcome.return_20d,
                60: outcome.return_60d,
                120: outcome.return_120d,
            }
        )
        if latest_return is None:
            continue
        by_direction.setdefault(outcome.signal_direction or "unknown", []).append(latest_return)
        by_bucket.setdefault(_bucket(outcome.signal_score), []).append(latest_return)

    direction_lines = [
        f"- {direction}: `{_fmt(_avg(values))}`"
        for direction, values in sorted(by_direction.items())
    ]
    bucket_lines = [
        f"- {bucket}: `{_fmt(_avg(values))}`"
        for bucket, values in sorted(by_bucket.items())
    ]

    return "\n".join(
        (
            title,
            "",
            f"Signal outcome rows: {len(outcomes)}",
            f"Pending: {pending_count}",
            f"Partial: {partial_count}",
            f"Completed: {completed_count}",
            f"Directional hit rate: {_fmt(hit_rate)}",
            "",
            "Returns by horizon:",
            *(horizon_lines or ["- none"]),
            "",
            "Latest available return by signal direction:",
            *(direction_lines or ["- none"]),
            "",
            f"Latest available return by {bucket_label}:",
            *(bucket_lines or ["- none"]),
        )
    )


def build_revision_validation_report(config: AppConfig) -> str:
    return build_signal_validation_report(
        config,
        title="Analyst Revision Signal Validation Report",
        signal_family=SIGNAL_FAMILY,
        composite_signal_name=COMPOSITE_SIGNAL_NAME,
        bucket_label="revision-score bucket",
    )


def build_news_catalyst_validation_report(config: AppConfig) -> str:
    return build_signal_validation_report(
        config,
        title="News/Catalyst Signal Validation Report",
        signal_family=NEWS_CATALYST_SIGNAL_FAMILY,
        composite_signal_name=NEWS_CATALYST_COMPOSITE_SIGNAL_NAME,
        bucket_label="news-catalyst-score bucket",
    )


def build_insider_validation_report(config: AppConfig) -> str:
    return build_signal_validation_report(
        config,
        title="Insider Activity Signal Validation Report",
        signal_family=INSIDER_ACTIVITY_SIGNAL_FAMILY,
        composite_signal_name=INSIDER_ACTIVITY_COMPOSITE_SIGNAL_NAME,
        bucket_label="insider-activity-score bucket",
    )


def build_short_interest_validation_report(config: AppConfig) -> str:
    return build_signal_validation_report(
        config,
        title="Short Interest Signal Validation Report",
        signal_family=SHORT_INTEREST_SIGNAL_FAMILY,
        composite_signal_name=SHORT_INTEREST_COMPOSITE_SIGNAL_NAME,
        bucket_label="short-interest-score bucket",
    )


def revision_validation_summary(config: AppConfig) -> tuple[int, int, int, int]:
    outcomes = list_signal_outcomes(
        config.database_path,
        signal_family=SIGNAL_FAMILY,
        signal_name=COMPOSITE_SIGNAL_NAME,
    )
    pending_count = sum(1 for item in outcomes if item.outcome_status == "pending")
    partial_count = sum(1 for item in outcomes if item.outcome_status == "partial")
    completed_count = sum(1 for item in outcomes if item.outcome_status == "completed")
    return len(outcomes), pending_count, partial_count, completed_count


def news_catalyst_validation_summary(config: AppConfig) -> tuple[int, int, int, int]:
    outcomes = list_signal_outcomes(
        config.database_path,
        signal_family=NEWS_CATALYST_SIGNAL_FAMILY,
        signal_name=NEWS_CATALYST_COMPOSITE_SIGNAL_NAME,
    )
    pending_count = sum(1 for item in outcomes if item.outcome_status == "pending")
    partial_count = sum(1 for item in outcomes if item.outcome_status == "partial")
    completed_count = sum(1 for item in outcomes if item.outcome_status == "completed")
    return len(outcomes), pending_count, partial_count, completed_count


def insider_validation_summary(config: AppConfig) -> tuple[int, int, int, int]:
    outcomes = list_signal_outcomes(
        config.database_path,
        signal_family=INSIDER_ACTIVITY_SIGNAL_FAMILY,
        signal_name=INSIDER_ACTIVITY_COMPOSITE_SIGNAL_NAME,
    )
    pending_count = sum(1 for item in outcomes if item.outcome_status == "pending")
    partial_count = sum(1 for item in outcomes if item.outcome_status == "partial")
    completed_count = sum(1 for item in outcomes if item.outcome_status == "completed")
    return len(outcomes), pending_count, partial_count, completed_count


def short_interest_validation_summary(config: AppConfig) -> tuple[int, int, int, int]:
    outcomes = list_signal_outcomes(
        config.database_path,
        signal_family=SHORT_INTEREST_SIGNAL_FAMILY,
        signal_name=SHORT_INTEREST_COMPOSITE_SIGNAL_NAME,
    )
    pending_count = sum(1 for item in outcomes if item.outcome_status == "pending")
    partial_count = sum(1 for item in outcomes if item.outcome_status == "partial")
    completed_count = sum(1 for item in outcomes if item.outcome_status == "completed")
    return len(outcomes), pending_count, partial_count, completed_count
