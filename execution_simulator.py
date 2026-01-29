from __future__ import annotations
"""
Execution Simulator — Non-Broker Adapter (LOCKED)

Purpose:
- Consume engine signals
- Simulate trade outcome deterministically
- Track per-instrument performance
- Persist metrics safely (JSON)

This file NEVER talks to a broker.
"""

import json
import os
from dataclasses import dataclass
from typing import Dict


METRICS_PATH = "data/metrics.json"


@dataclass
class TradeResult:
    symbol: str
    side: str
    win: bool


# -------------------------
# Metrics persistence
# -------------------------

def load_metrics() -> Dict[str, Dict[str, float]]:
    if not os.path.exists("data"):
        os.makedirs("data")

    if not os.path.exists(METRICS_PATH):
        return {}

    with open(METRICS_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def save_metrics(metrics: Dict[str, Dict[str, float]]) -> None:
    with open(METRICS_PATH, "w", encoding="utf-8") as f:
        json.dump(metrics, f, indent=2)


# -------------------------
# Simulation logic
# -------------------------

def simulate_trade(result: TradeResult) -> None:
    """
    Deterministic simulation:
    - BUY wins if win=True
    - SELL wins if win=True
    """

    metrics = load_metrics()

    sym = result.symbol
    if sym not in metrics:
        metrics[sym] = {
            "trades": 0,
            "wins": 0,
            "losses": 0,
            "accuracy": 0.0,
        }

    metrics[sym]["trades"] += 1

    if result.win:
        metrics[sym]["wins"] += 1
    else:
        metrics[sym]["losses"] += 1

    trades = metrics[sym]["trades"]
    wins = metrics[sym]["wins"]
    metrics[sym]["accuracy"] = round(wins / trades, 4)

    save_metrics(metrics)


# -------------------------
# Report helper
# -------------------------

def print_report() -> None:
    metrics = load_metrics()

    if not metrics:
        print("No trades recorded yet.")
        return

    print("\nPER-INSTRUMENT PERFORMANCE")
    print("-" * 40)
    for sym, m in metrics.items():
        print(
            f"{sym:7} | trades={m['trades']:3} "
            f"wins={m['wins']:3} "
            f"losses={m['losses']:3} "
            f"accuracy={m['accuracy']:.2%}"
        )
    print("-" * 40)


# -------------------------
# Manual test
# -------------------------

if __name__ == "__main__":
    simulate_trade(TradeResult("EURUSD", "buy", True))
    simulate_trade(TradeResult("EURUSD", "sell", False))
    simulate_trade(TradeResult("USDJPY", "buy", True))
    print_report()