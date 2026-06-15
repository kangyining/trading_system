from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import date
from io import StringIO
from pathlib import Path
import threading
import time
from typing import Any

from .config import AppConfig
from .dashboard import build_dashboard
from .ibkr_provider import check_ibkr_status, _import_ibapi, _is_info_error
from .missing_tickers import (
    SOURCE_ACCOUNT_CONTEXT,
    resolve_missing_tickers,
    run_missing_ticker_automation,
)
from .options import (
    OPTIONS_POSITION_HEADERS,
    REQUIRED_OPTIONS_POSITION_COLUMNS,
    compute_options_lifecycle,
    compute_options_outcomes,
    compute_options_risk,
    ensure_options_positions_csv_header,
    load_options_positions_csv,
    parse_options_positions_csv,
)
from .portfolio import (
    CASH_HEADERS,
    POSITION_HEADERS,
    compute_portfolio_context,
    ensure_portfolio_csv_headers,
    load_portfolio_csvs,
    parse_portfolio_cash_csv,
    parse_portfolio_positions_csv,
)
from .reporting import write_daily_report
from .storage import (
    count_rows_by_table,
    latest_asset,
    list_option_position_lifecycle_reviews,
    list_option_positions,
    list_option_risk_reviews,
    list_portfolio_cash,
    list_portfolio_positions,
    normalize_ticker,
)


ACCOUNT_EXPORT_HEADERS = (
    "record_type",
    "account",
    "ticker",
    "quantity",
    "cash_amount",
    "currency",
    "position_date",
    "cash_date",
    "market_price",
    "market_value",
    "base_market_value",
    "cost_basis_per_share",
    "cost_basis_total",
    "option_type",
    "side",
    "open_date",
    "expiration_date",
    "strike",
    "contracts",
    "premium",
    "close_date",
    "close_price",
    "assigned_flag",
    "assignment_price",
    "fees",
    "status",
    "source",
    "source_url",
    "notes",
    "as_of_date",
    "effective_date",
)


@dataclass(frozen=True)
class AccountContextValidation:
    valid_position_rows: int
    valid_cash_rows: int
    valid_option_position_rows: int
    blank_rows: int
    invalid_rows: tuple[str, ...]
    valid_position_tickers: tuple[str, ...]
    valid_option_tickers: tuple[str, ...]
    warnings: tuple[str, ...]

    @property
    def valid_rows(self) -> int:
        return (
            self.valid_position_rows
            + self.valid_cash_rows
            + self.valid_option_position_rows
        )

    @property
    def invalid_row_count(self) -> int:
        return len(self.invalid_rows)


@dataclass(frozen=True)
class AccountContextPreview:
    validation: AccountContextValidation
    current_portfolio_position_rows: int
    current_portfolio_cash_rows: int
    current_option_position_rows: int
    current_option_lifecycle_rows: int
    projected_portfolio_position_rows: int
    projected_portfolio_cash_rows: int
    projected_option_position_rows: int
    projected_option_lifecycle_rows: int
    current_missing_portfolio_context_risk_rows: int
    improvement_count: int
    apply_ready: bool
    blocked_reason: str | None
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class OptionPositionReadinessDiagnostics:
    readiness_status: str
    current_option_position_rows: int
    current_option_lifecycle_rows: int
    staged_option_position_rows: int
    blank_option_position_rows: int
    valid_option_position_rows: int
    invalid_option_position_rows: int
    valid_option_tickers: tuple[str, ...]
    projected_option_position_rows: int
    projected_option_lifecycle_rows: int
    would_improve_lifecycle: bool
    blockers: tuple[str, ...]
    warnings: tuple[str, ...]
    invalid_rows: tuple[str, ...]
    required_fields: tuple[str, ...]
    recommended_fields: tuple[str, ...]
    append_target_path: Path
    template_path: Path
    manual_path: Path
    source_files: tuple[Path, ...]
    recommended_actions: tuple[str, ...]


@dataclass(frozen=True)
class AccountContextTemplateResult:
    source_dir: Path
    files: tuple[Path, ...]


@dataclass(frozen=True)
class AccountContextApplyResult:
    preview: AccountContextPreview
    confirmed: bool
    applied: bool
    positions_loaded: int
    cash_loaded: int
    option_positions_loaded: int
    portfolio_reviews_computed: int
    option_risk_tickers: int
    option_outcome_tickers: int
    option_lifecycle_tickers: int
    report_path: Path | None
    dashboard_path: Path | None
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class AccountContextStatus:
    activation_status: str
    portfolio_position_rows: int
    portfolio_cash_rows: int
    option_position_rows: int
    option_lifecycle_rows: int
    option_risk_missing_portfolio_context_rows: int
    validation: AccountContextValidation
    preview: AccountContextPreview
    option_position_diagnostics: OptionPositionReadinessDiagnostics
    blockers: tuple[str, ...]


@dataclass(frozen=True)
class AccountExportNormalizeResult:
    provider: str
    input_path: Path
    output_files: tuple[Path, ...]
    position_rows: int
    cash_rows: int
    option_position_rows: int
    skipped_rows: int
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class AccountProviderStatus:
    source_exports_dir: Path
    source_export_files: int
    valid_position_rows: int
    valid_cash_rows: int
    valid_option_position_rows: int
    ibkr_available: bool
    ibkr_connected: bool
    ibkr_host: str
    ibkr_port: int
    ibkr_managed_account_count: int
    latest_source_export_timestamp: str | None
    blockers: tuple[str, ...]
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class AccountContextFetchResult:
    source: str
    provider: str
    read_only: bool
    fetched: bool
    input_path: Path | None
    output_files: tuple[Path, ...]
    position_rows: int
    cash_rows: int
    option_position_rows: int
    warnings: tuple[str, ...]


def export_account_context_template(config: AppConfig) -> AccountContextTemplateResult:
    ensure_portfolio_csv_headers(config.portfolio_positions_path, config.portfolio_cash_path)
    ensure_options_positions_csv_header(config.options_positions_path)
    source_dir = config.account_source_exports_dir
    source_dir.mkdir(parents=True, exist_ok=True)
    files = (
        _ensure_template(source_dir / "portfolio_positions_backfill.csv", POSITION_HEADERS),
        _ensure_template(source_dir / "portfolio_cash_backfill.csv", CASH_HEADERS),
        _ensure_template(source_dir / "options_positions_backfill.csv", OPTIONS_POSITION_HEADERS),
        _ensure_template(source_dir / "generic_account_export_template.csv", ACCOUNT_EXPORT_HEADERS),
        _ensure_template(source_dir / "ibkr_account_export_template.csv", ACCOUNT_EXPORT_HEADERS),
    )
    return AccountContextTemplateResult(source_dir=source_dir, files=files)


