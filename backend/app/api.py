"""
FastAPI wrapper for REA Capital Orchestration API

This module MUST export: app
Runner expects: app.api:app

We delegate orchestration to backend/app/main.py::orchestrate (already implemented).
"""

from typing import Any, Dict, Optional

from fastapi import FastAPI, Request
from pydantic import BaseModel

from .main import orchestrate  # async endpoint handler


app = FastAPI(title="REA Capital Orchestration API", version="0.13.0")


class OrchestrateIn(BaseModel):
    screen_id: str
    action: str
    payload: Dict[str, Any] = {}
    user_id: Optional[str] = None


@app.get("/health")
async def health() -> Dict[str, Any]:
    # Call main.orchestrate with a synthetic Request-like payload is messy,
    # so we provide a simple health response here.
    return {"status": "ok"}


@app.post("/orchestrate")
async def orchestrate_entry(req: OrchestrateIn, request: Request) -> Any:
    """
    Bridge: take validated JSON body and pass it to main.orchestrate
    by reusing the actual Starlette Request object and its JSON.
    """
    # Monkeypatch request.json() by using the already-parsed body:
    # simplest: attach to request.state and let main.orchestrate read request.json()
    # But main.orchestrate calls await request.json(), so we provide a small shim.

    class _ShimRequest:
        async def json(self) -> Dict[str, Any]:
            return req.model_dump()

    return await orchestrate(_ShimRequest())
