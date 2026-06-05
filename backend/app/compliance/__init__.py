"""Compliance authorities for CSS Phase 1 acceptance validation."""

from backend.app.compliance.legal_acceptance import (
    AcceptanceBlockReason,
    AcceptanceValidationResult,
    AcceptanceValidationStatus,
    LegalAcceptanceRecord,
)
from backend.app.compliance.legal_acceptance_enforcement import (
    AcceptanceEnforcementDecision,
    AcceptanceEnforcementStatus,
    TradingSessionReadinessRequest,
    enforce_trading_session_acceptance,
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
from backend.app.persistence.repositories.legal_acceptance_repository import (
    LegalAcceptanceRepository,
)

__all__ = [
    "AcceptanceBlockReason",
    "AcceptanceEnforcementDecision",
    "AcceptanceEnforcementStatus",
    "AcceptanceValidationResult",
    "AcceptanceValidationStatus",
    "CURRENT_ACCEPTANCE_VERSIONS",
    "InMemoryLegalAcceptanceStore",
    "LEGAL_TERMS",
    "LegalAcceptanceRecord",
    "LegalAcceptanceRepository",
    "LegalAcceptanceService",
    "REQUIRED_ACCEPTANCE_TYPES",
    "TRADING_RISK_DISCLOSURE",
    "TradingSessionReadinessRequest",
    "enforce_trading_session_acceptance",
]