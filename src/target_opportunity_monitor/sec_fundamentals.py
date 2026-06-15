from __future__ import annotations

import csv
from dataclasses import asdict, dataclass
from datetime import date, datetime
import json
from pathlib import Path
from urllib.error import URLError
from urllib.request import Request, urlopen

from .config import AppConfig
from .fundamental_data import FUNDAMENTAL_HEADERS, parse_fundamentals_csv
from .storage import Fundamental, normalize_ticker, upsert_fundamental


SEC_COMPANYFACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"

TAG_PRIORITY = {
    "revenue": (
        "RevenueFromContractWithCustomerExcludingAssessedTax",
        "Revenues",
        "SalesRevenueNet",
    ),
    "gross_profit": ("GrossProfit",),
    "operating_income": ("OperatingIncomeLoss",),
    "net_income": ("NetIncomeLoss", "ProfitLoss"),
    "diluted_eps": ("EarningsPerShareDiluted",),
    "cash_from_operations": ("NetCashProvidedByUsedInOperatingActivities",),
    "capex": (
        "PaymentsToAcquirePropertyPlantAndEquipment",
        "PaymentsToAcquireProductiveAssets",
    ),
    "cash": (
        "CashAndCashEquivalentsAtCarryingValue",
        "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents",
    ),
    "debt_current": ("LongTermDebtCurrent", "DebtCurrent"),
    "debt_noncurrent": (
        "LongTermDebtNoncurrent",
        "LongTermDebtAndFinanceLeaseObligationsNoncurrent",
    ),
    "debt_total": ("LongTermDebt", "LongTermDebtAndFinanceLeaseObligations"),
    "assets": ("Assets",),
    "equity": (
        "StockholdersEquity",
        "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest",
    ),
    "shares": ("WeightedAverageNumberOfDilutedSharesOutstanding",),
}

DA_COMBINED_TAGS = (
    "DepreciationDepletionAndAmortization",
    "DepreciationDepletionAndAmortizationExpense",
)

DA_COMPONENT_TAGS = (
    "Depreciation",
    "AmortizationOfIntangibleAssets",
)


@dataclass(frozen=True)
class StockSplit:
    ticker: str
    effective_date: str
    ratio: float


@dataclass(frozen=True)
class SecSeedResult:
    written_count: int
    loaded_count: int
    tickers: tuple[str, ...]
    skipped: tuple[str, ...]
    csv_path: Path


def _clean_cik(cik: str) -> str:
    return cik.strip().zfill(10)


def load_cik_map(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = {}
        for row in reader:
            ticker = (row.get("ticker") or "").strip()
            cik = (row.get("cik") or "").strip()
            if ticker and cik:
                rows[normalize_ticker(ticker)] = _clean_cik(cik)
    return rows


def load_stock_splits(path: Path) -> list[StockSplit]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        splits: list[StockSplit] = []
        for row in reader:
            ticker = (row.get("ticker") or "").strip()
            effective_date = (row.get("effective_date") or "").strip()
            ratio = (row.get("ratio") or "").strip()
            if not ticker or not effective_date or not ratio:
                continue
            date.fromisoformat(effective_date)
            splits.append(
                StockSplit(
                    ticker=normalize_ticker(ticker),
                    effective_date=effective_date,
                    ratio=float(ratio),
                )
            )
    return splits


def companyfacts_cache_path(cache_dir: Path, ticker: str, cik: str) -> Path:
    return cache_dir / "sec_companyfacts" / f"{normalize_ticker(ticker)}-{_clean_cik(cik)}.json"


def fetch_companyfacts(cik: str, user_agent: str) -> dict[str, object]:
    request = Request(
        SEC_COMPANYFACTS_URL.format(cik=_clean_cik(cik)),
        headers={"User-Agent": user_agent, "Accept": "application/json"},
    )
    try:
        with urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))
    except URLError as error:
        raise ValueError(f"SEC companyfacts request failed for CIK {cik}: {error}") from error


def load_or_fetch_companyfacts(
    cache_dir: Path,
    ticker: str,
    cik: str,
    user_agent: str,
    refresh_cache: bool = False,
) -> dict[str, object]:
    path = companyfacts_cache_path(cache_dir, ticker, cik)
    if path.exists() and not refresh_cache:
        return json.loads(path.read_text(encoding="utf-8"))
    payload = fetch_companyfacts(cik, user_agent)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return payload


def _us_gaap_facts(payload: dict[str, object]) -> dict[str, object]:
    facts = payload.get("facts", {})
    if not isinstance(facts, dict):
        return {}
    us_gaap = facts.get("us-gaap", {})
    return us_gaap if isinstance(us_gaap, dict) else {}


def _units_for(facts: dict[str, object], tag: str) -> list[dict[str, object]]:
    fact = facts.get(tag)
    if not isinstance(fact, dict):
        return []
    units = fact.get("units", {})
    if not isinstance(units, dict):
        return []
    for unit_name in ("USD", "shares", "USD/shares"):
        values = units.get(unit_name)
        if isinstance(values, list):
            return [value for value in values if isinstance(value, dict)]
    for values in units.values():
        if isinstance(values, list):
            return [value for value in values if isinstance(value, dict)]
    return []


