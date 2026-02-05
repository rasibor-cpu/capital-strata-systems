from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict

from fastapi import FastAPI
from fastapi.responses import FileResponse, RedirectResponse, JSONResponse

# Existing imports (keep yours if present)
# If your file already imports auth router elsewhere, keep it.
try:
    from backend.app.auth.auth_router import router as auth_router
    AUTH_OK = True
    AUTH_ERR = None
except Exception as e:
    auth_router = None
    AUTH_OK = False
    AUTH_ERR = repr(e)

app = FastAPI(title="REA Capital – Trading Engine")

# -----------------------------
# UI file locations
# -----------------------------
REPO_ROOT = Path(__file__).resolve().parents[2]  # ...\REA-capital-trading-engine
UI_DIR = REPO_ROOT / "ui"

LOGIN_HTML = UI_DIR / "login.html"
MENU_HTML = UI_DIR / "menu.html"


# -----------------------------
# API routes
# -----------------------------
@app.get("/health")
def health() -> Dict[str, Any]:
    return {"status": "ok", "auth_loaded": bool(AUTH_OK), "auth_error": AUTH_ERR}


@app.get("/routes")
def routes() -> Dict[str, Any]:
    paths = sorted([r.path for r in app.routes if hasattr(r, "path")])
    return {"auth_loaded": bool(AUTH_OK), "auth_error": AUTH_ERR, "paths": paths}


if auth_router is not None:
    app.include_router(auth_router)


# -----------------------------
# UI routes (seamless navigation)
# -----------------------------
@app.get("/")
def root():
    return RedirectResponse(url="/login")


@app.get("/login")
def login_page():
    if not LOGIN_HTML.exists():
        return JSONResponse(status_code=404, content={"detail": f"Missing UI file: {LOGIN_HTML}"})
    return FileResponse(str(LOGIN_HTML))


@app.get("/menu")
def menu_page():
    if not MENU_HTML.exists():
        return JSONResponse(status_code=404, content={"detail": f"Missing UI file: {MENU_HTML}"})
    return FileResponse(str(MENU_HTML))
