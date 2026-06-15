from __future__ import annotations

from argparse import Namespace
from contextlib import redirect_stdout
from datetime import date, timedelta
from pathlib import Path
import io
import json
import re
import sys
import unittest
from unittest.mock import patch


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
TEST_TMP_ROOT = PROJECT_ROOT / ".tmp_tests"
sys.path.insert(0, str(SRC_PATH))

from support import patch_refresh_pipeline_for_test, sqlite_connection_for_test
from target_opportunity_monitor.cli import (
    command_aggregate_revision_sources,
    command_compute_revision_signals,
    command_derive_analyst_revisions,
    command_fetch_revision_sources,
    command_import_revision_source_exports,
    command_load_analyst_revisions,
    command_revision_provider_status,
    command_revision_evidence_report,
    command_revision_source_status,
    command_revision_validation_report,
    command_signal_status,
    command_status,
    command_validate_revision_signals,
)
from target_opportunity_monitor.config import AppConfig, load_config
from target_opportunity_monitor.dashboard import build_dashboard
from target_opportunity_monitor.db import initialize_database
from target_opportunity_monitor.pipeline import run_refresh_data
from target_opportunity_monitor.reporting import write_daily_report
from target_opportunity_monitor.revision_evidence import (
    DECISION_COLLECTING,
    DECISION_ELIGIBLE,
    DECISION_INSUFFICIENT_SOURCE,
    DECISION_KEEP_SHADOW,
    build_revision_evidence,
    derive_eps_revision,
    derive_estimate_dispersion,
    derive_recommendation_revision,
)
from target_opportunity_monitor.revision_sources import (
    SOURCE_EXPORT_HEADERS,
    aggregate_revision_sources,
    derive_analyst_revision_input,
    derive_analyst_revisions_from_source_export,
    ensure_analyst_revision_source_export_header,
    fetch_revision_sources,
    import_revision_source_exports,
    parse_analyst_revision_source_export_csv,
    revision_provider_statuses,
    revision_source_status_report,
)
from target_opportunity_monitor.scoring import compute_scores
from target_opportunity_monitor.signal_validation import (
    evaluate_revision_signal_outcome,
    validate_revision_signals,
)
from target_opportunity_monitor.signals import (
    compute_revision_signals,
    ensure_analyst_revision_csv_header,
    load_analyst_revisions_csv,
    parse_analyst_revisions_csv,
)
from target_opportunity_monitor.storage import (
    Asset,
    Estimate,
    Fundamental,
    PriceFeature,
    Signal,
    Target,
    count_rows_by_table,
    list_analyst_revision_aggregates,
    list_analyst_revision_source_snapshots,
    latest_signal_date,
    latest_signal_outcome_date,
    list_scores,
    list_signal_outcomes,
    list_signals,
    list_prices,
    list_stored_signals,
    signal_statuses,
    signal_outcome_statuses,
    upsert_asset,
    upsert_estimate,
    upsert_fundamental,
    upsert_price_feature,
    upsert_prices,
    upsert_signal_outcome,
    upsert_signal,
    upsert_target,
    Price,
    SignalOutcome,
)


