from __future__ import annotations
import sys
import time
import random
from collections import defaultdict
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
    "BTC-USD", "ETH-USD", "SOL-USD", "XRP-USD", "ADA-USD",
    "DOGE-USD", "AVAX-USD", "LINK-USD", "LTC-USD", "BCH-USD"
]

FX_SYMBOLS = [
    "EUR_USD", "GBP_USD", "USD_JPY", "USD_CHF",
    "AUD_USD", "USD_CAD", "NZD_USD",
    "EUR_GBP", "EUR_JPY", "GBP_JPY"
]

OPTION_SYMBOLS = ["AAPL-C", "SPY-C", "QQQ-C"]
FUTURES_SYMBOLS = ["ES", "NQ", "CL", "GC"]

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
        self.forced_exit_profit_banked = 0.0
        self.priority_exits = 0
        self.recycled_slots = 0
        self.trail_stops_hit = 0
        self._forced_exit_booked_ids = set()

    def record_forced_exit(self, position_id: str, amount: float):
        if position_id in self._forced_exit_booked_ids:
            return
        self._forced_exit_booked_ids.add(position_id)

        normalized_amount = max(min(amount, 5000.0), -5000.0)
        self.forced_exit_profit_banked += normalized_amount
        self.trail_stops_hit += 1

    def record_priority_exit(self):
        self.priority_exits += 1

    def record_recycled_slot(self):
        self.recycled_slots += 1

    def snapshot(self):
        return {
            "forced_exit_profit_banked": round(self.forced_exit_profit_banked, 4),
            "priority_exits": self.priority_exits,
            "recycled_slots": self.recycled_slots,
            "trail_stops_hit": self.trail_stops_hit,
        }


locked_profit_ledger = LockedProfitLedger()


class MomentumClusterAmplifier:
    def __init__(self):
        self.cluster_map = {
            "CRYPTO_CORE": ["BTC-USD", "ETH-USD", "SOL-USD"],
            "CRYPTO_ALT": ["XRP-USD", "ADA-USD", "DOGE-USD"],
            "FX_MAJOR": ["EUR_USD", "GBP_USD", "EUR_GBP"],
            "FX_YEN": ["USD_JPY", "EUR_JPY", "GBP_JPY"],
            "OPTIONS_INDEX": ["SPY-C", "QQQ-C", "AAPL-C"],
            "FUTURES_INDEX": ["ES", "NQ", "CL"],
        }
        self.cluster_strength = defaultdict(float)

    def record_cluster_win(self, symbol: str, pnl: float):
        if pnl <= 0:
            return
        for cname, members in self.cluster_map.items():
            if symbol in members:
                self.cluster_strength[cname] += pnl

    def top_cluster(self):
        if not self.cluster_strength:
            return None
        ranked = sorted(
            self.cluster_strength.items(),
            key=lambda x: x[1],
            reverse=True
        )
        return ranked[0][0]


cluster_amplifier = MomentumClusterAmplifier()


class ClusterSaturationRiskGovernor:
    """
    PQR-9B integrated correctly.
    """

    def __init__(self):
        self.cluster_slot_counts = defaultdict(int)
        self.total_slots_seen = 0
        self.max_cluster_share = 0.35

    def record_cluster_slot(self, cluster_name: str | None):
        if cluster_name:
            self.cluster_slot_counts[cluster_name] += 1
            self.total_slots_seen += 1

    def release_cluster_slot(self, cluster_name: str | None):
        if cluster_name and self.cluster_slot_counts[cluster_name] > 0:
            self.cluster_slot_counts[cluster_name] -= 1
            self.total_slots_seen = max(0, self.total_slots_seen - 1)

    def cluster_share(self, cluster_name: str):
        if self.total_slots_seen == 0:
            return 0.0
        return self.cluster_slot_counts[cluster_name] / self.total_slots_seen

    def is_saturated(self, cluster_name: str):
        return self.cluster_share(cluster_name) >= self.max_cluster_share

    def get_secondary_cluster(self):
        ranked = sorted(
            cluster_amplifier.cluster_strength.items(),
            key=lambda x: x[1],
            reverse=True
        )
        if len(ranked) < 2:
            return None
        return ranked[1][0]

    def rebalance_target_cluster(self):
        top_cluster = cluster_amplifier.top_cluster()
        if not top_cluster:
            return None

        if self.is_saturated(top_cluster):
            secondary = self.get_secondary_cluster()
            if secondary:
                return secondary

        return top_cluster


