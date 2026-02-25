"""
engine/strategy/behaviour_mapper.py

Institutional Behaviour → StrategyProfile Mapping
Capital Strata Systems

Canonical Behaviour Codes:

A = DEFENSIVE
B = CONSERVATIVE
C = BALANCED
D = AGGRESSIVE
E = OFF
"""

from __future__ import annotations
from dataclasses import dataclass


# ============================================================
# STRATEGY PROFILE STRUCTURE
# ============================================================

@dataclass
class StrategyProfile:
    name: str
    description: str
    min_signal_strength: float
    max_trades_per_week: int
    allow_trend: bool
    allow_mean_reversion: bool
    risk_bias_multiplier: float


# ============================================================
# STRATEGY PROFILES
# ============================================================

DEFENSIVE_PROFILE = StrategyProfile(
    name="DEFENSIVE",
    description="Capital protection focus",
    min_signal_strength=0.70,
    max_trades_per_week=25,
    allow_trend=True,
    allow_mean_reversion=True,
    risk_bias_multiplier=0.8,
)

CONSERVATIVE_PROFILE = StrategyProfile(
    name="CONSERVATIVE",
    description="Low turnover institutional",
    min_signal_strength=0.65,
    max_trades_per_week=35,
    allow_trend=True,
    allow_mean_reversion=True,
    risk_bias_multiplier=0.9,
)

BALANCED_PROFILE = StrategyProfile(
    name="BALANCED",
    description="Balanced hybrid (Default Institutional Mode)",
    min_signal_strength=0.61,
    max_trades_per_week=40,
    allow_trend=True,
    allow_mean_reversion=True,
    risk_bias_multiplier=1.0,
)

AGGRESSIVE_PROFILE = StrategyProfile(
    name="AGGRESSIVE",
    description="Higher turnover / growth tilt",
    min_signal_strength=0.35,
    max_trades_per_week=60,
    allow_trend=True,
    allow_mean_reversion=True,
    risk_bias_multiplier=1.3,
)

OFF_PROFILE = StrategyProfile(
    name="OFF",
    description="Governance only / alpha disabled",
    min_signal_strength=1.0,
    max_trades_per_week=0,
    allow_trend=False,
    allow_mean_reversion=False,
    risk_bias_multiplier=0.0,
)


# ============================================================
# CANONICAL RESOLUTION
# ============================================================

def get_profile_for_behaviour(code: str) -> StrategyProfile:

    key = (code or "C").upper().strip()

    if key == "A":
        return DEFENSIVE_PROFILE
    if key == "B":
        return CONSERVATIVE_PROFILE
    if key == "C":
        return BALANCED_PROFILE
    if key == "D":
        return AGGRESSIVE_PROFILE
    if key == "E":
        return OFF_PROFILE

    # Accept full names
    if key == "DEFENSIVE":
        return DEFENSIVE_PROFILE
    if key == "CONSERVATIVE":
        return CONSERVATIVE_PROFILE
    if key == "BALANCED":
        return BALANCED_PROFILE
    if key == "AGGRESSIVE":
        return AGGRESSIVE_PROFILE
    if key == "OFF":
        return OFF_PROFILE

    return BALANCED_PROFILE