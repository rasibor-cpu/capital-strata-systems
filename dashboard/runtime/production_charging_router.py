from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Header, Query

from backend.app.persistence.services.production_charging_assessment_service import (
    ProductionChargingAssessmentService,
)
from dashboard.runtime.commercial_governance_router import token_store_session_resolver
from engine.commercial.commercial_authorization import (
    BearerSessionResolver,
    CommercialAuthorizer,
    actor_from_bearer,
)


def create_production_charging_router(
    *,
    session_resolver: BearerSessionResolver = token_store_session_resolver,
    authorizer: Optional[CommercialAuthorizer] = None,
) -> APIRouter:
    """Every route requires a bearer session with commercial view rights.

    Previously unauthenticated: leaked per-customer legal-review/certification/
    payment-authority readiness for any guessed customer_id/account_reference.
    """
    router = APIRouter()
    authorizer_ = authorizer or CommercialAuthorizer()

    @router.get("/api/v1/production-charging/readiness")
    def read_production_charging_readiness(
        customer_id: str = Query(...),
        account_reference: str = Query(...),
        agreement_id: str = Query(...),
        agreement_version: str = Query(...),
        jurisdiction_code: str = Query(...),
        assessed_at: str = Query(...),
        authorization: Optional[str] = Header(default=None),
    ) -> dict[str, Any]:
        actor_from_bearer(
            authorization, "commercial_view_obligations",
            session_resolver=session_resolver, authorizer=authorizer_,
        )
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
