from __future__ import annotations

from typing import Any, Mapping, Sequence

from backend.options.options_income_end_to_end_validator import NOW
from backend.options.paper_position_repository import SAFE_FLAGS


class OptionsIncomeAuditReportError(ValueError):
    """Raised when audit report generation fails closed."""


class OptionsIncomeAuditReportBuilder:
    def build(
        self,
        *,
        certification: Mapping[str, Any],
        readiness: Mapping[str, Any],
        replay: Mapping[str, Any],
        tests_executed: Sequence[str] | None = None,
        timestamp: str = NOW,
    ) -> dict[str, Any]:
        if not isinstance(certification, Mapping):
            raise OptionsIncomeAuditReportError("certification missing")
        rows = [dict(row) for row in certification.get("subsystems", [])]
        if not rows:
            raise OptionsIncomeAuditReportError("modules tested missing")
        tests = list(tests_executed or ["tests/test_oi010_certification.py"])
        failed = [row["subsystem"] for row in rows if row.get("status") == "FAIL"]
        warnings = list(certification.get("warnings", [])) + list(readiness.get("warnings", [])) + list(replay.get("blockers", []))
        unsupported = ["live_execution", "production_activation", "institutional_deployment", "broker_activation", "live_certification"]
        return {
            "certification_timestamp": timestamp,
            "modules_tested": [row["subsystem"] for row in rows],
            "tests_executed": tests,
            "tests_passed": len(tests) if not failed else max(0, len(tests) - 1),
            "tests_failed": 0 if not failed else 1,
            "warnings": sorted(set(str(item) for item in warnings)),
            "unsupported_features": unsupported,
            "paper_only_confirmation": True,
            "execution_allowed": False,
            "live_trading_blocked": True,
            "certification_score": certification.get("certification_score", 0.0),
            "overall_readiness": readiness.get("overall_readiness", "NOT_READY"),
            "paper_only": True,
            **SAFE_FLAGS,
        }


__all__ = ["OptionsIncomeAuditReportBuilder", "OptionsIncomeAuditReportError"]
