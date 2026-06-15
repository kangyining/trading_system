from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
import json
import math
import threading
import time
from typing import Any

from .config import AppConfig
from .etf_data import refresh_etf_features
from .storage import (
    Asset,
    EtfNav,
    OptionChainSnapshot,
    Price,
    QuoteSnapshot,
    insert_data_quality_check,
    latest_price_feature,
    list_assets,
    normalize_ticker,
    upsert_etf_nav,
    upsert_quote_snapshot,
)


MARKET_DATA_TYPE_CODES = {
    "live": 1,
    "frozen": 2,
    "delayed": 3,
    "delayed_frozen": 4,
}

MARKET_DATA_TYPE_LABELS = {
    1: "live",
    2: "frozen",
    3: "delayed",
    4: "delayed_frozen",
}


@dataclass(frozen=True)
class IbkrStatusResult:
    available: bool
    connected: bool
    host: str
    port: int
    managed_account_count: int
    server_time: int | None
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class IbkrTickerProbeResult:
    ticker: str
    status: str
    contract_found: bool
    historical_rows: int
    quote_loaded: bool
    etf_nav_loaded: bool
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class IbkrQuoteTickerResult:
    ticker: str
    status: str
    rows_loaded: int
    market_data_type: str | None
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class IbkrQuoteUpdateResult:
    results: tuple[IbkrQuoteTickerResult, ...]

    @property
    def loaded_count(self) -> int:
        return sum(result.rows_loaded for result in self.results)

    @property
    def warning_count(self) -> int:
        return sum(1 for result in self.results if result.warnings)


@dataclass(frozen=True)
class IbkrEtfNavTickerResult:
    ticker: str
    status: str
    rows_loaded: int
    nav_per_share: float | None
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class IbkrEtfNavUpdateResult:
    results: tuple[IbkrEtfNavTickerResult, ...]

    @property
    def loaded_count(self) -> int:
        return sum(result.rows_loaded for result in self.results)

    @property
    def warning_count(self) -> int:
        return sum(1 for result in self.results if result.warnings)


@dataclass(frozen=True)
class IbkrOptionChainTickerResult:
    ticker: str
    status: str
    rows_loaded: int
    selected_expirations: int
    selected_strikes: int
    snapshots: tuple[OptionChainSnapshot, ...]
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class IbkrOptionChainFetchResult:
    results: tuple[IbkrOptionChainTickerResult, ...]

    @property
    def loaded_count(self) -> int:
        return sum(result.rows_loaded for result in self.results)

    @property
    def warning_count(self) -> int:
        return sum(1 for result in self.results if result.warnings)


def _import_ibapi() -> tuple[Any, Any, Any, str | None]:
    try:
        from ibapi.client import EClient
        from ibapi.contract import Contract
        from ibapi.wrapper import EWrapper
    except Exception as error:  # pragma: no cover - environment dependent
        return None, None, None, str(error)
    return EClient, Contract, EWrapper, None


def _port(config: AppConfig, paper: bool = True) -> int:
    return config.ibkr_paper_port if paper else config.ibkr_live_port


def _market_data_type_code(config: AppConfig) -> int:
    return MARKET_DATA_TYPE_CODES.get(config.ibkr_market_data_type, 4)


def _stock_contract(contract_class: Any, ticker: str) -> Any:
    contract = contract_class()
    contract.symbol = _ibkr_symbol(ticker)
    contract.secType = "STK"
    contract.exchange = "SMART"
    contract.currency = "USD"
    return contract


def _ibkr_symbol(ticker: str) -> str:
    return normalize_ticker(ticker).replace(".", " ")


def _is_info_error(code: int) -> bool:
    return code in {2104, 2106, 2158, 10167}


def _bar_date(value: object) -> str:
    text = str(value).strip()
    if len(text) == 8 and text.isdigit():
        return f"{text[:4]}-{text[4:6]}-{text[6:]}"
    return text.split()[0]


