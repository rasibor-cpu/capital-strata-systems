from enum import Enum
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

class AlertEventType(Enum):
    PROFIT_TARGET_REACHED = "PROFIT_TARGET_REACHED"
    DRAWDOWN_BREACHED = "DRAWDOWN_BREACHED"
    LIVE_MODE_ARMED = "LIVE_MODE_ARMED"
    BROKER_CONNECTION_FAILURE = "BROKER_CONNECTION_FAILURE"
    TRADE_BLOCKED = "TRADE_BLOCKED"
    EMERGENCY_SHUTDOWN = "EMERGENCY_SHUTDOWN"
    INFO = "INFO"

class AlertService:
    def __init__(self):
        self.history = []

    def dispatch_alert(self, event_type: AlertEventType, message: str, context: Optional[Dict[str, Any]] = None) -> None:
        """
        Dispatches a fail-safe alert. Never raises an exception to the caller.
        """
        try:
            alert_payload = {
                "type": event_type.value,
                "message": message,
                "context": context or {}
            }
            self.history.append(alert_payload)
            # Notification-provider neutral: just log/print for now
            print(f"[CSS ALERT] [{event_type.value}] {message}")
            if context:
                print(f"[CSS ALERT CONTEXT] {context}")
        except Exception as e:
            # Must never fail the caller
            logger.error(f"Alert dispatch failed: {e}")

_GLOBAL_ALERT_SERVICE = AlertService()

def get_alert_service() -> AlertService:
    return _GLOBAL_ALERT_SERVICE
