from typing import Dict, Any
from datetime import date
from fastapi import Request

from backend.app.ticket_store import (
    create_or_update_ticket,
    get_ticket,
    update_ticket_status,
)

from backend.app.posting_store import (
    validate_posting_lines,
)

from backend.app.journal import post_to_journal

from backend.app.credit_limits import evaluate_credit_position

from backend.app.reporting_store import (
    get_journal_entries_for_year,
)

# -------------------------------
# Core Orchestrator
# -------------------------------

async def orchestrate(request: Request) -> Dict[str, Any]:
    body = await request.json()
    screen_id = body.get("screen_id")
    action = body.get("action")
    payload = body.get("payload", {})
    user_id = body.get("user_id", "unknown")

    if screen_id == "health":
        return ok("health", "Service healthy")

    if screen_id == "posting_entry":
        return handle_posting_entry(payload, user_id)

    if screen_id == "posting_submit":
        return handle_posting_submit(payload, user_id)

    if screen_id == "posting_approval":
        return handle_posting_approval(payload, user_id)

    if screen_id == "posting_result":
        return handle_posting_execution(payload, user_id)

    if screen_id == "ledger_journal":
        return handle_ledger_journal(payload)

    return error(screen_id, "Unknown screen_id")


# -------------------------------
# Posting Entry (Maker)
# -------------------------------

def handle_posting_entry(payload: Dict[str, Any], user_id: str):
    validate_posting_lines(payload["lines"])

    ticket = create_or_update_ticket(
        payload=payload,
        created_by=user_id,
        status="draft"
    )

    return ok(
        "posting_entry",
        f"Draft stored",
        {"ticket_id": ticket["ticket_id"], "status": "draft"}
    )


# -------------------------------
# Submit (Maker)
# -------------------------------

def handle_posting_submit(payload: Dict[str, Any], user_id: str):
    ticket_id = payload["ticket_id"]
    ticket = get_ticket(ticket_id)

    if ticket["status"] != "draft":
        return error("posting_submit", "Only draft tickets can be submitted")

    update_ticket_status(ticket_id, "submitted")

    return ok(
        "posting_submit",
        "Ticket submitted",
        {"ticket_id": ticket_id, "status": "submitted"}
    )


# -------------------------------
# Approval (Checker) – CREDIT GATED
# -------------------------------

def handle_posting_approval(payload: Dict[str, Any], user_id: str):
    ticket_id = payload["ticket_id"]
    decision = payload["decision"]
    comment = payload.get("comment", "")

    ticket = get_ticket(ticket_id)

    if ticket["status"] != "submitted":
        return error("posting_approval", "Only submitted tickets can be approved")

    if decision != "approve":
        update_ticket_status(ticket_id, "rejected", comment)
        return ok(
            "posting_approval",
            "Ticket rejected",
            {"ticket_id": ticket_id, "status": "rejected"}
        )

    # -------------------------------
    # CREDIT LIMIT HARD CHECK
    # -------------------------------
    customer_id = ticket["payload"].get("customer_id")

    credit_result = evaluate_credit_position(customer_id)

    if credit_result["decision"] == "BLOCK":
        update_ticket_status(
            ticket_id,
            "rejected",
            f"Credit limit breach: {credit_result['reason']}"
        )

        return error(
            "posting_approval",
            "Approval blocked by credit limits",
            credit_result
        )

    update_ticket_status(ticket_id, "approved", comment)

    return ok(
        "posting_approval",
        "Approved",
        {"ticket_id": ticket_id, "status": "approved"}
    )


# -------------------------------
# Execution (System)
# -------------------------------

def handle_posting_execution(payload: Dict[str, Any], user_id: str):
    ticket_id = payload["ticket_id"]
    ticket = get_ticket(ticket_id)

    if ticket["status"] != "approved":
        return error(
            "posting_result",
            "Execution failed",
            {"ok": False, "error": "Ticket not approved"}
        )

    journal_entries = post_to_journal(
        ticket_id=ticket_id,
        payload=ticket["payload"],
        executed_by=user_id
    )

    update_ticket_status(ticket_id, "posted")

    return ok(
        "posting_result",
        "Posting executed (double-entry ledger)",
        {
            "ticket_id": ticket_id,
            "status": "posted",
            "journal_entries": journal_entries,
            "ledger_integrity": "DR=CR enforced via journal"
        }
    )


# -------------------------------
# Ledger Journal Reporting
# -------------------------------

def handle_ledger_journal(payload: Dict[str, Any]):
    year = int(payload.get("year", date.today().year))
    entries = get_journal_entries_for_year(year)

    total_dr = sum(abs(e["delta"]) for e in entries if e["side"] == "DR")
    total_cr = sum(abs(e["delta"]) for e in entries if e["side"] == "CR")

    return ok(
        "ledger_journal",
        "Journal lines",
        {
            "lines": len(entries),
            "total_dr": round(total_dr, 2),
            "total_cr": round(total_cr, 2),
            "balanced": round(total_dr - total_cr, 2) == 0.0
        }
    )


# -------------------------------
# Response Helpers
# -------------------------------

def ok(screen_id: str, message: str, data: Dict[str, Any] = None):
    return {
        "screen_id": screen_id,
        "status": "ok",
        "message": message,
        "data": data or {}
    }


def error(screen_id: str, message: str, data: Dict[str, Any] = None):
    return {
        "screen_id": screen_id,
        "status": "error",
        "message": message,
        "data": data or {}
    }
