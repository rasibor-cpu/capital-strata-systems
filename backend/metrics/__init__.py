"""
CSS Observability & Metrics Subsystem (EWP-2D)

Exposes the MetricsService and its related telemetry and health classes.
It also provides default singleton instances for convenience.
"""

from backend.metrics.metrics_snapshot import MetricsSnapshot
from backend.metrics.metrics_registry import MetricsRegistry
from backend.metrics.telemetry import TelemetryCollector
from backend.metrics.health_metrics import HealthEvaluator
from backend.metrics.metrics_history import MetricsHistory
from backend.metrics.metrics_service import MetricsService

# Instantiate default singletons
_default_registry = MetricsRegistry()
_default_telemetry = TelemetryCollector()
_default_history = MetricsHistory()
_default_service = MetricsService(
    registry=_default_registry,
    telemetry=_default_telemetry,
    history=_default_history
)

def get_default_metrics_service() -> MetricsService:
    """Get the default MetricsService singleton."""
    return _default_service
