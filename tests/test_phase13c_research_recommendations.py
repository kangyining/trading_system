from __future__ import annotations

from argparse import Namespace
from contextlib import closing
from contextlib import redirect_stdout
from pathlib import Path
import csv
import io
import json
import sqlite3
import sys
import unittest
from unittest.mock import patch


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
TEST_TMP_ROOT = PROJECT_ROOT / ".tmp_tests" / "phase13c"
sys.path.insert(0, str(SRC_PATH))

from target_opportunity_monitor.cli import (
    command_export_research_recommendation_template,
    command_generate_research_recommendations,
    command_import_research_recommendations,
    command_promote_research_recommendation,
    command_research_recommendation_report,
    command_research_recommendation_status,
    command_set_research_recommendation_status,
    command_status,
)
from target_opportunity_monitor.config import AppConfig
from target_opportunity_monitor.db import REQUIRED_TABLES, initialize_database
from target_opportunity_monitor.research_recommendations import (
    bulk_set_research_recommendation_status,
    export_research_recommendation_template,
    generate_research_recommendations,
    import_research_recommendations,
    promote_research_recommendation,
    research_recommendation_triage,
    research_recommendation_status,
)
from target_opportunity_monitor.research_tickers import (
    apply_research_ticker,
    etf_strategy_review,
    research_ticker_plan,
    research_ticker_status,
)
from target_opportunity_monitor.storage import (
    Asset,
    EtfFeature,
    NewsCatalystSourceSnapshot,
    OptionChainSnapshot,
    OptionIncomeReview,
    PriceFeature,
    RangeSnapshot,
    ResearchRecommendationCandidate,
    Score,
    Target,
    TraderCommentaryBrowserCaptureRun,
    TraderCommentaryBrowserCaptureItem,
    TraderCommentaryClaim,
    count_rows_by_table,
    latest_asset,
    list_research_recommendation_candidates,
    list_research_recommendation_evidence,
    upsert_asset,
    upsert_etf_feature,
    upsert_research_recommendation_candidate,
    upsert_news_catalyst_source_snapshot,
    upsert_option_chain_snapshot,
    upsert_option_income_review,
    upsert_price_feature,
    upsert_range_snapshot,
    upsert_score,
    upsert_target,
    upsert_trader_commentary_browser_capture_item,
    upsert_trader_commentary_browser_capture_run,
    upsert_trader_commentary_claim,
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
        config_path=root / "phase13c.toml",
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
        research_recommendations_path=root
        / "data"
        / "research"
        / "manual"
        / "research_recommendations.csv",
        external_research_signals_db_path=root
        / "external"
        / "research-signals"
        / "x_posts.sqlite",
        cik_map_path=root / "configs" / "cik_map.csv",
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
                f'research_recommendations = "{config.research_recommendations_path.as_posix()}"',
                f'external_research_signals_db = "{config.external_research_signals_db_path.as_posix()}"',
                f'cik_map = "{config.cik_map_path.as_posix()}"',
                "",
                "[run]",
                'universe_mode = "manual_watchlist"',
                'run_mode = "daily_scoring"',
                "",
            )
        ),
        encoding="utf-8",
    )


def seed_assets(config: AppConfig) -> None:
    upsert_asset(
        config.database_path,
        Asset(
            ticker="AAPL",
            name="Apple",
            asset_type="equity",
            sector="Information Technology",
            industry="Consumer Electronics",
            asset_role="scoreable",
        ),
    )
    upsert_asset(
        config.database_path,
        Asset(
            ticker="TSLA",
            name="Tesla",
            asset_type="equity",
            sector="Consumer Discretionary",
            industry="Auto Manufacturers",
            asset_role="commentary_validation",
        ),
    )


