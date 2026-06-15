from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from .config import AppConfig
from .storage import (
    RefreshReadinessStatus,
    insert_data_quality_check,
    latest_etf_feature,
    latest_etf_nav,
    latest_fundamental,
    latest_price_feature,
    is_scoreable_asset,
    list_assets,
    list_estimates,
    list_etf_holdings,
    list_scores,
    list_targets,
    normalize_ticker,
)


@dataclass(frozen=True)
class ReadinessSummary:
    statuses: tuple[RefreshReadinessStatus, ...]

    @property
    def ready_count(self) -> int:
        return sum(1 for status in self.statuses if status.phase4_ready)

    @property
    def warning_count(self) -> int:
        return sum(1 for status in self.statuses if status.warnings)


def _asset_type(value: str | None) -> str:
    return (value or "equity").strip().lower()


def _latest_target_ready(config: AppConfig, ticker: str) -> bool:
    targets = list_targets(config.database_path, ticker)
    if not targets:
        return False
    latest = targets[-1]
    return latest.base_target is not None


def _latest_score_ready(config: AppConfig, ticker: str) -> bool:
    scores = list_scores(config.database_path, ticker)
    if not scores:
        return False
    latest = scores[-1]
    return latest.opportunity_score is not None


def _readiness_for_ticker(config: AppConfig, ticker: str) -> RefreshReadinessStatus:
    normalized = normalize_ticker(ticker)
    assets = [asset for asset in list_assets(config.database_path) if asset.ticker == normalized]
    if not assets:
        return RefreshReadinessStatus(
            ticker=normalized,
            asset_type="unknown",
            price_ready=False,
            feature_ready=False,
            fundamentals_ready=False,
            estimates_ready=False,
            etf_nav_ready=False,
            etf_holdings_ready=False,
            target_ready=False,
            score_ready=False,
            phase4_ready=False,
            warnings=("missing_asset",),
        )

    asset = assets[0]
    kind = _asset_type(asset.asset_type)
    price_feature = latest_price_feature(config.database_path, normalized)
    price_ready = price_feature is not None and price_feature.current_price is not None
    feature_ready = price_feature is not None
    target_ready = _latest_target_ready(config, normalized)
    score_ready = _latest_score_ready(config, normalized)

    fundamentals_ready = latest_fundamental(config.database_path, normalized) is not None
    estimates_ready = bool(list_estimates(config.database_path, normalized))
    etf_nav_ready = latest_etf_nav(config.database_path, normalized) is not None
    etf_feature = latest_etf_feature(config.database_path, normalized)
    latest_holdings = list_etf_holdings(
        config.database_path,
        normalized,
        etf_feature.latest_holdings_date if etf_feature else None,
    )
    etf_holdings_ready = len(latest_holdings) >= config.etf_minimum_holdings

    warnings: list[str] = []
    if not price_ready:
        warnings.append("missing_price")
    if not feature_ready:
        warnings.append("missing_price_feature")
    if not target_ready:
        warnings.append("missing_target")

    if kind == "etf":
        if not etf_nav_ready:
            warnings.append("missing_etf_nav")
        if etf_feature is None:
            warnings.append("missing_etf_feature")
        if not etf_holdings_ready:
            warnings.append("missing_or_insufficient_etf_holdings")
        phase4_ready = price_ready and feature_ready and etf_nav_ready and target_ready
    else:
        if not fundamentals_ready:
            warnings.append("missing_fundamentals")
        if not estimates_ready:
            warnings.append("missing_estimates")
        phase4_ready = (
            price_ready
            and feature_ready
            and fundamentals_ready
            and estimates_ready
            and target_ready
        )

    return RefreshReadinessStatus(
        ticker=normalized,
        asset_type=kind,
        price_ready=price_ready,
        feature_ready=feature_ready,
        fundamentals_ready=fundamentals_ready,
        estimates_ready=estimates_ready,
        etf_nav_ready=etf_nav_ready,
        etf_holdings_ready=etf_holdings_ready,
        target_ready=target_ready,
        score_ready=score_ready,
        phase4_ready=phase4_ready,
        warnings=tuple(warnings),
    )


def verify_ticker(config: AppConfig, ticker: str, intraday: bool = False) -> RefreshReadinessStatus:
    status = _readiness_for_ticker(config, ticker)
    source = "readiness_intraday" if intraday else "readiness"
    insert_data_quality_check(
        config.database_path,
        check_name=f"readiness:{status.ticker}",
        status="ok" if status.phase4_ready else "warning",
        details=", ".join(status.warnings) if status.warnings else "pre_alert_ready",
        source=source,
        as_of_date=date.today().isoformat(),
    )
    return status


def verify_universe(
    config: AppConfig,
    ticker: str | None = None,
    intraday: bool = False,
) -> ReadinessSummary:
    if ticker:
        statuses = (verify_ticker(config, ticker, intraday=intraday),)
        return ReadinessSummary(statuses=statuses)

    active_tickers = [
        asset.ticker
        for asset in list_assets(config.database_path)
        if is_scoreable_asset(asset)
    ]
    statuses = tuple(
        verify_ticker(config, active_ticker, intraday=intraday)
        for active_ticker in active_tickers
    )
    return ReadinessSummary(statuses=statuses)
