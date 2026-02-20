"""
run_sim_trade.py
================

Deterministic simulation runner that calls ExecutionGate.evaluate_trade
with fully-specified inputs so we can see the true gating chain.

SAFE:
- No broker calls
- No live execution
- Pure local gate evaluation

Usage:
    python -u run_sim_trade.py
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

from engine.execution.execution_gate import ExecutionGate


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def main() -> int:
    print("=== CSS / REA SIM TRADE PROBE ===")
    print(f"UTC={_utc_now()}")

    gate = ExecutionGate()

    instrument = "EUR_USD"
    side = "BUY"
    notional = 100000.0
    stop_distance_pct = 0.01

    equity = 100000.0
    equity_peak = 100000.0

    regime_persistence = 0.65
    policy = "core"

    rebalance_target_weights = {
        "EUR_USD": 0.40,
        "GBP_USD": 0.30,
        "USD_JPY": 0.30,
    }

    current_allocations = {
        "EUR_USD": 70000.0,
        "GBP_USD": 20000.0,
        "USD_JPY": 10000.0,
    }

    volatility_state = "HIGH"
    regime_state = "DEFENSIVE"

    decision = gate.evaluate_trade(
        instrument=instrument,
        side=side,
        notional=notional,
        stop_distance_pct=stop_distance_pct,
        equity=equity,
        equity_peak=equity_peak,
        regime_persistence=regime_persistence,
        policy=policy,
        current_allocations=current_allocations,
        rebalance_target_weights=rebalance_target_weights,
        volatility_state=volatility_state,
        regime_state=regime_state,
    )

    print("\n--- DECISION ---")
    print(json.dumps(decision, indent=2))

    # ---------------------------------------------------------
    # Post-ALLOW: simulate a completed trade + record PnL lines
    # ---------------------------------------------------------
    if decision.get("decision", {}).get("final") == "ALLOW":
        pnl = 250.0
        print(f"\n--- SIMULATED CLOSE ---\nrecord_trade_outcome(pnl={pnl}, instrument={instrument})")

        try:
            gate.risk_governor.record_trade_outcome(pnl, instrument=instrument)
            snap = gate.risk_governor.ledger.snapshot()
            print("\n--- LEDGER SNAPSHOT ---")
            print(json.dumps(snap, indent=2))
        except Exception as e:
            print("\n--- LEDGER SNAPSHOT ---")
            print(f"FAILED: {e}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
