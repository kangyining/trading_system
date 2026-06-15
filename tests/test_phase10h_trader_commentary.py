from __future__ import annotations

from argparse import Namespace
from contextlib import redirect_stdout
from datetime import date, timedelta
from pathlib import Path
import csv
import io
import shutil
import sys
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
TEST_TMP_ROOT = PROJECT_ROOT / ".tmp_tests" / "phase10h"
sys.path.insert(0, str(SRC_PATH))

from target_opportunity_monitor.cli import (
    command_export_trader_commentary_template,
    command_parse_trader_commentary_claims,
    command_status,
    command_trader_commentary_parse_review,
    command_trader_commentary_status,
    command_trader_commentary_validation_report,
    command_validate_trader_commentary_claims,
)
from target_opportunity_monitor.config import AppConfig, load_config
from target_opportunity_monitor.dashboard import build_dashboard
from target_opportunity_monitor.db import REQUIRED_TABLES, initialize_database
from target_opportunity_monitor.reporting import REPORT_CSV_COLUMNS, write_daily_report
from target_opportunity_monitor.storage import (
    Asset,
    Price,
    Score,
    count_rows_by_table,
    list_scores,
    list_stored_signals,
    list_trader_commentary_claim_outcomes,
    list_trader_commentary_claims,
    list_trader_commentary_raw,
    trader_commentary_statuses,
    upsert_asset,
    upsert_prices,
    upsert_score,
)
from target_opportunity_monitor.trader_commentary import (
    TRADER_COMMENTARY_HEADER,
    build_trader_commentary_parse_review,
    ensure_trader_commentary_csv_header,
    export_trader_commentary_template,
    load_trader_commentary_csv,
    parse_trader_commentary_claims,
    parse_trader_commentary_csv,
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
        config_path=TEST_TMP_ROOT / f"phase10h_{database_path.stem}.toml",
        database_path=database_path,
        reports_dir=TEST_TMP_ROOT / "reports_phase10h",
        watchlist_path=TEST_TMP_ROOT / "watchlist_phase10h.csv",
        market_data_dir=TEST_TMP_ROOT / "market_data_phase10h",
        manual_prices_dir=TEST_TMP_ROOT / "market_data_phase10h" / "manual",
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
                "[run]",
                'universe_mode = "manual_watchlist"',
                'run_mode = "daily_scoring"',
                "",
            )
        ),
        encoding="utf-8",
    )


def seed_assets(database_path: Path) -> None:
    initialize_database(database_path)
    for ticker in ("TSLA", "HOOD", "KORU"):
        upsert_asset(database_path, Asset(ticker=ticker, asset_type="equity"))
    upsert_asset(database_path, Asset(ticker="SPY", asset_type="etf"))


def make_price(ticker: str, price_date: str, close: float) -> Price:
    return Price(
        ticker=ticker,
        price_date=price_date,
        open=close,
        high=close + 2,
        low=close - 2,
        close=close,
        adjusted_close=close,
        volume=1_000_000,
        source="fixture",
        as_of_date=price_date,
        effective_date=price_date,
    )


def seed_prices(database_path: Path) -> None:
    start = date(2026, 6, 1)
    tsla_prices = [
        make_price("TSLA", (start + timedelta(days=index)).isoformat(), 390 + index)
        for index in range(8)
    ]
    hood_prices = [
        make_price("HOOD", (start + timedelta(days=index)).isoformat(), 90 + 2 * index)
        for index in range(8)
    ]
    koru_prices = [
        make_price("KORU", (start + timedelta(days=index)).isoformat(), 620 + index)
        for index in range(8)
    ]
    upsert_prices(database_path, tsla_prices + hood_prices + koru_prices)


def write_commentary_csv(config: AppConfig, rows: list[dict[str, str]]) -> None:
    config.trader_commentary_path.parent.mkdir(parents=True, exist_ok=True)
    with config.trader_commentary_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=TRADER_COMMENTARY_HEADER)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


COMMENTARY_TEXT = (
    "\u987a\u54e5\u3002\u4eca\u5929\u80a1\u5e02\u5927\u76d8\u6ca1\u6709"
    "\u7a81\u7834\u6211\u8bf4\u7684\u70b9\u4f4d7440-7460\uff0c"
    "\u6240\u4ee5\u8d8b\u52bf\u8fd8\u4e0d\u80fd\u4fee\u590d\u53cd\u8f6c\u3002"
    "\u4e0b\u6765\u77ed\u671f\u538b\u529b416-418\u3002"
    "Tsla \u6ca1\u6709\u8dcc\u7834\u6211\u5728VIP\u7fa4\u91cc\u63d0\u5230"
    "\u7684384-386 \u725b\u8d8b\u52bf\u652f\u6491\u3002"
    "\u867d\u7136\u6050\u614c\uff0c\u4f46\u662f\u6211\u89c9\u5f97\u53ef\u4ee5"
    "\u4e70Hood\u3002\u4e2d\u957f\u7ebf\u7cfb\u7edf\u770b100\u3002"
    "\u6709\u7fa4\u53cb\u5f00\u59cbsell put Koru 600,\u7ed9\u4f60100 premium\u3002"
)


