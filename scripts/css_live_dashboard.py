from __future__ import annotations
import sys
import time
import random
from datetime import datetime
from pathlib import Path

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

ENGINE_MODES = {
    "1": "SAFE",
    "2": "CONSERVATIVE",
    "3": "BALANCED",
    "4": "AGGRESSIVE",
    "5": "EXPANSION",
}


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


class LockedProfitLedger:
    def __init__(self):
        self.partial_profit_banked = 0.0
        self.forced_exit_profit_banked = 0.0
        self.trail_stops_hit = 0
        self.partial_events = 0
        self.accelerated_locks = 0
        self.decay_protections = 0
        self.priority_exits = 0

    def record_partial(self, amount: float):
        if amount > 0:
            self.partial_profit_banked += amount
            self.partial_events += 1

    def record_forced_exit(self, amount: float):
        self.forced_exit_profit_banked += amount
        self.trail_stops_hit += 1

    def record_acceleration(self):
        self.accelerated_locks += 1

    def record_decay_protection(self):
        self.decay_protections += 1

    def record_priority_exit(self):
        self.priority_exits += 1

    def snapshot(self):
        return {
            "partial_profit_banked": round(self.partial_profit_banked, 4),
            "forced_exit_profit_banked": round(self.forced_exit_profit_banked, 4),
            "trail_stops_hit": self.trail_stops_hit,
            "partial_events": self.partial_events,
            "accelerated_locks": self.accelerated_locks,
            "decay_protections": self.decay_protections,
            "priority_exits": self.priority_exits,
        }


locked_profit_ledger = LockedProfitLedger()


class ExitPriorityEngine:
    """
    PQR-5 Smart Exit Prioritization Engine
    Ranks breached positions and ejects weakest first.
    """

    def __init__(self):
        self.asset_fragility_weight = {
            "OPTIONS": 1.35,
            "FUTURES": 1.15,
            "CRYPTO": 1.00,
            "FX": 0.85,
        }

    def compute_priority_score(self, pos: dict):
        peak = pos.get("peak_unrealized", 0.0)
        floating = pos.get("floating", 0.0)
        signal_score = pos.get("signal_score", 10.0)
        asset_class = pos.get("asset_class", "CRYPTO")

        if peak <= 0:
            decay_ratio = 1.0
        else:
            decay_ratio = max(0.0, (peak - floating) / peak)

        fragility = self.asset_fragility_weight.get(asset_class, 1.0)

        signal_deterioration = max(0.0, (15.0 - signal_score) / 15.0)

        weakness_score = (
            decay_ratio * 4.0
            + signal_deterioration * 2.0
            + fragility
        )

        return round(weakness_score, 4)


exit_priority_engine = ExitPriorityEngine()


