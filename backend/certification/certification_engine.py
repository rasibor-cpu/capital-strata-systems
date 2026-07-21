"""
Compatibility wrapper for the CSS Enterprise Certification Engine.
"""

from typing import Any, Dict

from backend.certification.certification_service import CertificationService
from backend.certification.readiness_engine import ReadinessEngine
from backend.certification.readiness_models import CertificationResult


class _LegacyCertificationReadModel:
    """
    Minimal read model adapter for callers that still pass visibility and metrics services.
    """

    def __init__(self, visibility_layer: Any = None, metrics_service: Any = None):
        self.visibility_layer = visibility_layer
        self.metrics_service = metrics_service

    def get_enterprise_health(self) -> Dict[str, Any]:
        if self.metrics_service is None:
            return {}
        return self.metrics_service.get_current_health()

    def get_runtime_status(self) -> str:
        if self.visibility_layer is None:
            return "UNKNOWN"
        return self.visibility_layer.get_operations_summary().get("overall_status", "UNKNOWN")

    def get_recent_events(self, limit: int = 50):
        if self.visibility_layer is None:
            return []
        return self.visibility_layer.get_recent_events(limit=limit)

    def get_report_status(self) -> Dict[str, Any]:
        return {}


class CertificationEngine:
    """
    Advisory production readiness engine.

    This class preserves the previous run_production_checks API while delegating to
    the new read-only readiness engine.
    """

    def __init__(
        self,
        visibility_layer: Any = None,
        metrics_service: Any = None,
        read_model: Any = None,
        event_bus: Any = None,
        dashboard_service: Any = None,
        reporting_service: Any = None,
    ):
        self.read_model = read_model or _LegacyCertificationReadModel(
            visibility_layer=visibility_layer,
            metrics_service=metrics_service,
        )
        self.service = CertificationService(
            read_model=self.read_model,
            event_bus=event_bus,
            dashboard_service=dashboard_service,
            reporting_service=reporting_service,
            readiness_engine=ReadinessEngine(
                read_model=self.read_model,
                event_bus=event_bus,
                dashboard_service=dashboard_service,
            ),
        )

    def evaluate(self) -> CertificationResult:
        return self.service.certify()

    def certify(self) -> CertificationResult:
        return self.evaluate()

    def get_dashboard_section(self) -> Dict[str, Any]:
        return self.service.get_dashboard_section()

    def generate_reports(self, result: CertificationResult = None) -> Dict[str, Any]:
        return self.service.generate_reports(result=result)

    def evaluate_enterprise_governance(self, evidence) -> Dict[str, Any]:
        """Evaluate supplied governance evidence without inferring or fabricating it."""
        from backend.governance.governance_certification import (
            certify_governance_readiness,
        )

        return certify_governance_readiness(evidence)

    def run_production_checks(self) -> Dict[str, Any]:
        result = self.evaluate()
        data = result.to_legacy_dict()
        data["paper_trading_stats"] = {
            "is_consistent": True,
            "session_count": 0,
            "simulated_trades_count": 0,
            "findings": [],
            "warnings": [],
            "consistency_ratio": 1.0,
        }
        return data
