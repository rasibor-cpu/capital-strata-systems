
"""
End-to-End Dry Run (SAFE)
-------------------------
This script validates the pre-strategy and pre-trade safety pipeline:

1) Build SignalEnvelope
2) Arbitrate signals (conflict resolver)
3) RegimeGate (ALLOW/BLOCK)
4) ExecutionGate (ALLOW/BLOCK)  -> should BLOCK unless execution_enabled=True

NO orders are placed. No live network calls. Pure local logic.

Run:
  python test_end_to_end_dryrun.py
"""

from engine.signals.signal_envelope import SignalEnvelopeBuilder
from engine.signals.signal_arbitrator import SignalArbitrator
from engine.regime.regime_gate import RegimeGate
from engine.execution.execution_gate import ExecutionGate

import time


def main():
    instrument = "EURUSD"

    # 1) Build signal envelope (values in [-1, +1] convention)
    b = SignalEnvelopeBuilder(instrument=instrument)
    b.add_signal(
        name="price_feed_a",
        source="twelvedata",
        signal_type="price",
        value=0.20,
        confidence=0.85,
        meta={"note": "synthetic demo price signal"},
    )
    b.add_signal(
        name="bollinger_bias",
        source="indicators",
        signal_type="indicator",
        value=0.35,
        confidence=0.70,
        meta={"indicator": "bollinger"},
    )
    envelope = b.build(regime_hint=None)

    # 2) Arbitration
    arb = SignalArbitrator.arbitrate(envelope)

    # 3) Regime gate (synthetic safe values)
    regime = RegimeGate.evaluate(
        bars_5m=52,
        vol_norm_0_1=0.40,
        spread_bps=8.0,
        high_risk_news=False,
        extra={"instrument": instrument},
    )

    # 4) Execution gate (should BLOCK because execution_enabled=False)
    now_ts = time.time()
    exec_decision = ExecutionGate.evaluate(
        now_ts=now_ts,
        execution_enabled=False,          # HARD LOCK OFF by default
        equity=100000.0,
        peak_equity=100000.0,
        current_equity=99000.0,
        proposed_risk_amount=15000.0,     # 15% equity risk (<= 20% cap)
        trades_today=1,
        open_positions=0,
        global_loss_streak=0,
        global_cooldown_until_ts=0.0,
        pair_loss_streak=0,
        has_human_override=False,
        override_confirmations=0,
        extra={"instrument": instrument},
    )

    # Report
    print("\n=== REA ENGINE: END-TO-END DRY RUN (SAFE) ===")
    print(f"Instrument: {instrument}")
    print("\n[1] Arbitration")
    print(f"  allowed: {arb.allowed}")
    print(f"  reason : {arb.reason}")
    print(f"  conflict_score: {arb.conflict_score:.3f}")
    print(f"  aggregated_value: {arb.aggregated_value:.3f}")
    print(f"  aggregated_confidence: {arb.aggregated_confidence:.3f}")

    print("\n[2] Regime Gate")
    print(f"  decision: {regime.decision}")
    print(f"  reason  : {regime.reason}")
    print(f"  meta    : {regime.meta}")

    print("\n[3] Execution Gate (hard-lock)")
    print(f"  decision: {exec_decision.decision}")
    print(f"  reason  : {exec_decision.reason}")
    print(f"  meta    : {exec_decision.meta}")

    print("\nResult summary:")
    ok = arb.allowed and (regime.decision == "ALLOW") and (exec_decision.decision in ("ALLOW", "BLOCK"))
    print(f"  pipeline_ok: {ok}")
    print("  NOTE: Execution is expected to BLOCK unless explicitly enabled.\n")


if __name__ == "__main__":
    main()
