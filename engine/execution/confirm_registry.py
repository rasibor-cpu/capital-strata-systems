# engine/execution/confirm_registry.py
"""
Runtime-only pending token registry (fail-closed).
Stores the currently valid 6-char token + expiry in audit/confirm_token.json

This is NOT broker wiring, and contains no secrets beyond a short-lived token.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from typing import Optional


PATH = os.path.join("audit", "confirm_token.json")


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _to_iso(dt: datetime) -> str:
    return dt.isoformat()


def _from_iso(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def _ensure_audit_dir() -> None:
    os.makedirs("audit", exist_ok=True)


def _normalize_token(t: str) -> str:
    return (t or "").strip().upper()


def _is_valid_format(t: str) -> bool:
    if len(t) != 6:
        return False
    for ch in t:
        if not ("A" <= ch <= "Z" or "0" <= ch <= "9"):
            return False
    return True


@dataclass(frozen=True)
class PendingToken:
    token: str
    expires_at_utc: str


def write_pending_token(token: str, ttl_seconds: int = 900) -> PendingToken:
    """
    Overwrites any existing pending token. Fail-closed if invalid format.
    Default TTL = 15 minutes (governance: you can lower later).
    """
    t = _normalize_token(token)
    if not _is_valid_format(t):
        raise ValueError("token must be 6 chars A-Z0-9")

    _ensure_audit_dir()
    exp = _utc_now() + timedelta(seconds=int(ttl_seconds))

    payload = {"token": t, "expires_at_utc": _to_iso(exp)}
    with open(PATH, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)

    return PendingToken(token=t, expires_at_utc=payload["expires_at_utc"])


def read_pending_token() -> Optional[PendingToken]:
    if not os.path.exists(PATH):
        return None
    try:
        with open(PATH, "r", encoding="utf-8") as f:
            d = json.load(f)
        token = _normalize_token(d.get("token", ""))
        exp = str(d.get("expires_at_utc", "")).strip()
        if not _is_valid_format(token) or not exp:
            return None
        return PendingToken(token=token, expires_at_utc=exp)
    except Exception:
        return None


def clear_pending_token() -> None:
    try:
        if os.path.exists(PATH):
            os.remove(PATH)
    except Exception:
        pass


def validate_token(candidate: str) -> bool:
    """
    True only if token matches AND not expired.
    """
    pt = read_pending_token()
    if pt is None:
        return False

    cand = _normalize_token(candidate)
    if not _is_valid_format(cand):
        return False

    try:
        exp = _from_iso(pt.expires_at_utc)
    except Exception:
        return False

    if _utc_now() > exp:
        return False

    return cand == pt.token
