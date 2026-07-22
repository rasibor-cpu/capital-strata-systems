"""
Enterprise Event Subscription Manager for CSS

Centralizes the registration, unregistration, and wiring of enterprise
subsystems to the canonical Event Bus.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional
from backend.events.event_bus import EventBus

if TYPE_CHECKING:
    from backend.notifications.notification_service import NotificationService
    from backend.reporting.reporting_service import ReportingService


class EventSubscriptionManager:
    """
    Central coordinator to connect services to the Event Bus.
    
    Responsibility: Wire subscribers and clean up subscriptions dynamically.
    Dependencies: EventBus, NotificationService, ReportingService, OperationsService
    Thread-safety: Fully synchronized, operations delegating to locked EventBus.
    """
    def __init__(self, event_bus: EventBus):
        self.event_bus = event_bus

    def wire_notification_service(self, service: NotificationService) -> None:
        """Subscribe NotificationService to relevant trading and runtime events."""
        event_types = [
            "TRADE_APPROVED",
            "TRADE_REJECTED",
            "RUNTIME_STARTED",
            "RUNTIME_STOPPED",
            "HEARTBEAT_LOST",
            "RECOVERY_STARTED",
            "RECOVERY_COMPLETE",
            "REPORT_GENERATED"
        ]
        for etype in event_types:
            self.event_bus.subscribe(etype, service.handle_event)

    def unwire_notification_service(self, service: NotificationService) -> None:
        """Unsubscribe NotificationService from trading and runtime events."""
        event_types = [
            "TRADE_APPROVED",
            "TRADE_REJECTED",
            "RUNTIME_STARTED",
            "RUNTIME_STOPPED",
            "HEARTBEAT_LOST",
            "RECOVERY_STARTED",
            "RECOVERY_COMPLETE",
            "REPORT_GENERATED"
        ]
        for etype in event_types:
            self.event_bus.unsubscribe(etype, service.handle_event)

    def wire_reporting_service(self, service: ReportingService) -> None:
        """Subscribe ReportingService to all events for indexing/archiving."""
        self.event_bus.subscribe("*", service.handle_event)

    def unwire_reporting_service(self, service: ReportingService) -> None:
        """Unsubscribe ReportingService from all events."""
        self.event_bus.unsubscribe("*", service.handle_event)

    def wire_operations_service(self, service: "OperationsService") -> None:
        """Subscribe OperationsService to runtime, trade, and risk events."""
        event_types = [
            "TRADE_APPROVED",
            "TRADE_REJECTED",
            "RUNTIME_STARTED",
            "RUNTIME_STOPPED",
            "HEARTBEAT_LOST",
            "RECOVERY_STARTED",
            "RECOVERY_COMPLETE",
            "CAPITAL_LIMIT",
            "MARGIN_WARNING"
        ]
        for etype in event_types:
            self.event_bus.subscribe(etype, service.handle_event)

    def unwire_operations_service(self, service: "OperationsService") -> None:
        """Unsubscribe OperationsService from runtime, trade, and risk events."""
        event_types = [
            "TRADE_APPROVED",
            "TRADE_REJECTED",
            "RUNTIME_STARTED",
            "RUNTIME_STOPPED",
            "HEARTBEAT_LOST",
            "RECOVERY_STARTED",
            "RECOVERY_COMPLETE",
            "CAPITAL_LIMIT",
            "MARGIN_WARNING"
        ]
        for etype in event_types:
            self.event_bus.unsubscribe(etype, service.handle_event)

    def wire_metrics_service(self, service) -> None:
        """Subscribe MetricsService to wildcard to monitor all event telemetry."""
        self.event_bus.subscribe("*", service.handle_event)

    def unwire_metrics_service(self, service) -> None:
        """Unsubscribe MetricsService from wildcard."""
        self.event_bus.unsubscribe("*", service.handle_event)
