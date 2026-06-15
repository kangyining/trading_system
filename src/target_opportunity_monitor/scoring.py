from __future__ import annotations

from dataclasses import dataclass
from datetime import date
import math
from statistics import mean

from .config import AppConfig
from .storage import (
    Asset,
    EtfFeature,
    Fundamental,
    PriceFeature,
    Score,
    Target,
    insert_data_quality_check,
    is_scoreable_asset,
    latest_etf_feature,
    latest_price_feature,
    list_assets,
    list_estimates,
    list_fundamentals,
    list_signals,
    list_targets,
    normalize_ticker,
    upsert_score,
)
from .valuation import normalize_fundamentals


@dataclass(frozen=True)
class TickerScoreResult:
    ticker: str
    status: str
    asset_type: str
    opportunity_score: float | None
    score_model: str | None
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class ScoreUpdateResult:
    results: tuple[TickerScoreResult, ...]

    @property
    def computed_count(self) -> int:
        return sum(1 for result in self.results if result.status == "computed")

    @property
    def skipped_count(self) -> int:
        return sum(1 for result in self.results if result.status == "skipped")

    @property
    def warning_count(self) -> int:
        return sum(1 for result in self.results if result.warnings)


def _clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    if not math.isfinite(value):
        return 50.0
    return max(low, min(high, value))


def _safe_divide(numerator: float | None, denominator: float | None) -> float | None:
    if numerator is None or denominator in (None, 0):
        return None
    value = numerator / denominator
    return value if math.isfinite(value) else None


def _average(values: list[float]) -> float:
    return mean(values) if values else 50.0


def _score_growth(value: float | None) -> float | None:
    if value is None:
        return None
    return _clamp(50.0 + value * 100.0)


def _latest_target(database_path, ticker: str) -> Target | None:
    targets = list_targets(database_path, ticker)
    return targets[-1] if targets else None


def _asset_type(value: str | None) -> str:
    return (value or "equity").strip().lower()


def _quality_score(fundamental: Fundamental, warnings: list[str]) -> float:
    components: list[float] = []
    net_margin = _safe_divide(fundamental.net_income, fundamental.revenue)
    if net_margin is not None:
        components.append(_clamp(50.0 + net_margin * 150.0))
    fcf_margin = _safe_divide(fundamental.free_cash_flow, fundamental.revenue)
    if fcf_margin is not None:
        components.append(_clamp(50.0 + fcf_margin * 150.0))
    roe = _safe_divide(fundamental.net_income, fundamental.total_equity)
    if roe is not None:
        components.append(_clamp(50.0 + roe * 100.0))
    leverage = _safe_divide(fundamental.net_debt, fundamental.ebitda)
    if leverage is not None:
        components.append(_clamp(80.0 - leverage * 15.0, high=95.0))
    if not components:
        warnings.append("missing_quality_inputs")
    return _average(components)


def _growth_rate(current: float | None, previous: float | None) -> float | None:
    if current is None or previous in (None, 0):
        return None
    if previous <= 0:
        return None
    return current / previous - 1


def _growth_score(fundamentals: list[Fundamental], warnings: list[str]) -> float:
    annuals = [
        item
        for item in sorted(fundamentals, key=lambda row: row.fiscal_period_end)
        if item.report_type.lower() in {"annual", "ttm"}
        or item.fiscal_period.lower() in {"fy", "annual", "ttm"}
    ]
    if len(annuals) < 2:
        warnings.append("insufficient_growth_history")
        return 50.0
    latest = annuals[-1]
    previous = annuals[-2]
    components = [
        score
        for score in (
            _score_growth(_growth_rate(latest.revenue, previous.revenue)),
            _score_growth(_growth_rate(latest.net_income, previous.net_income)),
            _score_growth(_growth_rate(latest.free_cash_flow, previous.free_cash_flow)),
            _score_growth(_growth_rate(latest.diluted_eps, previous.diluted_eps)),
        )
        if score is not None
    ]
    if not components:
        warnings.append("missing_growth_inputs")
    return _average(components)


def _split_warnings(value: str | None) -> list[str]:
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def _latest_revision_signal(config: AppConfig, ticker: str):
    signals = [
        signal
        for signal in list_signals(
            config.database_path,
            ticker=ticker,
            signal_family="analyst_revision",
        )
        if signal.signal_name == "analyst_revision.composite"
        and signal.score is not None
    ]
    return signals[-1] if signals else None


