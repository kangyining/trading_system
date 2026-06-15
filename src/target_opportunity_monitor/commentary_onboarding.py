from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

from .config import AppConfig
from .storage import (
    Asset,
    AssetChangeEvent,
    TraderCommentaryInstrumentAlias,
    insert_asset_change_event,
    is_scoreable_asset,
    latest_asset,
    list_assets,
    list_trader_commentary_claims,
    list_trader_commentary_instrument_aliases,
    normalize_asset_role,
    normalize_ticker,
    trader_commentary_alias_map,
    upsert_asset,
    upsert_trader_commentary_instrument_alias,
)
from .watchlist import upsert_watchlist_asset


COMMENTARY_ALIAS_HEADER = (
    "instrument_label",
    "canonical_ticker",
    "asset_type",
    "asset_role",
    "source",
    "notes",
    "as_of_date",
    "effective_date",
)

COMMENTARY_LABEL_DISPOSITION_HEADER = (
    "instrument_label",
    "disposition",
    "source",
    "notes",
    "as_of_date",
    "effective_date",
)

VALID_COMMENTARY_LABEL_DISPOSITIONS = {
    "ignored_non_instrument_context",
    "intentionally_unresolved_ambiguous",
}

COMMENTARY_ONBOARDING_HEADER = (
    "action",
    "ticker",
    "instrument_label",
    "canonical_ticker",
    "name",
    "asset_type",
    "asset_role",
    "exchange",
    "currency",
    "sector",
    "industry",
    "country",
    "active",
    "source",
    "notes",
)

ETF_CANDIDATES = {"SOXL", "KORU", "XLV", "XLF", "XLC", "XLY", "XLP", "XLU", "XLE", "XLI"}


@dataclass(frozen=True)
class CommentaryOnboardingCandidate:
    ticker: str | None
    instrument_label: str | None
    claim_count: int
    claim_types: tuple[str, ...]
    latest_claim_date: str | None
    current_asset_role: str | None
    recommended_asset_type: str | None
    recommended_asset_role: str
    status: str
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class CommentaryLabelDisposition:
    instrument_label: str
    disposition: str
    source: str
    notes: str | None = None
    as_of_date: str | None = None
    effective_date: str | None = None


@dataclass(frozen=True)
class CommentaryOnboardingPlan:
    candidates: tuple[CommentaryOnboardingCandidate, ...]
    active_asset_count: int
    scoreable_asset_count: int
    reference_asset_count: int
    alias_count: int
    label_disposition_count: int

    @property
    def onboardable_count(self) -> int:
        return sum(1 for candidate in self.candidates if candidate.status == "onboardable")

    @property
    def unmapped_count(self) -> int:
        return sum(1 for candidate in self.candidates if candidate.status == "unmapped")

    @property
    def intentionally_unresolved_count(self) -> int:
        return sum(
            1
            for candidate in self.candidates
            if candidate.status == "intentionally_unresolved_ambiguous"
        )

    @property
    def ignored_non_instrument_count(self) -> int:
        return sum(
            1
            for candidate in self.candidates
            if candidate.status == "ignored_non_instrument_context"
        )


@dataclass(frozen=True)
class CommentaryAliasLoadResult:
    path: Path
    loaded_count: int
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class CommentaryLabelDispositionLoadResult:
    path: Path
    loaded_count: int
    invalid_count: int
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class CommentaryOnboardingTemplateResult:
    path: Path
    row_count: int
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class CommentaryOnboardingApplyResult:
    path: Path
    confirmed: bool
    asset_count: int
    alias_count: int
    skipped_count: int
    warnings: tuple[str, ...]


def _clean(value: str | None) -> str:
    return (value or "").strip()


def _asset_type_for_ticker(ticker: str | None) -> str:
    if not ticker:
        return "equity"
    return "etf" if normalize_ticker(ticker) in ETF_CANDIDATES else "equity"


def _active_flag(value: str | None, default: int = 1) -> int:
    cleaned = _clean(value).lower()
    if cleaned in {"", "default"}:
        return default
    if cleaned in {"1", "true", "yes", "y", "active"}:
        return 1
    if cleaned in {"0", "false", "no", "n", "inactive", "disabled"}:
        return 0
    return default


def _asset_change(
    config: AppConfig,
    ticker: str,
    previous: Asset | None,
    new_asset: Asset,
    reason: str | None,
    details: str | None,
) -> None:
    timestamp = datetime.now().isoformat(timespec="seconds")
    insert_asset_change_event(
        config.database_path,
        AssetChangeEvent(
            event_timestamp=timestamp,
            ticker=normalize_ticker(ticker),
            event_type="commentary_onboarding",
            previous_active_flag=previous.active_flag if previous else None,
            new_active_flag=new_asset.active_flag,
            reason=reason,
            details=details,
            as_of_date=date.today().isoformat(),
            effective_date=timestamp,
        ),
    )