def _duration_days(fact: dict[str, object]) -> int | None:
    start = fact.get("start")
    end = fact.get("end")
    if not isinstance(start, str) or not isinstance(end, str):
        return None
    try:
        return (datetime.fromisoformat(end) - datetime.fromisoformat(start)).days
    except ValueError:
        return None


def _fact_value(fact: dict[str, object] | None) -> float | None:
    if fact is None:
        return None
    value = fact.get("val")
    return float(value) if isinstance(value, int | float) else None


def _annual_fact(
    facts: dict[str, object],
    tags: tuple[str, ...],
    fiscal_year: int,
) -> dict[str, object] | None:
    for tag in tags:
        candidates = []
        for fact in _units_for(facts, tag):
            if (
                fact.get("fy") == fiscal_year
                and fact.get("fp") == "FY"
                and fact.get("form") == "10-K"
            ):
                duration = _duration_days(fact)
                if duration is not None and 300 <= duration <= 400:
                    candidates.append(fact)
        if candidates:
            candidates.sort(
                key=lambda item: (
                    str(item.get("end") or ""),
                    _duration_days(item) or 0,
                    str(item.get("filed") or ""),
                )
            )
            return candidates[-1]
    return None


def _instant_fact(
    facts: dict[str, object],
    tags: tuple[str, ...],
    fiscal_year: int,
    period_end: str,
) -> dict[str, object] | None:
    for tag in tags:
        candidates = []
        for fact in _units_for(facts, tag):
            if (
                fact.get("fy") == fiscal_year
                and fact.get("fp") == "FY"
                and fact.get("form") == "10-K"
                and fact.get("end") == period_end
                and fact.get("start") is None
            ):
                candidates.append(fact)
        if candidates:
            candidates.sort(key=lambda item: str(item.get("filed") or ""))
            return candidates[-1]
    return None


def _available_fiscal_years(facts: dict[str, object]) -> list[int]:
    years: set[int] = set()
    for tag in TAG_PRIORITY["revenue"]:
        for fact in _units_for(facts, tag):
            year = fact.get("fy")
            if not isinstance(year, int):
                continue
            if (
                fact.get("fp") == "FY"
                and fact.get("form") == "10-K"
                and (_duration_days(fact) or 0) >= 300
            ):
                years.add(year)
    return sorted(years)


def _annual_value(
    facts: dict[str, object],
    field_name: str,
    fiscal_year: int,
) -> float | None:
    return _fact_value(_annual_fact(facts, TAG_PRIORITY[field_name], fiscal_year))


def _instant_value(
    facts: dict[str, object],
    field_name: str,
    fiscal_year: int,
    period_end: str,
) -> float | None:
    return _fact_value(
        _instant_fact(facts, TAG_PRIORITY[field_name], fiscal_year, period_end)
    )


def _depreciation_and_amortization(
    facts: dict[str, object],
    fiscal_year: int,
) -> float | None:
    combined = _fact_value(_annual_fact(facts, DA_COMBINED_TAGS, fiscal_year))
    if combined is not None:
        return combined

    components = [
        _fact_value(_annual_fact(facts, (tag,), fiscal_year))
        for tag in DA_COMPONENT_TAGS
    ]
    usable = [value for value in components if value is not None]
    if not usable:
        return None
    return sum(usable)


def _split_ratio(ticker: str, period_end: str, splits: list[StockSplit]) -> float:
    ratio = 1.0
    end_date = date.fromisoformat(period_end)
    for split in splits:
        if split.ticker == normalize_ticker(ticker):
            effective_date = date.fromisoformat(split.effective_date)
            if end_date < effective_date:
                ratio *= split.ratio
    return ratio


