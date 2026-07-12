from __future__ import annotations

import os
import socket
import ssl
import time
from collections.abc import Callable, Mapping
from typing import Any
from urllib.parse import urlparse

from backend.app.brokers.credential_loader import load_credentials


PASS = "PASS"
FAIL = "FAIL"
UNKNOWN = "UNKNOWN"
PAYLOAD_VERSION = "css.phase165b.oanda_authentication_trace.v1"

ClockFn = Callable[[], float]

TOKEN_FIELDS = ("OANDA_API_KEY", "OANDA_ACCESS_TOKEN", "OANDA_TOKEN")
ACCOUNT_FIELDS = ("OANDA_ACCOUNT_ID", "OANDA_LIVE_ACCOUNT_ID", "OANDA_PRACTICE_ACCOUNT_ID")
BASE_URL_FIELDS = ("OANDA_BASE_URL", "base_url")
ENV_FIELDS = ("OANDA_ENV", "OANDA_MODE", "environment", "mode")

LIVE_BASE_URL = "https://api-fxtrade.oanda.com"
PRACTICE_BASE_URL = "https://api-fxpractice.oanda.com"


def validate_oanda_credential_material(
    env: Mapping[str, Any] | None = None,
    *,
    mode: str = "live",
    require_credentials: bool = True,
) -> dict[str, Any]:
    source = _credential_source(env, mode=mode)
    token = _first_present(source, TOKEN_FIELDS)
    account_id, account_source = _first_present_with_key(source, ACCOUNT_FIELDS)
    configured_env = _configured_env(source, mode=mode)
    base_url = _base_url(source, configured_env=configured_env)
    token_valid = _token_format_valid(token)
    account_valid = _account_id_format_valid(account_id)
    endpoint = _endpoint_alignment(source, mode=mode, configured_env=configured_env, base_url=base_url)

    blockers: list[str] = []
    if require_credentials or token or account_id:
        if not token:
            blockers.append("oanda_token_missing")
        elif not token_valid:
            blockers.append("oanda_token_format_invalid")
        if not account_id:
            blockers.append("oanda_account_id_missing")
        elif not account_valid:
            blockers.append("oanda_account_id_format_invalid")
    if endpoint["status"] == FAIL:
        blockers.append("oanda_endpoint_mode_mismatch")

    status = PASS if not blockers else FAIL
    if not require_credentials and not token and not account_id:
        status = UNKNOWN

    return {
        "payload_version": "css.phase165b.oanda_credential_validation.v1",
        "status": status,
        "credential_source": "provided_env" if isinstance(env, Mapping) else "canonical_loader",
        "token_present": bool(token),
        "token_format_valid": bool(token_valid) if token else False,
        "account_id_present": bool(account_id),
        "account_id_format_valid": bool(account_valid) if account_id else False,
        "account_id_source": account_source,
        "configured_environment": configured_env,
        "base_url_selected": bool(base_url),
        "endpoint_alignment": endpoint,
        "token_account_pairing_structurally_valid": bool(token and token_valid and account_id and account_valid),
        "blockers": blockers,
        "secrets_redacted": True,
        **_advisory_flags(),
    }


def trace_oanda_authentication(
    adapter: Any,
    *,
    env: Mapping[str, Any] | None = None,
    mode: str = "live",
    require_credentials: bool = False,
    clock: ClockFn = time.perf_counter,
) -> dict[str, Any]:
    started = clock()
    source = _credential_source(env, mode=mode)
    credentials = validate_oanda_credential_material(source, mode=mode, require_credentials=require_credentials)
    endpoint_alignment = credentials["endpoint_alignment"]
    endpoints = (
        _not_attempted_endpoints("credential_validation_failed")
        if require_credentials and credentials["status"] == FAIL
        else verify_oanda_read_only_endpoints(adapter, env=source, clock=clock)
    )

    account_ok = endpoints["account_summary"]["status"] == PASS or endpoints["account_details"]["status"] == PASS
    authentication_ok = endpoints["authentication"]["status"] == PASS or account_ok
    blockers = list(credentials.get("blockers", []))
    if endpoint_alignment["status"] == FAIL and "oanda_endpoint_mode_mismatch" not in blockers:
        blockers.append("oanda_endpoint_mode_mismatch")
    if credentials["status"] == FAIL:
        authentication_ok = False
    if not authentication_ok:
        blockers.append(_first_failure_stage(endpoints))

    status = PASS if authentication_ok and endpoint_alignment["status"] != FAIL and credentials["status"] != FAIL else FAIL
    return {
        "payload_version": PAYLOAD_VERSION,
        "broker": "OANDA",
        "mode": mode,
        "status": status,
        "authentication": status,
        "credential_validation": credentials,
        "endpoint_alignment": endpoint_alignment,
        "endpoint_verification": endpoints,
        "http_status": _first_http_status(endpoints),
        "endpoint": endpoints["authentication"].get("endpoint"),
        "tls_connectivity_state": endpoint_alignment.get("tls_connectivity_state", UNKNOWN),
        "authentication_latency_ms": _elapsed_ms(clock, started),
        "oanda_error_code": _first_error_code(endpoints),
        "oanda_error_message": _first_error_message(endpoints),
        "failure_stage": "" if status == PASS else _first_failure_stage(endpoints, blockers),
        "blockers": sorted({str(item) for item in blockers if str(item)}),
        "secrets_redacted": True,
        **_advisory_flags(),
    }


