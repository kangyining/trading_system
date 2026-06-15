from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from .config import AppConfig
from .storage import (
    Asset,
    Signal,
    SignalOutcomeStatus,
    SignalStatus,
    insert_data_quality_check,
    is_scoreable_asset,
    list_assets,
    list_signals,
    signal_outcome_statuses,
    signal_statuses_for_family,
    normalize_ticker,
    upsert_signal,
)


NEWS_CATALYST_HEADERS = (
    "ticker",
    "signal_date",
    "source",
    "source_url",
    "headline_or_event",
    "event_date",
    "sentiment_score",
    "catalyst_score",
    "urgency_score",
    "confidence",
    "topic",
    "notes",
    "as_of_date",
    "effective_date",
)
REQUIRED_COLUMNS = {"ticker", "signal_date", "source", "source_url", "headline_or_event"}
NUMERIC_FIELDS = {"sentiment_score", "catalyst_score", "urgency_score", "confidence"}
INPUT_SIGNAL_NAMES = {
    "sentiment_score": "news_catalyst.input.sentiment",
    "catalyst_score": "news_catalyst.input.catalyst",
    "urgency_score": "news_catalyst.input.urgency",
    "confidence": "news_catalyst.input.confidence",
}
OUTPUT_SIGNAL_NAMES = {
    "news_catalyst.input.sentiment": "news_catalyst.sentiment",
    "news_catalyst.input.catalyst": "news_catalyst.catalyst",
    "news_catalyst.input.urgency": "news_catalyst.urgency",
}
SIGNAL_FAMILY_INPUT = "news_catalyst_input"
SIGNAL_FAMILY = "news_catalyst"
COMPOSITE_SIGNAL_NAME = "news_catalyst.composite"


@dataclass(frozen=True)
class NewsCatalystInput:
    ticker: str
    signal_date: str
    source: str
    source_url: str
    headline_or_event: str
    event_date: str | None = None
    sentiment_score: float | None = None
    catalyst_score: float | None = None
    urgency_score: float | None = None
    confidence: float | None = None
    topic: str | None = None
    notes: str | None = None
    as_of_date: str | None = None
    effective_date: str | None = None


@dataclass(frozen=True)
class NewsCatalystLoadResult:
    path: Path
    row_count: int
    input_signal_count: int
    tickers: tuple[str, ...]
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class NewsCatalystTickerResult:
    ticker: str
    status: str
    asset_type: str
    composite_score: float | None
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class NewsCatalystUpdateResult:
    results: tuple[NewsCatalystTickerResult, ...]
    load_result: NewsCatalystLoadResult

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
class NewsCatalystStatus:
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


