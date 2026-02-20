"""
engine/regime/regime_controller.py

Regime Controller (Stateful + EMA Smoothed)
Capital Strata Systems (CSS)

Features:
- EMA smoothing of regime confidence
- Behaviour-configured alpha tuning (canonical BehaviourConfig)
- Stateful persistence

Default temperament: BALANCED
"""

from __future__ import annotations

from typing import Dict, Optional

from engine.core.behaviour_config import get_behaviour
from engine.regime.regime_state import (
    RegimeConfidence,
    ALL_REGIMES,
    normalize,
)


class RegimeController:
    """
    EMA smoothing controller.

    BehaviourConfig is the single source of truth for alpha:
    - DEFENSIVE  -> lower alpha (more smoothing)
    - BALANCED   -> baseline
    - AGGRESSIVE -> higher alpha (faster responsiveness)
    """

    def __init__(self, behaviour: str = "BALANCED") -> None:
        self.behaviour = (behaviour or "BALANCED").upper()
        cfg = get_behaviour(self.behaviour)

        # Canonical alpha source
        self.alpha: float = float(cfg.regime_alpha)

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

        a = float(self.alpha)
        one_minus = 1.0 - a

        for regime in ALL_REGIMES:
            new_values[regime] = (
                a * curr.get(regime, 0.0)
                + one_minus * prev.get(regime, 0.0)
            )

        self._state = normalize(new_values)
        return self._state

    # ---------------------------------------------------------

    def current(self) -> Optional[RegimeConfidence]:
        return self._state