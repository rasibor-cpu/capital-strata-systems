"""
backend.app.main – REA Capital Trading Engine API

Goal of this file:
- Never discard/overwrite headless payloads.
- Keep auth optional for HEADLESS_DEV endpoints.
- Provide /health and /routes for quick diagnostics.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field


app = FastAPI(title="REA Capital Trading Engine", version="0.1")


# ------------------------------------------------------------
# CORS (dev friendly)
# ------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ------------------------------------------------------------
# Optional auth wiring (do NOT hard-fail startup)
# ------------------------------------------------------------
_AUTH_LOADED: bool = False
_AUTH_ERROR: Optional[str] = None

try:
    # If your project has an auth router, we include it.
    # This MUST NOT break headless.
    from backend.app.auth.router import router as auth_router  # type: ignore

    app.include_router(auth_router, prefix="/auth", tags=["auth"])
    _AUTH_LOADED = True
except Exception as e:
    _AUTH_LOADED = False
    _AUTH_ERROR = f"{type(e).__name__}: {e}"


# ------------------------------------------------------------
# Models
# ------------------------------------------------------------
class HeadlessRunRequest(BaseModel):
    steps: int = Field(default=50, ge=1, le=5000)
    symbol: str = Field(default="EURUSD", min_length=3, max_length=30)


# ------------------------------------------------------------
# Routes
# ------------------------------------------------------------
@app.get("/health", tags=["system"])
def health() -> Dict[str, Any]:
    return {"status": "ok", "auth_loaded": _AUTH_LOADED, "auth_error": _AUTH_ERROR}


@app.get("/routes", tags=["system"])
def routes() -> List[str]:
    return [getattr(r, "path", "") for r in app.router.routes]


@app.post("/engine/headless/run", tags=["engine"])
def engine_headless_run(req: HeadlessRunRequest) -> Dict[str, Any]:
    """
    CRITICAL: return the run_headless(...) dict AS-IS.
    No wrapper that can overwrite result with {}.
    """
    try:
        from backend.app.headless_guarded_entry import run_headless  # type: ignore

        payload = run_headless(steps=req.steps, symbol=req.symbol)

        # Enforce predictable structure: never allow accidental {}
        if not isinstance(payload, dict):
            return {
                "ok": False,
                "error_type": "TypeError",
                "error": f"run_headless returned non-dict: {type(payload).__name__}",
                "hint": "run_headless must return a dict.",
            }

        # If older code returns {}, we surface it clearly
        if payload.get("ok") is True and payload.get("result") in (None, {}, []):
            payload["warning"] = (
                "Headless returned empty result. "
                "This indicates the underlying headless implementation is still returning {}."
            )

        return payload

    except Exception as e:
        return {
            "ok": False,
            "error_type": type(e).__name__,
            "error": str(e),
            "hint": "Dev-safe wrapper. Root cause is inside headless_guarded_entry.run_headless(...) or its imports.",
        }
