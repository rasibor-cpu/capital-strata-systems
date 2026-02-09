"""
Auth config (env-driven) — REA Capital Trading Engine

This module must be import-safe. No side effects.
"""

from __future__ import annotations

import os
from typing import List


def _getenv(name: str, default: str = "") -> str:
    v = os.getenv(name)
    return default if v is None else v


def _getenv_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return int(raw.strip())
    except Exception:
        return default


# --------------------------------------------------------------------
# Superuser (dev baseline)
# --------------------------------------------------------------------
# IMPORTANT:
# - Default username must be "admin" (per project decision)
# - Default password must be "123456" (6 digits)
# - Can be overridden via env vars
REA_SUPERUSER_USERNAME: str = (_getenv("REA_SUPERUSER_USERNAME", "admin").strip() or "admin")
REA_SUPERUSER_PASSWORD: str = (_getenv("REA_SUPERUSER_PASSWORD", "123456").strip() or "123456")

# Comma-separated roles, default "superuser"
_roles_raw = _getenv("REA_SUPERUSER_ROLES", "superuser")
REA_SUPERUSER_ROLES: List[str] = [r.strip() for r in _roles_raw.split(",") if r.strip()] or ["superuser"]


# --------------------------------------------------------------------
# OTP / Email
# --------------------------------------------------------------------
OTP_TTL_SECONDS: int = _getenv_int("OTP_TTL_SECONDS", 300)

OTP_SMTP_HOST: str = _getenv("OTP_SMTP_HOST", "").strip()
OTP_SMTP_PORT: int = _getenv_int("OTP_SMTP_PORT", 587)
OTP_SMTP_USER: str = _getenv("OTP_SMTP_USER", "").strip()
OTP_SMTP_PASS: str = _getenv("OTP_SMTP_PASS", "").strip()

OTP_FROM_EMAIL: str = _getenv("OTP_FROM_EMAIL", OTP_SMTP_USER).strip()
OTP_TO_EMAIL: str = _getenv("OTP_TO_EMAIL", "").strip()
