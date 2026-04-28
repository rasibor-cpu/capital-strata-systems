# PCNRASS FINAL ACCOUNT SETTLEMENT + PASSWORD MASK PATCH
# Run: python pcnrass_final_fix.py

import shutil
from datetime import datetime
from pathlib import Path

ROOT = Path.cwd()
DASH = ROOT / "scripts" / "css_live_dashboard.py"

def main():
    if not DASH.exists():
        raise SystemExit("Dashboard not found")

    backup = DASH.with_name(f"backup_final_{int(datetime.now().timestamp())}.py")
    shutil.copy2(DASH, backup)

    text = DASH.read_text(encoding="utf-8", errors="replace")

    # ===== PASSWORD MASK (visual aid with *) =====
    if "def masked_input" not in text:
        mask_block = 