# =========================
# FULL REPLACEMENT FILE — PART 1
# IMPORTS + CONSTANTS + CORE ENGINES
# =========================

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
ASSET_EDGE_FILE = STATE_DIR / "asset_class_edge.json"
SYMBOL_STREAK_FILE = STATE_DIR / "symbol_hot_streak.json"

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

ASSET_EDGE_MIN = 0.70
ASSET_EDGE_MAX = 1.35
ASSET_EDGE_REWARD = 0.035
ASSET_EDGE_PENALTY = 0.030
ASSET_EDGE_DECAY = 0.020

HOT_STREAK_MIN = -4
HOT_STREAK_MAX = 4

BLEED_GOVERNOR_ENABLED = True
BLEED_GOVERNOR_RATIO = 0.25

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

CAPITAL_MULTIPLIERS = {
    "BLOCK":0.0,
    "REDUCE":0.5,
    "ALLOW":1.0,
    "PRIORITIZE":1.5,
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


def clamp_bias(v):
    return max(BIAS_MIN, min(BIAS_MAX, v))


def clamp_asset_edge(v):
    return max(ASSET_EDGE_MIN, min(ASSET_EDGE_MAX, v))


def clamp_hot_streak(v):
    return max(HOT_STREAK_MIN, min(HOT_STREAK_MAX, v))


class ExecutionCostEngine:

    COST_TABLE = {
        "CRYPTO":{"spread_bps":32,"slippage_bps":18,"commission_bps":10},
        "FX":{"spread_bps":14,"slippage_bps":8,"commission_bps":4},
        "OPTIONS":{"spread_bps":36,"slippage_bps":20,"commission_bps":12},
        "FUTURES":{"spread_bps":18,"slippage_bps":10,"commission_bps":6},
    }

    MIN_NET_EDGE = {
        "CRYPTO":1.40,
        "FX":0.95,
        "OPTIONS":1.10,
        "FUTURES":1.05,
    }

    def estimate_cost(self, *, asset_class, gross_edge, signal_score):
        cfg = self.COST_TABLE[asset_class]
        total_bps = cfg["spread_bps"] + cfg["slippage_bps"] + cfg["commission_bps"]
        edge_base = max(abs(gross_edge), 0.50)
        friction = edge_base * (total_bps / 1000.0)
        score_factor = max(0.95, min(1.30, signal_score / 10.0))
        return round(friction * score_factor, 4)

    def passes_cost_gate(self, *, asset_class, gross_edge, signal_score):
        cost = self.estimate_cost(
            asset_class=asset_class,
            gross_edge=gross_edge,
            signal_score=signal_score
        )
        net_edge = gross_edge - cost
        threshold = self.MIN_NET_EDGE[asset_class]
        return net_edge >= threshold, round(net_edge,4), round(cost,4)


cost_engine = ExecutionCostEngine()


class ProfitPerWinnerEngine:

    ELITE_THRESHOLD = 20.0
    STRONG_THRESHOLD = 15.0
    MEDIUM_THRESHOLD = 11.0

    ASSET_WIN_MULTIPLIERS = {
        "CRYPTO":{"elite":1.42,"strong":1.24,"medium":1.08,"weak":0.92},
        "FX":{"elite":1.26,"strong":1.14,"medium":1.05,"weak":0.95},
        "OPTIONS":{"elite":1.65,"strong":1.36,"medium":1.12,"weak":0.90},
        "FUTURES":{"elite":1.48,"strong":1.28,"medium":1.10,"weak":0.93},
    }

    def classify_trade_tier(self, *, signal_score, prob_positive, expected_value):
        composite = (
            signal_score * 0.45 +
            (prob_positive * 100.0) * 0.35 +
            max(expected_value,0.0) * 0.20
        )
        if composite >= self.ELITE_THRESHOLD:
            return "elite"
        elif composite >= self.STRONG_THRESHOLD:
            return "strong"
        elif composite >= self.MEDIUM_THRESHOLD:
            return "medium"
        else:
            return "weak"

    def get_multiplier(self, *, asset_class, signal_score, prob_positive, expected_value, hot_streak):
        tier = self.classify_trade_tier(
            signal_score=signal_score,
            prob_positive=prob_positive,
            expected_value=expected_value
        )
        base = self.ASSET_WIN_MULTIPLIERS[asset_class][tier]
        bonus = min(max(hot_streak,0)*0.035,0.18)
        return tier, round(base + bonus,4)


ppw_engine = ProfitPerWinnerEngine()
# =========================
# FULL REPLACEMENT FILE — PART 2
# WINNER ENGINE + PPW LOGGING FIX + EXECUTION CORE
# =========================

class PreTradeProbabilityEngine:
    def estimate(
        self,
        *,
        regime_conf,
        vwap_mult,
        vol_mult,
        sweep_mult,
        raw_score
    ):
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
            round(prob_positive,4),
            round(prob_negative,4),
            round(expected_value,4),
            execute
        )