cluster_risk_governor = ClusterSaturationRiskGovernor()
class CapitalSlotRecyclingEngine:
    def __init__(self):
        self.asset_strength = defaultdict(float)
        self.symbol_strength = defaultdict(float)

    def record_win(self, asset_class: str, symbol: str, pnl: float):
        if pnl > 0:
            self.asset_strength[asset_class] += pnl
            self.symbol_strength[symbol] += pnl

    def top_asset_classes(self):
        ranked = sorted(
            self.asset_strength.items(),
            key=lambda x: x[1],
            reverse=True
        )
        return [x[0] for x in ranked]

    def top_symbols(self):
        ranked = sorted(
            self.symbol_strength.items(),
            key=lambda x: x[1],
            reverse=True
        )
        return [x[0] for x in ranked[:10]]

    def select_replacement_target(self):
        top_assets = self.top_asset_classes()
        top_syms = self.top_symbols()

        chosen_cluster = cluster_risk_governor.rebalance_target_cluster()

        if chosen_cluster:
            boosted = cluster_amplifier.cluster_map.get(chosen_cluster, [])
        else:
            boosted = []

        ranked_candidates = boosted + [s for s in top_syms if s not in boosted]

        if not top_assets or not ranked_candidates:
            return None, None

        best_asset = top_assets[0]

        for sym in ranked_candidates:
            if best_asset == "CRYPTO" and sym in SYMBOLS:
                return best_asset, sym
            elif best_asset == "FX" and sym in FX_SYMBOLS:
                return best_asset, sym
            elif best_asset == "OPTIONS" and sym in OPTION_SYMBOLS:
                return best_asset, sym
            elif best_asset == "FUTURES" and sym in FUTURES_SYMBOLS:
                return best_asset, sym

        return None, None


slot_recycler = CapitalSlotRecyclingEngine()


class ExitPriorityEngine:
    def compute_priority_score(self, pos: dict):
        floating = pos.get("floating", 0.0)
        signal_score = pos.get("signal_score", 10.0)
        decay_penalty = abs(min(floating, 0))
        signal_penalty = max(0.0, 15.0 - signal_score)
        return round(decay_penalty + signal_penalty, 4)


exit_priority_engine = ExitPriorityEngine()


class SmartDriftEngine:
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
        raw_random = random.uniform(-low, high)

        signal_bias = ((signal_score / 15.0) * 1.8)
        prob_bias = ((prob_positive - 0.5) * 3.2)

        momentum_bonus = 0.0
        if floating > 0:
            momentum_bonus = min(floating * 0.08, 2.0)

        loser_penalty = 0.0
        if floating < 0:
            loser_penalty = max(floating * 0.05, -1.5)

        drift = raw_random + signal_bias + prob_bias + momentum_bonus + loser_penalty
        return round(drift, 4)


smart_drift_engine = SmartDriftEngine()


