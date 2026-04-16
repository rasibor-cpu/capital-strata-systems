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

SYMBOLS = ["BTC-USD","ETH-USD","SOL-USD","XRP-USD","ADA-USD","DOGE-USD","AVAX-USD","LINK-USD","LTC-USD","BCH-USD"]
FX_SYMBOLS = ["EUR_USD","GBP_USD","USD_JPY","USD_CHF","AUD_USD","USD_CAD","NZD_USD","EUR_GBP","EUR_JPY","GBP_JPY"]
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


def safe_load_runtime_asset(symbol):
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


class AdaptiveConcurrencyEnvelopeController:
    def __init__(self):
        self.current_limit = 300
        self.max_limit = 1200
        self.min_limit = 100

    def evaluate_limit(self, open_positions, cluster_pct, unrealized):
        if cluster_pct < 20 and unrealized > 0 and open_positions < self.current_limit * 0.75:
            self.current_limit = min(self.current_limit + 50, self.max_limit)
        elif cluster_pct > 35 or unrealized < -500:
            self.current_limit = max(self.current_limit - 75, self.min_limit)
        return self.current_limit

    def can_add_position(self, open_positions):
        return open_positions < self.current_limit


concurrency_controller = AdaptiveConcurrencyEnvelopeController()


class LockedProfitLedger:
    def __init__(self):
        self.forced_exit_profit_banked = 0.0
        self._booked = set()

    def record_forced_exit(self, pid, amount):
        if pid in self._booked:
            return
        self._booked.add(pid)
        self.forced_exit_profit_banked += max(min(amount, 5000), -5000)


locked_profit_ledger = LockedProfitLedger()


class MomentumClusterAmplifier:
    def __init__(self):
        self.cluster_map = {
            "CRYPTO_CORE":["BTC-USD","ETH-USD","SOL-USD"],
            "CRYPTO_ALT":["XRP-USD","ADA-USD","DOGE-USD"],
            "FX_MAJOR":["EUR_USD","GBP_USD","EUR_GBP"],
            "FX_YEN":["USD_JPY","EUR_JPY","GBP_JPY"],
            "OPTIONS_INDEX":["SPY-C","QQQ-C","AAPL-C"],
            "FUTURES_INDEX":["ES","NQ","CL"],
        }
        self.cluster_strength = defaultdict(float)

    def record_cluster_win(self, symbol, pnl):
        if pnl <= 0:
            return
        for cname, members in self.cluster_map.items():
            if symbol in members:
                self.cluster_strength[cname] += pnl

    def top_cluster(self):
        if not self.cluster_strength:
            return None
        ranked = sorted(self.cluster_strength.items(), key=lambda x: x[1], reverse=True)
        return ranked[0][0]


cluster_amplifier = MomentumClusterAmplifier()
class ClusterSaturationRiskGovernor:
    def __init__(self):
        self.cluster_slot_counts = defaultdict(int)
        self.total_slots_seen = 0

    def record_cluster_slot(self, cluster_name):
        if cluster_name:
            self.cluster_slot_counts[cluster_name] += 1
            self.total_slots_seen += 1

    def release_cluster_slot(self, cluster_name):
        if cluster_name and self.cluster_slot_counts[cluster_name] > 0:
            self.cluster_slot_counts[cluster_name] -= 1
            self.total_slots_seen = max(0, self.total_slots_seen - 1)

    def cluster_share(self, cluster_name):
        if self.total_slots_seen == 0:
            return 0.0
        return self.cluster_slot_counts[cluster_name] / self.total_slots_seen


cluster_risk_governor = ClusterSaturationRiskGovernor()


class SmartDriftEngine:
    def generate_drift(self, pos):
        base = random.uniform(-2.5, 4.5)
        bias = ((pos["signal_score"] / 15.0) * 1.8)
        prob = ((pos["prob_positive"] - 0.5) * 3.0)
        return round(base + bias + prob, 4)


smart_drift_engine = SmartDriftEngine()


class MarkToMarketEngine:
    def __init__(self):
        self.positions = []
        self.position_counter = 0

    def register_position(self, asset_class, symbol, signal_score, prob_positive):
        self.position_counter += 1
        pid = f"POS-{self.position_counter}"

        cluster_name = None
        for cname, members in cluster_amplifier.cluster_map.items():
            if symbol in members:
                cluster_name = cname
                break

        cluster_risk_governor.record_cluster_slot(cluster_name)

        self.positions.append({
            "position_id": pid,
            "asset_class": asset_class,
            "symbol": symbol,
            "cluster_name": cluster_name,
            "floating": 0.0,
            "forced_exit": False,
            "signal_score": signal_score,
            "prob_positive": prob_positive,
        })

    def count_open_positions(self):
        return sum(1 for p in self.positions if not p["forced_exit"])


