"""
posting_submit.py (repo root)
Capital Strata Systems (CSS)

Purpose:
- Provide stable import target for main.py:
    from posting_submit import handle_posting_submit
- Delegate to the real posting submit handler (backend) if present.
- Fail-closed (never crash main loop).

This is a thin adapter only.
"""

from __future__ import annotations

from typing import Any, Dict


def handle_posting_submit(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Submit a posting request (pre-approval / workflow entrypoint).

    Minimal expected payload keys (typical):
      - ticket_id
      - maker_user_id
      - entries (list)
      - execution_date / value_date (optional depending on your backend)
    """
    if not isinstance(payload, dict):
        return {"status": "REJECTED", "reason_code": "INVALID_PAYLOAD_TYPE", "message": "payload must be a dict"}

    # Try delegate to backend, if implemented
    try:
        # Preferred: a dedicated submit handler
        from backend.app.posting_submit import handle_posting_submit as backend_submit  # type: ignore
        return backend_submit(payload)
    except ModuleNotFoundError:
        # If no backend submit module exists yet, provide a safe placeholder response.
        return {
            "status": "REJECTED",
            "reason_code": "SUBMIT_NOT_IMPLEMENTED",
            "message": "Posting submit handler not implemented yet (backend.app.posting_submit missing).",
        }
    except Exception as e:
        # Fail-closed
        return {"status": "REJECTED", "reason_code": "SUBMIT_EXCEPTION", "message": str(e)}