def _revision_score(config: AppConfig, ticker: str, warnings: list[str]) -> float:
    revision_signal = _latest_revision_signal(config, ticker)
    if revision_signal is not None and revision_signal.score is not None:
        warnings.extend(_split_warnings(revision_signal.data_warnings))
        if config.signals_analyst_revision_shadow_mode:
            warnings.append("revision_signal_shadow_mode")
        return _clamp(revision_signal.score)

    estimates = list_estimates(config.database_path, ticker)
    if not estimates:
        warnings.append("missing_estimates")
        return 50.0
    revisions: list[float] = []
    for estimate in estimates:
        if estimate.revision_1m is not None:
            revisions.append(estimate.revision_1m)
        if estimate.revision_3m is not None:
            revisions.append(estimate.revision_3m)
    if not revisions:
        warnings.append("missing_revision_data")
        return 50.0
    return _clamp(50.0 + mean(revisions) * 100.0)


def _momentum_score(feature: PriceFeature, warnings: list[str]) -> float:
    weighted_values = [
        (feature.return_1m, 0.25),
        (feature.return_3m, 0.35),
        (feature.return_6m, 0.25),
        (feature.return_12m, 0.15),
    ]
    usable = [
        (_clamp(50.0 + (value or 0.0) * 100.0), weight)
        for value, weight in weighted_values
        if value is not None
    ]
    if not usable:
        warnings.append("missing_momentum_inputs")
        return 50.0
    total_weight = sum(weight for _score, weight in usable)
    return sum(score * weight for score, weight in usable) / total_weight


def _risk_score(feature: PriceFeature, target: Target | None, warnings: list[str]) -> float:
    components: list[float] = []
    volatility = feature.realized_volatility_60d or feature.realized_volatility_20d
    if volatility is not None:
        components.append(_clamp(100.0 - volatility * 150.0))
    else:
        warnings.append("missing_volatility")
    if target and target.valuation_confidence is not None:
        components.append(_clamp(target.valuation_confidence))
    else:
        warnings.append("missing_valuation_confidence")
    return _average(components)


def _liquidity_score(feature: PriceFeature, warnings: list[str]) -> float:
    dollar_volume = feature.average_dollar_volume_20d
    if dollar_volume is None or dollar_volume <= 0:
        warnings.append("missing_liquidity")
        return 50.0
    return _clamp((math.log10(dollar_volume) - 5.0) * 20.0)


def _confidence_score(target: Target, warning_count: int) -> float:
    components: list[float] = []
    if target.valuation_confidence is not None:
        components.append(_clamp(target.valuation_confidence))
    if target.method_count is not None:
        components.append(_clamp(target.method_count / 6.0 * 100.0))
    components.append(_clamp(100.0 - warning_count * 8.0))
    return _average(components)


def _price_location_score(
    current_price: float | None,
    target: Target,
) -> float:
    if current_price is None or current_price <= 0:
        return 50.0
    if target.target_low is not None and current_price < target.target_low:
        return 100.0
    if target.target_high is not None and current_price > target.target_high:
        return 20.0
    if target.base_target is None:
        return 50.0
    gap = target.base_target / current_price - 1
    return _clamp(50.0 + gap * 100.0)


def _score_reason(parts: dict[str, float | str | None]) -> str:
    reason_parts = []
    for key, value in parts.items():
        if isinstance(value, float):
            reason_parts.append(f"{key}={value:.2f}")
        elif value is not None:
            reason_parts.append(f"{key}={value}")
    return "; ".join(reason_parts)


def _record_score_quality(config: AppConfig, ticker: str, warnings: tuple[str, ...]) -> None:
    insert_data_quality_check(
        config.database_path,
        check_name=f"scoring:{ticker}",
        status="warning" if warnings else "ok",
        details=", ".join(warnings) if warnings else "score_computed",
        source="scoring",
        as_of_date=date.today().isoformat(),
    )


def _record_score_skip(config: AppConfig, ticker: str, warnings: tuple[str, ...]) -> None:
    insert_data_quality_check(
        config.database_path,
        check_name=f"scoring:{ticker}",
        status="warning",
        details=", ".join(warnings),
        source="scoring",
        as_of_date=date.today().isoformat(),
    )


