"""
Auth Router – REA Capital Trading Engine (Phase 1)

Correct workflow (2-step):
1) POST /auth/login (username+password) -> returns 6-digit challenge code
2) POST /auth/verify (challenge code)   -> returns 6-digit session token (used for LIVE)
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any

from .auth_config import (
    REA_SUPERUSER,
    REA_SUPERPASS,
    REA_TOKEN_TTL_MINUTES,
    ALLOW_DEFAULT_CREDS,
    using_default_creds,
)
from .token_store import token_store

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=64)
    password: str = Field(..., min_length=1, max_length=128)


class LoginResponse(BaseModel):
    challenge_code: str  # 6 digits
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


@router.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest) -> LoginResponse:
    if using_default_creds() and not ALLOW_DEFAULT_CREDS:
        raise HTTPException(status_code=503, detail="Auth not configured (default creds disabled).")

    username = payload.username.strip()
    password = payload.password

    if username != REA_SUPERUSER or password != REA_SUPERPASS:
        raise HTTPException(status_code=401, detail="Invalid username/password.")

    roles = ["superuser"]
    challenge = token_store.issue_challenge(username=username, roles=roles, ttl_minutes=REA_TOKEN_TTL_MINUTES)

    return LoginResponse(
        challenge_code=challenge.code,
        expires_in_minutes=REA_TOKEN_TTL_MINUTES,
        username=challenge.username,
        roles=challenge.roles,
    )


@router.post("/verify", response_model=VerifyResponse)
def verify(payload: VerifyRequest) -> VerifyResponse:
    code = (payload.challenge_code or "").strip()
    if (not code.isdigit()) or len(code) != 6:
        raise HTTPException(status_code=400, detail="Challenge code must be exactly 6 digits.")

    challenge = token_store.consume_challenge(code)
    if challenge is None:
        raise HTTPException(status_code=401, detail="Invalid or expired challenge code.")

    session = token_store.issue_session(username=challenge.username, roles=challenge.roles, ttl_minutes=REA_TOKEN_TTL_MINUTES)

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
