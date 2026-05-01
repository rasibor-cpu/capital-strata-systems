from __future__ import annotations
import sys, time, random, json
from datetime import datetime
from pathlib import Path
from typing import Dict, Tuple, Optional

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
from backend.options.option_pricing_calibration_engine import OptionPricingCalibrationEngine
from backend.options.option_expiry_parser_engine import OptionExpiryParserEngine

# =========================
# STATE FILES
# =========================

STATE_DIR = PROJECT_ROOT / "artifacts"
STATE_DIR.mkdir(exist_ok=True)

FILES = {
    "crypto_pnl": STATE_DIR / "crypto_pnl.json",
    "fx_pnl": STATE_DIR / "fx_pnl.json",
    "options_pnl": STATE_DIR / "options_pnl.json",
    "futures_pnl": STATE_DIR / "futures_pnl.json",

    "crypto_trades": STATE_DIR / "crypto_trades.json",
    "fx_trades": STATE_DIR / "fx_trades.json",
    "options_trades": STATE_DIR / "options_trades.json",
    "futures_trades": STATE_DIR / "futures_trades.json",

    "crypto_wins": STATE_DIR / "crypto_wins.json",
    "fx_wins": STATE_DIR / "fx_wins.json",
    "options_wins": STATE_DIR / "options_wins.json",
    "futures_wins": STATE_DIR / "futures_wins.json",

    "futures_bias": STATE_DIR / "futures_symbol_bias.json",
    "futures_loss": STATE_DIR / "futures_loss_streak.json"
}

# =========================
# SYMBOLS
# =========================

SYMBOLS = ["BTC-USD","ETH-USD","SOL-USD","XRP-USD","ADA-USD",
           "DOGE-USD","AVAX-USD","LINK-USD","LTC-USD","BCH-USD"]

FX_SYMBOLS = ["EUR_USD","GBP_USD","USD_JPY","USD_CHF",
              "AUD_USD","USD_CAD","NZD_USD",
              "EUR_GBP","EUR_JPY","GBP_JPY"]

FUTURES_SYMBOLS = ["ES","NQ","CL","GC"]

OPTION_SYMBOLS = ["AAPL-C","SPY-C","QQQ-C"]

# =========================
# ENGINE CONSTANTS
# =========================

CYCLE_SLEEP = 8
BLEED_GOVERNOR_RATIO = 0.25

# =========================
# SAFE LOAD / SAVE
# =========================

def load_json(path, default):
    try:
        if path.exists():
            with open(path, "r") as f:
                data = json.load(f)
                return data if isinstance(data, dict) else default.copy()
    except Exception as e:
        print(f"[LOAD ERROR] {path}: {e}")
    return default.copy()

def save_json(path, data):
    try:
        with open(path, "w") as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        print(f"[SAVE ERROR] {path}: {e}")

# =========================
# INITIAL STATE LOAD
# =========================

crypto_pnl = load_json(FILES["crypto_pnl"], {s:0.0 for s in SYMBOLS})
fx_pnl = load_json(FILES["fx_pnl"], {s:0.0 for s in FX_SYMBOLS})
options_pnl = load_json(FILES["options_pnl"], {})
futures_pnl = load_json(FILES["futures_pnl"], {s:0.0 for s in FUTURES_SYMBOLS})

crypto_trades = load_json(FILES["crypto_trades"], {s:0 for s in SYMBOLS})
fx_trades = load_json(FILES["fx_trades"], {s:0 for s in FX_SYMBOLS})
options_trades = load_json(FILES["options_trades"], {})
futures_trades = load_json(FILES["futures_trades"], {s:0 for s in FUTURES_SYMBOLS})

crypto_wins = load_json(FILES["crypto_wins"], {s:0 for s in SYMBOLS})
fx_wins = load_json(FILES["fx_wins"], {s:0 for s in FX_SYMBOLS})
options_wins = load_json(FILES["options_wins"], {})
futures_wins = load_json(FILES["futures_wins"], {s:0 for s in FUTURES_SYMBOLS})

futures_bias = load_json(FILES["futures_bias"], {s:1.0 for s in FUTURES_SYMBOLS})
futures_loss = load_json(FILES["futures_loss"], {s:0 for s in FUTURES_SYMBOLS})

# =========================
# HELPERS
# =========================

def get_total_pnl():
    return round(
        sum(crypto_pnl.values()) +
        sum(fx_pnl.values()) +
        sum(options_pnl.values()) +
        sum(futures_pnl.values()), 4
    )

def snapshot_pnl():
    return {
        "CRYPTO": sum(crypto_pnl.values()),
        "FX": sum(fx_pnl.values()),
        "OPTIONS": sum(options_pnl.values()),
        "FUTURES": sum(futures_pnl.values()),
    }
  # =========================
# ENGINE LOGIC (V2–V4 RESTORED)
# =========================

BIAS_NEUTRAL = 1.0
BIAS_MIN = 0.35
BIAS_MAX = 2.25
BIAS_DECAY_RATE = 0.06

BIAS_REWARD_MULT = 1.10
BIAS_LOSS_PENALTY_1 = 0.88
BIAS_LOSS_PENALTY_2 = 0.78
BIAS_LOSS_PENALTY_3 = 0.68

REGIMES = ["TREND", "MEAN_REVERSION", "MOMENTUM", "NEUTRAL"]

