from __future__ import annotations

import csv
import json
import math
import tempfile
from dataclasses import dataclass
from datetime import date, datetime
from io import StringIO
from pathlib import Path

from .config import AppConfig
from .storage import (
    Asset,
    OptionChainSnapshot,
    OptionIncomeReview,
    OptionPositionLifecycleReview,
    OptionPositionLedger,
    OptionReviewOutcome,
    OptionRiskReview,
    insert_data_quality_check,
    latest_asset,
    latest_price_feature,
    latest_quote_snapshot,
    latest_range_snapshot,
    latest_option_review_outcome_id_for_income_review,
    latest_option_risk_review_id_for_income_review,
    list_option_risk_reviews,
    list_option_position_lifecycle_reviews,
    list_stored_option_income_reviews,
    list_assets,
    list_option_chain_snapshots,
    list_option_positions,
    list_option_review_outcomes,
    list_prices,
    list_trader_commentary_claims,
    normalize_asset_role,
    normalize_ticker,
    option_income_statuses,
    option_outcome_statuses,
    option_lifecycle_statuses,
    option_position_statuses,
    option_risk_statuses,
    portfolio_statuses,
    upsert_option_chain_snapshot,
    upsert_option_income_review,
    upsert_option_position,
    upsert_option_position_lifecycle_review,
    upsert_option_review_outcome,
    upsert_option_risk_review,
)


OPTIONS_CHAIN_HEADERS = (
    "ticker",
    "snapshot_timestamp",
    "expiration_date",
    "option_type",
    "strike",
    "bid",
    "ask",
    "last",
    "mark",
    "volume",
    "open_interest",
    "implied_volatility",
    "delta",
    "gamma",
    "theta",
    "vega",
    "source",
    "source_url",
    "as_of_date",
    "effective_date",
)
REQUIRED_OPTIONS_CHAIN_COLUMNS = {
    "ticker",
    "snapshot_timestamp",
    "expiration_date",
    "option_type",
    "strike",
    "bid",
    "ask",
}
OPTIONS_CHAIN_NON_ACTIONABLE_FILENAME = "options_chain_non_actionable.csv"
OPTIONS_CHAIN_NON_ACTIONABLE_HEADERS = (
    "ticker",
    "decision_date",
    "reason_code",
    "source",
    "source_url",
    "as_of_date",
    "effective_date",
    "notes",
)
ALLOWED_OPTIONS_CHAIN_NON_ACTIONABLE_REASONS = (
    "no_listed_options",
    "not_options_strategy_candidate",
)
OPTION_MULTIPLIER = 100
MINIMUM_OPTION_CHAIN_TICKERS = ("SOXL", "KORU", "AAPL")
OPTIONS_POSITION_HEADERS = (
    "position_id",
    "ticker",
    "open_date",
    "expiration_date",
    "option_type",
    "side",
    "strike",
    "contracts",
    "premium",
    "close_date",
    "close_price",
    "assigned_flag",
    "assignment_price",
    "fees",
    "account",
    "status",
    "roll_from_position_id",
    "roll_to_position_id",
    "underlying_assignment_date",
    "underlying_shares",
    "underlying_cost_basis",
    "tags",
    "source",
    "source_url",
    "notes",
    "as_of_date",
    "effective_date",
)
REQUIRED_OPTIONS_POSITION_COLUMNS = {
    "ticker",
    "open_date",
    "expiration_date",
    "option_type",
    "side",
    "strike",
    "contracts",
    "premium",
}


@dataclass(frozen=True)
class OptionsChainLoadResult:
    path: Path
    row_count: int
    loaded_count: int
    skipped_count: int
    tickers: tuple[str, ...]
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class OptionsPositionLoadResult:
    path: Path
    row_count: int
    loaded_count: int
    skipped_count: int
    tickers: tuple[str, ...]
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class OptionChainFetchTickerResult:
    ticker: str
    status: str
    rows_loaded: int
    selected_expirations: int = 0
    selected_strikes: int = 0
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class OptionChainFetchResult:
    source: str
    results: tuple[OptionChainFetchTickerResult, ...]
    cache_dir: Path | None = None

    @property
    def loaded_count(self) -> int:
        return sum(result.rows_loaded for result in self.results)

    @property
    def warning_count(self) -> int:
        return sum(1 for result in self.results if result.warnings)

    @property
    def skipped_count(self) -> int:
        return sum(1 for result in self.results if result.status in {"cached", "skipped"})

    @property
    def tickers(self) -> tuple[str, ...]:
        return tuple(result.ticker for result in self.results)


@dataclass(frozen=True)
class OptionIncomeTickerResult:
    ticker: str
    status: str
    review_count: int
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class OptionIncomeComputeResult:
    results: tuple[OptionIncomeTickerResult, ...]

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
class OptionRiskTickerResult:
    ticker: str
    status: str
    review_count: int
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class OptionRiskComputeResult:
    results: tuple[OptionRiskTickerResult, ...]

    @property
    def computed_count(self) -> int:
        return sum(1 for result in self.results if result.review_count)

    @property
    def skipped_count(self) -> int:
        return sum(1 for result in self.results if result.status == "skipped")

    @property
    def warning_count(self) -> int:
        return sum(1 for result in self.results if result.warnings)


@dataclass(frozen=True)
class OptionOutcomeTickerResult:
    ticker: str
    status: str
    outcome_count: int
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class OptionOutcomeComputeResult:
    results: tuple[OptionOutcomeTickerResult, ...]

    @property
    def computed_count(self) -> int:
        return sum(1 for result in self.results if result.outcome_count)

    @property
    def skipped_count(self) -> int:
        return sum(1 for result in self.results if result.status == "skipped")

    @property
    def warning_count(self) -> int:
        return sum(1 for result in self.results if result.warnings)


@dataclass(frozen=True)
class OptionLifecycleTickerResult:
    ticker: str
    status: str
    lifecycle_count: int
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class OptionLifecycleComputeResult:
    results: tuple[OptionLifecycleTickerResult, ...]

    @property
    def computed_count(self) -> int:
        return sum(1 for result in self.results if result.lifecycle_count)

    @property
    def skipped_count(self) -> int:
        return sum(1 for result in self.results if result.status == "skipped")

    @property
    def warning_count(self) -> int:
        return sum(1 for result in self.results if result.warnings)


@dataclass(frozen=True)
class OptionProviderStatus:
    source: str
    ibkr_host: str
    ibkr_port: int
    ibkr_client_id: int
    ibapi_status: str
    ibapi_error: str | None
    ibkr_connectivity_status: str
    ibkr_warnings: tuple[str, ...]
    chain_rows: int
    review_rows: int
    fetch_universe_tickers: tuple[str, ...]
    missing_chain_tickers: tuple[str, ...]
    latest_chain_snapshot: str | None
    latest_review_date: str | None
    cache_dir: Path
    cache_exists: bool
    cache_file_count: int
    latest_cache_timestamp: str | None
    readiness_status: str
    blocked_reason: str | None
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class OptionsChainBackfillValidation:
    source_dir: Path
    source_export_files: tuple[Path, ...]
    valid_row_count: int
    invalid_row_count: int
    blank_placeholder_count: int
    valid_tickers: tuple[str, ...]
    invalid_reasons: tuple[str, ...]
    projected_loaded_ticker_count: int
    fetch_universe_ticker_count: int
    apply_ready: bool
    blocked_reason: str | None
    minimum_tickers: tuple[str, ...] = ()
    minimum_loaded_tickers: tuple[str, ...] = ()
    minimum_valid_tickers: tuple[str, ...] = ()
    minimum_projected_loaded_tickers: tuple[str, ...] = ()
    minimum_missing_tickers: tuple[str, ...] = ()
    minimum_projected_loaded_ticker_count: int = 0
    minimum_ticker_count: int = 0


@dataclass(frozen=True)
class OptionChainNonActionableDecision:
    ticker: str
    decision_date: str
    reason_code: str
    source: str
    source_url: str
    as_of_date: str | None
    effective_date: str | None
    notes: str | None


@dataclass(frozen=True)
class OptionChainNonActionableValidation:
    path: Path
    file_exists: bool
    valid_decision_count: int
    invalid_decision_count: int
    blank_placeholder_count: int
    valid_tickers: tuple[str, ...]
    invalid_reasons: tuple[str, ...]
    allowed_reason_codes: tuple[str, ...]
    notes: tuple[str, ...]
    decisions: tuple[OptionChainNonActionableDecision, ...] = ()


@dataclass(frozen=True)
class OptionChainAvailabilityStatus:
    ticker: str
    availability_status: str
    reason_code: str | None
    reason: str | None
    source: str | None
    source_url: str | None
    decision_date: str | None
    as_of_date: str | None
    effective_date: str | None
    raw_chain_available: bool
    effective_coverage_included: bool


@dataclass(frozen=True)
class OptionsChainBackfillImportResult:
    source_dir: Path
    source_export_files: tuple[Path, ...]
    imported_count: int
    valid_row_count: int
    invalid_row_count: int
    blank_placeholder_count: int
    tickers: tuple[str, ...]
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class OptionsChainBackfillExportResult:
    path: Path
    row_count: int
    tickers: tuple[str, ...]
    warnings: tuple[str, ...]
    non_actionable_path: Path | None = None


@dataclass(frozen=True)
class OptionChainActivationStatus:
    activation_status: str
    blocked_reason: str | None
    provider_status: OptionProviderStatus
    validation: OptionsChainBackfillValidation
    minimum_tickers: tuple[str, ...]
    minimum_loaded_tickers: tuple[str, ...]
    minimum_valid_tickers: tuple[str, ...]
    minimum_missing_tickers: tuple[str, ...]
    minimum_option_chain_coverage: str
    minimum_option_review_count: int
    ibapi_repair_needed: bool
    next_commands: tuple[str, ...]
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class OptionChainActivationResult:
    confirmed: bool
    allow_partial: bool
    success: bool
    status: str
    blocked_reason: str | None
    validation: OptionsChainBackfillValidation
    imported_count: int = 0
    computed_review_tickers: int = 0
    minimum_option_review_count: int = 0
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class OptionChainCoveragePlan:
    coverage_status: str
    current_loaded_ticker_count: int
    fetch_universe_ticker_count: int
    raw_fetch_universe_ticker_count: int
    effective_fetch_universe_ticker_count: int
    current_loaded_tickers: tuple[str, ...]
    missing_tickers: tuple[str, ...]
    raw_missing_tickers: tuple[str, ...]
    effective_missing_tickers: tuple[str, ...]
    prioritized_missing_tickers: tuple[str, ...]
    valid_backfill_tickers: tuple[str, ...]
    projected_loaded_ticker_count: int
    projected_missing_tickers: tuple[str, ...]
    non_actionable_tickers: tuple[str, ...]
    non_actionable_valid_decision_count: int
    non_actionable_invalid_decision_count: int
    non_actionable_blank_placeholder_count: int
    non_actionable_invalid_reasons: tuple[str, ...]
    non_actionable_template_path: Path
    raw_coverage_count: str
    effective_coverage_count: str
    notes: tuple[str, ...]
    apply_ready: bool
    blocked_reason: str | None
    provider_blocked_reason: str | None
    backfill_template_path: Path
    next_commands: tuple[str, ...]
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class OptionChainCoverageApplyResult:
    confirmed: bool
    allow_partial: bool
    success: bool
    status: str
    blocked_reason: str | None
    plan: OptionChainCoveragePlan
    imported_count: int = 0
    computed_income_tickers: int = 0
    computed_risk_tickers: int = 0
    computed_outcome_tickers: int = 0
    computed_lifecycle_tickers: int = 0
    warnings: tuple[str, ...] = ()


def _today() -> date:
    return date.today()


def _join_unique(values: list[str] | tuple[str, ...]) -> str | None:
    cleaned = [value for value in values if value]
    unique = tuple(dict.fromkeys(cleaned))
    return ", ".join(unique) if unique else None


def _parse_date(value: str | None, field_name: str, row_number: int) -> str:
    text = (value or "").strip()
    if not text:
        raise ValueError(f"Row {row_number}: missing required {field_name}.")
    try:
        return date.fromisoformat(text).isoformat()
    except ValueError as error:
        raise ValueError(f"Row {row_number}: malformed {field_name}: {text}") from error


def _parse_timestamp(value: str | None, row_number: int) -> str:
    text = (value or "").strip()
    if not text:
        raise ValueError(f"Row {row_number}: missing required snapshot_timestamp.")
    try:
        return datetime.fromisoformat(text).isoformat(timespec="seconds")
    except ValueError as error:
        raise ValueError(f"Row {row_number}: malformed snapshot_timestamp: {text}") from error


def _parse_optional_date(value: str | None, field_name: str, row_number: int) -> str | None:
    text = (value or "").strip()
    if not text:
        return None
    return _parse_date(text, field_name, row_number)


def _parse_float(
    value: str | None,
    field_name: str,
    row_number: int,
    *,
    allow_negative: bool = False,
) -> float | None:
    text = (value or "").strip().replace(",", "")
    if not text:
        return None
    try:
        parsed = float(text)
    except ValueError as error:
        raise ValueError(f"Row {row_number}: malformed {field_name}: {value}") from error
    if not allow_negative and parsed < 0:
        raise ValueError(f"Row {row_number}: {field_name} cannot be negative.")
    return parsed


def _normalize_option_type(value: str | None, row_number: int) -> str:
    cleaned = (value or "").strip().lower()
    if cleaned in {"p", "put"}:
        return "put"
    if cleaned in {"c", "call"}:
        return "call"
    raise ValueError(f"Row {row_number}: unsupported option_type: {value}")


def ensure_options_chain_csv_header(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists() or not path.read_text(encoding="utf-8-sig").strip():
        path.write_text(",".join(OPTIONS_CHAIN_HEADERS) + "\n", encoding="utf-8")
        return

    reader = csv.DictReader(path.read_text(encoding="utf-8-sig").splitlines())
    if reader.fieldnames and set(OPTIONS_CHAIN_HEADERS).issubset(reader.fieldnames):
        return
    rows = list(reader)
    with path.open("w", newline="", encoding="utf-8") as output:
        writer = csv.DictWriter(output, fieldnames=OPTIONS_CHAIN_HEADERS)
        writer.writeheader()
        for row in rows:
            writer.writerow({header: row.get(header, "") for header in OPTIONS_CHAIN_HEADERS})


def ensure_options_chain_non_actionable_csv_header(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists() or not path.read_text(encoding="utf-8-sig").strip():
        path.write_text(
            ",".join(OPTIONS_CHAIN_NON_ACTIONABLE_HEADERS) + "\n",
            encoding="utf-8",
        )
        return

    reader = csv.DictReader(path.read_text(encoding="utf-8-sig").splitlines())
    if reader.fieldnames and set(OPTIONS_CHAIN_NON_ACTIONABLE_HEADERS).issubset(
        reader.fieldnames
    ):
        return
    rows = list(reader)
    with path.open("w", newline="", encoding="utf-8") as output:
        writer = csv.DictWriter(output, fieldnames=OPTIONS_CHAIN_NON_ACTIONABLE_HEADERS)
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    header: row.get(header, "")
                    for header in OPTIONS_CHAIN_NON_ACTIONABLE_HEADERS
                }
            )


def ensure_options_positions_csv_header(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists() or not path.read_text(encoding="utf-8-sig").strip():
        path.write_text(",".join(OPTIONS_POSITION_HEADERS) + "\n", encoding="utf-8")
        return

    reader = csv.DictReader(path.read_text(encoding="utf-8-sig").splitlines())
    if reader.fieldnames and set(OPTIONS_POSITION_HEADERS).issubset(reader.fieldnames):
        return
    rows = list(reader)
    with path.open("w", newline="", encoding="utf-8") as output:
        writer = csv.DictWriter(output, fieldnames=OPTIONS_POSITION_HEADERS)
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {header: row.get(header, "") for header in OPTIONS_POSITION_HEADERS}
            )


def _normalize_position_side(value: str | None, row_number: int) -> str:
    cleaned = (value or "").strip().lower().replace("-", "_").replace(" ", "_")
    if cleaned in {"short_put", "sell_put", "short", "sell", "sell_to_open", "sto"}:
        return "short_put"
    raise ValueError(f"Row {row_number}: unsupported side: {value}")


def _parse_optional_flag(value: str | None) -> int | None:
    text = (value or "").strip().lower()
    if not text:
        return None
    if text in {"1", "true", "yes", "y", "assigned"}:
        return 1
    if text in {"0", "false", "no", "n", "not_assigned"}:
        return 0
    return None


def _position_status(
    expiration_date: str,
    close_date: str | None,
    assigned_flag: int | None,
    explicit_status: str | None = None,
) -> str:
    cleaned = (explicit_status or "").strip().lower().replace("-", "_").replace(" ", "_")
    if cleaned in {
        "open",
        "closed",
        "assigned",
        "rolled",
        "expired",
        "expired_worthless",
        "expired_or_pending_manual_close",
    }:
        return cleaned
    if assigned_flag:
        return "assigned"
    if close_date:
        return "closed"
    try:
        if date.fromisoformat(expiration_date) < _today():
            return "expired_or_pending_manual_close"
    except ValueError:
        pass
    return "open"


def _position_key(
    position_id: str | None,
    ticker: str,
    open_date: str,
    expiration_date: str,
    option_type: str,
    side: str,
    strike: float,
    contracts: float,
    premium: float,
    account: str | None,
    source: str,
) -> str:
    if position_id:
        return position_id
    return "|".join(
        (
            account or "default",
            ticker,
            open_date,
            expiration_date,
            option_type,
            side,
            f"{strike:.4f}",
            f"{contracts:.4f}",
            f"{premium:.4f}",
            source,
        )
    )


def parse_options_positions_csv(
    text: str,
    config: AppConfig,
) -> list[OptionPositionLedger]:
    reader = csv.DictReader(StringIO(text))
    if not reader.fieldnames:
        raise ValueError("Options positions CSV is missing a header row.")
    missing = REQUIRED_OPTIONS_POSITION_COLUMNS - set(reader.fieldnames)
    if missing:
        raise ValueError(
            "Options positions CSV missing required columns: "
            + ", ".join(sorted(missing))
        )

    positions: list[OptionPositionLedger] = []
    for row_number, row in enumerate(reader, start=2):
        if not any((value or "").strip() for value in row.values()):
            continue
        ticker = normalize_ticker(row.get("ticker", ""))
        if not ticker:
            raise ValueError(f"Row {row_number}: missing required ticker.")
        asset = latest_asset(config.database_path, ticker)
        if asset is None or asset.active_flag != 1:
            raise ValueError(f"Row {row_number}: unsupported or inactive ticker: {ticker}")
        option_type = _normalize_option_type(row.get("option_type"), row_number)
        side = _normalize_position_side(row.get("side"), row_number)
        strike = _parse_float(row.get("strike"), "strike", row_number)
        contracts = _parse_float(row.get("contracts"), "contracts", row_number)
        premium = _parse_float(row.get("premium"), "premium", row_number)
        if strike in (None, 0) or contracts in (None, 0) or premium is None:
            raise ValueError(
                f"Row {row_number}: strike, contracts, and premium are required."
            )
        open_date = _parse_date(row.get("open_date"), "open_date", row_number)
        expiration_date = _parse_date(
            row.get("expiration_date"),
            "expiration_date",
            row_number,
        )
        close_date = _parse_optional_date(row.get("close_date"), "close_date", row_number)
        assigned_flag = _parse_optional_flag(row.get("assigned_flag"))
        position_id = (row.get("position_id") or "").strip() or None
        source = (row.get("source") or "manual_csv").strip() or "manual_csv"
        account = (row.get("account") or "").strip() or None
        warnings: list[str] = ["read_only_position_ledger"]
        if normalize_asset_role(asset.asset_role) != "scoreable":
            warnings.append("reference_instrument_only")
        if option_type != "put" or side != "short_put":
            warnings.append("non_sell_put_position_not_scored")
        status = _position_status(
            expiration_date,
            close_date,
            assigned_flag,
            row.get("status"),
        )
        positions.append(
            OptionPositionLedger(
                position_key=_position_key(
                    position_id,
                    ticker,
                    open_date,
                    expiration_date,
                    option_type,
                    side,
                    strike,
                    contracts,
                    premium,
                    account,
                    source,
                ),
                position_id=position_id,
                ticker=ticker,
                open_date=open_date,
                expiration_date=expiration_date,
                option_type=option_type,
                side=side,
                strike=strike,
                contracts=contracts,
                premium=premium,
                close_date=close_date,
                close_price=_parse_float(row.get("close_price"), "close_price", row_number),
                assigned_flag=assigned_flag,
                assignment_price=_parse_float(
                    row.get("assignment_price"),
                    "assignment_price",
                    row_number,
                ),
                fees=_parse_float(row.get("fees"), "fees", row_number),
                account=account,
                position_status=status,
                roll_from_position_id=(row.get("roll_from_position_id") or "").strip() or None,
                roll_to_position_id=(row.get("roll_to_position_id") or "").strip() or None,
                underlying_assignment_date=_parse_optional_date(
                    row.get("underlying_assignment_date"),
                    "underlying_assignment_date",
                    row_number,
                ),
                underlying_shares=_parse_float(
                    row.get("underlying_shares"),
                    "underlying_shares",
                    row_number,
                ),
                underlying_cost_basis=_parse_float(
                    row.get("underlying_cost_basis"),
                    "underlying_cost_basis",
                    row_number,
                ),
                tags=(row.get("tags") or "").strip() or None,
                data_warnings=_join_unique(warnings),
                model_version=config.options_position_model_version,
                source=source,
                source_url=(row.get("source_url") or "").strip() or None,
                notes=(row.get("notes") or "").strip() or None,
                as_of_date=_parse_optional_date(row.get("as_of_date"), "as_of_date", row_number),
                effective_date=_parse_optional_date(
                    row.get("effective_date"),
                    "effective_date",
                    row_number,
                ),
            )
        )
    return positions


