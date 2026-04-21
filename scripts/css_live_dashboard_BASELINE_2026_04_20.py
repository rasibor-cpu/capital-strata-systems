from __future__ import annotations

import time
import random
from dataclasses import dataclass
from typing import Dict, List


# ===============================
# CONFIG
# ===============================

STARTING_BALANCE = 200.0
MAX_TRADES_PER_CYCLE = 4

COST_THRESHOLD = 0.015  # Minimum net edge required


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
            spread = 0.002
            slippage = 0.002
            fees = 0.001

        elif asset_class == "FX":
            spread = 0.001
            slippage = 0.001
            fees = 0.0005

        elif asset_class == "FUTURES":
            spread = 0.0015
            slippage = 0.0015
            fees = 0.0005

        elif asset_class == "OPTIONS":
            spread = 0.003
            slippage = 0.002
            fees = 0.001

        else:
            spread = 0.002
            slippage = 0.002
            fees = 0.001

        return spread + slippage + fees


# ===============================
# EDGE GATE (NEW PHASE 3)
# ===============================

class EdgeGate:

    def __init__(self, threshold: float):
        self.threshold = threshold

    def passes(self, trade: Trade) -> bool:
        return trade.net_edge >= self.threshold
# ===============================
# MARKET SIMULATION (NON-REGRESSIVE SAFE)
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

    cost_engine = ExecutionCostEngine()
    cost = cost_engine.estimate_cost(asset_class)

    net_edge = expected_move - cost

    return Trade(
        symbol=symbol,
        asset_class=asset_class,
        score=score,
        expected_move=expected_move,
        cost=cost,
        net_edge=net_edge,
        direction=direction
    )


def scan_market() -> List[Trade]:

    trades = []

    for asset_class in SYMBOLS.keys():
        trade = generate_trade(asset_class)
        trades.append(trade)

    return trades
# ===============================
# DASHBOARD ENGINE
# ===============================

class Dashboard:

    def __init__(self):
        self.balance = STARTING_BALANCE
        self.cycle = 0
        self.edge_gate = EdgeGate(COST_THRESHOLD)

    def run_cycle(self):

        self.cycle += 1

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
                print("✅ PASSED EDGE GATE")
                selected_trades.append(trade)
            else:
                print("❌ REJECTED (LOW EDGE)")

        selected_trades = selected_trades[:MAX_TRADES_PER_CYCLE]

        pnl = 0

        for trade in selected_trades:

            outcome = random.choice(["WIN", "LOSS"])

            if outcome == "WIN":
                profit = trade.expected_move * 100
            else:
                profit = -trade.expected_move * 100

            pnl += profit

            print(f"\nTRADE RESULT: {trade.symbol} -> {outcome} | PnL: {round(profit,2)}")

        self.balance += pnl

        print("\n--- SUMMARY ---")
        print(f"Trades Taken: {len(selected_trades)}")
        print(f"Cycle PnL: {round(pnl,2)}")
        print(f"Balance: {round(self.balance,2)}")

    def run(self):

        print("\n🚀 CSS PHASE 3 — EDGE-GATED DASHBOARD STARTED\n")

        while True:
            self.run_cycle()
            time.sleep(3)


# ===============================
# ENTRY POINT
# ===============================

if __name__ == "__main__":

    dashboard = Dashboard()
    dashboard.run()