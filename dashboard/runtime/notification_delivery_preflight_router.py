from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Header, Query

from backend.app.persistence.services.notification_delivery_preflight_service import (
    NotificationDeliveryPreflightService,
)
from dashboard.runtime.commercial_governance_router import token_store_session_resolver
from engine.commercial.commercial_authorization import (
    BearerSessionResolver,
    CommercialAuthorizer,
    actor_from_bearer,
)


def create_notification_delivery_preflight_router(
    *,
    session_resolver: BearerSessionResolver = token_store_session_resolver,
    authorizer: Optional[CommercialAuthorizer] = None,
) -> APIRouter:
    """Requires a bearer session with commercial view rights.

    Previously unauthenticated: allowed enumerating valid notification_ids
    and their delivery-preflight reason codes.
    """
    router = APIRouter()
    authorizer_ = authorizer or CommercialAuthorizer()

    @router.get("/api/v1/customer-notifications/preflight")
    def read_notification_delivery_preflight(
        notification_id: str = Query(...),
        provider_id: str = Query(...),
        authorization: Optional[str] = Header(default=None),
    ) -> dict[str, Any]:
        actor_from_bearer(
            authorization, "commercial_view_obligations",
            session_resolver=session_resolver, authorizer=authorizer_,
        )
        result = NotificationDeliveryPreflightService().assess(
            notification_id=notification_id,
            provider_id=provider_id,
        )
        return {
            "delivery_preflight_allowed": result.allowed,
            "reason_codes": list(result.reason_codes),
            "provider_id": result.provider_id,
            "notification_id": result.notification_id,
            "send_endpoint_available": False,
            "delivery_executed": False,
            "read_only": True,
        }

    return router
