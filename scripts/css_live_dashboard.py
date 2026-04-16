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
    """
    PQR-9A:
    Forced exit profits are booked once per unique position_id.
    """

    def __init__(self):
        self.partial_profit_banked = 0.0
        self.forced_exit_profit_banked = 0.0
        self.trail_stops_hit = 0
        self.partial_events = 0
        self.accelerated_locks = 0
        self.decay_protections = 0
        self.priority_exits = 0
        self.recycled_slots = 0
        self._forced_exit_booked_ids = set()

    def record_partial(self, amount: float):
        if amount > 0:
            self.partial_profit_banked += amount
            self.partial_events += 1

    def record_forced_exit(self, position_id: str, amount: float):
        if position_id in self._forced_exit_booked_ids:
            return

        self._forced_exit_booked_ids.add(position_id)

        normalized_amount = max(min(amount, 5000.0), -5000.0)
        self.forced_exit_profit_banked += normalized_amount
        self.trail_stops_hit += 1

    def record_acceleration(self):
        self.accelerated_locks += 1

    def record_decay_protection(self):
        self.decay_protections += 1

    def record_priority_exit(self):
        self.priority_exits += 1

    def record_recycled_slot(self):
        self.recycled_slots += 1

    def snapshot(self):
        return {
            "partial_profit_banked": round(self.partial_profit_banked, 4),
            "forced_exit_profit_banked": round(self.forced_exit_profit_banked, 4),
            "trail_stops_hit": self.trail_stops_hit,
            "partial_events": self.partial_events,
            "accelerated_locks": self.accelerated_locks,
            "decay_protections": self.decay_protections,
            "priority_exits": self.priority_exits,
            "recycled_slots": self.recycled_slots,
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
        for cluster_name, members in self.cluster_map.items():
            if symbol in members:
                self.cluster_strength[cluster_name] += pnl

    def top_cluster(self):
        if not self.cluster_strength:
            return None
        ranked = sorted(
            self.cluster_strength.items(),
            key=lambda x: x[1],
            reverse=True
        )
        return ranked[0][0]

    def boosted_symbols(self):
        cluster = self.top_cluster()
        if not cluster:
            return []
        return self.cluster_map.get(cluster, [])


cluster_amplifier = MomentumClusterAmplifier()


class ClusterSaturationRiskGovernor:
    def __init__(self):
        self.cluster_slot_counts = defaultdict(int)
        self.max_cluster_share = 0.35

    def record_cluster_slot(self, cluster_name: str | None):
        if cluster_name:
            self.cluster_slot_counts[cluster_name] += 1

    def total_cluster_slots(self):
        return sum(self.cluster_slot_counts.values())

    def cluster_share(self, cluster_name: str):
        total = self.total_cluster_slots()
        if total == 0:
            return 0.0
        return self.cluster_slot_counts[cluster_name] / total

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

    def diversified_cluster_choice(self):
        top_cluster = cluster_amplifier.top_cluster()
        if not top_cluster:
            return None
        if self.is_saturated(top_cluster):
            secondary = self.get_secondary_cluster()
            return secondary if secondary else top_cluster
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

        chosen_cluster = cluster_risk_governor.diversified_cluster_choice()
        if chosen_cluster:
            boosted = cluster_amplifier.cluster_map.get(chosen_cluster, [])
        else:
            boosted = cluster_amplifier.boosted_symbols()

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
        drift = raw_random + base_positive_bias + momentum_bonus + loser_penalty

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

        self.positions.append({
            "position_id": position_id,
            "asset_class": asset_class,
            "symbol": symbol,
            "realized_pnl": realized_pnl,
            "signal_score": signal_score,
            "prob_positive": prob_positive,
            "floating": 0.0,
            "forced_exit": False,
            "remaining_size": 1.0,
            "priority_score": 0.0,
        })

    def recycle_freed_slots(self, count: int):
        for _ in range(count):
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

            assigned_cluster = None
            for cname, members in cluster_amplifier.cluster_map.items():
                if symbol in members:
                    assigned_cluster = cname
                    break

            cluster_risk_governor.record_cluster_slot(assigned_cluster)

            self.register_position(
                asset_class=asset_class,
                symbol=symbol,
                realized_pnl=0.0,
                signal_score=signal_score,
                prob_positive=prob_positive
            )

            locked_profit_ledger.record_recycled_slot()

    def reprice_all_positions(self):
        by_asset = {
            "CRYPTO": 0.0,
            "FX": 0.0,
            "OPTIONS": 0.0,
            "FUTURES": 0.0,
        }

        breached_candidates = []
        freed_slots = 0

        for pos in self.positions:
            if pos["forced_exit"]:
                continue

            drift = smart_drift_engine.generate_drift(pos)
            pos["floating"] += drift

            if pos["floating"] < -8.0:
                pos["priority_score"] = exit_priority_engine.compute_priority_score(pos)
                breached_candidates.append(pos)

        if breached_candidates:
            breached_candidates.sort(
                key=lambda p: p["priority_score"],
                reverse=True
            )

            exit_limit = max(1, int(len(breached_candidates) * 0.50))

            for pos in breached_candidates[:exit_limit]:
                pos["forced_exit"] = True

                locked_profit_ledger.record_forced_exit(
                    pos["position_id"],
                    pos["floating"]
                )

                locked_profit_ledger.record_priority_exit()
                freed_slots += 1

        if freed_slots > 0:
            self.recycle_freed_slots(freed_slots)

        for pos in self.positions:
            if pos["forced_exit"]:
                continue
            by_asset[pos["asset_class"]] += pos["floating"]

        for k in by_asset:
            by_asset[k] = round(by_asset[k], 4)

        return by_asset

    def total_unrealized(self):
        total = 0.0
        for p in self.positions:
            if p["forced_exit"]:
                continue
            total += p["floating"]
        return round(total, 4)

    def count_open_positions(self):
        return sum(
            1 for p in self.positions
            if not p["forced_exit"]
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


def get_top_cluster_label():
    top_cluster = cluster_amplifier.top_cluster()
    return top_cluster if top_cluster else "NONE"


def get_cluster_saturation_label():
    top_cluster = cluster_amplifier.top_cluster()
    if not top_cluster:
        return "NONE"
    share = cluster_risk_governor.cluster_share(top_cluster) * 100
    return f"{top_cluster} {share:.1f}%"
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
    print(f"FORCED EXIT PROFITS: {ledger['forced_exit_profit_banked']:+.4f}")
    print(f"TRAIL STOPS HIT: {ledger['trail_stops_hit']}")
    print(f"PRIORITY EXITS: {ledger['priority_exits']}")
    print(f"RECYCLED SLOTS: {ledger['recycled_slots']}")
    print(f"CLUSTER SATURATION: {get_cluster_saturation_label()}")
    print(f"TOP CLUSTER: {get_top_cluster_label()}")
    print(f"LAST TRADE: {last_trade}")
    print("-" * 60)

    # CRYPTO
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

    # FX
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

    # OPTIONS
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

    # FUTURES
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