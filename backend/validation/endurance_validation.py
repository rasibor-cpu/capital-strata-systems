from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Mapping

OV002_AUTHORITATIVE = False
PHASE181_AUTHORITATIVE = False


class EnduranceValidationError(RuntimeError):
    """Fail-closed exception for endurance validation."""


@dataclass(frozen=True)
class EnduranceValidationResult:
    status: str
    readiness_score: float
    go_no_go: str
    critical_findings: tuple[str, ...]
    warnings: tuple[str, ...]
    informational_findings: tuple[str, ...]
    recommended_actions: tuple[str, ...]
    metrics: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["ov002_authoritative"] = OV002_AUTHORITATIVE
        payload["phase181_authoritative"] = PHASE181_AUTHORITATIVE
        return payload


class EnduranceValidationEngine:
    """
    Read-only long-run validation engine for RC endurance evidence.
    """

    def __init__(
        self,
        *,
        minimum_cycles: int = 1,
        minimum_runtime_seconds: float = 1.0,
        minimum_uptime_pct: float = 0.95,
        maximum_alert_rate: float = 0.30,
        maximum_recovery_rate: float = 0.25,
        maximum_restart_rate: float = 0.10,
        maximum_memory_growth: float = 0.20,
        maximum_drawdown: float = 0.30,
    ) -> None:
        self.minimum_cycles = int(minimum_cycles)
        self.minimum_runtime_seconds = float(minimum_runtime_seconds)
        self.minimum_uptime_pct = float(minimum_uptime_pct)
        self.maximum_alert_rate = float(maximum_alert_rate)
        self.maximum_recovery_rate = float(maximum_recovery_rate)
        self.maximum_restart_rate = float(maximum_restart_rate)
        self.maximum_memory_growth = float(maximum_memory_growth)
        self.maximum_drawdown = float(maximum_drawdown)

    def validate(self, evidence: Mapping[str, Any]) -> EnduranceValidationResult:
        if not isinstance(evidence, Mapping):
            raise EnduranceValidationError("evidence must be a mapping")

        cycle_count = int(evidence.get("cycle_count", evidence.get("cycles_completed", 0)) or 0)
        runtime_seconds = self._float(evidence.get("runtime_duration_seconds", evidence.get("elapsed_time_seconds", 0.0)))
        uptime_pct = self._float(evidence.get("uptime_pct", 1.0))
        alert_count = len(list(evidence.get("alerts", [])))
        recovery_count = len(list(evidence.get("recovery_events", evidence.get("recoveries", []))))
        restart_count = len(list(evidence.get("restart_events", evidence.get("restarts", []))))
        alert_rate = self._rate(alert_count, cycle_count)
        recovery_rate = self._rate(recovery_count, cycle_count)
        restart_rate = self._rate(restart_count, cycle_count)
        memory_growth = self._float(evidence.get("memory_growth_metric", evidence.get("memory_growth_rate", 0.0)))
        max_drawdown = self._float(evidence.get("max_drawdown", evidence.get("maximum_drawdown", 0.0)))
        stop_reason = str(evidence.get("stop_reason") or "").strip()
        paper_mode = bool(evidence.get("paper_mode", evidence.get("paper_mode_enabled", True)))
        checkpoint_count = len(list(evidence.get("checkpoints", [])))
        resume_supported = bool(evidence.get("resume_supported", checkpoint_count > 0))
        heartbeat_status = str(evidence.get("heartbeat_status", "OK")).upper()
        runtime_status = str(evidence.get("runtime_status", "HEALTHY")).upper()

        critical: list[str] = []
        warnings: list[str] = []
        info: list[str] = []
        actions: list[str] = []

        if cycle_count < self.minimum_cycles:
            critical.append("minimum_cycles_not_met")
            actions.append("Complete the required long-run validation cycle count.")
        if runtime_seconds < self.minimum_runtime_seconds:
            critical.append("minimum_runtime_not_met")
            actions.append("Complete the required endurance runtime window.")
        if not paper_mode:
            critical.append("paper_mode_disabled")
            actions.append("Run endurance validation in paper or practice mode only.")
        if stop_reason:
            critical.append("unexpected_stop")
            actions.append("Resolve the endurance stop condition before RC1 approval.")
        if runtime_status in {"CRITICAL", "FAILED", "UNHEALTHY", "STOPPED"}:
            critical.append("runtime_unhealthy")
            actions.append("Restore runtime health before RC1 approval.")
        if heartbeat_status in {"LOST", "STALE", "CRITICAL"}:
            critical.append("heartbeat_unhealthy")
            actions.append("Restore heartbeat continuity before RC1 approval.")
        if max_drawdown > self.maximum_drawdown:
            critical.append("drawdown_exceeds_limit")
            actions.append("Reduce drawdown risk before RC1 approval.")

        if uptime_pct < self.minimum_uptime_pct:
            warnings.append("uptime_below_target")
            actions.append("Review uptime interruptions before RC1 release.")
        if alert_rate > self.maximum_alert_rate:
            warnings.append("alert_rate_above_target")
            actions.append("Review recurring alerts from endurance evidence.")
        if recovery_rate > self.maximum_recovery_rate:
            warnings.append("recovery_rate_above_target")
            actions.append("Review recovery frequency before RC1 release.")
        if restart_rate > self.maximum_restart_rate:
            warnings.append("restart_rate_above_target")
            actions.append("Review restart frequency before RC1 release.")
        if memory_growth > self.maximum_memory_growth:
            warnings.append("memory_growth_above_target")
            actions.append("Review memory growth before RC1 release.")
        if not resume_supported:
            info.append("checkpoint_resume_not_verified")
            actions.append("Capture checkpoint/resume evidence before final deployment approval.")

        score = self._score(len(critical), len(warnings), len(info))
        status = "FAIL" if critical else ("WARNING" if warnings else "PASS")
        go_no_go = "NO_GO" if critical else ("CONDITIONAL_GO" if warnings else "GO")
        if not actions:
            actions.append("Endurance evidence supports RC1 readiness review.")

        return EnduranceValidationResult(
            status=status,
            readiness_score=score,
            go_no_go=go_no_go,
            critical_findings=tuple(sorted(set(critical))),
            warnings=tuple(sorted(set(warnings))),
            informational_findings=tuple(sorted(set(info))),
            recommended_actions=tuple(dict.fromkeys(actions)),
            metrics={
                "cycle_count": cycle_count,
                "runtime_duration_seconds": round(runtime_seconds, 8),
                "uptime_pct": round(uptime_pct, 8),
                "alert_rate": round(alert_rate, 8),
                "recovery_rate": round(recovery_rate, 8),
                "restart_rate": round(restart_rate, 8),
                "memory_growth_metric": round(memory_growth, 8),
                "max_drawdown": round(max_drawdown, 8),
                "paper_mode": paper_mode,
                "resume_supported": resume_supported,
                "runtime_status": runtime_status,
                "heartbeat_status": heartbeat_status,
                "ov002_authoritative": OV002_AUTHORITATIVE,
                "phase181_authoritative": PHASE181_AUTHORITATIVE,
            },
        )

    @staticmethod
    def _rate(count: int, cycle_count: int) -> float:
        if cycle_count <= 0:
            return float(count)
        return float(count) / float(cycle_count)

    @staticmethod
    def _score(critical_count: int, warning_count: int, info_count: int) -> float:
        return max(0.0, min(100.0, 100.0 - (critical_count * 20.0) - (warning_count * 5.0) - (info_count * 1.0)))

    @staticmethod
    def _float(value: Any) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0
