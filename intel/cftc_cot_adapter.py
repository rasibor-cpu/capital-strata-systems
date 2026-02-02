"""
CFTC COT Adapter (DEMO MODE)
----------------------------
Weekly positioning / crowding intelligence (macro risk layer).

This version runs in DEMO mode (no live CSV download yet) to validate:
- Correct imports
- Correct IntelEnvelope construction
- Correct crowding/pressure logic

Next iteration will add real CFTC fetch + parse.
"""

from __future__ import annotations

import os
import sys
from datetime import datetime, timezone
from statistics import mean, stdev

# --- REPO ROOT BOOTSTRAP (so "python intel\\cftc_cot_adapter.py" works) ---
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

# Correct import location (intel/intel_envelope.py)
from intel.intel_envelope import IntelEnvelope


CONTRACT_MAP = {
    "S&P 500": "EQUITY",
    "EURO FX": "FX",
    "JAPANESE YEN": "FX",
    "BRITISH POUND": "FX",
    "GOLD": "COMMODITY",
    "CRUDE OIL, LIGHT SWEET": "COMMODITY",
}


def compute_crowding_z(net_positions):
    """
    Simple z-score crowding estimator on net positions.
    """
    if len(net_positions) < 5:
        return 0.0

    mu = mean(net_positions)
    sd = stdev(net_positions)
    if sd == 0:
        return 0.0

    return (net_positions[-1] - mu) / sd


def cot_record_to_envelope(contract: str, net_positions) -> IntelEnvelope:
    z = compute_crowding_z(net_positions)

    # Normalize to [0..1]
    pressure = min(abs(z) / 3.0, 1.0)

    direction = "crowded-long" if z > 0 else "crowded-short"
    scope = CONTRACT_MAP.get(contract, "GLOBAL")

    raw = {
        "contract": contract,
        "net_positions": net_positions,
        "z_score": round(z, 3),
        "direction": direction,
        "frequency": "weekly",
        "source_quality": "official",
    }

    return IntelEnvelope.create(
        provider="cftc",
        intel_type="positioning",
        signal_class="crowding",
        instrument_scope=scope,
        raw=raw,
        confidence=0.60,
        severity=round(pressure, 3),
        rea_instrument=None,
    )


def run_demo():
    # DEMO net positions (oldest->newest)
    sample_net_positions = [-12000, -8000, -4000, 2000, 9000, 15000]
    env = cot_record_to_envelope("S&P 500", sample_net_positions)

    print("CFTC_COT_OK")
    print(env)
    return env


if __name__ == "__main__":
    run_demo()
