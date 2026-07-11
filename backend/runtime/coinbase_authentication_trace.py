from __future__ import annotations

import json
import os
import socket
import ssl
import time
from collections.abc import Callable, Mapping
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec


PASS = "PASS"
FAIL = "FAIL"
WARN = "WARN"
UNKNOWN = "UNKNOWN"
PAYLOAD_VERSION = "css.phase165a.coinbase_authentication_trace.v1"

ClockFn = Callable[[], float]

KEY_FIELDS = ("COINBASE_CDP_KEY_NAME", "COINBASE_KEY_NAME", "COINBASE_API_KEY", "key_name", "name")
PRIVATE_KEY_FIELDS = (
    "COINBASE_CDP_PRIVATE_KEY",
    "COINBASE_PRIVATE_KEY",
    "COINBASE_API_SECRET",
    "private_key",
    "privateKey",
)
PRIVATE_KEY_PATH_FIELDS = (
    "COINBASE_CDP_PRIVATE_KEY_PATH",
    "COINBASE_PRIVATE_KEY_PATH",
    "COINBASE_KEY_JSON_PATH",
    "COINBASE_KEY_JSON",
    "COINBASE_KEY_FILE",
)


def validate_coinbase_credential_material(
    env: Mapping[str, Any] | None = None,
    *,
    require_credentials: bool = True,
    now: float | None = None,
    clock_skew_tolerance_seconds: int = 300,
) -> dict[str, Any]:
    source = env if isinstance(env, Mapping) else os.environ
    key_name = _first_present(source, KEY_FIELDS)
    private_key_material, key_source = _private_key_material(source)
    key_format_valid = _key_format_valid(key_name)
    parsed = _parse_ec_private_key(private_key_material)
    timestamp = _timestamp_valid(source, now=now, tolerance=clock_skew_tolerance_seconds)
    permissions = _permission_status(source)

    jwt_generated = False
    signature_status = FAIL
    jwt_reason = ""
    if parsed["pem_valid"] and parsed["private_key"] is not None:
        try:
            parsed["private_key"].sign(b"css-phase165-coinbase-read-only-auth-trace", ec.ECDSA(hashes.SHA256()))
            jwt_generated = True
            signature_status = PASS
        except Exception as exc:  # noqa: BLE001 - advisory diagnostics classify signing failures.
            jwt_reason = _failure_reason(exc)

    blockers: list[str] = []
    if require_credentials or key_name or private_key_material:
        if not key_name:
            blockers.append("coinbase_api_key_missing")
        elif not key_format_valid:
            blockers.append("coinbase_api_key_format_invalid")
        if not private_key_material:
            blockers.append("coinbase_private_key_missing")
        elif not parsed["pem_valid"]:
            blockers.append("coinbase_private_key_pem_invalid")
        elif not parsed["ec_private_key"]:
            blockers.append("coinbase_private_key_not_ec")
        if not jwt_generated:
            blockers.append("coinbase_jwt_generation_failed")
        if signature_status != PASS:
            blockers.append("coinbase_signature_generation_failed")
    if not timestamp["valid"]:
        blockers.append("coinbase_timestamp_outside_clock_skew_tolerance")
    if permissions["status"] == FAIL:
        blockers.append("coinbase_read_permission_missing")

    status = PASS if not blockers else FAIL
    if not require_credentials and not key_name and not private_key_material:
        status = UNKNOWN

    return {
        "payload_version": "css.phase165b.coinbase_credential_validation.v1",
        "status": status,
        "api_key_present": bool(key_name),
        "api_key_format_valid": bool(key_format_valid) if key_name else False,
        "private_key_present": bool(private_key_material),
        "private_key_source": key_source,
        "pem_valid": bool(parsed["pem_valid"]),
        "ec_private_key": bool(parsed["ec_private_key"]),
        "jwt_generated": jwt_generated,
        "signature_status": signature_status,
        "jwt_generation_status": PASS if jwt_generated else FAIL,
        "jwt_failure_reason": jwt_reason,
        "timestamp_valid": bool(timestamp["valid"]),
        "clock_skew_seconds": timestamp["clock_skew_seconds"],
        "clock_skew_tolerance_seconds": int(clock_skew_tolerance_seconds),
        "permissions": permissions,
        "blockers": blockers,
        "secrets_redacted": True,
        **_advisory_flags(),
    }