def load_options_positions_csv(
    config: AppConfig,
    path: Path | None = None,
) -> OptionsPositionLoadResult:
    positions_path = path or config.options_positions_path
    ensure_options_positions_csv_header(positions_path)
    positions = parse_options_positions_csv(
        positions_path.read_text(encoding="utf-8-sig"),
        config,
    )
    tickers: set[str] = set()
    for position in positions:
        upsert_option_position(config.database_path, position)
        tickers.add(position.ticker)
    warnings: list[str] = []
    if not positions:
        warnings.append("empty_options_positions")
    return OptionsPositionLoadResult(
        path=positions_path,
        row_count=len(positions),
        loaded_count=len(positions),
        skipped_count=0,
        tickers=tuple(sorted(tickers)),
        warnings=tuple(warnings),
    )


def _source_export_files(config: AppConfig, source_dir: Path | None = None) -> tuple[Path, ...]:
    directory = source_dir or config.options_chain_source_exports_dir
    if not directory.exists():
        return ()
    return tuple(
        sorted(
            path
            for path in directory.glob("*.csv")
            if path.is_file() and path.name != OPTIONS_CHAIN_NON_ACTIONABLE_FILENAME
        )
    )


def _cache_file_status(path: Path) -> tuple[int, str | None]:
    if not path.exists():
        return 0, None
    files = [item for item in path.rglob("*") if item.is_file()]
    if not files:
        return 0, None
    latest = max(item.stat().st_mtime for item in files)
    return len(files), datetime.fromtimestamp(latest).isoformat(timespec="seconds")


def _classify_import_error(error: str | None) -> str:
    if not error:
        return "ok"
    lowered = error.lower()
    if "permission" in lowered or "access is denied" in lowered:
        return "ibapi_permission_denied"
    if "no module named" in lowered or "cannot find" in lowered:
        return "ibapi_missing"
    return "ibapi_unavailable"


def _classify_warnings(warnings: tuple[str, ...]) -> str | None:
    joined = " | ".join(warnings).lower()
    if not joined:
        return None
    if "permission" in joined or "access is denied" in joined:
        return "ibapi_permission_denied"
    if "ibapi_unavailable" in joined:
        return "ibapi_missing" if "no module named" in joined else "ibapi_unavailable"
    if "connect_failed" in joined or "ibkr_unavailable" in joined:
        return "ibkr_not_connected"
    if "ibkr_option_subscription_missing" in joined:
        return "option_subscription_missing"
    if "missing_option_bid_ask" in joined:
        return "missing_bid_ask"
    if "stale_underlying_price" in joined:
        return "stale_underlying_price"
    return None


def minimum_option_chain_tickers(config: AppConfig) -> tuple[str, ...]:
    active_tickers = {
        asset.ticker for asset in list_assets(config.database_path) if asset.active_flag == 1
    }
    return tuple(ticker for ticker in MINIMUM_OPTION_CHAIN_TICKERS if ticker in active_tickers)


def _is_backfill_placeholder(row: dict[str, str | None]) -> bool:
    if not any((value or "").strip() for value in row.values()):
        return True
    if not (row.get("ticker") or "").strip():
        return False
    required_payload_fields = (
        "snapshot_timestamp",
        "expiration_date",
        "strike",
        "bid",
        "ask",
        "source",
        "source_url",
    )
    return not any((row.get(field) or "").strip() for field in required_payload_fields)


def _parse_options_source_export_row(
    row: dict[str, str | None],
    config: AppConfig,
    row_number: int,
    file_path: Path,
) -> OptionChainSnapshot:
    ticker = normalize_ticker(row.get("ticker", ""))
    if not ticker:
        raise ValueError(f"{file_path.name} row {row_number}: missing required ticker.")
    asset = latest_asset(config.database_path, ticker)
    if asset is None or asset.active_flag != 1:
        raise ValueError(f"{file_path.name} row {row_number}: unsupported or inactive ticker: {ticker}")
    source = (row.get("source") or "").strip()
    source_url = (row.get("source_url") or "").strip()
    if not source:
        raise ValueError(f"{file_path.name} row {row_number}: missing required source.")
    if not source_url:
        raise ValueError(f"{file_path.name} row {row_number}: missing required source_url.")

    strike = _parse_float(row.get("strike"), "strike", row_number)
    bid = _parse_float(row.get("bid"), "bid", row_number)
    ask = _parse_float(row.get("ask"), "ask", row_number)
    if strike in (None, 0) or bid is None or ask is None:
        raise ValueError(f"{file_path.name} row {row_number}: strike, bid, and ask are required.")
    if ask < bid:
        raise ValueError(f"{file_path.name} row {row_number}: ask cannot be below bid.")

    return OptionChainSnapshot(
        ticker=ticker,
        snapshot_timestamp=_parse_timestamp(row.get("snapshot_timestamp"), row_number),
        expiration_date=_parse_date(row.get("expiration_date"), "expiration_date", row_number),
        option_type=_normalize_option_type(row.get("option_type"), row_number),
        strike=strike,
        bid=bid,
        ask=ask,
        last=_parse_float(row.get("last"), "last", row_number),
        mark=_parse_float(row.get("mark"), "mark", row_number),
        volume=_parse_float(row.get("volume"), "volume", row_number),
        open_interest=_parse_float(row.get("open_interest"), "open_interest", row_number),
        implied_volatility=_parse_float(
            row.get("implied_volatility"),
            "implied_volatility",
            row_number,
        ),
        delta=_parse_float(row.get("delta"), "delta", row_number, allow_negative=True),
        gamma=_parse_float(row.get("gamma"), "gamma", row_number, allow_negative=True),
        theta=_parse_float(row.get("theta"), "theta", row_number, allow_negative=True),
        vega=_parse_float(row.get("vega"), "vega", row_number, allow_negative=True),
        source=source,
        source_url=source_url,
        as_of_date=_parse_optional_date(row.get("as_of_date"), "as_of_date", row_number),
        effective_date=_parse_optional_date(
            row.get("effective_date"),
            "effective_date",
            row_number,
        ),
    )


def _read_options_source_export_rows(
    config: AppConfig,
    file_path: Path,
) -> tuple[list[OptionChainSnapshot], int, list[str]]:
    reader = csv.DictReader(file_path.read_text(encoding="utf-8-sig").splitlines())
    if not reader.fieldnames:
        return [], 0, [f"{file_path.name}: missing header row"]
    missing = REQUIRED_OPTIONS_CHAIN_COLUMNS - set(reader.fieldnames)
    missing = missing | {"source", "source_url"} - set(reader.fieldnames)
    if missing:
        return [], 0, [
            f"{file_path.name}: missing required columns: {', '.join(sorted(missing))}"
        ]

    rows: list[OptionChainSnapshot] = []
    blank_placeholders = 0
    invalid_reasons: list[str] = []
    for row_number, row in enumerate(reader, start=2):
        if _is_backfill_placeholder(row):
            blank_placeholders += 1
            continue
        try:
            rows.append(_parse_options_source_export_row(row, config, row_number, file_path))
        except ValueError as error:
            invalid_reasons.append(str(error))
    return rows, blank_placeholders, invalid_reasons


def _non_actionable_path(config: AppConfig, source_dir: Path | None = None) -> Path:
    directory = source_dir or config.options_chain_source_exports_dir
    return directory / OPTIONS_CHAIN_NON_ACTIONABLE_FILENAME


def _is_non_actionable_placeholder(row: dict[str, str | None]) -> bool:
    if not any((value or "").strip() for value in row.values()):
        return True
    if not (row.get("ticker") or "").strip():
        return False
    decision_fields = ("decision_date", "reason_code", "source", "source_url")
    return not any((row.get(field) or "").strip() for field in decision_fields)


def _parse_non_actionable_decision(
    row: dict[str, str | None],
    config: AppConfig,
    row_number: int,
    file_path: Path,
    fetch_tickers: set[str],
) -> OptionChainNonActionableDecision:
    ticker = normalize_ticker(row.get("ticker", ""))
    if not ticker:
        raise ValueError(f"{file_path.name} row {row_number}: missing required ticker.")
    asset = latest_asset(config.database_path, ticker)
    if asset is None or asset.active_flag != 1:
        raise ValueError(f"{file_path.name} row {row_number}: unsupported or inactive ticker: {ticker}")
    if ticker not in fetch_tickers:
        raise ValueError(
            f"{file_path.name} row {row_number}: ticker_not_in_options_fetch_universe:{ticker}"
        )

    reason_code = (row.get("reason_code") or "").strip().lower()
    if reason_code not in ALLOWED_OPTIONS_CHAIN_NON_ACTIONABLE_REASONS:
        allowed = ", ".join(ALLOWED_OPTIONS_CHAIN_NON_ACTIONABLE_REASONS)
        raise ValueError(
            f"{file_path.name} row {row_number}: unsupported reason_code: "
            f"{reason_code or 'missing'}; allowed: {allowed}"
        )
    source = (row.get("source") or "").strip()
    source_url = (row.get("source_url") or "").strip()
    if not source:
        raise ValueError(f"{file_path.name} row {row_number}: missing required source.")
    if not source_url:
        raise ValueError(f"{file_path.name} row {row_number}: missing required source_url.")

    try:
        decision_date = _parse_date(row.get("decision_date"), "decision_date", row_number)
        as_of_date = _parse_optional_date(row.get("as_of_date"), "as_of_date", row_number)
        effective_date = _parse_optional_date(
            row.get("effective_date"),
            "effective_date",
            row_number,
        )
    except ValueError as error:
        raise ValueError(f"{file_path.name} {error}") from error

    return OptionChainNonActionableDecision(
        ticker=ticker,
        decision_date=decision_date,
        reason_code=reason_code,
        source=source,
        source_url=source_url,
        as_of_date=as_of_date,
        effective_date=effective_date,
        notes=(row.get("notes") or "").strip() or None,
    )


def validate_option_chain_non_actionable_decisions(
    config: AppConfig,
    source_dir: Path | None = None,
) -> OptionChainNonActionableValidation:
    path = _non_actionable_path(config, source_dir=source_dir)
    fetch_tickers = {
        asset.ticker for asset in option_fetch_assets(config, max_tickers=0)
    }
    if not path.exists():
        return OptionChainNonActionableValidation(
            path=path,
            file_exists=False,
            valid_decision_count=0,
            invalid_decision_count=0,
            blank_placeholder_count=0,
            valid_tickers=(),
            invalid_reasons=(),
            allowed_reason_codes=ALLOWED_OPTIONS_CHAIN_NON_ACTIONABLE_REASONS,
            notes=(),
        )

    reader = csv.DictReader(path.read_text(encoding="utf-8-sig").splitlines())
    if not reader.fieldnames:
        return OptionChainNonActionableValidation(
            path=path,
            file_exists=True,
            valid_decision_count=0,
            invalid_decision_count=1,
            blank_placeholder_count=0,
            valid_tickers=(),
            invalid_reasons=(f"{path.name}: missing header row",),
            allowed_reason_codes=ALLOWED_OPTIONS_CHAIN_NON_ACTIONABLE_REASONS,
            notes=(),
        )
    missing = set(OPTIONS_CHAIN_NON_ACTIONABLE_HEADERS) - set(reader.fieldnames)
    if missing:
        return OptionChainNonActionableValidation(
            path=path,
            file_exists=True,
            valid_decision_count=0,
            invalid_decision_count=1,
            blank_placeholder_count=0,
            valid_tickers=(),
            invalid_reasons=(
                f"{path.name}: missing required columns: {', '.join(sorted(missing))}",
            ),
            allowed_reason_codes=ALLOWED_OPTIONS_CHAIN_NON_ACTIONABLE_REASONS,
            notes=(),
        )

    decisions: list[OptionChainNonActionableDecision] = []
    blanks = 0
    invalid_reasons: list[str] = []
    for row_number, row in enumerate(reader, start=2):
        if _is_non_actionable_placeholder(row):
            blanks += 1
            continue
        try:
            decisions.append(
                _parse_non_actionable_decision(
                    row,
                    config,
                    row_number,
                    path,
                    fetch_tickers,
                )
            )
        except ValueError as error:
            invalid_reasons.append(str(error))

    valid_tickers = tuple(sorted({decision.ticker for decision in decisions}))
    notes = ("non_actionable_option_chain_excluded",) if valid_tickers else ()
    return OptionChainNonActionableValidation(
        path=path,
        file_exists=True,
        valid_decision_count=len(decisions),
        invalid_decision_count=len(invalid_reasons),
        blank_placeholder_count=blanks,
        valid_tickers=valid_tickers,
        invalid_reasons=tuple(invalid_reasons),
        allowed_reason_codes=ALLOWED_OPTIONS_CHAIN_NON_ACTIONABLE_REASONS,
        notes=notes,
        decisions=tuple(decisions),
    )


def valid_non_actionable_option_chain_tickers(config: AppConfig) -> tuple[str, ...]:
    return validate_option_chain_non_actionable_decisions(config).valid_tickers


def option_chain_availability_statuses(config: AppConfig) -> tuple[OptionChainAvailabilityStatus, ...]:
    non_actionable = validate_option_chain_non_actionable_decisions(config)
    decisions_by_ticker = {decision.ticker: decision for decision in non_actionable.decisions}
    loaded_tickers = set(_option_chain_loaded_tickers(config))
    statuses: list[OptionChainAvailabilityStatus] = []
    for asset in option_fetch_assets(config, max_tickers=0):
        ticker = asset.ticker
        decision = decisions_by_ticker.get(ticker)
        raw_available = ticker in loaded_tickers
        if decision is not None:
            statuses.append(
                OptionChainAvailabilityStatus(
                    ticker=ticker,
                    availability_status="unavailable",
                    reason_code=decision.reason_code,
                    reason=decision.notes or decision.reason_code,
                    source=decision.source,
                    source_url=decision.source_url,
                    decision_date=decision.decision_date,
                    as_of_date=decision.as_of_date,
                    effective_date=decision.effective_date,
                    raw_chain_available=raw_available,
                    effective_coverage_included=False,
                )
            )
        elif raw_available:
            statuses.append(
                OptionChainAvailabilityStatus(
                    ticker=ticker,
                    availability_status="available",
                    reason_code="option_chain_rows_loaded",
                    reason="Option-chain rows are loaded in TOM storage.",
                    source=None,
                    source_url=None,
                    decision_date=None,
                    as_of_date=None,
                    effective_date=None,
                    raw_chain_available=True,
                    effective_coverage_included=True,
                )
            )
        else:
            statuses.append(
                OptionChainAvailabilityStatus(
                    ticker=ticker,
                    availability_status="missing",
                    reason_code="missing_option_chain",
                    reason="No loaded option-chain rows or valid non-actionable decision.",
                    source=None,
                    source_url=None,
                    decision_date=None,
                    as_of_date=None,
                    effective_date=None,
                    raw_chain_available=False,
                    effective_coverage_included=True,
                )
            )
    return tuple(statuses)


def format_option_chain_availability(statuses: tuple[OptionChainAvailabilityStatus, ...]) -> str:
    non_available = [
        f"{status.ticker} {status.availability_status} - {status.reason_code or status.reason or 'none'}"
        for status in statuses
        if status.availability_status != "available"
    ]
    return ", ".join(non_available) if non_available else "all available"


def validate_options_chain_backfill(
    config: AppConfig,
    source_dir: Path | None = None,
) -> OptionsChainBackfillValidation:
    directory = source_dir or config.options_chain_source_exports_dir
    files = _source_export_files(config, directory)
    valid_rows: list[OptionChainSnapshot] = []
    invalid_reasons: list[str] = []
    blank_count = 0
    for file_path in files:
        rows, blanks, errors = _read_options_source_export_rows(config, file_path)
        valid_rows.extend(rows)
        blank_count += blanks
        invalid_reasons.extend(errors)

    fetch_tickers = tuple(asset.ticker for asset in option_fetch_assets(config, max_tickers=0))
    loaded_tickers = {
        status.ticker
        for status in option_income_statuses(config.database_path)
        if status.option_chain_rows
    }
    valid_tickers = tuple(sorted({row.ticker for row in valid_rows}))
    minimum_tickers = minimum_option_chain_tickers(config)
    minimum_set = set(minimum_tickers)
    minimum_loaded = tuple(sorted(minimum_set & loaded_tickers))
    minimum_valid = tuple(sorted(minimum_set & set(valid_tickers)))
    minimum_projected = tuple(sorted(minimum_set & (loaded_tickers | set(valid_tickers))))
    minimum_missing = tuple(ticker for ticker in minimum_tickers if ticker not in minimum_projected)
    projected = len(set(fetch_tickers) & (loaded_tickers | set(valid_tickers)))
    blocked_reason: str | None = None
    if invalid_reasons:
        blocked_reason = "invalid_option_backfill_rows"
    elif not valid_rows:
        blocked_reason = "no_valid_option_backfill_rows"
    elif projected <= len(set(fetch_tickers) & loaded_tickers):
        blocked_reason = "projected_option_chain_coverage_does_not_improve"
    return OptionsChainBackfillValidation(
        source_dir=directory,
        source_export_files=files,
        valid_row_count=len(valid_rows),
        invalid_row_count=len(invalid_reasons),
        blank_placeholder_count=blank_count,
        valid_tickers=valid_tickers,
        invalid_reasons=tuple(invalid_reasons),
        projected_loaded_ticker_count=projected,
        fetch_universe_ticker_count=len(fetch_tickers),
        apply_ready=blocked_reason is None,
        blocked_reason=blocked_reason,
        minimum_tickers=minimum_tickers,
        minimum_loaded_tickers=minimum_loaded,
        minimum_valid_tickers=minimum_valid,
        minimum_projected_loaded_tickers=minimum_projected,
        minimum_missing_tickers=minimum_missing,
        minimum_projected_loaded_ticker_count=len(minimum_projected),
        minimum_ticker_count=len(minimum_tickers),
    )


def export_options_chain_backfill_template(
    config: AppConfig,
    ticker: str | None = None,
    minimum_set: bool = False,
) -> OptionsChainBackfillExportResult:
    if minimum_set:
        assets_by_ticker = {
            asset.ticker: asset
            for asset in list_assets(config.database_path)
            if asset.active_flag == 1
        }
        assets = tuple(
            assets_by_ticker[ticker_name]
            for ticker_name in minimum_option_chain_tickers(config)
            if ticker_name in assets_by_ticker
        )
    else:
        assets = option_fetch_assets(config, ticker=ticker, max_tickers=0)
    warnings: list[str] = []
    if ticker and not assets:
        warnings.append(f"ticker_not_in_options_fetch_universe:{normalize_ticker(ticker)}")
    if minimum_set:
        fetch_tickers = {
            asset.ticker for asset in list_assets(config.database_path) if asset.active_flag == 1
        }
        missing_minimum = tuple(
            ticker_name
            for ticker_name in MINIMUM_OPTION_CHAIN_TICKERS
            if ticker_name not in fetch_tickers
        )
        warnings.extend(f"minimum_ticker_not_in_options_fetch_universe:{ticker_name}" for ticker_name in missing_minimum)
    directory = config.options_chain_source_exports_dir
    directory.mkdir(parents=True, exist_ok=True)
    suffix = "minimum_set" if minimum_set else (normalize_ticker(ticker).lower() if ticker else "all")
    path = directory / f"options_chain_backfill_{suffix}.csv"
    with path.open("w", newline="", encoding="utf-8") as output:
        writer = csv.DictWriter(output, fieldnames=OPTIONS_CHAIN_HEADERS)
        writer.writeheader()
        for asset in assets:
            writer.writerow(
                {
                    "ticker": asset.ticker,
                    "option_type": "put",
                    "source": "",
                    "source_url": "",
                }
            )
    return OptionsChainBackfillExportResult(
        path=path,
        row_count=len(assets),
        tickers=tuple(asset.ticker for asset in assets),
        warnings=tuple(warnings),
    )


