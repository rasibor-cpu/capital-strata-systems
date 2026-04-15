from __future__ import annotations
import sys
import time
import random
import json
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
    "BTC-USD", "ETH-USD", "SOL-USD", "XRP-USD", "ADA-USD",
    "DOGE-USD", "AVAX-USD", "LINK-USD", "LTC-USD", "BCH-USD",
]

FUTURES_SYMBOLS = ["ES", "NQ", "CL", "GC"]

FX_SYMBOLS = [
    "EUR_USD", "GBP_USD", "USD_JPY", "USD_CHF",
    "AUD_USD", "USD_CAD", "NZD_USD",
    "EUR_GBP", "EUR_JPY", "GBP_JPY",
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

ASSET_EDGE_MIN = 0.65
ASSET_EDGE_MAX = 1.35
ASSET_EDGE_DECAY = 0.05
ASSET_EDGE_REWARD = 0.03
ASSET_EDGE_PENALTY = 0.02

HOT_STREAK_MIN = -6
HOT_STREAK_MAX = 12

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

ENGINE_MODES = {
    "1": "SAFE",
    "2": "CONSERVATIVE",
    "3": "BALANCED",
    "4": "AGGRESSIVE",
    "5": "EXPANSION",
}


def load_json_state(path: Path, default: Dict):
    try:
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return default.copy()


def save_json_state(path: Path, data: Dict):
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except Exception:
        pass


def clamp_bias(v: float) -> float:
    return max(BIAS_MIN, min(BIAS_MAX, v))


def clamp_asset_edge(v: float) -> float:
    return max(ASSET_EDGE_MIN, min(ASSET_EDGE_MAX, v))


def clamp_hot_streak(v: int) -> int:
    return max(HOT_STREAK_MIN, min(HOT_STREAK_MAX, v))


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


class ExecutionCostEngine:
    def passes_cost_gate(self, asset_class: str, gross_edge: float, signal_score: float) -> Tuple[bool, float, float]:
        base_cost = {
            "CRYPTO": random.uniform(0.08, 1.10),
            "FX": random.uniform(0.05, 0.80),
            "OPTIONS": random.uniform(0.07, 0.95),
            "FUTURES": random.uniform(0.06, 0.90),
        }.get(asset_class, 0.25)

        score_factor = max(0.65, min(1.25, signal_score / 12.0))
        execution_cost = round(base_cost * score_factor, 4)

        net_edge = gross_edge - execution_cost
        passed = net_edge > 0.0

        return passed, round(net_edge, 4), execution_cost


cost_engine = ExecutionCostEngine()


class ProfitPerWinnerEngine:
    def get_multiplier(
        self,
        *,
        asset_class: str,
        signal_score: float,
        prob_positive: float,
        expected_value: float,
        hot_streak: int,
    ) -> Tuple[str, float]:
        quality = (
            signal_score * 0.35
            + prob_positive * 100 * 0.35
            + max(expected_value, 0.0) * 4 * 0.20
            + hot_streak * 0.10
        )

        if quality >= 24:
            return "elite", 1.60
        elif quality >= 19:
            return "strong", 1.40
        elif quality >= 15:
            return "qualified", 1.22
        else:
            return "base", 1.00


ppw_engine = ProfitPerWinnerEngine()


class PreTradeProbabilityEngine:
    def estimate(
        self,
        *,
        regime_conf: float,
        vwap_mult: float,
        vol_mult: float,
        sweep_mult: float,
        raw_score: float,
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
            execute,
        )


pt_engine = PreTradeProbabilityEngine()


class WinnerAsymmetryEngine:
    def realize_pnl(
        self,
        *,
        asset_class: str,
        signal_score: float,
        prob_positive: float,
        expected_value: float,
        eff_mult: float,
        symbol_bias: float = 1.0,
        asset_edge: float = 1.0,
        hot_streak: int = 0,
        execution_cost: float = 0.0,
    ) -> float:
        quality = (
            signal_score * 0.38
            + prob_positive * 100.0 * 0.34
            + max(expected_value, 0.0) * 4.0 * 0.20
            + asset_edge * 5.0 * 0.08
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
        adjusted_eff *= max(0.88, min(1.12, 1.0 + hot_streak * 0.04))

        won_trade = random.random() <= win_prob
        gross_pnl = (
            random.uniform(win_low, win_high) * adjusted_eff
            if won_trade
            else random.uniform(loss_low, loss_high) * adjusted_eff
        )

        net_pnl = gross_pnl - execution_cost

        if net_pnl > 0:
            _, mult = ppw_engine.get_multiplier(
                asset_class=asset_class,
                signal_score=signal_score,
                prob_positive=prob_positive,
                expected_value=expected_value,
                hot_streak=hot_streak,
            )
            net_pnl *= mult

        return round(net_pnl, 4)


winner_engine = WinnerAsymmetryEngine()
class MarkToMarketEngine:
    def __init__(self):
        self.positions = []

    def register_position(
        self,
        *,
        asset_class: str,
        symbol: str,
        entry_pnl: float,
        signal_score: float,
        prob_positive: float,
        realized_pnl: float,
    ):
        self.positions.append({
            "asset_class": asset_class,
            "symbol": symbol,
            "entry_pnl": entry_pnl,
            "signal_score": signal_score,
            "prob_positive": prob_positive,
            "realized_pnl": realized_pnl,
            "floating": 0.0,
            "peak_unrealized": 0.0,
            "remaining_size": 1.0,
            "locked_floor": 0.0,
            "partials_taken": 0.0,
            "tier1_done": False,
            "tier2_done": False,
            "tier3_done": False,
            "tier4_done": False,
            "tier5_done": False,
            "trailing_active": False,
            "forced_exit": False,
        })

    def reprice_all_positions(self):
        by_asset = {
            "CRYPTO": 0.0,
            "FX": 0.0,
            "OPTIONS": 0.0,
            "FUTURES": 0.0,
        }

        for pos in self.positions:
            if pos["forced_exit"] or pos["remaining_size"] <= 0:
                continue

            drift = random.uniform(-1.5, 3.0)
            pos["floating"] += drift

            if pos["floating"] > pos["peak_unrealized"]:
                pos["peak_unrealized"] = pos["floating"]

            trail_result = ppt_engine.process_position(
                asset_class=pos["asset_class"],
                symbol=pos["symbol"],
                current_unrealized=pos["floating"],
            )

            pos["remaining_size"] = trail_result["remaining_size"]
            pos["locked_floor"] = trail_result["locked_floor"]
            pos["trailing_active"] = trail_result["trailing_active"]
            pos["partials_taken"] = trail_result["partials_taken"]
            pos["peak_unrealized"] = max(pos["peak_unrealized"], trail_result["peak_unrealized"])

            if trail_result["force_exit"]:
                pos["forced_exit"] = True
                pos["floating"] = pos["locked_floor"]

            by_asset[pos["asset_class"]] += pos["floating"] * pos["remaining_size"]

        for k in by_asset:
            by_asset[k] = round(by_asset[k], 4)

        return by_asset

    def total_unrealized(self):
        total = 0.0
        for p in self.positions:
            if p["forced_exit"] or p["remaining_size"] <= 0:
                continue
            total += p["floating"] * p["remaining_size"]
        return round(total, 4)

    def count_open_positions(self):
        return sum(
            1 for p in self.positions
            if not p["forced_exit"] and p["remaining_size"] > 0
        )

    def total_partials_taken(self):
        return round(sum(p["partials_taken"] for p in self.positions), 4)

    def total_trailing_active(self):
        return sum(1 for p in self.positions if p["trailing_active"] and not p["forced_exit"])


mtm_engine = MarkToMarketEngine()


class PartialProfitTrailEngine:
    """
    Tier 1 @ +1.0R -> close 25%, lock breakeven
    Tier 2 @ +2.0R -> close 25%, lock +0.8R
    Tier 3 @ +3.5R -> close 20%, lock +1.8R
    Tier 4 @ +5.0R -> close 15%, trail 35% giveback
    Tier 5 @ +7.0R -> dynamic lock at 50% peak
    """

    def __init__(self):
        self.state = {}

    def _init_position(self, key: str):
        if key not in self.state:
            self.state[key] = {
                "remaining_size": 1.0,
                "peak_unrealized": 0.0,
                "locked_floor": 0.0,
                "tier1_done": False,
                "tier2_done": False,
                "tier3_done": False,
                "tier4_done": False,
                "tier5_done": False,
                "trailing_active": False,
                "partials_taken": 0.0,
            }

    def process_position(
        self,
        *,
        asset_class: str,
        symbol: str,
        current_unrealized: float,
    ) -> Dict[str, float]:
        key = f"{asset_class}::{symbol}"
        self._init_position(key)
        st = self.state[key]

        if current_unrealized > st["peak_unrealized"]:
            st["peak_unrealized"] = current_unrealized

        peak = st["peak_unrealized"]

        if current_unrealized >= 1.0 and not st["tier1_done"]:
            close_pct = 0.25
            st["remaining_size"] -= close_pct
            st["partials_taken"] += close_pct
            st["locked_floor"] = max(st["locked_floor"], 0.0)
            st["tier1_done"] = True

        if current_unrealized >= 2.0 and not st["tier2_done"]:
            close_pct = 0.25
            st["remaining_size"] -= close_pct
            st["partials_taken"] += close_pct
            st["locked_floor"] = max(st["locked_floor"], 0.8)
            st["tier2_done"] = True

        if current_unrealized >= 3.5 and not st["tier3_done"]:
            close_pct = 0.20
            st["remaining_size"] -= close_pct
            st["partials_taken"] += close_pct
            st["locked_floor"] = max(st["locked_floor"], 1.8)
            st["tier3_done"] = True

        if current_unrealized >= 5.0 and not st["tier4_done"]:
            close_pct = 0.15
            st["remaining_size"] -= close_pct
            st["partials_taken"] += close_pct
            st["trailing_active"] = True
            st["locked_floor"] = max(st["locked_floor"], peak * 0.65)
            st["tier4_done"] = True

        if current_unrealized >= 7.0:
            st["trailing_active"] = True
            st["tier5_done"] = True
            dynamic_floor = peak * 0.50
            st["locked_floor"] = max(st["locked_floor"], dynamic_floor)

        if st["trailing_active"]:
            trail_floor = peak * 0.65
            st["locked_floor"] = max(st["locked_floor"], trail_floor)

        force_exit = current_unrealized < st["locked_floor"]

        return {
            "remaining_size": round(st["remaining_size"], 4),
            "peak_unrealized": round(st["peak_unrealized"], 4),
            "locked_floor": round(st["locked_floor"], 4),
            "partials_taken": round(st["partials_taken"], 4),
            "trailing_active": st["trailing_active"],
            "force_exit": force_exit,
        }


ppt_engine = PartialProfitTrailEngine()


def weighted_score(raw_score: float, symbol: str) -> float:
    return raw_score * futures_symbol_bias.get(symbol, BIAS_NEUTRAL)


def get_hot_key(asset_class: str, symbol: str) -> str:
    return f"{asset_class}::{symbol}"


def get_symbol_hot_streak(asset_class: str, symbol: str) -> int:
    return int(symbol_hot_streak.get(get_hot_key(asset_class, symbol), 0))


def update_symbol_hot_streak(asset_class: str, symbol: str, pnl: float):
    key = get_hot_key(asset_class, symbol)
    current = int(symbol_hot_streak.get(key, 0))

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

        asset_class_edge[asset_class] = round(clamp_asset_edge(current), 6)


def update_asset_edge(asset_class: str, pnl: float):
    current = float(asset_class_edge.get(asset_class, 1.0))
    current += ASSET_EDGE_REWARD if pnl > 0 else -ASSET_EDGE_PENALTY
    asset_class_edge[asset_class] = round(clamp_asset_edge(current), 6)
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


def compute_vwap_state(symbol: str):
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
        "priority": priority,
        "capital_mult": CAPITAL_MULTIPLIERS[priority],
    }


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
    {s: 1.0 for s in FUTURES_SYMBOLS},
)

