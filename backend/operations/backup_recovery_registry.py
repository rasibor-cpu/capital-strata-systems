from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable


_ALLOWED = {"PASS", "WARN", "FAIL", "UNKNOWN"}


def _require_utc(value: datetime) -> None:
    if value.tzinfo is None or value.utcoffset() is None or value.utcoffset() != timezone.utc.utcoffset(value):
        raise ValueError("timestamp must be timezone-aware UTC")


@dataclass(frozen=True)
class BackupRecoveryEvidence:
    evidence_id: str
    category: str
    status: str
    observed_at_utc: datetime
    reference: str

    def __post_init__(self) -> None:
        if not self.evidence_id.strip() or not self.category.strip() or not self.reference.strip():
            raise ValueError("evidence id, category, and reference are required")
        _require_utc(self.observed_at_utc)
        if self.status.upper() not in _ALLOWED:
            raise ValueError("unsupported backup/recovery status")


def summarize_backup_recovery_evidence(items: Iterable[BackupRecoveryEvidence]) -> dict:
    rows = list(items)
    statuses = [row.status.upper() for row in rows]
    if "FAIL" in statuses or "UNKNOWN" in statuses:
        overall = "FAIL"
    elif "WARN" in statuses:
        overall = "WARN"
    else:
        overall = "PASS"

    return {
        "schema_version": "css.program_d.backup_recovery_registry.v1",
        "overall_status": overall,
        "evidence_count": len(rows),
        "items": [
            {
                "evidence_id": row.evidence_id,
                "category": row.category,
                "status": row.status.upper(),
                "observed_at_utc": row.observed_at_utc.isoformat(),
                "reference": row.reference,
            }
            for row in sorted(rows, key=lambda x: x.evidence_id)
        ],
        "execution_allowed": False,
        "money_movement_authorized": False,
    }
