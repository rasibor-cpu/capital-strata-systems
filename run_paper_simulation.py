"""
Paper Simulation Runner (SAFE)
------------------------------
End-to-end SAFE simulation that routes through:

Signals → Arbitration → Regime Gate → Execution Gate → Paper Simulator

Rules:
- NEVER places live orders
- ExecutionGate remains authoritative (live execution disabled)
- PaperSimulator only runs when upstream gates allow a trade decision

Run:
  python run_paper_simulation.py
"""

import time

from engine.signals.signal_envelope import SignalEnvelopeBuilder
from engine.signals.signal_arbitrator import SignalArbitrator
from engine.regime.regime_gate import RegimeGate
from engine.execution.execution_gate import ExecutionGate
from engine.sim.paper_simulator import PaperSimulator


def main():
    instrument = "EURUSD"
    starting_equity = 100_000.0

    sim = PaperSimulator(starting_equity=starting_equity)

    # --- Synthetic market snapshot (replace later with replay feeds) ---
    price_now = 1.1000
    price_next = 1.1035  # synthetic favorable move

    # --- Build signals ---
    b = SignalEnvelopeBuilder(instrument=instrument)
    b.add_signal(
        name="price_feed",
        source="twelvedata",
        signal_type="price",
        value=0.30,
        confidence=0.80,
        meta={"note": "synthetic price bias"},
    )
    b.add_signal(
        name="bollinger_bias",
        source="indicators",
        signal_type="indicator",
        value=0.40,
        confidence=0.75,
        meta={"indicator": "bollinger"},
    )
    envelope = b.build()

    # --- Arbitration ---
    arb = SignalArbitrator.arbitrate(envelope)

    # --- Regime Gate ---
    regime = RegimeGate.evaluate(
        bars_5m=52,
        vol_norm_0_1=0.35,
        spread_bps=7.0,
        high_risk_news=False,
        extra={"instrument": instrument},
    )

    # --- Execution Gate (live execution disabled by design) ---
    now_ts = time.time()
    exec_decision = ExecutionGate.evaluate(
        now_ts=now_ts,
        execution_enabled=False,          # LIVE EXECUTION OFF
        equity=sim.state.equity,
        peak_equity=sim.state.peak_equity,
        current_equity=sim.state.equity,
        proposed_risk_amount=10_000.0,    # 10% risk (within cap)
        trades_today=0,
        open_positions=0,
        global_loss_streak=0,
        global_cooldown_until_ts=0.0,
        pair_loss_streak=0,
        has_human_override=False,
        override_confirmations=0,
        extra={"instrument": instrument},
    )

    print("\n=== PAPER SIMULATION RUN ===")
    print(f"Instrument: {instrument}")
    print(f"Equity start: {starting_equity}")

    print("\n[1] Arbitration")
    print(f"  allowed: {arb.allowed} | reason: {arb.reason}")

    print("\n[2] Regime Gate")
    print(f"  decision: {regime.decision} | reason: {regime.reason}")

    print("\n[3] Execution Gate")
    print(f"  decision: {exec_decision.decision} | reason: {exec_decision.reason}")

    # --- Paper trade decision ---
    if arb.allowed and regime.decision == "ALLOW":
        print("\n[4] Paper Simulator")
        trade = sim.simulate_trade(
            instrument=instrument,
            direction="LONG",
            entry_price=price_now,
            exit_price=price_next,
            size=100_000,  # notional units (demo)
            meta={
                "arb_reason": arb.reason,
                "regime": regime.reason,
                "execution_gate": exec_decision.reason,
            },
        )
        print(f"  Simulated trade PnL: {round(trade.pnl, 2)}")
    else:
        print("\n[4] Paper Simulator")
        print("  Trade skipped due to upstream gate")

    # --- Snapshot ---
    snap = sim.snapshot()
    print("\n[5] Simulator Snapshot")
    for k, v in snap.items():
        print(f"  {k}: {v}")

    print("\nNOTE: Live execution remains disabled. This is a SAFE simulation.\n")


if __name__ == "__main__":
    main()
