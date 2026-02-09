"""
Headless Guarded Entry – REA Capital Trading Engine
--------------------------------------------------

IMPORTANT:
- main.py imports: run_headless, HeadlessConfig
- This file MUST export both names.

Design:
- Dev-safe: if any guard import fails, return structured error instead of crashing.
- Execution order:
  1) Daily Trade Guard
  2) Loss Streak Guard
  3) Concurrency Guard
  4) Equity Drawdown Guard (if available)
  5) Execution Lock

Safe default: missing/invalid inputs => BLOCK.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Optional


# -------------------------
# Config expected by main.py
# -------------------------

@dataclass(frozen=True)
class HeadlessConfig:
    max_trades_per_day: int = 15
    max_consecutive_losses: int = 5
    cooldown_seconds: int = 3600
    max_concurrent_positions: int = 20
    engine_locked: bool = True  # no live trades until explicitly unlocked


# -------------------------
# Helpers
# -------------------------

def _ts() -> str:
    return datetime.now(timezone.utc).isoformat()

def _safe_int(x: Any, default: int = 0) -> int:
    try:
        return int(x)
    except Exception:
        return default


# -------------------------
# Main entrypoint
# -------------------------

def run_headless(
    steps: int,
    symbol: str,
    execution_mode: str = "SIMULATION",
    current_open_positions: int = 0,
    trades_today: int = 0,
    consecutive_losses: int = 0,
    # equity snapshot (optional)
    current_equity: float = 100000.0,
    peak_equity: float = 100000.0,
    requested_trade_risk: float = 0.0,
    config: Optional[HeadlessConfig] = None,
) -> Dict[str, Any]:

    cfg = config or HeadlessConfig()

    steps_i = max(1, _safe_int(steps, 1))
    symbol_s = str(symbol or "EURUSD")
    exec_mode = str(execution_mode or "SIMULATION")
    open_pos = max(0, _safe_int(current_open_positions, 0))
    trades_today_i = max(0, _safe_int(trades_today, 0))
    losses_i = max(0, _safe_int(consecutive_losses, 0))

    # ---- Import guards safely (dev-safe) ----
    try:
        from backend.app.risk.daily_trade_guard import evaluate_daily_trade_guard
    except Exception as e:
        return {
            "ok": False,
            "error_type": "ImportError",
            "error": f"Failed to import daily_trade_guard: {e}",
            "timestamp_utc": _ts(),
        }

    try:
        from backend.app.risk.loss_streak_guard import evaluate_loss_streak
    except Exception as e:
        return {
            "ok": False,
            "error_type": "ImportError",
            "error": f"Failed to import loss_streak_guard: {e}",
            "timestamp_utc": _ts(),
        }

    try:
        from backend.app.risk.concurrency_guard import evaluate_concurrency
    except Exception as e:
        return {
            "ok": False,
            "error_type": "ImportError",
            "error": f"Failed to import concurrency_guard: {e}",
            "timestamp_utc": _ts(),
        }

    # Equity guard is optional (won’t crash engine if not present yet)
    equity_guard_available = True
    try:
        from backend.app.risk.equity_drawdown_guard import evaluate_equity_risk, EquitySnapshot
    except Exception:
        equity_guard_available = False
        evaluate_equity_risk = None  # type: ignore
        EquitySnapshot = None  # type: ignore

    # ---- Evaluate guards ----
    daily_result = evaluate_daily_trade_guard(
        trades_today=trades_today_i,
        max_trades=cfg.max_trades_per_day,
    )

    loss_result = evaluate_loss_streak(
        consecutive_losses=losses_i,
        max_consecutive_losses=cfg.max_consecutive_losses,
        cooldown_seconds=cfg.cooldown_seconds,
    )

    concurrency_result = evaluate_concurrency(
        open_positions=open_pos,
        max_positions=cfg.max_concurrent_positions,
    )

    equity_result: Dict[str, Any] = {"available": False}
    if equity_guard_available and evaluate_equity_risk and EquitySnapshot:
        equity_result = evaluate_equity_risk(
            EquitySnapshot(
                current_equity=float(current_equity),
                peak_equity=float(peak_equity),
                requested_trade_risk=float(requested_trade_risk),
            )
        )
        equity_result["available"] = True

    # ---- Run loop with breakdown ----
    blocked_breakdown = {
        "daily_trade_guard_blocked": 0,
        "loss_streak_guard_blocked": 0,
        "concurrency_guard_blocked": 0,
        "equity_guard_blocked": 0,
        "locked_execution_blocked": 0,
        "other_blocked": 0,
    }

    simulated_trades = 0
    blocked_trades = 0

    for _ in range(steps_i):
        if not bool(daily_result.get("allowed", False)):
            blocked_trades += 1
            blocked_breakdown["daily_trade_guard_blocked"] += 1
            continue

        if str(loss_result.get("decision", "BLOCK")) != "ALLOW":
            blocked_trades += 1
            blocked_breakdown["loss_streak_guard_blocked"] += 1
            continue

        if not bool(concurrency_result.get("allowed", False)):
            blocked_trades += 1
            blocked_breakdown["concurrency_guard_blocked"] += 1
            continue

        if equity_guard_available and str(equity_result.get("decision", "ALLOW")) == "BLOCK":
            blocked_trades += 1
            blocked_breakdown["equity_guard_blocked"] += 1
            continue

        if cfg.engine_locked:
            blocked_trades += 1
            blocked_breakdown["locked_execution_blocked"] += 1
            continue

        simulated_trades += 1

    blocked_reason = "Execution layer locked (no live trades)." if cfg.engine_locked else None

    return {
        "ok": True,
        "mode": exec_mode,
        "live_execution": (not cfg.engine_locked),
        "locked": cfg.engine_locked,
        "steps_requested": steps_i,
        "symbol": symbol_s,
        "simulated_trades": simulated_trades,
        "blocked_trades": blocked_trades,
        "blocked_breakdown": blocked_breakdown,
        "daily_trade_guard": daily_result,
        "loss_streak_guard": loss_result,
        "concurrency_guard": concurrency_result,
        "equity_guard": equity_result,
        "trade_preview": {
            "symbol": symbol_s,
            "side": "buy",
            "units": 1,
            "order_type": "MARKET",
        },
        "blocked_reason": blocked_reason,
        "timestamp_utc": _ts(),
    }
