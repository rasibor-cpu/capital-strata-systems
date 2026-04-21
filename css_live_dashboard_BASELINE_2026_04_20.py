from __future__ import annotations

import time
import random
from dataclasses import dataclass
from typing import List, Dict


# ===============================
# CONFIG
# ===============================

STARTING_BALANCE = 200.0
RESERVED_ORDER = ["FX", "CRYPTO", "FUTURES", "OPTIONS"]

TOP_N_PER_ASSET = 2

ASSET_BUDGET = {
    "FX": 6.0,
    "CRYPTO": 5.0,
    "FUTURES": 4.0,
    "OPTIONS": 3.0,
}

BASE_ASSET_WEIGHTS = {
    "FX": 1.00,
    "CRYPTO": 0.90,
    "FUTURES": 0.70,
    "OPTIONS": 0.50,
}

MAX_POSITION_SIZE_BY_ASSET = {
    "FX": 5.0,
    "CRYPTO": 4.5,
    "FUTURES": 3.5,
    "OPTIONS": 2.75,
}

BASE_RISK_PER_TRADE = 0.02
LOSS_MULTIPLIER = 0.8

TILT_SCALER = 80.0
MIN_TILT = 0.92
MAX_TILT = 1.08

# Phase 13 signal expansion
EDGE_AMPLIFICATION = 1.1
SCORE_EDGE_COUPLING = 1.2
EDGE_CONVEXITY = 1.2

# 🔥 Phase 13.1 dominance control
DOMINANCE_EXPONENT = 2.2


from backend.scanner.unified_market_scanner import UnifiedMarketScanner
from backend.intelligence.ai_opportunity_scorer import AIOpportunityScorer


@dataclass
class Trade:
    symbol: str
    asset_class: str
    score: float
    expected_move: float
    cost: float
    net_edge: float
    volatility: float


# ===============================
# MEMORY
# ===============================

class PerformanceMemory:

    def __init__(self):
        self.history = {k: [] for k in RESERVED_ORDER}
        self.balance = STARTING_BALANCE

    def update(self, asset_pnl: Dict[str, float], balance: float):
        self.balance = balance
        for k, v in asset_pnl.items():
            self.history[k].append(v)
            if len(self.history[k]) > 10:
                self.history[k].pop(0)

    def get_tilt(self):
        tilt = {}
        for asset, vals in self.history.items():
            if not vals:
                tilt[asset] = 1.0
                continue

            avg = sum(vals) / len(vals)
            norm = avg / max(1.0, self.balance)
            raw = 1.0 + norm * TILT_SCALER

            tilt[asset] = max(MIN_TILT, min(MAX_TILT, raw))

        return tilt


# ===============================
# REGIME ENGINE
# ===============================

class RegimeEngine:

    def evaluate(self, asset, trades):

        if not trades:
            return "WEAK"

        avg_score = sum(t.score for t in trades) / len(trades)
        avg_edge = sum(t.net_edge for t in trades) / len(trades)

        score = avg_score * 0.5 + avg_edge * 40 * 0.5

        if score >= 0.65:
            return "STRONG"
        elif score >= 0.40:
            return "NEUTRAL"
        return "WEAK"


# ===============================
# SIGNAL ENGINE
# ===============================

def extract_features(opp):

    m = float(opp.get("momentum", 0))
    v = float(opp.get("volatility", 0.01))

    accel = abs(m) * (1 + abs(m) * 2)
    vol_boost = v * (1 + v * 5)

    move = max(
        0.01,
        min(
            0.25,
            accel * 0.6 + vol_boost * 0.6
        )
    )

    return move, v


def normalize_score(raw):
    return max(0.0, min(1.0, raw * 50))


def amplify_edge(edge, score):

    coupled = edge * (1 + score * 1.5)
    convex = abs(coupled) ** 1.4

    if convex > 0.01:
        convex *= 1.3

    return convex


