from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from io import StringIO
import json
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .config import AppConfig
from .storage import (
    Asset,
    ShortInterestSourceSnapshot,
    Signal,
    SignalOutcomeStatus,
    SignalStatus,
    insert_data_quality_check,
    is_scoreable_asset,
    latest_price_feature,
    latest_short_interest_settlement_date,
    list_assets,
    list_short_interest_source_snapshots,
    normalize_ticker,
    signal_outcome_statuses,
    signal_statuses_for_family,
    upsert_short_interest_source_snapshot,
    upsert_signal,
)


SHORT_INTEREST_HEADERS = (
    "ticker",
    "settlement_date",
    "publication_date",
    "short_interest",
    "float_shares",
    "percent_float",
    "average_daily_volume",
    "days_to_cover",
    "source",
    "source_url",
    "notes",
    "as_of_date",
    "effective_date",
)
SHORT_INTEREST_SOURCE_EXPORT_HEADERS = SHORT_INTEREST_HEADERS + ("capture_method",)
SHORT_INTEREST_SOURCE_EXPORT_DIR = Path("data") / "signals" / "source_exports" / "short_interest"
SHORT_INTEREST_BACKFILL_TEMPLATE = "missing_short_interest_backfill.csv"
SHORT_INTEREST_MISSING_PROVIDER_TEMPLATE = "missing_provider_short_interest_backfill.csv"
SHORT_INTEREST_DEFAULT_SOURCE_EXPORTS = (
    "provider_export.csv",
    "exchange_manual.csv",
    "broker_manual.csv",
)
SHORT_INTEREST_PROVIDER_EXPORT_FILE = "provider_export.csv"
SHORT_INTEREST_FETCH_PROVIDERS = {"finra", "nasdaq_trader"}
SHORT_INTEREST_EXPORT_NORMALIZATION_PROVIDERS = {
    "finra",
    "nasdaq_trader",
    "nyse",
    "broker",
    "generic",
}
SHORT_INTEREST_PROVIDER_SOURCES = {
    "finra": "finra_official",
    "nasdaq_trader": "nasdaq_trader_official",
    "nyse": "nyse_manual",
    "broker": "broker_export",
    "generic": "provider_export",
}
FINRA_SHORT_INTEREST_ENDPOINT = (
    "https://api.finra.org/data/group/otcMarket/name/EquityShortInterestJSON"
)
FINRA_SHORT_INTEREST_SOURCE_URL = (
    "https://www.finra.org/finra-data/browse-catalog/equity-short-interest/data"
)
NASDAQ_SHORT_INTEREST_SOURCE_URL = "https://nasdaqtrader.com/trader.aspx?id=ShortInterest"
NASDAQ_SHORT_INTEREST_ENDPOINT_TEMPLATE = (
    "https://api.nasdaq.com/api/quote/{ticker}/short-interest?assetclass=stocks"
)
REQUIRED_COLUMNS = {"ticker", "settlement_date", "source", "source_url"}
NUMERIC_FIELDS = {
    "short_interest",
    "float_shares",
    "percent_float",
    "average_daily_volume",
    "days_to_cover",
}
SIGNAL_FAMILY = "short_interest"
COMPOSITE_SIGNAL_NAME = "short_interest.composite"
LEVEL_SIGNAL_NAME = "short_interest.level"
DAYS_TO_COVER_SIGNAL_NAME = "short_interest.days_to_cover"
CHANGE_SIGNAL_NAME = "short_interest.change"
SQUEEZE_SIGNAL_NAME = "short_interest.squeeze_setup"


@dataclass(frozen=True)
class ShortInterestInput:
    ticker: str
    settlement_date: str
    source: str
    source_url: str
    publication_date: str | None = None
    short_interest: float | None = None
    float_shares: float | None = None
    percent_float: float | None = None
    average_daily_volume: float | None = None
    days_to_cover: float | None = None
    notes: str | None = None
    as_of_date: str | None = None
    effective_date: str | None = None
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class ShortInterestLoadResult:
    path: Path
    row_count: int
    loaded_count: int
    skipped_count: int
    tickers: tuple[str, ...]
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class ShortInterestTickerResult:
    ticker: str
    status: str
    asset_type: str
    composite_score: float | None
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class ShortInterestUpdateResult:
    results: tuple[ShortInterestTickerResult, ...]
    load_result: ShortInterestLoadResult | None = None

    @property
    def computed_count(self) -> int:
        return sum(1 for result in self.results if result.status == "computed")

    @property
    def skipped_count(self) -> int:
        return sum(1 for result in self.results if result.status == "skipped")

    @property
    def warning_count(self) -> int:
        return sum(1 for result in self.results if result.warnings)


@dataclass(frozen=True)
class ShortInterestSourceTickerStatus:
    ticker: str
    asset_type: str
    status: str
    source_backed: bool
    source_row_count: int
    latest_settlement_date: str | None
    latest_publication_date: str | None
    percent_float: float | None
    days_to_cover: float | None
    change_pct: float | None
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class ShortInterestSourceStatusReport:
    active_equity_count: int
    source_backed_ticker_count: int
    source_snapshot_count: int
    latest_settlement_date: str | None
    source_backed_tickers: tuple[str, ...]
    missing_source_tickers: tuple[str, ...]
    skipped_etf_tickers: tuple[str, ...]
    stale_source_tickers: tuple[str, ...]
    statuses: tuple[ShortInterestSourceTickerStatus, ...]
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class ShortInterestStatus:
    ticker: str
    asset_type: str | None
    latest_signal_date: str | None
    composite_score: float | None
    composite_direction: str | None
    signal_count: int
    confidence: float | None
    model_version: str | None
    data_warnings: str | None
    source_status: str | None
    source_row_count: int | None
    latest_settlement_date: str | None
    percent_float: float | None
    days_to_cover: float | None
    change_pct: float | None
    validation_status: str | None
    validation_date: str | None


@dataclass(frozen=True)
class ShortInterestBackfillRowStatus:
    path: Path
    row_number: int
    ticker: str | None
    status: str
    source: str | None
    settlement_date: str | None
    errors: tuple[str, ...]
    warnings: tuple[str, ...]
    input_row: ShortInterestInput | None = None


@dataclass(frozen=True)
class ShortInterestBackfillValidationReport:
    source_exports_dir: Path
    source_export_files: tuple[Path, ...]
    current_source_backed_count: int
    active_equity_count: int
    current_source_backed_tickers: tuple[str, ...]
    missing_source_tickers: tuple[str, ...]
    skipped_etf_tickers: tuple[str, ...]
    valid_row_count: int
    valid_tickers: tuple[str, ...]
    valid_rows: tuple[ShortInterestBackfillRowStatus, ...]
    blank_placeholder_count: int
    blank_rows: tuple[ShortInterestBackfillRowStatus, ...]
    invalid_row_count: int
    invalid_rows: tuple[ShortInterestBackfillRowStatus, ...]
    etf_gated_rows: tuple[ShortInterestBackfillRowStatus, ...]
    projected_source_backed_count: int
    projected_source_backed_tickers: tuple[str, ...]
    blocked_import_reason: str | None

    @property
    def apply_ready(self) -> bool:
        return self.blocked_import_reason is None

    @property
    def projected_coverage_text(self) -> str:
        return f"{self.projected_source_backed_count}/{self.active_equity_count}"


@dataclass(frozen=True)
class ShortInterestBackfillExportResult:
    source_exports_dir: Path
    template_paths: tuple[Path, ...]
    backfill_path: Path
    missing_tickers: tuple[str, ...]
    etf_gated_tickers: tuple[str, ...]


@dataclass(frozen=True)
class ShortInterestImportResult:
    validation: ShortInterestBackfillValidationReport
    imported_count: int
    written_count: int
    output_path: Path
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class ShortInterestProviderFetchResult:
    provider: str
    requested_tickers: tuple[str, ...]
    fetched_count: int
    normalized_count: int
    written_count: int
    output_path: Path
    cache_hits: int
    cache_misses: int
    cache_writes: int
    live_requests: int
    tickers: tuple[str, ...]
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class ShortInterestProviderNormalizeResult:
    provider: str
    input_path: Path
    output_path: Path
    source_row_count: int
    normalized_count: int
    skipped_count: int
    written_count: int
    tickers: tuple[str, ...]
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class ShortInterestProviderStatus:
    active_equity_count: int
    source_backed_ticker_count: int
    provider_export_valid_row_count: int
    provider_export_tickers: tuple[str, ...]
    provider_order: tuple[str, ...]
    fetchable_providers: tuple[str, ...]
    manual_only_providers: tuple[str, ...]
    cache_dir: Path
    cache_file_count: int
    latest_cache_timestamp: str | None
    missing_source_tickers: tuple[str, ...]
    skipped_etf_tickers: tuple[str, ...]
    latest_settlement_date: str | None
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class ShortInterestProviderDiagnostic:
    ticker: str
    asset_type: str | None
    classification: str
    source_status: str | None
    attempted_paths: tuple[str, ...]
    valid_export_rows: int
    invalid_export_rows: int
    blank_placeholder_rows: int
    recommended_action: str
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class ShortInterestMissingCoveragePlan:
    current_source_backed_count: int
    active_equity_count: int
    missing_tickers: tuple[str, ...]
    etf_gated_tickers: tuple[str, ...]
    diagnostics: tuple[ShortInterestProviderDiagnostic, ...]
    template_path: Path
    valid_missing_tickers: tuple[str, ...]
    projected_source_backed_count: int
    blocked_apply_reason: str | None

    @property
    def apply_ready(self) -> bool:
        return self.blocked_apply_reason is None


@dataclass(frozen=True)
class ShortInterestProviderBackfillApplyResult:
    dry_run: bool
    validation: ShortInterestBackfillValidationReport
    missing_plan: ShortInterestMissingCoveragePlan
    imported_count: int
    written_count: int
    output_path: Path
    warnings: tuple[str, ...]
    blocked_apply_reason: str | None

    @property
    def apply_ready(self) -> bool:
        return self.blocked_apply_reason is None


@dataclass(frozen=True)
class ShortInterestMissingSourceResolutionResult:
    requested_tickers: tuple[str, ...]
    fetch_results: tuple[ShortInterestProviderFetchResult, ...]
    template_path: Path
    diagnostics: tuple[ShortInterestProviderDiagnostic, ...]
    current_source_backed_count: int
    active_equity_count: int
    projected_source_backed_count: int
    valid_missing_tickers: tuple[str, ...]
    blocked_apply_reason: str | None
    warnings: tuple[str, ...]

    @property
    def normalized_count(self) -> int:
        return sum(result.normalized_count for result in self.fetch_results)

    @property
    def written_count(self) -> int:
        return sum(result.written_count for result in self.fetch_results)

    @property
    def live_requests(self) -> int:
        return sum(result.live_requests for result in self.fetch_results)

    @property
    def cache_hits(self) -> int:
        return sum(result.cache_hits for result in self.fetch_results)

    @property
    def apply_ready(self) -> bool:
        return self.blocked_apply_reason is None


def _today() -> date:
    return date.today()


def _join_unique(items: tuple[str, ...] | list[str]) -> str | None:
    cleaned = [item.strip() for item in items if item and item.strip()]
    unique = tuple(dict.fromkeys(cleaned))
    return ", ".join(unique) if unique else None


def _format_float(value: float | None) -> str:
    if value is None:
        return ""
    return f"{value:.10g}"


def _clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, value))


def _parse_date(value: str | None, field_name: str, row_number: int) -> str:
    text = (value or "").strip()
    if not text:
        raise ValueError(f"Row {row_number}: missing required {field_name}.")
    try:
        return date.fromisoformat(text).isoformat()
    except ValueError as error:
        raise ValueError(f"Row {row_number}: malformed {field_name}: {text}") from error


def _parse_optional_date(value: str | None, field_name: str, row_number: int) -> str | None:
    text = (value or "").strip()
    if not text:
        return None
    return _parse_date(text, field_name, row_number)


