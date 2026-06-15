from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
import json
import math
from pathlib import Path
import sqlite3
import time
from contextlib import closing
import xml.etree.ElementTree as ET
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .config import AppConfig
from .sec_fundamentals import load_cik_map
from .storage import (
    Asset,
    InsiderTransactionSourceSnapshot,
    Signal,
    SignalOutcomeStatus,
    SignalStatus,
    insert_data_quality_check,
    is_scoreable_asset,
    list_assets,
    list_insider_transaction_source_snapshots,
    normalize_ticker,
    signal_outcome_statuses,
    signal_statuses_for_family,
    upsert_insider_transaction_source_snapshot,
    upsert_signal,
)


SEC_SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik}.json"
SEC_ARCHIVE_URL = "https://www.sec.gov/Archives/edgar/data/{cik}/{accession}/{document}"
SIGNAL_FAMILY = "insider_activity"
COMPOSITE_SIGNAL_NAME = "insider_activity.composite"
VALIDATION_MODEL_VERSION = "insider_activity_validation_mvp_v1"
OPEN_MARKET_BUY_SIGNAL_NAME = "insider_activity.open_market_buying"
SALE_PRESSURE_SIGNAL_NAME = "insider_activity.sale_pressure"
ROUTINE_SIGNAL_NAME = "insider_activity.routine_activity"
OPEN_MARKET_BUY_CODES = {"P"}
OPEN_MARKET_SALE_CODES = {"S"}
ROUTINE_CODES = {"A", "D", "F", "G", "M", "C", "X", "I", "J", "U", "W", "Z"}


@dataclass(frozen=True)
class InsiderFetchResult:
    fetched_count: int
    stored_count: int
    skipped_count: int
    tickers: tuple[str, ...]
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class InsiderSourceTickerStatus:
    ticker: str
    asset_type: str
    status: str
    source_backed: bool
    source_row_count: int
    latest_filing_date: str | None
    latest_transaction_date: str | None
    latest_successful_fetch_date: str | None
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class InsiderSourceStatusReport:
    active_equity_count: int
    covered_ticker_count: int
    source_backed_ticker_count: int
    source_snapshot_count: int
    latest_filing_date: str | None
    latest_transaction_date: str | None
    latest_successful_fetch_date: str | None
    covered_tickers: tuple[str, ...]
    source_backed_tickers: tuple[str, ...]
    missing_source_tickers: tuple[str, ...]
    skipped_etf_tickers: tuple[str, ...]
    no_recent_activity_tickers: tuple[str, ...]
    parse_warning_tickers: tuple[str, ...]
    sec_rate_limited_tickers: tuple[str, ...]
    stale_source_tickers: tuple[str, ...]
    statuses: tuple[InsiderSourceTickerStatus, ...]
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class InsiderTickerResult:
    ticker: str
    status: str
    asset_type: str
    composite_score: float | None
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class InsiderSignalUpdateResult:
    results: tuple[InsiderTickerResult, ...]

    @property
    def computed_count(self) -> int:
        return sum(1 for item in self.results if item.status == "computed")

    @property
    def skipped_count(self) -> int:
        return sum(1 for item in self.results if item.status == "skipped")

    @property
    def warning_count(self) -> int:
        return sum(1 for item in self.results if item.warnings)


@dataclass(frozen=True)
class InsiderActivityStatus:
    ticker: str
    asset_type: str | None
    latest_signal_date: str | None
    composite_score: float | None
    composite_direction: str | None
    signal_count: int
    confidence: float | None
    model_version: str | None
    data_warnings: str | None
    validation_status: str | None
    validation_date: str | None


def _today() -> date:
    return date.today()


def _join_unique(items: list[str] | tuple[str, ...]) -> str | None:
    cleaned = [item.strip() for item in items if item and item.strip()]
    unique = tuple(dict.fromkeys(cleaned))
    return ", ".join(unique) if unique else None


def _clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, value))


def _parse_date(value: str | None) -> date | None:
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


def _sec_request(url: str, user_agent: str) -> str:
    request = Request(
        url,
        headers={
            "User-Agent": user_agent,
            "Accept": "application/json,text/xml,application/xml,text/plain,*/*",
        },
    )
    with urlopen(request, timeout=30) as response:
        return response.read().decode("utf-8", errors="replace")


def _sleep_before_sec_document_request(config: AppConfig) -> None:
    delay = config.signals_insider_activity_sec_request_delay_seconds
    if delay > 0:
        time.sleep(delay)


def _is_sec_rate_limit_error(error: object) -> bool:
    if isinstance(error, HTTPError) and error.code == 429:
        return True
    text = str(error).lower()
    return "http error 429" in text or "too many requests" in text


def submissions_cache_path(cache_dir: Path, ticker: str, cik: str) -> Path:
    return cache_dir / "submissions" / f"{normalize_ticker(ticker)}-{cik.zfill(10)}.json"


def filing_cache_path(cache_dir: Path, ticker: str, accession_number: str) -> Path:
    accession = accession_number.replace("-", "")
    return cache_dir / "filings" / f"{normalize_ticker(ticker)}-{accession}.xml"


def _contains_ownership_xml(text: str) -> bool:
    return "<ownershipdocument" in text.lower()


def _cached_form4_document_available(
    config: AppConfig,
    ticker: str,
    accession_number: str,
) -> bool:
    path = filing_cache_path(config.insider_cache_dir, ticker, accession_number)
    if not path.exists():
        return False
    try:
        return _contains_ownership_xml(path.read_text(encoding="utf-8", errors="replace"))
    except OSError:
        return False


def fetch_sec_submissions(cik: str, user_agent: str) -> dict[str, object]:
    text = _sec_request(SEC_SUBMISSIONS_URL.format(cik=cik.zfill(10)), user_agent)
    return json.loads(text)


