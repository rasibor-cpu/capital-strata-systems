"""
Capital Strata Systems
REA Core – Guarded LIVE Runner (FAIL-CLOSED)

STRICT GOVERNANCE RULES:
- MUST be CS_MODE=live
- MUST be OANDA_ENV=live
- MUST be HEADLESS_DEV_MODE=true
- MUST be EXECUTION_ARMED=true
- MUST pass RiskGovernor evaluation
- MUST NOT have global shutdown active

This file is the final execution boundary.
"""

from __future__ import annotations

import os
from dotenv import load_dotenv

from backend.app.brokers.oanda_adapter import OandaAdapter, OrderRequest
from engine.execution.execution_gate import ExecutionGate
from engine.risk.risk_state_store import load_state


# ---------------------------------------------------------
# Helpers
# ---------------------------------------------------------

def _env(name: str, default: str = "") -> str:
    return (os.getenv(name) or default).strip()


# ---------------------------------------------------------
# Main
# ---------------------------------------------------------

def main() -> None:
    load_dotenv()

    cs_mode = _env("CS_MODE").lower()
    oanda_env = _env("OANDA_ENV").lower()
    headless = _env("HEADLESS_DEV_MODE", "false").lower() == "true"
    armed = _env("EXECUTION_ARMED", "false").lower() == "true"

    print("\n" + "=" * 70)
    print("CAPITAL STRATA SYSTEMS — GUARDED LIVE (FAIL-CLOSED)")
    print("=" * 70)
    print(f"CS_MODE            : {cs_mode or '(missing)'}")
    print(f"OANDA_ENV          : {oanda_env or '(missing)'}")
    print(f"OANDA_BASE_URL     : {_env('OANDA_BASE_URL') or '(missing)'}")
    print(f"HEADLESS_DEV_MODE  : {headless}")
    print(f"EXECUTION_ARMED    : {armed}")
    print("")

    # ---------------------------------------------------------
    # HARD FAIL CONDITIONS
    # ---------------------------------------------------------

    if cs_mode != "live":
        print("ABORT: Live runner requires CS_MODE=live.")
        return

    if oanda_env != "live":
        print("ABORT: Live runner requires OANDA_ENV=live.")
        return

    if not headless:
        print("ABORT: HEADLESS_DEV_MODE must be true.")
        return

    if not armed:
        print("SAFE MODE: EXECUTION_ARMED is false.")
        print("No live trade will be placed.")
        return

    # ---------------------------------------------------------
    # GLOBAL SHUTDOWN CHECK (ABSOLUTE BARRIER)
    # ---------------------------------------------------------

    state = load_state()

    if state.get("global_shutdown"):
        print("ABORT: GLOBAL SHUTDOWN ACTIVE.")
        print("Reason:", state.get("global_shutdown_reason"))
        print("Manual reset required via reset_global_lock.")
        return

    # ---------------------------------------------------------
    # BROKER INITIALIZATION
    # ---------------------------------------------------------

    adapter = OandaAdapter()

    if not adapter.is_configured():
        print("ABORT: OANDA credentials missing or invalid.")
        return

    summary = adapter.get_account_summary()

    if not summary.get("ok"):
        print("ABORT: account summary failed.")
        print(summary.get("error"))
        return

    bn = adapter.extract_balance_nav(summary)

    print("OANDA ACCOUNT SUMMARY")
    print("-" * 40)
    print(f"Balance: {bn['balance']}")
    print(f"NAV    : {bn['nav']}")
    print("")

    current_equity = float(bn["nav"])

    # ---------------------------------------------------------
    # RISK GOVERNOR EVALUATION (LIVE MODE)
    # ---------------------------------------------------------

    gate = ExecutionGate()

    decision = gate.evaluate_trade(
        instrument="EUR_USD",
        equity_risk=current_equity,
    )

    if decision["status"] != "APPROVED":
        print("ABORT: RiskGovernor blocked trade.")
        print("Reasons:", decision.get("reasons"))
        return

    # ---------------------------------------------------------
    # PLACE MICRO LIVE TRADE (STRICT)
    # ---------------------------------------------------------

    order = OrderRequest(
        symbol="EUR_USD",
        side="BUY",
        units=1,
        order_type="MARKET",
    )

    print("Placing LIVE micro trade (EUR_USD, BUY 1 unit)...")

    result = adapter.place_order(order=order)

    print("\nORDER RESULT")
    print("-" * 40)
    print(f"ok     : {result.get('ok')}")
    print(f"status : {result.get('status')}")
    print(f"error  : {result.get('error')}")

    data = result.get("data") or {}
    trade_id = None

    if isinstance(data, dict):
        opened = data.get("orderFillTransaction") or {}
        trade_opened = opened.get("tradeOpened") or {}
        trade_id = trade_opened.get("tradeID")

    print(f"tradeID: {trade_id}")
    print("\nDONE.\n")


if __name__ == "__main__":
    main()
