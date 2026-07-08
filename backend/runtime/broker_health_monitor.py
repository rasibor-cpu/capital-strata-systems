from __future__ import annotations

import json
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from backend.runtime.broker_credential_diagnostics import (
    diagnose_broker_credentials,
    diagnostics_payload,
)
from backend.runtime.live_connectivity_certifier import certify_live_connectivity


GREEN = "GREEN"
AMBER = "AMBER"
RED = "RED"
PASS = "PASS"
FAIL = "FAIL"
IMPROVING = "IMPROVING"
STABLE = "STABLE"
DEGRADING = "DEGRADING"
PAYLOAD_VERSION = "css.phase156c.broker_health_monitor.v1"


CredentialDiagnosticsFn = Callable[..., Any]
ConnectivityCertifierFn = Callable[..., Mapping[str, Any]]
ClockFn = Callable[[], float]


@dataclass(frozen=True)
class BrokerHealthThresholds:
    green_score: float = 85.0
    amber_score: float = 60.0
    latency_green_ms: int = 250
    latency_amber_ms: int = 1000
    stale_quote_seconds: int = 120
    drift_quote_seconds: int = 30
    trend_delta: float = 5.0


@dataclass(frozen=True)
class BrokerHealthSample:
    timestamp: float
    health: str
    overall_score: float
    latency_ms: dict[str, int | None]
    success: bool
    api_quality: float


@dataclass
class BrokerHealthHistory:
    samples: list[BrokerHealthSample] = field(default_factory=list)
    reconnect_count: int = 0
    last_state: str = "UNKNOWN"
    last_successful_validation: str = ""


