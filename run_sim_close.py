"""
run_sim_close.py
================

End-to-end SAFE close-path proof.

What this proves:
- PaperSimulator can route a simulated CLOSE through PaperBroker (canonical boundary)
- PaperBroker writes to PnL ledger (append_pnl_event)
- PaperBroker records outcome into RiskGovernor:
    - daily PnL / streak / equity updates
    - InstrumentPerformanceLedger (weekly/monthly/quarterly/annual)

SAFE:
- No broker calls
- No live execution
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

from trade_ticket import TradeTicket
from engine.risk.risk_governor import RiskGovernor
from engine.sim.paper_simulator import PaperSimulator


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def main() -> int:
    print("=== CSS / REA SIM CLOSE PROOF ===")
    print(f"UTC={_utc_now_iso()}")

    # Governor + simulator
    gov = RiskGovernor()
    sim = PaperSimulator(starting_equity=100000.0)

    # Initialize governor equity context (important for policy + drawdown tracking)
    gov.set_equity(100000.0)

    # Build a TradeTicket (minimal but complete)
    # NOTE: We rely on TradeTicket.ledger_path() to point to TEST vs LIVE file.
    ticket = TradeTicket(
        mode="TEST",
        symbol="EUR_USD",
        side="BUY",
        amount=100000.0,
        qty=0.0,  # broker derives qty from amount/entry_px if qty <= 0
        entry_px=1.1000,
        trade_type="SIM",
        execution_date="2026-02-19",
        value_date="2026-02-19",
        currency="USD",
        fx_rate=1.0,
        exchange_rate_text="SIM",
        tag="SIM_CLOSE_PROOF",
    )

    # Simulate: entry_price/exit_price are still used for in-memory math,
    # but with use_broker_close=True the authoritative close is PaperBroker.
    trade = sim.simulate_trade(
        instrument="EUR_USD",
        direction="LONG",
        entry_price=1.1000,
        exit_price=1.1050,
        size=100000.0,  # units for in-memory math (broker uses ticket qty/amount)
        meta={"note": "close path proof"},
        use_broker_close=True,
        trade_ticket=ticket,
        risk_governor=gov,
        fees=0.0,
    )

    print("\n--- SIM TRADE ---")
    print(json.dumps(trade.__dict__, indent=2, default=str))

    print("\n--- SIM SNAPSHOT ---")
    print(json.dumps(sim.snapshot(), indent=2))

    # Governor / performance ledger snapshot
    print("\n--- GOVERNOR STATE ---")
    print(json.dumps({
        "daily_pnl": gov.daily_pnl,
        "consecutive_losses": gov.consecutive_losses,
        "trades_today": gov.trades_today,
        "equity": gov.equity,
        "equity_peak": gov.equity_peak,
        "policy_hash": gov.policy_hash(),
    }, indent=2))

    print("\n--- INSTRUMENT PERFORMANCE LEDGER ---")
    try:
        print(json.dumps(gov.ledger.snapshot(), indent=2))
    except Exception as e:
        print(f"FAILED: {e}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
