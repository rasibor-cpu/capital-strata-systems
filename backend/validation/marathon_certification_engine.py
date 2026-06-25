from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Mapping


class MarathonCertificationEngineError(RuntimeError):
    """Fail-closed exception for marathon certification."""


@dataclass(frozen=True)
class MarathonCertificationDecision:
    status: str
    go_no_go: str
    warnings: tuple[str, ...]
    failures: tuple[str, ...]
    evidence_used: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class MarathonCertificationEngine:
    def __init__(
        self,
        *,
        minimum_cycles: int = 1,
        minimum_uptime_pct: float = 0.95,
        maximum_alert_rate: float = 0.30,
        maximum_recovery_rate: float = 0.25,
        maximum_drawdown: float = 0.30,
    ) -> None:
        self.minimum_cycles = int(minimum_cycles)
        self.minimum_uptime_pct = float(minimum_uptime_pct)
        self.maximum_alert_rate = float(maximum_alert_rate)
        self.maximum_recovery_rate = float(maximum_recovery_rate)
        self.maximum_drawdown = float(maximum_drawdown)

    def certify(
        self,
        evidence_summary: Mapping[str, Any],
        *,
        health_summary: Mapping[str, Any],
        runtime_statistics: Mapping[str, Any],
    ) -> dict[str, Any]:
        if not isinstance(evidence_summary, Mapping):
            raise MarathonCertificationEngineError("evidence_summary must be a mapping")
        if not isinstance(health_summary, Mapping):
            raise MarathonCertificationEngineError("health_summary must be a mapping")
        if not isinstance(runtime_statistics, Mapping):
            raise MarathonCertificationEngineError("runtime_statistics must be a mapping")

        failures: list[str] = []
        warnings: list[str] = []
        cycle_count = int(evidence_summary.get("cycle_count", 0) or 0)
        runtime_duration_seconds = self._float(evidence_summary.get("runtime_duration_seconds", 0.0))
        health_status = str(health_summary.get("status") or "").upper()
        uptime_pct = self._float(runtime_statistics.get("uptime_pct", 0.0))
        alert_rate = self._float(runtime_statistics.get("alert_rate", 0.0))
        recovery_rate = self._float(runtime_statistics.get("recovery_rate", 0.0))
        max_drawdown = self._float(evidence_summary.get("max_drawdown", evidence_summary.get("maximum_drawdown", 0.0)))
        trade_count = int(runtime_statistics.get("trade_count", evidence_summary.get("trade_count", 0)) or 0)
        learning_confidence_raw = runtime_statistics.get("learning_confidence", evidence_summary.get("learning_confidence"))
        learning_confidence = self._float(learning_confidence_raw) if learning_confidence_raw is not None else 0.0
        execution_health = str(runtime_statistics.get("execution_health", evidence_summary.get("execution_health", "UNKNOWN"))).upper()
        profitability_health = str(runtime_statistics.get("profitability_health", evidence_summary.get("profitability_health", "UNKNOWN"))).upper()
        portfolio_health = str(runtime_statistics.get("portfolio_health", evidence_summary.get("portfolio_health", "UNKNOWN"))).upper()
        optimization_health = str(runtime_statistics.get("optimization_health", evidence_summary.get("optimization_health", "UNKNOWN"))).upper()

        if cycle_count < self.minimum_cycles:
            failures.append("minimum_cycles")
        if runtime_duration_seconds <= 0.0:
            failures.append("runtime_duration")
        if health_status == "CRITICAL":
            failures.append("health_critical")
        if health_status == "WARNING":
            warnings.append("health_warning")
        if uptime_pct < self.minimum_uptime_pct:
            warnings.append("uptime_below_target")
        if alert_rate > self.maximum_alert_rate:
            warnings.append("alert_rate_above_target")
        if recovery_rate > self.maximum_recovery_rate:
            warnings.append("recovery_rate_above_target")
        if max_drawdown > self.maximum_drawdown:
            failures.append("drawdown_excessive")
        if trade_count <= 0:
            failures.append("trade_count")
        if learning_confidence_raw is not None and learning_confidence < 0.40:
            warnings.append("learning_confidence_low")

        severe_runtime = execution_health in {"FAILED", "BLOCKED", "UNHEALTHY"}
        severe_profitability = profitability_health in {"FAILED", "UNHEALTHY"}
        severe_portfolio = portfolio_health in {"FAILED", "UNHEALTHY", "UNSTABLE"}
        severe_optimization = optimization_health in {"FAILED", "UNHEALTHY", "UNSTABLE"}

        if severe_runtime:
            failures.append("execution_health")
        if severe_profitability:
            failures.append("profitability_health")
        if severe_portfolio:
            failures.append("portfolio_health")
        if severe_optimization:
            failures.append("optimization_health")

        if failures:
            status = "FAIL"
        elif warnings:
            status = "PASS_WITH_WARNINGS"
        else:
            status = "PASS"

        if failures:
            go_no_go = "NO_GO"
        elif warnings:
            go_no_go = "CONDITIONAL_GO"
        else:
            go_no_go = "GO"

        decision = MarathonCertificationDecision(
            status=status,
            go_no_go=go_no_go,
            warnings=tuple(sorted(set(warnings))),
            failures=tuple(sorted(set(failures))),
            evidence_used={
                "cycle_count": cycle_count,
                "runtime_duration_seconds": round(runtime_duration_seconds, 8),
                "health_status": health_status,
                "uptime_pct": round(uptime_pct, 8),
                "alert_rate": round(alert_rate, 8),
                "recovery_rate": round(recovery_rate, 8),
                "max_drawdown": round(max_drawdown, 8),
                "trade_count": trade_count,
                "learning_confidence": round(learning_confidence, 8),
                "execution_health": execution_health,
                "profitability_health": profitability_health,
                "portfolio_health": portfolio_health,
                "optimization_health": optimization_health,
            },
        )
        return decision.to_dict()

    @staticmethod
    def _float(value: Any) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0