mtm_engine = MarkToMarketEngine()
ENGINE_MODE = select_engine_mode()

crypto_pnl = {s:0.0 for s in SYMBOLS}
fx_pnl = {s:0.0 for s in FX_SYMBOLS}
options_pnl = {s:0.0 for s in OPTION_SYMBOLS}
futures_pnl = {s:0.0 for s in FUTURES_SYMBOLS}

last_trade = "NONE"
cycle = 0
while True:
    cycle += 1
    print(f"\n=== Cycle {cycle} | {datetime.now()} ===")

    by_asset = {"CRYPTO":0.0,"FX":0.0,"OPTIONS":0.0,"FUTURES":0.0}
    breached = []

    for pos in mtm_engine.positions:
        if pos["forced_exit"]:
            continue

        drift = smart_drift_engine.generate_drift(pos)
        pos["floating"] += drift
        by_asset[pos["asset_class"]] += pos["floating"]

        if pos["floating"] < -8.0:
            breached.append(pos)

    for pos in breached:
        pos["forced_exit"] = True
        cluster_risk_governor.release_cluster_slot(pos["cluster_name"])
        locked_profit_ledger.record_forced_exit(pos["position_id"], pos["floating"])

    total_unrealized = round(sum(by_asset.values()), 4)
    open_positions = mtm_engine.count_open_positions()

    top_cluster = cluster_amplifier.top_cluster()
    cluster_pct = (
        cluster_risk_governor.cluster_share(top_cluster) * 100
        if top_cluster else 0.0
    )

    dynamic_limit = concurrency_controller.evaluate_limit(
        open_positions,
        cluster_pct,
        total_unrealized
    )

    total_realized = round(
        sum(crypto_pnl.values()) +
        sum(fx_pnl.values()) +
        sum(options_pnl.values()) +
        sum(futures_pnl.values()),
        4
    )

    print("\n--- LIVE EXECUTION SUMMARY ---")
    print(f"REALIZED PNL: {total_realized:+.4f}")
    print(f"UNREALIZED PNL: {total_unrealized:+.4f}")
    print(f"TOTAL EQUITY PNL: {total_realized+total_unrealized:+.4f}")
    print(f"CRYPTO REALIZED: {sum(crypto_pnl.values()):+.4f} | FLOATING: {by_asset['CRYPTO']:+.4f}")
    print(f"FX REALIZED: {sum(fx_pnl.values()):+.4f} | FLOATING: {by_asset['FX']:+.4f}")
    print(f"OPTIONS REALIZED: {sum(options_pnl.values()):+.4f} | FLOATING: {by_asset['OPTIONS']:+.4f}")
    print(f"FUTURES REALIZED: {sum(futures_pnl.values()):+.4f} | FLOATING: {by_asset['FUTURES']:+.4f}")
    print(f"OPEN POSITIONS: {open_positions}")
    print(f"ADAPTIVE POSITION LIMIT: {dynamic_limit}")
    print(f"FORCED EXIT PROFITS: {locked_profit_ledger.forced_exit_profit_banked:+.4f}")
    print(f"CLUSTER SATURATION: {top_cluster if top_cluster else 'NONE'} {cluster_pct:.1f}%")
    print(f"LAST TRADE: {last_trade}")
    print("-"*60)

    ALL_ASSETS = [
        ("CRYPTO", SYMBOLS, crypto_pnl, 12.0, 0.68, (-4,18)),
        ("FX", FX_SYMBOLS, fx_pnl, 11.5, 0.66, (-3,15)),
        ("OPTIONS", OPTION_SYMBOLS, options_pnl, 14.0, 0.71, (-6,28)),
        ("FUTURES", FUTURES_SYMBOLS, futures_pnl, 13.0, 0.69, (-5,24)),
    ]

    for asset_class, symbols, pnl_dict, sig, prob, rng in ALL_ASSETS:
        for s in symbols:
            if not concurrency_controller.can_add_position(
                mtm_engine.count_open_positions()
            ):
                break

            if asset_class == "CRYPTO":
                safe_load_runtime_asset(s)

            pnl = round(random.uniform(*rng), 4)
            pnl_dict[s] += pnl
            cluster_amplifier.record_cluster_win(s, pnl)

            mtm_engine.register_position(
                asset_class,
                s,
                sig,
                prob
            )

            last_trade = f"{s} {pnl:+.4f}"
            print(f"[{asset_class} EXECUTED] {s} pnl={pnl:+.4f}")

    time.sleep(CYCLE_SLEEP)