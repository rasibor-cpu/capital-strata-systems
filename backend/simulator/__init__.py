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
from .mobile_contract import API_SCHEMA_VERSION, build_phone_preview_contract
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
from .readiness import ReadinessAssessment, ReadinessEngine, ReadinessLevel
from .replay import (
    CheckpointResult,
    CheckpointState,
    RecommendationCheckpoint,
    RecommendationReplayEngine,
    ReplayScore,
)
from .scenarios import Scenario, default_scenario_catalog, get_scenario
from .session import SimulatorSession, SimulatorSessionState

__all__ = [
    "API_SCHEMA_VERSION",
    "AcademyProgression",
    "AcademyScorer",
    "Achievement",
    "BenchmarkEngine",
    "BenchmarkResult",
    "ChallengeDefinition",
    "ChallengeProgress",
    "ChallengeType",
    "CheckpointResult",
    "CheckpointState",
    "DecisionAction",
    "DecisionOutcome",
    "ForecastAssessment",
    "LearnerProfile",
    "LearnerProfileStore",
    "Lesson",
    "LessonProgress",
    "LessonStatus",
    "ReadinessAssessment",
    "ReadinessEngine",
    "ReadinessLevel",
    "RecommendationCheckpoint",
    "RecommendationDecision",
    "RecommendationReplayEngine",
    "ReplayScore",
    "Scenario",
    "SimulatedFill",
    "SimulatedPortfolio",
    "SimulatedPosition",
    "SimulationEngine",
    "SimulationScore",
    "SimulatorSession",
    "SimulatorSessionState",
    "build_phone_preview_contract",
    "build_simulator_projection",
    "default_challenge_catalog",
    "default_scenario_catalog",
    "get_scenario",
]
