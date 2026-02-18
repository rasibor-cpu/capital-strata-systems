"""
Super Execution Gate Adapter
--------------------------------
Wraps ExecutionGate into the Phase-2A Gate Registry system.

Returns THIS repo's GateResult shape:
  GateResult(gate_name=..., decision=..., reason=...)

ExecutionGate returns:
  {"decision": "...", "reason": "..."}
"""

from __future__ import annotations

from typing import Any, Dict

from engine.execution.execution_gate import ExecutionGate, TradeIntent, EquityContext, MarketContext
from engine.execution_decision import GateResult


class SuperExecutionGateAdapter:
    def __init__(self) -> None:
        self._gate = ExecutionGate()

    def evaluate(self, *, state: Dict[str, Any]) -> GateResult:
        try:
            intent = TradeIntent(
                instrument=state["instrument"],
                side=state["side"],
                notional=state["notional"],
                stop_distance_pct=state["stop_distance_pct"],
                policy=state.get("policy", "core"),
            )

            eq = EquityContext(
                equity=state["equity"],
                equity_peak=state["equity_peak"],
            )

            # MarketContext currently supports ONLY regime_persistence
            mkt = MarketContext(
                regime_persistence=state.get("regime_persistence"),
            )

            result = self._gate.evaluate_trade(intent=intent, eq=eq, mkt=mkt)

            decision = "BLOCK"
            reason = "UNEXPECTED_EXECUTION_GATE_OUTPUT"

            if isinstance(result, dict):
                decision = str(result.get("decision", "BLOCK")).upper()
                reason = str(result.get("reason", "BLOCKED_BY_SUPER_EXECUTION_GATE"))

            if decision not in ("ALLOW", "BLOCK"):
                decision = "BLOCK"

            return GateResult(
                gate_name="super_execution_gate",
                decision=decision,
                reason=reason,
            )

        except Exception as e:
            return GateResult(
                gate_name="super_execution_gate",
                decision="BLOCK",
                reason=f"EXCEPTION: {type(e).__name__}: {e}",
            )
