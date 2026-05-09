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
    api_health: str = "UNKNOWN"
    reconnect_state: str = "NONE"
    supported_assets: tuple[str, ...] = ()
    account_readiness: str = "UNKNOWN"
    missing_credentials: bool = False
    latency_ms: float = 0.0
    readiness_status: str = "BROKER_BLOCKED"
    readiness_reasons: tuple[str, ...] = ()

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
            api_health=str(summary.get("api_health", "UNKNOWN")),
            reconnect_state=str(summary.get("reconnect_state", "NONE")),
            supported_assets=cls._to_assets(summary.get("supported_assets", [])),
            account_readiness=str(summary.get("account_readiness", "UNKNOWN")),
            missing_credentials=cls._to_bool(
                summary.get("missing_credentials", False)
            ),
            latency_ms=cls._to_float(summary.get("latency_ms", 0.0)),
            readiness_status=str(
                summary.get("readiness_status", "BROKER_BLOCKED")
            ),
            readiness_reasons=cls._to_assets(
                summary.get("readiness_reasons", [])
            ),
        )

    @staticmethod
    def _to_bool(value: Any) -> bool:
        if isinstance(value, bool):
            return value

        if value is None:
            return False

        normalized = str(value).strip().lower()

        return normalized in {"1", "true", "yes", "y", "enabled", "connected"}

    @staticmethod
    def _to_assets(value: Any) -> tuple[str, ...]:
        if isinstance(value, list):
            return tuple(str(item) for item in value)

        if isinstance(value, tuple):
            return tuple(str(item) for item in value)

        if isinstance(value, str):
            return tuple(item.strip() for item in value.split(",") if item.strip())

        return ()

    @staticmethod
    def _to_float(value: Any) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0
