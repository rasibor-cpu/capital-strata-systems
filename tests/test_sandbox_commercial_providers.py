from decimal import Decimal

from backend.commercialization.customer_notifications import (
    CustomerNotificationIntent,
    CustomerNotificationType,
)
from backend.commercialization.notification_delivery_provider import (
    NotificationDeliveryPreflight,
)
from backend.commercialization.payment_collection_provider import (
    PaymentCollectionPreflight,
    PaymentCollectionRequest,
)
from backend.commercialization.sandbox_notification_provider import (
    SandboxNotificationDeliveryProvider,
)
from backend.commercialization.sandbox_payment_provider import (
    SandboxPaymentCollectionProvider,
)


REFS = ("test:evidence",)


def test_sandbox_payment_is_deterministic_and_idempotent():
    provider = SandboxPaymentCollectionProvider()
    request = PaymentCollectionRequest(
        collection_id="COLL-1",
        customer_id="TEST-CUST",
        account_reference="test:account",
        amount=Decimal("12.34"),
        currency="USD",
        idempotency_key="test:idem:1",
        invoice_reference="TEST-INV-1",
        evidence_refs=REFS,
    )
    preflight = PaymentCollectionPreflight(
        allowed=True,
        reason_codes=(),
        provider_id=provider.provider_id,
    )
    tx1 = provider.collect(request, preflight)
    tx2 = provider.collect(request, preflight)
    assert tx1 == tx2 == "sandbox-pay:COLL-1"
    assert provider.receipt_for("test:idem:1").status == "SIMULATED_SUCCEEDED"


def test_sandbox_notification_is_deterministic():
    provider = SandboxNotificationDeliveryProvider()
    intent = CustomerNotificationIntent(
        notification_id="TEST-N-1",
        customer_id="TEST-CUST",
        account_reference="test:account",
        notification_type=CustomerNotificationType.TRIAL_EXPIRY_REMINDER,
        scheduled_for="2026-10-01T00:00:00Z",
        policy_id="TEST-NOTICE-POLICY",
        evidence_refs=REFS,
    )
    preflight = NotificationDeliveryPreflight(
        allowed=True,
        reason_codes=(),
        provider_id=provider.provider_id,
        notification_id=intent.notification_id,
    )
    msg1 = provider.send(intent, preflight)
    msg2 = provider.send(intent, preflight)
    assert msg1 == msg2 == "sandbox-notify:TEST-N-1"
    assert provider.receipt_for("TEST-N-1").status == "SIMULATED_DELIVERED"
