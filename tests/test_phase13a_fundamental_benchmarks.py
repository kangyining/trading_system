from __future__ import annotations

from argparse import Namespace
from contextlib import redirect_stdout
from pathlib import Path
import csv
import io
import sys
import unittest
from unittest.mock import patch


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
TEST_TMP_ROOT = PROJECT_ROOT / ".tmp_tests" / "phase13a"
sys.path.insert(0, str(SRC_PATH))

from target_opportunity_monitor.cli import (
    command_apply_research_ticker,
    command_compute_fundamental_benchmarks,
    command_fundamental_benchmark_report,
    command_fundamental_benchmark_status,
    command_refresh_research_ticker,
    command_research_ticker_plan,
    command_research_ticker_status,
    command_status,
)
from target_opportunity_monitor.config import AppConfig, load_config
from target_opportunity_monitor.dashboard import build_dashboard
from target_opportunity_monitor.db import REQUIRED_TABLES, initialize_database
from target_opportunity_monitor.fundamental_benchmarks import (
    apply_universe_candidates,
    compute_fundamental_benchmarks,
    export_universe_candidate_template,
    universe_expansion_plan,
)
from target_opportunity_monitor.pipeline import PipelineExecutionResult, PipelineStepSummary
from target_opportunity_monitor.research_tickers import (
    apply_research_ticker,
    research_ticker_plan,
    research_ticker_status,
)
from target_opportunity_monitor.reporting import REPORT_CSV_COLUMNS, write_daily_report
from target_opportunity_monitor.storage import (
    Asset,
    Estimate,
    Fundamental,
    PriceFeature,
    Score,
    Target,
    count_rows_by_table,
    fundamental_comparison_statuses,
    latest_asset,
    list_fundamental_benchmark_snapshots,
    upsert_asset,
    upsert_estimate,
    upsert_fundamental,
    upsert_price_feature,
    upsert_score,
    upsert_target,
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
        config_path=root / "phase13a.toml",
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
        universe_candidates_path=root / "configs" / "universe_candidates.csv",
        sector_benchmarks_path=root / "configs" / "sector_benchmarks.csv",
        cik_map_path=root / "configs" / "cik_map.csv",
        fundamental_benchmark_model_version="fundamental_benchmark_mvp_v1",
        fundamental_benchmark_min_sector_peer_count=3,
        fundamental_benchmark_min_industry_peer_count=2,
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
                f'universe_candidates = "{config.universe_candidates_path.as_posix()}"',
                f'sector_benchmarks = "{config.sector_benchmarks_path.as_posix()}"',
                f'cik_map = "{config.cik_map_path.as_posix()}"',
                "",
                "[fundamental_benchmarks]",
                'model_version = "fundamental_benchmark_mvp_v1"',
                "minimum_sector_peer_count = 3",
                "minimum_industry_peer_count = 2",
                "",
                "[run]",
                'universe_mode = "manual_watchlist"',
                'run_mode = "daily_scoring"',
                "",
            )
        ),
        encoding="utf-8",
    )


def write_candidate_rows(config: AppConfig, rows: list[dict[str, str]]) -> None:
    config.universe_candidates_path.parent.mkdir(parents=True, exist_ok=True)
    with config.universe_candidates_path.open("w", encoding="utf-8", newline="") as output:
        writer = csv.DictWriter(
            output,
            fieldnames=(
                "ticker",
                "name",
                "asset_type",
                "exchange",
                "currency",
                "sector",
                "industry",
                "country",
                "intended_role",
                "cik",
                "source",
                "notes",
            ),
        )
        writer.writeheader()
        writer.writerows(rows)


def seed_asset(config: AppConfig, ticker: str, sector: str, industry: str) -> None:
    upsert_asset(
        config.database_path,
        Asset(
            ticker=ticker,
            name=f"{ticker} Corp",
            asset_type="equity",
            exchange="NASDAQ",
            currency="USD",
            sector=sector,
            industry=industry,
            country="US",
            active_flag=1,
            asset_role="scoreable",
            source="test",
        ),
    )


