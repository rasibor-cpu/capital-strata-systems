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
    "SAFE": {"MAX_CRYPTO": 2, "MAX_OPTIONS": 1, "MAX_FX": 1, "MAX_FUTURES": 1},
    "CONSERVATIVE": {"MAX_CRYPTO": 2, "MAX_OPTIONS": 1, "MAX_FX": 2, "MAX_FUTURES": 2},
    "BALANCED": {"MAX_CRYPTO": 3, "MAX_OPTIONS": 2, "MAX_FX": 3, "MAX_FUTURES": 3},
    "AGGRESSIVE": {"MAX_CRYPTO": 4, "MAX_OPTIONS": 3, "MAX_FX": 4, "MAX_FUTURES": 4},
    "EXPANSION": {"MAX_CRYPTO": 5, "MAX_OPTIONS": 4, "MAX_FX": 5, "MAX_FUTURES": 5},
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
MAX_FUTURES = PROFILE["MAX_FUTURES"]

# =========================================================
# PARAMETERS
# =========================================================
CYCLE_SLEEP = 3
FX_ARB_THRESHOLD = 0.00025
FX_ARB_MAX_HOLD = 3

SIMULATED_EQUITY = 100000.0

FUTURES_MAX_HOLD = 6
FUTURES_SIGNAL_THRESHOLD = 9.5
FUTURES_CONFIRM_THRESHOLD = 4.0
FUTURES_STOP_PCT = 0.0025

BASE_FUTURES_PROFIT_TARGET = 3.0
DEFAULT_MAX_LOSS = -4.0

SYMBOL_MAX_LOSS = {
    "ES": -5.0,
    "NQ": -3.5,
    "CL": -3.0,
    "GC": -3.5,
}

# =========================================================
# SYMBOLS
# =========================================================
SYMBOLS = [
    "BTC-USD", "ETH-USD", "SOL-USD", "XRP-USD", "ADA-USD",
    "DOGE-USD", "AVAX-USD", "LINK-USD", "LTC-USD", "BCH-USD"
]

