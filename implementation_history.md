# Implementation History

Created: 2026-06-09

Purpose: archive completed implementation logs from `execution_plan.md` so the execution plan can stay focused on the current roadmap.

---

## 6. Implementation log

### 2026-06-15 - Live API/UI runtime closure

Completed:

- Started the local TOM API runtime from `F:\Investments\交易系统`.
  - API URL: `http://127.0.0.1:8765`
  - API process ID observed at launch: `38768`
- Started the local Vite UI runtime from `F:\Investments\tom-ui`.
  - UI URL: `http://127.0.0.1:5173`
  - UI launcher process ID observed at launch: `7076`
- Kept scheduler automation disabled by choice; the durable TOM loop remains the
  operational heartbeat.
- Did not change broker state, provider keys, source rows, recommendation
  decisions, option positions, or evidence gates.

Verification:

- `python -m target_opportunity_monitor status` reported TOM loop `running`,
  loop health `healthy`, intraday health `healthy`, pending notifications `0`,
  research pending `0`, news/catalyst source-backed coverage `33/33`,
  short-interest source-backed coverage `33/33`, effective option-chain coverage
  complete, and trader-commentary unmapped labels `0`.
- `python -m target_opportunity_monitor serve-api --once-smoke-test` passed.
- `npm run build` in `F:\Investments\tom-ui` passed.
- API routes returned `200` with `ok=True`:
  `/api/health`, `/api/status`, `/api/signals/status`,
  `/api/coverage/status`, and `/api/research/preparation/status`.
- UI routes returned `200`:
  `/`, `/signals`, `/coverage`, `/backfills`, `/activation`, `/research`, and
  `/loop`.
- Browser verification confirmed `/research` no longer shows
  `Local backend offline` and no longer reports unknown
  `/api/research/preparation/status`.
- Browser verification confirmed `/signals` and `/coverage` render after data
  load with no backend-offline or unknown-route errors. The signal API payload
  exposes trader-commentary counts:
  `unmapped_label_count=0`, `label_disposition_count=2`, and
  `intentionally_unresolved_label_count=2`.
- Post-checks:
  - `python -m target_opportunity_monitor tom-loop-status` reported
    `running/healthy`.
  - `python -m target_opportunity_monitor intraday-health-check` reported
    `healthy` with off-hours notes only.

Still open:

- Option-position/lifecycle source data requires real option-position rows.
- Phase 10D analyst-revision score impact remains evidence-gated.
- Full trader-commentary capture remains opt-in/setup-gated.
- Optional provider-native news redundancy remains key/export-gated.

### 2026-06-15 - Trader-commentary reviewed label dispositions

Completed:

- Added a guarded commentary label-disposition workflow beside the existing
  ticker-alias workflow.
- Added
  `data/signals/manual/trader_commentary_label_dispositions.csv` with reviewed
  dispositions for `unmapped_context` and `大盘` as
  `intentionally_unresolved_ambiguous`; `大盘` renders as `??` in legacy console
  output.
- Kept `trader_commentary_instrument_aliases.csv` reserved for real ticker
  mappings only; the new dispositions do not remap claims, validate claims, or
  promote any label to a ticker.
- Extended `trader-commentary-parse-review`, `commentary-onboarding-status`,
  `status`, signal coverage, reports, and dashboard data to distinguish true
  unmapped labels from intentionally unresolved or ignored labels.

Verification:

- `python -m py_compile src\target_opportunity_monitor\commentary_onboarding.py src\target_opportunity_monitor\trader_commentary.py src\target_opportunity_monitor\cli.py src\target_opportunity_monitor\reporting.py src\target_opportunity_monitor\dashboard.py src\target_opportunity_monitor\signal_coverage.py`
  passed.
- `python tests\test_phase10h3_commentary_onboarding.py` passed.
- `python tests\test_phase10h_trader_commentary.py` passed.
- `python tests\test_phase14f_signal_coverage_api.py` passed.
- `python -m target_opportunity_monitor load-commentary-label-dispositions`
  loaded `2` rows with `0` invalid rows.
- `python -m target_opportunity_monitor trader-commentary-parse-review`
  reported unmapped instrument claims `0` and intentionally unresolved
  instrument claims `8`.
- `python -m target_opportunity_monitor commentary-onboarding-status` reported
  unmapped labels `0`, label dispositions `2`, and intentionally unresolved
  labels `2`.
- `python -m target_opportunity_monitor status` reported trader-commentary
  unmapped instrument labels `0`, label dispositions `2`, intentionally
  unresolved labels `2`, TOM loop `running`, loop health `healthy`, intraday
  health `healthy`, and pending notifications `0`.
- `python -m target_opportunity_monitor serve-api --once-smoke-test` passed.
- `python tools\run_tests.py smoke --timeout-per-file 180` passed.
- `npm run build` in `F:\Investments\tom-ui` passed.

Still open:

- Full X/browser and Discord commentary capture remain opt-in/setup-gated.
- Option-position/lifecycle source data and Phase 10D analyst-revision evidence
  maturity remain separate open items.

### 2026-06-15 - SIVE/SOI source-backed news/catalyst closure

Completed:

- Refreshed the existing missing news/catalyst coverage queue; the active
  missing tickers were `SIVE` and `SOI`.
- Ran the configured provider fetch path first. It stored `0` rows for
  `SIVE`/`SOI`; available providers were empty, headline-only, key-limited, or
  plan-limited for these foreign tickers.
- Staged two source-backed text rows in
  `data/signals/source_exports/news_catalysts/news_catalyst_source_export.csv`.
- `SIVE` uses Sivers' official `2026-05-06` release:
  `Tachyon Networks Expands FWA Portfolio With USD1.5M Development Partnership
  With Sivers Semiconductors`.
- `SOI` uses Soitec's official `2026-05-27` FY2025-2026 financial-results
  release.
- Imported source exports, derived TOM text-backed numeric rows, aggregated,
  loaded, computed, and validated news/catalyst signals for both tickers.
- Preserved boundaries: no broker writes, no orders, no recommendation
  decisions, no option-position rows, no provider secrets, and no fabricated
  news/catalyst scores were added.

Verification:

- `python -m target_opportunity_monitor fetch-news-catalyst-sources --provider all --coverage-plan --coverage-mode missing --use-cache`
  reported `fetched=0`, `stored=0`, `numeric_stored=0`, and provider warnings
  for empty/limited provider paths.
- `python -m target_opportunity_monitor import-news-catalyst-source-exports`
  imported `2` source rows for `SIVE` and `SOI`.
- `python -m target_opportunity_monitor compute-news-catalyst-text-backfill --ticker SIVE`
  derived `1` row with expected `SIVE:text_derived_sentiment`.
- `python -m target_opportunity_monitor compute-news-catalyst-text-backfill --ticker SOI`
  derived `1` row with expected `SOI:text_derived_sentiment`.
- `python -m target_opportunity_monitor aggregate-news-catalyst-sources`
  produced `64` aggregates and final CSV rows including `SIVE` and `SOI`.
- `python -m target_opportunity_monitor load-news-catalysts` loaded `64` rows
  from `data/signals/manual/news_catalysts.csv`.
- `python -m target_opportunity_monitor compute-news-catalyst-signals --ticker SIVE`
  computed `SIVE` with composite `52.33` and expected shadow/low-confidence
  warnings.
- `python -m target_opportunity_monitor compute-news-catalyst-signals --ticker SOI`
  computed `SOI` with composite `49.33` and expected shadow/low-confidence
  warnings.
- `python -m target_opportunity_monitor validate-news-catalyst-signals`
  updated `55` validations; `SIVE` and `SOI` validation outcomes are partial.
- `python -m target_opportunity_monitor news-catalyst-source-status --missing-only`
  reported source-backed ticker coverage `33/33` and missing source-backed
  tickers `none`.
- `python -m target_opportunity_monitor status` reported TOM loop `running`,
  loop health `healthy`, intraday health `healthy`, pending notifications `0`,
  news/catalyst numeric ticker coverage `33/33`, and missing numeric tickers
  `0`.

Still open:

- Optional provider-native numeric news/catalyst redundancy remains `20/33` and
  is queued separately.
- Option-position/lifecycle source data, Phase 10D evidence maturity, and full
  trader-commentary capture opt-in/setup remain separate open items.

### 2026-06-15 - SIVE/SOI source-backed short-interest closure

Completed:

- Ran the existing short-interest missing-source resolver before editing source
  rows. It normalized `0` rows for `SIVE`/`SOI`; FINRA returned 404 and Nasdaq
  Trader returned empty/not-found payloads for both foreign tickers.
- Staged two source-backed rows in
  `data/signals/source_exports/short_interest/missing_provider_short_interest_backfill.csv`.
- `SIVE` uses Finansinspektionen's official net-short-position register:
  latest position date `2026-06-12`, current-list publication/update date
  `2026-06-15`, and total short percentage `5.5%`.
- `SOI` uses AMF BDIF net-short-position document `2026E1120460`: position
  date `2026-06-11`, disclosure date `2026-06-12`, and net short position
  `0.98%`.
- Ran dry-run apply before confirmed apply. Confirmed apply imported the
  validated source set to `data/signals/manual/short_interest.csv`.
- Loaded short-interest rows and recomputed/validated short-interest signals.
  `SIVE` and `SOI` now compute as shadow-only equity short-interest signals
  with expected single-row history warnings.
- Preserved boundaries: no broker writes, no orders, no recommendation
  decisions, no option-position rows, no provider secrets, and no news/catalyst
  rows were changed.

Verification:

- `python -m target_opportunity_monitor validate-short-interest-backfill`
  reported current coverage `31/33`, projected coverage `33/33`, valid rows
  `554`, valid tickers including `SIVE` and `SOI`, invalid rows `0`, and import
  apply ready `True`.
- `python -m target_opportunity_monitor apply-short-interest-provider-backfill`
  dry-run reported projected coverage improvement `2`, imported rows `0`, and
  apply ready `True`.
- `python -m target_opportunity_monitor apply-short-interest-provider-backfill --confirm`
  reported confirmed apply, imported rows `554`, written rows `586`, and blocked
  apply reason `none`.
- `python -m target_opportunity_monitor load-short-interest` loaded `562`
  source rows from `586` CSV rows, with `GOOG:inactive_or_unknown_ticker` as the
  only warning.
- `python -m target_opportunity_monitor compute-short-interest-signals` computed
  `33` equity tickers and skipped `17` ETF-gated tickers; `SIVE` composite was
  `59.80` and `SOI` composite was `66.13`.
- `python -m target_opportunity_monitor validate-short-interest-signals`
  updated `42` validations; `SIVE` and `SOI` validation outcomes are pending.
- `python -m target_opportunity_monitor short-interest-missing-coverage-plan`
  reported current source-backed coverage `33/33`, projected coverage `33/33`,
  missing source tickers `none`, valid missing-row tickers `none`, and
  diagnostics `none`.
- `python -m target_opportunity_monitor short-interest-status` reported
  source-backed coverage `33/33`, source rows `562`, latest settlement date
  `2026-06-12`, missing source tickers `none`, and stale source tickers `none`.
- `python tests\test_phase10g_short_interest.py` passed: 12 tests.
- `python tests\test_phase14e_activation_api.py` passed: 12 tests.
- `python tests\test_phase14f_signal_coverage_api.py` passed: 9 tests.
- `python tools\run_tests.py smoke --timeout-per-file 180` passed: 14 files.
- `python -m target_opportunity_monitor serve-api --once-smoke-test` passed
  with health/status `200`.
- `npm run build` in `F:\Investments\tom-ui` passed.
- `python -m target_opportunity_monitor status` reported TOM loop `running`,
  loop health `healthy`, intraday health `healthy`, pending notifications `0`,
  short-interest source-backed tickers `33/33`, and short-interest missing
  coverage tickers `none`.

Still open:

- `SIVE` and `SOI` still need source-backed news/catalyst rows.
- Option-position/lifecycle source data, Phase 10D evidence maturity, full
  trader-commentary capture opt-in/setup, and optional provider-native news
  redundancy remain separate open items.

### 2026-06-15 - SIVE/SOI source-backed option-chain availability decisions

Completed:

- Ran real option-chain fetch attempts for `SIVE` and `SOI` before editing any
  source rows.
- `fetch-options-chain --source auto --ticker SIVE --force-refresh` loaded `0`
  rows and reported `no_ibkr_underlying_contract` plus `no_expirations`.
- `fetch-options-chain --source auto --ticker SOI --force-refresh` loaded `0`
  rows and reported `no_ibkr_underlying_contract` plus `no_expirations`.
- Added source-backed non-actionable option-chain decisions for `SIVE` and
  `SOI` to `data/options/source_exports/options_chain_non_actionable.csv` with
  `reason_code=no_listed_options`, source `yfinance_option_chain`, and Yahoo
  Finance option-page URLs.
- Preserved raw option-chain integrity: no bid/ask rows, option positions,
  lifecycle rows, broker writes, orders, provider secrets, recommendation
  decisions, or evidence gates were changed.

Verification:

- `python -m target_opportunity_monitor validate-options-chain-backfill`
  reported valid option-chain backfill rows `39`, blank placeholders `2`, and
  invalid rows `0`.
- `python -m target_opportunity_monitor option-chain-coverage-plan` reported
  coverage status `complete`, effective chain coverage `47/47`, raw chain
  coverage `47/50`, missing tickers `none`, non-actionable chain tickers
  `BIL, SIVE, SOI`, and chain availability `SIVE unavailable -
  no_listed_options, SOI unavailable - no_listed_options`.
- `python tests\test_phase12b_options_chain.py` passed: 29 tests.
- `python tests\test_phase14e_activation_api.py` passed: 12 tests.
- `python tests\test_phase14f_signal_coverage_api.py` passed: 9 tests.
- `python tools\run_tests.py smoke --timeout-per-file 180` passed: 14 files.
- `python -m target_opportunity_monitor status` reported TOM loop `running`,
  loop health `healthy`, intraday health `healthy`, pending notifications `0`,
  options provider readiness `ready`, missing chain tickers `none`, broader
  coverage status `complete`, and option-chain availability `BIL unavailable -
  not_options_strategy_candidate, SIVE unavailable - no_listed_options, SOI
  unavailable - no_listed_options`.
- `python -m target_opportunity_monitor serve-api --once-smoke-test` passed
  with health/status `200`.
- `npm run build` in `F:\Investments\tom-ui` passed.

Still open:

- `SIVE` and `SOI` still need real numeric short-interest rows through
  `provider_export`, `exchange_manual`, or `broker_manual`.
- `SIVE` and `SOI` still need source-backed news/catalyst rows with provider or
  source numeric evidence.
- Option-position/lifecycle source data, Phase 10D evidence maturity, full
  trader-commentary capture opt-in/setup, and optional provider-native news
  redundancy remain separate open items.

### 2026-06-15 - SIVE source-backed analyst-target valuation fallback

Completed:

- Added guarded foreign-equity analyst target intake at
  `data/research/source_exports/foreign_equity_analyst_targets.csv`.
- Added validation for analyst target rows, including required source/source
  URL, positive target values, date parsing, stale-date rejection, supported
  foreign-equity identity, and scale sanity against TOM's latest local price.
- Extended `foreign-equity-source-status`, API serialization, CLI template
  export, and the `/research` Foreign Equity Sources panel to show analyst
  target path, counts, valid tickers, and ticker-level analyst target evidence.
- Extended `compute-targets` so source-backed foreign equities can use
  `source_backed_analyst_target` only when normal valuation methods fail and a
  valid analyst-target row exists.
- Staged the SIVE analyst target row from the local yfinance/Yahoo Finance
  provider-export path: target mean `9.8` SEK, low `6.0`, high `19.0`, analyst
  count `4`, source URL `https://finance.yahoo.com/quote/SIVE.ST/analysis/`.
- Recomputed SIVE target, score, and alerts without adding short-interest,
  news/catalyst, option-chain, account, recommendation, broker, or order state.

Verification:

- `python -m py_compile src\target_opportunity_monitor\valuation.py src\target_opportunity_monitor\foreign_equity_sources.py src\target_opportunity_monitor\config.py src\target_opportunity_monitor\api_server.py src\target_opportunity_monitor\cli.py`
  passed.
- `python tests\test_phase13e_foreign_equity_sources.py` passed: 6 tests.
- `python tests\test_phase13c_research_recommendations.py` passed: 19 tests.
- `python tests\test_phase14c_research_api.py` passed: 19 tests.
- `python tools\run_tests.py smoke --timeout-per-file 180` passed: 14 files.
- `python -m target_opportunity_monitor foreign-equity-source-status` reported
  `3` valid fundamental rows, `2` valid estimate rows, `1` valid analyst target
  row, valid analyst target tickers `SIVE`, source-required tickers `none`, and
  both `SIVE` and `SOI` ready with target/score.
- `python -m target_opportunity_monitor compute-targets --ticker SIVE` reported
  `computed=1`, target `9.8000`, methods `1`, and warnings
  `missing_eps_estimate`, `source_backed_analyst_target_only`,
  `loss_making_foreign_equity_valuation`.
- `python -m target_opportunity_monitor compute-scores --ticker SIVE --asset-type equity`
  reported `computed=1` with opportunity score `32.58` and warnings
  `insufficient_growth_history`, `missing_revision_data`.
- `python -m target_opportunity_monitor compute-alerts --ticker SIVE --asset-type equity`
  reported `evaluated=1`, `stored=1`, `alerts=1`, and alert `risk_warning`.
- `python -m target_opportunity_monitor research-ticker-status --ticker SIVE`
  reported `Target: yes`, `Score: yes`, and readiness blockers `none`.
- `python -m target_opportunity_monitor status` reported TOM loop `running`,
  loop health `healthy`, intraday health `healthy`, pending notifications `0`,
  target rows `130`, score rows `130`, alert rows `130`, news/catalyst
  source-backed tickers `31/33`, short-interest source-backed tickers `31/33`,
  and option-chain effective coverage `47/49` before the later SIVE/SOI
  non-actionable option-chain decisions.
- `python -m target_opportunity_monitor serve-api --once-smoke-test` passed with
  health/status `200`.
- `npm run build` in `F:\Investments\tom-ui` passed.

Still open:

- `SIVE` and `SOI` still need real numeric short-interest rows through
  `provider_export`, `exchange_manual`, or `broker_manual`.
- `SIVE` and `SOI` still need source-backed news/catalyst rows with provider or
  source numeric evidence.
- `SIVE` and `SOI` still needed real option-chain rows or source-backed
  non-actionable chain availability decisions at this point; this was closed in
  the later SIVE/SOI option-chain availability entry.
- Option-position/lifecycle source data, Phase 10D evidence maturity, full
  trader-commentary capture opt-in/setup, and optional provider-native news
  redundancy remain separate open items.

### 2026-06-15 - SIVE/SOI source-backed foreign-equity rows and verified blockers

Completed:

- Staged and confirmed source-backed foreign-equity fundamentals and forward EPS
  estimates for `SIVE` and `SOI`.
- Imported `SIVE` official 2025 annual-report fundamentals, `SIVE` Q1 2026
  interim fundamentals, and `SOI` FY26 official-result fundamentals through the
  guarded `apply-foreign-equity-source --confirm` path.
- Imported `SIVE` and `SOI` forward EPS estimate rows from the local yfinance
  provider export path, with Yahoo Finance analysis URLs retained in the source
  CSVs.
- Recomputed fundamental benchmarks, targets, scores, and alerts for the
  affected tickers.
- Preserved source-data boundaries: no short-interest row, news/catalyst row, or
  option-chain non-actionable decision was added without usable source evidence.

Verification:

- `python -m target_opportunity_monitor foreign-equity-source-status` reported
  `3` valid fundamental rows, `2` valid estimate rows, source-required tickers
  `none`, `Apply ready: True`, and blocked reason `none`.
- `python -m target_opportunity_monitor apply-foreign-equity-source` dry-ran
  cleanly; `python -m target_opportunity_monitor apply-foreign-equity-source --confirm`
  imported `3` fundamental rows and `2` estimate rows for `SIVE, SOI`.
- `python -m target_opportunity_monitor compute-targets --ticker SOI` computed
  a target; `python -m target_opportunity_monitor compute-scores --ticker SOI --asset-type equity`
  computed a score with warnings `insufficient_growth_history,
  missing_revision_data`.
- `python -m target_opportunity_monitor research-ticker-status --ticker SOI`
  reported readiness blockers `none`.
- `python -m target_opportunity_monitor compute-targets --ticker SIVE` remained
  skipped with `missing_eps_estimate, insufficient_valuation_methods`; TOM has a
  source-backed EPS row for `SIVE`, but the current forward EPS is negative and
  not usable by the positive-EPS valuation method.
- `python -m target_opportunity_monitor research-ticker-status --ticker SIVE`
  reported `Fundamental rows: 2`, `Forward EPS estimate: yes`, and remaining
  blockers `missing_target, missing_score`.
- `python -m target_opportunity_monitor short-interest-missing-coverage-plan`
  still reported source-backed coverage `31/33`, missing source tickers
  `SIVE, SOI`, and no valid missing rows.
- `python -m target_opportunity_monitor fetch-news-catalyst-sources --provider all --ticker SIVE --coverage-mode missing --use-cache`
  and the same command for `SOI` stored no numeric rows; provider warnings were
  rate-limit, missing-key, headline-only, plan-limited, or no-company-news
  blockers.
- `python -m target_opportunity_monitor option-chain-coverage-plan` still
  reported effective coverage `47/49`, missing tickers `SIVE, SOI`, provider
  blocked reason `missing_option_chain`, and BIL excluded by the existing
  non-actionable decision.
- `python -m py_compile src\target_opportunity_monitor\fundamental_data.py src\target_opportunity_monitor\research_tickers.py src\target_opportunity_monitor\api_server.py src\target_opportunity_monitor\cli.py`
  passed.
- `python tests\test_phase13e_foreign_equity_sources.py` passed: 3 tests.
- `python tests\test_phase13c_research_recommendations.py` passed: 19 tests.
- `python tests\test_phase13d_research_preparation.py` passed: 11 tests.
- `python tests\test_phase14c_research_api.py` passed: 19 tests.
- `python tests\test_phase10g_short_interest.py` passed: 12 tests.
- `python tests\test_phase10e_news_catalysts.py` passed: 30 tests.
- `python tests\test_phase12b_options_chain.py` passed: 29 tests.
- `python tools\run_tests.py smoke --timeout-per-file 180` passed: 14 files.
- `python -m target_opportunity_monitor serve-api --once-smoke-test` passed with
  health/status `200`.
- `npm run build` in `F:\Investments\tom-ui` passed.

Still open:

- `SIVE` target and score require source-backed usable valuation inputs or a
  validated valuation method for loss-making foreign equities; do not force a
  score from negative forward EPS and negative/insufficient valuation methods.
- `SIVE` and `SOI` still need real numeric short-interest rows through
  `provider_export`, `exchange_manual`, or `broker_manual`.
- `SIVE` and `SOI` still need source-backed news/catalyst rows with provider or
  source numeric evidence.
- `SIVE` and `SOI` still need real option-chain rows or source-backed
  non-actionable chain availability decisions.
- Option-position/lifecycle source data, Phase 10D evidence maturity, full
  trader-commentary capture opt-in/setup, and optional provider-native news
  redundancy remain separate open items.

### 2026-06-15 - Foreign-equity source intake and SIVE/SOI coverage diagnostics

Completed:

- Added guarded foreign-equity fundamentals/EPS source intake for `SIVE` and
  `SOI` through `foreign-equity-source-status`,
  `export-foreign-equity-source-template`, and
  `apply-foreign-equity-source --confirm`.
- Added source templates at
  `data/research/source_exports/foreign_equity_fundamentals.csv` and
  `data/research/source_exports/foreign_equity_estimates.csv`.
- Added read-only/confirmation-gated API coverage:
  `GET /api/research/foreign-equity-source-status`,
  `POST /api/research/foreign-equity-source-template`, and
  `POST /api/research/foreign-equity-source-apply`.
- Enhanced `/research` with a Foreign Equity Source Coverage panel showing
  valid/invalid rows, source-required tickers, blockers, file paths, and dry-run
  or confirmed apply controls.
- Preserved existing boundaries: no recommendation was approved or promoted, no
  source rows were fabricated, and no broker/account/order/provider-secret or
  evidence-gate state was changed.

Verification:

- `python -m py_compile src\target_opportunity_monitor\foreign_equity_sources.py src\target_opportunity_monitor\fundamental_data.py src\target_opportunity_monitor\research_tickers.py src\target_opportunity_monitor\api_server.py src\target_opportunity_monitor\cli.py src\target_opportunity_monitor\config.py`
  passed.
- `python tests\test_phase13c_research_recommendations.py` passed: 19 tests.
- `python tests\test_phase13d_research_preparation.py` passed: 11 tests.
- `python tests\test_phase13e_foreign_equity_sources.py` passed: 3 tests.
- `python tests\test_phase14c_research_api.py` passed: 19 tests.
- `python tools\run_tests.py smoke --timeout-per-file 180` passed: 14 files.
- `python -m target_opportunity_monitor serve-api --once-smoke-test` passed
  with health/status `200`.
- `npm run build` in `F:\Investments\tom-ui` passed.
- `foreign-equity-source-status` reported `0` valid fundamental rows, `0` valid
  estimate rows, source-required tickers `SIVE, SOI`, `Apply ready: False`, and
  blocked reason `no_valid_foreign_equity_source_rows`.
- `research-ticker-status --ticker SIVE` and `--ticker SOI` confirmed both
  tickers are scoreable foreign equities with identity, price, range snapshot,
  sector/industry, and benchmark comparison, but still block on
  `missing_fundamentals`, `missing_forward_eps_estimate`,
  `missing_usable_fundamentals`, `missing_target`, and `missing_score`.
- `short-interest-missing-coverage-plan` reported source-backed coverage
  `31/33`, missing source tickers `SIVE, SOI`, and no valid missing rows.
- `option-chain-coverage-plan` reported effective coverage `47/49`, missing
  tickers `SIVE, SOI`, and BIL still excluded by the source-backed
  non-actionable decision.
- `news-catalyst-source-status --provider-upgrade-only` reported
  source-backed ticker coverage `31/33` with missing source-backed tickers
  `SIVE, SOI`.
- `status` reported TOM loop `running`, TOM loop health `healthy`, intraday
  health `healthy`, pending notifications `0`, research recommendation pending
  `0`, and research preparation manual blockers `0`.

Still open:

- Real source-backed SIVE/SOI fundamentals and EPS estimate rows.
- Real source-backed SIVE/SOI short-interest rows, news/catalyst rows, and
  option-chain rows or source-backed non-actionable availability decisions.
- Option-position/lifecycle source data, Phase 10D evidence maturity, full
  trader-commentary capture opt-in/setup, and optional provider-native news
  redundancy.

### 2026-06-15 - Safe research context-row cleanup

Completed:

- Ran the confirmed research preparation cleanup only for `SOXL` and `KORU`,
  which were already scoreable ETF assets after the ETF source-preparation
  closure.
- Ignored recommendation IDs `1` and `7` as already-scoreable context rows.
- Preserved the strict gates: no recommendation was approved or promoted, no
  ticker was applied, no source rows were fabricated, and no broker/account,
  option-position, provider-secret, score, or evidence-gate state was changed.

Verification:

- Preflight `research-recommendation-status` reported 325 candidates, 57
  pending, 0 approved-not-promoted, 40 promoted, and 228 ignored.
- Preflight `research-preparation-run --source pending --action scan` reported
  57 pending rows across 6 groups: `SOXL` and `KORU` as
  `prepared_already_scoreable`, plus `SIVE`, `SIVEF`, `SLOIF`, and `SOI` as
  `identity_required`.
- `python -m target_opportunity_monitor research-preparation-run --source pending --action ignore_already_scoreable --ticker SOXL --ticker KORU --confirm`
  ignored 2 context rows and updated recommendation IDs `1` and `7`; applied
  tickers remained `0`.
- Post-check `research-recommendation-status` reported 55 pending, 0
  approved-not-promoted, 40 promoted, and 230 ignored.
- Post-check `research-preparation-run --source pending --action scan` reported
  55 pending rows across 4 groups, all `identity_required`: `SIVE`, `SIVEF`,
  `SLOIF`, and `SOI`.
- `python -m target_opportunity_monitor status` reported TOM loop `running`,
  TOM loop health `healthy`, intraday health `healthy`, pending notifications
  `0`, and research recommendation pending `55`.
- `python -m target_opportunity_monitor serve-api --once-smoke-test` passed.
- `npm run build` in `F:\Investments\tom-ui` passed.

Still open:

- Source-backed identity and metadata decisions for `SIVE`, `SIVEF`, `SLOIF`,
  and `SOI`.
- Option-position/lifecycle source data, Phase 10D evidence maturity, full
  trader-commentary capture opt-in/setup, and optional provider-native news
  redundancy.

### 2026-06-15 - SOXL/KORU ETF source preparation closure

Completed:

- Hardened the Direxion ETF evidence parser so split percentage tokens on the
  current official fund pages are recognized as index top-holding weights.
- Confirmed the allowlisted Direxion source-discovery path for `SOXL` and
  `KORU`, staged source-backed ETF NAV rows plus 10 index top-holding reference
  rows per ticker, loaded those rows, recomputed ETF readiness, and applied both
  tickers to scoreable status through confirmed research preparation.
- Kept recommendation review separate: no recommendation was approved, rejected,
  ignored, or promoted by the source-preparation run.
- Checked option-chain completion for long-call review through yfinance; both
  tickers exposed expirations/strikes but no usable bid/ask rows, so long-call
  review remains blocked with `missing_call_option_chain` instead of fabricated
  call quotes.

Verification:

- `python -m py_compile src\target_opportunity_monitor\research_preparation.py src\target_opportunity_monitor\research_tickers.py src\target_opportunity_monitor\api_server.py`
  passed.
- `python tests\test_phase13d_research_preparation.py` passed: 8 tests.
- `python tests\test_phase13c_research_recommendations.py` passed: 13 tests.
- `python tests\test_phase14c_research_api.py` passed: 16 tests.
- `python tools\run_tests.py smoke --timeout-per-file 180` passed: 14 files.
- `python -m target_opportunity_monitor research-preparation-run --source pending --action discover_sources --ticker SOXL --ticker KORU`
  discovered both tickers with warnings only:
  `direxion_index_holdings_used_as_reference`.
- `python -m target_opportunity_monitor research-preparation-run --source pending --action stage_source_rows --ticker SOXL --ticker KORU --confirm`
  staged 22 rows: one ETF NAV row and 10 ETF holding rows per ticker.
- `python -m target_opportunity_monitor research-preparation-run --source pending --action load_staged_sources --ticker SOXL --ticker KORU --confirm`
  loaded 648 ETF source rows.
- `python -m target_opportunity_monitor research-preparation-run --source pending --action compute_ready --ticker SOXL --ticker KORU --confirm`
  reported `ready_to_apply=2` and manual blockers `0`.
- `python -m target_opportunity_monitor research-preparation-run --source pending --action prepare_ready --ticker SOXL --ticker KORU --confirm`
  applied both tickers and updated no recommendation IDs.
- `research-ticker-status --ticker SOXL` and `research-ticker-status --ticker KORU`
  both report asset role `scoreable`, asset type `etf`, ETF feature `yes`, ETF
  NAV `yes`, target `yes`, score `yes`, range snapshot `yes`, and option chain
  `yes`; remaining warnings are stale/data-quality warnings, not apply blockers.
- `etf-strategy-review --ticker SOXL` and `etf-strategy-review --ticker KORU`
  report shares and sell cash-secured put review available, long call blocked
  by `missing_call_option_chain`, and overall decision `wait_no_clean_entry`.
- `python -m target_opportunity_monitor research-preparation-run --source pending --action scan`
  reports 57 pending rows across 6 groups, with `SOXL` and `KORU` as
  `prepared_already_scoreable` and `SIVE`, `SIVEF`, `SLOIF`, and `SOI` as
  `identity_required`.
- `python -m target_opportunity_monitor status` reports TOM loop `running`,
  TOM loop health `healthy`, intraday health `healthy`, scoreable assets `48`,
  short-interest source-backed tickers `31/31`, and pending notifications `0`.
- `python -m target_opportunity_monitor serve-api --once-smoke-test` passed.
- `npm run build` in `F:\Investments\tom-ui` passed.

Still open:

- Explicit review decisions for the remaining 57 pending research rows.
- Source-backed identity and metadata decisions for `SIVE`, `SIVEF`, `SLOIF`,
  and `SOI`.
- Long-call strategy review for `SOXL` and `KORU` until a source provides valid
  call bid/ask rows.
- Option-position/lifecycle source data, Phase 10D evidence maturity, and
  full trader-commentary capture opt-in/setup.

### 2026-06-15 - Max research preparation automation

Completed:

- Extended the existing research preparation service with `discover_sources`,
  `stage_source_rows`, `load_staged_sources`, `compute_ready`, ticker filters,
  source-candidate diagnostics, staged-row diagnostics, automation stages, and
  explicit cannot-automate reasons.
- Added an allowlisted Direxion ETF source adapter for `SOXL` and `KORU`.
  The adapter can discover official source evidence and stages only validated
  ETF NAV/holding rows with confirmation; ambiguous identity rows remain manual.
- Updated `/api/research/preparation/status`,
  `/api/research/preparation/run`, `research-preparation-run`, and `/research`
  so operators can scan, discover, stage, load, recompute, prepare ready
  tickers, ignore already-scoreable context, or run all safe steps.
- Preserved gates: no auto-approval, no auto-promotion, no broker writes, no
  orders, no fabricated identity/source rows, and no evidence-gate weakening.

Verification:

- `python -m py_compile src\target_opportunity_monitor\research_preparation.py src\target_opportunity_monitor\research_tickers.py src\target_opportunity_monitor\api_server.py src\target_opportunity_monitor\cli.py`
  passed.
- `python tests\test_phase13d_research_preparation.py` passed: 7 tests.
- `python tests\test_phase14c_research_api.py` passed: 16 tests.
- `python tests\test_phase13c_research_recommendations.py` passed: 13 tests.
- `npm run build` in `F:\Investments\tom-ui` passed.
- `python -m target_opportunity_monitor research-preparation-run --source pending --action scan`
  reported 57 pending rows across 6 groups; `SOXL` and `KORU` now show
  `automation=source_discovery_available`, while `SIVE`, `SIVEF`, `SLOIF`, and
  `SOI` remain `source_backed_identity_required`.
- `python -m target_opportunity_monitor research-preparation-run --source pending --action discover_sources --ticker SOXL --ticker KORU`
  discovered both ETF source adapters read-only and reported live blockers
  `direxion_holdings_not_found`; no source rows were staged.
- `python -m target_opportunity_monitor serve-api --once-smoke-test` passed.

### 2026-06-14 - ETF research promotion path and strategy review

Completed:

- Added an ETF branch to research ticker planning/apply/status. Equity research
  still requires CIK/company metadata; ETF research uses `asset_type=etf` and
  does not require CIK.
- Restricted ETF promotion to existing active ETF reference assets with stored
  ETF readiness: price, ETF feature/NAV/holdings, target, score, range snapshot,
  and option-chain rows.
- Added read-only ETF strategy review through CLI/API/UI. The review compares
  ETF shares, long calls from real call-chain rows, and cash-secured put income
  from existing sell-put reviews.
- Updated recommendation promotion preflight so ETF-path recommendations use the
  ETF path instead of the equity CIK path.
- Extended `/research` with an Equity/ETF path selector and ETF strategy review
  panel. Existing approval, apply, and promotion confirmation gates remain in
  place.

Live verification:

- `python -m target_opportunity_monitor research-ticker-plan --ticker SOXL --asset-type etf`
  reported `Research path: etf`, `Asset type: etf`, existing asset role
  `commentary_validation`, blocked reason `etf_readiness_required`, and
  readiness blockers `missing_etf_feature`, `missing_target`, `missing_score`,
  and `missing_range_snapshot`. It no longer reports a missing CIK blocker.
- `python -m target_opportunity_monitor research-ticker-plan --ticker XLV --asset-type etf`
  reported `Research path: etf`, blocked reason `etf_readiness_required`, and
  readiness blockers `missing_etf_feature`, `missing_target`, `missing_score`,
  `missing_range_snapshot`, and `missing_option_chain`. It no longer reports a
  missing CIK blocker.
- `python -m target_opportunity_monitor etf-strategy-review --ticker SOXL`
  reported `Decision: wait_no_clean_entry`; ETF shares were blocked by missing
  ETF data/target/score/range, long call was blocked by
  `missing_call_option_chain`, and sell cash-secured put was available from
  stored put-review rows but remained a read-only wait/no-clean-entry review.
- `python -m target_opportunity_monitor status` passed with required tables
  `56/56`, TOM loop `running/healthy`, intraday health `healthy`, pending
  notifications `0`, research recommendations still `313` pending, and no
  recommendation approval/promotion state changes.

Regression/verification commands passed:

```powershell
python -m py_compile src\target_opportunity_monitor\research_tickers.py src\target_opportunity_monitor\research_recommendations.py src\target_opportunity_monitor\api_server.py src\target_opportunity_monitor\options.py
python tests\test_phase13c_research_recommendations.py
python tests\test_phase14c_research_api.py
python tests\test_phase12a_options.py
python tests\test_phase12b_options_chain.py
python tools\run_tests.py smoke --timeout-per-file 180
python -m target_opportunity_monitor serve-api --once-smoke-test
npm run build
```

Results:

- `test_phase13c_research_recommendations.py`: 13 tests passed.
- `test_phase14c_research_api.py`: 11 tests passed.
- `test_phase12a_options.py`: 6 tests passed.
- `test_phase12b_options_chain.py`: 28 tests passed.
- Smoke suite: 14 files passed in 56.57s.
- API smoke: health endpoint 200 `ok=True`; status endpoint 200 `ok=True`.
- `tom-ui` TypeScript/Vite production build passed.

Still open:

- Live research recommendation review decisions.
- ETF readiness/source data for ETF recommendations whose strategy review is
  blocked by missing ETF NAV/holdings/target/score/range or missing call-chain
  rows.
- Real option-position rows and option lifecycle activation.
- Phase 10D analyst-revision evidence gate.
- Optional full trader-commentary capture setup.

### 2026-06-14 - Option-chain availability UI/API presentation

Completed:

- Added stored-evidence option-chain availability statuses for every ticker in
  the options fetch universe: `available`, `unavailable`, or `missing`.
- Extended `GET /api/backfills/options/status` with `availability_statuses` and
  `/api/coverage/status` account/options details with the same compact
  availability rows.
- Updated `/backfills` with an Option-Chain Availability table and `/coverage`
  with a compact account/options availability view.
- Updated `option-chain-coverage-plan`, `status`, reports, and dashboard data
  to include `Options chain availability: BIL unavailable -
  not_options_strategy_candidate`.

Verification:

```text
python -m py_compile src\target_opportunity_monitor\options.py src\target_opportunity_monitor\api_server.py src\target_opportunity_monitor\signal_coverage.py src\target_opportunity_monitor\cli.py src\target_opportunity_monitor\reporting.py src\target_opportunity_monitor\dashboard.py
passed.

python tests\test_phase12b_options_chain.py
28 tests passed.

python tests\test_phase14e_activation_api.py
12 tests passed.

python tests\test_phase14f_signal_coverage_api.py
5 tests passed.

python tests\test_phase8a_dashboard.py
4 tests passed.

python tools\run_tests.py smoke --timeout-per-file 180
14 files passed in 56.42s.

python -m target_opportunity_monitor option-chain-coverage-plan
coverage status complete; current/effective chain coverage 18/18; raw chain
coverage 18/19; raw missing ticker BIL; non-actionable chain tickers BIL;
valid non-actionable decisions 1; invalid decisions 0; blank placeholders 0;
notes non_actionable_option_chain_excluded; options chain availability BIL
unavailable - not_options_strategy_candidate; warnings none.

python -m target_opportunity_monitor status
required tables present 56/56; TOM loop running/healthy; intraday health
healthy; pending notifications 0; failed deliveries 0; options provider
readiness ready; options missing chain tickers none; raw missing chain tickers
BIL; options non-actionable chain tickers BIL; broader coverage complete 18/18;
broader raw coverage 18/19; options chain availability BIL unavailable -
not_options_strategy_candidate; account option readiness remains
source_data_required with option_positions=0 and option_lifecycle=0.

python -m target_opportunity_monitor serve-api --once-smoke-test
health endpoint 200 ok=True; status endpoint 200 ok=True.

npm run build
TypeScript and Vite production build passed.
```

Notes:

- Availability is derived only from stored TOM chain rows and validated
  source-backed non-actionable decisions; no fresh external scrape or provider
  dependency was added.
- No BIL bid/ask rows, option positions, lifecycle rows, broker writes, orders,
  provider keys, research approvals, score gates, or evidence gates were
  changed.
- Option-position source data, option lifecycle activation, short-interest
  missing rows, news/catalyst provider-native rows, research review,
  trader-commentary optional capture/aliases, and Phase 10D evidence gates
  remain open.

### 2026-06-14 - BIL option-chain non-actionable coverage closure

Completed:

- Replaced the blank `BIL` placeholder in
  `data/options/source_exports/options_chain_non_actionable.csv` with a
  source-backed non-actionable decision.
- Used Nasdaq's BIL option-chain page as the source URL after verifying it
  reported the BIL option chain as currently unavailable on 2026-06-14.
- Marked only the effective option-chain denominator gap resolved. No BIL
  option-chain bid/ask rows, option-position rows, or option-lifecycle rows
  were created.
- Updated `DOCS/cross-phase-gap-fix-plan.md` and `execution_plan.md` so BIL is
  no longer listed as an open provider/export option-chain gap.

Verification:

```text
python -m target_opportunity_monitor validate-options-chain-backfill
valid rows 4; blank placeholders 2; invalid rows 0; projected chain coverage
18/19; apply ready False; blocked reason
projected_option_chain_coverage_does_not_improve.

python -m target_opportunity_monitor option-chain-coverage-plan
coverage status complete; current/effective chain coverage 18/18; raw chain
coverage 18/19; raw missing ticker BIL; non-actionable chain tickers BIL;
valid non-actionable decisions 1; invalid decisions 0; blank placeholders 0;
notes non_actionable_option_chain_excluded; warnings none.

python tests\test_phase12b_options_chain.py
27 tests passed.

python tests\test_phase14e_activation_api.py
11 tests passed.

python tests\test_phase14f_signal_coverage_api.py
5 tests passed.

python tools\run_tests.py smoke --timeout-per-file 180
14 files passed in 57.89s.

python -m target_opportunity_monitor status
required tables present 56/56; TOM loop running/healthy; intraday health
healthy; pending notifications 0; failed deliveries 0; options provider
readiness ready; options missing chain tickers none; raw missing chain tickers
BIL; options non-actionable chain tickers BIL; broader coverage status
complete; broader chain coverage 18/18; broader raw chain coverage 18/19;
broader coverage notes non_actionable_option_chain_excluded; account option
readiness remains source_data_required with option_positions=0 and
option_lifecycle=0.

python -m target_opportunity_monitor serve-api --once-smoke-test
health endpoint 200 ok=True; status endpoint 200 ok=True.

npm run build
TypeScript and Vite production build passed.
```

Notes:

- The non-actionable decision is reversible if a real tradable BIL option chain
  is later supplied through source-backed bid/ask rows.
- Option-position source data, option lifecycle activation, short-interest
  missing rows, news/catalyst provider-native rows, research review,
  trader-commentary optional capture/aliases, and Phase 10D evidence gates
  remain open.
- No broker writes, order placement, provider keys, fabricated source rows,
  research approvals, score gates, or evidence gates were changed.

### 2026-06-14 - Option-position readiness diagnostics and lifecycle preview

Completed:

- Added structured option-position readiness diagnostics to account context
  status, including current rows, staged valid/invalid/blank rows, projected
  option/lifecycle rows, blockers, append/template paths, required fields, and
  recommended operator actions.
- Extended `GET /api/account/context-status`, `POST /api/account/append-row`,
  `/api/coverage/status`, `account-context-status`, `options-lifecycle-status`,
  `status`, report summaries, dashboard data, and `/activation`.
- Added an `/activation` Option Position Readiness panel while keeping validate,
  preview, dry-run apply, and confirmed apply separate.
- Kept account apply semantics strict: no valid option rows means lifecycle
  remains blocked, and staged rows are not imported until confirmed apply.

Verification:

```text
python -m py_compile src\target_opportunity_monitor\account.py src\target_opportunity_monitor\api_server.py src\target_opportunity_monitor\cli.py src\target_opportunity_monitor\signal_coverage.py src\target_opportunity_monitor\reporting.py src\target_opportunity_monitor\dashboard.py src\target_opportunity_monitor\options.py
passed.

python tests\test_phase12f_options_lifecycle.py
5 tests passed.

python tests\test_phase12f1_account_context.py
10 tests passed.

python tests\test_phase14e_activation_api.py
11 tests passed.

python tests\test_phase14f_signal_coverage_api.py
5 tests passed.

python tests\test_phase8a_dashboard.py
4 tests passed.

python tools\run_tests.py smoke --timeout-per-file 180
14 files passed in 53.96s.

python -m target_opportunity_monitor account-context-status
activation partial; portfolio rows 2; cash rows 1; option rows 0; lifecycle
rows 0; apply ready True; option readiness source_data_required; staged option
rows valid=0, invalid=0, blank=0; projected option/lifecycle rows 0/0;
blockers empty_options_positions, no_option_lifecycle_rows,
no_valid_option_position_rows.

python -m target_opportunity_monitor options-lifecycle-status
lifecycle readiness source_data_required; lifecycle blockers
empty_options_positions, no_option_lifecycle_rows.

python -m target_opportunity_monitor status
required tables present 56/56; TOM loop running/healthy; intraday health
healthy; pending notifications 0; failed deliveries 0; account option
readiness source_data_required; staged option rows valid=0, invalid=0, blank=0.

python -m target_opportunity_monitor serve-api --once-smoke-test
health endpoint 200 ok=True; status endpoint 200 ok=True.

npm run build
TypeScript and Vite production build passed.
```

Notes:

- No real option-position rows were supplied or fabricated; option lifecycle
  remains source-data-gated.
- No broker writes, order placement, provider keys, option-chain quotes,
  short-interest rows, news/catalyst rows, research approvals, score gates, or
  evidence gates were changed.

### 2026-06-14 - Durable TOM loop recovery

Completed:

- Cleared the live stale TOM loop lock with the existing
  `tom-loop-stop` recovery command.
- Verified the loop moved from `stale_lock` / `blocked` to `stopped` with
  `recovery_status=stopped_start_available`.
- Ran one safe validation cycle with
  `tom-loop-once --mode auto --deliver --channel file`; the cycle completed
  `ok` with one `daily-retry-check` step and zero warnings.
- Started the durable hidden local TOM loop with `tom-loop-start --mode auto
  --deliver --channel file`; the background Python process PID is `8152`.

Verification:

```text
Preflight tom-loop-status
status stale_lock; health blocked; active False; heartbeat age seconds
38447.173637; recovery_status stale_lock_clearable; actions clear_stale_lock,
start_loop, run_once; pending notifications 0; failed deliveries 0.

Preflight intraday-health-check
status healthy; market session weekend; blockers none; warnings none; notes
off_hours_quote_staleness_expected and
off_hours_intraday_cycle_staleness_expected.

python -m target_opportunity_monitor tom-loop-stop
Stale loop lock cleared; no active loop was running. Status stopped.

Post-clear tom-loop-status
status stopped; health stopped; recovery_status stopped_start_available;
actions start_loop, run_once; no stale_loop_lock warning.

python -m target_opportunity_monitor tom-loop-once --mode auto --deliver --channel file
manual_ops_cycle status ok; requested_mode daily-retry; selected_mode
daily-retry; steps 1; warnings 0; deliver True; channel file.

Start-Process durable loop
started hidden python process PID 8152.

Post-start tom-loop-status
status running; health healthy; active True; PID 8152; heartbeat age seconds
20.445841; recovery_status active_loop_running; actions monitor_loop; pending
notifications 0; failed deliveries 0.

Post-start tom-loop-health
health healthy; loop status running; active True; pending notifications 0;
failed deliveries 0.

python -m target_opportunity_monitor intraday-health-check
status healthy; market session weekend; warnings none; blockers none.

python -m target_opportunity_monitor status
required tables present 56/56; TOM loop running; TOM loop health healthy;
recovery status active_loop_running; recovery actions monitor_loop; pending
notifications 0; failed deliveries 0.

python -m target_opportunity_monitor serve-api --once-smoke-test
health endpoint 200 ok=True; status endpoint 200 ok=True.
```

Notes:

- No broker writes, order placement, provider keys, fabricated source rows,
  option positions, research approvals, score gates, or evidence gates were
  changed.
- Scheduler remains disabled by choice; the durable local TOM loop is the
  active operational path.
- Account/options source-data, BIL option-chain, short-interest,
  news/provider-native, research-review, disabled-capture, and Phase 10D
  evidence gaps remain open.

### 2026-06-14 - TOM loop stale-lock recovery UX and diagnostics

Completed:

- Added an explicit read-only recovery plan to TOM loop snapshots:
  `recovery_status`, `recommended_actions`, `clear_stale_lock_command`,
  `run_once_command`, `heartbeat_age_seconds`, `stale_lock`, and
  `recovery_notes`.
- Updated `tom-loop-status`, `tom-loop-health`, `status`, report text,
  dashboard data, `/api/loop/status`, and `/api/loop/health` to expose
  stale-lock recovery guidance without hiding the blocked loop state.
- Enhanced `/loop` with a stale-lock recovery panel and an explicit
  confirmation-gated `Clear Stale Lock` action backed by the existing
  `POST /api/loop/stop` endpoint.
- Kept intraday market-session health semantics unchanged and did not clear
  the live stale lock, start the live loop, or run live recovery actions.

Verification:

```text
python -m py_compile src\target_opportunity_monitor\tom_loop.py src\target_opportunity_monitor\api_server.py src\target_opportunity_monitor\cli.py src\target_opportunity_monitor\reporting.py src\target_opportunity_monitor\dashboard.py
passed.

python tests\test_phase11e_tom_loop.py
7 tests passed.

python tests\test_phase11e_loop_api.py
6 tests passed.

python tests\test_phase14d_ops_api.py
8 tests passed.

python tests\test_phase8a_dashboard.py
4 tests passed.

python tools\run_tests.py smoke --timeout-per-file 180
14 files passed in 55.21s.

python -m target_opportunity_monitor tom-loop-status
status stale_lock; health blocked; heartbeat age seconds 37886.104272;
recovery_status stale_lock_clearable; actions clear_stale_lock, start_loop,
run_once; warnings stale_loop_lock; notes off_hours_quote_staleness_expected
and off_hours_intraday_cycle_staleness_expected.

python -m target_opportunity_monitor tom-loop-health
health blocked; loop status stale_lock; recovery_status stale_lock_clearable;
actions clear_stale_lock, start_loop, run_once.

python -m target_opportunity_monitor intraday-health-check
status healthy; market session weekend; warnings none; blockers none; notes
off_hours_quote_staleness_expected and
off_hours_intraday_cycle_staleness_expected.

python -m target_opportunity_monitor status
required tables present 56/56; TOM loop stale_lock; loop health blocked;
heartbeat age seconds 37886.136971; recovery status stale_lock_clearable;
recovery actions clear_stale_lock, start_loop, run_once; pending notifications
0.

python -m target_opportunity_monitor serve-api --once-smoke-test
health endpoint 200 ok=True; status endpoint 200 ok=True.

npm run build
TypeScript and Vite production build passed.
```

Notes:

- No broker writes, order placement, provider keys, source rows, option
  positions, option-chain quotes, short-interest rows, news/catalyst rows,
  analyst evidence, research approvals, score gates, or evidence gates were
  changed.
- Scheduler remains disabled by choice. The local stale lock remains a live
  operator action until the user explicitly clears or restarts the loop.

### 2026-06-14 - Research recommendation triage and review workflow

Completed:

- Added `GET /api/research/recommendations/triage` for read-only grouped
  pending recommendation triage by ticker, including duplicate counts,
  representative IDs, warnings, blockers, classifications, and recommended
  operator actions.
- Added `POST /api/research/recommendations/bulk-status`, confirmation-gated,
  for batch `approved`, `ignored`, `rejected`, or `pending` review status
  updates. The endpoint rejects empty IDs, invalid IDs, unknown IDs, and
  `promoted` bulk status.
- Enhanced `/research` with triage summary cards, a grouped ticker table, raw
  queue checkbox selection, and confirmation-gated bulk review actions.
- Kept promotion one-at-a-time through the existing approval and confirmation
  gate. Bulk review does not call promotion or ticker-apply paths.

Verification:

```text
python -m py_compile src\target_opportunity_monitor\research_recommendations.py src\target_opportunity_monitor\api_server.py src\target_opportunity_monitor\cli.py src\target_opportunity_monitor\signal_coverage.py
passed.

python tests\test_phase13c_research_recommendations.py
9 tests passed.

python tests\test_phase14c_research_api.py
9 tests passed.

python tests\test_phase14f_signal_coverage_api.py
5 tests passed.

python tools\run_tests.py smoke --timeout-per-file 180
14 files passed in 54.38s.

python -m target_opportunity_monitor research-recommendation-status
total candidates 325; pending 313; approved not promoted 0; promoted 12;
ignored/rejected 0/0.

python -m target_opportunity_monitor status
required tables present 56/56; TOM loop running and healthy; intraday health
healthy; pending notifications 0; research recommendation candidates 325;
pending 313; approved not promoted 0.

python -m target_opportunity_monitor serve-api --once-smoke-test
health endpoint 200 ok=True; status endpoint 200 ok=True.

npm run build
TypeScript and Vite production build passed.
```

Notes:

- No recommendations were auto-approved, auto-rejected, ignored, or promoted.
- No provider keys, source rows, option positions, option-chain quotes,
  short-interest rows, news/catalyst rows, analyst evidence, broker writes, or
  order/execution paths were created.
- The research triage workflow is implemented, but the live queue remains
  `user_review_required` until rows are intentionally reviewed.

### 2026-06-14 - News/catalyst provider-native intake and diagnostics UI

Completed:

- Extended `GET /api/backfills/news/status` with structured provider-native
  diagnostics, diagnostics text, accepted source labels, source headers, and the
  provider-native append target path.
- Added `POST /api/backfills/news/append-row`, confirmation-gated, writing only
  to
  `data/signals/source_exports/news_catalysts/provider_native_backfill/news_catalyst_provider_native_backfill.csv`.
- Enhanced `/backfills` with a News/Catalyst diagnostics table and
  provider-native source-row builder. Appending a row does not import it or touch
  canonical news/catalyst data.
- Added focused tests for blank provider-native placeholders, valid CRM-style
  rows, invalid source/field cases, append confirmation, refreshed status
  serialization, and unchanged apply gates.

Verification:

```text
python -m py_compile src\target_opportunity_monitor\news_catalyst_sources.py src\target_opportunity_monitor\api_server.py src\target_opportunity_monitor\cli.py src\target_opportunity_monitor\reporting.py src\target_opportunity_monitor\dashboard.py
passed.

python tests\test_phase10e_news_catalysts.py
30 tests passed in 22.719s.

python tests\test_phase14e_activation_api.py
10 tests passed in 6.206s.

python tests\test_phase14f_signal_coverage_api.py
5 tests passed in 6.678s.

python tools\run_tests.py smoke --timeout-per-file 180
14 files passed in 50.82s.

python -m target_opportunity_monitor news-catalyst-provider-backfill-status
current provider-native coverage 5/13; projected 5/13; valid rows 0; blank
placeholders 8; invalid rows 0; blocked by no_valid_provider_native_backfill_rows;
still blocked CRM, GOOGL, JPM, LLY, META, MSFT, NVDA, ORCL.

python -m target_opportunity_monitor news-catalyst-provider-upgrade-status
status queued; provider-native coverage 5/13; upgraded tickers AAPL, AMD, AMZN,
AVGO, COST; text-derived-only CRM, GOOGL, JPM, LLY, META, MSFT, NVDA, ORCL;
marketaux, eodhd, and x_recent_search unavailable because keys are missing.

python -m target_opportunity_monitor status
Required tables present 56/56; TOM loop running and healthy; intraday health
healthy with weekend/off-hours notes only; pending notifications 0;
news/catalyst provider-native coverage 5/13; valid provider-native backfill rows
0; blank placeholders 8; projected provider-native coverage 5/13; blocked by
no_valid_provider_native_backfill_rows.

python -m target_opportunity_monitor serve-api --once-smoke-test
health endpoint 200 ok=True; status endpoint 200 ok=True.

npm run build
TypeScript and Vite production build passed.
```

Notes:

- No provider keys, provider-native rows, synthetic scores/headlines,
  short-interest rows, option positions, option-chain quotes, analyst evidence,
  research approvals, broker writes, or order/execution paths were created.
- The news/catalyst provider-native intake/diagnostics workflow is implemented,
  but the real `CRM`, `GOOGL`, `JPM`, `LLY`, `META`, `MSFT`, `NVDA`, and `ORCL`
  provider/export gap remains open until valid source-backed rows or provider
  keys are supplied.

### 2026-06-14 - Short-interest missing-row intake and diagnostics UI

Completed:

- Extended `GET /api/backfills/short-interest/status` with missing-plan text
  and provider diagnostics text, while preserving the structured missing-plan
  diagnostics payload.
- Added `POST /api/backfills/short-interest/append-row`, confirmation-gated,
  writing only to
  `data/signals/source_exports/short_interest/missing_provider_short_interest_backfill.csv`.
- Enhanced `/backfills` with a Short Interest diagnostics table and source-row
  intake form for real missing-provider rows. Appending a row does not import it
  or touch canonical short-interest data.
- Added focused tests for blank templates, valid missing rows, invalid rows,
  append confirmation, refreshed status serialization, and unchanged apply
  gates.

Verification:

```text
python -m py_compile src\target_opportunity_monitor\short_interest.py src\target_opportunity_monitor\api_server.py src\target_opportunity_monitor\cli.py src\target_opportunity_monitor\reporting.py src\target_opportunity_monitor\dashboard.py
passed.

python tests\test_phase10g_short_interest_backfill.py
3 tests passed.

python tests\test_phase14e_activation_api.py
8 tests passed.

python tests\test_phase14f_signal_coverage_api.py
5 tests passed.

python tools\run_tests.py smoke --timeout-per-file 180
14 files passed in 52.52s.

python -m target_opportunity_monitor short-interest-missing-coverage-plan
coverage 9/13; projected 9/13; missing CRM, JPM, LLY, ORCL; valid
missing-row tickers none; blocked by no_valid_missing_short_interest_rows.

python -m target_opportunity_monitor short-interest-status
source-backed coverage 9/13; source rows 216; latest settlement date
2026-05-29; missing CRM, JPM, LLY, ORCL.

python -m target_opportunity_monitor status
Required tables present 56/56; intraday health healthy; TOM loop running and
healthy; short-interest source-backed tickers 9/13; valid missing-row tickers
none; missing-coverage blocked apply reason no_valid_missing_short_interest_rows.

python -m target_opportunity_monitor serve-api --once-smoke-test
health endpoint 200 ok=True; status endpoint 200 ok=True.

npm run build
TypeScript and Vite production build passed.
```

Notes:

- No short-interest values, option positions, option-chain quotes,
  news/catalyst rows, analyst evidence, research approvals, broker writes, or
  order/execution paths were created.
- The short-interest intake/diagnostics workflow is implemented, but the real
  `CRM`, `JPM`, `LLY`, and `ORCL` source-data gap remains open until source rows
  are supplied.

### 2026-06-14 - Market-hours-aware intraday health semantics

Completed:

- Made `intraday_health.py` classify the current market session in
  `America/Toronto` as `regular`, `pre_market`, `after_hours`, or `weekend`.
- Kept regular-hours freshness strict: old quote/cycle timestamps still produce
  `stale_quote` and `stale_intraday_cycle` warnings during
  `09:30 <= time < 16:00` on weekdays.
- Moved expected off-hours quote/cycle age into informational notes:
  `off_hours_quote_staleness_expected` and
  `off_hours_intraday_cycle_staleness_expected`.
- Extended CLI/API/report/dashboard/loop surfaces with market session,
  regular-hours flag, and notes so status views no longer label expected
  off-hours freshness as stale.
- Updated the active completion gap register and cross-phase gap plan to mark
  the intraday semantics code gap resolved.

Verification:

```text
python -m py_compile src\target_opportunity_monitor\intraday_health.py src\target_opportunity_monitor\cli.py src\target_opportunity_monitor\api_server.py src\target_opportunity_monitor\reporting.py src\target_opportunity_monitor\dashboard.py src\target_opportunity_monitor\tom_loop.py
passed.

python tests\test_phase11d1_intraday_health.py
7 tests passed.

python tests\test_phase11e_tom_loop.py
6 tests passed.

python tests\test_phase14d_ops_api.py
8 tests passed.

python tests\test_phase6a_reporting.py
4 tests passed.

python tests\test_phase8a_dashboard.py
4 tests passed.

python tools\run_tests.py smoke --timeout-per-file 180
14 files passed in 48.43s.

python -m target_opportunity_monitor intraday-health-check
Status: healthy; Market session: weekend; Regular market hours: False;
Blockers: none; Warnings: none; Notes:
off_hours_quote_staleness_expected,
off_hours_intraday_cycle_staleness_expected.

python -m target_opportunity_monitor tom-loop-status
Status: running; Health: healthy; Market session: weekend; Regular market
hours: False; Notes: off_hours_quote_staleness_expected,
off_hours_intraday_cycle_staleness_expected.

python -m target_opportunity_monitor status
Intraday health: healthy; Intraday market session: weekend; Intraday health
warnings: none; Intraday health notes:
off_hours_quote_staleness_expected,
off_hours_intraday_cycle_staleness_expected.

python -m target_opportunity_monitor serve-api --once-smoke-test
health endpoint: 200 ok=True; status endpoint: 200 ok=True.

npm run build
TypeScript and Vite production build passed.

In-app browser verification against local Vite dev server
`/signals` rendered 7 lane rows with no offline state and no console errors;
`/coverage` rendered 5 group rows with no offline state and no console errors.
```

Notes:

- No option positions, BIL option-chain rows, short-interest rows,
  news/catalyst provider rows, research recommendations, score gates, alert
  gates, broker writes, or order/execution paths were changed.
- Source-data, provider/export, user-review, and Phase 10D evidence-gated gaps
  remain unchanged.

### 2026-06-13 - Cross-phase gap closure refresh

Completed:

- Refreshed the active completion gap register in `execution_plan.md` so it no
  longer treats Phase 11A/11C/11E as stopped or stale:
  - local TOM loop is running and healthy;
  - intraday health is healthy;
  - quote, intraday-gap, and range timestamps are fresh;
  - pending notifications are zero.
- Re-ran the read-only/confirmation-gated activation checks that can move
  without fabricating data:
  - IBKR read-only account fetch produced 2 position rows and 1 cash row;
  - account validation found 4 valid position rows, 2 valid cash rows, and no
    invalid rows;
  - confirmed account apply recomputed portfolio reviews, option risk,
    outcomes, and lifecycle surfaces.
- Confirmed the remaining account/options blocker is source data, not workflow:
  option-position rows remain zero, so option lifecycle rows remain zero.
- Confirmed option-chain coverage remains `18/19`; `BIL` is the only missing
  ticker and provider/source-export rows do not currently improve coverage.
- Confirmed short-interest coverage remains `9/13` with `CRM`, `JPM`, `LLY`,
  and `ORCL` blocked by missing source-backed rows; shadow signals still compute
  for the 9 covered tickers.
- Confirmed news/catalyst provider-native coverage remains `5/13`; the
  provider-native backfill package was regenerated for `CRM`, `GOOGL`, `JPM`,
  `LLY`, `META`, `MSFT`, `NVDA`, and `ORCL`, but the rows are placeholders
  until provider keys or source-backed exports are supplied.
- Confirmed research recommendations remain a user-review queue:
  `325` candidates, `313` pending, and `12` promoted.
- Confirmed Phase 10D remains evidence-gated: analyst revisions are still
  `collecting_evidence` with zero completed 20d validation rows.

Verification:

- `python -m target_opportunity_monitor intraday-health-check`: healthy, no
  blockers or warnings, pending notifications `0`.
- `python -m target_opportunity_monitor account-context-status`: partial;
  portfolio positions `2`, cash rows `1`, option-position rows `0`.
- `python -m target_opportunity_monitor fetch-account-context --source ibkr --read-only`:
  fetched 2 positions and 1 cash row.
- `python -m target_opportunity_monitor validate-account-context-backfill`:
  valid rows positions=`4`, cash=`2`, options=`0`, invalid=`0`.
- `python -m target_opportunity_monitor apply-account-context-backfill --confirm --allow-partial`:
  applied, computed 17 portfolio reviews, option risk for 18 tickers, option
  outcomes for 18 tickers, and zero lifecycle tickers.
- `python -m target_opportunity_monitor option-chain-coverage-plan`:
  coverage `18/19`, missing `BIL`.
- `python -m target_opportunity_monitor apply-options-chain-coverage-backfill`:
  dry-run blocked because projected coverage remains `18/19`.
- `python -m target_opportunity_monitor short-interest-missing-coverage-plan`:
  coverage `9/13`, missing `CRM`, `JPM`, `LLY`, `ORCL`.
- `python -m target_opportunity_monitor apply-short-interest-provider-backfill`:
  dry-run blocked by `no_valid_missing_short_interest_rows`.
- `python -m target_opportunity_monitor compute-short-interest-signals` and
  `validate-short-interest-signals`: completed for covered source-backed
  tickers and skipped missing/ETF-gated rows with warnings.
- `python -m target_opportunity_monitor news-catalyst-provider-backfill-status`:
  provider-native coverage `5/13`, 8 tickers still blocked.
- `python -m target_opportunity_monitor export-news-catalyst-provider-backfill`,
  `validate-news-catalyst-provider-backfill`, and
  `apply-news-catalyst-provider-backfill`: package exported, validation saw 8
  blank placeholders, dry-run blocked by no valid provider-native rows.
- `python -m target_opportunity_monitor test-news-catalyst-provider --provider all --ticker AAPL`:
  provider smoke test reported missing `marketaux`, `eodhd`, and
  `x_recent_search` credentials.
- `python -m target_opportunity_monitor research-recommendation-status` and
  `research-recommendation-report`: queue generated with 313 pending items.
- `python -m target_opportunity_monitor revision-evidence-report`: decision
  remains `collecting_evidence`.
- `python -m target_opportunity_monitor run-daily`: regenerated Markdown and
  CSV reports.
- `python -m target_opportunity_monitor build-dashboard`: regenerated
  `dashboard\index.html`.
- `python -m target_opportunity_monitor serve-api --once-smoke-test`: health
  and status endpoints returned HTTP 200 with `ok=True`.

### 2026-06-13 - Missing ticker resolver embedded in account and ops automation

Completed:

- Added `run_missing_ticker_automation` so source-backed account-context missing
  tickers can be resolved, onboarded, and hydrated from normal TOM workflows
  instead of only through ad hoc CLI commands.
- Wired the resolver into account-context fetch/apply:
  - read-only account fetch and file normalization now stage missing ticker
    candidates and report whether account apply can auto-onboard them;
  - confirmed `apply-account-context-backfill --confirm --allow-partial` now
    runs account-context resolve/onboard/hydrate before final validation/apply.
- Wired the resolver into operational automation:
  - `refresh-data --daily` runs `resolve-missing-tickers` before
    `load-portfolio` and `compute-portfolio-context`;
  - `manual-ops-cycle --mode morning` and `--mode all` run the resolver before
    `verify-universe`, so the persistent TOM loop inherits the behavior through
    its morning/daily paths.
- Kept high-frequency intraday cycles unchanged so the quote/range loop stays
  lightweight.
- Kept commentary/social/research mentions approval-gated; only source-backed
  account-context candidates are auto-onboarded.

Verification:

- `python -m py_compile src\target_opportunity_monitor\missing_tickers.py src\target_opportunity_monitor\account.py src\target_opportunity_monitor\pipeline.py src\target_opportunity_monitor\manual_ops.py src\target_opportunity_monitor\cli.py src\target_opportunity_monitor\api_server.py`: passed.
- `python tests\test_missing_tickers.py`: `6` tests OK.
- `python tests\test_phase11d3_manual_ops.py`: `10` tests OK.
- `python tests\test_phase15a_account_sync.py`: `6` tests OK.
- `python tests\test_phase9a_portfolio.py`: `7` tests OK.
- `python tests\test_phase8a_dashboard.py`: `4` tests OK.
- `python tools\run_tests.py smoke --timeout-per-file 180`: `14` files OK in
  about `46s`.
- `python -m target_opportunity_monitor serve-api --once-smoke-test`: passed.
- `npm run build` in `F:\Investments\tom-ui`: passed.
- Live sanity:
  - `missing-ticker-status`: `BIL` and `DBC` are hydrated account-context
    candidates with no ready or blocked candidates;
  - `manual-ops-cycle --mode morning --dry-run`: planned steps include
    `resolve-missing-tickers`;
  - `validate-account-context-backfill`: valid BIL/DBC position rows and cash
    rows, no invalid rows, option-position rows still empty.

### 2026-06-13 - Cross-phase missing ticker resolver and account activation repair

Completed:

- Added the central missing-ticker resolver with required SQLite tables:
  `missing_ticker_candidates` and `missing_ticker_resolution_events`, bringing
  required table coverage to `56/56`.
- Added storage helpers, CLI commands, local API endpoints, and JS UI panels for
  missing ticker status, resolve, apply, and hydrate workflows:
  - `missing-ticker-status`;
  - `missing-ticker-plan`;
  - `resolve-missing-tickers`;
  - `apply-missing-ticker-onboarding --confirm`;
  - `hydrate-missing-ticker --ticker TICKER`;
  - `/api/missing-tickers/status`;
  - `/api/missing-tickers/resolve`;
  - `/api/missing-tickers/apply`;
  - `/api/missing-tickers/hydrate`.
- Integrated account-context validation so unsupported or inactive holdings
  create auditable missing-ticker candidates instead of only returning a dead-end
  validation error.
- Preserved conservative policy boundaries:
  - source-backed account holdings can be onboarded and hydrated;
  - commentary/social/research mentions remain approval-gated;
  - no metadata, fundamentals, NAVs, holdings, or provider rows are fabricated;
  - no broker writes, order placement, execution, score-rule changes, or
    alert-rule changes.
- Repaired the live account-context blocker:
  - `BIL` and `DBC` were detected from IBKR read-only account rows;
  - both were onboarded as active scoreable ETF assets through watchlist/assets
    and asset-change audit;
  - both were hydrated through available read-only price/target/score/range
    paths;
  - account-context validation now has valid portfolio/cash rows and account
    apply succeeds.

Verification:

- `python -m target_opportunity_monitor init-db`: `56/56` required tables.
- `python -m target_opportunity_monitor resolve-missing-tickers --source account_context`: `BIL` and `DBC` ready/onboarded path verified.
- `python -m target_opportunity_monitor apply-missing-ticker-onboarding --confirm`: applied `2` candidates.
- `python -m target_opportunity_monitor validate-account-context-backfill`: valid portfolio rows and cash rows; no invalid rows.
- `python -m target_opportunity_monitor apply-account-context-backfill --confirm --allow-partial`: applied portfolio/cash rows and regenerated reports/dashboard.
- `python -m target_opportunity_monitor fetch-options-chain --source yfinance --ticker DBC --force-refresh`: loaded 1 DBC option-chain row.
- `python -m target_opportunity_monitor fetch-options-chain --source yfinance --ticker BIL --force-refresh`: provider returned `missing_bid_ask`, so BIL remains an option-chain coverage warning.
- `python tests\test_missing_tickers.py`: `3` tests OK.
- `python -m target_opportunity_monitor serve-api --once-smoke-test`: passed.
- `npm run build` in `F:\Investments\tom-ui`: passed.

Remaining blockers:

- ETF NAV/holdings for `BIL` and `DBC` remain source-data/provider gaps.
- BIL option-chain coverage remains missing unless a valid source-backed chain row
  exists.
- Option-position/lifecycle rows remain `0` until source-backed option-position
  rows are supplied.

### 2026-06-13 - Phase 11E local persistent TOM ops loop

Completed:

- Hardened the Phase 11E TOM loop controller around the existing
  `manual-ops-cycle` worker.
- Replaced the Windows process liveness check with a safe Windows process-query
  path instead of `os.kill(pid, 0)`.
- Kept the Phase 11E CLI surface focused on:
  - `tom-loop-start`;
  - `tom-loop-once`;
  - `tom-loop-stop`;
  - `tom-loop-status`;
  - `tom-loop-health`.
- Preserved loop state under `data/ops/loop/` with state JSON, lockfile,
  heartbeat JSON, and cooperative stop request.
- Stabilized Phase 11E tests by mocking the loop freshness seam so tests do not
  touch provider, IBKR, yfinance, or broad live health paths.
- Kept `/api/loop/status`, `/api/loop/health`, `/api/loop/start`,
  `/api/loop/stop`, and `/api/loop/run-once` stable and confirmation-gated for
  mutating calls.
- Updated README, UI README, and `execution_plan.md` so the preferred durable
  operator command is:
  `python -m target_opportunity_monitor tom-loop-start --mode auto --deliver --channel file`.

Verification:

```powershell
python -m py_compile src\target_opportunity_monitor\tom_loop.py src\target_opportunity_monitor\cli.py src\target_opportunity_monitor\api_server.py src\target_opportunity_monitor\reporting.py src\target_opportunity_monitor\dashboard.py
python tests\test_phase11e_tom_loop.py
python tests\test_phase11e_loop_api.py
python -m target_opportunity_monitor tom-loop-status
python -m target_opportunity_monitor tom-loop-once --mode auto --deliver --channel file
python -m target_opportunity_monitor tom-loop-start --mode auto --deliver --channel file --max-cycles 1 --interval-seconds 1
python -m target_opportunity_monitor tom-loop-health
python -m target_opportunity_monitor tom-loop-stop
python -m target_opportunity_monitor serve-api --once-smoke-test
python tools\run_tests.py smoke --timeout-per-file 180
npm run build
```

Results:

- Backend compile passed.
- Phase 11E loop tests passed: `6` tests OK.
- Phase 11E API tests passed: `4` tests OK.
- `tom-loop-status` reported stopped loop state, pending notifications `0`, and
  expected stale quote/intraday-cycle warnings from current live data.
- `tom-loop-once --mode auto --deliver --channel file` completed `ok` using
  the guarded `daily-retry` path.
- Bounded `tom-loop-start --max-cycles 1 --interval-seconds 1` completed `ok`
  with `iterations=1` and `reason=max_cycles_reached`.
- `tom-loop-health` and `tom-loop-stop` behaved cleanly with no active loop.
- Local API smoke test passed for `/api/health` and `/api/status`.
- Smoke suite passed: `13` files in about `42s`.
- `F:\Investments\tom-ui` production build passed.

Boundaries:

- Phase 11E is read-only with respect to brokers and trading.
- No broker writes, order placement, execution, score-rule changes,
  alert-rule changes, range-rule changes, or portfolio mutation were added.
- Codex scheduler can remain disabled by choice; TOM now has a user-started
  local persistent loop path.
- Account context remains blocked until real source-backed account/cash/option
  position rows are supplied or fetched and confirmed.

### 2026-06-12 - Phase 11D.2 scheduler reconciliation and alert delivery reliability MVP

Completed:

- Updated the live Codex `tom-intraday-probe` heartbeat automation from the
  older IBKR-only command to:
  `python -m target_opportunity_monitor intraday-cycle --source auto --deliver --channel file`.
- Added `scheduler.py` with intended TOM automation definitions and TOM-side
  reconciliation against saved Codex automation metadata under
  `C:\Users\Frank\.codex\automations`.
- Added CLI commands:
  - `scheduler-audit`;
  - `scheduler-repair-plan`;
  - `scheduler-automation-status`;
  - `notification-delivery-report`.
- Added `intraday-cycle --drain-first` so pending notification events can be
  delivered before new range events are created.
- Updated `scheduler-status`, `intraday-status`, `status`, daily Markdown/CSV,
  dashboard health, README, and `execution_plan.md` with scheduler
  reconciliation status, actual heartbeat command, stale/missing automation
  warnings, pending/delivery-failed notification state, and outbox visibility.

Verification:

```powershell
python -m unittest discover -s tests -p test_phase11d2_scheduler_reconciliation.py
python -m unittest discover -s tests -p test_phase11d1_intraday_health.py
python -m unittest discover -s tests -p test_phase11c_intraday_notifications.py
python -m target_opportunity_monitor scheduler-audit
python -m target_opportunity_monitor scheduler-repair-plan
python -m target_opportunity_monitor scheduler-automation-status
python -m target_opportunity_monitor notification-delivery-report
python -m target_opportunity_monitor intraday-cycle --source auto --drain-first --deliver --channel file
python -m target_opportunity_monitor intraday-health-check
python -m target_opportunity_monitor scheduler-status
python -m unittest discover -s tests
```

Results:

- Focused Phase 11D.2 tests passed: `7` tests OK.
- Existing Phase 11D.1 tests passed: `5` tests OK.
- Existing Phase 11C intraday/notification tests passed: `8` tests OK.
- Full regression passed: `285` tests OK.
- Live scheduler audit reported `configured` after the Codex heartbeat update.
- Final live `intraday-cycle --source auto --drain-first --deliver --channel
  file` completed `ok` with expected IBKR-unavailable warnings and daily-price
  fallback quote snapshots.
- Final live health was `healthy`:
  - pending notifications: `0`;
  - failed deliveries: `0`;
  - latest quote/range timestamps: `2026-06-12T20:37:59` /
    `2026-06-12T20:38:00`.
- Notification delivery report showed `0` pending events and `0` failed
  delivery rows.

Boundaries:

- Phase 11D.2 is read-only.
- No broker writes, order placement, execution, score impact, alert-rule
  change, range-rule change, portfolio mutation, or automatic trade inference
  was added.
- Account context remains blocked on user-supplied portfolio/cash/options rows.
- Phase 10D remains gated until analyst-revision 20d evidence matures.

### 2026-06-12 - Phase 11D.1 intraday health, quote freshness, and notification drain MVP

Completed:

- Added intraday health config defaults:
  - `realtime.intraday_cycle_stale_after_seconds = 1800`;
  - `realtime.notification_pending_stale_after_seconds = 1800`.
- Added `intraday_health.py` with shared `healthy|stale|blocked`
  classification from existing pipeline, quote, range, notification, and
  delivery rows.
- Added CLI commands:
  - `intraday-health-check`;
  - `intraday-repair-plan`;
  - `notification-outbox-status`;
  - `drain-pending-notifications --channel console|file|webhook`.
- Extended `intraday-cycle --source auto`:
  - tries IBKR quotes first;
  - if IBKR returns no quote rows, refreshes read-only daily market data;
  - writes explicit `daily_price_fallback` quote snapshots with warnings.
- Updated notification delivery so failed channels audit delivery rows and mark
  notification events as `delivery_failed`; successful file/console delivery
  drains events to `delivered`.
- Updated `status`, `intraday-status`, `scheduler-status`, daily Markdown/CSV,
  dashboard health, README, and `execution_plan.md` with intraday health,
  blockers, warnings, pending notification state, and preferred heartbeat
  command.

Verification:

```powershell
python -m py_compile src\target_opportunity_monitor\intraday_health.py src\target_opportunity_monitor\pipeline.py src\target_opportunity_monitor\cli.py src\target_opportunity_monitor\reporting.py src\target_opportunity_monitor\dashboard.py tests\test_phase11d1_intraday_health.py tests\test_phase11c_intraday_notifications.py
python -m unittest discover -s tests -p test_phase11d1_intraday_health.py
python -m unittest discover -s tests -p test_phase11c_intraday_notifications.py
python -m target_opportunity_monitor intraday-health-check
python -m target_opportunity_monitor intraday-repair-plan
python -m target_opportunity_monitor notification-outbox-status
python -m target_opportunity_monitor drain-pending-notifications --channel file
python -m target_opportunity_monitor intraday-cycle --source auto --deliver --channel file
python -m target_opportunity_monitor scheduler-status
```

Results:

- Focused Phase 11D.1 tests passed: `5` tests OK.
- Existing Phase 11C intraday/notification tests passed: `8` tests OK.
- Live health before repair was `stale`:
  - stale quote timestamp;
  - stale intraday cycle;
  - `4` pending notifications.
- `drain-pending-notifications --channel file` delivered `4` pending events
  into `data/notifications/outbox/2026-06-12/`.
- `intraday-cycle --source auto --deliver --channel file` completed with
  warning status on quote refresh because IBKR was not connected, then wrote
  `22` daily-price fallback quote snapshots and refreshed range state.
- Live health after repair was `healthy`:
  - pending notifications: `0`;
  - failed deliveries: `0`;
  - fresh quote/range timestamps;
  - preferred heartbeat command:
    `python -m target_opportunity_monitor intraday-cycle --source auto --deliver --channel file`.

Boundaries:

- Phase 11D.1 is read-only.
- No broker writes, order placement, execution, score impact, alert-rule
  change, range-rule change, portfolio mutation, or automatic trade inference
  was added.
- IBKR unavailability is now a visible warning with daily-price fallback, not a
  hard intraday-loop failure.

### 2026-06-12 - Phase 12F.1 / 9B account context activation MVP

Completed:

- Added guided account-context commands:
  - `account-context-status`;
  - `export-account-context-template`;
  - `validate-account-context-backfill`;
  - `preview-account-context-activation`;
  - `apply-account-context-backfill`;
  - `normalize-account-export --provider ibkr|generic --file PATH`.
- Added `paths.account_source_exports = "data/account/source_exports"` and
  generated header-only source-export templates for portfolio positions,
  portfolio cash, option positions, generic exports, and IBKR-style exports.
- Validation now checks account/source metadata, required dates, required
  numeric values, active tickers, and existing portfolio/options parser rules
  before any confirmed apply.
- `apply-account-context-backfill` is dry-run by default. Confirmed apply
  merges valid source-export rows into the manual CSVs, loads portfolio/cash and
  option positions, recomputes portfolio context, option risk, option outcomes,
  option lifecycle, daily report, and dashboard.
- Added account-context status fields to `status`, daily Markdown, and
  dashboard health output.

Verification:

```powershell
python -m compileall src\target_opportunity_monitor
python -m unittest discover -s tests -p test_phase12f1_account_context.py
python -m target_opportunity_monitor account-context-status
python -m target_opportunity_monitor export-account-context-template
python -m target_opportunity_monitor validate-account-context-backfill
python -m target_opportunity_monitor preview-account-context-activation
python -m target_opportunity_monitor apply-account-context-backfill
python -m target_opportunity_monitor apply-account-context-backfill --confirm --allow-partial
python -m target_opportunity_monitor status
```

Results:

- Focused Phase 12F.1 tests passed: `8` tests OK.
- Live account context remains `not_configured` because the templates are
  intentionally blank.
- Confirmed apply correctly blocks with `no valid rows are present`.
- Live blockers are explicit:
  - `empty_portfolio_positions`;
  - `empty_portfolio_cash`;
  - `empty_options_positions`;
  - `no_option_lifecycle_rows`;
  - `option_risk_missing_portfolio_context`.
- Option risk rows missing portfolio context remain `747` until real
  portfolio/cash rows are supplied.

Boundaries:

- Phase 12F.1 is read-only.
- No broker writes, order placement, execution, score impact, alert impact,
  range impact, or automatic trade inference was added.
- Phase 10D remains gated until analyst revision validation has mature 20d
  evidence that passes the configured evidence gate.

### 2026-06-12 - Phase 12E.1 broader option-chain data activation MVP

Completed:

- Added read-only `yfinance`/Yahoo option-chain fetching as a provider-backed
  fallback for the existing `fetch-options-chain` command.
- Added `auto` option-chain source behavior:
  - tries IBKR first;
  - falls back to yfinance/Yahoo for tickers that still return zero usable IBKR
    rows;
  - prioritizes missing chain tickers before refreshing already-covered names.
- Provider-fetched yfinance rows are source-backed with Yahoo option-chain URLs,
  cached under `data/options/cache/chains/yfinance/`, written through the
  source-export CSV shape, validated, and then stored in the existing
  `option_chain_snapshots` table.
- Updated `configs/default.toml` so daily option fetches use
  `options.chain_source = "auto"`.
- Extended broader option-chain apply reporting to include lifecycle
  recomputation alongside income, risk, and outcome recomputation.
- Updated option-chain coverage output to show fallback order and provider
  attempt status.
- Activated broader live option-chain coverage:
  - first yfinance run loaded 221 source-backed rows for
    `AMD`, `AMZN`, `AVGO`, `COST`, and `CRM`;
  - second yfinance run loaded 414 source-backed rows for
    `GOOGL`, `JPM`, `LLY`, `META`, `MSFT`, `NVDA`, `ORCL`, `QQQ`, and `SPY`;
  - broader option-chain coverage moved from `3/17` to `17/17`.
- Recomputed option income, risk, outcomes, and lifecycle after activation.
- Updated README and `execution_plan.md` to mark Phase 12E.1 complete and to
  remove broader option-chain fill as the active open options gap.

Verification:

```powershell
python -m compileall src\target_opportunity_monitor
python -m unittest discover -s tests -p "test_phase12*.py"
python -m target_opportunity_monitor fetch-options-chain --source yfinance --max-tickers 5 --force-refresh
python -m target_opportunity_monitor fetch-options-chain --source yfinance --max-tickers 9 --force-refresh
python -m target_opportunity_monitor compute-options-income
python -m target_opportunity_monitor compute-options-risk
python -m target_opportunity_monitor compute-options-outcomes
python -m target_opportunity_monitor compute-options-lifecycle
python -m target_opportunity_monitor option-chain-coverage-plan
python -m target_opportunity_monitor options-status
python -m target_opportunity_monitor refresh-data --daily-only
python -m target_opportunity_monitor run-daily
python -m target_opportunity_monitor build-dashboard
python -m target_opportunity_monitor status
python -m unittest discover -s tests
```

Results:

- Required schema remains `49/49` tables.
- Broader option-chain coverage is `17/17`.
- Option chain rows increased to `744` after the final daily refresh.
- Option income review rows increased to `747` across `17` reviewed tickers.
- Option risk review rows increased to `747`.
- Option outcome rows increased to `747`.
- Option lifecycle rows remain `0` because the manual options position ledger is
  empty, which is expected.

Boundaries:

- Phase 12E.1 is read-only.
- No broker writes, order placement, execution, score impact, alert impact,
  range impact, or margin automation was added.
- Phase 10D remains gated until analyst revision validation has mature 20d
  evidence that passes the configured evidence gate.

### 2026-06-12 - Phase 12F options position lifecycle and realized P/L MVP

Completed:

- Added Phase 12F options lifecycle config defaults:
  `options_lifecycle_model_version`, `options_realized_pl_model_version`,
  `options_option_multiplier`, `options_position_stale_after_days`, and
  `options_assignment_tracking_enabled`.
- Extended the manual option-position CSV workflow with optional lifecycle
  fields: `position_id`, `status`, roll links, underlying assignment date,
  underlying shares/cost basis, and tags.
- Added the `option_position_lifecycle_reviews` table with idempotent upsert
  keyed by manual position identity and lifecycle model version.
- Added read-only lifecycle/P&L computation:
  - closed short-put realized P/L from premium, close price, contracts,
    multiplier, and fees;
  - expired-worthless P/L when stored underlying prices show expiration above
    strike;
  - assigned-position exposure and cost-basis proxy from user-marked
    assignment rows;
  - open P/L proxy from latest option mark/mid when available.
- Linked manual positions to nearest option-income reviews, plus available
  option-risk and option-outcome rows.
- Added CLI commands:
  - `compute-options-lifecycle`
  - `compute-options-lifecycle --ticker TICKER`
  - `options-lifecycle-status`
  - `options-lifecycle-report`
- Updated `refresh-data --daily` and optional intraday options flow to compute
  lifecycle after position loading and option outcome validation.
- Updated `status`, `options-status`, daily Markdown/CSV, and dashboard health
  and ticker detail fields with lifecycle rows, realized P/L, open P/L proxy,
  assignment exposure, unmatched positions, and lifecycle warnings.
- Updated README and `execution_plan.md` to mark Phase 12F complete.

Verification:

```text
python -m compileall src\target_opportunity_monitor
Succeeded.

python -m unittest discover -s tests -p test_phase12f_options_lifecycle.py
5 tests passed.

python -m unittest discover -s tests -p "test_phase12*.py"
45 tests passed.

python -m unittest discover -s tests
263 tests passed.

python -m target_opportunity_monitor init-db
Required tables present: 49/49.

python -m target_opportunity_monitor load-options-positions
Options positions loaded: 0 rows.
Warnings: empty_options_positions.

python -m target_opportunity_monitor compute-options-outcomes
Option review outcomes computed for AAPL, KORU, and SOXL.

python -m target_opportunity_monitor compute-options-lifecycle
Option lifecycle reviews computed: 0 tickers because the manual positions CSV
is empty.

python -m target_opportunity_monitor compute-options-lifecycle --ticker SOXL
SOXL skipped with missing_option_position.

python -m target_opportunity_monitor options-lifecycle-status
Lifecycle rows: 0.

python -m target_opportunity_monitor options-lifecycle-report
Generated the read-only lifecycle report text with 0 rows.

python -m target_opportunity_monitor options-status
Option lifecycle rows: 0.

python -m target_opportunity_monitor run-daily
Created reports/2026-06-12-daily-report.md and CSV.

python -m target_opportunity_monitor build-dashboard
Dashboard regenerated.

python -m target_opportunity_monitor status
Required tables present: 49/49.
Option lifecycle review rows: 0.
```

Notes:

- Phase 12F is read-only. It does not place orders, write to brokers, automate
  exercise/assignment, or affect scores, alerts, ranges, or portfolio guidance.
- Manual option positions remain user-supplied truth. TOM does not infer real
  trades from reviewed ideas.
- Empty `options_positions.csv` remains valid and warning-only.
- Phase 10D remains gated until analyst revision validation has mature 20d
  evidence and passes the configured evidence gate.

### 2026-06-12 - Phase 12E broader option-chain coverage MVP

Completed:

- Added a broader option-chain coverage planner for the full options-eligible
  universe, with current coverage, prioritized missing tickers, valid source
  export rows, projected coverage, provider blockers, and next commands.
- Added CLI commands:
  - `option-chain-coverage-plan`
  - `export-options-chain-missing-template`
  - `apply-options-chain-coverage-backfill`
- Added a missing-chain source-export template at
  `data/options/source_exports/options_chain_missing_backfill.csv`.
- Added guarded broader coverage apply behavior. Dry run is the default;
  confirmed apply imports only valid source-backed rows, recomputes option
  income, risk, and outcomes, and aborts on invalid rows, zero valid rows, or no
  projected coverage improvement. `--allow-partial` permits incremental
  coverage gains.
- Extended `status`, `options-status`, `option-chain-status`, daily Markdown/CSV
  reports, and the dashboard health panel with broader option-chain coverage,
  missing tickers, projected coverage, valid backfill tickers, apply readiness,
  and blockers.
- Updated `README.md` and `execution_plan.md` to mark Phase 12E complete and set
  the next candidates to Phase 12F realized option P/L/lifecycle reporting,
  external delivery, remaining shadow-data cleanup, or Phase 10D once evidence
  matures.

Verification:

```text
python -m compileall -q src/target_opportunity_monitor
passed.

python -m unittest discover -s tests -p test_phase12b_options_chain.py
22 tests passed.

python -m unittest discover -s tests -p test_phase12c_options_risk.py
6 tests passed.

python -m unittest discover -s tests -p test_phase12d_options_outcomes.py
6 tests passed.

python -m unittest discover -s tests
258 tests passed.
```

Notes:

- Phase 12E does not fabricate option-chain rows. Broader coverage improves only
  after valid source-backed bid/ask rows are supplied for missing tickers.
- Source-backed manual/provider rows remain acceptable while live IBKR chain
  access is incomplete.
- No broker writes, order placement, auto execution, score impact, alert impact,
  or range impact was added.

### 2026-06-12 - Phase 12D options review outcome tracking and position ledger MVP

Completed:

- Added Phase 12D options outcome and position config defaults, including
  `paths.options_positions`, `options.outcome_model_version`,
  `options.position_model_version`, and the `5d`, `20d`, and `expiration`
  outcome horizons.
- Added required SQLite tables:
  - `option_review_outcomes`
  - `option_position_ledger`
- Added manual read-only option-position CSV loading at
  `data/options/manual/options_positions.csv`.
- Added option review outcome computation from stored underlying daily OHLCV
  prices, including 5d/20d/latest returns, expiration status, above-strike and
  above-breakeven flags, strike/breakeven touch flags, MFE/MAE, and linked
  manual position count.
- Added CLI commands:
  - `load-options-positions`
  - `compute-options-outcomes`
  - `compute-options-outcomes --ticker TICKER`
  - `options-position-status`
  - `options-outcome-status`
  - `options-outcome-report`
- Wired `refresh-data --daily` and optional intraday options runs to load
  manual option positions and compute option review outcomes after option risk.
- Extended `status`, `options-status`, daily Markdown/CSV reports, and dashboard
  health/ticker detail output with option outcome and position ledger coverage.

Verification:

```text
python -m unittest discover -s tests -p test_phase12d_options_outcomes.py
6 tests passed.

python -m unittest discover -s tests
253 tests passed.
```

Notes:

- Phase 12D outcomes are hypothetical review outcomes unless a manual position
  row is supplied.
- Phase 12D uses underlying daily prices only; it does not mark options to
  market, automate assignment, or model broker-specific margin.
- Reference instruments such as `SOXL` and `KORU` remain outcome-reviewable but
  excluded from scoreable alerts/ranges/portfolio guidance.
- No broker writes, order placement, auto execution, score impact, alert impact,
  or range impact was added.

### 2026-06-11 - Phase 12C options risk and margin depth MVP

Completed:

- Added `option_risk_reviews` as a required SQLite table with idempotent upsert
  keyed to the source `option_income_reviews` row and risk model version.
- Added Phase 12C options risk config defaults for the cash-secured proxy model,
  max single-contract notional weight, max total assignment notional weight,
  minimum cash reserve after assignment, downside scenario percentages, and
  reference-instrument warnings.
- Added read-only risk computation on top of existing option-income reviews:
  assignment notional, premium income, cash-secured requirement, max-loss proxy,
  `-5%`, `-10%`, and `-20%` scenario P/L, projected assignment weight,
  cash-after-assignment estimate, and max-contract advisory.
- Added risk categories:
  `risk_review_ready`, `portfolio_context_needed`, `assignment_notional_high`,
  `cash_reserve_breach`, `assignment_would_exceed_position_limit`,
  `range_or_technical_risk`, `reference_only_review`, and `not_reviewable`.
- Added CLI commands:
  - `compute-options-risk`
  - `compute-options-risk --ticker TICKER`
  - `options-risk-status`
  - `options-risk-report`
- Wired `refresh-data --daily` and optional intraday options runs to compute
  option risk after option-income reviews.
- Extended `status`, `options-status`, daily Markdown/CSV reports, and dashboard
  health/ticker details with option-risk coverage and risk metrics.

Verification:

```text
python -m unittest discover -s tests -p test_phase12c_options_risk.py
6 tests passed.
```

Notes:

- Phase 12C uses a conservative cash-secured proxy, not broker-specific
  portfolio margin.
- Empty or missing portfolio context creates warnings and risk rows; it does not
  block the daily pipeline.
- `SOXL` and `KORU` remain commentary/reference instruments and are labeled
  `reference_only_review` in risk output.
- No broker writes, order placement, auto execution, exercise/assignment
  automation, score impact, alert impact, or range impact was added.

### 2026-06-11 - Phase 12B.3 option-chain data activation and IBKR repair MVP

Completed:

- Repaired the local Python `ibapi` package in the current user Python
  environment after explicit approval. The prior live blocker
  `ibapi_permission_denied` is resolved and `diagnose-options-provider --source
  ibkr` now reports `ibapi status: ok`.
- Confirmed the remaining live IBKR blocker is connectivity rather than Python
  package access. IBKR/Gateway was not connected during verification, so live
  option-chain fetches remained unavailable.
- Activated the existing source-backed fallback path by generating minimum-set
  option-chain backfill rows for `SOXL`, `KORU`, and `AAPL` from provider-backed
  Yahoo/yfinance option-chain data.
- Imported 3 valid option-chain rows and computed 3 read-only sell-put advisory
  reviews.
- Confirmed the minimum activation state moved to active:
  - `Minimum chain coverage: 3/3`
  - `Minimum option review count: 3`
  - `Activation blocked reason: none`

Verification:

```text
python -m target_opportunity_monitor option-chain-activation-status
Activation status: active.
Activation blocked reason: none.
ibapi status: ok.
Minimum chain coverage: 3/3.
Minimum option review count: 3.

python -m target_opportunity_monitor activate-options-chain-data --confirm --allow-partial
Imported rows: 3.
Computed review tickers: 3.
Minimum option review count: 3.
```

Notes:

- IBKR remains read-only and was not connected during this activation pass.
- The activated option rows are advisory inputs only; TOM still does not place
  orders, write to brokers, execute trades, or change scores, alerts, ranges, or
  portfolio guidance.
- Phase 12C options risk/margin depth is now unblocked from a data-readiness
  perspective because option-income reviews exist.

### 2026-06-10 - Phase 12B.1 option provider health and data activation MVP

Completed:

- Added `paths.options_chain_source_exports = "data/options/source_exports"`.
- Added option-provider health/status helpers that classify blockers such as
  `ibapi_permission_denied`, `ibapi_missing`, `ibkr_not_connected`,
  `option_subscription_missing`, `missing_bid_ask`, `stale_underlying_price`,
  and `no_chain_rows`.
- Added provider/backfill commands:
  - `option-provider-status`
  - `diagnose-options-provider --source ibkr`
  - `test-options-provider --source ibkr --ticker TICKER`
  - `export-options-chain-backfill-template`
  - `validate-options-chain-backfill`
  - `import-options-chain-source-exports`
- Added strict source-export validation for option-chain backfills requiring
  source-backed bid/ask rows with `source` and `source_url`.
- Extended `status`, daily Markdown/CSV reports, dashboard health, and
  options status output with option-provider readiness, blocked reason, backfill
  readiness, projected chain coverage, and source-export visibility.
- Preserved Phase 12A/12B boundaries: read-only option advisory only, no broker
  writes, no order placement, and no score/alert/range changes.

Verification:

```text
python -m unittest discover -s tests -p test_phase12b_options_chain.py
13 tests passed.

python -m unittest discover -s tests -p test_phase12a_options.py
6 tests passed.

python -m unittest discover -s tests
237 tests passed.
Non-fatal ResourceWarnings appeared, consistent with prior suite behavior.

python -m target_opportunity_monitor init-db
Required tables present: 45/45.

python -m target_opportunity_monitor option-provider-status
Provider readiness: blocked.
Blocked reason: ibapi_permission_denied.

python -m target_opportunity_monitor diagnose-options-provider --source ibkr
IBKR connectivity: not_available because ibapi permission is blocked.

python -m target_opportunity_monitor test-options-provider --source ibkr --ticker SOXL
Rows loaded: 0; warning includes ibapi permission denied.

python -m target_opportunity_monitor export-options-chain-backfill-template --ticker SOXL
Created data/options/source_exports/options_chain_backfill_soxl.csv.

python -m target_opportunity_monitor validate-options-chain-backfill
Valid rows: 0; blank placeholders: 1; blocked reason no_valid_option_backfill_rows.

python -m target_opportunity_monitor import-options-chain-source-exports
Imported rows: 0; placeholder-only import remained safe.

python -m target_opportunity_monitor compute-options-income
Option income reviews: 0 until source-backed chain rows exist.

python -m target_opportunity_monitor run-daily
Daily Markdown and CSV regenerated.

python -m target_opportunity_monitor build-dashboard
Dashboard regenerated with option-provider health fields.
```

Live notes:

- Option-chain rows remain `0` and option-income reviews remain `0`.
- Current live blocker is local `ibapi_permission_denied`, not TOM schema or
  pipeline logic.
- Source-export fallback is now ready for source-backed option-chain rows.

### 2026-06-10 - Phase 12B IBKR option-chain ingestion MVP

Completed:

- Added Phase 12B option-chain provider/cache configuration defaults:
  - `paths.options_chain_cache = "data/options/cache/chains"`
  - `options.chain_source = "ibkr"`
  - bounded expiration/strike/ticker limits,
  - daily auto-fetch enabled,
  - intraday auto-fetch disabled unless explicitly requested.
- Added a read-only IBKR option-chain adapter using a separate client id offset.
  It discovers option expirations/strikes, filters to bounded put contracts,
  requests bid/ask quote snapshots, writes `source = "ibkr_option_chain"` rows,
  and records warning-only provider failures.
- Added provider-facing commands:
  - `fetch-options-chain --source ibkr|csv`
  - `fetch-options-chain --source ibkr --ticker TICKER`
  - `fetch-options-chain --source ibkr --max-tickers N --force-refresh`
  - `option-chain-status`
- Extended `refresh-data --daily` so bounded option-chain fetch runs before
  manual CSV load and sell-put review computation.
- Extended `intraday-cycle` with opt-in `--include-options`; the default
  heartbeat remains lightweight.
- Extended `status`, daily Markdown reports, and dashboard health with
  option-chain source/cache/fetch-universe/missing-chain visibility.
- Preserved the manual CSV fallback and all Phase 12A advisory-only boundaries.

Verification:

```text
python -m unittest discover -s tests -p test_phase12b_options_chain.py
8 tests passed.

python -m unittest discover -s tests -p test_phase12a_options.py
6 tests passed.

python -m unittest discover -s tests -p test_phase11c_intraday_notifications.py
8 tests passed.

python -m unittest discover -s tests
232 tests passed.
Non-fatal ResourceWarnings appeared, consistent with prior suite behavior.

python -m target_opportunity_monitor init-db
Required tables present: 45/45.

python -m target_opportunity_monitor ibkr-status
IBKR API object was importable but Gateway was not connected on 127.0.0.1:4002.

python -m target_opportunity_monitor fetch-options-chain --source ibkr --ticker SOXL --force-refresh
Rows loaded: 0. Warning-only failure: local ibapi permission denied plus ibkr_unavailable.

python -m target_opportunity_monitor fetch-options-chain --source ibkr --ticker KORU --force-refresh
Rows loaded: 0. Warning-only failure: local ibapi permission denied plus ibkr_unavailable.

python -m target_opportunity_monitor compute-options-income
Option income reviews computed: 0 tickers, because no live/manual chain rows exist yet.

python -m target_opportunity_monitor option-chain-status
Configured source: ibkr.
Rows: 0.
Fetch-universe tickers: 17.
Missing chain tickers: KORU, SOXL, AAPL, AMD, AMZN, AVGO, COST, CRM, GOOGL, JPM, LLY, META, MSFT, NVDA, ORCL, QQQ, SPY.

python -m target_opportunity_monitor options-status
Options chain rows: 0.
Option income review tickers: 0.

python -m target_opportunity_monitor refresh-data --daily-only
daily_refresh status: ok.
New fetch-options-chain step: warning-only with KORU/SOXL/AAPL ibapi permission warnings.

python -m target_opportunity_monitor run-daily
Created reports/2026-06-10-daily-report.md and reports/2026-06-10-daily-report.csv.

python -m target_opportunity_monitor build-dashboard
Dashboard regenerated with 29 rows.

python -m target_opportunity_monitor status
Options chain source: ibkr.
Options chain rows: 0.
Option income review rows: 0.
Options fetch-universe tickers: 17.

python -m target_opportunity_monitor verify-universe
Readiness summary: ready=15/15, warnings=0.
```

Boundaries:

- IBKR remains read-only.
- Missing Gateway access, missing option subscription, missing bid/ask, stale
  underlying price, or fetch-budget exhaustion are warnings, not failures or
  trading actions.
- No order placement, broker writes, margin model, assignment handling,
  automatic execution, score impact, alert impact, range impact, portfolio
  guidance impact, or notification-rule change.
- Phase 10D remains gated until analyst revision validation has mature 20d
  evidence and passes the configured evidence gate.

---

## Phase 12B.2 - Option chain activation and minimum data seeding MVP

Date: 2026-06-10

Implemented:

- Added explicit option-chain activation status for the minimum activation set:
  `SOXL`, `KORU`, and `AAPL`.
- Added diagnostic-only IBKR repair guidance with the exact `ibapi` import
  blocker surfaced without changing Windows permissions or broker settings.
- Added `--minimum-set` support for
  `export-options-chain-backfill-template`.
- Added guarded `activate-options-chain-data` dry-run/confirm flow.
  Confirmed activation imports only valid source-backed option-chain exports,
  recomputes sell-put reviews, and fails if no option-income review is
  produced.
- Added activation/minimum coverage fields to status, daily Markdown/CSV
  reports, and dashboard health output.

New commands:

```powershell
python -m target_opportunity_monitor option-chain-activation-status
python -m target_opportunity_monitor option-provider-repair-plan --source ibkr
python -m target_opportunity_monitor option-chain-minimum-backfill-plan
python -m target_opportunity_monitor export-options-chain-backfill-template --minimum-set
python -m target_opportunity_monitor activate-options-chain-data
python -m target_opportunity_monitor activate-options-chain-data --confirm --allow-partial
```

Verification:

```powershell
python -m unittest discover -s tests -p test_phase12b_options_chain.py
python -m unittest discover -s tests -p test_phase12a_options.py
```

Result:

```text
Phase 12B option-chain tests: 17 passed.
Phase 12A options advisory tests: 6 passed.
```

Notes:

- Phase 12C options risk/margin depth remains gated until at least one
  source-backed option-chain row produces an option-income review.
- IBKR remains read-only.
- Manual/provider source exports remain the fallback while `ibapi` or IBKR
  option-data access is blocked.

### 2026-06-10 - Phase 12A options/sell-put advisory MVP

Completed:

- Added Phase 12A options configuration defaults and the editable manual
  option-chain CSV at `data/options/manual/options_chain.csv`.
- Added `option_chain_snapshots` and `option_income_reviews` to the required
  SQLite schema.
- Added option-chain storage helpers, latest/list/status helpers, and an
  idempotent sell-put review upsert path.
- Added the read-only options advisory engine:
  - `load-options-chain`
  - `compute-options-income`
  - `compute-options-income --ticker TICKER`
  - `options-status`
- The sell-put review computes mid premium, breakeven, premium yield,
  annualized yield, downside buffer, breakeven buffer, assignment notional,
  liquidity/range warnings, and commentary option-idea links.
- Reference instruments such as commentary-only `SOXL` or `KORU` can be
  reviewed when source-backed option-chain data exists, while staying outside
  scoreable alerts, ranges, portfolio guidance, and execution.
- Extended `refresh-data --daily` with optional, warning-only
  `load-options-chain` and `compute-options-income` steps.
- Added options fields to `status`, daily Markdown report, daily CSV report,
  and the static dashboard.
- Added focused Phase 12A tests for config/schema, CSV parsing, review math,
  classifications, reference-instrument boundaries, CLI/status/report/CSV, and
  dashboard exposure.
- Updated README and `execution_plan.md` to mark Phase 12A complete and keep
  full option-chain automation/margin/execution work deferred.

Verification:

```text
python -m unittest discover -s tests -p test_phase12a_options.py
6 tests passed.

python -m unittest discover -s tests
224 tests passed.
Non-fatal ResourceWarnings appeared, consistent with prior suite behavior.

python -m target_opportunity_monitor init-db
Required tables present: 45/45.

python -m target_opportunity_monitor load-options-chain
Options chain loaded: 0 rows from data\options\manual\options_chain.csv.
Warnings: empty_options_chain.

python -m target_opportunity_monitor compute-options-income
Option income reviews computed: 0 tickers, skipped=0, warnings=0.

python -m target_opportunity_monitor compute-options-income --ticker SOXL
SOXL skipped with missing_option_chain, as expected while the CSV is header-only.

python -m target_opportunity_monitor options-status
Options chain rows: 0.
Option income review tickers: 0.
Read-only advisory: true.

python -m target_opportunity_monitor run-daily
Created reports/2026-06-10-daily-report.md.
Created reports/2026-06-10-daily-report.csv.

python -m target_opportunity_monitor build-dashboard
Dashboard regenerated with 29 rows.

python -m target_opportunity_monitor status
Required tables present: 45/45.
Scoreable assets: 15.
Reference assets: 7.
Options chain rows: 0.
Option income review rows: 0.
Revision evidence decision: collecting_evidence.
```

Boundaries:

- Manual/source-export option-chain data is the Phase 12A MVP input.
- No IBKR option-chain automation yet.
- No order placement, broker writes, automatic execution, assignment handling,
  or margin model.
- No change to equity/ETF scores, alerts, ranges, portfolio guidance,
  notifications, or shadow-signal gating.
- Phase 10D remains gated until analyst revision validation has mature 20d
  evidence and passes the configured evidence gate.

### 2026-06-10 - Phase 11D Codex scheduler intraday automation MVP

Completed:

- Added `scheduler-status` as a TOM-side operations surface for Codex
  automation health.
- `scheduler-status` reports intended Codex jobs, latest `intraday_cycle`,
  latest `daily_refresh`, quote and range freshness, pending notifications,
  failed notification deliveries, latest successful delivery, and latest
  report/dashboard paths.
- Updated existing Codex automations instead of creating duplicates:
  - `tom-intraday-probe`,
  - `tom-morning-check`,
  - `tom-daily-refresh`,
  - `tom-daily-retry`.
- Intraday heartbeat now uses
  `python -m target_opportunity_monitor intraday-cycle --source ibkr --deliver --channel file`.
- Daily/morning jobs now include the Phase 11D status surfaces and preserve the
  status-first conditional retry policy.
- Updated README and `execution_plan.md` with the Phase 11D scheduler workflow.

Verification:

- `python -m unittest discover -s tests -p test_phase11c_intraday_notifications.py`
- `python -m py_compile src\target_opportunity_monitor\cli.py tests\test_phase11c_intraday_notifications.py`
- `python -m target_opportunity_monitor intraday-cycle --source ibkr --deliver --channel file`
- `python -m target_opportunity_monitor intraday-status`
- `python -m target_opportunity_monitor scheduler-status`
- `python -m target_opportunity_monitor refresh-data --daily-only`
- `python -m target_opportunity_monitor run-daily`
- `python -m target_opportunity_monitor build-dashboard`
- `python -m unittest discover -s tests`

Boundaries:

- Codex scheduler is used instead of Windows Task Scheduler.
- File delivery remains the default durable delivery channel.
- IBKR unavailable remains warning-only when daily fallback data is available.
- No broker writes, order placement, automatic execution, options strategy
  engine, ML score impact, or thesis generation.

### 2026-06-10 - Phase 11C intraday operations and notification delivery MVP

Completed:

- Added scheduler-friendly `intraday-cycle --source ibkr` with optional
  `--ticker`, `--deliver`, `--channel console|file|webhook`, and `--no-deliver`.
- Reused existing `pipeline_runs` and `pipeline_step_results` for intraday
  cycle audit instead of adding a parallel run table.
- Added durable file notification delivery under
  `data/notifications/outbox/`, writing JSONL and readable Markdown artifacts.
- Added optional webhook delivery using `TOM_NOTIFICATION_WEBHOOK_URL`; missing
  or failed webhook delivery records failed delivery rows without printing or
  persisting the URL.
- Added `test-notification-channel`, `notification-status --pending-only`, and
  `intraday-status`.
- Extended `status`, Markdown reports, CSV/dashboard health data, and README
  docs with intraday cycle and notification delivery health.

Verification:

- `python -m unittest discover -s tests -p test_phase11c_intraday_notifications.py`
- `python -m unittest discover -s tests -p test_phase11a_ranges.py`
- `python -m target_opportunity_monitor intraday-cycle --source ibkr`
- `python -m target_opportunity_monitor intraday-cycle --source ibkr --deliver --channel file`
- `python -m target_opportunity_monitor notification-status --pending-only`
- `python -m target_opportunity_monitor test-notification-channel --channel console`
- `python -m target_opportunity_monitor intraday-status`
- `python -m target_opportunity_monitor run-daily`
- `python -m target_opportunity_monitor build-dashboard`
- `python -m unittest discover -s tests`

Boundaries:

- No broker writes, order placement, automatic execution, options strategy
  engine, ML score impact, or thesis generation.
- File delivery is the default durable notification channel.
- Webhook delivery remains optional and env-var gated.
- Phase 10D remains gated until analyst-revision 20d evidence matures.

### 2026-06-10 - Phase 10G.4 short interest missing row resolution MVP

Completed:

- Added `resolve-short-interest-missing-sources` and
  `resolve-short-interest-missing-sources --ticker TICKER`.
- The resolver targets only active equities still missing short-interest source
  rows, rechecks official/cache provider paths, refreshes
  `data/signals/source_exports/short_interest/missing_provider_short_interest_backfill.csv`,
  and recomputes missing-coverage diagnostics.
- Extended provider diagnostics with blank placeholder counts so the live
  blocker distinguishes empty templates from malformed or valid source rows.
- Tightened apply output with explicit projected coverage improvement.
- Updated README, `DOCS/short-interest-source-workflow.md`, and
  `execution_plan.md` with the Phase 10G.4 workflow and no-fabrication boundary.

Verification:

- `python -m py_compile src\target_opportunity_monitor\short_interest.py src\target_opportunity_monitor\cli.py tests\test_phase10g_short_interest.py`
- `python -m unittest discover -s tests -p test_phase10g_short_interest.py`
- `python -m target_opportunity_monitor resolve-short-interest-missing-sources --provider finra --use-cache`
- `python -m target_opportunity_monitor short-interest-provider-diagnostics --ticker CRM`
- `python -m target_opportunity_monitor apply-short-interest-provider-backfill`
- `python -m target_opportunity_monitor refresh-data --daily-only`
- `python -m unittest discover -s tests`

Live state after implementation:

- Required tables remain `43/43`.
- Short-interest source-backed coverage remains `9/13`.
- Missing short-interest tickers remain `CRM`, `JPM`, `LLY`, and `ORCL`.
- Live FINRA resolution attempt returned no normalized rows for those four
  tickers and surfaced provider warnings instead of fabricating data.
- Confirmed apply remains blocked until at least one valid source-backed missing
  row exists.

Boundaries:

- No fabricated short-interest values.
- No score, alert, range, portfolio, notification, broker, or execution impact.
- Short-interest remains shadow-only.

### 2026-06-10 - Phase 10G.3 short interest coverage closure MVP

Completed:

- Added focused short-interest missing-coverage commands:
  - `short-interest-missing-coverage-plan`,
  - `short-interest-provider-diagnostics --ticker TICKER`,
  - `export-short-interest-missing-provider-template`,
  - `apply-short-interest-provider-backfill [--confirm]`.
- Added missing-provider diagnostics that classify uncovered tickers as
  `official_fetch_missing`, `provider_export_needed`, `manual_exchange_needed`,
  `malformed_source_row`, or `etf_gated`.
- Added a focused missing-provider template:
  `data/signals/source_exports/short_interest/missing_provider_short_interest_backfill.csv`.
- Added guarded apply behavior:
  - dry-run by default,
  - confirmed apply exits nonzero if invalid rows exist,
  - confirmed apply exits nonzero if no currently missing ticker has a valid
    source-backed row,
  - existing already-covered provider rows do not count as coverage progress.
- Extended status, daily Markdown/CSV, and dashboard health with:
  - missing short-interest coverage tickers,
  - valid missing-row tickers,
  - provider diagnostic status,
  - missing-provider template path,
  - missing-coverage blocked apply reason.
- Updated README and `DOCS/short-interest-source-workflow.md` with the Phase
  10G.3 closure workflow and no-fabrication rule.

Verification:

- `python -m py_compile src\target_opportunity_monitor\short_interest.py src\target_opportunity_monitor\cli.py src\target_opportunity_monitor\reporting.py src\target_opportunity_monitor\dashboard.py tests\test_phase10g_short_interest.py`
- `python -m unittest discover -s tests -p test_phase10g_short_interest.py`
- `python -m target_opportunity_monitor short-interest-missing-coverage-plan`
- `python -m target_opportunity_monitor short-interest-provider-diagnostics --ticker CRM`
- `python -m target_opportunity_monitor export-short-interest-missing-provider-template`
- `python -m target_opportunity_monitor apply-short-interest-provider-backfill`
- `python -m target_opportunity_monitor apply-short-interest-provider-backfill --confirm`
  intentionally blocked with `no_valid_missing_short_interest_rows`.
- `python -m target_opportunity_monitor status`

Live state after implementation:

- Required tables: `43/43`.
- Short-interest source-backed coverage: `9/13`.
- Missing short-interest tickers: `CRM`, `JPM`, `LLY`, `ORCL`.
- Provider diagnostic status:
  `CRM:official_fetch_missing`, `JPM:official_fetch_missing`,
  `LLY:official_fetch_missing`, `ORCL:official_fetch_missing`.
- Focused missing-provider template exists and contains blank placeholders for
  the four missing tickers.
- Phase 10D remains gated because analyst-revision evidence is still
  `collecting_evidence`.

Boundaries:

- No fabricated short-interest values.
- No score, alert, range, portfolio, notification, broker, or execution impact.
- Short-interest remains shadow-only.

### 2026-06-10 - Phase 10H.5 Discord official commentary input MVP

Completed:

- Added disabled-by-default Discord commentary capture config:
  - `paths.trader_commentary_discord_capture =
    "data/signals/discord_captures/trader_commentary"`,
  - `[commentary_discord_capture] enabled = false`,
  - `provider = "discord_gateway"`,
  - `channel_ids = []`,
  - `max_messages_per_run = 100`,
  - `min_seconds_between_runs = 900`,
  - `require_operator_acknowledgement = true`.
- Added required SQLite tables, bringing live required-table coverage to
  `43/43`:
  - `trader_commentary_discord_capture_runs`,
  - `trader_commentary_discord_capture_items`.
- Added `discord_commentary.py`:
  - captures Discord messages through the official bot/API route,
  - reads `DISCORD_BOT_TOKEN` from environment only,
  - blocks live capture when config is disabled, channel ID is missing, token is
    missing, or operator acknowledgement is missing,
  - stores run artifacts under
    `data\signals\discord_captures\trader_commentary\YYYY-MM-DD\run-id`,
  - dedupes by Discord message ID with hash fallback,
  - preserves attachment metadata counts only,
  - ingests accepted items into `trader_commentary_raw` with
    `source = "discord_bot_capture"` and `platform = "discord"`.
- Added CLI commands:
  - `discord-capture-commentary-status`,
  - `discord-capture-commentary`,
  - `ingest-discord-captured-commentary`.
- Added a non-blocking daily pipeline ingestion step:
  - `ingest-discord-captured-commentary`.
  - Daily refresh does not fetch Discord by itself.
- Extended `status`, daily Markdown/CSV reports, and the static dashboard with
  Discord capture run/item counts, latest capture timestamp, enabled state, and
  source-health warnings.
- Updated README, `DOCS/trader-commentary-source-workflow.md`, and
  `execution_plan.md`.

Verification:

```powershell
python -m py_compile src\target_opportunity_monitor\discord_commentary.py src\target_opportunity_monitor\cli.py src\target_opportunity_monitor\pipeline.py src\target_opportunity_monitor\reporting.py src\target_opportunity_monitor\dashboard.py tests\test_phase10h5_discord_capture.py
python -m unittest discover -s tests -p test_phase10h5_discord_capture.py
python -m unittest discover -s tests -p test_phase10h2_browser_capture.py
python -m unittest discover -s tests -p test_phase10h_trader_commentary.py
python -m unittest discover -s tests -p test_phase10h3_commentary_onboarding.py
python -m unittest discover -s tests
python -m target_opportunity_monitor init-db
python -m target_opportunity_monitor discord-capture-commentary-status
python -m target_opportunity_monitor ingest-discord-captured-commentary
python -m target_opportunity_monitor status
python -m target_opportunity_monitor run-daily
python -m target_opportunity_monitor build-dashboard
```

Observed live state:

- Required tables: `43/43`.
- Discord capture enabled: `False`.
- Discord configured channels: `0`.
- Discord bot token present in current process: `False`.
- Discord capture run rows: `0`.
- Discord capture item rows: `0`.
- Daily report and dashboard regenerated with Discord capture fields.
- Full regression: `207` tests passed.

Boundaries:

- No Discord browser automation, scraping, permission bypass, score impact,
  alert impact, range impact, portfolio guidance impact, broker writes, or
  execution.
- Commentary remains shadow-only.
- Live capture requires future user-supplied bot token, channel allowlist, and
  operator acknowledgement.

### 2026-06-10 - Phase 10H.4 commentary reference instrument activation MVP

Completed:

- Applied the confirmed commentary onboarding template for seven reference
  instruments:
  - `BRK.B`
  - `HOOD`
  - `KORU`
  - `SOXL`
  - `TSLA`
  - `XLF`
  - `XLV`.
- Kept all seven as `asset_role = commentary_validation`, not scoreable assets.
- Left the two alias placeholders unmapped because no canonical ticker was
  supplied for `unmapped_context` or `大盘`.
- Loaded Yahoo-backed daily price history and price features for all seven
  reference instruments.
- Fixed class-share market-data symbol handling:
  - Stooq now maps US class-share tickers such as `BRK.B` to `brk.b.us`.
  - Yahoo Chart now maps dotted tickers such as `BRK.B` to `BRK-B`.
- Reran trader-commentary validation:
  - ticker-mapped commentary claims now update as pending validation outcomes,
  - unmapped/context claims remain explicitly skipped with
    `unmapped_instrument`.
- Refreshed the commentary onboarding template so it now contains only the two
  alias placeholders.
- Regenerated the daily Markdown/CSV reports and static dashboard.
- Updated README, `DOCS/trader-commentary-source-workflow.md`, and
  `execution_plan.md`.

Verification:

```powershell
python -m target_opportunity_monitor commentary-onboarding-status
python -m target_opportunity_monitor verify-universe
python -m target_opportunity_monitor apply-commentary-onboarding --file data\signals\source_exports\trader_commentary\commentary_onboarding_template.csv --confirm
python -m target_opportunity_monitor update-prices --ticker TSLA
python -m target_opportunity_monitor update-prices --ticker HOOD
python -m target_opportunity_monitor update-prices --ticker BRK.B
python -m target_opportunity_monitor update-prices --ticker SOXL
python -m target_opportunity_monitor update-prices --ticker KORU
python -m target_opportunity_monitor update-prices --ticker XLV
python -m target_opportunity_monitor update-prices --ticker XLF
python -m unittest discover -s tests -p test_phase2.py
python -m target_opportunity_monitor validate-trader-commentary-claims
python -m target_opportunity_monitor trader-commentary-validation-report
python -m target_opportunity_monitor export-commentary-onboarding-template
python -m target_opportunity_monitor run-daily
python -m target_opportunity_monitor build-dashboard
python -m target_opportunity_monitor status
```

Observed live state:

- Active assets: `22`.
- Scoreable assets: `15`.
- Reference assets: `7`.
- Reference tickers: `BRK.B`, `HOOD`, `KORU`, `SOXL`, `TSLA`, `XLF`, `XLV`.
- `verify-universe`: `15/15` ready, `0` warnings.
- Price rows after activation: `12098`.
- Latest price date: `2026-06-09`.
- Trader commentary claim outcome rows: `30`.
- Trader commentary validation result: `22` updated, `8` skipped.
- Pending commentary outcome rows: `22`.
- Unmapped commentary instrument labels: `2`.
- Commentary onboarding candidates: `0`.
- Alias mappings: `0`.

Notes:

- Reference instruments are now useful for commentary validation but remain out
  of valuation, scoring, alerts, range notifications, and portfolio guidance.
- ETF/levered ETF commentary validation remains price-proxy-only and carries
  `etf_trader_commentary_validation_gated` where applicable.
- Phase 10D remains gated until analyst-revision evidence matures.

### 2026-06-10 - Phase 10H.3 commentary asset onboarding and instrument mapping MVP

Completed:

- Added asset role support:
  - `scoreable`
  - `commentary_validation`
  - `regime_proxy`
  - `inactive`.
- Migrated the `assets` table with `asset_role`, defaulting existing assets to
  `scoreable`.
- Kept valuation, scoring, alerts, portfolio context, range monitoring,
  readiness, and core advanced-signal computation on scoreable active assets.
- Allowed price ingestion and trader-commentary validation to use active
  reference instruments.
- Added the required `trader_commentary_instrument_aliases` table, bringing live
  required table coverage to `41/41`.
- Added `commentary_onboarding.py`:
  - builds onboarding candidates from parsed trader-commentary claims,
  - distinguishes unsupported but onboardable tickers from unmapped labels,
  - exports a fillable onboarding template,
  - applies confirmed reference/scoreable onboarding rows idempotently,
  - loads explicit instrument-label aliases.
- Added CLI commands:
  - `commentary-onboarding-plan`
  - `commentary-onboarding-status`
  - `export-commentary-onboarding-template`
  - `apply-commentary-onboarding --file PATH`
  - `apply-commentary-onboarding --file PATH --confirm`
  - `load-commentary-instrument-aliases`.
- Updated `status`, daily Markdown/CSV reports, and dashboard health data with:
  - scoreable asset count,
  - reference asset count,
  - commentary onboarding candidate count,
  - unmapped commentary instrument count,
  - alias mapping count.
- Updated `trader-commentary-parse-review` to distinguish unsupported
  onboardable tickers from reference-instrument claims.
- Updated README, `DOCS/trader-commentary-source-workflow.md`, and
  `execution_plan.md`.

Verification:

```powershell
python -m py_compile src\target_opportunity_monitor\commentary_onboarding.py src\target_opportunity_monitor\storage.py src\target_opportunity_monitor\cli.py src\target_opportunity_monitor\reporting.py src\target_opportunity_monitor\dashboard.py src\target_opportunity_monitor\trader_commentary.py tests\test_phase10h3_commentary_onboarding.py
python -m unittest discover -s tests -p test_phase10h3_commentary_onboarding.py
python -m unittest discover -s tests -p test_phase10h_trader_commentary.py
python -m unittest discover -s tests -p test_phase10h2_browser_capture.py
python -m unittest discover -s tests -p test_phase11a_ranges.py
python -m unittest discover -s tests
python -m target_opportunity_monitor init-db
python -m target_opportunity_monitor load-commentary-instrument-aliases
python -m target_opportunity_monitor commentary-onboarding-plan
python -m target_opportunity_monitor commentary-onboarding-status
python -m target_opportunity_monitor export-commentary-onboarding-template
python -m target_opportunity_monitor apply-commentary-onboarding --file data\signals\source_exports\trader_commentary\commentary_onboarding_template.csv
python -m target_opportunity_monitor trader-commentary-parse-review
python -m target_opportunity_monitor run-daily
python -m target_opportunity_monitor build-dashboard
python -m target_opportunity_monitor status
```

Observed live state:

- Required tables present: `41/41`.
- Active assets: `15`.
- Scoreable assets: `15`.
- Reference assets: `0`.
- Trader commentary raw rows: `5`.
- Trader commentary parsed claim rows: `30`.
- Trader commentary claim outcome rows: `30`.
- Commentary onboarding candidates: `7`.
- Unmapped commentary instrument labels: `2`.
- Alias mappings: `0`.
- Exported template:
  `data\signals\source_exports\trader_commentary\commentary_onboarding_template.csv`.
- Dry-run apply found `9` actionable rows and made no live asset or alias
  changes.

Notes:

- Current onboarding candidates are `BRK.B`, `HOOD`, `KORU`, `SOXL`, `TSLA`,
  `XLF`, and `XLV`.
- Current unmapped labels remain unmapped until explicitly aliased.
- Commentary remains shadow-only and does not change final scores, alerts,
  ranges, portfolio guidance, notifications, broker writes, or execution.

### 2026-06-10 - Phase 10H.2 X browser capture fallback MVP

Completed:

- Added disabled-by-default browser capture config:
  - `paths.trader_commentary_browser_capture =
    "data/signals/browser_captures/trader_commentary"`
  - `[commentary_browser_capture] enabled = false`
  - `provider = "x_browser"`
  - `target_urls = []`
  - `max_scroll_batches = 3`
  - `min_seconds_between_runs = 900`
  - `require_operator_acknowledgement = true`.
- Added two required SQLite tables, bringing required table coverage to
  `40/40`:
  - `trader_commentary_browser_capture_runs`
  - `trader_commentary_browser_capture_items`.
- Added `browser_commentary.py`:
  - records run artifacts under
    `data\signals\browser_captures\trader_commentary\YYYY-MM-DD\run-id`,
  - writes `dom_text.txt`, optional `page.html`, `items.json`, and
    `run_metadata.json`,
  - parses mocked/rendered X visible text into post-like items,
  - dedupes by X status id when visible, otherwise stable text hash,
  - detects obvious login/captcha/rate-limit/block pages as partial runs,
  - keeps warnings such as `browser_capture_fragile`, `x_api_not_used`,
    `manual_auth_required`, `capture_may_be_incomplete`, and
    `terms_risk_acknowledgement_required`.
- Added storage helpers for capture runs/items, latest capture timestamp, and
  mark-ingested behavior.
- Added CLI:
  - `browser-capture-commentary --provider x_browser`
  - `browser-capture-commentary --provider x_browser --target-url URL`
  - `browser-capture-commentary-status`
  - `ingest-browser-captured-commentary`.
- Added optional `--dom-text-file` and `--page-html-file` inputs so Codex
  Browser/manual visible-text artifacts can be stored and tested without
  embedding fragile browser automation inside the Python CLI.
- Integrated ingestion into `refresh-data --daily`; daily refresh does not
  browse X, but it ingests already accepted captured items before parsing
  commentary claims.
- Extended `status`, daily Markdown, daily CSV, and dashboard health with
  browser capture run/item/latest-capture fields.
- Documented the Phase 10H.2 boundaries:
  - opt-in and low-frequency only,
  - no bypassing login, captcha, rate limits, paywalls, or technical
    restrictions,
  - if X blocks or requires auth, record a partial/failed run and stop,
  - Discord remains separate for a future official bot/Gateway route,
  - no WeChat browser-capture plan in this slice,
  - all captured commentary remains shadow-only.

Verification:

```text
python -m py_compile src\target_opportunity_monitor\browser_commentary.py src\target_opportunity_monitor\cli.py src\target_opportunity_monitor\pipeline.py src\target_opportunity_monitor\reporting.py src\target_opportunity_monitor\dashboard.py tests\test_phase10h2_browser_capture.py
python -m unittest discover -s tests -p test_phase10h2_browser_capture.py
python -m unittest discover -s tests -p test_phase10h_trader_commentary.py
python -m unittest discover -s tests
python -m target_opportunity_monitor init-db
python -m target_opportunity_monitor browser-capture-commentary-status
python -m target_opportunity_monitor ingest-browser-captured-commentary
python -m target_opportunity_monitor run-daily
python -m target_opportunity_monitor build-dashboard
python -m target_opportunity_monitor status
```

Observed live state after verification:

```text
Required tables present: 40/40.
Active assets: 15.
Trader commentary raw rows: 5.
Trader commentary parsed claim rows: 30.
Trader commentary claim outcome rows: 30.
Trader commentary browser capture run rows: 0.
Trader commentary browser capture item rows: 0.
Browser capture enabled: False.
Latest report: reports\2026-06-09-daily-report.md.
Latest CSV report: reports\2026-06-09-daily-report.csv.
Latest dashboard: dashboard\index.html.
Full regression: 197 tests OK.
```

Notes:

- I intentionally did not seed fake X posts into the live TOM database. The
  mocked X visible-text capture path is covered by deterministic tests.
- Manual browser capture should only be scheduled after a real operator-approved
  target URL and visible-text artifact flow works.
- Phase 10D remains gated until analyst revision 20d validation evidence
  matures.

### 2026-06-10 - Phase 10H.1 commentary seeding and parser review MVP

Completed:

- Seeded the user-provided Chinese commentary examples as UTF-8 text captures
  under `data\signals\source_exports\trader_commentary`.
- Updated `data\signals\manual\trader_commentary.csv` with five authorized
  local capture rows:
  - `source = user_paste`
  - `source_author = unknown_trader`
  - `platform = wechat_or_chat_capture`
  - `permission_scope = user_provided_private_capture`
  - local `capture_id` values instead of public URLs.
- Added `export-trader-commentary-template` to create a ready-to-fill
  commentary CSV plus UTF-8 text-file template.
- Added `trader-commentary-parse-review` to summarize:
  - parsed claim count,
  - ticker-mapped claims,
  - unmapped market/context claims,
  - unsupported tickers,
  - ETF-gated claims,
  - option proxy claims,
  - parser warning counts and examples.
- Tightened parser behavior after reviewing the seeded examples:
  - excluded phrase tokens such as `SELL`, `LOWER`, and `HIGH` from ticker
    extraction,
  - inherited recent tickers for adjacent support/resistance statements such as
    TSLA's 416-418 pressure range.
- Extended commentary validation so unmapped and unsupported claims create
  explicit `skipped` outcome rows instead of disappearing from validation
  coverage.
- Kept commentary shadow-only:
  - no score impact,
  - no alert impact,
  - no range override,
  - no portfolio guidance impact,
  - no notifications beyond local report/dashboard visibility,
  - no broker writes,
  - no execution.

Verification:

```text
python -m compileall src\target_opportunity_monitor tests\test_phase10h_trader_commentary.py
python -m unittest discover -s tests -p test_phase10h_trader_commentary.py
python -m target_opportunity_monitor init-db
python -m target_opportunity_monitor export-trader-commentary-template
python -m target_opportunity_monitor load-trader-commentary
python -m target_opportunity_monitor parse-trader-commentary-claims
python -m target_opportunity_monitor trader-commentary-parse-review
python -m target_opportunity_monitor validate-trader-commentary-claims
python -m target_opportunity_monitor trader-commentary-status
python -m target_opportunity_monitor trader-commentary-validation-report
python -m target_opportunity_monitor refresh-data --daily-only
python -m target_opportunity_monitor run-daily
python -m target_opportunity_monitor build-dashboard
python -m target_opportunity_monitor status
python -m unittest discover -s tests
```

Observed live state after commentary replay:

```text
Required tables present: 38/38.
Active assets: 15.
Trader commentary raw rows: 5.
Trader commentary parsed claim rows: 30.
Trader commentary claim outcome rows: 30.
Unsupported commentary tickers surfaced: BRK.B, HOOD, KORU, SOXL, TSLA, XLF, XLV.
All current commentary outcomes are skipped because the surfaced tickers are
not active TOM assets, or because the claim is unmapped market/context text.
Latest report: reports\2026-06-09-daily-report.md.
Latest CSV report: reports\2026-06-09-daily-report.csv.
Latest dashboard: dashboard\index.html.
Full regression: 191 tests OK.
```

Notes:

- The seeded examples are now evidence-producing as auditable raw/commentary
  claim rows, but not yet price-validating because the mentioned symbols are not
  in the active TOM universe.
- `大盘` remains unmapped by design until a future explicit mapping table exists.
- Phase 10D remains gated until analyst revision 20d validation evidence matures.
- The next practical follow-up is Phase 10H.2 commentary-driven asset
  onboarding/mapping, or another shadow-signal data-quality task.

### 2026-06-10 - Phase 10H trader commentary input shadow signals MVP

Completed:

- Added Phase 10H config defaults:
  - `paths.trader_commentary = "data/signals/manual/trader_commentary.csv"`
  - `paths.trader_commentary_exports = "data/signals/source_exports/trader_commentary"`
  - `signals.trader_commentary_model_version = "trader_commentary_mvp_v1"`
  - `signals.trader_commentary_shadow_mode = true`
  - default commentary validation horizons `1d`, `5d`, `20d`, and `60d`.
- Added required storage tables, bringing required table coverage to `38/38`:
  - `trader_commentary_raw`
  - `trader_commentary_claims`
  - `trader_commentary_claim_outcomes`
- Added typed storage helpers for raw commentary, parsed claims, claim outcomes,
  latest dates, and ticker-level commentary status.
- Added `trader_commentary.py`:
  - creates the default commentary CSV and export directory,
  - loads inline `raw_text` or UTF-8 `text_file` inputs,
  - preserves source author, platform, permission scope, source URL or capture ID,
    notes, and warning metadata,
  - deterministically parses Chinese and English support/resistance, target,
    downside, action, sector/catalyst, and sell-put claims,
  - supports recent ticker inheritance for adjacent target/action/risk sentences,
  - keeps unmapped labels such as `大盘` as `instrument_label` with
    `unmapped_instrument`,
  - validates claims against stored local prices without options P&L,
  - writes compact shadow rows to `signals` for `trader_commentary.levels`,
    `trader_commentary.direction`, `trader_commentary.action`, and
    `trader_commentary.composite`.
- Added CLI commands:
  - `load-trader-commentary`
  - `parse-trader-commentary-claims`
  - `parse-trader-commentary-claims --commentary-id ID`
  - `parse-trader-commentary-claims --ticker TSLA`
  - `validate-trader-commentary-claims`
  - `validate-trader-commentary-claims --ticker TSLA`
  - `trader-commentary-status`
  - `trader-commentary-validation-report`
- Wired `refresh-data --daily` to run commentary load, parse, and validation
  before final reports/dashboard.
- Extended `status`, daily Markdown reports, daily CSV reports, and the static
  dashboard with commentary raw rows, parsed claims, outcomes, latest dates,
  per-ticker claim counts, validation status, hit status, and warnings.
- Added `DOCS/trader-commentary-source-workflow.md` and README documentation for
  capture rules, CSV/text-file inputs, parser limits, validation behavior, and
  no-score-impact boundaries.
- Kept Phase 10H shadow-only:
  - no score impact,
  - no alert impact,
  - no range override,
  - no portfolio guidance impact,
  - no broker writes,
  - no execution.

Verification:

```text
python -m compileall src\target_opportunity_monitor tests\test_phase10h_trader_commentary.py
python -m unittest discover -s tests -p test_phase10h_trader_commentary.py
python -m unittest discover -s tests
python -m target_opportunity_monitor init-db
python -m target_opportunity_monitor load-trader-commentary
python -m target_opportunity_monitor parse-trader-commentary-claims
python -m target_opportunity_monitor validate-trader-commentary-claims
python -m target_opportunity_monitor trader-commentary-status
python -m target_opportunity_monitor trader-commentary-validation-report
python -m target_opportunity_monitor run-daily
python -m target_opportunity_monitor build-dashboard
python -m target_opportunity_monitor status
```

Observed live state after verification:

```text
Required tables present: 38/38.
Active assets: 15.
Trader commentary raw rows: 0.
Trader commentary parsed claim rows: 0.
Trader commentary claim outcome rows: 0.
Default commentary CSV exists at data\signals\manual\trader_commentary.csv.
Default commentary export directory exists at data\signals\source_exports\trader_commentary.
Latest report: reports\2026-06-09-daily-report.md.
Latest CSV report: reports\2026-06-09-daily-report.csv.
Latest dashboard: dashboard\index.html.
Full regression: 189 tests OK.
```

Notes:

- The live commentary CSV is header-only, so Phase 10H is workflow-ready but not
  evidence-producing until authorized commentary rows are added.
- Empty commentary input is warning-only and does not degrade the daily pipeline.
- Phase 10D remains gated until analyst revision 20d validation evidence matures.
- The next practical follow-up is either Phase 10H.1 real commentary seeding and
  parser-miss review, continued provider-native news/catalyst upgrades, or
  waiting for Phase 10D evidence eligibility.

### 2026-06-09 - Phase 11B technical and market regime signal engine MVP

Completed:

- Added Phase 11B config defaults:
  - `technical.model_version = "technical_levels_mvp_v1"`
  - technical lookback, minimum history, moving-average, pivot, near-level, and
    breakout-buffer settings.
  - `regime.model_version = "market_regime_mvp_v1"`
  - benchmark tickers `SPY`, `QQQ`, sector proxy tickers, and relative-strength
    lookback settings.
- Added required storage tables, bringing required table coverage to `35/35`:
  - `technical_signal_snapshots`
  - `regime_signal_snapshots`
- Migration-safely extended `range_snapshots` with technical/regime context:
  support and resistance zones, breakout/downside/trend-repair levels,
  moving-average state, drawdown state, price-location state, regime state,
  relative strength, sector-rotation rank, and confidence fields.
- Added technical and regime storage helpers and status helpers.
- Added `technical.py`:
  - computes support/resistance from pivots and recent lows/highs,
  - computes moving-average state, drawdown state, price-location state,
  - stores compact shadow rows in `signals` for `technical.trend` and
    `technical.levels`,
  - computes benchmark and sector-proxy regime snapshots,
  - stores compact shadow rows in `signals` for `regime.market` and
    `regime.sector_rotation`.
- Added CLI commands:
  - `compute-technical-signals`
  - `compute-technical-signals --ticker AAPL`
  - `compute-regime-signals`
  - `technical-status`
  - `regime-status`
- Wired `refresh-data --daily` to run `compute-technical-signals` and
  `compute-regime-signals` before `range-monitor`.
- Extended `range-monitor` and `range-status` with technical/regime fields and
  warnings such as `near_support`, `support_failed`, `near_resistance`,
  `resistance_breakout`, `trend_repair_needed`, and `regime_risk_off`.
- Extended daily Markdown reports, daily CSV reports, `status`, and the static
  dashboard with technical/regime status, levels, confidence, and warnings.
- Kept Phase 11B read-only and shadow/range-modifier only:
  - no order placement,
  - no broker writes,
  - no long-form thesis generation,
  - no automatic score impact from technical/regime signals.

Verification:

```text
python -m compileall src/target_opportunity_monitor
python -m unittest discover -s tests -p test_phase11b_technical_regime.py
python -m unittest discover -s tests -p test_phase6a_reporting.py
python -m unittest discover -s tests
python -m target_opportunity_monitor init-db
python -m target_opportunity_monitor compute-technical-signals
python -m target_opportunity_monitor compute-regime-signals
python -m target_opportunity_monitor technical-status
python -m target_opportunity_monitor regime-status
python -m target_opportunity_monitor range-monitor --source ibkr
python -m target_opportunity_monitor range-status
python -m target_opportunity_monitor run-daily
python -m target_opportunity_monitor build-dashboard
python -m target_opportunity_monitor status
python -m target_opportunity_monitor refresh-data --daily-only
```

Observed live state after verification:

```text
Required tables present: 35/35.
Active assets: 15.
Technical signal snapshot rows: 15.
Latest technical signal date: 2026-06-09.
Regime signal snapshot rows: 11.
Latest regime signal date: 2026-06-09.
Range snapshot rows: 47 after the daily pipeline.
Latest report: reports\2026-06-09-daily-report.md.
Latest CSV report: reports\2026-06-09-daily-report.csv.
Latest dashboard: dashboard\index.html.
Full regression: 184 tests OK.
```

Notes:

- Live technical snapshots computed for all 15 active assets without warnings.
- Live regime snapshots computed for SPY and QQQ. Configured sector proxies
  (`XLK`, `XLY`, `XLV`, `XLF`, `XLI`, `XLP`, `XLU`, `XLE`, `XLC`) currently
  report `missing_sector_proxy_price_history` because those ETFs are not yet in
  the priced universe; this is warning-only.
- Live `range-monitor --source ibkr` degraded safely because the local Python
  environment does not have the `ibapi` package installed. TOM used stored
  daily-price fallback and preserved quote/data warnings.
- Browser automation could not reload the `file://` dashboard because the
  in-app Browser URL policy blocked file navigation. Dashboard verification was
  completed by checking the generated `dashboard/index.html` contents on disk.
- The next recommended product phase is Phase 10H trader commentary input
  shadow signals. Phase 10D remains gated until analyst revision 20d validation
  evidence matures.

### 2026-06-09 - Phase 11A near-real-time range monitor and notifications MVP

Completed:

- Added realtime/range-monitor config defaults:
  - `realtime.source = "ibkr"`
  - `realtime.quote_stale_after_seconds = 900`
  - `realtime.range_model_version = "range_monitor_mvp_v1"`
  - `realtime.notification_cooldown_minutes = 60`
  - `realtime.monitor_active_assets_only = true`
- Added required storage tables, bringing required table coverage to `33/33`:
  - `range_snapshots`
  - `notification_events`
  - `notification_deliveries`
  - `asset_change_events`
- Added range snapshot, notification event/delivery, and asset-change storage
  helpers.
- Added `range-monitor` and `range-status`:
  - refreshes read-only quotes when possible,
  - falls back to latest daily prices when quotes are missing or stale,
  - computes equity buy/hold/trim/sell levels,
  - computes ETF NAV/premium-discount range levels,
  - stores one range state per active ticker.
- Added local notification events:
  - deduped by ticker/state/model/cooldown window,
  - stored in `notification_events`,
  - delivered through `deliver-notifications --channel console`,
  - audited in `notification_deliveries`.
- Added asset management commands:
  - `add-asset`
  - `deactivate-asset`
  - `reactivate-asset`
  - `remove-asset --soft`
  - `asset-status`
- Added optional `active` column support to `configs/watchlist.csv`; missing
  values default to active.
- Wired `probe-market` to run range monitoring after quote/gap updates.
- Wired `refresh-data --daily` to include range monitoring before final
  verification, reports, and dashboard generation.
- Extended `status`, daily Markdown reports, daily CSV reports, and the static
  dashboard with range and notification fields.
- Updated README and `execution_plan.md` with Phase 11A commands, boundaries,
  and current next step.
- Kept Phase 11A local and read-only:
  - no order placement,
  - no broker writes,
  - no external email/SMS/chat notifications,
  - no options strategy engine,
  - no advanced-signal score or alert impact.

Verification:

```text
python -m py_compile src\target_opportunity_monitor\ranges.py src\target_opportunity_monitor\notifications.py src\target_opportunity_monitor\storage.py src\target_opportunity_monitor\db.py src\target_opportunity_monitor\config.py
python -m py_compile src\target_opportunity_monitor\cli.py src\target_opportunity_monitor\pipeline.py src\target_opportunity_monitor\watchlist.py
python -m unittest discover -s tests -p test_phase11a_ranges.py
python -m unittest discover -s tests
python -m target_opportunity_monitor init-db
python -m target_opportunity_monitor asset-status --ticker AAPL
python -m target_opportunity_monitor range-monitor --source ibkr --ticker AAPL
python -m target_opportunity_monitor probe-market --source ibkr --ticker AAPL
python -m target_opportunity_monitor range-status --ticker AAPL
python -m target_opportunity_monitor notification-status
python -m target_opportunity_monitor deliver-notifications --channel console
python -m target_opportunity_monitor refresh-data --daily-only
python -m target_opportunity_monitor run-daily
python -m target_opportunity_monitor build-dashboard
python -m target_opportunity_monitor status
```

Observed live state after verification:

```text
Required tables present: 33/33.
Asset count: 15.
Active assets: 15.
Inactive assets: 0.
Range snapshot rows: 17.
Notification event rows: 11.
Pending notifications: 0 after console delivery.
Latest pipeline run: daily_refresh ok.
Latest report: reports\2026-06-09-daily-report.md.
Latest CSV report: reports\2026-06-09-daily-report.csv.
Latest dashboard: dashboard\index.html.
```

Notes:

- The live IBKR quote path degraded safely in verification: one run reported an
  `ibapi_unavailable` local permission warning and another reported IBKR
  `504:Not connected,no_quote_ticks`. Range monitoring still completed by using
  stored daily fallback prices with stale-quote warnings.
- First full-watchlist range monitoring created local notification events for
  actionable first-time states. They were delivered through the console channel
  and marked delivered.
- Phase 11A is not a trading or execution system. It records local range states
  and notification events only.
- The next product phase is Phase 11B technical/regime signals. Phase 10D
  remains gated until analyst revision 20d validation evidence matures.

### 2026-06-09 - Phase 10G.2 official short-interest source fetch and normalization MVP

Completed:

- Added short-interest provider/cache config defaults:
  - `paths.short_interest_cache = "data/signals/cache/short_interest"`
  - `signals.short_interest_provider_order`
  - provider timeout, retry/cache-staleness, max-ticker, and cache-use defaults.
- Added cache-first official/provider source fetch:
  - `fetch-short-interest-sources --provider all|finra|nasdaq_trader`
  - optional `--ticker`, `--use-cache`, `--no-cache`, and `--force-refresh`.
- Added provider-export normalization:
  - `normalize-short-interest-provider-export --provider finra|nasdaq_trader|nyse|broker|generic --file PATH`
  - normalized output writes to
    `data/signals/source_exports/short_interest/provider_export.csv`.
- Added provider status output:
  - `short-interest-provider-status`
  - source-backed coverage, provider-export valid rows/tickers, provider order,
    fetchable/manual-only providers, cache freshness, missing tickers, ETF gating,
    and warnings.
- Integrated the short-interest provider fetch/import/load/compute/validate chain
  into `refresh-data --daily`.
- Extended `status`, daily Markdown reports, daily CSV reports, and the static
  dashboard with short-interest provider cache/export/warning fields.
- Updated README and `DOCS/short-interest-source-workflow.md` with official
  source priority, cache-first behavior, export normalization, and no-fabrication
  rules.
- Kept short-interest signals shadow-only with no score, alert, portfolio,
  notification, broker, or execution impact.

Verification:

```text
python -m py_compile src\target_opportunity_monitor\short_interest.py src\target_opportunity_monitor\cli.py src\target_opportunity_monitor\reporting.py src\target_opportunity_monitor\dashboard.py tests\test_phase10g_short_interest.py
python -m unittest discover -s tests -p test_phase10g_short_interest.py
python -m unittest discover -s tests
python -m target_opportunity_monitor init-db
python -m target_opportunity_monitor short-interest-provider-status
python -m target_opportunity_monitor fetch-short-interest-sources --provider all
python -m target_opportunity_monitor import-short-interest-source-exports
python -m target_opportunity_monitor load-short-interest
python -m target_opportunity_monitor compute-short-interest-signals
python -m target_opportunity_monitor validate-short-interest-signals
python -m target_opportunity_monitor short-interest-status
python -m target_opportunity_monitor refresh-data --daily-only
python -m target_opportunity_monitor run-daily
python -m target_opportunity_monitor build-dashboard
python -m target_opportunity_monitor status
```

Observed live state after verification:

```text
Required tables present: 29/29.
Asset count: 15.
Provider fetch normalized 207 short-interest rows.
Short interest source rows: 207.
Short interest source-backed tickers: 9/13.
Short interest provider export valid rows: 207.
Short interest provider export tickers: AAPL, AMD, AMZN, AVGO, COST, GOOGL, META, MSFT, NVDA.
Missing short-interest source tickers: CRM, JPM, LLY, ORCL.
Short-interest validation rows: 9.
SPY/QQQ are ETF-gated for short interest.
Analyst revision evidence decision: collecting_evidence.
News/catalyst total numeric coverage: 13/13.
News/catalyst provider numeric ticker coverage: 1/13.
Insider activity source coverage: 13/13.
```

Notes:

- Direct FINRA fetch returned HTTP 404 in the live run; Nasdaq-style provider
  payloads covered 9 active equities.
- CRM/JPM/LLY/ORCL still need broker, exchange, NYSE, or provider export
  normalization because the live direct provider payloads were empty.
- Short-interest provider/export values remain shadow-only evidence.
- Phase 10D remains gated until analyst revision 20d validation evidence
  matures and passes the configured evidence gate.

### 2026-06-09 - Phase 10G.1 short-interest source coverage and import workflow MVP

Completed:

- Added the short-interest source-export directory
  `data/signals/source_exports/short_interest/`.
- Added source-export templates:
  - `provider_export.csv`
  - `exchange_manual.csv`
  - `broker_manual.csv`
  - `missing_short_interest_backfill.csv`
- Added `export-short-interest-backfill` to generate one blank auditable row
  per missing active equity ticker while excluding SPY/QQQ as ETF-gated.
- Added strict source-export validation for ticker, settlement date, source,
  source URL, numeric evidence, supported active equity status, malformed
  dates, malformed numbers, and ETF gating.
- Added derived `percent_float` and `days_to_cover` support through the
  source-export import path when enough source-backed numeric inputs are
  present.
- Added `import-short-interest-source-exports` with idempotent merge behavior
  into `data/signals/manual/short_interest.csv`, keyed by
  `ticker + settlement_date + source`.
- Added coverage and preview commands:
  - `short-interest-coverage-plan`
  - `short-interest-source-status --missing-only`
  - `validate-short-interest-backfill`
  - `preview-short-interest-import`
  - `import-short-interest-source-exports`
- Extended `status`, daily Markdown reports, daily CSV reports, and the static
  dashboard with short-interest backfill coverage, valid rows, invalid rows,
  blank placeholders, projected coverage, apply readiness, valid import
  tickers, and blocked import reason.
- Updated README and `DOCS/short-interest-source-workflow.md` with the
  source-export templates, validation rules, safe command sequence, and
  no-fabrication rule.
- Kept short interest shadow-only with no final score, alert, portfolio,
  notification, broker, or execution impact.

Verification:

```text
python -m py_compile src\target_opportunity_monitor\short_interest.py src\target_opportunity_monitor\cli.py src\target_opportunity_monitor\reporting.py src\target_opportunity_monitor\dashboard.py
python -m unittest discover -s tests -p test_phase10g_short_interest.py
python -m unittest discover -s tests
python -m target_opportunity_monitor init-db
python -m target_opportunity_monitor export-short-interest-backfill
python -m target_opportunity_monitor validate-short-interest-backfill
python -m target_opportunity_monitor preview-short-interest-import
python -m target_opportunity_monitor short-interest-coverage-plan
python -m target_opportunity_monitor short-interest-source-status --missing-only
python -m target_opportunity_monitor import-short-interest-source-exports
python -m target_opportunity_monitor load-short-interest
python -m target_opportunity_monitor compute-short-interest-signals
python -m target_opportunity_monitor validate-short-interest-signals
python -m target_opportunity_monitor short-interest-status
python -m target_opportunity_monitor refresh-data --daily-only
python -m target_opportunity_monitor run-daily
python -m target_opportunity_monitor build-dashboard
python -m target_opportunity_monitor status
```

Observed live state after verification:

```text
Required tables present: 29/29.
Asset count: 15.
Latest report: reports\2026-06-09-daily-report.md.
Latest CSV report: reports\2026-06-09-daily-report.csv.
Latest dashboard: dashboard\index.html.
Short interest source export directory exists: True.
Short interest source rows: 0.
Short interest source-backed tickers: 0/13.
Short interest missing source tickers: 13.
Short interest backfill valid rows: 0.
Short interest backfill blank placeholders: 13.
Short interest backfill invalid rows: 0.
Short interest projected source-backed coverage: 0/13.
Short interest backfill apply ready: False.
Short interest blocked import reason: no_valid_short_interest_backfill_rows.
SPY/QQQ are ETF-gated for short interest.
Analyst revision evidence decision: collecting_evidence.
News/catalyst total numeric coverage: 13/13.
News/catalyst provider numeric ticker coverage: 1/13.
Insider activity source coverage: 13/13.
```

Notes:

- Phase 10G.1 closes the short-interest workflow gap, but not the
  short-interest data gap.
- The generated backfill file is intentionally blank until source-backed
  short-interest values are supplied.
- Blank placeholders validate as safe placeholders, while filled rows require
  source URL plus numeric evidence.
- Phase 10D remains gated until analyst revision 20d validation evidence
  matures and passes the configured evidence gate.

### 2026-06-09 - Phase 10G short-interest shadow signals MVP

Completed:

- Updated stale README scope wording from older Phase 10E/10F wording to the
  current Phase 10E.10, Phase 10F.2, and Phase 10G state.
- Added short-interest config defaults and default manual CSV path:
  `data/signals/manual/short_interest.csv`.
- Added required table `short_interest_source_snapshots`, bringing required
  table coverage to `29/29`.
- Added source-backed short-interest CSV parsing/loading with required
  `ticker`, `settlement_date`, `source`, and `source_url` fields.
- Added derived `percent_float` and `days_to_cover` support when enough
  source-backed inputs are present.
- Added active-equity-only gating so SPY/QQQ are marked
  `etf_short_interest_gated`.
- Added short-interest shadow signals in the existing `signals` table:
  `short_interest.level`, `short_interest.days_to_cover`,
  `short_interest.change`, `short_interest.squeeze_setup`, and
  `short_interest.composite`.
- Added short-interest validation through the existing signal-outcome pattern.
- Added CLI commands:
  - `load-short-interest`
  - `compute-short-interest-signals`
  - `validate-short-interest-signals`
  - `short-interest-status`
  - `short-interest-validation-report`
- Wired Phase 10G into `refresh-data --daily` before reports and dashboard.
- Added short-interest status fields to `status`, daily Markdown reports,
  daily CSV reports, and the static dashboard.
- Added `DOCS/short-interest-source-workflow.md`.
- Kept short-interest shadow-only with no score, alert, portfolio,
  notification, broker, or execution impact.

Verification:

```text
python -m unittest discover -s tests -p test_phase10g_short_interest.py
python -m unittest discover -s tests
python -m target_opportunity_monitor init-db
python -m target_opportunity_monitor load-short-interest
python -m target_opportunity_monitor compute-short-interest-signals
python -m target_opportunity_monitor validate-short-interest-signals
python -m target_opportunity_monitor short-interest-status
python -m target_opportunity_monitor short-interest-validation-report
python -m target_opportunity_monitor refresh-data --daily-only
python -m target_opportunity_monitor run-daily
python -m target_opportunity_monitor build-dashboard
python -m target_opportunity_monitor status
```

Observed live state after verification:

```text
Required tables present: 29/29.
Asset count: 15.
Short interest file exists: True.
Short interest source rows: 0.
Short interest source-backed tickers: 0/13.
Short interest missing source tickers: 13.
Short interest signal rows: 0.
Short interest validation rows: 0.
SPY/QQQ are ETF-gated for short interest.
Analyst revision evidence decision: collecting_evidence.
News/catalyst total numeric coverage: 13/13.
News/catalyst provider numeric ticker coverage: 1/13.
Insider activity source coverage: 13/13.
```

Notes:

- Phase 10G is workflow-ready and validation-ready, but not
  evidence-producing until source-backed short-interest rows are added.
- Do not fabricate short interest, float, volume, or days-to-cover inputs.
- Phase 10D remains gated until analyst revision 20d validation evidence
  matures and passes the configured evidence gate.

### 2026-06-08 - Phase 10E.10 provider-native backfill apply and export normalization MVP

Completed:

- Added `normalize-news-catalyst-provider-export --provider marketaux|eodhd|x|licensed|generic --file PATH`.
- Normalized provider/export CSV rows into
  `data/signals/source_exports/news_catalysts/provider_native_backfill/normalized_{provider}_provider_native.csv`.
- Normalization accepts only active equities in the provider-native upgrade
  queue, skips already provider-native tickers, skips inactive tickers, and
  gates SPY/QQQ.
- Provider polarity values in `[-1, 1]` convert to `0-100`; already normalized
  `0-100` values pass through.
- Headline-only/text-only rows are rejected unless at least one source-backed
  provider numeric field is present.
- Added `news-catalyst-provider-backfill-status`.
- Added `apply-news-catalyst-provider-backfill` with dry-run default.
- Confirmed apply requires `--confirm`, aborts on invalid rows, zero valid rows,
  or non-improving provider-native coverage, and supports `--allow-partial` for
  partial upgrades.
- Fixed the package `__main__` entrypoint so command return codes propagate to
  the process exit code.
- Added apply-readiness fields to `status`, daily Markdown, daily CSV, and
  dashboard:
  `backfill_apply_ready`, `valid_upgrade_tickers`,
  `projected_upgrade_delta`, and `blocked_apply_reason`.
- Updated README and `DOCS/news-catalyst-source-workflow.md`.

Verification:

```text
python -m unittest discover -s tests -p test_phase10e_news_catalysts.py
30 tests passed.

python -m unittest discover -s tests
159 tests passed.
Non-fatal ResourceWarnings appeared, consistent with prior suite behavior.

python -m target_opportunity_monitor init-db
Required tables present: 28/28.

python -m target_opportunity_monitor export-news-catalyst-provider-backfill
Backfill package exported with 12 tickers.

python -m target_opportunity_monitor normalize-news-catalyst-provider-export --provider generic --file data\signals\source_exports\news_catalysts\provider_native_backfill\news_catalyst_provider_native_backfill.csv
Input rows: 12.
Normalized rows: 0.
Skipped rows: 12.
Warnings were missing_source_url for the 12 blank placeholder rows.

python -m target_opportunity_monitor validate-news-catalyst-provider-backfill
Valid provider-native rows: 0.
Blank placeholders: 12.
Invalid rows: 0.

python -m target_opportunity_monitor preview-news-catalyst-provider-upgrade
Current provider-native coverage: 1/13.
Projected provider-native coverage after import: 1/13.
Still blocked tickers: AMD, AMZN, AVGO, COST, CRM, GOOGL, JPM, LLY, META, MSFT,
NVDA, ORCL.

python -m target_opportunity_monitor news-catalyst-provider-backfill-status
Backfill apply ready: False.
Blocked apply reason: no_valid_provider_native_backfill_rows.
Projected upgrade delta: 0.

python -m target_opportunity_monitor apply-news-catalyst-provider-backfill
Dry run: True.
Applied: False.

python -m target_opportunity_monitor apply-news-catalyst-provider-backfill --confirm --allow-partial
Exited nonzero as expected because no valid provider-native rows exist.
Applied: False.
Blocked apply reason: no_valid_provider_native_backfill_rows.

python -m target_opportunity_monitor run-daily
Created reports/2026-06-08-daily-report.md.
Created reports/2026-06-08-daily-report.csv.

python -m target_opportunity_monitor build-dashboard
Dashboard regenerated with 15 rows.

python -m target_opportunity_monitor status
News/catalyst numeric ticker coverage: 13/13.
News/catalyst provider numeric ticker coverage: 1/13.
News/catalyst text-derived ticker coverage: 12/13.
News/catalyst backfill apply ready: False.
News/catalyst projected upgrade delta: 0.
News/catalyst blocked apply reason: no_valid_provider_native_backfill_rows.
Revision evidence decision: collecting_evidence.
```

### 2026-06-08 - Phase 10E.9 provider-native backfill validation and upgrade preview MVP

Completed:

- Added `validate-news-catalyst-provider-backfill`.
- Added `preview-news-catalyst-provider-upgrade`.
- Validation reads the provider-native backfill package without storing
  snapshots or changing aggregates.
- Validation classifies valid provider-native rows, blank placeholders, invalid
  rows, unsupported tickers, ETF-gated rows, malformed dates/numbers, and
  missing provider-native fields.
- Preview compares valid backfill rows with current persisted provider-native
  coverage and reports projected provider-native coverage after import plus
  still-blocked tickers.
- Added the exact next commands to the preview output:
  `import-news-catalyst-source-exports`, `aggregate-news-catalyst-sources`,
  `load-news-catalysts`, `compute-news-catalyst-signals`, and
  `validate-news-catalyst-signals`.
- Added backfill validation and projected-upgrade fields to `status`, daily
  Markdown, daily CSV, and dashboard health output.
- Updated README and `DOCS/news-catalyst-source-workflow.md` with the dry-run
  validation/preview workflow and no-fabrication rules.
- Tightened Phase 10E tests so temp source-export/cache directories are cleaned
  per test database stem.

Verification:

```text
python -m unittest discover -s tests -p test_phase10e_news_catalysts.py
26 tests passed.

python -m unittest discover -s tests
155 tests passed.
Non-fatal ResourceWarnings appeared, consistent with prior suite behavior.

python -m target_opportunity_monitor init-db
Required tables present: 28/28.

python -m target_opportunity_monitor export-news-catalyst-provider-backfill
Backfill package exported with 12 tickers.

python -m target_opportunity_monitor validate-news-catalyst-provider-backfill
Valid provider-native rows: 0.
Blank placeholders: 12.
Invalid rows: 0.
ETF-gated rows: 0.

python -m target_opportunity_monitor preview-news-catalyst-provider-upgrade
Current provider-native coverage: 1/13.
Projected provider-native coverage after import: 1/13.
Still blocked tickers: AMD, AMZN, AVGO, COST, CRM, GOOGL, JPM, LLY, META, MSFT,
NVDA, ORCL.

python -m target_opportunity_monitor news-catalyst-provider-upgrade-status
Preview command is shown.

python -m target_opportunity_monitor run-daily
Created reports/2026-06-08-daily-report.md.
Created reports/2026-06-08-daily-report.csv.

python -m target_opportunity_monitor build-dashboard
Dashboard regenerated with 15 rows.

python -m target_opportunity_monitor status
News/catalyst backfill valid rows: 0.
News/catalyst backfill blank placeholders: 12.
News/catalyst backfill invalid rows: 0.
News/catalyst projected provider-native coverage: 1/13.
Revision evidence decision: collecting_evidence.
```

Notes:

- Phase 10E.9 does not change final scores, alerts, portfolio guidance,
  notifications, broker writes, or execution.
- News/catalyst remains shadow-only.
- Provider-native coverage remains 1/13 until provider-native API data or
  source-backed provider exports fill the 12 remaining queued equities.
- Phase 10D remains gated until analyst revision validation has mature 20d
  evidence and passes the configured evidence gate.

### 2026-06-06 - Phase 0 project foundation

Completed:

- Created Python project scaffold with `pyproject.toml`, `src/target_opportunity_monitor/`, `tests/`, `configs/`, `data/`, and `reports/`.
- Added CLI commands: `init-db`, `status`, and `run-daily`.
- Added SQLite initialization for initial Phase 0 tables: `assets`, `prices`, `signals`, `targets`, `scores`, `alerts`, `alert_outcomes`, `data_quality_checks`, and `model_versions`.
- Added placeholder daily Markdown report generation.
- Added README run instructions and standard-library unit tests.
- Added `.gitignore` rules for runtime SQLite/report/test/cache artifacts.

Verification:

```text
python -m unittest discover -s tests
5 tests passed.

python -m target_opportunity_monitor init-db
Required tables present: 9/9.

python -m target_opportunity_monitor status
Database exists: True.
Required tables present: 9/9.

python -m target_opportunity_monitor run-daily
Created reports/2026-06-06-daily-report.md.
```

Notes:

- Phase 0 intentionally does not ingest market data, calculate valuation targets, score opportunities, or produce live alerts.
- A root `target_opportunity_monitor.py` shim allows `python -m target_opportunity_monitor ...` to work from the project folder without requiring installation.

### 2026-06-06 - Phase 1A usable data foundation

Completed:

- Added `fundamentals` and `estimates` tables to the required SQLite schema.
- Added default manual watchlist file at `configs/watchlist.csv`.
- Added config support for `paths.watchlist`.
- Added typed storage helpers for assets, fundamentals, estimates, row counts, and asset listing.
- Added watchlist CSV loading with idempotent asset upserts.
- Added CLI commands: `load-watchlist` and `list-assets`.
- Extended `status` to show watchlist file status and asset count.
- Added Phase 1A unit tests.

Verification:

```text
python -m unittest discover -s tests
10 tests passed.

python -m target_opportunity_monitor init-db
Required tables present: 11/11.

python -m target_opportunity_monitor load-watchlist
Loaded 5 assets from configs/watchlist.csv.

python -m target_opportunity_monitor list-assets
Listed AAPL, MSFT, NVDA, QQQ, SPY sorted by ticker.

python -m target_opportunity_monitor status
Watchlist exists: True.
Asset count: 5.
```

Notes:

- Phase 1A intentionally does not ingest live market data, calculate valuation targets, score opportunities, or produce real alerts.
- The default watchlist is editable and exists only to make the manual-universe path immediately testable.

### 2026-06-06 - Phase 2 universe and market data MVP

Completed:

- Added market-data config for online-first mode, Stooq primary source, Yahoo chart secondary source, and local CSV fallback.
- Added `price_features` table to the required SQLite schema.
- Added Stooq CSV parser/fetcher, Yahoo chart parser/fetcher, local CSV parser, and source-mode handling.
- Added price storage helpers, feature calculation, latest price status, and data-quality checks.
- Added CLI commands: `update-prices` and `price-status`.
- Extended `status` and daily report output with price row count, latest price date, feature coverage, missing tickers, and stale tickers.
- Added Phase 2 unit tests.

Verification:

```text
python -m unittest discover -s tests
21 tests passed.

python -m target_opportunity_monitor init-db
Required tables present: 12/12.

python -m target_opportunity_monitor load-watchlist
Loaded 5 assets from configs/watchlist.csv.

python -m target_opportunity_monitor update-prices
Loaded 5 assets, failed 0.
Rows per ticker: 549.
Source used: yahoo_chart.

python -m target_opportunity_monitor price-status
AAPL, MSFT, NVDA, QQQ, and SPY have latest price date 2026-06-05,
features available, and stale=False.

python -m target_opportunity_monitor status
Price rows: 2745.
Latest price date: 2026-06-05.
```

Notes:

- Stooq returned a browser JavaScript verification page in this environment, so auto mode falls through to Yahoo chart before local CSV fallback.
- Phase 2 intentionally does not calculate valuation targets, opportunity scores, or real alerts.

### 2026-06-06 - Phase 3 fundamental and valuation MVP

Completed:

- Added Phase 3 config defaults for manual fundamentals, manual estimates, valuation model version, uncertainty band, method count, peer count, and stale-data thresholds.
- Added editable manual CSV header files under `data/fundamentals/manual/`.
- Added fundamentals and estimates CSV parsing/loading with ticker normalization, date/numeric validation, and idempotent upsert behavior.
- Added storage helpers for listing/latest fundamentals, estimates, price features, targets, latest target date, and valuation status.
- Extended the existing `targets` table migration-safely with valuation score, valuation confidence, method count, target reason, and data warning fields.
- Added a non-alerting valuation engine that computes current valuation inputs, basic ratios, peer/historical method targets, combined target ranges, valuation gaps, valuation score, and valuation confidence.
- Added data-quality warnings for missing fundamentals, missing prices, missing shares, stale data, insufficient methods, and unsupported ETF/index-style assets.
- Added CLI commands: `load-fundamentals`, `load-estimates`, `compute-targets`, and `valuation-status`.
- Extended `status` and daily reports with fundamental row count, estimate row count, target row count, latest target date, valuation coverage, and target ranges.
- Updated README with Phase 3 commands and manual CSV notes.
- Added Phase 3 unit tests.

Verification:

```text
python -m unittest discover -s tests
29 tests passed.

python -m target_opportunity_monitor init-db
Required tables present: 12/12.

python -m target_opportunity_monitor load-watchlist
Loaded 5 assets from configs/watchlist.csv.

python -m target_opportunity_monitor update-prices
Loaded 5 assets, failed 0.
Source used: yahoo_chart.

python -m target_opportunity_monitor load-fundamentals
Loaded 0 rows from data/fundamentals/manual/fundamentals.csv.

python -m target_opportunity_monitor load-estimates
Loaded 0 rows from data/fundamentals/manual/estimates.csv.

python -m target_opportunity_monitor compute-targets
Computed 0 targets and skipped 5 assets because the default manual
fundamental/estimate files are header-only.

python -m target_opportunity_monitor valuation-status
AAPL, MSFT, and NVDA show missing fundamentals warnings.
QQQ and SPY show unsupported asset type warnings.

python -m target_opportunity_monitor status
Fundamental rows: 0.
Estimate rows: 0.
Target rows: 0.
Latest target date: none.

python -m target_opportunity_monitor run-daily
Created reports/2026-06-06-daily-report.md with valuation status.
```

Notes:

- Phase 3 is manual/CSV-first; no external fundamentals provider has been selected yet.
- The manual fundamentals and estimates files are editable. They were initially created as headers only, then seeded with AAPL, MSFT, and NVDA rows before Phase 4 planning.
- Deterministic tests verify actual target creation, valuation math, target upsert behavior, valuation status, and report output.
- SPY and QQQ are skipped by the company-level valuation model until ETF-specific valuation is added.
- Phase 3 intentionally does not create Phase 4 opportunity scores or Phase 5 live alerts.

### 2026-06-06 - Phase 3 manual valuation seed data

Completed:

- Added manual annual fundamentals for AAPL, MSFT, and NVDA to `data/fundamentals/manual/fundamentals.csv`.
- Added manual NTM EPS estimate rows for AAPL, MSFT, and NVDA to `data/fundamentals/manual/estimates.csv`.
- Loaded the manual rows into SQLite and recomputed valuation targets.
- Refined `valuation-status` so old missing-data warnings do not appear once a current target row exists.
- Added `seed-fundamentals` to fetch/cache SEC companyfacts, regenerate the fundamentals CSV, and load rows into SQLite.

Verification:

```text
python -m target_opportunity_monitor load-fundamentals
Loaded 9 rows from data/fundamentals/manual/fundamentals.csv.

python -m target_opportunity_monitor seed-fundamentals
Loaded 9 SEC-backed rows for AAPL, MSFT, and NVDA.

python -m target_opportunity_monitor load-estimates
Loaded 3 rows from data/fundamentals/manual/estimates.csv.

python -m target_opportunity_monitor compute-targets
AAPL, MSFT, and NVDA computed target ranges.
QQQ and SPY skipped as unsupported ETF assets.

python -m target_opportunity_monitor valuation-status
AAPL target: 308.9875.
MSFT target: 546.7839.
NVDA target: 377.0727.

python -m target_opportunity_monitor status
Fundamental rows: 9.
Estimate rows: 3.
Target rows: 3.
Latest target date: 2026-06-06.

python -m unittest discover -s tests
29 tests passed.
```

Notes:

- Fundamental rows were sourced from SEC companyfacts and stored as manual CSV rows.
- Raw SEC companyfacts JSON is cached under `data/fundamentals/cache/sec_companyfacts/`.
- MSFT EBITDA is approximated as operating income plus depreciation and amortization components from SEC facts.
- NVDA FY2024 diluted EPS and diluted shares were split-adjusted for the 10-for-1 stock split so historical multiples are comparable with current post-split prices.
- Estimate rows use Yahoo Finance current price and forward P/E to infer NTM EPS.

### 2026-06-06 - Phase 3B ETF tables and separate scoring path

Completed:

- Added separate required SQLite tables for ETF NAVs, ETF holdings, and ETF features.
- Added config defaults and editable manual CSV header files under `data/etf/manual/`.
- Added ETF NAV and holdings CSV parsing/loading with date/numeric validation, percent/decimal weight handling, and idempotent upserts.
- Added ETF storage helpers, ETF feature calculation, and ETF status output.
- Routed ETF assets through a NAV-based target path in `compute-targets` while keeping company equities on the existing fundamental valuation path.
- ETF target rows use `source = etf_valuation`, `model_version = etf_nav_mvp_v1`, and `target_method = etf_nav`.
- Added CLI commands: `load-etf-navs`, `load-etf-holdings`, and `etf-status`.
- Extended `status`, `valuation-status`, and daily reports with ETF coverage.
- Marked Phase 4 and Phase 5 as asset-type-aware: ETFs and single-company equities share output surfaces but require separate scoring logic and alert thresholds.

Verification:

```text
python -m unittest discover -s tests
39 tests passed.

python -m target_opportunity_monitor init-db
Required tables present: 15/15.

python -m target_opportunity_monitor load-etf-navs
Loaded 0 rows from data/etf/manual/etf_navs.csv.

python -m target_opportunity_monitor load-etf-holdings
Loaded 0 rows from data/etf/manual/etf_holdings.csv.

python -m target_opportunity_monitor compute-targets
AAPL, MSFT, and NVDA computed target ranges.
QQQ and SPY skipped with missing_etf_nav until manual ETF NAV rows are loaded.

python -m target_opportunity_monitor etf-status
QQQ and SPY show ETF-specific missing_etf_nav warnings.

python -m target_opportunity_monitor run-daily
Created reports/2026-06-06-daily-report.md with ETF status.
```

Notes:

- Phase 3B intentionally keeps ETF data manual/CSV-first; issuer scraping or automated holdings refresh can be added later.
- ETF target output is unified in `targets`, but ETF input data is separated from company fundamentals.
- Phase 4 should extend `scores` migration-safely with `asset_type`, `score_model`, `threshold_set`, `score_reason`, and `data_warnings` rather than creating a separate `etf_scores` table immediately.
- SPY and QQQ are no longer treated as unsupported asset types; they require ETF NAV data before ETF targets can be computed.

### 2026-06-06 - Phase 3C scheduled refresh and readiness pipeline

Completed:

- Added required SQLite tables for quote snapshots, intraday gap snapshots, pipeline runs, and pipeline step results.
- Added config defaults for a read-only local IBKR paper Gateway connection on `127.0.0.1:4002`.
- Added optional IBKR provider support for connectivity checks, historical prices, quote snapshots, and ETF NAV attempts.
- Added `verify-universe` and `verify-ticker` to show Phase 4 readiness by asset type.
- Added `refresh-data` as the scheduler-friendly daily refresh orchestration command.
- Added `probe-market` as the lightweight intraday quote/NAV/gap probe.
- Added `update-quotes`, `update-etf-navs`, `ibkr-status`, and `ibkr-probe`.
- Extended `status` and daily reports with quote, intraday gap, and pipeline audit information.
- Created Codex scheduler automations:
  - `tom-daily-refresh`
  - `tom-daily-retry`
  - `tom-morning-check`
  - `tom-intraday-probe`

Verification:

```text
python -m unittest discover -s tests
46 tests passed.

python -m target_opportunity_monitor init-db
Required tables present: 19/19.

python -m target_opportunity_monitor verify-universe
AAPL, MSFT, and NVDA are Phase 4 ready.
QQQ and SPY remain blocked by missing ETF NAV, ETF feature, ETF holdings, and ETF target rows.

python -m target_opportunity_monitor ibkr-status
Connected to local paper Gateway on port 4002 with 1 managed account.

python -m target_opportunity_monitor update-quotes --source ibkr --ticker AAPL
Loaded 1 delayed AAPL quote snapshot.

python -m target_opportunity_monitor update-etf-navs --source ibkr --ticker SPY
Loaded 0 NAV rows; SPY returned no ETF NAV ticks in the verification window.

python -m target_opportunity_monitor refresh-data --daily-only
Daily refresh completed with expected ETF NAV warnings.
```

Notes:

- Daily refresh is now the source-of-truth pipeline for Phase 4 scoring.
- Intraday probes are diagnostic only until Phase 5 alerts.
- IBKR is read-only and no order-placement path was added.
- IBKR quote data worked, but AAPL produced a subscription warning during one probe; delayed quote snapshots are still stored and labeled.
- IBKR ETF NAV tick IDs are supported by the provider path, but SPY did not emit NAV during verification, so ETF NAV CSV/manual issuer fallback remains required.
- Phase 4 can start for single-company equities now; ETF scoring should wait for SPY and QQQ NAV rows.

### 2026-06-06 - Phase 4 explainable core scoring MVP

Completed:

- Added scoring config defaults for equity and ETF model versions and threshold sets.
- Extended the existing `scores` table migration-safely with `asset_type`, `score_model`, `threshold_set`, `score_reason`, and `data_warnings`.
- Added score storage helpers for idempotent upsert, score listing, latest score date, and score status output.
- Added an explainable scoring engine with separate equity and ETF paths.
- Equity scoring now computes valuation gap, quality, growth, revision, momentum, risk, liquidity, confidence, timing, expected value, and opportunity scores.
- ETF scoring remains a separate path and is gated by missing ETF NAV/features for SPY and QQQ.
- Added CLI commands: `compute-scores` and `score-status`.
- Extended `status`, `run-daily`, `refresh-data`, and `verify-universe` with score coverage.
- Updated README with Phase 4 commands and score meanings.
- Added Phase 4 unit tests.

Verification:

```text
python -m unittest discover -s tests
54 tests passed.

python -m target_opportunity_monitor init-db
Required tables present: 19/19.

python -m target_opportunity_monitor compute-scores
AAPL opportunity score: 67.66.
MSFT opportunity score: 72.60.
NVDA opportunity score: 80.56.
QQQ and SPY skipped with missing_etf_nav.

python -m target_opportunity_monitor compute-scores --asset-type equity
AAPL, MSFT, and NVDA scored; ETFs skipped by filter.

python -m target_opportunity_monitor score-status
AAPL, MSFT, and NVDA show equity_score_mvp_v1 scores.
QQQ and SPY show missing_etf_nav warnings.

python -m target_opportunity_monitor status
Score rows: 3.
Latest score date: 2026-06-06.

python -m target_opportunity_monitor verify-universe
AAPL, MSFT, and NVDA are Phase 4 ready with score coverage.
QQQ and SPY remain blocked by missing ETF NAV, ETF feature, ETF holdings, ETF target, and score rows.

python -m target_opportunity_monitor run-daily
Created reports/2026-06-06-daily-report.md with score status.

python -m target_opportunity_monitor refresh-data --daily-only
Daily refresh completed and included compute-scores after compute-targets.
```

Notes:

- Phase 4 is daily/EOD scoring only. It does not create alerts, place orders, run ML models, or ingest sentiment.
- AAPL, MSFT, and NVDA are scoreable now because they have prices, fundamentals, estimates, and targets.
- Current manual estimates do not include revision fields, so equity scoring uses a neutral revision score and records `missing_revision_data`.
- SPY and QQQ stay unscored until ETF NAV/features exist; they should not be scored with the company equity model.

### 2026-06-07 - Pre-Phase-5 closure for Phases 0-4

Completed:

- Changed the default run mode from `placeholder` to `daily_scoring`.
- Updated CLI/help/report wording so the current system is described as a daily scoring pipeline, not a placeholder.
- Updated daily report next steps to point to Phase 5A equity alerts instead of Phase 4 scoring.
- Recorded SPY and QQQ ETF alert gating as a known non-blocker until ETF NAV, features, and holdings exist.
- Recorded `missing_revision_data` as a known non-blocker; revision-inflection alerts remain disabled until estimate revision history exists.
- Kept sentiment, portfolio-context, real-time alerts, and order execution out of scope before Phase 5.

Verification:

```text
python -m unittest discover -s tests
54 tests passed.

python -m target_opportunity_monitor status
Required tables present: 19/19.
Target rows: 3.
Score rows: 3.
Run mode: daily_scoring.

python -m target_opportunity_monitor verify-universe
AAPL, MSFT, and NVDA are pre-alert ready.
QQQ and SPY remain gated by missing ETF NAV, ETF feature, ETF holdings, ETF target, and score rows.

python -m target_opportunity_monitor run-daily
Daily report includes score coverage, removes stale Phase 4 scoring next-step text, and points to Phase 5A equity alerts.
```

Notes:

- Phases 0-4 are considered complete for the equity path.
- Phase 5 should begin with daily/EOD equity alerts for AAPL, MSFT, and NVDA.
- ETF alerts should be a later Phase 5B task after ETF data readiness is solved.

### 2026-06-07 - Phase 5A equity daily alert engine MVP

Completed:

- Added alert config defaults for the equity alert model, threshold set, valuation gap thresholds, score thresholds, data-quality threshold, watch threshold, bearish gap threshold, and risk warning threshold.
- Extended the existing `alerts` table migration-safely with alert metadata, reason/risk/data-warning fields, score/target dates, data-quality score, and `dedupe_key`.
- Added a unique alert dedupe index so repeated daily runs update the same ticker/date/type/model row.
- Added alert storage helpers for idempotent upsert, alert listing, latest alert timestamp, and alert status output.
- Added a Phase 5A alert engine with equity-only daily alert rules and ETF gating.
- Added alert types: `bullish_divergence`, `bearish_overvaluation`, `watch_only_gap`, `risk_warning`, `data_quality_warning`, and `no_alert`.
- Added CLI commands: `compute-alerts` and `alert-status`.
- Extended `status`, `run-daily`, and `refresh-data` with alert coverage.
- Updated README with Phase 5A commands and scope.
- Added Phase 5A unit tests.

Verification:

```text
python -m unittest discover -s tests
65 tests passed.

python -m target_opportunity_monitor init-db
Required tables present: 19/19.

python -m target_opportunity_monitor refresh-data --daily-only
Pipeline run 6 completed with status ok.
compute-alerts ran after compute-scores.
Daily refresh has 11 steps.

python -m target_opportunity_monitor compute-alerts
AAPL: no_alert.
MSFT: bullish_divergence, high priority.
NVDA: watch_only_gap, medium priority.
QQQ and SPY: skipped with etf_alerts_gated.

python -m target_opportunity_monitor alert-status
Shows AAPL no_alert, MSFT bullish_divergence, NVDA watch_only_gap,
and SPY/QQQ ETF gating.

python -m target_opportunity_monitor status
Alert rows: 3.
Run mode: daily_scoring.

python -m target_opportunity_monitor run-daily
Created reports/2026-06-07-daily-report.md with active alert count 2.
```

Notes:

- Phase 5A is daily/EOD alert reporting only. It does not send notifications, place orders, or run real-time triggers.
- `missing_revision_data` is preserved as a nonfatal risk code and does not block equity alerts.
- ETF alerts remain gated until ETF NAV, ETF features, and ETF holdings are available.
- Revision-inflection, sentiment, portfolio-context, and real-time alert types remain disabled.
- The next original-plan phase is reporting: daily CSV, richer Markdown detail, and later static HTML if useful.

### 2026-06-07 - Phase 6A equity alert reporting MVP

Completed:

- Added companion daily CSV report generation beside the existing daily Markdown report.
- Extended `ReportResult` with `csv_path` while preserving `path` as the Markdown report path.
- Added shared daily report row building so Markdown and CSV use the same ticker snapshot data.
- Added CSV fields for ticker, asset type, price, target range, valuation gap, scores, alert metadata, reasons, risks, invalidation, data freshness, and model warnings.
- Added richer Markdown sections: executive alert summary, data-health summary, model-health summary, equity ticker-level alert details, and CSV field documentation.
- Kept SPY and QQQ visible as gated ETF rows with `alert_type=skipped` and `etf_alerts_gated` warnings.
- Updated `status` and `run-daily` output to show the latest Markdown and CSV report paths.
- Updated README with Phase 6A reporting scope and commands.
- Added Phase 6A unit tests.

Verification:

```text
python -m unittest discover -s tests
69 tests passed.

python -m target_opportunity_monitor init-db
Required tables present: 19/19.

python -m target_opportunity_monitor refresh-data --daily-only
Pipeline run 8 completed with status ok.
Daily refresh has 11 steps.
compute-alerts remains warning-only for SPY/QQQ ETF gating.

python -m target_opportunity_monitor run-daily
Created reports/2026-06-07-daily-report.md.
Created reports/2026-06-07-daily-report.csv.

python -m target_opportunity_monitor status
Latest report: reports\2026-06-07-daily-report.md.
Latest CSV report: reports\2026-06-07-daily-report.csv.
Target rows: 6.
Score rows: 6.
Alert rows: 3.
Run mode: daily_scoring.
```

Notes:

- Phase 6A is reporting only. It does not add alert rules, notifications, outcome tracking, order placement, or execution automation.
- AAPL, MSFT, and NVDA are the actionable equity report rows.
- SPY and QQQ remain ETF-gated until ETF NAV/features/holdings exist.
- Static HTML reporting is still optional and can be done as Phase 6B if Markdown/CSV reports are not ergonomic enough.
- The next original-plan phase is Phase 7 outcome tracking and validation.

### 2026-06-07 - Phase 7A alert outcome tracking and validation MVP

Completed:

- Extended the existing `alert_outcomes` table migration-safely with alert metadata, entry/latest prices, target/invalidation prices, horizon status, data warnings, and model version fields.
- Added a unique outcome index on `alert_id` so repeated runs update the same outcome row.
- Added outcome storage helpers for stored alert access, idempotent outcome upsert, outcome listing, latest outcome date, and outcome status output.
- Added a Phase 7A outcome engine for actionable equity alerts.
- Added 5d/20d/60d/120d return tracking using stored daily prices.
- Added target-hit, invalidation-hit, max favorable excursion, and max adverse excursion calculations.
- Added pending/partial/completed outcome states so new alerts can be tracked before horizons mature.
- Added CLI commands: `update-alert-outcomes`, `outcome-status`, and `validation-report`.
- Extended `status`, `run-daily`, daily CSV reports, and daily Markdown reports with outcome coverage.
- Extended `refresh-data --daily` so it runs `update-alert-outcomes` after `compute-alerts` and before `run-daily`.
- Updated README with Phase 7A commands and scope.
- Added Phase 7A unit tests.

Verification:

```text
python -m unittest discover -s tests
76 tests passed.

python -m target_opportunity_monitor init-db
Required tables present: 19/19.

python -m target_opportunity_monitor refresh-data --daily-only
Pipeline run 9 completed with status ok.
Daily refresh has 12 steps.
update-alert-outcomes ran after compute-alerts.
MSFT and NVDA outcomes are pending because future price rows are not available yet.

python -m target_opportunity_monitor update-alert-outcomes
Updated 2 outcome rows.
AAPL no_alert was skipped.
MSFT bullish_divergence is pending.
NVDA watch_only_gap is pending.

python -m target_opportunity_monitor outcome-status
Shows MSFT and NVDA pending with 5d/20d/60d/120d horizons pending.

python -m target_opportunity_monitor validation-report
Shows 2 outcome rows, 2 pending, 0 partial, 0 completed.

python -m target_opportunity_monitor status
Outcome rows: 2.
Latest outcome date: 2026-06-07.

python -m target_opportunity_monitor run-daily
Created reports/2026-06-07-daily-report.md.
Created reports/2026-06-07-daily-report.csv.
Reports include outcome status fields and an Outcome Validation Summary.
```

Notes:

- Phase 7A is validation only. It does not add new alert rules, notifications, portfolio actions, order placement, or execution automation.
- ETF outcomes remain gated until ETF alerts exist.
- Current live outcomes are expected to be pending because alerts were generated on 2026-06-07 and latest stored prices are from 2026-06-05.
- The next original-plan phase is Phase 8 dashboard.

### 2026-06-07 - Phase 8A static dashboard MVP

Completed:

- Added a static dashboard generator that writes `dashboard/index.html`.
- Added a self-contained HTML dashboard with embedded CSS, embedded JSON data, and vanilla JavaScript.
- Added dashboard sections for daily alerts, watchlist ranking, ticker detail, price-vs-target chart, score breakdown, alert history, outcome status, data health, model health, and a gated portfolio review panel.
- Added CLI command: `build-dashboard`.
- Extended `status` so it reports the latest dashboard path.
- Extended `refresh-data --daily` so it runs `build-dashboard` after `run-daily`.
- Kept the dashboard local, read-only, dependency-free, and network-free.
- Kept SPY and QQQ visible as ETF-gated rows until ETF NAV/features/holdings and ETF alerts exist.
- Updated README with Phase 8A commands and scope.
- Added Phase 8A unit tests.

Verification:

```text
python -m unittest discover -s tests
80 tests passed.

python -m target_opportunity_monitor init-db
Required tables present: 19/19.

python -m target_opportunity_monitor refresh-data --daily-only
Pipeline run 11 completed with status ok.
Daily refresh has 13 steps.
build-dashboard ran after run-daily.

python -m target_opportunity_monitor build-dashboard
Dashboard written: dashboard\index.html rows=5.

python -m target_opportunity_monitor status
Latest dashboard: dashboard\index.html.
Target rows: 6.
Score rows: 6.
Alert rows: 3.
Outcome rows: 2.
Run mode: daily_scoring.

Dashboard HTML inspection
Includes Daily Alerts, Watchlist Ranking, Ticker Detail, Price vs Target,
Outcome Status, Data Health, and Model Health sections.
No external http:// or https:// dependencies were found.
```

Notes:

- Phase 8A is static local reporting only. It does not add notifications, live market calls, portfolio actions, order placement, or execution automation.
- The dashboard is generated from existing SQLite/reporting data and opens directly from disk.
- AAPL, MSFT, and NVDA are the actionable equity dashboard rows.
- SPY and QQQ remain ETF-gated until ETF NAV/features/holdings and ETF alerts exist.
- The portfolio review panel remains gated until Phase 9 portfolio context.
- The next original-plan phase is Phase 9 portfolio context and sizing guidance.

### 2026-06-07 - Phase 9A portfolio context and sizing guidance MVP

Completed:

- Added config defaults for manual portfolio positions/cash CSVs and advisory sizing thresholds.
- Added required SQLite tables: `portfolio_positions`, `portfolio_cash`, and `portfolio_reviews`.
- Added manual portfolio CSV header creation, parsing, validation, enrichment, and idempotent loading.
- Added read-only portfolio review engine that combines holdings, cash, alerts, scores, targets, price features, and active assets.
- Added review categories: `watch`, `research_deeper`, `review_existing_position`, `small_starter_candidate`, `add_candidate`, `reduce_risk_review`, and `exit_review_candidate`.
- Added advisory max-add value and sizing guidance without share quantities, orders, execution, or broker writes.
- Added CLI commands: `load-portfolio`, `compute-portfolio-context`, and `portfolio-status`.
- Extended `status`, `run-daily`, daily CSV reports, daily Markdown reports, and the static dashboard with portfolio context.
- Extended `refresh-data --daily` so it runs `load-portfolio` and `compute-portfolio-context` after `update-alert-outcomes` and before `run-daily`.
- Kept ETF-specific portfolio actions gated until ETF NAV/features/holdings and ETF alerts exist.
- Updated README with Phase 9A commands, CSV formats, and scope.
- Added Phase 9A unit tests.

Verification:

```text
python -m unittest discover -s tests
87 tests passed.

python -m target_opportunity_monitor init-db
Required tables present: 22/22.

python -m target_opportunity_monitor load-portfolio
Loaded 0 position rows and 0 cash rows from the default header-only CSV files.
Warnings: empty_portfolio_positions, empty_portfolio_cash.

python -m target_opportunity_monitor compute-portfolio-context
Computed 5 portfolio review rows.
AAPL: watch.
MSFT: research_deeper.
NVDA: research_deeper.
QQQ/SPY: watch with ETF portfolio review gated.

python -m target_opportunity_monitor portfolio-status
Shows 5 portfolio review rows with no loaded holdings/cash yet.

python -m target_opportunity_monitor refresh-data --daily-only
Pipeline run 12 completed with status ok.
Daily refresh has 15 steps.
load-portfolio and compute-portfolio-context ran before run-daily.

python -m target_opportunity_monitor run-daily
Created reports/2026-06-07-daily-report.md.
Created reports/2026-06-07-daily-report.csv.
Reports include portfolio review fields and Portfolio Review Summary.

python -m target_opportunity_monitor build-dashboard
Dashboard written: dashboard\index.html rows=5.
Dashboard includes portfolio review fields and no longer shows Phase 9 gated.

python -m target_opportunity_monitor status
Required tables present: 22/22.
Portfolio position rows: 0.
Portfolio cash rows: 0.
Portfolio review rows: 5.
Latest portfolio review date: 2026-06-07.
```

Notes:

- Phase 9A is advisory only. It does not place orders, write to a broker, calculate executable share quantities, or automate portfolio changes.
- The default portfolio CSV files are intentionally header-only until real holdings and cash are entered.
- Empty portfolio CSVs create warnings and research/watch categories but do not fail the daily pipeline.
- Non-USD rows require user-supplied base-currency values until FX conversion is added.
- The next original-plan phase is Phase 10 advanced signal expansion.

### 2026-06-07 - Phase 10A analyst revision shadow signals MVP

Completed:

- Added config defaults for manual analyst revision CSV input and shadow-mode signal settings.
- Added migration-safe signal metadata columns: `model_version`, `confidence`, and `data_warnings`.
- Added manual analyst revision CSV header creation, parsing, validation, and idempotent raw input loading.
- Added analyst revision signal engine that computes granular and composite revision signals into the shared `signals` table.
- Added signal storage helpers and status helpers for active-ticker signal coverage.
- Added CLI commands: `load-analyst-revisions`, `compute-revision-signals`, and `signal-status`.
- Extended `refresh-data --daily` so it runs analyst revision load/compute before `compute-scores`.
- Kept analyst revisions in shadow mode by default: visible in scores/reports/dashboard but neutral in final opportunity-score contribution.
- Extended `status`, `run-daily`, daily CSV reports, daily Markdown reports, and the static dashboard with advanced signal context.
- Updated README with Phase 10A commands, CSV format, and shadow-mode behavior.
- Added Phase 10A unit tests.

Verification:

```text
python -m unittest discover -s tests
94 tests passed.

python -m target_opportunity_monitor init-db
Required tables present: 22/22.

python -m target_opportunity_monitor load-analyst-revisions
Loaded 0 rows and 0 input signals from the default header-only CSV file.
Warnings: empty_analyst_revisions.

python -m target_opportunity_monitor compute-revision-signals
Computed 0 analyst revision signals and skipped 5 active assets.
AAPL/MSFT/NVDA: missing_revision_signal.
QQQ/SPY: etf_revision_signal_gated.

python -m target_opportunity_monitor signal-status
Shows all 5 active tickers with missing or gated revision signal status.

python -m target_opportunity_monitor refresh-data --daily-only
Pipeline run 13 completed with status ok.
Daily refresh has 17 steps.
load-analyst-revisions and compute-revision-signals ran before compute-scores.

python -m target_opportunity_monitor run-daily
Created reports/2026-06-07-daily-report.md.
Created reports/2026-06-07-daily-report.csv.
Reports include Advanced Signals and revision CSV fields.

python -m target_opportunity_monitor build-dashboard
Dashboard written: dashboard\index.html rows=5.
Dashboard includes Advanced Signals and latest signal health.

python -m target_opportunity_monitor status
Analyst revisions file exists: True.
Signal rows: 0.
Latest signal date: none.
```

Notes:

- Phase 10A uses manual CSV only; no paid provider, scraping, sentiment, options, macro, or ML is added.
- The default analyst revision CSV file is intentionally header-only until real revision rows are entered.
- Empty revision CSVs create warnings but do not fail the daily pipeline.
- Shadow mode keeps advanced signals from changing alerts until there is coverage, quality control, and outcome evidence.
- The next step is Phase 10B: validate analyst revision signal usefulness once real rows exist, or add the next shadow signal family.

### 2026-06-07 - Phase 10B analyst revision validation MVP

Completed:

- Fixed stale daily-report Next Steps wording so the report now points to Phase 10B source-backed analyst revision rows and validation.
- Extended the manual analyst revision CSV workflow with optional `source_url` and `notes` fields.
- Extended the shared `signals` table migration-safely with `source_url` and `notes` audit metadata.
- Added the `signal_outcomes` table for analyst revision shadow-signal validation.
- Added storage helpers for stored signals, signal outcome upsert/list/latest/status, and idempotent signal validation rows.
- Added an analyst revision validation engine for `analyst_revision.composite` equity signals using stored daily prices only.
- Added CLI commands: `validate-revision-signals` and `revision-validation-report`.
- Extended `refresh-data --daily` so it runs `validate-revision-signals` after `compute-revision-signals`.
- Extended `status`, `run-daily`, daily CSV reports, daily Markdown reports, and the static dashboard with revision validation context.
- Kept analyst revisions in shadow mode. Validation does not alter final opportunity scores or alerts.
- Updated README with Phase 10B commands, source-audit fields, and validation behavior.
- Tightened dashboard CLI test isolation with an optional config `paths.project_root` override.
- Added Phase 10B unit and integration tests.

Verification:

```text
python -m unittest discover -s tests
97 tests passed.
Non-fatal sqlite ResourceWarnings appeared, consistent with the prior suite behavior.

python -m target_opportunity_monitor init-db
Required tables present: 23/23.

python -m target_opportunity_monitor load-analyst-revisions
Loaded 0 rows and 0 input signals from the default header-only CSV file.
Warnings: empty_analyst_revisions.

python -m target_opportunity_monitor compute-revision-signals
Computed 0 analyst revision signals and skipped 5 active assets.
AAPL/MSFT/NVDA: missing_revision_signal.
QQQ/SPY: etf_revision_signal_gated.

python -m target_opportunity_monitor validate-revision-signals
Updated 0 rows and skipped 5 active assets.
AAPL/MSFT/NVDA: missing_revision_signal.
QQQ/SPY: etf_signal_validation_gated.

python -m target_opportunity_monitor revision-validation-report
Signal outcome rows: 0.
Pending: 0. Partial: 0. Completed: 0.

python -m target_opportunity_monitor refresh-data --daily-only
Pipeline run 14 completed with status ok.
Daily refresh has 18 steps and includes validate-revision-signals.

python -m target_opportunity_monitor run-daily
Created reports/2026-06-07-daily-report.md.
Created reports/2026-06-07-daily-report.csv.
Reports include signal outcome rows, analyst revision validation rows, and Phase 10B Next Steps.

python -m target_opportunity_monitor build-dashboard
Dashboard written: dashboard\index.html rows=5.
Dashboard includes revision_validation_status and latest_signal_validation_date.

python -m target_opportunity_monitor status
Required tables present: 23/23.
Signal rows: 0.
Signal outcome rows: 0.
Latest signal validation date: none.
```

Notes:

- The default analyst revision CSV remains intentionally header-only until source-backed rows are entered.
- Empty revision data creates warnings but does not fail the daily pipeline.
- Analyst revision validation rows will remain empty until composite analyst revision signals exist.
- AAPL, MSFT, and NVDA are ready for revision validation once real rows are added.
- SPY and QQQ remain ETF-gated for signal validation.
- The next step is Phase 10C: either review matured revision validation evidence for possible score/alert enablement, or add the next shadow signal family if revision data coverage remains sparse.

### 2026-06-07 - Phase 10C analyst revision source seeding and evidence gate

Completed:

- Updated README scope and command documentation through Phase 10C.
- Added `DOCS/analyst-revision-source-workflow.md` with approved source priority, fixed derivation formulas, CSV audit rules, and the no-fabrication rule.
- Kept `data/signals/manual/analyst_revisions.csv` header-only because current public/API checks did not return auditable live AAPL/MSFT/NVDA revision values without authorization or an API key.
- Added Phase 10C evidence config defaults for source coverage, signal coverage, completed 20d validation rows, 20d hit rate, direction-adjusted 20d return, and confidence.
- Added `revision_evidence.py` with EPS revision, recommendation revision, dispersion derivation helpers, and an evidence gate.
- Added evidence decisions: `insufficient_source_coverage`, `collecting_evidence`, `keep_shadow`, and `eligible_for_limited_score_trial`.
- Added CLI command: `revision-evidence-report`.
- Extended `status`, `run-daily`, daily CSV reports, daily Markdown reports, and the static dashboard with revision evidence decision and coverage fields.
- Kept `signals.analyst_revision_shadow_mode = true`; Phase 10C does not alter final opportunity scores or alerts.
- Added Phase 10C unit/integration tests and updated stale report wording regressions.

Verification:

```text
python -m unittest discover -s tests
100 tests passed.
Non-fatal sqlite ResourceWarnings appeared, consistent with the prior suite behavior.

python -m target_opportunity_monitor init-db
Required tables present: 23/23.

python -m target_opportunity_monitor load-analyst-revisions
Loaded 0 rows and 0 input signals from the default header-only CSV file.
Warnings: empty_analyst_revisions.

python -m target_opportunity_monitor compute-revision-signals
Computed 0 analyst revision signals and skipped 5 active assets.
AAPL/MSFT/NVDA: missing_revision_signal.
QQQ/SPY: etf_revision_signal_gated.

python -m target_opportunity_monitor validate-revision-signals
Updated 0 rows and skipped 5 active assets.
AAPL/MSFT/NVDA: missing_revision_signal.
QQQ/SPY: etf_signal_validation_gated.

python -m target_opportunity_monitor revision-evidence-report
Decision: insufficient_source_coverage.
Source-backed ticker coverage: 0.
Composite signal ticker coverage: 0.
Completed 20d validation rows: 0.
Shadow mode: True.

python -m target_opportunity_monitor refresh-data --daily-only
Pipeline run 15 completed with status ok.
Daily refresh has 18 steps.
Expected warnings: empty analyst revisions, missing revision signals, ETF gates, empty portfolio CSVs.

python -m target_opportunity_monitor run-daily
Created reports/2026-06-07-daily-report.md.
Created reports/2026-06-07-daily-report.csv.
Reports include revision evidence decision and Phase 10C Next Steps.

python -m target_opportunity_monitor build-dashboard
Dashboard written: dashboard\index.html rows=5.
Dashboard includes revision_evidence and revision_evidence_decision.

python -m target_opportunity_monitor status
Required tables present: 23/23.
Signal rows: 0.
Signal outcome rows: 0.
Revision evidence decision: insufficient_source_coverage.
```

Notes:

- Public search snippets showed partial Yahoo Analysis values, but snippets were not treated as durable enough to seed production rows.
- Yahoo quoteSummary direct module access returned unauthorized from this environment.
- Business Quant and Finnhub documented useful estimate/recommendation endpoints, but ticker-level data requires an API key.
- The system now has an explicit evidence gate instead of a silent revision-data gap.
- The next step is Phase 10C.1 source-backed analyst revision import before any Phase 10D score-impact trial.

### 2026-06-07 - Phase 10C.1 source-backed analyst revision import workflow

Completed:

- Added default source-export CSV: `data/signals/source_exports/analyst_revision_source_export.csv`.
- Added config path: `paths.analyst_revision_source_export`.
- Added `revision_sources.py` for source-export header creation, parsing, derivation, idempotent final CSV upsert, ETF gating, and source-status reporting.
- Added CLI command: `derive-analyst-revisions`.
- Added CLI command: `revision-source-status`.
- Source-export rows require `ticker`, `signal_date`, `source`, `source_url`, and `notes`.
- Derivation supports EPS, revenue, target-price, recommendation, and estimate-dispersion formulas.
- Rows missing `source_url`, missing `notes`, malformed dates/numbers, or no derivable numeric signal are rejected.
- Active equity rows are written to `data/signals/manual/analyst_revisions.csv` with upsert identity `ticker + signal_date + source`.
- ETF source rows such as SPY/QQQ are skipped as ETF-gated and are not written to the company analyst-revision CSV.
- Extended `status`, `run-daily`, daily CSV reports, daily Markdown reports, and the static dashboard with source-backed analyst revision coverage.
- Updated README and `DOCS/analyst-revision-source-workflow.md` with the normalized source-export schema and commands.
- Kept `signals.analyst_revision_shadow_mode = true`; Phase 10C.1 does not alter final opportunity scores or alerts.

Verification:

```text
python -m unittest discover -s tests -p test_phase10a_signals.py
15 tests passed.

python -m unittest discover -s tests
102 tests passed.
Non-fatal sqlite ResourceWarnings appeared, consistent with the prior suite behavior.

python -m target_opportunity_monitor init-db
Required tables present: 23/23.

python -m target_opportunity_monitor derive-analyst-revisions --file data/signals/source_exports/analyst_revision_source_export.csv
Source rows: 0.
Derived rows: 0.
Skipped rows: 0.
Written final rows: 0.

python -m target_opportunity_monitor load-analyst-revisions
Loaded 0 rows and 0 input signals from the default header-only CSV file.
Warnings: empty_analyst_revisions.

python -m target_opportunity_monitor compute-revision-signals
Computed 0 analyst revision signals and skipped 5 active assets.
AAPL/MSFT/NVDA: missing_revision_signal.
QQQ/SPY: etf_revision_signal_gated.

python -m target_opportunity_monitor validate-revision-signals
Updated 0 rows and skipped 5 active assets.
AAPL/MSFT/NVDA: missing_revision_signal.
QQQ/SPY: etf_signal_validation_gated.

python -m target_opportunity_monitor revision-source-status
Source-backed ticker coverage: 0/3.
Missing source-backed tickers: AAPL, MSFT, NVDA.
Revision evidence decision: insufficient_source_coverage.

python -m target_opportunity_monitor revision-evidence-report
Decision: insufficient_source_coverage.
Source-backed ticker coverage: 0.
Composite signal ticker coverage: 0.
Completed 20d validation rows: 0.
Shadow mode: True.

python -m target_opportunity_monitor run-daily
Created reports/2026-06-07-daily-report.md.
Created reports/2026-06-07-daily-report.csv.
Reports include analyst revision source-backed coverage.

python -m target_opportunity_monitor build-dashboard
Dashboard written: dashboard\index.html rows=5.
Dashboard includes revision_source_status and revision_source_backed_ticker_count.

python -m target_opportunity_monitor status
Required tables present: 23/23.
Analyst revision source export exists: True.
Analyst revision source-backed tickers: 0/3.
Revision evidence decision: insufficient_source_coverage.
```

Notes:

- The default source-export CSV is intentionally header-only until the user supplies auditable provider/public-source rows.
- The final analyst revision CSV remains header-only after verification because no source-backed AAPL/MSFT/NVDA values were supplied.
- This closes the workflow gap without fabricating data and without enabling revision score impact.
- The next step is Phase 10D limited revision-score trial only if the evidence gate reaches `eligible_for_limited_score_trial`; otherwise, collect source-backed revision rows or start the next shadow signal family.

### 2026-06-07 - AAPL/MSFT/NVDA analyst revision source rows seeded

Completed:

- Checked public online sources for source-backed analyst revision fields.
- Selected SecBot public stock pages as the first manual public source because they expose current-quarter EPS average, low, high, analyst count, and current/30d/90d EPS revision history.
- Added source-backed AAPL, MSFT, and NVDA rows to `data/signals/source_exports/analyst_revision_source_export.csv`.
- Derived final rows into `data/signals/manual/analyst_revisions.csv`.
- Loaded 3 analyst revision rows and 12 raw input signals.
- Computed 3 analyst revision composite shadow signals:
  - AAPL: positive composite score 87.27.
  - MSFT: neutral composite score 48.54.
  - NVDA: positive composite score 76.02.
- Created 3 pending signal validation rows.
- Recomputed equity scores and alerts; revision signals remain shadow-only and do not alter final opportunity scoring contribution.
- Regenerated the daily Markdown report, daily CSV report, and static dashboard.

Verification:

```text
python -m target_opportunity_monitor derive-analyst-revisions
Derived 3 rows from 3 source rows.

python -m target_opportunity_monitor load-analyst-revisions
Loaded 3 rows and 12 input signals.

python -m target_opportunity_monitor compute-revision-signals
AAPL computed composite 87.27.
MSFT computed composite 48.54.
NVDA computed composite 76.02.
SPY/QQQ remained ETF-gated.

python -m target_opportunity_monitor validate-revision-signals
Updated 3 pending signal outcome rows.

python -m target_opportunity_monitor revision-source-status
Source-backed ticker coverage: 3/3.
Missing source-backed tickers: none.
Revision evidence decision: collecting_evidence.

python -m target_opportunity_monitor revision-evidence-report
Decision: collecting_evidence.
Source-backed ticker coverage: 3.
Composite signal ticker coverage: 3.
Completed 20d validation rows: 0.
Average signal confidence: 74.0073.

python -m target_opportunity_monitor status
Signal rows: 24.
Signal outcome rows: 3.
Analyst revision source-backed tickers: 3/3.
Revision evidence decision: collecting_evidence.

python -m unittest discover -s tests -p test_phase10a_signals.py
15 tests passed.

python -m unittest discover -s tests
102 tests passed.
Non-fatal sqlite ResourceWarnings appeared, consistent with prior suite behavior.
```

Notes:

- Source rows intentionally include only EPS revision and estimate dispersion fields. Revenue revision, target-price revision, and recommendation revision remain blank until a source exposes comparable current/prior values.
- Phase 10D remains blocked until enough 20d validation outcomes mature and evidence passes the configured thresholds.

### 2026-06-07 - Phase 10C.2 multi-source analyst revision aggregation

Completed:

- Added required SQLite tables: `analyst_revision_source_snapshots` and `analyst_revision_aggregates`.
- Added config defaults for revision provider order, enabled providers, weighted-median source policy, disagreement thresholds, and minimum aggregate source count.
- Added API/provider source workflow:
  - `fetch-revision-sources --provider all|fmp|alpha_vantage|yfinance|ibkr|google_finance`
  - `revision-provider-status`
  - FMP and Alpha Vantage read API keys from environment only and do not print key values.
  - yfinance/Yahoo is optional and skipped if unavailable.
  - IBKR is a non-blocking future analyst-revision adapter.
  - Google Finance is explicitly marked unsupported for analyst revision fields.
- Added no-API source templates under `data/signals/source_exports/`:
  - `secbot_public_page.csv`
  - `techi_public_page.csv`
  - `redmatter_public_page.csv`
  - `morningstar_manual.csv`
  - `gurufocus_manual.csv`
- Added source import and aggregation workflow:
  - `import-revision-source-exports`
  - `aggregate-revision-sources`
  - `derive-analyst-revisions` remains a compatibility command that imports, aggregates, and writes the final CSV.
- Updated `load-analyst-revisions` / `compute-revision-signals` to prefer aggregate rows when they exist, preventing multiple same-date source rows from competing in the raw signal inputs.
- Updated daily refresh to run source fetch, source import, and aggregation before loading analyst revisions.
- Updated status, daily Markdown report, daily CSV, dashboard health, README, and `DOCS/analyst-revision-source-workflow.md` with source snapshot count, aggregate count, source count, aggregate confidence, disagreement warnings, and provider status.
- Kept `signals.analyst_revision_shadow_mode = true`; Phase 10C.2 does not alter final opportunity scores, alerts, or portfolio guidance.

Verification:

```text
python -m unittest discover -s tests
105 tests passed.
Non-fatal sqlite ResourceWarnings appeared, consistent with prior suite behavior.

python -m target_opportunity_monitor init-db
Required tables present: 25/25.

python -m target_opportunity_monitor revision-provider-status
FMP and Alpha Vantage were missing from the current shell environment.
yfinance was available but disabled by default.
source_export was available.
google_finance was unsupported.

python -m target_opportunity_monitor fetch-revision-sources --provider all
Fetched 0, stored 0.
Warnings: missing_alpha_vantage_api_key, missing_fmp_api_key.

python -m target_opportunity_monitor import-revision-source-exports
Imported 3 source rows for AAPL, MSFT, and NVDA.

python -m target_opportunity_monitor aggregate-revision-sources
Created 3 aggregate rows and 3 final CSV rows.
Warnings: single_source_only and missing_primary_api_source for AAPL/MSFT/NVDA.

python -m target_opportunity_monitor load-analyst-revisions
Loaded 3 aggregate revision rows and 12 input signals.

python -m target_opportunity_monitor compute-revision-signals
Computed 3 equity composite shadow signals.
SPY/QQQ remained ETF-gated.

python -m target_opportunity_monitor validate-revision-signals
Updated 3 pending signal outcome rows.

python -m target_opportunity_monitor revision-source-status
Source snapshot rows: 3.
Aggregate rows: 3.
Source-backed ticker coverage: 3/3.
Revision evidence decision: collecting_evidence.

python -m target_opportunity_monitor revision-evidence-report
Decision: collecting_evidence.
Source-backed ticker coverage: 3.
Composite signal ticker coverage: 3.
Completed 20d validation rows: 0.

python -m target_opportunity_monitor refresh-data --daily-only
Pipeline run 16 completed with status ok.
New source steps ran in order: fetch-revision-sources, import-revision-source-exports, aggregate-revision-sources.
```

Notes:

- Initial Phase 10C.2 verification used SecBot public-page data only, so it correctly carried `single_source_only` and `missing_primary_api_source` warnings at that time.
- Initial Phase 10C.2 verification did not expose the previously provided FMP/Alpha Vantage environment variables in the current shell, so API fetchers degraded to warnings instead of storing provider rows at that time.
- Phase 10D remained gated until source coverage improved and enough validation horizons matured.

### 2026-06-07 - Phase 10C.2 provider expansion follow-up

Completed:

- Expanded configured analyst-revision providers to include:
  - Alpha Vantage
  - FMP
  - Business Quant
  - Finnhub
  - yfinance/Yahoo
  - source exports
- Added Business Quant API adapter:
  - Reads `BUSINESSQUANT_API_KEY` or `BUSINESS_QUANT_API_KEY`.
  - Stores current EPS/revenue consensus and EPS dispersion fields when available.
  - Leaves true revision fields blank unless comparable current/prior values exist.
- Added Finnhub API adapter:
  - Reads `FINNHUB_API_KEY` or `FINHUB_API_KEY`.
  - Stores recommendation-trend current/prior counts.
  - Keeps EPS/price-target endpoints out of the adapter because the current key may not have access to those resources.
- Enabled yfinance/Yahoo by default as an optional source:
  - Uses Yahoo Finance Analysis EPS trend data through yfinance when available.
  - Redirects the yfinance timezone cache to a local temp directory so the optional adapter does not fail on cache-file permissions.
  - Prefers current-quarter EPS trend rows, with current-year rows as fallback.
- Updated CLI provider choices, README source documentation, and `DOCS/analyst-revision-source-workflow.md`.
- Kept all revision signals in shadow mode; this follow-up does not change final scores, alerts, portfolio reviews, or trading behavior.

Verification:

```text
python -m unittest discover -s tests -p test_phase10a_signals.py
18 tests passed.

python -m unittest discover -s tests
105 tests passed.
Non-fatal sqlite ResourceWarnings appeared, consistent with prior suite behavior.

python -m target_opportunity_monitor revision-provider-status
Enabled providers: alpha_vantage, fmp, business_quant, finnhub, yfinance, source_export.
FMP, Alpha Vantage, Business Quant, Finnhub, and yfinance were available/configured.
IBKR remained not implemented and Google Finance remained unsupported.

python -m target_opportunity_monitor fetch-revision-sources --provider all
Fetched 12, stored 12, skipped 3.
Stored provider rows for AAPL/MSFT/NVDA from FMP, Business Quant, Finnhub, and yfinance/Yahoo.
Alpha Vantage returned rate/plan-limit warnings during this run.

python -m target_opportunity_monitor import-revision-source-exports
Imported 3 source-export rows for AAPL, MSFT, and NVDA.

python -m target_opportunity_monitor aggregate-revision-sources
Created 3 aggregate rows and 3 final CSV rows.
Warnings reflected source disagreement rather than missing coverage.

python -m target_opportunity_monitor load-analyst-revisions
Loaded 3 aggregate revision rows and 15 input signals.

python -m target_opportunity_monitor compute-revision-signals
Computed 3 equity composite shadow signals.
SPY/QQQ remained ETF-gated.

python -m target_opportunity_monitor validate-revision-signals
Updated 3 pending signal outcome rows.

python -m target_opportunity_monitor revision-source-status
Source snapshot rows: 18.
Aggregate rows: 3.
Source-backed ticker coverage: 3/3.
Each equity ticker had 6 sources: alpha_vantage, business_quant, finnhub, fmp, secbot_public_page, yfinance.
Revision evidence decision: collecting_evidence.

python -m target_opportunity_monitor revision-evidence-report
Decision: collecting_evidence.
Source-backed ticker coverage: 3.
Composite signal ticker coverage: 3.
Completed 20d validation rows: 0.
```

Notes:

- Phase 10D remains gated because 20-day validation outcomes have not matured yet.
- The expanded source set now produces source-disagreement warnings, which is expected and useful for aggregate confidence.
- Alpha Vantage rows may come from existing stored snapshots when the live endpoint is temporarily rate/plan-limited.

### 2026-06-07 - Post-Phase-10 +10 scoreable equity expansion

Completed:

- Expanded `configs/watchlist.csv` from 5 active assets to 15 active assets.
- Added 10 scoreable US equities: `GOOGL`, `AMZN`, `META`, `AVGO`, `AMD`, `ORCL`, `CRM`, `JPM`, `LLY`, and `COST`.
- Added matching CIK rows to `configs/cik_map.csv`.
- Loaded the expanded watchlist and refreshed daily price history/features for all 15 assets.
- Seeded SEC fundamentals for 13 equities through the existing `seed-fundamentals` workflow.
- Added one source-backed NTM EPS estimate row for each new equity using yfinance/Yahoo `forwardEps` and analyst-count fields.
- Expanded analyst revision source snapshots and aggregate rows to all 13 equities.
- Recomputed revision signals, targets, scores, alerts, alert outcomes, portfolio context, daily Markdown/CSV reports, and the static dashboard.

Verification:

```text
python -m target_opportunity_monitor refresh-data --daily-only
Pipeline run 18 completed with status ok.

python -m unittest discover -s tests
105 tests passed.
Non-fatal ResourceWarnings appeared, consistent with prior suite behavior.

python -m target_opportunity_monitor status
Asset count: 15.
Price rows: 8225.
Fundamental rows: 39.
Estimate rows: 13.
Analyst revision source snapshot rows: 44.
Analyst revision aggregate rows: 13.
Analyst revision source-backed tickers: 13/13.
Revision evidence decision: collecting_evidence.

python -m target_opportunity_monitor verify-universe
Readiness summary: ready=13/15, warnings=2.
AAPL/MSFT/NVDA plus the 10 added equities are pre-alert ready.
SPY/QQQ remain ETF-gated with missing ETF NAV/features/holdings/targets.

python -m target_opportunity_monitor run-daily
Daily Markdown and CSV reports regenerated.

python -m target_opportunity_monitor build-dashboard
Dashboard regenerated with 15 rows.
```

Notes:

- This expansion is not a buy recommendation; it only broadens the scoreable watchlist universe.
- Revision signals remain shadow-only.
- ETF readiness remains intentionally out of scope for this equity expansion.
- Portfolio context still warns about empty position/cash CSVs until real portfolio rows are supplied.

### 2026-06-07 - Analyst revision provider failure-aware aggregation

Completed:

- Adjusted provider fetch behavior so failed or unusable provider attempts write `provider_status = failed` source snapshots for the affected ticker/date/source.
- Updated aggregation so failed source snapshots are kept for audit but excluded from:
  - weighted-median values
  - source counts
  - aggregate source URL lists
  - aggregate confidence source averages
- Added `source_unavailable:SOURCE` warnings to aggregate rows when a provider failed in the latest fetch cycle.
- Added delete-on-no-available-sources behavior so old aggregate rows do not linger if every source for a ticker/date becomes unavailable.
- Updated README and `DOCS/analyst-revision-source-workflow.md` to document unavailable-source handling.

Verification:

```text
python -m unittest discover -s tests -p test_phase10a_signals.py
19 tests passed.

python -m unittest discover -s tests
106 tests passed.
Non-fatal ResourceWarnings appeared, consistent with prior suite behavior.

python -m target_opportunity_monitor fetch-revision-sources --provider all
Fetched 35, stored 35, skipped 30.
Alpha Vantage remained rate/plan-limited.
Business Quant failed during this run.
Some FMP tickers failed with HTTPError.

python -m target_opportunity_monitor aggregate-revision-sources
Created 13 aggregate rows and 13 final CSV rows.
Unavailable providers were reported as `source_unavailable:*` warnings and excluded from source counts.

python -m target_opportunity_monitor revision-source-status
Source-backed ticker coverage: 13/13.
AAPL healthy aggregate sources became: finnhub, fmp, secbot_public_page, yfinance.
Failed Alpha Vantage and Business Quant rows were shown as warnings, not healthy contributors.

python -m target_opportunity_monitor run-daily
Daily Markdown and CSV reports regenerated.

python -m target_opportunity_monitor build-dashboard
Dashboard regenerated with 15 rows.
```

Notes:

- This change improves reliability accounting only. It does not change final score/alert logic because analyst revisions remain shadow-only.
- Source snapshot row count can increase because failed provider attempts are now stored as audit records.

### 2026-06-08 - ETF readiness MVP for SPY and QQQ

Completed:

- Seeded `data/etf/manual/etf_navs.csv` with source-backed ETF NAV rows:
  - SPY uses State Street official NAV history and premium/discount history workbooks.
  - QQQ uses Invesco official price/NAV API data from the Invesco QQQ product page.
- Seeded `data/etf/manual/etf_holdings.csv` with top-10 issuer-backed holdings for both SPY and QQQ:
  - SPY uses State Street official daily holdings workbook.
  - QQQ uses Invesco official holdings API data.
- Loaded ETF NAV and holdings rows idempotently into SQLite.
- Recomputed ETF features, NAV-based targets, and ETF scores for SPY and QQQ.
- Kept ETF alerts gated with `etf_alerts_gated`; this step makes ETF data/targets/scores ready, but does not enable ETF alert rules.
- Updated report wording and README documentation so current outputs say ETF alert rules are gated, not that ETF NAV/features/holdings are missing.
- Added a regression test that fails if the default ETF seed files no longer cover SPY and QQQ.

Verification:

```text
python -m target_opportunity_monitor load-etf-navs
ETF NAVs loaded: 61 rows from data\etf\manual\etf_navs.csv.
Tickers: QQQ, SPY.

python -m target_opportunity_monitor load-etf-holdings
ETF holdings loaded: 20 rows from data\etf\manual\etf_holdings.csv.
Tickers: QQQ, SPY.

python -m target_opportunity_monitor compute-targets --ticker SPY
SPY computed target: 756.9200, warnings=none.

python -m target_opportunity_monitor compute-targets --ticker QQQ
QQQ computed target: 705.0409, warnings=none.

python -m target_opportunity_monitor compute-scores --asset-type etf
QQQ computed ETF score: 67.59, warnings=missing_premium_discount_zscore, missing_valuation_confidence.
SPY computed ETF score: 69.38, warnings=missing_valuation_confidence.

python -m target_opportunity_monitor compute-alerts --asset-type etf
QQQ and SPY skipped with etf_alerts_gated.

python -m target_opportunity_monitor etf-status
QQQ: NAV 705.0409, holdings 10, target ready True.
SPY: NAV 756.9200, holdings 10, target ready True.

python -m target_opportunity_monitor verify-universe
Readiness summary: ready=15/15, warnings=0.

python -m target_opportunity_monitor run-daily
Daily Markdown and CSV reports regenerated for 2026-06-08.

python -m target_opportunity_monitor build-dashboard
Dashboard regenerated with 15 rows.

python -m unittest discover -s tests
107 tests passed.
Non-fatal ResourceWarnings appeared, consistent with prior suite behavior.
```

Notes:

- SPY has enough NAV/premium-discount history to compute a premium/discount z-score.
- QQQ has the latest issuer NAV row and top-10 holdings, but not a NAV-history series yet, so `missing_premium_discount_zscore` remains a non-blocking ETF score warning.
- Phase 10D remains gated until analyst revision validation matures.
- The next implementation step should be an ETF alert-rules MVP only if ETF score/target reporting feels useful enough; otherwise continue collecting analyst revision validation evidence or add the next shadow signal family.

### 2026-06-08 - Phase 5B ETF alert rules MVP

Completed:

- Added ETF alert config defaults for `etf_alert_mvp_v1` and `etf_liquid_index`.
- Replaced the hard ETF alert skip with ETF-specific daily alert rules:
  - `etf_nav_discount_dislocation`
  - `etf_nav_discount_watch`
  - `etf_nav_premium_warning`
  - `etf_risk_warning`
  - `data_quality_warning`
  - `no_alert`
- Kept equity alert logic unchanged.
- ETF alert gap calculation now prefers same-snapshot ETF feature market price before falling back to daily price features.
- Added ETF data-quality warnings for missing/stale NAV, missing market price, missing target, missing score, insufficient holdings, price-date mismatch, and missing premium/discount z-score.
- Stored ETF alerts in the existing unified `alerts` table with `asset_type = etf`, `alert_model = etf_alert_mvp_v1`, and `threshold_set = etf_liquid_index`.
- Updated daily Markdown/CSV reports and dashboard behavior so ETF alerts are evaluated rather than shown as `etf_alerts_gated`.
- Updated README documentation for ETF alert rules and current ETF output behavior.

Verification:

```text
python -m target_opportunity_monitor init-db
Required tables present: 25/25.

python -m target_opportunity_monitor load-etf-navs
ETF NAVs loaded: 61 rows.

python -m target_opportunity_monitor load-etf-holdings
ETF holdings loaded: 20 rows.

python -m target_opportunity_monitor compute-targets --ticker SPY
SPY computed target: 756.9200, warnings=none.

python -m target_opportunity_monitor compute-targets --ticker QQQ
QQQ computed target: 705.0409, warnings=none.

python -m target_opportunity_monitor compute-scores --asset-type etf
QQQ computed ETF score: 67.59.
SPY computed ETF score: 69.38.

python -m target_opportunity_monitor compute-alerts --asset-type etf
QQQ: no_alert, warnings=missing_premium_discount_zscore, missing_valuation_confidence.
SPY: no_alert, warnings=missing_valuation_confidence.

python -m target_opportunity_monitor alert-status
QQQ and SPY show alert_model = etf_alert_mvp_v1 and threshold_set = etf_liquid_index.

python -m target_opportunity_monitor run-daily
Daily Markdown and CSV reports regenerated for 2026-06-08.

python -m target_opportunity_monitor build-dashboard
Dashboard regenerated with 15 rows.

python -m target_opportunity_monitor verify-universe
Readiness summary: ready=15/15, warnings=0.

python -m unittest discover -s tests
113 tests passed.
Non-fatal ResourceWarnings appeared, consistent with prior suite behavior.
```

Notes:

- Current SPY and QQQ ETF alerts are `no_alert`, not skipped.
- SPY and QQQ alert rows use aligned issuer market prices, avoiding false ETF dislocation alerts from mismatched daily price/NAV dates.
- QQQ still lacks enough NAV history for a premium/discount z-score; this remains a non-blocking warning.
- Phase 10D remains gated until analyst revision validation matures.
- A logical next step is ETF alert outcome tracking, because ETF alerts now exist but Phase 7A outcome tracking was originally equity-first.

### 2026-06-08 - Phase 7B ETF alert outcome tracking MVP

Completed:

- Extended the existing Phase 7A outcome engine to support ETF alert outcomes without adding a new table.
- Reused `alert_outcomes` and the existing unique `alert_id` upsert.
- Added migration-safe ETF outcome metadata columns: `asset_type`, `alert_model`, and `threshold_set`.
- Removed the hard ETF outcome gate that emitted `etf_outcomes_gated`.
- Added ETF actionable outcome support for:
  - `etf_nav_discount_dislocation`
  - `etf_nav_discount_watch`
  - `etf_nav_premium_warning`
  - `etf_risk_warning`
- Kept `no_alert` and `data_quality_warning` skipped for outcome creation.
- Kept equity outcome behavior unchanged.
- ETF outcome entry price now uses the stored alert current price first, which preserves Phase 5B same-snapshot ETF market-price alignment.
- ETF discount/watch alerts use positive-direction validation.
- ETF premium-warning alerts use negative-direction validation.
- ETF risk-warning alerts remain diagnostic and do not require target-hit or invalidation-hit direction.
- ETF adverse invalidation uses a tighter 3% proxy, while equities keep the existing 10% proxy.
- Added `update-alert-outcomes --asset-type all|equity|etf`.
- Updated `outcome-status`, `validation-report`, daily Markdown reports, daily CSV inputs, and dashboard data so outcome rows carry asset type.
- Updated README documentation for Phase 7A/7B outcome tracking.
- Added deterministic ETF outcome unit tests.

Verification:

```text
python -m target_opportunity_monitor init-db
Required tables present: 25/25.

python -m target_opportunity_monitor compute-alerts --asset-type etf
QQQ: no_alert, warnings=missing_premium_discount_zscore, missing_valuation_confidence.
SPY: no_alert, warnings=missing_valuation_confidence.

python -m target_opportunity_monitor update-alert-outcomes --asset-type etf
updated=0, skipped=2, with_warnings=0.
QQQ and SPY were skipped because current ETF alerts are no_alert.

python -m target_opportunity_monitor outcome-status
Outcome rows show asset type metadata.

python -m target_opportunity_monitor validation-report
Outcome rows: 12.
Equity outcome rows: 12.
ETF outcome rows: 0.

python -m target_opportunity_monitor run-daily
Daily Markdown and CSV reports regenerated for 2026-06-08.

python -m target_opportunity_monitor build-dashboard
Dashboard regenerated with 15 rows.

python -m target_opportunity_monitor verify-universe
Readiness summary: ready=15/15, warnings=0.

python -m unittest discover -s tests
118 tests passed.
Non-fatal ResourceWarnings appeared, consistent with prior suite behavior.
```

Notes:

- Live SPY and QQQ ETF outcomes are currently absent because both ETF alerts are `no_alert`.
- Deterministic tests prove actionable ETF alerts will create pending/completed outcomes once they occur.
- Phase 10D remains gated until analyst revision 20d validation matures.
- The next practical step is either to wait for validation horizons to mature, collect more daily market data, or add the next shadow signal family while analyst revisions remain in shadow mode.

### 2026-06-08 - Phase 10E news and catalyst shadow signals MVP

Completed:

- Added Phase 10E config defaults:
  - `paths.news_catalysts = "data/signals/manual/news_catalysts.csv"`
  - `signals.news_catalyst_model_version = "news_catalyst_mvp_v1"`
  - `signals.news_catalyst_shadow_mode = true`
  - `signals.news_catalyst_stale_after_days = 30`
- Added default editable news/catalyst CSV header creation.
- Added manual CSV parsing and validation for required source-backed fields:
  `ticker`, `signal_date`, `source`, `source_url`, and `headline_or_event`.
- Added optional score inputs: `sentiment_score`, `catalyst_score`,
  `urgency_score`, `confidence`, `event_date`, `topic`, and `notes`.
- Stored raw news/catalyst inputs and computed outputs in the existing
  `signals` table.
- Added output signal names:
  - `news_catalyst.sentiment`
  - `news_catalyst.catalyst`
  - `news_catalyst.urgency`
  - `news_catalyst.composite`
- Added `news_catalyst_statuses` and generic signal-status storage helpers.
- Added generic signal-validation support and reused `signal_outcomes` for
  `news_catalyst.composite`.
- Added CLI commands:
  - `load-news-catalysts`
  - `compute-news-catalyst-signals`
  - `news-catalyst-status`
  - `validate-news-catalyst-signals`
  - `news-catalyst-validation-report`
- Extended `refresh-data --daily` with:
  - `load-news-catalysts`
  - `compute-news-catalyst-signals`
  - `validate-news-catalyst-signals`
- Extended `status`, daily Markdown reports, daily CSV reports, and the static
  dashboard with news/catalyst signal and validation coverage.
- Kept news/catalyst signals in shadow mode. They do not alter scores, alerts,
  portfolio guidance, or trading behavior.
- Kept ETF news/catalyst rows gated as informational in this MVP.
- Updated README documentation with Phase 10E CSV format, commands, and the
  no-fabrication/source-backed-data rule.
- Added focused Phase 10E tests and updated stale reporting assertions.

Verification:

```text
python -m target_opportunity_monitor init-db
Required tables present: 25/25.

python -m target_opportunity_monitor load-news-catalysts
Loaded 0 rows and 0 input signals from the default header-only CSV.
Warnings: empty_news_catalysts.

python -m target_opportunity_monitor compute-news-catalyst-signals
Computed 0 signals and skipped 15 assets.
Equities: missing_news_catalyst_signal.
SPY/QQQ: etf_news_catalyst_gated.

python -m target_opportunity_monitor validate-news-catalyst-signals
Updated 0 validation rows and skipped 15 assets.
Equities: missing_news_catalyst_signal.
SPY/QQQ: etf_news_catalyst_validation_gated.

python -m target_opportunity_monitor news-catalyst-status
Shows 13 equities with missing_news_catalyst_signal and SPY/QQQ as ETF-gated.

python -m target_opportunity_monitor news-catalyst-validation-report
Signal outcome rows: 0.

python -m target_opportunity_monitor run-daily
Daily Markdown and CSV reports regenerated for 2026-06-08.

python -m target_opportunity_monitor build-dashboard
Dashboard regenerated with 15 rows.

python -m target_opportunity_monitor refresh-data --daily-only
Pipeline run 19: daily_refresh status=ok.
New news/catalyst steps ran in order and stayed warning-only because the CSV is header-only.

python -m target_opportunity_monitor status
News/catalyst file exists: True.
News/catalyst signal rows: 0.
News/catalyst validation rows: 0.
Revision evidence decision: collecting_evidence.

python -m target_opportunity_monitor verify-universe
Readiness summary: ready=15/15, warnings=0.

python -m unittest discover -s tests
125 tests passed.
Non-fatal ResourceWarnings appeared, consistent with prior suite behavior.
```

Notes:

- `data/signals/manual/news_catalysts.csv` is intentionally header-only after
  implementation. No news/catalyst score was fabricated.
- Phase 10D remains gated because analyst revision evidence is still
  `collecting_evidence`.
- Phase 10E is workflow-ready and validation-ready, but it will not produce
  evidence until source-backed catalyst rows are entered.
- The next practical step is either to collect source-backed news/catalyst rows,
  keep waiting for analyst revision 20d evidence to mature, or add another
  shadow signal family while all advanced-signal score impact remains disabled.

### 2026-06-08 - Phase 10E.1 news/catalyst source aggregation MVP

Completed:

- Added Phase 10E.1 config defaults:
  - `paths.news_catalyst_source_exports_dir = "data/signals/source_exports/news_catalysts"`
  - `signals.news_catalyst_provider_order = ["alpha_vantage", "finnhub", "fmp", "source_export"]`
  - `signals.news_catalyst_enabled_providers = ["alpha_vantage", "finnhub", "fmp", "source_export"]`
  - `signals.news_catalyst_source_policy = "weighted_median"`
  - `signals.news_catalyst_lookback_days = 14`
  - `signals.news_catalyst_max_items_per_ticker = 5`
  - `signals.news_catalyst_disagreement_warning_threshold = 15.0`
  - `signals.news_catalyst_high_disagreement_threshold = 30.0`
  - `signals.news_catalyst_min_sources_for_aggregate = 1`
- Added required SQLite tables:
  - `news_catalyst_source_snapshots`
  - `news_catalyst_aggregates`
- Added typed storage helpers for news/catalyst source snapshots and aggregate
  rows.
- Added `news_catalyst_sources.py` with:
  - source-export CSV header/template creation,
  - audited source-export parsing and import,
  - Alpha Vantage, Finnhub, and FMP provider adapters,
  - provider failure/rate-limit warnings that do not break the pipeline,
  - weighted-median aggregation,
  - aggregate confidence and source-disagreement warnings,
  - final compatibility export to `data/signals/manual/news_catalysts.csv`,
  - source coverage/status reporting.
- Added CLI commands:
  - `fetch-news-catalyst-sources --provider all|alpha_vantage|finnhub|fmp`
  - `import-news-catalyst-source-exports`
  - `aggregate-news-catalyst-sources`
  - `news-catalyst-source-status`
- Extended `refresh-data --daily` so it runs:
  - `fetch-news-catalyst-sources`
  - `import-news-catalyst-source-exports`
  - `aggregate-news-catalyst-sources`
  before the existing `load-news-catalysts` step.
- Extended `status`, daily Markdown reports, daily CSV reports, and the static
  dashboard with news/catalyst source snapshot count, aggregate count,
  source-backed ticker coverage, aggregate confidence, and source warnings.
- Added `DOCS/news-catalyst-source-workflow.md`.
- Updated README with Phase 10E.1 commands, source-export schema, provider
  rules, aggregation rules, and the no-fabrication rule.
- Kept news/catalyst signals in shadow mode. Phase 10E.1 does not change final
  opportunity scores, alerts, portfolio guidance, notifications, execution, or
  orders.

Verification:

```text
python -m target_opportunity_monitor init-db
Required tables present: 27/27.

python -m target_opportunity_monitor fetch-news-catalyst-sources --provider all
Fetched/stored 65 headline/news snapshots across the 13 active equities.
Warnings included Alpha Vantage rate/plan limits, Finnhub sentiment HTTP
errors, and FMP HTTP errors.

python -m target_opportunity_monitor import-news-catalyst-source-exports
Imported 0 rows from the default header-only source-export templates.
Warnings: empty_news_catalyst_source_exports.

python -m target_opportunity_monitor aggregate-news-catalyst-sources
Aggregates: 0.
Final CSV rows: 0.
Reason: fetched provider rows were headline-only or unavailable for numeric
sentiment/catalyst fields, so the system refused to fabricate scores.

python -m target_opportunity_monitor load-news-catalysts
Loaded 0 rows and 0 input signals from data/signals/manual/news_catalysts.csv.
Warnings: empty_news_catalysts.

python -m target_opportunity_monitor compute-news-catalyst-signals
Computed 0 signals and skipped 15 assets.
Equities: missing_news_catalyst_signal.
SPY/QQQ: etf_news_catalyst_gated.

python -m target_opportunity_monitor validate-news-catalyst-signals
Updated 0 validation rows and skipped 15 assets.
Equities: missing_news_catalyst_signal.
SPY/QQQ: etf_news_catalyst_validation_gated.

python -m target_opportunity_monitor news-catalyst-source-status
Source snapshot rows: 91.
Aggregate rows: 0.
Source-backed ticker coverage: 0/13.
Provider keys are visible by variable presence for Alpha Vantage, Finnhub, and
FMP; key values are not printed.

python -m target_opportunity_monitor run-daily
Daily Markdown and CSV reports regenerated for 2026-06-08.

python -m target_opportunity_monitor build-dashboard
Dashboard regenerated with 15 rows.

python -m target_opportunity_monitor status
Required tables present: 27/27.
News/catalyst source snapshot rows: 91.
News/catalyst aggregate rows: 0.
Latest news/catalyst aggregate date: none.
News/catalyst source-backed tickers: 0/13.
Revision evidence decision: collecting_evidence.

python -m target_opportunity_monitor refresh-data --daily-only
Pipeline run 20: daily_refresh status=ok.
New Phase 10E.1 steps ran in order before load-news-catalysts.

python -m unittest discover -s tests
129 tests passed.
Non-fatal ResourceWarnings appeared, consistent with prior suite behavior.
```

Notes:

- Phase 10E.1 is source-ready and aggregation-ready, but live source-backed
  numeric news/catalyst coverage remains `0/13` because the providers did not
  return usable numeric sentiment/catalyst values in this run.
- Headline-only rows are intentionally preserved in
  `news_catalyst_source_snapshots` for audit, but they do not create final
  signal rows.
- Phase 10D remains gated because analyst revision evidence is still
  `collecting_evidence`.
- The next practical step is to either add a provider/source that returns
  numeric news sentiment reliably, manually capture numeric provider-export
  rows, or add another shadow signal family while advanced signals remain
  shadow-only.

### 2026-06-08 - Phase 10E.2 news/catalyst provider reliability and numeric backfill MVP

Completed:

- Added Phase 10E.2 config defaults:
  - `paths.news_catalyst_cache = "data/signals/cache/news_catalysts"`
  - `signals.news_catalyst_provider_request_budget = 3`
  - `signals.news_catalyst_provider_retry_delay_seconds = 1.0`
  - `signals.news_catalyst_cache_stale_hours = 24`
  - `signals.news_catalyst_use_cache = true`
- Added key-free raw provider payload caching under
  `data/signals/cache/news_catalysts/{provider}/`.
- Extended `fetch-news-catalyst-sources` with:
  - `--max-tickers N`
  - `--force-refresh`
  - `--use-cache`
  - `--no-cache`
- Updated provider handling so:
  - fresh cached payloads are reused before live calls,
  - live calls are capped by the configured provider request budget or
    `--max-tickers`,
  - auth, plan, rate-limit, HTTP, malformed, empty, and headline-only states are
    classified more clearly,
  - provider limit payloads are not cached as valid source payloads,
  - hard provider stops skip the remaining tickers for that provider cycle
    instead of hammering the API.
- Extended `status`, `news-catalyst-source-status`, daily reports, and the
  dashboard payload with cache file count, latest cache timestamp, numeric
  source snapshot count, headline-only source snapshot count, provider cache
  metadata, provider warnings, and source-backed coverage.
- Updated README and `DOCS/news-catalyst-source-workflow.md` with cache,
  provider-budget, fetch-switch, and no-fabrication rules.
- Added `.gitignore` coverage for local news/catalyst cache payloads.
- Kept news/catalyst signals shadow-only. Phase 10E.2 does not change final
  opportunity scores, alerts, portfolio guidance, notifications, execution, or
  orders.

Verification:

```text
python -m unittest discover -s tests -p test_phase10e_news_catalysts.py
12 tests passed.

python -m unittest discover -s tests
130 tests passed.
Non-fatal ResourceWarnings appeared, consistent with prior suite behavior.

python -m target_opportunity_monitor init-db
Required tables present: 27/27.

python -m target_opportunity_monitor fetch-news-catalyst-sources --provider alpha_vantage --max-tickers 1 --force-refresh
Result: provider=alpha_vantage, fetched=0, stored=0, skipped=13,
live_requests=1, cache_hits=0, cache_misses=0, cache_writes=0.
Alpha Vantage returned a rate-limit payload, so no invalid cache payload was
written and the remaining tickers were skipped for that provider cycle.

python -m target_opportunity_monitor aggregate-news-catalyst-sources
Aggregates: 0.
Final CSV rows: 0.
Reason: source snapshots still have no aggregatable numeric news/catalyst
fields.

python -m target_opportunity_monitor load-news-catalysts
Loaded 0 rows and 0 input signals.

python -m target_opportunity_monitor compute-news-catalyst-signals
Computed 0 signals and skipped 15 assets.

python -m target_opportunity_monitor validate-news-catalyst-signals
Updated 0 validation rows and skipped 15 assets.

python -m target_opportunity_monitor news-catalyst-source-status
Shows cache metadata, numeric source snapshot count, headline-only source
snapshot count, provider warnings, and source-backed coverage.

python -m target_opportunity_monitor refresh-data --daily-only
Pipeline run 21: daily_refresh status=ok.
The news/catalyst provider step used bounded provider fetching, cache-aware
Finnhub rows, and clearer warning classifications.
```

Notes:

- Live news/catalyst numeric coverage remains `0/13` because providers still did
  not return source-backed numeric sentiment/catalyst fields.
- Finnhub headline rows remain preserved for audit and cache reuse, but they do
  not create aggregates without numeric sentiment/catalyst inputs.
- Phase 10D remains gated because analyst revision evidence is still
  `collecting_evidence`.
- The next practical step is to either wait for provider quota and rerun bounded
  Alpha Vantage/Finnhub/FMP fetches, add audited numeric provider-export rows,
  or add another shadow signal family while advanced signals remain shadow-only.

### 2026-06-08 - Phase 10F SEC insider activity shadow signals MVP

Completed:

- Added Phase 10F config defaults:
  - `paths.insider_cache = "data/signals/cache/insider_transactions"`
  - `signals.insider_activity_model_version = "insider_activity_mvp_v1"`
  - `signals.insider_activity_shadow_mode = true`
  - `signals.insider_activity_lookback_days = 180`
  - `signals.insider_activity_stale_after_days = 14`
  - `signals.insider_activity_fetch_limit_per_ticker = 40`
  - `signals.insider_activity_min_transaction_value = 10000`
- Added the required `insider_transaction_source_snapshots` table and storage
  helpers for normalized SEC Form 4 transaction rows.
- Added official SEC Form 4 workflow:
  - reads `configs/cik_map.csv`,
  - fetches SEC submissions JSON,
  - selects recent Form 4 filings,
  - fetches raw ownership XML/document from SEC archive,
  - caches raw SEC payloads under
    `data/signals/cache/insider_transactions/`,
  - skips ETFs with `etf_insider_activity_gated`.
- Added insider shadow signal engine:
  - `insider_activity.open_market_buying`
  - `insider_activity.sale_pressure`
  - `insider_activity.routine_activity`
  - `insider_activity.composite`
- Added CLI commands:
  - `fetch-insider-transactions`
  - `compute-insider-signals`
  - `validate-insider-signals`
  - `insider-status`
  - `insider-validation-report`
- Reused `signal_outcomes` for insider validation with the existing 5d, 20d,
  60d, and 120d horizon framework.
- Integrated insider activity into:
  - `status`,
  - daily Markdown reports,
  - daily CSV reports,
  - static dashboard data and UI,
  - `refresh-data --daily`,
  - README,
  - `DOCS/insider-activity-source-workflow.md`.
- Kept insider activity shadow-only. Phase 10F does not change final
  opportunity scores, alerts, portfolio guidance, notifications, execution, or
  orders.

Verification:

```text
python -m unittest discover -s tests -p test_phase10f_insider_activity.py
6 tests passed.

python -m unittest discover -s tests
136 tests passed.
Non-fatal ResourceWarnings appeared, consistent with prior suite behavior.

python -m target_opportunity_monitor init-db
Required tables present: 28/28.

python -m target_opportunity_monitor fetch-insider-transactions --ticker AAPL --refresh-cache
Fetched filings: 24.
Stored source rows: 35.
Warnings: six recent AAPL Form 4 filings had no parsed transaction rows.

python -m target_opportunity_monitor compute-insider-signals --ticker AAPL
AAPL composite: 25.00.
Direction: negative.
Warnings: insider_activity_shadow_mode, routine_or_compensation_related.

python -m target_opportunity_monitor validate-insider-signals --ticker AAPL
Updated validation rows: 1.
Outcome status: partial.

python -m target_opportunity_monitor insider-validation-report
Signal outcome rows: 1.
Partial: 1.
Directional hit rate: 1.0000.

python -m target_opportunity_monitor run-daily
Daily Markdown and CSV reports regenerated with insider activity fields.

python -m target_opportunity_monitor build-dashboard
Dashboard regenerated with 15 rows and insider activity fields.

python -m target_opportunity_monitor refresh-data --daily-only --ticker AAPL
Pipeline run 22: daily_refresh status=ok.
New Phase 10F steps ran in order:
fetch-insider-transactions, compute-insider-signals, validate-insider-signals.
Expected provider/source warnings remained non-fatal.

python -m target_opportunity_monitor status
Required tables present: 28/28.
Insider activity source rows: 35.
Latest insider activity source date: 2026-05-27.
Insider activity signal rows: 4.
Insider activity validation rows: 1.
```

Notes:

- Phase 10D remains gated because analyst revision evidence is still
  `collecting_evidence`.
- News/catalyst numeric coverage remains blocked by provider/source limitations.
- The next practical step is to either fetch insider activity for all 13 active
  equities, improve news/catalyst numeric coverage, or continue adding
  source-backed shadow signal families while advanced signals remain
  shadow-only.

### 2026-06-08 - Phase 10F.1 full-watchlist insider coverage and source health

Completed:

- Added Phase 10F.1 insider fetch controls:
  - `signals.insider_activity_max_tickers_per_run = 13`
  - `signals.insider_activity_use_cache = true`
  - `fetch-insider-transactions --max-tickers N`
  - `fetch-insider-transactions --use-cache`
  - `fetch-insider-transactions --no-cache`
  - `fetch-insider-transactions --force-refresh`
- Added per-ticker SEC fetch quality checks under
  `insider_activity_fetch:{ticker}` so source health can distinguish:
  source-backed rows, confirmed no-recent-activity, parse/source warnings,
  missing CIK/source gaps, stale rows, and ETF gating.
- Added the new CLI command:
  - `insider-source-status`
- Extended `status`, daily Markdown reports, daily CSV reports, and the static
  dashboard with insider source coverage and source-health fields:
  - `insider_activity_source_status`
  - `insider_activity_source_coverage_count`
  - per-ticker source row counts and latest source dates.
- Updated `refresh-data --daily` so the insider fetch step uses the configured
  full-watchlist budget and cache policy.
- Kept insider activity shadow-only. No final score, alert, portfolio,
  notification, broker, or execution behavior changed.

Verification:

```text
python -m unittest discover -s tests -p test_phase10f_insider_activity.py
8 tests passed.

python -m unittest discover -s tests
138 tests passed.
Non-fatal ResourceWarnings appeared, consistent with prior suite behavior.

python -m target_opportunity_monitor init-db
Required tables present: 28/28.

python -m target_opportunity_monitor fetch-insider-transactions --max-tickers 13
Fetched filings: 353.
Stored source rows this run: 1077.
Processed tickers: AAPL, AMD, AMZN, AVGO, COST, CRM, GOOGL, JPM, LLY, META,
MSFT, NVDA, ORCL.
SPY/QQQ remained ETF-gated.

python -m target_opportunity_monitor compute-insider-signals
Computed: 13 equities.
Skipped: 2 ETFs.

python -m target_opportunity_monitor validate-insider-signals
Updated validation rows: 13.
Skipped: 2 ETFs.

python -m target_opportunity_monitor insider-source-status
Active equity coverage: 13/13.
Source-backed tickers: 11/13.
No-recent-activity tickers: LLY, ORCL.
ETF-gated tickers: QQQ, SPY.
Stale source tickers: AVGO, COST, CRM.
Missing source tickers: none.

python -m target_opportunity_monitor insider-status
Shows 13 equity insider composites and SPY/QQQ gated.

python -m target_opportunity_monitor insider-validation-report
Signal outcome rows: 13.
Pending: 8.
Partial: 5.
Completed: 0.

python -m target_opportunity_monitor refresh-data --daily-only
Pipeline run 23: daily_refresh status=ok.
verify-universe stayed ready at 15/15.

python -m target_opportunity_monitor run-daily
Created reports/2026-06-08-daily-report.md.
Created reports/2026-06-08-daily-report.csv.

python -m target_opportunity_monitor build-dashboard
Dashboard regenerated with 15 rows.

python -m target_opportunity_monitor verify-universe
Readiness summary: ready=15/15, warnings=0.
```

Notes:

- SEC returned HTTP 429 rate-limit responses for some Form 4 filing documents
  during the full-watchlist fetch. These are now captured as source-health
  warnings and do not break the pipeline.
- Insider coverage is operational for all 13 active equities, but some tickers
  still carry stale-source or parse-warning labels. The daily cached workflow
  should gradually improve this as SEC requests succeed.
- Phase 10D remains gated because analyst revision evidence is still collecting
  and has no mature 20d validation pass yet.
- News/catalyst numeric coverage remains blocked by provider/source limitations.
- The next practical cleanup is optional SEC pacing/backoff to reduce 429 noise;
  otherwise the system can continue collecting shadow-signal evidence.

### 2026-06-08 - Phase 10F.2 SEC pacing and insider warning cleanup MVP

Completed:

- Added Phase 10F.2 SEC pacing and backoff defaults:
  - `signals.insider_activity_sec_request_delay_seconds = 0.2`
  - `signals.insider_activity_sec_rate_limit_cooldown_seconds = 60`
  - `signals.insider_activity_stop_on_rate_limit = true`
  - `signals.insider_activity_max_live_form4_fetches_per_ticker = 10`
  - `signals.insider_activity_skip_successful_fetch_same_day = true`
- Hardened `fetch-insider-transactions`:
  - uses cached submissions and Form 4 documents first,
  - paces live SEC document requests,
  - caps live Form 4 fetches per ticker,
  - stops live fetches for a ticker after SEC 429 rate limits,
  - skips missing live documents after a successful same-day fetch unless
    `--force-refresh` is used.
- Added compact source-health warnings while preserving raw accession-level
  evidence in `data_quality_checks`.
- Added `insider-source-status --verbose` for raw SEC filing warning detail.
- Extended `status`, daily Markdown reports, daily CSV reports, and dashboard
  health with SEC-rate-limited insider source state.
- Updated README and `DOCS/insider-activity-source-workflow.md`.
- Kept insider activity shadow-only. No final score, alert, portfolio,
  notification, broker, or execution behavior changed.

Verification:

```text
python -m unittest discover -s tests -p test_phase10f_insider_activity.py
11 tests passed.

python -m unittest discover -s tests
141 tests passed.
Non-fatal ResourceWarnings appeared, consistent with prior suite behavior.

python -m target_opportunity_monitor init-db
Required tables present: 28/28.

python -m target_opportunity_monitor fetch-insider-transactions --max-tickers 13
Fetched filings: 383.
Stored source rows this run: 1106.
Warnings were compact:
JPM:live_form4_fetch_budget_exhausted: 20 filings,
LLY:live_form4_fetch_budget_exhausted: 30 filings,
ORCL:live_form4_fetch_budget_exhausted: 10 filings,
plus compact no-transaction and ETF-gated summaries.

python -m target_opportunity_monitor insider-source-status
Active equity coverage: 13/13.
Source-backed tickers: 13/13.
SEC-rate-limited tickers: none.
Stale source tickers: AVGO, COST, CRM, LLY.
ETF-gated tickers: QQQ, SPY.

python -m target_opportunity_monitor insider-source-status --verbose
Displayed raw accession-level budget/no-transaction details for audit.

python -m target_opportunity_monitor refresh-data --daily-only
Pipeline run 24: daily_refresh status=ok.
fetch-insider-transactions used compact warnings:
JPM:live_form4_fetch_budget_exhausted: 10 filings,
LLY:live_form4_fetch_budget_exhausted: 20 filings,
and no current SEC-rate-limited tickers.

python -m target_opportunity_monitor run-daily
Created reports/2026-06-08-daily-report.md.
Created reports/2026-06-08-daily-report.csv.

python -m target_opportunity_monitor build-dashboard
Dashboard regenerated with 15 rows.

python -m target_opportunity_monitor status
Insider activity source coverage: 13/13.
Insider activity source-backed tickers: 13/13.
Insider activity SEC-rate-limited tickers: 0.

python -m target_opportunity_monitor verify-universe
Readiness summary: ready=15/15, warnings=0.
```

Notes:

- SEC 429 responses are now separated from generic parse warnings and compacted
  in user-facing output.
- Heavy Form 4 tickers can still hit the live Form 4 budget; this is intentional
  and prevents the daily workflow from hammering SEC.
- Phase 10D remains gated because analyst revision evidence is still collecting
  and has no mature 20d validation pass yet.
- News/catalyst numeric coverage remains a separate source/provider limitation.

### 2026-06-08 - Phase 10E.3 news/catalyst numeric coverage work queue MVP

Completed:

- Added a durable news/catalyst coverage planner that prioritizes:
  - missing active equity source-backed numeric rows first,
  - stale source-backed rows second.
- Added a generated refill template:
  - `data/signals/source_exports/news_catalysts/news_catalyst_missing_coverage_queue.csv`
- The generated template is import-safe:
  - blank coverage-queue rows are skipped until filled with source URL,
    headline/event, and provider-backed numeric fields.
  - headline-only rows remain audit evidence but do not create numeric
    aggregates.
- Added CLI support:
  - `news-catalyst-coverage-plan`
  - `fetch-news-catalyst-sources --coverage-plan`
  - `news-catalyst-source-status --missing-only`
  - `news-catalyst-source-status --provider-warnings`
- Updated `refresh-data --daily` so the provider fetch step uses the coverage
  planner when no ticker filter is supplied.
- Extended `status`, daily Markdown reports, daily CSV reports, and the static
  dashboard with:
  - news/catalyst missing source-backed ticker count,
  - latest coverage-plan tickers,
  - provider warning summaries,
  - per-row coverage priority/reason.
- Updated README and `DOCS/news-catalyst-source-workflow.md` with the coverage
  queue and no-fabrication refill workflow.
- Kept news/catalyst signals shadow-only. No final score, alert, portfolio,
  notification, broker, or execution behavior changed.

Verification:

```text
python -m unittest discover -s tests -p test_phase10e_news_catalysts.py
14 tests passed.

python -m unittest discover -s tests
143 tests passed.
Non-fatal ResourceWarnings appeared, consistent with prior suite behavior.

python -m target_opportunity_monitor init-db
Required tables present: 28/28.

python -m target_opportunity_monitor news-catalyst-coverage-plan
Planned tickers under the default budget: AMD, AMZN, AVGO.
Missing source-backed tickers: 12.
Provider warnings showed Alpha Vantage rate-limited, Finnhub headline-only,
and FMP plan-limited states.

python -m target_opportunity_monitor news-catalyst-source-status --missing-only
Displayed the 12 active equities missing source-backed numeric news/catalyst
rows; AAPL remained the only covered equity.

python -m target_opportunity_monitor fetch-news-catalyst-sources --coverage-plan
Provider fetch ran against AMD, AMZN, and AVGO only.
Stored 15 source snapshots, used 3 cache hits, made 2 live requests, and kept
rate/plan limitations as warnings.

python -m target_opportunity_monitor import-news-catalyst-source-exports
Generated blank queue rows were safely skipped.

python -m target_opportunity_monitor aggregate-news-catalyst-sources
Aggregate rows remained 1 because provider results for the queued names were
headline-only or unavailable, not numeric.

python -m target_opportunity_monitor load-news-catalysts
Loaded 1 final news/catalyst row for AAPL.

python -m target_opportunity_monitor compute-news-catalyst-signals
Computed AAPL in shadow mode and marked remaining equities as
`missing_news_catalyst_signal`.

python -m target_opportunity_monitor validate-news-catalyst-signals
Updated 1 pending AAPL validation row.

python -m target_opportunity_monitor refresh-data --daily-only
Pipeline run 25: daily_refresh status=ok.
The news/catalyst provider fetch step used the coverage-plan queue.

python -m target_opportunity_monitor run-daily
Created reports/2026-06-08-daily-report.md.
Created reports/2026-06-08-daily-report.csv.

python -m target_opportunity_monitor build-dashboard
Dashboard regenerated with 15 rows.

python -m target_opportunity_monitor status
News/catalyst source-backed tickers: 1/13.
News/catalyst missing source-backed tickers: 12.
News/catalyst coverage-plan tickers: AMD, AMZN, AVGO.
```

Notes:

- Phase 10D remains gated because analyst revision evidence is still
  collecting and has no mature 20d validation pass yet.
- News/catalyst now has an operational work queue, but source-backed numeric
  coverage is still limited by provider availability and user/provider exports.
- The next practical step is to either fill the generated queue template with
  source-backed numeric provider exports, continue bounded provider collection,
  or add the next official/free shadow signal family while Phase 10D matures.

### 2026-06-08 - Phase 10E.4 news/catalyst numeric coverage expansion MVP

Completed:

- Added Phase 10E.4 news/catalyst source registry defaults:
  - `signals.news_catalyst_provider_order` now includes Alpha Vantage,
    Marketaux, EODHD, Finnhub, FMP, X recent search, Truth Social public, and
    source exports.
  - `signals.news_catalyst_text_backfill_enabled = true`.
  - `signals.news_catalyst_text_backfill_model_version =
    "news_text_lexicon_mvp_v1"`.
  - `signals.news_catalyst_min_numeric_coverage = 13`.
  - social/manual source defaults include Kobeissi Letter and Serenity-style
    manual captures.
- Added provider adapters for:
  - `marketaux` using `MARKETAUX_API_KEY` or `MARKET_AUX_API_KEY`,
  - `eodhd` using `EODHD_API_KEY` or `EOD_HISTORICAL_DATA_API_KEY`,
  - `x_recent_search` using `X_BEARER_TOKEN` or `TWITTER_BEARER_TOKEN`,
  - `truth_social_public` as source-backed text only.
- Added source-export templates for Marketaux, EODHD, Serenity, Kobeissi
  Letter, Truth Social, and X manual/provider captures.
- Added deterministic text-derived numeric backfill:
  - command: `compute-news-catalyst-text-backfill`,
  - source: existing source-backed headline/summary/event text,
  - model: transparent lexicon rules only,
  - warnings: `text_derived_sentiment`, `lower_confidence_source`, and
    `not_provider_numeric`,
  - lower aggregation weight than provider-native numeric rows.
- Updated aggregation and source status to distinguish:
  - provider numeric coverage,
  - text-derived numeric coverage,
  - total numeric coverage,
  - headline-only rows,
  - missing tickers,
  - stale coverage queue state,
  - provider limitation summaries.
- Updated `refresh-data --daily` so the news/catalyst sequence runs:
  provider fetch, source-export import, text backfill, aggregation, load,
  compute, and validation.
- Updated daily Markdown reports, daily CSV reports, dashboard health, status
  output, README, and `DOCS/news-catalyst-source-workflow.md`.
- Kept news/catalyst signals shadow-only. No final score, alert, portfolio,
  notification, broker, or execution behavior changed.

Verification:

```text
python -m unittest discover -s tests -p test_phase10e_news_catalysts.py
16 tests passed.

python -m unittest discover -s tests
145 tests passed.
Non-fatal ResourceWarnings appeared, consistent with prior suite behavior.

python -m target_opportunity_monitor init-db
Required tables present: 28/28.

python -m target_opportunity_monitor news-catalyst-coverage-plan --refresh-template
Coverage queue regenerated from current DB state.
Queue stale: false.
Initial queue tickers before backfill: AMD, AMZN, AVGO.

python -m target_opportunity_monitor fetch-news-catalyst-sources --coverage-plan
Provider fetch ran with the bounded coverage plan.
Stored source snapshots and preserved provider limitations as warnings.

python -m target_opportunity_monitor fetch-news-catalyst-sources --provider marketaux --coverage-plan
Returned `missing_marketaux_api_key`; no key value was printed or stored.

python -m target_opportunity_monitor import-news-catalyst-source-exports
Imported source-export directory.
Blank/manual templates were safely skipped.

python -m target_opportunity_monitor compute-news-catalyst-text-backfill
Derived 58 lower-confidence text-backed numeric snapshots.
Skipped AAPL because provider-native numeric coverage already existed.

python -m target_opportunity_monitor aggregate-news-catalyst-sources
Aggregate rows: 13.
Final compatibility CSV rows: 13.

python -m target_opportunity_monitor load-news-catalysts
Loaded 13 news/catalyst rows and 50 input signals.

python -m target_opportunity_monitor compute-news-catalyst-signals
Computed 13 equity news/catalyst signals in shadow mode.
Skipped SPY and QQQ as ETF-gated.

python -m target_opportunity_monitor validate-news-catalyst-signals
Updated 13 pending validation rows.

python -m target_opportunity_monitor news-catalyst-source-status
News/catalyst numeric ticker coverage: 13/13.
Provider numeric ticker coverage: 1/13.
Text-derived ticker coverage: 12/13.
Missing source-backed tickers: none.

python -m target_opportunity_monitor refresh-data --daily-only
Pipeline run 26: daily_refresh status=ok.
The pipeline included `compute-news-catalyst-text-backfill`.

python -m target_opportunity_monitor run-daily
Created reports/2026-06-08-daily-report.md.
Created reports/2026-06-08-daily-report.csv.

python -m target_opportunity_monitor build-dashboard
Dashboard regenerated with 15 rows.

python -m target_opportunity_monitor status
News/catalyst numeric ticker coverage: 13/13.
News/catalyst provider numeric ticker coverage: 1/13.
News/catalyst text-derived ticker coverage: 12/13.
News/catalyst coverage queue stale: False.
```

Notes:

- This closes the operational numeric-coverage bottleneck: all 13 active
  equities now have numeric news/catalyst rows.
- Provider-native quality is still thin. Current live state remains:
  - Alpha Vantage rate-limited,
  - Marketaux key missing,
  - EODHD key missing,
  - X bearer token missing,
  - Finnhub headline-only for this use case,
  - FMP plan-limited.
- Text-derived rows are source-backed and deterministic, but intentionally
  lower-confidence and shadow-only.
- Phase 10D remains gated because analyst revision evidence is still
  collecting and has no mature 20d validation pass yet.
- The next practical quality step is to add Marketaux, EODHD, X, or manual
  provider exports so more of the 13/13 coverage becomes provider-native.

### 2026-06-08 - Phase 10E.5 provider-native news/catalyst quality and queue hygiene MVP

Completed:

- Split news/catalyst coverage planning into explicit modes:
  - `missing`,
  - `provider-upgrade`,
  - `all`.
- Added a provider-native upgrade queue for equities that have text-derived
  numeric rows but no provider-native numeric rows:
  - `data/signals/source_exports/news_catalysts/news_catalyst_provider_upgrade_queue.csv`
- Kept the missing-numeric queue separate:
  - `data/signals/source_exports/news_catalysts/news_catalyst_missing_coverage_queue.csv`
- Fixed queue hygiene so complete total numeric coverage no longer makes the
  missing queue look stale after the missing template is refreshed.
- Added CLI visibility:
  - `news-catalyst-coverage-plan --mode missing`,
  - `news-catalyst-coverage-plan --mode provider-upgrade`,
  - `fetch-news-catalyst-sources --coverage-mode missing|provider-upgrade|all`,
  - `news-catalyst-source-status --provider-upgrade-only`.
- Updated `status`, daily Markdown reports, daily CSV reports, and the static
  dashboard to show:
  - missing numeric ticker count,
  - provider-native upgrade needed count,
  - provider-native upgrade tickers,
  - missing queue stale state,
  - provider-upgrade queue stale state.
- Updated aggregation precedence so provider-native numeric snapshots dominate
  deterministic text-derived snapshots for the same ticker/date, while
  preserving text-derived snapshots for audit.
- Updated README and `DOCS/news-catalyst-source-workflow.md`.
- Kept news/catalyst signals shadow-only. No final score, alert, portfolio,
  notification, broker, or execution behavior changed.

Verification:

```text
python -m unittest discover -s tests -p test_phase10e_news_catalysts.py
17 tests passed.

python -m unittest discover -s tests
146 tests passed.
Non-fatal ResourceWarnings appeared, consistent with prior suite behavior.

python -m target_opportunity_monitor init-db
Required tables present: 28/28.

python -m target_opportunity_monitor news-catalyst-coverage-plan --mode missing --refresh-template
Missing queue stale: False.
Missing numeric tickers: none.
Planned tickers: none.

python -m target_opportunity_monitor news-catalyst-coverage-plan --mode provider-upgrade --refresh-template
Provider upgrade queue stale: False.
Planned tickers under the default budget: AMD, AMZN, AVGO.
Provider-native upgrade tickers: AMD, AMZN, AVGO, COST, CRM, GOOGL, JPM, LLY,
META, MSFT, NVDA, ORCL.

python -m target_opportunity_monitor news-catalyst-source-status --provider-upgrade-only
Displayed the 12 active equities with text-derived numeric rows and no
provider-native numeric rows.

python -m target_opportunity_monitor fetch-news-catalyst-sources --coverage-plan
Fetched the provider-upgrade coverage plan tickers under the default budget.
Provider limitations remained warnings, not failures.

python -m target_opportunity_monitor aggregate-news-catalyst-sources
Aggregate rows: 13.
Final compatibility CSV rows: 13.

python -m target_opportunity_monitor load-news-catalysts
Loaded 13 news/catalyst rows and 50 input signals.

python -m target_opportunity_monitor compute-news-catalyst-signals
Computed 13 equity news/catalyst signals in shadow mode.
Skipped SPY and QQQ as ETF-gated.

python -m target_opportunity_monitor validate-news-catalyst-signals
Updated 13 pending validation rows.

python -m target_opportunity_monitor refresh-data --daily-only
Pipeline run 27: daily_refresh status=ok.
The provider fetch step used the provider-upgrade coverage plan after missing
numeric coverage was complete.

python -m target_opportunity_monitor run-daily
Created reports/2026-06-08-daily-report.md.
Created reports/2026-06-08-daily-report.csv.

python -m target_opportunity_monitor build-dashboard
Dashboard regenerated with 15 rows.

python -m target_opportunity_monitor status
News/catalyst numeric ticker coverage: 13/13.
News/catalyst provider numeric ticker coverage: 1/13.
News/catalyst text-derived ticker coverage: 12/13.
News/catalyst missing numeric tickers: 0.
News/catalyst provider-native upgrade needed: 12.
News/catalyst coverage-plan tickers: AMD, AMZN, AVGO.
News/catalyst missing queue stale: False.
News/catalyst provider upgrade queue stale: False.
```

Notes:

- Total news/catalyst numeric coverage remains complete at 13/13.
- Provider-native coverage remains 1/13, and 12/13 active equities are now
  clearly surfaced as provider-upgrade candidates rather than missing coverage.
- The provider-upgrade queue is the next quality lane if Marketaux, EODHD, X,
  or manual provider exports become available.
- Phase 10D remains gated because analyst revision evidence is still
  collecting and has no mature 20d validation pass yet.

### 2026-06-08 - Phase 10E.6 provider-native news/catalyst upgrade activation MVP

Completed:

- Added `news-catalyst-provider-upgrade-status` to summarize provider key
  presence, provider availability, provider-native coverage, text-derived-only
  tickers, current provider-upgrade queue tickers, and latest provider failure
  reasons without printing or persisting API key values.
- Added `fetch-news-catalyst-sources --provider-upgrade` as a friendly alias for
  `--coverage-plan --coverage-mode provider-upgrade`.
- Added provider-native manual/export source labels for `marketaux_export`,
  `eodhd_export`, `x_export`, and `licensed_news_provider_export`.
- Added validation that skips provider-native replacement rows when they claim
  an upgrade but lack `source_url`, `headline_or_event`, or at least one numeric
  provider field.
- Kept text-derived snapshots as audit evidence while preserving aggregate
  precedence for provider-native numeric rows.
- Updated `status`, daily Markdown reports, daily CSV reports, and dashboard
  health data with provider-upgrade status.
- Fixed queue hygiene so a provider-upgrade template refresh clears an old
  missing-numeric queue when total numeric coverage is already complete.
- Updated README and `DOCS/news-catalyst-source-workflow.md` with the Phase
  10E.6 commands, export labels, and provider-native validation rules.

Verification:

```text
python -m unittest discover -s tests -p test_phase10e_news_catalysts.py
19 tests passed.

python -m unittest discover -s tests
148 tests passed.
Non-fatal ResourceWarnings appeared, consistent with prior suite behavior.

python -m target_opportunity_monitor init-db
Required tables present: 28/28.

python -m target_opportunity_monitor news-catalyst-provider-upgrade-status
Status: queued.
Provider-native coverage: 1/13.
Text-derived-only tickers: AMD, AMZN, AVGO, COST, CRM, GOOGL, JPM, LLY, META,
MSFT, NVDA, ORCL.
Missing-key providers: marketaux, eodhd, x_recent_search.

python -m target_opportunity_monitor news-catalyst-coverage-plan --mode provider-upgrade --refresh-template
Missing queue stale: False.
Provider upgrade queue stale: False.
Planned tickers under the default budget: AMD, AMZN, AVGO.

python -m target_opportunity_monitor fetch-news-catalyst-sources --provider-upgrade
Fetched queued provider-upgrade tickers: AMD, AMZN, AVGO.
Provider limitations remained warnings, not failures.

python -m target_opportunity_monitor import-news-catalyst-source-exports
No manual/provider exports imported in the live run.

python -m target_opportunity_monitor aggregate-news-catalyst-sources
Aggregate rows: 13.
Final compatibility CSV rows: 13.

python -m target_opportunity_monitor load-news-catalysts
Loaded 13 news/catalyst rows and 50 input signals.

python -m target_opportunity_monitor compute-news-catalyst-signals
Computed 13 equity news/catalyst signals in shadow mode.
Skipped SPY and QQQ as ETF-gated.

python -m target_opportunity_monitor validate-news-catalyst-signals
Updated 13 pending validation rows.

python -m target_opportunity_monitor refresh-data --daily-only
Pipeline run 28: daily_refresh status=ok.

python -m target_opportunity_monitor run-daily
Created reports/2026-06-08-daily-report.md.
Created reports/2026-06-08-daily-report.csv.

python -m target_opportunity_monitor build-dashboard
Dashboard regenerated with 15 rows.

python -m target_opportunity_monitor status
Required tables present: 28/28.
Asset count: 15.
News/catalyst numeric ticker coverage: 13/13.
News/catalyst provider numeric ticker coverage: 1/13.
News/catalyst text-derived ticker coverage: 12/13.
News/catalyst missing numeric tickers: 0.
News/catalyst provider-native upgrade needed: 12.
News/catalyst provider-upgrade status: queued.
News/catalyst missing queue stale: False.
News/catalyst provider upgrade queue stale: False.
Revision evidence decision: collecting_evidence.
```

Notes:

- Phase 10E.6 does not change final scores, alerts, portfolio guidance,
  notifications, broker writes, or execution.
- News/catalyst remains shadow-only.
- Provider-native coverage is still the quality gap: 12/13 active equities rely
  on lower-confidence text-derived numeric rows.
- Phase 10D remains gated until analyst revision validation has mature 20d
  evidence and passes the configured evidence gate.

### 2026-06-08 - Phase 10E.8 provider-native news/catalyst backfill operations MVP

Completed:

- Added `export-news-catalyst-provider-backfill`.
- The command writes a provider-native CSV template and README/runbook under
  `data/signals/source_exports/news_catalysts/provider_native_backfill/`.
- The generated template includes only active equities that are covered by
  lower-confidence text-derived news/catalyst rows but lack provider-native
  numeric rows.
- Added `user_provider_export` as an accepted provider-native export label.
- Strengthened provider-native import validation so filled upgrade rows require
  ticker, date, source, source URL, headline/event, valid 0-100 numeric fields,
  and at least one aggregate numeric provider field.
- Blank queue/backfill placeholders remain harmless and are skipped.
- Invalid provider-native upgrade rows are rejected with warnings rather than
  stored as source snapshots.
- Added provider-native upgraded tickers, still text-derived-only tickers,
  latest accepted provider-native source date, rejected row count, and rejected
  tickers to provider-upgrade status.
- Added provider-native rejection/progress fields to `status`, daily Markdown,
  daily CSV, and dashboard.
- Updated README and `DOCS/news-catalyst-source-workflow.md` with the backfill
  workflow and no-fabrication rules.

Verification:

```text
python -m unittest discover -s tests -p test_phase10e_news_catalysts.py
24 tests passed.

python -m unittest discover -s tests
153 tests passed.
Non-fatal ResourceWarnings appeared, consistent with prior suite behavior.

python -m target_opportunity_monitor init-db
Required tables present: 28/28.

python -m target_opportunity_monitor news-catalyst-provider-upgrade-status
Provider-native coverage: 1/13.
Provider-native upgraded tickers: AAPL.
Still text-derived-only tickers: AMD, AMZN, AVGO, COST, CRM, GOOGL, JPM, LLY,
META, MSFT, NVDA, ORCL.
Rejected provider-native rows: 0.

python -m target_opportunity_monitor export-news-catalyst-provider-backfill
Backfill package exported with 12 tickers.

python -m target_opportunity_monitor import-news-catalyst-source-exports
Imported 0 rows from blank placeholders and warned empty source exports.

python -m target_opportunity_monitor aggregate-news-catalyst-sources
Aggregate rows: 13.
Final compatibility CSV rows: 13.

python -m target_opportunity_monitor load-news-catalysts
Loaded 13 news/catalyst rows and 50 input signals.

python -m target_opportunity_monitor compute-news-catalyst-signals
Computed 13 equity news/catalyst signals in shadow mode.
Skipped SPY and QQQ as ETF-gated.

python -m target_opportunity_monitor validate-news-catalyst-signals
Updated 13 pending validation rows.

python -m target_opportunity_monitor refresh-data --daily-only
Command timed out at the shell after printing, but persisted pipeline run 30
recorded daily_refresh status=ok.

python -m target_opportunity_monitor run-daily
Created reports/2026-06-08-daily-report.md.
Created reports/2026-06-08-daily-report.csv.

python -m target_opportunity_monitor build-dashboard
Dashboard regenerated with 15 rows.

python -m target_opportunity_monitor status
Latest pipeline run: daily_refresh ok 2026-06-08T20:46:51.
News/catalyst numeric ticker coverage: 13/13.
News/catalyst provider numeric ticker coverage: 1/13.
News/catalyst text-derived ticker coverage: 12/13.
News/catalyst rejected provider-native rows: 0.
News/catalyst coverage queue stale: False.
News/catalyst missing queue stale: False.
News/catalyst provider upgrade queue stale: False.
Revision evidence decision: collecting_evidence.
```

Notes:

- Phase 10E.8 does not change final scores, alerts, portfolio guidance,
  notifications, broker writes, or execution.
- News/catalyst remains shadow-only.
- Provider-native coverage remains 1/13 until additional provider-native API
  keys or manual provider exports supply source-backed numeric fields.
- Phase 10D remains gated until analyst revision validation has mature 20d
  evidence and passes the configured evidence gate.

### 2026-06-08 - Phase 10E.7 provider-native news/catalyst upgrade operations MVP

Completed:

- Fixed all-mode news/catalyst queue hygiene so `coverage queue stale` stays
  false when missing numeric coverage is complete and only provider-native
  upgrade work remains.
- Added `test-news-catalyst-provider --provider all|marketaux|eodhd|x_recent_search --ticker TICKER`.
- The smoke test classifies provider readiness as `provider_numeric_available`,
  `headline_only`, `rate_limited`, `plan_limited`, `auth_failed`,
  `missing_key`, or `http_failed`.
- Smoke tests suppress failure snapshot writes and never print or persist API
  key values. Successful source-backed provider rows can still be stored and
  aggregated normally.
- Added numeric-row accounting to news/catalyst provider fetch results.
- Improved `fetch-news-catalyst-sources --provider-upgrade` output with queue
  mode, planned tickers, attempted providers, numeric rows stored, and provider
  blockers.
- Added provider-upgrade blockers to `status`, daily Markdown reports, daily CSV
  reports, and dashboard health data.
- Updated README and `DOCS/news-catalyst-source-workflow.md` with smoke-test
  commands, key names, queue hygiene, and blocker behavior.

Verification:

```text
python -m unittest discover -s tests -p test_phase10e_news_catalysts.py
22 tests passed.

python -m unittest discover -s tests
151 tests passed.
Non-fatal ResourceWarnings appeared, consistent with prior suite behavior.

python -m target_opportunity_monitor init-db
Required tables present: 28/28.

python -m target_opportunity_monitor news-catalyst-coverage-plan --mode all
Coverage queue stale: False.
Missing queue stale: False.
Provider upgrade queue stale: False.
Planned tickers: AMD, AMZN, AVGO.

python -m target_opportunity_monitor news-catalyst-coverage-plan --mode provider-upgrade
Coverage queue stale: False.
Missing queue stale: False.
Provider upgrade queue stale: False.
Planned tickers: AMD, AMZN, AVGO.

python -m target_opportunity_monitor test-news-catalyst-provider --provider all --ticker AAPL
marketaux: missing_key.
eodhd: missing_key.
x_recent_search: missing_key.
No API key values were printed.

python -m target_opportunity_monitor fetch-news-catalyst-sources --provider-upgrade
Provider-upgrade queue mode: provider-upgrade.
Provider-upgrade planned tickers: AMD, AMZN, AVGO.
Provider-upgrade numeric rows stored: 0.
Provider blockers: alpha_vantage:rate_limited, marketaux:missing_key,
eodhd:missing_key, finnhub:headline_only, fmp:plan_limited,
x_recent_search:missing_key, truth_social_public:plan_limited.

python -m target_opportunity_monitor aggregate-news-catalyst-sources
Aggregate rows: 13.
Final compatibility CSV rows: 13.

python -m target_opportunity_monitor load-news-catalysts
Loaded 13 news/catalyst rows and 50 input signals.

python -m target_opportunity_monitor compute-news-catalyst-signals
Computed 13 equity news/catalyst signals in shadow mode.
Skipped SPY and QQQ as ETF-gated.

python -m target_opportunity_monitor validate-news-catalyst-signals
Updated 13 pending validation rows.

python -m target_opportunity_monitor refresh-data --daily-only
Pipeline run 29: daily_refresh status=ok.

python -m target_opportunity_monitor run-daily
Created reports/2026-06-08-daily-report.md.
Created reports/2026-06-08-daily-report.csv.

python -m target_opportunity_monitor build-dashboard
Dashboard regenerated with 15 rows.

python -m target_opportunity_monitor status
Required tables present: 28/28.
Asset count: 15.
News/catalyst numeric ticker coverage: 13/13.
News/catalyst provider numeric ticker coverage: 1/13.
News/catalyst text-derived ticker coverage: 12/13.
News/catalyst missing numeric tickers: 0.
News/catalyst provider-native upgrade needed: 12.
News/catalyst provider-upgrade status: queued.
News/catalyst coverage queue stale: False.
News/catalyst missing queue stale: False.
News/catalyst provider upgrade queue stale: False.
Revision evidence decision: collecting_evidence.
```

Notes:

- Phase 10E.7 does not change final scores, alerts, portfolio guidance,
  notifications, broker writes, or execution.
- News/catalyst remains shadow-only.
- Provider-native coverage remains 1/13 until additional provider-native keys or
  manual provider exports supply source-backed numeric fields.
- Phase 10D remains gated until analyst revision validation has mature 20d
  evidence and passes the configured evidence gate.

## Phase 13A - Expanded Universe Fundamental Benchmark Analytics

Implemented on 2026-06-13.

Summary:

- Added `configs/universe_candidates.csv` as a guarded intake surface for new
  scoreable equities and benchmark/reference assets.
- Added `configs/sector_benchmarks.csv` with overall benchmark mappings for
  `SPY`/`QQQ` and sector ETF mappings for `XLK`, `XLC`, `XLY`, `XLP`, `XLF`,
  `XLV`, `XLI`, `XLE`, `XLU`, `XLB`, and `XLRE`.
- Added `fundamental_benchmark_snapshots` and
  `fundamental_comparison_snapshots`.
- Added candidate and benchmark commands:
  `export-universe-candidate-template`, `universe-expansion-plan`,
  `apply-universe-candidates`, `compute-fundamental-benchmarks`,
  `fundamental-benchmark-status`, and `fundamental-benchmark-report`.
- Integrated benchmark computation into daily refresh after targets/scores and
  before report/dashboard output.
- Extended `status`, daily Markdown, daily CSV, and dashboard ticker details
  with sector peer count, benchmark ETF status, sector-relative valuation,
  local percentile, and relative strength versus `SPY`, `QQQ`, and the mapped
  sector ETF.
- Added `tests/test_phase13a_fundamental_benchmarks.py` and an `analytics`
  suite to `tools/run_tests.py`.

Verification:

```text
python -m py_compile src/target_opportunity_monitor/config.py src/target_opportunity_monitor/db.py src/target_opportunity_monitor/storage.py src/target_opportunity_monitor/fundamental_benchmarks.py src/target_opportunity_monitor/pipeline.py src/target_opportunity_monitor/cli.py src/target_opportunity_monitor/reporting.py src/target_opportunity_monitor/dashboard.py
passed.

python tests/test_phase13a_fundamental_benchmarks.py
5 tests passed.

python -m target_opportunity_monitor init-db
Required tables present: 51/51.

python -m target_opportunity_monitor compute-fundamental-benchmarks
Created 15 benchmark snapshots and 13 comparison snapshots.

python -m target_opportunity_monitor apply-universe-candidates --confirm --allow-partial
Applied 9 sector benchmark ETF candidates as regime_proxy assets.

python -m target_opportunity_monitor update-prices --ticker XLK/XLC/XLY/XLP/XLI/XLE/XLU/XLB/XLRE
Loaded 550 rows and price features for each sector benchmark ETF.

python -m target_opportunity_monitor compute-regime-signals
Computed 13 benchmark/sector regime signals.

python -m target_opportunity_monitor fundamental-benchmark-status
Compared scoreable equities: 13/13.
Missing benchmark assets: none.
Missing benchmark prices: none.
```

Notes:

- Phase 13A is analytical and read-only.
- Sector averages are local TOM medians only; no external sector-average values
  are fabricated.
- Sector ETFs are benchmark/regime proxies, not company fundamental peers.
- Sector benchmark ETF proxies are active and priced in the live workspace.
- Future missing benchmark ETF assets or price history are warnings, not
  failures.

## Phase 11D.3 - Manual TOM Ops Runner And Codex Automation Pause

Implemented on 2026-06-13.

Summary:

- Added `manual-ops-loop` as the never-ending TOM-native command to replace the
  TOM-specific Codex operational automations.
- Kept `manual-ops-cycle` as a one-shot iteration command.
- Added `manual-ops-status` to show the recommended manual command, latest
  manual run, TOM automation states, TOM automation IDs to pause, and
  browser/content automation IDs to leave untouched.
- Added `manual_ops_cycle` pipeline audit runs using existing
  `pipeline_runs` and `pipeline_step_results`.
- Added `auto`, `morning`, `intraday`, `daily-refresh`, `daily-retry`, and
  `all` modes.
- Added dry-run behavior that reports planned steps without writing audit rows.
- Added `--max-iterations` for bounded loop verification and a default
  600-second loop interval.
- Routed after-hours loop `auto` mode through the guarded retry path to avoid
  repeating full daily refreshes every interval when data is already current.
- Kept browser/content-capture automations out of the pause recommendation:
  `daily-aleabitoreddit-q-a-ingestion` and `trump-truth-social-posts-morning`.

Verification:

```text
python -m py_compile src/target_opportunity_monitor/manual_ops.py src/target_opportunity_monitor/cli.py
passed.

python tests/test_phase11d3_manual_ops.py
10 tests passed.

python -m target_opportunity_monitor manual-ops-loop --mode auto --deliver --channel file --max-iterations 1
completed one bounded loop iteration.
```

Pause boundary after verification:

```text
Pause:
tom-intraday-probe
tom-morning-check
tom-daily-refresh
tom-daily-retry

Do not pause:
daily-aleabitoreddit-q-a-ingestion
trump-truth-social-posts-morning
```

Notes:

- Phase 11D.3 is read-only.
- It does not place orders, write to brokers, change scores, change alerts,
  change ranges, mutate portfolio guidance, or touch browser-capture workflows.

## Phase 13B - Scoreable Research Ticker Intake And Benchmark Comparison

Implemented on 2026-06-13.

Summary:

- Added one-ticker scoreable research intake commands:
  `research-ticker-plan`, `apply-research-ticker`,
  `refresh-research-ticker`, and `research-ticker-status`.
- Added SEC company ticker metadata resolution with local cache for CIK, name,
  and exchange.
- Added optional FMP profile metadata resolution for sector, industry, exchange,
  currency, and country, with API keys read from environment only.
- Added explicit override support for CIK, sector, industry, name, exchange,
  currency, and country.
- Confirmed apply writes through existing watchlist, assets, CIK map, and
  asset-change audit paths.
- Added ticker-scoped benchmark report output through
  `fundamental-benchmark-report --ticker TICKER`.
- Added focused tests for metadata resolution, non-mutating plan behavior,
  confirmed apply, missing metadata blocking, ticker refresh wrapper, and
  one-ticker benchmark reporting.

Verification:

```text
python tests/test_phase13a_fundamental_benchmarks.py
8 tests passed.

python tools/run_tests.py smoke
6 files passed in 21.01s.

python tools/run_tests.py analytics --timeout-per-file 180
1 file passed in 11.13s.

python tools/run_tests.py full --timeout-per-file 180
34 files passed in 320.99s.
```

Notes:

- Phase 13B is analytical and read-only.
- New scoreable tickers still require price, SEC fundamentals, estimates,
  targets, scores, and benchmark comparisons before they are fully ready.
- Sector averages remain TOM-local medians only; no external averages or missing
  values are fabricated.
- This phase does not place orders, write to brokers, change final scores,
  change alerts, change ranges, mutate portfolio guidance, or execute trades.

## Phase 13C - Research Ticker Recommendation Queue

Implemented on 2026-06-13.

Summary:

- Added recommendation queue tables:
  `research_recommendation_candidates`,
  `research_recommendation_evidence`, and
  `research_recommendation_decisions`.
- Added the manual recommendation CSV at
  `data/research/manual/research_recommendations.csv`.
- Added TOM-internal candidate generation from unsupported commentary tickers
  and reference instruments.
- Added social-local candidate generation from existing X/browser capture,
  Discord capture, and social/news-catalyst rows already stored locally.
- Added optional import from the sibling `research-signals` SQLite suggestion
  queue at `../research/research-signals/data/x_posts.sqlite`.
- Added audited manual/Codex CSV import with strict ticker/rationale/status
  validation.
- Added research-only priority ranking and warning codes such as
  `already_scoreable`, `reference_only_candidate`, `missing_cik_metadata`,
  `social_text_only`, `external_suggestion_pending_approval`, and
  `insufficient_evidence`.
- Added CLI commands:
  `generate-research-recommendations`,
  `export-research-recommendation-template`,
  `import-research-recommendations`,
  `research-recommendation-status`,
  `research-recommendation-report`,
  `set-research-recommendation-status`, and
  `promote-research-recommendation`.
- Added compact recommendation queue visibility to `status`, daily Markdown,
  and dashboard health output.

Verification:

```text
python tests/test_phase13c_research_recommendations.py
7 tests passed.

python tools/run_tests.py smoke
6 files passed in 21.80s.

python tools/run_tests.py analytics --timeout-per-file 180
2 files passed in 15.83s.

python tools/run_tests.py full --timeout-per-file 180
35 files passed in 327.34s.

Post external-DB fallback fix:

python tools/run_tests.py analytics --timeout-per-file 180
2 files passed in 13.65s.

python -m target_opportunity_monitor status
Required tables present: 54/54; research recommendation candidates: 325.
```

Notes:

- Recommendation output is research intake only, not buy/sell advice.
- Promotion is explicit and approval-gated through Phase 13B.
- Social inputs are read from existing local captures/imports only.
- No scraping, broker writes, order placement, execution, score changes, alert
  changes, range changes, or portfolio mutation are included.

## Phase 14A - Local TOM API Server MVP

Implemented on 2026-06-13.

Summary:

- Added API config defaults:
  `api.host`, `api.port`, `api.allowed_origins`, and
  `api.require_mutation_confirmation`.
- Added a stdlib-only local HTTP/JSON server in `api_server.py` using
  `ThreadingHTTPServer`.
- Added CLI commands:
  `api-status` and `serve-api`.
- Added `serve-api --once-smoke-test` so API health/status can be verified
  without leaving a long-running server process alive.
- Added local CORS handling for the planned Vite dev origins:
  `http://127.0.0.1:5173` and `http://localhost:5173`.
- Added initial endpoints:
  `GET /api/health`,
  `GET /api/status`,
  `GET /api/dashboard-data`,
  `GET /api/assets`,
  `GET /api/research/recommendations`,
  `POST /api/research/recommendations/{id}/status`,
  `POST /api/research/recommendations/{id}/promote`,
  `POST /api/research/ticker-plan`,
  `POST /api/research/apply-ticker`,
  `POST /api/ops/intraday-cycle`,
  `POST /api/notifications/drain`,
  `GET /api/options/status`, and
  `GET /api/provider/status`.
- Mutating API routes require JSON `{"confirm": true}` or
  `X-TOM-Confirm: true`.
- API errors return structured JSON with `ok`, `error_code`, `message`, and
  optional warnings.
- Exposed dashboard payload generation through `build_dashboard_data` while
  preserving the existing static dashboard artifact.
- Added `tests/test_phase14a_api_server.py` and included it in the smoke suite.

Verification:

```text
python tests/test_phase14a_api_server.py
10 tests passed.

python -m py_compile src/target_opportunity_monitor/api_server.py src/target_opportunity_monitor/cli.py src/target_opportunity_monitor/config.py src/target_opportunity_monitor/dashboard.py
passed.

python -m target_opportunity_monitor api-status
listed 13 local API endpoints.

python -m target_opportunity_monitor serve-api --once-smoke-test
health endpoint: 200 ok=True; status endpoint: 200 ok=True.

python tools/run_tests.py smoke --timeout-per-file 180
7 files passed in 27.33s.
```

Notes:

- Phase 14A is local control-plane plumbing for the future
  `F:\Investments\tom-ui` repo.
- No broker writes, order placement, execution, score-rule changes,
  alert-rule changes, range-rule changes, or portfolio mutation were added.

## Phase 14B - TOM JS Control Center Scaffold MVP

Implemented on 2026-06-13.

Summary:

- Created the separate UI repo at `F:\Investments\tom-ui`.
- Added a Vite/React/TypeScript local control-center shell.
- Added `.env.local` with
  `VITE_TOM_API_BASE_URL=http://127.0.0.1:8765`.
- Added typed API wrappers for the Phase 14A TOM API endpoints.
- Built read-only routes:
  `/`,
  `/assets`,
  `/research`,
  `/options`, and
  `/dashboard-data`.
- Kept mutation helpers in the API client but did not expose active mutation UI
  actions in Phase 14B.
- Documented the UI launch flow in `F:\Investments\tom-ui\README.md` and in
  the backend README.

Verification:

```text
python -m target_opportunity_monitor serve-api --once-smoke-test
health endpoint: 200 ok=True; status endpoint: 200 ok=True.

npm install --cache F:\Investments\tom-ui\.npm-cache
completed.

npm run build
TypeScript and Vite production build passed.

Browser verification against http://127.0.0.1:5173
Overview, Assets, Research, Options, and Dashboard Data routes rendered from
the TOM API. The Dashboard Data route loaded after the larger
/api/dashboard-data payload returned.

API-offline verification
Assets route rendered a clear local-backend-offline state when TOM API was
temporarily stopped.

python tools/run_tests.py smoke --timeout-per-file 180
7 files passed in 28.32s.
```

Notes:

- TOM API and the Vite dev server were started locally for verification.
- The `/api/dashboard-data` payload is currently large, about 1.5 MB in the
  verified local state, so a later UI/API performance pass should consider a
  summarized dashboard endpoint.
- `npm install` reported npm audit warnings from frontend dependencies; no
  dependency upgrade was applied during this scaffold phase.
- No backend business logic, broker writes, order placement, execution,
  score-rule changes, alert-rule changes, range-rule changes, or portfolio
  mutation were added.

## Phase 14C - Research Recommendation And Ticker Intake UI MVP

Implemented on 2026-06-13.

Summary:

- Extended the local TOM API with:
  `POST /api/research/refresh-ticker`,
  `GET /api/research/ticker-status`, and
  `GET /api/research/fundamental-benchmark-report`.
- Kept apply, promote, status-change, refresh, intraday, and notification API
  mutations confirmation-gated.
- Upgraded `F:\Investments\tom-ui` `/research` into two workflows:
  `Recommendation Queue` and `Ticker Intake`.
- Added queue filtering/search, detail review, approve/ignore/reject actions,
  promotion preparation, ticker planning, confirmed apply, confirmed refresh,
  ticker status, and benchmark-report display.
- Added a local confirmation dialog so the UI sends `confirm: true` only after
  explicit user confirmation.
- Added `tests/test_phase14c_research_api.py` and included it in the smoke
  suite.

Verification:

```text
python -m py_compile src/target_opportunity_monitor/api_server.py
passed.

python tests/test_phase14a_api_server.py
10 tests passed.

python tests/test_phase14c_research_api.py
5 tests passed.

python tools/run_tests.py smoke --timeout-per-file 180
8 files passed in 27.00s.

python tools/run_tests.py analytics --timeout-per-file 180
2 files passed in 14.68s.

python -m target_opportunity_monitor serve-api --once-smoke-test
health endpoint: 200 ok=True; status endpoint: 200 ok=True.

npm run build
TypeScript and Vite production build passed.

Browser verification against http://127.0.0.1:5173/research
Recommendation Queue rendered candidates, detail review showed blockers, ticker
planning worked, Ticker Intake loaded TSLA plan/status/benchmark report, and
Apply/Promote opened confirmation dialogs before confirmed mutations.
```

Notes:

- Phase 14C is research intake UI only, not trading advice.
- No bulk research actions, broker writes, order placement, execution,
  score-rule changes, alert-rule changes, range-rule changes, or portfolio
  mutation were added.

## Phase 14D - Asset, Intraday, Scheduler, And Notification Controls UI MVP

Implemented on 2026-06-13.

Summary:

- Extended the local TOM API with structured operational endpoints:
  asset status/add/deactivate/reactivate/soft-remove, intraday status/health,
  manual ops cycle, scheduler status/audit, notification status, notification
  delivery report, and notification outbox status.
- Kept asset, ops, and notification mutation routes behind the existing
  `confirm: true` / `X-TOM-Confirm` API confirmation requirement.
- Upgraded `F:\Investments\tom-ui` `/assets` with asset detail, read-only
  status, add/update form, deactivate/reactivate, and soft-remove controls.
- Added `/ops` for intraday health, quote/range freshness, one-shot intraday
  cycle, one-shot manual ops cycle, and the operator-visible
  `manual-ops-loop` command.
- Added `/scheduler` for scheduler reconciliation, heartbeat command state,
  audit text, repair-plan text, and automation status without mutating Codex
  automations.
- Added `/notifications` for pending/delivered/failed events, delivery report,
  outbox status, and confirmation-gated file delivery drain.
- Added `tests/test_phase14d_ops_api.py` and included it in the smoke suite.

Verification:

```text
python -m py_compile src/target_opportunity_monitor/api_server.py
passed.

python tests/test_phase14d_ops_api.py
7 tests passed.

python tests/test_phase14a_api_server.py
10 tests passed.

python tools/run_tests.py smoke --timeout-per-file 180
9 files passed in 33.67s.

python -m target_opportunity_monitor serve-api --once-smoke-test
health endpoint: 200 ok=True; status endpoint: 200 ok=True.

python -m target_opportunity_monitor api-status
listed the Phase 14D API endpoints.

npm run build
TypeScript and Vite production build passed.

HTTP route verification against the running local Vite dev server
`/assets`, `/ops`, `/scheduler`, and `/notifications` returned 200 and rendered
the React app root.
```

Notes:

- The UI may trigger one-shot TOM cycles, but it does not start the persistent
  `manual-ops-loop`.
- Scheduler automation creation, pause, or repair remains outside the Phase 14D
  UI; the UI reports state and recommended commands only.
- No broker writes, order placement, execution, score-rule changes, alert-rule
  changes, range-rule changes, or portfolio mutation were added.

## Phase 14E - CSV, Backfill, Account, And Options Activation UI MVP

Implemented on 2026-06-13.

Summary:

- Extended the local TOM API with account-context activation endpoints for
  status, template export, validation, preview, apply, export normalization, and
  source-export row staging.
- Added backfill API endpoints for option-chain coverage, news/catalyst
  provider-native upgrades, and short-interest missing-row workflows.
- Kept export, normalize, row-builder append, and apply endpoints behind the
  existing `confirm: true` / `X-TOM-Confirm` confirmation requirement.
- Upgraded `F:\Investments\tom-ui` with `/activation` for account-context
  blockers, portfolio/cash/option-position row builders, validate/preview, and
  dry-run or confirmed apply controls.
- Added `/backfills` panels for option-chain, news/catalyst, and short-interest
  workflows with export, validate, blocker display, and confirmation-gated
  apply controls.
- Added `tests/test_phase14e_activation_api.py` and included it in the smoke
  suite.

Verification:

```text
python -m py_compile src/target_opportunity_monitor/api_server.py
passed.

python tests/test_phase14e_activation_api.py
6 tests passed.

python tests/test_phase14a_api_server.py
10 tests passed.

python tests/test_phase14d_ops_api.py
7 tests passed.

python -m target_opportunity_monitor serve-api --once-smoke-test
health endpoint: 200 ok=True; status endpoint: 200 ok=True.

python tools/run_tests.py smoke --timeout-per-file 180
10 files passed in 35.76s.

npm run build
TypeScript and Vite production build passed.
```

Notes:

- Row-builder submissions append only to TOM-controlled source-export/template
  paths and still require TOM validation/preview/apply before they affect the
  backend state.
- Phase 14E does not add arbitrary file upload, broker writes, order placement,
  execution, score-rule changes, alert-rule changes, range-rule changes, or
  portfolio mutation outside existing TOM workflows.

## Phase 15A - Read-Only Account Context Sync And Portfolio Activation MVP

Implemented on 2026-06-13.

Summary:

- Added read-only account provider status for TOM source-export files, valid
  staged account rows, IBKR API import/connectivity state, and account-context
  blockers.
- Added `fetch-account-context --source ibkr|file --read-only`, with the file
  path normalizing source-backed account exports and the IBKR path using
  read-only account-summary/position requests only.
- Extended account export normalization to accept `generic`, `ibkr`,
  `ibkr-flex`, and `ibkr-activity` provider labels.
- Added local API endpoints:
  `GET /api/account/provider-status` and `POST /api/account/fetch-context`.
- Extended the `F:\Investments\tom-ui` `/activation` page with provider status,
  normalize-export controls, and read-only fetch controls.
- Added `tests/test_phase15a_account_sync.py` and included it in the smoke
  suite.

Verification:

```text
python -m py_compile src/target_opportunity_monitor/account.py src/target_opportunity_monitor/cli.py src/target_opportunity_monitor/api_server.py
passed.

python tests/test_phase15a_account_sync.py
6 tests passed.

python tests/test_phase14e_activation_api.py
6 tests passed.

python -m target_opportunity_monitor account-provider-status --no-connectivity-check
reported source-export readiness and no valid account-context rows.

python -m target_opportunity_monitor fetch-account-context --source ibkr --read-only
completed warning-only with zero rows because local TWS/Gateway was not connected.

python -m target_opportunity_monitor serve-api --once-smoke-test
health endpoint: 200 ok=True; status endpoint: 200 ok=True.

python tools/run_tests.py smoke --timeout-per-file 180
11 files passed in 40.61s.

npm run build
TypeScript and Vite production build passed.
```

Notes:

- The IBKR account path only requests read-only account summary and positions.
  It does not call order, exercise, assignment, or broker-write APIs.
- Account context remains blocked until real source-backed holdings, cash, or
  option-position rows are supplied or fetched and then applied through the
  existing confirmation-gated workflow.

## Cross-Phase - Signal Coverage UI And Phase Readiness Matrix

Implemented on 2026-06-14.

Summary:

- Added a read-only signal coverage assembler for analyst revisions,
  news/catalyst, insider activity, short interest, trader commentary,
  technical/regime, and ranges.
- Added local API endpoints `GET /api/signals/status` and
  `GET /api/coverage/status`.
- Added `F:\Investments\tom-ui` routes `/signals` and `/coverage`, with dense
  lane/group tables, readiness badges, blockers, warnings, notes, counts, and
  existing CLI/status report text where useful.
- Added `tests/test_phase14f_signal_coverage_api.py`.
- Preserved all source-data/provider/user-review/evidence blockers. No source
  rows, provider rows, option positions, research approvals, score gates,
  broker writes, or order/execution paths were added.

Verification:

```text
python -m py_compile src\target_opportunity_monitor\signal_coverage.py src\target_opportunity_monitor\api_server.py src\target_opportunity_monitor\cli.py
passed.

python tests\test_phase14f_signal_coverage_api.py
4 tests passed.

python tests\test_phase14d_ops_api.py
8 tests passed.

python tests\test_phase8a_dashboard.py
4 tests passed.

python tools\run_tests.py smoke --timeout-per-file 180
14 files passed in 53.10s.

python -m target_opportunity_monitor status
passed; required tables 56/56, intraday health healthy, market session weekend,
TOM loop running/healthy, pending notifications 0, failed deliveries 0.

GET /api/signals/status through handle_api_request
200 ok=True; aggregate status provider_key_or_export_required; lanes:
analyst_revisions evidence_gated 13/13, news_catalyst
provider_key_or_export_required 5/13, insider_activity ready 13/13,
short_interest provider_key_or_export_required 9/13, trader_commentary ready
7/7, technical_regime source_data_required 13/17, ranges ready 33/33.

GET /api/coverage/status through handle_api_request
200 ok=True; aggregate status provider_key_or_export_required; groups:
operational_freshness ready, account_options_context
provider_key_or_export_required, signal_evidence_lanes
provider_key_or_export_required, research_queue user_review_required,
api_ui_runtime ready.

python -m target_opportunity_monitor serve-api --once-smoke-test
health endpoint: 200 ok=True; status endpoint: 200 ok=True.

npm run build
TypeScript and Vite production build passed.
```

Notes:

- `/signals` and `/coverage` are display-only routes.
- The signal API intentionally exposes expected blockers instead of resolving
  them: BIL option-chain coverage, option-position/lifecycle rows,
  short-interest missing tickers, news/catalyst provider-native upgrades,
  research review, and analyst-revision evidence maturity remain separate
  open gaps.

## Cross-Phase - Options Readiness Source Gates And Non-Actionable Chain Decisions

Implemented on 2026-06-14.

Summary:

- Added a source-backed non-actionable option-chain decision workflow for
  tickers that should be excluded from effective option-chain coverage only
  after an explicit source-backed decision.
- Added `data/options/source_exports/options_chain_non_actionable.csv` with a
  blank BIL placeholder. Blank or invalid rows do not change readiness.
- Extended option-chain coverage planning with raw/effective coverage counts,
  valid/invalid non-actionable decision counts, non-actionable tickers, notes,
  and invalid-decision warnings.
- Updated existing CLI/status/report/dashboard/API/UI surfaces. No new endpoint
  was added; `/api/backfills/options/status` and `/api/coverage/status` expose
  the new fields.
- Preserved all source-data gates: no option quotes, option positions,
  lifecycle rows, broker writes, orders, short-interest rows, news/catalyst rows,
  analyst evidence, or research approvals were fabricated.

Verification:

```text
python -m py_compile src\target_opportunity_monitor\options.py src\target_opportunity_monitor\api_server.py src\target_opportunity_monitor\cli.py src\target_opportunity_monitor\account.py src\target_opportunity_monitor\signal_coverage.py src\target_opportunity_monitor\reporting.py src\target_opportunity_monitor\dashboard.py
passed.

python tests\test_phase12b_options_chain.py
27 tests passed.

python tests\test_phase12f_options_lifecycle.py
5 tests passed.

python tests\test_phase12f1_account_context.py
8 tests passed.

python tests\test_phase14e_activation_api.py
6 tests passed.

python tests\test_phase14f_signal_coverage_api.py
5 tests passed.

python tests\test_phase8a_dashboard.py
4 tests passed.

python tools\run_tests.py smoke --timeout-per-file 180
14 files passed in 52.23s.

python -m target_opportunity_monitor option-chain-coverage-plan
reported coverage status missing_coverage, current/effective/raw coverage
18/19, missing ticker BIL, non-actionable valid decisions 0, invalid decisions
0, blank placeholders 1, notes none, blocked reason
projected_option_chain_coverage_does_not_improve, provider blocked reason
missing_option_chain.

python -m target_opportunity_monitor status
passed; required tables 56/56, intraday health healthy/weekend, TOM loop
running/healthy, option position ledger rows 0, option lifecycle review rows 0,
options missing chain tickers BIL, non-actionable chain tickers none, broader
coverage 18/19, raw coverage 18/19.

python -m target_opportunity_monitor serve-api --once-smoke-test
health endpoint: 200 ok=True; status endpoint: 200 ok=True.

npm run build
TypeScript and Vite production build passed.

Browser verification
`/backfills` rendered Option Chains with Coverage 18/19, Raw 18/19,
Non-actionable none, and blocker projected_option_chain_coverage_does_not_improve.
`/coverage` rendered Account/Options Context with option positions 0, lifecycle
rows 0, option-chain coverage count 18/19, raw coverage 18/19, and
non-actionable tickers none.
```

Notes:

- Filling `options_chain_non_actionable.csv` with a valid source-backed BIL
  decision can make effective chain coverage complete without importing option
  quotes.
- That decision still does not create option-position or lifecycle rows; those
  remain blocked until real source-backed option-position rows exist.

## Cross-Phase - Short-Interest Source Coverage Closure

Implemented on 2026-06-14.

Summary:

- Staged source-backed `provider_export` rows for `CRM`, `JPM`, `LLY`, and
  `ORCL` in
  `data/signals/source_exports/short_interest/missing_provider_short_interest_backfill.csv`.
- The rows use public MarketBeat short-interest pages as source URLs, settlement
  date `2026-05-29`, capture/as-of date `2026-06-14`, and reported short
  interest, percent float, and days-to-cover values.
- Ran dry-run apply first, then confirmed apply through the existing guarded
  short-interest provider backfill flow. No broker state, orders, provider keys,
  option-position rows, news/catalyst rows, research decisions, or evidence gates
  were changed.
- Reloaded short-interest rows, recomputed short-interest shadow signals, and
  validated them. Source-backed short-interest coverage is now `13/13` and
  missing source tickers are `none`.

Verification:

```text
python -m target_opportunity_monitor resolve-short-interest-missing-sources --provider all
ran 8 live requests, normalized 0 provider rows, and left the gap blocked by
no_valid_missing_short_interest_rows, so manual source-backed rows were used.

python -m target_opportunity_monitor validate-short-interest-backfill
passed; valid rows 220, invalid rows 0, projected source-backed coverage 13/13,
apply ready True.

python -m target_opportunity_monitor preview-short-interest-import
passed; projected source-backed coverage 13/13, valid import tickers AAPL, AMD,
AMZN, AVGO, COST, CRM, GOOGL, JPM, LLY, META, MSFT, NVDA, ORCL, still missing
after import none.

python -m target_opportunity_monitor apply-short-interest-provider-backfill
dry run only; projected coverage improvement 4, imported rows 0, written rows
0, apply ready True.

python -m target_opportunity_monitor apply-short-interest-provider-backfill --confirm
confirmed apply; projected coverage improvement 4, imported rows 220, written
rows 268, blocked apply reason none.

python -m target_opportunity_monitor load-short-interest
loaded 220 source-backed rows from 268 CSV rows; tickers AAPL, AMD, AMZN, AVGO,
COST, CRM, GOOGL, JPM, LLY, META, MSFT, NVDA, ORCL.

python -m target_opportunity_monitor compute-short-interest-signals
computed 13 equity signals, skipped 4 ETF-gated tickers, loaded sources 220.

python -m target_opportunity_monitor validate-short-interest-signals
updated 22 validations, skipped 4 ETF-gated validations, warnings only for ETF
validation gates.

python -m target_opportunity_monitor short-interest-missing-coverage-plan
reported current and projected source-backed coverage 13/13, missing source
tickers none, diagnostics none.

python -m target_opportunity_monitor short-interest-status
reported source-backed coverage 13/13, source rows 220, latest settlement date
2026-05-29, missing source tickers none.

GET /api/signals/status through handle_api_request
aggregate status provider_key_or_export_required because news/catalyst remains
provider-gated; short_interest lane ready 13/13.

GET /api/coverage/status through handle_api_request
aggregate status provider_key_or_export_required; groups remain
operational_freshness ready, account_options_context source_data_required,
signal_evidence_lanes provider_key_or_export_required, research_queue
user_review_required, api_ui_runtime ready.

python tests\test_phase10g_short_interest.py
12 tests passed.

python tests\test_phase14e_activation_api.py
12 tests passed.

python tests\test_phase14f_signal_coverage_api.py
5 tests passed.

python tools\run_tests.py smoke --timeout-per-file 180
14 files passed in 54.36s.

python -m target_opportunity_monitor status
passed; required tables 56/56, intraday health healthy, TOM loop
running/healthy, pending notifications 0, failed deliveries 0, short-interest
source-backed tickers 13/13, short-interest missing coverage tickers none.

python -m target_opportunity_monitor serve-api --once-smoke-test
health endpoint: 200 ok=True; status endpoint: 200 ok=True.

npm run build
TypeScript and Vite production build passed.
```

Notes:

- Short-interest remains shadow-mode signal evidence and does not directly place
  orders or write to brokers.
- News/catalyst provider-native rows, option-position source rows, research
  recommendation review, trader-commentary capture/aliases, technical ETF rows,
  and Phase 10D analyst-revision evidence gates remain open.

## Cross-Phase - News/Catalyst Provider-Native Coverage Closure

Implemented on 2026-06-14.

Summary:

- Closed the Phase 10E provider-native news/catalyst coverage gap using the
  existing provider-upgrade fetch workflow. No manual provider-native rows,
  synthetic headlines, fabricated scores, provider keys, broker writes, orders,
  research approvals, or evidence-gate changes were introduced.
- Ran three scoped provider-upgrade fetch passes. The first upgraded `CRM`,
  `GOOGL`, and `JPM`; the second upgraded `LLY`, `META`, and `MSFT`; the third
  upgraded `NVDA` and `ORCL`.
- Provider-native coverage moved from `5/13` to `13/13`. Upgrade tickers are
  now `none`; rejected provider-native rows are `0`.
- Refreshed the provider-native backfill package and coverage queue templates so
  stale queue flags are `False` and blank provider-native placeholders are `0`.
- Re-aggregated news/catalyst sources, reloaded the derived news/catalysts CSV,
  recomputed news/catalyst shadow signals, and updated validations.

Verification:

```text
python -m target_opportunity_monitor fetch-news-catalyst-sources --provider all --provider-upgrade --use-cache
first pass stored 15 provider numeric rows and moved provider-native coverage
from 5/13 to 8/13.

python -m target_opportunity_monitor fetch-news-catalyst-sources --provider all --provider-upgrade --use-cache
second pass stored 15 provider numeric rows and moved provider-native coverage
from 8/13 to 11/13.

python -m target_opportunity_monitor fetch-news-catalyst-sources --provider all --provider-upgrade --use-cache
third pass stored 10 provider numeric rows and completed provider-native
coverage at 13/13.

python -m target_opportunity_monitor news-catalyst-provider-upgrade-status
reported status provider_native_complete, provider-native coverage 13/13,
still text-derived-only tickers none, latest accepted provider-native source
date 2026-06-14, rejected provider-native rows 0.

python -m target_opportunity_monitor news-catalyst-source-status --provider-upgrade-only
reported provider numeric ticker coverage 13/13, provider-native upgrade
needed 0/13, provider-native upgrade tickers none, source warnings none.

python -m target_opportunity_monitor export-news-catalyst-provider-backfill
exported provider-native backfill package with tickers=0 and warning
no_provider_native_backfill_needed.

python -m target_opportunity_monitor news-catalyst-coverage-plan --mode provider-upgrade --refresh-template
python -m target_opportunity_monitor news-catalyst-coverage-plan --mode missing --refresh-template
refreshed stale queue templates; coverage queue stale False, missing queue stale
False, provider upgrade queue stale False.

python -m target_opportunity_monitor aggregate-news-catalyst-sources
aggregated 40 rows for AAPL, AMD, AMZN, AVGO, COST, CRM, GOOGL, JPM, LLY,
META, MSFT, NVDA, ORCL.

python -m target_opportunity_monitor load-news-catalysts
loaded 40 rows and 122 input signals from data/signals/manual/news_catalysts.csv.

python -m target_opportunity_monitor compute-news-catalyst-signals
computed 13 equity signals, skipped 4 ETF-gated rows, and loaded 122 inputs.

python -m target_opportunity_monitor validate-news-catalyst-signals
updated 35 validations and skipped 4 ETF-gated validations.

python -m target_opportunity_monitor status
passed; required tables 56/56, intraday health healthy, TOM loop
running/healthy, pending notifications 0, failed deliveries 0, news/catalyst
provider numeric ticker coverage 13/13, provider-native upgrade needed 0,
provider-native upgrade tickers none, stale news/catalyst queues False.

GET /api/signals/status through handle_api_request
aggregate status source_data_required; news_catalyst lane ready 13/13,
short_interest ready 13/13, insider_activity ready 13/13, trader_commentary
ready 7/7, ranges ready 33/33, analyst_revisions evidence_gated 13/13,
technical_regime source_data_required 13/17.

GET /api/coverage/status through handle_api_request
aggregate status source_data_required; operational_freshness ready,
account_options_context source_data_required, signal_evidence_lanes
source_data_required, research_queue user_review_required, api_ui_runtime ready.

python -m target_opportunity_monitor serve-api --once-smoke-test
health endpoint: 200 ok=True; status endpoint: 200 ok=True.

python tests\test_phase10e_news_catalysts.py
30 tests passed.

python tests\test_phase14e_activation_api.py
12 tests passed.

python tests\test_phase14f_signal_coverage_api.py
5 tests passed.

python tools\run_tests.py smoke --timeout-per-file 180
14 files passed in 66.31s.

npm run build
TypeScript and Vite production build passed.
```

Notes:

- Optional provider-key gaps remain visible as provider warnings for redundancy
  and breadth (`marketaux`, `eodhd`, `x_recent_search` missing; some available
  providers are headline-only or plan-limited), but they no longer block
  provider-native ticker coverage.
- News/catalyst signals remain shadow-mode context and do not place orders or
  write to brokers.
- Option-position source rows, research recommendation review,
  trader-commentary capture/aliases, technical ETF rows, and Phase 10D
  analyst-revision evidence gates remain open.

### 2026-06-14 - Technical/regime coverage and readiness semantics closure

Implemented the technical/regime gap closure using existing local TOM price
history and signal computation paths.

Changes:

- Updated signal coverage readiness semantics so the `technical_regime` lane
  checks two explicit universes:
  - technical snapshots for all active assets surfaced by `technical-status`,
  - configured benchmark/sector regime proxies from the regime config.
- Added structured technical/regime subcoverage fields to `/api/signals/status`
  and `/api/coverage/status`, including technical coverage, regime coverage,
  missing tickers, input-blocked tickers, and required regime tickers.
- Cleaned up news/catalyst coverage semantics so optional provider-key,
  rate-limit, plan-limit, and empty backfill-package conditions remain visible
  as warnings/notes after provider-native numeric coverage is complete, without
  appearing as blockers.
- Extended dashboard data and report health text with technical/regime
  coverage and missing ticker details.
- Added regression coverage for missing technical rows, complete
  technical/regime readiness, missing regime price-history blockers, and
  completed news provider coverage with optional provider limitations.

Live recompute:

```powershell
python -m target_opportunity_monitor compute-technical-signals
```

Computed 33 technical signals with warnings=0, including previously missing
`BIL`, `DBC`, `XLB`, `XLC`, `XLE`, `XLI`, `XLK`, `XLP`, `XLRE`, `XLU`, and
`XLY`.

```powershell
python -m target_opportunity_monitor compute-regime-signals
```

Computed 13 regime signals with warnings=0 for `SPY`, `QQQ`, `XLK`, `XLY`,
`XLV`, `XLF`, `XLI`, `XLP`, `XLU`, `XLE`, `XLC`, `XLB`, and `XLRE`.

Verification:

```powershell
python -m target_opportunity_monitor technical-status
```

Reported `2026-06-14` technical rows for all 33 active assets with no warnings.

```powershell
python -m target_opportunity_monitor regime-status
```

Reported `2026-06-14` regime rows for all 13 configured benchmark/sector
proxies with no warnings.

`GET /api/signals/status` through local payload builder reported:

- `news_catalyst`: `ready 13/13`, blockers `[]`, notes
  `text_derived_rows_remain_lower_confidence` and
  `optional_provider_limitations_not_blocking_coverage`.
- `technical_regime`: `ready 46/46`, technical coverage `33/33`, regime
  coverage `13/13`, no missing technical tickers, no missing regime tickers,
  latest technical date `2026-06-14`, latest regime date `2026-06-14`.

`GET /api/coverage/status` through local payload builder reported aggregate
status `source_data_required`, `signal_evidence_lanes:evidence_gated`, and
signal blockers limited to
`analyst_revisions:revision_evidence:collecting_evidence`.

`python -m target_opportunity_monitor status` passed with required tables
`56/56`, intraday health `healthy`, TOM loop `running/healthy`, pending
notifications `0`, failed notification deliveries `0`, latest technical signal
date `2026-06-14`, latest regime signal date `2026-06-14`, news/catalyst
provider numeric coverage `13/13`, and short-interest source-backed coverage
`13/13`.

Regression/verification commands passed:

```powershell
python -m py_compile src\target_opportunity_monitor\signal_coverage.py src\target_opportunity_monitor\technical.py src\target_opportunity_monitor\cli.py src\target_opportunity_monitor\reporting.py src\target_opportunity_monitor\dashboard.py
python tests\test_phase11b_technical_regime.py
python tests\test_phase14f_signal_coverage_api.py
python tests\test_phase8a_dashboard.py
python tools\run_tests.py smoke --timeout-per-file 180
python -m target_opportunity_monitor serve-api --once-smoke-test
npm run build
```

Results:

- `test_phase11b_technical_regime.py`: 8 tests passed.
- `test_phase14f_signal_coverage_api.py`: 9 tests passed.
- `test_phase8a_dashboard.py`: 4 tests passed.
- Smoke suite: 14 files passed in 60.44s.
- API smoke: health endpoint 200 `ok=True`; status endpoint 200 `ok=True`.
- `tom-ui` TypeScript/Vite production build passed.

Still open:

- Real option-position rows and option lifecycle activation.
- Research recommendation user review.
- Phase 10D analyst-revision evidence gate.
- Trader-commentary aliases and optional X/Discord capture.
- Explicit local API/UI process startup when using the JS control center.

## 2026-06-14 - ETF research promotion hardening and strategy review completion

Implemented the ETF strategy-review hardening pass without broker writes, order
placement, fabricated ETF rows, or recommendation auto-promotion.

Code/UI changes:

- `fetch-options-chain --source yfinance` now imports real call snapshots for
  ETF assets in addition to put snapshots, while keeping sell-put income reviews
  filtered to puts only.
- ETF call strike selection is side-aware and targets near/above-spot call
  strikes separately from put assignment-level strikes.
- `/research` ETF strategy cards and `etf-strategy-review` text now expose NAV,
  NAV gap, expiration, max loss, premium yield, annualized yield, downside
  buffer, assignment notional, source, blockers, and warnings.
- Added regression coverage proving ETF yfinance fetch can import both calls
  and puts, while option-income review generation remains put-only.

Live source-backed actions:

```powershell
python -m target_opportunity_monitor fetch-options-chain --source yfinance --ticker XLV --force-refresh
python -m target_opportunity_monitor fetch-options-chain --source yfinance --ticker XLRE --force-refresh
python -m target_opportunity_monitor compute-options-income --ticker XLV
python -m target_opportunity_monitor compute-options-income --ticker XLRE
python -m target_opportunity_monitor apply-research-ticker --ticker XLRE --asset-type etf --confirm
```

Results:

- `XLV` yfinance fetch loaded 36 source-backed option rows; long-call review is
  now available from `yfinance_option_chain`, and sell-put review remains
  available from `options_income`.
- `XLRE` yfinance fetch loaded 1 source-backed option row. `XLRE` became
  ETF apply-ready and was confirmed into `asset_role=scoreable`.
- `XLRE` strategy review now has available ETF-share and long-call alternatives;
  sell-put remains blocked by `missing_sell_put_review` because no real put
  review exists.
- `SOXL` and `KORU` remain blocked by missing source-backed ETF feature, target,
  score, and range snapshot. They have option-chain evidence, but no real
  issuer/provider ETF NAV/holdings rows were supplied.
- Recommendation rows were not approved, rejected, or promoted by this step.

Verification:

```powershell
python -m py_compile src\target_opportunity_monitor\research_tickers.py src\target_opportunity_monitor\api_server.py src\target_opportunity_monitor\options.py
python tests\test_phase12a_options.py
python tests\test_phase12b_options_chain.py
python tests\test_phase13c_research_recommendations.py
python tests\test_phase14c_research_api.py
python tests\test_phase14f_signal_coverage_api.py
python tools\run_tests.py smoke --timeout-per-file 180
python -m target_opportunity_monitor serve-api --once-smoke-test
npm run build
```

All listed tests and builds passed. Smoke suite passed 14 files in 63.52s. API
smoke returned health endpoint 200 `ok=True` and status endpoint 200 `ok=True`.

Current live status highlights after the change:

- `option-chain-coverage-plan`: effective coverage `47/47`, raw coverage
  `47/48`, raw missing ticker `BIL`, non-actionable ticker `BIL`, warnings
  `none`.
- `research-ticker-plan --ticker XLRE --asset-type etf`: blocked as
  `ticker_already_scoreable` with no readiness blockers.
- `research-ticker-plan --ticker SOXL --asset-type etf`: blocked by
  `missing_etf_feature`, `missing_target`, `missing_score`, and
  `missing_range_snapshot`.
- `research-ticker-plan --ticker KORU --asset-type etf`: blocked by
  `missing_etf_feature`, `missing_target`, `missing_score`, and
  `missing_range_snapshot`.
- `status`: required tables `56/56`, intraday health `healthy`, TOM loop
  `running/healthy`, pending notifications `0`, failed notification deliveries
  `0`, and latest option chain snapshot `2026-06-14T22:04:15`.

Still open:

- Explicit research-review decisions for the remaining pending recommendations.
- Source-backed ETF NAV/holdings rows for `SOXL` and `KORU` if those ETFs should
  become scoreable.
- Expanded-universe short-interest rows for `BRK.B`, `COHR`, `JBL`, and `TSM`
  were still open at this point; they were closed in the 2026-06-15 entry below.
- Optional provider-native news/catalyst redundancy for the expanded universe.
- Real option-position rows and option lifecycle activation.
- Phase 10D analyst-revision evidence gate.
- Trader-commentary aliases and optional X/Discord capture.

## 2026-06-15 - Research preparation autopilot and manual blocker escalation

Implemented the research-preparation autopilot without auto-approving,
auto-rejecting, promoting recommendations, fabricating source rows, changing
broker/account/order state, or weakening evidence gates.

Code/UI changes:

- Added `research_preparation_auto_enabled`,
  `research_preparation_auto_source`, and
  `research_preparation_auto_min_seconds_between_runs` config.
- Added `research-preparation-auto` to manual ops modes `morning`,
  `daily-retry`, and `all`, guarded by the configured throttle.
- Reused the existing confirmed `all_safe` preparation path so autopilot can
  stage/load source rows, recompute readiness, apply only `apply_ready=True`
  tickers, and ignore already-scoreable context rows when TOM gates allow.
- Added latest-autopilot metadata and manual-only blocker packets to research
  preparation status.
- Extended `/research` with an autopilot summary and manual blocker table.
- Added storage lookup for the latest pipeline step result.

Verification commands:

```powershell
python -m py_compile src\target_opportunity_monitor\research_preparation.py src\target_opportunity_monitor\manual_ops.py src\target_opportunity_monitor\api_server.py src\target_opportunity_monitor\cli.py src\target_opportunity_monitor\config.py src\target_opportunity_monitor\storage.py
python tests\test_phase13d_research_preparation.py
python tests\test_phase14c_research_api.py
python tests\test_phase11d3_manual_ops.py
python tests\test_phase13c_research_recommendations.py
python tools\run_tests.py smoke --timeout-per-file 180
python -m target_opportunity_monitor research-preparation-run --source all --action scan
python -m target_opportunity_monitor manual-ops-cycle --mode morning
python -m target_opportunity_monitor status
python -m target_opportunity_monitor serve-api --once-smoke-test
npm run build
```

Results:

- Targeted tests passed: Phase 13D `9/9`, Phase 14C `17/17`, Phase 11D3
  `13/13`, Phase 13C `13/13`.
- Smoke suite passed 14 files in 59.03s.
- `npm run build` in `F:\Investments\tom-ui` passed.
- Initial `research-preparation-run --source all --action scan` reported
  6 items, 55 pending recommendation rows represented, 0 ready-to-apply rows,
  0 already-scoreable/context-only rows, and 4 manual blockers:
  `SIVE`, `SIVEF`, `SLOIF`, and `SOI`, all with
  `source_backed_identity_required`.
- `manual-ops-cycle --mode morning` completed with overall status `ok`.
  The `research-preparation-auto` step ran, loaded/refreshed 6 units of safe
  preparation work, and recorded unresolved identity blockers as warnings:
  `manual_blockers:SIVE|SIVEF|SLOIF|SOI`.
- Follow-up scan reported autopilot `enabled=True`, source `all`, due `False`,
  throttle `21600` seconds, latest autopilot status `warning`, latest run
  `2026-06-15T01:39:45`, rows `6`, and the same four manual blocker packets.
- `status` reported required tables `56/56`, research recommendation pending
  `55`, approved not promoted `0`, latest research autopilot `warning
  2026-06-15T01:39:45 rows=6`, manual blocker tickers
  `SIVE`, `SIVEF`, `SLOIF`, `SOI`, intraday health `healthy`, TOM loop
  `running/healthy`, pending notifications `0`, failed deliveries `0`, and
  short-interest source-backed tickers `31/31`.
- `serve-api --once-smoke-test` returned health endpoint `200 ok=True` and
  status endpoint `200 ok=True`.

Still open:

- Source-backed identity/current listing plus sector/industry metadata for
  `SIVE`, `SIVEF`, `SLOIF`, and `SOI`.
- Explicit research review decisions after those identity blockers are resolved.
- Optional provider-native news/catalyst redundancy for expanded-universe
  tickers.
- Real option-position rows and option lifecycle activation.
- Phase 10D analyst-revision evidence gate.
- Trader-commentary aliases and optional X/Discord capture.

## 2026-06-14 - Research review cleanup for already-scoreable XLRE

Closed the stale `XLRE` research-review row as context-only after ETF hardening
made `XLRE` scoreable. No recommendation was approved or promoted, and no
source rows, score rules, broker/account state, provider keys, or evidence gates
changed.

Commands:

```powershell
python -m target_opportunity_monitor research-recommendation-status
python -m target_opportunity_monitor research-ticker-status --ticker XLRE
python -m target_opportunity_monitor research-ticker-plan --ticker SOXL --asset-type etf
python -m target_opportunity_monitor research-ticker-plan --ticker KORU --asset-type etf
python -m target_opportunity_monitor serve-api --once-smoke-test
npm run build
python -m target_opportunity_monitor set-research-recommendation-status --id 14 --status ignored --reason already_scoreable_after_etf_apply
python -m target_opportunity_monitor research-recommendation-status
python -m target_opportunity_monitor status
```

Results:

- Recommendation `#14 XLRE` changed from `pending` to `ignored`.
- Pending recommendations decreased from `58` to `57`.
- Ignored recommendations increased from `227` to `228`.
- Approved recommendations stayed `0`; promoted recommendations stayed `40`.
- Triage groups are now `SOXL` and `KORU` as `etf_path_required`, plus
  `SIVE`, `SIVEF`, `SLOIF`, and `SOI` as `metadata_required`.
- `SOXL` and `KORU` remain blocked by missing source-backed ETF feature, target,
  score, and range snapshot.
- `status` passed with required tables `56/56`, intraday health `healthy`, TOM
  loop `running/healthy`, pending notifications `0`, and failed deliveries `0`.

Still open:

- Research-review decisions for the remaining `57` pending recommendations.
- Source-backed ETF NAV/holdings rows for `SOXL` and `KORU`.

## 2026-06-15 - Expanded-universe short-interest source coverage closure

Closed the expanded scoreable-universe short-interest gap using the existing
missing-provider workflow. No provider secrets, fabricated values, broker state,
orders, research decisions, option rows, or evidence gates were changed.

Source-backed rows staged in
`data/signals/source_exports/short_interest/missing_provider_short_interest_backfill.csv`:

- `BRK.B`: 2026-05-29 settlement, short interest `12218857`, percent float
  `0.0088`, days to cover `2.82`, source URL
  `https://fintel.io/ss/us/brk.b`.
- `COHR`: 2026-05-29 settlement, short interest `7842738`, percent float
  `0.0403`, average daily volume `5636560`, days to cover `1.46`, source URL
  `https://www.marketbeat.com/stocks/NYSE/COHR/short-interest/`.
- `JBL`: 2026-05-29 settlement, short interest `2960661`, percent float
  `0.0284`, average daily volume `1091024`, days to cover `2.58`, source URL
  `https://www.marketbeat.com/stocks/NYSE/JBL/short-interest/`.
- `TSM`: 2026-05-29 settlement, short interest `28282997`, percent float
  `0.0055`, average daily volume `11890105`, days to cover `2.61`, source URL
  `https://www.marketbeat.com/stocks/NYSE/TSM/short-interest/`.

Commands:

```powershell
python -m target_opportunity_monitor short-interest-missing-coverage-plan
python -m target_opportunity_monitor short-interest-status
python -m target_opportunity_monitor validate-short-interest-backfill
python -m target_opportunity_monitor preview-short-interest-import
python -m target_opportunity_monitor apply-short-interest-provider-backfill
python -m target_opportunity_monitor apply-short-interest-provider-backfill --confirm
python -m target_opportunity_monitor load-short-interest
python -m target_opportunity_monitor compute-short-interest-signals
python -m target_opportunity_monitor validate-short-interest-signals
python tests\test_phase10g_short_interest.py
python tests\test_phase14e_activation_api.py
python tests\test_phase14f_signal_coverage_api.py
python tools\run_tests.py smoke --timeout-per-file 180
python -m target_opportunity_monitor status
python -m target_opportunity_monitor short-interest-status
python -m target_opportunity_monitor serve-api --once-smoke-test
npm run build
```

Results:

- Validation reported valid rows for `BRK.B`, `COHR`, `JBL`, and `TSM`, invalid
  rows `0`, projected source-backed coverage `31/31`, and apply ready `True`.
- Dry-run provider backfill imported `0` rows and reported projected coverage
  improvement `4`.
- Confirmed provider backfill imported `560` validated rows and wrote `584`
  rows to `data/signals/manual/short_interest.csv`.
- `load-short-interest` loaded `560` rows for 31 equity tickers; the only loader
  warning was an unrelated inactive/unknown `GOOG` source row.
- `compute-short-interest-signals` computed 31 equity signals; ETFs stayed
  gated by design.
- `validate-short-interest-signals` updated 40 validation rows; ETF validation
  remained gated by design.
- `short-interest-status` reported source-backed coverage `31/31`, latest
  settlement date `2026-05-29`, missing source tickers `none`, and stale source
  tickers `none`.
- `status` reported required tables `56/56`, TOM loop `running/healthy`,
  intraday health `healthy`, pending notifications `0`, failed notification
  deliveries `0`, short-interest source-backed tickers `31/31`, and short
  interest missing coverage tickers `none`.
- `serve-api --once-smoke-test` returned health endpoint `200 ok=True` and
  status endpoint `200 ok=True`.
- Targeted tests passed: Phase 10G `12/12`, Phase 14E `12/12`, Phase 14F `9/9`.
- Smoke suite passed 14 files in 58.49s.
- `npm run build` in `F:\Investments\tom-ui` passed.

Still open:

- Research-review decisions for the remaining `57` pending recommendations.
- Source-backed ETF NAV/holdings rows for `SOXL` and `KORU`.
- Optional provider-native news/catalyst redundancy for the expanded universe.
- Real option-position rows and option lifecycle activation.
- Phase 10D analyst-revision evidence gate.
- Trader-commentary aliases and optional X/Discord capture.

## 2026-06-15 - Optional news/catalyst provider-native redundancy partial closure

Ran the guarded provider-native upgrade workflow for the optional news/catalyst
redundancy lane. No manual provider-native rows, provider secrets, broker state,
orders, recommendation decisions, option-position rows, or evidence gates were
changed.

Commands:

```powershell
python -m target_opportunity_monitor status
python -m target_opportunity_monitor news-catalyst-provider-upgrade-status
python -m target_opportunity_monitor news-catalyst-provider-backfill-status
python -m target_opportunity_monitor news-catalyst-source-status --provider-upgrade-only
python -m target_opportunity_monitor fetch-news-catalyst-sources --provider all --provider-upgrade --use-cache
python -m target_opportunity_monitor fetch-news-catalyst-sources --provider all --provider-upgrade --use-cache
python -m target_opportunity_monitor fetch-news-catalyst-sources --provider all --provider-upgrade --use-cache
python -m target_opportunity_monitor fetch-news-catalyst-sources --provider all --provider-upgrade --use-cache
python -m target_opportunity_monitor news-catalyst-coverage-plan --mode provider-upgrade --max-tickers 50 --refresh-template
python -m target_opportunity_monitor fetch-news-catalyst-sources --provider all --provider-upgrade --max-tickers 50 --use-cache
python -m target_opportunity_monitor validate-news-catalyst-provider-backfill
python -m target_opportunity_monitor preview-news-catalyst-provider-upgrade
python -m target_opportunity_monitor apply-news-catalyst-provider-backfill
python -m target_opportunity_monitor aggregate-news-catalyst-sources
python -m target_opportunity_monitor load-news-catalysts
python -m target_opportunity_monitor compute-news-catalyst-signals
python -m target_opportunity_monitor validate-news-catalyst-signals
python -m target_opportunity_monitor news-catalyst-coverage-plan --mode provider-upgrade --max-tickers 50 --refresh-template
python -m target_opportunity_monitor status
python -m target_opportunity_monitor serve-api --once-smoke-test
```

Results:

- Provider-native numeric coverage improved from `20/33` to `30/33`.
- The provider-upgrade fetch path added accepted provider-native numeric rows
  for `KOPN`, `LITE`, `LRCX`, `MRVL`, `MU`, `POET`, `SMCI`, `TER`, `TSEM`, and
  `TSM`.
- Remaining text-derived-only provider-native upgrade tickers are `BRK.B`,
  `SIVE`, and `SOI`.
- Provider-native backfill validation found `0` valid rows, `0` invalid rows,
  and `0` blank placeholders; dry-run apply stayed blocked by
  `no_valid_provider_native_backfill_rows`.
- `aggregate-news-catalyst-sources` wrote `78` aggregates, `load-news-catalysts`
  loaded `78` rows, `compute-news-catalyst-signals` computed all `33` equity
  signals, and `validate-news-catalyst-signals` updated `65` validation rows.
- `status` reported required source-backed news/catalyst coverage still complete
  at `33/33`, provider-native numeric coverage `30/33`, missing numeric tickers
  `0`, rejected provider-native rows `0`, and backfill apply ready `False`.
- `serve-api --once-smoke-test` returned health endpoint `200 ok=True` and
  status endpoint `200 ok=True`.

Still open:

- Optional provider-native news/catalyst redundancy for `BRK.B`, `SIVE`, and
  `SOI`, blocked until provider keys, plan access, or valid provider-native
  export rows are supplied.
- Real option-position rows and option lifecycle activation.
- Phase 10D analyst-revision evidence gate.
- Optional X/browser and Discord trader-commentary capture setup.
