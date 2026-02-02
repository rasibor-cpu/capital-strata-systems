"""
journal.py — lightweight journal posting utility

Purpose:
- Provide a stable `post_to_journal()` API that other modules can import.
- Keep implementation simple, deterministic, and safe by default.
- Avoid breaking the app if journaling is not yet fully wired.

Design:
- Writes JSON lines to a local file (default: backend/data/journal.jsonl).
- If file writing fails, returns a safe error payload (no crash).
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Any, Dict, Optional


@dataclass
class JournalResult:
    ok: bool
    path: str
    entry_id: str
    error: Optional[str] = None


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ensure_parent_dir(path: str) -> None:
    parent = os.path.dirname(path)
    if parent and not os.path.exists(parent):
        os.makedirs(parent, exist_ok=True)


def post_to_journal(
    entry: Dict[str, Any],
    *,
    journal_path: str = "backend/data/journal.jsonl",
    entry_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Append a journal entry as a single JSON line.

    Args:
        entry: dict payload describing the journal entry
        journal_path: where to store journal lines
        entry_id: optional external id; generated if missing

    Returns:
        dict with fields: ok, path, entry_id, error (if any)
    """
    safe_entry_id = entry_id or f"jrn_{int(datetime.now().timestamp() * 1000)}"
    record = {
        "entry_id": safe_entry_id,
        "ts_utc": _utc_now_iso(),
        "entry": entry,
    }

    try:
        _ensure_parent_dir(journal_path)
        with open(journal_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

        res = JournalResult(ok=True, path=journal_path, entry_id=safe_entry_id)
        return asdict(res)

    except Exception as e:
        res = JournalResult(ok=False, path=journal_path, entry_id=safe_entry_id, error=str(e))
        return asdict(res)
