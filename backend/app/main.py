from __future__ import annotations
from backend.app.headless_guarded_entry import run_headless

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

@app.post("/engine/headless/run")
def engine_headless_run():
    """
    Triggers headless guarded entry in TEST mode.
    Returns execution result without killing server.
    """
    result = run_headless()
import os
from fastapi import Body

def _env_true(name: str) -> bool:
    v = os.getenv(name, "")
    return v.strip().lower() in ("1", "true", "yes", "y", "on")

HEADLESS_DEV_MODE = _env_true("HEADLESS_DEV_MODE")

@app.post("/dev/run_paper_smoketest")
def run_paper_smoketest(payload: dict = Body(default={})):
    """
    DEV ONLY. Requires HEADLESS_DEV_MODE=1.
    Runs a short paper/sim loop to validate engine wiring + risk gates without login.
    """
    if not HEADLESS_DEV_MODE:
        return {"ok": False, "detail": "dev endpoint disabled (set HEADLESS_DEV_MODE=1)"}

    # Optional knobs
    steps = int(payload.get("steps", 50))
    symbol = str(payload.get("symbol", "EURUSD")).upper()

    # Import here to avoid import-time side effects
    from backend.app.simulator import run_simulation_smoke  # adapt if name differs

    result = run_simulation_smoke(steps=steps, symbol=symbol)
    return {"ok": True, "result": result}

    return {"headless_result": result}

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
