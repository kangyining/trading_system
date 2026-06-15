from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime

from .config import AppConfig
from .storage import (
    Alert,
    Asset,
    EtfFeature,
    PriceFeature,
    Score,
    Target,
    insert_data_quality_check,
    is_scoreable_asset,
    latest_etf_feature,
    latest_price_feature,
    list_assets,
    list_scores,
    list_targets,
    normalize_ticker,
    upsert_alert,
)


NONFATAL_SCORE_WARNINGS = {"missing_revision_data"}


@dataclass(frozen=True)
class TickerAlertResult:
    ticker: str
    status: str
    asset_type: str
    alert_type: str | None
    priority: str | None
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class AlertComputationResult:
    results: tuple[TickerAlertResult, ...]

    @property
    def evaluated_count(self) -> int:
        return len(self.results)

    @property
    def stored_count(self) -> int:
        return sum(1 for result in self.results if result.status in {"alerted", "no_alert"})

    @property
    def alert_count(self) -> int:
        return sum(1 for result in self.results if result.status == "alerted")

    @property
    def skipped_count(self) -> int:
        return sum(1 for result in self.results if result.status == "skipped")

    @property
    def warning_count(self) -> int:
        return sum(1 for result in self.results if result.warnings)


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _asset_type(value: str | None) -> str:
    return (value or "equity").strip().lower()


def _latest_target(config: AppConfig, ticker: str) -> Target | None:
    targets = list_targets(config.database_path, ticker)
    return targets[-1] if targets else None


def _latest_score(config: AppConfig, ticker: str) -> Score | None:
    scores = list_scores(config.database_path, ticker)
    return scores[-1] if scores else None


def _split_codes(value: str | None) -> tuple[str, ...]:
    if not value:
        return ()
    return tuple(
        code.strip()
        for code in value.replace(";", ",").split(",")
        if code.strip()
    )


def _join_codes(values: tuple[str, ...] | list[str]) -> str | None:
    unique = tuple(dict.fromkeys(value for value in values if value))
    return ", ".join(unique) if unique else None


def _format_percent(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.1%}"


def _score_value(value: float | None) -> float:
    return value if value is not None else 0.0


def _data_quality_score(
    feature: PriceFeature | None,
    target: Target | None,
    score: Score | None,
) -> float:
    missing_count = 0
    if feature is None or feature.current_price is None:
        missing_count += 1
    if target is None or target.base_target is None or target.valuation_gap is None:
        missing_count += 1
    if score is None or score.opportunity_score is None:
        missing_count += 1
    return max(0.0, 100.0 - missing_count * 40.0)


def _date_age_days(value: str | None) -> int | None:
    if not value:
        return None
    try:
        return (date.today() - date.fromisoformat(value)).days
    except ValueError:
        return None


def _etf_market_price(
    feature: EtfFeature | None,
    price_feature: PriceFeature | None,
) -> tuple[float | None, tuple[str, ...]]:
    warnings: list[str] = []
    if feature and feature.market_price is not None:
        return feature.market_price, ()
    if price_feature and price_feature.current_price is not None:
        if (
            feature
            and feature.latest_nav_date
            and price_feature.latest_price_date
            and feature.latest_nav_date != price_feature.latest_price_date
        ):
            warnings.append("etf_price_date_mismatch")
        return price_feature.current_price, tuple(warnings)
    warnings.append("missing_etf_market_price")
    return None, tuple(warnings)


def _etf_nav_gap(nav: float | None, market_price: float | None) -> float | None:
    if nav is None or market_price in (None, 0):
        return None
    return nav / market_price - 1


def _etf_data_quality_score(
    feature: EtfFeature | None,
    target: Target | None,
    score: Score | None,
    market_price: float | None,
    warnings: tuple[str, ...],
) -> float:
    missing_count = 0
    if feature is None or feature.nav_per_share is None:
        missing_count += 1
    if market_price is None:
        missing_count += 1
    if target is None or target.base_target is None:
        missing_count += 1
    if score is None or score.opportunity_score is None:
        missing_count += 1
    if feature is None or not feature.holdings_count:
        missing_count += 1
    critical_warnings = {
        "missing_etf_feature",
        "missing_etf_nav",
        "missing_etf_market_price",
        "missing_target",
        "missing_score",
        "missing_or_insufficient_etf_holdings",
        "stale_etf_nav",
        "stale_etf_holdings",
    }
    warning_penalty = sum(1 for warning in warnings if warning in critical_warnings) * 10.0
    return max(0.0, 100.0 - missing_count * 25.0 - warning_penalty)


