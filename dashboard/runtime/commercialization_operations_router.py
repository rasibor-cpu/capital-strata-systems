from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query

from backend.app.persistence.services.commercialization_operations_status_service import (
    CommercializationOperationsStatusService,
)


def create_commercialization_operations_router() -> APIRouter:
    router = APIRouter()

    @router.get("/api/v1/commercialization-operations/status")
    def read_commercialization_operations_status(
        customer_id: str = Query(...),
        account_reference: str = Query(...),
        agreement_id: str = Query(...),
        agreement_version: str = Query(...),
        jurisdiction_code: str = Query(...),
        assessed_at: str = Query(...),
        provider_id: str = Query(...),
        uat_run_id: str = Query(...),
        dossier_id: str = Query(...),
    ) -> dict[str, Any]:
        return CommercializationOperationsStatusService().build_status(
            customer_id=customer_id,
            account_reference=account_reference,
            agreement_id=agreement_id,
            agreement_version=agreement_version,
            jurisdiction_code=jurisdiction_code,
            assessed_at=assessed_at,
            provider_id=provider_id,
            uat_run_id=uat_run_id,
            dossier_id=dossier_id,
        )

    return router