def ensure_news_catalyst_csv_header(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text(",".join(NEWS_CATALYST_HEADERS) + "\n", encoding="utf-8")
        return

    text = path.read_text(encoding="utf-8-sig")
    if not text.strip():
        path.write_text(",".join(NEWS_CATALYST_HEADERS) + "\n", encoding="utf-8")
        return

    reader = csv.DictReader(text.splitlines())
    if not reader.fieldnames:
        path.write_text(",".join(NEWS_CATALYST_HEADERS) + "\n", encoding="utf-8")
        return
    if set(NEWS_CATALYST_HEADERS).issubset(reader.fieldnames):
        return

    rows = list(reader)
    with path.open("w", newline="", encoding="utf-8") as output:
        writer = csv.DictWriter(output, fieldnames=NEWS_CATALYST_HEADERS)
        writer.writeheader()
        for row in rows:
            writer.writerow({header: row.get(header, "") for header in NEWS_CATALYST_HEADERS})


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


def parse_news_catalysts_csv(text: str) -> list[NewsCatalystInput]:
    reader = csv.DictReader(text.splitlines())
    if not reader.fieldnames:
        raise ValueError("News/catalysts CSV missing header.")
    missing = REQUIRED_COLUMNS - set(reader.fieldnames)
    if missing:
        raise ValueError(
            "News/catalysts CSV missing required columns: " + ", ".join(sorted(missing))
        )

    rows: list[NewsCatalystInput] = []
    for row_number, row in enumerate(reader, start=2):
        if not any((value or "").strip() for value in row.values()):
            continue
        ticker = normalize_ticker(row.get("ticker", ""))
        if not ticker:
            raise ValueError(f"Row {row_number}: missing required ticker.")
        source = (row.get("source") or "").strip()
        if not source:
            raise ValueError(f"Row {row_number}: missing required source.")
        source_url = (row.get("source_url") or "").strip()
        if not source_url:
            raise ValueError(f"Row {row_number}: missing required source_url.")
        headline = (row.get("headline_or_event") or "").strip()
        if not headline:
            raise ValueError(f"Row {row_number}: missing required headline_or_event.")
        signal_date = _parse_date(row.get("signal_date", ""), "signal_date", row_number)
        numeric = {
            field: _parse_score(row.get(field), field, row_number)
            for field in NUMERIC_FIELDS
        }
        rows.append(
            NewsCatalystInput(
                ticker=ticker,
                signal_date=signal_date,
                source=source,
                source_url=source_url,
                headline_or_event=headline,
                event_date=_parse_optional_date(row.get("event_date"), "event_date", row_number),
                topic=(row.get("topic") or "").strip() or None,
                notes=(row.get("notes") or "").strip() or None,
                as_of_date=_parse_optional_date(row.get("as_of_date"), "as_of_date", row_number)
                or date.today().isoformat(),
                effective_date=_parse_optional_date(
                    row.get("effective_date"), "effective_date", row_number
                )
                or signal_date,
                **numeric,
            )
        )
    return rows


def _direction_from_score(score: float | None) -> str:
    if score is None:
        return "neutral"
    if score >= 60:
        return "positive"
    if score <= 40:
        return "negative"
    return "neutral"


def _clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, value))


def _average(values: list[float]) -> float:
    return sum(values) / len(values) if values else 50.0


def _row_notes(row: NewsCatalystInput) -> str:
    parts = [row.headline_or_event]
    if row.topic:
        parts.append(f"topic={row.topic}")
    if row.event_date:
        parts.append(f"event_date={row.event_date}")
    if row.notes:
        parts.append(row.notes)
    return " | ".join(parts)


def _input_signals_from_row(row: NewsCatalystInput, asset_type: str) -> list[Signal]:
    values = {
        "sentiment_score": row.sentiment_score,
        "catalyst_score": row.catalyst_score,
        "urgency_score": row.urgency_score,
        "confidence": row.confidence,
    }
    warnings = "etf_news_catalyst_gated" if asset_type == "etf" else None
    signals: list[Signal] = []
    for field_name, value in values.items():
        if value is None:
            continue
        signals.append(
            Signal(
                ticker=row.ticker,
                signal_date=row.signal_date,
                signal_name=INPUT_SIGNAL_NAMES[field_name],
                signal_family=SIGNAL_FAMILY_INPUT,
                value=value,
                score=value,
                direction=_direction_from_score(value),
                reason_code="manual_news_catalyst_input",
                source=row.source,
                model_version=None,
                confidence=row.confidence,
                data_warnings=warnings,
                source_url=row.source_url,
                notes=_row_notes(row),
                as_of_date=row.as_of_date,
                effective_date=row.effective_date,
            )
        )
    return signals


def _asset_map(config: AppConfig) -> dict[str, Asset]:
    return {asset.ticker: asset for asset in list_assets(config.database_path) if is_scoreable_asset(asset)}


