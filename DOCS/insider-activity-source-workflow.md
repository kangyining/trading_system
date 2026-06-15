# SEC Insider Activity Source Workflow

Phase 10F adds SEC Form 4 insider activity as a source-backed shadow signal.
This workflow uses official SEC data only and does not scrape third-party pages.

## Source Priority

1. `configs/cik_map.csv` maps each active equity ticker to a SEC CIK.
2. SEC submissions JSON is fetched from:
   `https://data.sec.gov/submissions/CIK{cik}.json`
3. Recent Form 4 filings are selected from the submissions `filings.recent`
   arrays.
4. Each filing's ownership XML/document is fetched from the SEC archive.
5. Raw submissions and filing documents are cached under:
   `data/signals/cache/insider_transactions/`

ETF rows such as `SPY` and `QQQ` are not company insiders and stay gated with
`etf_insider_activity_gated`.

Daily full-watchlist fetches use cache by default and are bounded by:

```toml
signals.insider_activity_max_tickers_per_run = 13
signals.insider_activity_use_cache = true
signals.insider_activity_sec_request_delay_seconds = 0.2
signals.insider_activity_sec_rate_limit_cooldown_seconds = 60
signals.insider_activity_stop_on_rate_limit = true
signals.insider_activity_max_live_form4_fetches_per_ticker = 10
signals.insider_activity_skip_successful_fetch_same_day = true
```

Manual fetch controls:

- `--max-tickers N`: fetch only the first `N` active equity tickers for this
  run.
- `--use-cache`: read cached SEC submissions and Form 4 documents when present.
- `--no-cache`: bypass cache reads while still allowing fresh payloads to be
  stored.
- `--force-refresh` or `--refresh-cache`: force fresh SEC requests.

## SEC Pacing And Rate Limits

Phase 10F.2 keeps the SEC path polite and report-friendly:

- cached submissions and Form 4 documents are preferred;
- live Form 4 document requests are paced by
  `signals.insider_activity_sec_request_delay_seconds`;
- live Form 4 document fetches are capped per ticker by
  `signals.insider_activity_max_live_form4_fetches_per_ticker`;
- a SEC `429 Too Many Requests` response records `sec_rate_limited`, stops
  live fetches for that ticker when
  `signals.insider_activity_stop_on_rate_limit = true`, and applies the
  configured cooldown;
- when a ticker already had a successful same-day fetch, daily runs parse
  cached documents and skip missing live documents unless `--force-refresh` is
  used.

Detailed accession-level failures stay in `data_quality_checks` for audit.
Normal CLI/report/dashboard output compacts repeated filing failures, for
example `sec_rate_limited: 18 filings affected`.

## Normalized Storage

Parsed rows are stored in `insider_transaction_source_snapshots`.

Important fields:

- `ticker`
- `cik`
- `accession_number`
- `filing_date`
- `transaction_date`
- `owner_name`
- `owner_title`
- `transaction_code`
- `acquired_disposed_code`
- `shares`
- `price`
- `transaction_value`
- `source_url`
- `provider_status`
- `data_warnings`

The table is idempotent by ticker, filing accession, owner, transaction date,
transaction code, acquired/disposed code, shares, price, and source.

## Transaction-Code Handling

- `P`: open-market purchase, supportive.
- `S`: open-market sale, weak-to-moderate negative.
- Routine or compensation/exercise-style codes such as `A`, `D`, `F`, `M`,
  `C`, `X`, `G`, `I`, `J`, `U`, `W`, and `Z`: neutral with
  `routine_or_compensation_related`.
- Small transactions below
  `signals.insider_activity_min_transaction_value` receive
  `small_transaction_value`.

The model intentionally treats insider sales more cautiously than purchases,
because sales can be driven by diversification, taxes, or planned programs.

## Shadow Signals

Stored signal names:

```text
insider_activity.open_market_buying
insider_activity.sale_pressure
insider_activity.routine_activity
insider_activity.composite
```

Positive composite means supportive insider buying. Negative composite means
insider-sale pressure. Neutral means no meaningful recent open-market signal or
only routine activity.

All signals include `insider_activity_shadow_mode` while this signal family is
being collected and validated.

## Validation

`validate-insider-signals` reuses the existing signal validation layer:

- Entry price: latest stored daily price on or before the signal date.
- Horizons: `5d`, `20d`, `60d`, `120d`.
- Positive insider signals expect positive forward returns.
- Negative insider signals expect negative forward returns.
- Neutral insider signals are tracked but excluded from directional hit-rate.

Validation rows are stored in `signal_outcomes`.

## Commands

```powershell
python -m target_opportunity_monitor fetch-insider-transactions
python -m target_opportunity_monitor fetch-insider-transactions --ticker AAPL
python -m target_opportunity_monitor fetch-insider-transactions --ticker AAPL --refresh-cache
python -m target_opportunity_monitor fetch-insider-transactions --max-tickers 13 --use-cache
python -m target_opportunity_monitor compute-insider-signals
python -m target_opportunity_monitor compute-insider-signals --ticker AAPL
python -m target_opportunity_monitor validate-insider-signals
python -m target_opportunity_monitor validate-insider-signals --ticker AAPL
python -m target_opportunity_monitor insider-source-status
python -m target_opportunity_monitor insider-source-status --verbose
python -m target_opportunity_monitor insider-status
python -m target_opportunity_monitor insider-validation-report
```

Daily refresh runs insider fetch, compute, and validation before reports and the
dashboard are regenerated.

## Source Health

`insider-source-status` is the operational coverage check. It reports:

- active equity coverage as `covered/active_equities`,
- ETF-gated tickers,
- source row count,
- latest filing date,
- latest transaction date,
- latest successful fetch date,
- confirmed no-recent-activity tickers,
- parse-warning tickers,
- SEC-rate-limited tickers,
- stale source tickers,
- missing or unfetched source tickers.

The default output uses compact warning summaries. Use
`insider-source-status --verbose` when you need raw accession-level SEC warning
details.

Coverage includes tickers with SEC source rows and tickers with a successful
fetch that confirms no recent Form 4 filings. Parse-warning and missing-CIK
states remain warnings and should not be treated as healthy source coverage.

## No-Impact Rule

Phase 10F does not change final opportunity scores, alerts, portfolio guidance,
notifications, execution, or orders. It is evidence collection only.
