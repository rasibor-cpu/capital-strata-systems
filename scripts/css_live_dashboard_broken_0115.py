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

STATE_DIR = PROJECT_ROOT / "artifacts"
STATE_DIR.mkdir(exist_ok=True)

FUTURES_BIAS_FILE = STATE_DIR / "futures_symbol_bias.json"
FUTURES_LOSS_FILE = STATE_DIR / "futures_loss_streak.json"
FX_KILL_SWITCH_FILE = STATE_DIR / "fx_kill_switch_state.json"

SYMBOLS = [
    "BTC-USD","ETH-USD","SOL-USD","XRP-USD","ADA-USD",
    "DOGE-USD","AVAX-USD","LINK-USD","LTC-USD","BCH-USD"
]

FUTURES_SYMBOLS = ["ES","NQ","MES","MNQ","CL","GC"]

FX_SYMBOLS = [
    "EUR_USD","GBP_USD","USD_JPY","USD_CHF",
    "AUD_USD","USD_CAD","NZD_USD",
    "EUR_GBP","EUR_JPY","GBP_JPY"
]

OPTION_SYMBOLS = ["AAPL-C","SPY-C","QQQ-C"]

CYCLE_SLEEP = 8

BIAS_NEUTRAL = 1.0
BIAS_MIN = 0.35
BIAS_MAX = 2.25
BIAS_DECAY_RATE = 0.06
BIAS_REWARD_MULT = 1.10
BIAS_LOSS_PENALTY_1 = 0.88
BIAS_LOSS_PENALTY_2 = 0.78
BIAS_LOSS_PENALTY_3 = 0.68

CAPITAL_MULTIPLIERS = {
    "BLOCK":0.0,
    "REDUCE":0.5,
    "ALLOW":1.0,
    "PRIORITIZE":1.5,
}

REGIMES = ["TREND","MEAN_REVERSION","MOMENTUM","NEUTRAL"]

VOL_STATES = {
    "HIGH_VOL_EXPANDING":1.30,
    "LOW_VOL_COMPRESSED":0.70,
    "NORMAL_VOL":1.00,
    "BREAKOUT_EXPANSION":1.40,
}

SWEEP_STATES = {
    "SWEEP_UP_REVERSAL":0.65,
    "SWEEP_DOWN_REVERSAL":0.65,
    "CLEAN_BREAKOUT":1.25,
    "NO_SWEEP":1.00,
}

ENGINE_MODES = {
    "1":"SAFE",
    "2":"CONSERVATIVE",
    "3":"BALANCED",
    "4":"AGGRESSIVE",
    "5":"EXPANSION",
}

BLEED_GOVERNOR_ENABLED = True
BLEED_GOVERNOR_RATIO = 0.25

# ==========================================
# FX KILL SWITCH V3 SETTINGS
# ==========================================
FX_PAIR_MAX_LOSS_STREAK = 2
FX_PAIR_COOLDOWN_CYCLES = 4
FX_FIXED_EMERGENCY_LOSS_CAP = 12.0
FX_DYNAMIC_LOSS_CAP_RATIO = 0.25
FX_PRE_FREEZE_PROB_THRESHOLD = 0.57
FX_PRE_FREEZE_EV_THRESHOLD = 0.0


def load_json_state(path: Path, default: Dict):
    try:
        if path.exists():
            with open(path,"r") as f:
                return json.load(f)
    except Exception:
        pass
    return default.copy()


def save_json_state(path: Path, data: Dict):
    try:
        with open(path,"w") as f:
            json.dump(data,f,indent=2)
    except Exception:
        pass


def safe_load_runtime_asset(symbol: str):
    try:
        load_runtime_asset(symbol)
        print(f"Fetched 288 candles for {symbol}")
        return True
    except Exception as e:
        print(f"[FETCH FAIL] {symbol}: {str(e)[:80]}")
        return False


def select_engine_mode():
    print("\n=== CSS ENGINE MODE SELECTOR ===")
    for k,v in ENGINE_MODES.items():
        print(f"{k}. {v}")
    choice = input("Enter choice (1-5) [default=3]: ").strip()
    return ENGINE_MODES.get(choice,"BALANCED")


def clamp_bias(v):
    return max(BIAS_MIN,min(BIAS_MAX,v))


def weighted_score(raw_score,symbol):
    return raw_score * futures_symbol_bias.get(symbol,BIAS_NEUTRAL)


def get_positive_fx_total():
    return sum(v for v in fx_pnl.values() if v > 0)


def get_fx_dynamic_loss_cap():
    positive_total = get_positive_fx_total()
    if positive_total <= 0:
        return FX_FIXED_EMERGENCY_LOSS_CAP
    return max(
        FX_FIXED_EMERGENCY_LOSS_CAP,
        positive_total * FX_DYNAMIC_LOSS_CAP_RATIO
    )


def fx_pair_is_frozen(symbol):
    return fx_kill_switch_state[symbol]["frozen"]


