from __future__ import annotations

from argparse import Namespace
from contextlib import redirect_stdout
from dataclasses import replace
from datetime import date, timedelta
from pathlib import Path
import io
import json
import re
import shutil
import sys
import unittest
from unittest.mock import patch


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
TEST_TMP_ROOT = PROJECT_ROOT / ".tmp_tests"
sys.path.insert(0, str(SRC_PATH))

from support import patch_refresh_pipeline_for_test
from target_opportunity_monitor.cli import (
    command_compute_insider_signals,
    command_fetch_insider_transactions,
    command_insider_source_status,
    command_insider_status,
    command_insider_validation_report,
    command_status,
    command_validate_insider_signals,
)
from target_opportunity_monitor.config import AppConfig, load_config
from target_opportunity_monitor.dashboard import build_dashboard
from target_opportunity_monitor.db import initialize_database
from target_opportunity_monitor.insider_activity import (
    COMPOSITE_SIGNAL_NAME,
    SIGNAL_FAMILY,
    build_insider_source_status_text,
    compute_insider_signals,
    filing_cache_path,
    fetch_insider_transactions,
    insider_source_status_report,
    insider_statuses,
    load_or_fetch_form4_document,
    parse_form4_transactions,
    submissions_cache_path,
)
from target_opportunity_monitor.pipeline import run_refresh_data
from target_opportunity_monitor.reporting import write_daily_report
from target_opportunity_monitor.signal_validation import (
    build_insider_validation_report,
    validate_insider_signals,
)
from target_opportunity_monitor.storage import (
    Asset,
    InsiderTransactionSourceSnapshot,
    Price,
    count_rows_by_table,
    insert_data_quality_check,
    list_insider_transaction_source_snapshots,
    list_signal_outcomes,
    list_signals,
    signal_outcome_statuses,
    upsert_asset,
    upsert_insider_transaction_source_snapshot,
    upsert_prices,
)


def fresh_database_path(name: str) -> Path:
    TEST_TMP_ROOT.mkdir(exist_ok=True)
    path = TEST_TMP_ROOT / name
    if path.exists():
        path.unlink()
    return path


def make_config(database_path: Path) -> AppConfig:
    return AppConfig(
        project_root=TEST_TMP_ROOT,
        config_path=TEST_TMP_ROOT / f"phase10f_{database_path.stem}.toml",
        database_path=database_path,
        reports_dir=TEST_TMP_ROOT / "reports_phase10f",
        watchlist_path=TEST_TMP_ROOT / "watchlist_phase10f.csv",
        market_data_dir=TEST_TMP_ROOT / "market_data_phase10f",
        manual_prices_dir=TEST_TMP_ROOT / "market_data_phase10f" / "manual",
        market_data_primary_source="stooq",
        market_data_secondary_source="yahoo_chart",
        market_data_mode="csv",
        market_data_lookback_days=800,
        market_data_stale_after_days=7,
        market_data_minimum_history_days=252,
        universe_mode="manual_watchlist",
        run_mode="daily_scoring",
        report_title="Target Opportunity Monitor Daily Report",
        cik_map_path=TEST_TMP_ROOT / f"cik_map_{database_path.stem}.csv",
        insider_cache_dir=TEST_TMP_ROOT / "signals" / "cache" / database_path.stem,
        sec_user_agent="TargetOpportunityMonitorTest/1.0 test@example.com",
        signals_insider_activity_model_version="insider_activity_mvp_v1",
        signals_insider_activity_shadow_mode=True,
        signals_insider_activity_lookback_days=180,
        signals_insider_activity_stale_after_days=14,
        signals_insider_activity_fetch_limit_per_ticker=40,
        signals_insider_activity_sec_rate_limit_cooldown_seconds=0.0,
        signals_insider_activity_min_transaction_value=10_000.0,
    )


