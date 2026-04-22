from __future__ import annotations

import time
import random
from dataclasses import dataclass
from typing import List


# ===============================
# CONFIG (PHASE 5)
# ===============================

STARTING_BALANCE = 200.0
MAX_TRADES_PER_CYCLE = 4

COST_THRESHOLD = 0.015
MIN_SCORE_THRESHOLD = 0.55

BASE_RISK_PER_TRADE = 0.02
MAX_RISK_CAP = 0.10

# Adaptive controls
WIN_STREAK_BOOST = 1.2
LOSS_STREAK_CUT = 0.7
MAX_CONSECUTIVE_LOSSES = 3   # kill switch trigger


# ===============================
# DATA STRUCTURES
# ===============================

@dataclass
class Trade:
    symbol: str
    asset_class: str
    score: float
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
        return trade.net_edge >= COST_THRESHOLD and trade.score >= MIN_SCORE_THRESHOLD
# ===============================
# MARKET SIMULATION
# ===============================

SYMBOLS = {
    "CRYPTO": ["BTC-USD", "ETH-USD"],
    "FX": ["EURUSD", "GBPUSD"],
    "FUTURES": ["ES", "NQ"],
    "OPTIONS": ["SPY_CALL", "QQQ_PUT"]
}


def generate_trade(asset_class: str) -> Trade:

    symbol = random.choice(SYMBOLS[asset_class])
    score = round(random.uniform(0.3, 0.9), 3)
    expected_move = round(random.uniform(0.01, 0.05), 4)
    direction = random.choice(["LONG", "SHORT"])

    cost = ExecutionCostEngine().estimate_cost(asset_class)
    net_edge = expected_move - cost

    return Trade(symbol, asset_class, score, expected_move, cost, net_edge, direction)


def scan_market() -> List[Trade]:
    return [generate_trade(a) for a in SYMBOLS.keys()]


# ===============================
# ADAPTIVE CAPITAL ENGINE
# ===============================

class AdaptiveCapitalAllocator:

    def __init__(self):
        self.current_risk = 0.0
        self.win_streak = 0
        self.loss_streak = 0

    def reset_cycle(self):
        self.current_risk = 0.0

    def update_after_trade(self, outcome: str):

        if outcome == "WIN":
            self.win_streak += 1
            self.loss_streak = 0
        else:
            self.loss_streak += 1
            self.win_streak = 0

    def get_risk_multiplier(self):

        if self.loss_streak >= MAX_CONSECUTIVE_LOSSES:
            return 0.0   # kill switch

        if self.win_streak >= 2:
            return WIN_STREAK_BOOST

        if self.loss_streak >= 2:
            return LOSS_STREAK_CUT

        return 1.0

    def can_allocate(self, balance: float) -> bool:
        return self.current_risk < (balance * MAX_RISK_CAP)

    def allocate(self, balance: float, score: float) -> float:

        multiplier = self.get_risk_multiplier()

        if multiplier == 0.0:
            return 0.0

        # Score-weighted sizing
        score_weight = max(0.5, min(score, 1.0))

        position_size = balance * BASE_RISK_PER_TRADE * multiplier * score_weight

        self.current_risk += position_size

        return position_size
# ===============================
# DASHBOARD ENGINE
# ===============================

class Dashboard:

    def __init__(self):
        self.balance = STARTING_BALANCE
        self.cycle = 0
        self.edge_gate = EdgeGate()
        self.capital_engine = AdaptiveCapitalAllocator()

    def run_cycle(self):

        self.cycle += 1
        self.capital_engine.reset_cycle()

        print("\n" + "=" * 60)
        print(f"Cycle {self.cycle}")
        print("=" * 60)

        print(f"Win Streak: {self.capital_engine.win_streak} | Loss Streak: {self.capital_engine.loss_streak}")

        trades = scan_market()
        selected_trades = []

        for trade in trades:

            print(f"\n{trade.asset_class} | {trade.symbol}")
            print(f"Score: {trade.score}")
            print(f"Expected Move: {trade.expected_move}")
            print(f"Cost: {trade.cost}")
            print(f"Net Edge: {trade.net_edge}")

            if self.edge_gate.passes(trade):
                print("PASS")
                selected_trades.append(trade)
            else:
                print("REJECT")

        pnl = 0
        trades_taken = 0

        for trade in selected_trades:

            if trades_taken >= MAX_TRADES_PER_CYCLE:
                break

            if not self.capital_engine.can_allocate(self.balance):
                print("⚠ Risk cap reached")
                break

            position_size = self.capital_engine.allocate(self.balance, trade.score)

            if position_size == 0:
                print("⛔ KILL SWITCH ACTIVE - SKIPPING TRADES")
                break

            outcome = random.choice(["WIN", "LOSS"])

            if outcome == "WIN":
                profit = position_size * trade.expected_move
            else:
                profit = -position_size * trade.expected_move

            pnl += profit
            trades_taken += 1

            self.capital_engine.update_after_trade(outcome)

            print(f"\nTRADE: {trade.symbol}")
            print(f"Score Weight: {round(trade.score,2)}")
            print(f"Position Size: {round(position_size,2)}")
            print(f"Outcome: {outcome}")
            print(f"PnL: {round(profit,2)}")

        self.balance += pnl

        print("\n--- SUMMARY ---")
        print(f"Trades Taken: {trades_taken}")
        print(f"Cycle PnL: {round(pnl,2)}")
        print(f"Balance: {round(self.balance,2)}")

    def run(self):

        print("\nCSS PHASE 5 — ADAPTIVE ENGINE STARTED\n")

        while True:
            self.run_cycle()
            time.sleep(3)


# ===============================
# ENTRY
# ===============================

if __name__ == "__main__":
    Dashboard().run()