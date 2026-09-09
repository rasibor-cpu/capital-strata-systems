from __future__ import annotations

import json
from typing import Any

from backend.app.persistence.repositories.base_repository import BaseRepository
from backend.commercialization.fx_conversion import CommercialFxConversionEvidence


class FxConversionEvidenceRepository(BaseRepository):
    """Append-only documentary evidence; duplicate IDs never overwrite history."""

    def create_conversion(self, record: CommercialFxConversionEvidence) -> None:
        if not isinstance(record, CommercialFxConversionEvidence):
            raise TypeError("record must be CommercialFxConversionEvidence")
        self.execute(
            """
            INSERT INTO commercial_fx_conversion_evidence (
                fx_conversion_id, source_currency, target_currency, source_amount, converted_amount, fx_rate, rate_effective_at, rate_source_reference, evidence_refs_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                record.fx_conversion_id,
                record.source_currency,
                record.target_currency,
                str(record.source_amount),
                str(record.converted_amount),
                str(record.fx_rate),
                record.rate_effective_at,
                record.rate_source_reference,
                json.dumps(list(record.evidence_refs), separators=(",", ":")),
            ),
        )

    def get_by_fx_conversion_id(self, fx_conversion_id: str) -> dict[str, Any] | None:
        row = self.fetch_one(
            "SELECT * FROM commercial_fx_conversion_evidence WHERE fx_conversion_id = ?",
            (fx_conversion_id,),
        )
        return dict(row) if row is not None else None

    def list_all(self) -> list[dict[str, Any]]:
        return [dict(row) for row in self.fetch_all(
            "SELECT * FROM commercial_fx_conversion_evidence ORDER BY created_at, fx_conversion_id"
        )]
