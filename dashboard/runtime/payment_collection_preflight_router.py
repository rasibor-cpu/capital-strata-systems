from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query

from backend.app.persistence.services.payment_collection_preflight_service import (
    PaymentCollectionPreflightService,
)


def create_payment_collection_preflight_router() -> APIRouter:
    router = APIRouter()

    @router.get("/api/v1/payment-collection/preflight")
    def read_payment_collection_preflight(
        provider_id: str = Query(...),
        customer_id: str = Query(...),
        account_reference: str = Query(...),
        agreement_id: str = Query(...),
        agreement_version: str = Query(...),
        jurisdiction_code: str = Query(...),
        assessed_at: str = Query(...),
    ) -> dict[str, Any]:
        result = PaymentCollectionPreflightService().assess(
            provider_id=provider_id,
            customer_id=customer_id,
            account_reference=account_reference,
            agreement_id=agreement_id,
            agreement_version=agreement_version,
            jurisdiction_code=jurisdiction_code,
            assessed_at=assessed_at,
        )
        return {
            "collection_preflight_allowed": result.allowed,
            "reason_codes": list(result.reason_codes),
            "provider_id": result.provider_id,
            "collection_endpoint_available": False,
            "money_movement_executed": False,
            "trading_execution_authority": False,
            "read_only": True,
        }

    return router
