from __future__ import annotations

import csv
from pathlib import Path
import sys
import unittest
from uuid import uuid4


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
TEST_TMP_ROOT = PROJECT_ROOT / ".tmp_tests" / "phase13e"
sys.path.insert(0, str(SRC_PATH))

from target_opportunity_monitor.config import AppConfig
from target_opportunity_monitor.db import initialize_database
from target_opportunity_monitor.foreign_equity_sources import (
    FOREIGN_EQUITY_ANALYST_TARGET_HEADERS,
    FOREIGN_EQUITY_ESTIMATE_HEADERS,
    FOREIGN_EQUITY_FUNDAMENTAL_HEADERS,
    apply_foreign_equity_sources,
    export_foreign_equity_source_templates,
    latest_foreign_equity_analyst_targets,
    validate_foreign_equity_sources,
)
from target_opportunity_monitor.storage import (
    Asset,
    PriceFeature,
    latest_estimate,
    list_fundamentals,
    list_targets,
    upsert_asset,
    upsert_price_feature,
)
from target_opportunity_monitor.valuation import compute_targets


def _config(name: str) -> AppConfig:
    TEST_TMP_ROOT.mkdir(parents=True, exist_ok=True)
    root = TEST_TMP_ROOT / f"{name}_{uuid4().hex}"
    root.mkdir(parents=True, exist_ok=True)
    config = AppConfig(
        project_root=root,
        config_path=root / "config.toml",
        database_path=root / "tom.sqlite",
        reports_dir=root / "reports",
        watchlist_path=root / "configs" / "watchlist.csv",
        market_data_dir=root / "data" / "market_data",
        manual_prices_dir=root / "data" / "market_data" / "manual",
        market_data_primary_source="manual",
        market_data_secondary_source="manual",
        market_data_mode="manual",
        market_data_lookback_days=30,
        market_data_stale_after_days=7,
        market_data_minimum_history_days=5,
        universe_mode="manual_watchlist",
        run_mode="test",
        report_title="Test",
    )
    initialize_database(config.database_path)
    return config


def _write_foreign_identity(config: AppConfig, ticker: str = "SIVE") -> None:
    path = config.foreign_equity_identity_path
    if not path.is_absolute():
        path = config.project_root / path
    path.parent.mkdir(parents=True, exist_ok=True)
    headers = (
        "ticker",
        "name",
        "exchange",
        "currency",
        "country",
        "sector",
        "industry",
        "isin",
        "source",
        "source_url",
        "as_of_date",
        "effective_date",
        "notes",
    )
    row = {
        "ticker": ticker,
        "name": "Sivers Semiconductors AB",
        "exchange": "Nasdaq Stockholm",
        "currency": "SEK",
        "country": "Sweden",
        "sector": "Information Technology",
        "industry": "Semiconductors",
        "isin": "SE0003917798",
        "source": "issuer_investor_page",
        "source_url": "https://www.sivers-semiconductors.com/investors/shares-2/",
        "as_of_date": "2026-06-15",
        "effective_date": "2026-06-15",
        "notes": "Source-backed identity.",
    }
    with path.open("w", encoding="utf-8", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=headers)
        writer.writeheader()
        writer.writerow(row)


def _write_source_rows(
    config: AppConfig,
    *,
    fundamentals: list[dict[str, str]],
    estimates: list[dict[str, str]],
    analyst_targets: list[dict[str, str]] | None = None,
) -> None:
    fundamentals_path = config.foreign_equity_fundamentals_source_path
    estimates_path = config.foreign_equity_estimates_source_path
    analyst_targets_path = config.foreign_equity_analyst_targets_source_path
    if not fundamentals_path.is_absolute():
        fundamentals_path = config.project_root / fundamentals_path
    if not estimates_path.is_absolute():
        estimates_path = config.project_root / estimates_path
    if not analyst_targets_path.is_absolute():
        analyst_targets_path = config.project_root / analyst_targets_path
    fundamentals_path.parent.mkdir(parents=True, exist_ok=True)
    estimates_path.parent.mkdir(parents=True, exist_ok=True)
    analyst_targets_path.parent.mkdir(parents=True, exist_ok=True)
    with fundamentals_path.open("w", encoding="utf-8", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=FOREIGN_EQUITY_FUNDAMENTAL_HEADERS)
        writer.writeheader()
        for row in fundamentals:
            writer.writerow({field: row.get(field, "") for field in FOREIGN_EQUITY_FUNDAMENTAL_HEADERS})
    with estimates_path.open("w", encoding="utf-8", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=FOREIGN_EQUITY_ESTIMATE_HEADERS)
        writer.writeheader()
        for row in estimates:
            writer.writerow({field: row.get(field, "") for field in FOREIGN_EQUITY_ESTIMATE_HEADERS})
    with analyst_targets_path.open("w", encoding="utf-8", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=FOREIGN_EQUITY_ANALYST_TARGET_HEADERS)
        writer.writeheader()
        for row in analyst_targets or []:
            writer.writerow({field: row.get(field, "") for field in FOREIGN_EQUITY_ANALYST_TARGET_HEADERS})


