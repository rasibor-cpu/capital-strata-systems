from __future__ import annotations

import json
from typing import Optional

from backend.app.persistence.services.persistence_service import PersistenceService
from backend.commercialization.customer_notifications import (
    CustomerNotificationIntent,
    CustomerNotificationType,
)
from backend.commercialization.notification_delivery_provider import (
    NotificationChannel,
    NotificationDeliveryPreflight,
    NotificationProviderConfiguration,
    NotificationProviderStatus,
    assess_notification_delivery_preflight,
)


class NotificationDeliveryPreflightService:
    """Read-only notification delivery preflight."""

    def __init__(self, persistence_service: Optional[PersistenceService] = None) -> None:
        self._service = persistence_service or PersistenceService()

    def assess(
        self,
        *,
        notification_id: str,
        provider_id: str,
    ) -> NotificationDeliveryPreflight:
        intent_row = self._service.launch_operations.get_notification_intent(
            notification_id
        )
        if intent_row is None:
            return NotificationDeliveryPreflight(
                allowed=False,
                reason_codes=("NOTIFICATION_INTENT_MISSING",),
                provider_id=provider_id,
                notification_id=notification_id,
            )

        provider_row = (
            self._service.launch_operations
            .get_notification_provider_configuration(provider_id)
        )
        if provider_row is None:
            return NotificationDeliveryPreflight(
                allowed=False,
                reason_codes=("NOTIFICATION_PROVIDER_CONFIGURATION_MISSING",),
                provider_id=provider_id,
                notification_id=notification_id,
            )

        intent = CustomerNotificationIntent(
            notification_id=intent_row["notification_id"],
            customer_id=intent_row["customer_id"],
            account_reference=intent_row["account_reference"],
            notification_type=CustomerNotificationType(
                intent_row["notification_type"]
            ),
            scheduled_for=intent_row["scheduled_for"],
            policy_id=intent_row["policy_id"],
            evidence_refs=tuple(json.loads(intent_row["evidence_refs_json"])),
        )
        provider = NotificationProviderConfiguration(
            provider_id=provider_row["provider_id"],
            channel=NotificationChannel(provider_row["channel"]),
            status=NotificationProviderStatus(provider_row["status"]),
            environment=provider_row["environment"],
            provider_account_reference=provider_row[
                "provider_account_reference"
            ],
            approval_reference=provider_row["approval_reference"],
            evidence_refs=tuple(
                json.loads(provider_row["evidence_refs_json"])
            ),
        )
        return assess_notification_delivery_preflight(
            intent=intent,
            provider=provider,
        )