def _option_chain_loaded_tickers(config: AppConfig) -> tuple[str, ...]:
    return tuple(
        sorted(
            {
                status.ticker
                for status in option_income_statuses(config.database_path)
                if status.option_chain_rows
            }
        )
    )


def _option_chain_missing_assets(config: AppConfig) -> tuple[Asset, ...]:
    loaded = set(_option_chain_loaded_tickers(config))
    non_actionable = set(valid_non_actionable_option_chain_tickers(config))
    return tuple(
        asset
        for asset in option_fetch_assets(config, max_tickers=0)
        if asset.ticker not in loaded and asset.ticker not in non_actionable
    )


def _option_chain_missing_priority(asset: Asset) -> tuple[int, str]:
    role = normalize_asset_role(asset.asset_role)
    asset_type = (asset.asset_type or "").strip().lower()
    if role == "scoreable" and asset_type == "equity":
        return (0, asset.ticker)
    if role == "scoreable" and asset_type == "etf":
        return (1, asset.ticker)
    return (2, asset.ticker)


def prioritized_option_chain_missing_assets(config: AppConfig) -> tuple[Asset, ...]:
    return tuple(sorted(_option_chain_missing_assets(config), key=_option_chain_missing_priority))


def _provider_fetch_assets(
    config: AppConfig,
    ticker: str | None = None,
    max_tickers: int | None = None,
) -> tuple[Asset, ...]:
    if ticker:
        return option_fetch_assets(config, ticker=ticker, max_tickers=max_tickers)
    missing = list(prioritized_option_chain_missing_assets(config))
    missing_tickers = {asset.ticker for asset in missing}
    remaining = [
        asset
        for asset in option_fetch_assets(config, max_tickers=0)
        if asset.ticker not in missing_tickers
    ]
    selected = missing + remaining
    if max_tickers is None:
        max_tickers = config.options_max_tickers_per_run
    if max_tickers and max_tickers > 0:
        selected = selected[:max_tickers]
    return tuple(selected)


def option_chain_coverage_plan(config: AppConfig) -> OptionChainCoveragePlan:
    provider = option_provider_status(config, check_connectivity=False)
    validation = validate_options_chain_backfill(config)
    non_actionable = validate_option_chain_non_actionable_decisions(config)
    fetch_assets = option_fetch_assets(config, max_tickers=0)
    fetch_tickers = tuple(asset.ticker for asset in fetch_assets)
    loaded_tickers = _option_chain_loaded_tickers(config)
    loaded_set = set(loaded_tickers)
    fetch_set = set(fetch_tickers)
    non_actionable_set = set(non_actionable.valid_tickers)
    effective_fetch_tickers = tuple(
        ticker for ticker in fetch_tickers if ticker not in non_actionable_set
    )
    effective_fetch_set = set(effective_fetch_tickers)
    raw_current_loaded_count = len(loaded_set & fetch_set)
    current_loaded_count = len(loaded_set & effective_fetch_set)
    raw_missing_tickers = tuple(ticker for ticker in fetch_tickers if ticker not in loaded_set)
    missing_assets = prioritized_option_chain_missing_assets(config)
    missing_tickers = tuple(asset.ticker for asset in missing_assets)
    valid_set = set(validation.valid_tickers)
    projected_loaded = tuple(sorted(effective_fetch_set & (loaded_set | valid_set)))
    projected_missing = tuple(
        ticker for ticker in effective_fetch_tickers if ticker not in projected_loaded
    )
    blocked_reason: str | None = None
    if current_loaded_count < len(effective_fetch_tickers):
        if validation.invalid_reasons:
            blocked_reason = "invalid_option_backfill_rows"
        elif not validation.valid_row_count:
            blocked_reason = "no_valid_option_backfill_rows"
        elif len(projected_loaded) <= current_loaded_count:
            blocked_reason = "projected_option_chain_coverage_does_not_improve"
    apply_ready = blocked_reason is None and current_loaded_count < len(effective_fetch_tickers)
    coverage_status = (
        "complete"
        if current_loaded_count >= len(effective_fetch_tickers)
        else "ready_to_apply"
        if apply_ready
        else "missing_coverage"
    )
    template_path = config.options_chain_source_exports_dir / "options_chain_missing_backfill.csv"
    non_actionable_path = _non_actionable_path(config)
    warnings: list[str] = []
    if provider.blocked_reason:
        warnings.append(provider.blocked_reason)
    if validation.blocked_reason and missing_tickers:
        warnings.append(validation.blocked_reason)
    if non_actionable.invalid_decision_count:
        warnings.append("invalid_non_actionable_option_chain_decisions")
    if missing_tickers:
        warnings.append("missing_option_chain:" + ",".join(missing_tickers))
    notes = list(non_actionable.notes)
    next_commands = (
        "python -m target_opportunity_monitor fetch-options-chain --source auto --max-tickers 5 --force-refresh",
        "python -m target_opportunity_monitor fetch-options-chain --source yfinance --max-tickers 5 --force-refresh",
        "python -m target_opportunity_monitor export-options-chain-missing-template",
        "fill data/options/source_exports/options_chain_non_actionable.csv only with source-backed no-chain decisions",
        "python -m target_opportunity_monitor validate-options-chain-backfill",
        "python -m target_opportunity_monitor apply-options-chain-coverage-backfill",
        "python -m target_opportunity_monitor apply-options-chain-coverage-backfill --confirm --allow-partial",
    )
    return OptionChainCoveragePlan(
        coverage_status=coverage_status,
        current_loaded_ticker_count=current_loaded_count,
        fetch_universe_ticker_count=len(effective_fetch_tickers),
        raw_fetch_universe_ticker_count=len(fetch_tickers),
        effective_fetch_universe_ticker_count=len(effective_fetch_tickers),
        current_loaded_tickers=tuple(
            ticker for ticker in effective_fetch_tickers if ticker in loaded_set
        ),
        missing_tickers=tuple(
            ticker for ticker in effective_fetch_tickers if ticker not in loaded_set
        ),
        raw_missing_tickers=raw_missing_tickers,
        effective_missing_tickers=missing_tickers,
        prioritized_missing_tickers=missing_tickers,
        valid_backfill_tickers=validation.valid_tickers,
        projected_loaded_ticker_count=len(projected_loaded),
        projected_missing_tickers=projected_missing,
        non_actionable_tickers=non_actionable.valid_tickers,
        non_actionable_valid_decision_count=non_actionable.valid_decision_count,
        non_actionable_invalid_decision_count=non_actionable.invalid_decision_count,
        non_actionable_blank_placeholder_count=non_actionable.blank_placeholder_count,
        non_actionable_invalid_reasons=non_actionable.invalid_reasons,
        non_actionable_template_path=non_actionable_path,
        raw_coverage_count=f"{raw_current_loaded_count}/{len(fetch_tickers)}",
        effective_coverage_count=f"{current_loaded_count}/{len(effective_fetch_tickers)}",
        notes=tuple(dict.fromkeys(notes)),
        apply_ready=apply_ready,
        blocked_reason=blocked_reason,
        provider_blocked_reason=provider.blocked_reason,
        backfill_template_path=template_path,
        next_commands=next_commands,
        warnings=tuple(dict.fromkeys(warnings)),
    )


def export_options_chain_missing_template(
    config: AppConfig,
) -> OptionsChainBackfillExportResult:
    assets = prioritized_option_chain_missing_assets(config)
    directory = config.options_chain_source_exports_dir
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "options_chain_missing_backfill.csv"
    non_actionable_path = _non_actionable_path(config)
    with path.open("w", newline="", encoding="utf-8") as output:
        writer = csv.DictWriter(output, fieldnames=OPTIONS_CHAIN_HEADERS)
        writer.writeheader()
        for asset in assets:
            writer.writerow(
                {
                    "ticker": asset.ticker,
                    "option_type": "put",
                    "source": "",
                    "source_url": "",
                }
            )
    with non_actionable_path.open("w", newline="", encoding="utf-8") as output:
        writer = csv.DictWriter(
            output,
            fieldnames=OPTIONS_CHAIN_NON_ACTIONABLE_HEADERS,
        )
        writer.writeheader()
        for asset in assets:
            writer.writerow(
                {
                    "ticker": asset.ticker,
                    "reason_code": "",
                    "source": "",
                    "source_url": "",
                }
            )
    warnings: list[str] = []
    if not assets:
        warnings.append("no_missing_option_chain_tickers")
    return OptionsChainBackfillExportResult(
        path=path,
        row_count=len(assets),
        tickers=tuple(asset.ticker for asset in assets),
        warnings=tuple(warnings),
        non_actionable_path=non_actionable_path,
    )


def apply_options_chain_coverage_backfill(
    config: AppConfig,
    *,
    confirm: bool = False,
    allow_partial: bool = False,
    source_dir: Path | None = None,
) -> OptionChainCoverageApplyResult:
    validation = validate_options_chain_backfill(config, source_dir=source_dir)
    plan = option_chain_coverage_plan(config)
    warnings: list[str] = list(validation.invalid_reasons)
    current_loaded = plan.current_loaded_ticker_count
    projected = plan.projected_loaded_ticker_count
    full_count = plan.fetch_universe_ticker_count

    blocked_reason: str | None = None
    if validation.invalid_row_count:
        blocked_reason = "invalid_option_backfill_rows"
    elif not validation.valid_row_count:
        blocked_reason = "no_valid_option_backfill_rows"
    elif projected <= current_loaded:
        blocked_reason = "projected_option_chain_coverage_does_not_improve"
    elif not allow_partial and projected < full_count:
        blocked_reason = "option_chain_coverage_incomplete"

    if blocked_reason:
        warnings.append(blocked_reason)
        return OptionChainCoverageApplyResult(
            confirmed=confirm,
            allow_partial=allow_partial,
            success=False,
            status="blocked",
            blocked_reason=blocked_reason,
            plan=plan,
            warnings=tuple(dict.fromkeys(warnings)),
        )

    if not confirm:
        return OptionChainCoverageApplyResult(
            confirmed=False,
            allow_partial=allow_partial,
            success=True,
            status="dry_run_ready",
            blocked_reason=None,
            plan=plan,
            warnings=tuple(dict.fromkeys(warnings)),
        )

    imported = import_options_chain_source_exports(config, source_dir=source_dir)
    warnings.extend(imported.warnings)
    income = compute_options_income(config)
    risk = compute_options_risk(config)
    outcomes = compute_options_outcomes(config)
    lifecycle = compute_options_lifecycle(config)
    refreshed_plan = option_chain_coverage_plan(config)
    if refreshed_plan.current_loaded_ticker_count <= current_loaded:
        warnings.append("option_chain_coverage_did_not_improve")
        return OptionChainCoverageApplyResult(
            confirmed=True,
            allow_partial=allow_partial,
            success=False,
            status="blocked",
            blocked_reason="option_chain_coverage_did_not_improve",
            plan=refreshed_plan,
            imported_count=imported.imported_count,
            computed_income_tickers=income.computed_count,
            computed_risk_tickers=risk.computed_count,
            computed_outcome_tickers=outcomes.computed_count,
            computed_lifecycle_tickers=lifecycle.computed_count,
            warnings=tuple(dict.fromkeys(warnings)),
        )
    return OptionChainCoverageApplyResult(
        confirmed=True,
        allow_partial=allow_partial,
        success=True,
        status="applied",
        blocked_reason=None,
        plan=refreshed_plan,
        imported_count=imported.imported_count,
        computed_income_tickers=income.computed_count,
        computed_risk_tickers=risk.computed_count,
        computed_outcome_tickers=outcomes.computed_count,
        computed_lifecycle_tickers=lifecycle.computed_count,
        warnings=tuple(dict.fromkeys(warnings)),
    )


def build_option_chain_coverage_plan_text(config: AppConfig) -> str:
    plan = option_chain_coverage_plan(config)
    availability = option_chain_availability_statuses(config)
    lines = [
        "Option Chain Coverage Plan",
        f"Coverage status: {plan.coverage_status}",
        f"Current chain coverage: {plan.current_loaded_ticker_count}/{plan.fetch_universe_ticker_count}",
        f"Raw chain coverage: {plan.raw_coverage_count}",
        f"Effective chain coverage: {plan.effective_coverage_count}",
        f"Loaded tickers: {', '.join(plan.current_loaded_tickers) if plan.current_loaded_tickers else 'none'}",
        f"Missing tickers: {', '.join(plan.missing_tickers) if plan.missing_tickers else 'none'}",
        f"Raw missing tickers: {', '.join(plan.raw_missing_tickers) if plan.raw_missing_tickers else 'none'}",
        "Non-actionable chain tickers: "
        + (
            ", ".join(plan.non_actionable_tickers)
            if plan.non_actionable_tickers
            else "none"
        ),
        f"Non-actionable decision template: {plan.non_actionable_template_path}",
        f"Non-actionable valid decisions: {plan.non_actionable_valid_decision_count}",
        f"Non-actionable invalid decisions: {plan.non_actionable_invalid_decision_count}",
        f"Non-actionable blank placeholders: {plan.non_actionable_blank_placeholder_count}",
        "Prioritized missing tickers: "
        + (
            ", ".join(plan.prioritized_missing_tickers)
            if plan.prioritized_missing_tickers
            else "none"
        ),
        f"Valid backfill tickers: {', '.join(plan.valid_backfill_tickers) if plan.valid_backfill_tickers else 'none'}",
        f"Projected chain coverage: {plan.projected_loaded_ticker_count}/{plan.fetch_universe_ticker_count}",
        f"Projected missing tickers: {', '.join(plan.projected_missing_tickers) if plan.projected_missing_tickers else 'none'}",
        f"Apply ready: {plan.apply_ready}",
        f"Blocked reason: {plan.blocked_reason or 'none'}",
        f"Provider blocked reason: {plan.provider_blocked_reason or 'none'}",
        f"Notes: {', '.join(plan.notes) if plan.notes else 'none'}",
        f"Options chain availability: {format_option_chain_availability(availability)}",
        "Provider fallback order: ibkr -> yfinance -> source_export",
        "Provider attempt status: "
        + (
            ", ".join(f"{ticker}:missing_chain" for ticker in plan.prioritized_missing_tickers)
            if plan.prioritized_missing_tickers
            else "complete"
        ),
        f"Missing template: {plan.backfill_template_path}",
        f"Warnings: {', '.join(plan.warnings) if plan.warnings else 'none'}",
        "",
        "Next commands:",
    ]
    if plan.non_actionable_invalid_reasons:
        lines.append("")
        lines.append("Invalid non-actionable decisions:")
        lines.extend(f"- {reason}" for reason in plan.non_actionable_invalid_reasons)
        lines.append("")
    lines.extend(f"- {command}" for command in plan.next_commands)
    return "\n".join(lines)


def build_options_chain_missing_template_text(config: AppConfig) -> str:
    result = export_options_chain_missing_template(config)
    return "\n".join(
        (
            "Option Chain Missing Backfill Template",
            f"Template: {result.path}",
            f"Non-actionable template: {result.non_actionable_path or 'none'}",
            f"Rows: {result.row_count}",
            f"Tickers: {', '.join(result.tickers) if result.tickers else 'none'}",
            f"Warnings: {', '.join(result.warnings) if result.warnings else 'none'}",
        )
    )


def build_options_chain_coverage_apply_text(
    config: AppConfig,
    *,
    confirm: bool = False,
    allow_partial: bool = False,
    source_dir: Path | None = None,
) -> tuple[str, OptionChainCoverageApplyResult]:
    result = apply_options_chain_coverage_backfill(
        config,
        confirm=confirm,
        allow_partial=allow_partial,
        source_dir=source_dir,
    )
    plan = result.plan
    lines = [
        "Option Chain Coverage Backfill Apply",
        f"Mode: {'confirm' if confirm else 'dry_run'}",
        f"Allow partial: {allow_partial}",
        f"Status: {result.status}",
        f"Success: {result.success}",
        f"Blocked reason: {result.blocked_reason or 'none'}",
        f"Current chain coverage: {plan.current_loaded_ticker_count}/{plan.fetch_universe_ticker_count}",
        f"Projected chain coverage: {plan.projected_loaded_ticker_count}/{plan.fetch_universe_ticker_count}",
        f"Valid backfill tickers: {', '.join(plan.valid_backfill_tickers) if plan.valid_backfill_tickers else 'none'}",
        f"Projected missing tickers: {', '.join(plan.projected_missing_tickers) if plan.projected_missing_tickers else 'none'}",
        f"Imported rows: {result.imported_count}",
        f"Computed income tickers: {result.computed_income_tickers}",
        f"Computed risk tickers: {result.computed_risk_tickers}",
        f"Computed outcome tickers: {result.computed_outcome_tickers}",
        f"Computed lifecycle tickers: {result.computed_lifecycle_tickers}",
        f"Warnings: {', '.join(result.warnings) if result.warnings else 'none'}",
    ]
    if not confirm:
        lines.append("Dry run only: no source exports were imported and no reviews were recomputed.")
    return "\n".join(lines), result


def import_options_chain_source_exports(
    config: AppConfig,
    source_dir: Path | None = None,
) -> OptionsChainBackfillImportResult:
    validation = validate_options_chain_backfill(config, source_dir=source_dir)
    imported = 0
    tickers: set[str] = set()
    warnings: list[str] = list(validation.invalid_reasons)
    if validation.invalid_reasons:
        return OptionsChainBackfillImportResult(
            source_dir=validation.source_dir,
            source_export_files=validation.source_export_files,
            imported_count=0,
            valid_row_count=validation.valid_row_count,
            invalid_row_count=validation.invalid_row_count,
            blank_placeholder_count=validation.blank_placeholder_count,
            tickers=(),
            warnings=tuple(warnings),
        )
    for file_path in validation.source_export_files:
        rows, _blanks, _errors = _read_options_source_export_rows(config, file_path)
        for row in rows:
            upsert_option_chain_snapshot(config.database_path, row)
            imported += 1
            tickers.add(row.ticker)
    if not imported:
        warnings.append(validation.blocked_reason or "no_valid_option_backfill_rows")
    return OptionsChainBackfillImportResult(
        source_dir=validation.source_dir,
        source_export_files=validation.source_export_files,
        imported_count=imported,
        valid_row_count=validation.valid_row_count,
        invalid_row_count=validation.invalid_row_count,
        blank_placeholder_count=validation.blank_placeholder_count,
        tickers=tuple(sorted(tickers)),
        warnings=tuple(dict.fromkeys(warnings)),
    )


