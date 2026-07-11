from __future__ import annotations

import json
import math
import time
from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PAYLOAD_VERSION = "css.phase164.operational_proving.v1"
HISTORY_SCHEMA = "css.phase164.certification_history.v1"


def build_operational_proving_report(
    *,
    runtime_summary: Mapping[str, Any] | None = None,
    runtime_health: Mapping[str, Any] | None = None,
    runtime_performance: Mapping[str, Any] | None = None,
    certification_snapshot: Mapping[str, Any] | None = None,
    frontend_payload: Mapping[str, Any] | None = None,
    history: Sequence[Mapping[str, Any]] | None = None,
    now: float | None = None,
) -> dict[str, Any]:
    """Build the Phase 164 RC1 operational qualification report.

    This report is advisory-only. It consumes existing runtime/certification
    evidence and never calls broker mutation, order, cancellation, arming, or
    live execution paths.
    """

    generated_epoch = float(now if now is not None else time.time())
    runtime = _mapping(runtime_summary)
    health = _mapping(runtime_health)
    performance = _mapping(runtime_performance)
    snapshot = _mapping(certification_snapshot)
    frontend = _mapping(frontend_payload)
    history_rows = [_mapping(item) for item in (history or []) if isinstance(item, Mapping)]

    uptime = _uptime_seconds(runtime, generated_epoch)
    latency = _mapping(snapshot.get("latency"))
    telemetry = _mapping(snapshot.get("telemetry"))
    warnings = _string_list(health.get("warnings"))
    restart_count = _int(runtime.get("restart_count", health.get("restart_count", 0)))
    recovery_count = _int(runtime.get("recovery_count", health.get("recovery_count", 0)))
    unexpected_exceptions = _int(runtime.get("unexpected_exceptions", runtime.get("unexpected_exception_count", 0)))
    broker_disconnects = _int(runtime.get("broker_disconnects", runtime.get("broker_disconnect_count", 0)))

    metrics = {
        "startup_timestamp": str(runtime.get("startup_timestamp", runtime.get("started_at", "DATA UNAVAILABLE"))),
        "uptime_seconds": uptime,
        "heartbeat_continuity": _heartbeat_continuity(health),
        "runtime_cycle_duration_ms": _number(runtime.get("cycle_duration_ms", performance.get("pipeline_latency_ms"))),
        "memory_usage": performance.get("memory_usage"),
        "cpu_usage": performance.get("cpu_usage"),
        "broker_latency": {
            "authentication_ms": _nullable_number(latency.get("authentication_ms")),
            "account_ms": _nullable_number(latency.get("account_ms")),
            "market_data_ms": _nullable_number(latency.get("market_data_ms")),
            "overall_ms": _nullable_number(latency.get("overall_ms")),
            "active_validation_ms": _nullable_number(latency.get("active_validation_ms")),
        },
        "broker_health": str(snapshot.get("operational_state", health.get("runtime_health", "DATA UNAVAILABLE"))),
        "dashboard_latency_ms": _number(performance.get("dashboard_latency_ms")),
        "api_latency_ms": _number(performance.get("api_latency_ms")),
        "certification_latency_ms": _nullable_number(telemetry.get("certification_execution_ms")),
        "cache_efficiency": {
            "runtime_cache_hit_rate": _number(performance.get("cache_hit_rate")),
            "certification_cache_hits": _int(telemetry.get("cache_hits")),
            "certification_cache_misses": _int(telemetry.get("cache_misses")),
        },
        "snapshot_generation": {
            "payload_version": str(snapshot.get("payload_version", "DATA UNAVAILABLE")),
            "generated_at": str(snapshot.get("generated_at", "DATA UNAVAILABLE")),
            "source": str(snapshot.get("source", "DATA UNAVAILABLE")),
        },
        "frontend_payload_generation": {
            "payload_version": str(frontend.get("payload_version", "DATA UNAVAILABLE")),
            "generated_at": str(frontend.get("generated_at", "DATA UNAVAILABLE")),
            "section_count": len(_mapping(frontend.get("sections"))),
        },
        "broker_evidence_consistency": _broker_evidence_consistency(snapshot, frontend),
        "readiness_consistency": _readiness_consistency(snapshot, frontend),
        "operational_acceptance_consistency": _operational_acceptance_consistency(snapshot),
        "go_no_go_consistency": _go_no_go_consistency(snapshot),
        "restart_count": restart_count,
        "unexpected_exceptions": unexpected_exceptions,
        "broker_disconnects": broker_disconnects,
        "automatic_recovery_events": recovery_count,
        "runtime_warnings": warnings,
        "memory_growth": _memory_growth(history_rows, performance),
        "resource_utilization_trend": _resource_trend(history_rows, performance),
    }

    trend = certification_history_trend([*history_rows, _history_row(snapshot, metrics)])
    scorecard = operational_scorecard(metrics=metrics, runtime_health=health, certification_snapshot=snapshot, trend=trend)
    gate = pre_pilot_gate(metrics=metrics, runtime_health=health, certification_snapshot=snapshot, trend=trend, scorecard=scorecard)

    report = {
        "payload_version": PAYLOAD_VERSION,
        "generated_at": _iso(generated_epoch),
        "runtime_metrics": metrics,
        "certification_snapshot": dict(snapshot),
        "certification_history_trend": trend,
        "operational_scorecard": scorecard,
        "pre_pilot_gate": gate,
        "open_risks": _open_risks(metrics, scorecard, gate),
        "execution_allowed": False,
        "live_trading_blocked": True,
        "broker_execution_armed": False,
        "advisory_only": True,
    }
    return _json_safe(report)


