"""
EngineLoop – Canonical Capital Execution Loop
Capital Strata Systems

Design:
- Calls ExecutionGate via flat interface (instrument/side/notional/...)
- Uses RiskTelemetry for drawdown + kill-switch
- Prints step-by-step decisions + a run summary
"""

from __future__ import annotations

import uuid
from typing import Dict, Any, List

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

        # simple counters for summary
        self.steps: int = 0
        self.allow_count: int = 0
        self.block_count: int = 0
        self.compounding_applied_count: int = 0
        self.hard_breaker_count: int = 0

    def _propose_trade(self) -> Dict[str, Any]:
        # Flat interface (matches engine/execution/execution_gate.py)
        return self.gate.evaluate_trade(
            instrument="EUR_USD",
            side="BUY",
            notional=10000.0,
            stop_distance_pct=0.01,
            equity=self.equity,
            equity_peak=self.equity_peak,
            regime_persistence=0.85,
            policy="core",
        )

    def _simulate_pnl_path(self, i: int) -> float:
        # Deterministic path with a drawdown episode (to test breakers)
        # Feel free to tune later; this is just a harness.
        path: List[float] = [
            25.0, 25.0, 25.0,     # up
            -2000.0, -2000.0,     # drawdown
            50.0, 50.0,           # stabilize
            -15000.0,             # big hit (tests hard limit if repeated)
            1000.0, 1000.0,       # recovery attempt
        ]
        if i < len(path):
            return path[i]
        return 0.0

    def step(self, i: int) -> Dict[str, Any]:
        # Kill-switch enforcement (telemetry owns the hard stop state)
        if self.telemetry.kill_switch_triggered:
            return {
                "status": "HALTED",
                "reason": "hard_drawdown_limit_triggered",
                "drawdown_pct": self.telemetry._compute_drawdown_pct(),
            }

        decision = self._propose_trade()

        final = (decision.get("decision") or {}).get("final", "BLOCK")
        if final == "ALLOW":
            self.allow_count += 1
        else:
            self.block_count += 1

        if decision.get("reason") == "hard_drawdown_circuit_breaker":
            self.hard_breaker_count += 1

        comp_applied = bool(
            (decision.get("decision") or {}).get("compounding", {}).get("applied", False)
        )
        if comp_applied:
            self.compounding_applied_count += 1

        # Simulated PnL
        pnl = float(self._simulate_pnl_path(i))
        self.equity += pnl
        self.equity_peak = max(self.equity_peak, self.equity)

        self.telemetry.update_equity(self.equity)

        snapshot = self.telemetry.snapshot(
            effective_risk_pct=0.01,
            compounding_applied=comp_applied,
            regime_persistence=0.85,
        )

        self.steps += 1

        return {
            "engine_run_id": self.engine_run_id,
            "step": i,
            "pnl": pnl,
            "decision": decision,
            "equity": self.equity,
            "telemetry": snapshot.as_dict(),
        }

    def run(self, n: int = 12) -> None:
        for i in range(n):
            result = self.step(i)
            print(result)

            if result.get("status") == "HALTED":
                print("=== ENGINE HALTED ===")
                break

        print("\n==== RUN SUMMARY ====")
        print(f"engine_run_id: {self.engine_run_id}")
        print(f"steps: {self.steps}")
        print(f"ALLOW: {self.allow_count}")
        print(f"BLOCK: {self.block_count}")
        print(f"hard_drawdown_circuit_breaker: {self.hard_breaker_count}")
        print(f"compounding_applied: {self.compounding_applied_count}")


def main() -> int:
    loop = EngineLoop()
    loop.run(n=12)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