def load_or_fetch_sec_submissions(
    config: AppConfig,
    ticker: str,
    cik: str,
    refresh_cache: bool = False,
) -> dict[str, object]:
    path = submissions_cache_path(config.insider_cache_dir, ticker, cik)
    if path.exists() and not refresh_cache:
        return json.loads(path.read_text(encoding="utf-8"))
    payload = fetch_sec_submissions(cik, config.sec_user_agent)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return payload


def _archive_cik(cik: str) -> str:
    try:
        return str(int(cik))
    except ValueError:
        return cik.lstrip("0") or cik


def _filing_url(cik: str, accession_number: str, document: str) -> str:
    return SEC_ARCHIVE_URL.format(
        cik=_archive_cik(cik),
        accession=accession_number.replace("-", ""),
        document=document,
    )


def load_or_fetch_form4_document(
    config: AppConfig,
    ticker: str,
    cik: str,
    accession_number: str,
    primary_document: str,
    refresh_cache: bool = False,
) -> tuple[str, str]:
    path = filing_cache_path(config.insider_cache_dir, ticker, accession_number)
    if path.exists() and not refresh_cache:
        cached = path.read_text(encoding="utf-8", errors="replace")
        if _contains_ownership_xml(cached):
            document = primary_document.split("/")[-1] if "/" in primary_document else primary_document
            return cached, _filing_url(cik, accession_number, document)

    candidates: list[str] = []
    if "/" in primary_document:
        candidates.append(primary_document.split("/")[-1])
    candidates.append(primary_document)
    candidates.append(f"{accession_number}.txt")

    errors: list[str] = []
    text = ""
    source_url = _filing_url(cik, accession_number, candidates[0])
    for document in dict.fromkeys(candidates):
        source_url = _filing_url(cik, accession_number, document)
        try:
            _sleep_before_sec_document_request(config)
            candidate_text = _sec_request(source_url, config.sec_user_agent)
        except (HTTPError, URLError) as error:
            errors.append(f"{document}:{error}")
            continue
        text = candidate_text
        if _contains_ownership_xml(text):
            break
    if not text:
        raise ValueError(
            f"SEC Form 4 document request failed for {accession_number}: "
            + "; ".join(errors)
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return text, source_url


def _recent_form4_filings(
    submissions: dict[str, object],
    lookback_days: int,
    limit: int,
) -> list[dict[str, str]]:
    recent = submissions.get("filings", {})
    if not isinstance(recent, dict):
        return []
    filings = recent.get("recent", {})
    if not isinstance(filings, dict):
        return []
    forms = filings.get("form", [])
    accession_numbers = filings.get("accessionNumber", [])
    filing_dates = filings.get("filingDate", [])
    report_dates = filings.get("reportDate", [])
    primary_documents = filings.get("primaryDocument", [])
    if not all(isinstance(items, list) for items in (forms, accession_numbers, filing_dates)):
        return []

    cutoff = _today() - timedelta(days=lookback_days)
    rows: list[dict[str, str]] = []
    for index, form in enumerate(forms):
        if str(form).strip() != "4":
            continue
        filing_date = str(filing_dates[index] if index < len(filing_dates) else "")
        parsed_filing_date = _parse_date(filing_date)
        if parsed_filing_date is not None and parsed_filing_date < cutoff:
            continue
        accession_number = str(
            accession_numbers[index] if index < len(accession_numbers) else ""
        ).strip()
        primary_document = str(
            primary_documents[index] if index < len(primary_documents) else ""
        ).strip()
        if not accession_number or not primary_document:
            continue
        report_date = str(report_dates[index] if index < len(report_dates) else "").strip()
        rows.append(
            {
                "accession_number": accession_number,
                "filing_date": filing_date,
                "report_date": report_date,
                "primary_document": primary_document,
            }
        )
        if len(rows) >= limit:
            break
    return rows


def _ownership_xml(text: str) -> str:
    lowered = text.lower()
    start = lowered.find("<ownershipdocument")
    end = lowered.rfind("</ownershipdocument>")
    if start != -1 and end != -1:
        end += len("</ownershipdocument>")
        return text[start:end]
    return text


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _children(element: ET.Element, name: str) -> list[ET.Element]:
    return [child for child in list(element) if _local_name(child.tag) == name]


def _first_child(element: ET.Element | None, name: str) -> ET.Element | None:
    if element is None:
        return None
    children = _children(element, name)
    return children[0] if children else None


def _descendants(element: ET.Element, name: str) -> list[ET.Element]:
    return [child for child in element.iter() if _local_name(child.tag) == name]


def _text_path(element: ET.Element | None, path: tuple[str, ...]) -> str | None:
    current = element
    for name in path:
        current = _first_child(current, name)
        if current is None:
            return None
    text = (current.text or "").strip()
    return text or None


def _to_float(value: str | None) -> float | None:
    if value is None:
        return None
    try:
        return float(value.replace(",", ""))
    except ValueError:
        return None


def _owner_title(owner: ET.Element | None) -> str | None:
    relationship = _first_child(owner, "reportingOwnerRelationship")
    officer_title = _text_path(relationship, ("officerTitle",))
    if officer_title:
        return officer_title
    roles: list[str] = []
    for field_name, role_name in (
        ("isDirector", "director"),
        ("isOfficer", "officer"),
        ("isTenPercentOwner", "ten_percent_owner"),
        ("isOther", "other"),
    ):
        value = (_text_path(relationship, (field_name,)) or "").lower()
        if value in {"1", "true"}:
            roles.append(role_name)
    other_text = _text_path(relationship, ("otherText",))
    if other_text:
        roles.append(other_text)
    return ", ".join(roles) if roles else None


def _transaction_warnings(
    code: str | None,
    shares: float | None,
    price: float | None,
    value: float | None,
    min_transaction_value: float,
) -> tuple[str, ...]:
    warnings: list[str] = []
    if code and code.upper() in ROUTINE_CODES:
        warnings.append("routine_or_compensation_related")
    elif code and code.upper() not in OPEN_MARKET_BUY_CODES | OPEN_MARKET_SALE_CODES:
        warnings.append("non_open_market_code")
    if shares is None:
        warnings.append("missing_transaction_shares")
    if price is None:
        warnings.append("missing_transaction_price")
    if value is not None and value < min_transaction_value:
        warnings.append("small_transaction_value")
    return tuple(dict.fromkeys(warnings))


def parse_form4_transactions(
    ticker: str,
    cik: str,
    accession_number: str,
    filing_date: str,
    source_url: str,
    text: str,
    min_transaction_value: float,
) -> list[InsiderTransactionSourceSnapshot]:
    xml_text = _ownership_xml(text)
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as error:
        raise ValueError(f"Malformed Form 4 XML for {ticker} {accession_number}") from error

    owner = next(iter(_descendants(root, "reportingOwner")), None)
    owner_name = _text_path(owner, ("reportingOwnerId", "rptOwnerName")) or "unknown_owner"
    owner_title = _owner_title(owner)
    rows: list[InsiderTransactionSourceSnapshot] = []
    for transaction in _descendants(root, "nonDerivativeTransaction"):
        transaction_date = _text_path(transaction, ("transactionDate", "value"))
        code = _text_path(transaction, ("transactionCoding", "transactionCode"))
        shares = _to_float(_text_path(transaction, ("transactionAmounts", "transactionShares", "value")))
        price = _to_float(
            _text_path(transaction, ("transactionAmounts", "transactionPricePerShare", "value"))
        )
        acquired_disposed = _text_path(
            transaction,
            ("transactionAmounts", "transactionAcquiredDisposedCode", "value"),
        )
        value = shares * price if shares is not None and price is not None else None
        warnings = _transaction_warnings(code, shares, price, value, min_transaction_value)
        effective_date = transaction_date or filing_date
        rows.append(
            InsiderTransactionSourceSnapshot(
                ticker=ticker,
                cik=cik.zfill(10),
                accession_number=accession_number,
                filing_date=filing_date,
                transaction_date=transaction_date,
                owner_name=owner_name,
                owner_title=owner_title,
                transaction_code=code.upper() if code else None,
                acquired_disposed_code=(
                    acquired_disposed.upper() if acquired_disposed else None
                ),
                shares=shares,
                price=price,
                transaction_value=value,
                source_url=source_url,
                provider_status="ok",
                data_warnings=_join_unique(warnings),
                source="sec_form4",
                as_of_date=_today().isoformat(),
                effective_date=effective_date,
            )
        )
    return rows


def _active_assets(config: AppConfig, ticker: str | None = None) -> list[Asset]:
    wanted_ticker = normalize_ticker(ticker) if ticker else None
    return [
        asset
        for asset in list_assets(config.database_path)
        if is_scoreable_asset(asset) and (wanted_ticker is None or asset.ticker == wanted_ticker)
    ]


def _fetch_quality_by_ticker(config: AppConfig) -> dict[str, dict[str, str | None]]:
    if not config.database_path.exists():
        return {}
    with closing(sqlite3.connect(config.database_path)) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            """
            SELECT check_name, status, details, as_of_date, effective_date, check_timestamp
            FROM data_quality_checks
            WHERE check_name LIKE 'insider_activity_fetch:%'
            ORDER BY check_timestamp DESC, check_id DESC
            """
        ).fetchall()
    latest: dict[str, dict[str, str | None]] = {}
    for row in rows:
        ticker = str(row["check_name"]).split(":", 1)[-1]
        if ticker in latest:
            continue
        latest[ticker] = {
            "status": row["status"],
            "details": row["details"],
            "as_of_date": row["as_of_date"],
            "effective_date": row["effective_date"],
            "check_timestamp": row["check_timestamp"],
        }
    return latest


