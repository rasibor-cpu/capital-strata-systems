"""
engine/regime/regime_controller.py

Regime Controller (Stateful + EMA Smoothed)
Capital Strata Systems (CSS)

Features:
- EMA smoothing of regime confidence
- Behaviour-specific alpha tuning
- Stateful persistence
"""

from __future__ import annotations

from typing import Dict, Optional

from engine.regime.regime_state import (
    RegimeConfidence,
    ALL_REGIMES,
    normalize,
)


# ============================================================
# Behaviour → Alpha mapping
# ============================================================

BEHAVIOUR_ALPHA = {
    "DEFENSIVE": 0.20,
    "BALANCED": 0.30,
    "AGGRESSIVE": 0.45,
}


class RegimeController:

    def __init__(self, behaviour: str = "BALANCED") -> None:

        self.behaviour = behaviour.upper()
        self.alpha = BEHAVIOUR_ALPHA.get(self.behaviour, 0.30)

        self._state: Optional[RegimeConfidence] = None

    # ---------------------------------------------------------

    def update(self, raw_confidence: RegimeConfidence) -> RegimeConfidence:
        """
        Apply EMA smoothing:
        smoothed = alpha * new + (1 - alpha) * previous
        """

        if self._state is None:
            self._state = raw_confidence
            return self._state

        new_values: Dict[str, float] = {}

        prev = self._state.as_dict()
        curr = raw_confidence.as_dict()

        for regime in ALL_REGIMES:
            new_values[regime] = (
                self.alpha * curr.get(regime, 0.0)
                + (1.0 - self.alpha) * prev.get(regime, 0.0)
            )

        self._state = normalize(new_values)
        return self._state

    # ---------------------------------------------------------

    def current(self) -> Optional[RegimeConfidence]:
        return self._state