def seed_metrics(
    config: AppConfig,
    ticker: str,
    price: float,
    eps: float,
    revenue_latest: float,
    revenue_previous: float,
    net_income: float,
    free_cash_flow: float,
    ebitda: float,
    net_debt: float,
    score: float,
    return_3m: float,
) -> None:
    for period_end, revenue in (("2024-12-31", revenue_previous), ("2025-12-31", revenue_latest)):
        upsert_fundamental(
            config.database_path,
            Fundamental(
                ticker=ticker,
                fiscal_period_end=period_end,
                fiscal_period="FY",
                report_type="annual",
                currency="USD",
                revenue=revenue,
                net_income=net_income,
                ebitda=ebitda,
                free_cash_flow=free_cash_flow,
                net_debt=net_debt,
                total_equity=net_income * 5,
                diluted_shares=100.0,
                source="test",
            ),
        )
    upsert_estimate(
        config.database_path,
        Estimate(
            ticker=ticker,
            estimate_date="2026-06-13",
            fiscal_period_end="2026-12-31",
            metric="eps",
            fiscal_period="NTM",
            consensus_mean=eps,
            source="test",
        ),
    )
    upsert_price_feature(
        config.database_path,
        PriceFeature(
            ticker=ticker,
            feature_date="2026-06-13",
            current_price=price,
            return_1d=0.0,
            return_1m=0.0,
            return_3m=return_3m,
            return_6m=0.0,
            return_12m=0.0,
            realized_volatility_20d=0.2,
            realized_volatility_60d=0.25,
            average_dollar_volume_20d=1000000,
            latest_price_date="2026-06-13",
            source="test",
        ),
    )
    upsert_target(
        config.database_path,
        Target(
            ticker=ticker,
            target_date="2026-06-13",
            base_target=price * 1.1,
            target_low=price,
            target_high=price * 1.2,
            valuation_gap=0.1,
            target_method="test",
            uncertainty_band=0.1,
            source="test",
        ),
    )
    upsert_score(
        config.database_path,
        Score(
            ticker=ticker,
            score_date="2026-06-13",
            opportunity_score=score,
            asset_type="equity",
            source="test",
        ),
    )


def seed_benchmark_prices(config: AppConfig) -> None:
    for ticker, return_3m in (("SPY", 0.10), ("QQQ", 0.12), ("XLK", 0.08)):
        upsert_asset(
            config.database_path,
            Asset(
                ticker=ticker,
                name=f"{ticker} ETF",
                asset_type="etf",
                sector="Benchmark",
                industry="ETF",
                country="US",
                active_flag=1,
                asset_role="regime_proxy",
                source="test",
            ),
        )
        upsert_price_feature(
            config.database_path,
            PriceFeature(
                ticker=ticker,
                feature_date="2026-06-13",
                current_price=100.0,
                return_1d=0.0,
                return_1m=0.0,
                return_3m=return_3m,
                return_6m=0.0,
                return_12m=0.0,
                realized_volatility_20d=0.1,
                realized_volatility_60d=0.1,
                average_dollar_volume_20d=1000000,
                latest_price_date="2026-06-13",
                source="test",
            ),
        )


def sec_company_tickers_payload(ticker: str = "NEWE", cik: int = 1234567) -> dict[str, object]:
    return {
        "fields": ["cik", "name", "ticker", "exchange"],
        "data": [[cik, "New Equity Inc.", ticker, "Nasdaq"]],
    }


def fmp_profile_payload() -> dict[str, object]:
    return {
        "companyName": "New Equity Inc.",
        "sector": "Information Technology",
        "industry": "Software",
        "exchangeShortName": "NASDAQ",
        "currency": "USD",
        "country": "US",
    }


