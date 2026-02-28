# main.py
# CSS / REA Capital Trading Engine – Orchestrator
# Phase 22D (startup accrual safety check wired)

from __future__ import annotations

from fastapi import FastAPI
from typing import Dict, Any
from datetime import datetime

from taxonomy import SCREEN_TAXONOMY

from posting_entry import handle_posting_entry
from posting_review import handle_posting_review
from posting_submit import handle_posting_submit
from posting_approval import handle_posting_approval

app = FastAPI(title="REA Capital Trading Engine")

# -------------------------------------------------------------------
# Startup Lifecycle Hook (Phase 22D)
# -------------------------------------------------------------------

@app.on_event("startup")
def _startup_safety_checks() -> None:
    """
    Startup safety checks must be:
    - deterministic
    - idempotent
    - fail-closed on critical finance integrity issues
    """

    # 1) Daily accrual safety check (idempotent; safe on restart)
    try:
        from engine.facility.accrual_engine import startup_accrual_check

        result = startup_accrual_check()
        print("======================================")
        print("CSS STARTUP SAFETY CHECKS")
        print(f"Timestamp: {datetime.utcnow().isoformat()}Z")
        print("Daily Accrual Check: OK")
        print(f"  Posting Date         : {result.get('posting_date')}")
        print(f"  Facilities Processed : {result.get('facilities_processed')}")
        print(f"  Accruals Posted      : {result.get('accruals_posted')}")
        print(f"  Total Accrued        : {result.get('total_interest_accrued')}")
        print("======================================\n")

    except Exception as exc:
        # Fail-closed: do not start the API if we cannot guarantee integrity.
        print("======================================")
        print("CSS STARTUP SAFETY CHECKS: FAILED")
        print(f"Timestamp: {datetime.utcnow().isoformat()}Z")
        print("Reason: Daily Accrual safety check failed.")
        print(f"Error: {str(exc)}")
        print("System will not start (fail-closed).")
        print("======================================\n")
        raise


# -------------------------------------------------------------------
# Screen → Handler Registry
# -------------------------------------------------------------------

SCREEN_HANDLERS = {
    "posting_entry": handle_posting_entry,
    "posting_review": handle_posting_review,
    "posting_submit": handle_posting_submit,
    "posting_approval": handle_posting_approval,
}

# -------------------------------------------------------------------
# Orchestrator Endpoint
# -------------------------------------------------------------------

@app.post("/orchestrate")
def orchestrate(request: Dict[str, Any]):
    screen_id = request.get("screen_id")
    action = request.get("action")
    payload = request.get("payload", {})
    user_id = request.get("user_id")

    # -----------------------------
    # Basic validation
    # -----------------------------
    if not screen_id:
        return {
            "screen_id": None,
            "status": "error",
            "message": "screen_id is required",
            "data": {}
        }

    if screen_id not in SCREEN_TAXONOMY:
        return {
            "screen_id": screen_id,
            "status": "error",
            "message": "Unknown screen (not in taxonomy)",
            "data": {
                "known_screens": list(SCREEN_TAXONOMY.keys())
            }
        }

    handler = SCREEN_HANDLERS.get(screen_id)

    if not handler:
        return {
            "screen_id": screen_id,
            "status": "not_implemented",
            "message": "Screen is defined in taxonomy but not implemented yet.",
            "data": {
                "screen_id": screen_id,
                "action": action,
                "status": "not_implemented",
                "next_step": "Implement handler and register it in main.py"
            }
        }

    # -----------------------------
    # Execute handler
    # -----------------------------
    try:
        result = handler(payload=payload, user_id=user_id)

        status = "ok" if result.get("ok") else "error"

        return {
            "screen_id": screen_id,
            "status": status,
            "message": SCREEN_TAXONOMY[screen_id].get("label", ""),
            "data": result
        }

    except Exception as exc:
        return {
            "screen_id": screen_id,
            "status": "error",
            "message": "Unhandled exception",
            "data": {
                "error": str(exc)
            }
        }

# -------------------------------------------------------------------
# Health Check
# -------------------------------------------------------------------

@app.get("/health")
def health_check():
    return {
        "status": "ok",
        "engine": "REA Capital Trading Engine",
        "phase": "22D"
    }