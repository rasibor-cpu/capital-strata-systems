import os

class LauncherConfig:
    # Default Paths
    RUNTIME_DIR = os.path.join(os.getcwd(), "runtime")
    SUPERVISOR_STATE_FILE = os.path.join(RUNTIME_DIR, "supervisor", "css_runtime_supervisor_state.json")
    ALERTS_DIR = os.path.join(RUNTIME_DIR, "alerts")
    
    # Launcher metadata
    TITLE = "CSS Mobile Launcher"
    VERSION = "1.0.0"