def verify_oanda_read_only_endpoints(
    adapter: Any,
    *,
    env: Mapping[str, Any] | None = None,
    clock: ClockFn = time.perf_counter,
) -> dict[str, Any]:
    source = _credential_source(env, mode="live")
    return {
        "authentication": _call_stage(
            adapter,
            "authentication",
            (("authenticate", ()), ("get_account_summary", ())),
            env=source,
            clock=clock,
            field_group="account",
        ),
        "account_summary": _call_stage(
            adapter,
            "account_summary",
            (("get_account_summary", ()),),
            env=source,
            clock=clock,
            field_group="account",
        ),
        "account_details": _call_stage(
            adapter,
            "account_details",
            (("get_account_details", ()), ("get_account_metadata", ()), ("_request_json", ("GET", _account_path(source, "details")))),
            env=source,
            clock=clock,
            field_group="account",
        ),
        "instruments": _call_stage(
            adapter,
            "instruments",
            (("get_instruments", ()), ("list_instruments", ()), ("_request_json", ("GET", _account_path(source, "instruments")))),
            env=source,
            clock=clock,
        ),
        "pricing": _call_stage(
            adapter,
            "pricing",
            (
                ("get_pricing", ("EUR_USD",)),
                ("get_prices", ("EUR_USD",)),
                ("get_quote", ("EUR_USD",)),
                ("_request_json", ("GET", _account_path(source, "pricing"))),
            ),
            env=source,
            clock=clock,
        ),
        "open_trades": _call_stage(
            adapter,
            "open_trades",
            (("get_open_trades", ()), ("list_open_trades", ()), ("get_trades", ()), ("_request_json", ("GET", _account_path(source, "open_trades")))),
            env=source,
            clock=clock,
            allow_empty=True,
        ),
        "positions": _call_stage(
            adapter,
            "positions",
            (("get_positions", ()), ("get_open_positions", ()), ("list_positions", ()), ("_request_json", ("GET", _account_path(source, "positions")))),
            env=source,
            clock=clock,
            allow_empty=True,
        ),
    }


def _not_attempted_endpoints(reason: str) -> dict[str, Any]:
    return {
        stage: {
            "stage": stage,
            "status": FAIL,
            "endpoint": "",
            "http_status": None,
            "latency_ms": 0,
            "oanda_error_code": "NOT_ATTEMPTED",
            "oanda_error_message": reason,
            "attempted_methods": [],
            "read_only": True,
            **_advisory_flags(),
        }
        for stage in ("authentication", "account_summary", "account_details", "instruments", "pricing", "open_trades", "positions")
    }


