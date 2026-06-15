from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
import inspect
from io import StringIO
import json
import math
from pathlib import Path
from urllib.error import URLError
from urllib.request import Request, urlopen

from .config import AppConfig
from .storage import (
    Asset,
    Price,
    PriceFeature,
    insert_data_quality_check,
    list_assets,
    list_prices,
    normalize_ticker,
    upsert_price_feature,
    upsert_prices,
)


TRADING_DAY_LAGS = {
    "return_1d": 1,
    "return_1m": 21,
    "return_3m": 63,
    "return_6m": 126,
    "return_12m": 252,
}

PROVIDER_SYMBOL_ALIAS_HEADERS = (
    "ticker",
    "provider",
    "symbol",
    "source",
    "source_url",
    "as_of_date",
    "effective_date",
    "notes",
)


@dataclass(frozen=True)
class TickerUpdateResult:
    ticker: str
    status: str
    source: str | None
    rows_loaded: int
    feature_available: bool
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class MarketDataUpdateResult:
    results: tuple[TickerUpdateResult, ...]

    @property
    def loaded_count(self) -> int:
        return sum(1 for result in self.results if result.rows_loaded > 0)

    @property
    def failed_count(self) -> int:
        return sum(1 for result in self.results if result.status == "error")


def stooq_symbol(ticker: str, country: str | None = "US") -> str:
    normalized = normalize_ticker(ticker)
    if (country or "US").upper() == "US":
        if normalized.endswith(".US"):
            return normalized.lower()
        return f"{normalized.lower()}.us"
    return normalized.lower()


def yahoo_symbol(ticker: str) -> str:
    return normalize_ticker(ticker).replace(".", "-")


def _resolve_project_path(config: AppConfig, path: Path) -> Path:
    return path if path.is_absolute() else config.project_root / path


