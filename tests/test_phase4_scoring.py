from __future__ import annotations

from argparse import Namespace
from contextlib import redirect_stdout
from datetime import date
from pathlib import Path
import io
import sys
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
TEST_TMP_ROOT = PROJECT_ROOT / ".tmp_tests"
sys.path.insert(0, str(SRC_PATH))

from support import sqlite_connection_for_test
from target_opportunity_monitor.cli import command_compute_scores, command_score_status
from target_opportunity_monitor.config import AppConfig, load_config
from target_opportunity_monitor.db import initialize_database
from target_opportunity_monitor.scoring import compute_scores
from target_opportunity_monitor.storage import (
    Asset,
    Estimate,
    EtfFeature,
    Fundamental,
    PriceFeature,
    Score,
    Target,
    count_rows_by_table,
    latest_score_date,
    list_scores,
    score_statuses,
    upsert_asset,
    upsert_estimate,
    upsert_etf_feature,
    upsert_fundamental,
    upsert_price_feature,
    upsert_score,
    upsert_target,
)


def make_config(database_path: Path) -> AppConfig:
    return AppConfig(
        project_root=TEST_TMP_ROOT,
        config_path=TEST_TMP_ROOT / "phase4.toml",
        database_path=database_path,
        reports_dir=TEST_TMP_ROOT / "reports_phase4",
        watchlist_path=TEST_TMP_ROOT / "watchlist_phase4.csv",
        market_data_dir=TEST_TMP_ROOT / "market_data_phase4",
        manual_prices_dir=TEST_TMP_ROOT / "market_data_phase4" / "manual",
        market_data_primary_source="stooq",
        market_data_secondary_source="yahoo_chart",
        market_data_mode="csv",
        market_data_lookback_days=800,
        market_data_stale_after_days=7,
        market_data_minimum_history_days=252,
        universe_mode="manual_watchlist",
        run_mode="daily_scoring",
        report_title="Target Opportunity Monitor Daily Report",
        fundamentals_path=TEST_TMP_ROOT / "fundamentals_phase4.csv",
        estimates_path=TEST_TMP_ROOT / "estimates_phase4.csv",
        scoring_equity_model_version="equity_score_mvp_v1",
        scoring_etf_model_version="etf_score_mvp_v1",
        scoring_equity_threshold_set="equity_default",
        scoring_etf_threshold_set="etf_liquid_index",
    )


