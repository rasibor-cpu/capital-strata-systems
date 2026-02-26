"""
backend/app/screens/posting_approval.py

Posting Approval (Checker decision) – Phase 15
-------------------------------------------------
- Approval snapshot logging
- Ledger posting hook on APPROVE (persistent Journal -> GL)
- Carries dimension bundle (dims) for multi-level reconciliation/reporting
"""

from __future__ import annotations

import json
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, Any

from backend.app.posting_store import approve_ticket, reject_ticket, return_ticket
from backend.app.ledger.ledger_registry import post as ledger_post


def _audit_write_posting_snapshot(payload: dict) -> None:
    try:
        Path("audit_logs").mkdir(parents=True, exist_ok=True)
        out = Path("audit_logs") / "posting_snapshots.jsonl"
        with out.open("a", encoding="utf-8") as f:
            f.write(json.dumps(payload, ensure_ascii=False) + "\n")
    except Exception:
        return


def posting_approval_handler(payload: Dict[str, Any], user_id: str | None = None) -> Dict[str, Any]:
    ticket_id = str(payload.get("ticket_id", "")).strip()
    decision = str(payload.get("decision", "")).strip().lower()

    if not ticket_id:
        return {"ok": False, "error": "ticket_id is required"}
    if decision not in {"approve", "reject", "return"}:
        return {"ok": False, "error": "decision must be one of approve, reject, return"}

    checker_id = (user_id or "anonymous_checker").strip() or "anonymous_checker"

    # Optional dimension bundle from UI
    dims = payload.get("dims") or {}
    if not isinstance(dims, dict):
        return {"ok": False, "error": "dims must be an object/dict if provided"}

    try:
        if decision == "approve":
            t = approve_ticket(ticket_id, checker_id)
            maker_id = getattr(t, "created_by", None)

            ledger_result = ledger_post(
                t,
                maker_user_id=maker_id,
                checker_user_id=checker_id,
                dims=dims,
            )

            _audit_write_posting_snapshot(
                {
                    "timestamp": datetime.now(timezone.utc).timestamp(),
                    "event": "POSTING_APPROVAL",
                    "phase": "PHASE_15",
                    "ticket_id": ticket_id,
                    "checker_id": checker_id,
                    "maker_id": maker_id,
                    "decision": "approve",
                    "dims": dims,
                    "ticket_status": getattr(getattr(t, "status", None), "value", None),
                    "ledger": ledger_result,
                }
            )

            return {
                "ok": True,
                "decision": "approve",
                "ticket": {
                    "ticket_id": getattr(t, "ticket_id", ticket_id),
                    "status": getattr(getattr(t, "status", None), "value", None),
                },
                "ledger": ledger_result,
                "note": "Approved. Journal appended + GL updated (persistent, dimensional).",
            }

        if decision == "reject":
            reason = str(payload.get("reason", "Rejected by checker")).strip() or "Rejected by checker"
            t = reject_ticket(ticket_id, checker_id, reason)
            _audit_write_posting_snapshot(
                {
                    "timestamp": datetime.now(timezone.utc).timestamp(),
                    "event": "POSTING_REJECT",
                    "phase": "PHASE_15",
                    "ticket_id": ticket_id,
                    "checker_id": checker_id,
                    "decision": "reject",
                    "reason": reason,
                    "dims": dims,
                    "ticket_status": getattr(getattr(t, "status", None), "value", None),
                }
            )
            return {
                "ok": True,
                "decision": "reject",
                "ticket": {
                    "ticket_id": getattr(t, "ticket_id", ticket_id),
                    "status": getattr(getattr(t, "status", None), "value", None),
                },
                "note": reason,
            }

        if decision == "return":
            reason = str(payload.get("reason", "Returned for correction")).strip() or "Returned for correction"
            t = return_ticket(ticket_id, checker_id, reason)
            _audit_write_posting_snapshot(
                {
                    "timestamp": datetime.now(timezone.utc).timestamp(),
                    "event": "POSTING_RETURN",
                    "phase": "PHASE_15",
                    "ticket_id": ticket_id,
                    "checker_id": checker_id,
                    "decision": "return",
                    "reason": reason,
                    "dims": dims,
                    "ticket_status": getattr(getattr(t, "status", None), "value", None),
                }
            )
            return {
                "ok": True,
                "decision": "return",
                "ticket": {
                    "ticket_id": getattr(t, "ticket_id", ticket_id),
                    "status": getattr(getattr(t, "status", None), "value", None),
                },
                "note": "Returned to maker (no ledger write).",
            }

        return {"ok": False, "error": "Unhandled decision"}

    except Exception as e:
        return {"ok": False, "error": str(e)}