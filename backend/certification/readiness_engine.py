"""
CSS Enterprise Certification & Readiness Engine.
"""

import time
from typing import Any, List

from backend.certification.deployment_checklist import DeploymentChecklist
from backend.certification.health_validator import HealthValidator
from backend.certification.readiness_models import (
    CRITICAL,
    FAIL,
    INFO,
    PASS,
    WARNING,
    CertificationResult,
    ReadinessFinding,
    clamp_score,
)


class ReadinessEngine:
    """
    Computes advisory production readiness without changing trading behavior.
    """

    def __init__(
        self,
        read_model: Any = None,
        event_bus: Any = None,
        dashboard_service: Any = None,
        validator: HealthValidator = None,
        checklist: DeploymentChecklist = None,
    ):
        self.read_model = read_model
        self.event_bus = event_bus
        self.dashboard_service = dashboard_service
        self.validator = validator or HealthValidator()
        self.checklist = checklist or DeploymentChecklist()

    def evaluate(self) -> CertificationResult:
        subsystems, findings = self.validator.validate(
            read_model=self.read_model,
            event_bus=self.event_bus,
            dashboard_service=self.dashboard_service,
        )
        score = self._score(subsystems, findings)
        critical = [item for item in findings if item.severity == CRITICAL]
        warnings = [item for item in findings if item.severity == WARNING]
        info = [item for item in findings if item.severity == INFO]
        status = self._status(score, critical, warnings)
        checklist = self.checklist.build(subsystems)
        actions = self._recommended_actions(status, critical, warnings, info)

        return CertificationResult(
            overall_readiness_score=score,
            status=status,
            generated_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            subsystem_readiness=subsystems,
            critical_findings=critical,
            warnings=warnings,
            informational_findings=info,
            recommended_actions=actions,
            deployment_checklist=checklist,
        )

    def _score(self, subsystems: List[Any], findings: List[ReadinessFinding]) -> float:
        if not subsystems:
            return 0.0
        base = sum(item.score for item in subsystems) / float(len(subsystems))
        critical_count = len([item for item in findings if item.severity == CRITICAL])
        warning_count = len([item for item in findings if item.severity == WARNING])
        adjusted = base - (critical_count * 8.0) - (warning_count * 2.0)
        return round(clamp_score(adjusted), 2)

    def _status(
        self,
        score: float,
        critical: List[ReadinessFinding],
        warnings: List[ReadinessFinding],
    ) -> str:
        if critical or score < 70.0:
            return FAIL
        if warnings or score < 90.0:
            return WARNING
        return PASS

    def _recommended_actions(
        self,
        status: str,
        critical: List[ReadinessFinding],
        warnings: List[ReadinessFinding],
        info: List[ReadinessFinding],
    ) -> List[str]:
        actions = []
        for finding in critical + warnings:
            if finding.recommended_action and finding.recommended_action not in actions:
                actions.append(finding.recommended_action)

        if status == PASS:
            actions.append("Proceed with production deployment approval review.")
        elif status == WARNING:
            actions.append("Resolve or explicitly accept warning findings before deployment.")
        else:
            actions.append("Do not deploy until critical certification findings are resolved.")

        if info:
            actions.append("Review informational findings for deployment evidence completeness.")
        return actions
