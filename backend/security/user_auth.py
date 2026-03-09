from __future__ import annotations

import hashlib
import json
import secrets
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Tuple

PROJECT_ROOT = Path(__file__).resolve().parents[2]
USER_STORE = PROJECT_ROOT / "data_store" / "users.json"

MAX_LOGIN_ATTEMPTS = 3
DEFAULT_ADMIN_ID = "00000"
DEFAULT_ADMIN_PASSWORD = "CSS123456"
VALID_ROLES = {"ADMIN", "TRADER", "RISK_MANAGER", "VIEWER"}


@dataclass
class User:
    user_id: str
    password_hash: str
    role: str
    failed_attempts: int
    locked: bool
    recovery_question: str
    recovery_answer_hash: str


class UserAuth:
    def __init__(self) -> None:
        USER_STORE.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_store()

    def _ensure_store(self) -> None:
        if not USER_STORE.exists():
            self._save_users({})
        users = self._load_users()
        if DEFAULT_ADMIN_ID not in users:
            self._bootstrap_default_admin(users)

    def _load_users(self) -> Dict[str, Dict[str, Any]]:
        try:
            raw = USER_STORE.read_text(encoding="utf-8").strip()
            if not raw:
                return {}
            data = json.loads(raw)
            if isinstance(data, dict):
                return data
            return {}
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            return {}

    def _save_users(self, users: Dict[str, Dict[str, Any]]) -> None:
        USER_STORE.write_text(json.dumps(users, indent=2), encoding="utf-8")

    def _hash_password(self, password: str) -> str:
        salt = secrets.token_hex(16)
        hashed = hashlib.sha256((password + salt).encode("utf-8")).hexdigest()
        return f"{salt}:{hashed}"

    def _verify_password(self, password: str, stored_hash: str) -> bool:
        salt, hashed = stored_hash.split(":")
        verify = hashlib.sha256((password + salt).encode("utf-8")).hexdigest()
        return verify == hashed

    def _hash_recovery_answer(self, answer: str) -> str:
        normalized = answer.strip().lower()
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()

    def _validate_user_id(self, user_id: str) -> str:
        user_id = str(user_id).strip()
        if len(user_id) != 5 or not user_id.isdigit():
            raise ValueError("User ID must be exactly 5 numeric digits.")
        return user_id

    def _validate_role(self, role: str) -> str:
        role = str(role).strip().upper()
        if role not in VALID_ROLES:
            raise ValueError(f"Invalid role: {role}")
        return role

    def _bootstrap_default_admin(self, users: Dict[str, Dict[str, Any]]) -> None:
        users[DEFAULT_ADMIN_ID] = {
            "password": self._hash_password(DEFAULT_ADMIN_PASSWORD),
            "role": "ADMIN",
            "failed_attempts": 0,
            "locked": False,
            "recovery_question": "What is the CSS master recovery word?",
            "recovery_answer_hash": self._hash_recovery_answer("capital"),
        }
        self._save_users(users)

    def get_user(self, user_id: str) -> Dict[str, Any] | None:
        user_id = self._validate_user_id(user_id)
        users = self._load_users()
        return users.get(user_id)

    def create_user(
        self,
        user_id: str,
        password: str,
        role: str,
        recovery_question: str,
        recovery_answer: str,
    ) -> bool:
        user_id = self._validate_user_id(user_id)
        role = self._validate_role(role)

        if len(password) < 8:
            raise ValueError("Password must be at least 8 characters long.")

        users = self._load_users()

        if user_id in users:
            raise ValueError("User ID already exists.")

        users[user_id] = {
            "password": self._hash_password(password),
            "role": role,
            "failed_attempts": 0,
            "locked": False,
            "recovery_question": recovery_question.strip(),
            "recovery_answer_hash": self._hash_recovery_answer(recovery_answer),
        }

        self._save_users(users)
        return True

    def authenticate(self, user_id: str, password: str) -> Tuple[bool, str, str | None]:
        try:
            user_id = self._validate_user_id(user_id)
        except ValueError as exc:
            return False, str(exc), None

        users = self._load_users()

        if user_id not in users:
            return False, "User ID not found.", None

        user = users[user_id]

        if bool(user.get("locked", False)):
            return False, "Account locked. Use Reset Password to unlock.", None

        stored_password = str(user.get("password", ""))

        if self._verify_password(password, stored_password):
            user["failed_attempts"] = 0
            users[user_id] = user
            self._save_users(users)
            return True, "Login successful.", str(user.get("role", "VIEWER")).upper()

        user["failed_attempts"] = int(user.get("failed_attempts", 0)) + 1

        remaining = MAX_LOGIN_ATTEMPTS - user["failed_attempts"]
        if remaining <= 0:
            user["locked"] = True
            users[user_id] = user
            self._save_users(users)
            return False, "Password failed. You have been locked out. Reset password is required.", None

        users[user_id] = user
        self._save_users(users)
        return False, f"Password failed. You have {remaining} more attempt(s) before lockout.", None

    def reset_password(self, user_id: str, answer: str, new_password: str) -> Tuple[bool, str]:
        try:
            user_id = self._validate_user_id(user_id)
        except ValueError as exc:
            return False, str(exc)

        if len(new_password) < 8:
            return False, "New password must be at least 8 characters long."

        users = self._load_users()

        if user_id not in users:
            return False, "User ID not found."

        user = users[user_id]
        provided_hash = self._hash_recovery_answer(answer)
        expected_hash = str(user.get("recovery_answer_hash", ""))

        if provided_hash != expected_hash:
            return False, "Security answer incorrect."

        user["password"] = self._hash_password(new_password)
        user["failed_attempts"] = 0
        user["locked"] = False
        users[user_id] = user
        self._save_users(users)
        return True, "Password successfully reset."

    def admin_change_password(self, user_id: str, old_password: str, new_password: str) -> Tuple[bool, str]:
        ok, message, _role = self.authenticate(user_id, old_password)
        if not ok:
            return False, message

        users = self._load_users()
        user = users[user_id]
        if len(new_password) < 8:
            return False, "New password must be at least 8 characters long."

        user["password"] = self._hash_password(new_password)
        user["failed_attempts"] = 0
        user["locked"] = False
        users[user_id] = user
        self._save_users(users)
        return True, "Password changed successfully."

    def get_recovery_question(self, user_id: str) -> Tuple[bool, str]:
        try:
            user_id = self._validate_user_id(user_id)
        except ValueError as exc:
            return False, str(exc)

        users = self._load_users()
        if user_id not in users:
            return False, "User ID not found."

        return True, str(users[user_id].get("recovery_question", "No recovery question configured."))


if __name__ == "__main__":
    auth = UserAuth()
    print("CSS user authentication system ready.")
    print(f"Initial ADMIN user ID: {DEFAULT_ADMIN_ID}")
    print(f"Initial ADMIN password: {DEFAULT_ADMIN_PASSWORD}")