def check_ibkr_status(config: AppConfig, paper: bool = True) -> IbkrStatusResult:
    EClient, _Contract, EWrapper, import_error = _import_ibapi()
    port = _port(config, paper=paper)
    if import_error:
        return IbkrStatusResult(
            available=False,
            connected=False,
            host=config.ibkr_host,
            port=port,
            managed_account_count=0,
            server_time=None,
            warnings=(f"ibapi_unavailable:{import_error}",),
        )

    class StatusApp(EWrapper, EClient):  # type: ignore[misc, valid-type]
        def __init__(self) -> None:
            EClient.__init__(self, self)
            self.server_time: int | None = None
            self.accounts: str | None = None
            self.warnings: list[str] = []

        def nextValidId(self, orderId: int) -> None:
            self.reqCurrentTime()
            self.reqManagedAccts()

        def currentTime(self, time_: int) -> None:
            self.server_time = int(time_)

        def managedAccounts(self, accountsList: str) -> None:
            self.accounts = accountsList

        def error(
            self,
            reqId: int,
            errorCode: int,
            errorString: str,
            advancedOrderRejectJson: str = "",
        ) -> None:
            if not _is_info_error(int(errorCode)):
                self.warnings.append(f"{errorCode}:{errorString}")

    app = StatusApp()
    try:
        app.connect(config.ibkr_host, port, clientId=config.ibkr_client_id)
    except Exception as error:
        return IbkrStatusResult(
            available=True,
            connected=False,
            host=config.ibkr_host,
            port=port,
            managed_account_count=0,
            server_time=None,
            warnings=(f"connect_failed:{error}",),
        )

    thread = threading.Thread(target=app.run, daemon=True)
    thread.start()
    deadline = time.time() + config.ibkr_timeout_seconds
    while time.time() < deadline:
        if app.server_time is not None and app.accounts is not None:
            break
        time.sleep(0.1)
    connected = bool(app.isConnected())
    accounts = [account for account in (app.accounts or "").split(",") if account]
    app.disconnect()
    time.sleep(0.1)
    warnings = tuple(app.warnings)
    if app.server_time is None:
        warnings = warnings + ("server_time_timeout",)
    return IbkrStatusResult(
        available=True,
        connected=connected,
        host=config.ibkr_host,
        port=port,
        managed_account_count=len(accounts),
        server_time=app.server_time,
        warnings=warnings,
    )


def fetch_ibkr_historical_prices(config: AppConfig, asset: Asset) -> list[Price]:
    EClient, Contract, EWrapper, import_error = _import_ibapi()
    if import_error:
        raise ValueError(f"ibapi unavailable: {import_error}")

    class HistoricalApp(EWrapper, EClient):  # type: ignore[misc, valid-type]
        def __init__(self) -> None:
            EClient.__init__(self, self)
            self.bars: list[Any] = []
            self.done = False
            self.errors: list[str] = []

        def nextValidId(self, orderId: int) -> None:
            years = max(1, math.ceil(config.market_data_lookback_days / 365))
            self.reqHistoricalData(
                7101,
                _stock_contract(Contract, asset.ticker),
                "",
                f"{years} Y",
                "1 day",
                "TRADES",
                1,
                1,
                False,
                [],
            )

        def historicalData(self, reqId: int, bar: Any) -> None:
            self.bars.append(bar)

        def historicalDataEnd(self, reqId: int, start: str, end: str) -> None:
            self.done = True

        def error(
            self,
            reqId: int,
            errorCode: int,
            errorString: str,
            advancedOrderRejectJson: str = "",
        ) -> None:
            if not _is_info_error(int(errorCode)):
                self.errors.append(f"{errorCode}:{errorString}")
            if reqId == 7101 and int(errorCode) not in {2104, 2106, 2158, 10167}:
                self.done = True

    app = HistoricalApp()
    app.connect(config.ibkr_host, config.ibkr_paper_port, clientId=config.ibkr_client_id + 1)
    thread = threading.Thread(target=app.run, daemon=True)
    thread.start()
    deadline = time.time() + config.ibkr_timeout_seconds
    while time.time() < deadline and not app.done:
        time.sleep(0.1)
    app.disconnect()
    time.sleep(0.1)

    if app.errors:
        raise ValueError("; ".join(app.errors))
    if not app.bars:
        raise ValueError(f"IBKR returned no historical bars for {asset.ticker}.")

    prices: list[Price] = []
    for bar in app.bars:
        price_date = _bar_date(bar.date)
        prices.append(
            Price(
                ticker=asset.ticker,
                price_date=price_date,
                open=float(bar.open),
                high=float(bar.high),
                low=float(bar.low),
                close=float(bar.close),
                adjusted_close=float(bar.close),
                volume=float(bar.volume),
                source="ibkr_historical",
                as_of_date=date.today().isoformat(),
                effective_date=price_date,
            )
        )
    return prices


