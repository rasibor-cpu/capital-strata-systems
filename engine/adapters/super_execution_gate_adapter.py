"""
Super Execution Gate Adapter
--------------------------------
Wraps ExecutionGate into the Phase-2A Gate Registry system.

This allows the full ExecutionGate stack
(compounding + drawdown compression + breaker + risk governor)
to behave like a standard adapter-based gate.

Fail-closed.
First BLOCK wins (handled by DecisionBuilder).
"""

from __future__ import annotations

from typing import Any, Dict

from engine.execution.execution_gate import (
    ExecutionGate,
    TradeIntent,
    EquityContext,
    MarketContext,
)

from engine.execution_decision import GateResult


class SuperExecutionGateAdapter:
    """
    Adapter wrapper for ExecutionGate.
    """

    def __init__(self) -> None:
        self._gate = ExecutionGate()

    # ----------------------------------------------------------
    # Adapter Interface (Phase-2A compatible)
    # ----------------------------------------------------------
    def evaluate(self, *, state: Dict[str, Any]) -> GateResult:
        """
        Expected state fields:

        REQUIRED:
        - instrument
        - side
        - notional
        - stop_distance_pct
        - equity
        - equity_peak

        OPTIONAL:
        - policy
        - regime_persistence
        - vol_ratio
        - spread_bps
        - high_risk_news
        """

        try:
            # --------------------------
            # Build Intent
            # --------------------------
            intent = TradeIntent(
                instrument=state["instrument"],
                side=state["side"],
                notional=state["notional"],
                stop_distance_pct=state["stop_distance_pct"],
                policy=state.get("policy", "core"),
            )

            # --------------------------
            # Equity Context
            # --------------------------
            eq = EquityContext(
                equity=state["equity"],
                equity_peak=state["equity_peak"],
            )

            # --------------------------
            # Market Context (optional)
            # --------------------------
            mkt = MarketContext(
                regime_persistence=state.get("regime_persistence"),
                vol_ratio=state.get("vol_ratio"),
                spread_bps=state.get("spread_bps"),
                high_risk_news=state.get("high_risk_news"),
            )

            # --------------------------
            # Evaluate via ExecutionGate
            # --------------------------
            decision = self._gate.evaluate_trade(
                intent=intent,
                eq=eq,
                mkt=mkt,
            )

            # --------------------------
            # Normalize to GateResult
            # --------------------------
            if decision.decision == "ALLOW":
                return GateResult(
                    ok=True,
                    gate="super_execution_gate",
                    reason="allowed",
                    data=decision.meta,
                )

            return GateResult(
                ok=False,
                gate="super_execution_gate",
                reason="blocked",
                data={
                    "reasons": decision.reasons,
                    "meta": decision.meta,
                },
            )

        except Exception as e:
            # Fail-closed enforcement
            return GateResult(
                ok=False,
                gate="super_execution_gate",
                reason="exception",
                data={"error": str(e)},
            )
