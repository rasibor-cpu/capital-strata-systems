"""
engine/engine_loop.py

Canonical Institutional Engine Loop v10 (Diagnostic + ExecutionGate API aligned)

Fix:
- ExecutionGate method name is evaluate_trade() in this repo (not evaluate()).

Still includes:
- suppression counters
- replay-safe PnL approximation
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


# ============================================================
# CONFIG
# ============================================================

DEFAULT_MIN_SIGNAL_STRENGTH = 0.61
MA_WINDOW = 20

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
        # SignalEngine accepts behaviour_name but we keep it stable for now
        self.signal_engine = SignalEngine(self.profile, behaviour_name="BALANCED")

        self.execution_gate = ExecutionGate()
        self.pnl_tracker = PnLTracker(starting_equity=float(starting_equity))

        self.behaviour = behaviour
        self.starting_equity = float(starting_equity)

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

        # Regime/signal flat
        if signal.direction == "FLAT":
            self.regime_flat_blocks += 1
            self.prev_price = float(price)
            return

        # Strength filter (env var / global)
        if float(signal.strength) < float(MIN_SIGNAL_STRENGTH):
            self.threshold_blocks += 1
            self.prev_price = float(price)
            return

        # Governance layer (repo API: evaluate_trade)
        decision = self.execution_gate.evaluate_trade(
            instrument=instrument,
            direction=signal.direction,
            price=float(price),
            strength=float(signal.strength),
        )

        if not getattr(decision, "ok", False):
            self.gate_blocks += 1
            self.prev_price = float(price)
            return

        # Replay-safe PnL approximation
        direction_sign = 1.0 if signal.direction == "BUY" else -1.0
        delta = float(price) - float(self.prev_price)
        realized_pnl = delta * direction_sign * float(PIP_SCALE)

        self.pnl_tracker.record_trade(
            instrument=instrument,
            realized_pnl=float(realized_pnl),
            unrealized_pnl=0.0,
            timestamp=datetime.utcnow(),
        )

        self.trade_count += 1
        self.prev_price = float(price)

    def summary(self) -> Dict[str, Any]:
        net_pnl = float(self.pnl_tracker.current_equity - self.pnl_tracker.starting_equity)

        try:
            cur_dd = float(self.pnl_tracker.current_drawdown())
        except Exception:
            cur_dd = 0.0

        return {
            "bars_ma_window": MA_WINDOW,
            "pip_scale": float(PIP_SCALE),
            "min_signal_strength": float(MIN_SIGNAL_STRENGTH),
            "behaviour": self.behaviour,

            "total_signals": int(self.total_signals),
            "regime_flat_blocks": int(self.regime_flat_blocks),
            "threshold_blocks": int(self.threshold_blocks),
            "gate_blocks": int(self.gate_blocks),

            "trades": int(self.trade_count),
            "starting_equity": float(self.pnl_tracker.starting_equity),
            "ending_equity": float(self.pnl_tracker.current_equity),
            "net_pnl": float(net_pnl),
            "current_drawdown": float(cur_dd),
        }