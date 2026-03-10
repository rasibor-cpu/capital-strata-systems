from __future__ import annotations
import secrets
import time
from dataclasses import dataclass


@dataclass
class Session:
    session_id: str
    username: str
    role: str
    created: float


class SessionManager:

    """
    CSS Session Manager
    Handles login sessions
    """

    def __init__(self):

        self.sessions = {}

    def create_session(self, username, role):

        session_id = secrets.token_hex(16)

        session = Session(
            session_id=session_id,
            username=username,
            role=role,
            created=time.time()
        )

        self.sessions[session_id] = session

        return session

    def get_session(self, session_id):

        return self.sessions.get(session_id)

    def destroy_session(self, session_id):

        if session_id in self.sessions:
            del self.sessions[session_id]

    def list_sessions(self):

        return list(self.sessions.values())


if __name__ == "__main__":

    sm = SessionManager()

    s = sm.create_session(
        "admin",
        "ADMIN"
    )

    print("Session created:", s.session_id)