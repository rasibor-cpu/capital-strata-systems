from __future__ import annotations

import time
import random
from dataclasses import dataclass
from typing import List, Dict, Any


# ===============================
# CONFIG
# ===============================

STARTING_BALANCE = 200.0
RESERVED_ORDER = ["FX", "CRYPTO", "FUTURES", "OPTIONS"]

ASSET_RULES = {
    "CRYPTO":  {"min_score": 0.25, "min_edge": 0.005},
    "FX":      {"min_score": 0.28, "min_edge": 0.005},
    "FUTURES": {"min_score": 0.28, "min_edge": 0.006},
    "OPTIONS": {"min_score": 0.30, "min_edge": 0.006},
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
WIN_MULTIPLIER = 1.0
LOSS_MULTIPLIER = 0.8

# normalized tilt controls
TILT_SCALER = 80.0
MIN_TILT = 0.92
MAX_TILT = 1.08


# ===============================
# IMPORTS
# ===============================

from backend.scanner.unified_market_scanner import UnifiedMarketScanner
from backend.intelligence.ai_opportunity_scorer import AIOpportunityScorer


# ===============================
# DATA STRUCTURE
# ===============================

@dataclass
class Trade:
    symbol: str
    asset_class: str
    score: float
    raw_score: float
    expected_move: float
    cost: float
    net_edge: float
    direction: str
    source: str
    volatility: float


# ===============================
# NORMALIZED PERFORMANCE MEMORY
# ===============================

class PerformanceMemory:

    def __init__(self):
        self.history: Dict[str, List[float]] = {
            "FX": [],
            "CRYPTO": [],
            "FUTURES": [],
            "OPTIONS": []
        }
        self.window = 10
        self.reference_balance = STARTING_BALANCE

    def update(self, asset_pnl: Dict[str, float], balance: float):

        self.reference_balance = max(1.0, balance)

        for asset, pnl in asset_pnl.items():
            self.history.setdefault(asset, []).append(pnl)

            if len(self.history[asset]) > self.window:
                self.history[asset].pop(0)

    def get_tilt(self) -> Dict[str, float]:

        tilt = {}

        for asset, pnls in self.history.items():

            if not pnls:
                tilt[asset] = 1.0
                continue

            avg_pnl = sum(pnls) / len(pnls)
            normalized = avg_pnl / self.reference_balance

            raw_tilt = 1.0 + (normalized * TILT_SCALER)

            tilt[asset] = max(MIN_TILT, min(MAX_TILT, raw_tilt))

        return tilt
def extract_features(opp: Dict[str, Any]) -> Dict[str, float]:

    momentum = float(opp.get("momentum", 0.0))
    volatility = float(opp.get("volatility", 0.01))

    expected_move = max(
        0.01,
        min(0.15, abs(momentum) * 0.5 + volatility * 0.3)
    )

    return {
        "momentum": momentum,
        "volatility": volatility,
        "expected_move": expected_move,
    }


def normalize_score(raw_score: float) -> float:
    return max(0.0, min(1.0, raw_score * 50.0))


def build_option_candidates(base_trades: List[Trade]) -> List[Trade]:

    base = sorted(base_trades, key=lambda t: t.score, reverse=True)[:4]

    options = []

    for trade in base:

        side = "CALL" if trade.direction == "LONG" else "PUT"

        option_move = min(0.25, trade.expected_move * 1.3)

        options.append(
            Trade(
                symbol=f"{trade.symbol}_{side}",
                asset_class="OPTIONS",
                score=min(1.0, trade.score * 1.05),
                raw_score=min(1.0, trade.raw_score * 1.05),
                expected_move=option_move,
                cost=0.006,
                net_edge=option_move - 0.006,
                direction=trade.direction,
                source=f"DERIVED_{trade.symbol}",
                volatility=min(1.0, trade.volatility * 1.2),
            )
        )

    return options


def scan_market() -> List[Trade]:

    scanner = UnifiedMarketScanner()
    opportunities = list(scanner.scan())

    trades: List[Trade] = []
    ai_engine = AIOpportunityScorer()

    for opp in opportunities:
        try:
            features = extract_features(opp)

            raw_score = float(ai_engine.score(features))
            score = normalize_score(raw_score)

            cost = {
                "CRYPTO": 0.005,
                "FX": 0.0025,
                "FUTURES": 0.0035,
                "OPTIONS": 0.006,
            }.get(opp.get("asset_class", "CRYPTO"))

            trades.append(
                Trade(
                    symbol=opp.get("symbol"),
                    asset_class=opp.get("asset_class"),
                    score=score,
                    raw_score=raw_score,
                    expected_move=features["expected_move"],
                    cost=cost,
                    net_edge=features["expected_move"] - cost,
                    direction="LONG" if features["momentum"] >= 0 else "SHORT",
                    source="SCANNER",
                    volatility=features["volatility"],
                )
            )

        except Exception as e:
            print("[WARN]", e)

    trades.extend(build_option_candidates(trades))
    return trades
class ExecutionPnLEngine:

    def __init__(self, memory: PerformanceMemory):
        self.memory = memory

    def position_size(self, balance: float, trade: Trade) -> float:

        tilt = self.memory.get_tilt()

        base_weight = BASE_ASSET_WEIGHTS.get(trade.asset_class, 1.0)
        adjusted_weight = base_weight * tilt.get(trade.asset_class, 1.0)

        adjusted_weight = max(0.5, min(1.2, adjusted_weight))

        score_weight = max(0.5, min(1.0, trade.score))
        vol_damp = 1.0 / max(1.0, trade.volatility * 10)

        size = balance * BASE_RISK_PER_TRADE * adjusted_weight * score_weight * vol_damp

        size = max(1.25, size)
        size = min(size, MAX_POSITION_SIZE_BY_ASSET.get(trade.asset_class, 5.0))

        return size

    def simulate_outcome(self, trade: Trade) -> str:
        prob = min(0.75, max(0.45, trade.score))
        return "WIN" if random.random() < prob else "LOSS"

    def compute_pnl(self, size: float, trade: Trade, outcome: str) -> float:

        gross = size * trade.expected_move

        if trade.asset_class == "OPTIONS":
            gross *= 0.85

        if outcome == "WIN":
            gross *= WIN_MULTIPLIER
        else:
            gross *= -LOSS_MULTIPLIER

        return gross - (size * trade.cost)


class Dashboard:

    def __init__(self):
        self.balance = STARTING_BALANCE
        self.cycle = 0
        self.memory = PerformanceMemory()
        self.exec_engine = ExecutionPnLEngine(self.memory)

    def run_cycle(self):

        self.cycle += 1

        print("\n" + "=" * 60)
        print(f"Cycle {self.cycle}")
        print("=" * 60)

        trades = scan_market()

        grouped: Dict[str, List[Trade]] = {}
        for t in trades:
            grouped.setdefault(t.asset_class, []).append(t)

        selected: List[Trade] = []

        for asset in RESERVED_ORDER:
            candidates = sorted(
                grouped.get(asset, []),
                key=lambda t: (t.score, t.net_edge),
                reverse=True
            )

            for trade in candidates:
                rules = ASSET_RULES[asset]
                if trade.score >= rules["min_score"] and trade.net_edge >= rules["min_edge"]:
                    selected.append(trade)
                    break

        print("\n--- EXECUTION ---")

        cycle_pnl = 0.0
        asset_pnl: Dict[str, float] = {}

        for trade in selected:
            size = self.exec_engine.position_size(self.balance, trade)
            outcome = self.exec_engine.simulate_outcome(trade)
            pnl = self.exec_engine.compute_pnl(size, trade, outcome)

            cycle_pnl += pnl
            asset_pnl[trade.asset_class] = asset_pnl.get(trade.asset_class, 0.0) + pnl

            print(
                f"{trade.symbol} | {trade.asset_class} | "
                f"Size: {round(size,2)} | Outcome: {outcome} | PnL: {round(pnl,2)}"
            )

        self.balance += cycle_pnl
        self.memory.update(asset_pnl, self.balance)

        print("\n--- SUMMARY ---")
        print(f"CYCLE PnL: {round(cycle_pnl,2)}")
        print(f"BALANCE: {round(self.balance,2)}")

        print("\nTILT:")
        print(self.memory.get_tilt())

    def run(self):

        print("\nCSS PHASE 10.2 — NORMALIZED TILT MODE STARTED\n")

        while True:
            self.run_cycle()
            time.sleep(5)


if __name__ == "__main__":
    Dashboard().run()