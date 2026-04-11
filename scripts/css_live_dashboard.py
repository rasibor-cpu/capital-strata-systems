from __future__ import annotations

import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.data.coinbase_historical_downloader import load_runtime_asset
from backend.execution.position_manager import PositionManager
from backend.intelligence.market_regime_engine import MarketRegimeEngine

# ========================
# ENGINE MODE
# ========================
ENGINE_MODES = {
    "1": "SAFE",
    "2": "CONSERVATIVE",
    "3": "BALANCED",
    "4": "AGGRESSIVE",
    "5": "EXPANSION",
}

ENGINE_PROFILES = {
    "SAFE": {"MAX_CRYPTO": 2},
    "CONSERVATIVE": {"MAX_CRYPTO": 2},
    "BALANCED": {"MAX_CRYPTO": 3},
    "AGGRESSIVE": {"MAX_CRYPTO": 4},
    "EXPANSION": {"MAX_CRYPTO": 5},
}


def select_engine_mode():
    print("\n=== CSS ENGINE MODE SELECTOR ===")
    for k, v in ENGINE_MODES.items():
        print(f"{k}. {v}")
    choice = input("Enter choice (1-5) [default=3]: ").strip()
    return ENGINE_MODES.get(choice, "BALANCED")


ENGINE_MODE = select_engine_mode()
PROFILE = ENGINE_PROFILES[ENGINE_MODE]

MAX_CRYPTO = PROFILE["MAX_CRYPTO"]

TP_PCT = 0.006
SL_PCT = 0.004
MAX_HOLD = 3

SYMBOLS = [
    "BTC-USD", "ETH-USD", "SOL-USD", "XRP-USD",
    "ADA-USD", "DOGE-USD", "AVAX-USD", "LINK-USD",
    "LTC-USD", "BCH-USD",
]

pm = PositionManager()
regime_engine = MarketRegimeEngine()

prev_prices: Dict[str, float] = {}
pos_cycles: Dict[str, int] = {}


def safe(v, d=0.0):
    try:
        return float(v)
    except Exception:
        return d


def get_price(raw):
    if isinstance(raw, dict):
        if raw.get("price"):
            return safe(raw["price"])

        candles = raw.get("candles", [])
        if candles:
            c = candles[-1]
            if isinstance(c, dict):
                return safe(c.get("close"))
            elif hasattr(c, "close"):
                return safe(c.close)
            elif isinstance(c, (list, tuple)) and len(c) > 4:
                return safe(c[4])
    return 0.0


def get_candles(raw):
    return raw.get("candles", []) if isinstance(raw, dict) else []


def score(price, prev):
    if prev <= 0 or price <= 0:
        return 0.0
    return abs((price - prev) / prev) * 10000.0


def classify(sc):
    if sc >= 10:
        return "ELITE"
    if sc >= 7:
        return "QUALIFIED"
    return "WATCH"


def size(tier, regime_score):
    if tier == "ELITE":
        return 1.0
    if tier == "QUALIFIED":
        return 0.5
    if tier == "WATCH" and regime_score >= 0.80:
        return 0.25
    return 0.0


def is_reversion_entry(row):
    candles = row.get("candles", [])
    if len(candles) < 15:
        return False

    closes = []
    for c in candles[-15:]:
        try:
            if isinstance(c, dict):
                closes.append(float(c.get("close", 0)))
            elif hasattr(c, "close"):
                closes.append(float(c.close))
            elif isinstance(c, (list, tuple)) and len(c) > 4:
                closes.append(float(c[4]))
        except Exception:
            continue

    if len(closes) < 10:
        return False

    avg = sum(closes) / len(closes)
    current = closes[-1]

    returns = []
    for i in range(1, len(closes)):
        if closes[i - 1] > 0:
            returns.append(abs((closes[i] - closes[i - 1]) / closes[i - 1]))

    if not returns:
        return False

    volatility = sum(returns) / len(returns)
    threshold = max(0.0010, volatility * 1.2)
    deviation = abs((current - avg) / avg)

    return deviation >= threshold


def regime_allows(row, tier):
    regime = row.get("regime")
    rscore = safe(row.get("regime_score"))

    if regime == "UNSTABLE":
        return False

    if regime in {"TREND", "BREAKOUT"}:
        return tier in {"ELITE", "QUALIFIED"}

    if regime == "MEAN_REVERSION":
        if tier == "ELITE":
            return True
        if tier == "QUALIFIED" and rscore >= 0.60:
            return True
        if tier == "WATCH" and rscore >= 0.80:
            return True
        return False

    if regime == "RANGE":
        if tier == "ELITE":
            return True
        if tier == "QUALIFIED":
            return True
        if tier == "WATCH" and rscore >= 0.50:
            return True
        return False

    if regime == "VOLATILE":
        return tier == "ELITE"

    return False


cycle = 0

while True:
    cycle += 1
    print(f"\n=== Cycle {cycle} | {datetime.now()} ===")

    rows = []
    prices = {}

    for s in SYMBOLS:
        raw = load_runtime_asset(s)
        price = get_price(raw)
        sc = score(price, prev_prices.get(s, 0.0))

        row = {
            "symbol": s,
            "price": price,
            "score": sc,
            "candles": get_candles(raw),
        }

        rows.append(row)
        prices[s] = price

    rows = regime_engine.detect(rows)
    rows.sort(key=lambda x: -x["score"])

    print("\n--- CRYPTO ---")
    for r in rows[:5]:
        print(
            f"{r['symbol']} | score={r['score']:.2f} | "
            f"tier={classify(r['score'])} | regime={r.get('regime')} | "
            f"rscore={safe(r.get('regime_score')):.2f}"
        )

    pm.update_positions(prices)

    for sym, pos in list(pm.positions.items()):
        entry = pos["entry_price"]
        cur = prices.get(sym, 0.0)
        pnl = (cur - entry) / entry if entry > 0 else 0.0

        pos_cycles[sym] = pos_cycles.get(sym, 0) + 1
        print(f"{sym} pnl={pnl:.4%}")

        if pnl >= TP_PCT or pnl <= -SL_PCT or pos_cycles[sym] >= MAX_HOLD:
            pm.close_position(sym, cur, "EXIT")
            pos_cycles.pop(sym, None)

    open_count = len(pm.positions)

    for r in rows:
        if open_count >= MAX_CRYPTO:
            break

        if r["symbol"] in pm.positions:
            continue

        tier = classify(r["score"])
        regime = r.get("regime")
        rscore = safe(r.get("regime_score"))

        if not regime_allows(r, tier):
            print(f"[FILTERED] {r['symbol']} regime")
            continue

        # Only MEAN_REVERSION must pass reversion setup
        if regime == "MEAN_REVERSION":
            if not is_reversion_entry(r):
                print(f"[FILTERED] {r['symbol']} no reversion")
                continue

        sz = size(tier, rscore)
        if sz <= 0:
            continue

        pm.open_position(
            symbol=r["symbol"],
            entry_price=r["price"],
            size=sz,
            take_profit=r["price"] * (1 + TP_PCT),
            stop_loss=r["price"] * (1 - SL_PCT),
            side="LONG",
        )

        print(f"[OPEN] {r['symbol']} {tier} regime={regime} size={sz}")
        open_count += 1

    print("\n--- PROFIT DASHBOARD ---")
    print(f"Mode: {ENGINE_MODE}")
    print(f"Crypto Open: {len(pm.positions)}")

    prev_prices.update(prices)
    time.sleep(3)