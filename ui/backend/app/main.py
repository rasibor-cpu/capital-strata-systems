"""
Main FastAPI app – REA Capital Trading Engine

This file:
- Creates FastAPI app (or reuses existing factory if present)
- Registers auth router (Phase 1 login screen support)
- Stays defensive to avoid breaking existing modules/routers
"""

from __future__ import annotations

from fastapi import FastAPI

# --- create app ---
app = FastAPI(title="REA Capital – Trading Engine", version="phase-1")

# --- auth router (Phase 1) ---
try:
    from app.auth.auth_router import router as auth_router  # type: ignore
    app.include_router(auth_router)
except Exception as e:
    # Fail-closed would be too aggressive at import-time; keep API up but no auth endpoints.
    # You will see this clearly during smoke test.
    print(f"[WARN] Auth router not loaded: {e}")

# --- OPTIONAL: include other routers if your repo has them ---
# If you already include routers elsewhere, this won't interfere.
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
