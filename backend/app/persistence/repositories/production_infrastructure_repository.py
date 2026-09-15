from __future__ import annotations

import json
from typing import Any

from backend.app.persistence.repositories.base_repository import BaseRepository
from backend.commercialization.payment_collection_provider import (
    PaymentProviderConfiguration,
)
from backend.commercialization.production_security_certification import (
    ProductionSecurityOperationalCertification,
)


class ProductionInfrastructureRepository(BaseRepository):
    def create_security_certification(
        self,
        record: ProductionSecurityOperationalCertification,
    ) -> None:
        self.execute(
            """
            INSERT INTO production_security_operational_certifications (
                certification_id, status, certified_at,
                secrets_management_verified, tls_transport_verified,
                access_control_verified, audit_logging_verified,
                monitoring_alerting_verified, backup_restore_tested,
                rollback_tested, reconciliation_verified,
                incident_response_verified, dependency_vulnerability_reviewed,
                reviewer_reference, evidence_refs_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                record.certification_id,
                record.status.value,
                record.certified_at,
                int(record.secrets_management_verified),
                int(record.tls_transport_verified),
                int(record.access_control_verified),
                int(record.audit_logging_verified),
                int(record.monitoring_alerting_verified),
                int(record.backup_restore_tested),
                int(record.rollback_tested),
                int(record.reconciliation_verified),
                int(record.incident_response_verified),
                int(record.dependency_vulnerability_reviewed),
                record.reviewer_reference,
                json.dumps(list(record.evidence_refs), separators=(",", ":")),
            ),
        )

    def latest_security_certification(self) -> dict[str, Any] | None:
        row = self.fetch_one(
            """
            SELECT *
            FROM production_security_operational_certifications
            ORDER BY certified_at DESC, certification_id DESC
            LIMIT 1
            """
        )
        return dict(row) if row is not None else None

    def create_payment_provider_configuration(
        self,
        record: PaymentProviderConfiguration,
    ) -> None:
        self.execute(
            """
            INSERT INTO payment_provider_configurations (
                provider_id, status, environment,
                provider_account_reference, approval_reference,
                evidence_refs_json
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                record.provider_id,
                record.status.value,
                record.environment,
                record.provider_account_reference,
                record.approval_reference,
                json.dumps(list(record.evidence_refs), separators=(",", ":")),
            ),
        )

    def get_payment_provider_configuration(
        self,
        provider_id: str,
    ) -> dict[str, Any] | None:
        row = self.fetch_one(
            """
            SELECT *
            FROM payment_provider_configurations
            WHERE provider_id = ?
            """,
            (provider_id,),
        )
        return dict(row) if row is not None else None
