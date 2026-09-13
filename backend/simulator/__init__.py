"""CSS Simulator & Academy.

This package is intentionally broker-independent and simulation-only.
It must never be used as a broker execution surface.
"""

from .academy import (
    AcademyProgression,
    Achievement,
    DecisionAction,
    DecisionOutcome,
    Lesson,
    LessonProgress,
    LessonStatus,
    RecommendationDecision,
    default_challenge_catalog,
)
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
from .projection import build_simulator_projection

__all__ = [
    "AcademyProgression",
    "AcademyScorer",
    "Achievement",
    "ChallengeDefinition",
    "ChallengeProgress",
    "ChallengeType",
    "DecisionAction",
    "DecisionOutcome",
    "ForecastAssessment",
    "Lesson",
    "LessonProgress",
    "LessonStatus",
    "RecommendationDecision",
    "SimulatedFill",
    "SimulatedPortfolio",
    "SimulatedPosition",
    "SimulationEngine",
    "SimulationScore",
    "build_simulator_projection",
    "default_challenge_catalog",
]
