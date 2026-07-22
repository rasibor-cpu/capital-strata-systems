"""
Operations Service for CSS Operations Control Centre

Orchestrates component diagnostic execution, weighted health scoring,
system state persistence, and timeline history log appending.
"""

from typing import Optional
from backend.events.event_models import Event
from backend.common.configuration import OperationsConfig
from backend.common.exceptions import ValidationException
from backend.common.logger import get_logger
from backend.operations.operations_models import (
    create_state_event,
    create_timeline_event,
)
from backend.operations.health_monitor import HealthMonitor
from backend.operations.operational_state_manager import OperationalStateManager
from backend.operations.operational_timeline import OperationalTimeline
from backend.operations.runtime_statistics import RuntimeStatistics

logger = get_logger("css.operations.service")

class OperationsService:
    """
    Primary service orchestrating system diagnostics and timelines.
    Supports dependency injection and manages operations flows.
    
    Responsibility: Orchestrate diagnostic execution, weighted health scoring, system state persistence, timeline logs, and runtime stats.
    Dependencies: OperationsConfig, HealthMonitor, OperationalStateManager, OperationalTimeline, RuntimeStatistics
    Thread-safety: Synchronization should be handled by caller or sub-components.
    Integration: Exposes interfaces for supervisor checks and status dashboards.
    """
    def __init__(
        self,
        config: OperationsConfig,
        monitor: HealthMonitor,
        state_manager: OperationalStateManager,
        timeline: OperationalTimeline,
        statistics: RuntimeStatistics
    ):
        config.validate()
        self.config = config
        self.monitor = monitor
        self.state_manager = state_manager
        self.timeline = timeline
        self.statistics = statistics

    def record_timeline_event(self, event_type: str, severity: str, message: str, details: dict = None) -> Event:
        """Create and append a timeline event to the history log."""
        event = create_timeline_event(
            event_type=event_type,
            severity=severity,
            message=message,
            details=details
        )
        event.source = self.config.default_source
        event.validate()
        self.timeline.append(event)
        return event

    def run_diagnostics(self) -> Event:
        """
        Execute component health checks, aggregate statuses, and compute weighted health score.
        Persists state updates. Logs to timeline if overall status changes.
        """
        current_state_list = self.state_manager.load()
        old_status = "HEALTHY"
        if current_state_list:
            old_status = current_state_list[0].payload.get("overall_status", "HEALTHY")

        results = self.monitor.execute_checks()
        health_score = self.monitor.calculate_health_score(results)

        # Determine overall status — fail-closed when no checkers ran.
        statuses = [r.payload.get("status", "OK").upper() for r in results]
        if not results:
            new_status = "CRITICAL"
        elif "CRITICAL" in statuses:
            new_status = "CRITICAL"
        elif "WARN" in statuses or "WARNING" in statuses:
            new_status = "DEGRADED"
        else:
            new_status = "HEALTHY"

        component_states = {r.payload.get("component"): r.payload.get("status") for r in results}
        state_event = create_state_event(
            overall_status=new_status,
            health_score=health_score,
            component_states=component_states
        )
        state_event.source = self.config.default_source
        state_event.validate()

        # Persist updated state
        self.state_manager.append(state_event)

        # Log to timeline if status changes
        if new_status != old_status:
            timeline_event = self.record_timeline_event(
                event_type="STATE_CHANGE",
                severity="WARNING" if new_status == "DEGRADED" else ("CRITICAL" if new_status == "CRITICAL" else "INFO"),
                message=f"System status transitioned from {old_status} to {new_status} (Score: {health_score:.1f})",
                details={"old_status": old_status, "new_status": new_status, "health_score": health_score}
            )

        logger.info(f"Diagnostics complete. Status: {new_status} | Score: {health_score:.1f}")
        return state_event

    def handle_event(self, event: Event) -> None:
        """Passive event bus subscriber callback for Operations Control Centre."""
        try:
            # Log to operational timeline if it is a system status, trade outcome, or critical warning event
            if event.category == "SYSTEM" or event.severity in ("WARNING", "CRITICAL"):
                self.record_timeline_event(
                    event_type=event.event_type,
                    severity=event.severity,
                    message=f"Event Bus Logged: {event.event_type} - {event.source}",
                    details=event.payload
                )
            # Accumulate runtime stats
            self.statistics.increment("messages")
            if event.severity == "CRITICAL":
                self.statistics.increment("errors")
        except Exception as e:
            logger.error(f"Error in OperationsService handle_event: {e}")

