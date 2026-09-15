from backend.commercialization.production_charging_gate import (
    ApprovalStatus,
    JurisdictionLegalReview,
    ProductionCommercializationCertification,
    PaymentCollectionAuthorityApproval,
    assess_production_charging,
)
from backend.commercialization.trial_contract import (
    TrialConversionAssessment,
    TrialConversionStatus,
)


REFS = ("evidence:1",)


def _trial(status=TrialConversionStatus.ELIGIBLE_TO_CONVERT):
    return TrialConversionAssessment(
        status=status,
        assessed_at="2026-10-20T00:00:00Z",
        agreement_id="AGR-1",
        agreement_version="v1",
        pricing_plan_id="PLAN-A",
        reason="test assessment",
    )


def _legal(status=ApprovalStatus.APPROVED):
    return JurisdictionLegalReview(
        jurisdiction_code="CA-ON",
        agreement_id="AGR-1",
        agreement_version="v1",
        status=status,
        reviewed_at="2026-10-10T00:00:00Z",
        reviewer_reference="counsel:approval",
        evidence_refs=REFS,
    )


def _payment_authority(status=ApprovalStatus.APPROVED):
    return PaymentCollectionAuthorityApproval(
        authority_id="AUTH-1",
        agreement_id="AGR-1",
        agreement_version="v1",
        jurisdiction_code="CA-ON",
        status=status,
        approved_at="2026-10-16T00:00:00Z",
        authority_reference="payments:approval",
        evidence_refs=REFS,
    )


def _cert(**changes):
    values = dict(
        certification_id="CERT-1",
        agreement_id="AGR-1",
        agreement_version="v1",
        jurisdiction_code="CA-ON",
        status=ApprovalStatus.APPROVED,
        certified_at="2026-10-15T00:00:00Z",
        reconciliation_verified=True,
        security_release_blockers_clear=True,
        charging_controls_verified=True,
        evidence_refs=REFS,
    )
    values.update(changes)
    return ProductionCommercializationCertification(**values)


def _assess(**changes):
    values = dict(
        agreement_id="AGR-1",
        agreement_version="v1",
        jurisdiction_code="CA-ON",
        contract_accepted=True,
        trial_assessment=_trial(),
        legal_review=_legal(),
        certification=_cert(),
        payment_authority=_payment_authority(),
    )
    values.update(changes)
    return assess_production_charging(**values)


def test_all_independent_gates_must_pass_before_collection_is_allowed():
    result = _assess()
    assert result.allowed is True
    assert result.reason_codes == ()
    assert result.fee_collection_allowed is True
    assert result.payment_initiation_allowed is True


def test_charging_gate_remains_separate_from_trading_authority():
    result = _assess()
    assert result.allowed is True
    assert result.broker_execution_authority is False
    assert result.trading_execution_authority is False
    assert result.broker_withdrawal_allowed is False


def test_unapproved_legal_review_blocks_charging():
    result = _assess(legal_review=_legal(ApprovalStatus.PENDING))
    assert result.allowed is False
    assert "LEGAL_REVIEW_NOT_APPROVED" in result.reason_codes


def test_trial_not_converted_blocks_charging():
    result = _assess(
        trial_assessment=_trial(TrialConversionStatus.TRIAL_ACTIVE)
    )
    assert result.allowed is False
    assert "TRIAL_NOT_ELIGIBLE_FOR_PAID_SERVICE" in result.reason_codes


def test_any_production_control_failure_blocks_charging():
    result = _assess(
        certification=_cert(
            reconciliation_verified=False,
            security_release_blockers_clear=False,
            charging_controls_verified=False,
        )
    )
    assert result.allowed is False
    assert "RECONCILIATION_NOT_VERIFIED" in result.reason_codes
    assert "SECURITY_RELEASE_BLOCKERS_ACTIVE" in result.reason_codes
    assert "CHARGING_CONTROLS_NOT_VERIFIED" in result.reason_codes


def test_payment_authority_is_independent_required_gate():
    result = _assess(
        payment_authority=_payment_authority(ApprovalStatus.PENDING)
    )
    assert result.allowed is False
    assert "PAYMENT_COLLECTION_AUTHORITY_NOT_APPROVED" in result.reason_codes


def test_contract_acceptance_is_required():
    result = _assess(contract_accepted=False)
    assert result.allowed is False
    assert "CONTRACT_NOT_ACCEPTED" in result.reason_codes


def test_missing_approval_evidence_fails_closed():
    result = _assess(
        legal_review=None,
        certification=None,
        payment_authority=None,
        trial_assessment=None,
    )
    assert result.allowed is False
    assert "LEGAL_REVIEW_MISSING" in result.reason_codes
    assert "PRODUCTION_CERTIFICATION_MISSING" in result.reason_codes
    assert "PAYMENT_COLLECTION_AUTHORITY_MISSING" in result.reason_codes
    assert "TRIAL_ASSESSMENT_MISSING" in result.reason_codes
