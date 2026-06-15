from __future__ import annotations

from dataclasses import dataclass
from datetime import date
import math
from statistics import median
from typing import TYPE_CHECKING

from .config import AppConfig
from .etf_data import compute_etf_feature
from .storage import (
    Asset,
    Estimate,
    Fundamental,
    Target,
    insert_data_quality_check,
    is_scoreable_asset,
    latest_estimate,
    latest_etf_holdings,
    latest_etf_feature,
    latest_price_feature,
    list_assets,
    list_etf_navs,
    list_estimates,
    list_fundamentals,
    normalize_ticker,
    upsert_etf_feature,
    upsert_target,
)

if TYPE_CHECKING:
    from .foreign_equity_sources import ForeignEquityAnalystTarget


FLOW_FIELDS = (
    "revenue",
    "gross_profit",
    "operating_income",
    "ebitda",
    "ebit",
    "net_income",
    "eps",
    "diluted_eps",
    "cash_from_operations",
    "capital_expenditure",
    "free_cash_flow",
)

BALANCE_FIELDS = (
    "cash_and_equivalents",
    "total_debt",
    "net_debt",
    "total_assets",
    "total_equity",
    "shares_outstanding",
    "diluted_shares",
)


@dataclass(frozen=True)
class NormalizedFundamental:
    ticker: str
    fiscal_period_end: str
    currency: str | None
    revenue: float | None
    gross_profit: float | None
    operating_income: float | None
    ebitda: float | None
    ebit: float | None
    net_income: float | None
    eps: float | None
    diluted_eps: float | None
    cash_from_operations: float | None
    capital_expenditure: float | None
    free_cash_flow: float | None
    cash_and_equivalents: float | None
    total_debt: float | None
    net_debt: float | None
    total_assets: float | None
    total_equity: float | None
    shares_outstanding: float | None
    diluted_shares: float | None
    source: str


@dataclass(frozen=True)
class ValuationInputs:
    current_price: float
    shares: float
    market_cap: float
    enterprise_value: float
    net_debt: float
    trailing_eps: float | None
    forward_eps: float | None
    ebitda: float | None
    free_cash_flow: float | None
    revenue: float | None


@dataclass(frozen=True)
class MethodTarget:
    name: str
    value: float


@dataclass(frozen=True)
class TickerValuationResult:
    ticker: str
    status: str
    current_price: float | None
    base_target: float | None
    target_low: float | None
    target_high: float | None
    valuation_gap: float | None
    valuation_score: float | None
    valuation_confidence: float | None
    method_count: int
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class ValuationUpdateResult:
    results: tuple[TickerValuationResult, ...]

    @property
    def computed_count(self) -> int:
        return sum(1 for result in self.results if result.status == "computed")

    @property
    def skipped_count(self) -> int:
        return sum(1 for result in self.results if result.status == "skipped")

    @property
    def warning_count(self) -> int:
        return sum(1 for result in self.results if result.warnings)


def _safe_divide(numerator: float | None, denominator: float | None) -> float | None:
    if numerator is None or denominator in (None, 0):
        return None
    value = numerator / denominator
    if not math.isfinite(value):
        return None
    return value


def _positive(value: float | None) -> float | None:
    if value is None or value <= 0 or not math.isfinite(value):
        return None
    return value


def _is_annual_or_ttm(fundamental: Fundamental) -> bool:
    fiscal_period = fundamental.fiscal_period.strip().lower()
    report_type = fundamental.report_type.strip().lower()
    return fiscal_period in {"fy", "annual", "ttm"} or report_type in {"annual", "ttm"}


def _is_quarterly(fundamental: Fundamental) -> bool:
    fiscal_period = fundamental.fiscal_period.strip().lower()
    report_type = fundamental.report_type.strip().lower()
    return fiscal_period.startswith("q") or report_type == "quarterly"


def _latest_balance_value(latest: Fundamental, field_name: str) -> float | None:
    return getattr(latest, field_name)


def _sum_field(rows: list[Fundamental], field_name: str) -> float | None:
    values = [getattr(row, field_name) for row in rows]
    usable = [value for value in values if value is not None]
    if len(usable) != len(rows):
        return None
    return sum(usable)