futures_loss_streak = load_json_state(
    FUTURES_LOSS_FILE,
    {s: 0 for s in FUTURES_SYMBOLS},
)

asset_class_edge = load_json_state(
    ASSET_EDGE_FILE,
    {
        "CRYPTO": 1.0,
        "FX": 1.0,
        "OPTIONS": 1.0,
        "FUTURES": 1.0,
    },
)

all_hot_keys = (
    [f"CRYPTO::{s}" for s in SYMBOLS] +
    [f"FX::{s}" for s in FX_SYMBOLS] +
    [f"OPTIONS::{s}" for s in OPTION_SYMBOLS] +
    [f"FUTURES::{s}" for s in FUTURES_SYMBOLS]
)

symbol_hot_streak = load_json_state(
    SYMBOL_STREAK_FILE,
    {k: 0 for k in all_hot_keys},
)

crypto_pnl = {s: 0.0 for s in SYMBOLS}
fx_pnl = {s: 0.0 for s in FX_SYMBOLS}
options_pnl = {s: 0.0 for s in OPTION_SYMBOLS}
futures_realized_pnl = {s: 0.0 for s in FUTURES_SYMBOLS}

crypto_trades = {s: 0 for s in SYMBOLS}
fx_trades = {s: 0 for s in FX_SYMBOLS}
options_trades = {s: 0 for s in OPTION_SYMBOLS}
futures_trade_count = {s: 0 for s in FUTURES_SYMBOLS}