def _call_stage(
    adapter: Any,
    stage: str,
    methods: tuple[tuple[str, tuple[Any, ...]], ...],
    *,
    env: Mapping[str, Any],
    clock: ClockFn,
    field_group: str = "",
    allow_empty: bool = False,
) -> dict[str, Any]:
    started = clock()
    attempted: list[str] = []
    for method_name, args in methods:
        method = _resolve_method(adapter, method_name)
        if not callable(method):
            continue
        attempted.append(method_name)
        try:
            payload = method(*args)
        except TypeError:
            try:
                payload = method()
            except Exception as exc:  # noqa: BLE001 - advisory diagnostics classify read failures.
                return _stage_failure(stage, method_name, exc, started, clock, attempted)
        except Exception as exc:  # noqa: BLE001
            return _stage_failure(stage, method_name, exc, started, clock, attempted)

        ok, reason = _read_success(payload, allow_empty=allow_empty)
        status = PASS if ok else FAIL
        item_count = _item_count(payload)
        result = {
            "stage": stage,
            "status": status,
            "endpoint": _redacted_endpoint(stage, method_name, env),
            "http_status": _http_status(payload),
            "latency_ms": _elapsed_ms(clock, started),
            "oanda_error_code": "" if ok else _error_code(payload, reason),
            "oanda_error_message": "" if ok else _error_message(payload, reason),
            "payload_type": type(payload).__name__,
            "response_type": type(payload).__name__,
            "item_count": item_count,
            "attempted_methods": attempted,
            "read_only": True,
            **_advisory_flags(),
        }
        if field_group == "account":
            result["field_presence"] = _account_field_presence(payload)
        return result

    return {
        "stage": stage,
        "status": FAIL,
        "endpoint": "",
        "http_status": None,
        "latency_ms": _elapsed_ms(clock, started),
        "oanda_error_code": "READ_ONLY_METHOD_UNAVAILABLE",
        "oanda_error_message": "No compatible read-only adapter method was available.",
        "attempted_methods": attempted,
        "read_only": True,
        **_advisory_flags(),
    }


def _stage_failure(stage: str, method_name: str, exc: BaseException, started: float, clock: ClockFn, attempted: list[str]) -> dict[str, Any]:
    return {
        "stage": stage,
        "status": FAIL,
        "endpoint": _redacted_endpoint(stage, method_name, {}),
        "http_status": _exception_http_status(exc),
        "latency_ms": _elapsed_ms(clock, started),
        "oanda_error_code": _failure_reason(exc),
        "oanda_error_message": _sanitize_message(str(exc)),
        "exception_type": exc.__class__.__name__,
        "sanitized_exception_class": exc.__class__.__name__,
        "attempted_methods": attempted,
        "read_only": True,
        **_advisory_flags(),
    }


def _resolve_method(adapter: Any, method_name: str) -> Any:
    method = getattr(adapter, method_name, None)
    if callable(method):
        return method
    client = getattr(adapter, "read_client", None)
    if client is not None:
        method = getattr(client, method_name, None)
        if callable(method):
            return method
    client_getter = getattr(adapter, "_client", None)
    if callable(client_getter):
        try:
            client = client_getter()
        except Exception:
            client = None
        if client is not None:
            method = getattr(client, method_name, None)
            if callable(method):
                return method
    return None


def _credential_source(env: Mapping[str, Any] | None, *, mode: str) -> dict[str, Any]:
    if isinstance(env, Mapping):
        return dict(env)
    loaded = load_credentials("oanda", mode=mode) or {}
    return dict(loaded) if isinstance(loaded, Mapping) else dict(os.environ)


def _endpoint_alignment(
    env: Mapping[str, Any],
    *,
    mode: str,
    configured_env: str | None = None,
    base_url: str | None = None,
) -> dict[str, Any]:
    configured = str(base_url or _base_url(env, configured_env=configured_env or _configured_env(env, mode=mode)))
    parsed = urlparse(configured)
    host = parsed.hostname or ""
    lowered = configured.lower()
    mode_key = str(mode or configured_env or "live").lower()
    mismatch = (mode_key in {"live", "production", "prod"} and "fxpractice" in lowered) or (
        mode_key in {"paper", "practice", "demo", "sandbox"} and "fxtrade" in lowered and "fxpractice" not in lowered
    )
    return {
        "status": FAIL if mismatch else PASS,
        "configured_endpoint": configured,
        "host": host,
        "mode": mode_key,
        "sandbox_live_mismatch": mismatch,
        "tls_connectivity_state": _tls_state(host),
        "dns_resolution": "PASS" if _host_resolvable(host) else UNKNOWN,
        "tls_connection": "PASS" if _tls_state(host) == "RESOLVABLE" else UNKNOWN,
    }


def _tls_state(host: str) -> str:
    if not host:
        return UNKNOWN
    try:
        ssl.create_default_context()
        socket.getaddrinfo(host, 443)
        return "RESOLVABLE"
    except Exception:
        return UNKNOWN


def _host_resolvable(host: str) -> bool:
    if not host:
        return False
    try:
        socket.getaddrinfo(host, 443)
        return True
    except Exception:
        return False


def _configured_env(source: Mapping[str, Any], *, mode: str) -> str:
    raw = _first_present(source, ENV_FIELDS)
    return str(raw or mode or "live").strip().lower()


