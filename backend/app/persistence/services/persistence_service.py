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
from backend.app.persistence.repositories.settlement_readiness_repository import (
    SettlementReadinessRepository,
)
from backend.app.persistence.repositories.billable_obligation_repository import (
    BillableObligationRepository,
)
from backend.app.persistence.repositories.billing_profile_repository import (
    BillingProfileRepository,
)
from backend.app.persistence.repositories.invoice_candidate_repository import (
    InvoiceCandidateRepository,
)
from backend.app.persistence.repositories.invoice_identity_repository import (
    InvoiceIdentityRepository,
)
from backend.app.persistence.repositories.invoice_issued_repository import (
    InvoiceIssuedRepository,
)
from backend.app.persistence.repositories.invoice_correction_repository import (
    InvoiceCorrectionRepository,
)
from backend.app.persistence.repositories.receivable_recognition_repository import (
    ReceivableRecognitionRepository,
)
from backend.app.persistence.repositories.receivable_reversal_repository import (
    ReceivableReversalRepository,
)
from backend.app.persistence.repositories.receivable_due_repository import (
    ReceivableDueRepository,
)
from backend.app.persistence.repositories.receivable_payment_repository import (
    ReceivablePaymentRepository,
)
from backend.app.persistence.repositories.receivable_payment_allocation_repository import (
    ReceivablePaymentAllocationRepository,
)
from backend.app.persistence.repositories.receivable_credit_repository import (
    ReceivableCreditRepository,
)
from backend.app.persistence.repositories.receivable_writeoff_repository import (
    ReceivableWriteOffRepository,
)
from backend.app.persistence.repositories.platform_access_fee_terms_repository import (
    PlatformAccessFeeTermsRepository,
)
from backend.app.persistence.repositories.fx_conversion_repository import FxConversionEvidenceRepository
from backend.app.persistence.repositories.final_fee_selection_repository import FinalFeeSelectionRepository
from backend.app.persistence.repositories.trial_contract_repository import TrialContractRepository
from backend.app.persistence.repositories.independent_trade_economics_repository import IndependentTradeEconomicsRepository
from backend.app.persistence.repositories.commercialization_technical_validation_repository import CommercializationTechnicalValidationRepository
from backend.app.persistence.repositories.production_charging_approval_repository import ProductionChargingApprovalRepository
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
        self.platform_access_fee_terms = PlatformAccessFeeTermsRepository()
        self.fx_conversion_evidence = FxConversionEvidenceRepository()
        self.final_fee_selections = FinalFeeSelectionRepository()
        self.trial_contracts = TrialContractRepository()
        self.independent_trade_economics = IndependentTradeEconomicsRepository()
        self.commercialization_technical_validations = CommercializationTechnicalValidationRepository()
        self.production_charging_approvals = ProductionChargingApprovalRepository()
        self.shadow_compensation_entitlements = (
            ShadowCompensationEntitlementRepository()
        )
        self.performance_compensation_lifecycle_policies = (
            PerformanceCompensationLifecyclePolicyRepository()
        )
        self.crystallization_assessments = (
            CrystallizationAssessmentRepository()
        )
        self.settlement_readiness = (
            SettlementReadinessRepository()
        )
        self.billable_obligations = BillableObligationRepository()
        self.billing_profiles = BillingProfileRepository()
        self.invoice_candidates = InvoiceCandidateRepository()
        self.invoice_identity_allocations = InvoiceIdentityRepository()
        self.invoice_issued_records = InvoiceIssuedRepository()
        self.invoice_corrections = InvoiceCorrectionRepository()
        self.receivable_recognitions = ReceivableRecognitionRepository()
        self.receivable_reversals = ReceivableReversalRepository()
        self.receivable_due_records = ReceivableDueRepository()
        self.receivable_payments = ReceivablePaymentRepository()
        self.receivable_payment_allocations = (
            ReceivablePaymentAllocationRepository()
        )
        self.receivable_credits = ReceivableCreditRepository()
        self.receivable_writeoffs = ReceivableWriteOffRepository()
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
                "platform_access_fee_terms": True,
                "fx_conversion_evidence": True,
                "final_fee_selections": True,
                "trial_contracts": True,
                "independent_trade_economics": True,
                "commercialization_technical_validations": True,
                "production_charging_approvals": True,
                "shadow_compensation_entitlements": True,
                "performance_compensation_lifecycle_policies": True,
                "crystallization_assessments": True,
                "settlement_readiness": True,
                "billable_obligations": True,
                "billing_profiles": True,
                "invoice_candidates": True,
                "invoice_identity_allocations": True,
                "invoice_issued_records": True,
                "invoice_corrections": True,
                "receivable_recognitions": True,
                "receivable_reversals": True,
                "receivable_due_records": True,
                "receivable_payments": True,
                "receivable_payment_allocations": True,
                "receivable_credits": True,
                "receivable_writeoffs": True,
                "pnl_snapshots": True,
                "legal_acceptances": True,
            },
        }