def validate_account_context_backfill(config: AppConfig) -> AccountContextValidation:
    ensure_portfolio_csv_headers(config.portfolio_positions_path, config.portfolio_cash_path)
    ensure_options_positions_csv_header(config.options_positions_path)
    position_rows: list[dict[str, str]] = []
    cash_rows: list[dict[str, str]] = []
    option_rows: list[dict[str, str]] = []
    invalid: list[str] = []
    blank_rows = 0

    for path, kind in _account_context_files(config):
        parsed_rows, blanks, errors = _read_rows_for_kind(path, kind)
        blank_rows += blanks
        invalid.extend(errors)
        if kind == "portfolio_position":
            position_rows.extend(parsed_rows)
        elif kind == "portfolio_cash":
            cash_rows.extend(parsed_rows)
        elif kind == "option_position":
            option_rows.extend(parsed_rows)

    valid_position_rows, position_tickers, position_errors = _validate_portfolio_positions(
        config, position_rows
    )
    valid_cash_rows, cash_errors = _validate_portfolio_cash(cash_rows)
    valid_option_rows, option_tickers, option_errors = _validate_option_positions(
        config, option_rows
    )
    invalid.extend(position_errors)
    invalid.extend(cash_errors)
    invalid.extend(option_errors)

    warnings: list[str] = []
    if valid_position_rows == 0:
        warnings.append("no_valid_portfolio_position_rows")
    if valid_cash_rows == 0:
        warnings.append("no_valid_portfolio_cash_rows")
    if valid_option_rows == 0:
        warnings.append("no_valid_option_position_rows")
    if any("unsupported or inactive ticker" in item for item in invalid):
        warnings.append("missing_ticker_candidates_present")
        warnings.append(
            "run_missing_ticker_resolver:python -m target_opportunity_monitor resolve-missing-tickers --source account_context"
        )

    return AccountContextValidation(
        valid_position_rows=valid_position_rows,
        valid_cash_rows=valid_cash_rows,
        valid_option_position_rows=valid_option_rows,
        blank_rows=blank_rows,
        invalid_rows=tuple(invalid),
        valid_position_tickers=tuple(sorted(position_tickers)),
        valid_option_tickers=tuple(sorted(option_tickers)),
        warnings=tuple(_unique(warnings)),
    )


def preview_account_context_activation(config: AppConfig) -> AccountContextPreview:
    validation = validate_account_context_backfill(config)
    current_position_keys = _current_portfolio_position_keys(config)
    current_cash_keys = _current_portfolio_cash_keys(config)
    current_option_keys = _current_option_position_keys(config)
    incoming_position_keys, incoming_cash_keys, incoming_option_keys = _incoming_keys(config)

    projected_position_rows = len(current_position_keys | incoming_position_keys)
    projected_cash_rows = len(current_cash_keys | incoming_cash_keys)
    projected_option_rows = len(current_option_keys | incoming_option_keys)
    current_lifecycle_rows = count_rows_by_table(
        config.database_path, "option_position_lifecycle_reviews"
    )
    projected_lifecycle_rows = max(
        current_lifecycle_rows,
        projected_option_rows,
    )
    missing_context_rows = _missing_portfolio_context_risk_rows(config)

    improvement_count = 0
    if projected_position_rows > len(current_position_keys):
        improvement_count += projected_position_rows - len(current_position_keys)
    if projected_cash_rows > len(current_cash_keys):
        improvement_count += projected_cash_rows - len(current_cash_keys)
    if projected_option_rows > len(current_option_keys):
        improvement_count += projected_option_rows - len(current_option_keys)
    if projected_lifecycle_rows > current_lifecycle_rows:
        improvement_count += projected_lifecycle_rows - current_lifecycle_rows
    if missing_context_rows and (
        validation.valid_position_rows > 0 or validation.valid_cash_rows > 0
    ):
        improvement_count += 1

    blocked_reason = None
    if validation.invalid_rows:
        blocked_reason = "invalid_account_context_rows"
    elif validation.valid_rows == 0:
        blocked_reason = "no_valid_account_context_rows"
    elif improvement_count == 0:
        blocked_reason = "projected_account_context_does_not_improve"

    warnings: list[str] = []
    warnings.extend(validation.warnings)
    if missing_context_rows:
        warnings.append("option_risk_missing_portfolio_context")
    if current_lifecycle_rows == 0 and projected_lifecycle_rows == 0:
        warnings.append("no_option_lifecycle_rows")

    return AccountContextPreview(
        validation=validation,
        current_portfolio_position_rows=len(current_position_keys),
        current_portfolio_cash_rows=len(current_cash_keys),
        current_option_position_rows=len(current_option_keys),
        current_option_lifecycle_rows=current_lifecycle_rows,
        projected_portfolio_position_rows=projected_position_rows,
        projected_portfolio_cash_rows=projected_cash_rows,
        projected_option_position_rows=projected_option_rows,
        projected_option_lifecycle_rows=projected_lifecycle_rows,
        current_missing_portfolio_context_risk_rows=missing_context_rows,
        improvement_count=improvement_count,
        apply_ready=blocked_reason is None,
        blocked_reason=blocked_reason,
        warnings=tuple(_unique(warnings)),
    )


