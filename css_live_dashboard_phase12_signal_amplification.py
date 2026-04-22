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
LOSS_MULTIPLIER = 0.8

TILT_SCALER = 80.0
MIN_TILT = 0.92
MAX_TILT = 1.08

# Phase 12 amplification
EDGE_AMPLIFICATION = 1.0
SCORE_EDGE_COUPLING = 1.0
EDGE_CONVEXITY = 1.25


from backend.scanner.unified_market_scanner import UnifiedMarketScanner
from backend.intelligence.ai_opportunity_scorer import AIOpportunityScorer


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


class PerformanceMemory:

    def __init__(self):
        self.history = {k: [] for k in ["FX", "CRYPTO", "FUTURES", "OPTIONS"]}
        self.window = 10
        self.balance = STARTING_BALANCE

    def update(self, asset_pnl: Dict[str, float], balance: float):
        self.balance = balance
        for k, v in asset_pnl.items():
            self.history[k].append(v)
            if len(self.history[k]) > self.window:
                self.history[k].pop(0)

    def get_tilt(self) -> Dict[str, float]:
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


class RegimeEngine:

    def evaluate_asset(self, asset: str, trades: List[Trade]) -> Dict[str, Any]:

        if not trades:
            return {"asset": asset, "state": "WEAK", "score": 0.0}

        avg_score = sum(t.score for t in trades) / len(trades)
        avg_edge = sum(t.net_edge for t in trades) / len(trades)

        rules = ASSET_RULES[asset]
        passing = [t for t in trades if t.score >= rules["min_score"] and t.net_edge >= rules["min_edge"]]
        pass_rate = len(passing) / len(trades)

        regime_score = (
            (avg_score * 0.50) +
            (avg_edge * 50 * 0.40) +
            (pass_rate * 0.10)
        )

        # Phase 12.1 relaxed thresholds
        if regime_score >= 0.65:
            state = "STRONG"
        elif regime_score >= 0.40:
            state = "NEUTRAL"
        else:
            state = "WEAK"

        return {
            "asset": asset,
            "state": state,
            "score": round(regime_score, 3),
            "avg_edge": round(avg_edge, 4),
        }
def extract_features(opp: Dict[str, Any]) -> Dict[str, float]:

    m = float(opp.get("momentum", 0.0))
    v = float(opp.get("volatility", 0.01))

    move = max(0.01, min(0.15, abs(m) * 0.5 + v * 0.3))

    return {"momentum": m, "volatility": v, "expected_move": move}


def normalize_score(raw: float) -> float:
    return max(0.0, min(1.0, raw * 50.0))


def amplify_edge(raw_edge: float, score: float) -> float:
    coupled = raw_edge * (1.0 + score * SCORE_EDGE_COUPLING)
    convex = abs(coupled) ** EDGE_CONVEXITY
    convex = convex if coupled >= 0 else -convex
    amplified = convex * EDGE_AMPLIFICATION
    return amplified


def scan_market() -> List[Trade]:

    scanner = UnifiedMarketScanner()
    ai = AIOpportunityScorer()

    trades: List[Trade] = []

    for opp in scanner.scan():

        f = extract_features(opp)

        raw = float(ai.score(f))
        score = normalize_score(raw)

        asset_class = opp.get("asset_class", "CRYPTO")

        cost = {
            "CRYPTO": 0.005,
            "FX": 0.0025,
            "FUTURES": 0.0035,
            "OPTIONS": 0.006,
        }.get(asset_class, 0.005)

        raw_edge = f["expected_move"] - cost
        net_edge = amplify_edge(raw_edge, score)

        trades.append(
            Trade(
                symbol=opp.get("symbol"),
                asset_class=asset_class,
                score=score,
                raw_score=raw,
                expected_move=f["expected_move"],
                cost=cost,
                net_edge=net_edge,
                direction="LONG" if f["momentum"] >= 0 else "SHORT",
                source="SCANNER",
                volatility=f["volatility"],
            )
        )

    return trades
class ExecutionEngine:

    def __init__(self, memory: PerformanceMemory):
        self.memory = memory

    def regime_factor(self, regime_state: str, trade: Trade) -> float:

        if regime_state == "STRONG":
            return 1.0

        elif regime_state == "NEUTRAL":
            edge_strength = min(1.0, trade.net_edge / 0.02)
            return 0.55 + (edge_strength * 0.35)

        else:
            return 0.0

    def size(self, bal: float, trade: Trade, regime_state: str) -> float:

        tilt = self.memory.get_tilt()

        base_weight = BASE_ASSET_WEIGHTS.get(trade.asset_class, 1.0)
        adjusted_weight = base_weight * tilt.get(trade.asset_class, 1.0)

        score_w = max(0.5, min(1.0, trade.score))
        vol_adj = 1.0 / max(1.0, trade.volatility * 10)

        regime_factor = self.regime_factor(regime_state, trade)

        s = bal * BASE_RISK_PER_TRADE * adjusted_weight * score_w * vol_adj * regime_factor

        if regime_factor > 0:
            s = max(1.25, s)

        return min(s, MAX_POSITION_SIZE_BY_ASSET.get(trade.asset_class, 5.0))

    def outcome(self, trade: Trade) -> str:
        return "WIN" if random.random() < trade.score else "LOSS"

    def pnl(self, size: float, trade: Trade, out: str) -> float:
        g = size * trade.expected_move
        if out == "LOSS":
            g *= -LOSS_MULTIPLIER
        return g - size * trade.cost


class Dashboard:

    def __init__(self):
        self.balance = STARTING_BALANCE
        self.memory = PerformanceMemory()
        self.exec = ExecutionEngine(self.memory)

    def run(self):

        print("\nCSS PHASE 12.1 — RELAXED REGIME ACTIVE\n")

        regime_engine = RegimeEngine()

        while True:

            trades = scan_market()

            grouped: Dict[str, List[Trade]] = {}
            for t in trades:
                grouped.setdefault(t.asset_class, []).append(t)

            print("\n--- REGIMES ---")

            regime_map = {}
            for asset in RESERVED_ORDER:
                reg = regime_engine.evaluate_asset(asset, grouped.get(asset, []))
                regime_map[asset] = reg
                print(asset, reg)

            print("\n--- EXECUTION ---")

            pnl_total = 0.0
            asset_pnl = {}

            for asset in RESERVED_ORDER:

                reg = regime_map[asset]

                if reg["state"] == "WEAK":
                    print("Skipping", asset)
                    continue

                candidates = sorted(
                    grouped.get(asset, []),
                    key=lambda x: (x.score, x.net_edge),
                    reverse=True
                )

                if not candidates:
                    continue

                t = candidates[0]

                size = self.exec.size(self.balance, t, reg["state"])
                out = self.exec.outcome(t)
                pnl = self.exec.pnl(size, t, out)

                pnl_total += pnl
                asset_pnl[asset] = pnl

                print(f"{t.symbol} | {asset} | Regime: {reg['state']} | Size: {round(size,2)} | {out} | PnL: {round(pnl,2)}")

            self.balance += pnl_total
            self.memory.update(asset_pnl, self.balance)

            print("\nBAL:", round(self.balance, 2))
            print("PnL:", round(pnl_total, 2))
            print("TILT:", self.memory.get_tilt())

            time.sleep(5)


if __name__ == "__main__":
    Dashboard().run()