def normalize_fundamentals(rows: list[Fundamental]) -> NormalizedFundamental | None:
    if not rows:
        return None

    ordered = sorted(rows, key=lambda item: item.fiscal_period_end)
    annual_or_ttm = [row for row in ordered if _is_annual_or_ttm(row)]
    if annual_or_ttm:
        latest = annual_or_ttm[-1]
        return NormalizedFundamental(
            ticker=latest.ticker,
            fiscal_period_end=latest.fiscal_period_end,
            currency=latest.currency,
            revenue=latest.revenue,
            gross_profit=latest.gross_profit,
            operating_income=latest.operating_income,
            ebitda=latest.ebitda,
            ebit=latest.ebit,
            net_income=latest.net_income,
            eps=latest.eps,
            diluted_eps=latest.diluted_eps,
            cash_from_operations=latest.cash_from_operations,
            capital_expenditure=latest.capital_expenditure,
            free_cash_flow=latest.free_cash_flow,
            cash_and_equivalents=latest.cash_and_equivalents,
            total_debt=latest.total_debt,
            net_debt=latest.net_debt,
            total_assets=latest.total_assets,
            total_equity=latest.total_equity,
            shares_outstanding=latest.shares_outstanding,
            diluted_shares=latest.diluted_shares,
            source=latest.source,
        )

    quarterly = [row for row in ordered if _is_quarterly(row)]
    if len(quarterly) < 4:
        return None

    latest_four = quarterly[-4:]
    latest = latest_four[-1]
    flow_payload = {field: _sum_field(latest_four, field) for field in FLOW_FIELDS}
    balance_payload = {field: _latest_balance_value(latest, field) for field in BALANCE_FIELDS}
    return NormalizedFundamental(
        ticker=latest.ticker,
        fiscal_period_end=latest.fiscal_period_end,
        currency=latest.currency,
        source=latest.source,
        **flow_payload,
        **balance_payload,
    )


def _estimate_value(estimate: Estimate | None) -> float | None:
    if estimate is None:
        return None
    return (
        _positive(estimate.consensus_mean)
        or _positive(estimate.consensus_median)
        or _positive(estimate.consensus_high)
        or _positive(estimate.consensus_low)
    )


def build_inputs(
    current_price: float | None,
    fundamental: NormalizedFundamental | None,
    forward_eps: float | None,
) -> tuple[ValuationInputs | None, list[str]]:
    warnings: list[str] = []
    price = _positive(current_price)
    if price is None:
        warnings.append("missing_current_price")

    if fundamental is None:
        warnings.append("missing_usable_fundamentals")
        return None, warnings

    shares = _positive(fundamental.diluted_shares) or _positive(
        fundamental.shares_outstanding
    )
    if shares is None:
        warnings.append("missing_shares")

    if price is None or shares is None:
        return None, warnings

    market_cap = price * shares
    if fundamental.net_debt is not None:
        net_debt = fundamental.net_debt
    else:
        net_debt = (fundamental.total_debt or 0.0) - (
            fundamental.cash_and_equivalents or 0.0
        )
    enterprise_value = market_cap + net_debt
    free_cash_flow = fundamental.free_cash_flow
    if free_cash_flow is None and fundamental.cash_from_operations is not None:
        capital_expenditure = fundamental.capital_expenditure or 0.0
        free_cash_flow = (
            fundamental.cash_from_operations + capital_expenditure
            if capital_expenditure < 0
            else fundamental.cash_from_operations - capital_expenditure
        )

    return (
        ValuationInputs(
            current_price=price,
            shares=shares,
            market_cap=market_cap,
            enterprise_value=enterprise_value,
            net_debt=net_debt,
            trailing_eps=_positive(fundamental.diluted_eps)
            or _positive(fundamental.eps),
            forward_eps=_positive(forward_eps),
            ebitda=_positive(fundamental.ebitda),
            free_cash_flow=_positive(free_cash_flow),
            revenue=_positive(fundamental.revenue),
        ),
        warnings,
    )


def compute_ratios(inputs: ValuationInputs) -> dict[str, float | None]:
    return {
        "trailing_pe": _safe_divide(inputs.current_price, inputs.trailing_eps),
        "forward_pe": _safe_divide(inputs.current_price, inputs.forward_eps),
        "ev_ebitda": _safe_divide(inputs.enterprise_value, inputs.ebitda),
        "p_fcf": _safe_divide(inputs.market_cap, inputs.free_cash_flow),
        "p_s": _safe_divide(inputs.market_cap, inputs.revenue),
    }


