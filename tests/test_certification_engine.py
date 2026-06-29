"""
Tests for the CSS Enterprise Certification & Readiness Engine.
"""

from backend.certification import CertificationService
from backend.events.event_bus import EventBus
from backend.events.event_models import Event


class FakeMetricsService:
    def __init__(self, health=None, metrics=None):
        self.health = health or {
            "runtime_health": 100.0,
            "notification_health": 100.0,
            "reporting_health": 100.0,
            "operations_health": 100.0,
            "overall_health_score": 100.0,
        }
        self.metrics = metrics or {"events_published": 10, "reports_generated": 2}

    def get_current_health(self):
        return dict(self.health)

    def get_current_metrics(self):
        return dict(self.metrics)


class FakeVisibilityLayer:
    def __init__(self, runtime_status="HEALTHY"):
        self.runtime_status = runtime_status

    def get_operations_summary(self):
        return {
            "overall_status": self.runtime_status,
            "health_score": 100.0,
            "component_states": {"runtime": "OK"},
        }

    def get_notification_summary(self):
        return {"queue_count": 0, "sent_count": 5, "failed_count": 0}


class FakeReadModel:
    def __init__(self, health=None, runtime_status="HEALTHY", metrics=None, reports=True):
        self.metrics_service = FakeMetricsService(health=health, metrics=metrics)
        self.visibility_layer = FakeVisibilityLayer(runtime_status=runtime_status)
        self.runtime_status = runtime_status
        self.reports = reports
        self.read_calls = 0
        self.write_called = False

    def get_enterprise_health(self):
        self.read_calls += 1
        return self.metrics_service.get_current_health()

    def get_runtime_status(self):
        self.read_calls += 1
        return self.runtime_status

    def get_recent_events(self, limit=50):
        self.read_calls += 1
        return [Event("RUNTIME_STARTED", "INFO", "SYSTEM", "test", {})]

    def get_report_status(self):
        self.read_calls += 1
        if not self.reports:
            return {}
        return {"total_generated": 2, "recent_reports": [{"title": "Daily"}]}

    def submit_order(self, *_args, **_kwargs):
        self.write_called = True
        raise AssertionError("Certification must not submit orders")

    def run_diagnostics(self):
        self.write_called = True
        raise AssertionError("Certification must not run diagnostics")


class FakeDashboardService:
    def get_executive_summary(self):
        return {"enterprise_health_score": 100.0}


def wired_event_bus():
    bus = EventBus()
    bus.subscribe("RUNTIME_STARTED", lambda event: None)
    bus.subscribe("*", lambda event: None)
    return bus


def test_readiness_scoring_passes_for_healthy_platform():
    service = CertificationService(
        read_model=FakeReadModel(),
        event_bus=wired_event_bus(),
        dashboard_service=FakeDashboardService(),
    )

    result = service.certify()

    assert result.status == "PASS"
    assert result.overall_readiness_score == 100.0
    assert len(result.critical_findings) == 0
    assert all(item["status"] == "PASS" for item in result.deployment_checklist)


def test_health_validation_flags_critical_runtime_and_notification_failures():
    health = {
        "runtime_health": 55.0,
        "notification_health": 60.0,
        "reporting_health": 95.0,
        "operations_health": 95.0,
        "overall_health_score": 76.25,
    }
    service = CertificationService(
        read_model=FakeReadModel(health=health, runtime_status="STOPPED"),
        event_bus=wired_event_bus(),
        dashboard_service=FakeDashboardService(),
    )

    result = service.certify()

    assert result.status == "FAIL"
    assert result.overall_readiness_score < 70.0
    assert any(item.subsystem == "Runtime Supervisor" for item in result.critical_findings)
    assert any(item.subsystem == "Notification Framework" for item in result.critical_findings)


def test_warning_findings_generate_advisory_recommendations():
    health = {
        "runtime_health": 100.0,
        "notification_health": 85.0,
        "reporting_health": 100.0,
        "operations_health": 100.0,
        "overall_health_score": 96.25,
    }
    service = CertificationService(
        read_model=FakeReadModel(health=health),
        event_bus=wired_event_bus(),
        dashboard_service=FakeDashboardService(),
    )

    result = service.certify()

    assert result.status == "WARNING"
    assert any("notification" in action.lower() for action in result.recommended_actions)
    assert any("warning findings" in action.lower() for action in result.recommended_actions)


def test_missing_subsystem_data_is_handled_gracefully():
    result = CertificationService().certify()

    assert result.status in {"WARNING", "FAIL"}
    assert result.overall_readiness_score >= 0.0
    assert len(result.informational_findings) >= 1
    assert len(result.deployment_checklist) == 9


def test_certification_evaluation_is_read_only():
    read_model = FakeReadModel()
    bus = wired_event_bus()
    before_subscribers = {
        name: len(callbacks) for name, callbacks in bus._subscribers.items()
    }
    before_wildcards = len(bus._wildcard_subscribers)

    result = CertificationService(
        read_model=read_model,
        event_bus=bus,
        dashboard_service=FakeDashboardService(),
    ).certify()

    after_subscribers = {
        name: len(callbacks) for name, callbacks in bus._subscribers.items()
    }
    assert result.status == "PASS"
    assert read_model.read_calls > 0
    assert read_model.write_called is False
    assert before_subscribers == after_subscribers
    assert before_wildcards == len(bus._wildcard_subscribers)
