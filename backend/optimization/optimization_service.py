"""
Optimization Service Coordinator for CSS Trading Optimization Framework
"""

from typing import Dict, Any, List
from backend.intelligence.intelligence_service import IntelligenceService
from backend.optimization.parameter_optimizer import ParameterOptimizer
from backend.optimization.performance_optimizer import PerformanceOptimizer
from backend.optimization.allocation_optimizer import AllocationOptimizer
from backend.optimization.confidence_optimizer import ConfidenceOptimizer
from backend.optimization.risk_optimizer import RiskOptimizer
from backend.optimization.optimizer_reports import OptimizerReports

class OptimizationService:
    """
    Main service orchestrating advisory-only trading optimizations.
    """
    def __init__(self, intelligence_service: IntelligenceService, reporting_service: Any = None):
        self.intelligence_service = intelligence_service
        self.parameter_optimizer = ParameterOptimizer()
        self.performance_optimizer = PerformanceOptimizer()
        self.allocation_optimizer = AllocationOptimizer()
        self.confidence_optimizer = ConfidenceOptimizer()
        self.risk_optimizer = RiskOptimizer()
        self.optimizer_reports = OptimizerReports(reporting_service) if reporting_service else None

    def get_optimizations(self) -> Dict[str, Any]:
        """Aggregate analysis and return advisory recommendations only."""
        intel_report = self.intelligence_service.get_trading_intelligence_report()
        
        params = self.parameter_optimizer.optimize_parameters(intel_report.get("win_loss_statistics", {}))
        gap_recs = self.performance_optimizer.analyze_performance_gaps(intel_report.get("asset_class_performance", {}))
        alloc = self.allocation_optimizer.optimize_allocation(intel_report.get("portfolio_concentration", {}))
        threshold = self.confidence_optimizer.optimize_confidence_thresholds(
            intel_report.get("market_regime", "UNKNOWN")
        )
        risk = self.risk_optimizer.optimize_risk_parameters(intel_report.get("drawdown_trends", {}))
        
        recommendations = []
        recommendations.append(f"Adjust target leverage to {params['recommended_leverage']}x and risk multiplier to {params['recommended_risk_multiplier']}x.")
        recommendations.append(alloc["action_recommendation"])
        recommendations.append(f"Set advisory trade confidence approval threshold to {threshold * 100:.1f}%.")
        recommendations.append(f"Tighten suggested drawdown limits to {risk['suggested_drawdown']}% with exposure caps of {risk['exposure_cap'] * 100:.1f}%.")
        recommendations.extend(gap_recs)
        
        return {
            "advisory_only": True,
            "execution_allowed": False,
            "parameter_tuning": params,
            "allocation_tuning": alloc,
            "confidence_threshold": threshold,
            "risk_tuning": risk,
            "gap_recommendations": gap_recs,
            "overall_recommendations": recommendations
        }

    def generate_reports(self, optimization_results: Dict[str, Any] = None) -> Dict[str, Any]:
        """Generate optimization reports through the reporting framework."""
        if self.optimizer_reports is None:
            raise ValueError("Reporting service is required to generate optimization reports.")

        results = optimization_results or self.get_optimizations()
        return {
            "optimization": self.optimizer_reports.generate_optimization_report(results),
            "risk_optimization": self.optimizer_reports.generate_risk_optimization_report(results["risk_tuning"]),
        }
