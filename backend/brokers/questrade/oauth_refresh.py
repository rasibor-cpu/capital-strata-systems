"""Bounded Questrade OAuth refresh. One POST. Access token stays memory-only."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Mapping, Protocol
from urllib.parse import urlencode, urlsplit
import json
import urllib.error
import urllib.request

from backend.brokers.questrade.endpoint_security import validate_api_server
from backend.brokers.questrade.errors import (
    QuestradeAdvisoryError,
    TokenStoreError,
    WriteMethodBlockedError,
)
from backend.brokers.questrade.token_lifecycle import QuestradeTokenBundle


QUESTRADE_TOKEN_URL = "https://login.questrade.com/oauth2/token"
_TOKEN_HOST = "login.questrade.com"
_TOKEN_PATH = "/oauth2/token"
_DEFAULT_TIMEOUT_SECONDS = 10.0
_MAX_TIMEOUT_SECONDS = 15.0
_MAX_BODY_BYTES = 16_384


@dataclass(frozen=True)
class QuestradeOAuthHttpResponse:
    status_code: int
    payload: Mapping[str, Any] = field(default_factory=dict, repr=False)
    headers: Mapping[str, str] = field(default_factory=dict)


class QuestradeOAuthFormTransport(Protocol):
    def post_form(
        self,
        *,
        url: str,
        data: Mapping[str, str],
        headers: Mapping[str, str],
        timeout_seconds: float,
        allow_redirects: bool,
    ) -> QuestradeOAuthHttpResponse: ...


class QuestradeBoundedOAuthRefresh:
    """Exactly one refresh attempt. Persist rotated refresh token before success."""

    def __init__(
        self,
        store: Any,
        *,
        transport: QuestradeOAuthFormTransport | None = None,
        now: datetime | None = None,
        timeout_seconds: float = _DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        self._store = store
        self._transport = transport or QuestradeOAuthFormTransportImpl()
        self._now = now
        self._timeout_seconds = max(0.1, min(float(timeout_seconds), _MAX_TIMEOUT_SECONDS))
        self._memory_bundle: QuestradeTokenBundle | None = None

    def refresh(self) -> dict[str, Any]:
        try:
            refresh_token = _load_refresh_token(self._store)
        except TokenStoreError as exc:
            return _failure(exc.code, attempted=False)
        except Exception:
            return _failure("QUESTRADE_TOKEN_STORE_UNAVAILABLE", attempted=False)
        if not refresh_token:
            return _failure("QUESTRADE_REFRESH_TOKEN_MISSING", attempted=False)
        try:
            response = self._transport.post_form(
                url=QUESTRADE_TOKEN_URL,
                data={"grant_type": "refresh_token", "refresh_token": refresh_token},
                headers={
                    "Accept": "application/json",
                    "Content-Type": "application/x-www-form-urlencoded",
                },
                timeout_seconds=self._timeout_seconds,
                allow_redirects=False,
            )
        except WriteMethodBlockedError:
            return _failure("QUESTRADE_WRITE_METHOD_BLOCKED", attempted=True)
        except QuestradeAdvisoryError as exc:
            return _failure(exc.code, attempted=True)
        except Exception:
            return _failure("QUESTRADE_OAUTH_TRANSPORT_FAILED", attempted=True)
        return self._complete(response)

    def _complete(self, response: QuestradeOAuthHttpResponse) -> dict[str, Any]:
        if int(response.status_code) in {301, 302, 303, 307, 308}:
            return _failure("QUESTRADE_OAUTH_REDIRECT_REJECTED", attempted=True)
        if int(response.status_code) in {401, 403}:
            return _failure("QUESTRADE_AUTHORIZATION_REVOKED", attempted=True)
        if int(response.status_code) < 200 or int(response.status_code) >= 300:
            return _failure("QUESTRADE_OAUTH_RESPONSE_INVALID", attempted=True)
        payload = response.payload if isinstance(response.payload, Mapping) else {}
        access = str(payload.get("access_token") or "")
        refresh = str(payload.get("refresh_token") or "")
        server = str(payload.get("api_server") or "")
        try:
            expires_in = int(payload.get("expires_in"))
        except (TypeError, ValueError):
            return _failure("QUESTRADE_OAUTH_RESPONSE_INVALID", attempted=True)
        if not access or not refresh or expires_in <= 0:
            return _failure("QUESTRADE_OAUTH_RESPONSE_INVALID", attempted=True)
        try:
            validated = validate_api_server(server)
        except ValueError as exc:
            code = str(exc) if str(exc).startswith("API_SERVER_") else "API_SERVER_REJECTED"
            return _failure(code, attempted=True)
        now = self._now or datetime.now(timezone.utc)
        bundle = QuestradeTokenBundle(
            access_token=access,
            refresh_token=refresh,
            api_server=validated.base_url,
            acquired_at=now,
            expires_at=now + timedelta(seconds=expires_in),
            generation=1,
        )
        try:
            self._store.replace(bundle)
        except Exception:
            return _failure("QUESTRADE_TOKEN_REPLACE_FAILED", attempted=True)
        self._memory_bundle = bundle
        return {
            "success": True,
            "status": "AUTHENTICATED",
            "reason": "ok",
            "oauth_refresh_attempted": True,
            "oauth_refresh_succeeded": True,
            "refresh_token_persisted": True,
            "access_token_persisted": False,
            "access_token_memory_only": True,
            "network_call_performed": True,
            "token_values_returned": False,
            "metadata": bundle.metadata(now=now),
            "execution_allowed": False,
            "live_trading_blocked": True,
            "broker_execution_armed": False,
            "advisory_only": True,
        }

    @property
    def memory_bundle(self) -> QuestradeTokenBundle | None:
        return self._memory_bundle

    def __repr__(self) -> str:
        return "QuestradeBoundedOAuthRefresh(secret_material_redacted=True, advisory_only=True)"


class QuestradeOAuthFormTransportImpl:
    """Production POST-only token transport. Redirects rejected. Injectable via tests."""

    def post_form(
        self,
        *,
        url: str,
        data: Mapping[str, str],
        headers: Mapping[str, str],
        timeout_seconds: float,
        allow_redirects: bool,
    ) -> QuestradeOAuthHttpResponse:
        if allow_redirects:
            raise QuestradeAdvisoryError("QUESTRADE_OAUTH_REDIRECT_REJECTED", code="QUESTRADE_OAUTH_REDIRECT_REJECTED")
        _assert_token_url(url)
        body = urlencode(
            {
                "grant_type": "refresh_token",
                "refresh_token": str(data.get("refresh_token") or ""),
            }
        ).encode("utf-8")
        request = urllib.request.Request(
            QUESTRADE_TOKEN_URL,
            data=body,
            headers={
                "Accept": "application/json",
                "Content-Type": "application/x-www-form-urlencoded",
                "User-Agent": "CapitalStrataSystems-Questrade-ReadOnly/1.0",
            },
            method="POST",
        )
        opener = urllib.request.build_opener(_RejectRedirectHandler)
        try:
            with opener.open(request, timeout=max(0.1, min(float(timeout_seconds), _MAX_TIMEOUT_SECONDS))) as response:
                raw = response.read(_MAX_BODY_BYTES + 1)
                status = int(getattr(response, "status", 200))
        except urllib.error.HTTPError as exc:
            status = int(exc.code)
            if status in {301, 302, 303, 307, 308}:
                raise QuestradeAdvisoryError(
                    "QUESTRADE_OAUTH_REDIRECT_REJECTED",
                    code="QUESTRADE_OAUTH_REDIRECT_REJECTED",
                ) from None
            raw = exc.read(_MAX_BODY_BYTES + 1)
            if len(raw) > _MAX_BODY_BYTES:
                raise QuestradeAdvisoryError(
                    "QUESTRADE_OAUTH_BODY_TOO_LARGE",
                    code="QUESTRADE_OAUTH_BODY_TOO_LARGE",
                ) from None
            try:
                parsed = json.loads(raw.decode("utf-8")) if raw else {}
            except (UnicodeDecodeError, json.JSONDecodeError):
                parsed = {}
            if not isinstance(parsed, dict):
                parsed = {}
            return QuestradeOAuthHttpResponse(status_code=status, payload=parsed)
        except QuestradeAdvisoryError:
            raise
        except Exception:
            raise QuestradeAdvisoryError(
                "QUESTRADE_OAUTH_TRANSPORT_FAILED",
                code="QUESTRADE_OAUTH_TRANSPORT_FAILED",
            ) from None
        if len(raw) > _MAX_BODY_BYTES:
            raise QuestradeAdvisoryError("QUESTRADE_OAUTH_BODY_TOO_LARGE", code="QUESTRADE_OAUTH_BODY_TOO_LARGE")
        try:
            parsed = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise QuestradeAdvisoryError(
                "QUESTRADE_OAUTH_RESPONSE_INVALID",
                code="QUESTRADE_OAUTH_RESPONSE_INVALID",
            ) from None
        if not isinstance(parsed, dict):
            raise QuestradeAdvisoryError(
                "QUESTRADE_OAUTH_RESPONSE_INVALID",
                code="QUESTRADE_OAUTH_RESPONSE_INVALID",
            )
        return QuestradeOAuthHttpResponse(status_code=status, payload=parsed)


class _RejectRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # type: ignore[override]
        raise QuestradeAdvisoryError("QUESTRADE_OAUTH_REDIRECT_REJECTED", code="QUESTRADE_OAUTH_REDIRECT_REJECTED")


def _assert_token_url(url: str) -> None:
    parsed = urlsplit(str(url or ""))
    if parsed.scheme.lower() != "https":
        raise QuestradeAdvisoryError("QUESTRADE_OAUTH_URL_REJECTED", code="QUESTRADE_OAUTH_URL_REJECTED")
    if (parsed.hostname or "").lower() != _TOKEN_HOST:
        raise QuestradeAdvisoryError("QUESTRADE_OAUTH_URL_REJECTED", code="QUESTRADE_OAUTH_URL_REJECTED")
    if parsed.path.rstrip("/") != _TOKEN_PATH:
        raise QuestradeAdvisoryError("QUESTRADE_OAUTH_URL_REJECTED", code="QUESTRADE_OAUTH_URL_REJECTED")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise QuestradeAdvisoryError("QUESTRADE_OAUTH_URL_REJECTED", code="QUESTRADE_OAUTH_URL_REJECTED")


def _load_refresh_token(store: Any) -> str:
    loader = getattr(store, "load_refresh_token", None)
    value = loader() if callable(loader) else store.load()
    if isinstance(value, QuestradeTokenBundle):
        return str(value.refresh_token or "")
    return str(value or "")


def _failure(code: str, *, attempted: bool) -> dict[str, Any]:
    return {
        "success": False,
        "status": "UNAVAILABLE",
        "reason": code,
        "oauth_refresh_attempted": attempted,
        "oauth_refresh_succeeded": False,
        "refresh_token_persisted": False,
        "access_token_persisted": False,
        "access_token_memory_only": False,
        "network_call_performed": attempted,
        "token_values_returned": False,
        "execution_allowed": False,
        "live_trading_blocked": True,
        "broker_execution_armed": False,
        "advisory_only": True,
    }


def public_oauth_result(result: Mapping[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in result.items() if key != "_bundle"}


__all__ = [
    "QUESTRADE_TOKEN_URL",
    "QuestradeBoundedOAuthRefresh",
    "QuestradeOAuthFormTransport",
    "QuestradeOAuthFormTransportImpl",
    "QuestradeOAuthHttpResponse",
    "public_oauth_result",
]
