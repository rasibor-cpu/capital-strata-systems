# engine/execution/auto_disarm.py
"""
Auto-disarm checks (ENFORCED)

If any condition triggers, the system is immediately DISARMED.
"""

from __future__ import annotations

import subprocess
from typing import Optional
from engine.execution.live_state import force_disarm


def _working_tree_dirty() -> bool:
    r = subprocess.run(
        ["git", "status", "--porcelain"],
        capture_output=True,
        text=True,
    )
    return bool(r.stdout.strip())


def check_auto_disarm() -> Optional[str]:
    if _working_tree_dirty():
        force_disarm("working_tree_dirty")
        return "working_tree_dirty"

    return None