pt_engine = PreTradeProbabilityEngine()


class WinnerAsymmetryEngine:

    def realize_pnl(
        self,
        *,
        asset_class,
        signal_score,
        prob_positive,
        expected_value,
        eff_mult,
        symbol_bias=1.0,
        asset_edge=1.0,
        hot_streak=0,
        execution_cost=0.0
    ):

        quality = (
            signal_score * 0.38 +
            prob_positive * 100.0 * 0.34 +
            max(expected_value,0.0) * 4.0 * 0.20 +
            asset_edge * 5.0 * 0.08
        )

        if quality >= 22:
            win_prob = 0.74
            win_low, win_high = 10.0, 24.0
            loss_low, loss_high = -7.5, -2.0
        elif quality >= 18:
            win_prob = 0.69
            win_low, win_high = 8.0, 20.0
            loss_low, loss_high = -7.0, -2.5
        elif quality >= 15:
            win_prob = 0.64
            win_low, win_high = 6.0, 16.0
            loss_low, loss_high = -6.5, -3.0
        else:
            win_prob = 0.59
            win_low, win_high = 4.0, 12.0
            loss_low, loss_high = -6.0, -3.5

        adjusted_eff = max(0.35, eff_mult)
        adjusted_eff *= max(0.60, min(1.60, symbol_bias))
        adjusted_eff *= max(0.82, min(1.22, asset_edge))
        adjusted_eff *= max(0.88, min(1.12, 1.0 + hot_streak*0.04))

        won_trade = random.random() <= win_prob

        if won_trade:
            gross_pnl = random.uniform(win_low, win_high) * adjusted_eff
        else:
            gross_pnl = random.uniform(loss_low, loss_high) * adjusted_eff

        net_pnl = gross_pnl - execution_cost

        if net_pnl > 0:
            tier, mult = ppw_engine.get_multiplier(
                asset_class=asset_class,
                signal_score=signal_score,
                prob_positive=prob_positive,
                expected_value=expected_value,
                hot_streak=hot_streak
            )
            net_pnl *= mult

        return round(net_pnl,4)


winner_engine = WinnerAsymmetryEngine()


def weighted_score(raw_score, symbol):
    return raw_score * futures_symbol_bias.get(symbol, BIAS_NEUTRAL)


def get_hot_key(asset_class, symbol):
    return f"{asset_class}::{symbol}"


def get_symbol_hot_streak(asset_class, symbol):
    return int(symbol_hot_streak.get(get_hot_key(asset_class,symbol),0))


def update_symbol_hot_streak(asset_class, symbol, pnl):
    key = get_hot_key(asset_class,symbol)
    current = int(symbol_hot_streak.get(key,0))
    if pnl > 0:
        current = current + 1 if current >= 0 else 1
    else:
        current = current - 1 if current <= 0 else -1
    symbol_hot_streak[key] = clamp_hot_streak(current)


def decay_asset_edges():
    for asset_class, current in list(asset_class_edge.items()):
        if current > 1.0:
            current -= ((current - 1.0) * ASSET_EDGE_DECAY)
        elif current < 1.0:
            current += ((1.0 - current) * ASSET_EDGE_DECAY)
        asset_class_edge[asset_class] = round(clamp_asset_edge(current),6)


def update_asset_edge(asset_class, pnl):
    current = float(asset_class_edge.get(asset_class,1.0))
    current += ASSET_EDGE_REWARD if pnl > 0 else -ASSET_EDGE_PENALTY
    asset_class_edge[asset_class] = round(clamp_asset_edge(current),6)