def write_config(config: AppConfig) -> None:
    config.config_path.parent.mkdir(parents=True, exist_ok=True)
    config.config_path.write_text(
        "\n".join(
            (
                "[paths]",
                f'project_root = "{TEST_TMP_ROOT.as_posix()}"',
                f'database = "{config.database_path.as_posix()}"',
                f'reports = "{config.reports_dir.as_posix()}"',
                f'watchlist = "{config.watchlist_path.as_posix()}"',
                f'cik_map = "{config.cik_map_path.as_posix()}"',
                f'insider_cache = "{config.insider_cache_dir.as_posix()}"',
                "",
                "[sec]",
                f'user_agent = "{config.sec_user_agent}"',
                "",
                "[signals]",
                'insider_activity_model_version = "insider_activity_mvp_v1"',
                "insider_activity_shadow_mode = true",
                "insider_activity_lookback_days = 180",
                "insider_activity_stale_after_days = 14",
                "insider_activity_fetch_limit_per_ticker = 40",
                "insider_activity_max_tickers_per_run = 13",
                "insider_activity_use_cache = true",
                "insider_activity_sec_request_delay_seconds = 0.2",
                "insider_activity_sec_rate_limit_cooldown_seconds = 60",
                "insider_activity_stop_on_rate_limit = true",
                "insider_activity_max_live_form4_fetches_per_ticker = 10",
                "insider_activity_skip_successful_fetch_same_day = true",
                "insider_activity_min_transaction_value = 10000",
                "",
                "[run]",
                'universe_mode = "manual_watchlist"',
                'run_mode = "daily_scoring"',
                "",
                "[reports]",
                f'title = "{config.report_title}"',
                "",
            )
        ),
        encoding="utf-8",
    )


def form4_xml(
    transaction_date: str,
    code: str = "P",
    acquired_disposed: str = "A",
    shares: float = 1000,
    price: float = 120,
) -> str:
    return f"""<?xml version="1.0"?>
<ownershipDocument>
  <reportingOwner>
    <reportingOwnerId>
      <rptOwnerName>Jane Insider</rptOwnerName>
    </reportingOwnerId>
    <reportingOwnerRelationship>
      <isDirector>1</isDirector>
      <officerTitle>Chief Financial Officer</officerTitle>
    </reportingOwnerRelationship>
  </reportingOwner>
  <nonDerivativeTable>
    <nonDerivativeTransaction>
      <transactionDate><value>{transaction_date}</value></transactionDate>
      <transactionCoding><transactionCode>{code}</transactionCode></transactionCoding>
      <transactionAmounts>
        <transactionShares><value>{shares}</value></transactionShares>
        <transactionPricePerShare><value>{price}</value></transactionPricePerShare>
        <transactionAcquiredDisposedCode><value>{acquired_disposed}</value></transactionAcquiredDisposedCode>
      </transactionAmounts>
    </nonDerivativeTransaction>
  </nonDerivativeTable>
</ownershipDocument>
"""


def make_price(ticker: str, price_date: str, close: float) -> Price:
    return Price(
        ticker=ticker,
        price_date=price_date,
        open=close,
        high=close + 1,
        low=close - 1,
        close=close,
        adjusted_close=close,
        volume=1_000_000,
        source="fixture",
        as_of_date=price_date,
        effective_date=price_date,
    )


def seed_assets(config: AppConfig) -> None:
    initialize_database(config.database_path)
    upsert_asset(config.database_path, Asset(ticker="AAPL", asset_type="equity"))
    upsert_asset(config.database_path, Asset(ticker="MSFT", asset_type="equity"))
    upsert_asset(config.database_path, Asset(ticker="SPY", asset_type="etf"))
    config.cik_map_path.parent.mkdir(parents=True, exist_ok=True)
    config.cik_map_path.write_text(
        "ticker,cik\nAAPL,0000320193\nMSFT,0000789019\n",
        encoding="utf-8",
    )


