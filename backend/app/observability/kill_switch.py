"""
Kill-Switch Scaffolding (Fail-Closed)
REA Capital Trading Engine

Purpose:
- Provide a global emergency stop that can be checked from any layer.
- Works even before execution is wired.
- Supports:
    1) ENV kill switch: REA_KILL_SWITCH=1 / true / yes
    2) File kill switch: runtime/kill.switch
    3) Pair-level kill: runtime/kill.<SYMBOL>.switch (e.g., kill.EURUSD.switch)

Behavior:
- Does not raise exceptions by default (non-invasive).
- Logs deterministic KILL_BLOCK events.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from backend.app.observability.logger import get_logger, with_trace

log = get_logger("observability.kill_switch")


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _truthy(val: Optional[str]) -> bool:
    if val is None:
        return False
    v = str(val).strip().lower()
    return v in {"1", "true", "yes", "y", "on"}


@dataclass(frozen=True)
class KillSwitchDecision:
    killed: bool
    scope: str              # "global" | "pair" | "none"
    reason: str             # env/file details
    now_utc: datetime
    pair: str = ""


def _runtime_dir() -> Path:
    # repo-relative runtime dir (works on Windows + Linux)
    return Path("runtime")


def _global_kill_file() -> Path:
    return _runtime_dir() / "kill.switch"


def _pair_kill_file(pair: str) -> Path:
    safe = (pair or "").strip().upper().replace("/", "").replace(" ", "")
    return _runtime_dir() / f"kill.{safe}.switch"


def check_kill_switch(pair: Optional[str] = None) -> KillSwitchDecision:
    """
    Evaluate kill-switch state (env + file).
    Returns a KillSwitchDecision.
    """
    now = _utc_now()

    # 1) ENV kill switch
    if _truthy(os.getenv("REA_KILL_SWITCH")):
        return KillSwitchDecision(
            killed=True,
            scope="global",
            reason="env:REA_KILL_SWITCH",
            now_utc=now,
            pair=(pair or ""),
        )

    # 2) File-based global kill
    if _global_kill_file().exists():
        return KillSwitchDecision(
            killed=True,
            scope="global",
            reason=f"file:{_global_kill_file().as_posix()}",
            now_utc=now,
            pair=(pair or ""),
        )

    # 3) Pair-level kill (optional)
    if pair:
        pf = _pair_kill_file(pair)
        if pf.exists():
            return KillSwitchDecision(
                killed=True,
                scope="pair",
                reason=f"file:{pf.as_posix()}",
                now_utc=now,
                pair=pair,
            )

    return KillSwitchDecision(
        killed=False,
        scope="none",
        reason="not_killed",
        now_utc=now,
        pair=(pair or ""),
    )


def assert_not_killed(pair: Optional[str] = None, hard_fail: bool = True) -> bool:
    """
    Non-invasive guard for any loop.
    Returns:
      - True if allowed to proceed
      - False if kill-switch is active (logs a warning)

    hard_fail controls log severity only; function never raises.
    """
    decision = check_kill_switch(pair=pair)
    adapter = with_trace(log, "KILL")

    if not decision.killed:
        return True

    level_fn = adapter.critical if hard_fail else adapter.warning
    level_fn(
        "KILL_BLOCK | scope=%s | pair=%s | reason=%s | now_utc=%s",
        decision.scope,
        decision.pair or "",
        decision.reason,
        decision.now_utc.isoformat(),
    )
    return False


def enable_global_kill_file(note: str = "") -> None:
    """
    Convenience helper for local ops:
    Creates runtime/kill.switch.
    """
    _runtime_dir().mkdir(parents=True, exist_ok=True)
    p = _global_kill_file()
    p.write_text((note or "kill enabled") + "\n", encoding="utf-8")

    adapter = with_trace(log, "KILL")
    adapter.warning("KILL_ENABLED | file=%s", p.as_posix())


def disable_global_kill_file() -> None:
    """
    Convenience helper for local ops:
    Deletes runtime/kill.switch if present.
    """
    p = _global_kill_file()
    if p.exists():
        p.unlink()

    adapter = with_trace(log, "KILL")
    adapter.warning("KILL_DISABLED | file=%s", p.as_posix())
