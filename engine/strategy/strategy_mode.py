"""
StrategyMode – Institutional Behaviour Profiles
Capital Strata Systems (CSS)

Authoritative mapping between:
- User selectable behaviour
- Risk posture
- Signal strictness
- Trade frequency
- Alpha style allowance
"""

from dataclasses import dataclass
from typing import Dict


# ============================================================
# DATA STRUCTURE
# ============================================================

@dataclass(frozen=True)
class StrategyProfile:
    name: str
    description: str
    min_signal_strength: float
    max_trades_per_week: int
    allow_trend: bool
    allow_mean_reversion: bool
    risk_bias_multiplier: float


# ============================================================
# PROFILE REGISTRY
# ============================================================

STRATEGY_PROFILES: Dict[str, StrategyProfile] = {

    "DEFENSIVE": StrategyProfile(
        name="DEFENSIVE",
        description="Capital preservation priority",
        min_signal_strength=0.75,
        max_trades_per_week=5,
        allow_trend=True,
        allow_mean_reversion=False,
        risk_bias_multiplier=0.6,
    ),

    "CONSERVATIVE": StrategyProfile(
        name="CONSERVATIVE",
        description="Low turnover, selective entries",
        min_signal_strength=0.65,
        max_trades_per_week=10,
        allow_trend=True,
        allow_mean_reversion=True,
        risk_bias_multiplier=0.8,
    ),

    "BALANCED": StrategyProfile(
        name="BALANCED",
        description="Institutional hybrid posture",
        # Locked via cross-validated threshold sweeps (SPY 1m 30d + USD/GBP 10k)
        min_signal_strength=0.80,
        max_trades_per_week=20,
        allow_trend=True,
        allow_mean_reversion=True,
        risk_bias_multiplier=1.0,
    ),

    "AGGRESSIVE": StrategyProfile(
        name="AGGRESSIVE",
        description="Higher turnover, lower threshold",
        min_signal_strength=0.35,
        max_trades_per_week=40,
        allow_trend=True,
        allow_mean_reversion=True,
        risk_bias_multiplier=1.3,
    ),

    "OFF": StrategyProfile(
        name="OFF",
        description="No discretionary alpha (governance only)",
        min_signal_strength=1.0,
        max_trades_per_week=0,
        allow_trend=False,
        allow_mean_reversion=False,
        risk_bias_multiplier=0.0,
    ),
}


# ============================================================
# ACCESSOR
# ============================================================

def get_profile(mode: str) -> StrategyProfile:
    mode = mode.upper()
    if mode not in STRATEGY_PROFILES:
        raise ValueError(f"Unknown strategy mode: {mode}")
    return STRATEGY_PROFILES[mode]