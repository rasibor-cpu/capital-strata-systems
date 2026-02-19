"""
EngineLoop – Canonical Capital Execution Loop
Capital Strata Systems

Now includes:
- EquityAuthority (single equity source of truth)
- PnLTracker (multi-instrument, multi-timeframe PnL)
- RiskTelemetry
- PerformanceLedger
- Weekly AssetAllocator (50% intensity)
- Hard kill-switch

Key rule:
- EngineLoop must NOT maintain shadow equity state.
  Equity is owned by PnLTracker and exposed via EquityAuthority.
"""

from __future__ import annotations

import uuid
from typing import Dict, Any, Optional

from engine.execution.execution_gate import ExecutionGate
from engine.risk.risk_telemetry import RiskTelemetry
from engine.performance.performance_ledger import PerformanceLedger
from engine.allocation.asset_allocator import AssetAllocator

from engine.performance.pnl_tracker import PnLTracker
from engine.equity_authority import EquityAuthority
from engine.risk.risk_governor import RiskGovernor


class EngineLoop:

    WEEKLY_REBALANCE_INTERVAL = 10  # simulate weekly every 10 steps

    def __init__(self) -> None:
        self.engine_run_id = f"css-{uuid.uuid4()}"

        # --- Capital state (authoritative) ---
        self.tracker = PnLTracker(starting_equity=100000.0)
        self.equity_authority = EquityAuthority()
        self.equity_authority.bind_tracker(self.tracker)

        # --- Core components ---
        self.gate = ExecutionGate()
        self.telemetry = RiskTelemetry()
        self.ledger = PerformanceLedger()
        self.allocator = AssetAllocator(intensity=0.5)

        # --- Risk governor (bound to authority + tracker) ---
        # Even if ExecutionGate uses its own governor internally,
        # we still bind this instance for canonical usage and future injection.
        self.risk_governor = RiskGovernor(
            equity_authority=self.equity_authority,
            pnl_tracker=self.tracker,
        )

        self.step_count = 0

        # seed telemetry from authoritative equity
        self.telemetry.update_equity(self.equity_authority.current_equity())

    # --------------------------------------------------

    def _simulate_pnl(self, step: int) -> float:
        # Deterministic pattern for testing
        pattern = [800, 900, 1000, -2500, 900, 1000, -1500, 800, 900, 1000]
        return float(pattern[step % len(pattern)])

    # --------------------------------------------------

    def step(self, step: int) -> Dict[str, Any]:

        self.step_count += 1

        # Kill switch (telemetry-owned). Telemetry currently reads equity updates we feed it.
        if self.telemetry.kill_switch_triggered:
            return {
                "status": "HALTED",
                "reason": "hard_drawdown_limit_triggered",
                "drawdown_pct": self.telemetry._compute_drawdown_pct(),
            }

        regime_strength = 0.85

        # Use authoritative equity values
        equity = self.equity_authority.current_equity()
        equity_peak = self.equity_authority.peak_equity()

        decision = self.gate.evaluate_trade(
            instrument="EUR_USD",
            side="BUY",
            notional=10000.0,
            stop_distance_pct=0.01,
            equity=equity,
            equity_peak=equity_peak,
            regime_persistence=regime_strength,
        )

        pnl = self._simulate_pnl(step)

        # Record PnL in authoritative tracker (updates equity)
        self.tracker.record_trade(
            instrument="EUR_USD",
            realized_pnl=pnl,
            unrealized_pnl=0.0,
        )

        # Inform governor about completed outcome (for loss-streak compression)
        # (uses tracker journal when instrument is supplied)
        self.risk_governor.record_trade_outcome(
            pnl,
            instrument="EUR_USD",
        )

        # Update telemetry from authoritative equity
        self.telemetry.update_equity(self.equity_authority.current_equity())

        # Record PnL in existing ledger (kept for allocator compatibility for now)
        self.ledger.record_trade(
            instrument="EUR_USD",
            asset_class="FX",
            pnl=pnl,
        )

        # -------------------------
        # WEEKLY REBALANCE TRIGGER
        # -------------------------

        allocation_snapshot: Optional[Dict[str, Any]] = None

        if self.step_count % self.WEEKLY_REBALANCE_INTERVAL == 0:
            allocation_snapshot = self.allocator.rebalance(
                performance_snapshot=self.ledger.snapshot()
            )

        snapshot = self.telemetry.snapshot(
            effective_risk_pct=0.01,
            compounding_applied=decision.get("decision", {}).get("compounding", {}).get("applied", False),
            regime_persistence=regime_strength,
        )

        return {
            "engine_run_id": self.engine_run_id,
            "step": step,
            "pnl": pnl,
            "decision": decision,
            "equity": self.equity_authority.current_equity(),
            "telemetry": snapshot.as_dict(),
            "rebalance": allocation_snapshot,
        }

    # --------------------------------------------------

    def run(self, steps: int = 20) -> None:

        print("==== WEEKLY REBALANCE SIMULATION ====")

        for i in range(steps):
            result = self.step(i)
            print(result)

            if result.get("status") == "HALTED":
                print("⚠️ ENGINE HALTED")
                break

        print("\n==== LEDGER SUMMARY ====")
        print(self.ledger.snapshot())

        print("\n==== PNL TRACKER SUMMARY ====")
        print(self.tracker.equity_snapshot())
        print(self.tracker.instrument_summary())

        print("\n==== RUN SUMMARY ====")
        print(f"engine_run_id: {self.engine_run_id}")
        print(f"steps: {self.step_count}")


def main() -> int:
    loop = EngineLoop()
    loop.run(steps=20)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
