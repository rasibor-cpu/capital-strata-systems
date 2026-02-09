"""
Headless Guarded Entry – REA Capital Trading Engine
---------------------------------------------------

Responsibilities:
- Provide a dev-safe headless execution loop
- Evaluate risk guards (daily trades, loss streak, concurrency)
- Return structured results (never {})

IMPORTANT:
- This file is allowed to be conservative. Any import/eval failure => BLOCK.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Optional


@dataclass(frozen=True)
class HeadlessConfig:
    # guard thresholds
    max_trades_per_day: int = 15
    max_consecutive_losses: int = 5
    cooldown_seconds: int = 3600
    max_concurrent_positions: int = 20

    # fail-close execution layer (no real trades)
    execution_locked: bool = True


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_imports() -> Dict[str, Any]:
    """
    Import guard evaluators in a way that never crashes the server.
    Returns dict of callables or None.
    """
    out: Dict[str, Any] = {
        "evaluate_daily_trade_guard": None,
        "evaluate_loss_streak": None,
        "evaluate_concurrency_guard": None,
    }

    # Daily trade guard
    try:
        from backend.app.risk.daily_trade_guard import evaluate_daily_trade_guard  # type: ignore
        out["evaluate_daily_trade_guard"] = evaluate_daily_trade_guard
    except Exception:
        out["evaluate_daily_trade_guard"] = None

    # Loss streak guard
    try:
        from backend.app.risk.loss_streak_guard import evaluate_loss_streak  # type: ignore
        out["evaluate_loss_streak"] = evaluate_loss_streak
    except Exception:
        out["evaluate_loss_streak"] = None

    # Concurrency guard
    try:
        from backend.app.risk.concurrency_guard import evaluate_concurrency_guard  # type: ignore
        out["evaluate_concurrency_guard"] = evaluate_concurrency_guard
    except Exception:
        out["evaluate_concurrency_guard"] = None

    return out


def run_headless(
    *,
    steps: int,
    symbol: str,
    cfg: HeadlessConfig,
    # optional “current state” inputs for guards (caller can supply)
    current_open_positions: int = 0,
    trades_today: int = 0,
    consecutive_losses: int = 0,
) -> Dict[str, Any]:
    """
    Run a headless simulation “loop”.
    For now, this is a risk/guard harness (execution is locked by default).
    """
    # sanitize
    steps = int(steps or 0)
    steps = max(0, steps)
    symbol = str(symbol or "").strip() or "EURUSD"

    imports = _safe_imports()

    blocked_breakdown = {
        "daily_trade_guard_blocked": 0,
        "loss_streak_guard_blocked": 0,
        "concurrency_guard_blocked": 0,
        "locked_execution_blocked": 0,
        "other_blocked": 0,
    }

    daily_trade_guard: Dict[str, Any]
    loss_streak_guard: Dict[str, Any]
    concurrency_guard: Dict[str, Any]

    # -------------------------
    # DAILY TRADE GUARD
    # -------------------------
    if imports["evaluate_daily_trade_guard"] is None:
        daily_trade_guard = {
            "decision": "BLOCK",
            "reason": "daily_trade_guard import/eval failed (fail-closed).",
            "current_day": datetime.now(timezone.utc).date().isoformat(),
            "trades_today": int(trades_today),
            "max_trades": int(cfg.max_trades_per_day),
            "remaining": 0,
            "allowed": False,
        }
        blocked_breakdown["daily_trade_guard_blocked"] += steps
    else:
        try:
            daily_trade_guard = imports["evaluate_daily_trade_guard"](
                trades_today=trades_today,
                max_trades=cfg.max_trades_per_day,
            )
        except Exception as e:
            daily_trade_guard = {
                "decision": "BLOCK",
                "reason": f"daily_trade_guard import/eval failed (fail-closed): {type(e).__name__}: {e}",
                "current_day": datetime.now(timezone.utc).date().isoformat(),
                "trades_today": int(trades_today),
                "max_trades": int(cfg.max_trades_per_day),
                "remaining": 0,
                "allowed": False,
            }
            blocked_breakdown["daily_trade_guard_blocked"] += steps

    # -------------------------
    # LOSS STREAK GUARD
    # -------------------------
    if imports["evaluate_loss_streak"] is None:
        loss_streak_guard = {
            "decision": "BLOCK",
            "reason": "loss_streak_guard import/eval failed (fail-closed).",
            "consecutive_losses": int(consecutive_losses),
            "max_consecutive_losses": int(cfg.max_consecutive_losses),
            "cooldown_seconds": int(cfg.cooldown_seconds),
            "cooldown_remaining_seconds": int(cfg.cooldown_seconds),
            "allowed": False,
        }
        blocked_breakdown["loss_streak_guard_blocked"] += steps
    else:
        try:
            loss_streak_guard = imports["evaluate_loss_streak"](
                consecutive_losses=consecutive_losses,
                max_consecutive_losses=cfg.max_consecutive_losses,
                cooldown_seconds=cfg.cooldown_seconds,
            )
        except Exception as e:
            loss_streak_guard = {
                "decision": "BLOCK",
                "reason": f"loss_streak_guard import/eval failed (fail-closed): {type(e).__name__}: {e}",
                "consecutive_losses": int(consecutive_losses),
                "max_consecutive_losses": int(cfg.max_consecutive_losses),
                "cooldown_seconds": int(cfg.cooldown_seconds),
                "cooldown_remaining_seconds": int(cfg.cooldown_seconds),
                "allowed": False,
            }
            blocked_breakdown["loss_streak_guard_blocked"] += steps

    # -------------------------
    # CONCURRENCY GUARD
    # -------------------------
    if imports["evaluate_concurrency_guard"] is None:
        concurrency_guard = {
            "decision": "BLOCK",
            "reason": "concurrency_guard import/eval failed (fail-closed).",
            "open_positions": int(current_open_positions),
            "max_positions": int(cfg.max_concurrent_positions),
            "remaining": 0,
            "allowed": False,
            "timestamp_utc": _utc_now_iso(),
        }
        blocked_breakdown["concurrency_guard_blocked"] += steps
    else:
        try:
            from backend.app.risk.concurrency_guard import ConcurrencyPolicy  # type: ignore

            concurrency_guard = imports["evaluate_concurrency_guard"](
                current_open_positions=current_open_positions,
                policy=ConcurrencyPolicy(max_positions=cfg.max_concurrent_positions),
            )
            concurrency_guard["timestamp_utc"] = _utc_now_iso()
        except Exception as e:
            concurrency_guard = {
                "decision": "BLOCK",
                "reason": f"concurrency_guard import/eval failed (fail-closed): {type(e).__name__}: {e}",
                "open_positions": int(current_open_positions),
                "max_positions": int(cfg.max_concurrent_positions),
                "remaining": 0,
                "allowed": False,
                "timestamp_utc": _utc_now_iso(),
            }
            blocked_breakdown["concurrency_guard_blocked"] += steps

    # -------------------------
    # EXECUTION LAYER LOCK
    # -------------------------
    locked = bool(cfg.execution_locked)
    if locked:
        blocked_breakdown["locked_execution_blocked"] += steps

    # For now, "simulated trades" are those that would pass all guards AND if unlocked.
    guards_allow = (
        daily_trade_guard.get("allowed") is True
        and loss_streak_guard.get("decision") in ("ALLOW",)  # some versions use decision only
        and concurrency_guard.get("allowed") is True
    )

    simulated_trades = 0
    blocked_trades = steps

    if steps == 0:
        blocked_trades = 0

    # If locked, we do not “execute” — but we still report what guards would do.
    if not locked and guards_allow:
        simulated_trades = steps
        blocked_trades = 0

    # Provide a useful preview
    trade_preview = {
        "symbol": symbol,
        "side": "buy",
        "units": 1,
        "order_type": "MARKET",
    }

    blocked_reason_parts = []
    if locked:
        blocked_reason_parts.append("Execution layer locked (no live trades).")
    if daily_trade_guard.get("allowed") is False:
        blocked_reason_parts.append(str(daily_trade_guard.get("reason", "daily_trade_guard blocked")))
    if loss_streak_guard.get("decision") != "ALLOW":
        # some implementations block by decision or explicit allowed flag
        if loss_streak_guard.get("allowed") is False or loss_streak_guard.get("decision") == "BLOCK":
            blocked_reason_parts.append(str(loss_streak_guard.get("reason", "loss_streak_guard blocked")))
    if concurrency_guard.get("allowed") is False:
        blocked_reason_parts.append(str(concurrency_guard.get("reason", "concurrency_guard blocked")))

    blocked_reason = " | ".join([p for p in blocked_reason_parts if p]) if blocked_reason_parts else ""

    return {
        "mode": "SIMULATION",
        "live_execution": False,
        "locked": locked,
        "steps_requested": steps,
        "symbol": symbol,
        "simulated_trades": simulated_trades,
        "blocked_trades": blocked_trades,
        "blocked_breakdown": blocked_breakdown,
        "daily_trade_guard": daily_trade_guard,
        "loss_streak_guard": loss_streak_guard,
        "concurrency_guard": concurrency_guard,
        "trade_preview": trade_preview,
        "blocked_reason": blocked_reason,
        "timestamp_utc": _utc_now_iso(),
    }
