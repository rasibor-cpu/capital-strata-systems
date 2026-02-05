from __future__ import annotations

import os

DEFAULT_SUPERUSER = "robert"
DEFAULT_SUPERPASS = "123456"

def _env(name: str, default: str) -> str:
    v = os.getenv(name)
    return v.strip() if isinstance(v, str) and v.strip() else default

REA_SUPERUSER = _env("REA_SUPERUSER", DEFAULT_SUPERUSER)
REA_SUPERPASS = _env("REA_SUPERPASS", DEFAULT_SUPERPASS)

try:
    REA_TOKEN_TTL_MINUTES = int(_env("REA_TOKEN_TTL_MINUTES", "60"))
except Exception:
    REA_TOKEN_TTL_MINUTES = 60

ALLOW_DEFAULT_CREDS = _env("REA_ALLOW_DEFAULT_CREDS", "true").lower() in {"1", "true", "yes", "y"}

def using_default_creds() -> bool:
    return REA_SUPERUSER == DEFAULT_SUPERUSER and REA_SUPERPASS == DEFAULT_SUPERPASS
