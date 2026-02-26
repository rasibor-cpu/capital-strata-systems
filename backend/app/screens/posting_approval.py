"""
backend/app/screens/posting_approval.py

Posting Approval Screen (Checker Decision)
------------------------------------------
Workflow:
- approve / reject / return a ticket
- on APPROVE: append Journal + update GL (via ledger_registry.post)

Governance:
- Calls backend.app.posting_approval.validate_posting BEFORE ledger write.
- Fail-closed if governance gate is missing.
- AUDIT_CONTROL cannot approve/post (blocked by gate).
- TREASURY maker postings require dims.instrument_id (validated by gate).
"""

from __future__ import annotations

import json
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, Any

from backend.app.posting_store import approve_ticket, reject_ticket, return_ticket
from backend.app.ledger.ledger_registry import post as ledger_post

# Governance gate (fail-closed if missing)
try:
    from backend.app.posting_approval import validate_posting  # type: ignore
except Exception:  # pragma: no cover
    validate_posting = None


def _audit_write_posting_snapshot(payload: dict) -> None:
    try:
        Path("audit_logs").mkdir(parents=True, exist_ok=True)
        out = Path("audit_logs") / "posting_snapshots.jsonl"
        with out.open("a", encoding="utf-8") as f:
            f.write(json.dumps(payload, ensure_ascii=False) + "\n")
    except Exception:
        return


def posting_approval_handler(payload: Dict[str, Any], user_id: str | None = None) -> Dict[str, Any]:
    """
    Entry-point used by UI routing layer.

    Expected payload:
      - ticket_id: str
      - decision: "approve" | "reject" | "return"
      - role: caller role (e.g., "SUPER_USER", "FINCON_REPORTING", "AUDIT_CONTROL", "TREASURY")
      - maker_user_id: optional (recommended for pre-gate)
      - dims: optional dict
      - reason: optional for reject/return
    """
    ticket_id = str(payload.get("ticket_id", "")).strip()
    decision = str(payload.get("decision", "")).strip().lower()

    if not ticket_id:
        return {"ok": False, "error": "ticket_id is required"}
    if decision not in {"approve", "reject", "return"}:
        return {"ok": False, "error": "decision must be one of approve, reject, return"}

    checker_id = (user_id or "anonymous_checker").strip() or "anonymous_checker"
    role = str(payload.get("role") or payload.get("actor_role") or "UNKNOWN").strip().upper()

    dims = payload.get("dims") or {}
    if not isinstance(dims, dict):
        return {"ok": False, "error": "dims must be an object/dict if provided"}

    maker_user_id = str(payload.get("maker_user_id") or "").strip()

    try:
        # =========================
        # APPROVE
        # =========================
        if decision == "approve":
            # FAIL-CLOSED if gate missing
            if validate_posting is None:
                return {
                    "ok": False,
                    "error": "Governance gate missing: backend.app.posting_approval.validate_posting not available (fail-closed).",
                }

            # Prefer gating BEFORE touching ticket state if maker_user_id provided
            if maker_user_id:
                gate = validate_posting({"maker_user_id": maker_user_id, "dims": dims}, role)
                if not gate.get("approved", False):
                    reason = str(gate.get("reason") or "Governance gate blocked approval.")
                    _audit_write_posting_snapshot(
                        {
                            "timestamp": datetime.now(timezone.utc).timestamp(),
                            "event": "POSTING_APPROVAL_BLOCKED",
                            "ticket_id": ticket_id,
                            "checker_id": checker_id,
                            "maker_id": maker_user_id,
                            "role": role,
                            "dims": dims,
                            "reason": reason,
                        }
                    )
                    return {"ok": False, "error": reason}

            # Approve ticket (now we can reliably get maker_id from ticket if not supplied)
            t = approve_ticket(ticket_id, checker_id)
            maker_id = getattr(t, "created_by", None) or maker_user_id

            # If maker_user_id wasn't supplied, gate AFTER approval but BEFORE ledger write.
            # If blocked, we auto-return to maker to avoid leaving it approved without ledger posting.
            if not maker_user_id:
                gate = validate_posting({"maker_user_id": maker_id, "dims": dims}, role)
                if not gate.get("approved", False):
                    reason = str(gate.get("reason") or "Governance gate blocked approval.")
                    try:
                        return_ticket(ticket_id, checker_id, f"Auto-return (governance): {reason}")
                    except Exception:
                        pass

                    _audit_write_posting_snapshot(
                        {
                            "timestamp": datetime.now(timezone.utc).timestamp(),
                            "event": "POSTING_APPROVAL_BLOCKED_AFTER_APPROVE",
                            "ticket_id": ticket_id,
                            "checker_id": checker_id,
                            "maker_id": maker_id,
                            "role": role,
                            "dims": dims,
                            "reason": reason,
                        }
                    )
                    return {"ok": False, "error": reason}

            # Ledger post (persistent Journal -> GL)
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
                    "ticket_id": ticket_id,
                    "checker_id": checker_id,
                    "maker_id": maker_id,
                    "decision": "approve",
                    "role": role,
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
                "note": "Approved. Governance passed. Journal appended + GL updated.",
            }

        # =========================
        # REJECT
        # =========================
        if decision == "reject":
            reason = str(payload.get("reason", "Rejected by checker")).strip() or "Rejected by checker"
            t = reject_ticket(ticket_id, checker_id, reason)

            _audit_write_posting_snapshot(
                {
                    "timestamp": datetime.now(timezone.utc).timestamp(),
                    "event": "POSTING_REJECT",
                    "ticket_id": ticket_id,
                    "checker_id": checker_id,
                    "decision": "reject",
                    "role": role,
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

        # =========================
        # RETURN
        # =========================
        if decision == "return":
            reason = str(payload.get("reason", "Returned for correction")).strip() or "Returned for correction"
            t = return_ticket(ticket_id, checker_id, reason)

            _audit_write_posting_snapshot(
                {
                    "timestamp": datetime.now(timezone.utc).timestamp(),
                    "event": "POSTING_RETURN",
                    "ticket_id": ticket_id,
                    "checker_id": checker_id,
                    "decision": "return",
                    "role": role,
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