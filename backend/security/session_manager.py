from __future__ import annotations

import secrets
import time
import json
from dataclasses import dataclass
from pathlib import Path


SESSION_FILE = Path("artifacts/session_state.json")


@dataclass
class Session:
    session_id: str
    username: str
    role: str
    created: float
    last_active: float


class SessionManager:

    def __init__(self, idle_timeout_seconds=3600, max_session_seconds=28800):
        self.sessions = {}
        self.idle_timeout_seconds = idle_timeout_seconds
        self.max_session_seconds = max_session_seconds

    def create_session(self, username, role, idle_timeout_seconds=None, max_session_seconds=None):
        now = time.time()

        if idle_timeout_seconds is not None:
            self.idle_timeout_seconds = idle_timeout_seconds
        if max_session_seconds is not None:
            self.max_session_seconds = max_session_seconds

        session_id = secrets.token_hex(16)

        session = Session(
            session_id=session_id,
            username=username,
            role=role,
            created=now,
            last_active=now,
        )

        self.sessions[session_id] = session
        self.save_session(session)
        return session

    def save_session(self, session):
        try:
            data = {
                "session_id": session.session_id,
                "username": session.username,
                "role": session.role,
                "created": session.created,
                "last_active": session.last_active,
                "idle_timeout_seconds": self.idle_timeout_seconds,
                "max_session_seconds": self.max_session_seconds,
            }

            SESSION_FILE.parent.mkdir(exist_ok=True)

            with open(SESSION_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f)

        except Exception:
            pass

    def restore_session(self):
        try:
            if not SESSION_FILE.exists():
                return None

            with open(SESSION_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)

            now = time.time()

            saved_idle = int(data.get("idle_timeout_seconds", self.idle_timeout_seconds))
            saved_max = int(data.get("max_session_seconds", self.max_session_seconds))

            self.idle_timeout_seconds = saved_idle
            self.max_session_seconds = saved_max

            if now - float(data["last_active"]) > self.idle_timeout_seconds:
                return None

            if now - float(data["created"]) > self.max_session_seconds:
                return None

            session = Session(
                session_id=data["session_id"],
                username=data["username"],
                role=data["role"],
                created=float(data["created"]),
                last_active=float(data["last_active"]),
            )

            self.sessions[session.session_id] = session
            return session

        except Exception:
            return None

    def touch_session(self, session_id):
        session = self.sessions.get(session_id)
        if not session:
            return

        session.last_active = time.time()
        self.save_session(session)

    def get_session(self, session_id):
        return self.sessions.get(session_id)

    def get_session_status(self, session_id):
        session = self.sessions.get(session_id)

        if not session:
            return {
                "active": False,
                "end_reason": "not_found",
                "created": None,
                "last_activity": None,
                "idle_timeout_seconds": self.idle_timeout_seconds,
                "max_session_seconds": self.max_session_seconds,
            }

        now = time.time()

        if now - session.last_active > self.idle_timeout_seconds:
            return {
                "active": False,
                "end_reason": "idle_timeout",
                "created": session.created,
                "last_activity": session.last_active,
                "idle_timeout_seconds": self.idle_timeout_seconds,
                "max_session_seconds": self.max_session_seconds,
            }

        if now - session.created > self.max_session_seconds:
            return {
                "active": False,
                "end_reason": "max_duration_exceeded",
                "created": session.created,
                "last_activity": session.last_active,
                "idle_timeout_seconds": self.idle_timeout_seconds,
                "max_session_seconds": self.max_session_seconds,
            }

        return {
            "active": True,
            "end_reason": None,
            "created": session.created,
            "last_activity": session.last_active,
            "idle_timeout_seconds": self.idle_timeout_seconds,
            "max_session_seconds": self.max_session_seconds,
        }

    def destroy_session(self, session_id, reason="manual"):
        if session_id in self.sessions:
            del self.sessions[session_id]

        try:
            if SESSION_FILE.exists():
                SESSION_FILE.unlink()
        except Exception:
            pass

    def list_sessions(self):
        return list(self.sessions.values())