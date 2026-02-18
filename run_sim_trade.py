"""
run_sim_trade.py
================

Deterministic simulation runner that calls ExecutionGate.evaluate_trade()
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


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def main() -> int:
    print("=== CSS / REA SIM TRADE PROBE ===")
    print(f"UTC={_utc_now()}")

    from engine.execution.execution_gate import ExecutionGate  # type: ignore

    gate = ExecutionGate()

    # --- minimal context that AdaptiveCapital/Compounding typically needs ---
    # You can tune these later.
    payload = dict(
        instrument="EURUSD",
        side="BUY",
        notional=10000.0,
        stop_distance_pct=0.005,
        policy="core",

        # equity wiring (critical)
        equity=100000.0,
        equity_peak=100000.0,

        # optional risk context
        equity_risk=500.0,

        # regime/vol inputs (if gates use them)
        bars_5m=60,
        vol_norm_0_1=0.35,
        spread_bps=1.2,
        high_risk_news=False,

        # compounding / adaptive knobs (start conservative)
        regime_persistence=0.8,

        # hard safety
        live_allowed=False,
    )

    # Best-effort sync_context if present
    try:
        if hasattr(gate, "sync_context") and callable(getattr(gate, "sync_context")):
            gate.sync_context(
                day_key=datetime.now().strftime("%Y-%m-%d"),
                equity=payload["equity"],
                equity_peak=payload["equity_peak"],
                cooldown_active=False,
                regime=None,
                open_positions=0,
            )
    except Exception:
        pass

    try:
        out = gate.evaluate_trade(**payload)  # type: ignore[arg-type]
    except TypeError:
        # fallback if signature is strict
        out = gate.evaluate_trade(
            instrument=payload["instrument"],
            side=payload["side"],
            notional=payload["notional"],
            stop_distance_pct=payload["stop_distance_pct"],
            policy=payload["policy"],
        )
    except Exception as e:
        print("FATAL | evaluate_trade exception:", repr(e))
        return 2

    print("---- RESULT ----")
    try:
        print(json.dumps(out, indent=2, default=str))
    except Exception:
        print(out)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
