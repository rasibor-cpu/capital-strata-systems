"""Binance API credential handling: environment-only, never logged, never in the repo.

Credentials are read from the process environment (BINANCE_API_KEY /
BINANCE_API_SECRET), which the Windows helper populates for one process only from a
DPAPI-protected file outside the repository. Loading fails closed if a credential is
missing or malformed, or if either name appears in a .env file inside the repository.
Only a short SHA-256 fingerprint of the API key is ever recorded.
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import re
from pathlib import Path
from typing import Mapping

LOGGER = logging.getLogger(__name__)

ENV_API_KEY = "BINANCE_API_KEY"
ENV_API_SECRET = "BINANCE_API_SECRET"
REPO_ENV_FILES = (".env", ".env.practice", ".env.local", ".env.binance")
_TOKEN = re.compile(r"^[A-Za-z0-9]{32,128}$")


class CredentialPolicyError(RuntimeError):
    """Credentials are missing, malformed or stored somewhere they must not be."""


class BinanceCredentials:
    """Holds the key pair; signs on request. The secret is never exposed or printed."""

    __slots__ = ("_api_key", "_secret")

    def __init__(self, api_key: str, api_secret: str) -> None:
        object.__setattr__(self, "_api_key", api_key)
        object.__setattr__(self, "_secret", api_secret.encode("ascii"))

    def __setattr__(self, name: str, value: object) -> None:
        raise AttributeError("BinanceCredentials is immutable")

    def __repr__(self) -> str:
        return f"BinanceCredentials(fingerprint={self.fingerprint}, secret=<redacted>)"

    __str__ = __repr__

    def __reduce__(self):  # pragma: no cover - defensive: never pickle secrets
        raise TypeError("BinanceCredentials cannot be serialized")

    @property
    def api_key_header(self) -> str:
        return self._api_key

    @property
    def fingerprint(self) -> str:
        return "sha256:" + hashlib.sha256(self._api_key.encode("ascii")).hexdigest()[:12]

    def sign(self, query_string: str) -> str:
        return hmac.new(self._secret, query_string.encode("ascii"), hashlib.sha256).hexdigest()


def _repo_env_hits(repo_root: Path) -> list[str]:
    hits: list[str] = []
    for name in REPO_ENV_FILES:
        path = Path(repo_root) / name
        if not path.exists():
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for var in (ENV_API_KEY, ENV_API_SECRET):
            if re.search(rf"^\s*(export\s+)?{var}\s*=", text, flags=re.MULTILINE):
                hits.append(f"{name}:{var}")
    return hits


def load_credentials(environ: Mapping[str, str], repo_root: Path) -> BinanceCredentials:
    hits = _repo_env_hits(repo_root)
    if hits:
        raise CredentialPolicyError(
            "Binance credentials found in repository env file(s) "
            f"({', '.join(hits)}); remove them and use the DPAPI helper outside the repository"
        )
    api_key = str(environ.get(ENV_API_KEY, "")).strip()
    api_secret = str(environ.get(ENV_API_SECRET, "")).strip()
    if not api_key or not api_secret:
        raise CredentialPolicyError(f"{ENV_API_KEY} and {ENV_API_SECRET} must both be set for this process")
    if not _TOKEN.match(api_key):
        raise CredentialPolicyError(f"{ENV_API_KEY} is not a valid Binance HMAC API key format")
    if not _TOKEN.match(api_secret):
        raise CredentialPolicyError(f"{ENV_API_SECRET} is not a valid Binance HMAC secret format")
    if api_key == api_secret:
        raise CredentialPolicyError("API key and secret must differ")
    credentials = BinanceCredentials(api_key, api_secret)
    LOGGER.info("binance read-only credentials loaded (%s)", credentials.fingerprint)
    return credentials
