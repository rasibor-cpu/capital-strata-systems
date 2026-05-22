from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Dict, Any
import json
import uuid


class PersistentExecutionJournal:
    """
    Append-only persistent execution journal.

    PCNRASS SAFE:
    - No broker calls
    - No execution authority
    - File-based audit persistence only
    """

    def __init__(self, journal_path: str | None = None) -> None:
        if journal_path is None:
            root = Path(__file__).resolve().parents[3]
            journal_path = str(
                root / "artifacts" / "audit" / "execution_journal.jsonl"
            )

        self.journal_path = Path(journal_path)
        self.journal_path.parent.mkdir(parents=True, exist_ok=True)

    def append_record(
        self,
        *,
        asset_class: str,
        symbol: str,
        mode: str,
        broker: str,
        approved: bool,
        reason: str,
        execution_id: str,
        dry_run: bool,
        metadata: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:

        record = {
            "record_id": str(uuid.uuid4()),
            "timestamp_utc": datetime.utcnow().isoformat(),
            "asset_class": str(asset_class).upper(),
            "symbol": str(symbol).upper(),
            "mode": str(mode).lower(),
            "broker": str(broker).upper(),
            "approved": bool(approved),
            "reason": str(reason),
            "execution_id": str(execution_id),
            "dry_run": bool(dry_run),
            "metadata": dict(metadata or {}),
        }

        with self.journal_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, sort_keys=True) + "\n")

        print(
            f"[PERSISTENT JOURNAL] "
            f"{record['asset_class']} {record['symbol']} "
            f"approved={record['approved']} reason={record['reason']}"
        )

        return record

    def read_records(self, limit: int | None = None) -> list[Dict[str, Any]]:
        if not self.journal_path.exists():
            return []

        records: list[Dict[str, Any]] = []

        with self.journal_path.open("r", encoding="utf-8") as f:
            for line in f:
                text = line.strip()
                if not text:
                    continue
                try:
                    records.append(json.loads(text))
                except Exception:
                    continue

        if limit is not None:
            return records[-int(limit):]

        return records

    def total_records(self) -> int:
        return len(self.read_records())
