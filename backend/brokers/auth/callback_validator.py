"""Offline callback validation; this module exposes no HTTP endpoint."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Sequence
from urllib.parse import urlsplit

from backend.brokers.auth.authorization_state import AuthorizationState, AuthorizationStateStore


@dataclass(frozen=True)
class CallbackValidation:
    valid: bool
    broker: str
    state_id: str
    correlation_id: str
    authorization_code_present: bool
    code_returned: bool = False


class CallbackValidator:
    def __init__(self, states: AuthorizationStateStore, *, approved_callbacks: set[str]):
        self.states = states
        self.approved_callbacks = {str(value) for value in approved_callbacks}

    def validate(
        self,
        *,
        callback_uri: str,
        state_id: str,
        state_value: str,
        authorization_code: str,
    ) -> CallbackValidation:
        parsed = urlsplit(str(callback_uri))
        if parsed.scheme != "https" or callback_uri not in self.approved_callbacks:
            raise PermissionError("OAUTH_CALLBACK_URI_REJECTED")
        if not str(authorization_code).strip():
            raise ValueError("OAUTH_AUTHORIZATION_CODE_MISSING")
        state = self.states.consume(state_id, state_value)
        if state.callback_uri != callback_uri:
            raise PermissionError("OAUTH_CALLBACK_BINDING_MISMATCH")
        return CallbackValidation(
            valid=True,
            broker=state.broker,
            state_id=state.state_id,
            correlation_id=state.correlation_id,
            authorization_code_present=True,
            code_returned=False,
        )

    def validate_parameters(
        self,
        *,
        callback_uri: str,
        state_id: str,
        parameters: Mapping[str, str | Sequence[str]],
    ) -> CallbackValidation:
        normalized: dict[str, str] = {}
        for key, value in parameters.items():
            if isinstance(value, str):
                normalized[str(key)] = value
                continue
            rows = [str(item) for item in value]
            if len(rows) != 1:
                raise PermissionError(f"OAUTH_CALLBACK_PARAMETER_DUPLICATE:{key}")
            normalized[str(key)] = rows[0]
        if normalized.get("error"):
            raise PermissionError("OAUTH_PROVIDER_RETURNED_ERROR")
        if set(normalized) - {"code", "state"}:
            raise PermissionError("OAUTH_CALLBACK_PARAMETER_REJECTED")
        return self.validate(
            callback_uri=callback_uri,
            state_id=state_id,
            state_value=normalized.get("state", ""),
            authorization_code=normalized.get("code", ""),
        )


__all__ = ["CallbackValidation", "CallbackValidator"]