def _signal_quality_by_ticker(config: AppConfig) -> dict[str, dict[str, str | None]]:
    if not config.database_path.exists():
        return {}
    with closing(sqlite3.connect(config.database_path)) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            """
            SELECT check_name, status, details, as_of_date, effective_date, check_timestamp
            FROM data_quality_checks
            WHERE check_name LIKE 'insider_activity_signals:%'
            ORDER BY check_timestamp DESC, check_id DESC
            """
        ).fetchall()
    latest: dict[str, dict[str, str | None]] = {}
    for row in rows:
        ticker = str(row["check_name"]).split(":", 1)[-1]
        if ticker in latest:
            continue
        latest[ticker] = {
            "status": row["status"],
            "details": row["details"],
            "as_of_date": row["as_of_date"],
            "effective_date": row["effective_date"],
            "check_timestamp": row["check_timestamp"],
        }
    return latest


def _record_fetch_quality(config: AppConfig, ticker: str, warnings: tuple[str, ...]) -> None:
    insert_data_quality_check(
        config.database_path,
        check_name=f"insider_activity_fetch:{ticker}",
        status="warning" if warnings else "ok",
        details=", ".join(warnings) if warnings else "insider_activity_fetch_ok",
        source="insider_activity_fetch",
        as_of_date=_today().isoformat(),
    )


def _fetch_quality_successful_today(fetch_row: dict[str, str | None]) -> bool:
    if not fetch_row:
        return False
    fetch_date = _parse_date(fetch_row.get("as_of_date")) or _parse_date(
        fetch_row.get("check_timestamp")
    )
    if fetch_date != _today():
        return False
    details = fetch_row.get("details") or ""
    failed_tokens = (
        "sec_submissions_failed",
        "missing_cik",
        "etf_insider_activity_gated",
        "form4_parse_failed",
        "sec_rate_limited",
        "live_form4_fetch_budget_exhausted",
        "cached_submissions_missing",
    )
    return not any(token in details for token in failed_tokens)


def _rate_limit_affected_count(warning: str) -> int:
    if warning.startswith("sec_rate_limited_filings_skipped:"):
        try:
            return int(warning.rsplit(":", 1)[-1])
        except ValueError:
            return 0
    if (
        "sec_rate_limited" in warning
        or "HTTP Error 429" in warning
        or "Too Many Requests" in warning
    ):
        return 1
    return 0


