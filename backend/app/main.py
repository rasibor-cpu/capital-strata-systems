from fastapi import FastAPI, Request
from datetime import datetime
from typing import Dict, Any, Optional

# IMPORTANT: Use RELATIVE imports only (no "backend." absolute imports)
from .ledger_registry import post_journal_entry

app = FastAPI(title="REA Capital Trading Engine")

# -----------------------------
# In-memory ticket store (Phase 13/14 prototype)
# -----------------------------
TICKETS: Dict[str, Dict[str, Any]] = {}
_TICKET_SEQ = 5000


def _now() -> str:
    return datetime.utcnow().isoformat()


def _new_ticket_id() -> str:
    global _TICKET_SEQ
    _TICKET_SEQ += 1
    return f"T-{_TICKET_SEQ}"


def ok(screen_id: str, message: str, data: Optional[dict] = None) -> Dict[str, Any]:
    return {"screen_id": screen_id, "status": "ok", "message": message, "data": data or {}}


def error(screen_id: str, message: str, data: Optional[dict] = None) -> Dict[str, Any]:
    return {"screen_id": screen_id, "status": "error", "message": message, "data": data or {}}


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/orchestrate")
async def orchestrate(request: Request):
    body = await request.json()

    screen_id = body.get("screen_id")
    action = body.get("action")  # api.py enforces, but we won't crash if missing
    payload = body.get("payload", {}) or {}
    user_id = body.get("user_id") or "anonymous"

    if screen_id == "posting_entry":
        return handle_posting_entry(payload, user_id, action)

    if screen_id == "posting_submit":
        return handle_posting_submit(payload, user_id, action)

    if screen_id == "posting_approval":
        return handle_posting_approval(payload, user_id, action)

    if screen_id == "posting_result":
        return handle_posting_result(payload, user_id, action)

    return {
        "screen_id": screen_id,
        "status": "not_implemented",
        "message": "Screen not implemented",
        "data": {"known_screens": ["posting_entry", "posting_submit", "posting_approval", "posting_result"]},
    }


# -----------------------------
# Handlers
# -----------------------------

def handle_posting_entry(payload: Dict[str, Any], user_id: str, action: Optional[str]):
    """
    Creates a DRAFT ticket.
    If payload.ticket_id is provided, we respect it. Otherwise we auto-generate.
    Required fields:
      - lines: list of DR/CR legs
      - execution_date, value_date are optional in this prototype
    """
    lines = payload.get("lines", [])
    if not isinstance(lines, list) or len(lines) < 2:
        return error("posting_entry", "Validation failed", {"ok": False, "error": "lines must be a list with >= 2 legs"})

    # Basic DR=CR validation on amounts
    dr = sum(float(l.get("amount", 0)) for l in lines if str(l.get("side", "")).upper() == "DR")
    cr = sum(float(l.get("amount", 0)) for l in lines if str(l.get("side", "")).upper() == "CR")
    if abs(dr - cr) > 1e-9:
        return error("posting_entry", "Validation failed", {"ok": False, "error": f"Not balanced (DR={dr}, CR={cr})"})

    ticket_id = str(payload.get("ticket_id") or _new_ticket_id()).strip()
    if ticket_id in TICKETS:
        return error("posting_entry", "Store failed", {"ok": False, "error": f"Ticket already exists: {ticket_id}"})

    # Store DRAFT
    TICKETS[ticket_id] = {
        "ticket_id": ticket_id,
        "status": "draft",
        "created_by": user_id,
        "created_at": _now(),
        "execution_date": payload.get("execution_date"),
        "value_date": payload.get("value_date"),
        "lines": lines,
        "posted": False,
        "approvals": [],
    }

    return ok(
        "posting_entry",
        "Draft stored",
        {
            "ok": True,
            "ticket_id": ticket_id,
            "status": "draft",
            "next_actions": ["posting_submit"],
        },
    )


