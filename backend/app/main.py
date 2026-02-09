from __future__ import annotations

from fastapi import FastAPI
from pydantic import BaseModel
from typing import Optional, Dict, Any

from backend.app.headless_guarded_entry import run_headless, HeadlessConfig

app = FastAPI(title="REA Capital – Trading Engine")


class HeadlessRequest(BaseModel):
    steps: int = 5
    symbol: str = "EURUSD"
    execution_mode: str = "SIMULATION"  # reserved for future
    current_open_positions: int = 0
    trades_today: int = 0
    consecutive_losses: int = 0


@app.get("/health")
def health() -> Dict[str, Any]:
    # Keep health endpoint fail-safe. We DO NOT hard-import auth router here.
    return {
        "status": "ok",
        "time_utc": __import__("datetime").datetime.utcnow().isoformat() + "Z",
        "auth_loaded": False,
        "auth_error": "Auth router not loaded in Phase 1 headless mode (expected).",
    }


@app.post("/engine/headless/run")
def engine_headless_run(req: HeadlessRequest) -> Dict[str, Any]:
    # Phase 1: execution is locked (fail-closed). Headless is used for testing guards + wiring.
    cfg = HeadlessConfig(
        max_trades_per_day=15,
        max_consecutive_losses=5,
        cooldown_seconds=3600,
        max_concurrent_positions=20,
        execution_locked=True,  # <-- this MUST exist in HeadlessConfig now
    )

    result = run_headless(
        steps=req.steps,
        symbol=req.symbol,
        cfg=cfg,
        current_open_positions=req.current_open_positions,
        trades_today=req.trades_today,
        consecutive_losses=req.consecutive_losses,
    )

    return {
        "ok": True,
        "mode": "SIMULATION",
        "live_execution": False,
        **result,
    }
