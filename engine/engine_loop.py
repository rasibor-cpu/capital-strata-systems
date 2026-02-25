"""
engine/engine_loop.py

Replay/Simulation Engine Loop (Portfolio-Governed v6)
-----------------------------------------------------
Fixes:
- Multi-instrument exposure valuation now uses per-instrument mark prices
  (qty * last_price[instrument]) instead of a single shared prev_price.
- This allows PCC asset-class/global caps to trigger correctly in portfolio runs.

Integrates:
- ExecutionGate (instrument-level governance)
- PortfolioCapitalController (portfolio-level governance)
- PositionBook (position lifecycle)
- PnLTracker (equity + drawdown)
"""

from __future__ import annotations

from collections import deque
from datetime import datetime
from typing import Any, Dict, Optional, Deque
import os

from engine.execution.execution_gate import ExecutionGate
from engine.performance.pnl_tracker import PnLTracker
from engine.strategy.behaviour_mapper import get_profile_for_behaviour
from engine.strategy.signal_engine import SignalEngine
from engine.core.position_book import PositionBook
from engine.portfolio.portfolio_capital_controller import (
    PortfolioCapitalController,
    TradeProposal,
)

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

# Baseline sizing proxy (edit during stress tests)
BASELINE_NOTIONAL_PCT = _env_float("CSS_BASELINE_NOTIONAL_PCT", 0.08)  # set 0.07 / 0.08 / 0.09 via env if you want


