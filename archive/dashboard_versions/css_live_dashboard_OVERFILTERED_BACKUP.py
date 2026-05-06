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
from backend.intelligence.trade_decision_orchestrator import TradeDecisionOrchestrator

STATE_DIR = PROJECT_ROOT / "artifacts"
STATE_DIR.mkdir(exist_ok=True)

FUTURES_BIAS_FILE = STATE_DIR / "futures_symbol_bias.json"
FUTURES_LOSS_FILE = STATE_DIR / "futures_loss_streak.json"

SYMBOLS = [
    "BTC-USD", "ETH-USD", "SOL-USD", "XRP-USD", "ADA-USD",
    "DOGE-USD", "AVAX-USD", "LINK-USD", "LTC-USD", "BCH-USD"
]

FUTURES_SYMBOLS = ["ES", "NQ", "CL", "GC"]

FX_SYMBOLS = [
    "EUR_USD", "GBP_USD", "USD_JPY", "USD_CHF",
    "AUD_USD", "USD_CAD", "NZD_USD",
    "EUR_GBP", "EUR_JPY", "GBP_JPY"
]

OPTION_SYMBOLS = ["AAPL-C", "SPY-C"]

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
    "BLOCK": 0.0,
    "REDUCE": 0.5,
    "ALLOW": 1.0,
    "PRIORITIZE": 1.5,
}

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

ENGINE_MODES = {
    "1": "SAFE",
    "2": "CONSERVATIVE",
    "3": "BALANCED",
    "4": "AGGRESSIVE",
    "5": "EXPANSION",
}

# Relaxed V3 thresholds to restore trade flow while keeping filtering active.
V3_PROBABILITY_THRESHOLDS = {
    "CRYPTO": 0.30,
    "FX": 0.32,
    "OPTIONS": 0.28,
    "FUTURES": 0.34,
}

V3_DECISION_SCORE_FLOORS = {
    "CRYPTO": 0.18,
    "FX": 0.20,
    "OPTIONS": 0.16,
    "FUTURES": 0.22,
}


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
    for k, v in ENGINE_MODES.items():
        print(f"{k}. {v}")
    choice = input("Enter choice (1-5) [default=3]: ").strip()
    return ENGINE_MODES.get(choice, "BALANCED")


ENGINE_MODE = select_engine_mode()

pm = PositionManager()
futures_adapter = FuturesSimAdapter(max_portfolio_allocation=5.0)
futures_pm = FuturesPositionManager(futures_adapter)

options_adapter = OptionsChainAdapter()
options_pm = OptionsPositionManager()
options_intel = OptionsIntelligenceEngine()
trade_orchestrator = TradeDecisionOrchestrator()

futures_symbol_bias = load_json_state(
    FUTURES_BIAS_FILE,
    {s: 1.0 for s in FUTURES_SYMBOLS},
)

futures_loss_streak = load_json_state(
    FUTURES_LOSS_FILE,
    {s: 0 for s in FUTURES_SYMBOLS},
)

crypto_pnl = {s: 0.0 for s in SYMBOLS}
crypto_trades = {s: 0 for s in SYMBOLS}
crypto_wins = {s: 0 for s in SYMBOLS}

fx_pnl = {s: 0.0 for s in FX_SYMBOLS}
fx_trades = {s: 0 for s in FX_SYMBOLS}
fx_wins = {s: 0 for s in FX_SYMBOLS}

options_pnl = {s: 0.0 for s in OPTION_SYMBOLS}
options_trades = {s: 0 for s in OPTION_SYMBOLS}
options_wins = {s: 0 for s in OPTION_SYMBOLS}

futures_realized_pnl = {s: 0.0 for s in FUTURES_SYMBOLS}
futures_trade_count = {s: 0 for s in FUTURES_SYMBOLS}
futures_win_count = {s: 0 for s in FUTURES_SYMBOLS}