def extract_sec_annual_fundamentals(
    payload: dict[str, object],
    ticker: str,
    years: int,
    splits: list[StockSplit] | None = None,
    as_of_date: str | None = None,
) -> list[Fundamental]:
    facts = _us_gaap_facts(payload)
    if not facts:
        return []
    selected_years = _available_fiscal_years(facts)[-years:]
    split_rules = splits or []
    load_date = as_of_date or date.today().isoformat()
    rows: list[Fundamental] = []

    for fiscal_year in selected_years:
        revenue_fact = _annual_fact(facts, TAG_PRIORITY["revenue"], fiscal_year)
        revenue = _fact_value(revenue_fact)
        period_end = revenue_fact.get("end") if revenue_fact else None
        if revenue is None or not isinstance(period_end, str):
            continue

        operating_income = _annual_value(facts, "operating_income", fiscal_year)
        depreciation_amortization = _depreciation_and_amortization(facts, fiscal_year)
        ebitda = (
            operating_income + depreciation_amortization
            if operating_income is not None and depreciation_amortization is not None
            else None
        )
        capex_cash_outflow = _annual_value(facts, "capex", fiscal_year)
        cash_from_operations = _annual_value(
            facts, "cash_from_operations", fiscal_year
        )
        capital_expenditure = (
            -capex_cash_outflow if capex_cash_outflow is not None else None
        )
        free_cash_flow = (
            cash_from_operations - capex_cash_outflow
            if cash_from_operations is not None and capex_cash_outflow is not None
            else None
        )
        cash = _instant_value(facts, "cash", fiscal_year, period_end)
        total_debt = _instant_value(facts, "debt_total", fiscal_year, period_end)
        if total_debt is None:
            debt_current = _instant_value(
                facts, "debt_current", fiscal_year, period_end
            )
            debt_noncurrent = _instant_value(
                facts, "debt_noncurrent", fiscal_year, period_end
            )
            if debt_current is not None or debt_noncurrent is not None:
                total_debt = (debt_current or 0.0) + (debt_noncurrent or 0.0)
        net_debt = (
            total_debt - cash
            if total_debt is not None and cash is not None
            else None
        )

        diluted_eps = _annual_value(facts, "diluted_eps", fiscal_year)
        diluted_shares = _annual_value(facts, "shares", fiscal_year)
        split_ratio = _split_ratio(ticker, period_end, split_rules)
        source = "sec_companyfacts"
        if split_ratio != 1.0:
            if diluted_eps is not None:
                diluted_eps = diluted_eps / split_ratio
            if diluted_shares is not None:
                diluted_shares = diluted_shares * split_ratio
            source = "sec_companyfacts_split_adjusted"

        rows.append(
            Fundamental(
                ticker=ticker,
                fiscal_period_end=period_end,
                fiscal_period="FY",
                report_type="annual",
                currency="USD",
                revenue=revenue,
                gross_profit=_annual_value(facts, "gross_profit", fiscal_year),
                operating_income=operating_income,
                ebitda=ebitda,
                ebit=operating_income,
                net_income=_annual_value(facts, "net_income", fiscal_year),
                eps=diluted_eps,
                diluted_eps=diluted_eps,
                cash_from_operations=cash_from_operations,
                capital_expenditure=capital_expenditure,
                free_cash_flow=free_cash_flow,
                cash_and_equivalents=cash,
                total_debt=total_debt,
                net_debt=net_debt,
                total_assets=_instant_value(facts, "assets", fiscal_year, period_end),
                total_equity=_instant_value(facts, "equity", fiscal_year, period_end),
                shares_outstanding=diluted_shares,
                diluted_shares=diluted_shares,
                source=source,
                as_of_date=load_date,
                effective_date=period_end,
            )
        )
    return rows


def _fundamental_sort_key(row: Fundamental) -> tuple[str, str, str]:
    return (row.ticker, row.fiscal_period_end, row.source)


def merge_fundamentals_csv(path: Path, new_rows: list[Fundamental]) -> int:
    existing_rows: list[Fundamental] = []
    if path.exists() and path.read_text(encoding="utf-8-sig").strip():
        existing_rows = parse_fundamentals_csv(path.read_text(encoding="utf-8-sig"))

    replacement_tickers = {row.ticker for row in new_rows}
    retained_rows = [
        row
        for row in existing_rows
        if not (
            row.ticker in replacement_tickers
            and row.source.startswith("sec_companyfacts")
        )
    ]
    merged_rows = sorted(retained_rows + new_rows, key=_fundamental_sort_key)

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FUNDAMENTAL_HEADERS)
        writer.writeheader()
        for row in merged_rows:
            payload = asdict(row)
            writer.writerow({column: payload.get(column) for column in FUNDAMENTAL_HEADERS})
    return len(new_rows)


def seed_sec_fundamentals(
    config: AppConfig,
    ticker: str | None = None,
    years: int | None = None,
    refresh_cache: bool = False,
) -> SecSeedResult:
    cik_map = load_cik_map(config.cik_map_path)
    splits = load_stock_splits(config.stock_splits_path)
    selected_years = years or config.fundamental_seed_years
    wanted = normalize_ticker(ticker) if ticker else None
    tickers = [wanted] if wanted else sorted(cik_map)

    all_rows: list[Fundamental] = []
    skipped: list[str] = []
    for selected_ticker in tickers:
        cik = cik_map.get(selected_ticker)
        if not cik:
            skipped.append(f"{selected_ticker}:missing_cik")
            continue
        payload = load_or_fetch_companyfacts(
            config.fundamental_cache_dir,
            selected_ticker,
            cik,
            config.sec_user_agent,
            refresh_cache,
        )
        rows = extract_sec_annual_fundamentals(
            payload,
            selected_ticker,
            selected_years,
            splits=splits,
        )
        if not rows:
            skipped.append(f"{selected_ticker}:no_rows")
            continue
        all_rows.extend(rows)

    written_count = merge_fundamentals_csv(config.fundamentals_path, all_rows)
    for row in all_rows:
        upsert_fundamental(config.database_path, row)

    return SecSeedResult(
        written_count=written_count,
        loaded_count=len(all_rows),
        tickers=tuple(sorted({row.ticker for row in all_rows})),
        skipped=tuple(skipped),
        csv_path=config.fundamentals_path,
    )
