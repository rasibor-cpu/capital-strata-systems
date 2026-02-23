"""
engine/engine_loop.py

Institutional Replay Loop – 3-Bar Hold
Gate Signature Correct + Block Reason Sampling (first 5)
-------------------------------------------------------
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
from engine.equity_authority import EquityAuthority
from engine.risk.risk_governor import RiskGovernor

MA_WINDOW = 20


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

MIN_BAR_MOVE_R = _env_float("CSS_MIN_BAR_MOVE_R", 0.20)
SPREAD_BPS = _env_float("CSS_SPREAD_BPS", 2.5)
SLIPPAGE_BPS = _env_float("CSS_SLIPPAGE_BPS", 0.5)

DEFAULT_HOLD_BARS = int(_env_float("CSS_HOLD_BARS", 3))


class EngineLoop:
    def __init__(self, behaviour: str = "D", starting_equity: float = 1000.0):
        self.profile = get_profile_for_behaviour(behaviour)
        self.signal_engine = SignalEngine(self.profile)

        self.pnl_tracker = PnLTracker(starting_equity=float(starting_equity))

        self.equity_authority = EquityAuthority()
        self.equity_authority.bind_tracker(self.pnl_tracker)

        self.risk_governor = RiskGovernor(
            equity_authority=self.equity_authority,
            pnl_tracker=self.pnl_tracker,
        )

        self.execution_gate = ExecutionGate(risk_governor=self.risk_governor)

        self.prev_price: Optional[float] = None
        self.price_window: Deque[float] = deque(maxlen=MA_WINDOW)

        self.min_signal_strength = _env_float("CSS_MIN_SIGNAL_STRENGTH", 0.70)
        self.equity_peak: float = float(starting_equity)

        # Position state
        self.current_position: Optional[str] = None
        self.entry_price: Optional[float] = None
        self.hold_bars_remaining: int = 0

        # Stats
        self.trade_count = 0
        self.total_signals = 0
        self.threshold_blocks = 0
        self.gate_blocks = 0
        self._printed_blocks = 0

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
        if isinstance(inner, dict) and inner.get("final", "").upper() == "ALLOW":
            return True
        gov = decision.get("governor_response")
        if isinstance(gov, dict):
            if gov.get("ok") is True:
                return True
            if str(gov.get("status", "")).upper() in ("APPROVED", "ALLOW", "OK", "APPROVED_WITH_ADJUSTMENT"):
                return True
        return False

    def _call_execution_gate(self, **kwargs: Any) -> Any:
        fn = getattr(self.execution_gate, "evaluate_trade", None)
        if fn is None:
            return {"ok": False, "reason": "missing_evaluate_trade"}

        sig = inspect.signature(fn)
        allowed = set(sig.parameters.keys())

        equity = float(self.equity_authority.current_equity())
        self.equity_peak = max(self.equity_peak, equity)

        candidate = dict(kwargs)

        # ---- REQUIRED kw-only args (per your printed signature) ----
        candidate.setdefault("notional", equity)
        candidate.setdefault("stop_distance_pct", float(DEFAULT_STOP_DISTANCE_PCT))
        candidate.setdefault("equity", equity)
        candidate.setdefault("equity_peak", float(self.equity_peak))
        candidate.setdefault("regime_persistence", float(DEFAULT_REGIME_PERSISTENCE))

        # ---- Helpful diagnostics / realism knobs (optional in signature) ----
        candidate.setdefault("policy", "core")
        candidate.setdefault("spread_bps", float(SPREAD_BPS))
        candidate.setdefault("slippage_bps", float(SLIPPAGE_BPS))

        filtered = {k: v for k, v in candidate.items() if k in allowed}
        return fn(**filtered)

    def _close_position(self, instrument: str, price: float) -> None:
        if self.current_position is None or self.entry_price is None:
            return

        direction_sign = 1.0 if self.current_position == "BUY" else -1.0
        equity = float(self.equity_authority.current_equity())

        stop_pct = float(DEFAULT_STOP_DISTANCE_PCT)
        if stop_pct <= 0.0 or price <= 0.0:
            self.current_position = None
            self.entry_price = None
            self.hold_bars_remaining = 0
            return

        move_ratio = (float(price) - float(self.entry_price)) / (float(price) * stop_pct)

        # fixed 1% risk proxy for replay
        risk_amount = equity * 0.01
        gross_pnl = float(move_ratio) * float(risk_amount) * float(direction_sign)

        total_bps = float(SPREAD_BPS) + float(SLIPPAGE_BPS)
        cost = float(equity) * (total_bps / 10000.0)

        realized_pnl = gross_pnl - cost

        self.pnl_tracker.record_trade(
            instrument=instrument,
            realized_pnl=float(realized_pnl),
            unrealized_pnl=0.0,
            timestamp=datetime.utcnow(),
        )

        self.trade_count += 1
        self.current_position = None
        self.entry_price = None
        self.hold_bars_remaining = 0

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

        # If position open → manage hold
        if self.current_position is not None:
            self.hold_bars_remaining -= 1

            reverse = (
                (self.current_position == "BUY" and signal.direction == "SELL")
                or (self.current_position == "SELL" and signal.direction == "BUY")
            )

            if reverse or self.hold_bars_remaining <= 0:
                self._close_position(instrument, float(price))

            self.prev_price = float(price)
            return

        # No position open → evaluate entry
        if float(signal.strength) < float(self.min_signal_strength):
            self.threshold_blocks += 1
            self.prev_price = float(price)
            return

        # entry sanity: require enough movement vs stop-distance
        stop_pct = float(DEFAULT_STOP_DISTANCE_PCT)
        if stop_pct <= 0.0 or float(price) <= 0.0:
            self.prev_price = float(price)
            return

        move_ratio = (float(price) - float(self.prev_price)) / (float(price) * stop_pct)
        if abs(move_ratio) < float(MIN_BAR_MOVE_R):
            self.prev_price = float(price)
            return

        decision = self._call_execution_gate(
            instrument=instrument,
            side=signal.direction,
            timestamp=datetime.utcnow().isoformat(),
        )

        if not self._gate_ok(decision):
            self.gate_blocks += 1
            if self._printed_blocks < 5:
                self._printed_blocks += 1
                print("\n=== GATE BLOCK SAMPLE ===")
                print(decision)
                print("=== END SAMPLE ===\n")
            self.prev_price = float(price)
            return

        # Open position
        self.current_position = signal.direction
        self.entry_price = float(price)
        self.hold_bars_remaining = int(DEFAULT_HOLD_BARS)

        self.prev_price = float(price)

    def summary(self) -> Dict[str, Any]:
        eq = float(self.equity_authority.current_equity())
        return {
            "hold_bars": int(DEFAULT_HOLD_BARS),
            "min_signal_strength": float(self.min_signal_strength),
            "min_bar_move_r": float(MIN_BAR_MOVE_R),
            "spread_bps": float(SPREAD_BPS),
            "slippage_bps": float(SLIPPAGE_BPS),
            "total_signals": int(self.total_signals),
            "threshold_blocks": int(self.threshold_blocks),
            "gate_blocks": int(self.gate_blocks),
            "trades": int(self.trade_count),
            "starting_equity": float(self.pnl_tracker.starting_equity),
            "ending_equity": float(eq),
            "net_pnl": float(eq - float(self.pnl_tracker.starting_equity)),
        }