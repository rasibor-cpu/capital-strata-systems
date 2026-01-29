"""
Breakout Momentum Signal Generator
----------------------------------
Analysis-only signal model.

Fires when price breaks above/below recent range.
No execution, no broker, no side effects.
"""

from typing import List, Dict


def generate_breakout_signals(
    bars_5m: List[Dict],
    lookback: int = 10,
    buffer_pct: float = 0.05,
) -> List[Dict]:
    """
    BUY  when close breaks above recent high
    SELL when close breaks below recent low
    """

    signals = []

    if len(bars_5m) < lookback + 1:
        return signals

    window = bars_5m[-(lookback + 1):-1]
    last = bars_5m[-1]

    recent_high = max(b["h"] for b in window)
    recent_low = min(b["l"] for b in window)

    price = last["c"]

    if price > recent_high * (1 + buffer_pct / 100):
        signals.append({
            "ts": last["ts"],
            "type": "BUY",
            "price": price,
            "break_level": recent_high,
            "model": "breakout_momentum",
        })

    elif price < recent_low * (1 - buffer_pct / 100):
        signals.append({
            "ts": last["ts"],
            "type": "SELL",
            "price": price,
            "break_level": recent_low,
            "model": "breakout_momentum",
        })

    return signals