def apply_account_context_backfill(
    config: AppConfig,
    *,
    confirm: bool = False,
    allow_partial: bool = False,
) -> AccountContextApplyResult:
    automation_warnings: list[str] = []
    if confirm:
        automation = run_missing_ticker_automation(
            config,
            source=SOURCE_ACCOUNT_CONTEXT,
            apply_ready=True,
            hydrate=True,
        )
        if automation.onboarded_tickers:
            automation_warnings.append(
                "missing_ticker_auto_onboarded:" + ",".join(automation.onboarded_tickers)
            )
        if automation.hydrated_tickers:
            automation_warnings.append(
                "missing_ticker_auto_hydrated:" + ",".join(automation.hydrated_tickers)
            )
        automation_warnings.extend(automation.warnings)
    else:
        try:
            resolve_result = resolve_missing_tickers(config, source=SOURCE_ACCOUNT_CONTEXT)
            if resolve_result.ready_to_onboard_count:
                automation_warnings.append(
                    "missing_ticker_candidates_ready:"
                    f"{resolve_result.ready_to_onboard_count}"
                )
        except Exception as error:
            automation_warnings.append(f"missing_ticker_resolver_failed:{error}")

    preview = preview_account_context_activation(config)
    warnings: list[str] = list(preview.warnings)
    warnings.extend(automation_warnings)
    if not confirm:
        return AccountContextApplyResult(
            preview=preview,
            confirmed=False,
            applied=False,
            positions_loaded=0,
            cash_loaded=0,
            option_positions_loaded=0,
            portfolio_reviews_computed=0,
            option_risk_tickers=0,
            option_outcome_tickers=0,
            option_lifecycle_tickers=0,
            report_path=None,
            dashboard_path=None,
            warnings=tuple(_unique(warnings + ["dry_run_only"])),
        )
    if preview.validation.invalid_rows:
        raise ValueError("Cannot apply account context: invalid rows are present.")
    if preview.validation.valid_rows == 0:
        raise ValueError("Cannot apply account context: no valid rows are present.")
    if preview.improvement_count == 0:
        raise ValueError("Cannot apply account context: projected coverage does not improve.")
    if not allow_partial and (
        preview.validation.valid_position_rows == 0
        or preview.validation.valid_cash_rows == 0
        or preview.validation.valid_option_position_rows == 0
    ):
        raise ValueError(
            "Cannot apply account context: partial data requires --allow-partial."
        )

    _merge_valid_rows_into_manual_files(config)
    portfolio_load = load_portfolio_csvs(config)
    option_load = load_options_positions_csv(config)
    portfolio_context = compute_portfolio_context(config)
    risk_result = compute_options_risk(config)
    outcome_result = compute_options_outcomes(config)
    lifecycle_result = compute_options_lifecycle(config)
    report_result = write_daily_report(config)
    dashboard_result = build_dashboard(config)

    warnings.extend(portfolio_load.warnings)
    warnings.extend(option_load.warnings)
    for result in risk_result.results:
        warnings.extend(result.warnings)
    for result in lifecycle_result.results:
        warnings.extend(result.warnings)

    return AccountContextApplyResult(
        preview=preview,
        confirmed=True,
        applied=True,
        positions_loaded=portfolio_load.position_count,
        cash_loaded=portfolio_load.cash_count,
        option_positions_loaded=option_load.loaded_count,
        portfolio_reviews_computed=portfolio_context.computed_count,
        option_risk_tickers=risk_result.computed_count,
        option_outcome_tickers=outcome_result.computed_count,
        option_lifecycle_tickers=lifecycle_result.computed_count,
        report_path=report_result.path,
        dashboard_path=dashboard_result.path,
        warnings=tuple(_unique(warnings)),
    )


def option_position_readiness_diagnostics(
    config: AppConfig,
    *,
    preview: AccountContextPreview | None = None,
    current_option_position_rows: int | None = None,
    current_option_lifecycle_rows: int | None = None,
) -> OptionPositionReadinessDiagnostics:
    ensure_options_positions_csv_header(config.options_positions_path)
    preview_value = preview or preview_account_context_activation(config)
    option_rows: list[dict[str, str]] = []
    invalid: list[str] = []
    blank_rows = 0
    source_files: list[Path] = []
    for path, kind in _account_context_files(config):
        if kind != "option_position":
            continue
        source_files.append(path)
        rows, blanks, errors = _read_rows_for_kind(path, kind)
        option_rows.extend(rows)
        blank_rows += blanks
        invalid.extend(errors)

    valid_rows, valid_tickers, option_errors = _validate_option_positions(
        config,
        option_rows,
    )
    invalid.extend(option_errors)
    current_rows = (
        current_option_position_rows
        if current_option_position_rows is not None
        else count_rows_by_table(config.database_path, "option_position_ledger")
    )
    current_lifecycle_rows = (
        current_option_lifecycle_rows
        if current_option_lifecycle_rows is not None
        else count_rows_by_table(
            config.database_path,
            "option_position_lifecycle_reviews",
        )
    )

    blockers: list[str] = []
    warnings: list[str] = []
    if current_rows == 0:
        blockers.append("empty_options_positions")
    if current_lifecycle_rows == 0 and preview_value.projected_option_lifecycle_rows == 0:
        blockers.append("no_option_lifecycle_rows")
    if valid_rows == 0:
        blockers.append("no_valid_option_position_rows")
    if invalid:
        blockers.append("invalid_option_position_rows")
    if (
        valid_rows > 0
        and preview_value.projected_option_position_rows > current_rows
        and not invalid
    ):
        warnings.append("option_positions_staged_pending_apply")
    if blank_rows:
        warnings.append("blank_option_position_rows_ignored")

    if invalid:
        readiness_status = "invalid_source_rows"
        recommended_actions = ("fix_option_position_rows", "validate_account_backfill")
    elif current_rows > 0 and current_lifecycle_rows > 0:
        readiness_status = "active"
        recommended_actions = ("monitor_option_lifecycle",)
    elif valid_rows > 0 and preview_value.projected_option_position_rows > current_rows:
        readiness_status = "ready_for_apply"
        recommended_actions = (
            "preview_account_activation",
            "dry_run_apply_account_context",
            "apply_account_context",
        )
    elif current_rows > 0 and current_lifecycle_rows == 0:
        readiness_status = "lifecycle_compute_required"
        recommended_actions = ("compute_options_lifecycle",)
    else:
        readiness_status = "source_data_required"
        recommended_actions = (
            "fetch_read_only_account_context",
            "append_option_position_row",
            "validate_account_backfill",
        )

    required_fields = tuple(
        field
        for field in OPTIONS_POSITION_HEADERS
        if field in REQUIRED_OPTIONS_POSITION_COLUMNS or field in {"account", "source"}
    )
    recommended_fields = (
        "position_id",
        "source_url",
        "as_of_date",
        "effective_date",
        "notes",
    )
    return OptionPositionReadinessDiagnostics(
        readiness_status=readiness_status,
        current_option_position_rows=current_rows,
        current_option_lifecycle_rows=current_lifecycle_rows,
        staged_option_position_rows=len(option_rows),
        blank_option_position_rows=blank_rows,
        valid_option_position_rows=valid_rows,
        invalid_option_position_rows=len(invalid),
        valid_option_tickers=tuple(sorted(valid_tickers)),
        projected_option_position_rows=preview_value.projected_option_position_rows,
        projected_option_lifecycle_rows=preview_value.projected_option_lifecycle_rows,
        would_improve_lifecycle=(
            preview_value.projected_option_lifecycle_rows > current_lifecycle_rows
        ),
        blockers=tuple(_unique(blockers)),
        warnings=tuple(_unique(warnings)),
        invalid_rows=tuple(invalid),
        required_fields=required_fields,
        recommended_fields=recommended_fields,
        append_target_path=config.account_source_exports_dir
        / "ui_options_positions_backfill.csv",
        template_path=config.account_source_exports_dir / "options_positions_backfill.csv",
        manual_path=config.options_positions_path,
        source_files=tuple(source_files),
        recommended_actions=recommended_actions,
    )