def _parse_float(
    value: str | None,
    field_name: str,
    row_number: int,
    warnings: list[str],
) -> float | None:
    text = (value or "").strip().replace(",", "")
    if not text:
        return None
    percent_literal = text.endswith("%")
    if percent_literal:
        text = text[:-1].strip()
    try:
        parsed = float(text)
    except ValueError as error:
        raise ValueError(f"Row {row_number}: malformed {field_name}: {value}") from error
    if parsed < 0:
        raise ValueError(f"Row {row_number}: {field_name} cannot be negative.")
    if field_name == "percent_float":
        if percent_literal or parsed > 1:
            parsed = parsed / 100.0
            warnings.append("percent_float_converted_from_percent_points")
    return parsed


def ensure_short_interest_csv_header(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text(",".join(SHORT_INTEREST_HEADERS) + "\n", encoding="utf-8")
        return

    text = path.read_text(encoding="utf-8-sig")
    if not text.strip():
        path.write_text(",".join(SHORT_INTEREST_HEADERS) + "\n", encoding="utf-8")
        return

    reader = csv.DictReader(text.splitlines())
    if not reader.fieldnames:
        path.write_text(",".join(SHORT_INTEREST_HEADERS) + "\n", encoding="utf-8")
        return
    if set(SHORT_INTEREST_HEADERS).issubset(reader.fieldnames):
        return

    rows = list(reader)
    with path.open("w", newline="", encoding="utf-8") as output:
        writer = csv.DictWriter(output, fieldnames=SHORT_INTEREST_HEADERS)
        writer.writeheader()
        for row in rows:
            writer.writerow({header: row.get(header, "") for header in SHORT_INTEREST_HEADERS})


def short_interest_source_exports_dir(config: AppConfig, path: Path | None = None) -> Path:
    return path or (config.project_root / SHORT_INTEREST_SOURCE_EXPORT_DIR)


def short_interest_cache_dir(config: AppConfig) -> Path:
    return config.short_interest_cache_dir


def ensure_short_interest_source_export_templates(directory: Path) -> tuple[Path, ...]:
    directory.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    for file_name in SHORT_INTEREST_DEFAULT_SOURCE_EXPORTS:
        path = directory / file_name
        if not path.exists() or not path.read_text(encoding="utf-8", errors="ignore").strip():
            path.write_text(
                ",".join(SHORT_INTEREST_SOURCE_EXPORT_HEADERS) + "\n",
                encoding="utf-8",
            )
        paths.append(path)
    return tuple(paths)


def _source_export_files(directory: Path) -> tuple[Path, ...]:
    if not directory.exists():
        return ()
    return tuple(sorted(path for path in directory.glob("*.csv") if path.is_file()))


def _provider_export_path(config: AppConfig, directory: Path | None = None) -> Path:
    output_dir = short_interest_source_exports_dir(config, directory)
    ensure_short_interest_source_export_templates(output_dir)
    return output_dir / SHORT_INTEREST_PROVIDER_EXPORT_FILE


def _missing_provider_template_path(config: AppConfig, directory: Path | None = None) -> Path:
    output_dir = short_interest_source_exports_dir(config, directory)
    return output_dir / SHORT_INTEREST_MISSING_PROVIDER_TEMPLATE


def _safe_file_part(value: str) -> str:
    return "".join(character if character.isalnum() else "_" for character in value.lower())


def _cache_path(config: AppConfig, provider: str, ticker: str) -> Path:
    return short_interest_cache_dir(config) / provider / f"{_safe_file_part(ticker)}.json"


def _is_cache_fresh(path: Path, stale_hours: int) -> bool:
    if not path.exists():
        return False
    modified = datetime.fromtimestamp(path.stat().st_mtime)
    return datetime.now() - modified <= timedelta(hours=stale_hours)


def _read_cached_payload(path: Path) -> tuple[Any, str | None, str | None]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    return raw.get("payload"), raw.get("source_url"), raw.get("fetched_at")


def _write_cached_payload(path: Path, provider: str, ticker: str, source_url: str, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "provider": provider,
                "ticker": ticker,
                "source_url": source_url,
                "fetched_at": datetime.now().isoformat(timespec="seconds"),
                "payload": payload,
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )


def _http_json_request(
    url: str,
    timeout_seconds: int,
    method: str = "GET",
    payload: dict[str, object] | None = None,
) -> Any:
    body = None
    headers = {
        "Accept": "application/json,text/csv,text/plain,*/*",
        "User-Agent": "TargetOpportunityMonitor/0.1",
    }
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = Request(url, data=body, headers=headers, method=method)
    with urlopen(request, timeout=timeout_seconds) as response:
        text = response.read().decode("utf-8-sig", errors="replace")
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return text


def _active_asset_groups(config: AppConfig) -> tuple[dict[str, Asset], tuple[str, ...], tuple[str, ...]]:
    assets = _asset_map(config)
    active_equities = tuple(
        sorted(
            ticker
            for ticker, asset in assets.items()
            if (asset.asset_type or "equity").lower() != "etf"
        )
    )
    active_etfs = tuple(
        sorted(
            ticker
            for ticker, asset in assets.items()
            if (asset.asset_type or "equity").lower() == "etf"
        )
    )
    return assets, active_equities, active_etfs


def _is_blank_placeholder(row: dict[str, str]) -> bool:
    ticker = (row.get("ticker") or "").strip()
    if not ticker:
        return False
    for header in SHORT_INTEREST_SOURCE_EXPORT_HEADERS:
        if header == "ticker":
            continue
        if (row.get(header) or "").strip():
            return False
    return True


def _input_to_csv_row(input_row: ShortInterestInput) -> dict[str, str]:
    return {
        "ticker": input_row.ticker,
        "settlement_date": input_row.settlement_date,
        "publication_date": input_row.publication_date or "",
        "short_interest": _format_float(input_row.short_interest),
        "float_shares": _format_float(input_row.float_shares),
        "percent_float": _format_float(input_row.percent_float),
        "average_daily_volume": _format_float(input_row.average_daily_volume),
        "days_to_cover": _format_float(input_row.days_to_cover),
        "source": input_row.source,
        "source_url": input_row.source_url,
        "notes": input_row.notes or "",
        "as_of_date": input_row.as_of_date or "",
        "effective_date": input_row.effective_date or "",
    }


def _normalized_key(value: object) -> str:
    return "".join(character for character in str(value).lower() if character.isalnum())


def _raw_value(row: dict[str, object], aliases: tuple[str, ...]) -> object | None:
    lookup = {_normalized_key(key): value for key, value in row.items()}
    for alias in aliases:
        value = lookup.get(_normalized_key(alias))
        if value not in (None, ""):
            return value
    return None


def _string_value(value: object | None) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _provider_date(value: object | None) -> str:
    text = _string_value(value)
    if not text:
        return ""
    if text.endswith("Z") or "T" in text:
        text = text.split("T", 1)[0]
    compact = text.replace("-", "").replace("/", "").strip()
    if compact.isdigit() and len(compact) == 8:
        try:
            return date(int(compact[0:4]), int(compact[4:6]), int(compact[6:8])).isoformat()
        except ValueError:
            pass
    for format_string in ("%Y-%m-%d", "%m/%d/%Y", "%m/%d/%y", "%d-%b-%Y", "%b %d, %Y"):
        try:
            return datetime.strptime(text, format_string).date().isoformat()
        except ValueError:
            continue
    return text


def _extract_dict_rows(payload: Any) -> list[dict[str, object]]:
    if isinstance(payload, list):
        rows: list[dict[str, object]] = []
        for item in payload:
            rows.extend(_extract_dict_rows(item))
        return rows
    if not isinstance(payload, dict):
        return []
    direct_rows: list[dict[str, object]] = []
    if any(
        _normalized_key(key)
        in {
            "ticker",
            "symbol",
            "symbolcode",
            "settlementdate",
            "currentshortpositionquantity",
            "shortinterest",
            "sharesshort",
        }
        for key in payload
    ):
        direct_rows.append(payload)
    for key in ("data", "rows", "results", "items", "shortInterestTable"):
        value = payload.get(key)
        if value is not None:
            direct_rows.extend(_extract_dict_rows(value))
    return direct_rows


def _delimited_rows(text: str) -> list[dict[str, object]]:
    sample = text[:2048]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",|\t;")
    except csv.Error:
        dialect = csv.excel
    reader = csv.DictReader(StringIO(text), dialect=dialect)
    return [dict(row) for row in reader if row]


def _rows_from_provider_export_text(text: str) -> list[dict[str, object]]:
    stripped = text.strip()
    if not stripped:
        return []
    if stripped[0] in "[{":
        return _extract_dict_rows(json.loads(stripped))
    return _delimited_rows(stripped)


def _provider_source_label(provider: str) -> str:
    return SHORT_INTEREST_PROVIDER_SOURCES.get(provider, "provider_export")


def _provider_default_source_url(provider: str) -> str:
    if provider == "finra":
        return FINRA_SHORT_INTEREST_SOURCE_URL
    if provider == "nasdaq_trader":
        return NASDAQ_SHORT_INTEREST_SOURCE_URL
    return ""


def _provider_row_to_source_export_row(
    row: dict[str, object],
    provider: str,
    assets: dict[str, Asset],
    default_ticker: str | None = None,
    source_url: str | None = None,
) -> tuple[dict[str, str] | None, tuple[str, ...]]:
    warnings: list[str] = []
    ticker = normalize_ticker(
        _string_value(
            _raw_value(
                row,
                (
                    "ticker",
                    "symbol",
                    "symbolCode",
                    "symbol_code",
                    "issueSymbol",
                    "securitySymbol",
                ),
            )
            or default_ticker
        )
    )
    if not ticker:
        return None, ("missing_ticker",)
    asset = assets.get(ticker)
    if asset is None:
        return None, (f"{ticker}:unsupported_ticker",)
    if (asset.asset_type or "equity").lower() == "etf":
        return None, (f"{ticker}:etf_short_interest_gated",)

    settlement_date = _provider_date(
        _raw_value(
            row,
            (
                "settlement_date",
                "settlementDate",
                "Settlement Date",
                "date",
                "positionDate",
                "accountingYearMonthNumber",
            ),
        )
    )
    if not settlement_date:
        return None, (f"{ticker}:missing_settlement_date",)

    row_source_url = _string_value(
        _raw_value(row, ("source_url", "sourceUrl", "url", "source link", "link"))
    )
    final_source_url = row_source_url or source_url or _provider_default_source_url(provider)
    if not final_source_url:
        return None, (f"{ticker}:missing_source_url",)

    short_interest = _string_value(
        _raw_value(
            row,
            (
                "short_interest",
                "shortInterest",
                "sharesShort",
                "currentShort",
                "Current Short",
                "currentShortPositionQuantity",
                "shortPositionQuantity",
            ),
        )
    )
    average_daily_volume = _string_value(
        _raw_value(
            row,
            (
                "average_daily_volume",
                "averageDailyVolume",
                "averageDailyVolumeQuantity",
                "avgDailyVol",
                "Avg Daily Vol",
            ),
        )
    )
    percent_float = _string_value(
        _raw_value(
            row,
            (
                "percent_float",
                "percentFloat",
                "shortPercentOfFloat",
                "% Float",
                "percentOfFloat",
            ),
        )
    )
    days_to_cover = _string_value(
        _raw_value(
            row,
            (
                "days_to_cover",
                "daysToCover",
                "daysToCoverQuantity",
                "Days to Cover",
            ),
        )
    )
    float_shares = _string_value(
        _raw_value(row, ("float_shares", "floatShares", "sharesFloat", "float"))
    )
    if not any((short_interest, percent_float, days_to_cover)):
        return None, (f"{ticker}:missing_numeric_short_interest_evidence",)

    publication_date = _provider_date(
        _raw_value(
            row,
            (
                "publication_date",
                "publicationDate",
                "releaseDate",
                "disseminationDate",
            ),
        )
    )
    notes = _string_value(_raw_value(row, ("notes", "description", "issueName", "Issue Name")))
    provider_source = _string_value(_raw_value(row, ("source", "provider")))
    source = provider_source if provider_source and provider in {"generic", "broker"} else _provider_source_label(provider)
    as_of = _today().isoformat()
    output_row = {
        "ticker": ticker,
        "settlement_date": settlement_date,
        "publication_date": publication_date,
        "short_interest": short_interest,
        "float_shares": float_shares,
        "percent_float": percent_float,
        "average_daily_volume": average_daily_volume,
        "days_to_cover": days_to_cover,
        "source": source,
        "source_url": final_source_url,
        "notes": notes or f"{provider} normalized source row",
        "as_of_date": as_of,
        "effective_date": settlement_date,
        "capture_method": f"{provider}_normalization",
    }
    return output_row, tuple(warnings)


