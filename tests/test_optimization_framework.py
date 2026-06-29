"""
Tests for CSS Trading Optimization Framework (EWP-6 PART B)
"""

import pytest
import os
import tempfile
from backend.events.event_models import Event
from backend.events.visibility_layer import EventVisibilityLayer
from backend.metrics.metrics_service import MetricsService
from backend.metrics.metrics_registry import MetricsRegistry
from backend.metrics.telemetry import TelemetryCollector
from backend.metrics.metrics_history import MetricsHistory
from backend.intelligence.intelligence_service import IntelligenceService
from backend.optimization.optimization_service import OptimizationService
from backend.optimization.parameter_optimizer import ParameterOptimizer
from backend.optimization.confidence_optimizer import ConfidenceOptimizer
from backend.optimization.allocation_optimizer import AllocationOptimizer
from backend.optimization.performance_optimizer import PerformanceOptimizer
from backend.optimization.risk_optimizer import RiskOptimizer
from backend.reporting.reporting_service import ReportingService, ReportingConfig
from backend.reporting.report_generator import ReportGenerator
from backend.reporting.report_archive import ReportArchive
from backend.reporting.report_history import ReportHistory
from backend.reporting.report_scheduler import ReportScheduler
from backend.reporting.report_templates import ReportTemplates
from backend.dashboard.dashboard_service import DashboardService


def test_parameter_optimization():
    # Low win rate stats
    low_win = {"win_rate": 0.35}
    opt_low = ParameterOptimizer.optimize_parameters(low_win)
    assert opt_low["recommended_leverage"] == 1.0
    assert opt_low["recommended_risk_multiplier"] == 0.7
    
    # High win rate stats
    high_win = {"win_rate": 0.75}
    opt_high = ParameterOptimizer.optimize_parameters(high_win)
    assert opt_high["recommended_leverage"] == 3.0
    assert opt_high["recommended_risk_multiplier"] == 1.2


def test_risk_optimization():
    # High drawdown check
    drawdown_high = {"max_drawdown": 12.0}
    opt_risk = RiskOptimizer.optimize_risk_parameters(drawdown_high)
    assert opt_risk["suggested_drawdown"] == 8.0
    assert opt_risk["exposure_cap"] == 0.15
    
    # Healthy drawdown check
    drawdown_low = {"max_drawdown": 3.0}
    opt_risk_low = RiskOptimizer.optimize_risk_parameters(drawdown_low)
    assert opt_risk_low["suggested_drawdown"] == 15.0
    assert opt_risk_low["exposure_cap"] == 0.25


def test_confidence_allocation_and_performance_optimization():
    assert ConfidenceOptimizer.optimize_confidence_thresholds("HIGH_VOLATILITY") == 0.75
    assert ConfidenceOptimizer.optimize_confidence_thresholds("BEARISH") == 0.70
    assert ConfidenceOptimizer.optimize_confidence_thresholds("RANGE_BOUND") == 0.60

    high_concentration = {
        "risk_concentration_score": 55.0,
        "highest_exposure_asset": "CRYPTO",
    }
    allocation = AllocationOptimizer.optimize_allocation(high_concentration)
    assert allocation["target_allocation"]["CRYPTO"] == 0.30
    assert "Cap CRYPTO" in allocation["action_recommendation"]

    gaps = PerformanceOptimizer.analyze_performance_gaps(
        {
            "EQUITIES": {"total_pnl": 100.0},
            "FX": {"total_pnl": -25.0},
        }
    )
    assert len(gaps) == 1
    assert "FX" in gaps[0]


def test_optimization_service_aggregation():
    with tempfile.TemporaryDirectory() as temp_dir:
        # Setup metrics
        m_reg = MetricsRegistry()
        m_tel = TelemetryCollector()
        m_hist = MetricsHistory(file_path=os.path.join(temp_dir, "metrics.json"))
        metrics_service = MetricsService(registry=m_reg, telemetry=m_tel, history=m_hist)
        
        # Setup visibility
        v_layer = EventVisibilityLayer(
            event_store_file=os.path.join(temp_dir, "events.jsonl"),
            notification_queue_file=os.path.join(temp_dir, "notif_q.json"),
            notification_history_file=os.path.join(temp_dir, "notif_h.json"),
            operational_state_file=os.path.join(temp_dir, "ops_state.json"),
            operational_timeline_file=os.path.join(temp_dir, "ops_t.json")
        )
        
        intel = IntelligenceService(visibility_layer=v_layer, metrics_service=metrics_service)
        opt_service = OptimizationService(intelligence_service=intel)
        
        opts = opt_service.get_optimizations()
        assert opts["advisory_only"] is True
        assert opts["execution_allowed"] is False
        assert "parameter_tuning" in opts
        assert "allocation_tuning" in opts
        assert "confidence_threshold" in opts
        assert "risk_tuning" in opts
        assert "gap_recommendations" in opts
        assert "overall_recommendations" in opts
        assert len(opts["overall_recommendations"]) > 0


def test_optimization_reports_and_dashboard_are_advisory_only(tmp_path):
    class StubIntelligence:
        def get_trading_intelligence_report(self):
            return {
                "market_regime": "HIGH_VOLATILITY",
                "win_loss_statistics": {"win_rate": 0.75},
                "drawdown_trends": {"max_drawdown": 12.0},
                "asset_class_performance": {"CRYPTO": {"total_pnl": -10.0}},
                "portfolio_concentration": {
                    "risk_concentration_score": 60.0,
                    "highest_exposure_asset": "CRYPTO",
                },
            }

    archive_dir = tmp_path / "reports"
    history_file = tmp_path / "report_history.json"
    reporting_service = ReportingService(
        config=ReportingConfig(archive_dir=str(archive_dir), history_file=str(history_file)),
        generator=ReportGenerator(templates=ReportTemplates()),
        archive=ReportArchive(archive_dir=str(archive_dir)),
        history=ReportHistory(history_file=str(history_file)),
        scheduler=ReportScheduler(),
    )
    optimization_service = OptimizationService(
        intelligence_service=StubIntelligence(),
        reporting_service=reporting_service,
    )

    optimizations = optimization_service.get_optimizations()
    reports = optimization_service.generate_reports(optimizations)
    dashboard = DashboardService(read_model=None, optimization_service=optimization_service)
    view = dashboard.get_optimization_advisory_view()

    assert reports["optimization"].payload["report_type"] == "OPTIMIZATION"
    assert reports["risk_optimization"].payload["report_type"] == "RISK_OPTIMIZATION"
    assert "Trading Parameter Optimization Advice" in reports["optimization"].payload["content"]
    assert "Risk Optimization Guidelines" in reports["risk_optimization"].payload["content"]
    assert view["advisory_only"] is True
    assert view["execution_allowed"] is False
    assert view["confidence_threshold"] == 0.75


def test_optimization_framework_exposes_no_execution_hooks():
    service_attrs = dir(OptimizationService)
    optimizer_attrs = (
        dir(ParameterOptimizer)
        + dir(ConfidenceOptimizer)
        + dir(AllocationOptimizer)
        + dir(PerformanceOptimizer)
        + dir(RiskOptimizer)
    )
    forbidden_terms = (
        "submit_order",
        "execute_trade",
        "broker",
        "runtime_supervisor",
        "unified_trade_gate",
        "capital_governor",
    )

    exposed_names = [name.lower() for name in service_attrs + optimizer_attrs]
    assert not any(
        forbidden in exposed_name
        for forbidden in forbidden_terms
        for exposed_name in exposed_names
    )
