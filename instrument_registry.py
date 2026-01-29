"""
Instrument Registry — Personal Module (LOCKED BASELINE)

Purpose:
- Central, user-editable registry of tradable FX instruments
- Enforces consistent rules across all instruments
- Converts pip-based parameters into price units
- Safe defaults aligned with the Sanity Probe (M5, N=20, epsilon gate)

Design principles:
- Simple, explicit, transparent
- No broker dependency
- All new instruments inherit the same rules automatically
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, List


# -------------------------
# Core definitions
# -------------------------

@dataclass(frozen=True)
class InstrumentSpec:
    symbol: str
    pip_size: float          # e.g., 0.0001 or 0.01 for JPY pairs
    min_lot: float = 0.01
    max_lot: float = 10.0
    default_lot: float = 0.10


# -------------------------
# Registry (USER-EDITABLE)
# -------------------------

_REGISTRY: Dict[str, InstrumentSpec] = {
    # Majors
    "EURUSD": InstrumentSpec(symbol="EURUSD", pip_size=0.0001),
    "GBPUSD": InstrumentSpec(symbol="GBPUSD", pip_size=0.0001),
    "USDCHF": InstrumentSpec(symbol="USDCHF", pip_size=0.0001),
    "AUDUSD": InstrumentSpec(symbol="AUDUSD", pip_size=0.0001),
    "NZDUSD": InstrumentSpec(symbol="NZDUSD", pip_size=0.0001),

    # JPY pairs
    "USDJPY": InstrumentSpec(symbol="USDJPY", pip_size=0.01),
    "EURJPY": InstrumentSpec(symbol="EURJPY", pip_size=0.01),
    "GBPJPY": InstrumentSpec(symbol="GBPJPY", pip_size=0.01),
}


# -------------------------
# Public API
# -------------------------

def list_instruments() -> List[str]:
    """Return sorted list of enabled instruments."""
    return sorted(_REGISTRY.keys())


def get_instrument(symbol: str) -> InstrumentSpec:
    """Fetch instrument spec or raise a clear error."""
    key = symbol.strip().upper()
    if key not in _REGISTRY:
        raise KeyError(
            f"Instrument '{symbol}' not found. "
            f"Add it to instrument_registry.py to enable."
        )
    return _REGISTRY[key]


def pip_to_price(symbol: str, pips: float) -> float:
    """Convert pips to price units for the instrument."""
    spec = get_instrument(symbol)
    return pips * spec.pip_size


def price_to_pips(symbol: str, price_delta: float) -> float:
    """Convert a price delta into pips."""
    spec = get_instrument(symbol)
    return price_delta / spec.pip_size


# -------------------------
# Sanity Probe Defaults (LOCKED)
# -------------------------

DEFAULT_TIMEFRAME = "M5"
DEFAULT_LOOKBACK_BARS = 20

EPSILON_PIPS = {
    "conservative": 15.0,
    "balanced": 10.0,     # DEFAULT — target ~70% accuracy
    "aggressive": 6.0,
}

DEFAULT_ACCURACY_MODE = "balanced"


def epsilon_price(symbol: str, mode: str = DEFAULT_ACCURACY_MODE) -> float:
    """Return epsilon in price units for the given instrument and mode."""
    m = mode.strip().lower()
    if m not in EPSILON_PIPS:
        raise KeyError(f"Unknown accuracy mode '{mode}'.")
    return pip_to_price(symbol, EPSILON_PIPS[m])


# -------------------------
# Validation helper
# -------------------------

def validate_registry() -> None:
    """Sanity-check the registry at startup."""
    for sym, spec in _REGISTRY.items():
        if spec.pip_size <= 0:
            raise ValueError(f"{sym}: pip_size must be > 0")
        if spec.min_lot <= 0 or spec.max_lot <= 0:
            raise ValueError(f"{sym}: lot sizes must be > 0")
        if spec.default_lot < spec.min_lot or spec.default_lot > spec.max_lot:
            raise ValueError(f"{sym}: default_lot out of bounds")


# Run validation on import
validate_registry()