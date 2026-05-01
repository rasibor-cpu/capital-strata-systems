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

STATE_DIR = PROJECT_ROOT / "artifacts"
STATE_DIR.mkdir(exist_ok=True)

FUTURES_BIAS_FILE = STATE_DIR / "futures_symbol_bias.json"
FUTURES_LOSS_FILE = STATE_DIR / "futures_loss_streak.json"

CRYPTO_PNL_FILE = STATE_DIR / "crypto_pnl.json"
FX_PNL_FILE = STATE_DIR / "fx_pnl.json"
OPTIONS_PNL_FILE = STATE_DIR / "options_pnl.json"
FUTURES_PNL_FILE = STATE_DIR / "futures_pnl.json"

CRYPTO_TRADES_FILE = STATE_DIR / "crypto_trades.json"
FX_TRADES_FILE = STATE_DIR / "fx_trades.json"
OPTIONS_TRADES_FILE = STATE_DIR / "options_trades.json"
FUTURES_TRADES_FILE = STATE_DIR / "futures_trades.json"

CRYPTO_WINS_FILE = STATE_DIR / "crypto_wins.json"
FX_WINS_FILE = STATE_DIR / "fx_wins.json"
OPTIONS_WINS_FILE = STATE_DIR / "options_wins.json"
FUTURES_WINS_FILE = STATE_DIR / "futures_wins.json"

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

OPTION_SYMBOLS = ["AAPL-C", "SPY-C", "QQQ-C"]

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

BLEED_GOVERNOR_ENABLED = True
BLEED_GOVERNOR_RATIO = 0.25

OPTION_FALLBACK_MAX_PRICE = 6.50
OPTION_MIN_PROBABILITY = 0.60
OPTION_MIN_EXPECTED_VALUE = 1.50
OPTION_MIN_SIGNAL_SCORE = 11.25
OPTION_FORCE_FALLBACK_ONLY_IF_STRONG = True


def load_json_state(path: Path, default: Dict):
    try:
        if path.exists():
            with open(path, "r") as f:
                loaded = json.load(f)

            if isinstance(default, dict) and isinstance(loaded, dict):
                merged = default.copy()
                merged.update(loaded)
                return merged

            return loaded
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


def clamp_bias(v):
    return max(BIAS_MIN, min(BIAS_MAX, v))


def weighted_score(raw_score, symbol):
    return raw_score * futures_symbol_bias.get(symbol, BIAS_NEUTRAL)


