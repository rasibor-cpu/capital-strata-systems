"""Server-side, fail-closed authorization for commercial collection controls.

Roles and grants come from the existing ``backend.security.permissions``
PermissionEngine (see ``COMMERCIAL_ROLE_GRANTS``); this module adds no second
role model. Every check fails closed: a missing actor, identity or role, an
unknown role, an unknown commercial action or an ungranted action is denied.
Frontend visibility is never an authorization input.
"""
from dataclasses import dataclass
from typing import Callable, Optional


class CommercialAuthorizationError(PermissionError):
    """Raised when a commercial action is not authorized. Never bypassable."""

    def __init__(self, reason: str, *, actor_id: Optional[str] = None, role: Optional[str] = None, action: Optional[str] = None):
        super().__init__(reason)
        self.reason = reason
        self.actor_id = actor_id
        self.role = role
        self.action = action


@dataclass(frozen=True)
class CommercialActor:
    """An authenticated caller. Identity and role must come from the server session."""

    actor_id: str
    role: str


PermissionCheck = Callable[[str, str], bool]


def _default_permission_check() -> PermissionCheck:
    from backend.security.permissions import PermissionEngine

    engine = PermissionEngine()
    return lambda role, action: engine.check(role, action).allowed


def _commercial_actions() -> frozenset:
    from backend.security.permissions import COMMERCIAL_ACTIONS

    return COMMERCIAL_ACTIONS


class CommercialAuthorizer:
    def __init__(self, permission_check: Optional[PermissionCheck] = None, known_actions: Optional[frozenset] = None):
        self._check = permission_check or _default_permission_check()
        self._known_actions = known_actions if known_actions is not None else _commercial_actions()

    def require(self, actor: Optional[CommercialActor], action: str) -> CommercialActor:
        if actor is None or not isinstance(actor, CommercialActor):
            raise CommercialAuthorizationError("authenticated actor required", action=action)
        actor_id = (actor.actor_id or "").strip()
        role = (actor.role or "").strip()
        if not actor_id:
            raise CommercialAuthorizationError("actor identity required", role=role or None, action=action)
        if not role:
            raise CommercialAuthorizationError("actor role required", actor_id=actor_id, action=action)
        if action not in self._known_actions:
            raise CommercialAuthorizationError(f"unknown commercial action: {action}", actor_id=actor_id, role=role, action=action)
        if not self._check(role, action):
            raise CommercialAuthorizationError(f"role {role} is not permitted to {action}", actor_id=actor_id, role=role, action=action)
        return CommercialActor(actor_id=actor_id, role=role)

    def allowed(self, actor: Optional[CommercialActor], action: str) -> bool:
        try:
            self.require(actor, action)
        except CommercialAuthorizationError:
            return False
        return True
