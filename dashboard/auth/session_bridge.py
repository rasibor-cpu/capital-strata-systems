"""Phase 176D — Session bridge from CLI/runtime auth into web/mobile/MC.

Canonical identity sources (in order):
1. Explicit override (tests / DI)
2. Trusted internal headers (opt-in via CSS_TRUST_INTERNAL_AUTH_HEADERS)
3. Valid ``artifacts/css_auth_session.json`` via ``restore_login_session``
4. Valid ``session_user_ctx`` from recovery artifact (freshness-checked)
5. Fail closed

Never treat empty user_id as 00000. Never grant ADMIN/SUPER_USER from localhost alone.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Mapping

from backend.security.authorization_context import (
    CSSAuthorizationContext,
    context_from_identity,
    trusted_internal_headers_enabled,
    unauthenticated_context,
)
from backend.security.auth_diagnostics import log_authorization_denial

logger = logging.getLogger("css.auth.session_bridge")

PROJECT_ROOT = Path(__file__).resolve().parents[2]
ARTIFACTS_DIR = PROJECT_ROOT / "artifacts"
RECOVERY_SESSION_FILE = ARTIFACTS_DIR / "css_session_recovery.json"
SESSION_MAX_AGE_SECONDS = 86400


def resolve_authorization_context(
    *,
    channel: str,
    request: Any | None = None,
    override: Mapping[str, Any] | None = None,
    correlation_id: str | None = None,
) -> CSSAuthorizationContext:
    """Resolve one canonical authorization context for the request channel."""
    if override is not None:
        auth = _from_override(override, channel=channel, correlation_id=correlation_id)
        return _finalize(auth)

    if request is not None and trusted_internal_headers_enabled():
        header_auth = _from_trusted_headers(request, channel=channel, correlation_id=correlation_id)
        if header_auth.authenticated:
            return _finalize(header_auth)
        # Fall through to session bridge when headers absent; forged empty still fail-closed later.

    session_auth = load_bridged_session_context(channel=channel, correlation_id=correlation_id)
    if session_auth.authenticated:
        return _finalize(session_auth)

    # Headers present but trust disabled → forged-header denial (do not silently ignore as session miss)
    if request is not None and _headers_present(request) and not trusted_internal_headers_enabled():
        auth = unauthenticated_context(
            channel=channel,
            correlation_id=correlation_id,
            denial_reason="untrusted_identity_headers",
            identity_source="forged_or_untrusted_headers",
        )
        return _finalize(auth)

    auth = unauthenticated_context(
        channel=channel,
        correlation_id=correlation_id,
        denial_reason="missing_session",
        identity_source="none",
    )
    return _finalize(auth)


def load_bridged_session_context(
    *,
    channel: str,
    correlation_id: str | None = None,
) -> CSSAuthorizationContext:
    """Load and validate the CLI/runtime session for web/MC/mobile bridging."""
    mode = os.getenv("CSS_AUTH_BRIDGE_MODE", "auto").strip().lower()
    if mode in {"off", "0", "false", "no"}:
        return unauthenticated_context(
            channel=channel,
            correlation_id=correlation_id,
            denial_reason="bridge_disabled",
            identity_source="bridge_off",
        )

    from dashboard.auth.css_sign_on import restore_login_session

    try:
        restored = restore_login_session()
    except Exception as exc:  # noqa: BLE001
        logger.warning("session_bridge_restore_failed reason=%s", type(exc).__name__)
        return unauthenticated_context(
            channel=channel,
            correlation_id=correlation_id,
            denial_reason="session_restore_error",
            identity_source="css_auth_session",
        )

    if isinstance(restored, dict) and restored.get("user_id") and restored.get("role"):
        active = bool((restored.get("role_profile") or {}).get("can_login", True))
        return context_from_identity(
            user_id=str(restored.get("user_id")),
            role=str(restored.get("role")),
            display_name=str(restored.get("display_name") or ""),
            unit=str(restored.get("unit_code") or restored.get("unit") or ""),
            session_id=str(restored.get("session_id") or f"auth-{restored.get('user_id')}"),
            channel=channel,
            identity_source="css_auth_session",
            issued_at_utc=str(restored.get("last_login") or ""),
            active=active,
            correlation_id=correlation_id,
        )

    recovery = _load_recovery_user_ctx()
    if recovery is not None:
        return recovery_context(recovery, channel=channel, correlation_id=correlation_id)

    return unauthenticated_context(
        channel=channel,
        correlation_id=correlation_id,
        denial_reason="missing_session",
        identity_source="none",
    )


def recovery_context(
    user_ctx: Mapping[str, Any],
    *,
    channel: str,
    correlation_id: str | None = None,
) -> CSSAuthorizationContext:
    issued = str(user_ctx.get("authenticated_at") or user_ctx.get("last_login") or "")
    if issued and _is_stale(issued):
        return unauthenticated_context(
            channel=channel,
            correlation_id=correlation_id,
            denial_reason="expired_session",
            identity_source="css_session_recovery.session_user_ctx",
        )
    active = user_ctx.get("active")
    if active is False:
        return unauthenticated_context(
            channel=channel,
            correlation_id=correlation_id,
            denial_reason="inactive_user",
            identity_source="css_session_recovery.session_user_ctx",
        )
    return context_from_identity(
        user_id=str(user_ctx.get("user_id") or ""),
        role=str(user_ctx.get("role") or ""),
        display_name=str(user_ctx.get("display_name") or ""),
        unit=str(user_ctx.get("unit_code") or user_ctx.get("unit") or ""),
        session_id=str(user_ctx.get("session_id") or ""),
        channel=channel,
        identity_source="css_session_recovery.session_user_ctx",
        issued_at_utc=issued,
        correlation_id=correlation_id,
        active=True if active is None else bool(active),
    )


def _load_recovery_user_ctx() -> dict[str, Any] | None:
    path = Path(os.getenv("CSS_SESSION_RECOVERY_FILE", str(RECOVERY_SESSION_FILE)))
    if not path.is_file():
        return None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    if not isinstance(raw, dict):
        return None
    ctx = raw.get("session_user_ctx")
    if not isinstance(ctx, dict):
        return None
    if not ctx.get("user_id") or not ctx.get("role"):
        return None
    return dict(ctx)


def _from_override(
    override: Mapping[str, Any],
    *,
    channel: str,
    correlation_id: str | None,
) -> CSSAuthorizationContext:
    return context_from_identity(
        user_id=str(override.get("user_id") or ""),
        role=str(override.get("role") or ""),
        display_name=str(override.get("display_name") or ""),
        unit=str(override.get("unit") or override.get("unit_code") or ""),
        session_id=str(override.get("session_id") or ""),
        channel=channel,
        identity_source=str(override.get("identity_source") or "explicit_override"),
        issued_at_utc=str(override.get("issued_at_utc") or ""),
        expires_at_utc=str(override.get("expires_at_utc") or ""),
        correlation_id=correlation_id,
        active=bool(override.get("active", True)),
    )


def _from_trusted_headers(
    request: Any,
    *,
    channel: str,
    correlation_id: str | None,
) -> CSSAuthorizationContext:
    headers = getattr(request, "headers", {}) or {}
    role = str(headers.get("x-css-role") or headers.get("X-CSS-Role") or "").strip()
    user_id = str(headers.get("x-css-user-id") or headers.get("X-CSS-User-Id") or "").strip()
    if not role and not user_id:
        return unauthenticated_context(
            channel=channel,
            correlation_id=correlation_id,
            denial_reason="missing_session",
            identity_source="trusted_internal_headers_absent",
        )
    # Empty user_id must never be treated as 00000
    if not user_id:
        return unauthenticated_context(
            channel=channel,
            correlation_id=correlation_id,
            denial_reason="empty_user_id",
            identity_source="trusted_internal_headers",
        )
    if not role:
        return unauthenticated_context(
            channel=channel,
            correlation_id=correlation_id,
            denial_reason="empty_role",
            identity_source="trusted_internal_headers",
        )
    return context_from_identity(
        user_id=user_id,
        role=role,
        channel=channel,
        identity_source="trusted_internal_headers",
        correlation_id=correlation_id,
    )


def _headers_present(request: Any) -> bool:
    headers = getattr(request, "headers", {}) or {}
    role = str(headers.get("x-css-role") or headers.get("X-CSS-Role") or "").strip()
    user_id = str(headers.get("x-css-user-id") or headers.get("X-CSS-User-Id") or "").strip()
    return bool(role or user_id)


def _is_stale(issued_at: str) -> bool:
    raw = str(issued_at or "").strip()
    if not raw:
        return True
    try:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except Exception:
        return True
    if not isinstance(dt, datetime):
        return True
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    try:
        age = (datetime.now(timezone.utc) - dt.astimezone(timezone.utc)).total_seconds()
        return float(age) > float(SESSION_MAX_AGE_SECONDS)
    except (TypeError, ValueError):
        return True


def _finalize(auth: CSSAuthorizationContext) -> CSSAuthorizationContext:
    if not auth.authenticated or not auth.active:
        log_authorization_denial(
            route=auth.request_channel,
            auth=auth,
            permission_requested="authenticated_session",
            denial_reason=auth.denial_reason or "not_authenticated",
        )
    return auth
