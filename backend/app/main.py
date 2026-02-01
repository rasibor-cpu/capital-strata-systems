from typing import Dict, Any, Tuple, List
from datetime import datetime
from fastapi import Request


# =========================
# In-memory stores (Phase 13)
# =========================
TICKETS: Dict[str, Dict[str, Any]] = {}
LEDGER_ENTRIES: List[Dict[str, Any]] = []
BALANCES: Dict[Tuple[str, str], float] = {}  # (account_no, currency) -> signed balance
AUDIT_LOG: List[Dict[str, Any]] = []


def _now() -> str:
    return datetime.utcnow().isoformat()


def _ok(screen_id: str, message: str, data: Dict[str, Any]) -> Dict[str, Any]:
    return {"screen_id": screen_id, "status": "ok", "message": message, "data": data}


def _err(screen_id: str, message: str, error: str, data: Dict[str, Any] | None = None) -> Dict[str, Any]:
    out = {"screen_id": screen_id, "status": "error", "message": message, "data": {"ok": False, "error": error}}
    if data:
        out["data"].update(data)
    return out


def _not_impl(screen_id: str, action: str) -> Dict[str, Any]:
    return {
        "screen_id": screen_id,
        "status": "not_implemented",
        "message": "Screen not implemented yet",
        "data": {
            "screen_id": screen_id,
            "action": action,
            "status": "not_implemented",
            "message": "Screen is defined in taxonomy but not implemented yet.",
        },
    }


def _calc_totals(lines: List[Dict[str, Any]]) -> Dict[str, Any]:
    dr_total = 0.0
    cr_total = 0.0
    for ln in lines:
        side = str(ln.get("side", "")).strip().upper()
        amt = float(ln.get("amount", 0.0))
        if side == "DR":
            dr_total += amt
        elif side == "CR":
            cr_total += amt
    return {"dr_total": dr_total, "cr_total": cr_total, "balanced": abs(dr_total - cr_total) < 1e-9}


# =========================
# API helpers used by backend/app/api.py shim
# =========================
async def health() -> Dict[str, Any]:
    return _ok(
        "health",
        "ok",
        {
            "server_time": _now(),
            "engine_mode": "prompt-only",
            "execution_enabled": False,
            "tickets_in_memory": len(TICKETS),
        },
    )


async def orchestrate(request: Request) -> Dict[str, Any]:
    body = await request.json()
    screen_id = str(body.get("screen_id", "")).strip()
    action = str(body.get("action", "")).strip()
    payload = body.get("payload", {}) or {}
    user_id = body.get("user_id", None)

    if not screen_id:
        return _err("unknown", "Bad request", "screen_id is required")

    handlers = {
        "posting_entry": handle_posting_entry,
        "posting_submit": handle_posting_submit,
        "posting_review": handle_posting_review,
        "posting_approval": handle_posting_approval,
        "posting_result": handle_posting_result,
    }

    handler = handlers.get(screen_id)
    if not handler:
        return _not_impl(screen_id, action)

    return handler(payload=payload, user_id=user_id, action=action)


# =========================
# HANDLERS (Phase 13)
# =========================