def account_context_status(config: AppConfig) -> AccountContextStatus:
    preview = preview_account_context_activation(config)
    portfolio_rows = count_rows_by_table(config.database_path, "portfolio_positions")
    cash_rows = count_rows_by_table(config.database_path, "portfolio_cash")
    option_rows = count_rows_by_table(config.database_path, "option_position_ledger")
    lifecycle_rows = count_rows_by_table(
        config.database_path, "option_position_lifecycle_reviews"
    )
    missing_context_rows = _missing_portfolio_context_risk_rows(config)

    blockers: list[str] = []
    if portfolio_rows == 0:
        blockers.append("empty_portfolio_positions")
    if cash_rows == 0:
        blockers.append("empty_portfolio_cash")
    if option_rows == 0:
        blockers.append("empty_options_positions")
    if lifecycle_rows == 0:
        blockers.append("no_option_lifecycle_rows")
    if missing_context_rows:
        blockers.append("option_risk_missing_portfolio_context")
    if preview.blocked_reason:
        blockers.append(preview.blocked_reason)

    option_diagnostics = option_position_readiness_diagnostics(
        config,
        preview=preview,
        current_option_position_rows=option_rows,
        current_option_lifecycle_rows=lifecycle_rows,
    )

    if not blockers:
        activation_status = "active"
    elif portfolio_rows or cash_rows or option_rows or lifecycle_rows:
        activation_status = "partial"
    else:
        activation_status = "not_configured"

    return AccountContextStatus(
        activation_status=activation_status,
        portfolio_position_rows=portfolio_rows,
        portfolio_cash_rows=cash_rows,
        option_position_rows=option_rows,
        option_lifecycle_rows=lifecycle_rows,
        option_risk_missing_portfolio_context_rows=missing_context_rows,
        validation=preview.validation,
        preview=preview,
        option_position_diagnostics=option_diagnostics,
        blockers=tuple(_unique(blockers)),
    )


def account_provider_status(
    config: AppConfig,
    *,
    check_connectivity: bool = True,
) -> AccountProviderStatus:
    validation = validate_account_context_backfill(config)
    source_dir = config.account_source_exports_dir
    files = tuple(sorted(source_dir.glob("*.csv"))) if source_dir.exists() else ()
    latest_timestamp = None
    if files:
        latest_timestamp = datetime_from_timestamp(max(path.stat().st_mtime for path in files))

    ibkr_available = False
    ibkr_connected = False
    ibkr_port = config.ibkr_paper_port
    managed_accounts = 0
    warnings: list[str] = []
    if check_connectivity:
        ibkr = check_ibkr_status(config)
        ibkr_available = ibkr.available
        ibkr_connected = ibkr.connected
        ibkr_port = ibkr.port
        managed_accounts = ibkr.managed_account_count
        warnings.extend(ibkr.warnings)
    else:
        _EClient, _Contract, _EWrapper, import_error = _import_ibapi()
        ibkr_available = import_error is None
        if import_error:
            warnings.append(f"ibapi_unavailable:{import_error}")

    blockers: list[str] = []
    if not ibkr_available:
        blockers.append("ibapi_missing")
    elif check_connectivity and not ibkr_connected:
        blockers.append("ibkr_not_connected")
    if validation.valid_rows == 0:
        blockers.append("no_valid_account_context_rows")

    return AccountProviderStatus(
        source_exports_dir=source_dir,
        source_export_files=len(files),
        valid_position_rows=validation.valid_position_rows,
        valid_cash_rows=validation.valid_cash_rows,
        valid_option_position_rows=validation.valid_option_position_rows,
        ibkr_available=ibkr_available,
        ibkr_connected=ibkr_connected,
        ibkr_host=config.ibkr_host,
        ibkr_port=ibkr_port,
        ibkr_managed_account_count=managed_accounts,
        latest_source_export_timestamp=latest_timestamp,
        blockers=tuple(_unique(blockers)),
        warnings=tuple(_unique(warnings)),
    )


def fetch_account_context(
    config: AppConfig,
    *,
    source: str,
    read_only: bool,
    provider: str = "generic",
    path: Path | None = None,
) -> AccountContextFetchResult:
    if not read_only:
        raise ValueError("fetch-account-context requires --read-only.")
    source_key = source.strip().lower()
    if source_key == "file":
        if path is None:
            raise ValueError("fetch-account-context --source file requires --file PATH.")
        result = normalize_account_export(config, provider=provider, path=path)
        warnings = _warnings_with_missing_ticker_staging(config, result.warnings)
        return AccountContextFetchResult(
            source="file",
            provider=result.provider,
            read_only=True,
            fetched=bool(result.output_files),
            input_path=result.input_path,
            output_files=result.output_files,
            position_rows=result.position_rows,
            cash_rows=result.cash_rows,
            option_position_rows=result.option_position_rows,
            warnings=warnings,
        )
    if source_key == "ibkr":
        result = _fetch_ibkr_account_context(config)
        return AccountContextFetchResult(
            source=result.source,
            provider=result.provider,
            read_only=result.read_only,
            fetched=result.fetched,
            input_path=result.input_path,
            output_files=result.output_files,
            position_rows=result.position_rows,
            cash_rows=result.cash_rows,
            option_position_rows=result.option_position_rows,
            warnings=_warnings_with_missing_ticker_staging(config, result.warnings),
        )
    raise ValueError(f"Unsupported account context source: {source}")


def _warnings_with_missing_ticker_staging(
    config: AppConfig,
    warnings: tuple[str, ...],
) -> tuple[str, ...]:
    staged_warnings = list(warnings)
    try:
        result = resolve_missing_tickers(config, source=SOURCE_ACCOUNT_CONTEXT)
    except Exception as error:
        staged_warnings.append(f"missing_ticker_resolver_failed:{error}")
        return tuple(_unique(staged_warnings))
    if result.ready_to_onboard_count:
        staged_warnings.append(
            f"missing_ticker_candidates_ready:{result.ready_to_onboard_count}"
        )
        staged_warnings.append(
            "account_apply_will_auto_onboard_missing_tickers"
        )
    if result.blocked_count:
        staged_warnings.append(
            f"missing_ticker_candidates_blocked:{result.blocked_count}"
        )
    return tuple(_unique(staged_warnings))


