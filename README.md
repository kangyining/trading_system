# Target Opportunity Monitor

Local scaffold for the Target Opportunity Monitor trading-system project.

## Commands

Run these from this folder:

```powershell
python -m target_opportunity_monitor init-db
python -m target_opportunity_monitor status
python -m target_opportunity_monitor run-daily
python -m target_opportunity_monitor load-watchlist
python -m target_opportunity_monitor list-assets
python -m target_opportunity_monitor update-prices
python -m target_opportunity_monitor price-status
python -m target_opportunity_monitor load-fundamentals
python -m target_opportunity_monitor load-estimates
python -m target_opportunity_monitor load-etf-navs
python -m target_opportunity_monitor load-etf-holdings
python -m target_opportunity_monitor seed-fundamentals
python -m target_opportunity_monitor compute-targets
python -m target_opportunity_monitor etf-status
python -m target_opportunity_monitor valuation-status
python -m target_opportunity_monitor verify-universe
python -m target_opportunity_monitor verify-ticker --ticker AAPL
python -m target_opportunity_monitor refresh-data --daily
python -m target_opportunity_monitor probe-market --source ibkr
python -m target_opportunity_monitor ibkr-status
python -m target_opportunity_monitor ibkr-probe --ticker SPY
python -m target_opportunity_monitor update-quotes --source ibkr
python -m target_opportunity_monitor update-etf-navs --source auto
python -m target_opportunity_monitor range-monitor --source ibkr
python -m target_opportunity_monitor range-status
python -m target_opportunity_monitor compute-technical-signals
python -m target_opportunity_monitor compute-regime-signals
python -m target_opportunity_monitor technical-status
python -m target_opportunity_monitor regime-status
python -m target_opportunity_monitor intraday-cycle --source ibkr --deliver --channel file
python -m target_opportunity_monitor intraday-status
python -m target_opportunity_monitor scheduler-status
python -m target_opportunity_monitor manual-ops-cycle --mode auto --deliver --channel file
python -m target_opportunity_monitor tom-loop-start --mode auto --deliver --channel file
python -m target_opportunity_monitor tom-loop-status
python -m target_opportunity_monitor tom-loop-health
python -m target_opportunity_monitor manual-ops-status
python -m target_opportunity_monitor notification-status
python -m target_opportunity_monitor notification-status --pending-only
python -m target_opportunity_monitor deliver-notifications --channel console
python -m target_opportunity_monitor deliver-notifications --channel file
python -m target_opportunity_monitor test-notification-channel --channel file
python -m target_opportunity_monitor asset-status --ticker AAPL
python -m target_opportunity_monitor add-asset --ticker TSLA --asset-type equity --exchange NASDAQ --currency USD --country US
python -m target_opportunity_monitor deactivate-asset --ticker TSLA --reason "example"
python -m target_opportunity_monitor compute-scores
python -m target_opportunity_monitor score-status
python -m target_opportunity_monitor compute-alerts
python -m target_opportunity_monitor alert-status
python -m target_opportunity_monitor update-alert-outcomes
python -m target_opportunity_monitor outcome-status
python -m target_opportunity_monitor validation-report
python -m target_opportunity_monitor load-portfolio
python -m target_opportunity_monitor compute-portfolio-context
python -m target_opportunity_monitor portfolio-status
python -m target_opportunity_monitor load-analyst-revisions
python -m target_opportunity_monitor compute-revision-signals
python -m target_opportunity_monitor validate-revision-signals
python -m target_opportunity_monitor revision-validation-report
python -m target_opportunity_monitor revision-evidence-report
python -m target_opportunity_monitor fetch-news-catalyst-sources --provider all
python -m target_opportunity_monitor import-news-catalyst-source-exports
python -m target_opportunity_monitor aggregate-news-catalyst-sources
python -m target_opportunity_monitor load-news-catalysts
python -m target_opportunity_monitor compute-news-catalyst-signals
python -m target_opportunity_monitor validate-news-catalyst-signals
python -m target_opportunity_monitor news-catalyst-source-status
python -m target_opportunity_monitor news-catalyst-status
python -m target_opportunity_monitor news-catalyst-validation-report
python -m target_opportunity_monitor fetch-insider-transactions
python -m target_opportunity_monitor compute-insider-signals
python -m target_opportunity_monitor validate-insider-signals
python -m target_opportunity_monitor insider-source-status
python -m target_opportunity_monitor insider-status
python -m target_opportunity_monitor insider-validation-report
python -m target_opportunity_monitor signal-status
python -m target_opportunity_monitor option-chain-coverage-plan
python -m target_opportunity_monitor export-options-chain-missing-template
python -m target_opportunity_monitor apply-options-chain-coverage-backfill
python -m target_opportunity_monitor export-universe-candidate-template
python -m target_opportunity_monitor universe-expansion-plan
python -m target_opportunity_monitor apply-universe-candidates --confirm --allow-partial
python -m target_opportunity_monitor research-ticker-plan --ticker TSLA
python -m target_opportunity_monitor apply-research-ticker --ticker TSLA --confirm
python -m target_opportunity_monitor refresh-research-ticker --ticker TSLA
python -m target_opportunity_monitor research-ticker-status --ticker TSLA
python -m target_opportunity_monitor generate-research-recommendations --source all
python -m target_opportunity_monitor research-recommendation-status
python -m target_opportunity_monitor research-recommendation-report
python -m target_opportunity_monitor set-research-recommendation-status --id 1 --status approved
python -m target_opportunity_monitor promote-research-recommendation --id 1 --confirm
python -m target_opportunity_monitor api-status
python -m target_opportunity_monitor serve-api --once-smoke-test
python -m target_opportunity_monitor serve-api
python -m target_opportunity_monitor compute-fundamental-benchmarks
python -m target_opportunity_monitor fundamental-benchmark-status
python -m target_opportunity_monitor fundamental-benchmark-report --ticker TSLA
python -m target_opportunity_monitor build-dashboard
```

## Current Scope

Current implemented scope through Phase 10E.10, Phase 10F.2, Phase 10G.3, Phase 10H.5, Phase 11A, Phase 11B, Phase 11C, Phase 11D.3, Phase 12A, Phase 12B, Phase 12B.1, Phase 12B.2, Phase 12B.3, Phase 12C, Phase 12D, Phase 12E, Phase 12E.1, Phase 12F, Phase 13A, Phase 13B, Phase 13C, Phase 14A, Phase 14B, Phase 14C, Phase 14D, Phase 14E, and Phase 15A:

- Python project scaffold.
- SQLite schema initialization.
- CLI commands.
- Daily Markdown and CSV reports.
- Manual watchlist CSV loading.
- Local asset/fundamental/estimate storage helpers.
- Online-first market-data ingestion with CSV fallback.
- Price storage, price features, and price data-quality checks.
- Manual fundamentals and estimates CSV loading.
- SEC companyfacts fundamentals seeding with raw JSON cache.
- Non-alerting valuation target-range calculation.
- Manual ETF NAV and holdings CSV loading.
- ETF NAV-based target-range calculation.
- ETF status output and daily report ETF coverage.
- Valuation status output and daily report valuation coverage.
- Pre-alert readiness verification for equities and ETFs.
- Scheduler-friendly daily refresh orchestration.
- Optional read-only IBKR Gateway checks, historical-price source, quote snapshots, and ETF NAV attempts.
- Intraday price-vs-target gap snapshots.
- Pipeline run and step-result audit logging.
- Technical support/resistance, trend, and price-location snapshots from stored
  OHLCV history.
- Market-regime snapshots for SPY/QQQ and configured sector proxies, with
  missing sector ETF history reported as non-blocking warnings.
- Explainable equity opportunity scoring for AAPL, MSFT, and NVDA.
- ETF scoring for SPY and QQQ from ETF NAV/features/holdings.
- Unified score status and daily report score coverage.
- Explainable daily/EOD equity alerts for AAPL, MSFT, and NVDA.
- ETF-specific daily/EOD NAV-dislocation alert evaluation for SPY and QQQ.
- Alert status output and daily report alert summary.
- Richer equity alert reporting with executive summary, ticker-level details,
  report CSV rows, data-health summary, and model-health summary.
- Alert outcome tracking for actionable equity alerts.
- ETF alert outcome tracking for future actionable ETF alerts.
- Simple validation report with pending/completed coverage, hit-rate, false-positive,
  return, and opportunity-bucket summaries.
- Static local dashboard with daily alerts, watchlist ranking, ticker detail,
  price-vs-target chart, score breakdown, alert history, outcome status, data
  health, model health, and portfolio review.
- Manual portfolio positions and cash CSV loading.
- Read-only portfolio review categories and advisory sizing guidance.
- Portfolio context in status, daily Markdown/CSV reports, daily refresh, and
  dashboard output.
- Manual option-chain CSV loading.
- Read-only sell-put advisory reviews with premium, breakeven, annualized
  yield, downside buffer, assignment notional, liquidity/range warnings, and
  commentary claim linkage.
- Options advisory coverage in status, daily Markdown/CSV reports, daily
  refresh, and dashboard output.
- Option-chain activation diagnostics, minimum source-backed backfill plan for
  `SOXL`, `KORU`, and `AAPL`, and guarded activation apply.
- Source-backed minimum option-chain activation for `SOXL`, `KORU`, and `AAPL`,
  producing initial read-only sell-put review rows while IBKR remains read-only.
- Read-only cash-secured options risk reviews with assignment notional,
  cash-secured requirement, premium income, max-loss proxy, downside scenario
  P/L, portfolio-context warnings, and reference-instrument warnings.
- Read-only option review outcome tracking from underlying daily prices,
  including 5d/20d/expiration status, strike/breakeven touch flags, favorable
  and adverse excursion, and a manual option-position ledger.
- Broader option-chain coverage planning and guarded source-backed backfill for
  the options-eligible universe beyond the minimum `SOXL`/`KORU`/`AAPL` set.
- Expanded-universe candidate intake with guarded apply through the existing
  watchlist, asset, CIK, and asset-change audit paths.
- Sector benchmark mapping for SPY/QQQ plus GICS-style sector ETF proxies.
- Local fundamental benchmark snapshots for overall, sector, and industry
  groups, and ticker comparison snapshots versus overall medians, sector
  medians, industry medians, SPY/QQQ relative strength, and mapped sector ETF
  relative strength.
- Local-only HTTP/JSON TOM API server for the future JS control center, with
  health/status/dashboard/assets/research/options/provider endpoints and
  confirmation-gated mutation routes.
- Separate Vite/React/TypeScript read-only control center at
  `F:\Investments\tom-ui`, covering overview, assets, research recommendations,
  options/provider status, and dashboard-data inspection through the local TOM
  API.
- Approval-gated research recommendation and ticker-intake UI workflows for
  planning, approving/rejecting, promoting, applying, refreshing, and viewing
  ticker benchmark reports through the local TOM API.
- Confirmation-gated JS UI controls for asset add/deactivate/reactivate/soft
  remove, one-shot intraday/manual ops cycles, scheduler visibility, and
  notification delivery/outbox draining.
- Confirmation-gated JS UI activation/backfill controls for account-context
  templates, portfolio/cash/option-position row staging, options chain backfill,
  news/catalyst provider-native backfill, and short-interest missing-row
  backfill.
- Read-only account provider status plus file/IBKR account-context staging,
  with `generic`, `ibkr`, `ibkr-flex`, and `ibkr-activity` normalization labels
  feeding the existing validate/preview/apply workflow.
- Manual analyst revision signal CSV loading.
- Analyst revision shadow signals stored in the shared `signals` table.
- Analyst revision validation through `signal_outcomes`.
- Analyst revision evidence gate for source coverage, validation maturity,
  20-day hit rate, direction-adjusted returns, and signal confidence.
- Multi-source analyst revision source snapshots and aggregate rows.
- Optional FMP, Alpha Vantage, Business Quant, Finnhub, yfinance/Yahoo, and
  IBKR analyst-revision source adapters, with Google Finance explicitly marked
  unsupported for this signal.
- Audited no-API source-export workflow for SecBot, TECHi, RedMatter,
  Morningstar, GuruFocus, and user/provider exports.
- Manual source-backed news/catalyst shadow signals.
- Multi-source news/catalyst source snapshots and aggregate rows.
- Optional Alpha Vantage, Marketaux, EODHD, Finnhub, FMP, X recent-search, and
  Truth Social public news/catalyst source adapters.
