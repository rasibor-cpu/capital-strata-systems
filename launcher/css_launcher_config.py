import os

class LauncherConfig:
    # Default Paths
    RUNTIME_DIR = os.path.join(os.getcwd(), "runtime")
    SUPERVISOR_STATE_FILE = os.path.join(RUNTIME_DIR, "supervisor", "css_runtime_supervisor_state.json")
    ALERTS_DIR = os.path.join(RUNTIME_DIR, "alerts")
    
    ARTIFACTS_DIR = os.path.join(os.getcwd(), "artifacts")
    ACCOUNT_STATE_FILE = os.path.join(ARTIFACTS_DIR, "css_account_state_pcnrass.json")
    SESSION_STATE_FILE = os.path.join(ARTIFACTS_DIR, "css_session_state_pcnrass.json")
    CLOSED_TRADE_LEDGER_PATH = os.path.join(os.getcwd(), "audit_logs", "closed_trades.jsonl")
    
    # Launcher metadata
    TITLE = "CSS Mobile Launcher"
    VERSION = "1.0.0"
    
    # Server settings
    HOST = os.environ.get("CSS_LAUNCHER_HOST", "0.0.0.0")
    PORT = int(os.environ.get("CSS_LAUNCHER_PORT", "8765"))
    
    # Dashboard Link
    DASHBOARD_URL = os.environ.get("CSS_DASHBOARD_URL", "/mobile")
