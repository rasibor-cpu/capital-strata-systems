from __future__ import annotations

from typing import Any, Mapping


class BrokerPerformanceIntelligenceError(ValueError):
    """Fail-closed exception for broker performance intelligence inputs."""


class BrokerPerformanceIntelligenceEngine:
    """Advisory-only broker performance scoring with no execution authority."""

    def score_broker(
        self,
        broker_snapshot: Mapping[str, Any],
        *,
        execution_metrics: Mapping[str, Any] | None = None,
        operational_status: Mapping[str, Any] | None = None,
        credential_diagnostics: Mapping[str, Any] | None = None,
        broker_readiness: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        if not isinstance(broker_snapshot, Mapping):
            raise BrokerPerformanceIntelligenceError("broker_snapshot must be a Mapping")

        metrics = _mapping(execution_metrics)
        operational = _mapping(operational_status)
        credentials = _mapping(credential_diagnostics)
        readiness = _mapping(broker_readiness)

        broker_id = _normalized_broker_id(
            broker_snapshot.get("broker_id")
            or broker_snapshot.get("selected_broker")
            or broker_snapshot.get("broker")
            or operational.get("broker")
            or credentials.get("broker")
            or "UNKNOWN"
        )
        broker_name = str(
            broker_snapshot.get("broker_name")
            or broker_snapshot.get("label")
            or credentials.get("broker_name")
            or broker_id
        ).strip() or broker_id

        factors = {
            "execution_quality": _score_explicit_or_cost(
                metrics.get("execution_quality_score"),
                positive_default=70.0,
                slippage_bps=metrics.get("avg_slippage_bps", metrics.get("slippage_bps")),
                spread_bps=metrics.get("avg_spread_bps", metrics.get("spread_bps")),
            ),
            "rejection_error_frequency": _score_reliability_events(
                metrics.get("rejection_rate"),
                metrics.get("error_rate"),
                metrics.get("rejection_count"),
                metrics.get("error_count"),
                metrics.get("total_orders"),
            ),
            "latency_responsiveness": _score_latency(
                metrics.get("latency_ms", operational.get("latency_ms", broker_snapshot.get("latency_ms")))
            ),
            "data_availability": _score_data_availability(operational, broker_snapshot),
            "operational_readiness": _score_operational_readiness(operational, readiness, broker_snapshot, credentials),
            "recent_reliability_trend": _score_trend(
                broker_snapshot.get("recent_reliability_trend")
                or metrics.get("recent_reliability_trend")
                or operational.get("operational_state")
            ),
            "paper_live_mode_suitability": _score_mode_suitability(broker_snapshot, readiness),
        }

        blockers = _blockers(broker_snapshot, operational, credentials, readiness)
        score = round(sum(factors.values()) / len(factors), 4)
        if blockers:
            score = min(score, 39.0)
        status = _status_for_score(score)

        strengths = _strengths(factors, broker_snapshot, operational, readiness)
        weaknesses = _weaknesses(factors, blockers)
        recommended_use = _recommended_use(status, broker_snapshot)

        return {
            "broker_id": broker_id,
            "broker_name": broker_name,
            "overall_score": score,
            "status": status,
            "strengths": strengths,
            "weaknesses": weaknesses,
            "recommended_use": recommended_use,
            "blockers": blockers,
            "explanation": _explanation(broker_name, status, score, blockers),
            "factor_scores": {key: round(value, 4) for key, value in sorted(factors.items())},
            "advisory_only": True,
            "execution_allowed": False,
            "live_trading_enabled": False,
        }


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _normalized_broker_id(value: Any) -> str:
    return str(value or "UNKNOWN").strip().upper() or "UNKNOWN"


def _score_explicit_or_cost(
    explicit_score: Any,
    *,
    positive_default: float,
    slippage_bps: Any,
    spread_bps: Any,
) -> float:
    if explicit_score is not None:
        return _bounded_score(explicit_score)
    score = positive_default
    slippage = _float_or_none(slippage_bps)
    spread = _float_or_none(spread_bps)
    if slippage is not None:
        if slippage <= 2.0:
            score += 10.0
        elif slippage <= 10.0:
            score -= 8.0
        elif slippage <= 25.0:
            score -= 22.0
        else:
            score -= 38.0
    if spread is not None:
        if spread <= 2.0:
            score += 8.0
        elif spread <= 10.0:
            score -= 8.0
        elif spread <= 25.0:
            score -= 20.0
        else:
            score -= 35.0
    return _bounded_score(score)


def _score_reliability_events(
    rejection_rate: Any,
    error_rate: Any,
    rejection_count: Any,
    error_count: Any,
    total_orders: Any,
) -> float:
    rates = [_float_or_none(rejection_rate), _float_or_none(error_rate)]
    if all(rate is None for rate in rates):
        orders = _float_or_none(total_orders)
        rejects = _float_or_none(rejection_count) or 0.0
        errors = _float_or_none(error_count) or 0.0
        if orders and orders > 0:
            combined = (rejects + errors) / orders
        elif rejects + errors > 0:
            combined = 0.25
        else:
            combined = 0.0
    else:
        combined = sum(rate or 0.0 for rate in rates)
    if combined > 1.0:
        combined = combined / 100.0
    return _bounded_score(100.0 - (combined * 400.0))


def _score_latency(value: Any) -> float:
    latency = _float_or_none(value)
    if latency is None:
        return 55.0
    if latency <= 50.0:
        return 100.0
    if latency <= 150.0:
        return 85.0
    if latency <= 350.0:
        return 68.0
    if latency <= 750.0:
        return 42.0
    return 20.0


def _score_data_availability(operational: Mapping[str, Any], snapshot: Mapping[str, Any]) -> float:
    checks = (
        _is_ok(operational.get("market_data_status") or snapshot.get("market_data_status")),
        _is_ok(operational.get("balance_status") or snapshot.get("balance_position_status")),
        _positive_int(operational.get("product_count") or snapshot.get("products_loaded")),
        _is_ok(operational.get("account_sync_status") or snapshot.get("account_readiness")),
    )
    return round((sum(1 for item in checks if item) / len(checks)) * 100.0, 4)


def _score_operational_readiness(
    operational: Mapping[str, Any],
    readiness: Mapping[str, Any],
    snapshot: Mapping[str, Any],
    credentials: Mapping[str, Any],
) -> float:
    if _has_blocking_state(operational, readiness, snapshot, credentials):
        return 20.0
    score = 55.0
    if _truthy(snapshot.get("connected") or snapshot.get("broker_connected") or readiness.get("connected")):
        score += 15.0
    if _truthy(snapshot.get("authenticated") or snapshot.get("broker_authenticated") or readiness.get("authenticated")):
        score += 15.0
    if _truthy(snapshot.get("broker_ready") or readiness.get("broker_ready")):
        score += 10.0
    if str(snapshot.get("readiness_status", "")).upper() in {"READY", "BROKER_READY", "OPERATIONAL"}:
        score += 10.0
    if _is_ok(operational.get("operational_state")):
        score += 5.0
    return _bounded_score(score)


def _score_trend(value: Any) -> float:
    trend = str(value or "UNKNOWN").strip().upper()
    if trend in {"IMPROVING", "STABLE", "OPERATIONAL", "HEALTHY", "GREEN"}:
        return 88.0
    if trend in {"FLAT", "UNKNOWN", "PENDING", "WATCH"}:
        return 58.0
    if trend in {"DEGRADING", "DEGRADED", "AMBER", "WARNING"}:
        return 38.0
    if trend in {"FAILING", "FAILED", "RED", "BLOCKED", "DOWN"}:
        return 10.0
    return 58.0


def _score_mode_suitability(snapshot: Mapping[str, Any], readiness: Mapping[str, Any]) -> float:
    mode = str(snapshot.get("broker_mode", snapshot.get("mode", "paper")) or "paper").strip().lower()
    live_enabled = _truthy(snapshot.get("live_trading_enabled") or snapshot.get("can_live_execute"))
    execution_supported = _truthy(snapshot.get("execution_supported", readiness.get("execution_supported")))
    broker_ready = _truthy(snapshot.get("broker_ready", readiness.get("broker_ready")))
    if mode == "live":
        if live_enabled:
            return 45.0
        return 25.0
    if broker_ready or execution_supported or str(snapshot.get("readiness_status", "")).upper() in {"READY", "BROKER_READY", "OPERATIONAL"}:
        return 85.0
    return 68.0


def _blockers(
    snapshot: Mapping[str, Any],
    operational: Mapping[str, Any],
    credentials: Mapping[str, Any],
    readiness: Mapping[str, Any],
) -> list[str]:
    blockers: list[str] = []
    if _truthy(snapshot.get("missing_credentials")) or credentials.get("readiness_status") == "BLOCKED":
        blockers.append("Broker credentials are missing or blocked")
    if str(operational.get("operational_state", "")).upper() in {"FAILED", "BLOCKED", "DOWN"}:
        blockers.append("Broker operational state is blocked")
    if str(operational.get("failure_reason", "NONE")).upper() not in {"", "NONE", "PENDING"}:
        blockers.append(f"Broker failure reason: {str(operational.get('failure_reason')).upper()}")
    if _truthy(snapshot.get("live_trading_enabled")) or _truthy(snapshot.get("can_live_execute")):
        blockers.append("Live execution authority remains outside this advisory framework")
    if str(readiness.get("readiness_status", "")).upper() in {"BLOCKED", "FAILED", "BROKER_BLOCKED"}:
        blockers.append("Broker readiness is blocked")
    return sorted(dict.fromkeys(blockers))


def _strengths(
    factors: Mapping[str, float],
    snapshot: Mapping[str, Any],
    operational: Mapping[str, Any],
    readiness: Mapping[str, Any],
) -> list[str]:
    labels = {
        "execution_quality": "Strong execution quality",
        "rejection_error_frequency": "Low rejection and error frequency",
        "latency_responsiveness": "Responsive broker latency",
        "data_availability": "Broker data is available",
        "operational_readiness": "Operational readiness signals are healthy",
        "recent_reliability_trend": "Recent reliability trend is stable",
        "paper_live_mode_suitability": "Suitable for paper-mode evaluation",
    }
    strengths = [labels[key] for key, value in factors.items() if value >= 80.0]
    if _truthy(snapshot.get("connected") or readiness.get("connected")):
        strengths.append("Broker connection reported")
    if _is_ok(operational.get("operational_state")):
        strengths.append("Operational state reported as healthy")
    return sorted(dict.fromkeys(strengths))


def _weaknesses(factors: Mapping[str, float], blockers: list[str]) -> list[str]:
    labels = {
        "execution_quality": "Execution quality needs review",
        "rejection_error_frequency": "Reject/error frequency is elevated",
        "latency_responsiveness": "Broker latency is degraded",
        "data_availability": "Broker data availability is incomplete",
        "operational_readiness": "Operational readiness is incomplete",
        "recent_reliability_trend": "Recent reliability trend is weak",
        "paper_live_mode_suitability": "Live-mode suitability is constrained",
    }
    weaknesses = [labels[key] for key, value in factors.items() if value < 60.0]
    weaknesses.extend(blockers)
    return sorted(dict.fromkeys(weaknesses))


def _recommended_use(status: str, snapshot: Mapping[str, Any]) -> str:
    mode = str(snapshot.get("broker_mode", "paper") or "paper").strip().lower()
    if status == "GREEN":
        return "PAPER_PRIMARY" if mode != "live" else "PAPER_REVIEW_BEFORE_LIVE"
    if status == "AMBER":
        return "MONITOR_ONLY"
    return "DO_NOT_USE_FOR_LIVE"


def _explanation(name: str, status: str, score: float, blockers: list[str]) -> str:
    base = f"{name} broker intelligence status is {status} with score {score:.1f}."
    if blockers:
        return f"{base} Blockers keep this advisory output from implying live execution readiness."
    return f"{base} Output is advisory-only and does not authorize live trading."


def _status_for_score(score: float) -> str:
    if score >= 75.0:
        return "GREEN"
    if score >= 45.0:
        return "AMBER"
    return "RED"


def _has_blocking_state(*sources: Mapping[str, Any]) -> bool:
    text = " ".join(str(value).upper() for source in sources for value in source.values())
    return any(marker in text for marker in ("BLOCKED", "FAILED", "NO GO", "MISSING_CREDENTIALS"))


def _truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    return str(value or "").strip().lower() in {"1", "true", "yes", "y", "on", "enabled", "ready", "pass", "ok", "connected", "present"}


def _is_ok(value: Any) -> bool:
    return str(value or "").strip().upper() in {"OK", "READY", "PASS", "AVAILABLE", "OPERATIONAL", "HEALTHY", "CONNECTED", "AUTHENTICATED"}


def _positive_int(value: Any) -> bool:
    try:
        return int(value or 0) > 0
    except (TypeError, ValueError):
        return False


def _float_or_none(value: Any) -> float | None:
    try:
        if value is None or isinstance(value, bool):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _bounded_score(value: Any) -> float:
    numeric = _float_or_none(value)
    if numeric is None:
        return 0.0
    return round(max(0.0, min(100.0, numeric)), 4)


__all__ = [
    "BrokerPerformanceIntelligenceEngine",
    "BrokerPerformanceIntelligenceError",
]
