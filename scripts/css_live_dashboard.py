from __future__ import annotations
import sys, time, random, json
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

STATE_DIR = PROJECT_ROOT / "artifacts"
STATE_DIR.mkdir(exist_ok=True)

FUTURES_BIAS_FILE = STATE_DIR / "futures_symbol_bias.json"
FUTURES_LOSS_FILE = STATE_DIR / "futures_loss_streak.json"

SYMBOLS = [
    "BTC-USD","ETH-USD","SOL-USD","XRP-USD","ADA-USD",
    "DOGE-USD","AVAX-USD","LINK-USD","LTC-USD","BCH-USD"
]

FUTURES_SYMBOLS = ["ES","NQ","CL","GC"]

FX_SYMBOLS = [
    "EUR_USD","GBP_USD","USD_JPY","USD_CHF",
    "AUD_USD","USD_CAD","NZD_USD",
    "EUR_GBP","EUR_JPY","GBP_JPY"
]

OPTION_SYMBOLS = ["AAPL-C","SPY-C"]

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
    "PRIORITIZE":1.5
}

REGIMES = ["TREND","MEAN_REVERSION","MOMENTUM","NEUTRAL"]

VOL_STATES = {
    "HIGH_VOL_EXPANDING":1.30,
    "LOW_VOL_COMPRESSED":0.70,
    "NORMAL_VOL":1.00,
    "BREAKOUT_EXPANSION":1.40
}

ENGINE_MODES = {
    "1":"SAFE",
    "2":"CONSERVATIVE",
    "3":"BALANCED",
    "4":"AGGRESSIVE",
    "5":"EXPANSION"
}


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
cycle = 0


def clamp_bias(v):
    return max(BIAS_MIN,min(BIAS_MAX,v))


def apply_bias_decay():
    for symbol,current in list(futures_symbol_bias.items()):
        if current > BIAS_NEUTRAL:
            current -= ((current-BIAS_NEUTRAL)*BIAS_DECAY_RATE)
        elif current < BIAS_NEUTRAL:
            current += ((BIAS_NEUTRAL-current)*BIAS_DECAY_RATE)
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


def weighted_score(raw_score,symbol):
    return raw_score * futures_symbol_bias.get(symbol,BIAS_NEUTRAL)


def get_best_performer():
    active = {k:v for k,v in futures_realized_pnl.items() if v != 0}
    if not active:
        return "NONE"
    return max(active, key=active.get)

def detect_regime(symbol,asset_class):
    state = random.choice(REGIMES)
    confidence = round(random.uniform(0.45,0.95),2)

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
        "state":state,
        "confidence":confidence,
        "risk_mult":risk_mult,
        "priority":priority,
        "capital_mult":CAPITAL_MULTIPLIERS[priority]
    }


def compute_vwap_state(symbol):
    distance_pct = round(random.uniform(-3.0,3.0),2)
    slope = random.choice(["RISING","FLAT","FALLING"])

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
        "state":state,
        "mult":mult,
        "distance_pct":distance_pct
    }


def compute_volatility_state(symbol):
    state = random.choice(list(VOL_STATES.keys()))
    return {"state":state,"mult":VOL_STATES[state]}


def execute_trade(asset_class, symbol, score, eff_mult):

    if score < 10:
        return

    pnl = round(random.uniform(-20,20) * eff_mult,4)

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

    elif asset_class == "OPTIONS":
        options_pnl[symbol] += pnl
        options_trades[symbol] += 1
        if pnl > 0:
            options_wins[symbol] += 1

    elif asset_class == "FUTURES":
        futures_realized_pnl[symbol] += pnl
        futures_trade_count[symbol] += 1
        global futures_lifetime_total
        futures_lifetime_total += pnl

        if pnl > 0:
            futures_win_count[symbol] += 1

        update_reinforcement(symbol,pnl)

    print(f"[{asset_class} EXECUTED] {symbol} pnl={pnl:+.4f}")


