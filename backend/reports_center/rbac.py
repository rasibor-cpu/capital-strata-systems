"""Reports Center RBAC — server-side authorization."""

from __future__ import annotations

from typing import Any

from backend.security.permissions import PermissionEngine

# Core permissions (also mirrored onto ADMIN/SUPER_USER in permissions.py)
PERM_VIEW = "reports_view"
PERM_GENERATE = "reports_generate"
PERM_ADMIN = "reports_admin"
PERM_PRINT_ALL = "reports_print_all"
PERM_EXPORT = "reports_export"
PERM_AUDIT = "reports_audit_view"

# Family / type print grants (staff may receive these explicitly)
PRINT_PERMS = {
    "executive_brief_print",
    "transaction_ticket_print",
    "trade_journal_print",
    "account_statement_print",
    "portfolio_report_print",
    "risk_report_print",
    PERM_PRINT_ALL,
}

ADMIN_ROLES = {"ADMIN", "SUPER_USER"}


class ReportsAccessControl:
    def __init__(self, engine: PermissionEngine | None = None) -> None:
        self.engine = engine or PermissionEngine()

    def _has(self, role: str, action: str) -> bool:
        role_u = str(role or "").upper()
        # Legacy alias
        if action == PERM_VIEW and self.engine.check(role_u, "view_reports").allowed:
            return True
        return bool(self.engine.check(role_u, action).allowed)

    def can_view_catalog(self, role: str) -> bool:
        return self._has(role, PERM_VIEW) or str(role or "").upper() in ADMIN_ROLES

    def can_view_report(self, role: str, required: str) -> bool:
        role_u = str(role or "").upper()
        if role_u in ADMIN_ROLES:
            return True
        return self._has(role_u, required) or self._has(role_u, PERM_VIEW)

    def can_generate(self, role: str, required: str) -> bool:
        role_u = str(role or "").upper()
        if role_u in ADMIN_ROLES:
            return True
        return self._has(role_u, required) or self._has(role_u, PERM_GENERATE)

    def can_print(self, role: str, required: str, *, staff_grants: set[str] | None = None) -> bool:
        role_u = str(role or "").upper()
        if role_u in ADMIN_ROLES:
            return True
        if self._has(role_u, PERM_PRINT_ALL):
            return True
        if required and self._has(role_u, required):
            return True
        grants = staff_grants or set()
        if required and required in grants:
            return True
        return False

    def can_export(self, role: str) -> bool:
        role_u = str(role or "").upper()
        return role_u in ADMIN_ROLES or self._has(role_u, PERM_EXPORT)

    def can_view_audit(self, role: str) -> bool:
        role_u = str(role or "").upper()
        return role_u in ADMIN_ROLES or self._has(role_u, PERM_AUDIT) or self._has(role_u, "view_audit_logs")

    def can_email(self, role: str, required: str) -> bool:
        """Default EMAIL_DISABLED. Executive brief uses Phase 175 permission only."""
        if not required:
            return False
        role_u = str(role or "").upper()
        if required == "executive_brief_email":
            return role_u in ADMIN_ROLES and self._has(role_u, "executive_brief_email")
        return False

    def authorization_status(self, role: str, user_id: str = "") -> dict[str, Any]:
        role_u = str(role or "").upper()
        return {
            "user_id": user_id,
            "role": role_u,
            "reports_view": self.can_view_catalog(role_u),
            "reports_generate": self.can_generate(role_u, PERM_GENERATE),
            "reports_admin": role_u in ADMIN_ROLES or self._has(role_u, PERM_ADMIN),
            "reports_print_all": self.can_print(role_u, PERM_PRINT_ALL),
            "reports_export": self.can_export(role_u),
            "reports_audit_view": self.can_view_audit(role_u),
            "executive_brief_email": self.can_email(role_u, "executive_brief_email"),
            "email_default_policy": "EMAIL_DISABLED",
        }
