from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class AtlasKnowledgeEntry:
    entry_id: str
    title: str
    category: str
    path: str
    status: str = "ACTIVE"

    def __post_init__(self) -> None:
        if not all(value.strip() for value in (self.entry_id, self.title, self.category, self.path)):
            raise ValueError("Atlas knowledge entry fields are required")
        if self.status.upper() not in {"ACTIVE", "DEPRECATED", "ARCHIVED"}:
            raise ValueError("unsupported Atlas knowledge status")


def build_project_atlas_index(entries: Iterable[AtlasKnowledgeEntry]) -> dict:
    rows = sorted(entries, key=lambda x: (x.category.upper(), x.title.lower(), x.entry_id))
    return {
        "schema_version": "css.program_d.project_atlas.v1",
        "entry_count": len(rows),
        "entries": [
            {
                "entry_id": row.entry_id,
                "title": row.title,
                "category": row.category.upper(),
                "path": row.path,
                "status": row.status.upper(),
            }
            for row in rows
        ],
        "read_only": True,
        "execution_allowed": False,
    }
