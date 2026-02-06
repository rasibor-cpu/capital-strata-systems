"""
Auth Router — REA Capital Trading Engine

Workflow:
1) POST /auth/login  (username+password) -> sends OTP (email), returns expires_in_seconds
2) POST /auth/verify (username+otp)      -> returns session token (bearer)
3) GET  /auth/me     (Authorization: Bearer <token>) -> identity
4) POST /auth/logout (Authorization: Bearer <token>) -> revoke
"""

from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

from .auth_config import (
    REA_SUPERUSER_USERNAME,
    REA_SUPERUSER_PASSWORD,
    REA_SUPERUSER_ROLES,
    OTP_TTL_SECONDS,
)
from .token_store import token_store
from .otp_sender import send_otp_email

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1)
    password: str = Field(..., min_length=1)


class LoginResponse(BaseModel):
    ok: bool
    message: str
    expires_in_seconds: int
    username: str
    roles: list[str]


class VerifyRequest(BaseModel):
    username: str = Field(..., min_length=1)
    otp: str = Field(..., min_length=6, max_length=6)


class VerifyResponse(BaseModel):
    ok: bool
    token: str
    token_type: str
    expires_in_minutes: int
    username: str
    roles: list[str]


def _require_bearer(authorization: str | None) -> str:
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing Authorization header")
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(status_code=401, detail="Invalid Authorization header (expected Bearer token)")
    return parts[1].strip()


@router.post("/login", response_model=LoginResponse)
def login(req: LoginRequest) -> LoginResponse:
    username = req.username.strip().lower()
    password = req.password.strip()

    # For now: single dev superuser
    if username != REA_SUPERUSER_USERNAME.strip().lower() or password != REA_SUPERUSER_PASSWORD:
        raise HTTPException(status_code=401, detail="Invalid username or password")

    # Generate OTP + email it (never return OTP to the UI)
    otp_code = token_store.generate_otp(username)
    try:
        send_otp_email(otp_code=otp_code, username=username)
    except Exception as e:
        # keep OTP but tell user delivery failed
        raise HTTPException(status_code=502, detail=f"OTP delivery failed: {e}")

    return LoginResponse(
        ok=True,
        message="OTP sent",
        expires_in_seconds=int(OTP_TTL_SECONDS),
        username=username,
        roles=list(REA_SUPERUSER_ROLES),
    )


@router.post("/verify", response_model=VerifyResponse)
def verify(req: VerifyRequest) -> VerifyResponse:
    username = req.username.strip().lower()
    otp = req.otp.strip()

    if not token_store.verify_otp(username, otp):
        raise HTTPException(status_code=401, detail="Invalid or expired OTP")

    # Create session token (bearer)
    token = token_store.create_session(username=username, roles=list(REA_SUPERUSER_ROLES), minutes=60)
    return VerifyResponse(
        ok=True,
        token=token,
        token_type="bearer",
        expires_in_minutes=60,
        username=username,
        roles=list(REA_SUPERUSER_ROLES),
    )


@router.get("/me")
def me(authorization: str | None = Header(default=None)) -> dict:
    token = _require_bearer(authorization)
    info = token_store.validate(token)
    if info is None:
        raise HTTPException(status_code=401, detail="Invalid/expired session token")
    return info.to_public_dict()


@router.post("/logout")
def logout(authorization: str | None = Header(default=None)) -> dict:
    token = _require_bearer(authorization)
    revoked = token_store.revoke(token)
    return {"ok": True, "revoked": revoked}
