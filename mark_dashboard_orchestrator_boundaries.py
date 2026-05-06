from pathlib import Path
import shutil
from datetime import datetime

DASHBOARD = Path(r"scripts\css_live_dashboard.py")

START_MARKER = "# ===== ORCHESTRATOR REPLACEMENT START ====="
END_MARKER = "# ===== ORCHESTRATOR REPLACEMENT END ====="

def main():
    if not DASHBOARD.exists():
        raise FileNotFoundError(f"Dashboard file not found: {DASHBOARD}")

    text = DASHBOARD.read_text(encoding="utf-8")
    lines = text.splitlines()

    if START_MARKER in text or END_MARKER in text:
        print("[NO CHANGE] Markers already exist in dashboard.")
        return

    start_idx = None
    end_idx = None

    # Start safely at the RBAC/new-position block, based on current dashboard structure.
    for i, line in enumerate(lines):
        if "[RBAC] New position generation blocked for current role." in line:
            start_idx = i
            break

    # End safely at the hard open-position cap pause marker.
    for i, line in enumerate(lines):
        if "[SIGNAL GENERATION PAUSED] hard open-position cap reached" in line:
            end_idx = i
            break

    if start_idx is None:
        raise RuntimeError("Could not find start anchor: [RBAC] New position generation blocked for current role.")

    if end_idx is None:
        raise RuntimeError("Could not find end anchor: [SIGNAL GENERATION PAUSED] hard open-position cap reached")

    if start_idx >= end_idx:
        raise RuntimeError(f"Invalid marker order: start line {start_idx+1}, end line {end_idx+1}")

    backup = DASHBOARD.with_name(
        f"css_live_dashboard_before_orchestrator_markers_{datetime.now().strftime('%Y%m%d_%H%M%S')}.py"
    )
    shutil.copy2(DASHBOARD, backup)

    new_lines = []
    for i, line in enumerate(lines):
        if i == start_idx:
            new_lines.append(START_MARKER)
        new_lines.append(line)
        if i == end_idx:
            new_lines.append(END_MARKER)

    DASHBOARD.write_text("\n".join(new_lines) + "\n", encoding="utf-8")

    print("[SUCCESS] Orchestrator replacement markers inserted.")
    print(f"[BACKUP] {backup}")
    print(f"[START LINE APPROX] {start_idx + 1}")
    print(f"[END LINE APPROX] {end_idx + 1}")

if __name__ == "__main__":
    main()