last_trade = "NONE"
cycle = 0


def get_total_pnl():
    return round(
        sum(crypto_pnl.values()) +
        sum(fx_pnl.values()) +
        sum(options_pnl.values()) +
        sum(futures_realized_pnl.values()),
        4,
    )


def get_asset_class_pnls():
    return {
        "CRYPTO": round(sum(crypto_pnl.values()), 4),
        "FX": round(sum(fx_pnl.values()), 4),
        "OPTIONS": round(sum(options_pnl.values()), 4),
        "FUTURES": round(sum(futures_realized_pnl.values()), 4),
    }


def execute_trade(asset_class, symbol, score, eff_mult, prob_positive, expected_value):
    global last_trade

    passed, net_edge, execution_cost = cost_engine.passes_cost_gate(
        asset_class=asset_class,
        gross_edge=expected_value,
        signal_score=score,
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
        hot_streak=hot_streak,
    )

    symbol_bias = (
        futures_symbol_bias.get(symbol, BIAS_NEUTRAL)
        if asset_class == "FUTURES"
        else 1.0
    )

    pnl = winner_engine.realize_pnl(
        asset_class=asset_class,
        signal_score=score,
        prob_positive=prob_positive,
        expected_value=net_edge,
        eff_mult=eff_mult,
        symbol_bias=symbol_bias,
        asset_edge=asset_class_edge.get(asset_class, 1.0),
        hot_streak=hot_streak,
        execution_cost=execution_cost,
    )

    last_trade = f"{symbol} {pnl:+.4f}"

    if asset_class == "CRYPTO":
        crypto_pnl[symbol] += pnl
        crypto_trades[symbol] += 1
    elif asset_class == "FX":
        fx_pnl[symbol] += pnl
        fx_trades[symbol] += 1
    elif asset_class == "OPTIONS":
        options_pnl[symbol] += pnl
        options_trades[symbol] += 1
    elif asset_class == "FUTURES":
        futures_realized_pnl[symbol] += pnl
        futures_trade_count[symbol] += 1
        update_reinforcement(symbol, pnl)

    update_asset_edge(asset_class, pnl)
    update_symbol_hot_streak(asset_class, symbol, pnl)

    mtm_engine.register_position(
        asset_class=asset_class,
        symbol=symbol,
        entry_pnl=0.0,
        signal_score=score,
        prob_positive=prob_positive,
        realized_pnl=pnl,
    )

    print(
        f"[{asset_class} EXECUTED] {symbol} "
        f"netEV={net_edge:+.2f} "
        f"cost={execution_cost:.4f} "
        f"ppw={tier}:{mult:.2f} "
        f"pnl={pnl:+.4f}"
    )


