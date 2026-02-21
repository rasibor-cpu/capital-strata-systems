"""
engine/engine_loop.py

Canonical Institutional Engine Loop v8.2
- Supports SignalEngine.generate(instrument, price_prev, moving_avg)
- Adds rolling MA state
- Passes starting_equity to PnLTracker
"""

from __future__ import annotations

import os
import uuid
from typing import Dict, Any, Deque
from datetime import datetime, timezone
from collections import deque

from engine.execution.execution_gate import ExecutionGate
from engine.execution.execution_cost_engine import ExecutionCostEngine
from engine.performance.pnl_tracker import PnLTracker
from engine.core.position_book import PositionBook
from engine.strategy.behaviour_mapper import get_profile_for_behaviour
from engine.strategy.signal_engine import SignalEngine


# ============================================================
# CONFIG
# ============================================================

DEFAULT_MIN_SIGNAL_STRENGTH = 0.61

try:
    MIN_SIGNAL_STRENGTH = float(
        os.getenv("CSS_MIN_SIGNAL_STRENGTH", DEFAULT_MIN_SIGNAL_STRENGTH)
    )
except ValueError:
    MIN_SIGNAL_STRENGTH = DEFAULT_MIN_SIGNAL_STRENGTH


MA_WINDOW = 20  # simple rolling average window


# ============================================================
# ENGINE LOOP
# ============================================================

class EngineLoop:
    def __init__(self, behaviour: str = "D", starting_equity: float = 1000.0):
        self.profile = get_profile_for_behaviour(behaviour)
        self.signal_engine = SignalEngine(self.profile)

        self.execution_gate = ExecutionGate()
        self.cost_engine = ExecutionCostEngine()
        self.position_book = PositionBook()

        self.pnl_tracker = PnLTracker(starting_equity=starting_equity)

        self.trade_count = 0
        self.behaviour = behaviour
        self.starting_equity = starting_equity

        # --- NEW: price state ---
        self.prev_price: float | None = None
        self.price_window: Deque[float] = deque(maxlen=MA_WINDOW)

    # ----------------------------------------------------------
    def _moving_average(self) -> float | None:
        if not self.price_window:
            return None
        return sum(self.price_window) / len(self.price_window)

    # ----------------------------------------------------------
    def process_bar(self, instrument: str, price: float) -> None:
        # update MA window
        self.price_window.append(price)

        if self.prev_price is None:
            self.prev_price = price
            return  # need at least one previous price

        moving_avg = self._moving_average()
        if moving_avg is None:
            self.prev_price = price
            return

        # FIX: call correct signal signature
        signal = self.signal_engine.generate(
            instrument,
            self.prev_price,
            moving_avg
        )

        self.prev_price = price

        if signal.direction == "FLAT":
            return

        if signal.strength < MIN_SIGNAL_STRENGTH:
            return

        decision = self.execution_gate.evaluate(
            instrument=instrument,
            direction=signal.direction,
            price=price,
            strength=signal.strength,
        )
        if not decision.ok:
            return

        trade_id = str(uuid.uuid4())
        execution_price = self.cost_engine.apply_costs(instrument, price, signal.direction)

        pnl = self.position_book.open_position(
            trade_id,
            instrument,
            signal.direction,
            execution_price,
        )

        self.pnl_tracker.record_trade(
            trade_id=trade_id,
            instrument=instrument,
            pnl=pnl,
            timestamp=datetime.now(timezone.utc),
        )

        self.trade_count += 1

    # ----------------------------------------------------------
    def summary(self) -> Dict[str, Any]:
        return {
            "trades": self.trade_count,
            "net_pnl": self.pnl_tracker.total_pnl(),
            "max_drawdown": self.pnl_tracker.max_drawdown(),
            "min_signal_strength": MIN_SIGNAL_STRENGTH,
            "behaviour": self.behaviour,
            "starting_equity": self.starting_equity,
        }