import sqlite3

import backend.app.persistence.migrations.runner as migration_runner
import backend.app.persistence.repositories.base_repository as base_repository
from backend.app.persistence.services.persistence_service import PersistenceService
from backend.app.persistence.services.commercialization_release_status_service import (
    CommercializationReleaseStatusService,
)
from backend.commercialization.commercialization_release_status import (
    CommercializationTechnicalValidation,
)


REFS = ("ci:run-57",)


def _setup(monkeypatch):
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    monkeypatch.setattr(base_repository, "get_connection", lambda: conn)
    monkeypatch.setattr(migration_runner, "get_connection", lambda: conn)
    return conn, PersistenceService()


def test_missing_technical_and_commercial_evidence_stays_blocked(monkeypatch):
    conn, service = _setup(monkeypatch)
    try:
        result = CommercializationReleaseStatusService(service).assess(
            customer_id="CUST-1",
            account_reference="account:A",
            agreement_id="AGR-1",
            agreement_version="v1",
            jurisdiction_code="CA-ON",
            assessed_at="2026-10-05T00:00:00Z",
        )
        assert result.production_ready is False
        assert "TECHNICAL_VALIDATION_MISSING" in result.reason_codes
        assert any(
            reason.startswith("CHARGING_GATE:")
            for reason in result.reason_codes
        )
    finally:
        conn.close()


def test_stored_green_ci_removes_technical_blocker_but_not_legal_blockers(monkeypatch):
    conn, service = _setup(monkeypatch)
    try:
        service.commercialization_technical_validations.create_validation(
            CommercializationTechnicalValidation(
                validation_id="VAL-1931",
                commit_sha="cf1c9939043221e4f57eae724e8df1b98faeb7d3",
                validated_at="2026-09-15T20:13:26Z",
                test_count=1931,
                full_regression_passed=True,
                governance_validation_passed=True,
                commercialization_consistency_passed=True,
                evidence_refs=REFS,
            )
        )

        result = CommercializationReleaseStatusService(service).assess(
            customer_id="CUST-1",
            account_reference="account:A",
            agreement_id="AGR-1",
            agreement_version="v1",
            jurisdiction_code="CA-ON",
            assessed_at="2026-10-05T00:00:00Z",
        )
        assert result.production_ready is False
        assert result.validation_id == "VAL-1931"
        assert result.validated_commit_sha == (
            "cf1c9939043221e4f57eae724e8df1b98faeb7d3"
        )
        assert "TECHNICAL_VALIDATION_MISSING" not in result.reason_codes
        assert "CHARGING_GATE:LEGAL_REVIEW_MISSING" in result.reason_codes
    finally:
        conn.close()