- Audited news/catalyst source-export workflow for headline/event capture from
  no-API or provider-export sources.
- Conservative deterministic text-derived numeric backfill for source-backed
  headline/event rows when provider-numeric sentiment is unavailable. These rows
  are lower-confidence and remain shadow-only.
- Provider-native news/catalyst backfill package export, strict provider-native
  import validation, and provider-native progress reporting.
- News/catalyst validation through `signal_outcomes`.
- Official SEC Form 4 insider transaction source snapshots.
- Insider activity shadow signals and validation through `signal_outcomes`.
- Manual source-backed short-interest snapshots.
- Short-interest source-export backfill templates, validation, preview, and import.
- Official/provider short-interest fetch and export normalization, with cache-first
  fallback and no-fabrication validation.
- Focused short-interest missing-coverage diagnostics and guarded backfill apply
  for uncovered equities.
- Short-interest shadow signals and validation through `signal_outcomes`.
- Trader commentary raw capture, structured claim parsing, claim-level validation,
  and compact shadow signals for user-provided commentary.
- Commentary-driven onboarding candidates, explicit instrument-label aliases,
  and reference-instrument roles for priced commentary validation without
  forcing every mentioned ticker into the scoreable trading universe.
- Reference commentary instruments activated for `BRK.B`, `HOOD`, `KORU`,
  `SOXL`, `TSLA`, `XLF`, and `XLV`, with price history and pending
  commentary validation outcomes.
- Disabled-by-default Discord official bot/API capture for authorized channels,
  with dedupe and raw-commentary ingestion.
- Near-real-time range monitoring from latest quote snapshots or daily fallback
  prices.
- Equity buy/hold/trim/sell range states from targets, scores, alerts, risk,
  liquidity, confidence, and portfolio context.
- ETF NAV/premium-discount range states with tighter ETF-specific thresholds.
- Deduped local notification events and delivery audit rows for range crossings.
- Console/dashboard/Codex-scheduler-friendly notification output.
- Asset add, deactivate, reactivate, soft-remove, and status commands with an
  audit trail.
- Manual TOM ops runner that replaces the TOM-specific Codex heartbeat/cron
  automations with one-shot and never-ending local commands while explicitly
  leaving browser/content capture automations separate.
- Optional `active` watchlist column for active/inactive universe management.
- Advanced signal status in CLI, daily Markdown/CSV reports, daily refresh, and
  dashboard output.
- Standard-library unit tests.

It does not send external push/email/chat notifications, run ML models, let
advanced signals change alerts by default, place orders, run broker write
actions, or value ETFs through full holdings look-through. Portfolio guidance is
advisory only and does not calculate executable share quantities.

## Phase 3 Manual Data

Default editable CSV files:

```text
data/fundamentals/manual/fundamentals.csv
data/fundamentals/manual/estimates.csv
```

The files currently include manual seed rows for AAPL, MSFT, and NVDA.

Refresh SEC-backed actual fundamentals with:

```powershell
python -m target_opportunity_monitor seed-fundamentals
python -m target_opportunity_monitor load-estimates
python -m target_opportunity_monitor compute-targets
python -m target_opportunity_monitor run-daily
```

## Phase 3B ETF Data

Default editable CSV files:

```text
data/etf/manual/etf_navs.csv
data/etf/manual/etf_holdings.csv
```

ETF targets are NAV-based and use separate ETF storage tables while still showing
in the unified `targets`, `valuation-status`, and daily-report outputs.
The current seed files include issuer-backed rows for SPY and QQQ:

- SPY uses State Street official NAV history, premium/discount history, and
  daily holdings workbooks.
- QQQ uses Invesco official price/NAV and holdings API responses embedded by
  the Invesco QQQ product page.
- SPY currently has a 60-row premium/discount history. QQQ currently has the
  latest official NAV row and top-10 holdings; missing QQQ premium-history
  z-score remains a non-blocking model warning.

```powershell
python -m target_opportunity_monitor load-etf-navs
python -m target_opportunity_monitor load-etf-holdings
python -m target_opportunity_monitor compute-targets --ticker SPY
python -m target_opportunity_monitor compute-targets --ticker QQQ
python -m target_opportunity_monitor compute-scores --asset-type etf
python -m target_opportunity_monitor etf-status
```

Phase 4 scoring should keep ETF logic separate from single-company logic. ETF
scores should use NAV dislocation, premium/discount behavior, holdings
concentration, tracking quality, liquidity, and underlying/index momentum with
tighter alert thresholds than single-company valuation gaps.

## Phase 3C Scheduled Pipeline

Daily source-of-truth refresh:

```powershell
python -m target_opportunity_monitor refresh-data --daily
```

Lightweight intraday probe:

```powershell
python -m target_opportunity_monitor probe-market --source ibkr
```

Readiness checks:

```powershell
python -m target_opportunity_monitor verify-universe
python -m target_opportunity_monitor verify-ticker --ticker SPY
```

IBKR is optional and read-only. If Gateway is closed or a data subscription is
missing, commands record warnings and leave durable daily data untouched. ETF
NAV from IBKR is attempted through ETF NAV tick fields, but CSV/manual issuer
NAV remains the fallback until live NAV emission is confirmed.

## Phase 4 Scoring

Compute the current daily opportunity scores:

```powershell
python -m target_opportunity_monitor compute-scores
python -m target_opportunity_monitor compute-scores --ticker AAPL
python -m target_opportunity_monitor compute-scores --asset-type equity
python -m target_opportunity_monitor score-status
```

Equity scoring uses the latest targets, fundamentals, estimates, and price
features. The MVP stores explainable 0-100 components for valuation gap,
quality, growth, revisions, momentum, risk, liquidity, confidence, timing,
expected value, and final opportunity score.

ETF scoring uses a separate model path and threshold set. SPY and QQQ now have
issuer-backed ETF NAV/features/holdings and can produce ETF scores based on NAV
dislocation, premium/discount behavior, holdings concentration, liquidity, and
underlying/index momentum.

## Phase 5A Equity Alerts

Compute the current daily equity alerts:

```powershell
python -m target_opportunity_monitor compute-alerts
python -m target_opportunity_monitor compute-alerts --ticker AAPL
python -m target_opportunity_monitor compute-alerts --asset-type equity
python -m target_opportunity_monitor alert-status
```

Phase 5A alerts use the latest target ranges and opportunity scores. The MVP
supports `bullish_divergence`, `bearish_overvaluation`, `watch_only_gap`,
`risk_warning`, `data_quality_warning`, and `no_alert` daily evaluations.

ETF alerts use a separate ETF-specific rule set and tighter NAV-dislocation
thresholds than single-company equity alerts.
Revision-inflection, sentiment, real-time, and order execution workflows remain
disabled.

## Phase 6A Daily Reports

Generate the current read-and-filter report set:

```powershell
python -m target_opportunity_monitor run-daily
```

This writes both:

```text
reports/YYYY-MM-DD-daily-report.md
reports/YYYY-MM-DD-daily-report.csv
```

The Markdown report is the decision-facing daily readout. It includes an
executive alert summary, AAPL/MSFT/NVDA ticker-level alert details, data-health
and model-health summaries, ETF alert/outcome status, and the full alert table.

The CSV report is the scan/filter surface. It includes ticker, asset type,
current price, target range, valuation gap, opportunity/confidence/timing/risk/
liquidity/data-quality scores, alert metadata, reasons, risks, invalidation,
data freshness, and model warnings.
After Phase 9A, the CSV also includes portfolio held flag, quantity, position
value/weight, sector weight, cash available, review category, sizing guidance,
max add value, and portfolio warnings.

## Phase 7A/7B Outcome Tracking

Update and inspect current alert outcomes:

```powershell
python -m target_opportunity_monitor update-alert-outcomes
python -m target_opportunity_monitor update-alert-outcomes --ticker MSFT
python -m target_opportunity_monitor update-alert-outcomes --asset-type etf
python -m target_opportunity_monitor outcome-status
python -m target_opportunity_monitor validation-report
```

Phase 7A measures actionable equity alerts. Phase 7B extends the same outcome
surface to actionable ETF NAV-dislocation alerts. Both track 5d/20d/60d/120d
returns, target hits, invalidation hits, max favorable excursion, and max
adverse excursion from stored daily prices. New alerts normally start as
`pending` until enough future price rows exist.

ETF validation uses tighter invalidation assumptions than single equities
because ETF NAV gaps are much smaller. Outcome tracking does not send
notifications, place orders, or change alert rules.

## Phase 8A Static Dashboard

Build the local dashboard:

```powershell
python -m target_opportunity_monitor build-dashboard
```

This writes:

```text
dashboard/index.html
```

The dashboard opens directly from disk and requires no server, package
dependency, CDN, or network access. It embeds the latest local SQLite/reporting
data into one self-contained HTML file with sections for alerts, rankings,
ticker detail, price-vs-target, score breakdown, alert history, outcome status,
data health, model health, and portfolio review.

SPY and QQQ remain visible as ETF rows with NAV-based targets, ETF scores, and
ETF alert evaluations. Portfolio review is visible but ETF-specific portfolio
actions remain conservative until ETF alert outcomes are validated.

## Phase 9A Portfolio Context

Default editable CSV files:

```text
data/portfolio/manual/positions.csv
data/portfolio/manual/cash.csv
```

Load and compute portfolio context:

```powershell
python -m target_opportunity_monitor load-portfolio
python -m target_opportunity_monitor compute-portfolio-context
python -m target_opportunity_monitor portfolio-status
```

`positions.csv` requires `ticker` and `quantity`. Optional columns include
`account`, `position_date`, `currency`, `market_price`, `market_value`,
`base_market_value`, `cost_basis_per_share`, `cost_basis_total`, `asset_type`,
`sector`, `source`, `as_of_date`, and `effective_date`.

`cash.csv` requires `cash_amount`. Optional columns include `account`,
`cash_date`, `currency`, `base_cash_amount`, `source`, `as_of_date`, and
`effective_date`.

The engine outputs read-only categories: `watch`, `research_deeper`,
`review_existing_position`, `small_starter_candidate`, `add_candidate`,
`reduce_risk_review`, and `exit_review_candidate`. It never places orders,
writes to a broker, or calculates executable share quantities.

## Phase 10A Analyst Revision Shadow Signals

Default editable CSV file:

```text
data/signals/manual/analyst_revisions.csv
```

Load and compute analyst revision shadow signals:

```powershell
python -m target_opportunity_monitor load-analyst-revisions
python -m target_opportunity_monitor compute-revision-signals
python -m target_opportunity_monitor validate-revision-signals
python -m target_opportunity_monitor revision-validation-report
python -m target_opportunity_monitor revision-evidence-report
python -m target_opportunity_monitor derive-analyst-revisions
python -m target_opportunity_monitor revision-source-status
python -m target_opportunity_monitor signal-status
```

`analyst_revisions.csv` requires `ticker` and `signal_date`. Optional columns
include `eps_revision_1m`, `eps_revision_3m`, `revenue_revision_1m`,
`revenue_revision_3m`, `target_price_revision_3m`,
`recommendation_revision`, `estimate_dispersion`, `analyst_count`, `source`,
`source_url`, `notes`, `as_of_date`, and `effective_date`.

Revision values are decimal percentages: `0.05` means `+5%`. The first version
is shadow-mode only: revision scores are visible in `signal-status`, scores,
reports, and dashboard, but they do not change final opportunity scores or
alerts while `signals.analyst_revision_shadow_mode = true`.

## Phase 10B Analyst Revision Validation

Phase 10B validates stored `analyst_revision.composite` shadow signals against
local daily prices. It tracks 5d, 20d, 60d, and 120d forward returns in
`signal_outcomes`, marks immature horizons as pending, and keeps the signal
shadow-only.

Analyst revision rows should be source-backed. Use `source_url` and `notes` for
manual audit context, leave unknown fields blank, and do not fabricate revision
values when a reliable source is unavailable.

## Phase 10C Analyst Revision Evidence Gate

Phase 10C keeps analyst revisions in shadow mode and adds an explicit evidence
gate. The gate reads existing `signals` and `signal_outcomes`; it does not add a
new table and does not change opportunity scores or alerts.

Use:

```powershell
python -m target_opportunity_monitor revision-evidence-report
```

