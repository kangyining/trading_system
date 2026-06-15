# News/Catalyst Source Workflow

Phase 10E.6 keeps news and catalyst signals source-backed and shadow-only.
The final compatibility file is still:

```text
data/signals/manual/news_catalysts.csv
```

But the preferred workflow is now:

```text
provider/manual source rows
-> news_catalyst_source_snapshots
-> optional deterministic text backfill
-> news_catalyst_aggregates
-> data/signals/manual/news_catalysts.csv
-> existing load/compute/validate commands
```

## Approved Sources

Use these in priority order:

1. Provider-numeric API rows from Alpha Vantage News Sentiment, Marketaux
   entity sentiment, EODHD sentiment/news, Finnhub news/sentiment, or FMP news
   where numeric sentiment is returned.
2. Licensed or user-provided provider exports.
3. Source-backed text rows from X recent search, Truth Social public posts,
   Serenity, Kobeissi, newsletters, screenshots/exports, filings, company
   releases, earnings events, product/conference pages, reputable news pages, or
   other auditable public event pages. These become numeric only through the
   deterministic Phase 10E.4 backfill step.
4. Manual source-export captures from filings, company releases, earnings
   events, product/conference pages, reputable news pages, or other auditable
   public event pages.

Do not use unsupported snippets or memory-only impressions as production rows.
Do not fabricate sentiment, catalyst, urgency, relevance, or confidence values.
If a source only gives a headline/event, leave numeric fields blank. The row is
preserved as audit context. It can create a numeric aggregate only if
`compute-news-catalyst-text-backfill` derives a lower-confidence numeric snapshot
from the fixed lexicon.

## Source Export Schema

Default directory:

```text
data/signals/source_exports/news_catalysts/
```

Required columns:

```text
ticker, signal_date, source, source_url, headline_or_event
```

Optional columns:

```text
article_datetime, event_date, topic, summary, sentiment_score, catalyst_score,
urgency_score, relevance_score, confidence, notes, capture_method
```

All scores are `0-100`.

## Coverage Queue

Phase 10E.5 uses two durable coverage queues:

- missing numeric rows,
- provider-native upgrades for tickers currently covered only by deterministic
  text-derived rows.

Use:

```powershell
python -m target_opportunity_monitor news-catalyst-coverage-plan
python -m target_opportunity_monitor news-catalyst-coverage-plan --mode missing
python -m target_opportunity_monitor news-catalyst-coverage-plan --mode provider-upgrade
python -m target_opportunity_monitor news-catalyst-source-status --missing-only
python -m target_opportunity_monitor news-catalyst-source-status --provider-upgrade-only
python -m target_opportunity_monitor news-catalyst-source-status --provider-warnings
python -m target_opportunity_monitor news-catalyst-provider-upgrade-status
python -m target_opportunity_monitor test-news-catalyst-provider --provider all --ticker AAPL
python -m target_opportunity_monitor fetch-news-catalyst-sources --coverage-plan
python -m target_opportunity_monitor fetch-news-catalyst-sources --coverage-plan --coverage-mode provider-upgrade
python -m target_opportunity_monitor fetch-news-catalyst-sources --provider-upgrade
```

The planner prioritizes:

1. Active equities with no numeric news/catalyst row.
2. Active equities with only text-derived numeric rows and no provider-native
   numeric rows.
3. Active equities with stale source-backed rows.

It excludes SPY and QQQ from scoring coverage because ETF news/catalyst scoring
is still gated. The missing-numeric template is:

```text
data/signals/source_exports/news_catalysts/news_catalyst_missing_coverage_queue.csv
```

The provider-native upgrade template is:

```text
data/signals/source_exports/news_catalysts/news_catalyst_provider_upgrade_queue.csv
```

When total numeric coverage is complete, the missing-numeric template should be
empty/header-only. Provider-native quality work should appear in the provider
upgrade template instead of making the missing queue look stale.

The template contains one blank row per planned ticker. These rows are skipped
by import until they have real source-backed values. To fill one:

