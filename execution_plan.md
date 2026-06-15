# Execution Plan

Created: 2026-06-06

Purpose: this is the living implementation plan for the target trading system. Future implementation planning should update and refer to this file first.

System name:

```text
Target Opportunity Monitor
```

Core goal:

```text
Build a risk-adjusted opportunity monitor that estimates fair-value ranges,
calculates expected value, confirms timing, controls risk, and produces
explainable alerts when current price diverges meaningfully from fair value.
```

---

## 1. Source documents

Use these files as the planning foundation:

1. `DOCS/target-opportunity-trading-system-spec.md`
   - Main system specification.
   - Defines goal, inputs, outputs, components, scores, alert logic, data model, UI, validation, and V1/V2/V3 scope.

2. `DOCS/granular-signal-taxonomy-and-system-blueprint.md`
   - Detailed signal taxonomy.
   - Use for signal families, feature design, scoring logic, and validation concepts.

3. `DOCS/target-price-signal-system-design.md`
   - Simple MVP mental model.
   - Use for target-price range and divergence-alert logic.

4. `DOCS/exhaustive-signal-input-checklist.md`
   - Long-term signal backlog.
   - Use when expanding beyond V1.

5. `DOCS/factor-price-prediction-research-map.md`
   - Modeling and prediction research map.
   - Use when adding ML, factor ranking, RankIC, LightGBM, Qlib-style workflows, or forward-return prediction.

6. `DOCS/online-postings-signal-components-summary.md`
   - Source-backed summary.
   - Use for reasoning and justification.

7. `DOCS/trading-system-reading-list.md`
   - General study/reference material.

---

## 2. Build principle

Do not begin by building the full system.

Build a small, working, explainable V1 first:

```text
data -> target range -> basic scores -> alert report -> outcome tracking
```

Then expand.

The core implementation rule:

```text
No alert should fire just because target price is above current price.

An alert should fire only when target gap, expected value, confidence,
timing, liquidity, and risk all pass defined standards.
```

---

## 3. Implementation phases

### Phase 0: Project foundation

Goal:

Create the runnable project structure and decide the local storage/runtime setup.

Deliverables:

- Project folder structure.
- Configuration file.
- Local database or storage choice.
- Basic CLI entrypoint.
- Basic README/run instructions.

Suggested default:

```text
Python + SQLite + simple CLI + static HTML/Markdown reports
```

Reason:

This is enough for a reliable V1 without overbuilding the app layer too early.

---

### Phase 1: Data model and local storage

Goal:

Create the storage foundation.

Core tables:

```text
assets
prices
price_features
fundamentals
estimates
signals
targets
scores
alerts
alert_outcomes
data_quality_checks
model_versions
```

Deliverables:

- Database schema.
- Data loading/upsert helpers.
- Timestamp and source tracking.
- Data-quality flags.

Important rule:

Every dataset must track:

```text
source
as_of_date
loaded_at
effective_date
```

---

### Phase 2: Universe and market data MVP

Goal:

Start with a manageable universe and reliable market data.

V1 universe:

```text
existing watchlist
major US large/mid-cap names
liquid ETFs if useful
```

Deliverables:

- Asset universe loader.
- Price history loader.
- Adjusted close support.
- Volume and liquidity metrics.
- Basic data-quality checks.

Core features:

```text
current price
adjusted close
daily return
1m return
3m return
6m return
12m return
realized volatility
average dollar volume
```

---

### Phase 3: Fundamental and valuation MVP

Goal:

Produce the first fair-value range per ticker.

Deliverables:

- Fundamental data loader.
- Basic valuation ratios.
- Peer/sector relative valuation.
- Historical valuation comparison.
- Target price range calculation.

V1 valuation methods:

```text
forward P/E target
EV/EBITDA target
P/FCF target
historical multiple target
peer multiple target
```

Output:

```text
base_target
target_low
target_high
valuation_gap
valuation_score
valuation_confidence
```

---

### Phase 4: Core scoring modules

Goal:

Create the first 0-100 scores.

V1 scores:

```text
quality_score
growth_score
revision_score
momentum_score
risk_score
liquidity_score
confidence_score
timing_score
expected_value_score
opportunity_score
```

Deliverables:

- Score calculation modules.
- Score explanation/reason codes.
- Missing-data handling.
- Sector-relative ranking where possible.
- Asset-type-aware scoring: single-company equities and ETFs must use separate
  component logic, model versions, and threshold sets even if they share the
  final `scores` output table.
- Equity scoring uses company valuation, fundamentals, estimates, revisions,
  momentum, risk, and liquidity.
- ETF scoring uses NAV dislocation, premium/discount z-score, holdings
  concentration, tracking quality, liquidity, and underlying/index momentum.

Important:

Scores must remain explainable. Do not hide the system behind a single black-box number.
ETF score thresholds must be tighter than single-company thresholds because
liquid ETF NAV dislocations are usually much smaller than equity valuation gaps.

---

### Phase 5: Alert engine

Goal:

Turn scores and target ranges into useful alerts.

Alert types:

```text
bullish_divergence
bearish_overvaluation
watch_only_gap
revision_inflection
momentum_confirmation
sentiment_inflection
risk_warning
data_quality_warning
existing_position_review
```

Deliverables:

- Alert rules.
- Required gap calculation.
- Alert priority.
- Reason codes.
- Risk codes.
- Invalidation conditions.
- Separate equity and ETF alert thresholds. A 0.5%-1.0% NAV dislocation can be
  meaningful for liquid ETFs, while that same gap is usually noise for a single
  company stock.

V1 bullish rule:

```text
current_price < target_low
and upside_to_base >= required_gap
and expected_value_score >= minimum
and confidence_score >= minimum
and liquidity_score >= minimum
and data_quality_score >= minimum
```

---

### Phase 6: Reporting MVP

Goal:

Make the system useful without requiring a full app.

Deliverables:

- Daily Markdown report.
- Daily CSV report.
- Static HTML report if practical.
- Ticker-level detail section.
- Alert summary section.

Report should include:

```text
ticker
current_price
target_range
upside/downside
opportunity_score
confidence_score
timing_score
risk_score
alert_type
main_reasons
main_risks
invalidation
data_freshness
```

---

### Phase 7: Outcome tracking and validation

Goal:

Measure whether alerts actually work.

Deliverables:

- Alert outcome tracker.
- 5d/20d/60d/120d return tracking.
- Hit-target flag.
- Hit-invalidation flag.
- Max favorable excursion.
- Max adverse excursion.
- Simple validation report.

Metrics:

```text
hit rate
average return
false-positive rate
time to target
time to invalidation
max drawdown after alert
return by alert type
return by opportunity-score bucket
```

This phase is essential. Without outcome tracking, the system cannot improve.

---

### Phase 8: Dashboard

Goal:

Create a browser-based interface after the report flow works.

Screens:

```text
daily alerts
watchlist ranking
ticker detail
price vs target chart
signal breakdown
portfolio review
alert history
model health
data health
```

Default approach:

```text
static HTML dashboard generated from local data
```

