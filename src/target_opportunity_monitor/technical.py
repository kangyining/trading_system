from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from .config import AppConfig
from .storage import (
    Price,
    RegimeSignalSnapshot,
    Signal,
    TechnicalSignalSnapshot,
    list_assets,
    list_prices,
    normalize_ticker,
    regime_signal_statuses,
    technical_signal_statuses,
    upsert_regime_signal_snapshot,
    upsert_signal,
    upsert_technical_signal_snapshot,
)


@dataclass(frozen=True)
class TechnicalSignalResult:
    ticker: str
    signal_date: str
    trend_state: str | None
    price_location_state: str | None
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class TechnicalSignalRunResult:
    results: tuple[TechnicalSignalResult, ...]

    @property
    def computed_count(self) -> int:
        return len(self.results)

    @property
    def warning_count(self) -> int:
        return sum(1 for result in self.results if result.warnings)


@dataclass(frozen=True)
class RegimeSignalResult:
    ticker: str
    signal_date: str
    proxy_type: str
    trend_state: str | None
    risk_state: str | None
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class RegimeSignalRunResult:
    results: tuple[RegimeSignalResult, ...]

    @property
    def computed_count(self) -> int:
        return len(self.results)

    @property
    def warning_count(self) -> int:
        return sum(1 for result in self.results if result.warnings)


def _price_value(price: Price) -> float | None:
    value = price.adjusted_close if price.adjusted_close is not None else price.close
    return value if value is not None and value > 0 else None


def _high_value(price: Price) -> float | None:
    value = price.high if price.high is not None else price.close
    return value if value is not None and value > 0 else _price_value(price)


def _low_value(price: Price) -> float | None:
    value = price.low if price.low is not None else price.close
    return value if value is not None and value > 0 else _price_value(price)


def _valid_prices(prices: list[Price]) -> list[Price]:
    return [price for price in prices if _price_value(price) is not None]


