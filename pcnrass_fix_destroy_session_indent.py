from __future__ import annotations

"""
PCNRASS SAFE REPAIR: fix broken destroy_session indentation only.

Run from CSS project root:
    python pcnrass_fix_destroy_session_indent.py

Scope:
- Creates a timestamped backup first.
- Repairs only the broken close_active_session destroy_session block.
- Does not alter auth, PnL, broker logic, session/account balances, asset balances,
  engine modes, or execution logic.
"""

import re
import shutil
from datetime import datetime
from pathlib import Path

ROOT = Path.cwd()
DASH = ROOT / "scripts" / "css_live_dashboard.py"

BROKEN_PATTERNS = [
    # Common bad insertion: try line followed by unindented destroy call
    (
        re.compile(
            r"try:\s*\n\s*session_manager\.destroy_session\(str\(session_id\), reason=reason\)\s*\n\s*except TypeError:\s*\n\s*try:\s*\n\s*session_manager\.destroy_session\(str\(session_id\)\)\s*\n\s*except TypeError:\s*\n\s*pass",
            re.MULTILINE,
        ),
        """try:
        session_manager.destroy_session(str(session_id), reason=reason)
    except TypeError:
        try:
            session_manager.destroy_session(str(session_id))
        except TypeError:
            pass""",
    ),
    # Original single-line call if still present
    (
        re.compile(r"session_manager\.destroy_session\(str\(session_id\), reason=reason\)"),
        """try:
        session_manager.destroy_session(str(session_id), reason=reason)
    except TypeError:
        try:
            session_manager.destroy_session(str(session_id))
        except TypeError:
            pass""",
    ),
]


def main() -> None:
    if not DASH.exists():
        raise SystemExit(f"Dashboard not found: {DASH}")

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = DASH.with_name(f"css_live_dashboard_BACKUP_BEFORE_DESTROY_SESSION_FIX_{ts}.py")
    shutil.copy2(DASH, backup)

    text = DASH.read_text(encoding="utf-8", errors="replace")

    changed = False
    for pattern, replacement in BROKEN_PATTERNS:
        new_text, count = pattern.subn(replacement, text, count=1)
        if count:
            text = new_text
            changed = True
            break

    if not changed:
        print("[NO CHANGE] Could not find expected destroy_session block.")
        print(f"Backup still created: {backup}")
        raise SystemExit(1)

    DASH.write_text(text, encoding="utf-8")

    print("[PCNRASS DESTROY_SESSION INDENT FIX COMPLETE]")
    print(f"Backup created: {backup}")
    print("Patched: scripts/css_live_dashboard.py")
    print("Scope: destroy_session compatibility block only")


if __name__ == "__main__":
    main()
