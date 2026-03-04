# tools/coinbase_sell_smoke.py
from __future__ import annotations

import os
import sys

# Ensure repo root is on Python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.adapters.coinbase_adapter import CoinbaseAdapter
from backend.adapters.coinbase_execution import CoinbaseExecutionGate, RiskLimits


def main() -> int:
    print("=== CSS Coinbase SELL Smoke Test ===")

    keyfile = "cdp_api_key (2).json"

    limits = RiskLimits(
        risk_per_trade_usd=2.0,
        max_daily_loss_usd=10.0,
        max_concurrent_positions=5,
    )

    adapter = CoinbaseAdapter(keyfile)
    gate = CoinbaseExecutionGate(adapter, limits=limits)

    product_id = "BTC-USDC"
    maker_user_id = "ADMIN01"

    # Get live BTC balance
    accounts = adapter.get_accounts()
    btc_balance = 0.0

    for acct in accounts.get("accounts", []):
        bal = acct.get("available_balance", {})
        if bal.get("currency") == "BTC":
            btc_balance = float(bal.get("value", 0))

    print("Detected BTC balance:", btc_balance)

    if btc_balance <= 0:
        print("No BTC to sell.")
        return 0

    # Coinbase requires string
    base_size = str(btc_balance)

    dry_run = True
    if "--live" in sys.argv:
        dry_run = False

    result = gate.place_market_sell_base(
        maker_user_id=maker_user_id,
        product_id=product_id,
        base_size=base_size,
        dry_run=dry_run,
    )

    print("RESULT:")
    print(result)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())