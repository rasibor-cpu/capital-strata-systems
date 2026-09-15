from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query

from backend.app.persistence.services.production_charging_assessment_service import (
    ProductionChargingAssessmentService,
)


def create_production_charging_router() -> APIRouter:
    router = APIRouter()

    @router.get("/api/v1/production-charging/readiness")
    def read_production_charging_readiness(
        customer_id: str = Query(...),
        account_reference: str = Query(...),
        agreement_id: str = Query(...),
        agreement_version: str = Query(...),
        jurisdiction_code: str = Query(...),
        assessed_at: str = Query(...),
    ) -> dict[str, Any]:
        assessment = ProductionChargingAssessmentService().assess(
            customer_id=customer_id,
            account_reference=account_reference,
            agreement_id=agreement_id,
            agreement_version=agreement_version,
            jurisdiction_code=jurisdiction_code,
            assessed_at=assessed_at,
        )
        return {
            "charging_allowed": assessment.allowed,
            "reason_codes": list(assessment.reason_codes),
            "agreement_id": assessment.agreement_id,
            "agreement_version": assessment.agreement_version,
            "jurisdiction_code": assessment.jurisdiction_code,
            "fee_collection_allowed": assessment.fee_collection_allowed,
            "payment_initiation_allowed": assessment.payment_initiation_allowed,
            "client_funds_deduction_allowed": (
                assessment.client_funds_deduction_allowed
            ),
            "automatic_debit_allowed": assessment.automatic_debit_allowed,
            "broker_execution_authority": False,
            "trading_execution_authority": False,
            "broker_withdrawal_allowed": False,
            "read_only_assessment": True,
        }

    return router
