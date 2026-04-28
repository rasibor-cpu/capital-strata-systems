from __future__ import annotations

"""
PCNRASS FINAL FIX v2
- Adds cross-platform masked password visual aid.
- Adds final account settlement on normal operator stop and keyboard interrupt.
- Surgical patch only; creates backup first.

Run from CSS project root:
    python pcnrass_final_fix_v2.py
"""

import re
import shutil
from datetime import datetime
from pathlib import Path


ROOT = Path.cwd()
DASH = ROOT / "scripts" / "css_live_dashboard.py"


MASKED_INPUT_BLOCK = """
# ===== PCNRASS MASKED PASSWORD INPUT =====
def masked_password_input(prompt: str = "CSS LOGIN | password: ") -> str:
    try:
        import msvcrt

        print(prompt, end="", flush=True)
        password_chars = []

        while True:
            ch = msvcrt.getwch()

            if ch in ("\\r", "\\n"):
                print()
                break

            if ch in ("\\b", "\\x7f"):
                if password_chars:
                    password_chars.pop()
                    print("\\b \\b", end="", flush=True)
                continue

            if ch in ("\\x00", "\\xe0"):
                try:
                    msvcrt.getwch()
                except Exception:
                    pass
                continue

            password_chars.append(ch)
            print("*", end="", flush=True)

        return "".join(password_chars)

    except Exception:
        return getpass.getpass(prompt)
"""


SETTLEMENT_BLOCK = """
# ===== PCNRASS FINAL ACCOUNT SETTLEMENT =====
def finalize_account_session() -> None:
    try:
        if "pcnrass_session_state" not in globals() or "pcnrass_account_state" not in globals():
            return

        new_balance = float(pcnrass_session_state.get("session_equity", 0.0))
        if new_balance <= 0:
            return

        pcnrass_account_state["account_balance"] = round(new_balance, 4)
        pcnrass_account_state["last_session_close"] = datetime.now().isoformat(timespec="seconds")

        if "ACCOUNT_STATE_FILE" in globals():
            Path(ACCOUNT_STATE_FILE).parent.mkdir(parents=True, exist_ok=True)
            Path(ACCOUNT_STATE_FILE).write_text(
                json.dumps(pcnrass_account_state, indent=2, default=str),
                encoding="utf-8",
            )

        print(f"[ACCOUNT UPDATED] new balance: {new_balance:.2f}")

    except Exception as e:
        print(f"[ACCOUNT SETTLEMENT ERROR] {e}")
"""


def ensure_imports(text: str) -> str:
    if "import getpass" not in text:
        if "import hashlib" in text:
            text = text.replace("import hashlib\\n", "import hashlib\\nimport getpass\\n", 1)
        elif "import json" in text:
            text = text.replace("import json\\n", "import json\\nimport getpass\\n", 1)
        else:
            text = "import getpass\\n" + text
    return text


def insert_helpers(text: str) -> str:
    if "def masked_password_input(" not in text:
        marker = "def _css_hash_password"
        if marker in text:
            text = text.replace(marker, MASKED_INPUT_BLOCK + "\\n\\n" + marker, 1)
        else:
            text = MASKED_INPUT_BLOCK + "\\n\\n" + text

    if "def finalize_account_session(" not in text:
        marker = "try:\\n    while True:"
        if marker in text:
            text = text.replace(marker, SETTLEMENT_BLOCK + "\\n\\n" + marker, 1)
        else:
            text = text + "\\n\\n" + SETTLEMENT_BLOCK

    return text


def patch_password_prompt(text: str) -> str:
    text = text.replace(
        'getpass.getpass("CSS LOGIN | password: ")',
        'masked_password_input("CSS LOGIN | password: ")',
    )
    text = text.replace(
        "getpass.getpass('CSS LOGIN | password: ')",
        'masked_password_input("CSS LOGIN | password: ")',
    )
    text = text.replace(
        'getpass.getpass("Password: ")',
        'masked_password_input("CSS LOGIN | password: ")',
    )
    return text


def patch_operator_stop_settlement(text: str) -> str:
    if "finalize_account_session()\\n            close_active_session(" in text:
        return text

    old = """            close_active_session(
                "operator_requested_stop",
                extra={
"""
    new = """            try:
                finalize_account_session()
            except Exception as e:
                print(f"[SESSION SETTLEMENT WARN] {e}")

            close_active_session(
                "operator_requested_stop",
                extra={
"""
    if old in text:
        text = text.replace(old, new, 1)

    return text


def patch_keyboard_interrupt_settlement(text: str) -> str:
    pattern = r'except KeyboardInterrupt:\\s*\\n\\s*print\\("\\[SESSION STOPPED\\] Keyboard interrupt received\\."\\)'
    replacement = """except KeyboardInterrupt:
    try:
        finalize_account_session()
    except Exception as e:
        print(f"[SESSION SETTLEMENT WARN] {e}")
    print("[SESSION STOPPED] Keyboard interrupt received.")"""
    text = re.sub(pattern, replacement, text, count=1)
    return text


def main() -> None:
    if not DASH.exists():
        raise SystemExit(f"Dashboard not found: {DASH}")

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = DASH.with_name(f"css_live_dashboard_BACKUP_BEFORE_FINAL_FIX_V2_{ts}.py")
    shutil.copy2(DASH, backup)

    text = DASH.read_text(encoding="utf-8", errors="replace")
    text = ensure_imports(text)
    text = insert_helpers(text)
    text = patch_password_prompt(text)
    text = patch_operator_stop_settlement(text)
    text = patch_keyboard_interrupt_settlement(text)

    DASH.write_text(text, encoding="utf-8")

    print("[PCNRASS FINAL FIX v2 COMPLETE]")
    print(f"Backup created: {backup}")
    print("Patched: scripts/css_live_dashboard.py")
    print("Added: masked password visual aid")
    print("Added: final account settlement on session stop")


if __name__ == "__main__":
    main()