def scan():

    scanner = UnifiedMarketScanner()
    ai = AIOpportunityScorer()

    trades = []

    for opp in scanner.scan():

        move, vol = extract_features(opp)

        raw = float(ai.score({"momentum": move, "volatility": vol}))
        score = normalize_score(raw)

        asset = opp.get("asset_class", "CRYPTO")

        cost = {
            "CRYPTO": 0.005,
            "FX": 0.0025,
            "FUTURES": 0.0035,
            "OPTIONS": 0.006,
        }.get(asset, 0.005)

        edge = amplify_edge(move - cost, score)

        trades.append(
            Trade(
                symbol=opp.get("symbol"),
                asset_class=asset,
                score=score,
                expected_move=move,
                cost=cost,
                net_edge=edge,
                volatility=vol
            )
        )

    return trades


# ===============================
# EXECUTION ENGINE
# ===============================

class Executor:

    def __init__(self, memory):
        self.memory = memory
        self.trades = []

    def set_trades(self, trades):
        self.trades = trades

    def rank_strength(self, trade):

        edges = [t.net_edge for t in self.trades if t.asset_class == trade.asset_class]

        if not edges:
            return 0.5

        max_e = max(edges)
        min_e = min(edges)

        if max_e == min_e:
            return 0.5

        return (trade.net_edge - min_e) / (max_e - min_e)

    def base_size(self, bal, trade, regime):

        if regime == "WEAK":
            return 0.0

        strength = self.rank_strength(trade)
        regime_factor = 1.0 if regime == "STRONG" else (0.55 + strength * 0.35)

        tilt = self.memory.get_tilt().get(trade.asset_class, 1.0)
        weight = BASE_ASSET_WEIGHTS.get(trade.asset_class, 1.0)

        size = bal * BASE_RISK_PER_TRADE * weight * tilt
        size *= max(0.5, trade.score)
        size *= (1 / max(1.0, trade.volatility * 10))
        size *= regime_factor

        return size

    def run_trade(self, trade, size):

        outcome = "WIN" if random.random() < trade.score else "LOSS"

        pnl = size * trade.expected_move

        if outcome == "LOSS":
            pnl *= -LOSS_MULTIPLIER

        pnl -= size * trade.cost

        return outcome, pnl


# ===============================
# DASHBOARD
# ===============================

class Dashboard:

    def __init__(self):
        self.balance = STARTING_BALANCE
        self.memory = PerformanceMemory()
        self.executor = Executor(self.memory)
        self.regime = RegimeEngine()

    def run(self):

        print("\nCSS PHASE 13.1 — DOMINANCE WEIGHTING ACTIVE\n")

        while True:

            trades = scan()
            self.executor.set_trades(trades)

            grouped = {}
            for t in trades:
                grouped.setdefault(t.asset_class, []).append(t)

            total_pnl = 0.0
            asset_pnl = {}

            print("\n--- EXECUTION ---")

            for asset in RESERVED_ORDER:

                asset_trades = grouped.get(asset, [])
                regime = self.regime.evaluate(asset, asset_trades)

                if regime == "WEAK":
                    print("Skipping", asset)
                    continue

                selected = sorted(
                    asset_trades,
                    key=lambda x: x.net_edge,
                    reverse=True
                )[:TOP_N_PER_ASSET]

                raw_weights = []
                for t in selected:
                    strength = self.executor.rank_strength(t)
                    dominance_weight = max(0.05, strength) ** DOMINANCE_EXPONENT
                    raw_size = self.executor.base_size(self.balance, t, regime)
                    raw_weights.append((t, raw_size * dominance_weight))

                total_weight = sum(w for _, w in raw_weights)
                budget = ASSET_BUDGET.get(asset, 5.0)

                for t, w in raw_weights:

                    if total_weight > 0:
                        size = (w / total_weight) * budget
                    else:
                        size = 0.0

                    size = min(size, MAX_POSITION_SIZE_BY_ASSET[asset])

                    if size < 0.5:
                        continue

                    outcome, pnl = self.executor.run_trade(t, size)

                    total_pnl += pnl
                    asset_pnl[asset] = asset_pnl.get(asset, 0.0) + pnl

                    print(f"{t.symbol} | {asset} | Size: {round(size,2)} | {outcome} | PnL: {round(pnl,2)}")

            self.balance += total_pnl
            self.memory.update(asset_pnl, self.balance)

            print("\nBAL:", round(self.balance, 2))
            print("PnL:", round(total_pnl, 2))
            print("TILT:", self.memory.get_tilt())

            time.sleep(5)


if __name__ == "__main__":
    Dashboard().run()