def _asset_supported(asset: Asset) -> bool:
    asset_type = (asset.asset_type or "equity").strip().lower()
    return asset_type in {"equity", "stock", "common_stock"}


def _asset_is_etf(asset: Asset) -> bool:
    asset_type = (asset.asset_type or "").strip().lower()
    return asset_type in {"etf", "fund", "index_etf"}


def _peer_assets(asset: Asset, assets: list[Asset]) -> list[Asset]:
    same_industry = [
        peer
        for peer in assets
        if peer.ticker != asset.ticker
        and _asset_supported(peer)
        and peer.industry
        and asset.industry
        and peer.industry.strip().lower() == asset.industry.strip().lower()
    ]
    if same_industry:
        return same_industry
    return [
        peer
        for peer in assets
        if peer.ticker != asset.ticker
        and _asset_supported(peer)
        and peer.sector
        and asset.sector
        and peer.sector.strip().lower() == asset.sector.strip().lower()
    ]


def _peer_inputs(
    config: AppConfig,
    peer: Asset,
) -> ValuationInputs | None:
    feature = latest_price_feature(config.database_path, peer.ticker)
    fundamental = normalize_fundamentals(
        list_fundamentals(config.database_path, peer.ticker)
    )
    estimate = latest_estimate(config.database_path, peer.ticker, "eps")
    inputs, warnings = build_inputs(
        feature.current_price if feature else None,
        fundamental,
        _estimate_value(estimate),
    )
    return inputs if inputs is not None and not warnings else inputs


def _target_from_ev(
    target_ev: float | None,
    net_debt: float,
    shares: float,
) -> float | None:
    if target_ev is None:
        return None
    return _positive((target_ev - net_debt) / shares)


def _target_from_market_cap(target_market_cap: float | None, shares: float) -> float | None:
    if target_market_cap is None:
        return None
    return _positive(target_market_cap / shares)


def _historical_multiples(
    current_price: float,
    current_enterprise_value: float,
    fundamentals: list[Fundamental],
) -> dict[str, list[float]]:
    ordered = sorted(fundamentals, key=lambda item: item.fiscal_period_end)
    current = normalize_fundamentals(ordered)
    if current is None:
        return {"pe": [], "ev_ebitda": [], "p_fcf": []}

    historical_rows = [row for row in ordered if row.fiscal_period_end < current.fiscal_period_end]
    historical = [row for row in historical_rows if _is_annual_or_ttm(row)]
    multiples = {"pe": [], "ev_ebitda": [], "p_fcf": []}
    for row in historical:
        shares = _positive(row.diluted_shares) or _positive(row.shares_outstanding)
        eps = _positive(row.diluted_eps) or _positive(row.eps)
        if eps is not None:
            multiples["pe"].append(current_price / eps)

        ebitda = _positive(row.ebitda)
        if ebitda is not None:
            multiples["ev_ebitda"].append(current_enterprise_value / ebitda)

        fcf = _positive(row.free_cash_flow)
        if fcf is not None and shares is not None:
            multiples["p_fcf"].append(current_price * shares / fcf)
    return multiples