The evidence decision is one of `insufficient_source_coverage`,
`collecting_evidence`, `keep_shadow`, or
`eligible_for_limited_score_trial`. A limited trial is only a future Phase 10D
option; `signals.analyst_revision_shadow_mode = true` remains the default.

Source workflow guidance lives in
`DOCS/analyst-revision-source-workflow.md`. The current manual CSV should only
contain AAPL/MSFT/NVDA rows when the revision values are source-backed by a
provider export or a currently accessible public source. SPY/QQQ remain ETF
gated and should not receive company analyst-revision rows.

## Phase 10C.1 Source-Backed Analyst Revision Import

Default source-export CSV file:

```text
data/signals/source_exports/analyst_revision_source_export.csv
```

Use this file for manually captured public-source tables or provider exports.
The derivation command converts auditable raw fields into the final
`data/signals/manual/analyst_revisions.csv` file:

```powershell
python -m target_opportunity_monitor derive-analyst-revisions
python -m target_opportunity_monitor load-analyst-revisions
python -m target_opportunity_monitor compute-revision-signals
python -m target_opportunity_monitor validate-revision-signals
python -m target_opportunity_monitor revision-source-status
python -m target_opportunity_monitor revision-evidence-report
```

The source-export file requires `ticker`, `signal_date`, `source`,
`source_url`, and `notes`. It can derive EPS, revenue, target-price,
recommendation, and dispersion fields when the raw current/prior values are
available. Rows without `source_url`, `notes`, or any derivable numeric signal
are rejected. ETF rows remain gated and are not written to the final company
analyst-revision CSV.

## Phase 10C.2 Multi-Source Analyst Revision Aggregation

Phase 10C.2 preserves each provider or public-source row in
`analyst_revision_source_snapshots`, reconciles comparable fields into
`analyst_revision_aggregates`, and exports the aggregate row back to
`data/signals/manual/analyst_revisions.csv` for the existing shadow-signal
pipeline.

API keys are read from environment variables only and are never printed:

```text
FMP_API_KEY
FINANCIAL_MODELING_PREP_API_KEY
ALPHAVANTAGE_API_KEY
BUSINESSQUANT_API_KEY
BUSINESS_QUANT_API_KEY
FINNHUB_API_KEY
FINHUB_API_KEY
```

Current provider roles are intentionally field-specific:

- Alpha Vantage and yfinance/Yahoo can provide true EPS current vs prior trend
  values when available.
- FMP and Business Quant provide current consensus and dispersion-style fields.
- Finnhub currently contributes recommendation-trend changes with the available
  key; EPS and price-target estimate endpoints may require another Finnhub plan.
- Manual/public captures such as SecBot remain useful audit rows, but unsupported
  fields must stay blank.
- When a provider fails or returns no usable row, TOM stores an unavailable
  source snapshot for audit, excludes it from the weighted-median aggregate, and
  adds a `source_unavailable:SOURCE` warning.

Daily and manual commands:

```powershell
python -m target_opportunity_monitor fetch-revision-sources --provider all
python -m target_opportunity_monitor import-revision-source-exports
python -m target_opportunity_monitor aggregate-revision-sources
python -m target_opportunity_monitor load-analyst-revisions
python -m target_opportunity_monitor compute-revision-signals
python -m target_opportunity_monitor validate-revision-signals
python -m target_opportunity_monitor revision-provider-status
python -m target_opportunity_monitor revision-source-status
```

No-API sources use CSV templates in `data/signals/source_exports/`, including
SecBot, TECHi, RedMatter, Morningstar manual, and GuruFocus manual files. Use
only source-backed values, leave unsupported fields blank, and keep analyst
revisions in shadow mode until validation evidence is mature.

## Phase 10E News/Catalyst Shadow Signals

Phase 10E adds a second advanced signal family in shadow mode. It stores
source-backed news, event, and catalyst rows in the shared `signals` table and
validates only the `news_catalyst.composite` signal against stored daily prices.
It does not change opportunity scores, alerts, portfolio guidance, or trading
behavior.

Default editable CSV:

```text
data/signals/manual/news_catalysts.csv
```

Required columns:

```text
ticker, signal_date, source, source_url, headline_or_event
```

Optional columns:

```text
event_date, sentiment_score, catalyst_score, urgency_score, confidence, topic, notes
```

Scores are `0-100` values. Use only auditable source-backed rows: filings,
company releases, earnings events, reputable news articles, conference/product
events, or provider exports. Do not fabricate sentiment, catalyst, urgency, or
confidence values. ETF rows may be recorded for information, but they are gated
from news/catalyst scoring in this MVP.

Manual compatibility commands:

```powershell
python -m target_opportunity_monitor load-news-catalysts
python -m target_opportunity_monitor compute-news-catalyst-signals
python -m target_opportunity_monitor validate-news-catalyst-signals
python -m target_opportunity_monitor news-catalyst-status
python -m target_opportunity_monitor news-catalyst-validation-report
```

Daily refresh runs the news/catalyst load, compute, and validation steps before
final Markdown/CSV reports and the static dashboard are generated.

## Phase 10E.1 News/Catalyst Source Aggregation

Phase 10E.1 adds a source-backed aggregation layer before the final
`news_catalysts.csv` compatibility file. Provider/API and audited manual-export
rows are stored in `news_catalyst_source_snapshots`, then reconciled into one
canonical aggregate row per `ticker + signal_date` in
`news_catalyst_aggregates`.

Default source-export directory:

```text
data/signals/source_exports/news_catalysts/
```

Source-export files require:

```text
ticker, signal_date, source, source_url, headline_or_event
```

Optional source-export fields:

```text
article_datetime, event_date, topic, summary, sentiment_score, catalyst_score,
urgency_score, relevance_score, confidence, notes, capture_method
```

Aggregation rules:

- Numeric fields are aggregated by weighted median.
- Default source weights are Alpha Vantage `1.0`, Marketaux `1.0`, EODHD `0.9`,
  Finnhub `0.8`, FMP `0.7`, X recent-search `0.35`, Truth Social public `0.25`,
  deterministic text backfill `0.35`, and licensed/manual provider exports `0.9`.
- Headline-only rows are preserved for audit and do not create numeric
  aggregates by themselves unless the Phase 10E.4 deterministic text-backfill
  step is enabled.
- Provider failures, missing API keys, rate limits, and plan limits become
  warnings instead of daily-pipeline failures.
- ETF rows can be captured as informational source snapshots, but SPY/QQQ stay
  gated from news/catalyst scoring in this MVP.

Commands:

```powershell
python -m target_opportunity_monitor fetch-news-catalyst-sources --provider all --max-tickers 3
python -m target_opportunity_monitor fetch-news-catalyst-sources --provider marketaux --coverage-plan
python -m target_opportunity_monitor import-news-catalyst-source-exports
python -m target_opportunity_monitor compute-news-catalyst-text-backfill
python -m target_opportunity_monitor aggregate-news-catalyst-sources
python -m target_opportunity_monitor news-catalyst-source-status
```

Daily refresh now runs provider fetch, source-export import, text backfill,
aggregation, load, compute, and validation before final reports and dashboard.

Detailed source-capture rules are in
`DOCS/news-catalyst-source-workflow.md`.

## Phase 10E.2 News/Catalyst Provider Reliability

Provider fetches are budgeted and cache-aware so a daily run does not hammer
rate-limited APIs. Raw provider payloads are cached under:

```text
data/signals/cache/news_catalysts/{provider}/
```

The cache stores provider, ticker, timestamp, and returned JSON payload only.
API keys are read from environment variables and are never written to cache,
reports, dashboard data, or logs.

Fetch controls:

```powershell
python -m target_opportunity_monitor fetch-news-catalyst-sources --provider alpha_vantage --max-tickers 1 --force-refresh
python -m target_opportunity_monitor fetch-news-catalyst-sources --provider all --use-cache
python -m target_opportunity_monitor fetch-news-catalyst-sources --provider all --no-cache --max-tickers 1
```

Default reliability settings live in `configs/default.toml`:

```text
news_catalyst_provider_request_budget = 3
news_catalyst_provider_retry_delay_seconds = 1.0
news_catalyst_cache_stale_hours = 24
news_catalyst_use_cache = true
```

Alpha Vantage remains the preferred numeric news-sentiment source. Finnhub and
FMP rows are preserved when available, but headline-only rows still do not
create numeric aggregates by themselves. Provider auth, plan, rate-limit, HTTP,
and headline-only states are surfaced as warnings, not fatal pipeline errors.

## Phase 10E.3 News/Catalyst Coverage Queue

News/catalyst coverage is managed with bounded work queues so missing numeric
rows and provider-native quality upgrades can be filled steadily without
fabricating scores or hammering providers. The planner prioritizes missing
active equities first, then text-derived-only provider-upgrade candidates, then
stale source-backed rows. SPY and QQQ remain ETF-gated for news/catalyst
scoring.

Commands:

```powershell
python -m target_opportunity_monitor news-catalyst-coverage-plan
python -m target_opportunity_monitor news-catalyst-coverage-plan --mode missing
python -m target_opportunity_monitor news-catalyst-coverage-plan --mode provider-upgrade
python -m target_opportunity_monitor news-catalyst-source-status --missing-only
python -m target_opportunity_monitor news-catalyst-source-status --provider-upgrade-only
python -m target_opportunity_monitor news-catalyst-source-status --provider-warnings
python -m target_opportunity_monitor fetch-news-catalyst-sources --coverage-plan
```

`news-catalyst-coverage-plan --mode missing` writes a missing-numeric refill
template at:

```text
data/signals/source_exports/news_catalysts/news_catalyst_missing_coverage_queue.csv
```

`news-catalyst-coverage-plan --mode provider-upgrade` writes a provider-native
upgrade template at:

```text
data/signals/source_exports/news_catalysts/news_catalyst_provider_upgrade_queue.csv
```

Each generated row is a blank, auditable placeholder for either a missing
numeric ticker or a ticker currently covered only by lower-confidence
text-derived rows. Fill it only with source-backed values from an API export,
licensed/user provider export, or public source that clearly provides numeric
sentiment/catalyst fields. Rows without `source_url`, `headline_or_event`, and
at least one numeric field remain non-aggregating audit context.

Daily refresh uses the coverage planner for bounded provider fetches, then
runs the existing import, aggregate, load, compute, and validation steps. The
status command, reports, CSV, and dashboard show missing ticker count, latest
coverage-plan tickers, and provider limitation summaries.

## Phase 10E.4 News/Catalyst Numeric Coverage Expansion

Phase 10E.4 adds more source paths and a conservative numeric backfill layer so
headline-only source-backed rows can become evidence-producing without inventing
sentiment.

New provider/source adapters:

- `marketaux`: preferred new provider-numeric source when `MARKETAUX_API_KEY`
  or `MARKET_AUX_API_KEY` is present.
- `eodhd`: optional provider-numeric source when `EODHD_API_KEY` or
  `EOD_HISTORICAL_DATA_API_KEY` is present.
- `x_recent_search`: source-backed social/news text when `X_BEARER_TOKEN` or
  `TWITTER_BEARER_TOKEN` is present.
- `truth_social_public`: unauthenticated public post monitor for macro/catalyst
  context; text-only.
- `source_export`: audited manual/provider exports, including Serenity,
  Kobeissi, newsletters, X screenshots/exports, and paid provider exports.

Text backfill rules:

- Provider numeric scores remain higher priority.
- If a ticker only has source-backed text, `compute-news-catalyst-text-backfill`
  derives deterministic `0-100` sentiment/catalyst/urgency rows from a fixed
  lexicon.
- Derived rows use `source = "news_text_backfill"` and warnings including
  `text_derived_sentiment`, `lower_confidence_source`, and
  `not_provider_numeric`.
- Text-derived rows use lower aggregation weight and remain shadow-only.
- No LLM scoring, scraping, guessed values, score impact, alert impact, or
  portfolio impact is added.

Commands:

```powershell
python -m target_opportunity_monitor news-catalyst-coverage-plan --refresh-template
python -m target_opportunity_monitor fetch-news-catalyst-sources --provider marketaux --coverage-plan
python -m target_opportunity_monitor fetch-news-catalyst-sources --provider eodhd --coverage-plan
python -m target_opportunity_monitor fetch-news-catalyst-sources --provider x_recent_search --coverage-plan
python -m target_opportunity_monitor fetch-news-catalyst-sources --provider truth_social_public --coverage-plan
python -m target_opportunity_monitor import-news-catalyst-source-exports
python -m target_opportunity_monitor compute-news-catalyst-text-backfill
python -m target_opportunity_monitor aggregate-news-catalyst-sources
python -m target_opportunity_monitor news-catalyst-source-status
```