futures_lifetime_total = 0.0
last_trade = "NONE"
cycle = 0


def clamp_bias(v):
    return max(BIAS_MIN, min(BIAS_MAX, v))


def generate_mock_candles():
    return [{"close": random.uniform(90, 110)} for _ in range(30)]


def probability_gate(symbol: str, asset_class: str):
    candles = generate_mock_candles()
    decision = trade_orchestrator.evaluate_trade(symbol, candles)

    win_prob = float(decision.get("win_probability", 0.0))
    decision_score = float(decision.get("decision_score", 0.0))

    min_prob = V3_PROBABILITY_THRESHOLDS.get(asset_class, 0.30)
    min_score = V3_DECISION_SCORE_FLOORS.get(asset_class, 0.18)

    probability_pass = win_prob >= min_prob
    score_pass = decision_score >= min_score

    # Relaxed EV calibration to avoid total freeze while still penalizing weak setups.
    ev = ((1.35 * win_prob) - 0.35) * 100.0

    decision["asset_class"] = asset_class
    decision["min_required_probability"] = min_prob
    decision["min_required_decision_score"] = min_score
    decision["probability_pass"] = probability_pass
    decision["score_pass"] = score_pass
    decision["threshold_label"] = f"{asset_class}_V3"
    decision["expected_value_score"] = ev

    if not probability_pass or not score_pass:
        decision["execute_trade"] = False

    return decision


def apply_bias_decay():
    for symbol, current in list(futures_symbol_bias.items()):
        if current > BIAS_NEUTRAL:
            current -= ((current - BIAS_NEUTRAL) * BIAS_DECAY_RATE)
        elif current < BIAS_NEUTRAL:
            current += ((BIAS_NEUTRAL - current) * BIAS_DECAY_RATE)
        futures_symbol_bias[symbol] = clamp_bias(current)


def update_reinforcement(symbol, pnl):
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


def weighted_score(raw_score, symbol):
    return raw_score * futures_symbol_bias.get(symbol, BIAS_NEUTRAL)


def get_total_pnl():
    return round(
        sum(crypto_pnl.values()) +
        sum(fx_pnl.values()) +
        sum(options_pnl.values()) +
        sum(futures_realized_pnl.values()),
        4,
    )


def get_top_winner():
    combined = {}
    combined.update(crypto_pnl)
    combined.update(fx_pnl)
    combined.update(options_pnl)
    combined.update(futures_realized_pnl)
    return max(combined.items(), key=lambda x: x[1])


def get_top_loser():
    combined = {}
    combined.update(crypto_pnl)
    combined.update(fx_pnl)
    combined.update(options_pnl)
    combined.update(futures_realized_pnl)
    return min(combined.items(), key=lambda x: x[1])


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
        "capital_mult": CAPITAL_MULTIPLIERS[priority],
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
        "distance_pct": distance_pct,
    }


def compute_volatility_state(symbol):
    state = random.choice(list(VOL_STATES.keys()))
    return {"state": state, "mult": VOL_STATES[state]}


def compute_liquidity_sweep(symbol):
    state = random.choice(list(SWEEP_STATES.keys()))
    return {"state": state, "mult": SWEEP_STATES[state]}


def execute_trade(asset_class, symbol, score, eff_mult):
    global futures_lifetime_total, last_trade

    if score < 10:
        return

    pnl = round(random.uniform(-20, 20) * eff_mult, 4)
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
        update_reinforcement(symbol, pnl)

    print(f"[{asset_class} EXECUTED] {symbol} pnl={pnl:+.4f}")


