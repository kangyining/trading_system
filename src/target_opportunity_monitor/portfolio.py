from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import date
from io import StringIO
from pathlib import Path

from .config import AppConfig
from .storage import (
    PortfolioCash,
    PortfolioPosition,
    PortfolioReview,
    alert_statuses,
    insert_data_quality_check,
    is_scoreable_asset,
    latest_portfolio_cash,
    latest_portfolio_positions,
    latest_price_feature,
    list_assets,
    normalize_ticker,
    score_statuses,
    upsert_portfolio_cash,
    upsert_portfolio_position,
    upsert_portfolio_review,
)


POSITION_REQUIRED_COLUMNS = {"ticker", "quantity"}
CASH_REQUIRED_COLUMNS = {"cash_amount"}

POSITION_HEADERS = (
    "ticker",
    "quantity",
    "account",
    "position_date",
    "currency",
    "market_price",
    "market_value",
    "base_market_value",
    "cost_basis_per_share",
    "cost_basis_total",
    "asset_type",
    "sector",
    "source",
    "as_of_date",
    "effective_date",
)

CASH_HEADERS = (
    "account",
    "cash_date",
    "currency",
    "cash_amount",
    "base_cash_amount",
    "source",
    "as_of_date",
    "effective_date",
)

POSITION_NUMERIC_FIELDS = {
    "quantity",
    "market_price",
    "market_value",
    "base_market_value",
    "cost_basis_per_share",
    "cost_basis_total",
}
CASH_NUMERIC_FIELDS = {"cash_amount", "base_cash_amount"}
ACTIONABLE_BULLISH_ALERTS = {"bullish_divergence", "watch_only_gap"}


@dataclass(frozen=True)
class PortfolioLoadResult:
    positions_path: Path
    cash_path: Path
    position_count: int
    cash_count: int
    tickers: tuple[str, ...]
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class PortfolioReviewResult:
    ticker: str
    status: str
    review_category: str | None
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class PortfolioContextResult:
    computed_count: int
    results: tuple[PortfolioReviewResult, ...]


def ensure_portfolio_csv_headers(positions_path: Path, cash_path: Path) -> None:
    _ensure_header_file(positions_path, POSITION_HEADERS)
    _ensure_header_file(cash_path, CASH_HEADERS)


def _ensure_header_file(path: Path, headers: tuple[str, ...]) -> None:
    if path.exists():
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(",".join(headers) + "\n", encoding="utf-8")


def _lowered_fieldnames(fieldnames: list[str] | None) -> set[str]:
    return {field.strip().lower() for field in fieldnames or [] if field}


def _validate_columns(
    reader: csv.DictReader,
    required_columns: set[str],
    file_label: str,
) -> None:
    missing = required_columns - _lowered_fieldnames(reader.fieldnames)
    if missing:
        raise ValueError(
            f"{file_label} CSV missing required columns: {', '.join(sorted(missing))}"
        )


def _row_value(row: dict[str, str], name: str) -> str | None:
    wanted = name.strip().lower()
    for key, value in row.items():
        if key and key.strip().lower() == wanted:
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
        return float(value.replace(",", ""))
    except ValueError as error:
        raise ValueError(
            f"Row {row_number}: malformed numeric value for {name}: {value}."
        ) from error


def _positive_or_zero(value: float | None, name: str, row_number: int) -> float:
    if value is None:
        raise ValueError(f"Row {row_number}: missing required value for {name}.")
    if value < 0:
        raise ValueError(f"Row {row_number}: {name} must be non-negative.")
    return value


def parse_portfolio_positions_csv(text: str) -> list[PortfolioPosition]:
    reader = csv.DictReader(StringIO(text))
    _validate_columns(reader, POSITION_REQUIRED_COLUMNS, "Portfolio positions")

    positions: list[PortfolioPosition] = []
    for row in reader:
        if not any((value or "").strip() for value in row.values()):
            continue
        row_number = reader.line_num
        numeric_payload = {
            field: _float(row, field, row_number) for field in POSITION_NUMERIC_FIELDS
        }
        quantity = _positive_or_zero(numeric_payload.pop("quantity"), "quantity", row_number)
        positions.append(
            PortfolioPosition(
                ticker=normalize_ticker(_required_text(row, "ticker", row_number)),
                quantity=quantity,
                account=_text(row, "account", "default") or "default",
                position_date=_date(row, "position_date", row_number, required=False)
                or date.today().isoformat(),
                currency=(_text(row, "currency", "USD") or "USD").upper(),
                asset_type=_text(row, "asset_type"),
                sector=_text(row, "sector"),
                source=_text(row, "source", "manual_csv") or "manual_csv",
                as_of_date=_date(row, "as_of_date", row_number, required=False),
                effective_date=_date(row, "effective_date", row_number, required=False),
                **numeric_payload,
            )
        )
    return positions


