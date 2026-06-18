from collections import defaultdict
from typing import Protocol

from backend.app.compliance.legal_acceptance import LegalAcceptanceRecord


class LegalAcceptanceStore(Protocol):
    def save(self, record: LegalAcceptanceRecord) -> LegalAcceptanceRecord:
        ...

    def latest_for(
        self,
        user_id: str,
        acceptance_type: str,
    ) -> LegalAcceptanceRecord | None:
        ...

    def all_for_user(self, user_id: str) -> tuple[LegalAcceptanceRecord, ...]:
        ...


class InMemoryLegalAcceptanceStore:
    def __init__(self) -> None:
        self._records = defaultdict(list)

    def save(self, record: LegalAcceptanceRecord) -> LegalAcceptanceRecord:
        self._records[record.user_id].append(record)
        return record

    def latest_for(
        self,
        user_id: str,
        acceptance_type: str,
    ) -> LegalAcceptanceRecord | None:
        records = [
            record
            for record in self._records.get(user_id, [])
            if record.acceptance_type == acceptance_type
        ]

        if not records:
            return None

        return max(records, key=lambda record: record.accepted_at)

    def all_for_user(self, user_id: str) -> tuple[LegalAcceptanceRecord, ...]:
        return tuple(self._records.get(user_id, ()))

    def get(
        self,
        user_id: str,
        acceptance_type: str,
    ) -> LegalAcceptanceRecord | None:
        return self.latest_for(user_id, acceptance_type)