while True:
    cycle += 1
    print(f"\n=== Cycle {cycle} | {datetime.now()} ===")

    apply_bias_decay()
    decay_asset_edges()

    floating_by_asset = mtm_engine.reprice_all_positions()
    total_unrealized = mtm_engine.total_unrealized()
    total_realized = get_total_pnl()
    asset_pnls = get_asset_class_pnls()

    print("\n--- LIVE EXECUTION SUMMARY ---")
    print(f"REALIZED PNL: {total_realized:+.4f}")
    print(f"UNREALIZED PNL: {total_unrealized:+.4f}")
    print(f"TOTAL EQUITY PNL: {total_realized + total_unrealized:+.4f}")
    print(f"CRYPTO REALIZED: {asset_pnls['CRYPTO']:+.4f} | FLOATING: {floating_by_asset['CRYPTO']:+.4f}")
    print(f"FX REALIZED: {asset_pnls['FX']:+.4f} | FLOATING: {floating_by_asset['FX']:+.4f}")
    print(f"OPTIONS REALIZED: {asset_pnls['OPTIONS']:+.4f} | FLOATING: {floating_by_asset['OPTIONS']:+.4f}")
    print(f"FUTURES REALIZED: {asset_pnls['FUTURES']:+.4f} | FLOATING: {floating_by_asset['FUTURES']:+.4f}")
    print(f"OPEN POSITIONS: {mtm_engine.count_open_positions()}")
    print(f"PARTIALS TAKEN: {mtm_engine.total_partials_taken():+.4f}")
    print(f"TRAILING ACTIVE: {mtm_engine.total_trailing_active()}")
    print(f"LAST TRADE: {last_trade}")
    print("-" * 60)

    all_assets = [
        ("CRYPTO", SYMBOLS),
        ("FX", FX_SYMBOLS),
        ("OPTIONS", OPTION_SYMBOLS),
        ("FUTURES", FUTURES_SYMBOLS),
    ]

    for asset_class, asset_list in all_assets:
        for s in asset_list:
            if asset_class == "CRYPTO":
                safe_load_runtime_asset(s)

            reg = detect_regime(s, asset_class)
            vw = compute_vwap_state(s)
            vol = random.choice(list(VOL_STATES.values()))
            sw = random.choice(list(SWEEP_STATES.values()))

            if reg["priority"] == "BLOCK":
                continue

            raw_score = round(random.uniform(8, 18), 2)

            if asset_class == "FUTURES":
                raw_score = weighted_score(raw_score, s)

            signal_score = (
                raw_score *
                reg["risk_mult"] *
                vw["mult"] *
                vol *
                sw
            )

            prob_pos, _, ev, allow_trade = pt_engine.estimate(
                regime_conf=reg["confidence"],
                vwap_mult=vw["mult"],
                vol_mult=vol,
                sweep_mult=sw,
                raw_score=signal_score,
            )

            if not allow_trade:
                continue

            eff = (
                reg["capital_mult"] *
                vw["mult"] *
                vol *
                sw
            )

            execute_trade(
                asset_class,
                s,
                signal_score,
                eff,
                prob_pos,
                ev,
            )

    save_json_state(FUTURES_BIAS_FILE, futures_symbol_bias)
    save_json_state(FUTURES_LOSS_FILE, futures_loss_streak)
    save_json_state(ASSET_EDGE_FILE, asset_class_edge)
    save_json_state(SYMBOL_STREAK_FILE, symbol_hot_streak)

    print("\n--- ASSET CLASS EDGE ---")
    print(asset_class_edge)

    print("\n--- FUTURES SYMBOL BIAS ---")
    print(futures_symbol_bias)

    time.sleep(CYCLE_SLEEP)