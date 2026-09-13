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
from .benchmark import BenchmarkEngine, BenchmarkResult
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
from .profile import LearnerProfile, LearnerProfileStore
from .projection import build_simulator_projection
from .scenarios import Scenario, default_scenario_catalog, get_scenario
from .session import SimulatorSession, SimulatorSessionState

__all__ = [
    "AcademyProgression",
    "AcademyScorer",
    "Achievement",
    "BenchmarkEngine",
    "BenchmarkResult",
    "ChallengeDefinition",
    "ChallengeProgress",
    "ChallengeType",
    "DecisionAction",
    "DecisionOutcome",
    "ForecastAssessment",
    "LearnerProfile",
    "LearnerProfileStore",
    "Lesson",
    "LessonProgress",
    "LessonStatus",
    "RecommendationDecision",
    "Scenario",
    "SimulatedFill",
    "SimulatedPortfolio",
    "SimulatedPosition",
    "SimulationEngine",
    "SimulationScore",
    "SimulatorSession",
    "SimulatorSessionState",
    "build_simulator_projection",
    "default_challenge_catalog",
    "default_scenario_catalog",
    "get_scenario",
]
