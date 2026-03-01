"""
engine/batch/batch_registry.py
Capital Strata Systems (CSS)

Phase 24 – Batch Registry & Double-Run Guard

Purpose:
- Prevent accidental duplicate EOD runs for same processing date
- Persist batch execution state
- Provide audit-grade lifecycle trace

Design:
- Strict fail-closed
- One EOD per processing date
- Re-runnable only if explicitly reversed (future enhancement)
"""

from __future__ import annotations

import json
from pathlib import Path
from datetime import datetime
from typing import Dict, Any


BATCH_LOG_FILE = Path("audit_logs/batch_registry.json")


def _ensure_store():
    BATCH_LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    if not BATCH_LOG_FILE.exists():
        BATCH_LOG_FILE.write_text(json.dumps({}, indent=2), encoding="utf-8")


def _load() -> Dict[str, Any]:
    _ensure_store()
    return json.loads(BATCH_LOG_FILE.read_text(encoding="utf-8"))


def _save(data: Dict[str, Any]) -> None:
    BATCH_LOG_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")


def assert_eod_not_already_run(processing_date: str) -> None:
    """
    Fail-closed: prevent duplicate EOD for same date.
    """
    data = _load()

    if processing_date in data:
        raise RuntimeError(
            f"EOD already executed for {processing_date}. "
            f"Duplicate lifecycle execution blocked."
        )


def register_eod_success(processing_date: str) -> None:
    """
    Mark EOD as successfully completed.
    """
    data = _load()

    data[processing_date] = {
        "status": "COMPLETED",
        "completed_at_utc": datetime.utcnow().isoformat() + "Z"
    }

    _save(data)