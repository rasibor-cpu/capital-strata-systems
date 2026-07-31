"""DIP-004 Enterprise Edge Intelligence.

Offline, deterministic, advisory-only edge discovery, evaluation, registry,
and reporting over historical Trade DNA and derived metrics.
"""

from __future__ import annotations

from backend.intelligence.edge_intelligence.discovery import EdgeDiscoveryEngine
from backend.intelligence.edge_intelligence.evaluation import EdgeEvaluator, EvidenceThresholdPolicy
from backend.intelligence.edge_intelligence.models import (
    EDGE_ANALYSIS_VERSION,
    EDGE_REGISTRY_VERSION,
    EdgeCandidate,
    EdgeDefinition,
    EdgeEvaluation,
    EdgeExplanation,
    EdgeRecord,
)
from backend.intelligence.edge_intelligence.registry import EdgeRegistry
from backend.intelligence.edge_intelligence.reporting import EdgeReportBuilder

__all__ = [
    "EDGE_ANALYSIS_VERSION",
    "EDGE_REGISTRY_VERSION",
    "EdgeCandidate",
    "EdgeDefinition",
    "EdgeDiscoveryEngine",
    "EdgeEvaluation",
    "EdgeEvaluator",
    "EdgeExplanation",
    "EdgeRecord",
    "EdgeRegistry",
    "EdgeReportBuilder",
    "EvidenceThresholdPolicy",
]
