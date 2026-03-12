from __future__ import annotations

from typing import Dict, Any


def range_mean_reversion_signal(market_data: Dict[str, Any]) -> bool:
    """
    CSS Range Mean Reversion Strategy

    Used when market regime = RANGE.

    Logic:
    - Price deviates significantly from VWAP
    - Market lacks directional efficiency
    - Expect snap-back to mean

    Returns:
        True  -> BUY signal
        False -> no trade
    """

    price = market_data.get("price")
    vwap = market_data.get("vwap")
    regime = market_data.get("regime")
    volatility = market_data.get("volatility", 0)
    efficiency = market_data.get("trend_efficiency", 0)

    if price is None or vwap is None:
        return False

    # Only operate in RANGE regime
    if regime != "RANGE":
        return False

    deviation = abs(price - vwap) / vwap

    # Core signal logic
    if deviation > 0.003 and efficiency < 0.25 and volatility > 0:
        return True

    return False