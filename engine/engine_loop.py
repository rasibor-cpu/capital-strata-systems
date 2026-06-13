"""
engine/engine_loop.py

Replay/Simulation Engine Loop (Portfolio-Governed v8 + Audit Spine)
-------------------------------------------------------------------
Includes:
- Multi-instrument mark pricing (per-instrument last_price) for correct exposure valuation
- Rolling returns buffers (per instrument)
- Statistical correlation score (avg abs corr vs OPEN positions in same asset class)
- PCC exposure caps + drawdown policy enforcement
- Governance audit logging (JSONL) for explainability

Notes:
- Audit logger is fail-safe: if module missing, engine still runs.
"""

from __future__ import annotations

from collections import deque
from datetime import datetime
from typing import Any, Dict, Optional, Deque
import os
import statistics
import time

from engine.execution.execution_gate import ExecutionGate
from engine.performance.pnl_tracker import PnLTracker
from engine.strategy.behaviour_mapper import get_profile_for_behaviour
from engine.strategy.signal_engine import SignalEngine
from engine.core.position_book import PositionBook
from engine.portfolio.portfolio_capital_controller import (
    PortfolioCapitalController,
    TradeProposal,
)
from engine.risk.margin_engine import MarginEngine

# Optional audit spine (fail-safe import)
try:
    from engine.governance.governance_audit_logger import (
        GovernanceAuditLogger,
        GovernanceDecisionRecord,
    )
except Exception:  # pragma: no cover
    GovernanceAuditLogger = None  # type: ignore
    GovernanceDecisionRecord = None  # type: ignore

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

# Baseline sizing proxy for stress tests (override via env, e.g. 0.07 / 0.08 / 0.09)
BASELINE_NOTIONAL_PCT = _env_float("CSS_BASELINE_NOTIONAL_PCT", 0.08)
ANTI_BLEED_FEE_BPS = _env_float("CSS_ANTI_BLEED_FEE_BPS", 1.0)
ANTI_BLEED_SPREAD_BPS = _env_float("CSS_ANTI_BLEED_SPREAD_BPS", 1.0)
ANTI_BLEED_SLIPPAGE_BPS = _env_float("CSS_ANTI_BLEED_SLIPPAGE_BPS", 1.0)

# Correlation window (rolling returns length)
CORR_WINDOW = int(_env_float("CSS_CORR_WINDOW", 50))


