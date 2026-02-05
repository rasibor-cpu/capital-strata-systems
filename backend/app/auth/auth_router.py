from __future__ import annotations

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from datetime import datetime, timedelta

from backend.app.auth.token_store import token_store
from backend.app.auth.otp_sender import send_otp_email
from backend.app.auth.auth_config import USERS


router = APIRouter(prefix="/auth", tags=["auth"])


# ------------------------
# Models
# ------------------------

class LoginRequest(BaseModel):
    username: str
    password: str


class VerifyRequest(BaseModel):
    challenge_code: str


# ------------------------
# Routes
# ------------------------

@router.post("/login")
def login(req: LoginRequest):
    user = USERS.get(req.username.lower())
    if not user or user["password"] != req.password:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    # Generate OTP
    otp = token_store.issue_challenge(
        username=req.username,
        roles=user["roles"],
        ttl_seconds=300
    )

    # Send OTP via email
    try:
        send_otp_email(
            to_email=user["email"],
            otp_code=otp
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"OTP delivery failed: {e}")

    return {
        "ok": True,
        "message": "Verification code sent",
        "sent_to": user["email"][:3] + "***"
    }


@router.post("/verify")
def verify(req: VerifyRequest):
    info = token_store.validate(req.challenge_code)
    if not info:
        raise HTTPException(status_code=401, detail="Invalid or expired code")

    # Issue session token (6 digits)
    session_token = token_store.issue_session(info)

    return {
        "ok": True,
        "token": session_token,
        "expires_in_minutes": 60,
        "username": info.username,
        "roles": info.roles,
    }


@router.post("/logout")
def logout(token: str = Depends(token_store.require_session)):
    token_store.revoke_session(token)
    return {"ok": True}


@router.get("/me")
def me(token: str = Depends(token_store.require_session)):
    info = token_store.session_info(token)
    return {
        "username": info.username,
        "roles": info.roles,
        "issued_at_utc": info.issued_at.isoformat(),
        "expires_at_utc": info.expires_at.isoformat(),
    }
