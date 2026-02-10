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


# -------------------------------------------------------------------
# Helpers (signature-safe)
# -------------------------------------------------------------------

def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _filter_kwargs_for_callable(callable_obj: Any, desired: Dict[str, Any]) -> Dict[str, Any]:
    """
    Return only kwargs that the callable (function or class __init__) accepts.
    """
    try:
        sig = inspect.signature(callable_obj)
        accepted = set(sig.parameters.keys())
        return {k: v for k, v in desired.items() if k in accepted}
    except Exception:
        # If signature cannot be inspected, fall back to nothing to avoid TypeError.
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
        # Risk governor defaults (your current Phase 1 targets)
        "max_trades_per_day": 15,
        "max_positions": 20,
        "max_consecutive_losses": 5,
        "cooldown_seconds": 3600,

        # Execution must remain fail-closed. Different builds used different names.
        # We pass only what HeadlessConfig actually supports (filtered below).
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


def _call_run_headless(run_headless: Any, cfg: Any, req: HeadlessRunRequest) -> Dict[str, Any]:
    """
    Compatibility wrapper: tries multiple known run_headless() calling conventions.
    Returns a structured dict, fail-closed on errors.
    """
    attempts = []
    last_err: Optional[Exception] = None

    # Prepare common payloads
    req_dict = req.model_dump()

    # Figure out param names (best-effort)
    try:
        sig = inspect.signature(run_headless)
        params = list(sig.parameters.keys())
        param_set = set(params)
    except Exception:
        params = []
        param_set = set()

    def _try(call_desc: str, fn_call):
        nonlocal last_err
        try:
            out = fn_call()
            # Normalize to dict for API response
            if isinstance(out, dict):
                return out
            # Dataclass / pydantic / object: try dict-ish
            if hasattr(out, "model_dump"):
                return out.model_dump()
            if hasattr(out, "__dict__"):
                return dict(out.__dict__)
            return {"ok": True, "result": str(out)}
        except TypeError as e:
            last_err = e
            attempts.append(f"{call_desc}: TypeError: {e}")
            return None
        except Exception as e:
            last_err = e
            attempts.append(f"{call_desc}: Exception: {e!r}")
            return None

    # 1) Keyword style: run_headless(req=..., cfg=...)
    if {"req", "cfg"}.issubset(param_set):
        r = _try("kw(req, cfg)", lambda: run_headless(req=req_dict, cfg=cfg))
        if r is not None:
            return r

    # 2) Keyword style: run_headless(request=..., config=...)
    if {"request", "config"}.issubset(param_set):
        r = _try("kw(request, config)", lambda: run_headless(request=req_dict, config=cfg))
        if r is not None:
            return r

    # 3) Positional common variants
    r = _try("pos(cfg, req)", lambda: run_headless(cfg, req_dict))
    if r is not None:
        return r

    r = _try("pos(req, cfg)", lambda: run_headless(req_dict, cfg))
    if r is not None:
        return r

    # 4) Legacy positional signature: run_headless(symbol, execution_mode, ...)
    # We only pass args it likely expects; extra args avoided by filtering kwargs.
    if len(params) >= 2 and ("symbol" in param_set or params[0] == "symbol") and (
        "execution_mode" in param_set or "mode" in param_set or params[1] in {"execution_mode", "mode"}
    ):
        # Prefer 'execution_mode' key over legacy 'mode'
        mode_key = "execution_mode" if "execution_mode" in param_set else ("mode" if "mode" in param_set else params[1])
        base_kwargs = {
            "steps": req.steps,
            "current_open_positions": req.current_open_positions,
            "trades_today": req.trades_today,
            "consecutive_losses": req.consecutive_losses,
            "cfg": cfg,
            "config": cfg,
        }
        filtered = _filter_kwargs_for_callable(run_headless, base_kwargs)
        r = _try(
            f"pos(symbol, {mode_key}) + filtered kwargs",
            lambda: run_headless(req.symbol, getattr(req, "execution_mode"), **filtered),
        )
        if r is not None:
            return r

    # If we got here: fail-closed with diagnostics
    return {
        "ok": False,
        "timestamp_utc": _utc_now_iso(),
        "error": f"TypeError: run_headless signature mismatch after attempts. Last error: {last_err}",
        "attempts": attempts,
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
        # If/when you add it later, this will flip to loaded=True.
        import backend.app.auth.router  # type: ignore
        auth_loaded = True
    except Exception:
        auth_loaded = False
        auth_error = "Auth router not loaded in Phase 1 headless mode (expected)."

    # Headless engine import check
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
    # Import run_headless
    try:
        from backend.app.headless_guarded_entry import run_headless  # type: ignore
    except Exception as e:
        return {
            "ok": False,
            "timestamp_utc": _utc_now_iso(),
            "error": f"ImportError: {e}",
        }

    # Build config safely
    cfg, cfg_err = _build_headless_config()
    if cfg is None:
        return {
            "ok": False,
            "timestamp_utc": _utc_now_iso(),
            "error": cfg_err or "HeadlessConfig build failed",
        }

    # Call engine (signature-safe)
    result = _call_run_headless(run_headless, cfg, req)

    # Ensure some top-level fields are always present for your console readability
    if isinstance(result, dict):
        result.setdefault("timestamp_utc", _utc_now_iso())
    return result