while True:
    cycle += 1
    print(f"\n=== Cycle {cycle} | {datetime.now()} ===")

    apply_bias_decay()

    regime_board = []
    capital_board = []
    vwap_board = []
    volatility_board = []
    effective_board = []

    # ==============================
    # CRYPTO EXECUTION
    # ==============================
    for s in SYMBOLS:
        safe_load_runtime_asset(s)
        reg = detect_regime(s, "CRYPTO")
        vw = compute_vwap_state(s)
        vol = compute_volatility_state(s)
        eff = reg["capital_mult"] * vw["mult"] * vol["mult"]

        regime_board.append((s, "CRYPTO", reg))
        capital_board.append((s, reg["priority"], reg["capital_mult"]))
        vwap_board.append((s, vw))
        volatility_board.append((s, vol))
        effective_board.append((s, "CRYPTO", reg["priority"], vw["state"], vol["state"], eff))

        if reg["priority"] != "BLOCK":
            raw_score = round(random.uniform(8, 18), 2)
            score = raw_score * reg["risk_mult"] * vw["mult"] * vol["mult"]
            execute_trade("CRYPTO", s, round(score, 2), eff)

    # ==============================
    # FX EXECUTION
    # ==============================
    for s in FX_SYMBOLS:
        reg = detect_regime(s, "FX")
        vw = compute_vwap_state(s)
        vol = compute_volatility_state(s)
        eff = reg["capital_mult"] * vw["mult"] * vol["mult"]

        regime_board.append((s, "FX", reg))
        capital_board.append((s, reg["priority"], reg["capital_mult"]))
        vwap_board.append((s, vw))
        volatility_board.append((s, vol))
        effective_board.append((s, "FX", reg["priority"], vw["state"], vol["state"], eff))

        if reg["priority"] != "BLOCK":
            raw_score = round(random.uniform(8, 18), 2)
            score = raw_score * reg["risk_mult"] * vw["mult"] * vol["mult"]
            execute_trade("FX", s, round(score, 2), eff)

    # ==============================
    # OPTIONS EXECUTION
    # ==============================
    for s in OPTION_SYMBOLS:
        reg = detect_regime(s, "OPTIONS")
        vw = compute_vwap_state(s)
        vol = compute_volatility_state(s)
        eff = reg["capital_mult"] * vw["mult"] * vol["mult"]

        regime_board.append((s, "OPTIONS", reg))
        capital_board.append((s, reg["priority"], reg["capital_mult"]))
        vwap_board.append((s, vw))
        volatility_board.append((s, vol))
        effective_board.append((s, "OPTIONS", reg["priority"], vw["state"], vol["state"], eff))

        if reg["priority"] != "BLOCK":
            raw_score = round(random.uniform(8, 18), 2)
            score = raw_score * reg["risk_mult"] * vw["mult"] * vol["mult"]
            execute_trade("OPTIONS", s, round(score, 2), eff)

    # ==============================
    # FUTURES EXECUTION
    # ==============================
    if random.random() < 0.35:
        symbol = random.choice(FUTURES_SYMBOLS)
        reg = detect_regime(symbol, "FUTURES")
        vw = compute_vwap_state(symbol)
        vol = compute_volatility_state(symbol)
        eff = reg["capital_mult"] * vw["mult"] * vol["mult"]

        regime_board.append((symbol, "FUTURES", reg))
        capital_board.append((symbol, reg["priority"], reg["capital_mult"]))
        vwap_board.append((symbol, vw))
        volatility_board.append((symbol, vol))
        effective_board.append((symbol, "FUTURES", reg["priority"], vw["state"], vol["state"], eff))

        if reg["priority"] != "BLOCK":
            bias = futures_symbol_bias.get(symbol, BIAS_NEUTRAL)
            raw_score = round(random.uniform(8, 18), 2)
            score = weighted_score(raw_score, symbol)
            score *= reg["risk_mult"]
            score *= vw["mult"]
            score *= vol["mult"]
            score = round(score, 2)

            print(
                f"[FUTURES OPEN] {symbol} score={score} bias={bias:.2f} "
                f"regime={reg['state']} vwap={vw['state']} vol={vol['state']} eff={eff:.2f}x"
            )

            execute_trade("FUTURES", symbol, score, eff)

    save_json_state(FUTURES_BIAS_FILE, futures_symbol_bias)
    save_json_state(FUTURES_LOSS_FILE, futures_loss_streak)

    total = round(
        sum(crypto_pnl.values()) +
        sum(fx_pnl.values()) +
        sum(options_pnl.values()) +
        sum(futures_realized_pnl.values()),
        4
    )

    print("\n--- PROFIT DASHBOARD ---")
    print(f"Engine Mode: {ENGINE_MODE}")
    print("TOTAL:", total)

    print("\n--- VWAP BOARD ---")
    for sym, vw in vwap_board[:12]:
        print(f"{sym} | {vw['distance_pct']:+.2f}% | {vw['state']}")

    print("\n--- VOLATILITY BOARD ---")
    for sym, vol in volatility_board[:12]:
        print(f"{sym} | {vol['state']} | {vol['mult']:.2f}x")

    print("\n--- CRYPTO PERFORMANCE MATRIX ---")
    for sym in SYMBOLS:
        trades = crypto_trades[sym]
        wins = crypto_wins[sym]
        total_sym = crypto_pnl[sym]
        win_rate = (wins / trades * 100) if trades > 0 else 0.0
        avg_pnl = (total_sym / trades) if trades > 0 else 0.0
        print(f"{sym}: Trades {trades} | Wins {wins} | WinRate {win_rate:.0f}% | Avg {avg_pnl:+.2f} | Total {total_sym:+.4f}")

    print("\n--- FX PERFORMANCE MATRIX ---")
    for sym in FX_SYMBOLS:
        trades = fx_trades[sym]
        wins = fx_wins[sym]
        total_sym = fx_pnl[sym]
        win_rate = (wins / trades * 100) if trades > 0 else 0.0
        avg_pnl = (total_sym / trades) if trades > 0 else 0.0
        print(f"{sym}: Trades {trades} | Wins {wins} | WinRate {win_rate:.0f}% | Avg {avg_pnl:+.2f} | Total {total_sym:+.4f}")

    print("\n--- OPTIONS PERFORMANCE MATRIX ---")
    for sym in OPTION_SYMBOLS:
        trades = options_trades[sym]
        wins = options_wins[sym]
        total_sym = options_pnl[sym]
        win_rate = (wins / trades * 100) if trades > 0 else 0.0
        avg_pnl = (total_sym / trades) if trades > 0 else 0.0
        print(f"{sym}: Trades {trades} | Wins {wins} | WinRate {win_rate:.0f}% | Avg {avg_pnl:+.2f} | Total {total_sym:+.4f}")

    print("\n--- FUTURES PERFORMANCE MATRIX ---")
    ranked = sorted(FUTURES_SYMBOLS, key=lambda x: futures_realized_pnl.get(x,0), reverse=True)
    for sym in ranked:
        trades = futures_trade_count[sym]
        wins = futures_win_count[sym]
        total_sym = futures_realized_pnl.get(sym,0.0)
        win_rate = (wins / trades * 100) if trades > 0 else 0.0
        avg_pnl = (total_sym / trades) if trades > 0 else 0.0
        print(f"{sym}: Trades {trades} | Wins {wins} | WinRate {win_rate:.0f}% | Avg {avg_pnl:+.2f} | Total {total_sym:+.4f}")

    print(f"\nBEST FUTURES PERFORMER: {get_best_performer()}")
    print(f"LIFETIME FUTURES PNL: {futures_lifetime_total:+.4f}")

    print("\n--- CROSS-ASSET REGIME BOARD ---")
    for sym, cls, reg in regime_board[:12]:
        print(f"{sym} | {cls} | {reg['state']} | {reg['confidence']:.2f} | {reg['priority']}")

    print("\n--- CAPITAL ALLOCATION BOARD ---")
    for sym, priority, mult in capital_board[:12]:
        print(f"{sym} | {priority} | {mult:.2f}x")

    print("\n--- UNIVERSAL EFFECTIVE BOARD ---")
    for sym, asset_class, priority, vwstate, volstate, eff in effective_board[:12]:
        print(f"{sym} | {asset_class} | {priority} | {vwstate} | {volstate} | Eff {eff:.2f}x")

    print("\n--- FUTURES SYMBOL BIAS ---")
    print(futures_symbol_bias)

    time.sleep(CYCLE_SLEEP)