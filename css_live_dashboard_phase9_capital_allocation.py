from __future__ import annotations

import time
import random
from dataclasses import dataclass
from typing import List, Dict, Any


# ===============================
# CONFIG
# ===============================

STARTING_BALANCE = 200.0

# reserved portfolio construction
RESERVED_ORDER = ["FX", "CRYPTO", "FUTURES", "OPTIONS"]

# thresholds
ASSET_RULES = {
    "CRYPTO":  {"min_score": 0.25, "min_edge": 0.005},
    "FX":      {"min_score": 0.28, "min_edge": 0.005},
    "FUTURES": {"min_score": 0.28, "min_edge": 0.006},
    "OPTIONS": {"min_score": 0.30, "min_edge": 0.006},
}

ELITE_SCORE = 0.55
ELITE_EDGE = 0.007
OPTIONS_ELITE_SCORE = 0.65

# base risk
BASE_RISK_PER_TRADE = 0.02

# refined asset allocation intelligence
ASSET_SIZE_WEIGHTS = {
    "FX": 1.00,
    "CRYPTO": 0.90,
    "FUTURES": 0.70,
    "OPTIONS": 0.50,
}

MAX_POSITION_SIZE_BY_ASSET = {
    "FX": 5.00,
    "CRYPTO": 4.50,
    "FUTURES": 3.50,
    "OPTIONS": 2.75,
}

# pnl model
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
    volatility: float


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
# SAFE-MODE OPTIONS GENERATOR
# ===============================

def build_option_candidates(base_trades: List[Trade]) -> List[Trade]:

    option_bases = [t for t in base_trades if t.asset_class in {"CRYPTO", "FUTURES"}]
    option_bases = sorted(option_bases, key=lambda t: (t.score, t.net_edge), reverse=True)[:4]

    options: List[Trade] = []

    for trade in option_bases:
        side = "CALL" if trade.direction == "LONG" else "PUT"

        option_move = min(0.25, trade.expected_move * 1.35)
        option_cost = ExecutionCostEngine().estimate_cost("OPTIONS")

        options.append(
            Trade(
                symbol=f"{trade.symbol}_{side}",
                asset_class="OPTIONS",
                score=min(1.0, trade.score * 1.08),
                raw_score=min(1.0, trade.raw_score * 1.08),
                expected_move=option_move,
                cost=option_cost,
                net_edge=option_move - option_cost,
                direction=trade.direction,
                source=f"DERIVED_{trade.symbol}",
                volatility=min(1.0, trade.volatility * 1.20),
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
            direction = "LONG" if float(opp.get("momentum", 0.0)) >= 0 else "SHORT"

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
                    volatility=features["volatility"],
                )
            )

        except Exception as e:
            print(f"[WARN] {e}")

    trades.extend(build_option_candidates(trades))
    return trades


# ===============================
# EXECUTION / PNL ENGINE
# ===============================

class ExecutionPnLEngine:

    def position_size(self, balance: float, trade: Trade) -> float:

        asset_weight = ASSET_SIZE_WEIGHTS.get(trade.asset_class, 1.0)
        score_weight = max(0.5, min(1.0, trade.score))
        vol_damp = 1.0 / max(1.0, trade.volatility * 10.0)

        raw_size = balance * BASE_RISK_PER_TRADE * asset_weight * score_weight * vol_damp

        adjusted_size = max(1.25, raw_size)
        adjusted_size = min(adjusted_size, MAX_POSITION_SIZE_BY_ASSET.get(trade.asset_class, 5.0))

        return adjusted_size

    def simulate_outcome(self, trade: Trade) -> str:
        win_prob = min(0.75, max(0.45, trade.score))
        return "WIN" if random.random() < win_prob else "LOSS"

    def compute_pnl(self, size: float, trade: Trade, outcome: str) -> float:

        gross = size * trade.expected_move

        if trade.asset_class == "OPTIONS":
            gross *= 0.85

        if outcome == "WIN":
            gross *= WIN_MULTIPLIER
        else:
            gross *= -LOSS_MULTIPLIER

        friction = size * trade.cost
        return gross - friction
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

        grouped: Dict[str, List[Trade]] = {}
        for trade in trades:
            grouped.setdefault(trade.asset_class, []).append(trade)

        selected: List[Trade] = []

        for asset in RESERVED_ORDER:
            candidates = grouped.get(asset, [])
            candidates = sorted(candidates, key=lambda t: (t.score, t.net_edge), reverse=True)

            for trade in candidates:
                print(
                    f"\n{trade.symbol} | {trade.asset_class} | "
                    f"Raw: {round(trade.raw_score,4)} | "
                    f"Score: {round(trade.score,3)} | "
                    f"Edge: {round(trade.net_edge,4)} | "
                    f"Vol: {round(trade.volatility,4)} | "
                    f"Src: {trade.source}"
                )

                if self.edge_gate.passes(trade):

                    if trade.asset_class == "OPTIONS":
                        is_elite = trade.score >= OPTIONS_ELITE_SCORE and trade.net_edge >= ELITE_EDGE
                    else:
                        is_elite = trade.score >= ELITE_SCORE and trade.net_edge >= ELITE_EDGE

                    if is_elite:
                        print("PASS (ELITE SELECTED)")
                    else:
                        print("PASS (SELECTED)")

                    selected.append(trade)
                    break
                else:
                    print("REJECT")

        print("\n--- EXECUTION ---")

        cycle_pnl = 0.0
        asset_pnl: Dict[str, float] = {}
        asset_sizes: Dict[str, float] = {}

        for trade in selected:
            size = self.exec_engine.position_size(self.balance, trade)
            outcome = self.exec_engine.simulate_outcome(trade)
            pnl = self.exec_engine.compute_pnl(size, trade, outcome)

            cycle_pnl += pnl
            asset_pnl[trade.asset_class] = asset_pnl.get(trade.asset_class, 0.0) + pnl
            asset_sizes[trade.asset_class] = asset_sizes.get(trade.asset_class, 0.0) + size

            print(
                f"{trade.symbol} | {trade.asset_class} | "
                f"Size: {round(size,2)} | Outcome: {outcome} | PnL: {round(pnl,2)}"
            )

        self.balance += cycle_pnl

        print("\n--- SUMMARY ---")
        print(f"TRADES: {len(selected)}")
        print(f"CYCLE PnL: {round(cycle_pnl,2)}")
        print(f"BALANCE: {round(self.balance,2)}")

        if asset_sizes:
            print("\nASSET SIZE:")
            for asset, total_size in asset_sizes.items():
                print(f"{asset}: {round(total_size,2)}")

        if asset_pnl:
            print("\nASSET PnL:")
            for asset, pnl in asset_pnl.items():
                print(f"{asset}: {round(pnl,2)}")

    def run(self):
        print("\nCSS PHASE 9.1 — REFINED CAPITAL ALLOCATION MODE STARTED\n")

        while True:
            self.run_cycle()
            time.sleep(5)


if __name__ == "__main__":
    Dashboard().run()