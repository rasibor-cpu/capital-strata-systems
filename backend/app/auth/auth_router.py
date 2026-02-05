"""
Auth Router – REA Capital Trading Engine

SECURE OTP MODE (Email):
- /auth/login validates username/password then emails a 6-digit OTP.
- OTP is NOT returned to the UI (unless DEV_SHOW_OTP=1 for testing).
- /auth/verify consumes OTP and returns a 6-digit SESSION token (bearer).

ENV REQUIRED:
- OTP_TO_EMAIL (where to send the OTP for now)
Optional:
- DEV_SHOW_OTP=1 (development only; returns otp_code in response)
"""

from __future__ import annotations

import os
from typing import Optional, List, Dict, Any

from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel, Field

from .auth_config import (
    REA_SUPERUSER,
    REA_SUPERPASS,
    REA_TOKEN_TTL_MINUTES,
    ALLOW_DEFAULT_CREDS,
    using_default_creds,
)
from .token_store import token_store
from .otp_sender import send_otp_email

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=64)
    password: str = Field(..., min_length=1, max_length=128)


class LoginResponse(BaseModel):
    ok: bool
    message: str
    sent_to: str
    # For dev only (when DEV_SHOW_OTP=1)
    otp_code: Optional[str] = None
    expires_in_minutes: int
    username: str
    roles: List[str]


class VerifyRequest(BaseModel):
    challenge_code: str = Field(..., min_length=6, max_length=6)


class VerifyResponse(BaseModel):
    token: str  # 6-digit session token
    token_type: str = "bearer"
    expires_in_minutes: int
    username: str
    roles: List[str]


def _extract_bearer(authorization: Optional[str]) -> Optional[str]:
    if not authorization:
        return None
    parts = authorization.strip().split()
    if len(parts) != 2:
        return None
    if parts[0].lower() != "bearer":
        return None
    return parts[1].strip() or None


def _mask_email(email: str) -> str:
    e = (email or "").strip()
    if "@" not in e:
        return "***"
    name, domain = e.split("@", 1)
    if len(name) <= 2:
        name_mask = name[:1] + "***"
    else:
        name_mask = name[:2] + "***"
    return f"{name_mask}@{domain}"


@router.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest) -> LoginResponse:
    if using_default_creds() and not ALLOW_DEFAULT_CREDS:
        raise HTTPException(status_code=503, detail="Auth not configured (default creds disabled).")

    username = payload.username.strip()
    password = payload.password

    if username != REA_SUPERUSER or password != REA_SUPERPASS:
        raise HTTPException(status_code=401, detail="Invalid username/password.")

    roles = ["superuser"]

    # Issue OTP challenge (6 digits)
    challenge = token_store.issue_challenge(username=username, roles=roles, ttl_minutes=5)
    otp_code = challenge.code

    # Send OTP via email
    to_email = os.getenv("OTP_TO_EMAIL", "").strip()
    if not to_email:
        raise HTTPException(status_code=500, detail="OTP_TO_EMAIL not set (no destination email).")

    try:
        send_otp_email(to_email=to_email, otp_code=otp_code)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"OTP delivery failed: {e}")

    dev_show = os.getenv("DEV_SHOW_OTP", "0").strip() in ("1", "true", "TRUE", "yes", "YES")

    return LoginResponse(
        ok=True,
        message="Verification code sent.",
        sent_to=_mask_email(to_email),
        otp_code=(otp_code if dev_show else None),
        expires_in_minutes=5,
        username=username,
        roles=roles,
    )


@router.post("/verify", response_model=VerifyResponse)
def verify(payload: VerifyRequest) -> VerifyResponse:
    code = (payload.challenge_code or "").strip()
    if (not code.isdigit()) or len(code) != 6:
        raise HTTPException(status_code=400, detail="Challenge code must be exactly 6 digits.")

    challenge = token_store.consume_challenge(code)
    if challenge is None:
        raise HTTPException(status_code=401, detail="Invalid or expired challenge code.")

    session = token_store.issue_session(
        username=challenge.username,
        roles=challenge.roles,
        ttl_minutes=REA_TOKEN_TTL_MINUTES,
    )

    return VerifyResponse(
        token=session.token,
        expires_in_minutes=REA_TOKEN_TTL_MINUTES,
        username=session.username,
        roles=session.roles,
    )


@router.get("/me")
def me(authorization: Optional[str] = Header(default=None)) -> Dict[str, Any]:
    token = _extract_bearer(authorization)
    info = token_store.validate_session(token or "")
    if info is None:
        raise HTTPException(status_code=401, detail="Invalid or expired session token.")

    return {
        "username": info.username,
        "roles": info.roles,
        "issued_at_utc": info.issued_at_utc.isoformat(),
        "expires_at_utc": info.expires_at_utc.isoformat(),
    }


@router.post("/logout")
def logout(authorization: Optional[str] = Header(default=None)) -> Dict[str, Any]:
    token = _extract_bearer(authorization)
    if not token:
        raise HTTPException(status_code=400, detail="Missing bearer token.")
    ok = token_store.revoke(token)
    return {"revoked": bool(ok)}