class Phase10FInsiderActivityTest(unittest.TestCase):
    def test_config_defaults_and_table_initialize(self) -> None:
        config = load_config(PROJECT_ROOT / "configs" / "default.toml")
        self.assertEqual(
            config.insider_cache_dir,
            PROJECT_ROOT / "data" / "signals" / "cache" / "insider_transactions",
        )
        self.assertEqual(config.signals_insider_activity_model_version, "insider_activity_mvp_v1")
        self.assertTrue(config.signals_insider_activity_shadow_mode)
        self.assertEqual(config.signals_insider_activity_max_tickers_per_run, 13)
        self.assertTrue(config.signals_insider_activity_use_cache)
        self.assertEqual(config.signals_insider_activity_sec_request_delay_seconds, 0.2)
        self.assertEqual(config.signals_insider_activity_sec_rate_limit_cooldown_seconds, 60)
        self.assertTrue(config.signals_insider_activity_stop_on_rate_limit)
        self.assertEqual(
            config.signals_insider_activity_max_live_form4_fetches_per_ticker,
            10,
        )
        self.assertTrue(config.signals_insider_activity_skip_successful_fetch_same_day)
        database_path = fresh_database_path("phase10f_schema.sqlite")
        status = initialize_database(database_path)
        self.assertIn("insider_transaction_source_snapshots", status.existing_tables)
        self.assertEqual(
            count_rows_by_table(database_path, "insider_transaction_source_snapshots"),
            0,
        )

    def test_form4_parser_and_storage_are_idempotent(self) -> None:
        database_path = fresh_database_path("phase10f_storage.sqlite")
        initialize_database(database_path)
        rows = parse_form4_transactions(
            ticker="AAPL",
            cik="0000320193",
            accession_number="0000320193-26-000001",
            filing_date="2026-06-01",
            source_url="https://www.sec.gov/example.xml",
            text=form4_xml("2026-05-31"),
            min_transaction_value=10_000.0,
        )
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].transaction_code, "P")
        self.assertEqual(rows[0].transaction_value, 120_000)
        upsert_insider_transaction_source_snapshot(database_path, rows[0])
        upsert_insider_transaction_source_snapshot(database_path, rows[0])
        missing_price = InsiderTransactionSourceSnapshot(
            ticker="AAPL",
            cik="0000320193",
            accession_number="0000320193-26-000002",
            filing_date="2026-06-01",
            transaction_date="2026-05-31",
            owner_name="Jane Insider",
            transaction_code="P",
            acquired_disposed_code="A",
            shares=1000,
            price=None,
            transaction_value=None,
            source_url="https://www.sec.gov/example2.xml",
            as_of_date="2026-06-01",
            effective_date="2026-05-31",
        )
        upsert_insider_transaction_source_snapshot(database_path, missing_price)
        upsert_insider_transaction_source_snapshot(database_path, missing_price)
        stored = list_insider_transaction_source_snapshots(database_path, "AAPL")
        self.assertEqual(len(stored), 2)

    def test_fetch_uses_cik_map_and_skips_etfs(self) -> None:
        database_path = fresh_database_path("phase10f_fetch.sqlite")
        config = make_config(database_path)
        seed_assets(config)
        submissions = {
            "filings": {
                "recent": {
                    "form": ["4"],
                    "accessionNumber": ["0000320193-26-000001"],
                    "filingDate": [date.today().isoformat()],
                    "reportDate": [date.today().isoformat()],
                    "primaryDocument": ["form4.xml"],
                }
            }
        }
        def submissions_for_ticker(config: AppConfig, ticker: str, cik: str, refresh_cache: bool = False) -> dict[str, object]:
            if ticker == "AAPL":
                return submissions
            return {"filings": {"recent": {"form": []}}}

        with patch(
            "target_opportunity_monitor.insider_activity.load_or_fetch_sec_submissions",
            side_effect=submissions_for_ticker,
        ), patch(
            "target_opportunity_monitor.insider_activity.load_or_fetch_form4_document",
            return_value=(form4_xml(date.today().isoformat()), "https://www.sec.gov/form4.xml"),
        ):
            result = fetch_insider_transactions(config)

        self.assertEqual(result.stored_count, 1)
        self.assertIn("AAPL", result.tickers)
        self.assertIn("MSFT:no_recent_form4_filings", result.warnings)
        self.assertIn("SPY:etf_insider_activity_gated", result.warnings)
        self.assertEqual(
            count_rows_by_table(database_path, "insider_transaction_source_snapshots"),
            1,
        )

    def test_fetch_max_tickers_and_cache_flags_are_deterministic(self) -> None:
        database_path = fresh_database_path("phase10f_fetch_flags.sqlite")
        config = make_config(database_path)
        seed_assets(config)
        submissions = {"filings": {"recent": {"form": []}}}
        calls: list[tuple[str, bool]] = []

        def submissions_for_ticker(
            config: AppConfig,
            ticker: str,
            cik: str,
            refresh_cache: bool = False,
        ) -> dict[str, object]:
            calls.append((ticker, refresh_cache))
            return submissions

        with patch(
            "target_opportunity_monitor.insider_activity.load_or_fetch_sec_submissions",
            side_effect=submissions_for_ticker,
        ):
            result = fetch_insider_transactions(config, max_tickers=1, use_cache=True)

        self.assertEqual(calls, [("AAPL", False)])
        self.assertIn("AAPL:no_recent_form4_filings", result.warnings)
        self.assertIn("SPY:etf_insider_activity_gated", result.warnings)

        calls.clear()
        with patch(
            "target_opportunity_monitor.insider_activity.load_or_fetch_sec_submissions",
            side_effect=submissions_for_ticker,
        ):
            fetch_insider_transactions(config, ticker="MSFT", use_cache=False)
        self.assertEqual(calls, [("MSFT", True)])

        calls.clear()
        with patch(
            "target_opportunity_monitor.insider_activity.load_or_fetch_sec_submissions",
            side_effect=submissions_for_ticker,
        ):
            fetch_insider_transactions(config, ticker="MSFT", refresh_cache=True)
        self.assertEqual(calls, [("MSFT", True)])

    def test_form4_fetch_paces_live_requests_and_reuses_cache(self) -> None:
        database_path = fresh_database_path("phase10f_form4_cache.sqlite")
        config = make_config(database_path)
        if config.insider_cache_dir.exists():
            shutil.rmtree(config.insider_cache_dir)
        accession = "0000320193-26-000001"
        with patch(
            "target_opportunity_monitor.insider_activity._sec_request",
            return_value=form4_xml(date.today().isoformat()),
        ) as sec_request, patch(
            "target_opportunity_monitor.insider_activity.time.sleep"
        ) as sleep:
            text, source_url = load_or_fetch_form4_document(
                config,
                "AAPL",
                "0000320193",
                accession,
                "form4.xml",
            )
        self.assertIn("<ownershipDocument>", text)
        self.assertIn(accession.replace("-", ""), source_url)
        self.assertEqual(sec_request.call_count, 1)
        sleep.assert_called_once_with(0.2)

        with patch(
            "target_opportunity_monitor.insider_activity._sec_request",
            side_effect=AssertionError("cached Form 4 should avoid HTTP"),
        ), patch("target_opportunity_monitor.insider_activity.time.sleep") as cached_sleep:
            cached_text, _ = load_or_fetch_form4_document(
                config,
                "AAPL",
                "0000320193",
                accession,
                "form4.xml",
            )
        self.assertIn("<ownershipDocument>", cached_text)
        cached_sleep.assert_not_called()

    def test_same_day_success_parses_cached_documents_without_live_refetch(self) -> None:
        database_path = fresh_database_path("phase10f_same_day_skip.sqlite")
        config = make_config(database_path)
        seed_assets(config)
        today = date.today().isoformat()
        submissions = {
            "filings": {
                "recent": {
                    "form": ["4", "4"],
                    "accessionNumber": [
                        "0000320193-26-000001",
                        "0000320193-26-000002",
                    ],
                    "filingDate": [today, today],
                    "reportDate": [today, today],
                    "primaryDocument": ["form4.xml", "missing.xml"],
                }
            }
        }
        submissions_path = submissions_cache_path(
            config.insider_cache_dir,
            "AAPL",
            "0000320193",
        )
        submissions_path.parent.mkdir(parents=True, exist_ok=True)
        submissions_path.write_text(json.dumps(submissions), encoding="utf-8")
        cached_filing = filing_cache_path(
            config.insider_cache_dir,
            "AAPL",
            "0000320193-26-000001",
        )
        cached_filing.parent.mkdir(parents=True, exist_ok=True)
        cached_filing.write_text(form4_xml(today), encoding="utf-8")
        insert_data_quality_check(
            database_path,
            "insider_activity_fetch:AAPL",
            "ok",
            "insider_activity_fetch_ok",
            source="insider_activity_fetch",
            as_of_date=today,
        )

        with patch(
            "target_opportunity_monitor.insider_activity._sec_request",
            side_effect=AssertionError("same-day cache path should avoid HTTP"),
        ):
            result = fetch_insider_transactions(config, ticker="AAPL")

        self.assertEqual(result.fetched_count, 1)
        self.assertEqual(result.stored_count, 1)
        self.assertIn(
            "AAPL:live_form4_fetch_skipped_same_day_success: 1 filings",
            result.warnings,
        )

    def test_form4_live_budget_and_sec_429_stop_are_compact(self) -> None:
        database_path = fresh_database_path("phase10f_budget_rate.sqlite")
        config = replace(
            make_config(database_path),
            signals_insider_activity_max_live_form4_fetches_per_ticker=1,
        )
        seed_assets(config)
        today = date.today().isoformat()
        submissions = {
            "filings": {
                "recent": {
                    "form": ["4", "4", "4"],
                    "accessionNumber": [
                        "0000320193-26-000001",
                        "0000320193-26-000002",
                        "0000320193-26-000003",
                    ],
                    "filingDate": [today, today, today],
                    "reportDate": [today, today, today],
                    "primaryDocument": ["form4.xml", "form4.xml", "form4.xml"],
                }
            }
        }

        with patch(
            "target_opportunity_monitor.insider_activity.load_or_fetch_sec_submissions",
            return_value=submissions,
        ), patch(
            "target_opportunity_monitor.insider_activity.load_or_fetch_form4_document",
            return_value=(form4_xml(today), "https://www.sec.gov/form4.xml"),
        ) as form4_fetch:
            budget_result = fetch_insider_transactions(config, ticker="AAPL")
        self.assertEqual(form4_fetch.call_count, 1)
        self.assertIn(
            "AAPL:live_form4_fetch_budget_exhausted: 2 filings",
            budget_result.warnings,
        )

        rate_database_path = fresh_database_path("phase10f_rate_limit.sqlite")
        rate_config = replace(
            make_config(rate_database_path),
            signals_insider_activity_max_live_form4_fetches_per_ticker=10,
            signals_insider_activity_sec_rate_limit_cooldown_seconds=0.0,
        )
        seed_assets(rate_config)
        with patch(
            "target_opportunity_monitor.insider_activity.load_or_fetch_sec_submissions",
            return_value=submissions,
        ), patch(
            "target_opportunity_monitor.insider_activity.load_or_fetch_form4_document",
            side_effect=ValueError("HTTP Error 429: Too Many Requests"),
        ) as rate_fetch:
            rate_result = fetch_insider_transactions(rate_config, ticker="AAPL")
        self.assertEqual(rate_fetch.call_count, 1)
        self.assertIn("AAPL:sec_rate_limited: 3 filings affected", rate_result.warnings)
        report = insider_source_status_report(rate_config)
        by_ticker = {status.ticker: status for status in report.statuses}
        self.assertEqual(by_ticker["AAPL"].status, "sec_rate_limited")
        self.assertEqual(report.sec_rate_limited_tickers, ("AAPL",))
        self.assertIn("sec_rate_limited: 3 filings affected", by_ticker["AAPL"].warnings)
        verbose_report = insider_source_status_report(rate_config, verbose=True)
        verbose_status = {status.ticker: status for status in verbose_report.statuses}[
            "AAPL"
        ]
        self.assertTrue(
            any("0000320193-26-000001" in warning for warning in verbose_status.warnings)
        )
        compact_text = build_insider_source_status_text(rate_config)
        verbose_text = build_insider_source_status_text(rate_config, verbose=True)
        self.assertIn("sec_rate_limited: 3 filings affected", compact_text)
        self.assertIn("0000320193-26-000001", verbose_text)

    def test_insider_source_status_reports_coverage_and_warnings(self) -> None:
        database_path = fresh_database_path("phase10f_source_status.sqlite")
        config = make_config(database_path)
        seed_assets(config)
        upsert_asset(config.database_path, Asset(ticker="GOOG", asset_type="equity"))
        upsert_asset(config.database_path, Asset(ticker="NVDA", asset_type="equity"))
        today = date.today()
        stale = today - timedelta(days=30)
        upsert_insider_transaction_source_snapshot(
            database_path,
            InsiderTransactionSourceSnapshot(
                ticker="AAPL",
                cik="0000320193",
                accession_number="fresh",
                filing_date=today.isoformat(),
                transaction_date=today.isoformat(),
                owner_name="Fresh Insider",
                transaction_code="P",
                acquired_disposed_code="A",
                shares=100,
                price=200,
                transaction_value=20_000,
                source_url="https://www.sec.gov/fresh.xml",
                as_of_date=today.isoformat(),
                effective_date=today.isoformat(),
            ),
        )
        upsert_insider_transaction_source_snapshot(
            database_path,
            InsiderTransactionSourceSnapshot(
                ticker="MSFT",
                cik="0000789019",
                accession_number="stale",
                filing_date=stale.isoformat(),
                transaction_date=stale.isoformat(),
                owner_name="Stale Insider",
                transaction_code="S",
                acquired_disposed_code="D",
                shares=100,
                price=300,
                transaction_value=30_000,
                source_url="https://www.sec.gov/stale.xml",
                as_of_date=today.isoformat(),
                effective_date=stale.isoformat(),
            ),
        )
        insert_data_quality_check(
            database_path,
            "insider_activity_fetch:GOOG",
            "warning",
            "no_recent_form4_filings",
            source="insider_activity_fetch",
            as_of_date=today.isoformat(),
        )
        insert_data_quality_check(
            database_path,
            "insider_activity_fetch:NVDA",
            "warning",
            "000000:form4_parse_failed:Malformed Form 4 XML",
            source="insider_activity_fetch",
            as_of_date=today.isoformat(),
        )

        report = insider_source_status_report(config)
        self.assertEqual(report.active_equity_count, 4)
        self.assertEqual(report.source_backed_ticker_count, 2)
        self.assertEqual(report.covered_ticker_count, 3)
        self.assertEqual(report.skipped_etf_tickers, ("SPY",))
        self.assertIn("GOOG", report.no_recent_activity_tickers)
        self.assertIn("NVDA", report.parse_warning_tickers)
        self.assertIn("MSFT", report.stale_source_tickers)
        by_ticker = {status.ticker: status for status in report.statuses}
        self.assertEqual(by_ticker["AAPL"].status, "source_backed")
        self.assertEqual(by_ticker["GOOG"].status, "no_recent_activity")
        self.assertEqual(by_ticker["NVDA"].status, "parse_warning")

    def test_compute_insider_signals_scores_buys_sales_routine_and_etfs(self) -> None:
        database_path = fresh_database_path("phase10f_compute.sqlite")
        config = make_config(database_path)
        seed_assets(config)
        today = date.today().isoformat()
        snapshots = (
            InsiderTransactionSourceSnapshot(
                ticker="AAPL",
                cik="0000320193",
                accession_number="buy",
                filing_date=today,
                transaction_date=today,
                owner_name="Jane Insider",
                transaction_code="P",
                acquired_disposed_code="A",
                shares=1000,
                price=120,
                transaction_value=120_000,
                source_url="https://www.sec.gov/buy.xml",
                as_of_date=today,
                effective_date=today,
            ),
            InsiderTransactionSourceSnapshot(
                ticker="AAPL",
                cik="0000320193",
                accession_number="sale",
                filing_date=today,
                transaction_date=today,
                owner_name="John Insider",
                transaction_code="S",
                acquired_disposed_code="D",
                shares=100,
                price=100,
                transaction_value=10_000,
                source_url="https://www.sec.gov/sale.xml",
                as_of_date=today,
                effective_date=today,
            ),
            InsiderTransactionSourceSnapshot(
                ticker="AAPL",
                cik="0000320193",
                accession_number="routine",
                filing_date=today,
                transaction_date=today,
                owner_name="Routine Insider",
                transaction_code="M",
                acquired_disposed_code="A",
                shares=50,
                price=0,
                transaction_value=0,
                source_url="https://www.sec.gov/routine.xml",
                as_of_date=today,
                effective_date=today,
            ),
        )
        for snapshot in snapshots:
            upsert_insider_transaction_source_snapshot(database_path, snapshot)

        result = compute_insider_signals(config)
        by_ticker = {item.ticker: item for item in result.results}
        self.assertEqual(by_ticker["AAPL"].status, "computed")
        self.assertGreater(by_ticker["AAPL"].composite_score or 0, 50)
        self.assertIn("routine_or_compensation_related", by_ticker["AAPL"].warnings)
        self.assertEqual(by_ticker["MSFT"].composite_score, 50)
        self.assertIn("no_recent_insider_activity", by_ticker["MSFT"].warnings)
        self.assertEqual(by_ticker["SPY"].status, "skipped")
        self.assertIn("etf_insider_activity_gated", by_ticker["SPY"].warnings)
        output_signals = list_signals(database_path, signal_family=SIGNAL_FAMILY)
        self.assertTrue(any(signal.signal_name == COMPOSITE_SIGNAL_NAME for signal in output_signals))
        statuses = {status.ticker: status for status in insider_statuses(config)}
        self.assertEqual(statuses["AAPL"].composite_direction, "positive")

    def test_validate_insider_signals_and_report(self) -> None:
        database_path = fresh_database_path("phase10f_validate.sqlite")
        config = make_config(database_path)
        seed_assets(config)
        start = date.today() - timedelta(days=8)
        snapshot = InsiderTransactionSourceSnapshot(
            ticker="AAPL",
            cik="0000320193",
            accession_number="buy",
            filing_date=start.isoformat(),
            transaction_date=start.isoformat(),
            owner_name="Jane Insider",
            transaction_code="P",
            acquired_disposed_code="A",
            shares=1000,
            price=100,
            transaction_value=100_000,
            source_url="https://www.sec.gov/buy.xml",
            as_of_date=start.isoformat(),
            effective_date=start.isoformat(),
        )
        upsert_insider_transaction_source_snapshot(database_path, snapshot)
        prices = [
            make_price("AAPL", (start + timedelta(days=offset)).isoformat(), 100 + offset)
            for offset in range(0, 8)
        ]
        upsert_prices(database_path, prices)
        compute_insider_signals(config, ticker="AAPL")

        result = validate_insider_signals(config, ticker="AAPL")
        self.assertEqual(result.updated_count, 1)
        outcomes = list_signal_outcomes(
            database_path,
            signal_family=SIGNAL_FAMILY,
            signal_name=COMPOSITE_SIGNAL_NAME,
        )
        self.assertEqual(len(outcomes), 1)
        self.assertIsNotNone(outcomes[0].return_5d)
        self.assertEqual(outcomes[0].hit_status, "hit")
        report = build_insider_validation_report(config)
        self.assertIn("Insider Activity Signal Validation Report", report)
        self.assertIn("Signal outcome rows: 1", report)
        statuses = signal_outcome_statuses(
            database_path,
            signal_family=SIGNAL_FAMILY,
            signal_name=COMPOSITE_SIGNAL_NAME,
        )
        self.assertEqual(statuses[0].ticker, "AAPL")

    def test_cli_report_dashboard_status_and_pipeline_include_insider_activity(self) -> None:
        database_path = fresh_database_path("phase10f_cli.sqlite")
        config = make_config(database_path)
        write_config(config)
        seed_assets(config)
        today = date.today().isoformat()
        upsert_insider_transaction_source_snapshot(
            database_path,
            InsiderTransactionSourceSnapshot(
                ticker="AAPL",
                cik="0000320193",
                accession_number="buy",
                filing_date=today,
                transaction_date=today,
                owner_name="Jane Insider",
                transaction_code="P",
                acquired_disposed_code="A",
                shares=1000,
                price=120,
                transaction_value=120_000,
                source_url="https://www.sec.gov/buy.xml",
                as_of_date=today,
                effective_date=today,
            ),
        )
        upsert_prices(database_path, [make_price("AAPL", today, 120)])

        with redirect_stdout(io.StringIO()) as output:
            fetch_exit = command_fetch_insider_transactions(
                Namespace(config=config.config_path, ticker="SPY", refresh_cache=False)
            )
            compute_exit = command_compute_insider_signals(
                Namespace(config=config.config_path, ticker="AAPL")
            )
            source_status_exit = command_insider_source_status(
                Namespace(config=config.config_path)
            )
            verbose_source_status_exit = command_insider_source_status(
                Namespace(config=config.config_path, verbose=True)
            )
            status_exit = command_insider_status(Namespace(config=config.config_path))
            validate_exit = command_validate_insider_signals(
                Namespace(config=config.config_path, ticker="AAPL")
            )
            report_exit = command_insider_validation_report(Namespace(config=config.config_path))
            global_status_exit = command_status(Namespace(config=config.config_path))

        stdout = output.getvalue()
        self.assertEqual(fetch_exit, 0)
        self.assertEqual(compute_exit, 0)
        self.assertEqual(source_status_exit, 0)
        self.assertEqual(verbose_source_status_exit, 0)
        self.assertEqual(status_exit, 0)
        self.assertEqual(validate_exit, 0)
        self.assertEqual(report_exit, 0)
        self.assertEqual(global_status_exit, 0)
        self.assertIn("etf_insider_activity_gated", stdout)
        self.assertIn("Insider activity signal computation complete", stdout)
        self.assertIn("Insider activity source status", stdout)
        self.assertIn("Active equity coverage:", stdout)
        self.assertIn("Insider activity source coverage:", stdout)
        self.assertIn("Insider Activity Signal Validation Report", stdout)
        self.assertIn("Insider activity source rows", stdout)
        self.assertIn("Insider activity SEC-rate-limited tickers:", stdout)

        daily = write_daily_report(config)
        markdown = daily.path.read_text(encoding="utf-8")
        csv_text = daily.csv_path.read_text(encoding="utf-8") if daily.csv_path else ""
        self.assertIn("Insider activity signal coverage", markdown)
        self.assertIn("Insider activity source coverage", markdown)
        self.assertIn("insider_activity_score", csv_text)
        self.assertIn("insider_activity_source_status", csv_text)
        dashboard = build_dashboard(config)
        html = dashboard.path.read_text(encoding="utf-8")
        match = re.search(
            r'<script id="tom-dashboard-data" type="application/json">(.*?)</script>',
            html,
            flags=re.S,
        )
        self.assertIsNotNone(match)
        data = json.loads(match.group(1))
        self.assertIn("insider_activity_score", data["rows"][0])
        self.assertIn("insider_activity_source_status", data["rows"][0])
        self.assertIn("insider_activity_source_rows", data["health"])
        self.assertIn("insider_activity_source_covered_ticker_count", data["health"])
        self.assertIn("insider_activity_sec_rate_limited_ticker_count", data["health"])

        with patch_refresh_pipeline_for_test(
            _insider_fetch_step=(1, ()),
            _insider_signal_step=(1, ()),
            _insider_validation_step=(1, ()),
            _readiness_step=(1, ()),
        ):
            result = run_refresh_data(config)
        step_names = [step.step_name for step in result.steps]
        self.assertIn("fetch-insider-transactions", step_names)
        self.assertIn("compute-insider-signals", step_names)
        self.assertIn("validate-insider-signals", step_names)


if __name__ == "__main__":
    unittest.main()
