from fastapi import FastAPI, Request
from datetime import datetime

from backend.app.ticket_store import (
    create_ticket,
    get_ticket,
    submit_ticket,
    approve_ticket,
    mark_ticket_posted,
)
from backend.app.ledger_registry import post_journal_entry

app = FastAPI(title="REA Capital Trading Engine")

# -----------------------------
# Generic helpers
# -----------------------------

def now():
    return datetime.utcnow().isoformat()


def ok(screen_id: str, message: str, data: dict | None = None):
    return {
        "screen_id": screen_id,
        "status": "ok",
        "message": message,
        "data": data or {},
    }


def error(screen_id: str, message: str, data: dict | None = None):
    return {
        "screen_id": screen_id,
        "status": "error",
        "message": message,
        "data": data or {},
    }


# -----------------------------
# Health
# -----------------------------

@app.get("/health")
def health():
    return {"status": "ok"}


# -----------------------------
# Orchestrator
# -----------------------------

@app.post("/orchestrate")
async def orchestrate(request: Request):
    body = await request.json()

    screen_id = body.get("screen_id")
    action = body.get("action")
    payload = body.get("payload", {})

    if screen_id == "posting_entry":
        return handle_posting_entry(body)

    if screen_id == "posting_submit":
        return handle_posting_submit(body)

    if screen_id == "posting_approval":
        return handle_posting_approval(body)

    if screen_id == "posting_result":
        return handle_posting_result(body)

    return error(screen_id or "unknown", "Screen not implemented")


# -----------------------------
# Posting Entry (Maker)
# -----------------------------

def handle_posting_entry(body):
    payload = body["payload"]
    user_id = body["user_id"]

    ticket = create_ticket(
        created_by=user_id,
        execution_date=payload.get("execution_date"),
        value_date=payload.get("value_date"),
        lines=payload.get("lines", []),
    )

    return ok(
        "posting_entry",
        "Draft stored",
        {
            "ticket_id": ticket["ticket_id"],
            "status": ticket["status"],
            "line_count": len(ticket["lines"]),
        },
    )


# -----------------------------
# Posting Submit (Maker)
# -----------------------------

def handle_posting_submit(body):
    ticket_id = body["payload"]["ticket_id"]
    user_id = body["user_id"]

    ticket = submit_ticket(ticket_id, user_id)

    if not ticket:
        return error("posting_submit", "Ticket not found")

    return ok(
        "posting_submit",
        "Ticket submitted",
        {
            "ticket_id": ticket_id,
            "status": ticket["status"],
        },
    )


# -----------------------------
# Posting Approval (Checker)
# -----------------------------

def handle_posting_approval(body):
    payload = body["payload"]
    user_id = body["user_id"]

    ticket_id = payload["ticket_id"]
    decision = payload["decision"]
    comment = payload.get("comment", "")

    ticket = approve_ticket(ticket_id, user_id, decision, comment)

    if not ticket:
        return error("posting_approval", "Ticket not found")

    return ok(
        "posting_approval",
        "Approved" if decision == "approve" else "Rejected",
        {
            "ticket_id": ticket_id,
            "status": ticket["status"],
        },
    )


# -----------------------------
# Posting Result (System)
# -----------------------------

def handle_posting_result(body):
    payload = body["payload"]
    ticket_id = payload["ticket_id"]

    ticket = get_ticket(ticket_id)

    if not ticket:
        return error("posting_result", "Ticket not found")

    if ticket["status"] != "approved":
        return error(
            "posting_result",
            "Execution failed",
            {"ok": False, "error": "Ticket not approved"},
        )

    if ticket.get("posted") is True:
        return error(
            "posting_result",
            "Execution blocked",
            {"ok": False, "error": "Ticket already posted"},
        )

    journal_entries = []

    for line in ticket["lines"]:
        entry = post_journal_entry(
            ticket_id=ticket_id,
            user_id="system",
            side=line["side"],
            base_account_no=line["base_account_no"],
            account_type_code=line["account_type_code"],
            currency=line["currency"],
            amount=line["amount"],
            narrative=line.get("narrative", ""),
        )
        journal_entries.append(entry)

    mark_ticket_posted(ticket_id)

    return ok(
        "posting_result",
        "Posting executed (double-entry ledger)",
        {
            "ticket_id": ticket_id,
            "status": "posted",
            "journal_entries": journal_entries,
            "ledger_integrity": "DR=CR enforced via journal",
        },
    )