def _method_targets(
    config: AppConfig,
    asset: Asset,
    assets: list[Asset],
    inputs: ValuationInputs,
    fundamentals: list[Fundamental],
) -> tuple[list[MethodTarget], list[str]]:
    methods: list[MethodTarget] = []
    warnings: list[str] = []

    peers = _peer_assets(asset, assets)
    peer_inputs = [
        peer_input
        for peer in peers
        if (peer_input := _peer_inputs(config, peer)) is not None
    ]
    peer_ratios = [compute_ratios(peer_input) for peer_input in peer_inputs]

    if len(peer_ratios) >= config.valuation_minimum_peer_count:
        forward_pe_values = [
            ratio["forward_pe"] for ratio in peer_ratios if _positive(ratio["forward_pe"])
        ]
        ev_ebitda_values = [
            ratio["ev_ebitda"] for ratio in peer_ratios if _positive(ratio["ev_ebitda"])
        ]
        p_fcf_values = [
            ratio["p_fcf"] for ratio in peer_ratios if _positive(ratio["p_fcf"])
        ]

        if inputs.forward_eps is not None and forward_pe_values:
            methods.append(
                MethodTarget("forward_pe", inputs.forward_eps * median(forward_pe_values))
            )
        if inputs.ebitda is not None and ev_ebitda_values:
            target = _target_from_ev(
                inputs.ebitda * median(ev_ebitda_values),
                inputs.net_debt,
                inputs.shares,
            )
            if target is not None:
                methods.append(MethodTarget("peer_ev_ebitda", target))
        if inputs.free_cash_flow is not None and p_fcf_values:
            target = _target_from_market_cap(
                inputs.free_cash_flow * median(p_fcf_values),
                inputs.shares,
            )
            if target is not None:
                methods.append(MethodTarget("peer_p_fcf", target))
    else:
        warnings.append("insufficient_peer_count")

    historical = _historical_multiples(
        inputs.current_price, inputs.enterprise_value, fundamentals
    )
    if inputs.trailing_eps is not None and len(historical["pe"]) >= 2:
        methods.append(MethodTarget("historical_pe", inputs.trailing_eps * median(historical["pe"])))
    if inputs.ebitda is not None and len(historical["ev_ebitda"]) >= 2:
        target = _target_from_ev(
            inputs.ebitda * median(historical["ev_ebitda"]),
            inputs.net_debt,
            inputs.shares,
        )
        if target is not None:
            methods.append(MethodTarget("historical_ev_ebitda", target))
    if inputs.free_cash_flow is not None and len(historical["p_fcf"]) >= 2:
        target = _target_from_market_cap(
            inputs.free_cash_flow * median(historical["p_fcf"]),
            inputs.shares,
        )
        if target is not None:
            methods.append(MethodTarget("historical_p_fcf", target))

    if inputs.forward_eps is None:
        warnings.append("missing_eps_estimate")

    return methods, warnings


def _freshness_warnings(
    config: AppConfig,
    fundamental: NormalizedFundamental | None,
    estimate: Estimate | None,
) -> list[str]:
    warnings: list[str] = []
    today = date.today()
    if fundamental is not None:
        try:
            period_end = date.fromisoformat(fundamental.fiscal_period_end)
            if (today - period_end).days > config.valuation_stale_fundamentals_after_days:
                warnings.append("stale_fundamentals")
        except ValueError:
            warnings.append("malformed_fundamental_date")
    if estimate is not None:
        try:
            estimate_date = date.fromisoformat(estimate.estimate_date)
            if (today - estimate_date).days > config.valuation_stale_estimates_after_days:
                warnings.append("stale_estimates")
        except ValueError:
            warnings.append("malformed_estimate_date")
    return warnings


def _combine_targets(
    config: AppConfig,
    ticker: str,
    current_price: float,
    method_targets: list[MethodTarget],
    warnings: list[str],
) -> Target | None:
    values = [
        target.value
        for target in method_targets
        if target.value > 0 and math.isfinite(target.value)
    ]
    if len(values) < config.valuation_minimum_methods:
        return None

    base_target = median(values)
    if len(values) == 1:
        band = config.valuation_default_uncertainty_band
        target_low = base_target * (1 - band)
        target_high = base_target * (1 + band)
    else:
        target_low = min(values)
        target_high = max(values)
        band = (target_high - target_low) / base_target if base_target else None

    valuation_gap = base_target / current_price - 1
    valuation_score = max(0.0, min(100.0, 50.0 + valuation_gap * 100.0))
    dispersion = (
        (target_high - target_low) / base_target
        if base_target and target_high is not None and target_low is not None
        else 0.0
    )
    valuation_confidence = 35.0 + min(45.0, len(values) * 15.0)
    valuation_confidence -= min(25.0, dispersion * 25.0)
    valuation_confidence -= min(20.0, len(warnings) * 4.0)
    valuation_confidence = max(0.0, min(100.0, valuation_confidence))

    reason = "; ".join(f"{target.name}={target.value:.4f}" for target in method_targets)
    return Target(
        ticker=ticker,
        target_date=date.today().isoformat(),
        base_target=base_target,
        target_low=target_low,
        target_high=target_high,
        valuation_gap=valuation_gap,
        target_method=";".join(target.name for target in method_targets),
        uncertainty_band=band,
        valuation_score=valuation_score,
        valuation_confidence=valuation_confidence,
        method_count=len(values),
        target_reason=reason,
        data_warnings=", ".join(warnings) if warnings else None,
        model_version=config.valuation_model_version,
        source="valuation",
        as_of_date=date.today().isoformat(),
        effective_date=date.today().isoformat(),
    )


