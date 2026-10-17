"""Bounded Questrade OAuth refresh. One POST. Access token stays memory-only."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Mapping, Protocol
from urllib.parse import urlencode, urlsplit
import json
import time
import urllib.error
import urllib.request

from backend.brokers.questrade.endpoint_security import validate_api_server
from backend.brokers.questrade.errors import (
    QuestradeAdvisoryError,
    TokenStoreError,
    WriteMethodBlockedError,
)
from backend.brokers.questrade.refresh_coordination import (
    DEFAULT_LOCK_TIMEOUT_SECONDS,
    RefreshLockTimeout,
    coordination_key,
    process_lock_for,
    thread_lock_for,
)
from backend.brokers.questrade.token_lifecycle import QuestradeTokenBundle


QUESTRADE_TOKEN_URL = "https://login.questrade.com/oauth2/token"
_TOKEN_HOST = "login.questrade.com"
_TOKEN_PATH = "/oauth2/token"
_DEFAULT_TIMEOUT_SECONDS = 10.0
_MAX_TIMEOUT_SECONDS = 15.0
_MAX_BODY_BYTES = 16_384

# In-process rotation state keyed by store coordination key. Values hold secret material in
# memory only (QuestradeTokenBundle fields are repr=False); nothing here is logged.
_FRESH: dict[str, QuestradeTokenBundle] = {}
_PENDING: dict[str, QuestradeTokenBundle] = {}


def _reset_rotation_state_for_tests() -> None:
    _FRESH.clear()
    _PENDING.clear()


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
    """At most one refresh POST per rotation, coordinated across threads and processes.

    H2 hardening: Questrade refresh tokens are single-use and ``api_server`` may change on
    every refresh. Refresh is therefore single-flight (thread lock + inter-process file lock),
    the store is re-read under the lock, an in-process caller reuses a bundle another caller
    just obtained, and a rotated token whose persistence failed is held in memory (never
    discarded, never used for API calls) while persistence is retried. The spent token is
    never POSTed again by this process.
    """

    def __init__(
        self,
        store: Any,
        *,
        transport: QuestradeOAuthFormTransport | None = None,
        now: datetime | None = None,
        timeout_seconds: float = _DEFAULT_TIMEOUT_SECONDS,
        lock_timeout_seconds: float = DEFAULT_LOCK_TIMEOUT_SECONDS,
        persist_attempts: int = 3,
        persist_backoff_seconds: float = 0.2,
        reuse_margin_seconds: float = 60.0,
        sleeper: Callable[[float], None] = time.sleep,
    ) -> None:
        self._store = store
        self._transport = transport or QuestradeOAuthFormTransportImpl()
        self._now = now
        self._timeout_seconds = max(0.1, min(float(timeout_seconds), _MAX_TIMEOUT_SECONDS))
        self._lock_timeout = max(0.0, float(lock_timeout_seconds))
        self._persist_attempts = max(1, min(int(persist_attempts), 10))
        self._persist_backoff = max(0.0, min(float(persist_backoff_seconds), 5.0))
        self._reuse_margin = max(0.0, float(reuse_margin_seconds))
        self._sleeper = sleeper
        self._key = coordination_key(store)
        self._memory_bundle: QuestradeTokenBundle | None = None

    def refresh(self) -> dict[str, Any]:
        try:
            observed = _load_refresh_token(self._store)  # unlocked peek: detects peer rotation
        except Exception:
            observed = None
        thread_lock = thread_lock_for(self._key)
        # 0 means "do not wait" for both locks (the file lock already fails at once with 0).
        acquired = (thread_lock.acquire(timeout=self._lock_timeout) if self._lock_timeout > 0
                    else thread_lock.acquire(blocking=False))
        if not acquired:
            return _failure("QUESTRADE_REFRESH_LOCK_TIMEOUT", attempted=False)
        try:
            try:
                with process_lock_for(self._store, timeout_seconds=self._lock_timeout):
                    return self._refresh_locked(observed)
            except RefreshLockTimeout:
                return _failure("QUESTRADE_REFRESH_LOCK_TIMEOUT", attempted=False)
            except OSError:
                return _failure("QUESTRADE_REFRESH_LOCK_UNAVAILABLE", attempted=False)
        finally:
            thread_lock.release()

    def _refresh_locked(self, observed: str | None) -> dict[str, Any]:
        now = self._now or datetime.now(timezone.utc)
        pending = _PENDING.get(self._key)
        if pending is not None:
            # A rotated token is not yet durable: finish persisting it, never POST again.
            return self._persist_and_publish(pending, now=now, network_call=False)
        try:
            refresh_token = _load_refresh_token(self._store)
        except TokenStoreError as exc:
            return _failure(exc.code, attempted=False)
        except Exception:
            return _failure("QUESTRADE_TOKEN_STORE_UNAVAILABLE", attempted=False)
        if not refresh_token:
            return _failure("QUESTRADE_REFRESH_TOKEN_MISSING", attempted=False)
        fresh = _FRESH.get(self._key)
        if (
            fresh is not None
            and fresh.refresh_token == refresh_token
            and now < fresh.expires_at - timedelta(seconds=self._reuse_margin)
        ):
            self._memory_bundle = fresh
            return _success(fresh, now=now, network_call=False, reused=True)
        if observed is not None and observed != refresh_token:
            # Another process rotated the token while we waited; its access token lives only in
            # that process. Do not chain a second rotation implicitly; the caller may retry.
            failure = _failure("QUESTRADE_REFRESH_ROTATED_BY_PEER", attempted=False)
            failure["retryable"] = True
            return failure
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
        return self._complete(response, now=now, previous=fresh)

    def _complete(self, response: QuestradeOAuthHttpResponse, *, now: datetime,
                  previous: QuestradeTokenBundle | None) -> dict[str, Any]:
        if int(response.status_code) in {301, 302, 303, 307, 308}:
            return _failure("QUESTRADE_OAUTH_REDIRECT_REJECTED", attempted=True)
        if int(response.status_code) in {401, 403}:
            _FRESH.pop(self._key, None)
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
            # The old refresh token is already spent. Keep the rotated one durable (it is a valid
            # credential) but hand nothing to API clients: the returned server is untrusted.
            _FRESH.pop(self._key, None)
            failure = _failure(code, attempted=True)
            failure["rotated_refresh_token_persisted"] = self._save_refresh_only(refresh)
            return failure
        bundle = QuestradeTokenBundle(
            access_token=access,
            refresh_token=refresh,
            api_server=validated.base_url,  # always the server returned by THIS refresh
            acquired_at=now,
            expires_at=now + timedelta(seconds=expires_in),
            generation=(previous.generation + 1) if previous is not None else 1,
        )
        _FRESH.pop(self._key, None)  # the previous bundle's refresh token is now spent
        _PENDING[self._key] = bundle  # held until durable; never discarded
        return self._persist_and_publish(bundle, now=now, network_call=True)

    def _persist_and_publish(self, bundle: QuestradeTokenBundle, *, now: datetime,
                             network_call: bool) -> dict[str, Any]:
        for attempt in range(self._persist_attempts):
            try:
                self._store.replace(bundle)
            except Exception:
                if attempt + 1 < self._persist_attempts:
                    self._sleeper(self._persist_backoff * (2**attempt))
                continue
            _PENDING.pop(self._key, None)
            _FRESH[self._key] = bundle
            if now >= bundle.expires_at:
                return _failure("QUESTRADE_ACCESS_TOKEN_EXPIRED_REFRESH_REQUIRED", attempted=network_call)
            self._memory_bundle = bundle
            return _success(bundle, now=now, network_call=network_call, reused=False)
        self._memory_bundle = None  # fail closed: the unsaved token is not handed to any client
        return _degraded(bundle, now=now, network_call=network_call)

    def _save_refresh_only(self, refresh: str) -> bool:
        saver = getattr(self._store, "save_refresh_token", None)
        if not callable(saver):
            return False
        for attempt in range(self._persist_attempts):
            try:
                saver(refresh)
                return True
            except Exception:
                if attempt + 1 < self._persist_attempts:
                    self._sleeper(self._persist_backoff * (2**attempt))
        return False

    def pending_persistence(self) -> bool:
        return self._key in _PENDING

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


def _success(bundle: QuestradeTokenBundle, *, now: datetime, network_call: bool, reused: bool) -> dict[str, Any]:
    return {
        "success": True,
        "status": "AUTHENTICATED",
        "reason": "reused_in_process_rotation" if reused else "ok",
        "oauth_refresh_attempted": network_call,
        "oauth_refresh_succeeded": True,
        "refresh_token_persisted": True,
        "access_token_persisted": False,
        "access_token_memory_only": True,
        "network_call_performed": network_call,
        "reused_in_process_rotation": reused,
        "token_values_returned": False,
        "metadata": bundle.metadata(now=now),
        "execution_allowed": False,
        "live_trading_blocked": True,
        "broker_execution_armed": False,
        "advisory_only": True,
    }


def _degraded(bundle: QuestradeTokenBundle, *, now: datetime, network_call: bool) -> dict[str, Any]:
    result = _failure("QUESTRADE_TOKEN_PERSIST_FAILED_OPERATOR_ACTION_REQUIRED", attempted=network_call)
    result.update({
        "status": "DEGRADED",
        "oauth_refresh_succeeded": network_call or result["oauth_refresh_succeeded"],
        "rotated_refresh_token_held_in_memory": True,
        "operator_action_required": True,
        "recommended_action": (
            "Restore write access to the token store and call refresh() again in this process "
            "(it persists the held token without a network call). If this process exits first, "
            "Questrade re-authorization is required."
        ),
        "retryable": True,
    })
    return result


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
