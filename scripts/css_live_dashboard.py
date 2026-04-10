from __future__ import annotations

import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.data.coinbase_historical_downloader import load_runtime_asset
from backend.execution.position_manager import PositionManager
from backend.app.brokers.futures_sim_adapter import FuturesSimAdapter
from backend.app.risk.futures_position_manager import FuturesPositionManager
from backend.scanner.options_chain_adapter import OptionsChainAdapter
from backend.options.options_position_manager import OptionsPositionManager

# ========================
# ENGINE MODES
# ========================
ENGINE_MODES = {
    "1": "SAFE",
    "2": "CONSERVATIVE",
    "3": "BALANCED",
    "4": "AGGRESSIVE",
    "5": "EXPANSION",
}

ENGINE_PROFILES = {
    "SAFE": {"MAX_CRYPTO": 2, "MIN_SCORE": 0.12, "MIN_EXPECTED_MOVE": 0.0008, "PROFIT_BUFFER": 1.2},
    "CONSERVATIVE": {"MAX_CRYPTO": 2, "MIN_SCORE": 0.10, "MIN_EXPECTED_MOVE": 0.0007, "PROFIT_BUFFER": 1.12},
    "BALANCED": {"MAX_CRYPTO": 3, "MIN_SCORE": 0.08, "MIN_EXPECTED_MOVE": 0.0005, "PROFIT_BUFFER": 1.05},
    "AGGRESSIVE": {"MAX_CRYPTO": 4, "MIN_SCORE": 0.06, "MIN_EXPECTED_MOVE": 0.0004, "PROFIT_BUFFER": 1.0},
    "EXPANSION": {"MAX_CRYPTO": 5, "MIN_SCORE": 0.05, "MIN_EXPECTED_MOVE": 0.0003, "PROFIT_BUFFER": 0.95},
}

def select_engine_mode():
    print("\n=== CSS ENGINE MODE SELECTOR ===")
    for k, v in ENGINE_MODES.items():
        print(f"{k}. {v}")
    choice = input("Enter choice (1-5) [default=3]: ").strip()
    return ENGINE_MODES.get(choice, "BALANCED")

ENGINE_MODE = select_engine_mode()
PROFILE = ENGINE_PROFILES[ENGINE_MODE]

# ========================
# CONFIG
# ========================
CYCLE_SLEEP = 3
MAX_CRYPTO = PROFILE["MAX_CRYPTO"]
MIN_SCORE = PROFILE["MIN_SCORE"]
MIN_EXPECTED_MOVE = PROFILE["MIN_EXPECTED_MOVE"]
PROFIT_BUFFER = PROFILE["PROFIT_BUFFER"]
ESTIMATED_COST = 0.0006

TP_PCT = 0.006
SL_PCT = 0.004
MAX_HOLD = 3

SYMBOLS = ["BTC-USD","ETH-USD","SOL-USD","XRP-USD","ADA-USD","DOGE-USD","AVAX-USD","LINK-USD","LTC-USD","BCH-USD"]
FUTURES_SYMBOLS = ["ES","NQ"]

# ========================
# INIT
# ========================
pm = PositionManager()
futures_adapter = FuturesSimAdapter(max_portfolio_allocation=5.0)
futures_pm = FuturesPositionManager(futures_adapter)
options_adapter = OptionsChainAdapter()
options_pm = OptionsPositionManager()

prev_prices: Dict[str,float] = {}
pos_cycles: Dict[str,int] = {}

# ========================
# HELPERS
# ========================
def safe(v, d=0.0):
    try: return float(v)
    except: return d

def classify_signal(score):
    if score >= 10: return "ELITE"
    if score >= 7: return "QUALIFIED"
    return "WATCH"

def required_move():
    return max(MIN_EXPECTED_MOVE, ESTIMATED_COST * PROFIT_BUFFER)

def is_profitable(score, tier):
    return (score/10000.0) >= required_move()

def size_for(tier):
    return 1.0 if tier=="ELITE" else 0.5 if tier=="QUALIFIED" else 0.0

def score(symbol, price, prev):
    if prev<=0: return 0.0
    return abs((price-prev)/prev)*10000

# ========================
# LOOP
# ========================
cycle = 0

