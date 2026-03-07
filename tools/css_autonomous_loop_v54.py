"""
CSS Autonomous Loop v54 (Safe Fast Trend Engine)
Capital Strata Systems
"""

import json
import time
from pathlib import Path
from datetime import datetime

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

STATE_DIR = Path("backend/state")
AUDIT_DIR = Path("audit_logs")

POSITION_FILE = STATE_DIR / "spot_position.json"
TRADES_FILE = AUDIT_DIR / "trades.jsonl"

STATE_DIR.mkdir(parents=True, exist_ok=True)
AUDIT_DIR.mkdir(parents=True, exist_ok=True)

LOOKBACK = 2
SCAN_INTERVAL = 10
TOP_N = 5

ENTRY_THRESHOLD = 0.00002
TRAIL_STOP = 0.01

cash_usd = 500.0
position = None
highest_price = None


def now_utc_text():
    return datetime.now().astimezone().isoformat()


def get_price(asset):
    try:
        r = requests.get(f"{API}/products/{asset}/ticker", timeout=4)
        r.raise_for_status()
        data = r.json()
        price = data.get("price")
        return float(price) if price is not None else None
    except Exception:
        return None


def compute_score(prices):
    if len(prices) < 2:
        return 0.0
    first = prices[0]
    last = prices[-1]
    if first == 0:
        return 0.0
    return (last - first) / first


def scan_market():
    results = []

    print("\nScanning assets...\n")

    for asset in ASSETS:
        prices = []
        print(f"Scanning {asset}...")

        for _ in range(LOOKBACK):
            p = get_price(asset)
            if p is not None:
                prices.append(p)
            time.sleep(0.15)

        score = compute_score(prices)
        results.append(
            {
                "asset": asset,
                "score": score,
                "price": prices[-1] if prices else None,
            }
        )

    ranked = sorted(results, key=lambda x: x["score"], reverse=True)
    return ranked


def save_position():
    global position
    if position:
        with open(POSITION_FILE, "w", encoding="utf-8") as f:
            json.dump(position, f, indent=2)


def clear_position_file():
    try:
        if POSITION_FILE.exists():
            POSITION_FILE.unlink()
    except Exception as e:
        print(f"Warning: could not delete position file: {e}")


def log_trade(data):
    with open(TRADES_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(data) + "\n")


def print_header():
    print("\n" + "=" * 70)
    print(" CAPITAL STRATA SYSTEMS — SAFE FAST TREND ENGINE ")
    print("=" * 70)


def main():
    global cash_usd
    global position
    global highest_price

    while True:
        try:
            print_header()

            ranked = scan_market()

            print("\nTOP MOMENTUM ASSETS\n")
            shown = 0
            for i, r in enumerate(ranked, start=1):
                if r["price"] is None:
                    continue
                shown += 1
                print(f"{shown}. {r['asset']}  score={r['score']:.5f}  price={r['price']}")
                if shown >= TOP_N:
                    break

            valid_ranked = [r for r in ranked if r["price"] is not None]

            if not valid_ranked:
                print("\nNo valid priced assets returned this cycle.")
                print("\nLast Update:", now_utc_text())
                print(f"\nRefreshing in {SCAN_INTERVAL} seconds...\n")
                time.sleep(SCAN_INTERVAL)
                continue

            best = valid_ranked[0]

            if not position:
                if best["score"] > ENTRY_THRESHOLD:
                    size = round(cash_usd * 0.20, 2)

                    if size > 0:
                        units = size / best["price"]

                        position = {
                            "asset": best["asset"],
                            "entry_price": best["price"],
                            "size_usd": size,
                            "units": units,
                            "timestamp": now_utc_text(),
                        }

                        highest_price = best["price"]
                        cash_usd -= size

                        save_position()

                        log_trade(
                            {
                                "event": "BUY",
                                "asset": best["asset"],
                                "price": best["price"],
                                "size_usd": size,
                                "timestamp": now_utc_text(),
                                "pnl": 0.0,
                            }
                        )

                        print(f"\nBUY {best['asset']} price={best['price']} size=${size:.2f}")
                else:
                    print(
                        f"\nNo entry. Best score {best['score']:.5f} "
                        f"below threshold {ENTRY_THRESHOLD:.5f}"
                    )

            else:
                price = get_price(position["asset"])

                if price is not None:
                    pnl = (price - position["entry_price"]) * position["units"]

                    if highest_price is None or price > highest_price:
                        highest_price = price

                    trail_level = highest_price * (1 - TRAIL_STOP)

                    print(
                        f"\nHOLD {position['asset']} price={price:.4f} "
                        f"pnl={pnl:.2f} trail={trail_level:.4f}"
                    )

                    if price < trail_level:
                        cash_usd += price * position["units"]

                        log_trade(
                            {
                                "event": "SELL",
                                "asset": position["asset"],
                                "price": price,
                                "timestamp": now_utc_text(),
                                "pnl": pnl,
                            }
                        )

                        print(f"\nSELL {position['asset']} pnl={pnl:.2f}")

                        position = None
                        highest_price = None
                        clear_position_file()
                else:
                    print(f"\nNo fresh price for open asset {position['asset']}")

            print("\nCash USD:", round(cash_usd, 2))
            print("\nLast Update:", now_utc_text())
            print(f"\nRefreshing in {SCAN_INTERVAL} seconds...\n")

            time.sleep(SCAN_INTERVAL)

        except KeyboardInterrupt:
            print("\nStopped by user.")
            break
        except Exception as e:
            print(f"\nLoop error: {e}")
            print(f"\nRetrying in {SCAN_INTERVAL} seconds...\n")
            time.sleep(SCAN_INTERVAL)


if __name__ == "__main__":
    main()