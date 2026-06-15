# Short Interest Source Workflow

Phase 10G adds short interest as a shadow-only signal family. The purpose is to
track whether short-interest pressure is improving, worsening, or creating a
possible squeeze setup. It is not an alert trigger and it does not change final
scores, portfolio guidance, notifications, broker actions, or execution.

## Input File

Use the editable CSV:

```text
data/signals/manual/short_interest.csv
```

Phase 10G.1 also supports auditable source-export files under:

```text
data/signals/source_exports/short_interest/
```

The export command creates these templates:

```text
provider_export.csv
exchange_manual.csv
broker_manual.csv
missing_short_interest_backfill.csv
missing_provider_short_interest_backfill.csv
```

The missing-ticker backfill template contains one blank row per active equity
missing source-backed short-interest coverage. SPY and QQQ are intentionally
excluded from that equity backfill and remain ETF-gated.

Phase 10G.3 adds a focused missing-provider template and apply guard. The
focused template is only for currently uncovered equities such as `CRM`, `JPM`,
`LLY`, and `ORCL` in the current live watchlist state. It is blank by default;
fill it only with source-backed provider, exchange, or broker values.

Phase 10G.4 adds a resolver command for those uncovered equities. It rechecks
official/cache/provider paths only for missing tickers, refreshes the focused
template, and reports whether projected coverage would improve. If official
sources still return no usable rows, the resolver leaves coverage unchanged and
keeps the blocker explicit.

Phase 10G.2 adds a cache-first source fetch and provider-export normalization
workflow before this existing import path. Direct official fetches and normalized
provider exports both write into:

```text
data/signals/source_exports/short_interest/provider_export.csv
```

That file is still treated as an auditable source-export file. It must pass the
same validation rules before values are merged into
`data/signals/manual/short_interest.csv`.

Required columns:

```text
ticker, settlement_date, source, source_url
```

Optional columns:

```text
publication_date, short_interest, float_shares, percent_float,
average_daily_volume, days_to_cover, notes, as_of_date, effective_date
```

## Source Rules

- Use source-backed rows only.
- Do not fabricate short interest, float, percent float, volume, or days to cover.
- Leave unsupported fields blank.
- Keep a stable `source_url` for every row.
- Use `notes` to record capture details such as provider table name, export file,
  or manual capture date.
- SPY and QQQ are ETFs and remain gated as `etf_short_interest_gated`.

Acceptable source types for this MVP include exchange data, broker/provider
exports, licensed data exports, or user-supplied tables where the settlement
date and numeric fields are auditable. If a source only shows a headline or
commentary without numeric short-interest fields, do not load it as short
interest data.

Preferred source order:

```text
FINRA official fetch or export
Nasdaq Trader official/source-backed export
NYSE/broker/provider export normalization
exchange_manual or broker_manual source-export rows
```

FINRA and Nasdaq Trader availability can vary by endpoint, exchange coverage,
rate limits, or subscription requirements. If a free official direct fetch cannot
cover a ticker, use `normalize-short-interest-provider-export` on a broker,
exchange, or licensed provider export. Do not infer missing values from article
text or a quote page.

The source-export import path requires at least one numeric evidence field:

```text
short_interest, percent_float, days_to_cover
```

Rows can still derive `percent_float` or `days_to_cover`, but only from supplied
numeric fields. A row with only ticker/source/date and no numeric evidence is
rejected as `missing_numeric_short_interest_evidence`.

## Field Handling

`percent_float` may be captured as:

```text
0.052
5.2
5.2%
```

TOM stores it internally as a decimal fraction. If `percent_float` is blank and
both `short_interest` and `float_shares` are present, TOM derives:

```text
percent_float = short_interest / float_shares
```

If `days_to_cover` is blank and both `short_interest` and
`average_daily_volume` are present, TOM derives:

```text
days_to_cover = short_interest / average_daily_volume
```

Derived fields are marked with warnings such as `derived_percent_float` and
`derived_days_to_cover`.

## Signal Interpretation

The stored component signals are:

```text
short_interest.level
short_interest.days_to_cover
short_interest.change
short_interest.squeeze_setup
short_interest.composite
```

Higher composite scores mean the short-interest backdrop is more constructive:

