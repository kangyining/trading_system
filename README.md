# Target Opportunity Monitor

A Python and React research prototype for equities, ETFs and options. It stores
source-aware data in SQLite, calculates valuation ranges and component scores,
and produces alerts, reports and dashboards.

## Quick start

With Python 3.14+, run from the repository root:

```sh
python tools/review_demo.py
```

The demo uses generated data, disables network connections and writes to a new
`tmp/review-demo-*` directory. It prints paths to an HTML dashboard and
Markdown/CSV reports. Three issuers receive scores; one shows missing-data handling.
No credentials or third-party Python packages are needed.

## Code and checks

Start with [storage](src/target_opportunity_monitor/storage.py),
[valuation](src/target_opportunity_monitor/valuation.py) and
[scoring](src/target_opportunity_monitor/scoring.py).
[Tests](tests/) cover the backend; [tom-ui](tom-ui/) contains the React UI.

```sh
python tools/run_tests.py full --timeout-per-file 180
```

To build the UI with Node 24:

```sh
cd tom-ui
npm ci --ignore-scripts
npm run build
```

## Scope

Scores are hand-weighted heuristics; confidence values are not calibrated
probabilities. The synthetic demo checks software behavior, not investment
performance. Live providers and account workflows need separate configuration.

Imported from `lynx-canadensis/trading_system` with its original history preserved.