def _seed_sive_asset_and_price(config: AppConfig, price: float = 86.35) -> None:
    upsert_asset(
        config.database_path,
        Asset(
            ticker="SIVE",
            name="Sivers Semiconductors AB",
            asset_type="equity",
            asset_role="scoreable",
            exchange="Nasdaq Stockholm",
            currency="SEK",
            sector="Information Technology",
            industry="Semiconductors",
            country="Sweden",
            source="research_foreign_equity_identity",
            as_of_date="2026-06-15",
            effective_date="2026-06-15",
        ),
    )
    upsert_price_feature(
        config.database_path,
        PriceFeature(
            ticker="SIVE",
            feature_date="2026-06-15",
            current_price=price,
            return_1d=None,
            return_1m=None,
            return_3m=None,
            return_6m=None,
            return_12m=None,
            realized_volatility_20d=None,
            realized_volatility_60d=None,
            average_dollar_volume_20d=None,
            latest_price_date="2026-06-15",
            source="test_price",
            as_of_date="2026-06-15",
            effective_date="2026-06-15",
        ),
    )


class ForeignEquitySourceTests(unittest.TestCase):
    def test_valid_source_rows_import_only_after_confirmation(self) -> None:
        config = _config("valid_import")
        _write_foreign_identity(config)
        common = {
            "ticker": "SIVE",
            "source": "issuer_annual_report",
            "source_url": "https://example.com/sive-annual-report.pdf",
            "as_of_date": "2026-06-15",
            "effective_date": "2025-12-31",
            "notes": "Source-backed test row.",
        }
        _write_source_rows(
            config,
            fundamentals=[
                {
                    **common,
                    "fiscal_period_end": "2025-12-31",
                    "fiscal_period": "FY",
                    "report_type": "annual",
                    "currency": "SEK",
                    "revenue": "1000000",
                    "net_income": "100000",
                    "diluted_eps": "0.25",
                }
            ],
            estimates=[
                {
                    **common,
                    "estimate_date": "2026-06-15",
                    "fiscal_period_end": "2026-12-31",
                    "metric": "eps",
                    "fiscal_period": "NTM",
                    "currency": "SEK",
                    "consensus_mean": "0.31",
                    "analyst_count": "3",
                }
            ],
        )

        validation = validate_foreign_equity_sources(config)
        dry_run = apply_foreign_equity_sources(config, confirm=False)
        rows_after_dry_run = len(list_fundamentals(config.database_path, "SIVE"))
        confirmed = apply_foreign_equity_sources(config, confirm=True)

        self.assertTrue(validation.apply_ready)
        self.assertEqual(validation.valid_fundamental_rows, 1)
        self.assertEqual(validation.valid_estimate_rows, 1)
        self.assertFalse(dry_run.applied)
        self.assertEqual(rows_after_dry_run, 0)
        self.assertEqual(len(list_fundamentals(config.database_path, "SIVE")), 1)
        self.assertTrue(confirmed.applied)
        self.assertEqual(confirmed.imported_fundamental_rows, 1)
        self.assertEqual(confirmed.imported_estimate_rows, 1)
        self.assertEqual(list_fundamentals(config.database_path, "SIVE")[0].source, "issuer_annual_report")
        self.assertEqual(latest_estimate(config.database_path, "SIVE", "eps").consensus_mean, 0.31)

    def test_invalid_rows_block_apply(self) -> None:
        config = _config("invalid_rows")
        _write_foreign_identity(config)
        _write_source_rows(
            config,
            fundamentals=[
                {
                    "ticker": "SIVE",
                    "fiscal_period_end": "2025-12-31",
                    "fiscal_period": "FY",
                    "report_type": "annual",
                    "source": "issuer_annual_report",
                    "as_of_date": "2026-06-15",
                    "effective_date": "2025-12-31",
                    "notes": "Missing source URL.",
                    "revenue": "100",
                },
                {
                    "ticker": "NOPE",
                    "fiscal_period_end": "2025-12-31",
                    "fiscal_period": "FY",
                    "report_type": "annual",
                    "source": "issuer_annual_report",
                    "source_url": "https://example.com/nope.pdf",
                    "as_of_date": "2026-06-15",
                    "effective_date": "2025-12-31",
                    "notes": "Unsupported ticker.",
                    "revenue": "100",
                },
            ],
            estimates=[
                {
                    "ticker": "SIVE",
                    "estimate_date": "2026-06-15",
                    "fiscal_period_end": "2026-12-31",
                    "metric": "eps",
                    "source": "issuer_annual_report",
                    "source_url": "https://example.com/sive.pdf",
                    "as_of_date": "2026-06-15",
                    "effective_date": "2026-06-15",
                    "notes": "Malformed numeric.",
                    "consensus_mean": "bad",
                }
            ],
        )

        validation = validate_foreign_equity_sources(config)
        result = apply_foreign_equity_sources(config, confirm=True)

        self.assertFalse(validation.apply_ready)
        self.assertEqual(validation.invalid_rows, 3)
        self.assertEqual(validation.blocked_reason, "invalid_foreign_equity_source_rows")
        self.assertFalse(result.applied)
        self.assertEqual(result.blocked_reason, "invalid_foreign_equity_source_rows")
        self.assertEqual(len(list_fundamentals(config.database_path, "SIVE")), 0)

    def test_template_export_creates_empty_source_files(self) -> None:
        config = _config("template_export")

        fundamentals_path, estimates_path, analyst_targets_path = (
            export_foreign_equity_source_templates(config)
        )

        self.assertEqual(fundamentals_path, "data\\research\\source_exports\\foreign_equity_fundamentals.csv")
        self.assertEqual(estimates_path, "data\\research\\source_exports\\foreign_equity_estimates.csv")
        self.assertEqual(
            analyst_targets_path,
            "data\\research\\source_exports\\foreign_equity_analyst_targets.csv",
        )
        self.assertTrue((config.project_root / fundamentals_path).exists())
        self.assertTrue((config.project_root / estimates_path).exists())
        self.assertTrue((config.project_root / analyst_targets_path).exists())

    def test_valid_analyst_target_row_is_validated_and_exposed(self) -> None:
        config = _config("valid_analyst_target")
        _write_foreign_identity(config)
        _seed_sive_asset_and_price(config)
        _write_source_rows(
            config,
            fundamentals=[],
            estimates=[],
            analyst_targets=[
                {
                    "ticker": "SIVE",
                    "target_date": "2026-06-15",
                    "currency": "SEK",
                    "target_mean": "9.8",
                    "target_low": "6.0",
                    "target_high": "19.0",
                    "analyst_count": "4",
                    "source": "yfinance_analyst_target",
                    "source_url": "https://finance.yahoo.com/quote/SIVE.ST/analysis/",
                    "as_of_date": "2026-06-15",
                    "effective_date": "2026-06-15",
                    "notes": "Source-backed provider target.",
                }
            ],
        )

        validation = validate_foreign_equity_sources(config)
        targets = latest_foreign_equity_analyst_targets(config, "SIVE")
        status = next(item for item in validation.ticker_statuses if item.ticker == "SIVE")

        self.assertEqual(validation.valid_analyst_target_rows, 1)
        self.assertEqual(validation.valid_analyst_target_tickers, ("SIVE",))
        self.assertTrue(status.analyst_target_available)
        self.assertTrue(status.projected_analyst_target_available)
        self.assertEqual(len(targets), 1)
        self.assertEqual(targets[0].target_mean, 9.8)

    def test_invalid_analyst_target_rows_block_apply(self) -> None:
        config = _config("invalid_analyst_target")
        _write_foreign_identity(config)
        _seed_sive_asset_and_price(config, price=10.0)
        _write_source_rows(
            config,
            fundamentals=[],
            estimates=[],
            analyst_targets=[
                {
                    "ticker": "SIVE",
                    "target_date": "2026-06-15",
                    "currency": "SEK",
                    "target_mean": "9.8",
                    "source": "provider_export",
                    "as_of_date": "2026-06-15",
                    "effective_date": "2026-06-15",
                    "notes": "Missing URL.",
                },
                {
                    "ticker": "SIVE",
                    "target_date": "2020-01-01",
                    "currency": "SEK",
                    "target_mean": "9.8",
                    "source": "provider_export",
                    "source_url": "https://example.com/sive-target.csv",
                    "as_of_date": "2026-06-15",
                    "effective_date": "2026-06-15",
                    "notes": "Stale target.",
                },
                {
                    "ticker": "SIVE",
                    "target_date": "2026-06-15",
                    "currency": "SEK",
                    "target_mean": "1000",
                    "source": "provider_export",
                    "source_url": "https://example.com/sive-target.csv",
                    "as_of_date": "2026-06-15",
                    "effective_date": "2026-06-15",
                    "notes": "Scale mismatch.",
                },
            ],
        )

        validation = validate_foreign_equity_sources(config)
        blockers = {
            blocker
            for diagnostic in validation.diagnostics
            for blocker in diagnostic.blockers
        }

        self.assertFalse(validation.apply_ready)
        self.assertEqual(validation.invalid_rows, 3)
        self.assertIn("missing_source_url", blockers)
        self.assertIn("stale_target_date", blockers)
        self.assertIn("analyst_target_price_scale_mismatch", blockers)

    def test_analyst_target_fallback_computes_loss_making_foreign_equity_target(self) -> None:
        config = _config("analyst_target_fallback")
        _write_foreign_identity(config)
        _seed_sive_asset_and_price(config)
        common = {
            "ticker": "SIVE",
            "source": "issuer_interim_report",
            "source_url": "https://example.com/sive-interim.pdf",
            "as_of_date": "2026-06-15",
            "effective_date": "2025-12-31",
            "notes": "Source-backed loss-making test row.",
        }
        _write_source_rows(
            config,
            fundamentals=[
                {
                    **common,
                    "fiscal_period_end": "2025-12-31",
                    "fiscal_period": "FY",
                    "report_type": "annual",
                    "currency": "SEK",
                    "revenue": "1000000",
                    "net_income": "-500000",
                    "diluted_eps": "-0.25",
                    "ebitda": "-250000",
                    "free_cash_flow": "-100000",
                    "shares_outstanding": "100000000",
                }
            ],
            estimates=[
                {
                    **common,
                    "estimate_date": "2026-06-15",
                    "fiscal_period_end": "2026-12-31",
                    "metric": "eps",
                    "fiscal_period": "NTM",
                    "currency": "SEK",
                    "consensus_mean": "-0.10",
                    "analyst_count": "4",
                }
            ],
            analyst_targets=[
                {
                    "ticker": "SIVE",
                    "target_date": "2026-06-15",
                    "currency": "SEK",
                    "target_mean": "9.8",
                    "target_low": "6.0",
                    "target_high": "19.0",
                    "analyst_count": "4",
                    "source": "yfinance_analyst_target",
                    "source_url": "https://finance.yahoo.com/quote/SIVE.ST/analysis/",
                    "as_of_date": "2026-06-15",
                    "effective_date": "2026-06-15",
                    "notes": "Source-backed provider target.",
                }
            ],
        )
        apply_foreign_equity_sources(config, confirm=True)

        result = compute_targets(config, ticker="SIVE")
        targets = list_targets(config.database_path, "SIVE")

        self.assertEqual(result.computed_count, 1)
        self.assertEqual(len(targets), 1)
        self.assertEqual(targets[0].source, "foreign_equity_analyst_target")
        self.assertEqual(targets[0].target_method, "source_backed_analyst_target")
        self.assertIn("source_backed_analyst_target_only", targets[0].data_warnings or "")
        self.assertIn("loss_making_foreign_equity_valuation", targets[0].data_warnings or "")


if __name__ == "__main__":
    unittest.main()