Upgrade later only if needed.

---

### Phase 9: Portfolio context and sizing guidance

Goal:

Make alerts aware of current holdings and risk.

Inputs:

```text
current holdings
position size
cost basis
sector exposure
cash
risk tolerance
max position size
```

Outputs:

```text
watch
research deeper
review existing position
small starter candidate
add candidate
reduce/risk review
exit review candidate
```

Important:

V1 should provide review categories, not automatic execution.

---

### Phase 10: Advanced signal expansion

Goal:

Add more signal depth only after the core system works.

Candidates:

```text
news/social sentiment
earnings call transcript tone
filing language changes
short interest
insider trading
ETF/fund flows
options-implied signals
macro regime
alternative data
sector-specific KPIs
ML ranking model
probability calibration
```

Expansion rule:

Add one signal family at a time, and require validation before it affects alerts.

---

## 4. Current phase summary

Use this table as the quick status map before planning new work. Detailed
implementation evidence is archived in `implementation_history.md`.

| Area | Status | Current meaning |
|---|---|---|
| Phase 0 foundation | Complete | Python/SQLite/CLI scaffold, config, default data/report folders, status and daily report commands. |
| Phase 1 data model | Complete | Local schema, watchlist loading, assets, fundamentals, estimates, and typed storage helpers. |
| Phase 2 market data | Complete | Daily price ingestion, local fallback, price features, and market-data quality checks. |
| Phase 3 valuation | Complete | Equity fundamental/estimate loaders, equity targets, ETF NAV/holdings tables, ETF targets, refresh/readiness pipeline. |
| Phase 4 scoring | Complete | Explainable equity and ETF scoring in the unified `scores` surface, with asset-type-aware models. |
| Phase 5 alerts | Complete | Daily/EOD equity alerts and ETF-specific alert rules; no execution or broker writes. |
| Phase 6 reporting | Complete | Markdown and CSV daily reports with alerts, scores, targets, outcomes, ETF status, and portfolio context fields. |
| Phase 7 validation | Complete | Equity and ETF alert outcome tracking using stored daily prices. |
| Phase 8 dashboard | Complete | Static local dashboard at `dashboard/index.html`, generated from local SQLite/report data. |
| Phase 9 portfolio context | Structurally complete | Portfolio review tables, CSV workflow, sizing guidance, and dashboard/report integration exist; real guidance depends on user-filled portfolio CSVs. |
| Phase 10A-10C.2 analyst revisions | Complete but gated | Multi-source analyst revision workflow, aggregation, validation, and evidence gate exist; Phase 10D remains gated until matured 20d evidence passes thresholds. |
| Phase 10E-10E.10 news/catalyst | Complete but shadow-only | Total numeric/source-backed workflow is operational, including source-backed text-derived rows for newly onboarded foreign equities `SIVE` and `SOI`; optional provider-native redundancy is partially closed at `30/33` while signals stay shadow-only. |
| Phase 10F-10F.2 insider activity | Complete | SEC Form 4 insider source fetch, signals, validation, full-watchlist coverage, pacing, and compact source-health warnings. |
| Phase 10G-10G.4 short interest | Complete but shadow-only | Official/provider/export workflow exists and is evidence-producing; focused resolver, missing-coverage diagnostics, refreshed missing-provider template, and guarded apply closed all active-equity source coverage including `SIVE` and `SOI`; signals remain shadow-only. |
| Phase 10H trader commentary input | Complete | Ingest raw commentary, parse structured claims, validate claims over time, keep shadow-only. |
| Phase 10H.2 X browser capture fallback | Complete | Disabled-by-default, opt-in public X rendered-text artifact capture, dedupe, raw-commentary ingestion, and report/dashboard visibility. |
| Phase 10H.3 commentary onboarding and aliases | Complete | Unsupported commentary tickers become onboarding candidates; reference instruments can receive prices/commentary validation without entering scoreable alerts/ranges. |
| Phase 10H.4 commentary reference activation | Complete | Initial reference instruments are active and priced; ticker-mapped commentary claims now validate as pending outcomes while unmapped labels stay explicit. |
| Phase 10H.5 Discord official capture | Complete | Disabled-by-default Discord bot/API capture, dedupe, raw-commentary ingestion, and report/dashboard visibility; no browser automation or score impact. |
| Phase 11A near-real-time range monitor | Complete | Intraday quote probing with daily fallback, buy/hold/trim/sell ranges, dynamic ticker/ETF management, and deduped local notifications. |
| Phase 11B technical/regime engine | Complete | Support/resistance, trend, regime, sector rotation warnings, and range modifiers from stored price/ETF data. |
| Phase 11C intraday operations | Complete | Scheduler-friendly intraday cycle, file/webhook-capable notification delivery, and intraday delivery health in reports/dashboard. |
| Phase 11D Codex scheduler automation | Complete | Codex heartbeat/cron automations run intraday cycles, morning checks, daily refresh, and conditional retry with TOM-side scheduler status. |
| Phase 11D.1 intraday health/notification drain | Complete | Auto-source intraday cycle fallback, health/repair commands, notification outbox status, pending-notification drain, and scheduler/status/report/dashboard health classifications. |
| Phase 11E local persistent ops loop | Complete | User-started `tom-loop-start` persistent loop, one-shot loop recovery, status/health commands, lockfile/heartbeat/stop state under `data/ops/loop/`, and API/UI loop controls. |
| Phase 12A options/sell-put advisory | Complete | Manual option-chain CSV workflow, read-only sell-put advisory reviews, commentary option-idea linkage, and report/dashboard/status coverage. |
| Phase 12B IBKR option-chain ingestion | Complete | Bounded read-only IBKR option-chain fetch, provider/cache status, daily optional chain refresh, and sell-put review activation when bid/ask data exists. |
| Phase 12B.1 option provider health/backfill | Complete | IBKR provider diagnostics, option-chain source-export backfill validation/import, and status/report/dashboard visibility for provider blockers. |
| Phase 12B.2 option-chain activation/minimum seeding | Complete | Activation status, IBKR repair guidance, minimum source-backed backfill for SOXL/KORU/AAPL, and guarded dry-run/confirm apply before Phase 12C risk depth. |
| Phase 12B.3 option-chain data activation | Complete | Repaired local `ibapi` import, documented remaining IBKR connectivity blocker, activated source-backed minimum option-chain rows for SOXL/KORU/AAPL, and produced initial sell-put review rows. |
| Phase 12C options risk/margin depth | Complete | Read-only cash-secured proxy risk reviews with assignment exposure, premium income, downside scenarios, portfolio-context warnings, and reference-instrument warnings. |
| Phase 12D options outcome/position ledger | Complete | Read-only option review outcomes from underlying daily prices plus a manual option-position ledger linked to sell-put reviews. |
| Phase 12E broader option-chain coverage | Complete | Broader option-chain coverage planner, missing-chain source-export template, source-backed non-actionable decision template, guarded apply flow, and status/report/dashboard coverage exist; `BIL`, `SIVE`, and `SOI` raw chain gaps are excluded by source-backed non-actionable decisions. |
| Phase 12E.1 broader option-chain activation | Complete | Read-only `auto` option-chain fetch now tries IBKR then yfinance/Yahoo, stages provider rows through the source-export shape, caches payloads, imports ETF call rows for read-only long-call strategy review, and reports full effective chain coverage with SIVE/SOI non-actionable decisions. |
| Phase 12F option position lifecycle/P&L | Complete | Manual option positions now produce read-only lifecycle reviews, realized P/L, open P/L proxy, assignment exposure, roll links, and report/dashboard/status coverage. |
| Phase 12F.1 / 9B account context activation | Complete | Guided read-only account-context templates, validation, preview, normalization, guarded apply, and report/dashboard/status blockers for portfolio, cash, and option-position activation. |
| Phase 13A-13C research expansion | Complete | Expanded-universe intake, local fundamental benchmark comparisons, one-ticker research onboarding, approval-gated research recommendation queues, safe research-preparation autopilot for current/future tickers, and foreign-equity source intake. `SIVE` and `SOI` are target/score-ready; `SIVE` uses a guarded source-backed analyst-target fallback for loss-making valuation. |
| Phase 14A-14E JS control center | Complete | Local API plus React/TypeScript UI for research, preparation autopilot/manual blockers, assets, ops, scheduler, notifications, activation, and source-data backfills. |
| Phase 15A account context sync | Complete | Read-only account provider status, IBKR/file fetch staging, IBKR Flex/activity/generic normalization, API/UI provider controls, and confirmation-gated apply through existing TOM workflows. |
| Full options execution automation | Deferred | No broker writes, order placement, automatic exercise/assignment handling, or automatic execution. |
| ML/ranking model | Deferred | No production ML ranking, calibration, or score-impact model yet. |
| Trading execution | Out of scope | No order placement, broker writes, or automatic execution. |

