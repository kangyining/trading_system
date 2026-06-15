from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import date, timedelta
import json
import os
from pathlib import Path
import sqlite3
import tempfile
import time
from typing import Iterable
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .config import AppConfig
from .revision_evidence import (
    build_revision_evidence,
    derive_eps_revision,
    derive_estimate_dispersion,
    derive_recommendation_revision,
)
from .signals import ANALYST_REVISION_HEADERS, AnalystRevisionInput, ensure_analyst_revision_csv_header
from .storage import (
    AnalystRevisionAggregate,
    AnalystRevisionSourceSnapshot,
    Asset,
    delete_analyst_revision_aggregate,
    is_scoreable_asset,
    list_analyst_revision_aggregates,
    list_analyst_revision_source_snapshots,
    list_assets,
    normalize_ticker,
    upsert_analyst_revision_aggregate,
    upsert_analyst_revision_source_snapshot,
)


SOURCE_EXPORT_HEADERS = (
    "ticker",
    "signal_date",
    "source",
    "source_url",
    "notes",
    "capture_method",
    "eps_current",
    "eps_30d_ago",
    "eps_90d_ago",
    "eps_high",
    "eps_low",
    "eps_average",
    "analyst_count",
    "revenue_current",
    "revenue_30d_ago",
    "revenue_90d_ago",
    "target_price_current",
    "target_price_90d_ago",
    "recommendation_current_strong_buy",
    "recommendation_current_buy",
    "recommendation_current_hold",
    "recommendation_current_sell",
    "recommendation_current_strong_sell",
    "recommendation_90d_ago_strong_buy",
    "recommendation_90d_ago_buy",
    "recommendation_90d_ago_hold",
    "recommendation_90d_ago_sell",
    "recommendation_90d_ago_strong_sell",
)

REQUIRED_SOURCE_EXPORT_COLUMNS = {
    "ticker",
    "signal_date",
    "source",
    "source_url",
    "notes",
}

NUMERIC_SOURCE_EXPORT_FIELDS = tuple(
    header
    for header in SOURCE_EXPORT_HEADERS
    if header not in REQUIRED_SOURCE_EXPORT_COLUMNS | {"capture_method"}
)

REVISION_OUTPUT_FIELDS = (
    "eps_revision_1m",
    "eps_revision_3m",
    "revenue_revision_1m",
    "revenue_revision_3m",
    "target_price_revision_3m",
    "recommendation_revision",
    "estimate_dispersion",
)

CURRENT_RECOMMENDATION_FIELDS = {
    "strongBuy": "recommendation_current_strong_buy",
    "buy": "recommendation_current_buy",
    "hold": "recommendation_current_hold",
    "sell": "recommendation_current_sell",
    "strongSell": "recommendation_current_strong_sell",
}

PRIOR_RECOMMENDATION_FIELDS = {
    "strongBuy": "recommendation_90d_ago_strong_buy",
    "buy": "recommendation_90d_ago_buy",
    "hold": "recommendation_90d_ago_hold",
    "sell": "recommendation_90d_ago_sell",
    "strongSell": "recommendation_90d_ago_strong_sell",
}

SOURCE_EXPORT_TEMPLATE_FILES = (
    "analyst_revision_source_export.csv",
    "secbot_public_page.csv",
    "techi_public_page.csv",
    "redmatter_public_page.csv",
    "morningstar_manual.csv",
    "gurufocus_manual.csv",
)

SOURCE_WEIGHTS = {
    "fmp": 1.0,
    "financial_modeling_prep": 1.0,
    "alpha_vantage": 1.0,
    "business_quant": 0.85,
    "finnhub": 0.85,
    "yfinance": 0.7,
    "yahoo_finance": 0.7,
    "yahoo_finance_analysis": 0.7,
    "ibkr": 0.8,
    "secbot_public_page": 0.6,
    "redmatter_public_page": 0.5,
    "techi_public_page": 0.4,
    "morningstar_manual": 0.9,
    "gurufocus_manual": 0.9,
    "provider_export": 0.8,
    "analyst_revision_aggregate": 1.0,
}

PRIMARY_API_SOURCES = {
    "fmp",
    "financial_modeling_prep",
    "alpha_vantage",
    "business_quant",
    "finnhub",
}
HTTP_TIMEOUT_SECONDS = 12
ALPHA_VANTAGE_REQUEST_DELAY_SECONDS = 1.1


def _read_windows_registry_env(name: str) -> str | None:
    try:
        import winreg  # type: ignore[import-not-found]
    except Exception:
        return None

    locations = (
        (winreg.HKEY_CURRENT_USER, "Environment"),
        (
            winreg.HKEY_LOCAL_MACHINE,
            r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment",
        ),
    )
    for hive, subkey in locations:
        try:
            with winreg.OpenKey(hive, subkey) as key:
                value, _ = winreg.QueryValueEx(key, name)
        except OSError:
            continue
        if value:
            return str(value)
    return None


def _secret_env(name: str) -> str | None:
    value = os.environ.get(name)
    if value:
        return value
    return _read_windows_registry_env(name)


@dataclass(frozen=True)
class AnalystRevisionSourceRow:
    ticker: str
    signal_date: str
    source: str
    source_url: str
    notes: str
    capture_method: str = "manual_capture"
    eps_current: float | None = None
    eps_30d_ago: float | None = None
    eps_90d_ago: float | None = None
    eps_high: float | None = None
    eps_low: float | None = None
    eps_average: float | None = None
    analyst_count: int | None = None
    revenue_current: float | None = None
    revenue_30d_ago: float | None = None
    revenue_90d_ago: float | None = None
    target_price_current: float | None = None
    target_price_90d_ago: float | None = None
    recommendation_current_strong_buy: float | None = None
    recommendation_current_buy: float | None = None
    recommendation_current_hold: float | None = None
    recommendation_current_sell: float | None = None
    recommendation_current_strong_sell: float | None = None
    recommendation_90d_ago_strong_buy: float | None = None
    recommendation_90d_ago_buy: float | None = None
    recommendation_90d_ago_hold: float | None = None
    recommendation_90d_ago_sell: float | None = None
    recommendation_90d_ago_strong_sell: float | None = None


@dataclass(frozen=True)
class RevisionSourceDeriveResult:
    source_path: Path
    output_path: Path
    source_row_count: int
    derived_row_count: int
    written_row_count: int
    skipped_count: int
    tickers: tuple[str, ...]
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class RevisionSourceImportResult:
    source_dir: Path
    source_files: tuple[Path, ...]
    source_row_count: int
    imported_count: int
    skipped_count: int
    tickers: tuple[str, ...]
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class RevisionAggregateResult:
    aggregate_count: int
    written_row_count: int
    tickers: tuple[str, ...]
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class RevisionProviderFetchResult:
    provider: str
    fetched_count: int
    stored_count: int
    skipped_count: int
    tickers: tuple[str, ...]
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class RevisionProviderStatus:
    provider: str
    enabled: bool
    available: bool
    status: str
    details: str


@dataclass(frozen=True)
class RevisionSourceTickerStatus:
    ticker: str
    asset_type: str
    source_backed: bool
    signal_date: str | None
    source: str | None
    stale: bool
    warnings: tuple[str, ...]
    source_count: int = 0
    aggregate_confidence: float | None = None
    source_disagreement: str | None = None


@dataclass(frozen=True)
class RevisionSourceStatusReport:
    source_export_path: Path
    source_export_exists: bool
    source_exports_dir: Path
    source_snapshot_count: int
    aggregate_count: int
    analyst_revisions_path: Path
    analyst_revisions_exists: bool
    active_equity_count: int
    source_backed_ticker_count: int
    source_backed_tickers: tuple[str, ...]
    missing_source_tickers: tuple[str, ...]
    stale_tickers: tuple[str, ...]
    skipped_etf_tickers: tuple[str, ...]
    missing_source_field_tickers: tuple[str, ...]
    evidence_decision: str
    statuses: tuple[RevisionSourceTickerStatus, ...]
    warnings: tuple[str, ...]