def _select_assets(config: AppConfig, ticker: str | None = None, etfs_only: bool = False) -> list[Asset]:
    wanted = normalize_ticker(ticker) if ticker else None
    assets = [asset for asset in list_assets(config.database_path) if asset.active_flag == 1]
    if wanted:
        assets = [asset for asset in assets if asset.ticker == wanted]
    if etfs_only:
        assets = [
            asset
            for asset in assets
            if (asset.asset_type or "").strip().lower() == "etf"
        ]
    return assets


def update_quote_snapshots(
    config: AppConfig,
    ticker: str | None = None,
) -> IbkrQuoteUpdateResult:
    EClient, Contract, EWrapper, import_error = _import_ibapi()
    assets = _select_assets(config, ticker=ticker)
    if import_error:
        return IbkrQuoteUpdateResult(
            tuple(
                IbkrQuoteTickerResult(
                    ticker=asset.ticker,
                    status="error",
                    rows_loaded=0,
                    market_data_type=None,
                    warnings=(f"ibapi_unavailable:{import_error}",),
                )
                for asset in assets
            )
        )

    class QuoteApp(EWrapper, EClient):  # type: ignore[misc, valid-type]
        def __init__(self) -> None:
            EClient.__init__(self, self)
            self.quotes: dict[int, dict[str, float | str]] = {}
            self.market_types: dict[int, str] = {}
            self.errors: dict[int, list[str]] = {}

        def nextValidId(self, orderId: int) -> None:
            self.reqMarketDataType(_market_data_type_code(config))
            for index, selected_asset in enumerate(assets):
                req_id = 7200 + index
                self.reqMktData(
                    req_id,
                    _stock_contract(Contract, selected_asset.ticker),
                    "165,236,293,294,295,318,411,456",
                    False,
                    False,
                    [],
                )

        def marketDataType(self, reqId: int, marketDataType: int) -> None:
            self.market_types[reqId] = MARKET_DATA_TYPE_LABELS.get(
                int(marketDataType), str(marketDataType)
            )

        def tickPrice(self, reqId: int, tickType: int, price: float, attrib: Any) -> None:
            if price is None or price < 0:
                return
            field_by_type = {
                1: "bid",
                2: "ask",
                4: "last",
                6: "high",
                7: "low",
                9: "close",
                14: "open",
                37: "mark",
                66: "bid",
                67: "ask",
                68: "last",
                72: "high",
                73: "low",
                75: "close",
                76: "open",
            }
            field = field_by_type.get(int(tickType))
            if field:
                self.quotes.setdefault(reqId, {})[field] = float(price)
            if int(tickType) >= 66:
                self.market_types[reqId] = "delayed"

        def tickSize(self, reqId: int, tickType: int, size: Any) -> None:
            if int(tickType) in {8, 74}:
                try:
                    self.quotes.setdefault(reqId, {})["volume"] = float(size)
                except Exception:
                    return

        def error(
            self,
            reqId: int,
            errorCode: int,
            errorString: str,
            advancedOrderRejectJson: str = "",
        ) -> None:
            if int(errorCode) == 10167:
                self.market_types[reqId] = "delayed"
                return
            if not _is_info_error(int(errorCode)):
                self.errors.setdefault(reqId, []).append(f"{errorCode}:{errorString}")

    app = QuoteApp()
    try:
        app.connect(config.ibkr_host, config.ibkr_paper_port, clientId=config.ibkr_client_id + 2)
    except Exception as error:
        return IbkrQuoteUpdateResult(
            tuple(
                IbkrQuoteTickerResult(
                    ticker=asset.ticker,
                    status="error",
                    rows_loaded=0,
                    market_data_type=None,
                    warnings=(f"connect_failed:{error}",),
                )
                for asset in assets
            )
        )

    thread = threading.Thread(target=app.run, daemon=True)
    thread.start()
    time.sleep(config.ibkr_timeout_seconds)
    for index, _asset in enumerate(assets):
        try:
            app.cancelMktData(7200 + index)
        except Exception:
            pass
    app.disconnect()
    time.sleep(0.1)

    timestamp = datetime.now().isoformat(timespec="seconds")
    results: list[IbkrQuoteTickerResult] = []
    for index, selected_asset in enumerate(assets):
        req_id = 7200 + index
        payload = app.quotes.get(req_id, {})
        warnings = tuple(app.errors.get(req_id, ()))
        if not payload:
            warnings = warnings + ("no_quote_ticks",)
            insert_data_quality_check(
                config.database_path,
                check_name=f"quote_snapshot:{selected_asset.ticker}:missing",
                status="warning",
                details=", ".join(warnings),
                source="ibkr",
                as_of_date=date.today().isoformat(),
            )
            results.append(
                IbkrQuoteTickerResult(
                    ticker=selected_asset.ticker,
                    status="warning",
                    rows_loaded=0,
                    market_data_type=app.market_types.get(req_id),
                    warnings=warnings,
                )
            )
            continue

        market_data_type = app.market_types.get(req_id, config.ibkr_market_data_type)
        snapshot = QuoteSnapshot(
            ticker=selected_asset.ticker,
            quote_timestamp=timestamp,
            bid=_quote_float(payload, "bid"),
            ask=_quote_float(payload, "ask"),
            last=_quote_float(payload, "last"),
            mark=_quote_float(payload, "mark"),
            open=_quote_float(payload, "open"),
            high=_quote_float(payload, "high"),
            low=_quote_float(payload, "low"),
            close=_quote_float(payload, "close"),
            volume=_quote_float(payload, "volume"),
            market_data_type=market_data_type,
            source="ibkr",
            as_of_date=date.today().isoformat(),
            effective_date=timestamp,
        )
        upsert_quote_snapshot(config.database_path, snapshot)
        results.append(
            IbkrQuoteTickerResult(
                ticker=selected_asset.ticker,
                status="loaded",
                rows_loaded=1,
                market_data_type=market_data_type,
                warnings=warnings,
            )
        )
    return IbkrQuoteUpdateResult(results=tuple(results))