def load_news_catalysts_csv(
    config: AppConfig,
    path: Path | None = None,
) -> NewsCatalystLoadResult:
    news_path = path or config.news_catalysts_path
    ensure_news_catalyst_csv_header(news_path)
    rows = parse_news_catalysts_csv(news_path.read_text(encoding="utf-8-sig"))
    assets = _asset_map(config)
    input_signal_count = 0
    warnings: list[str] = []
    for row in rows:
        asset = assets.get(row.ticker)
        if asset is None:
            warnings.append(f"{row.ticker}:inactive_or_unknown_ticker")
            continue
        asset_type = (asset.asset_type or "equity").lower()
        raw_signals = _input_signals_from_row(row, asset_type)
        input_signal_count += len(raw_signals)
        for signal in raw_signals:
            upsert_signal(config.database_path, signal)
    if not rows:
        warnings.append("empty_news_catalysts")
    return NewsCatalystLoadResult(
        path=news_path,
        row_count=len(rows),
        input_signal_count=input_signal_count,
        tickers=tuple(sorted({row.ticker for row in rows})),
        warnings=tuple(dict.fromkeys(warnings)),
    )


def _latest_raw_inputs(config: AppConfig, ticker: str) -> tuple[str | None, dict[str, Signal]]:
    raw = list_signals(config.database_path, ticker=ticker, signal_family=SIGNAL_FAMILY_INPUT)
    if not raw:
        return None, {}
    latest_date = max(signal.signal_date for signal in raw)
    return latest_date, {signal.signal_name: signal for signal in raw if signal.signal_date == latest_date}


def _is_stale(signal_date: str, stale_after_days: int) -> bool:
    try:
        parsed = date.fromisoformat(signal_date)
    except ValueError:
        return True
    return (date.today() - parsed).days > stale_after_days


def _record_signal_quality(config: AppConfig, ticker: str, warnings: tuple[str, ...]) -> None:
    insert_data_quality_check(
        config.database_path,
        check_name=f"news_catalyst_signals:{ticker}",
        status="warning" if warnings else "ok",
        details=", ".join(warnings) if warnings else "news_catalyst_signals_computed",
        source="news_catalyst_signals",
        as_of_date=date.today().isoformat(),
    )


