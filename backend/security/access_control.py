from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Set


@dataclass
class AccessDecision:
    allowed: bool
    role: str
    resource: str
    action: str
    reason: str


class AccessControl:
    """
    CSS Role Based Access Control

    Covers:
    - login access
    - dashboard access
    - broker execution arming
    - live broker mode access
    - engine mode selection
    - trading visibility / execution
    - audit / admin / risk access
    """

    def __init__(self) -> None:
        self.known_roles: Set[str] = {
            "ADMIN",
            "SUPER_USER",
            "AUDIT",
            "TECH",
            "FINCON",
            "TELLER",
            "CASH_OFFICER",
            "BRANCH_SUPERVISOR",
            "TRADER",
            "TREASURY_OPERATIONS",
            "TREASURY_MANAGER",
            "TRADE_OFFICER",
            "TRADE_OPERATIONS",
            "TRADE_MANAGER",
            "FUNDS_TRANSFER_OFFICER",
            "SETTLEMENT_OFFICER",
            "OPERATIONS_SUPERVISOR",
            "RETAIL_OFFICER",
            "CUSTOMER_SERVICE",
            "RETAIL_MANAGER",
            "COMMERCIAL_OFFICER",
            "COMMERCIAL_MANAGER",
            "CORPORATE_OFFICER",
            "INSTITUTIONAL_BANKING_OFFICER",
            "CORPORATE_MANAGER",
            "LEGAL_OFFICER",
            "CORPORATE_SERVICES_OFFICER",
            "COMPLIANCE_OFFICER",
            "CREDIT_ADMIN_OFFICER",
            "CREDIT_CONTROL",
            "CREDIT_MANAGER",
            "VIEWER",
            "RISK_MANAGER",
        }

        self.permissions: Dict[str, Dict[str, Set[str]]] = {
            role: self._view_only_permissions()
            for role in self.known_roles
        }

        self._apply_role_overrides()

    def _view_only_permissions(self) -> Dict[str, Set[str]]:
        return {
            "auth": {"login"},
            "dashboard": {"view"},
            "system": {"view"},
            "trading": {"view"},
            "risk": {"view"},
            "audit": set(),
            "users": set(),
            "execution": set(),
            "broker": set(),
            "engine": set(),
            "admin": set(),
        }

    def _grant(self, role: str, resource: str, *actions: str) -> None:
        role = role.upper().strip()
        resource = resource.strip().lower()

        if role not in self.permissions:
            self.permissions[role] = self._view_only_permissions()

        if resource not in self.permissions[role]:
            self.permissions[role][resource] = set()

        for action in actions:
            self.permissions[role][resource].add(action.strip().lower())

    def _apply_role_overrides(self) -> None:
        full_admin_roles = {"SUPER_USER", "ADMIN", "TECH"}
        live_trading_roles = {"SUPER_USER", "ADMIN", "TRADE_MANAGER", "TREASURY_MANAGER"}
        paper_trading_roles = {
            "SUPER_USER",
            "ADMIN",
            "TRADER",
            "TRADE_OFFICER",
            "TRADE_OPERATIONS",
            "TRADE_MANAGER",
            "TREASURY_OPERATIONS",
            "TREASURY_MANAGER",
        }
        audit_roles = {"SUPER_USER", "ADMIN", "AUDIT", "FINCON", "COMPLIANCE_OFFICER"}
        risk_config_roles = {
            "SUPER_USER",
            "ADMIN",
            "RISK_MANAGER",
            "COMPLIANCE_OFFICER",
            "CREDIT_MANAGER",
            "CREDIT_CONTROL",
            "CREDIT_ADMIN_OFFICER",
        }
        user_admin_roles = {"SUPER_USER", "ADMIN", "TECH"}

        for role in self.known_roles:
            self._grant(role, "dashboard", "view")

        for role in paper_trading_roles:
            self._grant(role, "dashboard", "run")
            self._grant(role, "trading", "paper_execute")
            self._grant(role, "execution", "paper_arm")
            self._grant(role, "broker", "select")
            self._grant(role, "engine", "select_mode")

        for role in live_trading_roles:
            self._grant(role, "trading", "live_execute")
            self._grant(role, "execution", "live_arm")
            self._grant(role, "broker", "live_mode")

        for role in audit_roles:
            self._grant(role, "audit", "view")

        for role in risk_config_roles:
            self._grant(role, "risk", "configure")

        for role in user_admin_roles:
            self._grant(role, "users", "create", "update", "delete", "view")
            self._grant(role, "admin", "configure")
            self._grant(role, "system", "configure")
            self._grant(role, "audit", "view", "export")
        for role in {"RISK_MANAGER", "COMPLIANCE_OFFICER", "CREDIT_MANAGER", "CREDIT_CONTROL"}:
            self._grant(role, "dashboard", "run")

        for role in {"VIEWER", "AUDIT", "FINCON", "LEGAL_OFFICER"}:
            self._grant(role, "dashboard", "view")

        for role in {"SUPER_USER", "ADMIN", "TECH", "TRADER", "TRADE_OFFICER", "TRADE_MANAGER"}:
            self._grant(role, "trading", "execute", "view")

        for role in {"SUPER_USER", "ADMIN", "TECH"}:
            self._grant(role, "broker", "arm", "disarm")
            self._grant(role, "broker", "paper_mode", "live_mode")
            self._grant(role, "engine", "safe", "conservative", "balanced", "aggressive", "expansion")

        for role in {"TRADER", "TRADE_OFFICER", "TRADE_OPERATIONS", "TRADE_MANAGER", "TREASURY_OPERATIONS", "TREASURY_MANAGER"}:
            self._grant(role, "broker", "arm", "disarm")
            self._grant(role, "broker", "paper_mode")
            self._grant(role, "engine", "safe", "conservative", "balanced")

        for role in {"RISK_MANAGER", "COMPLIANCE_OFFICER", "AUDIT", "FINCON"}:
            self._grant(role, "trading", "view")
            self._grant(role, "audit", "view")

    def check(self, role: str, resource: str, action: str) -> AccessDecision:
        role = str(role).strip().upper()
        resource = str(resource).strip().lower()
        action = str(action).strip().lower()

        if role not in self.permissions:
            return AccessDecision(
                allowed=False,
                role=role,
                resource=resource,
                action=action,
                reason="Unknown role",
            )

        allowed_actions = self.permissions[role].get(resource, set())

        if action in allowed_actions:
            return AccessDecision(
                allowed=True,
                role=role,
                resource=resource,
                action=action,
                reason="Access granted",
            )

        return AccessDecision(
            allowed=False,
            role=role,
            resource=resource,
            action=action,
            reason="Permission denied",
        )

    def can_login(self, role: str) -> AccessDecision:
        return self.check(role, "auth", "login")

    def can_view_dashboard(self, role: str) -> AccessDecision:
        return self.check(role, "dashboard", "view")

    def can_run_dashboard(self, role: str) -> AccessDecision:
        return self.check(role, "dashboard", "run")

    def can_arm_broker(self, role: str) -> AccessDecision:
        return self.check(role, "broker", "arm")

    def can_use_live_broker_mode(self, role: str) -> AccessDecision:
        return self.check(role, "broker", "live_mode")

    def can_use_paper_broker_mode(self, role: str) -> AccessDecision:
        return self.check(role, "broker", "paper_mode")

    def can_select_engine_mode(self, role: str, engine_mode: str) -> AccessDecision:
        return self.check(role, "engine", engine_mode)

    def can_execute_live_trading(self, role: str) -> AccessDecision:
        return self.check(role, "trading", "live_execute")

    def can_execute_paper_trading(self, role: str) -> AccessDecision:
        return self.check(role, "trading", "paper_execute")
    def can_disarm_broker(self, role: str) -> AccessDecision:
        return self.check(role, "broker", "disarm")

    def can_select_broker(self, role: str) -> AccessDecision:
        return self.check(role, "broker", "select")

    def can_view_audit(self, role: str) -> AccessDecision:
        return self.check(role, "audit", "view")

    def can_configure_risk(self, role: str) -> AccessDecision:
        return self.check(role, "risk", "configure")

    def can_manage_users(self, role: str) -> AccessDecision:
        return self.check(role, "users", "update")


if __name__ == "__main__":
    ac = AccessControl()

    tests = [
        ("SUPER_USER", "broker", "live_mode"),
        ("TRADER", "broker", "live_mode"),
        ("TRADER", "broker", "paper_mode"),
        ("VIEWER", "broker", "arm"),
        ("AUDIT", "audit", "view"),
        ("RISK_MANAGER", "risk", "configure"),
    ]

    for role, resource, action in tests:
        print(ac.check(role, resource, action))