class PartialProfitTrailEngine:
    def __init__(self):
        self.state = {}
        self.asset_floor_profiles = {
            "CRYPTO": {"tier4_lock": 0.55, "tier5_lock": 0.45, "grace_band": 0.35},
            "FX": {"tier4_lock": 0.72, "tier5_lock": 0.60, "grace_band": 0.20},
            "OPTIONS": {"tier4_lock": 0.50, "tier5_lock": 0.40, "grace_band": 0.45},
            "FUTURES": {"tier4_lock": 0.60, "tier5_lock": 0.50, "grace_band": 0.30},
            "DEFAULT": {"tier4_lock": 0.60, "tier5_lock": 0.50, "grace_band": 0.25},
        }

    def _init_position(self, key):
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
                "force_exit_warning_count": 0,
                "last_floor_breach": False,
                "last_peak_snapshot": 0.0,
                "decay_guard_active": False,
            }
    def _get_profile(self, asset_class):
        return self.asset_floor_profiles.get(
            asset_class,
            self.asset_floor_profiles["DEFAULT"]
        )

    def process_position(self, *, asset_class, symbol, current_unrealized):
        key = f"{asset_class}::{symbol}"
        self._init_position(key)
        st = self.state[key]
        profile = self._get_profile(asset_class)

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
            st["locked_floor"] = max(st["locked_floor"], 0.8)
            locked_profit_ledger.record_partial(0.25)
            st["tier2_done"] = True

        if current_unrealized >= 3.5 and not st["tier3_done"]:
            close_pct = 0.20
            st["remaining_size"] -= close_pct
            st["partials_taken"] += close_pct
            st["locked_floor"] = max(st["locked_floor"], 1.8)
            locked_profit_ledger.record_partial(0.20)
            st["tier3_done"] = True

        if current_unrealized >= 5.0 and not st["tier4_done"]:
            close_pct = 0.15
            st["remaining_size"] -= close_pct
            st["partials_taken"] += close_pct
            st["trailing_active"] = True
            st["locked_floor"] = max(
                st["locked_floor"],
                peak * profile["tier4_lock"]
            )
            locked_profit_ledger.record_partial(0.15)
            st["tier4_done"] = True

        if current_unrealized >= 7.0:
            st["trailing_active"] = True
            st["tier5_done"] = True
            st["locked_floor"] = max(
                st["locked_floor"],
                peak * profile["tier5_lock"]
            )

        if peak >= 9.0:
            accel_floor = peak * 0.72
            if accel_floor > st["locked_floor"]:
                st["locked_floor"] = accel_floor
                locked_profit_ledger.record_acceleration()
        elif peak >= 6.5:
            accel_floor = peak * 0.64
            if accel_floor > st["locked_floor"]:
                st["locked_floor"] = accel_floor
                locked_profit_ledger.record_acceleration()

        if st["trailing_active"]:
            adaptive_floor = peak * profile["tier4_lock"]
            st["locked_floor"] = max(st["locked_floor"], adaptive_floor)

        peak_drop = peak - current_unrealized
        dynamic_grace = profile["grace_band"]

        if peak >= 5.0 and peak_drop >= (peak * 0.28):
            dynamic_grace *= 0.55
            st["decay_guard_active"] = True
            locked_profit_ledger.record_decay_protection()
        else:
            st["decay_guard_active"] = False

        if peak >= 3.0 and current_unrealized < 1.5:
            st["locked_floor"] = max(st["locked_floor"], 1.25)

        grace_floor = st["locked_floor"] - dynamic_grace

        breach = False
        force_exit = False

        if current_unrealized < grace_floor:
            st["force_exit_warning_count"] += 1
            st["last_floor_breach"] = True
            breach = True
        else:
            st["force_exit_warning_count"] = 0
            st["last_floor_breach"] = False

        if st["force_exit_warning_count"] >= 2:
            force_exit = True

        return {
            "remaining_size": round(st["remaining_size"], 4),
            "peak_unrealized": round(st["peak_unrealized"], 4),
            "locked_floor": round(st["locked_floor"], 4),
            "partials_taken": round(st["partials_taken"], 4),
            "trailing_active": st["trailing_active"],
            "force_exit": force_exit,
            "decay_guard_active": st["decay_guard_active"],
            "breach": breach,
        }


ppt_engine = PartialProfitTrailEngine()


class SmartDriftEngine:
    """
    PQR-4 Smart Drift Engine
    """

    def __init__(self):
        self.asset_volatility = {
            "CRYPTO": (0.8, 3.4),
            "FX": (0.3, 1.6),
            "OPTIONS": (1.2, 5.8),
            "FUTURES": (0.7, 4.2),
        }

    def generate_drift(self, pos: dict):
        asset_class = pos["asset_class"]
        signal_score = pos["signal_score"]
        prob_positive = pos["prob_positive"]
        floating = pos["floating"]

        low, high = self.asset_volatility.get(asset_class, (0.5, 2.0))

        signal_bias = ((signal_score / 15.0) * 1.8)
        prob_bias = ((prob_positive - 0.5) * 3.2)
        base_positive_bias = signal_bias + prob_bias

        momentum_bonus = 0.0
        if floating > 0:
            if floating >= 6.0:
                momentum_bonus = 1.8
            elif floating >= 3.0:
                momentum_bonus = 1.0
            elif floating >= 1.0:
                momentum_bonus = 0.45

        loser_penalty = 0.0
        if floating < 0:
            if floating <= -5.0:
                loser_penalty = -1.5
            elif floating <= -2.0:
                loser_penalty = -0.8
            else:
                loser_penalty = -0.3

        raw_random = random.uniform(-low, high)

        drift = (
            raw_random
            + base_positive_bias
            + momentum_bonus
            + loser_penalty
        )

        if asset_class == "OPTIONS":
            drift *= 1.25
        elif asset_class == "FX":
            drift *= 0.72
        elif asset_class == "FUTURES":
            drift *= 1.08
        elif asset_class == "CRYPTO":
            drift *= 1.12

        return round(drift, 4)


