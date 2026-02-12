"""
backend/app/main.py

Phase 1 – Deterministic Headless API
REA Capital Trading Engine

Strict adapter to:

    run_headless(
        steps,
        symbol,
        execution_mode,
        current_open_positions,
        trades_today,
        consecutive_losses,
        current_equity,
        peak_equity,
        cfg
    )

Fail-closed by design.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple

from fastapi import FastAPI
from pydantic import BaseModel, Field


# -----------------------------------------------------------
# App
# -----------------------------------------------------------

app = FastAPI(title="REA Capital Trading Engine – Phase 1 Headless")


# -----------------------------------------------------------
# Utilities
# -----------------------------------------------------------

def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# -----------------------------------------------------------
# Request Model
# -----------------------------------------------------------

class HeadlessRunRequest(BaseModel):
    steps: int = Field(default=5, ge=1, le=500)
    symbol: str = Field(default="EURUSD", min_length=1)
    execution_mode: str = Field(default="SIMULATION")

    current_open_positions: int = Field(default=0, ge=0)
    trades_today: int = Field(default=0, ge=0)
    consecutive_losses: int = Field(default=0, ge=0)

    current_equity: Optional[float] = None
    peak_equity: Optional[float] = None


# -----------------------------------------------------------
# Config Builder (Fail-Closed)
# -----------------------------------------------------------

def _build_headless_config() -> Tuple[Optional[Any], Optional[str]]:
    try:
        from backend.app.headless_guarded_entry import HeadlessConfig
    except Exception as e:
        return None, f"HeadlessConfig import failed: {e}"

    try:
        cfg = HeadlessConfig(
            max_trades_per_day=15,
            max_positions=20,
            max_consecutive_losses=5,
            cooldown_seconds=3600,
            execution_locked=True
        )
        return cfg, None
    except Exception as e:
        return None, f"HeadlessConfig init failed: {e}"


# -----------------------------------------------------------
# Routes
# -----------------------------------------------------------

@app.get("/health")
def health() -> Dict[str, Any]:
    try:
        from backend.app.headless_guarded_entry import run_headless
        loaded = callable(run_headless)
        error = None
    except Exception as e:
        loaded = False
        error = f"{type(e).__name__}: {e}"

    return {
        "status": "ok",
        "time_utc": _utc_now_iso(),
        "headless_loaded": loaded,
        "headless_error": error,
    }


@app.post("/engine/headless/run")
def engine_headless_run(req: HeadlessRunRequest) -> Dict[str, Any]:

    # Import engine
    try:
        from backend.app.headless_guarded_entry import run_headless
    except Exception as e:
        return {
            "ok": False,
            "timestamp_utc": _utc_now_iso(),
            "error": f"ImportError: {e}",
        }

    # Build config
    cfg, cfg_err = _build_headless_config()
    if cfg is None:
        return {
            "ok": False,
            "timestamp_utc": _utc_now_iso(),
            "error": cfg_err,
        }

    # Call engine deterministically
    try:
        result = run_headless(
            steps=req.steps,
            symbol=req.symbol,
            execution_mode=req.execution_mode,
            current_open_positions=req.current_open_positions,
            trades_today=req.trades_today,
            consecutive_losses=req.consecutive_losses,
            current_equity=req.current_equity,
            peak_equity=req.peak_equity,
            cfg=cfg,
        )

        if isinstance(result, dict):
            result.setdefault("ok", True)
            result.setdefault("timestamp_utc", _utc_now_iso())
            return result

        return {
            "ok": True,
            "timestamp_utc": _utc_now_iso(),
            "result": str(result),
        }

    except Exception as e:
        return {
            "ok": False,
            "timestamp_utc": _utc_now_iso(),
            "error": f"{type(e).__name__}: {e}",
        }
