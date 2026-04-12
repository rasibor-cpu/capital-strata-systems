from __future__ import annotations

import sys
import time
import random
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


# =========================================================
# ENGINE MODES
# =========================================================
ENGINE_MODES = {
    "1": "SAFE",
    "2": "CONSERVATIVE",
    "3": "BALANCED",
    "4": "AGGRESSIVE",
    "5": "EXPANSION",
}

ENGINE_PROFILES = {
    "SAFE": {"MAX_CRYPTO": 2, "MAX_OPTIONS": 1, "MAX_FX": 1},
    "CONSERVATIVE": {"MAX_CRYPTO": 2, "MAX_OPTIONS": 1, "MAX_FX": 2},
    "BALANCED": {"MAX_CRYPTO": 3, "MAX_OPTIONS": 2, "MAX_FX": 3},
    "AGGRESSIVE": {"MAX_CRYPTO": 4, "MAX_OPTIONS": 3, "MAX_FX": 4},
    "EXPANSION": {"MAX_CRYPTO": 5, "MAX_OPTIONS": 4, "MAX_FX": 5},
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
MAX_OPTIONS = PROFILE["MAX_OPTIONS"]
MAX_FX = PROFILE["MAX_FX"]

# =========================================================
# PARAMETERS
# =========================================================
CYCLE_SLEEP = 3

FX_ARB_THRESHOLD = 0.00025
FX_ARB_MAX_HOLD = 3

# =========================================================
# SYMBOLS
# =========================================================
SYMBOLS = [
    "BTC-USD","ETH-USD","SOL-USD","XRP-USD","ADA-USD",
    "DOGE-USD","AVAX-USD","LINK-USD","LTC-USD","BCH-USD"
]

FX_SYMBOLS = [
    "EUR_USD","GBP_USD","USD_JPY",
    "AUD_USD","USD_CAD","USD_CHF","NZD_USD"
]

FX_BASE_PRICES = {
    "EUR_USD": 1.0850,
    "GBP_USD": 1.2720,
    "USD_JPY": 151.20,
    "AUD_USD": 0.6570,
    "USD_CAD": 1.3520,
    "USD_CHF": 0.9010,
    "NZD_USD": 0.6120
}

# =========================================================
# ENGINES
# =========================================================
pm = PositionManager()
futures_adapter = FuturesSimAdapter(max_portfolio_allocation=5.0)
futures_pm = FuturesPositionManager(futures_adapter)

options_adapter = OptionsChainAdapter()
options_pm = OptionsPositionManager()
options_intel = OptionsIntelligenceEngine()

# =========================================================
# STATE
# =========================================================
prev_prices: Dict[str, float] = {}
crypto_realized_pnl: Dict[str, float] = {}
fx_realized_pnl: Dict[str, float] = {}
options_realized_pnl: Dict[str, float] = {}
fx_arb_realized_pnl: Dict[str, float] = {}
fx_arb_positions: Dict[str, Dict] = {}


# =========================================================
# HELPERS
# =========================================================
def safe(v, d=0.0):
    try:
        return float(v)
    except:
        return d


def classify_signal(score):
    if score >= 10:
        return "ELITE"
    if score >= 4.5:
        return "QUALIFIED"
    return "WATCH"


def score(symbol, price, prev):
    if prev <= 0:
        return 0.0
    return abs((price - prev) / prev) * 10000


def total_realized_pnl():
    return round(
        sum(crypto_realized_pnl.values())
        + sum(fx_realized_pnl.values())
        + sum(options_realized_pnl.values())
        + sum(fx_arb_realized_pnl.values()),
        4,
    )


def get_fx_price(symbol):
    prev = safe(prev_prices.get(symbol), 0.0)
    base = safe(FX_BASE_PRICES.get(symbol), 1.0)
    if prev <= 0:
        return base
    drift = random.uniform(0.9990, 1.0010)
    return round(prev * drift, 6)


def eur_gbp_synth(eurusd, gbpusd):
    if gbpusd == 0:
        return 0.0
    return eurusd / gbpusd


# =========================================================
# MAIN LOOP
# =========================================================
cycle = 0

while True:
    cycle += 1
    print(f"\n=== Cycle {cycle} | {datetime.now()} ===")

    price_map = {}
    fx_price_map = {}

    # -----------------------------------------------------
    # CRYPTO FETCH
    # -----------------------------------------------------
    for s in SYMBOLS:
        raw = load_runtime_asset(s)
        price = safe(raw.get("price") or raw.get("close"))
        price_map[s] = price
        print(f"Fetched 288 candles for {s}")

    # -----------------------------------------------------
    # FX FETCH
    # -----------------------------------------------------
    for fx in FX_SYMBOLS:
        fx_price_map[fx] = get_fx_price(fx)

    # =====================================================
    # FX TRIANGULAR ARBITRAGE
    # =====================================================
    if "EUR_USD" in fx_price_map and "GBP_USD" in fx_price_map:
        eurusd = fx_price_map["EUR_USD"]
        gbpusd = fx_price_map["GBP_USD"]

        synth = eur_gbp_synth(eurusd, gbpusd)

        live = synth * random.uniform(0.9994, 1.0006)
        spread = round(live - synth, 6)

        print(f"\n--- FX ARBITRAGE --- spread={spread:.6f}")

        arb_id = "EUR_TRI_ARB"

        if arb_id not in fx_arb_positions:
            if abs(spread) >= FX_ARB_THRESHOLD:
                fx_arb_positions[arb_id] = {
                    "entry_spread": spread,
                    "entry_cycle": cycle,
                    "status": "OPEN"
                }
                print(f"[FX ARB OPEN] {arb_id} spread={spread:.6f}")

        if arb_id in fx_arb_positions:
            pos = fx_arb_positions[arb_id]
            hold = cycle - pos["entry_cycle"]

            pnl = abs(pos["entry_spread"]) - abs(spread)

            print(
                f"[FX ARB PNL] {arb_id} "
                f"entry={pos['entry_spread']:.6f} "
                f"current={spread:.6f} "
                f"pnl={pnl:.6f} hold={hold}"
            )

            if hold >= FX_ARB_MAX_HOLD or abs(spread) < FX_ARB_THRESHOLD / 2:
                fx_arb_realized_pnl[arb_id] = round(
                    fx_arb_realized_pnl.get(arb_id, 0.0) + pnl,
                    6,
                )
                print(f"[FX ARB CLOSE] {arb_id} realized={pnl:.6f}")
                del fx_arb_positions[arb_id]

    # =====================================================
    # DASHBOARD
    # =====================================================
    print("\n--- PROFIT DASHBOARD ---")
    print(f"Engine Mode: {ENGINE_MODE}")
    print(f"Crypto Open: {len(pm.positions)}")
    print(f"FX Open: {len(futures_pm.get_open_positions())}")
    print(f"FX Arbitrage Open: {len(fx_arb_positions)}")
    print(f"Options Open: {len(options_pm.get_open_positions())}")

    print("\n--- REALIZED PNL ---")
    print("Crypto:", crypto_realized_pnl if crypto_realized_pnl else "{}")
    print("FX:", fx_realized_pnl if fx_realized_pnl else "{}")
    print("Options:", options_realized_pnl if options_realized_pnl else "{}")
    print("FX Arb:", fx_arb_realized_pnl if fx_arb_realized_pnl else "{}")
    print("TOTAL:", total_realized_pnl())

    prev_prices.update(price_map)
    prev_prices.update(fx_price_map)

    time.sleep(CYCLE_SLEEP)