def ensure_analyst_revision_source_export_header(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists() or not path.read_text(encoding="utf-8-sig").strip():
        path.write_text(",".join(SOURCE_EXPORT_HEADERS) + "\n", encoding="utf-8")
        return

    reader = csv.DictReader(path.read_text(encoding="utf-8-sig").splitlines())
    if not reader.fieldnames:
        path.write_text(",".join(SOURCE_EXPORT_HEADERS) + "\n", encoding="utf-8")
        return
    if set(SOURCE_EXPORT_HEADERS).issubset(reader.fieldnames):
        return

    rows = list(reader)
    with path.open("w", newline="", encoding="utf-8") as output:
        writer = csv.DictWriter(output, fieldnames=SOURCE_EXPORT_HEADERS)
        writer.writeheader()
        for row in rows:
            migrated = {header: row.get(header, "") for header in SOURCE_EXPORT_HEADERS}
            migrated["capture_method"] = migrated["capture_method"] or "manual_capture"
            writer.writerow(migrated)


def ensure_revision_source_export_templates(config: AppConfig) -> tuple[Path, ...]:
    config.analyst_revision_source_exports_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    for filename in SOURCE_EXPORT_TEMPLATE_FILES:
        path = config.analyst_revision_source_exports_dir / filename
        ensure_analyst_revision_source_export_header(path)
        paths.append(path)
    ensure_analyst_revision_source_export_header(config.analyst_revision_source_export_path)
    if config.analyst_revision_source_export_path not in paths:
        paths.append(config.analyst_revision_source_export_path)
    return tuple(paths)


def _parse_date(value: str, field_name: str, row_number: int) -> str:
    text = value.strip()
    if not text:
        raise ValueError(f"Row {row_number}: missing required {field_name}.")
    try:
        return date.fromisoformat(text).isoformat()
    except ValueError as error:
        raise ValueError(f"Row {row_number}: malformed {field_name}: {text}") from error


def _parse_float(value: str | None, field_name: str, row_number: int) -> float | None:
    text = (value or "").strip()
    if not text:
        return None
    try:
        return float(text)
    except ValueError as error:
        raise ValueError(f"Row {row_number}: malformed {field_name}: {text}") from error


def _parse_int(value: str | None, field_name: str, row_number: int) -> int | None:
    text = (value or "").strip()
    if not text:
        return None
    try:
        return int(float(text))
    except ValueError as error:
        raise ValueError(f"Row {row_number}: malformed {field_name}: {text}") from error


def parse_analyst_revision_source_export_csv(text: str) -> list[AnalystRevisionSourceRow]:
    reader = csv.DictReader(text.splitlines())
    if not reader.fieldnames:
        raise ValueError("Analyst revision source-export CSV missing header.")
    missing = REQUIRED_SOURCE_EXPORT_COLUMNS - set(reader.fieldnames)
    if missing:
        raise ValueError(
            "Analyst revision source-export CSV missing required columns: "
            + ", ".join(sorted(missing))
        )

    rows: list[AnalystRevisionSourceRow] = []
    for row_number, row in enumerate(reader, start=2):
        if not any((value or "").strip() for value in row.values()):
            continue
        ticker = normalize_ticker(row.get("ticker", ""))
        if not ticker:
            raise ValueError(f"Row {row_number}: missing required ticker.")
        signal_date = _parse_date(row.get("signal_date", ""), "signal_date", row_number)
        source = (row.get("source") or "").strip()
        source_url = (row.get("source_url") or "").strip()
        notes = (row.get("notes") or "").strip()
        capture_method = (row.get("capture_method") or "manual_capture").strip()
        if not source:
            raise ValueError(f"Row {row_number}: missing required source.")
        if not source_url:
            raise ValueError(f"Row {row_number}: missing required source_url.")
        if not notes:
            raise ValueError(f"Row {row_number}: missing required notes.")

        payload = {
            field: _parse_float(row.get(field), field, row_number)
            for field in NUMERIC_SOURCE_EXPORT_FIELDS
            if field != "analyst_count"
        }
        payload["analyst_count"] = _parse_int(
            row.get("analyst_count"), "analyst_count", row_number
        )
        source_row = AnalystRevisionSourceRow(
            ticker=ticker,
            signal_date=signal_date,
            source=source,
            source_url=source_url,
            notes=notes,
            capture_method=capture_method,
            **payload,
        )
        if not _has_derivable_signal(source_row):
            raise ValueError(f"Row {row_number}: no derivable numeric revision signal.")
        rows.append(source_row)
    return rows


def _recommendation_counts(
    row: AnalystRevisionSourceRow,
    fields: dict[str, str],
) -> dict[str, float | None]:
    return {key: getattr(row, field_name) for key, field_name in fields.items()}


def _target_price_revision(
    current: float | None,
    prior: float | None,
) -> float | None:
    if current is None or prior in (None, 0):
        return None
    return current / prior - 1.0


def _has_derivable_signal(row: AnalystRevisionSourceRow) -> bool:
    return any(
        value is not None
        for value in (
            derive_eps_revision(row.eps_current, row.eps_30d_ago),
            derive_eps_revision(row.eps_current, row.eps_90d_ago),
            derive_eps_revision(row.revenue_current, row.revenue_30d_ago),
            derive_eps_revision(row.revenue_current, row.revenue_90d_ago),
            _target_price_revision(row.target_price_current, row.target_price_90d_ago),
            derive_recommendation_revision(
                _recommendation_counts(row, CURRENT_RECOMMENDATION_FIELDS),
                _recommendation_counts(row, PRIOR_RECOMMENDATION_FIELDS),
            ),
            derive_estimate_dispersion(row.eps_high, row.eps_low, row.eps_average),
        )
    )


def derive_analyst_revision_input(row: AnalystRevisionSourceRow) -> AnalystRevisionInput:
    revision = AnalystRevisionInput(
        ticker=row.ticker,
        signal_date=row.signal_date,
        eps_revision_1m=derive_eps_revision(row.eps_current, row.eps_30d_ago),
        eps_revision_3m=derive_eps_revision(row.eps_current, row.eps_90d_ago),
        revenue_revision_1m=derive_eps_revision(row.revenue_current, row.revenue_30d_ago),
        revenue_revision_3m=derive_eps_revision(row.revenue_current, row.revenue_90d_ago),
        target_price_revision_3m=_target_price_revision(
            row.target_price_current,
            row.target_price_90d_ago,
        ),
        recommendation_revision=derive_recommendation_revision(
            _recommendation_counts(row, CURRENT_RECOMMENDATION_FIELDS),
            _recommendation_counts(row, PRIOR_RECOMMENDATION_FIELDS),
        ),
        estimate_dispersion=derive_estimate_dispersion(
            row.eps_high,
            row.eps_low,
            row.eps_average,
        ),
        analyst_count=row.analyst_count,
        source=row.source,
        source_url=row.source_url,
        notes=row.notes,
        as_of_date=date.today().isoformat(),
        effective_date=row.signal_date,
    )
    if not any(getattr(revision, field) is not None for field in REVISION_OUTPUT_FIELDS):
        raise ValueError(f"{row.ticker} {row.signal_date}: no derivable numeric revision signal.")
    return revision


def _source_key(source: str) -> str:
    return source.strip().lower()


def _source_weight(source: str) -> float:
    return SOURCE_WEIGHTS.get(_source_key(source), 0.5)


def _source_confidence(source: str) -> float:
    return min(100.0, max(0.0, _source_weight(source) * 100.0))


def _source_snapshot_from_row(row: AnalystRevisionSourceRow) -> AnalystRevisionSourceSnapshot:
    derived = derive_analyst_revision_input(row)
    return AnalystRevisionSourceSnapshot(
        ticker=row.ticker,
        signal_date=row.signal_date,
        source=row.source,
        source_url=row.source_url,
        notes=row.notes,
        capture_method=row.capture_method,
        provider_status="ok",
        eps_current=row.eps_current,
        eps_30d_ago=row.eps_30d_ago,
        eps_90d_ago=row.eps_90d_ago,
        eps_high=row.eps_high,
        eps_low=row.eps_low,
        eps_average=row.eps_average,
        analyst_count=row.analyst_count,
        revenue_current=row.revenue_current,
        revenue_30d_ago=row.revenue_30d_ago,
        revenue_90d_ago=row.revenue_90d_ago,
        target_price_current=row.target_price_current,
        target_price_90d_ago=row.target_price_90d_ago,
        recommendation_current_strong_buy=row.recommendation_current_strong_buy,
        recommendation_current_buy=row.recommendation_current_buy,
        recommendation_current_hold=row.recommendation_current_hold,
        recommendation_current_sell=row.recommendation_current_sell,
        recommendation_current_strong_sell=row.recommendation_current_strong_sell,
        recommendation_90d_ago_strong_buy=row.recommendation_90d_ago_strong_buy,
        recommendation_90d_ago_buy=row.recommendation_90d_ago_buy,
        recommendation_90d_ago_hold=row.recommendation_90d_ago_hold,
        recommendation_90d_ago_sell=row.recommendation_90d_ago_sell,
        recommendation_90d_ago_strong_sell=row.recommendation_90d_ago_strong_sell,
        eps_revision_1m=derived.eps_revision_1m,
        eps_revision_3m=derived.eps_revision_3m,
        revenue_revision_1m=derived.revenue_revision_1m,
        revenue_revision_3m=derived.revenue_revision_3m,
        target_price_revision_3m=derived.target_price_revision_3m,
        recommendation_revision=derived.recommendation_revision,
        estimate_dispersion=derived.estimate_dispersion,
        source_confidence=_source_confidence(row.source),
        as_of_date=date.today().isoformat(),
        effective_date=row.signal_date,
    )


def _format_float(value: float | None) -> str:
    return "" if value is None else f"{value:.10g}"


def _format_int(value: int | None) -> str:
    return "" if value is None else str(value)


def _revision_input_to_csv_row(row: AnalystRevisionInput) -> dict[str, str]:
    return {
        "ticker": row.ticker,
        "signal_date": row.signal_date,
        "eps_revision_1m": _format_float(row.eps_revision_1m),
        "eps_revision_3m": _format_float(row.eps_revision_3m),
        "revenue_revision_1m": _format_float(row.revenue_revision_1m),
        "revenue_revision_3m": _format_float(row.revenue_revision_3m),
        "target_price_revision_3m": _format_float(row.target_price_revision_3m),
        "recommendation_revision": _format_float(row.recommendation_revision),
        "estimate_dispersion": _format_float(row.estimate_dispersion),
        "analyst_count": _format_int(row.analyst_count),
        "source": row.source,
        "source_url": row.source_url or "",
        "notes": row.notes or "",
        "as_of_date": row.as_of_date or "",
        "effective_date": row.effective_date or "",
    }


def _aggregate_to_revision_input(row: AnalystRevisionAggregate) -> AnalystRevisionInput:
    return AnalystRevisionInput(
        ticker=row.ticker,
        signal_date=row.signal_date,
        eps_revision_1m=row.eps_revision_1m,
        eps_revision_3m=row.eps_revision_3m,
        revenue_revision_1m=row.revenue_revision_1m,
        revenue_revision_3m=row.revenue_revision_3m,
        target_price_revision_3m=row.target_price_revision_3m,
        recommendation_revision=row.recommendation_revision,
        estimate_dispersion=row.estimate_dispersion,
        analyst_count=row.analyst_count,
        source=row.source,
        source_url=row.source_url,
        notes=row.notes,
        as_of_date=row.as_of_date,
        effective_date=row.effective_date,
    )


def _write_final_revision_rows(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as output:
        writer = csv.DictWriter(output, fieldnames=ANALYST_REVISION_HEADERS)
        writer.writeheader()
        writer.writerows(rows)


def _asset_maps(config: AppConfig) -> tuple[dict[str, Asset], dict[str, Asset]]:
    try:
        assets = {
            asset.ticker: asset
            for asset in list_assets(config.database_path)
            if is_scoreable_asset(asset)
        }
    except sqlite3.Error:
        assets = {}
    equity_assets = {
        ticker: asset
        for ticker, asset in assets.items()
        if (asset.asset_type or "equity").strip().lower() == "equity"
    }
    return assets, equity_assets


def _csv_files_for_import(config: AppConfig, directory: Path | None = None) -> tuple[Path, ...]:
    if directory is not None:
        directory.mkdir(parents=True, exist_ok=True)
        paths = tuple(sorted(directory.glob("*.csv")))
        for path in paths:
            ensure_analyst_revision_source_export_header(path)
        return paths
    return ensure_revision_source_export_templates(config)


def import_revision_source_exports(
    config: AppConfig,
    directory: Path | None = None,
    path: Path | None = None,
) -> RevisionSourceImportResult:
    all_assets, equity_assets = _asset_maps(config)
    source_files = (path,) if path is not None else _csv_files_for_import(config, directory)
    if path is not None:
        ensure_analyst_revision_source_export_header(path)

    warnings: list[str] = []
    source_row_count = 0
    imported_count = 0
    skipped_count = 0
    imported_tickers: set[str] = set()

    for source_path in source_files:
        rows = parse_analyst_revision_source_export_csv(
            source_path.read_text(encoding="utf-8-sig")
        )
        source_row_count += len(rows)
        for source_row in rows:
            asset = all_assets.get(source_row.ticker)
            if asset and (asset.asset_type or "equity").strip().lower() == "etf":
                skipped_count += 1
                warnings.append(f"{source_row.ticker}:etf_revision_source_gated")
                continue
            if source_row.ticker not in equity_assets:
                skipped_count += 1
                warnings.append(f"{source_row.ticker}:inactive_or_unknown_equity")
                continue
            snapshot = _source_snapshot_from_row(source_row)
            upsert_analyst_revision_source_snapshot(config.database_path, snapshot)
            imported_count += 1
            imported_tickers.add(source_row.ticker)

    if source_row_count == 0:
        warnings.append("empty_revision_source_exports")

    return RevisionSourceImportResult(
        source_dir=directory or config.analyst_revision_source_exports_dir,
        source_files=tuple(source_files),
        source_row_count=source_row_count,
        imported_count=imported_count,
        skipped_count=skipped_count,
        tickers=tuple(sorted(imported_tickers)),
        warnings=tuple(dict.fromkeys(warnings)),
    )


def _weighted_median(values: list[tuple[float, float]]) -> float | None:
    if not values:
        return None
    ordered = sorted(values, key=lambda item: item[0])
    total_weight = sum(max(weight, 0.0) for _, weight in ordered)
    if total_weight <= 0:
        return ordered[len(ordered) // 2][0]
    midpoint = total_weight / 2.0
    running = 0.0
    for value, weight in ordered:
        running += max(weight, 0.0)
        if running >= midpoint:
            return value
    return ordered[-1][0]


def _join_unique(values: Iterable[str | None], separator: str = ", ") -> str | None:
    parts: list[str] = []
    for value in values:
        if not value:
            continue
        for part in str(value).split(","):
            cleaned = part.strip()
            if cleaned and cleaned not in parts:
                parts.append(cleaned)
    return separator.join(parts) if parts else None


def _field_weighted_value(
    snapshots: list[AnalystRevisionSourceSnapshot],
    field_name: str,
) -> tuple[float | None, float | None]:
    values = [
        (float(value), _source_weight(snapshot.source))
        for snapshot in snapshots
        for value in (getattr(snapshot, field_name),)
        if value is not None
    ]
    if not values:
        return None, None
    raw_values = [value for value, _ in values]
    spread = max(raw_values) - min(raw_values) if len(raw_values) > 1 else 0.0
    return _weighted_median(values), spread


def _snapshot_has_aggregate_value(snapshot: AnalystRevisionSourceSnapshot) -> bool:
    return any(getattr(snapshot, field) is not None for field in REVISION_OUTPUT_FIELDS)


def _snapshot_is_available(snapshot: AnalystRevisionSourceSnapshot) -> bool:
    status = (snapshot.provider_status or "ok").strip().lower()
    return status == "ok" and _snapshot_has_aggregate_value(snapshot)


def _aggregate_confidence(
    snapshots: list[AnalystRevisionSourceSnapshot],
    warnings: list[str],
) -> float:
    source_count = len({snapshot.source for snapshot in snapshots})
    average_source_confidence = (
        sum(snapshot.source_confidence or _source_confidence(snapshot.source) for snapshot in snapshots)
        / len(snapshots)
        if snapshots
        else 0.0
    )
    confidence = 35.0 + source_count * 12.0 + average_source_confidence * 0.35
    if "source_disagreement_medium" in warnings:
        confidence -= 7.0
    if "source_disagreement_high" in warnings:
        confidence -= 15.0
    if "single_source_only" in warnings:
        confidence -= 5.0
    if "missing_primary_api_source" in warnings:
        confidence -= 5.0
    if any(warning.startswith("source_unavailable:") for warning in warnings):
        confidence -= 5.0
    return max(0.0, min(100.0, confidence))


def _build_aggregate(
    config: AppConfig,
    ticker: str,
    signal_date: str,
    snapshots: list[AnalystRevisionSourceSnapshot],
) -> AnalystRevisionAggregate | None:
    if not snapshots:
        return None

    available_snapshots = [snapshot for snapshot in snapshots if _snapshot_is_available(snapshot)]
    unavailable_snapshots = [
        snapshot
        for snapshot in snapshots
        if (snapshot.provider_status or "ok").strip().lower() != "ok"
    ]
    if not available_snapshots:
        return None

    source_names = tuple(sorted({snapshot.source for snapshot in available_snapshots}))
    warnings: list[str] = []
    disagreement_parts: list[str] = []
    values: dict[str, float | None] = {}

    for field_name in REVISION_OUTPUT_FIELDS:
        value, spread = _field_weighted_value(available_snapshots, field_name)
        values[field_name] = value
        if spread is None:
            continue
        if spread >= config.signals_revision_high_disagreement_threshold:
            warnings.append("source_disagreement_high")
            disagreement_parts.append(f"{field_name}:{spread:.4f}")
        elif spread >= config.signals_revision_disagreement_warning_threshold:
            warnings.append("source_disagreement_medium")
            disagreement_parts.append(f"{field_name}:{spread:.4f}")

    analyst_count_value, _ = _field_weighted_value(available_snapshots, "analyst_count")
    analyst_count = int(round(analyst_count_value)) if analyst_count_value is not None else None

    if not any(values[field] is not None for field in REVISION_OUTPUT_FIELDS):
        return None
    if len(source_names) == 1:
        warnings.append("single_source_only")
    if len(source_names) < config.signals_revision_min_sources_for_aggregate:
        warnings.append("insufficient_sources_for_aggregate")
    if not any(_source_key(source) in PRIMARY_API_SOURCES for source in source_names):
        warnings.append("missing_primary_api_source")
    for snapshot in unavailable_snapshots:
        warnings.append(f"source_unavailable:{snapshot.source}")
        if snapshot.data_warnings:
            warnings.extend(part.strip() for part in snapshot.data_warnings.split(",") if part.strip())
    for snapshot in available_snapshots:
        if snapshot.data_warnings:
            warnings.extend(part.strip() for part in snapshot.data_warnings.split(",") if part.strip())

    source_urls = _join_unique((snapshot.source_url for snapshot in available_snapshots), separator="; ")
    notes = (
        f"Aggregated from {', '.join(source_names)} using "
        f"{config.signals_revision_source_policy}."
    )
    data_warnings = _join_unique(warnings)

    return AnalystRevisionAggregate(
        ticker=ticker,
        signal_date=signal_date,
        eps_revision_1m=values["eps_revision_1m"],
        eps_revision_3m=values["eps_revision_3m"],
        revenue_revision_1m=values["revenue_revision_1m"],
        revenue_revision_3m=values["revenue_revision_3m"],
        target_price_revision_3m=values["target_price_revision_3m"],
        recommendation_revision=values["recommendation_revision"],
        estimate_dispersion=values["estimate_dispersion"],
        analyst_count=analyst_count,
        source_count=len(source_names),
        sources=", ".join(source_names),
        source_policy=config.signals_revision_source_policy,
        aggregate_confidence=_aggregate_confidence(available_snapshots, warnings),
        source_disagreement=", ".join(disagreement_parts) if disagreement_parts else None,
        data_warnings=data_warnings,
        model_version=config.signals_analyst_revision_model_version,
        source="analyst_revision_aggregate",
        source_url=source_urls,
        notes=notes,
        as_of_date=date.today().isoformat(),
        effective_date=signal_date,
    )


def _export_aggregates_to_final_csv(config: AppConfig) -> int:
    aggregates = list_analyst_revision_aggregates(config.database_path)
    rows = [
        _revision_input_to_csv_row(_aggregate_to_revision_input(aggregate))
        for aggregate in sorted(
            aggregates,
            key=lambda row: (row.ticker, row.signal_date, row.source),
        )
    ]
    _write_final_revision_rows(config.analyst_revisions_path, rows)
    return len(rows)


def aggregate_revision_sources(
    config: AppConfig,
    ticker: str | None = None,
) -> RevisionAggregateResult:
    snapshots = list_analyst_revision_source_snapshots(config.database_path, ticker=ticker)
    wanted_ticker = normalize_ticker(ticker) if ticker else None
    grouped: dict[tuple[str, str], list[AnalystRevisionSourceSnapshot]] = {}
    for snapshot in snapshots:
        if wanted_ticker and snapshot.ticker != wanted_ticker:
            continue
        grouped.setdefault((snapshot.ticker, snapshot.signal_date), []).append(snapshot)

    aggregate_count = 0
    warnings: list[str] = []
    tickers: set[str] = set()
    for (group_ticker, signal_date), group_snapshots in sorted(grouped.items()):
        aggregate = _build_aggregate(config, group_ticker, signal_date, group_snapshots)
        if aggregate is None:
            delete_analyst_revision_aggregate(config.database_path, group_ticker, signal_date)
            warnings.append(f"{group_ticker}:no_aggregatable_revision_fields")
            continue
        upsert_analyst_revision_aggregate(config.database_path, aggregate)
        aggregate_count += 1
        tickers.add(group_ticker)
        if aggregate.data_warnings:
            warnings.extend(
                f"{group_ticker}:{part.strip()}"
                for part in aggregate.data_warnings.split(",")
                if part.strip()
            )

    if not grouped:
        warnings.append("no_revision_source_snapshots")

    written_count = _export_aggregates_to_final_csv(config)
    return RevisionAggregateResult(
        aggregate_count=aggregate_count,
        written_row_count=written_count,
        tickers=tuple(sorted(tickers)),
        warnings=tuple(dict.fromkeys(warnings)),
    )


def derive_analyst_revisions_from_source_export(
    config: AppConfig,
    path: Path | None = None,
) -> RevisionSourceDeriveResult:
    source_path = path or config.analyst_revision_source_export_path
    ensure_analyst_revision_source_export_header(source_path)
    source_rows = parse_analyst_revision_source_export_csv(
        source_path.read_text(encoding="utf-8-sig")
    )
    import_result = import_revision_source_exports(config, path=source_path)
    aggregate_result = aggregate_revision_sources(config)
    warnings = tuple(dict.fromkeys((*import_result.warnings, *aggregate_result.warnings)))
    return RevisionSourceDeriveResult(
        source_path=source_path,
        output_path=config.analyst_revisions_path,
        source_row_count=len(source_rows),
        derived_row_count=import_result.imported_count,
        written_row_count=aggregate_result.written_row_count,
        skipped_count=import_result.skipped_count,
        tickers=aggregate_result.tickers or import_result.tickers,
        warnings=warnings,
    )


def _active_equity_tickers(config: AppConfig, ticker: str | None = None) -> tuple[str, ...]:
    wanted = normalize_ticker(ticker) if ticker else None
    _, equity_assets = _asset_maps(config)
    return tuple(
        sorted(
            asset_ticker
            for asset_ticker in equity_assets
            if wanted is None or asset_ticker == wanted
        )
    )


def _http_json(url: str) -> object:
    request = Request(url, headers={"User-Agent": "TargetOpportunityMonitor/0.1"})
    with urlopen(request, timeout=HTTP_TIMEOUT_SECONDS) as response:
        return json.loads(response.read().decode("utf-8"))


def _first_number(payload: dict[str, object], keys: tuple[str, ...]) -> float | None:
    for key in keys:
        value = payload.get(key)
        if value in (None, ""):
            continue
        try:
            return float(value)
        except (TypeError, ValueError):
            continue
    return None


def _first_int(payload: dict[str, object], keys: tuple[str, ...]) -> int | None:
    value = _first_number(payload, keys)
    return int(round(value)) if value is not None else None


def _list_payload_rows(payload: object, keys: tuple[str, ...] = ()) -> list[dict[str, object]]:
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]
    if isinstance(payload, dict):
        for key in keys:
            value = payload.get(key)
            if isinstance(value, list):
                return [row for row in value if isinstance(row, dict)]
    return []


def _provider_payload_warning(
    provider: str,
    ticker: str,
    payload: dict[str, object],
) -> str | None:
    for key in (
        "Error Message",
        "Information",
        "Note",
        "Premium Information",
        "error",
        "message",
    ):
        value = payload.get(key)
        if not value:
            continue
        message = str(value).lower()
        if (
            "rate limit" in message
            or "spread" in message
            or "premium" in message
            or "access" in message
            or "forbidden" in message
        ):
            return f"{ticker}:{provider}_rate_limited_or_plan_limited"
        if "invalid api call" in message:
            return f"{ticker}:{provider}_invalid_api_call"
        return f"{ticker}:{provider}_provider_message"
    return None


def _store_provider_row(config: AppConfig, row: AnalystRevisionSourceRow) -> None:
    upsert_analyst_revision_source_snapshot(
        config.database_path,
        _source_snapshot_from_row(row),
    )


def _store_provider_failure(
    config: AppConfig,
    ticker: str,
    source: str,
    warning: str,
    source_url: str | None = None,
    capture_method: str = "api",
) -> None:
    upsert_analyst_revision_source_snapshot(
        config.database_path,
        AnalystRevisionSourceSnapshot(
            ticker=ticker,
            signal_date=date.today().isoformat(),
            source=source,
            source_url=source_url,
            notes=f"{source} unavailable for this fetch cycle.",
            capture_method=capture_method,
            provider_status="failed",
            source_confidence=0.0,
            data_warnings=warning,
            as_of_date=date.today().isoformat(),
            effective_date=date.today().isoformat(),
        ),
    )


def _store_provider_failures(
    config: AppConfig,
    tickers: tuple[str, ...],
    source: str,
    warning: str,
    source_url: str | None = None,
    capture_method: str = "api",
) -> None:
    for ticker in tickers:
        _store_provider_failure(
            config,
            ticker=ticker,
            source=source,
            warning=warning,
            source_url=source_url,
            capture_method=capture_method,
        )


def _fetch_fmp_rows(config: AppConfig, tickers: tuple[str, ...]) -> RevisionProviderFetchResult:
    key = _secret_env("FMP_API_KEY") or _secret_env("FINANCIAL_MODELING_PREP_API_KEY")
    warnings: list[str] = []
    if not key:
        _store_provider_failures(
            config,
            tickers,
            "fmp",
            "missing_fmp_api_key",
            "https://site.financialmodelingprep.com/developer/docs/analyst-estimates-api",
        )
        return RevisionProviderFetchResult(
            provider="fmp",
            fetched_count=0,
            stored_count=0,
            skipped_count=len(tickers),
            tickers=(),
            warnings=("missing_fmp_api_key",),
        )

    stored_tickers: set[str] = set()
    fetched_count = 0
    skipped_count = 0
    for ticker in tickers:
        query = urlencode({"symbol": ticker, "period": "annual", "apikey": key})
        url = f"https://financialmodelingprep.com/stable/analyst-estimates?{query}"
        try:
            payload = _http_json(url)
            rows = _list_payload_rows(payload)
            latest = rows[0] if rows else {}
            if not latest:
                skipped_count += 1
                warning = f"{ticker}:fmp_no_estimate_rows"
                warnings.append(warning)
                _store_provider_failure(
                    config,
                    ticker,
                    "fmp",
                    "fmp_no_estimate_rows",
                    "https://site.financialmodelingprep.com/developer/docs/analyst-estimates-api",
                )
                continue
            source_row = AnalystRevisionSourceRow(
                ticker=ticker,
                signal_date=date.today().isoformat(),
                source="fmp",
                source_url=(
                    "https://site.financialmodelingprep.com/developer/docs/"
                    "analyst-estimates-api"
                ),
                notes="FMP stable annual analyst-estimates API snapshot; only comparable fields are stored.",
                capture_method="api",
                eps_current=_first_number(
                    latest,
                    ("epsAvg", "estimatedEpsAvg", "epsEstimatedAvg", "epsEstimateAverage"),
                ),
                eps_high=_first_number(
                    latest,
                    ("epsHigh", "estimatedEpsHigh", "epsEstimatedHigh", "epsEstimateHigh"),
                ),
                eps_low=_first_number(
                    latest,
                    ("epsLow", "estimatedEpsLow", "epsEstimatedLow", "epsEstimateLow"),
                ),
                eps_average=_first_number(
                    latest,
                    ("epsAvg", "estimatedEpsAvg", "epsEstimatedAvg", "epsEstimateAverage"),
                ),
                analyst_count=_first_int(
                    latest,
                    (
                        "numAnalystsEps",
                        "numberAnalystEstimatedEps",
                        "numberAnalystsEstimatedEps",
                        "analystCount",
                    ),
                ),
                revenue_current=_first_number(
                    latest,
                    (
                        "revenueAvg",
                        "estimatedRevenueAvg",
                        "revenueEstimatedAvg",
                        "revenueEstimateAverage",
                    ),
                ),
            )
            if not _has_derivable_signal(source_row):
                skipped_count += 1
                warning = f"{ticker}:fmp_no_derivable_revision_fields"
                warnings.append(warning)
                _store_provider_failure(
                    config,
                    ticker,
                    "fmp",
                    "fmp_no_derivable_revision_fields",
                    "https://site.financialmodelingprep.com/developer/docs/analyst-estimates-api",
                )
                continue
            _store_provider_row(config, source_row)
            fetched_count += 1
            stored_tickers.add(ticker)
        except (HTTPError, URLError, TimeoutError, ValueError, json.JSONDecodeError) as error:
            skipped_count += 1
            warning = f"fmp_fetch_failed:{type(error).__name__}"
            warnings.append(f"{ticker}:{warning}")
            _store_provider_failure(
                config,
                ticker,
                "fmp",
                warning,
                "https://site.financialmodelingprep.com/developer/docs/analyst-estimates-api",
            )

    return RevisionProviderFetchResult(
        provider="fmp",
        fetched_count=fetched_count,
        stored_count=fetched_count,
        skipped_count=skipped_count,
        tickers=tuple(sorted(stored_tickers)),
        warnings=tuple(dict.fromkeys(warnings)),
    )


def _fetch_alpha_vantage_rows(
    config: AppConfig,
    tickers: tuple[str, ...],
) -> RevisionProviderFetchResult:
    key = _secret_env("ALPHAVANTAGE_API_KEY")
    warnings: list[str] = []
    if not key:
        _store_provider_failures(
            config,
            tickers,
            "alpha_vantage",
            "missing_alpha_vantage_api_key",
            "https://www.alphavantage.co/documentation/#earnings-estimates",
        )
        return RevisionProviderFetchResult(
            provider="alpha_vantage",
            fetched_count=0,
            stored_count=0,
            skipped_count=len(tickers),
            tickers=(),
            warnings=("missing_alpha_vantage_api_key",),
        )

    stored_tickers: set[str] = set()
    fetched_count = 0
    skipped_count = 0
    for index, ticker in enumerate(tickers):
        if index > 0:
            time.sleep(ALPHA_VANTAGE_REQUEST_DELAY_SECONDS)
        query = urlencode(
            {"function": "EARNINGS_ESTIMATES", "symbol": ticker, "apikey": key}
        )
        url = f"https://www.alphavantage.co/query?{query}"
        try:
            payload = _http_json(url)
            if not isinstance(payload, dict):
                skipped_count += 1
                warning = "alpha_vantage_unexpected_payload"
                warnings.append(f"{ticker}:{warning}")
                _store_provider_failure(
                    config,
                    ticker,
                    "alpha_vantage",
                    warning,
                    "https://www.alphavantage.co/documentation/#earnings-estimates",
                )
                continue
            provider_warning = _provider_payload_warning("alpha_vantage", ticker, payload)
            if provider_warning:
                skipped_count += 1
                warnings.append(provider_warning)
                _store_provider_failure(
                    config,
                    ticker,
                    "alpha_vantage",
                    provider_warning.split(":", 1)[1] if ":" in provider_warning else provider_warning,
                    "https://www.alphavantage.co/documentation/#earnings-estimates",
                )
                continue
            rows = _list_payload_rows(
                payload,
                (
                    "estimates",
                    "quarterlyEarningsEstimates",
                    "annualEarningsEstimates",
                ),
            )
            if not rows:
                skipped_count += 1
                warning = "alpha_vantage_no_estimate_rows"
                warnings.append(f"{ticker}:{warning}")
                _store_provider_failure(
                    config,
                    ticker,
                    "alpha_vantage",
                    warning,
                    "https://www.alphavantage.co/documentation/#earnings-estimates",
                )
                continue
            latest = rows[0]
            source_row = AnalystRevisionSourceRow(
                ticker=ticker,
                signal_date=date.today().isoformat(),
                source="alpha_vantage",
                source_url="https://www.alphavantage.co/documentation/#earnings-estimates",
                notes="Alpha Vantage earnings-estimates API snapshot; only comparable fields are stored.",
                capture_method="api",
                eps_current=_first_number(
                    latest,
                    (
                        "eps_estimate_average",
                        "epsEstimateAverage",
                        "estimatedEPSAvg",
                        "epsAvg",
                    ),
                ),
                eps_30d_ago=_first_number(
                    latest,
                    (
                        "eps_estimate_average_30_days_ago",
                        "epsEstimateAverage30DaysAgo",
                        "eps30DaysAgo",
                    ),
                ),
                eps_90d_ago=_first_number(
                    latest,
                    (
                        "eps_estimate_average_90_days_ago",
                        "epsEstimateAverage90DaysAgo",
                        "eps90DaysAgo",
                    ),
                ),
                eps_high=_first_number(
                    latest,
                    (
                        "eps_estimate_high",
                        "epsEstimateHigh",
                        "estimatedEPSHigh",
                        "epsHigh",
                    ),
                ),
                eps_low=_first_number(
                    latest,
                    (
                        "eps_estimate_low",
                        "epsEstimateLow",
                        "estimatedEPSLow",
                        "epsLow",
                    ),
                ),
                eps_average=_first_number(
                    latest,
                    (
                        "eps_estimate_average",
                        "epsEstimateAverage",
                        "estimatedEPSAvg",
                        "epsAvg",
                    ),
                ),
                analyst_count=_first_int(
                    latest,
                    (
                        "eps_estimate_analyst_count",
                        "numberOfAnalysts",
                        "analystCount",
                        "numberAnalysts",
                    ),
                ),
                revenue_current=_first_number(
                    latest,
                    (
                        "revenue_estimate_average",
                        "revenueEstimateAverage",
                        "revenueAvg",
                    ),
                ),
                revenue_30d_ago=_first_number(
                    latest,
                    (
                        "revenue_estimate_average_30_days_ago",
                        "revenueEstimateAverage30DaysAgo",
                    ),
                ),
                revenue_90d_ago=_first_number(
                    latest,
                    (
                        "revenue_estimate_average_90_days_ago",
                        "revenueEstimateAverage90DaysAgo",
                    ),
                ),
            )
            if not _has_derivable_signal(source_row):
                skipped_count += 1
                warning = "alpha_vantage_no_derivable_revision_fields"
                warnings.append(f"{ticker}:{warning}")
                _store_provider_failure(
                    config,
                    ticker,
                    "alpha_vantage",
                    warning,
                    "https://www.alphavantage.co/documentation/#earnings-estimates",
                )
                continue
            _store_provider_row(config, source_row)
            fetched_count += 1
            stored_tickers.add(ticker)
        except (HTTPError, URLError, TimeoutError, ValueError, json.JSONDecodeError) as error:
            skipped_count += 1
            warning = f"alpha_vantage_fetch_failed:{type(error).__name__}"
            warnings.append(f"{ticker}:{warning}")
            _store_provider_failure(
                config,
                ticker,
                "alpha_vantage",
                warning,
                "https://www.alphavantage.co/documentation/#earnings-estimates",
            )

    return RevisionProviderFetchResult(
        provider="alpha_vantage",
        fetched_count=fetched_count,
        stored_count=fetched_count,
        skipped_count=skipped_count,
        tickers=tuple(sorted(stored_tickers)),
        warnings=tuple(dict.fromkeys(warnings)),
    )


def _business_quant_groups(payload: object) -> list[dict[str, object]]:
    if not isinstance(payload, dict):
        return []
    groups = payload.get("data")
    if not isinstance(groups, list):
        return []
    return [group for group in groups if isinstance(group, dict)]


def _business_quant_estimate_rows(payload: object) -> list[dict[str, object]]:
    groups = _business_quant_groups(payload)
    ordered_groups = [
        *[group for group in groups if str(group.get("dimension", "")).lower() == "annual"],
        *[group for group in groups if str(group.get("dimension", "")).lower() != "annual"],
    ]
    for group in ordered_groups:
        estimates = group.get("estimates")
        if isinstance(estimates, list):
            rows = [row for row in estimates if isinstance(row, dict)]
            if rows:
                return rows
    return []


def _business_quant_latest_estimate(payload: object) -> dict[str, object] | None:
    rows = _business_quant_estimate_rows(payload)
    if not rows:
        return None

    estimate_rows = [
        row
        for row in rows
        if "estimate" in str(row.get("data_type", "")).lower()
        and _first_number(row, ("value_estimate", "high_estimate", "low_estimate")) is not None
    ]
    if estimate_rows:
        return sorted(
            estimate_rows,
            key=lambda row: (str(row.get("period", "")), str(row.get("sno", ""))),
        )[0]

    comparable_rows = [
        row
        for row in rows
        if _first_number(row, ("value_estimate", "high_estimate", "low_estimate")) is not None
    ]
    return comparable_rows[0] if comparable_rows else None


def _fetch_business_quant_rows(
    config: AppConfig,
    tickers: tuple[str, ...],
) -> RevisionProviderFetchResult:
    key = _secret_env("BUSINESSQUANT_API_KEY") or _secret_env("BUSINESS_QUANT_API_KEY")
    warnings: list[str] = []
    if not key:
        _store_provider_failures(
            config,
            tickers,
            "business_quant",
            "missing_business_quant_api_key",
            "https://businessquant.com/docs/api/estimates",
        )
        return RevisionProviderFetchResult(
            provider="business_quant",
            fetched_count=0,
            stored_count=0,
            skipped_count=len(tickers),
            tickers=(),
            warnings=("missing_business_quant_api_key",),
        )

    stored_tickers: set[str] = set()
    fetched_count = 0
    skipped_count = 0
    for ticker in tickers:
        try:
            base_query = {"ticker": ticker, "api_key": key}
            eps_payload = _http_json(
                "https://data.businessquant.com/estimates?"
                + urlencode({**base_query, "mode": "eps"})
            )
            revenue_payload = _http_json(
                "https://data.businessquant.com/estimates?"
                + urlencode({**base_query, "mode": "revenue"})
            )
            if isinstance(eps_payload, dict):
                provider_warning = _provider_payload_warning("business_quant", ticker, eps_payload)
                if provider_warning:
                    skipped_count += 1
                    warnings.append(provider_warning)
                    _store_provider_failure(
                        config,
                        ticker,
                        "business_quant",
                        provider_warning.split(":", 1)[1] if ":" in provider_warning else provider_warning,
                        "https://businessquant.com/docs/api/estimates",
                    )
                    continue
            if isinstance(revenue_payload, dict):
                provider_warning = _provider_payload_warning(
                    "business_quant",
                    ticker,
                    revenue_payload,
                )
                if provider_warning:
                    skipped_count += 1
                    warnings.append(provider_warning)
                    _store_provider_failure(
                        config,
                        ticker,
                        "business_quant",
                        provider_warning.split(":", 1)[1] if ":" in provider_warning else provider_warning,
                        "https://businessquant.com/docs/api/estimates",
                    )
                    continue

            eps_latest = _business_quant_latest_estimate(eps_payload)
            revenue_latest = _business_quant_latest_estimate(revenue_payload)
            if not eps_latest and not revenue_latest:
                skipped_count += 1
                warning = "business_quant_no_estimate_rows"
                warnings.append(f"{ticker}:{warning}")
                _store_provider_failure(
                    config,
                    ticker,
                    "business_quant",
                    warning,
                    "https://businessquant.com/docs/api/estimates",
                )
                continue

            source_row = AnalystRevisionSourceRow(
                ticker=ticker,
                signal_date=date.today().isoformat(),
                source="business_quant",
                source_url="https://businessquant.com/docs/api/estimates",
                notes=(
                    "Business Quant analyst-estimates API snapshot; current consensus "
                    "and dispersion fields are stored when available."
                ),
                capture_method="api",
                eps_current=_first_number(eps_latest or {}, ("value_estimate",)),
                eps_high=_first_number(eps_latest or {}, ("high_estimate",)),
                eps_low=_first_number(eps_latest or {}, ("low_estimate",)),
                eps_average=_first_number(eps_latest or {}, ("value_estimate",)),
                revenue_current=_first_number(revenue_latest or {}, ("value_estimate",)),
            )
            if not _has_derivable_signal(source_row):
                skipped_count += 1
                warning = "business_quant_no_derivable_revision_fields"
                warnings.append(f"{ticker}:{warning}")
                _store_provider_failure(
                    config,
                    ticker,
                    "business_quant",
                    warning,
                    "https://businessquant.com/docs/api/estimates",
                )
                continue
            _store_provider_row(config, source_row)
            fetched_count += 1
            stored_tickers.add(ticker)
        except (HTTPError, URLError, TimeoutError, ValueError, json.JSONDecodeError) as error:
            skipped_count += 1
            warning = f"business_quant_fetch_failed:{type(error).__name__}"
            warnings.append(f"{ticker}:{warning}")
            _store_provider_failure(
                config,
                ticker,
                "business_quant",
                warning,
                "https://businessquant.com/docs/api/estimates",
            )

    return RevisionProviderFetchResult(
        provider="business_quant",
        fetched_count=fetched_count,
        stored_count=fetched_count,
        skipped_count=skipped_count,
        tickers=tuple(sorted(stored_tickers)),
        warnings=tuple(dict.fromkeys(warnings)),
    )


def _parse_provider_date(value: object) -> date | None:
    try:
        return date.fromisoformat(str(value)[:10])
    except (TypeError, ValueError):
        return None


def _finnhub_recommendation_pair(
    rows: list[dict[str, object]],
) -> tuple[dict[str, object] | None, dict[str, object] | None]:
    dated_rows = [
        (parsed, row)
        for row in rows
        for parsed in (_parse_provider_date(row.get("period")),)
        if parsed is not None
    ]
    if not dated_rows:
        return (rows[0], rows[-1]) if len(rows) > 1 else ((rows[0], None) if rows else (None, None))

    dated_rows.sort(key=lambda item: item[0], reverse=True)
    latest_date, latest = dated_rows[0]
    target_prior = latest_date - timedelta(days=90)
    eligible = [item for item in dated_rows[1:] if item[0] <= latest_date - timedelta(days=45)]
    if eligible:
        prior = min(eligible, key=lambda item: abs((item[0] - target_prior).days))[1]
    elif len(dated_rows) > 1:
        prior = dated_rows[-1][1]
    else:
        prior = None
    return latest, prior


def _finnhub_recommendation_field(
    row: dict[str, object] | None,
    key: str,
) -> float | None:
    if row is None:
        return None
    return _first_number(row, (key,))


def _fetch_finnhub_rows(
    config: AppConfig,
    tickers: tuple[str, ...],
) -> RevisionProviderFetchResult:
    key = _secret_env("FINNHUB_API_KEY") or _secret_env("FINHUB_API_KEY")
    warnings: list[str] = []
    if not key:
        _store_provider_failures(
            config,
            tickers,
            "finnhub",
            "missing_finnhub_api_key",
            "https://finnhub.io/docs/api/recommendation-trends",
        )
        return RevisionProviderFetchResult(
            provider="finnhub",
            fetched_count=0,
            stored_count=0,
            skipped_count=len(tickers),
            tickers=(),
            warnings=("missing_finnhub_api_key",),
        )

    stored_tickers: set[str] = set()
    fetched_count = 0
    skipped_count = 0
    for ticker in tickers:
        query = urlencode({"symbol": ticker, "token": key})
        url = f"https://finnhub.io/api/v1/stock/recommendation?{query}"
        try:
            payload = _http_json(url)
            if isinstance(payload, dict):
                provider_warning = _provider_payload_warning("finnhub", ticker, payload)
                if provider_warning:
                    skipped_count += 1
                    warnings.append(provider_warning)
                    _store_provider_failure(
                        config,
                        ticker,
                        "finnhub",
                        provider_warning.split(":", 1)[1] if ":" in provider_warning else provider_warning,
                        "https://finnhub.io/docs/api/recommendation-trends",
                    )
                    continue
            rows = _list_payload_rows(payload)
            latest, prior = _finnhub_recommendation_pair(rows)
            if latest is None or prior is None:
                skipped_count += 1
                warning = "finnhub_insufficient_recommendation_history"
                warnings.append(f"{ticker}:{warning}")
                _store_provider_failure(
                    config,
                    ticker,
                    "finnhub",
                    warning,
                    "https://finnhub.io/docs/api/recommendation-trends",
                )
                continue

            source_row = AnalystRevisionSourceRow(
                ticker=ticker,
                signal_date=date.today().isoformat(),
                source="finnhub",
                source_url="https://finnhub.io/docs/api/recommendation-trends",
                notes=(
                    "Finnhub recommendation-trend API snapshot. This adapter uses "
                    "recommendation counts only; estimate and price-target endpoints "
                    "may require a different Finnhub plan."
                ),
                capture_method="api",
                recommendation_current_strong_buy=_finnhub_recommendation_field(
                    latest,
                    "strongBuy",
                ),
                recommendation_current_buy=_finnhub_recommendation_field(latest, "buy"),
                recommendation_current_hold=_finnhub_recommendation_field(latest, "hold"),
                recommendation_current_sell=_finnhub_recommendation_field(latest, "sell"),
                recommendation_current_strong_sell=_finnhub_recommendation_field(
                    latest,
                    "strongSell",
                ),
                recommendation_90d_ago_strong_buy=_finnhub_recommendation_field(
                    prior,
                    "strongBuy",
                ),
                recommendation_90d_ago_buy=_finnhub_recommendation_field(prior, "buy"),
                recommendation_90d_ago_hold=_finnhub_recommendation_field(prior, "hold"),
                recommendation_90d_ago_sell=_finnhub_recommendation_field(prior, "sell"),
                recommendation_90d_ago_strong_sell=_finnhub_recommendation_field(
                    prior,
                    "strongSell",
                ),
            )
            if not _has_derivable_signal(source_row):
                skipped_count += 1
                warning = "finnhub_no_derivable_revision_fields"
                warnings.append(f"{ticker}:{warning}")
                _store_provider_failure(
                    config,
                    ticker,
                    "finnhub",
                    warning,
                    "https://finnhub.io/docs/api/recommendation-trends",
                )
                continue
            _store_provider_row(config, source_row)
            fetched_count += 1
            stored_tickers.add(ticker)
        except (HTTPError, URLError, TimeoutError, ValueError, json.JSONDecodeError) as error:
            skipped_count += 1
            warning = f"finnhub_fetch_failed:{type(error).__name__}"
            warnings.append(f"{ticker}:{warning}")
            _store_provider_failure(
                config,
                ticker,
                "finnhub",
                warning,
                "https://finnhub.io/docs/api/recommendation-trends",
            )

    return RevisionProviderFetchResult(
        provider="finnhub",
        fetched_count=fetched_count,
        stored_count=fetched_count,
        skipped_count=skipped_count,
        tickers=tuple(sorted(stored_tickers)),
        warnings=tuple(dict.fromkeys(warnings)),
    )


def _value_from_yfinance_table(table: object, row_key: str, column_key: str) -> float | None:
    try:
        value = table.loc[row_key, column_key]  # type: ignore[attr-defined]
    except Exception:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _value_from_yfinance_table_any(
    table: object,
    row_keys: tuple[str, ...],
    column_key: str,
) -> float | None:
    for row_key in row_keys:
        value = _value_from_yfinance_table(table, row_key, column_key)
        if value is not None:
            return value
    return None


def _fetch_yfinance_rows(config: AppConfig, tickers: tuple[str, ...]) -> RevisionProviderFetchResult:
    try:
        import yfinance as yf  # type: ignore[import-not-found]
    except Exception:
        _store_provider_failures(
            config,
            tickers,
            "yfinance",
            "yfinance_not_installed",
            None,
            capture_method="optional_api",
        )
        return RevisionProviderFetchResult(
            provider="yfinance",
            fetched_count=0,
            stored_count=0,
            skipped_count=len(tickers),
            tickers=(),
            warnings=("yfinance_not_installed",),
        )

    try:
        cache_dir = Path(tempfile.gettempdir()) / "tom_yfinance_cache"
        cache_dir.mkdir(parents=True, exist_ok=True)
        if hasattr(yf, "set_tz_cache_location"):
            yf.set_tz_cache_location(str(cache_dir))
    except Exception:
        pass

    warnings: list[str] = []
    stored_tickers: set[str] = set()
    fetched_count = 0
    skipped_count = 0
    for ticker in tickers:
        try:
            yf_ticker = yf.Ticker(ticker)
            trend = yf_ticker.get_eps_trend()
            source_row = AnalystRevisionSourceRow(
                ticker=ticker,
                signal_date=date.today().isoformat(),
                source="yfinance",
                source_url=f"https://finance.yahoo.com/quote/{ticker}/analysis/",
                notes="yfinance EPS trend snapshot from Yahoo Finance Analysis data.",
                capture_method="optional_api",
                eps_current=_value_from_yfinance_table_any(trend, ("0q", "0y"), "current"),
                eps_30d_ago=_value_from_yfinance_table_any(trend, ("0q", "0y"), "30daysAgo"),
                eps_90d_ago=_value_from_yfinance_table_any(trend, ("0q", "0y"), "90daysAgo"),
            )
            if not _has_derivable_signal(source_row):
                skipped_count += 1
                warning = "yfinance_no_derivable_revision_fields"
                warnings.append(f"{ticker}:{warning}")
                _store_provider_failure(
                    config,
                    ticker,
                    "yfinance",
                    warning,
                    f"https://finance.yahoo.com/quote/{ticker}/analysis/",
                    capture_method="optional_api",
                )
                continue
            _store_provider_row(config, source_row)
            fetched_count += 1
            stored_tickers.add(ticker)
        except Exception as error:
            skipped_count += 1
            warning = f"yfinance_fetch_failed:{type(error).__name__}"
            warnings.append(f"{ticker}:{warning}")
            _store_provider_failure(
                config,
                ticker,
                "yfinance",
                warning,
                f"https://finance.yahoo.com/quote/{ticker}/analysis/",
                capture_method="optional_api",
            )

    return RevisionProviderFetchResult(
        provider="yfinance",
        fetched_count=fetched_count,
        stored_count=fetched_count,
        skipped_count=skipped_count,
        tickers=tuple(sorted(stored_tickers)),
        warnings=tuple(dict.fromkeys(warnings)),
    )


def _fetch_ibkr_rows(config: AppConfig, tickers: tuple[str, ...]) -> RevisionProviderFetchResult:
    return RevisionProviderFetchResult(
        provider="ibkr",
        fetched_count=0,
        stored_count=0,
        skipped_count=len(tickers),
        tickers=(),
        warnings=("ibkr_revision_import_not_implemented",),
    )


def fetch_revision_sources(
    config: AppConfig,
    provider: str = "all",
    ticker: str | None = None,
) -> RevisionProviderFetchResult:
    provider_key = provider.strip().lower()
    tickers = _active_equity_tickers(config, ticker=ticker)
    if provider_key == "google_finance":
        return RevisionProviderFetchResult(
            provider="google_finance",
            fetched_count=0,
            stored_count=0,
            skipped_count=len(tickers),
            tickers=(),
            warnings=("google_finance_analyst_revisions_unsupported",),
        )
    if provider_key == "all":
        providers = tuple(
            item
            for item in config.signals_revision_provider_order
            if item in config.signals_revision_enabled_providers
            and item not in {"source_export", "google_finance"}
        )
        results = [fetch_revision_sources(config, provider=item, ticker=ticker) for item in providers]
        return RevisionProviderFetchResult(
            provider="all",
            fetched_count=sum(result.fetched_count for result in results),
            stored_count=sum(result.stored_count for result in results),
            skipped_count=sum(result.skipped_count for result in results),
            tickers=tuple(sorted({ticker for result in results for ticker in result.tickers})),
            warnings=tuple(
                dict.fromkeys(
                    warning for result in results for warning in result.warnings
                )
            ),
        )
    if provider_key == "fmp":
        return _fetch_fmp_rows(config, tickers)
    if provider_key == "alpha_vantage":
        return _fetch_alpha_vantage_rows(config, tickers)
    if provider_key in {"business_quant", "businessquant"}:
        return _fetch_business_quant_rows(config, tickers)
    if provider_key in {"finnhub", "finhub"}:
        return _fetch_finnhub_rows(config, tickers)
    if provider_key in {"yfinance", "yahoo_finance"}:
        return _fetch_yfinance_rows(config, tickers)
    if provider_key == "ibkr":
        return _fetch_ibkr_rows(config, tickers)
    return RevisionProviderFetchResult(
        provider=provider_key,
        fetched_count=0,
        stored_count=0,
        skipped_count=len(tickers),
        tickers=(),
        warnings=(f"unsupported_revision_provider:{provider_key}",),
    )


def revision_provider_statuses(config: AppConfig) -> tuple[RevisionProviderStatus, ...]:
    enabled = set(config.signals_revision_enabled_providers)
    fmp_key_available = bool(
        _secret_env("FMP_API_KEY") or _secret_env("FINANCIAL_MODELING_PREP_API_KEY")
    )
    alpha_key_available = bool(_secret_env("ALPHAVANTAGE_API_KEY"))
    business_quant_key_available = bool(
        _secret_env("BUSINESSQUANT_API_KEY") or _secret_env("BUSINESS_QUANT_API_KEY")
    )
    finnhub_key_available = bool(_secret_env("FINNHUB_API_KEY") or _secret_env("FINHUB_API_KEY"))
    statuses = [
        RevisionProviderStatus(
            provider="fmp",
            enabled="fmp" in enabled,
            available=fmp_key_available,
            status="configured" if fmp_key_available else "missing_key",
            details=(
                "Reads FMP_API_KEY or FINANCIAL_MODELING_PREP_API_KEY from "
                "process env, with Windows user/machine env fallback."
            ),
        ),
        RevisionProviderStatus(
            provider="alpha_vantage",
            enabled="alpha_vantage" in enabled,
            available=alpha_key_available,
            status="configured" if alpha_key_available else "missing_key",
            details=(
                "Reads ALPHAVANTAGE_API_KEY from process env, with Windows "
                "user/machine env fallback."
            ),
        ),
        RevisionProviderStatus(
            provider="business_quant",
            enabled="business_quant" in enabled,
            available=business_quant_key_available,
            status="configured" if business_quant_key_available else "missing_key",
            details=(
                "Reads BUSINESSQUANT_API_KEY or BUSINESS_QUANT_API_KEY from "
                "process env, with Windows user/machine env fallback."
            ),
        ),
        RevisionProviderStatus(
            provider="finnhub",
            enabled="finnhub" in enabled,
            available=finnhub_key_available,
            status="configured" if finnhub_key_available else "missing_key",
            details=(
                "Reads FINNHUB_API_KEY or FINHUB_API_KEY from process env, "
                "with Windows user/machine env fallback. Current adapter uses "
                "recommendation trends."
            ),
        ),
        RevisionProviderStatus(
            provider="yfinance",
            enabled="yfinance" in enabled,
            available=_yfinance_available(),
            status="available" if _yfinance_available() else "optional_package_missing",
            details="Optional unofficial Yahoo Finance adapter; not required for the pipeline.",
        ),
        RevisionProviderStatus(
            provider="ibkr",
            enabled="ibkr" in enabled,
            available=False,
            status="not_implemented",
            details="IBKR revision import remains a non-blocking future adapter.",
        ),
        RevisionProviderStatus(
            provider="source_export",
            enabled="source_export" in enabled,
            available=True,
            status="available",
            details="Audited CSV workflow for SecBot, TECHi, RedMatter, Morningstar, GuruFocus, and user exports.",
        ),
        RevisionProviderStatus(
            provider="google_finance",
            enabled=False,
            available=False,
            status="unsupported",
            details="Google Finance does not expose comparable analyst revision fields.",
        ),
    ]
    return tuple(statuses)


def _yfinance_available() -> bool:
    try:
        __import__("yfinance")
        return True
    except Exception:
        return False


def _read_final_revision_rows(path: Path) -> list[dict[str, str]]:
    ensure_analyst_revision_csv_header(path)
    reader = csv.DictReader(path.read_text(encoding="utf-8-sig").splitlines())
    return [
        {header: (row.get(header) or "") for header in ANALYST_REVISION_HEADERS}
        for row in reader
        if any((value or "").strip() for value in row.values())
    ]


def _final_rows_by_ticker(config: AppConfig) -> dict[str, list[dict[str, str]]]:
    if not config.analyst_revisions_path.exists():
        return {}
    rows = _read_final_revision_rows(config.analyst_revisions_path)
    by_ticker: dict[str, list[dict[str, str]]] = {}
    for row in rows:
        ticker = normalize_ticker(row.get("ticker", ""))
        if ticker:
            by_ticker.setdefault(ticker, []).append(row)
    return by_ticker


def _aggregate_rows_by_ticker(config: AppConfig) -> dict[str, list[AnalystRevisionAggregate]]:
    try:
        rows = list_analyst_revision_aggregates(config.database_path)
    except sqlite3.Error:
        return {}
    by_ticker: dict[str, list[AnalystRevisionAggregate]] = {}
    for row in rows:
        by_ticker.setdefault(row.ticker, []).append(row)
    return by_ticker


def _row_has_source_fields(row: dict[str, str]) -> bool:
    return bool(row.get("source_url", "").strip() and row.get("notes", "").strip())


def _row_has_numeric_signal(row: dict[str, str]) -> bool:
    return any((row.get(field) or "").strip() for field in REVISION_OUTPUT_FIELDS)


def _latest_final_row(rows: list[dict[str, str]]) -> dict[str, str]:
    return max(rows, key=lambda row: (row.get("signal_date", ""), row.get("source", "")))


def _latest_aggregate(rows: list[AnalystRevisionAggregate]) -> AnalystRevisionAggregate:
    return max(rows, key=lambda row: (row.signal_date, row.source))


def _is_stale(signal_date: str | None, stale_after_days: int) -> bool:
    if not signal_date:
        return False
    try:
        parsed = date.fromisoformat(signal_date)
    except ValueError:
        return True
    return (date.today() - parsed).days > stale_after_days


def _skipped_source_etfs(config: AppConfig, all_assets: dict[str, Asset]) -> tuple[str, ...]:
    skipped: list[str] = []
    for source_file in _csv_files_for_import(config):
        try:
            rows = parse_analyst_revision_source_export_csv(
                source_file.read_text(encoding="utf-8-sig")
            )
        except ValueError:
            continue
        skipped.extend(
            row.ticker
            for row in rows
            if row.ticker in all_assets
            and (all_assets[row.ticker].asset_type or "equity").strip().lower() == "etf"
        )
    return tuple(sorted(set(skipped)))


def revision_source_status_report(config: AppConfig) -> RevisionSourceStatusReport:
    all_assets, equity_assets = _asset_maps(config)
    rows_by_ticker = _final_rows_by_ticker(config)
    aggregates_by_ticker = _aggregate_rows_by_ticker(config)
    evidence = build_revision_evidence(config)
    statuses: list[RevisionSourceTickerStatus] = []
    source_backed_tickers: list[str] = []
    missing_source_tickers: list[str] = []
    stale_tickers: list[str] = []
    missing_source_field_tickers: list[str] = []

    for ticker, asset in sorted(equity_assets.items()):
        aggregate_rows = aggregates_by_ticker.get(ticker, [])
        final_rows = rows_by_ticker.get(ticker, [])
        latest_aggregate = _latest_aggregate(aggregate_rows) if aggregate_rows else None
        latest_final = None
        if not latest_aggregate:
            source_rows = [
                row for row in final_rows if _row_has_source_fields(row) and _row_has_numeric_signal(row)
            ]
            latest_final = _latest_final_row(source_rows) if source_rows else None

        warnings: list[str] = []
        if latest_aggregate is not None:
            source_backed_tickers.append(ticker)
            if latest_aggregate.data_warnings:
                warnings.extend(
                    part.strip()
                    for part in latest_aggregate.data_warnings.split(",")
                    if part.strip()
                )
            signal_date = latest_aggregate.signal_date
            source = latest_aggregate.sources or latest_aggregate.source
            source_count = latest_aggregate.source_count
            aggregate_confidence = latest_aggregate.aggregate_confidence
            source_disagreement = latest_aggregate.source_disagreement
        elif latest_final is not None:
            source_backed_tickers.append(ticker)
            signal_date = latest_final.get("signal_date")
            source = latest_final.get("source")
            source_count = 1
            aggregate_confidence = None
            source_disagreement = None
        else:
            missing_source_tickers.append(ticker)
            warnings.append("missing_source_backed_revision_row")
            signal_date = None
            source = None
            source_count = 0
            aggregate_confidence = None
            source_disagreement = None

        if any(not _row_has_source_fields(row) for row in final_rows):
            missing_source_field_tickers.append(ticker)
            warnings.append("missing_source_url_or_notes")
        stale = _is_stale(signal_date, config.signals_stale_after_days)
        if stale:
            stale_tickers.append(ticker)
            warnings.append("stale_revision_source_row")
        statuses.append(
            RevisionSourceTickerStatus(
                ticker=ticker,
                asset_type=(asset.asset_type or "equity"),
                source_backed=signal_date is not None,
                signal_date=signal_date,
                source=source,
                stale=stale,
                warnings=tuple(dict.fromkeys(warnings)),
                source_count=source_count,
                aggregate_confidence=aggregate_confidence,
                source_disagreement=source_disagreement,
            )
        )

    skipped_etfs = _skipped_source_etfs(config, all_assets)
    warnings: list[str] = []
    if missing_source_tickers:
        warnings.append("missing_source_backed_revision_rows")
    if stale_tickers:
        warnings.append("stale_revision_source_rows")
    if missing_source_field_tickers:
        warnings.append("missing_source_url_or_notes")
    if skipped_etfs:
        warnings.append("etf_revision_source_gated")

    try:
        source_snapshot_count = len(list_analyst_revision_source_snapshots(config.database_path))
        aggregate_count = len(list_analyst_revision_aggregates(config.database_path))
    except sqlite3.Error:
        source_snapshot_count = 0
        aggregate_count = 0

    return RevisionSourceStatusReport(
        source_export_path=config.analyst_revision_source_export_path,
        source_export_exists=config.analyst_revision_source_export_path.exists(),
        source_exports_dir=config.analyst_revision_source_exports_dir,
        source_snapshot_count=source_snapshot_count,
        aggregate_count=aggregate_count,
        analyst_revisions_path=config.analyst_revisions_path,
        analyst_revisions_exists=config.analyst_revisions_path.exists(),
        active_equity_count=len(equity_assets),
        source_backed_ticker_count=len(source_backed_tickers),
        source_backed_tickers=tuple(sorted(source_backed_tickers)),
        missing_source_tickers=tuple(sorted(missing_source_tickers)),
        stale_tickers=tuple(sorted(stale_tickers)),
        skipped_etf_tickers=skipped_etfs,
        missing_source_field_tickers=tuple(sorted(set(missing_source_field_tickers))),
        evidence_decision=evidence.decision,
        statuses=tuple(statuses),
        warnings=tuple(dict.fromkeys(warnings)),
    )


def build_revision_source_status_text(config: AppConfig) -> str:
    report = revision_source_status_report(config)
    lines = [
        "Analyst Revision Source Status",
        "",
        f"Source export: {report.source_export_path}",
        f"Source export exists: {report.source_export_exists}",
        f"Source export directory: {report.source_exports_dir}",
        f"Source snapshot rows: {report.source_snapshot_count}",
        f"Aggregate rows: {report.aggregate_count}",
        f"Derived analyst revisions: {report.analyst_revisions_path}",
        f"Derived analyst revisions exists: {report.analyst_revisions_exists}",
        (
            "Source-backed ticker coverage: "
            f"{report.source_backed_ticker_count}/{report.active_equity_count}"
        ),
        f"Source-backed tickers: {', '.join(report.source_backed_tickers) or 'none'}",
        f"Missing source-backed tickers: {', '.join(report.missing_source_tickers) or 'none'}",
        f"Stale source-backed tickers: {', '.join(report.stale_tickers) or 'none'}",
        f"Skipped ETF source rows: {', '.join(report.skipped_etf_tickers) or 'none'}",
        (
            "Missing source fields: "
            f"{', '.join(report.missing_source_field_tickers) or 'none'}"
        ),
        f"Revision evidence decision: {report.evidence_decision}",
        f"Warnings: {', '.join(report.warnings) if report.warnings else 'none'}",
        "",
        (
            "Ticker | Type | Source Backed | Signal Date | Source | "
            "Source Count | Confidence | Disagreement | Stale | Warnings"
        ),
    ]
    for status in report.statuses:
        lines.append(
            " | ".join(
                (
                    status.ticker,
                    status.asset_type,
                    str(status.source_backed),
                    status.signal_date or "",
                    status.source or "",
                    str(status.source_count),
                    f"{status.aggregate_confidence:.2f}"
                    if status.aggregate_confidence is not None
                    else "",
                    status.source_disagreement or "",
                    str(status.stale),
                    ", ".join(status.warnings),
                )
            )
        )
    return "\n".join(lines)


def build_revision_provider_status_text(config: AppConfig) -> str:
    lines = [
        "Analyst Revision Provider Status",
        "",
        f"Provider order: {', '.join(config.signals_revision_provider_order)}",
        f"Enabled providers: {', '.join(config.signals_revision_enabled_providers)}",
        f"Source policy: {config.signals_revision_source_policy}",
        "",
        "Provider | Enabled | Available | Status | Details",
    ]
    for status in revision_provider_statuses(config):
        lines.append(
            " | ".join(
                (
                    status.provider,
                    str(status.enabled),
                    str(status.available),
                    status.status,
                    status.details,
                )
            )
        )
    return "\n".join(lines)
