from __future__ import annotations

import time
from typing import Dict

from backend.execution.coinbase_executor import CoinbaseExecutor
from backend.strategy.vwap_mean_reversion import (
    VWAPConfig,
    compute_vwap_from_candles,
    should_buy_mean_reversion,
)

POLL_INTERVAL = 30
PRODUCTS = ["BTC-USD", "ETH-USD", "SOL-USD"]


def banner(title: str):
    print("\n" + "=" * 70)
    print(title)
    print("=" * 70)


def get_mid_price(candle: Dict) -> float:
    high = float(candle["high"])
    low = float(candle["low"])
    return (high + low) / 2


def print_signal(product: str, price: float, vwap: float, spread: float, decision: bool):
    status = "BUY SIGNAL" if decision else "HOLD"
    print(f"{product:<8} | Price {price:>10.2f} | VWAP {vwap:>10.2f} | Spread {spread:>7.3f}% | {status}")


def run():

    banner("CSS SIGNAL DIAGNOSTICS MODE (NO TRADING)")

    executor = CoinbaseExecutor()
    vwap_cfg = VWAPConfig()

    while True:

        banner("MARKET SCAN")

        for product in PRODUCTS:

            candles = executor.get_candles(product, "FIFTEEN_MINUTE")

            if not candles:
                print(f"{product} : No candles returned")
                continue

            vwap = compute_vwap_from_candles(candles, 20)

            latest = candles[-1]

            price = get_mid_price(latest)

            spread = ((price - vwap) / vwap) * 100

            buy_ok, reason = should_buy_mean_reversion(
                price,
                vwap,
                spread,
                vwap_cfg,
            )

            print_signal(product, price, vwap, spread, buy_ok)

        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    run()