def _mean(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


def _moving_average(values: list[float], days: int) -> float | None:
    if days <= 0 or len(values) < days:
        return None
    return _mean(values[-days:])


def _round(value: float | None) -> float | None:
    return round(value, 4) if value is not None else None


def _direction_from_score(score: float | None) -> str:
    if score is None:
        return "neutral"
    if score >= 60:
        return "positive"
    if score <= 40:
        return "negative"
    return "neutral"


def _return_over(values: list[float], lookback_days: int) -> float | None:
    if lookback_days <= 0 or len(values) <= lookback_days:
        return None
    start = values[-lookback_days - 1]
    end = values[-1]
    if start == 0:
        return None
    return end / start - 1


def _pivot_lows(prices: list[Price], window: int) -> list[float]:
    lows = [_low_value(price) for price in prices]
    pivots: list[float] = []
    if window <= 0 or len(lows) < window * 2 + 1:
        return pivots
    for index in range(window, len(lows) - window):
        current = lows[index]
        if current is None:
            continue
        peers = [value for value in lows[index - window : index + window + 1] if value is not None]
        if peers and current <= min(peers):
            pivots.append(current)
    return pivots


def _pivot_highs(prices: list[Price], window: int) -> list[float]:
    highs = [_high_value(price) for price in prices]
    pivots: list[float] = []
    if window <= 0 or len(highs) < window * 2 + 1:
        return pivots
    for index in range(window, len(highs) - window):
        current = highs[index]
        if current is None:
            continue
        peers = [value for value in highs[index - window : index + window + 1] if value is not None]
        if peers and current >= max(peers):
            pivots.append(current)
    return pivots


def _zone(level: float | None, near_pct: float) -> tuple[float | None, float | None]:
    if level is None:
        return None, None
    half_width = max(near_pct, 0.0) / 2
    return _round(level * (1 - half_width)), _round(level * (1 + half_width))


def _moving_average_state(
    current_price: float | None,
    short_ma: float | None,
    medium_ma: float | None,
    long_ma: float | None,
) -> str:
    if None in (current_price, short_ma, medium_ma, long_ma):
        return "insufficient_history"
    if current_price >= short_ma >= medium_ma >= long_ma:
        return "bullish"
    if current_price <= short_ma <= medium_ma <= long_ma:
        return "bearish"
    return "mixed"


def _drawdown_state(drawdown_pct: float | None) -> str:
    if drawdown_pct is None:
        return "unknown"
    if drawdown_pct <= -0.20:
        return "deep_drawdown"
    if drawdown_pct <= -0.10:
        return "correction"
    if drawdown_pct <= -0.05:
        return "pullback"
    return "near_high"


def _price_location_state(
    current_price: float | None,
    support_low: float | None,
    support_high: float | None,
    resistance_low: float | None,
    resistance_high: float | None,
    breakout_buffer_pct: float,
) -> str:
    if current_price is None:
        return "missing_price"
    if support_low is not None and current_price < support_low:
        return "support_failed"
    if support_high is not None and current_price <= support_high:
        return "near_support"
    if (
        resistance_high is not None
        and current_price >= resistance_high * (1 + breakout_buffer_pct)
    ):
        return "resistance_breakout"
    if resistance_low is not None and current_price >= resistance_low:
        return "near_resistance"
    return "between_levels"


def _trend_score(state: str) -> float:
    return {
        "bullish": 75.0,
        "mixed": 50.0,
        "bearish": 25.0,
        "insufficient_history": 50.0,
    }.get(state, 50.0)


def _level_score(state: str) -> float:
    return {
        "near_support": 65.0,
        "resistance_breakout": 70.0,
        "between_levels": 50.0,
        "near_resistance": 40.0,
        "support_failed": 25.0,
        "missing_price": 50.0,
    }.get(state, 50.0)


def _confidence(history_count: int, minimum_history: int, has_support: bool, has_resistance: bool) -> float:
    if minimum_history <= 0:
        base = 100.0
    else:
        base = min(1.0, history_count / minimum_history) * 70.0
    if has_support:
        base += 15.0
    if has_resistance:
        base += 15.0
    return round(min(100.0, base), 2)


def _technical_snapshot_for_ticker(
    config: AppConfig,
    ticker: str,
    signal_date: str,
) -> TechnicalSignalSnapshot:
    all_prices = _valid_prices(list_prices(config.database_path, ticker))
    prices = all_prices[-config.technical_lookback_days :]
    warnings: list[str] = []
    if len(prices) < config.technical_minimum_history_days:
        warnings.append("insufficient_price_history")

    closes = [_price_value(price) for price in prices]
    close_values = [value for value in closes if value is not None]
    current_price = close_values[-1] if close_values else None
    current_highs = [value for value in (_high_value(price) for price in prices) if value is not None]
    if current_price is None:
        warnings.append("missing_current_price")

    short_ma = _moving_average(close_values, config.technical_short_ma_days)
    medium_ma = _moving_average(close_values, config.technical_medium_ma_days)
    long_ma = _moving_average(close_values, config.technical_long_ma_days)
    if long_ma is None:
        warnings.append("missing_long_ma")

    lows = _pivot_lows(prices, config.technical_pivot_window_days)
    highs = _pivot_highs(prices, config.technical_pivot_window_days)
    support_candidates = [
        value for value in lows if current_price is not None and value <= current_price
    ]
    resistance_candidates = [
        value for value in highs if current_price is not None and value >= current_price
    ]
    if prices:
        recent_lows = [value for value in (_low_value(price) for price in prices[-63:]) if value is not None]
        recent_highs = [value for value in (_high_value(price) for price in prices[-63:]) if value is not None]
        if recent_lows:
            support_candidates.append(min(recent_lows))
        if recent_highs:
            resistance_candidates.append(max(recent_highs))

    support_level = max(support_candidates) if support_candidates else None
    resistance_level = min(resistance_candidates) if resistance_candidates else None
    if support_level is None:
        warnings.append("no_pivot_support")
    if resistance_level is None:
        warnings.append("no_pivot_resistance")

    support_low, support_high = _zone(support_level, config.technical_near_level_pct)
    resistance_low, resistance_high = _zone(
        resistance_level,
        config.technical_near_level_pct,
    )
    breakout_level = (
        _round(resistance_high * (1 + config.technical_breakout_buffer_pct))
        if resistance_high is not None
        else None
    )
    downside_watch_level = support_low
    trend_repair_level = _round(long_ma if long_ma is not None else medium_ma)
    ma_state = _moving_average_state(current_price, short_ma, medium_ma, long_ma)
    drawdown_pct = (
        current_price / max(current_highs) - 1
        if current_price is not None and current_highs
        else None
    )
    drawdown_state = _drawdown_state(drawdown_pct)
    location_state = _price_location_state(
        current_price,
        support_low,
        support_high,
        resistance_low,
        resistance_high,
        config.technical_breakout_buffer_pct,
    )
    trend_score = _trend_score(ma_state)
    level_score = _level_score(location_state)
    confidence = _confidence(
        len(prices),
        config.technical_minimum_history_days,
        support_level is not None,
        resistance_level is not None,
    )

    return TechnicalSignalSnapshot(
        ticker=ticker,
        signal_date=signal_date,
        current_price=_round(current_price),
        support_low=support_low,
        support_high=support_high,
        resistance_low=resistance_low,
        resistance_high=resistance_high,
        breakout_level=breakout_level,
        downside_watch_level=downside_watch_level,
        trend_repair_level=trend_repair_level,
        short_ma=_round(short_ma),
        medium_ma=_round(medium_ma),
        long_ma=_round(long_ma),
        moving_average_state=ma_state,
        drawdown_pct=_round(drawdown_pct),
        drawdown_state=drawdown_state,
        price_location_state=location_state,
        trend_score=trend_score,
        level_score=level_score,
        confidence=confidence,
        data_warnings=", ".join(dict.fromkeys(warnings)) if warnings else None,
        model_version=config.technical_model_version,
        source="technical",
        as_of_date=signal_date,
        effective_date=signal_date,
    )


def _store_technical_signals(config: AppConfig, snapshot: TechnicalSignalSnapshot) -> None:
    warnings = snapshot.data_warnings
    upsert_signal(
        config.database_path,
        Signal(
            ticker=snapshot.ticker,
            signal_date=snapshot.signal_date,
            signal_name="technical.trend",
            signal_family="technical",
            value=snapshot.trend_score,
            score=snapshot.trend_score,
            direction=_direction_from_score(snapshot.trend_score),
            reason_code=snapshot.moving_average_state,
            source="technical",
            model_version=config.technical_model_version,
            confidence=snapshot.confidence,
            data_warnings=warnings,
            as_of_date=snapshot.signal_date,
            effective_date=snapshot.signal_date,
        ),
    )
    upsert_signal(
        config.database_path,
        Signal(
            ticker=snapshot.ticker,
            signal_date=snapshot.signal_date,
            signal_name="technical.levels",
            signal_family="technical",
            value=snapshot.current_price,
            score=snapshot.level_score,
            direction=_direction_from_score(snapshot.level_score),
            reason_code=snapshot.price_location_state,
            source="technical",
            model_version=config.technical_model_version,
            confidence=snapshot.confidence,
            data_warnings=warnings,
            as_of_date=snapshot.signal_date,
            effective_date=snapshot.signal_date,
        ),
    )


def compute_technical_signals(
    config: AppConfig,
    ticker: str | None = None,
) -> TechnicalSignalRunResult:
    wanted = normalize_ticker(ticker) if ticker else None
    assets = [
        asset
        for asset in list_assets(config.database_path)
        if asset.active_flag == 1 and (wanted is None or asset.ticker == wanted)
    ]
    signal_date = date.today().isoformat()
    results: list[TechnicalSignalResult] = []
    for asset in assets:
        snapshot = _technical_snapshot_for_ticker(config, asset.ticker, signal_date)
        upsert_technical_signal_snapshot(config.database_path, snapshot)
        _store_technical_signals(config, snapshot)
        warnings = tuple(
            part.strip()
            for part in (snapshot.data_warnings or "").split(",")
            if part.strip()
        )
        results.append(
            TechnicalSignalResult(
                ticker=asset.ticker,
                signal_date=signal_date,
                trend_state=snapshot.moving_average_state,
                price_location_state=snapshot.price_location_state,
                warnings=warnings,
            )
        )
    return TechnicalSignalRunResult(results=tuple(results))


def _trend_state_for_prices(values: list[float]) -> str:
    short_ma = _moving_average(values, 20)
    medium_ma = _moving_average(values, 50)
    long_ma = _moving_average(values, 200)
    current = values[-1] if values else None
    return _moving_average_state(current, short_ma, medium_ma, long_ma)


def _benchmark_risk_state(spy_state: str | None, qqq_state: str | None, spy_return: float | None, qqq_return: float | None) -> str:
    if spy_state == "bullish" and qqq_state == "bullish" and (spy_return or 0) > 0 and (qqq_return or 0) > 0:
        return "risk_on"
    if spy_state == "bearish" or ((spy_return or 0) < -0.05 and (qqq_return or 0) < 0):
        return "risk_off"
    return "neutral"


def _regime_inputs(config: AppConfig, ticker: str) -> tuple[list[Price], list[float]]:
    prices = _valid_prices(list_prices(config.database_path, ticker))
    prices = prices[-max(config.technical_lookback_days, config.regime_relative_strength_lookback_days + 1) :]
    values = [_price_value(price) for price in prices]
    return prices, [value for value in values if value is not None]


def _store_regime_signal(config: AppConfig, snapshot: RegimeSignalSnapshot) -> None:
    signal_name = (
        "regime.market"
        if snapshot.proxy_type == "benchmark"
        else "regime.sector_rotation"
    )
    score = 50.0
    if snapshot.risk_state == "risk_on":
        score = 70.0
    elif snapshot.risk_state == "risk_off":
        score = 30.0
    elif snapshot.relative_strength is not None:
        score = 60.0 if snapshot.relative_strength > 0 else 40.0
    upsert_signal(
        config.database_path,
        Signal(
            ticker=snapshot.ticker,
            signal_date=snapshot.signal_date,
            signal_name=signal_name,
            signal_family="regime",
            value=snapshot.relative_strength,
            score=score,
            direction=_direction_from_score(score),
            reason_code=snapshot.risk_state or snapshot.trend_state,
            source="regime",
            model_version=config.regime_model_version,
            confidence=snapshot.confidence,
            data_warnings=snapshot.data_warnings,
            as_of_date=snapshot.signal_date,
            effective_date=snapshot.signal_date,
        ),
    )


def compute_regime_signals(config: AppConfig) -> RegimeSignalRunResult:
    signal_date = date.today().isoformat()
    benchmarks = tuple(dict.fromkeys(normalize_ticker(t) for t in config.regime_benchmark_tickers))
    sectors = tuple(dict.fromkeys(normalize_ticker(t) for t in config.regime_sector_proxy_tickers))
    all_tickers = tuple(dict.fromkeys(benchmarks + sectors))
    benchmark = benchmarks[0] if benchmarks else "SPY"
    _, benchmark_values = _regime_inputs(config, benchmark)
    benchmark_return = _return_over(
        benchmark_values,
        config.regime_relative_strength_lookback_days,
    )
    qqq_return: float | None = None
    benchmark_states: dict[str, str] = {}
    returns: dict[str, float | None] = {}
    values_by_ticker: dict[str, list[float]] = {}
    warnings_by_ticker: dict[str, list[str]] = {}

    for ticker in all_tickers:
        _, values = _regime_inputs(config, ticker)
        values_by_ticker[ticker] = values
        ticker_warnings: list[str] = []
        if not values:
            ticker_warnings.append(
                "missing_sector_proxy_price_history"
                if ticker in sectors
                else "missing_benchmark_price_history"
            )
        elif len(values) <= config.regime_relative_strength_lookback_days:
            ticker_warnings.append("insufficient_regime_price_history")
        returns[ticker] = _return_over(values, config.regime_relative_strength_lookback_days)
        benchmark_states[ticker] = _trend_state_for_prices(values) if values else "missing"
        warnings_by_ticker[ticker] = ticker_warnings
        if ticker == "QQQ":
            qqq_return = returns[ticker]

    risk_state = _benchmark_risk_state(
        benchmark_states.get(benchmark),
        benchmark_states.get("QQQ"),
        benchmark_return,
        qqq_return,
    )
    sector_returns = {
        ticker: value for ticker, value in returns.items() if ticker in sectors and value is not None
    }
    sector_ranks = {
        ticker: rank
        for rank, ticker in enumerate(
            sorted(sector_returns, key=lambda item: sector_returns[item], reverse=True),
            start=1,
        )
    }
    defensive = {"XLV", "XLP", "XLU"}
    results: list[RegimeSignalResult] = []

    for ticker in all_tickers:
        values = values_by_ticker[ticker]
        ticker_return = returns[ticker]
        relative_strength = (
            ticker_return - benchmark_return
            if ticker_return is not None and benchmark_return is not None
            else None
        )
        proxy_type = "benchmark" if ticker in benchmarks else "sector"
        warnings = warnings_by_ticker[ticker]
        if ticker in sectors and benchmark_return is None:
            warnings.append("missing_benchmark_return")
        confidence = 80.0 if not warnings else 40.0
        snapshot = RegimeSignalSnapshot(
            ticker=ticker,
            signal_date=signal_date,
            proxy_type=proxy_type,
            current_price=_round(values[-1]) if values else None,
            benchmark_ticker=benchmark,
            benchmark_return=_round(benchmark_return),
            return_lookback=_round(ticker_return),
            relative_strength=_round(relative_strength),
            trend_state=benchmark_states.get(ticker),
            risk_state=risk_state,
            sector_rotation_rank=sector_ranks.get(ticker),
            defensive_rotation_flag=(
                1 if ticker in defensive and relative_strength is not None and relative_strength > 0 else 0
            ),
            confidence=confidence,
            data_warnings=", ".join(dict.fromkeys(warnings)) if warnings else None,
            model_version=config.regime_model_version,
            source="regime",
            as_of_date=signal_date,
            effective_date=signal_date,
        )
        upsert_regime_signal_snapshot(config.database_path, snapshot)
        _store_regime_signal(config, snapshot)
        results.append(
            RegimeSignalResult(
                ticker=ticker,
                signal_date=signal_date,
                proxy_type=proxy_type,
                trend_state=snapshot.trend_state,
                risk_state=snapshot.risk_state,
                warnings=tuple(dict.fromkeys(warnings)),
            )
        )

    return RegimeSignalRunResult(results=tuple(results))


def build_technical_status_text(config: AppConfig, ticker: str | None = None) -> str:
    statuses = technical_signal_statuses(config.database_path, ticker=ticker)
    lines = [
        "Ticker | Date | Price | Support | Resistance | MA State | Location | Confidence | Warnings"
    ]
    for status in statuses:
        support = f"{_round(status.support_low)}/{_round(status.support_high)}"
        resistance = f"{_round(status.resistance_low)}/{_round(status.resistance_high)}"
        lines.append(
            " | ".join(
                (
                    status.ticker,
                    status.signal_date or "none",
                    str(_round(status.current_price) or ""),
                    support,
                    resistance,
                    status.moving_average_state or "",
                    status.price_location_state or "",
                    str(_round(status.confidence) or ""),
                    status.data_warnings or "",
                )
            )
        )
    return "\n".join(lines)


def build_regime_status_text(config: AppConfig, ticker: str | None = None) -> str:
    statuses = regime_signal_statuses(config.database_path, ticker=ticker)
    lines = [
        "Ticker | Date | Type | Trend | Risk | Return | Relative Strength | Rank | Confidence | Warnings"
    ]
    for status in statuses:
        lines.append(
            " | ".join(
                (
                    status.ticker,
                    status.signal_date or "none",
                    status.proxy_type or "",
                    status.trend_state or "",
                    status.risk_state or "",
                    str(_round(status.return_lookback) or ""),
                    str(_round(status.relative_strength) or ""),
                    str(status.sector_rotation_rank or ""),
                    str(_round(status.confidence) or ""),
                    status.data_warnings or "",
                )
            )
        )
    return "\n".join(lines)
