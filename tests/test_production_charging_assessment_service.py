import sqlite3

import backend.app.persistence.migrations.runner as migration_runner
import backend.app.persistence.repositories.base_repository as base_repository
from backend.app.persistence.services.persistence_service import PersistenceService
from backend.app.persistence.services.production_charging_assessment_service import (
    ProductionChargingAssessmentService,
)
from backend.commercialization.production_charging_gate import (
    ApprovalStatus,
    JurisdictionLegalReview,
    PaymentCollectionAuthorityApproval,
    ProductionCommercializationCertification,
)
from backend.commercialization.trial_contract import (
    CommercialAgreementSnapshot,
    TrialEnrollment,
)


REFS = ("evidence:1",)
DISCLOSURE = "Trial converts to paid service if not canceled before expiry."


def _setup(monkeypatch):
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    monkeypatch.setattr(base_repository, "get_connection", lambda: conn)
    monkeypatch.setattr(migration_runner, "get_connection", lambda: conn)
    return conn, PersistenceService()


def _seed_contract(service):
    agreement = CommercialAgreementSnapshot(
        agreement_id="AGR-1",
        agreement_version="v1",
        jurisdiction_code="CA-ON",
        pricing_plan_id="PLAN-A",
        pricing_summary="20% of qualifying CSS new economic gain.",
        trial_duration_days=30,
        automatic_conversion_disclosure=DISCLOSURE,
        effective_from="2026-09-01T00:00:00Z",
        evidence_refs=REFS,
    )
    service.trial_contracts.create_agreement(agreement)
    service.trial_contracts.create_enrollment(
        TrialEnrollment(
            customer_id="CUST-1",
            account_reference="account:A",
            agreement_id="AGR-1",
            agreement_version="v1",
            pricing_plan_id="PLAN-A",
            accepted_at="2026-09-01T00:00:00Z",
            trial_start_at="2026-09-01T00:00:00Z",
            trial_expires_at="2026-10-01T00:00:00Z",
            displayed_pricing_summary=agreement.pricing_summary,
            displayed_conversion_disclosure=DISCLOSURE,
            acceptance_audit_reference="accept:1",
            evidence_refs=REFS,
        )
    )


def _seed_approvals(service):
    repo = service.production_charging_approvals
    repo.create_legal_review(
        JurisdictionLegalReview(
            jurisdiction_code="CA-ON",
            agreement_id="AGR-1",
            agreement_version="v1",
            status=ApprovalStatus.APPROVED,
            reviewed_at="2026-10-02T00:00:00Z",
            reviewer_reference="counsel:1",
            evidence_refs=REFS,
        )
    )
    repo.create_certification(
        ProductionCommercializationCertification(
            certification_id="CERT-1",
            agreement_id="AGR-1",
            agreement_version="v1",
            jurisdiction_code="CA-ON",
            status=ApprovalStatus.APPROVED,
            certified_at="2026-10-03T00:00:00Z",
            reconciliation_verified=True,
            security_release_blockers_clear=True,
            charging_controls_verified=True,
            evidence_refs=REFS,
        )
    )
    repo.create_payment_authority(
        PaymentCollectionAuthorityApproval(
            authority_id="AUTH-1",
            agreement_id="AGR-1",
            agreement_version="v1",
            jurisdiction_code="CA-ON",
            status=ApprovalStatus.APPROVED,
            approved_at="2026-10-04T00:00:00Z",
            authority_reference="payments:1",
            evidence_refs=REFS,
        )
    )


def test_no_stored_approvals_means_charging_is_blocked(monkeypatch):
    conn, service = _setup(monkeypatch)
    try:
        _seed_contract(service)
        result = ProductionChargingAssessmentService(service).assess(
            customer_id="CUST-1",
            account_reference="account:A",
            agreement_id="AGR-1",
            agreement_version="v1",
            jurisdiction_code="CA-ON",
            assessed_at="2026-10-05T00:00:00Z",
        )
        assert result.allowed is False
        assert "LEGAL_REVIEW_MISSING" in result.reason_codes
        assert "PRODUCTION_CERTIFICATION_MISSING" in result.reason_codes
        assert "PAYMENT_COLLECTION_AUTHORITY_MISSING" in result.reason_codes
    finally:
        conn.close()


def test_all_canonical_approvals_allow_collection_but_never_trading(monkeypatch):
    conn, service = _setup(monkeypatch)
    try:
        _seed_contract(service)
        _seed_approvals(service)
        result = ProductionChargingAssessmentService(service).assess(
            customer_id="CUST-1",
            account_reference="account:A",
            agreement_id="AGR-1",
            agreement_version="v1",
            jurisdiction_code="CA-ON",
            assessed_at="2026-10-05T00:00:00Z",
        )
        assert result.allowed is True
        assert result.fee_collection_allowed is True
        assert result.trading_execution_authority is False
        assert result.broker_execution_authority is False
    finally:
        conn.close()


def test_missing_customer_acceptance_blocks_even_with_approvals(monkeypatch):
    conn, service = _setup(monkeypatch)
    try:
        _seed_approvals(service)
        result = ProductionChargingAssessmentService(service).assess(
            customer_id="CUST-MISSING",
            account_reference="account:missing",
            agreement_id="AGR-1",
            agreement_version="v1",
            jurisdiction_code="CA-ON",
            assessed_at="2026-10-05T00:00:00Z",
        )
        assert result.allowed is False
        assert "CONTRACT_NOT_ACCEPTED" in result.reason_codes
        assert "TRIAL_ASSESSMENT_MISSING" in result.reason_codes
    finally:
        conn.close()
