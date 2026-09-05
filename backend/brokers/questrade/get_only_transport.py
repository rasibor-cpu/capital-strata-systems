"""Production GET-only HTTP transport for QuestradeReadOnlyClient."""

from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any, Mapping
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit, urlunsplit
import urllib.request

from backend.brokers.questrade.errors import QuestradeAdvisoryError, WriteMethodBlockedError
from backend.brokers.questrade.readonly_client import QuestradeHttpResponse


_DEFAULT_TIMEOUT_SECONDS = 10.0
_MAX_TIMEOUT_SECONDS = 15.0
_MAX_BODY_BYTES = 1_048_576
_SAFE_RESPONSE_HEADERS = ("X-RateLimit-Remaining", "Retry-After", "X-RateLimit-Reset")


@dataclass(frozen=True)
class _InjectedHttpResponse:
    status_code: int
    body: bytes
    headers: Mapping[str, str]


class QuestradeGetOnlyHttpTransport:
    """Reject non-GET before dispatch. HTTPS only. No Authorization echo."""

    def __init__(
        self,
        *,
        session: Any | None = None,
        timeout_seconds: float = _DEFAULT_TIMEOUT_SECONDS,
        max_body_bytes: int = _MAX_BODY_BYTES,
    ) -> None:
        self._session = session
        self._timeout_seconds = max(0.1, min(float(timeout_seconds), _MAX_TIMEOUT_SECONDS))
        self._max_body_bytes = max(1024, int(max_body_bytes))

    def send(
        self,
        *,
        method: str,
        url: str,
        headers: Mapping[str, str],
        params: Mapping[str, Any],
        timeout_seconds: float,
    ) -> QuestradeHttpResponse:
        if str(method or "").upper() != "GET":
            raise WriteMethodBlockedError("QUESTRADE_WRITE_METHOD_BLOCKED")
        parsed = urlsplit(str(url or ""))
        if parsed.scheme.lower() != "https":
            raise QuestradeAdvisoryError("QUESTRADE_HTTPS_REQUIRED", code="QUESTRADE_HTTPS_REQUIRED")
        if parsed.username or parsed.password:
            raise QuestradeAdvisoryError("QUESTRADE_URL_USERINFO_REJECTED", code="QUESTRADE_URL_USERINFO_REJECTED")
        timeout = max(0.1, min(float(timeout_seconds or self._timeout_seconds), _MAX_TIMEOUT_SECONDS))
        outbound_headers = {
            "Accept": "application/json",
            "Authorization": str(headers.get("Authorization") or ""),
        }
        try:
            raw = self._dispatch(url=str(url), headers=outbound_headers, params=dict(params or {}), timeout=timeout)
        except WriteMethodBlockedError:
            raise
        except QuestradeAdvisoryError:
            raise
        except Exception as exc:
            raise QuestradeAdvisoryError(
                "QUESTRADE_PROVIDER_UNAVAILABLE",
                code="QUESTRADE_PROVIDER_UNAVAILABLE",
            ) from exc
        if len(raw.body) > self._max_body_bytes:
            raise QuestradeAdvisoryError("QUESTRADE_RESPONSE_BODY_TOO_LARGE", code="QUESTRADE_RESPONSE_BODY_TOO_LARGE")
        try:
            parsed_json = json.loads(raw.body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise QuestradeAdvisoryError(
                "QUESTRADE_RESPONSE_NOT_JSON",
                code="QUESTRADE_RESPONSE_NOT_JSON",
            ) from None
        if not isinstance(parsed_json, dict):
            raise QuestradeAdvisoryError(
                "QUESTRADE_RESPONSE_NOT_JSON_OBJECT",
                code="QUESTRADE_RESPONSE_NOT_JSON_OBJECT",
            )
        safe_headers = {
            key: str(raw.headers.get(key))
            for key in _SAFE_RESPONSE_HEADERS
            if raw.headers.get(key) not in (None, "")
        }
        return QuestradeHttpResponse(status_code=int(raw.status_code), payload=parsed_json, headers=safe_headers)

    def _dispatch(
        self,
        *,
        url: str,
        headers: Mapping[str, str],
        params: Mapping[str, Any],
        timeout: float,
    ) -> _InjectedHttpResponse:
        if self._session is not None:
            return _dispatch_injected(self._session, url=url, headers=headers, params=params, timeout=timeout)
        return _dispatch_urllib(url=url, headers=headers, params=params, timeout=timeout, max_body=self._max_body_bytes)

    def __repr__(self) -> str:
        return "QuestradeGetOnlyHttpTransport(method='GET', secret_material_redacted=True)"


def _dispatch_injected(
    session: Any,
    *,
    url: str,
    headers: Mapping[str, str],
    params: Mapping[str, Any],
    timeout: float,
) -> _InjectedHttpResponse:
    if callable(session) and not hasattr(session, "request"):
        response = session("GET", url, headers=dict(headers), params=dict(params), timeout=timeout)
    else:
        request_fn = getattr(session, "request", None)
        if not callable(request_fn):
            raise QuestradeAdvisoryError("QUESTRADE_PROVIDER_UNAVAILABLE", code="QUESTRADE_PROVIDER_UNAVAILABLE")
        response = request_fn("GET", url, headers=dict(headers), params=dict(params), timeout=timeout)
    status = int(getattr(response, "status_code", getattr(response, "status", 0)))
    body = getattr(response, "content", None)
    if body is None:
        text = getattr(response, "text", "")
        body = text.encode("utf-8") if isinstance(text, str) else bytes(text or b"")
    elif isinstance(body, str):
        body = body.encode("utf-8")
    header_map = dict(getattr(response, "headers", {}) or {})
    return _InjectedHttpResponse(status_code=status, body=bytes(body), headers=header_map)


def _dispatch_urllib(
    *,
    url: str,
    headers: Mapping[str, str],
    params: Mapping[str, Any],
    timeout: float,
    max_body: int,
) -> _InjectedHttpResponse:
    parsed = urlsplit(url)
    query = urlencode({key: value for key, value in params.items() if value not in (None, "")})
    joined = urlunsplit((parsed.scheme, parsed.netloc, parsed.path, query, ""))
    request = urllib.request.Request(
        joined,
        headers={"Accept": "application/json", "Authorization": str(headers.get("Authorization") or "")},
        method="GET",
    )
    opener = urllib.request.build_opener(_RejectRedirectHandler)
    try:
        with opener.open(request, timeout=timeout) as response:
            raw = response.read(max_body + 1)
            status = int(getattr(response, "status", 200))
            header_map = {key: value for key, value in response.headers.items()}
    except HTTPError as exc:
        raw = exc.read(max_body + 1) if exc.fp is not None else b"{}"
        return _InjectedHttpResponse(status_code=int(exc.code), body=raw, headers=dict(exc.headers or {}))
    except URLError as exc:
        raise QuestradeAdvisoryError("QUESTRADE_PROVIDER_UNAVAILABLE", code="QUESTRADE_PROVIDER_UNAVAILABLE") from exc
    return _InjectedHttpResponse(status_code=status, body=raw, headers=header_map)


class _RejectRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # type: ignore[override]
        raise QuestradeAdvisoryError("QUESTRADE_REDIRECT_REJECTED", code="QUESTRADE_REDIRECT_REJECTED")


__all__ = ["QuestradeGetOnlyHttpTransport"]
