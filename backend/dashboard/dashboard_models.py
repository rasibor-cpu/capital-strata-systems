"""
Dashboard Models for CSS Executive Operations Platform
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any

@dataclass
class ExecutiveSummaryData:
    """
    Structured operational state snapshot of the entire enterprise.
    """
    enterprise_health_score: float = 100.0
    runtime_status: str = "UNKNOWN"
    engine_mode: str = "CONSERVATIVE"
    recent_events_count: int = 0
    active_alerts_count: int = 0
    outstanding_notifications_count: int = 0
    metrics_summary: Dict[str, Any] = field(default_factory=dict)
    subsystem_health: Dict[str, float] = field(default_factory=dict)
