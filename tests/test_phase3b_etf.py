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

from target_opportunity_monitor.cli import (
    command_compute_targets,
    command_etf_status,
    command_load_etf_holdings,
    command_load_etf_navs,
    command_status,
    command_valuation_status,
)
from target_opportunity_monitor.config import AppConfig
from target_opportunity_monitor.db import REQUIRED_TABLES, initialize_database
from target_opportunity_monitor.etf_data import (
    load_etf_holdings_csv,
    load_etf_navs_csv,
    parse_etf_holdings_csv,
    parse_etf_navs_csv,
)
from target_opportunity_monitor.reporting import write_daily_report
from target_opportunity_monitor.storage import (
    Asset,
    PriceFeature,
    count_rows_by_table,
    latest_etf_feature,
    list_targets,
    upsert_asset,
    upsert_price_feature,
)
from target_opportunity_monitor.valuation import compute_targets


def make_config(database_path: Path) -> AppConfig:
    return AppConfig(
        project_root=TEST_TMP_ROOT,
        config_path=TEST_TMP_ROOT / "phase3b.toml",
        database_path=database_path,
        reports_dir=TEST_TMP_ROOT / "reports_phase3b",
        watchlist_path=TEST_TMP_ROOT / "watchlist_phase3b.csv",
        market_data_dir=TEST_TMP_ROOT / "market_data_phase3b",
        manual_prices_dir=TEST_TMP_ROOT / "market_data_phase3b" / "manual",
        market_data_primary_source="stooq",
        market_data_secondary_source="yahoo_chart",
        market_data_mode="auto",
        market_data_lookback_days=800,
        market_data_stale_after_days=7,
        market_data_minimum_history_days=252,
        universe_mode="manual_watchlist",
        run_mode="daily_scoring",
        report_title="Target Opportunity Monitor Daily Report",
        etf_navs_path=TEST_TMP_ROOT / "etf_navs.csv",
        etf_holdings_path=TEST_TMP_ROOT / "etf_holdings.csv",
    )