def _base_url(source: Mapping[str, Any], *, configured_env: str) -> str:
    configured = _first_present(source, BASE_URL_FIELDS)
    if configured:
        return str(configured).strip().rstrip("/")
    return LIVE_BASE_URL if configured_env in {"live", "production", "prod"} else PRACTICE_BASE_URL


def _account_path(env: Mapping[str, Any], kind: str) -> str:
    account_id = _first_present(env, ACCOUNT_FIELDS)
    if not account_id:
        return ""
    path_map = {
        "details": f"v3/accounts/{account_id}",
        "instruments": f"v3/accounts/{account_id}/instruments",
        "pricing": f"v3/accounts/{account_id}/pricing?instruments=EUR_USD",
        "open_trades": f"v3/accounts/{account_id}/openTrades",
        "positions": f"v3/accounts/{account_id}/openPositions",
    }
    return path_map.get(kind, "")


def _redacted_endpoint(stage: str, method_name: str, env: Mapping[str, Any]) -> str:
    if method_name != "_request_json":
        return method_name
    paths = {
        "account_details": "GET /v3/accounts/{account_id}",
        "instruments": "GET /v3/accounts/{account_id}/instruments",
        "pricing": "GET /v3/accounts/{account_id}/pricing?instruments=EUR_USD",
        "open_trades": "GET /v3/accounts/{account_id}/openTrades",
        "positions": "GET /v3/accounts/{account_id}/openPositions",
    }
    return paths.get(stage, "GET /v3/accounts/{account_id}")


def _read_success(payload: Any, *, allow_empty: bool = False) -> tuple[bool, str]:
    if payload is None:
        return False, "empty_oanda_response"
    if isinstance(payload, bool):
        return payload, "" if payload else "oanda_returned_false"
    if isinstance(payload, Mapping):
        if payload.get("ok") is False:
            return False, str(payload.get("error") or payload.get("reason") or "oanda_read_failed")
        status = payload.get("status")
        if isinstance(status, int) and not (200 <= status < 300):
            return False, f"oanda_http_{status}"
        status_text = str(status or payload.get("statusText") or "").upper()
        if status_text in {"FAIL", "FAILED", "ERROR", "BLOCKED"}:
            return False, str(payload.get("reason") or payload.get("error") or status_text)
        if str(payload.get("error") or "").strip():
            return False, str(payload.get("error"))
        data = payload.get("data") if "data" in payload else payload
        if data in ({}, []) and not allow_empty:
            return False, "empty_oanda_response"
    if isinstance(payload, (list, tuple, set)):
        return bool(payload) or allow_empty, "" if payload or allow_empty else "empty_oanda_collection"
    return True, ""


def _account_field_presence(payload: Any) -> dict[str, bool]:
    account = _account_source(payload)
    return {
        "account_id": _value_present(_first_present(account, ("id", "account_id", "accountID"))),
        "alias": _value_present(_first_present(account, ("alias", "account_alias"))),
        "currency": _value_present(_first_present(account, ("currency", "homeCurrency"))),
        "balance": _value_present(_first_present(account, ("balance",))),
        "nav": _value_present(_first_present(account, ("NAV", "nav"))),
        "margin_available": _value_present(_first_present(account, ("marginAvailable", "margin_available"))),
    }


def _account_source(value: Any) -> Mapping[str, Any]:
    payload = _payload_data(value)
    if isinstance(payload, Mapping) and isinstance(payload.get("account"), Mapping):
        return payload["account"]
    return payload if isinstance(payload, Mapping) else {}


def _payload_data(value: Any) -> Any:
    if isinstance(value, Mapping) and "data" in value:
        return value.get("data")
    return value


def _http_status(payload: Any) -> int | None:
    if isinstance(payload, Mapping) and isinstance(payload.get("status"), int):
        return int(payload["status"])
    return None


def _item_count(payload: Any) -> int:
    source = _payload_data(payload)
    if isinstance(source, Mapping):
        for key in ("instruments", "prices", "positions", "trades", "accounts", "data", "results"):
            value = source.get(key)
            if isinstance(value, list):
                return len(value)
        return 1 if source else 0
    if isinstance(source, (list, tuple, set)):
        return len(source)
    return 1 if source is not None else 0


def _exception_http_status(exc: BaseException) -> int | None:
    response = getattr(exc, "response", None)
    status = getattr(response, "status_code", None) or getattr(exc, "status_code", None) or getattr(exc, "status", None)
    try:
        return int(status) if status is not None else None
    except (TypeError, ValueError):
        return None


