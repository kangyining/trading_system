from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime

from .config import AppConfig
from .storage import (
    IntradayGapSnapshot,
    is_scoreable_asset,
    latest_etf_nav,
    latest_price_feature,
    latest_quote_snapshot,
    list_assets,
    list_targets,
    normalize_ticker,
    upsert_intraday_gap_snapshot,
)


@dataclass(frozen=True)
class IntradayGapResult:
    ticker: str
    current_price: float | None
    gap_to_base: float | None
    etf_nav_gap: float | None
    source: str
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class IntradayGapUpdateResult:
    results: tuple[IntradayGapResult, ...]

    @property
    def updated_count(self) -> int:
        return sum(1 for result in self.results if result.current_price is not None)

    @property
    def warning_count(self) -> int:
        return sum(1 for result in self.results if result.warnings)


def _safe_gap(numerator: float | None, denominator: float | None) -> float | None:
    if numerator is None or denominator in (None, 0):
        return None
    return numerator / denominator - 1


def _current_price(config: AppConfig, ticker: str) -> tuple[float | None, str]:
    quote = latest_quote_snapshot(config.database_path, ticker)
    if quote is not None:
        for value in (quote.last, quote.mark, quote.close):
            if value is not None and value > 0:
                return value, quote.source

    feature = latest_price_feature(config.database_path, ticker)
    if feature is not None and feature.current_price is not None:
        return feature.current_price, feature.source
    return None, "none"


def compute_intraday_gaps(
    config: AppConfig,
    ticker: str | None = None,
) -> IntradayGapUpdateResult:
    wanted = normalize_ticker(ticker) if ticker else None
    assets = [
        asset
        for asset in list_assets(config.database_path)
        if is_scoreable_asset(asset) and (wanted is None or asset.ticker == wanted)
    ]
    timestamp = datetime.now().isoformat(timespec="seconds")
    results: list[IntradayGapResult] = []

    for asset in assets:
        current_price, price_source = _current_price(config, asset.ticker)
        targets = list_targets(config.database_path, asset.ticker)
        latest_target = targets[-1] if targets else None
        nav = latest_etf_nav(config.database_path, asset.ticker)
        warnings: list[str] = []
        if current_price is None:
            warnings.append("missing_current_price")
        if latest_target is None or latest_target.base_target is None:
            warnings.append("missing_target")

        snapshot = IntradayGapSnapshot(
            ticker=asset.ticker,
            snapshot_timestamp=timestamp,
            current_price=current_price,
            base_target=latest_target.base_target if latest_target else None,
            target_low=latest_target.target_low if latest_target else None,
            target_high=latest_target.target_high if latest_target else None,
            gap_to_base=_safe_gap(
                latest_target.base_target if latest_target else None,
                current_price,
            ),
            gap_to_low=_safe_gap(
                latest_target.target_low if latest_target else None,
                current_price,
            ),
            gap_to_high=_safe_gap(
                latest_target.target_high if latest_target else None,
                current_price,
            ),
            etf_nav_per_share=nav.nav_per_share if nav else None,
            etf_nav_gap=_safe_gap(nav.nav_per_share if nav else None, current_price),
            source="intraday_probe",
            as_of_date=date.today().isoformat(),
            effective_date=timestamp,
        )
        upsert_intraday_gap_snapshot(config.database_path, snapshot)
        results.append(
            IntradayGapResult(
                ticker=asset.ticker,
                current_price=current_price,
                gap_to_base=snapshot.gap_to_base,
                etf_nav_gap=snapshot.etf_nav_gap,
                source=price_source,
                warnings=tuple(warnings),
            )
        )

    return IntradayGapUpdateResult(results=tuple(results))
