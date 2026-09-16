import sqlite3

import pytest

import backend.app.persistence.migrations.runner as migration_runner
import backend.app.persistence.repositories.base_repository as base_repository
from backend.app.persistence.services.persistence_service import PersistenceService
from backend.app.persistence.services.trial_contract_enrollment_service import (
    TrialContractEnrollmentService,
)
from backend.commercialization.trial_contract import (
    CommercialAgreementSnapshot,
    TrialContractError,
)


REFS = ("contract:hash",)
DISCLOSURE = (
    "Your free trial ends after the stated trial period. "
    "If you do not cancel before expiry, paid CSS begins automatically."
)


def _service(monkeypatch):
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    monkeypatch.setattr(base_repository, "get_connection", lambda: conn)
    monkeypatch.setattr(migration_runner, "get_connection", lambda: conn)
    return conn, PersistenceService()


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
    return agreement


def test_enrollment_derives_exact_expiry_from_governing_agreement(monkeypatch):
    conn, persistence = _service(monkeypatch)
    try:
        agreement = _seed(persistence)
        enrollment = TrialContractEnrollmentService(persistence).enroll(
            customer_id="CUST-1",
            account_reference="account:A",
            agreement_id="AGR-1",
            agreement_version="v1",
            accepted_at="2026-09-15T14:00:00Z",
            displayed_pricing_summary=agreement.pricing_summary,
            displayed_conversion_disclosure=DISCLOSURE,
            acceptance_audit_reference="accept:1",
            evidence_refs=("accept:evidence",),
        )
        assert enrollment.trial_start_at == "2026-09-15T14:00:00Z"
        assert enrollment.trial_expires_at == "2026-10-15T14:00:00Z"
    finally:
        conn.close()


def test_customer_cannot_enroll_against_mismatched_pricing(monkeypatch):
    conn, persistence = _service(monkeypatch)
    try:
        _seed(persistence)
        with pytest.raises(TrialContractError, match="displayed pricing"):
            TrialContractEnrollmentService(persistence).enroll(
                customer_id="CUST-1",
                account_reference="account:A",
                agreement_id="AGR-1",
                agreement_version="v1",
                accepted_at="2026-09-15T14:00:00Z",
                displayed_pricing_summary="different pricing",
                displayed_conversion_disclosure=DISCLOSURE,
                acceptance_audit_reference="accept:bad",
                evidence_refs=("accept:evidence",),
            )
    finally:
        conn.close()


def test_customer_cannot_enroll_against_unknown_agreement_version(monkeypatch):
    conn, persistence = _service(monkeypatch)
    try:
        agreement = _seed(persistence)
        with pytest.raises(TrialContractError, match="governing commercial agreement is missing"):
            TrialContractEnrollmentService(persistence).enroll(
                customer_id="CUST-1",
                account_reference="account:A",
                agreement_id="AGR-1",
                agreement_version="v2",
                accepted_at="2026-09-15T14:00:00Z",
                displayed_pricing_summary=agreement.pricing_summary,
                displayed_conversion_disclosure=DISCLOSURE,
                acceptance_audit_reference="accept:stale-version",
                evidence_refs=("accept:evidence",),
            )
    finally:
        conn.close()