class BrokerHealthMonitor:
    """Continuous advisory broker health monitor.

    The monitor consumes credential diagnostics and Phase 156B connectivity
    certifications. It does not call order, cancel, mutation, arming, or live
    execution paths.
    """

    def __init__(
        self,
        *,
        credential_diagnostics_fn: CredentialDiagnosticsFn = diagnose_broker_credentials,
        connectivity_certifier_fn: ConnectivityCertifierFn = certify_live_connectivity,
        thresholds: BrokerHealthThresholds | None = None,
        clock: ClockFn = time.time,
        max_samples: int = 20,
    ) -> None:
        self.credential_diagnostics_fn = credential_diagnostics_fn
        self.connectivity_certifier_fn = connectivity_certifier_fn
        self.thresholds = thresholds or BrokerHealthThresholds()
        self.clock = clock
        self.max_samples = max(2, int(max_samples))
        self.history_by_broker: dict[str, BrokerHealthHistory] = {}

    def evaluate_broker(self, broker: str, *, mode: str = "live", env: Mapping[str, Any] | None = None) -> dict[str, Any]:
        broker_key = _normalize_broker(broker)
        history = self.history_by_broker.setdefault(broker_key, BrokerHealthHistory())
        now = self.clock()

        diagnostics = self._diagnostics(broker_key, env=env)
        connectivity = self._connectivity(broker_key, mode=mode)
        latency = _latency(connectivity)
        api = _api_health(connectivity, diagnostics)
        freshness = _market_data_freshness(connectivity, now=now, thresholds=self.thresholds)
        firewall = _firewall_status(connectivity)
        reliability = _reliability(connectivity, api)
        latency_health = _latency_health(latency, self.thresholds)
        score = _overall_score(
            diagnostics=diagnostics,
            connectivity=connectivity,
            latency=latency,
            freshness=freshness,
            api=api,
            reliability=reliability,
            firewall=firewall,
            thresholds=self.thresholds,
        )
        health = _health_state(score, firewall, api, freshness, latency_health, self.thresholds)
        success = health != RED and str(connectivity.get("certification", "")).upper() in {GREEN, AMBER}

        if success:
            history.last_successful_validation = _iso_timestamp(now)
        if history.last_state in {RED, "FAILED", "DOWN"} and health in {GREEN, AMBER}:
            history.reconnect_count += 1
        history.last_state = health

        sample = BrokerHealthSample(
            timestamp=now,
            health=health,
            overall_score=score,
            latency_ms=latency,
            success=success,
            api_quality=float(api["score"]),
        )
        history.samples.append(sample)
        del history.samples[:-self.max_samples]

        rolling = _rolling(history.samples)
        trend = _trend(history.samples, self.thresholds)
        blockers = _blockers(diagnostics, connectivity, api, freshness, firewall)
        integration = _integration_payload(
            broker=broker_key,
            health=health,
            score=score,
            diagnostics=diagnostics,
            connectivity=connectivity,
            latency=latency,
            rolling=rolling,
            trend=trend,
            blockers=blockers,
        )

        report = {
            "payload_version": PAYLOAD_VERSION,
            "broker": broker_key.upper() if broker_key else "NONE",
            "mode": mode,
            "health": health,
            "overall_score": score,
            "overall_health_score": score,
            "latency": {
                "authentication_ms": latency.get("authentication_ms"),
                "account_ms": latency.get("account_ms"),
                "market_ms": latency.get("market_data_ms"),
            },
            "availability": rolling["availability"],
            "reliability": rolling["reliability"],
            "trend": trend,
            "firewall": firewall["status"],
            "execution_allowed": False,
            "live_trading_blocked": True,
            "broker_execution_armed": False,
            "advisory_only": True,
            "credential_status": diagnostics.get("readiness_status", "UNKNOWN"),
            "authentication_status": connectivity.get("authentication", FAIL),
            "connectivity_status": connectivity.get("certification", RED),
            "market_data_freshness": freshness,
            "api_health": api,
            "latency_health": latency_health,
            "rolling_latency": rolling["latency"],
            "rolling_availability": rolling["availability"],
            "rolling_reliability": rolling["reliability"],
            "rolling_api_quality": rolling["api_quality"],
            "reconnect_count": history.reconnect_count,
            "last_successful_validation": history.last_successful_validation,
            "blocker_reasons": blockers,
            "integration_payloads": integration,
        }
        return _json_safe(report)

    def evaluate_all(
        self,
        brokers: Sequence[str],
        *,
        mode: str = "live",
        env: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        reports = [self.evaluate_broker(broker, mode=mode, env=env) for broker in brokers]
        worst = RED if any(item["health"] == RED for item in reports) else AMBER if any(item["health"] == AMBER for item in reports) else GREEN
        return _json_safe(
            {
                "payload_version": PAYLOAD_VERSION,
                "health": worst,
                "broker_count": len(reports),
                "brokers": reports,
                "execution_allowed": False,
                "live_trading_blocked": True,
                "broker_execution_armed": False,
                "advisory_only": True,
            }
        )

    def to_json(self, broker: str, *, mode: str = "live", indent: int = 2) -> str:
        return json.dumps(self.evaluate_broker(broker, mode=mode), indent=indent, sort_keys=True)

    def write_json_report(self, broker: str, path: str | Path, *, mode: str = "live", indent: int = 2) -> dict[str, Any]:
        report = self.evaluate_broker(broker, mode=mode)
        write_broker_health_report(report, path, indent=indent)
        return report

    def _diagnostics(self, broker: str, *, env: Mapping[str, Any] | None) -> dict[str, Any]:
        try:
            return diagnostics_payload(self.credential_diagnostics_fn(broker, env=env))
        except Exception as exc:
            return {
                "broker": broker,
                "credentials_present": False,
                "readiness_status": "BLOCKED",
                "failure_reason": _failure_reason(exc),
                "canonical_failure_reason": _failure_reason(exc),
                "execution_allowed": False,
                "live_trading_blocked": True,
                "advisory_only": True,
            }

    def _connectivity(self, broker: str, *, mode: str) -> dict[str, Any]:
        try:
            report = self.connectivity_certifier_fn(broker, mode=mode)
            return dict(report) if isinstance(report, Mapping) else {}
        except Exception as exc:
            reason = _failure_reason(exc)
            return {
                "broker": broker.upper(),
                "certification": RED,
                "authentication": FAIL,
                "account": FAIL,
                "market_data": FAIL,
                "latency": {
                    "authentication_ms": None,
                    "account_ms": None,
                    "market_data_ms": None,
                    "overall_ms": None,
                },
                "execution_allowed": False,
                "live_trading_blocked": True,
                "broker_execution_armed": False,
                "advisory_only": True,
                "blocker_reasons": [f"connectivity_exception:{reason}"],
            }


def monitor_broker_health(
    broker: str,
    *,
    mode: str = "live",
    credential_diagnostics_fn: CredentialDiagnosticsFn = diagnose_broker_credentials,
    connectivity_certifier_fn: ConnectivityCertifierFn = certify_live_connectivity,
    thresholds: BrokerHealthThresholds | None = None,
) -> dict[str, Any]:
    return BrokerHealthMonitor(
        credential_diagnostics_fn=credential_diagnostics_fn,
        connectivity_certifier_fn=connectivity_certifier_fn,
        thresholds=thresholds,
    ).evaluate_broker(broker, mode=mode)


def broker_health_json(report: Mapping[str, Any], *, indent: int = 2) -> str:
    return json.dumps(_json_safe(report), indent=indent, sort_keys=True)


def write_broker_health_report(report: Mapping[str, Any], path: str | Path, *, indent: int = 2) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(broker_health_json(report, indent=indent), encoding="utf-8")


def _latency(connectivity: Mapping[str, Any]) -> dict[str, int | None]:
    source = connectivity.get("latency") if isinstance(connectivity.get("latency"), Mapping) else {}
    return {
        "authentication_ms": _int_or_none(source.get("authentication_ms")),
        "account_ms": _int_or_none(source.get("account_ms")),
        "market_data_ms": _int_or_none(source.get("market_data_ms", source.get("market_ms"))),
        "overall_ms": _int_or_none(source.get("overall_ms")),
    }


def _api_health(connectivity: Mapping[str, Any], diagnostics: Mapping[str, Any]) -> dict[str, Any]:
    reasons = [str(item).upper() for item in connectivity.get("blocker_reasons", [])]
    diagnostic_reason = str(diagnostics.get("canonical_failure_reason") or diagnostics.get("failure_reason") or "NONE").upper()
    if diagnostic_reason and diagnostic_reason != "NONE":
        reasons.append(diagnostic_reason)
    reason_text = " ".join(reasons)
    detected = []
    for reason in ("TIMEOUT", "NETWORK_ERROR", "DNS_ERROR", "TLS_ERROR", "RATE_LIMIT", "BROKER_UNAVAILABLE", "CLOCK_SKEW", "AUTH_FAILED"):
        if reason in reason_text:
            detected.append(reason)
    if any(reason in detected for reason in ("DNS_ERROR", "TLS_ERROR", "BROKER_UNAVAILABLE", "CLOCK_SKEW", "AUTH_FAILED")):
        status = RED
        score = 20.0
    elif any(reason in detected for reason in ("TIMEOUT", "NETWORK_ERROR", "RATE_LIMIT")):
        status = AMBER
        score = 55.0
    elif str(connectivity.get("certification", "")).upper() == RED:
        status = RED
        score = 35.0
    else:
        status = GREEN
        score = 100.0
    return {
        "status": status,
        "score": score,
        "failure_reasons": sorted(dict.fromkeys(detected)),
    }


def _market_data_freshness(connectivity: Mapping[str, Any], *, now: float, thresholds: BrokerHealthThresholds) -> dict[str, Any]:
    stage = connectivity.get("stage_results") if isinstance(connectivity.get("stage_results"), Mapping) else {}
    market = stage.get("market_data") if isinstance(stage.get("market_data"), Mapping) else {}
    details = market.get("details") if isinstance(market.get("details"), Mapping) else {}
    missing = list(details.get("missing_symbols", [])) if isinstance(details.get("missing_symbols", []), list) else []
    timestamp = str(details.get("timestamp", "") or "")
    if not timestamp and isinstance(details.get("evidence"), Sequence):
        timestamp = _first_evidence_timestamp(details.get("evidence", ()))
    age = _timestamp_age_seconds(timestamp, now)
    drift = abs(age) if age is not None else None
    stale = age is not None and age > thresholds.stale_quote_seconds
    drifted = drift is not None and drift > thresholds.drift_quote_seconds and age < 0
    if missing:
        status = RED
        reason = "missing_quotes"
    elif stale:
        status = RED
        reason = "stale_quotes"
    elif drifted:
        status = AMBER
        reason = "timestamp_drift"
    elif str(connectivity.get("market_data", "")).upper() != PASS:
        status = RED
        reason = "market_data_failed"
    else:
        status = GREEN
        reason = "fresh"
    return {
        "status": status,
        "reason": reason,
        "timestamp": timestamp or "NOT_AVAILABLE",
        "age_seconds": age,
        "missing_quotes": missing,
        "timestamp_drift_seconds": drift,
    }


def _first_evidence_timestamp(evidence: Sequence[Any]) -> str:
    for item in evidence:
        if isinstance(item, Mapping) and item.get("success") is True and item.get("timestamp"):
            return str(item.get("timestamp"))
    return ""


def _firewall_status(connectivity: Mapping[str, Any]) -> dict[str, Any]:
    allowed = bool(connectivity.get("execution_allowed", False))
    blocked = bool(connectivity.get("live_trading_blocked", True))
    armed = bool(connectivity.get("broker_execution_armed", False))
    status = PASS if allowed is False and blocked is True and armed is False else FAIL
    return {
        "status": status,
        "execution_allowed": False,
        "live_trading_blocked": True,
        "broker_execution_armed": False,
        "reported_execution_allowed": allowed,
        "reported_live_trading_blocked": blocked,
        "reported_broker_execution_armed": armed,
    }


def _reliability(connectivity: Mapping[str, Any], api: Mapping[str, Any]) -> dict[str, Any]:
    certification = str(connectivity.get("certification", "")).upper()
    success = certification in {GREEN, AMBER} and str(api.get("status", "")).upper() != RED
    return {
        "success": success,
        "score": 100.0 if success else 0.0,
    }


def _overall_score(
    *,
    diagnostics: Mapping[str, Any],
    connectivity: Mapping[str, Any],
    latency: Mapping[str, int | None],
    freshness: Mapping[str, Any],
    api: Mapping[str, Any],
    reliability: Mapping[str, Any],
    firewall: Mapping[str, Any],
    thresholds: BrokerHealthThresholds,
) -> float:
    credential_score = 100.0 if diagnostics.get("credentials_present") and str(diagnostics.get("readiness_status", "")).upper() != "BLOCKED" else 0.0
    auth_score = 100.0 if str(connectivity.get("authentication", "")).upper() == PASS else 0.0
    connectivity_score = _float_or_default(connectivity.get("connectivity_score"), 0.0)
    latency_score = _latency_score(latency, thresholds)
    freshness_score = {GREEN: 100.0, AMBER: 60.0, RED: 0.0}.get(str(freshness.get("status", RED)).upper(), 0.0)
    api_score = _float_or_default(api.get("score"), 0.0)
    reliability_score = _float_or_default(reliability.get("score"), 0.0)
    firewall_score = 100.0 if firewall.get("status") == PASS else 0.0
    score = (
        credential_score * 0.15
        + auth_score * 0.15
        + connectivity_score * 0.15
        + latency_score * 0.15
        + freshness_score * 0.15
        + api_score * 0.10
        + reliability_score * 0.10
        + firewall_score * 0.05
    )
    if firewall.get("status") != PASS:
        score = min(score, 39.0)
    return round(max(0.0, min(100.0, score)), 2)


def _latency_score(latency: Mapping[str, int | None], thresholds: BrokerHealthThresholds) -> float:
    values = [value for key, value in latency.items() if key != "overall_ms" and isinstance(value, int)]
    if not values:
        return 0.0
    worst = max(values)
    if worst <= thresholds.latency_green_ms:
        return 100.0
    if worst <= thresholds.latency_amber_ms:
        return 65.0
    return 20.0


def _latency_health(latency: Mapping[str, int | None], thresholds: BrokerHealthThresholds) -> str:
    values = [value for key, value in latency.items() if key != "overall_ms" and isinstance(value, int)]
    if not values:
        return RED
    worst = max(values)
    if worst > thresholds.latency_amber_ms:
        return RED
    if worst > thresholds.latency_green_ms:
        return AMBER
    return GREEN


def _health_state(
    score: float,
    firewall: Mapping[str, Any],
    api: Mapping[str, Any],
    freshness: Mapping[str, Any],
    latency_health: str,
    thresholds: BrokerHealthThresholds,
) -> str:
    if firewall.get("status") != PASS:
        return RED
    if str(api.get("status", "")).upper() == RED or str(freshness.get("status", "")).upper() == RED or latency_health == RED:
        return RED
    if latency_health == AMBER and score >= thresholds.amber_score:
        return AMBER
    if score >= thresholds.green_score:
        return GREEN
    if score >= thresholds.amber_score:
        return AMBER
    return RED


def _rolling(samples: Sequence[BrokerHealthSample]) -> dict[str, Any]:
    if not samples:
        return {
            "availability": 0.0,
            "reliability": 0.0,
            "api_quality": 0.0,
            "latency": {"authentication_ms": None, "account_ms": None, "market_ms": None},
        }
    count = len(samples)
    successes = sum(1 for sample in samples if sample.success)
    latency = {
        "authentication_ms": _average(sample.latency_ms.get("authentication_ms") for sample in samples),
        "account_ms": _average(sample.latency_ms.get("account_ms") for sample in samples),
        "market_ms": _average(sample.latency_ms.get("market_data_ms") for sample in samples),
    }
    api_quality = _average(sample.api_quality for sample in samples) or 0.0
    availability = round((successes / count) * 100.0, 2)
    return {
        "availability": availability,
        "reliability": availability,
        "api_quality": round(api_quality, 2),
        "latency": latency,
    }


def _trend(samples: Sequence[BrokerHealthSample], thresholds: BrokerHealthThresholds) -> str:
    if len(samples) < 2:
        return STABLE
    first = samples[0].overall_score
    last = samples[-1].overall_score
    delta = last - first
    if delta >= thresholds.trend_delta:
        return IMPROVING
    if delta <= -thresholds.trend_delta:
        return DEGRADING
    return STABLE


def _blockers(
    diagnostics: Mapping[str, Any],
    connectivity: Mapping[str, Any],
    api: Mapping[str, Any],
    freshness: Mapping[str, Any],
    firewall: Mapping[str, Any],
) -> list[str]:
    blockers: list[str] = []
    if not diagnostics.get("credentials_present"):
        blockers.append("credentials_unavailable")
    if str(connectivity.get("certification", "")).upper() == RED:
        blockers.append("connectivity_certification_red")
    blockers.extend(str(item) for item in connectivity.get("blocker_reasons", []))
    blockers.extend(str(item) for item in api.get("failure_reasons", []))
    if str(freshness.get("status", "")).upper() != GREEN:
        blockers.append(str(freshness.get("reason", "market_data_freshness_failed")))
    if firewall.get("status") != PASS:
        blockers.append("firewall_integrity_failed")
    return sorted(dict.fromkeys(blockers))


def _integration_payload(
    *,
    broker: str,
    health: str,
    score: float,
    diagnostics: Mapping[str, Any],
    connectivity: Mapping[str, Any],
    latency: Mapping[str, int | None],
    rolling: Mapping[str, Any],
    trend: str,
    blockers: list[str],
) -> dict[str, Any]:
    broker_name = broker.upper() if broker else "NONE"
    broker_performance = {
        "broker": broker_name,
        "broker_id": broker_name,
        "overall_score": score,
        "status": health,
        "latency_ms": latency.get("overall_ms") or latency.get("market_data_ms"),
        "recent_reliability_trend": trend,
        "advisory_only": True,
        "execution_allowed": False,
    }
    decision_confidence = {
        "broker_performance": broker_performance,
        "broker_diagnostics": dict(diagnostics),
        "runtime_health": {"engine_mode": "READY" if health != RED else "BLOCKED"},
        "live_readiness_constraints": {
            "can_live_execute": False,
            "execution_authority": False,
            "execution_allowed": False,
        },
        "advisory_only": True,
        "execution_allowed": False,
    }
    opportunity_intelligence = {
        "broker_performance": score / 100.0,
        "broker_health": health,
        "broker_reliability": rolling.get("reliability", 0.0),
        "blockers": list(blockers),
        "advisory_only": True,
        "execution_allowed": False,
    }
    dashboard_runtime_status = {
        "broker": broker_name,
        "broker_health": health,
        "overall_health_score": score,
        "connectivity_status": connectivity.get("certification", RED),
        "trend": trend,
        "execution_allowed": False,
        "live_trading_blocked": True,
        "broker_execution_armed": False,
        "advisory_only": True,
    }
    return {
        "broker_performance_intelligence": broker_performance,
        "decision_confidence_framework": decision_confidence,
        "opportunity_intelligence": opportunity_intelligence,
        "dashboard_runtime_status": dashboard_runtime_status,
    }


def _timestamp_age_seconds(timestamp: str, now: float) -> float | None:
    if not timestamp:
        return None
    try:
        normalized = timestamp.strip().replace("Z", "+00:00")
        parsed = datetime.fromisoformat(normalized)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        then = parsed.timestamp()
        return round(now - then, 3)
    except Exception:
        return None


def _iso_timestamp(value: float) -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(value))


