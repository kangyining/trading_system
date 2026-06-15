from __future__ import annotations

from argparse import Namespace
from contextlib import redirect_stdout
from pathlib import Path
import csv
import io
import sys
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
TEST_TMP_ROOT = PROJECT_ROOT / ".tmp_tests" / "phase12f1"
sys.path.insert(0, str(SRC_PATH))

from target_opportunity_monitor.account import (
    account_context_status,
    apply_account_context_backfill,
    export_account_context_template,
    normalize_account_export,
    preview_account_context_activation,
    validate_account_context_backfill,
)
from target_opportunity_monitor.cli import (
    command_account_context_status,
    command_apply_account_context_backfill,
)
from target_opportunity_monitor.config import AppConfig
from target_opportunity_monitor.db import initialize_database
from target_opportunity_monitor.options import OPTIONS_POSITION_HEADERS
from target_opportunity_monitor.portfolio import CASH_HEADERS, POSITION_HEADERS
from target_opportunity_monitor.storage import (
    Asset,
    OptionIncomeReview,
    PortfolioCash,
    PortfolioPosition,
    count_rows_by_table,
    list_option_position_lifecycle_reviews,
    list_option_risk_reviews,
    upsert_asset,
    upsert_option_income_review,
    upsert_portfolio_cash,
    upsert_portfolio_position,
)


def fresh_database_path(name: str) -> Path:
    TEST_TMP_ROOT.mkdir(parents=True, exist_ok=True)
    path = TEST_TMP_ROOT / name
    if path.exists():
        path.unlink()
    return path


def make_config(database_path: Path) -> AppConfig:
    root = TEST_TMP_ROOT / database_path.stem
    return AppConfig(
        project_root=root,
        config_path=root / "config.toml",
        database_path=database_path,
        reports_dir=root / "reports",
        watchlist_path=root / "configs" / "watchlist.csv",
        market_data_dir=root / "market_data",
        manual_prices_dir=root / "market_data" / "manual",
        market_data_primary_source="stooq",
        market_data_secondary_source="yahoo_chart",
        market_data_mode="csv",
        market_data_lookback_days=800,
        market_data_stale_after_days=7,
        market_data_minimum_history_days=252,
        universe_mode="manual_watchlist",
        run_mode="daily_scoring",
        report_title="Target Opportunity Monitor Daily Report",
        portfolio_positions_path=root / "portfolio" / "positions.csv",
        portfolio_cash_path=root / "portfolio" / "cash.csv",
        options_positions_path=root / "options" / "options_positions.csv",
        account_source_exports_dir=root / "account" / "source_exports",
    )


def write_config(config: AppConfig) -> None:
    config.config_path.parent.mkdir(parents=True, exist_ok=True)
    config.config_path.write_text(
        "\n".join(
            (
                "[paths]",
                f'project_root = "{config.project_root.as_posix()}"',
                f'database = "{config.database_path.as_posix()}"',
                f'reports = "{config.reports_dir.as_posix()}"',
                f'watchlist = "{config.watchlist_path.as_posix()}"',
                f'portfolio_positions = "{config.portfolio_positions_path.as_posix()}"',
                f'portfolio_cash = "{config.portfolio_cash_path.as_posix()}"',
                f'options_positions = "{config.options_positions_path.as_posix()}"',
                f'account_source_exports = "{config.account_source_exports_dir.as_posix()}"',
                "",
                "[run]",
                'universe_mode = "manual_watchlist"',
                'run_mode = "daily_scoring"',
                "",
            )
        ),
        encoding="utf-8",
    )


def seed_asset_and_review(config: AppConfig) -> None:
    initialize_database(config.database_path)
    upsert_asset(
        config.database_path,
        Asset(
            ticker="AAPL",
            name="Apple",
            asset_type="equity",
            exchange="NASDAQ",
            currency="USD",
            sector="Information Technology",
            active_flag=1,
            asset_role="scoreable",
        ),
    )
    upsert_option_income_review(
        config.database_path,
        OptionIncomeReview(
            ticker="AAPL",
            review_date="2026-06-12",
            snapshot_timestamp="2026-06-12T10:00:00",
            expiration_date="2026-07-17",
            option_type="put",
            strike=180.0,
            bid=2.0,
            ask=2.2,
            mid_premium=2.1,
            breakeven=177.9,
            current_price=200.0,
            review_category="eligible_watch",
            source="fixture",
            as_of_date="2026-06-12",
            effective_date="2026-06-12",
        ),
    )


