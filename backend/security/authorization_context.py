"""Phase 176D — Canonical CSS authorization context.

One identity/authorization object for Mission Control HTML, MC APIs,
``/api/v1/reports``, and mobile. Services decide authorization; pages/APIs
consume this context. No silent ADMIN/anonymous substitution.
"""

from __future__ import annotations

import os
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Mapping

from backend.security.permissions import PermissionEngine


# Duplicated intentionally to avoid circular import with backend.reports_center.
SAFETY_LOCKS = {
    "advisory_only": True,
    "execution_allowed": False,
    "live_trading_blocked": True,
    "broker_execution_armed": False,
}

UNAUTHENTICATED_USER = ""
UNAUTHENTICATED_ROLE = ""


@dataclass(frozen=True)
class CSSAuthorizationContext:
    user_id: str
    display_name: str
    role: str
    unit: str
    session_id: str
    authenticated: bool
    active: bool
    permissions: frozenset[str]
    permission_source: str
    identity_source: str
    issued_at_utc: str
    expires_at_utc: str
    request_channel: str
    correlation_id: str
    advisory_only: bool = True
    execution_allowed: bool = False
    live_trading_blocked: bool = True
    broker_execution_armed: bool = False
    denial_reason: str = ""

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["permissions"] = sorted(self.permissions)
        return payload

    def reports_authorization(self) -> dict[str, Any]:
        """Canonical Reports authorization flags from this context (single RBAC eval)."""
        from backend.reports_center.rbac import ReportsAccessControl

        access = ReportsAccessControl()
        status = access.authorization_status(self.role if self.authenticated else "", self.user_id)
        status.update(
            {
                "authenticated": self.authenticated,
                "active": self.active,
                "identity_source": self.identity_source,
                "permission_source": self.permission_source,
                "session_id": self.session_id,
                "correlation_id": self.correlation_id,
                "denial_reason": self.denial_reason,
                **{k: getattr(self, k) for k in SAFETY_LOCKS},
            }
        )
        if not self.authenticated or not self.active:
            for key in (
                "reports_view",
                "reports_generate",
                "reports_admin",
                "reports_print_all",
                "reports_export",
                "reports_audit_view",
                "executive_brief_email",
            ):
                status[key] = False
            if not status.get("denial_reason"):
                status["denial_reason"] = self.denial_reason or "not_authenticated"
        return status


def unauthenticated_context(
    *,
    channel: str,
    correlation_id: str | None = None,
    denial_reason: str = "missing_session",
    identity_source: str = "none",
) -> CSSAuthorizationContext:
    now = datetime.now(timezone.utc).isoformat()
    return CSSAuthorizationContext(
        user_id=UNAUTHENTICATED_USER,
        display_name="",
        role=UNAUTHENTICATED_ROLE,
        unit="",
        session_id="",
        authenticated=False,
        active=False,
        permissions=frozenset(),
        permission_source="none",
        identity_source=identity_source,
        issued_at_utc=now,
        expires_at_utc="",
        request_channel=channel,
        correlation_id=correlation_id or str(uuid.uuid4()),
        denial_reason=denial_reason,
        **SAFETY_LOCKS,
    )


def context_from_identity(
    *,
    user_id: str,
    role: str,
    display_name: str = "",
    unit: str = "",
    session_id: str = "",
    channel: str,
    identity_source: str,
    permission_source: str = "PermissionEngine",
    issued_at_utc: str = "",
    expires_at_utc: str = "",
    correlation_id: str | None = None,
    active: bool = True,
) -> CSSAuthorizationContext:
    """Build context from a validated identity. Empty user_id is never treated as 00000."""
    uid = str(user_id or "").strip()
    role_u = str(role or "").strip().upper()
    if not uid:
        return unauthenticated_context(
            channel=channel,
            correlation_id=correlation_id,
            denial_reason="empty_user_id",
            identity_source=identity_source,
        )
    if not role_u:
        return unauthenticated_context(
            channel=channel,
            correlation_id=correlation_id,
            denial_reason="empty_role",
            identity_source=identity_source,
        )
    if not active:
        return unauthenticated_context(
            channel=channel,
            correlation_id=correlation_id,
            denial_reason="inactive_user",
            identity_source=identity_source,
        )

    engine = PermissionEngine()
    perms = frozenset(_role_perms(engine, role_u))
    now = datetime.now(timezone.utc).isoformat()
    return CSSAuthorizationContext(
        user_id=uid,
        display_name=str(display_name or uid),
        role=role_u,
        unit=str(unit or ""),
        session_id=str(session_id or ""),
        authenticated=True,
        active=True,
        permissions=perms,
        permission_source=permission_source,
        identity_source=identity_source,
        issued_at_utc=issued_at_utc or now,
        expires_at_utc=expires_at_utc or "",
        request_channel=channel,
        correlation_id=correlation_id or str(uuid.uuid4()),
        denial_reason="",
        **SAFETY_LOCKS,
    )


