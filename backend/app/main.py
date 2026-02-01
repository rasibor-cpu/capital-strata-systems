from typing import Dict, Any, Tuple, List
from datetime import datetime
from fastapi import Request

from .journal import post_line
from .fx_daily_rates import convert_to_base


# =========================
# In-memory stores
# =========================
TICKETS: Dict[str, Dict[str, Any]] = {}
AUDIT_LOG: List[Dict[str, Any]] = []


def _now() -> str:
    return datetime.utcnow().isoformat()


def _ok(screen_id: str, message: str, data: Dict[str, Any]) -> Dict[str, Any]:
    return {"screen_id": screen_id, "status": "ok", "message": message, "data": data}


def _err(screen_id: str, message: str, error: str) -> Dict[str, Any]:
    return {
        "screen_id": screen_id,
        "status": "error",
        "message": message,
        "data": {"ok": False, "error": error},
    }


# =========================
# Orchestrator
# =========================
async def orchestrate(request: Request) -> Dict[str, Any]:
    body = await request.json()
    screen_id = body.get("screen_id")
    action = body.get("action")
    payload = body.get("payload", {})
    user_id = body.get("user_id")

    handlers = {
        "posting_entry": handle_posting_entry,
        "posting_submit": handle_posting_submit,
        "posting_review": handle_posting_review,
        "posting_approval": handle_posting_approval,
        "posting_result": handle_posting_result,
    }

    handler = handlers.get(screen_id)
    if not handler:
        return {
            "screen_id": screen_id,
            "status": "not_implemented",
            "message": "Screen not implemented",
            "data": {},
        }

    return handler(payload=payload, user_id=user_id, action=action)


# =========================
# HANDLERS
# =========================

def handle_posting_entry(payload: Dict[str, Any], user_id: str, action: str) -> Dict[str, Any]:
    ticket_id = payload["ticket_id"]

    lines = payload["lines"]
    dr = sum(l["amount"] for l in lines if l["side"] == "DR")
    cr = sum(l["amount"] for l in lines if l["side"] == "CR")

    if abs(dr - cr) > 1e-9:
        return _err("posting_entry", "Validation failed", "DR and CR not balanced")

    TICKETS[ticket_id] = {
        "ticket_id": ticket_id,
        "status": "draft",
        "lines": lines,
        "created_by": user_id,
        "created_at": _now(),
    }

    return _ok(
        "posting_entry",
        "Draft stored",
        {"ticket_id": ticket_id, "status": "draft", "next_actions": ["posting_submit"]},
    )


def handle_posting_submit(payload: Dict[str, Any], user_id: str, action: str) -> Dict[str, Any]:
    t = TICKETS.get(payload["ticket_id"])
    if not t:
        return _err("posting_submit", "Submit failed", "Ticket not found")

    t["status"] = "submitted"
    t["submitted_at"] = _now()

    return _ok(
        "posting_submit",
        "Ticket submitted",
        {"ticket_id": t["ticket_id"], "status": "submitted"},
    )


def handle_posting_review(payload: Dict[str, Any], user_id: str, action: str) -> Dict[str, Any]:
    t = TICKETS.get(payload["ticket_id"])
    if not t:
        return _err("posting_review", "Review failed", "Ticket not found")

    return _ok("posting_review", "Review", {"ticket": t})


def handle_posting_approval(payload: Dict[str, Any], user_id: str, action: str) -> Dict[str, Any]:
    t = TICKETS.get(payload["ticket_id"])
    if not t:
        return _err("posting_approval", "Approval failed", "Ticket not found")

    if t["status"] != "submitted":
        return _err("posting_approval", "Approval failed", "Invalid status")

    t["status"] = "approved"
    t["approved_by"] = user_id
    t["approved_at"] = _now()

    return _ok(
        "posting_approval",
        "Approved",
        {"ticket_id": t["ticket_id"], "status": "approved", "next_actions": ["posting_result"]},
    )


def handle_posting_result(payload: Dict[str, Any], user_id: str, action: str) -> Dict[str, Any]:
    """
    FINAL EXECUTION:
    - Enforces DOUBLE ENTRY
    - All balance movement happens via JOURNAL ONLY
    - No direct balance mutation anywhere
    """

    t = TICKETS.get(payload["ticket_id"])
    if not t:
        return _err("posting_result", "Execution failed", "Ticket not found")

    if t["status"] != "approved":
        return _err("posting_result", "Execution failed", "Ticket not approved")

    journal_refs = []

    for ln in t["lines"]:
        ref = post_line(
            ticket_id=t["ticket_id"],
            user_id=user_id or "system",
            action="posting_result_execute",
            base_account_no=ln["base_account_no"],
            account_type_code=ln["account_type_code"],
            currency=ln["currency"],
            side=ln["side"],
            amount=ln["amount"],
            narrative=ln.get("narrative", ""),
            meta={"screen": "posting_result"},
        )
        journal_refs.append(ref)

    t["status"] = "posted"
    t["posted_at"] = _now()

    AUDIT_LOG.append(
        {
            "ticket_id": t["ticket_id"],
            "action": "posted",
            "by": user_id or "system",
            "at": t["posted_at"],
        }
    )

    return _ok(
        "posting_result",
        "Posting executed (double-entry ledger)",
        {
            "ticket_id": t["ticket_id"],
            "status": "posted",
            "journal_entries": journal_refs,
            "ledger_integrity": "DR=CR enforced via journal",
        },
    )