VOL_STATES = {
    "HIGH_VOL_EXPANDING": 1.30,
    "LOW_VOL_COMPRESSED": 0.70,
    "NORMAL_VOL": 1.00,
    "BREAKOUT_EXPANSION": 1.40,
}

SWEEP_STATES = {
    "SWEEP_UP_REVERSAL": 0.65,
    "SWEEP_DOWN_REVERSAL": 0.65,
    "CLEAN_BREAKOUT": 1.25,
    "NO_SWEEP": 1.00,
}

CAPITAL_MULTIPLIERS = {
    "BLOCK": 0.0,
    "REDUCE": 0.5,
    "ALLOW": 1.0,
    "PRIORITIZE": 1.5,
}

# =========================
# BIAS SYSTEM
# =========================

def clamp_bias(v):
    return max(BIAS_MIN, min(BIAS_MAX, v))


def apply_bias_decay():
    for symbol, current in list(futures_bias.items()):
        if current > BIAS_NEUTRAL:
            current -= ((current - BIAS_NEUTRAL) * BIAS_DECAY_RATE)
        elif current < BIAS_NEUTRAL:
            current += ((BIAS_NEUTRAL - current) * BIAS_DECAY_RATE)

        futures_bias[symbol] = clamp_bias(current)


def update_reinforcement(symbol, pnl):
    current = futures_bias.get(symbol, BIAS_NEUTRAL)

    if pnl > 0:
        futures_loss[symbol] = 0
        current *= BIAS_REWARD_MULT
    else:
        futures_loss[symbol] += 1
        streak = futures_loss[symbol]

        if streak >= 3:
            current *= BIAS_LOSS_PENALTY_3
        elif streak == 2:
            current *= BIAS_LOSS_PENALTY_2
        else:
            current *= BIAS_LOSS_PENALTY_1

    futures_bias[symbol] = clamp_bias(current)


def weighted_score(raw_score, symbol):
    return raw_score * futures_bias.get(symbol, BIAS_NEUTRAL)

# =========================
# PROBABILITY ENGINE
# =========================

class PreTradeProbabilityEngine:

    def estimate(
        self,
        *,
        regime_conf: float,
        vwap_mult: float,
        vol_mult: float,
        sweep_mult: float,
        raw_score: float
    ) -> Tuple[float, float, float, bool]:

        regime_component = regime_conf * 0.30
        vwap_component = min(vwap_mult / 1.5, 1.0) * 0.20
        vol_component = min(vol_mult / 1.4, 1.0) * 0.15
        sweep_component = min(sweep_mult / 1.25, 1.0) * 0.15
        score_component = min(raw_score / 20.0, 1.0) * 0.20

        prob_positive = (
            regime_component +
            vwap_component +
            vol_component +
            sweep_component +
            score_component
        )

        prob_positive = max(0.05, min(0.95, prob_positive))
        prob_negative = 1.0 - prob_positive

        expected_value = (prob_positive * raw_score) - (prob_negative * 8.0)

        execute = prob_positive >= 0.58 and expected_value > 0

        return (
            round(prob_positive, 4),
            round(prob_negative, 4),
            round(expected_value, 4),
            execute
        )


pt_engine = PreTradeProbabilityEngine()

# =========================
# MARKET STATE GENERATORS (SIMULATION)
# =========================

def detect_regime(symbol, asset_class):
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
        "priority": priority,
        "capital_mult": CAPITAL_MULTIPLIERS[priority]
    }


def compute_vwap_state(symbol):
    distance_pct = round(random.uniform(-3.0, 3.0), 2)
    slope = random.choice(["RISING", "FLAT", "FALLING"])

    if distance_pct > 0 and slope == "RISING":
        state = "ABOVE_RISING"
        mult = 1.25
    elif distance_pct < 0 and slope == "FALLING":
        state = "BELOW_FALLING"
        mult = 0.75
    else:
        state = "NEUTRAL"
        mult = 1.00

    return {
        "state": state,
        "mult": mult,
        "distance_pct": distance_pct
    }


def compute_volatility_state(symbol):
    state = random.choice(list(VOL_STATES.keys()))
    return {"state": state, "mult": VOL_STATES[state]}


def compute_liquidity_sweep(symbol):
    state = random.choice(list(SWEEP_STATES.keys()))
    return {"state": state, "mult": SWEEP_STATES[state]}

# =========================
# BLEED GOVERNOR (FIXED SNAPSHOT)
# =========================

def get_bleed_governor_state(
    asset_class: str,
    snapshot: Optional[Dict[str, float]] = None
) -> Tuple[bool, float, float, float]:

    pnl_map = snapshot if snapshot else snapshot_pnl()

    asset_pnl = float(pnl_map.get(asset_class, 0.0))

    if asset_pnl >= 0:
        return False, 0.0, 0.0, 0.0

    other_positive = sum(
        pnl for k, pnl in pnl_map.items()
        if k != asset_class and pnl > 0
    )

    if other_positive <= 0:
        return False, abs(asset_pnl), 0.0, other_positive

    limit = BLEED_GOVERNOR_RATIO * other_positive
    loss_abs = abs(asset_pnl)

    frozen = loss_abs > limit

    return frozen, round(loss_abs,4), round(limit,4), round(other_positive,4)
  
