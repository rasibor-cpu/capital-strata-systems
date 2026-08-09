"""Phase 194 — canonical broker qualification-path reconciliation.

This module does not authenticate, perform network operations, start runtimes,
or grant execution authority.

It reconciles the existing canonical broker architecture:

Canonical Tier-1 Registry (177C)
    -> Enterprise read-only runtime
    -> Multi-broker readiness (189)
    -> Operational qualification (193)
    -> Enterprise Certification Registry (191)

No new broker runtime or certification engine is introduced.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Mapping

from backend.app.brokers.canonical_tier1 import (
    ROADMAP_EXCLUDED_BROKERS,
    TIER1_BROKERS,
    get_canonical_broker_registry,
)
from backend.app.brokers.operational_qualification.matrix import DEFAULT_BROKERS


PHASE_194_VERSION = "194.1"
SCHEMA_ID = "CSS_CANONICAL_BROKER_QUALIFICATION_PATH"
SCHEMA_VERSION = "194.1"

EXECUTION_AUTHORITY = False
LIVE_TRADING_AUTHORIZED = False

CANONICAL_TIER1 = tuple(TIER1_BROKERS)

# Phase 193 intentionally also knows about IBKR and PLUGIN for governance
# classification. This does not make them active Tier-1 runtime brokers.
QUALIFICATION_SCOPE = tuple(DEFAULT_BROKERS)

# Dependency-safe static identity mapping to existing enterprise read-only runtimes.
# Phase 194 must not import the enterprise runtime/security dependency chain.
ENTERPRISE_RUNTIME_CONSUMERS = {
    "COINBASE": "CoinbaseEnterpriseReadOnlyRuntime",
    "BINANCE": "BinanceEnterpriseReadOnlyRuntime",
    "OANDA": "OandaEnterpriseReadOnlyRuntime",
    "QUESTRADE": "QuestradeEnterpriseReadOnlyRuntime",
}

FORBIDDEN_EXECUTION_ACTIONS = (
    "submit_order",
    "place_order",
    "create_order",
    "modify_order",
    "replace_order",
    "cancel_order",
    "close_position",
    "liquidate",
    "transfer_funds",
    "withdraw",
    "arm_execution",
    "enable_live_trading",
)


@dataclass(frozen=True)
class CanonicalBrokerQualificationPath:
    schema_id: str
    schema_version: str
    phase_version: str
    broker: str
    tier1_active: bool
    roadmap_excluded: bool
    plugin_only: bool
    canonical_registry_present: bool
    enterprise_runtime_consumer: str | None
    phase189_applicable: bool
    phase193_applicable: bool
    phase191_registry_required: bool
    live_read_only_advertised: bool
    execution_authority: bool
    live_trading_authorized: bool
    canonical_status: str
    blockers: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["blockers"] = list(self.blockers)

        # Hard Phase 194 safety invariants.
        payload["execution_authority"] = False
        payload["live_trading_authorized"] = False

        return payload

    def __post_init__(self) -> None:
        if self.execution_authority:
            raise ValueError("Phase 194 must never grant execution authority")
        if self.live_trading_authorized:
            raise ValueError("Phase 194 must never authorize live trading")


def _normalize(broker: str) -> str:
    return str(broker or "").strip().upper()


def canonical_broker_path(broker: str) -> CanonicalBrokerQualificationPath:
    """Return the governed canonical path for a broker without side effects."""

    key = _normalize(broker)

    tier1 = key in CANONICAL_TIER1
    excluded = key in ROADMAP_EXCLUDED_BROKERS
    plugin_only = key == "PLUGIN"

    registry = get_canonical_broker_registry()

    registry_present = registry.is_tier1(key)

    runtime_consumer = ENTERPRISE_RUNTIME_CONSUMERS.get(key)

    blockers: list[str] = []

    if excluded:
        blockers.append("ROADMAP_EXCLUDED")

    if plugin_only:
        blockers.extend(
            (
                "PLUGIN_REQUIRES_EXPLICIT_REGISTRATION",
                "PLUGIN_NOT_NATIVE_TIER1_RUNTIME",
            )
        )

    if tier1 and not registry_present:
        blockers.append("CANONICAL_REGISTRY_DRIFT")

    if tier1 and not runtime_consumer:
        blockers.append("ENTERPRISE_RUNTIME_CONSUMER_MISSING")

    if not tier1 and not excluded and not plugin_only:
        blockers.append("BROKER_NOT_IN_CANONICAL_SCOPE")

    if tier1:
        spec = registry.get(key)
        live_read_only = bool(spec.capabilities.live_read_only)
        if not live_read_only:
            blockers.append("LIVE_READ_ONLY_NOT_ADVERTISED")
    else:
        live_read_only = False

    if excluded:
        status = "BLOCKED_ROADMAP_EXCLUDED"
    elif plugin_only:
        status = "PLUGIN_REGISTRATION_REQUIRED"
    elif not tier1:
        status = "NOT_CANONICAL"
    elif blockers:
        status = "BLOCKED_CANONICAL_DRIFT"
    else:
        status = "CANONICAL_READ_ONLY_PATH_AVAILABLE"

    return CanonicalBrokerQualificationPath(
        schema_id=SCHEMA_ID,
        schema_version=SCHEMA_VERSION,
        phase_version=PHASE_194_VERSION,
        broker=key,
        tier1_active=tier1,
        roadmap_excluded=excluded,
        plugin_only=plugin_only,
        canonical_registry_present=registry_present,
        enterprise_runtime_consumer=runtime_consumer,
        phase189_applicable=key in QUALIFICATION_SCOPE,
        phase193_applicable=key in QUALIFICATION_SCOPE,
        phase191_registry_required=True,
        live_read_only_advertised=live_read_only,
        execution_authority=False,
        live_trading_authorized=False,
        canonical_status=status,
        blockers=tuple(blockers),
    )


def build_canonical_broker_path_matrix() -> tuple[CanonicalBrokerQualificationPath, ...]:
    """Return deterministic Phase 194 broker reconciliation matrix."""

    ordered = (
        "OANDA",
        "COINBASE",
        "BINANCE",
        "QUESTRADE",
        "IBKR",
        "PLUGIN",
    )

    return tuple(canonical_broker_path(broker) for broker in ordered)


def phase194_safety_contract() -> Mapping[str, Any]:
    """Machine-readable Phase 194 safety boundary."""

    return {
        "schema_id": "CSS_PHASE_194_SAFETY_CONTRACT",
        "schema_version": SCHEMA_VERSION,
        "network_allowed": False,
        "authentication_performed": False,
        "runtime_activation_allowed": False,
        "broker_contact_allowed": False,
        "order_submission_allowed": False,
        "execution_authority": False,
        "live_trading_authorized": False,
        "freeze_sha_designated": False,
        "forbidden_execution_actions": list(FORBIDDEN_EXECUTION_ACTIONS),
        "canonical_layers": [
            "PHASE_177C_CANONICAL_TIER1",
            "ENTERPRISE_READ_ONLY_RUNTIME",
            "PHASE_189_MULTI_BROKER_READINESS",
            "PHASE_193_OPERATIONAL_QUALIFICATION",
            "PHASE_191_ENTERPRISE_CERTIFICATION_REGISTRY",
        ],
    }


__all__ = [
    "CANONICAL_TIER1",
    "CanonicalBrokerQualificationPath",
    "EXECUTION_AUTHORITY",
    "FORBIDDEN_EXECUTION_ACTIONS",
    "LIVE_TRADING_AUTHORIZED",
    "PHASE_194_VERSION",
    "QUALIFICATION_SCOPE",
    "SCHEMA_ID",
    "SCHEMA_VERSION",
    "build_canonical_broker_path_matrix",
    "canonical_broker_path",
    "phase194_safety_contract",
]




