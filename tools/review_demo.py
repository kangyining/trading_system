"""Build an isolated, offline review example using synthetic issuer data."""
from __future__ import annotations

import argparse
from contextlib import ExitStack
from dataclasses import asdict, fields
from datetime import date, timedelta
import json
from pathlib import Path
import sys
import tempfile
import tomllib
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from target_opportunity_monitor.alerts import compute_alerts
from target_opportunity_monitor.config import load_config
from target_opportunity_monitor.dashboard import build_dashboard
from target_opportunity_monitor.db import initialize_database
from target_opportunity_monitor.market_data import compute_price_feature
from target_opportunity_monitor.reporting import write_daily_report
from target_opportunity_monitor.scoring import compute_scores
from target_opportunity_monitor.storage import (
    Asset, Estimate, Fundamental, Price, upsert_asset, upsert_estimate,
    upsert_fundamental, upsert_price_feature, upsert_prices,
)
from target_opportunity_monitor.valuation import compute_targets


def isolated_config(output: Path):
    raw_paths = tomllib.loads((PROJECT_ROOT / "configs/default.toml").read_text(encoding="utf-8-sig"))["paths"]
    paths = {}
    for key, value in raw_paths.items():
        original = (PROJECT_ROOT / value).resolve()
        paths[key] = str(original.relative_to(PROJECT_ROOT)) if original.is_relative_to(PROJECT_ROOT) else f"isolated/{key}/{original.name}"
    paths.update(project_root=output.as_posix(), scheduler_automations="isolated/automations")
    config_path = output / "review.toml"
    lines = ["[paths]"] + [f"{key} = {json.dumps(value.replace(chr(92), '/'))}" for key, value in paths.items()]
    lines += ["", "[market_data]", 'mode = "csv"', "", "[reports]", 'title = "SYNTHETIC REVIEW DEMO — Target Opportunity Monitor"', "", "[research_preparation]", "auto_enabled = false"]
    config_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    config = load_config(config_path)
    for field in fields(config):
        value = getattr(config, field.name)
        if isinstance(value, Path) and not value.resolve().is_relative_to(output):
            raise RuntimeError(f"Demo path escapes its output directory: {field.name}")
    return config


def seed_synthetic_data(config, today: date) -> None:
    initialize_database(config.database_path)
    for index, ticker in enumerate(("DEMOA", "DEMOB", "DEMOC", "DEMOGAP")):
        upsert_asset(config.database_path, Asset(
            ticker=ticker, name=f"Synthetic issuer {ticker}", sector="Synthetic sector",
            industry="Synthetic industry", source="review_fixture",
            as_of_date=today.isoformat(), effective_date=today.isoformat(),
        ))
        prices = []
        for offset in range(260):
            day = today - timedelta(days=259 - offset)
            close = 75 + index * 15 + offset * 0.08 + ((offset % 7) - 3) * 0.12
            prices.append(Price(
                ticker=ticker, price_date=day.isoformat(), open=close, high=close + 1,
                low=close - 1, close=close, adjusted_close=close, volume=1_000_000,
                source="review_fixture", as_of_date=day.isoformat(), effective_date=day.isoformat(),
            ))
        upsert_prices(config.database_path, prices)
        feature = compute_price_feature(ticker, prices)
        if feature is None:
            raise RuntimeError(f"Synthetic price feature was not computed: {ticker}")
        upsert_price_feature(config.database_path, feature)
        # One issuer deliberately lacks fundamentals, so reviewers can see a skip.
        if ticker == "DEMOGAP":
            continue
        for year, growth in ((today.year - 2, 0.9), (today.year - 1, 1.0)):
            scale = (1 + index * 0.15) * growth
            upsert_fundamental(config.database_path, Fundamental(
                ticker=ticker, fiscal_period_end=f"{year}-12-31", fiscal_period="FY",
                report_type="annual", currency="USD", revenue=1_000_000_000 * scale,
                operating_income=150_000_000 * scale, ebitda=180_000_000 * scale,
                net_income=120_000_000 * scale, diluted_eps=1.2 * scale,
                free_cash_flow=100_000_000 * scale, net_debt=100_000_000,
                total_equity=500_000_000, shares_outstanding=100_000_000,
                source="review_fixture", as_of_date=today.isoformat(), effective_date=today.isoformat(),
            ))
        upsert_estimate(config.database_path, Estimate(
            ticker=ticker, estimate_date=today.isoformat(), fiscal_period_end=f"{today.year + 1}-12-31",
            metric="eps", consensus_mean=1.44 * (1 + index * 0.15), revision_1m=0.03,
            revision_3m=0.05, source="review_fixture", as_of_date=today.isoformat(),
            effective_date=today.isoformat(),
        ))
    config.watchlist_path.parent.mkdir(parents=True, exist_ok=True)
    config.watchlist_path.write_text("ticker,asset_type\nDEMOA,equity\nDEMOB,equity\nDEMOC,equity\nDEMOGAP,equity\n", encoding="utf-8")


def run_demo(output: Path) -> dict:
    output = output.resolve()
    config = isolated_config(output)
    # Fail on any attempted network use, including an accidental future addition.
    with ExitStack() as stack:
        for target in ("socket.socket.connect", "socket.socket.connect_ex", "socket.create_connection", "socket.getaddrinfo"):
            stack.enter_context(patch(target, side_effect=RuntimeError("Network access is disabled in the review demo")))
        seed_synthetic_data(config, date.today())
        targets = compute_targets(config)
        scores = compute_scores(config)
        alerts = compute_alerts(config)
        report = write_daily_report(config)
        dashboard = build_dashboard(config)
    html = dashboard.path.read_text(encoding="utf-8")
    html = html.replace("<body>", '<body><div style="padding:16px;background:#fff3cd;color:#352600;font-weight:700">SYNTHETIC REVIEW DEMO — generated issuer inputs, not market observations or performance results.</div>', 1)
    dashboard.path.write_text(html, encoding="utf-8")
    summary = {
        "data_scope": "synthetic_review_fixture", "network_access": "disabled",
        "output_directory": str(output), "config": str(config.config_path),
        "computed_targets": targets.computed_count, "computed_scores": scores.computed_count,
        "skipped_scores": scores.skipped_count, "score_results": [asdict(row) for row in scores.results],
        "alerts": alerts.alert_count, "report": str(report.path), "csv": str(report.csv_path),
        "dashboard": str(dashboard.path),
    }
    (output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, help="New directory for demo files; existing directories are refused.")
    args = parser.parse_args()
    if args.output:
        output = args.output.resolve()
        if output.exists():
            parser.error("--output must name a new directory; existing files are never overwritten")
        output.mkdir(parents=True)
    else:
        parent = PROJECT_ROOT / "tmp"
        parent.mkdir(exist_ok=True)
        output = Path(tempfile.mkdtemp(prefix="review-demo-", dir=parent))
    print(json.dumps(run_demo(output), indent=2))


if __name__ == "__main__":
    main()
