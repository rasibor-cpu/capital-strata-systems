"""
Posting approval (checker decision) handler (Phase 13.6)

Decisions:
- approve  -> SUBMITTED -> APPROVED
- reject   -> SUBMITTED -> REJECTED
- return   -> SUBMITTED -> RETURNED

Hard rules:
- Maker cannot approve/return/reject own ticket
- NO ledger writes (state + audit only)
"""

from typing import Dict, Any

from ..posting_store import approve_ticket, reject_ticket, return_ticket


def posting_approval_handler(payload: Dict[str, Any], user_id: str | None) -> Dict[str, Any]:
    ticket_id = str(payload.get("ticket_id", "")).strip()
    decision = str(payload.get("decision", "")).strip().lower()
    reason = str(payload.get("reason", "")).strip()
    checker_id = user_id or "anonymous_checker"

    if not ticket_id:
        return {"ok": False, "error": "ticket_id is required"}

    if decision not in {"approve", "reject", "return"}:
        return {"ok": False, "error": "decision must be one of: approve, reject, return"}

    try:
        if decision == "approve":
            t = approve_ticket(ticket_id, checker_id)
            return {
                "ok": True,
                "decision": "approve",
                "ticket": {"ticket_id": t.ticket_id, "status": t.status.value},
                "next_actions": ["posting_result"],
                "note": "Approved (no ledger write at this phase).",
            }

        if decision == "reject":
            if not reason:
                reason = "Rejected by checker"
            t = reject_ticket(ticket_id, checker_id, reason)
            return {
                "ok": True,
                "decision": "reject",
                "reason": reason,
                "ticket": {"ticket_id": t.ticket_id, "status": t.status.value},
                "next_actions": ["posting_result"],
                "note": "Rejected (no ledger write).",
            }

        # decision == "return"
        if not reason:
            reason = "Returned for correction"
        t = return_ticket(ticket_id, checker_id, reason)
        return {
            "ok": True,
            "decision": "return",
            "reason": reason,
            "ticket": {"ticket_id": t.ticket_id, "status": t.status.value},
            "next_actions": ["posting_entry", "posting_submit"],
            "note": "Returned to maker (no ledger write).",
        }

    except Exception as e:
        return {"ok": False, "error": str(e)}
