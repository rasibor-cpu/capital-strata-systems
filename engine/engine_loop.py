"""
engine/engine_loop.py

Replay/Simulation Engine Loop (SAFE)
------------------------------------
Deterministic offline runner used by tools/run_replay_csv_threshold_sweep.py.

Compatibility upgrades:
1) Gate decision parsing accepts ALLOW shapes (not only {"ok": True}).
2) Gate call is signature-aware:
   - Avoids passing unsupported kwargs
   - Supplies required keyword-only governance fields when present:
       notional, stop_distance_pct, equity, equity_peak, regime_persistence

Replay assumptions (conservative, explicit):
- notional defaults to current equity (1x notional proxy)
- stop_distance_pct defaults to env CSS_STOP_DISTANCE_PCT else 0.01 (1%)
- regime_persistence defaults to env CSS_GATE_REGIME_PERSISTENCE else 0.95
- equity_peak tracked locally (max of equity through run)
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


MIN_SIGNAL_STRENGTH = _env_float("CSS_MIN_SIGNAL_STRENGTH", 0.61)
DEFAULT_STOP_DISTANCE_PCT = _env_float("CSS_STOP_DISTANCE_PCT", 0.01)
DEFAULT_REGIME_PERSISTENCE = _env_float("CSS_GATE_REGIME_PERSISTENCE", 0.95)


class EngineLoop:
    def __init__(self, behaviour: str = "D", starting_equity: float = 1000.0):
        self.profile = get_profile_for_behaviour(behaviour)
        self.signal_engine = SignalEngine(self.profile)

        self.execution_gate = ExecutionGate()
        self.pnl_tracker = PnLTracker(starting_equity=float(starting_equity))

        self.behaviour = behaviour
        self.prev_price: Optional[float] = None
        self.price_window: Deque[float] = deque(maxlen=MA_WINDOW)

        # Local equity peak tracker (some PnLTrackers may not expose peak)
        self.equity_peak: float = float(starting_equity)

        # Diagnostics
        self.total_signals = 0
        self.regime_flat_blocks = 0
        self.threshold_blocks = 0
        self.gate_blocks = 0
        self.trade_count = 0

    # ----------------------------
    # Helpers
    # ----------------------------

    def _moving_average(self) -> Optional[float]:
        if not self.price_window:
            return None
        return sum(self.price_window) / len(self.price_window)

    def _gate_ok(self, decision: Any) -> bool:
        """
        Accept multiple ExecutionGate decision shapes.

        True if:
          - {"ok": True}
          - {"final": "ALLOW"}
          - {"decision": {"final": "ALLOW"}}
          - {"governor_response": {"ok": True}} or status APPROVED
        """
        if not isinstance(decision, dict):
            return False

        if "ok" in decision:
            return bool(decision.get("ok", False))

        final = decision.get("final")
        if isinstance(final, str) and final.upper() == "ALLOW":
            return True

        inner = decision.get("decision")
        if isinstance(inner, dict):
            if "ok" in inner:
                return bool(inner.get("ok", False))
            inner_final = inner.get("final")
            if isinstance(inner_final, str) and inner_final.upper() == "ALLOW":
                return True

        gov = decision.get("governor_response")
        if isinstance(gov, dict):
            if "ok" in gov and bool(gov.get("ok", False)) is True:
                return True
            status = gov.get("status")
            if isinstance(status, str) and status.upper() in ("APPROVED", "ALLOW", "OK"):
                return True

        return False

    def _gate_reason(self, decision: Any) -> str:
        if not isinstance(decision, dict):
            return "non_dict_decision"
        if isinstance(decision.get("reason"), str):
            return decision["reason"]
        inner = decision.get("decision")
        if isinstance(inner, dict) and isinstance(inner.get("reason"), str):
            return inner["reason"]
        gov = decision.get("governor_response")
        if isinstance(gov, dict):
            if isinstance(gov.get("status"), str):
                return f"governor:{gov.get('status')}"
            if "ok" in gov:
                return f"governor_ok:{bool(gov.get('ok'))}"
        return "unknown"

    def _call_execution_gate(self, **kwargs: Any) -> Any:
        """
        Signature-aware gate call:
        - Pass only supported kwargs
        - Ensure required keyword-only params are provided when gate requires them
        """
        gate = self.execution_gate
        if not hasattr(gate, "evaluate_trade"):
            return {"ok": False, "reason": "missing_evaluate_trade"}

        fn = getattr(gate, "evaluate_trade")

        try:
            sig = inspect.signature(fn)
            params = sig.parameters
        except Exception:
            # If introspection fails, fail-closed conservatively
            return {"ok": False, "reason": "gate_signature_unavailable"}

        # Build a candidate argument dict with governance context
        equity = float(getattr(self.pnl_tracker, "current_equity", self.pnl_tracker.starting_equity))
        self.equity_peak = max(self.equity_peak, equity)

        candidate: Dict[str, Any] = dict(kwargs)

        # Provide governance-required fields (defaults are explicit and conservative)
        candidate.setdefault("equity", equity)
        candidate.setdefault("equity_peak", self.equity_peak)
        candidate.setdefault("regime_persistence", DEFAULT_REGIME_PERSISTENCE)
        candidate.setdefault("stop_distance_pct", DEFAULT_STOP_DISTANCE_PCT)
        candidate.setdefault("notional", equity)  # replay proxy: 1x notional

        # Filter to only supported parameters
        allowed = set(params.keys())
        filtered = {k: v for k, v in candidate.items() if k in allowed}

        # Check for missing required keyword-only args
        missing_required = []
        for name, p in params.items():
            if name == "self":
                continue
            is_required = (p.default is inspect._empty)
            if is_required and name not in filtered:
                missing_required.append(name)

        if missing_required:
            return {"ok": False, "reason": f"missing_required_gate_args:{','.join(missing_required)}"}

        return fn(**filtered)

    # ----------------------------
    # Main loop
    # ----------------------------

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

        if float(signal.strength) < float(MIN_SIGNAL_STRENGTH):
            self.threshold_blocks += 1
            self.prev_price = float(price)
            return

        decision = self._call_execution_gate(
            instrument=instrument,
            side=signal.direction,  # BUY / SELL
            rebalance_target_weights=None,
            signal_strength=float(signal.strength),
            strategy_style=getattr(signal, "style", "NONE"),
            timestamp=datetime.utcnow().isoformat(),
        )

        if not self._gate_ok(decision):
            self.gate_blocks += 1
            print("GATE BLOCK:", {"reason": self._gate_reason(decision), "decision": decision})
            self.prev_price = float(price)
            return

        # Simple replay PnL model (delta * direction * pip_scale)
        direction_sign = 1.0 if signal.direction == "BUY" else -1.0
        delta = float(price) - float(self.prev_price)
        realized_pnl = delta * direction_sign * PIP_SCALE

        self.pnl_tracker.record_trade(
            instrument=instrument,
            realized_pnl=float(realized_pnl),
            unrealized_pnl=0.0,
            timestamp=datetime.utcnow(),
        )

        # Update local equity peak after trade record
        equity = float(getattr(self.pnl_tracker, "current_equity", self.pnl_tracker.starting_equity))
        self.equity_peak = max(self.equity_peak, equity)

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