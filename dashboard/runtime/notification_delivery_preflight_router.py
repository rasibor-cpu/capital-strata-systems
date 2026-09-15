from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query

from backend.app.persistence.services.notification_delivery_preflight_service import (
    NotificationDeliveryPreflightService,
)


def create_notification_delivery_preflight_router() -> APIRouter:
    router = APIRouter()

    @router.get("/api/v1/customer-notifications/preflight")
    def read_notification_delivery_preflight(
        notification_id: str = Query(...),
        provider_id: str = Query(...),
    ) -> dict[str, Any]:
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