Current operating rule:

```text
Active usability beats feature expansion. TOM should prioritize making already
implemented phases produce useful live output now, while preserving no broker
writes, no order placement, no execution, and shadow-only advanced signals until
validation evidence is mature enough to justify score or alert impact.
```

---

## 5. Future planning convention

For future implementation work:

1. Start by reading this file.
2. Identify the current phase.
3. Write the exact task plan under `Active implementation plan`.
4. Keep the task scoped to one phase or one tightly related set of components.
5. After implementation, update `implementation_history.md` and this file's current status.
6. If the system design changes, update this file and the relevant source document.

---

## 6. Active implementation plan

Status:

```text
Cross-phase completion gap repair is the active priority. Do not add a new
phase label for this work. TOM is structurally complete across daily monitoring,
intraday ranges, API/UI, research recommendations, options advisory, and
account-context workflows. Live checks now show intraday quotes/ranges, account
positions/cash, reports, dashboard, API, research, and options layers are
usable. The local TOM loop stale lock was cleared on 2026-06-14, one safe
  validation cycle passed, and the durable loop is running/healthy. Research
  recommendation pending rows are currently `0`, and preparation autopilot now
  runs through manual ops with a six-hour throttle. SIVE/SOI foreign-equity
  fundamentals and EPS rows have been source-backed and imported; both tickers
  now have target/score coverage, with `SIVE` using a guarded source-backed
  analyst-target fallback for loss-making valuation. The remaining gaps are
  related provider/export coverage, option-position rows, optional
  runtime/provider setup, or evidence maturity.
```

Next recommended step:

```text
Check every implemented phase, identify whether the remaining gap is source
data, provider/export access, user review, intentional disablement, or evidence
gating, then fix only actual code/documentation/test gaps before adding new
features.
```

Suggested next implementation task:

```text
Maintain the Active completion gap register below. Treat an implemented phase as
not actively usable if it is stopped, stale, waiting on user/source-backed data,
disabled by choice, or blocked by a validation gate. Do not fabricate missing
data or promote shadow signals to make a phase look complete.
```

User target update:

```text
The next product direction is no longer narrative thesis generation. The system
should move toward near-real-time buy/sell range monitoring, dynamic universe
management, and real-time notifications once intraday alerts are generated.
```

Recommended next product phase:

```text
Build the next options/portfolio depth slice only after real account-context
rows exist. Good candidates are richer margin/cash stress views, realized P/L
rollups, external delivery setup, remaining shadow-data cleanup, or Phase 10D
after analyst-revision evidence matures.
```

Completed Phase 11A outcomes:

1. Make TOM near-real-time instead of daily-only.
   - Reuse the existing intraday foundation: `update-quotes`,
     `probe-market`, quote snapshots, intraday gap snapshots, and pipeline
     run/step audit logs.
   - Add an intraday range-monitor command that refreshes quotes, recomputes
     price-vs-target gaps, evaluates range states, and writes intraday alert
     snapshots without running the full daily fundamentals pipeline.
   - Daily refresh remains the source of truth for slow data such as
     fundamentals, estimates, ETF holdings, NAV history, analyst revisions,
     news/catalyst aggregates, insider activity, and short interest.

2. Generate buy/sell ranges, not thesis text.
   - Convert existing target ranges, scores, alerts, risk, liquidity,
     confidence, portfolio context, and current/intraday prices into explicit
     range outputs:
     - `strong_buy_range`
     - `starter_buy_range`
     - `add_range`
     - `hold_range`
     - `trim_range`
     - `reduce_or_sell_range`
     - `invalidation_or_risk_review_level`
   - Equity ranges should be driven by company target ranges, opportunity
     score, confidence, risk, liquidity, and portfolio exposure.
   - ETF ranges should use ETF-specific logic: NAV/premium-discount,
     ETF score, liquidity, tracking/data-quality warnings, and tighter
     thresholds than single-company equities.
   - This phase should not generate long-form market thesis commentary.

3. Allow add/remove ticker and ETF management.
   - Add explicit universe-management commands instead of editing CSVs by hand:
     - `add-asset --ticker TICKER --asset-type equity|etf ...`
     - `remove-asset --ticker TICKER`
     - `deactivate-asset --ticker TICKER`
     - `asset-status --ticker TICKER`
   - Prefer soft deactivation over hard deletion so historical prices, signals,
     alerts, and outcomes remain auditable.
   - Adding an equity should update the watchlist path, optionally update CIK
     mapping, run readiness checks, and show missing data steps.
   - Adding an ETF should require ETF NAV/holdings readiness separately from
     company fundamentals.

4. Send real-time alerts/notifications after intraday alerts are generated.
   - Add a notification abstraction before choosing channels:
     - `notification_events`
     - `notification_deliveries`
     - dedupe keys
     - cooldown windows
     - severity/priority
     - delivery status
   - Initial channels can be local/Codex-friendly:
     - CLI summary
     - daily/intraday dashboard badge
     - Codex scheduler/heartbeat notification
     - optional desktop/email/Telegram/Discord later
   - Notifications must be idempotent and must not send repeated alerts for
     the same ticker/range crossing inside the cooldown window.

Phase 11A boundaries:

