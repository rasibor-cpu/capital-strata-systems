# tools/coinbase_order_status_check.py
from __future__ import annotations

import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.adapters.coinbase_adapter import CoinbaseAdapter


def main() -> int:
    adapter = CoinbaseAdapter("cdp_api_key (2).json")

    # 1) Show BTC balance precisely
    accounts = adapter.get_accounts()
    btc = None
    usdc = None
    for acct in accounts.get("accounts", []):
        bal = acct.get("available_balance", {})
        ccy = bal.get("currency")
        if ccy == "BTC":
            btc = bal.get("value")
        if ccy == "USDC":
            usdc = bal.get("value")

    print("BTC available_balance:", btc)
    print("USDC available_balance:", usdc)

    # 2) Fetch latest fills (top slice) and show BTC-USDC only
    fills = adapter._request("GET", "/api/v3/brokerage/orders/historical/fills")
    rows = fills.get("fills", [])

    print("\nLatest fills (filtered BTC-USDC):")
    shown = 0
    for f in rows:
        if f.get("product_id") != "BTC-USDC":
            continue
        print(
            {
                "trade_id": f.get("trade_id"),
                "order_id": f.get("order_id"),
                "side": f.get("side"),
                "size": f.get("size"),
                "price": f.get("price"),
                "trade_time": f.get("trade_time"),
            }
        )
        shown += 1
        if shown >= 10:
            break

    print("\nDONE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())