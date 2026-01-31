"""
auth_control.py — Authentication, Password & Session Governance
---------------------------------------------------------------
Implements:
- Password expiry (30 days)
- Password history (new != last 2)
- Lockout after 3 failed attempts
- Admin-only reset/unlock
- Session idle timeout (3 minutes)

Prompt-only / demo-safe. No external auth systems.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import hashlib
import uuid


# -----------------------------
# Constants
# -----------------------------
PASSWORD_EXPIRY_DAYS = 30
MAX_FAILED_ATTEMPTS = 3
IDLE_TIMEOUT_SECONDS = 180  # 3 minutes


# -----------------------------
# Helpers
# -----------------------------

def _hash_password(pw: str) -> str:
    return hashlib.sha256(pw.encode("utf-8")).hexdigest()


def _now() -> datetime:
    return datetime.utcnow()


# -----------------------------
# User Record
# -----------------------------

@dataclass
class UserRecord:
    username: str
    role: str                      # USER / SUPERVISOR / ADMIN / SUPER
    password_hash: str
    password_history: List[str] = field(default_factory=list)
    password_set_at: datetime = field(default_factory=_now)
    failed_attempts: int = 0
    locked: bool = False


# -----------------------------
# Session Record
# -----------------------------

@dataclass
class Session:
    session_id: str
    username: str
    last_activity: datetime
    active: bool = True


# -----------------------------
# Auth Controller
# -----------------------------

class AuthController:
    def __init__(self):
        self.users: Dict[str, UserRecord] = {}
        self.sessions: Dict[str, Session] = {}

    # -------------------------
    # User management
    # -------------------------

    def create_user(self, username: str, role: str, initial_password: str) -> None:
        if username in self.users:
            raise ValueError("User already exists")

        pw_hash = _hash_password(initial_password)
        self.users[username] = UserRecord(
            username=username,
            role=role,
            password_hash=pw_hash,
            password_history=[],
            password_set_at=_now(),
        )

    def _check_password_rules(self, user: UserRecord, new_password: str) -> None:
        new_hash = _hash_password(new_password)
        recent = [user.password_hash] + user.password_history[-2:]
        if new_hash in recent:
            raise ValueError("New password must differ from last two passwords")

    def reset_password_admin(
        self,
        admin_username: str,
        target_username: str,
        new_password: str,
    ) -> None:
        admin = self.users.get(admin_username)
        if not admin or admin.role != "ADMIN":
            raise PermissionError("Only ADMIN can reset passwords")

        user = self.users.get(target_username)
        if not user:
            raise ValueError("Target user not found")

        self._check_password_rules(user, new_password)

        # rotate password
        user.password_history.append(user.password_hash)
        user.password_history = user.password_history[-2:]
        user.password_hash = _hash_password(new_password)
        user.password_set_at = _now()
        user.failed_attempts = 0
        user.locked = False

    # -------------------------
    # Authentication
    # -------------------------

    def authenticate(self, username: str, password: str) -> Session:
        user = self.users.get(username)
        if not user:
            raise PermissionError("Invalid credentials")

        if user.locked:
            raise PermissionError("User account is locked")

        # password expiry
        if _now() - user.password_set_at > timedelta(days=PASSWORD_EXPIRY_DAYS):
            raise PermissionError("Password expired — must be reset by ADMIN")

        if _hash_password(password) != user.password_hash:
            user.failed_attempts += 1
            if user.failed_attempts >= MAX_FAILED_ATTEMPTS:
                user.locked = True
            raise PermissionError("Invalid credentials")

        # success
        user.failed_attempts = 0
        session = Session(
            session_id=str(uuid.uuid4()),
            username=username,
            last_activity=_now(),
        )
        self.sessions[session.session_id] = session
        return session

    # -------------------------
    # Session management
    # -------------------------

    def touch(self, session_id: str) -> None:
        session = self.sessions.get(session_id)
        if not session or not session.active:
            raise PermissionError("Session inactive")

        if _now() - session.last_activity > timedelta(seconds=IDLE_TIMEOUT_SECONDS):
            session.active = False
            raise PermissionError("Session timed out due to inactivity")

        session.last_activity = _now()

    def logout(self, session_id: str) -> None:
        session = self.sessions.get(session_id)
        if session:
            session.active = False