def normalize_account_export(
    config: AppConfig,
    *,
    provider: str,
    path: Path,
) -> AccountExportNormalizeResult:
    provider_key = _account_provider_key(provider)
    if provider_key not in {"generic", "ibkr", "ibkr-flex", "ibkr-activity"}:
        raise ValueError(f"Unsupported account export provider: {provider}")
    if not path.exists():
        raise FileNotFoundError(path)

    rows = list(csv.DictReader(path.read_text(encoding="utf-8-sig").splitlines()))
    positions: list[dict[str, str]] = []
    cash_rows: list[dict[str, str]] = []
    option_rows: list[dict[str, str]] = []
    warnings: list[str] = []
    skipped = 0
    for row_number, row in enumerate(rows, start=2):
        normalized = _normalize_export_row(row)
        if normalized.get("source") == "normalized_export":
            normalized["source"] = f"{provider_key}_export"
        kind = normalized.get("record_type", "").strip().lower()
        if not kind:
            kind = _infer_export_kind(normalized)
        if kind in {"portfolio_position", "position", "stock", "equity", "etf"}:
            positions.append(_project_row(normalized, POSITION_HEADERS))
        elif kind in {"portfolio_cash", "cash"}:
            cash_rows.append(_project_row(normalized, CASH_HEADERS))
        elif kind in {"option_position", "option", "options"}:
            option_rows.append(_project_row(normalized, OPTIONS_POSITION_HEADERS))
        else:
            skipped += 1
            warnings.append(f"{path.name}:row{row_number}:unsupported_record_type")

    output_files: list[Path] = []
    config.account_source_exports_dir.mkdir(parents=True, exist_ok=True)
    if positions:
        output_files.append(
            _write_rows(
                config.account_source_exports_dir
                / f"normalized_{provider_key}_portfolio_positions.csv",
                POSITION_HEADERS,
                positions,
            )
        )
    if cash_rows:
        output_files.append(
            _write_rows(
                config.account_source_exports_dir
                / f"normalized_{provider_key}_portfolio_cash.csv",
                CASH_HEADERS,
                cash_rows,
            )
        )
    if option_rows:
        output_files.append(
            _write_rows(
                config.account_source_exports_dir
                / f"normalized_{provider_key}_options_positions.csv",
                OPTIONS_POSITION_HEADERS,
                option_rows,
            )
        )
    return AccountExportNormalizeResult(
        provider=provider_key,
        input_path=path,
        output_files=tuple(output_files),
        position_rows=len(positions),
        cash_rows=len(cash_rows),
        option_position_rows=len(option_rows),
        skipped_rows=skipped,
        warnings=tuple(_unique(warnings)),
    )


def build_account_provider_status_text(
    config: AppConfig,
    *,
    check_connectivity: bool = True,
) -> str:
    status = account_provider_status(config, check_connectivity=check_connectivity)
    lines = [
        "Account Provider Status",
        f"Source export dir: {status.source_exports_dir}",
        f"Source export files: {status.source_export_files}",
        (
            "Valid rows: "
            f"positions={status.valid_position_rows}, "
            f"cash={status.valid_cash_rows}, "
            f"options={status.valid_option_position_rows}"
        ),
        f"IBKR available: {status.ibkr_available}",
        f"IBKR connected: {status.ibkr_connected}",
        f"IBKR endpoint: {status.ibkr_host}:{status.ibkr_port}",
        f"IBKR managed accounts: {status.ibkr_managed_account_count}",
        f"Latest source export timestamp: {status.latest_source_export_timestamp or 'none'}",
        f"Blockers: {', '.join(status.blockers) if status.blockers else 'none'}",
    ]
    if status.warnings:
        lines.append("Warnings: " + ", ".join(status.warnings))
    return "\n".join(lines)


def build_account_context_fetch_text(result: AccountContextFetchResult, config: AppConfig) -> str:
    lines = [
        "Account Context Fetch",
        f"Source: {result.source}",
        f"Provider: {result.provider}",
        f"Read only: {result.read_only}",
        f"Fetched rows: {result.fetched}",
    ]
    if result.input_path:
        lines.append(f"Input: {result.input_path}")
    lines.append(
        "Rows: "
        f"positions={result.position_rows}, cash={result.cash_rows}, "
        f"options={result.option_position_rows}"
    )
    if result.output_files:
        lines.append("Output files:")
        for path in result.output_files:
            lines.append(f"- {path}")
    if result.warnings:
        lines.append("Warnings: " + ", ".join(result.warnings))
    return "\n".join(lines)


