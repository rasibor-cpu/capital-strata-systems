"""
Unit and Integration Tests for CSS Phase 162 - Production Pilot & Operational Acceptance
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

# Import Phase 162 classes
from backend.runtime.production_pilot import ProductionPilotFramework
from backend.validation.operational_acceptance import OperationalAcceptanceFramework
from backend.validation.long_duration_stability import LongDurationStabilityFramework
from backend.validation.production_governance import ProductionGovernanceFramework
from backend.validation.production_go_no_go import ProductionGoNoGoEngine
from backend.validation.canonical_readiness import CanonicalReadinessFramework


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


def test_production_pilot_framework():
    pilot = ProductionPilotFramework()
    assert pilot.state == "INACTIVE"
    
    # Attempt to start without approvals
    result = pilot.start_pilot()
    assert "NO_GO" in result
    
    # Approve and start
    pilot.approve_pilot("operator_signoff")
    pilot.approve_pilot("risk_committee")
    pilot.approve_pilot("deployment_approval")
    
    result = pilot.start_pilot()
    assert result == "RUNNING"
    assert pilot.state == "RUNNING"
    
    # Trigger connection drop rollback
    pilot.record_connection_drop()
    pilot.record_connection_drop()
    pilot.record_connection_drop()  # Exceeds max drops
    assert pilot.state == "ROLLED_BACK"
    assert pilot.rollback_reason == "Max connection drops exceeded"


def test_drawdown_rollback():
    pilot = ProductionPilotFramework()
    pilot.approve_pilot("operator_signoff")
    pilot.approve_pilot("risk_committee")
    pilot.approve_pilot("deployment_approval")
    pilot.start_pilot()
    
    # Simulate trade loss of $30 on $1000 max capital (3.0% drawdown, max drawdown is 2.0%)
    pilot.record_pnl(-30.0)
    assert pilot.state == "ROLLED_BACK"
    assert "drawdown" in pilot.rollback_reason.lower()


def test_operational_acceptance_testing(setup_platform):
    acceptance = OperationalAcceptanceFramework(dashboard_service=setup_platform)
    report = acceptance.validate_acceptance()
    assert "status" in report
    assert report["status"] == "PASS"
    assert "runtime_stability" in report["results"]


def test_long_duration_stability():
    stability = LongDurationStabilityFramework()
    stability.record_reconnect()
    stability.record_refresh()
    stability.track_memory(50.0)
    
    report = stability.run_endurance_check()
    assert report["status"] == "PASS"
    
    # Trigger memory growth failure
    stability.track_memory(300.0)
    report_fail = stability.run_endurance_check()
    assert report_fail["status"] == "FAIL"
    assert "memory_leak_detected" in report_fail["critical_findings"]


def test_production_governance():
    gov = ProductionGovernanceFramework()
    check = gov.check_governance()
    assert check["status"] == "FAIL"
    assert "operator_acknowledgement_missing" in check["blockers"]
    
    gov.acknowledge_operator()
    gov.authorize_live_trading()
    gov.approve_deployment()
    
    check_pass = gov.check_governance()
    assert check_pass["status"] == "PASS"


def test_go_no_go_engine(setup_platform):
    readiness = CanonicalReadinessFramework(dashboard_service=setup_platform)
    acceptance = OperationalAcceptanceFramework(dashboard_service=setup_platform)
    gov = ProductionGovernanceFramework()
    
    engine = ProductionGoNoGoEngine(
        readiness_framework=readiness,
        operational_acceptance=acceptance,
        governance_framework=gov
    )
    
    # Initial NO GO due to governance checkers
    decision = engine.evaluate_decision()
    assert decision["decision"] == "NO GO"
    
    # Solve blockers
    gov.acknowledge_operator()
    gov.authorize_live_trading()
    gov.approve_deployment()
    
    decision_pass = engine.evaluate_decision()
    assert decision_pass["decision"] == "GO"


def test_dashboard_extended_command_centre(setup_platform):
    view = setup_platform.get_operational_command_centre_view()
    
    assert "production_readiness" in view
    assert "pilot_status" in view
    assert "operational_acceptance" in view
    assert "go_no_go_status" in view
    assert "outstanding_blockers" in view
    assert "active_operational_risks" in view
    assert "executive_summary" in view