def compact_warning_tokens(warnings: tuple[str, ...] | list[str]) -> tuple[str, ...]:
    rate_limited_count = 0
    no_transaction_count = 0
    parse_failed_count = 0
    same_day_skip_count = 0
    budget_skip_count = 0
    after_rate_limit_skip_count = 0
    compact: list[str] = []
    for warning in warnings:
        if not warning:
            continue
        rate_limited = _rate_limit_affected_count(warning)
        if rate_limited:
            rate_limited_count += rate_limited
            continue
        if ":no_transactions" in warning:
            no_transaction_count += 1
            continue
        if "live_form4_fetch_skipped_same_day_success" in warning:
            same_day_skip_count += 1
            continue
        if "live_form4_fetch_budget_exhausted" in warning:
            budget_skip_count += 1
            continue
        if "live_form4_fetch_skipped_after_rate_limit" in warning:
            after_rate_limit_skip_count += 1
            continue
        if "form4_parse_failed" in warning:
            parse_failed_count += 1
            continue
        compact.append(warning)
    summarized: list[str] = []
    if rate_limited_count:
        summarized.append(f"sec_rate_limited: {rate_limited_count} filings affected")
    if after_rate_limit_skip_count:
        summarized.append(
            f"live_form4_fetch_skipped_after_rate_limit: {after_rate_limit_skip_count} filings"
        )
    if budget_skip_count:
        summarized.append(
            f"live_form4_fetch_budget_exhausted: {budget_skip_count} filings"
        )
    if same_day_skip_count:
        summarized.append(
            f"live_form4_fetch_skipped_same_day_success: {same_day_skip_count} filings"
        )
    if parse_failed_count:
        summarized.append(f"form4_parse_failed: {parse_failed_count} filings")
    if no_transaction_count:
        summarized.append(f"no_transaction_filings: {no_transaction_count}")
    summarized.extend(compact)
    return tuple(dict.fromkeys(summarized))


def _compact_fetch_warnings(warnings: list[str]) -> tuple[str, ...]:
    by_ticker: dict[str, list[str]] = {}
    passthrough: list[str] = []
    for warning in warnings:
        if ":" not in warning:
            passthrough.append(warning)
            continue
        ticker, detail = warning.split(":", 1)
        by_ticker.setdefault(ticker, []).append(detail)
    compacted = list(passthrough)
    for ticker in sorted(by_ticker):
        for detail in compact_warning_tokens(by_ticker[ticker]):
            compacted.append(f"{ticker}:{detail}")
    return tuple(dict.fromkeys(compacted))


def _limited_fetch_assets(
    assets: list[Asset],
    ticker: str | None,
    max_tickers: int | None,
) -> list[Asset]:
    if ticker or max_tickers is None:
        return assets
    equity_assets = [
        asset for asset in assets if (asset.asset_type or "equity").lower() != "etf"
    ]
    etf_assets = [
        asset for asset in assets if (asset.asset_type or "equity").lower() == "etf"
    ]
    return equity_assets[: max(0, max_tickers)] + etf_assets


