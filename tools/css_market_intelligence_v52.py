"""
CSS Market Intelligence v52
Capital Strata Systems

Faster market scanner with visible progress output.
Scans Coinbase assets, ranks simple momentum, and refreshes quickly.
"""

from __future__ import annotations

import time
from datetime import datetime
from typing import List, Dict, Optional

import requests


API = "https://api.exchange.coinbase.com"
ASSETS = [
    "BTC-USD",
    "ETH-USD",
    "SOL-USD",
    "LINK-USD",
    "AVAX-USD",
    "MATIC-USD",
    "ATOM-USD",
    "DOT-USD",
    "LTC-USD",
]

REQUEST_TIMEOUT = 4
SAMPLES_PER_ASSET = 2
SAMPLE_DELAY_SECONDS = 0.35
REFRESH_SECONDS = 10


def get_price(product: str) -> Optional[float]:
    url = f"{API}/products/{product}/ticker"
    try:
        response = requests.get(
            url,
            timeout=REQUEST_TIMEOUT,
            headers={"User-Agent": "CSS-Market-Intelligence/52"},
        )
        response.raise_for_status()
        data = response.json()
        price = data.get("price")
        if price is None:
            return None
        return float(price)
    except Exception:
        return None


def compute_momentum(prices: List[float]) -> float:
    if len(prices) < 2:
        return 0.0
    first = prices[0]
    last = prices[-1]
    if first == 0:
        return 0.0
    return (last - first) / first


def scan_market() -> List[Dict[str, object]]:
    results: List[Dict[str, object]] = []

    print("\nScanning assets...\n")

    for idx, asset in enumerate(ASSETS, start=1):
        prices: List[float] = []

        print(f"[{idx}/{len(ASSETS)}] {asset} ...", end=" ", flush=True)

        for sample_no in range(SAMPLES_PER_ASSET):
            price = get_price(asset)
            if price is not None:
                prices.append(price)
            if sample_no < SAMPLES_PER_ASSET - 1:
                time.sleep(SAMPLE_DELAY_SECONDS)

        score = compute_momentum(prices)
        last_price = prices[-1] if prices else None

        if last_price is None:
            print("no data")
        else:
            print(f"ok  last={last_price:.4f}  score={score:.6f}")

        results.append(
            {
                "asset": asset,
                "score": score,
                "last_price": last_price,
                "samples": len(prices),
            }
        )

    return results


def print_header() -> None:
    print("\n" + "=" * 70)
    print(" CAPITAL STRATA SYSTEMS — MARKET INTELLIGENCE ")
    print("=" * 70)


def display_rankings(results: List[Dict[str, object]]) -> None:
    ranked = sorted(
        results,
        key=lambda item: float(item.get("score", 0.0)),
        reverse=True,
    )

    print("\nTOP MOMENTUM ASSETS\n")

    shown = 0
    for item in ranked:
        asset = str(item.get("asset", "UNKNOWN"))
        score = float(item.get("score", 0.0))
        price = item.get("last_price")
        samples = int(item.get("samples", 0))

        if price is None:
            continue

        shown += 1
        print(
            f"{shown}. {asset:<9} score={score:+.6f}  "
            f"price={float(price):.4f}  samples={samples}"
        )

        if shown >= 5:
            break

    if shown == 0:
        print("No valid market data returned.")


def main() -> None:
    while True:
        print_header()
        results = scan_market()
        display_rankings(results)
        print(
            "\nLast Update:",
            datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC"),
        )
        print(f"\nRefreshing in {REFRESH_SECONDS} seconds...\n")
        time.sleep(REFRESH_SECONDS)


if __name__ == "__main__":
    main()