"""Secure Questrade token lifecycle contracts (network activation disabled)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Protocol

from backend.app.brokers.operational_state import BrokerOperationalState, operation_result
from backend.brokers.questrade.endpoint_security import validate_api_server


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class QuestradeTokenBundle:
    access_token: str = field(repr=False)
    refresh_token: str = field(repr=False)
    api_server: str
    expires_at: datetime
    acquired_at: datetime
    token_type: str = "Bearer"
    generation: int = 1

    def metadata(self, *, now: datetime | None = None) -> dict[str, Any]:
        current = now or _utc_now()
        return {
            "access_token_present": bool(self.access_token),
            "refresh_token_present": bool(self.refresh_token),
            "api_server": validate_api_server(self.api_server).sanitized_metadata(),
            "expires_at": self.expires_at.isoformat(),
            "acquired_at": self.acquired_at.isoformat(),
            "expired": current >= self.expires_at,
            "seconds_remaining": max(0, int((self.expires_at - current).total_seconds())),
            "token_type": self.token_type,
            "generation": self.generation,
            "token_values_returned": False,
        }

class RefreshTokenStore(Protocol):
    """Secure-store interface; implementations must replace atomically."""

    def load(self) -> QuestradeTokenBundle | str | None: ...

    def replace(self, bundle: QuestradeTokenBundle) -> None: ...

    def clear(self) -> None: ...


class InMemoryRefreshTokenStore:
    """Test/dev store that never persists to disk."""

    def __init__(self) -> None:
        self._value: QuestradeTokenBundle | str | None = None

    def load(self) -> QuestradeTokenBundle | str | None:
        return self._value

    def replace(self, bundle: QuestradeTokenBundle) -> None:
        self._value = bundle

    def load_refresh_token(self) -> str | None:
        if isinstance(self._value, QuestradeTokenBundle):
            return self._value.refresh_token
        return self._value

    def save_refresh_token(self, token: str) -> None:
        self._value = str(token) if token else None

    def clear(self) -> None:
        self._value = None


class TokenLifecycle:
    """Token metadata and rotation boundary; OAuth/network calls remain disabled."""

    def __init__(
        self,
        store: RefreshTokenStore | None = None,
        *,
        now: datetime | None = None,
    ) -> None:
        self.store = store or InMemoryRefreshTokenStore()
        self.activated = False
        self._now = now

    def status(self) -> dict[str, Any]:
        value = self._load()
        bundle = value if isinstance(value, QuestradeTokenBundle) else None
        has_refresh = bool(bundle.refresh_token if bundle else value)
        now = self._now or _utc_now()
        if bundle and now >= bundle.expires_at:
            state = BrokerOperationalState.TOKEN_EXPIRED
        elif bundle and bundle.access_token:
            state = BrokerOperationalState.AUTHENTICATED
        elif has_refresh:
            state = BrokerOperationalState.TOKEN_REFRESH_REQUIRED
        else:
            state = BrokerOperationalState.CREDENTIALS_REQUIRED
        success = state is BrokerOperationalState.AUTHENTICATED
        return operation_result(
            broker="QUESTRADE",
            operation="token_status",
            state=state,
            success=success,
            retryable=state in {BrokerOperationalState.TOKEN_EXPIRED, BrokerOperationalState.TOKEN_REFRESH_REQUIRED},
            failure_code=None if success else state.value,
            operator_message=(
                "Questrade access-token metadata is valid"
                if success
                else "Questrade authorization or token refresh is required"
            ),
            recommended_action="" if success else "Use the separately authorized OAuth onboarding workflow",
            data={
                "activated": False,
                "has_refresh_token_in_store": has_refresh,
                "access_token_present": bool(bundle and bundle.access_token),
                "metadata": bundle.metadata(now=now) if bundle else None,
                "refresh_attempts": 0,
                "network_call_performed": False,
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
        has_refresh = bool(self._refresh_token())
        state = BrokerOperationalState.TOKEN_REFRESH_REQUIRED
        result = operation_result(
            broker="QUESTRADE",
            operation="refresh_token",
            state=state,
            retryable=True,
            failure_code=state.value,
            operator_message="Questrade token refresh requires separate operator authorization",
            recommended_action="Authorize one bounded refresh attempt in a future activation phase",
            data={
                "activated": False,
                "refresh_token_present": has_refresh,
                "refresh_attempts": 0,
                "network_call_performed": False,
            },
        ).as_dict()
        result["status"] = result["state"]
        result["failure_reason"] = result["failure_code"]
        result["activated"] = False
        return result

    def record_external_token_response(
        self,
        response: dict[str, Any],
        *,
        allow_record: bool = False,
    ) -> dict[str, Any]:
        """Validate externally acquired token material; never initiates OAuth."""
        if not allow_record:
            return operation_result(
                broker="QUESTRADE",
                operation="record_external_token_response",
                state=BrokerOperationalState.AUTHENTICATION_REQUIRED,
                failure_code="TOKEN_RECORDING_NOT_AUTHORIZED",
                operator_message="External token recording is disabled",
                recommended_action="Use a separately approved activation phase",
                data={"recorded": False, "network_call_performed": False},
            ).as_dict()
        access = str(response.get("access_token") or "")
        refresh = str(response.get("refresh_token") or "")
        server = str(response.get("api_server") or "")
        try:
            expires_in = int(response.get("expires_in") or 0)
            validated = validate_api_server(server)
        except (TypeError, ValueError):
            return operation_result(
                broker="QUESTRADE",
                operation="record_external_token_response",
                state=BrokerOperationalState.AUTHENTICATION_REQUIRED,
                failure_code="TOKEN_RESPONSE_INVALID",
                operator_message="Questrade token response metadata is invalid",
                recommended_action="Repeat external authorization after reviewing sanitized diagnostics",
                data={"recorded": False, "network_call_performed": False},
            ).as_dict()
        if not access or not refresh or expires_in <= 0:
            return operation_result(
                broker="QUESTRADE",
                operation="record_external_token_response",
                state=BrokerOperationalState.AUTHENTICATION_REQUIRED,
                failure_code="TOKEN_RESPONSE_INVALID",
                operator_message="Questrade token response is incomplete",
                data={"recorded": False, "network_call_performed": False},
            ).as_dict()
        now = self._now or _utc_now()
        previous = self._load()
        generation = previous.generation + 1 if isinstance(previous, QuestradeTokenBundle) else 1
        bundle = QuestradeTokenBundle(
            access_token=access,
            refresh_token=refresh,
            api_server=validated.base_url,
            acquired_at=now,
            expires_at=now + timedelta(seconds=expires_in),
            generation=generation,
        )
        self.store.replace(bundle)
        return operation_result(
            broker="QUESTRADE",
            operation="record_external_token_response",
            state=BrokerOperationalState.AUTHENTICATED,
            success=True,
            operator_message="Questrade token metadata recorded in the injected secure store",
            data={"recorded": True, "metadata": bundle.metadata(now=now), "network_call_performed": False},
        ).as_dict()

    def access_token_for_transport(self) -> str | None:
        value = self._load()
        if not isinstance(value, QuestradeTokenBundle):
            return None
        now = self._now or _utc_now()
        return value.access_token if now < value.expires_at else None

    def api_server_for_transport(self) -> str | None:
        value = self._load()
        return value.api_server if isinstance(value, QuestradeTokenBundle) else None

    def _load(self) -> QuestradeTokenBundle | str | None:
        loader = getattr(self.store, "load", None)
        if callable(loader):
            return loader()
        legacy = getattr(self.store, "load_refresh_token", None)
        return legacy() if callable(legacy) else None

    def _refresh_token(self) -> str | None:
        value = self._load()
        return value.refresh_token if isinstance(value, QuestradeTokenBundle) else value


__all__ = [
    "InMemoryRefreshTokenStore",
    "QuestradeTokenBundle",
    "RefreshTokenStore",
    "TokenLifecycle",
]
