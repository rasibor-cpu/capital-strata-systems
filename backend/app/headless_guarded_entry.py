# backend/app/headless_guarded_entry.py
from __future__ import annotations

import os
import random
from dataclasses import dataclass
from typing import Any, Dict, Optional

from backend.app.risk.daily_trade_guard import DailyTradeGuard
from backend.app.risk.loss_streak_guard import LossStreakGuard

from backend.app.brokers.base import OrderRequest, OrderResult
from backend.app.brokers.oanda_adapter import OandaAdapter


@dataclass(frozen=True)
class HeadlessRunRequest:
    steps: int
    symbol: str


def _bool_env(name: str, default: str = "0") -> bool:
    return os.getenv(name, default).strip().lower() in ("1", "true", "yes", "y")


def _pick_adapter() -> Optional[Any]:
    # For now: OANDA only (practice). Easy to extend later.
    adapter = OandaAdapter()
    return adapter if adapter.is_configured() else None


def run_headless(*, steps: int, symbol: str) -> Dict[str, Any]:
    """
    Headless guarded runner.

    Modes:
    - HEADLESS_DEV: simulation only (safe)
    - PAPER: if broker env configured + explicit unlock flags
    """

    mode = "HEADLESS_DEV" if _bool_env("HEADLESS_DEV_MODE", "1") else "PAPER"
    # locked by default (fail-closed)
    execution_unlocked = _bool_env("EXECUTION_UNLOCKED", "0")
    dev_force_allow = _bool_env("DEV_FORCE_ALLOW", "0")

    locked = True
    if mode == "PAPER":
        # still require explicit unlocks
        locked = not (execution_unlocked and dev_force_allow)

    daily_guard = DailyTradeGuard(max_trades=10)
    loss_guard = LossStreakGuard(max_losses=5, cooldown_hours=1)  # 1 hour after 5 losses

    # NOTE: These guards are stateless across restarts for now.
    # Persistence is item (D), later.

    blocked_breakdown: Dict[str, int] = {"daily_guard": 0, "loss_streak": 0}
    simulated_trades = 0
    blocked_trades = 0
    paper_orders = 0
    paper_fails = 0

    adapter = _pick_adapter()

    for i in range(int(steps)):
        # 1) Daily limit gate
        dg = daily_guard.status()
        trades_today = int(dg.get("trades_today", 0))
        if trades_today >= daily_guard.max_trades:
            blocked_trades += 1
            blocked_breakdown["daily_guard"] += 1
            continue

        # 2) Loss streak gate
        lg = loss_guard.status()
        if bool(lg.get("cooldown_active", False)):
            blocked_trades += 1
            blocked_breakdown["loss_streak"] += 1
            continue

        # If locked, we simulate only
        if locked or mode == "HEADLESS_DEV" or adapter is None:
            # A proper outcomes simulator is item (A).
            # For now, minimal safe simulation: random outcomes with mild loss bias.
            simulated_trades += 1
            daily_guard.record_trade()

            # simulate win/loss (55% win, 45% loss default)
            is_loss = random.random() < float(os.getenv("SIM_LOSS_PROB", "0.45"))
            if is_loss:
                loss_guard.record_loss()
            else:
                loss_guard.record_win()
            continue

        # PAPER execution (practice) — still guarded and requires explicit unlock
        # Basic order sizing for smoke: 1 unit (we’ll enhance later)
        req = OrderRequest(symbol=symbol, side="buy", units=1, client_tag=f"REA_HEADLESS_{i}")
        result: OrderResult = adapter.place_order(req)
        paper_orders += 1
        daily_guard.record_trade()

        # Treat broker failure as a "loss" for risk brakes (conservative)
        if not result.ok:
            paper_fails += 1
            loss_guard.record_loss()
        else:
            loss_guard.record_win()  # placeholder until we read fills PnL

    return {
        "ok": True,
        "mode": mode,
        "locked": locked,
        "steps_requested": int(steps),
        "symbol": symbol,
        "simulated_trades": simulated_trades,
        "blocked_trades": blocked_trades,
        "blocked_breakdown": blocked_breakdown,
        "daily_trade_guard": daily_guard.status(),
        "loss_streak_guard": loss_guard.status(),
        "paper": {
            "configured": adapter is not None,
            "orders_sent": paper_orders,
            "order_failures": paper_fails,
            "unlock_flags": {
                "EXECUTION_UNLOCKED": execution_unlocked,
                "DEV_FORCE_ALLOW": dev_force_allow,
            },
        },
        "live_execution": (mode == "PAPER" and not locked and adapter is not None),
    }
