from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query

from backend.app.persistence.services.commercialization_release_status_service import (
    CommercializationReleaseStatusService,
)


def create_commercialization_release_router() -> APIRouter:
    router = APIRouter()

    @router.get("/api/v1/commercialization-release/readiness")
    def read_commercialization_release_readiness(
        customer_id: str = Query(...),
        account_reference: str = Query(...),
        agreement_id: str = Query(...),
        agreement_version: str = Query(...),
        jurisdiction_code: str = Query(...),
        assessed_at: str = Query(...),
        validation_id: str | None = Query(default=None),
    ) -> dict[str, Any]:
        assessment = CommercializationReleaseStatusService().assess(
            customer_id=customer_id,
            account_reference=account_reference,
            agreement_id=agreement_id,
            agreement_version=agreement_version,
            jurisdiction_code=jurisdiction_code,
            assessed_at=assessed_at,
            validation_id=validation_id,
        )
        return {
            "production_commercial_ready": assessment.production_ready,
            "live_fee_collection_release_allowed": (
                assessment.live_fee_collection_release_allowed
            ),
            "charging_allowed": assessment.charging_allowed,
            "reason_codes": list(assessment.reason_codes),
            "validation_id": assessment.validation_id,
            "validated_commit_sha": assessment.validated_commit_sha,
            "trading_execution_authority": False,
            "broker_execution_authority": False,
            "read_only_assessment": True,
        }

    return router