while True:
    cycle += 1
    print(f"\n=== Cycle {cycle} | {datetime.now()} ===")

    apply_bias_decay()

    total = get_total_pnl()
    winner_sym, winner_val = get_top_winner()
    loser_sym, loser_val = get_top_loser()

    print("\n--- LIVE EXECUTION SUMMARY ---")
    print(f"TOTAL PNL: {total:+.4f}")
    print(f"CRYPTO OPEN: {sum(crypto_trades.values())} | PNL {sum(crypto_pnl.values()):+.4f}")
    print(f"FX OPEN: {sum(fx_trades.values())} | PNL {sum(fx_pnl.values()):+.4f}")
    print(f"OPTIONS OPEN: {sum(options_trades.values())} | PNL {sum(options_pnl.values()):+.4f}")
    print(f"FUTURES OPEN: {sum(futures_trade_count.values())} | PNL {sum(futures_realized_pnl.values()):+.4f}")
    print(f"TOP WINNER: {winner_sym} {winner_val:+.4f}")
    print(f"TOP LOSER: {loser_sym} {loser_val:+.4f}")
    print(f"LAST TRADE: {last_trade}")
    print("-" * 60)

    regime_board = []
    capital_board = []
    vwap_board = []
    volatility_board = []
    sweep_board = []
    effective_board = []

    # ==============================
    # CRYPTO EXECUTION WITH V3 THRESHOLDS
    # ==============================
    for s in SYMBOLS:
        safe_load_runtime_asset(s)

        reg = detect_regime(s, "CRYPTO")
        vw = compute_vwap_state(s)
        vol = compute_volatility_state(s)
        sw = compute_liquidity_sweep(s)

        eff = reg["capital_mult"] * vw["mult"] * vol["mult"] * sw["mult"]

        regime_board.append((s, "CRYPTO", reg))
        capital_board.append((s, reg["priority"], reg["capital_mult"]))
        vwap_board.append((s, vw))
        volatility_board.append((s, vol))
        sweep_board.append((s, sw))
        effective_board.append(
            (s, "CRYPTO", reg["priority"], vw["state"], vol["state"], sw["state"], eff)
        )

        if reg["priority"] != "BLOCK":
            decision = probability_gate(s, "CRYPTO")

            if decision["execute_trade"]:
                raw_score = round(random.uniform(8, 18), 2)
                score = raw_score * reg["risk_mult"] * vw["mult"] * vol["mult"] * sw["mult"]
                execute_trade("CRYPTO", s, round(score, 2), eff)
            else:
                print(
                    f"[CRYPTO REJECTED] {s} "
                    f"P+={decision['win_probability']:.2%} "
                    f"EV={decision['expected_value_score']:+.2f}"
                )

    # ==============================
    # FX EXECUTION WITH V3 THRESHOLDS
    # ==============================
    for s in FX_SYMBOLS:
        reg = detect_regime(s, "FX")
        vw = compute_vwap_state(s)
        vol = compute_volatility_state(s)
        sw = compute_liquidity_sweep(s)

        eff = reg["capital_mult"] * vw["mult"] * vol["mult"] * sw["mult"]

        regime_board.append((s, "FX", reg))
        capital_board.append((s, reg["priority"], reg["capital_mult"]))
        vwap_board.append((s, vw))
        volatility_board.append((s, vol))
        sweep_board.append((s, sw))
        effective_board.append(
            (s, "FX", reg["priority"], vw["state"], vol["state"], sw["state"], eff)
        )

        if reg["priority"] != "BLOCK":
            decision = probability_gate(s, "FX")

            if decision["execute_trade"]:
                raw_score = round(random.uniform(8, 18), 2)
                score = raw_score * reg["risk_mult"] * vw["mult"] * vol["mult"] * sw["mult"]
                execute_trade("FX", s, round(score, 2), eff)
            else:
                print(
                    f"[FX REJECTED] {s} "
                    f"P+={decision['win_probability']:.2%} "
                    f"EV={decision['expected_value_score']:+.2f}"
                )

    # ==============================
    # OPTIONS EXECUTION WITH V3 THRESHOLDS
    # ==============================
    for s in OPTION_SYMBOLS:
        reg = detect_regime(s, "OPTIONS")
        vw = compute_vwap_state(s)
        vol = compute_volatility_state(s)
        sw = compute_liquidity_sweep(s)

        eff = reg["capital_mult"] * vw["mult"] * vol["mult"] * sw["mult"]

        regime_board.append((s, "OPTIONS", reg))
        capital_board.append((s, reg["priority"], reg["capital_mult"]))
        vwap_board.append((s, vw))
        volatility_board.append((s, vol))
        sweep_board.append((s, sw))
        effective_board.append(
            (s, "OPTIONS", reg["priority"], vw["state"], vol["state"], sw["state"], eff)
        )

        if reg["priority"] != "BLOCK":
            decision = probability_gate(s, "OPTIONS")

            if decision["execute_trade"]:
                raw_score = round(random.uniform(8, 18), 2)
                score = raw_score * reg["risk_mult"] * vw["mult"] * vol["mult"] * sw["mult"]
                execute_trade("OPTIONS", s, round(score, 2), eff)
            else:
                print(
                    f"[OPTIONS REJECTED] {s} "
                    f"P+={decision['win_probability']:.2%} "
                    f"EV={decision['expected_value_score']:+.2f}"
                )

    # ==============================
    # FUTURES EXECUTION WITH V3 THRESHOLDS
    # ==============================
    if random.random() < 0.35:
        symbol = random.choice(FUTURES_SYMBOLS)

        reg = detect_regime(symbol, "FUTURES")
        vw = compute_vwap_state(symbol)
        vol = compute_volatility_state(symbol)
        sw = compute_liquidity_sweep(symbol)

        eff = reg["capital_mult"] * vw["mult"] * vol["mult"] * sw["mult"]

        regime_board.append((symbol, "FUTURES", reg))
        capital_board.append((symbol, reg["priority"], reg["capital_mult"]))
        vwap_board.append((symbol, vw))
        volatility_board.append((symbol, vol))
        sweep_board.append((symbol, sw))
        effective_board.append(
            (symbol, "FUTURES", reg["priority"], vw["state"], vol["state"], sw["state"], eff)
        )

        if reg["priority"] != "BLOCK":
            decision = probability_gate(symbol, "FUTURES")

            if decision["execute_trade"]:
                raw_score = round(random.uniform(8, 18), 2)
                score = weighted_score(raw_score, symbol)
                score *= reg["risk_mult"] * vw["mult"] * vol["mult"] * sw["mult"]
                execute_trade("FUTURES", symbol, round(score, 2), eff)
            else:
                print(
                    f"[FUTURES REJECTED] {symbol} "
                    f"P+={decision['win_probability']:.2%} "
                    f"EV={decision['expected_value_score']:+.2f}"
                )

    save_json_state(FUTURES_BIAS_FILE, futures_symbol_bias)
    save_json_state(FUTURES_LOSS_FILE, futures_loss_streak)

    print("\n--- LIQUIDITY SWEEP BOARD ---")
    for sym, sw in sweep_board[:12]:
        print(f"{sym} | {sw['state']} | {sw['mult']:.2f}x")

    print("\n--- VWAP BOARD ---")
    for sym, vw in vwap_board[:12]:
        print(f"{sym} | {vw['distance_pct']:+.2f}% | {vw['state']}")

    print("\n--- VOLATILITY BOARD ---")
    for sym, vol in volatility_board[:12]:
        print(f"{sym} | {vol['state']} | {vol['mult']:.2f}x")

    print("\n--- UNIVERSAL EFFECTIVE BOARD ---")
    for sym, cls, pri, vwstate, volstate, swstate, eff in effective_board[:12]:
        print(
            f"{sym} | {cls} | {pri} | "
            f"{vwstate} | {volstate} | {swstate} | Eff {eff:.2f}x"
        )

    print("\n--- FUTURES SYMBOL BIAS ---")
    print(futures_symbol_bias)

    time.sleep(CYCLE_SLEEP)