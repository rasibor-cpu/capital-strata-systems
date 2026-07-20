"""
Phase 179 — Executive Decision Intelligence (EDI).

Orchestration and decision-support only.
Does NOT recalculate Phase 177 financial statements or Phase 178 package math.
Advisory-only. trading_impact=false. No execution authority.
"""

from backend.executive_decision_intelligence.service import (
    ExecutiveDecisionIntelligenceService,
    SCHEMA_VERSION,
)

__all__ = [
    "ExecutiveDecisionIntelligenceService",
    "SCHEMA_VERSION",
]
