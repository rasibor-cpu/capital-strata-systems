from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Mapping

from .endurance_validation import EnduranceValidationEngine, EnduranceValidationResult


class RC1ReadinessError(RuntimeError):
    """Fail-closed exception for RC1 readiness validation."""


@dataclass(frozen=True)
class RC1ReadinessResult:
    status: str
    go_no_go: str
    readiness_score: float
    critical_findings: tuple[str, ...]
    warnings: tuple[str, ...]
    informational_findings: tuple[str, ...]
    recommended_actions: tuple[str, ...]
    evidence_used: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class RC1ReadinessEvaluator:
    """
    Aggregates validation evidence into an advisory RC1 go/no-go decision.
    """

    def __init__(self, endurance_engine: EnduranceValidationEngine | None = None) -> None:
        self.endurance_engine = endurance_engine or EnduranceValidationEngine()

    def evaluate(
        self,
        *,
        endurance_evidence: Mapping[str, Any],
        certification_result: Mapping[str, Any] | None = None,
        optimization_result: Mapping[str, Any] | None = None,
        regression_result: Mapping[str, Any] | None = None,
    ) -> RC1ReadinessResult:
        endurance = self.endurance_engine.validate(endurance_evidence)
        certification = dict(certification_result or {})
        optimization = dict(optimization_result or {})
        regression = dict(regression_result or {})

        critical = list(endurance.critical_findings)
        warnings = list(endurance.warnings)
        info = list(endurance.informational_findings)
        actions = list(endurance.recommended_actions)

        certification_status = str(
            certification.get("certification_status", certification.get("status", "UNKNOWN"))
        ).upper()
        if certification_status in {"FAIL", "NO_GO", "FAILED"}:
            critical.append("certification_not_passed")
            actions.append("Resolve Enterprise Certification failures before RC1 approval.")
        elif certification_status in {"WARNING", "PASS_WITH_WARNINGS", "CONDITIONAL_GO"}:
            warnings.append("certification_has_warnings")
            actions.append("Review Enterprise Certification warnings before RC1 approval.")
        elif certification_status in {"PASS", "GO"}:
            info.append("certification_passed")
        else:
            warnings.append("certification_evidence_missing")
            actions.append("Attach Enterprise Certification evidence before RC1 approval.")

        advisory_only = bool(optimization.get("advisory_only", False))
        execution_allowed = bool(optimization.get("execution_allowed", False))
        if not advisory_only or execution_allowed:
            critical.append("optimization_not_advisory_only")
            actions.append("Confirm optimization remains advisory-only before RC1 approval.")
        else:
            info.append("optimization_advisory_only")

        regression_passed = bool(regression.get("passed", regression.get("tests_passed", False)))
        if not regression_passed:
            critical.append("regression_tests_not_passed")
            actions.append("Run and pass the affected enterprise regression suite before RC1 approval.")
        else:
            info.append("regression_tests_passed")

        score = max(0.0, min(100.0, endurance.readiness_score - (len(set(critical)) * 10.0) - (len(set(warnings)) * 3.0)))
        status = "FAIL" if critical else ("WARNING" if warnings else "PASS")
        go_no_go = "NO_GO" if critical else ("CONDITIONAL_GO" if warnings else "GO")

        return RC1ReadinessResult(
            status=status,
            go_no_go=go_no_go,
            readiness_score=round(score, 8),
            critical_findings=tuple(sorted(set(critical))),
            warnings=tuple(sorted(set(warnings))),
            informational_findings=tuple(sorted(set(info))),
            recommended_actions=tuple(dict.fromkeys(actions)),
            evidence_used={
                "endurance": endurance.to_dict(),
                "certification_status": certification_status,
                "optimization_advisory_only": advisory_only,
                "optimization_execution_allowed": execution_allowed,
                "regression_passed": regression_passed,
            },
        )

