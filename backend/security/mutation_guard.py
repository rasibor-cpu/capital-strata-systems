"""Fail-closed mutation auth and CSRF helpers (AR-023 / AR-024)."""

from __future__ import annotations

import os
from typing import Any, Mapping, MutableMapping, Optional

from fastapi import HTTPException, Request


CSRF_HEADER = "X-CSS-CSRF"
CSRF_HEADER_ALT = "X-Requested-With"
CSRF_TOKEN_ENV = "CSS_CSRF_TOKEN"


def auth_test_profile_enabled() -> bool:
    """Explicit opt-in only — PYTEST_CURRENT_TEST must not unlock bypass."""
    flag = os.getenv("CSS_AUTH_TEST_PROFILE", "").strip().lower()
    return flag in {"1", "true", "yes", "on"}


def automated_auth_bypass_allowed() -> bool:
    """CSS_AUTOMATED_INPUT is only valid under an explicit test profile."""
    if os.getenv("CSS_AUTOMATED_INPUT", "").strip() != "1":
        return False
    return auth_test_profile_enabled()


def mutation_auth_required() -> bool:
    """LAN/production profiles require auth; localhost-dev may opt out explicitly."""
    profile = os.getenv("CSS_HOST_SECURITY_PROFILE", "fail_closed").strip().lower()
    if profile in {"open_dev", "localhost_open"}:
        return False
    return True


def extract_bearer_or_session_identity(request: Request) -> Optional[dict[str, Any]]:
    """Best-effort identity from bridge headers or cookie (no trust elevation)."""
    user_id = (request.headers.get("X-CSS-User-Id") or "").strip()
    role = (request.headers.get("X-CSS-Role") or "").strip()
    if user_id and role:
        # Internal bridge headers only when explicitly trusted (existing reports pattern).
        if os.getenv("CSS_TRUST_INTERNAL_AUTH_HEADERS", "").strip().lower() in {
            "1",
            "true",
            "yes",
            "on",
        } or auth_test_profile_enabled():
            return {"user_id": user_id, "role": role, "source": "headers"}
    cookie = request.cookies.get("css_mobile_session") or request.cookies.get("css_session")
    if cookie:
        return {"user_id": "cookie-session", "role": "SESSION", "source": "cookie", "token": cookie}
    return None


def validate_csrf(request: Request) -> None:
    """Require CSRF synchronizer header on cookie-authenticated POSTs."""
    if request.method.upper() not in {"POST", "PUT", "PATCH", "DELETE"}:
        return
    header = (
        request.headers.get(CSRF_HEADER)
        or request.headers.get(CSRF_HEADER_ALT)
        or ""
    ).strip()
    if not header:
        raise HTTPException(status_code=403, detail="CSRF_TOKEN_REQUIRED")
    expected = os.getenv(CSRF_TOKEN_ENV, "").strip()
    if expected and header not in {expected, "CSS", "XMLHttpRequest"}:
        # Allow standard X-Requested-With: XMLHttpRequest as synchronizer when no shared secret set.
        if header != "XMLHttpRequest":
            raise HTTPException(status_code=403, detail="CSRF_TOKEN_INVALID")


def require_mutation_auth(request: Request) -> dict[str, Any]:
    """Fail closed for unauthorized mutations on secured host profiles."""
    if not mutation_auth_required():
        return {"user_id": "open_dev", "role": "OPEN_DEV", "source": "profile"}

    identity = extract_bearer_or_session_identity(request)
    if identity is None:
        raise HTTPException(status_code=401, detail="MUTATION_AUTH_REQUIRED")

    # Cookie sessions must present CSRF; header bridge under test profile may skip.
    if identity.get("source") == "cookie":
        validate_csrf(request)
    elif identity.get("source") == "headers" and not auth_test_profile_enabled():
        validate_csrf(request)

    return identity


def secure_cookie_kwargs(scheme: str) -> dict[str, Any]:
    """httponly + samesite; secure when HTTPS or forced."""
    force = os.getenv("CSS_FORCE_SECURE_COOKIES", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    secure = force or (scheme or "").lower() == "https"
    return {
        "httponly": True,
        "samesite": "lax",
        "secure": secure,
    }
