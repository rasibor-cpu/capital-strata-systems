from __future__ import annotations

import json
from typing import Optional

from backend.app.persistence.services.persistence_service import PersistenceService
from backend.commercialization.trial_contract import (
    CommercialAgreementSnapshot,
    TrialCancellation,
    TrialConversionAssessment,
    TrialContractError,
    TrialEnrollment,
    assess_trial_conversion,
)


class TrialConversionAssessmentService:
    """Read-only conversion assessment from durable commercial evidence."""

    def __init__(self, persistence_service: Optional[PersistenceService] = None) -> None:
        self._service = persistence_service or PersistenceService()

    def assess(
        self,
        *,
        customer_id: str,
        account_reference: str,
        agreement_id: str,
        agreement_version: str,
        assessed_at: str,
    ) -> TrialConversionAssessment:
        repo = self._service.trial_contracts

        agreement_row = repo.get_agreement(agreement_id, agreement_version)
        if agreement_row is None:
            raise TrialContractError("governing commercial agreement is missing")

        enrollment_row = repo.get_enrollment(
            customer_id=customer_id,
            account_reference=account_reference,
            agreement_id=agreement_id,
            agreement_version=agreement_version,
        )
        if enrollment_row is None:
            raise TrialContractError("accepted trial enrollment is missing")

        agreement = CommercialAgreementSnapshot(
            agreement_id=agreement_row["agreement_id"],
            agreement_version=agreement_row["agreement_version"],
            jurisdiction_code=agreement_row["jurisdiction_code"],
            pricing_plan_id=agreement_row["pricing_plan_id"],
            pricing_summary=agreement_row["pricing_summary"],
            trial_duration_days=int(agreement_row["trial_duration_days"]),
            automatic_conversion_disclosure=agreement_row[
                "automatic_conversion_disclosure"
            ],
            effective_from=agreement_row["effective_from"],
            evidence_refs=tuple(json.loads(agreement_row["evidence_refs_json"])),
        )

        enrollment = TrialEnrollment(
            customer_id=enrollment_row["customer_id"],
            account_reference=enrollment_row["account_reference"],
            agreement_id=enrollment_row["agreement_id"],
            agreement_version=enrollment_row["agreement_version"],
            pricing_plan_id=enrollment_row["pricing_plan_id"],
            accepted_at=enrollment_row["accepted_at"],
            trial_start_at=enrollment_row["trial_start_at"],
            trial_expires_at=enrollment_row["trial_expires_at"],
            displayed_pricing_summary=enrollment_row["displayed_pricing_summary"],
            displayed_conversion_disclosure=enrollment_row[
                "displayed_conversion_disclosure"
            ],
            acceptance_audit_reference=enrollment_row[
                "acceptance_audit_reference"
            ],
            evidence_refs=tuple(json.loads(enrollment_row["evidence_refs_json"])),
        )

        cancellation = None
        cancellation_row = repo.latest_cancellation(
            customer_id=customer_id,
            account_reference=account_reference,
        )
        if cancellation_row is not None:
            cancellation = TrialCancellation(
                customer_id=cancellation_row["customer_id"],
                account_reference=cancellation_row["account_reference"],
                canceled_at=cancellation_row["canceled_at"],
                cancellation_audit_reference=cancellation_row[
                    "cancellation_audit_reference"
                ],
                evidence_refs=tuple(
                    json.loads(cancellation_row["evidence_refs_json"])
                ),
            )

        return assess_trial_conversion(
            agreement,
            enrollment,
            assessed_at=assessed_at,
            cancellation=cancellation,
        )