def parse_portfolio_cash_csv(text: str) -> list[PortfolioCash]:
    reader = csv.DictReader(StringIO(text))
    _validate_columns(reader, CASH_REQUIRED_COLUMNS, "Portfolio cash")

    cash_rows: list[PortfolioCash] = []
    for row in reader:
        if not any((value or "").strip() for value in row.values()):
            continue
        row_number = reader.line_num
        numeric_payload = {
            field: _float(row, field, row_number) for field in CASH_NUMERIC_FIELDS
        }
        cash_amount = _positive_or_zero(
            numeric_payload.pop("cash_amount"), "cash_amount", row_number
        )
        cash_rows.append(
            PortfolioCash(
                cash_amount=cash_amount,
                account=_text(row, "account", "default") or "default",
                cash_date=_date(row, "cash_date", row_number, required=False)
                or date.today().isoformat(),
                currency=(_text(row, "currency", "USD") or "USD").upper(),
                source=_text(row, "source", "manual_csv") or "manual_csv",
                as_of_date=_date(row, "as_of_date", row_number, required=False),
                effective_date=_date(row, "effective_date", row_number, required=False),
                **numeric_payload,
            )
        )
    return cash_rows


def load_portfolio_csvs(
    config: AppConfig,
    positions_path: Path | None = None,
    cash_path: Path | None = None,
) -> PortfolioLoadResult:
    selected_positions_path = positions_path or config.portfolio_positions_path
    selected_cash_path = cash_path or config.portfolio_cash_path
    ensure_portfolio_csv_headers(config.portfolio_positions_path, config.portfolio_cash_path)

    positions = parse_portfolio_positions_csv(
        selected_positions_path.read_text(encoding="utf-8-sig")
    )
    cash_rows = parse_portfolio_cash_csv(selected_cash_path.read_text(encoding="utf-8-sig"))
    warnings: list[str] = []

    if not positions:
        warnings.append("empty_portfolio_positions")
    if not cash_rows:
        warnings.append("empty_portfolio_cash")

    enriched_positions: list[PortfolioPosition] = []
    for position in positions:
        feature = latest_price_feature(config.database_path, position.ticker)
        current_price = feature.current_price if feature else None
        market_price = position.market_price if position.market_price is not None else current_price
        market_value = position.market_value
        if market_value is None and market_price is not None:
            market_value = position.quantity * market_price
        if market_value is None:
            warnings.append(f"{position.ticker}:missing_price_for_market_value")

        base_market_value = position.base_market_value
        currency = (position.currency or config.portfolio_base_currency).upper()
        if base_market_value is None and currency == config.portfolio_base_currency.upper():
            base_market_value = market_value
        elif base_market_value is None and currency != config.portfolio_base_currency.upper():
            warnings.append(f"{position.ticker}:missing_fx_conversion")

        cost_basis_total = position.cost_basis_total
        if cost_basis_total is None and position.cost_basis_per_share is not None:
            cost_basis_total = position.cost_basis_per_share * position.quantity

        enriched_positions.append(
            PortfolioPosition(
                ticker=position.ticker,
                quantity=position.quantity,
                account=position.account,
                position_date=position.position_date,
                currency=position.currency,
                market_price=market_price,
                market_value=market_value,
                base_market_value=base_market_value,
                cost_basis_per_share=position.cost_basis_per_share,
                cost_basis_total=cost_basis_total,
                asset_type=position.asset_type,
                sector=position.sector,
                source=position.source,
                as_of_date=position.as_of_date,
                effective_date=position.effective_date,
            )
        )

    for position in enriched_positions:
        upsert_portfolio_position(config.database_path, position)

    for cash in cash_rows:
        base_cash_amount = cash.base_cash_amount
        currency = (cash.currency or config.portfolio_base_currency).upper()
        if base_cash_amount is None and currency == config.portfolio_base_currency.upper():
            base_cash_amount = cash.cash_amount
        elif base_cash_amount is None and currency != config.portfolio_base_currency.upper():
            warnings.append(f"cash:{currency}:missing_fx_conversion")
        upsert_portfolio_cash(
            config.database_path,
            PortfolioCash(
                cash_amount=cash.cash_amount,
                account=cash.account,
                cash_date=cash.cash_date,
                currency=cash.currency,
                base_cash_amount=base_cash_amount,
                source=cash.source,
                as_of_date=cash.as_of_date,
                effective_date=cash.effective_date,
            ),
        )

    tickers = tuple(sorted({position.ticker for position in enriched_positions}))
    return PortfolioLoadResult(
        positions_path=selected_positions_path,
        cash_path=selected_cash_path,
        position_count=len(enriched_positions),
        cash_count=len(cash_rows),
        tickers=tickers,
        warnings=tuple(_unique(warnings)),
    )


