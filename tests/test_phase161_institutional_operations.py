"""
Tests for CSS Phase 161 - Institutional Operations Intelligence & Production Readiness
"""

import pytest
import os
import tempfile
from backend.events.event_models import Event
from backend.events.visibility_layer import EventVisibilityLayer
from backend.notifications.notification_service import NotificationService, NotificationConfig
from backend.notifications.notification_queue import NotificationQueue
from backend.notifications.notification_history import NotificationHistory
from backend.notifications.notification_delivery import NotificationDeliveryRouter
from backend.notifications.notification_templates import NotificationTemplates
from backend.notifications.notification_scheduler import NotificationScheduler

from backend.reporting.reporting_service import ReportingService, ReportingConfig
from backend.reporting.report_generator import ReportGenerator
from backend.reporting.report_archive import ReportArchive
from backend.reporting.report_history import ReportHistory
from backend.reporting.report_scheduler import ReportScheduler
from backend.reporting.report_templates import ReportTemplates

from backend.operations.operations_service import OperationsService, OperationsConfig
from backend.operations.health_monitor import HealthMonitor
from backend.operations.operational_state_manager import OperationalStateManager
from backend.operations.operational_timeline import OperationalTimeline
from backend.operations.runtime_statistics import RuntimeStatistics

from backend.metrics.metrics_service import MetricsService
from backend.metrics.metrics_registry import MetricsRegistry
from backend.metrics.telemetry import TelemetryCollector
from backend.metrics.metrics_history import MetricsHistory

from backend.dashboard.dashboard_read_model import DashboardReadModel
from backend.dashboard.dashboard_service import DashboardService
from backend.reporting.executive_decision_brief import ExecutiveDecisionBrief


@pytest.fixture
def temp_dir():
    with tempfile.TemporaryDirectory() as td:
        yield td


@pytest.fixture
def setup_platform(temp_dir):
    # Setup Metrics
    m_reg = MetricsRegistry()
    m_tel = TelemetryCollector()
    m_hist = MetricsHistory(file_path=os.path.join(temp_dir, "metrics_snapshots.json"))
    metrics_service = MetricsService(registry=m_reg, telemetry=m_tel, history=m_hist)
    
    # Setup Notifications
    n_q = NotificationQueue(file_path=os.path.join(temp_dir, "notif_queue.json"))
    n_h = NotificationHistory(file_path=os.path.join(temp_dir, "notif_history.json"))
    notification_service = NotificationService(
        config=NotificationConfig(),
        queue=n_q,
        history=n_h,
        router=NotificationDeliveryRouter(),
        templates=NotificationTemplates(),
        scheduler=NotificationScheduler()
    )
    
    # Setup Reporting
    rep_arch = os.path.join(temp_dir, "reports")
    os.makedirs(rep_arch, exist_ok=True)
    r_hist = ReportHistory(history_file=os.path.join(temp_dir, "report_history.json"))
    reporting_service = ReportingService(
        config=ReportingConfig(archive_dir=rep_arch, history_file=os.path.join(temp_dir, "report_history.json")),
        generator=ReportGenerator(templates=ReportTemplates()),
        archive=ReportArchive(archive_dir=rep_arch),
        history=r_hist,
        scheduler=ReportScheduler()
    )
    
    # Setup Operations
    o_state = os.path.join(temp_dir, "ops_state.json")
    o_timeline = os.path.join(temp_dir, "ops_timeline.json")
    operations_service = OperationsService(
        config=OperationsConfig(state_file=o_state, timeline_file=o_timeline),
        monitor=HealthMonitor(),
        state_manager=OperationalStateManager(file_path=o_state),
        timeline=OperationalTimeline(file_path=o_timeline),
        statistics=RuntimeStatistics()
    )
    
    # Setup Visibility
    visibility_layer = EventVisibilityLayer(
        event_store_file=os.path.join(temp_dir, "events.jsonl"),
        notification_queue_file=os.path.join(temp_dir, "notif_queue.json"),
        notification_history_file=os.path.join(temp_dir, "notif_history.json"),
        operational_state_file=o_state,
        operational_timeline_file=o_timeline
    )
    
    read_model = DashboardReadModel(
        metrics_service=metrics_service,
        operations_service=operations_service,
        notification_service=notification_service,
        reporting_service=reporting_service,
        visibility_layer=visibility_layer
    )
    
    dashboard_service = DashboardService(read_model=read_model)
    return dashboard_service


