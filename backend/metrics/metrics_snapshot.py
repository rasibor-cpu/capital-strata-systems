"""
Observability Snapshot for CSS Enterprise Telemetry Subsystem

Defines the consolidated MetricsSnapshot class.
"""

from dataclasses import dataclass, field
from typing import Dict, Any
import time

@dataclass
class MetricsSnapshot:
    """
    Consolidated Enterprise Observability Snapshot.
    
    Responsibility: Bundle structured metrics, telemetry, and health states.
    Thread-safety: Immutable fields by design, safe.
    """
    timestamp: float = field(default_factory=time.time)
    schema_version: str = "1.0.0"
    metrics: Dict[str, int] = field(default_factory=dict)
    telemetry: Dict[str, Any] = field(default_factory=dict)
    health: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert snapshot instance to dictionary format."""
        return {
            "timestamp": self.timestamp,
            "schema_version": self.schema_version,
            "metrics": dict(self.metrics),
            "telemetry": dict(self.telemetry),
            "health": dict(self.health)
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MetricsSnapshot":
        """Construct snapshot instance from dictionary format."""
        return cls(
            timestamp=data.get("timestamp", time.time()),
            schema_version=data.get("schema_version", "1.0.0"),
            metrics=dict(data.get("metrics", {})),
            telemetry=dict(data.get("telemetry", {})),
            health=dict(data.get("health", {}))
        )
