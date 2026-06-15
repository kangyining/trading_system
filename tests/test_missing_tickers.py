from __future__ import annotations

from pathlib import Path
import csv
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
TEST_TMP_ROOT = PROJECT_ROOT / ".tmp_tests" / "missing_tickers"
sys.path.insert(0, str(SRC_PATH))

from target_opportunity_monitor.account import (
    apply_account_context_backfill,
    fetch_account_context,
    validate_account_context_backfill,
)
from target_opportunity_monitor.api_server import handle_api_request
from target_opportunity_monitor.config import AppConfig
from target_opportunity_monitor.db import initialize_database
from target_opportunity_monitor.missing_tickers import (
    apply_missing_ticker_onboarding,
    hydrate_missing_ticker,
    missing_ticker_status,
    resolve_missing_tickers,
    run_missing_ticker_automation,
)
from target_opportunity_monitor.portfolio import POSITION_HEADERS
from target_opportunity_monitor.storage import latest_asset


def _config(name: str) -> AppConfig:
    TEST_TMP_ROOT.mkdir(parents=True, exist_ok=True)
    root = TEST_TMP_ROOT / f"{name}_{uuid4().hex}"
    root.mkdir(parents=True, exist_ok=True)
    return AppConfig(
        project_root=root,
        config_path=root / "config.toml",
        database_path=root / "tom.sqlite",
        reports_dir=root / "reports",
        watchlist_path=root / "configs" / "watchlist.csv",
        portfolio_positions_path=root / "data" / "portfolio" / "manual" / "positions.csv",
        portfolio_cash_path=root / "data" / "portfolio" / "manual" / "cash.csv",
        options_positions_path=root / "data" / "options" / "manual" / "options_positions.csv",
        account_source_exports_dir=root / "data" / "account" / "source_exports",
        market_data_dir=root / "data" / "market_data",
        manual_prices_dir=root / "data" / "market_data" / "manual",
        market_data_primary_source="manual",
        market_data_secondary_source="manual",
        market_data_mode="manual",
        market_data_lookback_days=30,
        market_data_stale_after_days=7,
        market_data_minimum_history_days=5,
        universe_mode="manual_watchlist",
        run_mode="test",
        report_title="Test",
    )


def _write_account_positions(config: AppConfig) -> None:
    config.account_source_exports_dir.mkdir(parents=True, exist_ok=True)
    path = config.account_source_exports_dir / "ibkr_read_only_portfolio_positions.csv"
    rows = [
        {
            "ticker": "BIL",
            "quantity": "409",
            "account": "DU123",
            "position_date": "2026-06-13",
            "currency": "USD",
            "cost_basis_per_share": "91.61",
            "asset_type": "",
            "source": "ibkr_account_snapshot",
            "source_url": "ibkr://read-only-account-context",
            "as_of_date": "2026-06-13",
            "effective_date": "2026-06-13",
        },
        {
            "ticker": "DBC",
            "quantity": "399",
            "account": "DU123",
            "position_date": "2026-06-13",
            "currency": "USD",
            "cost_basis_per_share": "30.15",
            "asset_type": "",
            "source": "ibkr_account_snapshot",
            "source_url": "ibkr://read-only-account-context",
            "as_of_date": "2026-06-13",
            "effective_date": "2026-06-13",
        },
    ]
    with path.open("w", encoding="utf-8", newline="") as output_file:
        writer = csv.DictWriter(output_file, fieldnames=POSITION_HEADERS)
        writer.writeheader()
        for row in rows:
            writer.writerow({column: row.get(column, "") for column in POSITION_HEADERS})