```text
No order placement.
No broker writes.
No automatic trade execution.
No generated thesis/narrative brief.
No advanced signal score-impact enablement.
No broker writes, margin model, executable options strategy engine, or automatic execution.
No full ML model.
```

Phase 11A acceptance criteria:

```text
TOM can monitor active tickers intraday, show current buy/hold/trim/sell range
state, emit deduped notification events when a range threshold is crossed, and
let the user add/remove/deactivate equities or ETFs without manually editing
the watchlist CSV. Daily reports and the dashboard should show both daily/EOD
state and latest intraday range/notification state.
```

Phase 11A, Phase 11B, Phase 11C, Phase 11D, Phase 12A, Phase 12B, Phase 12B.1,
Phase 12B.2, Phase 12B.3, Phase 12C, Phase 12D, Phase 12E, Phase 12E.1, Phase 12F, Phase 12F.1 / 9B, Phase 10H, Phase 10H.1,
Phase 10H.2, Phase 10H.3, Phase 10H.4, and Phase 10H.5 are implemented. The
active next product layer should be chosen from manual option-position data
entry for lifecycle/P&L usefulness, external notification channels, remaining
shadow-data gaps, deeper option portfolio/margin analytics after more real
positions exist, or Phase 10D after
analyst-revision evidence matures.

Additional planned input/signal phases:

```text
Phase 10H - Trader commentary input shadow signals MVP. Completed.
Phase 10H.1 - Commentary seeding and parser review MVP. Completed.
Phase 10H.2 - X browser capture fallback MVP. Completed.
Phase 10H.3 - Commentary asset onboarding and instrument mapping MVP. Completed.
Phase 10H.4 - Commentary reference instrument activation MVP. Completed.
Phase 11B - Technical and market regime signal engine MVP. Completed.
Phase 11C - Intraday operations and notification delivery MVP. Completed.
Phase 11D - Codex scheduler intraday automation MVP. Completed.
Phase 12A - Options/sell-put advisory MVP. Completed.
Phase 12D - Options review outcome tracking and position ledger MVP. Completed.
Phase 12E - Broader option-chain coverage MVP. Completed.
Phase 12E.1 - Broader option-chain data activation MVP. Completed.
Phase 12F - Options position lifecycle and realized P/L MVP. Completed.
Phase 12F.1 / 9B - Account, portfolio, and options position activation MVP. Completed.
```

Phase 10H target outcomes:

1. Store raw trader commentary as source-backed input.
   - Accept manual pasted text, CSV imports, and user-authorized exports from
     private or public sources.
   - Preserve raw text, source author, platform, capture timestamp, source URL
     or capture ID, permission scope, and notes.
   - Keep private/VIP group content as user-provided capture only; do not add
     fragile scraping workflows.

2. Parse structured claims from commentary.
   - Extract tickers, index references, sectors, support/resistance ranges,
     target ranges, downside/risk levels, option strategy mentions, position
     actions, catalysts, time horizon, confidence language, and conditions.
   - Example claim types:
     - `market_resistance_breakout`
     - `technical_support_hold`
     - `technical_resistance_watch`
     - `ticker_price_target`
     - `sector_rotation_view`
     - `options_income_idea`
     - `risk_reduction_instruction`
   - Store parsed claims separately from raw commentary so parsing can improve
     without losing source evidence.

3. Validate commentary claims over time.
   - Track whether support held, resistance broke, target hit, downside level
     hit, direction worked over 1d/5d/20d/60d, and whether the source performs
     better by ticker, asset class, strategy, or regime.
   - Keep all commentary signals shadow-only until there is enough validation
     evidence.

4. Add public interfaces.
   - `load-trader-commentary`
   - `parse-trader-commentary-claims`
   - `validate-trader-commentary-claims`
   - `trader-commentary-status`
   - `trader-commentary-validation-report`

Phase 10H boundaries:

```text
No score impact by default.
No alert impact by default.
No automatic scraping of private groups.
No generated thesis.
No order placement.
```

Phase 10H acceptance criteria:

```text
TOM can ingest raw commentary, extract auditable structured claims such as
TSLA support/resistance or SOXL sell-put ideas, store them separately from raw
text, and validate them over time as shadow-only evidence.
```

Phase 11B target outcomes:

1. Generate technical support/resistance/trend signals from TOM price data.
   - Compute recent swing highs/lows, pivot zones, moving-average state,
     volatility-adjusted support/resistance ranges, breakout/failure states,
     drawdown state, and price location versus target range.
   - Generate explicit levels that can support outputs such as:
     `support_zone`, `resistance_zone`, `breakout_level`,
     `downside_watch_level`, and `trend_repair_level`.

2. Generate market regime and sector-rotation signals.
   - Add benchmark and sector ETF regime coverage for SPY, QQQ, IWM, XLK, XLY,
     XLV, XLF, XLI, XLP, XLU, XLE, XLC, and other configured proxies as needed.
   - Track risk-on/risk-off, breadth proxy, relative strength, sector rotation,
     defensive rotation, tech concentration/crowding proxy, and benchmark trend.
   - Use these as structured signals and range modifiers, not narrative claims.

3. Feed buy/sell range generation without producing long-form thesis.
   - Phase 11B should make Phase 11A ranges smarter by adding technical
     invalidation levels, support-aware starter/add ranges, resistance-aware
     trim ranges, and regime-aware risk warnings.
   - It can support a short explanation field, but should not generate a
     trader-style essay by default.

4. Add public interfaces.
   - `compute-technical-signals`
   - `compute-technical-signals --ticker TSLA`
   - `compute-regime-signals`
   - `technical-status`
   - `regime-status`

Phase 11B boundaries:

```text
No long-form thesis generation by default.
No options strategy engine.
No automatic score impact until validation evidence exists.
No order placement or broker writes.
```

Phase 11B acceptance criteria:

```text
TOM can derive support/resistance/trend/regime/sector-rotation signals from
stored price data and configured benchmark/sector proxies, then expose those
signals to range monitoring and reports. This is the layer that can eventually
support structured insights like "7440-7460 must break" without inventing
levels manually.
```

---

## Phase 11D.3 - Manual TOM ops runner and automation pause

Status: implemented on 2026-06-13.

Phase 11D.3 replaces the TOM-specific Codex automation set with one manual,
local TOM loop while leaving browser/content-capture automations separate.

Implemented surfaces:

```powershell
python -m target_opportunity_monitor manual-ops-loop --mode auto --deliver --channel file
python -m target_opportunity_monitor manual-ops-cycle --mode auto --deliver --channel file
python -m target_opportunity_monitor manual-ops-cycle --dry-run
python -m target_opportunity_monitor manual-ops-status
```

Operational behavior:

- `manual-ops-loop` runs continuously until Ctrl+C and defaults to a 600-second
  interval.
- `--max-iterations N` provides a bounded verification run.
- `auto` selects `morning`, `intraday`, `daily-refresh`, or `daily-retry`
  from America/Toronto time.
- In loop mode, after-hours `auto` uses the guarded retry path so a full daily
  refresh is not repeated every interval once data is current.
