"""
CSS VWAP Mean Reversion Strategy
"""

from dataclasses import dataclass
from typing import List, Tuple


@dataclass
class VWAPConfig:
    window: int = 20
    epsilon_bps: float = 12
    take_profit_bps: float = 35
    stop_loss_bps: float = 45


def compute_vwap_from_candles(candles: List[dict], window: int) -> float:
    candles = candles[-window:]

    total_pv = 0.0
    total_volume = 0.0

    for c in candles:
        price = float(c["close"])
        volume = float(c.get("volume", 1))

        total_pv += price * volume
        total_volume += volume

    if total_volume == 0:
        return 0.0

    return total_pv / total_volume


def should_buy_mean_reversion(
    mid: float,
    vwap: float,
    spread_bps: float,
    cfg: VWAPConfig,
) -> Tuple[bool, str]:

    if spread_bps < -cfg.epsilon_bps:
        return True, "Price below VWAP threshold"

    return False, "No signal"