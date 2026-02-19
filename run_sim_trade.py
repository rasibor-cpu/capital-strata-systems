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

    # -------------------------------------
    # Simulated Inputs
    # -------------------------------------

    instrument = "EUR_USD"
    side = "BUY"
    notional = 100000.0
    stop_distance_pct = 0.01

    equity = 100000.0
    equity_peak = 100000.0

    regime_persistence = 0.65
    policy = "core"

    # -------------------------------------
    # Rebalance Activation Inputs
    # -------------------------------------

    # Target allocation model (example)
    rebalance_target_weights = {
        "EUR_USD": 0.40,
        "GBP_USD": 0.30,
        "USD_JPY": 0.30,
    }

    # Simulated current exposure (intentionally drifted)
    current_allocations = {
        "EUR_USD": 70000.0,
        "GBP_USD": 20000.0,
        "USD_JPY": 10000.0,
    }

    # Volatility + Regime States
    volatility_state = "HIGH"
    regime_state = "DEFENSIVE"

    # -------------------------------------
    # Gate Evaluation
    # -------------------------------------

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

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