- lower percent-float short is generally better,
- lower days-to-cover is generally better,
- falling short interest is better than rising short interest,
- high short interest plus positive 1-month momentum may create
  `squeeze_candidate_shadow_only`.

Missing prior rows produce a neutral change component and
`missing_short_interest_history`.

## Commands

```powershell
python -m target_opportunity_monitor short-interest-provider-status
python -m target_opportunity_monitor fetch-short-interest-sources --provider all
python -m target_opportunity_monitor fetch-short-interest-sources --provider finra --ticker AAPL
python -m target_opportunity_monitor normalize-short-interest-provider-export --provider generic --file PATH
python -m target_opportunity_monitor export-short-interest-backfill
python -m target_opportunity_monitor short-interest-missing-coverage-plan
python -m target_opportunity_monitor short-interest-provider-diagnostics --ticker CRM
python -m target_opportunity_monitor resolve-short-interest-missing-sources
python -m target_opportunity_monitor resolve-short-interest-missing-sources --ticker CRM
python -m target_opportunity_monitor export-short-interest-missing-provider-template
python -m target_opportunity_monitor short-interest-coverage-plan
python -m target_opportunity_monitor short-interest-source-status --missing-only
python -m target_opportunity_monitor validate-short-interest-backfill
python -m target_opportunity_monitor preview-short-interest-import
python -m target_opportunity_monitor import-short-interest-source-exports
python -m target_opportunity_monitor apply-short-interest-provider-backfill
python -m target_opportunity_monitor apply-short-interest-provider-backfill --confirm
python -m target_opportunity_monitor load-short-interest
python -m target_opportunity_monitor compute-short-interest-signals
python -m target_opportunity_monitor validate-short-interest-signals
python -m target_opportunity_monitor short-interest-status
python -m target_opportunity_monitor short-interest-validation-report
```

The safe operating sequence is:

```powershell
python -m target_opportunity_monitor short-interest-provider-status
python -m target_opportunity_monitor fetch-short-interest-sources --provider all
python -m target_opportunity_monitor import-short-interest-source-exports
python -m target_opportunity_monitor load-short-interest
python -m target_opportunity_monitor compute-short-interest-signals
python -m target_opportunity_monitor validate-short-interest-signals
```

If direct provider fetches do not cover the ticker, normalize a source-backed
export:

```powershell
python -m target_opportunity_monitor normalize-short-interest-provider-export --provider broker --file PATH
python -m target_opportunity_monitor export-short-interest-backfill
python -m target_opportunity_monitor validate-short-interest-backfill
python -m target_opportunity_monitor preview-short-interest-import
python -m target_opportunity_monitor import-short-interest-source-exports
python -m target_opportunity_monitor load-short-interest
python -m target_opportunity_monitor compute-short-interest-signals
python -m target_opportunity_monitor validate-short-interest-signals
```

For the focused Phase 10G.3 closure path, use:

```powershell
python -m target_opportunity_monitor short-interest-missing-coverage-plan
python -m target_opportunity_monitor short-interest-provider-diagnostics --ticker CRM
python -m target_opportunity_monitor resolve-short-interest-missing-sources
python -m target_opportunity_monitor export-short-interest-missing-provider-template
python -m target_opportunity_monitor apply-short-interest-provider-backfill
```

The apply command is a dry run unless `--confirm` is supplied. Confirmed apply
aborts when there are invalid rows, zero valid rows for currently missing
tickers, or no projected source-backed coverage improvement. Existing valid rows
for already covered tickers do not count as progress.

Ticker-scoped commands are also supported:

```powershell
python -m target_opportunity_monitor compute-short-interest-signals --ticker AAPL
python -m target_opportunity_monitor validate-short-interest-signals --ticker AAPL
```

Provider cache files live under:

```text
data/signals/cache/short_interest/
```

Cache-first daily behavior is conservative. Use `--force-refresh` only when you
intentionally want to bypass the local cache:

```powershell
python -m target_opportunity_monitor fetch-short-interest-sources --provider all --force-refresh
python -m target_opportunity_monitor fetch-short-interest-sources --provider all --no-cache
```

## Current Limits

- Direct official/provider fetch is best effort; provider/export normalization is
  the accepted fallback when free official endpoints are incomplete or blocked.
- No scraping.
- No ETF short-interest scoring.
- No score-impact or alert-impact.
- Validation uses stored daily prices and remains evidence collection only.
