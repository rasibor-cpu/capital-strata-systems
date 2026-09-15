from __future__ import annotations

import json
from typing import Any

from backend.app.persistence.repositories.base_repository import BaseRepository
from backend.commercialization.commercialization_release_status import (
    CommercializationTechnicalValidation,
)


class CommercializationTechnicalValidationRepository(BaseRepository):
    """Append-only persistence for CI/governance commercialization evidence."""

    def create_validation(
        self,
        record: CommercializationTechnicalValidation,
    ) -> None:
        self.execute(
            """
            INSERT INTO commercial_technical_validations (
                validation_id,
                commit_sha,
                validated_at,
                test_count,
                full_regression_passed,
                governance_validation_passed,
                commercialization_consistency_passed,
                evidence_refs_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                record.validation_id,
                record.commit_sha,
                record.validated_at,
                record.test_count,
                int(record.full_regression_passed),
                int(record.governance_validation_passed),
                int(record.commercialization_consistency_passed),
                json.dumps(list(record.evidence_refs), separators=(",", ":")),
            ),
        )

    def get_by_validation_id(
        self,
        validation_id: str,
    ) -> dict[str, Any] | None:
        row = self.fetch_one(
            """
            SELECT *
            FROM commercial_technical_validations
            WHERE validation_id = ?
            """,
            (validation_id,),
        )
        return dict(row) if row is not None else None

    def latest_validation(self) -> dict[str, Any] | None:
        row = self.fetch_one(
            """
            SELECT *
            FROM commercial_technical_validations
            ORDER BY validated_at DESC, validation_id DESC
            LIMIT 1
            """
        )
        return dict(row) if row is not None else None
