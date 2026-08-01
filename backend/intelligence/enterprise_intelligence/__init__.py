"""DIP-005 Enterprise Intelligence Suite.

Offline, deterministic, advisory-only capital intelligence, executive
intelligence, and enterprise reporting over historical Trade DNA, derived
metrics, and Edge Intelligence records.
"""

from __future__ import annotations

from backend.intelligence.enterprise_intelligence.capital import CapitalIntelligenceEngine
from backend.intelligence.enterprise_intelligence.executive import ExecutiveIntelligenceEngine
from backend.intelligence.enterprise_intelligence.models import (
    ENTERPRISE_INTELLIGENCE_VERSION,
    ENTERPRISE_REPORT_SCHEMA_VERSION,
    ENTERPRISE_REPORT_VERSION,
    CapitalIntelligenceReport,
    EnterpriseIntelligenceReport,
    ExecutiveIntelligenceSummary,
)
from backend.intelligence.enterprise_intelligence.reporting import EnterpriseReportBuilder

__all__ = [
    "ENTERPRISE_INTELLIGENCE_VERSION",
    "ENTERPRISE_REPORT_SCHEMA_VERSION",
    "ENTERPRISE_REPORT_VERSION",
    "CapitalIntelligenceEngine",
    "CapitalIntelligenceReport",
    "EnterpriseIntelligenceReport",
    "EnterpriseReportBuilder",
    "ExecutiveIntelligenceEngine",
    "ExecutiveIntelligenceSummary",
]
