"""
engine/engine_loop.py

Replay/Simulation Engine Loop (Portfolio-Governed v5)
-----------------------------------------------------
Integrates:
- PositionBook (position lifecycle)
- PortfolioCapitalController (portfolio-level governance)
- ExecutionGate (instrument-level governance)
- PnLTracker (equity + drawdown)

Key:
- Exposure is measured in NOTIONAL terms (qty * price).
- Baseline sizing proxy set to 5% (aligns with PCC default instrument cap 8%).
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


class EngineLoop:
    def __init__(self, behaviour: str = "D", starting_equity: float = 1000.0):
        self.profile = get_profile_for_behaviour(behaviour)
        self.signal_engine = SignalEngine(self.profile)

        self.execution_gate = ExecutionGate()
        self.pnl_tracker = PnLTracker(starting_equity=float(starting_equity))
        self.position_book = PositionBook()
        self.pcc = PortfolioCapitalController()

        self.behaviour = behaviour
        self.prev_price: Optional[float] = None
        self.price_window: Deque[float] = deque(maxlen=MA_WINDOW)

        self.min_signal_strength = _env_float("CSS_MIN_SIGNAL_STRENGTH", 0.61)

        # Equity peak used by governance layers
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
        # You can override by setting: engine.asset_class_map["XAU_USD"]="COMMODITIES", etc.
        self.asset_class_map: Dict[str, str] = {}

        self.current_step = 0

    # ----------------------------------------------------
    # Exposure Helpers (NOTIONAL)
    # ----------------------------------------------------

    def _asset_class(self, instrument: str) -> str:
        return self.asset_class_map.get(instrument, "FX")

    def _mark_price(self) -> float:
        """
        Mark price used for notional exposure valuation.
        Uses prev_price when available, otherwise falls back to 0.
        """
        return float(self.prev_price) if self.prev_price is not None else 0.0

    def _total_exposure_notional(self) -> float:
        mp = self._mark_price()
        if mp <= 0:
            return 0.0
        return sum(float(pos.size) * mp for pos in self.position_book.positions.values())

    def _instrument_exposure_notional(self, instrument: str) -> float:
        mp = self._mark_price()
        if mp <= 0:
            return 0.0
        pos = self.position_book.positions.get(instrument)
        return float(pos.size) * mp if pos else 0.0

    def _asset_class_exposure_notional(self, asset_class: str) -> float:
        mp = self._mark_price()
        if mp <= 0:
            return 0.0
        total = 0.0
        for inst, pos in self.position_book.positions.items():
            if self._asset_class(inst) == asset_class:
                total += float(pos.size) * mp
        return float(total)

    def _open_positions_in_asset_class(self, asset_class: str) -> int:
        return sum(1 for inst in self.position_book.positions if self._asset_class(inst) == asset_class)

    # ----------------------------------------------------
    # Main Loop
    # ----------------------------------------------------

    def process_bar(self, instrument: str, price: float) -> None:
        self.current_step += 1
        self.price_window.append(float(price))

        if self.prev_price is None:
            self.prev_price = float(price)
            return

        moving_avg = sum(self.price_window) / len(self.price_window)

        signal = self.signal_engine.generate(
            instrument=instrument,
            price_now=float(price),
            price_prev=float(self.prev_price),
            moving_avg=float(moving_avg),
        )

        self.total_signals += 1

        # 0) Evaluate exits first (realized PnL into ledger)
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
            self.prev_price = float(price)
            return

        # 2) Threshold gate
        if float(signal.strength) < float(self.min_signal_strength):
            self.threshold_blocks += 1
            self.prev_price = float(price)
            return

        # 3) No pyramiding for now
        if self.position_book.has_position(instrument):
            self.prev_price = float(price)
            return

        # 4) ExecutionGate (instrument-level governance + sizing)
        # IMPORTANT: baseline sizing proxy is 5% (aligns with PCC instrument cap 8%)
        decision = self.execution_gate.evaluate_trade(
            instrument=instrument,
            side=signal.direction,
            notional=equity * 0.05,
            stop_distance_pct=float(DEFAULT_STOP_DISTANCE_PCT),
            equity=equity,
            equity_peak=self.equity_peak,
            regime_persistence=float(DEFAULT_REGIME_PERSISTENCE),
        )

        if str(decision.get("decision", {}).get("final", "")).upper() != "ALLOW":
            self.gate_blocks += 1
            self.prev_price = float(price)
            return

        debug = decision.get("debug", {}) if isinstance(decision, dict) else {}
        scaled_notional = float(debug.get("scaled_notional", 0.0))
        if scaled_notional <= 0.0:
            self.gate_blocks += 1
            self.prev_price = float(price)
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
            self.prev_price = float(price)
            return

        final_notional = scaled_notional * float(pcc_decision.sizing_multiplier)
        if final_notional <= 0.0:
            self.pcc_blocks += 1
            self.prev_price = float(price)
            return

        # 6) Open position (size is quantity; notional is qty * price)
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
        self.prev_price = float(price)

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
        }