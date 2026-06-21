import pytest
import json
from pathlib import Path
from backend.monitoring.css_alert_models import AlertType, AlertSeverity
from backend.monitoring.css_alert_service import CSSAlertService

def test_alert_service_creates_directory(tmp_path):
    storage_dir = tmp_path / "alerts"
    service = CSSAlertService(storage_dir=str(storage_dir))
    
    assert storage_dir.exists()
    assert storage_dir.is_dir()

def test_emit_alert_creates_and_persists_alert(tmp_path):
    storage_dir = tmp_path / "alerts"
    service = CSSAlertService(storage_dir=str(storage_dir))
    
    alert = service.emit_alert(
        alert_type=AlertType.ENGINE,
        severity=AlertSeverity.CRITICAL,
        message="Engine critical failure",
        source="EngineCore",
        metadata={"component": "execution_loop"}
    )
    
    assert alert.alert_id is not None
    assert alert.alert_type == AlertType.ENGINE
    assert alert.severity == AlertSeverity.CRITICAL
    assert alert.message == "Engine critical failure"
    assert alert.source == "EngineCore"
    assert alert.metadata == {"component": "execution_loop"}
    
    # Check persistence
    files = list(storage_dir.glob("*.json"))
    assert len(files) == 1
    
    with open(files[0], "r", encoding="utf-8") as f:
        data = json.load(f)
        assert data["alert_id"] == alert.alert_id
        assert data["alert_type"] == "ENGINE"
        assert data["severity"] == "CRITICAL"
        assert data["message"] == "Engine critical failure"

def test_specific_emit_methods(tmp_path):
    storage_dir = tmp_path / "alerts"
    service = CSSAlertService(storage_dir=str(storage_dir))
    
    a1 = service.emit_engine_alert(AlertSeverity.INFO, "Engine info", "src")
    assert a1.alert_type == AlertType.ENGINE
    assert a1.severity == AlertSeverity.INFO
    
    a2 = service.emit_trade_alert(AlertSeverity.WARNING, "Trade warn", "src")
    assert a2.alert_type == AlertType.TRADE
    assert a2.severity == AlertSeverity.WARNING
    
    a3 = service.emit_risk_alert(AlertSeverity.CRITICAL, "Risk crit", "src")
    assert a3.alert_type == AlertType.RISK
    assert a3.severity == AlertSeverity.CRITICAL
    
    a4 = service.emit_broker_alert(AlertSeverity.INFO, "Broker info", "src")
    assert a4.alert_type == AlertType.BROKER
    assert a4.severity == AlertSeverity.INFO
    
    a5 = service.emit_system_alert(AlertSeverity.WARNING, "System warn", "src")
    assert a5.alert_type == AlertType.SYSTEM
    assert a5.severity == AlertSeverity.WARNING

def test_heartbeat(tmp_path):
    storage_dir = tmp_path / "alerts"
    service = CSSAlertService(storage_dir=str(storage_dir))
    
    alert = service.heartbeat(source="HeartbeatEmitter", metadata={"status": "alive"})
    
    assert alert.alert_type == AlertType.SYSTEM
    assert alert.severity == AlertSeverity.INFO
    assert alert.message == "CSSAlertService Heartbeat"
    assert alert.source == "HeartbeatEmitter"
    assert alert.metadata == {"status": "alive"}
    
    files = list(storage_dir.glob("*.json"))
    assert len(files) == 1