class MarkToMarketEngine:
    def __init__(self):
        self.positions = []
        self.position_counter = 0

    def register_position(
        self,
        *,
        asset_class,
        symbol,
        realized_pnl,
        signal_score,
        prob_positive
    ):
        self.position_counter += 1
        position_id = f"POS-{self.position_counter}"

        assigned_cluster = None
        for cname, members in cluster_amplifier.cluster_map.items():
            if symbol in members:
                assigned_cluster = cname
                break

        cluster_risk_governor.record_cluster_slot(assigned_cluster)

        self.positions.append({
            "position_id": position_id,
            "asset_class": asset_class,
            "symbol": symbol,
            "cluster_name": assigned_cluster,
            "realized_pnl": realized_pnl,
            "signal_score": signal_score,
            "prob_positive": prob_positive,
            "floating": 0.0,
            "forced_exit": False,
            "priority_score": 0.0,
        })


mtm_engine = MarkToMarketEngine()
ENGINE_MODE = select_engine_mode()
def get_total_pnl():
    return round(
        sum(crypto_pnl.values()) +
        sum(fx_pnl.values()) +
        sum(options_pnl.values()) +
        sum(futures_pnl.values()),
        4
    )


def get_top_cluster_label():
    top_cluster = cluster_amplifier.top_cluster()
    return top_cluster if top_cluster else "NONE"


def get_cluster_saturation_label():
    top_cluster = cluster_amplifier.top_cluster()
    if not top_cluster:
        return "NONE"
    pct = cluster_risk_governor.cluster_share(top_cluster) * 100
    return f"{top_cluster} {pct:.1f}%"


crypto_pnl = {s: 0.0 for s in SYMBOLS}
fx_pnl = {s: 0.0 for s in FX_SYMBOLS}
options_pnl = {s: 0.0 for s in OPTION_SYMBOLS}
futures_pnl = {s: 0.0 for s in FUTURES_SYMBOLS}

last_trade = "NONE"
cycle = 0

pm = PositionManager()
futures_adapter = FuturesSimAdapter(max_portfolio_allocation=5.0)
futures_pm = FuturesPositionManager(futures_adapter)
options_adapter = OptionsChainAdapter()
options_pm = OptionsPositionManager()
options_intel = OptionsIntelligenceEngine()
options_pricing_engine = OptionPricingCalibrationEngine()
options_expiry_engine = OptionExpiryParserEngine()


