"""
engine/core/behaviour_config.py

Canonical Behaviour Configuration
Capital Strata Systems (CSS)

Behaviour controls:
- Regime smoothing alpha
- Base risk percentage
- Drawdown throttle aggressiveness
- Volatility haircut strength
- Stop multiplier tolerance

This is the top-level capital temperament selector.

Supports behaviour codes and names:
  A=DEFENSIVE, B=CONSERVATIVE, C=BALANCED, D=AGGRESSIVE, E=OFF
  Or: "DEFENSIVE", "CONSERVATIVE", "BALANCED", "AGGRESSIVE", "OFF"
"""

from __future__ import annotations
from dataclasses import dataclass


# ============================================================
# BEHAVIOUR PROFILES
# ============================================================

@dataclass(frozen=True)
class BehaviourConfig:
    name: str
    regime_alpha: float
    base_risk_pct: float
    drawdown_intensity: float
    volatility_haircut: float
    stop_multiplier: float


# ============================================================
# INSTITUTIONAL PROFILES
# ============================================================

DEFENSIVE = BehaviourConfig(
    name="DEFENSIVE",
    regime_alpha=0.20,
    base_risk_pct=0.005,         # 0.5%
    drawdown_intensity=1.5,      # stronger throttle
    volatility_haircut=0.60,     # heavier haircut
    stop_multiplier=0.8,         # tighter stops
)

CONSERVATIVE = BehaviourConfig(
    name="CONSERVATIVE",
    regime_alpha=0.25,
    base_risk_pct=0.0075,        # 0.75%
    drawdown_intensity=1.2,
    volatility_haircut=0.50,
    stop_multiplier=0.9,
)

BALANCED = BehaviourConfig(
    name="BALANCED",
    regime_alpha=0.30,
    base_risk_pct=0.010,         # 1.0%
    drawdown_intensity=1.0,
    volatility_haircut=0.40,
    stop_multiplier=1.0,
)

AGGRESSIVE = BehaviourConfig(
    name="AGGRESSIVE",
    regime_alpha=0.45,
    base_risk_pct=0.020,         # 2.0%
    drawdown_intensity=0.7,      # lighter throttle
    volatility_haircut=0.20,
    stop_multiplier=1.3,         # wider stops
)

OFF = BehaviourConfig(
    name="OFF",
    regime_alpha=0.30,
    base_risk_pct=0.0,
    drawdown_intensity=1.0,
    volatility_haircut=1.0,
    stop_multiplier=1.0,
)


# ============================================================
# CODE + NAME ALIASES
# ============================================================

# Single-letter behaviour codes (authoritative)
CODE_ALIASES = {
    "A": "DEFENSIVE",
    "B": "CONSERVATIVE",
    "C": "BALANCED",
    "D": "AGGRESSIVE",
    "E": "OFF",
}

# Registry by canonical name
BEHAVIOUR_REGISTRY = {
    "DEFENSIVE": DEFENSIVE,
    "CONSERVATIVE": CONSERVATIVE,
    "BALANCED": BALANCED,
    "AGGRESSIVE": AGGRESSIVE,
    "OFF": OFF,
}


def get_behaviour(name: str) -> BehaviourConfig:
    """
    Accepts:
      - A/B/C/D/E
      - DEFENSIVE/CONSERVATIVE/BALANCED/AGGRESSIVE/OFF
    Defaults to BALANCED if unknown.
    """
    if not name:
        return BALANCED

    k = str(name).strip().upper()

    # Expand letter codes to canonical names
    k = CODE_ALIASES.get(k, k)

    return BEHAVIOUR_REGISTRY.get(k, BALANCED)