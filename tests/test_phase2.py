from __future__ import annotations

from argparse import Namespace
from contextlib import redirect_stdout
from datetime import date, timedelta
from pathlib import Path
import io
import json
import math
import sys
import unittest
from unittest.mock import patch


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
TEST_TMP_ROOT = PROJECT_ROOT / ".tmp_tests"
sys.path.insert(0, str(SRC_PATH))

from target_opportunity_monitor.cli import command_price_status
from target_opportunity_monitor.config import AppConfig
from target_opportunity_monitor.db import REQUIRED_TABLES, initialize_database
from target_opportunity_monitor.market_data import (
    compute_price_feature,
    fetch_yahoo_chart_prices,
    parse_yahoo_chart_json,
    parse_price_csv,
    provider_symbol_alias,
    stooq_symbol,
    update_prices,
    yahoo_chart_url,
)
from target_opportunity_monitor.storage import (
    Asset,
    Price,
    count_rows_by_table,
    list_prices,
    upsert_asset,
    upsert_price,
)


def make_config(database_path: Path, manual_prices_dir: Path) -> AppConfig:
    return AppConfig(
        project_root=TEST_TMP_ROOT,
        config_path=TEST_TMP_ROOT / "phase2.toml",
        database_path=database_path,
        reports_dir=TEST_TMP_ROOT / "reports",
        watchlist_path=TEST_TMP_ROOT / "watchlist.csv",
        market_data_dir=TEST_TMP_ROOT / "market_data",
        manual_prices_dir=manual_prices_dir,
        market_data_primary_source="stooq",
        market_data_secondary_source="yahoo_chart",
        market_data_mode="auto",
        market_data_lookback_days=800,
        market_data_stale_after_days=7,
        market_data_minimum_history_days=252,
        universe_mode="manual_watchlist",
        run_mode="daily_scoring",
        report_title="Target Opportunity Monitor Daily Report",
    )


def write_config(config: AppConfig) -> None:
    config.config_path.write_text(
        "\n".join(
            (
                "[paths]",
                f'database = "{config.database_path.as_posix()}"',
                f'reports = "{config.reports_dir.as_posix()}"',
                f'watchlist = "{config.watchlist_path.as_posix()}"',
                f'market_data = "{config.market_data_dir.as_posix()}"',
                f'manual_prices = "{config.manual_prices_dir.as_posix()}"',
                "",
                "[market_data]",
                f'primary_source = "{config.market_data_primary_source}"',
                f'secondary_source = "{config.market_data_secondary_source}"',
                f'mode = "{config.market_data_mode}"',
                f"lookback_days = {config.market_data_lookback_days}",
                f"stale_after_days = {config.market_data_stale_after_days}",
                f"minimum_history_days = {config.market_data_minimum_history_days}",
                "",
                "[run]",
                f'universe_mode = "{config.universe_mode}"',
                f'run_mode = "{config.run_mode}"',
                "",
                "[reports]",
                f'title = "{config.report_title}"',
                "",
            )
        ),
        encoding="utf-8",
    )


