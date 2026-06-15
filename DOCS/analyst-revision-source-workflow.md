# Analyst Revision Source Workflow

Phase 10C keeps analyst revisions in shadow mode. The purpose of this workflow is
to make every manual revision row auditable before the signal is ever allowed to
affect scores or alerts.

## Source Priority

1. User or provider export.
   Prefer a CSV/export from a source the user already pays for or can audit. Keep
   the original export outside the database, then normalize raw fields in
   `data/signals/source_exports/analyst_revision_source_export.csv`.
2. Yahoo Finance Analysis page.
   Use the Analysis page EPS Trend and Recommendation Trend fields when the page
   is currently accessible and the row labels are clear.
3. API-key providers.
   Phase 10C.2 supports local provider adapters for FMP, Alpha Vantage,
   Business Quant, and Finnhub when keys exist in environment variables.
   yfinance/Yahoo is an optional unofficial Yahoo Finance path, and IBKR remains
   a non-blocking future path. Google Finance is marked unsupported for this
   signal because it does not expose comparable analyst revision fields.
4. No-API public-source captures.
   SecBot, TECHi, RedMatter, Morningstar manual exports, and GuruFocus manual
   exports should be recorded through source-specific CSV files under
   `data/signals/source_exports/`.

Do not fabricate values. If a source does not provide a field, leave that CSV
cell blank. If the source cannot be accessed reliably, do not seed the ticker.

## Normalized Source-Export Schema

Phase 10C.1 added a local source-export file:

```text
data/signals/source_exports/analyst_revision_source_export.csv
```

Required columns:

```text
ticker,signal_date,source,source_url,notes
```

Optional audit column:

```text
capture_method
```

Optional raw estimate fields:

```text
eps_current,eps_30d_ago,eps_90d_ago,eps_high,eps_low,eps_average,analyst_count
revenue_current,revenue_30d_ago,revenue_90d_ago
target_price_current,target_price_90d_ago
recommendation_current_strong_buy,recommendation_current_buy
recommendation_current_hold,recommendation_current_sell
recommendation_current_strong_sell
recommendation_90d_ago_strong_buy,recommendation_90d_ago_buy
recommendation_90d_ago_hold,recommendation_90d_ago_sell
recommendation_90d_ago_strong_sell
```

Run:

```powershell
python -m target_opportunity_monitor import-revision-source-exports
python -m target_opportunity_monitor aggregate-revision-sources
```

The aggregate command derives rows into:

```text
data/signals/manual/analyst_revisions.csv
```

Source snapshot upsert identity is `ticker + signal_date + source`. Aggregate
identity is one canonical row per `ticker + signal_date`. Rows missing
`source_url` or `notes` are rejected. Rows with no derivable numeric signal are
rejected. SPY/QQQ rows are skipped as ETF-gated and are not written to the
company analyst-revision CSV.

## Phase 10C.2 Aggregation Policy

Each imported source row is preserved in `analyst_revision_source_snapshots`.
The aggregate row in `analyst_revision_aggregates` uses weighted median by
field:

```text
FMP = 1.0
Alpha Vantage = 1.0
Business Quant = 0.85
Finnhub = 0.85
yfinance/Yahoo = 0.7
IBKR = 0.8
SecBot public page = 0.6
RedMatter public page = 0.5
TECHi public page = 0.4
Morningstar/GuruFocus licensed manual export = 0.9
```

Warnings:

- `single_source_only` when only one source supports a ticker/date.
- `missing_primary_api_source` when the aggregate has no primary API row from
  FMP, Alpha Vantage, Business Quant, or Finnhub.
- `source_unavailable:SOURCE` when a provider failed or returned no usable row
  in the latest fetch cycle. These failed source snapshots are kept for audit
  but excluded from weighted-median values and source counts.
- `source_disagreement_medium` when comparable revision fields differ by at least 5 percentage points.
- `source_disagreement_high` when comparable revision fields differ by at least 10 percentage points.

The aggregate row is exported back to `data/signals/manual/analyst_revisions.csv`
so the existing shadow-signal and validation pipeline remains unchanged.

## Derivation Rules

Use decimal percentages in the CSV. For example, `0.05` means `+5%`.

- `eps_revision_1m = current_eps_trend / eps_trend_30_days_ago - 1`
- `eps_revision_3m = current_eps_trend / eps_trend_90_days_ago - 1`
- `revenue_revision_1m = revenue_current / revenue_30d_ago - 1`
- `revenue_revision_3m = revenue_current / revenue_90d_ago - 1`
- `target_price_revision_3m = target_price_current / target_price_90d_ago - 1`
- `recommendation_revision = current_bull_bear_score - bull_bear_score_3m_ago`
- `estimate_dispersion = (high_estimate - low_estimate) / abs(avg_estimate)`

The recommendation bull-bear score uses these weights:

```text
strongBuy = 2
buy = 1
hold = 0
sell = -1
strongSell = -2
```

Use a weighted average, not a raw count, so the score is comparable when analyst
counts change.

`analyst_count` should come from the same estimate source when available.
`revenue_revision_1m`, `revenue_revision_3m`, and
`target_price_revision_3m` should stay blank unless the source provides current
and prior comparable values.

## CSV Audit Rules

Every seeded row must include:

- `ticker`
- `signal_date`
- at least one numeric revision or dispersion field
- `source`
- `source_url`
- `notes`
- `as_of_date`
- `effective_date`

The `notes` value should explain the exact source table and period used, such as
`Yahoo Finance Analysis EPS Trend current fiscal year vs 30/90 days ago`.

Do not add SPY or QQQ to this file. They are ETFs and stay gated for ETF-specific
NAV, holdings, tracking, and liquidity signals.

## Current Phase 10C Source Status

As of 2026-06-07, AAPL/MSFT/NVDA have source-backed SecBot public-page rows.
Those rows are useful as auditable public snapshots, but they are still
single-source public-page inputs until API/provider rows are added:

- SecBot rows expose EPS current/30d/90d, EPS high/low/average, and analyst count.
- Revenue revisions, target-price revisions, and recommendation revisions remain
  blank until a source exposes comparable current/prior values.
- FMP, Alpha Vantage, Business Quant, Finnhub, and yfinance/Yahoo are the
  configured provider checks for Phase 10C.2.
- Business Quant currently contributes current consensus/dispersion fields when
  available; true revision fields require prior comparable values from source
  history or another source.
- Finnhub currently contributes recommendation-trend revisions with the available
  key; some estimate and price-target endpoints may require a different plan.
- IBKR remains optional and non-blocking.
- Google Finance remains unsupported for analyst revision fields.

The evidence gate should remain conservative. With current source-backed rows it
can move from `insufficient_source_coverage` to `collecting_evidence`, but Phase
10D should wait for matured validation outcomes and stronger source coverage.

## Verification Workflow

After adding source-backed rows:

```powershell
python -m target_opportunity_monitor fetch-revision-sources --provider all
python -m target_opportunity_monitor import-revision-source-exports
python -m target_opportunity_monitor aggregate-revision-sources
python -m target_opportunity_monitor load-analyst-revisions
python -m target_opportunity_monitor compute-revision-signals
python -m target_opportunity_monitor validate-revision-signals
python -m target_opportunity_monitor revision-provider-status
python -m target_opportunity_monitor revision-source-status
python -m target_opportunity_monitor revision-evidence-report
python -m target_opportunity_monitor run-daily
python -m target_opportunity_monitor build-dashboard
```

The evidence decision can become `eligible_for_limited_score_trial`, but Phase
10C still does not change final opportunity scores or alerts.