- keep the ticker and signal date,
- set `source` to the provider/export source,
- add a real `source_url`,
- add the actual `headline_or_event`,
- fill only numeric fields the source truly provides,
- leave unsupported numeric fields blank,
- keep notes clear enough to audit the source later.

Do not type a personal sentiment guess into `sentiment_score`, `catalyst_score`,
`urgency_score`, `relevance_score`, or `confidence`. Headline-only rows are
allowed for audit. Aggregation ignores them until either a provider/export
numeric field exists or deterministic text backfill creates a derived numeric
snapshot.

Provider-native upgrade rows can use these export labels when the row contains
auditable provider-backed numeric fields:

- `marketaux_export`
- `eodhd_export`
- `x_export`
- `licensed_news_provider_export`
- `user_provider_export`

Rows that claim a provider-native upgrade but lack `source_url`,
`headline_or_event`, or at least one aggregate numeric field are skipped with a
warning and are not stored as source snapshots.

## Provider-Native Backfill Package

When API providers are missing, rate-limited, headline-only, or plan-limited,
generate a local audited backfill package:

```powershell
python -m target_opportunity_monitor export-news-catalyst-provider-backfill
```

This writes:

```text
data/signals/source_exports/news_catalysts/provider_native_backfill/news_catalyst_provider_native_backfill.csv
data/signals/source_exports/news_catalysts/provider_native_backfill/README.md
```

The generated CSV contains only active equities that are still text-derived-only.
Fill it only from provider exports or source-backed numeric provider fields. Leave
unknown fields blank. Do not hand-score headlines, do not fabricate values, and do
not add ETF rows.

The default `import-news-catalyst-source-exports` command scans the source-export
tree, including this package. Invalid provider-native rows remain visible through
`news-catalyst-provider-upgrade-status`, `status`, reports, and dashboard output.

Before importing a filled package, dry-run the package:

```powershell
python -m target_opportunity_monitor validate-news-catalyst-provider-backfill
python -m target_opportunity_monitor preview-news-catalyst-provider-upgrade
```

Validation classifies valid provider-native rows, blank placeholders, invalid
rows, unsupported tickers, ETF-gated rows, malformed dates/numbers, and missing
provider-native fields without storing snapshots or changing aggregates. Blank
placeholders are normal queue rows and are not failures.

The preview compares valid backfill rows with current persisted coverage and
reports current provider-native coverage, text-derived-only tickers, valid rows
ready to import, projected provider-native coverage after import, and still
blocked tickers. Only run the import/aggregate/load/compute/validate chain when
the preview is clean.

## Provider Export Normalization And Guarded Apply

If Marketaux, EODHD, X, a licensed provider, or a user/provider export gives a
CSV that is not already in TOM's source-export schema, normalize it first:

```powershell
python -m target_opportunity_monitor normalize-news-catalyst-provider-export --provider marketaux --file PATH
python -m target_opportunity_monitor normalize-news-catalyst-provider-export --provider eodhd --file PATH
python -m target_opportunity_monitor normalize-news-catalyst-provider-export --provider x --file PATH
python -m target_opportunity_monitor normalize-news-catalyst-provider-export --provider licensed --file PATH
python -m target_opportunity_monitor normalize-news-catalyst-provider-export --provider generic --file PATH
```

The normalized file is written to:

```text
data/signals/source_exports/news_catalysts/provider_native_backfill/normalized_{provider}_provider_native.csv
```

Normalization rules:

- Only active equities in the provider-native upgrade queue are accepted.
- Already provider-native tickers are skipped so they do not overwrite good
  provider evidence.
- SPY/QQQ are ETF-gated for this equity news/catalyst signal path.
- Provider polarity values in `[-1, 1]` are converted to `0-100`.
- Already normalized `0-100` fields pass through.
- Headline-only/text-only rows are rejected unless at least one source-backed
  provider numeric field is present.
- The output remains a source-export file; it is not imported automatically.

Check combined readiness:

```powershell
python -m target_opportunity_monitor news-catalyst-provider-backfill-status
python -m target_opportunity_monitor apply-news-catalyst-provider-backfill
```

