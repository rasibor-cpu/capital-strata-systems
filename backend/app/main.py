from __future__ import annotations

import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse

app = FastAPI(title="REA Capital – Trading Engine", version="phase-1")

# CORS for local dev (still fine)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # local dev only
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Auth router ---
AUTH_LOADED = False
AUTH_ERROR = None
try:
    from backend.app.auth.auth_router import router as auth_router  # type: ignore
    app.include_router(auth_router)
    AUTH_LOADED = True
except Exception as e:
    AUTH_ERROR = repr(e)

@app.get("/health")
def health() -> dict:
    return {"status": "ok", "auth_loaded": AUTH_LOADED, "auth_error": AUTH_ERROR}

@app.get("/routes")
def routes() -> dict:
    return {
        "auth_loaded": AUTH_LOADED,
        "auth_error": AUTH_ERROR,
        "paths": sorted({getattr(r, "path", "") for r in app.router.routes}),
    }

@app.get("/login", response_class=HTMLResponse)
def login_page() -> str:
    # Serve UI over HTTP to avoid file:// fetch issues
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    ui_path = os.path.join(repo_root, "ui", "login.html")
    try:
        with open(ui_path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        return f"<h3>UI file not found</h3><pre>{ui_path}\n{e}</pre>"
