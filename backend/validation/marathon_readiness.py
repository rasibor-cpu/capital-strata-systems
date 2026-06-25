from __future__ import annotations

import importlib
import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from .marathon_checklist import MarathonCheckResult, MarathonChecklist
from .marathon_report import MarathonReadinessReport, build_marathon_readiness_report


class MarathonReadinessError(RuntimeError):
    """Fail-closed exception for marathon readiness certification."""


@dataclass(frozen=True)
class MarathonCheckDefinition:
    name: str
    runner: Callable[[], MarathonCheckResult]


class MarathonReadiness:
    """Backend-only readiness certification for a 48-hour marathon run."""

    def __init__(
        self,
        *,
        repository_root: str | Path | None = None,
        config_path: str | Path | None = None,
        check_overrides: dict[str, Callable[[], MarathonCheckResult]] | None = None,
    ) -> None:
        self.repository_root = Path(repository_root or Path(__file__).resolve().parents[2])
        self.config_path = Path(config_path or (self.repository_root / "config.json"))
        self.check_overrides = dict(check_overrides or {})

    def certify(self) -> MarathonReadinessReport:
        checklist = MarathonChecklist(results=tuple(self.collect_check_results()))
        return build_marathon_readiness_report(checklist)

    def collect_check_results(self) -> list[MarathonCheckResult]:
        results: list[MarathonCheckResult] = []
        for definition in self._build_check_definitions():
            try:
                results.append(definition.runner())
            except Exception as exc:
                results.append(
                    MarathonCheckResult(
                        check_name=definition.name,
                        passed=False,
                        required=True,
                        message=str(exc),
                        evidence={"error_type": type(exc).__name__},
                    )
                )
        return results

    def _build_check_definitions(self) -> list[MarathonCheckDefinition]:
        return [
            MarathonCheckDefinition("repository_clean", self._check_repository_clean),
            MarathonCheckDefinition("replay_engine_available", self._check_replay_engine_available),
            MarathonCheckDefinition("intelligence_orchestrator_available", self._check_intelligence_orchestrator_available),
            MarathonCheckDefinition("learning_pipeline_available", self._check_learning_pipeline_available),
            MarathonCheckDefinition("alert_system_available", self._check_alert_system_available),
            MarathonCheckDefinition("recovery_manager_available", self._check_recovery_manager_available),
            MarathonCheckDefinition("notification_dispatcher_available", self._check_notification_dispatcher_available),
            MarathonCheckDefinition("paper_mode_configured", self._check_paper_mode_configured),
            MarathonCheckDefinition("runtime_supervisor_available", self._check_runtime_supervisor_available),
            MarathonCheckDefinition("portfolio_guard_available", self._check_portfolio_guard_available),
            MarathonCheckDefinition("adaptive_exit_available", self._check_adaptive_exit_available),
        ]

    def _check_repository_clean(self) -> MarathonCheckResult:
        override = self.check_overrides.get("repository_clean")
        if override:
            return override()

        try:
            completed = subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=self.repository_root,
                capture_output=True,
                text=True,
                check=False,
            )
        except Exception as exc:
            raise MarathonReadinessError(f"repository check unavailable: {exc}") from exc

        if completed.returncode != 0:
            raise MarathonReadinessError("repository status command failed")

        dirty = [line for line in completed.stdout.splitlines() if line.strip()]
        if dirty:
            return MarathonCheckResult(
                check_name="repository_clean",
                passed=False,
                message="working tree is dirty",
                evidence={"dirty_paths": dirty},
            )

        return MarathonCheckResult(
            check_name="repository_clean",
            passed=True,
            evidence={"status": "clean"},
        )

    def _check_replay_engine_available(self) -> MarathonCheckResult:
        return self._import_check(
            "replay_engine_available",
            "backend.validation.historical_replay_engine",
            "HistoricalReplayEngine",
        )

    def _check_intelligence_orchestrator_available(self) -> MarathonCheckResult:
        return self._import_check(
            "intelligence_orchestrator_available",
            "backend.intelligence.intelligence_orchestrator",
            "IntelligenceOrchestrator",
        )

    def _check_learning_pipeline_available(self) -> MarathonCheckResult:
        return self._import_check(
            "learning_pipeline_available",
            "backend.analytics.learning_pipeline_integration",
            "LearningPipelineIntegration",
        )

    def _check_alert_system_available(self) -> MarathonCheckResult:
        repository = self._import_check(
            "alert_repository_available",
            "backend.monitoring.alert_repository",
            "AlertRepository",
        )
        bridge = self._import_check(
            "alert_bridge_available",
            "backend.monitoring.alert_bridge",
            "CanonicalAlertBridge",
        )
        if not repository.passed:
            return MarathonCheckResult(
                check_name="alert_system_available",
                passed=False,
                message=repository.message,
                evidence=repository.evidence,
            )
        if not bridge.passed:
            return MarathonCheckResult(
                check_name="alert_system_available",
                passed=False,
                message=bridge.message,
                evidence=bridge.evidence,
            )
        return MarathonCheckResult(
            check_name="alert_system_available",
            passed=True,
            evidence={"components": ["AlertRepository", "CanonicalAlertBridge"]},
        )

    def _check_recovery_manager_available(self) -> MarathonCheckResult:
        return self._import_check(
            "recovery_manager_available",
            "backend.runtime.runtime_recovery_manager",
            "RuntimeRecoveryManager",
        )

    def _check_notification_dispatcher_available(self) -> MarathonCheckResult:
        return self._import_check(
            "notification_dispatcher_available",
            "backend.monitoring.notification_dispatcher",
            "NotificationDispatcher",
        )

    def _check_paper_mode_configured(self) -> MarathonCheckResult:
        override = self.check_overrides.get("paper_mode_configured")
        if override:
            return override()

        if not self.config_path.exists():
            return MarathonCheckResult(
                check_name="paper_mode_configured",
                passed=False,
                message="config.json is missing",
            )

        try:
            payload = json.loads(self.config_path.read_text(encoding="utf-8"))
        except Exception as exc:
            return MarathonCheckResult(
                check_name="paper_mode_configured",
                passed=False,
                message=f"config.json is unreadable: {exc}",
            )

        if not isinstance(payload, dict):
            return MarathonCheckResult(
                check_name="paper_mode_configured",
                passed=False,
                message="config.json must contain a JSON object",
            )

        system = payload.get("system", {})
        oanda = payload.get("oanda", {})
        risk = payload.get("risk", {})
        mode = str(system.get("mode") or "").strip().lower()
        environment = str(oanda.get("environment") or "").strip().lower()
        trading_enabled = bool(risk.get("trading_enabled", False))

        if environment in {"practice", "paper", "demo"}:
            warning = mode not in {"paper", "practice", "demo"}
            return MarathonCheckResult(
                check_name="paper_mode_configured",
                passed=True,
                warning=warning,
                message="paper-mode capable practice environment configured" if warning else "paper mode configured",
                evidence={
                    "system_mode": mode,
                    "oanda_environment": environment,
                    "trading_enabled": trading_enabled,
                },
            )

        return MarathonCheckResult(
            check_name="paper_mode_configured",
            passed=False,
            message="paper/practice environment not configured",
            evidence={
                "system_mode": mode,
                "oanda_environment": environment,
                "trading_enabled": trading_enabled,
            },
        )

    def _check_runtime_supervisor_available(self) -> MarathonCheckResult:
        return self._import_check(
            "runtime_supervisor_available",
            "backend.runtime.runtime_supervisor",
            "RuntimeSupervisor",
        )

    def _check_portfolio_guard_available(self) -> MarathonCheckResult:
        guard = self._import_check(
            "concentration_guard_available",
            "backend.analytics.concentration_guard",
            "ConcentrationGuard",
        )
        correlation = self._import_check(
            "portfolio_correlation_engine_available",
            "backend.analytics.portfolio_correlation_engine",
            "PortfolioCorrelationEngine",
        )
        if not guard.passed:
            return MarathonCheckResult(
                check_name="portfolio_guard_available",
                passed=False,
                message=guard.message,
                evidence=guard.evidence,
            )
        if not correlation.passed:
            return MarathonCheckResult(
                check_name="portfolio_guard_available",
                passed=False,
                message=correlation.message,
                evidence=correlation.evidence,
            )
        return MarathonCheckResult(
            check_name="portfolio_guard_available",
            passed=True,
            evidence={"components": ["ConcentrationGuard", "PortfolioCorrelationEngine"]},
        )

    def _check_adaptive_exit_available(self) -> MarathonCheckResult:
        return self._import_check(
            "adaptive_exit_available",
            "backend.analytics.adaptive_exit_engine",
            "AdaptiveExitEngine",
        )

    def _import_check(self, check_name: str, module_name: str, attribute_name: str) -> MarathonCheckResult:
        override = self.check_overrides.get(check_name)
        if override:
            return override()

        try:
            module = importlib.import_module(module_name)
        except Exception as exc:
            return MarathonCheckResult(
                check_name=check_name,
                passed=False,
                message=f"{module_name} unavailable: {exc}",
                evidence={"module": module_name, "error_type": type(exc).__name__},
            )

        if not hasattr(module, attribute_name):
            return MarathonCheckResult(
                check_name=check_name,
                passed=False,
                message=f"{attribute_name} missing from {module_name}",
                evidence={"module": module_name, "attribute": attribute_name},
            )

        return MarathonCheckResult(
            check_name=check_name,
            passed=True,
            evidence={"module": module_name, "attribute": attribute_name},
        )
