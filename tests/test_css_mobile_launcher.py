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
        
        orig_artifacts = LauncherConfig.ARTIFACTS_DIR
        orig_account = LauncherConfig.ACCOUNT_STATE_FILE
        orig_session = LauncherConfig.SESSION_STATE_FILE
        orig_ledger = LauncherConfig.CLOSED_TRADE_LEDGER_PATH
        
        # Mock paths
        LauncherConfig.RUNTIME_DIR = td
        LauncherConfig.SUPERVISOR_STATE_FILE = os.path.join(td, "supervisor", "css_runtime_supervisor_state.json")
        LauncherConfig.ALERTS_DIR = os.path.join(td, "alerts")
        
        LauncherConfig.ARTIFACTS_DIR = os.path.join(td, "artifacts")
        LauncherConfig.ACCOUNT_STATE_FILE = os.path.join(td, "artifacts", "css_account_state_pcnrass.json")
        LauncherConfig.SESSION_STATE_FILE = os.path.join(td, "artifacts", "css_session_state_pcnrass.json")
        LauncherConfig.CLOSED_TRADE_LEDGER_PATH = os.path.join(td, "audit_logs", "closed_trades.jsonl")
        
        yield td
        
        # Restore config
        LauncherConfig.RUNTIME_DIR = orig_runtime
        LauncherConfig.SUPERVISOR_STATE_FILE = orig_state
        LauncherConfig.ALERTS_DIR = orig_alerts
        LauncherConfig.ARTIFACTS_DIR = orig_artifacts
        LauncherConfig.ACCOUNT_STATE_FILE = orig_account
        LauncherConfig.SESSION_STATE_FILE = orig_session
        LauncherConfig.CLOSED_TRADE_LEDGER_PATH = orig_ledger

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

def test_malformed_state_handled_safely(launcher_temp_dir):
    os.makedirs(os.path.dirname(LauncherConfig.SUPERVISOR_STATE_FILE), exist_ok=True)
    with open(LauncherConfig.SUPERVISOR_STATE_FILE, "w") as f:
        f.write("{ INVALID JSON ]")
    
    summary = get_supervisor_summary()
    assert summary["status"] == "ERROR"
    assert "Expecting property name" in summary["message"] or "decode" in summary["message"].lower()

from fastapi.testclient import TestClient
from launcher.css_mobile_launcher import app

client = TestClient(app)

def test_launcher_routes_load(launcher_temp_dir):
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert LauncherConfig.TITLE in response.text
    
    response = client.get("/mobile-launcher")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    
    response = client.get("/launcher/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert LauncherConfig.TITLE in response.text
    
    response = client.get("/mobile-dashboard")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "CSS Mobile Dashboard" in response.text
    
    response = client.get("/mobile")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "CSS Mobile Dashboard" in response.text

def test_mobile_dashboard_helpers_missing_files_handled_safely(launcher_temp_dir):
    from launcher.css_mobile_launcher import (
        get_runtime_summary, get_account_summary, 
        get_trade_summary, get_engine_summary, build_mobile_dashboard_context
    )
    # Ensure missing files don't crash
    runtime = get_runtime_summary()
    assert runtime["runtime_mode"] == "UNKNOWN"
    
    account = get_account_summary()
    assert account["cash"] == 0.0
    
    trade = get_trade_summary()
    assert trade["open_trades_count"] == 0
    
    engine = get_engine_summary()
    assert engine["engine_mode"] == "UNKNOWN"
    
    context = build_mobile_dashboard_context()
    assert "runtime" in context
    assert "account" in context

def test_mobile_dashboard_helpers_malformed_json_handled_safely(launcher_temp_dir):
    from launcher.css_mobile_launcher import build_mobile_dashboard_context
    os.makedirs(LauncherConfig.ARTIFACTS_DIR, exist_ok=True)
    with open(LauncherConfig.SESSION_STATE_FILE, "w") as f:
        f.write("{ invalid }")
    with open(LauncherConfig.ACCOUNT_STATE_FILE, "w") as f:
        f.write("{ invalid }")
    
    context = build_mobile_dashboard_context()
    assert context["runtime"]["runtime_mode"] == "UNKNOWN"
    assert context["account"]["cash"] == 0.0

def test_launcher_manifest_and_icon_routes():
    response = client.get("/manifest.json")
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "CSS Mobile Launcher"
    assert data["start_url"] == "/mobile-launcher"
    assert data["scope"] == "/"
    
    response = client.get("/static/css_launcher_icon.svg")
    assert response.status_code == 200
    assert "image/svg+xml" in response.headers["content-type"]

    response = client.get("/favicon.ico")
    assert response.status_code == 200
    assert "image/svg+xml" in response.headers["content-type"]

def test_launcher_health_and_status_routes(launcher_temp_dir):
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["service"] == "css_mobile_launcher"
    
    response = client.get("/status")
    assert response.status_code == 200
    data = response.json()
    assert "backend_available" in data
    assert "supervisor_status" in data
    assert "alert_summary" in data
    assert "dashboard_url" in data