def write_rows(path: Path, headers: tuple[str, ...], rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=headers)
        writer.writeheader()
        for row in rows:
            writer.writerow({header: row.get(header, "") for header in headers})


def position_row(**overrides: object) -> dict[str, object]:
    row: dict[str, object] = {
        "ticker": "AAPL",
        "quantity": 10,
        "account": "paper",
        "position_date": "2026-06-12",
        "currency": "USD",
        "market_price": 200,
        "market_value": 2000,
        "base_market_value": 2000,
        "cost_basis_per_share": 150,
        "cost_basis_total": 1500,
        "asset_type": "equity",
        "sector": "Information Technology",
        "source": "fixture_export",
        "as_of_date": "2026-06-12",
        "effective_date": "2026-06-12",
    }
    row.update(overrides)
    return row


def cash_row(**overrides: object) -> dict[str, object]:
    row: dict[str, object] = {
        "account": "paper",
        "cash_date": "2026-06-12",
        "currency": "USD",
        "cash_amount": 100000,
        "base_cash_amount": 100000,
        "source": "fixture_export",
        "as_of_date": "2026-06-12",
        "effective_date": "2026-06-12",
    }
    row.update(overrides)
    return row


def option_position_row(**overrides: object) -> dict[str, object]:
    row: dict[str, object] = {
        "position_id": "aapl-put-1",
        "ticker": "AAPL",
        "open_date": "2026-06-12",
        "expiration_date": "2026-07-17",
        "option_type": "put",
        "side": "short_put",
        "strike": 180,
        "contracts": 1,
        "premium": 2.1,
        "close_date": "",
        "close_price": "",
        "assigned_flag": "",
        "assignment_price": "",
        "fees": "",
        "account": "paper",
        "status": "open",
        "roll_from_position_id": "",
        "roll_to_position_id": "",
        "underlying_assignment_date": "",
        "underlying_shares": "",
        "underlying_cost_basis": "",
        "tags": "fixture",
        "source": "fixture_export",
        "source_url": "https://example.com/position",
        "notes": "",
        "as_of_date": "2026-06-12",
        "effective_date": "2026-06-12",
    }
    row.update(overrides)
    return row


