"""
EngineLoop – Canonical Capital Execution Loop (DEBUG SAFE)
Capital Strata Systems (CSS)

Upgrades:
- ExecutionGate debug surfaced
- Clean ALLOW/BLOCK handling
- Cost engine integrated
- No silent failures
"""

from __future__ import annotations

import uuid
from typing import Dict, Any
from datetime import datetime

from engine.execution.execution_gate import ExecutionGate
from engine.execution.execution_cost_engine import ExecutionCostEngine
from engine.performance.pnl_tracker import PnLTracker


class EngineLoop:

    def __init__(self) -> None:
        self.engine_run_id = f"css-{uuid.uuid4()}"
        self.starting_equity = 100000.0

        self.pnl_tracker = PnLTracker(self.starting_equity)
        self.gate = ExecutionGate()
        self.cost_engine = ExecutionCostEngine(deterministic=True)

        self.step_count = 0
        self.instruments = ["EUR_USD", "GBP_USD", "USD_JPY", "AUD_USD", "USD_CHF"]

    # --------------------------------------------------

    def _simulate_pnl(self, instrument: str, step: int) -> float:
        patterns = {
            "EUR_USD": [800, 900, 1000, -2500, 900],
            "GBP_USD": [-300, -400, -500, 1000, 1200],
            "USD_JPY": [600, 700, -800, 900, 1000],
            "AUD_USD": [200, 300, -200, 400, -500],
            "USD_CHF": [-100, -200, -300, 400, -600],
        }
        return float(patterns[instrument][step % len(patterns[instrument])])

    # --------------------------------------------------

    def step(self, step: int) -> Dict[str, Any]:

        self.step_count += 1

        instrument = self.instruments[step % len(self.instruments)]
        notional = 10000.0

        equity = self.pnl_tracker.current_equity
        equity_peak = self.pnl_tracker.peak_equity

        decision = self.gate.evaluate_trade(
            instrument=instrument,
            side="BUY",
            notional=notional,
            stop_distance_pct=0.01,
            equity=equity,
            equity_peak=equity_peak,
            regime_persistence=0.85,
        )

        # ---- BLOCK HANDLING ----
        if decision["decision"]["final"] == "BLOCK":
            return {
                "status": "BLOCKED",
                "reason": decision.get("reason"),
                "gate_debug": decision.get("debug", {}),
            }

        # ---- TRADE EXECUTION ----
        raw_pnl = self._simulate_pnl(instrument, step)

        pnl_after_costs = self.cost_engine.apply_costs(
            instrument=instrument,
            notional=notional,
            raw_pnl=raw_pnl,
        )

        self.pnl_tracker.record_trade(
            instrument=instrument,
            realized_pnl=pnl_after_costs,
        )

        return {
            "status": "EXECUTED",
            "instrument": instrument,
            "raw_pnl": raw_pnl,
            "pnl_after_costs": pnl_after_costs,
            "equity": self.pnl_tracker.current_equity,
        }

    # --------------------------------------------------

    def run(self, steps: int = 200) -> None:

        print("==== INSTITUTIONAL SIMULATION (DEBUG MODE) ====")

        for i in range(steps):
            result = self.step(i)
            print(result)

        print("\n==== EQUITY SUMMARY ====")
        print(self.pnl_tracker.equity_snapshot())

        print("\n==== INSTRUMENT SUMMARY ====")
        print(self.pnl_tracker.instrument_summary())

        print("\n==== RUN SUMMARY ====")
        print(f"engine_run_id: {self.engine_run_id}")
        print(f"steps: {self.step_count}")

        print("\n==== SIMULATION COMPLETE ====")


def main() -> int:
    loop = EngineLoop()
    loop.run(steps=200)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
