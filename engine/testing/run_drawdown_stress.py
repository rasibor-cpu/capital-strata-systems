"""
Drawdown Stress Test
Forces consecutive losses to trigger throttle ladder
"""

from engine.execution.execution_gate import ExecutionGate

gate = ExecutionGate()

# Initialize equity
gate.risk_governor.set_equity(100000)

equity = 100000
peak = 100000

for i in range(1, 40):

    # Force -1% loss each iteration
    pnl = -1000
    equity += pnl
    peak = max(peak, equity)

    gate.risk_governor.set_equity(equity)
    gate.risk_governor.record_trade_outcome(pnl)

    result = gate.evaluate_trade(
        instrument="EURUSD",
        side="BUY",
        notional=10000,
        stop_distance_pct=0.01,
        regime_persistence=0.8,
        vol_ratio=1.0,
        spread_bps=1.0,
        high_risk_news=False,
        equity=equity,
        equity_peak=peak,
    )

    print(f"Trade {i} | Equity: {equity:.2f}")
    print(result["decision"])
    print("-" * 60)
