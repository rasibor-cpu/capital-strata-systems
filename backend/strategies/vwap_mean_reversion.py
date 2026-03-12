"""
CSS VWAP Mean Reversion Strategy
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Tuple


@dataclass
class VWAPConfig:
    window: int = 20
    epsilon_bps: float = 12.0
    take_profit_bps: float = 35.0
    stop_loss_bps: float = 45.0


def compute_vwap_from_candles(candles: List[dict], window: int) -> float:
    candles = candles[-window:]

    total_pv = 0.0
    total_volume = 0.0

    for c in candles:
        price = float(c.get("close", 0.0))
        volume = float(c.get("volume", 1.0))

        total_pv += price * volume
        total_volume += volume

    if total_volume == 0:
        return 0.0

    return total_pv / total_volume


def compute_deviation_bps(mid: float, vwap: float) -> float:
    """
    deviation_bps = (mid - vwap) / vwap * 10,000
    Positive => price above VWAP
    Negative => price below VWAP
    """
    if vwap <= 0:
        return 0.0
    return ((mid - vwap) / vwap) * 10000.0


def should_buy_mean_reversion(
    mid: float,
    vwap: float,
    spread_bps: float,
    cfg: VWAPConfig,
) -> Tuple[bool, str]:
    """
    Buy when price is sufficiently below VWAP.
    Spread is retained in signature for execution-quality context.
    """
    if mid <= 0 or vwap <= 0:
        return False, "Invalid price or VWAP"

    deviation_bps = compute_deviation_bps(mid, vwap)

    if deviation_bps <= -cfg.epsilon_bps:
        return True, f"Price below VWAP threshold ({deviation_bps:.2f} bps)"

    return False, "No buy signal"


def should_sell_mean_reversion(
    mid: float,
    vwap: float,
    spread_bps: float,
    cfg: VWAPConfig,
) -> Tuple[bool, str]:
    """
    Sell/exit when price is sufficiently above VWAP.
    """
    if mid <= 0 or vwap <= 0:
        return False, "Invalid price or VWAP"

    deviation_bps = compute_deviation_bps(mid, vwap)

    if deviation_bps >= cfg.epsilon_bps:
        return True, f"Price above VWAP threshold ({deviation_bps:.2f} bps)"

    return False, "No sell signal"


if __name__ == "__main__":
    sample_candles = [
        {"close": 100, "volume": 10},
        {"close": 101, "volume": 12},
        {"close": 99, "volume": 8},
        {"close": 98, "volume": 15},
        {"close": 97, "volume": 20},
    ]

    cfg = VWAPConfig(window=5, epsilon_bps=12)
    vwap = compute_vwap_from_candles(sample_candles, cfg.window)
    mid = 97.0
    spread_bps = 5.0

    buy_ok, buy_reason = should_buy_mean_reversion(mid, vwap, spread_bps, cfg)
    sell_ok, sell_reason = should_sell_mean_reversion(mid, vwap, spread_bps, cfg)

    print("VWAP:", vwap)
    print("Deviation bps:", compute_deviation_bps(mid, vwap))
    print("Buy:", buy_ok, "|", buy_reason)
    print("Sell:", sell_ok, "|", sell_reason)