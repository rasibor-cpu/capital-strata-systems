"""
Replay Mode (CSV) - SAFE
------------------------
Deterministic replay runner that reads a simple CSV and simulates paper trades.

CSV format (minimum):
  timestamp,price
Where:
  - timestamp: string (kept for logs)
  - price: float

This runner:
- Iterates prices
- Creates a simple synthetic signal (momentum placeholder)
- Runs: Envelope → Arbitration → RegimeGate → ExecutionGate (OFF) → PaperSimulator
- Prints MetricsReport at end

Run:
  python run_replay_from_csv.py path\to\prices.csv

NOTE:
- No live network calls
- No execution
"""

import csv
import sys
import time
from typing import List, Tuple

from engine.signals.signal_envelope import SignalEnvelopeBuilder
from engine.signals.signal_arbitrator import SignalArbitrator
from engine.regime.regime_gate import RegimeGate
from engine.execution.execution_gate import ExecutionGate
from engine.sim.paper_simulator import PaperSimulator
from engine.sim.metrics import metrics_from_simulator


def load_prices(path: str) -> List[Tuple[str, float]]:
    rows: List[Tuple[str, float]] = []
    with open(path, "r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        if "timestamp" not in reader.fieldnames or "price" not in reader.fieldnames:
            raise ValueError("CSV must have headers: timestamp,price")
        for r in reader:
            ts = str(r["timestamp"])
            px = float(r["price"])
            rows.append((ts, px))
    if len(rows) < 3:
        raise ValueError("CSV must contain at least 3 rows")
    return rows


def momentum_signal(prev_px: float, px: float) -> float:
    """
    Placeholder signal in [-1, +1]:
    - Positive when price rising, negative when falling.
    """
    if prev_px <= 0:
        return 0.0
    delta = (px - prev_px) / prev_px
    # scale small deltas into [-1, +1] conservatively
    scaled = max(-1.0, min(1.0, delta * 50.0))
    return scaled


def main():
    if len(sys.argv) < 2:
        print("Usage: python run_replay_from_csv.py path\\to\\prices.csv")
        sys.exit(1)

    path = sys.argv[1]
    instrument = "REPLAY_INSTRUMENT"
    starting_equity = 100_000.0
    sim = PaperSimulator(starting_equity=starting_equity)

    rows = load_prices(path)

    # For now, we treat sufficiency as len(rows)//5 bars of 5m (placeholder)
    bars_5m = max(1, len(rows) // 5)

    trades_taken = 0
    prev_ts, prev_px = rows[0]

    for i in range(1, len(rows)):
        ts_str, px = rows[i]
        sig = momentum_signal(prev_px, px)

        # Build envelope for this step
        b = SignalEnvelopeBuilder(instrument=instrument)
        b.add_signal(
            name="momentum",
            source="replay",
            signal_type="indicator",
            value=sig,
            confidence=0.65,
            meta={"timestamp": ts_str, "prev_price": prev_px, "price": px},
        )
        envelope = b.build()

        # Arbitration
        arb = SignalArbitrator.arbitrate(envelope)

        # Regime gate (placeholder: we only block if extreme vol proxy; here fixed safe)
        regime = RegimeGate.evaluate(
            bars_5m=bars_5m,
            vol_norm_0_1=0.35,
            spread_bps=7.0,
            high_risk_news=False,
            extra={"instrument": instrument, "ts": ts_str},
        )

        # Execution gate stays OFF (paper only)
        exec_decision = ExecutionGate.evaluate(
            now_ts=time.time(),
            execution_enabled=False,
            equity=sim.state.equity,
            peak_equity=sim.state.peak_equity,
            current_equity=sim.state.equity,
            proposed_risk_amount=10_000.0,
            trades_today=0,
            open_positions=0,
            global_loss_streak=0,
            global_cooldown_until_ts=0.0,
            pair_loss_streak=0,
            has_human_override=False,
            override_confirmations=0,
            extra={"instrument": instrument, "ts": ts_str},
        )

        # Simple decision rule for paper sim:
        # - only trade if arbitration allows AND regime allows
        # - go LONG if sig > +0.15, SHORT if sig < -0.15
        if arb.allowed and regime.decision == "ALLOW":
            if sig > 0.15 and i + 1 < len(rows):
                # exit at next bar (simple 1-step hold)
                _, next_px = rows[i + 1]
                sim.simulate_trade(
                    instrument=instrument,
                    direction="LONG",
                    entry_price=px,
                    exit_price=next_px,
                    size=100_000,
                    meta={"ts": ts_str, "sig": sig, "arb": arb.reason, "regime": regime.reason, "exec": exec_decision.reason},
                )
                trades_taken += 1
            elif sig < -0.15 and i + 1 < len(rows):
                _, next_px = rows[i + 1]
                sim.simulate_trade(
                    instrument=instrument,
                    direction="SHORT",
                    entry_price=px,
                    exit_price=next_px,
                    size=100_000,
                    meta={"ts": ts_str, "sig": sig, "arb": arb.reason, "regime": regime.reason, "exec": exec_decision.reason},
                )
                trades_taken += 1

        prev_ts, prev_px = ts_str, px

    report = metrics_from_simulator(sim)

    print("\n=== REPLAY MODE (CSV) SUMMARY ===")
    print(f"Rows: {len(rows)} | Trades taken: {trades_taken}")
    print(f"Equity start: {starting_equity} | Equity end: {sim.state.equity:.4f}")
    print("\n[Metrics]")
    print(f"  trades: {report.trades} | wins: {report.wins} | losses: {report.losses}")
    print(f"  win_rate: {report.win_rate}")
    print(f"  avg_win: {report.avg_win} | avg_loss: {report.avg_loss}")
    print(f"  payoff_ratio: {report.payoff_ratio}")
    print(f"  expectancy: {report.expectancy}")
    print(f"  max_drawdown_pct: {report.max_drawdown_pct}")
    print(f"  equity_curve_points: {len(report.equity_curve)}")
    print("\nNOTE: Execution remains disabled. Replay is paper-only.\n")


if __name__ == "__main__":
    main()
