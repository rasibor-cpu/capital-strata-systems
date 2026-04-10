from __future__ import annotations

import sys, time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# ========================
# IMPORTS
# ========================
from backend.data.coinbase_historical_downloader import load_runtime_asset
from backend.execution.position_manager import PositionManager

from backend.app.brokers.futures_sim_adapter import FuturesSimAdapter
from backend.app.risk.futures_position_manager import FuturesPositionManager

from backend.scanner.options_chain_adapter import OptionsChainAdapter

# ========================
# CONFIG
# ========================
CYCLE_SLEEP = 3

# Crypto
MAX_CRYPTO = 3

# Futures
MAX_FUTURES = 2

# Risk
TP_PCT = 0.006
SL_PCT = 0.004
MAX_HOLD_CYCLES = 3

MIN_SCORE = 0.08

SYMBOLS = [
    "BTC-USD","ETH-USD","SOL-USD","XRP-USD",
    "ADA-USD","DOGE-USD","AVAX-USD","LINK-USD",
    "LTC-USD","BCH-USD",
]

# Futures symbols (mapped manually for now)
FUTURES_SYMBOLS = ["ES","NQ"]

# ========================
# INIT
# ========================
pm = PositionManager()

futures_adapter = FuturesSimAdapter(max_portfolio_allocation=5.0)
futures_pm = FuturesPositionManager(futures_adapter)

options_adapter = OptionsChainAdapter()

previous_prices: Dict[str, float] = {}
position_cycles: Dict[str, int] = {}

# ========================
# HELPERS
# ========================
def safe_float(v, default=0.0):
    try: return float(v)
    except: return default

def extract_candles(data):
    return data.get("candles", []) if isinstance(data, dict) else data or []

def get_close(c):
    if isinstance(c, dict): return safe_float(c.get("close"))
    if isinstance(c,(list,tuple)) and len(c)>4: return safe_float(c[4])
    return 0.0

def extract_price(raw, candles):
    if isinstance(raw, dict):
        for k in ("price","last_price","close"):
            p = safe_float(raw.get(k))
            if p > 0: return p
    return get_close(candles[-1]) if candles else 0

def build_tp_sl(p):
    return p*(1+TP_PCT), p*(1-SL_PCT)

# ========================
# SCORING (STABLE)
# ========================
def score(symbol, price, candles):
    prev = previous_prices.get(symbol, 0)

    cycle_move = abs((price-prev)/prev) if prev > 0 else 0

    closes = [get_close(c) for c in candles[-6:] if get_close(c)>0]

    vol = 0
    if len(closes) > 1:
        vol = sum(abs((closes[i]-closes[i-1])/closes[i-1])
                  for i in range(1,len(closes))) / (len(closes)-1)

    raw = (cycle_move*0.7) + (vol*0.3)

    return raw * 10000

# ========================
# MAIN LOOP
# ========================
cycle = 0

while True:
    cycle += 1
    print(f"\n=== Cycle {cycle} ===")

    rows = []
    price_map = {}

    # =====================
    # CRYPTO DATA
    # =====================
    for s in SYMBOLS:
        try:
            raw = load_runtime_asset(s)
            candles = extract_candles(raw)
            if not candles: continue

            price = extract_price(raw, candles)
            sc = score(s, price, candles)

            rows.append({
                "symbol": s,
                "price": price,
                "candles": candles,
                "score": sc
            })

            price_map[s] = price

            print(f"Fetched {len(candles)} candles for {s}")
        except:
            continue

    rows.sort(key=lambda x: -x["score"])

    print("\n--- CRYPTO RANKED ---")
    for r in rows[:5]:
        print(f"{r['symbol']} | score={r['score']:.4f}")

    # =====================
    # UPDATE POSITIONS
    # =====================
    try:
        pm.update_positions(price_map)
    except Exception as e:
        print("Update error:", e)

    # =====================
    # EXIT LOGIC
    # =====================
    print("\n--- POSITION DEBUG ---")

    for sym, pos in list(pm.positions.items()):
        entry = safe_float(pos.get("entry_price"))
        current = safe_float(price_map.get(sym))

        if entry <= 0 or current <= 0:
            continue

        pnl = (current - entry) / entry
        position_cycles[sym] = position_cycles.get(sym, 0) + 1

        print(f"{sym} | pnl={pnl:.4%} | cycles={position_cycles[sym]}")

        if pnl >= TP_PCT:
            pm.close_position(sym, current, "TP")
            position_cycles.pop(sym, None)

        elif pnl <= -SL_PCT:
            pm.close_position(sym, current, "SL")
            position_cycles.pop(sym, None)

        elif position_cycles[sym] >= MAX_HOLD_CYCLES:
            pm.close_position(sym, current, "TIME")
            position_cycles.pop(sym, None)

    # =====================
    # CRYPTO ENTRY
    # =====================
    crypto_open = len(pm.positions)

    for r in rows:
        if crypto_open >= MAX_CRYPTO:
            break

        if r["symbol"] in pm.positions:
            continue

        if r["score"] < MIN_SCORE:
            continue

        tp, sl = build_tp_sl(r["price"])

        try:
            pm.open_position(
                symbol=r["symbol"],
                entry_price=r["price"],
                size=1,
                take_profit=tp,
                stop_loss=sl,
                side="LONG",
                confidence=r["score"]
            )

            print(f"[CRYPTO OPEN] {r['symbol']} @ {r['price']:.2f}")
            crypto_open += 1

        except Exception as e:
            print(e)

    # =====================
    # FUTURES ENTRY
    # =====================
    futures_open = len(futures_pm.get_open_positions())

    for f in FUTURES_SYMBOLS:
        if futures_open >= MAX_FUTURES:
            break

        try:
            result = futures_pm.open_position(
                symbol=f,
                entry_price=100,
                stop_price=99,
                contracts=1,
                current_equity=10000,
                state={}
            )

            if result.get("status") == "OPENED":
                print(f"[FUTURES OPEN] {f}")
                futures_open += 1

        except Exception as e:
            print(f"Futures error: {e}")

    # =====================
    # OPTIONS SCAN
    # =====================
    try:
        option_rows = options_adapter.fetch_option_rows(rows)
        print(f"\n--- OPTIONS SCAN --- {len(option_rows)} contracts visible")
    except Exception as e:
        print("Options error:", e)

    # =====================
    # STATUS
    # =====================
    print("\n--- STATUS ---")
    print(f"Crypto Open: {len(pm.positions)}")
    print(f"Futures Open: {len(futures_pm.get_open_positions())}")

    # =====================
    # STORE PRICES
    # =====================
    for r in rows:
        if r["price"] > 0:
            previous_prices[r["symbol"]] = r["price"]

    time.sleep(CYCLE_SLEEP)