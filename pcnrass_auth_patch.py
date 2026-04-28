from __future__ import annotations

"""
PCNRASS-SAFE CSS AUTH PATCH

Purpose:
- Patch ONLY the CSS login/authentication block in scripts/css_live_dashboard.py
- Preserve the current working dashboard, PnL, broker, session, risk, and execution logic
- Restore:
    * CSS LOGIN prompt
    * Super user ID 00000
    * Initial password 123456
    * Forced password change on first login
    * Forced password change every 30 calendar days
    * Login session persistence marker

Run from project root:
    python pcnrass_auth_patch.py
"""

import hashlib
import json
import shutil
from datetime import datetime
from pathlib import Path


PROJECT_ROOT = Path.cwd()
DASHBOARD = PROJECT_ROOT / "scripts" / "css_live_dashboard.py"
USERS_FILE = PROJECT_ROOT / "data" / "users.json"


AUTH_BLOCK = """
# === PCNRASS RESTORED CSS AUTHENTICATION ===
# Scope: authentication only. Do not touch PnL, broker, execution, dashboard, or risk logic.
# Policy:
# - Initial super user: 00000
# - Initial password: 123456
# - Force password change on first login
# - Force password change every 30 calendar days
# - Persist latest successful login under artifacts/css_auth_session.json
USERS_FILE = PROJECT_ROOT / "data" / "users.json"
SESSION_AUTH_FILE = ARTIFACTS_DIR / "css_auth_session.json"
PASSWORD_MAX_AGE_DAYS = 30


def _css_hash_password(password: str) -> str:
    import hashlib
    return hashlib.sha256(str(password).encode("utf-8")).hexdigest()


def _css_load_users() -> dict[str, Any]:
    USERS_FILE.parent.mkdir(parents=True, exist_ok=True)

    if not USERS_FILE.exists():
        USERS_FILE.write_text(json.dumps({
            "00000": {
                "user_id": "00000",
                "display_name": "CSS Administrator",
                "role": "SUPER_USER",
                "unit_code": "CORE",
                "home_branch": "HQ",
                "password_hash": _css_hash_password("123456"),
                "must_change_password": True,
                "last_password_change": None
            }
        }, indent=2), encoding="utf-8")

    with open(USERS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def _css_save_users(users: dict[str, Any]) -> None:
    USERS_FILE.parent.mkdir(parents=True, exist_ok=True)
    USERS_FILE.write_text(json.dumps(users, indent=2), encoding="utf-8")


def _css_password_expired(user_record: dict[str, Any]) -> bool:
    if bool(user_record.get("must_change_password", False)):
        return True

    last_change = user_record.get("last_password_change")
    if not last_change:
        return True

    try:
        last_dt = datetime.fromisoformat(str(last_change))
    except Exception:
        return True

    return datetime.now() - last_dt >= timedelta(days=PASSWORD_MAX_AGE_DAYS)


def _css_force_password_change(users: dict[str, Any], user_key: str) -> None:
    print("[PASSWORD CHANGE REQUIRED] Initial/expired password must be changed now.")

    while True:
        new_password = getpass.getpass("Enter new password: ").strip()
        confirm_password = getpass.getpass("Confirm new password: ").strip()

        if not new_password:
            print("[PASSWORD ERROR] Password cannot be blank.")
            continue

        if len(new_password) < 6:
            print("[PASSWORD ERROR] Password must be at least 6 characters.")
            continue

        if new_password == "123456":
            print("[PASSWORD ERROR] New password cannot remain the initial default password.")
            continue

        if new_password != confirm_password:
            print("[PASSWORD ERROR] Passwords do not match.")
            continue

        users[user_key]["password_hash"] = _css_hash_password(new_password)
        users[user_key]["must_change_password"] = False
        users[user_key]["last_password_change"] = datetime.now().isoformat(timespec="seconds")
        _css_save_users(users)
        print("[PASSWORD UPDATED] Password changed successfully.")
        return


def _css_persist_login_session(user_ctx: dict[str, Any]) -> None:
    SESSION_AUTH_FILE.parent.mkdir(parents=True, exist_ok=True)
    SESSION_AUTH_FILE.write_text(json.dumps({
        "user_id": user_ctx.get("user_id"),
        "display_name": user_ctx.get("display_name"),
        "role": user_ctx.get("role"),
        "unit_code": user_ctx.get("unit_code"),
        "home_branch": user_ctx.get("home_branch"),
        "last_login": datetime.now().isoformat(timespec="seconds"),
        "login_persistence": True
    }, indent=2), encoding="utf-8")


def await_login_ready_state():
    users = _css_load_users()

    while True:
        user_id = input("CSS LOGIN | user_id (numeric): ").strip().zfill(5)

        user_record = users.get(user_id)
        if not user_record:
            print("[AUTH FAILED] INVALID_USER_ID")
            continue

        password = getpass.getpass("CSS LOGIN | password: ")
        expected_hash = str(user_record.get("password_hash", "")).strip()
        supplied_hash = _css_hash_password(password)

        if supplied_hash != expected_hash:
            print("[AUTH FAILED] AUTH_FAILED")
            continue

        if _css_password_expired(user_record):
            _css_force_password_change(users, user_id)
            user_record = users[user_id]

        ctx = {
            "user_id": str(user_record.get("user_id", user_id)).zfill(5),
            "display_name": user_record.get("display_name", "CSS User"),
            "role": user_record.get("role", "VIEWER"),
            "unit_code": user_record.get("unit_code", "CORE"),
            "home_branch": user_record.get("home_branch", "HQ"),
        }

        _css_persist_login_session(ctx)
        print(f"[AUTH SUCCESS] {ctx['display_name']} | role={ctx['role']}")
        return ctx
"""


