from __future__ import annotations

from argparse import Namespace
from contextlib import redirect_stdout
from datetime import date, timedelta
from pathlib import Path
import csv
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
    command_aggregate_news_catalyst_sources,
    command_compute_news_catalyst_signals,
    command_compute_news_catalyst_text_backfill,
    command_export_news_catalyst_provider_backfill,
    command_apply_news_catalyst_provider_backfill,
    command_fetch_news_catalyst_sources,
    command_import_news_catalyst_source_exports,
    command_load_news_catalysts,
    command_news_catalyst_coverage_plan,
    command_news_catalyst_provider_backfill_status,
    command_news_catalyst_provider_upgrade_status,
    command_news_catalyst_source_status,
    command_news_catalyst_status,
    command_news_catalyst_validation_report,
    command_normalize_news_catalyst_provider_export,
    command_preview_news_catalyst_provider_upgrade,
    command_status,
    command_test_news_catalyst_provider,
    command_validate_news_catalyst_provider_backfill,
    command_validate_news_catalyst_signals,
)
from target_opportunity_monitor.news_catalyst_sources import (
    NewsCatalystProviderFetchResult,
    SOURCE_EXPORT_HEADERS,
    aggregate_news_catalyst_sources,
    apply_news_catalyst_provider_backfill,
    build_news_catalyst_provider_backfill_status_text,
    build_news_catalyst_provider_backfill_diagnostics_text,
    build_news_catalyst_provider_upgrade_status_text,
    build_news_catalyst_coverage_plan_text,
    compute_news_catalyst_text_backfill,
    ensure_news_catalyst_source_export_header,
    export_news_catalyst_provider_backfill,
    fetch_news_catalyst_sources,
    import_news_catalyst_source_exports,
    news_catalyst_coverage_plan,
    news_catalyst_coverage_queue_path,
    news_catalyst_provider_backfill_apply_status,
    news_catalyst_provider_backfill_diagnostics,
    normalize_news_catalyst_provider_export,
    preview_news_catalyst_provider_upgrade,
    news_catalyst_provider_upgrade_status,
    news_catalyst_source_status_report,
    parse_news_catalyst_source_export_csv,
    test_news_catalyst_provider,
    validate_news_catalyst_provider_backfill,
    write_news_catalyst_coverage_template,
)
from target_opportunity_monitor.config import AppConfig, load_config
from target_opportunity_monitor.dashboard import build_dashboard
from target_opportunity_monitor.db import initialize_database
from target_opportunity_monitor.news_catalysts import (
    NEWS_CATALYST_HEADERS,
    compute_news_catalyst_signals,
    ensure_news_catalyst_csv_header,
    load_news_catalysts_csv,
    news_catalyst_statuses,
    parse_news_catalysts_csv,
)
from target_opportunity_monitor.pipeline import run_refresh_data
from target_opportunity_monitor.reporting import write_daily_report
from target_opportunity_monitor.scoring import compute_scores
from target_opportunity_monitor.signal_validation import (
    build_news_catalyst_validation_report,
    validate_news_catalyst_signals,
)
from target_opportunity_monitor.storage import (
    Asset,
    Estimate,
    Fundamental,
    Price,
    PriceFeature,
    Target,
    count_rows_by_table,
    list_alerts,
    list_prices,
    list_signals,
    list_signal_outcomes,
    list_scores,
    list_news_catalyst_aggregates,
    list_news_catalyst_source_snapshots,
    signal_outcome_statuses,
    upsert_asset,
    upsert_estimate,
    upsert_fundamental,
    upsert_price_feature,
    upsert_prices,
    upsert_target,
)


def fresh_database_path(name: str) -> Path:
    TEST_TMP_ROOT.mkdir(exist_ok=True)
    path = TEST_TMP_ROOT / name
    if path.exists():
        path.unlink()
    for directory in (
        TEST_TMP_ROOT / "signals" / "source_exports" / path.stem,
        TEST_TMP_ROOT / "signals" / "cache" / path.stem,
    ):
        if directory.exists():
            shutil.rmtree(directory)
    for file_path in (
        TEST_TMP_ROOT / "signals" / f"{path.stem}.csv",
        TEST_TMP_ROOT / f"phase10e_{path.stem}.toml",
    ):
        if file_path.exists():
            file_path.unlink()
    return path


