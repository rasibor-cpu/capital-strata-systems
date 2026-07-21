"""Shared fail-closed authentication dependency for security metadata APIs."""

from dataclasses import dataclass

from fastapi import HTTPException, Request, status

from backend.security.authorization_context import CSSAuthorizationContext
from dashboard.auth.session_bridge import resolve_authorization_context

SECURITY_API_ADMIN_ROLES = frozenset({"SUPER_USER", "ADMIN"})


@dataclass(frozen=True)
class SecurityAPIAdminDependency:
    """Resolve request authentication before applying the administrative role gate."""

    channel: str

    def __call__(self, request: Request) -> CSSAuthorizationContext:
        auth = resolve_authorization_context(channel=self.channel, request=request)
        if (
            not auth.authenticated
            or not auth.active
            or str(auth.role or "").strip().upper() not in SECURITY_API_ADMIN_ROLES
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "status": "DENIED",
                    "reason": "ADMIN_AUTHENTICATION_REQUIRED",
                    "execution_allowed": False,
                },
            )
        return auth


__all__ = ["SECURITY_API_ADMIN_ROLES", "SecurityAPIAdminDependency"]
