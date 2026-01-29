from __future__ import annotations

"""
Execution Simulator — Registry-Wired, Persistent Metrics

Purpose:
- Central execution + accounting layer
- Receives decisions from rea_engine_personal.py
- Tracks per-instrument accuracy, wins/losses, abstentions
- Persists metrics to disk
- Produces a human-readable report

NO BROKER CONNECTION
NO AUTO-EXECUTION
"""

import json
import os
from datetime import datetime
from typing import Dict

import instrument_registry as ir

# -------------------------------------------------
# Storage
# -------------------------------------------------

METRICS_FILE = "out/metrics.json"


def _empty_metrics() -> Dict[str, Dict[str, int]]:
    metrics = {}
    for sym in ir.list_instruments():
        metrics[sym] = {
            "signals": 0,
            "wins": 0,
            "losses": 0,
            "no_trade": 0,
        }
    return metrics


def load_metrics() -> Dict[str, Dict[str, int]]:
    if not os.path.exists(METRICS_FILE):
        return _empty_metrics()

    with open(METRICS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_metrics(metrics: Dict[str, Dict[str, int]]) -> None:
    os.makedirs("out", exist_ok=True)
    with open(METRICS_FILE, "w", encoding="utf-8") as f:
        json.dump(metrics, f, indent=2)


# -------------------------------------------------
# Recording outcomes
# -------------------------------------------------

def record_no_trade(symbol: str) -> None:
    metrics = load_metrics()
    metrics.setdefault(symbol, _empty_metrics().get(symbol, {}))
    metrics[symbol]["no_trade"] += 1
    save_metrics(metrics)


def record_trade(symbol: str, win: bool) -> None:
    metrics = load_metrics()
    metrics.setdefault(symbol, _empty_metrics().get(symbol, {}))

    metrics[symbol]["signals"] += 1
    if win:
        metrics[symbol]["wins"] += 1
    else:
        metrics[symbol]["losses"] += 1

    save_metrics(metrics)


# -------------------------------------------------
# Reporting
# -------------------------------------------------

def generate_report() -> str:
    metrics = load_metrics()
    lines = []
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    lines.append("=" * 72)
    lines.append("REA ENGINE — PERFORMANCE REPORT")
    lines.append(f"Generated: {ts}")
    lines.append("=" * 72)

    for sym, m in metrics.items():
        signals = m["signals"]
        wins = m["wins"]
        losses = m["losses"]
        no_trade = m["no_trade"]

        accuracy = (wins / signals * 100.0) if signals > 0 else 0.0

        lines.append(f"\nInstrument: {sym}")
        lines.append(f"  Signals:   {signals}")
        lines.append(f"  Wins:      {wins}")
        lines.append(f"  Losses:    {losses}")
        lines.append(f"  No-Trade:  {no_trade}")
        lines.append(f"  Accuracy:  {accuracy:.2f}%")

    lines.append("\n" + "=" * 72)
    return "\n".join(lines)


def print_report() -> None:
    print(generate_report())


# -------------------------------------------------
# CLI entry
# -------------------------------------------------

if __name__ == "__main__":
    print_report()