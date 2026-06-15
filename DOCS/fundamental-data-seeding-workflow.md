# Fundamental Data Seeding Workflow

Created: 2026-06-06

Purpose: define a reliable, auditable workflow for seeding company fundamentals
and forward estimates before Phase 4 scoring.

## 1. Current Seed State

Current manual files:

```text
data/fundamentals/manual/fundamentals.csv
data/fundamentals/manual/estimates.csv
```

Current seeded tickers:

```text
AAPL
MSFT
NVDA
```

Current rows:

```text
fundamentals: 9 annual rows
estimates: 3 NTM EPS rows
targets: 3 target rows
```

Current unsupported tickers:

```text
SPY
QQQ
```

Reason: SPY and QQQ require ETF look-through valuation, not company-level
fundamental valuation.

Current automated actuals command:

```text
python -m target_opportunity_monitor seed-fundamentals
```

This command fetches or reuses cached SEC companyfacts JSON, transforms it into
the manual fundamentals CSV schema, loads the rows into SQLite, and preserves
the CSV as the editable audit layer.

## 2. Source Policy

Use different source tiers for different kinds of data.

Tier 1: SEC EDGAR companyfacts

- Use for historical reported fundamentals.
- Use for 10-K and 10-Q actuals.
- Source URL pattern:

```text
https://data.sec.gov/api/xbrl/companyfacts/CIK##########.json
```

Current CIKs:

```text
AAPL: 0000320193
MSFT: 0000789019
NVDA: 0001045810
```

Tier 2: Company investor relations filings/releases

- Use when SEC tags are missing, ambiguous, or need reconciliation.
- Good for guidance, segment KPIs, and management-provided non-GAAP metrics.
- Do not mix non-GAAP numbers with GAAP rows unless the source is clearly labeled.

Tier 3: Market-data/estimate aggregators

- Use for forward estimates only.
- Current seed uses Yahoo Finance current price and forward P/E to infer NTM EPS.
- Formula:

```text
ntm_eps = current_price / forward_pe
```

Tier 4: Manual analyst judgment

- Use only with explicit source notes.
- Do not allow Tier 4 values to drive alerts without review.

## 3. SEC Companyfacts Workflow

The reliable historical fundamentals workflow is:

1. Map ticker to CIK.
2. Fetch SEC companyfacts JSON with a descriptive User-Agent.
3. Extract annual 10-K facts.
4. Prefer facts where:
   - `form = 10-K`
   - `fp = FY`
   - duration facts have a start and end date about one fiscal year apart
   - balance-sheet facts are instant facts at the same fiscal period end
5. Store values in whole dollars and whole shares.
6. Preserve source and dates:
   - `source = sec_companyfacts`
   - `as_of_date = load date`
   - `effective_date = fiscal_period_end`

The project command for this workflow is:

```text
python -m target_opportunity_monitor seed-fundamentals
python -m target_opportunity_monitor seed-fundamentals --ticker AAPL
python -m target_opportunity_monitor seed-fundamentals --years 5
python -m target_opportunity_monitor seed-fundamentals --refresh-cache
```

Supporting files:

```text
configs/cik_map.csv
configs/stock_splits.csv
data/fundamentals/cache/sec_companyfacts/
```

Core tag mapping:

```text
revenue:
  RevenueFromContractWithCustomerExcludingAssessedTax
  Revenues
  SalesRevenueNet

gross_profit:
  GrossProfit

operating_income:
  OperatingIncomeLoss

net_income:
  NetIncomeLoss
  ProfitLoss

diluted_eps:
  EarningsPerShareDiluted

cash_from_operations:
  NetCashProvidedByUsedInOperatingActivities

capital_expenditure:
  PaymentsToAcquirePropertyPlantAndEquipment

cash_and_equivalents:
  CashAndCashEquivalentsAtCarryingValue
  CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents

debt:
  LongTermDebt
  LongTermDebtCurrent + LongTermDebtNoncurrent
  DebtCurrent + LongTermDebtNoncurrent

total_assets:
  Assets

total_equity:
  StockholdersEquity

diluted_shares:
  WeightedAverageNumberOfDilutedSharesOutstanding
```