def handle_posting_entry(payload: Dict[str, Any], user_id: str | None, action: str) -> Dict[str, Any]:
    """
    Creates DRAFT ticket after validation.
    Expects payload:
      ticket_id, execution_date, value_date, lines[]
    """
    ticket_id = str(payload.get("ticket_id", "")).strip()
    execution_date = str(payload.get("execution_date", "")).strip()
    value_date = str(payload.get("value_date", "")).strip()
    lines = payload.get("lines", []) or []

    if not ticket_id:
        return _err("posting_entry", "Validation failed", "ticket_id is required")
    if not execution_date or not value_date:
        return _err("posting_entry", "Validation failed", "execution_date and value_date are required")
    if not isinstance(lines, list) or len(lines) < 2:
        return _err("posting_entry", "Validation failed", "lines must be a list with at least 2 lines")

    # Normalize + basic validation
    norm_lines: List[Dict[str, Any]] = []
    for i, ln in enumerate(lines):
        side = str(ln.get("side", "")).strip().upper()
        acct = str(ln.get("account_no", "")).strip()
        ccy = str(ln.get("currency", "")).strip()
        narrative = str(ln.get("narrative", "")).strip()
        amt = float(ln.get("amount", 0.0))

        if side not in {"DR", "CR"}:
            return _err("posting_entry", "Validation failed", f"Line {i}: side must be DR or CR")
        if not acct:
            return _err("posting_entry", "Validation failed", f"Line {i}: account_no required")
        if not ccy or ccy.upper() != ccy:
            return _err("posting_entry", "Validation failed", f"Line {i}: currency must be FULL TEXT UPPERCASE")
        if amt <= 0:
            return _err("posting_entry", "Validation failed", f"Line {i}: amount must be > 0")

        norm_lines.append(
            {"side": side, "account_no": acct, "currency": ccy, "amount": amt, "narrative": narrative}
        )

    totals = _calc_totals(norm_lines)
    if not totals["balanced"]:
        return _err(
            "posting_entry",
            "Validation failed",
            f"Ticket not balanced (DR={totals['dr_total']}, CR={totals['cr_total']})",
        )

    if ticket_id in TICKETS:
        return _err("posting_entry", "Store failed", f"Ticket already exists: {ticket_id}")

    ticket = {
        "ticket_id": ticket_id,
        "created_by": user_id or "anonymous",
        "created_at": _now(),
        "execution_date": execution_date,
        "value_date": value_date,
        "status": "draft",
        "lines": norm_lines,
        "totals": totals,
        "approvals": [],
        "posted": False,
    }
    TICKETS[ticket_id] = ticket

    return _ok(
        "posting_entry",
        "Posting entry (validate + store draft)",
        {
            "ok": True,
            "ticket": {
                "ticket_id": ticket_id,
                "created_by": ticket["created_by"],
                "execution_date": execution_date,
                "value_date": value_date,
                "status": ticket["status"],
                "line_count": len(norm_lines),
            },
            "totals": totals,
            "stored": True,
            "next_actions": ["submit_ticket"],
            "note": "Validation passed. Ticket stored as DRAFT in memory. No ledger posting.",
        },
    )


def handle_posting_submit(payload: Dict[str, Any], user_id: str | None, action: str) -> Dict[str, Any]:
    ticket_id = str(payload.get("ticket_id", "")).strip()
    if not ticket_id:
        return _err("posting_submit", "Submit failed", "ticket_id is required")

    t = TICKETS.get(ticket_id)
    if not t:
        return _err("posting_submit", "Submit failed", f"Ticket not found: {ticket_id}")

    if t["status"] != "draft":
        return _err("posting_submit", "Submit failed", f"Only draft tickets can be submitted (current={t['status']})")

    t["status"] = "submitted"
    t["submitted_at"] = _now()
    t["approvals"].append({"action": "submit", "by": user_id or "anonymous", "at": t["submitted_at"]})

    return _ok(
        "posting_submit",
        "Ticket submitted",
        {
            "ok": True,
            "ticket": {"ticket_id": ticket_id, "status": "submitted", "submitted_at": t["submitted_at"]},
            "next_actions": ["checker_review", "checker_decision"],
        },
    )


def handle_posting_review(payload: Dict[str, Any], user_id: str | None, action: str) -> Dict[str, Any]:
    ticket_id = str(payload.get("ticket_id", "")).strip()
    if not ticket_id:
        return _err("posting_review", "Review failed", "ticket_id is required")

    t = TICKETS.get(ticket_id)
    if not t:
        return _err("posting_review", "Review failed", f"Ticket not found: {ticket_id}")

    return _ok(
        "posting_review",
        "Posting ticket review",
        {
            "ok": True,
            "ticket": {
                "ticket_id": t["ticket_id"],
                "status": t["status"],
                "created_by": t["created_by"],
                "created_at": t["created_at"],
                "submitted_at": t.get("submitted_at"),
                "execution_date": t["execution_date"],
                "value_date": t["value_date"],
                "line_count": len(t["lines"]),
            },
            "lines": t["lines"],
            "totals": t["totals"],
            "approvals": t["approvals"],
            "note": "Read-only review. No changes applied.",
        },
    )


