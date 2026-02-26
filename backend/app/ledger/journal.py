"""
Persistent Journal Engine – Phase 14c.0
Capital Strata Systems

Append-only JSONL journal with user metadata for EOD batch review.

Key:
- Backward-compatible loader: older journal lines without new fields still load.
- Append-only, immutable, deterministic.
"""

from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from decimal import Decimal
from typing import List, Optional
import hashlib
import json
from pathlib import Path


JOURNAL_FILE = Path("audit_logs") / "journal.jsonl"


@dataclass(frozen=True)
class JournalEntry:
    journal_id: str
    ticket_id: str
    execution_date: str  # business date for posting
    account_no: str
    side: str            # DR / CR
    amount: Decimal
    currency: str
    created_at: datetime

    # --- NEW (Phase 14c.0): batch review keys ---
    maker_user_id: Optional[str] = None
    checker_user_id: Optional[str] = None
    unit: Optional[str] = None        # branch/team/division/country (optional; future)
    entry_hash: str = ""


class JournalRegistry:
    def __init__(self):
        Path("audit_logs").mkdir(parents=True, exist_ok=True)
        self._entries: List[JournalEntry] = []
        self._load_from_disk()

    def _generate_hash(self, payload: dict) -> str:
        payload_str = json.dumps(payload, sort_keys=True)
        return hashlib.sha256(payload_str.encode()).hexdigest()

    def append(
        self,
        *,
        ticket_id: str,
        execution_date: str,
        account_no: str,
        side: str,
        amount: Decimal,
        currency: str,
        maker_user_id: Optional[str] = None,
        checker_user_id: Optional[str] = None,
        unit: Optional[str] = None,
    ) -> JournalEntry:

        # Hash payload (deterministic)
        payload = {
            "ticket_id": ticket_id,
            "execution_date": execution_date,
            "account_no": account_no,
            "side": side,
            "amount": str(amount),
            "currency": currency,
            "maker_user_id": maker_user_id,
            "checker_user_id": checker_user_id,
            "unit": unit,
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
            maker_user_id=maker_user_id,
            checker_user_id=checker_user_id,
            unit=unit,
            entry_hash=entry_hash,
        )

        self._entries.append(entry)
        self._write_to_disk(entry)
        return entry

    def _write_to_disk(self, entry: JournalEntry) -> None:
        record = asdict(entry)
        record["amount"] = str(record["amount"])
        record["created_at"] = record["created_at"].isoformat()

        with JOURNAL_FILE.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    def _load_from_disk(self) -> None:
        if not JOURNAL_FILE.exists():
            return

        with JOURNAL_FILE.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                data = json.loads(line)

                # Backward compatibility: older lines may not have maker/checker/unit
                entry = JournalEntry(
                    journal_id=data["journal_id"],
                    ticket_id=data["ticket_id"],
                    execution_date=data["execution_date"],
                    account_no=data["account_no"],
                    side=data["side"],
                    amount=Decimal(data["amount"]),
                    currency=data["currency"],
                    created_at=datetime.fromisoformat(data["created_at"]),
                    maker_user_id=data.get("maker_user_id"),
                    checker_user_id=data.get("checker_user_id"),
                    unit=data.get("unit"),
                    entry_hash=data.get("entry_hash", ""),
                )
                self._entries.append(entry)

    def all(self) -> List[JournalEntry]:
        return list(self._entries)