def _foreign_analyst_target_fallback(
    config: AppConfig,
    ticker: str,
    current_price: float,
    target: "ForeignEquityAnalystTarget",
    warnings: list[str],
) -> Target:
    base_target = target.target_mean
    if target.target_low is not None and target.target_high is not None:
        target_low = target.target_low
        target_high = target.target_high
        band = (target_high - target_low) / base_target if base_target else None
    else:
        band = config.valuation_default_uncertainty_band
        target_low = base_target * (1 - band)
        target_high = base_target * (1 + band)

    valuation_gap = base_target / current_price - 1
    valuation_score = max(0.0, min(100.0, 50.0 + valuation_gap * 100.0))
    dispersion = (
        (target_high - target_low) / base_target
        if base_target and target_high is not None and target_low is not None
        else 0.0
    )
    valuation_confidence = 35.0 + 15.0
    valuation_confidence -= min(25.0, dispersion * 25.0)
    valuation_confidence -= min(20.0, len(warnings) * 4.0)
    valuation_confidence = max(0.0, min(100.0, valuation_confidence))

    reason_parts = [
        f"source_backed_analyst_target={base_target:.4f}",
        f"source={target.source}",
    ]
    if target.target_low is not None:
        reason_parts.append(f"target_low={target.target_low:.4f}")
    if target.target_high is not None:
        reason_parts.append(f"target_high={target.target_high:.4f}")
    if target.analyst_count is not None:
        reason_parts.append(f"analyst_count={target.analyst_count}")

    return Target(
        ticker=ticker,
        target_date=date.today().isoformat(),
        base_target=base_target,
        target_low=target_low,
        target_high=target_high,
        valuation_gap=valuation_gap,
        target_method="source_backed_analyst_target",
        uncertainty_band=band,
        valuation_score=valuation_score,
        valuation_confidence=valuation_confidence,
        method_count=1,
        target_reason="; ".join(reason_parts),
        data_warnings=", ".join(dict.fromkeys(warnings)) if warnings else None,
        model_version=config.valuation_model_version,
        source="foreign_equity_analyst_target",
        as_of_date=date.today().isoformat(),
        effective_date=date.today().isoformat(),
    )


def _record_quality(config: AppConfig, result: TickerValuationResult) -> None:
    if result.warnings:
        status = "warning"
        details = f"{result.ticker}: {', '.join(result.warnings)}"
    else:
        status = "ok"
        details = (
            f"{result.ticker}: target={result.base_target}; "
            f"methods={result.method_count}"
        )
    insert_data_quality_check(
        config.database_path,
        check_name=f"valuation:{result.ticker}",
        status=status,
        details=details,
        source="valuation",
        as_of_date=date.today().isoformat(),
    )


def _etf_freshness_warnings(config: AppConfig, latest_nav_date: str | None, latest_holdings_date: str | None) -> list[str]:
    warnings: list[str] = []
    today = date.today()
    if latest_nav_date is not None:
        try:
            nav_date = date.fromisoformat(latest_nav_date)
            if (today - nav_date).days > config.etf_stale_nav_after_days:
                warnings.append("stale_etf_nav")
        except ValueError:
            warnings.append("malformed_etf_nav_date")
    if latest_holdings_date is not None:
        try:
            holdings_date = date.fromisoformat(latest_holdings_date)
            if (today - holdings_date).days > config.etf_stale_holdings_after_days:
                warnings.append("stale_etf_holdings")
        except ValueError:
            warnings.append("malformed_etf_holdings_date")
    return warnings


