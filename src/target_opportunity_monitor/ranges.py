from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta

from .config import AppConfig
from .notifications import create_range_notification
from .storage import (
    Asset,
    EtfFeature,
    PriceFeature,
    QuoteSnapshot,
    RangeSnapshot,
    Score,
    Target,
    alert_statuses,
    is_scoreable_asset,
    latest_etf_feature,
    latest_etf_nav,
    latest_price_feature,
    latest_quote_snapshot,
    latest_range_snapshot,
    latest_regime_signal_snapshot,
    latest_technical_signal_snapshot,
    list_assets,
    list_scores,
    list_targets,
    normalize_ticker,
    portfolio_statuses,
    upsert_range_snapshot,
)


@dataclass(frozen=True)
class RangeMonitorTickerResult:
    ticker: str
    range_state: str
    previous_range_state: str | None
    current_price: float | None
    notification_created: bool
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class RangeMonitorResult:
    results: tuple[RangeMonitorTickerResult, ...]

    @property
    def updated_count(self) -> int:
        return len(self.results)

    @property
    def notification_count(self) -> int:
        return sum(1 for result in self.results if result.notification_created)

    @property
    def warning_count(self) -> int:
        return sum(1 for result in self.results if result.warnings)


def _safe_gap(numerator: float | None, denominator: float | None) -> float | None:
    if numerator is None or denominator in (None, 0):
        return None
    return numerator / denominator - 1


def _latest_target(config: AppConfig, ticker: str) -> Target | None:
    targets = list_targets(config.database_path, ticker)
    return targets[-1] if targets else None


def _latest_score(config: AppConfig, ticker: str) -> Score | None:
    scores = list_scores(config.database_path, ticker)
    return scores[-1] if scores else None


