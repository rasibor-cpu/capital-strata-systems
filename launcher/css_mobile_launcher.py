import os
import json
from typing import Dict, Any, List
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from launcher.css_launcher_config import LauncherConfig

launcher_router = APIRouter()
templates = Jinja2Templates(directory=os.path.join(os.path.dirname(__file__), "templates"))

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

def build_launcher_context() -> Dict[str, Any]:
    status = get_mobile_launcher_status()
    supervisor = get_supervisor_summary()
    alerts = get_alert_summary()
    
    return {
        "title": LauncherConfig.TITLE,
        "version": LauncherConfig.VERSION,
        "status": status,
        "supervisor": supervisor,
        "recent_alerts": alerts
    }

@launcher_router.get("/", response_class=HTMLResponse)
async def launcher_home(request: Request):
    context = build_launcher_context()
    context["request"] = request
    return templates.TemplateResponse("mobile_launcher.html", context)
