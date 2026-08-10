"""
Unit and Integration Tests for CSS Phase 163 - Endurance Validation & Pilot Gate
"""

import pytest
import os
import tempfile
import time
import json
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

# Import Phase 163 classes
from backend.validation.endurance_evidence import CanonicalEnduranceEvidence
from backend.validation.controlled_pilot_gate import ControlledPilotGate
from backend.validation.pilot_risk_controls import PilotRiskControls
from backend.validation.operational_acceptance import OperationalAcceptanceFramework
from backend.validation.production_governance import ProductionGovernanceFramework


@pytest.fixture
def temp_dir():
    with tempfile.TemporaryDirectory() as td:
        yield td


@pytest.fixture
def setup_platform(temp_dir, monkeypatch):
    # Synthetic infrastructure prerequisite for canonical readiness.
    synthetic_env = os.path.join(temp_dir, ".env")
    with open(synthetic_env, "w", encoding="utf-8") as handle:
        handle.write("# synthetic Phase 162/163 readiness fixture\n")
    original_cwd = os.getcwd()
    monkeypatch.chdir(temp_dir)
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
    try:
        yield dashboard_service
    finally:
        # Restore cwd before TemporaryDirectory teardown on Windows.
        monkeypatch.chdir(original_cwd)


def test_endurance_evidence_reboot_detection(temp_dir):
    session_file = os.path.join(temp_dir, "endurance_session.json")
    
    # Simulate first initialization
    evidence = CanonicalEnduranceEvidence(file_path=session_file)
    evidence.load_session()
    evidence.record_heartbeat(120.0)
    
    # Verify save payload
    with open(session_file, "r") as f:
        saved_data = json.load(f)
    assert saved_data["pid"] == os.getpid()
    
    # Modify save payload to simulate a host reboot (different boot time and different pid)
    saved_data["pid"] = 99999
    saved_data["host_boot_time"] = saved_data["host_boot_time"] - 1000.0  # Mismatched boot time
    with open(session_file, "w") as f:
        json.dump(saved_data, f)
        
    # Reload session
    new_evidence = CanonicalEnduranceEvidence(file_path=session_file)
    new_evidence.load_session()
    assert new_evidence.host_restart_count == 1
    assert "host_reboot_detected" in new_evidence.warnings
    assert new_evidence.uninterrupted_runtime_duration == 0.0


def test_endurance_evidence_css_restart(temp_dir):
    session_file = os.path.join(temp_dir, "endurance_session.json")
    
    # Simulate first initialization
    evidence = CanonicalEnduranceEvidence(file_path=session_file)
    evidence.load_session()
    evidence.record_heartbeat(120.0)
    
    with open(session_file, "r") as f:
        saved_data = json.load(f)
        
    # Simulate process restart (pid changed but boot time remains same)
    saved_data["pid"] = 99999
    with open(session_file, "w") as f:
        json.dump(saved_data, f)
        
    new_evidence = CanonicalEnduranceEvidence(file_path=session_file)
    new_evidence.load_session()
    assert new_evidence.restart_count == 1
    assert "css_process_restart_detected" in new_evidence.warnings
    assert new_evidence.uninterrupted_runtime_duration == 0.0


def test_endurance_evidence_pass_fail_logic(temp_dir):
    session_file = os.path.join(temp_dir, "endurance_session.json")
    evidence = CanonicalEnduranceEvidence(file_path=session_file)
    evidence.load_session()
    
    # 1. Initially fail because duration is incomplete
    res = evidence.evaluate_result(target_hours=72.0)
    assert res["result"] == "FAIL"
    assert "endurance_duration_incomplete" in res["blockers"]
    
    # 2. Simulate complete duration
    evidence.validation_start_time = time.time() - (73.0 * 3600.0)
    res_pass = evidence.evaluate_result(target_hours=72.0)
    assert res_pass["result"] == "PASS"
    assert len(res_pass["blockers"]) == 0
    assert res_pass["evidence_completeness"] == 100.0


def test_controlled_pilot_gate_blockers(setup_platform, temp_dir):
    session_file = os.path.join(temp_dir, "endurance_session.json")
    evidence = CanonicalEnduranceEvidence(file_path=session_file)
    evidence.load_session()
    
    acceptance = OperationalAcceptanceFramework(dashboard_service=setup_platform)
    gov = ProductionGovernanceFramework()
    
    gate = ControlledPilotGate(
        endurance_evidence=evidence,
        operational_acceptance=acceptance,
        governance_framework=gov,
        broker_readiness_score=100.0,
        env_config_present=True
    )
    
    # Initial NO GO
    eval_res = gate.evaluate_gate()
    assert eval_res["decision"] == "NO GO"
    assert "endurance_check_failed" in eval_res["blockers"]
    assert "governance_approvals_missing" in eval_res["blockers"]
    
    # Satisfy endurance and governance
    evidence.validation_start_time = time.time() - (73.0 * 3600.0)
    gov.acknowledge_operator()
    gov.authorize_live_trading()
    gov.approve_deployment()
    
    eval_pass = gate.evaluate_gate()
    assert eval_pass["decision"] == "GO"
    assert len(eval_pass["blockers"]) == 0


def test_pilot_risk_controls():
    risk = PilotRiskControls()
    
    # Test valid limits
    res = risk.validate_exposure(
        symbol="EUR_USD",
        size=50.0,
        broker="OANDA",
        current_open_positions=1,
        daily_loss=10.0,
        drawdown=5.0
    )
    assert res["status"] == "FAIL"  # Fails due to missing operator auth
    
    risk.authorize_operator()
    res_authorized = risk.validate_exposure(
        symbol="EUR_USD",
        size=50.0,
        broker="OANDA",
        current_open_positions=1,
        daily_loss=10.0,
        drawdown=5.0
    )
    assert res_authorized["status"] == "PASS"
    
    # Test drawdown violation
    res_drawdown = risk.validate_exposure(
        symbol="EUR_USD",
        size=50.0,
        broker="OANDA",
        current_open_positions=1,
        daily_loss=10.0,
        drawdown=30.0
    )
    assert res_drawdown["status"] == "FAIL"
    assert "max_drawdown_limit_violated" in res_drawdown["violations"]


def test_dashboard_enrichment(setup_platform):
    view = setup_platform.get_operational_command_centre_view()
    
    assert "endurance_elapsed_time" in view
    assert "uninterrupted_runtime_duration" in view
    assert "host_restart_count" in view
    assert "css_restart_count" in view
    assert "broker_reconnect_count" in view
    assert "memory_baseline" in view
    assert "memory_peak" in view
    assert "current_endurance_status" in view
    assert "evidence_completeness" in view
    assert "active_blockers" in view
    assert "controlled_pilot_readiness" in view
    assert "latest_go_no_go_decision" in view
