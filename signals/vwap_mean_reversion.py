from enum import Enum
from typing import Optional, Dict, List


class VWAPContext(Enum):
    ABOVE = "ABOVE_VWAP"
    BELOW = "BELOW_VWAP"
    AT = "AT_VWAP"


class VWAPDistanceBucket(Enum):
    NEAR = "NEAR_VWAP"
    MID = "MID_FROM_VWAP"
    FAR = "FAR_FROM_VWAP"


def default_vwap_eps(vwap: float, pct: float = 0.0005) -> float:
    return vwap * pct if vwap > 0 else 0.0


def compute_vwap_context(price: float, vwap: float, eps: float) -> VWAPContext:
    if price > vwap + eps:
        return VWAPContext.ABOVE
    if price < vwap - eps:
        return VWAPContext.BELOW
    return VWAPContext.AT


def compute_vwap_distance_bucket(
    price: float,
    vwap: float,
    near_pct: float = 0.001,
    far_pct: float = 0.003
) -> VWAPDistanceBucket:
    if vwap <= 0:
        return VWAPDistanceBucket.NEAR

    dist = abs(price - vwap) / vwap
    if dist <= near_pct:
        return VWAPDistanceBucket.NEAR
    if dist >= far_pct:
        return VWAPDistanceBucket.FAR
    return VWAPDistanceBucket.MID


def build_vwap_payload_default_eps(
    price: float,
    vwap: float,
    extra: Optional[Dict] = None
) -> Dict:
    eps = default_vwap_eps(vwap)
    payload = {
        "price": price,
        "vwap": vwap,
        "vwap_context": compute_vwap_context(price, vwap, eps).value,
        "vwap_distance_bucket": compute_vwap_distance_bucket(price, vwap).value,
    }
    if extra:
        payload.update(extra)
    return payload


def build_vwap_prompt_default_eps(
    price: float,
    vwap: float,
    extra: Optional[Dict] = None
) -> Dict:
    return {
        "signal": "VWAP_MEAN_REVERSION",
        "payload": build_vwap_payload_default_eps(price, vwap, extra),
    }
