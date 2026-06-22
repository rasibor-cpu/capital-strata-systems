import os
import json
import datetime
from typing import Dict, Any, List
from fastapi import APIRouter, Request, FastAPI
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from launcher.css_launcher_config import LauncherConfig
import uvicorn

app = FastAPI(title=LauncherConfig.TITLE, version=LauncherConfig.VERSION)
launcher_router = APIRouter()
templates = Jinja2Templates(directory=os.path.join(os.path.dirname(__file__), "templates"))

app.mount("/static", StaticFiles(directory=os.path.join(os.path.dirname(__file__), "static")), name="static")


def _safe_load_artifact(filename: str) -> Dict[str, Any]:
    path = os.path.join(LauncherConfig.ARTIFACTS_DIR, filename)
    if os.path.exists(path):
        try:
            with open(path, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


# ── PAUSE / RESUME CONTROL ARTIFACT ─────────────────────────────────────────

MOBILE_CONTROLS_FILE = os.path.join(LauncherConfig.ARTIFACTS_DIR, "css_mobile_controls.json")


def get_pause_state() -> Dict[str, Any]:
    """Read current trading_paused flag from the controls artifact.

    Returns a dict with at minimum:
        trading_paused (bool)
        source (str)
        timestamp (str)
    Defaults to not-paused when the file is absent or unreadable.
    """
    try:
        if os.path.exists(MOBILE_CONTROLS_FILE):
            with open(MOBILE_CONTROLS_FILE, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            if isinstance(data, dict):
                return {
                    "trading_paused": bool(data.get("trading_paused", False)),
                    "source": str(data.get("source", "unknown")),
                    "timestamp": str(data.get("timestamp", "")),
                    "reason": str(data.get("reason", "")),
                }
    except Exception:
        pass
    return {
        "trading_paused": False,
        "source": "default",
        "timestamp": "",
        "reason": "",
    }


def write_pause_state(paused: bool, reason: str) -> Dict[str, Any]:
    """Merge trading_paused into the controls artifact and return the new state.

    Only writes the four launcher-controlled keys; all other existing keys in
    the file are preserved so the full mobile_app.py controls stack is not
    disturbed.
    """
    # Read existing controls to preserve any keys written by mobile_app.py
    existing: Dict[str, Any] = {}
    try:
        if os.path.exists(MOBILE_CONTROLS_FILE):
            with open(MOBILE_CONTROLS_FILE, "r", encoding="utf-8") as fh:
                existing = json.load(fh)
            if not isinstance(existing, dict):
                existing = {}
    except Exception:
        existing = {}

    now = datetime.datetime.utcnow().isoformat() + "Z"
    existing.update(
        {
            "trading_paused": paused,
            "source": "mobile_launcher",
            "timestamp": now,
            "reason": reason,
        }
    )

    os.makedirs(os.path.dirname(MOBILE_CONTROLS_FILE), exist_ok=True)
    with open(MOBILE_CONTROLS_FILE, "w", encoding="utf-8") as fh:
        json.dump(existing, fh, indent=2)

    return {
        "trading_paused": paused,
        "source": "mobile_launcher",
        "timestamp": now,
        "reason": reason,
    }

def get_supervisor_summary() -> Dict[str, Any]:
    state_file = LauncherConfig.SUPERVISOR_STATE_FILE
    if not os.path.exists(state_file):
        return {"status": "UNKNOWN", "last_heartbeat": "None", "message": "Supervisor state missing"}
    
    try:
        with open(state_file, "r") as f:
            state = json.load(f)
            
        return {
            "status": state.get("status", "UNKNOWN"),
            "last_heartbeat": state.get("last_heartbeat", "None"),
            "failure_count": state.get("failure_count", 0),
            "restart_count": state.get("restart_count", 0)
        }
    except Exception as e:
        return {"status": "ERROR", "last_heartbeat": "None", "message": str(e)}

def get_alert_summary() -> List[Dict[str, Any]]:
    alerts_dir = LauncherConfig.ALERTS_DIR
    if not os.path.exists(alerts_dir):
        return []
        
    try:
        files = [f for f in os.listdir(alerts_dir) if f.endswith(".json")]
        # Sort by filename descending to get most recent (assuming format starts with timestamp)
        files.sort(reverse=True)
        recent_files = files[:5]
        
        alerts = []
        for file in recent_files:
            try:
                with open(os.path.join(alerts_dir, file), "r") as f:
                    alerts.append(json.load(f))
            except Exception:
                pass
        return alerts
    except Exception:
        return []

def get_mobile_launcher_status() -> str:
    summary = get_supervisor_summary()
    if summary.get("status") in ("RUNNING", "DEGRADED"):
        return "ONLINE"
    return "OFFLINE"

def get_runtime_summary() -> Dict[str, Any]:
    session = _safe_load_artifact("css_session_state_pcnrass.json").get("session", {}) or _safe_load_artifact("css_session_recovery.json").get("session", {})
    summary = {
        "runtime_mode": session.get("engine_mode", "UNKNOWN"),
        "current_cycle": session.get("cycle_number", 0),
        "last_update": session.get("start_time", "None")
    }
    
    supervisor = get_supervisor_summary()
    summary["supervisor_status"] = supervisor.get("status", "UNKNOWN")
    summary["last_heartbeat"] = supervisor.get("last_heartbeat", "None")
    summary["restart_count"] = supervisor.get("restart_count", 0)
    summary["failure_count"] = supervisor.get("failure_count", 0)
    summary["status"] = get_mobile_launcher_status()
    
    return summary

def get_account_summary() -> Dict[str, Any]:
    state = _safe_load_artifact("css_account_state_pcnrass.json") or _safe_load_artifact("css_account_state_pcnrass_BACKUP.json")
    summary = {
        "cash": state.get("account_balance", 0.0),
        "equity": state.get("total_equity", state.get("account_balance", 0.0)),
        "buying_power": state.get("buying_power", state.get("account_balance", 0.0)),
        "open_pnl": state.get("unrealized_pnl", 0.0),
        "realized_pnl": state.get("lifetime_realized_pnl", 0.0),
        "total_pnl": state.get("lifetime_realized_pnl", 0.0) + state.get("unrealized_pnl", 0.0)
    }
    return summary

def get_trade_summary() -> Dict[str, Any]:
    summary = {
        "open_trades_count": 0,
        "closed_trades_count": 0,
        "pending_orders_count": 0,
        "recent_activity": []
    }
    
    session_state = _safe_load_artifact("css_session_state_pcnrass.json") or _safe_load_artifact("css_session_recovery.json")
    account_state = _safe_load_artifact("css_account_state_pcnrass.json") or _safe_load_artifact("css_account_state_pcnrass_BACKUP.json")
    positions = account_state.get("positions", [])
    if not positions and "open_trades" in session_state:
        positions = session_state["open_trades"]
    summary["open_trades_count"] = len(positions)
        
    try:
        if os.path.exists(LauncherConfig.CLOSED_TRADE_LEDGER_PATH):
            with open(LauncherConfig.CLOSED_TRADE_LEDGER_PATH, "r") as f:
                lines = f.readlines()
                summary["closed_trades_count"] = len(lines)
                
                recent = []
                for line in reversed(lines[-5:]):
                    try:
                        recent.append(json.loads(line))
                    except Exception:
                        pass
                summary["recent_activity"] = recent
    except Exception:
        pass
        
    return summary

def get_engine_summary() -> Dict[str, Any]:
    state = _safe_load_artifact("css_session_state_pcnrass.json") or _safe_load_artifact("css_session_recovery.json")
    session = state.get("session", {})
    
    summary = {
        "engine_mode": session.get("engine_mode", "UNKNOWN"),
        "current_strategy": session.get("strategy", "DEFAULT"),
        "trade_gate_status": "OPEN" if session.get("engine_mode") == "LIVE" else "SIMULATED",
        "runtime_readiness": "ONLINE" if session else "OFFLINE"
    }
    return summary

def build_mobile_dashboard_context() -> Dict[str, Any]:
    # Calculate heartbeat / staleness
    artifacts = [
        "css_session_state_pcnrass.json",
        "css_account_state_pcnrass.json",
        "css_session_recovery.json",
        "css_account_state_pcnrass_BACKUP.json"
    ]
    latest_mtime = 0
    for file in artifacts:
        p = os.path.join(LauncherConfig.ARTIFACTS_DIR, file)
        if os.path.exists(p):
            latest_mtime = max(latest_mtime, os.path.getmtime(p))
    
    if latest_mtime > 0:
        age = datetime.datetime.now().timestamp() - latest_mtime
        staleness = "ACTIVE" if age < 60 else "STALE"
    else:
        staleness = "OFFLINE"
        
    # Get chart data
    session_state = _safe_load_artifact("css_session_state_pcnrass.json") or _safe_load_artifact("css_session_recovery.json")
    account_state = _safe_load_artifact("css_account_state_pcnrass.json") or _safe_load_artifact("css_account_state_pcnrass_BACKUP.json")
    
    positions = account_state.get("positions", [])
    if not positions and "open_trades" in session_state:
        positions = session_state["open_trades"]
    if not isinstance(positions, list):
        positions = []
        
    assets_parsed = {}
    for pos in positions:
        try:
            val = abs(float(pos.get("market_value", pos.get("notional_value", pos.get("current_value", pos.get("entry_price", 0))))))
            qty = abs(float(pos.get("quantity", pos.get("size", 1))))
            if "market_value" not in pos and "notional_value" not in pos:
                val = val * qty
            if val > 0:
                sym = pos.get("symbol", pos.get("asset", "UNKNOWN"))
                assets_parsed[sym] = assets_parsed.get(sym, 0) + val
        except Exception:
            pass
            
    total_equity = account_state.get("total_equity", account_state.get("account_balance", 0.0))
    cash = account_state.get("account_balance", 0.0)

    # Simplified charts for launcher
    chart_data = {
        "has_data": bool(positions) or bool(account_state),
        "equity": total_equity,
        "cash": cash,
        "assets": assets_parsed
    }

    return {
        "title": "CSS Mobile Dashboard",
        "version": LauncherConfig.VERSION,
        "runtime": get_runtime_summary(),
        "account": get_account_summary(),
        "trade": get_trade_summary(),
        "alerts": get_alert_summary(),
        "engine": get_engine_summary(),
        "staleness": staleness,
        "chart_data": chart_data,
        "pause_state": get_pause_state(),
        "health": {
            "backend_available": get_mobile_launcher_status() == "ONLINE",
            "supervisor_status": get_supervisor_summary().get("status", "UNKNOWN"),
            "dashboard_status": "ONLINE"
        }
    }

def build_launcher_context() -> Dict[str, Any]:
    status = get_mobile_launcher_status()
    supervisor = get_supervisor_summary()
    alerts = get_alert_summary()
    
    return {
        "title": LauncherConfig.TITLE,
        "version": LauncherConfig.VERSION,
        "status": status,
        "supervisor": supervisor,
        "recent_alerts": alerts,
        "dashboard_url": LauncherConfig.DASHBOARD_URL
    }

@launcher_router.get("/", response_class=HTMLResponse)
async def launcher_home(request: Request):
    context = build_launcher_context()
    return templates.TemplateResponse(request, "mobile_launcher.html", context)

@launcher_router.get("/mobile-launcher", response_class=HTMLResponse)
@launcher_router.get("/launcher/", response_class=HTMLResponse)
async def launcher_home_alias(request: Request):
    context = build_launcher_context()
    return templates.TemplateResponse(request, "mobile_launcher.html", context)

@launcher_router.get("/mobile-dashboard", response_class=HTMLResponse)
@launcher_router.get("/mobile", response_class=HTMLResponse)
async def mobile_dashboard(request: Request):
    context = build_mobile_dashboard_context()
    return templates.TemplateResponse(request, "mobile_dashboard.html", context)

@launcher_router.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "service": "css_mobile_launcher",
        "timestamp": datetime.datetime.utcnow().isoformat() + "Z"
    }

@launcher_router.get("/status")
async def status_check():
    status = get_mobile_launcher_status()
    supervisor = get_supervisor_summary()
    alerts = get_alert_summary()
    return {
        "backend_available": status == "ONLINE",
        "supervisor_status": supervisor.get("status"),
        "alert_summary": alerts,
        "dashboard_url": LauncherConfig.DASHBOARD_URL,
        "readiness": status
    }

@launcher_router.get("/manifest.json")
async def get_manifest():
    return FileResponse(os.path.join(os.path.dirname(__file__), "static", "css_launcher_manifest.json"))

@launcher_router.get("/favicon.ico")
async def get_favicon():
    return FileResponse(os.path.join(os.path.dirname(__file__), "static", "css_launcher_icon.svg"), media_type="image/svg+xml")


# ── PAUSE / RESUME ROUTES ────────────────────────────────────────────────────

_BROWSER_REDIRECT_TARGET = "/mobile#risk"


def _wants_json(request: Request) -> bool:
    """Return True when the client explicitly requests JSON (API / XHR call).

    Browser form submissions send no Accept header or a wildcard; they expect
    a redirect, not a JSON body.  Only return True when the caller signals JSON
    intent via a recognised header.
    """
    accept = request.headers.get("accept", "")
    xhr    = request.headers.get("x-requested-with", "")
    return "application/json" in accept or xhr.lower() == "xmlhttprequest"


@launcher_router.post("/mobile/control/pause")
async def mobile_control_pause(request: Request):
    """Write trading_paused=true to the controls artifact.

    - Browser form POST  → 303 redirect to /mobile#risk (Risk tab auto-opens)
    - API / XHR caller   → JSON {ok, trading_paused, timestamp}
    Safe: only mutates the pause flag. No broker calls. No secrets.
    """
    state = write_pause_state(paused=True, reason="mobile_user_pause")
    if _wants_json(request):
        return JSONResponse(
            {"ok": True, "trading_paused": state["trading_paused"], "timestamp": state["timestamp"]}
        )
    return RedirectResponse(_BROWSER_REDIRECT_TARGET, status_code=303)


@launcher_router.post("/mobile/control/resume")
async def mobile_control_resume(request: Request):
    """Write trading_paused=false to the controls artifact.

    - Browser form POST  → 303 redirect to /mobile#risk (Risk tab auto-opens)
    - API / XHR caller   → JSON {ok, trading_paused, timestamp}
    Safe: only mutates the pause flag. No broker calls. No secrets.
    """
    state = write_pause_state(paused=False, reason="mobile_user_resume")
    if _wants_json(request):
        return JSONResponse(
            {"ok": True, "trading_paused": state["trading_paused"], "timestamp": state["timestamp"]}
        )
    return RedirectResponse(_BROWSER_REDIRECT_TARGET, status_code=303)

app.include_router(launcher_router)

if __name__ == "__main__":
    uvicorn.run(app, host=LauncherConfig.HOST, port=LauncherConfig.PORT)
