"""
Health Monitor for CSS Operations Control Centre

Registers and executes health checkers, aggregating results and calculating system-wide health scores.
"""

from typing import List, Dict, Callable
from backend.events.event_models import Event
from backend.operations.operations_models import create_health_check_event

class HealthMonitor:
    """
    Orchestrates health checks and calculates numerical scores.
    
    Responsibility: Register callbacks, run diagnostic queries, and calculate overall system health index.
    Dependencies: backend.events.event_models.Event
    Thread-safety: Not thread-safe (should be synchronized by caller if checkers list changes).
    Integration: Polled by OperationsService.
    """
    def __init__(self):
        self._checkers: Dict[str, Callable[[], Event]] = {}

    def register_checker(self, component: str, checker: Callable[[], Event]) -> None:
        """Register a health checker callback for a component."""
        self._checkers[component] = checker

    def execute_checks(self) -> List[Event]:
        """Execute all registered checkers and return their result Events."""
        results = []
        for component, checker in self._checkers.items():
            try:
                result = checker()
                results.append(result)
            except Exception as e:
                # Wrap checker failure as a critical Event
                results.append(create_health_check_event(
                    component=component,
                    status="CRITICAL",
                    message=f"Health checker failed: {e}",
                    latency_ms=0.0
                ))
        return results

    def calculate_health_score(self, results: List[Event]) -> float:
        """
        Calculate a health score from 0.0 to 100.0 based on component health statuses.
        OK = 100, WARN = 50, CRITICAL = 0.
        """
        if not results:
            return 100.0

        total_weight = 0.0
        weighted_sum = 0.0
        for event in results:
            weight = 1.0
            total_weight += weight
            status = event.payload.get("status", "OK").upper()
            
            if status == "OK":
                weighted_sum += 100.0 * weight
            elif status == "WARN":
                weighted_sum += 50.0 * weight
            else:
                weighted_sum += 0.0 * weight

        return weighted_sum / total_weight
