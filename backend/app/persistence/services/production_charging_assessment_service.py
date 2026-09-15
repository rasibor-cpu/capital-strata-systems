from __future__ import annotations

import json
from typing import Optional

from backend.app.persistence.services.persistence_service import PersistenceService
from backend.app.persistence.services.trial_conversion_assessment_service import (
    TrialConversionAssessmentService,
)
from backend.commercialization.production_charging_gate import (
    ApprovalStatus,
    JurisdictionLegalReview,
    PaymentCollectionAuthorityApproval,
    ProductionChargingAssessment,
    ProductionCommercializationCertification,
    assess_production_charging,
)
from backend.commercialization.trial_contract import TrialContractError
from backend.commercialization.production_security_certification import (
    ProductionSecurityOperationalCertification,
    SecurityOperationalApprovalStatus,
)


class ProductionChargingAssessmentService:
    """Read-only charging authorization assessment from canonical evidence."""

    def __init__(self, persistence_service: Optional[PersistenceService] = None) -> None:
        self._service = persistence_service or PersistenceService()

    def assess(
        self,
        *,
        customer_id: str,
        account_reference: str,
        agreement_id: str,
        agreement_version: str,
        jurisdiction_code: str,
        assessed_at: str,
    ) -> ProductionChargingAssessment:
        approvals = self._service.production_charging_approvals

        enrollment = self._service.trial_contracts.get_enrollment(
            customer_id=customer_id,
            account_reference=account_reference,
            agreement_id=agreement_id,
            agreement_version=agreement_version,
        )
        contract_accepted = enrollment is not None

        trial_assessment = None
        if contract_accepted:
            try:
                trial_assessment = TrialConversionAssessmentService(
                    self._service
                ).assess(
                    customer_id=customer_id,
                    account_reference=account_reference,
                    agreement_id=agreement_id,
                    agreement_version=agreement_version,
                    assessed_at=assessed_at,
                )
            except TrialContractError:
                trial_assessment = None

        legal_row = approvals.latest_legal_review(
            jurisdiction_code,
            agreement_id,
            agreement_version,
        )
        legal_review = None
        if legal_row is not None:
            legal_review = JurisdictionLegalReview(
                jurisdiction_code=legal_row["jurisdiction_code"],
                agreement_id=legal_row["agreement_id"],
                agreement_version=legal_row["agreement_version"],
                status=ApprovalStatus(legal_row["status"]),
                reviewed_at=legal_row["reviewed_at"],
                reviewer_reference=legal_row["reviewer_reference"],
                evidence_refs=tuple(json.loads(legal_row["evidence_refs_json"])),
            )

        certification_row = approvals.latest_certification(
            jurisdiction_code,
            agreement_id,
            agreement_version,
        )
        certification = None
        if certification_row is not None:
            certification = ProductionCommercializationCertification(
                certification_id=certification_row["certification_id"],
                agreement_id=certification_row["agreement_id"],
                agreement_version=certification_row["agreement_version"],
                jurisdiction_code=certification_row["jurisdiction_code"],
                status=ApprovalStatus(certification_row["status"]),
                certified_at=certification_row["certified_at"],
                reconciliation_verified=bool(
                    certification_row["reconciliation_verified"]
                ),
                security_release_blockers_clear=bool(
                    certification_row["security_release_blockers_clear"]
                ),
                charging_controls_verified=bool(
                    certification_row["charging_controls_verified"]
                ),
                evidence_refs=tuple(
                    json.loads(certification_row["evidence_refs_json"])
                ),
            )

        security_row = self._service.production_infrastructure.latest_security_certification()
        security_certification = None
        if security_row is not None:
            security_certification = ProductionSecurityOperationalCertification(
                certification_id=security_row["certification_id"],
                status=SecurityOperationalApprovalStatus(security_row["status"]),
                certified_at=security_row["certified_at"],
                secrets_management_verified=bool(
                    security_row["secrets_management_verified"]
                ),
                tls_transport_verified=bool(
                    security_row["tls_transport_verified"]
                ),
                access_control_verified=bool(
                    security_row["access_control_verified"]
                ),
                audit_logging_verified=bool(
                    security_row["audit_logging_verified"]
                ),
                monitoring_alerting_verified=bool(
                    security_row["monitoring_alerting_verified"]
                ),
                backup_restore_tested=bool(
                    security_row["backup_restore_tested"]
                ),
                rollback_tested=bool(security_row["rollback_tested"]),
                reconciliation_verified=bool(
                    security_row["reconciliation_verified"]
                ),
                incident_response_verified=bool(
                    security_row["incident_response_verified"]
                ),
                dependency_vulnerability_reviewed=bool(
                    security_row["dependency_vulnerability_reviewed"]
                ),
                reviewer_reference=security_row["reviewer_reference"],
                evidence_refs=tuple(
                    json.loads(security_row["evidence_refs_json"])
                ),
            )

        authority_row = approvals.latest_payment_authority(
            jurisdiction_code,
            agreement_id,
            agreement_version,
        )
        payment_authority = None
        if authority_row is not None:
            payment_authority = PaymentCollectionAuthorityApproval(
                authority_id=authority_row["authority_id"],
                agreement_id=authority_row["agreement_id"],
                agreement_version=authority_row["agreement_version"],
                jurisdiction_code=authority_row["jurisdiction_code"],
                status=ApprovalStatus(authority_row["status"]),
                approved_at=authority_row["approved_at"],
                authority_reference=authority_row["authority_reference"],
                evidence_refs=tuple(
                    json.loads(authority_row["evidence_refs_json"])
                ),
            )

        return assess_production_charging(
            agreement_id=agreement_id,
            agreement_version=agreement_version,
            jurisdiction_code=jurisdiction_code,
            contract_accepted=contract_accepted,
            trial_assessment=trial_assessment,
            legal_review=legal_review,
            certification=certification,
            security_certification=security_certification,
            payment_authority=payment_authority,
        )