Status, Markdown reports, CSV reports, and the dashboard now distinguish
provider-numeric coverage, text-derived numeric coverage, total numeric
coverage, missing numeric tickers, provider-native upgrade candidates,
headline-only evidence, split queue staleness, and provider limitations.

## Phase 10E.5 Provider-Native News/Catalyst Quality

Phase 10E.5 separates operational coverage from provider-native quality.
Total numeric coverage can be complete while some tickers still rely only on
deterministic text-derived rows.

New behavior:

- `news-catalyst-coverage-plan --mode missing` tracks tickers with no numeric
  news/catalyst row.
- `news-catalyst-coverage-plan --mode provider-upgrade` tracks tickers with
  text-derived numeric rows but no provider-native numeric rows.
- `news-catalyst-source-status --provider-upgrade-only` prints only the
  text-derived-only upgrade candidates.
- `news-catalyst-provider-upgrade-status` summarizes whether provider-native
  upgrading is `not_configured`, `queued`, `partially_upgraded`, or
  `provider_native_complete`.
- `fetch-news-catalyst-sources --coverage-plan` defaults to `--coverage-mode all`,
  so once missing numeric coverage is complete it automatically works the
  provider-native upgrade queue.
- `fetch-news-catalyst-sources --provider-upgrade` is a friendly alias for
  `--coverage-plan --coverage-mode provider-upgrade`.
- Aggregation preserves text-derived snapshots for audit, but provider-native
  numeric snapshots take precedence for the same ticker/date.

News/catalyst remains shadow-only. Provider-native upgrades do not change final
opportunity scores, alerts, portfolio guidance, notifications, broker writes,
or execution.

## Phase 10E.6 Provider-Native Upgrade Activation

Phase 10E.6 makes the provider-native upgrade lane operational without requiring
new API keys.

Commands:

```powershell
python -m target_opportunity_monitor news-catalyst-provider-upgrade-status
python -m target_opportunity_monitor fetch-news-catalyst-sources --provider-upgrade
python -m target_opportunity_monitor news-catalyst-coverage-plan --mode provider-upgrade --refresh-template
```

Manual/provider export labels that count as provider-native when they include
source-backed numeric fields:

- `marketaux_export`
- `eodhd_export`
- `x_export`
- `licensed_news_provider_export`
- `user_provider_export`

Provider-upgrade export rows must include `source_url`, `headline_or_event`,
and at least one numeric provider field. Invalid provider-upgrade rows are
skipped with warnings instead of being stored as misleading source snapshots.

## Phase 10E.7 Provider-Native Upgrade Operations

Phase 10E.7 keeps missing numeric coverage and provider-native upgrade coverage
as separate queues. When total numeric coverage is complete, the missing queue is
kept header-only and the provider-upgrade queue remains the active work queue.

Smoke-test provider-native upgrade keys before relying on a provider:

```powershell
python -m target_opportunity_monitor test-news-catalyst-provider --provider all --ticker AAPL
python -m target_opportunity_monitor test-news-catalyst-provider --provider marketaux --ticker AAPL
python -m target_opportunity_monitor test-news-catalyst-provider --provider eodhd --ticker AAPL
python -m target_opportunity_monitor test-news-catalyst-provider --provider x_recent_search --ticker AAPL
```

The smoke test reports `provider_numeric_available`, `headline_only`,
`rate_limited`, `plan_limited`, `auth_failed`, `missing_key`, or `http_failed`.
It never prints key values. Configure keys as environment variables only:

- `MARKETAUX_API_KEY`
- `EODHD_API_KEY`
- `X_BEARER_TOKEN`

`fetch-news-catalyst-sources --provider-upgrade` now prints queue mode, planned
tickers, attempted providers, numeric rows stored, and provider blockers.

## Phase 10E.8 Provider-Native Backfill Operations

Phase 10E.8 adds a local package for filling provider-native news/catalyst rows
when API keys are missing or providers are rate/plan limited:

```powershell
python -m target_opportunity_monitor export-news-catalyst-provider-backfill
```

The command writes:

```text
data/signals/source_exports/news_catalysts/provider_native_backfill/news_catalyst_provider_native_backfill.csv
data/signals/source_exports/news_catalysts/provider_native_backfill/README.md
```

The CSV contains only active equities that have text-derived numeric coverage but
no provider-native numeric coverage. Do not add SPY/QQQ rows. Completed rows must
include `source_url`, `headline_or_event`, and at least one provider-native
numeric field from an accepted source label:

- `marketaux_export`
- `eodhd_export`
- `x_export`
- `licensed_news_provider_export`
- `user_provider_export`

Invalid provider-native rows are skipped with warnings and are not stored as
source snapshots. `status`, reports, CSV output, and dashboard show provider
native coverage, rejected provider-native rows, and latest accepted provider
native source date separately from total numeric coverage.

## Phase 10E.9 Provider-Native Backfill Validation

Phase 10E.9 adds a non-mutating check before importing provider-native backfill
rows:

```powershell
python -m target_opportunity_monitor validate-news-catalyst-provider-backfill
python -m target_opportunity_monitor preview-news-catalyst-provider-upgrade
```

Validation classifies filled valid rows, blank placeholders, invalid rows,
unsupported tickers, ETF-gated rows, malformed dates/numbers, and missing
provider-native fields without writing snapshots or changing aggregates.

The preview shows current provider-native coverage, text-derived-only tickers,
valid rows ready to import, projected provider-native coverage after import, and
still-blocked tickers. When the preview is clean, run:

```powershell
python -m target_opportunity_monitor import-news-catalyst-source-exports
python -m target_opportunity_monitor aggregate-news-catalyst-sources
python -m target_opportunity_monitor load-news-catalysts
python -m target_opportunity_monitor compute-news-catalyst-signals
python -m target_opportunity_monitor validate-news-catalyst-signals
```

This remains a shadow-only quality workflow. It does not auto-import,
auto-promote, change scores, change alerts, change portfolio guidance, or trade.

## Phase 10E.10 Provider-Native Export Normalization And Guarded Apply

Phase 10E.10 makes the backfill package easier to use when a source gives you a
CSV export in its own shape. Normalize source-backed provider exports first:

```powershell
python -m target_opportunity_monitor normalize-news-catalyst-provider-export --provider marketaux --file PATH
python -m target_opportunity_monitor normalize-news-catalyst-provider-export --provider eodhd --file PATH
python -m target_opportunity_monitor normalize-news-catalyst-provider-export --provider x --file PATH
python -m target_opportunity_monitor normalize-news-catalyst-provider-export --provider licensed --file PATH
python -m target_opportunity_monitor normalize-news-catalyst-provider-export --provider generic --file PATH
```

Normalized rows are written under:

```text
data/signals/source_exports/news_catalysts/provider_native_backfill/normalized_{provider}_provider_native.csv
```

The normalizer accepts only active equities still in the provider-native upgrade
queue. It skips already provider-native tickers, inactive tickers, and SPY/QQQ.
Provider polarity values in `[-1, 1]` are converted to `0-100`; already
normalized `0-100` fields pass through. Headline-only rows are rejected unless
they contain at least one source-backed numeric provider field.

Use the combined readiness command before applying:

```powershell
python -m target_opportunity_monitor news-catalyst-provider-backfill-status
python -m target_opportunity_monitor apply-news-catalyst-provider-backfill
```

`apply-news-catalyst-provider-backfill` is dry-run only unless `--confirm` is
passed. Confirmed apply runs import, aggregate, load, compute, and validation
only when validation is clean and provider-native coverage improves:

```powershell
python -m target_opportunity_monitor apply-news-catalyst-provider-backfill --confirm --allow-partial
```

`--allow-partial` is required when fewer than all remaining text-derived-only
tickers are upgraded. This workflow remains shadow-only and never changes final
scores, alerts, portfolio guidance, notifications, broker writes, or execution.

## Phase 10F SEC Insider Activity Shadow Signals

Phase 10F adds official SEC Form 4 insider activity as a third advanced signal
family. It uses `configs/cik_map.csv`, the configured SEC user agent, SEC
submissions JSON, and each filing's ownership XML/document. Raw SEC payloads are
cached locally under:

```text
data/signals/cache/insider_transactions/
```

Normalized Form 4 rows are stored in `insider_transaction_source_snapshots`.
Shadow signals are stored in the shared `signals` table:

```text
insider_activity.open_market_buying
insider_activity.sale_pressure
insider_activity.routine_activity
insider_activity.composite
```

Open-market purchase code `P` is treated as supportive, open-market sale code
`S` is treated as weak-to-moderate negative, and routine or
compensation/exercise-style activity is neutral with warnings. ETF rows remain
gated with `etf_insider_activity_gated`.

Commands:

```powershell
python -m target_opportunity_monitor fetch-insider-transactions --ticker AAPL
python -m target_opportunity_monitor fetch-insider-transactions --ticker AAPL --refresh-cache
python -m target_opportunity_monitor fetch-insider-transactions --max-tickers 13 --use-cache
python -m target_opportunity_monitor fetch-insider-transactions --ticker MSFT --force-refresh
python -m target_opportunity_monitor compute-insider-signals --ticker AAPL
python -m target_opportunity_monitor validate-insider-signals --ticker AAPL
python -m target_opportunity_monitor insider-source-status
python -m target_opportunity_monitor insider-source-status --verbose
python -m target_opportunity_monitor insider-status
python -m target_opportunity_monitor insider-validation-report
```

`insider-source-status` reports active equity coverage, ETF-gated tickers,
source row count, latest filing/transaction/fetch dates, confirmed
no-recent-activity tickers, SEC-rate-limited tickers, parse-warning tickers,
stale source tickers, and missing source tickers. The default output compacts
repeated accession-level SEC failures; use `--verbose` to inspect raw filing
warnings.

Daily refresh uses a cache-first, paced SEC workflow by default:

```toml
insider_activity_max_tickers_per_run = 13
insider_activity_use_cache = true
insider_activity_sec_request_delay_seconds = 0.2
insider_activity_sec_rate_limit_cooldown_seconds = 60
insider_activity_stop_on_rate_limit = true
insider_activity_max_live_form4_fetches_per_ticker = 10
insider_activity_skip_successful_fetch_same_day = true
```

Insider activity remains shadow-only. It does not change final opportunity
scores, alerts, portfolio guidance, notifications, execution, or orders.

Detailed SEC source rules are in
`DOCS/insider-activity-source-workflow.md`.

## Phase 10G Short Interest Shadow Signals

Phase 10G adds source-backed short-interest inputs as another shadow-only
advanced signal family. The default editable CSV is:

```text
data/signals/manual/short_interest.csv
```

Required columns:

```text
ticker, settlement_date, source, source_url
```

Optional columns:

```text
publication_date, short_interest, float_shares, percent_float,
average_daily_volume, days_to_cover, notes, as_of_date, effective_date
```

`percent_float` can be entered as a decimal (`0.052`), percentage points (`5.2`),
or percent literal (`5.2%`). If `percent_float` is blank, TOM derives it from
`short_interest / float_shares` when both values are present. If
`days_to_cover` is blank, TOM derives it from
`short_interest / average_daily_volume` when possible.

Shadow signals are stored in the shared `signals` table:

```text
short_interest.level
short_interest.days_to_cover
short_interest.change
short_interest.squeeze_setup
short_interest.composite
```

