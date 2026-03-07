"""
CSS Autonomous Loop v55
Adaptive Market Discovery Engine
"""

import json
import time
import requests
from pathlib import Path
from datetime import datetime

API = "https://api.exchange.coinbase.com"

STATE_DIR = Path("backend/state")
AUDIT_DIR = Path("audit_logs")

POSITION_FILE = STATE_DIR / "spot_position.json"
TRADES_FILE = AUDIT_DIR / "trades.jsonl"

STATE_DIR.mkdir(parents=True, exist_ok=True)
AUDIT_DIR.mkdir(parents=True, exist_ok=True)

LOOKBACK = 2
SCAN_INTERVAL = 10
TOP_N = 5

ENTRY_THRESHOLD = 0.00005
TRAIL_STOP = 0.01

cash_usd = 500
position = None
highest_price = None


def get_coinbase_products():

    try:

        r = requests.get(f"{API}/products", timeout=6)
        products = r.json()

        usd_pairs = []

        for p in products:

            if p.get("quote_currency") == "USD" and p.get("status") == "online":

                usd_pairs.append(p["id"])

        return usd_pairs

    except:

        return []


def get_price(asset):

    try:

        r = requests.get(f"{API}/products/{asset}/ticker", timeout=4)
        data = r.json()

        return float(data["price"])

    except:

        return None


def compute_score(prices):

    if len(prices) < 2:
        return 0

    return (prices[-1] - prices[0]) / prices[0]


def scan_market(asset_list):

    results = []

    print("\nScanning markets...\n")

    for asset in asset_list:

        prices = []

        print(f"Scanning {asset}...")

        for _ in range(LOOKBACK):

            p = get_price(asset)

            if p:
                prices.append(p)

            time.sleep(0.15)

        score = compute_score(prices)

        results.append({
            "asset": asset,
            "score": score,
            "price": prices[-1] if prices else None
        })

    ranked = sorted(results, key=lambda x: x["score"], reverse=True)

    return ranked


def save_position():

    if position:

        with open(POSITION_FILE, "w") as f:
            json.dump(position, f, indent=2)


def log_trade(data):

    with open(TRADES_FILE, "a") as f:
        f.write(json.dumps(data) + "\n")


def print_header():

    print("\n" + "=" * 70)
    print(" CAPITAL STRATA SYSTEMS — ADAPTIVE ENGINE ")
    print("=" * 70)


def main():

    global cash_usd
    global position
    global highest_price

    assets = get_coinbase_products()

    if not assets:

        print("No assets discovered")
        return

    assets = assets[:25]

    print(f"\nDiscovered {len(assets)} USD markets\n")

    while True:

        print_header()

        ranked = scan_market(assets)

        print("\nTOP MOMENTUM ASSETS\n")

        for i, r in enumerate(ranked[:TOP_N], start=1):

            print(f"{i}. {r['asset']} score={r['score']:.5f} price={r['price']}")

        best = ranked[0]

        if not position:

            if best["score"] > ENTRY_THRESHOLD and best["price"]:

                size = cash_usd * 0.20
                units = size / best["price"]

                position = {
                    "asset": best["asset"],
                    "entry_price": best["price"],
                    "size_usd": size,
                    "units": units,
                    "timestamp": datetime.utcnow().isoformat()
                }

                highest_price = best["price"]

                cash_usd -= size

                save_position()

                log_trade({
                    "event": "BUY",
                    "asset": best["asset"],
                    "price": best["price"],
                    "size_usd": size,
                    "timestamp": datetime.utcnow().isoformat(),
                    "pnl": 0
                })

                print(f"\nBUY {best['asset']} price={best['price']} size=${size}")

        else:

            price = get_price(position["asset"])

            if price:

                pnl = (price - position["entry_price"]) * position["units"]

                if price > highest_price:
                    highest_price = price

                trail_level = highest_price * (1 - TRAIL_STOP)

                print(
                    f"\nHOLD {position['asset']} price={price} pnl={pnl:.2f} trail={trail_level:.2f}"
                )

                if price < trail_level:

                    cash_usd += price * position["units"]

                    log_trade({
                        "event": "SELL",
                        "asset": position["asset"],
                        "price": price,
                        "timestamp": datetime.utcnow().isoformat(),
                        "pnl": pnl
                    })

                    print(f"\nSELL {position['asset']} pnl={pnl:.2f}")

                    position = None
                    highest_price = None

                    if POSITION_FILE.exists():
                        POSITION_FILE.unlink()

        print("\nCash USD:", cash_usd)

        print("\nLast Update:", datetime.utcnow())

        print("\nRefreshing in 10 seconds...\n")

        time.sleep(SCAN_INTERVAL)


if __name__ == "__main__":
    main()