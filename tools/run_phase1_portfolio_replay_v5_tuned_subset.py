"""
Phase 1 – Portfolio Replay V5 (TUNED SUBSET HARNESS)

Purpose:
- Run controlled subset of instruments
- Cap number of bars per instrument
- Override MIN_STRENGTH / MAX_R_MULTIPLIER at runtime
- No modification to production runner

Usage:
    python tools/run_phase1_portfolio_replay_v5_tuned_subset.py
"""

from __future__ import annotations

import importlib
from pathlib import Path

# -------------------------
# TUNING CONTROLS
# -------------------------

MIN_STRENGTH_OVERRIDE = 0.72
MAX_R_MULTIPLIER_OVERRIDE = 2.5

MAX_INSTRUMENTS = 4
MAX_BARS_PER_INST = 5000

# -------------------------
# Load Production Module
# -------------------------

m = importlib.import_module(
    "tools.run_phase1_portfolio_replay_v5_convexity_trim_rvol"
)

# Override parameters safely
m.MIN_STRENGTH = MIN_STRENGTH_OVERRIDE
m.MAX_R_MULTIPLIER = MAX_R_MULTIPLIER_OVERRIDE

original_loader = m.load_all_data


def capped_loader():
    datasets = original_loader()

    # Limit instruments
    keys = sorted(datasets.keys())[:MAX_INSTRUMENTS]
    datasets = {k: datasets[k] for k in keys}

    # Cap bars
    for k in datasets:
        if MAX_BARS_PER_INST and len(datasets[k]) > MAX_BARS_PER_INST:
            datasets[k] = datasets[k][:MAX_BARS_PER_INST]

    return datasets


m.load_all_data = capped_loader

print("\n===== PHASE 1 V5 – TUNED SUBSET RUN =====")
print("MIN_STRENGTH:", m.MIN_STRENGTH)
print("MAX_R_MULTIPLIER:", m.MAX_R_MULTIPLIER)
print("MAX_INSTRUMENTS:", MAX_INSTRUMENTS)
print("MAX_BARS_PER_INST:", MAX_BARS_PER_INST)

m.main()