def sha256(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def ensure_dashboard_imports(text: str) -> str:
    if "import hashlib" not in text:
        text = text.replace("import contextlib\n", "import contextlib\nimport hashlib\n", 1)

    if "import getpass" not in text:
        if "import hashlib\n" in text:
            text = text.replace("import hashlib\n", "import hashlib\nimport getpass\n", 1)
        else:
            text = text.replace("import contextlib\n", "import contextlib\nimport getpass\n", 1)

    if "from datetime import datetime, timedelta" not in text:
        text = text.replace("from datetime import datetime\n", "from datetime import datetime, timedelta\n", 1)

    return text


def patch_auth_block(text: str) -> str:
    marker = "SESSION_USER_CTX = authenticate_startup_user()"
    if marker not in text:
        raise RuntimeError("Could not find SESSION_USER_CTX marker in dashboard.")

    insert_at = text.find(marker)

    start_markers = [
        "# === PCNRASS RESTORED CSS AUTHENTICATION ===",
        "# === PCNRASS AUTH RESTORE — MUST APPEAR BEFORE SESSION_USER_CTX ===",
        "# === PCNRASS AUTH OVERRIDE (CLEAN) ===",
        "# === PCNRASS AUTH HOTFIX (RESTORE SUPERUSER 00000) ===",
    ]

    best_start = -1
    for sm in start_markers:
        idx = text.rfind(sm, 0, insert_at)
        if idx > best_start:
            best_start = idx

    if best_start != -1:
        text = text[:best_start].rstrip() + "\n\n" + AUTH_BLOCK.strip() + "\n\n" + text[insert_at:]
    else:
        text = text[:insert_at].rstrip() + "\n\n" + AUTH_BLOCK.strip() + "\n\n" + text[insert_at:]

    text = text.replace("REA LOGIN | user_id (numeric):", "CSS LOGIN | user_id (numeric):")
    return text


def normalize_users_file() -> None:
    USERS_FILE.parent.mkdir(parents=True, exist_ok=True)

    if USERS_FILE.exists():
        try:
            users = json.loads(USERS_FILE.read_text(encoding="utf-8"))
        except Exception:
            users = {}
    else:
        users = {}

    users["00000"] = {
        "user_id": "00000",
        "display_name": "CSS Administrator",
        "role": "SUPER_USER",
        "unit_code": "CORE",
        "home_branch": "HQ",
        "password_hash": sha256("123456"),
        "must_change_password": True,
        "last_password_change": None,
    }

    # Preserve test users if present, but normalize IDs to strings.
    for key in list(users.keys()):
        if isinstance(users.get(key), dict):
            users[key]["user_id"] = str(users[key].get("user_id", key)).zfill(5)

    USERS_FILE.write_text(json.dumps(users, indent=2), encoding="utf-8")


def main() -> None:
    if not DASHBOARD.exists():
        raise SystemExit(f"Dashboard not found: {DASHBOARD}")

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = DASHBOARD.with_name(f"css_live_dashboard_BACKUP_BEFORE_AUTH_PATCH_{ts}.py")
    shutil.copy2(DASHBOARD, backup)

    text = DASHBOARD.read_text(encoding="utf-8", errors="replace")
    text = ensure_dashboard_imports(text)
    text = patch_auth_block(text)
    DASHBOARD.write_text(text, encoding="utf-8")

    normalize_users_file()

    print("[PCNRASS AUTH PATCH COMPLETE]")
    print(f"Backup created: {backup}")
    print("Patched: scripts/css_live_dashboard.py")
    print("Updated: data/users.json")
    print("Login policy:")
    print("  user_id: 00000")
    print("  initial password: 123456")
    print("  must change on first login: YES")
    print("  password expiry: 30 calendar days")


if __name__ == "__main__":
    main()
