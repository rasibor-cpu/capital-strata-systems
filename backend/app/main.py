from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

auth_loaded = False
auth_error = None

app = FastAPI(title="REA Capital Trading Engine")

# CORS: UI is loaded via file:// (Origin: null), so allow all for local dev
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Try-load auth router (fail-closed but server still boots)
try:
    from backend.app.auth.auth_router import router as auth_router
    app.include_router(auth_router)
    auth_loaded = True
except Exception as e:
    auth_loaded = False
    auth_error = f"{type(e).__name__}: {e}"

# ----------------------------
# Health + route introspection
# ----------------------------
@app.get("/health")
def health():
    return {"status": "ok", "auth_loaded": auth_loaded, "auth_error": auth_error}


@app.get("/routes")
def routes():
    paths = []
    for r in app.routes:
        try:
            paths.append(getattr(r, "path", str(r)))
        except Exception:
            pass
    paths = sorted(set(paths))
    return {"paths": paths, "auth_loaded": auth_loaded, "auth_error": auth_error}
