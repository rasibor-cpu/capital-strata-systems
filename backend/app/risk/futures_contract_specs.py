"""
Futures Contract Specifications
Capital Strata Systems – Phase 15+ / MES-MNQ Phase A

Defines tick size, tick value, and multiplier
for normalized risk calculation.

All risk must resolve to dollar terms.
Expanded to support FX pair simulation routing
while preserving futures contract coverage.
"""

from typing import Dict


FUTURES_SPECS: Dict[str, Dict[str, float]] = {

    # =====================================
    # Equity Index Futures
    # =====================================
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

    "MES": {   # Micro E-mini S&P 500
        "tick_size": 0.25,
        "tick_value": 1.25,
        "multiplier": 5,
    },

    "MNQ": {   # Micro E-mini Nasdaq-100
        "tick_size": 0.25,
        "tick_value": 0.50,
        "multiplier": 2,
    },

    # =====================================
    # Treasury Futures
    # =====================================
    "ZN": {   # 10-Year Note
        "tick_size": 0.015625,
        "tick_value": 15.625,
        "multiplier": 1000,
    },

    # =====================================
    # Commodities
    # =====================================
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

    # =====================================
    # FX Pair Simulation Specs
    # These are normalized for CSS paper-risk
    # approval, not broker-native contract specs.
    # =====================================
    "EUR_USD": {
        "tick_size": 0.0001,
        "tick_value": 10.0,
        "multiplier": 100000,
    },
    "GBP_USD": {
        "tick_size": 0.0001,
        "tick_value": 10.0,
        "multiplier": 100000,
    },
    "AUD_USD": {
        "tick_size": 0.0001,
        "tick_value": 10.0,
        "multiplier": 100000,
    },
    "NZD_USD": {
        "tick_size": 0.0001,
        "tick_value": 10.0,
        "multiplier": 100000,
    },
    "USD_CAD": {
        "tick_size": 0.0001,
        "tick_value": 10.0,
        "multiplier": 100000,
    },
    "USD_CHF": {
        "tick_size": 0.0001,
        "tick_value": 10.0,
        "multiplier": 100000,
    },
    "USD_JPY": {
        "tick_size": 0.01,
        "tick_value": 9.0,
        "multiplier": 100000,
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