def parse_options_chain_csv(
    text: str,
    config: AppConfig,
) -> list[OptionChainSnapshot]:
    reader = csv.DictReader(StringIO(text))
    if not reader.fieldnames:
        raise ValueError("Options chain CSV is missing a header row.")
    missing = REQUIRED_OPTIONS_CHAIN_COLUMNS - set(reader.fieldnames)
    if missing:
        raise ValueError(
            "Options chain CSV missing required columns: " + ", ".join(sorted(missing))
        )

    rows: list[OptionChainSnapshot] = []
    for row_number, row in enumerate(reader, start=2):
        if not any((value or "").strip() for value in row.values()):
            continue
        ticker = normalize_ticker(row.get("ticker", ""))
        if not ticker:
            raise ValueError(f"Row {row_number}: missing required ticker.")
        asset = latest_asset(config.database_path, ticker)
        if asset is None or asset.active_flag != 1:
            raise ValueError(f"Row {row_number}: unsupported or inactive ticker: {ticker}")

        strike = _parse_float(row.get("strike"), "strike", row_number)
        bid = _parse_float(row.get("bid"), "bid", row_number)
        ask = _parse_float(row.get("ask"), "ask", row_number)
        if strike in (None, 0) or bid is None or ask is None:
            raise ValueError(f"Row {row_number}: strike, bid, and ask are required.")
        if ask < bid:
            raise ValueError(f"Row {row_number}: ask cannot be below bid.")

        rows.append(
            OptionChainSnapshot(
                ticker=ticker,
                snapshot_timestamp=_parse_timestamp(row.get("snapshot_timestamp"), row_number),
                expiration_date=_parse_date(row.get("expiration_date"), "expiration_date", row_number),
                option_type=_normalize_option_type(row.get("option_type"), row_number),
                strike=strike,
                bid=bid,
                ask=ask,
                last=_parse_float(row.get("last"), "last", row_number),
                mark=_parse_float(row.get("mark"), "mark", row_number),
                volume=_parse_float(row.get("volume"), "volume", row_number),
                open_interest=_parse_float(row.get("open_interest"), "open_interest", row_number),
                implied_volatility=_parse_float(
                    row.get("implied_volatility"),
                    "implied_volatility",
                    row_number,
                ),
                delta=_parse_float(row.get("delta"), "delta", row_number, allow_negative=True),
                gamma=_parse_float(row.get("gamma"), "gamma", row_number, allow_negative=True),
                theta=_parse_float(row.get("theta"), "theta", row_number, allow_negative=True),
                vega=_parse_float(row.get("vega"), "vega", row_number, allow_negative=True),
                source=(row.get("source") or "manual_csv").strip() or "manual_csv",
                source_url=(row.get("source_url") or "").strip() or None,
                as_of_date=_parse_optional_date(row.get("as_of_date"), "as_of_date", row_number),
                effective_date=_parse_optional_date(
                    row.get("effective_date"),
                    "effective_date",
                    row_number,
                ),
            )
        )
    return rows


def load_options_chain_csv(
    config: AppConfig,
    path: Path | None = None,
) -> OptionsChainLoadResult:
    options_path = path or config.options_chain_path
    ensure_options_chain_csv_header(options_path)
    rows = parse_options_chain_csv(options_path.read_text(encoding="utf-8-sig"), config)
    tickers: set[str] = set()
    for row in rows:
        upsert_option_chain_snapshot(config.database_path, row)
        tickers.add(row.ticker)
    warnings: list[str] = []
    if not rows:
        warnings.append("empty_options_chain")
    return OptionsChainLoadResult(
        path=options_path,
        row_count=len(rows),
        loaded_count=len(rows),
        skipped_count=0,
        tickers=tuple(sorted(tickers)),
        warnings=tuple(warnings),
    )


def _option_claim_tickers(config: AppConfig) -> tuple[str, ...]:
    try:
        claims = list_trader_commentary_claims(config.database_path)
    except Exception:
        return ()
    return tuple(
        sorted(
            {
                normalize_ticker(claim.ticker)
                for claim in claims
                if claim.claim_type == "options_income_idea" and claim.ticker
            }
        )
    )


def option_fetch_assets(
    config: AppConfig,
    ticker: str | None = None,
    max_tickers: int | None = None,
) -> tuple[Asset, ...]:
    wanted = normalize_ticker(ticker) if ticker else None
    assets = [asset for asset in list_assets(config.database_path) if asset.active_flag == 1]
    if wanted:
        return tuple(asset for asset in assets if asset.ticker == wanted)

    claim_tickers = set(_option_claim_tickers(config))
    by_ticker = {asset.ticker: asset for asset in assets}
    selected: list[Asset] = []
    if config.options_option_fetch_universe == "scoreable_plus_commentary_options":
        for claim_ticker in sorted(claim_tickers):
            asset = by_ticker.get(claim_ticker)
            if asset is not None:
                selected.append(asset)
    for asset in sorted(assets, key=lambda item: item.ticker):
        role = normalize_asset_role(asset.asset_role)
        if role == "scoreable" and asset.ticker not in {item.ticker for item in selected}:
            selected.append(asset)
    if max_tickers is None:
        max_tickers = config.options_max_tickers_per_run
    if max_tickers and max_tickers > 0:
        selected = selected[:max_tickers]
    return tuple(selected)


def select_option_expirations(
    expirations: tuple[str, ...] | list[str],
    config: AppConfig,
    as_of: date | None = None,
) -> tuple[str, ...]:
    today = as_of or _today()
    parsed: list[tuple[date, str]] = []
    for expiration in expirations:
        text = str(expiration).strip()
        if not text:
            continue
        if len(text) == 8 and text.isdigit():
            text = f"{text[:4]}-{text[4:6]}-{text[6:]}"
        try:
            expiration_date = date.fromisoformat(text)
        except ValueError:
            continue
        dte = (expiration_date - today).days
        if config.options_default_min_dte <= dte <= config.options_default_max_dte:
            parsed.append((expiration_date, expiration_date.isoformat()))
    return tuple(
        item[1]
        for item in sorted(parsed, key=lambda item: item[0])[
            : config.options_max_expirations_per_ticker
        ]
    )


def select_option_strikes(
    strikes: tuple[float, ...] | list[float],
    current_price: float,
    config: AppConfig,
    range_level: float | None = None,
    option_type: str = "put",
) -> tuple[float, ...]:
    if current_price <= 0:
        return ()
    normalized_type = (option_type or "put").strip().lower()
    if normalized_type == "call":
        lower_bound = current_price
        upper_bound = current_price * (1 + config.options_strike_window_pct)
    else:
        lower_bound = current_price * (1 - config.options_strike_window_pct)
        upper_bound = current_price if config.options_fetch_puts_only else (
            current_price * (1 + config.options_strike_window_pct)
        )
    candidates = sorted(
        {
            float(strike)
            for strike in strikes
            if lower_bound <= float(strike) <= upper_bound
        }
    )
    if not candidates:
        if normalized_type == "call":
            above_spot = sorted({float(strike) for strike in strikes if float(strike) >= current_price})
            candidates = above_spot[: config.options_max_strikes_per_expiration]
        else:
            below_spot = sorted({float(strike) for strike in strikes if float(strike) <= current_price})
            candidates = below_spot[-config.options_max_strikes_per_expiration :]
    if not candidates:
        candidates = sorted({float(strike) for strike in strikes}, key=lambda strike: abs(strike - current_price))[
            : config.options_max_strikes_per_expiration
        ]
    if normalized_type == "call":
        anchor = current_price * (1 + config.options_assignment_buffer_pct)
        selected = sorted(
            candidates,
            key=lambda strike: (abs(strike - anchor), strike),
        )[: config.options_max_strikes_per_expiration]
    else:
        anchor = range_level or current_price * (1 - config.options_assignment_buffer_pct)
        selected = sorted(
            candidates,
            key=lambda strike: (abs(strike - anchor), -strike),
        )[: config.options_max_strikes_per_expiration]
    return tuple(sorted(selected))


def _latest_chain_age_minutes(config: AppConfig, ticker: str) -> float | None:
    snapshots = list_option_chain_snapshots(config.database_path, ticker)
    if not snapshots:
        return None
    latest = max(snapshot.snapshot_timestamp for snapshot in snapshots)
    try:
        timestamp = datetime.fromisoformat(latest)
    except ValueError:
        return None
    return (datetime.now() - timestamp).total_seconds() / 60


def _is_chain_fresh(config: AppConfig, ticker: str) -> bool:
    age = _latest_chain_age_minutes(config, ticker)
    return age is not None and age <= config.options_chain_stale_after_minutes


def _option_float(value: object) -> float | None:
    if value is None:
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(parsed) or math.isinf(parsed):
        return None
    return parsed


def _provider_frame_records(frame: object) -> list[dict[str, object]]:
    return getattr(frame, "to_dict", lambda *_args, **_kwargs: [])("records")


def _yfinance_symbol(ticker: str) -> str:
    return normalize_ticker(ticker).replace(".", "-")


def _write_yfinance_cache(
    config: AppConfig,
    ticker: str,
    payload: dict[str, object],
) -> None:
    cache_dir = config.options_chain_cache_dir / "yfinance"
    cache_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%dT%H%M%S")
    path = cache_dir / f"{normalize_ticker(ticker).lower()}_{timestamp}.json"
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _write_provider_option_chain_export(
    config: AppConfig,
    source: str,
    snapshots: tuple[OptionChainSnapshot, ...],
) -> Path:
    directory = config.options_chain_source_exports_dir
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"options_chain_{source}_provider.csv"
    with path.open("w", newline="", encoding="utf-8") as output:
        writer = csv.DictWriter(output, fieldnames=OPTIONS_CHAIN_HEADERS)
        writer.writeheader()
        for snapshot in snapshots:
            writer.writerow(
                {
                    "ticker": snapshot.ticker,
                    "snapshot_timestamp": snapshot.snapshot_timestamp,
                    "expiration_date": snapshot.expiration_date,
                    "option_type": snapshot.option_type,
                    "strike": snapshot.strike,
                    "bid": snapshot.bid,
                    "ask": snapshot.ask,
                    "last": snapshot.last if snapshot.last is not None else "",
                    "mark": snapshot.mark if snapshot.mark is not None else "",
                    "volume": snapshot.volume if snapshot.volume is not None else "",
                    "open_interest": (
                        snapshot.open_interest
                        if snapshot.open_interest is not None
                        else ""
                    ),
                    "implied_volatility": (
                        snapshot.implied_volatility
                        if snapshot.implied_volatility is not None
                        else ""
                    ),
                    "delta": snapshot.delta if snapshot.delta is not None else "",
                    "gamma": snapshot.gamma if snapshot.gamma is not None else "",
                    "theta": snapshot.theta if snapshot.theta is not None else "",
                    "vega": snapshot.vega if snapshot.vega is not None else "",
                    "source": snapshot.source,
                    "source_url": snapshot.source_url or "",
                    "as_of_date": snapshot.as_of_date or "",
                    "effective_date": snapshot.effective_date or "",
                }
            )
    return path


def _import_provider_option_chain_export(
    config: AppConfig,
    source: str,
    snapshots: tuple[OptionChainSnapshot, ...],
) -> tuple[int, tuple[str, ...]]:
    if not snapshots:
        return 0, ()
    path = _write_provider_option_chain_export(config, source, snapshots)
    rows, _blank_count, errors = _read_options_source_export_rows(config, path)
    if errors:
        return 0, tuple(errors)
    for row in rows:
        upsert_option_chain_snapshot(config.database_path, row)
    return len(rows), ()


def _fetch_yfinance_option_chain_snapshots(
    config: AppConfig,
    selected_assets: tuple[Asset, ...],
) -> OptionChainFetchResult:
    config.options_chain_cache_dir.mkdir(parents=True, exist_ok=True)
    try:
        import yfinance as yf  # type: ignore[import-not-found]
    except Exception as error:
        return OptionChainFetchResult(
            source="yfinance",
            cache_dir=config.options_chain_cache_dir,
            results=tuple(
                OptionChainFetchTickerResult(
                    ticker=asset.ticker,
                    status="warning",
                    rows_loaded=0,
                    warnings=(
                        "provider_unavailable",
                        f"yfinance_not_available:{type(error).__name__}",
                    ),
                )
                for asset in selected_assets
            ),
        )

    try:
        yf.set_tz_cache_location(str(config.options_chain_cache_dir / "yfinance_tz_cache"))
    except Exception:
        try:
            yf.set_tz_cache_location(str(Path(tempfile.gettempdir()) / "tom_yfinance_cache"))
        except Exception:
            pass

    all_snapshots: list[OptionChainSnapshot] = []
    results: list[OptionChainFetchTickerResult] = []
    snapshot_timestamp = datetime.now().isoformat(timespec="seconds")
    today_text = _today().isoformat()
    for asset in selected_assets:
        ticker = asset.ticker
        symbol = _yfinance_symbol(ticker)
        warnings: list[str] = []
        snapshots: list[OptionChainSnapshot] = []
        selected_expiration_count = 0
        selected_strike_values: set[float] = set()
        current_price = _quote_price(config, ticker)
        range_state, range_level = _range_level(config, ticker)
        include_calls = (asset.asset_type or "").strip().lower() == "etf"
        if current_price is None or current_price <= 0:
            warnings.append("stale_underlying_price")
        try:
            ticker_obj = yf.Ticker(symbol)
            expirations = tuple(str(value) for value in getattr(ticker_obj, "options", ()) or ())
            selected_expirations = select_option_expirations(expirations, config)
            selected_expiration_count = len(selected_expirations)
            if not selected_expirations:
                warnings.append("no_expirations")
            elif current_price is None or current_price <= 0:
                warnings.append("missing_underlying_price")
            else:
                for expiration in selected_expirations:
                    chain = ticker_obj.option_chain(expiration)
                    option_sources: list[tuple[str, list[dict[str, object]]]] = [
                        ("put", _provider_frame_records(getattr(chain, "puts", None))),
                    ]
                    if include_calls:
                        option_sources.append(
                            ("call", _provider_frame_records(getattr(chain, "calls", None)))
                        )
                    for option_type, option_rows in option_sources:
                        strikes = tuple(
                            value
                            for value in (_option_float(row.get("strike")) for row in option_rows)
                            if value is not None
                        )
                        selected_strikes = select_option_strikes(
                            strikes,
                            current_price,
                            config,
                            range_level=range_level,
                            option_type=option_type,
                        )
                        selected_strike_set = {round(value, 6) for value in selected_strikes}
                        selected_strike_values.update(selected_strikes)
                        for row in option_rows:
                            strike = _option_float(row.get("strike"))
                            if strike is None or round(strike, 6) not in selected_strike_set:
                                continue
                            bid = _option_float(row.get("bid"))
                            ask = _option_float(row.get("ask"))
                            if bid is None or ask is None or bid <= 0 or ask <= 0 or ask < bid:
                                continue
                            last = _option_float(row.get("lastPrice"))
                            mark = (bid + ask) / 2
                            snapshots.append(
                                OptionChainSnapshot(
                                    ticker=ticker,
                                    snapshot_timestamp=snapshot_timestamp,
                                    expiration_date=expiration,
                                    option_type=option_type,
                                    strike=round(strike, 4),
                                    bid=round(bid, 4),
                                    ask=round(ask, 4),
                                    last=_round_optional(last, digits=4),
                                    mark=round(mark, 4),
                                    volume=_option_float(row.get("volume")),
                                    open_interest=_option_float(row.get("openInterest")),
                                    implied_volatility=_option_float(row.get("impliedVolatility")),
                                    delta=_option_float(row.get("delta")),
                                    source="yfinance_option_chain",
                                    source_url=f"https://finance.yahoo.com/quote/{symbol}/options",
                                    as_of_date=today_text,
                                    effective_date=today_text,
                                )
                            )
                if selected_expirations and not snapshots:
                    warnings.append("missing_bid_ask")
        except Exception as error:
            warnings.append(f"provider_unavailable:{type(error).__name__}")

        all_snapshots.extend(snapshots)
        _write_yfinance_cache(
            config,
            ticker,
            {
                "ticker": ticker,
                "symbol": symbol,
                "snapshot_timestamp": snapshot_timestamp,
                "range_state": range_state,
                "rows": [snapshot.__dict__ for snapshot in snapshots],
                "warnings": warnings,
            },
        )
        results.append(
            OptionChainFetchTickerResult(
                ticker=ticker,
                status="loaded" if snapshots else "warning",
                rows_loaded=len(snapshots),
                selected_expirations=selected_expiration_count,
                selected_strikes=len(selected_strike_values),
                warnings=tuple(dict.fromkeys(warnings)),
            )
        )

    imported_count, import_warnings = _import_provider_option_chain_export(
        config,
        "yfinance",
        tuple(all_snapshots),
    )
    if import_warnings:
        results.append(
            OptionChainFetchTickerResult(
                ticker="YFINANCE_EXPORT",
                status="warning",
                rows_loaded=0,
                warnings=import_warnings,
            )
        )
    elif imported_count != len(all_snapshots):
        results.append(
            OptionChainFetchTickerResult(
                ticker="YFINANCE_EXPORT",
                status="warning",
                rows_loaded=0,
                warnings=("provider_export_import_mismatch",),
            )
        )
    return OptionChainFetchResult(
        source="yfinance",
        results=tuple(results),
        cache_dir=config.options_chain_cache_dir,
    )


def fetch_options_chain(
    config: AppConfig,
    source: str | None = None,
    ticker: str | None = None,
    max_tickers: int | None = None,
    force_refresh: bool = False,
) -> OptionChainFetchResult:
    requested_source = (source or config.options_chain_source or "ibkr").strip().lower()
    if requested_source in {"auto", "fallback"}:
        selected_assets = _provider_fetch_assets(config, ticker=ticker, max_tickers=max_tickers)
        if not selected_assets:
            normalized = normalize_ticker(ticker) if ticker else "ALL"
            return OptionChainFetchResult(
                source="auto",
                cache_dir=config.options_chain_cache_dir,
                results=(
                    OptionChainFetchTickerResult(
                        ticker=normalized,
                        status="skipped",
                        rows_loaded=0,
                        warnings=("no_option_fetch_universe",),
                    ),
                ),
            )
        ibkr_result = fetch_options_chain(
            config,
            source="ibkr",
            ticker=ticker,
            max_tickers=max_tickers,
            force_refresh=force_refresh,
        )
        ibkr_by_ticker = {result.ticker: result for result in ibkr_result.results}
        fallback_assets = tuple(
            asset
            for asset in selected_assets
            if (
                asset.ticker not in ibkr_by_ticker
                or (
                    ibkr_by_ticker[asset.ticker].rows_loaded == 0
                    and ibkr_by_ticker[asset.ticker].status != "cached"
                )
            )
        )
        if not fallback_assets:
            return OptionChainFetchResult(
                source="auto",
                cache_dir=config.options_chain_cache_dir,
                results=ibkr_result.results,
            )
        yfinance_result = _fetch_yfinance_option_chain_snapshots(config, fallback_assets)
        return OptionChainFetchResult(
            source="auto",
            cache_dir=config.options_chain_cache_dir,
            results=ibkr_result.results + yfinance_result.results,
        )
    if requested_source == "csv":
        result = load_options_chain_csv(config)
        csv_results = tuple(
            OptionChainFetchTickerResult(
                ticker=ticker_name,
                status="loaded",
                rows_loaded=sum(
                    1
                    for row in list_option_chain_snapshots(config.database_path, ticker_name)
                    if row.source == "manual_csv"
                ),
                warnings=(),
            )
            for ticker_name in result.tickers
        )
        if not csv_results:
            csv_results = (
                OptionChainFetchTickerResult(
                    ticker=normalize_ticker(ticker) if ticker else "ALL",
                    status="skipped",
                    rows_loaded=0,
                    warnings=tuple(result.warnings or ("empty_options_chain",)),
                ),
            )
        return OptionChainFetchResult(
            source="csv",
            cache_dir=None,
            results=csv_results,
        )
    if requested_source in {"yfinance", "yahoo", "yahoo_finance"}:
        selected_assets = _provider_fetch_assets(config, ticker=ticker, max_tickers=max_tickers)
        if not selected_assets:
            normalized = normalize_ticker(ticker) if ticker else "ALL"
            return OptionChainFetchResult(
                source="yfinance",
                cache_dir=config.options_chain_cache_dir,
                results=(
                    OptionChainFetchTickerResult(
                        ticker=normalized,
                        status="skipped",
                        rows_loaded=0,
                        warnings=("no_option_fetch_universe",),
                    ),
                ),
            )
        return _fetch_yfinance_option_chain_snapshots(config, selected_assets)
    if requested_source != "ibkr":
        return OptionChainFetchResult(
            source=requested_source,
            cache_dir=config.options_chain_cache_dir,
            results=(
                OptionChainFetchTickerResult(
                    ticker=normalize_ticker(ticker) if ticker else "ALL",
                    status="skipped",
                    rows_loaded=0,
                    warnings=(f"unsupported_option_chain_source:{requested_source}",),
                ),
            ),
        )

    config.options_chain_cache_dir.mkdir(parents=True, exist_ok=True)
    selected_assets = _provider_fetch_assets(config, ticker=ticker, max_tickers=max_tickers)
    if not selected_assets:
        normalized = normalize_ticker(ticker) if ticker else "ALL"
        return OptionChainFetchResult(
            source="ibkr",
            cache_dir=config.options_chain_cache_dir,
            results=(
                OptionChainFetchTickerResult(
                    ticker=normalized,
                    status="skipped",
                    rows_loaded=0,
                    warnings=("no_option_fetch_universe",),
                ),
            ),
        )

    cached_results: list[OptionChainFetchTickerResult] = []
    assets_to_fetch: list[Asset] = []
    for asset in selected_assets:
        if not force_refresh and _is_chain_fresh(config, asset.ticker):
            cached_results.append(
                OptionChainFetchTickerResult(
                    ticker=asset.ticker,
                    status="cached",
                    rows_loaded=0,
                    warnings=("fresh_cached_chain",),
                )
            )
        else:
            assets_to_fetch.append(asset)

    fetched_results: list[OptionChainFetchTickerResult] = []
    if assets_to_fetch:
        from .ibkr_provider import fetch_ibkr_option_chain_snapshots

        provider_result = fetch_ibkr_option_chain_snapshots(
            config,
            tuple(assets_to_fetch),
            force_refresh=force_refresh,
        )
        for provider_ticker in provider_result.results:
            for snapshot in provider_ticker.snapshots:
                upsert_option_chain_snapshot(config.database_path, snapshot)
            if provider_ticker.warnings:
                insert_data_quality_check(
                    config.database_path,
                    f"option_chain:{provider_ticker.ticker}:ibkr",
                    "warning",
                    ", ".join(provider_ticker.warnings),
                    source="ibkr_option_chain",
                    as_of_date=_today().isoformat(),
                )
            fetched_results.append(
                OptionChainFetchTickerResult(
                    ticker=provider_ticker.ticker,
                    status=provider_ticker.status,
                    rows_loaded=provider_ticker.rows_loaded,
                    selected_expirations=provider_ticker.selected_expirations,
                    selected_strikes=provider_ticker.selected_strikes,
                    warnings=provider_ticker.warnings,
                )
            )

    return OptionChainFetchResult(
        source="ibkr",
        results=tuple(cached_results + fetched_results),
        cache_dir=config.options_chain_cache_dir,
    )