def _role_perms(engine: PermissionEngine, role: str) -> set[str]:
    matrix = getattr(engine, "permissions", {}) or {}
    if isinstance(matrix, Mapping):
        raw = matrix.get(role) or matrix.get(str(role).upper()) or set()
        return {str(p) for p in raw}
    return set()


def trusted_internal_headers_enabled() -> bool:
    return os.getenv("CSS_TRUST_INTERNAL_AUTH_HEADERS", "").strip().lower() in {"1", "true", "yes", "on"}


def apply_auth_to_mission_control_state(state: dict[str, Any], auth: CSSAuthorizationContext) -> dict[str, Any]:
    """Overlay canonical identity onto MC state governance (pages consume; do not recompute)."""
    out = dict(state)
    gov = dict(out.get("governance") if isinstance(out.get("governance"), dict) else {})
    if auth.authenticated and auth.active:
        gov["current_user"] = auth.user_id
        gov["role"] = auth.role
        gov["unit"] = auth.unit or gov.get("unit")
        gov["session"] = auth.session_id or gov.get("session")
        gov["authentication_source"] = auth.identity_source
        gov["display_name"] = auth.display_name
    else:
        gov["current_user"] = "UNAUTHENTICATED"
        gov["role"] = "UNAUTHENTICATED"
        gov["authentication_source"] = auth.identity_source
        gov["auth_denial_reason"] = auth.denial_reason
    out["governance"] = gov
    out["authorization_context"] = auth.as_dict()
    out["reports_authorization"] = auth.reports_authorization()
    return out


_UNAVAILABLE_TOKENS = {
    "",
    "UNAVAILABLE",
    "DATA UNAVAILABLE",
    "DATA_UNAVAILABLE",
    "UNAUTHENTICATED",
}


def ensure_mc_authorization_state(state: Mapping[str, Any] | dict[str, Any]) -> dict[str, Any]:
    """Ensure MC page state carries canonical auth (from prior overlay or explicit governance)."""
    state_dict = dict(state)
    if isinstance(state_dict.get("authorization_context"), dict) and isinstance(
        state_dict.get("reports_authorization"), dict
    ):
        return state_dict
    gov = state_dict.get("governance") if isinstance(state_dict.get("governance"), dict) else {}
    role = str(gov.get("role") or "").strip().upper()
    user_id = str(gov.get("current_user") or "").strip()
    if role in _UNAVAILABLE_TOKENS or user_id.upper() in _UNAVAILABLE_TOKENS:
        return apply_auth_to_mission_control_state(
            state_dict,
            unauthenticated_context(
                channel="mission_control_shell",
                denial_reason="missing_authorization_context",
                identity_source="mc_shell",
            ),
        )
    auth = context_from_identity(
        user_id=user_id,
        role=role,
        display_name=str(gov.get("display_name") or user_id),
        unit=str(gov.get("unit") or ""),
        session_id=str(gov.get("session") or ""),
        channel="mission_control_shell",
        identity_source="mc_state_governance",
    )
    return apply_auth_to_mission_control_state(state_dict, auth)


def auth_from_mc_state(state: Mapping[str, Any]) -> CSSAuthorizationContext | None:
    raw = state.get("authorization_context")
    if not isinstance(raw, Mapping):
        return None
    try:
        perms = raw.get("permissions") or []
        return CSSAuthorizationContext(
            user_id=str(raw.get("user_id") or ""),
            display_name=str(raw.get("display_name") or ""),
            role=str(raw.get("role") or ""),
            unit=str(raw.get("unit") or ""),
            session_id=str(raw.get("session_id") or ""),
            authenticated=bool(raw.get("authenticated")),
            active=bool(raw.get("active")),
            permissions=frozenset(str(p) for p in perms),
            permission_source=str(raw.get("permission_source") or ""),
            identity_source=str(raw.get("identity_source") or ""),
            issued_at_utc=str(raw.get("issued_at_utc") or ""),
            expires_at_utc=str(raw.get("expires_at_utc") or ""),
            request_channel=str(raw.get("request_channel") or ""),
            correlation_id=str(raw.get("correlation_id") or ""),
            advisory_only=bool(raw.get("advisory_only", True)),
            execution_allowed=bool(raw.get("execution_allowed", False)),
            live_trading_blocked=bool(raw.get("live_trading_blocked", True)),
            broker_execution_armed=bool(raw.get("broker_execution_armed", False)),
            denial_reason=str(raw.get("denial_reason") or ""),
        )
    except Exception:
        return None
