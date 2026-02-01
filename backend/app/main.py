from fastapi import FastAPI, Request
from datetime import datetime
from typing import Dict, Any

app = FastAPI()

# =========================
# In-memory stores (Phase 13)
# =========================
TICKETS: Dict[str, Dict[str, Any]] = {}
LEDGER: list = []
AUDIT_LOG: list = []

# =========================
# Utilities
# =========================
def now():
    return datetime.utcnow().isoformat()

def error(screen_id: str, message: str, data: dict = None):
    return {
        "screen_id": screen_id,
        "status": "error",
        "message": message,
        "data": data or {}
    }

def ok(screen_id: str, message: str, data: dict = None):
    return {
        "screen_id": screen_id,
        "status": "ok",
        "message": message,
        "data": data or {}
    }

# =========================
# Health
# =========================
@app.get("/health")
def health():
    return {
        "status": "ok",
        "orchestration": {
            "server_time": now(),
            "engine_mode": "prompt"
        }
    }

# =========================
# Orchestrator
# =========================
@app.post("/orchestrate")
async def orchestrate(request: Request):
    body = await request.json()
    screen_id = body.get("screen_id")

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
            "message": "Screen not implemented yet",
            "data": {
                "screen_id": screen_id,
                "known_screens": list(handlers.keys())
            }
        }

    return handler(body)

# =========================
# HANDLERS
# =========================

def handle_posting_entry(body):
    ticket_id = f"T-{len(TICKETS)+2001}"

    ticket = {
        "ticket_id": ticket_id,
        "created_by": body.get("user_id"),
        "execution_date": body["payload"]["execution_date"],
        "value_date": body["payload"]["value_date"],
        "status": "draft",
        "lines": body["payload"]["lines"],
        "totals": body["payload"]["totals"],
        "created_at": now(),
        "approvals": []
    }

    TICKETS[ticket_id] = ticket

    return ok(
        "posting_entry",
        "Posting entry (validate + store draft)",
        {
            "ticket": ticket,
            "is_valid": True,
            "stored": True,
            "next_actions": ["submit_ticket"],
            "note": "Validation passed. Ticket stored as DRAFT in memory. No ledger posting."
        }
    )

def handle_posting_submit(body):
    ticket_id = body["payload"]["ticket_id"]
    ticket = TICKETS.get(ticket_id)

    if not ticket:
        return error("posting_submit", "Submit failed", {"error": f"Ticket not found: {ticket_id}"})

    ticket["status"] = "submitted"
    ticket["submitted_at"] = now()
    ticket["approvals"].append({
        "action": "submit",
        "by": body.get("user_id"),
        "at": now()
    })

    return ok(
        "posting_submit",
        "Ticket submitted",
        {
            "ok": True,
            "ticket": {
                "ticket_id": ticket_id,
                "status": "submitted",
                "submitted_at": ticket["submitted_at"]
            },
            "next_actions": ["checker_review", "checker_decision"]
        }
    )

def handle_posting_review(body):
    ticket_id = body["payload"]["ticket_id"]
    ticket = TICKETS.get(ticket_id)

    if not ticket:
        return error("posting_review", "Ticket not found", {"ticket_id": ticket_id})

    return ok(
        "posting_review",
        "Posting ticket review",
        {
            "ticket": ticket,
            "note": "Read-only review. No changes applied."
        }
    )

def handle_posting_approval(body):
    ticket_id = body["payload"]["ticket_id"]
    decision = body["payload"]["decision"]
    comment = body["payload"].get("comment", "")
    ticket = TICKETS.get(ticket_id)

    if not ticket:
        return error("posting_approval", "Approval failed", {"error": f"Ticket not found: {ticket_id}"})

    if ticket["status"] != "submitted":
        return error("posting_approval", "Invalid ticket state", {"status": ticket["status"]})

    ticket["status"] = "approved"
    ticket["approved_at"] = now()
    ticket["approvals"].append({
        "action": decision,
        "by": body.get("user_id"),
        "comment": comment,
        "at": now()
    })

    return ok(
        "posting_approval",
        "Ticket approved",
        {
            "ok": True,
            "decision": decision,
            "ticket": {
                "ticket_id": ticket_id,
                "status": "approved"
            },
            "next_actions": ["posting_result"],
            "note": "Approved (no ledger write at this phase)."
        }
    )

def handle_posting_result(body):
    ticket_id = body["payload"]["ticket_id"]
    ticket = TICKETS.get(ticket_id)

    if not ticket:
        return error("posting_result", "Execution failed", {"error": f"Ticket not found: {ticket_id}"})

    if ticket["status"] != "approved":
        return error("posting_result", "Invalid state for execution", {"status": ticket["status"]})

    if ticket.get("posted"):
        return ok(
            "posting_result",
            "Already posted",
            {
                "ticket": {
                    "ticket_id": ticket_id,
                    "status": "posted"
                },
                "idempotent": True
            }
        )

    # Write ledger
    for line in ticket["lines"]:
        LEDGER.append({
            "ticket_id": ticket_id,
            "side": line["side"],
            "account_no": line["account_no"],
            "currency": line["currency"],
            "amount": line["amount"],
            "narrative": line["narrative"],
            "posted_at": now()
        })

    ticket["status"] = "posted"
    ticket["posted"] = True
    ticket["posted_at"] = now()

    AUDIT_LOG.append({
        "ticket_id": ticket_id,
        "action": "execute_posting",
        "by": body.get("user_id"),
        "at": now()
    })

    return ok(
        "posting_result",
        "Posting executed successfully",
        {
            "ticket": {
                "ticket_id": ticket_id,
                "status": "posted",
                "posted_at": ticket["posted_at"]
            },
            "ledger_written": True,
            "entries": len(ticket["lines"]),
            "audit_logged": True
        }
    )
