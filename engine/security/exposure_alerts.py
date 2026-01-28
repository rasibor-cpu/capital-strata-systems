"""
Exposure Alerts (v1)
--------------------
Alert chain for exposure / limit breaches:

1) Trader/User
2) Supervisor
3) Department Head

V1 delivery:
- Console output (operator visibility)
- SupervisorAlerts service integration (SYSTEM audit + console)

Later:
- Email/SMS/Slack/Webhook
- Escalation timing + rate limiting
"""

from dataclasses import dataclass
from typing import Optional, Dict, Any

from engine.security.supervisor_alerts import SupervisorAlertService, SupervisorAlert
from engine.security.audit_log import AuditLogger, AuditEventType


@dataclass
class ExposureAlertEvent:
    alert_type: str  # TRADER_LIMIT_WARNING, TRADER_LIMIT_BREACH, INSTITUTIONAL_LIMIT_BREACH
    user_id: str
    session_id: Optional[str]
    scope_id: str
    currency: str
    proposed_amount: str
    reason: str
    meta: Dict[str, Any]


class ExposureAlertService:
    """
    Emits alerts in an escalation chain:
    - user -> supervisor -> department head

    v1: prints + writes audit SYSTEM events
    """

    def __init__(
        self,
        *,
        audit: AuditLogger,
        supervisor_alerts: SupervisorAlertService,
    ):
        self.audit = audit
        self.supervisor_alerts = supervisor_alerts

    def notify_user(self, evt: ExposureAlertEvent) -> None:
        self.audit.log(
            event_type=AuditEventType.SYSTEM,
            user_id=evt.user_id,
            role=None,
            session_id=evt.session_id,
            screen="RISK",
            action="ALERT_USER",
            resource=evt.scope_id,
            success=False,
            reason=evt.reason,
            meta={"alert_type": evt.alert_type, **evt.meta},
        )

        print("=" * 72)
        print("[EXPOSURE ALERT - USER]")
        print(f"User      : {evt.user_id}")
        print(f"Scope     : {evt.scope_id}")
        print(f"Currency  : {evt.currency}")
        print(f"Proposed  : {evt.proposed_amount}")
        print(f"Reason    : {evt.reason}")
        print("=" * 72)

    def notify_supervisor(self, evt: ExposureAlertEvent) -> None:
        # This uses existing supervisor alert pipeline
        self.supervisor_alerts.notify(
            SupervisorAlert(
                alert_type=evt.alert_type,
                user_id=evt.user_id,
                role="SUPERVISOR_NOTIFY",
                session_id=evt.session_id,
                screen="RISK",
                action="ALERT_SUPERVISOR",
                resource=evt.scope_id,
                reason=evt.reason,
                meta={"currency": evt.currency, "proposed_amount": evt.proposed_amount, **evt.meta},
            )
        )

    def notify_department_head(self, evt: ExposureAlertEvent) -> None:
        # v1: audit + console (later: email/SMS)
        self.audit.log(
            event_type=AuditEventType.SYSTEM,
            user_id=evt.user_id,
            role=None,
            session_id=evt.session_id,
            screen="RISK",
            action="ALERT_DEPT_HEAD",
            resource=evt.scope_id,
            success=False,
            reason=evt.reason,
            meta={"alert_type": evt.alert_type, **evt.meta},
        )

        print("=" * 72)
        print("[EXPOSURE ALERT - DEPARTMENT HEAD]")
        print(f"User      : {evt.user_id}")
        print(f"Scope     : {evt.scope_id}")
        print(f"Currency  : {evt.currency}")
        print(f"Proposed  : {evt.proposed_amount}")
        print(f"Reason    : {evt.reason}")
        print("=" * 72)

    def escalate_all(self, evt: ExposureAlertEvent) -> None:
        """
        Executes full escalation chain.
        """
        self.notify_user(evt)
        self.notify_supervisor(evt)
        self.notify_department_head(evt)