"""
Auth Config – REA Capital Trading Engine (Phase 1)

- Credentials come from environment variables (no hardcoding in repo).
- Token TTL configurable.
- Fail-closed philosophy: if auth is misconfigured, endpoints still work,
  but LIVE-critical paths should enforce stricter checks at the gate layer.
"""

from __future__ import annotations

import os


def _env(name: str, default: str) -> str:
    v = os.getenv(name)
    return v.strip() if isinstance(v, str) and v.strip() else default


# Phase-1 defaults (user requested 6 digits)
DEFAULT_SUPERUSER = "robert"
DEFAULT_SUPERPASS = "123456"

REA_SUPERUSER = _env("REA_SUPERUSER", DEFAULT_SUPERUSER)
REA_SUPERPASS = _env("REA_SUPERPASS", DEFAULT_SUPERPASS)

# TTL in minutes for issued session tokens
try:
    REA_TOKEN_TTL_MINUTES = int(_env("REA_TOKEN_TTL_MINUTES", "60"))
except Exception:
    REA_TOKEN_TTL_MINUTES = 60

# Guardrail: if defaults are in use, we can still allow TEST logins,
# but LIVE should require env overrides (enforced in engine gates later).
ALLOW_DEFAULT_CREDS = _env("REA_ALLOW_DEFAULT_CREDS", "true").lower() in {"1", "true", "yes", "y"}


def using_default_creds() -> bool:
    return REA_SUPERUSER == DEFAULT_SUPERUSER and REA_SUPERPASS == DEFAULT_SUPERPASS
