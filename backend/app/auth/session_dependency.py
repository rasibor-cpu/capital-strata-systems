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

import secrets
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


# ---------------------------------------------------------------------------
# CSRF
#
# The governing rule: every authenticated, cookie-backed, state-changing
# request must carry the session's synchronizer CSRF token. A browser attaches
# the session cookie to cross-site requests automatically; it never attaches
# an ``Authorization`` header (and no CORS policy is configured that would let
# a foreign origin set one), so a bearer-authenticated request needs no CSRF
# token. Login is exempt because no session exists yet.
# ---------------------------------------------------------------------------
CSRF_HEADER_NAME = "x-csrf-token"
CSRF_FORM_FIELD = "csrf_token"


def session_is_cookie_backed(request: Request) -> bool:
    """True when the session token this request resolves to came from the cookie.

    Mirrors ``_token_from_headers_and_cookies``'s precedence (cookie first).
    """
    return bool(request.cookies.get(SESSION_COOKIE_NAME))


def csrf_token_matches(session: SessionInfo, provided: Optional[str]) -> bool:
    expected = getattr(session, "csrf_token", "") or ""
    return bool(expected) and secrets.compare_digest(str(expected), str(provided or ""))


def require_mutation_session(request: Request, *, form_token: Optional[str] = None) -> SessionInfo:
    """Resolve the session for a state-changing request, enforcing CSRF for cookies.

    401 when there is no valid session (missing, forged, expired or revoked);
    403 when the session is cookie-backed and the CSRF token (``X-CSRF-Token``
    header, or ``form_token`` for an HTML form post) is missing or does not
    match *this* session's token. The CSRF check runs before any caller's
    role check or business logic.
    """
    session = resolve_operator_session(request)
    if session is None:
        raise HTTPException(status_code=401, detail="authentication required")
    if session_is_cookie_backed(request):
        provided = request.headers.get(CSRF_HEADER_NAME) or form_token
        if not csrf_token_matches(session, provided):
            raise HTTPException(status_code=403, detail="CSRF token missing or invalid")
    return session


def authorization_for_commercial_route(request: Request, *, mutating: bool) -> Optional[str]:
    """``Authorization`` value for ``actor_from_bearer`` that also accepts the session cookie.

    Only for the commercial routes the operator web pages call same-origin
    (billing, trial & contract, launch-ops status); API-only commercial routes
    stay bearer-header-only. Identity, role and permission are still resolved
    entirely by ``actor_from_bearer`` against the server-side session -- this
    only changes where the session token is read from, with the same cookie-
    first precedence as every other session consumer here. A cookie-backed
    mutating request must also carry the session's CSRF token (403 otherwise,
    before any permission check); a dead cookie falls through to
    ``actor_from_bearer``'s 401.
    """
    cookie_token = request.cookies.get(SESSION_COOKIE_NAME)
    if not cookie_token:
        return request.headers.get("authorization")
    if mutating:
        session = _validate(cookie_token)
        if session is not None and not csrf_token_matches(session, request.headers.get(CSRF_HEADER_NAME)):
            raise HTTPException(status_code=403, detail="CSRF token missing or invalid")
    return f"Bearer {cookie_token}"


def revoke_session_from_request(request: Request) -> bool:
    """Revoke whatever session token this request carries (cookie or bearer).

    Shared by every logout entry point so cookie/header precedence,
    revocation, and audit logging all stay in exactly one place. Callers must
    already have authorized the request (``require_mutation_session``), so a
    cookie-backed logout has passed the CSRF check before reaching here.
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
