"""Operator web login backed by the canonical ``css_sign_on`` user store.

Authenticates an operator against ``dashboard.auth.css_sign_on`` (password
verification, lockout and password-expiry policy all reused as-is) and issues
a bearer session token through the existing ``token_store`` — the same store
the commercial governance API and trial contract router already resolve
sessions against. The caller's identity and role always come from the stored
user record; neither is ever accepted from the request body.
"""
from __future__ import annotations

import os
from typing import Optional

from fastapi import APIRouter, Header, HTTPException, Request, Response
from pydantic import BaseModel, Field

from dashboard.auth.css_sign_on import (
    AuthFailure,
    PasswordChangeRequired,
    PasswordValidationError,
    authenticate_credentials,
    change_authenticated_password,
    load_users,
    save_users,
    set_user_disabled,
)

from .session_dependency import (
    SESSION_COOKIE_NAME,
    require_mutation_session,
    revoke_session_from_request,
)
from .token_store import token_store

OPERATOR_SESSION_MINUTES = 60


class OperatorLoginRequest(BaseModel):
    user_id: str = Field(min_length=1, max_length=5)
    password: str = Field(min_length=1)


class OperatorLoginResponse(BaseModel):
    token: str
    user_id: str
    display_name: str
    role: str
    expires_in_minutes: int
    # The session's synchronizer CSRF token. Only needed when a browser uses
    # the session *cookie* for a state-changing request (sent back as the
    # X-CSRF-Token header); a bearer-header client never needs it.
    csrf_token: str


class OperatorPasswordChangeRequest(BaseModel):
    user_id: str = Field(min_length=1, max_length=5)
    current_password: str = Field(min_length=1)
    new_password: str = Field(min_length=1)
    confirm_password: str = Field(min_length=1)


def _bearer_token(authorization: Optional[str]) -> str:
    parts = (authorization or "").split()
    if len(parts) != 2 or parts[0].lower() != "bearer" or not parts[1]:
        raise HTTPException(status_code=401, detail="bearer session token required")
    return parts[1]


def cookie_secure_default() -> bool:
    # Allow local HTTP development; default to secure cookies everywhere else.
    return os.environ.get("CSS_ENV", "").strip().lower() not in {"development", "dev", "local"}


def set_session_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        SESSION_COOKIE_NAME,
        token,
        httponly=True,
        samesite="lax",
        secure=cookie_secure_default(),
        max_age=OPERATOR_SESSION_MINUTES * 60,
    )


def create_operator_login_router() -> APIRouter:
    router = APIRouter(prefix="/auth/operator", tags=["operator-auth"])

    @router.post("/login", response_model=OperatorLoginResponse)
    def login(body: OperatorLoginRequest, response: Response) -> OperatorLoginResponse:
        users = load_users()
        try:
            user_ctx = authenticate_credentials(users, body.user_id, body.password)
        except PasswordChangeRequired:
            save_users(users)
            raise HTTPException(
                status_code=401,
                detail="password change required before sign-in",
            )
        except AuthFailure as exc:
            save_users(users)
            raise HTTPException(status_code=401, detail=exc.message) from exc

        save_users(users)
        token = token_store.create_session(
            user_ctx["user_id"],
            [user_ctx["role"]],
            minutes=OPERATOR_SESSION_MINUTES,
        )
        set_session_cookie(response, token)
        return OperatorLoginResponse(
            token=token,
            user_id=user_ctx["user_id"],
            display_name=user_ctx["display_name"],
            role=user_ctx["role"],
            expires_in_minutes=OPERATOR_SESSION_MINUTES,
            csrf_token=token_store.validate(token).csrf_token,
        )

    @router.post("/change-password", response_model=OperatorLoginResponse)
    def change_password(body: OperatorPasswordChangeRequest, response: Response) -> OperatorLoginResponse:
        users = load_users()
        try:
            user_ctx = change_authenticated_password(
                users,
                body.user_id,
                body.current_password,
                body.new_password,
                body.confirm_password,
            )
        except AuthFailure as exc:
            raise HTTPException(status_code=401, detail=exc.message) from exc
        except PasswordValidationError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        # A password change invalidates every other session for this operator
        # (e.g. a compromised password should not leave old sessions usable).
        token_store.revoke_all_for_user(user_ctx["user_id"])
        token = token_store.create_session(
            user_ctx["user_id"],
            [user_ctx["role"]],
            minutes=OPERATOR_SESSION_MINUTES,
        )
        set_session_cookie(response, token)
        return OperatorLoginResponse(
            token=token,
            user_id=user_ctx["user_id"],
            display_name=user_ctx["display_name"],
            role=user_ctx["role"],
            expires_in_minutes=OPERATOR_SESSION_MINUTES,
            csrf_token=token_store.validate(token).csrf_token,
        )

    @router.post("/logout")
    def logout(request: Request, response: Response) -> dict:
        # Logout is an authenticated state change (server-side revocation), so
        # a cookie-backed logout needs the session's CSRF token like every
        # other cookie-backed mutation; a missing/expired/revoked session is 401.
        require_mutation_session(request)
        revoked = revoke_session_from_request(request)
        response.delete_cookie(SESSION_COOKIE_NAME)
        return {"revoked": revoked}

    @router.post("/admin/users/{user_id}/disable")
    def disable_user(user_id: str, request: Request) -> dict:
        return _set_disabled(request, user_id, True)

    @router.post("/admin/users/{user_id}/enable")
    def enable_user(user_id: str, request: Request) -> dict:
        return _set_disabled(request, user_id, False)

    def _set_disabled(request: Request, user_id: str, disabled: bool) -> dict:
        caller = require_mutation_session(request)
        if "SUPER_USER" not in caller.roles:
            from .auth_audit import log_auth_event

            log_auth_event(
                "AUTHORIZATION_DENIED", actor_id=caller.username,
                actor_role=(caller.roles[0] if caller.roles else None), outcome="DENIED",
                reason="not a super user",
                details={"target_user_id": user_id, "action": "disable" if disabled else "enable"},
            )
            raise HTTPException(status_code=403, detail="only a super user may disable or enable accounts")

        users = load_users()
        try:
            user_ctx = set_user_disabled(
                users, {"user_id": caller.username, "role": "SUPER_USER"}, user_id, disabled
            )
        except AuthFailure as exc:
            raise HTTPException(status_code=404, detail=exc.message) from exc
        save_users(users)

        if disabled:
            # A disabled account must not keep using sessions issued before
            # it was disabled.
            token_store.revoke_all_for_user(user_ctx["user_id"])

        return {"user_id": user_ctx["user_id"], "disabled": disabled}

    @router.get("/me")
    def me(authorization: Optional[str] = Header(default=None)) -> dict:
        token = _bearer_token(authorization)
        info = token_store.validate(token)
        if info is None:
            raise HTTPException(status_code=401, detail="invalid or expired session")
        return {
            "user_id": info.username,
            "roles": list(info.roles),
            "issued_at_utc": info.issued_at_utc.isoformat(),
            "expires_at_utc": info.expires_at_utc.isoformat(),
        }

    return router