def _fetch_ibkr_account_context(config: AppConfig) -> AccountContextFetchResult:
    EClient, Contract, EWrapper, import_error = _import_ibapi()
    if import_error:
        return AccountContextFetchResult(
            source="ibkr",
            provider="ibkr",
            read_only=True,
            fetched=False,
            input_path=None,
            output_files=(),
            position_rows=0,
            cash_rows=0,
            option_position_rows=0,
            warnings=(f"ibapi_unavailable:{import_error}",),
        )

    class AccountApp(EWrapper, EClient):  # type: ignore[misc, valid-type]
        def __init__(self) -> None:
            EClient.__init__(self, self)
            self.position_rows: list[dict[str, str]] = []
            self.option_rows: list[dict[str, str]] = []
            self.cash_candidates: dict[tuple[str, str], tuple[int, dict[str, str]]] = {}
            self.positions_done = False
            self.summary_done = False
            self.warnings: list[str] = []

        def nextValidId(self, orderId: int) -> None:
            self.reqPositions()
            self.reqAccountSummary(
                8101,
                "All",
                "TotalCashValue,CashBalance,SettledCash,AccruedCash",
            )

        def position(self, account: str, contract: Any, position: float, avgCost: float) -> None:
            if position == 0:
                return
            sec_type = str(getattr(contract, "secType", "") or "").upper()
            symbol = _tom_symbol_from_ibkr(str(getattr(contract, "symbol", "") or ""))
            currency = str(getattr(contract, "currency", "") or config.portfolio_base_currency).upper()
            today = date.today().isoformat()
            if sec_type in {"STK", "ETF"}:
                asset_type = "etf" if sec_type == "ETF" else "equity"
                self.position_rows.append(
                    {
                        "ticker": symbol,
                        "quantity": _format_number(position),
                        "account": account or "ibkr",
                        "position_date": today,
                        "currency": currency,
                        "cost_basis_per_share": _format_number(abs(avgCost)) if avgCost else "",
                        "asset_type": asset_type,
                        "source": "ibkr_account_snapshot",
                        "source_url": "ibkr://read-only-account-context",
                        "as_of_date": today,
                        "effective_date": today,
                    }
                )
            elif sec_type == "OPT":
                right = str(getattr(contract, "right", "") or "").upper()
                if right != "P" or position >= 0:
                    self.warnings.append(f"{symbol}:unsupported_option_position")
                    return
                expiration = _ibkr_expiry_to_date(
                    str(getattr(contract, "lastTradeDateOrContractMonth", "") or "")
                )
                strike = getattr(contract, "strike", None)
                self.option_rows.append(
                    {
                        "ticker": symbol,
                        "open_date": today,
                        "expiration_date": expiration,
                        "option_type": "put",
                        "side": "short_put",
                        "strike": _format_number(strike),
                        "contracts": _format_number(abs(position)),
                        "premium": _format_number(abs(avgCost)) if avgCost else "",
                        "account": account or "ibkr",
                        "status": "open",
                        "source": "ibkr_account_snapshot",
                        "source_url": "ibkr://read-only-account-context",
                        "as_of_date": today,
                        "effective_date": today,
                        "notes": "read-only IBKR position snapshot; premium uses average cost when available",
                    }
                )
            else:
                self.warnings.append(f"{symbol or 'unknown'}:unsupported_ibkr_sec_type:{sec_type or 'blank'}")

        def positionEnd(self) -> None:
            self.positions_done = True

        def accountSummary(
            self,
            reqId: int,
            account: str,
            tag: str,
            value: str,
            currency: str,
        ) -> None:
            priority = {"TotalCashValue": 0, "CashBalance": 1, "SettledCash": 2, "AccruedCash": 3}
            if tag not in priority:
                return
            if not currency or currency.upper() == "BASE":
                currency = config.portfolio_base_currency
            key = (account or "ibkr", currency.upper())
            row = {
                "account": account or "ibkr",
                "cash_date": date.today().isoformat(),
                "currency": currency.upper(),
                "cash_amount": value,
                "source": "ibkr_account_snapshot",
                "source_url": "ibkr://read-only-account-context",
                "as_of_date": date.today().isoformat(),
                "effective_date": date.today().isoformat(),
                "notes": f"IBKR account summary tag {tag}",
            }
            current = self.cash_candidates.get(key)
            if current is None or priority[tag] < current[0]:
                self.cash_candidates[key] = (priority[tag], row)

        def accountSummaryEnd(self, reqId: int) -> None:
            self.summary_done = True

        def error(
            self,
            reqId: int,
            errorCode: int,
            errorString: str,
            advancedOrderRejectJson: str = "",
        ) -> None:
            if not _is_info_error(int(errorCode)):
                self.warnings.append(f"{errorCode}:{errorString}")

    port = config.ibkr_paper_port
    app = AccountApp()
    try:
        app.connect(config.ibkr_host, port, clientId=config.ibkr_client_id + 71)
    except Exception as error:
        return AccountContextFetchResult(
            source="ibkr",
            provider="ibkr",
            read_only=True,
            fetched=False,
            input_path=None,
            output_files=(),
            position_rows=0,
            cash_rows=0,
            option_position_rows=0,
            warnings=(f"ibkr_not_connected:{error}",),
        )

    thread = threading.Thread(target=app.run, daemon=True)
    thread.start()
    deadline = time.time() + config.ibkr_timeout_seconds
    while time.time() < deadline:
        if app.positions_done and app.summary_done:
            break
        time.sleep(0.1)
    try:
        app.cancelAccountSummary(8101)
        app.cancelPositions()
    except Exception:
        pass
    app.disconnect()
    time.sleep(0.1)

    cash_rows = [row for _priority, row in app.cash_candidates.values()]
    output_files: list[Path] = []
    config.account_source_exports_dir.mkdir(parents=True, exist_ok=True)
    if app.position_rows:
        output_files.append(
            _write_rows(
                config.account_source_exports_dir / "ibkr_read_only_portfolio_positions.csv",
                POSITION_HEADERS,
                app.position_rows,
            )
        )
    if cash_rows:
        output_files.append(
            _write_rows(
                config.account_source_exports_dir / "ibkr_read_only_portfolio_cash.csv",
                CASH_HEADERS,
                cash_rows,
            )
        )
    if app.option_rows:
        output_files.append(
            _write_rows(
                config.account_source_exports_dir / "ibkr_read_only_options_positions.csv",
                OPTIONS_POSITION_HEADERS,
                app.option_rows,
            )
        )

    warnings = list(app.warnings)
    if not app.positions_done:
        warnings.append("ibkr_positions_timeout")
    if not app.summary_done:
        warnings.append("ibkr_account_summary_timeout")
    if not output_files:
        warnings.append("no_ibkr_account_context_rows")

    return AccountContextFetchResult(
        source="ibkr",
        provider="ibkr",
        read_only=True,
        fetched=bool(output_files),
        input_path=None,
        output_files=tuple(output_files),
        position_rows=len(app.position_rows),
        cash_rows=len(cash_rows),
        option_position_rows=len(app.option_rows),
        warnings=tuple(_unique(warnings)),
    )


def _account_provider_key(provider: str) -> str:
    return provider.strip().lower().replace("_", "-")


def datetime_from_timestamp(timestamp: float) -> str:
    from datetime import datetime

    return datetime.fromtimestamp(timestamp).isoformat(timespec="seconds")


def _tom_symbol_from_ibkr(symbol: str) -> str:
    return normalize_ticker(symbol.replace(" ", "."))


def _ibkr_expiry_to_date(value: str) -> str:
    text = value.strip()
    if len(text) >= 8 and text[:8].isdigit():
        return f"{text[:4]}-{text[4:6]}-{text[6:8]}"
    return text


def _format_number(value: object) -> str:
    if value is None:
        return ""
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return str(value)
    if numeric.is_integer():
        return str(int(numeric))
    return f"{numeric:.6f}".rstrip("0").rstrip(".")


