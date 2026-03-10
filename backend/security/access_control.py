from __future__ import annotations
from dataclasses import dataclass


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
    """

    def __init__(self):

        self.permissions = {

            "ADMIN": {
                "system": {"view", "configure"},
                "users": {"create", "update", "delete", "view"},
                "trading": {"execute", "view"},
                "risk": {"configure", "view"}
            },

            "TRADER": {
                "system": {"view"},
                "users": set(),
                "trading": {"execute", "view"},
                "risk": {"view"}
            },

            "RISK_MANAGER": {
                "system": {"view"},
                "users": set(),
                "trading": {"view"},
                "risk": {"configure", "view"}
            },

            "VIEWER": {
                "system": {"view"},
                "users": set(),
                "trading": {"view"},
                "risk": {"view"}
            }

        }

    def check(self, role, resource, action):

        role = role.upper()

        if role not in self.permissions:

            return AccessDecision(
                False,
                role,
                resource,
                action,
                "Unknown role"
            )

        allowed_actions = self.permissions[role].get(resource, set())

        if action in allowed_actions:

            return AccessDecision(
                True,
                role,
                resource,
                action,
                "Access granted"
            )

        return AccessDecision(
            False,
            role,
            resource,
            action,
            "Permission denied"
        )


if __name__ == "__main__":

    ac = AccessControl()

    test = ac.check("TRADER", "trading", "execute")

    print(test)