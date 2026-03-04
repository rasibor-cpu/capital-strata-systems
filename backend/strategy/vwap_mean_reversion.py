from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple


@dataclass(frozen=True)
class VWAPConfig:
    window: int = 40                 # number of candles to include in VWAP
    entry_bps: float = 35.0          # enter BUY if price is below VWAP by this many bps
    exit_bps: float = 10.0           # "exit" signal threshold (not used yet since we only BUY in smoke)
    min_spread_bps: float = 15.0     # require spread <= this many bps to trade


def _safe_float(x: Any) -> Optional[float]:
    try:
        return float(x)
    except Exception:
        return None


def compute_vwap_from_candles(candles: List[Dict[str, Any]], window: int) -> Optional[float]:
    """
    Candles expected in dict form with keys like:
      - 'open','high','low','close','volume' (strings or numbers)
    We compute VWAP using typical price * volume.
    VWAP = sum(tp * v) / sum(v) over last N candles.

    Returns None if insufficient/invalid data.
    """
    if not candles:
        return None

    use = candles[-window:] if len(candles) >= window else candles[:]
    num = 0.0
    den = 0.0

    for c in use:
        h = _safe_float(c.get("high"))
        l = _safe_float(c.get("low"))
        cl = _safe_float(c.get("close"))
        v = _safe_float(c.get("volume"))

        if h is None or l is None or cl is None or v is None:
            continue
        if v <= 0:
            continue

        tp = (h + l + cl) / 3.0
        num += tp * v
        den += v

    if den <= 0:
        return None

    return num / den


def bps_diff(price: float, ref: float) -> float:
    """
    Returns (price - ref)/ref * 10,000.
    """
    if ref <= 0:
        return 0.0
    return (price - ref) / ref * 10000.0


def should_buy_mean_reversion(
    mid_price: float,
    vwap: float,
    spread_bps: float,
    cfg: VWAPConfig,
) -> Tuple[bool, str]:
    """
    BUY when price is sufficiently BELOW VWAP and spread is acceptable.
    """
    if vwap <= 0:
        return False, "VWAP_INVALID"

    if spread_bps > cfg.min_spread_bps:
        return False, f"SPREAD_TOO_WIDE ({spread_bps:.2f} bps)"

    diff_bps = bps_diff(mid_price, vwap)  # negative means below vwap
    if diff_bps <= -cfg.entry_bps:
        return True, f"BUY_SIGNAL (mid below vwap by {abs(diff_bps):.2f} bps)"

    return False, f"NO_SIGNAL (mid-vwap {diff_bps:.2f} bps)"