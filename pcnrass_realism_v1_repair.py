from __future__ import annotations

"""
PCNRASS REALISM v1 FUTURE-IMPORT REPAIR

Fixes:
- Moves the PCNRASS REALISM LAYER v1 block below `from __future__ import annotations`
- Preserves realism logic
- Does not alter trading/account/session/auth logic
"""

from pathlib import Path
import shutil
from datetime import datetime

DASH = Path("scripts/css_live_dashboard.py")

START = "# ===== PCNRASS REALISM LAYER v1 ====="
END_FUNC = "    return round(adjusted_pnl, 4)"


def main():
    if not DASH.exists():
        raise SystemExit(f"Dashboard not found: {DASH}")

    backup = DASH.with_name(
        f"css_live_dashboard_BACKUP_BEFORE_REALISM_REPAIR_{datetime.now().strftime('%Y%m%d_%H%M%S')}.py"
    )
    shutil.copy2(DASH, backup)

    text = DASH.read_text(encoding="utf-8", errors="replace")

    if START not in text:
        print("[NO CHANGE] Realism block not found.")
        print(f"Backup created: {backup}")
        return

    start_idx = text.find(START)
    end_idx = text.find(END_FUNC, start_idx)
    if end_idx == -1:
        raise SystemExit("Could not find end of realism block.")

    end_idx = end_idx + len(END_FUNC)
    while end_idx < len(text) and text[end_idx] in "\r\n":
        end_idx += 1

    realism_block = text[start_idx:end_idx].strip() + "\n\n"
    text_without = text[:start_idx] + text[end_idx:]

    future_line = "from __future__ import annotations"
    future_idx = text_without.find(future_line)
    if future_idx == -1:
        raise SystemExit("Future import not found; stop and inspect manually.")

    insert_pos = future_idx + len(future_line)
    while insert_pos < len(text_without) and text_without[insert_pos] in "\r\n":
        insert_pos += 1

    repaired = text_without[:insert_pos] + "\n\n" + realism_block + text_without[insert_pos:]
    DASH.write_text(repaired, encoding="utf-8")

    print("[PCNRASS REALISM REPAIR COMPLETE]")
    print(f"Backup created: {backup}")
    print("Run: python -m py_compile scripts\\css_live_dashboard.py")


if __name__ == "__main__":
    main()