def ensure_commentary_alias_csv_header(path: Path) -> None:
    if path.exists():
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=COMMENTARY_ALIAS_HEADER)
        writer.writeheader()


def ensure_commentary_label_disposition_csv_header(path: Path) -> None:
    if path.exists():
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=COMMENTARY_LABEL_DISPOSITION_HEADER)
        writer.writeheader()


def _read_alias_rows(path: Path) -> list[dict[str, str]]:
    ensure_commentary_alias_csv_header(path)
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise ValueError("Commentary instrument alias CSV is missing a header row.")
        fieldnames = {field.strip() for field in reader.fieldnames if field}
        missing = {"instrument_label", "canonical_ticker"} - fieldnames
        if missing:
            raise ValueError(
                "Commentary instrument alias CSV missing required columns: "
                + ", ".join(sorted(missing))
            )
        return [dict(row) for row in reader]


def _read_label_disposition_rows(path: Path) -> list[dict[str, str]]:
    ensure_commentary_label_disposition_csv_header(path)
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise ValueError("Commentary label disposition CSV is missing a header row.")
        fieldnames = {field.strip() for field in reader.fieldnames if field}
        missing = {"instrument_label", "disposition"} - fieldnames
        if missing:
            raise ValueError(
                "Commentary label disposition CSV missing required columns: "
                + ", ".join(sorted(missing))
            )
        return [dict(row) for row in reader]


def _parse_label_dispositions(
    rows: list[dict[str, str]],
) -> tuple[dict[str, CommentaryLabelDisposition], tuple[str, ...], int]:
    dispositions: dict[str, CommentaryLabelDisposition] = {}
    warnings: list[str] = []
    invalid = 0
    for index, row in enumerate(rows, start=2):
        label = _clean(row.get("instrument_label"))
        disposition = _clean(row.get("disposition"))
        if not label and not disposition:
            continue
        if not label or not disposition:
            invalid += 1
            warnings.append(f"row_{index}:missing_label_or_disposition")
            continue
        if disposition not in VALID_COMMENTARY_LABEL_DISPOSITIONS:
            invalid += 1
            warnings.append(f"{label}:invalid_label_disposition:{disposition}")
            continue
        normalized = label.lower()
        if normalized in dispositions:
            warnings.append(f"{label}:duplicate_label_disposition_last_wins")
        dispositions[normalized] = CommentaryLabelDisposition(
            instrument_label=label,
            disposition=disposition,
            source=_clean(row.get("source")) or "manual_csv",
            notes=_clean(row.get("notes")) or None,
            as_of_date=_clean(row.get("as_of_date")) or date.today().isoformat(),
            effective_date=_clean(row.get("effective_date")) or date.today().isoformat(),
        )
    return dispositions, tuple(dict.fromkeys(warnings)), invalid


def commentary_label_disposition_map(
    config: AppConfig,
    path: Path | None = None,
) -> dict[str, CommentaryLabelDisposition]:
    rows = _read_label_disposition_rows(
        path or config.trader_commentary_label_dispositions_path
    )
    dispositions, _warnings, _invalid = _parse_label_dispositions(rows)
    return dispositions


def load_commentary_label_dispositions(
    config: AppConfig,
    path: Path | None = None,
) -> CommentaryLabelDispositionLoadResult:
    disposition_path = path or config.trader_commentary_label_dispositions_path
    rows = _read_label_disposition_rows(disposition_path)
    dispositions, warnings, invalid = _parse_label_dispositions(rows)
    return CommentaryLabelDispositionLoadResult(
        path=disposition_path,
        loaded_count=len(dispositions),
        invalid_count=invalid,
        warnings=warnings,
    )


