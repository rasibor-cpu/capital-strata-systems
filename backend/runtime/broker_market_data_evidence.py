from __future__ import annotations

import os
import time
from collections.abc import Callable, Mapping
from datetime import datetime, timezone
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


PASS = "PASS"
FAIL = "FAIL"

DISCOVERY_ORDER: tuple[str, ...] = (
    "get_quote",
    "get_ticker",
    "get_market_data",
    "get_product",
    "get_pricing",
    "get_candles",
)

DEFAULT_CANDLE_GRANULARITY = "ONE_MINUTE"

ClockFn = Callable[[], float]
UrlOpenFn = Callable[..., Any]


def collect_market_data_evidence(
    adapter: Any,
    *,
    broker: str,
    instrument: str,
    clock: ClockFn = time.perf_counter,
) -> dict[str, Any]:
    """Collect normalized read-only market-data evidence from a broker adapter."""

    broker_name = _normalize_broker(broker)
    symbol = str(instrument or "").strip()
    started = clock()
    attempts: list[dict[str, str]] = []

    for method_name in DISCOVERY_ORDER:
        method = getattr(adapter, method_name, None)
        if not callable(method):
            continue
        payload, error = _call_market_data_method(method, method_name, symbol)
        latency_ms = _elapsed_ms(clock, started)
        if error:
            attempts.append({"source": method_name, "reason": error})
            continue
        ok, reason = _read_success(payload)
        if ok:
            mismatch = _explicit_instrument_mismatch(payload, symbol)
            if mismatch:
                attempts.append({"source": method_name, "reason": mismatch})
                continue
            return _success_payload(
                broker=broker_name,
                instrument=symbol,
                source=method_name,
                payload=payload,
                latency_ms=latency_ms,
            )
        attempts.append({"source": method_name, "reason": reason})

    if broker_name == "oanda" and callable(getattr(adapter, "_request_json", None)):
        payload, reason = _oanda_pricing_fallback(adapter, symbol)
        latency_ms = _elapsed_ms(clock, started)
        ok, read_reason = _read_success(payload)
        if ok:
            mismatch = _explicit_instrument_mismatch(payload, symbol)
            if mismatch:
                attempts.append({"source": "oanda_request_json_pricing", "reason": mismatch})
                reason = mismatch
                ok = False
        if ok:
            return _success_payload(
                broker=broker_name,
                instrument=symbol,
                source="oanda_request_json_pricing",
                payload=payload,
                latency_ms=latency_ms,
            )
        attempts.append({"source": "oanda_request_json_pricing", "reason": reason or read_reason})

    latency_ms = _elapsed_ms(clock, started)
    reason = _last_reason(attempts) or "read_only_method_unavailable"
    return {
        "success": False,
        "broker": broker_name,
        "instrument": symbol,
        "source": "",
        "timestamp": _iso_timestamp(),
        "latency_ms": latency_ms,
        "reason": reason,
        "attempts": attempts,
        **_advisory_safety_flags(),
    }


def collect_market_data_evidence_for_symbols(
    adapter: Any,
    *,
    broker: str,
    instruments: tuple[str, ...] | list[str],
    clock: ClockFn = time.perf_counter,
) -> dict[str, Any]:
    evidence: list[dict[str, Any]] = []
    quotes: dict[str, dict[str, Any]] = {}
    missing: list[str] = []
    timestamp = ""

    for instrument in instruments:
        item = collect_market_data_evidence(adapter, broker=broker, instrument=instrument, clock=clock)
        evidence.append(item)
        if item.get("success") is True:
            quotes[instrument] = {
                "status": PASS,
                "source": item.get("source", ""),
                "timestamp": item.get("timestamp", ""),
                "latency_ms": item.get("latency_ms"),
            }
            if not timestamp and item.get("timestamp"):
                timestamp = str(item["timestamp"])
        else:
            missing.append(instrument)
            quotes[instrument] = {
                "status": FAIL,
                "reason": item.get("reason", "market_data_missing"),
                "source": item.get("source", ""),
                "latency_ms": item.get("latency_ms"),
            }

    return {
        "valid": not missing,
        "reason": "" if not missing else "market_data_missing",
        "symbols": list(instruments),
        "missing_symbols": missing,
        "quotes": quotes,
        "timestamp": timestamp or _iso_timestamp(),
        "evidence": evidence,
        **_advisory_safety_flags(),
    }


