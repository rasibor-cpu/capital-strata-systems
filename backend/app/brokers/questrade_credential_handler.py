from __future__ import annotations

from dataclasses import dataclass
from threading import Lock
from typing import Mapping

from backend.brokers.questrade_oauth_manager import (
    AuthRequiredError,
    ConfigurationRequiredError,
    CredentialStore,
)


@dataclass
class InMemoryQuestradeCredentialStore(CredentialStore):
    _refresh_token: str | None = None

    def __post_init__(self) -> None:
        self._lock = Lock()

    def read_refresh_token(self) -> str | None:
        with self._lock:
            return self._refresh_token

    def replace_refresh_token(self, refresh_token: str) -> None:
        if not isinstance(refresh_token, str) or not refresh_token:
            raise ConfigurationRequiredError("refresh token is required")
        with self._lock:
            self._refresh_token = refresh_token


class QuestradeCredentialHandler:
    def __init__(self, values: Mapping[str, str] | None = None, *, store: CredentialStore | None = None) -> None:
        self._values = dict(values or {})
        self.store = store or InMemoryQuestradeCredentialStore(self._values.get("QUESTRADE_REFRESH_TOKEN"))

    def require_client_configuration(self) -> tuple[str, str]:
        client_id = self._values.get("QUESTRADE_CLIENT_ID")
        client_secret = self._values.get("QUESTRADE_CLIENT_SECRET")
        if not client_id or not client_secret:
            raise ConfigurationRequiredError("Questrade client configuration is required")
        return client_id, client_secret

    def require_refresh_token(self) -> str:
        token = self.store.read_refresh_token()
        if not token:
            raise AuthRequiredError("Questrade refresh token is required")
        return token


__all__ = ["InMemoryQuestradeCredentialStore", "QuestradeCredentialHandler"]
