# tools/coinbase_order_smoke.py
from __future__ import annotations

import os
import sys

# Ensure repo root is on Python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.adapters.coinbase_adapter import CoinbaseAdapter
from backend.adapters.coinbase_execution import CoinbaseExecutionGate, RiskLimits


def main() -> int:
    print("=== CSS Coinbase Execution Smoke Test ===")

    # Uses your existing working key file
    keyfile = "cdp_api_key (2).json"

    # Your defined risk limits
    limits = RiskLimits(
        risk_per_trade_usd=2.0,
        max_daily_loss_usd=10.0,
        max_concurrent_positions=5,
    )

    adapter = CoinbaseAdapter(keyfile)
    gate = CoinbaseExecutionGate(adapter, limits=limits)

    # IMPORTANT:
    # You are funded in USDC (not USD). Use BTC-USDC to avoid "account is not available".
    product_id = "BTC-USDC"

    maker_user_id = "ADMIN01"

    # Default = DRY RUN
    dry_run = True
    if "--live" in sys.argv:
        dry_run = False

    quote_size = "1.00"  # 1 USDC (treated ~1 USD)

    result = gate.place_market_buy_quote(
        maker_user_id=maker_user_id,
        product_id=product_id,
        quote_size_usd=quote_size,
        dry_run=dry_run,
    )

    print("RESULT:")
    print(result)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())