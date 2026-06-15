from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import date
from io import StringIO
from pathlib import Path
from statistics import mean, pstdev

from .storage import (
    EtfFeature,
    EtfHolding,
    EtfNav,
    latest_etf_holdings,
    latest_price_feature,
    list_etf_navs,
    normalize_ticker,
    upsert_etf_feature,
    upsert_etf_holding,
    upsert_etf_nav,
)


ETF_NAV_REQUIRED_COLUMNS = {"ticker", "nav_date", "nav_per_share"}
ETF_HOLDING_REQUIRED_COLUMNS = {"ticker", "holdings_date", "weight"}

ETF_NAV_NUMERIC_FIELDS = {
    "nav_per_share",
    "market_price",
    "premium_discount",
    "shares_outstanding",
    "net_assets",
}
ETF_HOLDING_NUMERIC_FIELDS = {"weight", "shares", "market_value"}

ETF_NAV_HEADERS = (
    "ticker",
    "nav_date",
    "nav_per_share",
    "market_price",
    "premium_discount",
    "shares_outstanding",
    "net_assets",
    "source",
    "as_of_date",
    "effective_date",
)

ETF_HOLDING_HEADERS = (
    "ticker",
    "holdings_date",
    "holding_ticker",
    "holding_name",
    "holding_asset_type",
    "weight",
    "shares",
    "market_value",
    "sector",
    "country",
    "source",
    "as_of_date",
    "effective_date",
)


@dataclass(frozen=True)
class EtfCsvLoadResult:
    path: Path
    loaded_count: int
    tickers: tuple[str, ...]


def ensure_etf_csv_headers(navs_path: Path, holdings_path: Path) -> None:
    _ensure_header_file(navs_path, ETF_NAV_HEADERS)
    _ensure_header_file(holdings_path, ETF_HOLDING_HEADERS)


def _ensure_header_file(path: Path, headers: tuple[str, ...]) -> None:
    if path.exists():
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(",".join(headers) + "\n", encoding="utf-8")


def _lowered_fieldnames(fieldnames: list[str] | None) -> set[str]:
    return {field.strip().lower() for field in fieldnames or [] if field}


def _row_value(row: dict[str, str], name: str) -> str | None:
    for key, value in row.items():
        if key and key.strip().lower() == name:
            return value
    return None


def _text(row: dict[str, str], name: str, default: str | None = None) -> str | None:
    value = _row_value(row, name)
    if value is None or value.strip() == "":
        return default
    return value.strip()


def _required_text(row: dict[str, str], name: str, row_number: int) -> str:
    value = _text(row, name)
    if value is None:
        raise ValueError(f"Row {row_number}: missing required value for {name}.")
    return value


def _date(row: dict[str, str], name: str, row_number: int, required: bool) -> str | None:
    value = _text(row, name)
    if value is None:
        if required:
            raise ValueError(f"Row {row_number}: missing required date for {name}.")
        return None
    try:
        return date.fromisoformat(value).isoformat()
    except ValueError as error:
        raise ValueError(
            f"Row {row_number}: malformed date for {name}: {value}."
        ) from error


def _float(row: dict[str, str], name: str, row_number: int) -> float | None:
    value = _text(row, name)
    if value is None:
        return None
    try:
        return float(value.replace(",", "").rstrip("%"))
    except ValueError as error:
        raise ValueError(
            f"Row {row_number}: malformed numeric value for {name}: {value}."
        ) from error


def _validate_columns(
    reader: csv.DictReader,
    required_columns: set[str],
    file_label: str,
) -> None:
    fieldnames = _lowered_fieldnames(reader.fieldnames)
    missing = required_columns - fieldnames
    if missing:
        raise ValueError(
            f"{file_label} CSV missing required columns: {', '.join(sorted(missing))}"
        )


def _percent_or_decimal(value: float | None, name: str, row_number: int) -> float | None:
    if value is None:
        return None
    if value < -100:
        raise ValueError(f"Row {row_number}: invalid {name}: {value}.")
    if abs(value) > 1:
        value = value / 100
    return value


