"""
ticket_store.py
---------------
Authoritative in-memory ticket registry for posting lifecycle.

Ticket states:
- draft
- submitted
- approved
- rejected
- posted

Design principles:
- Deterministic, auditable, simple
- No external dependencies
"""

from __future__ import annotations
from dataclasses import dataclass, asdict
from typing import Dict, Any, Optional
from datetime import datetime

# In-memory store (process-local)
_TICKETS: Dict[str, Dict[str, Any]] = {}
_TICKET_SEQ = 0


def _now_iso() -> str:
    return datetime.utcnow().isoformat()


def _next_ticket_id() -> str:
    global _TICKET_SEQ
    _TICKET_SEQ += 1
    return f"T-{_TICKET_SEQ:04d}"


def create_or_update_ticket(payload: Dict[str, Any], created_by: str, status: str = "draft") -> Dict[str, Any]:
    """
    Create a new ticket. If payload includes ticket_id and it exists, update payload only if still draft.
    """
    ticket_id = payload.get("ticket_id")

    if ticket_id and ticket_id in _TICKETS:
        t = _TICKETS[ticket_id]
        if t["status"] != "draft":
            return t  # immutable once not draft
        t["payload"] = payload
        t["updated_at"] = _now_iso()
        return t

    ticket_id = _next_ticket_id()
    ticket = {
        "ticket_id": ticket_id,
        "status": status,
        "payload": payload,
        "created_by": created_by,
        "created_at": _now_iso(),
        "updated_at": _now_iso(),
        "last_comment": "",
    }
    _TICKETS[ticket_id] = ticket
    return ticket


def get_ticket(ticket_id: str) -> Dict[str, Any]:
    if ticket_id not in _TICKETS:
        raise KeyError(f"Ticket not found: {ticket_id}")
    return _TICKETS[ticket_id]


def update_ticket_status(ticket_id: str, new_status: str, comment: str = "") -> Dict[str, Any]:
    t = get_ticket(ticket_id)
    t["status"] = new_status
    if comment:
        t["last_comment"] = comment
    t["updated_at"] = _now_iso()
    return t


def reset_ticket_store() -> Dict[str, Any]:
    """
    Test-only helper: clears ticket store.
    """
    global _TICKET_SEQ
    _TICKETS.clear()
    _TICKET_SEQ = 0
    return {"ok": True, "tickets": 0}