def _quote_float(payload: dict[str, float | str], key: str) -> float | None:
    value = payload.get(key)
    return float(value) if isinstance(value, int | float) else None


def update_etf_navs_from_ibkr(
    config: AppConfig,
    ticker: str | None = None,
) -> IbkrEtfNavUpdateResult:
    EClient, Contract, EWrapper, import_error = _import_ibapi()
    assets = _select_assets(config, ticker=ticker, etfs_only=True)
    if import_error:
        return IbkrEtfNavUpdateResult(
            tuple(
                IbkrEtfNavTickerResult(
                    ticker=asset.ticker,
                    status="error",
                    rows_loaded=0,
                    nav_per_share=None,
                    warnings=(f"ibapi_unavailable:{import_error}",),
                )
                for asset in assets
            )
        )

    class NavApp(EWrapper, EClient):  # type: ignore[misc, valid-type]
        def __init__(self) -> None:
            EClient.__init__(self, self)
            self.navs: dict[int, float] = {}
            self.market_prices: dict[int, float] = {}
            self.errors: dict[int, list[str]] = {}

        def nextValidId(self, orderId: int) -> None:
            self.reqMarketDataType(_market_data_type_code(config))
            for index, selected_asset in enumerate(assets):
                req_id = 7300 + index
                self.reqMktData(
                    req_id,
                    _stock_contract(Contract, selected_asset.ticker),
                    "577,614,623",
                    False,
                    False,
                    [],
                )

        def tickPrice(self, reqId: int, tickType: int, price: float, attrib: Any) -> None:
            if price is None or price <= 0:
                return
            if int(tickType) in {92, 93, 96, 97, 98, 99}:
                self.navs[reqId] = float(price)
            elif int(tickType) in {4, 37, 68}:
                self.market_prices[reqId] = float(price)

        def error(
            self,
            reqId: int,
            errorCode: int,
            errorString: str,
            advancedOrderRejectJson: str = "",
        ) -> None:
            if int(errorCode) == 10167:
                return
            if not _is_info_error(int(errorCode)):
                self.errors.setdefault(reqId, []).append(f"{errorCode}:{errorString}")

    app = NavApp()
    try:
        app.connect(config.ibkr_host, config.ibkr_paper_port, clientId=config.ibkr_client_id + 3)
    except Exception as error:
        return IbkrEtfNavUpdateResult(
            tuple(
                IbkrEtfNavTickerResult(
                    ticker=asset.ticker,
                    status="error",
                    rows_loaded=0,
                    nav_per_share=None,
                    warnings=(f"connect_failed:{error}",),
                )
                for asset in assets
            )
        )

    thread = threading.Thread(target=app.run, daemon=True)
    thread.start()
    time.sleep(config.ibkr_timeout_seconds)
    for index, _asset in enumerate(assets):
        try:
            app.cancelMktData(7300 + index)
        except Exception:
            pass
    app.disconnect()
    time.sleep(0.1)

    nav_date = date.today().isoformat()
    loaded_tickers: list[str] = []
    results: list[IbkrEtfNavTickerResult] = []
    for index, selected_asset in enumerate(assets):
        req_id = 7300 + index
        nav_value = app.navs.get(req_id)
        warnings = tuple(app.errors.get(req_id, ()))
        if nav_value is None:
            warnings = warnings + ("no_etf_nav_ticks",)
            insert_data_quality_check(
                config.database_path,
                check_name=f"etf_nav:{selected_asset.ticker}:ibkr_missing",
                status="warning",
                details=", ".join(warnings),
                source="ibkr",
                as_of_date=nav_date,
            )
            results.append(
                IbkrEtfNavTickerResult(
                    ticker=selected_asset.ticker,
                    status="warning",
                    rows_loaded=0,
                    nav_per_share=None,
                    warnings=warnings,
                )
            )
            continue

        price_feature = latest_price_feature(config.database_path, selected_asset.ticker)
        market_price = app.market_prices.get(req_id)
        if market_price is None and price_feature is not None:
            market_price = price_feature.current_price
        premium_discount = (
            market_price / nav_value - 1
            if market_price is not None and nav_value > 0
            else None
        )
        upsert_etf_nav(
            config.database_path,
            EtfNav(
                ticker=selected_asset.ticker,
                nav_date=nav_date,
                nav_per_share=nav_value,
                market_price=market_price,
                premium_discount=premium_discount,
                source="ibkr_etf_nav",
                as_of_date=nav_date,
                effective_date=nav_date,
            ),
        )
        loaded_tickers.append(selected_asset.ticker)
        results.append(
            IbkrEtfNavTickerResult(
                ticker=selected_asset.ticker,
                status="loaded",
                rows_loaded=1,
                nav_per_share=nav_value,
                warnings=warnings,
            )
        )

    if loaded_tickers:
        refresh_etf_features(config.database_path, tuple(loaded_tickers))
    return IbkrEtfNavUpdateResult(results=tuple(results))