def normalize_option_type(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None

    raw = str(value).strip().upper()

    if raw in {"CALL", "C"}:
        return "CALL"
    if raw in {"PUT", "P"}:
        return "PUT"
    if raw.startswith("CALL"):
        return "CALL"
    if raw.startswith("PUT"):
        return "PUT"
    if raw.startswith("C"):
        return "CALL"
    if raw.startswith("P"):
        return "PUT"

    return None


def get_selected_option_type(selected: Dict) -> Optional[str]:
    candidates = [
        selected.get("option_type"),
        selected.get("type"),
        selected.get("right"),
        selected.get("call_put"),
        selected.get("contract_type"),
        selected.get("side"),
        selected.get("direction"),
    ]

    for candidate in candidates:
        normalized = normalize_option_type(candidate)
        if normalized:
            return normalized

    symbol_like = (
        selected.get("symbol")
        or selected.get("option_symbol")
        or selected.get("contract_symbol")
        or selected.get("contract")
        or selected.get("ticker")
    )
    if symbol_like:
        raw = str(symbol_like).upper()
        if "-C-" in raw or raw.endswith("-C") or raw.endswith("C"):
            return "CALL"
        if "-P-" in raw or raw.endswith("-P") or raw.endswith("P"):
            return "PUT"

    return None


def get_selected_strike(selected: Dict) -> Optional[float]:
    candidates = [
        selected.get("strike"),
        selected.get("strike_price"),
        selected.get("k"),
    ]
    for candidate in candidates:
        if candidate is None:
            continue
        try:
            return float(candidate)
        except Exception:
            continue
    return None


def get_selected_expiry(selected: Dict) -> Optional[str]:
    candidates = [
        selected.get("expiry"),
        selected.get("expiration"),
        selected.get("expiration_date"),
        selected.get("expiry_date"),
        selected.get("exp_date"),
    ]
    for candidate in candidates:
        if candidate:
            return str(candidate)
    return None


def get_selected_entry_price(selected: Dict) -> Optional[float]:
    candidates = [
        selected.get("price"),
        selected.get("premium"),
        selected.get("mid"),
        selected.get("mark"),
        selected.get("last"),
        selected.get("last_price"),
        selected.get("ask"),
        selected.get("bid"),
    ]
    for candidate in candidates:
        if candidate is None:
            continue
        try:
            return float(candidate)
        except Exception:
            continue
    return None


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


ENGINE_MODE = select_engine_mode()

pm = PositionManager()
futures_adapter = FuturesSimAdapter(max_portfolio_allocation=5.0)
futures_pm = FuturesPositionManager(futures_adapter)

options_adapter = OptionsChainAdapter()
options_pm = OptionsPositionManager()
options_intel = OptionsIntelligenceEngine()
options_pricing_engine = OptionPricingCalibrationEngine()
options_expiry_engine = OptionExpiryParserEngine()

futures_symbol_bias = load_json_state(
    FUTURES_BIAS_FILE,
    {s: 1.0 for s in FUTURES_SYMBOLS}
)

futures_loss_streak = load_json_state(
    FUTURES_LOSS_FILE,
    {s: 0 for s in FUTURES_SYMBOLS}
)

crypto_pnl = load_json_state(CRYPTO_PNL_FILE, {s: 0.0 for s in SYMBOLS})
crypto_trades = load_json_state(CRYPTO_TRADES_FILE, {s: 0 for s in SYMBOLS})
crypto_wins = load_json_state(CRYPTO_WINS_FILE, {s: 0 for s in SYMBOLS})

fx_pnl = load_json_state(FX_PNL_FILE, {s: 0.0 for s in FX_SYMBOLS})
fx_trades = load_json_state(FX_TRADES_FILE, {s: 0 for s in FX_SYMBOLS})
fx_wins = load_json_state(FX_WINS_FILE, {s: 0 for s in FX_SYMBOLS})

options_pnl = load_json_state(OPTIONS_PNL_FILE, {})
options_trades = load_json_state(OPTIONS_TRADES_FILE, {})
options_wins = load_json_state(OPTIONS_WINS_FILE, {})

futures_realized_pnl = load_json_state(FUTURES_PNL_FILE, {s: 0.0 for s in FUTURES_SYMBOLS})
futures_trade_count = load_json_state(FUTURES_TRADES_FILE, {s: 0 for s in FUTURES_SYMBOLS})
futures_win_count = load_json_state(FUTURES_WINS_FILE, {s: 0 for s in FUTURES_SYMBOLS})

futures_lifetime_total = sum(float(v) for v in futures_realized_pnl.values())
last_trade = "NONE"
cycle = 0


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


def save_all_runtime_state():
    save_json_state(FUTURES_BIAS_FILE, futures_symbol_bias)
    save_json_state(FUTURES_LOSS_FILE, futures_loss_streak)

    save_json_state(CRYPTO_PNL_FILE, crypto_pnl)
    save_json_state(FX_PNL_FILE, fx_pnl)
    save_json_state(OPTIONS_PNL_FILE, options_pnl)
    save_json_state(FUTURES_PNL_FILE, futures_realized_pnl)

    save_json_state(CRYPTO_TRADES_FILE, crypto_trades)
    save_json_state(FX_TRADES_FILE, fx_trades)
    save_json_state(OPTIONS_TRADES_FILE, options_trades)
    save_json_state(FUTURES_TRADES_FILE, futures_trade_count)

    save_json_state(CRYPTO_WINS_FILE, crypto_wins)
    save_json_state(FX_WINS_FILE, fx_wins)
    save_json_state(OPTIONS_WINS_FILE, options_wins)
    save_json_state(FUTURES_WINS_FILE, futures_win_count)


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
        options_pnl[symbol] = options_pnl.get(symbol, 0.0) + pnl
        options_trades[symbol] = options_trades.get(symbol, 0) + 1
        if pnl > 0:
            options_wins[symbol] = options_wins.get(symbol, 0) + 1

    elif asset_class == "FUTURES":
        futures_realized_pnl[symbol] += pnl
        futures_trade_count[symbol] += 1
        futures_lifetime_total += pnl
        if pnl > 0:
            futures_win_count[symbol] += 1
        update_reinforcement(symbol, pnl)

    save_all_runtime_state()
    print(f"[{asset_class} EXECUTED] {symbol} pnl={pnl:+.4f}")


def get_total_pnl():
    return round(
        sum(crypto_pnl.values()) +
        sum(fx_pnl.values()) +
        sum(options_pnl.values()) +
        sum(futures_realized_pnl.values()),
        4
    )


def get_top_winner():
    combined = {}
    combined.update({f"CRYPTO:{k}": v for k, v in crypto_pnl.items()})
    combined.update({f"FX:{k}": v for k, v in fx_pnl.items()})
    combined.update({f"OPTIONS:{k}": v for k, v in options_pnl.items()})
    combined.update({f"FUTURES:{k}": v for k, v in futures_realized_pnl.items()})
    return max(combined.items(), key=lambda x: x[1]) if combined else ("NONE", 0.0)


def get_top_loser():
    combined = {}
    combined.update({f"CRYPTO:{k}": v for k, v in crypto_pnl.items()})
    combined.update({f"FX:{k}": v for k, v in fx_pnl.items()})
    combined.update({f"OPTIONS:{k}": v for k, v in options_pnl.items()})
    combined.update({f"FUTURES:{k}": v for k, v in futures_realized_pnl.items()})
    return min(combined.items(), key=lambda x: x[1]) if combined else ("NONE", 0.0)


def get_asset_class_pnls() -> Dict[str, float]:
    return {
        "CRYPTO": round(sum(crypto_pnl.values()), 4),
        "FX": round(sum(fx_pnl.values()), 4),
        "OPTIONS": round(sum(options_pnl.values()), 4),
        "FUTURES": round(sum(futures_realized_pnl.values()), 4),
    }


def get_bleed_governor_state(
    asset_class: str,
    snapshot: Optional[Dict[str, float]] = None
) -> Tuple[bool, float, float, float]:
    pnl_map = snapshot if snapshot is not None else get_asset_class_pnls()
    asset_pnl = float(pnl_map.get(asset_class, 0.0))

    if not BLEED_GOVERNOR_ENABLED:
        return False, 0.0, 0.0, 0.0

    if asset_pnl >= 0:
        return False, 0.0, 0.0, 0.0

    other_positive_total = 0.0
    for name, pnl in pnl_map.items():
        if name == asset_class:
            continue
        if pnl > 0:
            other_positive_total += pnl

    if other_positive_total <= 0:
        return False, abs(asset_pnl), 0.0, other_positive_total

    freeze_limit = BLEED_GOVERNOR_RATIO * other_positive_total
    asset_loss_abs = abs(asset_pnl)
    is_frozen = asset_loss_abs > freeze_limit

    return is_frozen, round(asset_loss_abs, 4), round(freeze_limit, 4), round(other_positive_total, 4)


def execute_intelligent_option_trade(
    option_symbol_stub,
    reg,
    vw,
    vol,
    sw,
    cycle,
    eff,
    cycle_pnl_snapshot=None
):
    global last_trade

    if reg["priority"] == "BLOCK":
        print(f"[OPTIONS SKIPPED] {option_symbol_stub} blocked by regime")
        return

    governor_frozen, asset_loss, freeze_limit, other_positive = get_bleed_governor_state(
        "OPTIONS",
        cycle_pnl_snapshot
    )
    if governor_frozen:
        print(
            f"[BLEED FREEZE] OPTIONS "
            f"LOSS={asset_loss:.4f} "
            f"LIMIT={freeze_limit:.4f} "
            f"OTHERS+={other_positive:.4f}"
        )
        return

    direction = "CALL" if vw["distance_pct"] >= 0 else "PUT"
    underlying_symbol = option_symbol_stub.split("-")[0]

    underlying_rows = [{
        "symbol": underlying_symbol,
        "price": round(random.uniform(90, 250), 2)
    }]

    option_rows = options_adapter.fetch_option_rows(underlying_rows)

    if not option_rows:
        print(f"[OPTIONS SKIPPED] {underlying_symbol} no option rows returned")
        return

    raw_score = round(random.uniform(8, 18), 2)
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

    if (
        not allow_trade
        or prob_pos < OPTION_MIN_PROBABILITY
        or ev < OPTION_MIN_EXPECTED_VALUE
        or signal_score < OPTION_MIN_SIGNAL_SCORE
    ):
        print(
            f"[OPTIONS REJECTED] {underlying_symbol} "
            f"P+={prob_pos:.2%} EV={ev:+.2f} SCORE={signal_score:.2f}"
        )
        return

    selected = options_intel.select_best_option(
        options=option_rows,
        underlying_price=underlying_rows[0]["price"],
        score=signal_score,
        tier="ELITE" if signal_score > 16 else "QUALIFIED",
        direction=direction
    )

    used_fallback_contract = False
    if not selected:
        if OPTION_FORCE_FALLBACK_ONLY_IF_STRONG and (prob_pos < 0.66 or ev < 2.25):
            print(
                f"[OPTIONS SKIPPED] {underlying_symbol} no contract selected "
                f"and fallback quality not strong enough"
            )
            return
        selected = option_rows[0]
        used_fallback_contract = True
        print(f"[OPTIONS FALLBACK] {underlying_symbol} using first available contract")

    option_type = get_selected_option_type(selected)
    if option_type is None:
        option_type = direction
        print(f"[OPTIONS FALLBACK] {underlying_symbol} using direction as option_type={option_type}")

    strike = get_selected_strike(selected)
    if strike is None:
        try:
            strike = float(round(underlying_rows[0]["price"]))
            print(f"[OPTIONS FALLBACK] {underlying_symbol} using synthetic strike={strike}")
        except Exception:
            print(f"[OPTIONS SKIPPED] {underlying_symbol} missing strike schema")
            return

    expiry = get_selected_expiry(selected)
    if expiry is None:
        expiry = "SIM-EXPIRY"
        print(f"[OPTIONS FALLBACK] {underlying_symbol} using synthetic expiry={expiry}")

    entry_price = get_selected_entry_price(selected)
    if entry_price is None:
        expiry_result = options_expiry_engine.build_expiry_result(
            selected,
            fallback_days=14
        )
        pricing_result = options_pricing_engine.estimate_premium(
            underlying_price=float(underlying_rows[0]["price"]),
            strike=float(strike),
            option_type=option_type,
            volatility_multiplier=float(vol["mult"]),
            days_to_expiry=int(expiry_result["days_to_expiry"])
        )
        entry_price = round(pricing_result.premium, 2)
        print(
            f"[OPTIONS FALLBACK] {underlying_symbol} calibrated price={entry_price} "
            f"intrinsic={pricing_result.intrinsic_value:.2f} "
            f"time={pricing_result.time_value:.2f} "
            f"decay={pricing_result.decay_factor:.2f} "
            f"dte={expiry_result['days_to_expiry']} "
            f"expiry={expiry_result['expiry_string']}"
        )

    if used_fallback_contract and entry_price > OPTION_FALLBACK_MAX_PRICE:
        print(
            f"[OPTIONS SKIPPED] {underlying_symbol} fallback contract too expensive "
            f"price={entry_price:.2f}"
        )
        return

    option_symbol = (
        f"{underlying_symbol}-"
        f"{option_type[0]}-"
        f"{int(strike)}"
    )

    open_result = options_pm.open_long_option(
        option_symbol=option_symbol,
        underlying_symbol=underlying_symbol,
        option_type=option_type,
        strike=strike,
        expiry=expiry,
        entry_price=entry_price,
        contracts=1,
        current_cycle=cycle,
        confidence=prob_pos,
        tier="ELITE" if signal_score > 16 else "QUALIFIED",
        note=f"PTPOP={prob_pos:.2%} EV={ev:+.2f}"
    )

    if open_result.get("status") == "OPENED":
        pnl_seed = round(random.uniform(-8, 15) * eff, 4)

        options_pnl[option_symbol] = options_pnl.get(option_symbol, 0.0) + pnl_seed
        options_trades[option_symbol] = options_trades.get(option_symbol, 0) + 1

        if pnl_seed > 0:
            options_wins[option_symbol] = options_wins.get(option_symbol, 0) + 1

        last_trade = f"{option_symbol} [{option_type}]"
        save_all_runtime_state()

        print(
            f"[OPTIONS EXECUTED] {option_symbol} "
            f"P+={prob_pos:.2%} EV={ev:+.2f} SCORE={signal_score:.2f}"
        )
    else:
        print(
            f"[OPTIONS NOT OPENED] {underlying_symbol} "
            f"status={open_result.get('status', 'UNKNOWN')}"
        )


while True:
    cycle += 1
    print(f"\n=== Cycle {cycle} | {datetime.now()} ===")

    apply_bias_decay()

    cycle_pnl_snapshot = get_asset_class_pnls()

    total = get_total_pnl()
    winner_sym, winner_val = get_top_winner()
    loser_sym, loser_val = get_top_loser()

    print("\n--- START-OF-CYCLE EXECUTION SUMMARY ---")
    print(f"TOTAL PNL: {total:+.4f}")
    print(f"CRYPTO TRADES: {sum(crypto_trades.values())} | PNL {sum(crypto_pnl.values()):+.4f}")
    print(f"FX TRADES: {sum(fx_trades.values())} | PNL {sum(fx_pnl.values()):+.4f}")
    print(f"OPTIONS TRADES: {sum(options_trades.values())} | PNL {sum(options_pnl.values()):+.4f}")
    print(f"FUTURES TRADES: {sum(futures_trade_count.values())} | PNL {sum(futures_realized_pnl.values()):+.4f}")
    print(f"TOP WINNER: {winner_sym} {winner_val:+.4f}")
    print(f"TOP LOSER: {loser_sym} {loser_val:+.4f}")
    print(f"LAST TRADE: {last_trade}")
    print("-" * 60)

    regime_board = []
    vwap_board = []
    volatility_board = []
    sweep_board = []
    effective_board = []

    for s in SYMBOLS:
        safe_load_runtime_asset(s)

        reg = detect_regime(s, "CRYPTO")
        vw = compute_vwap_state(s)
        vol = compute_volatility_state(s)
        sw = compute_liquidity_sweep(s)

        eff = reg["capital_mult"] * vw["mult"] * vol["mult"] * sw["mult"]

        regime_board.append((s, "CRYPTO", reg))
        vwap_board.append((s, vw))
        volatility_board.append((s, vol))
        sweep_board.append((s, sw))
        effective_board.append(
            (s, "CRYPTO", reg["priority"], vw["state"], vol["state"], sw["state"], eff)
        )

        if reg["priority"] == "BLOCK":
            continue

        governor_frozen, asset_loss, freeze_limit, other_positive = get_bleed_governor_state(
            "CRYPTO",
            cycle_pnl_snapshot
        )
        if governor_frozen:
            print(
                f"[BLEED FREEZE] CRYPTO "
                f"LOSS={asset_loss:.4f} "
                f"LIMIT={freeze_limit:.4f} "
                f"OTHERS+={other_positive:.4f}"
            )
            continue

        raw_score = round(random.uniform(8, 18), 2)
        signal_score = raw_score * reg["risk_mult"] * vw["mult"] * vol["mult"] * sw["mult"]

        prob_pos, prob_neg, ev, allow_trade = pt_engine.estimate(
            regime_conf=reg["confidence"],
            vwap_mult=vw["mult"],
            vol_mult=vol["mult"],
            sweep_mult=sw["mult"],
            raw_score=signal_score
        )

        if not allow_trade:
            print(f"[CRYPTO REJECTED] {s} P+={prob_pos:.2%} EV={ev:+.2f}")
            continue

        execute_trade("CRYPTO", s, round(signal_score, 2), eff)

    for s in FX_SYMBOLS:
        reg = detect_regime(s, "FX")
        vw = compute_vwap_state(s)
        vol = compute_volatility_state(s)
        sw = compute_liquidity_sweep(s)

        eff = reg["capital_mult"] * vw["mult"] * vol["mult"] * sw["mult"]

        regime_board.append((s, "FX", reg))
        vwap_board.append((s, vw))
        volatility_board.append((s, vol))
        sweep_board.append((s, sw))
        effective_board.append(
            (s, "FX", reg["priority"], vw["state"], vol["state"], sw["state"], eff)
        )

        if reg["priority"] == "BLOCK":
            continue

        governor_frozen, asset_loss, freeze_limit, other_positive = get_bleed_governor_state(
            "FX",
            cycle_pnl_snapshot
        )
        if governor_frozen:
            print(
                f"[BLEED FREEZE] FX "
                f"LOSS={asset_loss:.4f} "
                f"LIMIT={freeze_limit:.4f} "
                f"OTHERS+={other_positive:.4f}"
            )
            continue

        raw_score = round(random.uniform(8, 18), 2)
        signal_score = raw_score * reg["risk_mult"] * vw["mult"] * vol["mult"] * sw["mult"]

        prob_pos, prob_neg, ev, allow_trade = pt_engine.estimate(
            regime_conf=reg["confidence"],
            vwap_mult=vw["mult"],
            vol_mult=vol["mult"],
            sweep_mult=sw["mult"],
            raw_score=signal_score
        )

        if not allow_trade:
            print(f"[FX REJECTED] {s} P+={prob_pos:.2%} EV={ev:+.2f}")
            continue

        execute_trade("FX", s, round(signal_score, 2), eff)

    for s in OPTION_SYMBOLS:
        reg = detect_regime(s, "OPTIONS")
        vw = compute_vwap_state(s)
        vol = compute_volatility_state(s)
        sw = compute_liquidity_sweep(s)

        eff = reg["capital_mult"] * vw["mult"] * vol["mult"] * sw["mult"]

        regime_board.append((s, "OPTIONS", reg))
        vwap_board.append((s, vw))
        volatility_board.append((s, vol))
        sweep_board.append((s, sw))
        effective_board.append(
            (s, "OPTIONS", reg["priority"], vw["state"], vol["state"], sw["state"], eff)
        )

        execute_intelligent_option_trade(
            s, reg, vw, vol, sw, cycle, eff, cycle_pnl_snapshot
        )

    for symbol in FUTURES_SYMBOLS:
        reg = detect_regime(symbol, "FUTURES")
        vw = compute_vwap_state(symbol)
        vol = compute_volatility_state(symbol)
        sw = compute_liquidity_sweep(symbol)

        eff = reg["capital_mult"] * vw["mult"] * vol["mult"] * sw["mult"]

        regime_board.append((symbol, "FUTURES", reg))
        vwap_board.append((symbol, vw))
        volatility_board.append((symbol, vol))
        sweep_board.append((symbol, sw))
        effective_board.append(
            (symbol, "FUTURES", reg["priority"], vw["state"], vol["state"], sw["state"], eff)
        )

        if reg["priority"] == "BLOCK":
            continue

        governor_frozen, asset_loss, freeze_limit, other_positive = get_bleed_governor_state(
            "FUTURES",
            cycle_pnl_snapshot
        )
        if governor_frozen:
            print(
                f"[BLEED FREEZE] FUTURES "
                f"LOSS={asset_loss:.4f} "
                f"LIMIT={freeze_limit:.4f} "
                f"OTHERS+={other_positive:.4f}"
            )
            continue

        raw_score = round(random.uniform(8, 18), 2)
        weighted = weighted_score(raw_score, symbol)

        signal_score = (
            weighted *
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

        if allow_trade:
            execute_trade("FUTURES", symbol, round(signal_score, 2), eff)
        else:
            print(
                f"[FUTURES REJECTED] {symbol} "
                f"P+={prob_pos:.2%} EV={ev:+.2f}"
            )

    save_all_runtime_state()

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

    print("\n--- END-OF-CYCLE TRUE PNL SUMMARY ---")
    print(f"TOTAL PNL: {get_total_pnl():+.4f}")
    print(f"CRYPTO PNL: {sum(crypto_pnl.values()):+.4f}")
    print(f"FX PNL: {sum(fx_pnl.values()):+.4f}")
    print(f"OPTIONS PNL: {sum(options_pnl.values()):+.4f}")
    print(f"FUTURES PNL: {sum(futures_realized_pnl.values()):+.4f}")
    print("-" * 60)

    time.sleep(CYCLE_SLEEP)