def _unique(values: list[str]) -> list[str]:
    output: list[str] = []
    for value in values:
        if value and value not in output:
            output.append(value)
    return output


def _safe_divide(numerator: float | None, denominator: float | None) -> float | None:
    if numerator is None or denominator in (None, 0):
        return None
    return numerator / denominator


def _join(values: list[str | None]) -> str | None:
    cleaned = _unique([value for value in values if value])
    return ", ".join(cleaned) if cleaned else None


def _currency_base_value(
    value: float | None,
    base_value: float | None,
    currency: str | None,
    base_currency: str,
) -> tuple[float | None, str | None]:
    if base_value is not None:
        return base_value, None
    if (currency or base_currency).upper() == base_currency.upper():
        return value, None
    return None, "missing_fx_conversion"


def _latest_price(config: AppConfig, ticker: str) -> float | None:
    feature = latest_price_feature(config.database_path, ticker)
    return feature.current_price if feature else None


def _position_base_value(config: AppConfig, position: PortfolioPosition) -> tuple[float | None, str | None]:
    market_value = position.base_market_value
    warning: str | None = None
    if market_value is None:
        raw_value = position.market_value
        if raw_value is None:
            current_price = _latest_price(config, position.ticker)
            raw_value = (
                position.quantity * current_price if current_price is not None else None
            )
            if raw_value is None:
                warning = "missing_price_for_market_value"
        market_value, fx_warning = _currency_base_value(
            raw_value,
            None,
            position.currency,
            config.portfolio_base_currency,
        )
        warning = warning or fx_warning
    return market_value, warning


def _cash_base_value(config: AppConfig, cash: PortfolioCash) -> tuple[float | None, str | None]:
    return _currency_base_value(
        cash.cash_amount,
        cash.base_cash_amount,
        cash.currency,
        config.portfolio_base_currency,
    )


def _risk_score(alert: object | None, score: object | None) -> float | None:
    alert_risk = getattr(alert, "risk_score", None)
    return alert_risk if alert_risk is not None else getattr(score, "risk_score", None)


def _opportunity_score(alert: object | None, score: object | None) -> float | None:
    alert_score = getattr(alert, "opportunity_score", None)
    return alert_score if alert_score is not None else getattr(score, "opportunity_score", None)


def _confidence_score(alert: object | None, score: object | None) -> float | None:
    alert_confidence = getattr(alert, "confidence_score", None)
    return (
        alert_confidence
        if alert_confidence is not None
        else getattr(score, "confidence_score", None)
    )


def _sizing_text(category: str, max_add_value: float | None) -> str:
    value_text = f"${max_add_value:,.2f}" if max_add_value is not None else "$0.00"
    if category == "small_starter_candidate":
        return f"Advisory starter capacity up to {value_text}."
    if category == "add_candidate":
        return f"Advisory add capacity up to {value_text}."
    if category == "reduce_risk_review":
        return "Review risk or exposure before adding."
    if category == "exit_review_candidate":
        return "Review exit case; bearish valuation and weak risk/opportunity profile."
    if category == "research_deeper":
        return "Research deeper before sizing; signal or portfolio inputs are incomplete."
    if category == "review_existing_position":
        return "Held position; review against latest target, score, and alert context."
    return "No portfolio action."