class Phase2Tests(unittest.TestCase):
    def setUp(self) -> None:
        TEST_TMP_ROOT.mkdir(exist_ok=True)

    def fresh_database_path(self, name: str) -> Path:
        path = TEST_TMP_ROOT / name
        if path.exists():
            path.unlink()
        return path

    def test_stooq_symbol_mapping_for_us_assets(self) -> None:
        self.assertEqual(stooq_symbol("AAPL", "US"), "aapl.us")
        self.assertEqual(stooq_symbol("SPY", "US"), "spy.us")
        self.assertEqual(stooq_symbol("BRK.B", "US"), "brk.b.us")
        self.assertIn("/BRK-B?", yahoo_chart_url("BRK.B", 30))
        self.assertIn("/SIVE.ST?", yahoo_chart_url("SIVE.ST", 30, provider_symbol=True))

    def test_yahoo_fetch_uses_source_backed_provider_symbol_alias(self) -> None:
        database_path = self.fresh_database_path("provider_symbol_alias.sqlite")
        manual_prices_dir = TEST_TMP_ROOT / "manual_prices_provider_alias"
        manual_prices_dir.mkdir(exist_ok=True)
        config = make_config(database_path, manual_prices_dir)
        alias_path = config.market_data_symbol_aliases_path
        if not alias_path.is_absolute():
            alias_path = config.project_root / alias_path
        alias_path.parent.mkdir(parents=True, exist_ok=True)
        alias_path.write_text(
            "\n".join(
                (
                    "ticker,provider,symbol,source,source_url,as_of_date,effective_date,notes",
                    "SIVE,yahoo_chart,SIVE.ST,issuer_investor_page,https://example.com/sive,2026-06-15,2026-06-15,Provider alias.",
                )
            ),
            encoding="utf-8",
        )
        payload = {
            "chart": {
                "result": [
                    {
                        "timestamp": [1767225600],
                        "indicators": {
                            "quote": [
                                {
                                    "open": [10.0],
                                    "high": [11.0],
                                    "low": [9.5],
                                    "close": [10.5],
                                    "volume": [1234],
                                }
                            ],
                            "adjclose": [{"adjclose": [10.4]}],
                        },
                    }
                ],
                "error": None,
            }
        }

        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def read(self) -> bytes:
                return json.dumps(payload).encode("utf-8")

        captured_urls: list[str] = []

        def fake_urlopen(request, timeout):
            captured_urls.append(request.full_url)
            return FakeResponse()

        asset = Asset(
            ticker="SIVE",
            name="Sivers Semiconductors AB",
            asset_type="equity",
            exchange="Nasdaq Stockholm",
            currency="SEK",
            country="Sweden",
        )
        with patch("target_opportunity_monitor.market_data.urlopen", fake_urlopen):
            prices = fetch_yahoo_chart_prices(asset, 30, config=config)

        self.assertEqual(provider_symbol_alias(config, "SIVE", "yahoo_chart"), "SIVE.ST")
        self.assertIn("/SIVE.ST?", captured_urls[0])
        self.assertEqual(prices[0].ticker, "SIVE")
        self.assertEqual(prices[0].adjusted_close, 10.4)

    def test_price_csv_parser_handles_adjusted_and_unadjusted_csv(self) -> None:
        with_adjusted = "\n".join(
            (
                "date,open,high,low,close,adjusted_close,volume",
                "2026-01-02,10,11,9,10.5,10.4,1000",
            )
        )
        without_adjusted = "\n".join(
            (
                "date,open,high,low,close,volume",
                "2026-01-03,11,12,10,11.5,1100",
            )
        )

        adjusted = parse_price_csv(with_adjusted, "AAPL", "manual_csv")
        unadjusted = parse_price_csv(without_adjusted, "AAPL", "manual_csv")

        self.assertEqual(adjusted[0].adjusted_close, 10.4)
        self.assertEqual(unadjusted[0].adjusted_close, 11.5)

    def test_yahoo_chart_json_parser_handles_valid_payload(self) -> None:
        text = """
        {
          "chart": {
            "result": [{
              "timestamp": [1767225600, 1767312000],
              "indicators": {
                "quote": [{
                  "open": [10, 11],
                  "high": [12, 13],
                  "low": [9, 10],
                  "close": [11, 12],
                  "volume": [1000, 1100]
                }],
                "adjclose": [{
                  "adjclose": [10.5, 11.5]
                }]
              }
            }],
            "error": null
          }
        }
        """

        prices = parse_yahoo_chart_json(text, "AAPL")

        self.assertEqual(len(prices), 2)
        self.assertEqual(prices[0].source, "yahoo_chart")
        self.assertEqual(prices[1].adjusted_close, 11.5)

    def test_price_upsert_is_idempotent(self) -> None:
        database_path = self.fresh_database_path("phase2_price_upsert.sqlite")
        initialize_database(database_path)

        upsert_price(
            database_path,
            Price("AAPL", "2026-01-02", 10, 11, 9, 10.5, 10.5, 1000, "manual_csv"),
        )
        upsert_price(
            database_path,
            Price("AAPL", "2026-01-02", 10, 11, 9, 12.5, 12.5, 1200, "manual_csv"),
        )

        prices = list_prices(database_path, "AAPL")
        self.assertEqual(len(prices), 1)
        self.assertEqual(prices[0].close, 12.5)
        self.assertEqual(prices[0].volume, 1200)

    def test_feature_calculation_returns_expected_values(self) -> None:
        start = date(2025, 1, 1)
        prices = []
        for offset in range(253):
            close = 100.0 + offset
            prices.append(
                Price(
                    ticker="AAPL",
                    price_date=(start + timedelta(days=offset)).isoformat(),
                    open=close - 0.5,
                    high=close + 1,
                    low=close - 1,
                    close=close,
                    adjusted_close=close,
                    volume=1000 + offset,
                    source="manual_csv",
                )
            )

        feature = compute_price_feature("AAPL", prices)

        self.assertIsNotNone(feature)
        assert feature is not None
        self.assertAlmostEqual(feature.return_1d, 352 / 351 - 1)
        self.assertAlmostEqual(feature.return_1m, 352 / 331 - 1)
        self.assertAlmostEqual(feature.return_3m, 352 / 289 - 1)
        self.assertAlmostEqual(feature.return_6m, 352 / 226 - 1)
        self.assertAlmostEqual(feature.return_12m, 352 / 100 - 1)
        self.assertGreater(feature.realized_volatility_20d or 0, 0)
        self.assertGreater(feature.realized_volatility_60d or 0, 0)
        expected_adv = sum((100 + i) * (1000 + i) for i in range(233, 253)) / 20
        self.assertAlmostEqual(feature.average_dollar_volume_20d or math.nan, expected_adv)

    def test_online_failure_falls_back_to_local_csv(self) -> None:
        database_path = self.fresh_database_path("phase2_fallback.sqlite")
        manual_prices_dir = TEST_TMP_ROOT / "manual_prices_fallback"
        manual_prices_dir.mkdir(exist_ok=True)
        (manual_prices_dir / "AAPL.csv").write_text(
            "\n".join(
                (
                    "date,open,high,low,close,volume",
                    "2026-06-04,10,11,9,10,1000",
                    "2026-06-05,11,12,10,11,1100",
                )
            ),
            encoding="utf-8",
        )
        initialize_database(database_path)
        upsert_asset(database_path, Asset(ticker="AAPL"))
        config = make_config(database_path, manual_prices_dir)

        def failing_fetcher(asset: Asset, lookback_days: int) -> list[Price]:
            raise ValueError("online failed")

        result = update_prices(
            config,
            online_fetcher=failing_fetcher,
            secondary_online_fetcher=failing_fetcher,
        )

        self.assertEqual(result.loaded_count, 1)
        self.assertEqual(result.results[0].source, "manual_csv")
        self.assertEqual(count_rows_by_table(database_path, "prices"), 2)
        self.assertEqual(count_rows_by_table(database_path, "price_features"), 1)

    def test_auto_mode_uses_yahoo_when_stooq_fails(self) -> None:
        database_path = self.fresh_database_path("phase2_yahoo_fallback.sqlite")
        manual_prices_dir = TEST_TMP_ROOT / "manual_prices_yahoo"
        manual_prices_dir.mkdir(exist_ok=True)
        initialize_database(database_path)
        upsert_asset(database_path, Asset(ticker="AAPL"))
        config = make_config(database_path, manual_prices_dir)

        def failing_fetcher(asset: Asset, lookback_days: int) -> list[Price]:
            raise ValueError("stooq failed")

        def yahoo_fetcher(asset: Asset, lookback_days: int) -> list[Price]:
            return [
                Price(asset.ticker, "2026-06-04", 10, 11, 9, 10, 10, 1000, "yahoo_chart"),
                Price(asset.ticker, "2026-06-05", 11, 12, 10, 11, 11, 1100, "yahoo_chart"),
            ]

        result = update_prices(
            config,
            online_fetcher=failing_fetcher,
            secondary_online_fetcher=yahoo_fetcher,
        )

        self.assertEqual(result.loaded_count, 1)
        self.assertEqual(result.results[0].source, "yahoo_chart")
        self.assertEqual(count_rows_by_table(database_path, "prices"), 2)

    def test_missing_and_stale_prices_create_quality_warnings(self) -> None:
        database_path = self.fresh_database_path("phase2_quality.sqlite")
        manual_prices_dir = TEST_TMP_ROOT / "manual_prices_quality"
        manual_prices_dir.mkdir(exist_ok=True)
        (manual_prices_dir / "AAPL.csv").write_text(
            "\n".join(
                (
                    "date,open,high,low,close,volume",
                    "2020-01-02,10,11,9,10,1000",
                )
            ),
            encoding="utf-8",
        )
        initialize_database(database_path)
        upsert_asset(database_path, Asset(ticker="AAPL"))
        upsert_asset(database_path, Asset(ticker="MSFT"))
        config = make_config(database_path, manual_prices_dir)

        result = update_prices(config, source_mode="csv")

        self.assertEqual(result.loaded_count, 1)
        self.assertEqual(result.failed_count, 1)
        self.assertGreaterEqual(count_rows_by_table(database_path, "data_quality_checks"), 3)

    def test_price_status_works_after_price_loading(self) -> None:
        database_path = self.fresh_database_path("phase2_price_status.sqlite")
        manual_prices_dir = TEST_TMP_ROOT / "manual_prices_status"
        manual_prices_dir.mkdir(exist_ok=True)
        (manual_prices_dir / "AAPL.csv").write_text(
            "\n".join(
                (
                    "date,open,high,low,close,volume",
                    f"{date.today().isoformat()},10,11,9,10,1000",
                )
            ),
            encoding="utf-8",
        )
        initialize_database(database_path)
        upsert_asset(database_path, Asset(ticker="AAPL"))
        config = make_config(database_path, manual_prices_dir)
        write_config(config)
        update_prices(config, source_mode="csv")

        output = io.StringIO()
        with redirect_stdout(output):
            command_price_status(Namespace(config=config.config_path))

        text = output.getvalue()
        self.assertIn("Ticker | Rows | Latest Price Date", text)
        self.assertIn("AAPL | 1", text)

    def test_init_db_creates_price_features_table(self) -> None:
        database_path = self.fresh_database_path("phase2_required_tables.sqlite")

        status = initialize_database(database_path)

        self.assertIn("price_features", status.existing_tables)
        self.assertEqual(status.existing_required_table_count, len(REQUIRED_TABLES))


if __name__ == "__main__":
    unittest.main()
