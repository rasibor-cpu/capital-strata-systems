# engine/execution/live_state.py
"""
Live state reader (READ-ONLY)

Reads runtime arming state from audit/live_state.json (runtime artifact; never committed).
Fail-closed: if missing or invalid => DISARMED.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional


LIVE_STATE_PATH = os.path.join("audit", "live_state.json")


@dataclass(frozen=True)
class LiveState:
    state: str  # DISARMED | ARMED_PENDING | ARMED_ACTIVE
    expires_at_utc: Optional[str] = None  # ISO8601 UTC timestamp

    def is_expired(self) -> bool:
        if not self.expires_at_utc:
            return False
        try:
            dt = datetime.fromisoformat(self.expires_at_utc.replace("Z", "+00:00"))
            return datetime.now(timezone.utc) >= dt
        except Exception:
            # Fail-closed: treat malformed expiry as expired
            return True


def get_live_state() -> LiveState:
    # Default fail-closed
    if not os.path.exists(LIVE_STATE_PATH):
        return LiveState(state="DISARMED", expires_at_utc=None)

    try:
        with open(LIVE_STATE_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        state = data.get("armed_state") or data.get("state") or "DISARMED"
        expires = data.get("expires_at_utc")
        return LiveState(state=str(state), expires_at_utc=expires)
    except Exception:
        return LiveState(state="DISARMED", expires_at_utc=None)
