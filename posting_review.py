"""
posting_review.py (repo root)
Capital Strata Systems (CSS)

Purpose (48-hour live protocol):
- Provide a stable import target for main.py:
    from posting_review import handle_posting_review
- Minimal stub that can be expanded into a real review/queue UI later.

This is intentionally minimal and safe.
"""

from __future__ import annotations

from typing import Any, Dict


def handle_posting_review(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Minimal review handler (Phase-1 live protocol):
    - For now, just confirms service is up and echoes the request id/ticket id if present.

    Later:
    - Pull unapproved queue
    - Render by maker_user_id / ticket_id / date
    - Export print packs
    """
    if not isinstance(payload, dict):
        return {"status": "REJECTED", "reason_code": "INVALID_PAYLOAD_TYPE", "message": "payload must be a dict"}

    ticket_id = payload.get("ticket_id")
    maker_user_id = payload.get("maker_user_id")

    return {
        "status": "OK",
        "message": "posting_review online (minimal)",
        "ticket_id": ticket_id,
        "maker_user_id": maker_user_id,
    }