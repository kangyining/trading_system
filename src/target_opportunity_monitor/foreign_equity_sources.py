from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import date
from io import StringIO
from pathlib import Path

from .config import AppConfig
from .fundamental_data import (
    ESTIMATE_HEADERS,
    ESTIMATE_INTEGER_FIELDS,
    ESTIMATE_NUMERIC_FIELDS,
    FUNDAMENTAL_HEADERS,
    FUNDAMENTAL_NUMERIC_FIELDS,
    parse_estimates_csv,
    parse_fundamentals_csv,
)
from .research_tickers import (
    resolve_foreign_equity_research_metadata,
    research_ticker_status,
)
from .storage import (
    Estimate,
    Fundamental,
    is_scoreable_asset,
    latest_estimate,
    latest_price_feature,
    list_assets,
    list_fundamentals,
    normalize_ticker,
    upsert_estimate,
    upsert_fundamental,
)


FOREIGN_EQUITY_SOURCE_TICKERS = ("SIVE", "SOI")
FOREIGN_EQUITY_FUNDAMENTAL_HEADERS = (*FUNDAMENTAL_HEADERS, "source_url", "notes")
FOREIGN_EQUITY_ESTIMATE_HEADERS = (*ESTIMATE_HEADERS, "source_url", "notes")
FOREIGN_EQUITY_ANALYST_TARGET_HEADERS = (
    "ticker",
    "target_date",
    "currency",
    "target_mean",
    "target_low",
    "target_high",
    "analyst_count",
    "source",
    "source_url",
    "as_of_date",
    "effective_date",
    "notes",
)
DISALLOWED_SOURCE_LABELS = {"", "manual", "manual_csv", "unknown"}
ANALYST_TARGET_MIN_PRICE_RATIO = 0.05
ANALYST_TARGET_MAX_PRICE_RATIO = 20.0


@dataclass(frozen=True)
class ForeignEquitySourceRowDiagnostic:
    row_type: str
    row_number: int
    ticker: str | None
    status: str
    blockers: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    source: str | None = None
    source_url: str | None = None
    as_of_date: str | None = None
    effective_date: str | None = None


@dataclass(frozen=True)
class ForeignEquityAnalystTarget:
    ticker: str
    target_date: str
    currency: str | None
    target_mean: float
    target_low: float | None
    target_high: float | None
    analyst_count: int | None
    source: str
    source_url: str
    as_of_date: str | None
    effective_date: str | None
    notes: str | None = None


@dataclass(frozen=True)
class ForeignEquityTickerSourceStatus:
    ticker: str
    identity_available: bool
    fundamental_rows: int
    estimate_available: bool
    target_available: bool
    score_available: bool
    projected_fundamental_available: bool
    projected_estimate_available: bool
    analyst_target_available: bool
    projected_analyst_target_available: bool
    status: str
    blockers: tuple[str, ...]
    recommended_action: str


@dataclass(frozen=True)
class ForeignEquitySourceValidation:
    fundamentals_path: str
    estimates_path: str
    analyst_targets_path: str
    valid_fundamental_rows: int
    valid_estimate_rows: int
    invalid_rows: int
    blank_rows: int
    valid_fundamental_tickers: tuple[str, ...]
    valid_estimate_tickers: tuple[str, ...]
    valid_analyst_target_rows: int
    valid_analyst_target_tickers: tuple[str, ...]
    source_required_tickers: tuple[str, ...]
    projected_ready_tickers: tuple[str, ...]
    apply_ready: bool
    blocked_reason: str | None
    diagnostics: tuple[ForeignEquitySourceRowDiagnostic, ...]
    ticker_statuses: tuple[ForeignEquityTickerSourceStatus, ...]
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class ForeignEquitySourceApplyResult:
    dry_run: bool
    applied: bool
    imported_fundamental_rows: int
    imported_estimate_rows: int
    imported_tickers: tuple[str, ...]
    validation: ForeignEquitySourceValidation
    blocked_reason: str | None = None
    warnings: tuple[str, ...] = ()


def _display_path(config: AppConfig, path: Path) -> str:
    try:
        return str(path.relative_to(config.project_root))
    except ValueError:
        return str(path)