Commands:

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
python -m target_opportunity_monitor compute-short-interest-signals --ticker AAPL
python -m target_opportunity_monitor validate-short-interest-signals
python -m target_opportunity_monitor validate-short-interest-signals --ticker AAPL
python -m target_opportunity_monitor short-interest-status
python -m target_opportunity_monitor short-interest-validation-report
```

Phase 10G.1 source-export files live under:

```text
data/signals/source_exports/short_interest/
```

`export-short-interest-backfill` creates `provider_export.csv`,
`exchange_manual.csv`, `broker_manual.csv`, and a missing-ticker backfill
template. `import-short-interest-source-exports` accepts only active equity
rows with source-backed numeric evidence. Blank placeholders are safe; invalid
filled rows are rejected instead of guessed.

Phase 10G.2 adds a cache-first official/provider fetch and normalization lane.
`fetch-short-interest-sources` attempts configured official sources such as FINRA
and Nasdaq Trader, writes normalized rows into
`data/signals/source_exports/short_interest/provider_export.csv`, and then reuses
the same strict import path. If a free direct endpoint is unavailable for a
ticker, normalize a broker, exchange, or licensed provider export instead:

```powershell
python -m target_opportunity_monitor normalize-short-interest-provider-export --provider broker --file PATH
python -m target_opportunity_monitor import-short-interest-source-exports
python -m target_opportunity_monitor load-short-interest
python -m target_opportunity_monitor compute-short-interest-signals
python -m target_opportunity_monitor validate-short-interest-signals
```

Provider cache files live under:

```text
data/signals/cache/short_interest/
```

`short-interest-provider-status` shows source coverage, provider-export valid
rows, provider-export tickers, cache freshness, fetchable providers, manual/export
fallback providers, and provider warnings.

Phase 10G.3 adds a focused closure workflow for remaining uncovered equities.
`short-interest-missing-coverage-plan` reports missing tickers, provider/export
diagnostics, valid rows for currently missing tickers, and the exact apply
blocker. `export-short-interest-missing-provider-template` writes a focused
template for missing tickers only. `apply-short-interest-provider-backfill` is a
dry run by default; `--confirm` imports only when at least one currently missing
ticker has a valid source-backed row and there are no invalid rows. Existing
covered rows do not count as progress.

Phase 10G.4 adds `resolve-short-interest-missing-sources`, a missing-only
resolver that rechecks official fetch/cache paths for uncovered equities,
refreshes the focused missing-provider template, and prints the projected
coverage improvement before any apply. If official endpoints return empty or
unavailable results, TOM keeps coverage unchanged and points back to
provider/export rows instead of inventing values.

Higher short-interest composite scores mean the short-interest backdrop is more
constructive. High percent-float short and high days-to-cover reduce the level
and cover-risk components. Falling short interest improves the change component.
High short interest plus positive recent momentum can mark a
`squeeze_candidate_shadow_only` setup, but it remains low-weight and shadow-only.

SPY and QQQ are gated with `etf_short_interest_gated`; this MVP accepts active
equities only. Short-interest signals never change final scores, alerts,
portfolio guidance, notifications, broker writes, or execution.

Detailed source rules are in `DOCS/short-interest-source-workflow.md`.

## Phase 10H Trader Commentary Input

Phase 10H adds a source-backed commentary input lane for notes such as Chinese
or English trader updates, VIP-group captures, public posts, or personal
research notes. The lane is shadow-only: it stores raw text, parses structured
claims, validates them over time, and never changes final scores, alerts, ranges,
portfolio guidance, broker state, or execution.

Default editable CSV:

```text
data/signals/manual/trader_commentary.csv
```

Required columns:

```text
capture_date, source, source_author, platform, permission_scope
```

Each row must also include at least one of:

```text
raw_text, text_file, source_url, capture_id
```

Private or VIP content should use a user-provided `capture_id` when a public URL
does not exist. If `text_file` is supplied, TOM loads UTF-8 text relative to the
CSV file or `data/signals/source_exports/trader_commentary/`.

Commands:

```powershell
python -m target_opportunity_monitor load-trader-commentary
python -m target_opportunity_monitor load-trader-commentary --file PATH
python -m target_opportunity_monitor export-trader-commentary-template
python -m target_opportunity_monitor parse-trader-commentary-claims
python -m target_opportunity_monitor parse-trader-commentary-claims --commentary-id ID
python -m target_opportunity_monitor parse-trader-commentary-claims --ticker TSLA
python -m target_opportunity_monitor trader-commentary-parse-review
python -m target_opportunity_monitor validate-trader-commentary-claims
python -m target_opportunity_monitor validate-trader-commentary-claims --ticker TSLA
python -m target_opportunity_monitor trader-commentary-status
python -m target_opportunity_monitor trader-commentary-validation-report
```

Phase 10H.1 seeds the user-provided Chinese commentary examples as local
authorized captures under:

```text
data/signals/source_exports/trader_commentary/
```

The compatibility CSV references those text files with `source = "user_paste"`,
`source_author = "unknown_trader"`, `platform = "wechat_or_chat_capture"`,
`permission_scope = "user_provided_private_capture"`, and local `capture_id`
values instead of public URLs.

`export-trader-commentary-template` creates a ready-to-fill CSV plus a UTF-8
text-file template. `trader-commentary-parse-review` summarizes parsed claims,
unmapped market/index references, unsupported tickers, option proxy claims, and
parser warnings. Unsupported symbols such as `SOXL`, `TSLA`, `HOOD`, `KORU`,
`XLV`, `XLF`, and `BRK.B` stay visible as unpriced commentary claims until they
are onboarded as reference instruments or promoted to scoreable assets.

Parsed claim examples include:

```text
technical_support_hold
technical_resistance_watch
market_resistance_breakout
ticker_price_target
downside_level_watch
position_action
risk_reduction_instruction
sector_rotation_view
catalyst_watch
options_income_idea
```

For mixed-language commentary, TOM extracts explicit tickers such as `TSLA`,
`SOXL`, `HOOD`, `KORU`, `XLV`, `XLF`, and `BRK.B`. Unmapped labels such as
`大盘` are kept as `instrument_label` with `unmapped_instrument`; TOM does not
force-map them to SPY or QQQ. Sell-put comments are stored as
`options_income_idea` and validated only with an underlying-price proxy, not full
options P&L.

Validation uses stored daily prices and tracks 1d/5d/20d/60d returns, support
holds, resistance breakouts, target hits, downside/risk breaches, and pending
horizons. Commentary signals are also written to the shared `signals` table as:

```text
trader_commentary.levels
trader_commentary.direction
trader_commentary.action
trader_commentary.composite
```

Phase 10H.2 adds an opt-in X browser-capture fallback for public X pages, lists,
or search URLs when no paid X API is available. It is disabled by default and
requires an explicit operator acknowledgement.

```powershell
python -m target_opportunity_monitor browser-capture-commentary-status
python -m target_opportunity_monitor browser-capture-commentary --provider x_browser --target-url URL --acknowledge-terms-risk --dom-text-file PATH
python -m target_opportunity_monitor ingest-browser-captured-commentary
python -m target_opportunity_monitor parse-trader-commentary-claims
python -m target_opportunity_monitor trader-commentary-parse-review
python -m target_opportunity_monitor validate-trader-commentary-claims
```

Capture artifacts are stored under:

```text
data/signals/browser_captures/trader_commentary/YYYY-MM-DD/run-id/
```

Each run writes `dom_text.txt`, optional `page.html`, `items.json`, and
`run_metadata.json`. Accepted visible X items are deduped by post URL/status ID
when available, otherwise by stable text hash, and ingested into
`trader_commentary_raw` with `source = "x_browser_capture"` and `platform = "x"`.

Boundaries:

- browser capture is opt-in and low-frequency, not real-time scraping,
- do not bypass login, captchas, rate limits, technical restrictions, or
  paywalls,
- if X blocks, rate-limits, or shows a login/captcha wall, TOM records a
  partial/failed run and stops,
- Discord is intentionally separate and uses the Phase 10H.5 official
  bot/API capture workflow, not browser automation,
- no WeChat browser-capture plan is included now,
- all captured commentary remains shadow-only.

Phase 10H.5 adds disabled-by-default Discord commentary capture through an
authorized bot/API route. It reads `DISCORD_BOT_TOKEN` from the environment
only, never from project files, and requires explicit operator acknowledgement
before live capture.

```powershell
python -m target_opportunity_monitor discord-capture-commentary-status
python -m target_opportunity_monitor discord-capture-commentary --provider discord_gateway --channel-id CHANNEL_ID --acknowledge-permission
python -m target_opportunity_monitor ingest-discord-captured-commentary
python -m target_opportunity_monitor parse-trader-commentary-claims
python -m target_opportunity_monitor trader-commentary-parse-review
python -m target_opportunity_monitor validate-trader-commentary-claims
```

For tests or audited manual exports, `discord-capture-commentary` can read an
official-API-shaped JSON file with `--messages-json-file PATH`. Accepted
messages are deduped by Discord message ID and ingested into
`trader_commentary_raw` with `source = "discord_bot_capture"` and
`platform = "discord"`.

Discord capture boundaries:

- capture only channels the bot is authorized to read,
- do not bypass permissions, private channels, rate limits, captchas, or
  technical restrictions,
- attachments are metadata-only in this MVP,
- daily refresh ingests already captured Discord items but does not fetch
  Discord by itself,
- all Discord commentary remains shadow-only.

Manual commentary capture still accepts only user-provided or authorized source
text. Keep source metadata and do not treat commentary validation as live trading
advice. Detailed capture and validation rules are in
`DOCS/trader-commentary-source-workflow.md`.

Phase 10H.3 adds a commentary onboarding lane. It surfaces unsupported tickers
and unmapped instrument labels from parsed claims, then exports a fillable
template. The default recommendation is `asset_role = commentary_validation`,
which allows price ingestion and commentary validation but keeps scoring,
alerts, ranges, portfolio guidance, and universe readiness limited to
`asset_role = scoreable` assets.

```powershell
python -m target_opportunity_monitor commentary-onboarding-plan
python -m target_opportunity_monitor commentary-onboarding-status
python -m target_opportunity_monitor export-commentary-onboarding-template
python -m target_opportunity_monitor apply-commentary-onboarding --file PATH
python -m target_opportunity_monitor apply-commentary-onboarding --file PATH --confirm
python -m target_opportunity_monitor load-commentary-instrument-aliases
```

Alias rows live at:

```text
data/signals/manual/trader_commentary_instrument_aliases.csv
```

Use aliases only when you intentionally want a label mapped, such as mapping a
specific source's `market index` label to a canonical ticker. TOM does not
default-map broad labels such as `大盘` to SPY or QQQ.

Phase 10H.4 activates the initial commentary references surfaced by seeded
commentary:

```text
BRK.B, HOOD, KORU, SOXL, TSLA, XLF, XLV
```

They remain `commentary_validation` references, not scoreable trading assets.
TOM can fetch prices and validate commentary claims for them, but
`verify-universe`, scoring, alerts, range notifications, and portfolio guidance
still use the 15 scoreable assets only.

## Phase 11A Near-Real-Time Ranges And Notifications

Phase 11A adds a near-real-time monitoring layer on top of the completed daily
stack. It refreshes quotes when possible, falls back to latest daily prices when
IBKR is unavailable, computes buy/hold/trim/sell range states, and records
deduped local notification events when meaningful range states are crossed.

```powershell
python -m target_opportunity_monitor update-quotes --source ibkr
python -m target_opportunity_monitor range-monitor --source ibkr
python -m target_opportunity_monitor range-monitor --ticker AAPL
python -m target_opportunity_monitor range-status
python -m target_opportunity_monitor notification-status
python -m target_opportunity_monitor deliver-notifications --channel console
```

Equity ranges expose:

```text
strong_buy_below
starter_buy_below
add_below
hold_low
hold_high
trim_above
reduce_or_sell_above
risk_review_below
```

ETF ranges expose:

```text
nav_action_discount_below
nav_watch_discount_below
nav_fair_value
nav_premium_warning_above
etf_risk_review_level
```

Asset management is soft by default, so historical prices, scores, alerts,
signals, and outcomes remain auditable:

```powershell
python -m target_opportunity_monitor add-asset --ticker TSLA --asset-type equity --exchange NASDAQ --currency USD --country US
python -m target_opportunity_monitor deactivate-asset --ticker TSLA --reason "example"
python -m target_opportunity_monitor reactivate-asset --ticker TSLA
python -m target_opportunity_monitor remove-asset --ticker TSLA --soft
python -m target_opportunity_monitor asset-status --ticker AAPL
```

`probe-market --source ibkr` now runs the range monitor after quote/gap updates.
`refresh-data --daily` also includes range and notification status in the final
reports and dashboard. Notifications are local event records plus console,
dashboard, and scheduler-friendly output in this phase; no email, SMS, chat,
broker write, or execution action is sent.

## Phase 11B Technical And Market Regime Signals

Phase 11B adds structured support/resistance, trend, price-location, and market
regime signals from stored local price data. These signals make Phase 11A
buy/hold/trim/sell ranges more explainable, but they do not overwrite valuation
targets, final scores, alerts, portfolio guidance, broker state, or execution.

```powershell
python -m target_opportunity_monitor compute-technical-signals
python -m target_opportunity_monitor compute-technical-signals --ticker AAPL
python -m target_opportunity_monitor compute-regime-signals
python -m target_opportunity_monitor technical-status
python -m target_opportunity_monitor regime-status
python -m target_opportunity_monitor range-monitor --source ibkr
python -m target_opportunity_monitor range-status
```

Technical snapshots include:

```text
support_low/support_high
resistance_low/resistance_high
breakout_level
downside_watch_level
trend_repair_level
moving_average_state
drawdown_state
price_location_state
technical_confidence
```

Regime snapshots include benchmark and sector-proxy state:

```text
trend_state
risk_state
return_lookback
relative_strength
sector_rotation_rank
defensive_rotation_flag
regime_confidence
```

`refresh-data --daily` now computes technical and regime signals before
`range-monitor`. If configured sector ETFs such as `XLK`, `XLY`, `XLV`, `XLF`,
`XLI`, `XLP`, `XLU`, `XLE`, or `XLC` are not priced yet, TOM records
`missing_sector_proxy_price_history` as a warning and continues. SPY/QQQ regime
signals work from the existing ETF price history.

Daily Markdown/CSV reports and `dashboard/index.html` show the latest support,
resistance, moving-average state, price-location state, regime state, relative
strength, and range warnings. These remain structured shadow/range-modifier
signals; long-form thesis generation and option-strategy logic are still out of
scope.

## Phase 11C Intraday Operations And Notification Delivery

Phase 11C adds a scheduler-friendly intraday cycle and stronger local delivery
surfaces. The command runs quote refresh/probe, intraday gaps, range monitoring,
notification event creation, and optional delivery through existing
`pipeline_runs` and `pipeline_step_results`.

```powershell
python -m target_opportunity_monitor intraday-cycle --source ibkr
python -m target_opportunity_monitor intraday-cycle --source ibkr --ticker AAPL
python -m target_opportunity_monitor intraday-cycle --source ibkr --deliver --channel file
python -m target_opportunity_monitor intraday-cycle --source auto --deliver --channel file
python -m target_opportunity_monitor intraday-status
python -m target_opportunity_monitor intraday-health-check
python -m target_opportunity_monitor intraday-repair-plan
python -m target_opportunity_monitor notification-status --pending-only
python -m target_opportunity_monitor deliver-notifications --channel file
python -m target_opportunity_monitor drain-pending-notifications --channel file
python -m target_opportunity_monitor notification-outbox-status
python -m target_opportunity_monitor test-notification-channel --channel console
python -m target_opportunity_monitor test-notification-channel --channel file
```

The file channel writes JSONL plus readable Markdown to:

```text
data/notifications/outbox/
```

Webhook delivery is optional and disabled unless `TOM_NOTIFICATION_WEBHOOK_URL`
is present in the environment. TOM never prints or persists the webhook URL.

Codex scheduler/heartbeat pattern:

```powershell
python -m target_opportunity_monitor intraday-cycle --source auto --deliver --channel file
```

Phase 11C is still read-only. It does not place orders, write to brokers,
generate long-form thesis text, run an options strategy engine, or let shadow
signals change final scores/alerts.

## Phase 11D Codex Scheduler Intraday Automation

Phase 11D operationalizes Phase 11C with Codex automations, not Windows Task
Scheduler. The intended jobs are:

```text
TOM Intraday Probe/Heartbeat: weekdays during market hours, every 10 minutes
TOM Morning Check: weekdays 8:30 AM America/Toronto
TOM Daily Refresh: weekdays 6:30 PM America/Toronto
TOM Daily Retry: weekdays 8:30 PM America/Toronto
```

The intraday heartbeat command is:

```powershell
python -m target_opportunity_monitor intraday-cycle --source auto --deliver --channel file
```

Use this to inspect scheduler health from the TOM side:

```powershell
python -m target_opportunity_monitor scheduler-status
```

`scheduler-status` reports the intended jobs, latest intraday cycle, latest
daily refresh, quote/range freshness, pending notifications, failed deliveries,
and latest report/dashboard paths. IBKR connectivity problems remain warnings
when daily fallback data is available. File delivery remains the default durable
notification channel.

## Phase 11D.1 Intraday Health And Notification Drain

Phase 11D.1 makes the intraday loop self-diagnosing. `intraday-health-check`
classifies the live loop as `healthy`, `stale`, or `blocked` from existing
pipeline, quote, range, notification, and delivery rows. `intraday-repair-plan`
prints the exact local command sequence to drain notifications, run an
auto-source heartbeat, and recheck health.

```powershell
python -m target_opportunity_monitor intraday-health-check
python -m target_opportunity_monitor intraday-repair-plan
python -m target_opportunity_monitor notification-outbox-status
python -m target_opportunity_monitor drain-pending-notifications --channel file
python -m target_opportunity_monitor intraday-cycle --source auto --deliver --channel file
python -m target_opportunity_monitor scheduler-status
```

`intraday-cycle --source auto` tries IBKR quotes first. If IBKR is unavailable
or returns no quote rows, TOM refreshes read-only daily market data and writes
explicit `daily_price_fallback` quote snapshots so range monitoring and local
notifications can keep running with clear stale/fallback warnings. File
delivery marks successful pending events as `delivered`; failed channels write
delivery audit rows and mark events `delivery_failed`.

## Phase 11D.2 Scheduler Reconciliation And Delivery Reliability

Phase 11D.2 reconciles TOM's intended Codex automations against saved Codex
automation metadata and confirms the live intraday heartbeat uses the resilient
auto-source command:

```powershell
python -m target_opportunity_monitor intraday-cycle --source auto --deliver --channel file
```

Use these commands to audit and repair scheduler state:

```powershell
python -m target_opportunity_monitor scheduler-audit
python -m target_opportunity_monitor scheduler-repair-plan
python -m target_opportunity_monitor scheduler-automation-status
python -m target_opportunity_monitor intraday-cycle --source auto --drain-first --deliver --channel file
python -m target_opportunity_monitor notification-delivery-report
```

`scheduler-audit` reads Codex automation TOML metadata when available and
reports `configured`, `missing`, `stale_command`, `disabled`,
`last_run_stale`, or `unknown_external_state`. The default heartbeat was
updated from the old IBKR-only command to the auto fallback command. File
delivery remains the durable default outbox, and webhook delivery remains
environment-variable gated.

## Phase 11D.3 Manual TOM Ops Runner

Phase 11D.3 lets TOM run the non-browser operational automation set manually
from one local command instead of relying on Codex automations. The preferred
persistent operator path is now the Phase 11E `tom-loop-start` wrapper; the
older `manual-ops-loop` remains available for compatibility.

```powershell
python -m target_opportunity_monitor tom-loop-start --mode auto --deliver --channel file
python -m target_opportunity_monitor tom-loop-once --mode auto --deliver --channel file
python -m target_opportunity_monitor tom-loop-status
python -m target_opportunity_monitor tom-loop-health
python -m target_opportunity_monitor tom-loop-stop
python -m target_opportunity_monitor manual-ops-cycle --mode auto --deliver --channel file
python -m target_opportunity_monitor manual-ops-cycle --dry-run
python -m target_opportunity_monitor manual-ops-status
```

Supported modes:

```text
auto
morning
intraday
daily-refresh
daily-retry
all
```

`tom-loop-start` runs until Ctrl+C or `tom-loop-stop`. By default it uses
`realtime.manual_ops_loop_interval_seconds = 600`, matching the old 10-minute
heartbeat cadence. Use `--max-cycles N` for a bounded trial.

Phase 11E stores loop state under `data/ops/loop/` with a state file,
lockfile, heartbeat file, and cooperative stop request. `tom-loop-once` runs
the same safe worker once without starting a persistent process.

`--mode auto` uses America/Toronto time to choose the safe operation:

- morning check before the market window;
- intraday quote/range/notification cycle during market hours;
- daily refresh after the close;
- conditional retry later in the evening or outside the normal window.

For the never-ending loop, after-hours `auto` uses the guarded retry path so it
does not run a full daily refresh every 10 minutes once the daily data is
already current.

Real runs are stored as `manual_ops_cycle` rows in the existing
`pipeline_runs` and `pipeline_step_results` tables. Dry runs do not write audit
rows.

After the manual command is verified, pause only the TOM automation IDs:

```text
tom-intraday-probe
tom-morning-check
tom-daily-refresh
tom-daily-retry
```

Do not pause browser/content-capture automations such as
`daily-aleabitoreddit-q-a-ingestion` or `trump-truth-social-posts-morning`.

## Phase 12A Options/Sell-Put Advisory

Phase 12A adds read-only option-income review rows for source-backed option
chain data. The manual CSV remains the fallback input:

```powershell
python -m target_opportunity_monitor load-options-chain
python -m target_opportunity_monitor load-options-chain --file data/options/manual/options_chain.csv
python -m target_opportunity_monitor fetch-options-chain --source csv
python -m target_opportunity_monitor compute-options-income
python -m target_opportunity_monitor compute-options-income --ticker SOXL
python -m target_opportunity_monitor options-status
```

The editable default file is:

```text
data/options/manual/options_chain.csv
```

Required columns:

```text
ticker,snapshot_timestamp,expiration_date,option_type,strike,bid,ask
```

Optional columns:

```text
last,mark,volume,open_interest,implied_volatility,delta,gamma,theta,vega,source,source_url,as_of_date,effective_date
```

The sell-put review computes mid premium, breakeven, premium yield, annualized
yield, downside buffer, breakeven buffer, assignment notional, liquidity status,
range-context warnings, and commentary option-idea linkage when parsed
commentary claims include a matching ticker/strike. Reference instruments such
as commentary-only `SOXL` or `KORU` can be reviewed when option-chain and price
data exist, but they remain outside scoreable alerts, ranges, portfolio
guidance, and trading decisions unless explicitly promoted later.

Phase 12A remains advisory-only:

```text
No order placement.
No broker writes.
No automatic exercise or assignment handling.
No margin model.
No score, alert, portfolio, notification, or execution impact.
```

## Phase 12B IBKR Option Chain Ingestion

Phase 12B adds a bounded, read-only IBKR option-chain fetch path. It discovers
expirations/strikes, keeps puts only by default, filters by DTE and strike
window, and writes source-backed bid/ask rows to the existing
`option_chain_snapshots` table with `source = "ibkr_option_chain"`.

```powershell
python -m target_opportunity_monitor fetch-options-chain --source ibkr --ticker SOXL
python -m target_opportunity_monitor fetch-options-chain --source ibkr --ticker KORU --force-refresh
python -m target_opportunity_monitor fetch-options-chain --source ibkr --max-tickers 3
python -m target_opportunity_monitor fetch-options-chain --source yfinance --max-tickers 5 --force-refresh
python -m target_opportunity_monitor fetch-options-chain --source auto --max-tickers 5 --force-refresh
python -m target_opportunity_monitor option-chain-status
python -m target_opportunity_monitor compute-options-income
python -m target_opportunity_monitor options-status
```

Daily refresh runs bounded option-chain fetches before sell-put review
computation when `options.auto_fetch_daily = true`. Intraday option fetching is
off by default; use the explicit flag only when needed:

```powershell
python -m target_opportunity_monitor intraday-cycle --source ibkr --include-options
```

Useful Phase 12B defaults:

```toml
[options]
chain_source = "auto"
option_fetch_universe = "scoreable_plus_commentary_options"
max_expirations_per_ticker = 4
max_strikes_per_expiration = 12
strike_window_pct = 0.30
fetch_puts_only = true
auto_fetch_daily = true
auto_fetch_intraday = false
max_tickers_per_run = 3
```

IBKR and yfinance/Yahoo option-chain fetches remain read-only. `auto` tries
IBKR first and then yfinance for tickers that still have no usable chain rows.
Missing Gateway access, missing option-data subscriptions, missing bid/ask
quotes, stale underlying prices, provider failures, and exhausted fetch budgets
are warnings, not trading actions. The manual CSV remains
available when IBKR option data is unavailable.

### Phase 12B.1 Option Provider Health And Backfill

Phase 12B.1 adds explicit option-provider diagnostics and a stricter
source-export backfill path for cases where IBKR is unavailable or option-data
permissions are incomplete.

```powershell
python -m target_opportunity_monitor option-provider-status
python -m target_opportunity_monitor option-provider-status --check-connectivity
python -m target_opportunity_monitor diagnose-options-provider --source ibkr
python -m target_opportunity_monitor test-options-provider --source ibkr --ticker SOXL
python -m target_opportunity_monitor export-options-chain-backfill-template --ticker SOXL
python -m target_opportunity_monitor validate-options-chain-backfill
python -m target_opportunity_monitor import-options-chain-source-exports
```

Backfill exports live under `data/options/source_exports/`. Source-export rows
must include `source` and `source_url` plus the normal option-chain fields
(`ticker`, `snapshot_timestamp`, `expiration_date`, `option_type`, `strike`,
`bid`, and `ask`). Blank template rows are treated as placeholders; invalid
filled rows are reported and are not imported.

### Phase 12B.2 Option Chain Activation

Phase 12B.2 adds a guided activation layer so TOM can become
options-evidence-producing before deeper risk/margin work starts. The minimum
activation set is `SOXL`, `KORU`, and `AAPL`. IBKR repair guidance is
diagnostic only; TOM does not change Windows permissions or broker settings.

```powershell
python -m target_opportunity_monitor option-chain-activation-status
python -m target_opportunity_monitor option-provider-repair-plan --source ibkr
python -m target_opportunity_monitor option-chain-minimum-backfill-plan
python -m target_opportunity_monitor export-options-chain-backfill-template --minimum-set
python -m target_opportunity_monitor validate-options-chain-backfill
python -m target_opportunity_monitor activate-options-chain-data
python -m target_opportunity_monitor activate-options-chain-data --confirm --allow-partial
```

`activate-options-chain-data` is dry-run by default. Confirmed activation
imports only valid source-backed option-chain rows, recomputes sell-put reviews,
and fails if no option-income review is produced. `--allow-partial` permits a
minimum activation when at least one of the minimum tickers has valid bid/ask
rows.

### Phase 12B.3 Option Chain Data Activation

Phase 12B.3 closes the first activation gap. TOM verifies that the local
`ibapi` package imports cleanly, attempts read-only IBKR option-chain access,
and falls back to source-backed provider/export rows when IBKR is closed,
subscription-gated, or unavailable.

The current minimum activation set is active:

- `SOXL`
- `KORU`
- `AAPL`

Those rows are stored as source-backed option-chain snapshots and produce
read-only sell-put reviews. IBKR remains read-only; TOM still does not place
orders, write to a broker, or change scores, alerts, ranges, or portfolio
guidance.

Useful checks:

```powershell
python -m target_opportunity_monitor option-chain-activation-status
python -m target_opportunity_monitor options-status
python -m target_opportunity_monitor option-provider-status
```

### Phase 12C Options Risk And Margin Depth

Phase 12C adds read-only cash-secured risk reviews on top of existing
option-income reviews. It does not place orders, write to IBKR, automate
exercise/assignment, or change scores, alerts, ranges, or portfolio guidance.

```powershell
python -m target_opportunity_monitor compute-options-risk
python -m target_opportunity_monitor compute-options-risk --ticker SOXL
python -m target_opportunity_monitor options-risk-status
python -m target_opportunity_monitor options-risk-report
```

Risk reviews use a conservative cash-secured proxy:

- Assignment notional: `strike * 100`.
- Premium income: `mid premium * 100`.
- Cash-secured requirement: `assignment notional - premium income`.
- Max-loss proxy: `breakeven * 100`.
- Downside scenarios: `-5%`, `-10%`, and `-20%` from current underlying price.

If portfolio cash/position context is unavailable, TOM still writes risk rows
with `missing_portfolio_context`. Commentary reference instruments such as
`SOXL` and `KORU` remain risk-reviewable but are labeled
`reference_only_review`.

### Phase 12D Options Outcomes And Position Ledger

Phase 12D validates reviewed sell-put ideas with stored underlying daily OHLCV
prices and optionally links them to manual read-only position rows. Outcomes are
hypothetical review outcomes unless a row exists in
`data/options/manual/options_positions.csv`.

```powershell
python -m target_opportunity_monitor load-options-positions
python -m target_opportunity_monitor compute-options-outcomes
python -m target_opportunity_monitor compute-options-outcomes --ticker SOXL
python -m target_opportunity_monitor options-position-status
python -m target_opportunity_monitor options-outcome-status
python -m target_opportunity_monitor options-outcome-report
```

The manual position CSV is created with this required core:

- `ticker`, `open_date`, `expiration_date`, `option_type`, `side`, `strike`,
  `contracts`, `premium`.
- Optional context includes `close_date`, `close_price`, `assigned_flag`,
  `assignment_price`, `fees`, `account`, `source`, `source_url`, and `notes`.

Phase 12D uses underlying prices only. It does not mark options to market,
automate assignment, place orders, write to brokers, or change scores, alerts,
ranges, or portfolio guidance.

### Phase 12E And 12E.1 Broader Option-Chain Coverage

Phase 12E expands the source-backed option-chain workflow beyond the minimum
activation set. TOM now plans full coverage for the options-eligible universe,
prioritizing missing scoreable equities first and then `SPY`/`QQQ`, while
keeping all option logic read-only.

Phase 12E.1 activates the broader provider path. `fetch-options-chain --source
auto` tries IBKR first and falls back to yfinance/Yahoo for missing tickers.
Provider rows are source-backed, cached under `data/options/cache/chains/`, and
also staged through the source-export validation shape before they are stored.

```powershell
python -m target_opportunity_monitor option-chain-coverage-plan
python -m target_opportunity_monitor fetch-options-chain --source auto --max-tickers 5 --force-refresh
python -m target_opportunity_monitor fetch-options-chain --source yfinance --max-tickers 5 --force-refresh
python -m target_opportunity_monitor export-options-chain-missing-template
python -m target_opportunity_monitor validate-options-chain-backfill
python -m target_opportunity_monitor apply-options-chain-coverage-backfill
python -m target_opportunity_monitor apply-options-chain-coverage-backfill --confirm --allow-partial
python -m target_opportunity_monitor compute-options-income
python -m target_opportunity_monitor compute-options-risk
python -m target_opportunity_monitor compute-options-outcomes
python -m target_opportunity_monitor options-status
```

`export-options-chain-missing-template` writes
`data/options/source_exports/options_chain_missing_backfill.csv` with blank
rows only for tickers that do not already have option-chain snapshots. Filled
rows must be source-backed and include `ticker`, `snapshot_timestamp`,
`expiration_date`, `option_type`, `strike`, `bid`, `ask`, `source`, and
`source_url`.

`apply-options-chain-coverage-backfill` is dry-run by default. Confirmed apply
imports valid rows and recomputes option income, risk, outcomes, and lifecycle.
It aborts if rows are invalid, if no valid rows exist, or if projected coverage
would not improve. `--allow-partial` permits progress for fewer than all missing
tickers.

### Phase 12F Options Position Lifecycle And Realized P/L

Phase 12F turns the manual read-only option-position ledger into lifecycle and
P/L reporting. TOM still treats manual positions as user-supplied truth and
does not infer real trades from reviewed ideas.

```powershell
python -m target_opportunity_monitor load-options-positions
python -m target_opportunity_monitor compute-options-outcomes
python -m target_opportunity_monitor compute-options-lifecycle
python -m target_opportunity_monitor compute-options-lifecycle --ticker SOXL
python -m target_opportunity_monitor options-lifecycle-status
python -m target_opportunity_monitor options-lifecycle-report
python -m target_opportunity_monitor options-status
```

`data/options/manual/options_positions.csv` keeps the Phase 12D required core:

- `ticker`, `open_date`, `expiration_date`, `option_type`, `side`, `strike`,
  `contracts`, `premium`.

Phase 12F adds optional lifecycle fields:

- `position_id`, `status`, `roll_from_position_id`, `roll_to_position_id`,
  `underlying_assignment_date`, `underlying_shares`,
  `underlying_cost_basis`, and `tags`.

Lifecycle reviews compute:

- closed short-put realized P/L from premium, close price, contracts,
  multiplier, and fees;
- expired-worthless P/L when stored underlying prices show expiration above
  strike;
- assignment exposure and cost-basis proxy when assignment is marked manually;
- open P/L proxy from latest option mark/mid when available.

Ambiguous cases are warnings, not guesses. Examples include
`assignment_status_needed`, `missing_option_mark`, and
`unmatched_option_review`. Reference instruments such as `SOXL` and `KORU`
remain lifecycle-reviewable but do not enter scoreable alerts, ranges, or
portfolio guidance.

Phase 12F remains read-only:

```text
No broker writes.
No order placement.
No automatic exercise or assignment handling.
No score, alert, range, or portfolio impact.
```

### Phase 12F.1 / 9B Account Context Activation

Phase 12F.1 / 9B adds a guided read-only workflow for filling the account
context that makes portfolio sizing and option lifecycle/P&L useful. It does
not infer holdings, cash, trades, or broker state.

```powershell
python -m target_opportunity_monitor account-context-status
python -m target_opportunity_monitor account-provider-status
python -m target_opportunity_monitor fetch-account-context --source ibkr --read-only
python -m target_opportunity_monitor fetch-account-context --source file --read-only --provider generic --file PATH
python -m target_opportunity_monitor export-account-context-template
python -m target_opportunity_monitor validate-account-context-backfill
python -m target_opportunity_monitor preview-account-context-activation
python -m target_opportunity_monitor apply-account-context-backfill
python -m target_opportunity_monitor apply-account-context-backfill --confirm --allow-partial
python -m target_opportunity_monitor normalize-account-export --provider generic --file PATH
python -m target_opportunity_monitor normalize-account-export --provider ibkr --file PATH
python -m target_opportunity_monitor normalize-account-export --provider ibkr-flex --file PATH
python -m target_opportunity_monitor normalize-account-export --provider ibkr-activity --file PATH
```

`export-account-context-template` creates fillable source-export CSVs under
`data/account/source_exports/` and ensures the existing manual CSV headers are
present for:

- `data/portfolio/manual/positions.csv`
- `data/portfolio/manual/cash.csv`
- `data/options/manual/options_positions.csv`

Validation is stricter than the base loaders. Nonblank rows must include
account/source metadata, required dates, and required numeric values. Confirmed
apply is guarded: invalid rows block apply, blank templates stay warning-only,
and `--allow-partial` permits importing a valid subset only when at least one
account-context count or portfolio-context blocker improves.

Confirmed apply runs:

```text
portfolio/cash import -> option position import -> portfolio context ->
option risk -> option outcomes -> option lifecycle -> daily report/dashboard
```

Everything remains read-only:

```text
No broker writes.
No order placement.
No automatic execution.
No score, alert, range, or portfolio-guidance mutation beyond reading the
user-supplied account context.
```

Phase 15A extends this workflow with provider readiness and source ingestion:

- `account-provider-status` reports local source-export rows, valid staged
  account rows, IBKR API import/connectivity state, and blockers.
- `fetch-account-context --source file --read-only --provider ... --file PATH`
  normalizes a source-backed account export into TOM source-export files.
- `fetch-account-context --source ibkr --read-only` requests IBKR account
  summary and position snapshots using read-only API calls only. If TWS/Gateway
  is unavailable, TOM records warnings and leaves account context unchanged.
- The `/activation` UI shows provider status and exposes normalize/fetch
  controls, but apply remains a separate confirmation-gated TOM workflow.

### Missing Ticker Resolver

Account, provider, commentary, and research workflows can surface tickers that
are not yet active TOM assets. The missing-ticker resolver stages those cases in
`missing_ticker_candidates` and records audit events in
`missing_ticker_resolution_events`.

For source-backed account holdings, TOM can now stage, onboard, and hydrate the
missing ticker through the normal watchlist/assets/audit path. Owned ETFs such
as `BIL` and `DBC` default to scoreable ETF assets when TOM can resolve safe ETF
metadata; unknown equities remain blocked until required metadata is supplied or
resolved. Commentary, social, and research-only mentions stay approval-gated and
are not auto-scoreable.

This is embedded in the normal automation workflow:

- `fetch-account-context --source ibkr --read-only` and file normalization stage
  missing account tickers and report whether account apply can auto-onboard them.
- `apply-account-context-backfill --confirm --allow-partial` automatically runs
  account-context missing ticker resolve/onboard/hydrate before validating the
  account rows.
- `refresh-data --daily` runs the same source-backed account resolver before
  `load-portfolio` and `compute-portfolio-context`.
- `manual-ops-cycle --mode morning` and the persistent TOM loop's morning/daily
  paths also run the resolver before universe readiness checks.

Useful commands:

```powershell
python -m target_opportunity_monitor missing-ticker-status
python -m target_opportunity_monitor resolve-missing-tickers --source account_context
python -m target_opportunity_monitor apply-missing-ticker-onboarding --confirm
python -m target_opportunity_monitor hydrate-missing-ticker --ticker BIL
python -m target_opportunity_monitor validate-account-context-backfill
python -m target_opportunity_monitor apply-account-context-backfill --confirm --allow-partial
```

Hydration is read-only. It attempts available price, ETF NAV, target, score, and
range computations, but still reports source-data gaps such as missing ETF NAVs
or holdings rather than fabricating data.

## Phase 13A Expanded Universe And Fundamental Benchmarks

Phase 13A adds a conservative workflow for adding more assets and comparing
scoreable equities against local fundamental peer groups. It does not change
targets, scores, alerts, ranges, options reviews, portfolio guidance, broker
state, or execution.

```powershell
python -m target_opportunity_monitor export-universe-candidate-template
python -m target_opportunity_monitor universe-expansion-plan
python -m target_opportunity_monitor apply-universe-candidates --confirm --allow-partial
python -m target_opportunity_monitor compute-fundamental-benchmarks
python -m target_opportunity_monitor fundamental-benchmark-status
python -m target_opportunity_monitor fundamental-benchmark-report
```

`configs/universe_candidates.csv` is the intake surface for new assets. Rows
must include `ticker`, `asset_type`, `sector`, `industry`, `country`,
`intended_role`, `source`, and `notes`. Scoreable equities also need a CIK
unless a future resolver fills it. ETFs default to `regime_proxy` unless a row
explicitly marks them scoreable.

`configs/sector_benchmarks.csv` maps overall benchmarks and GICS-style sectors
to ETF proxies such as `SPY`, `QQQ`, `XLK`, `XLC`, `XLY`, `XLP`, `XLF`, `XLV`,
`XLI`, `XLE`, `XLU`, `XLB`, and `XLRE`. Missing sector ETF assets or missing
price history are warnings, not blockers.

`compute-fundamental-benchmarks` writes:

- overall, sector, and industry benchmark medians from TOM's local scoreable
  equity universe only;
- ticker comparison snapshots for valuation, quality, growth, leverage,
  estimate coverage, valuation gap, opportunity score, and relative strength;
- sparse-peer warnings such as `insufficient_sector_peer_count` rather than
  invented sector averages.

Daily Markdown/CSV reports and the dashboard include the latest benchmark
status, sector peer count, sector ETF mapping, sector valuation discount or
premium, sector percentile, and relative strength versus `SPY`, `QQQ`, and the
mapped sector ETF.

## Phase 13B Scoreable Research Ticker Intake

Phase 13B adds a safer one-ticker wrapper for adding a name you want to research
as a scoreable equity. It resolves CIK/name/exchange from SEC company ticker
metadata, uses provider profile metadata for sector/industry when available, and
requires confirmation before writing watchlist, asset, and CIK rows.

```powershell
python -m target_opportunity_monitor research-ticker-plan --ticker TSLA
python -m target_opportunity_monitor research-ticker-plan --ticker TSLA --refresh-metadata
python -m target_opportunity_monitor apply-research-ticker --ticker TSLA --confirm
python -m target_opportunity_monitor apply-research-ticker --ticker TSLA --confirm --sector "Consumer Discretionary" --industry "Auto Manufacturers" --cik 0001318605
python -m target_opportunity_monitor refresh-research-ticker --ticker TSLA
python -m target_opportunity_monitor research-ticker-status --ticker TSLA
python -m target_opportunity_monitor fundamental-benchmark-report --ticker TSLA
```

Confirmed apply is blocked when a scoreable equity is missing CIK, sector, or
industry. If provider metadata is missing or plan-limited, supply explicit
`--sector`, `--industry`, and `--cik` values. `refresh-research-ticker` runs the
existing bounded per-ticker refresh chain and then reports remaining readiness
blockers such as missing estimates, fundamentals, target, score, or benchmark
comparison.

## Phase 13C Research Recommendation Queue

Phase 13C adds an approval-gated research ticker recommendation queue. It can
suggest tickers for research from local TOM signals, local social/commentary
captures, the sibling `research-signals` SQLite suggestion queue, and audited
manual/Codex CSV rows. These are research candidates only, not buy/sell
recommendations.

```powershell
python -m target_opportunity_monitor generate-research-recommendations --source all
python -m target_opportunity_monitor export-research-recommendation-template
python -m target_opportunity_monitor import-research-recommendations
python -m target_opportunity_monitor research-recommendation-status
python -m target_opportunity_monitor research-recommendation-report
python -m target_opportunity_monitor set-research-recommendation-status --id 1 --status approved
python -m target_opportunity_monitor promote-research-recommendation --id 1
python -m target_opportunity_monitor promote-research-recommendation --id 1 --confirm
```

Promotion reuses Phase 13B. A confirmed promotion is blocked unless the
candidate is approved and the scoreable research ticker path can resolve or is
supplied with CIK, sector, and industry metadata. X/Truth/Discord inputs are
read only from already captured local rows or approved external artifacts; this
phase adds no scraping and no score, alert, range, portfolio, broker, or
execution impact.

## Phase 14A Local TOM API Server

Phase 14A adds a local-only HTTP/JSON control plane around the existing Python
backend. It is intended for the future `F:\Investments\tom-ui` JS/TypeScript
control center. The static dashboard remains available as a read-only generated
artifact.

```powershell
python -m target_opportunity_monitor api-status
python -m target_opportunity_monitor serve-api --once-smoke-test
python -m target_opportunity_monitor serve-api
```

Default bind settings are local-only:

```toml
[api]
host = "127.0.0.1"
port = 8765
allowed_origins = ["http://127.0.0.1:5173", "http://localhost:5173"]
require_mutation_confirmation = true
```

Initial endpoints:

```text
GET  /api/health
GET  /api/status
GET  /api/dashboard-data
GET  /api/assets
GET  /api/assets/status
POST /api/assets/add
POST /api/assets/deactivate
POST /api/assets/reactivate
POST /api/assets/remove
GET  /api/research/recommendations
POST /api/research/recommendations/{id}/status
POST /api/research/recommendations/{id}/promote
POST /api/research/ticker-plan
POST /api/research/apply-ticker
POST /api/research/refresh-ticker
GET  /api/research/ticker-status
GET  /api/research/fundamental-benchmark-report
POST /api/ops/intraday-cycle
GET  /api/ops/intraday-status
GET  /api/ops/intraday-health
POST /api/ops/manual-cycle
GET  /api/scheduler/status
GET  /api/scheduler/audit
POST /api/notifications/drain
GET  /api/notifications/status
GET  /api/notifications/delivery-report
GET  /api/notifications/outbox-status
GET  /api/options/status
GET  /api/provider/status
GET  /api/account/context-status
GET  /api/account/provider-status
POST /api/account/export-template
GET  /api/account/validate-backfill
GET  /api/account/preview-activation
POST /api/account/apply-backfill
POST /api/account/normalize-export
POST /api/account/fetch-context
POST /api/account/append-row
GET  /api/backfills/options/status
POST /api/backfills/options/export-template
GET  /api/backfills/options/validate
POST /api/backfills/options/apply
GET  /api/backfills/news/status
POST /api/backfills/news/export-template
GET  /api/backfills/news/validate
POST /api/backfills/news/apply
GET  /api/backfills/short-interest/status
POST /api/backfills/short-interest/export-template
GET  /api/backfills/short-interest/validate
POST /api/backfills/short-interest/apply
```

Mutating routes require JSON `{"confirm": true}` or the header
`X-TOM-Confirm: true`. API responses are JSON objects with `ok` plus either
`data` or structured error fields. Phase 14A does not expose a public service,
place orders, write to brokers, change score rules, change alert rules, change
range rules, or mutate portfolio state outside existing confirmation-gated TOM
workflows.

## Phase 14B JS Control Center

Phase 14B adds the separate local UI repo at `F:\Investments\tom-ui`. The Python
backend remains the source of truth; the UI reads from the Phase 14A API and is
read-only in this phase.

Start TOM API first from the backend repo:

```powershell
cd F:\Investments\交易系统
python -m target_opportunity_monitor serve-api
```

Then start the UI:

```powershell
cd F:\Investments\tom-ui
npm install --cache F:\Investments\tom-ui\.npm-cache
npm run dev
```

Open `http://127.0.0.1:5173`.

