"""Shared operator-session gate for routes that aren't commercial-permission-scoped.

``engine/commercial/commercial_authorization.actor_from_bearer`` (bearer-header
only) already gates the commercial-collections routers with a specific
permission. This module gates general operational surfaces -- the dashboard
HTML pages, Mission Control, and the JSON/WebSocket state feeds those pages
fetch same-origin -- behind "any valid operator session, no specific
permission required". A browser page navigation or same-origin ``fetch()``
call cannot easily attach a custom ``Authorization`` header, so this accepts
the session token as a cookie too; both paths resolve through the same
``token_store`` used everywhere else in the app. There is exactly one session
mechanism, not two.
"""
from __future__ import annotations

from typing import Optional

from fastapi import HTTPException, Request, WebSocket

from .token_store import SessionInfo

SESSION_COOKIE_NAME = "css_operator_session"


def _validate(token: str) -> Optional[SessionInfo]:
    # Local import so a monkeypatched backend.app.auth.token_store.token_store
    # (the usual way tests isolate session state) is always seen -- a
    # module-level `from .token_store import token_store` would freeze a
    # stale reference at import time instead.
    from .token_store import token_store

    return token_store.validate(token)


def _token_from_headers_and_cookies(cookie_token: Optional[str], auth_header: Optional[str]) -> Optional[str]:
    if cookie_token:
        return cookie_token
    parts = (auth_header or "").split()
    if len(parts) == 2 and parts[0].lower() == "bearer" and parts[1]:
        return parts[1]
    return None


def _token_from_request(request: Request) -> Optional[str]:
    return _token_from_headers_and_cookies(
        request.cookies.get(SESSION_COOKIE_NAME), request.headers.get("authorization")
    )


def resolve_operator_session(request: Request) -> Optional[SessionInfo]:
    token = _token_from_request(request)
    if not token:
        return None
    return _validate(token)


def revoke_session_from_request(request: Request) -> bool:
    """Revoke whatever session token this request carries (cookie or bearer).

    Shared by every logout entry point so cookie/header precedence,
    revocation, and audit logging all stay in exactly one place.
    """
    token = _token_from_request(request)
    if not token:
        return False
    from .token_store import token_store

    session = token_store.validate(token)
    revoked = token_store.revoke(token)
    if revoked:
        try:
            from .auth_audit import log_auth_event

            log_auth_event(
                "LOGOUT",
                actor_id=session.username if session else None,
                actor_role=(session.roles[0] if session and session.roles else None),
                outcome="SUCCEEDED",
            )
        except Exception:
            pass
    return revoked


def require_operator_session(request: Request) -> SessionInfo:
    session = resolve_operator_session(request)
    if session is None:
        raise HTTPException(status_code=401, detail="authentication required")
    return session


def resolve_operator_session_ws(websocket: WebSocket) -> Optional[SessionInfo]:
    token = _token_from_headers_and_cookies(
        websocket.cookies.get(SESSION_COOKIE_NAME), websocket.headers.get("authorization")
    )
    if not token:
        return None
    return _validate(token)