def _record_alert_quality(
    config: AppConfig,
    ticker: str,
    status: str,
    details: tuple[str, ...],
) -> None:
    insert_data_quality_check(
        config.database_path,
        check_name=f"alerts:{ticker}",
        status="warning" if details else "ok",
        details=", ".join(details) if details else status,
        source="alerts",
        as_of_date=date.today().isoformat(),
    )


def _make_alert(
    config: AppConfig,
    ticker: str,
    alert_type: str,
    priority: str,
    status: str,
    feature: PriceFeature | None,
    target: Target | None,
    score: Score | None,
    required_gap: float | None,
    data_quality_score: float,
    reason_codes: tuple[str, ...],
    risk_codes: tuple[str, ...],
    data_warnings: tuple[str, ...],
    main_reasons: str,
    main_risks: str,
    invalidation: str,
    asset_type: str = "equity",
    alert_model: str | None = None,
    threshold_set: str | None = None,
    current_price: float | None = None,
    valuation_gap: float | None = None,
) -> Alert:
    today = date.today().isoformat()
    model = alert_model or config.alerts_equity_model_version
    dedupe_key = f"{today}:{ticker}:{alert_type}:{model}"
    return Alert(
        ticker=ticker,
        alert_type=alert_type,
        alert_timestamp=_now_iso(),
        priority=priority,
        status=status,
        asset_type=asset_type,
        current_price=current_price if current_price is not None else (feature.current_price if feature else None),
        base_target=target.base_target if target else None,
        target_low=target.target_low if target else None,
        target_high=target.target_high if target else None,
        target_date=target.target_date if target else None,
        score_date=score.score_date if score else None,
        valuation_gap=valuation_gap if valuation_gap is not None else (target.valuation_gap if target else None),
        required_gap=required_gap,
        opportunity_score=score.opportunity_score if score else None,
        expected_value_score=score.expected_value_score if score else None,
        confidence_score=score.confidence_score if score else None,
        timing_score=score.timing_score if score else None,
        risk_score=score.risk_score if score else None,
        liquidity_score=score.liquidity_score if score else None,
        data_quality_score=data_quality_score,
        main_reasons=main_reasons,
        main_risks=main_risks,
        reason_codes=_join_codes(reason_codes),
        risk_codes=_join_codes(risk_codes),
        data_warnings=_join_codes(data_warnings),
        invalidation=invalidation,
        alert_model=model,
        threshold_set=threshold_set or config.alerts_equity_threshold_set,
        model_version=model,
        source="alerts",
        as_of_date=today,
        effective_date=today,
        dedupe_key=dedupe_key,
    )


def _data_quality_alert(
    config: AppConfig,
    asset: Asset,
    feature: PriceFeature | None,
    target: Target | None,
    score: Score | None,
    missing: tuple[str, ...],
    asset_type: str = "equity",
    alert_model: str | None = None,
    threshold_set: str | None = None,
    current_price: float | None = None,
    valuation_gap: float | None = None,
) -> TickerAlertResult:
    ticker = asset.ticker
    quality_score = _data_quality_score(feature, target, score)
    alert = _make_alert(
        config=config,
        ticker=ticker,
        alert_type="data_quality_warning",
        priority="high",
        status="open",
        feature=feature,
        target=target,
        score=score,
        required_gap=config.alerts_minimum_data_quality_score,
        data_quality_score=quality_score,
        reason_codes=missing,
        risk_codes=("data_incomplete",),
        data_warnings=missing,
        main_reasons="Required alert inputs are missing.",
        main_risks="Alert output is unreliable until required data is refreshed.",
        invalidation="Refresh price features, target ranges, and opportunity scores.",
        asset_type=asset_type,
        alert_model=alert_model,
        threshold_set=threshold_set,
        current_price=current_price,
        valuation_gap=valuation_gap,
    )
    upsert_alert(config.database_path, alert)
    _record_alert_quality(config, ticker, "data_quality_warning", missing)
    return TickerAlertResult(
        ticker=ticker,
        status="alerted",
        asset_type=asset_type,
        alert_type="data_quality_warning",
        priority="high",
        warnings=missing,
    )