def _ensure_template(path: Path, headers: tuple[str, ...]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists() or not path.read_text(encoding="utf-8-sig").strip():
        path.write_text(",".join(headers) + "\n", encoding="utf-8")
    return path


def _account_context_files(config: AppConfig) -> tuple[tuple[Path, str], ...]:
    files: list[tuple[Path, str]] = [
        (config.portfolio_positions_path, "portfolio_position"),
        (config.portfolio_cash_path, "portfolio_cash"),
        (config.options_positions_path, "option_position"),
    ]
    if config.account_source_exports_dir.exists():
        for path in sorted(config.account_source_exports_dir.glob("*.csv")):
            kind = _classify_account_file(path)
            if kind:
                files.append((path, kind))
    return tuple(files)


def _classify_account_file(path: Path) -> str | None:
    try:
        reader = csv.DictReader(path.read_text(encoding="utf-8-sig").splitlines())
    except UnicodeDecodeError:
        return None
    headers = set(reader.fieldnames or [])
    if set(OPTIONS_POSITION_HEADERS).issubset(headers):
        return "option_position"
    if set(POSITION_HEADERS).issubset(headers):
        return "portfolio_position"
    if set(CASH_HEADERS).issubset(headers):
        return "portfolio_cash"
    return None


def _read_rows_for_kind(path: Path, kind: str) -> tuple[list[dict[str, str]], int, list[str]]:
    reader = csv.DictReader(path.read_text(encoding="utf-8-sig").splitlines())
    rows: list[dict[str, str]] = []
    errors: list[str] = []
    blank_count = 0
    for row_number, row in enumerate(reader, start=2):
        if not any((value or "").strip() for value in row.values()):
            blank_count += 1
            continue
        errors.extend(_metadata_errors(path, row_number, row, kind))
        payload = dict(row)
        payload["_source_file"] = path.name
        payload["_source_row"] = str(row_number)
        rows.append(payload)
    return rows, blank_count, errors


def _metadata_errors(
    path: Path,
    row_number: int,
    row: dict[str, str],
    kind: str,
) -> list[str]:
    prefix = f"{path.name}:row{row_number}"
    errors: list[str] = []
    if not _has_value(row, "account"):
        errors.append(f"{prefix}:missing_account")
    if not _has_value(row, "source"):
        errors.append(f"{prefix}:missing_source")
    if kind == "portfolio_position" and not _has_value(row, "position_date"):
        errors.append(f"{prefix}:missing_position_date")
    if kind == "portfolio_cash" and not _has_value(row, "cash_date"):
        errors.append(f"{prefix}:missing_cash_date")
    return errors


def _validate_portfolio_positions(
    config: AppConfig,
    rows: list[dict[str, str]],
) -> tuple[int, set[str], list[str]]:
    if not rows:
        return 0, set(), []
    errors: list[str] = []
    valid_rows = 0
    tickers: set[str] = set()
    for row in rows:
        path = row.get("_source_file", "portfolio_positions")
        row_number = row.get("_source_row", "?")
        try:
            parsed = parse_portfolio_positions_csv(
                _csv_text(POSITION_HEADERS, [_project_row(row, POSITION_HEADERS)])
            )
            ticker = parsed[0].ticker if parsed else ""
            asset = latest_asset(config.database_path, ticker)
            if asset is None or asset.active_flag != 1:
                from .missing_tickers import record_missing_ticker_candidate_from_account_row

                record_missing_ticker_candidate_from_account_row(
                    config,
                    row,
                    str(path),
                    str(row_number),
                )
                raise ValueError(f"unsupported or inactive ticker: {ticker}")
            valid_rows += 1
            tickers.add(ticker)
        except Exception as error:
            errors.append(f"{path}:row{row_number}:{error}")
    return valid_rows, tickers, errors


def _validate_portfolio_cash(rows: list[dict[str, str]]) -> tuple[int, list[str]]:
    if not rows:
        return 0, []
    errors: list[str] = []
    valid_rows = 0
    for row in rows:
        path = row.get("_source_file", "portfolio_cash")
        row_number = row.get("_source_row", "?")
        try:
            parse_portfolio_cash_csv(_csv_text(CASH_HEADERS, [_project_row(row, CASH_HEADERS)]))
            valid_rows += 1
        except Exception as error:
            errors.append(f"{path}:row{row_number}:{error}")
    return valid_rows, errors


def _validate_option_positions(
    config: AppConfig,
    rows: list[dict[str, str]],
) -> tuple[int, set[str], list[str]]:
    if not rows:
        return 0, set(), []
    errors: list[str] = []
    valid_rows = 0
    tickers: set[str] = set()
    for row in rows:
        path = row.get("_source_file", "options_positions")
        row_number = row.get("_source_row", "?")
        try:
            parsed = parse_options_positions_csv(
                _csv_text(OPTIONS_POSITION_HEADERS, [_project_row(row, OPTIONS_POSITION_HEADERS)]),
                config,
            )
            valid_rows += 1
            if parsed:
                tickers.add(parsed[0].ticker)
        except Exception as error:
            errors.append(f"{path}:row{row_number}:{error}")
    return valid_rows, tickers, errors


def _incoming_keys(
    config: AppConfig,
) -> tuple[set[tuple[str, ...]], set[tuple[str, ...]], set[str]]:
    position_keys: set[tuple[str, ...]] = set()
    cash_keys: set[tuple[str, ...]] = set()
    option_keys: set[str] = set()
    for path, kind in _account_context_files(config):
        rows, _, _ = _read_rows_for_kind(path, kind)
        if kind == "portfolio_position":
            for row in rows:
                try:
                    parsed = parse_portfolio_positions_csv(
                        _csv_text(POSITION_HEADERS, [_project_row(row, POSITION_HEADERS)])
                    )
                    if parsed:
                        position = parsed[0]
                        position_keys.add(
                            (
                                position.account or "default",
                                position.ticker,
                                position.position_date or "",
                            )
                        )
                except Exception:
                    continue
        elif kind == "portfolio_cash":
            for row in rows:
                try:
                    parsed = parse_portfolio_cash_csv(
                        _csv_text(CASH_HEADERS, [_project_row(row, CASH_HEADERS)])
                    )
                    if parsed:
                        cash = parsed[0]
                        cash_keys.add(
                            (
                                cash.account or "default",
                                cash.currency or "",
                                cash.cash_date or "",
                            )
                        )
                except Exception:
                    continue
        elif kind == "option_position":
            for row in rows:
                try:
                    parsed = parse_options_positions_csv(
                        _csv_text(
                            OPTIONS_POSITION_HEADERS,
                            [_project_row(row, OPTIONS_POSITION_HEADERS)],
                        ),
                        config,
                    )
                    if parsed:
                        option_keys.add(parsed[0].position_key)
                except Exception:
                    continue
    return position_keys, cash_keys, option_keys


def _current_portfolio_position_keys(config: AppConfig) -> set[tuple[str, ...]]:
    return {
        (position.account or "default", position.ticker, position.position_date or "")
        for position in list_portfolio_positions(config.database_path)
    }


def _current_portfolio_cash_keys(config: AppConfig) -> set[tuple[str, ...]]:
    return {
        (cash.account or "default", cash.currency or "", cash.cash_date or "")
        for cash in list_portfolio_cash(config.database_path)
    }


def _current_option_position_keys(config: AppConfig) -> set[str]:
    return {position.position_key for position in list_option_positions(config.database_path)}


def _missing_portfolio_context_risk_rows(config: AppConfig) -> int:
    return sum(
        1
        for review in list_option_risk_reviews(config.database_path)
        if review.risk_category == "portfolio_context_needed"
        or "missing_portfolio_context" in (review.risk_warnings or "")
    )


def _merge_valid_rows_into_manual_files(config: AppConfig) -> None:
    position_rows: list[dict[str, str]] = []
    cash_rows: list[dict[str, str]] = []
    option_rows: list[dict[str, str]] = []
    for path, kind in _account_context_files(config):
        rows, _, _ = _read_rows_for_kind(path, kind)
        if path in {
            config.portfolio_positions_path,
            config.portfolio_cash_path,
            config.options_positions_path,
        }:
            continue
        if kind == "portfolio_position":
            position_rows.extend(_project_row(row, POSITION_HEADERS) for row in rows)
        elif kind == "portfolio_cash":
            cash_rows.extend(_project_row(row, CASH_HEADERS) for row in rows)
        elif kind == "option_position":
            option_rows.extend(_project_row(row, OPTIONS_POSITION_HEADERS) for row in rows)

    if position_rows:
        _merge_csv_rows(
            config.portfolio_positions_path,
            POSITION_HEADERS,
            position_rows,
            key_fields=("account", "ticker", "position_date"),
        )
    if cash_rows:
        _merge_csv_rows(
            config.portfolio_cash_path,
            CASH_HEADERS,
            cash_rows,
            key_fields=("account", "currency", "cash_date"),
        )
    if option_rows:
        _merge_csv_rows(
            config.options_positions_path,
            OPTIONS_POSITION_HEADERS,
            option_rows,
            key_fields=(
                "position_id",
                "account",
                "ticker",
                "open_date",
                "expiration_date",
                "option_type",
                "side",
                "strike",
                "contracts",
                "premium",
            ),
        )


def _merge_csv_rows(
    path: Path,
    headers: tuple[str, ...],
    rows: list[dict[str, str]],
    *,
    key_fields: tuple[str, ...],
) -> None:
    existing_rows = _read_existing_projected_rows(path, headers)
    by_key: dict[tuple[str, ...], dict[str, str]] = {}
    for row in existing_rows + rows:
        if not any((value or "").strip() for value in row.values()):
            continue
        key = tuple((row.get(field) or "").strip() for field in key_fields)
        by_key[key] = {header: row.get(header, "") for header in headers}
    _write_rows(path, headers, list(by_key.values()))


def _read_existing_projected_rows(path: Path, headers: tuple[str, ...]) -> list[dict[str, str]]:
    if not path.exists():
        return []
    reader = csv.DictReader(path.read_text(encoding="utf-8-sig").splitlines())
    return [_project_row(row, headers) for row in reader]


def _write_rows(path: Path, headers: tuple[str, ...], rows: list[dict[str, str]]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=headers)
        writer.writeheader()
        for row in rows:
            writer.writerow({header: row.get(header, "") for header in headers})
    return path


def _csv_text(headers: tuple[str, ...], rows: list[dict[str, str]]) -> str:
    handle = StringIO()
    writer = csv.DictWriter(handle, fieldnames=headers)
    writer.writeheader()
    for row in rows:
        writer.writerow({header: row.get(header, "") for header in headers})
    return handle.getvalue()


def _project_row(row: dict[str, str], headers: tuple[str, ...]) -> dict[str, str]:
    return {header: _value(row, header) for header in headers}


def _has_value(row: dict[str, str], field: str) -> bool:
    return bool(_value(row, field).strip())


def _value(row: dict[str, str], field: str) -> str:
    wanted = field.strip().lower()
    for key, value in row.items():
        if key and key.strip().lower() == wanted:
            return (value or "").strip()
    return ""


def _normalize_export_row(row: dict[str, str]) -> dict[str, str]:
    aliases = {
        "record_type": ("record_type", "type", "asset_class", "category"),
        "account": ("account", "account_id", "account_name"),
        "ticker": ("ticker", "symbol", "underlying", "underlying_symbol"),
        "quantity": ("quantity", "qty", "position", "shares"),
        "cash_amount": ("cash_amount", "cash", "amount", "balance"),
        "currency": ("currency", "ccy"),
        "position_date": ("position_date", "date", "as_of_date", "report_date"),
        "cash_date": ("cash_date", "date", "as_of_date", "report_date"),
        "open_date": ("open_date", "trade_date", "date"),
        "expiration_date": ("expiration_date", "expiry", "expiration"),
        "option_type": ("option_type", "put_call", "right"),
        "side": ("side", "action", "position_side"),
        "strike": ("strike", "strike_price"),
        "contracts": ("contracts", "contract_count", "quantity"),
        "premium": ("premium", "open_price", "price", "credit"),
        "source": ("source", "provider"),
        "source_url": ("source_url", "url"),
        "notes": ("notes", "description"),
    }
    normalized: dict[str, str] = {}
    lowered = {key.strip().lower(): value for key, value in row.items() if key}
    for target, candidates in aliases.items():
        for candidate in candidates:
            if candidate in lowered and str(lowered[candidate] or "").strip():
                normalized[target] = str(lowered[candidate]).strip()
                break
    for key, value in row.items():
        if key:
            normalized.setdefault(key.strip().lower(), str(value or "").strip())
    if normalized.get("ticker"):
        normalized["ticker"] = normalize_ticker(normalized["ticker"])
    if not normalized.get("source"):
        normalized["source"] = "normalized_export"
    today = date.today().isoformat()
    if normalized.get("record_type", "").lower() in {"cash", "portfolio_cash"}:
        normalized.setdefault("cash_date", normalized.get("position_date", today))
    elif normalized.get("option_type") or normalized.get("expiration_date"):
        normalized.setdefault("open_date", normalized.get("position_date", today))
    else:
        normalized.setdefault("position_date", normalized.get("cash_date", today))
    return normalized


def _infer_export_kind(row: dict[str, str]) -> str:
    if row.get("option_type") or row.get("expiration_date") or row.get("strike"):
        return "option_position"
    if row.get("cash_amount") and not row.get("ticker"):
        return "portfolio_cash"
    if row.get("ticker") and row.get("quantity"):
        return "portfolio_position"
    return ""


def _unique(values: list[str] | tuple[str, ...]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(value for value in values if value))