def load_commentary_instrument_aliases(
    config: AppConfig,
    path: Path | None = None,
) -> CommentaryAliasLoadResult:
    alias_path = path or config.trader_commentary_aliases_path
    rows = _read_alias_rows(alias_path)
    loaded = 0
    warnings: list[str] = []
    assets = {asset.ticker for asset in list_assets(config.database_path)}
    for index, row in enumerate(rows, start=2):
        label = _clean(row.get("instrument_label"))
        ticker = _clean(row.get("canonical_ticker"))
        if not label and not ticker:
            continue
        if not label or not ticker:
            warnings.append(f"row_{index}:missing_alias_label_or_ticker")
            continue
        normalized = normalize_ticker(ticker)
        if normalized not in assets:
            warnings.append(f"{normalized}:alias_ticker_not_in_assets")
        alias = TraderCommentaryInstrumentAlias(
            instrument_label=label,
            canonical_ticker=normalized,
            asset_type=_clean(row.get("asset_type")) or _asset_type_for_ticker(normalized),
            asset_role=normalize_asset_role(row.get("asset_role") or "commentary_validation"),
            source=_clean(row.get("source")) or "manual_csv",
            notes=_clean(row.get("notes")) or None,
            as_of_date=_clean(row.get("as_of_date")) or date.today().isoformat(),
            effective_date=_clean(row.get("effective_date")) or date.today().isoformat(),
        )
        upsert_trader_commentary_instrument_alias(config.database_path, alias)
        loaded += 1
    return CommentaryAliasLoadResult(
        path=alias_path,
        loaded_count=loaded,
        warnings=tuple(warnings),
    )


def build_commentary_onboarding_plan(config: AppConfig) -> CommentaryOnboardingPlan:
    claims = list_trader_commentary_claims(config.database_path)
    assets = {asset.ticker: asset for asset in list_assets(config.database_path)}
    active_assets = [asset for asset in assets.values() if asset.active_flag == 1]
    aliases = trader_commentary_alias_map(config.database_path)
    label_dispositions = commentary_label_disposition_map(config)

    ticker_groups: dict[str, list[object]] = {}
    label_groups: dict[str, list[object]] = {}
    for claim in claims:
        if claim.ticker:
            ticker_groups.setdefault(claim.ticker, []).append(claim)
        else:
            label = (claim.instrument_label or "unmapped_context").strip()
            label_groups.setdefault(label, []).append(claim)

    candidates: list[CommentaryOnboardingCandidate] = []
    for ticker, grouped_claims in sorted(ticker_groups.items()):
        asset = assets.get(ticker)
        current_role = normalize_asset_role(asset.asset_role) if asset else None
        if asset and asset.active_flag == 1:
            status = "reference_ready" if current_role != "scoreable" else "already_scoreable"
            warnings: tuple[str, ...] = ()
        else:
            status = "onboardable"
            warnings = ("ticker_not_active_or_missing_asset",)
        claim_types = tuple(sorted({claim.claim_type for claim in grouped_claims}))
        latest = max(claim.claim_date for claim in grouped_claims)
        candidates.append(
            CommentaryOnboardingCandidate(
                ticker=ticker,
                instrument_label=None,
                claim_count=len(grouped_claims),
                claim_types=claim_types,
                latest_claim_date=latest,
                current_asset_role=current_role,
                recommended_asset_type=_asset_type_for_ticker(ticker),
                recommended_asset_role="commentary_validation",
                status=status,
                warnings=warnings,
            )
        )

    for label, grouped_claims in sorted(label_groups.items()):
        alias = aliases.get(label.lower())
        disposition = label_dispositions.get(label.lower())
        if alias:
            status = "mapped_alias"
            warning = "alias_available"
            recommended_role = alias.asset_role
        elif disposition:
            status = disposition.disposition
            warning = f"label_disposition:{disposition.disposition}"
            recommended_role = disposition.disposition
        else:
            status = "unmapped"
            warning = "unmapped_instrument"
            recommended_role = "alias_mapping_required"
        claim_types = tuple(sorted({claim.claim_type for claim in grouped_claims}))
        latest = max(claim.claim_date for claim in grouped_claims)
        candidates.append(
            CommentaryOnboardingCandidate(
                ticker=alias.canonical_ticker if alias else None,
                instrument_label=label,
                claim_count=len(grouped_claims),
                claim_types=claim_types,
                latest_claim_date=latest,
                current_asset_role=alias.asset_role if alias else None,
                recommended_asset_type=alias.asset_type if alias else None,
                recommended_asset_role=recommended_role,
                status=status,
                warnings=(warning,),
            )
        )

    return CommentaryOnboardingPlan(
        candidates=tuple(candidates),
        active_asset_count=len(active_assets),
        scoreable_asset_count=sum(1 for asset in active_assets if is_scoreable_asset(asset)),
        reference_asset_count=sum(
            1
            for asset in active_assets
            if normalize_asset_role(asset.asset_role) in {"commentary_validation", "regime_proxy"}
        ),
        alias_count=len(list_trader_commentary_instrument_aliases(config.database_path)),
        label_disposition_count=len(label_dispositions),
    )


