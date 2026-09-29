from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Header, Query

from backend.app.persistence.services.commercialization_release_status_service import (
    CommercializationReleaseStatusService,
)
from dashboard.runtime.commercial_governance_router import token_store_session_resolver
from engine.commercial.commercial_authorization import (
    BearerSessionResolver,
    CommercialAuthorizer,
    actor_from_bearer,
)


def create_commercialization_release_router(
    *,
    session_resolver: BearerSessionResolver = token_store_session_resolver,
    authorizer: Optional[CommercialAuthorizer] = None,
) -> APIRouter:
    """Requires a bearer session with commercial view rights.

    Previously unauthenticated: leaked per-customer production-release/
    payment-provider readiness for any guessed customer_id.
    """
    router = APIRouter()
    authorizer_ = authorizer or CommercialAuthorizer()

    @router.get("/api/v1/commercialization-release/readiness")
    def read_commercialization_release_readiness(
        customer_id: str = Query(...),
        account_reference: str = Query(...),
        agreement_id: str = Query(...),
        agreement_version: str = Query(...),
        jurisdiction_code: str = Query(...),
        assessed_at: str = Query(...),
        provider_id: str = Query(...),
        validation_id: str | None = Query(default=None),
        authorization: Optional[str] = Header(default=None),
    ) -> dict[str, Any]:
        actor_from_bearer(
            authorization, "commercial_view_obligations",
            session_resolver=session_resolver, authorizer=authorizer_,
        )
        assessment = CommercializationReleaseStatusService().assess(
            customer_id=customer_id,
            account_reference=account_reference,
            agreement_id=agreement_id,
            agreement_version=agreement_version,
            jurisdiction_code=jurisdiction_code,
            assessed_at=assessed_at,
            provider_id=provider_id,
            validation_id=validation_id,
        )
        return {
            "production_commercial_ready": assessment.production_ready,
            "live_fee_collection_release_allowed": (
                assessment.live_fee_collection_release_allowed
            ),
            "charging_allowed": assessment.charging_allowed,
            "payment_provider_ready": assessment.payment_provider_ready,
            "reason_codes": list(assessment.reason_codes),
            "validation_id": assessment.validation_id,
            "validated_commit_sha": assessment.validated_commit_sha,
            "trading_execution_authority": False,
            "broker_execution_authority": False,
            "read_only_assessment": True,
        }

    return router