def discover_server_health_endpoints(
    *,
    env: Mapping[str, Any] | None = None,
    timeout_seconds: float = 1.5,
    opener: UrlOpenFn = urlopen,
) -> dict[str, Any]:
    """Advisory health endpoint discovery. Never binds ports or changes config."""

    source = env or os.environ
    endpoints = _configured_health_candidates(source) + _default_health_candidates()
    seen: set[str] = set()
    results: list[dict[str, Any]] = []

    for endpoint in endpoints:
        url = endpoint["url"]
        if url in seen:
            continue
        seen.add(url)
        result = dict(endpoint)
        started = time.perf_counter()
        try:
            request = Request(url, method="GET")
            response = opener(request, timeout=timeout_seconds)
            status = int(getattr(response, "status", getattr(response, "code", 0)) or 0)
            result.update(
                {
                    "reachable": 200 <= status < 500,
                    "status_code": status,
                    "error": "",
                    "response_time_ms": _elapsed_ms(time.perf_counter, started),
                    "health_state": _endpoint_health_state(status, True),
                }
            )
        except HTTPError as exc:
            result.update(
                {
                    "reachable": True,
                    "status_code": exc.code,
                    "error": "",
                    "response_time_ms": _elapsed_ms(time.perf_counter, started),
                    "health_state": _endpoint_health_state(exc.code, True),
                }
            )
        except (TimeoutError, URLError, OSError) as exc:
            result.update(
                {
                    "reachable": False,
                    "status_code": None,
                    "error": exc.__class__.__name__,
                    "response_time_ms": _elapsed_ms(time.perf_counter, started),
                    "health_state": "RED",
                }
            )
        results.append(result)

    selected = next((item for item in results if item.get("reachable") is True), None)
    return {
        "advisory_only": True,
        "any_healthy": selected is not None,
        "selected_endpoint": selected,
        "response_time": selected.get("response_time_ms") if selected else None,
        "response_time_ms": selected.get("response_time_ms") if selected else None,
        "health_state": selected.get("health_state") if selected else "RED",
        "endpoints": results,
        **_advisory_safety_flags(),
    }


def _call_market_data_method(method: Callable[..., Any], method_name: str, instrument: str) -> tuple[Any, str]:
    signatures: tuple[tuple[Any, ...], ...]
    if method_name == "get_candles":
        signatures = (
            (instrument,),
            (instrument, DEFAULT_CANDLE_GRANULARITY, 1),
            (instrument, DEFAULT_CANDLE_GRANULARITY),
            (),
        )
    else:
        signatures = ((instrument,), ())

    last_type_error = ""
    for args in signatures:
        try:
            return method(*args), ""
        except TypeError as exc:
            last_type_error = str(exc)
            continue
    return None, last_type_error or "method_signature_unavailable"


def _oanda_pricing_fallback(adapter: Any, instrument: str) -> tuple[Any, str]:
    account_id = str(getattr(adapter, "account_id", "") or "").strip()
    if not account_id:
        return None, "account_id_missing"
    try:
        return adapter._request_json("GET", f"v3/accounts/{account_id}/pricing?instruments={instrument}"), ""
    except Exception as exc:  # noqa: BLE001 - advisory evidence captures broker/read failures.
        return None, _failure_reason(exc)


def _success_payload(
    *,
    broker: str,
    instrument: str,
    source: str,
    payload: Any,
    latency_ms: int,
) -> dict[str, Any]:
    return {
        "success": True,
        "broker": broker,
        "instrument": instrument,
        "source": source,
        "timestamp": _extract_timestamp(payload) or _iso_timestamp(),
        "latency_ms": latency_ms,
        "payload_type": type(payload).__name__,
        **_advisory_safety_flags(),
    }


def _read_success(value: Any) -> tuple[bool, str]:
    if value is None:
        return False, "empty_broker_response"
    if isinstance(value, bool):
        return (value, "" if value else "broker_returned_false")
    if isinstance(value, Mapping):
        if value.get("ok") is False:
            return False, str(value.get("error") or value.get("reason") or "broker_read_failed")
        status = value.get("status")
        if isinstance(status, int) and not (200 <= status < 300):
            return False, f"http_{status}"
        if str(value.get("error") or "").strip():
            return False, str(value.get("error"))
        if str(value.get("status") or "").upper() in {"FAIL", "FAILED", "FAIL_CLOSED", "ERROR"}:
            return False, str(value.get("reason") or value.get("status"))
        return bool(value), "empty_broker_response" if not value else ""
    if isinstance(value, (list, tuple, set)):
        return bool(value), "empty_broker_response" if not value else ""
    return True, ""


def _extract_timestamp(value: Any) -> str:
    payload = _payload_data(value)
    timestamp = _timestamp_from_payload(payload)
    if timestamp:
        return timestamp
    if isinstance(payload, Mapping):
        for collection_key in ("prices", "candles", "data", "results"):
            nested = payload.get(collection_key)
            timestamp = _timestamp_from_payload(nested)
            if timestamp:
                return timestamp
    return ""


