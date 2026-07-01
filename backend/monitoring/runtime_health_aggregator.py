from __future__ import annotations

from collections.abc import Mapping
from typing import Any


class RuntimeHealthAggregatorError(RuntimeError):
    """Fail-closed exception for runtime health aggregation."""


class RuntimeHealthAggregator:
    """Combine operational telemetry into one canonical runtime health package."""

    ORDER = {"GREEN": 0, "AMBER": 1, "RED": 2}

    def aggregate(
        self,
        performance: Mapping[str, Any] | None,
        session_validation: Mapping[str, Any] | None,
        supervisor_status: Mapping[str, Any] | None = None,
        portfolio_decision: Mapping[str, Any] | None = None,
        runtime_portfolio_state: Mapping[str, Any] | None = None,
        artifact_freshness: Mapping[str, Any] | None = None,
        session_continuity: Mapping[str, Any] | None = None,
        canonical_artifacts: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        if not isinstance(performance, Mapping):
            return self._unavailable("performance_unavailable")
        if not isinstance(session_validation, Mapping):
            return self._unavailable("session_validation_unavailable")

        if isinstance(canonical_artifacts, Mapping):
            portfolio_decision = portfolio_decision or self._canonical_payload(canonical_artifacts, "portfolio_decision")
            runtime_portfolio_state = runtime_portfolio_state or self._canonical_payload(canonical_artifacts, "runtime_portfolio_state")
            artifact_freshness = artifact_freshness or self._canonical_payload(canonical_artifacts, "artifact_freshness")
            session_continuity = session_continuity or self._canonical_payload(canonical_artifacts, "session_continuity")

        supervisor = supervisor_status if isinstance(supervisor_status, Mapping) else {}
        decision = portfolio_decision if isinstance(portfolio_decision, Mapping) else {}
        portfolio_state = self._portfolio_lifecycle_state(runtime_portfolio_state)
        warnings = self._portfolio_warnings(runtime_portfolio_state)
        artifact = artifact_freshness if isinstance(artifact_freshness, Mapping) else {}
        continuity = session_continuity if isinstance(session_continuity, Mapping) else {}
        artifact_warnings = self._list_values(artifact.get("warnings", []))
        warnings.extend(artifact_warnings)
        warnings.extend(self._list_values(continuity.get("warnings", [])))
        warnings = self._stabilized_warnings(warnings, artifact)
        statuses = [
            str(performance.get("overall_status", "RED")).upper(),
            str(session_validation.get("session_status", "RED")).upper(),
            self._supervisor_health(supervisor),
            str(decision.get("overall_status", "RED" if not decision else "GREEN")).upper(),
        ]
        if portfolio_state == "BROKEN_PIPELINE":
            statuses.append("RED")
        artifact_status = str(artifact.get("freshness_status", "")).upper()
        if artifact_status in {"AMBER", "RED"}:
            statuses.append(artifact_status)
        continuity_status = str(continuity.get("session_continuity_status", "")).upper()
        if continuity_status in {"EXPIRED", "REAUTH_REQUIRED", "UNKNOWN"}:
            statuses.append("RED")
        elif continuity_status == "EXPIRING_SOON":
            statuses.append("AMBER")
        elif [item for item in warnings if item != "no_recent_closed_trades"]:
            statuses.append("AMBER")
        overall = max(statuses, key=lambda item: self.ORDER.get(item, 2))

        recommendation = "Runtime health is acceptable for advisory monitoring."
        if overall == "RED":
            recommendation = "Operational health is red; investigate telemetry before relying on runtime dashboards."
        elif overall == "AMBER":
            recommendation = "Operational health is degraded; continue advisory-only monitoring."

        return {
            "status": "OK",
            "runtime_health": overall,
            "overall_operational_health": overall,
            "performance_status": performance.get("overall_status"),
            "session_status": session_validation.get("session_status"),
            "supervisor_status": supervisor.get("status", "UNKNOWN"),
            "portfolio_decision_status": decision.get("overall_status", "UNKNOWN"),
            "portfolio_lifecycle_state": portfolio_state,
            "artifact_freshness_status": artifact.get("freshness_status", "UNKNOWN"),
            "stale_artifacts": artifact.get("stale_artifacts", []),
            "refreshed_artifacts": artifact.get("refreshed_artifacts", []),
            "ledger_freshness": self._artifact_field(artifact, "closed_trade_ledger", "freshness"),
            "account_state_freshness": self._artifact_field(artifact, "account_state", "freshness"),
            "session_continuity_status": continuity.get("session_continuity_status", "UNKNOWN"),
            "quiet_mode_active": bool(continuity.get("quiet_mode_active", False)),
            "reauth_required": bool(continuity.get("reauth_required", False)),
            "warnings": sorted(set(warnings)),
            "pipeline_latency_ms": performance.get("pipeline_latency_ms"),
            "dashboard_latency_ms": performance.get("dashboard_latency_ms"),
            "cache_hit_rate": performance.get("cache_hit_rate"),
            "heartbeat_age": session_validation.get("heartbeat_age"),
            "restart_count": session_validation.get("restart_count"),
            "recovery_count": session_validation.get("recovery_count"),
            "memory_usage": performance.get("memory_usage"),
            "cpu_usage": performance.get("cpu_usage"),
            "recommendation": recommendation,
            "advisory_only": True,
            "execution_allowed": False,
        }

    @staticmethod
    def _supervisor_health(supervisor: Mapping[str, Any]) -> str:
        status = str(supervisor.get("status", "UNKNOWN")).upper()
        if status in {"RUNNING", "ONLINE", "HEALTHY", "GREEN"}:
            return "GREEN"
        if status in {"STARTING", "RECOVERING", "DEGRADED", "AMBER"}:
            return "AMBER"
        return "RED"

    @staticmethod
    def _portfolio_lifecycle_state(runtime_portfolio_state: Mapping[str, Any] | None) -> str:
        if not isinstance(runtime_portfolio_state, Mapping):
            return "UNKNOWN"
        state = str(runtime_portfolio_state.get("portfolio_state", "")).upper()
        if state in {"NO_PORTFOLIO", "PARTIAL_PORTFOLIO", "ACTIVE_PORTFOLIO", "BROKEN_PIPELINE"}:
            return state
        if str(runtime_portfolio_state.get("status", "")).upper() == "DATA UNAVAILABLE":
            return "BROKEN_PIPELINE"
        return "UNKNOWN"

    @staticmethod
    def _portfolio_warnings(runtime_portfolio_state: Mapping[str, Any] | None) -> list[str]:
        if not isinstance(runtime_portfolio_state, Mapping):
            return []
        warnings: list[str] = []
        staleness = runtime_portfolio_state.get("staleness", {})
        if isinstance(staleness, Mapping):
            account = staleness.get("account_state")
            if isinstance(account, Mapping) and account.get("stale") is True:
                warnings.append("stale_account_state")
        return sorted(set(warnings))

    @staticmethod
    def _unavailable(reason: str) -> dict[str, Any]:
        return {
            "status": "DATA UNAVAILABLE",
            "runtime_health": "RED",
            "overall_operational_health": "RED",
            "performance_status": "RED",
            "session_status": "RED",
            "supervisor_status": "UNKNOWN",
            "portfolio_decision_status": "UNKNOWN",
            "portfolio_lifecycle_state": "BROKEN_PIPELINE",
            "artifact_freshness_status": "UNKNOWN",
            "stale_artifacts": [],
            "refreshed_artifacts": [],
            "ledger_freshness": "UNKNOWN",
            "account_state_freshness": "UNKNOWN",
            "session_continuity_status": "UNKNOWN",
            "quiet_mode_active": False,
            "reauth_required": False,
            "warnings": [reason],
            "pipeline_latency_ms": None,
            "dashboard_latency_ms": None,
            "cache_hit_rate": 0.0,
            "heartbeat_age": None,
            "restart_count": 0,
            "recovery_count": 0,
            "memory_usage": None,
            "cpu_usage": None,
            "recommendation": f"Runtime health unavailable: {reason}.",
            "advisory_only": True,
            "execution_allowed": False,
        }

    @staticmethod
    def _artifact_field(artifact_freshness: Mapping[str, Any], artifact_name: str, field: str) -> Any:
        artifacts = artifact_freshness.get("artifacts", {})
        if not isinstance(artifacts, Mapping):
            return "UNKNOWN"
        artifact = artifacts.get(artifact_name, {})
        if not isinstance(artifact, Mapping):
            return "UNKNOWN"
        return artifact.get(field, "UNKNOWN")

    @staticmethod
    def _list_values(values: Any) -> list[str]:
        if isinstance(values, str):
            return [values]
        if isinstance(values, list):
            return [str(item) for item in values if str(item).strip()]
        return []

    @classmethod
    def _stabilized_warnings(cls, warnings: list[str], artifact_freshness: Mapping[str, Any]) -> list[str]:
        artifacts = artifact_freshness.get("artifacts", {}) if isinstance(artifact_freshness, Mapping) else {}
        artifacts = artifacts if isinstance(artifacts, Mapping) else {}
        optional_names = {
            "closed_trade_ledger",
            "portfolio_snapshot",
            "runtime_portfolio_state",
            "portfolio_state",
            "runtime_advisory_snapshot",
            "portfolio_decision",
            "validation_summary",
        }
        result: list[str] = []
        for warning in warnings:
            if warning == "stale_account_state" and cls._artifact_status(artifacts, "account_state") in {"FRESH", "AGING"}:
                continue
            if warning.startswith("missing_"):
                name = warning.removeprefix("missing_")
                if name in optional_names and cls._artifact_exists(artifacts, name):
                    continue
            result.append(warning)
        return result

    @staticmethod
    def _artifact_status(artifacts: Mapping[str, Any], name: str) -> str:
        payload = artifacts.get(name)
        if not isinstance(payload, Mapping):
            return "UNKNOWN"
        return str(payload.get("status", payload.get("freshness", "UNKNOWN"))).upper()

    @staticmethod
    def _artifact_exists(artifacts: Mapping[str, Any], name: str) -> bool:
        payload = artifacts.get(name)
        return isinstance(payload, Mapping) and payload.get("exists") is True and str(payload.get("status", payload.get("freshness", ""))).upper() != "MISSING"

    @staticmethod
    def _canonical_payload(payloads: Mapping[str, Any], name: str) -> Mapping[str, Any] | None:
        payload = payloads.get(name)
        if isinstance(payload, Mapping):
            return payload
        artifacts = payloads.get("artifacts")
        if isinstance(artifacts, Mapping):
            payload = artifacts.get(name)
            if isinstance(payload, Mapping):
                return payload
        return None