def _compute_equity_score(config: AppConfig, asset: Asset) -> TickerScoreResult:
    ticker = asset.ticker
    warnings: list[str] = []
    feature = latest_price_feature(config.database_path, ticker)
    target = _latest_target(config.database_path, ticker)
    fundamentals = list_fundamentals(config.database_path, ticker)
    normalized = normalize_fundamentals(fundamentals)

    if feature is None or feature.current_price is None:
        warnings.append("missing_price_feature")
    if target is None or target.base_target is None or target.valuation_gap is None:
        warnings.append("missing_target")
    if normalized is None:
        warnings.append("missing_fundamentals")

    fatal_warnings = tuple(warnings)
    if (
        feature is None
        or feature.current_price is None
        or target is None
        or target.base_target is None
        or target.valuation_gap is None
        or normalized is None
    ):
        _record_score_skip(config, ticker, fatal_warnings)
        return TickerScoreResult(
            ticker=ticker,
            status="skipped",
            asset_type="equity",
            opportunity_score=None,
            score_model=config.scoring_equity_model_version,
            warnings=fatal_warnings,
        )

    latest_fundamental = sorted(fundamentals, key=lambda item: item.fiscal_period_end)[-1]
    valuation_gap_score = _clamp(50.0 + (target.valuation_gap or 0.0) * 100.0)
    quality_score = _quality_score(latest_fundamental, warnings)
    growth_score = _growth_score(fundamentals, warnings)
    revision_score = _revision_score(config, ticker, warnings)
    revision_contribution_score = (
        50.0 if config.signals_analyst_revision_shadow_mode else revision_score
    )
    momentum_score = _momentum_score(feature, warnings)
    risk_score = _risk_score(feature, target, warnings)
    liquidity_score = _liquidity_score(feature, warnings)
    confidence_score = _confidence_score(target, len(warnings))
    timing_score = (
        momentum_score * 0.50
        + risk_score * 0.20
        + _price_location_score(feature.current_price, target) * 0.30
    )
    expected_value_score = (
        valuation_gap_score * 0.50
        + confidence_score * 0.30
        + risk_score * 0.20
    )
    opportunity_score = (
        expected_value_score * 0.35
        + timing_score * 0.20
        + quality_score * 0.15
        + growth_score * 0.10
        + revision_contribution_score * 0.10
        + liquidity_score * 0.05
        + risk_score * 0.05
    )
    score_warnings = tuple(dict.fromkeys(warnings))
    score = Score(
        ticker=ticker,
        score_date=date.today().isoformat(),
        valuation_gap_score=valuation_gap_score,
        quality_score=quality_score,
        growth_score=growth_score,
        revision_score=revision_score,
        momentum_score=momentum_score,
        risk_score=risk_score,
        liquidity_score=liquidity_score,
        confidence_score=confidence_score,
        timing_score=timing_score,
        expected_value_score=expected_value_score,
        opportunity_score=opportunity_score,
        asset_type="equity",
        score_model=config.scoring_equity_model_version,
        threshold_set=config.scoring_equity_threshold_set,
        score_reason=_score_reason(
            {
                "valuation": valuation_gap_score,
                "expected_value": expected_value_score,
                "timing": timing_score,
                "quality": quality_score,
                "growth": growth_score,
                "revision": revision_score,
                "revision_contribution": revision_contribution_score,
                "risk": risk_score,
                "liquidity": liquidity_score,
            }
        ),
        data_warnings=", ".join(score_warnings) if score_warnings else None,
        model_version=config.scoring_equity_model_version,
        source="scoring",
        as_of_date=date.today().isoformat(),
        effective_date=date.today().isoformat(),
    )
    upsert_score(config.database_path, score)
    _record_score_quality(config, ticker, score_warnings)
    return TickerScoreResult(
        ticker=ticker,
        status="computed",
        asset_type="equity",
        opportunity_score=opportunity_score,
        score_model=config.scoring_equity_model_version,
        warnings=score_warnings,
    )


def _etf_nav_gap(feature: EtfFeature, price_feature: PriceFeature | None) -> float | None:
    price = feature.market_price
    if price is None and price_feature is not None:
        price = price_feature.current_price
    if price in (None, 0) or feature.nav_per_share is None:
        return None
    return feature.nav_per_share / price - 1


