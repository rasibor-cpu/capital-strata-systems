from enum import Enum
import logging
from typing import Dict, Any, Optional

from backend.monitoring.css_alert_models import AlertSeverity
from backend.monitoring.css_alert_service import CSSAlertService

logger = logging.getLogger(__name__)


class AlertEventType(Enum):
    PROFIT_TARGET_REACHED = "PROFIT_TARGET_REACHED"
    DRAWDOWN_BREACHED = "DRAWDOWN_BREACHED"
    LIVE_MODE_ARMED = "LIVE_MODE_ARMED"
    BROKER_CONNECTION_FAILURE = "BROKER_CONNECTION_FAILURE"
    TRADE_BLOCKED = "TRADE_BLOCKED"
    EMERGENCY_SHUTDOWN = "EMERGENCY_SHUTDOWN"
    ENGINE_HEARTBEAT_LOST = "ENGINE_HEARTBEAT_LOST"
    BROKER_CONNECTION_UNSTABLE = "BROKER_CONNECTION_UNSTABLE"
    RUNTIME_RECOVERY_ATTEMPT = "RUNTIME_RECOVERY_ATTEMPT"
    RUNTIME_RECOVERY_FAILED = "RUNTIME_RECOVERY_FAILED"
    INFO = "INFO"


_ALERT_SEVERITY_BY_EVENT = {
    AlertEventType.PROFIT_TARGET_REACHED: AlertSeverity.INFO,
    AlertEventType.DRAWDOWN_BREACHED: AlertSeverity.CRITICAL,
    AlertEventType.LIVE_MODE_ARMED: AlertSeverity.WARNING,
    AlertEventType.BROKER_CONNECTION_FAILURE: AlertSeverity.CRITICAL,
    AlertEventType.TRADE_BLOCKED: AlertSeverity.WARNING,
    AlertEventType.EMERGENCY_SHUTDOWN: AlertSeverity.CRITICAL,
    AlertEventType.ENGINE_HEARTBEAT_LOST: AlertSeverity.CRITICAL,
    AlertEventType.BROKER_CONNECTION_UNSTABLE: AlertSeverity.WARNING,
    AlertEventType.RUNTIME_RECOVERY_ATTEMPT: AlertSeverity.WARNING,
    AlertEventType.RUNTIME_RECOVERY_FAILED: AlertSeverity.CRITICAL,
    AlertEventType.INFO: AlertSeverity.INFO,
}


class AlertService:
    def __init__(self):
        self.history = []
        self._persistent_alerts = CSSAlertService()

    def dispatch_alert(
        self,
        event_type: AlertEventType,
        message: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Dispatches a fail-safe alert.

        This method must never raise to callers. It keeps the legacy in-memory
        history/console behavior and also persists alerts to runtime/alerts via
        CSSAlertService for unattended-operation visibility.
        """
        try:
            alert_payload = {
                "type": event_type.value,
                "message": message,
                "context": context or {},
            }
            self.history.append(alert_payload)

            print(f"[CSS ALERT] [{event_type.value}] {message}")
            if context:
                print(f"[CSS ALERT CONTEXT] {context}")

            severity = _ALERT_SEVERITY_BY_EVENT.get(
                event_type,
                AlertSeverity.INFO,
            )
            self._persistent_alerts.emit_system_alert(
                severity=severity,
                message=message,
                source="engine.information.alerts",
                metadata={
                    "event_type": event_type.value,
                    "context": context or {},
                },
            )

        except Exception as e:
            logger.error(f"Alert dispatch failed: {e}")


_GLOBAL_ALERT_SERVICE = AlertService()


def get_alert_service() -> AlertService:
    return _GLOBAL_ALERT_SERVICE
