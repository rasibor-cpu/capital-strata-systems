"""
Global Futures Exposure Store
Capital Strata Systems – Phase 16 (Hardened)

Enhancements:
- deterministic file path
- atomic writes (no corruption risk)
- backward compatible interface
"""

import json
import os
from typing import Dict

# -----------------------------------------------------
# Deterministic storage path (project-safe)
# -----------------------------------------------------

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STORE_FILE = os.path.join(BASE_DIR, "futures_exposure.json")


# -----------------------------------------------------
# Load exposure
# -----------------------------------------------------

def load_exposure() -> float:
    if not os.path.exists(STORE_FILE):
        return 0.0

    try:
        with open(STORE_FILE, "r") as f:
            data = json.load(f)
            return float(data.get("open_futures_risk", 0.0))
    except Exception:
        return 0.0


# -----------------------------------------------------
# Atomic save (prevents corruption)
# -----------------------------------------------------

def save_exposure(value: float) -> None:
    temp_file = STORE_FILE + ".tmp"

    data = {
        "open_futures_risk": round(float(value), 6)
    }

    with open(temp_file, "w") as f:
        json.dump(data, f)

    os.replace(temp_file, STORE_FILE)