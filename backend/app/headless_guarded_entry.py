"""
Headless Guarded Entry – REA Capital Trading Engine

Goal:
- Provide a stable "headless run" API that NEVER returns {}.
- Fail-closed by default.
- Return structured JSON that your PowerShell can show clearly.

Notes:
- This does NOT require login (HEADLESS_DEV_MODE supported).
- Live execution remains locked unless explicitly enabled elsewhere.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Dict, Optional
from datetime import datetime, timezone

# Guards
from backend.app.risk.loss_streak_guard import LossStreakGuard

# If you have a daily trade guard module, we try to import it.
# But we fail-safe if it doesn't exist or is broken.
try:
    from backend.app.risk.daily_trade_guard import DailyTradeGuard  # type: ignore
except Exception:
    DailyTradeGuard = None  # type: ignore


UTC = timezone.utc


@dataclass
class HeadlessResult:
    ok: bool
    mode: str
    live_execution: bool
    locked: bool
    steps_requested: int
    symbol: str
    simulated_trades: int
    blocked_trades: int
    blocked_breakdown: Dict[str, Any]
    daily_trade_guard: Dict[str, Any]
    loss_streak_guard: Dict[str, Any]
    trade_preview: Dict[str, Any]
    blocked_reason: Optional[str] = None
    warning: Optional[str] = None
    timestamp_utc: str = ""


def _utc_now_iso() -> str:
    return datetime.now(tz=UTC).isoformat()


def _safe_status(obj: Any) -> Dict[str, Any]:
    try:
        if obj is None:
            return {"enabled": False}
        if hasattr(obj, "status") and callable(getattr(obj, "status")):
            s = obj.status()
            return s if isinstance(s, dict) else {"value": s}
        return {"enabled": True, "note": "No status() method."}
    except Exception as e:
        return {"enabled": True, "error": f"{type(e).__name__}: {e}"}


def _safe_call(fn, default: Any) -> Any:
    try:
        return fn()
    except Exception as e:
        return default, f"{type(e).__name__}: {e}"


def run_headless(
    steps: int,
    symbol: str,
    execution_mode: str = "SIMULATION",
    **_ignored: Any,
) -> Dict[str, Any]:
    """
    Primary entrypoint called by backend.app.main engine_headless_run.

    IMPORTANT:
    - Always returns a dict with keys. Never {}.
    - execution_mode is accepted but SIMULATION is the only safe mode here unless unlocked elsewhere.
    """
    mode = str(execution_mode or "SIMULATION").upper().strip()

    # Safety defaults
    live_execution = False
    locked = True  # Execution layer locked in headless by default

    # Normalize inputs
    try:
        steps_i = int(steps)
    except Exception:
        steps_i = 1
    steps_i = max(1, min(steps_i, 5000))

    sym = (symbol or "EUR_USD").strip()

    # Instantiate guards (in-memory for now)
    # Loss streak policy: 5 losses -> 1 hour cooldown (per Robert)
    loss_guard = LossStreakGuard(max_losses=5, cooldown_hours=1.0)

    # Daily trade guard is optional; if missing, we return a disabled status.
    daily_guard = None
    if DailyTradeGuard is not None:
        try:
            daily_guard = DailyTradeGuard(max_trades=15)  # you asked max/day 15 earlier
        except Exception:
            daily_guard = None

    # Simulate "steps" events: we just create a deterministic pattern for smoke testing.
    # You can replace this later with real signal loop / broker adapter calls.
    simulated_trades = 0
    blocked_trades = 0
    breakdown: Dict[str, Any] = {
        "daily_trade_guard_blocked": 0,
        "loss_streak_guard_blocked": 0,
        "locked_execution_blocked": 0,
        "other_blocked": 0,
    }

    # Trade preview (what we WOULD do if unlocked)
    trade_preview = {"symbol": sym, "side": "buy", "units": 1, "order_type": "MARKET"}

    blocked_reason: Optional[str] = None

    for i in range(steps_i):
        # 1) Execution locked => we can preview but not execute live
        if locked:
            blocked_trades += 1
            breakdown["locked_execution_blocked"] += 1
            blocked_reason = "Execution layer locked (no live trades)."
            continue

        # 2) Daily trade guard (if enabled)
        if daily_guard is not None:
            try:
                d = daily_guard.should_block()  # expected dict with decision
                if isinstance(d, dict) and d.get("decision") == "BLOCK":
                    blocked_trades += 1
                    breakdown["daily_trade_guard_blocked"] += 1
                    blocked_reason = d.get("reason", "Daily trade limit reached.")
                    continue
            except Exception:
                # fail-safe: block
                blocked_trades += 1
                breakdown["daily_trade_guard_blocked"] += 1
                blocked_reason = "Daily trade guard error (fail-safe block)."
                continue

        # 3) Loss streak guard
        lg = loss_guard.should_block()
        if lg.get("decision") == "BLOCK":
            blocked_trades += 1
            breakdown["loss_streak_guard_blocked"] += 1
            blocked_reason = lg.get("reason", "Loss streak cooldown active.")
            continue

        # If allowed, count as simulated trade
        simulated_trades += 1

        # Deterministic fake outcome: every 6th trade is a loss to exercise the guard.
        if (simulated_trades % 6) == 0:
            loss_guard.record_loss()
        else:
            loss_guard.record_win()

    result = HeadlessResult(
        ok=True,
        mode=mode,
        live_execution=live_execution,
        locked=locked,
        steps_requested=steps_i,
        symbol=sym,
        simulated_trades=simulated_trades,
        blocked_trades=blocked_trades,
        blocked_breakdown=breakdown,
        daily_trade_guard=_safe_status(daily_guard),
        loss_streak_guard=_safe_status(loss_guard),
        trade_preview=trade_preview,
        blocked_reason=blocked_reason,
        warning=None,
        timestamp_utc=_utc_now_iso(),
    )

    out = asdict(result)

    # Hard guarantee: never return {} even if something unexpected happens
    if not out:
        return {
            "ok": False,
            "mode": mode,
            "locked": True,
            "error": "HeadlessResult serialization returned empty dict (fail-safe).",
            "timestamp_utc": _utc_now_iso(),
        }

    return out