def _compute_etf_target(
    config: AppConfig,
    asset: Asset,
    current_price: float | None,
) -> tuple[Target | None, tuple[str, ...]]:
    warnings: list[str] = []
    price = _positive(current_price)
    if price is None:
        warnings.append("missing_current_price")

    navs = list_etf_navs(config.database_path, asset.ticker)
    holdings = latest_etf_holdings(config.database_path, asset.ticker)
    feature = compute_etf_feature(
        asset.ticker,
        navs,
        holdings,
        price,
        config.etf_premium_discount_history_days,
    )
    if feature is not None:
        upsert_etf_feature(config.database_path, feature)
    else:
        feature = latest_etf_feature(config.database_path, asset.ticker)

    if feature is None or feature.nav_per_share is None:
        warnings.append("missing_etf_nav")
        return None, tuple(dict.fromkeys(warnings))

    if feature.holdings_count is None:
        warnings.append("missing_etf_holdings")
    elif feature.holdings_count < config.etf_minimum_holdings:
        warnings.append("insufficient_etf_holdings")

    if feature.premium_discount_average_60d is None:
        warnings.append("insufficient_premium_discount_history")

    warnings.extend(
        _etf_freshness_warnings(
            config, feature.latest_nav_date, feature.latest_holdings_date
        )
    )

    if price is None:
        return None, tuple(dict.fromkeys(warnings))

    nav = feature.nav_per_share
    band = config.etf_default_premium_discount_band
    valuation_gap = nav / price - 1
    valuation_score = max(0.0, min(100.0, 50.0 + valuation_gap / band * 25.0))
    valuation_confidence = 75.0
    if feature.premium_discount_zscore is not None:
        valuation_confidence += 5.0
    valuation_confidence -= min(35.0, len(warnings) * 6.0)
    valuation_confidence = max(0.0, min(100.0, valuation_confidence))

    reason_parts = [
        f"nav={nav:.4f}",
        f"price={price:.4f}",
        f"premium_discount={(feature.premium_discount or 0.0):.6f}",
    ]
    if feature.premium_discount_zscore is not None:
        reason_parts.append(f"pd_zscore={feature.premium_discount_zscore:.4f}")

    target = Target(
        ticker=asset.ticker,
        target_date=date.today().isoformat(),
        base_target=nav,
        target_low=nav * (1 - band),
        target_high=nav * (1 + band),
        valuation_gap=valuation_gap,
        target_method="etf_nav",
        uncertainty_band=band,
        valuation_score=valuation_score,
        valuation_confidence=valuation_confidence,
        method_count=1,
        target_reason="; ".join(reason_parts),
        data_warnings=", ".join(dict.fromkeys(warnings)) if warnings else None,
        model_version=config.etf_model_version,
        source="etf_valuation",
        as_of_date=date.today().isoformat(),
        effective_date=date.today().isoformat(),
    )
    return target, tuple(dict.fromkeys(warnings))