FX_SYMBOLS = [
    "EUR_USD", "GBP_USD", "USD_JPY",
    "AUD_USD", "USD_CAD", "USD_CHF", "NZD_USD"
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

FUTURES_SYMBOLS = ["ES", "NQ", "CL", "GC"]
FUTURES_BASE_PRICES = {
    "ES": 5200.0,
    "NQ": 18250.0,
    "CL": 78.50,
    "GC": 2185.0,
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
futures_realized_pnl: Dict[str, float] = {}
options_realized_pnl: Dict[str, float] = {}
fx_arb_realized_pnl: Dict[str, float] = {}
fx_arb_positions: Dict[str, Dict] = {}
futures_signal_memory: Dict[str, float] = {}

# F9 accelerated learning state
futures_symbol_bias: Dict[str, float] = {
    "ES": 1.0,
    "NQ": 1.0,
    "CL": 1.0,
    "GC": 1.0,
}

futures_loss_streak: Dict[str, int] = {
    "ES": 0,
    "NQ": 0,
    "CL": 0,
    "GC": 0,
}

# =========================================================
# HELPERS
# =========================================================
def safe(v, d=0.0):
    try:
        return float(v)
    except Exception:
        return d


def score(symbol, price, prev):
    if prev <= 0:
        return 0.0
    return abs((price - prev) / prev) * 10000


def total_realized_pnl():
    return round(
        sum(crypto_realized_pnl.values())
        + sum(fx_realized_pnl.values())
        + sum(futures_realized_pnl.values())
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


def get_futures_price(symbol):
    prev = safe(prev_prices.get(symbol), 0.0)
    base = safe(FUTURES_BASE_PRICES.get(symbol), 100.0)
    if prev <= 0:
        return base
    drift = random.uniform(0.9985, 1.0015)
    return round(prev * drift, 4)


def eur_gbp_synth(eurusd, gbpusd):
    if gbpusd == 0:
        return 0.0
    return eurusd / gbpusd


def get_open_futures_count() -> int:
    try:
        return len(futures_pm.get_open_positions())
    except Exception:
        return 0


# =========================================================
# F7 CONTRACT GOVERNOR
# =========================================================
def determine_contract_size(symbol, signal_score, prior_score):
    if signal_score >= 14:
        base = 3
    elif signal_score >= 11:
        base = 2
    else:
        base = 1

    if prior_score < 8:
        base = min(base, 1)
    elif prior_score < 10:
        base = min(base, 2)

    if symbol == "NQ":
        base = min(base, 1)
    elif symbol == "CL":
        base = min(base, 1)
    elif symbol == "GC":
        base = min(base, 2)

    return max(1, base)


# =========================================================
# F9 ACCELERATED REINFORCEMENT ENGINE
# =========================================================
def get_symbol_bias(symbol):
    return futures_symbol_bias.get(symbol, 1.0)


def adjust_symbol_bias(symbol, pnl):
    current = futures_symbol_bias.get(symbol, 1.0)

    if pnl > 0:
        futures_loss_streak[symbol] = 0
        current *= 1.20
    else:
        futures_loss_streak[symbol] += 1
        streak = futures_loss_streak[symbol]

        if streak >= 3:
            current *= 0.65
        elif streak == 2:
            current *= 0.75
        else:
            current *= 0.85

    current = max(0.25, min(2.25, current))
    futures_symbol_bias[symbol] = current


def allocation_weighted_score(symbol, raw_score):
    bias = get_symbol_bias(symbol)
    return raw_score * bias


# =========================================================
# MAIN LOOP
# =========================================================
cycle = 0

while True:
    cycle += 1
    print(f"\n=== Cycle {cycle} | {datetime.now()} ===")

    price_map = {}
    fx_price_map = {}
    futures_price_map = {}

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

    # -----------------------------------------------------
    # FUTURES FETCH
    # -----------------------------------------------------
    for fut in FUTURES_SYMBOLS:
        futures_price_map[fut] = get_futures_price(fut)

    # =====================================================
    # FUTURES ENTRY ENGINE
    # =====================================================
    for fut in FUTURES_SYMBOLS:
        current_price = futures_price_map[fut]
        prev_price = safe(prev_prices.get(fut), current_price)

        raw_score = score(fut, current_price, prev_price)
        fut_score = allocation_weighted_score(fut, raw_score)
        prior_score = safe(futures_signal_memory.get(fut), 0.0)

        score_confirmed = (
            fut_score >= FUTURES_SIGNAL_THRESHOLD
            and prior_score >= FUTURES_CONFIRM_THRESHOLD
        )
        upward_momentum = current_price > prev_price

        if (
            score_confirmed
            and upward_momentum
            and not futures_pm.has_open_position_for_symbol(fut)
            and get_open_futures_count() < MAX_FUTURES
        ):
            stop_price = current_price * (1.0 - FUTURES_STOP_PCT)

            contracts = determine_contract_size(
                fut,
                fut_score,
                prior_score
            )

            result = futures_pm.open_position_if_allowed(
                symbol=fut,
                entry_price=current_price,
                stop_price=stop_price,
                contracts=contracts,
                current_equity=SIMULATED_EQUITY,
                state={}
            )

            if result.get("status") == "OPENED":
                pos = result["position"]
                futures_pm.mark_position_cycle_metadata(
                    position_id=pos["position_id"],
                    entry_cycle=cycle,
                    signal_score=fut_score,
                )

                print(
                    f"[FUTURES OPEN] {fut} "
                    f"entry={current_price:.4f} "
                    f"contracts={contracts} "
                    f"score={fut_score:.2f} "
                    f"bias={get_symbol_bias(fut):.2f}"
                )

        futures_signal_memory[fut] = fut_score

    # =====================================================
    # FUTURES EXIT ENGINE
    # =====================================================
    open_futures = futures_pm.get_open_positions()

    for pos in open_futures:
        symbol = pos["symbol"]
        current_price = futures_price_map.get(symbol, pos["entry_price"])
        entry_price = float(pos["entry_price"])

        # FIXED keyword-only call
        hold = futures_pm.get_position_hold_cycles(
            position=pos,
            current_cycle=cycle
        )

        contracts = int(pos.get("contracts", 1))
        unrealized = (current_price - entry_price) * contracts

        signal_score = float(pos.get("signal_score", 0.0))

        dynamic_profit_target = BASE_FUTURES_PROFIT_TARGET
        if signal_score >= 15:
            dynamic_profit_target = 6.0
        elif signal_score >= 12:
            dynamic_profit_target = 4.5
        elif signal_score >= 10:
            dynamic_profit_target = 3.5

        dynamic_profit_target *= contracts

        symbol_max_loss = SYMBOL_MAX_LOSS.get(symbol, DEFAULT_MAX_LOSS)
        symbol_max_loss *= contracts

        hit_profit_target = unrealized >= dynamic_profit_target
        hit_max_loss = unrealized <= symbol_max_loss
        hit_time_exit = hold >= FUTURES_MAX_HOLD

        if hit_profit_target or hit_max_loss or hit_time_exit:
            close_result = futures_pm.close_position(
                position_id=pos["position_id"],
                exit_price=current_price,
            )

            if close_result.get("status") == "CLOSED":
                pnl = float(close_result["position"]["pnl"])

                futures_realized_pnl[symbol] = round(
                    futures_realized_pnl.get(symbol, 0.0) + pnl,
                    4,
                )

                adjust_symbol_bias(symbol, pnl)

                exit_reason = "TIME"
                if hit_profit_target:
                    exit_reason = "TP"
                elif hit_max_loss:
                    exit_reason = "SL"

                print(
                    f"[FUTURES CLOSE] {symbol} "
                    f"exit={current_price:.4f} pnl={pnl:.4f} "
                    f"hold={hold} reason={exit_reason} "
                    f"new_bias={get_symbol_bias(symbol):.2f} "
                    f"loss_streak={futures_loss_streak[symbol]}"
                )

    # =====================================================
    # FX ARBITRAGE
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
    print(f"FX Open: {len(fx_realized_pnl)}")
    print(f"Futures Open: {len(futures_pm.get_open_positions())}")
    print(f"FX Arbitrage Open: {len(fx_arb_positions)}")
    print(f"Options Open: {len(options_pm.get_open_positions())}")

    print("\n--- REALIZED PNL ---")
    print("Crypto:", crypto_realized_pnl if crypto_realized_pnl else "{}")
    print("FX:", fx_realized_pnl if fx_realized_pnl else "{}")
    print("Futures:", futures_realized_pnl if futures_realized_pnl else "{}")
    print("Options:", options_realized_pnl if options_realized_pnl else "{}")
    print("FX Arb:", fx_arb_realized_pnl if fx_arb_realized_pnl else "{}")
    print("TOTAL:", total_realized_pnl())

    print("\n--- FUTURES SYMBOL BIAS ---")
    print(futures_symbol_bias)

    print("\n--- FUTURES LOSS STREAK ---")
    print(futures_loss_streak)

    prev_prices.update(price_map)
    prev_prices.update(fx_price_map)
    prev_prices.update(futures_price_map)

    time.sleep(CYCLE_SLEEP)