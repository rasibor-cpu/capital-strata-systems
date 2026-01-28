"""
Access Control (v1)
------------------
Central authorization gate for screens, actions, and resources.

Design:
- Explicit allow/deny
- Denials are always audited
- Denials always trigger supervisor alert
- Business logic stays clean (returns True/False)
"""

from typing import Optional, Set, Dict, Any

from engine.security.audit_log import (
    AuditLogger,
    AuditEventType,
    log_access_denied,
)
from engine.security.supervisor_alerts import (
    SupervisorAlert,
    SupervisorAlertService,
)


class AccessPolicy:
    """
    Simple RBAC-style access policy (v1).

    Later:
    - Attribute-based access control (ABAC)
    - Time-based rules
    - Geo/IP rules
    """

    def __init__(
        self,
        *,
        allowed_screens: Optional[Set[str]] = None,
        allowed_actions: Optional[Set[str]] = None,
        allowed_resources: Optional[Set[str]] = None,
    ):
        self.allowed_screens = allowed_screens or set()
        self.allowed_actions = allowed_actions or set()
        self.allowed_resources = allowed_resources or set()

    def allows(
        self,
        *,
        screen: Optional[str],
        action: Optional[str],
        resource: Optional[str],
    ) -> bool:
        if screen and self.allowed_screens and screen not in self.allowed_screens:
            return False
        if action and self.allowed_actions and action not in self.allowed_actions:
            return False
        if resource and self.allowed_resources and resource not in self.allowed_resources:
            return False
        return True


class AccessController:
    """
    Authorization + audit + alert orchestration.
    """

    def __init__(
        self,
        *,
        audit: AuditLogger,
        alert_service: SupervisorAlertService,
        policies_by_role: Dict[str, AccessPolicy],
    ):
        self.audit = audit
        self.alerts = alert_service
        self.policies_by_role = policies_by_role

    def check(
        self,
        *,
        user_id: Optional[str],
        role: Optional[str],
        session_id: Optional[str],
        screen: Optional[str],
        action: Optional[str],
        resource: Optional[str],
        ip_address: Optional[str] = None,
        device: Optional[str] = None,
        meta: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        Returns True if allowed, False if denied (with audit + alert).
        """
        policy = self.policies_by_role.get(role or "")

        if policy and policy.allows(
            screen=screen,
            action=action,
            resource=resource,
        ):
            return True

        # ── DENIED ─────────────────────────────
        reason = "Unauthorized access attempt"

        # 1) Audit log
        log_access_denied(
            self.audit,
            user_id=user_id,
            role=role,
            session_id=session_id,
            screen=screen,
            action=action,
            resource=resource,
            reason=reason,
            ip_address=ip_address,
            device=device,
            meta=meta or {},
        )

        # 2) Supervisor alert
        alert = SupervisorAlert(
            alert_type="UNAUTHORIZED_ACCESS",
            user_id=user_id,
            role=role,
            session_id=session_id,
            screen=screen,
            action=action,
            resource=resource,
            reason=reason,
            meta=meta or {},
        )
        self.alerts.notify(alert)

        return False