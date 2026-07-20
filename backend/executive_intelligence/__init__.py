# Phase 174 — CSS Executive Intelligence Engine
# Canonical producer of the Daily Executive Brief (DEB) / ExecutiveMorningBrief.
# Advisory-only. Fail-closed. Architecture Freeze v1.0 compliant.

"""Executive Intelligence Engine public surface."""

from backend.executive_intelligence.constants import (
    ARCHIVE_SCHEMA_VERSION,
    BRIEF_SCHEMA_VERSION,
    PLATFORM_CONTRACT,
    SAFETY_LOCKS,
)
from backend.executive_intelligence.orchestrator import ExecutiveBriefReadinessOrchestrator
from backend.executive_intelligence.readiness import ExecutiveBriefReadinessEvaluator
from backend.executive_intelligence.service import ExecutiveIntelligenceEngine

# Phase 178 — optional read-only financial provider for EI consumers
from backend.executive_reporting.ei_adapter import executive_intelligence_financial_provider  # noqa: F401

__all__ = [
    "ARCHIVE_SCHEMA_VERSION",
    "BRIEF_SCHEMA_VERSION",
    "PLATFORM_CONTRACT",
    "SAFETY_LOCKS",
    "ExecutiveBriefReadinessEvaluator",
    "ExecutiveBriefReadinessOrchestrator",
    "ExecutiveIntelligenceEngine",
    "executive_intelligence_financial_provider",
]