- Real runs write `manual_ops_cycle` rows to the existing pipeline audit tables.
- Dry runs show planned steps without writing pipeline rows.
- `daily-retry` refreshes only when the latest daily refresh failed or expected
  price data is stale.

Automation state:

```text
Pause after verification:
tom-intraday-probe
tom-morning-check
tom-daily-refresh
tom-daily-retry

Leave active:
daily-aleabitoreddit-q-a-ingestion
trump-truth-social-posts-morning
```

Boundaries:

- No broker writes.
- No order placement or execution.
- No score, alert-rule, range-rule, option-review, or portfolio mutation.

---

## Phase 11E - Local persistent TOM ops loop

Status: implemented on 2026-06-13.

Phase 11E turns the manual ops worker into a user-started persistent local
process with deterministic file-backed state. Codex scheduler can remain
disabled by choice; TOM can now keep itself fresh from a foreground command.

Implemented surfaces:

```powershell
python -m target_opportunity_monitor tom-loop-start --mode auto --deliver --channel file
python -m target_opportunity_monitor tom-loop-once --mode auto --deliver --channel file
python -m target_opportunity_monitor tom-loop-status
python -m target_opportunity_monitor tom-loop-health
python -m target_opportunity_monitor tom-loop-stop
```

Operational behavior:

- State is stored only under `data/ops/loop/`.
- The loop writes a state file, lockfile, heartbeat file, and stop-request
  marker.
- `tom-loop-start` supports duplicate-loop prevention, stale-lock detection,
  cooperative stop, Ctrl+C shutdown, and bounded `--max-cycles` verification.
- `tom-loop-once` runs one safe `manual-ops-cycle` worker iteration without
  starting a persistent process.
- API endpoints and UI `/loop` expose status, health, start, stop, and run-once
  controls with confirmation gates on mutating actions.
- Stale-lock recovery diagnostics are explicit in `tom-loop-status`,
  `tom-loop-health`, `status`, `/api/loop/status`, `/api/loop/health`,
  dashboard data, and `/loop`. A stale lock stays blocked until the operator
  uses the confirmation-gated clear/start/run-once path.

Preferred operator command:

```powershell
python -m target_opportunity_monitor tom-loop-start --mode auto --deliver --channel file
```

Boundaries:

- No broker writes.
- No order placement or execution.
- No score, alert-rule, range-rule, option-review, or portfolio mutation.

---

## Phase 13A - Expanded universe fundamental benchmark analytics

Status: implemented on 2026-06-13.

Phase 13A adds a first-class, read-only analytics layer for adding more assets
and comparing scoreable equities against local overall, sector, and industry
fundamental medians.

Implemented surfaces:

```powershell
python -m target_opportunity_monitor export-universe-candidate-template
python -m target_opportunity_monitor universe-expansion-plan
python -m target_opportunity_monitor apply-universe-candidates --confirm --allow-partial
python -m target_opportunity_monitor compute-fundamental-benchmarks
python -m target_opportunity_monitor fundamental-benchmark-status
python -m target_opportunity_monitor fundamental-benchmark-report
```

Artifacts:

- `configs/universe_candidates.csv`
- `configs/sector_benchmarks.csv`
- `fundamental_benchmark_snapshots`
- `fundamental_comparison_snapshots`

Current operating notes:

- Sector averages are computed only from TOM's local scoreable equity universe.
- SPY/QQQ and sector ETFs are price/regime benchmarks, not company fundamental
  peers.
- Sector benchmark ETF proxies are active as `regime_proxy` assets and have
  price features for relative-strength comparisons.
- Future missing sector benchmark assets or prices are warnings, not failures.
- New scoreable equities still need price history, SEC fundamentals, estimates,
  targets, and scores before they are ready.
- This phase does not change final scores, alerts, ranges, options reviews,
  portfolio guidance, broker state, or execution.

Recommended next data step:

```text
Use the candidate workflow for any new scoreable equity additions, but require
CIK, price, SEC fundamentals, estimates, targets, and scores before treating
them as ready. Keep sector benchmark ETFs as regime/relative-strength proxies,
not company fundamental peers.
```

---

## Phase 13B - Scoreable research ticker intake and benchmark comparison

Status: implemented on 2026-06-13.

Phase 13B adds a one-ticker workflow for adding a user-requested ticker as a
scoreable research equity after metadata resolution and explicit confirmation.

Implemented surfaces:

```powershell
python -m target_opportunity_monitor research-ticker-plan --ticker TSLA
python -m target_opportunity_monitor research-ticker-plan --ticker TSLA --refresh-metadata
python -m target_opportunity_monitor apply-research-ticker --ticker TSLA --confirm
python -m target_opportunity_monitor apply-research-ticker --ticker TSLA --confirm --sector "Consumer Discretionary" --industry "Auto Manufacturers" --cik 0001318605
python -m target_opportunity_monitor refresh-research-ticker --ticker TSLA
python -m target_opportunity_monitor research-ticker-status --ticker TSLA
python -m target_opportunity_monitor fundamental-benchmark-report --ticker TSLA
```

Current operating notes:

- SEC company ticker metadata is used for CIK/name/exchange where available.
- Provider profile metadata can fill sector/industry when keys and plan access
  allow it; missing provider data is a warning, not fabricated metadata.
- Confirmed scoreable apply blocks when CIK, sector, or industry is missing
  unless supplied explicitly.
- `refresh-research-ticker` reuses the existing ticker-scoped refresh pipeline
  and reports readiness blockers after the run.
- Per-ticker benchmark reports compare the ticker to TOM-local overall, sector,
  and industry medians plus relative strength versus SPY, QQQ, and the mapped
  sector ETF.
- This phase does not change final scoring rules, alert rules, ranges, options
  reviews, portfolio guidance, broker state, or execution.

---

## Phase 13C - Research ticker recommendation queue

Status: implemented on 2026-06-13.

Phase 13C adds an approval-gated queue for recommending tickers for research,
not trading. Candidate generation reads only local TOM state and approved local
artifacts: unsupported/reference commentary tickers, X/browser and Discord
capture rows already in TOM, news/catalyst social rows, the optional sibling
`research-signals` SQLite suggestion queue, and audited manual/Codex CSV rows.

Implemented surfaces:

```powershell
python -m target_opportunity_monitor generate-research-recommendations --source all
python -m target_opportunity_monitor export-research-recommendation-template
python -m target_opportunity_monitor import-research-recommendations
python -m target_opportunity_monitor research-recommendation-status
python -m target_opportunity_monitor research-recommendation-report
python -m target_opportunity_monitor set-research-recommendation-status --id ID --status approved
python -m target_opportunity_monitor promote-research-recommendation --id ID
python -m target_opportunity_monitor promote-research-recommendation --id ID --confirm
python -m target_opportunity_monitor research-preparation-run --source all --action scan
python -m target_opportunity_monitor research-preparation-run --source all --action all_safe --confirm
```

Current operating notes:

- Recommendation scoring is `research_priority_score`, not TOM opportunity
  score.
