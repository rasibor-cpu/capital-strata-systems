"""
Backward-compatible certification report builders.
"""

from typing import Any, Dict

from backend.certification.certification_report import CertificationReportPublisher
from backend.certification.readiness_models import CertificationResult


class CertificationReports:
    """
    Legacy facade over CertificationReportPublisher.
    """

    def __init__(self, reporting_service: Any):
        self.publisher = CertificationReportPublisher(reporting_service)

    def generate_readiness_report(self, checks_results: Dict[str, Any]) -> Any:
        return self.publisher.reporting_service.create_report(
            report_type="PRODUCTION_READINESS",
            title="Production Readiness Report",
            context=self._legacy_context(checks_results),
            metadata={"source": "enterprise_certification_engine", "read_only": True},
        )

    def generate_certification_report(self, checks_results: Dict[str, Any]) -> Any:
        return self.publisher.reporting_service.create_report(
            report_type="CERTIFICATION",
            title="Certification Report",
            context=self._legacy_context(checks_results),
            metadata={"source": "enterprise_certification_engine", "read_only": True},
        )

    def generate_deployment_checklist_report(self, result: CertificationResult) -> Any:
        return self.publisher.generate_deployment_checklist_report(result)

    def _legacy_context(self, checks_results: Dict[str, Any]) -> Dict[str, Any]:
        critical = checks_results.get("critical_findings", [])
        warnings = checks_results.get("warnings", [])
        info = checks_results.get("informational_findings", checks_results.get("info_findings", []))
        return {
            "generated_at": checks_results.get("generated_at", "UNKNOWN"),
            "readiness_score": checks_results.get("overall_readiness_score", 0.0),
            "certification_status": checks_results.get("certification_status", checks_results.get("deployment_recommendation", "WARNING")),
            "status": checks_results.get("certification_status", checks_results.get("deployment_recommendation", "WARNING")),
            "critical_findings_count": len(critical),
            "warning_count": len(warnings),
            "information_count": len(info),
            "critical_findings": "\n".join(critical) if critical else "None",
            "warnings": "\n".join(warnings) if warnings else "None",
            "informational_findings": "\n".join(info) if info else "None",
            "recommended_actions": "\n".join(checks_results.get("recommended_actions", [])),
            "deployment_checklist": "Not generated",
            "recommendation": checks_results.get("deployment_recommendation", "WARNING"),
            "findings_count": len(critical),
        }
