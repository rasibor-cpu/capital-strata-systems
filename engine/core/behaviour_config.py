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


# ============================================================
# REGISTRY
# ============================================================

BEHAVIOUR_REGISTRY = {
    "DEFENSIVE": DEFENSIVE,
    "BALANCED": BALANCED,
    "AGGRESSIVE": AGGRESSIVE,
}


def get_behaviour(name: str) -> BehaviourConfig:
    return BEHAVIOUR_REGISTRY.get(name.upper(), BALANCED)