def fetch_insider_transactions(
    config: AppConfig,
    ticker: str | None = None,
    refresh_cache: bool = False,
    max_tickers: int | None = None,
    use_cache: bool | None = None,
) -> InsiderFetchResult:
    cik_map = load_cik_map(config.cik_map_path)
    warnings: list[str] = []
    fetched_count = 0
    stored_count = 0
    skipped_count = 0
    tickers: list[str] = []
    cache_enabled = config.signals_insider_activity_use_cache if use_cache is None else use_cache
    effective_refresh_cache = refresh_cache or not cache_enabled
    assets = _limited_fetch_assets(_active_assets(config, ticker=ticker), ticker, max_tickers)
    existing_fetch_quality = _fetch_quality_by_ticker(config)
    for asset in assets:
        ticker_warnings: list[str] = []
        asset_type = (asset.asset_type or "equity").lower()
        if asset_type == "etf":
            skipped_count += 1
            ticker_warnings.append("etf_insider_activity_gated")
            warnings.append(f"{asset.ticker}:etf_insider_activity_gated")
            _record_fetch_quality(config, asset.ticker, tuple(ticker_warnings))
            continue
        cik = cik_map.get(asset.ticker)
        if not cik:
            skipped_count += 1
            ticker_warnings.append("missing_cik")
            warnings.append(f"{asset.ticker}:missing_cik")
            _record_fetch_quality(config, asset.ticker, tuple(ticker_warnings))
            continue
        same_day_success_skip = (
            config.signals_insider_activity_skip_successful_fetch_same_day
            and not effective_refresh_cache
            and _fetch_quality_successful_today(existing_fetch_quality.get(asset.ticker, {}))
        )
        submissions_path = submissions_cache_path(config.insider_cache_dir, asset.ticker, cik)
        if same_day_success_skip and not submissions_path.exists():
            skipped_count += 1
            ticker_warnings.append("cached_submissions_missing_after_same_day_success")
            warnings.append(f"{asset.ticker}:cached_submissions_missing_after_same_day_success")
            _record_fetch_quality(config, asset.ticker, tuple(ticker_warnings))
            continue
        try:
            submissions = load_or_fetch_sec_submissions(
                config,
                asset.ticker,
                cik,
                refresh_cache=effective_refresh_cache,
            )
        except (HTTPError, URLError, ValueError, json.JSONDecodeError) as error:
            skipped_count += 1
            ticker_warnings.append(f"sec_submissions_failed:{error}")
            warnings.append(f"{asset.ticker}:sec_submissions_failed:{error}")
            _record_fetch_quality(config, asset.ticker, tuple(ticker_warnings))
            continue

        filings = _recent_form4_filings(
            submissions,
            lookback_days=config.signals_insider_activity_lookback_days,
            limit=config.signals_insider_activity_fetch_limit_per_ticker,
        )
        if not filings:
            ticker_warnings.append("no_recent_form4_filings")
            warnings.append(f"{asset.ticker}:no_recent_form4_filings")
        live_form4_fetches = 0
        rate_limit_stopped = False
        for filing_index, filing in enumerate(filings):
            cached_document = (
                not effective_refresh_cache
                and _cached_form4_document_available(
                    config,
                    asset.ticker,
                    filing["accession_number"],
                )
            )
            live_fetch_needed = effective_refresh_cache or not cached_document
            if live_fetch_needed:
                if same_day_success_skip:
                    ticker_warnings.append(
                        f"{filing['accession_number']}:live_form4_fetch_skipped_same_day_success"
                    )
                    warnings.append(
                        f"{asset.ticker}:{filing['accession_number']}:"
                        "live_form4_fetch_skipped_same_day_success"
                    )
                    continue
                if rate_limit_stopped:
                    ticker_warnings.append(
                        f"{filing['accession_number']}:live_form4_fetch_skipped_after_rate_limit"
                    )
                    warnings.append(
                        f"{asset.ticker}:{filing['accession_number']}:"
                        "live_form4_fetch_skipped_after_rate_limit"
                    )
                    continue
                if (
                    config.signals_insider_activity_max_live_form4_fetches_per_ticker >= 0
                    and live_form4_fetches
                    >= config.signals_insider_activity_max_live_form4_fetches_per_ticker
                ):
                    ticker_warnings.append(
                        f"{filing['accession_number']}:live_form4_fetch_budget_exhausted"
                    )
                    warnings.append(
                        f"{asset.ticker}:{filing['accession_number']}:"
                        "live_form4_fetch_budget_exhausted"
                    )
                    continue
                live_form4_fetches += 1
            try:
                document_text, source_url = load_or_fetch_form4_document(
                    config,
                    asset.ticker,
                    cik,
                    filing["accession_number"],
                    filing["primary_document"],
                    refresh_cache=effective_refresh_cache,
                )
                snapshots = parse_form4_transactions(
                    ticker=asset.ticker,
                    cik=cik,
                    accession_number=filing["accession_number"],
                    filing_date=filing["filing_date"],
                    source_url=source_url,
                    text=document_text,
                    min_transaction_value=config.signals_insider_activity_min_transaction_value,
                )
            except (HTTPError, URLError, ValueError) as error:
                if _is_sec_rate_limit_error(error):
                    ticker_warnings.append(
                        f"{filing['accession_number']}:form4_parse_failed:sec_rate_limited:{error}"
                    )
                    warnings.append(
                        f"{asset.ticker}:{filing['accession_number']}:"
                        f"form4_parse_failed:sec_rate_limited:{error}"
                    )
                    if config.signals_insider_activity_stop_on_rate_limit:
                        remaining = len(filings) - filing_index - 1
                        if remaining > 0:
                            ticker_warnings.append(
                                f"sec_rate_limited_filings_skipped:{remaining}"
                            )
                            warnings.append(
                                f"{asset.ticker}:sec_rate_limited_filings_skipped:{remaining}"
                            )
                        rate_limit_stopped = True
                    if config.signals_insider_activity_sec_rate_limit_cooldown_seconds > 0:
                        time.sleep(
                            config.signals_insider_activity_sec_rate_limit_cooldown_seconds
                        )
                    continue
                ticker_warnings.append(
                    f"{filing['accession_number']}:form4_parse_failed:{error}"
                )
                warnings.append(
                    f"{asset.ticker}:{filing['accession_number']}:form4_parse_failed:{error}"
                )
                continue
            fetched_count += 1
            if not snapshots:
                ticker_warnings.append(f"{filing['accession_number']}:no_transactions")
                warnings.append(f"{asset.ticker}:{filing['accession_number']}:no_transactions")
            for snapshot in snapshots:
                upsert_insider_transaction_source_snapshot(config.database_path, snapshot)
                stored_count += 1
        tickers.append(asset.ticker)
        _record_fetch_quality(config, asset.ticker, tuple(dict.fromkeys(ticker_warnings)))
    return InsiderFetchResult(
        fetched_count=fetched_count,
        stored_count=stored_count,
        skipped_count=skipped_count,
        tickers=tuple(sorted(dict.fromkeys(tickers))),
        warnings=_compact_fetch_warnings(warnings),
    )


def _max_date(values: list[str | None]) -> str | None:
    cleaned = [value for value in values if value]
    return max(cleaned) if cleaned else None


def _warning_tokens(details: str | None) -> tuple[str, ...]:
    if not details:
        return ()
    return tuple(part.strip() for part in details.split(",") if part.strip())