def _category_for_review(
    *,
    asset_type: str,
    held: bool,
    alert_type: str | None,
    opportunity_score: float | None,
    confidence_score: float | None,
    risk_score: float | None,
    position_weight: float | None,
    sector_weight: float | None,
    max_add_value: float | None,
    warnings: list[str],
    config: AppConfig,
) -> str:
    if asset_type == "etf":
        return "review_existing_position" if held else "watch"

    actionable = alert_type in ACTIONABLE_BULLISH_ALERTS
    bearish = alert_type == "bearish_overvaluation"
    risk_warning = alert_type == "risk_warning" or (
        risk_score is not None and risk_score < 40
    )
    over_position = (
        position_weight is not None
        and position_weight > config.portfolio_default_max_position_weight
    )
    over_sector = (
        sector_weight is not None and sector_weight > config.portfolio_max_sector_weight
    )
    weak_confidence = confidence_score is not None and confidence_score < 60
    blocked = (
        max_add_value is not None
        and max_add_value <= 0
        and actionable
        and "no_portfolio_data" not in warnings
    )

    if held and bearish and ((opportunity_score or 0) < 50 or (risk_score or 100) < 40):
        return "exit_review_candidate"
    if held and (bearish or risk_warning or over_position or over_sector):
        return "reduce_risk_review"
    if actionable and ("no_portfolio_data" in warnings or weak_confidence or blocked):
        return "research_deeper"
    if actionable and held:
        return "add_candidate"
    if actionable and not held:
        return "small_starter_candidate"
    if held:
        return "review_existing_position"
    return "watch"


