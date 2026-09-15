from __future__ import annotations

import json
from typing import Optional

from backend.app.persistence.services.persistence_service import PersistenceService
from backend.app.persistence.services.production_charging_assessment_service import (
    ProductionChargingAssessmentService,
)
from backend.commercialization.commercialization_release_status import (
    CommercializationReleaseAssessment,
    CommercializationTechnicalValidation,
    assess_commercialization_release,
)


class CommercializationReleaseStatusService:
    """Read-only release status from immutable CI and commercial evidence."""

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
        validation_id: str | None = None,
    ) -> CommercializationReleaseAssessment:
        repo = self._service.commercialization_technical_validations

        row = (
            repo.get_by_validation_id(validation_id)
            if validation_id is not None
            else repo.latest_validation()
        )
        validation = None
        if row is not None:
            validation = CommercializationTechnicalValidation(
                validation_id=row["validation_id"],
                commit_sha=row["commit_sha"],
                validated_at=row["validated_at"],
                test_count=int(row["test_count"]),
                full_regression_passed=bool(row["full_regression_passed"]),
                governance_validation_passed=bool(
                    row["governance_validation_passed"]
                ),
                commercialization_consistency_passed=bool(
                    row["commercialization_consistency_passed"]
                ),
                evidence_refs=tuple(json.loads(row["evidence_refs_json"])),
            )

        charging = ProductionChargingAssessmentService(self._service).assess(
            customer_id=customer_id,
            account_reference=account_reference,
            agreement_id=agreement_id,
            agreement_version=agreement_version,
            jurisdiction_code=jurisdiction_code,
            assessed_at=assessed_at,
        )

        return assess_commercialization_release(
            technical_validation=validation,
            charging_assessment=charging,
        )
