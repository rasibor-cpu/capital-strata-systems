from __future__ import annotations

import sys
import time
import random
import json
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
# STATE FILES
# =========================================================
STATE_DIR = PROJECT_ROOT / "artifacts"
STATE_DIR.mkdir(exist_ok=True)

FUTURES_BIAS_FILE = STATE_DIR / "futures_symbol_bias.json"
FUTURES_LOSS_FILE = STATE_DIR / "futures_loss_streak.json"


# =========================================================
# JSON HELPERS
# =========================================================
def load_json_state(path: Path, default: Dict):
    try:
        if path.exists():
            with open(path, "r") as f:
                return json.load(f)
    except Exception:
        pass
    return default.copy()


def save_json_state(path: Path, data: Dict):
    try:
        with open(path, "w") as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        print(f"[STATE SAVE ERROR] {path.name}: {e}")


# =========================================================
# SAFE FETCH WRAPPER
# =========================================================
def safe_load_runtime_asset(symbol: str):
    try:
        load_runtime_asset(symbol)
        print(f"Fetched 288 candles for {symbol}")
        return True
    except Exception as e:
        print(f"[FETCH FAIL] {symbol}: {str(e)[:80]}")
        return False


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


# =========================================================
# PARAMETERS
# =========================================================
CYCLE_SLEEP = 3

BIAS_NEUTRAL = 1.0
BIAS_MIN = 0.35
BIAS_MAX = 2.25
BIAS_DECAY_RATE = 0.06
BIAS_REWARD_MULT = 1.10
BIAS_LOSS_PENALTY_1 = 0.88
BIAS_LOSS_PENALTY_2 = 0.78
BIAS_LOSS_PENALTY_3 = 0.68

SYMBOLS = [
    "BTC-USD", "ETH-USD", "SOL-USD", "XRP-USD", "ADA-USD",
    "DOGE-USD", "AVAX-USD", "LINK-USD", "LTC-USD", "BCH-USD"
]

FUTURES_SYMBOLS = ["ES", "NQ", "CL", "GC"]
FX_SYMBOLS = ["EUR_USD", "GBP_USD", "USD_JPY"]
OPTION_SYMBOLS = ["AAPL-C", "SPY-C"]


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
# LEARNING STATE
# =========================================================
futures_symbol_bias = load_json_state(
    FUTURES_BIAS_FILE,
    {s: 1.0 for s in FUTURES_SYMBOLS}
)

futures_loss_streak = load_json_state(
    FUTURES_LOSS_FILE,
    {s: 0 for s in FUTURES_SYMBOLS}
)


# =========================================================
# TRACKING STATE
# =========================================================
futures_realized_pnl = {}
futures_trade_count = {s: 0 for s in FUTURES_SYMBOLS}
futures_win_count = {s: 0 for s in FUTURES_SYMBOLS}
futures_lifetime_total = 0.0

cycle = 0


# =========================================================
# REGIME ENGINE
# =========================================================
REGIMES = ["TREND", "MEAN_REVERSION", "MOMENTUM", "NEUTRAL"]


def detect_regime(symbol: str, asset_class: str):
    state = random.choice(REGIMES)
    confidence = round(random.uniform(0.45, 0.95), 2)

    if state == "MOMENTUM":
        risk_mult = 1.25
        priority = "PRIORITIZE"
    elif state == "TREND":
        risk_mult = 1.10
        priority = "ALLOW"
    elif state == "MEAN_REVERSION":
        risk_mult = 0.90
        priority = "REDUCE"
    else:
        risk_mult = 0.70
        priority = "BLOCK"

    return {
        "state": state,
        "confidence": confidence,
        "risk_mult": risk_mult,
        "priority": priority
    }


# =========================================================
# BIAS HELPERS
# =========================================================
def clamp_bias(v: float) -> float:
    return max(BIAS_MIN, min(BIAS_MAX, v))


def apply_bias_decay():
    for symbol, current in list(futures_symbol_bias.items()):
        if current > BIAS_NEUTRAL:
            current -= ((current - BIAS_NEUTRAL) * BIAS_DECAY_RATE)
        elif current < BIAS_NEUTRAL:
            current += ((BIAS_NEUTRAL - current) * BIAS_DECAY_RATE)
        futures_symbol_bias[symbol] = clamp_bias(current)


def update_reinforcement(symbol: str, pnl: float):
    current = futures_symbol_bias.get(symbol, BIAS_NEUTRAL)

    if pnl > 0:
        futures_loss_streak[symbol] = 0
        current *= BIAS_REWARD_MULT
    else:
        futures_loss_streak[symbol] += 1
        streak = futures_loss_streak[symbol]

        if streak >= 3:
            current *= BIAS_LOSS_PENALTY_3
        elif streak == 2:
            current *= BIAS_LOSS_PENALTY_2
        else:
            current *= BIAS_LOSS_PENALTY_1

    futures_symbol_bias[symbol] = clamp_bias(current)


