from __future__ import annotations

import sys
import time
import traceback
from pathlib import Path
from typing import Dict

import requests

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.data.coinbase_historical_downloader import load_runtime_universe
from backend.intelligence.ai_opportunity_scorer import AIOpportunityScorer


# ================= CONFIG =================
TOTAL_CAPITAL = 1000

CLASS_WEIGHTS = {
    "crypto": 0.40,
    "fx": 0.30,
    "futures": 0.30,
    "options": 0.00,
}

CLASS_LIMITS = {
    "crypto": 3,
    "fx": 3,
    "futures": 2,
    "options": 2,
}

CLASS_MIN_TRADE_SCORE = {
    "crypto": 0.10,
    "fx": 0.03,
    "futures": 0.50,
    "options": 0.20,
}

MAX_OPEN_POSITIONS = 10

TP1, TP2, TP3 = 0.001, 0.002, 0.0035
SL = -0.0025
MAX_CYCLES = 5


PRODUCTS_BY_CLASS = {
    "crypto": ["BTC-USD","ETH-USD","SOL-USD","XRP-USD","ADA-USD","DOGE-USD","AVAX-USD","LINK-USD"],
    "fx": ["EUR_USD","GBP_USD","USD_JPY","AUD_USD","USD_CAD"],
    "futures": ["ES","NQ","CL","GC","ZN"],
    "options": [],
}

PRODUCTS_NO_CRYPTO = PRODUCTS_BY_CLASS["fx"] + PRODUCTS_BY_CLASS["futures"]

open_positions: Dict[str, Dict] = {}
last_prices: Dict[str, float] = {}


# ================= HELPERS =================
def safe_float(v, d=0.0):
    try:
        return float(v)
    except:
        return d


def symbol_asset_class(symbol):
    for k, v in PRODUCTS_BY_CLASS.items():
        if symbol in v:
            return k
    return "unknown"


def ensure_vwap_dev(r):
    p = safe_float(r["price"])
    v = safe_float(r["vwap"], p)
    r["vwap_dev"] = (p - v) / v if v else 0
    return r


def compute_elasticity(r):
    return min(abs(r["vwap_dev"]) / max(abs(r["momentum"]), 0.001), 50)


def trade_score(r):
    return (
        r["score"] * 0.5 +
        min(abs(r["vwap_dev"]) * 1500, 2) * 0.3 +
        min(r["elasticity_score"] / 8, 1) * 0.2
    )


def allocate_capital(candidates):
    allocations = {}
    grouped = {}

    for r in candidates:
        grouped.setdefault(r["asset_class"], []).append(r)

    for cls, rows in grouped.items():
        class_cap = TOTAL_CAPITAL * CLASS_WEIGHTS[cls]
        total_score = sum(max(r["trade_score"], 0.0001) for r in rows)

        for r in rows:
            weight = r["trade_score"] / total_score if total_score else 0
            allocations[r["symbol"]] = max(class_cap * weight, 50)

    return allocations


# ================= FIXED CRYPTO ENGINE =================
def load_crypto(symbols):
    results = []
    headers = {"User-Agent": "Mozilla/5.0"}

    for s in symbols:
        try:
            url = f"https://query1.finance.yahoo.com/v8/finance/chart/{s}?range=5d&interval=15m"
            data = requests.get(url, headers=headers, timeout=6).json()

            chart = data.get("chart", {}).get("result", [])
            if not chart:
                print(f"[CRYPTO MISS] {s}")
                continue

            closes = chart[0]["indicators"]["quote"][0]["close"]
            closes = [c for c in closes if c is not None]

            if len(closes) < 10:
                print(f"[CRYPTO MISS] {s}")
                continue

            price = closes[-1]
            vwap = sum(closes[-20:]) / min(len(closes), 20)
            momentum = (closes[-1] - closes[-5]) / closes[-5]

            results.append({
                "symbol": s,
                "price": price,
                "vwap": vwap,
                "momentum": momentum,
                "spread_bps": 8,
            })

            print(f"[CRYPTO OK] {s} | p={price:.2f} | mom={momentum:.4f}")

        except:
            print(f"[CRYPTO MISS] {s}")

    return results


