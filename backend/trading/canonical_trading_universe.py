from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any


class CanonicalTradingUniverseError(RuntimeError):
    """Fail-closed exception for canonical universe operations."""


@dataclass(frozen=True)
class CanonicalInstrument:
    symbol: str
    display_name: str
    asset_class: str
    broker: str
    paper_supported: bool
    live_supported: bool
    enabled: bool
    priority: int
    default_strategy: str
    risk_profile: str
    minimum_confidence: float
    preferred_timeframes: list[str]
    tags: list[str]
    supported_expiries: list[str] = field(default_factory=list)
    default_expiry: str = ""
    option_types: list[str] = field(default_factory=list)
    supported_strikes: list[str] = field(default_factory=list)
    strike_policy: str = ""
    contract_style: str = ""
    supported_contract_months: list[str] = field(default_factory=list)
    default_contract: str = ""
    roll_policy: str = ""
    contract_size: float = 0.0
    tick_value: float = 0.0
    expiry_source: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class CanonicalTradingUniverse:
    """Canonical curated trading universe for the CSS decision console."""

    _ALLOWED_ASSET_CLASSES = {"CRYPTO", "FOREX", "INDICES", "FUTURES", "OPTIONS"}

    def __init__(self) -> None:
        self._instruments = self._build_registry()

    def all_instruments(self, *, mode: str = "paper") -> list[dict[str, Any]]:
        mode_value = self._normalize_mode(mode)
        rows = [self._serialize(item, mode=mode_value) for item in self._instruments]
        return sorted(rows, key=lambda row: (row["asset_class"], -int(row["priority"]), row["symbol"]))

    def grouped(self, *, mode: str = "paper") -> dict[str, list[dict[str, Any]]]:
        mode_value = self._normalize_mode(mode)
        groups = {
            "CRYPTO": [],
            "FOREX": [],
            "INDICES": [],
            "FUTURES": [],
            "OPTIONS": [],
        }
        for item in self._instruments:
            groups[item.asset_class].append(self._serialize(item, mode=mode_value))

        return {
            asset_class: sorted(items, key=lambda row: (-int(row["priority"]), row["symbol"]))
            for asset_class, items in groups.items()
        }

    def by_symbol(self, symbol: str, *, asset_class: str | None = None, mode: str = "paper") -> dict[str, Any] | None:
        wanted_symbol = str(symbol or "").strip().upper()
        wanted_asset = str(asset_class or "").strip().upper()
        if not wanted_symbol:
            raise CanonicalTradingUniverseError("symbol must be non-empty")
        if wanted_asset and wanted_asset not in self._ALLOWED_ASSET_CLASSES:
            raise CanonicalTradingUniverseError(f"unsupported asset class: {asset_class}")

        mode_value = self._normalize_mode(mode)
        for item in self._instruments:
            if item.symbol.upper() != wanted_symbol:
                continue
            if wanted_asset and item.asset_class != wanted_asset:
                continue
            return self._serialize(item, mode=mode_value)
        return None

    def selectable_symbols(self, *, mode: str = "paper") -> list[str]:
        mode_value = self._normalize_mode(mode)
        selected = [
            item.symbol
            for item in self._instruments
            if self._serialize(item, mode=mode_value)["selectable"]
        ]
        return sorted(set(selected))

    def summary(self) -> dict[str, Any]:
        grouped = self.grouped(mode="paper")
        return {
            "total": len(self._instruments),
            "groups": {key: len(value) for key, value in grouped.items()},
            "paper_selectable": len(self.selectable_symbols(mode="paper")),
            "live_selectable": len(self.selectable_symbols(mode="live")),
        }

    @staticmethod
    def _normalize_mode(mode: str) -> str:
        normalized = str(mode or "paper").strip().lower()
        if normalized in {"paper", "practice", "sim", "simulated", "safe", "sandbox"}:
            return "paper"
        if normalized == "live":
            return "live"
        raise CanonicalTradingUniverseError(f"unsupported mode: {mode}")

    def _serialize(self, item: CanonicalInstrument, *, mode: str) -> dict[str, Any]:
        supported = item.paper_supported if mode == "paper" else item.live_supported
        selectable = bool(item.enabled and supported)
        unavailable_reason = ""
        if not item.enabled:
            unavailable_reason = "Disabled by fail-closed discovery"
        elif not supported:
            unavailable_reason = f"Unavailable in {mode.upper()} mode"

        payload = item.to_dict()
        min_order_size = self._min_order_size(item)
        tenor_options: list[str] = []
        default_tenor = ""
        metadata_status = "NOT_APPLICABLE"

        if item.asset_class == "OPTIONS":
            tenor_options = list(item.supported_expiries)
            default_tenor = str(item.default_expiry or "")
            metadata_status = "EXPLICIT" if tenor_options and default_tenor else "MISSING"
        elif item.asset_class == "FUTURES":
            tenor_options = list(item.supported_contract_months)
            default_tenor = str(item.default_contract or "")
            metadata_status = "EXPLICIT" if tenor_options and default_tenor else "MISSING"
        payload.update(
            {
                "mode": mode,
                "selectable": selectable,
                "unavailable_reason": unavailable_reason,
                "instrument_id": f"{item.asset_class}:{item.symbol}",
                "min_order_size": min_order_size,
                "default_tenor": default_tenor,
                "tenor_options": tenor_options,
                "metadata_status": metadata_status,
                "last_updated": datetime.now(timezone.utc).isoformat(),
            }
        )
        return payload

    @staticmethod
    def _min_order_size(item: CanonicalInstrument) -> float:
        if item.asset_class == "CRYPTO":
            return 0.001
        return 1.0

    def _build_registry(self) -> list[CanonicalInstrument]:
        return [
            # CRYPTO
            self._item("BTC-USD", "Bitcoin / US Dollar", "CRYPTO", "coinbase", True, True, True, 100, "momentum_breakout", "balanced", 0.62, ["5m", "15m", "1h"], ["core", "liquid"]),
            self._item("ETH-USD", "Ethereum / US Dollar", "CRYPTO", "coinbase", True, True, True, 95, "momentum_breakout", "balanced", 0.61, ["5m", "15m", "1h"], ["core", "liquid"]),
            self._item("SOL-USD", "Solana / US Dollar", "CRYPTO", "coinbase", True, True, True, 88, "momentum_breakout", "aggressive", 0.64, ["5m", "15m"], ["high_beta"]),
            self._item("XRP-USD", "XRP / US Dollar", "CRYPTO", "coinbase", True, True, True, 80, "volatility_reversion", "balanced", 0.6, ["5m", "15m"], ["alt"]),
            self._item("DOGE-USD", "Dogecoin / US Dollar", "CRYPTO", "coinbase", True, True, False, 72, "volatility_reversion", "aggressive", 0.68, ["5m"], ["alt", "fail_closed"]),
            self._item("LTC-USD", "Litecoin / US Dollar", "CRYPTO", "coinbase", True, True, True, 76, "momentum_breakout", "balanced", 0.6, ["5m", "15m"], ["alt"]),
            self._item("BCH-USD", "Bitcoin Cash / US Dollar", "CRYPTO", "coinbase", True, True, True, 70, "volatility_reversion", "aggressive", 0.66, ["5m", "15m"], ["alt"]),
            # FOREX
            self._item("EUR_USD", "Euro / US Dollar", "FOREX", "oanda", True, True, True, 100, "macro_trend", "conservative", 0.58, ["15m", "1h", "4h"], ["major"]),
            self._item("GBP_USD", "British Pound / US Dollar", "FOREX", "oanda", True, True, True, 97, "macro_trend", "balanced", 0.59, ["15m", "1h", "4h"], ["major"]),
            self._item("USD_JPY", "US Dollar / Japanese Yen", "FOREX", "oanda", True, True, True, 96, "macro_trend", "balanced", 0.58, ["15m", "1h", "4h"], ["major"]),
            self._item("USD_CAD", "US Dollar / Canadian Dollar", "FOREX", "oanda", True, True, True, 86, "macro_trend", "balanced", 0.57, ["15m", "1h"], ["major"]),
            self._item("USD_CHF", "US Dollar / Swiss Franc", "FOREX", "oanda", True, True, True, 84, "macro_trend", "conservative", 0.57, ["15m", "1h"], ["major"]),
            self._item("AUD_USD", "Australian Dollar / US Dollar", "FOREX", "oanda", True, True, True, 82, "macro_trend", "balanced", 0.58, ["15m", "1h"], ["major"]),
            self._item("NZD_USD", "New Zealand Dollar / US Dollar", "FOREX", "oanda", True, True, True, 78, "macro_trend", "balanced", 0.58, ["15m", "1h"], ["major"]),
            self._item("EUR_GBP", "Euro / British Pound", "FOREX", "oanda", True, True, True, 77, "mean_reversion", "balanced", 0.6, ["15m", "1h"], ["cross"]),
            self._item("EUR_JPY", "Euro / Japanese Yen", "FOREX", "oanda", True, True, True, 79, "macro_trend", "aggressive", 0.61, ["15m", "1h"], ["cross"]),
            self._item("GBP_JPY", "British Pound / Japanese Yen", "FOREX", "oanda", True, True, True, 75, "macro_trend", "aggressive", 0.63, ["15m", "1h"], ["cross"]),
            # INDICES
            self._item("SPY", "SPDR S&P 500 ETF", "INDICES", "alpaca", True, False, True, 99, "index_momentum", "balanced", 0.6, ["15m", "1h", "1d"], ["index"]),
            self._item("QQQ", "Invesco QQQ Trust", "INDICES", "alpaca", True, False, True, 98, "index_momentum", "aggressive", 0.61, ["15m", "1h", "1d"], ["index", "tech"]),
            self._item("DIA", "SPDR Dow Jones ETF", "INDICES", "alpaca", True, False, True, 90, "index_reversion", "conservative", 0.57, ["15m", "1h", "1d"], ["index"]),
            self._item("IWM", "iShares Russell 2000 ETF", "INDICES", "alpaca", True, False, True, 89, "index_momentum", "aggressive", 0.62, ["15m", "1h", "1d"], ["index", "smallcap"]),
            # FUTURES
            self._item("ES", "E-mini S&P 500", "FUTURES", "sim_futures", True, True, True, 100, "futures_trend", "balanced", 0.6, ["5m", "15m", "1h"], ["cme"], supported_contract_months=["2026H", "2026M", "2026U", "2026Z"], default_contract="2026H", roll_policy="ROLL_5D_BEFORE_EXPIRY", contract_size=50.0, tick_value=12.5, expiry_source="canonical_futures_contract_metadata"),
            self._item("NQ", "E-mini Nasdaq 100", "FUTURES", "sim_futures", True, True, True, 98, "futures_trend", "aggressive", 0.63, ["5m", "15m", "1h"], ["cme"], supported_contract_months=["2026H", "2026M", "2026U", "2026Z"], default_contract="2026H", roll_policy="ROLL_5D_BEFORE_EXPIRY", contract_size=20.0, tick_value=5.0, expiry_source="canonical_futures_contract_metadata"),
            self._item("YM", "E-mini Dow", "FUTURES", "sim_futures", True, True, True, 92, "futures_trend", "balanced", 0.6, ["5m", "15m", "1h"], ["cme"], supported_contract_months=["2026H", "2026M", "2026U", "2026Z"], default_contract="2026H", roll_policy="ROLL_5D_BEFORE_EXPIRY", contract_size=5.0, tick_value=5.0, expiry_source="canonical_futures_contract_metadata"),
            self._item("RTY", "E-mini Russell 2000", "FUTURES", "sim_futures", True, True, True, 90, "futures_trend", "aggressive", 0.63, ["5m", "15m", "1h"], ["cme"], supported_contract_months=["2026H", "2026M", "2026U", "2026Z"], default_contract="2026H", roll_policy="ROLL_5D_BEFORE_EXPIRY", contract_size=50.0, tick_value=5.0, expiry_source="canonical_futures_contract_metadata"),
            self._item("CL", "Crude Oil", "FUTURES", "sim_futures", True, True, True, 94, "commodity_breakout", "aggressive", 0.64, ["5m", "15m", "1h"], ["nymex"], supported_contract_months=["2026F", "2026G", "2026H", "2026J"], default_contract="2026F", roll_policy="ROLL_3D_BEFORE_EXPIRY", contract_size=1000.0, tick_value=10.0, expiry_source="canonical_futures_contract_metadata"),
            self._item("GC", "Gold", "FUTURES", "sim_futures", True, True, True, 93, "commodity_reversion", "balanced", 0.61, ["5m", "15m", "1h"], ["comex"], supported_contract_months=["2026G", "2026J", "2026M", "2026Q"], default_contract="2026G", roll_policy="ROLL_5D_BEFORE_EXPIRY", contract_size=100.0, tick_value=10.0, expiry_source="canonical_futures_contract_metadata"),
            self._item("SI", "Silver", "FUTURES", "sim_futures", True, True, True, 85, "commodity_breakout", "aggressive", 0.64, ["5m", "15m", "1h"], ["comex"], supported_contract_months=["2026H", "2026K", "2026N", "2026U"], default_contract="2026H", roll_policy="ROLL_5D_BEFORE_EXPIRY", contract_size=5000.0, tick_value=25.0, expiry_source="canonical_futures_contract_metadata"),
            # OPTIONS
            self._item("SPY", "SPY Options Chain", "OPTIONS", "sim_options", True, False, True, 96, "volatility_structure", "balanced", 0.64, ["15m", "1h"], ["options", "index"], supported_expiries=["2026-07-17", "2026-08-21", "2026-09-18"], default_expiry="2026-07-17", option_types=["CALL", "PUT"], supported_strikes=["ATM-5", "ATM", "ATM+5"], strike_policy="ATM_LADDER", contract_style="AMERICAN", expiry_source="canonical_options_chain_metadata"),
            self._item("QQQ", "QQQ Options Chain", "OPTIONS", "sim_options", True, False, True, 95, "volatility_structure", "aggressive", 0.66, ["15m", "1h"], ["options", "tech"], supported_expiries=["2026-07-17", "2026-08-21", "2026-09-18"], default_expiry="2026-07-17", option_types=["CALL", "PUT"], supported_strikes=["ATM-5", "ATM", "ATM+5"], strike_policy="ATM_LADDER", contract_style="AMERICAN", expiry_source="canonical_options_chain_metadata"),
        ]

    @staticmethod
    def _item(
        symbol: str,
        display_name: str,
        asset_class: str,
        broker: str,
        paper_supported: bool,
        live_supported: bool,
        enabled: bool,
        priority: int,
        default_strategy: str,
        risk_profile: str,
        minimum_confidence: float,
        preferred_timeframes: list[str],
        tags: list[str],
        supported_expiries: list[str] | None = None,
        default_expiry: str = "",
        option_types: list[str] | None = None,
        supported_strikes: list[str] | None = None,
        strike_policy: str = "",
        contract_style: str = "",
        supported_contract_months: list[str] | None = None,
        default_contract: str = "",
        roll_policy: str = "",
        contract_size: float = 0.0,
        tick_value: float = 0.0,
        expiry_source: str = "",
    ) -> CanonicalInstrument:
        return CanonicalInstrument(
            symbol=symbol,
            display_name=display_name,
            asset_class=asset_class,
            broker=broker,
            paper_supported=paper_supported,
            live_supported=live_supported,
            enabled=enabled,
            priority=int(priority),
            default_strategy=default_strategy,
            risk_profile=risk_profile,
            minimum_confidence=float(minimum_confidence),
            preferred_timeframes=list(preferred_timeframes),
            tags=list(tags),
            supported_expiries=list(supported_expiries or []),
            default_expiry=default_expiry,
            option_types=list(option_types or []),
            supported_strikes=list(supported_strikes or []),
            strike_policy=strike_policy,
            contract_style=contract_style,
            supported_contract_months=list(supported_contract_months or []),
            default_contract=default_contract,
            roll_policy=roll_policy,
            contract_size=float(contract_size),
            tick_value=float(tick_value),
            expiry_source=expiry_source,
        )
