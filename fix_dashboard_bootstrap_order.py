from pathlib import Path
import shutil
from datetime import datetime

DASHBOARD = Path(r"scripts\css_live_dashboard.py")

EARLY_BLOCK = """from __future__ import annotations
from backend.intelligence.dashboard_orchestrator_bridge import run_dashboard_orchestration
bridge_output = run_dashboard_orchestration(SYMBOLS)
"""

BAD_IMPORT_LINE = "from backend.intelligence.dashboard_orchestrator_bridge import run_dashboard_orchestration"

def main():
    if not DASHBOARD.exists():
        raise FileNotFoundError(f"Dashboard file not found: {DASHBOARD}")

    text = DASHBOARD.read_text(encoding="utf-8")

    backup = DASHBOARD.with_name(
        f"css_live_dashboard_before_bootstrap_fix2_{datetime.now().strftime('%Y%m%d_%H%M%S')}.py"
    )
    shutil.copy2(DASHBOARD, backup)

    changes = 0

    if EARLY_BLOCK in text:
        text = text.replace(EARLY_BLOCK, "from __future__ import annotations\n", 1)
        changes += 1

    import_count = text.count(BAD_IMPORT_LINE)
    if import_count:
        text = text.replace(BAD_IMPORT_LINE, "# PCNRASS: orchestrator bridge import deferred until after PROJECT_ROOT bootstrap")
        changes += import_count

    DASHBOARD.write_text(text, encoding="utf-8")

    print(f"[SUCCESS] Bootstrap/orchestrator unsafe imports neutralized. changes={changes}")
    print(f"[BACKUP] {backup}")

if __name__ == "__main__":
    main()