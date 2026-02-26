"""
Journal Engine – Phase 14
Capital Strata Systems

Append-only journal.
No mutation.
Institutional-grade foundation.
"""

from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from decimal import Decimal
from typing import List, Dict
import hashlib
import json


@dataclass(frozen=True)
class JournalEntry:
    journal_id: str
    ticket_id: str
    execution_date: str
    account_no: str
    side: str   # DR / CR
    amount: Decimal
    currency: str
    created_at: datetime
    entry_hash: str


class JournalRegistry:
    """
    In-memory journal (Phase 14a)
    Will later move to persistent storage.
    """

    def __init__(self):
        self._entries: List[JournalEntry] = []

    def _generate_hash(self, payload: Dict) -> str:
        payload_str = json.dumps(payload, sort_keys=True)
        return hashlib.sha256(payload_str.encode()).hexdigest()

    def append(
        self,
        ticket_id: str,
        execution_date: str,
        account_no: str,
        side: str,
        amount: Decimal,
        currency: str,
    ) -> JournalEntry:

        payload = {
            "ticket_id": ticket_id,
            "execution_date": execution_date,
            "account_no": account_no,
            "side": side,
            "amount": str(amount),
            "currency": currency,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        entry_hash = self._generate_hash(payload)

        entry = JournalEntry(
            journal_id=f"J-{len(self._entries)+1:08d}",
            ticket_id=ticket_id,
            execution_date=execution_date,
            account_no=account_no,
            side=side,
            amount=amount,
            currency=currency,
            created_at=datetime.now(timezone.utc),
            entry_hash=entry_hash,
        )

        self._entries.append(entry)
        return entry

    def all(self) -> List[JournalEntry]:
        return list(self._entries)