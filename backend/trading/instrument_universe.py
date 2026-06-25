from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Mapping


class InstrumentUniverseError(RuntimeError):
    """Fail-closed exception for tradable instrument universe discovery and filtering."""


@dataclass(frozen=True)
class TradableInstrument:
    symbol: str
    display_name: str
    asset_class: str
    broker: str
    tradable: bool
    paper_supported: bool
    live_supported: bool
    exchange: str
    currency: str
    min_order_size: float
    max_order_size: float
    tick_size: float
    last_updated: str
    status: str
    metadata: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class InstrumentUniverse:
    """Canonical tradable instrument registry for CSS trade-tab selection."""

    _SUPPORTED_ASSET_CLASSES = {"CRYPTO", "FX", "OPTIONS", "FUTURES", "EQUITIES"}

    _KNOWN_COINBASE_SYMBOLS = (
        ("BTC-USD", "Bitcoin / US Dollar"),
        ("ETH-USD", "Ethereum / US Dollar"),
        ("SOL-USD", "Solana / US Dollar"),
        ("LTC-USD", "Litecoin / US Dollar"),
    )

    _KNOWN_OANDA_SYMBOLS = (
        ("EUR_USD", "Euro / US Dollar"),
        ("USD_JPY", "US Dollar / Japanese Yen"),
        ("GBP_USD", "British Pound / US Dollar"),
        ("AUD_USD", "Australian Dollar / US Dollar"),
    )

    _EQUITIES_PLACEHOLDERS = (
        ("AAPL", "Apple Inc."),
        ("MSFT", "Microsoft Corp."),
        ("SPY", "SPDR S&P 500 ETF"),
    )

    _FALLBACK_PAPER_SAFE = (
        ("BTC-USD", "Bitcoin / US Dollar", "CRYPTO", "coinbase", "COINBASE", "USD", 0.0001, 1000.0, 0.01),
        ("ETH-USD", "Ethereum / US Dollar", "CRYPTO", "coinbase", "COINBASE", "USD", 0.001, 5000.0, 0.01),
        ("EUR_USD", "Euro / US Dollar", "FX", "oanda", "OANDA", "USD", 1.0, 1000000.0, 0.00001),
        ("GBP_USD", "British Pound / US Dollar", "FX", "oanda", "OANDA", "USD", 1.0, 1000000.0, 0.00001),
        ("SPY-C-500", "SPY Call 500", "OPTIONS", "sim_options", "OPRA", "USD", 1.0, 1000.0, 0.01),
        ("ES", "E-mini S&P 500", "FUTURES", "sim_futures", "CME", "USD", 1.0, 500.0, 0.25),
        ("AAPL", "Apple Inc.", "EQUITIES", "alpaca", "NASDAQ", "USD", 1.0, 10000.0, 0.01),
    )

    def __init__(self) -> None:
        self._instruments: list[TradableInstrument] = []
        self.refresh()

    def refresh(self) -> None:
        now = datetime.now(timezone.utc).isoformat()
        discovered: list[TradableInstrument] = []

        try:
            discovered.extend(self._discover_option_contracts(now))
            discovered.extend(self._discover_futures_contracts(now))
            discovered.extend(self._discover_broker_symbols(now))
            discovered.extend(self._discover_equities_placeholders(now))
        except Exception:
            discovered = []

        if not discovered:
            discovered = self._fallback_instruments(now)

        self._instruments = self._dedupe_and_sort(discovered)

    def all_instruments(self) -> list[dict[str, Any]]:
        return [item.to_dict() for item in self._instruments]

    def instruments_by_asset_class(self, asset_class: str) -> list[dict[str, Any]]:
        normalized = str(asset_class or "").strip().upper()
        if normalized not in self._SUPPORTED_ASSET_CLASSES:
            raise InstrumentUniverseError(f"unsupported asset class: {asset_class}")
        return [item.to_dict() for item in self._instruments if item.asset_class == normalized]

    def instruments_by_broker(self, broker: str) -> list[dict[str, Any]]:
        normalized = str(broker or "").strip().lower()
        if not normalized:
            raise InstrumentUniverseError("broker must be non-empty")
        return [item.to_dict() for item in self._instruments if item.broker.lower() == normalized]

    def tradable_paper_instruments(self) -> list[dict[str, Any]]:
        return [
            item.to_dict()
            for item in self._instruments
            if item.tradable and item.paper_supported
        ]

    def tradeable_symbols(
        self,
        mode: str = "paper",
        asset_class: str | None = None,
        broker: str | None = None,
    ) -> list[TradableInstrument]:
        mode_value = self._normalize_mode(mode)
        wanted_asset = str(asset_class or "").strip().upper()
        wanted_broker = str(broker or "").strip().lower()

        if wanted_asset and wanted_asset not in self._SUPPORTED_ASSET_CLASSES:
            raise InstrumentUniverseError(f"unsupported asset class: {asset_class}")

        rows: list[TradableInstrument] = []
        for item in self._instruments:
            if not self._is_tradeable_for_mode(item=item, mode=mode_value):
                continue

            if wanted_asset and item.asset_class != wanted_asset:
                continue

            if wanted_broker and item.broker.lower() != wanted_broker:
                continue

            rows.append(item)

        return sorted(rows, key=lambda row: (row.asset_class, row.broker, row.symbol))

    def build_feed(self) -> dict[str, Any]:
        all_rows = self.all_instruments()
        brokers = sorted({row["broker"] for row in all_rows})
        asset_classes = sorted({row["asset_class"] for row in all_rows})

        return {
            "all_instruments": all_rows,
            "asset_classes": asset_classes,
            "brokers": brokers,
            "instruments_by_asset_class": {
                asset_class: self.instruments_by_asset_class(asset_class)
                for asset_class in asset_classes
            },
            "instruments_by_broker": {
                broker: self.instruments_by_broker(broker)
                for broker in brokers
            },
            "tradable_paper_instruments": self.tradable_paper_instruments(),
        }

    @staticmethod
    def _normalize_mode(mode: str) -> str:
        normalized = str(mode or "paper").strip().lower()
        if normalized in {"paper", "practice", "sim", "simulated", "sandbox", "safe"}:
            return "paper"
        if normalized == "live":
            return "live"
        raise InstrumentUniverseError(f"unsupported mode: {mode}")

    @staticmethod
    def _is_tradeable_for_mode(*, item: TradableInstrument, mode: str) -> bool:
        status = str(item.status or "").strip().upper()
        metadata = item.metadata if isinstance(item.metadata, Mapping) else {}
        fail_closed_discovery = bool(metadata.get("fail_closed", False))

        if fail_closed_discovery:
            return False

        if status not in {"ACTIVE", "PAPER_ACTIVE"}:
            return False

        if not item.tradable:
            return False

        if mode == "paper":
            return bool(item.paper_supported)

        return bool(item.live_supported)

    def _discover_option_contracts(self, now: str) -> Iterable[TradableInstrument]:
        from backend.app.options.options_contract_registry import SUPPORTED_OPTION_UNDERLYINGS, build_option_symbol

        rows: list[TradableInstrument] = []
        for underlying, payload in SUPPORTED_OPTION_UNDERLYINGS.items():
            symbol = build_option_symbol(
                underlying=underlying,
                option_type="CALL",
                strike=100.0,
                expiry="TBD",
            )
            rows.append(
                TradableInstrument(
                    symbol=symbol,
                    display_name=f"{underlying} Call 100",
                    asset_class="OPTIONS",
                    broker="sim_options",
                    tradable=True,
                    paper_supported=True,
                    live_supported=False,
                    exchange=str(payload.get("exchange", "OPRA")),
                    currency=str(payload.get("currency", "USD")),
                    min_order_size=1.0,
                    max_order_size=1000.0,
                    tick_size=0.01,
                    last_updated=now,
                    status="ACTIVE",
                    metadata={
                        "source": "options_contract_registry",
                        "underlying": underlying,
                        "option_type": "CALL",
                        "live_enabled": False,
                    },
                )
            )
        return rows

    def _discover_futures_contracts(self, now: str) -> Iterable[TradableInstrument]:
        from backend.app.futures.futures_contract_registry import FUTURES_CONTRACTS

        rows: list[TradableInstrument] = []
        for symbol, contract in FUTURES_CONTRACTS.items():
            rows.append(
                TradableInstrument(
                    symbol=symbol,
                    display_name=contract.name,
                    asset_class="FUTURES",
                    broker="sim_futures",
                    tradable=True,
                    paper_supported=True,
                    live_supported=bool(contract.live_enabled),
                    exchange=contract.exchange,
                    currency=contract.currency,
                    min_order_size=1.0,
                    max_order_size=500.0,
                    tick_size=float(contract.tick_size),
                    last_updated=now,
                    status="ACTIVE" if contract.live_enabled else "PAPER_ONLY",
                    metadata={
                        "source": "futures_contract_registry",
                        "margin_class": contract.margin_class,
                        "notes": contract.notes,
                    },
                )
            )
        return rows

    def _discover_broker_symbols(self, now: str) -> Iterable[TradableInstrument]:
        from backend.app.brokers.broker_registry import BROKER_REGISTRY

        rows: list[TradableInstrument] = []
        for broker_name, spec in BROKER_REGISTRY.items():
            if broker_name == "coinbase":
                for symbol, display_name in self._KNOWN_COINBASE_SYMBOLS:
                    rows.append(
                        TradableInstrument(
                            symbol=symbol,
                            display_name=display_name,
                            asset_class="CRYPTO",
                            broker=broker_name,
                            tradable=True,
                            paper_supported=bool(spec.supports_paper),
                            live_supported=bool(spec.supports_live),
                            exchange="COINBASE",
                            currency="USD",
                            min_order_size=0.0001,
                            max_order_size=1000.0,
                            tick_size=0.01,
                            last_updated=now,
                            status="ACTIVE",
                            metadata={
                                "source": "broker_registry+coinbase_known_symbols",
                            },
                        )
                    )

            if broker_name == "oanda":
                for symbol, display_name in self._KNOWN_OANDA_SYMBOLS:
                    rows.append(
                        TradableInstrument(
                            symbol=symbol,
                            display_name=display_name,
                            asset_class="FX",
                            broker=broker_name,
                            tradable=True,
                            paper_supported=bool(spec.supports_paper),
                            live_supported=bool(spec.supports_live),
                            exchange="OANDA",
                            currency="USD",
                            min_order_size=1.0,
                            max_order_size=1000000.0,
                            tick_size=0.00001,
                            last_updated=now,
                            status="ACTIVE",
                            metadata={
                                "source": "broker_registry+oanda_known_symbols",
                            },
                        )
                    )

        return rows

    def _discover_equities_placeholders(self, now: str) -> Iterable[TradableInstrument]:
        rows: list[TradableInstrument] = []
        for symbol, display_name in self._EQUITIES_PLACEHOLDERS:
            rows.append(
                TradableInstrument(
                    symbol=symbol,
                    display_name=display_name,
                    asset_class="EQUITIES",
                    broker="alpaca",
                    tradable=False,
                    paper_supported=True,
                    live_supported=False,
                    exchange="NASDAQ",
                    currency="USD",
                    min_order_size=1.0,
                    max_order_size=10000.0,
                    tick_size=0.01,
                    last_updated=now,
                    status="PLACEHOLDER_UNVERIFIED",
                    metadata={
                        "source": "safe_placeholder",
                        "reason": "symbol listed for selector convenience; execution remains gate-controlled",
                    },
                )
            )
        return rows

    def _fallback_instruments(self, now: str) -> list[TradableInstrument]:
        rows: list[TradableInstrument] = []
        for (
            symbol,
            display_name,
            asset_class,
            broker,
            exchange,
            currency,
            min_order_size,
            max_order_size,
            tick_size,
        ) in self._FALLBACK_PAPER_SAFE:
            rows.append(
                TradableInstrument(
                    symbol=symbol,
                    display_name=display_name,
                    asset_class=asset_class,
                    broker=broker,
                    tradable=False,
                    paper_supported=True,
                    live_supported=False,
                    exchange=exchange,
                    currency=currency,
                    min_order_size=min_order_size,
                    max_order_size=max_order_size,
                    tick_size=tick_size,
                    last_updated=now,
                    status="DISCOVERY_FALLBACK",
                    metadata={
                        "source": "static_fallback",
                        "fail_closed": True,
                    },
                )
            )
        return rows

    @staticmethod
    def _dedupe_and_sort(instruments: list[TradableInstrument]) -> list[TradableInstrument]:
        deduped: Dict[str, TradableInstrument] = {}
        for item in instruments:
            key = f"{item.broker.lower()}::{item.symbol.upper()}::{item.asset_class}"
            deduped[key] = item

        return sorted(
            deduped.values(),
            key=lambda item: (item.asset_class, item.broker, item.symbol),
        )
