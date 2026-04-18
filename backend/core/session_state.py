from __future__ import annotations

import time


SESSION_LOCKED: bool = False
SESSION_LOCK_REASON: str = ""
SESSION_LOCK_TIME: float | None = None


def lock_session(reason: str) -> None:
    global SESSION_LOCKED, SESSION_LOCK_REASON, SESSION_LOCK_TIME

    SESSION_LOCKED = True
    SESSION_LOCK_REASON = reason
    SESSION_LOCK_TIME = time.time()


def unlock_session() -> None:
    global SESSION_LOCKED, SESSION_LOCK_REASON, SESSION_LOCK_TIME

    SESSION_LOCKED = False
    SESSION_LOCK_REASON = ""
    SESSION_LOCK_TIME = None


def is_session_locked() -> bool:
    return SESSION_LOCKED


def get_session_lock_state() -> dict:
    return {
        "locked": SESSION_LOCKED,
        "reason": SESSION_LOCK_REASON,
        "lock_time": SESSION_LOCK_TIME,
    }