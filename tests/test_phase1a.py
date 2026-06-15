from __future__ import annotations

from argparse import Namespace
from contextlib import redirect_stdout
from pathlib import Path
import io
import sys
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
TEST_TMP_ROOT = PROJECT_ROOT / ".tmp_tests"
sys.path.insert(0, str(SRC_PATH))

from target_opportunity_monitor.cli import command_status
from target_opportunity_monitor.db import REQUIRED_TABLES, initialize_database
from target_opportunity_monitor.storage import (
    Asset,
    Estimate,
    Fundamental,
    count_assets,
    count_rows_by_table,
    list_assets,
    upsert_asset,
    upsert_estimate,
    upsert_fundamental,
)
from target_opportunity_monitor.watchlist import load_watchlist


class Phase1ATests(unittest.TestCase):
    def setUp(self) -> None:
        TEST_TMP_ROOT.mkdir(exist_ok=True)

    def fresh_database_path(self, name: str) -> Path:
        path = TEST_TMP_ROOT / name
        if path.exists():
            path.unlink()
        return path

    def fresh_file_path(self, name: str) -> Path:
        path = TEST_TMP_ROOT / name
        if path.exists():
            path.unlink()
        return path

    def write_config(self, name: str, database_path: Path, watchlist_path: Path) -> Path:
        config_path = self.fresh_file_path(name)
        config_path.write_text(
            "\n".join(
                (
                    "[paths]",
                    f'database = "{database_path.as_posix()}"',
                    f'reports = "{(TEST_TMP_ROOT / "reports").as_posix()}"',
                    f'watchlist = "{watchlist_path.as_posix()}"',
                    "",
                    "[run]",
                    'universe_mode = "manual_watchlist"',
                    'run_mode = "daily_scoring"',
                    "",
                    "[reports]",
                    'title = "Target Opportunity Monitor Daily Report"',
                    "",
                )
            ),
            encoding="utf-8",
        )
        return config_path

    def test_init_db_creates_phase1a_required_tables(self) -> None:
        database_path = self.fresh_database_path("phase1a_required_tables.sqlite")

        status = initialize_database(database_path)

        self.assertIn("fundamentals", status.existing_tables)
        self.assertIn("estimates", status.existing_tables)
        self.assertEqual(status.existing_required_table_count, len(REQUIRED_TABLES))

    def test_asset_upsert_and_list_are_idempotent_and_sorted(self) -> None:
        database_path = self.fresh_database_path("assets.sqlite")
        initialize_database(database_path)

        upsert_asset(database_path, Asset(ticker="msft", name="Old Name"))
        upsert_asset(database_path, Asset(ticker="AAPL", name="Apple Inc."))
        upsert_asset(database_path, Asset(ticker="MSFT", name="Microsoft Corporation"))

        assets = list_assets(database_path)

        self.assertEqual(count_assets(database_path), 2)
        self.assertEqual([asset.ticker for asset in assets], ["AAPL", "MSFT"])
        self.assertEqual(assets[1].name, "Microsoft Corporation")

    def test_watchlist_loader_inserts_and_updates_without_duplicates(self) -> None:
        database_path = self.fresh_database_path("watchlist.sqlite")
        watchlist_path = self.fresh_file_path("watchlist.csv")
        initialize_database(database_path)
        watchlist_path.write_text(
            "\n".join(
                (
                    "ticker,name,asset_type,exchange,currency,sector,industry,country",
                    "msft,Old Microsoft,equity,NASDAQ,USD,Technology,Software,US",
                    "aapl,Apple Inc.,equity,NASDAQ,USD,Technology,Devices,US",
                    "",
                )
            ),
            encoding="utf-8",
        )

        first_result = load_watchlist(database_path, watchlist_path)
        watchlist_path.write_text(
            "\n".join(
                (
                    "ticker,name,asset_type,exchange,currency,sector,industry,country",
                    "MSFT,Microsoft Corporation,equity,NASDAQ,USD,Technology,Software,US",
                    "AAPL,Apple Inc.,equity,NASDAQ,USD,Technology,Devices,US",
                    "",
                )
            ),
            encoding="utf-8",
        )
        second_result = load_watchlist(database_path, watchlist_path)

        assets = list_assets(database_path)
        self.assertEqual(first_result.loaded_count, 2)
        self.assertEqual(second_result.loaded_count, 2)
        self.assertEqual(count_assets(database_path), 2)
        self.assertEqual([asset.ticker for asset in assets], ["AAPL", "MSFT"])
        self.assertEqual(assets[1].name, "Microsoft Corporation")

    def test_fundamental_and_estimate_upserts_are_idempotent(self) -> None:
        database_path = self.fresh_database_path("fundamentals_estimates.sqlite")
        initialize_database(database_path)

        upsert_fundamental(
            database_path,
            Fundamental(
                ticker="AAPL",
                fiscal_period_end="2026-03-31",
                fiscal_period="Q2",
                report_type="quarterly",
                currency="USD",
                revenue=100.0,
                source="manual",
            ),
        )
        upsert_fundamental(
            database_path,
            Fundamental(
                ticker="AAPL",
                fiscal_period_end="2026-03-31",
                fiscal_period="Q2",
                report_type="quarterly",
                currency="USD",
                revenue=110.0,
                source="manual",
            ),
        )
        upsert_estimate(
            database_path,
            Estimate(
                ticker="AAPL",
                estimate_date="2026-06-06",
                fiscal_period_end="2026-09-30",
                metric="eps",
                consensus_mean=2.5,
                analyst_count=25,
                source="manual",
            ),
        )
        upsert_estimate(
            database_path,
            Estimate(
                ticker="AAPL",
                estimate_date="2026-06-06",
                fiscal_period_end="2026-09-30",
                metric="eps",
                consensus_mean=2.7,
                analyst_count=26,
                source="manual",
            ),
        )

        self.assertEqual(count_rows_by_table(database_path, "fundamentals"), 1)
        self.assertEqual(count_rows_by_table(database_path, "estimates"), 1)

    def test_status_reports_asset_count_and_watchlist_existence(self) -> None:
        database_path = self.fresh_database_path("status_phase1a.sqlite")
        watchlist_path = self.fresh_file_path("status_watchlist.csv")
        config_path = self.write_config("status_config.toml", database_path, watchlist_path)
        initialize_database(database_path)
        watchlist_path.write_text(
            "ticker,name\nAAPL,Apple Inc.\n",
            encoding="utf-8",
        )
        load_watchlist(database_path, watchlist_path)

        output = io.StringIO()
        with redirect_stdout(output):
            command_status(Namespace(config=config_path))

        status_text = output.getvalue()
        self.assertIn("Asset count: 1", status_text)
        self.assertIn("Watchlist exists: True", status_text)
        self.assertIn(
            f"Required tables present: {len(REQUIRED_TABLES)}/{len(REQUIRED_TABLES)}",
            status_text,
        )


if __name__ == "__main__":
    unittest.main()
