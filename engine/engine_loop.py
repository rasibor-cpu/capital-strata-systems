"""
engine/engine_loop.py

Canonical Institutional Engine Loop v6
Signal-driven + Multi-bar hold model
"""

from __future__ import annotations

import uuid
from typing import Dict, Any
from datetime import datetime, timezone

from engine.execution.execution_gate import ExecutionGate
from engine.execution.execution_cost_engine import ExecutionCostEngine
from engine.performance.pnl_tracker import PnLTracker
from engine.core.position_book import PositionBook
from engine.strategy.behaviour_mapper import get_profile_for_behaviour
from engine.strategy.signal_engine import SignalEngine


WEEKLY_INSTRUMENT_CLAMP_PCT = 0.05


class EngineLoop:

    def __init__(self, behaviour: str = "C") -> None:

        self.engine_run_id = f"css-{uuid.uuid4()}"
        self.equity_start = 100000.0

        self.pnl_tracker = PnLTracker(self.equity_start)
        self.gate = ExecutionGate()
        self.costs = ExecutionCostEngine(deterministic=True)
        self.position_book = PositionBook()

        self.profile = get_profile_for_behaviour(behaviour)
        self.signal_engine = SignalEngine(self.profile)

        self.step_count = 0
        self.instrument_suspensions: Dict[str, str] = {}

        self.instruments = [
            "EUR_USD",
            "GBP_USD",
            "USD_JPY",
            "AUD_USD",
            "USD_CHF",
        ]

    # --------------------------------------------------

    def _synthetic_price(self, instrument: str, step: int) -> float:
        base = {
            "EUR_USD": 1.10,
            "GBP_USD": 1.30,
            "USD_JPY": 110.0,
            "AUD_USD": 0.70,
            "USD_CHF": 0.90,
        }
        return base[instrument] + (step % 5) * 0.001

    # --------------------------------------------------

    def _check_weekly_clamp(self, instrument: str) -> bool:

        snapshot = self.pnl_tracker.weekly_snapshot()
        if not snapshot:
            return False

        inst_totals = snapshot.get("weekly_instrument_totals", {})
        pnl = float(inst_totals.get(instrument, 0.0))

        clamp_threshold = -self.equity_start * WEEKLY_INSTRUMENT_CLAMP_PCT

        if pnl <= clamp_threshold:
            return True

        return False

    # --------------------------------------------------

    def step(self, step: int) -> Dict[str, Any]:

        self.step_count += 1
        instrument = self.instruments[step % len(self.instruments)]

        price_now = self._synthetic_price(instrument, step)
        price_prev = self._synthetic_price(instrument, step - 1)
        moving_avg = self._synthetic_price(instrument, step - 3)

        # --------------------------------------------------
        # First evaluate exit on existing position
        # --------------------------------------------------

        realized_exit_pnl = self.position_book.evaluate_exit(
            instrument=instrument,
            current_price=price_now,
            current_step=step,
        )

        if realized_exit_pnl != 0.0:
            pnl_after_costs = self.costs.apply_costs(
                instrument=instrument,
                notional=10000.0,
                raw_pnl=realized_exit_pnl,
            )

            self.pnl_tracker.record_trade(
                instrument=instrument,
                realized_pnl=pnl_after_costs,
            )

        # --------------------------------------------------
        # Generate new signal
        # --------------------------------------------------

        signal = self.signal_engine.generate(
            instrument=instrument,
            price_now=price_now,
            price_prev=price_prev,
            moving_avg=moving_avg,
        )

        # --------------------------------------------------
        # Open new position only if none exists
        # --------------------------------------------------

        if (
            signal.direction != "FLAT"
            and not self.position_book.has_position(instrument)
            and not self._check_weekly_clamp(instrument)
        ):

            notional = 10000.0 * signal.strength

            equity = self.pnl_tracker.current_equity
            equity_peak = self.pnl_tracker.peak_equity

            decision = self.gate.evaluate_trade(
                instrument=instrument,
                side=signal.direction,
                notional=notional,
                stop_distance_pct=0.01,
                equity=equity,
                equity_peak=equity_peak,
                regime_persistence=0.85,
            )

            if decision["decision"]["final"] == "ALLOW":

                size = notional / price_now

                self.position_book.open_position(
                    instrument=instrument,
                    side=signal.direction,
                    size=size,
                    price=price_now,
                    step=step,
                    stop_distance_pct=0.002,
                    take_profit_pct=0.004,
                    max_hold_steps=4,
                )

        return {
            "step": step,
            "instrument": instrument,
            "price": price_now,
            "equity": self.pnl_tracker.current_equity,
            "open_positions": self.position_book.summary(),
        }

    # --------------------------------------------------

    def run(self, steps: int = 200) -> None:

        print("==== SIGNAL + HOLD SIMULATION ====")
        print("Behaviour:", self.profile.name)

        for i in range(steps):
            print(self.step(i))

        print("\n==== FINAL EQUITY SNAPSHOT ====")
        print(self.pnl_tracker.equity_snapshot())

        print("\n==== INSTRUMENT SUMMARY ====")
        print(self.pnl_tracker.instrument_summary())

        print("\n==== RUN SUMMARY ====")
        print("engine_run_id:", self.engine_run_id)
        print("steps:", self.step_count)
        print("\n==== COMPLETE ====")


def main() -> int:
    loop = EngineLoop(behaviour="C")
    loop.run(steps=200)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())