- Promotion remains explicit and confirmation-gated through Phase 13B.
- Confirmed promotion blocks when CIK, sector, or industry metadata is missing.
- Research preparation automation scans pending and missing ticker candidates,
  runs only safe source-discovery/staging/load/compute/apply-ready/context-cleanup
  steps, and leaves approval/promotion to explicit user review.
- `research-preparation-auto` runs from manual ops in `morning`, `daily-retry`,
  and `all` modes with a throttle, and records unresolved identity/source
  blockers as warnings instead of failing the TOM loop.
- Social inputs use already captured/imported local rows only; no new scraping
  or X/API bypass is introduced.
- This phase does not change final scores, alerts, ranges, options, portfolio
  guidance, broker state, or execution.

---

## Phase 14A/14B/14C/14D/14E - TOM local API and JS control center

Status: Phase 14A, Phase 14B, Phase 14C, Phase 14D, and Phase 14E implemented.

Phase 14 documents the recommended UI migration direction. TOM should keep the
existing Python backend as the source of truth for data ingestion, scoring,
signals, options, portfolio context, scheduler operations, reports, and SQLite
state. A new local API layer should expose safe HTTP/JSON surfaces, and a
separate JS/TypeScript frontend repo should become the full control center.

Architecture decision:

- Keep `F:\Investments\交易系统` as the Python TOM backend.
- Create a parallel UI repo at `F:\Investments\tom-ui`.
- Let the UI talk to TOM through local `127.0.0.1` HTTP/JSON APIs.
- Keep the current static dashboard available as a generated read-only report
  artifact until the JS UI fully replaces it.

Planned and implemented slices:

- Phase 14A: implemented a local TOM API server around existing backend
  functions and CLI-safe workflows.
- Phase 14B: implemented the separate Vite/React/TypeScript read-only UI repo
  at `F:\Investments\tom-ui`.
- Phase 14C: implemented approval-gated research recommendation and research
  ticker intake UI workflows.
- Phase 14D: implemented confirmation-gated asset management, one-shot intraday
  and manual ops controls, scheduler visibility, and notification delivery
  controls.
- Phase 14E: implemented CSV/backfill/account-context/options activation
  screens, including account row staging and confirmation-gated backfill apply
  controls.
- Cross-phase signal coverage refresh: implemented read-only `/signals` and
  `/coverage` UI pages backed by local API coverage payloads for signal lanes
  and phase readiness.

Phase 14A API surface:

```text
GET  /api/health
GET  /api/status
GET  /api/dashboard-data
GET  /api/signals/status
GET  /api/coverage/status
GET  /api/assets
GET  /api/assets/status
POST /api/assets/add
POST /api/assets/deactivate
POST /api/assets/reactivate
POST /api/assets/remove
GET  /api/research/recommendations
GET  /api/research/recommendations/triage
POST /api/research/recommendations/bulk-status
POST /api/research/recommendations/{id}/status
POST /api/research/recommendations/{id}/promote
POST /api/research/ticker-plan
POST /api/research/apply-ticker
POST /api/research/refresh-ticker
GET  /api/research/ticker-status
GET  /api/research/fundamental-benchmark-report
GET  /api/research/etf-strategy-review
GET  /api/research/preparation/status
POST /api/research/preparation/run
GET  /api/research/foreign-equity-source-status
POST /api/research/foreign-equity-source-template
POST /api/research/foreign-equity-source-apply
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
POST /api/backfills/news/append-row
POST /api/backfills/news/apply
GET  /api/backfills/short-interest/status
POST /api/backfills/short-interest/export-template
GET  /api/backfills/short-interest/validate
POST /api/backfills/short-interest/append-row
POST /api/backfills/short-interest/apply
```

Phase 14A commands:

```powershell
python -m target_opportunity_monitor api-status
python -m target_opportunity_monitor serve-api --once-smoke-test
python -m target_opportunity_monitor serve-api
```

Phase 14B UI repo:

```powershell
cd F:\Investments\tom-ui
npm install --cache F:\Investments\tom-ui\.npm-cache
npm run dev
```

Phase 14B read-only routes:

```text
/
/signals
/coverage
/assets
/research
/ops
/scheduler
/notifications
/options
/activation
/backfills
/dashboard-data
```

The UI reads `VITE_TOM_API_BASE_URL` from `F:\Investments\tom-ui\.env.local`
and defaults to `http://127.0.0.1:8765`.

Phase 14C research UI:

```text
/research
  Recommendation Queue: filter/search, details, approve/ignore/reject/promote.
  Ticker Intake: plan, apply, refresh, status, and benchmark report.
  Research Preparation: autopilot status, safe actions, source candidates,
  staged-source rows, and manual-only blocker packets.
```

Phase 14C keeps all state-changing actions behind a local confirmation dialog
before the UI sends API confirmation.

Phase 14D operational controls UI:

```text
/assets
  Detail/status, add/update, deactivate, reactivate, soft remove.
/ops
  Intraday health, manual-ops status, one-shot intraday/manual ops controls.
/loop
  Persistent TOM loop status, health, heartbeat, blockers, and start/stop/run-once controls.
/scheduler
  Scheduler status/audit/reconciliation text, no automation mutation.
/notifications
  Notification event status, delivery report, outbox status, drain to file.
```

Phase 14D keeps asset, ops, and notification actions behind the same local
confirmation dialog. Phase 11E adds the dedicated `/loop` control surface and
prefers `tom-loop-start` for durable foreground operation.

Phase 14E activation/backfill UI:

```text
/activation
  Account-context status, account provider readiness, read-only file/IBKR
  staging, export templates, validate, preview, dry-run apply, confirmed apply,
  and simple source-export row builders for portfolio positions, cash, and
  option positions.
/backfills
  Option-chain, news/catalyst provider-native, and short-interest missing-row
  panels with export, validate, blocker visibility, confirmed apply, and
  confirmation-gated news/catalyst provider-native and short-interest
  missing-provider source-row intake.
```

Phase 14E keeps CSV/source-export writes and apply flows confirmation-gated.
Row builders append only to TOM-controlled source-export paths; TOM validation
and preview remain the source of truth before apply.

Current operating boundaries:

- Local-only first; do not expose the API publicly.
- UI actions that mutate TOM state must remain confirmation-gated.
- Do not add broker writes, order placement, execution, score-rule changes,
  alert-rule changes, range-rule changes, or portfolio mutation.
- The JS UI is a control panel for TOM workflows, not a replacement for the
  Python backend logic.

---

## Active completion gap register

This is not a new phase. Use this register to finish and activate prior phases
before adding more product surface area. A phase may be structurally complete
but still not actively useful if it is stopped, stale, waiting for
source-backed rows, intentionally disabled, waiting for user review, or blocked
by evidence gates.

Allowed gap types: `none`, `operator_start`, `source_data_required`,
`provider_key_or_export_required`, `user_review_required`, `evidence_gated`,
`code_gap`, `disabled_by_choice`.

Live check baseline:

- `status`: passed; `56/56` required tables exist after adding the
  missing-ticker resolver tables.
