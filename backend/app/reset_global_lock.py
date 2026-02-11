"""
Capital Strata Systems
Global Drawdown Reset Utility

Purpose:
- Manually clear global_shutdown state
- Preserve audit trail via console print
- Requires explicit execution

Usage:
    python -m backend.app.reset_global_lock
"""

from __future__ import annotations

import json
from pathlib import Path

STATE_FILE = Path("engine/risk/risk_state.json")


def main() -> None:
    print("\n" + "=" * 60)
    print("CAPITAL STRATA — GLOBAL LOCK RESET")
    print("=" * 60)

    if not STATE_FILE.exists():
        print("No risk state file found.")
        return

    with STATE_FILE.open("r") as f:
        state = json.load(f)

    if not state.get("global_shutdown"):
        print("No global shutdown active. Nothing to reset.")
        return

    print("Current shutdown reason:")
    print(state.get("global_shutdown_reason"))
    print("")

    confirm = input("Type RESET to confirm unlock: ").strip()

    if confirm != "RESET":
        print("Abort. No changes made.")
        return

    state["global_shutdown"] = False
    state["global_shutdown_reason"] = ""

    with STATE_FILE.open("w") as f:
        json.dump(state, f, indent=2)

    print("\nGlobal lock cleared.")
    print("You may resume trading if conditions justify it.")
    print("")


if __name__ == "__main__":
    main()
