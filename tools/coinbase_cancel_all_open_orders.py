# tools/coinbase_cancel_all_open_orders.py
from __future__ import annotations

import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.adapters.coinbase_adapter import CoinbaseAdapter

PRODUCT_ID = "BTC-USDC"


def main() -> int:
    print("=== CSS Coinbase Cancel All Open Orders ===")

    keyfile = "cdp_api_key (2).json"
    adapter = CoinbaseAdapter(keyfile)

    dry_run = True
    if "--live" in sys.argv:
        dry_run = False

    exec_enabled = os.getenv("COINBASE_EXECUTION_ENABLED", "false").strip().lower() == "true"

    # Fetch open orders
    open_orders = adapter._request(
        "GET",
        "/api/v3/brokerage/orders/historical/batch",
        params={
            "product_id": PRODUCT_ID,
            "order_status": "OPEN",
        },
    )

    orders = open_orders.get("orders", [])

    print(f"Open orders found: {len(orders)}")

    if not orders:
        print("No open orders.")
        return 0

    for o in orders:
        print(f"Order ID: {o.get('order_id')} | Side: {o.get('side')} | Price: {o.get('limit_price')}")

    if dry_run:
        print("\nDRY_RUN: No cancellations sent.")
        print("To execute cancellations:")
        print("  $env:COINBASE_EXECUTION_ENABLED='true'")
        print("  python tools\\coinbase_cancel_all_open_orders.py --live")
        return 0

    if not exec_enabled:
        print("BLOCKED: live mode requested but COINBASE_EXECUTION_ENABLED not true.")
        return 2

    # Cancel each order
    for o in orders:
        order_id = o.get("order_id")
        resp = adapter._request(
            "POST",
            "/api/v3/brokerage/orders/batch_cancel",
            payload={"order_ids": [order_id]},
        )
        print(f"Cancel response for {order_id}: {resp}")

    print("DONE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())