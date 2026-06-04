"""In-memory acceptance storage used by Phase 1 validation services."""

from __future__ import annotations

from collections import defaultdict

from backend.app.compliance.legal_acceptance import LegalAcceptanceRecord


class InMemoryLegalAcceptanceStore:
    """Simple acceptance record authority for Phase 1."""

    def __init__(self) -> None:
        self._records = defaultdict(dict)

    def save(self, record: LegalAcceptanceRecord) -> None:
        self._records[record.user_id][record.acceptance_type] = record

    def get(
        self,
        user_id: str,
        acceptance_type: str,
    ) -> LegalAcceptanceRecord | None:
        return self._records.get(user_id, {}).get(acceptance_type)

    def get_all_for_user(
        self,
        user_id: str,
    ) -> dict[str, LegalAcceptanceRecord]:
        return dict(self._records.get(user_id, {}))