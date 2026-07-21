"""Broker-independent, offline OAuth/PKCE preparation framework."""

from __future__ import annotations

import base64
from contextlib import contextmanager
import hashlib
import secrets
import uuid
from typing import Iterator

from backend.brokers.auth.authorization_state import AuthorizationStateStore
from backend.security.vault_crypto import zeroize


class OAuthPreparation:
    __slots__ = ("broker", "state_id", "state_value", "code_challenge", "callback_uri", "correlation_id", "_verifier")

    def __init__(
        self,
        *,
        broker: str,
        state_id: str,
        state_value: str,
        code_challenge: str,
        callback_uri: str,
        correlation_id: str,
        verifier: bytearray,
    ):
        self.broker = broker
        self.state_id = state_id
        self.state_value = state_value
        self.code_challenge = code_challenge
        self.callback_uri = callback_uri
        self.correlation_id = correlation_id
        self._verifier = verifier

    def metadata(self) -> dict:
        return {
            "broker": self.broker,
            "state_id": self.state_id,
            "code_challenge": self.code_challenge,
            "callback_uri": self.callback_uri,
            "correlation_id": self.correlation_id,
            "state_value_returned": False,
            "code_verifier_returned": False,
            "browser_launch_enabled": False,
            "token_exchange_enabled": False,
        }

    @contextmanager
    def verifier_lease(self) -> Iterator[memoryview]:
        try:
            yield memoryview(self._verifier)
        finally:
            zeroize(self._verifier)

    def __repr__(self) -> str:
        return f"OAuthPreparation(broker={self.broker!r}, state_id={self.state_id!r}, secrets_redacted=True)"


class OAuthManager:
    def __init__(self, states: AuthorizationStateStore | None = None):
        self.states = states or AuthorizationStateStore()

    def prepare(self, *, broker: str, callback_uri: str) -> OAuthPreparation:
        if not str(callback_uri).startswith("https://"):
            raise ValueError("HTTPS_CALLBACK_REQUIRED")
        correlation_id = str(uuid.uuid4())
        state_value, state = self.states.issue(
            broker=broker,
            callback_uri=callback_uri,
            correlation_id=correlation_id,
        )
        verifier_text = secrets.token_urlsafe(64)
        verifier = bytearray(verifier_text.encode("ascii"))
        challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier).digest()).rstrip(b"=").decode("ascii")
        return OAuthPreparation(
            broker=str(broker).upper(),
            state_id=state.state_id,
            state_value=state_value,
            code_challenge=challenge,
            callback_uri=callback_uri,
            correlation_id=correlation_id,
            verifier=verifier,
        )


__all__ = ["OAuthManager", "OAuthPreparation"]
