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
from backend.executive_intelligence.service import ExecutiveIntelligenceEngine

__all__ = [
    "ARCHIVE_SCHEMA_VERSION",
    "BRIEF_SCHEMA_VERSION",
    "PLATFORM_CONTRACT",
    "SAFETY_LOCKS",
    "ExecutiveIntelligenceEngine",
]