def _compute_etf_score(config: AppConfig, asset: Asset) -> TickerScoreResult:
    ticker = asset.ticker
    warnings: list[str] = []
    feature = latest_etf_feature(config.database_path, ticker)
    price_feature = latest_price_feature(config.database_path, ticker)
    if feature is None or feature.nav_per_share is None:
        warnings.append("missing_etf_nav")
        _record_score_skip(config, ticker, tuple(warnings))
        return TickerScoreResult(
            ticker=ticker,
            status="skipped",
            asset_type="etf",
            opportunity_score=None,
            score_model=config.scoring_etf_model_version,
            warnings=tuple(warnings),
        )
    if price_feature is None:
        warnings.append("missing_price_feature")

    nav_gap = _etf_nav_gap(feature, price_feature)
    if nav_gap is None:
        warnings.append("missing_etf_nav_gap")
        nav_gap = 0.0
    band = config.etf_default_premium_discount_band or 0.005
    valuation_gap_score = _clamp(50.0 + nav_gap / band * 25.0)
    if feature.premium_discount_zscore is None:
        warnings.append("missing_premium_discount_zscore")
        zscore_score = 50.0
    else:
        zscore_score = _clamp(50.0 - feature.premium_discount_zscore * 15.0)
    momentum_score = _momentum_score(price_feature, warnings) if price_feature else 50.0
    risk_score = _risk_score(price_feature, None, warnings) if price_feature else 50.0
    liquidity_score = _liquidity_score(price_feature, warnings) if price_feature else 50.0
    concentration_components: list[float] = []
    if feature.largest_holding_weight is not None:
        concentration_components.append(_clamp(100.0 - feature.largest_holding_weight * 250.0))
    if feature.top_10_weight is not None:
        concentration_components.append(_clamp(100.0 - max(0.0, feature.top_10_weight - 0.25) * 100.0))
    if not concentration_components:
        warnings.append("missing_etf_holdings")
    holdings_score = _average(concentration_components)
    confidence_score = _average(
        [
            90.0 if feature.latest_nav_date else 50.0,
            80.0 if feature.holdings_count else 50.0,
            _clamp(100.0 - len(warnings) * 10.0),
        ]
    )
    timing_score = _average([valuation_gap_score, zscore_score, momentum_score])
    expected_value_score = (
        valuation_gap_score * 0.55
        + confidence_score * 0.25
        + risk_score * 0.20
    )
    opportunity_score = (
        expected_value_score * 0.40
        + timing_score * 0.25
        + liquidity_score * 0.15
        + risk_score * 0.10
        + holdings_score * 0.10
    )
    score_warnings = tuple(dict.fromkeys(warnings))
    score = Score(
        ticker=ticker,
        score_date=date.today().isoformat(),
        valuation_gap_score=valuation_gap_score,
        quality_score=holdings_score,
        growth_score=None,
        revision_score=zscore_score,
        momentum_score=momentum_score,
        risk_score=risk_score,
        liquidity_score=liquidity_score,
        confidence_score=confidence_score,
        timing_score=timing_score,
        expected_value_score=expected_value_score,
        opportunity_score=opportunity_score,
        asset_type="etf",
        score_model=config.scoring_etf_model_version,
        threshold_set=config.scoring_etf_threshold_set,
        score_reason=_score_reason(
            {
                "nav_gap": nav_gap,
                "nav_score": valuation_gap_score,
                "pd_zscore_score": zscore_score,
                "momentum": momentum_score,
                "liquidity": liquidity_score,
                "holdings": holdings_score,
            }
        ),
        data_warnings=", ".join(score_warnings) if score_warnings else None,
        model_version=config.scoring_etf_model_version,
        source="scoring",
        as_of_date=date.today().isoformat(),
        effective_date=date.today().isoformat(),
    )
    upsert_score(config.database_path, score)
    _record_score_quality(config, ticker, score_warnings)
    return TickerScoreResult(
        ticker=ticker,
        status="computed",
        asset_type="etf",
        opportunity_score=opportunity_score,
        score_model=config.scoring_etf_model_version,
        warnings=score_warnings,
    )


def compute_scores(
    config: AppConfig,
    ticker: str | None = None,
    asset_type: str | None = None,
) -> ScoreUpdateResult:
    wanted_ticker = normalize_ticker(ticker) if ticker else None
    wanted_asset_type = asset_type.strip().lower() if asset_type else None
    allow_explicit_etf_reference = wanted_ticker is not None and wanted_asset_type == "etf"
    assets = [
        asset
        for asset in list_assets(config.database_path)
        if (
            is_scoreable_asset(asset)
            or (allow_explicit_etf_reference and _asset_type(asset.asset_type) == "etf")
        )
        and (wanted_ticker is None or asset.ticker == wanted_ticker)
        and (wanted_asset_type is None or _asset_type(asset.asset_type) == wanted_asset_type)
    ]

    results: list[TickerScoreResult] = []
    for asset in assets:
        if _asset_type(asset.asset_type) == "etf":
            results.append(_compute_etf_score(config, asset))
        else:
            results.append(_compute_equity_score(config, asset))
    return ScoreUpdateResult(results=tuple(results))
