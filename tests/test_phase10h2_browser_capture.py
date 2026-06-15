from __future__ import annotations

from argparse import Namespace
from contextlib import redirect_stdout
from datetime import date
from pathlib import Path
import io
import shutil
import sys
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
TEST_TMP_ROOT = PROJECT_ROOT / ".tmp_tests" / "phase10h2"
sys.path.insert(0, str(SRC_PATH))

from target_opportunity_monitor.browser_commentary import (
    browser_capture_commentary,
    browser_capture_status,
    extract_x_browser_items,
    ingest_browser_captured_commentary,
)
from target_opportunity_monitor.cli import (
    command_browser_capture_commentary,
    command_browser_capture_commentary_status,
    command_ingest_browser_captured_commentary,
    command_status,
)
from target_opportunity_monitor.config import AppConfig, load_config
from target_opportunity_monitor.dashboard import build_dashboard
from target_opportunity_monitor.db import REQUIRED_TABLES, initialize_database
from target_opportunity_monitor.reporting import REPORT_CSV_COLUMNS, write_daily_report
from target_opportunity_monitor.storage import (
    count_rows_by_table,
    list_trader_commentary_browser_capture_items,
    list_trader_commentary_raw,
)
from target_opportunity_monitor.trader_commentary import (
    parse_trader_commentary_claims,
    validate_trader_commentary_claims,
)


def fresh_database_path(name: str) -> Path:
    TEST_TMP_ROOT.mkdir(parents=True, exist_ok=True)
    path = TEST_TMP_ROOT / name
    if path.exists():
        path.unlink()
    return path


def make_config(database_path: Path) -> AppConfig:
    return AppConfig(
        project_root=TEST_TMP_ROOT,
        config_path=TEST_TMP_ROOT / f"phase10h2_{database_path.stem}.toml",
        database_path=database_path,
        reports_dir=TEST_TMP_ROOT / "reports_phase10h2",
        watchlist_path=TEST_TMP_ROOT / "watchlist_phase10h2.csv",
        market_data_dir=TEST_TMP_ROOT / "market_data_phase10h2",
        manual_prices_dir=TEST_TMP_ROOT / "market_data_phase10h2" / "manual",
        market_data_primary_source="stooq",
        market_data_secondary_source="yahoo_chart",
        market_data_mode="csv",
        market_data_lookback_days=800,
        market_data_stale_after_days=7,
        market_data_minimum_history_days=252,
        universe_mode="manual_watchlist",
        run_mode="daily_scoring",
        report_title="Target Opportunity Monitor Daily Report",
        trader_commentary_path=TEST_TMP_ROOT
        / "signals"
        / "manual"
        / f"{database_path.stem}_commentary.csv",
        trader_commentary_exports_dir=TEST_TMP_ROOT
        / "signals"
        / "source_exports"
        / database_path.stem,
        trader_commentary_browser_capture_dir=TEST_TMP_ROOT
        / "signals"
        / "browser_captures"
        / database_path.stem,
        signals_trader_commentary_model_version="trader_commentary_mvp_v1",
        signals_trader_commentary_shadow_mode=True,
        signals_trader_commentary_default_horizons=("1d", "5d", "20d", "60d"),
        signals_trader_commentary_stale_after_days=30,
    )


def write_config(config: AppConfig) -> None:
    config.config_path.parent.mkdir(parents=True, exist_ok=True)
    config.config_path.write_text(
        "\n".join(
            (
                "[paths]",
                f'database = "{config.database_path.as_posix()}"',
                f'reports = "{config.reports_dir.as_posix()}"',
                f'watchlist = "{config.watchlist_path.as_posix()}"',
                f'trader_commentary = "{config.trader_commentary_path.as_posix()}"',
                f'trader_commentary_exports = "{config.trader_commentary_exports_dir.as_posix()}"',
                f'trader_commentary_browser_capture = "{config.trader_commentary_browser_capture_dir.as_posix()}"',
                "",
                "[market_data]",
                'primary_source = "stooq"',
                'secondary_source = "yahoo_chart"',
                'mode = "csv"',
                "lookback_days = 800",
                "stale_after_days = 7",
                "minimum_history_days = 252",
                "",
                "[signals]",
                'trader_commentary_model_version = "trader_commentary_mvp_v1"',
                "trader_commentary_shadow_mode = true",
                'trader_commentary_default_horizons = ["1d", "5d", "20d", "60d"]',
                "trader_commentary_stale_after_days = 30",
                "",
                "[commentary_browser_capture]",
                "enabled = false",
                'provider = "x_browser"',
                "target_urls = []",
                "max_scroll_batches = 3",
                "min_seconds_between_runs = 900",
                "require_operator_acknowledgement = true",
                "",
                "[run]",
                'universe_mode = "manual_watchlist"',
                'run_mode = "daily_scoring"',
                "",
            )
        ),
        encoding="utf-8",
    )