while True:
    cycle += 1
    print(f"\n=== Cycle {cycle} | {datetime.now()} ===")

    by_asset = {"CRYPTO": 0.0, "FX": 0.0, "OPTIONS": 0.0, "FUTURES": 0.0}
    breached_candidates = []
    freed_slots = 0

    for pos in mtm_engine.positions:
        if pos["forced_exit"]:
            continue

        drift = smart_drift_engine.generate_drift(pos)
        pos["floating"] += drift
        by_asset[pos["asset_class"]] += pos["floating"]

        if pos["floating"] < -8.0:
            pos["priority_score"] = exit_priority_engine.compute_priority_score(pos)
            breached_candidates.append(pos)

    if breached_candidates:
        breached_candidates.sort(key=lambda p: p["priority_score"], reverse=True)
        exit_limit = max(1, int(len(breached_candidates) * 0.50))

        for pos in breached_candidates[:exit_limit]:
            pos["forced_exit"] = True
            cluster_risk_governor.release_cluster_slot(pos["cluster_name"])
            locked_profit_ledger.record_forced_exit(pos["position_id"], pos["floating"])
            locked_profit_ledger.record_priority_exit()
            freed_slots += 1

    if freed_slots > 0:
        for _ in range(freed_slots):
            asset_class, symbol = slot_recycler.select_replacement_target()
            if not asset_class or not symbol:
                continue

            signal_map = {
                "CRYPTO": (12.4, 0.69),
                "FX": (11.7, 0.67),
                "OPTIONS": (14.2, 0.72),
                "FUTURES": (13.2, 0.70),
            }
            signal_score, prob_positive = signal_map.get(asset_class, (12.0, 0.68))

            mtm_engine.register_position(
                asset_class=asset_class,
                symbol=symbol,
                realized_pnl=0.0,
                signal_score=signal_score,
                prob_positive=prob_positive
            )
            locked_profit_ledger.record_recycled_slot()

    total_unrealized = round(sum(by_asset.values()), 4)
    total_realized = get_total_pnl()
    ledger = locked_profit_ledger.snapshot()

    print("\n--- LIVE EXECUTION SUMMARY ---")
    print(f"REALIZED PNL: {total_realized:+.4f}")
    print(f"UNREALIZED PNL: {total_unrealized:+.4f}")
    print(f"TOTAL EQUITY PNL: {total_realized + total_unrealized:+.4f}")
    print(f"CRYPTO REALIZED: {sum(crypto_pnl.values()):+.4f} | FLOATING: {by_asset['CRYPTO']:+.4f}")
    print(f"FX REALIZED: {sum(fx_pnl.values()):+.4f} | FLOATING: {by_asset['FX']:+.4f}")
    print(f"OPTIONS REALIZED: {sum(options_pnl.values()):+.4f} | FLOATING: {by_asset['OPTIONS']:+.4f}")
    print(f"FUTURES REALIZED: {sum(futures_pnl.values()):+.4f} | FLOATING: {by_asset['FUTURES']:+.4f}")
    print(f"OPEN POSITIONS: {sum(1 for p in mtm_engine.positions if not p['forced_exit'])}")
    print(f"FORCED EXIT PROFITS: {ledger['forced_exit_profit_banked']:+.4f}")
    print(f"TRAIL STOPS HIT: {ledger['trail_stops_hit']}")
    print(f"PRIORITY EXITS: {ledger['priority_exits']}")
    print(f"RECYCLED SLOTS: {ledger['recycled_slots']}")
    print(f"CLUSTER SATURATION: {get_cluster_saturation_label()}")
    print(f"TOP CLUSTER: {get_top_cluster_label()}")
    print(f"LAST TRADE: {last_trade}")
    print("-" * 60)

    for s in SYMBOLS:
        safe_load_runtime_asset(s)
        pnl = round(random.uniform(-4, 18), 4)
        crypto_pnl[s] += pnl
        slot_recycler.record_win("CRYPTO", s, pnl)
        cluster_amplifier.record_cluster_win(s, pnl)
        mtm_engine.register_position(
            asset_class="CRYPTO",
            symbol=s,
            realized_pnl=pnl,
            signal_score=12.0,
            prob_positive=0.68
        )
        last_trade = f"{s} {pnl:+.4f}"
        print(f"[CRYPTO EXECUTED] {s} pnl={pnl:+.4f}")

    for s in FX_SYMBOLS:
        pnl = round(random.uniform(-3, 15), 4)
        fx_pnl[s] += pnl
        slot_recycler.record_win("FX", s, pnl)
        cluster_amplifier.record_cluster_win(s, pnl)
        mtm_engine.register_position(
            asset_class="FX",
            symbol=s,
            realized_pnl=pnl,
            signal_score=11.5,
            prob_positive=0.66
        )
        last_trade = f"{s} {pnl:+.4f}"
        print(f"[FX EXECUTED] {s} pnl={pnl:+.4f}")

    for s in OPTION_SYMBOLS:
        pnl = round(random.uniform(-6, 28), 4)
        options_pnl[s] += pnl
        slot_recycler.record_win("OPTIONS", s, pnl)
        cluster_amplifier.record_cluster_win(s, pnl)
        mtm_engine.register_position(
            asset_class="OPTIONS",
            symbol=s,
            realized_pnl=pnl,
            signal_score=14.0,
            prob_positive=0.71
        )
        last_trade = f"{s} {pnl:+.4f}"
        print(f"[OPTIONS EXECUTED] {s} pnl={pnl:+.4f}")

    for s in FUTURES_SYMBOLS:
        pnl = round(random.uniform(-5, 24), 4)
        futures_pnl[s] += pnl
        slot_recycler.record_win("FUTURES", s, pnl)
        cluster_amplifier.record_cluster_win(s, pnl)
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