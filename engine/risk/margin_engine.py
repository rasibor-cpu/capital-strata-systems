"""
Capital Strata Systems
Phase 96B

Margin Engine

Purpose
-------
Calculates canonical margin state from required and available margin.

No broker calls.
No trade execution.
No dashboard wiring.
No portfolio mutation.
"""

from dataclasses import dataclass
from enum import Enum


class MarginState(str, Enum):
    UNKNOWN = "UNKNOWN"
    GREEN = "GREEN"
    YELLOW = "YELLOW"
    ORANGE = "ORANGE"
    RED = "RED"
    BLACK = "BLACK"


class MarginEscalationState(str, Enum):
    NORMAL = "NORMAL"
    MONITOR = "MONITOR"
    RESTRICT_NEW_RISK = "RESTRICT_NEW_RISK"
    DEFENSIVE_ONLY = "DEFENSIVE_ONLY"
    CRITICAL_BLOCK = "CRITICAL_BLOCK"


@dataclass(frozen=True)
class MarginSnapshot:
    margin_source: str
    required_margin: float
    available_margin: float
    free_margin: float
    margin_utilization_pct: float
    margin_state: MarginState
    escalation_state: MarginEscalationState


class MarginEngine:
    """
    Deterministic institutional margin engine.

    Utilization formula:

        required_margin / available_margin * 100

    State bands:

        UNKNOWN: invalid or missing data
        GREEN:   0% to 40%
        YELLOW: >40% to 60%
        ORANGE: >60% to 75%
        RED:    >75% to 90%
        BLACK:  >90%
    """

    def calculate(
        self,
        *,
        required_margin: float,
        available_margin: float,
        margin_source: str = "SIMULATED",
    ) -> MarginSnapshot:
        required = float(required_margin or 0.0)
        available = float(available_margin or 0.0)

        if available <= 0:
            return MarginSnapshot(
                margin_source=str(margin_source or "UNKNOWN"),
                required_margin=round(required, 2),
                available_margin=round(available, 2),
                free_margin=round(available - required, 2),
                margin_utilization_pct=0.0,
                margin_state=MarginState.UNKNOWN,
                escalation_state=MarginEscalationState.CRITICAL_BLOCK,
            )

        utilization = (required / available) * 100.0
        free_margin = available - required

        margin_state = self._state_for_utilization(utilization)
        escalation = self._escalation_for_state(margin_state)

        return MarginSnapshot(
            margin_source=str(margin_source or "UNKNOWN"),
            required_margin=round(required, 2),
            available_margin=round(available, 2),
            free_margin=round(free_margin, 2),
            margin_utilization_pct=round(utilization, 2),
            margin_state=margin_state,
            escalation_state=escalation,
        )

    def _state_for_utilization(self, utilization: float) -> MarginState:
        if utilization <= 40.0:
            return MarginState.GREEN
        if utilization <= 60.0:
            return MarginState.YELLOW
        if utilization <= 75.0:
            return MarginState.ORANGE
        if utilization <= 90.0:
            return MarginState.RED
        return MarginState.BLACK

    def _escalation_for_state(
        self,
        state: MarginState,
    ) -> MarginEscalationState:
        if state == MarginState.GREEN:
            return MarginEscalationState.NORMAL
        if state == MarginState.YELLOW:
            return MarginEscalationState.MONITOR
        if state == MarginState.ORANGE:
            return MarginEscalationState.RESTRICT_NEW_RISK
        if state == MarginState.RED:
            return MarginEscalationState.DEFENSIVE_ONLY
        return MarginEscalationState.CRITICAL_BLOCK