def _percent_or_decimal_cell(
    row: dict[str, str],
    name: str,
    row_number: int,
) -> float | None:
    raw = _text(row, name)
    value = _float(row, name, row_number)
    if value is None:
        return None
    if raw is not None and raw.endswith("%"):
        return value / 100
    return _percent_or_decimal(value, name, row_number)


def _weight(value: float | None, row_number: int) -> float:
    normalized = _percent_or_decimal(value, "weight", row_number)
    if normalized is None:
        raise ValueError(f"Row {row_number}: missing required value for weight.")
    if normalized < 0 or normalized > 1:
        raise ValueError(f"Row {row_number}: weight must be between 0 and 1.")
    return normalized


def parse_etf_navs_csv(text: str) -> list[EtfNav]:
    reader = csv.DictReader(StringIO(text))
    _validate_columns(reader, ETF_NAV_REQUIRED_COLUMNS, "ETF NAV")

    navs: list[EtfNav] = []
    for row in reader:
        if not any((value or "").strip() for value in row.values()):
            continue
        row_number = reader.line_num
        numeric_payload = {
            field: _float(row, field, row_number) for field in ETF_NAV_NUMERIC_FIELDS
        }
        nav_per_share = numeric_payload.pop("nav_per_share")
        if nav_per_share is None or nav_per_share <= 0:
            raise ValueError(f"Row {row_number}: nav_per_share must be positive.")
        numeric_payload.pop("premium_discount")
        premium_discount = _percent_or_decimal_cell(
            row, "premium_discount", row_number
        )
        navs.append(
            EtfNav(
                ticker=normalize_ticker(_required_text(row, "ticker", row_number)),
                nav_date=_date(row, "nav_date", row_number, required=True) or "",
                nav_per_share=nav_per_share,
                premium_discount=premium_discount,
                source=_text(row, "source", "manual_csv") or "manual_csv",
                as_of_date=_date(row, "as_of_date", row_number, required=False),
                effective_date=_date(row, "effective_date", row_number, required=False),
                **numeric_payload,
            )
        )
    return navs


def parse_etf_holdings_csv(text: str) -> list[EtfHolding]:
    reader = csv.DictReader(StringIO(text))
    _validate_columns(reader, ETF_HOLDING_REQUIRED_COLUMNS, "ETF holdings")

    holdings: list[EtfHolding] = []
    for row in reader:
        if not any((value or "").strip() for value in row.values()):
            continue
        row_number = reader.line_num
        holding_ticker = _text(row, "holding_ticker")
        holding_name = _text(row, "holding_name")
        if holding_ticker is None and holding_name is None:
            raise ValueError(
                f"Row {row_number}: holding_ticker or holding_name is required."
            )
        numeric_payload = {
            field: _float(row, field, row_number) for field in ETF_HOLDING_NUMERIC_FIELDS
        }
        holdings.append(
            EtfHolding(
                ticker=normalize_ticker(_required_text(row, "ticker", row_number)),
                holdings_date=_date(row, "holdings_date", row_number, required=True)
                or "",
                holding_ticker=normalize_ticker(holding_ticker) if holding_ticker else "",
                holding_name=holding_name or "",
                holding_asset_type=_text(row, "holding_asset_type"),
                weight=_weight(numeric_payload.pop("weight"), row_number),
                sector=_text(row, "sector"),
                country=_text(row, "country"),
                source=_text(row, "source", "manual_csv") or "manual_csv",
                as_of_date=_date(row, "as_of_date", row_number, required=False),
                effective_date=_date(row, "effective_date", row_number, required=False),
                **numeric_payload,
            )
        )
    return holdings


def load_etf_navs_csv(database_path: Path, path: Path) -> EtfCsvLoadResult:
    navs = parse_etf_navs_csv(path.read_text(encoding="utf-8-sig"))
    for nav in navs:
        upsert_etf_nav(database_path, nav)
    tickers = tuple(sorted({nav.ticker for nav in navs}))
    refresh_etf_features(database_path, tickers)
    return EtfCsvLoadResult(path=path, loaded_count=len(navs), tickers=tickers)


