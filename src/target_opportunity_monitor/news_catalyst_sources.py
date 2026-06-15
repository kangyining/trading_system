from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import date, datetime, timedelta
import json
import os
from pathlib import Path
import sqlite3
import time
from typing import Iterable
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .config import AppConfig
from .news_catalysts import NEWS_CATALYST_HEADERS, ensure_news_catalyst_csv_header
from .storage import (
    Asset,
    NewsCatalystAggregate,
    NewsCatalystSourceSnapshot,
    delete_news_catalyst_aggregate,
    is_scoreable_asset,
    list_assets,
    list_news_catalyst_aggregates,
    list_news_catalyst_source_snapshots,
    normalize_ticker,
    upsert_news_catalyst_aggregate,
    upsert_news_catalyst_source_snapshot,
)


SOURCE_EXPORT_HEADERS = (
    "ticker",
    "signal_date",
    "source",
    "source_url",
    "headline_or_event",
    "article_datetime",
    "event_date",
    "topic",
    "summary",
    "sentiment_score",
    "catalyst_score",
    "urgency_score",
    "relevance_score",
    "confidence",
    "notes",
    "capture_method",
)
REQUIRED_SOURCE_EXPORT_COLUMNS = {
    "ticker",
    "signal_date",
    "source",
    "source_url",
    "headline_or_event",
}
NUMERIC_SOURCE_EXPORT_FIELDS = {
    "sentiment_score",
    "catalyst_score",
    "urgency_score",
    "relevance_score",
    "confidence",
}
AGGREGATE_NUMERIC_FIELDS = (
    "sentiment_score",
    "catalyst_score",
    "urgency_score",
)
SOURCE_EXPORT_TEMPLATE_FILES = (
    "news_catalyst_source_export.csv",
    "alpha_vantage_manual.csv",
    "marketaux_manual.csv",
    "eodhd_manual.csv",
    "finnhub_manual.csv",
    "fmp_manual.csv",
    "serenity_manual.csv",
    "kobeissi_letter_manual.csv",
    "truth_social_manual.csv",
    "x_manual.csv",
    "licensed_provider_manual.csv",
)
COVERAGE_QUEUE_EXPORT_FILE = "news_catalyst_missing_coverage_queue.csv"
PROVIDER_UPGRADE_QUEUE_EXPORT_FILE = "news_catalyst_provider_upgrade_queue.csv"
PROVIDER_NATIVE_BACKFILL_DIRNAME = "provider_native_backfill"
PROVIDER_NATIVE_BACKFILL_EXPORT_FILE = "news_catalyst_provider_native_backfill.csv"
PROVIDER_NATIVE_BACKFILL_README_FILE = "README.md"
NORMALIZED_PROVIDER_BACKFILL_FILE_TEMPLATE = "normalized_{provider}_provider_native.csv"
COVERAGE_PLAN_MODES = {"missing", "provider-upgrade", "all"}
PROVIDER_EXPORT_NORMALIZATION_PROVIDERS = {
    "marketaux",
    "eodhd",
    "x",
    "licensed",
    "generic",
}
PROVIDER_EXPORT_NORMALIZED_SOURCE = {
    "marketaux": "marketaux_export",
    "eodhd": "eodhd_export",
    "x": "x_export",
    "licensed": "licensed_news_provider_export",
}
SOURCE_WEIGHTS = {
    "alpha_vantage": 1.0,
    "marketaux": 1.0,
    "eodhd": 0.9,
    "finnhub": 0.8,
    "finnhub_sentiment": 0.8,
    "fmp": 0.7,
    "financial_modeling_prep": 0.7,
    "x_recent_search": 0.35,
    "truth_social_public": 0.25,
    "news_text_backfill": 0.35,
    "marketaux_export": 1.0,
    "eodhd_export": 0.9,
    "x_export": 0.7,
    "licensed_news_provider_export": 0.9,
    "licensed_provider_manual": 0.9,
    "user_provider_export": 0.9,
    "provider_export": 0.9,
    "manual_provider_export": 0.9,
    "manual_capture": 0.6,
    "source_export": 0.6,
    "news_catalyst_aggregate": 1.0,
}
PRIMARY_SENTIMENT_SOURCES = {
    "alpha_vantage",
    "marketaux",
    "eodhd",
    "finnhub",
    "finnhub_sentiment",
    "fmp",
    "marketaux_export",
    "eodhd_export",
    "x_export",
    "licensed_news_provider_export",
    "user_provider_export",
}
PROVIDER_NATIVE_EXPORT_SOURCES = {
    "marketaux_export",
    "eodhd_export",
    "x_export",
    "licensed_news_provider_export",
    "user_provider_export",
}
PROVIDER_NATIVE_SMOKE_TEST_PROVIDERS = ("marketaux", "eodhd", "x_recent_search")
HEADLINE_ONLY_WEIGHT = 0.0
HTTP_TIMEOUT_SECONDS = 12
ALPHA_VANTAGE_REQUEST_DELAY_SECONDS = 1.1
TRUTH_SOCIAL_ACCOUNT = "realDonaldTrump"

POSITIVE_TEXT_TERMS = {
    "accelerate",
    "beat",
    "boost",
    "breakthrough",
    "bullish",
    "contract",
    "expand",
    "growth",
    "guidance raised",
    "innovation",
    "launch",
    "outperform",
    "profit",
    "record",
    "strong",
    "upgrade",
    "wins",
}
NEGATIVE_TEXT_TERMS = {
    "bearish",
    "cut",
    "decline",
    "delay",
    "downgrade",
    "fine",
    "fraud",
    "investigation",
    "lawsuit",
    "miss",
    "probe",
    "recall",
    "risk",
    "slows",
    "weak",
}
CATALYST_TEXT_TERMS = {
    "acquisition",
    "approval",
    "buyback",
    "contract",
    "earnings",
    "fda",
    "guidance",
    "launch",
    "merger",
    "partnership",
    "product",
    "regulatory",
    "tariff",
}
URGENCY_TEXT_TERMS = {
    "breaking",
    "today",
    "now",
    "immediate",
    "urgent",
    "just announced",
    "pre-market",
    "after hours",
}


@dataclass(frozen=True)
class NewsCatalystSourceRow:
    ticker: str
    signal_date: str
    source: str
    source_url: str
    headline_or_event: str
    article_datetime: str | None = None
    event_date: str | None = None
    topic: str | None = None
    summary: str | None = None
    sentiment_score: float | None = None
    catalyst_score: float | None = None
    urgency_score: float | None = None
    relevance_score: float | None = None
    confidence: float | None = None
    notes: str | None = None
    capture_method: str = "manual_capture"


@dataclass(frozen=True)
class NewsCatalystSourceImportResult:
    source_dir: Path
    source_files: tuple[Path, ...]
    source_row_count: int
    imported_count: int
    skipped_count: int
    tickers: tuple[str, ...]
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class NewsCatalystAggregateResult:
    aggregate_count: int
    written_row_count: int
    tickers: tuple[str, ...]
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class NewsCatalystTextBackfillResult:
    derived_count: int
    skipped_count: int
    tickers: tuple[str, ...]
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class NewsCatalystProviderFetchResult:
    provider: str
    fetched_count: int
    stored_count: int
    skipped_count: int
    tickers: tuple[str, ...]
    warnings: tuple[str, ...]
    cache_hits: int = 0
    cache_misses: int = 0
    cache_writes: int = 0
    live_requests: int = 0
    budget_exhausted: bool = False
    numeric_stored_count: int = 0


@dataclass(frozen=True)
class NewsCatalystProviderSmokeTestResult:
    provider: str
    ticker: str
    status: str
    fetched_count: int
    stored_count: int
    numeric_stored_count: int
    warnings: tuple[str, ...]
    live_requests: int = 0
    cache_hits: int = 0
    cache_misses: int = 0


@dataclass(frozen=True)
class NewsCatalystProviderBackfillExportResult:
    output_dir: Path
    template_path: Path
    readme_path: Path
    ticker_count: int
    tickers: tuple[str, ...]
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class NewsCatalystProviderBackfillValidationResult:
    source_dir: Path
    source_files: tuple[Path, ...]
    total_row_count: int
    valid_row_count: int
    blank_placeholder_count: int
    invalid_row_count: int
    unsupported_ticker_count: int
    etf_gated_count: int
    valid_tickers: tuple[str, ...]
    blank_placeholder_tickers: tuple[str, ...]
    invalid_tickers: tuple[str, ...]
    unsupported_tickers: tuple[str, ...]
    etf_gated_tickers: tuple[str, ...]
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class NewsCatalystProviderBackfillDiagnostic:
    ticker: str
    classification: str
    current_provider_native: bool
    text_derived_only: bool
    valid_rows: int
    blank_placeholder_rows: int
    invalid_rows: int
    warnings: tuple[str, ...]
    recommended_action: str


@dataclass(frozen=True)
class NewsCatalystProviderUpgradePreview:
    validation: NewsCatalystProviderBackfillValidationResult
    active_equity_count: int
    current_provider_native_ticker_count: int
    current_provider_native_tickers: tuple[str, ...]
    text_derived_only_tickers: tuple[str, ...]
    valid_backfill_tickers: tuple[str, ...]
    projected_provider_native_ticker_count: int
    projected_provider_native_tickers: tuple[str, ...]
    still_blocked_tickers: tuple[str, ...]
    next_commands: tuple[str, ...]
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class NewsCatalystProviderExportNormalizationResult:
    provider: str
    source_path: Path
    output_path: Path
    input_row_count: int
    normalized_count: int
    skipped_count: int
    tickers: tuple[str, ...]
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class NewsCatalystProviderBackfillApplyStatus:
    preview: NewsCatalystProviderUpgradePreview
    allow_partial: bool
    backfill_apply_ready: bool
    projected_upgrade_delta: int
    valid_upgrade_tickers: tuple[str, ...]
    blocked_apply_reason: str | None
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class NewsCatalystProviderBackfillApplyResult:
    confirmed: bool
    applied: bool
    status: NewsCatalystProviderBackfillApplyStatus
    imported_count: int = 0
    aggregate_count: int = 0
    loaded_row_count: int = 0
    computed_count: int = 0
    validation_updated_count: int = 0
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class NewsCatalystProviderUpgradeStatus:
    status: str
    active_equity_count: int
    provider_native_ticker_count: int
    text_derived_only_ticker_count: int
    provider_native_tickers: tuple[str, ...]
    text_derived_only_tickers: tuple[str, ...]
    current_queue_tickers: tuple[str, ...]
    available_providers: tuple[str, ...]
    unavailable_providers: tuple[str, ...]
    missing_key_providers: tuple[str, ...]
    latest_provider_failures: tuple[str, ...]
    provider_blockers: tuple[str, ...]
    latest_provider_native_source_date: str | None
    provider_native_rejected_row_count: int
    provider_native_rejected_tickers: tuple[str, ...]
    provider_native_rejected_warnings: tuple[str, ...]
    provider_statuses: tuple["NewsCatalystProviderStatus", ...]
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class NewsCatalystProviderStatus:
    provider: str
    enabled: bool
    available: bool
    status: str
    details: str
    cache_file_count: int = 0
    latest_cache_at: str | None = None
    numeric_snapshot_count: int = 0
    headline_only_snapshot_count: int = 0
    latest_warning: str | None = None


@dataclass(frozen=True)
class NewsCatalystSourceTickerStatus:
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
    has_provider_numeric: bool = False
    has_text_derived_numeric: bool = False
    provider_native_upgrade_needed: bool = False


@dataclass(frozen=True)
class NewsCatalystSourceStatusReport:
    source_exports_dir: Path
    cache_dir: Path
    cache_file_count: int
    latest_cache_at: str | None
    provider_numeric_snapshot_count: int
    text_derived_snapshot_count: int
    provider_numeric_ticker_count: int
    text_derived_ticker_count: int
    total_numeric_ticker_count: int
    numeric_snapshot_count: int
    headline_only_snapshot_count: int
    source_snapshot_count: int
    aggregate_count: int
    news_catalysts_path: Path
    news_catalysts_exists: bool
    active_equity_count: int
    source_backed_ticker_count: int
    source_backed_tickers: tuple[str, ...]
    missing_source_tickers: tuple[str, ...]
    missing_numeric_tickers: tuple[str, ...]
    provider_numeric_tickers: tuple[str, ...]
    text_derived_tickers: tuple[str, ...]
    provider_native_upgrade_tickers: tuple[str, ...]
    latest_provider_native_source_date: str | None
    provider_native_rejected_row_count: int
    provider_native_rejected_tickers: tuple[str, ...]
    provider_native_rejected_warnings: tuple[str, ...]
    stale_tickers: tuple[str, ...]
    skipped_etf_tickers: tuple[str, ...]
    missing_source_field_tickers: tuple[str, ...]
    provider_statuses: tuple[NewsCatalystProviderStatus, ...]
    statuses: tuple[NewsCatalystSourceTickerStatus, ...]
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class NewsCatalystCoveragePlanItem:
    ticker: str
    asset_type: str
    coverage_status: str
    priority: int
    reason: str
    stale: bool
    source_count: int = 0
    aggregate_confidence: float | None = None
    provider_warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class NewsCatalystCoveragePlan:
    generated_at: str
    mode: str
    max_tickers: int
    template_path: Path
    missing_template_path: Path
    provider_upgrade_template_path: Path
    planned_tickers: tuple[str, ...]
    missing_tickers: tuple[str, ...]
    missing_numeric_tickers: tuple[str, ...]
    provider_native_upgrade_tickers: tuple[str, ...]
    stale_tickers: tuple[str, ...]
    source_backed_tickers: tuple[str, ...]
    provider_warning_summary: tuple[str, ...]
    queue_template_tickers: tuple[str, ...]
    queue_template_stale: bool
    missing_queue_template_tickers: tuple[str, ...]
    missing_queue_template_stale: bool
    provider_upgrade_queue_template_tickers: tuple[str, ...]
    provider_upgrade_queue_template_stale: bool
    items: tuple[NewsCatalystCoveragePlanItem, ...]
    warnings: tuple[str, ...]


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


@dataclass
class _ProviderFetchState:
    live_budget: int
    cache_hits: int = 0
    cache_misses: int = 0
    cache_writes: int = 0
    live_requests: int = 0
    budget_exhausted: bool = False


@dataclass(frozen=True)
class _CachedProviderPayload:
    payload: object
    cached_at: str
    stale: bool
    path: Path


def _provider_cache_dir(config: AppConfig, provider: str) -> Path:
    return config.news_catalyst_cache_dir / _source_key(provider)


def _provider_cache_path(config: AppConfig, provider: str, ticker: str) -> Path:
    safe_ticker = normalize_ticker(ticker) or "UNKNOWN"
    return _provider_cache_dir(config, provider) / f"{safe_ticker}.json"


def _parse_cached_at(value: object) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value))
    except ValueError:
        return None


def _read_provider_cache(
    config: AppConfig,
    provider: str,
    ticker: str,
) -> _CachedProviderPayload | None:
    path = _provider_cache_path(config, provider, ticker)
    if not path.exists():
        return None
    try:
        wrapper = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(wrapper, dict) or "payload" not in wrapper:
        return None
    cached_at = str(wrapper.get("cached_at") or "")
    parsed_cached_at = _parse_cached_at(cached_at)
    stale = True
    if parsed_cached_at is not None:
        max_age = timedelta(hours=config.signals_news_catalyst_cache_stale_hours)
        stale = datetime.now() - parsed_cached_at > max_age
    return _CachedProviderPayload(
        payload=wrapper["payload"],
        cached_at=cached_at,
        stale=stale,
        path=path,
    )


def _write_provider_cache(
    config: AppConfig,
    provider: str,
    ticker: str,
    payload: object,
) -> None:
    path = _provider_cache_path(config, provider, ticker)
    path.parent.mkdir(parents=True, exist_ok=True)
    wrapper = {
        "provider": _source_key(provider),
        "ticker": normalize_ticker(ticker),
        "cached_at": datetime.now().isoformat(timespec="seconds"),
        "payload": payload,
    }
    path.write_text(json.dumps(wrapper, ensure_ascii=True, indent=2), encoding="utf-8")


def _cache_files(config: AppConfig, provider: str | None = None) -> tuple[Path, ...]:
    root = _provider_cache_dir(config, provider) if provider else config.news_catalyst_cache_dir
    if not root.exists():
        return ()
    return tuple(sorted(path for path in root.rglob("*.json") if path.is_file()))


def _latest_cache_at(config: AppConfig, provider: str | None = None) -> str | None:
    latest: str | None = None
    for path in _cache_files(config, provider):
        try:
            wrapper = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        cached_at = str(wrapper.get("cached_at") or "") if isinstance(wrapper, dict) else ""
        if cached_at and (latest is None or cached_at > latest):
            latest = cached_at
    return latest


def _live_request_budget(config: AppConfig, max_tickers: int | None) -> int:
    budget = (
        config.signals_news_catalyst_provider_request_budget
        if max_tickers is None
        else max_tickers
    )
    return max(0, int(budget))


def _cache_enabled(config: AppConfig, use_cache: bool | None) -> bool:
    return config.signals_news_catalyst_use_cache if use_cache is None else use_cache


def ensure_news_catalyst_source_export_header(path: Path) -> None:
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


def ensure_news_catalyst_source_export_templates(config: AppConfig) -> tuple[Path, ...]:
    config.news_catalyst_source_exports_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    for filename in SOURCE_EXPORT_TEMPLATE_FILES:
        path = config.news_catalyst_source_exports_dir / filename
        ensure_news_catalyst_source_export_header(path)
        paths.append(path)
    return tuple(paths)


def export_news_catalyst_provider_backfill(
    config: AppConfig,
    output_dir: Path | None = None,
) -> NewsCatalystProviderBackfillExportResult:
    target_dir = output_dir or provider_native_backfill_dir(config)
    target_dir.mkdir(parents=True, exist_ok=True)
    template_path = target_dir / PROVIDER_NATIVE_BACKFILL_EXPORT_FILE
    readme_path = target_dir / PROVIDER_NATIVE_BACKFILL_README_FILE

    report = news_catalyst_source_status_report(config)
    tickers = tuple(sorted(report.provider_native_upgrade_tickers))
    reasons = {
        ticker: "provider_native_news_catalyst_upgrade_needed" for ticker in tickers
    }
    with template_path.open("w", newline="", encoding="utf-8") as output:
        writer = csv.DictWriter(output, fieldnames=SOURCE_EXPORT_HEADERS)
        writer.writeheader()
        for ticker in tickers:
            writer.writerow(_coverage_template_row(ticker, reasons[ticker]))

    readme_path.write_text(
        "\n".join(
            (
                "# News/Catalyst Provider-Native Backfill",
                "",
                "Fill this package only with source-backed provider-native numeric data.",
                "Do not fabricate sentiment, catalyst, urgency, relevance, or confidence values.",
                "",
                "Accepted provider-native source labels:",
                "- marketaux_export",
                "- eodhd_export",
                "- x_export",
                "- licensed_news_provider_export",
                "- user_provider_export",
                "",
                "Required fields for every completed row:",
                "- ticker",
                "- signal_date",
                "- source",
                "- source_url",
                "- headline_or_event",
                "- at least one of sentiment_score, catalyst_score, or urgency_score",
                "",
                "Optional numeric fields are relevance_score and confidence.",
                "Numeric fields must be 0-100 scores from the provider/export.",
                "Leave unsupported fields blank rather than guessing.",
                "",
                "After editing, run:",
                "python -m target_opportunity_monitor import-news-catalyst-source-exports",
                "python -m target_opportunity_monitor aggregate-news-catalyst-sources",
                "python -m target_opportunity_monitor load-news-catalysts",
                "python -m target_opportunity_monitor compute-news-catalyst-signals",
                "python -m target_opportunity_monitor validate-news-catalyst-signals",
                "",
                "Current text-derived-only tickers:",
                ", ".join(tickers) if tickers else "none",
                "",
            )
        ),
        encoding="utf-8",
    )

    warnings: list[str] = []
    if not tickers:
        warnings.append("no_provider_native_backfill_needed")

    return NewsCatalystProviderBackfillExportResult(
        output_dir=target_dir,
        template_path=template_path,
        readme_path=readme_path,
        ticker_count=len(tickers),
        tickers=tickers,
        warnings=tuple(warnings),
    )


def _normalize_provider_export_provider(provider: str) -> str:
    normalized = (provider or "").strip().lower().replace("-", "_")
    if normalized not in PROVIDER_EXPORT_NORMALIZATION_PROVIDERS:
        raise ValueError(
            "news/catalyst provider export normalization provider must be one of: "
            + ", ".join(sorted(PROVIDER_EXPORT_NORMALIZATION_PROVIDERS))
        )
    return normalized


def _normalized_provider_backfill_path(config: AppConfig, provider: str) -> Path:
    normalized = _normalize_provider_export_provider(provider)
    return provider_native_backfill_dir(config) / NORMALIZED_PROVIDER_BACKFILL_FILE_TEMPLATE.format(
        provider=normalized
    )


def _first_row_text(row: dict[str, str | None], aliases: tuple[str, ...]) -> str:
    for alias in aliases:
        value = row.get(alias)
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return ""


def _parse_provider_export_date(value: str) -> str | None:
    text = value.strip()
    if not text:
        return None
    try:
        return date.fromisoformat(text[:10]).isoformat()
    except ValueError:
        pass
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        return parsed.date().isoformat()
    except ValueError:
        pass
    try:
        numeric = float(text)
    except ValueError:
        return None
    try:
        parsed = datetime.fromtimestamp(numeric)
    except (OSError, ValueError):
        return None
    return parsed.date().isoformat()


