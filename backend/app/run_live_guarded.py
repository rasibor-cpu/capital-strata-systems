"""
Capital Strata Systems
REA Capital — Guarded LIVE Runner (FAIL-CLOSED)

Rules (hard):
- MUST be CS_MODE=live (hard abort otherwise)
- MUST be OANDA_ENV=live (hard abort otherwise)
- MUST be HEADLESS_DEV_MODE=true (we only run guarded in headless mode)
- MUST be EXECUTION_ARMED=true to place any trade
- LIVE env MUST NOT point to fxpractice URL (hard abort)
"""

from __future__ import annotations

import os
from dotenv import load_dotenv

from backend.app.brokers.oanda_adapter import OandaAdapter, OrderRequest


def _env(name: str, default: str = "") -> str:
    return (os.getenv(name) or default).strip()


def _as_bool(v: str) -> bool:
    return v.strip().lower() == "true"


def main() -> None:
    # IMPORTANT:
    # In Windows CMD, users often do: set EXECUTION_ARMED=true
    # load_dotenv() will NOT override that unless override=True.
    # We want .env.* to be authoritative for guarded runs.
    load_dotenv(override=True)

    cs_mode = _env("CS_MODE").lower()
    oanda_env = _env("OANDA_ENV").lower()
    base_url = _env("OANDA_BASE_URL")
    headless = _as_bool(_env("HEADLESS_DEV_MODE", "false"))
    armed = _as_bool(_env("EXECUTION_ARMED", "false"))

    print("\n" + "=" * 78)
    print("CAPITAL STRATA SYSTEMS — GUARDED LIVE (FAIL-CLOSED)")
    print("=" * 78)
    print(f"CS_MODE           : {cs_mode or '(missing)'}")
    print(f"OANDA_ENV         : {oanda_env or '(missing)'}")
    print(f"OANDA_BASE_URL    : {base_url or '(missing)'}")
    print(f"HEADLESS_DEV_MODE : {headless}")
    print(f"EXECUTION_ARMED   : {armed}")
    print("")

    # --- Hard gates ---
    if cs_mode != "live":
        print("ABORT: Live runner requires CS_MODE=live.")
        return

    if oanda_env != "live":
        print("ABORT: Live runner requires OANDA_ENV=live.")
        return

    if not headless:
        print("ABORT: HEADLESS_DEV_MODE must be true for guarded runs.")
        return

    # Prevent accidental live-mode calls to practice endpoints
    if "fxpractice" in (base_url or "").lower():
        print("ABORT: LIVE mode must not use fxpractice base URL.")
        print("Fix OANDA_BASE_URL to the live endpoint (fxtrade), then rerun.")
        return

    adapter = OandaAdapter()
    if not adapter.is_configured():
        print("ABORT: OANDA creds missing. Check .env.live.")
        return

    # Always pull summary first
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

    if not armed:
        print("SAFE MODE: EXECUTION_ARMED is false. No trade will be placed.")
        print("Set EXECUTION_ARMED=true only when you are truly ready.")
        return

    # LIVE guarded: still micro-size until explicitly expanded.
    order = OrderRequest(symbol="EUR_USD", side="BUY", units=1, order_type="MARKET")
    print("Placing LIVE micro trade (EUR_USD, BUY 1 unit)...")
    result = adapter.place_order(order=order)

    print("\nORDER RESULT")
    print("-" * 40)
    print(f"ok    : {result.get('ok')}")
    print(f"status: {result.get('status')}")
    print(f"error : {result.get('error')}")

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
