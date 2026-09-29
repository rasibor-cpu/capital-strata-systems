"""Operator web login backed by the canonical ``css_sign_on`` user store.

Authenticates an operator against ``dashboard.auth.css_sign_on`` (password
verification, lockout and password-expiry policy all reused as-is) and issues
a bearer session token through the existing ``token_store`` — the same store
the commercial governance API and trial contract router already resolve
sessions against. The caller's identity and role always come from the stored
user record; neither is ever accepted from the request body.
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

from dashboard.auth.css_sign_on import (
    AuthFailure,
    PasswordChangeRequired,
    PasswordValidationError,
    authenticate_credentials,
    change_authenticated_password,
    load_users,
    save_users,
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


def create_operator_login_router() -> APIRouter:
    router = APIRouter(prefix="/auth/operator", tags=["operator-auth"])

    @router.post("/login", response_model=OperatorLoginResponse)
    def login(body: OperatorLoginRequest) -> OperatorLoginResponse:
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
        return OperatorLoginResponse(
            token=token,
            user_id=user_ctx["user_id"],
            display_name=user_ctx["display_name"],
            role=user_ctx["role"],
            expires_in_minutes=OPERATOR_SESSION_MINUTES,
        )

    @router.post("/change-password", response_model=OperatorLoginResponse)
    def change_password(body: OperatorPasswordChangeRequest) -> OperatorLoginResponse:
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

        token = token_store.create_session(
            user_ctx["user_id"],
            [user_ctx["role"]],
            minutes=OPERATOR_SESSION_MINUTES,
        )
        return OperatorLoginResponse(
            token=token,
            user_id=user_ctx["user_id"],
            display_name=user_ctx["display_name"],
            role=user_ctx["role"],
            expires_in_minutes=OPERATOR_SESSION_MINUTES,
        )

    @router.post("/logout")
    def logout(authorization: Optional[str] = Header(default=None)) -> dict:
        token = _bearer_token(authorization)
        token_store.revoke(token)
        return {"revoked": True}

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