Derived fields:

```text
free_cash_flow = cash_from_operations - capex_cash_outflow
capital_expenditure = negative capex_cash_outflow
net_debt = total_debt - cash_and_equivalents
ebit = operating_income
ebitda = operating_income + depreciation_and_amortization
```

Known capex tags:

```text
PaymentsToAcquirePropertyPlantAndEquipment
PaymentsToAcquireProductiveAssets
```

Important caveats:

- SEC tags differ by company.
- Companyfacts can contain duplicate prior-period values repeated in later filings.
- Quarterly filings often include both quarter-only and year-to-date rows.
- Always check `start`, `end`, `fy`, `fp`, and `form`.
- EPS and share counts may require stock-split adjustment when comparing old
  historical per-share metrics to current post-split prices.

## 4. Estimate Workflow

SEC does not provide analyst estimates.

For now:

1. Use Yahoo Finance current price and forward P/E.
2. Infer NTM EPS as:

```text
ntm_eps = current_price / forward_pe
```

3. Store the estimate row as:

```text
metric = eps
fiscal_period = NTM
source = yahoo_finance_forward_pe
estimate_date = date of quote/forward P/E observation
as_of_date = load date
effective_date = quote/forward P/E observation date
```

Current estimate seed:

```text
AAPL: 307.34 / 32.15 = 9.5596
MSFT: 416.67 / 21.46 = 19.4161
NVDA: 205.10 / 25.45 = 8.0589
```

Reliability caveat:

Yahoo Finance is useful for manual estimate seeding, but it is not the same
quality as SEC filing data. For a durable production workflow, use a stable
licensed estimates provider or store manual estimate snapshots with source URLs,
timestamps, and analyst count when available.

## 5. Quality Checks

Before accepting seeded rows:

```text
python -m target_opportunity_monitor seed-fundamentals
python -m target_opportunity_monitor load-estimates
python -m target_opportunity_monitor compute-targets
python -m target_opportunity_monitor valuation-status
python -m target_opportunity_monitor status
python -m target_opportunity_monitor run-daily
python -m unittest discover -s tests
```

Accept only if:

- Fundamentals load without parser errors.
- Estimates load without parser errors.
- AAPL/MSFT/NVDA produce target rows.
- SPY/QQQ remain unsupported unless ETF valuation is added.
- `status` shows the expected row counts.
- Tests pass.
- Daily report shows target coverage and current target ranges.

Current expected row counts:

```text
Asset rows: 5
Price rows: 2745
Price feature rows: 5
Fundamental rows: 9
Estimate rows: 3
Target rows: 3
```

## 6. Refresh Cadence

Daily:

- Refresh prices.
- Recompute targets if price features changed.

Weekly:

- Review forward estimates.
- Refresh estimate rows if forward P/E or consensus EPS moved meaningfully.

Quarterly:

- Refresh SEC companyfacts after 10-Q/10-K filings:

```text
python -m target_opportunity_monitor seed-fundamentals --refresh-cache
```

- Add the new quarter or annual row.
- Recompute targets.

After stock splits:

- Review historical EPS and share count comparability.
- Mark adjusted rows clearly in `source`.
- Prefer preserving raw facts separately before adding adjusted valuation rows.

## 7. Future Improvement

Before relying on this heavily for alerts, add an automated Phase 3B/4 helper:

```text
python -m target_opportunity_monitor seed-estimates --ticker AAPL --source provider
```

The helper should:

- Cache raw source JSON.
- Write transformed CSV rows.
- Record source URLs.
- Record transform warnings.
- Refuse to overwrite changed manual values without an explicit update flag.