def _parse_timestamp(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _quote_price(quote: QuoteSnapshot | None) -> float | None:
    if quote is None:
        return None
    for value in (quote.last, quote.mark, quote.close):
        if value is not None and value > 0:
            return value
    if quote.bid is not None and quote.ask is not None and quote.bid > 0 and quote.ask > 0:
        return (quote.bid + quote.ask) / 2
    return None


def _current_price_context(
    config: AppConfig,
    ticker: str,
) -> tuple[float | None, str | None, str | None, int, list[str]]:
    warnings: list[str] = []
    quote = latest_quote_snapshot(config.database_path, ticker)
    quote_price = _quote_price(quote)
    quote_timestamp = quote.quote_timestamp if quote else None
    quote_source = quote.source if quote else None
    quote_stale = 0
    if quote is not None:
        quote_dt = _parse_timestamp(quote.quote_timestamp)
        if quote_dt is None:
            quote_stale = 1
            warnings.append("malformed_quote_timestamp")
        elif datetime.now() - quote_dt > timedelta(
            seconds=config.realtime_quote_stale_after_seconds
        ):
            quote_stale = 1
            warnings.append("stale_quote")
    if quote_price is not None:
        return quote_price, quote_timestamp, quote_source, quote_stale, warnings

    feature = latest_price_feature(config.database_path, ticker)
    if feature is not None and feature.current_price is not None:
        warnings.append("using_daily_price_fallback")
        return feature.current_price, feature.latest_price_date, feature.source, 1, warnings

    warnings.append("missing_current_price")
    return None, quote_timestamp, quote_source, quote_stale, warnings


def _round(value: float | None) -> float | None:
    return round(value, 4) if value is not None else None


def _score_pass(value: float | None, minimum: float) -> bool:
    return value is not None and value >= minimum


def _technical_warnings(
    current_price: float | None,
    technical: object | None,
    regime: object | None,
) -> list[str]:
    warnings: list[str] = []
    location = getattr(technical, "price_location_state", None)
    if location in {
        "near_support",
        "support_failed",
        "near_resistance",
        "resistance_breakout",
    }:
        warnings.append(location)
    ma_state = getattr(technical, "moving_average_state", None)
    repair_level = getattr(technical, "trend_repair_level", None)
    if (
        current_price is not None
        and repair_level is not None
        and current_price < repair_level
        and ma_state in {"bearish", "mixed"}
    ):
        warnings.append("trend_repair_needed")
    if getattr(regime, "risk_state", None) == "risk_off":
        warnings.append("regime_risk_off")
    return warnings


def _equity_snapshot(
    config: AppConfig,
    asset: Asset,
    timestamp: str,
    target: Target | None,
    score: Score | None,
    feature: PriceFeature | None,
    current_price: float | None,
    quote_timestamp: str | None,
    quote_source: str | None,
    quote_stale: int,
    portfolio_by_ticker: dict[str, object],
    technical: object | None,
    regime: object | None,
    warnings: list[str],
) -> RangeSnapshot:
    if target is None or target.base_target is None:
        warnings.append("missing_target")
    if score is None:
        warnings.append("missing_score")
    if feature is None:
        warnings.append("missing_price_feature")

    target_low = target.target_low if target else None
    base_target = target.base_target if target else None
    target_high = target.target_high if target else None
    strong_buy_below = _round(target_low * 0.95) if target_low else None
    starter_buy_below = _round(target_low)
    add_below = _round(base_target * 0.95) if base_target else None
    hold_low = _round(target_low)
    hold_high = _round(target_high)
    trim_above = _round(target_high)
    reduce_or_sell_above = _round(target_high * 1.05) if target_high else None
    risk_review_below = _round(target_low * 0.85) if target_low else None
    opportunity = score.opportunity_score if score else None
    confidence = score.confidence_score if score else None
    timing = score.timing_score if score else None
    risk = score.risk_score if score else None
    liquidity = score.liquidity_score if score else None
    range_state = "no_range"
    reason_codes: list[str] = []

    if current_price is None or target is None or score is None:
        range_state = "data_quality_warning"
        reason_codes.append("missing_required_range_input")
    elif risk is not None and risk < config.alerts_risk_warning_score_below:
        range_state = "risk_review"
        reason_codes.append("risk_score_below_threshold")
    elif risk_review_below is not None and current_price <= risk_review_below:
        range_state = "risk_review"
        reason_codes.append("price_below_risk_review_level")
    elif (
        strong_buy_below is not None
        and current_price <= strong_buy_below
        and _score_pass(opportunity, 75)
        and _score_pass(confidence, 60)
        and _score_pass(risk, 40)
        and _score_pass(liquidity, 60)
    ):
        range_state = "strong_buy"
        reason_codes.append("deep_discount_high_score")
    elif (
        starter_buy_below is not None
        and current_price <= starter_buy_below
        and _score_pass(opportunity, 65)
        and _score_pass(confidence, 50)
    ):
        range_state = "starter_buy"
        reason_codes.append("below_target_low")
    elif add_below is not None and current_price <= add_below and _score_pass(opportunity, 65):
        range_state = "add_candidate"
        reason_codes.append("below_add_range")
    elif reduce_or_sell_above is not None and current_price >= reduce_or_sell_above:
        range_state = "reduce_or_sell"
        reason_codes.append("above_extended_target_high")
    elif trim_above is not None and current_price >= trim_above:
        range_state = "trim"
        reason_codes.append("above_target_high")
    elif hold_low is not None and hold_high is not None and hold_low <= current_price <= hold_high:
        range_state = "hold"
        reason_codes.append("inside_target_range")
    else:
        range_state = "hold"
        reason_codes.append("outside_action_ranges")

    portfolio = portfolio_by_ticker.get(asset.ticker)
    warnings.extend(_technical_warnings(current_price, technical, regime))
    return RangeSnapshot(
        ticker=asset.ticker,
        snapshot_timestamp=timestamp,
        asset_type=asset.asset_type,
        current_price=current_price,
        quote_timestamp=quote_timestamp,
        quote_source=quote_source,
        quote_stale=quote_stale,
        base_target=base_target,
        target_low=target_low,
        target_high=target_high,
        opportunity_score=opportunity,
        confidence_score=confidence,
        timing_score=timing,
        risk_score=risk,
        liquidity_score=liquidity,
        data_quality_score=_latest_alert_quality(config, asset.ticker),
        position_weight=getattr(portfolio, "position_weight", None),
        portfolio_review_category=getattr(portfolio, "review_category", None),
        strong_buy_below=strong_buy_below,
        starter_buy_below=starter_buy_below,
        add_below=add_below,
        hold_low=hold_low,
        hold_high=hold_high,
        trim_above=trim_above,
        reduce_or_sell_above=reduce_or_sell_above,
        risk_review_below=risk_review_below,
        range_state=range_state,
        reason_codes=", ".join(reason_codes) if reason_codes else None,
        data_warnings=", ".join(dict.fromkeys(warnings)) if warnings else None,
        technical_signal_date=getattr(technical, "signal_date", None),
        support_low=getattr(technical, "support_low", None),
        support_high=getattr(technical, "support_high", None),
        resistance_low=getattr(technical, "resistance_low", None),
        resistance_high=getattr(technical, "resistance_high", None),
        breakout_level=getattr(technical, "breakout_level", None),
        downside_watch_level=getattr(technical, "downside_watch_level", None),
        trend_repair_level=getattr(technical, "trend_repair_level", None),
        moving_average_state=getattr(technical, "moving_average_state", None),
        drawdown_state=getattr(technical, "drawdown_state", None),
        price_location_state=getattr(technical, "price_location_state", None),
        regime_signal_date=getattr(regime, "signal_date", None),
        regime_state=getattr(regime, "risk_state", None),
        relative_strength=getattr(regime, "relative_strength", None),
        sector_rotation_rank=getattr(regime, "sector_rotation_rank", None),
        technical_confidence=getattr(technical, "confidence", None),
        regime_confidence=getattr(regime, "confidence", None),
        model_version=config.realtime_range_model_version,
        source="range_monitor",
        as_of_date=date.today().isoformat(),
        effective_date=timestamp,
    )


def _etf_snapshot(
    config: AppConfig,
    asset: Asset,
    timestamp: str,
    target: Target | None,
    score: Score | None,
    etf_feature: EtfFeature | None,
    current_price: float | None,
    quote_timestamp: str | None,
    quote_source: str | None,
    quote_stale: int,
    portfolio_by_ticker: dict[str, object],
    technical: object | None,
    regime: object | None,
    warnings: list[str],
) -> RangeSnapshot:
    nav = latest_etf_nav(config.database_path, asset.ticker)
    nav_per_share = (
        etf_feature.nav_per_share
        if etf_feature and etf_feature.nav_per_share is not None
        else (nav.nav_per_share if nav else None)
    )
    if nav_per_share is None:
        warnings.append("missing_etf_nav")
    if etf_feature is None:
        warnings.append("missing_etf_feature")
    if score is None:
        warnings.append("missing_score")

    action_discount = config.alerts_etf_action_nav_discount_gap
    watch_discount = config.alerts_etf_watch_nav_discount_gap
    premium_warning = abs(config.alerts_etf_premium_warning_gap)
    nav_action_discount_below = (
        _round(nav_per_share * (1 - action_discount)) if nav_per_share else None
    )
    nav_watch_discount_below = (
        _round(nav_per_share * (1 - watch_discount)) if nav_per_share else None
    )
    nav_premium_warning_above = (
        _round(nav_per_share * (1 + premium_warning)) if nav_per_share else None
    )
    etf_risk_review_level = _round(nav_per_share * 0.97) if nav_per_share else None
    opportunity = score.opportunity_score if score else None
    confidence = score.confidence_score if score else None
    timing = score.timing_score if score else None
    risk = score.risk_score if score else None
    liquidity = score.liquidity_score if score else None
    nav_gap = _safe_gap(nav_per_share, current_price)
    range_state = "no_range"
    reason_codes: list[str] = []

    if current_price is None or nav_per_share is None or score is None:
        range_state = "data_quality_warning"
        reason_codes.append("missing_required_etf_range_input")
    elif not _score_pass(risk, config.alerts_etf_minimum_risk_score):
        range_state = "risk_review"
        reason_codes.append("etf_risk_score_below_threshold")
    elif not _score_pass(liquidity, config.alerts_etf_minimum_liquidity_score):
        range_state = "risk_review"
        reason_codes.append("etf_liquidity_score_below_threshold")
    elif nav_action_discount_below is not None and current_price <= nav_action_discount_below:
        range_state = "strong_buy"
        reason_codes.append("etf_nav_action_discount")
    elif nav_watch_discount_below is not None and current_price <= nav_watch_discount_below:
        range_state = "starter_buy"
        reason_codes.append("etf_nav_watch_discount")
    elif nav_premium_warning_above is not None and current_price >= nav_premium_warning_above:
        range_state = "trim"
        reason_codes.append("etf_nav_premium_warning")
    else:
        range_state = "hold"
        reason_codes.append("near_etf_nav_fair_value")

    portfolio = portfolio_by_ticker.get(asset.ticker)
    warnings.extend(_technical_warnings(current_price, technical, regime))
    return RangeSnapshot(
        ticker=asset.ticker,
        snapshot_timestamp=timestamp,
        asset_type=asset.asset_type,
        current_price=current_price,
        quote_timestamp=quote_timestamp,
        quote_source=quote_source,
        quote_stale=quote_stale,
        base_target=target.base_target if target else nav_per_share,
        target_low=target.target_low if target else None,
        target_high=target.target_high if target else None,
        etf_nav_per_share=nav_per_share,
        etf_nav_gap=nav_gap,
        opportunity_score=opportunity,
        confidence_score=confidence,
        timing_score=timing,
        risk_score=risk,
        liquidity_score=liquidity,
        data_quality_score=_latest_alert_quality(config, asset.ticker),
        position_weight=getattr(portfolio, "position_weight", None),
        portfolio_review_category=getattr(portfolio, "review_category", None),
        nav_action_discount_below=nav_action_discount_below,
        nav_watch_discount_below=nav_watch_discount_below,
        nav_fair_value=_round(nav_per_share),
        nav_premium_warning_above=nav_premium_warning_above,
        etf_risk_review_level=etf_risk_review_level,
        range_state=range_state,
        reason_codes=", ".join(reason_codes) if reason_codes else None,
        data_warnings=", ".join(dict.fromkeys(warnings)) if warnings else None,
        technical_signal_date=getattr(technical, "signal_date", None),
        support_low=getattr(technical, "support_low", None),
        support_high=getattr(technical, "support_high", None),
        resistance_low=getattr(technical, "resistance_low", None),
        resistance_high=getattr(technical, "resistance_high", None),
        breakout_level=getattr(technical, "breakout_level", None),
        downside_watch_level=getattr(technical, "downside_watch_level", None),
        trend_repair_level=getattr(technical, "trend_repair_level", None),
        moving_average_state=getattr(technical, "moving_average_state", None),
        drawdown_state=getattr(technical, "drawdown_state", None),
        price_location_state=getattr(technical, "price_location_state", None),
        regime_signal_date=getattr(regime, "signal_date", None),
        regime_state=getattr(regime, "risk_state", None),
        relative_strength=getattr(regime, "relative_strength", None),
        sector_rotation_rank=getattr(regime, "sector_rotation_rank", None),
        technical_confidence=getattr(technical, "confidence", None),
        regime_confidence=getattr(regime, "confidence", None),
        model_version=config.realtime_range_model_version,
        source="range_monitor",
        as_of_date=date.today().isoformat(),
        effective_date=timestamp,
    )


def _latest_alert_quality(config: AppConfig, ticker: str) -> float | None:
    for status in alert_statuses(config.database_path):
        if status.ticker == ticker:
            return status.data_quality_score
    return None


def compute_range_snapshots(
    config: AppConfig,
    ticker: str | None = None,
    create_notifications: bool = True,
) -> RangeMonitorResult:
    wanted = normalize_ticker(ticker) if ticker else None
    allow_explicit_etf_reference = wanted is not None
    assets = [
        asset
        for asset in list_assets(config.database_path)
        if (
            not config.realtime_monitor_active_assets_only
            or is_scoreable_asset(asset)
            or (
                allow_explicit_etf_reference
                and (asset.asset_type or "").strip().lower() in {"etf", "fund", "index_etf"}
            )
        )
        and (wanted is None or asset.ticker == wanted)
    ]
    timestamp = datetime.now().isoformat(timespec="seconds")
    portfolio_by_ticker = {
        status.ticker: status for status in portfolio_statuses(config.database_path)
    }
    results: list[RangeMonitorTickerResult] = []

    for asset in assets:
        warnings: list[str] = []
        current_price, quote_timestamp, quote_source, quote_stale, quote_warnings = (
            _current_price_context(config, asset.ticker)
        )
        warnings.extend(quote_warnings)
        target = _latest_target(config, asset.ticker)
        score = _latest_score(config, asset.ticker)
        previous = latest_range_snapshot(config.database_path, asset.ticker)
        technical = latest_technical_signal_snapshot(config.database_path, asset.ticker)
        regime = (
            latest_regime_signal_snapshot(config.database_path, asset.ticker)
            or latest_regime_signal_snapshot(config.database_path, "SPY")
        )
        if (asset.asset_type or "equity").lower() == "etf":
            snapshot = _etf_snapshot(
                config,
                asset,
                timestamp,
                target,
                score,
                latest_etf_feature(config.database_path, asset.ticker),
                current_price,
                quote_timestamp,
                quote_source,
                quote_stale,
                portfolio_by_ticker,
                technical,
                regime,
                warnings,
            )
        else:
            snapshot = _equity_snapshot(
                config,
                asset,
                timestamp,
                target,
                score,
                latest_price_feature(config.database_path, asset.ticker),
                current_price,
                quote_timestamp,
                quote_source,
                quote_stale,
                portfolio_by_ticker,
                technical,
                regime,
                warnings,
            )
        snapshot = RangeSnapshot(
            **{
                **snapshot.__dict__,
                "previous_range_state": previous.range_state if previous else None,
            }
        )
        upsert_range_snapshot(config.database_path, snapshot)
        notification_created = False
        if create_notifications:
            notification = create_range_notification(
                config,
                snapshot,
                previous.range_state if previous else None,
            )
            notification_created = notification is not None
        results.append(
            RangeMonitorTickerResult(
                ticker=asset.ticker,
                range_state=snapshot.range_state,
                previous_range_state=previous.range_state if previous else None,
                current_price=snapshot.current_price,
                notification_created=notification_created,
                warnings=tuple(dict.fromkeys(warnings)),
            )
        )

    return RangeMonitorResult(results=tuple(results))
