"""
engine/regime/regime_state.py

Canonical Regime State Definitions
Capital Strata Systems (CSS)

Defines:
- Regime labels
- RegimeConfidence container
- Normalization helpers
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict


# ============================================================
# REGIME LABELS
# ============================================================

TREND_UP = "TREND_UP"
TREND_DOWN = "TREND_DOWN"
RANGE = "RANGE"
HIGH_VOLATILITY = "HIGH_VOLATILITY"
LOW_VOLATILITY = "LOW_VOLATILITY"


ALL_REGIMES = [
    TREND_UP,
    TREND_DOWN,
    RANGE,
    HIGH_VOLATILITY,
    LOW_VOLATILITY,
]


# ============================================================
# REGIME CONFIDENCE STRUCTURE
# ============================================================

@dataclass
class RegimeConfidence:
    """
    Holds normalized regime probabilities.
    Values must sum to 1.0
    """

    values: Dict[str, float]

    def dominant(self) -> str:
        return max(self.values, key=self.values.get)

    def get(self, regime: str) -> float:
        return float(self.values.get(regime, 0.0))

    def as_dict(self) -> Dict[str, float]:
        return dict(self.values)


# ============================================================
# HELPERS
# ============================================================

def normalize(conf: Dict[str, float]) -> RegimeConfidence:
    """
    Normalizes a raw confidence dictionary into a probability distribution.
    """

    clean = {k: max(0.0, float(v)) for k, v in conf.items()}
    total = sum(clean.values())

    if total <= 0:
        # fallback to neutral range bias
        fallback = {r: 0.0 for r in ALL_REGIMES}
        fallback[RANGE] = 1.0
        return RegimeConfidence(fallback)

    normalized = {k: v / total for k, v in clean.items()}

    # ensure all regimes present
    for regime in ALL_REGIMES:
        normalized.setdefault(regime, 0.0)

    return RegimeConfidence(normalized)