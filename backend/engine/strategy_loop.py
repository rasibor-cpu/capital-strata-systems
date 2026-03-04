from __future__ import annotations

import os
import random
import time

from backend.execution.coinbase_executor import CoinbaseExecutor, OrderIntent
from backend.risk.trading_safety import TradingSafety


def generate_signal() -> str:
    """
    Placeholder signal generator.
    Emits BUY randomly for plumbing tests.
    """
    return "BUY" if random.random() > 0.7 else "NONE"


def run_loop() -> None:

    executor = CoinbaseExecutor()
    safety = TradingSafety()

    product_id = os.getenv("PRODUCT_ID", "BTC-USDC").strip().upper()
    quote_size = os.getenv("SMOKE_QUOTE_SIZE", "2").strip()

    print("\nStrategy loop started.")
    print("TRADE_MODE:", os.getenv("TRADE_MODE", "DRY_RUN"))
    print("LIVE_TRADING_ARMED:", os.getenv("LIVE_TRADING_ARMED", "NO"))
    print("PRODUCT_ID:", product_id)
    print("SMOKE_QUOTE_SIZE:", quote_size)
    print("KILL_SWITCH_FILE:", str(safety.cfg.kill_switch_file))
    print("-------------------------------------------------\n")

    while True:

        try:

            # kill switch check
            if safety.kill_switch_active():
                print("KILL SWITCH ACTIVE — LIVE orders blocked.")
                time.sleep(5)
                continue

            signal = generate_signal()
            print("Signal:", signal)

            if signal == "BUY":

                allowed, reason = safety.can_send_order(quote_size=quote_size)

                if not allowed:
                    safety.record_block(reason)
                    print("BLOCKED:", reason)
                    time.sleep(5)
                    continue

                intent = OrderIntent(
                    product_id=product_id,
                    side="BUY",
                    order_type="MARKET",
                    quote_size=quote_size
                )

                result = executor.create_order(intent)

                print("Order Result:", result)

                # IMPORTANT SAFETY FIX
                # record immediately after order response
                if not result.get("dry_run", True):
                    safety.record_order_sent()

        except Exception as e:

            print("ENGINE EXCEPTION:", str(e))

        time.sleep(10)


def main():

    run_loop()


if __name__ == "__main__":

    main()