def build_commentary_onboarding_plan_text(config: AppConfig) -> str:
    plan = build_commentary_onboarding_plan(config)
    lines = [
        "Commentary Onboarding Plan",
        f"Active assets: {plan.active_asset_count}",
        f"Scoreable assets: {plan.scoreable_asset_count}",
        f"Reference assets: {plan.reference_asset_count}",
        f"Alias mappings: {plan.alias_count}",
        f"Label dispositions: {plan.label_disposition_count}",
        f"Onboardable tickers: {plan.onboardable_count}",
        f"Unmapped instrument labels: {plan.unmapped_count}",
        f"Intentionally unresolved labels: {plan.intentionally_unresolved_count}",
        f"Ignored non-instrument labels: {plan.ignored_non_instrument_count}",
        "Ticker | Label | Claims | Types | Latest | Recommended Role | Status | Warnings",
    ]
    for candidate in plan.candidates:
        lines.append(
            " | ".join(
                (
                    candidate.ticker or "",
                    candidate.instrument_label or "",
                    str(candidate.claim_count),
                    ",".join(candidate.claim_types),
                    candidate.latest_claim_date or "",
                    candidate.recommended_asset_role,
                    candidate.status,
                    ",".join(candidate.warnings),
                )
            )
        )
    return "\n".join(lines)


def build_commentary_onboarding_status_text(config: AppConfig) -> str:
    plan = build_commentary_onboarding_plan(config)
    reference_tickers = [
        asset.ticker
        for asset in list_assets(config.database_path)
        if asset.active_flag == 1
        and normalize_asset_role(asset.asset_role) in {"commentary_validation", "regime_proxy"}
    ]
    lines = [
        "Commentary Onboarding Status",
        f"Active assets: {plan.active_asset_count}",
        f"Scoreable assets: {plan.scoreable_asset_count}",
        f"Reference assets: {plan.reference_asset_count}",
        f"Reference tickers: {', '.join(reference_tickers) if reference_tickers else 'none'}",
        f"Alias mappings: {plan.alias_count}",
        f"Label dispositions: {plan.label_disposition_count}",
        f"Onboardable tickers: {plan.onboardable_count}",
        f"Unmapped labels: {plan.unmapped_count}",
        f"Intentionally unresolved labels: {plan.intentionally_unresolved_count}",
        f"Ignored non-instrument labels: {plan.ignored_non_instrument_count}",
    ]
    onboardable = [candidate for candidate in plan.candidates if candidate.status == "onboardable"]
    if onboardable:
        lines.append(
            "Onboardable: "
            + ", ".join(
                f"{candidate.ticker}({candidate.recommended_asset_type}:{candidate.recommended_asset_role})"
                for candidate in onboardable
            )
        )
    unmapped = [candidate for candidate in plan.candidates if candidate.status == "unmapped"]
    if unmapped:
        lines.append(
            "Unmapped labels: "
            + ", ".join(candidate.instrument_label or "unmapped_context" for candidate in unmapped)
        )
    unresolved = [
        candidate
        for candidate in plan.candidates
        if candidate.status == "intentionally_unresolved_ambiguous"
    ]
    if unresolved:
        lines.append(
            "Intentionally unresolved labels: "
            + ", ".join(candidate.instrument_label or "unmapped_context" for candidate in unresolved)
        )
    ignored = [
        candidate
        for candidate in plan.candidates
        if candidate.status == "ignored_non_instrument_context"
    ]
    if ignored:
        lines.append(
            "Ignored non-instrument labels: "
            + ", ".join(candidate.instrument_label or "unmapped_context" for candidate in ignored)
        )
    lines.append(
        "Template: "
        + str(config.trader_commentary_exports_dir / "commentary_onboarding_template.csv")
    )
    return "\n".join(lines)


def export_commentary_onboarding_template(
    config: AppConfig,
    path: Path | None = None,
) -> CommentaryOnboardingTemplateResult:
    output_path = path or config.trader_commentary_exports_dir / "commentary_onboarding_template.csv"
    plan = build_commentary_onboarding_plan(config)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, str]] = []
    for candidate in plan.candidates:
        if candidate.status == "onboardable":
            rows.append(
                {
                    "action": "add_reference",
                    "ticker": candidate.ticker or "",
                    "instrument_label": "",
                    "canonical_ticker": candidate.ticker or "",
                    "name": "",
                    "asset_type": candidate.recommended_asset_type or "equity",
                    "asset_role": candidate.recommended_asset_role,
                    "exchange": "",
                    "currency": "USD",
                    "sector": "",
                    "industry": "",
                    "country": "US",
                    "active": "1",
                    "source": "commentary_onboarding",
                    "notes": f"{candidate.claim_count} commentary claims",
                }
            )
        elif candidate.status == "unmapped":
            rows.append(
                {
                    "action": "alias",
                    "ticker": "",
                    "instrument_label": candidate.instrument_label or "",
                    "canonical_ticker": "",
                    "name": "",
                    "asset_type": "",
                    "asset_role": "commentary_validation",
                    "exchange": "",
                    "currency": "USD",
                    "sector": "",
                    "industry": "",
                    "country": "US",
                    "active": "1",
                    "source": "commentary_alias",
                    "notes": "fill canonical_ticker only when you want this label mapped",
                }
            )
    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=COMMENTARY_ONBOARDING_HEADER)
        writer.writeheader()
        writer.writerows(rows)
    return CommentaryOnboardingTemplateResult(
        path=output_path,
        row_count=len(rows),
        warnings=(),
    )