def insider_source_status_report(
    config: AppConfig,
    verbose: bool = False,
) -> InsiderSourceStatusReport:
    assets = _active_assets(config)
    snapshots_by_ticker: dict[str, list[InsiderTransactionSourceSnapshot]] = {}
    for snapshot in list_insider_transaction_source_snapshots(config.database_path):
        snapshots_by_ticker.setdefault(snapshot.ticker, []).append(snapshot)
    fetch_quality = _fetch_quality_by_ticker(config)
    signal_quality = _signal_quality_by_ticker(config)
    statuses: list[InsiderSourceTickerStatus] = []
    covered_tickers: list[str] = []
    source_backed_tickers: list[str] = []
    missing_source_tickers: list[str] = []
    skipped_etf_tickers: list[str] = []
    no_recent_activity_tickers: list[str] = []
    parse_warning_tickers: list[str] = []
    sec_rate_limited_tickers: list[str] = []
    stale_source_tickers: list[str] = []
    all_warnings: list[str] = []

    cutoff = _today() - timedelta(days=config.signals_insider_activity_stale_after_days)
    for asset in assets:
        asset_type = (asset.asset_type or "equity").lower()
        ticker = asset.ticker
        snapshots = snapshots_by_ticker.get(ticker, [])
        row_count = len(snapshots)
        latest_filing_date = _max_date([snapshot.filing_date for snapshot in snapshots])
        latest_transaction_date = _max_date([snapshot.transaction_date for snapshot in snapshots])
        fetch_row = fetch_quality.get(ticker, {})
        signal_row = signal_quality.get(ticker, {})
        fetch_warnings = _warning_tokens(fetch_row.get("details"))
        signal_warnings = _warning_tokens(signal_row.get("details"))
        latest_successful_fetch_date = None
        if fetch_row:
            details = fetch_row.get("details") or ""
            if (row_count > 0 or "no_recent_form4_filings" in details) and not any(
                token in details
                for token in ("sec_submissions_failed", "missing_cik", "gated")
            ):
                latest_successful_fetch_date = fetch_row.get("as_of_date") or fetch_row.get(
                    "check_timestamp"
                )

        warnings = list(dict.fromkeys(fetch_warnings + signal_warnings))
        if asset_type == "etf":
            status = "etf_gated"
            skipped_etf_tickers.append(ticker)
        else:
            source_backed = row_count > 0
            no_recent = (
                "no_recent_form4_filings" in warnings
                or "no_recent_insider_activity" in warnings
            )
            parse_warning = any(
                token_part in warning
                for warning in warnings
                for token_part in ("form4_parse_failed", "no_transactions", "Malformed")
            )
            rate_limited = any(
                token_part in warning
                for warning in warnings
                for token_part in ("sec_rate_limited", "HTTP Error 429", "Too Many Requests")
            )
            if parse_warning:
                parse_warning_tickers.append(ticker)
            if rate_limited:
                sec_rate_limited_tickers.append(ticker)
            latest_source_date = _parse_date(latest_transaction_date) or _parse_date(
                latest_filing_date
            )
            stale = latest_source_date is not None and latest_source_date < cutoff
            if source_backed:
                status = "source_backed"
                source_backed_tickers.append(ticker)
                covered_tickers.append(ticker)
                if stale:
                    status = "stale_source"
                    stale_source_tickers.append(ticker)
                    warnings.append("stale_insider_source")
            elif rate_limited:
                status = "sec_rate_limited"
            elif no_recent:
                status = "no_recent_activity"
                no_recent_activity_tickers.append(ticker)
                covered_tickers.append(ticker)
            elif parse_warning:
                status = "parse_warning"
            else:
                status = "missing_source"
                missing_source_tickers.append(ticker)
            source_backed = row_count > 0
            all_warnings.extend(f"{ticker}:{warning}" for warning in warnings)

        statuses.append(
            InsiderSourceTickerStatus(
                ticker=ticker,
                asset_type=asset_type,
                status=status,
                source_backed=row_count > 0,
                source_row_count=row_count,
                latest_filing_date=latest_filing_date,
                latest_transaction_date=latest_transaction_date,
                latest_successful_fetch_date=latest_successful_fetch_date,
                warnings=(
                    tuple(dict.fromkeys(warnings))
                    if verbose
                    else compact_warning_tokens(warnings)
                ),
            )
        )

    latest_successful_fetch = _max_date(
        [status.latest_successful_fetch_date for status in statuses]
    )
    active_equity_count = sum(1 for status in statuses if status.asset_type != "etf")
    return InsiderSourceStatusReport(
        active_equity_count=active_equity_count,
        covered_ticker_count=len(tuple(dict.fromkeys(covered_tickers))),
        source_backed_ticker_count=len(tuple(dict.fromkeys(source_backed_tickers))),
        source_snapshot_count=sum(len(rows) for rows in snapshots_by_ticker.values()),
        latest_filing_date=_max_date(
            [status.latest_filing_date for status in statuses if status.asset_type != "etf"]
        ),
        latest_transaction_date=_max_date(
            [
                status.latest_transaction_date
                for status in statuses
                if status.asset_type != "etf"
            ]
        ),
        latest_successful_fetch_date=latest_successful_fetch,
        covered_tickers=tuple(sorted(dict.fromkeys(covered_tickers))),
        source_backed_tickers=tuple(sorted(dict.fromkeys(source_backed_tickers))),
        missing_source_tickers=tuple(sorted(dict.fromkeys(missing_source_tickers))),
        skipped_etf_tickers=tuple(sorted(dict.fromkeys(skipped_etf_tickers))),
        no_recent_activity_tickers=tuple(sorted(dict.fromkeys(no_recent_activity_tickers))),
        parse_warning_tickers=tuple(sorted(dict.fromkeys(parse_warning_tickers))),
        sec_rate_limited_tickers=tuple(sorted(dict.fromkeys(sec_rate_limited_tickers))),
        stale_source_tickers=tuple(sorted(dict.fromkeys(stale_source_tickers))),
        statuses=tuple(sorted(statuses, key=lambda item: item.ticker)),
        warnings=(
            tuple(dict.fromkeys(all_warnings))
            if verbose
            else _compact_fetch_warnings(all_warnings)
        ),
    )


def build_insider_source_status_text(config: AppConfig, verbose: bool = False) -> str:
    report = insider_source_status_report(config, verbose=verbose)
    lines = [
        "Insider activity source status" + (" (verbose)" if verbose else ""),
        f"Active equity coverage: {report.covered_ticker_count}/{report.active_equity_count}",
        f"Source-backed tickers: {report.source_backed_ticker_count}/{report.active_equity_count}",
        f"ETF-gated tickers: {', '.join(report.skipped_etf_tickers) if report.skipped_etf_tickers else 'none'}",
        f"Source rows: {report.source_snapshot_count}",
        f"Latest filing date: {report.latest_filing_date or 'none'}",
        f"Latest transaction date: {report.latest_transaction_date or 'none'}",
        f"Latest successful fetch date: {report.latest_successful_fetch_date or 'none'}",
        f"No-recent-activity tickers: {', '.join(report.no_recent_activity_tickers) if report.no_recent_activity_tickers else 'none'}",
        f"Parse-warning tickers: {', '.join(report.parse_warning_tickers) if report.parse_warning_tickers else 'none'}",
        f"SEC-rate-limited tickers: {', '.join(report.sec_rate_limited_tickers) if report.sec_rate_limited_tickers else 'none'}",
        f"Stale source tickers: {', '.join(report.stale_source_tickers) if report.stale_source_tickers else 'none'}",
        f"Missing source tickers: {', '.join(report.missing_source_tickers) if report.missing_source_tickers else 'none'}",
        "Ticker | Type | Status | Rows | Latest Filing | Latest Transaction | Latest Fetch | Warnings",
    ]
    for status in report.statuses:
        lines.append(
            " | ".join(
                (
                    status.ticker,
                    status.asset_type,
                    status.status,
                    str(status.source_row_count),
                    status.latest_filing_date or "",
                    status.latest_transaction_date or "",
                    status.latest_successful_fetch_date or "",
                    ", ".join(status.warnings),
                )
            )
        )
    return "\n".join(lines)


