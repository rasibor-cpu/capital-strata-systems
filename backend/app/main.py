from __future__ import annotations

import inspect
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

# We are in Phase 1 headless mode. Auth router may not exist yet.
AUTH_IMPORT_ERROR: Optional[str] = None
HEADLESS_IMPORT_ERROR: Optional[str] = None

try:
    from backend.app.headless_guarded_entry import run_headless, HeadlessConfig  # type: ignore
except Exception as e:  # pragma: no cover
    run_headless = None  # type: ignore
    HeadlessConfig = None  # type: ignore
    HEADLESS_IMPORT_ERROR = f"{type(e).__name__}: {e}"


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class HeadlessRunRequest(BaseModel):
    # Core
    steps: int = Field(5, ge=1, le=10_000)
    symbol: str = Field(..., min_length=1)
    execution_mode: str = Field(..., min_length=1)  # e.g. "SIMULATION"

    # Risk-state inputs (optional)
    current_open_positions: int = Field(0, ge=0)
    trades_today: int = Field(0, ge=0)
    consecutive_losses: int = Field(0, ge=0)

    # Optional: equity drawdown % (if/when you wire it)
    equity_drawdown_pct: Optional[float] = Field(None, ge=0.0)


def _safe_construct(cls: Any, proposed: Dict[str, Any]) -> Any:
    """
    Construct an object but only pass kwargs that exist in the target __init__ signature.
    This prevents breakages when HeadlessConfig fields change.
    """
    if cls is None:
        raise RuntimeError("HeadlessConfig is not available (import failed).")

    try:
        sig = inspect.signature(cls)
        allowed = set(sig.parameters.keys())
        filtered = {k: v for k, v in proposed.items() if k in allowed}
        return cls(**filtered)
    except TypeError:
        # Some classes (e.g. dataclasses) still show signature fine; this is a last resort.
        return cls()


def _call_run_headless(fn: Any, payload: Dict[str, Any], cfg: Any) -> Any:
    """
    Call run_headless using signature inspection to support different function shapes.
    """
    if fn is None:
        raise RuntimeError("run_headless is not available (import failed).")

    sig = inspect.signature(fn)
    params = list(sig.parameters.values())

    # Build candidate kwargs
    symbol = payload.get("symbol")
    execution_mode = payload.get("execution_mode")
    steps = payload.get("steps")
    current_open_positions = payload.get("current_open_positions")
    trades_today = payload.get("trades_today")
    consecutive_losses = payload.get("consecutive_losses")
    equity_drawdown_pct = payload.get("equity_drawdown_pct")

    candidate_kwargs: Dict[str, Any] = {}

    # Common names in our codebase
    name_map = {
        "symbol": symbol,
        "pair": symbol,
        "instrument": symbol,
        "execution_mode": execution_mode,
        "mode": execution_mode,
        "executionMode": execution_mode,
        "steps": steps,
        "steps_requested": steps,
        "n_steps": steps,
        "current_open_positions": current_open_positions,
        "open_positions": current_open_positions,
        "trades_today": trades_today,
        "consecutive_losses": consecutive_losses,
        "equity_drawdown_pct": equity_drawdown_pct,
        "drawdown_pct": equity_drawdown_pct,
        "cfg": cfg,
        "config": cfg,
    }

    for p in params:
        if p.kind in (p.VAR_POSITIONAL, p.VAR_KEYWORD):
            continue
        if p.name in name_map and name_map[p.name] is not None:
            candidate_kwargs[p.name] = name_map[p.name]

    # If function requires positional args for symbol/execution_mode, supply them.
    # We try the most likely ordering: (symbol, execution_mode, cfg, ...)
    # but we do it defensively based on parameter names.
    required = [
        p for p in params
        if p.default is inspect._empty
        and p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD)
    ]

    # Build positional list if needed
    positional: list[Any] = []
    used_names: set[str] = set()

    for p in required:
        if p.name in ("symbol", "pair", "instrument"):
            positional.append(symbol)
            used_names.add(p.name)
        elif p.name in ("execution_mode", "mode", "executionMode"):
            positional.append(execution_mode)
            used_names.add(p.name)
        elif p.name in ("cfg", "config"):
            positional.append(cfg)
            used_names.add(p.name)
        else:
            # Not sure what it needs; fall back to kwargs or raise cleanly
            if p.name in candidate_kwargs:
                used_names.add(p.name)
            else:
                raise TypeError(
                    f"run_headless requires '{p.name}' but it is not provided by payload/config."
                )

    # Remove any kwargs that we already satisfied positionally
    for n in list(candidate_kwargs.keys()):
        if n in used_names:
            candidate_kwargs.pop(n, None)

    return fn(*positional, **candidate_kwargs)


app = FastAPI(title="REA Capital Trading Engine – Phase 1 (Headless)")


@app.get("/health")
def health() -> Dict[str, Any]:
    return {
        "status": "ok",
        "time_utc": utc_now_iso(),
        "auth_loaded": False,
        "auth_error": "Auth router not loaded in Phase 1 headless mode (expected)."
        if AUTH_IMPORT_ERROR is None
        else AUTH_IMPORT_ERROR,
        "headless_loaded": HEADLESS_IMPORT_ERROR is None,
        "headless_error": HEADLESS_IMPORT_ERROR,
    }


@app.post("/engine/headless/run")
def engine_headless_run(req: HeadlessRunRequest):
    try:
        if run_headless is None or HeadlessConfig is None:
            return JSONResponse(
                status_code=500,
                content={
                    "ok": False,
                    "error": "Headless imports not available.",
                    "detail": HEADLESS_IMPORT_ERROR,
                    "timestamp_utc": utc_now_iso(),
                },
            )

        # Phase-1 defaults (safe, fail-closed)
        # NOTE: We only pass fields that exist in your current HeadlessConfig.
        proposed_cfg = {
            "max_trades_per_day": 15,
            "max_trades": 15,  # some variants may use this name
            "max_concurrent_positions": 20,
            "max_positions": 20,
            "max_consecutive_losses": 5,
            "cooldown_seconds": 3600,
            "execution_locked": True,
            "locked": True,
            "live_execution": False,
        }
        cfg = _safe_construct(HeadlessConfig, proposed_cfg)

        payload = req.model_dump()

        result = _call_run_headless(run_headless, payload, cfg)

        # Make sure result is JSON-serializable
        if isinstance(result, (dict, list, str, int, float, bool)) or result is None:
            out = result
        else:
            out = str(result)

        return {
            "ok": True,
            "timestamp_utc": utc_now_iso(),
            "result": out,
        }

    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={
                "ok": False,
                "error": f"{type(e).__name__}: {e}",
                "timestamp_utc": utc_now_iso(),
            },
        )