class MissingTickerTests(unittest.TestCase):
    def test_account_validation_creates_candidates_and_onboarding_unblocks_rows(self) -> None:
        config = _config("account_candidates")
        initialize_database(config.database_path)
        _write_account_positions(config)

        validation = validate_account_context_backfill(config)
        status = missing_ticker_status(config)

        self.assertEqual(validation.valid_position_rows, 0)
        self.assertTrue(any("unsupported or inactive ticker: BIL" in row for row in validation.invalid_rows))
        self.assertTrue(any("unsupported or inactive ticker: DBC" in row for row in validation.invalid_rows))
        ready_tickers = {
            candidate.ticker
            for candidate in status.candidates
            if candidate.status == "ready_to_onboard"
        }
        self.assertEqual(ready_tickers, {"BIL", "DBC"})

        result = apply_missing_ticker_onboarding(config, confirm=True)
        self.assertTrue(result.applied)
        self.assertEqual(result.onboarded_count, 2)
        self.assertEqual(latest_asset(config.database_path, "BIL").asset_role, "scoreable")
        self.assertEqual(latest_asset(config.database_path, "DBC").asset_type, "etf")

        validation_after = validate_account_context_backfill(config)
        self.assertEqual(validation_after.valid_position_rows, 2)
        self.assertEqual(validation_after.invalid_row_count, 0)

    def test_hydration_uses_mocked_read_only_paths(self) -> None:
        config = _config("hydrate")
        initialize_database(config.database_path)
        _write_account_positions(config)
        apply_missing_ticker_onboarding(config, confirm=True)

        with (
            patch(
                "target_opportunity_monitor.missing_tickers.update_prices",
                return_value=SimpleNamespace(
                    loaded_count=1,
                    results=(SimpleNamespace(warnings=()),),
                ),
            ),
            patch(
                "target_opportunity_monitor.missing_tickers.update_etf_navs_from_ibkr",
                return_value=SimpleNamespace(
                    results=(SimpleNamespace(rows_loaded=0, warnings=("missing_etf_nav",)),),
                ),
            ),
            patch(
                "target_opportunity_monitor.missing_tickers.compute_targets",
                return_value=SimpleNamespace(
                    results=(SimpleNamespace(warnings=("missing_etf_nav",)),),
                ),
            ),
            patch(
                "target_opportunity_monitor.missing_tickers.compute_scores",
                return_value=SimpleNamespace(results=(SimpleNamespace(warnings=()),)),
            ),
            patch(
                "target_opportunity_monitor.missing_tickers.compute_range_snapshots",
                return_value=SimpleNamespace(results=(SimpleNamespace(warnings=()),)),
            ),
        ):
            result = hydrate_missing_ticker(config, "BIL")

        self.assertEqual(result.status, "hydrated")
        self.assertEqual(result.price_loaded_count, 1)
        self.assertIn("missing_etf_nav", result.warnings)

    def test_automation_onboards_and_hydrates_account_candidates(self) -> None:
        config = _config("automation")
        initialize_database(config.database_path)
        _write_account_positions(config)

        with (
            patch(
                "target_opportunity_monitor.missing_tickers.update_prices",
                return_value=SimpleNamespace(
                    loaded_count=1,
                    results=(SimpleNamespace(warnings=()),),
                ),
            ),
            patch(
                "target_opportunity_monitor.missing_tickers.update_etf_navs_from_ibkr",
                return_value=SimpleNamespace(results=()),
            ),
            patch(
                "target_opportunity_monitor.missing_tickers.compute_targets",
                return_value=SimpleNamespace(results=()),
            ),
            patch(
                "target_opportunity_monitor.missing_tickers.compute_scores",
                return_value=SimpleNamespace(results=()),
            ),
            patch(
                "target_opportunity_monitor.missing_tickers.compute_range_snapshots",
                return_value=SimpleNamespace(results=()),
            ),
        ):
            result = run_missing_ticker_automation(config)

        self.assertEqual(result.onboarded_count, 2)
        self.assertEqual(result.hydrated_count, 2)
        self.assertEqual(set(result.onboarded_tickers), {"BIL", "DBC"})
        self.assertEqual(validate_account_context_backfill(config).valid_position_rows, 2)

    def test_confirmed_account_apply_runs_missing_ticker_automation(self) -> None:
        config = _config("account_apply_auto")
        initialize_database(config.database_path)
        _write_account_positions(config)

        with (
            patch(
                "target_opportunity_monitor.missing_tickers.update_prices",
                return_value=SimpleNamespace(
                    loaded_count=1,
                    results=(SimpleNamespace(warnings=()),),
                ),
            ),
            patch(
                "target_opportunity_monitor.missing_tickers.update_etf_navs_from_ibkr",
                return_value=SimpleNamespace(results=()),
            ),
            patch(
                "target_opportunity_monitor.missing_tickers.compute_targets",
                return_value=SimpleNamespace(results=()),
            ),
            patch(
                "target_opportunity_monitor.missing_tickers.compute_scores",
                return_value=SimpleNamespace(results=()),
            ),
            patch(
                "target_opportunity_monitor.missing_tickers.compute_range_snapshots",
                return_value=SimpleNamespace(results=()),
            ),
            patch(
                "target_opportunity_monitor.account.load_portfolio_csvs",
                return_value=SimpleNamespace(position_count=2, cash_count=0, warnings=()),
            ),
            patch(
                "target_opportunity_monitor.account.load_options_positions_csv",
                return_value=SimpleNamespace(loaded_count=0, warnings=()),
            ),
            patch(
                "target_opportunity_monitor.account.compute_portfolio_context",
                return_value=SimpleNamespace(computed_count=2),
            ),
            patch(
                "target_opportunity_monitor.account.compute_options_risk",
                return_value=SimpleNamespace(computed_count=0, results=()),
            ),
            patch(
                "target_opportunity_monitor.account.compute_options_outcomes",
                return_value=SimpleNamespace(computed_count=0, results=()),
            ),
            patch(
                "target_opportunity_monitor.account.compute_options_lifecycle",
                return_value=SimpleNamespace(computed_count=0, results=()),
            ),
            patch(
                "target_opportunity_monitor.account.write_daily_report",
                return_value=SimpleNamespace(path=Path("report.md")),
            ),
            patch(
                "target_opportunity_monitor.account.build_dashboard",
                return_value=SimpleNamespace(path=Path("dashboard.html")),
            ),
        ):
            result = apply_account_context_backfill(
                config,
                confirm=True,
                allow_partial=True,
            )

        self.assertTrue(result.applied)
        self.assertEqual(result.preview.validation.valid_position_rows, 2)
        self.assertEqual(result.preview.validation.invalid_row_count, 0)
        self.assertEqual(latest_asset(config.database_path, "BIL").asset_role, "scoreable")
        onboarded_warning = next(
            warning
            for warning in result.warnings
            if warning.startswith("missing_ticker_auto_onboarded:")
        )
        self.assertEqual(set(onboarded_warning.split(":", 1)[1].split(",")), {"BIL", "DBC"})

    def test_account_fetch_stages_missing_ticker_candidates(self) -> None:
        config = _config("fetch_file")
        initialize_database(config.database_path)
        _write_account_positions(config)
        source_file = config.account_source_exports_dir / "ibkr_read_only_portfolio_positions.csv"

        result = fetch_account_context(
            config,
            source="file",
            provider="generic",
            path=source_file,
            read_only=True,
        )

        self.assertTrue(result.fetched)
        self.assertIn("missing_ticker_candidates_ready:2", result.warnings)
        self.assertEqual(missing_ticker_status(config).ready_to_onboard, 2)

    def test_missing_ticker_api_requires_confirmation_for_mutations(self) -> None:
        config = _config("api")
        initialize_database(config.database_path)
        _write_account_positions(config)

        status_code, status_payload = handle_api_request(config, "GET", "/api/missing-tickers/status")
        blocked_code, blocked_payload = handle_api_request(
            config,
            "POST",
            "/api/missing-tickers/resolve",
            body={"source": "account_context"},
        )
        ok_code, ok_payload = handle_api_request(
            config,
            "POST",
            "/api/missing-tickers/resolve",
            body={"source": "account_context", "confirm": True},
        )

        self.assertEqual(status_code, 200)
        self.assertTrue(status_payload["ok"])
        self.assertEqual(blocked_code, 403)
        self.assertFalse(blocked_payload["ok"])
        self.assertEqual(ok_code, 200)
        self.assertTrue(ok_payload["ok"])


if __name__ == "__main__":
    unittest.main()
