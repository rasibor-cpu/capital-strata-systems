"""
engine/engine_loop.py

Canonical Institutional Engine Loop v8
Signal-driven + Multi-bar hold model
Threshold configurable via environment variable

Enhancement:
- MIN_SIGNAL_STRENGTH defaults to 0.61
- Override via env var CSS_MIN_SIGNAL_STRENGTH
"""

from __future__ import annotations

import os
import uuid
from typing import Dict, Any, List
from datetime import datetime, timezone

from engine.execution.execution_gate import ExecutionGate
from engine.execution.execution_cost_engine import ExecutionCostEngine
from engine.performance.pnl_tracker import PnLTracker
from engine.core.position_book import PositionBook
from engine.strategy.behaviour_mapper import get_profile_for_behaviour
from engine.strategy.signal_engine import SignalEngine


# ============================================================
# CONFIGURATION
# ============================================================

DEFAULT_MIN_SIGNAL_STRENGTH = 0.61

try:
    MIN_SIGNAL_STRENGTH = float(
        os.getenv("CSS_MIN_SIGNAL_STRENGTH", DEFAULT_MIN_SIGNAL_STRENGTH)
    )
except ValueError:
    MIN_SIGNAL_STRENGTH = DEFAULT_MIN_SIGNAL_STRENGTH


# ============================================================
# ENGINE LOOP
# ============================================================

class EngineLoop:

    def __init__(self, behaviour: str = "BALANCED"):

        self.profile = get_profile_for_behaviour(behaviour)
        self.signal_engine = SignalEngine(self.profile)
        self.execution_gate = ExecutionGate()
        self.cost_engine = ExecutionCostEngine()
        self.position_book = PositionBook()
        self.pnl_tracker = PnLTracker()

        self.trade_count = 0

    # ----------------------------------------------------------
    # PROCESS BAR
    # ----------------------------------------------------------

    def process_bar(self, instrument: str, price: float) -> None:

        # 1. Generate signal
        signal = self.signal_engine.generate(instrument, price)

        if signal.direction == "FLAT":
            return

        if signal.strength < MIN_SIGNAL_STRENGTH:
            return

        # 2. Gate approval
        decision = self.execution_gate.evaluate(
            instrument=instrument,
            direction=signal.direction,
            price=price,
            strength=signal.strength,
        )

        if not decision.ok:
            return

        # 3. Execute simulated trade
        trade_id = str(uuid.uuid4())
        execution_price = self.cost_engine.apply_costs(
            instrument, price, signal.direction
        )

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
    # SUMMARY
    # ----------------------------------------------------------

    def summary(self) -> Dict[str, Any]:

        return {
            "trades": self.trade_count,
            "net_pnl": self.pnl_tracker.total_pnl(),
            "max_drawdown": self.pnl_tracker.max_drawdown(),
            "min_signal_strength": MIN_SIGNAL_STRENGTH,
        }