"""
Rebalancer – Institutional Capital Tilt Engine
Capital Strata Systems (CSS)

Reads PnLTracker signals and generates
controlled capital reallocation adjustments.

Governance-first design.
"""

from typing import Dict


class Rebalancer:

    def __init__(
        self,
        max_tilt: float = 0.05,
        min_tilt: float = -0.05,
    ):
        """
        max_tilt: maximum capital increase per instrument (e.g. 0.05 = +5%)
        min_tilt: maximum capital decrease per instrument (e.g. -0.05 = -5%)
        """

        self.max_tilt = max_tilt
        self.min_tilt = min_tilt

    # ==========================================================
    # GENERATE ADJUSTMENT MAP
    # ==========================================================

    def generate_adjustments(self, signal_weights: Dict[str, float]) -> Dict[str, float]:
        """
        signal_weights:
            output of PnLTracker.rebalancing_signal()

        returns:
            { instrument: capital_adjustment_percentage }
        """

        if not signal_weights:
            return {}

        adjustments = {}

        for instrument, raw_weight in signal_weights.items():

            # raw_weight already normalized by abs total
            # but we enforce governance limits

            if raw_weight > 0:
                adjustment = min(raw_weight, self.max_tilt)
            elif raw_weight < 0:
                adjustment = max(raw_weight, self.min_tilt)
            else:
                adjustment = 0.0

            adjustments[instrument] = adjustment

        return adjustments

    # ==========================================================
    # APPLY TO CURRENT WEIGHTS
    # ==========================================================

    def apply_adjustments(
        self,
        current_weights: Dict[str, float],
        adjustments: Dict[str, float],
    ) -> Dict[str, float]:
        """
        Applies tilt to existing capital weights.
        Ensures total weights remain normalized.
        """

        if not current_weights:
            return {}

        updated = {}

        for inst, weight in current_weights.items():
            delta = adjustments.get(inst, 0.0)
            updated[inst] = weight + delta

        # Normalize to 1.0 total
        total = sum(updated.values())
        if total == 0:
            return updated

        normalized = {k: v / total for k, v in updated.items()}

        return normalized