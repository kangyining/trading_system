from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from .config import AppConfig
from .storage import (
    Asset,
    Signal,
    insert_data_quality_check,
    is_scoreable_asset,
    list_analyst_revision_aggregates,
    list_assets,
    list_signals,
    normalize_ticker,
    upsert_signal,
)


ANALYST_REVISION_HEADERS = (
    "ticker",
    "signal_date",
    "eps_revision_1m",
    "eps_revision_3m",
    "revenue_revision_1m",
    "revenue_revision_3m",
    "target_price_revision_3m",
    "recommendation_revision",
    "estimate_dispersion",
    "analyst_count",
    "source",
    "source_url",
    "notes",
    "as_of_date",
    "effective_date",
)

REQUIRED_COLUMNS = {"ticker", "signal_date"}
NUMERIC_FIELDS = {
    "eps_revision_1m",
    "eps_revision_3m",
    "revenue_revision_1m",
    "revenue_revision_3m",
    "target_price_revision_3m",
    "recommendation_revision",
    "estimate_dispersion",
}

RAW_SIGNAL_NAMES = {
    "eps_revision_1m": "analyst_revision.input.eps_1m",
    "eps_revision_3m": "analyst_revision.input.eps_3m",
    "revenue_revision_1m": "analyst_revision.input.revenue_1m",
    "revenue_revision_3m": "analyst_revision.input.revenue_3m",
    "target_price_revision_3m": "analyst_revision.input.target_price_3m",
    "recommendation_revision": "analyst_revision.input.recommendation",
    "estimate_dispersion": "analyst_revision.input.estimate_dispersion",
    "analyst_count": "analyst_revision.input.analyst_count",
}

OUTPUT_SIGNAL_NAMES = {
    "analyst_revision.input.eps_1m": "analyst_revision.eps_1m",
    "analyst_revision.input.eps_3m": "analyst_revision.eps_3m",
    "analyst_revision.input.revenue_1m": "analyst_revision.revenue_1m",
    "analyst_revision.input.revenue_3m": "analyst_revision.revenue_3m",
    "analyst_revision.input.target_price_3m": "analyst_revision.target_price_3m",
    "analyst_revision.input.recommendation": "analyst_revision.recommendation",
    "analyst_revision.input.estimate_dispersion": "analyst_revision.estimate_dispersion",
}


@dataclass(frozen=True)
class AnalystRevisionInput:
    ticker: str
    signal_date: str
    eps_revision_1m: float | None = None
    eps_revision_3m: float | None = None
    revenue_revision_1m: float | None = None
    revenue_revision_3m: float | None = None
    target_price_revision_3m: float | None = None
    recommendation_revision: float | None = None
    estimate_dispersion: float | None = None
    analyst_count: int | None = None
    source: str = "manual_analyst_revision_csv"
    source_url: str | None = None
    notes: str | None = None
    as_of_date: str | None = None
    effective_date: str | None = None


@dataclass(frozen=True)
class AnalystRevisionLoadResult:
    path: Path
    row_count: int
    input_signal_count: int
    tickers: tuple[str, ...]
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class TickerSignalResult:
    ticker: str
    status: str
    asset_type: str
    composite_score: float | None
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class RevisionSignalUpdateResult:
    results: tuple[TickerSignalResult, ...]
    load_result: AnalystRevisionLoadResult

    @property
    def computed_count(self) -> int:
        return sum(1 for result in self.results if result.status == "computed")

    @property
    def skipped_count(self) -> int:
        return sum(1 for result in self.results if result.status == "skipped")

    @property
    def warning_count(self) -> int:
        return sum(1 for result in self.results if result.warnings)


