"""Canonical Enterprise Broker Runtime contracts."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any

from backend.security.identity.secret_handle import (
    SecretHandle,
    canonical_secret_consumer,
)
from backend.security.oauth.oauth_handles import OAuthHandle


class AdvisoryRuntimeState(str, Enum):
    FAILURE = "FAILURE"
    DATA_DEPENDENCY_BLOCKED = "DATA_DEPENDENCY_BLOCKED"
    PROVIDER_UNAVAILABLE = "PROVIDER_UNAVAILABLE"
    STALE = "STALE"
    PARTIAL_DATA = "PARTIAL_DATA"
    NO_CURRENT_OPPORTUNITIES = "NO_CURRENT_OPPORTUNITIES"
    ADVISORY_READY = "ADVISORY_READY"


STATE_PRIORITY = {state: index for index, state in enumerate(AdvisoryRuntimeState)}

BROKER_RUNTIME_CONSUMERS = {
    "QUESTRADE": "QuestradeEnterpriseReadOnlyRuntime",
    "COINBASE": "CoinbaseEnterpriseReadOnlyRuntime",
    "BINANCE": "BinanceEnterpriseReadOnlyRuntime",
    "OANDA": "OandaEnterpriseReadOnlyRuntime",
}


def canonical_broker_consumer(broker: str) -> str:
    normalized = str(broker or "").strip().upper()
    try:
        return BROKER_RUNTIME_CONSUMERS[normalized]
    except KeyError as exc:
        raise ValueError(f"BROKER_RUNTIME_CONSUMER_UNKNOWN:{normalized or 'EMPTY'}") from exc


@dataclass(frozen=True)
class BrokerCapabilityContract:
    broker: str
    operations: tuple[str, ...]
    credential_capabilities: tuple[str, ...]
    read_only: bool = True
    advisory_only: bool = True
    order_endpoints_allowed: bool = False
    trading_endpoints_allowed: bool = False
    execution_allowed: bool = False

    def permits(self, operation: str) -> bool:
        return (
            self.read_only
            and not self.execution_allowed
            and str(operation).upper() in self.operations
        )

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class EnterpriseBrokerBinding:
    broker: str
    consumer: str
    secret_handles: tuple[SecretHandle, ...]
    oauth_handle: OAuthHandle | None
    capabilities: BrokerCapabilityContract
    legacy_compatibility: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "broker", str(self.broker or "").strip().upper())
        object.__setattr__(
            self,
            "consumer",
            canonical_secret_consumer(self.consumer),
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "broker": self.broker,
            "consumer": self.consumer,
            "secret_handles": [handle.as_dict() for handle in self.secret_handles],
            "oauth_handle": self.oauth_handle.as_dict() if self.oauth_handle else None,
            "capabilities": self.capabilities.as_dict(),
            "legacy_compatibility": self.legacy_compatibility,
            "enterprise_managed": not self.legacy_compatibility,
            "plaintext_returned": False,
            "execution_allowed": False,
        }


def resolve_advisory_state(states: list[str]) -> AdvisoryRuntimeState:
    normalized = []
    aliases = {"FAILED": "FAILURE", "READY": "ADVISORY_READY"}
    for value in states:
        text = aliases.get(str(value).upper(), str(value).upper())
        try:
            normalized.append(AdvisoryRuntimeState(text))
        except ValueError:
            continue
    return min(normalized, key=lambda item: STATE_PRIORITY[item]) if normalized else AdvisoryRuntimeState.DATA_DEPENDENCY_BLOCKED


__all__ = [
    "AdvisoryRuntimeState",
    "BrokerCapabilityContract",
    "BROKER_RUNTIME_CONSUMERS",
    "EnterpriseBrokerBinding",
    "STATE_PRIORITY",
    "canonical_broker_consumer",
    "resolve_advisory_state",
]
