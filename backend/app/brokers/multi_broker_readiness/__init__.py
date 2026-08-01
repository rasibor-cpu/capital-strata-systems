"""Phase 189 — multi-broker operational readiness and controlled online certification.

NO TRADING AUTHORIZATION. NO ORDER SUBMISSION. NO LIVE EXECUTION UNLOCK.
"""

from __future__ import annotations

from backend.app.brokers.multi_broker_readiness.audit_matrix import (
    CAPABILITY_PROFILES,
    get_capability_profile,
    register_plugin_capability,
)
from backend.app.brokers.multi_broker_readiness.auth_ttl import (
    AuthorizationTTL,
    AuthorizationTTLRegistry,
)
from backend.app.brokers.multi_broker_readiness.contracts import (
    FRAMEWORK_VERSION,
    SCHEMA_VERSION,
    AssetClass,
    BrokerCapabilityProfile,
    BrokerCertificationEvidence,
    BrokerCertificationGeneration,
    BrokerOperationalReadiness,
    BrokerProviderFingerprint,
    BrokerReadOnlyCertification,
    BrokerType,
)
from backend.app.brokers.multi_broker_readiness.firewall import verify_multi_broker_firewall
from backend.app.brokers.multi_broker_readiness.framework import MultiBrokerReadinessFramework
from backend.app.brokers.multi_broker_readiness.precheck import (
    ControlledOnlinePrecheck,
    run_controlled_online_precheck,
)
from backend.app.brokers.multi_broker_readiness.rc004 import RC004Readiness, evaluate_rc004_readiness
from backend.app.brokers.multi_broker_readiness.state_machine import (
    CERTIFICATION_STATES,
    BrokerCertificationStateMachine,
)

__all__ = [
    "FRAMEWORK_VERSION",
    "SCHEMA_VERSION",
    "BrokerType",
    "AssetClass",
    "BrokerCapabilityProfile",
    "BrokerReadOnlyCertification",
    "BrokerOperationalReadiness",
    "BrokerCertificationEvidence",
    "BrokerCertificationGeneration",
    "BrokerProviderFingerprint",
    "BrokerCertificationStateMachine",
    "CERTIFICATION_STATES",
    "AuthorizationTTL",
    "AuthorizationTTLRegistry",
    "RC004Readiness",
    "evaluate_rc004_readiness",
    "ControlledOnlinePrecheck",
    "run_controlled_online_precheck",
    "MultiBrokerReadinessFramework",
    "CAPABILITY_PROFILES",
    "get_capability_profile",
    "register_plugin_capability",
    "verify_multi_broker_firewall",
]
