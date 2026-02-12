"""
Futures Contract Specifications
Capital Strata Systems – Phase 15

Defines tick size, tick value, and multiplier
for normalized risk calculation.

All risk must resolve to dollar terms.
"""

from typing import Dict


FUTURES_SPECS: Dict[str, Dict[str, float]] = {

    # Equity Index Futures
    "ES": {   # S&P 500 E-mini
        "tick_size": 0.25,
        "tick_value": 12.50,
        "multiplier": 50,
    },

    "NQ": {   # Nasdaq E-mini
        "tick_size": 0.25,
        "tick_value": 5.00,
        "multiplier": 20,
    },

    # Treasury Futures
    "ZN": {   # 10-Year Note
        "tick_size": 0.015625,
        "tick_value": 15.625,
        "multiplier": 1000,
    },

    # Commodities
    "GC": {   # Gold
        "tick_size": 0.10,
        "tick_value": 10.0,
        "multiplier": 100,
    },

    "CL": {   # Crude Oil
        "tick_size": 0.01,
        "tick_value": 10.0,
        "multiplier": 1000,
    },
}


def calculate_futures_risk(
    symbol: str,
    entry_price: float,
    stop_price: float,
    contracts: int
) -> float:
    """
    Returns risk in USD.
    """

    if symbol not in FUTURES_SPECS:
        raise ValueError(f"Unsupported futures contract: {symbol}")

    spec = FUTURES_SPECS[symbol]

    tick_size = spec["tick_size"]
    tick_value = spec["tick_value"]

    price_diff = abs(entry_price - stop_price)
    ticks = price_diff / tick_size

    risk = ticks * tick_value * contracts

    return round(float(risk), 2)