def _parse_provider_export_datetime(value: str) -> str | None:
    text = value.strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).isoformat()
    except ValueError:
        pass
    try:
        numeric = float(text)
    except ValueError:
        return None
    try:
        return datetime.fromtimestamp(numeric).isoformat()
    except (OSError, ValueError):
        return None


def _score_from_provider_export_value(
    value: str,
    *,
    allow_negative_polarity: bool,
) -> float | None:
    text = value.strip()
    if not text:
        return None
    try:
        parsed = float(text)
    except ValueError:
        return None
    if allow_negative_polarity and -1.0 <= parsed <= 1.0:
        return _clamp_score((parsed + 1.0) * 50.0)
    if not allow_negative_polarity and 0.0 <= parsed <= 1.0:
        return _clamp_score(parsed * 100.0)
    if 0.0 <= parsed <= 100.0:
        return _clamp_score(parsed)
    return None


def _score_from_provider_export_aliases(
    row: dict[str, str | None],
    aliases: tuple[str, ...],
    *,
    allow_negative_polarity: bool,
) -> float | None:
    for alias in aliases:
        raw_value = row.get(alias)
        if raw_value is None:
            continue
        score = _score_from_provider_export_value(
            str(raw_value),
            allow_negative_polarity=allow_negative_polarity,
        )
        if score is not None:
            return score
    return None


def _provider_export_source_label(provider: str, row: dict[str, str | None]) -> str:
    if provider == "generic":
        source_key = _source_key(row.get("source"))
        if source_key in PROVIDER_NATIVE_EXPORT_SOURCES:
            return source_key
        return "user_provider_export"
    return PROVIDER_EXPORT_NORMALIZED_SOURCE.get(provider, "user_provider_export")


def normalize_news_catalyst_provider_export(
    config: AppConfig,
    provider: str,
    source_path: Path,
) -> NewsCatalystProviderExportNormalizationResult:
    normalized_provider = _normalize_provider_export_provider(provider)
    if not source_path.exists():
        raise ValueError(f"Provider export file does not exist: {source_path}")

    text = source_path.read_text(encoding="utf-8-sig")
    reader = csv.DictReader(text.splitlines())
    if not reader.fieldnames:
        raise ValueError("Provider export CSV missing header.")

    all_assets, equity_assets, etf_assets = _asset_maps(config)
    report = news_catalyst_source_status_report(config)
    upgrade_tickers = set(report.provider_native_upgrade_tickers)
    already_provider_native = set(report.provider_numeric_tickers)
    output_path = _normalized_provider_backfill_path(config, normalized_provider)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    warnings: list[str] = []
    normalized_rows: list[dict[str, str]] = []
    input_row_count = 0

    for row_number, row in enumerate(reader, start=2):
        if not any((value or "").strip() for value in row.values()):
            continue
        input_row_count += 1
        source_row = {key: (value or "") for key, value in row.items()}
        ticker = normalize_ticker(
            _first_row_text(
                source_row,
                ("ticker", "symbol", "entity_symbol", "entity_ticker"),
            )
        )
        label = ticker or f"row_{row_number}"
        if not ticker:
            warnings.append(f"{label}:missing_ticker")
            continue
        if ticker in etf_assets:
            warnings.append(f"{ticker}:etf_news_catalyst_gated")
            continue
        if ticker not in all_assets or ticker not in equity_assets:
            warnings.append(f"{ticker}:inactive_or_unknown_ticker")
            continue
        if ticker in already_provider_native:
            warnings.append(f"{ticker}:already_provider_native")
            continue
        if ticker not in upgrade_tickers:
            warnings.append(f"{ticker}:not_in_provider_native_upgrade_queue")
            continue

        raw_signal_date = _first_row_text(
            source_row,
            ("signal_date", "date", "published_at", "publishedAt", "article_datetime", "datetime"),
        )
        signal_date = _parse_provider_export_date(raw_signal_date)
        if signal_date is None:
            warnings.append(f"{ticker}:malformed_or_missing_signal_date")
            continue
        source_url = _first_row_text(source_row, ("source_url", "url", "link", "article_url"))
        if not source_url:
            warnings.append(f"{ticker}:missing_source_url")
            continue
        headline = _first_row_text(
            source_row,
            ("headline_or_event", "headline", "title", "event", "description"),
        )
        if not headline:
            warnings.append(f"{ticker}:missing_headline_or_event")
            continue

        sentiment_score = _score_from_provider_export_aliases(
            source_row,
            (
                "sentiment_score",
                "sentiment",
                "sentimentScore",
                "entity_sentiment_score",
                "entity_sentiment",
                "polarity",
                "sentiment_polarity",
            ),
            allow_negative_polarity=True,
        )
        catalyst_score = _score_from_provider_export_aliases(
            source_row,
            ("catalyst_score", "catalyst", "event_score", "catalystScore"),
            allow_negative_polarity=True,
        )
        urgency_score = _score_from_provider_export_aliases(
            source_row,
            ("urgency_score", "urgency", "urgencyScore"),
            allow_negative_polarity=True,
        )
        if not any(score is not None for score in (sentiment_score, catalyst_score, urgency_score)):
            warnings.append(f"{ticker}:no_provider_numeric_field")
            continue

        relevance_score = _score_from_provider_export_aliases(
            source_row,
            (
                "relevance_score",
                "relevance",
                "match_score",
                "entity_relevance",
                "entity_relevance_score",
            ),
            allow_negative_polarity=False,
        )
        confidence = _score_from_provider_export_aliases(
            source_row,
            ("confidence", "confidence_score", "source_confidence"),
            allow_negative_polarity=False,
        )
        article_datetime_raw = _first_row_text(
            source_row,
            ("article_datetime", "published_at", "publishedAt", "datetime"),
        )
        article_datetime = _parse_provider_export_datetime(article_datetime_raw)
        event_date = _parse_provider_export_date(
            _first_row_text(source_row, ("event_date",))
        )
        source = _provider_export_source_label(normalized_provider, source_row)
        notes = _join_unique(
            (
                _first_row_text(source_row, ("notes",)),
                f"normalized_provider_export:{normalized_provider}",
            )
        )
        normalized_row = {header: "" for header in SOURCE_EXPORT_HEADERS}
        normalized_row.update(
            {
                "ticker": ticker,
                "signal_date": signal_date,
                "source": source,
                "source_url": source_url,
                "headline_or_event": headline,
                "article_datetime": article_datetime or "",
                "event_date": event_date or "",
                "topic": _first_row_text(
                    source_row,
                    ("topic", "category", "source_name", "publisher", "source"),
                ),
                "summary": _first_row_text(source_row, ("summary", "description", "snippet")),
                "sentiment_score": _format_export_score(sentiment_score),
                "catalyst_score": _format_export_score(catalyst_score),
                "urgency_score": _format_export_score(urgency_score),
                "relevance_score": _format_export_score(relevance_score),
                "confidence": _format_export_score(confidence),
                "notes": notes or "",
                "capture_method": f"{normalized_provider}_provider_export",
            }
        )
        normalized_rows.append(normalized_row)

    with output_path.open("w", newline="", encoding="utf-8") as output:
        writer = csv.DictWriter(output, fieldnames=SOURCE_EXPORT_HEADERS)
        writer.writeheader()
        writer.writerows(normalized_rows)

    return NewsCatalystProviderExportNormalizationResult(
        provider=normalized_provider,
        source_path=source_path,
        output_path=output_path,
        input_row_count=input_row_count,
        normalized_count=len(normalized_rows),
        skipped_count=input_row_count - len(normalized_rows),
        tickers=tuple(sorted({row["ticker"] for row in normalized_rows})),
        warnings=tuple(dict.fromkeys(warnings)),
    )


def _format_export_score(value: float | None) -> str:
    if value is None:
        return ""
    return f"{value:.6f}".rstrip("0").rstrip(".")


def _normalize_coverage_plan_mode(mode: str | None) -> str:
    normalized = (mode or "all").strip().lower().replace("_", "-")
    if normalized not in COVERAGE_PLAN_MODES:
        raise ValueError(
            "news/catalyst coverage mode must be one of: "
            + ", ".join(sorted(COVERAGE_PLAN_MODES))
        )
    return normalized


def news_catalyst_coverage_queue_path(
    config: AppConfig,
    mode: str = "missing",
) -> Path:
    normalized = _normalize_coverage_plan_mode(mode)
    if normalized == "provider-upgrade":
        return config.news_catalyst_source_exports_dir / PROVIDER_UPGRADE_QUEUE_EXPORT_FILE
    return config.news_catalyst_source_exports_dir / COVERAGE_QUEUE_EXPORT_FILE


def _coverage_queue_tickers(path: Path) -> tuple[str, ...]:
    if not path.exists():
        return ()
    try:
        reader = csv.DictReader(path.read_text(encoding="utf-8-sig").splitlines())
    except OSError:
        return ()
    tickers: list[str] = []
    for row in reader:
        ticker = normalize_ticker(row.get("ticker", ""))
        if ticker:
            tickers.append(ticker)
    return tuple(sorted(dict.fromkeys(tickers)))


def _coverage_template_row(ticker: str, reason: str) -> dict[str, str]:
    today = date.today().isoformat()
    row = {header: "" for header in SOURCE_EXPORT_HEADERS}
    row.update(
        {
            "ticker": ticker,
            "signal_date": today,
            "source": "user_provider_export"
            if reason == "provider_native_news_catalyst_upgrade_needed"
            else "provider_export",
            "source_url": "",
            "headline_or_event": "",
            "article_datetime": "",
            "event_date": "",
            "topic": "",
            "summary": "",
            "sentiment_score": "",
            "catalyst_score": "",
            "urgency_score": "",
            "relevance_score": "",
            "confidence": "",
            "notes": (
                f"coverage_queue:{reason}; fill only source-backed numeric fields; "
                "leave blank if unavailable"
            ),
            "capture_method": "manual_provider_export",
        }
    )
    return row


def write_news_catalyst_coverage_template(
    config: AppConfig,
    tickers: tuple[str, ...],
    reasons: dict[str, str],
    mode: str = "missing",
) -> Path:
    path = news_catalyst_coverage_queue_path(config, mode=mode)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as output:
        writer = csv.DictWriter(output, fieldnames=SOURCE_EXPORT_HEADERS)
        writer.writeheader()
        for ticker in tickers:
            writer.writerow(_coverage_template_row(ticker, reasons.get(ticker, "missing")))
    return path


def provider_native_backfill_dir(config: AppConfig) -> Path:
    return config.news_catalyst_source_exports_dir / PROVIDER_NATIVE_BACKFILL_DIRNAME


def provider_native_backfill_template_path(config: AppConfig) -> Path:
    return provider_native_backfill_dir(config) / PROVIDER_NATIVE_BACKFILL_EXPORT_FILE


def _parse_date(value: str, field_name: str, row_number: int) -> str:
    text = value.strip()
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


def _parse_optional_datetime(value: str | None, field_name: str, row_number: int) -> str | None:
    text = (value or "").strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).isoformat()
    except ValueError as error:
        raise ValueError(f"Row {row_number}: malformed {field_name}: {text}") from error


def _parse_score(value: str | None, field_name: str, row_number: int) -> float | None:
    text = (value or "").strip()
    if not text:
        return None
    try:
        parsed = float(text)
    except ValueError as error:
        raise ValueError(f"Row {row_number}: malformed {field_name}: {text}") from error
    if parsed < 0 or parsed > 100:
        raise ValueError(f"Row {row_number}: {field_name} must be between 0 and 100.")
    return parsed


def parse_news_catalyst_source_export_csv(text: str) -> list[NewsCatalystSourceRow]:
    reader = csv.DictReader(text.splitlines())
    if not reader.fieldnames:
        raise ValueError("News/catalyst source-export CSV missing header.")
    missing = REQUIRED_SOURCE_EXPORT_COLUMNS - set(reader.fieldnames)
    if missing:
        raise ValueError(
            "News/catalyst source-export CSV missing required columns: "
            + ", ".join(sorted(missing))
        )

    rows: list[NewsCatalystSourceRow] = []
    for row_number, row in enumerate(reader, start=2):
        if not any((value or "").strip() for value in row.values()):
            continue
        ticker = normalize_ticker(row.get("ticker", ""))
        if not ticker:
            raise ValueError(f"Row {row_number}: missing required ticker.")
        signal_date = _parse_date(row.get("signal_date", ""), "signal_date", row_number)
        source = (row.get("source") or "").strip()
        source_url = (row.get("source_url") or "").strip()
        headline = (row.get("headline_or_event") or "").strip()
        notes = (row.get("notes") or "").strip()
        if notes.startswith("coverage_queue:") and (not source_url or not headline):
            continue
        if not source:
            raise ValueError(f"Row {row_number}: missing required source.")
        if not source_url:
            raise ValueError(f"Row {row_number}: missing required source_url.")
        if not headline:
            raise ValueError(f"Row {row_number}: missing required headline_or_event.")
        numeric = {
            field: _parse_score(row.get(field), field, row_number)
            for field in NUMERIC_SOURCE_EXPORT_FIELDS
        }
        rows.append(
            NewsCatalystSourceRow(
                ticker=ticker,
                signal_date=signal_date,
                source=source,
                source_url=source_url,
                headline_or_event=headline,
                article_datetime=_parse_optional_datetime(
                    row.get("article_datetime"),
                    "article_datetime",
                    row_number,
                ),
                event_date=_parse_optional_date(row.get("event_date"), "event_date", row_number),
                topic=(row.get("topic") or "").strip() or None,
                summary=(row.get("summary") or "").strip() or None,
                notes=notes or None,
                capture_method=(row.get("capture_method") or "manual_capture").strip(),
                **numeric,
            )
        )
    return rows


def _row_claims_provider_native_upgrade(row: dict[str, str | None]) -> bool:
    source_key = _source_key(row.get("source"))
    notes = (row.get("notes") or "").strip().lower()
    return source_key in PROVIDER_NATIVE_EXPORT_SOURCES or (
        notes.startswith("coverage_queue:")
        and "provider_native_news_catalyst_upgrade_needed" in notes
    )


def _is_blank_provider_upgrade_placeholder(row: dict[str, str | None]) -> bool:
    notes = (row.get("notes") or "").strip().lower()
    return (
        notes.startswith("coverage_queue:")
        and not (row.get("source_url") or "").strip()
        and not (row.get("headline_or_event") or "").strip()
        and not any((row.get(field) or "").strip() for field in AGGREGATE_NUMERIC_FIELDS)
    )


def _provider_native_upgrade_row_validation_reasons(
    row: dict[str, str | None],
    row_number: int,
) -> tuple[str, ...]:
    reasons: list[str] = []
    ticker = normalize_ticker(row.get("ticker", ""))
    if not ticker:
        reasons.append("missing_ticker")
    if not (row.get("source") or "").strip():
        reasons.append("missing_source")
    signal_date_text = (row.get("signal_date") or "").strip()
    if not signal_date_text:
        reasons.append("missing_signal_date")
    else:
        try:
            date.fromisoformat(signal_date_text)
        except ValueError:
            reasons.append("malformed_signal_date")
    if not (row.get("source_url") or "").strip():
        reasons.append("missing_source_url")
    if not (row.get("headline_or_event") or "").strip():
        reasons.append("missing_headline_or_event")
    if not any((row.get(field) or "").strip() for field in AGGREGATE_NUMERIC_FIELDS):
        reasons.append("missing_provider_numeric_field")
    for field in NUMERIC_SOURCE_EXPORT_FIELDS:
        if not (row.get(field) or "").strip():
            continue
        try:
            _parse_score(row.get(field), field, row_number)
        except ValueError:
            reasons.append(f"malformed_{field}")
    return tuple(dict.fromkeys(reasons))


def _provider_native_validation_warnings_for_text(
    text: str,
) -> tuple[str, ...]:
    reader = csv.DictReader(text.splitlines())
    if not reader.fieldnames:
        return ()
    warnings: list[str] = []
    for row_number, row in enumerate(reader, start=2):
        if not any((value or "").strip() for value in row.values()):
            continue
        normalized_row = {
            header: (row.get(header) or "") for header in reader.fieldnames
        }
        if not _row_claims_provider_native_upgrade(normalized_row):
            continue
        if _is_blank_provider_upgrade_placeholder(normalized_row):
            continue
        missing_reasons = _provider_native_upgrade_row_validation_reasons(
            normalized_row,
            row_number,
        )
        if missing_reasons:
            ticker = normalize_ticker(normalized_row.get("ticker", ""))
            label = ticker or f"row_{row_number}"
            warnings.append(
                f"{label}:invalid_provider_native_upgrade_row:"
                + ",".join(missing_reasons)
            )
    return tuple(dict.fromkeys(warnings))


def _filter_invalid_provider_upgrade_rows(
    text: str,
) -> tuple[str, tuple[str, ...]]:
    lines = text.splitlines()
    reader = csv.DictReader(lines)
    if not reader.fieldnames:
        return text, ()

    warnings: list[str] = []
    valid_rows: list[dict[str, str]] = []
    for row_number, row in enumerate(reader, start=2):
        if not any((value or "").strip() for value in row.values()):
            continue
        normalized_row = {
            header: (row.get(header) or "") for header in reader.fieldnames
        }
        if _row_claims_provider_native_upgrade(normalized_row):
            if _is_blank_provider_upgrade_placeholder(normalized_row):
                valid_rows.append(normalized_row)
                continue
            ticker = normalize_ticker(normalized_row.get("ticker", ""))
            missing_reasons = _provider_native_upgrade_row_validation_reasons(
                normalized_row,
                row_number,
            )
            if missing_reasons:
                label = ticker or f"row_{row_number}"
                warnings.append(
                    f"{label}:invalid_provider_native_upgrade_row:"
                    + ",".join(missing_reasons)
                )
                continue
        valid_rows.append(normalized_row)

    from io import StringIO

    output = StringIO()
    writer = csv.DictWriter(output, fieldnames=reader.fieldnames)
    writer.writeheader()
    writer.writerows(valid_rows)
    return output.getvalue(), tuple(dict.fromkeys(warnings))


def _source_key(source: str | None) -> str:
    return (source or "").strip().lower().replace("-", "_").replace(" ", "_")


def _source_weight(source: str | None) -> float:
    key = _source_key(source)
    if key in SOURCE_WEIGHTS:
        return SOURCE_WEIGHTS[key]
    if "headline" in key:
        return HEADLINE_ONLY_WEIGHT
    return 0.6


def _source_confidence(source: str | None) -> float:
    return max(0.0, min(100.0, _source_weight(source) * 100.0))


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


def _asset_maps(config: AppConfig) -> tuple[dict[str, Asset], dict[str, Asset], dict[str, Asset]]:
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
    etf_assets = {
        ticker: asset
        for ticker, asset in assets.items()
        if (asset.asset_type or "equity").strip().lower() == "etf"
    }
    return assets, equity_assets, etf_assets


def _active_equity_tickers(config: AppConfig, ticker: str | None = None) -> tuple[str, ...]:
    wanted = normalize_ticker(ticker) if ticker else None
    _, equity_assets, _ = _asset_maps(config)
    return tuple(
        sorted(
            asset_ticker
            for asset_ticker in equity_assets
            if wanted is None or asset_ticker == wanted
        )
    )


def _source_snapshot_from_row(
    row: NewsCatalystSourceRow,
    provider_status: str = "ok",
    data_warnings: str | None = None,
) -> NewsCatalystSourceSnapshot:
    warnings = data_warnings
    if not any(
        value is not None
        for value in (row.sentiment_score, row.catalyst_score, row.urgency_score)
    ):
        warnings = _join_unique((warnings, "headline_only_source"))
    return NewsCatalystSourceSnapshot(
        ticker=row.ticker,
        signal_date=row.signal_date,
        source=row.source,
        source_url=row.source_url,
        headline_or_event=row.headline_or_event,
        article_datetime=row.article_datetime,
        event_date=row.event_date,
        topic=row.topic,
        summary=row.summary,
        capture_method=row.capture_method,
        provider_status=provider_status,
        sentiment_score=row.sentiment_score,
        catalyst_score=row.catalyst_score,
        urgency_score=row.urgency_score,
        relevance_score=row.relevance_score,
        source_confidence=row.confidence
        if row.confidence is not None
        else _source_confidence(row.source),
        data_warnings=warnings,
        as_of_date=date.today().isoformat(),
        effective_date=row.signal_date,
    )


def _csv_files_for_import(config: AppConfig, directory: Path | None = None) -> tuple[Path, ...]:
    root = directory or config.news_catalyst_source_exports_dir
    root.mkdir(parents=True, exist_ok=True)
    if directory is None:
        ensure_news_catalyst_source_export_templates(config)
    paths = tuple(sorted(path for path in root.rglob("*.csv") if path.is_file()))
    for path in paths:
        ensure_news_catalyst_source_export_header(path)
    return paths


