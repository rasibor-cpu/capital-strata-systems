"""
engine/engine_loop.py

Canonical Institutional Engine Loop v8.5 (Phase 1.3 Validation Wiring)
- Correct SignalEngine signature:
    generate(instrument, price_now, price_prev, moving_avg)
- Correct PnLTracker contract (this repo):
    PnLTracker(starting_equity=...)
    record_trade(instrument, realized_pnl, unrealized_pnl=0.0, timestamp=...)
    current_drawdown()
    equity_snapshot()
    attributes: current_equity, starting_equity, max_drawdown

NOTE (validation-only):
- Uses a one-bar realized PnL approximation for replay sweeps:
    pnl = (price_now - price_prev) * direction_sign * PIP_SCALE
  This enables threshold sensitivity comparisons without relying on a
  full position lifecycle implementation.
"""

from __future__ import annotations

import os
from typing import Dict, Any, Deque, Optional
from datetime import datetime
from collections import deque

from engine.execution.execution_gate import ExecutionGate
from engine.strategy.behaviour_mapper import get_profile_for_behaviour
from engine.strategy.signal_engine import SignalEngine

# IMPORTANT: your repo's PnLTracker is under engine.performance.* (confirmed)
from engine.performance.pnl_tracker import PnLTracker


# ============================================================
# CONFIG
# ============================================================

DEFAULT_MIN_SIGNAL_STRENGTH = 0.61
MA_WINDOW = 20

# Convert FX price deltas into "pips-like" units for readability in validation.
# Example: GBPUSD move of 0.00010 ~ 1 pip => scale 10000
try:
    PIP_SCALE = float(os.getenv("CSS_PIP_SCALE", "10000"))
except ValueError:
    PIP_SCALE = 10000.0

try:
    MIN_SIGNAL_STRENGTH = float(os.getenv("CSS_MIN_SIGNAL_STRENGTH", DEFAULT_MIN_SIGNAL_STRENGTH))
except ValueError:
    MIN_SIGNAL_STRENGTH = DEFAULT_MIN_SIGNAL_STRENGTH


# ============================================================
# ENGINE LOOP
# ============================================================

class EngineLoop:
    def __init__(self, behaviour: str = "D", starting_equity: float = 1000.0):
        self.profile = get_profile_for_behaviour(behaviour)
        self.signal_engine = SignalEngine(self.profile)

        self.execution_gate = ExecutionGate()
        self.pnl_tracker = PnLTracker(starting_equity=float(starting_equity))

        self.trade_count = 0
        self.behaviour = behaviour
        self.starting_equity = float(starting_equity)

        self.prev_price: Optional[float] = None
        self.price_window: Deque[float] = deque(maxlen=MA_WINDOW)

    def _moving_average(self) -> Optional[float]:
        if not self.price_window:
            return None
        return sum(self.price_window) / len(self.price_window)

    def process_bar(self, instrument: str, price: float) -> None:
        # Update MA window
        self.price_window.append(price)

        if self.prev_price is None:
            self.prev_price = price
            return

        moving_avg = self._moving_average()
        if moving_avg is None:
            self.prev_price = price
            return

        # ✅ Correct signal signature (confirmed):
        # generate(instrument, price_now, price_prev, moving_avg)
        signal = self.signal_engine.generate(instrument, price, self.prev_price, moving_avg)

        # Gate: ignore flats + weak signals
        if signal.direction == "FLAT" or signal.strength < MIN_SIGNAL_STRENGTH:
            self.prev_price = price
            return

        # Gate approval (governance)
        decision = self.execution_gate.evaluate(
            instrument=instrument,
            direction=signal.direction,
            price=price,
            strength=signal.strength,
        )
        if not getattr(decision, "ok", False):
            self.prev_price = price
            return

        # ------------------------------------------------------------
        # Phase 1.3 validation PnL approximation (one-bar realized pnl)
        # ------------------------------------------------------------
        direction_sign = 1.0 if signal.direction == "BUY" else -1.0
        delta = (price - self.prev_price)
        realized_pnl = delta * direction_sign * PIP_SCALE

        # ✅ Correct PnLTracker API (confirmed):
        self.pnl_tracker.record_trade(
            instrument=instrument,
            realized_pnl=float(realized_pnl),
            unrealized_pnl=0.0,
            timestamp=datetime.utcnow(),
        )

        self.trade_count += 1
        self.prev_price = price

    def summary(self) -> Dict[str, Any]:
        # Net PnL = current_equity - starting_equity (repo semantics)
        net_pnl = float(self.pnl_tracker.current_equity - self.pnl_tracker.starting_equity)

        # max_drawdown is an attribute in your implementation
        max_dd = float(getattr(self.pnl_tracker, "max_drawdown", 0.0))

        # current_drawdown is a method (present in your method list)
        try:
            cur_dd = float(self.pnl_tracker.current_drawdown())
        except Exception:
            cur_dd = 0.0

        return {
            "bars_ma_window": MA_WINDOW,
            "pip_scale": PIP_SCALE,
            "min_signal_strength": MIN_SIGNAL_STRENGTH,
            "behaviour": self.behaviour,

            "trades": self.trade_count,
            "starting_equity": float(self.pnl_tracker.starting_equity),
            "ending_equity": float(self.pnl_tracker.current_equity),
            "net_pnl": net_pnl,
            "max_drawdown": max_dd,
            "current_drawdown": cur_dd,
        }