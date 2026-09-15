from backend.commercialization.trial_contract import (
    CommercialAgreementSnapshot,
    TrialCancellation,
    TrialConversionStatus,
    TrialEnrollment,
    assess_trial_conversion,
)


DISCLOSURE = (
    "Your free trial ends on 2026-10-01T00:00:00Z. If you do not cancel "
    "before that time, your paid CSS service begins automatically."
)
REFS = ("contract:hash",)


def _agreement():
    return CommercialAgreementSnapshot(
        agreement_id="AGR-1",
        agreement_version="v1",
        jurisdiction_code="CA-ON",
        pricing_plan_id="PLAN-A",
        pricing_summary="20% of qualifying CSS new economic gain; separate disclosed platform terms.",
        trial_duration_days=30,
        automatic_conversion_disclosure=DISCLOSURE,
        effective_from="2026-09-01T00:00:00Z",
        evidence_refs=REFS,
    )


def _enrollment():
    return TrialEnrollment(
        customer_id="CUST-1",
        account_reference="account:A",
        agreement_id="AGR-1",
        agreement_version="v1",
        pricing_plan_id="PLAN-A",
        accepted_at="2026-09-01T00:00:00Z",
        trial_start_at="2026-09-01T00:00:00Z",
        trial_expires_at="2026-10-01T00:00:00Z",
        displayed_pricing_summary=_agreement().pricing_summary,
        displayed_conversion_disclosure=DISCLOSURE,
        acceptance_audit_reference="acceptance:1",
        evidence_refs=REFS,
    )


def test_trial_active_before_expiry():
    result = assess_trial_conversion(
        _agreement(),
        _enrollment(),
        assessed_at="2026-09-20T00:00:00Z",
    )
    assert result.status is TrialConversionStatus.TRIAL_ACTIVE
    assert result.automatic_conversion_allowed is False


def test_uncanceled_trial_is_eligible_only_after_expiry():
    result = assess_trial_conversion(
        _agreement(),
        _enrollment(),
        assessed_at="2026-10-01T00:00:00Z",
    )
    assert result.status is TrialConversionStatus.ELIGIBLE_TO_CONVERT
    assert result.automatic_conversion_allowed is True
    assert result.money_movement_allowed is False
    assert result.payment_execution_allowed is False


def test_pre_expiry_cancellation_blocks_conversion():
    cancellation = TrialCancellation(
        customer_id="CUST-1",
        account_reference="account:A",
        canceled_at="2026-09-30T23:59:59Z",
        cancellation_audit_reference="cancel:1",
        evidence_refs=("cancel:evidence",),
    )
    result = assess_trial_conversion(
        _agreement(),
        _enrollment(),
        assessed_at="2026-10-02T00:00:00Z",
        cancellation=cancellation,
    )
    assert result.status is TrialConversionStatus.CANCELED
    assert result.automatic_conversion_allowed is False


def test_mismatched_contract_version_fails_closed():
    enrollment = TrialEnrollment(
        customer_id="CUST-1",
        account_reference="account:A",
        agreement_id="AGR-1",
        agreement_version="v0",
        pricing_plan_id="PLAN-A",
        accepted_at="2026-09-01T00:00:00Z",
        trial_start_at="2026-09-01T00:00:00Z",
        trial_expires_at="2026-10-01T00:00:00Z",
        displayed_pricing_summary=_agreement().pricing_summary,
        displayed_conversion_disclosure=DISCLOSURE,
        acceptance_audit_reference="acceptance:old",
        evidence_refs=REFS,
    )
    result = assess_trial_conversion(
        _agreement(),
        enrollment,
        assessed_at="2026-10-02T00:00:00Z",
    )
    assert result.status is TrialConversionStatus.BLOCKED
    assert result.automatic_conversion_allowed is False


def test_pricing_or_disclosure_mismatch_fails_closed():
    enrollment = TrialEnrollment(
        customer_id="CUST-1",
        account_reference="account:A",
        agreement_id="AGR-1",
        agreement_version="v1",
        pricing_plan_id="PLAN-A",
        accepted_at="2026-09-01T00:00:00Z",
        trial_start_at="2026-09-01T00:00:00Z",
        trial_expires_at="2026-10-01T00:00:00Z",
        displayed_pricing_summary="different pricing",
        displayed_conversion_disclosure=DISCLOSURE,
        acceptance_audit_reference="acceptance:bad",
        evidence_refs=REFS,
    )
    result = assess_trial_conversion(
        _agreement(),
        enrollment,
        assessed_at="2026-10-02T00:00:00Z",
    )
    assert result.status is TrialConversionStatus.BLOCKED