class EngineLoop:
    def __init__(self, behaviour: str = "D", starting_equity: float = 1000.0):
        self.profile = get_profile_for_behaviour(behaviour)
        self.signal_engine = SignalEngine(self.profile)

        self.execution_gate = ExecutionGate()
        self.pnl_tracker = PnLTracker(starting_equity=float(starting_equity))
        self.position_book = PositionBook()
        self.pcc = PortfolioCapitalController()

        self.behaviour = behaviour

        # Per-instrument rolling price windows (so MA is instrument-correct)
        self.price_windows: Dict[str, Deque[float]] = {}
        self.prev_price_by_instrument: Dict[str, float] = {}

        # Per-instrument last mark (used for exposure valuation)
        self.last_price_by_instrument: Dict[str, float] = {}

        self.min_signal_strength = _env_float("CSS_MIN_SIGNAL_STRENGTH", 0.61)

        self.equity_peak: float = float(starting_equity)

        # Diagnostics
        self.total_signals = 0
        self.regime_flat_blocks = 0
        self.threshold_blocks = 0
        self.gate_blocks = 0
        self.pcc_blocks = 0
        self.trade_count = 0
        self.exit_count = 0

        # Phase-1 asset class registry (default FX)
        self.asset_class_map: Dict[str, str] = {}

        self.current_step = 0

    # ----------------------------------------------------
    # Exposure Helpers (NOTIONAL, per-instrument mark)
    # ----------------------------------------------------

    def _asset_class(self, instrument: str) -> str:
        return self.asset_class_map.get(instrument, "FX")

    def _mark_price(self, instrument: str) -> float:
        return float(self.last_price_by_instrument.get(instrument, 0.0))

    def _position_notional(self, instrument: str) -> float:
        pos = self.position_book.positions.get(instrument)
        if pos is None:
            return 0.0
        mp = self._mark_price(instrument)
        if mp <= 0.0:
            return 0.0
        return float(pos.size) * mp

    def _total_exposure_notional(self) -> float:
        total = 0.0
        for inst in self.position_book.positions.keys():
            total += self._position_notional(inst)
        return float(total)

    def _instrument_exposure_notional(self, instrument: str) -> float:
        return float(self._position_notional(instrument))

    def _asset_class_exposure_notional(self, asset_class: str) -> float:
        total = 0.0
        for inst in self.position_book.positions.keys():
            if self._asset_class(inst) == asset_class:
                total += self._position_notional(inst)
        return float(total)

    def _open_positions_in_asset_class(self, asset_class: str) -> int:
        return sum(1 for inst in self.position_book.positions.keys() if self._asset_class(inst) == asset_class)

    # ----------------------------------------------------
    # Main Loop
    # ----------------------------------------------------

    def process_bar(self, instrument: str, price: float) -> None:
        self.current_step += 1

        # Update mark price cache (critical for PCC exposure valuation)
        self.last_price_by_instrument[instrument] = float(price)

        # Ensure rolling window exists
        if instrument not in self.price_windows:
            self.price_windows[instrument] = deque(maxlen=MA_WINDOW)

        self.price_windows[instrument].append(float(price))

        # Need a prev price per instrument for signal generation
        if instrument not in self.prev_price_by_instrument:
            self.prev_price_by_instrument[instrument] = float(price)
            return

        prev_price = float(self.prev_price_by_instrument[instrument])
        moving_avg = sum(self.price_windows[instrument]) / len(self.price_windows[instrument])

        signal = self.signal_engine.generate(
            instrument=instrument,
            price_now=float(price),
            price_prev=float(prev_price),
            moving_avg=float(moving_avg),
        )

        self.total_signals += 1

        # 0) Evaluate exits first
        realized_exit = self.position_book.evaluate_exit(
            instrument=instrument,
            current_price=float(price),
            current_step=self.current_step,
            incoming_signal=signal.direction,
        )

        if realized_exit != 0.0:
            self.exit_count += 1
            self.pnl_tracker.record_trade(
                instrument=instrument,
                realized_pnl=float(realized_exit),
                unrealized_pnl=0.0,
                timestamp=datetime.utcnow(),
            )

        # Update equity peak for governance
        equity = float(self.pnl_tracker.current_equity)
        self.equity_peak = max(self.equity_peak, equity)

        # 1) Regime flat
        if signal.direction == "FLAT":
            self.regime_flat_blocks += 1
            self.prev_price_by_instrument[instrument] = float(price)
            return

        # 2) Threshold gate
        if float(signal.strength) < float(self.min_signal_strength):
            self.threshold_blocks += 1
            self.prev_price_by_instrument[instrument] = float(price)
            return

        # 3) No pyramiding
        if self.position_book.has_position(instrument):
            self.prev_price_by_instrument[instrument] = float(price)
            return

        # 4) ExecutionGate (instrument-level governance + sizing)
        decision = self.execution_gate.evaluate_trade(
            instrument=instrument,
            side=signal.direction,
            notional=equity * float(BASELINE_NOTIONAL_PCT),
            stop_distance_pct=float(DEFAULT_STOP_DISTANCE_PCT),
            equity=equity,
            equity_peak=self.equity_peak,
            regime_persistence=float(DEFAULT_REGIME_PERSISTENCE),
        )

        if str(decision.get("decision", {}).get("final", "")).upper() != "ALLOW":
            self.gate_blocks += 1
            self.prev_price_by_instrument[instrument] = float(price)
            return

        debug = decision.get("debug", {}) if isinstance(decision, dict) else {}
        scaled_notional = float(debug.get("scaled_notional", 0.0))
        if scaled_notional <= 0.0:
            self.gate_blocks += 1
            self.prev_price_by_instrument[instrument] = float(price)
            return

        # 5) PCC (portfolio-level governance)
        asset_class = self._asset_class(instrument)

        proposal = TradeProposal(
            instrument=instrument,
            asset_class=asset_class,
            requested_notional=scaled_notional,
            equity=equity,
            current_total_exposure=self._total_exposure_notional(),
            current_instrument_exposure=self._instrument_exposure_notional(instrument),
            current_asset_class_exposure=self._asset_class_exposure_notional(asset_class),
            portfolio_dd_pct=self.pnl_tracker.current_drawdown() * 100.0,
            open_positions_in_asset_class=self._open_positions_in_asset_class(asset_class),
        )

        pcc_decision = self.pcc.evaluate(proposal)

        if pcc_decision.final != "ALLOW":
            self.pcc_blocks += 1
            self.prev_price_by_instrument[instrument] = float(price)
            return

        final_notional = scaled_notional * float(pcc_decision.sizing_multiplier)
        if final_notional <= 0.0:
            self.pcc_blocks += 1
            self.prev_price_by_instrument[instrument] = float(price)
            return

        # 6) Open position (qty such that qty * price = notional)
        qty = float(final_notional) / float(price)

        self.position_book.open_position(
            instrument=instrument,
            side=signal.direction,
            size=float(qty),
            price=float(price),
            step=self.current_step,
            stop_distance_pct=float(DEFAULT_STOP_DISTANCE_PCT),
        )

        self.trade_count += 1
        self.prev_price_by_instrument[instrument] = float(price)

    # ----------------------------------------------------
    # Summary
    # ----------------------------------------------------

    def summary(self) -> Dict[str, Any]:
        net_pnl = self.pnl_tracker.current_equity - self.pnl_tracker.starting_equity
        return {
            "behaviour": self.behaviour,
            "total_signals": self.total_signals,
            "regime_flat_blocks": self.regime_flat_blocks,
            "threshold_blocks": self.threshold_blocks,
            "gate_blocks": self.gate_blocks,
            "pcc_blocks": self.pcc_blocks,
            "trades_opened": self.trade_count,
            "exits_closed": self.exit_count,
            "starting_equity": float(self.pnl_tracker.starting_equity),
            "ending_equity": float(self.pnl_tracker.current_equity),
            "net_pnl": float(net_pnl),
            "current_drawdown_pct": float(self.pnl_tracker.current_drawdown() * 100.0),
            "open_positions": len(self.position_book.positions),
            "baseline_notional_pct": float(BASELINE_NOTIONAL_PCT),
        }