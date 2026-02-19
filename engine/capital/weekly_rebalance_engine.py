"""
Weekly Rebalance Engine – Dynamic Drift Model
Capital Strata Systems / REA

Hybrid Model:
- Friday 17:00 ET calendar gate
- Volatility-adjusted drift threshold
- Regime-adjusted drift tightening
- Fail-closed
"""

from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from typing import Dict


@dataclass
class RebalanceResult:
    should_rebalance: bool
    reason: str
    drift_snapshot: Dict[str, float]
    effective_threshold: float


class WeeklyRebalanceEngine:
    def __init__(
        self,
        target_weights: Dict[str, float],
        base_threshold: float = 0.05
    ):
        self.target_weights = target_weights
        self.base_threshold = base_threshold

    # -------------------------
    # Time Gate
    # -------------------------

    def _is_rebalance_time(self, now: datetime) -> bool:
        return now.weekday() == 4 and now.hour >= 17

    # -------------------------
    # Dynamic Threshold
    # -------------------------

    def _compute_dynamic_threshold(
        self,
        volatility_state: str,
        regime_state: str
    ) -> float:

        volatility_map = {
            "HIGH": 0.6,
            "MEDIUM": 1.0,
            "LOW": 1.3
        }

        regime_map = {
            "DEFENSIVE": 0.75,
            "NORMAL": 1.0,
            "AGGRESSIVE": 1.2
        }

        vol_factor = volatility_map.get(volatility_state.upper(), 1.0)
        regime_factor = regime_map.get(regime_state.upper(), 1.0)

        return self.base_threshold * vol_factor * regime_factor

    # -------------------------
    # Drift Calculation
    # -------------------------

    def _calculate_drift(
        self,
        current_allocations: Dict[str, float]
    ) -> Dict[str, float]:

        drift = {}
        total = sum(current_allocations.values())

        if total <= 0:
            return drift

        for instrument, value in current_allocations.items():
            current_weight = value / total
            target_weight = self.target_weights.get(instrument, 0.0)
            drift[instrument] = current_weight - target_weight

        return drift

    # -------------------------
    # Public Interface
    # -------------------------

    def evaluate(
        self,
        now: datetime,
        current_allocations: Dict[str, float],
        volatility_state: str,
        regime_state: str
    ) -> RebalanceResult:

        try:
            if not self._is_rebalance_time(now):
                return RebalanceResult(
                    False,
                    "Not rebalance window",
                    {},
                    0.0
                )

            drift = self._calculate_drift(current_allocations)

            if not drift:
                return RebalanceResult(
                    False,
                    "Invalid allocation snapshot",
                    {},
                    0.0
                )

            effective_threshold = self._compute_dynamic_threshold(
                volatility_state,
                regime_state
            )

            for value in drift.values():
                if abs(value) >= effective_threshold:
                    return RebalanceResult(
                        True,
                        "Dynamic drift threshold exceeded",
                        drift,
                        effective_threshold
                    )

            return RebalanceResult(
                False,
                "Drift within dynamic tolerance",
                drift,
                effective_threshold
            )

        except Exception as e:
            return RebalanceResult(
                False,
                f"Exception: {str(e)}",
                {},
                0.0
            )