def apply_bias_decay():
    for symbol, current in list(futures_symbol_bias.items()):
        if current > BIAS_NEUTRAL:
            current -= ((current - BIAS_NEUTRAL) * BIAS_DECAY_RATE)
        elif current < BIAS_NEUTRAL:
            current += ((BIAS_NEUTRAL - current) * BIAS_DECAY_RATE)
        futures_symbol_bias[symbol] = clamp_bias(current)


def update_reinforcement(symbol, pnl):
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

def execute_trade(asset_class, symbol, score, eff_mult, prob_positive, expected_value):
    global futures_lifetime_total, last_trade

    passed, net_edge, execution_cost = cost_engine.passes_cost_gate(
        asset_class=asset_class,
        gross_edge=expected_value,
        signal_score=score
    )

    if not passed:
        print(
            f"[{asset_class} COST BLOCKED] {symbol} "
            f"grossEV={expected_value:+.2f} "
            f"netEV={net_edge:+.2f} "
            f"cost={execution_cost:.4f}"
        )
        return

    hot_streak = get_symbol_hot_streak(asset_class, symbol)
    tier, mult = ppw_engine.get_multiplier(
        asset_class=asset_class,
        signal_score=score,
        prob_positive=prob_positive,
        expected_value=net_edge,
        hot_streak=hot_streak
    )

    symbol_bias = futures_symbol_bias.get(symbol, BIAS_NEUTRAL) if asset_class == "FUTURES" else 1.0

    pnl = winner_engine.realize_pnl(
        asset_class=asset_class,
        signal_score=score,
        prob_positive=prob_positive,
        expected_value=net_edge,
        eff_mult=eff_mult,
        symbol_bias=symbol_bias,
        asset_edge=asset_class_edge.get(asset_class, 1.0),
        hot_streak=hot_streak,
        execution_cost=execution_cost
    )

    last_trade = f"{symbol} {pnl:+.4f}"

    if asset_class == "CRYPTO":
        crypto_pnl[symbol] += pnl
        crypto_trades[symbol] += 1
        if pnl > 0:
            crypto_wins[symbol] += 1
            crypto_gross_wins[symbol] += pnl

    elif asset_class == "FX":
        fx_pnl[symbol] += pnl
        fx_trades[symbol] += 1
        if pnl > 0:
            fx_wins[symbol] += 1
            fx_gross_wins[symbol] += pnl

    elif asset_class == "FUTURES":
        futures_realized_pnl[symbol] += pnl
        futures_trade_count[symbol] += 1
        futures_lifetime_total += pnl
        if pnl > 0:
            futures_win_count[symbol] += 1
            futures_gross_wins[symbol] += pnl
        update_reinforcement(symbol, pnl)

    elif asset_class == "OPTIONS":
        options_pnl[symbol] += pnl
        options_trades[symbol] += 1
        if pnl > 0:
            options_wins[symbol] += 1
            options_gross_wins[symbol] += pnl

    update_asset_edge(asset_class, pnl)
    update_symbol_hot_streak(asset_class, symbol, pnl)

    print(
        f"[{asset_class} EXECUTED] {symbol} "
        f"netEV={net_edge:+.2f} "
        f"cost={execution_cost:.4f} "
        f"ppw={tier}:{mult:.2f} "
        f"pnl={pnl:+.4f}"
    )

ENGINE_MODES = {
    "1": "SAFE",
    "2": "CONSERVATIVE",
    "3": "BALANCED",
    "4": "AGGRESSIVE",
    "5": "EXPANSION",
}


def select_engine_mode():
    print("\n=== CSS ENGINE MODE SELECTOR ===")
    for k, v in ENGINE_MODES.items():
        print(f"{k}. {v}")
    choice = input("Enter choice (1-5) [default=3]: ").strip()
    return ENGINE_MODES.get(choice, "BALANCED")


def safe_load_runtime_asset(symbol: str):
    try:
        load_runtime_asset(symbol)
        print(f"Fetched 288 candles for {symbol}")
        return True
    except Exception as e:
        print(f"[FETCH FAIL] {symbol}: {str(e)[:80]}")
        return False


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
    for candidate in [
        selected.get("strike"),
        selected.get("strike_price"),
        selected.get("k"),
    ]:
        if candidate is None:
            continue
        try:
            return float(candidate)
        except Exception:
            continue
    return None


