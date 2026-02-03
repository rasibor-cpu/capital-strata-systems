# engine/runtime/live_banner.py
"""
Live Banner (Operator Visibility) — runtime-only logging.

Purpose:
- Print an unmistakable LIVE/SAFE status banner every run
- Include: arming state, expiry, policy version, gate decision/reason, auto-disarm reason
- Write to audit/live_banner.log (runtime artifact; never commit)

This module NEVER places orders. Pure visibility.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Optional, Dict, Any


BANNER_LOG_PATH = os.path.join("audit", "live_banner.log")


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _append_log(line: str) -> None:
    os.makedirs(os.path.dirname(BANNER_LOG_PATH), exist_ok=True)
    with open(BANNER_LOG_PATH, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def render_banner(
    armed_state: str,
    expires_at_utc: Optional[str],
    policy_version: str,
    gate_decision: str,
    gate_reason: str,
    auto_disarm_reason: Optional[str] = None,
) -> str:
    expires = expires_at_utc or "n/a"
    disarm = auto_disarm_reason or "none"

    lines = [
        "",
        "==================== REA LIVE STATUS ====================",
        f"UTC Now      : {_utc_now()}",
        f"State        : {armed_state}",
        f"Expires (UTC): {expires}",
        f"Policy       : v{policy_version}",
        f"Exec Gate    : {gate_decision} | {gate_reason}",
        f"Auto-Disarm  : {disarm}",
        "=========================================================",
        "",
    ]
    return "\n".join(lines)


def emit_banner(
    armed_state: str,
    expires_at_utc: Optional[str],
    policy_version: str,
    gate_decision: str,
    gate_reason: str,
    auto_disarm_reason: Optional[str] = None,
    extra_meta: Optional[Dict[str, Any]] = None,
) -> None:
    banner = render_banner(
        armed_state=armed_state,
        expires_at_utc=expires_at_utc,
        policy_version=policy_version,
        gate_decision=gate_decision,
        gate_reason=gate_reason,
        auto_disarm_reason=auto_disarm_reason,
    )
    print(banner)

    # Runtime log line (single-line JSON-ish text for quick grep)
    meta = extra_meta or {}
    log_line = (
        f"{_utc_now()} | state={armed_state} | exp={expires_at_utc or 'n/a'} "
        f"| policy=v{policy_version} | gate={gate_decision}:{gate_reason} "
        f"| autodisarm={auto_disarm_reason or 'none'} | meta={meta}"
    )
    _append_log(log_line)
