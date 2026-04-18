from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, Optional

PROJECT_ROOT = Path(__file__).resolve().parents[3]
USER_STORE = PROJECT_ROOT / "data" / "users.json"

INITIAL_PASSWORD = "123456"
DEFAULT_ADMIN_USER_ID = "00000"
DEFAULT_ADMIN_DISPLAY_NAME = "CSS Administrator"
DEFAULT_ADMIN_ROLE = "SUPER_USER"
DEFAULT_ADMIN_UNIT_CODE = "CORE"
DEFAULT_ADMIN_HOME_BRANCH = "HQ"


@dataclass
class UserRecord:
    user_id: int
    display_name: str
    role: str
    unit_code: str
    home_branch: str
    password_hash: str
    must_change_password: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _hash_password(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def _normalize_user_key(user_id: int | str) -> str:
    try:
        numeric = int(str(user_id).strip())
    except Exception as exc:
        raise RuntimeError("AUTH_FAIL: invalid_user_id") from exc

    if numeric < 0 or numeric > 99999:
        raise RuntimeError("AUTH_FAIL: invalid_user_id")

    return f"{numeric:05d}"


def _coerce_record(raw: dict) -> UserRecord:
    return UserRecord(
        user_id=int(raw["user_id"]),
        display_name=str(raw["display_name"]),
        role=str(raw["role"]),
        unit_code=str(raw["unit_code"]),
        home_branch=str(raw["home_branch"]),
        password_hash=str(raw["password_hash"]),
        must_change_password=bool(raw.get("must_change_password", True)),
    )


def _default_admin_record() -> Dict[str, Any]:
    return {
        "user_id": int(DEFAULT_ADMIN_USER_ID),
        "display_name": DEFAULT_ADMIN_DISPLAY_NAME,
        "role": DEFAULT_ADMIN_ROLE,
        "unit_code": DEFAULT_ADMIN_UNIT_CODE,
        "home_branch": DEFAULT_ADMIN_HOME_BRANCH,
        "password_hash": _hash_password(INITIAL_PASSWORD),
        "must_change_password": True,
    }


def _safe_read_json() -> Dict[str, dict]:
    if not USER_STORE.exists():
        return {}

    try:
        raw = USER_STORE.read_text(encoding="utf-8").strip()
        if not raw:
            return {}
        data = json.loads(raw)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _save_users(users: Dict[str, dict]) -> None:
    USER_STORE.parent.mkdir(parents=True, exist_ok=True)
    USER_STORE.write_text(json.dumps(users, indent=2), encoding="utf-8")


def _ensure_store() -> None:
    users = _safe_read_json()

    if DEFAULT_ADMIN_USER_ID not in users:
        users[DEFAULT_ADMIN_USER_ID] = _default_admin_record()

    _save_users(users)


try:
    _ensure_store()
except Exception:
    # Fail closed later during auth if the store is unusable.
    pass


def _load_users() -> Dict[str, dict]:
    return _safe_read_json()
def load_users() -> Dict[str, dict]:
    """
    Public loader for compatibility with auth_gate and any admin utilities.
    Returns the raw keyed user dictionary.
    """
    return _load_users()


def get_user(user_id: int | str) -> Optional[Dict[str, Any]]:
    """
    Primary reader expected by auth_gate.
    Returns a plain dict or None.
    """
    try:
        key = _normalize_user_key(user_id)
    except Exception:
        return None

    users = _load_users()
    raw = users.get(key)
    if not isinstance(raw, dict):
        return None

    try:
        return _coerce_record(raw).to_dict()
    except Exception:
        return None


def find_user(user_id: int | str) -> Optional[Dict[str, Any]]:
    """
    Alias for compatibility with alternate gate/import paths.
    """
    return get_user(user_id)


def verify_password(user: Dict[str, Any], password: str) -> bool:
    """
    Boolean password verifier expected by auth_gate fallback paths.
    """
    try:
        stored_hash = str(user.get("password_hash", ""))
        if not stored_hash:
            return False
        return stored_hash == _hash_password(password)
    except Exception:
        return False


def authenticate(user_id: int | str, password: str) -> bool:
    """
    Auth_gate expects a strict boolean True/False here.
    Never raise for normal auth failure.
    """
    try:
        record = get_user(user_id)
        if not record:
            return False
        return verify_password(record, password)
    except Exception:
        return False


def change_password(user_id: int | str, new_password: str) -> bool:
    """
    Auth_gate expects literal True on success.
    Password policy here is aligned to auth_gate:
    - not empty
    - maximum length = 6
    """
    try:
        key = _normalize_user_key(user_id)
    except Exception:
        return False

    new_password = str(new_password).strip()

    if not new_password:
        return False

    if len(new_password) > 6:
        return False

    users = _load_users()
    if key not in users or not isinstance(users[key], dict):
        return False

    users[key]["password_hash"] = _hash_password(new_password)
    users[key]["must_change_password"] = False
    _save_users(users)
    return True


def create_user(
    user_id: int | str,
    display_name: str,
    role: str,
    unit_code: str,
    home_branch: str,
    temp_password: str = INITIAL_PASSWORD,
    must_change_password: bool = True,
) -> bool:
    """
    Creates a new user and returns True on success.
    Fails with RuntimeError only for clearly invalid admin actions.
    """
    key = _normalize_user_key(user_id)

    display_name = str(display_name).strip()
    role = str(role).strip().upper()
    unit_code = str(unit_code).strip().upper() or "CORE"
    home_branch = str(home_branch).strip().upper() or "HQ"
    temp_password = str(temp_password).strip()

    if not display_name:
        raise RuntimeError("USER_CREATE_FAIL: blank_display_name")

    if not role:
        raise RuntimeError("USER_CREATE_FAIL: blank_role")

    if not temp_password:
        raise RuntimeError("USER_CREATE_FAIL: blank_temp_password")

    if len(temp_password) > 6:
        raise RuntimeError("USER_CREATE_FAIL: password_too_long")

    users = _load_users()
    if key in users:
        raise RuntimeError("USER_ALREADY_EXISTS")

    record = UserRecord(
        user_id=int(key),
        display_name=display_name,
        role=role,
        unit_code=unit_code,
        home_branch=home_branch,
        password_hash=_hash_password(temp_password),
        must_change_password=bool(must_change_password),
    )

    users[key] = record.to_dict()
    _save_users(users)
    return True


def upsert_user(
    user_id: int | str,
    display_name: str,
    role: str,
    unit_code: str,
    home_branch: str,
    temp_password: str = INITIAL_PASSWORD,
    must_change_password: bool = True,
) -> bool:
    """
    Safe admin helper for seeding or updating a record without breaking auth.
    """
    key = _normalize_user_key(user_id)

    display_name = str(display_name).strip() or "CSS User"
    role = str(role).strip().upper() or "VIEWER"
    unit_code = str(unit_code).strip().upper() or "CORE"
    home_branch = str(home_branch).strip().upper() or "HQ"
    temp_password = str(temp_password).strip() or INITIAL_PASSWORD

    if len(temp_password) > 6:
        raise RuntimeError("USER_UPSERT_FAIL: password_too_long")

    users = _load_users()
    users[key] = UserRecord(
        user_id=int(key),
        display_name=display_name,
        role=role,
        unit_code=unit_code,
        home_branch=home_branch,
        password_hash=_hash_password(temp_password),
        must_change_password=bool(must_change_password),
    ).to_dict()

    _save_users(users)
    return True
def list_users() -> list[Dict[str, Any]]:
    """
    Admin-friendly listing helper.
    Returns normalized user dicts sorted by user_id.
    """
    users = _load_users()
    rows: list[Dict[str, Any]] = []

    for key in sorted(users.keys()):
        raw = users.get(key)
        if not isinstance(raw, dict):
            continue
        try:
            rows.append(_coerce_record(raw).to_dict())
        except Exception:
            continue

    return rows


def delete_user(user_id: int | str) -> bool:
    """
    Optional admin helper.
    Protects the default admin from accidental deletion.
    """
    try:
        key = _normalize_user_key(user_id)
    except Exception:
        return False

    if key == DEFAULT_ADMIN_USER_ID:
        return False

    users = _load_users()
    if key not in users:
        return False

    del users[key]
    _save_users(users)
    return True


def ensure_default_admin() -> bool:
    """
    Public bootstrap helper.
    Ensures the canonical initial admin exists.
    """
    try:
        users = _load_users()
        if DEFAULT_ADMIN_USER_ID not in users:
            users[DEFAULT_ADMIN_USER_ID] = _default_admin_record()
            _save_users(users)
        return True
    except Exception:
        return False


def registry_healthcheck() -> Dict[str, Any]:
    """
    Lightweight diagnostic for startup troubleshooting.
    """
    try:
        users = _load_users()
        admin_present = DEFAULT_ADMIN_USER_ID in users
        return {
            "ok": True,
            "user_store": str(USER_STORE),
            "user_count": len(users),
            "default_admin_present": admin_present,
        }
    except Exception as exc:
        return {
            "ok": False,
            "user_store": str(USER_STORE),
            "error": str(exc),
        }


if __name__ == "__main__":
    ok = ensure_default_admin()
    info = registry_healthcheck()
    print("CSS user_registry ready.")
    print(f"bootstrap_ok={ok}")
    print(json.dumps(info, indent=2))