def seed_ready_etf(config: AppConfig, ticker: str = "XLV") -> None:
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
            timing_score=65.0,
            risk_score=60.0,
            liquidity_score=85.0,
            asset_type="etf",
            score_model="etf_score_mvp_v1",
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
            target_low=98.0,
            target_high=120.0,
            etf_nav_per_share=101.0,
            etf_nav_gap=0.01,
            opportunity_score=72.0,
            confidence_score=75.0,
            timing_score=65.0,
            risk_score=60.0,
            liquidity_score=85.0,
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
            volume=50,
            open_interest=100,
            source="test_chain",
        ),
    )
    upsert_option_chain_snapshot(
        config.database_path,
        OptionChainSnapshot(
            ticker=ticker,
            snapshot_timestamp="2026-06-14T12:00:00+00:00",
            expiration_date="2026-07-17",
            option_type="put",
            strike=95.0,
            bid=1.4,
            ask=1.6,
            mark=1.5,
            volume=50,
            open_interest=100,
            source="test_chain",
        ),
    )
    upsert_option_income_review(
        config.database_path,
        OptionIncomeReview(
            ticker=ticker,
            review_date="2026-06-14",
            snapshot_timestamp="2026-06-14T12:00:00+00:00",
            expiration_date="2026-07-17",
            option_type="put",
            strike=95.0,
            bid=1.4,
            ask=1.6,
            mid_premium=1.5,
            breakeven=93.5,
            premium_yield=0.015,
            annualized_yield=0.18,
            downside_buffer_pct=0.05,
            assignment_notional=9500.0,
            open_interest=100,
            volume=50,
            current_price=100.0,
            range_state="starter_buy",
            review_category="eligible_watch",
        ),
    )


def write_cik_map(config: AppConfig, rows: list[tuple[str, str]]) -> None:
    config.cik_map_path.parent.mkdir(parents=True, exist_ok=True)
    with config.cik_map_path.open("w", encoding="utf-8", newline="") as output:
        writer = csv.writer(output)
        writer.writerow(("ticker", "cik"))
        writer.writerows(rows)


