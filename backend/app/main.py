from fastapi import FastAPI
from typing import Dict, Any
from datetime import datetime

from screens.posting_entry import handle_posting_entry
from screens.posting_submit import handle_posting_submit
from screens.posting_review import handle_posting_review
from screens.posting_approval import handle_posting_approval
from screens.posting_result import handle_posting_result

app = FastAPI(title="REA Capital Orchestration API")

# -----------------------------------------------------------------------------
# In-memory ticket store (authoritative for Phase 13)
# -----------------------------------------------------------------------------
TICKETS: Dict[str, Dict[str, Any]] = {}

# -----------------------------------------------------------------------------
# Screen registry
# -----------------------------------------------------------------------------
SCREEN_HANDLERS = {
    "posting_entry": handle_posting_entry,
    "posting_submit": handle_posting_submit,
    "posting_review": handle_posting_review,
    "posting_approval": handle_posting_approval,
    "posting_result": handle_posting_result,
}

# -----------------------------------------------------------------------------
# Health
# -----------------------------------------------------------------------------
@app.get("/health")
def health():
    return {"status": "ok", "service": "REA Capital Orchestrator"}

# -----------------------------------------------------------------------------
# Orchestrator
# -----------------------------------------------------------------------------
@app.post("/orchestrate")
def orchestrate(payload: Dict[str, Any]):
    screen_id = payload.get("screen_id")
    action = payload.get("action")
    user_id = payload.get("user_id")

    if screen_id not in SCREEN_HANDLERS:
        return {
            "screen_id": screen_id,
            "status": "error",
            "message": "Unknown screen (not in taxonomy)",
            "data": {"known_screens": list(SCREEN_HANDLERS.keys())},
        }

    handler = SCREEN_HANDLERS[screen_id]

    return handler(
        payload=payload,
        tickets=TICKETS,
        user_id=user_id,
        now=datetime.utcnow(),
    )
