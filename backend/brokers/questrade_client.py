from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Mapping, Protocol
from urllib.parse import urlencode, urlparse

from .questrade_oauth_manager import (
    AuthRequiredError,
    QuestradeOAuthManager,
    QuestradeTokenSession,
)


class ProviderError(RuntimeError):
    pass


class ProviderUnavailableError(ProviderError):
    pass


class ProviderRateLimitedError(ProviderError):
    pass


class ProviderResponseError(ProviderError):
    pass


class MalformedResponseError(ProviderError):
    pass


@dataclass(frozen=True)
class RateLimitMetadata:
    remaining: str | None = None
    reset: str | None = None


@dataclass(frozen=True)
class QuestradeResponse:
    payload: Any
    status_code: int
    rate_limit: RateLimitMetadata


class QuestradeTransport(Protocol):
    def get(self, url: str, *, headers: Mapping[str, str], timeout: float) -> Any: ...


def chunk_activity_range(start: datetime, end: datetime) -> list[tuple[datetime, datetime]]:
    if start.tzinfo is None or end.tzinfo is None:
        raise ValueError("activity range must use timezone-aware datetimes")
    start = start.astimezone(timezone.utc)
    end = end.astimezone(timezone.utc)
    if end < start:
        raise ValueError("activity range end precedes start")
    chunks = []
    cursor = start
    while cursor < end:
        boundary = min(cursor + timedelta(days=31), end)
        chunks.append((cursor, boundary))
        cursor = boundary
    return chunks or [(start, end)]


class QuestradeReadOnlyClient:
    def __init__(self, *, session: QuestradeTokenSession, transport: QuestradeTransport, timeout: float = 20.0, oauth: QuestradeOAuthManager | None = None) -> None:
        if urlparse(session.api_server).scheme != "https":
            raise ValueError("Questrade API server must use HTTPS")
        self._session = session
        self._transport = transport
        self._timeout = timeout
        self._oauth = oauth
        self.last_rate_limit = RateLimitMetadata()

    @property
    def session(self) -> QuestradeTokenSession:
        return self._session

    def _get(self, path: str, *, query: Mapping[str, Any] | None = None, retried: bool = False) -> Any:
        url = f"{self._session.api_server}/v1/{path.lstrip('/')}"
        if query:
            url += "?" + urlencode({key: value for key, value in query.items() if value is not None})
        try:
            response = self._transport.get(url, headers={"Authorization": f"Bearer {self._session.access_token}"}, timeout=self._timeout)
        except (TimeoutError, OSError) as exc:
            raise ProviderUnavailableError("Questrade provider unavailable") from exc
        status = int(getattr(response, "status_code", 200))
        headers = getattr(response, "headers", {}) or {}
        self.last_rate_limit = RateLimitMetadata(headers.get("X-RateLimit-Remaining"), headers.get("X-RateLimit-Reset"))
        if status == 401 and self._oauth is not None and not retried:
            try:
                self._session = self._oauth.refresh()
            except Exception as exc:
                raise AuthRequiredError("Questrade authentication failed") from exc
            return self._get(path, query=query, retried=True)
        if status == 401:
            raise AuthRequiredError("Questrade authentication failed")
        if status == 403:
            raise ProviderResponseError("Questrade authorization denied")
        if status == 429:
            raise ProviderRateLimitedError("Questrade rate limit reached")
        if status >= 500:
            raise ProviderUnavailableError("Questrade provider unavailable")
        if status >= 400:
            raise ProviderResponseError("Questrade provider request failed")
        try:
            payload = response.json()
        except (ValueError, AttributeError) as exc:
            raise MalformedResponseError("Questrade response was not valid JSON") from exc
        if not isinstance(payload, Mapping):
            raise MalformedResponseError("Questrade response must be an object")
        return payload

    def get_time(self) -> Any: return self._get("time")
    def get_accounts(self) -> Any: return self._get("accounts")
    def get_positions(self, account_id: str) -> Any: return self._get(f"accounts/{account_id}/positions")
    def get_balances(self, account_id: str) -> Any: return self._get(f"accounts/{account_id}/balances")
    def get_executions(self, account_id: str, **query: Any) -> Any: return self._get(f"accounts/{account_id}/executions", query=query)
    def get_orders(self, account_id: str, **query: Any) -> Any: return self._get(f"accounts/{account_id}/orders", query=query)

    def get_activities(self, account_id: str, start_time: datetime, end_time: datetime) -> list[Any]:
        results = []
        for start, end in chunk_activity_range(start_time, end_time):
            payload = self._get(f"accounts/{account_id}/activities", query={"startTime": start.isoformat(), "endTime": end.isoformat()})
            results.extend(payload.get("activities", []))
        return results


__all__ = ["MalformedResponseError", "ProviderRateLimitedError", "ProviderUnavailableError", "ProviderResponseError", "QuestradeReadOnlyClient", "RateLimitMetadata", "chunk_activity_range"]
