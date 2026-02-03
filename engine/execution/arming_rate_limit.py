# engine/execution/arming_rate_limit.py
"""
Arming/Confirm Rate-Limit + Cooldown (runtime only, fail-closed)

Stores counters in: audit/arming_rate_limit.json  (DO NOT COMMIT)

Policies (defaults; can be moved to execution_policy.json later):
- ARM attempts:
    max_per_hour = 6
    max_per_day  = 20
- CONFIRM attempts per pending window:
    max_confirm_attempts = 5
- COOLDOWN:
    after max_confirm_attempts exceeded -> cooldown_minutes = 30
    after max_per_hour/day exceeded     -> cooldown_minutes = 30

All checks are fail-closed.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, Optional

PATH = os.path.join("audit", "arming_rate_limit.json")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.isoformat()


def _parse(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


@dataclass
class RLDecision:
    allowed: bool
    reason: str
    cooldown_until_utc: Optional[str] = None


DEFAULTS = {
    "max_arm_per_hour": 6,
    "max_arm_per_day": 20,
    "max_confirm_attempts": 5,
    "cooldown_minutes": 30,
}


def _load() -> Dict[str, Any]:
    if not os.path.exists(PATH):
        return {
            "cooldown_until_utc": None,
            "arm_events": [],      # list of iso timestamps
            "confirm_events": {},  # pending_id -> list of iso timestamps
        }
    try:
        with open(PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        # fail-closed posture => treat as in cooldown
        return {
            "cooldown_until_utc": _iso(_now() + timedelta(minutes=DEFAULTS["cooldown_minutes"])),
            "arm_events": [],
            "confirm_events": {},
        }


def _save(d: Dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(PATH), exist_ok=True)
    with open(PATH, "w", encoding="utf-8") as f:
        json.dump(d, f, indent=2)


def _in_cooldown(d: Dict[str, Any]) -> Optional[str]:
    cu = d.get("cooldown_until_utc")
    if not cu:
        return None
    try:
        if _now() < _parse(cu):
            return cu
        # expired cooldown -> clear
        d["cooldown_until_utc"] = None
        _save(d)
        return None
    except Exception:
        # malformed => fail closed by forcing cooldown
        return cu


def _prune_events(events: list[str]) -> list[str]:
    # keep last 2 days only
    cutoff = _now() - timedelta(days=2)
    kept = []
    for ts in events:
        try:
            if _parse(ts) >= cutoff:
                kept.append(ts)
        except Exception:
            continue
    return kept


def check_and_record_arm() -> RLDecision:
    d = _load()

    cu = _in_cooldown(d)
    if cu:
        return RLDecision(False, "cooldown_active", cu)

    d["arm_events"] = _prune_events(d.get("arm_events", []))

    now = _now()
    one_hour = now - timedelta(hours=1)
    one_day = now - timedelta(days=1)

    arm_events = [t for t in d["arm_events"] if _parse(t) >= one_day]
    per_day = len(arm_events)
    per_hour = len([t for t in arm_events if _parse(t) >= one_hour])

    if per_hour >= DEFAULTS["max_arm_per_hour"]:
        cu_until = _iso(now + timedelta(minutes=DEFAULTS["cooldown_minutes"]))
        d["cooldown_until_utc"] = cu_until
        _save(d)
        return RLDecision(False, "arm_rate_limited_hour", cu_until)

    if per_day >= DEFAULTS["max_arm_per_day"]:
        cu_until = _iso(now + timedelta(minutes=DEFAULTS["cooldown_minutes"]))
        d["cooldown_until_utc"] = cu_until
        _save(d)
        return RLDecision(False, "arm_rate_limited_day", cu_until)

    # record
    d["arm_events"].append(_iso(now))
    _save(d)
    return RLDecision(True, "ok", None)


def check_and_record_confirm(pending_id: str) -> RLDecision:
    d = _load()

    cu = _in_cooldown(d)
    if cu:
        return RLDecision(False, "cooldown_active", cu)

    d["arm_events"] = _prune_events(d.get("arm_events", []))
    ce: Dict[str, list[str]] = d.get("confirm_events", {}) or {}
    events = ce.get(pending_id, [])
    events = _prune_events(events)

    if len(events) >= DEFAULTS["max_confirm_attempts"]:
        cu_until = _iso(_now() + timedelta(minutes=DEFAULTS["cooldown_minutes"]))
        d["cooldown_until_utc"] = cu_until
        ce[pending_id] = events
        d["confirm_events"] = ce
        _save(d)
        return RLDecision(False, "confirm_rate_limited", cu_until)

    events.append(_iso(_now()))
    ce[pending_id] = events
    d["confirm_events"] = ce
    _save(d)
    return RLDecision(True, "ok", None)
