from __future__ import annotations

import time
import random
from dataclasses import dataclass
from typing import List, Dict, Any


# ===============================
# CONFIG
# ===============================

STARTING_BALANCE = 200.0

# 🔥 FORCE ONE PER CLASS
RESERVED_ORDER = ["FX", "CRYPTO", "FUTURES", "OPTIONS"]

# relaxed thresholds
ASSET_RULES = {
    "CRYPTO":  {"min_score": 0.25, "min_edge": 0.005},
    "FX":      {"min_score": 0.28, "min_edge": 0.005},
    "FUTURES": {"min_score": 0.28, "min_edge": 0.006},
    "OPTIONS": {"min_score": 0.30, "min_edge": 0.006},
}

ELITE_SCORE = 0.55
ELITE_EDGE = 0.007

BASE_RISK_PER_TRADE = 0.02
WIN_MULTIPLIER = 1.0
LOSS_MULTIPLIER = 0.8


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


# ===============================
# COST ENGINE
# ===============================

class ExecutionCostEngine:

    def estimate_cost(self, asset_class: str) -> float:

        return {
            "CRYPTO": 0.005,
            "FX": 0.0025,
            "FUTURES": 0.0035,
            "OPTIONS": 0.006,
        }.get(asset_class, 0.005)


# ===============================
# EDGE GATE
# ===============================

class EdgeGate:

    def passes(self, trade: Trade) -> bool:

        rules = ASSET_RULES.get(trade.asset_class, ASSET_RULES["CRYPTO"])

        return (
            trade.score >= rules["min_score"]
            and trade.net_edge >= rules["min_edge"]
        )
# ===============================
# FEATURE EXTRACTION
# ===============================

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


# ===============================
# OPTIONS (SAFE MODE)
# ===============================

def build_option_candidates(base_trades: List[Trade]) -> List[Trade]:

    base_trades = sorted(base_trades, key=lambda t: t.score, reverse=True)[:4]

    options = []

    for trade in base_trades:

        side = "CALL" if trade.direction == "LONG" else "PUT"

        options.append(
            Trade(
                symbol=f"{trade.symbol}_{side}",
                asset_class="OPTIONS",
                score=min(1.0, trade.score * 1.1),
                raw_score=min(1.0, trade.raw_score * 1.1),
                expected_move=min(0.25, trade.expected_move * 1.4),
                cost=ExecutionCostEngine().estimate_cost("OPTIONS"),
                net_edge=min(0.25, trade.expected_move * 1.4) - 0.006,
                direction=trade.direction,
                source=f"DERIVED_{trade.symbol}",
            )
        )

    return options


# ===============================
# SCAN
# ===============================

def scan_market() -> List[Trade]:

    scanner = UnifiedMarketScanner()
    opportunities = list(scanner.scan())

    trades: List[Trade] = []
    ai_engine = AIOpportunityScorer()

    for opp in opportunities:

        try:
            symbol = opp.get("symbol", "UNKNOWN")
            asset_class = opp.get("asset_class", "CRYPTO")
            direction = "LONG" if float(opp.get("momentum", 0)) >= 0 else "SHORT"

            features = extract_features(opp)

            raw_score = float(ai_engine.score(features)) if hasattr(ai_engine, "score") else 0.02
            score = normalize_score(raw_score)

            cost = ExecutionCostEngine().estimate_cost(asset_class)

            trades.append(
                Trade(
                    symbol=symbol,
                    asset_class=asset_class,
                    score=score,
                    raw_score=raw_score,
                    expected_move=features["expected_move"],
                    cost=cost,
                    net_edge=features["expected_move"] - cost,
                    direction=direction,
                    source="SCANNER",
                )
            )

        except Exception as e:
            print(f"[WARN] {e}")

    trades.extend(build_option_candidates(trades))

    return trades
# ===============================
# EXECUTION ENGINE
# ===============================

class ExecutionPnLEngine:

    def position_size(self, balance: float, trade: Trade) -> float:
        return balance * BASE_RISK_PER_TRADE * max(0.5, trade.score)

    def simulate_outcome(self, trade: Trade) -> str:
        prob = min(0.75, max(0.45, trade.score))
        return "WIN" if random.random() < prob else "LOSS"

    def compute_pnl(self, size: float, trade: Trade, outcome: str) -> float:

        gross = size * trade.expected_move

        if outcome == "WIN":
            gross *= WIN_MULTIPLIER
        else:
            gross *= -LOSS_MULTIPLIER

        return gross - (size * trade.cost)


# ===============================
# DASHBOARD
# ===============================

class Dashboard:

    def __init__(self):
        self.balance = STARTING_BALANCE
        self.cycle = 0
        self.edge_gate = EdgeGate()
        self.exec_engine = ExecutionPnLEngine()

    def run_cycle(self):

        self.cycle += 1

        print("\n" + "=" * 60)
        print(f"Cycle {self.cycle}")
        print("=" * 60)

        trades = scan_market()

        # group by asset class
        grouped: Dict[str, List[Trade]] = {}

        for t in trades:
            grouped.setdefault(t.asset_class, []).append(t)

        selected: List[Trade] = []

        # 🔥 RESERVED SELECTION
        for asset in RESERVED_ORDER:

            candidates = grouped.get(asset, [])

            candidates = sorted(candidates, key=lambda t: (t.score, t.net_edge), reverse=True)

            for trade in candidates:
                if self.edge_gate.passes(trade):
                    selected.append(trade)
                    break

        print("\n--- EXECUTION ---")

        cycle_pnl = 0
        asset_pnl: Dict[str, float] = {}

        for trade in selected:

            size = self.exec_engine.position_size(self.balance, trade)
            outcome = self.exec_engine.simulate_outcome(trade)
            pnl = self.exec_engine.compute_pnl(size, trade, outcome)

            cycle_pnl += pnl
            asset_pnl[trade.asset_class] = asset_pnl.get(trade.asset_class, 0) + pnl

            print(f"{trade.symbol} | {trade.asset_class} | Size: {round(size,2)} | Outcome: {outcome} | PnL: {round(pnl,2)}")

        self.balance += cycle_pnl

        print("\n--- SUMMARY ---")
        print(f"TRADES: {len(selected)}")
        print(f"CYCLE PnL: {round(cycle_pnl,2)}")
        print(f"BALANCE: {round(self.balance,2)}")

        print("\nASSET PnL:")
        for k, v in asset_pnl.items():
            print(f"{k}: {round(v,2)}")

    def run(self):

        print("\nCSS PHASE 8 — RESERVED SLOTS MODE STARTED\n")

        while True:
            self.run_cycle()
            time.sleep(5)


if __name__ == "__main__":
    Dashboard().run()