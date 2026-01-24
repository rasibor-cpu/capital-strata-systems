from enum import Enum
from typing import Optional, Dict, List


# =========================
# VWAP CONTEXT ENUM (STEP 1)
# =========================
class VWAPContext(Enum):
    ABOVE = "ABOVE_VWAP"
    BELOW = "BELOW_VWAP"
    AT = "AT_VWAP"


# =========================================
# VWAP CONTEXT COMPUTATION (STEP 2)
# =========================================
def compute_vwap_context(price: float, vwap: float, eps: float) -> VWAPContext:
    """
    Classifies price position relative to VWAP using a tolerance eps.
    Pure function. No side effects.
    """
    if price > vwap + eps:
        return VWAPContext.ABOVE
    if price < vwap - eps:
        return VWAPContext.BELOW
    return VWAPContext.AT


# =========================================================
# Existing VWAP Mean Reversion Logic (UNCHANGED)
# =========================================================
def compute_vwap(prices: List[float], volumes: List[float]) -> Optional[float]:
    """
    Existing VWAP computation.
    DO NOT MODIFY in Step 2.
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
    DO NOT MODIFY in Step 2.
    """
    return {
        "signal": "VWAP_MEAN_REVERSION",
        "payload": payload,
    }
