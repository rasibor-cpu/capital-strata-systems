from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from backend.analytics.performance_analytics_engine import PerformanceAnalyticsEngine
from backend.analytics.performance_reporting_engine import PerformanceReportingEngine
from backend.runtime.runtime_recovery_manager import RuntimeRecoveryManager
from backend.runtime.runtime_supervisor import RuntimeSupervisor

from .live_readiness_report import LiveReadinessReport


class LiveReadinessGateError(RuntimeError):
    """Fail-closed exception for live readiness gating."""


class LiveReadinessGate:
    """Evaluates whether production autonomy can proceed."""

    def __init__(
        self,
        *,
        repository_root: str | Path,
        evidence_path: str | Path,
        repository_clean_probe: Any | None = None,
        runtime_supervisor: RuntimeSupervisor | None = None,
        recovery_manager: RuntimeRecoveryManager | None = None,
        performance_engine: PerformanceAnalyticsEngine | None = None,
        reporting_engine: PerformanceReportingEngine | None = None,
        minimum_win_rate: float = 0.5,
        minimum_profit_factor: float = 1.0,
        maximum_drawdown: float = 0.2,
    ) -> None:
        self.repository_root = Path(repository_root)
        self.evidence_path = Path(evidence_path)
        self.repository_clean_probe = repository_clean_probe
        self.runtime_supervisor = runtime_supervisor or RuntimeSupervisor()
        self.recovery_manager = recovery_manager or RuntimeRecoveryManager()
        self.performance_engine = performance_engine or PerformanceAnalyticsEngine()
        self.reporting_engine = reporting_engine or PerformanceReportingEngine()
        self.minimum_win_rate = float(minimum_win_rate)
        self.minimum_profit_factor = float(minimum_profit_factor)
        self.maximum_drawdown = float(maximum_drawdown)

    def evaluate(
        self,
        *,
        trades: list[Mapping[str, Any]] | None,
        calibration_summary: Mapping[str, Any] | None,
        tests_passing: bool,
        runtime_healthy: bool,
        alerts_operational: bool,
        recovery_operational: bool,
        learning_operational: bool,
        calibration_complete: bool,
    ) -> LiveReadinessReport:
        if trades is not None and not isinstance(trades, list):
            raise LiveReadinessGateError("trades must be a list when provided")
        if calibration_summary is not None and not isinstance(calibration_summary, Mapping):
            raise LiveReadinessGateError("calibration_summary must be a mapping when provided")

        metrics = self.performance_engine.analyze(trades or [])
        repo_clean = self._repository_clean()

        failed_checks: list[str] = []
        warnings: list[str] = []

        if not repo_clean:
            failed_checks.append("repository_clean")
        if not tests_passing:
            failed_checks.append("tests_passing")
        if not runtime_healthy:
            failed_checks.append("runtime_healthy")
        if not alerts_operational:
            failed_checks.append("alerts_operational")
        if not recovery_operational:
            failed_checks.append("recovery_operational")
        if not learning_operational:
            failed_checks.append("learning_operational")
        if not calibration_complete:
            failed_checks.append("calibration_complete")
        if not self.evidence_path.exists():
            failed_checks.append("paper_marathon_evidence_present")
        if metrics["win_rate"] < self.minimum_win_rate:
            failed_checks.append("performance_win_rate")
        if metrics["profit_factor"] < self.minimum_profit_factor:
            failed_checks.append("performance_profit_factor")
        if metrics["max_drawdown"] > self.maximum_drawdown:
            failed_checks.append("drawdown_acceptable")
        if calibration_summary is None:
            warnings.append("calibration_summary_missing")
        elif not calibration_summary.get("audit_trail"):
            warnings.append("calibration_audit_trail_missing")

        status = self._resolve_status(failed_checks, warnings)
        recommendation = self._recommendation_for_status(status)

        operational_summary = {
            "repository_clean": repo_clean,
            "tests_passing": bool(tests_passing),
            "runtime_healthy": bool(runtime_healthy),
            "alerts_operational": bool(alerts_operational),
            "recovery_operational": bool(recovery_operational),
            "learning_operational": bool(learning_operational),
            "calibration_complete": bool(calibration_complete),
            "paper_marathon_evidence_present": self.evidence_path.exists(),
        }

        evidence = {
            "repository_root": str(self.repository_root),
            "evidence_path": str(self.evidence_path),
            "calibration_summary": dict(calibration_summary or {}),
            "report_snapshot": self.reporting_engine.build_reports(
                performance_metrics=metrics,
                calibration_report=calibration_summary or {},
                trade_quality_report={},
                runtime_health_report={"runtime_healthy": runtime_healthy},
                recovery_report={"operational": recovery_operational},
                profitability_report=metrics,
                learning_report={"learning_status": "READY" if learning_operational else "NOT_READY"},
                strategy_ranking_report={"strategy_rankings": []},
            ),
        }

        return LiveReadinessReport(
            readiness_status=status,
            failed_checks=tuple(sorted(set(failed_checks))),
            warnings=tuple(sorted(set(warnings))),
            metrics_summary=metrics,
            operational_summary=operational_summary,
            recommendation=recommendation,
            evidence=evidence,
        )

    def _repository_clean(self) -> bool:
        if self.repository_clean_probe is not None:
            probe = self.repository_clean_probe
            if not callable(probe):
                raise LiveReadinessGateError("repository_clean_probe must be callable when provided")
            result = probe()
            if not isinstance(result, bool):
                raise LiveReadinessGateError("repository_clean_probe must return a bool")
            return result

        import subprocess

        completed = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=self.repository_root,
            capture_output=True,
            text=True,
            check=False,
        )
        if completed.returncode != 0:
            raise LiveReadinessGateError("repository status command failed")
        return not any(line.strip() for line in completed.stdout.splitlines())

    @staticmethod
    def _resolve_status(failed_checks: list[str], warnings: list[str]) -> str:
        if failed_checks:
            if set(failed_checks).issubset({"tests_passing", "calibration_complete", "paper_marathon_evidence_present"}):
                return "CONDITIONAL_GO"
            if failed_checks == ["paper_marathon_evidence_present"]:
                return "CONDITIONAL_GO"
            if len(failed_checks) == 1 and failed_checks[0] in {"tests_passing", "calibration_complete"}:
                return "CONDITIONAL_GO"
            return "NO_GO"
        if warnings:
            return "CONDITIONAL_GO"
        return "GO"

    @staticmethod
    def _recommendation_for_status(status: str) -> str:
        if status == "GO":
            return "APPROVE_LIVE_READINESS"
        if status == "CONDITIONAL_GO":
            return "APPROVE_WITH_CONDITIONS"
        return "DENY_LIVE_READINESS"
