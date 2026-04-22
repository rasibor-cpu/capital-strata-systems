from __future__ import annotations

import time
from dataclasses import dataclass
from typing import List, Dict, Any


# ===============================
# CONFIG
# ===============================

STARTING_BALANCE = 200.0

# selection cap
MAX_SELECTED = 3

# elite filter
ELITE_SCORE = 0.55
ELITE_EDGE = 0.007

# asset rules
ASSET_RULES = {
    "CRYPTO":  {"min_score": 0.25, "min_edge": 0.005},
    "FX":      {"min_score": 0.28, "min_edge": 0.005},
    "FUTURES": {"min_score": 0.32, "min_edge": 0.007},
    "OPTIONS": {"min_score": 0.40, "min_edge": 0.010},
}

# pnl / execution controls
BASE_RISK_PER_TRADE = 0.02
WIN_SCORE_THRESHOLD = 0.45
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


# ===============================
# COST ENGINE
# ===============================

class ExecutionCostEngine:

    def estimate_cost(self, asset_class: str) -> float:

        if asset_class == "CRYPTO":
            return 0.005
        elif asset_class == "FX":
            return 0.0025
        elif asset_class == "FUTURES":
            return 0.0035
        elif asset_class == "OPTIONS":
            return 0.006

        return 0.005


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
        min(
            0.15,
            abs(momentum) * 0.5 + volatility * 0.3
        )
    )

    return {
        "momentum": momentum,
        "volatility": volatility,
        "expected_move": expected_move,
    }


# ===============================
# SCORE NORMALIZATION
# ===============================

def normalize_score(raw_score: float) -> float:
    scaled = raw_score * 50.0
    return max(0.0, min(1.0, scaled))


# ===============================
# MARKET SCAN
# ===============================

def scan_market() -> List[Trade]:

    scanner = UnifiedMarketScanner()
    opportunities = list(scanner.scan())

    trades: List[Trade] = []
    ai_engine = AIOpportunityScorer()

    raw_scores: List[float] = []

    for opp in opportunities:

        try:
            symbol = opp.get("symbol", "UNKNOWN")
            asset_class = opp.get("asset_class", "CRYPTO")

            features = extract_features(opp)

            if hasattr(ai_engine, "score"):
                raw_score = float(ai_engine.score(features))
            else:
                raw_score = 0.02

            score = normalize_score(raw_score)
            raw_scores.append(raw_score)

            expected_move = features["expected_move"]
            cost = ExecutionCostEngine().estimate_cost(asset_class)

            trades.append(
                Trade(
                    symbol=symbol,
                    asset_class=asset_class,
                    score=score,
                    raw_score=raw_score,
                    expected_move=expected_move,
                    cost=cost,
                    net_edge=expected_move - cost,
                    direction="LONG",
                )
            )

        except Exception as e:
            print(f"[WARN] Skipping {opp.get('symbol','?')} | {e}")

    if raw_scores:
        print(f"\n[SCORER RANGE] min={min(raw_scores):.4f} max={max(raw_scores):.4f}")

    return trades


# ===============================
# EXECUTION / PNL ENGINE
# ===============================

class ExecutionPnLEngine:

    def position_size(self, balance: float, trade: Trade) -> float:
        score_weight = max(0.5, min(trade.score, 1.0))
        return balance * BASE_RISK_PER_TRADE * score_weight

    def simulate_outcome(self, trade: Trade) -> str:
        return "WIN" if trade.score >= WIN_SCORE_THRESHOLD else "LOSS"

    def compute_pnl(self, size: float, trade: Trade, outcome: str) -> float:

        gross_move = size * trade.expected_move

        if outcome == "WIN":
            gross = gross_move * WIN_MULTIPLIER
        else:
            gross = -gross_move * LOSS_MULTIPLIER

        # apply estimated transaction friction once more at execution layer
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

        trades = sorted(
            trades,
            key=lambda t: (t.score, t.net_edge),
            reverse=True
        )

        selected_trades: List[Trade] = []
        class_counts: Dict[str, int] = {}

        for trade in trades:

            print(
                f"\n{trade.symbol} | {trade.asset_class} | "
                f"Raw: {round(trade.raw_score,4)} | "
                f"Score: {round(trade.score,3)} | "
                f"Edge: {round(trade.net_edge,4)}"
            )

            if self.edge_gate.passes(trade):

                is_elite = (
                    trade.score >= ELITE_SCORE
                    and trade.net_edge >= ELITE_EDGE
                )

                if len(selected_trades) < MAX_SELECTED:
                    if is_elite:
                        print("PASS (ELITE SELECTED)")
                    else:
                        print("PASS (SELECTED)")

                    selected_trades.append(trade)
                    class_counts[trade.asset_class] = class_counts.get(trade.asset_class, 0) + 1
                else:
                    print("PASS (SKIPPED - LIMIT)")
            else:
                print("REJECT")

        print("\n--- EXECUTION ---")

        cycle_pnl = 0.0
        asset_pnl: Dict[str, float] = {}

        for trade in selected_trades:

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

        print("\n--- SUMMARY ---")
        print(f"TOTAL SELECTED: {len(selected_trades)}")
        print(f"SELECTION LIMIT: {MAX_SELECTED}")

        if class_counts:
            for asset_class, count in class_counts.items():
                print(f"{asset_class}: {count}")
        else:
            print("No trades selected.")

        print(f"\nCYCLE PnL: {round(cycle_pnl,2)}")
        print(f"BALANCE: {round(self.balance,2)}")

        if asset_pnl:
            print("\nASSET PnL:")
            for asset_class, pnl in asset_pnl.items():
                print(f"{asset_class}: {round(pnl,2)}")

    def run(self):

        print("\nCSS PHASE 8 — EXECUTION + PNL MODE STARTED\n")

        while True:
            self.run_cycle()
            time.sleep(5)


if __name__ == "__main__":
    Dashboard().run()