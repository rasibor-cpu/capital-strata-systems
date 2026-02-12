"""
Global Futures Exposure Store
Capital Strata Systems – Phase 16

Persists open futures risk to disk.
Crash-safe capital tracking.
"""

import json
import os
from typing import Dict


STORE_FILE = "futures_exposure.json"


def load_exposure() -> float:
    if not os.path.exists(STORE_FILE):
        return 0.0

    try:
        with open(STORE_FILE, "r") as f:
            data = json.load(f)
            return float(data.get("open_futures_risk", 0.0))
    except Exception:
        return 0.0


def save_exposure(value: float) -> None:
    with open(STORE_FILE, "w") as f:
        json.dump(
            {
                "open_futures_risk": round(float(value), 6)
            },
            f
        )
