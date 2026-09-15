import pytest

from backend.commercialization.customer_notifications import (
    CustomerNotificationIntent,
    CustomerNotificationType,
)
from backend.commercialization.notification_delivery_provider import (
    DisabledNotificationDeliveryProvider,
    NotificationChannel,
    NotificationProviderConfiguration,
    NotificationProviderStatus,
    assess_notification_delivery_preflight,
)


REFS = ("evidence:1",)


def _intent():
    return CustomerNotificationIntent(
        notification_id="N-1",
        customer_id="CUST-1",
        account_reference="account:A",
        notification_type=CustomerNotificationType.TRIAL_EXPIRY_REMINDER,
        scheduled_for="2026-10-12T14:00:00Z",
        policy_id="NOTICE-1",
        evidence_refs=REFS,
    )


def test_disabled_notification_provider_blocks_delivery():
    provider = NotificationProviderConfiguration(
        provider_id="NOTIFY-DISABLED",
        channel=NotificationChannel.EMAIL,
        status=NotificationProviderStatus.DISABLED,
        environment="production",
        provider_account_reference=None,
        approval_reference=None,
        evidence_refs=REFS,
    )
    result = assess_notification_delivery_preflight(
        intent=_intent(),
        provider=provider,
    )
    assert result.allowed is False
    assert "NOTIFICATION_PROVIDER_NOT_APPROVED" in result.reason_codes


def test_disabled_delivery_adapter_never_sends():
    provider = NotificationProviderConfiguration(
        provider_id="NOTIFY-DISABLED",
        channel=NotificationChannel.EMAIL,
        status=NotificationProviderStatus.DISABLED,
        environment="production",
        provider_account_reference=None,
        approval_reference=None,
        evidence_refs=REFS,
    )
    preflight = assess_notification_delivery_preflight(
        intent=_intent(),
        provider=provider,
    )
    with pytest.raises(RuntimeError, match="disabled"):
        DisabledNotificationDeliveryProvider().send(_intent(), preflight)
