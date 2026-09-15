import sqlite3

import backend.app.persistence.migrations.runner as migration_runner
import backend.app.persistence.repositories.base_repository as base_repository
from backend.app.persistence.services.persistence_service import PersistenceService
from backend.app.persistence.services.trial_conversion_assessment_service import (
    TrialConversionAssessmentService,
)
from backend.commercialization.trial_contract import (
    CommercialAgreementSnapshot,
    TrialCancellation,
    TrialConversionStatus,
    TrialEnrollment,
)


REFS = ("contract:hash",)
DISCLOSURE = (
    "Your free trial ends on 2026-10-01T00:00:00Z. "
    "If you do not cancel before that time, paid CSS begins automatically."
)


def _seed(service):
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


def test_persisted_uncanceled_trial_becomes_documentarily_eligible(monkeypatch):
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    monkeypatch.setattr(base_repository, "get_connection", lambda: conn)
    monkeypatch.setattr(migration_runner, "get_connection", lambda: conn)
    try:
        service = PersistenceService()
        _seed(service)
        result = TrialConversionAssessmentService(service).assess(
            customer_id="CUST-1",
            account_reference="account:A",
            agreement_id="AGR-1",
            agreement_version="v1",
            assessed_at="2026-10-02T00:00:00Z",
        )
        assert result.status is TrialConversionStatus.ELIGIBLE_TO_CONVERT
        assert result.automatic_conversion_allowed is True
        assert result.payment_execution_allowed is False
    finally:
        conn.close()


def test_persisted_pre_expiry_cancellation_blocks_conversion(monkeypatch):
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    monkeypatch.setattr(base_repository, "get_connection", lambda: conn)
    monkeypatch.setattr(migration_runner, "get_connection", lambda: conn)
    try:
        service = PersistenceService()
        _seed(service)
        service.trial_contracts.create_cancellation(
            TrialCancellation(
                customer_id="CUST-1",
                account_reference="account:A",
                canceled_at="2026-09-30T23:59:59Z",
                cancellation_audit_reference="cancel:1",
                evidence_refs=("cancel:evidence",),
            )
        )
        result = TrialConversionAssessmentService(service).assess(
            customer_id="CUST-1",
            account_reference="account:A",
            agreement_id="AGR-1",
            agreement_version="v1",
            assessed_at="2026-10-02T00:00:00Z",
        )
        assert result.status is TrialConversionStatus.CANCELED
        assert result.automatic_conversion_allowed is False
    finally:
        conn.close()
