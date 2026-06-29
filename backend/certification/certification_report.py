"""
Reporting integration for CSS certification results.
"""

from typing import Any, Dict

from backend.certification.readiness_models import CertificationResult


class CertificationReportPublisher:
    """
    Publishes certification artifacts through the existing ReportingService.
    """

    def __init__(self, reporting_service: Any):
        self.reporting_service = reporting_service

    def generate_production_readiness_report(self, result: CertificationResult) -> Any:
        return self._create(
            "PRODUCTION_READINESS",
            "Production Readiness Report",
            result,
        )

    def generate_certification_report(self, result: CertificationResult) -> Any:
        return self._create(
            "CERTIFICATION",
            "Certification Report",
            result,
        )

    def generate_deployment_checklist_report(self, result: CertificationResult) -> Any:
        return self._create(
            "DEPLOYMENT_CHECKLIST",
            "Deployment Checklist Report",
            result,
        )

    def generate_all(self, result: CertificationResult) -> Dict[str, Any]:
        return {
            "production_readiness": self.generate_production_readiness_report(result),
            "certification": self.generate_certification_report(result),
            "deployment_checklist": self.generate_deployment_checklist_report(result),
        }

    def _create(self, report_type: str, title: str, result: CertificationResult) -> Any:
        return self.reporting_service.create_report(
            report_type=report_type,
            title=title,
            context=self._context(result),
            metadata={"source": "enterprise_certification_engine", "read_only": True},
        )

    def _context(self, result: CertificationResult) -> Dict[str, Any]:
        critical = [item.message for item in result.critical_findings]
        warnings = [item.message for item in result.warnings]
        info = [item.message for item in result.informational_findings]
        checklist = [
            f"{item['status']}: {item['item']}" for item in result.deployment_checklist
        ]
        return {
            "generated_at": result.generated_at,
            "readiness_score": result.overall_readiness_score,
            "certification_status": result.status,
            "status": result.status,
            "critical_findings_count": len(critical),
            "warning_count": len(warnings),
            "information_count": len(info),
            "critical_findings": "\n".join(critical) if critical else "None",
            "warnings": "\n".join(warnings) if warnings else "None",
            "informational_findings": "\n".join(info) if info else "None",
            "recommended_actions": "\n".join(result.recommended_actions),
            "deployment_checklist": "\n".join(checklist),
            "recommendation": result.status,
            "findings_count": len(critical),
        }
