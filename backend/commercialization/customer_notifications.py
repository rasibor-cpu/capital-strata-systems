from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Tuple


class CustomerNotificationType(str, Enum):
    TRIAL_EXPIRY_REMINDER = "TRIAL_EXPIRY_REMINDER"
    CONVERSION_CONFIRMATION = "CONVERSION_CONFIRMATION"
    CANCELLATION_CONFIRMATION = "CANCELLATION_CONFIRMATION"
    FEE_STATEMENT = "FEE_STATEMENT"
    MATERIAL_TERMS_REACCEPTANCE = "MATERIAL_TERMS_REACCEPTANCE"


@dataclass(frozen=True, slots=True)
class CustomerNotificationPolicy:
    policy_id: str
    jurisdiction_code: str
    notification_type: CustomerNotificationType
    lead_time_hours: int
    approved_for_production: bool
    approval_reference: str | None
    evidence_refs: Tuple[str, ...]

    def __post_init__(self) -> None:
        for name in ("policy_id", "jurisdiction_code"):
            value = getattr(self, name)
            if not value or value != value.strip():
                raise ValueError(f"{name} is required and must be canonical")
        if not isinstance(self.notification_type, CustomerNotificationType):
            raise TypeError("notification_type must be CustomerNotificationType")
        if self.lead_time_hours < 0:
            raise ValueError("lead_time_hours cannot be negative")
        if not isinstance(self.evidence_refs, tuple) or not self.evidence_refs:
            raise ValueError("notification policy requires evidence refs")
        if self.approved_for_production and not self.approval_reference:
            raise ValueError("approved notification policy requires approval reference")


@dataclass(frozen=True, slots=True)
class CustomerNotificationIntent:
    notification_id: str
    customer_id: str
    account_reference: str
    notification_type: CustomerNotificationType
    scheduled_for: str
    policy_id: str
    evidence_refs: Tuple[str, ...]

    def __post_init__(self) -> None:
        for name in (
            "notification_id",
            "customer_id",
            "account_reference",
            "scheduled_for",
            "policy_id",
        ):
            value = getattr(self, name)
            if not value or value != value.strip():
                raise ValueError(f"{name} is required and must be canonical")
        if not isinstance(self.notification_type, CustomerNotificationType):
            raise TypeError("notification_type must be CustomerNotificationType")
        if not isinstance(self.evidence_refs, tuple) or not self.evidence_refs:
            raise ValueError("notification intent requires evidence refs")

    @property
    def delivery_authorized(self) -> bool:
        return False


def build_notification_intent(
    *,
    notification_id: str,
    customer_id: str,
    account_reference: str,
    notification_type: CustomerNotificationType,
    scheduled_for: str,
    policy: CustomerNotificationPolicy,
    evidence_refs: Tuple[str, ...],
) -> CustomerNotificationIntent:
    if not isinstance(policy, CustomerNotificationPolicy):
        raise TypeError("policy must be CustomerNotificationPolicy")
    if policy.notification_type != notification_type:
        raise ValueError("notification policy type mismatch")
    if not policy.approved_for_production:
        raise ValueError("notification policy is not production approved")

    return CustomerNotificationIntent(
        notification_id=notification_id,
        customer_id=customer_id,
        account_reference=account_reference,
        notification_type=notification_type,
        scheduled_for=scheduled_for,
        policy_id=policy.policy_id,
        evidence_refs=tuple(dict.fromkeys((*policy.evidence_refs, *evidence_refs))),
    )