The apply command is dry-run only by default. It prints whether the package is
apply-ready, valid upgrade tickers, projected upgrade delta, and any blocking
reason. Confirmed apply is guarded:

```powershell
python -m target_opportunity_monitor apply-news-catalyst-provider-backfill --confirm
python -m target_opportunity_monitor apply-news-catalyst-provider-backfill --confirm --allow-partial
```

Confirmed apply aborts if invalid rows exist, valid rows are zero, or projected
provider-native coverage would not improve. Use `--allow-partial` when one or
more tickers can be upgraded but some text-derived-only tickers remain blocked.

## Provider Smoke Tests

Before depending on a provider-native upgrade source, run:

```powershell
python -m target_opportunity_monitor test-news-catalyst-provider --provider all --ticker AAPL
python -m target_opportunity_monitor test-news-catalyst-provider --provider marketaux --ticker AAPL
python -m target_opportunity_monitor test-news-catalyst-provider --provider eodhd --ticker AAPL
python -m target_opportunity_monitor test-news-catalyst-provider --provider x_recent_search --ticker AAPL
```

The command checks key presence and makes at most one low-budget request per
provider/ticker. It classifies readiness as `provider_numeric_available`,
`headline_only`, `rate_limited`, `plan_limited`, `auth_failed`, `missing_key`,
or `http_failed`. It never prints API key values.

Configure keys as environment variables only:

- `MARKETAUX_API_KEY`
- `EODHD_API_KEY`
- `X_BEARER_TOKEN`

Smoke tests suppress failure snapshot writes. Successful source-backed provider
rows may be stored normally so they can be aggregated into the shadow signal
workflow.

## Provider Rules

- Alpha Vantage ticker sentiment is converted from polarity `[-1, 1]` to
  `0-100` with `(score + 1) * 50`.
- Marketaux entity `sentiment_score` is converted from polarity `[-1, 1]` to
  `0-100` with `(score + 1) * 50`. Symbols like `AAPL.US` are matched to
  `AAPL`.
- EODHD sentiment/polarity fields are converted from polarity `[-1, 1]` to
  `0-100` with `(score + 1) * 50` when available.
- Finnhub bullish/bearish percentage sentiment is converted to `0-100` with
  `50 + (bullish - bearish) / 2` after percentages are normalized.
- FMP numeric sentiment is accepted only when a numeric score is returned. Text
  labels are not converted into scores in this MVP.
- X recent-search and Truth Social public rows are source-backed text only.
  They do not provide provider-numeric sentiment.
- Provider failures, missing keys, rate limits, and plan limits are stored or
  reported as warnings, not as fatal daily-pipeline errors.
- Provider fetches are cache-aware. Fresh raw payloads are reused before live
  API calls unless `--force-refresh` or `--no-cache` is supplied.
- Live calls are capped by `news_catalyst_provider_request_budget` or by the
  CLI `--max-tickers` value. When a provider returns an auth, plan, or
  rate-limit warning, remaining tickers are skipped for that provider cycle.
- Cache payloads live under `data/signals/cache/news_catalysts/{provider}/`.
  They contain provider, ticker, timestamp, and returned JSON payload only.
  API keys are never stored.
- Provider-limit, auth, malformed, empty, or unexpected payloads are not treated
  as numeric signal inputs. They remain warnings until a valid provider payload
  or audited source-export row exists.

## Aggregation Rules

- Aggregates are one canonical row per `ticker + signal_date`.
- Numeric fields use weighted median.
- If provider-native numeric rows exist for a ticker/date, deterministic
  text-derived rows for that same ticker/date are kept for audit but excluded
  from aggregate calculation.
- Default weights:
  - Alpha Vantage: `1.0`
  - Marketaux: `1.0`
  - EODHD: `0.9`
  - Finnhub: `0.8`
  - FMP: `0.7`
  - X recent-search: `0.35`
  - Truth Social public: `0.25`
  - deterministic text backfill: `0.35`
  - Marketaux export: `1.0`
  - EODHD export: `0.9`
  - X export: `0.7`
  - Licensed news provider export: `0.9`
  - Licensed/manual provider export: `0.9`
  - Headline-only rows: `0.0`
