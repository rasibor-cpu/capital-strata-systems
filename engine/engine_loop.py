"""
engine/engine_loop.py

Canonical Institutional Engine Loop v7
Signal-driven + Multi-bar hold model (correct exit sweep)

Key Fix:
- Evaluate exits for ALL open positions every step

Inspection mode:
- Prints signal strength so we can calibrate MIN_SIGNAL_STRENGTH safely.
"""

from __future__ import annotations

import uuid
from typing import Dict, Any, List

from engine.execution.execution_gate import ExecutionGate
from engine.execution.execution_cost_engine import ExecutionCostEngine
from engine.performance.pnl_tracker import PnLTracker
from engine.core.position_book import PositionBook
from engine.strategy.behaviour_mapper import get_profile_for_behaviour
from engine.strategy.signal_engine import SignalEngine


WEEKLY_INSTRUMENT_CLAMP_PCT = 0.05

# INSPECTION: allow all strengths so we can observe distribution
MIN_SIGNAL_STRENGTH = 0.0


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

        # Diagnostics for tuning
        self.skipped_weak_signals = 0
        self.attempted_entries = 0
        self.opened_entries = 0

        self.instruments: List[str] = [
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
        # slightly wider band than before
        return base[instrument] + ((step % 11) - 5) * 0.001

    # --------------------------------------------------

    def _check_weekly_clamp(self, instrument: str) -> bool:
        snapshot = self.pnl_tracker.weekly_snapshot()
        if not snapshot:
            return False
        inst_totals = snapshot.get("weekly_instrument_totals", {})
        pnl = float(inst_totals.get(instrument, 0.0))
        clamp_threshold = -self.equity_start * WEEKLY_INSTRUMENT_CLAMP_PCT
        return pnl <= clamp_threshold

    # --------------------------------------------------

    def _exit_sweep(self, step: int) -> Dict[str, float]:
        """
        Evaluate exits for ALL open positions.
        Returns realized_pnl per instrument for those that closed.
        """
        realized: Dict[str, float] = {}

        # Build current price map
        prices = {inst: self._synthetic_price(inst, step) for inst in self.instruments}

        # Copy keys (because we may delete positions during loop)
        open_insts = list(self.position_book.positions.keys())

        for inst in open_insts:
            pnl = self.position_book.evaluate_exit(
                instrument=inst,
                current_price=prices.get(inst, 0.0),
                current_step=step,
            )
            if pnl != 0.0:
                realized[inst] = pnl

        return realized

    # --------------------------------------------------

    def step(self, step: int) -> Dict[str, Any]:

        self.step_count += 1

        # 1) Exit sweep (ALL positions)
        closed = self._exit_sweep(step)

        for inst, raw_pnl in closed.items():
            pnl_after_costs = self.costs.apply_costs(
                instrument=inst,
                notional=10000.0,
                raw_pnl=raw_pnl,
            )
            self.pnl_tracker.record_trade(instrument=inst, realized_pnl=pnl_after_costs)

        # 2) Choose one instrument to consider for entry this step
        instrument = self.instruments[step % len(self.instruments)]
        price_now = self._synthetic_price(instrument, step)
        price_prev = self._synthetic_price(instrument, step - 1)
        moving_avg = self._synthetic_price(instrument, step - 3)

        signal = self.signal_engine.generate(
            instrument=instrument,
            price_now=price_now,
            price_prev=price_prev,
            moving_avg=moving_avg,
        )

        strength = float(signal.strength)

        # 3) Open if allowed
        opened = False

        # Quality filter (currently disabled for inspection unless you set MIN_SIGNAL_STRENGTH > 0)
        if signal.direction != "FLAT" and strength < float(MIN_SIGNAL_STRENGTH):
            self.skipped_weak_signals += 1
            return {
                "step": step,
                "instrument": instrument,
                "signal": signal.direction,
                "strength": strength,
                "opened": False,
                "closed": closed,
                "equity": self.pnl_tracker.current_equity,
                "open_positions": self.position_book.summary(),
                "skipped_weak_signals": self.skipped_weak_signals,
            }

        if (
            signal.direction != "FLAT"
            and not self.position_book.has_position(instrument)
            and not self._check_weekly_clamp(instrument)
        ):
            self.attempted_entries += 1

            notional = 10000.0 * strength

            decision = self.gate.evaluate_trade(
                instrument=instrument,
                side=signal.direction,
                notional=notional,
                stop_distance_pct=0.002,
                equity=self.pnl_tracker.current_equity,
                equity_peak=self.pnl_tracker.peak_equity,
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
                opened = True
                self.opened_entries += 1

        return {
            "step": step,
            "instrument": instrument,
            "signal": signal.direction,
            "strength": strength,
            "opened": opened,
            "closed": closed,
            "equity": self.pnl_tracker.current_equity,
            "open_positions": self.position_book.summary(),
            "skipped_weak_signals": self.skipped_weak_signals,
            "attempted_entries": self.attempted_entries,
            "opened_entries": self.opened_entries,
        }

    # --------------------------------------------------

    def run(self, steps: int = 200) -> None:

        print("==== SIGNAL + HOLD SIMULATION (EXIT SWEEP) ====")
        print("Behaviour:", self.profile.name)
        print("MIN_SIGNAL_STRENGTH:", MIN_SIGNAL_STRENGTH)

        for i in range(steps):
            print(self.step(i))

        print("\n==== FINAL EQUITY SNAPSHOT ====")
        print(self.pnl_tracker.equity_snapshot())

        print("\n==== INSTRUMENT SUMMARY ====")
        print(self.pnl_tracker.instrument_summary())

        print("\n==== RUN SUMMARY ====")
        print("engine_run_id:", self.engine_run_id)
        print("steps:", self.step_count)
        print("skipped_weak_signals:", self.skipped_weak_signals)
        print("attempted_entries:", self.attempted_entries)
        print("opened_entries:", self.opened_entries)
        print("\n==== COMPLETE ====")


def main() -> int:
    loop = EngineLoop(behaviour="C")
    loop.run(steps=200)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())