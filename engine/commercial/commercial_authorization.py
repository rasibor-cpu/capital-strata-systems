"""Server-side, fail-closed authorization for commercial collection controls.

Roles and grants come from the existing ``backend.security.permissions``
PermissionEngine (see ``COMMERCIAL_ROLE_GRANTS``); this module adds no second
role model. Every check fails closed: a missing actor, identity or role, an
unknown role, an unknown commercial action or an ungranted action is denied.
Frontend visibility is never an authorization input.
"""
from dataclasses import dataclass
from typing import Callable, Optional, Sequence, Tuple


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


def _log_authorization_denied(username: str, roles: Sequence[str], permission: str, reason: str) -> None:
    from backend.app.auth.auth_audit import log_auth_event  # never raises

    log_auth_event(
        "AUTHORIZATION_DENIED", actor_id=username, actor_role=",".join(roles) or None,
        outcome="DENIED", reason=reason, details={"permission": permission},
    )


# A session resolver returns (username, roles) for a valid bearer token, or None.
BearerSessionResolver = Callable[[str], Optional[Tuple[str, Sequence[str]]]]


def actor_from_bearer(
    authorization: Optional[str],
    permission: str,
    *,
    session_resolver: BearerSessionResolver,
    authorizer: CommercialAuthorizer,
    on_denied: Optional[Callable[[str, Sequence[str], str, str], None]] = None,
) -> CommercialActor:
    """Resolve an authorized ``CommercialActor`` from an ``Authorization`` header.

    Identity and role always come from the server-side session the token
    resolves to, never from the request. Raises a 401 for a missing, malformed,
    invalid or expired session, and a 403 when no role the session holds grants
    ``permission``.

    Every 403 is audited exactly once: through ``on_denied`` when the caller
    supplies one (the governance API records into its commercial audit log),
    otherwise as a canonical ``AUTHORIZATION_DENIED`` event in the
    authentication audit trail. Only identity, roles, the permission and the
    denial reason are recorded -- never the token or any request payload. A
    401 (no identified actor) is not an authorization denial and is not logged.
    """
    from fastapi import HTTPException

    parts = (authorization or "").split()
    if len(parts) != 2 or parts[0].lower() != "bearer" or not parts[1]:
        raise HTTPException(status_code=401, detail="bearer session token required")
    session = session_resolver(parts[1])
    if session is None:
        raise HTTPException(status_code=401, detail="invalid or expired session")
    username, roles = session
    candidates = [CommercialActor(username, r) for r in roles] or [CommercialActor(username, "")]
    for candidate in candidates:
        if authorizer.allowed(candidate, permission):
            return candidate
    # Fail closed through the authorizer so the denial reason is precise.
    try:
        authorizer.require(candidates[0], permission)
    except CommercialAuthorizationError as exc:
        if on_denied is not None:
            on_denied(username, roles, permission, exc.reason)
        else:
            _log_authorization_denied(username, roles, permission, exc.reason)
        raise HTTPException(status_code=403, detail=exc.reason) from exc
    raise HTTPException(status_code=403, detail="not permitted")  # pragma: no cover - defensive