def load_etf_holdings_csv(database_path: Path, path: Path) -> EtfCsvLoadResult:
    holdings = parse_etf_holdings_csv(path.read_text(encoding="utf-8-sig"))
    for holding in holdings:
        upsert_etf_holding(database_path, holding)
    tickers = tuple(sorted({holding.ticker for holding in holdings}))
    refresh_etf_features(database_path, tickers)
    return EtfCsvLoadResult(path=path, loaded_count=len(holdings), tickers=tickers)


def _premium_discount(nav: EtfNav, fallback_market_price: float | None) -> float | None:
    if nav.premium_discount is not None:
        return nav.premium_discount
    market_price = nav.market_price if nav.market_price is not None else fallback_market_price
    if market_price is None or nav.nav_per_share <= 0:
        return None
    return market_price / nav.nav_per_share - 1


def _holding_type(holding: EtfHolding) -> str:
    return (holding.holding_asset_type or "").strip().lower().replace("-", "_")


def compute_etf_feature(
    ticker: str,
    navs: list[EtfNav],
    holdings: list[EtfHolding],
    current_price: float | None,
    history_days: int,
) -> EtfFeature | None:
    if not navs:
        return None

    ordered_navs = sorted(navs, key=lambda item: item.nav_date)
    latest_nav = ordered_navs[-1]
    market_price = latest_nav.market_price if latest_nav.market_price is not None else current_price
    current_premium_discount = _premium_discount(latest_nav, current_price)
    history = []
    for nav in ordered_navs[-history_days:]:
        fallback = current_price if nav is latest_nav else None
        value = _premium_discount(nav, fallback)
        if value is not None:
            history.append(value)
    average = mean(history) if history else None
    volatility = pstdev(history) if len(history) >= 2 else None
    zscore = (
        (current_premium_discount - average) / volatility
        if current_premium_discount is not None
        and average is not None
        and volatility not in (None, 0)
        else None
    )

    sorted_holdings = sorted(holdings, key=lambda item: item.weight, reverse=True)
    weights = [holding.weight for holding in sorted_holdings]
    equity_types = {"equity", "stock", "common_stock", "common stock"}
    cash_types = {"cash", "currency", "money_market", "money market"}
    equity_weight = sum(
        holding.weight for holding in sorted_holdings if _holding_type(holding) in equity_types
    )
    cash_weight = sum(
        holding.weight for holding in sorted_holdings if _holding_type(holding) in cash_types
    )

    return EtfFeature(
        ticker=normalize_ticker(ticker),
        feature_date=date.today().isoformat(),
        nav_per_share=latest_nav.nav_per_share,
        market_price=market_price,
        premium_discount=current_premium_discount,
        premium_discount_average_60d=average,
        premium_discount_volatility_60d=volatility,
        premium_discount_zscore=zscore,
        holdings_count=len(sorted_holdings) if sorted_holdings else None,
        top_10_weight=sum(weights[:10]) if weights else None,
        largest_holding_weight=max(weights) if weights else None,
        equity_weight=equity_weight if sorted_holdings else None,
        cash_weight=cash_weight if sorted_holdings else None,
        latest_nav_date=latest_nav.nav_date,
        latest_holdings_date=sorted_holdings[0].holdings_date if sorted_holdings else None,
        as_of_date=date.today().isoformat(),
        effective_date=date.today().isoformat(),
    )


def refresh_etf_features(
    database_path: Path,
    tickers: tuple[str, ...] | list[str],
    history_days: int = 60,
) -> int:
    refreshed = 0
    for ticker in tickers:
        normalized = normalize_ticker(ticker)
        price_feature = latest_price_feature(database_path, normalized)
        feature = compute_etf_feature(
            normalized,
            list_etf_navs(database_path, normalized),
            latest_etf_holdings(database_path, normalized),
            price_feature.current_price if price_feature is not None else None,
            history_days,
        )
        if feature is None:
            continue
        upsert_etf_feature(database_path, feature)
        refreshed += 1
    return refreshed
