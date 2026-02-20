"""
engine/engine_loop.py

Canonical Institutional Engine Loop
Capital Strata Systems (CSS)

Integrated Layers:
- Multi-instrument rotation
- Allocator weighting
- Weekly instrument clamp
- ExecutionGate enforcement
- ExecutionCostEngine friction
- PnLTracker authoritative equity spine
- Futures-ready architecture (adapter hook)
"""

from __future__ import annotations

import uuid
from typing import Dict, Any
from datetime import datetime, timezone

from engine.execution.execution_gate import ExecutionGate
from engine.execution.execution_cost_engine import ExecutionCostEngine
from engine.performance.pnl_tracker import PnLTracker
from engine.allocation.asset_allocator import AssetAllocator


WEEKLY_REBALANCE_INTERVAL = 20
WEEKLY_INSTRUMENT_CLAMP_PCT = 0.05


class EngineLoop:

    def __init__(self) -> None:
        self.engine_run_id = f"css-{uuid.uuid4()}"
        self.equity_start = 100000.0

        self.pnl_tracker = PnLTracker(self.equity_start)
        self.gate = ExecutionGate()
        self.costs = ExecutionCostEngine(deterministic=True)
        self.allocator = AssetAllocator(intensity=0.5)

        self.step_count = 0
        self.instrument_suspensions: Dict[str, str] = {}

        # Futures-ready registry hook
        self.instruments = [
            "EUR_USD",
            "GBP_USD",
            "USD_JPY",
            "AUD_USD",
            "USD_CHF",
        ]

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

    def _current_week_key(self) -> str:
        now = datetime.now(timezone.utc)
        return f"{now.year}-W{now.isocalendar().week}"

    # --------------------------------------------------

    def _check_weekly_clamp(self, instrument: str) -> bool:
        snapshot = self.pnl_tracker.weekly_snapshot()
        week_key = self._current_week_key()

        if not snapshot:
            return False

        weekly_inst = snapshot.get("weekly_instrument_totals", {})
        pnl = float(weekly_inst.get(instrument, 0.0))

        clamp_threshold = -self.equity_start * WEEKLY_INSTRUMENT_CLAMP_PCT

        if pnl <= clamp_threshold:
            self.instrument_suspensions[instrument] = week_key
            return True

        return False

    # --------------------------------------------------

    def step(self, step: int) -> Dict[str, Any]:

        self.step_count += 1

        instrument = self.instruments[step % len(self.instruments)]
        week_key = self._current_week_key()

        # Release suspension if new week
        if instrument in self.instrument_suspensions:
            if self.instrument_suspensions[instrument] != week_key:
                del self.instrument_suspensions[instrument]

        if instrument in self.instrument_suspensions:
            return {
                "status": "SUSPENDED",
                "instrument": instrument,
                "reason": "weekly_loss_clamp_active",
            }

        # Allocator weighting
        weight = 1.0
        if self.step_count % WEEKLY_REBALANCE_INTERVAL == 0:
            alloc = self.allocator.rebalance_weekly(
                week_key="SIM-WEEK",
                ledger_snapshot=self.pnl_tracker.weekly_snapshot(),
            )
            weight = float(alloc.instrument_weights.get(instrument, 1.0))

        notional = 10000.0 * weight

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

        if decision["decision"]["final"] == "BLOCK":
            return {"status": "BLOCKED", "reason": decision.get("reason")}

        raw_pnl = self._simulate_pnl(instrument, step)

        pnl_after_costs = self.costs.apply_costs(
            instrument=instrument,
            notional=notional,
            raw_pnl=raw_pnl,
        )

        self.pnl_tracker.record_trade(
            instrument=instrument,
            realized_pnl=pnl_after_costs,
        )

        if self._check_weekly_clamp(instrument):
            return {
                "status": "SUSPENDED",
                "instrument": instrument,
                "reason": "weekly_loss_clamp_triggered",
            }

        return {
            "engine_run_id": self.engine_run_id,
            "step": step,
            "instrument": instrument,
            "raw_pnl": raw_pnl,
            "pnl_after_costs": pnl_after_costs,
            "notional": notional,
            "weight": weight,
            "equity": self.pnl_tracker.current_equity,
        }

    # --------------------------------------------------

    def run(self, steps: int = 200) -> None:

        print("==== INSTITUTIONAL SIMULATION (WITH FRICTION) ====")

        for i in range(steps):
            result = self.step(i)
            print(result)

        print("\n==== PNL TRACKER SUMMARY ====")
        print(self.pnl_tracker.equity_snapshot())
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