def trigger_fx_freeze(symbol):
    fx_kill_switch_state[symbol]["frozen"] = True
    fx_kill_switch_state[symbol]["cooldown"] = FX_PAIR_COOLDOWN_CYCLES


def decrement_fx_cooldowns():
    for s in FX_SYMBOLS:
        if fx_kill_switch_state[s]["frozen"]:
            fx_kill_switch_state[s]["cooldown"] -= 1
            if fx_kill_switch_state[s]["cooldown"] <= 0:
                fx_kill_switch_state[s]["frozen"] = False
                fx_kill_switch_state[s]["cooldown"] = 0
                fx_kill_switch_state[s]["loss_streak"] = 0
                print(f"[FX REACTIVATED] {s}")


def update_fx_kill_switch(symbol,pnl):
    state = fx_kill_switch_state[symbol]

    if pnl > 0:
        state["loss_streak"] = 0
        return

    state["loss_streak"] += 1
    dynamic_cap = get_fx_dynamic_loss_cap()

    if (
        state["loss_streak"] >= FX_PAIR_MAX_LOSS_STREAK
        or abs(fx_pnl[symbol]) >= dynamic_cap
    ):
        trigger_fx_freeze(symbol)

        print(
            f"[FX KILL SWITCH TRIGGERED] {symbol} "
            f"LOSS_STREAK={state['loss_streak']} "
            f"PAIR_PNL={fx_pnl[symbol]:+.4f} "
            f"CAP={dynamic_cap:.4f}"
        )
def early_warning_suppress(symbol, prob_pos, ev):
    state = fx_kill_switch_state[symbol]

    if (
        state["loss_streak"] >= 1
        and prob_pos < FX_PRE_FREEZE_PROB_THRESHOLD
        and ev < FX_PRE_FREEZE_EV_THRESHOLD
    ):
        trigger_fx_freeze(symbol)

        print(
            f"[FX EARLY WARNING FREEZE] {symbol} "
            f"P+={prob_pos:.2%} EV={ev:+.2f} "
            f"LOSS_STREAK={state['loss_streak']}"
        )
        return True

    return False


class PreTradeProbabilityEngine:
    def estimate(
        self,
        *,
        regime_conf: float,
        vwap_mult: float,
        vol_mult: float,
        sweep_mult: float,
        raw_score: float
    ) -> Tuple[float,float,float,bool]:

        regime_component = regime_conf * 0.30
        vwap_component = min(vwap_mult / 1.5,1.0) * 0.20
        vol_component = min(vol_mult / 1.4,1.0) * 0.15
        sweep_component = min(sweep_mult / 1.25,1.0) * 0.15
        score_component = min(raw_score / 20.0,1.0) * 0.20

        prob_positive = (
            regime_component +
            vwap_component +
            vol_component +
            sweep_component +
            score_component
        )

        prob_positive = max(0.05,min(0.95,prob_positive))
        prob_negative = 1.0 - prob_positive
        expected_value = (prob_positive * raw_score) - (prob_negative * 8.0)
        execute = prob_positive >= 0.58 and expected_value > 0

        return (
            round(prob_positive,4),
            round(prob_negative,4),
            round(expected_value,4),
            execute
        )


pt_engine = PreTradeProbabilityEngine()


ENGINE_MODE = select_engine_mode()

pm = PositionManager()
futures_adapter = FuturesSimAdapter(max_portfolio_allocation=5.0)
futures_pm = FuturesPositionManager(futures_adapter)

options_adapter = OptionsChainAdapter()
options_pm = OptionsPositionManager()
options_intel = OptionsIntelligenceEngine()

futures_symbol_bias = load_json_state(
    FUTURES_BIAS_FILE,
    {s:1.0 for s in FUTURES_SYMBOLS}
)

futures_loss_streak = load_json_state(
    FUTURES_LOSS_FILE,
    {s:0 for s in FUTURES_SYMBOLS}
)

fx_kill_switch_state = load_json_state(
    FX_KILL_SWITCH_FILE,
    {
        s:{
            "loss_streak":0,
            "cooldown":0,
            "frozen":False
        } for s in FX_SYMBOLS
    }
)

crypto_pnl = {s:0.0 for s in SYMBOLS}
crypto_trades = {s:0 for s in SYMBOLS}
crypto_wins = {s:0 for s in SYMBOLS}

fx_pnl = {s:0.0 for s in FX_SYMBOLS}
fx_trades = {s:0 for s in FX_SYMBOLS}
fx_wins = {s:0 for s in FX_SYMBOLS}

options_pnl = {s:0.0 for s in OPTION_SYMBOLS}
options_trades = {s:0 for s in OPTION_SYMBOLS}
options_wins = {s:0 for s in OPTION_SYMBOLS}

futures_realized_pnl = {s:0.0 for s in FUTURES_SYMBOLS}
futures_trade_count = {s:0 for s in FUTURES_SYMBOLS}
futures_win_count = {s:0 for s in FUTURES_SYMBOLS}