def _compute_equity_alert(config: AppConfig, asset: Asset) -> TickerAlertResult:
    ticker = asset.ticker
    feature = latest_price_feature(config.database_path, ticker)
    target = _latest_target(config, ticker)
    score = _latest_score(config, ticker)

    missing: list[str] = []
    if feature is None or feature.current_price is None:
        missing.append("missing_price_feature")
    if target is None or target.base_target is None or target.valuation_gap is None:
        missing.append("missing_target")
    if score is None or score.opportunity_score is None:
        missing.append("missing_score")
    if missing:
        return _data_quality_alert(config, asset, feature, target, score, tuple(missing))

    assert feature is not None
    assert target is not None
    assert score is not None

    data_quality_score = _data_quality_score(feature, target, score)
    score_warnings = _split_codes(score.data_warnings)
    risk_codes = [code for code in score_warnings if code in NONFATAL_SCORE_WARNINGS]
    data_warnings = [code for code in score_warnings if code not in NONFATAL_SCORE_WARNINGS]

    current_price = feature.current_price or 0.0
    valuation_gap = target.valuation_gap or 0.0
    opportunity_score = _score_value(score.opportunity_score)
    expected_value_score = _score_value(score.expected_value_score)
    confidence_score = _score_value(score.confidence_score)
    liquidity_score = _score_value(score.liquidity_score)
    risk_score = _score_value(score.risk_score)

    thresholds_pass = (
        valuation_gap >= config.alerts_minimum_bullish_valuation_gap
        and expected_value_score >= config.alerts_minimum_expected_value_score
        and confidence_score >= config.alerts_minimum_confidence_score
        and liquidity_score >= config.alerts_minimum_liquidity_score
        and risk_score >= config.alerts_minimum_risk_score
        and data_quality_score >= config.alerts_minimum_data_quality_score
    )

    if risk_score < config.alerts_risk_warning_score_below:
        alert_type = "risk_warning"
        priority = "medium"
        status = "open"
        required_gap = config.alerts_risk_warning_score_below
        reason_codes = ("risk_score_below_threshold",)
        risk_codes.append("low_risk_score")
        main_reasons = f"Risk score is {risk_score:.1f}, below the configured threshold."
        main_risks = "Volatility or valuation-confidence risk is too high for a clean opportunity alert."
        invalidation = "Risk score recovers above the configured warning threshold."
    elif (
        target.target_low is not None
        and current_price < target.target_low
        and thresholds_pass
    ):
        alert_type = "bullish_divergence"
        priority = "high"
        status = "open"
        required_gap = config.alerts_minimum_bullish_valuation_gap
        reason_codes = (
            "price_below_target_low",
            "valuation_gap_pass",
            "expected_value_pass",
            "confidence_pass",
            "liquidity_pass",
            "risk_pass",
        )
        main_reasons = (
            f"Price is below target low and valuation gap is {_format_percent(valuation_gap)} "
            "with passing expected value, confidence, liquidity, and risk checks."
        )
        main_risks = "Target range can move lower or momentum can fail before price converges."
        invalidation = "Price reaches base target, target drops, or expected value/risk thresholds fail."
    elif target.target_high is not None and current_price > target.target_high and (
        valuation_gap <= config.alerts_bearish_overvaluation_gap
    ):
        alert_type = "bearish_overvaluation"
        priority = "high"
        status = "open"
        required_gap = abs(config.alerts_bearish_overvaluation_gap)
        reason_codes = ("price_above_target_high", "negative_valuation_gap")
        risk_codes.append("overvaluation")
        main_reasons = (
            f"Price is above target high and valuation gap is {_format_percent(valuation_gap)}."
        )
        main_risks = "Upside assumptions may be exhausted or downside risk may be elevated."
        invalidation = "Price returns inside the target range or valuation gap improves."
    elif (
        valuation_gap >= config.alerts_watch_gap_threshold
        and opportunity_score >= config.alerts_watch_opportunity_score
    ):
        alert_type = "watch_only_gap"
        priority = "medium"
        status = "open"
        required_gap = config.alerts_watch_gap_threshold
        reason_codes = ("valuation_gap_watch", "opportunity_score_watch")
        main_reasons = (
            f"Valuation gap is {_format_percent(valuation_gap)} and opportunity score is "
            f"{opportunity_score:.1f}, but full bullish-divergence criteria are not met."
        )
        main_risks = "Entry timing is not confirmed by the full alert rule."
        invalidation = "Valuation gap falls below the watch threshold or opportunity score weakens."
    else:
        alert_type = "no_alert"
        priority = "none"
        status = "closed"
        required_gap = config.alerts_minimum_bullish_valuation_gap
        reason_codes = ("no_rule_triggered",)
        main_reasons = "No Phase 5A equity alert rule triggered."
        main_risks = "Continue monitoring target range, scores, and data quality."
        invalidation = "A configured alert rule triggers on a future daily run."

    alert = _make_alert(
        config=config,
        ticker=ticker,
        alert_type=alert_type,
        priority=priority,
        status=status,
        feature=feature,
        target=target,
        score=score,
        required_gap=required_gap,
        data_quality_score=data_quality_score,
        reason_codes=tuple(reason_codes),
        risk_codes=tuple(risk_codes),
        data_warnings=tuple(data_warnings),
        main_reasons=main_reasons,
        main_risks=main_risks,
        invalidation=invalidation,
    )
    upsert_alert(config.database_path, alert)
    result_warnings = tuple(dict.fromkeys(data_warnings))
    _record_alert_quality(config, ticker, alert_type, result_warnings)
    return TickerAlertResult(
        ticker=ticker,
        status="no_alert" if alert_type == "no_alert" else "alerted",
        asset_type="equity",
        alert_type=alert_type,
        priority=priority,
        warnings=result_warnings,
    )


