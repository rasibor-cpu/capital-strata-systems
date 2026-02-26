"""
Close Registry
Capital Strata Systems – Phase 17B

Purpose:
- Record month-end and year-end close events
- Provide fail-closed guardrails for posting/journal writes
- Support idempotent close (prevent double-close)
- Keep Phase 1 storage simple: JSON file under audit_logs/
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

REPO_ROOT = Path(__file__).resolve().parents[2]
AUDIT_DIR = REPO_ROOT / "audit_logs" / "close"
AUDIT_DIR.mkdir(parents=True, exist_ok=True)

CLOSE_FILE = AUDIT_DIR / "close_registry.json"


def _utc_now() -> str:
    return datetime.utcnow().isoformat()


def _load() -> Dict[str, Any]:
    if not CLOSE_FILE.exists():
        return {"schema_version": "v1.0", "events": []}
    return json.loads(CLOSE_FILE.read_text(encoding="utf-8"))


def _save(payload: Dict[str, Any]) -> None:
    CLOSE_FILE.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _key(close_type: str, year: int, month: Optional[int]) -> str:
    if close_type == "MONTH_END":
        if month is None:
            raise ValueError("month is required for MONTH_END")
        return f"MONTH_END:{year:04d}-{month:02d}"
    if close_type == "YEAR_END":
        return f"YEAR_END:{year:04d}"
    raise ValueError(f"Unknown close_type: {close_type}")


@dataclass(frozen=True)
class CloseEvent:
    close_type: str  # MONTH_END | YEAR_END
    year: int
    month: Optional[int]
    closed_at_utc: str
    actor_role: str
    notes: str = ""


class CloseRegistry:
    """
    Minimal close registry for Phase 1.
    Later phases can replace JSON with DB without breaking the API.
    """

    @staticmethod
    def is_closed(close_type: str, year: int, month: Optional[int] = None) -> bool:
        payload = _load()
        k = _key(close_type, year, month)
        return any(e.get("key") == k for e in payload.get("events", []))

    @staticmethod
    def record_close(
        close_type: str,
        year: int,
        month: Optional[int],
        actor_role: str,
        notes: str = "",
    ) -> Dict[str, Any]:
        payload = _load()
        k = _key(close_type, year, month)

        # Idempotent: if already closed, return existing event
        for e in payload.get("events", []):
            if e.get("key") == k:
                return {"ok": True, "status": "ALREADY_CLOSED", "event": e}

        event = {
            "schema_version": "v1.0",
            "key": k,
            "close_type": close_type,
            "year": year,
            "month": month,
            "closed_at_utc": _utc_now(),
            "actor_role": actor_role,
            "notes": notes,
        }

        payload["events"].append(event)
        _save(payload)

        return {"ok": True, "status": "CLOSED", "event": event}

    @staticmethod
    def latest_close() -> Optional[Dict[str, Any]]:
        payload = _load()
        events = payload.get("events", [])
        if not events:
            return None
        # last append is latest close
        return events[-1]