SAMPLE_X_TEXT = """Kobeissi Letter
@KobeissiLetter
https://x.com/KobeissiLetter/status/1800000000000000001
AAPL is testing 200 support. Breakout above 210 could repair the trend.

Market Monitor
@MarketMonitor
https://x.com/MarketMonitor/status/1800000000000000002
MSFT target 520 if cloud momentum continues, risk below 480.
"""


class Phase10H2BrowserCaptureTests(unittest.TestCase):
    def setUp(self) -> None:
        if TEST_TMP_ROOT.exists():
            shutil.rmtree(TEST_TMP_ROOT)
        TEST_TMP_ROOT.mkdir(parents=True, exist_ok=True)

    def test_config_defaults_and_schema(self) -> None:
        config = load_config(PROJECT_ROOT / "configs" / "default.toml")
        self.assertFalse(config.commentary_browser_capture_enabled)
        self.assertEqual(config.commentary_browser_capture_provider, "x_browser")
        self.assertEqual(config.commentary_browser_capture_target_urls, ())
        self.assertEqual(config.commentary_browser_capture_max_scroll_batches, 3)
        self.assertEqual(config.commentary_browser_capture_min_seconds_between_runs, 900)
        self.assertTrue(config.commentary_browser_capture_require_operator_acknowledgement)
        self.assertEqual(
            config.trader_commentary_browser_capture_dir,
            PROJECT_ROOT / "data" / "signals" / "browser_captures" / "trader_commentary",
        )

        database_path = fresh_database_path("phase10h2_schema.sqlite")
        status = initialize_database(database_path)
        self.assertEqual(status.existing_required_table_count, len(REQUIRED_TABLES))
        self.assertIn("trader_commentary_browser_capture_runs", status.existing_tables)
        self.assertIn("trader_commentary_browser_capture_items", status.existing_tables)

    def test_parser_extracts_mocked_x_visible_text(self) -> None:
        items, warnings = extract_x_browser_items(
            SAMPLE_X_TEXT,
            "https://x.com/KobeissiLetter",
            observed_at="2026-06-10T10:00:00",
        )
        self.assertEqual(len(items), 2)
        self.assertIn("x_api_not_used", warnings)
        self.assertEqual(items[0].external_id, "1800000000000000001")
        self.assertIn("AAPL", items[0].content_text)

    def test_missing_acknowledgement_blocks_capture(self) -> None:
        database_path = fresh_database_path("phase10h2_ack.sqlite")
        config = make_config(database_path)
        initialize_database(database_path)
        text_path = TEST_TMP_ROOT / "x_text.txt"
        text_path.write_text(SAMPLE_X_TEXT, encoding="utf-8")

        result = browser_capture_commentary(
            config,
            provider="x_browser",
            target_url="https://x.com/KobeissiLetter",
            dom_text_file=text_path,
            acknowledge_terms_risk=False,
        )
        self.assertEqual(result.status, "blocked")
        self.assertIn("terms_risk_acknowledgement_required", result.warnings)
        self.assertEqual(count_rows_by_table(database_path, "trader_commentary_browser_capture_runs"), 1)
        self.assertEqual(count_rows_by_table(database_path, "trader_commentary_browser_capture_items"), 0)

    def test_capture_dedupe_ingest_and_commentary_parser_flow(self) -> None:
        database_path = fresh_database_path("phase10h2_ingest.sqlite")
        config = make_config(database_path)
        initialize_database(database_path)
        text_path = TEST_TMP_ROOT / "x_text.txt"
        text_path.write_text(SAMPLE_X_TEXT, encoding="utf-8")

        first = browser_capture_commentary(
            config,
            provider="x_browser",
            target_url="https://x.com/KobeissiLetter",
            dom_text_file=text_path,
            acknowledge_terms_risk=True,
        )
        second = browser_capture_commentary(
            config,
            provider="x_browser",
            target_url="https://x.com/KobeissiLetter",
            dom_text_file=text_path,
            acknowledge_terms_risk=True,
        )
        self.assertEqual(first.stored_count, 2)
        self.assertEqual(second.stored_count, 2)
        self.assertEqual(count_rows_by_table(database_path, "trader_commentary_browser_capture_runs"), 2)
        self.assertEqual(count_rows_by_table(database_path, "trader_commentary_browser_capture_items"), 2)

        ingest = ingest_browser_captured_commentary(config)
        self.assertEqual(ingest.imported_count, 2)
        self.assertEqual(count_rows_by_table(database_path, "trader_commentary_raw"), 2)
        self.assertTrue(
            all(item.ingested_at for item in list_trader_commentary_browser_capture_items(database_path))
        )
        raw_rows = list_trader_commentary_raw(database_path)
        self.assertTrue(all(row.source == "x_browser_capture" for row in raw_rows))

        parse_result = parse_trader_commentary_claims(config)
        self.assertGreaterEqual(parse_result.parsed_count, 1)
        validation_result = validate_trader_commentary_claims(config)
        self.assertGreaterEqual(validation_result.skipped_count, 0)

    def test_block_page_records_partial_run(self) -> None:
        database_path = fresh_database_path("phase10h2_block.sqlite")
        config = make_config(database_path)
        initialize_database(database_path)
        text_path = TEST_TMP_ROOT / "x_block.txt"
        text_path.write_text("Sign in to X\ncaptcha\nSomething went wrong", encoding="utf-8")

        result = browser_capture_commentary(
            config,
            provider="x_browser",
            target_url="https://x.com/search?q=AAPL",
            dom_text_file=text_path,
            acknowledge_terms_risk=True,
        )
        self.assertEqual(result.status, "partial")
        self.assertIn("browser_capture_blocked", result.warnings)
        self.assertEqual(result.stored_count, 0)

    def test_cli_status_reports_and_dashboard_include_browser_capture(self) -> None:
        database_path = fresh_database_path("phase10h2_outputs.sqlite")
        config = make_config(database_path)
        write_config(config)
        initialize_database(database_path)
        text_path = TEST_TMP_ROOT / "x_text.txt"
        text_path.write_text(SAMPLE_X_TEXT, encoding="utf-8")

        with redirect_stdout(io.StringIO()) as capture_output:
            self.assertEqual(
                command_browser_capture_commentary(
                    Namespace(
                        config=config.config_path,
                        provider="x_browser",
                        target_url="https://x.com/KobeissiLetter",
                        dom_text_file=text_path,
                        page_html_file=None,
                        acknowledge_terms_risk=True,
                    )
                ),
                0,
            )
        self.assertIn("Browser commentary capture complete", capture_output.getvalue())

        with redirect_stdout(io.StringIO()) as ingest_output:
            self.assertEqual(
                command_ingest_browser_captured_commentary(
                    Namespace(config=config.config_path, provider="x_browser")
                ),
                0,
            )
        self.assertIn("imported=2", ingest_output.getvalue())

        with redirect_stdout(io.StringIO()) as browser_status_output:
            self.assertEqual(
                command_browser_capture_commentary_status(
                    Namespace(config=config.config_path)
                ),
                0,
            )
        self.assertIn("Trader Commentary Browser Capture Status", browser_status_output.getvalue())

        with redirect_stdout(io.StringIO()) as system_status_output:
            self.assertEqual(command_status(Namespace(config=config.config_path)), 0)
        self.assertIn("Trader commentary browser capture run rows", system_status_output.getvalue())

        report = write_daily_report(config, run_date=date(2026, 6, 10))
        report_text = report.path.read_text(encoding="utf-8")
        self.assertIn("Trader commentary browser capture run rows", report_text)
        self.assertIn("trader_commentary_browser_capture_run_count", REPORT_CSV_COLUMNS)
        csv_text = report.csv_path.read_text(encoding="utf-8") if report.csv_path else ""
        self.assertIn("trader_commentary_browser_capture_run_count", csv_text)

        dashboard = build_dashboard(config)
        html = dashboard.path.read_text(encoding="utf-8")
        self.assertIn("Commentary Browser Runs", html)
        self.assertIn("trader_commentary_browser_capture_run_rows", html)

        status = browser_capture_status(config)
        self.assertEqual(status.run_count, 1)
        self.assertEqual(status.item_count, 2)


if __name__ == "__main__":
    unittest.main()