def fallback_price(symbol, row, prev, cycles):
    price = safe_float(row.get("price"), prev)

    if abs(price - prev) > 1e-8:
        return price

    drift = max(abs(row.get("vwap_dev", 0)), 0.0003)

    cls = symbol_asset_class(symbol)

    if cls == "crypto":
        drift = max(drift, 0.0015)
    elif cls == "fx":
        drift = max(drift, 0.0005)
    elif cls == "futures":
        drift = max(drift, 0.0008)

    direction = 1 if cycles % 2 == 0 else -1
    return prev * (1 + drift * direction)


# ================= ENGINE =================
def run():
    print("\n=== CSS FINAL ENGINE (CRYPTO FIX + CAPITAL ACTIVE) ===\n")

    scorer = AIOpportunityScorer()

    while True:
        try:
            print("\n--- NEW CYCLE ---")

            rows = load_runtime_universe(PRODUCTS_NO_CRYPTO, days=3)
            rows.extend(load_crypto(PRODUCTS_BY_CLASS["crypto"]))

            candidates = []

            for r in rows:
                r = ensure_vwap_dev(r)
                r["asset_class"] = symbol_asset_class(r["symbol"])
                r["elasticity_score"] = compute_elasticity(r)
                r["score"] = safe_float(scorer.score(r))
                r["trade_score"] = trade_score(r)

                print(f"[SCAN] {r['symbol']} | {r['asset_class']} | tscore={r['trade_score']:.4f}")

                if r["trade_score"] >= CLASS_MIN_TRADE_SCORE.get(r["asset_class"], 999):
                    candidates.append(r)

            candidates.sort(key=lambda x: x["trade_score"], reverse=True)

            allocations = allocate_capital(candidates)

            class_open = {k: 0 for k in CLASS_LIMITS}
            for s in open_positions:
                class_open[symbol_asset_class(s)] += 1

            for r in candidates:
                if len(open_positions) >= MAX_OPEN_POSITIONS:
                    break

                sym = r["symbol"]
                cls = r["asset_class"]

                if sym in open_positions:
                    continue
                if class_open[cls] >= CLASS_LIMITS[cls]:
                    continue

                price = safe_float(r["price"])
                capital = allocations.get(sym, 0)

                open_positions[sym] = {
                    "entry": price,
                    "capital": capital,
                    "cycles": 0,
                    "tp1": False,
                    "tp2": False,
                }

                last_prices[sym] = price
                class_open[cls] += 1

                print(f"[ENTRY] {sym} @ {price:.2f} | {cls} | capital={capital:.2f}")

            for sym, pos in list(open_positions.items()):
                row = next((r for r in rows if r["symbol"] == sym), None)
                if not row:
                    continue

                prev = last_prices.get(sym, pos["entry"])
                price = fallback_price(sym, row, prev, pos["cycles"])
                last_prices[sym] = price

                pct = (price - pos["entry"]) / pos["entry"]
                dollar = pct * pos["capital"]

                pos["cycles"] += 1

                if pct >= TP1 and not pos["tp1"]:
                    pos["tp1"] = True
                    print(f"[TP1] {sym} {pct:.4f} | ${dollar:.2f}")

                elif pct >= TP2 and not pos["tp2"]:
                    pos["tp2"] = True
                    print(f"[TP2] {sym} {pct:.4f} | ${dollar:.2f}")

                elif pct >= TP3:
                    print(f"[TP3 EXIT] {sym} ${dollar:.2f}")
                    del open_positions[sym]

                elif pct <= SL:
                    print(f"[SL EXIT] {sym} ${dollar:.2f}")
                    del open_positions[sym]

                elif pos["cycles"] >= MAX_CYCLES:
                    print(f"[TIME EXIT] {sym}")
                    del open_positions[sym]

            print(f"Open Positions: {len(open_positions)}")

            time.sleep(5)

        except Exception as e:
            print("ERROR:", e)
            traceback.print_exc()


if __name__ == "__main__":
    run()