"""
Supervisor Alerts (v1)
----------------------
When unauthorized actions are attempted, we notify supervisors.

V1 behavior:
- Write an audit SYSTEM event (flag)
- Print to console (operator visibility)

Later upgrades:
- Email/SMS/Slack/Webhook
- Escalation policies
- Rate limiting
"""

from dataclasses import dataclass
from typing import Optional, Dict, Any

from engine.security.audit_log import AuditLogger, AuditEventType


@dataclass
class SupervisorAlert:
    alert_type: str  # UNAUTHORIZED_ACCESS, etc.
    user_id: Optional[str]
    role: Optional[str]
    session_id: Optional[str]
    screen: Optional[str]
    action: Optional[str]
    resource: Optional[str]
    reason: Optional[str]
    meta: Dict[str, Any]


class SupervisorAlertService:
    """
    V1 supervisor alert service.
    """

    def __init__(self, audit: AuditLogger):
        self.audit = audit

    def notify(self, alert: SupervisorAlert) -> None:
        # 1) Log as SYSTEM event
        self.audit.log(
            event_type=AuditEventType.SYSTEM,
            user_id=alert.user_id,
            role=alert.role,
            session_id=alert.session_id,
            screen=alert.screen,
            action=alert.action,
            resource=alert.resource,
            success=False,
            reason=alert.reason or "Supervisor alert",
            meta={
                "alert_type": alert.alert_type,
                **(alert.meta or {}),
            },
        )

        # 2) Console visibility (v1)
        print("=" * 72)
        print("[SUPERVISOR ALERT]")
        print(f"Type     : {alert.alert_type}")
        print(f"User     : {alert.user_id} ({alert.role})")
        print(f"Session  : {alert.session_id}")
        print(f"Screen   : {alert.screen}")
        print(f"Action   : {alert.action}")
        print(f"Resource : {alert.resource}")
        print(f"Reason   : {alert.reason}")
        print("=" * 72)