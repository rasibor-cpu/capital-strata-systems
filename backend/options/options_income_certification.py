from __future__ import annotations

from typing import Any, Mapping, Sequence

from backend.options.options_income_audit_report import OptionsIncomeAuditReportBuilder
from backend.options.options_income_certification_report import OptionsIncomeCertificationReportBuilder
from backend.options.options_income_end_to_end_validator import NOW, OptionsIncomeEndToEndValidator, SUBSYSTEMS
from backend.options.options_income_operational_readiness import OptionsIncomeOperationalReadiness
from backend.options.options_income_replay_validator import OptionsIncomeReplayValidator
from backend.options.options_income_runtime_validator import OptionsIncomeRuntimeValidator
from backend.options.paper_position_repository import SAFE_FLAGS


class OptionsIncomeCertificationError(ValueError):
    """Raised when controlled paper certification fails closed."""


class OptionsIncomeCertificationEngine:
    def __init__(
        self,
        *,
        end_to_end: OptionsIncomeEndToEndValidator | None = None,
        replay: OptionsIncomeReplayValidator | None = None,
        runtime: OptionsIncomeRuntimeValidator | None = None,
        readiness: OptionsIncomeOperationalReadiness | None = None,
        audit: OptionsIncomeAuditReportBuilder | None = None,
        report: OptionsIncomeCertificationReportBuilder | None = None,
    ) -> None:
        self.end_to_end = end_to_end or OptionsIncomeEndToEndValidator()
        self.replay = replay or OptionsIncomeReplayValidator()
        self.runtime = runtime or OptionsIncomeRuntimeValidator()
        self.readiness = readiness or OptionsIncomeOperationalReadiness()
        self.audit = audit or OptionsIncomeAuditReportBuilder()
        self.report = report or OptionsIncomeCertificationReportBuilder()

    def certify(
        self,
        *,
        mode: str = "PAPER",
        timestamp: str = NOW,
        tests_executed: Sequence[str] | None = None,
        documentation_present: bool = True,
    ) -> dict[str, Any]:
        if str(mode or "").strip().upper() != "PAPER":
            raise OptionsIncomeCertificationError("unsafe runtime")
        e2e = self.end_to_end.validate(mode=mode, now=timestamp)
        runtime_result = self.runtime.validate(e2e, section="options_income_certification")
        replay_result = self.replay.validate(lambda: self.end_to_end.validate(mode=mode, now=timestamp))
        base = _certification_base(e2e, runtime_result, replay_result)
        readiness_result = self.readiness.score(
            certification=base,
            replay=replay_result,
            runtime=runtime_result,
            documentation_present=documentation_present,
        )
        base["readiness"] = readiness_result
        base["overall_readiness"] = readiness_result["overall_readiness"]
        audit = self.audit.build(
            certification=base,
            readiness=readiness_result,
            replay=replay_result,
            tests_executed=tests_executed,
            timestamp=timestamp,
        )
        if not audit:
            raise OptionsIncomeCertificationError("missing audit")
        report = self.report.build(base, audit)
        base["audit_report"] = audit
        base["certification_report"] = report
        return base

    def fail_closed(self, reason: str) -> dict[str, Any]:
        return {
            "certification_status": "FAIL",
            "overall_readiness": "NOT_READY",
            "certification_score": 0.0,
            "blockers": [str(reason)],
            "warnings": [],
            "subsystems": [
                {"subsystem": name, "status": "UNAVAILABLE", "evidence": "certification failed closed", "paper_only": True, **SAFE_FLAGS}
                for name in SUBSYSTEMS
            ],
            "paper_only": True,
            **SAFE_FLAGS,
        }


def certify_options_income_engine(**kwargs: Any) -> dict[str, Any]:
    return OptionsIncomeCertificationEngine().certify(**kwargs)


def _certification_base(e2e: Mapping[str, Any], runtime: Mapping[str, Any], replay: Mapping[str, Any]) -> dict[str, Any]:
    subsystem_rows = [dict(row) for row in e2e.get("subsystems", [])]
    if len({row.get("subsystem") for row in subsystem_rows}) != len(subsystem_rows):
        raise OptionsIncomeCertificationError("duplicate reports")
    failed = [row["subsystem"] for row in subsystem_rows if row.get("status") == "FAIL"]
    unavailable = [row["subsystem"] for row in subsystem_rows if row.get("status") == "UNAVAILABLE"]
    warnings = [row["subsystem"] for row in subsystem_rows if row.get("status") == "WARNING"]
    blockers = sorted(set(list(e2e.get("blockers", [])) + failed + unavailable + list(runtime.get("blockers", [])) + list(replay.get("blockers", []))))
    pass_count = sum(1 for row in subsystem_rows if row.get("status") == "PASS")
    score = round((pass_count / max(1, len(subsystem_rows))) * 100.0, 8)
    status = "FAIL" if blockers else ("WARNING" if warnings else "PASS")
    return {
        "certification_status": status,
        "certification_score": score,
        "subsystems": subsystem_rows,
        "end_to_end": dict(e2e),
        "runtime_validation": dict(runtime),
        "replay_validation": dict(replay),
        "blockers": blockers,
        "warnings": sorted(set(warnings + list(e2e.get("warnings", [])))),
        "paper_only": True,
        **SAFE_FLAGS,
    }


__all__ = ["OptionsIncomeCertificationEngine", "OptionsIncomeCertificationError", "certify_options_income_engine"]
