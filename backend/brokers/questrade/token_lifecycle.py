"""Token lifecycle and refresh-token storage interfaces (not activated)."""

from __future__ import annotations

from typing import Any, Protocol

from backend.app.brokers.operational_state import BrokerOperationalState, operation_result

class RefreshTokenStore(Protocol):
    """Interface only — Phase 178A does not write or load live tokens."""

    def load_refresh_token(self) -> str | None: ...

    def save_refresh_token(self, token: str) -> None: ...

    def clear(self) -> None: ...


class InMemoryRefreshTokenStore:
    """Test/dev store that never persists to disk."""

    def __init__(self) -> None:
        self._token: str | None = None

    def load_refresh_token(self) -> str | None:
        return self._token

    def save_refresh_token(self, token: str) -> None:
        self._token = str(token) if token else None

    def clear(self) -> None:
        self._token = None


class TokenLifecycle:
    """Lifecycle interface. authenticate()/refresh() remain blocked in 178A."""

    def __init__(self, store: RefreshTokenStore | None = None) -> None:
        self.store = store or InMemoryRefreshTokenStore()
        self.activated = False

    def status(self) -> dict[str, Any]:
        has_refresh = bool(self.store.load_refresh_token())
        state = (
            BrokerOperationalState.AUTHENTICATION_REQUIRED
            if has_refresh
            else BrokerOperationalState.CREDENTIALS_REQUIRED
        )
        return operation_result(
            broker="QUESTRADE",
            operation="token_status",
            state=state,
            failure_code=state.value,
            operator_message=(
                "Questrade authentication is required"
                if has_refresh
                else "Questrade refresh credentials are required"
            ),
            recommended_action="Use an approved future OAuth activation workflow",
            data={
                "activated": False,
                "has_refresh_token_in_store": has_refresh,
                "access_token_present": False,
            },
        ).as_dict()

    def authenticate(self) -> dict[str, Any]:
        result = operation_result(
            broker="QUESTRADE",
            operation="authenticate",
            state=BrokerOperationalState.AUTHENTICATION_REQUIRED,
            failure_code="AUTHENTICATION_NOT_ACTIVATED",
            operator_message="Questrade authentication is not activated",
            recommended_action="Use an approved future OAuth activation workflow",
            data={"activated": False},
        ).as_dict()
        result["status"] = result["state"]
        result["failure_reason"] = result["failure_code"]
        result["activated"] = False
        return result

    def refresh(self) -> dict[str, Any]:
        result = operation_result(
            broker="QUESTRADE",
            operation="refresh_token",
            state=BrokerOperationalState.TOKEN_REFRESH_REQUIRED,
            retryable=True,
            failure_code="TOKEN_REFRESH_REQUIRED",
            operator_message="Questrade token refresh is required but not activated",
            recommended_action="Use an approved future OAuth activation workflow",
            data={"activated": False},
        ).as_dict()
        result["status"] = result["state"]
        result["failure_reason"] = result["failure_code"]
        result["activated"] = False
        return result


__all__ = ["InMemoryRefreshTokenStore", "RefreshTokenStore", "TokenLifecycle"]
