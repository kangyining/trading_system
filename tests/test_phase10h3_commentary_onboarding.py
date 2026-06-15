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
TEST_TMP_ROOT = PROJECT_ROOT / ".tmp_tests" / "phase10h3"
sys.path.insert(0, str(SRC_PATH))

from target_opportunity_monitor.cli import (
    command_apply_commentary_onboarding,
    command_commentary_onboarding_plan,
    command_commentary_onboarding_status,
    command_export_commentary_onboarding_template,
    command_load_commentary_instrument_aliases,
    command_load_commentary_label_dispositions,
    command_status,
)
from target_opportunity_monitor.commentary_onboarding import (
    COMMENTARY_ALIAS_HEADER,
    COMMENTARY_LABEL_DISPOSITION_HEADER,
    COMMENTARY_ONBOARDING_HEADER,
    build_commentary_onboarding_plan,
    ensure_commentary_alias_csv_header,
    ensure_commentary_label_disposition_csv_header,
    export_commentary_onboarding_template,
    load_commentary_instrument_aliases,
    load_commentary_label_dispositions,
)
from target_opportunity_monitor.config import AppConfig, load_config
from target_opportunity_monitor.dashboard import build_dashboard
from target_opportunity_monitor.db import REQUIRED_TABLES, initialize_database
from target_opportunity_monitor.readiness import verify_universe
from target_opportunity_monitor.reporting import REPORT_CSV_COLUMNS, write_daily_report
from target_opportunity_monitor.scoring import compute_scores
from target_opportunity_monitor.storage import (
    Asset,
    Price,
    TraderCommentaryClaim,
    count_reference_assets,
    count_rows_by_table,
    count_scoreable_assets,
    latest_asset,
    list_assets,
    list_trader_commentary_claim_outcomes,
    upsert_asset,
    upsert_prices,
    upsert_trader_commentary_claim,
)
from target_opportunity_monitor.trader_commentary import (
    build_trader_commentary_parse_review,
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
        config_path=TEST_TMP_ROOT / f"{database_path.stem}.toml",
        database_path=database_path,
        reports_dir=TEST_TMP_ROOT / "reports",
        watchlist_path=TEST_TMP_ROOT / "configs" / "watchlist.csv",
        market_data_dir=TEST_TMP_ROOT / "market_data",
        manual_prices_dir=TEST_TMP_ROOT / "market_data" / "manual",
        market_data_primary_source="stooq",
        market_data_secondary_source="yahoo_chart",
        market_data_mode="csv",
        market_data_lookback_days=800,
        market_data_stale_after_days=7,
        market_data_minimum_history_days=252,
        universe_mode="manual_watchlist",
        run_mode="daily_scoring",
        report_title="Target Opportunity Monitor Daily Report",
        trader_commentary_path=TEST_TMP_ROOT / "signals" / "manual" / "commentary.csv",
        trader_commentary_aliases_path=TEST_TMP_ROOT
        / "signals"
        / "manual"
        / "trader_commentary_instrument_aliases.csv",
        trader_commentary_label_dispositions_path=TEST_TMP_ROOT
        / "signals"
        / "manual"
        / "trader_commentary_label_dispositions.csv",
        trader_commentary_exports_dir=TEST_TMP_ROOT
        / "signals"
        / "source_exports"
        / "trader_commentary",
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
                f'trader_commentary_aliases = "{config.trader_commentary_aliases_path.as_posix()}"',
                f'trader_commentary_label_dispositions = "{config.trader_commentary_label_dispositions_path.as_posix()}"',
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


def seed_prices(database_path: Path, ticker: str, start_price: float = 100.0) -> None:
    start = date(2026, 6, 1)
    prices = [
        make_price(ticker, (start + timedelta(days=index)).isoformat(), start_price + index)
        for index in range(8)
    ]
    upsert_prices(database_path, prices)


def seed_commentary_claims(database_path: Path) -> None:
    upsert_trader_commentary_claim(
        database_path,
        TraderCommentaryClaim(
            claim_key="commentary-tsla-support",
            claim_date="2026-06-01",
            claim_type="technical_support_hold",
            ticker="TSLA",
            direction="positive",
            level_low=384,
            level_high=386,
            source="fixture",
        ),
    )
    upsert_trader_commentary_claim(
        database_path,
        TraderCommentaryClaim(
            claim_key="commentary-hood-target",
            claim_date="2026-06-01",
            claim_type="ticker_price_target",
            ticker="HOOD",
            direction="positive",
            target_price=100,
            source="fixture",
        ),
    )
    upsert_trader_commentary_claim(
        database_path,
        TraderCommentaryClaim(
            claim_key="commentary-koru-put",
            claim_date="2026-06-01",
            claim_type="options_income_idea",
            ticker="KORU",
            strike_price=600,
            premium=100,
            source="fixture",
            parser_warnings="options_proxy_only",
        ),
    )
    upsert_trader_commentary_claim(
        database_path,
        TraderCommentaryClaim(
            claim_key="commentary-market-resistance",
            claim_date="2026-06-01",
            claim_type="market_resistance_breakout",
            instrument_label="\u5927\u76d8",
            direction="positive",
            level_low=7440,
            level_high=7460,
            source="fixture",
            parser_warnings="unmapped_instrument",
        ),
    )


class Phase10H3CommentaryOnboardingTests(unittest.TestCase):
    def tearDown(self) -> None:
        if TEST_TMP_ROOT.exists():
            shutil.rmtree(TEST_TMP_ROOT)

    def test_config_schema_alias_header_and_default_asset_role(self) -> None:
        config = load_config(PROJECT_ROOT / "configs" / "default.toml")
        self.assertEqual(
            config.trader_commentary_aliases_path,
            PROJECT_ROOT
            / "data"
            / "signals"
            / "manual"
            / "trader_commentary_instrument_aliases.csv",
        )
        self.assertEqual(
            config.trader_commentary_label_dispositions_path,
            PROJECT_ROOT
            / "data"
            / "signals"
            / "manual"
            / "trader_commentary_label_dispositions.csv",
        )

        database_path = fresh_database_path("schema.sqlite")
        status = initialize_database(database_path)
        self.assertIn("trader_commentary_instrument_aliases", status.existing_tables)
        self.assertEqual(status.existing_required_table_count, len(REQUIRED_TABLES))

        upsert_asset(database_path, Asset(ticker="aapl", asset_type="equity"))
        asset = latest_asset(database_path, "AAPL")
        self.assertIsNotNone(asset)
        self.assertEqual(asset.asset_role, "scoreable")
        self.assertEqual(count_scoreable_assets(database_path), 1)

        alias_path = TEST_TMP_ROOT / "aliases.csv"
        ensure_commentary_alias_csv_header(alias_path)
        ensure_commentary_alias_csv_header(alias_path)
        self.assertEqual(alias_path.read_text(encoding="utf-8").strip(), ",".join(COMMENTARY_ALIAS_HEADER))

        disposition_path = TEST_TMP_ROOT / "label_dispositions.csv"
        ensure_commentary_label_disposition_csv_header(disposition_path)
        ensure_commentary_label_disposition_csv_header(disposition_path)
        self.assertEqual(
            disposition_path.read_text(encoding="utf-8").strip(),
            ",".join(COMMENTARY_LABEL_DISPOSITION_HEADER),
        )

    def test_onboarding_plan_identifies_unsupported_and_unmapped_claims(self) -> None:
        database_path = fresh_database_path("plan.sqlite")
        config = make_config(database_path)
        initialize_database(database_path)
        upsert_asset(database_path, Asset(ticker="AAPL", asset_type="equity"))
        seed_commentary_claims(database_path)

        plan = build_commentary_onboarding_plan(config)
        candidates = {candidate.ticker or candidate.instrument_label: candidate for candidate in plan.candidates}

        self.assertEqual(candidates["TSLA"].status, "onboardable")
        self.assertEqual(candidates["HOOD"].status, "onboardable")
        self.assertEqual(candidates["KORU"].recommended_asset_type, "etf")
        self.assertEqual(candidates["\u5927\u76d8"].status, "unmapped")
        self.assertEqual(plan.onboardable_count, 3)
        self.assertEqual(plan.unmapped_count, 1)

        review = build_trader_commentary_parse_review(config)
        self.assertIn("Unsupported but onboardable ticker claims", review)
        self.assertIn("\u5927\u76d8", review)

    def test_reference_assets_validate_commentary_without_scoreable_readiness(self) -> None:
        database_path = fresh_database_path("reference.sqlite")
        config = make_config(database_path)
        initialize_database(database_path)
        upsert_asset(database_path, Asset(ticker="AAPL", asset_type="equity"))
        seed_commentary_claims(database_path)
        write_config(config)

        template = export_commentary_onboarding_template(config)
        with redirect_stdout(io.StringIO()) as dry_run_output:
            self.assertEqual(
                command_apply_commentary_onboarding(
                    Namespace(config=config.config_path, file=template.path, confirm=False)
                ),
                0,
            )
        self.assertIn("dry run", dry_run_output.getvalue())

        rows = [
            {
                "action": "add_reference",
                "ticker": "TSLA",
                "instrument_label": "",
                "canonical_ticker": "TSLA",
                "name": "Tesla",
                "asset_type": "equity",
                "asset_role": "commentary_validation",
                "exchange": "NASDAQ",
                "currency": "USD",
                "sector": "Consumer Discretionary",
                "industry": "Auto",
                "country": "US",
                "active": "1",
                "source": "commentary_onboarding",
                "notes": "fixture",
            }
        ]
        custom_template = TEST_TMP_ROOT / "onboard_tsla.csv"
        custom_template.parent.mkdir(parents=True, exist_ok=True)
        with custom_template.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=COMMENTARY_ONBOARDING_HEADER)
            writer.writeheader()
            writer.writerows(rows)

        with redirect_stdout(io.StringIO()) as apply_output:
            self.assertEqual(
                command_apply_commentary_onboarding(
                    Namespace(config=config.config_path, file=custom_template, confirm=True)
                ),
                0,
            )
        self.assertIn("Assets changed: 1", apply_output.getvalue())

        tsla = latest_asset(database_path, "TSLA")
        self.assertIsNotNone(tsla)
        self.assertEqual(tsla.asset_role, "commentary_validation")
        self.assertEqual(count_reference_assets(database_path), 1)
        self.assertEqual(count_rows_by_table(database_path, "asset_change_events"), 1)

        readiness_tickers = {status.ticker for status in verify_universe(config).statuses}
        self.assertEqual(readiness_tickers, {"AAPL"})
        self.assertFalse(any(result.ticker == "TSLA" for result in compute_scores(config).results))

        seed_prices(database_path, "TSLA", start_price=390)
        validation = validate_trader_commentary_claims(config, ticker="TSLA")
        self.assertGreaterEqual(validation.updated_count, 1)
        self.assertTrue(list_trader_commentary_claim_outcomes(database_path, ticker="TSLA"))

    def test_alias_mapping_validates_unmapped_label_without_default_mapping(self) -> None:
        database_path = fresh_database_path("aliases.sqlite")
        config = make_config(database_path)
        initialize_database(database_path)
        seed_commentary_claims(database_path)
        upsert_asset(
            database_path,
            Asset(ticker="SPY", asset_type="etf", asset_role="commentary_validation"),
        )
        seed_prices(database_path, "SPY", start_price=7445)

        plan_before = build_commentary_onboarding_plan(config)
        self.assertEqual(plan_before.unmapped_count, 1)

        config.trader_commentary_aliases_path.parent.mkdir(parents=True, exist_ok=True)
        with config.trader_commentary_aliases_path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=COMMENTARY_ALIAS_HEADER)
            writer.writeheader()
            writer.writerow(
                {
                    "instrument_label": "\u5927\u76d8",
                    "canonical_ticker": "SPY",
                    "asset_type": "etf",
                    "asset_role": "commentary_validation",
                    "source": "unit_test",
                    "notes": "explicit alias",
                }
            )
        result = load_commentary_instrument_aliases(config)
        self.assertEqual(result.loaded_count, 1)

        validation = validate_trader_commentary_claims(config)
        self.assertIn("SPY:alias_mapped_instrument", validation.warnings)
        outcomes = list_trader_commentary_claim_outcomes(database_path, ticker="SPY")
        self.assertTrue(outcomes)
        self.assertIn("alias_mapped_instrument", outcomes[0].data_warnings or "")

        plan_after = build_commentary_onboarding_plan(config)
        self.assertEqual(plan_after.unmapped_count, 0)
        self.assertEqual(plan_after.alias_count, 1)

    def test_label_disposition_marks_ambiguous_label_without_alias_mapping(self) -> None:
        database_path = fresh_database_path("dispositions.sqlite")
        config = make_config(database_path)
        initialize_database(database_path)
        seed_commentary_claims(database_path)

        plan_before = build_commentary_onboarding_plan(config)
        self.assertEqual(plan_before.unmapped_count, 1)

        config.trader_commentary_label_dispositions_path.parent.mkdir(
            parents=True, exist_ok=True
        )
        with config.trader_commentary_label_dispositions_path.open(
            "w", encoding="utf-8", newline=""
        ) as handle:
            writer = csv.DictWriter(handle, fieldnames=COMMENTARY_LABEL_DISPOSITION_HEADER)
            writer.writeheader()
            writer.writerow(
                {
                    "instrument_label": "\u5927\u76d8",
                    "disposition": "intentionally_unresolved_ambiguous",
                    "source": "unit_test_review",
                    "notes": "ambiguous market label; no canonical ticker chosen",
                    "as_of_date": "2026-06-15",
                    "effective_date": "2026-06-15",
                }
            )

        result = load_commentary_label_dispositions(config)
        self.assertEqual(result.loaded_count, 1)
        self.assertEqual(result.invalid_count, 0)

        validation = validate_trader_commentary_claims(config)
        self.assertFalse(list_trader_commentary_claim_outcomes(database_path, ticker="SPY"))
        self.assertNotIn("SPY:alias_mapped_instrument", validation.warnings)

        plan_after = build_commentary_onboarding_plan(config)
        candidates = {
            candidate.ticker or candidate.instrument_label: candidate
            for candidate in plan_after.candidates
        }
        self.assertEqual(plan_after.unmapped_count, 0)
        self.assertEqual(plan_after.intentionally_unresolved_count, 1)
        self.assertEqual(plan_after.label_disposition_count, 1)
        self.assertEqual(
            candidates["\u5927\u76d8"].status,
            "intentionally_unresolved_ambiguous",
        )
        self.assertIsNone(candidates["\u5927\u76d8"].ticker)

        review = build_trader_commentary_parse_review(config)
        self.assertIn("Unmapped instrument claims: 0", review)
        self.assertIn("Intentionally unresolved instrument claims: 1", review)
        self.assertIn("\u5927\u76d8", review)

    def test_invalid_label_dispositions_are_rejected_with_warnings(self) -> None:
        database_path = fresh_database_path("invalid_dispositions.sqlite")
        config = make_config(database_path)
        initialize_database(database_path)
        config.trader_commentary_label_dispositions_path.parent.mkdir(
            parents=True, exist_ok=True
        )
        with config.trader_commentary_label_dispositions_path.open(
            "w", encoding="utf-8", newline=""
        ) as handle:
            writer = csv.DictWriter(handle, fieldnames=COMMENTARY_LABEL_DISPOSITION_HEADER)
            writer.writeheader()
            writer.writerow(
                {
                    "instrument_label": "\u5927\u76d8",
                    "disposition": "map_to_spy",
                    "source": "unit_test_review",
                }
            )
            writer.writerow(
                {
                    "instrument_label": "",
                    "disposition": "intentionally_unresolved_ambiguous",
                    "source": "unit_test_review",
                }
            )

        result = load_commentary_label_dispositions(config)
        self.assertEqual(result.loaded_count, 0)
        self.assertEqual(result.invalid_count, 2)
        self.assertTrue(any("invalid_label_disposition" in item for item in result.warnings))

    def test_cli_reports_dashboard_and_status_include_onboarding_fields(self) -> None:
        database_path = fresh_database_path("outputs.sqlite")
        config = make_config(database_path)
        write_config(config)
        initialize_database(database_path)
        upsert_asset(database_path, Asset(ticker="AAPL", asset_type="equity"))
        seed_commentary_claims(database_path)

        with redirect_stdout(io.StringIO()) as load_alias_output:
            self.assertEqual(command_load_commentary_instrument_aliases(Namespace(config=config.config_path, file=None)), 0)
        self.assertIn("Commentary instrument aliases loaded", load_alias_output.getvalue())

        with redirect_stdout(io.StringIO()) as load_disposition_output:
            self.assertEqual(
                command_load_commentary_label_dispositions(
                    Namespace(config=config.config_path, file=None)
                ),
                0,
            )
        self.assertIn(
            "Commentary label dispositions loaded",
            load_disposition_output.getvalue(),
        )

        with redirect_stdout(io.StringIO()) as plan_output:
            self.assertEqual(command_commentary_onboarding_plan(Namespace(config=config.config_path)), 0)
        self.assertIn("Commentary Onboarding Plan", plan_output.getvalue())
        self.assertIn("TSLA", plan_output.getvalue())

        with redirect_stdout(io.StringIO()) as status_output:
            self.assertEqual(command_commentary_onboarding_status(Namespace(config=config.config_path)), 0)
        self.assertIn("Commentary Onboarding Status", status_output.getvalue())

        with redirect_stdout(io.StringIO()) as export_output:
            self.assertEqual(command_export_commentary_onboarding_template(Namespace(config=config.config_path, output=None)), 0)
        self.assertIn("Commentary onboarding template exported", export_output.getvalue())

        with redirect_stdout(io.StringIO()) as system_status_output:
            self.assertEqual(command_status(Namespace(config=config.config_path)), 0)
        system_status = system_status_output.getvalue()
        self.assertIn("Trader commentary alias file", system_status)
        self.assertIn("Trader commentary onboarding candidates", system_status)
        self.assertIn("Trader commentary label dispositions", system_status)
        self.assertIn("Scoreable assets", system_status)

        report = write_daily_report(config, run_date=date(2026, 6, 9))
        report_text = report.path.read_text(encoding="utf-8")
        self.assertIn("Trader commentary onboarding candidates", report_text)
        self.assertIn("Trader commentary label dispositions", report_text)
        self.assertIn("trader_commentary_onboarding_candidate_count", REPORT_CSV_COLUMNS)
        self.assertIn("trader_commentary_label_disposition_count", REPORT_CSV_COLUMNS)
        csv_text = report.csv_path.read_text(encoding="utf-8") if report.csv_path else ""
        self.assertIn("trader_commentary_onboarding_candidate_count", csv_text)
        self.assertIn("trader_commentary_label_disposition_count", csv_text)

        dashboard = build_dashboard(config)
        html = dashboard.path.read_text(encoding="utf-8")
        self.assertIn("trader_commentary_onboarding_candidate_count", html)
        self.assertIn("Scoreable Assets", html)

        assets = {asset.ticker: asset for asset in list_assets(database_path)}
        self.assertEqual(assets["AAPL"].asset_role, "scoreable")


if __name__ == "__main__":
    unittest.main()