def _record_signal_quality(config: AppConfig, ticker: str, warnings: tuple[str, ...]) -> None:
    insert_data_quality_check(
        config.database_path,
        check_name=f"insider_activity_signals:{ticker}",
        status="warning" if warnings else "ok",
        details=", ".join(warnings) if warnings else "insider_activity_signals_computed",
        source="insider_activity_signals",
        as_of_date=_today().isoformat(),
    )


def _snapshot_date(snapshot: InsiderTransactionSourceSnapshot) -> date | None:
    return _parse_date(snapshot.transaction_date) or _parse_date(snapshot.filing_date)


def _latest_source_url(snapshots: list[InsiderTransactionSourceSnapshot]) -> str | None:
    for snapshot in sorted(snapshots, key=lambda item: item.filing_date, reverse=True):
        if snapshot.source_url:
            return snapshot.source_url
    return None


def _recent_snapshots(
    config: AppConfig,
    ticker: str,
) -> list[InsiderTransactionSourceSnapshot]:
    cutoff = _today() - timedelta(days=config.signals_insider_activity_lookback_days)
    return [
        snapshot
        for snapshot in list_insider_transaction_source_snapshots(
            config.database_path,
            ticker=ticker,
        )
        if (snapshot_date := _snapshot_date(snapshot)) is not None
        and snapshot_date >= cutoff
    ]


def _is_open_market_buy(snapshot: InsiderTransactionSourceSnapshot) -> bool:
    return (
        (snapshot.transaction_code or "").upper() in OPEN_MARKET_BUY_CODES
        and (snapshot.acquired_disposed_code or "").upper() == "A"
    )


def _is_open_market_sale(snapshot: InsiderTransactionSourceSnapshot) -> bool:
    return (
        (snapshot.transaction_code or "").upper() in OPEN_MARKET_SALE_CODES
        and (snapshot.acquired_disposed_code or "").upper() == "D"
    )


def _transaction_value(snapshot: InsiderTransactionSourceSnapshot) -> float:
    return snapshot.transaction_value or 0.0


def _score_strength(total_value: float, min_value: float, multiplier: float, cap: float) -> float:
    if total_value <= 0:
        return 0.0
    base = max(min_value, 1.0)
    return min(cap, math.log10(1.0 + total_value / base) * multiplier)


def _component_signals(
    config: AppConfig,
    ticker: str,
    signal_date: str,
    buy_value: float,
    sale_value: float,
    routine_count: int,
    confidence: float,
    warnings: tuple[str, ...],
    source_url: str | None,
    notes: str,
) -> list[Signal]:
    min_value = config.signals_insider_activity_min_transaction_value
    buy_score = _clamp(50.0 + _score_strength(buy_value, min_value, 12.0, 35.0))
    sale_score = _clamp(50.0 - _score_strength(sale_value, min_value, 7.0, 25.0))
    routine_score = 50.0
    shared = {
        "ticker": ticker,
        "signal_date": signal_date,
        "signal_family": SIGNAL_FAMILY,
        "model_version": config.signals_insider_activity_model_version,
        "confidence": confidence,
        "data_warnings": _join_unique(warnings),
        "source_url": source_url,
        "notes": notes,
        "as_of_date": _today().isoformat(),
        "effective_date": signal_date,
    }
    return [
        Signal(
            signal_name=OPEN_MARKET_BUY_SIGNAL_NAME,
            value=buy_value,
            score=buy_score,
            direction=_direction_from_score(buy_score),
            reason_code="open_market_buying",
            source="insider_activity",
            **shared,
        ),
        Signal(
            signal_name=SALE_PRESSURE_SIGNAL_NAME,
            value=sale_value,
            score=sale_score,
            direction=_direction_from_score(sale_score),
            reason_code="sale_pressure",
            source="insider_activity",
            **shared,
        ),
        Signal(
            signal_name=ROUTINE_SIGNAL_NAME,
            value=float(routine_count),
            score=routine_score,
            direction="neutral",
            reason_code="routine_activity",
            source="insider_activity",
            **shared,
        ),
    ]