class Phase10HTraderCommentaryTests(unittest.TestCase):
    def tearDown(self) -> None:
        if TEST_TMP_ROOT.exists():
            shutil.rmtree(TEST_TMP_ROOT)

    def test_config_defaults_schema_and_csv_header(self) -> None:
        config = load_config(PROJECT_ROOT / "configs" / "default.toml")
        self.assertEqual(
            config.trader_commentary_path,
            PROJECT_ROOT / "data" / "signals" / "manual" / "trader_commentary.csv",
        )
        self.assertEqual(
            config.trader_commentary_exports_dir,
            PROJECT_ROOT / "data" / "signals" / "source_exports" / "trader_commentary",
        )
        self.assertEqual(config.signals_trader_commentary_model_version, "trader_commentary_mvp_v1")
        self.assertTrue(config.signals_trader_commentary_shadow_mode)

        database_path = fresh_database_path("phase10h_schema.sqlite")
        status = initialize_database(database_path)
        self.assertIn("trader_commentary_raw", status.existing_tables)
        self.assertIn("trader_commentary_claims", status.existing_tables)
        self.assertIn("trader_commentary_claim_outcomes", status.existing_tables)
        self.assertEqual(status.existing_required_table_count, len(REQUIRED_TABLES))

        header_path = TEST_TMP_ROOT / "commentary.csv"
        ensure_trader_commentary_csv_header(header_path)
        ensure_trader_commentary_csv_header(header_path)
        self.assertEqual(
            header_path.read_text(encoding="utf-8").strip(),
            ",".join(TRADER_COMMENTARY_HEADER),
        )

    def test_csv_loader_accepts_inline_and_text_file_and_rejects_bad_rows(self) -> None:
        database_path = fresh_database_path("phase10h_loader.sqlite")
        config = make_config(database_path)
        seed_assets(database_path)
        config.trader_commentary_exports_dir.mkdir(parents=True, exist_ok=True)
        text_file = config.trader_commentary_exports_dir / "commentary_note.txt"
        text_file.write_text("TSLA support 384-386", encoding="utf-8")
        write_commentary_csv(
            config,
            [
                {
                    "capture_date": "2026-06-01",
                    "source": "vip_capture",
                    "source_author": "trader_a",
                    "platform": "wechat",
                    "permission_scope": "private_user_capture",
                    "raw_text": "HOOD target 100",
                    "capture_id": "capture-inline",
                },
                {
                    "capture_date": "2026-06-02",
                    "source": "vip_capture",
                    "source_author": "trader_a",
                    "platform": "wechat",
                    "permission_scope": "private_user_capture",
                    "text_file": "commentary_note.txt",
                    "capture_id": "capture-file",
                },
            ],
        )

        parsed = parse_trader_commentary_csv(
            config.trader_commentary_path.read_text(encoding="utf-8"),
            config,
            config.trader_commentary_path,
        )
        self.assertEqual(len(parsed), 2)
        self.assertIn("TSLA support", parsed[1].raw_text)

        result = load_trader_commentary_csv(config)
        self.assertEqual(result.loaded_count, 2)
        self.assertEqual(count_rows_by_table(database_path, "trader_commentary_raw"), 2)
        self.assertEqual(len(list_trader_commentary_raw(database_path)), 2)

        write_commentary_csv(
            config,
            [
                {
                    "capture_date": "2026-06-03",
                    "source": "vip_capture",
                    "source_author": "",
                    "platform": "wechat",
                    "permission_scope": "private_user_capture",
                    "raw_text": "TSLA support 384",
                    "capture_id": "bad-metadata",
                }
            ],
        )
        with self.assertRaises(ValueError):
            load_trader_commentary_csv(config)

        write_commentary_csv(
            config,
            [
                {
                    "capture_date": "2026-06-03",
                    "source": "vip_capture",
                    "source_author": "trader_a",
                    "platform": "wechat",
                    "permission_scope": "private_user_capture",
                    "capture_id": "",
                }
            ],
        )
        with self.assertRaises(ValueError):
            load_trader_commentary_csv(config)

    def test_template_export_creates_csv_and_text_file(self) -> None:
        database_path = fresh_database_path("phase10h_template.sqlite")
        config = make_config(database_path)
        result = export_trader_commentary_template(config)
        self.assertTrue(result.csv_path.exists())
        self.assertTrue(result.text_path.exists())
        csv_text = result.csv_path.read_text(encoding="utf-8")
        self.assertIn(",".join(TRADER_COMMENTARY_HEADER), csv_text)
        self.assertIn("capture_template_001", csv_text)
        self.assertIn(result.text_path.name, csv_text)

        write_config(config)
        with redirect_stdout(io.StringIO()) as template_output:
            self.assertEqual(
                command_export_trader_commentary_template(
                    Namespace(config=config.config_path)
                ),
                0,
            )
        self.assertIn("Trader commentary template exported", template_output.getvalue())

    def test_parser_extracts_chinese_levels_targets_and_options_proxy(self) -> None:
        database_path = fresh_database_path("phase10h_parser.sqlite")
        config = make_config(database_path)
        seed_assets(database_path)
        write_commentary_csv(
            config,
            [
                {
                    "capture_date": "2026-06-01",
                    "source": "vip_capture",
                    "source_author": "trader_a",
                    "platform": "wechat",
                    "permission_scope": "private_user_capture",
                    "raw_text": COMMENTARY_TEXT,
                    "capture_id": "commentary-1",
                    "language": "zh",
                }
            ],
        )
        load_result = load_trader_commentary_csv(config)
        self.assertEqual(load_result.loaded_count, 1)

        parse_result = parse_trader_commentary_claims(config)
        self.assertGreaterEqual(parse_result.parsed_count, 4)
        claims = list_trader_commentary_claims(database_path)
        claim_types = {claim.claim_type for claim in claims}
        self.assertIn("technical_resistance_watch", claim_types)
        self.assertIn("technical_support_hold", claim_types)
        self.assertIn("ticker_price_target", claim_types)
        self.assertIn("options_income_idea", claim_types)

        support = [claim for claim in claims if claim.claim_type == "technical_support_hold"][0]
        self.assertEqual(support.ticker, "TSLA")
        self.assertEqual(support.level_low, 384)
        self.assertEqual(support.level_high, 386)

        target = [claim for claim in claims if claim.claim_type == "ticker_price_target"][0]
        self.assertEqual(target.ticker, "HOOD")
        self.assertEqual(target.target_price, 100)

        options_claim = [claim for claim in claims if claim.claim_type == "options_income_idea"][0]
        self.assertEqual(options_claim.ticker, "KORU")
        self.assertEqual(options_claim.strike_price, 600)
        self.assertEqual(options_claim.premium, 100)
        self.assertIn("options_proxy_only", options_claim.parser_warnings or "")

        unmapped = [claim for claim in claims if claim.instrument_label]
        self.assertTrue(any(claim.instrument_label == "\u5927\u76d8" for claim in unmapped))
        self.assertTrue(any("unmapped_instrument" in (claim.parser_warnings or "") for claim in unmapped))

        signals = list_stored_signals(database_path, signal_family="trader_commentary")
        self.assertTrue(signals)
        self.assertTrue(any(signal.signal_name == "trader_commentary.composite" for signal in signals))

    def test_parse_review_reports_unmapped_unsupported_and_options_claims(self) -> None:
        database_path = fresh_database_path("phase10h_review.sqlite")
        config = make_config(database_path)
        initialize_database(database_path)
        upsert_asset(database_path, Asset(ticker="TSLA", asset_type="equity"))
        write_commentary_csv(
            config,
            [
                {
                    "capture_date": "2026-06-01",
                    "source": "user_paste",
                    "source_author": "unknown_trader",
                    "platform": "wechat_or_chat_capture",
                    "permission_scope": "user_provided_private_capture",
                    "raw_text": COMMENTARY_TEXT,
                    "capture_id": "commentary-review",
                    "language": "zh",
                }
            ],
        )
        load_trader_commentary_csv(config)
        parse_trader_commentary_claims(config)

        review = build_trader_commentary_parse_review(config)
        self.assertIn("Trader Commentary Parse Review", review)
        self.assertIn("Unmapped instruments", review)
        self.assertIn("\u5927\u76d8", review)
        self.assertIn("Unsupported tickers", review)
        self.assertIn("HOOD", review)
        self.assertIn("KORU", review)
        self.assertIn("Options proxy tickers", review)

        write_config(config)
        with redirect_stdout(io.StringIO()) as cli_output:
            self.assertEqual(
                command_trader_commentary_parse_review(Namespace(config=config.config_path)),
                0,
            )
        self.assertIn("Unsupported ticker claims", cli_output.getvalue())

    def test_validation_creates_outcomes_and_keeps_scores_shadow_only(self) -> None:
        database_path = fresh_database_path("phase10h_validation.sqlite")
        config = make_config(database_path)
        seed_assets(database_path)
        seed_prices(database_path)
        upsert_score(
            database_path,
            Score(
                ticker="TSLA",
                score_date="2026-06-01",
                opportunity_score=75,
                confidence_score=70,
                timing_score=65,
                risk_score=55,
                liquidity_score=90,
                asset_type="equity",
                score_model="fixture_score",
            ),
        )
        before_scores = list_scores(database_path, "TSLA")
        write_commentary_csv(
            config,
            [
                {
                    "capture_date": "2026-06-01",
                    "source": "vip_capture",
                    "source_author": "trader_a",
                    "platform": "wechat",
                    "permission_scope": "private_user_capture",
                    "raw_text": COMMENTARY_TEXT,
                    "capture_id": "commentary-2",
                    "language": "zh",
                }
            ],
        )
        load_trader_commentary_csv(config)
        parse_trader_commentary_claims(config)

        validation = validate_trader_commentary_claims(config)
        self.assertGreaterEqual(validation.updated_count, 2)
        self.assertGreaterEqual(validation.skipped_count, 1)
        self.assertIn("unmapped_instrument", ",".join(validation.warnings))

        outcomes = list_trader_commentary_claim_outcomes(database_path, ticker="TSLA")
        self.assertTrue(outcomes)
        self.assertIn(outcomes[0].outcome_status, {"pending", "partial", "completed"})
        all_outcomes = list_trader_commentary_claim_outcomes(database_path)
        self.assertTrue(
            any(
                outcome.outcome_status == "skipped"
                and "unmapped_instrument" in (outcome.data_warnings or "")
                for outcome in all_outcomes
            )
        )
        support_outcomes = [
            outcome for outcome in outcomes if outcome.claim_type == "technical_support_hold"
        ]
        self.assertTrue(support_outcomes)
        self.assertIn(
            support_outcomes[0].hit_status,
            {"level_held", "level_breached", "pending_level_check", "hit"},
        )
        self.assertEqual(list_scores(database_path, "TSLA"), before_scores)

        statuses = trader_commentary_statuses(database_path)
        tsla_status = [status for status in statuses if status.ticker == "TSLA"][0]
        self.assertEqual(tsla_status.claim_count, 1)
        self.assertGreaterEqual(tsla_status.validation_count, 1)

    def test_cli_report_dashboard_and_csv_include_commentary_fields(self) -> None:
        database_path = fresh_database_path("phase10h_outputs.sqlite")
        config = make_config(database_path)
        write_config(config)
        seed_assets(database_path)
        seed_prices(database_path)
        write_commentary_csv(
            config,
            [
                {
                    "capture_date": "2026-06-01",
                    "source": "vip_capture",
                    "source_author": "trader_a",
                    "platform": "wechat",
                    "permission_scope": "private_user_capture",
                    "raw_text": COMMENTARY_TEXT,
                    "capture_id": "commentary-3",
                    "language": "zh",
                }
            ],
        )
        load_trader_commentary_csv(config)

        with redirect_stdout(io.StringIO()) as parse_output:
            self.assertEqual(
                command_parse_trader_commentary_claims(
                    Namespace(config=config.config_path, commentary_id=None, ticker=None)
                ),
                0,
            )
        self.assertIn("parsed=", parse_output.getvalue())

        with redirect_stdout(io.StringIO()) as validate_output:
            self.assertEqual(
                command_validate_trader_commentary_claims(
                    Namespace(config=config.config_path, ticker=None)
                ),
                0,
            )
        self.assertIn("updated=", validate_output.getvalue())

        with redirect_stdout(io.StringIO()) as status_output:
            self.assertEqual(command_trader_commentary_status(Namespace(config=config.config_path)), 0)
        self.assertIn("Trader Commentary Status", status_output.getvalue())

        with redirect_stdout(io.StringIO()) as validation_report_output:
            self.assertEqual(
                command_trader_commentary_validation_report(Namespace(config=config.config_path)),
                0,
            )
        self.assertIn("Trader Commentary Validation Report", validation_report_output.getvalue())

        with redirect_stdout(io.StringIO()) as system_status_output:
            self.assertEqual(command_status(Namespace(config=config.config_path)), 0)
        self.assertIn("Trader commentary raw rows", system_status_output.getvalue())

        report = write_daily_report(config, run_date=date(2026, 6, 9))
        report_text = report.path.read_text(encoding="utf-8")
        self.assertIn("Trader commentary raw rows", report_text)
        self.assertIn("Trader Commentary", report_text)
        self.assertIn("trader_commentary_claim_count", REPORT_CSV_COLUMNS)
        csv_text = report.csv_path.read_text(encoding="utf-8") if report.csv_path else ""
        self.assertIn("trader_commentary_claim_count", csv_text)

        dashboard = build_dashboard(config)
        html = dashboard.path.read_text(encoding="utf-8")
        self.assertIn("Trader Commentary Claims", html)
        self.assertIn("trader_commentary_status", html)


if __name__ == "__main__":
    unittest.main()
