from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Mapping, Protocol
from urllib.parse import urlparse


class ConfigurationRequiredError(RuntimeError):
    pass


class AuthRequiredError(RuntimeError):
    pass


class TokenRefreshFailedError(RuntimeError):
    pass


class CredentialStore(Protocol):
    def read_refresh_token(self) -> str | None: ...
    def replace_refresh_token(self, refresh_token: str) -> None: ...


class FileQuestradeCredentialStore:
    def __init__(self, path: str) -> None:
        self.path = os.path.abspath(path)

    def read_refresh_token(self) -> str | None:
        try:
            with open(self.path, encoding="utf-8") as handle:
                payload = json.load(handle)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            if isinstance(exc, FileNotFoundError):
                return None
            raise ConfigurationRequiredError("Questrade credential storage is invalid") from exc
        token = payload.get("refresh_token") if isinstance(payload, dict) else None
        return token if isinstance(token, str) and token else None

    def replace_refresh_token(self, refresh_token: str) -> None:
        if not isinstance(refresh_token, str) or not refresh_token:
            raise ConfigurationRequiredError("refresh token is required")
        directory = os.path.dirname(self.path)
        os.makedirs(directory, mode=0o700, exist_ok=True)
        fd, temporary = tempfile.mkstemp(prefix=".questrade-", dir=directory, text=True)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump({"refresh_token": refresh_token}, handle)
                handle.flush()
                os.fsync(handle.fileno())
            os.chmod(temporary, 0o600)
            os.replace(temporary, self.path)
        except Exception:
            try:
                os.unlink(temporary)
            except OSError:
                pass
            raise


@dataclass(frozen=True)
class QuestradeTokenSession:
    access_token: str
    refresh_token: str
    api_server: str
    expires_at_utc: datetime
    token_type: str = "Bearer"

    def __repr__(self) -> str:
        return (
            "QuestradeTokenSession(access_token=<redacted>, "
            "refresh_token=<redacted>, api_server={!r}, expires_at_utc={!r}, "
            "token_type={!r})"
        ).format(self.api_server, self.expires_at_utc, self.token_type)

    def is_expired(self, *, now: datetime | None = None) -> bool:
        current = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
        return current >= self.expires_at_utc


def _https_url(value: Any, field: str) -> str:
    if not isinstance(value, str) or urlparse(value).scheme != "https" or not urlparse(value).netloc:
        raise ConfigurationRequiredError(f"{field} must be an HTTPS URL")
    return value.rstrip("/")


def parse_token_response(payload: Mapping[str, Any], *, refresh_token: str | None = None, now: datetime | None = None) -> QuestradeTokenSession:
    if not isinstance(payload, Mapping):
        raise AuthRequiredError("malformed token response")
    access = payload.get("access_token")
    rotated = payload.get("refresh_token") or refresh_token
    expires = payload.get("expires_in")
    if not isinstance(access, str) or not access or not isinstance(rotated, str) or not rotated:
        raise AuthRequiredError("token response is incomplete")
    if isinstance(expires, bool) or not isinstance(expires, (int, float)) or expires <= 0:
        raise AuthRequiredError("token expiry is invalid")
    api_server = _https_url(payload.get("api_server"), "api_server")
    issued = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    return QuestradeTokenSession(
        access_token=access,
        refresh_token=rotated,
        api_server=api_server,
        expires_at_utc=issued + timedelta(seconds=float(expires)),
        token_type=str(payload.get("token_type") or "Bearer"),
    )


class QuestradeOAuthManager:
    def __init__(self, *, client_id: str, client_secret: str, token_transport: Any, credential_store: CredentialStore) -> None:
        if not client_id or not client_secret:
            raise ConfigurationRequiredError("Questrade OAuth client configuration is required")
        self._client_id = client_id
        self._client_secret = client_secret
        self._transport = token_transport
        self._store = credential_store

    def refresh(self) -> QuestradeTokenSession:
        old = self._store.read_refresh_token()
        if not old:
            raise AuthRequiredError("Questrade refresh token is required")
        try:
            response = self._transport.post_token(
                client_id=self._client_id,
                client_secret=self._client_secret,
                refresh_token=old,
            )
            session = parse_token_response(response, refresh_token=old)
        except (ConfigurationRequiredError, AuthRequiredError) as exc:
            raise TokenRefreshFailedError("Questrade token refresh failed") from exc
        self._store.replace_refresh_token(session.refresh_token)
        return session


__all__ = [
    "AuthRequiredError", "ConfigurationRequiredError", "CredentialStore",
    "FileQuestradeCredentialStore",
    "QuestradeOAuthManager", "QuestradeTokenSession", "TokenRefreshFailedError",
    "parse_token_response",
]
