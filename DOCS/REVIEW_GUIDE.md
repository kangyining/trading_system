# Reviewer guide

## Start with an offline example

From a fresh clone, with Python 3.14 or newer:

```sh
python tools/review_demo.py
```

No third-party Python packages or provider credentials are needed for this path.
It creates a new directory under `tmp/` and prints the paths to its JSON summary,
Markdown report, CSV report and interactive HTML dashboard. Open the HTML file in
a browser. The example generates three synthetic issuers with complete inputs
and a fourth with missing fundamentals. Expected results are three computed
targets/scores and one skipped issuer. Network connections are disabled in the
demo itself. Existing project data and scheduler directories are not used.

The numeric inputs are fixed synthetic examples; their dates are relative to the
execution day so freshness checks continue to exercise current-data behavior.
They are not market observations, investment recommendations or a performance
backtest. The generated price series uses synthetic calendar-day rows.

## A ten-minute code walkthrough

| Step | Entry point | What to inspect |
| --- | --- | --- |
| Storage | [`storage.py`](../src/target_opportunity_monitor/storage.py), [`db.py`](../src/target_opportunity_monitor/db.py) | Typed records, source/as-of fields, SQLite schema and idempotent writes. |
| Features | [`market_data.py`](../src/target_opportunity_monitor/market_data.py) | Price normalization, feature calculation and missing/stale data checks. |
| Valuation | [`valuation.py`](../src/target_opportunity_monitor/valuation.py) | Method-specific targets, peer requirements, uncertainty bands and reasons for skipping an asset. |
| Scoring | [`scoring.py`](../src/target_opportunity_monitor/scoring.py) | Explicit component weights and per-issuer explanations rather than an opaque fitted model. |
| Output | [`reporting.py`](../src/target_opportunity_monitor/reporting.py), [`dashboard.py`](../src/target_opportunity_monitor/dashboard.py) | The same stored state reaches inspectable reports and the dashboard. |
| Verification | [`tests/`](../tests/) | Fixtures, failure paths, provider mocks, schema migration and API tests. |

The static diagram is: source inputs -> normalized SQLite records -> price and
fundamental features -> targets -> component scores -> alerts/reports/dashboard.
Optional external providers and the local API are separate from the review demo.

## Checks

```sh
python tests/test_review_demo.py
python tools/run_tests.py smoke
python tools/run_tests.py full --timeout-per-file 180
```

Tests use temporary project-local data. The full suite is substantially longer
than the two demo tests. The React UI has a separate Node dependency/build path:

```sh
cd tom-ui
npm ci --ignore-scripts
npm run build
```

## Model and engineering limits to discuss

- The opportunity score is a hand-weighted heuristic. Unit-test correctness does
  not establish forecasting power, calibration or excess returns.
- Confidence fields summarize the implemented inputs/methods. They are not
  statistically calibrated outcome probabilities.
- Before using historical results as research evidence, establish point-in-time
  availability, corporate-action treatment, universe selection, transaction
  costs, out-of-sample evaluation and an appropriate benchmark.
- Missing provider inputs are surfaced through warnings and readiness states.
  A fresh clone is not populated with private portfolio data or every optional
  source. The demo deliberately shows a missing-data case.
- The API is local by default. Operational/account workflows are outside the
  synthetic review path and require their own configuration and validation.

The repository was imported from `lynx-canadensis/trading_system`; the original
history is preserved. The current review preparation is recorded separately in
Git. Use the original history and a discussion of project responsibilities when
explaining contribution scope.
