from backend.commercialization.commercialization_release_status import (
    CommercializationTechnicalValidation,
    assess_commercialization_release,
)
from backend.commercialization.production_charging_gate import (
    ProductionChargingAssessment,
)


REFS = ("ci:run",)


def _validation(**changes):
    values = dict(
        validation_id="VAL-1",
        commit_sha="abc123",
        validated_at="2026-09-15T20:13:26Z",
        test_count=1931,
        full_regression_passed=True,
        governance_validation_passed=True,
        commercialization_consistency_passed=True,
        evidence_refs=REFS,
    )
    values.update(changes)
    return CommercializationTechnicalValidation(**values)


def _charging(allowed=True, reasons=()):
    return ProductionChargingAssessment(
        allowed=allowed,
        reason_codes=tuple(reasons),
        agreement_id="AGR-1",
        agreement_version="v1",
        jurisdiction_code="CA-ON",
    )


def test_release_requires_both_technical_validation_and_charging_gate():
    result = assess_commercialization_release(
        technical_validation=_validation(),
        charging_assessment=_charging(),
    )
    assert result.production_ready is True
    assert result.live_fee_collection_release_allowed is True
    assert result.trading_execution_authority is False


def test_missing_technical_validation_blocks_release():
    result = assess_commercialization_release(
        technical_validation=None,
        charging_assessment=_charging(),
    )
    assert result.production_ready is False
    assert "TECHNICAL_VALIDATION_MISSING" in result.reason_codes


def test_charging_blockers_are_preserved_in_release_reasons():
    result = assess_commercialization_release(
        technical_validation=_validation(),
        charging_assessment=_charging(
            False,
            ("LEGAL_REVIEW_MISSING", "PAYMENT_COLLECTION_AUTHORITY_MISSING"),
        ),
    )
    assert result.production_ready is False
    assert "CHARGING_GATE:LEGAL_REVIEW_MISSING" in result.reason_codes
    assert (
        "CHARGING_GATE:PAYMENT_COLLECTION_AUTHORITY_MISSING"
        in result.reason_codes
    )


def test_failed_ci_component_blocks_release():
    result = assess_commercialization_release(
        technical_validation=_validation(full_regression_passed=False),
        charging_assessment=_charging(),
    )
    assert result.production_ready is False
    assert "FULL_REGRESSION_NOT_PASSED" in result.reason_codes
