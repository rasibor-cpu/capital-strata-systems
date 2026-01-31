"""
run_demo_end_to_end.py — Canonical End-to-End Demo Runner (Prompt-Only)
-----------------------------------------------------------------------
Runs:
- EngineLoop step() for a small set of symbols (prompt-only)
- Registers intents into trade ledger
- Simulates fills (dry-run)
- Demonstrates governance-grade customer onboarding + postings:
    (a) SUPERVISOR-approved ACCOUNT_OPEN (success)
    (b) posting blocked for non-onboarded customer (enforced)
    (c) system postings to SYS-SUSPENSE and SYS-SUNDRY (allowed)
- Generates reports + breach alerts INCLUDING customer/ledger/transaction details

No execution. No broker calls. Safe demo only.

Usage:
    python run_demo_end_to_end.py
"""

from typing import Dict, Any
from engine_loop import EngineLoop
from reports_engine import ReportsEngine
from posting_ledger import PostingLedger


def make_market_context(symbol: str) -> Dict[str, Any]:
    return {
        "symbol": symbol,
        "timeframe": "5m",
        "vwap": 100.0,
        "last": 101.0,
        "spread": 0.01,
        "volatility": 0.5,
        "liquidity": "NORMAL",
        "trend": "MEAN_REVERT",
        "features": {"zscore": 1.2, "atr": 0.8, "range": 1.5},
    }


def main() -> None:
    symbols = ["EURUSD", "GBPUSD", "USDJPY", "SPY"]
    bars_available = 60

    engine = EngineLoop(
        min_bars_required=40,
        per_symbol_limit=5_000_000,
        gross_limit=20_000_000,
        simulate_fills=True,
    )

    print("\n=== REA Capital Trading Engine — End-to-End Demo (Prompt-Only) ===\n")

    # ---------------------------
    # Trade ledger demo (prompt-only)
    # ---------------------------
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

    # ---------------------------
    # Customer onboarding + postings demo (governance)
    # ---------------------------
    posting = PostingLedger()

    print("\n=== CUSTOMER ONBOARDING & POSTINGS (Governance) ===")

    # (a) SUPERVISOR-approved ACCOUNT_OPEN (SUCCESS)
    cust = posting.open_customer_account(
        customer_name="ACME Trading Ltd",
        account_ref="ACME-USD-001",
        approved_by="Jane Supervisor",
        approval_level="SUPERVISOR",
    )
    print(f"Account opened OK: {cust.customer_id} | {cust.customer_name} | {cust.account_ref}")

    # (b) Posting for a NON-ONBOARDED customer (BLOCKED)
    try:
        posting.post(
            customer_id="CUST-NOT-ONBOARDED",
            ledger_type="CUSTOMER",
            ledger_id="LEDGER-UNKNOWN",
            transaction_type="POSTING",
            side="DR",
            currency="USD",
            notional=100_000,
            description="Should fail: customer not onboarded",
            value_date="2026-01-30",
        )
    except Exception as e:
        print(f"Posting blocked as expected (non-onboarded): {e}")

    # (c) Postings for onboarded customer (allowed)
    posting.post(
        customer_id=cust.customer_id,
        ledger_type="CUSTOMER",
        ledger_id=f"LEDGER-{cust.account_ref}",
        transaction_type="POSTING",
        side="DR",
        currency="USD",
        notional=1_250_000,
        description="Customer DR posting - invoice settlement",
        value_date="2026-01-30",
    )
    posting.post(
        customer_id=cust.customer_id,
        ledger_type="CUSTOMER",
        ledger_id=f"LEDGER-{cust.account_ref}",
        transaction_type="POSTING",
        side="DR",
        currency="USD",
        notional=1_000_000,  # cumulative breaches per_customer_limit default 2,000,000 in ReportsEngine demo
        description="Customer DR posting - additional debit",
        value_date="2026-01-30",
    )
    print("Customer postings created OK (expected to breach per-customer limit in reports).")

    # (d) System accounts: SUSPENSE and SUNDRY (allowed)
    posting.post(
        customer_id="SYS-SUSPENSE",
        ledger_type="INTERNAL",
        ledger_id="LEDGER-SUSPENSE",
        transaction_type="ADJUSTMENT",
        side="DR",
        currency="USD",
        notional=250_000,
        description="Suspense booking pending EOD resolution",
        value_date="2026-01-30",
    )
    posting.post(
        customer_id="SYS-SUNDRY",
        ledger_type="INTERNAL",
        ledger_id="LEDGER-SUNDRY",
        transaction_type="ADJUSTMENT",
        side="CR",
        currency="USD",
        notional=75_000,
        description="Sundry booking pending EOD resolution",
        value_date="2026-01-30",
    )
    print("System postings created OK: SYS-SUSPENSE and SYS-SUNDRY")

    # ---------------------------
    # Reports + breaches (trade + posting)
    # ---------------------------
    reporter = ReportsEngine(
        engine.ledger,
        posting_ledger=posting,
        per_customer_limit=2_000_000,
        per_ledger_limit=10_000_000,
    )

    breaches = reporter.supervisor_alerts()

    print("\n=== BREACH ALERTS (Supervisor Payload) ===")
    if not breaches:
        print("No breaches detected.\n")
    else:
        for b in breaches:
            print(
                f"- {b['breach_type']} | {b['severity']} | "
                f"cust={b.get('customer_id')} | ledger={b.get('ledger_id')} | "
                f"tx={b.get('transaction_type')} {b.get('side')} {b.get('currency')} "
                f"{b.get('notional')} | observed={b['observed_value']} limit={b['limit_value']} | "
                f"esc={b['escalation_level']}"
            )

    print("\nDemo complete.\n")


if __name__ == "__main__":
    main()
