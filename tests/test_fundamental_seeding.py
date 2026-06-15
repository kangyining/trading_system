from __future__ import annotations

from pathlib import Path
import sys
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
TEST_TMP_ROOT = PROJECT_ROOT / ".tmp_tests"
sys.path.insert(0, str(SRC_PATH))

from target_opportunity_monitor.cli import build_parser
from target_opportunity_monitor.fundamental_data import parse_fundamentals_csv
from target_opportunity_monitor.sec_fundamentals import (
    StockSplit,
    extract_sec_annual_fundamentals,
    load_cik_map,
    merge_fundamentals_csv,
)


def fact(
    value: float,
    fy: int,
    start: str | None,
    end: str,
    unit: str = "USD",
) -> dict[str, object]:
    payload: dict[str, object] = {
        "fy": fy,
        "fp": "FY",
        "form": "10-K",
        "end": end,
        "val": value,
        "filed": f"{fy + 1}-02-01",
    }
    if start is not None:
        payload["start"] = start
    return payload


def tag(values: list[dict[str, object]], unit: str = "USD") -> dict[str, object]:
    return {"units": {unit: values}}


class FundamentalSeedingTests(unittest.TestCase):
    def setUp(self) -> None:
        TEST_TMP_ROOT.mkdir(exist_ok=True)

    def test_cik_map_loader_normalizes_tickers_and_ciks(self) -> None:
        path = TEST_TMP_ROOT / "cik_map_seed_test.csv"
        path.write_text("ticker,cik\naapl,320193\n", encoding="utf-8")

        mapping = load_cik_map(path)

        self.assertEqual(mapping["AAPL"], "0000320193")

    def test_sec_companyfacts_transform_derives_fields_and_applies_split(self) -> None:
        payload = {
            "facts": {
                "us-gaap": {
                    "RevenueFromContractWithCustomerExcludingAssessedTax": tag(
                        [fact(1000, 2024, "2023-01-01", "2023-12-31")]
                    ),
                    "GrossProfit": tag([fact(700, 2024, "2023-01-01", "2023-12-31")]),
                    "OperatingIncomeLoss": tag(
                        [fact(400, 2024, "2023-01-01", "2023-12-31")]
                    ),
                    "Depreciation": tag([fact(40, 2024, "2023-01-01", "2023-12-31")]),
                    "AmortizationOfIntangibleAssets": tag(
                        [fact(10, 2024, "2023-01-01", "2023-12-31")]
                    ),
                    "NetIncomeLoss": tag([fact(300, 2024, "2023-01-01", "2023-12-31")]),
                    "EarningsPerShareDiluted": tag(
                        [fact(12, 2024, "2023-01-01", "2023-12-31", "USD/shares")],
                        "USD/shares",
                    ),
                    "NetCashProvidedByUsedInOperatingActivities": tag(
                        [fact(500, 2024, "2023-01-01", "2023-12-31")]
                    ),
                    "PaymentsToAcquirePropertyPlantAndEquipment": tag(
                        [fact(100, 2024, "2023-01-01", "2023-12-31")]
                    ),
                    "CashAndCashEquivalentsAtCarryingValue": tag(
                        [fact(80, 2024, None, "2023-12-31")]
                    ),
                    "LongTermDebtCurrent": tag([fact(30, 2024, None, "2023-12-31")]),
                    "LongTermDebtNoncurrent": tag([fact(70, 2024, None, "2023-12-31")]),
                    "Assets": tag([fact(2000, 2024, None, "2023-12-31")]),
                    "StockholdersEquity": tag([fact(900, 2024, None, "2023-12-31")]),
                    "WeightedAverageNumberOfDilutedSharesOutstanding": tag(
                        [fact(100, 2024, "2023-01-01", "2023-12-31", "shares")],
                        "shares",
                    ),
                }
            }
        }

        rows = extract_sec_annual_fundamentals(
            payload,
            "TEST",
            years=1,
            splits=[StockSplit("TEST", "2024-06-01", 10)],
            as_of_date="2026-06-06",
        )

        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row.ebitda, 450)
        self.assertEqual(row.capital_expenditure, -100)
        self.assertEqual(row.free_cash_flow, 400)
        self.assertEqual(row.net_debt, 20)
        self.assertEqual(row.diluted_eps, 1.2)
        self.assertEqual(row.diluted_shares, 1000)
        self.assertEqual(row.source, "sec_companyfacts_split_adjusted")

    def test_merge_replaces_prior_sec_rows_and_preserves_manual_rows(self) -> None:
        path = TEST_TMP_ROOT / "fundamentals_merge.csv"
        path.write_text(
            "\n".join(
                (
                    "ticker,fiscal_period_end,fiscal_period,report_type,currency,revenue,gross_profit,operating_income,ebitda,ebit,net_income,eps,diluted_eps,cash_from_operations,capital_expenditure,free_cash_flow,cash_and_equivalents,total_debt,net_debt,total_assets,total_equity,shares_outstanding,diluted_shares,source,as_of_date,effective_date",
                    "AAPL,2023-12-31,FY,annual,USD,1,,,,,,,,,,,,,,,,,,sec_companyfacts,2026-01-01,2023-12-31",
                    "AAPL,2022-12-31,FY,annual,USD,2,,,,,,,,,,,,,,,,,,manual_override,2026-01-01,2022-12-31",
                )
            ),
            encoding="utf-8",
        )
        new_rows = parse_fundamentals_csv(
            "\n".join(
                (
                    "ticker,fiscal_period_end,fiscal_period,report_type,currency,revenue,source,as_of_date,effective_date",
                    "AAPL,2024-12-31,FY,annual,USD,3,sec_companyfacts,2026-06-06,2024-12-31",
                )
            )
        )

        merge_fundamentals_csv(path, new_rows)
        rows = parse_fundamentals_csv(path.read_text(encoding="utf-8"))

        self.assertEqual(len(rows), 2)
        self.assertEqual([row.source for row in rows], ["manual_override", "sec_companyfacts"])
        self.assertEqual(rows[-1].revenue, 3)

    def test_seed_fundamentals_cli_is_registered(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["seed-fundamentals", "--ticker", "AAPL", "--years", "3"])

        self.assertEqual(args.command, "seed-fundamentals")
        self.assertEqual(args.ticker, "AAPL")
        self.assertEqual(args.years, 3)


if __name__ == "__main__":
    unittest.main()
