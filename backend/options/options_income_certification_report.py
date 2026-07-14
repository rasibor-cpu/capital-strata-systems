from __future__ import annotations

from typing import Any, Mapping

from backend.options.paper_position_repository import SAFE_FLAGS


class OptionsIncomeCertificationReportError(ValueError):
    """Raised when certification report generation fails closed."""


class OptionsIncomeCertificationReportBuilder:
    def build(self, certification: Mapping[str, Any], audit: Mapping[str, Any]) -> dict[str, Any]:
        if not certification:
            raise OptionsIncomeCertificationReportError("invalid certification")
        if not audit:
            raise OptionsIncomeCertificationReportError("missing audit")
        return {
            "report_type": "OPTIONS_INCOME_CONTROLLED_PAPER_CERTIFICATION",
            "certification_status": certification.get("certification_status", "FAIL"),
            "overall_readiness": certification.get("overall_readiness", "NOT_READY"),
            "certification_score": certification.get("certification_score", 0.0),
            "audit": dict(audit),
            "summary": _summary(certification),
            "paper_only": True,
            **SAFE_FLAGS,
        }


def _summary(certification: Mapping[str, Any]) -> str:
    return (
        "Options Income Engine controlled paper certification "
        f"{certification.get('certification_status', 'FAIL')} with readiness "
        f"{certification.get('overall_readiness', 'NOT_READY')}."
    )


__all__ = ["OptionsIncomeCertificationReportBuilder", "OptionsIncomeCertificationReportError"]