def _compute_ticker_news_catalyst_signals(
    config: AppConfig,
    asset: Asset,
) -> NewsCatalystTickerResult:
    ticker = asset.ticker
    asset_type = (asset.asset_type or "equity").lower()
    if asset_type == "etf":
        warnings = ("etf_news_catalyst_gated",)
        _record_signal_quality(config, ticker, warnings)
        return NewsCatalystTickerResult(ticker, "skipped", "etf", None, warnings)

    latest_date, raw_inputs = _latest_raw_inputs(config, ticker)
    if latest_date is None:
        warnings = ("missing_news_catalyst_signal",)
        _record_signal_quality(config, ticker, warnings)
        return NewsCatalystTickerResult(ticker, "skipped", "equity", None, warnings)

    component_scores: list[float] = []
    output_signals: list[Signal] = []
    source_url = next((signal.source_url for signal in raw_inputs.values() if signal.source_url), None)
    notes = next((signal.notes for signal in raw_inputs.values() if signal.notes), None)
    for input_name, output_name in OUTPUT_SIGNAL_NAMES.items():
        raw = raw_inputs.get(input_name)
        if raw is None or raw.score is None:
            continue
        component_scores.append(raw.score)
        output_signals.append(
            Signal(
                ticker=ticker,
                signal_date=latest_date,
                signal_name=output_name,
                signal_family=SIGNAL_FAMILY,
                value=raw.value,
                score=raw.score,
                direction=_direction_from_score(raw.score),
                reason_code=output_name.replace("news_catalyst.", ""),
                source="news_catalyst",
                model_version=config.signals_news_catalyst_model_version,
                source_url=source_url,
                notes=notes,
                as_of_date=date.today().isoformat(),
                effective_date=latest_date,
            )
        )

    warnings_list: list[str] = []
    if config.signals_news_catalyst_shadow_mode:
        warnings_list.append("news_catalyst_shadow_mode")
    if _is_stale(latest_date, config.signals_news_catalyst_stale_after_days):
        warnings_list.append("stale_news_catalyst_signal")
    if not component_scores:
        warnings = tuple(dict.fromkeys(warnings_list + ["missing_news_catalyst_scores"]))
        _record_signal_quality(config, ticker, warnings)
        return NewsCatalystTickerResult(ticker, "skipped", "equity", None, warnings)

    raw_confidence = raw_inputs.get("news_catalyst.input.confidence")
    confidence = raw_confidence.value if raw_confidence and raw_confidence.value is not None else None
    if confidence is None:
        confidence = 50.0 + len(component_scores) * 10.0
    if "stale_news_catalyst_signal" in warnings_list:
        confidence -= 15.0
    confidence = _clamp(confidence)
    if confidence < 50:
        warnings_list.append("low_confidence_news_catalyst")

    composite_score = _average(component_scores)
    warnings = tuple(dict.fromkeys(warnings_list))
    for signal in output_signals:
        upsert_signal(
            config.database_path,
            Signal(
                **{
                    **signal.__dict__,
                    "confidence": confidence,
                    "data_warnings": ", ".join(warnings) if warnings else None,
                }
            ),
        )

    upsert_signal(
        config.database_path,
        Signal(
            ticker=ticker,
            signal_date=latest_date,
            signal_name=COMPOSITE_SIGNAL_NAME,
            signal_family=SIGNAL_FAMILY,
            value=composite_score,
            score=composite_score,
            direction=_direction_from_score(composite_score),
            reason_code="news_catalyst_composite",
            source="news_catalyst",
            model_version=config.signals_news_catalyst_model_version,
            confidence=confidence,
            data_warnings=", ".join(warnings) if warnings else None,
            source_url=source_url,
            notes=notes,
            as_of_date=date.today().isoformat(),
            effective_date=latest_date,
        )
    )
    _record_signal_quality(config, ticker, warnings)
    return NewsCatalystTickerResult(ticker, "computed", "equity", composite_score, warnings)


def compute_news_catalyst_signals(
    config: AppConfig,
    ticker: str | None = None,
) -> NewsCatalystUpdateResult:
    load_result = load_news_catalysts_csv(config)
    wanted_ticker = normalize_ticker(ticker) if ticker else None
    assets = [
        asset
        for asset in list_assets(config.database_path)
        if is_scoreable_asset(asset) and (wanted_ticker is None or asset.ticker == wanted_ticker)
    ]
    results = [_compute_ticker_news_catalyst_signals(config, asset) for asset in assets]
    return NewsCatalystUpdateResult(results=tuple(results), load_result=load_result)


def news_catalyst_statuses(config: AppConfig) -> list[NewsCatalystStatus]:
    signal_status = {
        status.ticker: status
        for status in signal_statuses_for_family(
            config.database_path,
            signal_family=SIGNAL_FAMILY,
            composite_signal_name=COMPOSITE_SIGNAL_NAME,
            quality_check_prefix="news_catalyst_signals",
        )
    }
    validation_status = {
        status.ticker: status
        for status in signal_outcome_statuses(
            config.database_path,
            signal_family=SIGNAL_FAMILY,
            signal_name=COMPOSITE_SIGNAL_NAME,
        )
    }
    rows: list[NewsCatalystStatus] = []
    for ticker, status in sorted(signal_status.items()):
        outcome = validation_status.get(ticker)
        rows.append(
            NewsCatalystStatus(
                ticker=ticker,
                asset_type=status.asset_type,
                latest_signal_date=status.latest_signal_date,
                composite_score=status.composite_score,
                composite_direction=status.composite_direction,
                signal_count=status.signal_count,
                confidence=status.confidence,
                model_version=status.model_version,
                data_warnings=status.data_warnings,
                validation_status=outcome.outcome_status if outcome else None,
                validation_date=outcome.outcome_date if outcome else None,
            )
        )
    return rows
