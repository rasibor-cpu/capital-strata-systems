import os
import json
import tempfile
import pytest

from launcher.css_launcher_config import LauncherConfig
from launcher.css_mobile_launcher import (
    get_supervisor_summary,
    get_alert_summary,
    get_mobile_launcher_status,
    build_launcher_context
)

@pytest.fixture
def launcher_temp_dir():
    with tempfile.TemporaryDirectory() as td:
        # Save original config
        orig_runtime = LauncherConfig.RUNTIME_DIR
        orig_state = LauncherConfig.SUPERVISOR_STATE_FILE
        orig_alerts = LauncherConfig.ALERTS_DIR
        
        # Mock paths
        LauncherConfig.RUNTIME_DIR = td
        LauncherConfig.SUPERVISOR_STATE_FILE = os.path.join(td, "supervisor", "css_runtime_supervisor_state.json")
        LauncherConfig.ALERTS_DIR = os.path.join(td, "alerts")
        
        yield td
        
        # Restore config
        LauncherConfig.RUNTIME_DIR = orig_runtime
        LauncherConfig.SUPERVISOR_STATE_FILE = orig_state
        LauncherConfig.ALERTS_DIR = orig_alerts

def test_missing_supervisor_state_handled_safely(launcher_temp_dir):
    summary = get_supervisor_summary()
    assert summary["status"] == "UNKNOWN"
    assert summary["last_heartbeat"] == "None"
    assert summary["message"] == "Supervisor state missing"
    
    status = get_mobile_launcher_status()
    assert status == "OFFLINE"

def test_missing_alert_directory_handled_safely(launcher_temp_dir):
    alerts = get_alert_summary()
    assert isinstance(alerts, list)
    assert len(alerts) == 0

def test_launcher_context_builds_successfully(launcher_temp_dir):
    os.makedirs(os.path.dirname(LauncherConfig.SUPERVISOR_STATE_FILE), exist_ok=True)
    with open(LauncherConfig.SUPERVISOR_STATE_FILE, "w") as f:
        json.dump({
            "status": "RUNNING",
            "last_heartbeat": "2026-06-21T12:00:00Z",
            "failure_count": 0,
            "restart_count": 1
        }, f)
        
    os.makedirs(LauncherConfig.ALERTS_DIR, exist_ok=True)
    with open(os.path.join(LauncherConfig.ALERTS_DIR, "1_alert.json"), "w") as f:
        json.dump({"alert_type": "ENGINE", "message": "Test alert", "severity": "INFO"}, f)
        
    context = build_launcher_context()
    
    assert context["title"] == LauncherConfig.TITLE
    assert context["status"] == "ONLINE"
    assert context["supervisor"]["status"] == "RUNNING"
    assert context["supervisor"]["restart_count"] == 1
    assert len(context["recent_alerts"]) == 1
    assert context["recent_alerts"][0]["message"] == "Test alert"

def test_offline_state_handled_safely(launcher_temp_dir):
    os.makedirs(os.path.dirname(LauncherConfig.SUPERVISOR_STATE_FILE), exist_ok=True)
    with open(LauncherConfig.SUPERVISOR_STATE_FILE, "w") as f:
        json.dump({
            "status": "STOPPED",
            "last_heartbeat": "2026-06-21T12:00:00Z",
        }, f)
    
    context = build_launcher_context()
    assert context["status"] == "OFFLINE"
    assert context["supervisor"]["status"] == "STOPPED"

def test_manifest_exists_and_valid_json():
    manifest_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "launcher", "static", "css_launcher_manifest.json")
    assert os.path.exists(manifest_path)
    with open(manifest_path, "r") as f:
        data = json.load(f)
        assert data["name"] == "CSS Mobile Launcher"
        assert data["display"] == "standalone"

def test_icon_asset_exists():
    icon_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "launcher", "static", "css_launcher_icon.svg")
    assert os.path.exists(icon_path)
    
def test_launcher_does_not_expose_secrets(launcher_temp_dir):
    context = build_launcher_context()
    context_str = json.dumps(context).lower()
    
    # Assert no obvious secrets are part of the context
    assert "password" not in context_str
    assert "token" not in context_str
    assert "secret" not in context_str
    assert "key" not in context_str