Implemented read-only routes:

```text
/
/assets
/research
/ops
/scheduler
/notifications
/options
/dashboard-data
```

The UI uses `VITE_TOM_API_BASE_URL` from `F:\Investments\tom-ui\.env.local`.

## Phase 14C Research UI

Phase 14C makes `/research` operational for approval-gated research intake.

- `Recommendation Queue` supports status filtering, text search, detail review,
  approve/ignore/reject actions, and promote preparation.
- `Ticker Intake` supports ticker planning, confirmed apply, confirmed refresh,
  ticker readiness status, and per-ticker fundamental benchmark reports.
- Promote/apply/refresh/status-change actions open a local confirmation dialog
  before the UI sends API confirmation.

Phase 14C does not add bulk actions, broker writes, order placement, execution,
score-rule changes, alert-rule changes, range-rule changes, or portfolio
mutation.

## Phase 14D Operational Controls UI

Phase 14D adds local control routes for TOM operations:

- `/assets` supports asset detail/status plus confirmation-gated add/update,
  deactivate, reactivate, and soft-remove actions.
- `/ops` shows intraday health, quote/range freshness, manual-ops status, and
  confirmation-gated one-shot `intraday-cycle` and `manual-ops-cycle` buttons.
- `/scheduler` shows scheduler reconciliation, heartbeat command state,
  recommended repair text, and automation status without mutating Codex
  automations.