class Phase12F1AccountContextTests(unittest.TestCase):
    def test_template_export_creates_expected_files(self) -> None:
        config = make_config(fresh_database_path("templates.sqlite"))
        seed_asset_and_review(config)

        result = export_account_context_template(config)
        status = account_context_status(config)

        self.assertTrue(config.portfolio_positions_path.exists())
        self.assertTrue(config.portfolio_cash_path.exists())
        self.assertTrue(config.options_positions_path.exists())
        self.assertEqual(len(result.files), 5)
        self.assertTrue((config.account_source_exports_dir / "portfolio_positions_backfill.csv").exists())
        diagnostics = status.option_position_diagnostics
        self.assertEqual(diagnostics.readiness_status, "source_data_required")
        self.assertEqual(diagnostics.current_option_position_rows, 0)
        self.assertEqual(diagnostics.current_option_lifecycle_rows, 0)
        self.assertEqual(diagnostics.valid_option_position_rows, 0)
        self.assertIn("empty_options_positions", diagnostics.blockers)
        self.assertIn("no_option_lifecycle_rows", diagnostics.blockers)
        self.assertTrue(str(diagnostics.append_target_path).endswith("ui_options_positions_backfill.csv"))

    def test_blank_option_position_rows_do_not_improve_lifecycle_readiness(self) -> None:
        config = make_config(fresh_database_path("blank_options.sqlite"))
        seed_asset_and_review(config)
        export_account_context_template(config)
        write_rows(
            config.account_source_exports_dir / "options_positions_backfill.csv",
            OPTIONS_POSITION_HEADERS,
            [{}],
        )

        status = account_context_status(config)
        diagnostics = status.option_position_diagnostics

        self.assertEqual(diagnostics.readiness_status, "source_data_required")
        self.assertEqual(diagnostics.blank_option_position_rows, 1)
        self.assertEqual(diagnostics.valid_option_position_rows, 0)
        self.assertEqual(diagnostics.projected_option_position_rows, 0)
        self.assertEqual(diagnostics.projected_option_lifecycle_rows, 0)
        self.assertIn("blank_option_position_rows_ignored", diagnostics.warnings)

    def test_invalid_option_position_rows_surface_field_level_diagnostics(self) -> None:
        config = make_config(fresh_database_path("invalid_options.sqlite"))
        seed_asset_and_review(config)
        export_account_context_template(config)
        write_rows(
            config.account_source_exports_dir / "options_positions_backfill.csv",
            OPTIONS_POSITION_HEADERS,
            [option_position_row(strike="")],
        )

        status = account_context_status(config)
        diagnostics = status.option_position_diagnostics

        self.assertEqual(diagnostics.readiness_status, "invalid_source_rows")
        self.assertEqual(diagnostics.invalid_option_position_rows, 1)
        self.assertFalse(status.preview.apply_ready)
        self.assertIn("invalid_option_position_rows", diagnostics.blockers)
        self.assertTrue(any("strike" in reason for reason in diagnostics.invalid_rows))

    def test_validator_accepts_valid_rows_and_preview_is_non_mutating(self) -> None:
        config = make_config(fresh_database_path("preview.sqlite"))
        seed_asset_and_review(config)
        export_account_context_template(config)
        write_rows(
            config.account_source_exports_dir / "portfolio_positions_backfill.csv",
            POSITION_HEADERS,
            [position_row()],
        )
        write_rows(
            config.account_source_exports_dir / "portfolio_cash_backfill.csv",
            CASH_HEADERS,
            [cash_row()],
        )
        write_rows(
            config.account_source_exports_dir / "options_positions_backfill.csv",
            OPTIONS_POSITION_HEADERS,
            [option_position_row()],
        )

        validation = validate_account_context_backfill(config)
        preview = preview_account_context_activation(config)

        self.assertEqual(validation.valid_position_rows, 1)
        self.assertEqual(validation.valid_cash_rows, 1)
        self.assertEqual(validation.valid_option_position_rows, 1)
        self.assertEqual(validation.invalid_row_count, 0)
        self.assertTrue(preview.apply_ready)
        diagnostics = account_context_status(config).option_position_diagnostics
        self.assertEqual(diagnostics.readiness_status, "ready_for_apply")
        self.assertEqual(diagnostics.valid_option_position_rows, 1)
        self.assertEqual(diagnostics.projected_option_position_rows, 1)
        self.assertEqual(diagnostics.projected_option_lifecycle_rows, 1)
        self.assertTrue(diagnostics.would_improve_lifecycle)
        self.assertEqual(count_rows_by_table(config.database_path, "portfolio_positions"), 0)
        self.assertEqual(count_rows_by_table(config.database_path, "option_position_ledger"), 0)

    def test_validator_rejects_missing_account_and_unsupported_ticker(self) -> None:
        config = make_config(fresh_database_path("invalid.sqlite"))
        seed_asset_and_review(config)
        export_account_context_template(config)
        write_rows(
            config.account_source_exports_dir / "portfolio_positions_backfill.csv",
            POSITION_HEADERS,
            [position_row(account="", ticker="NOPE")],
        )

        validation = validate_account_context_backfill(config)

        self.assertGreaterEqual(validation.invalid_row_count, 2)
        self.assertTrue(any("missing_account" in reason for reason in validation.invalid_rows))
        self.assertTrue(any("unsupported or inactive ticker" in reason for reason in validation.invalid_rows))

    def test_apply_dry_run_does_not_mutate(self) -> None:
        config = make_config(fresh_database_path("dry_run.sqlite"))
        seed_asset_and_review(config)
        export_account_context_template(config)
        write_rows(
            config.account_source_exports_dir / "portfolio_cash_backfill.csv",
            CASH_HEADERS,
            [cash_row()],
        )

        result = apply_account_context_backfill(config)

        self.assertFalse(result.applied)
        self.assertIn("dry_run_only", result.warnings)
        self.assertEqual(count_rows_by_table(config.database_path, "portfolio_cash"), 0)

    def test_confirm_allow_partial_imports_rows_and_computes_lifecycle(self) -> None:
        config = make_config(fresh_database_path("apply.sqlite"))
        seed_asset_and_review(config)
        export_account_context_template(config)
        write_rows(
            config.account_source_exports_dir / "portfolio_positions_backfill.csv",
            POSITION_HEADERS,
            [position_row()],
        )
        write_rows(
            config.account_source_exports_dir / "portfolio_cash_backfill.csv",
            CASH_HEADERS,
            [cash_row()],
        )
        write_rows(
            config.account_source_exports_dir / "options_positions_backfill.csv",
            OPTIONS_POSITION_HEADERS,
            [option_position_row()],
        )

        result = apply_account_context_backfill(
            config,
            confirm=True,
            allow_partial=True,
        )

        self.assertTrue(result.applied)
        self.assertEqual(count_rows_by_table(config.database_path, "portfolio_positions"), 1)
        self.assertEqual(count_rows_by_table(config.database_path, "portfolio_cash"), 1)
        self.assertEqual(count_rows_by_table(config.database_path, "option_position_ledger"), 1)
        self.assertEqual(len(list_option_position_lifecycle_reviews(config.database_path)), 1)
        diagnostics = account_context_status(config).option_position_diagnostics
        self.assertEqual(diagnostics.readiness_status, "active")
        self.assertEqual(diagnostics.current_option_position_rows, 1)
        self.assertEqual(diagnostics.current_option_lifecycle_rows, 1)
        risk_reviews = list_option_risk_reviews(config.database_path, ticker="AAPL")
        self.assertTrue(risk_reviews)
        self.assertTrue(
            all("missing_portfolio_context" not in (review.risk_warnings or "") for review in risk_reviews)
        )

    def test_confirm_blocks_when_no_valid_rows_exist(self) -> None:
        config = make_config(fresh_database_path("blocked.sqlite"))
        seed_asset_and_review(config)
        export_account_context_template(config)

        with self.assertRaises(ValueError):
            apply_account_context_backfill(config, confirm=True, allow_partial=True)
        diagnostics = account_context_status(config).option_position_diagnostics
        self.assertEqual(diagnostics.readiness_status, "source_data_required")
        self.assertIn("empty_options_positions", diagnostics.blockers)

    def test_normalize_generic_account_export_writes_source_exports(self) -> None:
        config = make_config(fresh_database_path("normalize.sqlite"))
        seed_asset_and_review(config)
        raw_path = config.project_root / "generic_account.csv"
        write_rows(
            raw_path,
            (
                "record_type",
                "account",
                "ticker",
                "quantity",
                "cash_amount",
                "currency",
                "position_date",
                "cash_date",
                "source",
            ),
            [
                {
                    "record_type": "position",
                    "account": "paper",
                    "ticker": "AAPL",
                    "quantity": 3,
                    "currency": "USD",
                    "position_date": "2026-06-12",
                    "source": "generic_export",
                },
                {
                    "record_type": "cash",
                    "account": "paper",
                    "cash_amount": 5000,
                    "currency": "USD",
                    "cash_date": "2026-06-12",
                    "source": "generic_export",
                },
            ],
        )

        result = normalize_account_export(config, provider="generic", path=raw_path)

        self.assertEqual(result.position_rows, 1)
        self.assertEqual(result.cash_rows, 1)
        self.assertEqual(len(result.output_files), 2)

    def test_cli_status_and_apply_are_wired(self) -> None:
        config = make_config(fresh_database_path("cli.sqlite"))
        seed_asset_and_review(config)
        write_config(config)

        status_buffer = io.StringIO()
        with redirect_stdout(status_buffer):
            exit_code = command_account_context_status(Namespace(config=config.config_path))

        self.assertEqual(exit_code, 0)
        self.assertIn("Account Context Status", status_buffer.getvalue())

        apply_buffer = io.StringIO()
        with redirect_stdout(apply_buffer):
            exit_code = command_apply_account_context_backfill(
                Namespace(config=config.config_path, confirm=False, allow_partial=False)
            )
        self.assertEqual(exit_code, 0)
        self.assertIn("dry_run_only", apply_buffer.getvalue())


if __name__ == "__main__":
    unittest.main()
