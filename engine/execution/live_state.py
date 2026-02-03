# engine/execution/live_state.py
"""
Authoritative Live State + Enforcement (Backward Compatible)

Supports old schema keys:
  - armed_state (old)
  - state       (new)

Normalizes to:
  state: DISARMED | ARMED_PENDING | ARMED_ACTIVE

Fail-closed always.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any

STATE_PATH = os.path.join("audit", "live_state.json")


@dataclass
class LiveState:
    state: str  # DISARMED | ARMED_PENDING | ARMED_ACTIVE
    expires_at_utc: Optional[str]
    last_updated_utc: str
    reason: str

    def is_expired(self) -> bool:
        if not self.expires_at_utc:
            return False
        try:
            exp = datetime.fromisoformat(self.expires_at_utc.replace("Z", "+00:00"))
            return datetime.now(timezone.utc) > exp
        except Exception:
            # malformed expiry => treat as expired
            return True


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalize(d: Dict[str, Any]) -> LiveState:
    """
    Accepts both old and new JSON keys and returns normalized LiveState.
    """
    # Old key fallback
    state = d.get("state") or d.get("armed_state") or "DISARMED"
    expires = d.get("expires_at_utc")

    # Older files sometimes used different key names; tolerate if present.
    if not expires:
        expires = d.get("expires_utc") or d.get("expires_at") or None

    last_updated = d.get("last_updated_utc") or d.get("ts") or _utc_now()
    reason = d.get("reason") or "loaded"

    return LiveState(
        state=str(state),
        expires_at_utc=expires,
        last_updated_utc=str(last_updated),
        reason=str(reason),
    )


def _write(ls: LiveState) -> None:
    os.makedirs(os.path.dirname(STATE_PATH), exist_ok=True)
    with open(STATE_PATH, "w", encoding="utf-8") as f:
        json.dump(ls.__dict__, f, indent=2)


def _read() -> LiveState:
    if not os.path.exists(STATE_PATH):
        return LiveState(
            state="DISARMED",
            expires_at_utc=None,
            last_updated_utc=_utc_now(),
            reason="initial",
        )

    try:
        with open(STATE_PATH, "r", encoding="utf-8") as f:
            d = json.load(f)
        return _normalize(d)
    except Exception:
        # fail-closed
        return LiveState(
            state="DISARMED",
            expires_at_utc=None,
            last_updated_utc=_utc_now(),
            reason="read_failed",
        )


# ---------- PUBLIC API ----------

def get_live_state() -> LiveState:
    return _read()


def force_disarm(reason: str) -> LiveState:
    ls = LiveState(
        state="DISARMED",
        expires_at_utc=None,
        last_updated_utc=_utc_now(),
        reason=reason,
    )
    _write(ls)
    return ls


def request_arm(ttl_minutes: int = 15) -> LiveState:
    now = datetime.now(timezone.utc)
    expires = now + timedelta(minutes=ttl_minutes)

    ls = LiveState(
        state="ARMED_PENDING",
        expires_at_utc=expires.isoformat(),
        last_updated_utc=_utc_now(),
        reason="awaiting_reconfirmation",
    )
    _write(ls)
    return ls


def confirm_arm(preflight_ok: bool) -> LiveState:
    ls = _read()

    # HARD GUARDS
    if ls.state != "ARMED_PENDING":
        return force_disarm("confirm_invalid_state")

    if not preflight_ok:
        return force_disarm("preflight_failed")

    # expiry must exist + not expired
    if not ls.expires_at_utc:
        return force_disarm("missing_expiry")

    if ls.is_expired():
        return force_disarm("token_expired")

    # ACTIVATE
    active = LiveState(
        state="ARMED_ACTIVE",
        expires_at_utc=ls.expires_at_utc,
        last_updated_utc=_utc_now(),
        reason="confirmed",
    )
    _write(active)
    return active
