from __future__ import annotations

from typing import Any, Mapping


class DecisionConfidenceFrameworkError(ValueError):
    """Fail-closed exception for malformed decision confidence inputs."""


class DecisionConfidenceFramework:
    """Advisory-only confidence evaluator for broker-related decisions."""

    def evaluate_confidence(
        self,
        *,
        broker_readiness: Mapping[str, Any] | None = None,
        broker_diagnostics: Mapping[str, Any] | None = None,
        broker_performance: Mapping[str, Any] | None = None,
        runtime_health: Mapping[str, Any] | None = None,
        trade_gate_context: Mapping[str, Any] | None = None,
        account_context: Mapping[str, Any] | None = None,
        live_readiness_constraints: Mapping[str, Any] | None = None,
        requested_mode: str = "paper",
    ) -> dict[str, Any]:
        readiness = _mapping(broker_readiness)
        diagnostics = _mapping(broker_diagnostics)
        performance = _mapping(broker_performance)
        runtime = _mapping(runtime_health)
        gates = _mapping(trade_gate_context)
        account = _mapping(account_context)
        live_constraints = _mapping(live_readiness_constraints)

        missing_inputs = _missing_inputs(
            readiness=readiness,
            diagnostics=diagnostics,
            performance=performance,
            runtime=runtime,
            gates=gates,
            account=account,
            live_constraints=live_constraints,
        )
        reasons: list[str] = []
        safety_notes = [
            "Advisory-only confidence output; no orders are routed or authorized.",
            "Existing R7 gates, RBAC, broker startup gates, and NO-GO protections remain authoritative.",
        ]

        component_scores = {
            "broker_readiness": _score_readiness(readiness),
            "broker_diagnostics": _score_diagnostics(diagnostics),
            "broker_performance": _score_performance(performance),
            "data_completeness": _score_data_completeness(missing_inputs),
            "runtime_health": _score_runtime_health(runtime),
            "trade_gate_alignment": _score_trade_gate_alignment(gates),
            "account_visibility": _score_account_visibility(account),
            "live_readiness_constraints": _score_live_constraints(live_constraints, requested_mode),
        }

        score = round(sum(component_scores.values()) / len(component_scores), 4)
        blockers = _blockers(
            requested_mode=requested_mode,
            readiness=readiness,
            diagnostics=diagnostics,
            performance=performance,
            runtime=runtime,
            gates=gates,
            account=account,
            live_constraints=live_constraints,
            missing_inputs=missing_inputs,
        )
        if blockers:
            score = min(score, 39.0)
            reasons.extend(blockers)
        if missing_inputs:
            reasons.append(f"Missing advisory inputs: {', '.join(missing_inputs)}")
        reasons.extend(_component_reasons(component_scores))
        reasons = sorted(dict.fromkeys(reasons))

        band = _confidence_band(score, blockers)
        decision = _decision_for_band(band, requested_mode)
        if str(requested_mode or "paper").strip().lower() == "live":
            safety_notes.append("Live trading remains blocked unless separate live-execution authority explicitly approves it.")

        return {
            "confidence_score": score,
            "confidence_band": band,
            "decision": decision,
            "reasons": reasons,
            "missing_inputs": missing_inputs,
            "safety_notes": safety_notes,
            "explanation": _explanation(score, band, decision, requested_mode),
            "component_scores": {key: round(value, 4) for key, value in sorted(component_scores.items())},
            "advisory_only": True,
            "execution_allowed": False,
            "live_trading_enabled": False,
        }


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _missing_inputs(**sources: Mapping[str, Any]) -> list[str]:
    labels = {
        "readiness": "broker_readiness",
        "diagnostics": "broker_diagnostics",
        "performance": "broker_performance",
        "runtime": "runtime_health",
        "gates": "trade_gate_context",
        "account": "account_context",
        "live_constraints": "live_readiness_constraints",
    }
    return sorted(labels.get(name, name) for name, value in sources.items() if not value)


def _score_readiness(value: Mapping[str, Any]) -> float:
    if not value:
        return 35.0
    if _truthy(value.get("broker_ready")) or str(value.get("readiness_status", "")).upper() in {"READY", "OPERATIONAL"}:
        return 90.0
    if str(value.get("readiness_status", "")).upper() in {"BLOCKED", "FAILED", "BROKER_BLOCKED"}:
        return 20.0
    return 60.0


def _score_diagnostics(value: Mapping[str, Any]) -> float:
    if not value:
        return 35.0
    reason = str(value.get("failure_reason", "NONE")).upper()
    if reason == "NONE" and _truthy(value.get("credentials_present", True)):
        return 90.0
    if reason in {"RATE_LIMIT", "TIMEOUT", "NETWORK_ERROR", "BROKER_UNAVAILABLE"}:
        return 45.0
    return 20.0


def _score_performance(value: Mapping[str, Any]) -> float:
    if not value:
        return 35.0
    return _bounded_score(value.get("overall_score"))


def _score_data_completeness(missing_inputs: list[str]) -> float:
    if not missing_inputs:
        return 100.0
    return round(max(0.0, 100.0 - (len(missing_inputs) * 13.0)), 4)


