"""
Readiness data models for the CSS certification engine.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List


PASS = "PASS"
WARNING = "WARNING"
FAIL = "FAIL"

CRITICAL = "CRITICAL"
INFO = "INFO"
from backend.common.numeric_utils import clamp


def clamp_score(value: float) -> float:
    """Clamp readiness scores into the canonical 0-100 range."""
    return clamp(value, 0.0, 100.0)


@dataclass(frozen=True)
class ReadinessFinding:
    severity: str
    subsystem: str
    message: str
    recommended_action: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "severity": self.severity,
            "subsystem": self.subsystem,
            "message": self.message,
            "recommended_action": self.recommended_action,
        }


@dataclass(frozen=True)
class SubsystemReadiness:
    name: str
    score: float
    status: str
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "score": clamp_score(self.score),
            "status": self.status,
            "details": dict(self.details),
        }


@dataclass(frozen=True)
class CertificationResult:
    overall_readiness_score: float
    status: str
    generated_at: str
    subsystem_readiness: List[SubsystemReadiness] = field(default_factory=list)
    critical_findings: List[ReadinessFinding] = field(default_factory=list)
    warnings: List[ReadinessFinding] = field(default_factory=list)
    informational_findings: List[ReadinessFinding] = field(default_factory=list)
    recommended_actions: List[str] = field(default_factory=list)
    deployment_checklist: List[Dict[str, Any]] = field(default_factory=list)

    @property
    def certification_status(self) -> str:
        return self.status

    def dashboard_section(self) -> Dict[str, Any]:
        return {
            "overall_readiness_score": clamp_score(self.overall_readiness_score),
            "certification_status": self.status,
            "critical_findings_count": len(self.critical_findings),
            "warning_count": len(self.warnings),
            "information_count": len(self.informational_findings),
            "last_certification_time": self.generated_at,
        }

    def to_dict(self) -> Dict[str, Any]:
        return {
            "overall_readiness_score": clamp_score(self.overall_readiness_score),
            "certification_status": self.status,
            "generated_at": self.generated_at,
            "subsystem_readiness": [item.to_dict() for item in self.subsystem_readiness],
            "critical_findings": [item.to_dict() for item in self.critical_findings],
            "warnings": [item.to_dict() for item in self.warnings],
            "informational_findings": [item.to_dict() for item in self.informational_findings],
            "recommended_actions": list(self.recommended_actions),
            "deployment_checklist": [dict(item) for item in self.deployment_checklist],
        }

    def to_legacy_dict(self) -> Dict[str, Any]:
        data = self.to_dict()
        data.update(
            {
                "deployment_recommendation": self.status,
                "critical_findings": [item.message for item in self.critical_findings],
                "warnings": [item.message for item in self.warnings],
                "info_findings": [item.message for item in self.informational_findings],
            }
        )
        return data
