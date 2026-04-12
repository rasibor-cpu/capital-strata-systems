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
# F10/F11 PERSISTENCE FILES
# =========================================================
STATE_DIR = PROJECT_ROOT / "artifacts"
STATE_DIR.mkdir(exist_ok=True)

FUTURES_BIAS_FILE = STATE_DIR / "futures_symbol_bias.json"
FUTURES_LOSS_FILE = STATE_DIR / "futures_loss_streak.json"


# =========================================================
# LOAD / SAVE HELPERS
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

SYMBOLS = [
    "BTC-USD", "ETH-USD", "SOL-USD", "XRP-USD", "ADA-USD",
    "DOGE-USD", "AVAX-USD", "LINK-USD", "LTC-USD", "BCH-USD"
]

FUTURES_SYMBOLS = ["ES", "NQ", "CL", "GC"]

# F11 decay controls
BIAS_NEUTRAL = 1.0
BIAS_MIN = 0.35
BIAS_MAX = 2.25
BIAS_DECAY_RATE = 0.06      # per cycle drift toward neutral
BIAS_REWARD_MULT = 1.10     # positive reinforcement
BIAS_LOSS_PENALTY_1 = 0.88  # first loss
BIAS_LOSS_PENALTY_2 = 0.78  # second consecutive loss
BIAS_LOSS_PENALTY_3 = 0.68  # third+ consecutive loss


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
# PERSISTENT LEARNING STATE
# =========================================================
futures_symbol_bias = load_json_state(
    FUTURES_BIAS_FILE,
    {s: 1.0 for s in FUTURES_SYMBOLS}
)

futures_loss_streak = load_json_state(
    FUTURES_LOSS_FILE,
    {s: 0 for s in FUTURES_SYMBOLS}
)

print("[F11 LOADED FUTURES BIAS]", futures_symbol_bias)
print("[F11 LOADED LOSS STREAK]", futures_loss_streak)

# =========================================================
# STATE
# =========================================================
prev_prices: Dict[str, float] = {}
crypto_realized_pnl: Dict[str, float] = {}
fx_realized_pnl: Dict[str, float] = {}
options_realized_pnl: Dict[str, float] = {}
fx_arb_realized_pnl: Dict[str, float] = {}
fx_arb_positions: Dict[str, Dict] = {}
futures_realized_pnl: Dict[str, float] = {}

cycle = 0


# =========================================================
# HELPERS
# =========================================================
def clamp_bias(v: float) -> float:
    return max(BIAS_MIN, min(BIAS_MAX, v))


def apply_bias_decay():
    """
    Pull all biases gently back toward neutral each cycle.
    This prevents runaway overweighting and permanent suppression.
    """
    for symbol, current in list(futures_symbol_bias.items()):
        if current > BIAS_NEUTRAL:
            current = current - ((current - BIAS_NEUTRAL) * BIAS_DECAY_RATE)
        elif current < BIAS_NEUTRAL:
            current = current + ((BIAS_NEUTRAL - current) * BIAS_DECAY_RATE)
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


# =========================================================
# MAIN LOOP
# =========================================================
while True:
    cycle += 1
    print(f"\n=== Cycle {cycle} | {datetime.now()} ===")

    # -----------------------------------------------------
    # F11 decay pass
    # -----------------------------------------------------
    apply_bias_decay()

    # -----------------------------------------------------
    # CRYPTO FETCH
    # -----------------------------------------------------
    for s in SYMBOLS:
        _ = load_runtime_asset(s)
        print(f"Fetched 288 candles for {s}")

    # -----------------------------------------------------
    # FUTURES DEMO ENGINE
    # -----------------------------------------------------
    if random.random() < 0.35:
        symbol = random.choice(FUTURES_SYMBOLS)
        bias = futures_symbol_bias.get(symbol, BIAS_NEUTRAL)

        raw_score = round(random.uniform(8, 18), 2)
        score = round(weighted_score(raw_score, symbol), 2)
        entry = round(random.uniform(75, 22050), 4)

        contracts = 1
        if bias >= 1.45:
            contracts = 2

        print(
            f"[FUTURES OPEN] {symbol} entry={entry} "
            f"contracts={contracts} score={score} bias={bias:.2f}"
        )

        if score >= 10:
            raw_pnl = random.uniform(-25, 25)
            pnl = round(raw_pnl * bias, 4)

            futures_realized_pnl[symbol] = round(
                futures_realized_pnl.get(symbol, 0.0) + pnl,
                4
            )

            update_reinforcement(symbol, pnl)

            print(
                f"[FUTURES CLOSE] {symbol} pnl={pnl} "
                f"new_bias={futures_symbol_bias[symbol]:.2f} "
                f"loss_streak={futures_loss_streak[symbol]}"
            )

    # -----------------------------------------------------
    # SAVE LEARNING STATE EACH CYCLE
    # -----------------------------------------------------
    save_json_state(FUTURES_BIAS_FILE, futures_symbol_bias)
    save_json_state(FUTURES_LOSS_FILE, futures_loss_streak)

    # -----------------------------------------------------
    # DASHBOARD
    # -----------------------------------------------------
    total = round(
        sum(futures_realized_pnl.values()) +
        sum(fx_arb_realized_pnl.values()),
        4
    )

    print("\n--- PROFIT DASHBOARD ---")
    print(f"Engine Mode: {ENGINE_MODE}")
    print(f"Crypto Open: {len(pm.positions)}")
    print("FX Open: 0")
    print(f"Futures Open: {len(futures_pm.get_open_positions())}")
    print(f"FX Arbitrage Open: {len(fx_arb_positions)}")
    print(f"Options Open: {len(options_pm.get_open_positions())}")

    print("\n--- REALIZED PNL ---")
    print("Crypto:", crypto_realized_pnl if crypto_realized_pnl else "{}")
    print("FX:", fx_realized_pnl if fx_realized_pnl else "{}")
    print("Futures:", futures_realized_pnl if futures_realized_pnl else "{}")
    print("Options:", options_realized_pnl if options_realized_pnl else "{}")
    print("FX Arb:", fx_arb_realized_pnl if fx_arb_realized_pnl else "{}")
    print("TOTAL:", total)

    print("\n--- FUTURES SYMBOL BIAS ---")
    print(futures_symbol_bias)

    print("\n--- FUTURES LOSS STREAK ---")
    print(futures_loss_streak)

    time.sleep(CYCLE_SLEEP)