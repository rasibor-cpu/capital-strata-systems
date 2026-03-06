"""
posting_approval.py (repo root)
Capital Strata Systems (CSS)

Purpose:
- Provide stable import target for main.py:
    from posting_approval import handle_posting_approval
- Delegate to the real governance engine in backend.app.posting_approval
- Fail-closed if backend module isn't available.

This is a thin adapter only (no scope creep).
"""

from __future__ import annotations

from typing import Any, Dict


def handle_posting_approval(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Approval/governance gate. Returns APPROVED/REJECTED response dict.

    Expected minimal payload keys (based on your validate_posting tests):
      - account_no
      - side (DR/CR)
      - amount
    """
    if not isinstance(payload, dict):
        return {"status": "REJECTED", "reason_code": "INVALID_PAYLOAD_TYPE", "message": "payload must be a dict"}

    # Delegate to the backend governance module
    try:
        from backend.app.posting_approval import validate_posting  # authoritative gate
    except Exception as e:
        return {
            "status": "REJECTED",
            "reason_code": "IMPORT_ERROR",
            "message": f"backend.app.posting_approval.validate_posting not available: {e}",
        }

    try:
        return validate_posting(payload)
    except Exception as e:
        # Fail-closed: never crash main loop
        return {
            "status": "REJECTED",
            "reason_code": "VALIDATION_EXCEPTION",
            "message": str(e),
        }