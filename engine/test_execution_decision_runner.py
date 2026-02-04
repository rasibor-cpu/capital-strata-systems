"""
Phase-6 Execution Decision Runner (With Firewall)
=================================================

Purpose:
- Build GateInputs
- Evaluate all execution gates
- Enforce LIVE vs TEST execution firewall
- NEVER place real trades

This runner proves:
- Decision envelope correctness
- Firewall correctness
- Impossible-to-accidentally-trade guarantee
"""

from __future__ import annotations

import json
import os
import uuid

from engine.decision_builder import GateInputs, build_trade_execution_decision
from engine.gates_registry import get_configured_gates
from engine.execution_firewall import check_execution_firewall


def main() -> None:
    # ------------------------------------------------------------
    # Engine context
    # ------------------------------------------------------------
    engine_run_id = os.getenv("ENGINE_RUN_ID") or f"TEST-{uuid.uuid4()}"
    mode = os.getenv("ENGINE_MODE", "TEST")

    # ------------------------------------------------------------
    # Synthetic inputs (safe defaults)
    # ------------------------------------------------------------
    inputs = GateInputs(
        instrument="EURUSD",
        snapshot={
            "timestamp": "synthetic",
            "price": 1.1000,
            "vwap": 1.0995,
            "bars_5m": 52,
            "high_risk_news": False,
        },
        volatility={
            "vol_norm_0_1": 0.35,
            "current": 0.0012,
            "baseline": 0.0008,
            "ratio": 1.5,
        },
        liquidity={
            "spread_bps": 1.2,
            "spread": 0.0001,
            "mid": 1.1000,
            "depth": 5,
            "book_ok": True,
            "liquidity_score": 0.8,
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
            "daily_loss_pct": 0.0,
            "max_daily_loss_pct": 5.0,
        },
    )

    # ------------------------------------------------------------
    # Build decision envelope
    # ------------------------------------------------------------
    gates = get_configured_gates()
    decision = build_trade_execution_decision(
        engine_run_id=engine_run_id,
        mode=mode,
        inputs=inputs,
        gates=gates,
    )

    print("\n=== EXECUTION DECISION ENVELOPE ===")
    print(json.dumps(decision.as_dict(), indent=2))

    # ------------------------------------------------------------
    # FINAL FIREWALL
    # ------------------------------------------------------------
    firewall = check_execution_firewall(
        decision_allows_execution=decision.can_execute,
        engine_run_id=engine_run_id,
    )

    print("\n=== EXECUTION FIREWALL RESULT ===")
    print(json.dumps({
        "allowed": firewall.allowed,
        "mode": firewall.mode,
        "reason": firewall.reason,
        "audit": firewall.audit,
    }, indent=2))

    # ------------------------------------------------------------
    # Final status
    # ------------------------------------------------------------
    if firewall.allowed and firewall.mode == "LIVE":
        print("\n🔥 LIVE EXECUTION AUTHORIZED (INTENTIONALLY) 🔥")
    elif firewall.allowed:
        print("\n✅ TEST MODE — execution simulated only")
    else:
        print("\n⛔ EXECUTION BLOCKED BY FIREWALL")
        print("REASON:", firewall.reason)


if __name__ == "__main__":
    main()
