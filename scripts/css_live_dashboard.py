from __future__ import annotations

import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.data.coinbase_historical_downloader import load_runtime_asset
from backend.execution.position_manager import PositionManager
from backend.app.brokers.futures_sim_adapter import FuturesSimAdapter
from backend.app.risk.futures_position_manager import FuturesPositionManager
from backend.scanner.options_chain_adapter import OptionsChainAdapter
from backend.options.options_position_manager import OptionsPositionManager
from backend.options.options_intelligence_engine import OptionsIntelligenceEngine

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
    "SAFE": {"MAX_CRYPTO": 2, "MAX_OPTIONS": 1},
    "CONSERVATIVE": {"MAX_CRYPTO": 2, "MAX_OPTIONS": 1},
    "BALANCED": {"MAX_CRYPTO": 3, "MAX_OPTIONS": 2},
    "AGGRESSIVE": {"MAX_CRYPTO": 4, "MAX_OPTIONS": 3},
    "EXPANSION": {"MAX_CRYPTO": 5, "MAX_OPTIONS": 4},
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
MAX_OPTIONS = PROFILE["MAX_OPTIONS"]

MIN_SCORE = 0.08
TP_PCT = 0.006
SL_PCT = 0.004
MAX_HOLD = 3

OPTION_MIN_PREMIUM = 0.001
OPTION_MAX_PREMIUM = 50.0
OPTION_PREMIUM_TO_UNDERLYING_MAX = 0.40

SYMBOLS = [
    "BTC-USD","ETH-USD","SOL-USD","XRP-USD",
    "ADA-USD","DOGE-USD","AVAX-USD","LINK-USD",
    "LTC-USD","BCH-USD"
]

# ========================
# INIT
# ========================
pm = PositionManager()
futures_adapter = FuturesSimAdapter(max_portfolio_allocation=5.0)
futures_pm = FuturesPositionManager(futures_adapter)

options_adapter = OptionsChainAdapter()
options_pm = OptionsPositionManager()
options_intel = OptionsIntelligenceEngine()

prev_prices: Dict[str, float] = {}
pos_cycles: Dict[str, int] = {}

# ========================
# HELPERS
# ========================
def safe(v, d=0.0):
    try:
        return float(v)
    except Exception:
        return d


def classify_signal(score):
    if score >= 10:
        return "ELITE"
    if score >= 4.5:
        return "QUALIFIED"
    return "WATCH"


def size_for(tier):
    return 1.0 if tier == "ELITE" else 0.5 if tier == "QUALIFIED" else 0.0


def score(symbol, price, prev):
    if prev <= 0:
        return 0.0
    return abs((price - prev) / prev) * 10000


def option_symbol(underlying, best):
    strike = safe(best.get("strike"))
    expiry = str(best.get("expiry") or "NA")
    return f"{underlying}_CALL_{strike:.2f}_{expiry}"


# =========================================================
# DIAGNOSTIC EDGE MODEL
# =========================================================
def option_has_sufficient_edge(score_value, premium, underlying_price, tier):
    if underlying_price <= 0:
        return False, "bad underlying"

    expected_move = (score_value / 10000.0) * 1.8
    premium_cost = premium / underlying_price

    if premium_cost <= 0:
        return False, "bad premium cost"

    if tier == "ELITE":
        factor = 0.35
    elif tier == "QUALIFIED":
        factor = 0.45
    else:
        return False, "watch tier"

    hurdle = premium_cost * factor
    passed = expected_move >= hurdle

    print(
        f"[OPTION DIAG] "
        f"score={score_value:.2f} "
        f"exp_move={expected_move:.6f} "
        f"premium={premium:.6f} "
        f"ratio={premium_cost:.6f} "
        f"hurdle={hurdle:.6f} "
        f"tier={tier}"
    )

    if not passed:
        return False, "weak edge"

    return True, "pass"


def option_has_reasonable_premium(premium, underlying_price):
    if premium < OPTION_MIN_PREMIUM:
        return False, "premium too low"
    if premium > OPTION_MAX_PREMIUM:
        return False, "premium too high"
    if underlying_price <= 0:
        return False, "bad underlying"
    if (premium / underlying_price) > OPTION_PREMIUM_TO_UNDERLYING_MAX:
        return False, "premium ratio too high"
    return True, "pass"


# ========================
# LOOP
# ========================
cycle = 0