def _etf_freshness_warnings(config: AppConfig, feature: EtfFeature | None) -> tuple[str, ...]:
    if feature is None:
        return ("missing_etf_feature",)
    warnings: list[str] = []
    nav_age = _date_age_days(feature.latest_nav_date)
    holdings_age = _date_age_days(feature.latest_holdings_date)
    if feature.latest_nav_date is None:
        warnings.append("missing_etf_nav")
    elif nav_age is None:
        warnings.append("malformed_etf_nav_date")
    elif nav_age > config.etf_stale_nav_after_days:
        warnings.append("stale_etf_nav")
    if feature.holdings_count is None or feature.holdings_count < config.etf_minimum_holdings:
        warnings.append("missing_or_insufficient_etf_holdings")
    elif feature.latest_holdings_date is None:
        warnings.append("missing_etf_holdings_date")
    elif holdings_age is None:
        warnings.append("malformed_etf_holdings_date")
    elif holdings_age > config.etf_stale_holdings_after_days:
        warnings.append("stale_etf_holdings")
    if feature.premium_discount_zscore is None:
        warnings.append("missing_premium_discount_zscore")
    return tuple(warnings)


def _compute_etf_alert(config: AppConfig, asset: Asset) -> TickerAlertResult:
    ticker = asset.ticker
    price_feature = latest_price_feature(config.database_path, ticker)
    target = _latest_target(config, ticker)
    score = _latest_score(config, ticker)
    etf_feature = latest_etf_feature(config.database_path, ticker)
    market_price, price_warnings = _etf_market_price(etf_feature, price_feature)

    warnings: list[str] = []
    warnings.extend(_etf_freshness_warnings(config, etf_feature))
    warnings.extend(price_warnings)
    if target is None or target.base_target is None:
        warnings.append("missing_target")
    if score is None or score.opportunity_score is None:
        warnings.append("missing_score")

    nav_gap = _etf_nav_gap(
        etf_feature.nav_per_share if etf_feature else None,
        market_price,
    )
    if nav_gap is None:
        warnings.append("missing_etf_nav_gap")

    all_warnings = tuple(dict.fromkeys(warnings))
    data_quality_score = _etf_data_quality_score(
        etf_feature,
        target,
        score,
        market_price,
        all_warnings,
    )
    critical_missing = {
        "missing_etf_feature",
        "missing_etf_nav",
        "missing_etf_market_price",
        "missing_target",
        "missing_score",
        "missing_or_insufficient_etf_holdings",
        "stale_etf_nav",
        "stale_etf_holdings",
        "missing_etf_nav_gap",
    }
    if any(warning in critical_missing for warning in all_warnings) or (
        data_quality_score < config.alerts_etf_minimum_data_quality_score
    ):
        quality_missing = tuple(
            warning
            for warning in all_warnings
            if warning in critical_missing
        ) or ("etf_data_quality_below_threshold",)
        quality_score = data_quality_score
        alert = _make_alert(
            config=config,
            ticker=ticker,
            alert_type="data_quality_warning",
            priority="high",
            status="open",
            feature=price_feature,
            target=target,
            score=score,
            required_gap=config.alerts_etf_minimum_data_quality_score,
            data_quality_score=quality_score,
            reason_codes=quality_missing,
            risk_codes=("etf_data_incomplete",),
            data_warnings=all_warnings,
            main_reasons="Required ETF alert inputs are missing, stale, or incomplete.",
            main_risks="ETF alert output is unreliable until NAV, holdings, target, score, and price data are refreshed.",
            invalidation="Refresh ETF NAVs, holdings, features, targets, and scores.",
            asset_type="etf",
            alert_model=config.alerts_etf_model_version,
            threshold_set=config.alerts_etf_threshold_set,
            current_price=market_price,
            valuation_gap=nav_gap,
        )
        upsert_alert(config.database_path, alert)
        _record_alert_quality(config, ticker, "data_quality_warning", all_warnings)
        return TickerAlertResult(
            ticker=ticker,
            status="alerted",
            asset_type="etf",
            alert_type="data_quality_warning",
            priority="high",
            warnings=all_warnings,
        )

    assert target is not None
    assert score is not None
    nav_gap = nav_gap or 0.0
    opportunity_score = _score_value(score.opportunity_score)
    liquidity_score = _score_value(score.liquidity_score)
    risk_score = _score_value(score.risk_score)
    score_warnings = _split_codes(score.data_warnings)
    data_warnings = list(dict.fromkeys(tuple(all_warnings) + score_warnings))
    nonblocking_warnings = tuple(data_warnings)

    thresholds_pass = (
        opportunity_score >= config.alerts_etf_minimum_opportunity_score
        and liquidity_score >= config.alerts_etf_minimum_liquidity_score
        and risk_score >= config.alerts_etf_minimum_risk_score
        and data_quality_score >= config.alerts_etf_minimum_data_quality_score
    )

    if risk_score < config.alerts_etf_minimum_risk_score or liquidity_score < config.alerts_etf_minimum_liquidity_score:
        alert_type = "etf_risk_warning"
        priority = "medium"
        status = "open"
        required_gap = None
        reason_codes = ("etf_risk_or_liquidity_below_threshold",)
        risk_codes = tuple(
            code
            for code, passed in (
                ("low_etf_risk_score", risk_score >= config.alerts_etf_minimum_risk_score),
                ("low_etf_liquidity_score", liquidity_score >= config.alerts_etf_minimum_liquidity_score),
            )
            if not passed
        )
        main_reasons = (
            f"ETF risk score is {risk_score:.1f} and liquidity score is {liquidity_score:.1f}, "
            "below one or more configured ETF thresholds."
        )
        main_risks = "ETF liquidity or volatility conditions are not strong enough for a clean dislocation alert."
        invalidation = "Risk and liquidity scores recover above ETF thresholds."
    elif nav_gap >= config.alerts_etf_action_nav_discount_gap and thresholds_pass:
        alert_type = "etf_nav_discount_dislocation"
        priority = "high"
        status = "open"
        required_gap = config.alerts_etf_action_nav_discount_gap
        reason_codes = (
            "etf_nav_discount_action_gap",
            "etf_opportunity_score_pass",
            "etf_liquidity_pass",
            "etf_risk_pass",
        )
        risk_codes = ()
        main_reasons = (
            f"ETF NAV is {_format_percent(nav_gap)} above aligned market price with passing ETF score, "
            "risk, liquidity, and data-quality thresholds."
        )
        main_risks = "ETF NAV dislocations are usually small and can close quickly or reflect stale inputs."
        invalidation = "NAV gap closes below the action threshold or ETF score/risk/liquidity thresholds fail."
    elif nav_gap >= config.alerts_etf_watch_nav_discount_gap:
        alert_type = "etf_nav_discount_watch"
        priority = "medium"
        status = "open"
        required_gap = config.alerts_etf_watch_nav_discount_gap
        reason_codes = ("etf_nav_discount_watch_gap",)
        risk_codes = ()
        if not thresholds_pass:
            risk_codes = ("etf_thresholds_incomplete",)
        main_reasons = (
            f"ETF NAV is {_format_percent(nav_gap)} above aligned market price, enough for watch-only monitoring."
        )
        main_risks = "The gap is below the action threshold or supporting ETF thresholds are incomplete."
        invalidation = "NAV gap falls below the ETF watch threshold."
    elif nav_gap <= config.alerts_etf_premium_warning_gap:
        alert_type = "etf_nav_premium_warning"
        priority = "medium"
        status = "open"
        required_gap = abs(config.alerts_etf_premium_warning_gap)
        reason_codes = ("etf_market_price_premium_to_nav",)
        risk_codes = ("etf_premium_to_nav",)
        main_reasons = f"ETF market price is {_format_percent(abs(nav_gap))} above NAV."
        main_risks = "Paying a meaningful premium to NAV can create avoidable entry slippage."
        invalidation = "ETF market price returns close to NAV."
    else:
        alert_type = "no_alert"
        priority = "none"
        status = "closed"
        required_gap = config.alerts_etf_action_nav_discount_gap
        reason_codes = ("no_etf_rule_triggered",)
        risk_codes = ()
        main_reasons = "No Phase 5B ETF alert rule triggered."
        main_risks = "Continue monitoring NAV gap, ETF scores, liquidity, and data quality."
        invalidation = "A configured ETF alert rule triggers on a future daily run."

    alert = _make_alert(
        config=config,
        ticker=ticker,
        alert_type=alert_type,
        priority=priority,
        status=status,
        feature=price_feature,
        target=target,
        score=score,
        required_gap=required_gap,
        data_quality_score=data_quality_score,
        reason_codes=tuple(reason_codes),
        risk_codes=tuple(risk_codes),
        data_warnings=nonblocking_warnings,
        main_reasons=main_reasons,
        main_risks=main_risks,
        invalidation=invalidation,
        asset_type="etf",
        alert_model=config.alerts_etf_model_version,
        threshold_set=config.alerts_etf_threshold_set,
        current_price=market_price,
        valuation_gap=nav_gap,
    )
    upsert_alert(config.database_path, alert)
    _record_alert_quality(config, ticker, alert_type, nonblocking_warnings)
    return TickerAlertResult(
        ticker=asset.ticker,
        status="no_alert" if alert_type == "no_alert" else "alerted",
        asset_type="etf",
        alert_type=alert_type,
        priority=priority,
        warnings=nonblocking_warnings,
    )


def compute_alerts(
    config: AppConfig,
    ticker: str | None = None,
    asset_type: str | None = None,
) -> AlertComputationResult:
    wanted_ticker = normalize_ticker(ticker) if ticker else None
    wanted_asset_type = asset_type.strip().lower() if asset_type else None
    assets = [
        asset
        for asset in list_assets(config.database_path)
        if is_scoreable_asset(asset)
        and (wanted_ticker is None or asset.ticker == wanted_ticker)
        and (wanted_asset_type is None or _asset_type(asset.asset_type) == wanted_asset_type)
    ]

    results: list[TickerAlertResult] = []
    for asset in assets:
        if _asset_type(asset.asset_type) == "etf":
            results.append(_compute_etf_alert(config, asset))
        else:
            results.append(_compute_equity_alert(config, asset))
    return AlertComputationResult(results=tuple(results))
