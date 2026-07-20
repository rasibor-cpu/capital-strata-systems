"""
Phase 177C — Canonical LIVE_READ_ONLY capability contract.

Restores LIVE_READ_ONLY as a first-class runtime capability for Tier-1 brokers.

Allowed:
  authenticate, load balances, load positions, load market data,
  synchronize products, refresh broker health, refresh readiness.

Forbidden:
  order submission, live trades, execution authority elevation.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Mapping

from backend.app.brokers.canonical_tier1 import get_canonical_broker_registry

SCHEMA_VERSION = "css.broker.live_read_only.v1"

LIVE_READ_ONLY_ACTIONS = (
    "authenticate",
    "load_balances",
    "load_positions",
    "load_market_data",
    "synchronize_products",
    "refresh_broker_health",
    "refresh_readiness",
)

BLOCKED_ACTIONS = (
    "submit_order",
    "cancel_order",
    "modify_order",
    "place_trade",
    "arm_execution",
    "enable_live_trading",
)


@dataclass(frozen=True)
class LiveReadOnlyContract:
    broker: str
    runtime_mode: str
    allowed_actions: tuple[str, ...]
    blocked_actions: tuple[str, ...]
    execution_enabled: bool
    order_submission: str
    execution_authority: str
    live_trading_enabled: bool
    advisory_only: bool
    reason: str
    schema_version: str = SCHEMA_VERSION
    generated_at: str = ""

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["allowed_actions"] = list(self.allowed_actions)
        payload["blocked_actions"] = list(self.blocked_actions)
        payload["generated_at"] = self.generated_at or _utc_now()
        return payload


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def build_live_read_only_contract(broker: str, *, evidence: Mapping[str, Any] | None = None) -> LiveReadOnlyContract:
    """
    Build the fail-closed LIVE_READ_ONLY contract for a Tier-1 broker.

    Execution is always blocked regardless of evidence.
    """
    registry = get_canonical_broker_registry()
    key = str(broker or "").strip().upper()
    if not registry.is_tier1(key):
        return LiveReadOnlyContract(
            broker=key or "NONE",
            runtime_mode="DISABLED",
            allowed_actions=(),
            blocked_actions=BLOCKED_ACTIONS,
            execution_enabled=False,
            order_submission="BLOCKED",
            execution_authority="BLOCKED",
            live_trading_enabled=False,
            advisory_only=True,
            reason="broker_not_in_tier1_registry",
        )

    spec = registry.get(key)
    if not spec.capabilities.live_read_only:
        return LiveReadOnlyContract(
            broker=key,
            runtime_mode="DISABLED",
            allowed_actions=(),
            blocked_actions=BLOCKED_ACTIONS,
            execution_enabled=False,
            order_submission="BLOCKED",
            execution_authority="BLOCKED",
            live_trading_enabled=False,
            advisory_only=True,
            reason="live_read_only_not_advertised",
        )

    evidence = evidence if isinstance(evidence, Mapping) else {}
    # Evidence may report auth/connectivity; never elevates execution
    return LiveReadOnlyContract(
        broker=key,
        runtime_mode="LIVE_READ_ONLY",
        allowed_actions=LIVE_READ_ONLY_ACTIONS,
        blocked_actions=BLOCKED_ACTIONS,
        execution_enabled=False,
        order_submission="BLOCKED",
        execution_authority="BLOCKED",
        live_trading_enabled=False,
        advisory_only=True,
        reason=str(evidence.get("reason") or "live_read_only_validation_only"),
    )


def assert_execution_blocked(contract: LiveReadOnlyContract | Mapping[str, Any]) -> bool:
    if isinstance(contract, LiveReadOnlyContract):
        return (
            contract.execution_enabled is False
            and contract.order_submission == "BLOCKED"
            and contract.live_trading_enabled is False
        )
    return (
        not bool(contract.get("execution_enabled"))
        and str(contract.get("order_submission") or "BLOCKED").upper() == "BLOCKED"
        and not bool(contract.get("live_trading_enabled"))
    )


__all__ = [
    "BLOCKED_ACTIONS",
    "LIVE_READ_ONLY_ACTIONS",
    "LiveReadOnlyContract",
    "SCHEMA_VERSION",
    "assert_execution_blocked",
    "build_live_read_only_contract",
]