def _path(config: AppConfig, configured: Path) -> Path:
    return configured if configured.is_absolute() else config.project_root / configured


def _is_blank_row(row: dict[str, str]) -> bool:
    return not any((value or "").strip() for value in row.values())


def _read_rows(path: Path) -> list[tuple[int, dict[str, str]]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as input_file:
        reader = csv.DictReader(input_file)
        return [
            (reader.line_num, dict(row))
            for row in reader
        ]


def _date_value(row: dict[str, str], name: str, blockers: list[str]) -> str | None:
    value = (row.get(name) or "").strip()
    if not value:
        blockers.append(f"missing_{name}")
        return None
    try:
        return date.fromisoformat(value).isoformat()
    except ValueError:
        blockers.append(f"malformed_{name}")
        return None


def _source_blockers(row: dict[str, str]) -> tuple[str, ...]:
    blockers: list[str] = []
    source = (row.get("source") or "").strip()
    source_url = (row.get("source_url") or "").strip()
    notes = (row.get("notes") or "").strip()
    if source.lower() in DISALLOWED_SOURCE_LABELS:
        blockers.append("missing_source")
    if not source_url:
        blockers.append("missing_source_url")
    elif not source_url.lower().startswith(("https://", "http://")):
        blockers.append("unsupported_source_url")
    if not notes:
        blockers.append("missing_notes")
    return tuple(blockers)


def _foreign_identity_blockers(config: AppConfig, ticker: str) -> tuple[str, ...]:
    metadata, blockers = resolve_foreign_equity_research_metadata(config, ticker)
    if blockers:
        return ("source_backed_foreign_identity_required", *blockers)
    if not metadata.isin or not metadata.source_url:
        return ("source_backed_foreign_identity_required",)
    return ()


def _has_numeric(row: dict[str, str], fields: set[str]) -> bool:
    return any((row.get(field) or "").strip() for field in fields)


def _float_value(row: dict[str, str], name: str, blockers: list[str], *, required: bool = False) -> float | None:
    value = (row.get(name) or "").strip()
    if not value:
        if required:
            blockers.append(f"missing_{name}")
        return None
    try:
        return float(value.replace(",", ""))
    except ValueError:
        blockers.append(f"malformed_{name}")
        return None


def _int_value(row: dict[str, str], name: str, blockers: list[str]) -> int | None:
    value = (row.get(name) or "").strip()
    if not value:
        return None
    try:
        return int(value.replace(",", ""))
    except ValueError:
        blockers.append(f"malformed_{name}")
        return None


def _target_date_stale(config: AppConfig, target_date: str | None) -> bool:
    if target_date is None:
        return False
    try:
        parsed = date.fromisoformat(target_date)
    except ValueError:
        return False
    return (date.today() - parsed).days > config.valuation_stale_estimates_after_days


def _analyst_target_scale_blockers(
    config: AppConfig,
    ticker: str,
    values: tuple[float | None, ...],
) -> tuple[str, ...]:
    feature = latest_price_feature(config.database_path, ticker)
    current_price = feature.current_price if feature is not None else None
    if current_price is None or current_price <= 0:
        return ("missing_current_price_for_target_scale_check",)
    blockers: list[str] = []
    for value in values:
        if value is None:
            continue
        ratio = value / current_price
        if ratio < ANALYST_TARGET_MIN_PRICE_RATIO or ratio > ANALYST_TARGET_MAX_PRICE_RATIO:
            blockers.append("analyst_target_price_scale_mismatch")
            break
    return tuple(blockers)


def _parse_single_fundamental(row: dict[str, str]) -> Fundamental:
    output = StringIO()
    writer = csv.DictWriter(output, fieldnames=FUNDAMENTAL_HEADERS)
    writer.writeheader()
    writer.writerow({field: row.get(field, "") for field in FUNDAMENTAL_HEADERS})
    return parse_fundamentals_csv(output.getvalue())[0]


def _parse_single_estimate(row: dict[str, str]) -> Estimate:
    output = StringIO()
    writer = csv.DictWriter(output, fieldnames=ESTIMATE_HEADERS)
    writer.writeheader()
    writer.writerow({field: row.get(field, "") for field in ESTIMATE_HEADERS})
    return parse_estimates_csv(output.getvalue())[0]


def _validate_fundamental_row(
    config: AppConfig,
    row_number: int,
    row: dict[str, str],
) -> tuple[ForeignEquitySourceRowDiagnostic, Fundamental | None]:
    if _is_blank_row(row):
        return (
            ForeignEquitySourceRowDiagnostic(
                row_type="fundamental",
                row_number=row_number,
                ticker=None,
                status="blank",
            ),
            None,
        )
    blockers = list(_source_blockers(row))
    as_of_date = _date_value(row, "as_of_date", blockers)
    effective_date = _date_value(row, "effective_date", blockers)
    ticker = normalize_ticker(row.get("ticker", ""))
    if not ticker:
        blockers.append("missing_ticker")
    else:
        blockers.extend(_foreign_identity_blockers(config, ticker))
    if not _has_numeric(row, FUNDAMENTAL_NUMERIC_FIELDS):
        blockers.append("missing_numeric_fundamental_field")
    fundamental: Fundamental | None = None
    if not blockers:
        try:
            fundamental = _parse_single_fundamental(row)
        except (IndexError, ValueError) as error:
            blockers.append(str(error).replace(" ", "_"))
    status = "valid" if fundamental is not None and not blockers else "invalid"
    return (
        ForeignEquitySourceRowDiagnostic(
            row_type="fundamental",
            row_number=row_number,
            ticker=ticker or None,
            status=status,
            blockers=tuple(blockers),
            source=(row.get("source") or "").strip() or None,
            source_url=(row.get("source_url") or "").strip() or None,
            as_of_date=as_of_date,
            effective_date=effective_date,
        ),
        fundamental if status == "valid" else None,
    )


def _validate_estimate_row(
    config: AppConfig,
    row_number: int,
    row: dict[str, str],
) -> tuple[ForeignEquitySourceRowDiagnostic, Estimate | None]:
    if _is_blank_row(row):
        return (
            ForeignEquitySourceRowDiagnostic(
                row_type="estimate",
                row_number=row_number,
                ticker=None,
                status="blank",
            ),
            None,
        )
    blockers = list(_source_blockers(row))
    as_of_date = _date_value(row, "as_of_date", blockers)
    effective_date = _date_value(row, "effective_date", blockers)
    ticker = normalize_ticker(row.get("ticker", ""))
    metric = (row.get("metric") or "").strip().lower()
    if not ticker:
        blockers.append("missing_ticker")
    else:
        blockers.extend(_foreign_identity_blockers(config, ticker))
    if metric != "eps":
        blockers.append("foreign_equity_requires_eps_estimate")
    if not _has_numeric(row, ESTIMATE_NUMERIC_FIELDS | ESTIMATE_INTEGER_FIELDS):
        blockers.append("missing_numeric_estimate_field")
    estimate: Estimate | None = None
    if not blockers:
        try:
            estimate = _parse_single_estimate(row)
        except (IndexError, ValueError) as error:
            blockers.append(str(error).replace(" ", "_"))
    status = "valid" if estimate is not None and not blockers else "invalid"
    return (
        ForeignEquitySourceRowDiagnostic(
            row_type="estimate",
            row_number=row_number,
            ticker=ticker or None,
            status=status,
            blockers=tuple(blockers),
            source=(row.get("source") or "").strip() or None,
            source_url=(row.get("source_url") or "").strip() or None,
            as_of_date=as_of_date,
            effective_date=effective_date,
        ),
        estimate if status == "valid" else None,
    )


def _validate_analyst_target_row(
    config: AppConfig,
    row_number: int,
    row: dict[str, str],
) -> tuple[ForeignEquitySourceRowDiagnostic, ForeignEquityAnalystTarget | None]:
    if _is_blank_row(row):
        return (
            ForeignEquitySourceRowDiagnostic(
                row_type="analyst_target",
                row_number=row_number,
                ticker=None,
                status="blank",
            ),
            None,
        )
    blockers = list(_source_blockers(row))
    target_date = _date_value(row, "target_date", blockers)
    as_of_date = _date_value(row, "as_of_date", blockers)
    effective_date = _date_value(row, "effective_date", blockers)
    ticker = normalize_ticker(row.get("ticker", ""))
    if not ticker:
        blockers.append("missing_ticker")
    else:
        blockers.extend(_foreign_identity_blockers(config, ticker))
    target_mean = _float_value(row, "target_mean", blockers, required=True)
    target_low = _float_value(row, "target_low", blockers)
    target_high = _float_value(row, "target_high", blockers)
    analyst_count = _int_value(row, "analyst_count", blockers)
    if target_mean is not None and target_mean <= 0:
        blockers.append("non_positive_target_mean")
    if target_low is not None and target_low <= 0:
        blockers.append("non_positive_target_low")
    if target_high is not None and target_high <= 0:
        blockers.append("non_positive_target_high")
    if (
        target_low is not None
        and target_high is not None
        and target_low > target_high
    ):
        blockers.append("target_low_above_target_high")
    if (
        target_mean is not None
        and target_low is not None
        and target_mean < target_low
    ):
        blockers.append("target_mean_below_target_low")
    if (
        target_mean is not None
        and target_high is not None
        and target_mean > target_high
    ):
        blockers.append("target_mean_above_target_high")
    if analyst_count is not None and analyst_count < 0:
        blockers.append("negative_analyst_count")
    if _target_date_stale(config, target_date):
        blockers.append("stale_target_date")
    if ticker and target_mean is not None:
        blockers.extend(
            _analyst_target_scale_blockers(
                config,
                ticker,
                (target_mean, target_low, target_high),
            )
        )

    target: ForeignEquityAnalystTarget | None = None
    if not blockers and target_date is not None and target_mean is not None:
        target = ForeignEquityAnalystTarget(
            ticker=ticker,
            target_date=target_date,
            currency=(row.get("currency") or "").strip() or None,
            target_mean=target_mean,
            target_low=target_low,
            target_high=target_high,
            analyst_count=analyst_count,
            source=(row.get("source") or "").strip(),
            source_url=(row.get("source_url") or "").strip(),
            as_of_date=as_of_date,
            effective_date=effective_date,
            notes=(row.get("notes") or "").strip() or None,
        )
    status = "valid" if target is not None and not blockers else "invalid"
    return (
        ForeignEquitySourceRowDiagnostic(
            row_type="analyst_target",
            row_number=row_number,
            ticker=ticker or None,
            status=status,
            blockers=tuple(blockers),
            source=(row.get("source") or "").strip() or None,
            source_url=(row.get("source_url") or "").strip() or None,
            as_of_date=as_of_date,
            effective_date=effective_date,
        ),
        target if status == "valid" else None,
    )


def _target_tickers(config: AppConfig) -> tuple[str, ...]:
    tickers: list[str] = []
    for asset in list_assets(config.database_path):
        if not is_scoreable_asset(asset):
            continue
        if (asset.asset_type or "equity").strip().lower() != "equity":
            continue
        if not _foreign_identity_blockers(config, asset.ticker):
            tickers.append(asset.ticker)
    for ticker in FOREIGN_EQUITY_SOURCE_TICKERS:
        if not _foreign_identity_blockers(config, ticker) and ticker not in tickers:
            tickers.append(ticker)
    return tuple(sorted(dict.fromkeys(tickers)))


def _validated_rows(
    config: AppConfig,
) -> tuple[
    tuple[ForeignEquitySourceRowDiagnostic, ...],
    tuple[Fundamental, ...],
    tuple[Estimate, ...],
    tuple[ForeignEquityAnalystTarget, ...],
]:
    diagnostics: list[ForeignEquitySourceRowDiagnostic] = []
    fundamentals: list[Fundamental] = []
    estimates: list[Estimate] = []
    analyst_targets: list[ForeignEquityAnalystTarget] = []
    fundamentals_path = _path(config, config.foreign_equity_fundamentals_source_path)
    estimates_path = _path(config, config.foreign_equity_estimates_source_path)
    analyst_targets_path = _path(config, config.foreign_equity_analyst_targets_source_path)
    for row_number, row in _read_rows(fundamentals_path):
        diagnostic, fundamental = _validate_fundamental_row(config, row_number, row)
        diagnostics.append(diagnostic)
        if fundamental is not None:
            fundamentals.append(fundamental)
    for row_number, row in _read_rows(estimates_path):
        diagnostic, estimate = _validate_estimate_row(config, row_number, row)
        diagnostics.append(diagnostic)
        if estimate is not None:
            estimates.append(estimate)
    for row_number, row in _read_rows(analyst_targets_path):
        diagnostic, analyst_target = _validate_analyst_target_row(config, row_number, row)
        diagnostics.append(diagnostic)
        if analyst_target is not None:
            analyst_targets.append(analyst_target)
    return tuple(diagnostics), tuple(fundamentals), tuple(estimates), tuple(analyst_targets)


def latest_foreign_equity_analyst_targets(
    config: AppConfig,
    ticker: str | None = None,
) -> tuple[ForeignEquityAnalystTarget, ...]:
    _, _, _, analyst_targets = _validated_rows(config)
    selected = [
        target
        for target in analyst_targets
        if ticker is None or target.ticker == normalize_ticker(ticker)
    ]
    latest_by_ticker: dict[str, ForeignEquityAnalystTarget] = {}
    for target in sorted(selected, key=lambda item: (item.ticker, item.target_date)):
        latest_by_ticker[target.ticker] = target
    return tuple(latest_by_ticker[ticker] for ticker in sorted(latest_by_ticker))


def export_foreign_equity_source_templates(config: AppConfig) -> tuple[str, str, str]:
    fundamentals_path = _path(config, config.foreign_equity_fundamentals_source_path)
    estimates_path = _path(config, config.foreign_equity_estimates_source_path)
    analyst_targets_path = _path(config, config.foreign_equity_analyst_targets_source_path)
    for path, headers in (
        (fundamentals_path, FOREIGN_EQUITY_FUNDAMENTAL_HEADERS),
        (estimates_path, FOREIGN_EQUITY_ESTIMATE_HEADERS),
        (analyst_targets_path, FOREIGN_EQUITY_ANALYST_TARGET_HEADERS),
    ):
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            with path.open("w", encoding="utf-8", newline="") as output_file:
                csv.DictWriter(output_file, fieldnames=headers).writeheader()
    return (
        _display_path(config, fundamentals_path),
        _display_path(config, estimates_path),
        _display_path(config, analyst_targets_path),
    )


def validate_foreign_equity_sources(config: AppConfig) -> ForeignEquitySourceValidation:
    diagnostics, fundamentals, estimates, analyst_targets = _validated_rows(config)
    target_tickers = _target_tickers(config)
    valid_fundamental_tickers = tuple(sorted({row.ticker for row in fundamentals}))
    valid_estimate_tickers = tuple(sorted({row.ticker for row in estimates}))
    valid_analyst_target_tickers = tuple(sorted({row.ticker for row in analyst_targets}))
    existing_fundamental_tickers = {
        ticker for ticker in target_tickers if list_fundamentals(config.database_path, ticker)
    }
    existing_estimate_tickers = {
        ticker
        for ticker in target_tickers
        if latest_estimate(config.database_path, ticker, "eps") is not None
    }
    existing_analyst_target_tickers = set(valid_analyst_target_tickers)
    projected_fundamental_tickers = existing_fundamental_tickers | set(valid_fundamental_tickers)
    projected_estimate_tickers = existing_estimate_tickers | set(valid_estimate_tickers)
    projected_analyst_target_tickers = existing_analyst_target_tickers | set(valid_analyst_target_tickers)
    source_required_tickers = tuple(
        ticker
        for ticker in target_tickers
        if ticker not in projected_fundamental_tickers or ticker not in projected_estimate_tickers
    )
    projected_ready_tickers = tuple(
        ticker
        for ticker in target_tickers
        if ticker in projected_fundamental_tickers and ticker in projected_estimate_tickers
    )
    invalid_rows = sum(1 for row in diagnostics if row.status == "invalid")
    blank_rows = sum(1 for row in diagnostics if row.status == "blank")
    valid_row_count = len(fundamentals) + len(estimates) + len(analyst_targets)
    blocked_reason = None
    if invalid_rows:
        blocked_reason = "invalid_foreign_equity_source_rows"
    elif valid_row_count == 0:
        blocked_reason = "no_valid_foreign_equity_source_rows"
    warnings: list[str] = []
    if source_required_tickers:
        warnings.append("foreign_equity_source_data_required")
    if blank_rows:
        warnings.append("blank_foreign_equity_source_rows_ignored")
    ticker_statuses: list[ForeignEquityTickerSourceStatus] = []
    for ticker in target_tickers:
        status = research_ticker_status(config, ticker)
        projected_fundamental = ticker in projected_fundamental_tickers
        projected_estimate = ticker in projected_estimate_tickers
        projected_analyst_target = ticker in projected_analyst_target_tickers
        blockers: list[str] = []
        if not projected_fundamental:
            blockers.append("missing_source_backed_foreign_fundamentals")
        if not projected_estimate:
            blockers.append("missing_source_backed_foreign_eps_estimate")
        if not status.target_available:
            blockers.append("missing_target")
        if not status.score_available:
            blockers.append("missing_score")
        ticker_statuses.append(
            ForeignEquityTickerSourceStatus(
                ticker=ticker,
                identity_available=status.foreign_identity_available,
                fundamental_rows=status.fundamental_count,
                estimate_available=status.estimate_available,
                target_available=status.target_available,
                score_available=status.score_available,
                projected_fundamental_available=projected_fundamental,
                projected_estimate_available=projected_estimate,
                analyst_target_available=ticker in existing_analyst_target_tickers,
                projected_analyst_target_available=projected_analyst_target,
                status="ready" if not blockers else "source_data_required",
                blockers=tuple(blockers),
                recommended_action=(
                    "Recompute targets and scores."
                    if (
                        projected_fundamental
                        and projected_estimate
                        and (projected_analyst_target or ticker not in source_required_tickers)
                        and blockers
                    )
                    else "Stage source-backed fundamentals and EPS estimates."
                ),
            )
        )
    fundamentals_path = _path(config, config.foreign_equity_fundamentals_source_path)
    estimates_path = _path(config, config.foreign_equity_estimates_source_path)
    analyst_targets_path = _path(config, config.foreign_equity_analyst_targets_source_path)
    return ForeignEquitySourceValidation(
        fundamentals_path=_display_path(config, fundamentals_path),
        estimates_path=_display_path(config, estimates_path),
        analyst_targets_path=_display_path(config, analyst_targets_path),
        valid_fundamental_rows=len(fundamentals),
        valid_estimate_rows=len(estimates),
        valid_analyst_target_rows=len(analyst_targets),
        invalid_rows=invalid_rows,
        blank_rows=blank_rows,
        valid_fundamental_tickers=valid_fundamental_tickers,
        valid_estimate_tickers=valid_estimate_tickers,
        valid_analyst_target_tickers=valid_analyst_target_tickers,
        source_required_tickers=source_required_tickers,
        projected_ready_tickers=projected_ready_tickers,
        apply_ready=blocked_reason is None,
        blocked_reason=blocked_reason,
        diagnostics=diagnostics,
        ticker_statuses=tuple(ticker_statuses),
        warnings=tuple(warnings),
    )


def apply_foreign_equity_sources(
    config: AppConfig,
    *,
    confirm: bool = False,
) -> ForeignEquitySourceApplyResult:
    validation = validate_foreign_equity_sources(config)
    if not validation.apply_ready:
        return ForeignEquitySourceApplyResult(
            dry_run=not confirm,
            applied=False,
            imported_fundamental_rows=0,
            imported_estimate_rows=0,
            imported_tickers=(),
            validation=validation,
            blocked_reason=validation.blocked_reason,
            warnings=validation.warnings,
        )
    diagnostics, fundamentals, estimates, _ = _validated_rows(config)
    tickers = tuple(sorted({row.ticker for row in fundamentals} | {row.ticker for row in estimates}))
    if not confirm:
        return ForeignEquitySourceApplyResult(
            dry_run=True,
            applied=False,
            imported_fundamental_rows=0,
            imported_estimate_rows=0,
            imported_tickers=tickers,
            validation=validation,
            warnings=("dry_run_only", *validation.warnings),
        )
    for row in fundamentals:
        upsert_fundamental(config.database_path, row)
    for row in estimates:
        upsert_estimate(config.database_path, row)
    refreshed = validate_foreign_equity_sources(config)
    return ForeignEquitySourceApplyResult(
        dry_run=False,
        applied=True,
        imported_fundamental_rows=len(fundamentals),
        imported_estimate_rows=len(estimates),
        imported_tickers=tickers,
        validation=refreshed,
        warnings=refreshed.warnings,
    )


def build_foreign_equity_source_status_text(
    validation: ForeignEquitySourceValidation,
) -> str:
    lines = [
        "Foreign Equity Source Status",
        f"Fundamentals source: {validation.fundamentals_path}",
        f"Estimates source: {validation.estimates_path}",
        f"Analyst targets source: {validation.analyst_targets_path}",
        f"Valid fundamental rows: {validation.valid_fundamental_rows}",
        f"Valid estimate rows: {validation.valid_estimate_rows}",
        f"Valid analyst target rows: {validation.valid_analyst_target_rows}",
        f"Invalid rows: {validation.invalid_rows}",
        f"Blank rows: {validation.blank_rows}",
        "Valid fundamental tickers: "
        + (", ".join(validation.valid_fundamental_tickers) if validation.valid_fundamental_tickers else "none"),
        "Valid estimate tickers: "
        + (", ".join(validation.valid_estimate_tickers) if validation.valid_estimate_tickers else "none"),
        "Valid analyst target tickers: "
        + (
            ", ".join(validation.valid_analyst_target_tickers)
            if validation.valid_analyst_target_tickers
            else "none"
        ),
        "Source-required tickers: "
        + (", ".join(validation.source_required_tickers) if validation.source_required_tickers else "none"),
        "Projected source-ready tickers: "
        + (", ".join(validation.projected_ready_tickers) if validation.projected_ready_tickers else "none"),
        f"Apply ready: {validation.apply_ready}",
        f"Blocked reason: {validation.blocked_reason or 'none'}",
    ]
    if validation.ticker_statuses:
        lines.append("Ticker diagnostics:")
        for item in validation.ticker_statuses:
            lines.append(
                " | ".join(
                    (
                        item.ticker,
                        item.status,
                        f"fundamentals={item.fundamental_rows}",
                        f"eps_estimate={item.estimate_available}",
                        f"analyst_target={item.analyst_target_available}",
                        f"target={item.target_available}",
                        f"score={item.score_available}",
                        "blockers=" + (",".join(item.blockers) if item.blockers else "none"),
                    )
                )
            )
    if validation.diagnostics:
        lines.append("Row diagnostics:")
        for row in validation.diagnostics:
            lines.append(
                f"- {row.row_type} row {row.row_number}: "
                f"{row.ticker or 'blank'} {row.status}; "
                f"blockers={','.join(row.blockers) if row.blockers else 'none'}"
            )
    if validation.warnings:
        lines.append("Warnings: " + ", ".join(validation.warnings))
    return "\n".join(lines)


def build_foreign_equity_source_apply_text(result: ForeignEquitySourceApplyResult) -> str:
    lines = [
        "Foreign equity source apply",
        f"Dry run: {result.dry_run}",
        f"Applied: {result.applied}",
        f"Imported fundamental rows: {result.imported_fundamental_rows}",
        f"Imported estimate rows: {result.imported_estimate_rows}",
        "Imported tickers: " + (", ".join(result.imported_tickers) if result.imported_tickers else "none"),
        f"Blocked reason: {result.blocked_reason or 'none'}",
    ]
    if result.warnings:
        lines.append("Warnings: " + ", ".join(result.warnings))
    return "\n".join(lines)
