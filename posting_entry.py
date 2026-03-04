"""
posting_entry.py (repo root)
Capital Strata Systems (CSS)

Purpose (48-hour live protocol):
- Provide a stable import target for main.py:
    from posting_entry import handle_posting_entry
- Keep logic minimal and delegate to backend modules where available.
- Fail-closed: if backend handler is missing, return a safe error payload.

This is intentionally thin. We can harden later (post Phase-1 stabilization).
"""

from __future__ import annotations

from typing import Any, Dict


def handle_posting_entry(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Live protocol posting-entry handler.

    Expected payload (minimal):
      {
        "ticket_id": "...",
        "maker_user_id": "...",
        "execution_date": "YYYY-MM-DD",
        "value_date": "YYYY-MM-DD",
        "description": "...",
        "currency": "NGN",
        "override": {...} | None,
        "entries": [{"account_no":"...","side":"DR|CR","amount":"..."}]
      }

    Returns:
      {"status": "...", ...}
    """
    if not isinstance(payload, dict):
        return {"status": "REJECTED", "reason_code": "INVALID_PAYLOAD_TYPE", "message": "payload must be a dict"}

    # Prefer backend journal_writer as the single source of truth for posting.
    try:
        from backend.app.ledger.journal_writer import post_transaction  # type: ignore
    except Exception as e:
        return {
            "status": "REJECTED",
            "reason_code": "BACKEND_IMPORT_ERROR",
            "message": f"backend journal_writer not available: {e}",
        }

    # Minimal required fields (fail-closed)
    required = ["ticket_id", "maker_user_id", "execution_date", "value_date", "description", "currency", "entries"]
    missing = [k for k in required if k not in payload]
    if missing:
        return {
            "status": "REJECTED",
            "reason_code": "MISSING_FIELDS",
            "message": f"Missing required fields: {', '.join(missing)}",
        }

    entries = payload.get("entries")
    if not isinstance(entries, list) or not entries:
        return {"status": "REJECTED", "reason_code": "INVALID_ENTRIES", "message": "entries must be a non-empty list"}

    # Execute via the governed writer (calendar + approvals + hashing, as implemented)
    try:
        result = post_transaction(
            ticket_id=str(payload["ticket_id"]),
            maker_user_id=str(payload["maker_user_id"]),
            execution_date=str(payload["execution_date"]),
            value_date=str(payload["value_date"]),
            description=str(payload["description"]),
            currency=str(payload["currency"]),
            override=payload.get("override", None),
            entries=entries,
        )
        return {
            "status": "POSTED",
            "transaction_id": result.get("transaction_id"),
            "entries_written": result.get("entries_written", 0),
        }
    except PermissionError as pe:
        return {"status": "REJECTED", "reason_code": "PERMISSION", "message": str(pe)}
    except Exception as e:
        return {"status": "REJECTED", "reason_code": "POSTING_ERROR", "message": str(e)}