def _merge_provider_export_rows(path: Path, rows: list[dict[str, str]]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    existing: dict[tuple[str, str, str], dict[str, str]] = {}
    if path.exists() and path.read_text(encoding="utf-8-sig").strip():
        reader = csv.DictReader(path.read_text(encoding="utf-8-sig").splitlines())
        for row in reader:
            ticker = normalize_ticker(row.get("ticker", ""))
            settlement_date = (row.get("settlement_date") or "").strip()
            source = (row.get("source") or "").strip()
            if ticker and settlement_date and source:
                existing[(ticker, settlement_date, source)] = {
                    header: row.get(header, "") for header in SHORT_INTEREST_SOURCE_EXPORT_HEADERS
                }
    for row in rows:
        key = (
            normalize_ticker(row.get("ticker", "")),
            (row.get("settlement_date") or "").strip(),
            (row.get("source") or "").strip(),
        )
        if all(key):
            existing[key] = {header: row.get(header, "") for header in SHORT_INTEREST_SOURCE_EXPORT_HEADERS}
    with path.open("w", newline="", encoding="utf-8") as output:
        writer = csv.DictWriter(output, fieldnames=SHORT_INTEREST_SOURCE_EXPORT_HEADERS)
        writer.writeheader()
        for key in sorted(existing):
            writer.writerow(existing[key])
    return len(existing)


def _parse_source_export_row(
    row: dict[str, str],
    file_path: Path,
    row_number: int,
    assets: dict[str, Asset],
) -> ShortInterestBackfillRowStatus:
    ticker = normalize_ticker(row.get("ticker", ""))
    if not ticker and not any((value or "").strip() for value in row.values()):
        return ShortInterestBackfillRowStatus(
            file_path,
            row_number,
            None,
            "empty",
            None,
            None,
            (),
            (),
        )
    if _is_blank_placeholder(row):
        return ShortInterestBackfillRowStatus(
            file_path,
            row_number,
            ticker,
            "blank_placeholder",
            None,
            None,
            (),
            (),
        )
    if not ticker:
        return ShortInterestBackfillRowStatus(
            file_path,
            row_number,
            None,
            "invalid",
            (row.get("source") or "").strip() or None,
            (row.get("settlement_date") or "").strip() or None,
            ("missing_ticker",),
            (),
        )
    asset = assets.get(ticker)
    if asset is None:
        return ShortInterestBackfillRowStatus(
            file_path,
            row_number,
            ticker,
            "invalid",
            (row.get("source") or "").strip() or None,
            (row.get("settlement_date") or "").strip() or None,
            ("inactive_or_unknown_ticker",),
            (),
        )
    if (asset.asset_type or "equity").lower() == "etf":
        return ShortInterestBackfillRowStatus(
            file_path,
            row_number,
            ticker,
            "etf_gated",
            (row.get("source") or "").strip() or None,
            (row.get("settlement_date") or "").strip() or None,
            (),
            ("etf_short_interest_gated",),
        )

    csv_row = {header: row.get(header, "") for header in SHORT_INTEREST_HEADERS}
    capture_method = (row.get("capture_method") or "").strip()
    if capture_method:
        existing_notes = csv_row.get("notes", "").strip()
        capture_note = f"capture_method={capture_method}"
        csv_row["notes"] = "; ".join(
            item for item in (existing_notes, capture_note) if item
        )
    buffer = StringIO()
    writer = csv.DictWriter(buffer, fieldnames=SHORT_INTEREST_HEADERS)
    writer.writeheader()
    writer.writerow(csv_row)
    try:
        parsed = parse_short_interest_csv(buffer.getvalue())[0]
    except ValueError as error:
        return ShortInterestBackfillRowStatus(
            file_path,
            row_number,
            ticker,
            "invalid",
            csv_row.get("source") or None,
            csv_row.get("settlement_date") or None,
            (str(error).replace("Row 2:", f"Row {row_number}:").strip(),),
            (),
        )

    if (
        parsed.short_interest is None
        and parsed.percent_float is None
        and parsed.days_to_cover is None
    ):
        return ShortInterestBackfillRowStatus(
            file_path,
            row_number,
            parsed.ticker,
            "invalid",
            parsed.source,
            parsed.settlement_date,
            ("missing_numeric_short_interest_evidence",),
            parsed.warnings,
            parsed,
        )
    return ShortInterestBackfillRowStatus(
        file_path,
        row_number,
        parsed.ticker,
        "valid",
        parsed.source,
        parsed.settlement_date,
        (),
        parsed.warnings,
        parsed,
    )


def export_short_interest_backfill(
    config: AppConfig,
    directory: Path | None = None,
) -> ShortInterestBackfillExportResult:
    output_dir = short_interest_source_exports_dir(config, directory)
    template_paths = ensure_short_interest_source_export_templates(output_dir)
    source_status = short_interest_source_status_report(config)
    backfill_path = output_dir / SHORT_INTEREST_BACKFILL_TEMPLATE
    with backfill_path.open("w", newline="", encoding="utf-8") as output:
        writer = csv.DictWriter(output, fieldnames=SHORT_INTEREST_SOURCE_EXPORT_HEADERS)
        writer.writeheader()
        for ticker in source_status.missing_source_tickers:
            writer.writerow({header: ticker if header == "ticker" else "" for header in SHORT_INTEREST_SOURCE_EXPORT_HEADERS})
    return ShortInterestBackfillExportResult(
        source_exports_dir=output_dir,
        template_paths=template_paths,
        backfill_path=backfill_path,
        missing_tickers=source_status.missing_source_tickers,
        etf_gated_tickers=source_status.skipped_etf_tickers,
    )


def export_short_interest_missing_provider_template(
    config: AppConfig,
    directory: Path | None = None,
) -> ShortInterestBackfillExportResult:
    output_dir = short_interest_source_exports_dir(config, directory)
    template_paths = ensure_short_interest_source_export_templates(output_dir)
    source_status = short_interest_source_status_report(config)
    backfill_path = _missing_provider_template_path(config, output_dir)
    with backfill_path.open("w", newline="", encoding="utf-8") as output:
        writer = csv.DictWriter(output, fieldnames=SHORT_INTEREST_SOURCE_EXPORT_HEADERS)
        writer.writeheader()
        for ticker in source_status.missing_source_tickers:
            writer.writerow(
                {
                    header: ticker if header == "ticker" else ""
                    for header in SHORT_INTEREST_SOURCE_EXPORT_HEADERS
                }
            )
    return ShortInterestBackfillExportResult(
        source_exports_dir=output_dir,
        template_paths=template_paths,
        backfill_path=backfill_path,
        missing_tickers=source_status.missing_source_tickers,
        etf_gated_tickers=source_status.skipped_etf_tickers,
    )


def validate_short_interest_backfill(
    config: AppConfig,
    directory: Path | None = None,
) -> ShortInterestBackfillValidationReport:
    source_status = short_interest_source_status_report(config)
    output_dir = short_interest_source_exports_dir(config, directory)
    files = _source_export_files(output_dir)
    assets, _active_equities, active_etfs = _active_asset_groups(config)
    row_statuses: list[ShortInterestBackfillRowStatus] = []
    for file_path in files:
        text = file_path.read_text(encoding="utf-8-sig")
        if not text.strip():
            continue
        reader = csv.DictReader(text.splitlines())
        if not reader.fieldnames:
            row_statuses.append(
                ShortInterestBackfillRowStatus(
                    file_path,
                    1,
                    None,
                    "invalid",
                    None,
                    None,
                    ("missing_header",),
                    (),
                )
            )
            continue
        for row_number, row in enumerate(reader, start=2):
            row_status = _parse_source_export_row(row, file_path, row_number, assets)
            if row_status.status != "empty":
                row_statuses.append(row_status)

    valid_rows = tuple(status for status in row_statuses if status.status == "valid")
    invalid_rows = tuple(status for status in row_statuses if status.status == "invalid")
    blank_rows = tuple(
        status for status in row_statuses if status.status == "blank_placeholder"
    )
    etf_rows = tuple(status for status in row_statuses if status.status == "etf_gated")
    valid_tickers = tuple(
        sorted(dict.fromkeys(status.ticker for status in valid_rows if status.ticker))
    )
    projected_tickers = tuple(
        sorted(dict.fromkeys(source_status.source_backed_tickers + valid_tickers))
    )
    blocked_reason: str | None = None
    if invalid_rows:
        blocked_reason = "invalid_short_interest_backfill_rows"
    elif not valid_rows:
        blocked_reason = "no_valid_short_interest_backfill_rows"
    elif len(projected_tickers) <= source_status.source_backed_ticker_count:
        blocked_reason = "projected_short_interest_coverage_does_not_improve"

    etf_gated_tickers = tuple(
        sorted(
            dict.fromkeys(
                source_status.skipped_etf_tickers
                + active_etfs
                + tuple(status.ticker for status in etf_rows if status.ticker)
            )
        )
    )
    return ShortInterestBackfillValidationReport(
        source_exports_dir=output_dir,
        source_export_files=files,
        current_source_backed_count=source_status.source_backed_ticker_count,
        active_equity_count=source_status.active_equity_count,
        current_source_backed_tickers=source_status.source_backed_tickers,
        missing_source_tickers=source_status.missing_source_tickers,
        skipped_etf_tickers=etf_gated_tickers,
        valid_row_count=len(valid_rows),
        valid_tickers=valid_tickers,
        valid_rows=valid_rows,
        blank_placeholder_count=len(blank_rows),
        blank_rows=blank_rows,
        invalid_row_count=len(invalid_rows),
        invalid_rows=invalid_rows,
        etf_gated_rows=etf_rows,
        projected_source_backed_count=len(projected_tickers),
        projected_source_backed_tickers=projected_tickers,
        blocked_import_reason=blocked_reason,
    )


def _row_statuses_by_ticker(
    rows: tuple[ShortInterestBackfillRowStatus, ...],
) -> dict[str, tuple[ShortInterestBackfillRowStatus, ...]]:
    grouped: dict[str, list[ShortInterestBackfillRowStatus]] = {}
    for row in rows:
        if row.ticker:
            grouped.setdefault(row.ticker, []).append(row)
    return {ticker: tuple(items) for ticker, items in grouped.items()}


def _provider_cache_attempts(config: AppConfig, ticker: str) -> tuple[str, ...]:
    attempts: list[str] = []
    for provider in config.signals_short_interest_provider_order:
        if provider in SHORT_INTEREST_FETCH_PROVIDERS:
            cache_path = _cache_path(config, provider, ticker)
            attempts.append(
                f"{provider}:cache_present" if cache_path.exists() else f"{provider}:not_cached"
            )
        else:
            attempts.append(f"{provider}:manual_export_path")
    return tuple(attempts)


def short_interest_provider_diagnostics(
    config: AppConfig,
    ticker: str | None = None,
    directory: Path | None = None,
) -> tuple[ShortInterestProviderDiagnostic, ...]:
    source_report = short_interest_source_status_report(config)
    validation = validate_short_interest_backfill(config, directory)
    assets, active_equities, active_etfs = _active_asset_groups(config)
    source_by_ticker = {status.ticker: status for status in source_report.statuses}
    valid_by_ticker = _row_statuses_by_ticker(validation.valid_rows)
    invalid_by_ticker = _row_statuses_by_ticker(validation.invalid_rows)
    all_row_statuses = (
        validation.valid_rows
        + validation.invalid_rows
        + validation.blank_rows
        + validation.etf_gated_rows
    )
    blank_by_ticker = _row_statuses_by_ticker(
        tuple(row for row in all_row_statuses if row.status == "blank_placeholder")
    )
    requested = normalize_ticker(ticker) if ticker else None
    tickers = (requested,) if requested else tuple(source_report.missing_source_tickers)
    diagnostics: list[ShortInterestProviderDiagnostic] = []
    for item_ticker in tickers:
        if not item_ticker:
            continue
        asset = assets.get(item_ticker)
        source_status = source_by_ticker.get(item_ticker)
        valid_rows = valid_by_ticker.get(item_ticker, ())
        invalid_rows = invalid_by_ticker.get(item_ticker, ())
        blank_rows = blank_by_ticker.get(item_ticker, ())
        attempted_paths = list(_provider_cache_attempts(config, item_ticker))
        if valid_rows:
            attempted_paths.append("provider_export:valid_row")
        elif any(row.path.name == SHORT_INTEREST_PROVIDER_EXPORT_FILE for row in invalid_rows):
            attempted_paths.append("provider_export:invalid_row")
        else:
            attempted_paths.append("provider_export:missing")
        attempted_paths.extend(("exchange_manual:available", "broker_manual:available"))

        warnings: list[str] = []
        if source_status and source_status.warnings:
            warnings.extend(source_status.warnings)
        for row in invalid_rows:
            warnings.extend(row.errors)
        if asset is None:
            classification = "unsupported_ticker"
            recommended_action = "Add the ticker as a scoreable equity before short-interest coverage."
            asset_type = None
        else:
            asset_type = (asset.asset_type or "equity").lower()
            if asset_type == "etf" or item_ticker in active_etfs:
                classification = "etf_gated"
                recommended_action = "ETF short-interest signals are gated in this MVP."
                warnings.append("etf_short_interest_gated")
            elif source_status and source_status.source_backed:
                classification = "source_backed"
                recommended_action = "No backfill action needed."
            elif invalid_rows:
                classification = "malformed_source_row"
                recommended_action = "Fix invalid source-export rows, then rerun apply."
            elif valid_rows:
                classification = "provider_export_needed"
                recommended_action = "Run apply-short-interest-provider-backfill --confirm."
            elif any(
                attempt.endswith(":cache_present")
                for attempt in attempted_paths
            ):
                classification = "official_fetch_missing"
                recommended_action = (
                    "Use provider_export, exchange_manual, or broker_manual source rows."
                )
            elif item_ticker in active_equities:
                classification = "provider_export_needed"
                recommended_action = (
                    "Fetch official sources or fill the missing-provider template."
                )
            else:
                classification = "manual_exchange_needed"
                recommended_action = "Use exchange or broker source export."
        diagnostics.append(
            ShortInterestProviderDiagnostic(
                ticker=item_ticker,
                asset_type=asset_type,
                classification=classification,
                source_status=source_status.status if source_status else None,
                attempted_paths=tuple(dict.fromkeys(attempted_paths)),
                valid_export_rows=len(valid_rows),
                invalid_export_rows=len(invalid_rows),
                blank_placeholder_rows=len(blank_rows),
                recommended_action=recommended_action,
                warnings=tuple(dict.fromkeys(warnings)),
            )
        )
    return tuple(sorted(diagnostics, key=lambda item: item.ticker))


def short_interest_missing_coverage_plan(
    config: AppConfig,
    directory: Path | None = None,
) -> ShortInterestMissingCoveragePlan:
    source_report = short_interest_source_status_report(config)
    validation = validate_short_interest_backfill(config, directory)
    missing = source_report.missing_source_tickers
    valid_missing_tickers = tuple(
        ticker for ticker in validation.valid_tickers if ticker in missing
    )
    projected_tickers = tuple(
        sorted(dict.fromkeys(source_report.source_backed_tickers + valid_missing_tickers))
    )
    blocked_reason: str | None = None
    if validation.invalid_row_count:
        blocked_reason = "invalid_short_interest_backfill_rows"
    elif not valid_missing_tickers:
        blocked_reason = "no_valid_missing_short_interest_rows"
    elif len(projected_tickers) <= source_report.source_backed_ticker_count:
        blocked_reason = "projected_short_interest_coverage_does_not_improve"
    return ShortInterestMissingCoveragePlan(
        current_source_backed_count=source_report.source_backed_ticker_count,
        active_equity_count=source_report.active_equity_count,
        missing_tickers=missing,
        etf_gated_tickers=source_report.skipped_etf_tickers,
        diagnostics=short_interest_provider_diagnostics(config, directory=directory),
        template_path=_missing_provider_template_path(config, directory),
        valid_missing_tickers=valid_missing_tickers,
        projected_source_backed_count=len(projected_tickers),
        blocked_apply_reason=blocked_reason,
    )


def apply_short_interest_provider_backfill(
    config: AppConfig,
    directory: Path | None = None,
    confirm: bool = False,
) -> ShortInterestProviderBackfillApplyResult:
    validation = validate_short_interest_backfill(config, directory)
    missing_plan = short_interest_missing_coverage_plan(config, directory)
    warnings: list[str] = []
    blocked_reason = missing_plan.blocked_apply_reason
    if not confirm:
        warnings.append("dry_run_only")
        return ShortInterestProviderBackfillApplyResult(
            dry_run=True,
            validation=validation,
            missing_plan=missing_plan,
            imported_count=0,
            written_count=0,
            output_path=config.short_interest_path,
            warnings=tuple(warnings),
            blocked_apply_reason=blocked_reason,
        )
    if blocked_reason is not None:
        warnings.append(blocked_reason)
        return ShortInterestProviderBackfillApplyResult(
            dry_run=False,
            validation=validation,
            missing_plan=missing_plan,
            imported_count=0,
            written_count=0,
            output_path=config.short_interest_path,
            warnings=tuple(dict.fromkeys(warnings)),
            blocked_apply_reason=blocked_reason,
        )
    import_result = import_short_interest_source_exports(config, directory)
    warnings.extend(import_result.warnings)
    return ShortInterestProviderBackfillApplyResult(
        dry_run=False,
        validation=validation,
        missing_plan=missing_plan,
        imported_count=import_result.imported_count,
        written_count=import_result.written_count,
        output_path=import_result.output_path,
        warnings=tuple(dict.fromkeys(warnings)),
        blocked_apply_reason=None,
    )


def preview_short_interest_import(
    config: AppConfig,
    directory: Path | None = None,
) -> ShortInterestBackfillValidationReport:
    return validate_short_interest_backfill(config, directory)


def import_short_interest_source_exports(
    config: AppConfig,
    directory: Path | None = None,
) -> ShortInterestImportResult:
    validation = validate_short_interest_backfill(config, directory)
    warnings: list[str] = []
    if validation.invalid_row_count:
        warnings.append("invalid_short_interest_backfill_rows")
        return ShortInterestImportResult(
            validation=validation,
            imported_count=0,
            written_count=0,
            output_path=config.short_interest_path,
            warnings=tuple(warnings),
        )
    valid_inputs = [status.input_row for status in validation.valid_rows if status.input_row]
    if not valid_inputs:
        warnings.append("no_valid_short_interest_backfill_rows")
        return ShortInterestImportResult(
            validation=validation,
            imported_count=0,
            written_count=0,
            output_path=config.short_interest_path,
            warnings=tuple(warnings),
        )

    ensure_short_interest_csv_header(config.short_interest_path)
    existing_rows: dict[tuple[str, str, str], dict[str, str]] = {}
    current_text = config.short_interest_path.read_text(encoding="utf-8-sig")
    reader = csv.DictReader(current_text.splitlines())
    for row in reader:
        ticker = normalize_ticker(row.get("ticker", ""))
        settlement = (row.get("settlement_date") or "").strip()
        source = (row.get("source") or "").strip()
        if ticker and settlement and source:
            existing_rows[(ticker, settlement, source)] = {
                header: row.get(header, "") for header in SHORT_INTEREST_HEADERS
            }
    for input_row in valid_inputs:
        key = (input_row.ticker, input_row.settlement_date, input_row.source)
        existing_rows[key] = _input_to_csv_row(input_row)

    config.short_interest_path.parent.mkdir(parents=True, exist_ok=True)
    with config.short_interest_path.open("w", newline="", encoding="utf-8") as output:
        writer = csv.DictWriter(output, fieldnames=SHORT_INTEREST_HEADERS)
        writer.writeheader()
        for key in sorted(existing_rows):
            writer.writerow(existing_rows[key])
    return ShortInterestImportResult(
        validation=validation,
        imported_count=len(valid_inputs),
        written_count=len(existing_rows),
        output_path=config.short_interest_path,
        warnings=tuple(dict.fromkeys(warnings)),
    )


def _provider_payload_for_ticker(
    config: AppConfig,
    provider: str,
    ticker: str,
    use_cache: bool,
    force_refresh: bool,
) -> tuple[Any | None, str | None, bool, bool, bool, tuple[str, ...]]:
    warnings: list[str] = []
    cache_path = _cache_path(config, provider, ticker)
    stale_hours = config.signals_short_interest_provider_cache_stale_hours
    if use_cache and not force_refresh and _is_cache_fresh(cache_path, stale_hours):
        try:
            payload, source_url, _fetched_at = _read_cached_payload(cache_path)
            return payload, source_url, True, False, False, ()
        except (OSError, json.JSONDecodeError) as error:
            warnings.append(f"{ticker}:{provider}_cache_read_failed:{error}")

    source_url = None
    payload: Any | None = None
    try:
        if provider == "finra":
            source_url = FINRA_SHORT_INTEREST_SOURCE_URL
            request_payload = {
                "limit": 25,
                "compareFilters": [
                    {
                        "compareType": "equal",
                        "fieldName": "symbolCode",
                        "fieldValue": ticker,
                    }
                ],
            }
            payload = _http_json_request(
                FINRA_SHORT_INTEREST_ENDPOINT,
                timeout_seconds=config.signals_short_interest_provider_timeout_seconds,
                method="POST",
                payload=request_payload,
            )
        elif provider == "nasdaq_trader":
            source_url = NASDAQ_SHORT_INTEREST_ENDPOINT_TEMPLATE.format(ticker=ticker)
            payload = _http_json_request(
                source_url,
                timeout_seconds=config.signals_short_interest_provider_timeout_seconds,
            )
        else:
            warnings.append(f"{provider}:manual_source_export_only")
            return None, None, False, False, False, tuple(warnings)
    except HTTPError as error:
        warnings.append(f"{ticker}:{provider}_http_{error.code}")
        return None, source_url, False, True, False, tuple(warnings)
    except (URLError, TimeoutError, OSError) as error:
        warnings.append(f"{ticker}:{provider}_http_failed:{error}")
        return None, source_url, False, True, False, tuple(warnings)

    cache_written = False
    if payload is not None:
        try:
            _write_cached_payload(cache_path, provider, ticker, source_url or "", payload)
            cache_written = True
        except OSError as error:
            warnings.append(f"{ticker}:{provider}_cache_write_failed:{error}")
    return payload, source_url, False, True, cache_written, tuple(warnings)


def _normalize_provider_payload(
    config: AppConfig,
    provider: str,
    ticker: str,
    payload: Any,
    source_url: str | None,
) -> tuple[list[dict[str, str]], tuple[str, ...]]:
    assets, _equities, _etfs = _active_asset_groups(config)
    if isinstance(payload, str):
        try:
            rows = _rows_from_provider_export_text(payload)
        except (csv.Error, json.JSONDecodeError) as error:
            return [], (f"{ticker}:{provider}_payload_parse_failed:{error}",)
    else:
        rows = _extract_dict_rows(payload)
    warnings: list[str] = []
    normalized: list[dict[str, str]] = []
    for row in rows:
        output_row, row_warnings = _provider_row_to_source_export_row(
            row,
            provider,
            assets,
            default_ticker=ticker,
            source_url=source_url,
        )
        warnings.extend(row_warnings)
        if output_row:
            normalized.append(output_row)
    if not rows:
        warnings.append(f"{ticker}:{provider}_empty_payload")
    elif not normalized:
        warnings.append(f"{ticker}:{provider}_no_normalized_short_interest_rows")
    return normalized, tuple(dict.fromkeys(warnings))


def _requested_equity_tickers(
    config: AppConfig,
    ticker: str | None = None,
    max_tickers: int | None = None,
) -> tuple[str, ...]:
    _assets, equities, _etfs = _active_asset_groups(config)
    if ticker:
        wanted = normalize_ticker(ticker)
        return (wanted,) if wanted in equities else ()
    limit = max_tickers or config.signals_short_interest_provider_max_tickers_per_run
    return tuple(equities[:limit])


def fetch_short_interest_sources(
    config: AppConfig,
    provider: str = "all",
    ticker: str | None = None,
    use_cache: bool | None = None,
    force_refresh: bool = False,
    max_tickers: int | None = None,
    directory: Path | None = None,
) -> ShortInterestProviderFetchResult:
    if provider != "all" and provider not in SHORT_INTEREST_FETCH_PROVIDERS:
        output_path = _provider_export_path(config, directory)
        return ShortInterestProviderFetchResult(
            provider=provider,
            requested_tickers=(),
            fetched_count=0,
            normalized_count=0,
            written_count=0,
            output_path=output_path,
            cache_hits=0,
            cache_misses=0,
            cache_writes=0,
            live_requests=0,
            tickers=(),
            warnings=(f"{provider}:unsupported_short_interest_fetch_provider",),
        )
    selected_providers = (
        tuple(item for item in config.signals_short_interest_provider_order if item in SHORT_INTEREST_FETCH_PROVIDERS)
        if provider == "all"
        else (provider,)
    )
    requested_tickers = _requested_equity_tickers(config, ticker=ticker, max_tickers=max_tickers)
    output_path = _provider_export_path(config, directory)
    use_cache_value = config.signals_short_interest_provider_use_cache if use_cache is None else use_cache
    warnings: list[str] = []
    output_rows: list[dict[str, str]] = []
    cache_hits = 0
    cache_misses = 0
    cache_writes = 0
    live_requests = 0
    fetched_count = 0
    for requested_ticker in requested_tickers:
        ticker_row_count = 0
        for selected_provider in selected_providers:
            payload, source_url, cache_hit, live_request, cache_written, fetch_warnings = (
                _provider_payload_for_ticker(
                    config,
                    selected_provider,
                    requested_ticker,
                    use_cache=use_cache_value,
                    force_refresh=force_refresh,
                )
            )
            warnings.extend(fetch_warnings)
            cache_hits += 1 if cache_hit else 0
            cache_misses += 0 if cache_hit else 1
            live_requests += 1 if live_request else 0
            cache_writes += 1 if cache_written else 0
            if payload is None:
                continue
            fetched_count += 1
            rows, normalize_warnings = _normalize_provider_payload(
                config,
                selected_provider,
                requested_ticker,
                payload,
                source_url,
            )
            warnings.extend(normalize_warnings)
            output_rows.extend(rows)
            ticker_row_count += len(rows)
            if rows:
                break
        if ticker_row_count == 0:
            warnings.append(f"{requested_ticker}:missing_short_interest_provider_row")
    written_count = _merge_provider_export_rows(output_path, output_rows) if output_rows else 0
    return ShortInterestProviderFetchResult(
        provider=provider,
        requested_tickers=requested_tickers,
        fetched_count=fetched_count,
        normalized_count=len(output_rows),
        written_count=written_count,
        output_path=output_path,
        cache_hits=cache_hits,
        cache_misses=cache_misses,
        cache_writes=cache_writes,
        live_requests=live_requests,
        tickers=tuple(sorted({row["ticker"] for row in output_rows})),
        warnings=tuple(dict.fromkeys(warnings)),
    )


def resolve_short_interest_missing_sources(
    config: AppConfig,
    ticker: str | None = None,
    provider: str = "all",
    use_cache: bool | None = None,
    force_refresh: bool = False,
    directory: Path | None = None,
) -> ShortInterestMissingSourceResolutionResult:
    before_plan = short_interest_missing_coverage_plan(config, directory)
    requested = normalize_ticker(ticker) if ticker else None
    warnings: list[str] = []
    if requested:
        if requested not in before_plan.missing_tickers:
            warnings.append(f"{requested}:not_missing_short_interest_source")
            requested_tickers: tuple[str, ...] = ()
        else:
            requested_tickers = (requested,)
    else:
        requested_tickers = before_plan.missing_tickers

    fetch_results: list[ShortInterestProviderFetchResult] = []
    for missing_ticker in requested_tickers:
        result = fetch_short_interest_sources(
            config,
            provider=provider,
            ticker=missing_ticker,
            use_cache=use_cache,
            force_refresh=force_refresh,
            max_tickers=1,
            directory=directory,
        )
        fetch_results.append(result)
        warnings.extend(result.warnings)

    export_result = export_short_interest_missing_provider_template(config, directory)
    after_plan = short_interest_missing_coverage_plan(config, directory)
    diagnostics = (
        short_interest_provider_diagnostics(config, ticker=requested, directory=directory)
        if requested
        else after_plan.diagnostics
    )
    if not requested_tickers and not requested:
        warnings.append("no_missing_short_interest_sources")
    return ShortInterestMissingSourceResolutionResult(
        requested_tickers=requested_tickers,
        fetch_results=tuple(fetch_results),
        template_path=export_result.backfill_path,
        diagnostics=diagnostics,
        current_source_backed_count=after_plan.current_source_backed_count,
        active_equity_count=after_plan.active_equity_count,
        projected_source_backed_count=after_plan.projected_source_backed_count,
        valid_missing_tickers=after_plan.valid_missing_tickers,
        blocked_apply_reason=after_plan.blocked_apply_reason,
        warnings=tuple(dict.fromkeys(warnings)),
    )


def normalize_short_interest_provider_export(
    config: AppConfig,
    provider: str,
    file_path: Path,
    directory: Path | None = None,
) -> ShortInterestProviderNormalizeResult:
    provider = provider.strip().lower()
    if provider not in SHORT_INTEREST_EXPORT_NORMALIZATION_PROVIDERS:
        output_path = _provider_export_path(config, directory)
        return ShortInterestProviderNormalizeResult(
            provider=provider,
            input_path=file_path,
            output_path=output_path,
            source_row_count=0,
            normalized_count=0,
            skipped_count=0,
            written_count=0,
            tickers=(),
            warnings=(f"{provider}:unsupported_short_interest_normalization_provider",),
        )
    output_path = _provider_export_path(config, directory)
    if not file_path.exists():
        return ShortInterestProviderNormalizeResult(
            provider=provider,
            input_path=file_path,
            output_path=output_path,
            source_row_count=0,
            normalized_count=0,
            skipped_count=0,
            written_count=0,
            tickers=(),
            warnings=(f"{file_path}:missing_provider_export_file",),
        )
    text = file_path.read_text(encoding="utf-8-sig", errors="replace")
    try:
        rows = _rows_from_provider_export_text(text)
    except (csv.Error, json.JSONDecodeError) as error:
        return ShortInterestProviderNormalizeResult(
            provider=provider,
            input_path=file_path,
            output_path=output_path,
            source_row_count=0,
            normalized_count=0,
            skipped_count=0,
            written_count=0,
            tickers=(),
            warnings=(f"{file_path}:provider_export_parse_failed:{error}",),
        )
    assets, _equities, _etfs = _active_asset_groups(config)
    warnings: list[str] = []
    output_rows: list[dict[str, str]] = []
    for row_number, row in enumerate(rows, start=2):
        output_row, row_warnings = _provider_row_to_source_export_row(row, provider, assets)
        warnings.extend(
            f"{file_path.name}:{row_number}:{warning}" for warning in row_warnings
        )
        if output_row:
            output_rows.append(output_row)
    written_count = _merge_provider_export_rows(output_path, output_rows) if output_rows else 0
    return ShortInterestProviderNormalizeResult(
        provider=provider,
        input_path=file_path,
        output_path=output_path,
        source_row_count=len(rows),
        normalized_count=len(output_rows),
        skipped_count=max(0, len(rows) - len(output_rows)),
        written_count=written_count,
        tickers=tuple(sorted({row["ticker"] for row in output_rows})),
        warnings=tuple(dict.fromkeys(warnings)),
    )


def short_interest_provider_status(config: AppConfig) -> ShortInterestProviderStatus:
    source_status = short_interest_source_status_report(config)
    validation = validate_short_interest_backfill(config)
    provider_export_path = _provider_export_path(config)
    provider_valid_rows = tuple(
        row
        for row in validation.valid_rows
        if row.path.name == SHORT_INTEREST_PROVIDER_EXPORT_FILE
    )
    provider_order = config.signals_short_interest_provider_order
    fetchable = tuple(item for item in provider_order if item in SHORT_INTEREST_FETCH_PROVIDERS)
    manual_only = tuple(item for item in provider_order if item not in SHORT_INTEREST_FETCH_PROVIDERS)
    cache_dir = short_interest_cache_dir(config)
    cache_files = tuple(cache_dir.rglob("*.json")) if cache_dir.exists() else ()
    latest_cache_timestamp = None
    if cache_files:
        latest_cache_timestamp = datetime.fromtimestamp(
            max(path.stat().st_mtime for path in cache_files)
        ).isoformat(timespec="seconds")
    warnings: list[str] = []
    if not fetchable:
        warnings.append("no_fetchable_short_interest_providers_configured")
    if not provider_export_path.exists() or not provider_valid_rows:
        warnings.append("provider_export_empty")
    if source_status.source_backed_ticker_count < source_status.active_equity_count:
        warnings.append("short_interest_source_coverage_incomplete")
    if not cache_files:
        warnings.append("short_interest_provider_cache_empty")
    return ShortInterestProviderStatus(
        active_equity_count=source_status.active_equity_count,
        source_backed_ticker_count=source_status.source_backed_ticker_count,
        provider_export_valid_row_count=len(provider_valid_rows),
        provider_export_tickers=tuple(sorted({row.ticker or "" for row in provider_valid_rows if row.ticker})),
        provider_order=provider_order,
        fetchable_providers=fetchable,
        manual_only_providers=manual_only,
        cache_dir=cache_dir,
        cache_file_count=len(cache_files),
        latest_cache_timestamp=latest_cache_timestamp,
        missing_source_tickers=source_status.missing_source_tickers,
        skipped_etf_tickers=source_status.skipped_etf_tickers,
        latest_settlement_date=source_status.latest_settlement_date,
        warnings=tuple(dict.fromkeys(warnings + list(source_status.warnings))),
    )


def parse_short_interest_csv(text: str) -> list[ShortInterestInput]:
    reader = csv.DictReader(text.splitlines())
    if not reader.fieldnames:
        raise ValueError("Short-interest CSV missing header.")
    missing = REQUIRED_COLUMNS - set(reader.fieldnames)
    if missing:
        raise ValueError(
            "Short-interest CSV missing required columns: " + ", ".join(sorted(missing))
        )

    rows: list[ShortInterestInput] = []
    for row_number, row in enumerate(reader, start=2):
        if not any((value or "").strip() for value in row.values()):
            continue
        warnings: list[str] = []
        ticker = normalize_ticker(row.get("ticker", ""))
        if not ticker:
            raise ValueError(f"Row {row_number}: missing required ticker.")
        source = (row.get("source") or "").strip()
        if not source:
            raise ValueError(f"Row {row_number}: missing required source.")
        source_url = (row.get("source_url") or "").strip()
        if not source_url:
            raise ValueError(f"Row {row_number}: missing required source_url.")
        numeric = {
            field: _parse_float(row.get(field), field, row_number, warnings)
            for field in NUMERIC_FIELDS
        }
        if numeric["percent_float"] is None:
            short_interest = numeric["short_interest"]
            float_shares = numeric["float_shares"]
            if short_interest not in (None, 0) and float_shares not in (None, 0):
                numeric["percent_float"] = short_interest / float_shares
                warnings.append("derived_percent_float")
        if numeric["days_to_cover"] is None:
            short_interest = numeric["short_interest"]
            average_daily_volume = numeric["average_daily_volume"]
            if short_interest not in (None, 0) and average_daily_volume not in (None, 0):
                numeric["days_to_cover"] = short_interest / average_daily_volume
                warnings.append("derived_days_to_cover")
        if not any(numeric[field] is not None for field in NUMERIC_FIELDS):
            warnings.append("missing_short_interest_numeric_fields")

        settlement_date = _parse_date(
            row.get("settlement_date"),
            "settlement_date",
            row_number,
        )
        rows.append(
            ShortInterestInput(
                ticker=ticker,
                settlement_date=settlement_date,
                publication_date=_parse_optional_date(
                    row.get("publication_date"), "publication_date", row_number
                ),
                source=source,
                source_url=source_url,
                notes=(row.get("notes") or "").strip() or None,
                as_of_date=_parse_optional_date(row.get("as_of_date"), "as_of_date", row_number)
                or _today().isoformat(),
                effective_date=_parse_optional_date(
                    row.get("effective_date"), "effective_date", row_number
                )
                or settlement_date,
                warnings=tuple(dict.fromkeys(warnings)),
                **numeric,
            )
        )
    return rows


def _asset_map(config: AppConfig) -> dict[str, Asset]:
    return {asset.ticker: asset for asset in list_assets(config.database_path) if is_scoreable_asset(asset)}


def load_short_interest_csv(
    config: AppConfig,
    path: Path | None = None,
) -> ShortInterestLoadResult:
    short_interest_path = path or config.short_interest_path
    ensure_short_interest_csv_header(short_interest_path)
    rows = parse_short_interest_csv(short_interest_path.read_text(encoding="utf-8-sig"))
    assets = _asset_map(config)
    warnings: list[str] = []
    loaded_count = 0
    skipped_count = 0
    loaded_tickers: list[str] = []
    for row in rows:
        asset = assets.get(row.ticker)
        if asset is None:
            skipped_count += 1
            warnings.append(f"{row.ticker}:inactive_or_unknown_ticker")
            continue
        asset_type = (asset.asset_type or "equity").lower()
        if asset_type == "etf":
            skipped_count += 1
            warnings.append(f"{row.ticker}:etf_short_interest_gated")
            _record_signal_quality(config, row.ticker, ("etf_short_interest_gated",))
            continue
        upsert_short_interest_source_snapshot(
            config.database_path,
            ShortInterestSourceSnapshot(
                ticker=row.ticker,
                settlement_date=row.settlement_date,
                publication_date=row.publication_date,
                short_interest=row.short_interest,
                float_shares=row.float_shares,
                percent_float=row.percent_float,
                average_daily_volume=row.average_daily_volume,
                days_to_cover=row.days_to_cover,
                source=row.source,
                source_url=row.source_url,
                notes=row.notes,
                data_warnings=_join_unique(row.warnings),
                as_of_date=row.as_of_date,
                effective_date=row.effective_date,
            ),
        )
        loaded_count += 1
        loaded_tickers.append(row.ticker)
        if row.warnings:
            warnings.append(f"{row.ticker}:{','.join(row.warnings)}")
    if not rows:
        warnings.append("empty_short_interest")
    return ShortInterestLoadResult(
        path=short_interest_path,
        row_count=len(rows),
        loaded_count=loaded_count,
        skipped_count=skipped_count,
        tickers=tuple(sorted(dict.fromkeys(loaded_tickers))),
        warnings=tuple(dict.fromkeys(warnings)),
    )


def _parse_source_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return None


def _direction_from_score(score: float | None) -> str:
    if score is None:
        return "neutral"
    if score >= 60:
        return "positive"
    if score <= 40:
        return "negative"
    return "neutral"


def _score_level(percent_float: float | None) -> float:
    if percent_float is None:
        return 50.0
    return _clamp(100.0 - (percent_float / 0.25) * 100.0)


def _score_days_to_cover(days_to_cover: float | None) -> float:
    if days_to_cover is None:
        return 50.0
    return _clamp(100.0 - (days_to_cover / 10.0) * 100.0)


def _score_change(change_pct: float | None) -> float:
    if change_pct is None:
        return 50.0
    return _clamp(50.0 - change_pct * 200.0)


def _score_squeeze_setup(
    percent_float: float | None,
    days_to_cover: float | None,
    return_1m: float | None,
) -> tuple[float, tuple[str, ...]]:
    if percent_float is None or days_to_cover is None or return_1m is None:
        return 50.0, ()
    if percent_float >= 0.08 and days_to_cover >= 3.0 and return_1m > 0.03:
        score = _clamp(55.0 + min(percent_float * 100.0, 20.0) + return_1m * 180.0)
        return score, ("squeeze_candidate_shadow_only",)
    return 50.0, ()


def _change_pct(
    latest: ShortInterestSourceSnapshot,
    prior: ShortInterestSourceSnapshot | None,
) -> float | None:
    if (
        prior is None
        or latest.short_interest is None
        or prior.short_interest in (None, 0)
    ):
        return None
    return latest.short_interest / prior.short_interest - 1.0


def _latest_and_prior(
    snapshots: list[ShortInterestSourceSnapshot],
) -> tuple[ShortInterestSourceSnapshot | None, ShortInterestSourceSnapshot | None]:
    if not snapshots:
        return None, None
    ordered = sorted(snapshots, key=lambda item: item.settlement_date)
    latest = ordered[-1]
    prior = ordered[-2] if len(ordered) > 1 else None
    return latest, prior


def _record_signal_quality(config: AppConfig, ticker: str, warnings: tuple[str, ...]) -> None:
    insert_data_quality_check(
        config.database_path,
        check_name=f"short_interest_signals:{ticker}",
        status="warning" if warnings else "ok",
        details=", ".join(warnings) if warnings else "short_interest_signals_computed",
        source="short_interest_signals",
        as_of_date=_today().isoformat(),
    )


def _upsert_component_signal(
    config: AppConfig,
    ticker: str,
    signal_date: str,
    signal_name: str,
    value: float | None,
    score: float,
    reason_code: str,
    confidence: float,
    warnings: tuple[str, ...],
    source_url: str | None,
    notes: str | None,
) -> None:
    upsert_signal(
        config.database_path,
        Signal(
            ticker=ticker,
            signal_date=signal_date,
            signal_name=signal_name,
            signal_family=SIGNAL_FAMILY,
            value=value,
            score=score,
            direction=_direction_from_score(score),
            reason_code=reason_code,
            source="short_interest",
            model_version=config.signals_short_interest_model_version,
            confidence=confidence,
            data_warnings=_join_unique(warnings),
            source_url=source_url,
            notes=notes,
            as_of_date=_today().isoformat(),
            effective_date=signal_date,
        )
    )


def _compute_ticker_short_interest_signals(
    config: AppConfig,
    asset: Asset,
) -> ShortInterestTickerResult:
    ticker = asset.ticker
    asset_type = (asset.asset_type or "equity").lower()
    if asset_type == "etf":
        warnings = ("etf_short_interest_gated",)
        _record_signal_quality(config, ticker, warnings)
        return ShortInterestTickerResult(ticker, "skipped", "etf", None, warnings)

    snapshots = list_short_interest_source_snapshots(config.database_path, ticker=ticker)
    latest, prior = _latest_and_prior(snapshots)
    if latest is None:
        warnings = ("missing_short_interest_source",)
        _record_signal_quality(config, ticker, warnings)
        return ShortInterestTickerResult(ticker, "skipped", "equity", None, warnings)

    warnings: list[str] = []
    if config.signals_short_interest_shadow_mode:
        warnings.append("short_interest_shadow_mode")
    if latest.data_warnings:
        warnings.extend(item.strip() for item in latest.data_warnings.split(",") if item.strip())
    latest_date = _parse_source_date(latest.settlement_date)
    if latest_date is None:
        warnings.append("malformed_short_interest_settlement_date")
    elif (_today() - latest_date).days > config.signals_short_interest_stale_after_days:
        warnings.append("stale_short_interest_source")
    if latest.percent_float is None:
        warnings.append("missing_percent_float")
    if latest.days_to_cover is None:
        warnings.append("missing_days_to_cover")

    change_pct = _change_pct(latest, prior)
    if change_pct is None:
        warnings.append("missing_short_interest_history")

    price_feature = latest_price_feature(config.database_path, ticker)
    return_1m = price_feature.return_1m if price_feature else None
    squeeze_score, squeeze_warnings = _score_squeeze_setup(
        latest.percent_float,
        latest.days_to_cover,
        return_1m,
    )
    warnings.extend(squeeze_warnings)

    level_score = _score_level(latest.percent_float)
    days_score = _score_days_to_cover(latest.days_to_cover)
    change_score = _score_change(change_pct)
    composite_score = _clamp(
        level_score * 0.35
        + days_score * 0.25
        + change_score * 0.30
        + squeeze_score * 0.10
    )
    confidence = 65.0
    if "missing_short_interest_history" in warnings:
        confidence -= 10.0
    if "stale_short_interest_source" in warnings:
        confidence -= 15.0
    if "missing_percent_float" in warnings:
        confidence -= 10.0
    if "missing_days_to_cover" in warnings:
        confidence -= 10.0
    confidence = _clamp(confidence)

    notes = _join_unique(
        [
            latest.notes or "",
            f"short_interest={latest.short_interest}" if latest.short_interest is not None else "",
            f"percent_float={latest.percent_float}" if latest.percent_float is not None else "",
            f"days_to_cover={latest.days_to_cover}" if latest.days_to_cover is not None else "",
            f"change_pct={change_pct}" if change_pct is not None else "",
        ]
    )
    final_warnings = tuple(dict.fromkeys(warnings))
    signal_date = latest.settlement_date
    _upsert_component_signal(
        config,
        ticker,
        signal_date,
        LEVEL_SIGNAL_NAME,
        latest.percent_float,
        level_score,
        "short_interest_level",
        confidence,
        final_warnings,
        latest.source_url,
        notes,
    )
    _upsert_component_signal(
        config,
        ticker,
        signal_date,
        DAYS_TO_COVER_SIGNAL_NAME,
        latest.days_to_cover,
        days_score,
        "short_interest_days_to_cover",
        confidence,
        final_warnings,
        latest.source_url,
        notes,
    )
    _upsert_component_signal(
        config,
        ticker,
        signal_date,
        CHANGE_SIGNAL_NAME,
        change_pct,
        change_score,
        "short_interest_change",
        confidence,
        final_warnings,
        latest.source_url,
        notes,
    )
    _upsert_component_signal(
        config,
        ticker,
        signal_date,
        SQUEEZE_SIGNAL_NAME,
        return_1m,
        squeeze_score,
        "short_interest_squeeze_setup",
        confidence,
        final_warnings,
        latest.source_url,
        notes,
    )
    upsert_signal(
        config.database_path,
        Signal(
            ticker=ticker,
            signal_date=signal_date,
            signal_name=COMPOSITE_SIGNAL_NAME,
            signal_family=SIGNAL_FAMILY,
            value=composite_score,
            score=composite_score,
            direction=_direction_from_score(composite_score),
            reason_code="short_interest_composite",
            source="short_interest",
            model_version=config.signals_short_interest_model_version,
            confidence=confidence,
            data_warnings=_join_unique(final_warnings),
            source_url=latest.source_url,
            notes=notes,
            as_of_date=_today().isoformat(),
            effective_date=signal_date,
        )
    )
    _record_signal_quality(config, ticker, final_warnings)
    return ShortInterestTickerResult(
        ticker,
        "computed",
        "equity",
        composite_score,
        final_warnings,
    )


def compute_short_interest_signals(
    config: AppConfig,
    ticker: str | None = None,
) -> ShortInterestUpdateResult:
    load_result = load_short_interest_csv(config)
    wanted_ticker = normalize_ticker(ticker) if ticker else None
    assets = [
        asset
        for asset in list_assets(config.database_path)
        if is_scoreable_asset(asset) and (wanted_ticker is None or asset.ticker == wanted_ticker)
    ]
    results = tuple(_compute_ticker_short_interest_signals(config, asset) for asset in assets)
    return ShortInterestUpdateResult(results=results, load_result=load_result)


def short_interest_source_status_report(config: AppConfig) -> ShortInterestSourceStatusReport:
    assets = [asset for asset in list_assets(config.database_path) if is_scoreable_asset(asset)]
    snapshots_by_ticker: dict[str, list[ShortInterestSourceSnapshot]] = {}
    for snapshot in list_short_interest_source_snapshots(config.database_path):
        snapshots_by_ticker.setdefault(snapshot.ticker, []).append(snapshot)
    statuses: list[ShortInterestSourceTickerStatus] = []
    source_backed: list[str] = []
    missing: list[str] = []
    skipped_etfs: list[str] = []
    stale: list[str] = []
    all_warnings: list[str] = []
    cutoff_days = config.signals_short_interest_stale_after_days
    for asset in assets:
        ticker = asset.ticker
        asset_type = (asset.asset_type or "equity").lower()
        snapshots = snapshots_by_ticker.get(ticker, [])
        latest, prior = _latest_and_prior(snapshots)
        warnings: list[str] = []
        if asset_type == "etf":
            status = "etf_gated"
            skipped_etfs.append(ticker)
            warnings.append("etf_short_interest_gated")
        elif latest is None:
            status = "missing_source"
            missing.append(ticker)
            warnings.append("missing_short_interest_source")
        else:
            status = "source_backed"
            source_backed.append(ticker)
            if latest.data_warnings:
                warnings.extend(
                    item.strip() for item in latest.data_warnings.split(",") if item.strip()
                )
            latest_date = _parse_source_date(latest.settlement_date)
            if latest_date is None:
                warnings.append("malformed_short_interest_settlement_date")
            elif (_today() - latest_date).days > cutoff_days:
                status = "stale_source"
                stale.append(ticker)
                warnings.append("stale_short_interest_source")
        if warnings:
            all_warnings.extend(f"{ticker}:{warning}" for warning in warnings)
        change = _change_pct(latest, prior) if latest else None
        statuses.append(
            ShortInterestSourceTickerStatus(
                ticker=ticker,
                asset_type=asset_type,
                status=status,
                source_backed=latest is not None,
                source_row_count=len(snapshots),
                latest_settlement_date=latest.settlement_date if latest else None,
                latest_publication_date=latest.publication_date if latest else None,
                percent_float=latest.percent_float if latest else None,
                days_to_cover=latest.days_to_cover if latest else None,
                change_pct=change,
                warnings=tuple(dict.fromkeys(warnings)),
            )
        )
    return ShortInterestSourceStatusReport(
        active_equity_count=sum(1 for status in statuses if status.asset_type != "etf"),
        source_backed_ticker_count=len(tuple(dict.fromkeys(source_backed))),
        source_snapshot_count=sum(len(rows) for rows in snapshots_by_ticker.values()),
        latest_settlement_date=latest_short_interest_settlement_date(config.database_path),
        source_backed_tickers=tuple(sorted(dict.fromkeys(source_backed))),
        missing_source_tickers=tuple(sorted(dict.fromkeys(missing))),
        skipped_etf_tickers=tuple(sorted(dict.fromkeys(skipped_etfs))),
        stale_source_tickers=tuple(sorted(dict.fromkeys(stale))),
        statuses=tuple(sorted(statuses, key=lambda item: item.ticker)),
        warnings=tuple(dict.fromkeys(all_warnings)),
    )


def short_interest_statuses(config: AppConfig) -> list[ShortInterestStatus]:
    signal_status_by_ticker: dict[str, SignalStatus] = {
        status.ticker: status
        for status in signal_statuses_for_family(
            config.database_path,
            signal_family=SIGNAL_FAMILY,
            composite_signal_name=COMPOSITE_SIGNAL_NAME,
            quality_check_prefix="short_interest_signals",
        )
    }
    source_by_ticker = {
        status.ticker: status for status in short_interest_source_status_report(config).statuses
    }
    validation_by_ticker: dict[str, SignalOutcomeStatus] = {
        status.ticker: status
        for status in signal_outcome_statuses(
            config.database_path,
            signal_family=SIGNAL_FAMILY,
            signal_name=COMPOSITE_SIGNAL_NAME,
        )
    }
    rows: list[ShortInterestStatus] = []
    for ticker, status in sorted(signal_status_by_ticker.items()):
        source_status = source_by_ticker.get(ticker)
        validation = validation_by_ticker.get(ticker)
        rows.append(
            ShortInterestStatus(
                ticker=ticker,
                asset_type=status.asset_type,
                latest_signal_date=status.latest_signal_date,
                composite_score=status.composite_score,
                composite_direction=status.composite_direction,
                signal_count=status.signal_count,
                confidence=status.confidence,
                model_version=status.model_version,
                data_warnings=status.data_warnings,
                source_status=source_status.status if source_status else None,
                source_row_count=source_status.source_row_count if source_status else None,
                latest_settlement_date=(
                    source_status.latest_settlement_date if source_status else None
                ),
                percent_float=source_status.percent_float if source_status else None,
                days_to_cover=source_status.days_to_cover if source_status else None,
                change_pct=source_status.change_pct if source_status else None,
                validation_status=validation.outcome_status if validation else None,
                validation_date=validation.outcome_date if validation else None,
            )
        )
    return rows


def build_short_interest_status_text(config: AppConfig) -> str:
    source_report = short_interest_source_status_report(config)
    statuses = short_interest_statuses(config)
    status_by_ticker = {status.ticker: status for status in statuses}
    lines = [
        "Short interest status",
        f"Source-backed coverage: {source_report.source_backed_ticker_count}/{source_report.active_equity_count}",
        f"Source rows: {source_report.source_snapshot_count}",
        f"Latest settlement date: {source_report.latest_settlement_date or 'none'}",
        f"Missing source tickers: {', '.join(source_report.missing_source_tickers) if source_report.missing_source_tickers else 'none'}",
        f"ETF-gated tickers: {', '.join(source_report.skipped_etf_tickers) if source_report.skipped_etf_tickers else 'none'}",
        f"Stale source tickers: {', '.join(source_report.stale_source_tickers) if source_report.stale_source_tickers else 'none'}",
        "Ticker | Type | Source Status | Settlement | Percent Float | Days To Cover | Change | Composite | Direction | Validation | Warnings",
    ]
    for source_status in source_report.statuses:
        signal_status = status_by_ticker.get(source_status.ticker)
        warnings = _join_unique(
            list(source_status.warnings)
            + ([signal_status.data_warnings] if signal_status and signal_status.data_warnings else [])
        )
        lines.append(
            " | ".join(
                (
                    source_status.ticker,
                    source_status.asset_type,
                    source_status.status,
                    source_status.latest_settlement_date or "",
                    f"{source_status.percent_float:.4f}"
                    if source_status.percent_float is not None
                    else "",
                    f"{source_status.days_to_cover:.2f}"
                    if source_status.days_to_cover is not None
                    else "",
                    f"{source_status.change_pct:.4f}"
                    if source_status.change_pct is not None
                    else "",
                    f"{signal_status.composite_score:.2f}"
                    if signal_status and signal_status.composite_score is not None
                    else "",
                    signal_status.composite_direction if signal_status and signal_status.composite_direction else "",
                    (
                        f"{signal_status.validation_status}@{signal_status.validation_date}"
                        if signal_status and signal_status.validation_status and signal_status.validation_date
                        else ""
                    ),
                    warnings or "",
                )
            )
        )
    return "\n".join(lines)


def _display_path(path: Path, project_root: Path) -> str:
    try:
        return str(path.resolve().relative_to(project_root.resolve()))
    except ValueError:
        return str(path)


def _format_row_errors(row: ShortInterestBackfillRowStatus, project_root: Path) -> str:
    location = f"{_display_path(row.path, project_root)}:{row.row_number}"
    ticker = row.ticker or "none"
    errors = ", ".join(row.errors) if row.errors else "none"
    warnings = ", ".join(row.warnings) if row.warnings else "none"
    return f"{location} | {ticker} | {row.status} | errors={errors} | warnings={warnings}"


def build_short_interest_coverage_plan_text(
    config: AppConfig,
    directory: Path | None = None,
) -> str:
    validation = validate_short_interest_backfill(config, directory)
    lines = [
        "Short interest coverage plan",
        f"Source exports directory: {_display_path(validation.source_exports_dir, config.project_root)}",
        f"Current source-backed coverage: {validation.current_source_backed_count}/{validation.active_equity_count}",
        f"Projected source-backed coverage: {validation.projected_coverage_text}",
        f"Missing source tickers: {', '.join(validation.missing_source_tickers) if validation.missing_source_tickers else 'none'}",
        f"Valid backfill tickers: {', '.join(validation.valid_tickers) if validation.valid_tickers else 'none'}",
        f"ETF-gated tickers: {', '.join(validation.skipped_etf_tickers) if validation.skipped_etf_tickers else 'none'}",
        f"Blank placeholder rows: {validation.blank_placeholder_count}",
        f"Invalid rows: {validation.invalid_row_count}",
        f"Import apply ready: {validation.apply_ready}",
        f"Blocked import reason: {validation.blocked_import_reason or 'none'}",
        "Next commands:",
        "python -m target_opportunity_monitor export-short-interest-backfill",
        "python -m target_opportunity_monitor validate-short-interest-backfill",
        "python -m target_opportunity_monitor import-short-interest-source-exports",
        "python -m target_opportunity_monitor load-short-interest",
        "python -m target_opportunity_monitor compute-short-interest-signals",
    ]
    return "\n".join(lines)


def build_short_interest_missing_coverage_plan_text(
    config: AppConfig,
    directory: Path | None = None,
) -> str:
    plan = short_interest_missing_coverage_plan(config, directory)
    lines = [
        "Short interest missing coverage plan",
        f"Current source-backed coverage: {plan.current_source_backed_count}/{plan.active_equity_count}",
        f"Projected source-backed coverage after valid missing rows: {plan.projected_source_backed_count}/{plan.active_equity_count}",
        f"Missing source tickers: {', '.join(plan.missing_tickers) if plan.missing_tickers else 'none'}",
        f"Valid missing-row tickers: {', '.join(plan.valid_missing_tickers) if plan.valid_missing_tickers else 'none'}",
        f"ETF-gated tickers: {', '.join(plan.etf_gated_tickers) if plan.etf_gated_tickers else 'none'}",
        f"Missing-provider template: {_display_path(plan.template_path, config.project_root)}",
        f"Apply ready: {plan.apply_ready}",
        f"Blocked apply reason: {plan.blocked_apply_reason or 'none'}",
        "Diagnostics:",
    ]
    if not plan.diagnostics:
        lines.append("none")
    for item in plan.diagnostics:
        lines.append(
            " | ".join(
                (
                    item.ticker,
                    item.classification,
                    item.source_status or "none",
                    "attempted=" + ", ".join(item.attempted_paths),
                    f"valid_rows={item.valid_export_rows}",
                    f"invalid_rows={item.invalid_export_rows}",
                    f"blank_rows={item.blank_placeholder_rows}",
                    item.recommended_action,
                    "warnings=" + (", ".join(item.warnings) if item.warnings else "none"),
                )
            )
        )
    lines.extend(
        (
            "Next commands:",
            "python -m target_opportunity_monitor export-short-interest-missing-provider-template",
            "python -m target_opportunity_monitor apply-short-interest-provider-backfill",
            "python -m target_opportunity_monitor apply-short-interest-provider-backfill --confirm",
            "python -m target_opportunity_monitor load-short-interest",
            "python -m target_opportunity_monitor compute-short-interest-signals",
            "python -m target_opportunity_monitor validate-short-interest-signals",
        )
    )
    return "\n".join(lines)


def build_short_interest_provider_diagnostics_text(
    config: AppConfig,
    ticker: str | None = None,
    directory: Path | None = None,
) -> str:
    diagnostics = short_interest_provider_diagnostics(config, ticker=ticker, directory=directory)
    lines = [
        "Short interest provider diagnostics",
        f"Ticker filter: {normalize_ticker(ticker) if ticker else 'missing tickers'}",
        "Ticker | Type | Classification | Source Status | Valid Rows | Invalid Rows | Blank Rows | Attempted Paths | Recommended Action | Warnings",
    ]
    if not diagnostics:
        lines.append("none")
    for item in diagnostics:
        lines.append(
            " | ".join(
                (
                    item.ticker,
                    item.asset_type or "",
                    item.classification,
                    item.source_status or "",
                    str(item.valid_export_rows),
                    str(item.invalid_export_rows),
                    str(item.blank_placeholder_rows),
                    ", ".join(item.attempted_paths),
                    item.recommended_action,
                    ", ".join(item.warnings) if item.warnings else "",
                )
            )
        )
    return "\n".join(lines)


def build_short_interest_missing_source_resolution_text(
    config: AppConfig,
    ticker: str | None = None,
    provider: str = "all",
    use_cache: bool | None = None,
    force_refresh: bool = False,
    directory: Path | None = None,
) -> str:
    result = resolve_short_interest_missing_sources(
        config,
        ticker=ticker,
        provider=provider,
        use_cache=use_cache,
        force_refresh=force_refresh,
        directory=directory,
    )
    lines = [
        "Short interest missing source resolution",
        f"Ticker filter: {normalize_ticker(ticker) if ticker else 'missing tickers'}",
        f"Provider: {provider}",
        f"Requested missing tickers: {', '.join(result.requested_tickers) if result.requested_tickers else 'none'}",
        f"Provider rows normalized: {result.normalized_count}",
        f"Provider export rows written: {result.written_count}",
        f"Live requests: {result.live_requests}",
        f"Cache hits: {result.cache_hits}",
        f"Current source-backed coverage: {result.current_source_backed_count}/{result.active_equity_count}",
        f"Projected source-backed coverage after valid missing rows: {result.projected_source_backed_count}/{result.active_equity_count}",
        f"Valid missing-row tickers: {', '.join(result.valid_missing_tickers) if result.valid_missing_tickers else 'none'}",
        f"Missing-provider template refreshed: {_display_path(result.template_path, config.project_root)}",
        f"Apply ready: {result.apply_ready}",
        f"Blocked apply reason: {result.blocked_apply_reason or 'none'}",
        "Diagnostics:",
    ]
    if not result.diagnostics:
        lines.append("none")
    for item in result.diagnostics:
        lines.append(
            " | ".join(
                (
                    item.ticker,
                    item.classification,
                    item.source_status or "none",
                    "attempted=" + ", ".join(item.attempted_paths),
                    f"valid_rows={item.valid_export_rows}",
                    f"invalid_rows={item.invalid_export_rows}",
                    f"blank_rows={item.blank_placeholder_rows}",
                    item.recommended_action,
                    "warnings=" + (", ".join(item.warnings) if item.warnings else "none"),
                )
            )
        )
    if result.warnings:
        lines.append("Warnings: " + ", ".join(result.warnings))
    lines.extend(
        (
            "Next commands:",
            "python -m target_opportunity_monitor apply-short-interest-provider-backfill",
            "python -m target_opportunity_monitor apply-short-interest-provider-backfill --confirm",
            "python -m target_opportunity_monitor load-short-interest",
            "python -m target_opportunity_monitor compute-short-interest-signals",
            "python -m target_opportunity_monitor validate-short-interest-signals",
        )
    )
    return "\n".join(lines)


def build_short_interest_provider_backfill_apply_text(
    config: AppConfig,
    directory: Path | None = None,
    confirm: bool = False,
) -> tuple[str, ShortInterestProviderBackfillApplyResult]:
    result = apply_short_interest_provider_backfill(config, directory=directory, confirm=confirm)
    mode = "confirmed apply" if confirm else "dry run"
    lines = [
        f"Short interest provider backfill {mode}",
        f"Current source-backed coverage: {result.missing_plan.current_source_backed_count}/{result.missing_plan.active_equity_count}",
        f"Projected source-backed coverage: {result.missing_plan.projected_source_backed_count}/{result.missing_plan.active_equity_count}",
        f"Projected coverage improvement: {result.missing_plan.projected_source_backed_count - result.missing_plan.current_source_backed_count}",
        f"Missing source tickers: {', '.join(result.missing_plan.missing_tickers) if result.missing_plan.missing_tickers else 'none'}",
        f"Valid missing-row tickers: {', '.join(result.missing_plan.valid_missing_tickers) if result.missing_plan.valid_missing_tickers else 'none'}",
        f"Invalid rows: {result.validation.invalid_row_count}",
        f"Blank placeholders: {result.validation.blank_placeholder_count}",
        f"Imported rows: {result.imported_count}",
        f"Written rows: {result.written_count}",
        f"Output path: {_display_path(result.output_path, config.project_root)}",
        f"Apply ready: {result.apply_ready}",
        f"Blocked apply reason: {result.blocked_apply_reason or 'none'}",
    ]
    if not confirm:
        lines.append("Dry run only. Add --confirm to write validated source rows.")
    if result.warnings:
        lines.append("Warnings: " + ", ".join(result.warnings))
    return "\n".join(lines), result


def build_short_interest_source_status_text(
    config: AppConfig,
    missing_only: bool = False,
) -> str:
    source_report = short_interest_source_status_report(config)
    lines = [
        "Short interest source status",
        f"Source-backed coverage: {source_report.source_backed_ticker_count}/{source_report.active_equity_count}",
        f"Source rows: {source_report.source_snapshot_count}",
        f"Latest settlement date: {source_report.latest_settlement_date or 'none'}",
        f"ETF-gated tickers: {', '.join(source_report.skipped_etf_tickers) if source_report.skipped_etf_tickers else 'none'}",
    ]
    if missing_only:
        lines.append(
            "Missing source tickers: "
            + (
                ", ".join(source_report.missing_source_tickers)
                if source_report.missing_source_tickers
                else "none"
            )
        )
        return "\n".join(lines)
    lines.append(
        "Ticker | Type | Source Status | Settlement | Percent Float | Days To Cover | Change | Warnings"
    )
    for status in source_report.statuses:
        warnings = ", ".join(status.warnings) if status.warnings else ""
        lines.append(
            " | ".join(
                (
                    status.ticker,
                    status.asset_type,
                    status.status,
                    status.latest_settlement_date or "",
                    f"{status.percent_float:.4f}" if status.percent_float is not None else "",
                    f"{status.days_to_cover:.2f}" if status.days_to_cover is not None else "",
                    f"{status.change_pct:.4f}" if status.change_pct is not None else "",
                    warnings,
                )
            )
        )
    return "\n".join(lines)


def build_short_interest_provider_status_text(config: AppConfig) -> str:
    status = short_interest_provider_status(config)
    lines = [
        "Short interest provider status",
        f"Source-backed coverage: {status.source_backed_ticker_count}/{status.active_equity_count}",
        f"Provider export valid rows: {status.provider_export_valid_row_count}",
        f"Provider export tickers: {', '.join(status.provider_export_tickers) if status.provider_export_tickers else 'none'}",
        f"Provider order: {', '.join(status.provider_order) if status.provider_order else 'none'}",
        f"Fetchable providers: {', '.join(status.fetchable_providers) if status.fetchable_providers else 'none'}",
        f"Manual/export-only providers: {', '.join(status.manual_only_providers) if status.manual_only_providers else 'none'}",
        f"Cache directory: {status.cache_dir}",
        f"Cache files: {status.cache_file_count}",
        f"Latest cache timestamp: {status.latest_cache_timestamp or 'none'}",
        f"Latest settlement date: {status.latest_settlement_date or 'none'}",
        f"Missing source tickers: {', '.join(status.missing_source_tickers) if status.missing_source_tickers else 'none'}",
        f"ETF-gated tickers: {', '.join(status.skipped_etf_tickers) if status.skipped_etf_tickers else 'none'}",
    ]
    if status.warnings:
        lines.append("Warnings: " + ", ".join(status.warnings))
    lines.extend(
        (
            "Next commands:",
            "python -m target_opportunity_monitor fetch-short-interest-sources --provider all",
            "python -m target_opportunity_monitor import-short-interest-source-exports",
            "python -m target_opportunity_monitor load-short-interest",
            "python -m target_opportunity_monitor compute-short-interest-signals",
            "python -m target_opportunity_monitor validate-short-interest-signals",
        )
    )
    return "\n".join(lines)


def build_short_interest_backfill_validation_text(
    config: AppConfig,
    directory: Path | None = None,
) -> str:
    validation = validate_short_interest_backfill(config, directory)
    lines = [
        "Short interest backfill validation",
        f"Source exports directory: {_display_path(validation.source_exports_dir, config.project_root)}",
        f"Source export files: {len(validation.source_export_files)}",
        f"Current source-backed coverage: {validation.current_source_backed_count}/{validation.active_equity_count}",
        f"Valid rows: {validation.valid_row_count}",
        f"Valid tickers: {', '.join(validation.valid_tickers) if validation.valid_tickers else 'none'}",
        f"Blank placeholders: {validation.blank_placeholder_count}",
        f"Invalid rows: {validation.invalid_row_count}",
        f"ETF-gated rows: {len(validation.etf_gated_rows)}",
        f"Projected source-backed coverage: {validation.projected_coverage_text}",
        f"Import apply ready: {validation.apply_ready}",
        f"Blocked import reason: {validation.blocked_import_reason or 'none'}",
    ]
    if validation.invalid_rows:
        lines.append("Invalid row detail:")
        lines.extend(_format_row_errors(row, config.project_root) for row in validation.invalid_rows)
    if validation.etf_gated_rows:
        lines.append("ETF-gated row detail:")
        lines.extend(_format_row_errors(row, config.project_root) for row in validation.etf_gated_rows)
    return "\n".join(lines)


def build_short_interest_import_preview_text(
    config: AppConfig,
    directory: Path | None = None,
) -> str:
    validation = preview_short_interest_import(config, directory)
    still_missing = tuple(
        ticker
        for ticker in validation.missing_source_tickers
        if ticker not in validation.valid_tickers
    )
    lines = [
        "Short interest import preview",
        f"Current source-backed coverage: {validation.current_source_backed_count}/{validation.active_equity_count}",
        f"Projected source-backed coverage: {validation.projected_coverage_text}",
        f"Valid rows ready to import: {validation.valid_row_count}",
        f"Valid import tickers: {', '.join(validation.valid_tickers) if validation.valid_tickers else 'none'}",
        f"Still missing after import: {', '.join(still_missing) if still_missing else 'none'}",
        f"Invalid rows: {validation.invalid_row_count}",
        f"Blank placeholders: {validation.blank_placeholder_count}",
        f"ETF-gated tickers: {', '.join(validation.skipped_etf_tickers) if validation.skipped_etf_tickers else 'none'}",
        f"Import apply ready: {validation.apply_ready}",
        f"Blocked import reason: {validation.blocked_import_reason or 'none'}",
        "Run when preview is clean:",
        "python -m target_opportunity_monitor import-short-interest-source-exports",
        "python -m target_opportunity_monitor load-short-interest",
        "python -m target_opportunity_monitor compute-short-interest-signals",
        "python -m target_opportunity_monitor validate-short-interest-signals",
    ]
    return "\n".join(lines)
