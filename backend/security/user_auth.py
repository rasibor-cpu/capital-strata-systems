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
MIN_PASSWORD_LENGTH = 6

DEFAULT_ADMIN_ID = "00000"
DEFAULT_ADMIN_PASSWORD = "CSS123"

VALID_ROLES = {
    "ADMIN",
    "SUPER_USER",
    "AUDIT",
    "TECH",
    "FINCON",
    "TELLER",
    "CASH_OFFICER",
    "BRANCH_SUPERVISOR",
    "TRADER",
    "TREASURY_OPERATIONS",
    "TREASURY_MANAGER",
    "TRADE_OFFICER",
    "TRADE_OPERATIONS",
    "TRADE_MANAGER",
    "FUNDS_TRANSFER_OFFICER",
    "SETTLEMENT_OFFICER",
    "OPERATIONS_SUPERVISOR",
    "RETAIL_OFFICER",
    "CUSTOMER_SERVICE",
    "RETAIL_MANAGER",
    "COMMERCIAL_OFFICER",
    "COMMERCIAL_MANAGER",
    "CORPORATE_OFFICER",
    "INSTITUTIONAL_BANKING_OFFICER",
    "CORPORATE_MANAGER",
    "LEGAL_OFFICER",
    "CORPORATE_SERVICES_OFFICER",
    "COMPLIANCE_OFFICER",
    "CREDIT_ADMIN_OFFICER",
    "CREDIT_CONTROL",
    "CREDIT_MANAGER",
    "VIEWER",
}

RECOVERY_QUESTIONS = [
    "What city were you born in?",
    "What was the name of your first school?",
    "What is your mother's maiden name?",
    "What was the name of your first pet?",
    "What street did you grow up on?",
    "What is the name of your favorite teacher?",
    "What was your childhood nickname?",
    "What is the name of the town where your parents met?",
    "What was the first company you worked for?",
    "What is your favorite childhood food?",
    "What was the make of your first car?",
    "What is the name of your favorite cousin?",
    "What was the name of your primary school headteacher?",
    "What hospital were you born in?",
    "What was your best subject in secondary school?",
]


@dataclass
class User:
    user_id: str
    password_hash: str
    role: str
    failed_attempts: int
    locked: bool
    recovery_question: str
    recovery_answer_hash: str
    must_change_password: bool


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
            return data if isinstance(data, dict) else {}

        except Exception:
            return {}

    def _save_users(self, users: Dict[str, Dict[str, Any]]) -> None:
        USER_STORE.write_text(json.dumps(users, indent=2), encoding="utf-8")

    def _hash_password(self, password: str) -> str:
        salt = secrets.token_hex(16)
        hashed = hashlib.sha256((password + salt).encode("utf-8")).hexdigest()
        return f"{salt}:{hashed}"

    def _verify_password(self, password: str, stored: str) -> bool:
        salt, hashed = stored.split(":")
        verify = hashlib.sha256((password + salt).encode("utf-8")).hexdigest()
        return verify == hashed

    def _hash_answer(self, answer: str) -> str:
        return hashlib.sha256(answer.lower().strip().encode("utf-8")).hexdigest()

    def _validate_user_id(self, user_id: str) -> str:
        user_id = str(user_id).strip()

        if len(user_id) != 5 or not user_id.isdigit():
            raise ValueError("User ID must be exactly 5 numeric digits")

        return user_id

    def _validate_password(self, password: str) -> None:
        if len(password) < MIN_PASSWORD_LENGTH:
            raise ValueError(f"Password must contain at least {MIN_PASSWORD_LENGTH} characters")

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
            "recovery_question": RECOVERY_QUESTIONS[0],
            "recovery_answer_hash": self._hash_answer("capital"),
            "must_change_password": True,
        }

        self._save_users(users)

    def create_user(
        self,
        user_id: str,
        password: str,
        role: str,
        recovery_question: str,
        recovery_answer: str,
        must_change_password: bool = True,
    ) -> Tuple[bool, str]:
        try:
            user_id = self._validate_user_id(user_id)
            role = self._validate_role(role)
            self._validate_password(password)
        except Exception as exc:
            return False, str(exc)

        recovery_question = recovery_question.strip()
        recovery_answer = recovery_answer.strip()

        if recovery_question not in RECOVERY_QUESTIONS:
            return False, "Recovery question is not in the approved list."

        if recovery_answer == "":
            return False, "Recovery answer cannot be blank."

        users = self._load_users()

        if user_id in users:
            return False, f"User ID {user_id} already exists."

        users[user_id] = {
            "password": self._hash_password(password),
            "role": role,
            "failed_attempts": 0,
            "locked": False,
            "recovery_question": recovery_question,
            "recovery_answer_hash": self._hash_answer(recovery_answer),
            "must_change_password": bool(must_change_password),
        }

        self._save_users(users)
        return True, "User created successfully"

    def authenticate(self, user_id: str, password: str) -> Tuple[bool, str, str | None, bool]:
        try:
            user_id = self._validate_user_id(user_id)
        except Exception as e:
            return False, str(e), None, False

        users = self._load_users()

        if user_id not in users:
            return False, "User ID not found", None, False

        user = users[user_id]

        if user["locked"]:
            return False, "Account locked. Reset password required.", None, False

        if self._verify_password(password, user["password"]):
            user["failed_attempts"] = 0
            users[user_id] = user
            self._save_users(users)
            return True, "Login successful", user["role"], user["must_change_password"]

        user["failed_attempts"] += 1

        remaining = MAX_LOGIN_ATTEMPTS - user["failed_attempts"]

        if remaining <= 0:
            user["locked"] = True
            users[user_id] = user
            self._save_users(users)
            return False, "Account locked after failed attempts", None, False

        users[user_id] = user
        self._save_users(users)

        return False, f"Password incorrect. {remaining} attempts remaining", None, False

    def reset_password(self, user_id: str, answer: str, new_password: str) -> Tuple[bool, str]:
        try:
            user_id = self._validate_user_id(user_id)
            self._validate_password(new_password)
        except Exception as exc:
            return False, str(exc)

        users = self._load_users()

        if user_id not in users:
            return False, "User not found"

        user = users[user_id]

        if self._hash_answer(answer) != user["recovery_answer_hash"]:
            return False, "Recovery answer incorrect"

        user["password"] = self._hash_password(new_password)
        user["locked"] = False
        user["failed_attempts"] = 0
        user["must_change_password"] = False

        users[user_id] = user
        self._save_users(users)

        return True, "Password successfully reset"

    def change_password(self, user_id: str, old_password: str, new_password: str) -> Tuple[bool, str]:
        try:
            user_id = self._validate_user_id(user_id)
            self._validate_password(new_password)
        except Exception as exc:
            return False, str(exc)

        users = self._load_users()

        if user_id not in users:
            return False, "User not found"

        user = users[user_id]

        if not self._verify_password(old_password, user["password"]):
            return False, "Current password incorrect"

        user["password"] = self._hash_password(new_password)
        user["must_change_password"] = False
        user["failed_attempts"] = 0
        user["locked"] = False

        users[user_id] = user
        self._save_users(users)

        return True, "Password changed successfully"

    def get_recovery_question(self, user_id: str) -> Tuple[bool, str]:
        try:
            user_id = self._validate_user_id(user_id)
        except Exception as exc:
            return False, str(exc)

        users = self._load_users()

        if user_id not in users:
            return False, "User not found"

        return True, users[user_id]["recovery_question"]


if __name__ == "__main__":
    auth = UserAuth()
    print("CSS user authentication system ready.")