from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


BROKER_READY = "BROKER_READY"
BROKER_DEGRADED = "BROKER_DEGRADED"
BROKER_BLOCKED = "BROKER_BLOCKED"


@dataclass(frozen=True)
class BrokerReadinessReport:
    status: str
    reasons: tuple[str, ...] = field(default_factory=tuple)
    selected_broker: str = "NONE"
    broker_mode: str = "paper"
    connected: bool = False
    live_trading_enabled: bool = False
    missing_credentials: bool = False

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["reasons"] = list(self.reasons)
        return payload


def certify_broker_readiness(
    *,
    selected_broker: str,
    broker_mode: str,
    connected: bool,
    live_trading_enabled: bool,
    missing_credentials: bool = False,
    api_health: str = "UNKNOWN",
    account_readiness: str = "UNKNOWN",
) -> BrokerReadinessReport:
    broker = str(selected_broker or "NONE").strip().upper()
    mode = _mode(broker_mode)
    health = str(api_health or "UNKNOWN").strip().upper()
    account = str(account_readiness or "UNKNOWN").strip().upper()
    reasons: list[str] = []

    if broker in {"", "NONE"}:
        reasons.append("broker_not_selected")

    if missing_credentials:
        reasons.append("missing_credentials")

    if not connected:
        reasons.append("broker_not_connected")

    if mode == "live" and not live_trading_enabled:
        reasons.append("live_trading_not_enabled")

    if health not in {"OK", "READY", "HEALTHY", "UNKNOWN"}:
        reasons.append("api_health_degraded")

    if account not in {"READY", "PAPER_READY", "LIVE_READY", "UNKNOWN"}:
        reasons.append("account_readiness_degraded")

    blocking = {
        "broker_not_selected",
        "missing_credentials",
        "live_trading_not_enabled",
    }
    if any(reason in blocking for reason in reasons):
        status = BROKER_BLOCKED
    elif reasons:
        status = BROKER_DEGRADED
    else:
        status = BROKER_READY

    return BrokerReadinessReport(
        status=status,
        reasons=tuple(reasons),
        selected_broker=broker or "NONE",
        broker_mode=mode,
        connected=bool(connected),
        live_trading_enabled=bool(live_trading_enabled),
        missing_credentials=bool(missing_credentials),
    )


def _mode(value: str) -> str:
    normalized = str(value).strip().lower()
    return "live" if normalized == "live" else "paper"


__all__ = [
    "BROKER_BLOCKED",
    "BROKER_DEGRADED",
    "BROKER_READY",
    "BrokerReadinessReport",
    "certify_broker_readiness",
]