- `tom-loop-status`: passed after live recovery; loop is `running`, health is
  `healthy`, active is `True`, PID is `8152`, heartbeat age seconds were
  `20.445841`, and `recovery_status` is `active_loop_running`.
- `tom-loop-health`: passed; health is `healthy`, active is `True`, pending
  notifications are `0`, and failed deliveries are `0`.
- `intraday-health-check`: passed; status is `healthy` during the weekend
  off-hours session. Quote and intraday-cycle age are reported as informational
  `off_hours_*_expected` notes instead of stale warnings.
- `account-context-status`: passed; account context is `partial` with 2
  portfolio rows and 1 cash row active; option-position/lifecycle rows remain
  empty. Option-position readiness diagnostics are implemented and currently
  report `source_data_required`, staged option rows `valid=0, invalid=0,
  blank=0`, projected option/lifecycle rows `0/0`, and blockers
  `empty_options_positions`, `no_option_lifecycle_rows`,
  `no_valid_option_position_rows`.
- `account-provider-status`: passed; IBKR read-only source fetch produced
  source-backed account rows for `BIL` and `DBC`.
- `options-status`, `options-risk-status`, `options-lifecycle-status`: passed;
  chain/review layers are active, risk has portfolio/cash context, and
  lifecycle waits on real option-position rows.
- `option-chain-coverage-plan`: passed; broader effective coverage is complete
  at `47/47`, raw coverage is `47/50`, and raw missing tickers `BIL`, `SIVE`,
  and `SOI` are excluded by source-backed non-actionable decisions.
- `short-interest-missing-coverage-plan`: passed after source-backed
  provider/export/manual rows were staged and applied for the original `CRM`,
  `JPM`, `LLY`, and `ORCL` gap, the expanded-universe `BRK.B`, `COHR`, `JBL`,
  and `TSM` gap, and the foreign-equity `SIVE`/`SOI` gap. Source-backed
  coverage is now `33/33`, with missing source tickers `none`.
- `news-catalyst-source-status --missing-only`: passed; source-backed ticker
  coverage is complete at `33/33`, with missing source-backed tickers `none`.
  `SIVE` and `SOI` are covered by official company source-export rows and TOM
  text-derived numeric scoring.
- `news-catalyst-source-status --provider-upgrade-only`: passed; provider-native
  numeric coverage is `30/33`; remaining provider-native upgrade tickers are
  `BRK.B`, `SIVE`, and `SOI`, and they are optional redundancy unless they
  block source-backed coverage.
- `foreign-equity-source-status`: passed; SIVE/SOI source templates contain `3`
  valid fundamental rows, `2` valid estimate rows, and `1` valid analyst-target
  row. Source-required tickers are `none`, blocked reason is `none`, and both
  `SIVE` and `SOI` are ready with target/score.
- `research-recommendation-status`: passed; 325 candidates exist, pending rows
  are `0`, approved-not-promoted rows are `0`, promoted rows are `40`, and
  ignored/rejected rows are `285/0`.
- `revision-evidence-report`: passed; Phase 10D remains `collecting_evidence`
  with zero completed 20d validations.
- `serve-api --once-smoke-test`, `tools/run_tests.py smoke`, and
  `npm run build` passed during this gap-closure refresh.
- `status`: passed; TOM loop is `running`, loop health is `healthy`, intraday
  health is `healthy`, pending notifications are `0`, research preparation
  active/manual-blocker items are `0`, and both `SIVE` and `SOI` have
  foreign-equity target/score coverage.
- `npm run build` in `F:\Investments\tom-ui` passed after adding `/signals` and
  `/coverage`.
- Missing ticker resolver: `BIL` and `DBC` were detected from source-backed
  IBKR account rows, onboarded as scoreable ETFs, hydrated through available
  read-only data paths, and account-context validation/apply now passes.