def _average(values: Any) -> float | None:
    numeric = [float(value) for value in values if isinstance(value, (int, float))]
    if not numeric:
        return None
    return round(sum(numeric) / len(numeric), 2)


def _int_or_none(value: Any) -> int | None:
    try:
        if value is None or isinstance(value, bool):
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


def _float_or_default(value: Any, default: float) -> float:
    try:
        if value is None or isinstance(value, bool):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _failure_reason(exc: BaseException) -> str:
    text = f"{exc.__class__.__name__} {exc}".lower()
    if "dns" in text or "name resolution" in text:
        return "DNS_ERROR"
    if "tls" in text or "ssl" in text or "certificate" in text:
        return "TLS_ERROR"
    if "rate" in text and "limit" in text:
        return "RATE_LIMIT"
    if "timeout" in text or "timed out" in text:
        return "TIMEOUT"
    if "unavailable" in text or "503" in text:
        return "BROKER_UNAVAILABLE"
    if "clock" in text or "skew" in text:
        return "CLOCK_SKEW"
    if "network" in text or "connection" in text:
        return "NETWORK_ERROR"
    if "auth" in text or "401" in text:
        return "AUTH_FAILED"
    return "UNKNOWN_ERROR"


def _normalize_broker(broker: str) -> str:
    return str(broker or "").strip().lower()


def _json_safe(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(item) for item in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


__all__ = [
    "AMBER",
    "DEGRADING",
    "GREEN",
    "IMPROVING",
    "PASS",
    "PAYLOAD_VERSION",
    "RED",
    "STABLE",
    "BrokerHealthHistory",
    "BrokerHealthMonitor",
    "BrokerHealthSample",
    "BrokerHealthThresholds",
    "broker_health_json",
    "monitor_broker_health",
    "write_broker_health_report",
]
