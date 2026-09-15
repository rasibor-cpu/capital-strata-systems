from __future__ import annotations

import json
from typing import Any

from backend.app.persistence.repositories.base_repository import BaseRepository
from backend.commercialization.production_charging_gate import (
    JurisdictionLegalReview,
    PaymentCollectionAuthorityApproval,
    ProductionCommercializationCertification,
)


class ProductionChargingApprovalRepository(BaseRepository):
    """Append-only evidence for legal, production, and collection approvals."""

    def create_legal_review(self, record: JurisdictionLegalReview) -> None:
        self.execute(
            """
            INSERT INTO commercial_jurisdiction_legal_reviews (
                jurisdiction_code, agreement_id, agreement_version, status,
                reviewed_at, reviewer_reference, evidence_refs_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                record.jurisdiction_code,
                record.agreement_id,
                record.agreement_version,
                record.status.value,
                record.reviewed_at,
                record.reviewer_reference,
                json.dumps(list(record.evidence_refs), separators=(",", ":")),
            ),
        )

    def create_certification(
        self,
        record: ProductionCommercializationCertification,
    ) -> None:
        self.execute(
            """
            INSERT INTO commercial_production_certifications (
                certification_id, agreement_id, agreement_version,
                jurisdiction_code, status, certified_at,
                reconciliation_verified, security_release_blockers_clear,
                charging_controls_verified, evidence_refs_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                record.certification_id,
                record.agreement_id,
                record.agreement_version,
                record.jurisdiction_code,
                record.status.value,
                record.certified_at,
                int(record.reconciliation_verified),
                int(record.security_release_blockers_clear),
                int(record.charging_controls_verified),
                json.dumps(list(record.evidence_refs), separators=(",", ":")),
            ),
        )

    def create_payment_authority(
        self,
        record: PaymentCollectionAuthorityApproval,
    ) -> None:
        self.execute(
            """
            INSERT INTO commercial_payment_collection_authorities (
                authority_id, agreement_id, agreement_version,
                jurisdiction_code, status, approved_at, authority_reference,
                evidence_refs_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                record.authority_id,
                record.agreement_id,
                record.agreement_version,
                record.jurisdiction_code,
                record.status.value,
                record.approved_at,
                record.authority_reference,
                json.dumps(list(record.evidence_refs), separators=(",", ":")),
            ),
        )

    def latest_legal_review(
        self,
        jurisdiction_code: str,
        agreement_id: str,
        agreement_version: str,
    ) -> dict[str, Any] | None:
        row = self.fetch_one(
            """
            SELECT * FROM commercial_jurisdiction_legal_reviews
            WHERE jurisdiction_code = ?
              AND agreement_id = ?
              AND agreement_version = ?
            ORDER BY reviewed_at DESC, legal_review_id DESC
            LIMIT 1
            """,
            (jurisdiction_code, agreement_id, agreement_version),
        )
        return dict(row) if row is not None else None

    def latest_certification(
        self,
        jurisdiction_code: str,
        agreement_id: str,
        agreement_version: str,
    ) -> dict[str, Any] | None:
        row = self.fetch_one(
            """
            SELECT * FROM commercial_production_certifications
            WHERE jurisdiction_code = ?
              AND agreement_id = ?
              AND agreement_version = ?
            ORDER BY certified_at DESC, certification_id DESC
            LIMIT 1
            """,
            (jurisdiction_code, agreement_id, agreement_version),
        )
        return dict(row) if row is not None else None

    def latest_payment_authority(
        self,
        jurisdiction_code: str,
        agreement_id: str,
        agreement_version: str,
    ) -> dict[str, Any] | None:
        row = self.fetch_one(
            """
            SELECT * FROM commercial_payment_collection_authorities
            WHERE jurisdiction_code = ?
              AND agreement_id = ?
              AND agreement_version = ?
            ORDER BY approved_at DESC, authority_id DESC
            LIMIT 1
            """,
            (jurisdiction_code, agreement_id, agreement_version),
        )
        return dict(row) if row is not None else None
