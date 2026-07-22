"""
Read-only subsystem health validation for production certification.
"""

from typing import Any, Callable, Dict, List, Optional, Tuple

from backend.certification.readiness_models import (
    CRITICAL,
    FAIL,
    INFO,
    PASS,
    WARNING,
    ReadinessFinding,
    SubsystemReadiness,
    clamp_score,
)


class HealthValidator:
    """
    Evaluates enterprise subsystem health using read-only service methods.
    """

    def validate(
        self,
        read_model: Any = None,
        event_bus: Any = None,
        dashboard_service: Any = None,
    ) -> Tuple[List[SubsystemReadiness], List[ReadinessFinding]]:
        health = self._safe_call(read_model, "get_enterprise_health", default={})
        metrics = self._safe_nested_call(read_model, "metrics_service", "get_current_metrics", default={})
        report_status = self._safe_call(read_model, "get_report_status", default={})
        runtime_status = self._safe_call(read_model, "get_runtime_status", default="UNKNOWN")
        operations_summary = self._safe_nested_call(
            read_model, "visibility_layer", "get_operations_summary", default={}
        )
        notification_summary = self._safe_nested_call(
            read_model, "visibility_layer", "get_notification_summary", default={}
        )
        recent_events = self._safe_call(read_model, "get_recent_events", default=[], limit=20)

        findings: List[ReadinessFinding] = []
        subsystems = [
            self._component(
                "Enterprise Event Bus",
                self._event_bus_score(event_bus, recent_events, findings),
                {"recent_events_sampled": len(recent_events or [])},
            ),
            self._component(
                "Notification Framework",
                self._health_score(health, "notification_health", findings, "Notification Framework"),
                notification_summary,
            ),
            self._component(
                "Reporting Framework",
                self._reporting_score(health, report_status, findings),
                report_status,
            ),
            self._component(
                "Operations Framework",
                self._operations_score(health, operations_summary, findings),
                operations_summary,
            ),
            self._component(
                "Metrics & Telemetry",
                self._metrics_score(health, metrics, findings),
                {"metrics_count": len(metrics or {}), "overall_health": health.get("overall_health_score")},
            ),
            self._component(
                "Dashboard Availability",
                self._dashboard_score(read_model, findings),
                {"read_model_available": read_model is not None},
            ),
            self._component(
                "Event Subscription Integrity",
                self._subscription_score(event_bus, health, findings),
                self._subscription_snapshot(event_bus),
            ),
            self._component(
                "Runtime Supervisor",
                self._runtime_score(health, runtime_status, findings),
                {"runtime_status": runtime_status, "runtime_health": health.get("runtime_health")},
            ),
            self._component(
                "Executive Dashboard",
                self._executive_dashboard_score(dashboard_service, read_model, findings),
                {"dashboard_service_available": dashboard_service is not None},
            ),
        ]

        return subsystems, findings

    def _component(self, name: str, score: float, details: Dict[str, Any]) -> SubsystemReadiness:
        score = clamp_score(score)
        if score < 70.0:
            status = FAIL
        elif score < 90.0:
            status = WARNING
        else:
            status = PASS
        return SubsystemReadiness(name=name, score=score, status=status, details=details or {})

    def _health_score(
        self,
        health: Dict[str, Any],
        key: str,
        findings: List[ReadinessFinding],
        subsystem: str,
    ) -> float:
        if not isinstance(health, dict) or key not in health:
            findings.append(
                ReadinessFinding(
                    CRITICAL,
                    subsystem,
                    f"{subsystem} health score is not available from telemetry.",
                    "Confirm telemetry wiring before production deployment.",
                )
            )
            return 0.0

        score = clamp_score(health[key])
        if score < 70.0:
            findings.append(
                ReadinessFinding(
                    CRITICAL,
                    subsystem,
                    f"{subsystem} health is failing at {score:.1f}.",
                    f"Restore {subsystem.lower()} before deployment.",
                )
            )
        elif score < 90.0:
            findings.append(
                ReadinessFinding(
                    WARNING,
                    subsystem,
                    f"{subsystem} health is degraded at {score:.1f}.",
                    f"Review {subsystem.lower()} telemetry and recent errors.",
                )
            )
        return score

    def _event_bus_score(
        self,
        event_bus: Any,
        recent_events: List[Any],
        findings: List[ReadinessFinding],
    ) -> float:
        if event_bus is not None and hasattr(event_bus, "publish") and hasattr(event_bus, "subscribe"):
            return 100.0
        if recent_events:
            findings.append(
                ReadinessFinding(
                    WARNING,
                    "Enterprise Event Bus",
                    "Event bus instance was not supplied, but persisted events are readable.",
                    "Provide the active EventBus when certification runs in-process.",
                )
            )
            return 85.0
        findings.append(
            ReadinessFinding(
                CRITICAL,
                "Enterprise Event Bus",
                "No active event bus instance or persisted event sample was available.",
                "Verify event persistence and bus wiring during deployment rehearsal.",
            )
        )
        return 0.0

    def _reporting_score(
        self,
        health: Dict[str, Any],
        report_status: Dict[str, Any],
        findings: List[ReadinessFinding],
    ) -> float:
        score = self._health_score(health, "reporting_health", findings, "Reporting Framework")
        if not report_status:
            findings.append(
                ReadinessFinding(
                    CRITICAL,
                    "Reporting Framework",
                    "Report status data is unavailable.",
                    "Confirm report history is readable before deployment.",
                )
            )
            return min(score, 0.0)
        return score

    def _operations_score(
        self,
        health: Dict[str, Any],
        operations_summary: Dict[str, Any],
        findings: List[ReadinessFinding],
    ) -> float:
        score = self._health_score(health, "operations_health", findings, "Operations Framework")
        status = str(operations_summary.get("overall_status", "UNKNOWN")).upper()
        if status in ("CRITICAL", "FAILED", "FAIL"):
            findings.append(
                ReadinessFinding(
                    CRITICAL,
                    "Operations Framework",
                    f"Operations status is {status}.",
                    "Resolve operations control centre failures before deployment.",
                )
            )
            return min(score, 50.0)
        if status in ("DEGRADED", "WARN", "WARNING"):
            findings.append(
                ReadinessFinding(
                    WARNING,
                    "Operations Framework",
                    f"Operations status is {status}.",
                    "Review operational timeline warnings before deployment.",
                )
            )
            return min(score, 85.0)
        return score

    def _metrics_score(
        self,
        health: Dict[str, Any],
        metrics: Dict[str, Any],
        findings: List[ReadinessFinding],
    ) -> float:
        score = self._health_score(health, "overall_health_score", findings, "Metrics & Telemetry")
        if not metrics:
            findings.append(
                ReadinessFinding(
                    CRITICAL,
                    "Metrics & Telemetry",
                    "Metrics counters are empty or unavailable.",
                    "Confirm telemetry collectors are registered during deployment rehearsal.",
                )
            )
            return min(score, 0.0)
        return score

    def _dashboard_score(self, read_model: Any, findings: List[ReadinessFinding]) -> float:
        required_methods = ("get_enterprise_health", "get_runtime_status", "get_report_status")
        if read_model is None:
            findings.append(
                ReadinessFinding(
                    CRITICAL,
                    "Dashboard Availability",
                    "Dashboard read model was not supplied.",
                    "Wire DashboardReadModel into certification for production dashboard checks.",
                )
            )
            return 0.0
        missing = [name for name in required_methods if not hasattr(read_model, name)]
        if missing:
            findings.append(
                ReadinessFinding(
                    WARNING,
                    "Dashboard Availability",
                    f"Dashboard read model is missing read methods: {', '.join(missing)}.",
                    "Restore dashboard read model contract before production deployment.",
                )
            )
            return 80.0
        return 100.0

    def _subscription_score(
        self,
        event_bus: Any,
        health: Dict[str, Any],
        findings: List[ReadinessFinding],
    ) -> float:
        if event_bus is None:
            findings.append(
                ReadinessFinding(
                    CRITICAL,
                    "Event Subscription Integrity",
                    "Active EventBus was not supplied for subscription inspection.",
                    "Run certification in-process to verify subscriber registrations.",
                )
            )
            return 0.0

        snapshot = self._subscription_snapshot(event_bus)
        specific_count = snapshot.get("specific_subscriber_count", 0)
        wildcard_count = snapshot.get("wildcard_subscriber_count", 0)
        if specific_count + wildcard_count == 0:
            findings.append(
                ReadinessFinding(
                    WARNING,
                    "Event Subscription Integrity",
                    "EventBus has no registered subscribers.",
                    "Wire notification, reporting, operations, and metrics subscribers.",
                )
            )
            return 75.0

        failures = float(health.get("subscriber_failures", 0) or 0)
        if failures:
            findings.append(
                ReadinessFinding(
                    WARNING,
                    "Event Subscription Integrity",
                    f"Subscriber failure count is {failures:.0f}.",
                    "Review failing event subscribers before deployment.",
                )
            )
            return 85.0
        return 100.0

    def _runtime_score(
        self,
        health: Dict[str, Any],
        runtime_status: str,
        findings: List[ReadinessFinding],
    ) -> float:
        score = self._health_score(health, "runtime_health", findings, "Runtime Supervisor")
        status = str(runtime_status or "UNKNOWN").upper()
        if status in ("CRITICAL", "FAILED", "FAIL", "STOPPED"):
            findings.append(
                ReadinessFinding(
                    CRITICAL,
                    "Runtime Supervisor",
                    f"Runtime supervisor status is {status}.",
                    "Restore runtime supervisor before production deployment.",
                )
            )
            return min(score, 50.0)
        if status in ("UNKNOWN", "DEGRADED"):
            findings.append(
                ReadinessFinding(
                    WARNING if status == "DEGRADED" else CRITICAL,
                    "Runtime Supervisor",
                    f"Runtime supervisor status is {status}.",
                    "Confirm runtime state during deployment readiness review.",
                )
            )
            return min(score, 69.0 if status == "DEGRADED" else 0.0)
        return score

    def _executive_dashboard_score(
        self,
        dashboard_service: Any,
        read_model: Any,
        findings: List[ReadinessFinding],
    ) -> float:
        if dashboard_service is None:
            findings.append(
                ReadinessFinding(
                    CRITICAL if read_model is None else WARNING,
                    "Executive Dashboard",
                    "Dashboard service was not supplied; read model availability was checked instead.",
                    "Pass DashboardService to include endpoint-level dashboard certification.",
                )
            )
            return 85.0 if read_model is not None else 0.0
        if not hasattr(dashboard_service, "get_executive_summary"):
            findings.append(
                ReadinessFinding(
                    WARNING,
                    "Executive Dashboard",
                    "Dashboard service is missing get_executive_summary.",
                    "Restore executive dashboard service contract.",
                )
            )
            return 80.0
        return 100.0

    def _subscription_snapshot(self, event_bus: Any) -> Dict[str, Any]:
        if event_bus is None:
            return {"specific_subscriber_count": 0, "wildcard_subscriber_count": 0}
        subscribers = getattr(event_bus, "_subscribers", {}) or {}
        wildcard = getattr(event_bus, "_wildcard_subscribers", []) or []
        return {
            "specific_event_types": sorted(subscribers.keys()),
            "specific_subscriber_count": sum(len(items) for items in subscribers.values()),
            "wildcard_subscriber_count": len(wildcard),
        }

    def _safe_call(self, target: Any, method_name: str, default: Any = None, **kwargs: Any) -> Any:
        if target is None or not hasattr(target, method_name):
            return default
        method = getattr(target, method_name)
        try:
            return method(**kwargs)
        except TypeError:
            return method()
        except Exception:
            return default

    def _safe_nested_call(
        self,
        target: Any,
        attr_name: str,
        method_name: str,
        default: Any = None,
    ) -> Any:
        nested = getattr(target, attr_name, None) if target is not None else None
        return self._safe_call(nested, method_name, default=default)
