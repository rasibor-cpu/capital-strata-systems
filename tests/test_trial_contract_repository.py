import sqlite3

import backend.app.persistence.migrations.runner as migration_runner
import backend.app.persistence.repositories.base_repository as base_repository
from backend.app.persistence.services.persistence_service import PersistenceService
from backend.commercialization.trial_contract import (
    CommercialAgreementSnapshot,
    TrialCancellation,
    TrialEnrollment,
)


REFS = ("contract:hash",)


def test_trial_contract_evidence_persists_immutably(monkeypatch):
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    monkeypatch.setattr(base_repository, "get_connection", lambda: conn)
    monkeypatch.setattr(migration_runner, "get_connection", lambda: conn)

    try:
        service = PersistenceService()

        agreement = CommercialAgreementSnapshot(
            agreement_id="AGR-1",
            agreement_version="v1",
            jurisdiction_code="CA-ON",
            pricing_plan_id="PLAN-A",
            pricing_summary="20% of qualifying CSS new economic gain.",
            trial_duration_days=30,
            automatic_conversion_disclosure=(
                "Your free trial ends on 2026-10-01T00:00:00Z. "
                "If you do not cancel before that time, paid CSS begins automatically."
            ),
            effective_from="2026-09-01T00:00:00Z",
            evidence_refs=REFS,
        )
        service.trial_contracts.create_agreement(agreement)

        enrollment = TrialEnrollment(
            customer_id="CUST-1",
            account_reference="account:A",
            agreement_id="AGR-1",
            agreement_version="v1",
            pricing_plan_id="PLAN-A",
            accepted_at="2026-09-01T00:00:00Z",
            trial_start_at="2026-09-01T00:00:00Z",
            trial_expires_at="2026-10-01T00:00:00Z",
            displayed_pricing_summary=agreement.pricing_summary,
            displayed_conversion_disclosure=agreement.automatic_conversion_disclosure,
            acceptance_audit_reference="accept:1",
            evidence_refs=REFS,
        )
        service.trial_contracts.create_enrollment(enrollment)

        cancellation = TrialCancellation(
            customer_id="CUST-1",
            account_reference="account:A",
            canceled_at="2026-09-30T23:59:59Z",
            cancellation_audit_reference="cancel:1",
            evidence_refs=("cancel:evidence",),
        )
        service.trial_contracts.create_cancellation(cancellation)

        agreement_row = service.trial_contracts.get_agreement("AGR-1", "v1")
        assert agreement_row["pricing_plan_id"] == "PLAN-A"

        enrollment_row = service.trial_contracts.get_enrollment(
            customer_id="CUST-1",
            account_reference="account:A",
            agreement_id="AGR-1",
            agreement_version="v1",
        )
        assert enrollment_row["trial_expires_at"] == "2026-10-01T00:00:00Z"
        assert enrollment_row["acceptance_audit_reference"] == "accept:1"

        cancellation_row = service.trial_contracts.latest_cancellation(
            customer_id="CUST-1",
            account_reference="account:A",
        )
        assert cancellation_row["cancellation_audit_reference"] == "cancel:1"
    finally:
        conn.close()
