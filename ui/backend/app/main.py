"""
Main FastAPI app – REA Capital Trading Engine

Adds:
- Auth router (Phase 1)
- CORS middleware so standalone file:// UI can call localhost API safely
"""

from __future__ import annotations

from fastapi import FastAPI

# CORS (needed for file:// and separate UI origins)
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="REA Capital – Trading Engine", version="phase-1")

# Allow local UI calls (file:// or any localhost origin)
# Phase 1: wide-open CORS is acceptable for local dev only.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Auth router (Phase 1)
try:
    from app.auth.auth_router import router as auth_router  # type: ignore
    app.include_router(auth_router)
except Exception as e:
    try:
        from .auth.auth_router import router as auth_router  # type: ignore
        app.include_router(auth_router)
    except Exception as fallback_error:
        print(f"[WARN] Auth router not loaded: {e}; {fallback_error}")

try:
    from app.dashboard_state_router import router as dashboard_state_router  # type: ignore
    app.include_router(dashboard_state_router)
except Exception as e:
    try:
        from .dashboard_state_router import router as dashboard_state_router  # type: ignore
        app.include_router(dashboard_state_router)
    except Exception as fallback_error:
        print(f"[WARN] DashboardState router not loaded: {e}; {fallback_error}")

# Optional other routers (defensive)
for mod_path, attr in [
    ("app.api.router", "router"),
    ("app.router", "router"),
    ("app.routes.router", "router"),
]:
    try:
        m = __import__(mod_path, fromlist=[attr])
        r = getattr(m, attr)
        app.include_router(r)
    except Exception:
        pass


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
