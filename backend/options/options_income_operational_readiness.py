from __future__ import annotations

from typing import Any, Mapping

from backend.options.paper_position_repository import SAFE_FLAGS


class OptionsIncomeOperationalReadinessError(ValueError):
    """Raised when operational readiness scoring fails closed."""


class OptionsIncomeOperationalReadiness:
    def score(
        self,
        *,
        certification: Mapping[str, Any],
        replay: Mapping[str, Any],
        runtime: Mapping[str, Any],
        documentation_present: bool = True,
    ) -> dict[str, Any]:
        if not isinstance(certification, Mapping):
            raise OptionsIncomeOperationalReadinessError("certification must be a mapping")
        subsystem_rows = list(certification.get("subsystems", []))
        pass_count = sum(1 for row in subsystem_rows if dict(row).get("status") == "PASS")
        total = max(1, len(subsystem_rows))
        architecture_score = 100.0 if total >= 20 else 70.0
        integration_score = round((pass_count / total) * 100.0, 8)
        determinism_score = 100.0 if replay.get("status") == "PASS" else 0.0
        paper_safety_score = 100.0 if runtime.get("status") == "PASS" else 0.0
        dashboard_score = 100.0 if _subsystem(certification, "dashboard") == "PASS" else 0.0
        broker_abstraction_score = 100.0 if _subsystem(certification, "broker_abstraction") == "PASS" else 0.0
        documentation_score = 100.0 if documentation_present else 0.0
        scores = {
            "architecture_score": architecture_score,
            "integration_score": integration_score,
            "determinism_score": determinism_score,
            "paper_safety_score": paper_safety_score,
            "dashboard_score": dashboard_score,
            "broker_abstraction_score": broker_abstraction_score,
            "documentation_score": documentation_score,
        }
        overall = round(sum(scores.values()) / len(scores), 8)
        if overall >= 95.0:
            readiness = "READY_FOR_CONTROLLED_CERTIFICATION"
        elif overall >= 80.0:
            readiness = "READY_FOR_PAPER"
        else:
            readiness = "NOT_READY"
        return {
            **scores,
            "overall_readiness_score": overall,
            "overall_readiness": readiness,
            "warnings": [] if readiness == "READY_FOR_CONTROLLED_CERTIFICATION" else ["readiness_below_controlled_certification_threshold"],
            "paper_only": True,
            **SAFE_FLAGS,
        }


def _subsystem(certification: Mapping[str, Any], name: str) -> str:
    for row in certification.get("subsystems", []):
        item = dict(row)
        if item.get("subsystem") == name:
            return str(item.get("status", "UNAVAILABLE"))
    return "UNAVAILABLE"


__all__ = ["OptionsIncomeOperationalReadiness", "OptionsIncomeOperationalReadinessError"]
