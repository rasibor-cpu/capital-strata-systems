"""
approval_queue_snapshot.py
Capital Strata Systems (CSS)

Purpose:
- Generate an auditable snapshot of all unclosed / pending approval queue items
- Designed for EOD batch review and next-day follow-up
- Provides a stable callable API for report_printer

Canonical API:
- build_approval_queue_snapshot(run_date)

Backward compatibility:
- If older function names existed, keep aliases where safe.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional
import json


APPROVAL_QUEUE_FILE = Path("audit/approval_queue.json")
OUTPUT_DIR = Path("audit/eod_snapshots/approval_queue")


def _load_json(path: Path, default):
    if not path.exists():
        return default
    with open(path, "r") as f:
        return json.load(f)


def _save_json(path: Path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(payload, f, indent=4)


def _as_date_str(d: date) -> str:
    return d.isoformat()


def _normalize_queue(raw: Any) -> List[Dict[str, Any]]:
    """
    Supports queue file being either:
    - list[dict]
    - dict with 'items' list
    - empty / missing
    """
    if raw is None:
        return []
    if isinstance(raw, list):
        return [x for x in raw if isinstance(x, dict)]
    if isinstance(raw, dict):
        items = raw.get("items", [])
        if isinstance(items, list):
            return [x for x in items if isinstance(x, dict)]
    return []


def build_approval_queue_snapshot(run_date: Optional[date] = None) -> Dict[str, Any]:
    """
    Canonical snapshot builder. Used by report_printer during EOD.

    Output is stored as:
      audit/eod_snapshots/approval_queue/approval_queue_snapshot_YYYY-MM-DD.json
    """
    if run_date is None:
        run_date = date.today()

    raw = _load_json(APPROVAL_QUEUE_FILE, default=None)
    items = _normalize_queue(raw)

    # Pending/unclosed definition: status not in CLOSED/APPROVED/REJECTED
    # (We preserve unknown statuses rather than dropping them.)
    pending: List[Dict[str, Any]] = []
    closed: List[Dict[str, Any]] = []

    for it in items:
        status = str(it.get("status", "")).upper().strip()
        if status in ("CLOSED", "APPROVED", "REJECTED"):
            closed.append(it)
        else:
            pending.append(it)

    snapshot = {
        "as_at": _as_date_str(run_date),
        "source_file": str(APPROVAL_QUEUE_FILE),
        "counts": {
            "total_items": len(items),
            "pending_items": len(pending),
            "closed_items": len(closed),
        },
        "pending": pending,
        "closed": closed,
    }

    out_file = OUTPUT_DIR / f"approval_queue_snapshot_{_as_date_str(run_date)}.json"
    _save_json(out_file, snapshot)

    return {
        "ok": True,
        "as_at": _as_date_str(run_date),
        "output_file": str(out_file),
        "counts": snapshot["counts"],
    }


# --- Backward-compatible aliases (safe no-ops if older code calls them) ---

def run_approval_queue_snapshot(run_date: Optional[date] = None) -> Dict[str, Any]:
    return build_approval_queue_snapshot(run_date)


def generate_approval_queue_snapshot(run_date: Optional[date] = None) -> Dict[str, Any]:
    return build_approval_queue_snapshot(run_date)