def _explicit_instrument_mismatch(payload: Any, instrument: str) -> str:
    requested = _normalize_symbol(instrument)
    if not requested:
        return ""
    observed = _instrument_values(_payload_data(payload))
    if not observed:
        return ""
    if requested in {_normalize_symbol(value) for value in observed}:
        return ""
    return "instrument_mismatch"


def _instrument_values(payload: Any) -> set[str]:
    values: set[str] = set()
    if isinstance(payload, Mapping):
        for key in ("instrument", "product_id", "product", "symbol"):
            value = payload.get(key)
            if _value_present(value):
                values.add(str(value))
        for collection_key in ("prices", "candles", "data", "results"):
            nested = payload.get(collection_key)
            values.update(_instrument_values(nested))
    elif isinstance(payload, (list, tuple)):
        for item in payload:
            values.update(_instrument_values(item))
    return values


def _normalize_symbol(value: str) -> str:
    return str(value or "").strip().upper().replace("/", "-")


def _timestamp_from_payload(payload: Any) -> str:
    if isinstance(payload, Mapping):
        for key in ("timestamp", "time", "trade_time", "price_time", "ts", "start"):
            value = payload.get(key)
            if _value_present(value):
                return _normalize_timestamp(value)
    if isinstance(payload, (list, tuple)) and payload:
        first = payload[-1]
        if isinstance(first, Mapping):
            return _timestamp_from_payload(first)
        if isinstance(first, (list, tuple)) and first:
            return _normalize_timestamp(first[0])
    return ""


def _normalize_timestamp(value: Any) -> str:
    if isinstance(value, (int, float)):
        number = float(value)
        if number > 10_000_000_000:
            number = number / 1000.0
        return datetime.fromtimestamp(number, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return str(value)


def _payload_data(value: Any) -> Any:
    if isinstance(value, Mapping) and "data" in value:
        return value.get("data")
    return value


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


def _configured_health_candidates(env: Mapping[str, Any]) -> list[dict[str, str]]:
    candidates: list[dict[str, str]] = []
    pairs = (
        ("dashboard", "DASHBOARD_HOST", "DASHBOARD_PORT", "/health"),
        ("api", "API_HOST", "API_PORT", "/health"),
        ("backend", "BACKEND_HOST", "BACKEND_PORT", "/health"),
        ("mobile", "MOBILE_HOST", "MOBILE_PORT", "/api/status"),
        ("launcher", "LAUNCHER_HOST", "LAUNCHER_PORT", "/health"),
    )
    for name, host_key, port_key, path in pairs:
        host = str(env.get(host_key, "") or "").strip()
        port = str(env.get(port_key, "") or "").strip()
        if host and port:
            candidates.append({"name": name, "source": "configured", "url": f"http://{host}:{port}{path}"})
    explicit = str(env.get("CSS_HEALTH_URL", "") or "").strip()
    if explicit:
        candidates.insert(0, {"name": "explicit", "source": "configured", "url": explicit})
    return candidates


def _default_health_candidates() -> list[dict[str, str]]:
    return [
        {"name": "backend_api", "source": "default", "url": "http://127.0.0.1:8000/health"},
        {"name": "dashboard_web", "source": "default", "url": "http://127.0.0.1:8091/health"},
        {"name": "dashboard_mobile", "source": "default", "url": "http://127.0.0.1:8090/api/status"},
        {"name": "launcher", "source": "default", "url": "http://127.0.0.1:12345/health"},
    ]


def _endpoint_health_state(status_code: int | None, reachable: bool) -> str:
    if not reachable:
        return "RED"
    if isinstance(status_code, int) and 200 <= status_code < 300:
        return "GREEN"
    if isinstance(status_code, int) and 300 <= status_code < 500:
        return "AMBER"
    return "RED"


def _last_reason(attempts: list[dict[str, str]]) -> str:
    for attempt in reversed(attempts):
        reason = str(attempt.get("reason", "") or "")
        if reason:
            return reason
    return ""


def _elapsed_ms(clock: ClockFn, started: float) -> int:
    return max(0, int(round((clock() - started) * 1000)))


def _iso_timestamp() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _failure_reason(exc: BaseException) -> str:
    if isinstance(exc, TimeoutError):
        return "TIMEOUT"
    return str(exc) or exc.__class__.__name__


def _normalize_broker(broker: str) -> str:
    return str(broker or "").strip().lower()


def _advisory_safety_flags() -> dict[str, bool]:
    return {
        "advisory_only": True,
        "execution_allowed": False,
        "live_trading_blocked": True,
        "broker_execution_armed": False,
    }
