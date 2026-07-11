from __future__ import annotations

import copy
import time
from collections.abc import Callable, Mapping
from datetime import datetime, timezone
from typing import Any

from backend.runtime.broker_health_monitor import monitor_broker_health
from backend.runtime.live_connectivity_certifier import certify_live_connectivity


PAYLOAD_VERSION = "css.phase163b3a.runtime_certification_snapshot.v1"
DIAGNOSTICS_SCHEMA = "css.phase163b3a.runtime_certification_diagnostics.v1"


CertificationFn = Callable[..., Mapping[str, Any]]
HealthMonitorFn = Callable[..., Mapping[str, Any]]
ClockFn = Callable[[], float]

_SNAPSHOT_CACHE: dict[tuple[str, str, str], dict[str, Any]] = {}
_CAPABILITY_CACHE: dict[tuple[str, str], dict[str, Any]] = {}
_TELEMETRY: dict[str, Any] = {
    "certification_runs": 0,
    "cache_hits": 0,
    "cache_misses": 0,
    "broker_api_calls_performed": 0,
}


def get_runtime_certification_snapshot(
    broker: str,
    *,
    mode: str = "live",
    cycle_id: str | int | None = None,
    force_refresh: bool = False,
    certifier_fn: CertificationFn = certify_live_connectivity,
    health_monitor_fn: HealthMonitorFn = monitor_broker_health,
    clock: ClockFn = time.perf_counter,
) -> dict[str, Any]:
    """Return one canonical read-only broker certification snapshot per cycle.

    The snapshot is advisory-only. The certifier path is read-only and is
    cached by broker, mode, and runtime cycle so dashboard refreshes cannot
    trigger duplicate broker certification work in the same cycle.
    """

    broker_key = _broker_key(broker)
    mode_key = _mode_key(mode)
    cycle_key = str(cycle_id if cycle_id is not None else "default")
    cache_key = (broker_key, mode_key, cycle_key)

    if not force_refresh and cache_key in _SNAPSHOT_CACHE:
        _TELEMETRY["cache_hits"] = int(_TELEMETRY.get("cache_hits", 0)) + 1
        return copy.deepcopy(_SNAPSHOT_CACHE[cache_key])

    _TELEMETRY["cache_misses"] = int(_TELEMETRY.get("cache_misses", 0)) + 1
    cycle_started = clock()

    certification_started = clock()
    phase156b = _call_certifier(certifier_fn, broker_key, mode_key)
    certification_ms = _elapsed_ms(clock, certification_started)
    api_calls = _estimate_broker_api_calls(phase156b)
    _TELEMETRY["certification_runs"] = int(_TELEMETRY.get("certification_runs", 0)) + 1
    _TELEMETRY["broker_api_calls_performed"] = int(_TELEMETRY.get("broker_api_calls_performed", 0)) + api_calls

    capability_info, capability_cache_status = _capability_info(broker_key, mode_key, phase156b)
    phase156c = _call_health_monitor(health_monitor_fn, broker_key, mode_key, phase156b)
    runtime_cycle_ms = _elapsed_ms(clock, cycle_started)

    snapshot = build_runtime_certification_snapshot(
        broker_key,
        mode=mode_key,
        cycle_id=cycle_key,
        phase156b=phase156b,
        phase156c=phase156c,
        source="live_connectivity_certifier",
        capability_info=capability_info,
        telemetry={
            "certification_execution_ms": certification_ms,
            "broker_api_calls_performed": api_calls,
            "cache_hits": int(_TELEMETRY.get("cache_hits", 0)),
            "cache_misses": int(_TELEMETRY.get("cache_misses", 0)),
            "runtime_cycle_duration_ms": runtime_cycle_ms,
            "capability_cache_status": capability_cache_status,
        },
    )
    _SNAPSHOT_CACHE[cache_key] = copy.deepcopy(snapshot)
    return snapshot


