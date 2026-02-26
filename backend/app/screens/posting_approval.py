"""
backend/app/screens/posting_approval.py

Posting Approval (Checker decision) – Phase 15
-------------------------------------------------
- Approval snapshot logging
- Posting date governance (fail-closed)
- Override logging (hash-chained, append-only) via posting_date_policy
- Ledger posting hook on APPROVE (persistent Journal -> GL)
- Carries dimension bundle (dims) for multi-level reconciliation/reporting

Notes:
- Period-close is NOT overridable here.
- Backdate/future-date within OPEN periods requires an override with reason.
"""

from __future__ import annotations

import json
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, Any, Optional

from backend.app.posting_store import approve_ticket, reject_ticket, return_ticket
from backend.app.ledger.ledger_registry import post as ledger_post
from backend.app.posting_date_policy import evaluate_posting_date


def _repo_root() -> Path:
    # backend/app/screens/posting_approval.py -> parents[3] is repo root
    return Path(__file__).resolve().parents[3]


def _audit_dir() -> Path:
    out = _repo_root() / "audit_logs"
    out.mkdir(parents=True, exist_ok=True)
    return out


def _audit_write_posting_snapshot(payload: dict) -> None:
    try:
        out = _audit_dir() / "posting_snapshots.jsonl"
        with out.open("a", encoding="utf-8") as f:
            f.write(json.dumps(payload, ensure_ascii=False) + "\n")
    except Exception:
        return


def _extract_posting_date(payload: Dict[str, Any], ticket_obj: Any) -> Optional[str]:
    """
    Best-effort extraction order:
    1) payload.posting_date / payload.value_date
    2) ticket.posting_date / ticket.value_date
    3) None => policy will fail closed
    """
    for key in ("posting_date", "value_date", "effective_date", "txn_date"):
        v = payload.get(key)
        if v:
            return str(v)

    for attr in ("posting_date", "value_date", "effective_date", "txn_date"):
        v = getattr(ticket_obj, attr, None)
        if v:
            return str(v)

    return None


def posting_approval_handler(payload: Dict[str, Any], user_id: str | None = None) -> Dict[str, Any]:
    ticket_id = str(payload.get("ticket_id", "")).strip()
    decision = str(payload.get("decision", "")).strip().lower()

    if not ticket_id:
        return {"ok": False, "error": "ticket_id is required"}
    if decision not in {"approve", "reject", "return"}:
        return {"ok": False, "error": "decision must be one of approve, reject, return"}

    checker_id = (user_id or "anonymous_checker").strip() or "anonymous_checker"

    # Optional dimension bundle from UI
    dims = payload.get("dims") or {}
    if not isinstance(dims, dict):
        return {"ok": False, "error": "dims must be an object/dict if provided"}

    # Optional override payload (only used when policy requires it)
    # Expected structure (minimum):
    #   {"reason": "...", "approval_level": "CHECKER"}  (override_id optional)
    override = payload.get("override") or {}
    if override and not isinstance(override, dict):
        return {"ok": False, "error": "override must be an object/dict if provided"}

    try:
        if decision == "approve":
            t = approve_ticket(ticket_id, checker_id)
            maker_id = getattr(t, "created_by", None)

            posting_date = _extract_posting_date(payload, t)
            if not posting_date:
                return {"ok": False, "error": "posting_date (or value_date) is required for approval governance"}

            # ---------------------------
            # Posting Date Governance Gate
            # ---------------------------
            decision_gate = evaluate_posting_date(
                posting_date=posting_date,
                actor_user_id=checker_id,
                override=override if override else None,
                scope={
                    "ticket_id": ticket_id,
                    "checker_id": checker_id,
                    "maker_id": maker_id,
                    "action": "APPROVE_POSTING",
                },
            )

            if not decision_gate.allowed:
                _audit_write_posting_snapshot(
                    {
                        "timestamp": datetime.now(timezone.utc).timestamp(),
                        "event": "POSTING_APPROVAL_BLOCKED",
                        "phase": "PHASE_15",
                        "ticket_id": ticket_id,
                        "checker_id": checker_id,
                        "maker_id": maker_id,
                        "decision": "approve",
                        "blocked_by": "POSTING_DATE_POLICY",
                        "reason": decision_gate.reason,
                        "posting_date": posting_date,
                        "requires_override": decision_gate.requires_override,
                        "required_override_type": decision_gate.required_override_type,
                        "next_open_period": decision_gate.next_open_period_iso,
                        "dims": dims,
                    }
                )

                return {
                    "ok": False,
                    "error": decision_gate.reason,
                    "policy": {
                        "posting_date": posting_date,
                        "requires_override": decision_gate.requires_override,
                        "required_override_type": decision_gate.required_override_type,
                        "next_open_period": decision_gate.next_open_period_iso,
                    },
                }

            # ---------------------------
            # Ledger Posting (persistent Journal -> GL)
            # ---------------------------
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
                    "phase": "PHASE_15",
                    "ticket_id": ticket_id,
                    "checker_id": checker_id,
                    "maker_id": maker_id,
                    "decision": "approve",
                    "posting_date": decision_gate.posting_date_iso,
                    "override": decision_gate.override_record,
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
                "posting_date": decision_gate.posting_date_iso,
                "override": decision_gate.override_record,
                "ledger": ledger_result,
                "note": "Approved. Posting date governed. Journal appended + GL updated (persistent, dimensional).",
            }

        if decision == "reject":
            reason = str(payload.get("reason", "Rejected by checker")).strip() or "Rejected by checker"
            t = reject_ticket(ticket_id, checker_id, reason)
            _audit_write_posting_snapshot(
                {
                    "timestamp": datetime.now(timezone.utc).timestamp(),
                    "event": "POSTING_REJECT",
                    "phase": "PHASE_15",
                    "ticket_id": ticket_id,
                    "checker_id": checker_id,
                    "decision": "reject",
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

        if decision == "return":
            reason = str(payload.get("reason", "Returned for correction")).strip() or "Returned for correction"
            t = return_ticket(ticket_id, checker_id, reason)
            _audit_write_posting_snapshot(
                {
                    "timestamp": datetime.now(timezone.utc).timestamp(),
                    "event": "POSTING_RETURN",
                    "phase": "PHASE_15",
                    "ticket_id": ticket_id,
                    "checker_id": checker_id,
                    "decision": "return",
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