class Phase13AFundamentalBenchmarkTests(unittest.TestCase):
    def test_database_and_config_defaults(self) -> None:
        config = make_config(fresh_database_path("defaults.sqlite"))
        status = initialize_database(config.database_path)

        self.assertIn("fundamental_benchmark_snapshots", REQUIRED_TABLES)
        self.assertIn("fundamental_comparison_snapshots", REQUIRED_TABLES)
        self.assertEqual(status.existing_required_table_count, status.required_table_count)
        self.assertEqual(config.fundamental_benchmark_model_version, "fundamental_benchmark_mvp_v1")

    def test_universe_candidate_template_and_apply(self) -> None:
        config = make_config(fresh_database_path("candidates.sqlite"))
        initialize_database(config.database_path)
        upsert_asset(config.database_path, Asset(ticker="SPY", asset_type="etf", asset_role="scoreable"))
        upsert_asset(config.database_path, Asset(ticker="QQQ", asset_type="etf", asset_role="scoreable"))

        path = export_universe_candidate_template(config)
        text = path.read_text(encoding="utf-8")
        self.assertIn("XLK", text)
        self.assertIn("XLRE", text)
        self.assertNotIn("\nSPY,", text)

        plan = universe_expansion_plan(config)
        self.assertTrue(plan.apply_ready)
        self.assertIn("XLK", [candidate.ticker for candidate in plan.valid_candidates])

        applied = apply_universe_candidates(config, confirm=True, allow_partial=True)
        self.assertIn("XLK", applied.applied_tickers)
        plan_after_apply = universe_expansion_plan(config)
        self.assertFalse(plan_after_apply.invalid_candidates)
        self.assertIn("XLK", plan_after_apply.already_active_tickers)
        self.assertEqual(plan_after_apply.blocked_reason, "all_candidates_already_active")

    def test_apply_candidates_validates_cik_and_partial_apply(self) -> None:
        config = make_config(fresh_database_path("apply.sqlite"))
        initialize_database(config.database_path)
        write_candidate_rows(
            config,
            [
                {
                    "ticker": "XLB",
                    "name": "Materials ETF",
                    "asset_type": "etf",
                    "exchange": "NYSEARCA",
                    "currency": "USD",
                    "sector": "Materials",
                    "industry": "Sector ETF",
                    "country": "US",
                    "intended_role": "regime_proxy",
                    "cik": "",
                    "source": "test",
                    "notes": "benchmark",
                },
                {
                    "ticker": "NEWE",
                    "name": "New Equity",
                    "asset_type": "equity",
                    "exchange": "NASDAQ",
                    "currency": "USD",
                    "sector": "Information Technology",
                    "industry": "Software",
                    "country": "US",
                    "intended_role": "scoreable",
                    "cik": "",
                    "source": "test",
                    "notes": "missing cik",
                },
            ],
        )

        blocked = apply_universe_candidates(config, confirm=True)
        self.assertEqual(blocked.applied_count, 0)
        self.assertEqual(blocked.blocked_reason, "invalid_candidates_present")

        applied = apply_universe_candidates(config, confirm=True, allow_partial=True)
        self.assertEqual(applied.applied_tickers, ("XLB",))
        self.assertEqual(latest_asset(config.database_path, "XLB").asset_role, "regime_proxy")

    def test_research_ticker_plan_and_apply_scoreable_equity(self) -> None:
        config = make_config(fresh_database_path("research_apply.sqlite"))
        initialize_database(config.database_path)
        with (
            patch(
                "target_opportunity_monitor.research_tickers._load_or_fetch_sec_company_tickers",
                return_value=sec_company_tickers_payload(),
            ),
            patch(
                "target_opportunity_monitor.research_tickers._fetch_fmp_profile",
                return_value=(fmp_profile_payload(), ()),
            ),
        ):
            plan = research_ticker_plan(config, "newe")
            self.assertTrue(plan.apply_ready)
            self.assertEqual(plan.metadata.cik, "0001234567")
            self.assertEqual(plan.metadata.sector, "Information Technology")
            self.assertIsNone(latest_asset(config.database_path, "NEWE"))

            dry_run = apply_research_ticker(config, "NEWE")
            self.assertTrue(dry_run.dry_run)
            self.assertFalse(dry_run.applied)
            self.assertIsNone(latest_asset(config.database_path, "NEWE"))

            applied = apply_research_ticker(config, "NEWE", confirm=True)

        self.assertTrue(applied.applied)
        asset = latest_asset(config.database_path, "NEWE")
        self.assertIsNotNone(asset)
        self.assertEqual(asset.asset_role, "scoreable")
        self.assertEqual(asset.sector, "Information Technology")
        self.assertIn("NEWE,0001234567", config.cik_map_path.read_text(encoding="utf-8"))
        status = research_ticker_status(config, "NEWE")
        self.assertIn("missing_price_feature", status.readiness_blockers)

    def test_research_ticker_blocks_missing_metadata_until_overridden(self) -> None:
        config = make_config(fresh_database_path("research_blocked.sqlite"))
        initialize_database(config.database_path)
        with (
            patch(
                "target_opportunity_monitor.research_tickers._load_or_fetch_sec_company_tickers",
                return_value=sec_company_tickers_payload(),
            ),
            patch(
                "target_opportunity_monitor.research_tickers._fetch_fmp_profile",
                return_value=(None, ("missing_profile_api_key",)),
            ),
        ):
            blocked = apply_research_ticker(config, "NEWE", confirm=True)
            self.assertEqual(blocked.blocked_reason, "missing_sector")
            self.assertIsNone(latest_asset(config.database_path, "NEWE"))

            applied = apply_research_ticker(
                config,
                "NEWE",
                confirm=True,
                sector="Information Technology",
                industry="Software",
            )
        self.assertTrue(applied.applied)
        self.assertEqual(latest_asset(config.database_path, "NEWE").industry, "Software")

    def test_research_ticker_plan_handles_missing_sec_and_provider_failure(self) -> None:
        config = make_config(fresh_database_path("research_missing.sqlite"))
        initialize_database(config.database_path)
        with (
            patch(
                "target_opportunity_monitor.research_tickers._load_or_fetch_sec_company_tickers",
                return_value={"fields": ["cik", "name", "ticker", "exchange"], "data": []},
            ),
            patch(
                "target_opportunity_monitor.research_tickers._fetch_fmp_profile",
                return_value=(None, ("profile_provider_failed:URLError",)),
            ),
        ):
            plan = research_ticker_plan(config, "MISS")
        self.assertFalse(plan.apply_ready)
        self.assertEqual(plan.blocked_reason, "missing_cik")
        self.assertIn("sec_ticker_not_found", plan.warnings)
        self.assertIn("profile_provider_failed:URLError", plan.warnings)

    def test_research_ticker_cli_and_refresh_wrapper(self) -> None:
        config = make_config(fresh_database_path("research_cli.sqlite"))
        initialize_database(config.database_path)
        write_config(config)
        with (
            patch(
                "target_opportunity_monitor.research_tickers._load_or_fetch_sec_company_tickers",
                return_value=sec_company_tickers_payload(),
            ),
            patch(
                "target_opportunity_monitor.research_tickers._fetch_fmp_profile",
                return_value=(fmp_profile_payload(), ()),
            ),
        ):
            with redirect_stdout(io.StringIO()) as output:
                self.assertEqual(
                    command_research_ticker_plan(Namespace(config=config.config_path, ticker="NEWE", refresh_metadata=False, name=None, sector=None, industry=None, cik=None, exchange=None, currency=None, country=None)),
                    0,
                )
            self.assertIn("Apply ready: True", output.getvalue())
            self.assertEqual(
                command_apply_research_ticker(Namespace(config=config.config_path, ticker="NEWE", confirm=True, refresh_metadata=False, name=None, sector=None, industry=None, cik=None, exchange=None, currency=None, country=None)),
                0,
            )

        fake_result = PipelineExecutionResult(
            pipeline_run_id=42,
            run_type="daily_refresh",
            status="ok",
            steps=(PipelineStepSummary("update-prices", "ok", 1, ()),),
            summary="ok",
        )
        with patch("target_opportunity_monitor.pipeline.run_refresh_data", return_value=fake_result) as refresh:
            with redirect_stdout(io.StringIO()) as output:
                self.assertEqual(
                    command_refresh_research_ticker(Namespace(config=config.config_path, ticker="NEWE")),
                    0,
                )
        refresh.assert_called_once()
        self.assertIn("Pipeline run id: 42", output.getvalue())

        with redirect_stdout(io.StringIO()) as output:
            self.assertEqual(
                command_research_ticker_status(Namespace(config=config.config_path, ticker="NEWE")),
                0,
            )
        self.assertIn("Research ticker status", output.getvalue())

    def test_compute_fundamental_benchmarks(self) -> None:
        config = make_config(fresh_database_path("benchmarks.sqlite"))
        initialize_database(config.database_path)
        seed_benchmark_prices(config)
        for ticker, sector, industry, price, eps, score, return_3m in (
            ("AAA", "Information Technology", "Software", 100.0, 5.0, 70.0, 0.20),
            ("BBB", "Information Technology", "Software", 80.0, 4.0, 65.0, 0.05),
            ("CCC", "Information Technology", "Semiconductors", 60.0, 3.0, 75.0, 0.15),
            ("DDD", "Utilities", "Utilities", 50.0, 2.0, 55.0, 0.02),
        ):
            seed_asset(config, ticker, sector, industry)
            seed_metrics(
                config,
                ticker,
                price=price,
                eps=eps,
                revenue_latest=1200.0,
                revenue_previous=1000.0,
                net_income=200.0,
                free_cash_flow=150.0,
                ebitda=300.0,
                net_debt=100.0,
                score=score,
                return_3m=return_3m,
            )

        result = compute_fundamental_benchmarks(config)
        self.assertEqual(result.comparison_count, 4)
        self.assertGreaterEqual(result.benchmark_count, 4)

        comparisons = {row.ticker: row for row in fundamental_comparison_statuses(config.database_path)}
        self.assertEqual(comparisons["AAA"].sector_peer_count, 3)
        self.assertEqual(comparisons["AAA"].sector_benchmark_ticker, "XLK")
        self.assertAlmostEqual(comparisons["AAA"].relative_strength_vs_spy, 0.10)
        self.assertEqual(comparisons["DDD"].benchmark_status, "sparse_sector")
        self.assertIn("insufficient_sector_peer_count", comparisons["DDD"].data_warnings)

        sector_snapshots = [
            row
            for row in list_fundamental_benchmark_snapshots(config.database_path, "sector")
            if row.benchmark_key == "Information Technology"
        ]
        self.assertEqual(sector_snapshots[0].ticker_count, 3)

    def test_cli_report_and_dashboard_surfaces(self) -> None:
        config = make_config(fresh_database_path("surfaces.sqlite"))
        initialize_database(config.database_path)
        write_config(config)
        seed_benchmark_prices(config)
        for ticker in ("AAA", "BBB", "CCC"):
            seed_asset(config, ticker, "Information Technology", "Software")
            seed_metrics(
                config,
                ticker,
                price=100.0,
                eps=5.0,
                revenue_latest=1200.0,
                revenue_previous=1000.0,
                net_income=200.0,
                free_cash_flow=150.0,
                ebitda=300.0,
                net_debt=100.0,
                score=70.0,
                return_3m=0.2,
            )

        args = Namespace(config=config.config_path)
        self.assertEqual(command_compute_fundamental_benchmarks(args), 0)
        with redirect_stdout(io.StringIO()) as output:
            self.assertEqual(command_fundamental_benchmark_status(args), 0)
        self.assertIn("Compared scoreable equities: 3/3", output.getvalue())
        with redirect_stdout(io.StringIO()) as output:
            self.assertEqual(command_fundamental_benchmark_report(args), 0)
        self.assertIn("Ticker Comparisons", output.getvalue())
        with redirect_stdout(io.StringIO()) as output:
            self.assertEqual(
                command_fundamental_benchmark_report(
                    Namespace(config=config.config_path, ticker="AAA")
                ),
                0,
            )
        ticker_report = output.getvalue()
        self.assertIn("Fundamental Benchmark Report: AAA", ticker_report)
        self.assertIn("Relative strength vs SPY", ticker_report)

        report = write_daily_report(config)
        report_text = report.path.read_text(encoding="utf-8")
        self.assertIn("## Fundamental Benchmarks", report_text)
        self.assertIn("fundamental_sector_forward_pe_discount_pct", REPORT_CSV_COLUMNS)

        dashboard = build_dashboard(config)
        dashboard_text = dashboard.path.read_text(encoding="utf-8")
        self.assertIn("Fundamental Benchmarks", dashboard_text)
        self.assertIn("fundamental_sector_forward_pe_discount_pct", dashboard_text)

        with redirect_stdout(io.StringIO()) as status_output:
            self.assertEqual(command_status(args), 0)
        self.assertIn("Fundamental comparison rows:", status_output.getvalue())


if __name__ == "__main__":
    unittest.main()