def operational_scorecard(
    *,
    metrics: Mapping[str, Any],
    runtime_health: Mapping[str, Any],
    certification_snapshot: Mapping[str, Any],
    trend: Mapping[str, Any],
) -> dict[str, Any]:
    safety = _safety_score(certification_snapshot)
    dimensions = {
        "runtime_stability": _runtime_stability_score(metrics, runtime_health),
        "broker_reliability": _broker_reliability_score(certification_snapshot),
        "dashboard_reliability": _dashboard_reliability_score(metrics),
        "operational_readiness": _operational_readiness_score(certification_snapshot),
        "certification_stability": _certification_stability_score(trend),
        "performance": _performance_score(metrics),
        "safety": safety,
        "recovery": _recovery_score(metrics),
        "availability": _availability_score(metrics),
    }
    overall = round(sum(dimensions.values()) / len(dimensions), 2)
    if safety < 100.0:
        overall = min(overall, 25.0)
    status = _score_status(overall)
    return {
        "dimensions": dimensions,
        "overall_operational_score": overall,
        "overall_status": status,
        "execution_allowed": False,
        "live_trading_blocked": True,
        "broker_execution_armed": False,
        "advisory_only": True,
    }


def pre_pilot_gate(
    *,
    metrics: Mapping[str, Any],
    runtime_health: Mapping[str, Any],
    certification_snapshot: Mapping[str, Any],
    trend: Mapping[str, Any],
    scorecard: Mapping[str, Any],
) -> dict[str, Any]:
    blockers: list[str] = []
    certification = str(certification_snapshot.get("certification", "RED")).upper()
    if certification == "RED" or _int(trend.get("red_certification_count")) > 0:
        blockers.append("red_certification_present")
    if bool(trend.get("stable_amber_green_trend")) is not True:
        blockers.append("certification_trend_not_stable")
    phase156b = _mapping(certification_snapshot.get("phase156b"))
    if str(phase156b.get("authentication", "")).upper() != "PASS":
        blockers.append("broker_not_authenticated")
    if str(_mapping(metrics.get("broker_evidence_consistency")).get("status", "")).upper() != "PASS":
        blockers.append("dashboard_broker_evidence_inconsistent")
    if str(runtime_health.get("runtime_health", runtime_health.get("overall_operational_health", "RED"))).upper() == "RED":
        blockers.append("runtime_not_stable")
    if str(_mapping(metrics.get("memory_growth")).get("status", "GREEN")).upper() == "RED":
        blockers.append("memory_growth_unstable")
    if _int(metrics.get("restart_count")) > 0 or _int(metrics.get("unexpected_exceptions")) > 0:
        blockers.append("unexpected_restart_or_exception_present")
    if _safety_score(certification_snapshot) < 100.0:
        blockers.append("execution_firewall_not_preserved")
    if _number(_mapping(scorecard).get("overall_operational_score")) < 75.0:
        blockers.append("operational_score_below_threshold")

    eligible = not blockers
    return {
        "eligible": eligible,
        "decision": "ELIGIBLE_FOR_CONTROLLED_READ_ONLY_PILOT_PLANNING" if eligible else "NOT_ELIGIBLE",
        "blockers": sorted(set(blockers)),
        "recommendation": (
            "Continue controlled read-only pilot planning; execution remains blocked."
            if eligible
            else "Resolve pre-pilot blockers before pilot planning."
        ),
        "execution_allowed": False,
        "live_trading_blocked": True,
        "broker_execution_armed": False,
        "advisory_only": True,
    }