while True:
    cycle += 1
    print(f"\n=== Cycle {cycle} | {datetime.now()} ===")

    rows = []
    price_map = {}

    for s in SYMBOLS:
        try:
            raw = load_runtime_asset(s)
            price = safe(raw.get("price") or raw.get("close"))
            sc = score(s, price, prev_prices.get(s, 0))
            rows.append({"symbol": s, "price": price, "score": sc})
            price_map[s] = price
        except Exception as e:
            print(f"[DATA ERROR] {s}: {e}")

    rows.sort(key=lambda x: -x["score"])

    print("\n--- CRYPTO ---")
    for r in rows[:5]:
        tier = classify_signal(r["score"])
        print(f"{r['symbol']} | score={r['score']:.2f} | tier={tier}")

    pm.update_positions(price_map)

    for sym, pos in list(pm.positions.items()):
        entry = safe(pos.get("entry_price"))
        cur = safe(price_map.get(sym))
        pnl = (cur - entry) / entry if entry > 0 else 0
        pos_cycles[sym] = pos_cycles.get(sym, 0) + 1

        print(f"{sym} | size={pos.get('size')} | pnl={pnl:.4%}")

        if pnl >= TP_PCT or pnl <= -SL_PCT or pos_cycles[sym] >= MAX_HOLD:
            pm.close_position(sym, cur, "TIME")
            pos_cycles.pop(sym, None)

    # ===== CRYPTO ENTRY =====
    open_crypto = len(pm.positions)

    for r in rows:
        if open_crypto >= MAX_CRYPTO:
            break
        if r["symbol"] in pm.positions:
            continue

        tier = classify_signal(r["score"])
        if tier == "WATCH":
            continue

        size = size_for(tier)
        if size <= 0:
            continue

        pm.open_position(
            symbol=r["symbol"],
            entry_price=r["price"],
            size=size,
            take_profit=r["price"] * (1 + TP_PCT),
            stop_loss=r["price"] * (1 - SL_PCT),
            side="LONG"
        )

        print(f"[CRYPTO OPEN] {r['symbol']} ({tier}) size={size}")
        open_crypto += 1

    # ===== OPTIONS =====
    option_rows = []
    executed_options = 0

    try:
        opts = options_adapter.fetch_option_rows(
            [{"symbol": r["symbol"], "price": r["price"]} for r in rows[:3]]
        )

        option_rows = opts
        print(f"\nOptions Visible: {len(opts)}")

        open_options = len(options_pm.get_open_positions())

        for r in rows[:3]:
            if open_options >= MAX_OPTIONS:
                break

            underlying = r["symbol"]
            tier = classify_signal(r["score"])

            if tier == "WATCH":
                continue

            best = options_intel.select_best_option(
                options=[o for o in opts if o.get("symbol") == underlying],
                underlying_price=r["price"],
                score=r["score"],
                tier=tier
            )

            if not best:
                print(f"[OPTIONS FILTERED] {underlying} no contract")
                continue

            premium = safe(best.get("price"), 0.0)

            ok_premium, reason = option_has_reasonable_premium(
                premium, r["price"]
            )
            if not ok_premium:
                print(f"[OPTIONS FILTERED] {underlying} {reason}")
                continue

            ok_edge, edge_reason = option_has_sufficient_edge(
                r["score"], premium, r["price"], tier
            )
            if not ok_edge:
                print(f"[OPTIONS FILTERED] {underlying} {edge_reason}")
                continue

            sym = option_symbol(underlying, best)

            if sym in options_pm.positions:
                continue

            res = options_pm.open_long_option(
                option_symbol=sym,
                underlying_symbol=underlying,
                option_type="CALL",
                strike=safe(best.get("strike")),
                expiry=str(best.get("expiry")),
                entry_price=premium,
                contracts=1,
                current_cycle=cycle,
                confidence=r["score"],
                tier=tier
            )

            if res.get("status") == "OPENED":
                print(f"[OPTIONS OPEN] {sym} ({tier}) premium={premium:.4f}")
                executed_options += 1
                open_options += 1

    except Exception as e:
        print(f"[OPTIONS ERROR] {e}")

    print("\n--- PROFIT DASHBOARD ---")
    print(f"Engine Mode: {ENGINE_MODE}")
    print(f"Crypto Open: {len(pm.positions)}")
    print(f"Options Open: {len(options_pm.get_open_positions())}")
    print(f"Executed Options This Cycle: {executed_options}")

    prev_prices.update(price_map)
    time.sleep(CYCLE_SLEEP)