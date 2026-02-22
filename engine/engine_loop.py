"""
engine/engine_loop.py

EngineLoop v13
- Clean indentation
- ExecutionGate aligned
- Debug print for rejection reason (temporary)
"""

from __future__ import annotations

import os
from typing import Dict, Any, Deque, Optional
from datetime import datetime
from collections import deque

from engine.execution.execution_gate import ExecutionGate
from engine.strategy.behaviour_mapper import get_profile_for_behaviour
from engine.strategy.signal_engine import SignalEngine
from engine.performance.pnl_tracker import PnLTracker


DEFAULT_MIN_SIGNAL_STRENGTH = 0.61
MA_WINDOW = 20

PIP_SCALE = float(os.getenv("CSS_PIP_SCALE", "10000"))
MIN_SIGNAL_STRENGTH = float(os.getenv("CSS_MIN_SIGNAL_STRENGTH", DEFAULT_MIN_SIGNAL_STRENGTH))

GATE_NOTIONAL = float(os.getenv("CSS_GATE_NOTIONAL", "1.0"))
GATE_STOP_DISTANCE_PCT = float(os.getenv("CSS_GATE_STOP_PCT", "0.002"))
GATE_REGIME_PERSISTENCE = float(os.getenv("CSS_GATE_REGIME_PERSISTENCE", "0.50"))
GATE_POLICY = os.getenv("CSS_GATE_POLICY", "core")


class EngineLoop:

    def __init__(self, behaviour: str = "D", starting_equity: float = 1000.0):
        self.profile = get_profile_for_behaviour(behaviour)
        self.signal_engine = SignalEngine(self.profile, behaviour_name="BALANCED")

        self.execution_gate = ExecutionGate()
        self.pnl_tracker = PnLTracker(starting_equity=float(starting_equity))

        self.behaviour = behaviour
        self.prev_price: Optional[float] = None
        self.price_window: Deque[float] = deque(maxlen=MA_WINDOW)

        # Diagnostics
        self.total_signals = 0
        self.regime_flat_blocks = 0
        self.threshold_blocks = 0
        self.gate_blocks = 0
        self.trade_count = 0

    def _moving_average(self) -> Optional[float]:
        if not self.price_window:
            return None
        return sum(self.price_window) / len(self.price_window)

    def _gate_ok(self, decision: Any) -> bool:
        if isinstance(decision, dict):
            return bool(decision.get("ok", False))
        return False

    def process_bar(self, instrument: str, price: float) -> None:

        self.price_window.append(float(price))

        if self.prev_price is None:
            self.prev_price = float(price)
            return

        moving_avg = self._moving_average()
        if moving_avg is None:
            self.prev_price = float(price)
            return

        signal = self.signal_engine.generate(
            instrument=instrument,
            price_now=float(price),
            price_prev=float(self.prev_price),
            moving_avg=float(moving_avg),
        )

        self.total_signals += 1

        if signal.direction == "FLAT":
            self.regime_flat_blocks += 1
            self.prev_price = float(price)
            return

        if float(signal.strength) < MIN_SIGNAL_STRENGTH:
            self.threshold_blocks += 1
            self.prev_price = float(price)
            return

        decision = self.execution_gate.evaluate_trade(
            instrument=instrument,
            side=str(signal.direction),
            notional=GATE_NOTIONAL,
            stop_distance_pct=GATE_STOP_DISTANCE_PCT,
            equity=float(self.pnl_tracker.current_equity),
            equity_peak=float(self.pnl_tracker.peak_equity),
            regime_persistence=GATE_REGIME_PERSISTENCE,
            policy=GATE_POLICY,
            current_allocations=None,
            rebalance_target_weights=None,
            volatility_state="MEDIUM",
            regime_state="NORMAL",
        )

        if not self._gate_ok(decision):
            self.gate_blocks += 1
            print("GATE REJECT:", decision)
            self.prev_price = float(price)
            return

        direction_sign = 1.0 if signal.direction == "BUY" else -1.0
        delta = float(price) - float(self.prev_price)
        realized_pnl = delta * direction_sign * PIP_SCALE

        self.pnl_tracker.record_trade(
            instrument=instrument,
            realized_pnl=float(realized_pnl),
            unrealized_pnl=0.0,
            timestamp=datetime.utcnow(),
        )

        self.trade_count += 1
        self.prev_price = float(price)

    def summary(self) -> Dict[str, Any]:
        net_pnl = self.pnl_tracker.current_equity - self.pnl_tracker.starting_equity

        return {
            "bars_ma_window": MA_WINDOW,
            "pip_scale": PIP_SCALE,
            "min_signal_strength": MIN_SIGNAL_STRENGTH,
            "behaviour": self.behaviour,
            "total_signals": self.total_signals,
            "regime_flat_blocks": self.regime_flat_blocks,
            "threshold_blocks": self.threshold_blocks,
            "gate_blocks": self.gate_blocks,
            "trades": self.trade_count,
            "starting_equity": self.pnl_tracker.starting_equity,
            "ending_equity": self.pnl_tracker.current_equity,
            "net_pnl": net_pnl,
        }