from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import date
from io import StringIO
from pathlib import Path

from .storage import (
    Estimate,
    Fundamental,
    normalize_ticker,
    upsert_estimate,
    upsert_fundamental,
)


FUNDAMENTAL_REQUIRED_COLUMNS = {
    "ticker",
    "fiscal_period_end",
    "fiscal_period",
    "report_type",
}

FUNDAMENTAL_NUMERIC_FIELDS = {
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
    "cash_and_equivalents",
    "total_debt",
    "net_debt",
    "total_assets",
    "total_equity",
    "shares_outstanding",
    "diluted_shares",
}

ESTIMATE_REQUIRED_COLUMNS = {
    "ticker",
    "estimate_date",
    "fiscal_period_end",
    "metric",
}

ESTIMATE_NUMERIC_FIELDS = {
    "consensus_mean",
    "consensus_median",
    "consensus_high",
    "consensus_low",
    "revision_1m",
    "revision_3m",
}

ESTIMATE_INTEGER_FIELDS = {"analyst_count"}

FUNDAMENTAL_HEADERS = (
    "ticker",
    "fiscal_period_end",
    "fiscal_period",
    "report_type",
    "currency",
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
    "cash_and_equivalents",
    "total_debt",
    "net_debt",
    "total_assets",
    "total_equity",
    "shares_outstanding",
    "diluted_shares",
    "source",
    "as_of_date",
    "effective_date",
)

ESTIMATE_HEADERS = (
    "ticker",
    "estimate_date",
    "fiscal_period_end",
    "metric",
    "fiscal_period",
    "currency",
    "consensus_mean",
    "consensus_median",
    "consensus_high",
    "consensus_low",
    "analyst_count",
    "revision_1m",
    "revision_3m",
    "source",
    "as_of_date",
    "effective_date",
)


@dataclass(frozen=True)
class CsvLoadResult:
    path: Path
    loaded_count: int
    tickers: tuple[str, ...]


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
        return float(value.replace(",", ""))
    except ValueError as error:
        raise ValueError(
            f"Row {row_number}: malformed numeric value for {name}: {value}."
        ) from error


def _int(row: dict[str, str], name: str, row_number: int) -> int | None:
    value = _text(row, name)
    if value is None:
        return None
    try:
        return int(value.replace(",", ""))
    except ValueError as error:
        raise ValueError(
            f"Row {row_number}: malformed integer value for {name}: {value}."
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


def parse_fundamentals_csv(text: str) -> list[Fundamental]:
    reader = csv.DictReader(StringIO(text))
    _validate_columns(reader, FUNDAMENTAL_REQUIRED_COLUMNS, "Fundamentals")

    fundamentals: list[Fundamental] = []
    for row in reader:
        if not any((value or "").strip() for value in row.values()):
            continue
        row_number = reader.line_num
        numeric_payload = {
            field: _float(row, field, row_number) for field in FUNDAMENTAL_NUMERIC_FIELDS
        }
        fundamentals.append(
            Fundamental(
                ticker=normalize_ticker(_required_text(row, "ticker", row_number)),
                fiscal_period_end=_date(
                    row, "fiscal_period_end", row_number, required=True
                )
                or "",
                fiscal_period=_required_text(row, "fiscal_period", row_number),
                report_type=_required_text(row, "report_type", row_number),
                currency=_text(row, "currency"),
                source=_text(row, "source", "manual_csv") or "manual_csv",
                as_of_date=_date(row, "as_of_date", row_number, required=False),
                effective_date=_date(row, "effective_date", row_number, required=False),
                **numeric_payload,
            )
        )
    return fundamentals


def parse_estimates_csv(text: str) -> list[Estimate]:
    reader = csv.DictReader(StringIO(text))
    _validate_columns(reader, ESTIMATE_REQUIRED_COLUMNS, "Estimates")

    estimates: list[Estimate] = []
    for row in reader:
        if not any((value or "").strip() for value in row.values()):
            continue
        row_number = reader.line_num
        numeric_payload = {
            field: _float(row, field, row_number) for field in ESTIMATE_NUMERIC_FIELDS
        }
        integer_payload = {
            field: _int(row, field, row_number) for field in ESTIMATE_INTEGER_FIELDS
        }
        estimates.append(
            Estimate(
                ticker=normalize_ticker(_required_text(row, "ticker", row_number)),
                estimate_date=_date(row, "estimate_date", row_number, required=True)
                or "",
                fiscal_period_end=_date(
                    row, "fiscal_period_end", row_number, required=True
                )
                or "",
                metric=_required_text(row, "metric", row_number).strip().lower(),
                fiscal_period=_text(row, "fiscal_period"),
                currency=_text(row, "currency"),
                source=_text(row, "source", "manual_csv") or "manual_csv",
                as_of_date=_date(row, "as_of_date", row_number, required=False),
                effective_date=_date(row, "effective_date", row_number, required=False),
                **numeric_payload,
                **integer_payload,
            )
        )
    return estimates


def load_fundamentals_csv(database_path: Path, path: Path) -> CsvLoadResult:
    fundamentals = parse_fundamentals_csv(path.read_text(encoding="utf-8-sig"))
    for fundamental in fundamentals:
        upsert_fundamental(database_path, fundamental)
    return CsvLoadResult(
        path=path,
        loaded_count=len(fundamentals),
        tickers=tuple(sorted({fundamental.ticker for fundamental in fundamentals})),
    )


def load_estimates_csv(database_path: Path, path: Path) -> CsvLoadResult:
    estimates = parse_estimates_csv(path.read_text(encoding="utf-8-sig"))
    for estimate in estimates:
        upsert_estimate(database_path, estimate)
    return CsvLoadResult(
        path=path,
        loaded_count=len(estimates),
        tickers=tuple(sorted({estimate.ticker for estimate in estimates})),
    )