- `/notifications` shows pending/delivered/failed notification state, delivery
  report, outbox status, and a confirmation-gated file-drain action.

The UI shows the Phase 11E loop state and the preferred operator command:

```powershell
python -m target_opportunity_monitor tom-loop-start --mode auto --deliver --channel file
```

Phase 14D does not add broker writes, order placement, execution, score-rule
changes, alert-rule changes, range-rule changes, or portfolio mutation.

## Phase 14E Activation And Backfill UI

Phase 14E adds the remaining CSV/source-export workflows to the local UI:

- `/activation` shows account-context blockers for portfolio positions, cash,
  option positions, option lifecycle rows, and option-risk portfolio context.
  It can export templates, validate, preview, dry-run apply, confirmed apply,
  and stage simple portfolio/cash/option-position rows into known
  source-export CSVs.
- `/backfills` shows source-data panels for option-chain coverage,
  news/catalyst provider-native upgrades, and short-interest missing rows. Each
  panel can export templates, validate, show current blockers, and run
  confirmation-gated apply when TOM says coverage can improve.

Row-builder submissions append only to TOM-controlled source-export/template
paths. They still must pass TOM validation, preview, and confirmation-gated
apply before they affect backend CSVs or SQLite state. Phase 14E does not add
arbitrary file upload, broker writes, order placement, execution, score-rule
changes, alert-rule changes, range-rule changes, or portfolio mutation outside
existing TOM workflows.

## Tests

Use the tiered runner for normal development. It runs test files as scripts,
prints per-file timings, and applies a per-file timeout so one slow file does
not make the whole shell wrapper look like a regression failure.

```powershell
python tools/run_tests.py smoke
python tools/run_tests.py core
python tools/run_tests.py signals
python tools/run_tests.py ops
python tools/run_tests.py options
python tools/run_tests.py analytics
python tools/run_tests.py full --timeout-per-file 180
```

Recommended local loop:

```powershell
python tools/run_tests.py smoke
python tools/run_tests.py <suite-for-touched-code>
python tools/run_tests.py full --timeout-per-file 180
```

The legacy unittest discovery command is still valid for full regression
fallback, but it can take around 10 minutes on this machine:

```powershell
python -m unittest discover -s tests
```