def make_config(database_path: Path, shadow_mode: bool = True) -> AppConfig:
    return AppConfig(
        project_root=TEST_TMP_ROOT,
        config_path=TEST_TMP_ROOT / f"phase10a_{database_path.stem}.toml",
        database_path=database_path,
        reports_dir=TEST_TMP_ROOT / "reports_phase10a",
        watchlist_path=TEST_TMP_ROOT / "watchlist_phase10a.csv",
        market_data_dir=TEST_TMP_ROOT / "market_data_phase10a",
        manual_prices_dir=TEST_TMP_ROOT / "market_data_phase10a" / "manual",
        market_data_primary_source="stooq",
        market_data_secondary_source="yahoo_chart",
        market_data_mode="csv",
        market_data_lookback_days=800,
        market_data_stale_after_days=7,
        market_data_minimum_history_days=252,
        universe_mode="manual_watchlist",
        run_mode="daily_scoring",
        report_title="Target Opportunity Monitor Daily Report",
        analyst_revisions_path=TEST_TMP_ROOT / "signals" / f"{database_path.stem}.csv",
        analyst_revision_source_export_path=(
            TEST_TMP_ROOT / "signals" / "source_exports" / f"{database_path.stem}.csv"
        ),
        analyst_revision_source_exports_dir=(
            TEST_TMP_ROOT / "signals" / "source_exports" / f"{database_path.stem}_dir"
        ),
        signals_analyst_revision_model_version="analyst_revision_mvp_v1",
        signals_analyst_revision_shadow_mode=shadow_mode,
        signals_minimum_revision_inputs=1,
        signals_stale_after_days=45,
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
                f'analyst_revisions = "{config.analyst_revisions_path.as_posix()}"',
                (
                    "analyst_revision_source_export = "
                    f'"{config.analyst_revision_source_export_path.as_posix()}"'
                ),
                (
                    "analyst_revision_source_exports_dir = "
                    f'"{config.analyst_revision_source_exports_dir.as_posix()}"'
                ),
                "",
                "[signals]",
                f'analyst_revision_model_version = "{config.signals_analyst_revision_model_version}"',
                f"analyst_revision_shadow_mode = {str(config.signals_analyst_revision_shadow_mode).lower()}",
                f"minimum_revision_inputs = {config.signals_minimum_revision_inputs}",
                f"stale_after_days = {config.signals_stale_after_days}",
                (
                    'revision_provider_order = ["alpha_vantage", "fmp", '
                    '"business_quant", "finnhub", "yfinance", "ibkr", "source_export"]'
                ),
                (
                    'revision_enabled_providers = ["alpha_vantage", "fmp", '
                    '"business_quant", "finnhub", "yfinance", "source_export"]'
                ),
                'revision_source_policy = "weighted_median"',
                "revision_disagreement_warning_threshold = 0.05",
                "revision_high_disagreement_threshold = 0.10",
                "revision_min_sources_for_aggregate = 1",
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


def fresh_database_path(name: str) -> Path:
    TEST_TMP_ROOT.mkdir(exist_ok=True)
    path = TEST_TMP_ROOT / name
    if path.exists():
        path.unlink()
    return path


def write_revision_csv(config: AppConfig, rows: list[str]) -> None:
    config.analyst_revisions_path.parent.mkdir(parents=True, exist_ok=True)
    config.analyst_revisions_path.write_text(
        "\n".join(
            [
                "ticker,signal_date,eps_revision_1m,eps_revision_3m,revenue_revision_1m,revenue_revision_3m,target_price_revision_3m,recommendation_revision,estimate_dispersion,analyst_count,source,as_of_date,effective_date",
                *rows,
                "",
            ]
        ),
        encoding="utf-8",
    )


def write_source_revision_csv(config: AppConfig, rows: list[str]) -> None:
    config.analyst_revisions_path.parent.mkdir(parents=True, exist_ok=True)
    config.analyst_revisions_path.write_text(
        "\n".join(
            [
                "ticker,signal_date,eps_revision_1m,eps_revision_3m,revenue_revision_1m,revenue_revision_3m,target_price_revision_3m,recommendation_revision,estimate_dispersion,analyst_count,source,source_url,notes,as_of_date,effective_date",
                *rows,
                "",
            ]
        ),
        encoding="utf-8",
    )


def source_export_row(**values: object) -> str:
    row = {header: "" for header in SOURCE_EXPORT_HEADERS}
    row.update({key: str(value) for key, value in values.items() if value is not None})
    return ",".join(row[header] for header in SOURCE_EXPORT_HEADERS)


def write_source_export_csv(config: AppConfig, rows: list[str]) -> None:
    config.analyst_revision_source_export_path.parent.mkdir(parents=True, exist_ok=True)
    config.analyst_revision_source_export_path.write_text(
        "\n".join([",".join(SOURCE_EXPORT_HEADERS), *rows, ""]),
        encoding="utf-8",
    )


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


def seed_equity_fixture(database_path: Path, ticker: str = "AAPL") -> None:
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


class Phase10AAnalystRevisionSignalTests(unittest.TestCase):
    def test_config_defaults_and_signal_schema_metadata(self) -> None:
        config = load_config()
        self.assertEqual(
            config.analyst_revisions_path,
            PROJECT_ROOT / "data" / "signals" / "manual" / "analyst_revisions.csv",
        )
        self.assertEqual(
            config.analyst_revision_source_export_path,
            PROJECT_ROOT
            / "data"
            / "signals"
            / "source_exports"
            / "analyst_revision_source_export.csv",
        )
        self.assertEqual(
            config.analyst_revision_source_exports_dir,
            PROJECT_ROOT / "data" / "signals" / "source_exports",
        )
        self.assertEqual(config.signals_analyst_revision_model_version, "analyst_revision_mvp_v1")
        self.assertTrue(config.signals_analyst_revision_shadow_mode)
        self.assertEqual(config.signals_minimum_revision_inputs, 1)
        self.assertEqual(config.signals_revision_evidence_min_source_tickers, 3)
        self.assertEqual(config.signals_revision_evidence_min_signal_tickers, 3)
        self.assertEqual(config.signals_revision_evidence_min_completed_20d, 3)
        self.assertEqual(config.signals_revision_evidence_min_hit_rate_20d, 0.55)
        self.assertEqual(config.signals_revision_evidence_min_avg_return_20d, 0.0)
        self.assertEqual(config.signals_revision_evidence_min_confidence, 60)
        self.assertEqual(
            config.signals_revision_provider_order,
            (
                "alpha_vantage",
                "fmp",
                "business_quant",
                "finnhub",
                "yfinance",
                "ibkr",
                "source_export",
            ),
        )
        self.assertEqual(
            config.signals_revision_enabled_providers,
            ("alpha_vantage", "fmp", "business_quant", "finnhub", "yfinance", "source_export"),
        )
        self.assertEqual(config.signals_revision_source_policy, "weighted_median")
        self.assertEqual(config.signals_revision_disagreement_warning_threshold, 0.05)
        self.assertEqual(config.signals_revision_high_disagreement_threshold, 0.10)
        self.assertEqual(config.signals_revision_min_sources_for_aggregate, 1)

        database_path = fresh_database_path("phase10a_schema.sqlite")
        initialize_database(database_path)
        with sqlite_connection_for_test(database_path) as connection:
            columns = {
                row[1]
                for row in connection.execute("PRAGMA table_info(signals)").fetchall()
            }
        self.assertIn("model_version", columns)
        self.assertIn("confidence", columns)
        self.assertIn("data_warnings", columns)
        self.assertIn("source_url", columns)
        self.assertIn("notes", columns)
        with sqlite_connection_for_test(database_path) as connection:
            tables = {
                row[0]
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                ).fetchall()
            }
            index_names = {
                row[1]
                for row in connection.execute(
                    "PRAGMA index_list(signal_outcomes)"
                ).fetchall()
            }
        self.assertIn("signal_outcomes", tables)
        self.assertIn("analyst_revision_source_snapshots", tables)
        self.assertIn("analyst_revision_aggregates", tables)
        self.assertIn("idx_signal_outcomes_identity", index_names)

    def test_phase10c_derivation_helpers(self) -> None:
        self.assertAlmostEqual(derive_eps_revision(10.5, 10.0) or 0, 0.05)
        self.assertIsNone(derive_eps_revision(10.5, 0))
        self.assertAlmostEqual(derive_estimate_dispersion(12, 8, 10) or 0, 0.4)
        self.assertIsNone(derive_estimate_dispersion(12, 8, 0))

        current = {"strongBuy": 10, "buy": 5, "hold": 5, "sell": 0, "strongSell": 0}
        prior = {"strongBuy": 5, "buy": 5, "hold": 10, "sell": 0, "strongSell": 0}
        self.assertAlmostEqual(derive_recommendation_revision(current, prior) or 0, 0.5)

    def test_phase10c1_source_export_header_parser_and_derivation(self) -> None:
        database_path = fresh_database_path("phase10c1_parser.sqlite")
        config = make_config(database_path)
        ensure_analyst_revision_source_export_header(
            config.analyst_revision_source_export_path
        )
        self.assertTrue(config.analyst_revision_source_export_path.exists())
        self.assertIn(
            "eps_current",
            config.analyst_revision_source_export_path.read_text(encoding="utf-8"),
        )

        row = source_export_row(
            ticker="aapl",
            signal_date="2026-06-07",
            source="yahoo_analysis_manual_capture",
            source_url="https://finance.yahoo.com/quote/AAPL/analysis/",
            notes="Yahoo Analysis EPS and recommendation tables captured manually",
            eps_current=10.5,
            eps_30d_ago=10.0,
            eps_90d_ago=9.0,
            eps_high=12,
            eps_low=8,
            eps_average=10,
            analyst_count=31,
            revenue_current=420,
            revenue_30d_ago=400,
            revenue_90d_ago=390,
            target_price_current=230,
            target_price_90d_ago=220,
            recommendation_current_strong_buy=10,
            recommendation_current_buy=5,
            recommendation_current_hold=5,
            recommendation_current_sell=0,
            recommendation_current_strong_sell=0,
            recommendation_90d_ago_strong_buy=5,
            recommendation_90d_ago_buy=5,
            recommendation_90d_ago_hold=10,
            recommendation_90d_ago_sell=0,
            recommendation_90d_ago_strong_sell=0,
        )
        rows = parse_analyst_revision_source_export_csv(
            "\n".join([",".join(SOURCE_EXPORT_HEADERS), row, ""])
        )
        derived = derive_analyst_revision_input(rows[0])
        self.assertEqual(rows[0].ticker, "AAPL")
        self.assertAlmostEqual(derived.eps_revision_1m or 0, 0.05)
        self.assertAlmostEqual(derived.eps_revision_3m or 0, 10.5 / 9.0 - 1)
        self.assertAlmostEqual(derived.revenue_revision_1m or 0, 0.05)
        self.assertAlmostEqual(derived.target_price_revision_3m or 0, 230 / 220 - 1)
        self.assertAlmostEqual(derived.recommendation_revision or 0, 0.5)
        self.assertAlmostEqual(derived.estimate_dispersion or 0, 0.4)
        self.assertEqual(derived.analyst_count, 31)
        self.assertEqual(derived.source_url, "https://finance.yahoo.com/quote/AAPL/analysis/")

        with self.assertRaises(ValueError):
            parse_analyst_revision_source_export_csv(
                "\n".join(
                    [
                        ",".join(SOURCE_EXPORT_HEADERS),
                        source_export_row(
                            ticker="AAPL",
                            signal_date="2026-06-07",
                            source="provider",
                            source_url="",
                            notes="missing source url",
                            eps_current=10.5,
                            eps_30d_ago=10.0,
                        ),
                        "",
                    ]
                )
            )
        with self.assertRaises(ValueError):
            parse_analyst_revision_source_export_csv(
                "\n".join(
                    [
                        ",".join(SOURCE_EXPORT_HEADERS),
                        source_export_row(
                            ticker="AAPL",
                            signal_date="bad-date",
                            source="provider",
                            source_url="https://example.com",
                            notes="bad date",
                            eps_current=10.5,
                            eps_30d_ago=10.0,
                        ),
                        "",
                    ]
                )
            )
        with self.assertRaises(ValueError):
            parse_analyst_revision_source_export_csv(
                "\n".join(
                    [
                        ",".join(SOURCE_EXPORT_HEADERS),
                        source_export_row(
                            ticker="AAPL",
                            signal_date="2026-06-07",
                            source="provider",
                            source_url="https://example.com",
                            notes="analyst count alone is not derivable",
                            analyst_count=30,
                        ),
                        "",
                    ]
                )
            )

    def test_phase10c1_derive_source_export_is_idempotent_and_gates_etfs(self) -> None:
        database_path = fresh_database_path("phase10c1_derive.sqlite")
        config = make_config(database_path)
        write_config(config)
        initialize_database(database_path)
        for ticker in ("AAPL", "MSFT", "NVDA"):
            upsert_asset(database_path, Asset(ticker=ticker, asset_type="equity"))
        upsert_asset(database_path, Asset(ticker="SPY", asset_type="etf"))

        rows = []
        for offset, ticker in enumerate(("AAPL", "MSFT", "NVDA", "SPY")):
            rows.append(
                source_export_row(
                    ticker=ticker,
                    signal_date="2026-06-07",
                    source="provider_export",
                    source_url=f"https://example.com/{ticker.lower()}/analysis",
                    notes=f"Provider EPS trend export for {ticker}",
                    eps_current=10.0 + offset,
                    eps_30d_ago=9.5 + offset,
                    eps_90d_ago=9.0 + offset,
                    eps_high=12.0 + offset,
                    eps_low=8.0 + offset,
                    eps_average=10.0 + offset,
                    analyst_count=20 + offset,
                )
            )
        write_source_export_csv(config, rows)

        first = derive_analyst_revisions_from_source_export(config)
        second = derive_analyst_revisions_from_source_export(config)
        self.assertEqual(first.derived_row_count, 3)
        self.assertEqual(second.derived_row_count, 3)
        self.assertEqual(first.skipped_count, 1)
        self.assertIn("SPY:etf_revision_source_gated", first.warnings)
        final_rows = [
            line
            for line in config.analyst_revisions_path.read_text(encoding="utf-8").splitlines()[1:]
            if line.strip()
        ]
        self.assertEqual(len(final_rows), 3)

        load_result = load_analyst_revisions_csv(config)
        signal_result = compute_revision_signals(config)
        evidence = build_revision_evidence(config)
        source_status = revision_source_status_report(config)

        self.assertEqual(load_result.row_count, 3)
        self.assertEqual(signal_result.computed_count, 3)
        self.assertEqual(evidence.decision, DECISION_COLLECTING)
        self.assertEqual(source_status.source_backed_ticker_count, 3)
        self.assertEqual(source_status.skipped_etf_tickers, ("SPY",))

        derive_output = io.StringIO()
        with redirect_stdout(derive_output):
            derive_exit = command_derive_analyst_revisions(
                Namespace(config=config.config_path, file=None)
            )
        status_output = io.StringIO()
        with redirect_stdout(status_output):
            source_status_exit = command_revision_source_status(
                Namespace(config=config.config_path)
            )
        self.assertEqual(derive_exit, 0)
        self.assertEqual(source_status_exit, 0)
        self.assertIn("Analyst revisions derived", derive_output.getvalue())
        self.assertIn("Source-backed ticker coverage: 3/3", status_output.getvalue())
        self.assertIn("Skipped ETF source rows: SPY", status_output.getvalue())

    def test_phase10c2_imports_multiple_sources_and_aggregates_without_duplicates(self) -> None:
        database_path = fresh_database_path("phase10c2_aggregate.sqlite")
        config = make_config(database_path)
        initialize_database(database_path)
        for ticker in ("AAPL", "MSFT", "NVDA"):
            upsert_asset(database_path, Asset(ticker=ticker, asset_type="equity"))

        source_dir = config.analyst_revision_source_exports_dir
        source_dir.mkdir(parents=True, exist_ok=True)
        (source_dir / "fmp.csv").write_text(
            "\n".join(
                [
                    ",".join(SOURCE_EXPORT_HEADERS),
                    source_export_row(
                        ticker="AAPL",
                        signal_date="2026-06-07",
                        source="fmp",
                        source_url="https://financialmodelingprep.com/api/v3/analyst-estimates/AAPL",
                        notes="FMP provider export",
                        eps_current=10.0,
                        eps_30d_ago=9.5,
                        eps_90d_ago=9.0,
                        eps_high=11.0,
                        eps_low=9.0,
                        eps_average=10.0,
                        analyst_count=30,
                    ),
                    "",
                ]
            ),
            encoding="utf-8",
        )
        (source_dir / "secbot.csv").write_text(
            "\n".join(
                [
                    ",".join(SOURCE_EXPORT_HEADERS),
                    source_export_row(
                        ticker="AAPL",
                        signal_date="2026-06-07",
                        source="secbot_public_page",
                        source_url="https://secbot.trade/stocks/aapl-apple-inc",
                        notes="SecBot public page capture",
                        eps_current=10.8,
                        eps_30d_ago=9.0,
                        eps_90d_ago=8.8,
                        eps_high=12.0,
                        eps_low=8.0,
                        eps_average=10.0,
                        analyst_count=32,
                    ),
                    source_export_row(
                        ticker="MSFT",
                        signal_date="2026-06-07",
                        source="secbot_public_page",
                        source_url="https://secbot.trade/stocks/msft-microsoft-corp",
                        notes="SecBot public page capture",
                        eps_current=5.1,
                        eps_30d_ago=5.0,
                        eps_90d_ago=4.9,
                        eps_high=5.5,
                        eps_low=4.5,
                        eps_average=5.0,
                        analyst_count=28,
                    ),
                    "",
                ]
            ),
            encoding="utf-8",
        )

        import_result = import_revision_source_exports(config, directory=source_dir)
        aggregate_result = aggregate_revision_sources(config)
        snapshots = list_analyst_revision_source_snapshots(database_path, "AAPL")
        aggregates = list_analyst_revision_aggregates(database_path, "AAPL")
        final_rows = [
            line
            for line in config.analyst_revisions_path.read_text(encoding="utf-8").splitlines()[1:]
            if line.strip()
        ]

        self.assertEqual(import_result.imported_count, 3)
        self.assertEqual(len(snapshots), 2)
        self.assertEqual(aggregate_result.aggregate_count, 2)
        self.assertEqual(len(aggregates), 1)
        self.assertEqual(aggregates[0].source_count, 2)
        self.assertIn("fmp", aggregates[0].sources or "")
        self.assertIn("secbot_public_page", aggregates[0].sources or "")
        self.assertIn("source_disagreement", aggregates[0].data_warnings or "")
        self.assertGreater(aggregates[0].aggregate_confidence or 0, 50)
        self.assertEqual(len(final_rows), 2)
        self.assertIn("analyst_revision_aggregate", final_rows[0])

        load_result = load_analyst_revisions_csv(config)
        compute_result = compute_revision_signals(config, ticker="AAPL")
        raw_inputs = [
            signal
            for signal in list_signals(database_path, ticker="AAPL", signal_family="analyst_revision_input")
            if signal.signal_date == "2026-06-07"
        ]
        self.assertEqual(load_result.row_count, 2)
        self.assertEqual(compute_result.computed_count, 1)
        self.assertEqual({signal.source for signal in raw_inputs}, {"analyst_revision_aggregate"})

    def test_phase10c2_provider_status_and_mocked_fetchers(self) -> None:
        database_path = fresh_database_path("phase10c2_provider.sqlite")
        config = make_config(database_path)
        write_config(config)
        initialize_database(database_path)
        upsert_asset(database_path, Asset(ticker="AAPL", asset_type="equity"))

        statuses = {status.provider: status for status in revision_provider_statuses(config)}
        self.assertEqual(statuses["google_finance"].status, "unsupported")
        google_result = fetch_revision_sources(config, provider="google_finance")
        self.assertIn("google_finance_analyst_revisions_unsupported", google_result.warnings)

        fmp_payload = [
            {
                "epsAvg": 10.0,
                "epsHigh": 11.0,
                "epsLow": 9.0,
                "numAnalystsEps": 20,
            }
        ]
        alpha_payload = {
            "estimates": [
                {
                    "eps_estimate_average": "10.2",
                    "eps_estimate_average_30_days_ago": "10.0",
                    "eps_estimate_average_90_days_ago": "9.8",
                    "eps_estimate_high": "11.2",
                    "eps_estimate_low": "9.2",
                    "eps_estimate_analyst_count": "21",
                }
            ]
        }
        business_quant_eps_payload = {
            "data": [
                {
                    "dimension": "annual",
                    "estimates": [
                        {
                            "period": "2027",
                            "data_type": "estimate",
                            "value_estimate": "10.4",
                            "high_estimate": "11.5",
                            "low_estimate": "9.5",
                        }
                    ],
                }
            ]
        }
        business_quant_revenue_payload = {
            "data": [
                {
                    "dimension": "annual",
                    "estimates": [
                        {
                            "period": "2027",
                            "data_type": "estimate",
                            "value_estimate": "420000000000",
                        }
                    ],
                }
            ]
        }
        finnhub_payload = [
            {
                "period": "2026-06-01",
                "strongBuy": 10,
                "buy": 20,
                "hold": 5,
                "sell": 1,
                "strongSell": 0,
            },
            {
                "period": "2026-03-01",
                "strongBuy": 8,
                "buy": 18,
                "hold": 8,
                "sell": 1,
                "strongSell": 0,
            },
        ]

        with patch.dict("os.environ", {}, clear=True), patch(
            "target_opportunity_monitor.revision_sources._read_windows_registry_env",
            side_effect=lambda name: {
                "FMP_API_KEY": "test-fmp-key",
                "ALPHAVANTAGE_API_KEY": "test-alpha-key",
                "BUSINESSQUANT_API_KEY": "test-business-quant-key",
                "FINNHUB_API_KEY": "test-finnhub-key",
            }.get(name),
        ), patch(
            "target_opportunity_monitor.revision_sources._http_json",
            side_effect=[fmp_payload, alpha_payload],
        ):
            registry_statuses = {
                status.provider: status for status in revision_provider_statuses(config)
            }
            fmp_result = fetch_revision_sources(config, provider="fmp", ticker="AAPL")
            alpha_result = fetch_revision_sources(
                config,
                provider="alpha_vantage",
                ticker="AAPL",
            )

        self.assertEqual(registry_statuses["fmp"].status, "configured")
        self.assertEqual(registry_statuses["alpha_vantage"].status, "configured")
        self.assertEqual(registry_statuses["business_quant"].status, "configured")
        self.assertEqual(registry_statuses["finnhub"].status, "configured")
        self.assertEqual(fmp_result.stored_count, 1)
        self.assertEqual(alpha_result.stored_count, 1)

        with patch.dict("os.environ", {}, clear=True), patch(
            "target_opportunity_monitor.revision_sources._read_windows_registry_env",
            side_effect=lambda name: {"BUSINESSQUANT_API_KEY": "test-business-quant-key"}.get(
                name
            ),
        ), patch(
            "target_opportunity_monitor.revision_sources._http_json",
            side_effect=[business_quant_eps_payload, business_quant_revenue_payload],
        ):
            business_quant_result = fetch_revision_sources(
                config,
                provider="business_quant",
                ticker="AAPL",
            )

        with patch.dict("os.environ", {}, clear=True), patch(
            "target_opportunity_monitor.revision_sources._read_windows_registry_env",
            side_effect=lambda name: {"FINNHUB_API_KEY": "test-finnhub-key"}.get(name),
        ), patch(
            "target_opportunity_monitor.revision_sources._http_json",
            return_value=finnhub_payload,
        ):
            finnhub_result = fetch_revision_sources(
                config,
                provider="finnhub",
                ticker="AAPL",
            )

        self.assertEqual(business_quant_result.stored_count, 1)
        self.assertEqual(finnhub_result.stored_count, 1)
        self.assertEqual(
            {snapshot.source for snapshot in list_analyst_revision_source_snapshots(database_path)},
            {"fmp", "alpha_vantage", "business_quant", "finnhub"},
        )

        with patch.dict("os.environ", {}, clear=True), patch(
            "target_opportunity_monitor.revision_sources._read_windows_registry_env",
            side_effect=lambda name: {"FMP_API_KEY": "test-fmp-key"}.get(name),
        ), patch(
            "target_opportunity_monitor.revision_sources._http_json",
            return_value=[],
        ):
            fmp_failure_result = fetch_revision_sources(config, provider="fmp", ticker="AAPL")
        self.assertIn("AAPL:fmp_no_estimate_rows", fmp_failure_result.warnings)

        snapshots_by_source = {
            snapshot.source: snapshot
            for snapshot in list_analyst_revision_source_snapshots(database_path, "AAPL")
        }
        self.assertEqual(snapshots_by_source["fmp"].provider_status, "failed")
        aggregate_result = aggregate_revision_sources(config, ticker="AAPL")
        aggregate = list_analyst_revision_aggregates(database_path, "AAPL")[0]
        self.assertEqual(aggregate_result.aggregate_count, 1)
        self.assertNotIn("fmp", aggregate.sources or "")
        self.assertIn("alpha_vantage", aggregate.sources or "")
        self.assertIn("source_unavailable:fmp", aggregate.data_warnings or "")

        with patch.dict("os.environ", {}, clear=True), patch(
            "target_opportunity_monitor.revision_sources._read_windows_registry_env",
            side_effect=lambda name: {"ALPHAVANTAGE_API_KEY": "test-alpha-key"}.get(name),
        ), patch(
            "target_opportunity_monitor.revision_sources._http_json",
            return_value={"Information": "Please spread out your free API requests."},
        ):
            rate_result = fetch_revision_sources(
                config,
                provider="alpha_vantage",
                ticker="AAPL",
            )
        self.assertIn(
            "AAPL:alpha_vantage_rate_limited_or_plan_limited",
            rate_result.warnings,
        )

        fetch_output = io.StringIO()
        with patch.dict("os.environ", {}, clear=True), patch(
            "target_opportunity_monitor.revision_sources._read_windows_registry_env",
            return_value=None,
        ), redirect_stdout(fetch_output):
            fetch_exit = command_fetch_revision_sources(
                Namespace(config=config.config_path, provider="fmp", ticker="AAPL")
            )
        self.assertEqual(fetch_exit, 0)
        self.assertIn("missing_fmp_api_key", fetch_output.getvalue())
        self.assertNotIn("test-fmp-key", fetch_output.getvalue())

        provider_output = io.StringIO()
        with redirect_stdout(provider_output):
            provider_exit = command_revision_provider_status(Namespace(config=config.config_path))
        self.assertEqual(provider_exit, 0)
        self.assertIn("google_finance", provider_output.getvalue())

    def test_phase10c2_all_failed_provider_rows_remove_stale_aggregate(self) -> None:
        database_path = fresh_database_path("phase10c2_failed_aggregate.sqlite")
        config = make_config(database_path)
        initialize_database(database_path)
        upsert_asset(database_path, Asset(ticker="AAPL", asset_type="equity"))

        fmp_payload = [{"epsAvg": 10.0, "epsHigh": 11.0, "epsLow": 9.0}]
        with patch.dict("os.environ", {}, clear=True), patch(
            "target_opportunity_monitor.revision_sources._read_windows_registry_env",
            side_effect=lambda name: {"FMP_API_KEY": "test-fmp-key"}.get(name),
        ), patch(
            "target_opportunity_monitor.revision_sources._http_json",
            return_value=fmp_payload,
        ):
            fetch_revision_sources(config, provider="fmp", ticker="AAPL")
        first = aggregate_revision_sources(config, ticker="AAPL")
        self.assertEqual(first.aggregate_count, 1)
        self.assertEqual(len(list_analyst_revision_aggregates(database_path, "AAPL")), 1)

        with patch.dict("os.environ", {}, clear=True), patch(
            "target_opportunity_monitor.revision_sources._read_windows_registry_env",
            side_effect=lambda name: {"FMP_API_KEY": "test-fmp-key"}.get(name),
        ), patch(
            "target_opportunity_monitor.revision_sources._http_json",
            return_value=[],
        ):
            fetch_revision_sources(config, provider="fmp", ticker="AAPL")
        second = aggregate_revision_sources(config, ticker="AAPL")
        self.assertEqual(second.aggregate_count, 0)
        self.assertIn("AAPL:no_aggregatable_revision_fields", second.warnings)
        self.assertEqual(list_analyst_revision_aggregates(database_path, "AAPL"), [])

    def test_phase10c2_cli_import_aggregate_and_pipeline_steps(self) -> None:
        database_path = fresh_database_path("phase10c2_cli.sqlite")
        config = make_config(database_path)
        write_config(config)
        initialize_database(database_path)
        upsert_asset(database_path, Asset(ticker="AAPL", asset_type="equity"))
        config.analyst_revision_source_exports_dir.mkdir(parents=True, exist_ok=True)
        (config.analyst_revision_source_exports_dir / "provider.csv").write_text(
            "\n".join(
                [
                    ",".join(SOURCE_EXPORT_HEADERS),
                    source_export_row(
                        ticker="AAPL",
                        signal_date="2026-06-07",
                        source="provider_export",
                        source_url="https://example.com/aapl",
                        notes="Provider export",
                        eps_current=10.0,
                        eps_30d_ago=9.0,
                        eps_90d_ago=8.0,
                        eps_high=11.0,
                        eps_low=9.0,
                        eps_average=10.0,
                        analyst_count=20,
                    ),
                    "",
                ]
            ),
            encoding="utf-8",
        )

        import_output = io.StringIO()
        with redirect_stdout(import_output):
            import_exit = command_import_revision_source_exports(
                Namespace(config=config.config_path, dir=config.analyst_revision_source_exports_dir)
            )
        aggregate_output = io.StringIO()
        with redirect_stdout(aggregate_output):
            aggregate_exit = command_aggregate_revision_sources(
                Namespace(config=config.config_path, ticker=None)
            )

        self.assertEqual(import_exit, 0)
        self.assertEqual(aggregate_exit, 0)
        self.assertIn("Revision source exports imported", import_output.getvalue())
        self.assertIn("Revision sources aggregated", aggregate_output.getvalue())
        self.assertEqual(count_rows_by_table(database_path, "analyst_revision_source_snapshots"), 1)
        self.assertEqual(count_rows_by_table(database_path, "analyst_revision_aggregates"), 1)

        with patch_refresh_pipeline_for_test(
            _revision_source_import_step=(1, ()),
            _revision_aggregation_step=(1, ()),
            _analyst_revision_load_step=(1, ()),
            _revision_signal_step=(1, ()),
            _revision_validation_step=(1, ()),
        ):
            pipeline_result = run_refresh_data(config, skip_ibkr=True)
        step_names = [step.step_name for step in pipeline_result.steps]
        self.assertIn("fetch-revision-sources", step_names)
        self.assertIn("import-revision-source-exports", step_names)
        self.assertIn("aggregate-revision-sources", step_names)

    def test_parser_and_header_creation_validate_revision_csv(self) -> None:
        database_path = fresh_database_path("phase10a_parser.sqlite")
        config = make_config(database_path)
        ensure_analyst_revision_csv_header(config.analyst_revisions_path)
        self.assertTrue(config.analyst_revisions_path.exists())
        self.assertIn("eps_revision_3m", config.analyst_revisions_path.read_text())
        self.assertIn("source_url", config.analyst_revisions_path.read_text())

        rows = parse_analyst_revisions_csv(
            "ticker,signal_date,eps_revision_3m,analyst_count,source_url,notes\n"
            "aapl,2026-01-10,0.05,30,https://example.com/aapl,source checked\n"
        )
        self.assertEqual(rows[0].ticker, "AAPL")
        self.assertEqual(rows[0].eps_revision_3m, 0.05)
        self.assertEqual(rows[0].analyst_count, 30)
        self.assertEqual(rows[0].source_url, "https://example.com/aapl")
        self.assertEqual(rows[0].notes, "source checked")

        with self.assertRaises(ValueError):
            parse_analyst_revisions_csv("ticker,eps_revision_3m\nAAPL,0.05\n")
        with self.assertRaises(ValueError):
            parse_analyst_revisions_csv(
                "ticker,signal_date,eps_revision_3m\nAAPL,not-a-date,0.05\n"
            )
        with self.assertRaises(ValueError):
            parse_analyst_revisions_csv(
                "ticker,signal_date,eps_revision_3m\nAAPL,2026-01-10,bad\n"
            )

    def test_signal_storage_and_load_are_idempotent(self) -> None:
        database_path = fresh_database_path("phase10a_load.sqlite")
        config = make_config(database_path)
        initialize_database(database_path)
        upsert_asset(database_path, Asset(ticker="AAPL", asset_type="equity"))
        write_revision_csv(
            config,
            ["AAPL,2026-01-10,0.02,0.05,0.01,0.03,0.04,1,0.12,32,manual,2026-01-10,2026-01-10"],
        )

        first = load_analyst_revisions_csv(config)
        second = load_analyst_revisions_csv(config)

        self.assertEqual(first.row_count, 1)
        self.assertEqual(first.input_signal_count, second.input_signal_count)
        self.assertEqual(count_rows_by_table(database_path, "signals"), first.input_signal_count)
        self.assertEqual(first.tickers, ("AAPL",))

        upsert_signal(
            database_path,
            Signal(
                ticker="AAPL",
                signal_date="2026-01-10",
                signal_name="analyst_revision.test",
                signal_family="analyst_revision",
                score=75,
                source="test",
            ),
        )
        upsert_signal(
            database_path,
            Signal(
                ticker="AAPL",
                signal_date="2026-01-10",
                signal_name="analyst_revision.test",
                signal_family="analyst_revision",
                score=75,
                source="test",
            ),
        )
        self.assertEqual(latest_signal_date(database_path), "2026-01-10")
        self.assertTrue(list_signals(database_path, "AAPL"))

    def test_source_backed_revision_rows_propagate_source_audit_fields(self) -> None:
        database_path = fresh_database_path("phase10c_source_rows.sqlite")
        config = make_config(database_path)
        initialize_database(database_path)
        upsert_asset(database_path, Asset(ticker="AAPL", asset_type="equity"))
        write_source_revision_csv(
            config,
            [
                "AAPL,2026-01-10,,0.05,,,,,0.10,25,yahoo_finance_analysis,https://finance.yahoo.com/quote/AAPL/analysis/,Yahoo Analysis EPS trend verified,2026-01-10,2026-01-10",
            ],
        )

        compute_revision_signals(config)
        composite = [
            signal
            for signal in list_signals(database_path, "AAPL", "analyst_revision")
            if signal.signal_name == "analyst_revision.composite"
        ][0]

        self.assertEqual(composite.source_url, "https://finance.yahoo.com/quote/AAPL/analysis/")
        self.assertEqual(composite.notes, "Yahoo Analysis EPS trend verified")
        self.assertGreater(composite.score or 0, 50)

    def test_signal_outcome_storage_is_idempotent(self) -> None:
        database_path = fresh_database_path("phase10b_signal_outcomes.sqlite")
        initialize_database(database_path)
        outcome = SignalOutcome(
            ticker="AAPL",
            signal_date="2026-01-10",
            signal_name="analyst_revision.composite",
            signal_family="analyst_revision",
            signal_score=70,
            signal_direction="positive",
            outcome_date="2026-01-20",
            outcome_status="partial",
            entry_price=100,
            entry_price_date="2026-01-10",
            latest_price=110,
            latest_price_date="2026-01-20",
            completed_horizons="5d",
            pending_horizons="20d,60d,120d",
            return_5d=0.05,
            directional_hit_flag=1,
            hit_status="hit",
        )

        upsert_signal_outcome(database_path, outcome)
        upsert_signal_outcome(database_path, outcome)

        self.assertEqual(count_rows_by_table(database_path, "signal_outcomes"), 1)
        self.assertEqual(latest_signal_outcome_date(database_path), "2026-01-20")
        self.assertEqual(list_signal_outcomes(database_path)[0].ticker, "AAPL")

    def test_compute_revision_signals_handles_positive_negative_stale_and_dispersion(self) -> None:
        database_path = fresh_database_path("phase10a_compute.sqlite")
        config = make_config(database_path)
        initialize_database(database_path)
        for ticker in ("AAPL", "MSFT", "NVDA", "SPY"):
            upsert_asset(
                database_path,
                Asset(ticker=ticker, asset_type="etf" if ticker == "SPY" else "equity"),
            )
        stale_date = (date.today() - timedelta(days=60)).isoformat()
        write_revision_csv(
            config,
            [
                f"AAPL,{date.today().isoformat()},0.02,0.05,0.01,0.03,0.04,1,0.10,30,manual,{date.today().isoformat()},{date.today().isoformat()}",
                f"MSFT,{date.today().isoformat()},,-0.04,,-0.02,-0.03,-1,0.30,25,manual,{date.today().isoformat()},{date.today().isoformat()}",
                f"NVDA,{stale_date},,0.03,,,,,0.05,20,manual,{date.today().isoformat()},{stale_date}",
            ],
        )

        result = compute_revision_signals(config)
        statuses = {status.ticker: status for status in signal_statuses(database_path)}

        self.assertEqual(result.computed_count, 3)
        self.assertEqual(result.skipped_count, 1)
        self.assertGreater(statuses["AAPL"].composite_score or 0, 50)
        self.assertLess(statuses["MSFT"].composite_score or 100, 50)
        self.assertIn("high_estimate_dispersion", statuses["MSFT"].data_warnings)
        self.assertIn("stale_revision_signal", statuses["NVDA"].data_warnings)
        self.assertIn("etf_revision_signal_gated", statuses["SPY"].data_warnings)

    def test_compute_revision_signals_ticker_filter_only_computes_requested_ticker(self) -> None:
        database_path = fresh_database_path("phase10a_filter.sqlite")
        config = make_config(database_path)
        initialize_database(database_path)
        upsert_asset(database_path, Asset(ticker="AAPL", asset_type="equity"))
        upsert_asset(database_path, Asset(ticker="MSFT", asset_type="equity"))
        write_revision_csv(
            config,
            [
                f"AAPL,{date.today().isoformat()},,0.05,,,,,,20,manual,{date.today().isoformat()},{date.today().isoformat()}",
                f"MSFT,{date.today().isoformat()},,-0.05,,,,,,20,manual,{date.today().isoformat()},{date.today().isoformat()}",
            ],
        )

        result = compute_revision_signals(config, ticker="AAPL")
        output_signals = list_signals(database_path, signal_family="analyst_revision")

        self.assertEqual(result.computed_count, 1)
        self.assertEqual([item.ticker for item in result.results], ["AAPL"])
        self.assertEqual({signal.ticker for signal in output_signals}, {"AAPL"})

    def test_validate_revision_signals_computes_pending_hits_and_ticker_filter(self) -> None:
        database_path = fresh_database_path("phase10b_validate.sqlite")
        config = make_config(database_path)
        initialize_database(database_path)
        for ticker, asset_type in (
            ("AAPL", "equity"),
            ("MSFT", "equity"),
            ("NVDA", "equity"),
            ("SPY", "etf"),
        ):
            upsert_asset(database_path, Asset(ticker=ticker, asset_type=asset_type))
        write_revision_csv(
            config,
            [
                "AAPL,2026-01-10,,0.05,,,,,,25,manual,2026-01-10,2026-01-10",
                "MSFT,2026-01-10,,-0.05,,,,,,25,manual,2026-01-10,2026-01-10",
                "NVDA,2026-01-10,,0.00,,,,,,25,manual,2026-01-10,2026-01-10",
            ],
        )
        start = date(2026, 1, 1)
        seed_price_history(database_path, "AAPL", start, [100 + offset for offset in range(30)])
        seed_price_history(database_path, "MSFT", start, [200 - offset for offset in range(30)])
        seed_price_history(database_path, "NVDA", start, [300 + offset for offset in range(10)])
        compute_revision_signals(config)

        result = validate_revision_signals(config)
        statuses = {status.ticker: status for status in signal_outcome_statuses(database_path)}

        self.assertEqual(result.updated_count, 3)
        self.assertEqual(result.skipped_count, 1)
        self.assertEqual(statuses["AAPL"].outcome_status, "partial")
        self.assertEqual(statuses["AAPL"].directional_hit_flag, 1)
        self.assertEqual(statuses["MSFT"].directional_hit_flag, 1)
        self.assertEqual(statuses["NVDA"].outcome_status, "pending")
        self.assertEqual(statuses["NVDA"].hit_status, "neutral")
        self.assertIn("pending_future_prices", statuses["NVDA"].data_warnings)

        filtered_database = fresh_database_path("phase10b_validate_filter.sqlite")
        filtered_config = make_config(filtered_database)
        initialize_database(filtered_database)
        upsert_asset(filtered_database, Asset(ticker="AAPL", asset_type="equity"))
        upsert_asset(filtered_database, Asset(ticker="MSFT", asset_type="equity"))
        write_revision_csv(
            filtered_config,
            [
                "AAPL,2026-01-10,,0.05,,,,,,25,manual,2026-01-10,2026-01-10",
                "MSFT,2026-01-10,,-0.05,,,,,,25,manual,2026-01-10,2026-01-10",
            ],
        )
        seed_price_history(filtered_database, "AAPL", start, [100 + offset for offset in range(30)])
        seed_price_history(filtered_database, "MSFT", start, [200 - offset for offset in range(30)])
        compute_revision_signals(filtered_config)
        filtered_result = validate_revision_signals(filtered_config, ticker="AAPL")

        self.assertEqual(filtered_result.updated_count, 1)
        self.assertEqual({item.ticker for item in filtered_result.results}, {"AAPL"})
        self.assertEqual({item.ticker for item in list_signal_outcomes(filtered_database)}, {"AAPL"})

    def test_revision_evidence_gate_decisions(self) -> None:
        empty_database = fresh_database_path("phase10c_empty_evidence.sqlite")
        empty_config = make_config(empty_database)
        initialize_database(empty_database)
        empty_evidence = build_revision_evidence(empty_config)
        self.assertEqual(empty_evidence.decision, DECISION_INSUFFICIENT_SOURCE)

        collecting_database = fresh_database_path("phase10c_collecting.sqlite")
        collecting_config = make_config(collecting_database)
        initialize_database(collecting_database)
        for ticker in ("AAPL", "MSFT", "NVDA"):
            upsert_asset(collecting_database, Asset(ticker=ticker, asset_type="equity"))
        write_source_revision_csv(
            collecting_config,
            [
                f"{ticker},2026-01-10,0.02,0.05,0.01,0.02,0.03,0.20,0.05,25,provider,https://example.com/{ticker},source row,2026-01-10,2026-01-10"
                for ticker in ("AAPL", "MSFT", "NVDA")
            ],
        )
        compute_revision_signals(collecting_config)
        collecting_evidence = build_revision_evidence(collecting_config)
        self.assertEqual(collecting_evidence.decision, DECISION_COLLECTING)
        self.assertEqual(collecting_evidence.source_ticker_count, 3)
        self.assertEqual(collecting_evidence.signal_ticker_count, 3)

        keep_database = fresh_database_path("phase10c_keep_shadow.sqlite")
        keep_config = make_config(keep_database)
        initialize_database(keep_database)
        for ticker in ("AAPL", "MSFT", "NVDA"):
            upsert_asset(keep_database, Asset(ticker=ticker, asset_type="equity"))
        write_source_revision_csv(
            keep_config,
            [
                f"{ticker},2026-01-10,0.02,0.05,0.01,0.02,0.03,0.20,0.05,25,provider,https://example.com/{ticker},source row,2026-01-10,2026-01-10"
                for ticker in ("AAPL", "MSFT", "NVDA")
            ],
        )
        compute_revision_signals(keep_config)
        for ticker, return_20d in (("AAPL", -0.01), ("MSFT", -0.02), ("NVDA", 0.03)):
            upsert_signal_outcome(
                keep_database,
                SignalOutcome(
                    ticker=ticker,
                    signal_date="2026-01-10",
                    signal_name="analyst_revision.composite",
                    signal_family="analyst_revision",
                    signal_score=70,
                    signal_direction="positive",
                    outcome_date="2026-02-10",
                    outcome_status="partial",
                    return_20d=return_20d,
                    directional_hit_flag=1 if return_20d > 0 else 0,
                ),
            )
        keep_evidence = build_revision_evidence(keep_config)
        self.assertEqual(keep_evidence.decision, DECISION_KEEP_SHADOW)

        eligible_database = fresh_database_path("phase10c_eligible.sqlite")
        eligible_config = make_config(eligible_database)
        initialize_database(eligible_database)
        for ticker in ("AAPL", "MSFT", "NVDA"):
            upsert_asset(eligible_database, Asset(ticker=ticker, asset_type="equity"))
        write_source_revision_csv(
            eligible_config,
            [
                f"{ticker},2026-01-10,0.02,0.05,0.01,0.02,0.03,0.20,0.05,25,provider,https://example.com/{ticker},source row,2026-01-10,2026-01-10"
                for ticker in ("AAPL", "MSFT", "NVDA")
            ],
        )
        compute_revision_signals(eligible_config)
        for ticker, return_20d in (("AAPL", 0.01), ("MSFT", 0.02), ("NVDA", 0.03)):
            upsert_signal_outcome(
                eligible_database,
                SignalOutcome(
                    ticker=ticker,
                    signal_date="2026-01-10",
                    signal_name="analyst_revision.composite",
                    signal_family="analyst_revision",
                    signal_score=70,
                    signal_direction="positive",
                    outcome_date="2026-02-10",
                    outcome_status="partial",
                    return_20d=return_20d,
                    directional_hit_flag=1,
                ),
            )
        eligible_evidence = build_revision_evidence(eligible_config)
        self.assertEqual(eligible_evidence.decision, DECISION_ELIGIBLE)
        self.assertAlmostEqual(eligible_evidence.hit_rate_20d or 0, 1.0)

    def test_evaluate_revision_signal_outcome_computes_horizon_returns(self) -> None:
        database_path = fresh_database_path("phase10b_horizons.sqlite")
        config = make_config(database_path)
        initialize_database(database_path)
        upsert_asset(database_path, Asset(ticker="AAPL", asset_type="equity"))
        write_revision_csv(
            config,
            ["AAPL,2026-01-10,,0.05,,,,,,25,manual,2026-01-10,2026-01-10"],
        )
        start = date(2026, 1, 1)
        seed_price_history(database_path, "AAPL", start, [100 + offset for offset in range(70)])
        compute_revision_signals(config)
        signal = [
            item
            for item in list_signals(database_path, "AAPL", signal_family="analyst_revision")
            if item.signal_name == "analyst_revision.composite"
        ][0]
        stored_signal = [
            item
            for item in list_stored_signals(
                database_path,
                ticker="AAPL",
                signal_family="analyst_revision",
                signal_name="analyst_revision.composite",
            )
        ][0]

        outcome = evaluate_revision_signal_outcome(
            stored_signal,
            list_prices(database_path, "AAPL"),
            outcome_date=date(2026, 3, 15),
        )

        self.assertEqual(signal.direction, "positive")
        self.assertAlmostEqual(outcome.return_5d or 0, 114 / 109 - 1)
        self.assertAlmostEqual(outcome.return_20d or 0, 129 / 109 - 1)
        self.assertEqual(outcome.directional_hit_flag, 1)
        self.assertEqual(outcome.outcome_status, "partial")

    def test_shadow_mode_keeps_opportunity_score_neutral_while_showing_revision_score(self) -> None:
        shadow_database = fresh_database_path("phase10a_shadow.sqlite")
        live_database = fresh_database_path("phase10a_live.sqlite")
        shadow_config = make_config(shadow_database, shadow_mode=True)
        live_config = make_config(live_database, shadow_mode=False)
        for config in (shadow_config, live_config):
            seed_equity_fixture(config.database_path)
            write_revision_csv(
                config,
                [
                    f"AAPL,{date.today().isoformat()},,0.10,,,,,,25,manual,{date.today().isoformat()},{date.today().isoformat()}"
                ],
            )
            compute_revision_signals(config, ticker="AAPL")
            compute_scores(config, ticker="AAPL")

        shadow_score = list_scores(shadow_database, "AAPL")[0]
        live_score = list_scores(live_database, "AAPL")[0]

        self.assertGreater(shadow_score.revision_score or 0, 50)
        self.assertIn("revision_contribution=50.00", shadow_score.score_reason or "")
        self.assertLess(shadow_score.opportunity_score or 0, live_score.opportunity_score or 0)
        self.assertIn("revision_signal_shadow_mode", shadow_score.data_warnings or "")

    def test_cli_report_dashboard_status_and_pipeline_include_signals(self) -> None:
        database_path = fresh_database_path("phase10a_interfaces.sqlite")
        config = make_config(database_path)
        write_config(config)
        seed_equity_fixture(database_path)
        config.watchlist_path.write_text("ticker,asset_type\nAAPL,equity\n", encoding="utf-8")
        write_revision_csv(
            config,
            [
                f"AAPL,{date.today().isoformat()},,0.05,,,,,0.10,25,manual,{date.today().isoformat()},{date.today().isoformat()}"
            ],
        )

        load_output = io.StringIO()
        with redirect_stdout(load_output):
            load_exit = command_load_analyst_revisions(Namespace(config=config.config_path, file=None))
        compute_output = io.StringIO()
        with redirect_stdout(compute_output):
            compute_exit = command_compute_revision_signals(
                Namespace(config=config.config_path, ticker="AAPL")
            )
        signal_output = io.StringIO()
        with redirect_stdout(signal_output):
            signal_exit = command_signal_status(Namespace(config=config.config_path))
        validation_output = io.StringIO()
        with redirect_stdout(validation_output):
            validation_exit = command_validate_revision_signals(
                Namespace(config=config.config_path, ticker="AAPL")
            )
        validation_report_output = io.StringIO()
        with redirect_stdout(validation_report_output):
            validation_report_exit = command_revision_validation_report(
                Namespace(config=config.config_path)
            )
        evidence_report_output = io.StringIO()
        with redirect_stdout(evidence_report_output):
            evidence_report_exit = command_revision_evidence_report(
                Namespace(config=config.config_path)
            )
        status_output = io.StringIO()
        with redirect_stdout(status_output):
            status_exit = command_status(Namespace(config=config.config_path))

        report = write_daily_report(config)
        csv_text = report.csv_path.read_text(encoding="utf-8")
        markdown = report.path.read_text(encoding="utf-8")
        dashboard = build_dashboard(config)
        dashboard_text = dashboard.path.read_text(encoding="utf-8")
        data = dashboard_data(dashboard_text)

        self.assertEqual(load_exit, 0)
        self.assertEqual(compute_exit, 0)
        self.assertEqual(signal_exit, 0)
        self.assertEqual(validation_exit, 0)
        self.assertEqual(validation_report_exit, 0)
        self.assertEqual(evidence_report_exit, 0)
        self.assertEqual(status_exit, 0)
        self.assertIn("Analyst revisions loaded", load_output.getvalue())
        self.assertIn("Revision signal computation complete", compute_output.getvalue())
        self.assertIn("AAPL", signal_output.getvalue())
        self.assertIn("Revision signal validation complete", validation_output.getvalue())
        self.assertIn(
            "Analyst Revision Signal Validation Report",
            validation_report_output.getvalue(),
        )
        self.assertIn(
            "Analyst Revision Evidence Report",
            evidence_report_output.getvalue(),
        )
        self.assertIn("Signal rows:", status_output.getvalue())
        self.assertIn("Signal outcome rows:", status_output.getvalue())
        self.assertIn("Analyst revision source-backed tickers:", status_output.getvalue())
        self.assertIn("Revision evidence decision:", status_output.getvalue())
        self.assertIn("revision_score", csv_text)
        self.assertIn("revision_signal_status", csv_text)
        self.assertIn("revision_source_status", csv_text)
        self.assertIn("revision_source_coverage_count", csv_text)
        self.assertIn("revision_validation_status", csv_text)
        self.assertIn("revision_evidence_decision", csv_text)
        self.assertIn("Advanced Signals", markdown)
        self.assertIn("Analyst revision source-backed coverage", markdown)
        self.assertIn("Source-export ticker coverage", markdown)
        self.assertIn("Analyst revision validation rows", markdown)
        self.assertIn("Revision evidence decision", markdown)
        self.assertIn("News/catalyst signal coverage", markdown)
        self.assertIn("Phase 10D", markdown)
        self.assertNotIn("Start Phase 10B", markdown)
        self.assertIn("Advanced Signals", dashboard_text)
        self.assertIn("latest_signal_date", data["health"])
        self.assertIn("latest_signal_validation_date", data["health"])
        self.assertIn("revision_evidence", data)
        self.assertIn("revision_source_status", data)
        self.assertIn("revision_source_backed_ticker_count", data["health"])
        self.assertIn("revision_evidence_decision", data["health"])
        self.assertTrue(data["signal_outcomes"])
        self.assertEqual(data["rows"][0]["revision_signal_status"].split("@")[0], "positive")
        self.assertEqual(data["rows"][0]["revision_source_status"], "missing")
        self.assertIn("missing_entry_price", data["rows"][0]["advanced_signal_warnings"])

        with patch_refresh_pipeline_for_test(
            _revision_source_import_step=(1, ()),
            _revision_aggregation_step=(1, ()),
            _analyst_revision_load_step=(1, ()),
            _revision_signal_step=(1, ()),
            _revision_validation_step=(1, ()),
        ):
            pipeline_result = run_refresh_data(config, skip_ibkr=True)
        step_names = [step.step_name for step in pipeline_result.steps]
        self.assertIn("fetch-revision-sources", step_names)
        self.assertIn("import-revision-source-exports", step_names)
        self.assertIn("aggregate-revision-sources", step_names)
        self.assertIn("load-analyst-revisions", step_names)
        self.assertIn("compute-revision-signals", step_names)
        self.assertIn("validate-revision-signals", step_names)


if __name__ == "__main__":
    unittest.main()
