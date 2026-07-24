"""
Tests for Component C: Operations Control Centre Foundation
"""

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from backend.operations import (
    create_health_check_event,
    create_state_event,
    HealthMonitor,
    OperationalStateManager,
    OperationalTimeline,
    RuntimeStatistics,
    OperationsConfig,
    OperationsService,
)


def _write_runtime_evidence(
    root: Path,
    *,
    heartbeat: str | None = None,
    risk_state: str = "GREEN",
    gate_status: str = "OPEN",
    broker_section: dict | None = None,
) -> tuple[Path, Path]:
    artifacts = root / "artifacts"
    supervisor = root / "runtime" / "supervisor" / "css_runtime_supervisor_state.json"
    artifacts.mkdir(parents=True, exist_ok=True)
    supervisor.parent.mkdir(parents=True, exist_ok=True)
    now = heartbeat or datetime.now(timezone.utc).isoformat()
    broker = broker_section if broker_section is not None else {
        "selected_broker": "SIMULATED",
        "broker_mode": "paper",
        "overall_status": "GREEN",
        "broker_health": "GREEN",
        "connection_status": "PASS",
        "authentication_status": "PASS",
        "account_data_health": "PASS",
        "balance_position_status": "PASS",
        "market_data_status": "PASS",
        "readiness_score": 100.0,
        "execution_scope": "READ_ONLY",
    }
    (artifacts / "frontend_state.json").write_text(
        json.dumps(
            {
                "payload_schema": "css.frontend.contract.v1",
                "generated_at": now,
                "mission_control_data_source": "RUNTIME",
                "session": {"session_id": "ops-health-test", "engine_mode": "SAFE"},
                "sections": {
                    "risk": {
                        "risk_state": risk_state,
                        "risk_score": 9.0,
                        "gate_status": gate_status,
                    },
                    "broker": broker,
                    "runtime_certification_snapshot": {
                        "certification": "GREEN",
                        "operational_state": "READ_ONLY",
                        "generated_at": now,
                    },
                },
            }
        ),
        encoding="utf-8",
    )
    (artifacts / "css_session_state_pcnrass.json").write_text(
        json.dumps({"session": {"session_id": "ops-health-test", "engine_mode": "SAFE", "cycle_number": 1}}),
        encoding="utf-8",
    )
    (artifacts / "css_account_state_pcnrass.json").write_text(
        json.dumps({"account_balance": 100.0, "total_equity": 100.0, "buying_power": 100.0}),
        encoding="utf-8",
    )
    supervisor.write_text(
        json.dumps({"status": "RUNNING", "last_heartbeat_at": now, "restart_count": 0, "failure_count": 0}),
        encoding="utf-8",
    )
    return artifacts, supervisor

def test_health_check_event_creation():
    event = create_health_check_event(
        component="broker_api",
        status="WARN",
        message="Latency high",
        latency_ms=450.5,
        details={"ping": 450.5}
    )
    assert event.event_type == "HEALTH_CHECK_RESULT"
    assert event.severity == "WARNING"
    assert event.payload["component"] == "broker_api"
    assert event.payload["status"] == "WARN"
    assert event.payload["latency_ms"] == 450.5


def test_monitor_scoring():
    monitor = HealthMonitor()
    
    event_ok = create_health_check_event("c1", "OK", "Fine", 10.0)
    event_warn = create_health_check_event("c2", "WARN", "Degraded", 50.0)
    event_crit = create_health_check_event("c3", "CRITICAL", "Dead", 500.0)

    score_all_ok = monitor.calculate_health_score([event_ok, event_ok])
    assert score_all_ok == 100.0

    score_mixed = monitor.calculate_health_score([event_ok, event_warn])
    assert score_mixed == 75.0

    score_with_crit = monitor.calculate_health_score([event_ok, event_crit])
    assert score_with_crit == 50.0

    score_empty = monitor.calculate_health_score([])
    assert score_empty == 0.0


def test_monitor_wraps_checker_exception_as_critical_event():
    monitor = HealthMonitor()

    def broken_checker():
        raise RuntimeError("boom")

    monitor.register_checker("broken_component", broken_checker)

    results = monitor.execute_checks()

    assert len(results) == 1
    assert results[0].payload["component"] == "broken_component"
    assert results[0].payload["status"] == "CRITICAL"
    assert "Health checker failed" in results[0].payload["message"]

def test_state_manager_and_timeline(tmp_path):
    state_file = tmp_path / "state.json"
    timeline_file = tmp_path / "timeline.json"

    state_mgr = OperationalStateManager(file_path=str(state_file))
    timeline = OperationalTimeline(file_path=str(timeline_file))

    monitor = HealthMonitor()
    statistics = RuntimeStatistics()

    config = OperationsConfig(default_source="ops_control")
    service = OperationsService(
        config=config,
        monitor=monitor,
        state_manager=state_mgr,
        timeline=timeline,
        statistics=statistics
    )

    monitor.register_checker("database", lambda: create_health_check_event("database", "OK", "Connected", 5.0))
    monitor.register_checker("risk_gate", lambda: create_health_check_event("risk_gate", "OK", "Active", 1.0))

    state_event = service.run_diagnostics()
    assert state_event.payload["overall_status"] == "HEALTHY"
    assert state_event.payload["health_score"] == 100.0
    assert len(state_mgr.load()) == 1
    assert state_mgr.load()[0].event_id == state_event.event_id
    assert len(timeline.load()) == 0

    # Modify checker to simulate status change
    monitor.register_checker("risk_gate", lambda: create_health_check_event("risk_gate", "WARN", "Warning limits", 2.0))

    state_event2 = service.run_diagnostics()
    assert state_event2.payload["overall_status"] == "DEGRADED"
    assert state_event2.payload["health_score"] == 75.0

    timeline_events = timeline.load()
    assert len(timeline_events) == 1
    assert timeline_events[0].event_type == "TIMELINE_EVENT"
    assert "transitioned from HEALTHY to DEGRADED" in timeline_events[0].payload["message"]


