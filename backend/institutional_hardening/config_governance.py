from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any


@dataclass(frozen=True)
class ConfigChangeRecord:
    change_id: str
    changed_by: str
    approver_id: str
    changed_at_utc: datetime
    rollback_reference: str
    before: dict[str, Any]
    after: dict[str, Any]

    def __post_init__(self) -> None:
        if self.changed_at_utc.tzinfo is None or self.changed_at_utc.utcoffset() != timezone.utc.utcoffset(self.changed_at_utc):
            raise ValueError("changed_at_utc must be UTC")
        if not all((self.change_id.strip(), self.changed_by.strip(), self.approver_id.strip(), self.rollback_reference.strip())):
            raise ValueError("change metadata is required")

    def diff(self) -> dict[str, dict[str, Any]]:
        keys = sorted(set(self.before) | set(self.after))
        return {
            key: {"before": self.before.get(key), "after": self.after.get(key)}
            for key in keys
            if self.before.get(key) != self.after.get(key)
        }