def handle_posting_submit(payload: Dict[str, Any], user_id: str, action: Optional[str]):
    ticket_id = str(payload.get("ticket_id", "")).strip()
    t = TICKETS.get(ticket_id)
    if not t:
        return error("posting_submit", "Submit failed", {"ok": False, "error": f"Ticket not found: {ticket_id}"})

    if t["status"] != "draft":
        return error("posting_submit", "Submit failed", {"ok": False, "error": f"Ticket not in draft state (current={t['status']})"})

    t["status"] = "submitted"
    t["submitted_at"] = _now()
    t["approvals"].append({"action": "submit", "by": user_id, "at": t["submitted_at"]})

    return ok(
        "posting_submit",
        "Ticket submitted",
        {"ok": True, "ticket_id": ticket_id, "status": "submitted", "next_actions": ["posting_approval"]},
    )


def handle_posting_approval(payload: Dict[str, Any], user_id: str, action: Optional[str]):
    ticket_id = str(payload.get("ticket_id", "")).strip()
    decision = str(payload.get("decision", "")).strip().lower()
    comment = str(payload.get("comment", "")).strip()

    t = TICKETS.get(ticket_id)
    if not t:
        return error("posting_approval", "Approval failed", {"ok": False, "error": f"Ticket not found: {ticket_id}"})

    if t["status"] != "submitted":
        return error("posting_approval", "Approval failed", {"ok": False, "error": f"Ticket not submitted (current={t['status']})"})

    if decision != "approve":
        return error("posting_approval", "Approval failed", {"ok": False, "error": "Only decision='approve' enabled in this phase"})

    # maker-checker separation
    if user_id == t["created_by"]:
        return error("posting_approval", "Approval failed", {"ok": False, "error": "Maker cannot approve own ticket"})

    t["status"] = "approved"
    t["approved_at"] = _now()
    t["approvals"].append({"action": "approve", "by": user_id, "comment": comment, "at": t["approved_at"]})

    return ok(
        "posting_approval",
        "Approved",
        {"ok": True, "ticket_id": ticket_id, "status": "approved", "next_actions": ["posting_result"]},
    )


def handle_posting_result(payload: Dict[str, Any], user_id: str, action: Optional[str]):
    """
    Executes immutable double-entry ledger write.
    Writes journal entries ONLY via ledger_registry.post_journal_entry().
    Idempotent: blocks if already posted.
    """
    ticket_id = str(payload.get("ticket_id", "")).strip()
    t = TICKETS.get(ticket_id)
    if not t:
        return error("posting_result", "Execution failed", {"ok": False, "error": f"Ticket not found: {ticket_id}"})

    if t["status"] != "approved":
        return error("posting_result", "Execution failed", {"ok": False, "error": "Ticket not approved"})

    if t.get("posted") is True:
        return error("posting_result", "Execution blocked", {"ok": False, "error": "Ticket already posted"})

    journal_entries = []
    for line in t["lines"]:
        # REQUIRED line fields for multi-account/multi-currency customer model:
        # base_account_no, account_type_code, currency, side, amount
        entry = post_journal_entry(
            ticket_id=ticket_id,
            user_id="system",
            side=str(line.get("side", "")).upper(),
            base_account_no=str(line.get("base_account_no", "")).strip(),
            account_type_code=str(line.get("account_type_code", "")).strip().upper(),
            currency=str(line.get("currency", "")).strip().upper(),
            amount=float(line.get("amount", 0.0)),
            narrative=str(line.get("narrative", "")).strip(),
        )
        journal_entries.append(entry)

    t["posted"] = True
    t["status"] = "posted"
    t["posted_at"] = _now()

    return ok(
        "posting_result",
        "Posting executed (double-entry ledger)",
        {
            "ok": True,
            "ticket_id": ticket_id,
            "status": "posted",
            "journal_entries": journal_entries,
            "ledger_integrity": "DR=CR enforced via journal",
        },
    )