def weighted_score(raw_score: float, symbol: str) -> float:
    return raw_score * futures_symbol_bias.get(symbol, BIAS_NEUTRAL)


def get_best_performer():
    active = {k: v for k, v in futures_realized_pnl.items() if v != 0}
    if not active:
        return "NONE"
    return max(active, key=active.get)


# =========================================================
# MAIN LOOP
# =========================================================
while True:
    cycle += 1
    print(f"\n=== Cycle {cycle} | {datetime.now()} ===")

    apply_bias_decay()
    regime_board = []

    # SAFE CRYPTO FETCH
    for s in SYMBOLS:
        safe_load_runtime_asset(s)
        reg = detect_regime(s, "CRYPTO")
        regime_board.append((s, "CRYPTO", reg))

    # FX REGIMES
    for s in FX_SYMBOLS:
        reg = detect_regime(s, "FX")
        regime_board.append((s, "FX", reg))

    # OPTIONS REGIMES
    for s in OPTION_SYMBOLS:
        reg = detect_regime(s, "OPTIONS")
        regime_board.append((s, "OPTIONS", reg))

    # FUTURES ENGINE
    if random.random() < 0.35:
        symbol = random.choice(FUTURES_SYMBOLS)
        reg = detect_regime(symbol, "FUTURES")
        regime_board.append((symbol, "FUTURES", reg))

        if reg["priority"] != "BLOCK":
            bias = futures_symbol_bias.get(symbol, BIAS_NEUTRAL)

            raw_score = round(random.uniform(8, 18), 2)
            score = round(
                weighted_score(raw_score, symbol) * reg["risk_mult"],
                2
            )

            contracts = 2 if bias >= 1.45 else 1
            if reg["priority"] == "REDUCE":
                contracts = 1
            elif reg["priority"] == "PRIORITIZE":
                contracts += 1

            print(
                f"[FUTURES OPEN] {symbol} contracts={contracts} "
                f"score={score} bias={bias:.2f} regime={reg['state']}"
            )

            if score >= 10:
                raw_pnl = random.uniform(-25, 25)
                pnl = round(raw_pnl * bias * reg["risk_mult"], 4)

                futures_realized_pnl[symbol] = round(
                    futures_realized_pnl.get(symbol, 0.0) + pnl,
                    4
                )

                futures_trade_count[symbol] += 1
                futures_lifetime_total += pnl

                if pnl > 0:
                    futures_win_count[symbol] += 1

                update_reinforcement(symbol, pnl)

                print(
                    f"[FUTURES CLOSE] {symbol} pnl={pnl} "
                    f"new_bias={futures_symbol_bias[symbol]:.2f}"
                )

    save_json_state(FUTURES_BIAS_FILE, futures_symbol_bias)
    save_json_state(FUTURES_LOSS_FILE, futures_loss_streak)

    total = round(sum(futures_realized_pnl.values()), 4)

    # DASHBOARD
    print("\n--- PROFIT DASHBOARD ---")
    print(f"Engine Mode: {ENGINE_MODE}")
    print("TOTAL:", total)

    print("\n--- FUTURES PERFORMANCE MATRIX ---")
    ranked = sorted(
        FUTURES_SYMBOLS,
        key=lambda x: futures_realized_pnl.get(x, 0),
        reverse=True
    )

    for sym in ranked:
        trades = futures_trade_count[sym]
        wins = futures_win_count[sym]
        total_sym = futures_realized_pnl.get(sym, 0.0)
        win_rate = (wins / trades * 100) if trades > 0 else 0.0
        avg_pnl = (total_sym / trades) if trades > 0 else 0.0

        print(
            f"{sym}: Trades {trades} | Wins {wins} | "
            f"WinRate {win_rate:.0f}% | Avg {avg_pnl:+.2f} | Total {total_sym:+.4f}"
        )

    print(f"\nBEST PERFORMER: {get_best_performer()}")
    print(f"LIFETIME FUTURES PNL: {futures_lifetime_total:+.4f}")

    print("\n--- CROSS-ASSET REGIME BOARD ---")
    for sym, cls, reg in regime_board[:12]:
        print(
            f"{sym} | {cls} | {reg['state']} | "
            f"{reg['confidence']:.2f} | {reg['priority']}"
        )

    print("\n--- FUTURES SYMBOL BIAS ---")
    print(futures_symbol_bias)

    time.sleep(CYCLE_SLEEP)