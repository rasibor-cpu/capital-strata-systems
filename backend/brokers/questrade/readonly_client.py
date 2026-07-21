"""Allowlisted Questrade GET-only HTTP boundary."""

from __future__ import annotations

from dataclasses import dataclass, field
import re
import time
from typing import Any, Callable, Mapping, Protocol
import uuid

from backend.app.brokers.operational_state import BrokerOperationalState, operation_result
from backend.brokers.questrade.endpoint_security import safe_join_api_path, validate_api_server
from backend.brokers.questrade.token_lifecycle import TokenLifecycle


_ALLOWED_PATHS = (
    re.compile(r"^/accounts$"),
    re.compile(r"^/accounts/[^/]+/(balances|positions|activities)$"),
    re.compile(r"^/markets$"),
    re.compile(r"^/markets/quotes$"),
    re.compile(r"^/symbols$"),
    re.compile(r"^/symbols/[0-9]+/options$"),
)


@dataclass(frozen=True)
class QuestradeHttpResponse:
    status_code: int
    payload: Mapping[str, Any] = field(default_factory=dict, repr=False)
    headers: Mapping[str, str] = field(default_factory=dict)


class QuestradeTransport(Protocol):
    def send(
        self,
        *,
        method: str,
        url: str,
        headers: Mapping[str, str],
        params: Mapping[str, Any],
        timeout_seconds: float,
    ) -> QuestradeHttpResponse: ...


class DisabledQuestradeTransport:
    def send(self, **_: Any) -> QuestradeHttpResponse:
        raise RuntimeError("QUESTRADE_NETWORK_TRANSPORT_DISABLED")


@dataclass(frozen=True)
class QuestradeHttpResult:
    success: bool
    state: BrokerOperationalState
    payload: Mapping[str, Any] = field(default_factory=dict, repr=False)
    failure_code: str | None = None
    retryable: bool = False
    retries: int = 0
    latency_ms: float | None = None
    retry_after_seconds: float | None = None
    rate_limit_remaining: int | None = None
    correlation_id: str = ""

    def diagnostics(self, operation: str) -> dict[str, Any]:
        return operation_result(
            broker="QUESTRADE",
            operation=operation,
            state=self.state,
            success=self.success,
            retryable=self.retryable,
            expected_condition=self.state is not BrokerOperationalState.FAILED,
            failure_code=self.failure_code,
            operator_message="Questrade read-only request completed" if self.success else "Questrade read-only request unavailable",
            recommended_action="" if self.success else "Review sanitized Questrade readiness diagnostics",
            data={
                "http_payload_returned": False,
                "retries": self.retries,
                "retry_after_seconds": self.retry_after_seconds,
                "rate_limit_remaining": self.rate_limit_remaining,
                "method": "GET",
                "read_only_allowlist": True,
            },
            latency_ms=self.latency_ms,
            correlation_id=self.correlation_id or None,
        ).as_dict()


