from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Mapping


class ReplayModelsError(RuntimeError):
    """Fail-closed exception for replay model validation."""


_ASSET_CLASS_ALIASES = {
    "FOREX": "FX",
    "FX": "FX",
    "CRYPTO": "CRYPTO",
    "FUTURES": "FUTURES",
    "OPTIONS": "OPTIONS",
    "EQUITY": "EQUITY",
    "STOCK": "EQUITY",
    "ETF": "ETF",
    "ETFS": "ETF",
    "COMMODITY": "COMMODITY",
    "BOND": "BOND",
    "FIXED_INCOME": "BOND",
    "INDEX": "INDEX",
}


def normalize_asset_class(asset_class: Any) -> str:
    value = str(asset_class or "").strip().upper()
    if not value:
        raise ReplayModelsError("asset_class must be non-empty")
    normalized = _ASSET_CLASS_ALIASES.get(value)
    if normalized is None:
        raise ReplayModelsError(f"Unknown asset class: {value}")
    return normalized


@dataclass(frozen=True)
class HistoricalMarketEvent:
    timestamp: str
    symbol: str
    asset_class: str
    market_snapshot: dict[str, Any]

    @staticmethod
    def from_mapping(payload: Mapping[str, Any]) -> "HistoricalMarketEvent":
        if not isinstance(payload, Mapping):
            raise ReplayModelsError("market event must be a mapping")
        required = {"timestamp", "symbol", "asset_class", "market_snapshot"}
        missing = [field for field in required if field not in payload]
        if missing:
            raise ReplayModelsError(f"market event missing required fields: {', '.join(missing)}")

        timestamp = str(payload.get("timestamp") or "").strip()
        symbol = str(payload.get("symbol") or "").strip().upper()
        asset_class = normalize_asset_class(payload.get("asset_class"))
        market_snapshot = payload.get("market_snapshot")
        if not timestamp:
            raise ReplayModelsError("market event timestamp must be non-empty")
        if not symbol:
            raise ReplayModelsError("market event symbol must be non-empty")
        if not isinstance(market_snapshot, Mapping):
            raise ReplayModelsError("market event market_snapshot must be a mapping")

        return HistoricalMarketEvent(
            timestamp=timestamp,
            symbol=symbol,
            asset_class=asset_class,
            market_snapshot=dict(market_snapshot),
        )


@dataclass(frozen=True)
class HistoricalTradeCandidate:
    trade_id: str
    symbol: str
    asset_class: str
    direction: str
    strategy: str
    current_price: float
    market_snapshot: dict[str, Any]
    portfolio_snapshot: dict[str, Any]

    @staticmethod
    def from_mapping(payload: Mapping[str, Any]) -> "HistoricalTradeCandidate":
        if not isinstance(payload, Mapping):
            raise ReplayModelsError("trade candidate must be a mapping")
        required = {
            "trade_id",
            "symbol",
            "asset_class",
            "direction",
            "strategy",
            "current_price",
            "market_snapshot",
            "portfolio_snapshot",
        }
        missing = [field for field in required if field not in payload]
        if missing:
            raise ReplayModelsError(f"trade candidate missing required fields: {', '.join(missing)}")

        trade_id = str(payload.get("trade_id") or "").strip()
        symbol = str(payload.get("symbol") or "").strip().upper()
        asset_class = normalize_asset_class(payload.get("asset_class"))
        direction = str(payload.get("direction") or "").strip().upper()
        strategy = str(payload.get("strategy") or "").strip()
        if not trade_id:
            raise ReplayModelsError("trade_id must be non-empty")
        if not symbol:
            raise ReplayModelsError("symbol must be non-empty")
        if direction not in {"LONG", "SHORT", "BUY", "SELL"}:
            raise ReplayModelsError("direction must be LONG, SHORT, BUY, or SELL")
        if not strategy:
            raise ReplayModelsError("strategy must be non-empty")

        try:
            current_price = float(payload.get("current_price"))
        except (TypeError, ValueError) as exc:
            raise ReplayModelsError("current_price must be numeric") from exc
        if current_price <= 0:
            raise ReplayModelsError("current_price must be positive")

        market_snapshot = payload.get("market_snapshot")
        portfolio_snapshot = payload.get("portfolio_snapshot")
        if not isinstance(market_snapshot, Mapping):
            raise ReplayModelsError("market_snapshot must be a mapping")
        if not isinstance(portfolio_snapshot, Mapping):
            raise ReplayModelsError("portfolio_snapshot must be a mapping")

        return HistoricalTradeCandidate(
            trade_id=trade_id,
            symbol=symbol,
            asset_class=asset_class,
            direction=direction,
            strategy=strategy,
            current_price=current_price,
            market_snapshot=dict(market_snapshot),
            portfolio_snapshot=dict(portfolio_snapshot),
        )