def write_config(config: AppConfig) -> None:
    config.config_path.write_text(
        "\n".join(
            (
                "[paths]",
                f'database = "{config.database_path.as_posix()}"',
                f'reports = "{config.reports_dir.as_posix()}"',
                f'watchlist = "{config.watchlist_path.as_posix()}"',
                "",
                "[scoring]",
                f'equity_model_version = "{config.scoring_equity_model_version}"',
                f'etf_model_version = "{config.scoring_etf_model_version}"',
                f'equity_threshold_set = "{config.scoring_equity_threshold_set}"',
                f'etf_threshold_set = "{config.scoring_etf_threshold_set}"',
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
            revision_1m=0.03,
            revision_3m=0.05,
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


class Phase4ScoringTests(unittest.TestCase):
    def setUp(self) -> None:
        TEST_TMP_ROOT.mkdir(exist_ok=True)

    def fresh_database_path(self, name: str) -> Path:
        path = TEST_TMP_ROOT / name
        if path.exists():
            path.unlink()
        return path

    def test_db_init_migrates_score_metadata_columns(self) -> None:
        database_path = self.fresh_database_path("phase4_schema.sqlite")

        initialize_database(database_path)

        with sqlite_connection_for_test(database_path) as connection:
            columns = {
                row[1]
                for row in connection.execute("PRAGMA table_info(scores)").fetchall()
            }
        self.assertIn("asset_type", columns)
        self.assertIn("score_model", columns)
        self.assertIn("threshold_set", columns)
        self.assertIn("score_reason", columns)
        self.assertIn("data_warnings", columns)

    def test_config_loads_scoring_defaults(self) -> None:
        config = load_config(PROJECT_ROOT / "configs" / "default.toml")

        self.assertEqual(config.scoring_equity_model_version, "equity_score_mvp_v1")
        self.assertEqual(config.scoring_etf_model_version, "etf_score_mvp_v1")
        self.assertEqual(config.scoring_equity_threshold_set, "equity_default")
        self.assertEqual(config.scoring_etf_threshold_set, "etf_liquid_index")

    def test_score_upsert_list_and_latest_are_idempotent(self) -> None:
        database_path = self.fresh_database_path("phase4_storage.sqlite")
        initialize_database(database_path)
        score = Score(
            ticker="AAPL",
            score_date="2026-06-06",
            opportunity_score=77,
            asset_type="equity",
            score_model="equity_score_mvp_v1",
            threshold_set="equity_default",
            model_version="equity_score_mvp_v1",
            source="scoring",
        )

        upsert_score(database_path, score)
        upsert_score(database_path, score)

        scores = list_scores(database_path, "AAPL")
        self.assertEqual(len(scores), 1)
        self.assertEqual(count_rows_by_table(database_path, "scores"), 1)
        self.assertEqual(latest_score_date(database_path), "2026-06-06")

    def test_equity_scoring_computes_deterministic_scores(self) -> None:
        database_path = self.fresh_database_path("phase4_equity.sqlite")
        config = make_config(database_path)
        seed_equity_fixture(database_path)

        result = compute_scores(config, ticker="AAPL")
        second_result = compute_scores(config, ticker="AAPL")
        scores = list_scores(database_path, "AAPL")

        self.assertEqual(result.computed_count, 1)
        self.assertEqual(second_result.computed_count, 1)
        self.assertEqual(len(scores), 1)
        self.assertIsNotNone(scores[0].opportunity_score)
        assert scores[0].opportunity_score is not None
        self.assertGreater(scores[0].opportunity_score, 50)
        self.assertLessEqual(scores[0].opportunity_score, 100)
        self.assertEqual(scores[0].score_model, "equity_score_mvp_v1")
        self.assertEqual(scores[0].threshold_set, "equity_default")

    def test_compute_scores_asset_type_filter_scores_only_equities(self) -> None:
        database_path = self.fresh_database_path("phase4_filter.sqlite")
        config = make_config(database_path)
        seed_equity_fixture(database_path, "AAPL")
        upsert_asset(database_path, Asset(ticker="SPY", asset_type="etf"))

        result = compute_scores(config, asset_type="equity")

        self.assertEqual(result.computed_count, 1)
        self.assertEqual([item.ticker for item in result.results], ["AAPL"])

    def test_missing_inputs_and_etf_missing_nav_skip_without_crashing(self) -> None:
        database_path = self.fresh_database_path("phase4_missing.sqlite")
        config = make_config(database_path)
        initialize_database(database_path)
        upsert_asset(database_path, Asset(ticker="AAPL", asset_type="equity"))
        upsert_asset(database_path, Asset(ticker="SPY", asset_type="etf"))

        result = compute_scores(config)
        by_ticker = {item.ticker: item for item in result.results}

        self.assertEqual(result.skipped_count, 2)
        self.assertIn("missing_target", by_ticker["AAPL"].warnings)
        self.assertIn("missing_etf_nav", by_ticker["SPY"].warnings)

    def test_etf_fixture_with_nav_features_can_score(self) -> None:
        database_path = self.fresh_database_path("phase4_etf.sqlite")
        config = make_config(database_path)
        today = date.today().isoformat()
        initialize_database(database_path)
        upsert_asset(database_path, Asset(ticker="SPY", asset_type="etf"))
        upsert_price_feature(
            database_path,
            PriceFeature(
                ticker="SPY",
                feature_date=today,
                current_price=100,
                return_1d=0.01,
                return_1m=0.02,
                return_3m=0.04,
                return_6m=0.06,
                return_12m=0.08,
                realized_volatility_20d=0.10,
                realized_volatility_60d=0.12,
                average_dollar_volume_20d=5_000_000_000,
                latest_price_date=today,
            ),
        )
        upsert_etf_feature(
            database_path,
            EtfFeature(
                ticker="SPY",
                feature_date=today,
                nav_per_share=101,
                market_price=100,
                premium_discount=-0.01,
                premium_discount_average_60d=-0.001,
                premium_discount_volatility_60d=0.005,
                premium_discount_zscore=-1.8,
                holdings_count=500,
                top_10_weight=0.30,
                largest_holding_weight=0.07,
                equity_weight=0.99,
                cash_weight=0.01,
                latest_nav_date=today,
                latest_holdings_date=today,
            ),
        )

        result = compute_scores(config, ticker="SPY")
        scores = list_scores(database_path, "SPY")

        self.assertEqual(result.computed_count, 1)
        self.assertEqual(len(scores), 1)
        self.assertEqual(scores[0].score_model, "etf_score_mvp_v1")
        self.assertEqual(scores[0].threshold_set, "etf_liquid_index")

    def test_score_cli_and_status_output(self) -> None:
        database_path = self.fresh_database_path("phase4_cli.sqlite")
        config = make_config(database_path)
        write_config(config)
        seed_equity_fixture(database_path)

        compute_output = io.StringIO()
        with redirect_stdout(compute_output):
            compute_exit = command_compute_scores(
                Namespace(config=config.config_path, ticker="AAPL", asset_type=None)
            )
        status_output = io.StringIO()
        with redirect_stdout(status_output):
            status_exit = command_score_status(Namespace(config=config.config_path))

        self.assertEqual(compute_exit, 0)
        self.assertEqual(status_exit, 0)
        self.assertIn("AAPL", compute_output.getvalue())
        self.assertIn("Opportunity", status_output.getvalue())
        self.assertTrue(score_statuses(database_path)[0].opportunity_score)


if __name__ == "__main__":
    unittest.main()