def build_runtime_certification_snapshot(
    broker: str,
    *,
    mode: str = "live",
    cycle_id: str | int | None = None,
    phase156b: Mapping[str, Any] | None = None,
    phase156c: Mapping[str, Any] | None = None,
    source: str = "runtime_snapshot",
    capability_info: Mapping[str, Any] | None = None,
    telemetry: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the canonical dashboard/runtime projection from Phase 156B/156C."""

    phase156b_report = _mapping(phase156b)
    phase156c_report = _mapping(phase156c)
    broker_key = _broker_key(broker or phase156b_report.get("broker") or phase156c_report.get("broker"))
    mode_key = _mode_key(mode or phase156b_report.get("mode") or phase156c_report.get("mode"))
    latency = _canonical_latency(phase156b_report, phase156c_report)
    freshness = _canonical_freshness(phase156b_report, phase156c_report)
    certification = str(
        phase156b_report.get("certification")
        or _validation_status_to_certification(phase156b_report.get("validation_status"))
        or phase156c_report.get("connectivity_status")
        or phase156c_report.get("health")
        or "RED"
    ).upper()
    operational_state = str(phase156c_report.get("health") or certification or "RED").upper()
    readiness = str(phase156b_report.get("phase156a") or ("GREEN" if certification in {"GREEN", "AMBER"} else "RED")).upper()

    snapshot = {
        "payload_version": PAYLOAD_VERSION,
        "broker": broker_key.upper() if broker_key else "NONE",
        "mode": mode_key,
        "cycle_id": str(cycle_id if cycle_id is not None else "default"),
        "generated_at": _utc_iso(),
        "source": str(source),
        "phase156a": readiness,
        "phase156b": phase156b_report,
        "phase156c": phase156c_report,
        "certification": certification,
        "broker_readiness": readiness,
        "operational_state": operational_state,
        "latency": latency,
        "latency_status": str(phase156b_report.get("latency_status") or phase156c_report.get("latency_health") or "RED").upper(),
        "market_data_freshness": freshness,
        "connectivity_score": _float_or_none(phase156b_report.get("connectivity_score")),
        "health_score": _float_or_none(phase156c_report.get("overall_health_score", phase156c_report.get("overall_score"))),
        "capability_info": dict(capability_info or _derive_capability_info(phase156b_report)),
        "execution_allowed": False,
        "live_trading_blocked": True,
        "broker_execution_armed": False,
        "advisory_only": True,
        "telemetry": {
            "certification_execution_ms": _int_or_none(_mapping(telemetry).get("certification_execution_ms")),
            "broker_api_calls_performed": int(_mapping(telemetry).get("broker_api_calls_performed", 0) or 0),
            "cache_hits": int(_mapping(telemetry).get("cache_hits", 0) or 0),
            "cache_misses": int(_mapping(telemetry).get("cache_misses", 0) or 0),
            "runtime_cycle_duration_ms": _int_or_none(_mapping(telemetry).get("runtime_cycle_duration_ms")),
            "capability_cache_status": str(_mapping(telemetry).get("capability_cache_status", "NOT_USED")),
        },
    }
    return _json_safe(snapshot)


def runtime_certification_diagnostics(snapshot: Mapping[str, Any] | None = None) -> dict[str, Any]:
    source = _mapping(snapshot)
    telemetry = _mapping(source.get("telemetry"))
    payload = {
        "payload_schema": DIAGNOSTICS_SCHEMA,
        "generated_at": _utc_iso(),
        "certification_execution_ms": telemetry.get("certification_execution_ms"),
        "broker_api_calls_performed": int(
            telemetry.get("broker_api_calls_performed", _TELEMETRY.get("broker_api_calls_performed", 0)) or 0
        ),
        "cache_hits": int(telemetry.get("cache_hits", _TELEMETRY.get("cache_hits", 0)) or 0),
        "cache_misses": int(telemetry.get("cache_misses", _TELEMETRY.get("cache_misses", 0)) or 0),
        "runtime_cycle_duration_ms": telemetry.get("runtime_cycle_duration_ms"),
        "certification_runs": int(_TELEMETRY.get("certification_runs", 0) or 0),
        "cached_snapshot_count": len(_SNAPSHOT_CACHE),
        "cached_capability_count": len(_CAPABILITY_CACHE),
        "execution_allowed": False,
        "live_trading_blocked": True,
        "broker_execution_armed": False,
        "advisory_only": True,
    }
    return _json_safe(payload)


def clear_runtime_certification_snapshot_cache() -> None:
    _SNAPSHOT_CACHE.clear()
    _CAPABILITY_CACHE.clear()
    _TELEMETRY.update(
        {
            "certification_runs": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "broker_api_calls_performed": 0,
        }
    )


def _call_certifier(certifier_fn: CertificationFn, broker: str, mode: str) -> dict[str, Any]:
    try:
        report = certifier_fn(broker, mode=mode)
        return dict(report) if isinstance(report, Mapping) else {}
    except Exception as exc:
        return {
            "broker": broker.upper(),
            "mode": mode,
            "phase156a": "RED",
            "certification": "RED",
            "authentication": "FAIL",
            "account": "FAIL",
            "market_data": "FAIL",
            "latency": {},
            "blocker_reasons": [f"certifier_exception:{_failure_reason(exc)}"],
            "execution_allowed": False,
            "live_trading_blocked": True,
            "broker_execution_armed": False,
            "advisory_only": True,
        }


def _call_health_monitor(
    health_monitor_fn: HealthMonitorFn,
    broker: str,
    mode: str,
    phase156b: Mapping[str, Any],
) -> dict[str, Any]:
    try:
        report = health_monitor_fn(
            broker,
            mode=mode,
            connectivity_certifier_fn=lambda *_args, **_kwargs: dict(phase156b),
        )
        return dict(report) if isinstance(report, Mapping) else {}
    except TypeError:
        try:
            report = health_monitor_fn(broker, mode=mode)
            return dict(report) if isinstance(report, Mapping) else {}
        except Exception as exc:
            return _health_fail_closed(broker, mode, exc)
    except Exception as exc:
        return _health_fail_closed(broker, mode, exc)


def _health_fail_closed(broker: str, mode: str, exc: Exception) -> dict[str, Any]:
    return {
        "broker": broker.upper(),
        "mode": mode,
        "health": "RED",
        "overall_score": 0.0,
        "market_data_freshness": {"status": "RED", "reason": "health_monitor_exception"},
        "blocker_reasons": [f"health_monitor_exception:{_failure_reason(exc)}"],
        "execution_allowed": False,
        "live_trading_blocked": True,
        "broker_execution_armed": False,
        "advisory_only": True,
    }


def _capability_info(broker: str, mode: str, phase156b: Mapping[str, Any]) -> tuple[dict[str, Any], str]:
    key = (broker, mode)
    if key in _CAPABILITY_CACHE:
        return copy.deepcopy(_CAPABILITY_CACHE[key]), "HIT"
    info = _derive_capability_info(phase156b)
    _CAPABILITY_CACHE[key] = copy.deepcopy(info)
    return info, "MISS"


def _derive_capability_info(phase156b: Mapping[str, Any]) -> dict[str, Any]:
    stage = _mapping(phase156b.get("stage_results"))
    account = _mapping(stage.get("account"))
    market = _mapping(stage.get("market_data"))
    market_details = _mapping(market.get("details"))
    evidence = market_details.get("evidence") if isinstance(market_details.get("evidence"), list) else []
    symbols = [
        str(item.get("symbol"))
        for item in evidence
        if isinstance(item, Mapping) and item.get("symbol")
    ]
    return {
        "account_read_supported": str(account.get("status", phase156b.get("account", ""))).upper() == "PASS"
        or bool(phase156b.get("account_loaded", False)),
        "market_data_read_supported": str(market.get("status", phase156b.get("market_data", ""))).upper() == "PASS"
        or bool(phase156b.get("market_data_loaded", False)),
        "symbols": sorted(dict.fromkeys(symbols)),
        "product_count": int(phase156b.get("products_loaded", 0) or 0),
        "execution_supported": False,
        "advisory_only": True,
    }


def _estimate_broker_api_calls(phase156b: Mapping[str, Any]) -> int:
    stage = _mapping(phase156b.get("stage_results"))
    count = 0
    if str(phase156b.get("phase156a", "")).upper() == "GREEN":
        count += 1
    for name in ("authentication", "account", "market_data"):
        item = _mapping(stage.get(name))
        if item or str(phase156b.get(name, "")).upper() in {"PASS", "FAIL"}:
            count += 1
    market_details = _mapping(_mapping(stage.get("market_data")).get("details"))
    evidence = market_details.get("evidence")
    if isinstance(evidence, list) and len(evidence) > 1:
        count += max(0, len(evidence) - 1)
    return count


def _canonical_latency(phase156b: Mapping[str, Any], phase156c: Mapping[str, Any]) -> dict[str, Any]:
    source = _mapping(phase156b.get("latency"))
    if not source:
        source = _mapping(phase156c.get("latency"))
    fallback_latency = _int_or_none(phase156b.get("latency_ms"))
    return {
        "authentication_ms": _int_or_none(source.get("authentication_ms")),
        "account_ms": _int_or_none(source.get("account_ms")),
        "market_data_ms": _int_or_none(source.get("market_data_ms", source.get("market_ms"))),
        "overall_ms": _int_or_none(source.get("overall_ms")) or fallback_latency,
        "active_validation_ms": _int_or_none(source.get("active_validation_ms")),
    }


def _canonical_freshness(phase156b: Mapping[str, Any], phase156c: Mapping[str, Any]) -> dict[str, Any]:
    freshness = _mapping(phase156c.get("market_data_freshness"))
    if freshness:
        return freshness
    market_status = str(phase156b.get("market_data", "")).upper()
    market_loaded = bool(phase156b.get("market_data_loaded", False))
    stage = _mapping(phase156b.get("stage_results"))
    details = _mapping(_mapping(stage.get("market_data")).get("details"))
    return {
        "status": "GREEN" if market_status == "PASS" or market_loaded else "RED",
        "reason": "phase156b_market_data_pass" if market_status == "PASS" or market_loaded else "phase156b_market_data_failed",
        "timestamp": str(details.get("timestamp", phase156b.get("validation_timestamp", "NOT_AVAILABLE"))),
        "missing_quotes": list(details.get("missing_symbols", [])) if isinstance(details.get("missing_symbols"), list) else [],
    }


def _validation_status_to_certification(value: Any) -> str:
    status = str(value or "").strip().upper()
    if status in {"GREEN", "PASS", "OK", "READY", "OPERATIONAL"}:
        return "GREEN"
    if status in {"AMBER", "WARN", "WARNING", "DEGRADED"}:
        return "AMBER"
    if status:
        return "RED"
    return ""


def _elapsed_ms(clock: ClockFn, started: float) -> int:
    return max(0, int(round((clock() - started) * 1000)))


def _broker_key(value: Any) -> str:
    return str(value or "none").strip().lower()


def _mode_key(value: Any) -> str:
    return str(value or "live").strip().lower()


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _int_or_none(value: Any) -> int | None:
    try:
        if value in (None, ""):
            return None
        return int(round(float(value)))
    except (TypeError, ValueError):
        return None


def _float_or_none(value: Any) -> float | None:
    try:
        if value in (None, ""):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _failure_reason(exc: Exception) -> str:
    return exc.__class__.__name__.lower()


def _utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _json_safe(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(item) for item in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


__all__ = [
    "PAYLOAD_VERSION",
    "build_runtime_certification_snapshot",
    "clear_runtime_certification_snapshot_cache",
    "get_runtime_certification_snapshot",
    "runtime_certification_diagnostics",
]