@dataclass(frozen=True)
class HistoricalCompletedTrade:
    trade_id: str
    symbol: str
    asset_class: str
    strategy: str
    timestamp_open: str
    timestamp_close: str
    realized_pnl: float
    market_regime: str

    @staticmethod
    def from_mapping(payload: Mapping[str, Any]) -> "HistoricalCompletedTrade":
        if not isinstance(payload, Mapping):
            raise ReplayModelsError("completed trade must be a mapping")
        required = {
            "trade_id",
            "symbol",
            "asset_class",
            "strategy",
            "timestamp_open",
            "timestamp_close",
            "realized_pnl",
            "market_regime",
        }
        missing = [field for field in required if field not in payload]
        if missing:
            raise ReplayModelsError(f"completed trade missing required fields: {', '.join(missing)}")

        trade_id = str(payload.get("trade_id") or "").strip()
        symbol = str(payload.get("symbol") or "").strip().upper()
        asset_class = normalize_asset_class(payload.get("asset_class"))
        strategy = str(payload.get("strategy") or "").strip()
        timestamp_open = str(payload.get("timestamp_open") or "").strip()
        timestamp_close = str(payload.get("timestamp_close") or "").strip()
        market_regime = str(payload.get("market_regime") or "").strip().upper() or "UNKNOWN"
        if not trade_id or not symbol or not strategy or not timestamp_open or not timestamp_close:
            raise ReplayModelsError("completed trade string fields must be non-empty")

        try:
            realized_pnl = float(payload.get("realized_pnl"))
        except (TypeError, ValueError) as exc:
            raise ReplayModelsError("realized_pnl must be numeric") from exc

        return HistoricalCompletedTrade(
            trade_id=trade_id,
            symbol=symbol,
            asset_class=asset_class,
            strategy=strategy,
            timestamp_open=timestamp_open,
            timestamp_close=timestamp_close,
            realized_pnl=realized_pnl,
            market_regime=market_regime,
        )


@dataclass(frozen=True)
class HistoricalReplayRecord:
    timestamp: str
    trade_candidate: HistoricalTradeCandidate
    market_event: HistoricalMarketEvent
    completed_trade: HistoricalCompletedTrade | None = None

    @staticmethod
    def from_mapping(payload: Mapping[str, Any]) -> "HistoricalReplayRecord":
        if not isinstance(payload, Mapping):
            raise ReplayModelsError("replay record must be a mapping")

        if "trade_candidate" in payload:
            trade_candidate_payload = payload.get("trade_candidate")
            market_event_payload = payload.get("market_event")
            timestamp = str(payload.get("timestamp") or "").strip()
            completed_trade_payload = payload.get("completed_trade")
        else:
            trade_candidate_payload = payload
            market_event_payload = {
                "timestamp": payload.get("timestamp"),
                "symbol": payload.get("symbol"),
                "asset_class": payload.get("asset_class"),
                "market_snapshot": payload.get("market_snapshot"),
            }
            timestamp = str(payload.get("timestamp") or "").strip()
            completed_trade_payload = payload.get("completed_trade")

        trade_candidate = HistoricalTradeCandidate.from_mapping(trade_candidate_payload)
        market_event = HistoricalMarketEvent.from_mapping(market_event_payload)

        if not timestamp:
            timestamp = market_event.timestamp

        completed_trade = None
        if completed_trade_payload is not None:
            completed_trade = HistoricalCompletedTrade.from_mapping(completed_trade_payload)

        return HistoricalReplayRecord(
            timestamp=timestamp,
            trade_candidate=trade_candidate,
            market_event=market_event,
            completed_trade=completed_trade,
        )


@dataclass(frozen=True)
class ReplayDecision:
    timestamp: str
    symbol: str
    market_regime: str
    selected_strategy: str
    allocation: dict[str, Any]
    position_size: dict[str, Any]
    risk_score: float
    confidence: float
    decision: str
    exit_plan: dict[str, Any]
    diagnostics: dict[str, Any]
    canonical_decision: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ReplayRunResult:
    decisions: list[ReplayDecision]
    statistics: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "decisions": [decision.to_dict() for decision in self.decisions],
            "statistics": dict(self.statistics),
        }
