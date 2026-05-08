# engine/execution/live_state.py
"""
Authoritative Live State + Enforcement (Backward Compatible) + Rate Limits

Supports old schema keys:
  - armed_state (old)
  - state       (new)

Normalizes to:
  state: DISARMED | ARMED_PENDING | ARMED_ACTIVE

Adds:
- arm / confirm rate-limits + cooldown (fail-closed)
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional, Dict, Any

from engine.execution.arming_rate_limit import check_and_record_arm, check_and_record_confirm

PROJECT_ROOT = Path(__file__).resolve().parents[2]
STATE_PATH = Path(
    os.getenv(
        "CSS_LIVE_STATE_PATH",
        str(PROJECT_ROOT / "audit" / "live_state.json"),
    )
)


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
            return True


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalize(d: Dict[str, Any]) -> LiveState:
    state = d.get("state") or d.get("armed_state") or "DISARMED"
    expires = d.get("expires_at_utc") or d.get("expires_utc") or d.get("expires_at") or None
    last_updated = d.get("last_updated_utc") or d.get("ts") or _utc_now()
    reason = d.get("reason") or "loaded"
    return LiveState(
        state=str(state),
        expires_at_utc=expires,
        last_updated_utc=str(last_updated),
        reason=str(reason),
    )


def _write(ls: LiveState) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with STATE_PATH.open("w", encoding="utf-8") as f:
        json.dump(ls.__dict__, f, indent=2)


def _read() -> LiveState:
    if not STATE_PATH.exists():
        return LiveState("DISARMED", None, _utc_now(), "initial")
    try:
        with STATE_PATH.open("r", encoding="utf-8") as f:
            d = json.load(f)
        return _normalize(d)
    except Exception:
        # fail-closed
        return LiveState("DISARMED", None, _utc_now(), "read_failed")


# ---------- PUBLIC API ----------

def get_live_state() -> LiveState:
    return _read()


def force_disarm(reason: str) -> LiveState:
    ls = LiveState("DISARMED", None, _utc_now(), reason)
    _write(ls)
    return ls


def request_arm(ttl_minutes: int = 15) -> LiveState:
    # Rate limit check (fail-closed)
    rl = check_and_record_arm()
    if not rl.allowed:
        return force_disarm(f"{rl.reason}:{rl.cooldown_until_utc or 'n/a'}")

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

    if ls.state != "ARMED_PENDING":
        return force_disarm("confirm_invalid_state")

    if not preflight_ok:
        return force_disarm("preflight_failed")

    if not ls.expires_at_utc:
        return force_disarm("missing_expiry")

    if ls.is_expired():
        return force_disarm("token_expired")

    # Confirm rate-limit per pending window
    pending_id = ls.expires_at_utc  # stable per arm window
    rl = check_and_record_confirm(pending_id=pending_id)
    if not rl.allowed:
        return force_disarm(f"{rl.reason}:{rl.cooldown_until_utc or 'n/a'}")

    active = LiveState("ARMED_ACTIVE", ls.expires_at_utc, _utc_now(), "confirmed")
    _write(active)
    return active