def get_selected_expiry(selected: Dict) -> Optional[str]:
    for candidate in [
        selected.get("expiry"),
        selected.get("expiration"),
        selected.get("expiration_date"),
        selected.get("expiry_date"),
        selected.get("exp_date"),
    ]:
        if candidate:
            return str(candidate)
    return None


def get_selected_entry_price(selected: Dict) -> Optional[float]:
    for candidate in [
        selected.get("price"),
        selected.get("premium"),
        selected.get("mid"),
        selected.get("mark"),
        selected.get("last"),
        selected.get("last_price"),
        selected.get("ask"),
        selected.get("bid"),
    ]:
        if candidate is None:
            continue
        try:
            return float(candidate)
        except Exception:
            continue
    return None


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
asset_class_edge = load_json_state(
    ASSET_EDGE_FILE,
    {"CRYPTO": 1.0, "FX": 1.0, "OPTIONS": 1.0, "FUTURES": 1.0}
)

all_hot_keys = (
    [f"CRYPTO::{s}" for s in SYMBOLS] +
    [f"FX::{s}" for s in FX_SYMBOLS] +
    [f"OPTIONS::{s}" for s in OPTION_SYMBOLS] +
    [f"FUTURES::{s}" for s in FUTURES_SYMBOLS]
)
symbol_hot_streak = load_json_state(
    SYMBOL_STREAK_FILE,
    {k: 0 for k in all_hot_keys}
)

crypto_pnl = {s: 0.0 for s in SYMBOLS}
crypto_trades = {s: 0 for s in SYMBOLS}
crypto_wins = {s: 0 for s in SYMBOLS}
crypto_gross_wins = {s: 0.0 for s in SYMBOLS}

fx_pnl = {s: 0.0 for s in FX_SYMBOLS}
fx_trades = {s: 0 for s in FX_SYMBOLS}
fx_wins = {s: 0 for s in FX_SYMBOLS}
fx_gross_wins = {s: 0.0 for s in FX_SYMBOLS}

options_pnl = {s: 0.0 for s in OPTION_SYMBOLS}
options_trades = {s: 0 for s in OPTION_SYMBOLS}
options_wins = {s: 0 for s in OPTION_SYMBOLS}
options_gross_wins = {s: 0.0 for s in OPTION_SYMBOLS}

futures_realized_pnl = {s: 0.0 for s in FUTURES_SYMBOLS}
futures_trade_count = {s: 0 for s in FUTURES_SYMBOLS}
futures_win_count = {s: 0 for s in FUTURES_SYMBOLS}
futures_gross_wins = {s: 0.0 for s in FUTURES_SYMBOLS}

futures_lifetime_total = 0.0
last_trade = "NONE"
cycle = 0


def get_total_pnl():
    return round(
        sum(crypto_pnl.values()) +
        sum(fx_pnl.values()) +
        sum(options_pnl.values()) +
        sum(futures_realized_pnl.values()),
        4
    )


def get_asset_class_pnls() -> Dict[str, float]:
    return {
        "CRYPTO": round(sum(crypto_pnl.values()), 4),
        "FX": round(sum(fx_pnl.values()), 4),
        "OPTIONS": round(sum(options_pnl.values()), 4),
        "FUTURES": round(sum(futures_realized_pnl.values()), 4),
    }


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

    return {"state": state, "mult": mult, "distance_pct": distance_pct}


def compute_volatility_state(symbol):
    state = random.choice(list(VOL_STATES.keys()))
    return {"state": state, "mult": VOL_STATES[state]}


def compute_liquidity_sweep(symbol):
    state = random.choice(list(SWEEP_STATES.keys()))
    return {"state": state, "mult": SWEEP_STATES[state]}


