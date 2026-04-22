from __future__ import annotations

import time
import random
from dataclasses import dataclass
from typing import List


# ===============================
# CONFIG (PHASE 4)
# ===============================

STARTING_BALANCE = 200.0
MAX_TRADES_PER_CYCLE = 4

COST_THRESHOLD = 0.015
MIN_SCORE_THRESHOLD = 0.55   # NEW: quality filter

RISK_PER_TRADE = 0.02        # 2% risk per trade
MAX_RISK_CAP = 0.10          # max 10% total exposure


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
# EXECUTION COST ENGINE
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

    return Trade(
        symbol, asset_class, score, expected_move, cost, net_edge, direction
    )


def scan_market() -> List[Trade]:
    return [generate_trade(a) for a in SYMBOLS.keys()]


# ===============================
# CAPITAL ENGINE (NEW PHASE 4)
# ===============================

class CapitalAllocator:

    def __init__(self):
        self.current_risk = 0.0

    def can_allocate(self, balance: float) -> bool:
        return self.current_risk < (balance * MAX_RISK_CAP)

    def allocate(self, balance: float) -> float:

        position_size = balance * RISK_PER_TRADE
        self.current_risk += position_size

        return position_size

    def reset_cycle(self):
        self.current_risk = 0.0
# ===============================
# DASHBOARD ENGINE
# ===============================

class Dashboard:

    def __init__(self):
        self.balance = STARTING_BALANCE
        self.cycle = 0
        self.edge_gate = EdgeGate()
        self.capital_engine = CapitalAllocator()

    def run_cycle(self):

        self.cycle += 1
        self.capital_engine.reset_cycle()

        print("\n" + "=" * 60)
        print(f"Cycle {self.cycle}")
        print("=" * 60)

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

            position_size = self.capital_engine.allocate(self.balance)

            outcome = random.choice(["WIN", "LOSS"])

            if outcome == "WIN":
                profit = position_size * trade.expected_move
            else:
                profit = -position_size * trade.expected_move

            pnl += profit
            trades_taken += 1

            print(f"\nTRADE: {trade.symbol}")
            print(f"Position Size: {round(position_size,2)}")
            print(f"Outcome: {outcome}")
            print(f"PnL: {round(profit,2)}")

        self.balance += pnl

        print("\n--- SUMMARY ---")
        print(f"Trades Taken: {trades_taken}")
        print(f"Cycle PnL: {round(pnl,2)}")
        print(f"Balance: {round(self.balance,2)}")

    def run(self):

        print("\nCSS PHASE 4 — CAPITAL CONTROL ENGINE STARTED\n")

        while True:
            self.run_cycle()
            time.sleep(3)


# ===============================
# ENTRY
# ===============================

if __name__ == "__main__":
    Dashboard().run()