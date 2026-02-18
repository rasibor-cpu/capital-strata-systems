"""
CSS / REA – Capital Feedback Loop Runner
========================================

Simulates:
- Trade approval
- PnL realization
- Governor state mutation
- Risk compression & expansion

Institutional validation runner.
"""

from __future__ import annotations

import random
from datetime import datetime
from engine.execution.execution_gate import ExecutionGate


def banner():
    print("=" * 70)
    print("CSS – Capital Feedback Loop Simulation")
    print(f"UTC: {datetime.utcnow().isoformat()}")
    print("=" * 70)


def simulate_pnl(notional: float, stop_distance_pct: float) -> float:
    """
    Controlled random PnL.
    Produces wins and losses within stop framework.
    """
    direction = random.choice([-1, 1])
    move_pct = random.uniform(0.25, 1.0) * stop_distance_pct
    pnl = direction * notional * move_pct
    return round(pnl, 2)


def main():
    banner()

    gate = ExecutionGate()
    gov = gate.risk_governor

    # Initialize capital
    gov.set_equity(100000.0)

    instrument = "EUR_USD"
    side = "BUY"
    stop_pct = 0.008

    for i in range(1, 11):
        print(f"\n---- TRADE {i} ----")

        result = gate.evaluate_trade(
            instrument=instrument,
            side=side,
            notional=10000.0,
            stop_distance_pct=stop_pct,
            equity=gov.equity,
            equity_peak=gov.equity_peak,
            regime_persistence=0.8,
            vol_ratio=1.0,
            spread_bps=1.2,
            high_risk_news=False,
        )

        decision = result["decision"]
        print("Decision:", decision)

        if not decision.get("ok"):
            print("Trade blocked:", decision.get("reason"))
            continue

        # Simulate execution
        pnl = simulate_pnl(
            notional=decision["recommended_notional"],
            stop_distance_pct=stop_pct,
        )

        print("Simulated PnL:", pnl)

        # Record outcome
        gov.record_trade_outcome(pnl)

        print("Updated Equity:", gov.equity)
        print("Equity Peak:", gov.equity_peak)
        print("Loss Streak:", gov.consecutive_losses)

    print("\nSimulation Complete.")
    print("Final Equity:", gov.equity)
    print("Total Trades:", gov.trades_today)


if __name__ == "__main__":
    main()
