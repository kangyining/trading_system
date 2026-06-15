# TOM UI

Local React/TypeScript control center for the Python TOM backend.

## Requirements

Start the TOM API first from the backend repo:

```powershell
python -m target_opportunity_monitor serve-api
```

Then start this UI from `F:\Investments\tom-ui`:

```powershell
npm install --cache F:\Investments\tom-ui\.npm-cache
npm run dev
```

Open `http://127.0.0.1:5173`.

## Phase 14C Research Workflows

The `/research` page now includes:

- `Recommendation Queue` for filtering/searching research candidates, reviewing
  details, approving, ignoring, rejecting, and preparing promotions.
- `Ticker Intake` for ticker planning, confirmed apply, confirmed refresh,
  readiness status, and fundamental benchmark reports.

Every state-changing action opens a local confirmation dialog before the UI
sends `confirm: true` to TOM.

## Phase 14D Operational Controls

The UI now includes local operations pages:

- `/assets`: asset table, asset status detail, add/update form, deactivate,
  reactivate, and soft-remove controls.
- `/ops`: intraday health, quote/range freshness, manual-ops status, one-shot
  intraday cycle, and one-shot manual ops cycle controls.
- `/scheduler`: scheduler reconciliation, heartbeat command, audit text, repair
  plan, and automation status. This page does not mutate Codex automations.
- `/notifications`: pending/delivered/failed notification status, delivery
  report, outbox status, and file-drain control.

The `/loop` page shows loop state, heartbeat age, blockers, and local controls.
For durable operation, prefer the foreground TOM command:

```powershell
python -m target_opportunity_monitor tom-loop-start --mode auto --deliver --channel file
```

The older `manual-ops-loop` command remains compatible, but `tom-loop-start` is
the preferred persistent operator path.

## Phase 14E Activation And Backfills

The UI now includes activation/backfill screens for workflows that were
previously CLI-only:

- `/activation`: account-context status, template export, validation, preview,
  provider status, read-only file/IBKR staging, export normalization, dry-run
  apply, confirmed apply, and small row-builder forms for portfolio positions,
  cash rows, and option positions. It also includes the Missing Tickers panel
  for resolving source-backed account holdings that are not yet active TOM
  assets; confirmed account apply also runs this source-backed resolver before
  validation so held tickers do not require a separate cleanup command.
- `/backfills`: option-chain coverage, news/catalyst provider-native upgrade,
  and short-interest missing-row panels with export, validate, blocker display,
  and confirmation-gated apply controls.

Provider fetches and row builders stage rows into TOM-controlled
source-export/template paths only. They do not edit broker state or bypass TOM
validation. Apply buttons still require TOM preview/validation and a local
confirmation dialog before the UI sends `confirm: true`.

The `/research` page also shows the Missing Tickers panel, but research/social
mentions remain approval-gated. Only source-backed account holdings can flow
through the automatic onboarding path.

## Boundaries

This UI reads the local TOM API and only mutates TOM through explicit
confirmation-gated TOM workflows. It does not place orders, write to brokers,
change TOM scores, change TOM alerts, change ranges, or mutate portfolio state.
