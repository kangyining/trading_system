from __future__ import annotations

import csv
from pathlib import Path
import sys
import unittest
from uuid import uuid4
from unittest.mock import patch


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
TEST_TMP_ROOT = PROJECT_ROOT / ".tmp_tests" / "phase15a"
sys.path.insert(0, str(SRC_PATH))

from target_opportunity_monitor.account import (  # noqa: E402
    AccountContextFetchResult,
    account_provider_status,
    fetch_account_context,
    normalize_account_export,
    validate_account_context_backfill,
)
from target_opportunity_monitor.api_server import handle_api_request  # noqa: E402
from target_opportunity_monitor.config import AppConfig  # noqa: E402
from target_opportunity_monitor.db import initialize_database  # noqa: E402
from target_opportunity_monitor.storage import Asset, upsert_asset  # noqa: E402


def _config(tmpdir: str) -> AppConfig:
    root = Path(tmpdir)
    return AppConfig(
        project_root=root,
        config_path=root / "config.toml",
        database_path=root / "tom.sqlite",
        reports_dir=root / "reports",
        watchlist_path=root / "configs" / "watchlist.csv",
        cik_map_path=root / "configs" / "cik_map.csv",
        account_source_exports_dir=root / "data" / "account" / "source_exports",
        portfolio_positions_path=root / "data" / "portfolio" / "manual" / "positions.csv",
        portfolio_cash_path=root / "data" / "portfolio" / "manual" / "cash.csv",
        options_positions_path=root / "data" / "options" / "manual" / "options_positions.csv",
        options_chain_source_exports_dir=root / "data" / "options" / "source_exports",
        news_catalyst_source_exports_dir=root / "data" / "signals" / "source_exports" / "news_catalysts",
        scheduler_automations_dir=root / ".codex" / "automations",
        notification_outbox_dir=root / "data" / "notifications" / "outbox",
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


def _initialized_config(name: str) -> AppConfig:
    TEST_TMP_ROOT.mkdir(parents=True, exist_ok=True)
    root = TEST_TMP_ROOT / f"{name}_{uuid4().hex}"
    root.mkdir(parents=True, exist_ok=True)
    config = _config(str(root))
    initialize_database(config.database_path)
    upsert_asset(
        config.database_path,
        Asset(ticker="AAPL", name="Apple", asset_type="equity", asset_role="scoreable"),
    )
    return config


def _write_generic_export(config: AppConfig) -> Path:
    path = config.account_source_exports_dir / "raw_account_export.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    headers = (
        "record_type",
        "account",
        "ticker",
        "quantity",
        "cash_amount",
        "currency",
        "position_date",
        "cash_date",
        "market_price",
        "option_type",
        "side",
        "open_date",
        "expiration_date",
        "strike",
        "contracts",
        "premium",
        "source",
        "source_url",
    )
    rows = (
        {
            "record_type": "portfolio_position",
            "account": "test",
            "ticker": "AAPL",
            "quantity": "2",
            "currency": "USD",
            "position_date": "2026-06-13",
            "market_price": "200",
            "source": "broker_export",
            "source_url": "broker://positions",
        },
        {
            "record_type": "portfolio_cash",
            "account": "test",
            "cash_amount": "1000",
            "currency": "USD",
            "cash_date": "2026-06-13",
            "source": "broker_export",
            "source_url": "broker://cash",
        },
        {
            "record_type": "option_position",
            "account": "test",
            "ticker": "AAPL",
            "option_type": "put",
            "side": "short_put",
            "open_date": "2026-06-13",
            "expiration_date": "2026-07-17",
            "strike": "180",
            "contracts": "1",
            "premium": "2.5",
            "source": "broker_export",
            "source_url": "broker://options",
        },
    )
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=headers)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
    return path


class Phase15AAccountSyncTests(unittest.TestCase):
    def test_provider_status_reports_missing_ibapi_without_failing(self) -> None:
        config = _initialized_config("provider_status")

        with patch(
            "target_opportunity_monitor.account._import_ibapi",
            return_value=(None, None, None, "permission denied"),
        ):
            status = account_provider_status(config, check_connectivity=False)

        self.assertFalse(status.ibkr_available)
        self.assertIn("ibapi_missing", status.blockers)
        self.assertIn("ibapi_unavailable:permission denied", status.warnings)

    def test_normalize_account_export_accepts_provider_labels(self) -> None:
        config = _initialized_config("normalize")
        export_path = _write_generic_export(config)

        result = normalize_account_export(config, provider="ibkr-flex", path=export_path)
        validation = validate_account_context_backfill(config)

        self.assertEqual(result.provider, "ibkr-flex")
        self.assertEqual(result.position_rows, 1)
        self.assertEqual(result.cash_rows, 1)
        self.assertEqual(result.option_position_rows, 1)
        self.assertGreaterEqual(len(result.output_files), 3)
        self.assertEqual(validation.valid_position_rows, 1)
        self.assertEqual(validation.valid_cash_rows, 1)
        self.assertEqual(validation.valid_option_position_rows, 1)
        self.assertEqual(validation.invalid_row_count, 0)

    def test_fetch_account_context_file_normalizes_read_only_export(self) -> None:
        config = _initialized_config("fetch_file")
        export_path = _write_generic_export(config)

        result = fetch_account_context(
            config,
            source="file",
            read_only=True,
            provider="generic",
            path=export_path,
        )

        self.assertTrue(result.fetched)
        self.assertEqual(result.position_rows, 1)
        self.assertEqual(result.cash_rows, 1)
        self.assertEqual(result.option_position_rows, 1)

    def test_fetch_account_context_requires_read_only_acknowledgement(self) -> None:
        config = _initialized_config("requires_read_only")
        export_path = _write_generic_export(config)

        with self.assertRaises(ValueError):
            fetch_account_context(
                config,
                source="file",
                read_only=False,
                provider="generic",
                path=export_path,
            )

    def test_api_fetch_context_requires_confirmation(self) -> None:
        config = _initialized_config("api_confirmation")

        code, payload = handle_api_request(
            config,
            "POST",
            "/api/account/fetch-context",
            body={"source": "ibkr", "read_only": True},
        )

        self.assertEqual(code, 403)
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["error_code"], "confirmation_required")

    def test_api_fetch_context_uses_mocked_ibkr_read_only_path(self) -> None:
        config = _initialized_config("api_ibkr")
        fake_result = AccountContextFetchResult(
            source="ibkr",
            provider="ibkr",
            read_only=True,
            fetched=True,
            input_path=None,
            output_files=(config.account_source_exports_dir / "ibkr_read_only_portfolio_cash.csv",),
            position_rows=0,
            cash_rows=1,
            option_position_rows=0,
            warnings=("mocked_read_only_ibkr",),
        )

        with patch(
            "target_opportunity_monitor.api_server.fetch_account_context",
            return_value=fake_result,
        ) as fetch_mock:
            code, payload = handle_api_request(
                config,
                "POST",
                "/api/account/fetch-context",
                body={"confirm": True, "source": "ibkr", "read_only": True},
            )

        self.assertEqual(code, 200)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["data"]["result"]["cash_rows"], 1)
        fetch_mock.assert_called_once()


if __name__ == "__main__":
    unittest.main()