def _quote_price(config: AppConfig, ticker: str) -> float | None:
    quote = latest_quote_snapshot(config.database_path, ticker)
    if quote is not None:
        for value in (quote.last, quote.mark, quote.close):
            if value is not None and value > 0:
                return value
        if quote.bid is not None and quote.ask is not None and quote.bid > 0 and quote.ask > 0:
            return (quote.bid + quote.ask) / 2
    feature = latest_price_feature(config.database_path, ticker)
    return feature.current_price if feature else None


def _range_level(config: AppConfig, ticker: str) -> tuple[str | None, float | None]:
    snapshot = latest_range_snapshot(config.database_path, ticker)
    if snapshot is None:
        return None, None
    if (snapshot.asset_type or "").lower() == "etf":
        return snapshot.range_state, snapshot.nav_watch_discount_below or snapshot.nav_fair_value
    return snapshot.range_state, snapshot.starter_buy_below or snapshot.add_below


def _matching_commentary_claim_count(
    config: AppConfig,
    ticker: str,
    strike: float,
) -> int:
    try:
        claims = list_trader_commentary_claims(config.database_path, ticker=ticker)
    except Exception:
        return 0
    return sum(
        1
        for claim in claims
        if claim.claim_type == "options_income_idea"
        and claim.strike_price is not None
        and abs(claim.strike_price - strike) < 0.01
    )


def _review_snapshot(
    config: AppConfig,
    snapshot: OptionChainSnapshot,
    asset_role: str,
    current_price: float | None,
    range_state: str | None,
    range_level: float | None,
) -> OptionIncomeReview:
    review_date = _today().isoformat()
    warnings: list[str] = ["read_only_advisory_only"]
    dte = (date.fromisoformat(snapshot.expiration_date) - _today()).days
    mid_premium = snapshot.mark if snapshot.mark is not None and snapshot.mark > 0 else (
        snapshot.bid + snapshot.ask
    ) / 2
    breakeven = snapshot.strike - mid_premium
    premium_yield = mid_premium / snapshot.strike if snapshot.strike else None
    annualized_yield = (
        premium_yield * 365 / dte if premium_yield is not None and dte > 0 else None
    )
    downside_buffer = (
        current_price / snapshot.strike - 1 if current_price is not None and snapshot.strike else None
    )
    breakeven_buffer = (
        current_price / breakeven - 1
        if current_price is not None and breakeven and breakeven > 0
        else None
    )
    assignment_notional = snapshot.strike * OPTION_MULTIPLIER
    category = "eligible_watch"

    if snapshot.option_type != "put":
        category = "unsupported_underlying"
        warnings.append("sell_put_advisory_ignores_non_put_option")
    if dte < config.options_default_min_dte or dte > config.options_default_max_dte:
        warnings.append("outside_dte_window")
        category = "high_assignment_risk" if dte < config.options_default_min_dte else category
    if current_price is None:
        warnings.append("missing_underlying_price")
        category = "missing_range_context"
    if snapshot.open_interest is None or snapshot.open_interest < config.options_min_open_interest:
        warnings.append("low_open_interest")
        category = "illiquid_option"
    if snapshot.volume is None or snapshot.volume < config.options_min_volume:
        warnings.append("low_option_volume")
        category = "illiquid_option"
    if annualized_yield is None or annualized_yield < config.options_min_annualized_premium_yield:
        warnings.append("low_annualized_premium_yield")
        category = "low_premium" if category == "eligible_watch" else category
    if downside_buffer is None or downside_buffer < config.options_assignment_buffer_pct:
        warnings.append("assignment_buffer_below_threshold")
        category = "too_close_to_price" if category == "eligible_watch" else category
    if config.options_use_range_filter:
        if range_level is None:
            warnings.append("missing_range_context")
            category = "missing_range_context" if category == "eligible_watch" else category
        elif snapshot.strike > range_level:
            warnings.append("strike_above_range_level")
            category = "high_assignment_risk" if category == "eligible_watch" else category
    if normalize_asset_role(asset_role) != "scoreable":
        warnings.append("reference_instrument_only")
        category = "reference_only"

    return OptionIncomeReview(
        ticker=snapshot.ticker,
        review_date=review_date,
        snapshot_timestamp=snapshot.snapshot_timestamp,
        expiration_date=snapshot.expiration_date,
        option_type=snapshot.option_type,
        strike=round(snapshot.strike, 4),
        bid=snapshot.bid,
        ask=snapshot.ask,
        mid_premium=round(mid_premium, 4),
        breakeven=round(breakeven, 4),
        premium_yield=round(premium_yield, 6) if premium_yield is not None else None,
        annualized_yield=round(annualized_yield, 6) if annualized_yield is not None else None,
        downside_buffer_pct=round(downside_buffer, 6) if downside_buffer is not None else None,
        breakeven_buffer_pct=round(breakeven_buffer, 6) if breakeven_buffer is not None else None,
        assignment_notional=round(assignment_notional, 2),
        open_interest=snapshot.open_interest,
        volume=snapshot.volume,
        implied_volatility=snapshot.implied_volatility,
        delta=snapshot.delta,
        current_price=current_price,
        range_state=range_state,
        range_level=range_level,
        review_category=category,
        risk_warnings=_join_unique(warnings),
        commentary_claim_count=_matching_commentary_claim_count(config, snapshot.ticker, snapshot.strike),
        model_version=config.options_model_version,
        source="options_income",
        as_of_date=review_date,
        effective_date=snapshot.snapshot_timestamp,
    )


def compute_options_income(
    config: AppConfig,
    ticker: str | None = None,
) -> OptionIncomeComputeResult:
    wanted = normalize_ticker(ticker) if ticker else None
    chain_rows = list_option_chain_snapshots(config.database_path, wanted)
    by_ticker: dict[str, list[OptionChainSnapshot]] = {}
    for row in chain_rows:
        if wanted and row.ticker != wanted:
            continue
        if row.option_type != "put":
            continue
        by_ticker.setdefault(row.ticker, []).append(row)

    results: list[OptionIncomeTickerResult] = []
    for row_ticker, snapshots in sorted(by_ticker.items()):
        asset = latest_asset(config.database_path, row_ticker)
        if asset is None or asset.active_flag != 1:
            insert_data_quality_check(
                config.database_path,
                f"options:{row_ticker}",
                "warning",
                "unsupported_underlying",
                source="options_income",
            )
            results.append(
                OptionIncomeTickerResult(
                    ticker=row_ticker,
                    status="skipped",
                    review_count=0,
                    warnings=("unsupported_underlying",),
                )
            )
            continue

        current_price = _quote_price(config, row_ticker)
        range_state, range_level = _range_level(config, row_ticker)
        warnings: list[str] = []
        review_count = 0
        latest_snapshot_timestamp = max(snapshot.snapshot_timestamp for snapshot in snapshots)
        for snapshot in snapshots:
            if snapshot.snapshot_timestamp != latest_snapshot_timestamp:
                continue
            review = _review_snapshot(
                config,
                snapshot,
                asset.asset_role,
                current_price,
                range_state,
                range_level,
            )
            upsert_option_income_review(config.database_path, review)
            review_count += 1
            if review.risk_warnings:
                warnings.extend(part.strip() for part in review.risk_warnings.split(","))
        results.append(
            OptionIncomeTickerResult(
                ticker=row_ticker,
                status="computed" if review_count else "skipped",
                review_count=review_count,
                warnings=tuple(dict.fromkeys(warnings)),
            )
        )

    if wanted and wanted not in by_ticker:
        insert_data_quality_check(
            config.database_path,
            f"options:{wanted}",
            "warning",
            "missing_option_chain",
            source="options_income",
        )
        results.append(
            OptionIncomeTickerResult(
                ticker=wanted,
                status="skipped",
                review_count=0,
                warnings=("missing_option_chain",),
            )
        )

    return OptionIncomeComputeResult(results=tuple(results))


def _latest_income_reviews_for_risk(
    config: AppConfig,
    ticker: str | None = None,
) -> dict[str, list]:
    wanted = normalize_ticker(ticker) if ticker else None
    reviews = list_stored_option_income_reviews(config.database_path, wanted)
    latest_dates: dict[str, str] = {}
    for review in reviews:
        if wanted and review.ticker != wanted:
            continue
        latest_dates[review.ticker] = max(
            latest_dates.get(review.ticker, review.review_date),
            review.review_date,
        )

    selected: dict[str, list] = {}
    for review in reviews:
        if latest_dates.get(review.ticker) == review.review_date:
            selected.setdefault(review.ticker, []).append(review)
    return selected


def _safe_weight(numerator: float | None, denominator: float | None) -> float | None:
    if numerator is None or denominator is None or denominator <= 0:
        return None
    return numerator / denominator


def _portfolio_context_by_ticker(config: AppConfig) -> dict[str, object]:
    return {status.ticker: status for status in portfolio_statuses(config.database_path)}


def _global_portfolio_context(portfolio_context: dict[str, object]) -> tuple[float | None, float | None]:
    total_value = next(
        (
            status.total_portfolio_value
            for status in portfolio_context.values()
            if getattr(status, "total_portfolio_value", None) is not None
        ),
        None,
    )
    cash_available = next(
        (
            status.cash_available
            for status in portfolio_context.values()
            if getattr(status, "cash_available", None) is not None
        ),
        None,
    )
    return total_value, cash_available


def _scenario_pl(
    current_price: float | None,
    strike: float,
    premium_income: float,
    pct: float,
) -> float | None:
    if current_price is None:
        return None
    scenario_price = current_price * (1 + pct)
    intrinsic_loss = max(strike - scenario_price, 0) * OPTION_MULTIPLIER
    return premium_income - intrinsic_loss


