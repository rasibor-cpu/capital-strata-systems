"""
BehaviourMapper – User Behaviour → StrategyProfile Mapping
Capital Strata Systems (CSS)

Purpose:
- User selects Behaviour at sign-on
- Engine derives internal StrategyProfile automatically
- Keeps UI simple (1 selection only)
"""

from engine.strategy.strategy_mode import get_profile, StrategyProfile


# ============================================================
# BEHAVIOUR → STRATEGY PROFILE MAPPING
# ============================================================

BEHAVIOUR_MAP = {

    # A — Capital Protection Focus
    "A": "DEFENSIVE",

    # B — Low Turnover Institutional
    "B": "CONSERVATIVE",

    # C — Balanced Hybrid (Default Institutional Mode)
    "C": "BALANCED",

    # D — Higher Turnover / Growth Tilt
    "D": "AGGRESSIVE",

    # E — Governance Only / Alpha Disabled
    "E": "OFF",
}


# ============================================================
# PUBLIC ACCESSOR
# ============================================================

def get_profile_for_behaviour(behaviour_code: str) -> StrategyProfile:
    """
    Converts user behaviour selection into StrategyProfile.
    """

    if behaviour_code is None:
        raise ValueError("Behaviour code cannot be None")

    behaviour_code = behaviour_code.upper()

    if behaviour_code not in BEHAVIOUR_MAP:
        raise ValueError(f"Unknown behaviour code: {behaviour_code}")

    strategy_key = BEHAVIOUR_MAP[behaviour_code]
    return get_profile(strategy_key)