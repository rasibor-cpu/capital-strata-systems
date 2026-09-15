from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class ImprovementItem:
    item_id: str
    title: str
    priority: str
    status: str
    evidence_reference: str

    def __post_init__(self) -> None:
        if not all(value.strip() for value in (self.item_id, self.title, self.evidence_reference)):
            raise ValueError("improvement item fields are required")
        if self.priority.upper() not in {"LOW", "MEDIUM", "HIGH", "CRITICAL"}:
            raise ValueError("unsupported improvement priority")
        if self.status.upper() not in {"QUEUED", "IN_PROGRESS", "BLOCKED", "COMPLETE"}:
            raise ValueError("unsupported improvement status")


def build_improvement_register(items: Iterable[ImprovementItem]) -> dict:
    rows = list(items)
    open_rows = [row for row in rows if row.status.upper() != "COMPLETE"]
    return {
        "schema_version": "css.program_d.improvement_register.v1",
        "total_items": len(rows),
        "open_items": len(open_rows),
        "items": [
            {
                "item_id": row.item_id,
                "title": row.title,
                "priority": row.priority.upper(),
                "status": row.status.upper(),
                "evidence_reference": row.evidence_reference,
            }
            for row in sorted(rows, key=lambda x: (x.status.upper() == "COMPLETE", x.priority.upper(), x.item_id))
        ],
        "read_only": True,
        "execution_allowed": False,
    }