def _max_contracts_advisory(
    config: AppConfig,
    assignment_notional: float,
    cash_requirement: float,
    total_portfolio_value: float | None,
    cash_available: float | None,
) -> int | None:
    if total_portfolio_value is None or total_portfolio_value <= 0:
        return None
    max_by_weight = int(
        (total_portfolio_value * config.options_max_single_contract_notional_weight)
        // assignment_notional
    )
    if cash_available is None or cash_requirement <= 0:
        return max_by_weight
    reserve = total_portfolio_value * config.options_minimum_cash_reserve_after_assignment
    cash_above_reserve = cash_available - reserve
    max_by_cash = int(cash_above_reserve // cash_requirement) if cash_above_reserve > 0 else 0
    return max(0, min(max_by_weight, max_by_cash))


def _risk_review_from_income(
    config: AppConfig,
    review,
    asset: Asset,
    portfolio_context: dict[str, object],
    total_assignment_notional: float,
) -> OptionRiskReview:
    risk_review_date = _today().isoformat()
    warnings: list[str] = ["read_only_advisory_only"]
    if review.risk_warnings:
        warnings.extend(part.strip() for part in review.risk_warnings.split(",") if part.strip())

    mid_premium = review.mid_premium
    strike = review.strike
    assignment_notional = review.assignment_notional or (strike * OPTION_MULTIPLIER)
    premium_income = mid_premium * OPTION_MULTIPLIER if mid_premium is not None else None
    cash_requirement = (
        assignment_notional - premium_income
        if premium_income is not None and assignment_notional is not None
        else None
    )
    max_loss = review.breakeven * OPTION_MULTIPLIER if review.breakeven is not None else None

    ticker_context = portfolio_context.get(review.ticker)
    global_total_value, global_cash_available = _global_portfolio_context(portfolio_context)
    total_portfolio_value = (
        getattr(ticker_context, "total_portfolio_value", None)
        if ticker_context is not None
        else None
    ) or global_total_value
    cash_available = (
        getattr(ticker_context, "cash_available", None) if ticker_context is not None else None
    ) or global_cash_available
    position_weight = (
        getattr(ticker_context, "position_weight", None) if ticker_context is not None else None
    )

    assignment_weight = _safe_weight(assignment_notional, total_portfolio_value)
    cash_after_assignment = (
        cash_available - cash_requirement
        if cash_available is not None and cash_requirement is not None
        else None
    )
    cash_reserve_after = _safe_weight(cash_after_assignment, total_portfolio_value)
    max_contracts = (
        _max_contracts_advisory(
            config,
            assignment_notional,
            cash_requirement,
            total_portfolio_value,
            cash_available,
        )
        if assignment_notional is not None and cash_requirement is not None
        else None
    )

    missing_portfolio_context = (
        total_portfolio_value is None
        or total_portfolio_value <= 0
        or cash_available is None
    )

    if missing_portfolio_context:
        warnings.append("missing_portfolio_context")
    if assignment_weight is not None and assignment_weight > config.options_max_single_contract_notional_weight:
        warnings.append("assignment_notional_above_single_contract_limit")
    total_assignment_weight = _safe_weight(total_assignment_notional, total_portfolio_value)
    if (
        total_assignment_weight is not None
        and total_assignment_weight > config.options_max_total_assignment_notional_weight
    ):
        warnings.append("total_assignment_notional_above_limit")
    if (
        cash_reserve_after is not None
        and cash_reserve_after < config.options_minimum_cash_reserve_after_assignment
    ):
        warnings.append("cash_reserve_below_threshold")
    if (
        position_weight is not None
        and assignment_weight is not None
        and position_weight + assignment_weight > config.portfolio_default_max_position_weight
    ):
        warnings.append("assignment_would_exceed_position_limit")
    if review.risk_warnings and any(
        code in review.risk_warnings
        for code in ("strike_above_range_level", "assignment_buffer_below_threshold")
    ):
        warnings.append("range_or_technical_risk")
    if (
        config.options_reference_instrument_risk_warning
        and normalize_asset_role(asset.asset_role) != "scoreable"
    ):
        warnings.append("reference_instrument_only")

    if (
        review.option_income_review_id is None
        or mid_premium is None
        or review.breakeven is None
        or assignment_notional is None
        or cash_requirement is None
    ):
        category = "not_reviewable"
    elif normalize_asset_role(asset.asset_role) != "scoreable":
        category = "reference_only_review"
    elif missing_portfolio_context:
        category = "portfolio_context_needed"
    elif cash_reserve_after is not None and cash_reserve_after < config.options_minimum_cash_reserve_after_assignment:
        category = "cash_reserve_breach"
    elif assignment_weight is not None and assignment_weight > config.options_max_single_contract_notional_weight:
        category = "assignment_notional_high"
    elif (
        position_weight is not None
        and assignment_weight is not None
        and position_weight + assignment_weight > config.portfolio_default_max_position_weight
    ):
        category = "assignment_would_exceed_position_limit"
    elif "range_or_technical_risk" in warnings:
        category = "range_or_technical_risk"
    else:
        category = "risk_review_ready"

    return OptionRiskReview(
        option_income_review_id=int(review.option_income_review_id or 0),
        ticker=review.ticker,
        review_date=review.review_date,
        risk_review_date=risk_review_date,
        expiration_date=review.expiration_date,
        option_type=review.option_type,
        strike=round(strike, 4),
        mid_premium=round(mid_premium, 4) if mid_premium is not None else None,
        breakeven=round(review.breakeven, 4) if review.breakeven is not None else None,
        current_price=review.current_price,
        assignment_notional=round(assignment_notional, 2) if assignment_notional is not None else None,
        premium_income=round(premium_income, 2) if premium_income is not None else None,
        cash_secured_requirement=round(cash_requirement, 2) if cash_requirement is not None else None,
        max_cash_secured_loss=round(max_loss, 2) if max_loss is not None else None,
        scenario_pl_5pct=_round_optional(
            _scenario_pl(review.current_price, strike, premium_income or 0, -0.05)
        ),
        scenario_pl_10pct=_round_optional(
            _scenario_pl(review.current_price, strike, premium_income or 0, -0.10)
        ),
        scenario_pl_20pct=_round_optional(
            _scenario_pl(review.current_price, strike, premium_income or 0, -0.20)
        ),
        projected_assignment_weight=_round_optional(assignment_weight, digits=6),
        cash_after_assignment=round(cash_after_assignment, 2)
        if cash_after_assignment is not None
        else None,
        cash_reserve_after_assignment=_round_optional(cash_reserve_after, digits=6),
        max_contracts_advisory=max_contracts,
        total_portfolio_value=round(total_portfolio_value, 2)
        if total_portfolio_value is not None
        else None,
        cash_available=round(cash_available, 2) if cash_available is not None else None,
        position_weight=_round_optional(position_weight, digits=6),
        risk_category=category,
        risk_warnings=_join_unique(tuple(warnings)),
        model_version=config.options_risk_model_version,
        source=config.options_risk_margin_model,
        as_of_date=risk_review_date,
        effective_date=risk_review_date,
    )


def _round_optional(value: float | None, digits: int = 2) -> float | None:
    return round(value, digits) if value is not None else None


def compute_options_risk(
    config: AppConfig,
    ticker: str | None = None,
) -> OptionRiskComputeResult:
    wanted = normalize_ticker(ticker) if ticker else None
    latest_reviews = _latest_income_reviews_for_risk(config, wanted)
    portfolio_context = _portfolio_context_by_ticker(config)
    total_assignment_notional = sum(
        review.assignment_notional or (review.strike * OPTION_MULTIPLIER)
        for reviews in latest_reviews.values()
        for review in reviews
    )
    results: list[OptionRiskTickerResult] = []

    for row_ticker, reviews in sorted(latest_reviews.items()):
        asset = latest_asset(config.database_path, row_ticker)
        if asset is None or asset.active_flag != 1:
            insert_data_quality_check(
                config.database_path,
                f"options_risk:{row_ticker}",
                "warning",
                "unsupported_underlying",
                source="options_risk",
            )
            results.append(
                OptionRiskTickerResult(
                    ticker=row_ticker,
                    status="skipped",
                    review_count=0,
                    warnings=("unsupported_underlying",),
                )
            )
            continue

        warnings: list[str] = []
        review_count = 0
        for review in reviews:
            risk_review = _risk_review_from_income(
                config,
                review,
                asset,
                portfolio_context,
                total_assignment_notional,
            )
            upsert_option_risk_review(config.database_path, risk_review)
            review_count += 1
            if risk_review.risk_warnings:
                warnings.extend(
                    part.strip()
                    for part in risk_review.risk_warnings.split(",")
                    if part.strip()
                )
        results.append(
            OptionRiskTickerResult(
                ticker=row_ticker,
                status="computed" if review_count else "skipped",
                review_count=review_count,
                warnings=tuple(dict.fromkeys(warnings)),
            )
        )

    if wanted and wanted not in latest_reviews:
        insert_data_quality_check(
            config.database_path,
            f"options_risk:{wanted}",
            "warning",
            "missing_option_income_review",
            source="options_risk",
        )
        results.append(
            OptionRiskTickerResult(
                ticker=wanted,
                status="skipped",
                review_count=0,
                warnings=("missing_option_income_review",),
            )
        )

    return OptionRiskComputeResult(results=tuple(results))


def _price_close(price: object) -> float | None:
    adjusted_close = getattr(price, "adjusted_close", None)
    close = getattr(price, "close", None)
    return adjusted_close if adjusted_close is not None else close


def _prices_after_review(config: AppConfig, ticker: str, review_date: str) -> list[object]:
    prices = list_prices(config.database_path, ticker)
    return [price for price in prices if price.price_date > review_date]


def _latest_price_on_or_before(
    prices: list[object],
    target_date: str,
) -> object | None:
    candidates = [price for price in prices if price.price_date <= target_date]
    return candidates[-1] if candidates else None


def _horizon_return(
    future_prices: list[object],
    trading_day_offset: int,
    entry_price: float | None,
) -> tuple[float | None, str | None]:
    if entry_price is None or entry_price <= 0:
        return None, None
    if len(future_prices) < trading_day_offset:
        return None, None
    price = future_prices[trading_day_offset - 1]
    close = _price_close(price)
    if close is None:
        return None, price.price_date
    return close / entry_price - 1, price.price_date


def _flag(value: bool | None) -> int | None:
    if value is None:
        return None
    return 1 if value else 0


def _linked_position_count(
    positions: list[OptionPositionLedger],
    review,
) -> int:
    return sum(
        1
        for position in positions
        if position.ticker == review.ticker
        and position.expiration_date == review.expiration_date
        and position.option_type == review.option_type
        and abs(position.strike - review.strike) < 0.01
    )


def _outcome_from_review(
    config: AppConfig,
    review,
    asset: Asset,
    positions: list[OptionPositionLedger],
) -> OptionReviewOutcome:
    outcome_date = _today().isoformat()
    prices = list_prices(config.database_path, review.ticker)
    future_prices = _prices_after_review(config, review.ticker, review.review_date)
    latest_price = prices[-1] if prices else None
    latest_close = _price_close(latest_price) if latest_price else None
    entry_price = review.current_price or latest_close
    warnings: list[str] = ["hypothetical_review_outcome", "underlying_price_proxy_only"]
    if config.options_outcome_use_underlying_prices_only:
        warnings.append("option_mark_to_market_not_used")
    if normalize_asset_role(asset.asset_role) != "scoreable":
        warnings.append("reference_instrument_only")
    linked_positions = _linked_position_count(positions, review)
    if not linked_positions:
        warnings.append("no_manual_option_position")
    if not prices:
        warnings.append("missing_underlying_price_history")

    return_5d, price_date_5d = _horizon_return(future_prices, 5, entry_price)
    return_20d, price_date_20d = _horizon_return(future_prices, 20, entry_price)
    completed: list[str] = []
    pending: list[str] = []
    if "5d" in config.options_outcome_horizons:
        (completed if return_5d is not None else pending).append("5d")
    if "20d" in config.options_outcome_horizons:
        (completed if return_20d is not None else pending).append("20d")

    expiration_price = _latest_price_on_or_before(prices, review.expiration_date)
    expiration_close = _price_close(expiration_price) if expiration_price else None
    expiration_mature = (
        expiration_price is not None and expiration_price.price_date >= review.review_date
        and review.expiration_date <= outcome_date
    )
    above_strike: bool | None = None
    above_breakeven: bool | None = None
    expiration_status = "pending"
    if expiration_mature and expiration_close is not None:
        above_strike = expiration_close >= review.strike
        above_breakeven = (
            expiration_close >= review.breakeven
            if review.breakeven is not None
            else None
        )
        if above_strike:
            expiration_status = "above_strike"
        elif above_breakeven:
            expiration_status = "below_strike_above_breakeven"
        else:
            expiration_status = "below_breakeven"
        if "expiration" in config.options_outcome_horizons:
            completed.append("expiration")
    elif "expiration" in config.options_outcome_horizons:
        pending.append("expiration")

    if not future_prices:
        touched_strike = None
        touched_breakeven = None
        max_favorable = None
        max_adverse = None
    else:
        lows = [price.low for price in future_prices if price.low is not None]
        highs = [price.high for price in future_prices if price.high is not None]
        touched_strike = min(lows) <= review.strike if lows else None
        touched_breakeven = (
            min(lows) <= review.breakeven
            if lows and review.breakeven is not None
            else None
        )
        max_favorable = (
            max(highs) / entry_price - 1
            if highs and entry_price is not None and entry_price > 0
            else None
        )
        max_adverse = (
            min(lows) / entry_price - 1
            if lows and entry_price is not None and entry_price > 0
            else None
        )

    latest_return = (
        latest_close / entry_price - 1
        if latest_close is not None and entry_price is not None and entry_price > 0
        else None
    )
    outcome_status = "completed" if "expiration" in completed else (
        "partial" if completed else "pending"
    )
    if price_date_5d is None and "5d" in completed:
        warnings.append("missing_5d_close")
    if price_date_20d is None and "20d" in completed:
        warnings.append("missing_20d_close")

    return OptionReviewOutcome(
        option_income_review_id=int(review.option_income_review_id or 0),
        ticker=review.ticker,
        review_date=review.review_date,
        outcome_date=outcome_date,
        expiration_date=review.expiration_date,
        option_type=review.option_type,
        strike=round(review.strike, 4),
        mid_premium=review.mid_premium,
        breakeven=review.breakeven,
        review_price=entry_price,
        latest_underlying_price=latest_close,
        latest_underlying_price_date=latest_price.price_date if latest_price else None,
        expiration_close=expiration_close,
        expiration_price_date=expiration_price.price_date if expiration_price else None,
        expiration_status=expiration_status,
        outcome_status=outcome_status,
        completed_horizons=_join_unique(completed),
        pending_horizons=_join_unique(pending),
        return_5d=_round_optional(return_5d, digits=6),
        return_20d=_round_optional(return_20d, digits=6),
        return_to_latest=_round_optional(latest_return, digits=6),
        above_strike_flag=_flag(above_strike),
        above_breakeven_flag=_flag(above_breakeven),
        touched_strike_flag=_flag(touched_strike),
        touched_breakeven_flag=_flag(touched_breakeven),
        max_favorable_excursion=_round_optional(max_favorable, digits=6),
        max_adverse_excursion=_round_optional(max_adverse, digits=6),
        linked_position_count=linked_positions,
        data_warnings=_join_unique(warnings),
        model_version=config.options_outcome_model_version,
        source="options_outcome",
        as_of_date=outcome_date,
        effective_date=latest_price.price_date if latest_price else outcome_date,
    )


def compute_options_outcomes(
    config: AppConfig,
    ticker: str | None = None,
) -> OptionOutcomeComputeResult:
    wanted = normalize_ticker(ticker) if ticker else None
    reviews = [
        review
        for review in list_stored_option_income_reviews(config.database_path, wanted)
        if review.option_type == "put"
    ]
    by_ticker: dict[str, list] = {}
    for review in reviews:
        by_ticker.setdefault(review.ticker, []).append(review)
    positions = list_option_positions(config.database_path, wanted)

    results: list[OptionOutcomeTickerResult] = []
    for row_ticker, ticker_reviews in sorted(by_ticker.items()):
        asset = latest_asset(config.database_path, row_ticker)
        if asset is None or asset.active_flag != 1:
            insert_data_quality_check(
                config.database_path,
                f"options_outcome:{row_ticker}",
                "warning",
                "unsupported_underlying",
                source="options_outcome",
            )
            results.append(
                OptionOutcomeTickerResult(
                    ticker=row_ticker,
                    status="skipped",
                    outcome_count=0,
                    warnings=("unsupported_underlying",),
                )
            )
            continue
        warnings: list[str] = []
        outcome_count = 0
        for review in ticker_reviews:
            if review.option_income_review_id is None:
                warnings.append("missing_option_income_review_id")
                continue
            outcome = _outcome_from_review(config, review, asset, positions)
            upsert_option_review_outcome(config.database_path, outcome)
            outcome_count += 1
            if outcome.data_warnings:
                warnings.extend(
                    part.strip()
                    for part in outcome.data_warnings.split(",")
                    if part.strip()
                )
        results.append(
            OptionOutcomeTickerResult(
                ticker=row_ticker,
                status="computed" if outcome_count else "skipped",
                outcome_count=outcome_count,
                warnings=tuple(dict.fromkeys(warnings)),
            )
        )

    if wanted and wanted not in by_ticker:
        insert_data_quality_check(
            config.database_path,
            f"options_outcome:{wanted}",
            "warning",
            "missing_option_income_review",
            source="options_outcome",
        )
        results.append(
            OptionOutcomeTickerResult(
                ticker=wanted,
                status="skipped",
                outcome_count=0,
                warnings=("missing_option_income_review",),
            )
        )

    return OptionOutcomeComputeResult(results=tuple(results))


def _position_matches_review(
    position: OptionPositionLedger,
    review: object,
) -> bool:
    return (
        position.ticker == review.ticker
        and position.option_type == review.option_type
        and position.expiration_date == review.expiration_date
        and abs(position.strike - review.strike) < 0.0001
    )


def _find_linked_income_review(
    position: OptionPositionLedger,
    reviews: list[object],
) -> object | None:
    matches = [review for review in reviews if _position_matches_review(position, review)]
    if not matches:
        return None
    return min(
        matches,
        key=lambda review: (
            abs(
                (
                    date.fromisoformat(position.open_date)
                    - date.fromisoformat(review.review_date)
                ).days
            ),
            review.review_date,
        ),
    )


def _latest_chain_mark(
    config: AppConfig,
    position: OptionPositionLedger,
) -> tuple[float | None, str | None]:
    snapshots = [
        snapshot
        for snapshot in list_option_chain_snapshots(config.database_path, position.ticker)
        if snapshot.option_type == position.option_type
        and snapshot.expiration_date == position.expiration_date
        and abs(snapshot.strike - position.strike) < 0.0001
    ]
    if not snapshots:
        return None, None
    latest = max(snapshots, key=lambda snapshot: snapshot.snapshot_timestamp)
    if latest.mark is not None:
        return latest.mark, latest.snapshot_timestamp
    return (latest.bid + latest.ask) / 2, latest.snapshot_timestamp


def _expiration_close_for_position(
    config: AppConfig,
    position: OptionPositionLedger,
) -> float | None:
    prices = list_prices(config.database_path, position.ticker)
    expiration_price = _latest_price_on_or_before(prices, position.expiration_date)
    return _price_close(expiration_price) if expiration_price else None


def _lifecycle_status_from_position(
    position: OptionPositionLedger,
    expiration_close: float | None,
) -> tuple[str, list[str]]:
    warnings: list[str] = []
    status = (position.position_status or "").strip().lower()
    if position.roll_from_position_id or position.roll_to_position_id or status == "rolled":
        return "rolled", warnings
    if position.assigned_flag:
        return "assigned", warnings
    if position.close_date:
        return "closed", warnings
    if status == "closed":
        return "closed", warnings
    if status == "assigned":
        return "assigned", warnings
    try:
        expired = date.fromisoformat(position.expiration_date) < _today()
    except ValueError:
        warnings.append("malformed_expiration_date")
        expired = False
    if expired:
        if expiration_close is None:
            warnings.append("missing_expiration_underlying_price")
            return "expiration_status_needed", warnings
        if expiration_close >= position.strike:
            return "expired_worthless", warnings
        warnings.append("assignment_status_needed")
        return "expired_below_strike_assignment_unknown", warnings
    return "open", warnings


def _lifecycle_review_from_position(
    config: AppConfig,
    position: OptionPositionLedger,
    reviews: list[object],
    asset: Asset | None,
) -> OptionPositionLifecycleReview:
    multiplier = config.options_option_multiplier
    lifecycle_review_date = _today().isoformat()
    warnings: list[str] = ["read_only_lifecycle_review"]
    if asset is None or asset.active_flag != 1:
        warnings.append("unsupported_underlying")
    elif normalize_asset_role(asset.asset_role) != "scoreable":
        warnings.append("reference_instrument_only")
    if position.option_type != "put" or position.side != "short_put":
        warnings.append("non_sell_put_position")

    linked_review = _find_linked_income_review(position, reviews)
    linked_review_id = int(linked_review.option_income_review_id) if linked_review else None
    linked_risk_id = (
        latest_option_risk_review_id_for_income_review(
            config.database_path,
            linked_review_id,
        )
        if linked_review_id is not None
        else None
    )
    linked_outcome_id = (
        latest_option_review_outcome_id_for_income_review(
            config.database_path,
            linked_review_id,
        )
        if linked_review_id is not None
        else None
    )
    if linked_review_id is None:
        warnings.append("unmatched_option_review")

    expiration_close = _expiration_close_for_position(config, position)
    lifecycle_status, status_warnings = _lifecycle_status_from_position(
        position,
        expiration_close,
    )
    warnings.extend(status_warnings)

    premium_income = position.premium * position.contracts * multiplier
    fees = position.fees or 0.0
    realized_pl: float | None = None
    open_pl_proxy: float | None = None
    latest_mark: float | None = None
    latest_mark_timestamp: str | None = None
    assignment_price = position.assignment_price or position.strike
    assignment_notional = position.strike * position.contracts * multiplier
    cash_requirement = assignment_notional - premium_income

    if lifecycle_status in {"closed", "rolled"}:
        if position.close_price is None:
            warnings.append("missing_close_price")
        else:
            realized_pl = (
                (position.premium - position.close_price)
                * position.contracts
                * multiplier
                - fees
            )
    elif lifecycle_status == "expired_worthless":
        realized_pl = premium_income - fees
    elif lifecycle_status == "assigned":
        realized_pl = premium_income - fees
        assignment_notional = assignment_price * position.contracts * multiplier
        if position.underlying_cost_basis is None:
            warnings.append("missing_underlying_cost_basis")
    elif lifecycle_status == "open":
        latest_mark, latest_mark_timestamp = _latest_chain_mark(config, position)
        if latest_mark is None:
            warnings.append("missing_option_mark")
        else:
            open_pl_proxy = (
                (position.premium - latest_mark)
                * position.contracts
                * multiplier
                - fees
            )

    underlying_shares = position.underlying_shares
    if underlying_shares is None and position.assigned_flag:
        underlying_shares = position.contracts * multiplier
    underlying_cost_basis = position.underlying_cost_basis
    if underlying_cost_basis is None and position.assigned_flag:
        underlying_cost_basis = assignment_price - position.premium

    return OptionPositionLifecycleReview(
        position_key=position.position_key,
        position_id=position.position_id,
        ticker=position.ticker,
        lifecycle_review_date=lifecycle_review_date,
        open_date=position.open_date,
        expiration_date=position.expiration_date,
        option_type=position.option_type,
        side=position.side,
        strike=round(position.strike, 4),
        contracts=position.contracts,
        premium=position.premium,
        close_date=position.close_date,
        close_price=position.close_price,
        assigned_flag=position.assigned_flag,
        assignment_price=position.assignment_price,
        fees=position.fees,
        lifecycle_status=lifecycle_status,
        realized_pl=_round_optional(realized_pl),
        open_pl_proxy=_round_optional(open_pl_proxy),
        assignment_notional=_round_optional(assignment_notional),
        cash_secured_requirement=_round_optional(cash_requirement),
        premium_income=_round_optional(premium_income),
        latest_option_mark=_round_optional(latest_mark, digits=4),
        latest_option_mark_timestamp=latest_mark_timestamp,
        underlying_assignment_date=position.underlying_assignment_date,
        underlying_shares=underlying_shares,
        underlying_cost_basis=_round_optional(underlying_cost_basis, digits=4),
        linked_option_income_review_id=linked_review_id,
        linked_option_risk_review_id=linked_risk_id,
        linked_option_review_outcome_id=linked_outcome_id,
        roll_from_position_id=position.roll_from_position_id,
        roll_to_position_id=position.roll_to_position_id,
        risk_warnings=_join_unique(tuple(warnings)),
        model_version=config.options_lifecycle_model_version,
        source=config.options_realized_pl_model_version,
        as_of_date=lifecycle_review_date,
        effective_date=lifecycle_review_date,
    )


def compute_options_lifecycle(
    config: AppConfig,
    ticker: str | None = None,
) -> OptionLifecycleComputeResult:
    wanted = normalize_ticker(ticker) if ticker else None
    positions = list_option_positions(config.database_path, wanted)
    reviews = list_stored_option_income_reviews(config.database_path, wanted)
    by_ticker: dict[str, list[OptionPositionLedger]] = {}
    for position in positions:
        by_ticker.setdefault(position.ticker, []).append(position)

    results: list[OptionLifecycleTickerResult] = []
    for row_ticker, ticker_positions in sorted(by_ticker.items()):
        asset = latest_asset(config.database_path, row_ticker)
        ticker_reviews = [review for review in reviews if review.ticker == row_ticker]
        warnings: list[str] = []
        lifecycle_count = 0
        for position in ticker_positions:
            review = _lifecycle_review_from_position(
                config,
                position,
                ticker_reviews,
                asset,
            )
            upsert_option_position_lifecycle_review(config.database_path, review)
            lifecycle_count += 1
            if review.risk_warnings:
                warnings.extend(
                    part.strip()
                    for part in review.risk_warnings.split(",")
                    if part.strip()
                )
        results.append(
            OptionLifecycleTickerResult(
                ticker=row_ticker,
                status="computed" if lifecycle_count else "skipped",
                lifecycle_count=lifecycle_count,
                warnings=tuple(dict.fromkeys(warnings)),
            )
        )

    if wanted and wanted not in by_ticker:
        insert_data_quality_check(
            config.database_path,
            f"options_lifecycle:{wanted}",
            "warning",
            "missing_option_position",
            source="options_lifecycle",
        )
        results.append(
            OptionLifecycleTickerResult(
                ticker=wanted,
                status="skipped",
                lifecycle_count=0,
                warnings=("missing_option_position",),
            )
        )
    return OptionLifecycleComputeResult(results=tuple(results))


def option_provider_status(
    config: AppConfig,
    *,
    check_connectivity: bool = False,
) -> OptionProviderStatus:
    from .ibkr_provider import _import_ibapi, check_ibkr_status

    _EClient, _Contract, _EWrapper, import_error = _import_ibapi()
    ibapi_status = _classify_import_error(import_error)
    ibkr_warnings: tuple[str, ...] = ()
    connectivity = "not_checked"
    if check_connectivity and ibapi_status == "ok":
        status = check_ibkr_status(config)
        connectivity = "connected" if status.connected else "not_connected"
        ibkr_warnings = status.warnings
    elif check_connectivity:
        connectivity = "not_available"

    statuses = option_income_statuses(config.database_path)
    fetch_tickers = tuple(asset.ticker for asset in option_fetch_assets(config, max_tickers=0))
    non_actionable_tickers = set(valid_non_actionable_option_chain_tickers(config))
    effective_fetch_tickers = tuple(
        ticker for ticker in fetch_tickers if ticker not in non_actionable_tickers
    )
    loaded_tickers = {status.ticker for status in statuses if status.option_chain_rows}
    missing = tuple(ticker for ticker in effective_fetch_tickers if ticker not in loaded_tickers)
    snapshots = list_option_chain_snapshots(config.database_path)
    review_count = sum(1 for status in statuses if status.review_date)
    chain_count = len(snapshots)
    latest_chain = max((snapshot.snapshot_timestamp for snapshot in snapshots), default=None)
    latest_review = max((status.review_date for status in statuses if status.review_date), default=None)
    cache_count, latest_cache = _cache_file_status(config.options_chain_cache_dir)

    warnings: list[str] = []
    blocked_reason = _classify_import_error(import_error)
    if blocked_reason != "ok":
        warnings.append(blocked_reason)
    elif check_connectivity and connectivity != "connected":
        blocked_reason = _classify_warnings(ibkr_warnings) or "ibkr_not_connected"
        warnings.append(blocked_reason)
    elif not chain_count and effective_fetch_tickers:
        blocked_reason = "no_chain_rows"
        warnings.append(blocked_reason)
    elif missing:
        blocked_reason = "missing_option_chain"
        warnings.append(blocked_reason)
    else:
        blocked_reason = None

    if ibkr_warnings:
        warnings.extend(ibkr_warnings)
    readiness = "ready" if blocked_reason is None else "blocked"
    return OptionProviderStatus(
        source=config.options_chain_source,
        ibkr_host=config.ibkr_host,
        ibkr_port=config.ibkr_paper_port,
        ibkr_client_id=config.ibkr_client_id + 4,
        ibapi_status=ibapi_status,
        ibapi_error=import_error,
        ibkr_connectivity_status=connectivity,
        ibkr_warnings=ibkr_warnings,
        chain_rows=chain_count,
        review_rows=review_count,
        fetch_universe_tickers=fetch_tickers,
        missing_chain_tickers=missing,
        latest_chain_snapshot=latest_chain,
        latest_review_date=latest_review,
        cache_dir=config.options_chain_cache_dir,
        cache_exists=config.options_chain_cache_dir.exists(),
        cache_file_count=cache_count,
        latest_cache_timestamp=latest_cache,
        readiness_status=readiness,
        blocked_reason=blocked_reason,
        warnings=tuple(dict.fromkeys(warnings)),
    )


def _minimum_option_review_count(config: AppConfig, tickers: tuple[str, ...]) -> int:
    ticker_set = set(tickers)
    return sum(
        1
        for status in option_income_statuses(config.database_path)
        if status.ticker in ticker_set and status.review_date
    )


def option_chain_activation_status(config: AppConfig) -> OptionChainActivationStatus:
    provider = option_provider_status(config, check_connectivity=False)
    validation = validate_options_chain_backfill(config)
    minimum_tickers = validation.minimum_tickers
    minimum_review_count = _minimum_option_review_count(config, minimum_tickers)
    ibapi_repair_needed = provider.blocked_reason in {
        "ibapi_permission_denied",
        "ibapi_missing",
        "ibapi_unavailable",
    }

    blocked_reason: str | None = None
    if minimum_review_count > 0:
        activation = "active"
    elif validation.invalid_row_count:
        activation = "blocked"
        blocked_reason = "invalid_option_backfill_rows"
    elif validation.minimum_valid_tickers:
        if validation.minimum_projected_loaded_ticker_count >= max(validation.minimum_ticker_count, 1):
            activation = "ready_to_activate"
        else:
            activation = "partial_ready"
            blocked_reason = "minimum_option_chain_coverage_incomplete"
    else:
        activation = "blocked"
        blocked_reason = (
            provider.blocked_reason
            or validation.blocked_reason
            or "minimum_option_chain_rows_missing"
        )

    next_commands = (
        "python -m target_opportunity_monitor option-provider-repair-plan --source ibkr",
        "python -m target_opportunity_monitor export-options-chain-backfill-template --minimum-set",
        "python -m target_opportunity_monitor validate-options-chain-backfill",
        "python -m target_opportunity_monitor activate-options-chain-data",
        "python -m target_opportunity_monitor activate-options-chain-data --confirm --allow-partial",
    )
    warnings: list[str] = []
    if ibapi_repair_needed:
        warnings.append("ibapi_repair_needed")
    if validation.minimum_missing_tickers:
        warnings.append(
            "minimum_option_chain_missing:"
            + ",".join(validation.minimum_missing_tickers)
        )
    if validation.invalid_reasons:
        warnings.append("invalid_option_backfill_rows")
    if blocked_reason:
        warnings.append(blocked_reason)

    denominator = validation.minimum_ticker_count
    coverage = f"{validation.minimum_projected_loaded_ticker_count}/{denominator}"
    return OptionChainActivationStatus(
        activation_status=activation,
        blocked_reason=blocked_reason,
        provider_status=provider,
        validation=validation,
        minimum_tickers=minimum_tickers,
        minimum_loaded_tickers=validation.minimum_loaded_tickers,
        minimum_valid_tickers=validation.minimum_valid_tickers,
        minimum_missing_tickers=validation.minimum_missing_tickers,
        minimum_option_chain_coverage=coverage,
        minimum_option_review_count=minimum_review_count,
        ibapi_repair_needed=ibapi_repair_needed,
        next_commands=next_commands,
        warnings=tuple(dict.fromkeys(warnings)),
    )


def build_option_chain_activation_status_text(config: AppConfig) -> str:
    status = option_chain_activation_status(config)
    provider = status.provider_status
    validation = status.validation
    lines = [
        "Option Chain Activation Status",
        f"Activation status: {status.activation_status}",
        f"Activation blocked reason: {status.blocked_reason or 'none'}",
        f"Provider readiness: {provider.readiness_status}",
        f"Provider blocked reason: {provider.blocked_reason or 'none'}",
        f"ibapi status: {provider.ibapi_status}",
        f"ibapi error: {provider.ibapi_error or 'none'}",
        f"IBKR host: {provider.ibkr_host}",
        f"IBKR paper port: {provider.ibkr_port}",
        f"IBKR option client id: {provider.ibkr_client_id}",
        f"Minimum tickers: {', '.join(status.minimum_tickers) if status.minimum_tickers else 'none'}",
        f"Minimum chain coverage: {status.minimum_option_chain_coverage}",
        f"Minimum loaded tickers: {', '.join(status.minimum_loaded_tickers) if status.minimum_loaded_tickers else 'none'}",
        f"Minimum valid backfill tickers: {', '.join(status.minimum_valid_tickers) if status.minimum_valid_tickers else 'none'}",
        f"Minimum missing tickers: {', '.join(status.minimum_missing_tickers) if status.minimum_missing_tickers else 'none'}",
        f"Minimum option review count: {status.minimum_option_review_count}",
        f"Backfill valid rows: {validation.valid_row_count}",
        f"Backfill invalid rows: {validation.invalid_row_count}",
        f"Backfill blank placeholders: {validation.blank_placeholder_count}",
        f"Backfill apply ready: {validation.apply_ready}",
        f"Backfill blocked reason: {validation.blocked_reason or 'none'}",
        f"ibapi repair needed: {status.ibapi_repair_needed}",
        f"Warnings: {', '.join(status.warnings) if status.warnings else 'none'}",
        "",
        "Next commands:",
    ]
    lines.extend(f"- {command}" for command in status.next_commands)
    if validation.invalid_reasons:
        lines.append("")
        lines.append("Invalid rows:")
        lines.extend(f"- {reason}" for reason in validation.invalid_reasons)
    return "\n".join(lines)


def build_option_provider_repair_plan_text(
    config: AppConfig,
    *,
    source: str = "ibkr",
) -> str:
    requested = source.strip().lower()
    if requested != "ibkr":
        return (
            "Option Provider Repair Plan\n"
            f"Source: {requested}\n"
            f"Blocked reason: unsupported_option_provider:{requested}"
        )
    status = option_provider_status(config, check_connectivity=True)
    lines = [
        "Option Provider Repair Plan",
        "Source: ibkr",
        f"Current blocker: {status.blocked_reason or 'none'}",
        f"ibapi status: {status.ibapi_status}",
        f"ibapi import error: {status.ibapi_error or 'none'}",
        f"IBKR connectivity: {status.ibkr_connectivity_status}",
        f"IBKR host: {status.ibkr_host}",
        f"IBKR paper port: {status.ibkr_port}",
        f"IBKR option client id: {status.ibkr_client_id}",
        "",
        "This command is diagnostic only. It does not change Windows permissions, install packages, or modify IBKR settings.",
        "",
        "Suggested repair path:",
    ]
    if status.blocked_reason == "ibapi_permission_denied":
        lines.extend(
            (
                "- Fix the local Python package/file permission that blocks importing ibapi.",
                "- Reinstall or repair ibapi in the same Python environment used by TOM if needed.",
                "- Re-run `python -m target_opportunity_monitor diagnose-options-provider --source ibkr`.",
            )
        )
    elif status.blocked_reason == "ibapi_missing":
        lines.extend(
            (
                "- Install the IBKR Python API package in TOM's Python environment.",
                "- Re-run the option provider diagnostic command.",
            )
        )
    elif status.blocked_reason == "ibkr_not_connected":
        lines.extend(
            (
                "- Start IBKR Gateway or TWS paper trading.",
                "- Confirm API socket access is enabled and the configured paper port is correct.",
                "- Re-run `python -m target_opportunity_monitor test-options-provider --source ibkr --ticker SOXL`.",
            )
        )
    else:
        lines.extend(
            (
                "- If IBKR remains unavailable, use the source-backed CSV backfill workflow.",
                "- Export the minimum template and fill real bid/ask rows from a broker/provider export.",
            )
        )
    lines.extend(
        (
            "",
            "CSV fallback while IBKR is blocked:",
            "- python -m target_opportunity_monitor export-options-chain-backfill-template --minimum-set",
            "- python -m target_opportunity_monitor validate-options-chain-backfill",
            "- python -m target_opportunity_monitor activate-options-chain-data --confirm --allow-partial",
        )
    )
    return "\n".join(lines)


def build_option_chain_minimum_backfill_plan_text(config: AppConfig) -> str:
    status = option_chain_activation_status(config)
    lines = [
        "Option Chain Minimum Backfill Plan",
        f"Minimum tickers: {', '.join(status.minimum_tickers) if status.minimum_tickers else 'none'}",
        f"Minimum chain coverage: {status.minimum_option_chain_coverage}",
        f"Minimum valid backfill tickers: {', '.join(status.minimum_valid_tickers) if status.minimum_valid_tickers else 'none'}",
        f"Minimum missing tickers: {', '.join(status.minimum_missing_tickers) if status.minimum_missing_tickers else 'none'}",
        f"Minimum option review count: {status.minimum_option_review_count}",
        f"Source-export directory: {status.validation.source_dir}",
        f"Source-export files: {len(status.validation.source_export_files)}",
        f"Valid rows: {status.validation.valid_row_count}",
        f"Blank placeholders: {status.validation.blank_placeholder_count}",
        f"Invalid rows: {status.validation.invalid_row_count}",
        f"Activation status: {status.activation_status}",
        f"Activation blocked reason: {status.blocked_reason or 'none'}",
        "",
        "Command sequence:",
        "- python -m target_opportunity_monitor export-options-chain-backfill-template --minimum-set",
        "- Fill source-backed bid/ask rows for the minimum tickers.",
        "- python -m target_opportunity_monitor validate-options-chain-backfill",
        "- python -m target_opportunity_monitor activate-options-chain-data",
        "- python -m target_opportunity_monitor activate-options-chain-data --confirm --allow-partial",
    ]
    return "\n".join(lines)


def activate_options_chain_data(
    config: AppConfig,
    *,
    confirm: bool = False,
    allow_partial: bool = False,
    source_dir: Path | None = None,
) -> OptionChainActivationResult:
    validation = validate_options_chain_backfill(config, source_dir=source_dir)
    warnings: list[str] = list(validation.invalid_reasons)
    minimum_projected = validation.minimum_projected_loaded_ticker_count
    minimum_required = validation.minimum_ticker_count

    blocked_reason: str | None = None
    if validation.invalid_row_count:
        blocked_reason = "invalid_option_backfill_rows"
    elif not validation.valid_row_count:
        blocked_reason = "no_valid_option_backfill_rows"
    elif minimum_projected <= len(validation.minimum_loaded_tickers):
        blocked_reason = "minimum_option_chain_coverage_does_not_improve"
    elif not allow_partial and minimum_projected < minimum_required:
        blocked_reason = "minimum_option_chain_coverage_incomplete"

    if blocked_reason:
        warnings.append(blocked_reason)
        return OptionChainActivationResult(
            confirmed=confirm,
            allow_partial=allow_partial,
            success=False,
            status="blocked",
            blocked_reason=blocked_reason,
            validation=validation,
            warnings=tuple(dict.fromkeys(warnings)),
        )

    if not confirm:
        return OptionChainActivationResult(
            confirmed=False,
            allow_partial=allow_partial,
            success=True,
            status="dry_run_ready",
            blocked_reason=None,
            validation=validation,
            warnings=tuple(dict.fromkeys(warnings)),
        )

    imported = import_options_chain_source_exports(config, source_dir=source_dir)
    warnings.extend(imported.warnings)
    review_result = compute_options_income(config)
    activation = option_chain_activation_status(config)
    if not activation.minimum_option_review_count:
        warnings.append("no_option_income_reviews_produced")
        return OptionChainActivationResult(
            confirmed=True,
            allow_partial=allow_partial,
            success=False,
            status="blocked",
            blocked_reason="no_option_income_reviews_produced",
            validation=validation,
            imported_count=imported.imported_count,
            computed_review_tickers=review_result.computed_count,
            minimum_option_review_count=activation.minimum_option_review_count,
            warnings=tuple(dict.fromkeys(warnings)),
        )

    return OptionChainActivationResult(
        confirmed=True,
        allow_partial=allow_partial,
        success=True,
        status="activated",
        blocked_reason=None,
        validation=validation,
        imported_count=imported.imported_count,
        computed_review_tickers=review_result.computed_count,
        minimum_option_review_count=activation.minimum_option_review_count,
        warnings=tuple(dict.fromkeys(warnings)),
    )


def build_option_chain_activation_apply_text(
    config: AppConfig,
    *,
    confirm: bool = False,
    allow_partial: bool = False,
    source_dir: Path | None = None,
) -> tuple[str, OptionChainActivationResult]:
    result = activate_options_chain_data(
        config,
        confirm=confirm,
        allow_partial=allow_partial,
        source_dir=source_dir,
    )
    lines = [
        "Option Chain Activation Apply",
        f"Mode: {'confirm' if confirm else 'dry_run'}",
        f"Allow partial: {allow_partial}",
        f"Status: {result.status}",
        f"Success: {result.success}",
        f"Blocked reason: {result.blocked_reason or 'none'}",
        f"Valid rows: {result.validation.valid_row_count}",
        f"Invalid rows: {result.validation.invalid_row_count}",
        f"Blank placeholders: {result.validation.blank_placeholder_count}",
        "Minimum projected chain coverage: "
        f"{result.validation.minimum_projected_loaded_ticker_count}/"
        f"{result.validation.minimum_ticker_count}",
        "Minimum valid backfill tickers: "
        + (
            ", ".join(result.validation.minimum_valid_tickers)
            if result.validation.minimum_valid_tickers
            else "none"
        ),
        "Minimum missing tickers: "
        + (
            ", ".join(result.validation.minimum_missing_tickers)
            if result.validation.minimum_missing_tickers
            else "none"
        ),
        f"Imported rows: {result.imported_count}",
        f"Computed review tickers: {result.computed_review_tickers}",
        f"Minimum option review count: {result.minimum_option_review_count}",
        f"Warnings: {', '.join(result.warnings) if result.warnings else 'none'}",
    ]
    if not confirm:
        lines.append("Dry run only: no source exports were imported and no reviews were recomputed.")
    return "\n".join(lines), result


def build_option_provider_status_text(
    config: AppConfig,
    *,
    check_connectivity: bool = True,
) -> str:
    status = option_provider_status(config, check_connectivity=check_connectivity)
    validation = validate_options_chain_backfill(config)
    non_actionable = validate_option_chain_non_actionable_decisions(config)
    activation = option_chain_activation_status(config)
    lines = [
        "Option Provider Health",
        f"Source: {status.source}",
        f"Readiness: {status.readiness_status}",
        f"Blocked reason: {status.blocked_reason or 'none'}",
        f"IBKR host: {status.ibkr_host}",
        f"IBKR paper port: {status.ibkr_port}",
        f"IBKR option client id: {status.ibkr_client_id}",
        f"ibapi status: {status.ibapi_status}",
        f"IBKR connectivity: {status.ibkr_connectivity_status}",
        f"Warnings: {', '.join(status.warnings) if status.warnings else 'none'}",
        f"Cache directory: {status.cache_dir}",
        f"Cache exists: {status.cache_exists}",
        f"Cache files: {status.cache_file_count}",
        f"Latest cache timestamp: {status.latest_cache_timestamp or 'none'}",
        f"Chain rows: {status.chain_rows}",
        f"Review rows: {status.review_rows}",
        f"Latest chain snapshot: {status.latest_chain_snapshot or 'none'}",
        f"Latest review date: {status.latest_review_date or 'none'}",
        f"Fetch-universe tickers: {len(status.fetch_universe_tickers)}",
        f"Missing chain tickers: {', '.join(status.missing_chain_tickers) if status.missing_chain_tickers else 'none'}",
        "Non-actionable decision file: "
        f"{non_actionable.path}",
        "Non-actionable tickers: "
        f"{', '.join(non_actionable.valid_tickers) if non_actionable.valid_tickers else 'none'}",
        f"Non-actionable valid decisions: {non_actionable.valid_decision_count}",
        f"Non-actionable invalid decisions: {non_actionable.invalid_decision_count}",
        f"Non-actionable blank placeholders: {non_actionable.blank_placeholder_count}",
        f"Source-export directory: {validation.source_dir}",
        f"Source-export files: {len(validation.source_export_files)}",
        f"Backfill valid rows: {validation.valid_row_count}",
        f"Backfill blank placeholders: {validation.blank_placeholder_count}",
        f"Backfill invalid rows: {validation.invalid_row_count}",
        f"Backfill valid tickers: {', '.join(validation.valid_tickers) if validation.valid_tickers else 'none'}",
        f"Projected chain coverage: {validation.projected_loaded_ticker_count}/{validation.fetch_universe_ticker_count}",
        "Minimum projected chain coverage: "
        f"{validation.minimum_projected_loaded_ticker_count}/"
        f"{validation.minimum_ticker_count}",
        f"Minimum valid tickers: {', '.join(validation.minimum_valid_tickers) if validation.minimum_valid_tickers else 'none'}",
        f"Minimum missing tickers: {', '.join(validation.minimum_missing_tickers) if validation.minimum_missing_tickers else 'none'}",
        f"Backfill apply ready: {validation.apply_ready}",
        f"Backfill blocked reason: {validation.blocked_reason or 'none'}",
        f"Option activation status: {activation.activation_status}",
        f"Option activation blocked reason: {activation.blocked_reason or 'none'}",
        f"Minimum option review count: {activation.minimum_option_review_count}",
        f"ibapi repair needed: {activation.ibapi_repair_needed}",
    ]
    if validation.invalid_reasons:
        lines.append("Invalid rows:")
        lines.extend(f"- {reason}" for reason in validation.invalid_reasons)
    return "\n".join(lines)


def build_options_provider_diagnostics_text(
    config: AppConfig,
    *,
    source: str = "ibkr",
) -> str:
    requested = source.strip().lower()
    if requested != "ibkr":
        return (
            "Option Provider Diagnostics\n"
            f"Source: {requested}\n"
            f"Blocked reason: unsupported_option_provider:{requested}"
        )
    return build_option_provider_status_text(config, check_connectivity=True)


def test_options_provider(
    config: AppConfig,
    *,
    source: str = "ibkr",
    ticker: str,
) -> OptionChainFetchResult:
    return fetch_options_chain(
        config,
        source=source,
        ticker=ticker,
        max_tickers=1,
        force_refresh=True,
    )


def build_options_provider_test_text(
    config: AppConfig,
    *,
    source: str = "ibkr",
    ticker: str,
) -> str:
    result = test_options_provider(config, source=source, ticker=ticker)
    lines = [
        "Option Provider Test",
        f"Source: {result.source}",
        f"Ticker: {normalize_ticker(ticker)}",
        f"Rows loaded: {result.loaded_count}",
        f"Warnings: {result.warning_count}",
    ]
    for item in result.results:
        warning_text = ", ".join(item.warnings) if item.warnings else "none"
        lines.append(
            f"{item.ticker}: {item.status} rows={item.rows_loaded} "
            f"expirations={item.selected_expirations} strikes={item.selected_strikes} "
            f"warnings={warning_text}"
        )
    return "\n".join(lines)


def build_options_position_status_text(config: AppConfig) -> str:
    statuses = option_position_statuses(config.database_path)
    positions = list_option_positions(config.database_path)
    lines = [
        "Options Position Ledger Status",
        f"Position file: {config.options_positions_path}",
        f"Position file exists: {config.options_positions_path.exists()}",
        f"Position rows: {len(positions)}",
        f"Position model: {config.options_position_model_version}",
        "Read-only ledger: true",
        "",
        "Ticker | Type | Role | Positions | Open | Assigned | Latest Open | Latest Expiration | Contracts | Warnings",
    ]
    for status in statuses:
        if not status.position_count:
            continue
        lines.append(
            " | ".join(
                (
                    status.ticker,
                    status.asset_type or "",
                    status.asset_role or "",
                    str(status.position_count),
                    str(status.open_position_count or 0),
                    str(status.assigned_position_count or 0),
                    status.latest_open_date or "",
                    status.latest_expiration_date or "",
                    _fmt_number(status.total_contracts),
                    status.data_warnings or "",
                )
            )
        )
    return "\n".join(lines)


def build_options_outcome_status_text(config: AppConfig) -> str:
    statuses = option_outcome_statuses(config.database_path)
    outcomes = list_option_review_outcomes(config.database_path)
    categories: dict[str, int] = {}
    expiration_statuses: dict[str, int] = {}
    for outcome in outcomes:
        categories[outcome.outcome_status] = categories.get(outcome.outcome_status, 0) + 1
        if outcome.expiration_status:
            expiration_statuses[outcome.expiration_status] = (
                expiration_statuses.get(outcome.expiration_status, 0) + 1
            )
    category_text = ", ".join(f"{key}:{value}" for key, value in sorted(categories.items()))
    expiration_text = ", ".join(
        f"{key}:{value}" for key, value in sorted(expiration_statuses.items())
    )
    lines = [
        "Options Outcome Status",
        f"Outcome model: {config.options_outcome_model_version}",
        f"Position model: {config.options_position_model_version}",
        f"Outcome rows: {len(outcomes)}",
        f"Outcome statuses: {category_text or 'none'}",
        f"Expiration statuses: {expiration_text or 'none'}",
        f"Underlying-price-only: {config.options_outcome_use_underlying_prices_only}",
        "Read-only validation: true",
        "",
        "Ticker | Type | Role | Outcome | Expiration Status | Expiration | Strike | Latest Price | Above Strike | Above Breakeven | Touched Strike | Touched Breakeven | MFE | MAE | Positions | Warnings",
    ]
    for status in statuses:
        if not status.outcome_count:
            continue
        lines.append(
            " | ".join(
                (
                    status.ticker,
                    status.asset_type or "",
                    status.asset_role or "",
                    status.outcome_status or "",
                    status.expiration_status or "",
                    status.expiration_date or "",
                    _fmt_number(status.strike),
                    _fmt_number(status.latest_underlying_price),
                    str(bool(status.above_strike_flag)) if status.above_strike_flag is not None else "",
                    str(bool(status.above_breakeven_flag)) if status.above_breakeven_flag is not None else "",
                    str(bool(status.touched_strike_flag)) if status.touched_strike_flag is not None else "",
                    str(bool(status.touched_breakeven_flag)) if status.touched_breakeven_flag is not None else "",
                    _fmt_percent(status.max_favorable_excursion),
                    _fmt_percent(status.max_adverse_excursion),
                    str(status.linked_position_count or 0),
                    status.data_warnings or "",
                )
            )
        )
    return "\n".join(lines)


def build_options_outcome_report_text(config: AppConfig) -> str:
    outcomes = list_option_review_outcomes(config.database_path)
    lines = [
        "# Options Outcome Report",
        "",
        f"- Outcome model: `{config.options_outcome_model_version}`",
        f"- Outcome rows: `{len(outcomes)}`",
        "- Scope: `read-only sell-put review validation from underlying daily prices`",
        "",
        "Ticker | Review Date | Expiration | Strike | Outcome | Expiration Status | 5d | 20d | Latest | Above Strike | Above Breakeven | Touched Strike | Touched Breakeven | Positions | Warnings",
        "---|---|---|---:|---|---|---:|---:|---:|---|---|---|---|---:|---",
    ]
    for outcome in outcomes:
        lines.append(
            " | ".join(
                (
                    outcome.ticker,
                    outcome.review_date,
                    outcome.expiration_date,
                    _fmt_number(outcome.strike),
                    outcome.outcome_status,
                    outcome.expiration_status or "",
                    _fmt_percent(outcome.return_5d),
                    _fmt_percent(outcome.return_20d),
                    _fmt_percent(outcome.return_to_latest),
                    str(bool(outcome.above_strike_flag)) if outcome.above_strike_flag is not None else "",
                    str(bool(outcome.above_breakeven_flag)) if outcome.above_breakeven_flag is not None else "",
                    str(bool(outcome.touched_strike_flag)) if outcome.touched_strike_flag is not None else "",
                    str(bool(outcome.touched_breakeven_flag)) if outcome.touched_breakeven_flag is not None else "",
                    str(outcome.linked_position_count),
                    outcome.data_warnings or "",
                )
            )
        )
    return "\n".join(lines)


def build_options_lifecycle_status_text(config: AppConfig) -> str:
    statuses = option_lifecycle_statuses(config.database_path)
    positions = list_option_positions(config.database_path)
    reviews = list_option_position_lifecycle_reviews(config.database_path)
    status_counts: dict[str, int] = {}
    for review in reviews:
        status_counts[review.lifecycle_status] = (
            status_counts.get(review.lifecycle_status, 0) + 1
        )
    status_text = ", ".join(f"{key}:{value}" for key, value in sorted(status_counts.items()))
    lines = [
        "Options Lifecycle Status",
        f"Lifecycle model: {config.options_lifecycle_model_version}",
        f"Realized P/L model: {config.options_realized_pl_model_version}",
        f"Option position rows: {len(positions)}",
        f"Lifecycle rows: {len(reviews)}",
        f"Lifecycle statuses: {status_text or 'none'}",
        "Lifecycle readiness: "
        + (
            "active"
            if positions and reviews
            else "source_data_required"
            if not positions
            else "lifecycle_compute_required"
        ),
        "Lifecycle blockers: "
        + (
            "none"
            if positions and reviews
            else "empty_options_positions, no_option_lifecycle_rows"
            if not positions
            else "no_option_lifecycle_rows"
        ),
        f"Option multiplier: {config.options_option_multiplier}",
        f"Assignment tracking enabled: {config.options_assignment_tracking_enabled}",
        "Read-only lifecycle reporting: true",
        "",
        "Ticker | Type | Role | Positions | Reviews | Latest Review | Lifecycle | Open | Closed | Expired | Assigned | Rolled | Realized P/L | Open P/L Proxy | Assignment Notional | Unmatched | Warnings",
    ]
    for status in statuses:
        if not status.position_count and not status.lifecycle_review_count:
            continue
        lines.append(
            " | ".join(
                (
                    status.ticker,
                    status.asset_type or "",
                    status.asset_role or "",
                    str(status.position_count or 0),
                    str(status.lifecycle_review_count or 0),
                    status.lifecycle_review_date or "",
                    status.lifecycle_status or "",
                    str(status.open_lifecycle_count or 0),
                    str(status.closed_lifecycle_count or 0),
                    str(status.expired_lifecycle_count or 0),
                    str(status.assigned_lifecycle_count or 0),
                    str(status.rolled_lifecycle_count or 0),
                    _fmt_number(status.realized_pl_total),
                    _fmt_number(status.open_pl_proxy_total),
                    _fmt_number(status.assignment_notional_total),
                    str(status.unmatched_position_count or 0),
                    status.risk_warnings or "",
                )
            )
        )
    return "\n".join(lines)


def build_options_lifecycle_report_text(config: AppConfig) -> str:
    reviews = list_option_position_lifecycle_reviews(config.database_path)
    lines = [
        "# Options Lifecycle Report",
        "",
        f"- Lifecycle model: `{config.options_lifecycle_model_version}`",
        f"- Realized P/L model: `{config.options_realized_pl_model_version}`",
        f"- Lifecycle rows: `{len(reviews)}`",
        "- Scope: `read-only manual option position lifecycle and realized/open P/L proxy`",
        "",
        "Ticker | Position ID | Open | Expiration | Side | Strike | Contracts | Premium | Lifecycle | Realized P/L | Open P/L Proxy | Mark | Assignment Notional | Linked Review | Warnings",
        "---|---|---|---|---|---:|---:|---:|---|---:|---:|---:|---:|---:|---",
    ]
    for review in reviews:
        lines.append(
            " | ".join(
                (
                    review.ticker,
                    review.position_id or review.position_key,
                    review.open_date,
                    review.expiration_date,
                    review.side,
                    _fmt_number(review.strike),
                    _fmt_number(review.contracts),
                    _fmt_number(review.premium),
                    review.lifecycle_status,
                    _fmt_number(review.realized_pl),
                    _fmt_number(review.open_pl_proxy),
                    _fmt_number(review.latest_option_mark),
                    _fmt_number(review.assignment_notional),
                    str(review.linked_option_income_review_id or ""),
                    review.risk_warnings or "",
                )
            )
        )
    return "\n".join(lines)


def build_options_status_text(config: AppConfig) -> str:
    statuses = option_income_statuses(config.database_path)
    risk_statuses = option_risk_statuses(config.database_path)
    outcome_status_rows = option_outcome_statuses(config.database_path)
    position_status_rows = option_position_statuses(config.database_path)
    lifecycle_status_rows = option_lifecycle_statuses(config.database_path)
    risk_by_ticker = {status.ticker: status for status in risk_statuses}
    outcome_by_ticker = {status.ticker: status for status in outcome_status_rows}
    position_by_ticker = {status.ticker: status for status in position_status_rows}
    lifecycle_by_ticker = {status.ticker: status for status in lifecycle_status_rows}
    activation = option_chain_activation_status(config)
    coverage = option_chain_coverage_plan(config)
    chain_rows = len(list_option_chain_snapshots(config.database_path))
    review_rows = sum(1 for status in statuses if status.review_date)
    risk_rows = len(list_option_risk_reviews(config.database_path))
    outcome_rows = len(list_option_review_outcomes(config.database_path))
    position_rows = len(list_option_positions(config.database_path))
    lifecycle_rows = len(list_option_position_lifecycle_reviews(config.database_path))
    latest_chain = max(
        (status.latest_snapshot_timestamp for status in statuses if status.latest_snapshot_timestamp),
        default=None,
    )
    latest_review = max(
        (status.review_date for status in statuses if status.review_date),
        default=None,
    )
    lines = [
        "Options/Sell-Put Advisory Status",
        f"Options chain file: {config.options_chain_path}",
        f"Options chain file exists: {config.options_chain_path.exists()}",
        f"Options chain source: {config.options_chain_source}",
        f"Options chain cache: {config.options_chain_cache_dir}",
        f"Options source-export directory: {config.options_chain_source_exports_dir}",
        f"Options chain rows: {chain_rows}",
        f"Option income review tickers: {review_rows}",
        f"Option risk review rows: {risk_rows}",
        f"Option outcome rows: {outcome_rows}",
        f"Option position rows: {position_rows}",
        f"Option lifecycle rows: {lifecycle_rows}",
        f"Latest option chain snapshot: {latest_chain or 'none'}",
        f"Latest option income review date: {latest_review or 'none'}",
        f"Latest option risk review date: {max((status.risk_review_date for status in risk_statuses if status.risk_review_date), default=None) or 'none'}",
        f"Latest option outcome date: {max((status.outcome_date for status in outcome_status_rows if status.outcome_date), default=None) or 'none'}",
        f"Latest option lifecycle review date: {max((status.lifecycle_review_date for status in lifecycle_status_rows if status.lifecycle_review_date), default=None) or 'none'}",
        f"Options position file: {config.options_positions_path}",
        f"Options position file exists: {config.options_positions_path.exists()}",
        f"Options model: {config.options_model_version}",
        f"Options risk model: {config.options_risk_model_version}",
        f"Options outcome model: {config.options_outcome_model_version}",
        f"Options lifecycle model: {config.options_lifecycle_model_version}",
        f"Option activation status: {activation.activation_status}",
        f"Activation blocked reason: {activation.blocked_reason or 'none'}",
        f"Minimum option chain coverage: {activation.minimum_option_chain_coverage}",
        f"Minimum option review count: {activation.minimum_option_review_count}",
        f"ibapi repair needed: {activation.ibapi_repair_needed}",
        f"Broader option chain coverage status: {coverage.coverage_status}",
        f"Broader option chain coverage: {coverage.current_loaded_ticker_count}/{coverage.fetch_universe_ticker_count}",
        "Broader missing chain tickers: "
        + (
            ", ".join(coverage.prioritized_missing_tickers)
            if coverage.prioritized_missing_tickers
            else "none"
        ),
        "Broader valid backfill tickers: "
        + (
            ", ".join(coverage.valid_backfill_tickers)
            if coverage.valid_backfill_tickers
            else "none"
        ),
        f"Broader projected chain coverage: {coverage.projected_loaded_ticker_count}/{coverage.fetch_universe_ticker_count}",
        f"Broader coverage apply ready: {coverage.apply_ready}",
        f"Broader coverage blocked reason: {coverage.blocked_reason or 'none'}",
        "Read-only advisory: true",
        "",
        "Ticker | Type | Role | Chain Rows | Expiration | Strike | Premium | Annualized Yield | Downside Buffer | Category | Risk Category | Outcome | Expiration Status | Positions | Lifecycle | Realized P/L | Open P/L Proxy | Cash Requirement | Scenario -10% P/L | Commentary Claims | Warnings",
    ]
    for status in statuses:
        if not status.option_chain_rows and not status.review_date:
            continue
        risk_status = risk_by_ticker.get(status.ticker)
        outcome_status = outcome_by_ticker.get(status.ticker)
        position_status = position_by_ticker.get(status.ticker)
        lifecycle_status = lifecycle_by_ticker.get(status.ticker)
        lines.append(
            " | ".join(
                (
                    status.ticker,
                    status.asset_type or "",
                    status.asset_role or "",
                    str(status.option_chain_rows),
                    status.expiration_date or "",
                    _fmt_number(status.strike),
                    _fmt_number(status.mid_premium),
                    _fmt_percent(status.annualized_yield),
                    _fmt_percent(status.downside_buffer_pct),
                    status.review_category or "",
                    risk_status.risk_category or "" if risk_status else "",
                    outcome_status.outcome_status or "" if outcome_status else "",
                    outcome_status.expiration_status or "" if outcome_status else "",
                    str(position_status.position_count or 0) if position_status else "0",
                    lifecycle_status.lifecycle_status or "" if lifecycle_status else "",
                    _fmt_number(lifecycle_status.realized_pl_total if lifecycle_status else None),
                    _fmt_number(lifecycle_status.open_pl_proxy_total if lifecycle_status else None),
                    _fmt_number(risk_status.cash_secured_requirement if risk_status else None),
                    _fmt_number(risk_status.scenario_pl_10pct if risk_status else None),
                    str(status.commentary_claim_count or 0),
                    _join_unique(
                        tuple(
                            part
                            for part in (
                                status.risk_warnings,
                                risk_status.risk_warnings if risk_status else None,
                                outcome_status.data_warnings if outcome_status else None,
                                position_status.data_warnings if position_status else None,
                                lifecycle_status.risk_warnings if lifecycle_status else None,
                            )
                            if part
                        )
                    )
                    or "",
                )
            )
        )
    return "\n".join(lines)


def build_options_risk_status_text(config: AppConfig) -> str:
    statuses = option_risk_statuses(config.database_path)
    reviews = list_option_risk_reviews(config.database_path)
    latest_date = max(
        (status.risk_review_date for status in statuses if status.risk_review_date),
        default=None,
    )
    categories: dict[str, int] = {}
    for review in reviews:
        categories[review.risk_category] = categories.get(review.risk_category, 0) + 1
    category_text = ", ".join(f"{key}:{value}" for key, value in sorted(categories.items()))
    lines = [
        "Options Risk/Margin Status",
        f"Risk model: {config.options_risk_model_version}",
        f"Margin model: {config.options_risk_margin_model}",
        f"Risk review rows: {len(reviews)}",
        f"Latest option risk review date: {latest_date or 'none'}",
        f"Risk categories: {category_text or 'none'}",
        "Read-only advisory: true",
        "",
        "Ticker | Type | Role | Expiration | Strike | Assignment Notional | Cash Requirement | Premium Income | Max Loss | Assignment Weight | Cash After Assignment | Max Contracts | Category | Warnings",
    ]
    for status in statuses:
        if not status.risk_review_count:
            continue
        lines.append(
            " | ".join(
                (
                    status.ticker,
                    status.asset_type or "",
                    status.asset_role or "",
                    status.expiration_date or "",
                    _fmt_number(status.strike),
                    _fmt_number(status.assignment_notional),
                    _fmt_number(status.cash_secured_requirement),
                    _fmt_number(status.premium_income),
                    _fmt_number(status.max_cash_secured_loss),
                    _fmt_percent(status.projected_assignment_weight),
                    _fmt_number(status.cash_after_assignment),
                    "" if status.max_contracts_advisory is None else str(status.max_contracts_advisory),
                    status.risk_category or "",
                    status.risk_warnings or "",
                )
            )
        )
    return "\n".join(lines)


def build_options_risk_report_text(config: AppConfig) -> str:
    reviews = list_option_risk_reviews(config.database_path)
    lines = [
        "# Options Risk Report",
        "",
        f"- Risk model: `{config.options_risk_model_version}`",
        f"- Margin model: `{config.options_risk_margin_model}`",
        f"- Risk review rows: `{len(reviews)}`",
        "- Read-only advisory: `true`",
        "",
        "Ticker | Expiration | Strike | Premium Income | Cash Requirement | Max Loss | P/L -5% | P/L -10% | P/L -20% | Category | Warnings",
        "---|---|---:|---:|---:|---:|---:|---:|---:|---|---",
    ]
    for review in reviews:
        lines.append(
            " | ".join(
                (
                    review.ticker,
                    review.expiration_date,
                    _fmt_number(review.strike),
                    _fmt_number(review.premium_income),
                    _fmt_number(review.cash_secured_requirement),
                    _fmt_number(review.max_cash_secured_loss),
                    _fmt_number(review.scenario_pl_5pct),
                    _fmt_number(review.scenario_pl_10pct),
                    _fmt_number(review.scenario_pl_20pct),
                    review.risk_category,
                    review.risk_warnings or "",
                )
            )
        )
    return "\n".join(lines)


def build_option_chain_status_text(config: AppConfig) -> str:
    fetch_assets = option_fetch_assets(config, max_tickers=0)
    activation = option_chain_activation_status(config)
    coverage = option_chain_coverage_plan(config)
    snapshots = list_option_chain_snapshots(config.database_path)
    rows_by_ticker: dict[str, int] = {}
    latest_by_ticker: dict[str, str] = {}
    sources_by_ticker: dict[str, set[str]] = {}
    for snapshot in snapshots:
        rows_by_ticker[snapshot.ticker] = rows_by_ticker.get(snapshot.ticker, 0) + 1
        latest_by_ticker[snapshot.ticker] = max(
            latest_by_ticker.get(snapshot.ticker, ""),
            snapshot.snapshot_timestamp,
        )
        sources_by_ticker.setdefault(snapshot.ticker, set()).add(snapshot.source)

    latest_chain = max(latest_by_ticker.values(), default=None)
    lines = [
        "Option Chain Provider Status",
        f"Configured source: {config.options_chain_source}",
        f"Fetch universe: {config.options_option_fetch_universe}",
        f"Daily auto-fetch: {config.options_auto_fetch_daily}",
        f"Intraday auto-fetch: {config.options_auto_fetch_intraday}",
        f"Cache directory: {config.options_chain_cache_dir}",
        f"Cache stale after minutes: {config.options_chain_stale_after_minutes}",
        f"Rows: {len(snapshots)}",
        f"Latest snapshot: {latest_chain or 'none'}",
        f"Fetch-universe tickers: {len(fetch_assets)}",
        "Missing chain tickers: "
        f"{', '.join(coverage.effective_missing_tickers) if coverage.effective_missing_tickers else 'none'}",
        "Raw missing chain tickers: "
        f"{', '.join(coverage.raw_missing_tickers) if coverage.raw_missing_tickers else 'none'}",
        "Non-actionable chain tickers: "
        f"{', '.join(coverage.non_actionable_tickers) if coverage.non_actionable_tickers else 'none'}",
        f"Option activation status: {activation.activation_status}",
        f"Minimum option chain coverage: {activation.minimum_option_chain_coverage}",
        f"Minimum option review count: {activation.minimum_option_review_count}",
        f"Broader coverage status: {coverage.coverage_status}",
        f"Broader chain coverage: {coverage.effective_coverage_count}",
        f"Broader raw chain coverage: {coverage.raw_coverage_count}",
        f"Broader projected chain coverage: {coverage.projected_loaded_ticker_count}/{coverage.fetch_universe_ticker_count}",
        f"Broader coverage blocker: {coverage.blocked_reason or 'none'}",
        f"Broader coverage notes: {', '.join(coverage.notes) if coverage.notes else 'none'}",
        "",
        "Ticker | Type | Role | Rows | Latest Snapshot | Sources",
    ]
    for asset in fetch_assets:
        lines.append(
            " | ".join(
                (
                    asset.ticker,
                    asset.asset_type or "",
                    asset.asset_role or "",
                    str(rows_by_ticker.get(asset.ticker, 0)),
                    latest_by_ticker.get(asset.ticker, ""),
                    ", ".join(sorted(sources_by_ticker.get(asset.ticker, set()))),
                )
            )
        )
    return "\n".join(lines)


def _fmt_number(value: float | None) -> str:
    if value is None:
        return ""
    return f"{value:.4f}".rstrip("0").rstrip(".")


def _fmt_percent(value: float | None) -> str:
    if value is None:
        return ""
    return f"{value:.2%}"