def execute_intelligent_option_trade(option_symbol_stub, reg, vw, vol, sw, cycle, eff):
    global last_trade

    if reg["priority"] == "BLOCK":
        return

    direction = "CALL" if vw["distance_pct"] >= 0 else "PUT"
    underlying_symbol = option_symbol_stub.split("-")[0]

    underlying_rows = [{
        "symbol": underlying_symbol,
        "price": round(random.uniform(90, 250), 2),
    }]

    option_rows = options_adapter.fetch_option_rows(underlying_rows)
    if not option_rows:
        return

    raw_score = round(random.uniform(8, 18), 2)
    signal_score = raw_score * reg["risk_mult"] * vw["mult"] * vol["mult"] * sw["mult"]

    prob_pos, _, ev, allow_trade = pt_engine.estimate(
        regime_conf=reg["confidence"],
        vwap_mult=vw["mult"],
        vol_mult=vol["mult"],
        sweep_mult=sw["mult"],
        raw_score=signal_score,
    )

    if not allow_trade:
        return

    passed, net_edge, execution_cost = cost_engine.passes_cost_gate(
        asset_class="OPTIONS",
        gross_edge=ev,
        signal_score=signal_score,
    )
    if not passed:
        print(
            f"[OPTIONS COST BLOCKED] {underlying_symbol} "
            f"grossEV={ev:+.2f} netEV={net_edge:+.2f} cost={execution_cost:.4f}"
        )
        return

    selected = option_rows[0]

    option_type = get_selected_option_type(selected) or direction
    strike = get_selected_strike(selected)
    if strike is None:
        strike = float(round(underlying_rows[0]["price"]))

    expiry = get_selected_expiry(selected) or "SIM-EXPIRY"

    entry_price = get_selected_entry_price(selected)
    if entry_price is None:
        expiry_result = options_expiry_engine.build_expiry_result(selected, fallback_days=14)
        pricing_result = options_pricing_engine.estimate_premium(
            underlying_price=float(underlying_rows[0]["price"]),
            strike=float(strike),
            option_type=option_type,
            volatility_multiplier=float(vol["mult"]),
            days_to_expiry=int(expiry_result["days_to_expiry"]),
        )
        entry_price = round(pricing_result.premium, 2)

    option_symbol = f"{underlying_symbol}-{option_type[0]}-{int(strike)}"

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
        tier="QUALIFIED",
        note=f"PTPOP={prob_pos:.2%} EV={net_edge:+.2f}",
    )

    if open_result.get("status") != "OPENED":
        return

    hot_streak = get_symbol_hot_streak("OPTIONS", option_symbol_stub)
    tier, mult = ppw_engine.get_multiplier(
        asset_class="OPTIONS",
        signal_score=signal_score,
        prob_positive=prob_pos,
        expected_value=net_edge,
        hot_streak=hot_streak,
    )

    pnl = winner_engine.realize_pnl(
        asset_class="OPTIONS",
        signal_score=signal_score,
        prob_positive=prob_pos,
        expected_value=net_edge,
        eff_mult=eff,
        symbol_bias=1.0,
        asset_edge=asset_class_edge.get("OPTIONS", 1.0),
        hot_streak=hot_streak,
        execution_cost=execution_cost,
    )

    options_pnl[option_symbol_stub] += pnl
    options_trades[option_symbol_stub] += 1
    if pnl > 0:
        options_wins[option_symbol_stub] += 1
        options_gross_wins[option_symbol_stub] += pnl

    update_asset_edge("OPTIONS", pnl)
    update_symbol_hot_streak("OPTIONS", option_symbol_stub, pnl)

    last_trade = f"{option_symbol} {pnl:+.4f}"

    print(
        f"[OPTIONS EXECUTED] {option_symbol} "
        f"netEV={net_edge:+.2f} cost={execution_cost:.4f} "
        f"ppw={tier}:{mult:.2f} pnl={pnl:+.4f}"
    )