def _read_onboarding_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise ValueError("Commentary onboarding CSV is missing a header row.")
        return [dict(row) for row in reader]


def apply_commentary_onboarding(
    config: AppConfig,
    path: Path,
    confirm: bool = False,
) -> CommentaryOnboardingApplyResult:
    rows = _read_onboarding_rows(path)
    warnings: list[str] = []
    asset_count = 0
    alias_count = 0
    skipped_count = 0
    if not confirm:
        actionable = sum(1 for row in rows if _clean(row.get("action")).lower() not in {"", "skip"})
        return CommentaryOnboardingApplyResult(
            path=path,
            confirmed=False,
            asset_count=0,
            alias_count=0,
            skipped_count=len(rows) - actionable,
            warnings=(f"dry_run_actionable_rows={actionable}", "confirmation_required"),
        )

    for index, row in enumerate(rows, start=2):
        action = _clean(row.get("action")).lower()
        if action in {"", "skip"}:
            skipped_count += 1
            continue
        role = normalize_asset_role(row.get("asset_role") or "commentary_validation")
        ticker_value = _clean(row.get("ticker")) or _clean(row.get("canonical_ticker"))
        canonical = _clean(row.get("canonical_ticker")) or ticker_value
        label = _clean(row.get("instrument_label"))
        if action in {"add_reference", "add_scoreable", "add_asset", "promote_scoreable"}:
            if not ticker_value:
                warnings.append(f"row_{index}:missing_ticker")
                skipped_count += 1
                continue
            ticker = normalize_ticker(ticker_value)
            final_role = "scoreable" if action in {"add_scoreable", "promote_scoreable"} else role
            asset = Asset(
                ticker=ticker,
                name=_clean(row.get("name")) or None,
                asset_type=_clean(row.get("asset_type")) or _asset_type_for_ticker(ticker),
                exchange=_clean(row.get("exchange")) or None,
                currency=_clean(row.get("currency")) or "USD",
                sector=_clean(row.get("sector")) or None,
                industry=_clean(row.get("industry")) or None,
                country=_clean(row.get("country")) or "US",
                active_flag=0 if final_role == "inactive" else _active_flag(row.get("active")),
                asset_role=final_role,
                source=_clean(row.get("source")) or "commentary_onboarding",
                as_of_date=date.today().isoformat(),
                effective_date=datetime.now().isoformat(timespec="seconds"),
            )
            previous = latest_asset(config.database_path, ticker)
            upsert_asset(config.database_path, asset)
            upsert_watchlist_asset(config.watchlist_path, asset)
            _asset_change(
                config,
                ticker,
                previous,
                asset,
                _clean(row.get("notes")) or None,
                f"asset_role={asset.asset_role};action={action}",
            )
            asset_count += 1
            canonical = ticker
        if action in {"alias", "add_reference", "add_scoreable", "add_asset", "promote_scoreable"} and label:
            if not canonical:
                warnings.append(f"row_{index}:missing_canonical_ticker_for_alias")
                skipped_count += 1
                continue
            alias = TraderCommentaryInstrumentAlias(
                instrument_label=label,
                canonical_ticker=normalize_ticker(canonical),
                asset_type=_clean(row.get("asset_type")) or _asset_type_for_ticker(canonical),
                asset_role=role,
                source=_clean(row.get("source")) or "commentary_alias",
                notes=_clean(row.get("notes")) or None,
                as_of_date=date.today().isoformat(),
                effective_date=datetime.now().isoformat(timespec="seconds"),
            )
            upsert_trader_commentary_instrument_alias(config.database_path, alias)
            alias_count += 1
        elif action == "alias":
            warnings.append(f"row_{index}:missing_instrument_label")
            skipped_count += 1
    return CommentaryOnboardingApplyResult(
        path=path,
        confirmed=True,
        asset_count=asset_count,
        alias_count=alias_count,
        skipped_count=skipped_count,
        warnings=tuple(warnings),
    )