def _compute_ticker_insider_signals(
    config: AppConfig,
    asset: Asset,
) -> InsiderTickerResult:
    ticker = asset.ticker
    asset_type = (asset.asset_type or "equity").lower()
    if asset_type == "etf":
        warnings = ("etf_insider_activity_gated",)
        _record_signal_quality(config, ticker, warnings)
        return InsiderTickerResult(ticker, "skipped", "etf", None, warnings)

    snapshots = _recent_snapshots(config, ticker)
    warnings: list[str] = []
    if config.signals_insider_activity_shadow_mode:
        warnings.append("insider_activity_shadow_mode")
    if not snapshots:
        warnings.append("no_recent_insider_activity")
        signal_date = _today().isoformat()
        confidence = 45.0
        composite_score = 50.0
        upsert_signal(
            config.database_path,
            Signal(
                ticker=ticker,
                signal_date=signal_date,
                signal_name=COMPOSITE_SIGNAL_NAME,
                signal_family=SIGNAL_FAMILY,
                value=0.0,
                score=composite_score,
                direction="neutral",
                reason_code="no_recent_insider_activity",
                source="insider_activity",
                model_version=config.signals_insider_activity_model_version,
                confidence=confidence,
                data_warnings=_join_unique(warnings),
                as_of_date=_today().isoformat(),
                effective_date=signal_date,
            )
        )
        _record_signal_quality(config, ticker, tuple(warnings))
        return InsiderTickerResult(ticker, "computed", "equity", composite_score, tuple(warnings))

    latest_snapshot_date = max(
        snapshot_date for snapshot in snapshots if (snapshot_date := _snapshot_date(snapshot))
    )
    signal_date = latest_snapshot_date.isoformat()
    min_value = config.signals_insider_activity_min_transaction_value
    buys = [
        snapshot
        for snapshot in snapshots
        if _is_open_market_buy(snapshot) and _transaction_value(snapshot) >= min_value
    ]
    sales = [
        snapshot
        for snapshot in snapshots
        if _is_open_market_sale(snapshot) and _transaction_value(snapshot) >= min_value
    ]
    routine = [
        snapshot
        for snapshot in snapshots
        if not _is_open_market_buy(snapshot) and not _is_open_market_sale(snapshot)
    ]
    small_transactions = [
        snapshot
        for snapshot in snapshots
        if (snapshot.transaction_value or 0.0) > 0
        and (snapshot.transaction_value or 0.0) < min_value
    ]
    buy_value = sum(_transaction_value(snapshot) for snapshot in buys)
    sale_value = sum(_transaction_value(snapshot) for snapshot in sales)
    owner_count = len({snapshot.owner_name for snapshot in buys + sales if snapshot.owner_name})

    if routine:
        warnings.append("routine_or_compensation_related")
    if small_transactions:
        warnings.append("small_transaction_value")
    if owner_count == 1 and (buy_value > 0 or sale_value > 0):
        warnings.append("single_insider_only")
    latest_age = (_today() - latest_snapshot_date).days
    if latest_age > config.signals_insider_activity_stale_after_days:
        warnings.append("stale_insider_activity")
    if buy_value == 0 and sale_value == 0:
        warnings.append("no_meaningful_open_market_activity")

    buy_strength = _score_strength(buy_value, min_value, 12.0, 35.0)
    sale_strength = _score_strength(sale_value, min_value, 7.0, 25.0)
    composite_score = _clamp(50.0 + buy_strength - sale_strength)
    confidence = 45.0 + min(owner_count, 3) * 10.0 + min(len(buys) + len(sales), 5) * 4.0
    if routine:
        confidence -= 5.0
    if latest_age > config.signals_insider_activity_stale_after_days:
        confidence -= 15.0
    confidence = _clamp(confidence)
    source_url = _latest_source_url(snapshots)
    notes = (
        f"buy_value={buy_value:.2f}; sale_value={sale_value:.2f}; "
        f"open_market_buy_count={len(buys)}; open_market_sale_count={len(sales)}; "
        f"routine_count={len(routine)}; owner_count={owner_count}"
    )

    final_warnings = tuple(dict.fromkeys(warnings))
    for signal in _component_signals(
        config,
        ticker,
        signal_date,
        buy_value,
        sale_value,
        len(routine),
        confidence,
        final_warnings,
        source_url,
        notes,
    ):
        upsert_signal(config.database_path, signal)
    upsert_signal(
        config.database_path,
        Signal(
            ticker=ticker,
            signal_date=signal_date,
            signal_name=COMPOSITE_SIGNAL_NAME,
            signal_family=SIGNAL_FAMILY,
            value=buy_value - sale_value,
            score=composite_score,
            direction=_direction_from_score(composite_score),
            reason_code="insider_activity_composite",
            source="insider_activity",
            model_version=config.signals_insider_activity_model_version,
            confidence=confidence,
            data_warnings=_join_unique(final_warnings),
            source_url=source_url,
            notes=notes,
            as_of_date=_today().isoformat(),
            effective_date=signal_date,
        )
    )
    _record_signal_quality(config, ticker, final_warnings)
    return InsiderTickerResult(ticker, "computed", "equity", composite_score, final_warnings)


def compute_insider_signals(
    config: AppConfig,
    ticker: str | None = None,
) -> InsiderSignalUpdateResult:
    results = tuple(_compute_ticker_insider_signals(config, asset) for asset in _active_assets(config, ticker))
    return InsiderSignalUpdateResult(results=results)


def insider_statuses(config: AppConfig) -> list[InsiderActivityStatus]:
    signal_status_by_ticker: dict[str, SignalStatus] = {
        status.ticker: status
        for status in signal_statuses_for_family(
            config.database_path,
            signal_family=SIGNAL_FAMILY,
            composite_signal_name=COMPOSITE_SIGNAL_NAME,
            quality_check_prefix="insider_activity_signals",
        )
    }
    validation_by_ticker: dict[str, SignalOutcomeStatus] = {
        status.ticker: status
        for status in signal_outcome_statuses(
            config.database_path,
            signal_family=SIGNAL_FAMILY,
            signal_name=COMPOSITE_SIGNAL_NAME,
        )
    }
    rows: list[InsiderActivityStatus] = []
    for ticker, status in sorted(signal_status_by_ticker.items()):
        validation = validation_by_ticker.get(ticker)
        rows.append(
            InsiderActivityStatus(
                ticker=ticker,
                asset_type=status.asset_type,
                latest_signal_date=status.latest_signal_date,
                composite_score=status.composite_score,
                composite_direction=status.composite_direction,
                signal_count=status.signal_count,
                confidence=status.confidence,
                model_version=status.model_version,
                data_warnings=status.data_warnings,
                validation_status=validation.outcome_status if validation else None,
                validation_date=validation.outcome_date if validation else None,
            )
        )
    return rows