def handle_posting_approval(payload: Dict[str, Any], user_id: str | None, action: str) -> Dict[str, Any]:
    ticket_id = str(payload.get("ticket_id", "")).strip()
    decision = str(payload.get("decision", "")).strip().lower()
    comment = str(payload.get("comment", "")).strip()

    if not ticket_id:
        return _err("posting_approval", "Approval failed", "ticket_id is required")
    if decision not in {"approve", "reject", "return"}:
        return _err("posting_approval", "Approval failed", "decision must be approve|reject|return")

    t = TICKETS.get(ticket_id)
    if not t:
        return _err("posting_approval", "Approval failed", f"Ticket not found: {ticket_id}")

    if t["status"] != "submitted":
        return _err("posting_approval", "Approval failed", f"Only submitted tickets can be decided (current={t['status']})")

    checker = user_id or "anonymous_checker"
    if checker == t["created_by"]:
        return _err("posting_approval", "Approval failed", "Maker cannot approve/reject/return own ticket")

    if decision == "approve":
        t["status"] = "approved"
    elif decision == "reject":
        t["status"] = "rejected"
    else:
        t["status"] = "returned"

    at = _now()
    t["approvals"].append({"action": decision, "by": checker, "comment": comment, "at": at})

    return _ok(
        "posting_approval",
        f"Ticket {decision}d" if decision != "return" else "Ticket returned",
        {
            "ok": True,
            "decision": decision,
            "ticket": {"ticket_id": ticket_id, "status": t["status"]},
            "next_actions": (["posting_result"] if decision == "approve" else ["posting_entry"]),
            "note": "Decision recorded (no ledger write until posting_result).",
        },
    )


def handle_posting_result(payload: Dict[str, Any], user_id: str | None, action: str) -> Dict[str, Any]:
    """
    Executes ledger write for APPROVED tickets and marks them POSTED.
    Idempotent: if already posted, returns ok with idempotent=True
    """
    ticket_id = str(payload.get("ticket_id", "")).strip()
    if not ticket_id:
        return _err("posting_result", "Execution failed", "ticket_id is required")

    t = TICKETS.get(ticket_id)
    if not t:
        return _err("posting_result", "Execution failed", f"Ticket not found: {ticket_id}")

    if t["status"] != "approved":
        return _err("posting_result", "Execution failed", f"Ticket must be approved (current={t['status']})")

    if t.get("posted") is True:
        return _ok(
            "posting_result",
            "Already posted",
            {
                "ok": True,
                "idempotent": True,
                "ticket": {"ticket_id": ticket_id, "status": "posted", "posted_at": t.get("posted_at")},
                "ledger_written": False,
            },
        )

    # Ledger write
    posted_at = _now()
    for ln in t["lines"]:
        side = ln["side"]
        acct = ln["account_no"]
        ccy = ln["currency"]
        amt = float(ln["amount"])

        # Signed balances: DR increases (+), CR decreases (-)
        key = (acct, ccy)
        cur = float(BALANCES.get(key, 0.0))
        new = cur + amt if side == "DR" else cur - amt
        BALANCES[key] = new

        LEDGER_ENTRIES.append(
            {
                "ticket_id": ticket_id,
                "side": side,
                "account_no": acct,
                "currency": ccy,
                "amount": amt,
                "narrative": ln.get("narrative", ""),
                "posted_at": posted_at,
            }
        )

    t["status"] = "posted"
    t["posted"] = True
    t["posted_at"] = posted_at

    AUDIT_LOG.append({"ticket_id": ticket_id, "action": "execute_posting", "by": user_id or "system", "at": posted_at})

    return _ok(
        "posting_result",
        "Posting executed successfully",
        {
            "ok": True,
            "ticket": {"ticket_id": ticket_id, "status": "posted", "posted_at": posted_at},
            "ledger_written": True,
            "entries_written": len(t["lines"]),
            "balances_touched": len(set((ln["account_no"], ln["currency"]) for ln in t["lines"])),
            "audit_logged": True,
        },
    )
