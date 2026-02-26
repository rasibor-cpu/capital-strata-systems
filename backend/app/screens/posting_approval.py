"""
backend/app/screens/posting_approval.py

Posting Approval (Checker decision) – Phase 13.6
------------------------------------------------
Adds:
- Regulator-grade immutable approval snapshot logging (JSONL)
- Fail-safe audit write (never blocks approval)
"""

from __future__ import annotations

import json
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, Any

from backend.app.posting_store import approve_ticket, reject_ticket, return_ticket


def _audit_write_posting_snapshot(payload: dict) -> None:
    try:
        Path("audit_logs").mkdir(parents=True, exist_ok=True)
        out = Path("audit_logs") / "posting_snapshots.jsonl"
        with out.open("a", encoding="utf-8") as f:
            f.write(json.dumps(payload, ensure_ascii=False) + "\n")
    except Exception:
        return


def posting_approval_handler(
    payload: Dict[str, Any],
    user_id: str | None = None,
) -> Dict[str, Any]:

    ticket_id = payload.get("ticket_id")
    decision = payload.get("decision")

    if not ticket_id:
        return {"ok": False, "error": "ticket_id is required"}

    if decision not in {"approve", "reject", "return"}:
        return {"ok": False, "error": "decision must be one of approve, reject, return"}

    checker_id = user_id or "anonymous_checker"

    try:
        if decision == "approve":
            t = approve_ticket(ticket_id, checker_id)

            _audit_write_posting_snapshot(
                {
                    "timestamp": datetime.now(timezone.utc).timestamp(),
                    "event": "POSTING_APPROVAL",
                    "phase": "PHASE_13_6",
                    "ticket_id": ticket_id,
                    "checker_id": checker_id,
                    "decision": "approve",
                    "ticket_status": getattr(getattr(t, "status", None), "value", None),
                }
            )

            return {
                "ok": True,
                "decision": "approve",
                "ticket": {"ticket_id": getattr(t, "ticket_id", ticket_id), "status": t.status.value},
                "note": "Approved (ledger execution handled downstream).",
            }

        if decision == "reject":
            reason = payload.get("reason", "Rejected by checker")
            t = reject_ticket(ticket_id, checker_id, reason)

            _audit_write_posting_snapshot(
                {
                    "timestamp": datetime.now(timezone.utc).timestamp(),
                    "event": "POSTING_REJECT",
                    "phase": "PHASE_13_6",
                    "ticket_id": ticket_id,
                    "checker_id": checker_id,
                    "decision": "reject",
                    "reason": reason,
                    "ticket_status": getattr(getattr(t, "status", None), "value", None),
                }
            )

            return {
                "ok": True,
                "decision": "reject",
                "ticket": {"ticket_id": getattr(t, "ticket_id", ticket_id), "status": t.status.value},
                "note": reason,
            }

        if decision == "return":
            reason = payload.get("reason", "Returned for correction")
            t = return_ticket(ticket_id, checker_id, reason)

            _audit_write_posting_snapshot(
                {
                    "timestamp": datetime.now(timezone.utc).timestamp(),
                    "event": "POSTING_RETURN",
                    "phase": "PHASE_13_6",
                    "ticket_id": ticket_id,
                    "checker_id": checker_id,
                    "decision": "return",
                    "reason": reason,
                    "ticket_status": getattr(getattr(t, "status", None), "value", None),
                }
            )

            return {
                "ok": True,
                "decision": "return",
                "ticket": {"ticket_id": getattr(t, "ticket_id", ticket_id), "status": t.status.value},
                "note": "Returned to maker (no ledger write).",
            }

        return {"ok": False, "error": "Unhandled decision"}

    except Exception as e:
        return {"ok": False, "error": str(e)}