class EngineLoop:
    def __init__(self, behaviour: str = "D", starting_equity: float = 1000.0):
        self.profile = get_profile_for_behaviour(behaviour)
        self.signal_engine = SignalEngine(self.profile)

        self.execution_gate = ExecutionGate()
        self.margin_engine = MarginEngine()
        self.pnl_tracker = PnLTracker(starting_equity=float(starting_equity))
        self.position_book = PositionBook()
        self.pcc = PortfolioCapitalController()

        self.behaviour = behaviour

        # Per-instrument rolling price windows (MA must be instrument-correct)
        self.price_windows: Dict[str, Deque[float]] = {}
        self.prev_price_by_instrument: Dict[str, float] = {}

        # Per-instrument last mark (used for exposure valuation)
        self.last_price_by_instrument: Dict[str, float] = {}

        # Rolling returns storage for correlation governance
        self.return_history: Dict[str, Deque[float]] = {}
        self.correlation_window: int = int(CORR_WINDOW)

        # Threshold gate (instance-bound)
        self.min_signal_strength = _env_float("CSS_MIN_SIGNAL_STRENGTH", 0.61)

        # Equity peak for governance
        self.equity_peak: float = float(starting_equity)

        # Diagnostics
        self.total_signals = 0
        self.regime_flat_blocks = 0
        self.threshold_blocks = 0
        self.gate_blocks = 0
        self.pcc_blocks = 0
        self.trade_count = 0
        self.exit_count = 0

        # Asset class registry (default FX)
        self.asset_class_map: Dict[str, str] = {}

        self.current_step = 0

        # Governance audit logger (optional)
        self.audit_logger = None
        if GovernanceAuditLogger is not None:
            try:
                self.audit_logger = GovernanceAuditLogger()
            except Exception:
                self.audit_logger = None

    # ----------------------------------------------------
    # Asset class + exposure helpers (NOTIONAL, per-instrument mark)
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
        return sum(
            1 for inst in self.position_book.positions.keys()
            if self._asset_class(inst) == asset_class
        )

    # ----------------------------------------------------
    # Correlation governance helpers
    # ----------------------------------------------------

    def _update_returns(self, instrument: str, price: float) -> None:
        """
        Update rolling returns buffer for instrument.
        Uses prev_price_by_instrument (instrument-correct).
        """
        if instrument not in self.return_history:
            self.return_history[instrument] = deque(maxlen=self.correlation_window)

        prev = self.prev_price_by_instrument.get(instrument)
        if prev is None or prev <= 0:
            return

        ret = (float(price) - float(prev)) / float(prev)
        self.return_history[instrument].append(float(ret))

    def _avg_abs_corr_vs_open(self, *, instrument: str, asset_class: str) -> float:
        """
        Average absolute correlation of `instrument` returns vs each OPEN position
        in the SAME asset class.

        Returns 0.0 if insufficient data.
        """
        base = list(self.return_history.get(instrument, []))
        if len(base) < 10:
            return 0.0

        corrs: list[float] = []

        for inst in self.position_book.positions.keys():
            if inst == instrument:
                continue
            if self._asset_class(inst) != asset_class:
                continue

            other = list(self.return_history.get(inst, []))
            if len(other) < 10:
                continue

            n = min(len(base), len(other))
            if n < 10:
                continue

            r1 = base[-n:]
            r2 = other[-n:]

            try:
                c = statistics.correlation(r1, r2)
                if c != c:  # NaN guard
                    continue
                corrs.append(abs(float(c)))
            except Exception:
                continue

        if not corrs:
            return 0.0

        return float(sum(corrs) / len(corrs))

    # ----------------------------------------------------
    # Audit helper
    # ----------------------------------------------------

    def _audit_pcc_decision(
        self,
        *,
        instrument: str,
        asset_class: str,
        signal_strength: float,
        proposal: TradeProposal,
        avg_corr: float,
        pcc_final: str,
        pcc_reason: str,
        sizing_multiplier: float,
    ) -> None:
        """
        Non-blocking audit log for PCC decisions (ALLOW/BLOCK).
        """
        if self.audit_logger is None or GovernanceDecisionRecord is None:
            return

        try:
            effective_notional = float(proposal.requested_notional) * float(sizing_multiplier)
            rec = GovernanceDecisionRecord(
                timestamp=float(time.time()),
                instrument=str(instrument),
                asset_class=str(asset_class),
                signal_strength=float(signal_strength),
                requested_notional=float(proposal.requested_notional),
                effective_notional=float(effective_notional),
                equity=float(proposal.equity),
                portfolio_dd_pct=float(proposal.portfolio_dd_pct),
                total_exposure=float(proposal.current_total_exposure),
                asset_class_exposure=float(proposal.current_asset_class_exposure),
                correlation_score=float(avg_corr),
                pcc_final=str(pcc_final),
                pcc_reason=str(pcc_reason),
                sizing_multiplier=float(sizing_multiplier),
            )
            self.audit_logger.record(rec)
        except Exception:
            # fail-silent
            return

    # ----------------------------------------------------
    # Main loop
    # ----------------------------------------------------

    def process_bar(self, instrument: str, price: float) -> None:
        self.current_step += 1

        # Update mark price cache (critical for PCC exposure valuation)
        self.last_price_by_instrument[instrument] = float(price)

        # Ensure rolling MA window exists
        if instrument not in self.price_windows:
            self.price_windows[instrument] = deque(maxlen=MA_WINDOW)

        self.price_windows[instrument].append(float(price))

        # If first tick for this instrument, seed prev and return
        if instrument not in self.prev_price_by_instrument:
            self.prev_price_by_instrument[instrument] = float(price)
            if instrument not in self.return_history:
                self.return_history[instrument] = deque(maxlen=self.correlation_window)
            return

        # Update returns before overwriting prev
        self._update_returns(instrument, float(price))

        prev_price = float(self.prev_price_by_instrument[instrument])
        moving_avg = sum(self.price_windows[instrument]) / len(self.price_windows[instrument])

        signal = self.signal_engine.generate(
            instrument=instrument,
            price_now=float(price),
            price_prev=float(prev_price),
            moving_avg=float(moving_avg),
        )

        self.total_signals += 1
        signal_strength = float(getattr(signal, "strength", 0.0))

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
        if signal_strength < float(self.min_signal_strength):
            self.threshold_blocks += 1
            self.prev_price_by_instrument[instrument] = float(price)
            return

        # 3) No pyramiding
        if self.position_book.has_position(instrument):
            self.prev_price_by_instrument[instrument] = float(price)
            return

        # 4) ExecutionGate (instrument-level governance + sizing)
        margin_snapshot = self.margin_engine.calculate(
            required_margin=0.0,
            available_margin=equity,
            margin_source="SIMULATED",
        )

        decision = self.execution_gate.evaluate_trade(
            instrument=instrument,
            side=signal.direction,
            notional=equity * float(BASELINE_NOTIONAL_PCT),
            stop_distance_pct=float(DEFAULT_STOP_DISTANCE_PCT),
            equity=equity,
            equity_peak=self.equity_peak,
            regime_persistence=float(DEFAULT_REGIME_PERSISTENCE),
            expected_move_bps=signal_strength * 100.0,
            fee_bps=float(ANTI_BLEED_FEE_BPS),
            spread_bps=float(ANTI_BLEED_SPREAD_BPS),
            slippage_bps=float(ANTI_BLEED_SLIPPAGE_BPS),
            margin_snapshot=margin_snapshot,
            broker_mode="PAPER",
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

        # 5) PCC (portfolio-level governance + correlation throttle input)
        asset_class = self._asset_class(instrument)
        avg_corr = self._avg_abs_corr_vs_open(instrument=instrument, asset_class=asset_class)

        # Snapshot exposures (portfolio state) at time of decision
        total_exposure = self._total_exposure_notional()
        inst_exposure = self._instrument_exposure_notional(instrument)
        ac_exposure = self._asset_class_exposure_notional(asset_class)
        dd_pct = float(self.pnl_tracker.current_drawdown() * 100.0)
        open_in_ac = self._open_positions_in_asset_class(asset_class)

        proposal = TradeProposal(
            instrument=instrument,
            asset_class=asset_class,
            requested_notional=scaled_notional,
            equity=equity,
            current_total_exposure=total_exposure,
            current_instrument_exposure=inst_exposure,
            current_asset_class_exposure=ac_exposure,
            portfolio_dd_pct=dd_pct,
            open_positions_in_asset_class=open_in_ac,
            avg_correlation=float(avg_corr),
        )

        pcc_decision = self.pcc.evaluate(proposal)

        # Audit PCC decision (both allow and block)
        self._audit_pcc_decision(
            instrument=instrument,
            asset_class=asset_class,
            signal_strength=signal_strength,
            proposal=proposal,
            avg_corr=float(avg_corr),
            pcc_final=str(pcc_decision.final),
            pcc_reason=str(pcc_decision.reason),
            sizing_multiplier=float(pcc_decision.sizing_multiplier),
        )

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
            "corr_window": int(self.correlation_window),
        }
