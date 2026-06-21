import os
import json
import datetime
from typing import Dict, Any, List
from fastapi import APIRouter, Request, FastAPI
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from launcher.css_launcher_config import LauncherConfig
import uvicorn

app = FastAPI(title=LauncherConfig.TITLE, version=LauncherConfig.VERSION)
launcher_router = APIRouter()
templates = Jinja2Templates(directory=os.path.join(os.path.dirname(__file__), "templates"))

app.mount("/static", StaticFiles(directory=os.path.join(os.path.dirname(__file__), "static")), name="static")

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
    state_file = LauncherConfig.SESSION_STATE_FILE
    summary = {
        "runtime_mode": "UNKNOWN",
        "current_cycle": 0,
        "last_update": "None"
    }
    try:
        if os.path.exists(state_file):
            with open(state_file, "r") as f:
                state = json.load(f)
                session = state.get("session", {})
                summary["runtime_mode"] = session.get("engine_mode", "UNKNOWN")
                summary["current_cycle"] = session.get("cycle_number", 0)
                summary["last_update"] = state.get("last_updated", session.get("start_time", "None"))
    except Exception:
        pass
    
    supervisor = get_supervisor_summary()
    summary["supervisor_status"] = supervisor.get("status", "UNKNOWN")
    summary["last_heartbeat"] = supervisor.get("last_heartbeat", "None")
    summary["restart_count"] = supervisor.get("restart_count", 0)
    summary["failure_count"] = supervisor.get("failure_count", 0)
    summary["status"] = get_mobile_launcher_status()
    
    return summary

def get_account_summary() -> Dict[str, Any]:
    state_file = LauncherConfig.ACCOUNT_STATE_FILE
    summary = {
        "cash": 0.0,
        "equity": 0.0,
        "buying_power": 0.0,
        "open_pnl": 0.0,
        "realized_pnl": 0.0,
        "total_pnl": 0.0
    }
    try:
        if os.path.exists(state_file):
            with open(state_file, "r") as f:
                state = json.load(f)
                summary["cash"] = state.get("account_balance", 0.0)
                summary["equity"] = state.get("total_equity", state.get("account_balance", 0.0))
                summary["buying_power"] = state.get("buying_power", summary["cash"])
                summary["realized_pnl"] = state.get("lifetime_realized_pnl", 0.0)
                # In absence of full PnL snapshot, we estimate or use available data
                summary["open_pnl"] = state.get("unrealized_pnl", 0.0)
                summary["total_pnl"] = summary["realized_pnl"] + summary["open_pnl"]
    except Exception:
        pass
    return summary

def get_trade_summary() -> Dict[str, Any]:
    summary = {
        "open_trades_count": 0,
        "closed_trades_count": 0,
        "pending_orders_count": 0,
        "recent_activity": []
    }
    
    try:
        if os.path.exists(LauncherConfig.SESSION_STATE_FILE):
            with open(LauncherConfig.SESSION_STATE_FILE, "r") as f:
                state = json.load(f)
                assets = state.get("assets", {})
                # Count assets with non-zero balance as open trades
                open_trades = [k for k, v in assets.items() if isinstance(v, (int, float)) and v > 0]
                summary["open_trades_count"] = len(open_trades)
    except Exception:
        pass
        
    try:
        if os.path.exists(LauncherConfig.CLOSED_TRADE_LEDGER_PATH):
            with open(LauncherConfig.CLOSED_TRADE_LEDGER_PATH, "r") as f:
                lines = f.readlines()
                summary["closed_trades_count"] = len(lines)
                
                # Get last 5 trades
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
    state_file = LauncherConfig.SESSION_STATE_FILE
    summary = {
        "engine_mode": "UNKNOWN",
        "current_strategy": "NONE",
        "trade_gate_status": "UNKNOWN",
        "runtime_readiness": "OFFLINE"
    }
    try:
        if os.path.exists(state_file):
            with open(state_file, "r") as f:
                state = json.load(f)
                session = state.get("session", {})
                summary["engine_mode"] = session.get("engine_mode", "UNKNOWN")
                summary["current_strategy"] = session.get("strategy", "DEFAULT")
                summary["trade_gate_status"] = "OPEN" if session.get("engine_mode") == "LIVE" else "SIMULATED"
                summary["runtime_readiness"] = "ONLINE"
    except Exception:
        pass
    return summary

def build_mobile_dashboard_context() -> Dict[str, Any]:
    return {
        "title": "CSS Mobile Dashboard",
        "version": LauncherConfig.VERSION,
        "runtime": get_runtime_summary(),
        "account": get_account_summary(),
        "trade": get_trade_summary(),
        "alerts": get_alert_summary(),
        "engine": get_engine_summary(),
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
    context["request"] = request
    return templates.TemplateResponse("mobile_launcher.html", context)

@launcher_router.get("/mobile-launcher", response_class=HTMLResponse)
@launcher_router.get("/launcher/", response_class=HTMLResponse)
async def launcher_home_alias(request: Request):
    context = build_launcher_context()
    context["request"] = request
    return templates.TemplateResponse("mobile_launcher.html", context)

@launcher_router.get("/mobile-dashboard", response_class=HTMLResponse)
@launcher_router.get("/mobile", response_class=HTMLResponse)
async def mobile_dashboard(request: Request):
    context = build_mobile_dashboard_context()
    context["request"] = request
    return templates.TemplateResponse("mobile_dashboard.html", context)

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

app.include_router(launcher_router)

if __name__ == "__main__":
    uvicorn.run(app, host=LauncherConfig.HOST, port=LauncherConfig.PORT)