def write_config(config: AppConfig) -> None:
    config.config_path.write_text(
        "\n".join(
            (
                "[paths]",
                f'database = "{config.database_path.as_posix()}"',
                f'reports = "{config.reports_dir.as_posix()}"',
                f'watchlist = "{config.watchlist_path.as_posix()}"',
                f'etf_navs = "{config.etf_navs_path.as_posix()}"',
                f'etf_holdings = "{config.etf_holdings_path.as_posix()}"',
                "",
                "[etf]",
                f'model_version = "{config.etf_model_version}"',
                f"default_premium_discount_band = {config.etf_default_premium_discount_band}",
                f"stale_nav_after_days = {config.etf_stale_nav_after_days}",
                f"stale_holdings_after_days = {config.etf_stale_holdings_after_days}",
                f"minimum_holdings = {config.etf_minimum_holdings}",
                f"premium_discount_history_days = {config.etf_premium_discount_history_days}",
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


def seed_spy_asset_and_price(database_path: Path, price: float = 100.0) -> None:
    initialize_database(database_path)
    upsert_asset(
        database_path,
        Asset(
            ticker="SPY",
            name="SPDR S&P 500 ETF Trust",
            asset_type="etf",
            sector="ETF",
            industry="Broad Market",
        ),
    )
    upsert_price_feature(
        database_path,
        PriceFeature(
            ticker="SPY",
            feature_date=date.today().isoformat(),
            current_price=price,
            return_1d=None,
            return_1m=None,
            return_3m=None,
            return_6m=None,
            return_12m=None,
            realized_volatility_20d=None,
            realized_volatility_60d=None,
            average_dollar_volume_20d=None,
            latest_price_date=date.today().isoformat(),
        ),
    )


def write_etf_fixture_files(config: AppConfig) -> None:
    today = date.today().isoformat()
    config.etf_navs_path.write_text(
        "\n".join(
            (
                "ticker,nav_date,nav_per_share,market_price,source",
                "SPY,2026-06-05,100,99,manual_csv",
                f"SPY,{today},101,100,manual_csv",
            )
        ),
        encoding="utf-8",
    )
    holding_rows = [
        "ticker,holdings_date,holding_ticker,holding_name,holding_asset_type,weight,sector,country,source"
    ]
    for index in range(10):
        holding_rows.append(
            f"SPY,{today},H{index},Holding {index},equity,10,Technology,US,manual_csv"
        )
    config.etf_holdings_path.write_text("\n".join(holding_rows), encoding="utf-8")


class Phase3BEtfTests(unittest.TestCase):
    def setUp(self) -> None:
        TEST_TMP_ROOT.mkdir(exist_ok=True)

    def fresh_database_path(self, name: str) -> Path:
        path = TEST_TMP_ROOT / name
        if path.exists():
            path.unlink()
        return path

    def test_init_db_creates_etf_tables(self) -> None:
        database_path = self.fresh_database_path("phase3b_schema.sqlite")

        status = initialize_database(database_path)

        self.assertIn("etf_navs", status.existing_tables)
        self.assertIn("etf_holdings", status.existing_tables)
        self.assertIn("etf_features", status.existing_tables)
        self.assertEqual(status.existing_required_table_count, len(REQUIRED_TABLES))

    def test_etf_csv_parsers_accept_valid_rows_and_reject_bad_inputs(self) -> None:
        navs = parse_etf_navs_csv(
            "\n".join(
                (
                    "ticker,nav_date,nav_per_share,market_price,premium_discount",
                    "spy,2026-06-06,101,100,-0.99%",
                )
            )
        )
        holdings = parse_etf_holdings_csv(
            "\n".join(
                (
                    "ticker,holdings_date,holding_ticker,holding_name,holding_asset_type,weight",
                    "spy,2026-06-06,aapl,Apple Inc.,equity,7.5",
                )
            )
        )

        self.assertEqual(navs[0].ticker, "SPY")
        self.assertAlmostEqual(navs[0].premium_discount or 0, -0.0099)
        self.assertEqual(holdings[0].holding_ticker, "AAPL")
        self.assertAlmostEqual(holdings[0].weight, 0.075)

        with self.assertRaises(ValueError):
            parse_etf_navs_csv("ticker,nav_date,nav_per_share\nSPY,bad-date,101\n")
        with self.assertRaises(ValueError):
            parse_etf_holdings_csv(
                "ticker,holdings_date,weight\nSPY,2026-06-06,0.1\n"
            )

    def test_default_etf_seed_files_cover_spy_and_qqq(self) -> None:
        navs = parse_etf_navs_csv(
            (PROJECT_ROOT / "data" / "etf" / "manual" / "etf_navs.csv").read_text(
                encoding="utf-8-sig"
            )
        )
        holdings = parse_etf_holdings_csv(
            (
                PROJECT_ROOT / "data" / "etf" / "manual" / "etf_holdings.csv"
            ).read_text(encoding="utf-8-sig")
        )

        nav_tickers = {nav.ticker for nav in navs}
        holdings_by_ticker: dict[str, int] = {}
        for holding in holdings:
            holdings_by_ticker[holding.ticker] = holdings_by_ticker.get(holding.ticker, 0) + 1

        self.assertIn("SPY", nav_tickers)
        self.assertIn("QQQ", nav_tickers)
        self.assertGreaterEqual(holdings_by_ticker.get("SPY", 0), 10)
        self.assertGreaterEqual(holdings_by_ticker.get("QQQ", 0), 10)

    def test_etf_loaders_are_idempotent_and_compute_features(self) -> None:
        database_path = self.fresh_database_path("phase3b_loaders.sqlite")
        config = make_config(database_path)
        seed_spy_asset_and_price(database_path)
        write_etf_fixture_files(config)

        load_etf_navs_csv(database_path, config.etf_navs_path)
        load_etf_navs_csv(database_path, config.etf_navs_path)
        load_etf_holdings_csv(database_path, config.etf_holdings_path)
        load_etf_holdings_csv(database_path, config.etf_holdings_path)

        self.assertEqual(count_rows_by_table(database_path, "etf_navs"), 2)
        self.assertEqual(count_rows_by_table(database_path, "etf_holdings"), 10)
        self.assertEqual(count_rows_by_table(database_path, "etf_features"), 1)
        feature = latest_etf_feature(database_path, "SPY")
        self.assertIsNotNone(feature)
        assert feature is not None
        self.assertEqual(feature.holdings_count, 10)
        self.assertAlmostEqual(feature.top_10_weight or 0, 1.0)
        self.assertIsNotNone(feature.premium_discount_zscore)

    def test_compute_targets_writes_etf_target_for_spy(self) -> None:
        database_path = self.fresh_database_path("phase3b_target.sqlite")
        config = make_config(database_path)
        seed_spy_asset_and_price(database_path)
        write_etf_fixture_files(config)
        load_etf_navs_csv(database_path, config.etf_navs_path)
        load_etf_holdings_csv(database_path, config.etf_holdings_path)

        result = compute_targets(config, ticker="SPY")
        target = list_targets(database_path, "SPY")[0]

        self.assertEqual(result.computed_count, 1)
        self.assertEqual(target.source, "etf_valuation")
        self.assertEqual(target.model_version, "etf_nav_mvp_v1")
        self.assertEqual(target.target_method, "etf_nav")
        self.assertAlmostEqual(target.base_target or 0, 101.0)
        self.assertAlmostEqual(target.valuation_gap or 0, 0.01)
        self.assertNotIn("unsupported_asset_type", result.results[0].warnings)

    def test_compute_targets_flags_missing_etf_nav_without_unsupported_warning(self) -> None:
        database_path = self.fresh_database_path("phase3b_missing_nav.sqlite")
        config = make_config(database_path)
        seed_spy_asset_and_price(database_path)

        result = compute_targets(config, ticker="SPY")

        self.assertEqual(result.skipped_count, 1)
        self.assertIn("missing_etf_nav", result.results[0].warnings)
        self.assertNotIn("unsupported_asset_type", result.results[0].warnings)

    def test_cli_status_and_report_include_etf_outputs(self) -> None:
        database_path = self.fresh_database_path("phase3b_cli.sqlite")
        config = make_config(database_path)
        seed_spy_asset_and_price(database_path)
        write_etf_fixture_files(config)
        write_config(config)

        output = io.StringIO()
        with redirect_stdout(output):
            command_load_etf_navs(Namespace(config=config.config_path, file=None))
            command_load_etf_holdings(Namespace(config=config.config_path, file=None))
            command_compute_targets(Namespace(config=config.config_path, ticker="SPY"))
            command_etf_status(Namespace(config=config.config_path))
            command_valuation_status(Namespace(config=config.config_path))
            command_status(Namespace(config=config.config_path))

        text = output.getvalue()
        self.assertIn("ETF NAVs loaded: 2 rows", text)
        self.assertIn("ETF holdings loaded: 10 rows", text)
        self.assertIn("SPY: status=computed", text)
        self.assertIn("Ticker | Price | NAV | Premium/Discount", text)
        self.assertIn("SPY | 100.0000 | 101.0000", text)
        self.assertIn("ETF NAV rows: 2", text)
        self.assertIn("ETF holding rows: 10", text)

        report = write_daily_report(config, run_date=date.today())
        body = report.path.read_text(encoding="utf-8")
        self.assertIn("## ETF Status", body)
        self.assertIn("ETF target coverage: `1/1`", body)
        self.assertIn("SPY", body)


if __name__ == "__main__":
    unittest.main()