def persist_certification_snapshot(
    snapshot: Mapping[str, Any],
    path: str | Path,
    *,
    max_records: int = 500,
    now: float | None = None,
) -> dict[str, Any]:
    target = Path(path)
    rows = load_certification_history(target)
    rows.append(_history_row(snapshot, {}, now=now))
    rows = rows[-max(1, int(max_records)) :]
    payload = {
        "payload_schema": HISTORY_SCHEMA,
        "updated_at": _iso(now if now is not None else time.time()),
        "records": rows,
        "execution_allowed": False,
        "live_trading_blocked": True,
        "broker_execution_armed": False,
        "advisory_only": True,
    }
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(_json_safe(payload), indent=2, sort_keys=True), encoding="utf-8")
    return payload


def load_certification_history(path: str | Path) -> list[dict[str, Any]]:
    target = Path(path)
    if not target.exists():
        return []
    try:
        payload = json.loads(target.read_text(encoding="utf-8"))
    except Exception:
        return []
    records = payload.get("records") if isinstance(payload, Mapping) else []
    return [dict(item) for item in records if isinstance(item, Mapping)] if isinstance(records, list) else []


def certification_history_trend(history: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    rows = [_mapping(item) for item in history if isinstance(item, Mapping)]
    if not rows:
        return {
            "sample_count": 0,
            "red_certification_count": 0,
            "stable_amber_green_trend": False,
            "latest_certification": "DATA UNAVAILABLE",
            "score_delta": 0.0,
            "trend": "INSUFFICIENT_DATA",
        }
    certifications = [str(row.get("certification", "RED")).upper() for row in rows]
    scores = [_number(row.get("runtime_score")) for row in rows if row.get("runtime_score") is not None]
    score_delta = round(scores[-1] - scores[0], 2) if len(scores) >= 2 else 0.0
    red_count = sum(1 for item in certifications if item == "RED")
    latest = certifications[-1]
    stable = red_count == 0 and latest in {"GREEN", "AMBER"} and len(rows) >= 1
    return {
        "sample_count": len(rows),
        "red_certification_count": red_count,
        "stable_amber_green_trend": stable,
        "latest_certification": latest,
        "score_delta": score_delta,
        "trend": "IMPROVING" if score_delta > 2 else "DEGRADING" if score_delta < -2 else "STABLE",
    }


def _history_row(snapshot: Mapping[str, Any], metrics: Mapping[str, Any], *, now: float | None = None) -> dict[str, Any]:
    phase156b = _mapping(snapshot.get("phase156b"))
    phase156c = _mapping(snapshot.get("phase156c"))
    score = snapshot.get("health_score", snapshot.get("connectivity_score"))
    if metrics:
        score = _mapping(metrics.get("operational_scorecard")).get("overall_operational_score", score)
    return {
        "timestamp": str(snapshot.get("generated_at", _iso(now if now is not None else time.time()))),
        "phase156a": str(snapshot.get("phase156a", phase156b.get("phase156a", "RED"))).upper(),
        "phase156b": str(snapshot.get("certification", phase156b.get("certification", "RED"))).upper(),
        "phase156c": str(phase156c.get("health", snapshot.get("operational_state", "RED"))).upper(),
        "health": str(snapshot.get("operational_state", phase156c.get("health", "RED"))).upper(),
        "latency": _mapping(snapshot.get("latency")),
        "broker_state": {"broker": snapshot.get("broker"), "mode": snapshot.get("mode")},
        "execution_state": {
            "execution_allowed": False,
            "live_trading_blocked": True,
            "broker_execution_armed": False,
        },
        "runtime_score": _number(score),
        "operational_status": str(snapshot.get("operational_state", "RED")).upper(),
        "certification": str(snapshot.get("certification", phase156b.get("certification", "RED"))).upper(),
    }


def _runtime_stability_score(metrics: Mapping[str, Any], health: Mapping[str, Any]) -> float:
    score = _status_score(str(health.get("runtime_health", health.get("overall_operational_health", "RED"))))
    score -= min(30.0, _int(metrics.get("restart_count")) * 15.0)
    score -= min(30.0, _int(metrics.get("unexpected_exceptions")) * 10.0)
    score -= min(15.0, len(_string_list(metrics.get("runtime_warnings"))) * 3.0)
    return _bounded(score)


def _broker_reliability_score(snapshot: Mapping[str, Any]) -> float:
    cert = _status_score(str(snapshot.get("certification", "RED")))
    health = _status_score(str(snapshot.get("operational_state", "RED")))
    return round((cert + health) / 2.0, 2)


def _dashboard_reliability_score(metrics: Mapping[str, Any]) -> float:
    score = 100.0 if _mapping(metrics.get("broker_evidence_consistency")).get("status") == "PASS" else 45.0
    latency = _number(metrics.get("dashboard_latency_ms"))
    if latency >= 3000:
        score -= 50.0
    elif latency >= 1000:
        score -= 20.0
    return _bounded(score)


def _operational_readiness_score(snapshot: Mapping[str, Any]) -> float:
    readiness = str(snapshot.get("broker_readiness", snapshot.get("phase156a", "RED"))).upper()
    return _status_score(readiness)


def _certification_stability_score(trend: Mapping[str, Any]) -> float:
    if _int(trend.get("red_certification_count")):
        return 20.0
    return 100.0 if bool(trend.get("stable_amber_green_trend")) else 65.0


def _performance_score(metrics: Mapping[str, Any]) -> float:
    latencies = [
        _number(metrics.get("runtime_cycle_duration_ms")),
        _number(metrics.get("dashboard_latency_ms")),
        _number(metrics.get("api_latency_ms")),
        _number(metrics.get("certification_latency_ms")),
    ]
    worst = max(latencies) if latencies else 0.0
    score = 100.0
    if worst >= 5000:
        score -= 60.0
    elif worst >= 1500:
        score -= 25.0
    cache = _mapping(metrics.get("cache_efficiency"))
    if _number(cache.get("runtime_cache_hit_rate")) < 40.0 and (_int(cache.get("certification_cache_hits")) + _int(cache.get("certification_cache_misses"))) > 0:
        score -= 10.0
    return _bounded(score)


def _safety_score(snapshot: Mapping[str, Any]) -> float:
    return 100.0 if (
        snapshot.get("execution_allowed") is False
        and snapshot.get("live_trading_blocked") is True
        and snapshot.get("broker_execution_armed") is False
        and snapshot.get("advisory_only") is True
    ) else 0.0


def _recovery_score(metrics: Mapping[str, Any]) -> float:
    if _int(metrics.get("unexpected_exceptions")):
        return 40.0
    if _int(metrics.get("automatic_recovery_events")):
        return 85.0
    return 100.0


def _availability_score(metrics: Mapping[str, Any]) -> float:
    if _mapping(metrics.get("heartbeat_continuity")).get("status") != "PASS":
        return 45.0
    uptime = _number(metrics.get("uptime_seconds"))
    return 100.0 if uptime >= 0 else 65.0


def _open_risks(metrics: Mapping[str, Any], scorecard: Mapping[str, Any], gate: Mapping[str, Any]) -> list[str]:
    risks = list(_mapping(gate).get("blockers", []))
    if str(_mapping(scorecard).get("overall_status", "RED")).upper() != "GREEN":
        risks.append("operational_score_not_green")
    if _mapping(metrics.get("heartbeat_continuity")).get("status") != "PASS":
        risks.append("heartbeat_continuity_not_confirmed")
    return sorted({str(item) for item in risks if str(item).strip()})


def _heartbeat_continuity(health: Mapping[str, Any]) -> dict[str, Any]:
    age = health.get("heartbeat_age")
    age_value = _nullable_number(age)
    status = "PASS" if age_value is None or age_value <= 300 else "FAIL"
    return {"status": status, "heartbeat_age": age_value}


def _uptime_seconds(runtime: Mapping[str, Any], now: float) -> float:
    for key in ("uptime_seconds", "continuous_uptime_seconds"):
        value = runtime.get(key)
        if value is not None:
            return _number(value)
    started = runtime.get("startup_timestamp", runtime.get("started_at"))
    parsed = _parse_timestamp(started)
    return round(max(0.0, now - parsed), 3) if parsed is not None else 0.0


def _memory_growth(history: Sequence[Mapping[str, Any]], performance: Mapping[str, Any]) -> dict[str, Any]:
    current = _memory_value(performance.get("memory_usage"))
    previous = [_memory_value(_mapping(row.get("resource_utilization")).get("memory_usage")) for row in history]
    previous = [value for value in previous if value is not None]
    delta = current - previous[-1] if current is not None and previous else 0.0
    status = "RED" if delta > 250_000 else "AMBER" if delta > 100_000 else "GREEN"
    return {"status": status, "current": current, "delta": delta}


def _resource_trend(history: Sequence[Mapping[str, Any]], performance: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "sample_count": len(history) + 1,
        "memory_usage": performance.get("memory_usage"),
        "cpu_usage": performance.get("cpu_usage"),
    }


def _broker_evidence_consistency(snapshot: Mapping[str, Any], frontend: Mapping[str, Any]) -> dict[str, Any]:
    sections = _mapping(frontend.get("sections"))
    broker_section = _mapping(sections.get("broker"))
    if not broker_section:
        return {"status": "PASS", "reason": "frontend_payload_not_provided"}
    broker = str(snapshot.get("broker", "")).upper()
    displayed = str(broker_section.get("selected_broker", "")).upper()
    return {"status": "PASS" if not broker or not displayed or broker == displayed else "FAIL", "snapshot_broker": broker, "displayed_broker": displayed}


def _readiness_consistency(snapshot: Mapping[str, Any], frontend: Mapping[str, Any]) -> dict[str, Any]:
    sections = _mapping(frontend.get("sections"))
    broker_section = _mapping(sections.get("broker"))
    if not broker_section:
        return {"status": "PASS", "reason": "frontend_payload_not_provided"}
    snapshot_cert = str(snapshot.get("certification", "")).upper()
    displayed = str(broker_section.get("certification", snapshot_cert)).upper()
    return {"status": "PASS" if displayed == snapshot_cert else "FAIL", "snapshot_certification": snapshot_cert, "displayed_certification": displayed}


def _operational_acceptance_consistency(snapshot: Mapping[str, Any]) -> dict[str, Any]:
    cert = str(snapshot.get("certification", "RED")).upper()
    state = "GO_READ_ONLY" if cert in {"GREEN", "AMBER"} else "NO_GO"
    return {"status": "PASS", "operational_acceptance": state}


def _go_no_go_consistency(snapshot: Mapping[str, Any]) -> dict[str, Any]:
    blocked = snapshot.get("execution_allowed") is False and snapshot.get("live_trading_blocked") is True
    return {"status": "PASS" if blocked else "FAIL", "go_no_go": "CONDITIONAL_GO_READ_ONLY" if blocked else "NO_GO"}


def _status_score(value: str) -> float:
    status = str(value).upper()
    if status in {"GREEN", "PASS", "OK", "READY", "OPERATIONAL", "AMBER"}:
        return 100.0 if status != "AMBER" else 75.0
    return 20.0


def _score_status(score: float) -> str:
    if score >= 85.0:
        return "GREEN"
    if score >= 70.0:
        return "AMBER"
    return "RED"


def _bounded(value: float) -> float:
    return round(max(0.0, min(100.0, float(value))), 2)


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _string_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value]
    if value in (None, ""):
        return []
    return [str(value)]


def _number(value: Any) -> float:
    try:
        if value is None:
            return 0.0
        result = float(value)
        return 0.0 if math.isnan(result) or math.isinf(result) else result
    except (TypeError, ValueError):
        return 0.0


def _nullable_number(value: Any) -> float | None:
    if value in (None, ""):
        return None
    return _number(value)


def _int(value: Any) -> int:
    try:
        return int(float(value or 0))
    except (TypeError, ValueError):
        return 0


def _memory_value(value: Any) -> float | None:
    data = _mapping(value)
    for key in ("rss_kb", "rss_mb", "working_set_bytes"):
        if key in data:
            return _number(data.get(key))
    return None


def _parse_timestamp(value: Any) -> float | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).timestamp()
    except Exception:
        return None


def _iso(epoch: float) -> str:
    return datetime.fromtimestamp(float(epoch), tz=timezone.utc).isoformat()


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
    "build_operational_proving_report",
    "certification_history_trend",
    "load_certification_history",
    "operational_scorecard",
    "persist_certification_snapshot",
    "pre_pilot_gate",
]
