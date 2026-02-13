"""
backend/app/main.py

Phase 1 (Headless) API for REA Capital Trading Engine.

Goals:
- Keep /health stable even if auth router is absent (expected in Phase 1 headless).
- Provide /engine/headless/run with robust compatibility against evolving run_headless() signatures.
- Fail-closed: default execution remains locked unless the underlying engine explicitly allows otherwise.
"""

from __future__ import annotations

import inspect
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple

from fastapi import FastAPI
from pydantic import BaseModel, Field

# -------------------------------------------------------------------
# App
# -------------------------------------------------------------------

app = FastAPI(title="REA Capital Trading Engine (Phase 1 Headless)")


# -------------------------------------------------------------------
# Models
# -------------------------------------------------------------------

class HeadlessRunRequest(BaseModel):
    steps: int = Field(default=5, ge=1, le=500)
    symbol: str = Field(default="EURUSD", min_length=1)
    execution_mode: str = Field(default="SIMULATION")  # SIMULATION | PAPER | LIVE (engine decides)
    current_open_positions: int = Field(default=0, ge=0)
    trades_today: int = Field(default=0, ge=0)
    consecutive_losses: int = Field(default=0, ge=0)

    # Optional equity inputs (helps drawdown guard + cap scaler)
    current_equity: float = Field(default=100000.0, ge=0)
    peak_equity: float = Field(default=100000.0, ge=0)


# -------------------------------------------------------------------
# Helpers
# -------------------------------------------------------------------

def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _filter_kwargs_for_callable(callable_obj: Any, desired: Dict[str, Any]) -> Dict[str, Any]:
    """
    Return only kwargs that the callable accepts.
    """
    try:
        sig = inspect.signature(callable_obj)
        accepted = set(sig.parameters.keys())
        return {k: v for k, v in desired.items() if k in accepted}
    except Exception:
        return {}


def _build_headless_config() -> Tuple[Optional[Any], Optional[str]]:
    """
    Build HeadlessConfig using only parameters it supports (avoids 'unexpected keyword' errors).
    """
    try:
        from backend.app.headless_guarded_entry import HeadlessConfig  # type: ignore
    except Exception as e:
        return None, f"HeadlessConfig import failed: {e!r}"

    desired = {
        # Risk governor defaults (Phase 1 targets)
        "max_trades_per_day": 15,
        "max_positions": 20,
        "max_consecutive_losses": 5,
        "cooldown_seconds": 3600,

        # Fail-closed execution locks (different builds used different names)
        "execution_locked": True,
        "locked": True,
        "lock_execution": True,
        "live_execution": False,
    }

    kwargs = _filter_kwargs_for_callable(HeadlessConfig, desired)
    try:
        return HeadlessConfig(**kwargs), None
    except Exception as e:
        return None, f"HeadlessConfig init failed: {e!r}"


def _normalize_engine_output(out: Any) -> Dict[str, Any]:
    if isinstance(out, dict):
        return out
    if hasattr(out, "model_dump"):
        return out.model_dump()
    if hasattr(out, "__dict__"):
        return dict(out.__dict__)
    return {"ok": True, "result": str(out)}


def _call_run_headless(run_headless: Any, cfg: Any, req: HeadlessRunRequest) -> Dict[str, Any]:
    """
    Compatibility wrapper.

    IMPORTANT: Prefer dict-based calling conventions to avoid passing
    individual fields (like steps=...) to engines that don't accept them.

    Order:
    1) run_headless(req=<dict>, cfg=<cfg>)
    2) run_headless(<dict>, <cfg>)
    3) run_headless(<dict>)
    4) If signature clearly wants field kwargs, pass ONLY accepted kwargs
    """
    attempts = []
    last_err: Optional[Exception] = None

    payload = req.model_dump()

    # Signature sniff (best-effort)
    try:
        sig = inspect.signature(run_headless)
        params = list(sig.parameters.keys())
        param_set = set(params)
    except Exception:
        params = []
        param_set = set()

    def _try(label: str, fn_call):
        nonlocal last_err
        try:
            out = fn_call()
            return _normalize_engine_output(out)
        except TypeError as e:
            last_err = e
            attempts.append(f"{label}: TypeError: {e}")
            return None
        except Exception as e:
            last_err = e
            attempts.append(f"{label}: Exception: {e!r}")
            return None

    # 1) Keyword style: run_headless(req=..., cfg=...)
    if {"req", "cfg"}.issubset(param_set):
        r = _try("kw(req,cfg)", lambda: run_headless(req=payload, cfg=cfg))
        if r is not None:
            return r

    # 2) Keyword style variants
    if {"request", "config"}.issubset(param_set):
        r = _try("kw(request,config)", lambda: run_headless(request=payload, config=cfg))
        if r is not None:
            return r

    # 3) Positional dict-first conventions (most common)
    r = _try("pos(payload,cfg)", lambda: run_headless(payload, cfg))
    if r is not None:
        return r

    r = _try("pos(payload)", lambda: run_headless(payload))
    if r is not None:
        return r

    # 4) Only if engine clearly wants field kwargs (NO req dict param)
    #    Pass ONLY accepted kwargs to avoid "unexpected keyword 'steps'"
    if "req" not in param_set:
        filtered = _filter_kwargs_for_callable(run_headless, payload)
        if filtered:
            r = _try("kw(filtered_fields)", lambda: run_headless(**filtered))
            if r is not None:
                return r

    # Fail-closed with diagnostics
    return {
        "ok": False,
        "timestamp_utc": _utc_now_iso(),
        "error": f"TypeError: run_headless signature mismatch. Last error: {last_err}",
        "attempts": attempts,
        "detected_params": params,
    }


# -------------------------------------------------------------------
# Routes
# -------------------------------------------------------------------

@app.get("/health")
def health() -> Dict[str, Any]:
    # Auth router may not exist in Phase 1 headless mode (expected).
    auth_loaded = False
    auth_error: Optional[str] = None
    try:
        import backend.app.auth.router  # type: ignore
        auth_loaded = True
    except Exception:
        auth_loaded = False
        auth_error = "Auth router not loaded in Phase 1 headless mode (expected)."

    headless_loaded = False
    headless_error: Optional[str] = None
    try:
        from backend.app.headless_guarded_entry import run_headless  # type: ignore
        headless_loaded = callable(run_headless)
    except Exception as e:
        headless_loaded = False
        headless_error = f"{e.__class__.__name__}: {e}"

    return {
        "status": "ok",
        "time_utc": _utc_now_iso(),
        "auth_loaded": auth_loaded,
        "auth_error": auth_error,
        "headless_loaded": headless_loaded,
        "headless_error": headless_error,
    }


@app.post("/engine/headless/run")
def engine_headless_run(req: HeadlessRunRequest) -> Dict[str, Any]:
    try:
        from backend.app.headless_guarded_entry import run_headless  # type: ignore
    except Exception as e:
        return {
            "ok": False,
            "timestamp_utc": _utc_now_iso(),
            "error": f"ImportError: {e}",
        }

    cfg, cfg_err = _build_headless_config()
    if cfg is None:
        return {
            "ok": False,
            "timestamp_utc": _utc_now_iso(),
            "error": cfg_err or "HeadlessConfig build failed",
        }

    result = _call_run_headless(run_headless, cfg, req)

    if isinstance(result, dict):
        result.setdefault("timestamp_utc", _utc_now_iso())
    return result
