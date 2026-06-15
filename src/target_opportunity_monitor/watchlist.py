from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

from .storage import Asset, normalize_asset_role, normalize_ticker, upsert_asset


WATCHLIST_COLUMNS = (
    "ticker",
    "name",
    "asset_type",
    "exchange",
    "currency",
    "sector",
    "industry",
    "country",
    "active",
    "asset_role",
)


@dataclass(frozen=True)
class WatchlistLoadResult:
    path: Path
    loaded_count: int
    tickers: tuple[str, ...]


def _clean_cell(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned if cleaned else None


def _active_flag(value: str | None) -> int:
    cleaned = (value or "").strip().lower()
    if cleaned in {"0", "false", "no", "n", "inactive", "disabled"}:
        return 0
    return 1


def read_watchlist(path: Path) -> list[Asset]:
    with path.open("r", encoding="utf-8-sig", newline="") as watchlist_file:
        reader = csv.DictReader(watchlist_file)
        if reader.fieldnames is None:
            raise ValueError("Watchlist CSV is missing a header row.")

        fieldnames = {field.strip() for field in reader.fieldnames if field}
        if "ticker" not in fieldnames:
            raise ValueError("Watchlist CSV must include a 'ticker' column.")

        assets: list[Asset] = []
        for row in reader:
            ticker_value = _clean_cell(row.get("ticker"))
            if not ticker_value:
                continue

            assets.append(
                Asset(
                    ticker=normalize_ticker(ticker_value),
                    name=_clean_cell(row.get("name")),
                    asset_type=_clean_cell(row.get("asset_type")) or "equity",
                    exchange=_clean_cell(row.get("exchange")),
                    currency=_clean_cell(row.get("currency")) or "USD",
                    sector=_clean_cell(row.get("sector")),
                    industry=_clean_cell(row.get("industry")),
                    country=_clean_cell(row.get("country")) or "US",
                    active_flag=_active_flag(row.get("active")),
                    asset_role=normalize_asset_role(row.get("asset_role")),
                    source="manual",
                )
            )

    return assets


def load_watchlist(database_path: Path, watchlist_path: Path) -> WatchlistLoadResult:
    assets = read_watchlist(watchlist_path)
    for asset in assets:
        upsert_asset(database_path, asset)
    return WatchlistLoadResult(
        path=watchlist_path,
        loaded_count=len(assets),
        tickers=tuple(asset.ticker for asset in assets),
    )


def _read_watchlist_rows(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    if not path.exists():
        return list(WATCHLIST_COLUMNS), []
    with path.open("r", encoding="utf-8-sig", newline="") as watchlist_file:
        reader = csv.DictReader(watchlist_file)
        fieldnames = list(reader.fieldnames or [])
        rows = [dict(row) for row in reader]
    return fieldnames, rows


def _write_watchlist_rows(
    path: Path,
    fieldnames: list[str],
    rows: list[dict[str, str]],
) -> None:
    final_fieldnames = list(fieldnames)
    for column in WATCHLIST_COLUMNS:
        if column not in final_fieldnames:
            final_fieldnames.append(column)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as watchlist_file:
        writer = csv.DictWriter(watchlist_file, fieldnames=final_fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({column: row.get(column, "") for column in final_fieldnames})


def upsert_watchlist_asset(path: Path, asset: Asset) -> None:
    fieldnames, rows = _read_watchlist_rows(path)
    normalized = normalize_ticker(asset.ticker)
    updated = False
    payload = {
        "ticker": normalized,
        "name": asset.name or "",
        "asset_type": asset.asset_type or "equity",
        "exchange": asset.exchange or "",
        "currency": asset.currency or "USD",
        "sector": asset.sector or "",
        "industry": asset.industry or "",
        "country": asset.country or "US",
        "active": "1" if asset.active_flag == 1 else "0",
        "asset_role": normalize_asset_role(asset.asset_role),
    }
    for row in rows:
        if normalize_ticker(row.get("ticker", "")) == normalized:
            row.update(payload)
            updated = True
            break
    if not updated:
        rows.append(payload)
    _write_watchlist_rows(path, fieldnames, rows)


def set_watchlist_active(path: Path, ticker: str, active: bool) -> bool:
    fieldnames, rows = _read_watchlist_rows(path)
    normalized = normalize_ticker(ticker)
    changed = False
    for row in rows:
        if normalize_ticker(row.get("ticker", "")) == normalized:
            row["active"] = "1" if active else "0"
            changed = True
            break
    if changed:
        _write_watchlist_rows(path, fieldnames, rows)
    return changed