def make_config(database_path: Path, news_shadow_mode: bool = True) -> AppConfig:
    return AppConfig(
        project_root=TEST_TMP_ROOT,
        config_path=TEST_TMP_ROOT / f"phase10e_{database_path.stem}.toml",
        database_path=database_path,
        reports_dir=TEST_TMP_ROOT / "reports_phase10e",
        watchlist_path=TEST_TMP_ROOT / "watchlist_phase10e.csv",
        market_data_dir=TEST_TMP_ROOT / "market_data_phase10e",
        manual_prices_dir=TEST_TMP_ROOT / "market_data_phase10e" / "manual",
        market_data_primary_source="stooq",
        market_data_secondary_source="yahoo_chart",
        market_data_mode="csv",
        market_data_lookback_days=800,
        market_data_stale_after_days=7,
        market_data_minimum_history_days=252,
        universe_mode="manual_watchlist",
        run_mode="daily_scoring",
        report_title="Target Opportunity Monitor Daily Report",
        news_catalysts_path=TEST_TMP_ROOT / "signals" / f"{database_path.stem}.csv",
        news_catalyst_source_exports_dir=(
            TEST_TMP_ROOT / "signals" / "source_exports" / database_path.stem
        ),
        news_catalyst_cache_dir=TEST_TMP_ROOT / "signals" / "cache" / database_path.stem,
        signals_news_catalyst_model_version="news_catalyst_mvp_v1",
        signals_news_catalyst_shadow_mode=news_shadow_mode,
        signals_news_catalyst_stale_after_days=30,
        signals_news_catalyst_provider_order=(
            "alpha_vantage",
            "marketaux",
            "eodhd",
            "finnhub",
            "fmp",
            "x_recent_search",
            "truth_social_public",
            "source_export",
        ),
        signals_news_catalyst_enabled_providers=(
            "alpha_vantage",
            "marketaux",
            "eodhd",
            "finnhub",
            "fmp",
            "x_recent_search",
            "truth_social_public",
            "source_export",
        ),
        signals_news_catalyst_text_backfill_enabled=True,
        signals_news_catalyst_text_backfill_model_version="news_text_lexicon_mvp_v1",
        signals_news_catalyst_min_numeric_coverage=13,
        signals_news_catalyst_social_accounts=("KobeissiLetter",),
        signals_news_catalyst_manual_influencer_sources=("serenity", "kobeissi_letter"),
        signals_news_catalyst_source_policy="weighted_median",
        signals_news_catalyst_lookback_days=14,
        signals_news_catalyst_max_items_per_ticker=5,
        signals_news_catalyst_disagreement_warning_threshold=15.0,
        signals_news_catalyst_high_disagreement_threshold=30.0,
        signals_news_catalyst_min_sources_for_aggregate=1,
        signals_news_catalyst_provider_request_budget=3,
        signals_news_catalyst_provider_retry_delay_seconds=0.0,
        signals_news_catalyst_cache_stale_hours=24,
        signals_news_catalyst_use_cache=True,
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
                f'news_catalysts = "{config.news_catalysts_path.as_posix()}"',
                (
                    "news_catalyst_source_exports_dir = "
                    f'"{config.news_catalyst_source_exports_dir.as_posix()}"'
                ),
                f'news_catalyst_cache = "{config.news_catalyst_cache_dir.as_posix()}"',
                "",
                "[signals]",
                (
                    'news_catalyst_model_version = '
                    f'"{config.signals_news_catalyst_model_version}"'
                ),
                (
                    "news_catalyst_shadow_mode = "
                    f"{str(config.signals_news_catalyst_shadow_mode).lower()}"
                ),
                (
                    "news_catalyst_stale_after_days = "
                    f"{config.signals_news_catalyst_stale_after_days}"
                ),
                (
                    "news_catalyst_provider_order = "
                    '["alpha_vantage", "marketaux", "eodhd", "finnhub", "fmp", "x_recent_search", "truth_social_public", "source_export"]'
                ),
                (
                    "news_catalyst_enabled_providers = "
                    '["alpha_vantage", "marketaux", "eodhd", "finnhub", "fmp", "x_recent_search", "truth_social_public", "source_export"]'
                ),
                "news_catalyst_text_backfill_enabled = true",
                'news_catalyst_text_backfill_model_version = "news_text_lexicon_mvp_v1"',
                "news_catalyst_min_numeric_coverage = 13",
                'news_catalyst_social_accounts = ["KobeissiLetter"]',
                'news_catalyst_manual_influencer_sources = ["serenity", "kobeissi_letter"]',
                'news_catalyst_source_policy = "weighted_median"',
                f"news_catalyst_lookback_days = {config.signals_news_catalyst_lookback_days}",
                (
                    "news_catalyst_max_items_per_ticker = "
                    f"{config.signals_news_catalyst_max_items_per_ticker}"
                ),
                (
                    "news_catalyst_disagreement_warning_threshold = "
                    f"{config.signals_news_catalyst_disagreement_warning_threshold}"
                ),
                (
                    "news_catalyst_high_disagreement_threshold = "
                    f"{config.signals_news_catalyst_high_disagreement_threshold}"
                ),
                (
                    "news_catalyst_min_sources_for_aggregate = "
                    f"{config.signals_news_catalyst_min_sources_for_aggregate}"
                ),
                (
                    "news_catalyst_provider_request_budget = "
                    f"{config.signals_news_catalyst_provider_request_budget}"
                ),
                (
                    "news_catalyst_provider_retry_delay_seconds = "
                    f"{config.signals_news_catalyst_provider_retry_delay_seconds}"
                ),
                (
                    "news_catalyst_cache_stale_hours = "
                    f"{config.signals_news_catalyst_cache_stale_hours}"
                ),
                (
                    "news_catalyst_use_cache = "
                    f"{str(config.signals_news_catalyst_use_cache).lower()}"
                ),
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


def write_news_csv(config: AppConfig, rows: list[str]) -> None:
    config.news_catalysts_path.parent.mkdir(parents=True, exist_ok=True)
    config.news_catalysts_path.write_text(
        "\n".join([",".join(NEWS_CATALYST_HEADERS), *rows, ""]),
        encoding="utf-8",
    )


def news_row(**values: object) -> str:
    row = {header: "" for header in NEWS_CATALYST_HEADERS}
    row.update({key: str(value) for key, value in values.items() if value is not None})
    return ",".join(row[header] for header in NEWS_CATALYST_HEADERS)


def source_export_row(**values: object) -> str:
    row = {header: "" for header in SOURCE_EXPORT_HEADERS}
    row.update({key: str(value) for key, value in values.items() if value is not None})
    return ",".join(row[header] for header in SOURCE_EXPORT_HEADERS)


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


def seed_price_history(
    database_path: Path,
    ticker: str,
    start_date: date,
    closes: list[float],
) -> None:
    upsert_prices(
        database_path,
        [
            make_price(ticker, (start_date + timedelta(days=offset)).isoformat(), close)
            for offset, close in enumerate(closes)
        ],
    )


def seed_equity_scoring_fixture(database_path: Path, ticker: str = "AAPL") -> None:
    today = date.today().isoformat()
    initialize_database(database_path)
    upsert_asset(database_path, Asset(ticker=ticker, asset_type="equity"))
    upsert_price_feature(
        database_path,
        PriceFeature(
            ticker=ticker,
            feature_date=today,
            current_price=100,
            return_1d=0.01,
            return_1m=0.05,
            return_3m=0.10,
            return_6m=0.15,
            return_12m=0.20,
            realized_volatility_20d=0.20,
            realized_volatility_60d=0.25,
            average_dollar_volume_20d=1_000_000_000,
            latest_price_date=today,
        ),
    )
    for fiscal_year, revenue, net_income, fcf, eps in (
        (2024, 900, 90, 80, 4.0),
        (2025, 1000, 120, 100, 5.0),
    ):
        upsert_fundamental(
            database_path,
            Fundamental(
                ticker=ticker,
                fiscal_period_end=f"{fiscal_year}-12-31",
                fiscal_period="FY",
                report_type="annual",
                revenue=revenue,
                operating_income=150,
                ebitda=180,
                net_income=net_income,
                diluted_eps=eps,
                free_cash_flow=fcf,
                net_debt=100,
                total_equity=500,
                shares_outstanding=100,
            ),
        )
    upsert_estimate(
        database_path,
        Estimate(
            ticker=ticker,
            estimate_date=today,
            fiscal_period_end="2026-12-31",
            metric="eps",
            consensus_mean=6.0,
        ),
    )
    upsert_target(
        database_path,
        Target(
            ticker=ticker,
            target_date=today,
            base_target=130,
            target_low=95,
            target_high=150,
            valuation_gap=0.30,
            target_method="fixture",
            uncertainty_band=0.25,
            valuation_confidence=75,
            method_count=6,
            model_version="valuation_mvp_v1",
        ),
    )


def dashboard_data(html: str) -> dict[str, object]:
    match = re.search(
        r'<script id="tom-dashboard-data" type="application/json">(.*?)</script>',
        html,
        flags=re.DOTALL,
    )
    if not match:
        raise AssertionError("Dashboard data script not found.")
    return json.loads(match.group(1))


class Phase10ENewsCatalystTests(unittest.TestCase):
    def test_config_defaults_and_header_creation(self) -> None:
        config = load_config()
        self.assertEqual(
            config.news_catalysts_path,
            PROJECT_ROOT / "data" / "signals" / "manual" / "news_catalysts.csv",
        )
        self.assertEqual(config.signals_news_catalyst_model_version, "news_catalyst_mvp_v1")
        self.assertTrue(config.signals_news_catalyst_shadow_mode)
        self.assertEqual(config.signals_news_catalyst_stale_after_days, 30)
        self.assertEqual(
            config.news_catalyst_source_exports_dir,
            PROJECT_ROOT / "data" / "signals" / "source_exports" / "news_catalysts",
        )
        self.assertEqual(
            config.news_catalyst_cache_dir,
            PROJECT_ROOT / "data" / "signals" / "cache" / "news_catalysts",
        )
        self.assertEqual(
            config.signals_news_catalyst_provider_order,
            (
                "alpha_vantage",
                "marketaux",
                "eodhd",
                "finnhub",
                "fmp",
                "x_recent_search",
                "truth_social_public",
                "source_export",
            ),
        )
        self.assertTrue(config.signals_news_catalyst_text_backfill_enabled)
        self.assertEqual(
            config.signals_news_catalyst_text_backfill_model_version,
            "news_text_lexicon_mvp_v1",
        )
        self.assertEqual(config.signals_news_catalyst_min_numeric_coverage, 13)
        self.assertEqual(config.signals_news_catalyst_social_accounts, ("KobeissiLetter",))
        self.assertEqual(
            config.signals_news_catalyst_manual_influencer_sources,
            ("serenity", "kobeissi_letter"),
        )
        self.assertEqual(config.signals_news_catalyst_source_policy, "weighted_median")
        self.assertEqual(config.signals_news_catalyst_provider_request_budget, 3)
        self.assertEqual(config.signals_news_catalyst_cache_stale_hours, 24)
        self.assertTrue(config.signals_news_catalyst_use_cache)

        database_path = fresh_database_path("phase10e_header.sqlite")
        test_config = make_config(database_path)
        ensure_news_catalyst_csv_header(test_config.news_catalysts_path)
        ensure_news_catalyst_csv_header(test_config.news_catalysts_path)

        text = test_config.news_catalysts_path.read_text(encoding="utf-8")
        self.assertTrue(text.startswith("ticker,signal_date,source"))
        self.assertIn("headline_or_event", text)
        ensure_news_catalyst_source_export_header(
            test_config.news_catalyst_source_exports_dir / "manual.csv"
        )
        source_text = (
            test_config.news_catalyst_source_exports_dir / "manual.csv"
        ).read_text(encoding="utf-8")
        self.assertTrue(source_text.startswith("ticker,signal_date,source"))

    def test_source_tables_are_initialized(self) -> None:
        database_path = fresh_database_path("phase10e_source_schema.sqlite")
        status = initialize_database(database_path)

        self.assertIn("news_catalyst_source_snapshots", status.existing_tables)
        self.assertIn("news_catalyst_aggregates", status.existing_tables)

    def test_parser_accepts_valid_rows_and_rejects_bad_rows(self) -> None:
        parsed = parse_news_catalysts_csv(
            "\n".join(
                [
                    ",".join(NEWS_CATALYST_HEADERS),
                    news_row(
                        ticker="aapl",
                        signal_date="2026-06-08",
                        source="manual_capture",
                        source_url="https://example.com/aapl-news",
                        headline_or_event="Product launch confirmed",
                        event_date="2026-06-15",
                        sentiment_score=75,
                        catalyst_score=80,
                        urgency_score=70,
                        confidence=85,
                        topic="product",
                        notes="Source-backed row.",
                    ),
                    "",
                ]
            )
        )
        self.assertEqual(parsed[0].ticker, "AAPL")
        self.assertEqual(parsed[0].sentiment_score, 75)
        self.assertEqual(parsed[0].source_url, "https://example.com/aapl-news")

        bad_rows = [
            "ticker,signal_date,source,source_url\nAAPL,2026-06-08,manual,https://example.com\n",
            ",".join(NEWS_CATALYST_HEADERS)
            + "\nAAPL,not-a-date,manual,https://example.com,Headline,,,,,,,,,\n",
            ",".join(NEWS_CATALYST_HEADERS)
            + "\nAAPL,2026-06-08,manual,,Headline,,,,,,,,,\n",
            ",".join(NEWS_CATALYST_HEADERS)
            + "\nAAPL,2026-06-08,manual,https://example.com,,,,,,,,,,\n",
            ",".join(NEWS_CATALYST_HEADERS)
            + "\nAAPL,2026-06-08,manual,https://example.com,Headline,,bad,,,,,,,\n",
            ",".join(NEWS_CATALYST_HEADERS)
            + "\nAAPL,2026-06-08,manual,https://example.com,Headline,,101,,,,,,,\n",
        ]
        for text in bad_rows:
            with self.assertRaises(ValueError):
                parse_news_catalysts_csv(text)

    def test_source_export_import_and_aggregation_are_idempotent(self) -> None:
        database_path = fresh_database_path("phase10e_source_aggregate.sqlite")
        config = make_config(database_path)
        initialize_database(database_path)
        for ticker, asset_type in (("AAPL", "equity"), ("MSFT", "equity"), ("SPY", "etf")):
            upsert_asset(database_path, Asset(ticker=ticker, asset_type=asset_type))
        source_path = config.news_catalyst_source_exports_dir / "manual.csv"
        source_path.parent.mkdir(parents=True, exist_ok=True)
        today = date.today().isoformat()
        source_path.write_text(
            "\n".join(
                [
                    ",".join(SOURCE_EXPORT_HEADERS),
                    source_export_row(
                        ticker="AAPL",
                        signal_date=today,
                        source="alpha_vantage",
                        source_url="https://example.com/aapl/1",
                        headline_or_event="AAPL AI catalyst one",
                        sentiment_score=80,
                        catalyst_score=70,
                        relevance_score=90,
                        confidence=85,
                    ),
                    source_export_row(
                        ticker="AAPL",
                        signal_date=today,
                        source="fmp",
                        source_url="https://example.com/aapl/2",
                        headline_or_event="AAPL AI catalyst two",
                        sentiment_score=60,
                        catalyst_score=65,
                        relevance_score=75,
                        confidence=70,
                    ),
                    source_export_row(
                        ticker="MSFT",
                        signal_date=today,
                        source="finnhub",
                        source_url="https://example.com/msft/1",
                        headline_or_event="MSFT headline only",
                    ),
                    source_export_row(
                        ticker="SPY",
                        signal_date=today,
                        source="alpha_vantage",
                        source_url="https://example.com/spy/1",
                        headline_or_event="SPY macro headline",
                        sentiment_score=55,
                    ),
                    "",
                ]
            ),
            encoding="utf-8",
        )

        parsed = parse_news_catalyst_source_export_csv(
            source_path.read_text(encoding="utf-8")
        )
        first_import = import_news_catalyst_source_exports(config, directory=source_path.parent)
        second_import = import_news_catalyst_source_exports(config, directory=source_path.parent)
        aggregate_result = aggregate_news_catalyst_sources(config)
        snapshots = list_news_catalyst_source_snapshots(database_path, "AAPL")
        aggregates = list_news_catalyst_aggregates(database_path, "AAPL")
        final_text = config.news_catalysts_path.read_text(encoding="utf-8")

        self.assertEqual(len(parsed), 4)
        self.assertEqual(first_import.imported_count, second_import.imported_count)
        self.assertEqual(len(snapshots), 2)
        self.assertEqual(aggregate_result.aggregate_count, 1)
        self.assertEqual(len(aggregates), 1)
        self.assertEqual(aggregates[0].sentiment_score, 80)
        self.assertIn("source_disagreement_medium", aggregates[0].data_warnings or "")
        self.assertIn("SPY:etf_or_non_equity_news_catalyst_gated", aggregate_result.warnings)
        self.assertIn("news_catalyst_aggregate", final_text)
        self.assertIn("AAPL", final_text)
        self.assertNotIn("SPY,", final_text)

        load_result = load_news_catalysts_csv(config)
        signal_result = compute_news_catalyst_signals(config, ticker="AAPL")
        status = news_catalyst_source_status_report(config)

        self.assertGreater(load_result.input_signal_count, 0)
        self.assertEqual(signal_result.computed_count, 1)
        self.assertEqual(status.source_backed_ticker_count, 1)
        self.assertIn("MSFT", status.missing_source_tickers)

    def test_source_export_rejects_bad_rows_and_preserves_headline_only_warning(self) -> None:
        valid_header = ",".join(SOURCE_EXPORT_HEADERS)
        bad_rows = [
            "ticker,signal_date,source,source_url\nAAPL,2026-06-08,manual,https://example.com\n",
            valid_header + "\nAAPL,bad,manual,https://example.com,Headline,,,,,,,,,,\n",
            valid_header + "\nAAPL,2026-06-08,manual,,Headline,,,,,,,,,,\n",
            valid_header + "\nAAPL,2026-06-08,manual,https://example.com,,,,,,,,,,,\n",
            valid_header + "\nAAPL,2026-06-08,manual,https://example.com,Headline,,,,,bad,,,,,\n",
        ]
        for text in bad_rows:
            with self.assertRaises(ValueError):
                parse_news_catalyst_source_export_csv(text)

        database_path = fresh_database_path("phase10e_headline_only.sqlite")
        config = make_config(database_path)
        initialize_database(database_path)
        upsert_asset(database_path, Asset(ticker="AAPL", asset_type="equity"))
        source_path = config.news_catalyst_source_exports_dir / "manual.csv"
        source_path.parent.mkdir(parents=True, exist_ok=True)
        source_path.write_text(
            "\n".join(
                [
                    valid_header,
                    source_export_row(
                        ticker="AAPL",
                        signal_date=date.today().isoformat(),
                        source="provider_export",
                        source_url="https://example.com/aapl",
                        headline_or_event="Headline only but source-backed",
                    ),
                    "",
                ]
            ),
            encoding="utf-8",
        )

        import_result = import_news_catalyst_source_exports(config, directory=source_path.parent)
        aggregate_result = aggregate_news_catalyst_sources(config)
        snapshot = list_news_catalyst_source_snapshots(database_path, "AAPL")[0]

        self.assertEqual(import_result.imported_count, 1)
        self.assertIn("headline_only_source", snapshot.data_warnings or "")
        self.assertEqual(aggregate_result.aggregate_count, 0)
        self.assertIn("AAPL:no_aggregatable_news_catalyst_fields", aggregate_result.warnings)

    def test_coverage_plan_prioritizes_missing_excludes_etfs_and_writes_template(self) -> None:
        database_path = fresh_database_path("phase10e_coverage_plan.sqlite")
        config = make_config(database_path)
        write_config(config)
        initialize_database(database_path)
        for ticker, asset_type in (
            ("AAPL", "equity"),
            ("MSFT", "equity"),
            ("NVDA", "equity"),
            ("SPY", "etf"),
        ):
            upsert_asset(database_path, Asset(ticker=ticker, asset_type=asset_type))
        source_path = config.news_catalyst_source_exports_dir / "manual.csv"
        source_path.parent.mkdir(parents=True, exist_ok=True)
        today = date.today().isoformat()
        stale_date = (date.today() - timedelta(days=45)).isoformat()
        source_path.write_text(
            "\n".join(
                [
                    ",".join(SOURCE_EXPORT_HEADERS),
                    source_export_row(
                        ticker="AAPL",
                        signal_date=today,
                        source="alpha_vantage",
                        source_url="https://example.com/aapl",
                        headline_or_event="AAPL numeric catalyst",
                        sentiment_score=75,
                    ),
                    source_export_row(
                        ticker="MSFT",
                        signal_date=stale_date,
                        source="alpha_vantage",
                        source_url="https://example.com/msft",
                        headline_or_event="MSFT stale catalyst",
                        sentiment_score=65,
                    ),
                    source_export_row(
                        ticker="NVDA",
                        signal_date=today,
                        source="finnhub",
                        source_url="https://example.com/nvda",
                        headline_or_event="NVDA headline only",
                    ),
                    source_export_row(
                        ticker="SPY",
                        signal_date=today,
                        source="alpha_vantage",
                        source_url="https://example.com/spy",
                        headline_or_event="ETF informational row",
                        sentiment_score=55,
                    ),
                    "",
                ]
            ),
            encoding="utf-8",
        )
        import_news_catalyst_source_exports(config, directory=source_path.parent)
        aggregate_news_catalyst_sources(config)

        stale_queue_path = news_catalyst_coverage_queue_path(config)
        stale_queue_path.parent.mkdir(parents=True, exist_ok=True)
        stale_queue_path.write_text(
            "\n".join(
                [
                    ",".join(SOURCE_EXPORT_HEADERS),
                    source_export_row(
                        ticker="AAPL",
                        signal_date=today,
                        source="provider_export",
                        notes="coverage_queue:stale_fixture",
                    ),
                    source_export_row(
                        ticker="GOOG",
                        signal_date=today,
                        source="provider_export",
                        notes="coverage_queue:stale_fixture",
                    ),
                    "",
                ]
            ),
            encoding="utf-8",
        )
        stale_plan = news_catalyst_coverage_plan(config, max_tickers=2, write_template=False)
        plan = news_catalyst_coverage_plan(config, max_tickers=2)
        queue_path = news_catalyst_coverage_queue_path(config)
        queue_text = queue_path.read_text(encoding="utf-8")
        missing_only_text = build_news_catalyst_coverage_plan_text(config, max_tickers=2)
        status_output = io.StringIO()
        with redirect_stdout(status_output):
            source_status_exit = command_news_catalyst_source_status(
                Namespace(
                    config=config.config_path,
                    missing_only=True,
                    provider_warnings=False,
                )
            )
        provider_output = io.StringIO()
        with redirect_stdout(provider_output):
            provider_status_exit = command_news_catalyst_source_status(
                Namespace(
                    config=config.config_path,
                    missing_only=False,
                    provider_warnings=True,
                )
            )
        coverage_output = io.StringIO()
        with redirect_stdout(coverage_output):
            coverage_exit = command_news_catalyst_coverage_plan(
                Namespace(config=config.config_path, max_tickers=2)
        )

        self.assertTrue(stale_plan.queue_template_stale)
        self.assertTrue(stale_plan.missing_queue_template_stale)
        self.assertIn("stale_news_catalyst_missing_queue_template", stale_plan.warnings)
        self.assertEqual(stale_plan.queue_template_tickers, ("AAPL", "GOOG"))
        self.assertEqual(plan.planned_tickers, ("NVDA", "MSFT"))
        self.assertFalse(plan.queue_template_stale)
        self.assertFalse(plan.missing_queue_template_stale)
        self.assertEqual([item.priority for item in plan.items], [1, 3])
        self.assertIn("NVDA", queue_text)
        self.assertIn("MSFT", queue_text)
        self.assertNotIn("SPY", queue_text)
        self.assertIn("coverage_queue:missing_numeric_news_catalyst_row", queue_text)
        self.assertEqual(parse_news_catalyst_source_export_csv(queue_text), [])
        self.assertIn("Planned tickers: NVDA, MSFT", missing_only_text)
        self.assertEqual(source_status_exit, 0)
        self.assertIn("NVDA | equity | False", status_output.getvalue())
        self.assertNotIn("AAPL | equity | True", status_output.getvalue())
        self.assertEqual(provider_status_exit, 0)
        self.assertIn("finnhub:headline_only", provider_output.getvalue())
        self.assertEqual(coverage_exit, 0)
        self.assertIn("News/Catalyst Coverage Plan", coverage_output.getvalue())
        self.assertIn("Coverage queue template", coverage_output.getvalue())

    def test_coverage_plan_modes_split_missing_and_provider_upgrade(self) -> None:
        database_path = fresh_database_path("phase10e_coverage_modes.sqlite")
        config = make_config(database_path)
        write_config(config)
        initialize_database(database_path)
        for ticker in ("AAPL", "MSFT", "NVDA"):
            upsert_asset(database_path, Asset(ticker=ticker, asset_type="equity"))
        source_path = config.news_catalyst_source_exports_dir / "manual.csv"
        source_path.parent.mkdir(parents=True, exist_ok=True)
        today = date.today().isoformat()
        source_path.write_text(
            "\n".join(
                [
                    ",".join(SOURCE_EXPORT_HEADERS),
                    source_export_row(
                        ticker="AAPL",
                        signal_date=today,
                        source="alpha_vantage",
                        source_url="https://example.com/aapl",
                        headline_or_event="AAPL provider numeric catalyst",
                        sentiment_score=75,
                    ),
                    source_export_row(
                        ticker="MSFT",
                        signal_date=today,
                        source="finnhub",
                        source_url="https://example.com/msft",
                        headline_or_event="MSFT upgrade catalyst gains",
                    ),
                    "",
                ]
            ),
            encoding="utf-8",
        )
        import_news_catalyst_source_exports(config, directory=source_path.parent)
        aggregate_news_catalyst_sources(config)
        compute_news_catalyst_text_backfill(config)
        aggregate_news_catalyst_sources(config)

        missing_plan = news_catalyst_coverage_plan(
            config, max_tickers=5, mode="missing"
        )
        provider_plan = news_catalyst_coverage_plan(
            config, max_tickers=5, mode="provider-upgrade"
        )
        all_plan = news_catalyst_coverage_plan(config, max_tickers=5, mode="all")
        status_text = build_news_catalyst_coverage_plan_text(
            config, max_tickers=5, mode="provider-upgrade"
        )
        source_status_output = io.StringIO()
        with redirect_stdout(source_status_output):
            source_status_exit = command_news_catalyst_source_status(
                Namespace(
                    config=config.config_path,
                    missing_only=False,
                    provider_warnings=False,
                    provider_upgrade_only=True,
                )
            )

        self.assertEqual(missing_plan.planned_tickers, ("NVDA",))
        self.assertEqual(missing_plan.missing_numeric_tickers, ("NVDA",))
        self.assertFalse(missing_plan.missing_queue_template_stale)
        self.assertEqual(provider_plan.planned_tickers, ("MSFT",))
        self.assertEqual(provider_plan.provider_native_upgrade_tickers, ("MSFT",))
        self.assertFalse(provider_plan.provider_upgrade_queue_template_stale)
        self.assertEqual(all_plan.planned_tickers, ("NVDA", "MSFT"))
        self.assertEqual([item.coverage_status for item in all_plan.items], [
            "missing_numeric",
            "provider_upgrade",
        ])
        missing_queue_text = news_catalyst_coverage_queue_path(
            config, mode="missing"
        ).read_text(encoding="utf-8")
        provider_queue_text = news_catalyst_coverage_queue_path(
            config, mode="provider-upgrade"
        ).read_text(encoding="utf-8")
        self.assertIn("NVDA", missing_queue_text)
        self.assertNotIn("MSFT", missing_queue_text)
        self.assertIn("MSFT", provider_queue_text)
        self.assertNotIn("AAPL", provider_queue_text)
        self.assertIn("Mode: provider-upgrade", status_text)
        self.assertIn("Provider-native upgrade tickers: MSFT", status_text)
        self.assertEqual(source_status_exit, 0)
        self.assertIn("MSFT | equity | True", source_status_output.getvalue())
        self.assertNotIn("AAPL | equity", source_status_output.getvalue())

    def test_provider_upgrade_status_alias_and_export_validation(self) -> None:
        database_path = fresh_database_path("phase10e_provider_upgrade_status.sqlite")
        config = make_config(database_path)
        write_config(config)
        initialize_database(database_path)
        for ticker in ("AAPL", "MSFT"):
            upsert_asset(database_path, Asset(ticker=ticker, asset_type="equity"))
        source_path = config.news_catalyst_source_exports_dir / "manual.csv"
        source_path.parent.mkdir(parents=True, exist_ok=True)
        today = date.today().isoformat()
        source_path.write_text(
            "\n".join(
                [
                    ",".join(SOURCE_EXPORT_HEADERS),
                    source_export_row(
                        ticker="AAPL",
                        signal_date=today,
                        source="alpha_vantage",
                        source_url="https://example.com/aapl",
                        headline_or_event="AAPL provider numeric catalyst",
                        sentiment_score=75,
                    ),
                    source_export_row(
                        ticker="MSFT",
                        signal_date=today,
                        source="finnhub",
                        source_url="https://example.com/msft",
                        headline_or_event="MSFT catalyst gains",
                    ),
                    source_export_row(
                        ticker="MSFT",
                        signal_date=today,
                        source="marketaux_export",
                        source_url="https://example.com/msft-invalid",
                        headline_or_event="MSFT invalid provider upgrade",
                    ),
                    "",
                ]
            ),
            encoding="utf-8",
        )
        import_result = import_news_catalyst_source_exports(
            config, directory=source_path.parent
        )
        aggregate_news_catalyst_sources(config)
        compute_news_catalyst_text_backfill(config)
        aggregate_news_catalyst_sources(config)
        write_news_catalyst_coverage_template(
            config,
            ("CADX",),
            {"CADX": "old_missing_queue_row"},
            mode="missing",
        )
        provider_plan = news_catalyst_coverage_plan(
            config, max_tickers=5, mode="provider-upgrade"
        )
        upgrade = news_catalyst_provider_upgrade_status(config, max_tickers=5)
        text = build_news_catalyst_provider_upgrade_status_text(config, max_tickers=5)
        cli_output = io.StringIO()
        with redirect_stdout(cli_output):
            cli_exit = command_news_catalyst_provider_upgrade_status(
                Namespace(config=config.config_path, max_tickers=5)
            )
        with patch(
            "target_opportunity_monitor.cli.fetch_news_catalyst_sources",
            return_value=NewsCatalystProviderFetchResult(
                provider="alpha_vantage",
                fetched_count=0,
                stored_count=0,
                skipped_count=0,
                tickers=("MSFT",),
                warnings=(),
                ),
            ) as fetch_mock:
            fetch_output = io.StringIO()
            with redirect_stdout(fetch_output):
                fetch_exit = command_fetch_news_catalyst_sources(
                    Namespace(
                        config=config.config_path,
                        provider="alpha_vantage",
                        ticker=None,
                        max_tickers=5,
                        force_refresh=False,
                        use_cache=None,
                        coverage_plan=False,
                        coverage_mode="missing",
                        provider_upgrade=True,
                    )
                )

        self.assertEqual(cli_exit, 0)
        self.assertEqual(fetch_exit, 0)
        self.assertEqual(upgrade.status, "queued")
        self.assertFalse(provider_plan.missing_queue_template_stale)
        self.assertEqual(provider_plan.missing_queue_template_tickers, ())
        self.assertNotIn(
            "CADX",
            news_catalyst_coverage_queue_path(config, mode="missing").read_text(
                encoding="utf-8"
            ),
        )
        self.assertEqual(upgrade.provider_native_ticker_count, 1)
        self.assertEqual(upgrade.text_derived_only_tickers, ("MSFT",))
        self.assertIn("Status: queued", text)
        self.assertIn("MSFT", cli_output.getvalue())
        self.assertIn(
            "MSFT:invalid_provider_native_upgrade_row:missing_provider_numeric_field",
            import_result.warnings,
        )
        self.assertTrue(fetch_mock.call_args.kwargs["coverage_plan"])
        self.assertEqual(fetch_mock.call_args.kwargs["coverage_mode"], "provider-upgrade")

    def test_all_mode_queue_hygiene_when_only_provider_upgrade_remains(self) -> None:
        database_path = fresh_database_path("phase10e_all_queue_hygiene.sqlite")
        config = make_config(database_path)
        initialize_database(database_path)
        for ticker in ("AAPL", "MSFT"):
            upsert_asset(database_path, Asset(ticker=ticker, asset_type="equity"))
        today = date.today().isoformat()
        source_path = config.news_catalyst_source_exports_dir / "manual.csv"
        source_path.parent.mkdir(parents=True, exist_ok=True)
        source_path.write_text(
            "\n".join(
                [
                    ",".join(SOURCE_EXPORT_HEADERS),
                    source_export_row(
                        ticker="AAPL",
                        signal_date=today,
                        source="alpha_vantage",
                        source_url="https://example.com/aapl",
                        headline_or_event="AAPL provider numeric catalyst",
                        sentiment_score=75,
                    ),
                    source_export_row(
                        ticker="MSFT",
                        signal_date=today,
                        source="finnhub",
                        source_url="https://example.com/msft",
                        headline_or_event="MSFT upgrade catalyst gains",
                    ),
                    "",
                ]
            ),
            encoding="utf-8",
        )
        import_news_catalyst_source_exports(config, directory=source_path.parent)
        aggregate_news_catalyst_sources(config)
        compute_news_catalyst_text_backfill(config)
        aggregate_news_catalyst_sources(config)
        write_news_catalyst_coverage_template(
            config,
            ("CADX",),
            {"CADX": "old_missing_queue_row"},
            mode="missing",
        )

        all_plan = news_catalyst_coverage_plan(
            config, max_tickers=5, write_template=False, mode="all"
        )
        all_text = build_news_catalyst_coverage_plan_text(
            config, max_tickers=5, mode="all"
        )

        self.assertFalse(all_plan.queue_template_stale)
        self.assertFalse(all_plan.missing_queue_template_stale)
        self.assertFalse(all_plan.provider_upgrade_queue_template_stale)
        self.assertEqual(all_plan.missing_queue_template_tickers, ())
        self.assertEqual(all_plan.provider_native_upgrade_tickers, ("MSFT",))
        self.assertIn("Coverage queue stale: False", all_text)
        self.assertIn("Missing queue tickers: none", all_text)
        self.assertIn("Provider upgrade queue tickers: MSFT", all_text)

    def test_provider_smoke_test_classifies_results_without_printing_keys(self) -> None:
        database_path = fresh_database_path("phase10e_provider_smoke.sqlite")
        config = make_config(database_path)
        write_config(config)
        initialize_database(database_path)
        upsert_asset(database_path, Asset(ticker="AAPL", asset_type="equity"))
        marketaux_payload = {
            "data": [
                {
                    "title": "AAPL provider numeric catalyst",
                    "url": "https://example.com/marketaux/aapl",
                    "published_at": date.today().isoformat(),
                    "entities": [
                        {
                            "symbol": "AAPL",
                            "sentiment_score": 0.4,
                            "match_score": 0.9,
                        }
                    ],
                }
            ]
        }
        secret = "marketaux-secret-value"

        with patch.dict("os.environ", {"MARKETAUX_API_KEY": secret}, clear=False):
            with patch(
                "target_opportunity_monitor.news_catalyst_sources._http_json",
                return_value=marketaux_payload,
            ):
                result = test_news_catalyst_provider(
                    config, provider="marketaux", ticker="AAPL"
                )[0]
                output = io.StringIO()
                with redirect_stdout(output):
                    cli_exit = command_test_news_catalyst_provider(
                        Namespace(
                            config=config.config_path,
                            provider="marketaux",
                            ticker="AAPL",
                        )
                    )

        snapshots = list_news_catalyst_source_snapshots(database_path, "AAPL")
        self.assertEqual(result.status, "provider_numeric_available")
        self.assertEqual(result.numeric_stored_count, 1)
        self.assertTrue(any(snapshot.source == "marketaux" for snapshot in snapshots))
        self.assertEqual(cli_exit, 0)
        self.assertIn("provider_numeric_available", output.getvalue())
        self.assertIn("Numeric Stored", output.getvalue())
        self.assertNotIn(secret, output.getvalue())

    def test_provider_smoke_test_missing_key_does_not_store_failure_snapshot(self) -> None:
        database_path = fresh_database_path("phase10e_provider_smoke_missing.sqlite")
        config = make_config(database_path)
        initialize_database(database_path)
        upsert_asset(database_path, Asset(ticker="AAPL", asset_type="equity"))

        with patch(
            "target_opportunity_monitor.news_catalyst_sources._secret_env",
            return_value=None,
        ):
            result = test_news_catalyst_provider(
                config, provider="marketaux", ticker="AAPL"
            )[0]

        snapshots = list_news_catalyst_source_snapshots(database_path, "AAPL")
        self.assertEqual(result.status, "missing_key")
        self.assertEqual(result.stored_count, 0)
        self.assertEqual(snapshots, [])

    def test_provider_native_export_takes_precedence_over_text_backfill(self) -> None:
        database_path = fresh_database_path("phase10e_provider_export_precedence.sqlite")
        config = make_config(database_path)
        initialize_database(database_path)
        upsert_asset(database_path, Asset(ticker="MSFT", asset_type="equity"))
        source_path = config.news_catalyst_source_exports_dir / "manual.csv"
        source_path.parent.mkdir(parents=True, exist_ok=True)
        today = date.today().isoformat()
        source_path.write_text(
            "\n".join(
                [
                    ",".join(SOURCE_EXPORT_HEADERS),
                    source_export_row(
                        ticker="MSFT",
                        signal_date=today,
                        source="finnhub",
                        source_url="https://example.com/msft-headline",
                        headline_or_event="MSFT strong growth catalyst",
                    ),
                    "",
                ]
            ),
            encoding="utf-8",
        )
        import_news_catalyst_source_exports(config, directory=source_path.parent)
        compute_news_catalyst_text_backfill(config)
        aggregate_news_catalyst_sources(config)
        text_only_aggregate = list_news_catalyst_aggregates(database_path, "MSFT")[0]
        self.assertEqual(text_only_aggregate.sources, "news_text_backfill")

        source_path.write_text(
            "\n".join(
                [
                    ",".join(SOURCE_EXPORT_HEADERS),
                    source_export_row(
                        ticker="MSFT",
                        signal_date=today,
                        source="finnhub",
                        source_url="https://example.com/msft-headline",
                        headline_or_event="MSFT strong growth catalyst",
                    ),
                    source_export_row(
                        ticker="MSFT",
                        signal_date=today,
                        source="marketaux_export",
                        source_url="https://example.com/msft-provider",
                        headline_or_event="MSFT provider native catalyst",
                        sentiment_score=82,
                    ),
                    "",
                ]
            ),
            encoding="utf-8",
        )
        import_news_catalyst_source_exports(config, directory=source_path.parent)
        aggregate_news_catalyst_sources(config)
        snapshots = list_news_catalyst_source_snapshots(database_path, "MSFT")
        aggregate = list_news_catalyst_aggregates(database_path, "MSFT")[0]
        status = news_catalyst_source_status_report(config)

        self.assertTrue(any(snapshot.source == "news_text_backfill" for snapshot in snapshots))
        self.assertTrue(any(snapshot.source == "marketaux_export" for snapshot in snapshots))
        self.assertEqual(aggregate.sources, "marketaux_export")
        self.assertAlmostEqual(aggregate.sentiment_score or 0.0, 82.0)
        self.assertEqual(status.provider_numeric_ticker_count, 1)
        self.assertEqual(status.provider_native_upgrade_tickers, ())

    def test_provider_native_backfill_export_targets_text_derived_only_equities(self) -> None:
        database_path = fresh_database_path("phase10e_provider_backfill_export.sqlite")
        config = make_config(database_path)
        write_config(config)
        initialize_database(database_path)
        for ticker, asset_type in (
            ("AAPL", "equity"),
            ("AMD", "equity"),
            ("MSFT", "equity"),
            ("SPY", "etf"),
        ):
            upsert_asset(database_path, Asset(ticker=ticker, asset_type=asset_type))
        source_path = config.news_catalyst_source_exports_dir / "manual.csv"
        source_path.parent.mkdir(parents=True, exist_ok=True)
        today = date.today().isoformat()
        source_path.write_text(
            "\n".join(
                [
                    ",".join(SOURCE_EXPORT_HEADERS),
                    source_export_row(
                        ticker="AAPL",
                        signal_date=today,
                        source="alpha_vantage",
                        source_url="https://example.com/aapl",
                        headline_or_event="AAPL provider native catalyst",
                        sentiment_score=75,
                    ),
                    source_export_row(
                        ticker="AMD",
                        signal_date=today,
                        source="finnhub",
                        source_url="https://example.com/amd",
                        headline_or_event="AMD strong growth catalyst",
                    ),
                    source_export_row(
                        ticker="MSFT",
                        signal_date=today,
                        source="fmp",
                        source_url="https://example.com/msft",
                        headline_or_event="MSFT strong growth catalyst",
                    ),
                    source_export_row(
                        ticker="SPY",
                        signal_date=today,
                        source="finnhub",
                        source_url="https://example.com/spy",
                        headline_or_event="SPY macro catalyst",
                    ),
                    "",
                ]
            ),
            encoding="utf-8",
        )
        import_news_catalyst_source_exports(config, directory=source_path.parent)
        compute_news_catalyst_text_backfill(config)
        aggregate_news_catalyst_sources(config)

        result = export_news_catalyst_provider_backfill(config)
        output = io.StringIO()
        with redirect_stdout(output):
            cli_exit = command_export_news_catalyst_provider_backfill(
                Namespace(config=config.config_path, dir=None)
            )

        template_text = result.template_path.read_text(encoding="utf-8")
        readme_text = result.readme_path.read_text(encoding="utf-8")
        self.assertEqual(cli_exit, 0)
        self.assertEqual(result.tickers, ("AMD", "MSFT"))
        self.assertIn("AMD", template_text)
        self.assertIn("MSFT", template_text)
        self.assertNotIn("AAPL", template_text)
        self.assertNotIn("SPY", template_text)
        self.assertIn("Do not fabricate", readme_text)
        self.assertIn("provider-native backfill package exported", output.getvalue())

    def test_provider_native_backfill_import_rejects_invalid_rows_without_failing(self) -> None:
        database_path = fresh_database_path("phase10e_provider_backfill_import.sqlite")
        config = make_config(database_path)
        initialize_database(database_path)
        upsert_asset(database_path, Asset(ticker="MSFT", asset_type="equity"))
        backfill_dir = config.news_catalyst_source_exports_dir / "provider_native_backfill"
        backfill_dir.mkdir(parents=True, exist_ok=True)
        source_path = backfill_dir / "news_catalyst_provider_native_backfill.csv"
        today = date.today().isoformat()
        source_path.write_text(
            "\n".join(
                [
                    ",".join(SOURCE_EXPORT_HEADERS),
                    source_export_row(
                        ticker="MSFT",
                        signal_date=today,
                        source="marketaux_export",
                        source_url="https://example.com/msft-valid",
                        headline_or_event="MSFT provider native catalyst",
                        sentiment_score=82,
                    ),
                    source_export_row(
                        ticker="MSFT",
                        signal_date=today,
                        source="marketaux_export",
                        headline_or_event="MSFT missing URL",
                        sentiment_score=80,
                    ),
                    source_export_row(
                        ticker="MSFT",
                        signal_date=today,
                        source="eodhd_export",
                        source_url="https://example.com/msft-missing-numeric",
                        headline_or_event="MSFT missing numeric",
                    ),
                    source_export_row(
                        ticker="MSFT",
                        signal_date="bad-date",
                        source="x_export",
                        source_url="https://example.com/msft-bad-date",
                        headline_or_event="MSFT bad date",
                        sentiment_score=70,
                    ),
                    source_export_row(
                        ticker="MSFT",
                        signal_date=today,
                        source="licensed_news_provider_export",
                        source_url="https://example.com/msft-bad-score",
                        headline_or_event="MSFT bad score",
                        sentiment_score="bad",
                    ),
                    "",
                ]
            ),
            encoding="utf-8",
        )

        result = import_news_catalyst_source_exports(config)
        aggregate_news_catalyst_sources(config)
        snapshots = list_news_catalyst_source_snapshots(database_path, "MSFT")
        aggregate = list_news_catalyst_aggregates(database_path, "MSFT")[0]
        source_status = news_catalyst_source_status_report(config)
        upgrade_status = news_catalyst_provider_upgrade_status(config)

        self.assertEqual(result.imported_count, 1)
        self.assertEqual(result.source_row_count, 1)
        self.assertEqual(len(snapshots), 1)
        self.assertEqual(aggregate.sources, "marketaux_export")
        self.assertEqual(source_status.provider_native_rejected_row_count, 4)
        self.assertEqual(source_status.provider_native_rejected_tickers, ("MSFT",))
        self.assertEqual(upgrade_status.provider_native_rejected_row_count, 4)
        self.assertIn(
            "MSFT:invalid_provider_native_upgrade_row:missing_source_url",
            ",".join(result.warnings),
        )
        self.assertIn("malformed_signal_date", ",".join(source_status.provider_native_rejected_warnings))
        self.assertIn("malformed_sentiment_score", ",".join(source_status.provider_native_rejected_warnings))

    def test_provider_backfill_validation_classifies_rows_without_mutating(self) -> None:
        database_path = fresh_database_path("phase10e_provider_backfill_validate.sqlite")
        config = make_config(database_path)
        write_config(config)
        initialize_database(database_path)
        for ticker, asset_type in (
            ("AMD", "equity"),
            ("MSFT", "equity"),
            ("SPY", "etf"),
        ):
            upsert_asset(database_path, Asset(ticker=ticker, asset_type=asset_type))
        backfill_dir = config.news_catalyst_source_exports_dir / "provider_native_backfill"
        backfill_dir.mkdir(parents=True, exist_ok=True)
        source_path = backfill_dir / "news_catalyst_provider_native_backfill.csv"
        today = date.today().isoformat()
        source_path.write_text(
            "\n".join(
                [
                    ",".join(SOURCE_EXPORT_HEADERS),
                    source_export_row(
                        ticker="AMD",
                        signal_date=today,
                        source="user_provider_export",
                        notes=(
                            "coverage_queue:provider_native_news_catalyst_upgrade_needed"
                        ),
                    ),
                    source_export_row(
                        ticker="MSFT",
                        signal_date=today,
                        source="marketaux_export",
                        source_url="https://example.com/msft-valid",
                        headline_or_event="MSFT provider native catalyst",
                        sentiment_score=82,
                    ),
                    source_export_row(
                        ticker="AMD",
                        signal_date=today,
                        source="marketaux_export",
                        headline_or_event="AMD missing URL",
                        sentiment_score=77,
                    ),
                    source_export_row(
                        ticker="AMD",
                        signal_date=today,
                        source="eodhd_export",
                        source_url="https://example.com/amd-no-numeric",
                        headline_or_event="AMD no numeric field",
                    ),
                    source_export_row(
                        ticker="AMD",
                        signal_date="bad-date",
                        source="x_export",
                        source_url="https://example.com/amd-bad-date",
                        headline_or_event="AMD malformed date",
                        sentiment_score=60,
                    ),
                    source_export_row(
                        ticker="AMD",
                        signal_date=today,
                        source="licensed_news_provider_export",
                        source_url="https://example.com/amd-bad-score",
                        headline_or_event="AMD malformed score",
                        sentiment_score=120,
                    ),
                    source_export_row(
                        ticker="AMD",
                        signal_date=today,
                        source="finnhub",
                        source_url="https://example.com/amd-unsupported-source",
                        headline_or_event="AMD unsupported provider native source",
                        sentiment_score=75,
                    ),
                    source_export_row(
                        ticker="ZZZZ",
                        signal_date=today,
                        source="marketaux_export",
                        source_url="https://example.com/zzzz",
                        headline_or_event="Unknown ticker provider row",
                        sentiment_score=75,
                    ),
                    source_export_row(
                        ticker="SPY",
                        signal_date=today,
                        source="marketaux_export",
                        source_url="https://example.com/spy",
                        headline_or_event="SPY ETF row",
                        sentiment_score=75,
                    ),
                    "",
                ]
            ),
            encoding="utf-8",
        )
        before_snapshots = count_rows_by_table(
            database_path,
            "news_catalyst_source_snapshots",
        )

        result = validate_news_catalyst_provider_backfill(config)
        preview = preview_news_catalyst_provider_upgrade(config)
        diagnostics = {
            item.ticker: item for item in news_catalyst_provider_backfill_diagnostics(config)
        }
        diagnostics_text = build_news_catalyst_provider_backfill_diagnostics_text(config)
        after_snapshots = count_rows_by_table(
            database_path,
            "news_catalyst_source_snapshots",
        )
        output = io.StringIO()
        with redirect_stdout(output):
            validate_exit = command_validate_news_catalyst_provider_backfill(
                Namespace(config=config.config_path, dir=None)
            )

        self.assertEqual(validate_exit, 0)
        self.assertEqual(before_snapshots, after_snapshots)
        self.assertEqual(result.total_row_count, 9)
        self.assertEqual(result.valid_row_count, 1)
        self.assertEqual(result.blank_placeholder_count, 1)
        self.assertEqual(result.invalid_row_count, 7)
        self.assertEqual(result.valid_tickers, ("MSFT",))
        self.assertEqual(result.blank_placeholder_tickers, ("AMD",))
        self.assertEqual(result.unsupported_tickers, ("ZZZZ",))
        self.assertEqual(result.etf_gated_tickers, ("SPY",))
        warning_text = ",".join(result.warnings)
        self.assertIn("missing_source_url", warning_text)
        self.assertIn("missing_provider_numeric_field", warning_text)
        self.assertIn("malformed_signal_date", warning_text)
        self.assertIn("malformed_sentiment_score", warning_text)
        self.assertIn("unsupported_provider_native_source", warning_text)
        self.assertIn("inactive_or_unknown_ticker", warning_text)
        self.assertIn("etf_news_catalyst_gated", warning_text)
        self.assertEqual(preview.valid_backfill_tickers, ())
        self.assertEqual(diagnostics["MSFT"].classification, "valid_row_no_upgrade_needed")
        self.assertEqual(diagnostics["MSFT"].valid_rows, 1)
        self.assertEqual(diagnostics["AMD"].classification, "invalid_provider_native_row")
        self.assertEqual(diagnostics["AMD"].blank_placeholder_rows, 1)
        self.assertEqual(diagnostics["AMD"].invalid_rows, 5)
        self.assertIn("missing_source_url", diagnostics["AMD"].warnings)
        self.assertEqual(diagnostics["SPY"].classification, "invalid_provider_native_row")
        self.assertIn("etf_news_catalyst_gated", diagnostics["SPY"].warnings)
        self.assertIn("MSFT | valid_row_no_upgrade_needed", diagnostics_text)
        self.assertIn("AMD | invalid_provider_native_row", diagnostics_text)
        self.assertIn("Valid provider-native rows: 1", output.getvalue())

    def test_provider_upgrade_preview_projects_coverage_without_mutating(self) -> None:
        database_path = fresh_database_path("phase10e_provider_upgrade_preview.sqlite")
        config = make_config(database_path)
        write_config(config)
        initialize_database(database_path)
        for ticker, asset_type in (
            ("AAPL", "equity"),
            ("AMD", "equity"),
            ("MSFT", "equity"),
            ("SPY", "etf"),
        ):
            upsert_asset(database_path, Asset(ticker=ticker, asset_type=asset_type))
        today = date.today().isoformat()
        source_path = config.news_catalyst_source_exports_dir / "manual.csv"
        source_path.parent.mkdir(parents=True, exist_ok=True)
        source_path.write_text(
            "\n".join(
                [
                    ",".join(SOURCE_EXPORT_HEADERS),
                    source_export_row(
                        ticker="AAPL",
                        signal_date=today,
                        source="alpha_vantage",
                        source_url="https://example.com/aapl",
                        headline_or_event="AAPL provider native catalyst",
                        sentiment_score=72,
                    ),
                    source_export_row(
                        ticker="AMD",
                        signal_date=today,
                        source="finnhub",
                        source_url="https://example.com/amd",
                        headline_or_event="AMD strong product launch",
                    ),
                    source_export_row(
                        ticker="MSFT",
                        signal_date=today,
                        source="fmp",
                        source_url="https://example.com/msft",
                        headline_or_event="MSFT strong cloud growth",
                    ),
                    "",
                ]
            ),
            encoding="utf-8",
        )
        import_news_catalyst_source_exports(config, directory=source_path.parent)
        compute_news_catalyst_text_backfill(config)
        aggregate_news_catalyst_sources(config)
        backfill_dir = config.news_catalyst_source_exports_dir / "provider_native_backfill"
        backfill_dir.mkdir(parents=True, exist_ok=True)
        backfill_path = backfill_dir / "news_catalyst_provider_native_backfill.csv"
        backfill_path.write_text(
            "\n".join(
                [
                    ",".join(SOURCE_EXPORT_HEADERS),
                    source_export_row(
                        ticker="MSFT",
                        signal_date=today,
                        source="marketaux_export",
                        source_url="https://example.com/msft-provider-native",
                        headline_or_event="MSFT provider-native upgrade row",
                        sentiment_score=84,
                    ),
                    source_export_row(
                        ticker="AMD",
                        signal_date=today,
                        source="user_provider_export",
                        notes=(
                            "coverage_queue:provider_native_news_catalyst_upgrade_needed"
                        ),
                    ),
                    "",
                ]
            ),
            encoding="utf-8",
        )
        before_snapshot_count = count_rows_by_table(
            database_path,
            "news_catalyst_source_snapshots",
        )
        before_aggregate_count = count_rows_by_table(
            database_path,
            "news_catalyst_aggregates",
        )

        preview = preview_news_catalyst_provider_upgrade(config)
        after_snapshot_count = count_rows_by_table(
            database_path,
            "news_catalyst_source_snapshots",
        )
        after_aggregate_count = count_rows_by_table(
            database_path,
            "news_catalyst_aggregates",
        )
        output = io.StringIO()
        with redirect_stdout(output):
            preview_exit = command_preview_news_catalyst_provider_upgrade(
                Namespace(config=config.config_path, dir=None)
            )

        self.assertEqual(preview_exit, 0)
        self.assertEqual(before_snapshot_count, after_snapshot_count)
        self.assertEqual(before_aggregate_count, after_aggregate_count)
        self.assertEqual(preview.current_provider_native_ticker_count, 1)
        self.assertEqual(preview.current_provider_native_tickers, ("AAPL",))
        self.assertEqual(preview.text_derived_only_tickers, ("AMD", "MSFT"))
        self.assertEqual(preview.valid_backfill_tickers, ("MSFT",))
        self.assertEqual(preview.projected_provider_native_ticker_count, 2)
        self.assertEqual(preview.still_blocked_tickers, ("AMD",))
        self.assertIn(
            "python -m target_opportunity_monitor import-news-catalyst-source-exports",
            output.getvalue(),
        )

    def test_provider_export_normalization_accepts_marketaux_and_eodhd_rows(self) -> None:
        database_path = fresh_database_path("phase10e_provider_export_normalize.sqlite")
        config = make_config(database_path)
        write_config(config)
        initialize_database(database_path)
        for ticker in ("AAPL", "AMD", "MSFT"):
            upsert_asset(database_path, Asset(ticker=ticker, asset_type="equity"))
        today = date.today().isoformat()
        source_path = config.news_catalyst_source_exports_dir / "manual.csv"
        source_path.parent.mkdir(parents=True, exist_ok=True)
        source_path.write_text(
            "\n".join(
                [
                    ",".join(SOURCE_EXPORT_HEADERS),
                    source_export_row(
                        ticker="AAPL",
                        signal_date=today,
                        source="alpha_vantage",
                        source_url="https://example.com/aapl",
                        headline_or_event="AAPL provider native catalyst",
                        sentiment_score=72,
                    ),
                    source_export_row(
                        ticker="AMD",
                        signal_date=today,
                        source="finnhub",
                        source_url="https://example.com/amd",
                        headline_or_event="AMD strong catalyst",
                    ),
                    source_export_row(
                        ticker="MSFT",
                        signal_date=today,
                        source="fmp",
                        source_url="https://example.com/msft",
                        headline_or_event="MSFT cloud growth catalyst",
                    ),
                    "",
                ]
            ),
            encoding="utf-8",
        )
        import_news_catalyst_source_exports(config, directory=source_path.parent)
        compute_news_catalyst_text_backfill(config)
        aggregate_news_catalyst_sources(config)

        raw_dir = TEST_TMP_ROOT / "provider_raw" / database_path.stem
        raw_dir.mkdir(parents=True, exist_ok=True)
        marketaux_raw = raw_dir / "marketaux.csv"
        marketaux_raw.write_text(
            "\n".join(
                [
                    "symbol,published_at,url,title,sentiment_score,relevance_score",
                    f"MSFT,{today}T14:30:00Z,https://example.com/msft-provider,MSFT provider native row,0.6,0.9",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        eodhd_raw = raw_dir / "eodhd.csv"
        eodhd_raw.write_text(
            "\n".join(
                [
                    "ticker,date,link,headline,polarity,confidence",
                    f"AMD,{today},https://example.com/amd-provider,AMD provider native row,-0.2,0.7",
                    "",
                ]
            ),
            encoding="utf-8",
        )

        marketaux_result = normalize_news_catalyst_provider_export(
            config,
            provider="marketaux",
            source_path=marketaux_raw,
        )
        eodhd_result = normalize_news_catalyst_provider_export(
            config,
            provider="eodhd",
            source_path=eodhd_raw,
        )
        cli_output = io.StringIO()
        with redirect_stdout(cli_output):
            cli_exit = command_normalize_news_catalyst_provider_export(
                Namespace(
                    config=config.config_path,
                    provider="marketaux",
                    file=marketaux_raw,
                )
            )

        marketaux_rows = list(
            csv.DictReader(
                marketaux_result.output_path.read_text(encoding="utf-8").splitlines()
            )
        )
        eodhd_rows = list(
            csv.DictReader(
                eodhd_result.output_path.read_text(encoding="utf-8").splitlines()
            )
        )

        self.assertEqual(cli_exit, 0)
        self.assertEqual(marketaux_result.normalized_count, 1)
        self.assertEqual(eodhd_result.normalized_count, 1)
        self.assertEqual(marketaux_result.tickers, ("MSFT",))
        self.assertEqual(eodhd_result.tickers, ("AMD",))
        self.assertEqual(marketaux_rows[0]["source"], "marketaux_export")
        self.assertEqual(eodhd_rows[0]["source"], "eodhd_export")
        self.assertEqual(float(marketaux_rows[0]["sentiment_score"]), 80.0)
        self.assertEqual(float(marketaux_rows[0]["relevance_score"]), 90.0)
        self.assertEqual(float(eodhd_rows[0]["sentiment_score"]), 40.0)
        self.assertEqual(float(eodhd_rows[0]["confidence"]), 70.0)
        self.assertIn("provider export normalized", cli_output.getvalue())

    def test_provider_export_normalization_skips_non_upgrade_and_text_only_rows(self) -> None:
        database_path = fresh_database_path("phase10e_provider_export_normalize_skips.sqlite")
        config = make_config(database_path)
        initialize_database(database_path)
        for ticker, asset_type in (
            ("AAPL", "equity"),
            ("AMD", "equity"),
            ("SPY", "etf"),
        ):
            upsert_asset(database_path, Asset(ticker=ticker, asset_type=asset_type))
        today = date.today().isoformat()
        source_path = config.news_catalyst_source_exports_dir / "manual.csv"
        source_path.parent.mkdir(parents=True, exist_ok=True)
        source_path.write_text(
            "\n".join(
                [
                    ",".join(SOURCE_EXPORT_HEADERS),
                    source_export_row(
                        ticker="AAPL",
                        signal_date=today,
                        source="alpha_vantage",
                        source_url="https://example.com/aapl",
                        headline_or_event="AAPL provider native catalyst",
                        sentiment_score=72,
                    ),
                    source_export_row(
                        ticker="AMD",
                        signal_date=today,
                        source="finnhub",
                        source_url="https://example.com/amd",
                        headline_or_event="AMD source backed text",
                    ),
                    "",
                ]
            ),
            encoding="utf-8",
        )
        import_news_catalyst_source_exports(config, directory=source_path.parent)
        compute_news_catalyst_text_backfill(config)
        aggregate_news_catalyst_sources(config)

        raw_path = TEST_TMP_ROOT / "provider_raw" / database_path.stem / "generic.csv"
        raw_path.parent.mkdir(parents=True, exist_ok=True)
        raw_path.write_text(
            "\n".join(
                [
                    "ticker,signal_date,source,source_url,headline_or_event,sentiment_score",
                    f"AAPL,{today},marketaux_export,https://example.com/aapl,AAPL already native,81",
                    f"SPY,{today},marketaux_export,https://example.com/spy,SPY ETF native,82",
                    f"ZZZZ,{today},marketaux_export,https://example.com/zzzz,Unknown native,83",
                    f"AMD,{today},marketaux_export,https://example.com/amd-text,AMD headline only,",
                    f"AMD,{today},licensed_news_provider_export,https://example.com/amd-valid,AMD valid native,77",
                    "",
                ]
            ),
            encoding="utf-8",
        )

        result = normalize_news_catalyst_provider_export(
            config,
            provider="generic",
            source_path=raw_path,
        )
        rows = list(
            csv.DictReader(result.output_path.read_text(encoding="utf-8").splitlines())
        )
        warning_text = ",".join(result.warnings)

        self.assertEqual(result.normalized_count, 1)
        self.assertEqual(result.skipped_count, 4)
        self.assertEqual(rows[0]["ticker"], "AMD")
        self.assertEqual(rows[0]["source"], "licensed_news_provider_export")
        self.assertIn("AAPL:already_provider_native", warning_text)
        self.assertIn("SPY:etf_news_catalyst_gated", warning_text)
        self.assertIn("ZZZZ:inactive_or_unknown_ticker", warning_text)
        self.assertIn("AMD:no_provider_numeric_field", warning_text)

    def test_provider_backfill_apply_dry_run_and_confirm_guards_do_not_mutate(self) -> None:
        database_path = fresh_database_path("phase10e_provider_backfill_apply_guard.sqlite")
        config = make_config(database_path)
        write_config(config)
        initialize_database(database_path)
        upsert_asset(database_path, Asset(ticker="AMD", asset_type="equity"))
        today = date.today().isoformat()
        source_path = config.news_catalyst_source_exports_dir / "manual.csv"
        source_path.parent.mkdir(parents=True, exist_ok=True)
        source_path.write_text(
            "\n".join(
                [
                    ",".join(SOURCE_EXPORT_HEADERS),
                    source_export_row(
                        ticker="AMD",
                        signal_date=today,
                        source="finnhub",
                        source_url="https://example.com/amd",
                        headline_or_event="AMD source backed text",
                    ),
                    "",
                ]
            ),
            encoding="utf-8",
        )
        import_news_catalyst_source_exports(config, directory=source_path.parent)
        compute_news_catalyst_text_backfill(config)
        aggregate_news_catalyst_sources(config)
        export_news_catalyst_provider_backfill(config)
        before_snapshots = count_rows_by_table(database_path, "news_catalyst_source_snapshots")
        before_aggregates = count_rows_by_table(database_path, "news_catalyst_aggregates")

        dry_run = apply_news_catalyst_provider_backfill(config)
        blocked = apply_news_catalyst_provider_backfill(config, confirm=True)
        status_text = build_news_catalyst_provider_backfill_status_text(config)
        status_output = io.StringIO()
        with redirect_stdout(status_output):
            status_exit = command_news_catalyst_provider_backfill_status(
                Namespace(config=config.config_path, dir=None, allow_partial=False)
            )
        apply_output = io.StringIO()
        with redirect_stdout(apply_output):
            apply_exit = command_apply_news_catalyst_provider_backfill(
                Namespace(
                    config=config.config_path,
                    dir=None,
                    confirm=False,
                    allow_partial=False,
                )
            )
        confirm_output = io.StringIO()
        with redirect_stdout(confirm_output):
            confirm_exit = command_apply_news_catalyst_provider_backfill(
                Namespace(
                    config=config.config_path,
                    dir=None,
                    confirm=True,
                    allow_partial=False,
                )
            )

        self.assertFalse(dry_run.applied)
        self.assertFalse(blocked.applied)
        self.assertEqual(status_exit, 0)
        self.assertEqual(apply_exit, 0)
        self.assertEqual(confirm_exit, 1)
        self.assertEqual(before_snapshots, count_rows_by_table(database_path, "news_catalyst_source_snapshots"))
        self.assertEqual(before_aggregates, count_rows_by_table(database_path, "news_catalyst_aggregates"))
        self.assertEqual(blocked.status.blocked_apply_reason, "no_valid_provider_native_backfill_rows")
        self.assertIn("Backfill apply ready: False", status_text)
        self.assertIn("Dry run: True", apply_output.getvalue())
        self.assertIn("provider_native_backfill_apply_blocked", confirm_output.getvalue())

    def test_provider_backfill_apply_confirm_allow_partial_imports_valid_rows(self) -> None:
        database_path = fresh_database_path("phase10e_provider_backfill_apply_partial.sqlite")
        config = make_config(database_path)
        write_config(config)
        initialize_database(database_path)
        for ticker in ("AAPL", "AMD", "MSFT"):
            upsert_asset(database_path, Asset(ticker=ticker, asset_type="equity"))
        today = date.today().isoformat()
        source_path = config.news_catalyst_source_exports_dir / "manual.csv"
        source_path.parent.mkdir(parents=True, exist_ok=True)
        source_path.write_text(
            "\n".join(
                [
                    ",".join(SOURCE_EXPORT_HEADERS),
                    source_export_row(
                        ticker="AAPL",
                        signal_date=today,
                        source="alpha_vantage",
                        source_url="https://example.com/aapl",
                        headline_or_event="AAPL provider native catalyst",
                        sentiment_score=72,
                    ),
                    source_export_row(
                        ticker="AMD",
                        signal_date=today,
                        source="finnhub",
                        source_url="https://example.com/amd",
                        headline_or_event="AMD source backed text",
                    ),
                    source_export_row(
                        ticker="MSFT",
                        signal_date=today,
                        source="fmp",
                        source_url="https://example.com/msft",
                        headline_or_event="MSFT source backed text",
                    ),
                    "",
                ]
            ),
            encoding="utf-8",
        )
        import_news_catalyst_source_exports(config, directory=source_path.parent)
        compute_news_catalyst_text_backfill(config)
        aggregate_news_catalyst_sources(config)
        backfill_dir = config.news_catalyst_source_exports_dir / "provider_native_backfill"
        backfill_dir.mkdir(parents=True, exist_ok=True)
        (backfill_dir / "normalized_marketaux_provider_native.csv").write_text(
            "\n".join(
                [
                    ",".join(SOURCE_EXPORT_HEADERS),
                    source_export_row(
                        ticker="MSFT",
                        signal_date=today,
                        source="marketaux_export",
                        source_url="https://example.com/msft-provider",
                        headline_or_event="MSFT provider native row",
                        sentiment_score=83,
                    ),
                    source_export_row(
                        ticker="AMD",
                        signal_date=today,
                        source="user_provider_export",
                        notes="coverage_queue:provider_native_news_catalyst_upgrade_needed",
                    ),
                    "",
                ]
            ),
            encoding="utf-8",
        )

        blocked_status = news_catalyst_provider_backfill_apply_status(config)
        partial_status = news_catalyst_provider_backfill_apply_status(
            config,
            allow_partial=True,
        )
        result = apply_news_catalyst_provider_backfill(
            config,
            confirm=True,
            allow_partial=True,
        )
        source_status = news_catalyst_source_status_report(config)
        aggregate = list_news_catalyst_aggregates(database_path, "MSFT")[0]

        self.assertFalse(blocked_status.backfill_apply_ready)
        self.assertEqual(
            blocked_status.blocked_apply_reason,
            "partial_provider_native_backfill_requires_allow_partial",
        )
        self.assertTrue(partial_status.backfill_apply_ready)
        self.assertTrue(result.applied)
        self.assertGreaterEqual(result.imported_count, 1)
        self.assertEqual(result.status.valid_upgrade_tickers, ("MSFT",))
        self.assertEqual(result.status.projected_upgrade_delta, 1)
        self.assertEqual(aggregate.sources, "marketaux_export")
        self.assertEqual(source_status.provider_numeric_tickers, ("AAPL", "MSFT"))
        self.assertEqual(source_status.provider_native_upgrade_tickers, ("AMD",))

    def test_coverage_plan_fetch_uses_bounded_planned_tickers(self) -> None:
        database_path = fresh_database_path("phase10e_coverage_fetch.sqlite")
        config = make_config(database_path)
        initialize_database(database_path)
        for ticker in ("AAPL", "MSFT", "NVDA"):
            upsert_asset(database_path, Asset(ticker=ticker, asset_type="equity"))
        source_path = config.news_catalyst_source_exports_dir / "manual.csv"
        source_path.parent.mkdir(parents=True, exist_ok=True)
        source_path.write_text(
            "\n".join(
                [
                    ",".join(SOURCE_EXPORT_HEADERS),
                    source_export_row(
                        ticker="AAPL",
                        signal_date=date.today().isoformat(),
                        source="alpha_vantage",
                        source_url="https://example.com/aapl",
                        headline_or_event="AAPL numeric catalyst",
                        sentiment_score=75,
                    ),
                    "",
                ]
            ),
            encoding="utf-8",
        )
        import_news_catalyst_source_exports(config, directory=source_path.parent)
        aggregate_news_catalyst_sources(config)

        with patch(
            "target_opportunity_monitor.news_catalyst_sources._fetch_alpha_vantage_news_rows",
            return_value=NewsCatalystProviderFetchResult(
                provider="alpha_vantage",
                fetched_count=0,
                stored_count=0,
                skipped_count=0,
                tickers=(),
                warnings=(),
            ),
        ) as fetch_mock:
            fetch_news_catalyst_sources(
                config,
                provider="alpha_vantage",
                coverage_plan=True,
                max_tickers=1,
            )

        self.assertEqual(fetch_mock.call_args.args[1], ["MSFT"])

    def test_provider_fetch_uses_mocked_payloads_and_missing_keys_warn(self) -> None:
        database_path = fresh_database_path("phase10e_provider_fetch.sqlite")
        config = make_config(database_path)
        initialize_database(database_path)
        upsert_asset(database_path, Asset(ticker="AAPL", asset_type="equity"))

        with (
            patch.dict("os.environ", {}, clear=True),
            patch(
                "target_opportunity_monitor.news_catalyst_sources._read_windows_registry_env",
                return_value=None,
            ),
        ):
            missing_result = fetch_news_catalyst_sources(config, provider="alpha_vantage")
        self.assertEqual(missing_result.stored_count, 0)
        self.assertIn("missing_alpha_vantage_api_key", missing_result.warnings)

        alpha_payload = {
            "feed": [
                {
                    "title": "AAPL product catalyst",
                    "url": "https://example.com/alpha/aapl",
                    "time_published": "20260608T120000",
                    "summary": "Source-backed article.",
                    "topics": [{"topic": "technology"}],
                    "ticker_sentiment": [
                        {
                            "ticker": "AAPL",
                            "ticker_sentiment_score": "0.5",
                            "relevance_score": "0.8",
                        }
                    ],
                }
            ]
        }
        with (
            patch.dict("os.environ", {"ALPHAVANTAGE_API_KEY": "test-key"}),
            patch(
                "target_opportunity_monitor.news_catalyst_sources._read_windows_registry_env",
                return_value=None,
            ),
            patch(
                "target_opportunity_monitor.news_catalyst_sources._http_json",
                return_value=alpha_payload,
            ),
            patch(
                "target_opportunity_monitor.news_catalyst_sources.time.sleep",
                return_value=None,
            ),
        ):
            result = fetch_news_catalyst_sources(config, provider="alpha_vantage")

        snapshots = [
            snapshot
            for snapshot in list_news_catalyst_source_snapshots(database_path, "AAPL")
            if snapshot.provider_status == "ok" and snapshot.source == "alpha_vantage"
        ]
        self.assertEqual(result.stored_count, 1)
        self.assertEqual(snapshots[0].source, "alpha_vantage")
        self.assertEqual(snapshots[0].sentiment_score, 75)
        self.assertEqual(snapshots[0].relevance_score, 80)

        with (
            patch.dict("os.environ", {"FINNHUB_API_KEY": "test-key"}),
            patch(
                "target_opportunity_monitor.news_catalyst_sources._read_windows_registry_env",
                return_value=None,
            ),
            patch(
                "target_opportunity_monitor.news_catalyst_sources._http_json",
                side_effect=[
                    {"sentiment": {"bullishPercent": 0.7, "bearishPercent": 0.2}},
                    [
                        {
                            "headline": "AAPL company news",
                            "url": "https://example.com/finnhub/aapl",
                            "datetime": 1780920000,
                            "summary": "Company news.",
                            "category": "company",
                        }
                    ],
                ],
            ),
        ):
            finnhub_result = fetch_news_catalyst_sources(config, provider="finnhub")
        self.assertEqual(finnhub_result.stored_count, 1)

        with (
            patch.dict("os.environ", {"FMP_API_KEY": "test-key"}),
            patch(
                "target_opportunity_monitor.news_catalyst_sources._read_windows_registry_env",
                return_value=None,
            ),
            patch(
                "target_opportunity_monitor.news_catalyst_sources._http_json",
                return_value=[
                    {
                        "title": "AAPL FMP news",
                        "url": "https://example.com/fmp/aapl",
                        "publishedDate": "2026-06-08 12:00:00",
                        "sentimentScore": 0.2,
                        "site": "FMP",
                    }
                ],
            ),
        ):
            fmp_result = fetch_news_catalyst_sources(config, provider="fmp")
        self.assertEqual(fmp_result.stored_count, 1)

    def test_marketaux_and_eodhd_numeric_payloads_create_aggregates(self) -> None:
        database_path = fresh_database_path("phase10e_marketaux_eodhd.sqlite")
        config = make_config(database_path)
        initialize_database(database_path)
        upsert_asset(database_path, Asset(ticker="AAPL", asset_type="equity"))

        marketaux_payload = {
            "data": [
                {
                    "title": "AAPL strong product launch",
                    "url": "https://example.com/marketaux/aapl",
                    "published_at": "2026-06-08T12:00:00Z",
                    "description": "AAPL announces a strong product launch.",
                    "entities": [
                        {
                            "symbol": "AAPL.US",
                            "sentiment_score": 0.6,
                            "match_score": 0.9,
                            "industry": "technology",
                        }
                    ],
                }
            ]
        }
        with (
            patch.dict("os.environ", {"MARKETAUX_API_KEY": "test-key"}),
            patch(
                "target_opportunity_monitor.news_catalyst_sources._read_windows_registry_env",
                return_value=None,
            ),
            patch(
                "target_opportunity_monitor.news_catalyst_sources._http_json",
                return_value=marketaux_payload,
            ),
        ):
            marketaux_result = fetch_news_catalyst_sources(
                config,
                provider="marketaux",
                ticker="AAPL",
                force_refresh=True,
            )
        self.assertEqual(marketaux_result.stored_count, 1)

        eodhd_payload = [
            {
                "title": "AAPL earnings catalyst",
                "link": "https://example.com/eodhd/aapl",
                "date": "2026-06-08T13:00:00Z",
                "content": "AAPL earnings catalyst is positive.",
                "sentiment": {"polarity": 0.2},
                "tags": ["earnings", "technology"],
            }
        ]
        with (
            patch.dict("os.environ", {"EODHD_API_KEY": "test-key"}),
            patch(
                "target_opportunity_monitor.news_catalyst_sources._read_windows_registry_env",
                return_value=None,
            ),
            patch(
                "target_opportunity_monitor.news_catalyst_sources._http_json",
                return_value=eodhd_payload,
            ),
        ):
            eodhd_result = fetch_news_catalyst_sources(
                config,
                provider="eodhd",
                ticker="AAPL",
                force_refresh=True,
            )

        aggregate_result = aggregate_news_catalyst_sources(config, ticker="AAPL")
        aggregates = list_news_catalyst_aggregates(database_path, "AAPL")
        status = news_catalyst_source_status_report(config)

        self.assertEqual(eodhd_result.stored_count, 1)
        self.assertEqual(aggregate_result.aggregate_count, 1)
        self.assertEqual(len(aggregates), 1)
        self.assertAlmostEqual(aggregates[0].sentiment_score or 0.0, 80.0)
        self.assertEqual(status.provider_numeric_ticker_count, 1)
        self.assertEqual(status.text_derived_ticker_count, 0)
        self.assertEqual(status.total_numeric_ticker_count, 1)

    def test_x_and_truth_text_rows_feed_deterministic_backfill(self) -> None:
        database_path = fresh_database_path("phase10e_text_backfill.sqlite")
        config = make_config(database_path)
        initialize_database(database_path)
        upsert_asset(
            database_path,
            Asset(ticker="AAPL", name="Apple Inc", asset_type="equity"),
        )

        x_payload = {
            "data": [
                {
                    "id": "123",
                    "created_at": "2026-06-08T12:00:00Z",
                    "text": "AAPL strong launch today boosts growth",
                }
            ]
        }
        with (
            patch.dict("os.environ", {"X_BEARER_TOKEN": "test-token"}),
            patch(
                "target_opportunity_monitor.news_catalyst_sources._read_windows_registry_env",
                return_value=None,
            ),
            patch(
                "target_opportunity_monitor.news_catalyst_sources._http_json",
                return_value=x_payload,
            ),
        ):
            x_result = fetch_news_catalyst_sources(
                config,
                provider="x_recent_search",
                ticker="AAPL",
                force_refresh=True,
            )

        truth_lookup = {"id": "42"}
        truth_statuses = [
            {
                "id": "987",
                "created_at": "2026-06-08T13:00:00Z",
                "content": "<p>AAPL tariff risk today could delay growth</p>",
                "url": "https://truthsocial.com/@realDonaldTrump/posts/987",
            }
        ]
        with patch(
            "target_opportunity_monitor.news_catalyst_sources._http_json",
            side_effect=[truth_lookup, truth_statuses],
        ):
            truth_result = fetch_news_catalyst_sources(
                config,
                provider="truth_social_public",
                ticker="AAPL",
                force_refresh=True,
                use_cache=False,
            )

        backfill_result = compute_news_catalyst_text_backfill(config, ticker="AAPL")
        aggregate_result = aggregate_news_catalyst_sources(config, ticker="AAPL")
        snapshots = list_news_catalyst_source_snapshots(database_path, "AAPL")
        aggregates = list_news_catalyst_aggregates(database_path, "AAPL")
        status = news_catalyst_source_status_report(config)

        self.assertEqual(x_result.stored_count, 1)
        self.assertEqual(truth_result.stored_count, 1)
        self.assertEqual(backfill_result.derived_count, 2)
        self.assertEqual(aggregate_result.aggregate_count, 1)
        self.assertTrue(
            any(snapshot.source == "news_text_backfill" for snapshot in snapshots)
        )
        self.assertIn("text_derived_sentiment", aggregates[0].data_warnings or "")
        self.assertIn("not_provider_numeric", aggregates[0].data_warnings or "")
        self.assertEqual(status.provider_numeric_ticker_count, 0)
        self.assertEqual(status.text_derived_ticker_count, 1)
        self.assertEqual(status.total_numeric_ticker_count, 1)

    def test_provider_cache_budget_and_rate_limit_handling(self) -> None:
        database_path = fresh_database_path("phase10e_provider_cache.sqlite")
        config = make_config(database_path)
        initialize_database(database_path)
        for ticker in ("AAPL", "MSFT", "NVDA"):
            upsert_asset(database_path, Asset(ticker=ticker, asset_type="equity"))

        alpha_payload = {
            "feed": [
                {
                    "title": "AAPL source-backed catalyst",
                    "url": "https://example.com/alpha/aapl-cache",
                    "time_published": "20260608T120000",
                    "ticker_sentiment": [
                        {
                            "ticker": "AAPL",
                            "ticker_sentiment_score": "0.4",
                            "relevance_score": "0.9",
                        }
                    ],
                }
            ]
        }
        with (
            patch.dict("os.environ", {"ALPHAVANTAGE_API_KEY": "test-key"}),
            patch(
                "target_opportunity_monitor.news_catalyst_sources._read_windows_registry_env",
                return_value=None,
            ),
            patch(
                "target_opportunity_monitor.news_catalyst_sources._http_json",
                return_value=alpha_payload,
            ) as first_http,
        ):
            first_result = fetch_news_catalyst_sources(
                config,
                provider="alpha_vantage",
                ticker="AAPL",
                force_refresh=True,
            )

        self.assertEqual(first_result.live_requests, 1)
        self.assertEqual(first_result.cache_writes, 1)
        self.assertEqual(first_http.call_count, 1)

        with (
            patch.dict("os.environ", {"ALPHAVANTAGE_API_KEY": "test-key"}),
            patch(
                "target_opportunity_monitor.news_catalyst_sources._read_windows_registry_env",
                return_value=None,
            ),
            patch(
                "target_opportunity_monitor.news_catalyst_sources._http_json",
                side_effect=AssertionError("cache hit should avoid HTTP"),
            ),
        ):
            cached_result = fetch_news_catalyst_sources(
                config,
                provider="alpha_vantage",
                ticker="AAPL",
                use_cache=True,
            )

        self.assertEqual(cached_result.cache_hits, 1)
        self.assertEqual(cached_result.live_requests, 0)
        self.assertEqual(cached_result.stored_count, 1)

        with (
            patch.dict("os.environ", {"ALPHAVANTAGE_API_KEY": "test-key"}),
            patch(
                "target_opportunity_monitor.news_catalyst_sources._read_windows_registry_env",
                return_value=None,
            ),
            patch(
                "target_opportunity_monitor.news_catalyst_sources._http_json",
                return_value=alpha_payload,
            ) as budget_http,
        ):
            budget_result = fetch_news_catalyst_sources(
                config,
                provider="alpha_vantage",
                max_tickers=1,
                force_refresh=True,
                use_cache=False,
            )

        self.assertEqual(budget_result.live_requests, 1)
        self.assertEqual(budget_http.call_count, 1)
        self.assertTrue(budget_result.budget_exhausted)
        self.assertIn("MSFT:alpha_vantage_provider_budget_exhausted", budget_result.warnings)
        self.assertIn("NVDA:alpha_vantage_provider_budget_exhausted", budget_result.warnings)

        rate_limit_database = fresh_database_path("phase10e_provider_rate_limit.sqlite")
        rate_limit_config = make_config(rate_limit_database)
        initialize_database(rate_limit_database)
        for ticker in ("AAPL", "MSFT"):
            upsert_asset(rate_limit_database, Asset(ticker=ticker, asset_type="equity"))
        rate_limit_payload = {
            "Note": (
                "Thank you for using Alpha Vantage! Our standard API call frequency "
                "is limited."
            )
        }
        with (
            patch.dict("os.environ", {"ALPHAVANTAGE_API_KEY": "test-key"}),
            patch(
                "target_opportunity_monitor.news_catalyst_sources._read_windows_registry_env",
                return_value=None,
            ),
            patch(
                "target_opportunity_monitor.news_catalyst_sources._http_json",
                return_value=rate_limit_payload,
            ) as rate_limit_http,
        ):
            rate_limit_result = fetch_news_catalyst_sources(
                rate_limit_config,
                provider="alpha_vantage",
                max_tickers=3,
                force_refresh=True,
                use_cache=False,
            )

        self.assertEqual(rate_limit_result.live_requests, 1)
        self.assertEqual(rate_limit_http.call_count, 1)
        self.assertEqual(rate_limit_result.cache_writes, 0)
        self.assertIn("AAPL:alpha_vantage_rate_limited", rate_limit_result.warnings)
        self.assertIn("MSFT:alpha_vantage_rate_limited", rate_limit_result.warnings)

    def test_load_compute_and_status_are_idempotent_with_etf_gating(self) -> None:
        database_path = fresh_database_path("phase10e_load_compute.sqlite")
        config = make_config(database_path)
        initialize_database(database_path)
        for ticker, asset_type in (
            ("AAPL", "equity"),
            ("MSFT", "equity"),
            ("NVDA", "equity"),
            ("SPY", "etf"),
        ):
            upsert_asset(database_path, Asset(ticker=ticker, asset_type=asset_type))

        stale_date = (date.today() - timedelta(days=60)).isoformat()
        today = date.today().isoformat()
        write_news_csv(
            config,
            [
                news_row(
                    ticker="AAPL",
                    signal_date=today,
                    source="manual_capture",
                    source_url="https://example.com/aapl",
                    headline_or_event="AAPL product catalyst",
                    sentiment_score=80,
                    catalyst_score=70,
                    urgency_score=60,
                    confidence=85,
                ),
                news_row(
                    ticker="MSFT",
                    signal_date=today,
                    source="manual_capture",
                    source_url="https://example.com/msft",
                    headline_or_event="MSFT regulatory risk",
                    sentiment_score=30,
                    catalyst_score=40,
                    urgency_score=35,
                    confidence=45,
                ),
                news_row(
                    ticker="NVDA",
                    signal_date=stale_date,
                    source="manual_capture",
                    source_url="https://example.com/nvda",
                    headline_or_event="Old NVDA catalyst",
                    sentiment_score=50,
                    catalyst_score=55,
                    urgency_score=45,
                ),
                news_row(
                    ticker="SPY",
                    signal_date=today,
                    source="manual_capture",
                    source_url="https://example.com/spy",
                    headline_or_event="ETF macro note",
                    sentiment_score=65,
                    catalyst_score=65,
                ),
            ],
        )

        first_load = load_news_catalysts_csv(config)
        second_load = load_news_catalysts_csv(config)
        result = compute_news_catalyst_signals(config)
        statuses = {status.ticker: status for status in news_catalyst_statuses(config)}

        self.assertEqual(first_load.input_signal_count, second_load.input_signal_count)
        self.assertEqual(
            count_rows_by_table(database_path, "signals"),
            first_load.input_signal_count + 12,
        )
        self.assertEqual(result.computed_count, 3)
        self.assertEqual(result.skipped_count, 1)
        self.assertEqual(statuses["AAPL"].composite_direction, "positive")
        self.assertEqual(statuses["MSFT"].composite_direction, "negative")
        self.assertIn("low_confidence_news_catalyst", statuses["MSFT"].data_warnings or "")
        self.assertIn("stale_news_catalyst_signal", statuses["NVDA"].data_warnings or "")
        self.assertIn("etf_news_catalyst_gated", statuses["SPY"].data_warnings or "")

    def test_compute_ticker_filter_only_writes_requested_output_signals(self) -> None:
        database_path = fresh_database_path("phase10e_filter.sqlite")
        config = make_config(database_path)
        initialize_database(database_path)
        upsert_asset(database_path, Asset(ticker="AAPL", asset_type="equity"))
        upsert_asset(database_path, Asset(ticker="MSFT", asset_type="equity"))
        today = date.today().isoformat()
        write_news_csv(
            config,
            [
                news_row(
                    ticker="AAPL",
                    signal_date=today,
                    source="manual_capture",
                    source_url="https://example.com/aapl",
                    headline_or_event="AAPL event",
                    catalyst_score=75,
                ),
                news_row(
                    ticker="MSFT",
                    signal_date=today,
                    source="manual_capture",
                    source_url="https://example.com/msft",
                    headline_or_event="MSFT event",
                    catalyst_score=25,
                ),
            ],
        )

        result = compute_news_catalyst_signals(config, ticker="AAPL")
        output_signals = list_signals(database_path, signal_family="news_catalyst")

        self.assertEqual(result.computed_count, 1)
        self.assertEqual([item.ticker for item in result.results], ["AAPL"])
        self.assertEqual({signal.ticker for signal in output_signals}, {"AAPL"})

    def test_validation_computes_directional_hits_and_ticker_filter(self) -> None:
        database_path = fresh_database_path("phase10e_validation.sqlite")
        config = make_config(database_path)
        initialize_database(database_path)
        for ticker, asset_type in (
            ("AAPL", "equity"),
            ("MSFT", "equity"),
            ("NVDA", "equity"),
            ("SPY", "etf"),
        ):
            upsert_asset(database_path, Asset(ticker=ticker, asset_type=asset_type))
        write_news_csv(
            config,
            [
                news_row(
                    ticker="AAPL",
                    signal_date="2026-01-10",
                    source="manual_capture",
                    source_url="https://example.com/aapl",
                    headline_or_event="Positive AAPL event",
                    catalyst_score=80,
                ),
                news_row(
                    ticker="MSFT",
                    signal_date="2026-01-10",
                    source="manual_capture",
                    source_url="https://example.com/msft",
                    headline_or_event="Negative MSFT event",
                    catalyst_score=20,
                ),
                news_row(
                    ticker="NVDA",
                    signal_date="2026-01-10",
                    source="manual_capture",
                    source_url="https://example.com/nvda",
                    headline_or_event="Neutral NVDA event",
                    catalyst_score=50,
                ),
            ],
        )
        start = date(2026, 1, 1)
        seed_price_history(database_path, "AAPL", start, [100 + offset for offset in range(30)])
        seed_price_history(database_path, "MSFT", start, [200 - offset for offset in range(30)])
        seed_price_history(database_path, "NVDA", start, [300 + offset for offset in range(10)])
        compute_news_catalyst_signals(config)

        result = validate_news_catalyst_signals(config)
        statuses = {
            status.ticker: status
            for status in signal_outcome_statuses(
                database_path,
                signal_family="news_catalyst",
                signal_name="news_catalyst.composite",
            )
        }

        self.assertEqual(result.updated_count, 3)
        self.assertEqual(result.skipped_count, 1)
        self.assertEqual(statuses["AAPL"].outcome_status, "partial")
        self.assertEqual(statuses["AAPL"].directional_hit_flag, 1)
        self.assertEqual(statuses["MSFT"].directional_hit_flag, 1)
        self.assertEqual(statuses["NVDA"].outcome_status, "pending")
        self.assertEqual(statuses["NVDA"].hit_status, "neutral")

        filtered_database = fresh_database_path("phase10e_validation_filter.sqlite")
        filtered_config = make_config(filtered_database)
        initialize_database(filtered_database)
        upsert_asset(filtered_database, Asset(ticker="AAPL", asset_type="equity"))
        upsert_asset(filtered_database, Asset(ticker="MSFT", asset_type="equity"))
        write_news_csv(
            filtered_config,
            [
                news_row(
                    ticker="AAPL",
                    signal_date="2026-01-10",
                    source="manual_capture",
                    source_url="https://example.com/aapl",
                    headline_or_event="Positive AAPL event",
                    catalyst_score=80,
                ),
                news_row(
                    ticker="MSFT",
                    signal_date="2026-01-10",
                    source="manual_capture",
                    source_url="https://example.com/msft",
                    headline_or_event="Negative MSFT event",
                    catalyst_score=20,
                ),
            ],
        )
        seed_price_history(filtered_database, "AAPL", start, [100 + offset for offset in range(30)])
        seed_price_history(filtered_database, "MSFT", start, [200 - offset for offset in range(30)])
        compute_news_catalyst_signals(filtered_config)
        filtered_result = validate_news_catalyst_signals(filtered_config, ticker="AAPL")

        self.assertEqual(filtered_result.updated_count, 1)
        self.assertEqual({item.ticker for item in filtered_result.results}, {"AAPL"})
        self.assertEqual(
            {
                item.ticker
                for item in list_signal_outcomes(
                    filtered_database,
                    signal_family="news_catalyst",
                    signal_name="news_catalyst.composite",
                )
            },
            {"AAPL"},
        )

    def test_shadow_mode_does_not_change_scores_or_alerts(self) -> None:
        database_path = fresh_database_path("phase10e_shadow.sqlite")
        config = make_config(database_path)
        seed_equity_scoring_fixture(database_path)
        today = date.today().isoformat()

        compute_scores(config, ticker="AAPL")
        before_score = list_scores(database_path, "AAPL")[0].opportunity_score
        write_news_csv(
            config,
            [
                news_row(
                    ticker="AAPL",
                    signal_date=today,
                    source="manual_capture",
                    source_url="https://example.com/aapl",
                    headline_or_event="Strong but shadow-only catalyst",
                    sentiment_score=100,
                    catalyst_score=100,
                    urgency_score=100,
                    confidence=100,
                )
            ],
        )
        compute_news_catalyst_signals(config, ticker="AAPL")
        compute_scores(config, ticker="AAPL")
        after_score = list_scores(database_path, "AAPL")[0].opportunity_score

        self.assertEqual(before_score, after_score)
        self.assertEqual(list_alerts(database_path), [])

    def test_cli_report_dashboard_status_and_pipeline_include_news_catalysts(self) -> None:
        database_path = fresh_database_path("phase10e_interfaces.sqlite")
        config = make_config(database_path)
        write_config(config)
        seed_equity_scoring_fixture(database_path)
        config.watchlist_path.write_text("ticker,asset_type\nAAPL,equity\n", encoding="utf-8")
        source_path = config.news_catalyst_source_exports_dir / "manual.csv"
        source_path.parent.mkdir(parents=True, exist_ok=True)
        source_path.write_text(
            "\n".join(
                [
                    ",".join(SOURCE_EXPORT_HEADERS),
                    source_export_row(
                        ticker="AAPL",
                        signal_date=date.today().isoformat(),
                        source="alpha_vantage",
                        source_url="https://example.com/aapl",
                        headline_or_event="AAPL source-backed catalyst",
                        sentiment_score=75,
                        catalyst_score=80,
                        urgency_score=65,
                        relevance_score=90,
                        confidence=85,
                    ),
                    "",
                ]
            ),
            encoding="utf-8",
        )
        seed_price_history(database_path, "AAPL", date.today() - timedelta(days=5), [100, 101, 102])

        import_output = io.StringIO()
        with redirect_stdout(import_output):
            import_exit = command_import_news_catalyst_source_exports(
                Namespace(config=config.config_path, dir=config.news_catalyst_source_exports_dir)
            )
        backfill_output = io.StringIO()
        with redirect_stdout(backfill_output):
            backfill_exit = command_compute_news_catalyst_text_backfill(
                Namespace(config=config.config_path, ticker=None)
            )
        aggregate_output = io.StringIO()
        with redirect_stdout(aggregate_output):
            aggregate_exit = command_aggregate_news_catalyst_sources(
                Namespace(config=config.config_path, ticker=None)
            )
        source_status_output = io.StringIO()
        with redirect_stdout(source_status_output):
            source_status_exit = command_news_catalyst_source_status(
                Namespace(config=config.config_path)
            )
        validate_backfill_output = io.StringIO()
        with redirect_stdout(validate_backfill_output):
            validate_backfill_exit = command_validate_news_catalyst_provider_backfill(
                Namespace(config=config.config_path, dir=None)
            )
        preview_upgrade_output = io.StringIO()
        with redirect_stdout(preview_upgrade_output):
            preview_upgrade_exit = command_preview_news_catalyst_provider_upgrade(
                Namespace(config=config.config_path, dir=None)
            )
        backfill_status_output = io.StringIO()
        with redirect_stdout(backfill_status_output):
            backfill_status_exit = command_news_catalyst_provider_backfill_status(
                Namespace(config=config.config_path, dir=None, allow_partial=False)
            )
        apply_backfill_output = io.StringIO()
        with redirect_stdout(apply_backfill_output):
            apply_backfill_exit = command_apply_news_catalyst_provider_backfill(
                Namespace(
                    config=config.config_path,
                    dir=None,
                    confirm=False,
                    allow_partial=False,
                )
            )
        load_output = io.StringIO()
        with redirect_stdout(load_output):
            load_exit = command_load_news_catalysts(Namespace(config=config.config_path, file=None))
        compute_output = io.StringIO()
        with redirect_stdout(compute_output):
            compute_exit = command_compute_news_catalyst_signals(
                Namespace(config=config.config_path, ticker="AAPL")
            )
        status_output = io.StringIO()
        with redirect_stdout(status_output):
            news_status_exit = command_news_catalyst_status(Namespace(config=config.config_path))
        validation_output = io.StringIO()
        with redirect_stdout(validation_output):
            validation_exit = command_validate_news_catalyst_signals(
                Namespace(config=config.config_path, ticker="AAPL")
            )
        validation_report_output = io.StringIO()
        with redirect_stdout(validation_report_output):
            validation_report_exit = command_news_catalyst_validation_report(
                Namespace(config=config.config_path)
            )
        system_status_output = io.StringIO()
        with redirect_stdout(system_status_output):
            system_status_exit = command_status(Namespace(config=config.config_path))

        report = write_daily_report(config)
        csv_text = report.csv_path.read_text(encoding="utf-8")
        markdown = report.path.read_text(encoding="utf-8")
        dashboard = build_dashboard(config)
        dashboard_text = dashboard.path.read_text(encoding="utf-8")
        data = dashboard_data(dashboard_text)

        self.assertEqual(import_exit, 0)
        self.assertEqual(backfill_exit, 0)
        self.assertEqual(aggregate_exit, 0)
        self.assertEqual(source_status_exit, 0)
        self.assertEqual(validate_backfill_exit, 0)
        self.assertEqual(preview_upgrade_exit, 0)
        self.assertEqual(backfill_status_exit, 0)
        self.assertEqual(apply_backfill_exit, 0)
        self.assertEqual(load_exit, 0)
        self.assertEqual(compute_exit, 0)
        self.assertEqual(news_status_exit, 0)
        self.assertEqual(validation_exit, 0)
        self.assertEqual(validation_report_exit, 0)
        self.assertEqual(system_status_exit, 0)
        self.assertIn("News/catalysts loaded", load_output.getvalue())
        self.assertIn("News/catalyst signal computation complete", compute_output.getvalue())
        self.assertIn("AAPL", status_output.getvalue())
        self.assertIn("News/catalyst signal validation complete", validation_output.getvalue())
        self.assertIn(
            "News/Catalyst Signal Validation Report",
            validation_report_output.getvalue(),
        )
        self.assertIn("News/catalyst file:", system_status_output.getvalue())
        self.assertIn("News/catalyst signal rows:", system_status_output.getvalue())
        self.assertIn("News/catalyst missing source-backed tickers:", system_status_output.getvalue())
        self.assertIn("News/catalyst coverage-plan tickers:", system_status_output.getvalue())
        self.assertIn("News/catalyst provider-upgrade status:", system_status_output.getvalue())
        self.assertIn("News/catalyst backfill valid rows:", system_status_output.getvalue())
        self.assertIn(
            "News/catalyst projected provider-native coverage:",
            system_status_output.getvalue(),
        )
        self.assertIn("News/catalyst backfill apply ready:", system_status_output.getvalue())
        self.assertIn("News/catalyst valid upgrade tickers:", system_status_output.getvalue())
        self.assertIn("News/catalyst projected upgrade delta:", system_status_output.getvalue())
        self.assertIn("News/catalyst blocked apply reason:", system_status_output.getvalue())
        self.assertIn("News/catalyst source exports imported", import_output.getvalue())
        self.assertIn("News/catalyst text backfill complete", backfill_output.getvalue())
        self.assertIn("News/catalyst sources aggregated", aggregate_output.getvalue())
        self.assertIn("Source-backed ticker coverage", source_status_output.getvalue())
        self.assertIn("Cache files", source_status_output.getvalue())
        self.assertIn("Provider Backfill Validation", validate_backfill_output.getvalue())
        self.assertIn("Provider Upgrade Preview", preview_upgrade_output.getvalue())
        self.assertIn("Provider Backfill Status", backfill_status_output.getvalue())
        self.assertIn("Dry run: True", apply_backfill_output.getvalue())
        self.assertIn("news_catalyst_score", csv_text)
        self.assertIn("news_catalyst_source_count", csv_text)
        self.assertIn("news_catalyst_numeric_source_type", csv_text)
        self.assertIn("news_catalyst_provider_numeric_coverage_count", csv_text)
        self.assertIn("news_catalyst_text_derived_coverage_count", csv_text)
        self.assertIn("news_catalyst_total_numeric_coverage_count", csv_text)
        self.assertIn("news_catalyst_coverage_priority", csv_text)
        self.assertIn("news_catalyst_provider_upgrade_status", csv_text)
        self.assertIn("news_catalyst_provider_upgrade_blockers", csv_text)
        self.assertIn("news_catalyst_provider_native_rejected_rows", csv_text)
        self.assertIn("news_catalyst_latest_provider_native_source_date", csv_text)
        self.assertIn("news_catalyst_backfill_valid_rows", csv_text)
        self.assertIn("news_catalyst_backfill_blank_placeholders", csv_text)
        self.assertIn("news_catalyst_backfill_invalid_rows", csv_text)
        self.assertIn("news_catalyst_projected_provider_native_coverage_count", csv_text)
        self.assertIn("news_catalyst_provider_upgrade_still_blocked_tickers", csv_text)
        self.assertIn("news_catalyst_backfill_apply_ready", csv_text)
        self.assertIn("news_catalyst_valid_upgrade_tickers", csv_text)
        self.assertIn("news_catalyst_projected_upgrade_delta", csv_text)
        self.assertIn("news_catalyst_blocked_apply_reason", csv_text)
        self.assertIn("news_catalyst_provider_warnings", csv_text)
        self.assertIn("news_catalyst_validation_status", csv_text)
        self.assertIn("News/catalyst signal coverage", markdown)
        self.assertIn("News/catalyst source-backed coverage", markdown)
        self.assertIn("News/catalyst provider-numeric coverage", markdown)
        self.assertIn("News/catalyst text-derived numeric coverage", markdown)
        self.assertIn("News/catalyst total numeric coverage", markdown)
        self.assertIn("News/catalyst coverage-plan tickers", markdown)
        self.assertIn("News/catalyst coverage queue stale", markdown)
        self.assertIn("News/catalyst provider-upgrade status", markdown)
        self.assertIn("News/catalyst provider-upgrade blockers", markdown)
        self.assertIn("News/catalyst rejected provider-native rows", markdown)
        self.assertIn("Latest news/catalyst provider-native source date", markdown)
        self.assertIn("News/catalyst backfill valid rows", markdown)
        self.assertIn("News/catalyst projected provider-native coverage", markdown)
        self.assertIn("News/catalyst still-blocked provider-native tickers", markdown)
        self.assertIn("News/catalyst backfill apply ready", markdown)
        self.assertIn("News/catalyst valid upgrade tickers", markdown)
        self.assertIn("News/catalyst projected upgrade delta", markdown)
        self.assertIn("News/catalyst blocked apply reason", markdown)
        self.assertIn("News/catalyst provider smoke-test command", markdown)
        self.assertIn("News/catalyst provider warnings", markdown)
        self.assertIn("News/catalyst cache files", markdown)
        self.assertIn("News/Catalyst Status", dashboard_text)
        self.assertIn("News Source Type", dashboard_text)
        self.assertIn("News Provider Numeric", dashboard_text)
        self.assertIn("News Text-Derived", dashboard_text)
        self.assertIn("News Coverage Plan", dashboard_text)
        self.assertIn("Provider Upgrade Status", dashboard_text)
        self.assertIn("Provider Upgrade Blockers", dashboard_text)
        self.assertIn("Rejected Provider-Native Rows", dashboard_text)
        self.assertIn("Backfill Valid Rows", dashboard_text)
        self.assertIn("Projected Provider-Native", dashboard_text)
        self.assertIn("Still Blocked Provider-Native", dashboard_text)
        self.assertIn("Backfill Apply Ready", dashboard_text)
        self.assertIn("Valid Upgrade Tickers", dashboard_text)
        self.assertIn("Projected Upgrade Delta", dashboard_text)
        self.assertIn("Blocked Apply Reason", dashboard_text)
        self.assertIn("Latest Provider-Native Date", dashboard_text)
        self.assertIn("News Smoke Test", dashboard_text)
        self.assertIn("News Provider Warnings", dashboard_text)
        self.assertEqual(data["rows"][0]["news_catalyst_signal_status"].split("@")[0], "positive")
        self.assertEqual(data["rows"][0]["news_catalyst_source_status"].split("@")[0], "source_backed")
        self.assertEqual(data["rows"][0]["news_catalyst_numeric_source_type"], "provider_numeric")
        self.assertEqual(data["health"]["news_catalyst_source_backed_ticker_count"], 1)
        self.assertEqual(data["health"]["news_catalyst_provider_numeric_ticker_count"], 1)
        self.assertEqual(data["health"]["news_catalyst_text_derived_ticker_count"], 0)
        self.assertEqual(data["health"]["news_catalyst_total_numeric_ticker_count"], 1)
        self.assertEqual(data["health"]["news_catalyst_provider_upgrade_status"], "provider_native_complete")
        self.assertIn("news_catalyst_provider_upgrade_blockers", data["health"])
        self.assertIn("news_catalyst_provider_native_rejected_row_count", data["health"])
        self.assertIn("news_catalyst_latest_provider_native_source_date", data["health"])
        self.assertIn("news_catalyst_backfill_valid_row_count", data["health"])
        self.assertIn("news_catalyst_backfill_invalid_row_count", data["health"])
        self.assertIn("news_catalyst_projected_provider_native_ticker_count", data["health"])
        self.assertIn("news_catalyst_provider_upgrade_still_blocked_tickers", data["health"])
        self.assertIn("news_catalyst_backfill_apply_ready", data["health"])
        self.assertIn("news_catalyst_valid_upgrade_tickers", data["health"])
        self.assertIn("news_catalyst_projected_upgrade_delta", data["health"])
        self.assertIn("news_catalyst_blocked_apply_reason", data["health"])
        self.assertIn("test-news-catalyst-provider", data["health"]["news_catalyst_provider_smoke_test_command"])
        self.assertIn("news_catalyst_coverage_plan", data)
        self.assertIsInstance(data["news_catalyst_coverage_plan"]["template_path"], str)
        self.assertTrue(data["signal_outcomes"])

        with patch_refresh_pipeline_for_test(
            _news_catalyst_aggregation_step=(1, ()),
            _news_catalyst_load_step=(1, ()),
            _news_catalyst_signal_step=(1, ()),
            _news_catalyst_validation_step=(1, ()),
        ):
            pipeline_result = run_refresh_data(config, skip_ibkr=True)
        step_names = [step.step_name for step in pipeline_result.steps]
        self.assertIn("fetch-news-catalyst-sources", step_names)
        self.assertIn("import-news-catalyst-source-exports", step_names)
        self.assertIn("compute-news-catalyst-text-backfill", step_names)
        self.assertIn("aggregate-news-catalyst-sources", step_names)
        self.assertIn("load-news-catalysts", step_names)
        self.assertIn("compute-news-catalyst-signals", step_names)
        self.assertIn("validate-news-catalyst-signals", step_names)


if __name__ == "__main__":
    unittest.main()
