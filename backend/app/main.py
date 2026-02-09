from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# Headless runner (prints [HEADLESS] logs)
from backend.app.headless_guarded_entry import run_headless


# -----------------------------------------------------------------------------
# App
# -----------------------------------------------------------------------------

auth_loaded: bool = False
auth_error: Optional[str] = None

app = FastAPI(title="REA Capital Trading Engine", version="0.1.0")

# CORS: UI is loaded via file:// (Origin: null), so allow all for local dev
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Try-load auth router (fail-closed but server still boots)
try:
    from backend.app.auth.auth_router import router as auth_router  # type: ignore

    app.include_router(auth_router)
    auth_loaded = True
except Exception as e:  # pragma: no cover
    auth_loaded = False
    auth_error = f"{type(e).__name__}: {e}"


# -----------------------------------------------------------------------------
# Models
# -----------------------------------------------------------------------------

class HeadlessRunRequest(BaseModel):
    steps: int = Field(default=50, ge=1, le=1_000_000)
    symbol: str = Field(default="EURUSD", min_length=1, max_length=32)


# -----------------------------------------------------------------------------
# Routes
# -----------------------------------------------------------------------------

@app.get("/health")
def health() -> Dict[str, Any]:
    return {
        "status": "ok",
        "auth_loaded": auth_loaded,
        "auth_error": auth_error,
    }


@app.get("/routes")
def routes() -> List[str]:
    # Return visible routes for debugging
    return [getattr(r, "path", str(r)) for r in app.router.routes]


@app.post("/engine/headless/run")
def engine_headless_run(req: HeadlessRunRequest) -> Dict[str, Any]:
    """
    HEADLESS DEV endpoint.
    IMPORTANT: We must never return null; always return a JSON object.

    The runner may currently return None (which becomes JSON null).
    So we wrap it and always return a summary payload.
    """
    result = run_headless(steps=req.steps, symbol=req.symbol)

    # Force a useful JSON response even if runner returns None
    if result is None:
        return {
            "ok": True,
            "mode": "HEADLESS_DEV",
            "locked": True,
            "steps": req.steps,
            "symbol": req.symbol,
            "result": None,
            "notes": [
                "Runner returned None (no payload yet) — returning summary wrapper.",
                "Execution layer locked (no live trades).",
            ],
        }

    return {
        "ok": True,
        "mode": "HEADLESS_DEV",
        "locked": True,
        "steps": req.steps,
        "symbol": req.symbol,
        "result": result,
    }
