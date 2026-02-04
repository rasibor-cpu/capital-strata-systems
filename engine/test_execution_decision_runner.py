"""
Phase-1 Execution Decision Test Runner
======================================

Purpose:
- Build GateInputs with the minimum fields required by the regime gate
- Load configured gates
- Produce a single ExecutionDecision envelope
- Print decision in a human-readable form

RULE:
- This file NEVER places trades
- Safe for TEST mode
"""

from __future__ import annotations

import json
import os
import uuid

from engine.decision_builder import (
    GateInputs,
    build_trade_execution_decision,
)
from engine.gates_registry import get_configured_gates


def main() -> None:
    # ------------------------------------------------------------------
    # Engine context (SAFE defaults)
    # ------------------------------------------------------------------
    engine_run_id = os.getenv("ENGINE_RUN_ID") or f"TEST-{uuid.uuid4()}"
    mode = os.getenv("ENGINE_MODE", "TEST")

    # ------------------------------------------------------------------
    # Minimal synthetic inputs (safe placeholders)
    #
    # IMPORTANT:
    # - regime gate requires bars_5m (int)
    # - optional: vol_norm_0_1, spread_bps, high_risk_news
    # ------------------------------------------------------------------
    inputs = GateInputs(
        instrument="EURUSD",
        snapshot={
            "timestamp": "synthetic",
            "price": 1.1000,
            "vwap": 1.0995,

            # REQUIRED by RegimeGate().evaluate(...)
            "bars_5m": 52,

            # Optional (regime-related)
            "high_risk_news": False,
        },
        volatility={
            # Optional: RegimeGate expects vol_norm_0_1 (0..1 normalized)
            "vol_norm_0_1": 0.35,

            # Extra placeholders (ok if unused)
            "current": 0.0012,
            "baseline": 0.0008,
            "ratio": 1.5,
        },
        liquidity={
            # Optional: RegimeGate expects spread_bps
            "spread_bps": 1.2,

            # Extra placeholders (ok if unused)
            "spread": 0.0001,
            "mid": 1.1000,
            "depth": "OK",
        },
        slippage={
            "expected": 0.00005,
            "max_allowed": 0.0002,
        },
        risk={
            "equity": 100_000,
            "risk_pct": 2.0,
            "loss_streak": 0,
            "max_loss_streak": 5,
        },
    )

    # ------------------------------------------------------------------
    # Load gates + build decision
    # ------------------------------------------------------------------
    gates = get_configured_gates()

    decision = build_trade_execution_decision(
        engine_run_id=engine_run_id,
        mode=mode,
        inputs=inputs,
        gates=gates,
    )

    # ------------------------------------------------------------------
    # Output
    # ------------------------------------------------------------------
    print("\n=== EXECUTION DECISION ENVELOPE ===")
    print(json.dumps(decision.as_dict(), indent=2))
    print("=================================\n")

    if decision.can_execute:
        print("STATUS: ✅ EXECUTION WOULD BE ALLOWED (TEST MODE ONLY)")
    else:
        print("STATUS: ⛔ EXECUTION BLOCKED")
        print("PRIMARY REASON:", decision.primary_reason)


if __name__ == "__main__":
    main()
