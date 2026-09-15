import sqlite3

import backend.app.persistence.migrations.runner as migration_runner
import backend.app.persistence.repositories.base_repository as base_repository
from backend.app.persistence.services.payment_collection_preflight_service import (
    PaymentCollectionPreflightService,
)
from backend.app.persistence.services.persistence_service import PersistenceService
from backend.commercialization.payment_collection_provider import (
    PaymentProviderConfiguration,
    PaymentProviderStatus,
)
from backend.commercialization.production_security_certification import (
    ProductionSecurityOperationalCertification,
    SecurityOperationalApprovalStatus,
)


REFS = ("evidence:1",)


def _setup(monkeypatch):
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    monkeypatch.setattr(base_repository, "get_connection", lambda: conn)
    monkeypatch.setattr(migration_runner, "get_connection", lambda: conn)
    return conn, PersistenceService()


def test_security_and_provider_configuration_persist(monkeypatch):
    conn, service = _setup(monkeypatch)
    try:
        security = ProductionSecurityOperationalCertification(
            certification_id="SEC-1",
            status=SecurityOperationalApprovalStatus.APPROVED,
            certified_at="2026-10-01T00:00:00Z",
            secrets_management_verified=True,
            tls_transport_verified=True,
            access_control_verified=True,
            audit_logging_verified=True,
            monitoring_alerting_verified=True,
            backup_restore_tested=True,
            rollback_tested=True,
            reconciliation_verified=True,
            incident_response_verified=True,
            dependency_vulnerability_reviewed=True,
            reviewer_reference="security:review",
            evidence_refs=REFS,
        )
        service.production_infrastructure.create_security_certification(security)
        row = service.production_infrastructure.latest_security_certification()
        assert row["certification_id"] == "SEC-1"
        assert row["rollback_tested"] == 1

        provider = PaymentProviderConfiguration(
            provider_id="PROVIDER-1",
            status=PaymentProviderStatus.APPROVED,
            environment="production",
            provider_account_reference="merchant:1",
            approval_reference="payments:approval",
            evidence_refs=REFS,
        )
        service.production_infrastructure.create_payment_provider_configuration(
            provider
        )
        provider_row = (
            service.production_infrastructure
            .get_payment_provider_configuration("PROVIDER-1")
        )
        assert provider_row["status"] == "APPROVED"
    finally:
        conn.close()


def test_missing_provider_configuration_blocks_preflight(monkeypatch):
    conn, service = _setup(monkeypatch)
    try:
        result = PaymentCollectionPreflightService(service).assess(
            provider_id="MISSING",
            customer_id="CUST-1",
            account_reference="account:A",
            agreement_id="AGR-1",
            agreement_version="v1",
            jurisdiction_code="CA-ON",
            assessed_at="2026-10-05T00:00:00Z",
        )
        assert result.allowed is False
        assert result.reason_codes == (
            "PAYMENT_PROVIDER_CONFIGURATION_MISSING",
        )
    finally:
        conn.close()