def fetch_ibkr_option_chain_snapshots(
    config: AppConfig,
    assets: tuple[Asset, ...],
    force_refresh: bool = False,
) -> IbkrOptionChainFetchResult:
    del force_refresh
    EClient, Contract, EWrapper, import_error = _import_ibapi()
    if import_error:
        return IbkrOptionChainFetchResult(
            tuple(
                IbkrOptionChainTickerResult(
                    ticker=asset.ticker,
                    status="warning",
                    rows_loaded=0,
                    selected_expirations=0,
                    selected_strikes=0,
                    snapshots=(),
                    warnings=(f"ibapi_unavailable:{import_error}", "ibkr_unavailable"),
                )
                for asset in assets
            )
        )

    from .options import select_option_expirations, select_option_strikes

    class OptionChainApp(EWrapper, EClient):  # type: ignore[misc, valid-type]
        def __init__(self) -> None:
            EClient.__init__(self, self)
            self.contract_details: dict[int, list[Any]] = {}
            self.secdef_done: set[int] = set()
            self.expirations: dict[int, set[str]] = {}
            self.strikes: dict[int, set[float]] = {}
            self.quotes: dict[int, dict[str, float]] = {}
            self.errors: dict[int, list[str]] = {}
            self.started = False

        def nextValidId(self, orderId: int) -> None:
            self.started = True
            self.reqMarketDataType(_market_data_type_code(config))
            for index, selected_asset in enumerate(assets):
                req_id = 8200 + index
                self.reqContractDetails(req_id, _stock_contract(Contract, selected_asset.ticker))

        def contractDetails(self, reqId: int, contractDetails: Any) -> None:
            self.contract_details.setdefault(reqId, []).append(contractDetails)

        def contractDetailsEnd(self, reqId: int) -> None:
            details = self.contract_details.get(reqId, [])
            if not details:
                self.secdef_done.add(reqId)
                return
            selected_contract = getattr(details[0], "contract", None)
            con_id = getattr(selected_contract, "conId", None)
            symbol = getattr(selected_contract, "symbol", None)
            if not con_id or not symbol:
                self.secdef_done.add(reqId)
                return
            self.reqSecDefOptParams(reqId, str(symbol), "", "STK", int(con_id))

        def securityDefinitionOptionParameter(
            self,
            reqId: int,
            exchange: str,
            underlyingConId: int,
            tradingClass: str,
            multiplier: str,
            expirations: set[str],
            strikes: set[float],
        ) -> None:
            del underlyingConId, tradingClass, multiplier
            requested_exchange = config.options_ibkr_exchange.upper()
            if exchange and exchange.upper() not in {requested_exchange, "SMART"}:
                return
            self.expirations.setdefault(reqId, set()).update(str(item) for item in expirations)
            self.strikes.setdefault(reqId, set()).update(float(item) for item in strikes)

        def securityDefinitionOptionParameterEnd(self, reqId: int) -> None:
            self.secdef_done.add(reqId)

        def marketDataType(self, reqId: int, marketDataType: int) -> None:
            if int(marketDataType) >= 3:
                self.quotes.setdefault(reqId, {})["delayed_market_data"] = 1.0

        def tickPrice(self, reqId: int, tickType: int, price: float, attrib: Any) -> None:
            del attrib
            if price is None or price < 0:
                return
            field_by_type = {
                1: "bid",
                2: "ask",
                4: "last",
                37: "mark",
                66: "bid",
                67: "ask",
                68: "last",
            }
            field = field_by_type.get(int(tickType))
            if field:
                self.quotes.setdefault(reqId, {})[field] = float(price)

        def tickSize(self, reqId: int, tickType: int, size: Any) -> None:
            try:
                numeric = float(size)
            except Exception:
                return
            if int(tickType) in {8, 74}:
                self.quotes.setdefault(reqId, {})["volume"] = numeric
            if int(tickType) in {27, 28, 86, 87}:
                self.quotes.setdefault(reqId, {})["open_interest"] = numeric

        def tickOptionComputation(
            self,
            reqId: int,
            tickType: int,
            tickAttrib: int,
            impliedVol: float,
            delta: float,
            optPrice: float,
            pvDividend: float,
            gamma: float,
            vega: float,
            theta: float,
            undPrice: float,
        ) -> None:
            del tickType, tickAttrib, optPrice, pvDividend, undPrice
            payload = self.quotes.setdefault(reqId, {})
            for key, value in (
                ("implied_volatility", impliedVol),
                ("delta", delta),
                ("gamma", gamma),
                ("vega", vega),
                ("theta", theta),
            ):
                try:
                    if value is not None and float(value) > -1e10:
                        payload[key] = float(value)
                except Exception:
                    continue

        def error(
            self,
            reqId: int,
            errorCode: int,
            errorString: str,
            advancedOrderRejectJson: str = "",
        ) -> None:
            del advancedOrderRejectJson
            code = int(errorCode)
            if code == 10167:
                return
            if _is_info_error(code):
                return
            warning = f"{code}:{errorString}"
            if code in {354, 10168, 10186}:
                warning = f"ibkr_option_subscription_missing:{warning}"
            self.errors.setdefault(reqId, []).append(warning)

    app = OptionChainApp()
    try:
        app.connect(config.ibkr_host, config.ibkr_paper_port, clientId=config.ibkr_client_id + 4)
    except Exception as error:
        return IbkrOptionChainFetchResult(
            tuple(
                IbkrOptionChainTickerResult(
                    ticker=asset.ticker,
                    status="warning",
                    rows_loaded=0,
                    selected_expirations=0,
                    selected_strikes=0,
                    snapshots=(),
                    warnings=(f"connect_failed:{error}", "ibkr_unavailable"),
                )
                for asset in assets
            )
        )

    thread = threading.Thread(target=app.run, daemon=True)
    thread.start()
    deadline = time.time() + config.ibkr_timeout_seconds
    while time.time() < deadline and not app.started:
        time.sleep(0.1)
    expected_req_ids = {8200 + index for index, _asset in enumerate(assets)}
    while time.time() < deadline and not expected_req_ids.issubset(app.secdef_done):
        time.sleep(0.1)

    selected_contracts: dict[int, tuple[Asset, str, float]] = {}
    results_by_ticker: dict[str, dict[str, Any]] = {
        asset.ticker: {
            "snapshots": [],
            "warnings": [],
            "selected_expirations": 0,
            "selected_strikes": 0,
        }
        for asset in assets
    }
    quote_req_id = 8400
    for index, asset in enumerate(assets):
        req_id = 8200 + index
        ticker_warnings = results_by_ticker[asset.ticker]["warnings"]
        ticker_warnings.extend(app.errors.get(req_id, ()))
        if not app.contract_details.get(req_id):
            ticker_warnings.append("no_ibkr_underlying_contract")
            continue
        price_feature = latest_price_feature(config.database_path, asset.ticker)
        current_price = price_feature.current_price if price_feature else None
        if current_price is None or current_price <= 0:
            ticker_warnings.append("stale_underlying_price")
            continue
        expirations = select_option_expirations(tuple(app.expirations.get(req_id, ())), config)
        strikes = select_option_strikes(
            tuple(app.strikes.get(req_id, ())),
            current_price,
            config,
            range_level=None,
        )
        results_by_ticker[asset.ticker]["selected_expirations"] = len(expirations)
        results_by_ticker[asset.ticker]["selected_strikes"] = len(strikes)
        if len(app.expirations.get(req_id, ())) > len(expirations) or len(app.strikes.get(req_id, ())) > len(strikes):
            ticker_warnings.append("option_chain_budget_exhausted")
        if not expirations:
            ticker_warnings.append("no_expirations_in_dte_window")
            continue
        if not strikes:
            ticker_warnings.append("no_strikes_in_window")
            continue
        for expiration in expirations:
            expiration_compact = expiration.replace("-", "")
            for strike in strikes:
                contract = Contract()
                contract.symbol = _ibkr_symbol(asset.ticker)
                contract.secType = "OPT"
                contract.exchange = config.options_ibkr_exchange
                contract.currency = config.options_ibkr_currency
                contract.lastTradeDateOrContractMonth = expiration_compact
                contract.strike = float(strike)
                contract.right = "P" if config.options_fetch_puts_only else "P"
                contract.multiplier = "100"
                selected_contracts[quote_req_id] = (asset, expiration, float(strike))
                try:
                    app.reqMktData(quote_req_id, contract, "100,101,104,106", True, False, [])
                except Exception as error:
                    ticker_warnings.append(f"option_quote_request_failed:{error}")
                quote_req_id += 1

    time.sleep(config.ibkr_timeout_seconds)
    for req_id in selected_contracts:
        try:
            app.cancelMktData(req_id)
        except Exception:
            pass
    app.disconnect()
    time.sleep(0.1)

    timestamp = datetime.now().isoformat(timespec="seconds")
    as_of_date = date.today().isoformat()
    for req_id, (asset, expiration, strike) in selected_contracts.items():
        payload = app.quotes.get(req_id, {})
        warnings = results_by_ticker[asset.ticker]["warnings"]
        warnings.extend(app.errors.get(req_id, ()))
        bid = payload.get("bid")
        ask = payload.get("ask")
        if bid is None or ask is None or bid <= 0 or ask <= 0:
            warnings.append("missing_option_bid_ask")
            continue
        results_by_ticker[asset.ticker]["snapshots"].append(
            OptionChainSnapshot(
                ticker=asset.ticker,
                snapshot_timestamp=timestamp,
                expiration_date=expiration,
                option_type="put",
                strike=round(float(strike), 4),
                bid=float(bid),
                ask=float(ask),
                last=_quote_float(payload, "last"),
                mark=_quote_float(payload, "mark"),
                volume=_quote_float(payload, "volume"),
                open_interest=_quote_float(payload, "open_interest"),
                implied_volatility=_quote_float(payload, "implied_volatility"),
                delta=_quote_float(payload, "delta"),
                gamma=_quote_float(payload, "gamma"),
                theta=_quote_float(payload, "theta"),
                vega=_quote_float(payload, "vega"),
                source="ibkr_option_chain",
                source_url=None,
                as_of_date=as_of_date,
                effective_date=timestamp,
            )
        )

    results: list[IbkrOptionChainTickerResult] = []
    for asset in assets:
        payload = results_by_ticker[asset.ticker]
        snapshots = tuple(payload["snapshots"])
        warnings = tuple(dict.fromkeys(payload["warnings"]))
        if not snapshots and not warnings:
            warnings = ("no_option_quotes",)
        status = "loaded" if snapshots else "warning"
        _write_option_chain_cache_metadata(
            config,
            asset.ticker,
            {
                "ticker": asset.ticker,
                "timestamp": timestamp,
                "rows_loaded": len(snapshots),
                "warnings": list(warnings),
                "source": "ibkr_option_chain",
            },
        )
        results.append(
            IbkrOptionChainTickerResult(
                ticker=asset.ticker,
                status=status,
                rows_loaded=len(snapshots),
                selected_expirations=int(payload["selected_expirations"]),
                selected_strikes=int(payload["selected_strikes"]),
                snapshots=snapshots,
                warnings=warnings,
            )
        )
    return IbkrOptionChainFetchResult(results=tuple(results))


