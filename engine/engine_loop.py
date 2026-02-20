"""
engine/engine_loop.py

Canonical Institutional Engine Loop v3
Capital Strata Systems (CSS)

Upgrades:
- Surfaces ExecutionGate debug payload
- Clean diagnostic output
- Self-governing capital tilt engine
- Weekly clamp enforcement
"""

from __future__ import annotations

import uuid
from typing import Dict, Any
from datetime import datetime, timezone

from engine.execution.execution_gate import ExecutionGate
from engine.execution.execution_cost_engine import ExecutionCostEngine
from engine.performance.pnl_tracker import PnLTracker
from engine.core.rebalancer import Rebalancer


WEEKLY_REBALANCE_INTERVAL = 20
WEEKLY_INSTRUMENT_CLAMP_PCT = 0.05


class EngineLoop:

    def __init__(self) -> None:
        self.engine_run_id = f"css-{uuid.uuid4()}"
        self.equity_start = 100000.0

        self.pnl_tracker = PnLTracker(self.equity_start)
        self.gate = ExecutionGate()
        self.costs = ExecutionCostEngine(deterministic=True)
        self.rebalancer = Rebalancer()

        self.step_count = 0
        self.instrument_suspensions: Dict[str, str] = {}

        self.instruments = [
            "EUR_USD",
            "GBP_USD",
            "USD_JPY",
            "AUD_USD",
            "USD_CHF",
        ]

        equal_weight = 1.0 / len(self.instruments)
        self.capital_weights = {inst: equal_weight for inst in self.instruments}

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
        if not snapshot:
            return False

        instrument_perf = snapshot.get("instrument_performance", {})
        pnl = float(instrument_perf.get(instrument, {}).get("net_pnl", 0.0))

        clamp_threshold = -self.equity_start * WEEKLY_INSTRUMENT_CLAMP_PCT

        if pnl <= clamp_threshold:
            self.instrument_suspensions[instrument] = self._current_week_key()
            return True

        return False

    # --------------------------------------------------

    def _rebalance_if_needed(self):

        if self.step_count % WEEKLY_REBALANCE_INTERVAL != 0:
            return

        signal = self.pnl_tracker.rebalancing_signal()
        adjustments = self.rebalancer.generate_adjustments(signal)

        self.capital_weights = self.rebalancer.apply_adjustments(
            current_weights=self.capital_weights,
            adjustments=adjustments,
        )

        print("\n==== WEEKLY REBALANCE EVENT ====")
        print("Signal:", signal)
        print("Adjustments:", adjustments)
        print("New Weights:", self.capital_weights)
        print("================================\n")

    # --------------------------------------------------

    def step(self, step: int) -> Dict[str, Any]:

        self.step_count += 1

        instrument = self.instruments[step % len(self.instruments)]
        week_key = self._current_week_key()

        if instrument in self.instrument_suspensions:
            if self.instrument_suspensions[instrument] != week_key:
                del self.instrument_suspensions[instrument]

        if instrument in self.instrument_suspensions:
            return {
                "status": "SUSPENDED",
                "instrument": instrument,
                "reason": "weekly_loss_clamp_active",
            }

        self._rebalance_if_needed()

        weight = float(self.capital_weights.get(instrument, 1.0))
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

        # 🔥 FULL DEBUG SURFACE
        if decision["decision"]["final"] == "BLOCK":
            return {
                "status": "BLOCKED",
                "reason": decision.get("reason"),
                "debug": decision.get("debug"),
            }

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

        print("==== INSTITUTIONAL SIMULATION (DIAGNOSTIC MODE) ====")

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