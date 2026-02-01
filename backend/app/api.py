"""
FastAPI wrapper for Screen Orchestration (Phase 12.6)

Provides:
- POST /orchestrate

Note:
- This is prompt-only orchestration routing.
- No trade execution or auto-risk escalation exists here.
"""

from typing import Any, Dict, Optional
from fastapi import FastAPI
from pydantic import BaseModel

from .main import handle_screen_request


app = FastAPI(title="REA Capital Orchestration API", version="0.12.6")


class OrchestrateIn(BaseModel):
    screen_id: str
    action: str
    payload: Dict[str, Any] = {}
    user_id: Optional[str] = None


class OrchestrateOut(BaseModel):
    screen_id: str
    status: str
    message: str
    data: Dict[str, Any]


@app.get("/health")
def health() -> Dict[str, Any]:
    resp = handle_screen_request("health_check", "ping", {})
    return {
        "status": "ok",
        "orchestration": resp.data,
    }


@app.post("/orchestrate", response_model=OrchestrateOut)
def orchestrate(req: OrchestrateIn) -> OrchestrateOut:
    resp = handle_screen_request(req.screen_id, req.action, req.payload, user_id=req.user_id)
    return OrchestrateOut(
        screen_id=resp.screen_id,
        status=resp.status,
        message=resp.message,
        data=resp.data,
    )
