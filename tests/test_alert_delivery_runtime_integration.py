from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from backend.monitoring.alert_bridge import CanonicalAlertBridge
from backend.monitoring.alert_repository import AlertCentreCompatibilityAdapter, AlertRepository
from backend.runtime.css_runtime_supervisor import CSSRuntimeSupervisor
from backend.runtime.runtime_supervisor import RuntimeSupervisor
from launcher import css_mobile_launcher


class _NoopAlertService:
    def dispatch_alert(self, event_type, message, context=None):
        return {
            "event_type": str(event_type),
            "message": message,
            "context": context or {},
        }


def test_supervisor_recovery_creates_canonical_alert(tmp_path: Path) -> None:
    repo = AlertRepository(storage_dir=str(tmp_path / "alerts"))
    supervisor = CSSRuntimeSupervisor(
        state_dir=str(tmp_path / "state"),
        trusted_root=tmp_path,
        canonical_alert_bridge=CanonicalAlertBridge(repo),
    )

    supervisor.record_restart_success("css_runtime", 1)

    alerts = repo.load_alerts()
    assert any(item["event_type"] == "SUPERVISOR_RECOVERY" for item in alerts)


def test_runtime_failure_creates_canonical_alert(tmp_path: Path) -> None:
    repo = AlertRepository(storage_dir=str(tmp_path / "alerts"))
    supervisor = RuntimeSupervisor(
        state_file=tmp_path / "runtime_supervisor.json",
        broker_disconnect_alert_threshold=1,
        alert_service=_NoopAlertService(),
        canonical_alert_bridge=CanonicalAlertBridge(repo),
    )

    supervisor.record_error("simulated runtime error")

    alerts = repo.load_alerts()
    assert any(item["event_type"] == "RUNTIME_FAILURE" for item in alerts)


def test_heartbeat_stale_creates_canonical_alert(tmp_path: Path) -> None:
    repo = AlertRepository(storage_dir=str(tmp_path / "alerts"))
    supervisor = CSSRuntimeSupervisor(
        state_dir=str(tmp_path / "state"),
        trusted_root=tmp_path,
        canonical_alert_bridge=CanonicalAlertBridge(repo),
    )

    stale_time = datetime.now(timezone.utc) - timedelta(seconds=900)
    supervisor.last_heartbeat_at = stale_time.isoformat()
    supervisor.status = "RUNNING"

    assert supervisor.check_stale_heartbeat(stale_threshold_seconds=10) is True

    alerts = repo.load_alerts()
    assert any(item["event_type"] == "HEARTBEAT_STALE" for item in alerts)


def test_broker_disconnect_creates_canonical_alert(tmp_path: Path) -> None:
    repo = AlertRepository(storage_dir=str(tmp_path / "alerts"))
    supervisor = RuntimeSupervisor(
        state_file=tmp_path / "runtime_supervisor.json",
        broker_disconnect_alert_threshold=1,
        alert_service=_NoopAlertService(),
        canonical_alert_bridge=CanonicalAlertBridge(repo),
    )

    supervisor.record_broker_disconnect("oanda", "connection dropped")

    alerts = repo.load_alerts()
    assert any(item["event_type"] == "BROKER_DISCONNECT" for item in alerts)


def test_mobile_feed_reads_canonical_alerts(tmp_path: Path, monkeypatch) -> None:
    alerts_dir = tmp_path / "alerts"
    repo = AlertRepository(storage_dir=str(alerts_dir))
    repo.persist_alert(
        {
            "severity": "CRITICAL",
            "event_type": "RUNTIME_FAILURE",
            "source": "runtime",
            "message": "runtime failure detected",
            "details": {"component": "engine"},
            "dedupe_key": "runtime:failure:mobile",
        }
    )

    monkeypatch.setattr(css_mobile_launcher.LauncherConfig, "ALERTS_DIR", str(alerts_dir))

    context = css_mobile_launcher.build_mobile_dashboard_context()
    assert context["alerts"]
    assert context["alerts"][0]["event_type"] == "RUNTIME_FAILURE"


def test_launcher_feed_reads_canonical_alerts(tmp_path: Path, monkeypatch) -> None:
    alerts_dir = tmp_path / "alerts"
    repo = AlertRepository(storage_dir=str(alerts_dir))
    repo.persist_alert(
        {
            "severity": "CRITICAL",
            "event_type": "SUPERVISOR_RECOVERY",
            "source": "runtime",
            "message": "supervisor recovered",
            "details": {},
            "dedupe_key": "runtime:recovery:launcher",
        }
    )

    monkeypatch.setattr(css_mobile_launcher.LauncherConfig, "ALERTS_DIR", str(alerts_dir))

    context = css_mobile_launcher.build_launcher_context()
    assert context["recent_alerts"]
    assert context["recent_alerts"][0]["event_type"] == "SUPERVISOR_RECOVERY"


def test_acknowledge_alert_flow(tmp_path: Path) -> None:
    repo = AlertRepository(storage_dir=str(tmp_path / "alerts"))
    created = repo.persist_alert(
        {
            "severity": "CRITICAL",
            "event_type": "RUNTIME_FAILURE",
            "source": "runtime",
            "message": "ack me",
            "details": {},
            "dedupe_key": "runtime:ack:1",
        }
    )

    assert repo.acknowledge_alert(created["alert_id"]) is True

    refreshed = repo.load_alerts()
    target = next(item for item in refreshed if item["alert_id"] == created["alert_id"])
    assert target["acknowledged"] is True


def test_dedupe_remains_enforced(tmp_path: Path) -> None:
    repo = AlertRepository(storage_dir=str(tmp_path / "alerts"))
    bridge = CanonicalAlertBridge(repo)

    bridge.record_runtime_failure(
        source="runtime_supervisor",
        message="same failure",
        details={"code": "E1"},
        dedupe_key="runtime:dedupe:e1",
    )
    bridge.record_runtime_failure(
        source="runtime_supervisor",
        message="same failure again",
        details={"code": "E1"},
        dedupe_key="runtime:dedupe:e1",
    )

    alerts = repo.load_alerts()
    assert len(alerts) == 1

    adapter = AlertCentreCompatibilityAdapter(repo)
    feed = adapter.build_payload(limit=5)
    assert len(feed) == 1