def import_news_catalyst_source_exports(
    config: AppConfig,
    directory: Path | None = None,
    path: Path | None = None,
) -> NewsCatalystSourceImportResult:
    all_assets, equity_assets, _ = _asset_maps(config)
    source_files = (path,) if path is not None else _csv_files_for_import(config, directory)
    if path is not None:
        ensure_news_catalyst_source_export_header(path)

    warnings: list[str] = []
    source_row_count = 0
    imported_count = 0
    skipped_count = 0
    imported_tickers: set[str] = set()

    for source_path in source_files:
        filtered_text, row_warnings = _filter_invalid_provider_upgrade_rows(
            source_path.read_text(encoding="utf-8-sig")
        )
        warnings.extend(row_warnings)
        rows = parse_news_catalyst_source_export_csv(filtered_text)
        source_row_count += len(rows)
        for source_row in rows:
            asset = all_assets.get(source_row.ticker)
            if asset is None:
                skipped_count += 1
                warnings.append(f"{source_row.ticker}:inactive_or_unknown_ticker")
                continue
            asset_type = (asset.asset_type or "equity").strip().lower()
            row_warnings = None
            if asset_type == "etf":
                row_warnings = "etf_news_catalyst_gated"
                warnings.append(f"{source_row.ticker}:etf_news_catalyst_gated")
            if asset_type != "etf" and source_row.ticker not in equity_assets:
                skipped_count += 1
                warnings.append(f"{source_row.ticker}:inactive_or_unknown_equity")
                continue
            upsert_news_catalyst_source_snapshot(
                config.database_path,
                _source_snapshot_from_row(source_row, data_warnings=row_warnings),
            )
            imported_count += 1
            imported_tickers.add(source_row.ticker)

    if source_row_count == 0:
        warnings.append("empty_news_catalyst_source_exports")

    return NewsCatalystSourceImportResult(
        source_dir=directory or config.news_catalyst_source_exports_dir,
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
        return None
    midpoint = total_weight / 2.0
    running = 0.0
    for value, weight in ordered:
        running += max(weight, 0.0)
        if running >= midpoint:
            return value
    return ordered[-1][0]


def _snapshot_has_aggregate_value(snapshot: NewsCatalystSourceSnapshot) -> bool:
    return any(getattr(snapshot, field) is not None for field in AGGREGATE_NUMERIC_FIELDS)


def _snapshot_is_available(snapshot: NewsCatalystSourceSnapshot) -> bool:
    status = (snapshot.provider_status or "ok").strip().lower()
    return status == "ok" and _snapshot_has_aggregate_value(snapshot)


def _is_text_derived_snapshot(snapshot: NewsCatalystSourceSnapshot) -> bool:
    return _source_key(snapshot.source) == "news_text_backfill"


def _field_weighted_value(
    snapshots: list[NewsCatalystSourceSnapshot],
    field_name: str,
) -> tuple[float | None, float | None]:
    values = [
        (float(value), _source_weight(snapshot.source))
        for snapshot in snapshots
        for value in (getattr(snapshot, field_name),)
        if value is not None and _source_weight(snapshot.source) > 0
    ]
    if not values:
        return None, None
    raw_values = [value for value, _ in values]
    spread = max(raw_values) - min(raw_values) if len(raw_values) > 1 else 0.0
    return _weighted_median(values), spread


def _aggregate_confidence(
    snapshots: list[NewsCatalystSourceSnapshot],
    warnings: list[str],
) -> float:
    if not snapshots:
        return 0.0
    source_count = len({snapshot.source for snapshot in snapshots})
    average_source_confidence = (
        sum(snapshot.source_confidence or _source_confidence(snapshot.source) for snapshot in snapshots)
        / len(snapshots)
    )
    average_relevance = (
        sum(snapshot.relevance_score or 50.0 for snapshot in snapshots) / len(snapshots)
    )
    confidence = 30.0 + source_count * 12.0 + average_source_confidence * 0.25
    confidence += average_relevance * 0.15
    if "source_disagreement_medium" in warnings:
        confidence -= 8.0
    if "source_disagreement_high" in warnings:
        confidence -= 18.0
    if "single_source_only" in warnings:
        confidence -= 6.0
    if "missing_primary_sentiment_source" in warnings:
        confidence -= 8.0
    if any(warning.startswith("source_unavailable:") for warning in warnings):
        confidence -= 5.0
    return max(0.0, min(100.0, confidence))


def _headline_for_aggregate(snapshots: list[NewsCatalystSourceSnapshot]) -> str | None:
    ranked = sorted(
        snapshots,
        key=lambda snapshot: (
            snapshot.relevance_score or 0.0,
            snapshot.source_confidence or 0.0,
            snapshot.article_datetime or "",
            snapshot.source,
        ),
        reverse=True,
    )
    return ranked[0].headline_or_event if ranked else None


def _topic_for_aggregate(snapshots: list[NewsCatalystSourceSnapshot]) -> str | None:
    return _join_unique((snapshot.topic for snapshot in snapshots))


def _build_aggregate(
    config: AppConfig,
    ticker: str,
    signal_date: str,
    snapshots: list[NewsCatalystSourceSnapshot],
) -> NewsCatalystAggregate | None:
    if not snapshots:
        return None

    available_snapshots = [snapshot for snapshot in snapshots if _snapshot_is_available(snapshot)]
    provider_numeric_snapshots = [
        snapshot for snapshot in available_snapshots if not _is_text_derived_snapshot(snapshot)
    ]
    if provider_numeric_snapshots:
        available_snapshots = provider_numeric_snapshots
    unavailable_snapshots = [
        snapshot
        for snapshot in snapshots
        if (snapshot.provider_status or "ok").strip().lower() != "ok"
    ]
    headline_only_snapshots = [
        snapshot
        for snapshot in snapshots
        if not _snapshot_has_aggregate_value(snapshot)
        and (snapshot.provider_status or "ok").strip().lower() == "ok"
    ]
    if not available_snapshots:
        return None

    source_names = tuple(sorted({snapshot.source for snapshot in available_snapshots}))
    warnings: list[str] = []
    disagreement_parts: list[str] = []
    values: dict[str, float | None] = {}

    for field_name in AGGREGATE_NUMERIC_FIELDS:
        value, spread = _field_weighted_value(available_snapshots, field_name)
        values[field_name] = value
        if spread is None:
            continue
        if spread >= config.signals_news_catalyst_high_disagreement_threshold:
            warnings.append("source_disagreement_high")
            disagreement_parts.append(f"{field_name}:{spread:.2f}")
        elif spread >= config.signals_news_catalyst_disagreement_warning_threshold:
            warnings.append("source_disagreement_medium")
            disagreement_parts.append(f"{field_name}:{spread:.2f}")

    if not any(values[field] is not None for field in AGGREGATE_NUMERIC_FIELDS):
        return None
    if len(source_names) == 1:
        warnings.append("single_source_only")
    if len(source_names) < config.signals_news_catalyst_min_sources_for_aggregate:
        warnings.append("insufficient_sources_for_aggregate")
    if not any(_source_key(source) in PRIMARY_SENTIMENT_SOURCES for source in source_names):
        warnings.append("missing_primary_sentiment_source")
    if headline_only_snapshots:
        warnings.append("headline_only_source")
    for snapshot in unavailable_snapshots:
        warnings.append(f"source_unavailable:{snapshot.source}")
        if snapshot.data_warnings:
            warnings.extend(part.strip() for part in snapshot.data_warnings.split(",") if part.strip())
    for snapshot in snapshots:
        if snapshot.data_warnings:
            warnings.extend(part.strip() for part in snapshot.data_warnings.split(",") if part.strip())

    source_urls = _join_unique((snapshot.source_url for snapshot in available_snapshots), separator="; ")
    notes = (
        f"Aggregated from {', '.join(source_names)} using "
        f"{config.signals_news_catalyst_source_policy}."
    )
    data_warnings = _join_unique(warnings)
    aggregate_confidence = _aggregate_confidence(available_snapshots, warnings)

    return NewsCatalystAggregate(
        ticker=ticker,
        signal_date=signal_date,
        sentiment_score=values["sentiment_score"],
        catalyst_score=values["catalyst_score"],
        urgency_score=values["urgency_score"],
        confidence=aggregate_confidence,
        source_count=len(source_names),
        sources=", ".join(source_names),
        source_policy=config.signals_news_catalyst_source_policy,
        aggregate_confidence=aggregate_confidence,
        source_disagreement=", ".join(disagreement_parts) if disagreement_parts else None,
        headline_or_event=_headline_for_aggregate(available_snapshots),
        topic=_topic_for_aggregate(available_snapshots),
        data_warnings=data_warnings,
        model_version=config.signals_news_catalyst_model_version,
        source="news_catalyst_aggregate",
        source_url=source_urls,
        notes=notes,
        as_of_date=date.today().isoformat(),
        effective_date=signal_date,
    )


def _aggregate_to_final_row(aggregate: NewsCatalystAggregate) -> dict[str, str]:
    def fmt(value: object | None) -> str:
        if value is None:
            return ""
        if isinstance(value, float):
            return f"{value:.6f}".rstrip("0").rstrip(".")
        return str(value)

    return {
        "ticker": aggregate.ticker,
        "signal_date": aggregate.signal_date,
        "source": aggregate.source,
        "source_url": aggregate.source_url or "",
        "headline_or_event": aggregate.headline_or_event or "Aggregated news/catalyst signal",
        "event_date": aggregate.effective_date or aggregate.signal_date,
        "sentiment_score": fmt(aggregate.sentiment_score),
        "catalyst_score": fmt(aggregate.catalyst_score),
        "urgency_score": fmt(aggregate.urgency_score),
        "confidence": fmt(aggregate.confidence),
        "topic": aggregate.topic or "",
        "notes": _join_unique((aggregate.notes, aggregate.data_warnings)) or "",
        "as_of_date": aggregate.as_of_date or date.today().isoformat(),
        "effective_date": aggregate.effective_date or aggregate.signal_date,
    }


def _read_final_news_rows(path: Path) -> list[dict[str, str]]:
    ensure_news_catalyst_csv_header(path)
    reader = csv.DictReader(path.read_text(encoding="utf-8-sig").splitlines())
    return [
        {header: (row.get(header) or "") for header in NEWS_CATALYST_HEADERS}
        for row in reader
        if any((value or "").strip() for value in row.values())
    ]


def _write_final_news_rows(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as output:
        writer = csv.DictWriter(output, fieldnames=NEWS_CATALYST_HEADERS)
        writer.writeheader()
        writer.writerows(rows)


def _export_aggregates_to_final_csv(config: AppConfig) -> int:
    existing_rows = [
        row
        for row in _read_final_news_rows(config.news_catalysts_path)
        if (row.get("source") or "").strip() != "news_catalyst_aggregate"
    ]
    aggregate_rows = [
        _aggregate_to_final_row(aggregate)
        for aggregate in sorted(
            list_news_catalyst_aggregates(config.database_path),
            key=lambda row: (row.ticker, row.signal_date, row.source),
        )
    ]
    rows = existing_rows + aggregate_rows
    _write_final_news_rows(config.news_catalysts_path, rows)
    return len(rows)


def aggregate_news_catalyst_sources(
    config: AppConfig,
    ticker: str | None = None,
) -> NewsCatalystAggregateResult:
    snapshots = list_news_catalyst_source_snapshots(config.database_path, ticker=ticker)
    wanted_ticker = normalize_ticker(ticker) if ticker else None
    _, equity_assets, _ = _asset_maps(config)
    grouped: dict[tuple[str, str], list[NewsCatalystSourceSnapshot]] = {}
    warnings: list[str] = []
    for snapshot in snapshots:
        if wanted_ticker and snapshot.ticker != wanted_ticker:
            continue
        if snapshot.ticker not in equity_assets:
            warnings.append(f"{snapshot.ticker}:etf_or_non_equity_news_catalyst_gated")
            continue
        grouped.setdefault((snapshot.ticker, snapshot.signal_date), []).append(snapshot)

    aggregate_count = 0
    tickers: set[str] = set()
    for (group_ticker, signal_date), group_snapshots in sorted(grouped.items()):
        aggregate = _build_aggregate(config, group_ticker, signal_date, group_snapshots)
        if aggregate is None:
            delete_news_catalyst_aggregate(config.database_path, group_ticker, signal_date)
            warnings.append(f"{group_ticker}:no_aggregatable_news_catalyst_fields")
            continue
        upsert_news_catalyst_aggregate(config.database_path, aggregate)
        aggregate_count += 1
        tickers.add(group_ticker)
        if aggregate.data_warnings:
            warnings.extend(
                f"{group_ticker}:{part.strip()}"
                for part in aggregate.data_warnings.split(",")
                if part.strip()
            )

    if not grouped:
        warnings.append("no_news_catalyst_source_snapshots")

    written_count = _export_aggregates_to_final_csv(config)
    return NewsCatalystAggregateResult(
        aggregate_count=aggregate_count,
        written_row_count=written_count,
        tickers=tuple(sorted(tickers)),
        warnings=tuple(dict.fromkeys(warnings)),
    )


def _http_json(url: str, headers: dict[str, str] | None = None) -> object:
    request_headers = {"User-Agent": "TargetOpportunityMonitor/0.1"}
    if headers:
        request_headers.update(headers)
    request = Request(url, headers=request_headers)
    with urlopen(request, timeout=HTTP_TIMEOUT_SECONDS) as response:
        return json.loads(response.read().decode("utf-8"))


def _provider_http_warning(provider: str, error: HTTPError) -> str:
    if error.code == 401:
        return f"{provider}_auth_failed"
    if error.code == 402:
        return f"{provider}_plan_limited"
    if error.code == 403:
        return f"{provider}_plan_limited"
    if error.code == 429:
        return f"{provider}_rate_limited"
    return f"{provider}_http_failed:{error.code}"


def _is_hard_provider_stop(warning: str) -> bool:
    normalized = warning.lower()
    return any(
        part in normalized
        for part in (
            "auth_failed",
            "plan_limited",
            "rate_limited",
            "provider_budget_exhausted",
        )
    )


def _fetch_provider_payload(
    config: AppConfig,
    provider: str,
    ticker: str,
    url: str,
    state: _ProviderFetchState,
    *,
    force_refresh: bool = False,
    use_cache: bool | None = None,
    headers: dict[str, str] | None = None,
) -> tuple[object | None, str | None, bool]:
    cache_allowed = _cache_enabled(config, use_cache)
    if cache_allowed and not force_refresh:
        cached = _read_provider_cache(config, provider, ticker)
        if cached is not None and not cached.stale:
            state.cache_hits += 1
            return cached.payload, None, True
        state.cache_misses += 1

    if state.live_requests >= state.live_budget:
        state.budget_exhausted = True
        return None, f"{provider}_provider_budget_exhausted", False

    state.live_requests += 1
    try:
        payload = _http_json(url, headers=headers)
    except HTTPError as error:
        return None, _provider_http_warning(provider, error), False
    except (URLError, TimeoutError, json.JSONDecodeError) as error:
        return None, f"{provider}_http_failed:{type(error).__name__}", False

    return payload, None, False


def _list_payload_rows(payload: object, keys: tuple[str, ...] = ()) -> list[dict[str, object]]:
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]
    if isinstance(payload, dict):
        for key in keys:
            value = payload.get(key)
            if isinstance(value, list):
                return [row for row in value if isinstance(row, dict)]
    return []


def _provider_payload_warning(provider: str, ticker: str, payload: dict[str, object]) -> str | None:
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
        if "invalid api key" in message or "invalid token" in message:
            return f"{ticker}:{provider}_auth_failed"
        if "invalid api call" in message:
            return f"{ticker}:{provider}_invalid_api_call"
        if "rate limit" in message or "frequency" in message or "call limit" in message:
            return f"{ticker}:{provider}_rate_limited"
        if (
            "premium" in message
            or "plan" in message
            or "access" in message
            or "forbidden" in message
            or "not available" in message
        ):
            return f"{ticker}:{provider}_plan_limited"
        return f"{ticker}:{provider}_provider_message"
    return None


def _alpha_vantage_time(value: str | None) -> tuple[str, str | None]:
    if not value:
        today = date.today().isoformat()
        return today, None
    try:
        parsed = datetime.strptime(value, "%Y%m%dT%H%M%S")
        return parsed.date().isoformat(), parsed.isoformat()
    except ValueError:
        return date.today().isoformat(), None


def _epoch_time(value: object) -> tuple[str, str | None]:
    try:
        parsed = datetime.fromtimestamp(float(value))
    except (TypeError, ValueError, OSError):
        today = date.today().isoformat()
        return today, None
    return parsed.date().isoformat(), parsed.isoformat()


def _isoish_time(value: object) -> tuple[str, str | None]:
    text = str(value or "").strip()
    if not text:
        today = date.today().isoformat()
        return today, None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        return parsed.date().isoformat(), parsed.isoformat()
    except ValueError:
        try:
            parsed_date = date.fromisoformat(text[:10])
            return parsed_date.isoformat(), None
        except ValueError:
            return date.today().isoformat(), None


def _clamp_score(value: float) -> float:
    return max(0.0, min(100.0, value))


def _polarity_to_score(value: object) -> float | None:
    if value in (None, ""):
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if -1.0 <= parsed <= 1.0:
        return _clamp_score((parsed + 1.0) * 50.0)
    if 0.0 <= parsed <= 100.0:
        return _clamp_score(parsed)
    return None


def _percent_to_score(value: object) -> float | None:
    if value in (None, ""):
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if 0.0 <= parsed <= 1.0:
        return _clamp_score(parsed * 100.0)
    if 0.0 <= parsed <= 100.0:
        return _clamp_score(parsed)
    return None


def _alpha_ticker_sentiment(row: dict[str, object], ticker: str) -> tuple[float | None, float | None]:
    sentiments = row.get("ticker_sentiment")
    if not isinstance(sentiments, list):
        return _polarity_to_score(row.get("overall_sentiment_score")), None
    for item in sentiments:
        if not isinstance(item, dict):
            continue
        item_ticker = normalize_ticker(str(item.get("ticker") or ""))
        if item_ticker != ticker:
            continue
        sentiment = _polarity_to_score(item.get("ticker_sentiment_score"))
        relevance = _percent_to_score(item.get("relevance_score"))
        return sentiment, relevance
    return _polarity_to_score(row.get("overall_sentiment_score")), None


def _row_text(row: dict[str, object], keys: tuple[str, ...]) -> str | None:
    for key in keys:
        value = row.get(key)
        if value not in (None, ""):
            return str(value).strip()
    return None


def _store_provider_failure(
    config: AppConfig,
    ticker: str,
    source: str,
    warning: str,
    source_url: str,
    provider_status: str = "failed",
    enabled: bool = True,
) -> None:
    if not enabled:
        return
    upsert_news_catalyst_source_snapshot(
        config.database_path,
        NewsCatalystSourceSnapshot(
            ticker=ticker,
            signal_date=date.today().isoformat(),
            source=source,
            source_url=source_url,
            headline_or_event=f"{source} unavailable for this fetch cycle.",
            capture_method="api",
            provider_status=provider_status,
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
    source_url: str,
    provider_status: str = "failed",
    enabled: bool = True,
) -> None:
    for ticker in tickers:
        _store_provider_failure(
            config,
            ticker,
            source,
            warning,
            source_url,
            provider_status,
            enabled=enabled,
        )


def _skip_provider_ticker(
    config: AppConfig,
    ticker: str,
    provider: str,
    warning: str,
    docs_url: str,
    record_failure: bool = True,
) -> str:
    _store_provider_failure(
        config,
        ticker,
        provider,
        warning,
        docs_url,
        provider_status="skipped",
        enabled=record_failure,
    )
    return f"{ticker}:{warning}"


def _fetch_alpha_vantage_news_rows(
    config: AppConfig,
    tickers: tuple[str, ...],
    max_tickers: int | None = None,
    force_refresh: bool = False,
    use_cache: bool | None = None,
    record_failures: bool = True,
) -> NewsCatalystProviderFetchResult:
    key = _secret_env("ALPHAVANTAGE_API_KEY")
    docs_url = "https://www.alphavantage.co/documentation/#news-sentiment"
    if not key:
        _store_provider_failures(
            config,
            tickers,
            "alpha_vantage",
            "missing_alpha_vantage_api_key",
            docs_url,
            enabled=record_failures,
        )
        return NewsCatalystProviderFetchResult(
            provider="alpha_vantage",
            fetched_count=0,
            stored_count=0,
            skipped_count=len(tickers),
            tickers=(),
            warnings=("missing_alpha_vantage_api_key",),
        )

    fetched_count = 0
    numeric_stored_count = 0
    skipped_count = 0
    stored_tickers: set[str] = set()
    warnings: list[str] = []
    state = _ProviderFetchState(live_budget=_live_request_budget(config, max_tickers))
    blocked_warning: str | None = None
    for ticker in tickers:
        if blocked_warning:
            skipped_count += 1
            warnings.append(_skip_provider_ticker(config, ticker, "alpha_vantage", blocked_warning, docs_url, record_failure=record_failures))
            continue
        if state.live_requests > 0:
            time.sleep(config.signals_news_catalyst_provider_retry_delay_seconds)
        query = urlencode(
            {
                "function": "NEWS_SENTIMENT",
                "tickers": ticker,
                "sort": "LATEST",
                "limit": str(config.signals_news_catalyst_max_items_per_ticker),
                "apikey": key,
            }
        )
        url = f"https://www.alphavantage.co/query?{query}"
        payload, fetch_warning, from_cache = _fetch_provider_payload(
            config,
            "alpha_vantage",
            ticker,
            url,
            state,
            force_refresh=force_refresh,
            use_cache=use_cache,
        )
        if fetch_warning:
            skipped_count += 1
            warning = fetch_warning
            warnings.append(f"{ticker}:{warning}")
            _store_provider_failure(config, ticker, "alpha_vantage", warning, docs_url, enabled=record_failures)
            if _is_hard_provider_stop(warning):
                blocked_warning = warning
            continue
        if not isinstance(payload, dict):
            skipped_count += 1
            warning = "alpha_vantage_unexpected_payload"
            warnings.append(f"{ticker}:{warning}")
            _store_provider_failure(config, ticker, "alpha_vantage", warning, docs_url, enabled=record_failures)
            continue
        provider_warning = _provider_payload_warning("alpha_vantage", ticker, payload)
        if provider_warning:
            skipped_count += 1
            warnings.append(provider_warning)
            _store_provider_failure(
                config,
                ticker,
                "alpha_vantage",
                provider_warning.split(":", 1)[1],
                docs_url,
                enabled=record_failures,
            )
            if _is_hard_provider_stop(provider_warning):
                blocked_warning = provider_warning.split(":", 1)[1]
            continue
        rows = _list_payload_rows(payload, ("feed",))
        if not rows:
            skipped_count += 1
            warning = "alpha_vantage_no_news_rows"
            warnings.append(f"{ticker}:{warning}")
            _store_provider_failure(config, ticker, "alpha_vantage", warning, docs_url)
            continue
        if not from_cache:
            _write_provider_cache(config, "alpha_vantage", ticker, payload)
            state.cache_writes += 1
        for item in rows[: config.signals_news_catalyst_max_items_per_ticker]:
            signal_date, article_datetime = _alpha_vantage_time(
                str(item.get("time_published") or "")
            )
            sentiment_score, relevance_score = _alpha_ticker_sentiment(item, ticker)
            source_url = _row_text(item, ("url",)) or docs_url
            headline = _row_text(item, ("title", "summary")) or "Alpha Vantage news item"
            topic = None
            topics = item.get("topics")
            if isinstance(topics, list):
                topic = _join_unique(
                    str(topic_row.get("topic")) if isinstance(topic_row, dict) else str(topic_row)
                    for topic_row in topics
                )
            snapshot = NewsCatalystSourceSnapshot(
                ticker=ticker,
                signal_date=signal_date,
                source="alpha_vantage",
                source_url=source_url,
                headline_or_event=headline,
                article_datetime=article_datetime,
                topic=topic,
                summary=_row_text(item, ("summary",)),
                capture_method="api",
                provider_status="ok",
                sentiment_score=sentiment_score,
                relevance_score=relevance_score,
                source_confidence=relevance_score or 85.0,
                data_warnings=None if sentiment_score is not None else "headline_only_source",
                as_of_date=date.today().isoformat(),
                effective_date=signal_date,
            )
            upsert_news_catalyst_source_snapshot(config.database_path, snapshot)
            fetched_count += 1
            if _snapshot_has_aggregate_value(snapshot):
                numeric_stored_count += 1
            stored_tickers.add(ticker)
    return NewsCatalystProviderFetchResult(
        provider="alpha_vantage",
        fetched_count=fetched_count,
        stored_count=fetched_count,
        skipped_count=skipped_count,
        tickers=tuple(sorted(stored_tickers)),
        warnings=tuple(dict.fromkeys(warnings)),
        cache_hits=state.cache_hits,
        cache_misses=state.cache_misses,
        cache_writes=state.cache_writes,
        live_requests=state.live_requests,
        budget_exhausted=state.budget_exhausted,
        numeric_stored_count=numeric_stored_count,
    )


def _finnhub_sentiment_score(payload: object) -> float | None:
    if not isinstance(payload, dict):
        return None
    sentiment = payload.get("sentiment")
    if isinstance(sentiment, dict):
        bullish = _percent_to_score(sentiment.get("bullishPercent"))
        bearish = _percent_to_score(sentiment.get("bearishPercent"))
        if bullish is not None and bearish is not None:
            return _clamp_score(50.0 + (bullish - bearish) / 2.0)
    company_score = _polarity_to_score(payload.get("companyNewsScore"))
    if company_score is not None:
        return company_score
    return _polarity_to_score(payload.get("buzz"))


def _fetch_finnhub_news_rows(
    config: AppConfig,
    tickers: tuple[str, ...],
    max_tickers: int | None = None,
    force_refresh: bool = False,
    use_cache: bool | None = None,
    record_failures: bool = True,
) -> NewsCatalystProviderFetchResult:
    key = _secret_env("FINNHUB_API_KEY") or _secret_env("FINHUB_API_KEY")
    docs_url = "https://finnhub.io/docs/api/company-news"
    if not key:
        _store_provider_failures(
            config,
            tickers,
            "finnhub",
            "missing_finnhub_api_key",
            docs_url,
            enabled=record_failures,
        )
        return NewsCatalystProviderFetchResult(
            provider="finnhub",
            fetched_count=0,
            stored_count=0,
            skipped_count=len(tickers),
            tickers=(),
            warnings=("missing_finnhub_api_key",),
        )

    from_date = (date.today() - timedelta(days=config.signals_news_catalyst_lookback_days)).isoformat()
    to_date = date.today().isoformat()
    fetched_count = 0
    numeric_stored_count = 0
    skipped_count = 0
    stored_tickers: set[str] = set()
    warnings: list[str] = []
    state = _ProviderFetchState(live_budget=_live_request_budget(config, max_tickers))
    blocked_warning: str | None = None
    for ticker in tickers:
        if blocked_warning:
            skipped_count += 1
            warnings.append(_skip_provider_ticker(config, ticker, "finnhub", blocked_warning, docs_url, record_failure=record_failures))
            continue
        sentiment_score: float | None = None
        sentiment_query = urlencode({"symbol": ticker, "token": key})
        sentiment_url = f"https://finnhub.io/api/v1/news-sentiment?{sentiment_query}"
        try:
            sentiment_payload = _http_json(sentiment_url)
            if isinstance(sentiment_payload, dict):
                provider_warning = _provider_payload_warning("finnhub", ticker, sentiment_payload)
                if provider_warning:
                    warnings.append(provider_warning)
                else:
                    sentiment_score = _finnhub_sentiment_score(sentiment_payload)
        except HTTPError as error:
            warnings.append(f"{ticker}:finnhub_sentiment_{_provider_http_warning('finnhub', error)}")
        except (URLError, TimeoutError, json.JSONDecodeError) as error:
            warnings.append(f"{ticker}:finnhub_sentiment_http_failed:{type(error).__name__}")

        query = urlencode({"symbol": ticker, "from": from_date, "to": to_date, "token": key})
        url = f"https://finnhub.io/api/v1/company-news?{query}"
        payload, fetch_warning, from_cache = _fetch_provider_payload(
            config,
            "finnhub",
            ticker,
            url,
            state,
            force_refresh=force_refresh,
            use_cache=use_cache,
        )
        if fetch_warning:
            skipped_count += 1
            warning = fetch_warning
            warnings.append(f"{ticker}:{warning}")
            _store_provider_failure(config, ticker, "finnhub", warning, docs_url, enabled=record_failures)
            if _is_hard_provider_stop(warning):
                blocked_warning = warning
            continue
        rows = _list_payload_rows(payload)
        if not rows:
            skipped_count += 1
            warning = "finnhub_no_company_news_rows"
            warnings.append(f"{ticker}:{warning}")
            _store_provider_failure(config, ticker, "finnhub", warning, docs_url, enabled=record_failures)
            continue
        if not from_cache:
            _write_provider_cache(config, "finnhub", ticker, payload)
            state.cache_writes += 1
        for index, item in enumerate(rows[: config.signals_news_catalyst_max_items_per_ticker]):
            signal_date, article_datetime = _epoch_time(item.get("datetime"))
            source_url = _row_text(item, ("url",)) or docs_url
            headline = _row_text(item, ("headline", "summary")) or "Finnhub company news item"
            row_sentiment = sentiment_score if index == 0 else None
            snapshot = NewsCatalystSourceSnapshot(
                ticker=ticker,
                signal_date=signal_date,
                source="finnhub",
                source_url=source_url,
                headline_or_event=headline,
                article_datetime=article_datetime,
                topic=_row_text(item, ("category", "source")),
                summary=_row_text(item, ("summary",)),
                capture_method="api",
                provider_status="ok",
                sentiment_score=row_sentiment,
                source_confidence=80.0 if row_sentiment is not None else 45.0,
                data_warnings=None if row_sentiment is not None else "headline_only_source",
                as_of_date=date.today().isoformat(),
                effective_date=signal_date,
            )
            upsert_news_catalyst_source_snapshot(config.database_path, snapshot)
            fetched_count += 1
            if _snapshot_has_aggregate_value(snapshot):
                numeric_stored_count += 1
            stored_tickers.add(ticker)
    return NewsCatalystProviderFetchResult(
        provider="finnhub",
        fetched_count=fetched_count,
        stored_count=fetched_count,
        skipped_count=skipped_count,
        tickers=tuple(sorted(stored_tickers)),
        warnings=tuple(dict.fromkeys(warnings)),
        cache_hits=state.cache_hits,
        cache_misses=state.cache_misses,
        cache_writes=state.cache_writes,
        live_requests=state.live_requests,
        budget_exhausted=state.budget_exhausted,
        numeric_stored_count=numeric_stored_count,
    )


def _fmp_sentiment(row: dict[str, object]) -> float | None:
    for key in ("sentimentScore", "sentiment_score", "score", "sentiment"):
        value = row.get(key)
        if isinstance(value, (int, float)):
            return _polarity_to_score(value)
        if isinstance(value, str):
            try:
                return _polarity_to_score(float(value))
            except ValueError:
                continue
    return None


def _fetch_fmp_news_rows(
    config: AppConfig,
    tickers: tuple[str, ...],
    max_tickers: int | None = None,
    force_refresh: bool = False,
    use_cache: bool | None = None,
    record_failures: bool = True,
) -> NewsCatalystProviderFetchResult:
    key = _secret_env("FMP_API_KEY") or _secret_env("FINANCIAL_MODELING_PREP_API_KEY")
    docs_url = "https://site.financialmodelingprep.com/developer/docs/stable/general-news"
    if not key:
        _store_provider_failures(config, tickers, "fmp", "missing_fmp_api_key", docs_url, enabled=record_failures)
        return NewsCatalystProviderFetchResult(
            provider="fmp",
            fetched_count=0,
            stored_count=0,
            skipped_count=len(tickers),
            tickers=(),
            warnings=("missing_fmp_api_key",),
        )

    fetched_count = 0
    numeric_stored_count = 0
    skipped_count = 0
    stored_tickers: set[str] = set()
    warnings: list[str] = []
    state = _ProviderFetchState(live_budget=_live_request_budget(config, max_tickers))
    blocked_warning: str | None = None
    for ticker in tickers:
        if blocked_warning:
            skipped_count += 1
            warnings.append(_skip_provider_ticker(config, ticker, "fmp", blocked_warning, docs_url, record_failure=record_failures))
            continue
        query = urlencode(
            {
                "symbols": ticker,
                "limit": str(config.signals_news_catalyst_max_items_per_ticker),
                "apikey": key,
            }
        )
        url = f"https://financialmodelingprep.com/stable/news/stock?{query}"
        payload, fetch_warning, from_cache = _fetch_provider_payload(
            config,
            "fmp",
            ticker,
            url,
            state,
            force_refresh=force_refresh,
            use_cache=use_cache,
        )
        if fetch_warning:
            skipped_count += 1
            warning = fetch_warning
            warnings.append(f"{ticker}:{warning}")
            _store_provider_failure(config, ticker, "fmp", warning, docs_url, enabled=record_failures)
            if _is_hard_provider_stop(warning):
                blocked_warning = warning
            continue
        if isinstance(payload, dict):
            provider_warning = _provider_payload_warning("fmp", ticker, payload)
            if provider_warning:
                skipped_count += 1
                warnings.append(provider_warning)
                _store_provider_failure(config, ticker, "fmp", provider_warning.split(":", 1)[1], docs_url, enabled=record_failures)
                if _is_hard_provider_stop(provider_warning):
                    blocked_warning = provider_warning.split(":", 1)[1]
                continue
        rows = _list_payload_rows(payload, ("content", "data"))
        if not rows:
            skipped_count += 1
            warning = "fmp_no_news_rows"
            warnings.append(f"{ticker}:{warning}")
            _store_provider_failure(config, ticker, "fmp", warning, docs_url, enabled=record_failures)
            continue
        if not from_cache:
            _write_provider_cache(config, "fmp", ticker, payload)
            state.cache_writes += 1
        for item in rows[: config.signals_news_catalyst_max_items_per_ticker]:
            signal_date, article_datetime = _isoish_time(
                item.get("publishedDate") or item.get("date")
            )
            source_url = _row_text(item, ("url", "link")) or docs_url
            headline = _row_text(item, ("title", "headline", "text")) or "FMP news item"
            sentiment_score = _fmp_sentiment(item)
            snapshot = NewsCatalystSourceSnapshot(
                ticker=ticker,
                signal_date=signal_date,
                source="fmp",
                source_url=source_url,
                headline_or_event=headline,
                article_datetime=article_datetime,
                topic=_row_text(item, ("site", "publisher", "symbol")),
                summary=_row_text(item, ("text", "summary")),
                capture_method="api",
                provider_status="ok",
                sentiment_score=sentiment_score,
                source_confidence=70.0 if sentiment_score is not None else 40.0,
                data_warnings=None if sentiment_score is not None else "headline_only_source",
                as_of_date=date.today().isoformat(),
                effective_date=signal_date,
            )
            upsert_news_catalyst_source_snapshot(config.database_path, snapshot)
            fetched_count += 1
            if _snapshot_has_aggregate_value(snapshot):
                numeric_stored_count += 1
            stored_tickers.add(ticker)
    return NewsCatalystProviderFetchResult(
        provider="fmp",
        fetched_count=fetched_count,
        stored_count=fetched_count,
        skipped_count=skipped_count,
        tickers=tuple(sorted(stored_tickers)),
        warnings=tuple(dict.fromkeys(warnings)),
        cache_hits=state.cache_hits,
        cache_misses=state.cache_misses,
        cache_writes=state.cache_writes,
        live_requests=state.live_requests,
        budget_exhausted=state.budget_exhausted,
        numeric_stored_count=numeric_stored_count,
    )


def _marketaux_entity(row: dict[str, object], ticker: str) -> dict[str, object] | None:
    entities = row.get("entities")
    if not isinstance(entities, list):
        return None
    for entity in entities:
        if not isinstance(entity, dict):
            continue
        symbol = normalize_ticker(str(entity.get("symbol") or entity.get("ticker") or ""))
        if symbol == ticker or symbol.split(".", 1)[0] == ticker:
            return entity
    return None


def _fetch_marketaux_news_rows(
    config: AppConfig,
    tickers: tuple[str, ...],
    max_tickers: int | None = None,
    force_refresh: bool = False,
    use_cache: bool | None = None,
    record_failures: bool = True,
) -> NewsCatalystProviderFetchResult:
    key = _secret_env("MARKETAUX_API_KEY") or _secret_env("MARKET_AUX_API_KEY")
    docs_url = "https://www.marketaux.com/documentation"
    if not key:
        _store_provider_failures(
            config,
            tickers,
            "marketaux",
            "missing_marketaux_api_key",
            docs_url,
            enabled=record_failures,
        )
        return NewsCatalystProviderFetchResult(
            provider="marketaux",
            fetched_count=0,
            stored_count=0,
            skipped_count=len(tickers),
            tickers=(),
            warnings=("missing_marketaux_api_key",),
        )

    fetched_count = 0
    numeric_stored_count = 0
    skipped_count = 0
    stored_tickers: set[str] = set()
    warnings: list[str] = []
    state = _ProviderFetchState(live_budget=_live_request_budget(config, max_tickers))
    blocked_warning: str | None = None
    for ticker in tickers:
        if blocked_warning:
            skipped_count += 1
            warnings.append(_skip_provider_ticker(config, ticker, "marketaux", blocked_warning, docs_url, record_failure=record_failures))
            continue
        query = urlencode(
            {
                "symbols": ticker,
                "filter_entities": "true",
                "language": "en",
                "limit": str(config.signals_news_catalyst_max_items_per_ticker),
                "api_token": key,
            }
        )
        url = f"https://api.marketaux.com/v1/news/all?{query}"
        payload, fetch_warning, from_cache = _fetch_provider_payload(
            config,
            "marketaux",
            ticker,
            url,
            state,
            force_refresh=force_refresh,
            use_cache=use_cache,
        )
        if fetch_warning:
            skipped_count += 1
            warnings.append(f"{ticker}:{fetch_warning}")
            _store_provider_failure(config, ticker, "marketaux", fetch_warning, docs_url, enabled=record_failures)
            if _is_hard_provider_stop(fetch_warning):
                blocked_warning = fetch_warning
            continue
        if not isinstance(payload, dict):
            skipped_count += 1
            warning = "marketaux_unexpected_payload"
            warnings.append(f"{ticker}:{warning}")
            _store_provider_failure(config, ticker, "marketaux", warning, docs_url, enabled=record_failures)
            continue
        provider_warning = _provider_payload_warning("marketaux", ticker, payload)
        if provider_warning:
            skipped_count += 1
            warnings.append(provider_warning)
            _store_provider_failure(
                config,
                ticker,
                "marketaux",
                provider_warning.split(":", 1)[1],
                docs_url,
                enabled=record_failures,
            )
            if _is_hard_provider_stop(provider_warning):
                blocked_warning = provider_warning.split(":", 1)[1]
            continue
        rows = _list_payload_rows(payload, ("data",))
        if not rows:
            skipped_count += 1
            warning = "marketaux_no_news_rows"
            warnings.append(f"{ticker}:{warning}")
            _store_provider_failure(config, ticker, "marketaux", warning, docs_url, enabled=record_failures)
            continue
        if not from_cache:
            _write_provider_cache(config, "marketaux", ticker, payload)
            state.cache_writes += 1
        for item in rows[: config.signals_news_catalyst_max_items_per_ticker]:
            entity = _marketaux_entity(item, ticker) or {}
            signal_date, article_datetime = _isoish_time(
                item.get("published_at") or item.get("publishedAt") or item.get("date")
            )
            sentiment_score = _polarity_to_score(entity.get("sentiment_score"))
            relevance_score = _percent_to_score(
                entity.get("match_score") or entity.get("relevance_score")
            )
            source_url = _row_text(item, ("url", "link")) or docs_url
            headline = _row_text(item, ("title", "headline", "description")) or "Marketaux news item"
            snapshot = NewsCatalystSourceSnapshot(
                ticker=ticker,
                signal_date=signal_date,
                source="marketaux",
                source_url=source_url,
                headline_or_event=headline,
                article_datetime=article_datetime,
                topic=_row_text(item, ("source", "language")) or _row_text(entity, ("industry", "type")),
                summary=_row_text(item, ("description", "snippet")),
                capture_method="api",
                provider_status="ok",
                sentiment_score=sentiment_score,
                relevance_score=relevance_score,
                source_confidence=relevance_score or (85.0 if sentiment_score is not None else 45.0),
                data_warnings=None if sentiment_score is not None else "headline_only_source",
                as_of_date=date.today().isoformat(),
                effective_date=signal_date,
            )
            upsert_news_catalyst_source_snapshot(config.database_path, snapshot)
            fetched_count += 1
            if _snapshot_has_aggregate_value(snapshot):
                numeric_stored_count += 1
            stored_tickers.add(ticker)
    return NewsCatalystProviderFetchResult(
        provider="marketaux",
        fetched_count=fetched_count,
        stored_count=fetched_count,
        skipped_count=skipped_count,
        tickers=tuple(sorted(stored_tickers)),
        warnings=tuple(dict.fromkeys(warnings)),
        cache_hits=state.cache_hits,
        cache_misses=state.cache_misses,
        cache_writes=state.cache_writes,
        live_requests=state.live_requests,
        budget_exhausted=state.budget_exhausted,
        numeric_stored_count=numeric_stored_count,
    )


def _eodhd_sentiment(row: dict[str, object]) -> float | None:
    for key in ("sentiment", "sentiment_score", "sentimentScore", "polarity"):
        value = row.get(key)
        if isinstance(value, dict):
            nested = (
                value.get("polarity")
                or value.get("score")
                or value.get("sentiment_score")
                or value.get("sentimentScore")
            )
            score = _polarity_to_score(nested)
            if score is not None:
                return score
        score = _polarity_to_score(value)
        if score is not None:
            return score
    return None


def _fetch_eodhd_news_rows(
    config: AppConfig,
    tickers: tuple[str, ...],
    max_tickers: int | None = None,
    force_refresh: bool = False,
    use_cache: bool | None = None,
    record_failures: bool = True,
) -> NewsCatalystProviderFetchResult:
    key = _secret_env("EODHD_API_KEY") or _secret_env("EOD_HISTORICAL_DATA_API_KEY")
    docs_url = "https://eodhd.com/financial-apis-blog/sentimental-data-api-added-to-alternative-apis"
    if not key:
        _store_provider_failures(config, tickers, "eodhd", "missing_eodhd_api_key", docs_url, enabled=record_failures)
        return NewsCatalystProviderFetchResult(
            provider="eodhd",
            fetched_count=0,
            stored_count=0,
            skipped_count=len(tickers),
            tickers=(),
            warnings=("missing_eodhd_api_key",),
        )

    fetched_count = 0
    numeric_stored_count = 0
    skipped_count = 0
    stored_tickers: set[str] = set()
    warnings: list[str] = []
    state = _ProviderFetchState(live_budget=_live_request_budget(config, max_tickers))
    blocked_warning: str | None = None
    for ticker in tickers:
        if blocked_warning:
            skipped_count += 1
            warnings.append(_skip_provider_ticker(config, ticker, "eodhd", blocked_warning, docs_url, record_failure=record_failures))
            continue
        query = urlencode(
            {
                "s": f"{ticker}.US",
                "limit": str(config.signals_news_catalyst_max_items_per_ticker),
                "fmt": "json",
                "api_token": key,
            }
        )
        url = f"https://eodhistoricaldata.com/api/news?{query}"
        payload, fetch_warning, from_cache = _fetch_provider_payload(
            config,
            "eodhd",
            ticker,
            url,
            state,
            force_refresh=force_refresh,
            use_cache=use_cache,
        )
        if fetch_warning:
            skipped_count += 1
            warnings.append(f"{ticker}:{fetch_warning}")
            _store_provider_failure(config, ticker, "eodhd", fetch_warning, docs_url, enabled=record_failures)
            if _is_hard_provider_stop(fetch_warning):
                blocked_warning = fetch_warning
            continue
        if isinstance(payload, dict):
            provider_warning = _provider_payload_warning("eodhd", ticker, payload)
            if provider_warning:
                skipped_count += 1
                warnings.append(provider_warning)
                _store_provider_failure(config, ticker, "eodhd", provider_warning.split(":", 1)[1], docs_url, enabled=record_failures)
                if _is_hard_provider_stop(provider_warning):
                    blocked_warning = provider_warning.split(":", 1)[1]
                continue
        rows = _list_payload_rows(payload, ("data", "news"))
        if not rows:
            skipped_count += 1
            warning = "eodhd_no_news_rows"
            warnings.append(f"{ticker}:{warning}")
            _store_provider_failure(config, ticker, "eodhd", warning, docs_url, enabled=record_failures)
            continue
        if not from_cache:
            _write_provider_cache(config, "eodhd", ticker, payload)
            state.cache_writes += 1
        for item in rows[: config.signals_news_catalyst_max_items_per_ticker]:
            signal_date, article_datetime = _isoish_time(
                item.get("date") or item.get("published_at") or item.get("publishedAt")
            )
            sentiment_score = _eodhd_sentiment(item)
            source_url = _row_text(item, ("link", "url")) or docs_url
            headline = _row_text(item, ("title", "headline")) or "EODHD news item"
            tags = item.get("tags")
            topic = _join_unique(str(tag) for tag in tags) if isinstance(tags, list) else None
            snapshot = NewsCatalystSourceSnapshot(
                ticker=ticker,
                signal_date=signal_date,
                source="eodhd",
                source_url=source_url,
                headline_or_event=headline,
                article_datetime=article_datetime,
                topic=topic,
                summary=_row_text(item, ("content", "summary", "description")),
                capture_method="api",
                provider_status="ok",
                sentiment_score=sentiment_score,
                source_confidence=80.0 if sentiment_score is not None else 45.0,
                data_warnings=None if sentiment_score is not None else "headline_only_source",
                as_of_date=date.today().isoformat(),
                effective_date=signal_date,
            )
            upsert_news_catalyst_source_snapshot(config.database_path, snapshot)
            fetched_count += 1
            if _snapshot_has_aggregate_value(snapshot):
                numeric_stored_count += 1
            stored_tickers.add(ticker)
    return NewsCatalystProviderFetchResult(
        provider="eodhd",
        fetched_count=fetched_count,
        stored_count=fetched_count,
        skipped_count=skipped_count,
        tickers=tuple(sorted(stored_tickers)),
        warnings=tuple(dict.fromkeys(warnings)),
        cache_hits=state.cache_hits,
        cache_misses=state.cache_misses,
        cache_writes=state.cache_writes,
        live_requests=state.live_requests,
        budget_exhausted=state.budget_exhausted,
        numeric_stored_count=numeric_stored_count,
    )


def _ticker_query_terms(config: AppConfig, ticker: str) -> str:
    assets, _, _ = _asset_maps(config)
    asset = assets.get(ticker)
    names = []
    if asset and asset.name:
        names = [part.strip() for part in asset.name.replace(",", " ").split() if len(part.strip()) > 3]
    name_query = " OR ".join(f'"{name}"' for name in names[:2])
    ticker_query = f"${ticker} OR {ticker}"
    return f"({ticker_query}{' OR ' + name_query if name_query else ''})"


def _fetch_x_recent_search_rows(
    config: AppConfig,
    tickers: tuple[str, ...],
    max_tickers: int | None = None,
    force_refresh: bool = False,
    use_cache: bool | None = None,
    record_failures: bool = True,
) -> NewsCatalystProviderFetchResult:
    key = _secret_env("X_BEARER_TOKEN") or _secret_env("TWITTER_BEARER_TOKEN")
    docs_url = "https://docs.x.com/x-api/posts/recent-search"
    if not key:
        _store_provider_failures(config, tickers, "x_recent_search", "missing_x_bearer_token", docs_url, enabled=record_failures)
        return NewsCatalystProviderFetchResult(
            provider="x_recent_search",
            fetched_count=0,
            stored_count=0,
            skipped_count=len(tickers),
            tickers=(),
            warnings=("missing_x_bearer_token",),
        )

    account_query = " OR ".join(
        f"from:{account}" for account in config.signals_news_catalyst_social_accounts
    )
    fetched_count = 0
    numeric_stored_count = 0
    skipped_count = 0
    stored_tickers: set[str] = set()
    warnings: list[str] = []
    state = _ProviderFetchState(live_budget=_live_request_budget(config, max_tickers))
    blocked_warning: str | None = None
    for ticker in tickers:
        if blocked_warning:
            skipped_count += 1
            warnings.append(_skip_provider_ticker(config, ticker, "x_recent_search", blocked_warning, docs_url, record_failure=record_failures))
            continue
        query_text = (
            f"{_ticker_query_terms(config, ticker)} "
            f"({account_query}) -is:retweet -is:reply lang:en"
            if account_query
            else f"{_ticker_query_terms(config, ticker)} -is:retweet -is:reply lang:en"
        )
        query = urlencode(
            {
                "query": query_text,
                "max_results": str(max(10, config.signals_news_catalyst_max_items_per_ticker)),
                "tweet.fields": "created_at,author_id,public_metrics",
            }
        )
        url = f"https://api.x.com/2/tweets/search/recent?{query}"
        payload, fetch_warning, from_cache = _fetch_provider_payload(
            config,
            "x_recent_search",
            ticker,
            url,
            state,
            force_refresh=force_refresh,
            use_cache=use_cache,
            headers={"Authorization": f"Bearer {key}"},
        )
        if fetch_warning:
            skipped_count += 1
            warnings.append(f"{ticker}:{fetch_warning}")
            _store_provider_failure(config, ticker, "x_recent_search", fetch_warning, docs_url, enabled=record_failures)
            if _is_hard_provider_stop(fetch_warning):
                blocked_warning = fetch_warning
            continue
        if not isinstance(payload, dict):
            skipped_count += 1
            warning = "x_recent_search_unexpected_payload"
            warnings.append(f"{ticker}:{warning}")
            _store_provider_failure(config, ticker, "x_recent_search", warning, docs_url, enabled=record_failures)
            continue
        provider_warning = _provider_payload_warning("x_recent_search", ticker, payload)
        if provider_warning:
            skipped_count += 1
            warnings.append(provider_warning)
            _store_provider_failure(config, ticker, "x_recent_search", provider_warning.split(":", 1)[1], docs_url, enabled=record_failures)
            if _is_hard_provider_stop(provider_warning):
                blocked_warning = provider_warning.split(":", 1)[1]
            continue
        rows = _list_payload_rows(payload, ("data",))
        if not rows:
            skipped_count += 1
            warning = "x_recent_search_no_matching_posts"
            warnings.append(f"{ticker}:{warning}")
            _store_provider_failure(config, ticker, "x_recent_search", warning, docs_url, provider_status="skipped", enabled=record_failures)
            continue
        if not from_cache:
            _write_provider_cache(config, "x_recent_search", ticker, payload)
            state.cache_writes += 1
        for item in rows[: config.signals_news_catalyst_max_items_per_ticker]:
            tweet_id = str(item.get("id") or "")
            signal_date, article_datetime = _isoish_time(item.get("created_at"))
            text = _row_text(item, ("text",)) or "X recent-search post"
            source_url = f"https://x.com/i/web/status/{tweet_id}" if tweet_id else docs_url
            snapshot = NewsCatalystSourceSnapshot(
                ticker=ticker,
                signal_date=signal_date,
                source="x_recent_search",
                source_url=source_url,
                headline_or_event=text[:240],
                article_datetime=article_datetime,
                topic="x_social",
                summary=text,
                capture_method="api",
                provider_status="ok",
                source_confidence=35.0,
                data_warnings="headline_only_source,social_text_source",
                as_of_date=date.today().isoformat(),
                effective_date=signal_date,
            )
            upsert_news_catalyst_source_snapshot(config.database_path, snapshot)
            fetched_count += 1
            if _snapshot_has_aggregate_value(snapshot):
                numeric_stored_count += 1
            stored_tickers.add(ticker)
    return NewsCatalystProviderFetchResult(
        provider="x_recent_search",
        fetched_count=fetched_count,
        stored_count=fetched_count,
        skipped_count=skipped_count,
        tickers=tuple(sorted(stored_tickers)),
        warnings=tuple(dict.fromkeys(warnings)),
        cache_hits=state.cache_hits,
        cache_misses=state.cache_misses,
        cache_writes=state.cache_writes,
        live_requests=state.live_requests,
        budget_exhausted=state.budget_exhausted,
        numeric_stored_count=numeric_stored_count,
    )


def _plain_text_from_htmlish(value: object) -> str:
    text = str(value or "")
    cleaned = []
    in_tag = False
    for char in text:
        if char == "<":
            in_tag = True
            cleaned.append(" ")
            continue
        if char == ">":
            in_tag = False
            continue
        if not in_tag:
            cleaned.append(char)
    return " ".join("".join(cleaned).split())


def _fetch_truth_social_rows(
    config: AppConfig,
    tickers: tuple[str, ...],
    max_tickers: int | None = None,
    force_refresh: bool = False,
    use_cache: bool | None = None,
    record_failures: bool = True,
) -> NewsCatalystProviderFetchResult:
    docs_url = "https://truthsocial.com/api/v1/accounts/lookup"
    state = _ProviderFetchState(live_budget=_live_request_budget(config, max_tickers))
    fetched_count = 0
    skipped_count = 0
    stored_tickers: set[str] = set()
    warnings: list[str] = []
    account_query = urlencode({"acct": TRUTH_SOCIAL_ACCOUNT})
    lookup_url = f"https://truthsocial.com/api/v1/accounts/lookup?{account_query}"
    lookup_payload, lookup_warning, _ = _fetch_provider_payload(
        config,
        "truth_social_public",
        "TRUTH_SOCIAL",
        lookup_url,
        state,
        force_refresh=force_refresh,
        use_cache=use_cache,
    )
    if lookup_warning:
        _store_provider_failures(config, tickers, "truth_social_public", lookup_warning, docs_url, enabled=record_failures)
        return NewsCatalystProviderFetchResult(
            provider="truth_social_public",
            fetched_count=0,
            stored_count=0,
            skipped_count=len(tickers),
            tickers=(),
            warnings=tuple(f"{ticker}:{lookup_warning}" for ticker in tickers),
            cache_hits=state.cache_hits,
            cache_misses=state.cache_misses,
            cache_writes=state.cache_writes,
            live_requests=state.live_requests,
            budget_exhausted=state.budget_exhausted,
        )
    if not isinstance(lookup_payload, dict) or not lookup_payload.get("id"):
        warning = "truth_social_account_lookup_failed"
        _store_provider_failures(config, tickers, "truth_social_public", warning, docs_url, enabled=record_failures)
        return NewsCatalystProviderFetchResult(
            provider="truth_social_public",
            fetched_count=0,
            stored_count=0,
            skipped_count=len(tickers),
            tickers=(),
            warnings=tuple(f"{ticker}:{warning}" for ticker in tickers),
            cache_hits=state.cache_hits,
            cache_misses=state.cache_misses,
            cache_writes=state.cache_writes,
            live_requests=state.live_requests,
            budget_exhausted=state.budget_exhausted,
        )
    account_id = str(lookup_payload["id"])
    statuses_url = (
        f"https://truthsocial.com/api/v1/accounts/{account_id}/statuses?"
        + urlencode({"limit": str(max(10, config.signals_news_catalyst_max_items_per_ticker))})
    )
    statuses_payload, statuses_warning, from_cache = _fetch_provider_payload(
        config,
        "truth_social_public",
        TRUTH_SOCIAL_ACCOUNT,
        statuses_url,
        state,
        force_refresh=force_refresh,
        use_cache=use_cache,
    )
    if statuses_warning:
        _store_provider_failures(config, tickers, "truth_social_public", statuses_warning, docs_url, enabled=record_failures)
        return NewsCatalystProviderFetchResult(
            provider="truth_social_public",
            fetched_count=0,
            stored_count=0,
            skipped_count=len(tickers),
            tickers=(),
            warnings=tuple(f"{ticker}:{statuses_warning}" for ticker in tickers),
            cache_hits=state.cache_hits,
            cache_misses=state.cache_misses,
            cache_writes=state.cache_writes,
            live_requests=state.live_requests,
            budget_exhausted=state.budget_exhausted,
        )
    rows = _list_payload_rows(statuses_payload)
    if not rows:
        warning = "truth_social_no_posts"
        _store_provider_failures(config, tickers, "truth_social_public", warning, docs_url, provider_status="skipped", enabled=record_failures)
        return NewsCatalystProviderFetchResult(
            provider="truth_social_public",
            fetched_count=0,
            stored_count=0,
            skipped_count=len(tickers),
            tickers=(),
            warnings=tuple(f"{ticker}:{warning}" for ticker in tickers),
            cache_hits=state.cache_hits,
            cache_misses=state.cache_misses,
            cache_writes=state.cache_writes,
            live_requests=state.live_requests,
            budget_exhausted=state.budget_exhausted,
        )
    if not from_cache:
        _write_provider_cache(config, "truth_social_public", TRUTH_SOCIAL_ACCOUNT, statuses_payload)
        state.cache_writes += 1

    assets, _, _ = _asset_maps(config)
    for ticker in tickers:
        terms = {ticker.lower(), f"${ticker.lower()}"}
        asset = assets.get(ticker)
        if asset and asset.name:
            terms.update(part.lower() for part in asset.name.replace(",", " ").split() if len(part) > 3)
        matched = 0
        for item in rows:
            text = _plain_text_from_htmlish(item.get("content"))
            lowered = text.lower()
            if not any(term in lowered for term in terms):
                continue
            signal_date, article_datetime = _isoish_time(item.get("created_at"))
            post_id = str(item.get("id") or "")
            source_url = str(item.get("url") or f"https://truthsocial.com/@{TRUTH_SOCIAL_ACCOUNT}/posts/{post_id}")
            snapshot = NewsCatalystSourceSnapshot(
                ticker=ticker,
                signal_date=signal_date,
                source="truth_social_public",
                source_url=source_url,
                headline_or_event=text[:240] or "Truth Social public post",
                article_datetime=article_datetime,
                topic="truth_social_macro",
                summary=text,
                capture_method="public_api",
                provider_status="ok",
                source_confidence=25.0,
                data_warnings="headline_only_source,macro_social_text_source",
                as_of_date=date.today().isoformat(),
                effective_date=signal_date,
            )
            upsert_news_catalyst_source_snapshot(config.database_path, snapshot)
            fetched_count += 1
            matched += 1
            stored_tickers.add(ticker)
            if matched >= config.signals_news_catalyst_max_items_per_ticker:
                break
        if matched == 0:
            skipped_count += 1
            warnings.append(f"{ticker}:truth_social_no_matching_posts")
    return NewsCatalystProviderFetchResult(
        provider="truth_social_public",
        fetched_count=fetched_count,
        stored_count=fetched_count,
        skipped_count=skipped_count,
        tickers=tuple(sorted(stored_tickers)),
        warnings=tuple(dict.fromkeys(warnings)),
        cache_hits=state.cache_hits,
        cache_misses=state.cache_misses,
        cache_writes=state.cache_writes,
        live_requests=state.live_requests,
        budget_exhausted=state.budget_exhausted,
    )


def fetch_news_catalyst_sources(
    config: AppConfig,
    provider: str = "all",
    ticker: str | None = None,
    max_tickers: int | None = None,
    force_refresh: bool = False,
    use_cache: bool | None = None,
    coverage_plan: bool = False,
    coverage_mode: str = "all",
    _tickers_override: tuple[str, ...] | None = None,
    record_failures: bool = True,
) -> NewsCatalystProviderFetchResult:
    provider_key = provider.strip().lower()
    if _tickers_override is not None:
        tickers = list(_tickers_override)
    elif coverage_plan and ticker is None:
        plan = news_catalyst_coverage_plan(
            config, max_tickers=max_tickers, mode=coverage_mode
        )
        tickers = list(plan.planned_tickers)
    else:
        tickers = _active_equity_tickers(config, ticker=ticker)
    if provider_key == "all":
        providers = tuple(
            item
            for item in config.signals_news_catalyst_provider_order
            if item in config.signals_news_catalyst_enabled_providers
            and item != "source_export"
        )
        results = [
            fetch_news_catalyst_sources(
                config,
                provider=item,
                ticker=ticker,
                max_tickers=max_tickers,
                force_refresh=force_refresh,
                use_cache=use_cache,
                coverage_plan=False,
                coverage_mode=coverage_mode,
                _tickers_override=tuple(tickers),
                record_failures=record_failures,
            )
            for item in providers
        ]
        return NewsCatalystProviderFetchResult(
            provider="all",
            fetched_count=sum(result.fetched_count for result in results),
            stored_count=sum(result.stored_count for result in results),
            skipped_count=sum(result.skipped_count for result in results),
            tickers=tuple(sorted({ticker for result in results for ticker in result.tickers})),
            warnings=tuple(
                dict.fromkeys(warning for result in results for warning in result.warnings)
            ),
            cache_hits=sum(result.cache_hits for result in results),
            cache_misses=sum(result.cache_misses for result in results),
            cache_writes=sum(result.cache_writes for result in results),
            live_requests=sum(result.live_requests for result in results),
            budget_exhausted=any(result.budget_exhausted for result in results),
            numeric_stored_count=sum(result.numeric_stored_count for result in results),
        )
    if provider_key == "alpha_vantage":
        return _fetch_alpha_vantage_news_rows(
            config,
            tickers,
            max_tickers=max_tickers,
            force_refresh=force_refresh,
            use_cache=use_cache,
            record_failures=record_failures,
        )
    if provider_key == "marketaux":
        return _fetch_marketaux_news_rows(
            config,
            tickers,
            max_tickers=max_tickers,
            force_refresh=force_refresh,
            use_cache=use_cache,
            record_failures=record_failures,
        )
    if provider_key == "eodhd":
        return _fetch_eodhd_news_rows(
            config,
            tickers,
            max_tickers=max_tickers,
            force_refresh=force_refresh,
            use_cache=use_cache,
            record_failures=record_failures,
        )
    if provider_key == "finnhub":
        return _fetch_finnhub_news_rows(
            config,
            tickers,
            max_tickers=max_tickers,
            force_refresh=force_refresh,
            use_cache=use_cache,
            record_failures=record_failures,
        )
    if provider_key in {"x_recent_search", "x"}:
        return _fetch_x_recent_search_rows(
            config,
            tickers,
            max_tickers=max_tickers,
            force_refresh=force_refresh,
            use_cache=use_cache,
            record_failures=record_failures,
        )
    if provider_key in {"truth_social_public", "truth_social"}:
        return _fetch_truth_social_rows(
            config,
            tickers,
            max_tickers=max_tickers,
            force_refresh=force_refresh,
            use_cache=use_cache,
            record_failures=record_failures,
        )
    if provider_key in {"fmp", "financial_modeling_prep"}:
        return _fetch_fmp_news_rows(
            config,
            tickers,
            max_tickers=max_tickers,
            force_refresh=force_refresh,
            use_cache=use_cache,
            record_failures=record_failures,
        )
    return NewsCatalystProviderFetchResult(
        provider=provider_key,
        fetched_count=0,
        stored_count=0,
        skipped_count=len(tickers),
        tickers=(),
        warnings=(f"unsupported_news_catalyst_provider:{provider_key}",),
    )


def _classify_provider_smoke_test(
    result: NewsCatalystProviderFetchResult,
) -> str:
    warning_text = ",".join(result.warnings).lower()
    if result.numeric_stored_count > 0:
        return "provider_numeric_available"
    if result.stored_count > 0:
        return "headline_only"
    if "missing_" in warning_text:
        return "missing_key"
    if "auth_failed" in warning_text:
        return "auth_failed"
    if "rate_limited" in warning_text:
        return "rate_limited"
    if "plan_limited" in warning_text or "forbidden" in warning_text:
        return "plan_limited"
    return "http_failed"


def test_news_catalyst_provider(
    config: AppConfig,
    provider: str = "all",
    ticker: str = "AAPL",
) -> tuple[NewsCatalystProviderSmokeTestResult, ...]:
    provider_key = provider.strip().lower()
    if provider_key == "all":
        providers = PROVIDER_NATIVE_SMOKE_TEST_PROVIDERS
    elif provider_key in PROVIDER_NATIVE_SMOKE_TEST_PROVIDERS:
        providers = (provider_key,)
    else:
        normalized_ticker = normalize_ticker(ticker)
        return (
            NewsCatalystProviderSmokeTestResult(
                provider=provider_key,
                ticker=normalized_ticker,
                status="http_failed",
                fetched_count=0,
                stored_count=0,
                numeric_stored_count=0,
                warnings=(f"unsupported_news_catalyst_provider:{provider_key}",),
            ),
        )

    normalized_ticker = normalize_ticker(ticker)
    if normalized_ticker not in _active_equity_tickers(config, ticker=normalized_ticker):
        return tuple(
            NewsCatalystProviderSmokeTestResult(
                provider=item,
                ticker=normalized_ticker,
                status="http_failed",
                fetched_count=0,
                stored_count=0,
                numeric_stored_count=0,
                warnings=(f"{normalized_ticker}:ticker_not_active_equity",),
            )
            for item in providers
        )

    results: list[NewsCatalystProviderSmokeTestResult] = []
    for item in providers:
        fetch_result = fetch_news_catalyst_sources(
            config,
            provider=item,
            ticker=normalized_ticker,
            max_tickers=1,
            force_refresh=True,
            use_cache=False,
            record_failures=False,
        )
        results.append(
            NewsCatalystProviderSmokeTestResult(
                provider=item,
                ticker=normalized_ticker,
                status=_classify_provider_smoke_test(fetch_result),
                fetched_count=fetch_result.fetched_count,
                stored_count=fetch_result.stored_count,
                numeric_stored_count=fetch_result.numeric_stored_count,
                warnings=fetch_result.warnings,
                live_requests=fetch_result.live_requests,
                cache_hits=fetch_result.cache_hits,
                cache_misses=fetch_result.cache_misses,
            )
        )
    return tuple(results)


def build_news_catalyst_provider_smoke_test_text(
    config: AppConfig,
    provider: str = "all",
    ticker: str = "AAPL",
) -> str:
    results = test_news_catalyst_provider(config, provider=provider, ticker=ticker)
    lines = [
        "News/Catalyst Provider Smoke Test",
        f"Ticker: {normalize_ticker(ticker)}",
        f"Provider: {provider.strip().lower()}",
        "",
        "Provider | Status | Fetched | Stored | Numeric Stored | Live Requests | Warnings",
    ]
    for result in results:
        lines.append(
            " | ".join(
                (
                    result.provider,
                    result.status,
                    str(result.fetched_count),
                    str(result.stored_count),
                    str(result.numeric_stored_count),
                    str(result.live_requests),
                    ", ".join(result.warnings) if result.warnings else "none",
                )
            )
        )
    return "\n".join(lines)


def _provider_snapshot_metrics(
    config: AppConfig,
    provider: str,
) -> tuple[int, int, str | None]:
    try:
        snapshots = [
            snapshot
            for snapshot in list_news_catalyst_source_snapshots(config.database_path)
            if _source_key(snapshot.source) == _source_key(provider)
        ]
    except sqlite3.Error:
        return 0, 0, None
    numeric_count = sum(1 for snapshot in snapshots if _snapshot_has_aggregate_value(snapshot))
    headline_only_count = sum(
        1
        for snapshot in snapshots
        if not _snapshot_has_aggregate_value(snapshot)
        and (snapshot.provider_status or "ok").strip().lower() == "ok"
    )
    warning_rows = [
        snapshot
        for snapshot in snapshots
        if snapshot.data_warnings
        or (snapshot.provider_status or "ok").strip().lower() not in {"ok"}
    ]
    latest_warning_row = max(
        warning_rows,
        key=lambda snapshot: (snapshot.as_of_date or "", snapshot.signal_date, snapshot.ticker),
        default=None,
    )
    latest_warning = None
    if latest_warning_row is not None:
        latest_warning = latest_warning_row.data_warnings or latest_warning_row.provider_status
    return numeric_count, headline_only_count, latest_warning


def _text_term_count(text: str, terms: set[str]) -> int:
    lowered = text.lower()
    return sum(1 for term in terms if term in lowered)


def _text_backfill_scores(snapshot: NewsCatalystSourceSnapshot) -> tuple[float, float, float]:
    text = " ".join(
        part
        for part in (
            snapshot.headline_or_event,
            snapshot.summary,
            snapshot.topic,
        )
        if part
    )
    positive_count = _text_term_count(text, POSITIVE_TEXT_TERMS)
    negative_count = _text_term_count(text, NEGATIVE_TEXT_TERMS)
    catalyst_count = _text_term_count(text, CATALYST_TEXT_TERMS)
    urgency_count = _text_term_count(text, URGENCY_TEXT_TERMS)
    sentiment = _clamp_score(50.0 + positive_count * 7.0 - negative_count * 7.0)
    catalyst = _clamp_score(45.0 + catalyst_count * 10.0 + positive_count * 2.0)
    urgency = _clamp_score(40.0 + urgency_count * 12.0 + catalyst_count * 3.0)
    return sentiment, catalyst, urgency


def compute_news_catalyst_text_backfill(
    config: AppConfig,
    ticker: str | None = None,
) -> NewsCatalystTextBackfillResult:
    if not config.signals_news_catalyst_text_backfill_enabled:
        return NewsCatalystTextBackfillResult(
            derived_count=0,
            skipped_count=0,
            tickers=(),
            warnings=("news_catalyst_text_backfill_disabled",),
        )

    wanted_ticker = normalize_ticker(ticker) if ticker else None
    _, equity_assets, _ = _asset_maps(config)
    snapshots = list_news_catalyst_source_snapshots(config.database_path, ticker=wanted_ticker)
    snapshots_by_ticker: dict[str, list[NewsCatalystSourceSnapshot]] = {}
    for snapshot in snapshots:
        if snapshot.ticker not in equity_assets:
            continue
        snapshots_by_ticker.setdefault(snapshot.ticker, []).append(snapshot)

    derived_count = 0
    skipped_count = 0
    derived_tickers: set[str] = set()
    warnings: list[str] = []
    for group_ticker, group_snapshots in sorted(snapshots_by_ticker.items()):
        if wanted_ticker and group_ticker != wanted_ticker:
            continue
        provider_numeric = [
            snapshot
            for snapshot in group_snapshots
            if _snapshot_has_aggregate_value(snapshot)
            and _source_key(snapshot.source) != "news_text_backfill"
            and (snapshot.provider_status or "ok").strip().lower() == "ok"
        ]
        if provider_numeric:
            skipped_count += 1
            warnings.append(f"{group_ticker}:provider_numeric_already_available")
            continue
        text_snapshots = [
            snapshot
            for snapshot in group_snapshots
            if not _snapshot_has_aggregate_value(snapshot)
            and (snapshot.provider_status or "ok").strip().lower() == "ok"
            and snapshot.source_url
            and snapshot.headline_or_event
            and _source_key(snapshot.source) != "news_text_backfill"
        ]
        if not text_snapshots:
            skipped_count += 1
            warnings.append(f"{group_ticker}:no_source_backed_text_for_backfill")
            continue
        latest_date = max(snapshot.signal_date for snapshot in text_snapshots)
        latest_text_snapshots = [
            snapshot for snapshot in text_snapshots if snapshot.signal_date == latest_date
        ]
        for snapshot in latest_text_snapshots[: config.signals_news_catalyst_max_items_per_ticker]:
            sentiment, catalyst, urgency = _text_backfill_scores(snapshot)
            derived_snapshot = NewsCatalystSourceSnapshot(
                ticker=group_ticker,
                signal_date=snapshot.signal_date,
                source="news_text_backfill",
                source_url=snapshot.source_url,
                headline_or_event=snapshot.headline_or_event,
                article_datetime=snapshot.article_datetime,
                event_date=snapshot.event_date,
                topic=snapshot.topic,
                summary=snapshot.summary,
                capture_method="derived_text_backfill",
                provider_status="ok",
                sentiment_score=sentiment,
                catalyst_score=catalyst,
                urgency_score=urgency,
                relevance_score=snapshot.relevance_score,
                source_confidence=35.0,
                data_warnings=(
                    "text_derived_sentiment,lower_confidence_source,"
                    f"not_provider_numeric,derived_from:{snapshot.source}"
                ),
                as_of_date=date.today().isoformat(),
                effective_date=snapshot.signal_date,
            )
            upsert_news_catalyst_source_snapshot(config.database_path, derived_snapshot)
            derived_count += 1
            derived_tickers.add(group_ticker)
        warnings.append(f"{group_ticker}:text_derived_sentiment")

    return NewsCatalystTextBackfillResult(
        derived_count=derived_count,
        skipped_count=skipped_count,
        tickers=tuple(sorted(derived_tickers)),
        warnings=tuple(dict.fromkeys(warnings)),
    )


def news_catalyst_provider_statuses(config: AppConfig) -> tuple[NewsCatalystProviderStatus, ...]:
    statuses: list[NewsCatalystProviderStatus] = []
    enabled = set(config.signals_news_catalyst_enabled_providers)
    for provider in config.signals_news_catalyst_provider_order:
        provider_key = provider.strip().lower()
        cache_file_count = len(_cache_files(config, provider_key))
        latest_cache_at = _latest_cache_at(config, provider_key)
        numeric_count, headline_only_count, latest_warning = _provider_snapshot_metrics(
            config,
            provider_key,
        )
        if provider_key == "source_export":
            available = config.news_catalyst_source_exports_dir.exists()
            statuses.append(
                NewsCatalystProviderStatus(
                    provider="source_export",
                    enabled=provider_key in enabled,
                    available=available,
                    status="available" if available else "missing_directory",
                    details=str(config.news_catalyst_source_exports_dir),
                    cache_file_count=cache_file_count,
                    latest_cache_at=latest_cache_at,
                    numeric_snapshot_count=numeric_count,
                    headline_only_snapshot_count=headline_only_count,
                    latest_warning=latest_warning,
                )
            )
            continue
        if provider_key == "alpha_vantage":
            available = bool(_secret_env("ALPHAVANTAGE_API_KEY"))
            details = "ALPHAVANTAGE_API_KEY present" if available else "missing ALPHAVANTAGE_API_KEY"
        elif provider_key == "marketaux":
            available = bool(_secret_env("MARKETAUX_API_KEY") or _secret_env("MARKET_AUX_API_KEY"))
            details = "MARKETAUX_API_KEY present" if available else "missing MARKETAUX_API_KEY"
        elif provider_key == "eodhd":
            available = bool(_secret_env("EODHD_API_KEY") or _secret_env("EOD_HISTORICAL_DATA_API_KEY"))
            details = "EODHD_API_KEY present" if available else "missing EODHD_API_KEY"
        elif provider_key == "finnhub":
            available = bool(_secret_env("FINNHUB_API_KEY") or _secret_env("FINHUB_API_KEY"))
            details = "FINNHUB_API_KEY present" if available else "missing FINNHUB_API_KEY"
        elif provider_key in {"fmp", "financial_modeling_prep"}:
            available = bool(_secret_env("FMP_API_KEY") or _secret_env("FINANCIAL_MODELING_PREP_API_KEY"))
            details = "FMP API key present" if available else "missing FMP_API_KEY"
        elif provider_key in {"x_recent_search", "x"}:
            available = bool(_secret_env("X_BEARER_TOKEN") or _secret_env("TWITTER_BEARER_TOKEN"))
            details = "X_BEARER_TOKEN present" if available else "missing X_BEARER_TOKEN"
        elif provider_key in {"truth_social_public", "truth_social"}:
            available = True
            details = "public unauthenticated endpoint"
        else:
            available = False
            details = "unsupported provider"
        statuses.append(
            NewsCatalystProviderStatus(
                provider=provider_key,
                enabled=provider_key in enabled,
                available=available,
                status="available" if available else "unavailable",
                details=details,
                cache_file_count=cache_file_count,
                latest_cache_at=latest_cache_at,
                numeric_snapshot_count=numeric_count,
                headline_only_snapshot_count=headline_only_count,
                latest_warning=latest_warning,
            )
        )
    return tuple(statuses)


def _aggregate_rows_by_ticker(config: AppConfig) -> dict[str, list[NewsCatalystAggregate]]:
    try:
        rows = list_news_catalyst_aggregates(config.database_path)
    except sqlite3.Error:
        return {}
    by_ticker: dict[str, list[NewsCatalystAggregate]] = {}
    for row in rows:
        by_ticker.setdefault(row.ticker, []).append(row)
    return by_ticker


def _final_rows_by_ticker(config: AppConfig) -> dict[str, list[dict[str, str]]]:
    if not config.news_catalysts_path.exists():
        return {}
    rows = _read_final_news_rows(config.news_catalysts_path)
    by_ticker: dict[str, list[dict[str, str]]] = {}
    for row in rows:
        ticker = normalize_ticker(row.get("ticker", ""))
        if ticker:
            by_ticker.setdefault(ticker, []).append(row)
    return by_ticker


def _latest_aggregate(rows: list[NewsCatalystAggregate]) -> NewsCatalystAggregate:
    return max(rows, key=lambda row: (row.signal_date, row.source))


def _latest_final_row(rows: list[dict[str, str]]) -> dict[str, str]:
    return max(rows, key=lambda row: (row.get("signal_date", ""), row.get("source", "")))


def _row_has_source_fields(row: dict[str, str]) -> bool:
    return bool(row.get("source_url", "").strip() and row.get("headline_or_event", "").strip())


def _row_has_numeric_signal(row: dict[str, str]) -> bool:
    return any((row.get(field) or "").strip() for field in AGGREGATE_NUMERIC_FIELDS)


def _provider_native_validation_summary(
    config: AppConfig,
) -> tuple[int, tuple[str, ...], tuple[str, ...]]:
    if not config.news_catalyst_source_exports_dir.exists():
        return 0, (), ()
    warnings: list[str] = []
    for path in sorted(config.news_catalyst_source_exports_dir.rglob("*.csv")):
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8-sig")
        except OSError:
            continue
        path_warnings = _provider_native_validation_warnings_for_text(text)
        try:
            relative = str(path.relative_to(config.news_catalyst_source_exports_dir))
        except ValueError:
            relative = str(path)
        warnings.extend(f"{relative}:{warning}" for warning in path_warnings)
    tickers = []
    for warning in warnings:
        parts = warning.split(":")
        if len(parts) < 2:
            continue
        ticker = normalize_ticker(parts[-3] if len(parts) >= 3 else parts[0])
        if ticker and not ticker.startswith("ROW_"):
            tickers.append(ticker)
    return len(warnings), tuple(sorted(set(tickers))), tuple(dict.fromkeys(warnings))


def _relative_source_path(path: Path, base: Path) -> str:
    try:
        return str(path.relative_to(base))
    except ValueError:
        return str(path)


def _provider_backfill_source_files(source_dir: Path) -> tuple[Path, ...]:
    if not source_dir.exists():
        return ()
    return tuple(sorted(path for path in source_dir.rglob("*.csv") if path.is_file()))


def _provider_backfill_validation_reasons(
    row: dict[str, str | None],
    row_number: int,
    all_assets: dict[str, Asset],
    equity_assets: dict[str, Asset],
    etf_assets: dict[str, Asset],
) -> tuple[str, ...]:
    reasons = list(_provider_native_upgrade_row_validation_reasons(row, row_number))
    source_key = _source_key(row.get("source"))
    ticker = normalize_ticker(row.get("ticker", ""))
    if source_key and source_key not in PROVIDER_NATIVE_EXPORT_SOURCES:
        reasons.append("unsupported_provider_native_source")
    if ticker:
        if ticker in etf_assets:
            reasons.append("etf_news_catalyst_gated")
        elif ticker not in equity_assets:
            reasons.append("inactive_or_unknown_ticker")
        elif ticker not in all_assets:
            reasons.append("inactive_or_unknown_ticker")
    return tuple(dict.fromkeys(reasons))


def validate_news_catalyst_provider_backfill(
    config: AppConfig,
    directory: Path | None = None,
) -> NewsCatalystProviderBackfillValidationResult:
    source_dir = directory or provider_native_backfill_dir(config)
    all_assets, equity_assets, etf_assets = _asset_maps(config)
    source_files = _provider_backfill_source_files(source_dir)
    warnings: list[str] = []
    valid_tickers: list[str] = []
    blank_tickers: list[str] = []
    invalid_tickers: list[str] = []
    unsupported_tickers: list[str] = []
    etf_gated_tickers: list[str] = []
    total_rows = 0
    valid_rows = 0
    blank_rows = 0
    invalid_rows = 0

    if not source_dir.exists():
        warnings.append("missing_provider_native_backfill_dir")
    elif not source_files:
        warnings.append("no_provider_native_backfill_csv_files")

    for path in source_files:
        relative = _relative_source_path(path, source_dir)
        try:
            text = path.read_text(encoding="utf-8-sig")
        except OSError as error:
            warnings.append(f"{relative}:read_failed:{error.__class__.__name__}")
            continue

        reader = csv.DictReader(text.splitlines())
        if not reader.fieldnames:
            warnings.append(f"{relative}:missing_header")
            continue
        missing = REQUIRED_SOURCE_EXPORT_COLUMNS - set(reader.fieldnames)
        if missing:
            warnings.append(
                f"{relative}:missing_required_columns:" + ",".join(sorted(missing))
            )
            continue

        for row_number, row in enumerate(reader, start=2):
            if not any((value or "").strip() for value in row.values()):
                continue
            total_rows += 1
            normalized_row = {
                header: (row.get(header) or "") for header in reader.fieldnames
            }
            ticker = normalize_ticker(normalized_row.get("ticker", ""))
            label = ticker or f"row_{row_number}"
            if _is_blank_provider_upgrade_placeholder(normalized_row):
                blank_rows += 1
                if ticker:
                    blank_tickers.append(ticker)
                continue

            reasons = _provider_backfill_validation_reasons(
                normalized_row,
                row_number,
                all_assets,
                equity_assets,
                etf_assets,
            )
            if reasons:
                invalid_rows += 1
                if ticker:
                    invalid_tickers.append(ticker)
                    if "inactive_or_unknown_ticker" in reasons:
                        unsupported_tickers.append(ticker)
                    if "etf_news_catalyst_gated" in reasons:
                        etf_gated_tickers.append(ticker)
                warnings.append(
                    f"{relative}:{label}:invalid_provider_native_backfill_row:"
                    + ",".join(reasons)
                )
                continue

            valid_rows += 1
            valid_tickers.append(ticker)

    return NewsCatalystProviderBackfillValidationResult(
        source_dir=source_dir,
        source_files=source_files,
        total_row_count=total_rows,
        valid_row_count=valid_rows,
        blank_placeholder_count=blank_rows,
        invalid_row_count=invalid_rows,
        unsupported_ticker_count=len(set(unsupported_tickers)),
        etf_gated_count=len(set(etf_gated_tickers)),
        valid_tickers=tuple(sorted(set(valid_tickers))),
        blank_placeholder_tickers=tuple(sorted(set(blank_tickers))),
        invalid_tickers=tuple(sorted(set(invalid_tickers))),
        unsupported_tickers=tuple(sorted(set(unsupported_tickers))),
        etf_gated_tickers=tuple(sorted(set(etf_gated_tickers))),
        warnings=tuple(dict.fromkeys(warnings)),
    )


PROVIDER_UPGRADE_NEXT_COMMANDS = (
    "python -m target_opportunity_monitor import-news-catalyst-source-exports",
    "python -m target_opportunity_monitor aggregate-news-catalyst-sources",
    "python -m target_opportunity_monitor load-news-catalysts",
    "python -m target_opportunity_monitor compute-news-catalyst-signals",
    "python -m target_opportunity_monitor validate-news-catalyst-signals",
)


def preview_news_catalyst_provider_upgrade(
    config: AppConfig,
    directory: Path | None = None,
) -> NewsCatalystProviderUpgradePreview:
    validation = validate_news_catalyst_provider_backfill(config, directory=directory)
    report = news_catalyst_source_status_report(config)
    current_provider_native_tickers = tuple(report.provider_numeric_tickers)
    text_derived_only_tickers = tuple(report.provider_native_upgrade_tickers)
    candidate_tickers = set(validation.valid_tickers)
    valid_backfill_tickers = tuple(
        sorted(
            candidate_tickers
            & set(text_derived_only_tickers)
            - set(current_provider_native_tickers)
        )
    )
    projected_provider_native_tickers = tuple(
        sorted(set(current_provider_native_tickers) | set(valid_backfill_tickers))
    )
    still_blocked_tickers = tuple(
        sorted(set(text_derived_only_tickers) - set(valid_backfill_tickers))
    )
    warnings = list(validation.warnings)
    if not validation.valid_row_count:
        warnings.append("no_valid_provider_native_backfill_rows")
    if still_blocked_tickers:
        warnings.append("provider_native_upgrade_still_blocked")
    if validation.invalid_row_count:
        warnings.append("invalid_provider_native_backfill_rows")
    return NewsCatalystProviderUpgradePreview(
        validation=validation,
        active_equity_count=report.active_equity_count,
        current_provider_native_ticker_count=len(current_provider_native_tickers),
        current_provider_native_tickers=current_provider_native_tickers,
        text_derived_only_tickers=text_derived_only_tickers,
        valid_backfill_tickers=valid_backfill_tickers,
        projected_provider_native_ticker_count=len(projected_provider_native_tickers),
        projected_provider_native_tickers=projected_provider_native_tickers,
        still_blocked_tickers=still_blocked_tickers,
        next_commands=PROVIDER_UPGRADE_NEXT_COMMANDS,
        warnings=tuple(dict.fromkeys(warnings)),
    )


def _provider_backfill_row_classifications(
    config: AppConfig,
    directory: Path | None = None,
) -> dict[str, list[tuple[str, tuple[str, ...]]]]:
    source_dir = directory or provider_native_backfill_dir(config)
    all_assets, equity_assets, etf_assets = _asset_maps(config)
    grouped: dict[str, list[tuple[str, tuple[str, ...]]]] = {}
    for path in _provider_backfill_source_files(source_dir):
        try:
            text = path.read_text(encoding="utf-8-sig")
        except OSError:
            continue
        reader = csv.DictReader(text.splitlines())
        if not reader.fieldnames:
            continue
        missing = REQUIRED_SOURCE_EXPORT_COLUMNS - set(reader.fieldnames)
        if missing:
            continue
        for row_number, row in enumerate(reader, start=2):
            if not any((value or "").strip() for value in row.values()):
                continue
            normalized_row = {
                header: (row.get(header) or "") for header in reader.fieldnames
            }
            ticker = normalize_ticker(normalized_row.get("ticker", ""))
            label = ticker or f"ROW_{row_number}"
            if _is_blank_provider_upgrade_placeholder(normalized_row):
                grouped.setdefault(label, []).append(("blank_placeholder", ()))
                continue
            reasons = _provider_backfill_validation_reasons(
                normalized_row,
                row_number,
                all_assets,
                equity_assets,
                etf_assets,
            )
            if reasons:
                grouped.setdefault(label, []).append(("invalid", reasons))
            else:
                grouped.setdefault(label, []).append(("valid", ()))
    return grouped


def news_catalyst_provider_backfill_diagnostics(
    config: AppConfig,
    directory: Path | None = None,
) -> tuple[NewsCatalystProviderBackfillDiagnostic, ...]:
    preview = preview_news_catalyst_provider_upgrade(config, directory=directory)
    grouped = _provider_backfill_row_classifications(config, directory=directory)
    current = set(preview.current_provider_native_tickers)
    text_derived_only = set(preview.text_derived_only_tickers)
    diagnostic_tickers = sorted(set(grouped) | current | text_derived_only)
    diagnostics: list[NewsCatalystProviderBackfillDiagnostic] = []
    for ticker in diagnostic_tickers:
        rows = grouped.get(ticker, [])
        valid_rows = sum(1 for status, _reasons in rows if status == "valid")
        blank_rows = sum(1 for status, _reasons in rows if status == "blank_placeholder")
        invalid_rows = sum(1 for status, _reasons in rows if status == "invalid")
        warnings = tuple(
            dict.fromkeys(
                reason
                for status, reasons in rows
                if status == "invalid"
                for reason in reasons
            )
        )
        is_current = ticker in current
        needs_upgrade = ticker in text_derived_only
        if is_current:
            classification = "provider_native_current"
            recommended_action = "No provider-native backfill action needed."
        elif valid_rows and needs_upgrade:
            classification = "valid_provider_native_row_ready"
            recommended_action = "Validate, then apply provider-native backfill with confirmation."
        elif invalid_rows:
            classification = "invalid_provider_native_row"
            recommended_action = "Fix invalid provider-native source-export rows."
        elif blank_rows:
            classification = "blank_placeholder"
            recommended_action = "Fill source-backed provider-native fields or leave the row blank."
        elif needs_upgrade:
            classification = "provider_native_row_needed"
            recommended_action = "Add a source-backed provider-native numeric row."
        elif valid_rows:
            classification = "valid_row_no_upgrade_needed"
            recommended_action = "Row is valid, but it does not improve provider-native coverage."
        else:
            classification = "no_backfill_action"
            recommended_action = "No provider-native backfill action needed."
        diagnostics.append(
            NewsCatalystProviderBackfillDiagnostic(
                ticker=ticker,
                classification=classification,
                current_provider_native=is_current,
                text_derived_only=needs_upgrade,
                valid_rows=valid_rows,
                blank_placeholder_rows=blank_rows,
                invalid_rows=invalid_rows,
                warnings=warnings,
                recommended_action=recommended_action,
            )
        )
    return tuple(diagnostics)


def news_catalyst_provider_backfill_apply_status(
    config: AppConfig,
    allow_partial: bool = False,
    directory: Path | None = None,
) -> NewsCatalystProviderBackfillApplyStatus:
    preview = preview_news_catalyst_provider_upgrade(config, directory=directory)
    projected_delta = (
        preview.projected_provider_native_ticker_count
        - preview.current_provider_native_ticker_count
    )
    blocked_reason: str | None = None
    if preview.validation.invalid_row_count:
        blocked_reason = "invalid_provider_native_backfill_rows"
    elif not preview.valid_backfill_tickers:
        blocked_reason = "no_valid_provider_native_backfill_rows"
    elif projected_delta <= 0:
        blocked_reason = "provider_native_coverage_would_not_improve"
    elif preview.still_blocked_tickers and not allow_partial:
        blocked_reason = "partial_provider_native_backfill_requires_allow_partial"

    warnings = list(preview.warnings)
    if blocked_reason:
        warnings.append(blocked_reason)
    if allow_partial and preview.still_blocked_tickers and projected_delta > 0:
        warnings.append("partial_provider_native_backfill_allowed")
    return NewsCatalystProviderBackfillApplyStatus(
        preview=preview,
        allow_partial=allow_partial,
        backfill_apply_ready=blocked_reason is None,
        projected_upgrade_delta=max(0, projected_delta),
        valid_upgrade_tickers=preview.valid_backfill_tickers,
        blocked_apply_reason=blocked_reason,
        warnings=tuple(dict.fromkeys(warnings)),
    )


def apply_news_catalyst_provider_backfill(
    config: AppConfig,
    *,
    confirm: bool = False,
    allow_partial: bool = False,
    directory: Path | None = None,
) -> NewsCatalystProviderBackfillApplyResult:
    status = news_catalyst_provider_backfill_apply_status(
        config,
        allow_partial=allow_partial,
        directory=directory,
    )
    warnings = list(status.warnings)
    if not confirm:
        warnings.append("dry_run_only")
        return NewsCatalystProviderBackfillApplyResult(
            confirmed=False,
            applied=False,
            status=status,
            warnings=tuple(dict.fromkeys(warnings)),
        )
    if not status.backfill_apply_ready:
        warnings.append("provider_native_backfill_apply_blocked")
        return NewsCatalystProviderBackfillApplyResult(
            confirmed=True,
            applied=False,
            status=status,
            warnings=tuple(dict.fromkeys(warnings)),
        )

    from .news_catalysts import compute_news_catalyst_signals, load_news_catalysts_csv
    from .signal_validation import validate_news_catalyst_signals

    import_result = import_news_catalyst_source_exports(
        config,
        directory=status.preview.validation.source_dir,
    )
    aggregate_result = aggregate_news_catalyst_sources(config)
    load_result = load_news_catalysts_csv(config)
    compute_result = compute_news_catalyst_signals(config)
    validation_result = validate_news_catalyst_signals(config)
    warnings.extend(import_result.warnings)
    warnings.extend(aggregate_result.warnings)
    warnings.extend(load_result.warnings)
    warnings.extend(
        f"{result.ticker}:{','.join(result.warnings)}"
        for result in compute_result.results
        if result.warnings
    )
    warnings.extend(
        f"{result.ticker}:{','.join(result.warnings)}"
        for result in validation_result.results
        if result.warnings
    )
    return NewsCatalystProviderBackfillApplyResult(
        confirmed=True,
        applied=True,
        status=status,
        imported_count=import_result.imported_count,
        aggregate_count=aggregate_result.aggregate_count,
        loaded_row_count=load_result.row_count,
        computed_count=compute_result.computed_count,
        validation_updated_count=validation_result.updated_count,
        warnings=tuple(dict.fromkeys(warnings)),
    )


def _is_stale(signal_date: str | None, stale_after_days: int) -> bool:
    if not signal_date:
        return False
    try:
        parsed = date.fromisoformat(signal_date)
    except ValueError:
        return True
    return (date.today() - parsed).days > stale_after_days


def news_catalyst_source_status_report(config: AppConfig) -> NewsCatalystSourceStatusReport:
    all_assets, equity_assets, etf_assets = _asset_maps(config)
    rows_by_ticker = _final_rows_by_ticker(config)
    aggregates_by_ticker = _aggregate_rows_by_ticker(config)
    try:
        all_snapshots = list_news_catalyst_source_snapshots(config.database_path)
        source_snapshot_count = len(all_snapshots)
        aggregate_count = len(list_news_catalyst_aggregates(config.database_path))
    except sqlite3.Error:
        all_snapshots = []
        source_snapshot_count = 0
        aggregate_count = 0
    numeric_snapshot_count = sum(
        1 for snapshot in all_snapshots if _snapshot_has_aggregate_value(snapshot)
    )
    provider_numeric_snapshots = [
        snapshot
        for snapshot in all_snapshots
        if _snapshot_has_aggregate_value(snapshot)
        and not _is_text_derived_snapshot(snapshot)
    ]
    text_derived_snapshots = [
        snapshot
        for snapshot in all_snapshots
        if _snapshot_has_aggregate_value(snapshot)
        and _is_text_derived_snapshot(snapshot)
    ]
    provider_numeric_tickers = {
        snapshot.ticker for snapshot in provider_numeric_snapshots if snapshot.ticker in equity_assets
    }
    latest_provider_native_source_date = max(
        (
            snapshot.signal_date
            for snapshot in provider_numeric_snapshots
            if snapshot.ticker in equity_assets
            and (snapshot.provider_status or "ok").strip().lower() == "ok"
        ),
        default=None,
    )
    text_derived_tickers = {
        snapshot.ticker for snapshot in text_derived_snapshots if snapshot.ticker in equity_assets
    }
    total_numeric_tickers = {
        snapshot.ticker
        for snapshot in all_snapshots
        if snapshot.ticker in equity_assets and _snapshot_has_aggregate_value(snapshot)
    }
    missing_numeric_tickers = set(equity_assets) - total_numeric_tickers
    provider_native_upgrade_tickers = text_derived_tickers - provider_numeric_tickers
    headline_only_snapshot_count = sum(
        1
        for snapshot in all_snapshots
        if not _snapshot_has_aggregate_value(snapshot)
        and (snapshot.provider_status or "ok").strip().lower() == "ok"
    )
    statuses: list[NewsCatalystSourceTickerStatus] = []
    source_backed_tickers: list[str] = []
    missing_source_tickers: list[str] = []
    stale_tickers: list[str] = []
    missing_source_field_tickers: list[str] = []

    for ticker, asset in sorted(equity_assets.items()):
        has_provider_numeric = ticker in provider_numeric_tickers
        has_text_derived_numeric = ticker in text_derived_tickers
        provider_native_upgrade_needed = ticker in provider_native_upgrade_tickers
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
            warnings.append("missing_source_backed_news_catalyst_row")
            signal_date = None
            source = None
            source_count = 0
            aggregate_confidence = None
            source_disagreement = None

        if any(not _row_has_source_fields(row) for row in final_rows):
            missing_source_field_tickers.append(ticker)
            warnings.append("missing_source_url_or_headline")
        if provider_native_upgrade_needed:
            warnings.append("provider_native_upgrade_needed")
        stale = _is_stale(signal_date, config.signals_news_catalyst_stale_after_days)
        if stale:
            stale_tickers.append(ticker)
            warnings.append("stale_news_catalyst_source_row")
        statuses.append(
            NewsCatalystSourceTickerStatus(
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
                has_provider_numeric=has_provider_numeric,
                has_text_derived_numeric=has_text_derived_numeric,
                provider_native_upgrade_needed=provider_native_upgrade_needed,
            )
        )

    skipped_etfs = tuple(
        sorted(
            ticker
            for ticker in etf_assets
            if ticker in rows_by_ticker or ticker in aggregates_by_ticker
        )
    )
    (
        provider_native_rejected_row_count,
        provider_native_rejected_tickers,
        provider_native_rejected_warnings,
    ) = _provider_native_validation_summary(config)
    warnings: list[str] = []
    if missing_source_tickers:
        warnings.append("missing_source_backed_news_catalyst_rows")
    if stale_tickers:
        warnings.append("stale_news_catalyst_source_rows")
    if missing_source_field_tickers:
        warnings.append("missing_source_url_or_headline")
    if skipped_etfs:
        warnings.append("etf_news_catalyst_source_gated")
    if provider_native_upgrade_tickers:
        warnings.append("provider_native_news_catalyst_upgrade_needed")
    if provider_native_rejected_row_count:
        warnings.append("invalid_provider_native_upgrade_rows")

    return NewsCatalystSourceStatusReport(
        source_exports_dir=config.news_catalyst_source_exports_dir,
        cache_dir=config.news_catalyst_cache_dir,
        cache_file_count=len(_cache_files(config)),
        latest_cache_at=_latest_cache_at(config),
        provider_numeric_snapshot_count=len(provider_numeric_snapshots),
        text_derived_snapshot_count=len(text_derived_snapshots),
        provider_numeric_ticker_count=len(
            {
                snapshot.ticker
                for snapshot in provider_numeric_snapshots
                if snapshot.ticker in equity_assets
            }
        ),
        text_derived_ticker_count=len(
            {
                snapshot.ticker
                for snapshot in text_derived_snapshots
                if snapshot.ticker in equity_assets
            }
        ),
        total_numeric_ticker_count=len(
            {
                snapshot.ticker
                for snapshot in all_snapshots
                if snapshot.ticker in equity_assets
                and _snapshot_has_aggregate_value(snapshot)
            }
        ),
        numeric_snapshot_count=numeric_snapshot_count,
        headline_only_snapshot_count=headline_only_snapshot_count,
        source_snapshot_count=source_snapshot_count,
        aggregate_count=aggregate_count,
        news_catalysts_path=config.news_catalysts_path,
        news_catalysts_exists=config.news_catalysts_path.exists(),
        active_equity_count=len(equity_assets),
        source_backed_ticker_count=len(source_backed_tickers),
        source_backed_tickers=tuple(sorted(source_backed_tickers)),
        missing_source_tickers=tuple(sorted(missing_source_tickers)),
        missing_numeric_tickers=tuple(sorted(missing_numeric_tickers)),
        provider_numeric_tickers=tuple(sorted(provider_numeric_tickers)),
        text_derived_tickers=tuple(sorted(text_derived_tickers)),
        provider_native_upgrade_tickers=tuple(sorted(provider_native_upgrade_tickers)),
        latest_provider_native_source_date=latest_provider_native_source_date,
        provider_native_rejected_row_count=provider_native_rejected_row_count,
        provider_native_rejected_tickers=provider_native_rejected_tickers,
        provider_native_rejected_warnings=provider_native_rejected_warnings,
        stale_tickers=tuple(sorted(stale_tickers)),
        skipped_etf_tickers=skipped_etfs,
        missing_source_field_tickers=tuple(sorted(set(missing_source_field_tickers))),
        provider_statuses=news_catalyst_provider_statuses(config),
        statuses=tuple(statuses),
        warnings=tuple(dict.fromkeys(warnings)),
    )


def _provider_warning_summary(
    provider_statuses: tuple[NewsCatalystProviderStatus, ...],
) -> tuple[str, ...]:
    warnings: list[str] = []
    for status in provider_statuses:
        if status.latest_warning:
            warnings.append(f"{status.provider}:{status.latest_warning}")
        if status.headline_only_snapshot_count and not status.numeric_snapshot_count:
            warnings.append(f"{status.provider}:headline_only")
        if status.enabled and not status.available:
            warnings.append(f"{status.provider}:unavailable")
    return tuple(dict.fromkeys(warnings))


def _provider_upgrade_blockers(
    provider_statuses: tuple[NewsCatalystProviderStatus, ...],
) -> tuple[str, ...]:
    blockers: list[str] = []
    for status in provider_statuses:
        if not status.enabled:
            continue
        latest_warning = (status.latest_warning or "").lower()
        details = status.details.lower()
        if not status.available and "missing" in details:
            blockers.append(f"{status.provider}:missing_key")
        elif not status.available:
            blockers.append(f"{status.provider}:unavailable")
        if "auth_failed" in latest_warning:
            blockers.append(f"{status.provider}:auth_failed")
        if "rate_limited" in latest_warning:
            blockers.append(f"{status.provider}:rate_limited")
        if "plan_limited" in latest_warning:
            blockers.append(f"{status.provider}:plan_limited")
        if status.headline_only_snapshot_count and not status.numeric_snapshot_count:
            blockers.append(f"{status.provider}:headline_only")
    return tuple(dict.fromkeys(blockers))


def news_catalyst_provider_upgrade_status(
    config: AppConfig,
    max_tickers: int | None = None,
) -> NewsCatalystProviderUpgradeStatus:
    report = news_catalyst_source_status_report(config)
    plan = news_catalyst_coverage_plan(
        config,
        max_tickers=max_tickers,
        write_template=False,
        mode="provider-upgrade",
    )
    provider_statuses = report.provider_statuses
    provider_native_tickers = tuple(report.provider_numeric_tickers)
    text_derived_only_tickers = tuple(report.provider_native_upgrade_tickers)
    available_providers = tuple(
        status.provider
        for status in provider_statuses
        if status.enabled and status.available
    )
    unavailable_providers = tuple(
        status.provider
        for status in provider_statuses
        if status.enabled and not status.available
    )
    missing_key_providers = tuple(
        status.provider
        for status in provider_statuses
        if status.enabled
        and (
            "missing" in status.details.lower()
            or (status.latest_warning or "").startswith("missing_")
        )
    )
    latest_failures = _provider_warning_summary(provider_statuses)
    provider_blockers = _provider_upgrade_blockers(provider_statuses)

    if (
        report.active_equity_count
        and len(provider_native_tickers) >= report.active_equity_count
    ):
        status_value = "provider_native_complete"
    elif plan.planned_tickers:
        status_value = "queued"
    elif text_derived_only_tickers and provider_native_tickers:
        status_value = "partially_upgraded"
    elif text_derived_only_tickers:
        status_value = "not_configured"
    else:
        status_value = "not_configured"

    warnings: list[str] = []
    if text_derived_only_tickers:
        warnings.append("provider_native_news_catalyst_upgrade_needed")
    if missing_key_providers:
        warnings.append("missing_keys")
    if any("rate_limited" in blocker or "plan_limited" in blocker for blocker in provider_blockers):
        warnings.append("provider_limited")
    if plan.planned_tickers:
        warnings.append("queued")
    if report.provider_native_rejected_row_count:
        warnings.append("invalid_provider_native_upgrade_rows")
    warnings.extend(latest_failures)
    return NewsCatalystProviderUpgradeStatus(
        status=status_value,
        active_equity_count=report.active_equity_count,
        provider_native_ticker_count=len(provider_native_tickers),
        text_derived_only_ticker_count=len(text_derived_only_tickers),
        provider_native_tickers=provider_native_tickers,
        text_derived_only_tickers=text_derived_only_tickers,
        current_queue_tickers=plan.planned_tickers,
        available_providers=available_providers,
        unavailable_providers=unavailable_providers,
        missing_key_providers=missing_key_providers,
        latest_provider_failures=latest_failures,
        provider_blockers=provider_blockers,
        latest_provider_native_source_date=report.latest_provider_native_source_date,
        provider_native_rejected_row_count=(
            report.provider_native_rejected_row_count
        ),
        provider_native_rejected_tickers=(
            report.provider_native_rejected_tickers
        ),
        provider_native_rejected_warnings=(
            report.provider_native_rejected_warnings
        ),
        provider_statuses=provider_statuses,
        warnings=tuple(dict.fromkeys(warnings)),
    )


def build_news_catalyst_provider_upgrade_status_text(
    config: AppConfig,
    max_tickers: int | None = None,
) -> str:
    upgrade = news_catalyst_provider_upgrade_status(config, max_tickers=max_tickers)
    lines = [
        "News/Catalyst Provider Upgrade Status",
        f"Status: {upgrade.status}",
        (
            "Provider-native coverage: "
            f"{upgrade.provider_native_ticker_count}/{upgrade.active_equity_count}"
        ),
        (
            "Provider-native upgraded tickers: "
            f"{', '.join(upgrade.provider_native_tickers) or 'none'}"
        ),
        (
            "Still text-derived-only tickers: "
            f"{', '.join(upgrade.text_derived_only_tickers) or 'none'}"
        ),
        (
            "Latest accepted provider-native source date: "
            f"{upgrade.latest_provider_native_source_date or 'none'}"
        ),
        (
            "Rejected provider-native rows: "
            f"{upgrade.provider_native_rejected_row_count}"
        ),
        (
            "Rejected provider-native tickers: "
            f"{', '.join(upgrade.provider_native_rejected_tickers) or 'none'}"
        ),
        (
            "Current upgrade queue tickers: "
            f"{', '.join(upgrade.current_queue_tickers) or 'none'}"
        ),
        (
            "Available providers: "
            f"{', '.join(upgrade.available_providers) or 'none'}"
        ),
        (
            "Unavailable providers: "
            f"{', '.join(upgrade.unavailable_providers) or 'none'}"
        ),
        (
            "Missing-key providers: "
            f"{', '.join(upgrade.missing_key_providers) or 'none'}"
        ),
        (
            "Latest provider failures: "
            f"{', '.join(upgrade.latest_provider_failures) or 'none'}"
        ),
        (
            "Provider blockers: "
            f"{', '.join(upgrade.provider_blockers) or 'none'}"
        ),
        (
            "Provider-native rejection warnings: "
            f"{', '.join(upgrade.provider_native_rejected_warnings) or 'none'}"
        ),
        (
            "Preview command: "
            "python -m target_opportunity_monitor preview-news-catalyst-provider-upgrade"
        ),
        f"Warnings: {', '.join(upgrade.warnings) if upgrade.warnings else 'none'}",
        "",
        "Provider | Enabled | Available | Key/Source Status | Latest Warning | Numeric Snapshots | Details",
    ]
    for provider in upgrade.provider_statuses:
        key_status = "available" if provider.available else "missing_or_unavailable"
        lines.append(
            " | ".join(
                (
                    provider.provider,
                    str(provider.enabled),
                    str(provider.available),
                    key_status,
                    provider.latest_warning or "",
                    str(provider.numeric_snapshot_count),
                    provider.details,
                )
            )
        )
    return "\n".join(lines)


def build_news_catalyst_provider_backfill_validation_text(
    config: AppConfig,
    directory: Path | None = None,
) -> str:
    result = validate_news_catalyst_provider_backfill(config, directory=directory)
    lines = [
        "News/Catalyst Provider Backfill Validation",
        f"Source directory: {result.source_dir}",
        f"CSV files: {len(result.source_files)}",
        f"Total filled or placeholder rows: {result.total_row_count}",
        f"Valid provider-native rows: {result.valid_row_count}",
        f"Blank placeholders: {result.blank_placeholder_count}",
        f"Invalid rows: {result.invalid_row_count}",
        f"Unsupported ticker rows: {result.unsupported_ticker_count}",
        f"ETF-gated rows: {result.etf_gated_count}",
        f"Valid tickers: {', '.join(result.valid_tickers) or 'none'}",
        (
            "Blank placeholder tickers: "
            f"{', '.join(result.blank_placeholder_tickers) or 'none'}"
        ),
        f"Invalid tickers: {', '.join(result.invalid_tickers) or 'none'}",
        f"Unsupported tickers: {', '.join(result.unsupported_tickers) or 'none'}",
        f"ETF-gated tickers: {', '.join(result.etf_gated_tickers) or 'none'}",
        f"Warnings: {', '.join(result.warnings) if result.warnings else 'none'}",
    ]
    if result.source_files:
        lines.extend(["", "Files:"])
        lines.extend(str(path) for path in result.source_files)
    return "\n".join(lines)


def build_news_catalyst_provider_backfill_diagnostics_text(
    config: AppConfig,
    directory: Path | None = None,
) -> str:
    diagnostics = news_catalyst_provider_backfill_diagnostics(config, directory=directory)
    lines = [
        "News/Catalyst Provider-Native Backfill Diagnostics",
        (
            "Accepted source labels: "
            f"{', '.join(sorted(PROVIDER_NATIVE_EXPORT_SOURCES))}"
        ),
        "Ticker | Classification | Current Native | Text-Derived Only | Valid Rows | Blank Rows | Invalid Rows | Recommended Action | Warnings",
    ]
    if not diagnostics:
        lines.append("none")
    for item in diagnostics:
        lines.append(
            " | ".join(
                (
                    item.ticker,
                    item.classification,
                    str(item.current_provider_native),
                    str(item.text_derived_only),
                    str(item.valid_rows),
                    str(item.blank_placeholder_rows),
                    str(item.invalid_rows),
                    item.recommended_action,
                    ", ".join(item.warnings) if item.warnings else "none",
                )
            )
        )
    return "\n".join(lines)


def build_news_catalyst_provider_upgrade_preview_text(
    config: AppConfig,
    directory: Path | None = None,
) -> str:
    preview = preview_news_catalyst_provider_upgrade(config, directory=directory)
    validation = preview.validation
    lines = [
        "News/Catalyst Provider Upgrade Preview",
        (
            "Current provider-native coverage: "
            f"{preview.current_provider_native_ticker_count}/{preview.active_equity_count}"
        ),
        (
            "Current provider-native tickers: "
            f"{', '.join(preview.current_provider_native_tickers) or 'none'}"
        ),
        (
            "Text-derived-only tickers: "
            f"{', '.join(preview.text_derived_only_tickers) or 'none'}"
        ),
        f"Valid backfill rows ready to import: {validation.valid_row_count}",
        f"Valid backfill tickers: {', '.join(preview.valid_backfill_tickers) or 'none'}",
        (
            "Projected provider-native coverage after import: "
            f"{preview.projected_provider_native_ticker_count}/{preview.active_equity_count}"
        ),
        (
            "Projected provider-native tickers: "
            f"{', '.join(preview.projected_provider_native_tickers) or 'none'}"
        ),
        (
            "Still blocked tickers: "
            f"{', '.join(preview.still_blocked_tickers) or 'none'}"
        ),
        f"Blank placeholders: {validation.blank_placeholder_count}",
        f"Invalid rows: {validation.invalid_row_count}",
        f"Unsupported tickers: {', '.join(validation.unsupported_tickers) or 'none'}",
        f"ETF-gated tickers: {', '.join(validation.etf_gated_tickers) or 'none'}",
        f"Warnings: {', '.join(preview.warnings) if preview.warnings else 'none'}",
        "",
        "Next commands when the preview is clean:",
    ]
    lines.extend(preview.next_commands)
    return "\n".join(lines)


def build_news_catalyst_provider_backfill_status_text(
    config: AppConfig,
    allow_partial: bool = False,
    directory: Path | None = None,
) -> str:
    status = news_catalyst_provider_backfill_apply_status(
        config,
        allow_partial=allow_partial,
        directory=directory,
    )
    preview = status.preview
    validation = preview.validation
    lines = [
        "News/Catalyst Provider Backfill Status",
        (
            "Current provider-native coverage: "
            f"{preview.current_provider_native_ticker_count}/{preview.active_equity_count}"
        ),
        (
            "Projected provider-native coverage: "
            f"{preview.projected_provider_native_ticker_count}/{preview.active_equity_count}"
        ),
        f"Projected upgrade delta: {status.projected_upgrade_delta}",
        f"Backfill apply ready: {status.backfill_apply_ready}",
        f"Allow partial: {status.allow_partial}",
        f"Blocked apply reason: {status.blocked_apply_reason or 'none'}",
        f"Valid rows: {validation.valid_row_count}",
        f"Blank placeholders: {validation.blank_placeholder_count}",
        f"Invalid rows: {validation.invalid_row_count}",
        (
            "Valid upgrade tickers: "
            f"{', '.join(status.valid_upgrade_tickers) or 'none'}"
        ),
        (
            "Still blocked tickers: "
            f"{', '.join(preview.still_blocked_tickers) or 'none'}"
        ),
        (
            "Source directory: "
            f"{validation.source_dir}"
        ),
        f"Warnings: {', '.join(status.warnings) if status.warnings else 'none'}",
        "",
        "Apply behavior:",
        "- Without --confirm, apply-news-catalyst-provider-backfill is dry-run only.",
        "- With --confirm, invalid rows, zero valid rows, and non-improving coverage block apply.",
        "- Add --allow-partial to accept fewer than all remaining provider-native upgrades.",
    ]
    return "\n".join(lines)


def build_news_catalyst_provider_backfill_apply_text(
    result: NewsCatalystProviderBackfillApplyResult,
) -> str:
    lines = [
        "News/Catalyst Provider Backfill Apply",
        f"Confirmed: {result.confirmed}",
        f"Applied: {result.applied}",
        f"Dry run: {not result.confirmed}",
        f"Backfill apply ready: {result.status.backfill_apply_ready}",
        f"Blocked apply reason: {result.status.blocked_apply_reason or 'none'}",
        f"Projected upgrade delta: {result.status.projected_upgrade_delta}",
        (
            "Valid upgrade tickers: "
            f"{', '.join(result.status.valid_upgrade_tickers) or 'none'}"
        ),
        f"Imported rows: {result.imported_count}",
        f"Aggregates recomputed: {result.aggregate_count}",
        f"Final CSV rows loaded: {result.loaded_row_count}",
        f"Signals computed: {result.computed_count}",
        f"Validations updated: {result.validation_updated_count}",
        f"Warnings: {', '.join(result.warnings) if result.warnings else 'none'}",
    ]
    if not result.confirmed:
        lines.append(
            "Next: rerun with --confirm once the preview is clean and coverage improves."
        )
    return "\n".join(lines)


def news_catalyst_coverage_plan(
    config: AppConfig,
    max_tickers: int | None = None,
    write_template: bool = True,
    mode: str = "all",
) -> NewsCatalystCoveragePlan:
    coverage_mode = _normalize_coverage_plan_mode(mode)
    report = news_catalyst_source_status_report(config)
    limit = _live_request_budget(config, max_tickers)
    provider_warnings = _provider_warning_summary(report.provider_statuses)
    status_by_ticker = {status.ticker: status for status in report.statuses}
    items: list[NewsCatalystCoveragePlanItem] = []

    def include_item(kind: str) -> bool:
        return coverage_mode == "all" or coverage_mode == kind

    missing_reasons: dict[str, str] = {}
    provider_upgrade_reasons: dict[str, str] = {}

    if include_item("missing"):
        missing_candidates = report.missing_numeric_tickers or report.missing_source_tickers
    else:
        missing_candidates = ()
    for ticker in missing_candidates:
        status = status_by_ticker.get(ticker)
        item = NewsCatalystCoveragePlanItem(
            ticker=ticker,
            asset_type=status.asset_type if status else "equity",
            coverage_status="missing_numeric",
            priority=1,
            reason="missing_numeric_news_catalyst_row",
            stale=False,
            source_count=status.source_count if status else 0,
            aggregate_confidence=status.aggregate_confidence if status else None,
            provider_warnings=provider_warnings,
        )
        items.append(item)
        missing_reasons[ticker] = item.reason

    if include_item("provider-upgrade"):
        for ticker in report.provider_native_upgrade_tickers:
            status = status_by_ticker.get(ticker)
            item = NewsCatalystCoveragePlanItem(
                ticker=ticker,
                asset_type=status.asset_type if status else "equity",
                coverage_status="provider_upgrade",
                priority=2,
                reason="provider_native_news_catalyst_upgrade_needed",
                stale=status.stale if status else False,
                source_count=status.source_count if status else 0,
                aggregate_confidence=status.aggregate_confidence if status else None,
                provider_warnings=provider_warnings,
            )
            items.append(item)
            provider_upgrade_reasons[ticker] = item.reason

    stale_candidates = report.stale_tickers if coverage_mode == "all" else ()
    for ticker in stale_candidates:
        if ticker in report.missing_source_tickers:
            continue
        if ticker in report.provider_native_upgrade_tickers:
            continue
        status = status_by_ticker.get(ticker)
        item = NewsCatalystCoveragePlanItem(
            ticker=ticker,
            asset_type=status.asset_type if status else "equity",
            coverage_status="stale",
            priority=3,
            reason="stale_news_catalyst_source_row",
            stale=True,
            source_count=status.source_count if status else 0,
            aggregate_confidence=status.aggregate_confidence if status else None,
            provider_warnings=provider_warnings,
        )
        items.append(item)
        missing_reasons[ticker] = item.reason

    ordered_items = tuple(sorted(items, key=lambda item: (item.priority, item.ticker)))
    planned_items = ordered_items[:limit] if limit else ()
    planned_tickers = tuple(item.ticker for item in planned_items)
    missing_template_path = news_catalyst_coverage_queue_path(config, mode="missing")
    provider_upgrade_template_path = news_catalyst_coverage_queue_path(
        config, mode="provider-upgrade"
    )
    missing_planned_tickers = tuple(
        item.ticker
        for item in planned_items
        if item.coverage_status in {"missing_numeric", "stale"}
    )
    provider_upgrade_planned_tickers = tuple(
        item.ticker for item in planned_items if item.coverage_status == "provider_upgrade"
    )
    missing_template_tickers = _coverage_queue_tickers(missing_template_path)
    provider_upgrade_template_tickers = _coverage_queue_tickers(
        provider_upgrade_template_path
    )
    missing_gap_complete = (
        not report.missing_numeric_tickers and not report.missing_source_tickers
    )
    if missing_gap_complete:
        missing_template_tickers = ()
    missing_queue_template_stale = bool(
        missing_template_tickers
        and missing_template_tickers != tuple(sorted(missing_planned_tickers))
    )
    provider_upgrade_queue_template_stale = bool(
        provider_upgrade_template_tickers
        and provider_upgrade_template_tickers
        != tuple(sorted(provider_upgrade_planned_tickers))
    )
    if write_template:
        if missing_gap_complete and coverage_mode in {"provider-upgrade", "all"}:
            write_news_catalyst_coverage_template(
                config,
                (),
                missing_reasons,
                mode="missing",
            )
            missing_template_tickers = ()
            missing_queue_template_stale = False
        if coverage_mode in {"missing", "all"}:
            write_news_catalyst_coverage_template(
                config,
                tuple(sorted(missing_planned_tickers)),
                missing_reasons,
                mode="missing",
            )
            missing_template_tickers = tuple(sorted(missing_planned_tickers))
            missing_queue_template_stale = False
        if coverage_mode in {"provider-upgrade", "all"}:
            write_news_catalyst_coverage_template(
                config,
                tuple(sorted(provider_upgrade_planned_tickers)),
                provider_upgrade_reasons,
                mode="provider-upgrade",
            )
            provider_upgrade_template_tickers = tuple(
                sorted(provider_upgrade_planned_tickers)
            )
            provider_upgrade_queue_template_stale = False
    if coverage_mode == "provider-upgrade":
        template_path = provider_upgrade_template_path
        queue_template_tickers = provider_upgrade_template_tickers
        queue_template_stale = provider_upgrade_queue_template_stale
    elif coverage_mode == "missing":
        template_path = missing_template_path
        queue_template_tickers = missing_template_tickers
        queue_template_stale = missing_queue_template_stale
    else:
        template_path = (
            provider_upgrade_template_path
            if provider_upgrade_planned_tickers and not missing_planned_tickers
            else missing_template_path
        )
        queue_template_tickers = tuple(
            sorted(set(missing_template_tickers) | set(provider_upgrade_template_tickers))
        )
        queue_template_stale = (
            missing_queue_template_stale or provider_upgrade_queue_template_stale
        )

    warnings: list[str] = []
    if not planned_tickers:
        warnings.append("no_news_catalyst_coverage_gap")
    if missing_queue_template_stale:
        warnings.append("stale_news_catalyst_missing_queue_template")
    if provider_upgrade_queue_template_stale:
        warnings.append("stale_news_catalyst_provider_upgrade_queue_template")
    warnings.extend(provider_warnings)
    return NewsCatalystCoveragePlan(
        generated_at=datetime.now().isoformat(timespec="seconds"),
        mode=coverage_mode,
        max_tickers=limit,
        template_path=template_path,
        missing_template_path=missing_template_path,
        provider_upgrade_template_path=provider_upgrade_template_path,
        planned_tickers=planned_tickers,
        missing_tickers=tuple(report.missing_source_tickers),
        missing_numeric_tickers=tuple(report.missing_numeric_tickers),
        provider_native_upgrade_tickers=tuple(report.provider_native_upgrade_tickers),
        stale_tickers=tuple(report.stale_tickers),
        source_backed_tickers=tuple(report.source_backed_tickers),
        provider_warning_summary=provider_warnings,
        queue_template_tickers=queue_template_tickers,
        queue_template_stale=queue_template_stale,
        missing_queue_template_tickers=missing_template_tickers,
        missing_queue_template_stale=missing_queue_template_stale,
        provider_upgrade_queue_template_tickers=provider_upgrade_template_tickers,
        provider_upgrade_queue_template_stale=provider_upgrade_queue_template_stale,
        items=planned_items,
        warnings=tuple(dict.fromkeys(warnings)),
    )


def build_news_catalyst_coverage_plan_text(
    config: AppConfig,
    max_tickers: int | None = None,
    mode: str = "all",
) -> str:
    plan = news_catalyst_coverage_plan(config, max_tickers=max_tickers, mode=mode)
    lines = [
        "News/Catalyst Coverage Plan",
        f"Generated at: {plan.generated_at}",
        f"Mode: {plan.mode}",
        f"Max tickers this run: {plan.max_tickers}",
        f"Coverage queue template: {plan.template_path}",
        f"Missing queue template: {plan.missing_template_path}",
        f"Provider upgrade queue template: {plan.provider_upgrade_template_path}",
        f"Coverage queue stale: {plan.queue_template_stale}",
        f"Missing queue stale: {plan.missing_queue_template_stale}",
        f"Provider upgrade queue stale: {plan.provider_upgrade_queue_template_stale}",
        f"Coverage queue tickers: {', '.join(plan.queue_template_tickers) if plan.queue_template_tickers else 'none'}",
        f"Missing queue tickers: {', '.join(plan.missing_queue_template_tickers) if plan.missing_queue_template_tickers else 'none'}",
        f"Provider upgrade queue tickers: {', '.join(plan.provider_upgrade_queue_template_tickers) if plan.provider_upgrade_queue_template_tickers else 'none'}",
        f"Planned tickers: {', '.join(plan.planned_tickers) if plan.planned_tickers else 'none'}",
        f"Missing tickers: {', '.join(plan.missing_tickers) if plan.missing_tickers else 'none'}",
        f"Missing numeric tickers: {', '.join(plan.missing_numeric_tickers) if plan.missing_numeric_tickers else 'none'}",
        f"Provider-native upgrade tickers: {', '.join(plan.provider_native_upgrade_tickers) if plan.provider_native_upgrade_tickers else 'none'}",
        f"Stale tickers: {', '.join(plan.stale_tickers) if plan.stale_tickers else 'none'}",
        (
            "Provider warnings: "
            f"{', '.join(plan.provider_warning_summary) if plan.provider_warning_summary else 'none'}"
        ),
        f"Warnings: {', '.join(plan.warnings) if plan.warnings else 'none'}",
        "",
        "Ticker | Type | Priority | Coverage Status | Reason | Source Count | Confidence | Provider Warnings",
    ]
    for item in plan.items:
        lines.append(
            " | ".join(
                (
                    item.ticker,
                    item.asset_type,
                    str(item.priority),
                    item.coverage_status,
                    item.reason,
                    str(item.source_count),
                    f"{item.aggregate_confidence:.2f}"
                    if item.aggregate_confidence is not None
                    else "",
                    ", ".join(item.provider_warnings),
                )
            )
        )
    return "\n".join(lines)


def build_news_catalyst_source_status_text(
    config: AppConfig,
    missing_only: bool = False,
    provider_warnings_only: bool = False,
    provider_upgrade_only: bool = False,
) -> str:
    report = news_catalyst_source_status_report(config)
    provider_warning_summary = _provider_warning_summary(report.provider_statuses)
    if provider_warnings_only:
        lines = [
            "News/Catalyst Provider Warnings",
            (
                "Provider warnings: "
                f"{', '.join(provider_warning_summary) if provider_warning_summary else 'none'}"
            ),
            "",
            (
                "Provider | Enabled | Available | Status | Numeric Snapshots | "
                "Headline-Only Snapshots | Latest Warning | Details"
            ),
        ]
        for status in report.provider_statuses:
            has_warning = bool(status.latest_warning)
            headline_only = bool(status.headline_only_snapshot_count and not status.numeric_snapshot_count)
            if not has_warning and not headline_only:
                continue
            lines.append(
                " | ".join(
                    (
                        status.provider,
                        str(status.enabled),
                        str(status.available),
                        status.status,
                        str(status.numeric_snapshot_count),
                        str(status.headline_only_snapshot_count),
                        status.latest_warning or "",
                        status.details,
                    )
                )
            )
        return "\n".join(lines)

    lines = [
        "News/Catalyst Source Status",
        "",
        f"Source export directory: {report.source_exports_dir}",
        f"Cache directory: {report.cache_dir}",
        f"Cache files: {report.cache_file_count}",
        f"Latest cache timestamp: {report.latest_cache_at or 'none'}",
        f"Source snapshot rows: {report.source_snapshot_count}",
        f"Numeric source snapshot rows: {report.numeric_snapshot_count}",
        f"Provider numeric source snapshot rows: {report.provider_numeric_snapshot_count}",
        f"Text-derived numeric source snapshot rows: {report.text_derived_snapshot_count}",
        (
            "Numeric ticker coverage: "
            f"{report.total_numeric_ticker_count}/{report.active_equity_count}"
        ),
        (
            "Provider numeric ticker coverage: "
            f"{report.provider_numeric_ticker_count}/{report.active_equity_count}"
        ),
        (
            "Text-derived numeric ticker coverage: "
            f"{report.text_derived_ticker_count}/{report.active_equity_count}"
        ),
        (
            "Provider-native upgrade needed: "
            f"{len(report.provider_native_upgrade_tickers)}/{report.active_equity_count}"
        ),
        (
            "Provider-native upgrade tickers: "
            f"{', '.join(report.provider_native_upgrade_tickers) or 'none'}"
        ),
        (
            "Latest accepted provider-native source date: "
            f"{report.latest_provider_native_source_date or 'none'}"
        ),
        (
            "Rejected provider-native rows: "
            f"{report.provider_native_rejected_row_count}"
        ),
        (
            "Rejected provider-native tickers: "
            f"{', '.join(report.provider_native_rejected_tickers) or 'none'}"
        ),
        f"Headline-only source snapshot rows: {report.headline_only_snapshot_count}",
        f"Aggregate rows: {report.aggregate_count}",
        f"Derived news/catalysts: {report.news_catalysts_path}",
        f"Derived news/catalysts exists: {report.news_catalysts_exists}",
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
        f"Warnings: {', '.join(report.warnings) if report.warnings else 'none'}",
        (
            "Provider warnings: "
            f"{', '.join(provider_warning_summary) if provider_warning_summary else 'none'}"
        ),
        (
            "Provider-native rejection warnings: "
            f"{', '.join(report.provider_native_rejected_warnings) if report.provider_native_rejected_warnings else 'none'}"
        ),
        "",
        (
            "Provider | Enabled | Available | Status | Cache Files | Latest Cache | "
            "Numeric Snapshots | Headline-Only Snapshots | Latest Warning | Details"
        ),
    ]
    for status in report.provider_statuses:
        lines.append(
            " | ".join(
                (
                    status.provider,
                    str(status.enabled),
                    str(status.available),
                    status.status,
                    str(status.cache_file_count),
                    status.latest_cache_at or "",
                    str(status.numeric_snapshot_count),
                    str(status.headline_only_snapshot_count),
                    status.latest_warning or "",
                    status.details,
                )
            )
        )
    lines.extend(
        [
            "",
            (
                "Ticker | Type | Source Backed | Signal Date | Source | "
                "Provider Numeric | Text-Derived Numeric | Source Count | "
                "Confidence | Disagreement | Stale | Warnings"
            ),
        ]
    )
    statuses = (
        [status for status in report.statuses if status.provider_native_upgrade_needed]
        if provider_upgrade_only
        else (
            [status for status in report.statuses if not status.source_backed]
            if missing_only
            else list(report.statuses)
        )
    )
    for status in statuses:
        lines.append(
            " | ".join(
                (
                    status.ticker,
                    status.asset_type,
                    str(status.source_backed),
                    status.signal_date or "",
                    status.source or "",
                    str(status.has_provider_numeric),
                    str(status.has_text_derived_numeric),
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
