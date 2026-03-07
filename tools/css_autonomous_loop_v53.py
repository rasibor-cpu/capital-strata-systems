"""
CSS Autonomous Loop v53
Capital Strata Systems
Paper trading autonomous engine with dynamic asset selection
"""

import json
import time
import requests
from pathlib import Path
from datetime import datetime

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
    "LTC-USD"
]

STATE_DIR = Path("backend/state")
AUDIT_DIR = Path("audit_logs")

POSITION_FILE = STATE_DIR / "spot_position.json"
TRADES_FILE = AUDIT_DIR / "trades.jsonl"

STATE_DIR.mkdir(parents=True, exist_ok=True)
AUDIT_DIR.mkdir(parents=True, exist_ok=True)

LOOKBACK = 5
SCAN_INTERVAL = 15
TOP_N = 5

cash_usd = 500
position = None


def get_price(asset):

    url = f"{API}/products/{asset}/ticker"

    try:
        r = requests.get(url, timeout=5)
        data = r.json()
        return float(data["price"])
    except:
        return None


def compute_score(prices):

    if len(prices) < 2:
        return 0

    return (prices[-1] - prices[0]) / prices[0]


def scan_market():

    results = []

    for asset in ASSETS:

        prices = []

        for _ in range(LOOKBACK):

            p = get_price(asset)

            if p:
                prices.append(p)

            time.sleep(0.3)

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
    print(" CAPITAL STRATA SYSTEMS — AUTONOMOUS ENGINE ")
    print("=" * 70)


def main():

    global cash_usd
    global position

    while True:

        print_header()

        ranked = scan_market()

        print("\nTOP MOMENTUM ASSETS\n")

        for i, r in enumerate(ranked[:TOP_N], start=1):

            print(f"{i}. {r['asset']}  score={r['score']:.4f}  price={r['price']}")

        best = ranked[0]

        if not position:

            if best["score"] > 0.001 and best["price"]:

                size = cash_usd * 0.20

                units = size / best["price"]

                position = {
                    "asset": best["asset"],
                    "entry_price": best["price"],
                    "size_usd": size,
                    "units": units,
                    "timestamp": datetime.utcnow().isoformat()
                }

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

                print(f"\nHOLD {position['asset']} current={price} pnl={pnl:.2f}")

                if pnl < -2 or pnl > 5:

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

                    if POSITION_FILE.exists():
                        POSITION_FILE.unlink()

        print("\nLast Update:", datetime.utcnow())

        print("\nRefreshing in 15 seconds...\n")

        time.sleep(SCAN_INTERVAL)


if __name__ == "__main__":
    main()