while True:
    cycle += 1
    print(f"\n=== Cycle {cycle} | {datetime.now()} ===")

    rows=[]
    price_map={}

    for s in SYMBOLS:
        try:
            raw = load_runtime_asset(s)
            price = safe(raw.get("price") or raw.get("close"))
            sc = score(s, price, prev_prices.get(s,0))
            rows.append({"symbol":s,"price":price,"score":sc})
            price_map[s]=price
        except Exception as e:
            print(f"[DATA ERROR] {s}: {e}")

    rows.sort(key=lambda x:-x["score"])

    print("\n--- CRYPTO ---")
    for r in rows[:5]:
        tier = classify_signal(r["score"])
        print(f"{r['symbol']} | score={r['score']:.2f} | tier={tier} | profitable={'Y' if is_profitable(r['score'],tier) else 'N'}")

    # ===== UPDATE CRYPTO =====
    pm.update_positions(price_map)

    for sym,pos in list(pm.positions.items()):
        entry = safe(pos.get("entry_price"))
        cur = safe(price_map.get(sym))
        pnl = (cur-entry)/entry if entry>0 else 0
        pos_cycles[sym] = pos_cycles.get(sym,0)+1

        print(f"{sym} | size={pos.get('size')} | pnl={pnl:.4%}")

        if pnl>=TP_PCT or pnl<=-SL_PCT or pos_cycles[sym]>=MAX_HOLD:
            pm.close_position(sym,cur,"TIME")
            pos_cycles.pop(sym,None)

    # ===== ENTRY =====
    open_crypto=len(pm.positions)

    for r in rows:
        if open_crypto>=MAX_CRYPTO: break
        if r["symbol"] in pm.positions: continue
        if r["score"]<MIN_SCORE: continue

        tier = classify_signal(r["score"])
        if tier=="WATCH": continue
        if not is_profitable(r["score"],tier): continue

        size = size_for(tier)
        if size<=0: continue

        try:
            pm.open_position(
                symbol=r["symbol"],
                entry_price=r["price"],
                size=size,
                take_profit=r["price"]*(1+TP_PCT),
                stop_loss=r["price"]*(1-SL_PCT),
                side="LONG"
            )
            print(f"[CRYPTO OPEN] {r['symbol']} ({tier}) size={size}")
            open_crypto+=1
        except Exception as e:
            print(e)

    # ===== OPTIONS =====
    option_rows=[]
    executed_options=0

    try:
        opts = options_adapter.fetch_option_rows(
            [{"symbol":r["symbol"],"price":r["price"]} for r in rows[:3]]
        )
        option_rows=opts
        print(f"\nOptions Visible: {len(opts)}")

        for opt in opts[:5]:
            underlying = opt.get("symbol")
            premium = safe(opt.get("price"),0.01)
            score_val = next((r["score"] for r in rows if r["symbol"]==underlying),0)

            tier = classify_signal(score_val)
            if tier=="WATCH": continue
            if not is_profitable(score_val,tier): continue

            res = options_pm.open_long_option(
                option_symbol=f"{underlying}_OPT",
                underlying_symbol=underlying,
                option_type="CALL",
                strike=0,
                expiry="NA",
                entry_price=premium,
                current_cycle=cycle,
                confidence=score_val,
                tier=tier
            )

            if res.get("status")=="OPENED":
                print(f"[OPTIONS OPEN] {underlying} ({tier})")
                executed_options+=1

    except Exception as e:
        print(e)

    # ===== OPTIONS UPDATE =====
    option_price_map = {
        f"{o.get('symbol')}_OPT": safe(o.get("price"),0.01)
        for o in option_rows
    }

    events = options_pm.update_positions(option_price_map,current_cycle=cycle)

    for e in events:
        print(f"[OPTIONS CLOSED] {e.get('option_symbol')} pnl={e.get('pnl')}")

    # ===== DASHBOARD =====
    print("\n--- PROFIT DASHBOARD ---")
    print(f"Engine Mode: {ENGINE_MODE}")
    print(f"Crypto Open: {len(pm.positions)}")
    print(f"Options Open: {len(options_pm.get_open_positions())}")

    prev_prices.update(price_map)

    time.sleep(CYCLE_SLEEP)