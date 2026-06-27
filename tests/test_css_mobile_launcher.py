import os
import json
import tempfile
import pytest

from launcher.css_launcher_config import LauncherConfig
from launcher.css_mobile_launcher import (
    get_supervisor_summary,
    get_alert_summary,
    get_mobile_launcher_status,
    build_launcher_context,
    get_pause_state,
    write_pause_state,
    write_mobile_paper_trade_request,
    _wants_json,
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
    assert "portfolio_summary" in context

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


# ────────────────────────────────────────────────────────────────
# PAUSE / RESUME TESTS
# ────────────────────────────────────────────────────────────────

def test_get_pause_state_defaults_to_not_paused_when_file_absent(launcher_temp_dir):
    """get_pause_state() must return trading_paused=False when the file does not exist."""
    # Redirect MOBILE_CONTROLS_FILE to the temp artifacts dir
    import launcher.css_mobile_launcher as mod
    orig = mod.MOBILE_CONTROLS_FILE
    mod.MOBILE_CONTROLS_FILE = os.path.join(LauncherConfig.ARTIFACTS_DIR, "css_mobile_controls.json")
    try:
        state = get_pause_state()
        assert state["trading_paused"] is False
        assert state["source"] == "default"
    finally:
        mod.MOBILE_CONTROLS_FILE = orig


def test_write_pause_state_round_trip(launcher_temp_dir):
    """write_pause_state writes the correct JSON; get_pause_state reads it back."""
    import launcher.css_mobile_launcher as mod
    orig = mod.MOBILE_CONTROLS_FILE
    controls_path = os.path.join(LauncherConfig.ARTIFACTS_DIR, "css_mobile_controls.json")
    mod.MOBILE_CONTROLS_FILE = controls_path
    try:
        os.makedirs(LauncherConfig.ARTIFACTS_DIR, exist_ok=True)

        # Pause
        written = write_pause_state(paused=True, reason="mobile_user_pause")
        assert written["trading_paused"] is True
        assert written["source"] == "mobile_launcher"
        assert written["reason"] == "mobile_user_pause"
        assert written["timestamp"].endswith("Z")

        read_back = get_pause_state()
        assert read_back["trading_paused"] is True
        assert read_back["source"] == "mobile_launcher"

        # Resume
        write_pause_state(paused=False, reason="mobile_user_resume")
        read_back2 = get_pause_state()
        assert read_back2["trading_paused"] is False
        assert read_back2["reason"] == "mobile_user_resume"

        # Confirm the file is valid JSON with all required keys
        with open(controls_path) as fh:
            on_disk = json.load(fh)
        assert "trading_paused" in on_disk
        assert "source" in on_disk
        assert "timestamp" in on_disk
        assert "reason" in on_disk
    finally:
        mod.MOBILE_CONTROLS_FILE = orig


def test_write_pause_state_preserves_existing_keys(launcher_temp_dir):
    """write_pause_state must not destroy keys written by mobile_app.py."""
    import launcher.css_mobile_launcher as mod
    orig = mod.MOBILE_CONTROLS_FILE
    controls_path = os.path.join(LauncherConfig.ARTIFACTS_DIR, "css_mobile_controls.json")
    mod.MOBILE_CONTROLS_FILE = controls_path
    try:
        os.makedirs(LauncherConfig.ARTIFACTS_DIR, exist_ok=True)
        # Simulate a file previously written by mobile_app.py
        pre_existing = {
            "mobile_trading_mode": "MOBILE_PAPER_TRADING",
            "engine_mode": "SAFE",
            "live_order_kill_switch": False,
        }
        with open(controls_path, "w") as fh:
            json.dump(pre_existing, fh)

        write_pause_state(paused=True, reason="mobile_user_pause")

        with open(controls_path) as fh:
            result = json.load(fh)

        # Launcher keys present
        assert result["trading_paused"] is True
        # Pre-existing keys preserved
        assert result["mobile_trading_mode"] == "MOBILE_PAPER_TRADING"
        assert result["engine_mode"] == "SAFE"
        assert result["live_order_kill_switch"] is False
    finally:
        mod.MOBILE_CONTROLS_FILE = orig


def test_pause_route_writes_paused_true_json(launcher_temp_dir):
    """POST /mobile/control/pause with Accept: application/json returns JSON and writes artifact."""
    import launcher.css_mobile_launcher as mod
    orig = mod.MOBILE_CONTROLS_FILE
    controls_path = os.path.join(LauncherConfig.ARTIFACTS_DIR, "css_mobile_controls.json")
    mod.MOBILE_CONTROLS_FILE = controls_path
    try:
        os.makedirs(LauncherConfig.ARTIFACTS_DIR, exist_ok=True)
        response = client.post(
            "/mobile/control/pause",
            headers={"Accept": "application/json"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["ok"] is True
        assert data["trading_paused"] is True
        assert "timestamp" in data

        # Artifact must exist and show paused=true
        with open(controls_path) as fh:
            on_disk = json.load(fh)
        assert on_disk["trading_paused"] is True
        assert on_disk["source"] == "mobile_launcher"
        assert on_disk["reason"] == "mobile_user_pause"
    finally:
        mod.MOBILE_CONTROLS_FILE = orig


def test_resume_route_writes_paused_false_json(launcher_temp_dir):
    """POST /mobile/control/resume with Accept: application/json returns JSON and writes artifact."""
    import launcher.css_mobile_launcher as mod
    orig = mod.MOBILE_CONTROLS_FILE
    controls_path = os.path.join(LauncherConfig.ARTIFACTS_DIR, "css_mobile_controls.json")
    mod.MOBILE_CONTROLS_FILE = controls_path
    try:
        os.makedirs(LauncherConfig.ARTIFACTS_DIR, exist_ok=True)
        # First pause so we have a meaningful state to resume from
        client.post("/mobile/control/pause", headers={"Accept": "application/json"})

        response = client.post(
            "/mobile/control/resume",
            headers={"Accept": "application/json"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["ok"] is True
        assert data["trading_paused"] is False

        with open(controls_path) as fh:
            on_disk = json.load(fh)
        assert on_disk["trading_paused"] is False
        assert on_disk["reason"] == "mobile_user_resume"
    finally:
        mod.MOBILE_CONTROLS_FILE = orig


def test_mobile_dashboard_exposes_pause_state(launcher_temp_dir):
    """GET /mobile must include Trading PAUSED/ACTIVE pill in the rendered HTML."""
    response = client.get("/mobile")
    assert response.status_code == 200
    # Either state is valid; what matters is the pill is rendered
    assert "Trading" in response.text
    assert ("PAUSED" in response.text or "ACTIVE" in response.text)


def test_pause_route_browser_redirects_to_risk(launcher_temp_dir):
    """Browser POST (no Accept header) must 303-redirect to /mobile#risk and write artifact."""
    import launcher.css_mobile_launcher as mod
    orig = mod.MOBILE_CONTROLS_FILE
    controls_path = os.path.join(LauncherConfig.ARTIFACTS_DIR, "css_mobile_controls.json")
    mod.MOBILE_CONTROLS_FILE = controls_path
    try:
        os.makedirs(LauncherConfig.ARTIFACTS_DIR, exist_ok=True)
        # follow_redirects=False so we see the raw 303, not the eventual HTML
        response = client.post("/mobile/control/pause", follow_redirects=False)
        assert response.status_code == 303
        assert response.headers["location"] == "/mobile#risk"

        # Artifact must still have been written before the redirect
        with open(controls_path) as fh:
            on_disk = json.load(fh)
        assert on_disk["trading_paused"] is True
        assert on_disk["source"] == "mobile_launcher"
    finally:
        mod.MOBILE_CONTROLS_FILE = orig


def test_resume_route_browser_redirects_to_risk(launcher_temp_dir):
    """Browser POST (no Accept header) must 303-redirect to /mobile#risk and write artifact."""
    import launcher.css_mobile_launcher as mod
    orig = mod.MOBILE_CONTROLS_FILE
    controls_path = os.path.join(LauncherConfig.ARTIFACTS_DIR, "css_mobile_controls.json")
    mod.MOBILE_CONTROLS_FILE = controls_path
    try:
        os.makedirs(LauncherConfig.ARTIFACTS_DIR, exist_ok=True)
        response = client.post("/mobile/control/resume", follow_redirects=False)
        assert response.status_code == 303
        assert response.headers["location"] == "/mobile#risk"

        with open(controls_path) as fh:
            on_disk = json.load(fh)
        assert on_disk["trading_paused"] is False
        assert on_disk["source"] == "mobile_launcher"
    finally:
        mod.MOBILE_CONTROLS_FILE = orig


def test_xhr_header_returns_json_not_redirect(launcher_temp_dir):
    """X-Requested-With: XMLHttpRequest must also trigger the JSON path."""
    import launcher.css_mobile_launcher as mod
    orig = mod.MOBILE_CONTROLS_FILE
    controls_path = os.path.join(LauncherConfig.ARTIFACTS_DIR, "css_mobile_controls.json")
    mod.MOBILE_CONTROLS_FILE = controls_path
    try:
        os.makedirs(LauncherConfig.ARTIFACTS_DIR, exist_ok=True)
        response = client.post(
            "/mobile/control/pause",
            headers={"X-Requested-With": "XMLHttpRequest"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["ok"] is True
        assert data["trading_paused"] is True
    finally:
        mod.MOBILE_CONTROLS_FILE = orig

# ────────────────────────────────────────────────────────────────
# MOBILE PAPER TRADE REQUEST TESTS
# ────────────────────────────────────────────────────────────────

def _set_mobile_trade_requests_file(tmp_path):
    import launcher.css_mobile_launcher as mod
    orig = mod.MOBILE_TRADE_REQUESTS_FILE
    path = os.path.join(tmp_path, "artifacts", "css_mobile_trade_requests.jsonl")
    mod.MOBILE_TRADE_REQUESTS_FILE = path
    return mod, orig, path


def test_mobile_paper_trade_request_success_writes_artifact(launcher_temp_dir):
    mod, orig, trade_path = _set_mobile_trade_requests_file(launcher_temp_dir)
    try:
        response = client.post(
            "/mobile/trade/paper",
            headers={"Accept": "application/json"},
            data={
                "symbol": "btc-usd",
                "asset_class": "crypto",
                "side": "buy",
                "quantity": "1",
                "paper_only": "true",
                "broker_mode": "paper",
                "broker_execution_allowed": "false",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["ok"] is True
        request_record = data["trade_request"]
        assert request_record["source"] == "mobile_dashboard"
        assert request_record["paper_only"] is True
        assert request_record["symbol"] == "BTC-USD"
        assert request_record["asset_class"] == "CRYPTO"
        assert request_record["side"] == "BUY"
        assert request_record["quantity"] == 1.0
        assert request_record["status"] == "REQUESTED"
        assert os.path.exists(trade_path)

        with open(trade_path) as fh:
            rows = [json.loads(line) for line in fh if line.strip()]
        assert len(rows) == 1
        assert rows[0]["symbol"] == "BTC-USD"
    finally:
        mod.MOBILE_TRADE_REQUESTS_FILE = orig


def test_mobile_paper_trade_rejects_invalid_side(launcher_temp_dir):
    mod, orig, trade_path = _set_mobile_trade_requests_file(launcher_temp_dir)
    try:
        response = client.post(
            "/mobile/trade/paper",
            headers={"Accept": "application/json"},
            data={"symbol": "BTC-USD", "asset_class": "CRYPTO", "side": "HOLD", "quantity": "1"},
        )
        assert response.status_code == 400
        assert response.json()["ok"] is False
        assert not os.path.exists(trade_path)
    finally:
        mod.MOBILE_TRADE_REQUESTS_FILE = orig


def test_mobile_paper_trade_rejects_blank_symbol(launcher_temp_dir):
    mod, orig, trade_path = _set_mobile_trade_requests_file(launcher_temp_dir)
    try:
        response = client.post(
            "/mobile/trade/paper",
            headers={"Accept": "application/json"},
            data={"symbol": "   ", "asset_class": "CRYPTO", "side": "BUY", "quantity": "1"},
        )
        assert response.status_code == 400
        assert response.json()["ok"] is False
        assert not os.path.exists(trade_path)
    finally:
        mod.MOBILE_TRADE_REQUESTS_FILE = orig


def test_mobile_paper_trade_rejects_quantity_lte_zero(launcher_temp_dir):
    mod, orig, trade_path = _set_mobile_trade_requests_file(launcher_temp_dir)
    try:
        response = client.post(
            "/mobile/trade/paper",
            headers={"Accept": "application/json"},
            data={"symbol": "BTC-USD", "asset_class": "CRYPTO", "side": "BUY", "quantity": "0"},
        )
        assert response.status_code == 400
        assert response.json()["ok"] is False
        assert not os.path.exists(trade_path)
    finally:
        mod.MOBILE_TRADE_REQUESTS_FILE = orig


def test_mobile_paper_trade_rejects_missing_asset_class(launcher_temp_dir):
    mod, orig, trade_path = _set_mobile_trade_requests_file(launcher_temp_dir)
    try:
        response = client.post(
            "/mobile/trade/paper",
            headers={"Accept": "application/json"},
            data={"symbol": "BTC-USD", "asset_class": "", "side": "BUY", "quantity": "1"},
        )
        assert response.status_code == 400
        assert response.json()["ok"] is False
        assert not os.path.exists(trade_path)
    finally:
        mod.MOBILE_TRADE_REQUESTS_FILE = orig


def test_mobile_paper_trade_rejects_live_or_broker_execution_request(launcher_temp_dir):
    mod, orig, trade_path = _set_mobile_trade_requests_file(launcher_temp_dir)
    try:
        live_response = client.post(
            "/mobile/trade/paper",
            headers={"Accept": "application/json"},
            data={
                "symbol": "BTC-USD",
                "asset_class": "CRYPTO",
                "side": "BUY",
                "quantity": "1",
                "broker_mode": "live",
            },
        )
        assert live_response.status_code == 400

        broker_response = client.post(
            "/mobile/trade/paper",
            headers={"Accept": "application/json"},
            data={
                "symbol": "BTC-USD",
                "asset_class": "CRYPTO",
                "side": "BUY",
                "quantity": "1",
                "broker_execution_allowed": "true",
            },
        )
        assert broker_response.status_code == 400
        assert not os.path.exists(trade_path)
    finally:
        mod.MOBILE_TRADE_REQUESTS_FILE = orig


def test_mobile_paper_trade_artifact_append_behavior(launcher_temp_dir):
    mod, orig, trade_path = _set_mobile_trade_requests_file(launcher_temp_dir)
    try:
        for symbol in ("BTC-USD", "ETH-USD"):
            response = client.post(
                "/mobile/trade/paper",
                headers={"Accept": "application/json"},
                data={
                    "symbol": symbol,
                    "asset_class": "CRYPTO",
                    "side": "BUY",
                    "quantity": "1",
                    "paper_only": "true",
                    "broker_mode": "paper",
                    "broker_execution_allowed": "false",
                },
            )
            assert response.status_code == 200

        with open(trade_path) as fh:
            rows = [json.loads(line) for line in fh if line.strip()]

        assert len(rows) == 2
        assert [row["symbol"] for row in rows] == ["BTC-USD", "ETH-USD"]
        assert all(row["status"] == "REQUESTED" for row in rows)
    finally:
        mod.MOBILE_TRADE_REQUESTS_FILE = orig


def test_mobile_dashboard_exposes_paper_trade_ticket(launcher_temp_dir):
    response = client.get("/mobile")
    assert response.status_code == 200
    assert "Mobile Trade Ticket" in response.text
    assert "PAPER TRADING ONLY" in response.text
    assert "/mobile/trade/paper" in response.text

def test_mobile_dashboard_exposes_trade_tab_navigation(launcher_temp_dir):
    response = client.get("/mobile")
    assert response.status_code == 200
    assert 'id="nav-trade"' in response.text
    assert 'data-screen="trade"' in response.text
    assert 'id="screen-trade"' in response.text
    assert "CSS Decision Console" in response.text
    assert "Canonical Trading Universe" in response.text
    assert "TOP OPPORTUNITIES" in response.text
    assert "PAPER TRADING ONLY" in response.text
    assert "/mobile/trade/paper" in response.text


def test_trade_tab_ticket_layout_and_mode_visibility(launcher_temp_dir):
    response = client.get("/mobile")
    assert response.status_code == 200
    html = response.text

    assert 'id="trade-asset-class"' in html
    assert 'id="trade-symbol"' in html
    assert 'id="trade-side"' in html
    assert 'id="trade-tenor"' in html
    assert 'id="trade-price"' in html
    assert 'id="trade-quantity"' in html
    assert "PAPER MODE" in html or "LIVE MODE" in html


def test_trade_tab_wired_to_trade_ticket_data_feed(launcher_temp_dir):
    response = client.get("/mobile")
    assert response.status_code == 200
    html = response.text

    assert 'id="trade-ticket-data-card"' in html
    assert "/mobile/trade-ticket-data" in html
    assert 'id="tt-account-cash"' in html
    assert 'id="tt-account-buying-power"' in html
    assert 'id="tt-account-equity"' in html
    assert 'id="tt-broker-selected"' in html
    assert 'id="tt-paper-live-mode"' in html
    assert 'id="tt-engine-mode"' in html
    assert 'id="tt-min-order-size"' in html
    assert 'id="tt-max-order-size"' in html
    assert 'id="tt-tick-size"' in html
    assert 'id="tt-degraded-warning"' in html
    assert 'id="tt-network-warning"' in html


def test_trade_tab_render_does_not_execute_trade_request(launcher_temp_dir):
    import launcher.css_mobile_launcher as mod

    mod_ref, orig, trade_path = _set_mobile_trade_requests_file(launcher_temp_dir)
    try:
        response = client.get("/mobile")
        assert response.status_code == 200
        assert not os.path.exists(trade_path)
    finally:
        mod_ref.MOBILE_TRADE_REQUESTS_FILE = orig


def test_mobile_opportunity_routes_return_json(launcher_temp_dir):
    response = client.get("/mobile/opportunities")
    assert response.status_code == 200
    body = response.json()
    assert "all_opportunities" in body
    assert "top_opportunities" in body

    response_top = client.get("/mobile/opportunities/top")
    assert response_top.status_code == 200
    assert "top_opportunities" in response_top.json()

    response_asset = client.get("/mobile/opportunities/asset-class/FX")
    assert response_asset.status_code == 200
    assert response_asset.json()["asset_class"] == "FX"


def test_mobile_trading_universe_routes_return_json(launcher_temp_dir):
    response = client.get("/mobile/trading-universe")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "OK"
    assert "instruments" in payload

    grouped = client.get("/mobile/trading-universe/grouped")
    assert grouped.status_code == 200
    grouped_payload = grouped.json()
    assert grouped_payload["status"] == "OK"
    assert "groups" in grouped_payload


def test_mobile_top_opportunities_route_returns_json(launcher_temp_dir):
    response = client.get("/mobile/top-opportunities")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "OK"
    assert "top_opportunities" in payload


def test_mobile_opportunity_summary_route_returns_decision_panel(launcher_temp_dir):
    response = client.get("/mobile/opportunity-summary/BTC-USD")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] in {"OK", "ERROR"}
    if payload["status"] == "OK":
        assert "decision_panel" in payload
        assert "engine_outputs" in payload


def test_mobile_opportunity_summary_exposes_explicit_options_metadata(launcher_temp_dir):
    response = client.get("/mobile/opportunity-summary/SPY?asset_class=OPTIONS")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "OK"

    panel = payload["decision_panel"]
    assert panel["tenor_options"] == ["2026-07-17", "2026-08-21", "2026-09-18"]
    assert panel["default_tenor"] == "2026-07-17"
    assert panel["suggested_tenor"] == "2026-07-17"
    assert panel["expiry_source"] == "canonical_options_chain_metadata"
    assert panel["option_types"] == ["CALL", "PUT"]
    assert panel["strike_policy"] == "ATM_LADDER"
    assert panel["contract_metadata_status"] == "EXPLICIT"


def test_mobile_opportunity_summary_exposes_explicit_futures_metadata(launcher_temp_dir):
    response = client.get("/mobile/opportunity-summary/ES?asset_class=FUTURES")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "OK"

    panel = payload["decision_panel"]
    assert panel["tenor_options"] == ["2026H", "2026M", "2026U", "2026Z"]
    assert panel["default_tenor"] == "2026H"
    assert panel["suggested_tenor"] == "2026H"
    assert panel["expiry_source"] == "canonical_futures_contract_metadata"
    assert panel["contract_months"] == ["2026H", "2026M", "2026U", "2026Z"]
    assert panel["contract_metadata_status"] == "EXPLICIT"


def test_mobile_portfolio_summary_route_returns_recommendation(launcher_temp_dir):
    response = client.get("/mobile/portfolio-summary")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] in {"OK", "ERROR"}
    if payload["status"] == "OK":
        assert "summary" in payload
        assert "recommendation" in payload
        assert "strategy_evolution" in payload


def test_mobile_strategy_evolution_route_returns_recommendation(launcher_temp_dir):
    response = client.get("/mobile/strategy-evolution")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] in {"OK", "INSUFFICIENT_DATA", "ERROR"}
    assert "recommended_strategy_weights" in payload


def test_mobile_trade_tab_renders_portfolio_summary_panel(launcher_temp_dir):
    response = client.get("/mobile")
    assert response.status_code == 200
    html = response.text
    assert "Portfolio Summary" in html
    assert 'id="portfolio-summary-card"' in html
    assert "Strategy Evolution" in html
    assert 'id="strategy-evolution-card"' in html


def test_mobile_tradeable_symbols_route_shape_and_filters(launcher_temp_dir, monkeypatch):
    import launcher.css_mobile_launcher as mod
    from types import SimpleNamespace

    class _StubUniverse:
        def tradeable_symbols(self, mode="paper", asset_class=None, broker=None):
            rows = [
                SimpleNamespace(
                    symbol="EUR_USD",
                    display_name="Euro / US Dollar",
                    asset_class="FX",
                    broker="oanda",
                    paper_supported=True,
                    live_supported=True,
                    status="ACTIVE",
                ),
                SimpleNamespace(
                    symbol="BTC-USD",
                    display_name="Bitcoin / US Dollar",
                    asset_class="CRYPTO",
                    broker="coinbase",
                    paper_supported=True,
                    live_supported=True,
                    status="ACTIVE",
                ),
            ]
            if asset_class:
                rows = [row for row in rows if row.asset_class == asset_class]
            if broker:
                rows = [row for row in rows if row.broker == broker]
            return rows

    monkeypatch.setattr(mod, "InstrumentUniverse", _StubUniverse)

    response = client.get("/mobile/tradeable-symbols?mode=paper&asset_class=FX&broker=oanda")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "OK"
    assert payload["mode"] == "paper"
    assert payload["count"] == 1
    assert payload["symbols"][0]["symbol"] == "EUR_USD"


def test_opportunity_alert_generated_when_no_opportunities(launcher_temp_dir, monkeypatch):
    import launcher.css_mobile_launcher as mod

    class _EmptyEngine:
        def rank_all(self, include_blocked=True):
            return []

        def top_opportunities(self, limit=10):
            return []

        def paper_opportunities(self, limit=10):
            return []

    monkeypatch.setattr(mod, "OpportunityRankingEngine", _EmptyEngine)

    feed = mod.get_opportunity_feed()
    assert feed["all_opportunities"] == []

    alerts = mod.get_alert_summary()
    assert any("No tradable opportunities available" in str(item.get("message", "")) for item in alerts)


def test_mobile_trade_ticket_data_happy_path_uses_provider_timestamp(launcher_temp_dir, monkeypatch):
    import launcher.css_mobile_launcher as mod

    provider_timestamp = "2026-06-26T10:11:12Z"

    monkeypatch.setattr(
        mod,
        "get_tradeable_symbols_feed",
        lambda: {
            "status": "OK",
            "timestamp": provider_timestamp,
            "symbols": [
                {
                    "symbol": "EUR_USD",
                    "display_name": "Euro / US Dollar",
                    "asset_class": "FX",
                    "broker": "oanda",
                    "paper_supported": True,
                    "live_supported": True,
                    "status": "ACTIVE",
                    "min_order_size": 1.0,
                    "max_order_size": 100000.0,
                    "tick_size": 0.0001,
                }
            ],
        },
    )
    monkeypatch.setattr(
        mod,
        "get_grouped_trading_universe_feed",
        lambda: {"status": "OK", "groups": []},
    )
    monkeypatch.setattr(
        mod,
        "get_account_summary",
        lambda: {"cash": 1000.0, "buying_power": 2000.0, "equity": 1500.0},
    )
    monkeypatch.setattr(
        mod,
        "get_runtime_summary",
        lambda: {"runtime_mode": "PAPER", "status": "ONLINE", "updated_at": "2026-06-26T09:00:00Z"},
    )
    monkeypatch.setattr(
        mod,
        "get_engine_summary",
        lambda: {"trade_gate_status": "OPEN", "engine_mode": "PAPER"},
    )
    monkeypatch.setattr(
        mod,
        "get_pause_state",
        lambda: {"trading_paused": False, "timestamp": "2026-06-26T09:05:00Z"},
    )

    response = client.get("/mobile/trade-ticket-data")
    assert response.status_code == 200
    payload = response.json()

    for key in (
        "status",
        "timestamp",
        "symbols",
        "available_symbols",
        "account",
        "runtime",
        "broker",
        "permissions",
        "limits",
        "errors",
    ):
        assert key in payload

    assert payload["status"] == "OK"
    assert payload["timestamp"] == provider_timestamp
    assert payload["account"]["cash"] == 1000.0
    assert payload["account"]["buying_power"] == 2000.0
    assert payload["account"]["equity"] == 1500.0
    assert payload["broker"]["selected"] == "oanda"
    assert "execution_capabilities" in payload["broker"]
    assert payload["permissions"]["read_only"] is True
    assert payload["permissions"]["mobile_order_submission_enabled"] is False
    assert payload["permissions"]["endpoint_authorizes_execution"] is False


def test_mobile_trade_ticket_data_provider_failure_returns_degraded(launcher_temp_dir, monkeypatch):
    import launcher.css_mobile_launcher as mod

    def _raise_provider_unavailable(*args, **kwargs):
        raise RuntimeError("provider unavailable")

    monkeypatch.setattr(mod, "get_tradeable_symbols_feed", _raise_provider_unavailable)
    monkeypatch.setattr(mod, "get_grouped_trading_universe_feed", _raise_provider_unavailable)
    monkeypatch.setattr(mod, "get_account_summary", _raise_provider_unavailable)
    monkeypatch.setattr(mod, "get_runtime_summary", _raise_provider_unavailable)
    monkeypatch.setattr(mod, "get_engine_summary", _raise_provider_unavailable)
    monkeypatch.setattr(mod, "get_pause_state", _raise_provider_unavailable)

    response = client.get("/mobile/trade-ticket-data")
    assert response.status_code == 200
    payload = response.json()

    assert payload["status"] == "DEGRADED"
    assert payload["symbols"] == []
    assert payload["runtime"]["runtime_mode"] == "UNKNOWN"
    assert payload["account"]["cash"] == 0.0
    assert payload["account"]["buying_power"] == 0.0
    assert payload["account"]["equity"] == 0.0
    assert isinstance(payload["errors"], list)
    assert len(payload["errors"]) >= 1
    first_error = payload["errors"][0]
    assert "provider" in first_error
    assert first_error["error_type"] == "RuntimeError"
    assert first_error["message"] == "provider unavailable"


def test_mobile_trade_ticket_data_timestamp_skips_none_literal(launcher_temp_dir, monkeypatch):
    import launcher.css_mobile_launcher as mod

    grouped_ts = "2026-06-26T14:22:00Z"

    monkeypatch.setattr(
        mod,
        "get_tradeable_symbols_feed",
        lambda: {"status": "OK", "mode": "paper", "timestamp": "None", "symbols": []},
    )
    monkeypatch.setattr(
        mod,
        "get_grouped_trading_universe_feed",
        lambda: {"status": "OK", "mode": "paper", "updated_at": grouped_ts, "groups": []},
    )
    monkeypatch.setattr(mod, "get_account_summary", lambda: {"cash": 0.0, "buying_power": 0.0, "equity": 0.0})
    monkeypatch.setattr(mod, "get_runtime_summary", lambda: {"runtime_mode": "UNKNOWN", "status": "ONLINE"})
    monkeypatch.setattr(mod, "get_engine_summary", lambda: {"engine_mode": "UNKNOWN", "trade_gate_status": "SIMULATED"})
    monkeypatch.setattr(mod, "get_pause_state", lambda: {"trading_paused": False, "timestamp": ""})

    response = client.get("/mobile/trade-ticket-data")
    assert response.status_code == 200
    payload = response.json()
    assert payload["timestamp"] == grouped_ts


def test_mobile_trade_ticket_data_resolves_paper_live_and_engine_mode(launcher_temp_dir, monkeypatch):
    import launcher.css_mobile_launcher as mod

    monkeypatch.setattr(
        mod,
        "get_tradeable_symbols_feed",
        lambda: {
            "status": "OK",
            "mode": "paper",
            "symbols": [
                {
                    "symbol": "EUR_USD",
                    "asset_class": "FX",
                    "broker": "oanda",
                    "status": "ACTIVE",
                    "min_order_size": 1.0,
                    "max_order_size": 100000.0,
                    "tick_size": 0.0001,
                }
            ],
        },
    )
    monkeypatch.setattr(mod, "get_grouped_trading_universe_feed", lambda: {"status": "OK", "mode": "paper", "groups": []})
    monkeypatch.setattr(mod, "get_account_summary", lambda: {"cash": 100.0, "buying_power": 200.0, "equity": 150.0})
    monkeypatch.setattr(mod, "get_runtime_summary", lambda: {"runtime_mode": "BALANCED", "status": "ONLINE"})
    monkeypatch.setattr(mod, "get_engine_summary", lambda: {"engine_mode": "UNKNOWN", "trade_gate_status": "SIMULATED"})
    monkeypatch.setattr(mod, "get_pause_state", lambda: {"trading_paused": False})

    response = client.get("/mobile/trade-ticket-data")
    assert response.status_code == 200
    payload = response.json()

    assert payload["mode"]["paper_live"] == "paper"
    assert payload["mode"]["engine"] == "BALANCED"
    assert payload["engine"]["engine_mode"] == "BALANCED"


def test_trade_tab_has_collapsible_advanced_diagnostics_section(launcher_temp_dir):
    response = client.get("/mobile")
    assert response.status_code == 200
    html = response.text
    assert 'id="trade-diagnostics-advanced"' in html
    assert "Advanced Diagnostics JSON" in html

