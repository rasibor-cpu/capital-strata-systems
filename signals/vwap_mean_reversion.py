"""
VWAP Mean Reversion Signal Generator
-----------------------------------
Analysis-only signal module.
No execution, no broker, no side effects.

Inputs:
- bars_5m: list[dict] with keys:
    ts, o, h, l, c, v

Outputs:
- list of signal dicts
"""

from typing import List, Dict
import math


def compute_vwap(bars: List[Dict]) -> float:
    pv_sum = 0.0
    v_sum = 0.0
    for b in bars:
        price = (b["h"] + b["l"] + b["c"]) / 3.0
        vol = b.get("v", 0.0)
        pv_sum += price * vol
        v_sum += vol
    if v_sum == 0:
        return math.nan
    return pv_sum / v_sum


def generate_vwap_mean_reversion_signals(
    bars_5m: List[Dict],
    lookback: int = 20,
    z_threshold: float = 1.5,
) -> List[Dict]:
    """
    Generates BUY/SELL signals when price deviates
    from VWAP by a z-score threshold.
    """

    signals = []

    if len(bars_5m) < lookback:
        return signals

    window = bars_5m[-lookback:]
    vwap = compute_vwap(window)

    if not math.isfinite(vwap):
        return signals

    last = bars_5m[-1]
    price = last["c"]

    # simple deviation proxy (not true z-score yet)
    deviation = (price - vwap) / vwap

    if deviation <= -z_threshold / 100:
        signals.append({
            "ts": last["ts"],
            "type": "BUY",
            "price": price,
            "vwap": vwap,
            "deviation": deviation,
            "model": "vwap_mean_reversion",
        })

    elif deviation >= z_threshold / 100:
        signals.append({
            "ts": last["ts"],
            "type": "SELL",
            "price": price,
            "vwap": vwap,
            "deviation": deviation,
            "model": "vwap_mean_reversion",
        })

    return signals