def _error_code(payload: Any, fallback: str) -> str:
    if isinstance(payload, Mapping):
        data = payload.get("data") if isinstance(payload.get("data"), Mapping) else payload
        return str(data.get("errorCode") or data.get("error_code") or data.get("code") or payload.get("error") or fallback).upper()
    return str(fallback).upper()


def _error_message(payload: Any, fallback: str) -> str:
    if isinstance(payload, Mapping):
        data = payload.get("data") if isinstance(payload.get("data"), Mapping) else payload
        return _sanitize_message(str(data.get("errorMessage") or data.get("error_message") or payload.get("message") or payload.get("reason") or fallback))
    return _sanitize_message(str(fallback))


def _failure_reason(exc: BaseException) -> str:
    status = _exception_http_status(exc)
    if status:
        return f"OANDA_HTTP_{status}"
    text = f"{exc.__class__.__name__} {exc}".lower()
    if "tls" in text or "ssl" in text or "certificate" in text:
        return "OANDA_TLS_ERROR"
    if "timeout" in text or "timed out" in text:
        return "OANDA_TIMEOUT"
    if "unauthorized" in text or "401" in text:
        return "OANDA_HTTP_401"
    if "forbidden" in text or "403" in text:
        return "OANDA_HTTP_403"
    if "not found" in text or "404" in text:
        return "OANDA_HTTP_404"
    if "rate" in text or "429" in text:
        return "OANDA_HTTP_429"
    if "unavailable" in text or "503" in text:
        return "OANDA_HTTP_503"
    if "network" in text or "connection" in text:
        return "OANDA_NETWORK_ERROR"
    return f"OANDA_{exc.__class__.__name__.upper()}"


def _first_failure_stage(endpoints: Mapping[str, Any], blockers: list[str] | None = None) -> str:
    if blockers:
        return str(blockers[0])
    for name, payload in endpoints.items():
        if isinstance(payload, Mapping) and payload.get("status") == FAIL:
            return str(name)
    return "oanda_authentication_failed"


def _first_http_status(endpoints: Mapping[str, Any]) -> int | None:
    for payload in endpoints.values():
        if isinstance(payload, Mapping) and payload.get("http_status") is not None:
            return payload.get("http_status")
    return None


def _first_error_code(endpoints: Mapping[str, Any]) -> str:
    for payload in endpoints.values():
        if isinstance(payload, Mapping) and payload.get("oanda_error_code"):
            return str(payload.get("oanda_error_code"))
    return ""


def _first_error_message(endpoints: Mapping[str, Any]) -> str:
    for payload in endpoints.values():
        if isinstance(payload, Mapping) and payload.get("oanda_error_message"):
            return str(payload.get("oanda_error_message"))
    return ""


def _first_present(source: Mapping[str, Any], keys: tuple[str, ...]) -> Any:
    for key in keys:
        value = source.get(key)
        if _value_present(value):
            return value
    return None


def _first_present_with_key(source: Mapping[str, Any], keys: tuple[str, ...]) -> tuple[Any, str]:
    for key in keys:
        value = source.get(key)
        if _value_present(value):
            return value, key
    return None, ""


def _token_format_valid(value: Any) -> bool:
    text = str(value or "").strip()
    return bool(text) and "BEGIN " not in text and not any(char.isspace() for char in text)


def _account_id_format_valid(value: Any) -> bool:
    text = str(value or "").strip()
    return bool(text) and len(text) >= 4 and "/" not in text and not any(char.isspace() for char in text)


def _value_present(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return value.strip().upper() not in {"", "NONE", "NULL", "DATA UNAVAILABLE", "NOT_AVAILABLE"}
    if isinstance(value, Mapping):
        return bool(value)
    if isinstance(value, (list, tuple, set)):
        return bool(value)
    return True


def _elapsed_ms(clock: ClockFn, started: float) -> int:
    return max(0, int(round((clock() - started) * 1000)))


def _sanitize_message(value: str) -> str:
    text = str(value or "")
    for marker in ("Bearer ", "Authorization:"):
        if marker in text:
            text = text.split(marker)[0] + marker + "[REDACTED]"
    return text[:240]


def _advisory_flags() -> dict[str, Any]:
    return {
        "execution_allowed": False,
        "live_trading_blocked": True,
        "broker_execution_armed": False,
        "advisory_only": True,
    }


__all__ = [
    "PASS",
    "FAIL",
    "UNKNOWN",
    "trace_oanda_authentication",
    "validate_oanda_credential_material",
    "verify_oanda_read_only_endpoints",
]
