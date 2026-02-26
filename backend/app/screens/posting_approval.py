"""
backend/app/screens/posting_approval.py

Posting Approval (Checker decision) – Phase 13.6 → Phase 14 Wiring
------------------------------------------------------------------
Adds:
- Regulator-grade immutable approval snapshot logging (JSONL)
- Fail-safe audit write (never blocks approval)
- Phase 14: Ledger posting hook on APPROVE (Journal → GL in real-time)

Notes:
- Uses backend.app.posting_store as the single source of truth for ticket store + lifecycle.
- Ledger posting occurs ONLY after successful approval.
- No ledger posting occurs on reject/return.
"""

from __future__ import annotations

import json
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, Any

from backend.app.posting_store import approve_ticket, reject_ticket, return_ticket
from backend.app.ledger.ledger_registry import post as ledger_post


# ============================================================
# Internal Audit Writer (Fail-Safe)
# ============================================================

def _audit_write_posting_snapshot(payload: dict) -> None:
    """
    Writes immutable JSONL event.
    Must never interrupt posting approval flow.
    """
    try:
        Path("audit_logs").mkdir(parents=True, exist_ok=True)
        out = Path("audit_logs") / "posting_snapshots.jsonl"
        with out.open("a", encoding="utf-8") as f:
            f.write(json.dumps(payload, ensure_ascii=False) + "\n")
    except Exception:
        # Fail silent — approvals must never break due to reporting
        return


# ============================================================
# Checker Approval Handler
# ============================================================

def posting_approval_handler(
    payload: Dict[str, Any],
    user_id: str | None = None,
) -> Dict[str, Any]:
    """
    Expected payload:
      {
        "ticket_id": "T-0001",
        "decision": "approve" | "reject" | "return",
        "reason": "optional string"
      }
    """

    ticket_id = str(payload.get("ticket_id", "")).strip()
    decision = str(payload.get("decision", "")).strip().lower()

    if not ticket_id:
        return {"ok": False, "error": "ticket_id is required"}

    if decision not in {"approve", "reject", "return"}:
        return {"ok": False, "error": "decision must be one of approve, reject, return"}

    checker_id = (user_id or "anonymous_checker").strip() or "anonymous_checker"

    try:
        # ------------------------------------------------------------
        # APPROVE
        # ------------------------------------------------------------
        if decision == "approve":
            t = approve_ticket(ticket_id, checker_id)

            # Phase 14: post to ledger (Journal -> GL)
            ledger_result = ledger_post(t)

            # --- REGULATOR SNAPSHOT HOOK (post-success) ---
            _audit_write_posting_snapshot(
                {
                    "timestamp": datetime.now(timezone.utc).timestamp(),
                    "event": "POSTING_APPROVAL",
                    "phase": "PHASE_14",
                    "ticket_id": ticket_id,
                    "checker_id": checker_id,
                    "decision": "approve",
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
                "note": "Approved. Journal appended + GL updated (real-time).",
            }

        # ------------------------------------------------------------
        # REJECT
        # ------------------------------------------------------------
        if decision == "reject":
            reason = str(payload.get("reason", "Rejected by checker")).strip() or "Rejected by checker"
            t = reject_ticket(ticket_id, checker_id, reason)

            _audit_write_posting_snapshot(
                {
                    "timestamp": datetime.now(timezone.utc).timestamp(),
                    "event": "POSTING_REJECT",
                    "phase": "PHASE_14",
                    "ticket_id": ticket_id,
                    "checker_id": checker_id,
                    "decision": "reject",
                    "reason": reason,
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

        # ------------------------------------------------------------
        # RETURN
        # ------------------------------------------------------------
        if decision == "return":
            reason = str(payload.get("reason", "Returned for correction")).strip() or "Returned for correction"
            t = return_ticket(ticket_id, checker_id, reason)

            _audit_write_posting_snapshot(
                {
                    "timestamp": datetime.now(timezone.utc).timestamp(),
                    "event": "POSTING_RETURN",
                    "phase": "PHASE_14",
                    "ticket_id": ticket_id,
                    "checker_id": checker_id,
                    "decision": "return",
                    "reason": reason,
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