"""
tools/coinbase_flatten_btc_market.py
Capital Strata Systems (CSS)

Flatten BTC position by SELLing all available BTC on BTC-USD using the
Coinbase Advanced SDK typed method: market_order_sell.

This avoids raw /brokerage/orders payload schema issues.

Usage:
  python tools/coinbase_flatten_btc_market.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List

# --- ensure repo root on sys.path ---
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.adapters.coinbase_adapter import CoinbaseAdapter  # noqa: E402
from coinbase.rest import RESTClient  # noqa: E402


def _as_list(x: Any) -> List[Any]:
    if x is None:
        return []
    if isinstance(x, list):
        return x
    return [x]


def _pick_btc_available(accounts_resp: Dict[str, Any]) -> Decimal:
    accounts = _as_list(accounts_resp.get("accounts") or accounts_resp.get("result") or accounts_resp.get("data"))

    for a in accounts:
        cur = a.get("currency")
        if isinstance(cur, dict):
            cur = cur.get("symbol") or cur.get("code")

        if str(cur).upper() != "BTC":
            continue

        bal = a.get("available_balance") or a.get("available") or a.get("balance") or {}
        if isinstance(bal, dict):
            amt = bal.get("value") or bal.get("amount")
        else:
            amt = bal

        try:
            return Decimal(str(amt))
        except (InvalidOperation, TypeError):
            continue

    return Decimal("0")


def main() -> int:
    keyfile = os.environ.get("COINBASE_KEYFILE") or str(REPO_ROOT / "keys" / "cdp_api_key (2).json")

    adapter = CoinbaseAdapter()  # uses env COINBASE_KEYFILE already
    acct_resp = adapter.get_accounts(limit=250)
    btc_avail = _pick_btc_available(acct_resp)

    print("\n=== CSS Coinbase Flatten BTC (Market via SDK) ===")
    print(f"Keyfile: {keyfile}")
    print(f"BTC available: {btc_avail}")

    if btc_avail <= Decimal("0"):
        print("No BTC available to sell. Already flat (or BTC locked/unavailable).")
        return 0

    client = RESTClient(key_file=keyfile, verbose=False)

    # Use a unique client_order_id per run (avoid duplicate-reject rules)
    client_order_id = f"CSS-FLATTEN-BTC-{int(__import__('time').time())}"

    # SDK expects strings for sizes
    base_size = format(btc_avail, "f")

    # Typed helper (most reliable)
    resp = client.market_order_sell(
        client_order_id=client_order_id,
        product_id="BTC-USD",
        base_size=base_size,
    )

    # Normalize output
    if hasattr(resp, "to_dict"):
        resp_out = resp.to_dict()
    else:
        resp_out = resp

    print("\nOrder response:")
    print(resp_out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())