def trace_coinbase_authentication(
    adapter: Any,
    *,
    env: Mapping[str, Any] | None = None,
    mode: str = "live",
    require_credentials: bool = False,
    clock: ClockFn = time.perf_counter,
) -> dict[str, Any]:
    started = clock()
    source = env if isinstance(env, Mapping) else os.environ
    credentials = validate_coinbase_credential_material(source, require_credentials=require_credentials)
    endpoint_alignment = _endpoint_alignment(source, mode=mode)
    endpoints = (
        _not_attempted_endpoints("credential_validation_failed")
        if require_credentials and credentials["status"] == FAIL
        else verify_coinbase_read_only_endpoints(adapter, clock=clock)
    )
    auth_endpoint = endpoints["authentication"]
    account_ok = endpoints["accounts"]["status"] == PASS or endpoints["balances"]["status"] == PASS
    authentication_ok = auth_endpoint["status"] == PASS or account_ok
    blockers = list(credentials.get("blockers", []))
    if endpoint_alignment["status"] == FAIL:
        blockers.append("coinbase_endpoint_mode_mismatch")
    if credentials["status"] == FAIL:
        authentication_ok = False
    if not authentication_ok:
        blockers.append(_first_failure_stage(endpoints))

    status = PASS if authentication_ok and endpoint_alignment["status"] != FAIL and credentials["status"] != FAIL else FAIL
    return {
        "payload_version": PAYLOAD_VERSION,
        "broker": "COINBASE",
        "mode": mode,
        "status": status,
        "authentication": status,
        "credential_validation": credentials,
        "endpoint_alignment": endpoint_alignment,
        "endpoint_verification": endpoints,
        "http_status": _first_http_status(endpoints),
        "endpoint": auth_endpoint.get("endpoint"),
        "jwt_generated": bool(credentials.get("jwt_generated")),
        "signature_status": credentials.get("signature_status"),
        "tls_connectivity_state": endpoint_alignment.get("tls_connectivity_state", UNKNOWN),
        "authentication_latency_ms": _elapsed_ms(clock, started),
        "coinbase_error_code": _first_error_code(endpoints),
        "coinbase_error_message": _first_error_message(endpoints),
        "failure_stage": "" if status == PASS else _first_failure_stage(endpoints, blockers),
        "blockers": sorted({str(item) for item in blockers if str(item)}),
        "secrets_redacted": True,
        **_advisory_flags(),
    }


def verify_coinbase_read_only_endpoints(adapter: Any, *, clock: ClockFn = time.perf_counter) -> dict[str, Any]:
    return {
        "authentication": _call_stage(
            adapter,
            "authentication",
            (("authenticate", ()), ("verify_authentication", ()), ("get_server_time", ()), ("get_accounts", ())),
            clock=clock,
        ),
        "accounts": _call_stage(adapter, "accounts", (("get_accounts", ()), ("get_account", ())), clock=clock),
        "balances": _call_stage(adapter, "balances", (("get_balances", ()), ("get_balance", ()), ("get_account_balance", ())), clock=clock),
        "portfolios": _call_stage(adapter, "portfolios", (("get_portfolios", ()), ("get_portfolio", ())), clock=clock),
        "products": _call_stage(adapter, "products", (("get_products", ()), ("list_products", ())), clock=clock),
        "market_data": _call_stage(
            adapter,
            "market_data",
            (("get_ticker", ("BTC-USD",)), ("get_product", ("BTC-USD",)), ("get_product_ticker", ("BTC-USD",))),
            clock=clock,
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
            "coinbase_error_code": "NOT_ATTEMPTED",
            "coinbase_error_message": reason,
            "attempted_methods": [],
            "read_only": True,
            **_advisory_flags(),
        }
        for stage in ("authentication", "accounts", "balances", "portfolios", "products", "market_data")
    }


