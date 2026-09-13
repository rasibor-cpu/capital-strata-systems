"""CSS Simulator & Academy foundation.

This package is intentionally broker-independent and simulation-only.
It must never be used as a broker execution surface.
"""

from .engine import AcademyScorer, SimulationEngine
from .models import (
    ChallengeDefinition,
    ChallengeProgress,
    ChallengeType,
    ForecastAssessment,
    SimulatedFill,
    SimulatedPortfolio,
    SimulatedPosition,
    SimulationScore,
)

__all__ = [
    "AcademyScorer",
    "ChallengeDefinition",
    "ChallengeProgress",
    "ChallengeType",
    "ForecastAssessment",
    "SimulatedFill",
    "SimulatedPortfolio",
    "SimulatedPosition",
    "SimulationEngine",
    "SimulationScore",
]
