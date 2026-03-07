"""
CSS Autonomous Loop v58
Profit Ladder + Trend Engine
"""

import json
import time
import requests
from pathlib import Path
from datetime import datetime, UTC

API = "https://api.exchange.coinbase.com"

STATE_DIR = Path("backend/state")
AUDIT_DIR = Path("audit_logs")

POSITION_FILE = STATE_DIR / "spot_position.json"
TRADES_FILE = AUDIT_DIR / "trades.jsonl"

STATE_DIR.mkdir(parents=True, exist_ok=True)
AUDIT_DIR.mkdir(parents=True, exist_ok=True)

SCAN_INTERVAL = 10
LOOKBACK = 3
TOP_N = 5

ENTRY_THRESHOLD = 0.00008
TRAIL_STOP = 0.01

# Profit ladder levels
LADDER_1 = 0.005
LADDER_2 = 0.012

MIN_PRICE = 0.10
MAX_PRICE = 100000

MAX_MARKETS = 30
CONFIRM_CYCLES = 3

cash_usd = 500
position = None
highest_price = None

momentum_memory = {}


def discover_markets():

    try:

        r = requests.get(f"{API}/products", timeout=6)
        data = r.json()

        markets = []

        for p in data:

            if p.get("quote_currency") != "USD":
                continue

            if p.get("status") != "online":
                continue

            markets.append(p["id"])

        return markets

    except:

        return []


def get_price(asset):

    try:

        r = requests.get(f"{API}/products/{asset}/ticker", timeout=5)
        data = r.json()

        return float(data["price"])

    except:

        return None


def price_is_valid(price):

    if price is None:
        return False

    if price < MIN_PRICE:
        return False

    if price > MAX_PRICE:
        return False

    return True


def compute_score(prices):

    if len(prices) < 2:
        return 0

    return (prices[-1] - prices[0]) / prices[0]


def scan_market(markets):

    results = []

    print("\nScanning markets...\n")

    for asset in markets:

        prices = []

        print(f"Scanning {asset}...")

        for _ in range(LOOKBACK):

            p = get_price(asset)

            if price_is_valid(p):
                prices.append(p)

            time.sleep(0.15)

        if not prices:
            continue

        score = compute_score(prices)

        results.append({
            "asset": asset,
            "score": score,
            "price": prices[-1]
        })

    ranked = sorted(results, key=lambda x: x["score"], reverse=True)

    return ranked


def confirm_momentum(asset):

    if asset not in momentum_memory:
        momentum_memory[asset] = 1
    else:
        momentum_memory[asset] += 1

    return momentum_memory[asset] >= CONFIRM_CYCLES


def save_position():

    if position:

        with open(POSITION_FILE, "w") as f:
            json.dump(position, f, indent=2)


def log_trade(data):

    with open(TRADES_FILE, "a") as f:
        f.write(json.dumps(data) + "\n")


def print_header():

    print("\n" + "=" * 70)
    print(" CAPITAL STRATA SYSTEMS — PROFIT LADDER ENGINE ")
    print("=" * 70)


def main():

    global cash_usd
    global position
    global highest_price

    markets = discover_markets()

    if not markets:

        print("Market discovery failed")
        return

    markets = markets[:MAX_MARKETS]

    print(f"\nDiscovered {len(markets)} markets\n")

    while True:

        print_header()

        ranked = scan_market(markets)

        print("\nTOP MOMENTUM ASSETS\n")

        for i, r in enumerate(ranked[:TOP_N], start=1):

            print(f"{i}. {r['asset']} score={r['score']:.5f} price={r['price']}")

        best = ranked[0] if ranked else None

        if not position and best:

            if best["score"] > ENTRY_THRESHOLD and confirm_momentum(best["asset"]):

                size = cash_usd * 0.20
                units = size / best["price"]

                position = {
                    "asset": best["asset"],
                    "entry_price": best["price"],
                    "units": units,
                    "remaining_units": units,
                    "size_usd": size,
                    "ladder1_done": False,
                    "ladder2_done": False,
                    "timestamp": datetime.now(UTC).isoformat()
                }

                highest_price = best["price"]

                cash_usd -= size

                save_position()

                log_trade({
                    "event": "BUY",
                    "asset": best["asset"],
                    "price": best["price"],
                    "size_usd": size,
                    "timestamp": datetime.now(UTC).isoformat(),
                    "pnl": 0
                })

                print(f"\nBUY {best['asset']} price={best['price']} size=${size}")

        elif position:

            price = get_price(position["asset"])

            if price:

                entry = position["entry_price"]
                units = position["remaining_units"]

                pnl = (price - entry) * units

                move = (price - entry) / entry

                if price > highest_price:
                    highest_price = price

                # Ladder level 1
                if move >= LADDER_1 and not position["ladder1_done"]:

                    sell_units = position["units"] * 0.25
                    cash_usd += sell_units * price
                    position["remaining_units"] -= sell_units

                    position["ladder1_done"] = True

                    log_trade({
                        "event": "LADDER_SELL_1",
                        "asset": position["asset"],
                        "price": price,
                        "timestamp": datetime.now(UTC).isoformat()
                    })

                    print("\nLADDER 1 triggered — 25% locked")

                # Ladder level 2
                if move >= LADDER_2 and not position["ladder2_done"]:

                    sell_units = position["units"] * 0.25
                    cash_usd += sell_units * price
                    position["remaining_units"] -= sell_units

                    position["ladder2_done"] = True

                    log_trade({
                        "event": "LADDER_SELL_2",
                        "asset": position["asset"],
                        "price": price,
                        "timestamp": datetime.now(UTC).isoformat()
                    })

                    print("\nLADDER 2 triggered — another 25% locked")

                trail_level = highest_price * (1 - TRAIL_STOP)

                print(
                    f"\nHOLD {position['asset']} price={price} pnl={pnl:.2f} trail={trail_level:.2f}"
                )

                if price < trail_level:

                    remaining = position["remaining_units"]

                    cash_usd += remaining * price

                    log_trade({
                        "event": "SELL_FINAL",
                        "asset": position["asset"],
                        "price": price,
                        "timestamp": datetime.now(UTC).isoformat(),
                        "pnl": pnl
                    })

                    print(f"\nFINAL EXIT pnl={pnl:.2f}")

                    position = None
                    highest_price = None
                    momentum_memory.clear()

                    if POSITION_FILE.exists():
                        POSITION_FILE.unlink()

        print("\nCash USD:", cash_usd)

        print("\nLast Update:", datetime.now(UTC))

        print("\nRefreshing in 10 seconds...\n")

        time.sleep(SCAN_INTERVAL)


if __name__ == "__main__":
    main()