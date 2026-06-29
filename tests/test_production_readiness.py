"""
Production readiness dashboard and report integration tests.
"""

from backend.certification import CertificationService
from backend.dashboard.dashboard_service import DashboardService
from backend.events.event_bus import EventBus
from backend.reporting import (
    ReportArchive,
    ReportGenerator,
    ReportHistory,
    ReportScheduler,
    ReportTemplates,
    ReportingConfig,
    ReportingService,
)


class FakeMetricsService:
    def get_current_health(self):
        return {
            "runtime_health": 100.0,
            "notification_health": 100.0,
            "reporting_health": 100.0,
            "operations_health": 100.0,
            "overall_health_score": 100.0,
        }

    def get_current_metrics(self):
        return {"events_published": 10, "reports_generated": 2}


class FakeVisibilityLayer:
    def get_operations_summary(self):
        return {
            "overall_status": "HEALTHY",
            "health_score": 100.0,
            "component_states": {"runtime": "OK"},
        }

    def get_notification_summary(self):
        return {"queue_count": 0, "sent_count": 5, "failed_count": 0}


class FakeReadModel:
    def __init__(self):
        self.metrics_service = FakeMetricsService()
        self.visibility_layer = FakeVisibilityLayer()

    def get_enterprise_health(self):
        return self.metrics_service.get_current_health()

    def get_runtime_status(self):
        return "HEALTHY"

    def get_recent_events(self, limit=50):
        return []

    def get_report_status(self):
        return {"total_generated": 2, "recent_reports": [{"title": "Daily"}]}


def reporting_service(tmp_path):
    archive_dir = tmp_path / "reports"
    history_file = tmp_path / "report_history.json"
    return ReportingService(
        config=ReportingConfig(archive_dir=str(archive_dir), history_file=str(history_file)),
        generator=ReportGenerator(templates=ReportTemplates()),
        archive=ReportArchive(archive_dir=str(archive_dir)),
        history=ReportHistory(history_file=str(history_file)),
        scheduler=ReportScheduler(),
    )


def wired_event_bus():
    bus = EventBus()
    bus.subscribe("RUNTIME_STARTED", lambda event: None)
    bus.subscribe("*", lambda event: None)
    return bus


def test_dashboard_includes_read_only_certification_section():
    read_model = FakeReadModel()
    dashboard = DashboardService(read_model=read_model)
    service = CertificationService(
        read_model=read_model,
        event_bus=wired_event_bus(),
        dashboard_service=dashboard,
    )
    dashboard.certification_engine = service

    section = dashboard.get_certification_readiness_view()

    assert section["overall_readiness_score"] == 100.0
    assert section["certification_status"] == "PASS"
    assert section["critical_findings_count"] == 0
    assert section["warning_count"] == 0
    assert section["information_count"] == 0
    assert section["last_certification_time"]


def test_report_generation_uses_existing_reporting_framework(tmp_path):
    service = CertificationService(
        read_model=FakeReadModel(),
        event_bus=wired_event_bus(),
        reporting_service=reporting_service(tmp_path),
    )
    result = service.certify()

    reports = service.generate_reports(result)

    assert set(reports.keys()) == {
        "production_readiness",
        "certification",
        "deployment_checklist",
    }
    assert reports["production_readiness"].payload["report_type"] == "PRODUCTION_READINESS"
    assert reports["certification"].payload["report_type"] == "CERTIFICATION"
    assert reports["deployment_checklist"].payload["report_type"] == "DEPLOYMENT_CHECKLIST"
    assert "Production Readiness Report" in reports["production_readiness"].payload["content"]
    assert "Deployment Checklist Report" in reports["deployment_checklist"].payload["content"]


def test_legacy_production_checks_shape_is_available():
    from backend.certification import CertificationEngine

    engine = CertificationEngine(read_model=FakeReadModel(), event_bus=wired_event_bus())

    checks = engine.run_production_checks()

    assert "overall_readiness_score" in checks
    assert "deployment_recommendation" in checks
    assert "critical_findings" in checks
    assert "warnings" in checks
    assert "recommended_actions" in checks
