"""
engine/engine_loop.py

Canonical Institutional Engine Loop v12
- Diagnostic counters retained
- SignalEngine wired
- ExecutionGate.evaluate_trade signature aligned to repo

Gate signature (from inspect):
(self, *, instrument: str, side: str, notional: float, stop_distance_pct: float,
 equity: float, equity_peak: float, regime_persistence: float, policy='core', ... ) -> Dict[str, Any]
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

# Replay PnL scaling helper
try:
    PIP_SCALE = float(os.getenv("CSS_PIP_SCALE", "10000"))
except ValueError:
    PIP_SCALE = 10000.0

try:
    MIN_SIGNAL_STRENGTH = float(os.getenv("CSS_MIN_SIGNAL_STRENGTH", DEFAULT_MIN_SIGNAL_STRENGTH))
except ValueError:
    MIN_SIGNAL_STRENGTH = DEFAULT_MIN_SIGNAL_STRENGTH

# Gate inputs (safe defaults for replay)
# Notional: 1 unit (paper)
try:
    GATE_NOTIONAL = float(os.getenv("CSS_GATE_NOTIONAL", "1.0"))
except ValueError:
    GATE_NOTIONAL = 1.0

# Stop distance percent: default 0.20% (0.002) unless overridden
try:
    GATE_STOP_DISTANCE_PCT = float(os.getenv("CSS_GATE_STOP_PCT", "0.002"))
except ValueError:
    GATE_STOP_DISTANCE_PCT = 0.002

# Regime persistence: neutral 0.50 unless overridden
try:
    GATE_REGIME_PERSISTENCE = float(os.getenv("CSS_GATE_REGIME_PERSISTENCE", "0.50"))
except ValueError:
    GATE_REGIME_PERSISTENCE = 0.50


# ============================================================
# ENGINE LOOP
# ============================================================

class EngineLoop:
    def __init__(self, behaviour: str = "D", starting_equity: float = 1000.0):
        self.profile = get_profile_for_behaviour(behaviour)
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

    def _gate_ok(self, decision: Any) -> bool:
        """
        ExecutionGate returns Dict[str, Any] in this repo.
        We accept common allow keys defensively.
        """
        if isinstance(decision, dict):
            if "ok" in decision:
                return bool(decision["ok"])
            if "allow" in decision:
                return bool(decision["allow"])
            if "approved" in decision:
                return bool(decision["approved"])
            if "pass" in decision:
                return bool(decision["pass"])
        # fallback: if it returns True/False directly
        if isinstance(decision, bool):
            return decision
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

        # Signal flat
        if signal.direction == "FLAT":
            self.regime_flat_blocks += 1
            self.prev_price = float(price)
            return

        # Strength filter
        if float(signal.strength) < float(MIN_SIGNAL_STRENGTH):
            self.threshold_blocks += 1
            self.prev_price = float(price)
            return

        # Gate expects side + equity context
        decision = self.execution_gate.evaluate_trade(
            instrument=instrument,
            side=str(signal.direction),
            notional=float(GATE_NOTIONAL),
            stop_distance_pct=float(GATE_STOP_DISTANCE_PCT),
            equity=float(self.pnl_tracker.current_equity),
            equity_peak=float(self.pnl_tracker.peak_equity),
            regime_persistence=float(GATE_REGIME_PERSISTENCE),
            policy=os.getenv("CSS_GATE_POLICY", "core"),
            current_allocations=None,
            rebalance_target_weights=None,
            volatility_state="MEDIUM",
            regime_state="NORMAL",
        )

        if not self._gate_ok(decision):
            self.gate_blocks += 1
            self.prev_price = float(price)
            return

        # Replay-safe PnL approximation (no broker)
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