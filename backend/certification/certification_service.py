"""
Service facade for CSS enterprise certification.
"""

from typing import Any, Dict

from backend.certification.certification_report import CertificationReportPublisher
from backend.certification.readiness_engine import ReadinessEngine
from backend.certification.readiness_models import CertificationResult


class CertificationService:
    """
    Advisory facade for production readiness certification.
    """

    def __init__(
        self,
        read_model: Any = None,
        event_bus: Any = None,
        dashboard_service: Any = None,
        reporting_service: Any = None,
        readiness_engine: ReadinessEngine = None,
    ):
        self.readiness_engine = readiness_engine or ReadinessEngine(
            read_model=read_model,
            event_bus=event_bus,
            dashboard_service=dashboard_service,
        )
        self.report_publisher = (
            CertificationReportPublisher(reporting_service)
            if reporting_service is not None
            else None
        )
        self._last_result: CertificationResult = None

    def certify(self) -> CertificationResult:
        self._last_result = self.readiness_engine.evaluate()
        return self._last_result

    def get_dashboard_section(self) -> Dict[str, Any]:
        result = self.certify()
        return result.dashboard_section()

    def generate_reports(self, result: CertificationResult = None) -> Dict[str, Any]:
        if self.report_publisher is None:
            raise ValueError("Reporting service is required to generate certification reports.")
        return self.report_publisher.generate_all(result or self.certify())

    def get_last_result(self) -> CertificationResult:
        return self._last_result
