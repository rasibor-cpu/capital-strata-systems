from typing import Any

from backend.app.persistence.repositories.legal_acceptance_repository import (
    LegalAcceptanceRepository,
)
from backend.app.persistence.repositories.pnl_snapshot_repository import (
    PnlSnapshotRepository,
)
from backend.app.persistence.repositories.session_repository import (
    SessionRepository,
)
from backend.app.persistence.repositories.trade_repository import (
    TradeRepository,
)
from backend.app.persistence.repositories.trade_provenance_repository import (
    TradeProvenanceRepository,
)
from backend.app.persistence.repositories.attributable_performance_repository import (
    AttributablePerformanceRepository,
)
from backend.app.persistence.repositories.performance_accounting_transition_repository import (
    PerformanceAccountingTransitionRepository,
)
from backend.app.persistence.repositories.performance_compensation_terms_repository import (
    PerformanceCompensationTermsRepository,
)
from backend.app.persistence.repositories.shadow_compensation_entitlement_repository import (
    ShadowCompensationEntitlementRepository,
)
from backend.app.persistence.repositories.performance_compensation_lifecycle_policy_repository import (
    PerformanceCompensationLifecyclePolicyRepository,
)
from backend.app.persistence.repositories.crystallization_assessment_repository import (
    CrystallizationAssessmentRepository,
)
from backend.app.persistence.migrations.runner import run_migrations


class PersistenceService:
    """
    Central persistence coordination service.

    This service provides a unified access layer
    for all CSS persistence repositories.

    IMPORTANT:
    - No orchestration logic here
    - No governance logic here
    - No broker execution logic here
    - Persistence only
    """

    def __init__(self) -> None:
        run_migrations()
        self.sessions = SessionRepository()
        self.trades = TradeRepository()
        self.trade_provenance = TradeProvenanceRepository()
        self.attributable_performance = (
            AttributablePerformanceRepository()
        )
        self.performance_accounting_transitions = (
            PerformanceAccountingTransitionRepository()
        )
        self.performance_compensation_terms = (
            PerformanceCompensationTermsRepository()
        )
        self.shadow_compensation_entitlements = (
            ShadowCompensationEntitlementRepository()
        )
        self.performance_compensation_lifecycle_policies = (
            PerformanceCompensationLifecyclePolicyRepository()
        )
        self.crystallization_assessments = (
            CrystallizationAssessmentRepository()
        )
        self.pnl_snapshots = (
            PnlSnapshotRepository()
        )
        self.legal_acceptances = (
            LegalAcceptanceRepository()
        )

    def healthcheck(self) -> dict[str, Any]:
        """
        Basic persistence health verification.
        """

        return {
            "service": "PersistenceService",
            "status": "ok",
            "repositories": {
                "sessions": True,
                "trades": True,
                "trade_provenance": True,
                "attributable_performance": True,
                "performance_accounting_transitions": True,
                "performance_compensation_terms": True,
                "shadow_compensation_entitlements": True,
                "performance_compensation_lifecycle_policies": True,
                "crystallization_assessments": True,
                "pnl_snapshots": True,
                "legal_acceptances": True,
            },
        }
