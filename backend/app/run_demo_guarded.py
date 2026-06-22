"""
REA Capital — Guarded DEMO Runner (PRACTICE)

- Fail-closed (won’t run unless OANDA_ENV=practice)
- Requires HEADLESS_DEV_MODE=true
- Requires EXECUTION_ARMORED=true to actually place a trade
  (default False: it will only print what it WOULD do)
"""

from __future__ import annotations

import os
from dotenv import load_dotenv

from backend.app.brokers.oanda_adapter import OandaAdapter, OrderRequest


def _env(name: str, default: str = "") -> str:
    return (os.getenv(name) or default).strip()


def main() -> None:
    load_dotenv()

    oanda_env = _env("OANDA_ENV").lower()
    headless = _env("HEADLESS_DEV_MODE", "false").lower() == "true"
    armed = _env("EXECUTION_ARMED", "false").lower() == "true"

    print("\n" + "=" * 62)
    print("REA CAPITAL — GUARDED DEMO (FAIL-CLOSED)")
    print("=" * 62)
    print(f"OANDA_ENV         : {oanda_env or '(missing)'}")
    print(f"OANDA_BASE_URL    : {_env('OANDA_BASE_URL') or '(missing)'}")
    print(f"HEADLESS_DEV_MODE : {headless}")
    print(f"EXECUTION_ARMED   : {armed}")
    print("")

    if oanda_env != "practice":
        print("ABORT: DEMO runner requires OANDA_ENV=practice.")
        return
    if not headless:
        print("ABORT: HEADLESS_DEV_MODE must be true for guarded runs.")
        return

    adapter = OandaAdapter()
    if not adapter.is_configured():
        print("ABORT: OANDA creds missing. Check .env.")
        return

    # Account summary
    summary = adapter.get_account_summary()
    if not summary.get("ok"):
        print(f"ABORT: account summary failed: {summary.get('status')} {summary.get('error')}")
        print(summary.get("data"))
        return

    bn = adapter.extract_balance_nav(summary)
    print("OANDA ACCOUNT SUMMARY")
    print("-" * 40)
    print(f"Balance: {bn['balance']}")
    print(f"NAV    : {bn['nav']}")
    print("")

    # If not armed, stop here (safe by default)
    if not armed:
        print("SAFE MODE: EXECUTION_ARMED is false. No trade will be placed.")
        print("Set EXECUTION_ARMED=true in .env when you are ready to place DEMO micro trades.")
        return

    # Micro trade
    order = OrderRequest(symbol="EUR_USD", side="BUY", units=1, order_type="MARKET")
    print("Placing DEMO micro trade (EUR_USD, BUY 1 unit)...")
    result = adapter.place_order(
        order=order,
        # ── Live firewall parameters ──────────────────────────────────────────
        # This runner is PRACTICE-ONLY (OANDA_ENV=practice asserted above).
        # broker_mode="paper" is intentional: the firewall will block at
        # condition 2 unless live mode is explicitly selected, which this
        # runner never does. This documents the practice-only constraint in code.
        broker_mode="paper",
        broker_execution_armed=armed,
        governance_approved=False,  # no governance approval pathway in demo runner
        controls={},
        user_context={
            "user_id": "demo_guarded_runner",
            "role": "SUPER_USER",
            "role_profile": {"can_execute_live_trading": False},  # practice only
        },
    )

    print("\nORDER RESULT")
    print("-" * 40)
    print(f"ok    : {result.get('ok')}")
    print(f"status: {result.get('status')}")
    print(f"error : {result.get('error')}")
    # print minimal parts of response
    data = result.get("data") or {}
    print(f"keys  : {list(data.keys()) if isinstance(data, dict) else type(data)}")

    # Best-effort close if tradeID is present
    trade_id = None
    if isinstance(data, dict):
        opened = data.get("orderFillTransaction") or {}
        trade_opened = opened.get("tradeOpened") or {}
        trade_id = trade_opened.get("tradeID")

    if trade_id:
        print(f"\nClosing tradeID={trade_id} (best-effort)...")
        close = adapter.close_trade(str(trade_id))
        print(f"CLOSE ok={close.get('ok')} status={close.get('status')} error={close.get('error')}")
    else:
        print("\nNo tradeID found. Skipping close.")

    print("\nDONE.\n")


if __name__ == "__main__":
    main()
