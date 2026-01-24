from enum import Enum
from typing import Optional, Dict, List


# =========================
# VWAP CONTEXT ENUM (STEP 1)
# =========================
class VWAPContext(Enum):
    ABOVE = "ABOVE_VWAP"
    BELOW = "BELOW_VWAP"
    AT = "AT_VWAP"


# =========================================================
# Existing VWAP Mean Reversion Logic (UNCHANGED)
# =========================================================

def compute_vwap(prices: List[float], volumes: List[float]) -> Optional[float]:
    """
    Existing VWAP computation.
    DO NOT MODIFY in Step 1.
    """
    if not prices or not volumes:
        return None

    total_volume = sum(volumes)
    if total_volume == 0:
        return None

    return sum(p * v for p, v in zip(prices, volumes)) / total_volume


def generate_vwap_prompt(payload: Dict) -> Dict:
    """
    Existing prompt generator.
    DO NOT MODIFY in Step 1.
    """
    return {
        "signal": "VWAP_MEAN_REVERSION",
        "payload": payload,
    }
