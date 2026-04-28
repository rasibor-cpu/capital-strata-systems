from __future__ import annotations

"""
PCNRASS SYNTAX REPAIR AFTER FINAL FIX v2

Fixes accidental literal "\\n" sequences inserted into scripts/css_live_dashboard.py.
Scope: syntax repair only.
Run from project root:
    python pcnrass_repair_literal_newlines.py
"""

import shutil
from datetime import datetime
from pathlib import Path

ROOT = Path.cwd()
DASH = ROOT / "scripts" / "css_live_dashboard.py"

def main() -> None:
    if not DASH.exists():
        raise SystemExit(f"Dashboard not found: {DASH}")

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = DASH.with_name(f"css_live_dashboard_BACKUP_BEFORE_LITERAL_N_REPAIR_{ts}.py")
    shutil.copy2(DASH, backup)

    text = DASH.read_text(encoding="utf-8", errors="replace")

    # Repair only literal backslash-n sequences that were injected into code.
    # This converts text like: \n\ndef _css_hash_password
    # into actual blank lines before the function definition.
    text = text.replace("\\n\\ndef _css_hash_password", "\n\ndef _css_hash_password")
    text = text.replace("\\ndef _css_hash_password", "\ndef _css_hash_password")
    text = text.replace("\\n\\n# ===== PCNRASS", "\n\n# ===== PCNRASS")
    text = text.replace("\\n# ===== PCNRASS", "\n# ===== PCNRASS")

    # Broader cleanup for any remaining literal newlines before top-level defs/classes/comments
    for token in ["def ", "class ", "# =====", "# ==="]:
        text = text.replace("\\n" + token, "\n" + token)

    DASH.write_text(text, encoding="utf-8")

    print("[PCNRASS LITERAL NEWLINE REPAIR COMPLETE]")
    print(f"Backup created: {backup}")
    print("Patched: scripts/css_live_dashboard.py")
    print("Now run: python -m py_compile scripts\\css_live_dashboard.py")

if __name__ == "__main__":
    main()