def ensure_analyst_revision_csv_header(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text(",".join(ANALYST_REVISION_HEADERS) + "\n", encoding="utf-8")
        return

    text = path.read_text(encoding="utf-8-sig")
    if not text.strip():
        path.write_text(",".join(ANALYST_REVISION_HEADERS) + "\n", encoding="utf-8")
        return

    reader = csv.DictReader(text.splitlines())
    if not reader.fieldnames:
        path.write_text(",".join(ANALYST_REVISION_HEADERS) + "\n", encoding="utf-8")
        return
    if set(ANALYST_REVISION_HEADERS).issubset(reader.fieldnames):
        return

    rows = list(reader)
    with path.open("w", newline="", encoding="utf-8") as output:
        writer = csv.DictWriter(output, fieldnames=ANALYST_REVISION_HEADERS)
        writer.writeheader()
        for row in rows:
            writer.writerow({header: row.get(header, "") for header in ANALYST_REVISION_HEADERS})


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
        return int(text)
    except ValueError as error:
        raise ValueError(f"Row {row_number}: malformed {field_name}: {text}") from error


def parse_analyst_revisions_csv(text: str) -> list[AnalystRevisionInput]:
    reader = csv.DictReader(text.splitlines())
    if not reader.fieldnames:
        raise ValueError("Analyst revisions CSV missing header.")
    missing = REQUIRED_COLUMNS - set(reader.fieldnames)
    if missing:
        raise ValueError(
            "Analyst revisions CSV missing required columns: "
            + ", ".join(sorted(missing))
        )

    rows: list[AnalystRevisionInput] = []
    for row_number, row in enumerate(reader, start=2):
        if not any((value or "").strip() for value in row.values()):
            continue
        ticker = normalize_ticker(row.get("ticker", ""))
        if not ticker:
            raise ValueError(f"Row {row_number}: missing required ticker.")
        signal_date = _parse_date(row.get("signal_date", ""), "signal_date", row_number)
        payload = {
            field: _parse_float(row.get(field), field, row_number)
            for field in NUMERIC_FIELDS
        }
        rows.append(
            AnalystRevisionInput(
                ticker=ticker,
                signal_date=signal_date,
                analyst_count=_parse_int(row.get("analyst_count"), "analyst_count", row_number),
                source=(row.get("source") or "manual_analyst_revision_csv").strip()
                or "manual_analyst_revision_csv",
                source_url=(row.get("source_url") or "").strip() or None,
                notes=(row.get("notes") or "").strip() or None,
                as_of_date=_parse_optional_date(row.get("as_of_date"), "as_of_date", row_number)
                or date.today().isoformat(),
                effective_date=_parse_optional_date(
                    row.get("effective_date"), "effective_date", row_number
                )
                or signal_date,
                **payload,
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


def _direction_from_value(value: float | None) -> str:
    if value is None:
        return "neutral"
    if value > 0:
        return "positive"
    if value < 0:
        return "negative"
    return "neutral"


def _raw_signals_from_row(row: AnalystRevisionInput) -> list[Signal]:
    values = {
        "eps_revision_1m": row.eps_revision_1m,
        "eps_revision_3m": row.eps_revision_3m,
        "revenue_revision_1m": row.revenue_revision_1m,
        "revenue_revision_3m": row.revenue_revision_3m,
        "target_price_revision_3m": row.target_price_revision_3m,
        "recommendation_revision": row.recommendation_revision,
        "estimate_dispersion": row.estimate_dispersion,
        "analyst_count": float(row.analyst_count) if row.analyst_count is not None else None,
    }
    signals: list[Signal] = []
    for field_name, value in values.items():
        if value is None:
            continue
        signals.append(
            Signal(
                ticker=row.ticker,
                signal_date=row.signal_date,
                signal_name=RAW_SIGNAL_NAMES[field_name],
                signal_family="analyst_revision_input",
                value=value,
                score=None,
                direction=_direction_from_value(value),
                reason_code="manual_revision_input",
                source=row.source,
                source_url=row.source_url,
                notes=row.notes,
                as_of_date=row.as_of_date,
                effective_date=row.effective_date,
            )
        )
    return signals


def _aggregate_revision_inputs(config: AppConfig) -> list[AnalystRevisionInput]:
    rows = list_analyst_revision_aggregates(config.database_path)
    return [
        AnalystRevisionInput(
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
        for row in rows
    ]


def load_analyst_revisions_csv(
    config: AppConfig,
    path: Path | None = None,
) -> AnalystRevisionLoadResult:
    revision_path = path or config.analyst_revisions_path
    rows = _aggregate_revision_inputs(config) if path is None else []
    if not rows:
        ensure_analyst_revision_csv_header(revision_path)
        rows = parse_analyst_revisions_csv(revision_path.read_text(encoding="utf-8-sig"))
    input_signal_count = 0
    for row in rows:
        raw_signals = _raw_signals_from_row(row)
        input_signal_count += len(raw_signals)
        for signal in raw_signals:
            upsert_signal(config.database_path, signal)
    warnings = ("empty_analyst_revisions",) if not rows else ()
    return AnalystRevisionLoadResult(
        path=revision_path,
        row_count=len(rows),
        input_signal_count=input_signal_count,
        tickers=tuple(sorted({row.ticker for row in rows})),
        warnings=warnings,
    )


def _clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, value))


def _score_revision(value: float) -> float:
    return _clamp(50.0 + value * 400.0)


def _score_recommendation(value: float) -> float:
    return _clamp(50.0 + value * 25.0)


def _score_dispersion(value: float) -> float:
    return _clamp(100.0 - value * 200.0)


def _average(values: list[float]) -> float:
    return sum(values) / len(values) if values else 50.0


def _first_text(values: list[str | None]) -> str | None:
    for value in values:
        if value:
            return value
    return None


def _latest_raw_inputs(database_path: Path, ticker: str) -> tuple[str | None, dict[str, Signal]]:
    raw = list_signals(database_path, ticker=ticker, signal_family="analyst_revision_input")
    if not raw:
        return None, {}
    latest_date = max(signal.signal_date for signal in raw)
    latest: dict[str, Signal] = {}
    for signal in raw:
        if signal.signal_date == latest_date:
            latest[signal.signal_name] = signal
    return latest_date, latest


def _is_stale(signal_date: str, stale_after_days: int) -> bool:
    try:
        parsed = date.fromisoformat(signal_date)
    except ValueError:
        return True
    return (date.today() - parsed).days > stale_after_days


def _record_signal_quality(
    config: AppConfig,
    ticker: str,
    warnings: tuple[str, ...],
) -> None:
    insert_data_quality_check(
        config.database_path,
        check_name=f"signals:{ticker}",
        status="warning" if warnings else "ok",
        details=", ".join(warnings) if warnings else "revision_signals_computed",
        source="signals",
        as_of_date=date.today().isoformat(),
    )


def _asset_type(asset: Asset) -> str:
    return (asset.asset_type or "equity").strip().lower()


def _compute_ticker_revision_signals(
    config: AppConfig,
    asset: Asset,
) -> TickerSignalResult:
    ticker = asset.ticker
    if _asset_type(asset) == "etf":
        warnings = ("etf_revision_signal_gated",)
        _record_signal_quality(config, ticker, warnings)
        return TickerSignalResult(
            ticker=ticker,
            status="skipped",
            asset_type="etf",
            composite_score=None,
            warnings=warnings,
        )

    latest_date, raw_inputs = _latest_raw_inputs(config.database_path, ticker)
    if latest_date is None:
        warnings = ("missing_revision_signal",)
        _record_signal_quality(config, ticker, warnings)
        return TickerSignalResult(
            ticker=ticker,
            status="skipped",
            asset_type="equity",
            composite_score=None,
            warnings=warnings,
        )

    warnings_list: list[str] = []
    if _is_stale(latest_date, config.signals_stale_after_days):
        warnings_list.append("stale_revision_signal")
    if config.signals_analyst_revision_shadow_mode:
        warnings_list.append("revision_signal_shadow_mode")

    scored_signals: list[Signal] = []
    revision_scores: list[float] = []
    revision_values: list[float] = []
    dispersion: float | None = None
    analyst_count: int | None = None
    source_url = _first_text([raw.source_url for raw in raw_inputs.values()])
    notes = _first_text([raw.notes for raw in raw_inputs.values()])

    for input_name, output_name in OUTPUT_SIGNAL_NAMES.items():
        raw = raw_inputs.get(input_name)
        if raw is None or raw.value is None:
            continue
        if input_name.endswith("recommendation"):
            score = _score_recommendation(raw.value)
            revision_scores.append(score)
        elif input_name.endswith("estimate_dispersion"):
            dispersion = raw.value
            score = _score_dispersion(raw.value)
        else:
            score = _score_revision(raw.value)
            revision_scores.append(score)
            revision_values.append(raw.value)
        scored_signals.append(
            Signal(
                ticker=ticker,
                signal_date=latest_date,
                signal_name=output_name,
                signal_family="analyst_revision",
                value=raw.value,
                score=score,
                direction=_direction_from_score(score),
                reason_code=output_name.replace("analyst_revision.", ""),
                source="analyst_revision",
                model_version=config.signals_analyst_revision_model_version,
                source_url=source_url,
                notes=notes,
                as_of_date=date.today().isoformat(),
                effective_date=latest_date,
            )
        )

    raw_analyst_count = raw_inputs.get("analyst_revision.input.analyst_count")
    if raw_analyst_count and raw_analyst_count.value is not None:
        analyst_count = int(raw_analyst_count.value)

    if len(revision_scores) < config.signals_minimum_revision_inputs:
        warnings = tuple(dict.fromkeys(warnings_list + ["missing_revision_signal"]))
        _record_signal_quality(config, ticker, warnings)
        return TickerSignalResult(
            ticker=ticker,
            status="skipped",
            asset_type="equity",
            composite_score=None,
            warnings=warnings,
        )

    if dispersion is not None and dispersion >= 0.20:
        warnings_list.append("high_estimate_dispersion")

    confidence = 50.0 + min(len(revision_scores), 5) * 8.0
    if analyst_count is not None:
        confidence += min(max(analyst_count, 0), 20) * 1.0
    if dispersion is not None:
        confidence -= max(dispersion, 0.0) * 100.0
    if "stale_revision_signal" in warnings_list:
        confidence -= 15.0
    confidence = _clamp(confidence)
    composite_score = _average(revision_scores)
    composite_value = _average(revision_values) if revision_values else None
    warnings = tuple(dict.fromkeys(warnings_list))

    for signal in scored_signals:
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
            signal_name="analyst_revision.composite",
            signal_family="analyst_revision",
            value=composite_value,
            score=composite_score,
            direction=_direction_from_score(composite_score),
            reason_code="revision_composite",
            source="analyst_revision",
            model_version=config.signals_analyst_revision_model_version,
            confidence=confidence,
            data_warnings=", ".join(warnings) if warnings else None,
            source_url=source_url,
            notes=notes,
            as_of_date=date.today().isoformat(),
            effective_date=latest_date,
        )
    )
    _record_signal_quality(config, ticker, warnings)
    return TickerSignalResult(
        ticker=ticker,
        status="computed",
        asset_type="equity",
        composite_score=composite_score,
        warnings=warnings,
    )


def compute_revision_signals(
    config: AppConfig,
    ticker: str | None = None,
) -> RevisionSignalUpdateResult:
    load_result = load_analyst_revisions_csv(config)
    wanted_ticker = normalize_ticker(ticker) if ticker else None
    assets = [
        asset
        for asset in list_assets(config.database_path)
        if is_scoreable_asset(asset) and (wanted_ticker is None or asset.ticker == wanted_ticker)
    ]
    results = [_compute_ticker_revision_signals(config, asset) for asset in assets]
    return RevisionSignalUpdateResult(results=tuple(results), load_result=load_result)
