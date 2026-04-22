from __future__ import annotations

import time
import random
from dataclasses import dataclass
from typing import List


# ===============================
# CONFIG
# ===============================

STARTING_BALANCE = 200.0
MAX_TRADES_PER_CYCLE = 4

COST_THRESHOLD = 0.015
BASE_MIN_SCORE = 0.55

BASE_RISK_PER_TRADE = 0.02
MAX_RISK_CAP = 0.10

WIN_STREAK_BOOST = 1.2
LOSS_STREAK_CUT = 0.7
MAX_CONSECUTIVE_LOSSES = 3

COOLDOWN_CYCLES = 2
RECOVERY_RISK_FACTOR = 0.5
RISK_RAMP_STEP = 0.25


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

    def __init__(self):
        self.dynamic_score_threshold = BASE_MIN_SCORE

    def adjust_after_losses(self, loss_streak: int):
        if loss_streak >= 2:
            self.dynamic_score_threshold = BASE_MIN_SCORE + 0.05
        else:
            self.dynamic_score_threshold = BASE_MIN_SCORE

    def passes(self, trade: Trade) -> bool:
        return (
            trade.net_edge >= COST_THRESHOLD
            and trade.score >= self.dynamic_score_threshold
        )


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
# RECOVERY ENGINE (FIXED)
# ===============================

class RecoveryCapitalAllocator:

    def __init__(self):
        self.current_risk = 0.0
        self.win_streak = 0
        self.loss_streak = 0

        self.cooldown_remaining = 0
        self.recovery_mode = False
        self.risk_scale = 1.0

    def reset_cycle(self):
        self.current_risk = 0.0

    def update_after_trade(self, outcome: str):

        if outcome == "WIN":
            self.win_streak += 1
            self.loss_streak = 0
        else:
            self.loss_streak += 1
            self.win_streak = 0

        if self.loss_streak >= MAX_CONSECUTIVE_LOSSES:
            self.cooldown_remaining = COOLDOWN_CYCLES
            self.recovery_mode = True
            self.risk_scale = RECOVERY_RISK_FACTOR

    def process_cycle_state(self):

        if self.cooldown_remaining > 0:
            self.cooldown_remaining -= 1
            return "COOLDOWN"

        if self.recovery_mode:

            # 🔥 CRITICAL FIX
            if self.loss_streak >= MAX_CONSECUTIVE_LOSSES:
                self.loss_streak = 1

            self.risk_scale = min(1.0, self.risk_scale + RISK_RAMP_STEP)

            if self.risk_scale >= 1.0:
                self.recovery_mode = False

            return "RECOVERY"

        return "NORMAL"

    def get_risk_multiplier(self):

        # 🔥 FIX: allow trading during recovery
        if not self.recovery_mode and self.loss_streak >= MAX_CONSECUTIVE_LOSSES:
            return 0.0

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

        score_weight = max(0.5, min(score, 1.0))

        position_size = (
            balance
            * BASE_RISK_PER_TRADE
            * multiplier
            * score_weight
            * self.risk_scale
        )

        self.current_risk += position_size

        return position_size
# ===============================
# DASHBOARD
# ===============================

class Dashboard:

    def __init__(self):
        self.balance = STARTING_BALANCE
        self.cycle = 0

        self.edge_gate = EdgeGate()
        self.capital_engine = RecoveryCapitalAllocator()

    def run_cycle(self):

        self.cycle += 1
        self.capital_engine.reset_cycle()

        state = self.capital_engine.process_cycle_state()
        self.edge_gate.adjust_after_losses(self.capital_engine.loss_streak)

        print("\n" + "=" * 60)
        print(f"Cycle {self.cycle}")
        print("=" * 60)

        print(f"STATE: {state}")
        print(f"Win: {self.capital_engine.win_streak} | Loss: {self.capital_engine.loss_streak}")
        print(f"Risk Scale: {round(self.capital_engine.risk_scale,2)}")

        trades = scan_market()
        selected_trades = []

        for trade in trades:

            print(f"\n{trade.asset_class} | {trade.symbol}")
            print(f"Score: {trade.score}")
            print(f"Edge: {trade.net_edge}")

            if self.edge_gate.passes(trade):
                print("PASS")
                selected_trades.append(trade)
            else:
                print("REJECT")

        if state == "COOLDOWN":
            print("⛔ COOLDOWN ACTIVE - NO TRADING")
            return

        pnl = 0
        trades_taken = 0

        for trade in selected_trades:

            if trades_taken >= MAX_TRADES_PER_CYCLE:
                break

            if not self.capital_engine.can_allocate(self.balance):
                break

            position_size = self.capital_engine.allocate(self.balance, trade.score)

            if position_size == 0:
                print("⛔ KILL SWITCH")
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
            print(f"Size: {round(position_size,2)} | Outcome: {outcome} | PnL: {round(profit,2)}")

        self.balance += pnl

        print("\n--- SUMMARY ---")
        print(f"Trades: {trades_taken}")
        print(f"PnL: {round(pnl,2)}")
        print(f"Balance: {round(self.balance,2)}")

    def run(self):

        print("\nCSS PHASE 6.1 — RECOVERY FIXED ENGINE STARTED\n")

        while True:
            self.run_cycle()
            time.sleep(3)


if __name__ == "__main__":
    Dashboard().run()