def compute_targets(config: AppConfig, ticker: str | None = None) -> ValuationUpdateResult:
    all_database_assets = list_assets(config.database_path)
    assets = [asset for asset in all_database_assets if is_scoreable_asset(asset)]
    if ticker:
        wanted = normalize_ticker(ticker)
        assets = [
            asset
            for asset in all_database_assets
            if asset.ticker == wanted and (is_scoreable_asset(asset) or _asset_is_etf(asset))
        ]

    all_assets = [asset for asset in all_database_assets if is_scoreable_asset(asset)]
    results: list[TickerValuationResult] = []
    for asset in assets:
        warnings: list[str] = []
        feature = latest_price_feature(config.database_path, asset.ticker)
        current_price = feature.current_price if feature is not None else None

        if _asset_is_etf(asset):
            target, target_warnings = _compute_etf_target(config, asset, current_price)
            if target is None:
                result = TickerValuationResult(
                    ticker=asset.ticker,
                    status="skipped",
                    current_price=current_price,
                    base_target=None,
                    target_low=None,
                    target_high=None,
                    valuation_gap=None,
                    valuation_score=None,
                    valuation_confidence=None,
                    method_count=0,
                    warnings=target_warnings,
                )
                _record_quality(config, result)
                results.append(result)
                continue

            upsert_target(config.database_path, target)
            result = TickerValuationResult(
                ticker=asset.ticker,
                status="computed",
                current_price=current_price,
                base_target=target.base_target,
                target_low=target.target_low,
                target_high=target.target_high,
                valuation_gap=target.valuation_gap,
                valuation_score=target.valuation_score,
                valuation_confidence=target.valuation_confidence,
                method_count=target.method_count or 0,
                warnings=target_warnings,
            )
            _record_quality(config, result)
            results.append(result)
            continue

        if not _asset_supported(asset):
            result = TickerValuationResult(
                ticker=asset.ticker,
                status="skipped",
                current_price=current_price,
                base_target=None,
                target_low=None,
                target_high=None,
                valuation_gap=None,
                valuation_score=None,
                valuation_confidence=None,
                method_count=0,
                warnings=("unsupported_asset_type",),
            )
            _record_quality(config, result)
            results.append(result)
            continue

        fundamentals = list_fundamentals(config.database_path, asset.ticker)
        normalized = normalize_fundamentals(fundamentals)
        estimate = latest_estimate(config.database_path, asset.ticker, "eps")
        forward_eps = _estimate_value(estimate)
        inputs, input_warnings = build_inputs(current_price, normalized, forward_eps)
        warnings.extend(input_warnings)
        warnings.extend(_freshness_warnings(config, normalized, estimate))

        if inputs is None:
            result = TickerValuationResult(
                ticker=asset.ticker,
                status="skipped",
                current_price=current_price,
                base_target=None,
                target_low=None,
                target_high=None,
                valuation_gap=None,
                valuation_score=None,
                valuation_confidence=None,
                method_count=0,
                warnings=tuple(dict.fromkeys(warnings)),
            )
            _record_quality(config, result)
            results.append(result)
            continue

        method_targets, method_warnings = _method_targets(
            config, asset, all_assets, inputs, fundamentals
        )
        warnings.extend(method_warnings)
        target = _combine_targets(
            config,
            asset.ticker,
            inputs.current_price,
            method_targets,
            warnings,
        )
        if target is None:
            from .foreign_equity_sources import latest_foreign_equity_analyst_targets

            analyst_targets = latest_foreign_equity_analyst_targets(config, asset.ticker)
            if analyst_targets:
                warnings.extend(
                    (
                        "source_backed_analyst_target_only",
                        "loss_making_foreign_equity_valuation",
                    )
                )
                target = _foreign_analyst_target_fallback(
                    config,
                    asset.ticker,
                    inputs.current_price,
                    analyst_targets[0],
                    warnings,
                )
        if target is None:
            warnings.append("insufficient_valuation_methods")
            result = TickerValuationResult(
                ticker=asset.ticker,
                status="skipped",
                current_price=current_price,
                base_target=None,
                target_low=None,
                target_high=None,
                valuation_gap=None,
                valuation_score=None,
                valuation_confidence=None,
                method_count=len(method_targets),
                warnings=tuple(dict.fromkeys(warnings)),
            )
            _record_quality(config, result)
            results.append(result)
            continue

        if target.data_warnings != (", ".join(dict.fromkeys(warnings)) if warnings else None):
            target = Target(
                ticker=target.ticker,
                target_date=target.target_date,
                base_target=target.base_target,
                target_low=target.target_low,
                target_high=target.target_high,
                valuation_gap=target.valuation_gap,
                target_method=target.target_method,
                uncertainty_band=target.uncertainty_band,
                valuation_score=target.valuation_score,
                valuation_confidence=target.valuation_confidence,
                method_count=target.method_count,
                target_reason=target.target_reason,
                data_warnings=", ".join(dict.fromkeys(warnings)) if warnings else None,
                model_version=target.model_version,
                source=target.source,
                as_of_date=target.as_of_date,
                effective_date=target.effective_date,
            )
        upsert_target(config.database_path, target)
        result = TickerValuationResult(
            ticker=asset.ticker,
            status="computed",
            current_price=current_price,
            base_target=target.base_target,
            target_low=target.target_low,
            target_high=target.target_high,
            valuation_gap=target.valuation_gap,
            valuation_score=target.valuation_score,
            valuation_confidence=target.valuation_confidence,
            method_count=target.method_count or 0,
            warnings=tuple(dict.fromkeys(warnings)),
        )
        _record_quality(config, result)
        results.append(result)

    return ValuationUpdateResult(results=tuple(results))
