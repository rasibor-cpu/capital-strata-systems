from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Protocol, Tuple

from backend.commercialization.customer_notifications import (
    CustomerNotificationIntent,
)


class NotificationProviderStatus(str, Enum):
    DISABLED = "DISABLED"
    APPROVED = "APPROVED"


class NotificationChannel(str, Enum):
    EMAIL = "EMAIL"
    SMS = "SMS"
    PUSH = "PUSH"


@dataclass(frozen=True, slots=True)
class NotificationProviderConfiguration:
    provider_id: str
    channel: NotificationChannel
    status: NotificationProviderStatus
    environment: str
    provider_account_reference: str | None
    approval_reference: str | None
    evidence_refs: Tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.provider_id or self.provider_id != self.provider_id.strip():
            raise ValueError("provider_id is required and must be canonical")
        if not isinstance(self.channel, NotificationChannel):
            raise TypeError("channel must be NotificationChannel")
        if not isinstance(self.status, NotificationProviderStatus):
            raise TypeError("status must be NotificationProviderStatus")
        if not self.environment or self.environment != self.environment.strip():
            raise ValueError("environment is required and must be canonical")
        if not isinstance(self.evidence_refs, tuple) or not self.evidence_refs:
            raise ValueError("notification provider requires evidence refs")
        if self.status == NotificationProviderStatus.APPROVED:
            if not self.provider_account_reference or not self.approval_reference:
                raise ValueError(
                    "approved notification provider requires account and approval references"
                )


@dataclass(frozen=True, slots=True)
class NotificationDeliveryPreflight:
    allowed: bool
    reason_codes: Tuple[str, ...]
    provider_id: str
    notification_id: str


def assess_notification_delivery_preflight(
    *,
    intent: CustomerNotificationIntent,
    provider: NotificationProviderConfiguration,
) -> NotificationDeliveryPreflight:
    if not isinstance(intent, CustomerNotificationIntent):
        raise TypeError("intent must be CustomerNotificationIntent")
    if not isinstance(provider, NotificationProviderConfiguration):
        raise TypeError("provider must be NotificationProviderConfiguration")

    reasons = []
    if provider.status != NotificationProviderStatus.APPROVED:
        reasons.append("NOTIFICATION_PROVIDER_NOT_APPROVED")
    if intent.delivery_authorized:
        reasons.append("INTENT_MUST_NOT_SELF_AUTHORIZE_DELIVERY")

    return NotificationDeliveryPreflight(
        allowed=not reasons,
        reason_codes=tuple(reasons),
        provider_id=provider.provider_id,
        notification_id=intent.notification_id,
    )


class NotificationDeliveryProvider(Protocol):
    @property
    def provider_id(self) -> str:
        ...

    def send(
        self,
        intent: CustomerNotificationIntent,
        preflight: NotificationDeliveryPreflight,
    ) -> str:
        ...


class DisabledNotificationDeliveryProvider:
    @property
    def provider_id(self) -> str:
        return "DISABLED"

    def send(
        self,
        intent: CustomerNotificationIntent,
        preflight: NotificationDeliveryPreflight,
    ) -> str:
        if not isinstance(intent, CustomerNotificationIntent):
            raise TypeError("intent must be CustomerNotificationIntent")
        if not isinstance(preflight, NotificationDeliveryPreflight):
            raise TypeError("preflight must be NotificationDeliveryPreflight")
        raise RuntimeError("notification delivery provider is disabled")