def compute_portfolio_context(
    config: AppConfig,
    ticker: str | None = None,
) -> PortfolioContextResult:
    assets = [asset for asset in list_assets(config.database_path) if is_scoreable_asset(asset)]
    if ticker:
        requested_ticker = normalize_ticker(ticker)
        review_assets = [asset for asset in assets if asset.ticker == requested_ticker]
    else:
        review_assets = assets

    positions = latest_portfolio_positions(config.database_path)
    cash_rows = latest_portfolio_cash(config.database_path)
    asset_by_ticker = {asset.ticker: asset for asset in assets}
    alerts_by_ticker = {status.ticker: status for status in alert_statuses(config.database_path)}
    scores_by_ticker = {status.ticker: status for status in score_statuses(config.database_path)}

    position_warnings: dict[str, list[str]] = {}
    position_values: dict[str, float] = {}
    quantities: dict[str, float] = {}
    cost_basis: dict[str, float] = {}
    sector_by_ticker: dict[str, str] = {}

    for position in positions:
        base_value, warning = _position_base_value(config, position)
        ticker_warnings = position_warnings.setdefault(position.ticker, [])
        if warning:
            ticker_warnings.append(warning)
        if base_value is not None:
            position_values[position.ticker] = position_values.get(position.ticker, 0.0) + base_value
        quantities[position.ticker] = quantities.get(position.ticker, 0.0) + position.quantity
        if position.cost_basis_total is not None:
            cost_basis[position.ticker] = cost_basis.get(position.ticker, 0.0) + position.cost_basis_total
        asset = asset_by_ticker.get(position.ticker)
        sector_by_ticker[position.ticker] = (
            position.sector or (asset.sector if asset else None) or "unknown"
        )

    cash_warnings: list[str] = []
    base_cash = 0.0
    for cash in cash_rows:
        value, warning = _cash_base_value(config, cash)
        if warning:
            cash_warnings.append(f"cash:{cash.currency or ''}:{warning}")
        if value is not None:
            base_cash += value

    total_positions = sum(position_values.values())
    total_portfolio_value = total_positions + base_cash
    cash_reserve = total_portfolio_value * config.portfolio_cash_reserve_weight
    cash_available = max(base_cash - cash_reserve, 0.0)
    no_portfolio_data = not positions and not cash_rows

    sector_values: dict[str, float] = {}
    for position_ticker, value in position_values.items():
        sector = sector_by_ticker.get(position_ticker)
        if not sector:
            sector = asset_by_ticker.get(position_ticker).sector if position_ticker in asset_by_ticker else None
        sector_values[sector or "unknown"] = sector_values.get(sector or "unknown", 0.0) + value

    today = date.today().isoformat()
    results: list[PortfolioReviewResult] = []
    for asset in review_assets:
        ticker_warnings = list(position_warnings.get(asset.ticker, []))
        if no_portfolio_data:
            ticker_warnings.append("no_portfolio_data")
        if not cash_rows:
            ticker_warnings.append("no_cash_data")
        ticker_warnings.extend(cash_warnings)

        asset_type = (asset.asset_type or "equity").lower()
        if asset_type == "etf":
            ticker_warnings.append("etf_portfolio_review_gated")

        position_value = position_values.get(asset.ticker)
        quantity = quantities.get(asset.ticker)
        held = bool((quantity or 0.0) > 0 or (position_value or 0.0) > 0)
        sector = sector_by_ticker.get(asset.ticker) or asset.sector or "unknown"
        current_sector_value = sector_values.get(sector, 0.0)
        position_weight = _safe_divide(position_value, total_portfolio_value)
        sector_weight = _safe_divide(current_sector_value, total_portfolio_value)
        alert = alerts_by_ticker.get(asset.ticker)
        score = scores_by_ticker.get(asset.ticker)
        alert_type = alert.alert_type if alert else None
        risk_score = _risk_score(alert, score)
        opportunity = _opportunity_score(alert, score)
        confidence = _confidence_score(alert, score)

        max_position_room = max(
            total_portfolio_value * config.portfolio_default_max_position_weight
            - (position_value or 0.0),
            0.0,
        )
        sector_room = max(
            total_portfolio_value * config.portfolio_max_sector_weight
            - current_sector_value,
            0.0,
        )
        target_add_weight = (
            config.portfolio_default_add_position_weight
            if held
            else config.portfolio_default_starter_position_weight
        )
        target_add_value = total_portfolio_value * target_add_weight
        max_add_value = min(cash_available, max_position_room, sector_room, target_add_value)
        if no_portfolio_data or asset_type == "etf":
            max_add_value = 0.0

        if (
            position_weight is not None
            and position_weight > config.portfolio_default_max_position_weight
        ):
            ticker_warnings.append("max_position_exceeded")
        if sector_weight is not None and sector_weight > config.portfolio_max_sector_weight:
            ticker_warnings.append("max_sector_exceeded")
        if alert_type in ACTIONABLE_BULLISH_ALERTS and max_add_value <= 0 and not no_portfolio_data:
            ticker_warnings.append("sizing_blocked")

        review_category = _category_for_review(
            asset_type=asset_type,
            held=held,
            alert_type=alert_type,
            opportunity_score=opportunity,
            confidence_score=confidence,
            risk_score=risk_score,
            position_weight=position_weight,
            sector_weight=sector_weight,
            max_add_value=max_add_value,
            warnings=ticker_warnings,
            config=config,
        )
        risk_notes = _join(
            [
                alert.main_risks if alert else None,
                alert.risk_codes if alert else None,
                _join(ticker_warnings),
            ]
        )
        review = PortfolioReview(
            ticker=asset.ticker,
            review_date=today,
            asset_type=asset_type,
            held_flag=1 if held else 0,
            quantity=quantity,
            position_value=position_value,
            cost_basis_total=cost_basis.get(asset.ticker),
            unrealized_gain_loss=(
                position_value - cost_basis[asset.ticker]
                if position_value is not None and asset.ticker in cost_basis
                else None
            ),
            position_weight=position_weight,
            sector=sector,
            sector_weight=sector_weight,
            cash_available=cash_available,
            total_portfolio_value=total_portfolio_value,
            review_category=review_category,
            sizing_guidance=_sizing_text(review_category, max_add_value),
            max_add_value=max_add_value,
            risk_notes=risk_notes,
            data_warnings=_join(ticker_warnings),
            model_version=config.portfolio_model_version,
            source="portfolio",
            as_of_date=today,
            effective_date=today,
        )
        upsert_portfolio_review(config.database_path, review)
        insert_data_quality_check(
            config.database_path,
            check_name=f"portfolio:{asset.ticker}",
            status="warning" if ticker_warnings else "ok",
            details=", ".join(_unique(ticker_warnings)) if ticker_warnings else "ok",
            source="portfolio",
            as_of_date=today,
            effective_date=today,
        )
        results.append(
            PortfolioReviewResult(
                ticker=asset.ticker,
                status="warning" if ticker_warnings else "ok",
                review_category=review_category,
                warnings=tuple(_unique(ticker_warnings)),
            )
        )

    return PortfolioContextResult(computed_count=len(results), results=tuple(results))