def write_foreign_equity_identity_rows(
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


def write_recommendation_rows(config: AppConfig, rows: list[dict[str, str]]) -> None:
    config.research_recommendations_path.parent.mkdir(parents=True, exist_ok=True)
    with config.research_recommendations_path.open("w", encoding="utf-8", newline="") as output:
        writer = csv.DictWriter(
            output,
            fieldnames=(
                "ticker",
                "recommendation_date",
                "source",
                "topic",
                "rationale",
                "confidence",
                "priority",
                "source_url",
                "notes",
                "status",
            ),
        )
        writer.writeheader()
        writer.writerows(rows)


class Phase13CResearchRecommendationsTest(unittest.TestCase):
    def test_tables_config_and_template(self) -> None:
        config = make_config(fresh_database_path("phase13c_tables.sqlite"))
        status = initialize_database(config.database_path)
        self.assertIn("research_recommendation_candidates", REQUIRED_TABLES)
        self.assertIn("research_recommendation_evidence", REQUIRED_TABLES)
        self.assertIn("research_recommendation_decisions", REQUIRED_TABLES)
        self.assertEqual(status.existing_required_table_count, len(REQUIRED_TABLES))

        path = export_research_recommendation_template(config)
        self.assertTrue(path.exists())
        self.assertIn("rationale", path.read_text(encoding="utf-8"))

    def test_tom_internal_candidates_include_reference_and_unsupported_claims(self) -> None:
        config = make_config(fresh_database_path("phase13c_internal.sqlite"))
        initialize_database(config.database_path)
        seed_assets(config)
        write_cik_map(config, [("TSLA", "0001318605")])
        upsert_trader_commentary_claim(
            config.database_path,
            TraderCommentaryClaim(
                claim_key="claim-tsla-support",
                claim_date="2026-06-10",
                claim_type="support",
                source="user_paste",
                ticker="TSLA",
                level_low=384,
                level_high=386,
                raw_excerpt="TSLA 384-386 support held.",
            ),
        )
        upsert_trader_commentary_claim(
            config.database_path,
            TraderCommentaryClaim(
                claim_key="claim-hood-target",
                claim_date="2026-06-10",
                claim_type="target",
                source="user_paste",
                ticker="HOOD",
                target_price=100,
                raw_excerpt="HOOD medium term system target 100.",
            ),
        )

        result = generate_research_recommendations(config, "tom_internal")
        self.assertGreaterEqual(result.candidate_count, 2)
        candidates = {
            candidate.ticker: candidate
            for candidate in list_research_recommendation_candidates(config.database_path)
        }
        self.assertIn("TSLA", candidates)
        self.assertIn("HOOD", candidates)
        self.assertIn("reference_only_candidate", candidates["TSLA"].warning_codes or "")
        self.assertIn("missing_cik_metadata", candidates["HOOD"].warning_codes or "")
        self.assertGreaterEqual(
            len(
                list_research_recommendation_evidence(
                    config.database_path,
                    recommendation_key=candidates["HOOD"].recommendation_key,
                )
            ),
            1,
        )

    def test_social_local_candidates_from_x_and_truth_rows(self) -> None:
        config = make_config(fresh_database_path("phase13c_social.sqlite"))
        initialize_database(config.database_path)
        seed_assets(config)
        upsert_trader_commentary_browser_capture_run(
            config.database_path,
            TraderCommentaryBrowserCaptureRun(
                run_id="run-1",
                provider="x_browser",
                run_date="2026-06-11",
                started_at="2026-06-11T13:29:00",
                status="ok",
            ),
        )
        upsert_trader_commentary_browser_capture_item(
            config.database_path,
            TraderCommentaryBrowserCaptureItem(
                run_id="run-1",
                provider="x_browser",
                item_key="x-1",
                content_text="Watching PLTR and HOOD for research after AI momentum.",
                observed_at="2026-06-11T13:30:00",
                canonical_url="https://x.example/post/1",
            ),
        )
        upsert_news_catalyst_source_snapshot(
            config.database_path,
            NewsCatalystSourceSnapshot(
                ticker="DJT",
                signal_date="2026-06-11",
                source="truth_social_public",
                source_url="https://truth.example/post/1",
                headline_or_event="Trump-related post mentions DJT catalyst risk.",
            ),
        )

        result = generate_research_recommendations(config, "social_local")
        self.assertGreaterEqual(result.candidate_count, 3)
        candidates = {
            candidate.ticker: candidate
            for candidate in list_research_recommendation_candidates(config.database_path)
        }
        self.assertIn("PLTR", candidates)
        self.assertIn("HOOD", candidates)
        self.assertIn("DJT", candidates)
        self.assertIn("social_text_only", candidates["PLTR"].warning_codes or "")

    def test_external_research_signals_import_preserves_approval_status(self) -> None:
        config = make_config(fresh_database_path("phase13c_external.sqlite"))
        initialize_database(config.database_path)
        seed_assets(config)
        config.external_research_signals_db_path.parent.mkdir(parents=True, exist_ok=True)
        if config.external_research_signals_db_path.exists():
            config.external_research_signals_db_path.unlink()
        with closing(sqlite3.connect(config.external_research_signals_db_path)) as connection:
            connection.execute(
                """
                CREATE TABLE research_suggestions (
                    id INTEGER PRIMARY KEY,
                    topic_title TEXT,
                    topic_slug TEXT,
                    tickers_json TEXT,
                    rationale TEXT,
                    priority REAL,
                    confidence REAL,
                    status TEXT,
                    report_path TEXT,
                    created_at TEXT
                )
                """
            )
            connection.execute(
                """
                INSERT INTO research_suggestions
                (topic_title, topic_slug, tickers_json, rationale, priority,
                 confidence, status, report_path, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "AI infrastructure watch",
                    "ai-infra-watch",
                    json.dumps(["ANET", "AAPL"]),
                    "External X queue surfaced AI infra discussion.",
                    80,
                    70,
                    "approved",
                    "reports/ai-infra.md",
                    "2026-06-12",
                ),
            )
            connection.commit()

        result = generate_research_recommendations(config, "external_research_signals")
        self.assertEqual(result.warnings, ())
        candidates = {
            candidate.ticker: candidate
            for candidate in list_research_recommendation_candidates(config.database_path)
        }
        self.assertEqual(candidates["ANET"].status, "approved")
        self.assertIn("already_scoreable", candidates["AAPL"].warning_codes or "")

    def test_manual_import_validation_and_cli(self) -> None:
        config = make_config(fresh_database_path("phase13c_manual.sqlite"))
        initialize_database(config.database_path)
        write_config(config)
        seed_assets(config)
        config.research_recommendations_path.parent.mkdir(parents=True, exist_ok=True)
        with config.research_recommendations_path.open(
            "w", encoding="utf-8", newline=""
        ) as output:
            writer = csv.DictWriter(
                output,
                fieldnames=(
                    "ticker",
                    "recommendation_date",
                    "source",
                    "topic",
                    "rationale",
                    "confidence",
                    "priority",
                    "source_url",
                    "notes",
                    "status",
                ),
            )
            writer.writeheader()
            writer.writerow(
                {
                    "ticker": "CRWD",
                    "recommendation_date": "2026-06-12",
                    "source": "codex_manual",
                    "topic": "Cybersecurity peer research",
                    "rationale": "Add as a software/security comparison candidate.",
                    "confidence": "65",
                    "priority": "72",
                    "source_url": "manual://codex",
                    "notes": "Audited local idea.",
                    "status": "pending",
                }
            )
            writer.writerow({"ticker": "", "rationale": ""})

        result = import_research_recommendations(config)
        self.assertEqual(result.imported_count, 1)
        self.assertEqual(result.skipped_count, 1)

        with redirect_stdout(io.StringIO()) as output:
            self.assertEqual(
                command_research_recommendation_status(Namespace(config=config.config_path)),
                0,
            )
        self.assertIn("CRWD", output.getvalue())
        with redirect_stdout(io.StringIO()) as output:
            self.assertEqual(
                command_research_recommendation_report(Namespace(config=config.config_path)),
                0,
            )
        self.assertIn("Research Recommendation Queue", output.getvalue())
        with redirect_stdout(io.StringIO()) as output:
            self.assertEqual(
                command_export_research_recommendation_template(
                    Namespace(config=config.config_path)
                ),
                0,
            )
        self.assertIn("Research recommendation template", output.getvalue())
        with redirect_stdout(io.StringIO()) as output:
            self.assertEqual(
                command_import_research_recommendations(
                    Namespace(config=config.config_path, file=None)
                ),
                0,
            )
        self.assertIn("Imported rows", output.getvalue())

    def test_research_recommendation_triage_groups_pending_duplicates(self) -> None:
        config = make_config(fresh_database_path("phase13c_triage.sqlite"))
        initialize_database(config.database_path)
        seed_assets(config)
        upsert_asset(
            config.database_path,
            Asset(
                ticker="XLV",
                name="Health Care Select Sector SPDR",
                asset_type="etf",
                asset_role="reference",
            ),
        )
        write_cik_map(config, [("CRWD", "0001535527")])
        write_recommendation_rows(
            config,
            [
                {
                    "ticker": "CRWD",
                    "recommendation_date": "2026-06-12",
                    "source": "codex_manual",
                    "topic": "Cloud security peer",
                    "rationale": "Review as a software security peer.",
                    "priority": "72",
                    "status": "pending",
                },
                {
                    "ticker": "CRWD",
                    "recommendation_date": "2026-06-13",
                    "source": "codex_manual",
                    "topic": "Security platform expansion",
                    "rationale": "Duplicate CRWD research idea from another note.",
                    "priority": "68",
                    "status": "pending",
                },
                {
                    "ticker": "HOOD",
                    "recommendation_date": "2026-06-12",
                    "source": "codex_manual",
                    "topic": "Brokerage peer",
                    "rationale": "Needs metadata before promotion.",
                    "priority": "64",
                    "status": "pending",
                },
                {
                    "ticker": "XLV",
                    "recommendation_date": "2026-06-12",
                    "source": "codex_manual",
                    "topic": "ETF review",
                    "rationale": "ETF recommendation should use an ETF path.",
                    "priority": "80",
                    "status": "pending",
                },
                {
                    "ticker": "AAPL",
                    "recommendation_date": "2026-06-12",
                    "source": "codex_manual",
                    "topic": "Existing holding context",
                    "rationale": "Already scoreable context row.",
                    "priority": "58",
                    "status": "pending",
                },
            ],
        )
        import_research_recommendations(config)
        upsert_research_recommendation_candidate(
            config.database_path,
            ResearchRecommendationCandidate(
                recommendation_key="manual-review-key",
                ticker="MANU",
                recommendation_date="2026-06-12",
                source="codex_manual",
                status="pending",
                topic="Manual review",
                rationale="Synthetic blocker for manual-review triage.",
                research_priority_score=45.0,
                confidence=50.0,
                source_count=1,
                evidence_count=1,
                source_mix="codex_manual",
                metadata_status="unknown",
                warning_codes="custom_warning",
                promotion_blockers="custom_review",
            ),
        )

        triage = research_recommendation_triage(config)
        groups = {group.ticker: group for group in triage.groups}

        self.assertEqual(triage.pending_count, 6)
        self.assertEqual(groups["CRWD"].candidate_count, 2)
        self.assertEqual(groups["CRWD"].classification, "promotion_ready_after_approval")
        self.assertEqual(len(groups["CRWD"].representative_candidate_ids), 2)
        self.assertEqual(groups["HOOD"].classification, "metadata_required")
        self.assertEqual(groups["XLV"].classification, "etf_path_required")
        self.assertEqual(groups["AAPL"].classification, "already_scoreable_context_only")
        self.assertEqual(groups["MANU"].classification, "manual_review_required")
        classification_counts = dict(triage.classification_counts)
        self.assertEqual(classification_counts["promotion_ready_after_approval"], 1)
        self.assertEqual(classification_counts["metadata_required"], 1)
        self.assertEqual(classification_counts["etf_path_required"], 1)
        self.assertEqual(classification_counts["already_scoreable_context_only"], 1)
        self.assertEqual(classification_counts["manual_review_required"], 1)

    def test_etf_research_plan_uses_etf_path_without_cik(self) -> None:
        config = make_config(fresh_database_path("phase13c_etf_plan.sqlite"))
        initialize_database(config.database_path)
        upsert_asset(
            config.database_path,
            Asset(
                ticker="XLV",
                name="Health Care Select Sector SPDR",
                asset_type="etf",
                asset_role="commentary_validation",
            ),
        )

        plan = research_ticker_plan(config, "XLV", asset_type="etf")
        status = research_ticker_status(config, "XLV")

        self.assertEqual(plan.asset_type, "etf")
        self.assertEqual(plan.research_path, "etf")
        self.assertEqual(plan.blocked_reason, "etf_readiness_required")
        self.assertIn("missing_etf_feature", plan.readiness_blockers)
        self.assertNotIn("missing_cik", plan.readiness_blockers)
        self.assertNotIn("missing_cik", plan.warnings)
        self.assertIn("not_active_scoreable", status.readiness_blockers)
        self.assertNotIn("missing_cik", status.readiness_blockers)

    def test_ready_etf_reference_can_be_promoted_only_with_confirmed_etf_apply(self) -> None:
        config = make_config(fresh_database_path("phase13c_ready_etf.sqlite"))
        initialize_database(config.database_path)
        seed_ready_etf(config, "XLV")

        plan = research_ticker_plan(config, "XLV", asset_type="etf")
        dry_run = apply_research_ticker(config, "XLV", asset_type="etf", confirm=False)
        result = apply_research_ticker(config, "XLV", asset_type="etf", confirm=True)
        asset = latest_asset(config.database_path, "XLV")

        self.assertTrue(plan.apply_ready)
        self.assertIsNone(plan.blocked_reason)
        self.assertFalse(dry_run.applied)
        self.assertTrue(dry_run.dry_run)
        self.assertTrue(result.applied)
        self.assertEqual(result.asset_type, "etf")
        self.assertIsNotNone(asset)
        self.assertEqual(asset.asset_type, "etf")
        self.assertEqual(asset.asset_role, "scoreable")

    def test_etf_strategy_review_uses_stored_call_and_sell_put_rows(self) -> None:
        config = make_config(fresh_database_path("phase13c_etf_strategy.sqlite"))
        initialize_database(config.database_path)
        seed_ready_etf(config, "XLV")

        review = etf_strategy_review(config, "XLV")

        self.assertEqual(review.asset_type, "etf")
        self.assertEqual(review.share.status, "available")
        self.assertEqual(review.long_call.status, "available")
        self.assertEqual(review.long_call.option_strike, 105.0)
        self.assertEqual(review.sell_put.status, "available")
        self.assertEqual(review.sell_put.option_strike, 95.0)
        self.assertIn(
            review.decision,
            {
                "prefer_etf_shares",
                "prefer_long_call",
                "prefer_sell_put",
                "wait_no_clean_entry",
            },
        )

    def test_etf_recommendation_promotion_uses_etf_path(self) -> None:
        config = make_config(fresh_database_path("phase13c_etf_promotion_path.sqlite"))
        initialize_database(config.database_path)
        seed_ready_etf(config, "XLV")
        upsert_research_recommendation_candidate(
            config.database_path,
            ResearchRecommendationCandidate(
                recommendation_key="xlv-etf",
                ticker="XLV",
                recommendation_date="2026-06-12",
                source="codex_manual",
                status="approved",
                topic="ETF path",
                rationale="ETF recommendation should promote through ETF path.",
                research_priority_score=80.0,
                confidence=70.0,
                source_count=1,
                evidence_count=1,
                source_mix="codex_manual",
                metadata_status="reference",
                promotion_blockers="etf_research_ticker_requires_etf_path",
            ),
        )
        candidate = list_research_recommendation_candidates(config.database_path)[0]

        with patch(
            "target_opportunity_monitor.research_recommendations.apply_research_ticker"
        ) as apply_mock:
            apply_mock.return_value = type(
                "ApplyResult",
                (),
                {
                    "blocked_reason": None,
                    "warnings": (),
                },
            )()
            result = promote_research_recommendation(
                config, candidate.research_recommendation_id, confirm=True
            )

        self.assertTrue(result.promoted)
        apply_mock.assert_called_once()
        self.assertEqual(apply_mock.call_args.kwargs["asset_type"], "etf")

    def test_equity_path_still_requires_cik_for_non_us_symbol(self) -> None:
        config = make_config(fresh_database_path("phase13c_equity_cik_strict.sqlite"))
        initialize_database(config.database_path)
        write_foreign_equity_identity_rows(
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

        plan = research_ticker_plan(
            config,
            "SIVE",
            asset_type="equity",
            name="Sivers Semiconductors AB",
            sector="Technology",
            industry="Semiconductors",
        )

        self.assertFalse(plan.apply_ready)
        self.assertEqual(plan.asset_type, "equity")
        self.assertEqual(plan.blocked_reason, "missing_cik")

    def test_foreign_equity_identity_row_makes_plan_apply_ready_without_cik(self) -> None:
        config = make_config(fresh_database_path("phase13c_foreign_plan.sqlite"))
        initialize_database(config.database_path)
        write_foreign_equity_identity_rows(
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

        plan = research_ticker_plan(config, "SIVE", asset_type="foreign_equity")

        self.assertTrue(plan.apply_ready)
        self.assertEqual(plan.asset_type, "foreign_equity")
        self.assertEqual(plan.research_path, "foreign_equity")
        self.assertIsNone(plan.blocked_reason)
        self.assertEqual(plan.metadata.cik, None)
        self.assertEqual(plan.metadata.isin, "SE0003917798")
        self.assertEqual(plan.metadata.source_url, "https://www.sivers-semiconductors.com/investors/shares-2/")
        self.assertNotIn("missing_cik", plan.readiness_blockers)

    def test_invalid_foreign_equity_identity_row_blocks_plan(self) -> None:
        config = make_config(fresh_database_path("phase13c_foreign_invalid.sqlite"))
        initialize_database(config.database_path)
        write_foreign_equity_identity_rows(
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
                    "source": "issuer_investor_page",
                    "as_of_date": "2026-06-15",
                    "effective_date": "2026-06-15",
                }
            ],
        )

        plan = research_ticker_plan(config, "SIVE", asset_type="foreign_equity")

        self.assertFalse(plan.apply_ready)
        self.assertEqual(plan.blocked_reason, "foreign_equity_identity_required")
        self.assertIn("missing_isin", plan.readiness_blockers)
        self.assertIn("missing_source_url", plan.readiness_blockers)

    def test_foreign_equity_identity_reclassifies_existing_missing_cik_recommendations(self) -> None:
        config = make_config(fresh_database_path("phase13c_foreign_triage.sqlite"))
        initialize_database(config.database_path)
        write_foreign_equity_identity_rows(
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
        upsert_research_recommendation_candidate(
            config.database_path,
            ResearchRecommendationCandidate(
                recommendation_key="sive-foreign",
                ticker="SIVE",
                recommendation_date="2026-06-15",
                source="codex_manual",
                status="pending",
                topic="Foreign equity path",
                rationale="Existing row was imported before foreign-equity path support.",
                research_priority_score=46.0,
                confidence=70.0,
                source_count=1,
                evidence_count=1,
                source_mix="codex_manual",
                warning_codes="missing_cik_metadata",
                promotion_blockers="missing_cik_metadata",
            ),
        )

        triage = research_recommendation_triage(config)
        group = triage.groups[0]
        status = research_recommendation_status(config)

        self.assertEqual(group.ticker, "SIVE")
        self.assertEqual(group.classification, "foreign_equity_path_required")
        self.assertIn("foreign_equity_path_required", group.promotion_blockers)
        self.assertNotIn("missing_cik_metadata", group.promotion_blockers)
        self.assertIn("foreign_equity_path_required", status.warnings)
        self.assertNotIn("missing_cik_metadata", status.warnings)

    def test_confirmed_foreign_equity_apply_creates_scoreable_asset_without_cik_map(self) -> None:
        config = make_config(fresh_database_path("phase13c_foreign_apply.sqlite"))
        initialize_database(config.database_path)
        write_foreign_equity_identity_rows(
            config,
            [
                {
                    "ticker": "SOI",
                    "name": "Soitec SA",
                    "exchange": "Euronext Paris/XPAR",
                    "currency": "EUR",
                    "country": "France",
                    "sector": "Technology",
                    "industry": "Semiconductors",
                    "isin": "FR0013227113",
                    "source": "exchange_listing_page",
                    "source_url": "https://live.euronext.com/en/product/equities/FR0013227113-XPAR",
                    "as_of_date": "2026-06-15",
                    "effective_date": "2026-06-15",
                }
            ],
        )

        dry_run = apply_research_ticker(config, "SOI", asset_type="foreign_equity", confirm=False)
        result = apply_research_ticker(config, "SOI", asset_type="foreign_equity", confirm=True)
        asset = latest_asset(config.database_path, "SOI")
        status = research_ticker_status(config, "SOI")

        self.assertFalse(dry_run.applied)
        self.assertTrue(result.applied)
        self.assertEqual(result.asset_type, "foreign_equity")
        self.assertIsNotNone(asset)
        self.assertEqual(asset.asset_type, "equity")
        self.assertEqual(asset.asset_role, "scoreable")
        self.assertEqual(asset.source, "research_foreign_equity_identity")
        self.assertEqual(asset.currency, "EUR")
        self.assertEqual(asset.country, "France")
        self.assertFalse(config.cik_map_path.exists())
        self.assertTrue(status.foreign_identity_available)
        self.assertEqual(status.foreign_identity_isin, "FR0013227113")
        self.assertNotIn("missing_cik", status.readiness_blockers)

    def test_foreign_identity_suppresses_cik_blocker_after_manual_asset_reload(self) -> None:
        config = make_config(fresh_database_path("phase13c_foreign_manual_asset.sqlite"))
        initialize_database(config.database_path)
        write_foreign_equity_identity_rows(
            config,
            [
                {
                    "ticker": "SIVE",
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
                }
            ],
        )
        upsert_asset(
            config.database_path,
            Asset(
                ticker="SIVE",
                name="Sivers Semiconductors AB",
                asset_type="equity",
                exchange="Nasdaq Stockholm",
                currency="SEK",
                sector="Information Technology",
                industry="Semiconductors",
                country="Sweden",
                asset_role="scoreable",
                active_flag=1,
                source="manual",
            ),
        )

        status = research_ticker_status(config, "SIVE")

        self.assertTrue(status.foreign_identity_available)
        self.assertNotIn("missing_cik", status.readiness_blockers)

    def test_bulk_status_updates_only_requested_recommendation_rows(self) -> None:
        config = make_config(fresh_database_path("phase13c_bulk.sqlite"))
        initialize_database(config.database_path)
        write_cik_map(config, [("CRWD", "0001535527")])
        write_recommendation_rows(
            config,
            [
                {
                    "ticker": "CRWD",
                    "recommendation_date": "2026-06-12",
                    "source": "codex_manual",
                    "topic": "Cloud security peer",
                    "rationale": "Review as a software security peer.",
                    "priority": "72",
                    "status": "pending",
                },
                {
                    "ticker": "HOOD",
                    "recommendation_date": "2026-06-12",
                    "source": "codex_manual",
                    "topic": "Brokerage peer",
                    "rationale": "Needs metadata before promotion.",
                    "priority": "64",
                    "status": "pending",
                },
            ],
        )
        import_research_recommendations(config)
        candidates = list_research_recommendation_candidates(config.database_path)
        ids = tuple(candidate.research_recommendation_id for candidate in candidates)

        promoted = bulk_set_research_recommendation_status(
            config, ids, "promoted", reason="test"
        )
        self.assertEqual(promoted.blocked_reason, "invalid_bulk_status")
        missing = bulk_set_research_recommendation_status(
            config, (999999,), "approved", reason="test"
        )
        self.assertEqual(missing.blocked_reason, "unknown_recommendation_ids")

        with patch("target_opportunity_monitor.research_recommendations.apply_research_ticker") as apply_mock:
            result = bulk_set_research_recommendation_status(
                config, ids[:1], "approved", reason="bulk_test"
            )

        self.assertIsNone(result.blocked_reason)
        self.assertEqual(result.updated_count, 1)
        apply_mock.assert_not_called()
        refreshed = {
            candidate.research_recommendation_id: candidate
            for candidate in list_research_recommendation_candidates(config.database_path)
        }
        self.assertEqual(refreshed[ids[0]].status, "approved")
        self.assertEqual(refreshed[ids[1]].status, "pending")
        with closing(sqlite3.connect(config.database_path)) as connection:
            decisions = connection.execute(
                "SELECT COUNT(*) FROM research_recommendation_decisions"
            ).fetchone()[0]
        self.assertEqual(decisions, 1)

    def test_status_update_and_promotion_gate(self) -> None:
        config = make_config(fresh_database_path("phase13c_promotion.sqlite"))
        initialize_database(config.database_path)
        write_config(config)
        seed_assets(config)
        config.research_recommendations_path.parent.mkdir(parents=True, exist_ok=True)
        with config.research_recommendations_path.open(
            "w", encoding="utf-8", newline=""
        ) as output:
            writer = csv.DictWriter(
                output,
                fieldnames=(
                    "ticker",
                    "recommendation_date",
                    "source",
                    "topic",
                    "rationale",
                    "confidence",
                    "priority",
                    "source_url",
                    "notes",
                    "status",
                ),
            )
            writer.writeheader()
            writer.writerow(
                {
                    "ticker": "CRWD",
                    "recommendation_date": "2026-06-12",
                    "source": "codex_manual",
                    "rationale": "Manual candidate.",
                    "status": "pending",
                }
            )
        import_research_recommendations(config)
        candidate = list_research_recommendation_candidates(config.database_path)[0]

        blocked = promote_research_recommendation(
            config, candidate.research_recommendation_id, confirm=True
        )
        self.assertFalse(blocked.promoted)
        self.assertEqual(
            blocked.blocked_reason, "recommendation_must_be_approved_before_promotion"
        )

        with redirect_stdout(io.StringIO()) as output:
            self.assertEqual(
                command_set_research_recommendation_status(
                    Namespace(
                        config=config.config_path,
                        id=candidate.research_recommendation_id,
                        status="approved",
                        reason="test",
                    )
                ),
                0,
            )
        self.assertIn("approved", output.getvalue())
        with patch(
            "target_opportunity_monitor.research_recommendations.apply_research_ticker"
        ) as apply_mock:
            apply_mock.return_value = type(
                "ApplyResult",
                (),
                {
                    "blocked_reason": "missing_cik_metadata",
                    "warnings": ("missing_cik_metadata",),
                },
            )()
            promoted = promote_research_recommendation(
                config, candidate.research_recommendation_id, confirm=True
            )
        self.assertFalse(promoted.promoted)
        self.assertEqual(promoted.blocked_reason, "missing_cik_metadata")

        with patch(
            "target_opportunity_monitor.research_recommendations.apply_research_ticker"
        ) as apply_mock:
            apply_mock.return_value = type(
                "ApplyResult",
                (),
                {
                    "blocked_reason": "missing_cik_metadata",
                    "warnings": ("missing_cik_metadata",),
                },
            )()
            with redirect_stdout(io.StringIO()) as output:
                self.assertEqual(
                    command_promote_research_recommendation(
                        Namespace(
                            config=config.config_path,
                            id=candidate.research_recommendation_id,
                            confirm=True,
                        )
                    ),
                    1,
                )
        self.assertIn("Blocked reason", output.getvalue())

    def test_cli_generate_and_status_output(self) -> None:
        config = make_config(fresh_database_path("phase13c_cli.sqlite"))
        initialize_database(config.database_path)
        write_config(config)
        seed_assets(config)
        upsert_trader_commentary_claim(
            config.database_path,
            TraderCommentaryClaim(
                claim_key="claim-hood-cli",
                claim_date="2026-06-10",
                claim_type="target",
                source="user_paste",
                ticker="HOOD",
                target_price=100,
                raw_excerpt="HOOD to 100.",
            ),
        )

        with redirect_stdout(io.StringIO()) as output:
            self.assertEqual(
                command_generate_research_recommendations(
                    Namespace(config=config.config_path, source="tom_internal")
                ),
                0,
            )
        self.assertIn("Candidates touched", output.getvalue())
        with redirect_stdout(io.StringIO()) as output:
            self.assertEqual(command_status(Namespace(config=config.config_path)), 0)
        self.assertIn("Research recommendation candidates", output.getvalue())
        self.assertGreater(
            count_rows_by_table(config.database_path, "research_recommendation_candidates"),
            0,
        )


if __name__ == "__main__":
    unittest.main()
