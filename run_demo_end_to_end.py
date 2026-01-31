"""
run_demo_end_to_end.py — Canonical End-to-End Demo Runner (Prompt-Only)
-----------------------------------------------------------------------
Runs:
- EngineLoop step() for a small set of symbols
- Registers intents into ledger
- Optionally simulates fills (dry-run)
- Generates reports + breach alerts

No execution. No broker calls. Safe demo only.

Usage:
    python run_demo_end_to_end.py
"""

from typing import Dict, Any
from engine_loop import EngineLoop
from reports_engine import ReportsEngine


def make_market_context(symbol: str) -> Dict[str, Any]:
    """
    Minimal synthetic market context for demo purposes.
    This is intentionally simple and deterministic.
    """
    return {
        "symbol": symbol,
        "timeframe": "5m",
        "vwap": 100.0,
        "last": 101.0,
        "spread": 0.01,
        "volatility": 0.5,
        "liquidity": "NORMAL",
        "trend": "MEAN_REVERT",
        # RegimeGate may look at these; if unused, harmless.
        "features": {
            "zscore": 1.2,
            "atr": 0.8,
            "range": 1.5,
        },
    }


def main() -> None:
    symbols = ["EURUSD", "GBPUSD", "USDJPY", "SPY"]
    bars_available = 60  # >= min_bars_required

    # Prompt-only engine; set simulate_fills=True to see exposures + breaches in action
    engine = EngineLoop(
        min_bars_required=40,
        per_symbol_limit=5_000_000,
        gross_limit=20_000_000,
        simulate_fills=True,   # demo: ON (still no execution)
    )

    print("\n=== REA Capital Trading Engine — End-to-End Demo (Prompt-Only) ===\n")

    for sym in symbols:
        ctx = make_market_context(sym)
        out = engine.step(symbol=sym, bars_available=bars_available, market_context=ctx)

        print(f"--- {sym} ---")
        print(f"Regime allowed: {out.get('regime_allowed')} | Bars: {out.get('bars_available')}")
        if "blocked_reason" in out:
            print(f"Blocked reason: {out['blocked_reason']}\n")
            continue

        print(f"Intent registered: {out.get('intent_registered')} | intent_id: {out.get('intent_id')}")
        sim = out.get("simulation")
        if sim:
            print(f"Simulated ticket: {sim.get('ticket_id')} | breaches: {sim.get('breaches')}")
        print("")

    # Reports + breaches
    reporter = ReportsEngine(engine.ledger)
    open_intents = reporter.report_open_intents()
    approved = reporter.report_approved_tickets()
    fills = reporter.report_simulated_fills()
    positions = reporter.report_positions()
    gross = reporter.report_gross_exposure()
    breaches = reporter.supervisor_alerts()

    print("\n=== REPORTS SUMMARY ===")
    print(f"Open intents: {len(open_intents)}")
    print(f"Approved entries: {len(approved)}")
    print(f"Simulated fills: {len(fills)}")
    print(f"Gross exposure: {gross}")
    print(f"Positions: {list(positions.keys())}")

    print("\n=== BREACH ALERTS (Supervisor Payload) ===")
    if not breaches:
        print("No breaches detected.\n")
    else:
        for b in breaches:
            print(f"- {b['breach_type']} | {b['severity']} | {b['symbol']} | "
                  f"observed={b['observed_value']} limit={b['limit_value']} | "
                  f"escalation={b['escalation_level']}")

    print("\nDemo complete.\n")


if __name__ == "__main__":
    main()
