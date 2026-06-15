from __future__ import annotations

from contextlib import ExitStack, closing, contextmanager
import sqlite3
from types import SimpleNamespace
from typing import Iterator
from unittest.mock import patch


class _ExistingPath:
    def exists(self) -> bool:
        return True


@contextmanager
def sqlite_connection_for_test(database_path) -> Iterator[sqlite3.Connection]:
    with closing(sqlite3.connect(database_path)) as connection:
        with connection:
            yield connection


DEFAULT_REFRESH_PIPELINE_PATCHES: dict[str, tuple[int, tuple[str, ...]]] = {
    "_price_step": (0, ()),
    "_fundamental_seed_step": (0, ()),
    "_revision_provider_fetch_step": (0, ()),
    "_revision_source_import_step": (0, ()),
    "_revision_aggregation_step": (0, ()),
    "_analyst_revision_load_step": (0, ()),
    "_revision_signal_step": (0, ()),
    "_revision_validation_step": (0, ()),
    "_news_catalyst_provider_fetch_step": (0, ()),
    "_news_catalyst_source_import_step": (0, ()),
    "_news_catalyst_text_backfill_step": (0, ()),
    "_news_catalyst_aggregation_step": (0, ()),
    "_news_catalyst_load_step": (0, ()),
    "_news_catalyst_signal_step": (0, ()),
    "_news_catalyst_validation_step": (0, ()),
    "_browser_captured_commentary_ingest_step": (0, ()),
    "_discord_captured_commentary_ingest_step": (0, ()),
    "_trader_commentary_load_step": (0, ()),
    "_trader_commentary_alias_step": (0, ()),
    "_trader_commentary_parse_step": (0, ()),
    "_trader_commentary_validation_step": (0, ()),
    "_insider_fetch_step": (0, ()),
    "_insider_signal_step": (0, ()),
    "_insider_validation_step": (0, ()),
    "_short_interest_provider_fetch_step": (0, ()),
    "_short_interest_source_import_step": (0, ()),
    "_short_interest_load_step": (0, ()),
    "_short_interest_signal_step": (0, ()),
    "_short_interest_validation_step": (0, ()),
    "_options_chain_fetch_step": (0, ()),
    "_options_chain_load_step": (0, ()),
    "_options_income_step": (0, ()),
    "_options_risk_step": (0, ()),
    "_options_position_load_step": (0, ()),
    "_options_outcome_step": (0, ()),
    "_options_lifecycle_step": (0, ()),
    "_etf_nav_csv_step": (0, ()),
    "_etf_holdings_step": (0, ()),
    "_quote_step": (0, ()),
    "_ibkr_etf_nav_step": (0, ()),
    "_target_step": (0, ()),
    "_score_step": (0, ()),
    "_fundamental_benchmark_step": (0, ()),
    "_alert_step": (0, ()),
    "_outcome_step": (0, ()),
    "_missing_ticker_resolver_step": (0, ()),
    "_portfolio_load_step": (0, ()),
    "_portfolio_context_step": (0, ()),
    "_technical_step": (0, ()),
    "_regime_step": (0, ()),
    "_range_step": (0, ()),
    "_readiness_step": (0, ()),
    "_dashboard_step": (1, ()),
}


@contextmanager
def patch_refresh_pipeline_for_test(
    overrides: dict[str, tuple[int, tuple[str, ...]]] | None = None,
    **step_overrides: tuple[int, tuple[str, ...]],
) -> Iterator[None]:
    values = dict(DEFAULT_REFRESH_PIPELINE_PATCHES)
    values.update(overrides or {})
    values.update(step_overrides)
    with ExitStack() as stack:
        for function_name, return_value in values.items():
            stack.enter_context(
                patch(
                    f"target_opportunity_monitor.pipeline.{function_name}",
                    return_value=return_value,
                )
            )
        stack.enter_context(
            patch(
                "target_opportunity_monitor.pipeline.write_daily_report",
                return_value=SimpleNamespace(path=_ExistingPath()),
            )
        )
        yield