def ensure_provider_symbol_alias_csv(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        with path.open("w", encoding="utf-8", newline="") as output:
            csv.writer(output).writerow(PROVIDER_SYMBOL_ALIAS_HEADERS)
    return path


def _read_provider_symbol_alias_rows(config: AppConfig) -> tuple[dict[str, str], ...]:
    path = ensure_provider_symbol_alias_csv(
        _resolve_project_path(config, config.market_data_symbol_aliases_path)
    )
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return tuple(dict(row) for row in csv.DictReader(handle))


def _provider_alias_keys(provider: str) -> set[str]:
    normalized = provider.strip().lower()
    keys = {normalized}
    if normalized in {"yahoo", "yahoo_chart", "yahoo_finance"}:
        keys.update({"yahoo", "yahoo_chart", "yahoo_finance"})
    if normalized in {"stooq", "stooq_csv"}:
        keys.update({"stooq", "stooq_csv"})
    return keys


def provider_symbol_alias(config: AppConfig | None, ticker: str, provider: str) -> str | None:
    if config is None:
        return None
    normalized_ticker = normalize_ticker(ticker)
    providers = _provider_alias_keys(provider)
    for row in _read_provider_symbol_alias_rows(config):
        row_ticker = normalize_ticker(row.get("ticker", ""))
        row_provider = (row.get("provider") or "").strip().lower()
        symbol = (row.get("symbol") or "").strip()
        source_url = (row.get("source_url") or "").strip()
        if row_ticker != normalized_ticker or row_provider not in providers:
            continue
        if not symbol or not source_url.lower().startswith(("http://", "https://")):
            continue
        return symbol
    return None


def stooq_url(symbol: str, lookback_days: int | None = None) -> str:
    base = f"https://stooq.com/q/d/l/?s={symbol}&i=d"
    if lookback_days is None:
        return base
    end = date.today()
    start = end - timedelta(days=lookback_days)
    return f"{base}&d1={start:%Y%m%d}&d2={end:%Y%m%d}"


def _float_or_none(value: str | None) -> float | None:
    if value is None:
        return None
    cleaned = value.strip()
    if not cleaned:
        return None
    return float(cleaned.replace(",", ""))


def _row_value(row: dict[str, str], *names: str) -> str | None:
    lowered = {key.lower().strip(): value for key, value in row.items() if key}
    for name in names:
        if name.lower() in lowered:
            return lowered[name.lower()]
    return None


def parse_price_csv(text: str, ticker: str, source: str) -> list[Price]:
    if "<html" in text[:200].lower() or "requires javascript" in text[:500].lower():
        raise ValueError("Price CSV response was HTML, not CSV data.")

    reader = csv.DictReader(StringIO(text))
    if reader.fieldnames is None:
        raise ValueError("Price CSV is missing a header row.")

    fieldnames = {field.lower().strip() for field in reader.fieldnames if field}
    required = {"date", "open", "high", "low", "close", "volume"}
    missing = required - fieldnames
    if missing:
        raise ValueError(f"Price CSV missing required columns: {', '.join(sorted(missing))}")

    prices: list[Price] = []
    for row in reader:
        price_date = _row_value(row, "date")
        if not price_date:
            continue

        close = _float_or_none(_row_value(row, "close"))
        adjusted_close = _float_or_none(
            _row_value(row, "adjusted_close", "adj close", "adj_close")
        )
        if adjusted_close is None:
            adjusted_close = close

        prices.append(
            Price(
                ticker=ticker,
                price_date=price_date.strip(),
                open=_float_or_none(_row_value(row, "open")),
                high=_float_or_none(_row_value(row, "high")),
                low=_float_or_none(_row_value(row, "low")),
                close=close,
                adjusted_close=adjusted_close,
                volume=_float_or_none(_row_value(row, "volume")),
                source=source,
                as_of_date=date.today().isoformat(),
                effective_date=price_date.strip(),
            )
        )

    if not prices:
        raise ValueError("Price CSV contained no price rows.")
    return prices


def fetch_stooq_prices(
    asset: Asset,
    lookback_days: int,
    *,
    config: AppConfig | None = None,
) -> list[Price]:
    symbol = provider_symbol_alias(config, asset.ticker, "stooq") or stooq_symbol(
        asset.ticker,
        asset.country,
    )
    request = Request(
        stooq_url(symbol, lookback_days),
        headers={"User-Agent": "Mozilla/5.0"},
    )
    try:
        with urlopen(request, timeout=30) as response:
            text = response.read().decode("utf-8", errors="replace")
    except URLError as error:
        raise ValueError(f"Stooq request failed for {asset.ticker}: {error}") from error
    return parse_price_csv(text, asset.ticker, "stooq")


def yahoo_chart_url(
    ticker: str,
    lookback_days: int,
    *,
    provider_symbol: bool = False,
) -> str:
    end = date.today()
    start = end - timedelta(days=lookback_days)
    period1 = int(datetime.combine(start, time.min).timestamp())
    period2 = int(datetime.combine(end + timedelta(days=1), time.min).timestamp())
    symbol = ticker if provider_symbol else yahoo_symbol(ticker)
    return (
        f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
        f"?period1={period1}&period2={period2}&interval=1d&events=history"
    )


def parse_yahoo_chart_json(text: str, ticker: str) -> list[Price]:
    payload = json.loads(text)
    chart = payload.get("chart", {})
    error = chart.get("error")
    if error:
        raise ValueError(f"Yahoo chart error for {ticker}: {error}")

    results = chart.get("result") or []
    if not results:
        raise ValueError(f"Yahoo chart returned no results for {ticker}.")

    result = results[0]
    timestamps = result.get("timestamp") or []
    indicators = result.get("indicators", {})
    quote = (indicators.get("quote") or [{}])[0]
    adjclose = (indicators.get("adjclose") or [{}])[0].get("adjclose") or []

    prices: list[Price] = []
    for index, timestamp in enumerate(timestamps):
        price_date = date.fromtimestamp(timestamp).isoformat()
        close = _indexed_value(quote.get("close"), index)
        adjusted_close = _indexed_value(adjclose, index)
        if adjusted_close is None:
            adjusted_close = close
        if close is None:
            continue

        prices.append(
            Price(
                ticker=ticker,
                price_date=price_date,
                open=_indexed_value(quote.get("open"), index),
                high=_indexed_value(quote.get("high"), index),
                low=_indexed_value(quote.get("low"), index),
                close=close,
                adjusted_close=adjusted_close,
                volume=_indexed_value(quote.get("volume"), index),
                source="yahoo_chart",
                as_of_date=date.today().isoformat(),
                effective_date=price_date,
            )
        )

    if not prices:
        raise ValueError(f"Yahoo chart returned no usable price rows for {ticker}.")
    return prices


def _indexed_value(values: list[float | int | None] | None, index: int) -> float | None:
    if values is None or index >= len(values):
        return None
    value = values[index]
    return float(value) if value is not None else None


def fetch_yahoo_chart_prices(
    asset: Asset,
    lookback_days: int,
    *,
    config: AppConfig | None = None,
) -> list[Price]:
    alias = provider_symbol_alias(config, asset.ticker, "yahoo_chart")
    symbol = alias or asset.ticker
    request = Request(
        yahoo_chart_url(symbol, lookback_days, provider_symbol=alias is not None),
        headers={"User-Agent": "Mozilla/5.0"},
    )
    try:
        with urlopen(request, timeout=30) as response:
            text = response.read().decode("utf-8", errors="replace")
    except URLError as error:
        raise ValueError(f"Yahoo chart request failed for {asset.ticker}: {error}") from error
    return parse_yahoo_chart_json(text, asset.ticker)


def _call_price_fetcher(
    fetcher,
    config: AppConfig,
    asset: Asset,
    lookback_days: int,
) -> list[Price]:
    try:
        parameters = inspect.signature(fetcher).parameters
    except (TypeError, ValueError):
        parameters = {}
    if "config" in parameters:
        return fetcher(asset, lookback_days, config=config)
    return fetcher(asset, lookback_days)


def manual_price_csv_path(manual_prices_dir: Path, ticker: str) -> Path:
    return manual_prices_dir / f"{normalize_ticker(ticker)}.csv"


def load_manual_prices(asset: Asset, manual_prices_dir: Path) -> list[Price]:
    path = manual_price_csv_path(manual_prices_dir, asset.ticker)
    if not path.exists():
        raise ValueError(f"Manual price CSV not found: {path}")
    return parse_price_csv(path.read_text(encoding="utf-8-sig"), asset.ticker, "manual_csv")


def _dedupe_prices_by_date(prices: list[Price]) -> list[Price]:
    by_date: dict[str, Price] = {}
    for price in prices:
        by_date[price.price_date] = price
    return [by_date[key] for key in sorted(by_date)]


def _return_for_lag(prices: list[Price], lag: int) -> float | None:
    if len(prices) <= lag:
        return None
    latest = prices[-1].adjusted_close or prices[-1].close
    previous = prices[-1 - lag].adjusted_close or prices[-1 - lag].close
    if latest is None or previous in (None, 0):
        return None
    return latest / previous - 1


def _daily_returns(prices: list[Price]) -> list[float]:
    returns: list[float] = []
    for previous, current in zip(prices, prices[1:]):
        previous_close = previous.adjusted_close or previous.close
        current_close = current.adjusted_close or current.close
        if previous_close not in (None, 0) and current_close is not None:
            returns.append(current_close / previous_close - 1)
    return returns


def _annualized_volatility(daily_returns: list[float], window: int) -> float | None:
    if len(daily_returns) < window:
        return None
    sample = daily_returns[-window:]
    mean = sum(sample) / len(sample)
    variance = sum((value - mean) ** 2 for value in sample) / len(sample)
    return math.sqrt(variance) * math.sqrt(252)


def _average_dollar_volume(prices: list[Price], window: int) -> float | None:
    if len(prices) < window:
        return None
    values = []
    for price in prices[-window:]:
        if price.close is not None and price.volume is not None:
            values.append(price.close * price.volume)
    if not values:
        return None
    return sum(values) / len(values)


def compute_price_feature(ticker: str, prices: list[Price]) -> PriceFeature | None:
    deduped = _dedupe_prices_by_date(prices)
    if not deduped:
        return None

    returns = _daily_returns(deduped)
    latest = deduped[-1]
    current_price = latest.adjusted_close or latest.close

    return PriceFeature(
        ticker=ticker,
        feature_date=date.today().isoformat(),
        current_price=current_price,
        return_1d=_return_for_lag(deduped, TRADING_DAY_LAGS["return_1d"]),
        return_1m=_return_for_lag(deduped, TRADING_DAY_LAGS["return_1m"]),
        return_3m=_return_for_lag(deduped, TRADING_DAY_LAGS["return_3m"]),
        return_6m=_return_for_lag(deduped, TRADING_DAY_LAGS["return_6m"]),
        return_12m=_return_for_lag(deduped, TRADING_DAY_LAGS["return_12m"]),
        realized_volatility_20d=_annualized_volatility(returns, 20),
        realized_volatility_60d=_annualized_volatility(returns, 60),
        average_dollar_volume_20d=_average_dollar_volume(deduped, 20),
        latest_price_date=latest.price_date,
        source="computed",
        as_of_date=date.today().isoformat(),
        effective_date=latest.price_date,
    )


def _quality_warnings(
    ticker: str,
    prices: list[Price],
    stale_after_days: int,
    minimum_history_days: int,
) -> tuple[str, ...]:
    warnings: list[str] = []
    if not prices:
        return ("missing_prices",)

    deduped = _dedupe_prices_by_date(prices)
    if len(deduped) < minimum_history_days:
        warnings.append("insufficient_history")

    latest = deduped[-1].price_date
    try:
        latest_date = date.fromisoformat(latest)
        if (date.today() - latest_date).days > stale_after_days:
            warnings.append("stale_price")
    except ValueError:
        warnings.append("malformed_latest_price_date")

    return tuple(warnings)


def _record_quality_checks(
    config: AppConfig,
    ticker: str,
    warnings: tuple[str, ...],
    row_count: int,
    source: str | None,
) -> None:
    if not warnings:
        insert_data_quality_check(
            config.database_path,
            check_name=f"price_history:{ticker}",
            status="ok",
            details=f"{ticker}: loaded {row_count} rows from {source}",
            source="market_data",
            as_of_date=date.today().isoformat(),
        )
        return

    for warning in warnings:
        insert_data_quality_check(
            config.database_path,
            check_name=f"price_history:{ticker}:{warning}",
            status="warning",
            details=f"{ticker}: {warning}; rows={row_count}; source={source}",
            source="market_data",
            as_of_date=date.today().isoformat(),
        )


def _load_prices_for_asset(
    config: AppConfig,
    asset: Asset,
    source_mode: str,
    online_fetcher=fetch_stooq_prices,
    secondary_online_fetcher=fetch_yahoo_chart_prices,
) -> tuple[list[Price], str]:
    mode = source_mode.lower()
    if mode not in {"auto", "stooq", "yahoo", "csv", "ibkr"}:
        raise ValueError(f"Unsupported market data source mode: {source_mode}")

    if mode == "csv":
        return load_manual_prices(asset, config.manual_prices_dir), "manual_csv"

    if mode == "ibkr":
        from .ibkr_provider import fetch_ibkr_historical_prices

        return fetch_ibkr_historical_prices(config, asset), "ibkr_historical"

    if mode == "yahoo":
        return (
            _call_price_fetcher(
                secondary_online_fetcher,
                config,
                asset,
                config.market_data_lookback_days,
            ),
            "yahoo_chart",
        )

    if mode == "stooq":
        return (
            _call_price_fetcher(
                online_fetcher,
                config,
                asset,
                config.market_data_lookback_days,
            ),
            "stooq",
        )

    try:
        return (
            _call_price_fetcher(
                online_fetcher,
                config,
                asset,
                config.market_data_lookback_days,
            ),
            "stooq",
        )
    except ValueError:
        try:
            return (
                _call_price_fetcher(
                    secondary_online_fetcher,
                    config,
                    asset,
                    config.market_data_lookback_days,
                ),
                "yahoo_chart",
            )
        except ValueError:
            return load_manual_prices(asset, config.manual_prices_dir), "manual_csv"


def update_prices(
    config: AppConfig,
    ticker: str | None = None,
    source_mode: str | None = None,
    online_fetcher=fetch_stooq_prices,
    secondary_online_fetcher=fetch_yahoo_chart_prices,
) -> MarketDataUpdateResult:
    selected_source_mode = source_mode or config.market_data_mode
    active_assets = list_assets(config.database_path)
    if ticker:
        wanted = normalize_ticker(ticker)
        active_assets = [asset for asset in active_assets if asset.ticker == wanted]

    results: list[TickerUpdateResult] = []
    for asset in active_assets:
        loaded_source: str | None = None
        try:
            prices, loaded_source = _load_prices_for_asset(
                config,
                asset,
                selected_source_mode,
                online_fetcher,
                secondary_online_fetcher,
            )
            upsert_prices(config.database_path, prices)
            stored_prices = list_prices(config.database_path, asset.ticker)
            feature = compute_price_feature(asset.ticker, stored_prices)
            feature_available = feature is not None
            if feature is not None:
                upsert_price_feature(config.database_path, feature)
            warnings = _quality_warnings(
                asset.ticker,
                stored_prices,
                config.market_data_stale_after_days,
                config.market_data_minimum_history_days,
            )
            _record_quality_checks(
                config, asset.ticker, warnings, len(stored_prices), loaded_source
            )
            results.append(
                TickerUpdateResult(
                    ticker=asset.ticker,
                    status="loaded",
                    source=loaded_source,
                    rows_loaded=len(prices),
                    feature_available=feature_available,
                    warnings=warnings,
                )
            )
        except ValueError as error:
            warning = str(error)
            insert_data_quality_check(
                config.database_path,
                check_name=f"price_history:{asset.ticker}:load_error",
                status="error",
                details=warning,
                source="market_data",
                as_of_date=date.today().isoformat(),
            )
            results.append(
                TickerUpdateResult(
                    ticker=asset.ticker,
                    status="error",
                    source=loaded_source,
                    rows_loaded=0,
                    feature_available=False,
                    warnings=(warning,),
                )
            )

    return MarketDataUpdateResult(results=tuple(results))