- Warnings are added for single-source aggregates, missing primary sentiment
  sources, headline-only rows, medium/high source disagreement, provider
  failures, stale rows, and ETF gating.

## Deterministic Text Backfill

Phase 10E.4 adds deterministic text backfill for source-backed headline/event
rows that do not have provider-numeric sentiment.

Run:

```powershell
python -m target_opportunity_monitor compute-news-catalyst-text-backfill
python -m target_opportunity_monitor compute-news-catalyst-text-backfill --ticker AMD
```

Backfill rules:

- It never overwrites a ticker/date with provider-numeric evidence.
- It uses only source-backed rows with `source_url` and `headline_or_event`.
- It scores text with fixed positive, negative, catalyst, and urgency term
  lists.
- It stores derived rows as `source = "news_text_backfill"`.
- It adds warnings: `text_derived_sentiment`, `lower_confidence_source`,
  `not_provider_numeric`, and `derived_from:<source>`.
- It stays shadow-only and does not change final opportunity scores, alerts,
  portfolio guidance, notifications, or execution.

Use text-derived coverage as evidence to watch and validate, not as a
provider-quality substitute.

## Commands

```powershell
python -m target_opportunity_monitor fetch-news-catalyst-sources --provider all --max-tickers 3
python -m target_opportunity_monitor fetch-news-catalyst-sources --provider alpha_vantage --max-tickers 1 --force-refresh
python -m target_opportunity_monitor fetch-news-catalyst-sources --provider marketaux --coverage-plan
python -m target_opportunity_monitor fetch-news-catalyst-sources --provider eodhd --coverage-plan
python -m target_opportunity_monitor fetch-news-catalyst-sources --provider x_recent_search --coverage-plan
python -m target_opportunity_monitor fetch-news-catalyst-sources --provider truth_social_public --coverage-plan
python -m target_opportunity_monitor fetch-news-catalyst-sources --coverage-plan --coverage-mode provider-upgrade
python -m target_opportunity_monitor fetch-news-catalyst-sources --provider-upgrade
python -m target_opportunity_monitor news-catalyst-provider-upgrade-status
python -m target_opportunity_monitor test-news-catalyst-provider --provider all --ticker AAPL
python -m target_opportunity_monitor export-news-catalyst-provider-backfill
python -m target_opportunity_monitor normalize-news-catalyst-provider-export --provider generic --file PATH
python -m target_opportunity_monitor validate-news-catalyst-provider-backfill
python -m target_opportunity_monitor preview-news-catalyst-provider-upgrade
python -m target_opportunity_monitor news-catalyst-provider-backfill-status
python -m target_opportunity_monitor apply-news-catalyst-provider-backfill
python -m target_opportunity_monitor import-news-catalyst-source-exports
python -m target_opportunity_monitor compute-news-catalyst-text-backfill
python -m target_opportunity_monitor aggregate-news-catalyst-sources
python -m target_opportunity_monitor load-news-catalysts
python -m target_opportunity_monitor compute-news-catalyst-signals
python -m target_opportunity_monitor validate-news-catalyst-signals
python -m target_opportunity_monitor news-catalyst-coverage-plan
python -m target_opportunity_monitor news-catalyst-source-status
python -m target_opportunity_monitor news-catalyst-source-status --missing-only
python -m target_opportunity_monitor news-catalyst-source-status --provider-warnings
python -m target_opportunity_monitor news-catalyst-status
```

## Gating

AAPL/MSFT/NVDA plus the expanded liquid equity universe are eligible for
news/catalyst shadow scoring when source-backed numeric rows exist.

SPY and QQQ can have informational source snapshots, but ETF news/catalyst
scoring remains gated in Phase 10E.4.

News/catalyst signals remain shadow-only. They do not change final opportunity
scores, alerts, portfolio guidance, notifications, orders, or execution.
