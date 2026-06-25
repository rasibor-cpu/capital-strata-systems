from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Mapping


class TradeContextRecorderError(RuntimeError):
    """Raised when completed trade context is incomplete or invalid."""


@dataclass(frozen=True)
class TradeContextRecord:
    trade_id: str
    symbol: str
    asset_class: str
    strategy: str
    entry_time: str
    exit_time: str
    market_regime: str
    volatility: float
    trend_strength: float
    confidence: float
    broker: str
    session: str


_REQUIRED_FIELDS = tuple(TradeContextRecord.__dataclass_fields__.keys())


class TradeContextRecorder:
    """Builds canonical context payloads for completed trades."""

    def record_context(self, payload: Mapping[str, Any] | TradeContextRecord) -> dict[str, Any]:
        return asdict(self._normalize(payload))

    @staticmethod
    def _normalize(payload: Mapping[str, Any] | TradeContextRecord) -> TradeContextRecord:
        if isinstance(payload, TradeContextRecord):
            raw = asdict(payload)
        elif isinstance(payload, Mapping):
            raw = dict(payload)
        else:
            raise TradeContextRecorderError("Trade context payload must be a mapping or TradeContextRecord")

        missing = [field for field in _REQUIRED_FIELDS if field not in raw]
        if missing:
            raise TradeContextRecorderError(
                f"Trade context missing required fields: {', '.join(missing)}"
            )

        string_fields = {
            "trade_id",
            "symbol",
            "asset_class",
            "strategy",
            "entry_time",
            "exit_time",
            "market_regime",
            "broker",
            "session",
        }

        normalized: dict[str, Any] = {}
        for field in string_fields:
            value = str(raw[field]).strip()
            if not value:
                raise TradeContextRecorderError(f"Trade context field {field} must be non-empty")
            if field in {"symbol", "asset_class", "market_regime"}:
                value = value.upper()
            normalized[field] = value

        try:
            normalized["volatility"] = float(raw["volatility"])
            normalized["trend_strength"] = float(raw["trend_strength"])
            normalized["confidence"] = float(raw["confidence"])
        except (TypeError, ValueError) as exc:
            raise TradeContextRecorderError("Trade context numeric fields must be numeric") from exc

        if normalized["confidence"] < 0 or normalized["confidence"] > 1:
            raise TradeContextRecorderError("Trade context confidence must be between 0 and 1")

        return TradeContextRecord(**{field: normalized[field] for field in _REQUIRED_FIELDS})
