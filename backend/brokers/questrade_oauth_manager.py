from __future__ import annotations

import json
import math
import os
import re
import stat
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


class TokenEndpointError(RuntimeError):
    def __init__(self, message: str, *, category: str, diagnostics: Mapping[str, Any] | None = None) -> None:
        super().__init__(message)
        self.category = category
        self.diagnostics = dict(diagnostics or {})


def redact_provider_description(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    text = re.sub(r"(?i)(access[_-]?token|refresh[_-]?token|authorization|token)\s*[:=]\s*[^,;\s]+", r"\1=<redacted>", value)
    text = re.sub(r"\b[A-Za-z0-9_-]{32,}\b", "<redacted>", text)
    return " ".join(text.split())[:240] or None


def safe_token_response_diagnostics(payload: Any, *, http_status: int | None = None, content_type: str | None = None) -> dict[str, Any]:
    mapping = payload if isinstance(payload, Mapping) else {}
    diagnostics = {
        "http_status": http_status,
        "content_type": content_type,
        "response_keys": sorted(str(key) for key in mapping.keys()),
        "safe_error_code": None,
        "safe_error_description": None,
        "access_token_present": bool(mapping.get("access_token")),
        "refresh_token_present": bool(mapping.get("refresh_token")),
        "expires_in_present": "expires_in" in mapping,
        "api_server_present": bool(mapping.get("api_server")),
        "token_type_present": "token_type" in mapping,
    }
    for key in ("error", "error_code", "code", "errorCode"):
        value = mapping.get(key)
        if isinstance(value, str) and re.fullmatch(r"[A-Za-z0-9_.-]{1,80}", value):
            diagnostics["safe_error_code"] = value
            break
    for key in ("error_description", "description", "message"):
        description = redact_provider_description(mapping.get(key))
        if description:
            diagnostics["safe_error_description"] = description
            break
    return diagnostics


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
        if not isinstance(payload, dict) or not isinstance(token, str) or not token:
            raise ConfigurationRequiredError("Questrade credential storage is invalid")
        self._enforce_permissions()
        return token

    def _enforce_permissions(self) -> None:
        try:
            mode = stat.S_IMODE(os.stat(self.path).st_mode)
            if mode & 0o077:
                os.chmod(self.path, 0o600)
        except OSError:
            # Windows may not expose POSIX permission bits; opening the file
            # still remains restricted by the platform ACL.
            return

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
            self._enforce_permissions()
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
    token_type = payload.get("token_type")
    if not isinstance(access, str) or not access or not isinstance(rotated, str) or not rotated:
        raise AuthRequiredError("token response is incomplete")
    if token_type is not None and (not isinstance(token_type, str) or token_type.lower() != "bearer"):
        raise AuthRequiredError("token type is invalid")
    if isinstance(expires, bool) or not isinstance(expires, (int, float)) or not math.isfinite(float(expires)) or expires <= 0:
        raise AuthRequiredError("token expiry is invalid")
    api_server = _https_url(payload.get("api_server"), "api_server")
    issued = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    return QuestradeTokenSession(
        access_token=access,
        refresh_token=rotated,
        api_server=api_server,
        expires_at_utc=issued + timedelta(seconds=float(expires)),
        token_type=str(token_type or "Bearer"),
    )


class QuestradeOAuthManager:
    def __init__(self, *, client_id: str | None = None, client_secret: str | None = None, token_transport: Any, credential_store: CredentialStore) -> None:
        self._client_id = client_id
        self._client_secret = client_secret
        self._transport = token_transport
        self._store = credential_store

    def refresh(self) -> QuestradeTokenSession:
        if not self._client_id or not self._client_secret:
            raise ConfigurationRequiredError("Questrade OAuth client configuration is required")
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

    def redeem_authorization_token(self, authorization_token: str) -> QuestradeTokenSession:
        if not isinstance(authorization_token, str) or not authorization_token.strip():
            raise AuthRequiredError("Questrade authorization token is required")
        try:
            response = self._transport.post_token(
                refresh_token=authorization_token,
            )
            session = parse_token_response(response)
        except (ConfigurationRequiredError, AuthRequiredError) as exc:
            raise TokenRefreshFailedError("Questrade token redemption failed") from exc
        self._store.replace_refresh_token(session.refresh_token)
        return session


__all__ = [
    "AuthRequiredError", "ConfigurationRequiredError", "CredentialStore",
    "FileQuestradeCredentialStore",
    "QuestradeOAuthManager", "QuestradeTokenSession", "TokenRefreshFailedError",
    "parse_token_response",
]
