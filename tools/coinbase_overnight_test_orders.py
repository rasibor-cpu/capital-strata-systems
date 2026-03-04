# tools/coinbase_overnight_test_orders.py
from __future__ import annotations

import os
import sys
from decimal import Decimal, ROUND_DOWN

# Ensure repo root is on Python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.adapters.coinbase_adapter import CoinbaseAdapter

PRODUCT_ID = "BTC-USDC"

# Overnight test parameters (small + conservative)
BUY_OFFSET_PCT = Decimal("0.003")   # 0.30% below current
SELL_OFFSET_PCT = Decimal("0.003")  # 0.30% above current
BUY_QUOTE_USDC = Decimal("2.00")    # spend 2 USDC on the buy test (small)

# Decimal helpers
def d(x: str | float | int) -> Decimal:
    return Decimal(str(x))

def quantize_base_size(x: Decimal) -> str:
    # BTC base size typically supports up to 8 decimals
    return str(x.quantize(Decimal("0.00000001"), rounding=ROUND_DOWN))

def quantize_price(x: Decimal) -> str:
    # Price precision varies; 2 decimals is usually safe for USDC quotes, but we’ll keep 2
    return str(x.quantize(Decimal("0.01"), rounding=ROUND_DOWN))

def get_current_price(adapter: CoinbaseAdapter) -> Decimal:
    # Pull product details; prefer price field if available
    prod = adapter._request("GET", f"/api/v3/brokerage/products/{PRODUCT_ID}")
    # Coinbase response commonly includes "price" as a string
    price = prod.get("price")
    if price is None:
        raise RuntimeError(f"Could not read price from product response: keys={list(prod.keys())[:30]}")
    return d(price)

def get_btc_balance(adapter: CoinbaseAdapter) -> Decimal:
    accounts = adapter.get_accounts()
    for acct in accounts.get("accounts", []):
        bal = acct.get("available_balance", {})
        if bal.get("currency") == "BTC":
            return d(bal.get("value") or "0")
    return Decimal("0")

def main() -> int:
    print("=== CSS Coinbase Overnight LIMIT Orders (Tiny Test) ===")
    keyfile = "cdp_api_key (2).json"
    adapter = CoinbaseAdapter(keyfile)

    dry_run = True
    if "--live" in sys.argv:
        dry_run = False

    # Extra safety latch: even with --live, require env flag
    exec_enabled = os.getenv("COINBASE_EXECUTION_ENABLED", "false").strip().lower() == "true"
    if not dry_run and not exec_enabled:
        print("BLOCKED: live mode requested but COINBASE_EXECUTION_ENABLED is not true.")
        print("Set:  $env:COINBASE_EXECUTION_ENABLED='true'  then rerun with --live")
        return 2

    px = get_current_price(adapter)
    btc_bal = get_btc_balance(adapter)

    buy_px = px * (Decimal("1") - BUY_OFFSET_PCT)
    sell_px = px * (Decimal("1") + SELL_OFFSET_PCT)

    # Convert quote spend to BTC base size at the BUY limit price
    buy_base = BUY_QUOTE_USDC / buy_px

    buy_px_s = quantize_price(buy_px)
    sell_px_s = quantize_price(sell_px)
    buy_base_s = quantize_base_size(buy_base)

    print(f"Current {PRODUCT_ID} price: {px}")
    print(f"Planned BUY  limit: {buy_px_s}  for ~{BUY_QUOTE_USDC} USDC => base_size {buy_base_s} BTC")
    print(f"Planned SELL limit: {sell_px_s}  (only if BTC held)")
    print(f"Detected BTC balance: {btc_bal}")

    if dry_run:
        print("\nDRY_RUN: No orders will be sent.")
        print("To go live:")
        print("  $env:COINBASE_EXECUTION_ENABLED='true'")
        print("  python tools\\coinbase_overnight_test_orders.py --live")
        return 0

    # --- Place BUY LIMIT (GTC) ---
    buy_resp = adapter.place_limit_order(
        product_id=PRODUCT_ID,
        side="BUY",
        limit_price=buy_px_s,
        base_size=buy_base_s,
        time_in_force="GTC",
    )
    print("\nBUY ORDER RESPONSE:")
    print(buy_resp)

    # --- Place SELL LIMIT (GTC) if BTC held above dust ---
    # Keep a small dust filter so we don’t place nonsense sells
    if btc_bal > Decimal("0.00000100"):
        sell_base_s = quantize_base_size(btc_bal)
        sell_resp = adapter.place_limit_order(
            product_id=PRODUCT_ID,
            side="SELL",
            limit_price=sell_px_s,
            base_size=sell_base_s,
            time_in_force="GTC",
        )
        print("\nSELL ORDER RESPONSE:")
        print(sell_resp)
    else:
        print("\nSkipping SELL: BTC balance is dust / too small to place a meaningful sell order.")

    print("\nDONE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())