"""Phase 187A — OANDA read-only certification framework (OFFLINE architecture).

NO NETWORK. NO AUTHENTICATION. NO LIVE CONNECTION. NO EXECUTION.
"""

from __future__ import annotations

from backend.app.market.oanda_readonly_certification.contracts import (
    FRAMEWORK_VERSION,
    SCHEMA_VERSION,
    OandaAccountStatus,
    OandaAuthenticationStatus,
    OandaConnectionStatus,
    OandaMarketDataStatus,
    OandaReadOnlyCertification,
)
from backend.app.market.oanda_readonly_certification.evidence import (
    OandaReadOnlyEvidencePackage,
    build_evidence_package,
)
from backend.app.market.oanda_readonly_certification.fingerprint import (
    ProviderFingerprint,
    build_provider_fingerprint,
)
from backend.app.market.oanda_readonly_certification.framework import (
    OandaReadOnlyCertificationFramework,
)
from backend.app.market.oanda_readonly_certification.gates import READ_ONLY_GATES, GateResult
from backend.app.market.oanda_readonly_certification.invalidation import (
    INVALIDATION_TRIGGERS,
    evaluate_invalidation,
)
from backend.app.market.oanda_readonly_certification.replay import (
    ReplayProtectionRegistry,
    evaluate_replay,
)
from backend.app.market.oanda_readonly_certification.state_machine import (
    CERTIFICATION_STATES,
    OandaReadOnlyStateMachine,
    TransitionResult,
)

__all__ = [
    "FRAMEWORK_VERSION",
    "SCHEMA_VERSION",
    "OandaConnectionStatus",
    "OandaAuthenticationStatus",
    "OandaAccountStatus",
    "OandaMarketDataStatus",
    "OandaReadOnlyCertification",
    "OandaReadOnlyEvidencePackage",
    "build_evidence_package",
    "ProviderFingerprint",
    "build_provider_fingerprint",
    "OandaReadOnlyCertificationFramework",
    "READ_ONLY_GATES",
    "GateResult",
    "INVALIDATION_TRIGGERS",
    "evaluate_invalidation",
    "ReplayProtectionRegistry",
    "evaluate_replay",
    "CERTIFICATION_STATES",
    "OandaReadOnlyStateMachine",
    "TransitionResult",
]
