"""
Tests for CSS Executive Dashboard (EWP-3 PART A)
"""

import pytest
import os
import tempfile
import time
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


def test_dashboard_read_only_aggregation(setup_platform):
    # Inject dummy event via metrics registry to trigger stats counts
    setup_platform.read_model.metrics_service.registry.increment("events_published", 12)
    setup_platform.read_model.metrics_service.registry.increment("trades_approved", 5)

    summary = setup_platform.get_executive_summary()
    assert summary["enterprise_health_score"] == 100.0
    assert summary["recent_events_count"] == 12
    assert summary["metrics_summary"]["trades_approved"] == 5

    # Check read-only behavior: there should be no mutate or send trade endpoints
    assert hasattr(setup_platform, "get_executive_summary")
    assert not hasattr(setup_platform, "submit_order")
