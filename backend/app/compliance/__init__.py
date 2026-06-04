"""Compliance authorities for CSS Phase 1 acceptance validation.

This package is intentionally additive and side-effect free. It does not alter
broker behavior, live execution behavior, dashboard authority, PnL calculations,
or existing governance gates.
"""

from backend.app.compliance.legal_acceptance import (
    AcceptanceBlockReason,
    AcceptanceValidationResult,
    AcceptanceValidationStatus,
    LegalAcceptanceRecord,
)

from backend.app.compliance.legal_acceptance_service import (
    LegalAcceptanceService,
)

from backend.app.compliance.legal_acceptance_store import (
    InMemoryLegalAcceptanceStore,
)

from backend.app.compliance.legal_acceptance_versions import (
    CURRENT_ACCEPTANCE_VERSIONS,
    LEGAL_TERMS,
    REQUIRED_ACCEPTANCE_TYPES,
    TRADING_RISK_DISCLOSURE,
)

__all__ = [
    "AcceptanceBlockReason",
    "AcceptanceValidationResult",
    "AcceptanceValidationStatus",
    "CURRENT_ACCEPTANCE_VERSIONS",
    "InMemoryLegalAcceptanceStore",
    "LEGAL_TERMS",
    "LegalAcceptanceRecord",
    "LegalAcceptanceService",
    "REQUIRED_ACCEPTANCE_TYPES",
    "TRADING_RISK_DISCLOSURE",
]