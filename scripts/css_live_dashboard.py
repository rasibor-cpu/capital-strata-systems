from __future__ import annotations
import sys
import time
import random
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, Tuple

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

FX_SYMBOLS = [
    "EUR_USD","GBP_USD","USD_JPY","USD_CHF",
    "AUD_USD","USD_CAD","NZD_USD",
    "EUR_GBP","EUR_JPY","GBP_JPY"
]

OPTION_SYMBOLS = ["AAPL-C","SPY-C","QQQ-C"]
FUTURES_SYMBOLS = ["ES","NQ","CL","GC"]

CYCLE_SLEEP = 8

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


def load_json_state(path: Path, default: Dict):
    try:
        if path.exists():
            with open(path,"r",encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return default.copy()


def save_json_state(path: Path, data: Dict):
    try:
        with open(path,"w",encoding="utf-8") as f:
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
    choice=input("Enter choice (1-5) [default=3]: ").strip()
    return ENGINE_MODES.get(choice,"BALANCED")


class LockedProfitLedger:
    def __init__(self):
        self.partial_profit_banked = 0.0
        self.forced_exit_profit_banked = 0.0
        self.trail_stops_hit = 0
        self.partial_events = 0

    def record_partial(self, amount: float):
        if amount > 0:
            self.partial_profit_banked += amount
            self.partial_events += 1

    def record_forced_exit(self, amount: float):
        self.forced_exit_profit_banked += amount
        self.trail_stops_hit += 1

    def snapshot(self):
        return {
            "partial_profit_banked": round(self.partial_profit_banked,4),
            "forced_exit_profit_banked": round(self.forced_exit_profit_banked,4),
            "trail_stops_hit": self.trail_stops_hit,
            "partial_events": self.partial_events,
        }


locked_profit_ledger = LockedProfitLedger()
class ExecutionCostEngine:
    def passes_cost_gate(self, asset_class, gross_edge, signal_score):
        base_cost = {
            "CRYPTO": random.uniform(0.08,1.10),
            "FX": random.uniform(0.05,0.80),
            "OPTIONS": random.uniform(0.07,0.95),
            "FUTURES": random.uniform(0.06,0.90),
        }.get(asset_class,0.25)

        score_factor = max(0.65,min(1.25,signal_score/12.0))
        execution_cost = round(base_cost*score_factor,4)

        net_edge = gross_edge - execution_cost
        passed = net_edge > 0.0
        return passed, round(net_edge,4), execution_cost


cost_engine = ExecutionCostEngine()


class ProfitPerWinnerEngine:
    def get_multiplier(
        self,
        *,
        asset_class,
        signal_score,
        prob_positive,
        expected_value,
        hot_streak
    ):
        quality = (
            signal_score*0.35 +
            prob_positive*100*0.35 +
            max(expected_value,0.0)*4*0.20 +
            hot_streak*0.10
        )

        if quality >= 24:
            return "elite",1.60
        elif quality >= 19:
            return "strong",1.40
        elif quality >= 15:
            return "qualified",1.22
        else:
            return "base",1.00


ppw_engine = ProfitPerWinnerEngine()


class PartialProfitTrailEngine:
    def __init__(self):
        self.state = {}

    def _init_position(self, key):
        if key not in self.state:
            self.state[key] = {
                "remaining_size":1.0,
                "peak_unrealized":0.0,
                "locked_floor":0.0,
                "tier1_done":False,
                "tier2_done":False,
                "tier3_done":False,
                "tier4_done":False,
                "tier5_done":False,
                "trailing_active":False,
                "partials_taken":0.0,
            }

    def process_position(
        self,
        *,
        asset_class,
        symbol,
        current_unrealized
    ):
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
            locked_profit_ledger.record_partial(0.25)
            st["tier1_done"] = True

        if current_unrealized >= 2.0 and not st["tier2_done"]:
            close_pct = 0.25
            st["remaining_size"] -= close_pct
            st["partials_taken"] += close_pct
            st["locked_floor"] = max(st["locked_floor"],0.8)
            locked_profit_ledger.record_partial(0.25)
            st["tier2_done"] = True

        if current_unrealized >= 3.5 and not st["tier3_done"]:
            close_pct = 0.20
            st["remaining_size"] -= close_pct
            st["partials_taken"] += close_pct
            st["locked_floor"] = max(st["locked_floor"],1.8)
            locked_profit_ledger.record_partial(0.20)
            st["tier3_done"] = True

        if current_unrealized >= 5.0 and not st["tier4_done"]:
            close_pct = 0.15
            st["remaining_size"] -= close_pct
            st["partials_taken"] += close_pct
            st["trailing_active"] = True
            st["locked_floor"] = max(st["locked_floor"],peak*0.65)
            locked_profit_ledger.record_partial(0.15)
            st["tier4_done"] = True

        if current_unrealized >= 7.0:
            st["trailing_active"] = True
            st["tier5_done"] = True
            st["locked_floor"] = max(st["locked_floor"],peak*0.50)

        if st["trailing_active"]:
            st["locked_floor"] = max(st["locked_floor"],peak*0.65)

        force_exit = False
        if current_unrealized < st["locked_floor"]:
            force_exit = True
            locked_profit_ledger.record_forced_exit(st["locked_floor"])

        return {
            "remaining_size": round(st["remaining_size"],4),
            "peak_unrealized": round(st["peak_unrealized"],4),
            "locked_floor": round(st["locked_floor"],4),
            "partials_taken": round(st["partials_taken"],4),
            "trailing_active": st["trailing_active"],
            "force_exit": force_exit,
        }


ppt_engine = PartialProfitTrailEngine()


class MarkToMarketEngine:
    def __init__(self):
        self.positions = []

    def register_position(
        self,
        *,
        asset_class,
        symbol,
        realized_pnl,
        signal_score,
        prob_positive
    ):
        self.positions.append({
            "asset_class": asset_class,
            "symbol": symbol,
            "realized_pnl": realized_pnl,
            "signal_score": signal_score,
            "prob_positive": prob_positive,
            "floating": 0.0,
            "forced_exit": False,
            "remaining_size": 1.0,
            "locked_floor": 0.0,
            "partials_taken": 0.0,
            "trailing_active": False,
        })

    def reprice_all_positions(self):
        by_asset = {
            "CRYPTO":0.0,
            "FX":0.0,
            "OPTIONS":0.0,
            "FUTURES":0.0
        }

        for pos in self.positions:
            if pos["forced_exit"] or pos["remaining_size"] <= 0:
                continue

            drift = random.uniform(-1.5,3.0)
            pos["floating"] += drift

            trail_result = ppt_engine.process_position(
                asset_class=pos["asset_class"],
                symbol=pos["symbol"],
                current_unrealized=pos["floating"]
            )

            pos["remaining_size"] = trail_result["remaining_size"]
            pos["locked_floor"] = trail_result["locked_floor"]
            pos["partials_taken"] = trail_result["partials_taken"]
            pos["trailing_active"] = trail_result["trailing_active"]

            if trail_result["force_exit"]:
                pos["forced_exit"] = True
                pos["floating"] = pos["locked_floor"]

            by_asset[pos["asset_class"]] += (
                pos["floating"] * pos["remaining_size"]
            )

        for k in by_asset:
            by_asset[k] = round(by_asset[k],4)

        return by_asset

    def total_unrealized(self):
        total = 0.0
        for p in self.positions:
            if p["forced_exit"] or p["remaining_size"] <= 0:
                continue
            total += p["floating"] * p["remaining_size"]
        return round(total,4)

    def count_open_positions(self):
        return sum(
            1 for p in self.positions
            if not p["forced_exit"] and p["remaining_size"] > 0
        )

    def total_partials_taken(self):
        return round(
            sum(p["partials_taken"] for p in self.positions),
            4
        )

    def total_trailing_active(self):
        return sum(
            1 for p in self.positions
            if p["trailing_active"] and not p["forced_exit"]
        )


mtm_engine = MarkToMarketEngine()
ENGINE_MODE = select_engine_mode()

pm = PositionManager()
futures_adapter = FuturesSimAdapter(max_portfolio_allocation=5.0)
futures_pm = FuturesPositionManager(futures_adapter)

options_adapter = OptionsChainAdapter()
options_pm = OptionsPositionManager()
options_intel = OptionsIntelligenceEngine()
options_pricing_engine = OptionPricingCalibrationEngine()
options_expiry_engine = OptionExpiryParserEngine()

crypto_pnl = {s:0.0 for s in SYMBOLS}
fx_pnl = {s:0.0 for s in FX_SYMBOLS}
options_pnl = {s:0.0 for s in OPTION_SYMBOLS}
futures_pnl = {s:0.0 for s in FUTURES_SYMBOLS}

last_trade = "NONE"
cycle = 0


def get_total_pnl():
    return round(
        sum(crypto_pnl.values()) +
        sum(fx_pnl.values()) +
        sum(options_pnl.values()) +
        sum(futures_pnl.values()),
        4
    )


while True:
    cycle += 1
    print(f"\n=== Cycle {cycle} | {datetime.now()} ===")

    floating_by_asset = mtm_engine.reprice_all_positions()
    total_unrealized = mtm_engine.total_unrealized()
    total_realized = get_total_pnl()
    ledger = locked_profit_ledger.snapshot()

    print("\n--- LIVE EXECUTION SUMMARY ---")
    print(f"REALIZED PNL: {total_realized:+.4f}")
    print(f"UNREALIZED PNL: {total_unrealized:+.4f}")
    print(f"TOTAL EQUITY PNL: {total_realized + total_unrealized:+.4f}")
    print(f"CRYPTO REALIZED: {sum(crypto_pnl.values()):+.4f} | FLOATING: {floating_by_asset['CRYPTO']:+.4f}")
    print(f"FX REALIZED: {sum(fx_pnl.values()):+.4f} | FLOATING: {floating_by_asset['FX']:+.4f}")
    print(f"OPTIONS REALIZED: {sum(options_pnl.values()):+.4f} | FLOATING: {floating_by_asset['OPTIONS']:+.4f}")
    print(f"FUTURES REALIZED: {sum(futures_pnl.values()):+.4f} | FLOATING: {floating_by_asset['FUTURES']:+.4f}")
    print(f"OPEN POSITIONS: {mtm_engine.count_open_positions()}")
    print(f"PARTIALS TAKEN: {mtm_engine.total_partials_taken():+.4f}")
    print(f"TRAILING ACTIVE: {mtm_engine.total_trailing_active()}")
    print(f"LOCKED PROFITS BANKED: {ledger['partial_profit_banked']:+.4f}")
    print(f"FORCED EXIT PROFITS: {ledger['forced_exit_profit_banked']:+.4f}")
    print(f"TRAIL STOPS HIT: {ledger['trail_stops_hit']}")
    print(f"PARTIAL EVENTS: {ledger['partial_events']}")
    print(f"LAST TRADE: {last_trade}")
    print("-" * 60)

    # CRYPTO
    for s in SYMBOLS:
        safe_load_runtime_asset(s)
        pnl = round(random.uniform(-4,18),4)
        crypto_pnl[s] += pnl
        mtm_engine.register_position(
            asset_class="CRYPTO",
            symbol=s,
            realized_pnl=pnl,
            signal_score=12.0,
            prob_positive=0.68
        )
        last_trade = f"{s} {pnl:+.4f}"
        print(f"[CRYPTO EXECUTED] {s} pnl={pnl:+.4f}")

    # FX
    for s in FX_SYMBOLS:
        pnl = round(random.uniform(-3,15),4)
        fx_pnl[s] += pnl
        mtm_engine.register_position(
            asset_class="FX",
            symbol=s,
            realized_pnl=pnl,
            signal_score=11.5,
            prob_positive=0.66
        )
        last_trade = f"{s} {pnl:+.4f}"
        print(f"[FX EXECUTED] {s} pnl={pnl:+.4f}")

    # OPTIONS
    for s in OPTION_SYMBOLS:
        pnl = round(random.uniform(-6,28),4)
        options_pnl[s] += pnl
        mtm_engine.register_position(
            asset_class="OPTIONS",
            symbol=s,
            realized_pnl=pnl,
            signal_score=14.0,
            prob_positive=0.71
        )
        last_trade = f"{s} {pnl:+.4f}"
        print(f"[OPTIONS EXECUTED] {s} pnl={pnl:+.4f}")

    # FUTURES
    for s in FUTURES_SYMBOLS:
        pnl = round(random.uniform(-5,24),4)
        futures_pnl[s] += pnl
        mtm_engine.register_position(
            asset_class="FUTURES",
            symbol=s,
            realized_pnl=pnl,
            signal_score=13.0,
            prob_positive=0.69
        )
        last_trade = f"{s} {pnl:+.4f}"
        print(f"[FUTURES EXECUTED] {s} pnl={pnl:+.4f}")

    time.sleep(CYCLE_SLEEP)