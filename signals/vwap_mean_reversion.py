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
# VWAP DISTANCE BUCKET ENUM (STEP 7)
# =========================================
class VWAPDistanceBucket(Enum):
    NEAR = "NEAR_VWAP"
    MID = "MID_FROM_VWAP"
    FAR = "FAR_FROM_VWAP"


# =========================================
# DEFAULT VWAP EPSILON (STEP 5)
# =========================================
def default_vwap_eps(vwap: float, pct: float = 0.0005) -> float:
    if vwap <= 0:
        return 0.0
    return vwap * pct


# =========================================
# VWAP CONTEXT COMPUTATION (STEP 2)
# =========================================
def compute_vwap_context(price: float, vwap: float, eps: float) -> VWAPContext:
    if price > vwap + eps:
        return VWAPContext.ABOVE
    if price < vwap - eps:
        return VWAPContext.BELOW
    return VWAPContext.AT


# =========================================
# VWAP DISTANCE BUCKETING (STEP 7)
# =========================================
def compute_vwap_distance_bucket(
    price: float,
    vwap: float,
    near_pct: float = 0.001,
    far_pct: float = 0.003
) -> VWAPDistanceBucket:
    if vwap <= 0:
        return VWAPDistanceBucket.NEAR

    dist_pct = abs(price - vwap) / vwap

    if dist_pct <= near_pct:
        return VWAPDistanceBucket.NEAR
    if dist_pct >= far_pct:
        return VWAPDistanceBucket.FAR
    return VWAPDistanceBucket.MID


# =========================================================
# VWAP CALCULATION
# =========================================================
def compute_vwap(prices: List[float], volumes: List[float]) -> Optional[float]:
    if not prices or not volumes:
        return None

    total_volume = sum(volumes)
    if total_volume == 0:
        return None

    return sum(p * v for p, v in zip(prices, volumes)) / total_volume


# =========================================================
# PROMPT GENERATOR (STEP 9)
# =========================================================
def generate_vwap_prompt(payload: Dict) -> Optional[Dict]:
    if not isinstance(payload, dict):
        return None

    if "vwap_context" not in payload:
        return None

    if "vwap_distance_bucket" not in payload:
        return None

    return {
        "signal": "VWAP_MEAN_REVERSION",
        "payload": payload,
    }


# =========================================================
# PAYLOAD BUILDER (STEP 8)
# =========================================================
def build_vwap_payload(
    price: float,
    vwap: float,
    eps: float,
    extra: Optional[Dict] = None
) -> Dict:
    payload = {
        "price": price,
        "vwap": vwap,
        "vwap_context": compute_vwap_context(price, vwap, eps).value,
        "vwap_distance_bucket": compute_vwap_distance_bucket(price, vwap).value,
    }
    if isinstance(extra, dict):
        payload.update(extra)
    return payload


# =========================================================
# PAYLOAD BUILDER WITH DEFAULT EPS (STEP 6)
# =========================================================
def build_vwap_payload_default_eps(
    price: float,
    vwap: float,
    extra: Optional[Dict] = None,
    pct: float = 0.0005
) -> Dict:
    eps = default_vwap_eps(vwap, pct=pct)
    return build_vwap_payload(price=price, vwap=vwap, eps=eps, extra=extra)


# =========================================================
# PAYLOAD + PROMPT HELPER (STEP 10 — FIXED)
# =========================================================
def build_vwap_prompt_default_eps(
    price: float,
    vwap: float,
    extra: Optional[Dict] = None,
    pct: float = 0.0005
) -> Optional[Dict]:
    payload = build_vwap_payload_default_eps(
        price=price,
        vwap=vwap,
        extra=extra,
        pct=pct
    )
    return generate_vwap_prompt(payload)
