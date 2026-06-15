from __future__ import annotations

import csv
import json
from datetime import datetime
from pathlib import Path
import sqlite3
import sys
import unittest
from uuid import uuid4
from unittest.mock import patch


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
TEST_TMP_ROOT = PROJECT_ROOT / ".tmp_tests" / "phase13d"
sys.path.insert(0, str(SRC_PATH))

from target_opportunity_monitor.config import AppConfig
from target_opportunity_monitor.db import initialize_database
from target_opportunity_monitor.research_preparation import (
    DirexionEtfEvidence,
    RESEARCH_PREPARATION_AUTO_STEP_NAME,
    _index_top_holdings,
    research_preparation_status,
    run_research_preparation,
)
from target_opportunity_monitor.storage import (
    Asset,
    EtfFeature,
    MissingTickerCandidate,
    OptionChainSnapshot,
    PriceFeature,
    RangeSnapshot,
    ResearchRecommendationCandidate,
    Score,
    Target,
    insert_pipeline_step_result,
    latest_asset,
    list_research_recommendation_candidates,
    start_pipeline_run,
    upsert_missing_ticker_candidate,
    upsert_asset,
    upsert_etf_feature,
    upsert_option_chain_snapshot,
    upsert_price_feature,
    upsert_range_snapshot,
    upsert_research_recommendation_candidate,
    upsert_score,
    upsert_target,
)


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
        etf_navs_path=root / "data" / "etf" / "manual" / "etf_navs.csv",
        etf_holdings_path=root / "data" / "etf" / "manual" / "etf_holdings.csv",
        universe_mode="manual_watchlist",
        run_mode="test",
        report_title="Test",
    )
    initialize_database(config.database_path)
    _write_empty_sec_cache(config)
    return config


def _write_empty_sec_cache(config: AppConfig) -> None:
    cache_path = config.project_root / config.fundamental_cache_dir / "sec_company_tickers_exchange.json"
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(json.dumps({"fields": ["ticker", "cik", "name", "exchange"], "data": []}), encoding="utf-8")


