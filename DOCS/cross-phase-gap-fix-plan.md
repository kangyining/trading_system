# Cross-Phase Gap Fix Plan

Snapshot date: 2026-06-15.

TOM is operationally healthy: the durable loop is `running/healthy`, intraday
health is `healthy`, pending notifications are `0`, and the research
recommendation queue is currently closed with `0` pending rows. The major
workflow gaps for BIL option-chain availability, ETF research onboarding,
research preparation/autopilot, grouped research review, expanded short-interest
coverage before foreign-equity expansion, technical/regime coverage, TOM loop
recovery, intraday health semantics, and the core API/UI surfaces are already
implemented or outside this immediate focus list. The live API/UI runtime gap is
closed for this session: API is serving at `http://127.0.0.1:8765` and the Vite
UI is serving at `http://127.0.0.1:5173`.

Trader-commentary unmapped-label diagnostics are also resolved: unknown
unmapped labels are now `0`, while `unmapped_context` and the reviewed
market-wide label rendered as `??` in legacy console output are retained as
auditable `intentionally_unresolved_ambiguous` dispositions rather than guessed
ticker mappings.

The live source universe expanded after `SIVE` and `SOI` were promoted as
source-backed foreign equities. Both now have imported source-backed
fundamentals and forward EPS estimate rows. `SOI` has target and score coverage,
and `SIVE` now has target and score coverage through a guarded
source-backed analyst-target fallback for loss-making foreign equities. Both
tickers now have source-backed option-chain availability decisions,
short-interest rows, and news/catalyst rows. Required SIVE/SOI source coverage
is complete; optional provider-native news redundancy remains separate.

Boundaries:

- No broker writes.
- No order placement or execution.
- No fabricated source rows, option quotes, account rows, news/catalyst rows,
  short-interest values, fundamentals, estimates, or analyst-revision evidence.
- No plaintext provider keys persisted in TOM files.
- No weakening of shadow-signal or evidence gates.

## Resolvable Now

### SIVE/SOI Foreign-Equity Source Coverage Follow-Up

Current:

- `SIVE` and `SOI` are scoreable foreign equities with source-backed identity.
- Both have price, range snapshot, sector/industry, and benchmark comparison.
- Foreign-equity source status shows `3` valid fundamental rows, `2` valid
  estimate rows, `1` valid analyst-target row, no source-required tickers, and
  no blocked import reason.
- `SOI` is ready: fundamentals, EPS estimate, target, and score are all present.
- `SIVE` is ready: fundamentals, EPS estimate, target, and score are all
  present. Its target uses the guarded `source_backed_analyst_target` method
  with warnings `source_backed_analyst_target_only` and
  `loss_making_foreign_equity_valuation`.
- Short-interest source-backed coverage is complete at `33/33`; missing source
  tickers are `none`.
- SIVE/SOI short-interest rows are source-backed by Finansinspektionen and AMF
  net-short-position evidence, with latest settlement/position dates
  `2026-06-12` and `2026-06-11`.
- News/catalyst source-backed coverage is complete at `33/33`; missing
  source-backed tickers are `none`.
- SIVE/SOI news/catalyst rows are source-backed by official company releases:
  Sivers' Tachyon Networks development-partnership release dated `2026-05-06`
  and Soitec's FY2025-2026 financial-results release dated `2026-05-27`.
- Provider-native numeric news/catalyst coverage remains optional redundancy at
  `30/33`. The provider-upgrade fetch workflow safely upgraded `KOPN`,
  `LITE`, `LRCX`, `MRVL`, `MU`, `POET`, `SMCI`, `TER`, `TSEM`, and `TSM`
  on `2026-06-15`; the remaining provider-native upgrade tickers are
  `BRK.B`, `SIVE`, and `SOI`.
- Effective option-chain coverage is complete at `47/47`; raw missing tickers
  are `BIL`, `SIVE`, and `SOI`, and all three are excluded by source-backed
  non-actionable decisions.

Why resolvable:

- The guarded foreign-equity source workflow now exists:
  `foreign-equity-source-status`, `export-foreign-equity-source-template`, and
  `apply-foreign-equity-source --confirm`.
- The source templates are staged at
  `data/research/source_exports/foreign_equity_fundamentals.csv` and
  `data/research/source_exports/foreign_equity_estimates.csv`.
- Source-backed analyst target evidence for loss-making foreign-equity
  valuation is staged at
  `data/research/source_exports/foreign_equity_analyst_targets.csv`.
- Existing guarded workflows already cover the related short-interest,
  news/catalyst, and option-chain availability lanes.

Action:

- Keep the imported SIVE/SOI foreign-equity fundamentals and EPS estimate rows
  source-backed and auditable.
- Keep the SIVE analyst-target valuation row source-backed and auditable; do not
  treat it as evidence for short-interest, news/catalyst, or option-chain
  availability.
- Keep the imported SIVE/SOI short-interest rows source-backed and auditable;
  replace them only with newer real numeric provider/exchange/broker evidence.
- Keep the imported SIVE/SOI news/catalyst rows source-backed and auditable;
  replace them only with newer real provider-native or company/source evidence.
- Keep the SIVE/SOI option-chain non-actionable decisions auditable; replace
  them only if a future broker/provider source supplies tradable chain rows.

Guardrail:

- Do not infer fundamentals, EPS, short interest, sentiment scores, or option
  availability from price movement or ticker identity alone.
- Stop with `source_data_required` if source documents cannot be obtained.

### Scheduler Automation

Current:

- Scheduler automation is disabled while the durable local TOM loop is healthy.

Why resolvable:

- Scheduler automation can be enabled or configured if that path is preferred.

Action:

- Leave scheduler automation disabled and keep using the durable TOM loop, or
  explicitly switch back to the scheduler path.

### Optional News Provider Redundancy

Current:

- Provider-native numeric coverage is `30/33`; optional provider-native
  upgrades are queued for `3` tickers.
- Provider-native upgrade tickers are `BRK.B`, `SIVE`, and `SOI`.
- The configured provider-upgrade fetch path improved coverage from `20/33`
  to `30/33` on `2026-06-15`, with no manual provider-native rows or
  plaintext secrets added.
- Optional provider warnings remain for missing keys, rate limits,
  headline-only sources, or plan-limited sources.
- SIVE/SOI required source-backed news coverage is complete; provider-native
  numeric upgrades for them are optional redundancy.

Why resolvable:

- Optional provider keys, provider-plan upgrades, or source-backed provider
  exports could improve the remaining redundancy.

Action:

- Add only desired provider keys through the operator environment, or use the
  source-export workflow for valid provider-native rows for `BRK.B`, `SIVE`,
  and `SOI`.

Guardrail:

- Do not print or persist plaintext provider secrets in TOM files.
- Treat optional redundancy separately from required source-backed coverage.

## Not Resolvable Now

### Phase 10D Analyst Revision Score Impact

Current:

- Decision is `collecting_evidence`.
- Completed 20-day validation rows are still `0`.

Why not resolvable now:

- This is evidence-gated by design.
- It needs time and completed validation windows, not code changes.

What would unblock it:

- Enough matured 20-day analyst-revision validation evidence passing the
  configured gate.

### Full Trader Commentary Capture

Current:

- Manual commentary works.
- X/browser and Discord capture are disabled.

Why not resolvable without choice/setup:

- Capture requires explicit opt-in and allowed targets.
- Discord capture also requires authorized token/channel setup.

What would unblock it:

- User approval plus source/capture configuration.
