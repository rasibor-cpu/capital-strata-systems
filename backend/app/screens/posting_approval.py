"""
backend/app/screens/posting_approval.py

Posting Approval (Checker decision) – Phase 13.6
------------------------------------------------
Adds:
- Regulator-grade immutable approval snapshot logging (JSONL)
- Fail-safe audit write (never blocks approval)
"""

from __future__ import annotations

import json
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, Any

from backend.app.posting_store import approve_ticket, reject_ticket, return_ticket


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

    ticket_id = payload.get("ticket_id")
    decision = payload.get("decision")

    if not ticket_id:
        return {"ok": False, "error": "ticket_id is required"}

    if decision not in {"approve", "reject", "return"}:
        return {"ok": False, "error": "decision must be one of approve, reject, return"}

    checker_id = user_id or "anonymous_checker"

    try:
        # ------------------------------------------------------------
        # APPROVE
        # ------------------------------------------------------------
        if decision == "approve":
            t = approve_ticket(ticket_id, checker_id)

            # --- REGULATOR SNAPSHOT HOOK (post-success) ---
            _audit_write_posting_snapshot(
                {
                    "timestamp": datetime.now(timezone.utc).timestamp(),
                    "event": "POSTING_APPROVAL",
                    "phase": "PHASE_13_6",
                    "ticket_id": ticket_id,
                    "checker_id": checker_id,
                    "decision": "approve",
                    "ticket_status": getattr(t, "status", None).value
                    if getattr(t, "status", None)
                    else None,
                }
            )

            return {
                "decision": "approve",
                "ticket": {"ticket_id": getattr(t, "ticket_id", ticket_id), "status": t.status.value},
                "note": "Approved (ledger execution handled downstream).",
            }

        # ------------------------------------------------------------
        # REJECT
        # ------------------------------------------------------------
        if decision == "reject":
            reason = payload.get("reason", "Rejected by checker")
            t = reject_ticket(ticket_id, checker_id, reason)

            return {
                "decision": "reject",
                "ticket": {"ticket_id": getattr(t, "ticket_id", ticket_id), "status": t.status.value},
                "note": reason,
            }

        # ------------------------------------------------------------
        # RETURN
        # ------------------------------------------------------------
        # NOTE: we keep the decision string "return" for API compatibility
        if decision == "return":
            reason = payload.get("reason", "Returned for correction")
            t = return_ticket(ticket_id, checker_id, reason)

            return {
                "decision": "return",
                "ticket": {"ticket_id": getattr(t, "ticket_id", ticket_id), "status": t.status.value},
                "note": "Returned to maker (no ledger write).",
            }

    except Exception as e:
        return {"ok": False, "error": str(e)}