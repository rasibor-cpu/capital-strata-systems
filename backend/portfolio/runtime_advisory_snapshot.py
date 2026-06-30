from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping


class RuntimeAdvisorySnapshotError(RuntimeError):
    """Fail-closed exception for runtime advisory snapshots."""


class RuntimeAdvisorySnapshot:
    """Build a canonical advisory snapshot from runtime state and components."""

    REQUIRED_COMPONENTS = (
        "portfolio_intelligence",
        "capital_rotation",
        "adaptive_portfolio",
        "strategy_attribution",
        "regime_allocation",
        "risk_committee",
        "quantitative_metrics",
        "market_regime_intelligence",
        "policy_profile",
        "recommendation_tracker",
    )

    def build(
        self,
        *,
        runtime_state: Mapping[str, Any] | None,
        advisory_components: Mapping[str, Any] | None,
        portfolio_decision: Mapping[str, Any] | None = None,
        timestamp: str | None = None,
    ) -> dict[str, Any]:
        runtime_status = self._status(runtime_state)
        components = advisory_components if isinstance(advisory_components, Mapping) else {}
        component_statuses: dict[str, str] = {}
        available: list[str] = []
        limited: list[str] = []
        missing: list[str] = []
        for name in self.REQUIRED_COMPONENTS:
            status = self._status(components.get(name))
            component_statuses[name] = status
            if status == "OK":
                available.append(name)
            elif status == "LIMITED":
                available.append(name)
                limited.append(name)
            else:
                missing.append(name)

        decision_status = self._decision_status(portfolio_decision)
        if runtime_status == "DATA UNAVAILABLE" and not available:
            snapshot_status = "DATA UNAVAILABLE"
        elif missing or runtime_status != "OK":
            snapshot_status = "PARTIAL"
        else:
            snapshot_status = "OK"

        return {
            "snapshot_status": snapshot_status,
            "timestamp": timestamp or datetime.now(timezone.utc).isoformat(),
            "runtime_state_status": runtime_status,
            "portfolio_decision_status": decision_status,
            "available_components": sorted(available),
            "limited_components": sorted(limited),
            "missing_components": sorted(missing),
            "component_statuses": component_statuses,
            "missing_input_reasons": self._missing_reasons(runtime_state, components, portfolio_decision),
            "advisory_only": True,
            "execution_allowed": False,
        }

    @staticmethod
    def _status(payload: Mapping[str, Any] | None) -> str:
        if not isinstance(payload, Mapping):
            return "DATA UNAVAILABLE"
        return str(payload.get("status", "OK")).strip().upper() or "DATA UNAVAILABLE"

    @staticmethod
    def _decision_status(portfolio_decision: Mapping[str, Any] | None) -> str:
        if not isinstance(portfolio_decision, Mapping):
            return "DATA UNAVAILABLE"
        return str(portfolio_decision.get("overall_status", portfolio_decision.get("status", "DATA UNAVAILABLE"))).upper()

    @staticmethod
    def _missing_reasons(
        runtime_state: Mapping[str, Any] | None,
        components: Mapping[str, Any],
        portfolio_decision: Mapping[str, Any] | None,
    ) -> list[str]:
        reasons: list[str] = []
        if isinstance(runtime_state, Mapping):
            reasons.extend(str(item) for item in runtime_state.get("reasons", []) if str(item).strip())
        for name, payload in components.items():
            if isinstance(payload, Mapping) and str(payload.get("status", "OK")).upper() == "DATA UNAVAILABLE":
                for key in ("reasons", "explainability", "risk_flags", "concerns"):
                    values = payload.get(key, [])
                    if isinstance(values, str):
                        values = [values]
                    if isinstance(values, list):
                        reasons.extend(f"{name}:{item}" for item in values if str(item).strip())
        if isinstance(portfolio_decision, Mapping):
            reasons.extend(f"portfolio_decision_missing:{item}" for item in portfolio_decision.get("missing_inputs", []))
        return sorted(set(reasons))
