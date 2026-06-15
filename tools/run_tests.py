from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
TEST_DIR = PROJECT_ROOT / "tests"

SMOKE_TESTS = (
    "test_phase0.py",
    "test_phase1a.py",
    "test_phase2.py",
    "test_phase11d1_intraday_health.py",
    "test_phase11d2_scheduler_reconciliation.py",
    "test_phase11d3_manual_ops.py",
    "test_phase11e_tom_loop.py",
    "test_phase11e_loop_api.py",
    "test_phase14a_api_server.py",
    "test_phase14c_research_api.py",
    "test_phase14d_ops_api.py",
    "test_phase14e_activation_api.py",
    "test_phase15a_account_sync.py",
    "test_missing_tickers.py",
)

CORE_TESTS = (
    "test_fundamental_seeding.py",
    "test_phase0.py",
    "test_phase1a.py",
    "test_phase2.py",
    "test_phase3.py",
    "test_phase3b_etf.py",
    "test_phase3c_scheduler_pipeline.py",
    "test_phase4_scoring.py",
    "test_phase5a_alerts.py",
    "test_phase6a_reporting.py",
    "test_phase7a_outcomes.py",
    "test_phase8a_dashboard.py",
    "test_phase9a_portfolio.py",
)

SIGNAL_TESTS = tuple(path.name for path in sorted(TEST_DIR.glob("test_phase10*.py")))
OPS_TESTS = tuple(path.name for path in sorted(TEST_DIR.glob("test_phase11*.py")))
OPTIONS_TESTS = tuple(path.name for path in sorted(TEST_DIR.glob("test_phase12*.py")))
ANALYTICS_TESTS = tuple(path.name for path in sorted(TEST_DIR.glob("test_phase13*.py")))
FULL_TESTS = tuple(path.name for path in sorted(TEST_DIR.glob("test_*.py")))

SUITES = {
    "smoke": SMOKE_TESTS,
    "core": CORE_TESTS,
    "signals": SIGNAL_TESTS,
    "ops": OPS_TESTS,
    "options": OPTIONS_TESTS,
    "analytics": ANALYTICS_TESTS,
    "full": FULL_TESTS,
}


def _existing_test_files(names: tuple[str, ...]) -> list[Path]:
    files = [TEST_DIR / name for name in names]
    missing = [path.name for path in files if not path.exists()]
    if missing:
        raise SystemExit(f"Unknown test files in suite: {', '.join(missing)}")
    return files


def _list_suites() -> int:
    for suite_name, names in SUITES.items():
        print(f"{suite_name}:")
        for name in names:
            print(f"  {name}")
    return 0


def _run_file(path: Path, timeout: int) -> tuple[int, float]:
    started = time.perf_counter()
    try:
        completed = subprocess.run(
            [sys.executable, str(path)],
            cwd=PROJECT_ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as error:
        elapsed = time.perf_counter() - started
        print(f"{path.name}: TIMEOUT after {elapsed:.2f}s")
        if error.stdout:
            print(error.stdout)
        return 124, elapsed

    elapsed = time.perf_counter() - started
    status = "OK" if completed.returncode == 0 else f"FAIL({completed.returncode})"
    print(f"{path.name}: {status} in {elapsed:.2f}s")
    if completed.returncode != 0:
        print(completed.stdout)
    return completed.returncode, elapsed


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run TOM test suites with per-file timing.")
    parser.add_argument(
        "suite",
        nargs="?",
        choices=tuple(SUITES),
        help="Suite to run. Use --list to inspect suite contents.",
    )
    parser.add_argument("--list", action="store_true", help="List available suites and test files.")
    parser.add_argument(
        "--timeout-per-file",
        type=int,
        default=120,
        help="Maximum seconds allowed for each test file. Default: 120.",
    )
    parser.add_argument("--fail-fast", action="store_true", help="Stop after the first failure.")
    args = parser.parse_args(argv)

    if args.list:
        return _list_suites()
    if not args.suite:
        parser.error("suite is required unless --list is used")

    files = _existing_test_files(SUITES[args.suite])
    suite_started = time.perf_counter()
    failures: list[str] = []
    timings: list[tuple[float, str]] = []
    print(f"Running {args.suite} suite: {len(files)} files")
    for path in files:
        return_code, elapsed = _run_file(path, args.timeout_per_file)
        timings.append((elapsed, path.name))
        if return_code != 0:
            failures.append(path.name)
            if args.fail_fast:
                break

    total = time.perf_counter() - suite_started
    print()
    print(f"{args.suite} suite finished in {total:.2f}s")
    print("Slowest files:")
    for elapsed, name in sorted(timings, reverse=True)[:10]:
        print(f"  {elapsed:8.2f}s {name}")
    if failures:
        print(f"Failures: {', '.join(failures)}")
        return 1
    print("All selected tests passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