def test_runtime_statistics():
    stats = RuntimeStatistics()
    stats.increment("messages_processed", 5)
    stats.increment("messages_processed")
    stats.set_gauge("cpu_percent", 14.5)

    summary = stats.get_summary()
    assert summary["counters"]["messages_processed"] == 6
    assert summary["gauges"]["cpu_percent"] == 14.5

    stats.reset()
    assert len(stats.get_summary()["counters"]) == 0


def test_production_health_checkers_pass_with_canonical_evidence(tmp_path):
    from backend.operations.host_activation import activate_operations_service

    artifacts, supervisor = _write_runtime_evidence(tmp_path)
    service = activate_operations_service(
        artifacts_dir=tmp_path / "ops",
        runtime_artifacts_dir=artifacts,
        supervisor_state_path=supervisor,
    )

    state = service.run_diagnostics()

    assert state.payload["overall_status"] == "HEALTHY"
    assert state.payload["health_score"] == 100.0
    assert state.payload["component_states"] == {
        "runtime_heartbeat": "OK",
        "risk_gate": "OK",
        "broker_readiness": "OK",
    }


def test_runtime_heartbeat_checker_fails_closed_when_stale(tmp_path):
    from backend.operations.host_activation import activate_operations_service

    stale = (datetime.now(timezone.utc) - timedelta(minutes=15)).isoformat()
    artifacts, supervisor = _write_runtime_evidence(tmp_path, heartbeat=stale)
    service = activate_operations_service(
        artifacts_dir=tmp_path / "ops",
        runtime_artifacts_dir=artifacts,
        supervisor_state_path=supervisor,
    )

    state = service.run_diagnostics()

    assert state.payload["overall_status"] == "CRITICAL"
    assert state.payload["component_states"]["runtime_heartbeat"] == "CRITICAL"


def test_broker_readiness_checker_fails_closed_when_missing(tmp_path):
    from backend.operations.host_activation import activate_operations_service

    artifacts, supervisor = _write_runtime_evidence(tmp_path, broker_section={})
    service = activate_operations_service(
        artifacts_dir=tmp_path / "ops",
        runtime_artifacts_dir=artifacts,
        supervisor_state_path=supervisor,
    )

    state = service.run_diagnostics()

    assert state.payload["overall_status"] == "CRITICAL"
    assert state.payload["component_states"]["broker_readiness"] == "CRITICAL"


def test_risk_gate_checker_fails_closed_on_failed_gate(tmp_path):
    from backend.operations.host_activation import activate_operations_service

    artifacts, supervisor = _write_runtime_evidence(tmp_path, risk_state="FAIL", gate_status="FAILED")
    service = activate_operations_service(
        artifacts_dir=tmp_path / "ops",
        runtime_artifacts_dir=artifacts,
        supervisor_state_path=supervisor,
    )

    state = service.run_diagnostics()

    assert state.payload["overall_status"] == "CRITICAL"
    assert state.payload["component_states"]["risk_gate"] == "CRITICAL"


def test_observability_tick_reuses_existing_diagnostics(tmp_path, monkeypatch):
    from backend.operations.host_activation import activate_operations_service, run_host_observability_tick

    artifacts, supervisor = _write_runtime_evidence(tmp_path)
    service = activate_operations_service(
        artifacts_dir=tmp_path / "ops",
        runtime_artifacts_dir=artifacts,
        supervisor_state_path=supervisor,
    )
    diagnostics = service.run_diagnostics()

    def fail_if_called_again():
        raise AssertionError("run_diagnostics called twice")

    monkeypatch.setattr(service, "run_diagnostics", fail_if_called_again)
    result = run_host_observability_tick(service, diagnostics=diagnostics)

    assert result["operations_status"] == "HEALTHY"
    assert result["health_score"] == 100.0


def test_ops_health_route_runs_diagnostics_once(monkeypatch):
    from backend.app import main as app_main
    from backend.monitoring import css_alert_repository
    import backend.metrics as metrics_module

    class FakeMetrics:
        def persist_snapshot(self):
            return {"ok": True}

    class FakeAlertRepository:
        def purge_old_alerts(self, keep_latest=500):
            return 0

    class FakeService:
        def __init__(self):
            self.calls = 0

        def run_diagnostics(self):
            self.calls += 1
            return create_state_event(
                overall_status="HEALTHY",
                health_score=100.0,
                component_states={"runtime_heartbeat": "OK"},
            )

    service = FakeService()
    monkeypatch.setattr(metrics_module, "get_default_metrics_service", lambda: FakeMetrics())
    monkeypatch.setattr(css_alert_repository, "CSSAlertRepository", FakeAlertRepository)
    monkeypatch.setattr(app_main, "_ops_service", service)

    response = app_main.ops_health()

    assert response["ok"] is True
    assert response["status"] == "HEALTHY"
    assert service.calls == 1