def _call_stage(
    adapter: Any,
    stage: str,
    methods: tuple[tuple[str, tuple[Any, ...]], ...],
    *,
    clock: ClockFn,
) -> dict[str, Any]:
    started = clock()
    attempted: list[str] = []
    for method_name, args in methods:
        method = getattr(adapter, method_name, None)
        if not callable(method):
            continue
        attempted.append(method_name)
        try:
            payload = method(*args)
        except TypeError:
            try:
                payload = method()
            except Exception as exc:  # noqa: BLE001
                return _stage_failure(stage, method_name, exc, started, clock, attempted)
        except Exception as exc:  # noqa: BLE001
            return _stage_failure(stage, method_name, exc, started, clock, attempted)
        ok, reason = _read_success(payload)
        status = PASS if ok else FAIL
        return {
            "stage": stage,
            "status": status,
            "endpoint": method_name,
            "http_status": _http_status(payload),
            "latency_ms": _elapsed_ms(clock, started),
            "coinbase_error_code": "" if ok else _error_code(payload, reason),
            "coinbase_error_message": "" if ok else _error_message(payload, reason),
            "payload_type": type(payload).__name__,
            "item_count": _item_count(payload),
            "attempted_methods": attempted,
            "read_only": True,
            **_advisory_flags(),
        }
    return {
        "stage": stage,
        "status": FAIL,
        "endpoint": "",
        "http_status": None,
        "latency_ms": _elapsed_ms(clock, started),
        "coinbase_error_code": "READ_ONLY_METHOD_UNAVAILABLE",
        "coinbase_error_message": "No compatible read-only adapter method was available.",
        "attempted_methods": attempted,
        "read_only": True,
        **_advisory_flags(),
    }


def _stage_failure(stage: str, method_name: str, exc: BaseException, started: float, clock: ClockFn, attempted: list[str]) -> dict[str, Any]:
    return {
        "stage": stage,
        "status": FAIL,
        "endpoint": method_name,
        "http_status": _exception_http_status(exc),
        "latency_ms": _elapsed_ms(clock, started),
        "coinbase_error_code": _failure_reason(exc),
        "coinbase_error_message": str(exc),
        "exception_type": exc.__class__.__name__,
        "attempted_methods": attempted,
        "read_only": True,
        **_advisory_flags(),
    }


def _read_success(payload: Any) -> tuple[bool, str]:
    if payload is None:
        return False, "empty_coinbase_response"
    if isinstance(payload, bool):
        return payload, "" if payload else "coinbase_returned_false"
    if isinstance(payload, Mapping):
        if payload.get("authenticated") is False or payload.get("ok") is False:
            return False, str(payload.get("reason") or payload.get("error") or "coinbase_read_failed")
        status = payload.get("status")
        if isinstance(status, int) and not (200 <= status < 300):
            return False, f"coinbase_http_{status}"
        status_text = str(status or "").upper()
        if status_text in {"FAIL", "FAILED", "ERROR", "BLOCKED"}:
            return False, str(payload.get("reason") or payload.get("error") or status_text)
        if payload.get("error") or payload.get("message") and status_text in {"ERROR", "FAIL"}:
            return False, str(payload.get("error") or payload.get("message"))
    if isinstance(payload, (list, tuple, set)):
        return bool(payload), "" if payload else "empty_coinbase_collection"
    return True, ""


