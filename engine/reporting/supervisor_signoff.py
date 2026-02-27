"""
engine/reporting/supervisor_signoff.py

Supervisor Sign-Off Engine (Phase 18 – Temporal Governance Enforced)
---------------------------------------------------------------------

Features:
- Immutable append-only JSONL log
- One sign-off per (supervisor, report_name, business_date)
- Requires integrity hash
- Enforces:
    • No future date
    • Must be business day
    • Must equal previous working day (strict policy)
- Fail-closed if business calendar unavailable
"""

from __future__ import annotations

import json
from pathlib import Path
from datetime import datetime, timezone, date
from typing import Dict, Any

from engine.reporting.business_calendar import (
    previous_business_day,
    is_business_day,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
LOG_FILE = REPO_ROOT / "audit_logs" / "supervisor_signoffs.jsonl"


# -------------------------------------------------
# Utilities
# -------------------------------------------------

def _today_utc_date() -> date:
    return datetime.now(timezone.utc).date()


def _parse_date(d: str) -> date:
    return date.fromisoformat(d)


def _load_existing() -> list[Dict[str, Any]]:
    if not LOG_FILE.exists():
        return []
    rows = []
    for line in LOG_FILE.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def _append_log(entry: Dict[str, Any]) -> None:
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with LOG_FILE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, separators=(",", ":"), ensure_ascii=False))
        f.write("\n")


# -------------------------------------------------
# Core API
# -------------------------------------------------

def sign_off_report(
    *,
    supervisor_id: str,
    report_name: str,
    business_date: str,
    integrity_block: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Records supervisor sign-off with strict previous-day enforcement.
    """

    if not supervisor_id:
        return {"ok": False, "reason": "Missing supervisor_id"}

    if not report_name:
        return {"ok": False, "reason": "Missing report_name"}

    if not business_date:
        return {"ok": False, "reason": "Missing business_date"}

    try:
        biz_date = _parse_date(business_date)
    except Exception:
        return {"ok": False, "reason": "Invalid business_date format (YYYY-MM-DD required)"}

    today = _today_utc_date()

    # --------------------------------------------
    # Strict Temporal Enforcement
    # --------------------------------------------

    if biz_date > today:
        return {"ok": False, "reason": "Cannot sign off future date"}

    if not is_business_day(biz_date):
        return {"ok": False, "reason": "Cannot sign off non-business day"}

    expected = previous_business_day(today)

    if biz_date != expected:
        return {
            "ok": False,
            "reason": f"Signoff allowed only for previous working day ({expected.isoformat()})",
        }

    # --------------------------------------------
    # Integrity Enforcement
    # --------------------------------------------

    if not integrity_block or not integrity_block.get("sha256"):
        return {"ok": False, "reason": "Integrity block missing sha256"}

    # --------------------------------------------
    # Duplicate Prevention
    # --------------------------------------------

    existing = _load_existing()

    for row in existing:
        if (
            row.get("supervisor_id") == supervisor_id
            and row.get("report_name") == report_name
            and row.get("business_date") == business_date
        ):
            return {"ok": False, "reason": "Already signed off"}

    # --------------------------------------------
    # Persist Entry
    # --------------------------------------------

    entry = {
        "supervisor_id": supervisor_id,
        "report_name": report_name,
        "business_date": business_date,
        "integrity_sha256": integrity_block.get("sha256"),
        "schema_name": integrity_block.get("schema_name"),
        "schema_version": integrity_block.get("schema_version"),
        "signed_at_utc": datetime.now(timezone.utc).isoformat(),
    }

    _append_log(entry)

    return {"ok": True}