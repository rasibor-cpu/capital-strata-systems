from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Dict, Any, List
import uuid


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(tzinfo=None).isoformat()


@dataclass(frozen=True)
class ExecutionAuditRecord:
    record_id: str
    timestamp_utc: str
    asset_class: str
    symbol: str
    mode: str
    broker: str
    approved: bool
    reason: str
    execution_id: str
    dry_run: bool
    metadata: Dict[str, Any]


class ExecutionAuditLedger:
    """
    Institutional execution audit ledger.

    PCNRASS SAFE:
    - In-memory audit ledger
    - No broker calls
    - No execution authority
    - Immutable-style append-only records
    """

    def __init__(self) -> None:
        self._records: List[ExecutionAuditRecord] = []

    def record_execution(
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
    ) -> ExecutionAuditRecord:

        record = ExecutionAuditRecord(
            record_id=str(uuid.uuid4()),
            timestamp_utc=_now_iso(),
            asset_class=str(asset_class).upper(),
            symbol=str(symbol).upper(),
            mode=str(mode).lower(),
            broker=str(broker).upper(),
            approved=bool(approved),
            reason=str(reason),
            execution_id=str(execution_id),
            dry_run=bool(dry_run),
            metadata=dict(metadata or {}),
        )

        self._records.append(record)

        print(
            f"[AUDIT LEDGER] "
            f"{record.asset_class} "
            f"{record.symbol} "
            f"approved={record.approved} "
            f"broker={record.broker} "
            f"reason={record.reason}"
        )

        return record

    def get_all_records(self) -> List[ExecutionAuditRecord]:
        return list(self._records)

    def export_records(self) -> List[Dict[str, Any]]:
        return [asdict(record) for record in self._records]

    def total_records(self) -> int:
        return len(self._records)

    def clear(self) -> None:
        self._records.clear()
