from __future__ import annotations

from dataclasses import dataclass
from typing import Dict

from backend.commercialization.customer_notifications import (
    CustomerNotificationIntent,
)
from backend.commercialization.notification_delivery_provider import (
    NotificationDeliveryPreflight,
)


@dataclass(frozen=True, slots=True)
class SandboxNotificationReceipt:
    provider_id: str
    notification_id: str
    provider_message_id: str
    status: str


class SandboxNotificationDeliveryProvider:
    """Deterministic non-production notification simulator."""

    def __init__(self) -> None:
        self._receipts: Dict[str, SandboxNotificationReceipt] = {}

    @property
    def provider_id(self) -> str:
        return "CSS-SANDBOX-NOTIFY"

    def send(
        self,
        intent: CustomerNotificationIntent,
        preflight: NotificationDeliveryPreflight,
    ) -> str:
        if not isinstance(intent, CustomerNotificationIntent):
            raise TypeError("intent must be CustomerNotificationIntent")
        if not isinstance(preflight, NotificationDeliveryPreflight):
            raise TypeError("preflight must be NotificationDeliveryPreflight")
        if not preflight.allowed:
            raise RuntimeError("sandbox notification preflight is not allowed")
        if preflight.provider_id != self.provider_id:
            raise RuntimeError("sandbox notification provider identity mismatch")
        if preflight.notification_id != intent.notification_id:
            raise RuntimeError("notification identity mismatch")

        existing = self._receipts.get(intent.notification_id)
        if existing is not None:
            return existing.provider_message_id

        message_id = f"sandbox-notify:{intent.notification_id}"
        self._receipts[intent.notification_id] = SandboxNotificationReceipt(
            provider_id=self.provider_id,
            notification_id=intent.notification_id,
            provider_message_id=message_id,
            status="SIMULATED_DELIVERED",
        )
        return message_id

    def receipt_for(
        self,
        notification_id: str,
    ) -> SandboxNotificationReceipt | None:
        return self._receipts.get(notification_id)
