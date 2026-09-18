from backend.commercialization.production_closure_status import (
    ClosureWorkstream,
    assess_production_closure,
)
from backend.commercialization.production_evidence_handoff import (
    ProductionEvidenceValidation,
)


def _valid_evidence():
    return ProductionEvidenceValidation(
        valid_for_review=True,
        missing_categories=(),
        invalid_reasons=(),
        package_id="PROD-1",
        jurisdiction_code="CA-ON",
        agreement_id="AGR-1",
        agreement_version="v1",
    )


def test_missing_evidence_keeps_every_external_workstream_open():
    result = assess_production_closure(
        internal_engineering_complete=True,
        evidence_validation=None,
    )
    assert result.work_items_closed is False
    assert result.production_authorized is False
    assert ClosureWorkstream.LEGAL_REGULATORY.value in result.open_workstreams
    assert ClosureWorkstream.PAYMENT_PROVIDER.value in result.open_workstreams
    assert ClosureWorkstream.RELEASE_OWNER.value in result.open_workstreams
    assert result.money_movement_authorized is False
    assert result.trading_execution_authority is False


def test_valid_external_package_still_does_not_self_authorize_production():
    result = assess_production_closure(
        internal_engineering_complete=True,
        evidence_validation=_valid_evidence(),
    )
    assert result.work_items_closed is True
    assert result.external_evidence_valid_for_review is True
    assert result.production_authorized is False
    assert result.open_workstreams == ()
    assert (
        "READY_FOR_CONTROLLED_HUMAN_EVIDENCE_IMPORT_AND_FINAL_AUTHORIZATION"
        in result.blocker_reasons
    )