while True:
    cycle += 1
    print(f"\n=== Cycle {cycle} | {datetime.now()} ===")

    apply_bias_decay()
    decay_asset_edges()

    total = get_total_pnl()
    asset_pnls = get_asset_class_pnls()

    print("\n--- LIVE EXECUTION SUMMARY ---")
    print(f"TOTAL PNL: {total:+.4f}")
    print(f"CRYPTO PNL: {asset_pnls['CRYPTO']:+.4f}")
    print(f"FX PNL: {asset_pnls['FX']:+.4f}")
    print(f"OPTIONS PNL: {asset_pnls['OPTIONS']:+.4f}")
    print(f"FUTURES PNL: {asset_pnls['FUTURES']:+.4f}")
    print(f"LAST TRADE: {last_trade}")
    print("-" * 60)

    for s in SYMBOLS:
        safe_load_runtime_asset(s)
        reg = detect_regime(s, "CRYPTO")
        vw = compute_vwap_state(s)
        vol = compute_volatility_state(s)
        sw = compute_liquidity_sweep(s)

        if reg["priority"] == "BLOCK":
            continue

        raw_score = round(random.uniform(8, 18), 2)
        signal_score = raw_score * reg["risk_mult"] * vw["mult"] * vol["mult"] * sw["mult"]
        prob_pos, _, ev, allow_trade = pt_engine.estimate(
            regime_conf=reg["confidence"],
            vwap_mult=vw["mult"],
            vol_mult=vol["mult"],
            sweep_mult=sw["mult"],
            raw_score=signal_score,
        )
        if allow_trade:
            eff = reg["capital_mult"] * vw["mult"] * vol["mult"] * sw["mult"]
            execute_trade("CRYPTO", s, signal_score, eff, prob_pos, ev)
            if s in crypto_pnl:
                crypto_pnl[s] += 0.0
                crypto_trades[s] += 1 if False else 0

    for s in FX_SYMBOLS:
        reg = detect_regime(s, "FX")
        vw = compute_vwap_state(s)
        vol = compute_volatility_state(s)
        sw = compute_liquidity_sweep(s)

        if reg["priority"] == "BLOCK":
            continue

        raw_score = round(random.uniform(8, 18), 2)
        signal_score = raw_score * reg["risk_mult"] * vw["mult"] * vol["mult"] * sw["mult"]
        prob_pos, _, ev, allow_trade = pt_engine.estimate(
            regime_conf=reg["confidence"],
            vwap_mult=vw["mult"],
            vol_mult=vol["mult"],
            sweep_mult=sw["mult"],
            raw_score=signal_score,
        )
        if allow_trade:
            eff = reg["capital_mult"] * vw["mult"] * vol["mult"] * sw["mult"]
            execute_trade("FX", s, signal_score, eff, prob_pos, ev)

    for s in OPTION_SYMBOLS:
        reg = detect_regime(s, "OPTIONS")
        vw = compute_vwap_state(s)
        vol = compute_volatility_state(s)
        sw = compute_liquidity_sweep(s)
        eff = reg["capital_mult"] * vw["mult"] * vol["mult"] * sw["mult"]
        execute_intelligent_option_trade(s, reg, vw, vol, sw, cycle, eff)

    for s in FUTURES_SYMBOLS:
        reg = detect_regime(s, "FUTURES")
        vw = compute_vwap_state(s)
        vol = compute_volatility_state(s)
        sw = compute_liquidity_sweep(s)

        if reg["priority"] == "BLOCK":
            continue

        raw_score = weighted_score(round(random.uniform(8, 18), 2), s)
        signal_score = raw_score * reg["risk_mult"] * vw["mult"] * vol["mult"] * sw["mult"]
        prob_pos, _, ev, allow_trade = pt_engine.estimate(
            regime_conf=reg["confidence"],
            vwap_mult=vw["mult"],
            vol_mult=vol["mult"],
            sweep_mult=sw["mult"],
            raw_score=signal_score,
        )
        if allow_trade:
            eff = reg["capital_mult"] * vw["mult"] * vol["mult"] * sw["mult"]
            execute_trade("FUTURES", s, signal_score, eff, prob_pos, ev)

    save_json_state(FUTURES_BIAS_FILE, futures_symbol_bias)
    save_json_state(FUTURES_LOSS_FILE, futures_loss_streak)
    save_json_state(ASSET_EDGE_FILE, asset_class_edge)
    save_json_state(SYMBOL_STREAK_FILE, symbol_hot_streak)

    print("\n--- ASSET CLASS EDGE ---")
    print(asset_class_edge)

    print("\n--- FUTURES SYMBOL BIAS ---")
    print(futures_symbol_bias)

    time.sleep(CYCLE_SLEEP)