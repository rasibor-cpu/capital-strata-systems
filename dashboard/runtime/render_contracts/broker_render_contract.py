from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class BrokerRenderContract:
    """
    PCNRASS-safe immutable render contract for broker display.
    """

    selected_broker: str
    broker_mode: str
    connected: bool
    live_trading_enabled: bool
    last_heartbeat: str

    @classmethod
    def from_summary(cls, broker_summary: dict) -> "BrokerRenderContract":
        summary = broker_summary or {}

        return cls(
            selected_broker=str(summary.get("selected_broker", "NONE")),
            broker_mode=str(summary.get("broker_mode", "paper")),
            connected=cls._to_bool(summary.get("connected", False)),
            live_trading_enabled=cls._to_bool(
                summary.get("live_trading_enabled", False)
            ),
            last_heartbeat=str(summary.get("last_heartbeat", "")),
        )

    @staticmethod
    def _to_bool(value: Any) -> bool:
        if isinstance(value, bool):
            return value

        if value is None:
            return False

        normalized = str(value).strip().lower()

        return normalized in {"1", "true", "yes", "y", "enabled", "connected"}