| Phase | usable_now | gap_type | blocker | fix_path | verification_command |
|---|---|---|---|---|---|
| 0 foundation | yes | none | none | Keep using existing CLI/database scaffold. | `python -m target_opportunity_monitor status` |
| 1 data model | yes | none | none | Keep watchlist/assets/CIK loading current. | `python -m target_opportunity_monitor verify-universe` |
| 2 market data | yes | none | Intraday quote/gap/range timestamps are interpreted with market-hours-aware health; off-hours age is informational, while regular market hours remain strict. IBKR live ticks may still fall back to daily prices when another market-data session blocks ticks. | Keep `tom-loop-start --mode auto --deliver --channel file` running when live monitoring is desired. | `python -m target_opportunity_monitor intraday-health-check` |
| 3 valuation | yes | none | none structural; latest targets exist. | Run daily refresh when price/fundamental data is stale. | `python -m target_opportunity_monitor valuation-status` |
| 4 scoring | yes | none | none structural; latest scores exist. | Keep daily score computation in refresh pipeline. | `python -m target_opportunity_monitor score-status` |
| 5 alerts | yes | none | none structural; alerts are read-only. | Keep daily alert computation and validation active. | `python -m target_opportunity_monitor alert-status` |
| 6 reporting | yes | none | Latest report exists. | Use `run-daily` when a fresh report is needed. | `python -m target_opportunity_monitor status` |
| 7 validation | yes | none | none structural. | Keep outcome update pipeline running. | `python -m target_opportunity_monitor outcome-status` |
| 8 dashboard | yes | none | Dashboard artifact exists. | Rebuild after data refresh. | `python -m target_opportunity_monitor build-dashboard` |
| 9 portfolio context | partial | source_data_required | Portfolio/cash context is active for `BIL` and `DBC`; manual option positions are still empty. Option-position readiness diagnostics/API/UI are implemented and show staged/projected lifecycle readiness. | Add source-backed option-position rows when available; keep cash/position fetch current. | `python -m target_opportunity_monitor account-context-status` |
| 10A-10C analyst revisions | usable_shadow | evidence_gated | 20d evidence has not matured enough for score/alert impact. | Keep collecting source-backed revision validations in shadow mode. | `python -m target_opportunity_monitor revision-evidence-report` |
| 10D analyst revision score impact | no | evidence_gated | Decision is `collecting_evidence`; completed 20d validations are zero. | Do not activate until evidence gate passes configured thresholds. | `python -m target_opportunity_monitor revision-evidence-report` |
| 10E news/catalyst | usable_shadow | none | Source-backed numeric coverage is complete at `33/33`; missing source-backed tickers are `none`. Provider-native numeric coverage is `30/33`, with optional redundancy upgrades still queued for `BRK.B`, `SIVE`, and `SOI`. | Keep source rows auditable; use provider-native exports or keys only if optional redundancy is desired. | `python -m target_opportunity_monitor news-catalyst-source-status --missing-only` |
| 10F insider activity | usable_shadow | none | none structural; coverage is complete and shadow-only. | Keep SEC source fetch/compute/validate in daily pipeline. | `python -m target_opportunity_monitor insider-source-status` |
| 10G short interest | usable_shadow | none | Source-backed coverage is complete at `33/33`; missing source tickers are `none`. ETFs remain gated by design and signals remain shadow-only. | Keep source rows auditable and refresh with newer provider/exchange/broker evidence when available. | `python -m target_opportunity_monitor short-interest-missing-coverage-plan` |
| 10H trader commentary | usable_shadow | disabled_by_choice | Manual seeded commentary works; unknown unmapped labels are `0`. `unmapped_context` and `大盘` (rendered as `??` in legacy console output) are auditable `intentionally_unresolved_ambiguous` dispositions, not ticker mappings. X/Discord captures are disabled unless configured. | Add capture targets/tokens only if desired; add aliases only when the intended instrument is known. | `python -m target_opportunity_monitor commentary-onboarding-status` |
| 11A range monitor | yes | none | Range snapshots exist, intraday health is healthy off-hours, and the durable local loop is running/healthy after stale-lock recovery. | Keep the loop running when active monitoring is desired; use stale-lock recovery only if a future lock appears. | `python -m target_opportunity_monitor range-status` |
| 11B technical/regime | yes | none | Technical coverage is `33/33` active assets and configured regime proxy coverage is `13/13`; `/signals` reports `technical_regime:ready 46/46`. | Keep price refresh and technical/regime computation current. | `python -m target_opportunity_monitor technical-status` |
| 11C intraday operations | yes | none | Intraday health is market-session-aware, pending notifications are drained, and file delivery is available. Expected off-hours quote/cycle age is separated into notes, not warnings; loop stale locks are separate operational blockers. | Monitor `/loop`, `tom-loop-health`, and `notification-delivery-report`. | `python -m target_opportunity_monitor intraday-health-check` |
| 11D scheduler automation | no | disabled_by_choice | Codex scheduler is intentionally not the preferred ops path. | Leave disabled; use Phase 11E local loop. | `python -m target_opportunity_monitor scheduler-status` |
| 11E local persistent ops loop | yes | none | Live loop status is `running`, health is `healthy`, active is `True`, PID is `8152`, and `recovery_status=active_loop_running` after stale-lock recovery. | Keep the foreground loop running when active monitoring is desired; stop with `tom-loop-stop` or recover through `/loop` if a future stale lock appears. | `python -m target_opportunity_monitor tom-loop-status` |
| 12A-12E options advisory/chains | yes | none | Broader effective option-chain coverage is complete at `47/47`. Raw BIL, SIVE, and SOI chain quotes remain absent and are excluded by source-backed non-actionable decisions; ETF yfinance fetches still import real call rows for read-only strategy review where available. | Keep non-actionable decisions auditable; replace them only if future broker/provider chain rows are supplied. | `python -m target_opportunity_monitor option-chain-coverage-plan` |
| 12C options risk | partial | source_data_required | Portfolio/cash context is active; one risk category still reports portfolio-context-needed and lifecycle remains blocked by missing option positions. Option readiness diagnostics distinguish this from generic account partial status. | Add source-backed option-position rows and refresh option risk/lifecycle. | `python -m target_opportunity_monitor options-risk-status` |
| 12D/12F option outcomes/lifecycle | partial | source_data_required | Option position rows and lifecycle rows are zero; `options-lifecycle-status` now reports lifecycle readiness `source_data_required` with explicit option-position blockers. | Fill option positions or account exports, then apply and recompute lifecycle. | `python -m target_opportunity_monitor options-lifecycle-status` |
| 12F.1 / 9B account activation | partial | source_data_required | Account positions/cash are active; option-position rows remain zero. `/activation` now includes an Option Position Readiness panel and context-status API diagnostics. | Fill `options_positions.csv` or import broker option-position rows, then validate/preview/apply. | `python -m target_opportunity_monitor account-context-status` |
| 13A benchmarks | yes | none | Uses TOM-local peers only; no external averages fabricated. | Keep fundamental benchmarks recomputed after scores. | `python -m target_opportunity_monitor fundamental-benchmark-status` |
| 13B research ticker intake | yes | none | Equity intake keeps CIK/company-metadata requirements, ETF intake has a separate `asset_type=etf` path with read-only shares/call/sell-put strategy review, and foreign-equity intake supports source-backed identities without CIK. `XLRE`, `SOXL`, and `KORU` are scoreable through the ETF path; `SIVE` and `SOI` are scoreable through the foreign-equity path. SIVE/SOI now have imported source-backed fundamentals and forward EPS estimates; both have target/score coverage, with `SIVE` using a guarded `source_backed_analyst_target` fallback. | Keep SIVE/SOI source rows and the SIVE analyst-target row auditable; keep approval/promotion confirmation-gated. | `python -m target_opportunity_monitor foreign-equity-source-status` |
| 13C research recommendations | yes | none | Research recommendation pending rows are `0`, approved-not-promoted rows are `0`, and preparation active items are `0`. Triage/API/UI batch-review, grouped queue, and preparation automation are implemented; no rows are auto-approved or auto-promoted. | Keep `/research` available for future recommendations; promote approved ideas one at a time with confirmation. | `python -m target_opportunity_monitor research-recommendation-status` |
| 14A API | yes | none | API is live for this session at `http://127.0.0.1:8765`; health/status/signals/coverage/research-preparation routes returned `200`. | Keep `serve-api` running while using the JS UI; restart it if the local process exits. | `python -m target_opportunity_monitor serve-api --once-smoke-test` |
| 14B-14E JS control center | yes | none | UI is live for this session at `http://127.0.0.1:5173`; `/research`, `/signals`, `/coverage`, `/backfills`, `/activation`, `/loop`, and `/` rendered without backend-offline or unknown-route errors. | Use the live Vite URL while the dev server is running; restart `npm run dev` if the local process exits. | `npm run build` in `F:\Investments\tom-ui` |
| 15A account provider sync | partial | source_data_required | IBKR read-only account fetch works for current holdings; source-backed missing ticker staging is embedded; option-position rows are still empty. | Keep IBKR connected for refreshes or normalize broker exports when options are opened/closed. | `python -m target_opportunity_monitor account-provider-status` |

Priority gap repair order:

1. Operational freshness: keep the local TOM loop running and monitor
   market-session-aware health. Use the stale-lock recovery flow only if a
   future lock appears; only fix code if loop commands/UI status fail.
2. Account/options context: keep portfolio/cash source rows fresh. Option
   readiness diagnostics are implemented; supply source-backed option-position
   rows when available, then validate, preview, dry-run, and confirm apply.
3. Foreign-equity source coverage: keep SIVE/SOI imported fundamentals, EPS
   estimates, short-interest rows, news/catalyst rows, and the SIVE
   source-backed analyst-target fallback auditable. Keep SIVE/SOI option-chain
   non-actionable decisions auditable. Use provider-native news exports for
   `BRK.B`, `SIVE`, and `SOI` only if optional redundancy is desired.
4. Evidence-gated phases: keep Phase 10D and advanced signal score/alert impact
   gated until validation evidence matures.

---

## 7. Implementation history archive

Completed phase implementation logs have been archived in `implementation_history.md`.

Keep `execution_plan.md` focused on current status, planned phases, gated work, and the next active implementation plan.

