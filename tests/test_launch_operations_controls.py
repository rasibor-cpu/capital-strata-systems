import pytest

from backend.commercialization.customer_notifications import (
    CustomerNotificationPolicy,
    CustomerNotificationType,
    build_notification_intent,
)
from backend.commercialization.launch_evidence_dossier import (
    LaunchEvidenceCategory,
    LaunchEvidenceItem,
    REQUIRED_LAUNCH_EVIDENCE,
    assess_launch_dossier,
)


REFS = ("evidence:1",)


def test_notification_policy_must_be_approved_before_intent_creation():
    policy = CustomerNotificationPolicy(
        policy_id="NOTICE-1",
        jurisdiction_code="CA-ON",
        notification_type=CustomerNotificationType.TRIAL_EXPIRY_REMINDER,
        lead_time_hours=72,
        approved_for_production=False,
        approval_reference=None,
        evidence_refs=REFS,
    )
    with pytest.raises(ValueError, match="not production approved"):
        build_notification_intent(
            notification_id="N-1",
            customer_id="CUST-1",
            account_reference="account:A",
            notification_type=CustomerNotificationType.TRIAL_EXPIRY_REMINDER,
            scheduled_for="2026-10-12T14:00:00Z",
            policy=policy,
            evidence_refs=REFS,
        )


def test_notification_intent_never_self_authorizes_delivery():
    policy = CustomerNotificationPolicy(
        policy_id="NOTICE-1",
        jurisdiction_code="CA-ON",
        notification_type=CustomerNotificationType.TRIAL_EXPIRY_REMINDER,
        lead_time_hours=72,
        approved_for_production=True,
        approval_reference="counsel:notice-policy",
        evidence_refs=REFS,
    )
    intent = build_notification_intent(
        notification_id="N-1",
        customer_id="CUST-1",
        account_reference="account:A",
        notification_type=CustomerNotificationType.TRIAL_EXPIRY_REMINDER,
        scheduled_for="2026-10-12T14:00:00Z",
        policy=policy,
        evidence_refs=REFS,
    )
    assert intent.delivery_authorized is False


def test_launch_dossier_requires_every_category_approved():
    items = tuple(
        LaunchEvidenceItem(category=c, evidence_reference=f"evidence:{c.value}", approved=True)
        for c in REQUIRED_LAUNCH_EVIDENCE
    )
    assert assess_launch_dossier(items).complete is True


def test_launch_dossier_exposes_missing_or_unapproved_evidence():
    items = (
        LaunchEvidenceItem(
            category=LaunchEvidenceCategory.TECHNICAL_VALIDATION,
            evidence_reference="ci:run",
            approved=True,
        ),
        LaunchEvidenceItem(
            category=LaunchEvidenceCategory.OWNER_SIGNOFF,
            evidence_reference="owner:pending",
            approved=False,
        ),
    )
    result = assess_launch_dossier(items)
    assert result.complete is False
    assert LaunchEvidenceCategory.OWNER_SIGNOFF in result.unapproved_categories
    assert LaunchEvidenceCategory.APPROVED_CUSTOMER_AGREEMENT in result.missing_categories