def _endpoint_alignment(env: Mapping[str, Any], *, mode: str) -> dict[str, Any]:
    configured = str(
        _first_present(env, ("COINBASE_BASE_URL", "COINBASE_API_URL", "COINBASE_REST_URL"))
        or "https://api.coinbase.com"
    )
    parsed = urlparse(configured)
    host = parsed.hostname or ""
    lowered = configured.lower()
    mode_key = str(mode or "live").lower()
    mismatch = (mode_key == "live" and "sandbox" in lowered) or (mode_key in {"paper", "sandbox"} and "sandbox" not in lowered and "api.coinbase.com" in lowered)
    return {
        "status": FAIL if mismatch else PASS,
        "configured_endpoint": configured,
        "host": host,
        "mode": mode_key,
        "sandbox_live_mismatch": mismatch,
        "tls_connectivity_state": _tls_state(host),
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


def _private_key_material(env: Mapping[str, Any]) -> tuple[str, str]:
    raw = _first_present(env, PRIVATE_KEY_FIELDS)
    if raw:
        text = str(raw).strip()
        path = Path(text).expanduser()
        if path.exists() and path.is_file():
            loaded, source = _load_key_file(path)
            return loaded, source
        if text.startswith("{"):
            loaded = _key_from_json_text(text)
            return loaded, "json_value" if loaded else "inline"
        return text.replace("\\n", "\n"), "inline"
    for field in PRIVATE_KEY_PATH_FIELDS:
        value = env.get(field)
        if not value:
            continue
        path = Path(str(value).strip().strip('"')).expanduser()
        if path.exists() and path.is_file():
            return _load_key_file(path)
    return "", ""


def _load_key_file(path: Path) -> tuple[str, str]:
    try:
        content = path.read_text(encoding="utf-8").strip()
    except OSError:
        return "", str(path)
    if content.startswith("{") or path.suffix.lower() == ".json":
        return _key_from_json_text(content), str(path)
    return content.replace("\\n", "\n"), str(path)


def _key_from_json_text(text: str) -> str:
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return ""
    if not isinstance(payload, Mapping):
        return ""
    return str(payload.get("privateKey") or payload.get("private_key") or payload.get("apiSecret") or "").replace("\\n", "\n").strip()


def _parse_ec_private_key(material: str) -> dict[str, Any]:
    if not material:
        return {"pem_valid": False, "ec_private_key": False, "private_key": None}
    try:
        private_key = serialization.load_pem_private_key(material.encode("utf-8"), password=None)
    except Exception:
        return {"pem_valid": False, "ec_private_key": False, "private_key": None}
    return {
        "pem_valid": True,
        "ec_private_key": isinstance(private_key, ec.EllipticCurvePrivateKey),
        "private_key": private_key,
    }


def _permission_status(env: Mapping[str, Any]) -> dict[str, Any]:
    raw = str(_first_present(env, ("COINBASE_API_PERMISSIONS", "COINBASE_SCOPES", "COINBASE_CDP_PERMISSIONS")) or "").lower()
    if not raw:
        return {"status": UNKNOWN, "read_permission_present": None, "declared": False}
    read_ok = any(token in raw for token in ("view", "read", "wallet:accounts:read", "trade:read"))
    return {"status": PASS if read_ok else FAIL, "read_permission_present": read_ok, "declared": True}


def _timestamp_valid(env: Mapping[str, Any], *, now: float | None, tolerance: int) -> dict[str, Any]:
    reference = float(now if now is not None else time.time())
    raw = _first_present(env, ("COINBASE_AUTH_TIMESTAMP", "COINBASE_JWT_TIMESTAMP"))
    if not raw:
        return {"valid": True, "clock_skew_seconds": 0.0}
    try:
        timestamp = float(raw)
    except (TypeError, ValueError):
        try:
            timestamp = datetime.fromisoformat(str(raw).replace("Z", "+00:00")).timestamp()
        except Exception:
            return {"valid": False, "clock_skew_seconds": None}
    skew = round(abs(reference - timestamp), 3)
    return {"valid": skew <= tolerance, "clock_skew_seconds": skew}


def _key_format_valid(value: Any) -> bool:
    text = str(value or "").strip()
    if not text or "BEGIN " in text:
        return False
    return len(text) >= 8 and not any(char.isspace() for char in text)


def _http_status(payload: Any) -> int | None:
    if isinstance(payload, Mapping) and isinstance(payload.get("status"), int):
        return int(payload["status"])
    return None


def _item_count(payload: Any) -> int:
    if isinstance(payload, Mapping):
        for key in ("products", "accounts", "portfolios", "data"):
            value = payload.get(key)
            if isinstance(value, list):
                return len(value)
        return 1 if payload else 0
    if isinstance(payload, (list, tuple, set)):
        return len(payload)
    return 1 if payload is not None else 0


def _exception_http_status(exc: BaseException) -> int | None:
    response = getattr(exc, "response", None)
    status = getattr(response, "status_code", None) or getattr(exc, "status_code", None) or getattr(exc, "status", None)
    try:
        return int(status) if status is not None else None
    except (TypeError, ValueError):
        return None


def _error_code(payload: Any, fallback: str) -> str:
    if isinstance(payload, Mapping):
        return str(payload.get("error_code") or payload.get("code") or payload.get("error") or fallback).upper()
    return str(fallback).upper()


def _error_message(payload: Any, fallback: str) -> str:
    if isinstance(payload, Mapping):
        return str(payload.get("error_message") or payload.get("message") or payload.get("reason") or fallback)
    return str(fallback)


def _failure_reason(exc: BaseException) -> str:
    status = _exception_http_status(exc)
    if status:
        return f"COINBASE_HTTP_{status}"
    text = f"{exc.__class__.__name__} {exc}".lower()
    if "tls" in text or "ssl" in text or "certificate" in text:
        return "COINBASE_TLS_ERROR"
    if "timeout" in text:
        return "COINBASE_TIMEOUT"
    if "unauthorized" in text or "401" in text:
        return "COINBASE_HTTP_401"
    if "forbidden" in text or "403" in text:
        return "COINBASE_HTTP_403"
    if "unavailable" in text or "503" in text:
        return "COINBASE_HTTP_503"
    if "network" in text or "connection" in text:
        return "COINBASE_NETWORK_ERROR"
    return f"COINBASE_{exc.__class__.__name__.upper()}"


def _first_failure_stage(endpoints: Mapping[str, Any], blockers: list[str] | None = None) -> str:
    for name, payload in endpoints.items():
        if isinstance(payload, Mapping) and payload.get("status") == FAIL:
            return str(name)
    return str((blockers or ["coinbase_authentication_failed"])[0])


def _first_http_status(endpoints: Mapping[str, Any]) -> int | None:
    for payload in endpoints.values():
        if isinstance(payload, Mapping) and payload.get("http_status") is not None:
            return payload.get("http_status")
    return None


def _first_error_code(endpoints: Mapping[str, Any]) -> str:
    for payload in endpoints.values():
        if isinstance(payload, Mapping) and payload.get("coinbase_error_code"):
            return str(payload.get("coinbase_error_code"))
    return ""


def _first_error_message(endpoints: Mapping[str, Any]) -> str:
    for payload in endpoints.values():
        if isinstance(payload, Mapping) and payload.get("coinbase_error_message"):
            return str(payload.get("coinbase_error_message"))
    return ""


def _first_present(source: Mapping[str, Any], keys: tuple[str, ...]) -> Any:
    for key in keys:
        value = source.get(key)
        if value not in (None, ""):
            return value
    return None


def _elapsed_ms(clock: ClockFn, started: float) -> int:
    return max(0, int(round((clock() - started) * 1000)))


def _advisory_flags() -> dict[str, Any]:
    return {
        "execution_allowed": False,
        "live_trading_blocked": True,
        "broker_execution_armed": False,
        "advisory_only": True,
    }


__all__ = [
    "trace_coinbase_authentication",
    "validate_coinbase_credential_material",
    "verify_coinbase_read_only_endpoints",
]