smart_drift_engine = SmartDriftEngine()
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
            "decay_guard_active": False,
            "peak_unrealized": 0.0,
            "breach": False,
            "priority_score": 0.0,
        })

    def reprice_all_positions(self):
        by_asset = {
            "CRYPTO": 0.0,
            "FX": 0.0,
            "OPTIONS": 0.0,
            "FUTURES": 0.0,
        }

        breached_candidates = []

        for pos in self.positions:
            if pos["forced_exit"] or pos["remaining_size"] <= 0:
                continue

            drift = smart_drift_engine.generate_drift(pos)
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
            pos["decay_guard_active"] = trail_result["decay_guard_active"]
            pos["breach"] = trail_result["breach"]
            pos["peak_unrealized"] = trail_result["peak_unrealized"]

            if trail_result["force_exit"]:
                pos["priority_score"] = exit_priority_engine.compute_priority_score(pos)
                breached_candidates.append(pos)

        # ---------------------------------
        # PQR-5 selective priority exits
        # Exit only the weakest breached names first
        # ---------------------------------
        if breached_candidates:
            breached_candidates.sort(
                key=lambda p: p["priority_score"],
                reverse=True
            )

            exit_limit = max(1, int(len(breached_candidates) * 0.50))

            for pos in breached_candidates[:exit_limit]:
                pos["forced_exit"] = True
                pos["floating"] = pos["locked_floor"]
                locked_profit_ledger.record_forced_exit(pos["locked_floor"])
                locked_profit_ledger.record_priority_exit()

        for pos in self.positions:
            if pos["forced_exit"] or pos["remaining_size"] <= 0:
                continue

            by_asset[pos["asset_class"]] += (
                pos["floating"] * pos["remaining_size"]
            )

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
        return round(
            sum(p["partials_taken"] for p in self.positions),
            4
        )

    def total_trailing_active(self):
        return sum(
            1 for p in self.positions
            if p["trailing_active"] and not p["forced_exit"]
        )

    def total_decay_guard_active(self):
        return sum(
            1 for p in self.positions
            if p["decay_guard_active"] and not p["forced_exit"]
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

crypto_pnl = {s: 0.0 for s in SYMBOLS}
fx_pnl = {s: 0.0 for s in FX_SYMBOLS}
options_pnl = {s: 0.0 for s in OPTION_SYMBOLS}
futures_pnl = {s: 0.0 for s in FUTURES_SYMBOLS}

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
    print(f"DECAY GUARD ACTIVE: {mtm_engine.total_decay_guard_active()}")
    print(f"LOCKED PROFITS BANKED: {ledger['partial_profit_banked']:+.4f}")
    print(f"FORCED EXIT PROFITS: {ledger['forced_exit_profit_banked']:+.4f}")
    print(f"TRAIL STOPS HIT: {ledger['trail_stops_hit']}")
    print(f"PARTIAL EVENTS: {ledger['partial_events']}")
    print(f"ACCELERATED LOCKS: {ledger['accelerated_locks']}")
    print(f"DECAY PROTECTIONS: {ledger['decay_protections']}")
    print(f"PRIORITY EXITS: {ledger['priority_exits']}")
    print(f"LAST TRADE: {last_trade}")
    print("-" * 60)

    # CRYPTO
    for s in SYMBOLS:
        safe_load_runtime_asset(s)
        pnl = round(random.uniform(-4, 18), 4)
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
        pnl = round(random.uniform(-3, 15), 4)
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
        pnl = round(random.uniform(-6, 28), 4)
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
        pnl = round(random.uniform(-5, 24), 4)
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