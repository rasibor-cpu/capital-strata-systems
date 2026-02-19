"""
EngineLoop – Multi-Pair Controlled Paper Mode
Capital Strata Systems

Phase C – Realistic FX Rotation (Controlled)

Features:
- 5-pair FX universe
- Instrument-specific stop distances
- Allocator weight applied to notional
- Authority-native execution
- PnLTracker driven allocation
- Weekly rebalance enforcement
"""

from __future__ import annotations

import uuid
from typing import Dict, Any, Optional

from engine.execution.execution_gate import ExecutionGate
from engine.risk.risk_telemetry import RiskTelemetry
from engine.allocation.asset_allocator import AssetAllocator

from engine.performance.pnl_tracker import PnLTracker
from engine.equity_authority import EquityAuthority
from engine.risk.risk_governor import RiskGovernor


class EngineLoop:

    WEEKLY_REBALANCE_INTERVAL = 10

    FX_UNIVERSE = [
        "EUR_USD",
        "GBP_USD",
        "USD_JPY",
        "AUD_USD",
        "USD_CHF",
    ]

    # Instrument-specific stop distances
    STOP_MAP = {
        "EUR_USD": 0.010,   # 1.0%
        "GBP_USD": 0.012,   # 1.2%
        "USD_JPY": 0.009,   # 0.9%
        "AUD_USD": 0.011,   # 1.1%
        "USD_CHF": 0.008,   # 0.8%
    }

    def __init__(self) -> None:

        self.engine_run_id = f"css-{uuid.uuid4()}"

        # --------------------------------------------------
        # AUTHORITATIVE CAPITAL SPINE
        # --------------------------------------------------
        self.tracker = PnLTracker(starting_equity=100000.0)

        self.equity_authority = EquityAuthority()
        self.equity_authority.bind_tracker(self.tracker)

        self.risk_governor = RiskGovernor(
            equity_authority=self.equity_authority,
            pnl_tracker=self.tracker,
        )

        self.gate = ExecutionGate(
            risk_governor=self.risk_governor,
            equity_authority=self.equity_authority,
        )

        # --------------------------------------------------
        # SYSTEM COMPONENTS
        # --------------------------------------------------
        self.telemetry = RiskTelemetry()
        self.allocator = AssetAllocator(intensity=0.5)

        self.step_count = 0
        self.last_allocation: Dict[str, float] = {}

        self.telemetry.update_equity(
            self.equity_authority.current_equity()
        )

    # --------------------------------------------------
    # Instrument-specific deterministic PnL profiles
    # --------------------------------------------------

    def _simulate_pnl(self, instrument: str, step: int) -> float:

        profiles = {
            "EUR_USD": [600, 700, 800, -900, 700],
            "GBP_USD": [900, -1200, 1100, -1500, 1300],
            "USD_JPY": [400, -300, 350, -250, 300],
            "AUD_USD": [700, 800, -1000, 900, -800],
            "USD_CHF": [300, 350, -400, 320, -280],
        }

        series = profiles[instrument]
        return float(series[step % len(series)])

    # --------------------------------------------------

    def step(self, step: int) -> Dict[str, Any]:

        self.step_count += 1

        if self.telemetry.kill_switch_triggered:
            return {
                "status": "HALTED",
                "reason": "hard_drawdown_limit_triggered",
                "drawdown_pct": self.telemetry._compute_drawdown_pct(),
            }

        regime_strength = 0.85

        # --------------------------------------------------
        # ROTATE INSTRUMENT
        # --------------------------------------------------
        instrument = self.FX_UNIVERSE[step % len(self.FX_UNIVERSE)]

        stop_distance_pct = self.STOP_MAP[instrument]

        # --------------------------------------------------
        # APPLY ALLOCATOR WEIGHT
        # --------------------------------------------------
        base_notional = 10000.0
        weight = self.last_allocation.get(instrument, 1.0)
        weighted_notional = base_notional * weight

        # --------------------------------------------------
        # TRADE DECISION
        # --------------------------------------------------
        decision = self.gate.evaluate_trade(
            instrument=instrument,
            side="BUY",
            notional=weighted_notional,
            stop_distance_pct=stop_distance_pct,
            regime_persistence=regime_strength,
        )

        # --------------------------------------------------
        # SIMULATED EXECUTION
        # --------------------------------------------------
        pnl = self._simulate_pnl(instrument, step)

        self.tracker.record_trade(
            instrument=instrument,
            realized_pnl=pnl,
            unrealized_pnl=0.0,
        )

        self.risk_governor.record_trade_outcome(
            pnl,
            instrument=instrument,
        )

        self.telemetry.update_equity(
            self.equity_authority.current_equity()
        )

        # --------------------------------------------------
        # WEEKLY REBALANCE
        # --------------------------------------------------
        allocation_snapshot: Optional[Dict[str, Any]] = None

        if self.step_count % self.WEEKLY_REBALANCE_INTERVAL == 0:

            week_key = "SIM-WEEK"

            allocation_result = self.allocator.rebalance_weekly(
                week_key=week_key,
                ledger_snapshot=self.tracker.weekly_snapshot(),
            )

            allocation_snapshot = allocation_result.as_dict()

            # store instrument weights
            self.last_allocation = allocation_snapshot.get(
                "instrument_weights", {}
            )

        snapshot = self.telemetry.snapshot(
            effective_risk_pct=0.01,
            compounding_applied=decision.get("decision", {}).get("compounding", {}).get("applied", False),
            regime_persistence=regime_strength,
        )

        return {
            "engine_run_id": self.engine_run_id,
            "step": step,
            "instrument": instrument,
            "pnl": pnl,
            "weighted_notional": weighted_notional,
            "decision": decision,
            "equity": self.equity_authority.current_equity(),
            "telemetry": snapshot.as_dict(),
            "rebalance": allocation_snapshot,
        }

    # --------------------------------------------------

    def run(self, steps: int = 25) -> None:

        print("==== MULTI-PAIR FX SIMULATION ====")

        for i in range(steps):
            result = self.step(i)
            print(result)

            if result.get("status") == "HALTED":
                print("⚠️ ENGINE HALTED")
                break

        print("\n==== PNL TRACKER SUMMARY ====")
        print(self.tracker.equity_snapshot())
        print(self.tracker.instrument_summary())

        print("\n==== RUN SUMMARY ====")
        print(f"engine_run_id: {self.engine_run_id}")
        print(f"steps: {self.step_count}")


def main() -> int:
    loop = EngineLoop()
    loop.run(steps=25)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
