"""
Optimizer Report Builders for CSS Optimization Framework
"""

from typing import Dict, Any

class OptimizerReports:
    """
    Triggers optimization advisory reports via the ReportingService.
    """
    def __init__(self, reporting_service):
        self.reporting_service = reporting_service

    def generate_optimization_report(self, optimization_results: Dict[str, Any]) -> Any:
        """Trigger parameter optimization guidelines report."""
        params = optimization_results.get("parameter_tuning", {})
        context = {
            "recommended_leverage": params.get("recommended_leverage", 2.0),
            "recommended_risk_multiplier": params.get("recommended_risk_multiplier", 1.0)
        }
        return self.reporting_service.create_report(
            report_type="OPTIMIZATION",
            title="Trading Parameter Optimization Advice",
            context=context,
            metadata={"source": "optimization_framework", "advisory_only": True}
        )

    def generate_risk_optimization_report(self, risk_results: Dict[str, Any]) -> Any:
        """Trigger risk parameters optimization report."""
        context = {
            "suggested_drawdown": risk_results.get("suggested_drawdown", 15.0),
            "exposure_cap": risk_results.get("exposure_cap", 0.25)
        }
        return self.reporting_service.create_report(
            report_type="RISK_OPTIMIZATION",
            title="Risk Optimization Guidelines",
            context=context,
            metadata={"source": "optimization_framework", "advisory_only": True}
        )
