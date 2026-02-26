"""
Persistent Journal Engine – Phase 14b
Capital Strata Systems

Append-only JSONL journal.
Rebuildable.
Deterministic.
Institutional-grade.
"""

from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from decimal import Decimal
from typing import List
import hashlib
import json
from pathlib import Path


JOURNAL_FILE = Path("audit_logs") / "journal.jsonl"


@dataclass(frozen=True)
class JournalEntry:
    journal_id: str
    ticket_id: str
    execution_date: str
    account_no: str
    side: str
    amount: Decimal
    currency: str
    created_at: datetime
    entry_hash: str


class JournalRegistry:

    def __init__(self):
        Path("audit_logs").mkdir(parents=True, exist_ok=True)
        self._entries: List[JournalEntry] = []
        self._load_from_disk()

    # ------------------------------------------------------------

    def _generate_hash(self, payload: dict) -> str:
        payload_str = json.dumps(payload, sort_keys=True)
        return hashlib.sha256(payload_str.encode()).hexdigest()

    # ------------------------------------------------------------

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
        self._write_to_disk(entry)

        return entry

    # ------------------------------------------------------------

    def _write_to_disk(self, entry: JournalEntry) -> None:
        record = asdict(entry)
        record["amount"] = str(record["amount"])
        record["created_at"] = record["created_at"].isoformat()

        with JOURNAL_FILE.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")

    # ------------------------------------------------------------

    def _load_from_disk(self) -> None:
        if not JOURNAL_FILE.exists():
            return

        with JOURNAL_FILE.open("r", encoding="utf-8") as f:
            for line in f:
                data = json.loads(line)

                entry = JournalEntry(
                    journal_id=data["journal_id"],
                    ticket_id=data["ticket_id"],
                    execution_date=data["execution_date"],
                    account_no=data["account_no"],
                    side=data["side"],
                    amount=Decimal(data["amount"]),
                    currency=data["currency"],
                    created_at=datetime.fromisoformat(data["created_at"]),
                    entry_hash=data["entry_hash"],
                )

                self._entries.append(entry)

    # ------------------------------------------------------------

    def all(self) -> List[JournalEntry]:
        return list(self._entries)