futures_lifetime_total = 0.0
last_trade = "NONE"
cycle = 0


def apply_bias_decay():
    for symbol,current in list(futures_symbol_bias.items()):
        if current > BIAS_NEUTRAL:
            current -= ((current - BIAS_NEUTRAL) * BIAS_DECAY_RATE)
        elif current < BIAS_NEUTRAL:
            current += ((BIAS_NEUTRAL - current) * BIAS_DECAY_RATE)

        futures_symbol_bias[symbol] = clamp_bias(current)


def update_reinforcement(symbol,pnl):
    current = futures_symbol_bias.get(symbol,BIAS_NEUTRAL)

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


def execute_trade(asset_class,symbol,score,eff_mult):
    global futures_lifetime_total,last_trade

    if score < 10:
        return

    pnl = round(random.uniform(-20,20) * eff_mult,4)
    last_trade = f"{symbol} {pnl:+.4f}"

    if asset_class == "CRYPTO":
        crypto_pnl[symbol] += pnl
        crypto_trades[symbol] += 1
        if pnl > 0:
            crypto_wins[symbol] += 1

    elif asset_class == "FX":
        fx_pnl[symbol] += pnl
        fx_trades[symbol] += 1
        if pnl > 0:
            fx_wins[symbol] += 1
        update_fx_kill_switch(symbol,pnl)

    elif asset_class == "OPTIONS":
        options_pnl[symbol] += pnl
        options_trades[symbol] += 1
        if pnl > 0:
            options_wins[symbol] += 1

    elif asset_class == "FUTURES":
        futures_realized_pnl[symbol] += pnl
        futures_trade_count[symbol] += 1
        futures_lifetime_total += pnl
        if pnl > 0:
            futures_win_count[symbol] += 1
        update_reinforcement(symbol,pnl)

    print(f"[{asset_class} EXECUTED] {symbol} pnl={pnl:+.4f}")
# =========================================================
# MAIN LOOP MERGE BLOCK (insert into your current while True loop)
# Replace ONLY the FX loop section with this upgraded version
# =========================================================

while True:
    cycle += 1
    print(f"\n=== Cycle {cycle} | {datetime.now()} ===")

    apply_bias_decay()
    decrement_fx_cooldowns()

    # ================= FX LOOP WITH KILL SWITCH V3 =================
    for s in FX_SYMBOLS:

        if fx_pair_is_frozen(s):
            print(
                f"[FX FROZEN] {s} "
                f"COOLDOWN={fx_kill_switch_state[s]['cooldown']}"
            )
            continue

        reg = detect_regime(s, "FX")
        vw = compute_vwap_state(s)
        vol = compute_volatility_state(s)
        sw = compute_liquidity_sweep(s)

        eff = reg["capital_mult"] * vw["mult"] * vol["mult"] * sw["mult"]

        if reg["priority"] == "BLOCK":
            continue

        governor_frozen, asset_loss, freeze_limit, other_positive = get_bleed_governor_state("FX")
        if governor_frozen:
            print(
                f"[BLEED FREEZE] FX "
                f"LOSS={asset_loss:.4f} "
                f"LIMIT={freeze_limit:.4f} "
                f"OTHERS+={other_positive:.4f}"
            )
            continue

        raw_score = round(random.uniform(8,18),2)
        signal_score = (
            raw_score *
            reg["risk_mult"] *
            vw["mult"] *
            vol["mult"] *
            sw["mult"]
        )

        prob_pos, prob_neg, ev, allow_trade = pt_engine.estimate(
            regime_conf=reg["confidence"],
            vwap_mult=vw["mult"],
            vol_mult=vol["mult"],
            sweep_mult=sw["mult"],
            raw_score=signal_score
        )

        # EARLY WARNING SUPPRESSION
        if early_warning_suppress(s, prob_pos, ev):
            continue

        if not allow_trade:
            print(
                f"[FX REJECTED] {s} "
                f"P+={prob_pos:.2%} EV={ev:+.2f}"
            )
            continue

        execute_trade("FX", s, round(signal_score,2), eff)

    # persist state each cycle
    save_json_state(FX_KILL_SWITCH_FILE, fx_kill_switch_state)
    save_json_state(FUTURES_BIAS_FILE, futures_symbol_bias)
    save_json_state(FUTURES_LOSS_FILE, futures_loss_streak)

    print("\n--- FX KILL SWITCH STATUS ---")
    for s in FX_SYMBOLS:
        st = fx_kill_switch_state[s]
        if st["frozen"]:
            print(
                f"{s} | FROZEN | cooldown={st['cooldown']} | "
                f"loss_streak={st['loss_streak']} | pnl={fx_pnl[s]:+.4f}"
            )

    # =====================================================
    # KEEP ALL YOUR EXISTING:
    # crypto loop
    # options loop
    # futures loop
    # dashboards / boards / summaries
    # =====================================================

    time.sleep(CYCLE_SLEEP)