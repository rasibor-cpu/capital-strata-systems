"""
EngineLoop – Canonical Capital Execution Loop
Capital Strata Systems

Now includes:
- RiskTelemetry integration
- 20% institutional hard kill-switch
- Structured risk reporting
"""

from __future__ import annotations

import uuid
from typing import Dict, Any

from engine.execution.execution_gate import ExecutionGate
from engine.risk.risk_telemetry import RiskTelemetry


class EngineLoop:

    def __init__(self) -> None:
        self.engine_run_id = f"css-{uuid.uuid4()}"
        self.gate = ExecutionGate()
        self.telemetry = RiskTelemetry()

        # Initial simulated capital
        self.equity = 100000.0
        self.equity_peak = 100000.0

        self.telemetry.update_equity(self.equity)

    # --------------------------------------------------
    # Core Step
    # --------------------------------------------------

    def step(self) -> Dict[str, Any]:

        # ---- Kill-switch enforcement ----
        if self.telemetry.kill_switch_triggered:
            return {
                "status": "HALTED",
                "reason": "hard_drawdown_limit_triggered",
                "drawdown_pct": self.telemetry._compute_drawdown_pct(),
            }

        # ---- Trade proposal (simulation) ----
        decision = self.gate.evaluate_trade(
            instrument="EUR_USD",
            side="BUY",
            notional=10000.0,
            stop_distance_pct=0.01,
            equity=self.equity,
            equity_peak=self.equity_peak,
            regime_persistence=0.8,
        )

        # ---- Simulated PnL ----
        simulated_pnl = 25.0  # deterministic for now
        self.equity += simulated_pnl
        self.equity_peak = max(self.equity_peak, self.equity)

        self.telemetry.update_equity(self.equity)

        # ---- Risk Snapshot ----
        effective_risk_pct = 0.01
        comp_applied = decision.get("decision", {}).get("compounding", {}).get("applied", False)

        snapshot = self.telemetry.snapshot(
            effective_risk_pct=effective_risk_pct,
            compounding_applied=comp_applied,
            regime_persistence=0.8,
        )

        return {
            "engine_run_id": self.engine_run_id,
            "decision": decision,
            "equity": self.equity,
            "telemetry": snapshot.as_dict(),
        }


def main() -> int:
    loop = EngineLoop()

    for i in range(10):
        result = loop.step()
        print(result)

        if result.get("status") == "HALTED":
            print("⚠️ ENGINE HALTED")
            break

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