class QuestradeReadOnlyClient:
    def __init__(
        self,
        tokens: TokenLifecycle,
        *,
        transport: QuestradeTransport | None = None,
        max_retries: int = 2,
        timeout_seconds: float = 10.0,
        sleeper: Callable[[float], None] = time.sleep,
        cancelled: Callable[[], bool] | None = None,
    ) -> None:
        self.tokens = tokens
        self.transport = transport or DisabledQuestradeTransport()
        self.max_retries = max(0, min(int(max_retries), 3))
        self.timeout_seconds = max(0.1, min(float(timeout_seconds), 30.0))
        self.sleeper = sleeper
        self.cancelled = cancelled or (lambda: False)

    def request(
        self,
        path: str,
        *,
        method: str = "GET",
        params: Mapping[str, Any] | None = None,
        success_state: BrokerOperationalState = BrokerOperationalState.READ_ONLY_READY,
    ) -> QuestradeHttpResult:
        if str(method).upper() != "GET":
            return QuestradeHttpResult(
                success=False,
                state=BrokerOperationalState.EXECUTION_BLOCKED,
                failure_code="QUESTRADE_WRITE_METHOD_BLOCKED",
            )
        normalized_path = "/" + str(path or "").lstrip("/")
        if not any(pattern.fullmatch(normalized_path) for pattern in _ALLOWED_PATHS):
            return QuestradeHttpResult(
                success=False,
                state=BrokerOperationalState.EXECUTION_BLOCKED,
                failure_code="QUESTRADE_PATH_NOT_ALLOWLISTED",
            )
        token = self.tokens.access_token_for_transport()
        server_value = self.tokens.api_server_for_transport()
        if not token or not server_value:
            return QuestradeHttpResult(
                success=False,
                state=BrokerOperationalState.AUTHENTICATION_REQUIRED,
                failure_code="QUESTRADE_ACCESS_TOKEN_REQUIRED",
            )
        try:
            server = validate_api_server(server_value)
            url = safe_join_api_path(server, normalized_path)
        except ValueError:
            return QuestradeHttpResult(
                success=False,
                state=BrokerOperationalState.CONFIGURATION_REQUIRED,
                failure_code="QUESTRADE_API_SERVER_REJECTED",
            )

        started = time.perf_counter()
        for attempt in range(self.max_retries + 1):
            if self.cancelled():
                return QuestradeHttpResult(
                    success=False,
                    state=BrokerOperationalState.DEGRADED,
                    failure_code="QUESTRADE_REQUEST_CANCELLED",
                    retries=attempt,
                )
            try:
                response = self.transport.send(
                    method="GET",
                    url=url,
                    headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
                    params=dict(params or {}),
                    timeout_seconds=self.timeout_seconds,
                )
            except Exception:  # transport boundary; never expose exception/token/url
                return QuestradeHttpResult(
                    success=False,
                    state=BrokerOperationalState.PROVIDER_UNAVAILABLE,
                    failure_code="QUESTRADE_PROVIDER_UNAVAILABLE",
                    retryable=True,
                    retries=attempt,
                    latency_ms=(time.perf_counter() - started) * 1000,
                    correlation_id=uuid.uuid4().hex,
                )
            remaining = _integer_header(response.headers, "X-RateLimit-Remaining")
            retry_after = _float_header(response.headers, "Retry-After")
            if response.status_code == 429:
                if attempt < self.max_retries:
                    self.sleeper(min(retry_after if retry_after is not None else 2**attempt, 5.0))
                    continue
                return QuestradeHttpResult(
                    success=False,
                    state=BrokerOperationalState.RATE_LIMITED,
                    failure_code="QUESTRADE_RATE_LIMITED",
                    retryable=True,
                    retries=attempt,
                    retry_after_seconds=retry_after,
                    rate_limit_remaining=remaining,
                    latency_ms=(time.perf_counter() - started) * 1000,
                )
            if response.status_code in {401, 403}:
                return QuestradeHttpResult(
                    success=False,
                    state=BrokerOperationalState.AUTHENTICATION_REQUIRED,
                    failure_code="QUESTRADE_AUTHORIZATION_REVOKED",
                    retries=attempt,
                    latency_ms=(time.perf_counter() - started) * 1000,
                )
            if response.status_code >= 500:
                if attempt < self.max_retries:
                    self.sleeper(min(2**attempt, 5.0))
                    continue
                return QuestradeHttpResult(
                    success=False,
                    state=BrokerOperationalState.PROVIDER_UNAVAILABLE,
                    failure_code="QUESTRADE_PROVIDER_UNAVAILABLE",
                    retryable=True,
                    retries=attempt,
                    latency_ms=(time.perf_counter() - started) * 1000,
                    correlation_id=uuid.uuid4().hex,
                )
            if response.status_code < 200 or response.status_code >= 300:
                return QuestradeHttpResult(
                    success=False,
                    state=BrokerOperationalState.DEGRADED,
                    failure_code="QUESTRADE_UNEXPECTED_RESPONSE",
                    retries=attempt,
                    latency_ms=(time.perf_counter() - started) * 1000,
                    correlation_id=uuid.uuid4().hex,
                )
            return QuestradeHttpResult(
                success=True,
                state=success_state,
                payload=dict(response.payload),
                retries=attempt,
                latency_ms=(time.perf_counter() - started) * 1000,
                rate_limit_remaining=remaining,
            )
        raise AssertionError("bounded retry loop exhausted")


def _float_header(headers: Mapping[str, str], key: str) -> float | None:
    try:
        return float(headers.get(key, ""))
    except (TypeError, ValueError):
        return None


def _integer_header(headers: Mapping[str, str], key: str) -> int | None:
    try:
        return int(headers.get(key, ""))
    except (TypeError, ValueError):
        return None


__all__ = [
    "DisabledQuestradeTransport",
    "QuestradeHttpResponse",
    "QuestradeHttpResult",
    "QuestradeReadOnlyClient",
    "QuestradeTransport",
]
