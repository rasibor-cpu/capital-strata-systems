"""
EngineLoop – Canonical Capital Execution Loop
Capital Strata Systems

Includes:
- RiskTelemetry integration
- 20% institutional hard kill-switch
- Structured risk reporting
- PerformanceLedger (multi-asset, multi-period tracking)

Repo-safe:
- PerformanceLedger API may differ across iterations
- We call summary/report/as_dict if available; otherwise print exports
"""

from __future__ import annotations

import uuid
from typing import Dict, Any

from engine.execution.execution_gate import ExecutionGate
from engine.risk.risk_telemetry import RiskTelemetry
from engine.performance.performance_ledger import PerformanceLedger


def _ledger_best_effort_summary(ledger: Any) -> Dict[str, Any]:
    """
    Adapter-safe summary accessor for PerformanceLedger.
    Tries common method names; otherwise returns exports for debugging.
    """
    for name in ("summary", "report", "as_dict", "to_dict", "export", "snapshot"):
        fn = getattr(ledger, name, None)
        if callable(fn):
            try:
                out = fn()
                # normalize to dict if possible
                if isinstance(out, dict):
                    return {"method": name, "data": out}
                return {"method": name, "data": {"value": out}}
            except Exception as e:
                return {"method": name, "error": f"{type(e).__name__}: {e}"}

    exports = [n for n in dir(ledger) if not n.startswith("_")]
    return {"method": None, "data": {"exports": exports}}


class EngineLoop:
    def __init__(self) -> None:
        self.engine_run_id = f"css-{uuid.uuid4()}"

        self.gate = ExecutionGate()
        self.telemetry = RiskTelemetry()
        self.ledger = PerformanceLedger()

        # Initial simulated capital
        self.equity = 100000.0
        self.equity_peak = 100000.0

        self.telemetry.update_equity(self.equity)

    def step(self, step_index: int) -> Dict[str, Any]:
        # ---- Kill-switch enforcement ----
        if self.telemetry.kill_switch_triggered:
            return {
                "status": "HALTED",
                "reason": "hard_drawdown_limit_triggered",
                "drawdown_pct": self.telemetry._compute_drawdown_pct(),
            }

        instrument = "EUR_USD"
        asset_class = "FX"  # required by PerformanceLedger.record_trade()

        # ---- Trade proposal (simulation) ----
        decision = self.gate.evaluate_trade(
            instrument=instrument,
            side="BUY",
            notional=10000.0,
            stop_distance_pct=0.01,
            equity=self.equity,
            equity_peak=self.equity_peak,
            regime_persistence=0.85,
        )

        # ---- Simulated PnL Pattern ----
        simulated_sequence = [800, 900, 1000, -2500, 900, 1000, -1500, 1000, 1000, 0]
        pnl = float(simulated_sequence[step_index % len(simulated_sequence)])

        # ---- Apply PnL ----
        self.equity += pnl
        self.equity_peak = max(self.equity_peak, self.equity)

        self.telemetry.update_equity(self.equity)

        # ---- Record Performance (only if pnl != 0; capture losses too) ----
        if pnl != 0:
            self.ledger.record_trade(
                asset_class=asset_class,
                instrument=instrument,
                pnl=pnl,
            )

        # ---- Risk Snapshot ----
        comp_applied = decision.get("decision", {}).get("compounding", {}).get("applied", False)

        snapshot = self.telemetry.snapshot(
            effective_risk_pct=0.01,
            compounding_applied=comp_applied,
            regime_persistence=0.85,
        )

        return {
            "engine_run_id": self.engine_run_id,
            "step": step_index,
            "pnl": pnl,
            "decision": decision,
            "equity": self.equity,
            "telemetry": snapshot.as_dict(),
        }


def main() -> int:
    loop = EngineLoop()

    print("==== CONTROLLER TIER ESCALATION TEST ====")

    for i in range(12):
        result = loop.step(i)
        print(result)

        if result.get("status") == "HALTED":
            print("⚠️ ENGINE HALTED")
            break

    print("\n===== LEDGER SUMMARY (BEST EFFORT) =====")
    print(_ledger_best_effort_summary(loop.ledger))

    print("\n===== RUN SUMMARY =====")
    print(f"engine_run_id: {loop.engine_run_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