def _write_option_chain_cache_metadata(
    config: AppConfig,
    ticker: str,
    payload: dict[str, Any],
) -> None:
    try:
        cache_dir = config.options_chain_cache_dir / normalize_ticker(ticker)
        cache_dir.mkdir(parents=True, exist_ok=True)
        timestamp = str(payload.get("timestamp") or datetime.now().isoformat(timespec="seconds"))
        filename = timestamp.replace(":", "").replace("-", "").replace("T", "_")
        (cache_dir / f"{filename}.json").write_text(
            json.dumps(payload, indent=2, sort_keys=True),
            encoding="utf-8",
        )
    except Exception:
        return


def probe_ibkr_ticker(config: AppConfig, ticker: str) -> IbkrTickerProbeResult:
    normalized = normalize_ticker(ticker)
    status = check_ibkr_status(config)
    if not status.connected:
        return IbkrTickerProbeResult(
            ticker=normalized,
            status="error",
            contract_found=False,
            historical_rows=0,
            quote_loaded=False,
            etf_nav_loaded=False,
            warnings=status.warnings or ("ibkr_not_connected",),
        )

    asset = Asset(ticker=normalized, asset_type="etf" if normalized in {"SPY", "QQQ"} else "equity")
    warnings: list[str] = list(status.warnings)
    historical_rows = 0
    try:
        historical_rows = len(fetch_ibkr_historical_prices(config, asset))
    except ValueError as error:
        warnings.append(f"historical_error:{error}")

    quote_result = update_quote_snapshots(config, normalized)
    quote_loaded = any(result.rows_loaded > 0 for result in quote_result.results)
    for result in quote_result.results:
        warnings.extend(result.warnings)

    nav_loaded = False
    if asset.asset_type == "etf":
        nav_result = update_etf_navs_from_ibkr(config, normalized)
        nav_loaded = any(result.rows_loaded > 0 for result in nav_result.results)
        for result in nav_result.results:
            warnings.extend(result.warnings)

    return IbkrTickerProbeResult(
        ticker=normalized,
        status="ok" if quote_loaded or historical_rows else "warning",
        contract_found=bool(historical_rows or quote_loaded),
        historical_rows=historical_rows,
        quote_loaded=quote_loaded,
        etf_nav_loaded=nav_loaded,
        warnings=tuple(warnings),
    )
