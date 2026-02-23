"""
engine/engine_loop.py

Replay/Simulation Engine Loop (Institutional-Safe)
--------------------------------------------------

Fixes:
- Threshold now instance-bound (no import-time locking)
- Risk-consistent replay sizing (R-multiple based)
- Signature-aware ExecutionGate invocation
- Governance-compatible equity + peak feeding
"""

from __future__ import annotations

from collections import deque
from datetime import datetime
from typing import Any, Dict, Optional, Deque
import inspect
import os

from engine.execution.execution_gate import ExecutionGate
from engine.performance.pnl_tracker import PnLTracker
from engine.strategy.behaviour_mapper import get_profile_for_behaviour
from engine.strategy.signal_engine import SignalEngine


MA_WINDOW = 20
PIP_SCALE = 10000.0


def _env_float(name: str, default: float) -> float:
    v = os.getenv(name, "")
    if not v:
        return default
    try:
        return float(v)
    except Exception:
        return default


DEFAULT_STOP_DISTANCE_PCT = _env_float("CSS_STOP_DISTANCE_PCT", 0.01)
DEFAULT_REGIME_PERSISTENCE = _env_float("CSS_GATE_REGIME_PERSISTENCE", 0.95)
MAX_R_PER_BAR = _env_float("CSS_MAX_R_PER_BAR", 3.0)


class EngineLoop:
    def __init__(self, behaviour: str = "D", starting_equity: float = 1000.0):
        self.profile = get_profile_for_behaviour(behaviour)
        self.signal_engine = SignalEngine(self.profile)

        self.execution_gate = ExecutionGate()
        self.pnl_tracker = PnLTracker(starting_equity=float(starting_equity))

        self.behaviour = behaviour
        self.prev_price: Optional[float] = None
        self.price_window: Deque[float] = deque(maxlen=MA_WINDOW)

        # Threshold now instance-bound
        self.min_signal_strength = _env_float("CSS_MIN_SIGNAL_STRENGTH", 0.61)

        # Equity tracking for governance
        self.equity_peak: float = float(starting_equity)

        # Diagnostics
        self.total_signals = 0
        self.regime_flat_blocks = 0
        self.threshold_blocks = 0
        self.gate_blocks = 0
        self.trade_count = 0

    # ----------------------------------------------------
    # Helpers
    # ----------------------------------------------------

    def _moving_average(self) -> Optional[float]:
        if not self.price_window:
            return None
        return sum(self.price_window) / len(self.price_window)

    def _gate_ok(self, decision: Any) -> bool:
        if not isinstance(decision, dict):
            return False

        if decision.get("ok") is True:
            return True

        if decision.get("final", "").upper() == "ALLOW":
            return True

        inner = decision.get("decision")
        if isinstance(inner, dict):
            if inner.get("ok") is True:
                return True
            if inner.get("final", "").upper() == "ALLOW":
                return True

        gov = decision.get("governor_response")
        if isinstance(gov, dict):
            if gov.get("ok") is True:
                return True
            if str(gov.get("status", "")).upper() in ("APPROVED", "ALLOW", "OK"):
                return True

        return False

    def _gate_reason(self, decision: Any) -> str:
        if not isinstance(decision, dict):
            return "non_dict_decision"
        if "reason" in decision:
            return str(decision["reason"])
        inner = decision.get("decision")
        if isinstance(inner, dict) and "reason" in inner:
            return str(inner["reason"])
        return "unknown"

    def _extract_risk_pct(self, decision: Any, fallback: float = 0.01) -> float:
        try:
            if isinstance(decision, dict):
                dbg = decision.get("debug")
                if isinstance(dbg, dict) and dbg.get("risk_pct") is not None:
                    return float(dbg["risk_pct"])

                inner = decision.get("decision")
                if isinstance(inner, dict):
                    dbg2 = inner.get("debug")
                    if isinstance(dbg2, dict) and dbg2.get("risk_pct") is not None:
                        return float(dbg2["risk_pct"])
        except Exception:
            pass
        return float(fallback)

    def _call_execution_gate(self, **kwargs: Any) -> Any:
        fn = getattr(self.execution_gate, "evaluate_trade", None)
        if fn is None:
            return {"ok": False, "reason": "missing_evaluate_trade"}

        try:
            sig = inspect.signature(fn)
            allowed = set(sig.parameters.keys())
        except Exception:
            return {"ok": False, "reason": "gate_signature_error"}

        equity = float(self.pnl_tracker.current_equity)
        self.equity_peak = max(self.equity_peak, equity)

        candidate = dict(kwargs)
        candidate.setdefault("equity", equity)
        candidate.setdefault("equity_peak", self.equity_peak)
        candidate.setdefault("regime_persistence", DEFAULT_REGIME_PERSISTENCE)
        candidate.setdefault("stop_distance_pct", DEFAULT_STOP_DISTANCE_PCT)
        candidate.setdefault("notional", equity)

        filtered = {k: v for k, v in candidate.items() if k in allowed}

        return fn(**filtered)

    # ----------------------------------------------------
    # Main Loop
    # ----------------------------------------------------

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

        if float(signal.strength) < float(self.min_signal_strength):
            self.threshold_blocks += 1
            self.prev_price = float(price)
            return

        decision = self._call_execution_gate(
            instrument=instrument,
            side=signal.direction,
            rebalance_target_weights=None,
            signal_strength=float(signal.strength),
            strategy_style=getattr(signal, "style", "NONE"),
            timestamp=datetime.utcnow().isoformat(),
        )

        if not self._gate_ok(decision):
            self.gate_blocks += 1
            print("GATE BLOCK:", {"reason": self._gate_reason(decision)})
            self.prev_price = float(price)
            return

        direction_sign = 1.0 if signal.direction == "BUY" else -1.0

        equity = float(self.pnl_tracker.current_equity)
        self.equity_peak = max(self.equity_peak, equity)

        risk_pct = self._extract_risk_pct(decision, fallback=0.01)
        stop_distance_pct = float(DEFAULT_STOP_DISTANCE_PCT)

        if stop_distance_pct <= 0.0 or float(price) <= 0.0:
            self.prev_price = float(price)
            return

        move_ratio = (float(price) - float(self.prev_price)) / (float(price) * stop_distance_pct)

        if move_ratio > MAX_R_PER_BAR:
            move_ratio = MAX_R_PER_BAR
        elif move_ratio < -MAX_R_PER_BAR:
            move_ratio = -MAX_R_PER_BAR

        risk_amount = equity * float(risk_pct)
        realized_pnl = float(move_ratio) * float(risk_amount) * float(direction_sign)

        self.pnl_tracker.record_trade(
            instrument=instrument,
            realized_pnl=float(realized_pnl),
            unrealized_pnl=0.0,
            timestamp=datetime.utcnow(),
        )

        self.trade_count += 1
        self.prev_price = float(price)

    # ----------------------------------------------------
    # Summary
    # ----------------------------------------------------

    def summary(self) -> Dict[str, Any]:
        net_pnl = self.pnl_tracker.current_equity - self.pnl_tracker.starting_equity
        return {
            "bars_ma_window": MA_WINDOW,
            "pip_scale": PIP_SCALE,
            "min_signal_strength": self.min_signal_strength,
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