# engine/execution/auto_disarm.py
"""
Auto-disarm checks (fail-closed)

If any critical safety condition is violated, return a reason string.
If everything is OK, return None.

This module does NOT perform disarm; it only reports.
(run_live_guarded.py should perform actual disarm/state transitions.)
"""

from __future__ import annotations

import os
import subprocess
from typing import Optional


def _run_git(args) -> str:
    cp = subprocess.run(
        ["git"] + args,
        capture_output=True,
        text=True,
        shell=False,
    )
    if cp.returncode != 0:
        raise RuntimeError(cp.stderr.strip() or "git failed")
    return cp.stdout.strip()


def check_auto_disarm() -> Optional[str]:
    """
    Returns a string reason if disarm should be triggered, else None.
    Fail-closed: if git checks fail, we return a reason.
    """
    # 1) Working tree must be clean
    try:
        porcelain = _run_git(["status", "--porcelain"])
        if porcelain:
            return "working_tree_dirty"
    except Exception:
        return "git_status_unavailable"

    # 2) Detached HEAD is not allowed for live
    try:
        head = _run_git(["rev-parse", "--abbrev-ref", "HEAD"])
        if head == "HEAD":
            return "detached_head"
    except Exception:
        return "git_head_unavailable"

    # 3) Required config must exist
    if not os.path.exists(os.path.join("config", "superuser.json")):
        return "missing_superuser_config"
    if not os.path.exists(os.path.join("config", "execution_policy.json")):
        return "missing_execution_policy"

    return None