def test_command_centre_unification(setup_platform):
    view = setup_platform.get_operational_command_centre_view()
    
    # Verify the unified health areas are present
    assert "broker_health" in view
    assert "portfolio_health" in view
    assert "strategy_health" in view
    assert "learning_status" in view
    assert "capital_deployment" in view
    assert "diagnostics" in view

    assert view["broker_health"] in {"GREEN", "AMBER", "RED"}
    assert view["portfolio_health"]["status"] == "OPTIMAL"
    assert "active_strategies" in view["strategy_health"]
    assert view["learning_status"]["feedback_loops_active"] is True
    assert view["capital_deployment"]["mode"] == "ADVISORY"


def test_decision_intelligence_explainability():
    brief_engine = ExecutiveDecisionBrief()
    
    pc = {
        "status": "OK",
        "portfolio_quality": 95.4,
        "expected_return": 12.5,
        "expected_drawdown": 4.5,
        "preferred_portfolio": [
            {"symbol": "SPY", "weight": 0.5},
        ],
        "ranked_opportunities": [
            {"symbol": "SPY", "expected_return": 18.0},
        ],
        "portfolio_resilience": {
            "market_regime": "Risk-On",
        },
        "diversification_optimization": {
            "concentration_score": 35.0,
        }
    }
    comm = {
        "status": "OK",
        "overall_recommendation": "APPROVE",
        "committee_vote": {
            "approve": 6,
            "conditional": 0,
            "reject": 0,
        }
    }
    
    brief = brief_engine.generate_brief(
        portfolio_construction=pc,
        committee=comm,
        decision_confidence={"confidence": 92.5},
        broker_health={"health": "GREEN"},
        runtime_health={"status": "GREEN"}
    )
    
    assert brief["status"] == "OK"
    assert "decision_intelligence" in brief
    intel = brief["decision_intelligence"]
    assert "why_recommendation" in intel
    assert "why_now" in intel
    assert "confidence_level" in intel
    assert "evidence_used" in intel
    assert "capital_allocation_rationale" in intel
    assert "rejected_alternatives" in intel
    
    assert "92.5%" in intel["confidence_level"]
    assert "portfolio_construction" in intel["evidence_used"]


def test_audit_intelligence_consolidation(setup_platform):
    # Setup some test events
    v_layer = setup_platform.read_model.visibility_layer
    
    # Write some events to operations timeline
    event1 = Event(
        event_type="TRADE_APPROVED",
        severity="INFO",
        category="DECISIONS",
        source="gate",
        payload={"trade_id": "T1", "message": "Approved"}
    )
    event2 = Event(
        event_type="RUNTIME_STARTED",
        severity="INFO",
        category="RUNTIME",
        source="supervisor",
        payload={"message": "System runtime started"}
    )
    
    # Save them
    setup_platform.read_model.operations_service.timeline.save([event1, event2])
    
    # Retrieve audit views
    audit_trail = setup_platform.get_audit_intelligence_view()
    assert len(audit_trail["decisions"]) == 1
    assert len(audit_trail["runtime_events"]) == 1
    
    report = setup_platform.get_audit_trail_report()
    assert "# Capital Strata Systems (CSS) Institutional Audit Report" in report
    assert "T1" in report


def test_canonical_readiness_checks(setup_platform):
    readiness = setup_platform.get_canonical_readiness_view()
    assert "status" in readiness
    assert "go_no_go" in readiness
    assert "readiness_score" in readiness
    assert readiness["readiness_score"] >= 0.0


def test_production_validation_framework(setup_platform):
    validation = setup_platform.get_production_validation_view()
    assert "status" in validation
    assert "informational_findings" in validation
    assert "safety_validation_advisory_only_locked" in validation["informational_findings"]


def test_executive_reporting_engine_views(setup_platform):
    # Test multiple reporting views
    exec_report = setup_platform.get_consolidated_report(view_type="EXECUTIVE")
    assert exec_report["view_type"] == "EXECUTIVE"
    assert "readiness_score" in exec_report
    
    committee_report = setup_platform.get_consolidated_report(view_type="INVESTMENT_COMMITTEE")
    assert committee_report["view_type"] == "INVESTMENT_COMMITTEE"
    assert committee_report["recommendation"] == "APPROVE"
    
    ops_report = setup_platform.get_consolidated_report(view_type="OPERATIONS")
    assert ops_report["view_type"] == "OPERATIONS"
    assert ops_report["runtime_health"] == "GREEN"
    
    audit_report = setup_platform.get_consolidated_report(view_type="AUDIT")
    assert audit_report["view_type"] == "AUDIT"
    assert "decisions" in audit_report
