# Target Opportunity Monitor

A local research and monitoring prototype for equities, ETFs and options. It
combines source-aware data storage, valuation ranges, explicit component scores,
readiness checks and inspectable reports. Python owns the backend; a separate
React UI talks to a local API.

**Start here:** [reviewer guide](DOCS/REVIEW_GUIDE.md) ·
[backend source](src/target_opportunity_monitor/) · [tests](tests/) ·
[operational reference](DOCS/OPERATIONS_AND_COMMANDS.md)

## Try it offline

With Python 3.14+, run from the repository root:

```sh
python tools/review_demo.py
```

This path uses only the Python standard library. It generates a fresh synthetic
dataset and prints links to a JSON summary, Markdown/CSV reports and an HTML
dashboard. Network connections are disabled inside the demo. Three synthetic
issuers produce targets/scores; a fourth demonstrates missing-data handling.
The example writes to a new `tmp/review-demo-*` directory and does not use an
existing portfolio database or scheduler configuration.

## How it fits together

```text
source inputs -> normalized SQLite records -> features -> targets -> scores
                                                               -> alerts
                                                               -> reports / UI
```

| Area | Implementation |
| --- | --- |
| Data and provenance | Typed price, fundamental, estimate and signal records with source/as-of metadata; manual inputs and optional providers. |
| Valuation and scoring | Multiple valuation methods, uncertainty bands, explicit scoring weights, warnings and per-asset explanations. |
| Monitoring | Technical/range indicators, signal coverage/readiness, research preparation and operational status. |
| Review and delivery | Markdown/CSV reports, static dashboard, local JSON API and React UI. |

The project is a research prototype. The score is a hand-weighted heuristic, and
its confidence fields are not calibrated outcome probabilities. Tests verify
software behavior; the synthetic demo does not establish investment performance.

## Verify

```sh
python tests/test_review_demo.py
python tools/run_tests.py smoke
python tools/run_tests.py full --timeout-per-file 180
```

The full suite covers storage, data normalization, valuation/scoring, signals,
options, operations and API behavior. Its provider calls use test fixtures and
mocks. See the guide for review order and model-validation limitations.

The UI has a separate Node 24 build:

```sh
cd tom-ui
npm ci --ignore-scripts
npm run build
```

The `Review checks` workflow runs Python tests and the UI build on pull requests.
It is verification, not deployment.

## Project context

Imported from `lynx-canadensis/trading_system` with its original history. The
review-preparation changes are separate commits. Optional live provider/account
workflows are described in the operational reference and are outside the offline
review example.