def _write_foreign_equity_identity_rows(
    config: AppConfig,
    rows: list[dict[str, str]],
) -> None:
    path = config.foreign_equity_identity_path
    if not path.is_absolute():
        path = config.project_root / path
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = (
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
    with path.open("w", encoding="utf-8", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def _seed_recommendation(
    config: AppConfig,
    ticker: str,
    *,
    key: str | None = None,
    warnings: str | None = None,
    blockers: str | None = None,
    status: str = "pending",
) -> None:
    upsert_research_recommendation_candidate(
        config.database_path,
        ResearchRecommendationCandidate(
            recommendation_key=key or f"prep:{ticker}",
            ticker=ticker,
            recommendation_date="2026-06-14",
            source="codex_manual",
            status=status,
            topic="Preparation test",
            rationale=f"Prepare {ticker}.",
            research_priority_score=75.0,
            confidence=70.0,
            source_count=1,
            evidence_count=1,
            source_mix="codex_manual",
            warning_codes=warnings,
            promotion_blockers=blockers,
        ),
    )


def _seed_ready_etf(config: AppConfig, ticker: str = "XLV", *, role: str = "commentary_validation") -> None:
    upsert_asset(
        config.database_path,
        Asset(
            ticker=ticker,
            name=f"{ticker} ETF",
            asset_type="etf",
            asset_role=role,
            active_flag=1,
        ),
    )
    upsert_price_feature(
        config.database_path,
        PriceFeature(
            ticker=ticker,
            feature_date="2026-06-14",
            current_price=100.0,
            return_1d=0.01,
            return_1m=0.02,
            return_3m=0.03,
            return_6m=0.04,
            return_12m=0.05,
            realized_volatility_20d=0.2,
            realized_volatility_60d=0.22,
            average_dollar_volume_20d=10000000.0,
            latest_price_date="2026-06-14",
        ),
    )
    upsert_etf_feature(
        config.database_path,
        EtfFeature(
            ticker=ticker,
            feature_date="2026-06-14",
            nav_per_share=101.0,
            market_price=100.0,
            premium_discount=-0.01,
            premium_discount_average_60d=-0.002,
            premium_discount_volatility_60d=0.003,
            premium_discount_zscore=-1.0,
            holdings_count=50,
            top_10_weight=0.35,
            largest_holding_weight=0.08,
            equity_weight=0.98,
            cash_weight=0.02,
            latest_nav_date="2026-06-14",
            latest_holdings_date="2026-06-14",
        ),
    )
    upsert_target(
        config.database_path,
        Target(
            ticker=ticker,
            target_date="2026-06-14",
            base_target=112.0,
            target_low=98.0,
            target_high=120.0,
            valuation_gap=0.12,
            target_method="etf_nav",
            uncertainty_band=0.1,
            valuation_score=70.0,
        ),
    )
    upsert_score(
        config.database_path,
        Score(
            ticker=ticker,
            score_date="2026-06-14",
            opportunity_score=72.0,
            confidence_score=75.0,
            asset_type="etf",
            score_model="test",
        ),
    )
    upsert_range_snapshot(
        config.database_path,
        RangeSnapshot(
            ticker=ticker,
            snapshot_timestamp="2026-06-14T12:00:00+00:00",
            asset_type="etf",
            current_price=100.0,
            base_target=112.0,
            opportunity_score=72.0,
            range_state="starter_buy",
        ),
    )
    upsert_option_chain_snapshot(
        config.database_path,
        OptionChainSnapshot(
            ticker=ticker,
            snapshot_timestamp="2026-06-14T12:00:00+00:00",
            expiration_date="2026-07-17",
            option_type="call",
            strike=105.0,
            bid=2.4,
            ask=2.6,
            mark=2.5,
            source="test_chain",
        ),
    )


def _seed_etf_shell(config: AppConfig, ticker: str = "SOXL", *, with_option_chain: bool = True) -> None:
    upsert_asset(
        config.database_path,
        Asset(
            ticker=ticker,
            name=f"{ticker} ETF",
            asset_type="etf",
            asset_role="commentary_validation",
            active_flag=1,
        ),
    )
    upsert_price_feature(
        config.database_path,
        PriceFeature(
            ticker=ticker,
            feature_date="2026-06-14",
            current_price=100.0,
            return_1d=0.01,
            return_1m=0.02,
            return_3m=0.03,
            return_6m=0.04,
            return_12m=0.05,
            realized_volatility_20d=0.2,
            realized_volatility_60d=0.22,
            average_dollar_volume_20d=10000000.0,
            latest_price_date="2026-06-14",
        ),
    )
    if with_option_chain:
        upsert_option_chain_snapshot(
            config.database_path,
            OptionChainSnapshot(
                ticker=ticker,
                snapshot_timestamp="2026-06-14T12:00:00+00:00",
                expiration_date="2026-07-17",
                option_type="call",
                strike=105.0,
                bid=2.4,
                ask=2.6,
                mark=2.5,
                source="test_chain",
            ),
        )


def _direxion_evidence(ticker: str = "SOXL") -> DirexionEtfEvidence:
    return DirexionEtfEvidence(
        ticker=ticker,
        source_url=f"https://example.com/{ticker.lower()}",
        nav_date="2026-06-14",
        nav_per_share=101.0,
        market_price=100.0,
        holdings_date="2026-06-14",
        holdings=tuple(
            {
                "holding_name": f"Holding {index}",
                "holding_asset_type": "equity",
                "weight": 0.1,
                "source": "direxion_official_holdings",
            }
            for index in range(1, 11)
        ),
    )


class ResearchPreparationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.profile_patcher = patch(
            "target_opportunity_monitor.research_tickers._fetch_fmp_profile",
            return_value=(None, ("missing_profile_api_key",)),
        )
        self.profile_patcher.start()

    def tearDown(self) -> None:
        self.profile_patcher.stop()

    def test_direxion_index_holdings_parser_handles_split_percent_tokens(self) -> None:
        lines = [
            "Index Top Ten Holdings",
            "% of Total",
            "Nvidia",
            "8.41",
            "%",
            "Broadcom Limited",
            "8.28",
            "%",
            ".css-1e4sizb{margin-top:0.5rem;}",
            "View all Index Holdings",
        ]

        holdings = _index_top_holdings(lines)

        self.assertEqual(len(holdings), 2)
        self.assertEqual(holdings[0]["holding_name"], "Nvidia")
        self.assertAlmostEqual(float(holdings[0]["weight"]), 0.0841)
        self.assertEqual(holdings[1]["holding_name"], "Broadcom Limited")
        self.assertAlmostEqual(float(holdings[1]["weight"]), 0.0828)

    def test_preparation_status_classifies_mixed_pending_queue(self) -> None:
        config = _config("mixed_status")
        _seed_ready_etf(config, "XLV", role="scoreable")
        _seed_recommendation(config, "XLV", warnings="already_scoreable")
        upsert_asset(
            config.database_path,
            Asset(ticker="SOXL", name="SOXL ETF", asset_type="etf", asset_role="commentary_validation"),
        )
        _seed_recommendation(
            config,
            "SOXL",
            blockers="etf_research_ticker_requires_etf_path",
        )
        _seed_recommendation(
            config,
            "SIVE",
            warnings="missing_cik_metadata",
            blockers="missing_cik_metadata",
        )

        status = research_preparation_status(config)
        items = {item.ticker: item for item in status.items}

        self.assertEqual(items["XLV"].preparation_state, "prepared_already_scoreable")
        self.assertTrue(items["XLV"].can_ignore_context)
        self.assertEqual(items["SOXL"].preparation_state, "source_data_required")
        self.assertIn("missing_etf_feature", items["SOXL"].blockers)
        self.assertTrue(items["SOXL"].can_discover_sources)
        self.assertTrue(items["SOXL"].can_stage_sources)
        self.assertEqual(items["SOXL"].automation_stage, "source_discovery_available")
        self.assertIn(items["SIVE"].preparation_state, {"metadata_required", "identity_required"})
        self.assertEqual(items["SIVE"].cannot_automate_reason, "source_backed_identity_required")
        self.assertIsNotNone(status.autopilot)
        self.assertTrue(status.autopilot.enabled)
        self.assertEqual(status.autopilot.source, "pending")
        packets = {packet.ticker: packet for packet in status.manual_blocker_packets}
        self.assertEqual(packets["SIVE"].cannot_automate_reason, "source_backed_identity_required")
        self.assertIn("source_backed_current_listing", packets["SIVE"].required_fields)

    def test_preparation_status_skips_hydrated_missing_ticker_history(self) -> None:
        config = _config("hydrated_missing_history")
        _seed_ready_etf(config, "BIL", role="scoreable")
        upsert_missing_ticker_candidate(
            config.database_path,
            MissingTickerCandidate(
                ticker="BIL",
                first_seen_source="account_context",
                source_file="positions.csv",
                source_row="2",
                detected_asset_type="etf",
                recommended_asset_role="scoreable",
                status="hydrated",
                warnings="missing_etf_feature,missing_score",
            ),
        )

        status = research_preparation_status(config, source="all")

        self.assertEqual(status.total_items, 0)
        self.assertEqual(status.items, ())
        self.assertEqual(status.state_counts, ())

    def test_foreign_equity_identity_row_makes_pending_item_ready_to_apply(self) -> None:
        config = _config("foreign_ready")
        _seed_recommendation(
            config,
            "SIVE",
            warnings="missing_cik_metadata",
            blockers="missing_cik_metadata",
        )
        _write_foreign_equity_identity_rows(
            config,
            [
                {
                    "ticker": "SIVE",
                    "name": "Sivers Semiconductors AB",
                    "exchange": "Nasdaq Stockholm",
                    "currency": "SEK",
                    "country": "Sweden",
                    "sector": "Technology",
                    "industry": "Semiconductors",
                    "isin": "SE0003917798",
                    "source": "issuer_investor_page",
                    "source_url": "https://www.sivers-semiconductors.com/investors/shares-2/",
                    "as_of_date": "2026-06-15",
                    "effective_date": "2026-06-15",
                }
            ],
        )

        status = research_preparation_status(config)
        item = {entry.ticker: entry for entry in status.items}["SIVE"]
        dry_run = run_research_preparation(config, source="pending", action="prepare_ready")
        result = run_research_preparation(
            config,
            source="pending",
            action="prepare_ready",
            confirm=True,
        )
        asset = latest_asset(config.database_path, "SIVE")
        candidate = list_research_recommendation_candidates(config.database_path)[0]

        self.assertEqual(item.asset_type, "foreign_equity")
        self.assertEqual(item.research_path, "foreign_equity")
        self.assertEqual(item.preparation_state, "ready_to_apply")
        self.assertTrue(item.can_apply)
        self.assertNotIn("missing_cik_metadata", item.blockers)
        self.assertTrue(dry_run.dry_run)
        self.assertEqual(dry_run.applied_count, 0)
        self.assertEqual(result.applied_count, 1)
        self.assertEqual(result.applied_tickers, ("SIVE",))
        self.assertIsNotNone(asset)
        self.assertEqual(asset.asset_type, "equity")
        self.assertEqual(asset.asset_role, "scoreable")
        self.assertEqual(asset.source, "research_foreign_equity_identity")
        self.assertEqual(candidate.status, "pending")

    def test_preparation_status_reads_latest_autopilot_step(self) -> None:
        config = _config("autopilot_latest")
        _seed_recommendation(
            config,
            "SIVE",
            warnings="missing_cik_metadata",
            blockers="missing_cik_metadata",
        )
        now = datetime.now().isoformat(timespec="seconds")
        pipeline_run_id = start_pipeline_run(
            config.database_path,
            "manual_ops_cycle",
            source="manual_ops",
        )
        insert_pipeline_step_result(
            config.database_path,
            pipeline_run_id=pipeline_run_id,
            step_name=RESEARCH_PREPARATION_AUTO_STEP_NAME,
            status="warning",
            rows_loaded=2,
            warnings=(
                "manual_blockers:SIVE, "
                "cannot_automate:SIVE:source_backed_identity_required, "
                "applied:XLRE, ignored_recommendation_ids:1|2"
            ),
            source="manual_ops",
            started_at=now,
            finished_at=now,
        )

        status = research_preparation_status(config, source="all")

        self.assertIsNotNone(status.autopilot)
        self.assertFalse(status.autopilot.due)
        self.assertEqual(status.autopilot.latest_status, "warning")
        self.assertEqual(status.autopilot.latest_rows_loaded, 2)
        self.assertEqual(status.autopilot.applied_tickers, ("XLRE",))
        self.assertEqual(status.autopilot.ignored_context_rows, 2)

    def test_dry_run_preparation_makes_no_recommendation_decisions(self) -> None:
        config = _config("dry_run")
        _seed_ready_etf(config, "XLV", role="scoreable")
        _seed_recommendation(config, "XLV", warnings="already_scoreable")

        with sqlite3.connect(config.database_path) as connection:
            before = connection.execute("SELECT COUNT(*) FROM research_recommendation_decisions").fetchone()[0]
        result = run_research_preparation(config, action="ignore_already_scoreable", confirm=False)
        with sqlite3.connect(config.database_path) as connection:
            after = connection.execute("SELECT COUNT(*) FROM research_recommendation_decisions").fetchone()[0]

        self.assertTrue(result.dry_run)
        self.assertEqual(result.ignored_count, 0)
        self.assertEqual(before, after)
        self.assertEqual(list_research_recommendation_candidates(config.database_path)[0].status, "pending")

    def test_confirmed_ignore_updates_only_already_scoreable_context_rows(self) -> None:
        config = _config("confirmed_ignore")
        _seed_ready_etf(config, "XLV", role="scoreable")
        _seed_recommendation(config, "XLV", key="xlv", warnings="already_scoreable")
        _seed_recommendation(config, "SIVE", key="sive", blockers="missing_cik_metadata")

        result = run_research_preparation(config, action="ignore_already_scoreable", confirm=True)

        self.assertEqual(result.ignored_count, 1)
        refreshed = {candidate.ticker: candidate for candidate in list_research_recommendation_candidates(config.database_path)}
        self.assertEqual(refreshed["XLV"].status, "ignored")
        self.assertEqual(refreshed["SIVE"].status, "pending")

    def test_confirmed_prepare_ready_applies_without_promotion(self) -> None:
        config = _config("prepare_ready")
        _seed_ready_etf(config, "XLRE", role="commentary_validation")
        _seed_recommendation(
            config,
            "XLRE",
            blockers="etf_research_ticker_requires_etf_path",
        )

        with patch("target_opportunity_monitor.research_preparation.bulk_set_research_recommendation_status") as bulk_mock:
            result = run_research_preparation(config, action="prepare_ready", confirm=True)

        self.assertEqual(result.applied_count, 1)
        self.assertEqual(result.applied_tickers, ("XLRE",))
        asset = latest_asset(config.database_path, "XLRE")
        self.assertIsNotNone(asset)
        self.assertEqual(asset.asset_role, "scoreable")
        self.assertEqual(list_research_recommendation_candidates(config.database_path)[0].status, "pending")
        bulk_mock.assert_not_called()

    def test_dry_run_all_safe_makes_no_source_or_recommendation_changes(self) -> None:
        config = _config("dry_run_all_safe")
        _seed_etf_shell(config, "SOXL")
        _seed_recommendation(
            config,
            "SOXL",
            blockers="etf_research_ticker_requires_etf_path",
        )

        result = run_research_preparation(config, action="all_safe", confirm=False)

        self.assertTrue(result.dry_run)
        self.assertEqual(result.staged_count, 0)
        self.assertEqual(result.loaded_source_count, 0)
        self.assertFalse(config.etf_navs_path.exists())
        self.assertEqual(list_research_recommendation_candidates(config.database_path)[0].status, "pending")

    def test_confirmed_stage_load_and_compute_makes_etf_ready_to_apply(self) -> None:
        config = _config("stage_load_compute")
        _seed_etf_shell(config, "SOXL")
        _seed_recommendation(
            config,
            "SOXL",
            blockers="etf_research_ticker_requires_etf_path",
        )

        with patch(
            "target_opportunity_monitor.research_preparation._fetch_direxion_etf_evidence",
            return_value=_direxion_evidence("SOXL"),
        ):
            staged = run_research_preparation(
                config,
                action="stage_source_rows",
                confirm=True,
                tickers=("SOXL",),
            )
            loaded = run_research_preparation(
                config,
                action="load_staged_sources",
                confirm=True,
                tickers=("SOXL",),
            )
            computed = run_research_preparation(
                config,
                action="compute_ready",
                confirm=True,
                tickers=("SOXL",),
            )

        self.assertEqual(staged.staged_tickers, ("SOXL",))
        self.assertGreaterEqual(staged.staged_count, 11)
        self.assertEqual(loaded.loaded_source_tickers, ("SOXL",))
        self.assertEqual(computed.computed_tickers, ("SOXL",))
        status = research_preparation_status(config, tickers=("SOXL",))
        item = status.items[0]
        self.assertEqual(item.preparation_state, "ready_to_apply")
        self.assertTrue(item.can_apply)

    def test_compute_ready_keeps_etf_blocked_without_option_chain(self) -> None:
        config = _config("compute_missing_chain")
        _seed_etf_shell(config, "KORU", with_option_chain=False)
        _seed_recommendation(
            config,
            "KORU",
            blockers="etf_research_ticker_requires_etf_path",
        )

        with patch(
            "target_opportunity_monitor.research_preparation._fetch_direxion_etf_evidence",
            return_value=_direxion_evidence("KORU"),
        ):
            run_research_preparation(config, action="stage_source_rows", confirm=True, tickers=("KORU",))
            run_research_preparation(config, action="load_staged_sources", confirm=True, tickers=("KORU",))
            run_research_preparation(config, action="compute_ready", confirm=True, tickers=("KORU",))

        status = research_preparation_status(config, tickers=("KORU",))
        item = status.items[0]
        self.assertEqual(item.preparation_state, "source_data_required")
        self.assertIn("missing_option_chain", item.blockers)
        self.assertFalse(item.can_apply)


if __name__ == "__main__":
    unittest.main()