def _score_runtime_health(value: Mapping[str, Any]) -> float:
    if not value:
        return 45.0
    if str(value.get("engine_mode", "")).upper() in {"SAFE", "PAPER", "READY"}:
        return 85.0
    if str(value.get("engine_mode", "")).upper() in {"BLOCKED", "ERROR", "FAILED"}:
        return 20.0
    return 65.0


def _score_trade_gate_alignment(value: Mapping[str, Any]) -> float:
    if not value:
        return 40.0
    gate = str(value.get("gate_status", value.get("unified_trade_gate", "OPEN"))).upper()
    risk = str(value.get("risk_state", "NORMAL")).upper()
    if gate in {"OPEN", "PASS", "READY"} and risk in {"NORMAL", "GREEN", "OK"}:
        return 90.0
    if gate in {"CLOSED", "BLOCKED", "REJECTING", "NO_GO", "NO GO"}:
        return 15.0
    return 55.0


def _score_account_visibility(value: Mapping[str, Any]) -> float:
    if not value:
        return 35.0
    visible = any(value.get(key) not in (None, "", "DATA UNAVAILABLE") for key in ("cash_balance", "total_equity", "buying_power", "balance", "equity"))
    return 85.0 if visible else 45.0


def _score_live_constraints(value: Mapping[str, Any], requested_mode: str) -> float:
    mode = str(requested_mode or "paper").strip().lower()
    if mode != "live":
        return 90.0
    if not value:
        return 15.0
    if _truthy(value.get("can_live_execute") or value.get("execution_authority")):
        return 45.0
    return 15.0


def _blockers(
    *,
    requested_mode: str,
    readiness: Mapping[str, Any],
    diagnostics: Mapping[str, Any],
    performance: Mapping[str, Any],
    runtime: Mapping[str, Any],
    gates: Mapping[str, Any],
    account: Mapping[str, Any],
    live_constraints: Mapping[str, Any],
    missing_inputs: list[str],
) -> list[str]:
    blockers: list[str] = []
    mode = str(requested_mode or "paper").strip().lower()
    if mode == "live":
        blockers.append("Live mode decision cannot be authorized by this advisory framework")
        if not _truthy(live_constraints.get("can_live_execute") or live_constraints.get("execution_authority")):
            blockers.append("Live execution authority is absent or blocked")
    if str(performance.get("status", "")).upper() == "RED":
        blockers.append("Broker performance intelligence is RED")
    if str(diagnostics.get("readiness_status", "")).upper() in {"BLOCKED", "FAILED"}:
        blockers.append("Broker diagnostics are blocked")
    if str(readiness.get("readiness_status", "")).upper() in {"BLOCKED", "FAILED", "BROKER_BLOCKED"}:
        blockers.append("Broker readiness is blocked")
    if str(gates.get("gate_status", "")).upper() in {"CLOSED", "BLOCKED", "REJECTING", "NO_GO", "NO GO"}:
        blockers.append("Trade gate context is closed or blocked")
    if str(runtime.get("engine_mode", "")).upper() in {"BLOCKED", "ERROR", "FAILED"}:
        blockers.append("Runtime health is blocked")
    if mode == "live" and "account" in " ".join(missing_inputs):
        blockers.append("Account visibility is incomplete for live review")
    if not account and mode == "live":
        blockers.append("Account/balance visibility is missing for live review")
    return sorted(dict.fromkeys(blockers))


def _component_reasons(scores: Mapping[str, float]) -> list[str]:
    labels = {
        "broker_readiness": "Broker readiness is weak",
        "broker_diagnostics": "Broker diagnostics need review",
        "broker_performance": "Broker performance score is weak",
        "data_completeness": "Input completeness is limited",
        "runtime_health": "Runtime health is not fully confirmed",
        "trade_gate_alignment": "Trade gate alignment is weak",
        "account_visibility": "Account visibility is limited",
        "live_readiness_constraints": "Live-readiness constraints are not satisfied",
    }
    return [labels[key] for key, value in scores.items() if value < 50.0]


def _confidence_band(score: float, blockers: list[str]) -> str:
    if blockers:
        return "BLOCKED"
    if score >= 75.0:
        return "HIGH"
    if score >= 50.0:
        return "MEDIUM"
    return "LOW"


def _decision_for_band(band: str, requested_mode: str) -> str:
    mode = str(requested_mode or "paper").strip().lower()
    if band == "BLOCKED":
        return "BLOCKED"
    if mode == "live":
        return "DO_NOT_PROCEED_LIVE"
    if band == "HIGH":
        return "PROCEED_PAPER"
    return "MONITOR"


def _explanation(score: float, band: str, decision: str, requested_mode: str) -> str:
    return (
        f"Broker decision confidence is {band} at {score:.1f} for requested {requested_mode.upper()} mode. "
        f"Decision is {decision}; this does not enable live trading."
    )


def _truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    return str(value or "").strip().lower() in {"1", "true", "yes", "y", "on", "enabled", "ready", "pass", "ok", "go"}


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
    "DecisionConfidenceFramework",
    "DecisionConfidenceFrameworkError",
]
