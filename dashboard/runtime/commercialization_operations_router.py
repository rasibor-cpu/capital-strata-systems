from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Query, Request

from backend.app.persistence.services.commercialization_operations_status_service import (
    CommercializationOperationsStatusService,
)
from backend.app.auth.session_dependency import authorization_for_commercial_route
from dashboard.runtime.commercial_governance_router import token_store_session_resolver
from engine.commercial.commercial_authorization import (
    BearerSessionResolver,
    CommercialAuthorizer,
    actor_from_bearer,
)


def create_commercialization_operations_router(
    *,
    session_resolver: BearerSessionResolver = token_store_session_resolver,
    authorizer: Optional[CommercialAuthorizer] = None,
) -> APIRouter:
    """Requires an operator session (bearer, or the web session cookie) with commercial view rights.

    Previously unauthenticated: leaked per-customer UAT/dossier/provider
    operations status for any guessed customer_id.
    """
    router = APIRouter()
    authorizer_ = authorizer or CommercialAuthorizer()

    @router.get("/api/v1/commercialization-operations/status")
    def read_commercialization_operations_status(
        http_request: Request,
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
        actor_from_bearer(
            authorization_for_commercial_route(http_request, mutating=False), "commercial_view_obligations",
            session_resolver=session_resolver, authorizer=authorizer_,
        )
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
