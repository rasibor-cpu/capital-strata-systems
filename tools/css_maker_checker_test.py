from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(PROJECT_ROOT))

from backend.security.maker_checker import MakerCheckerEngine


def main():

    engine = MakerCheckerEngine()

    print()
    print("====================================")
    print(" CSS MAKER CHECKER TEST CONSOLE ")
    print("====================================")
    print()

    maker = input("Maker User ID: ").strip()

    action = input("Action Type: ").strip()

    payload = {"example": "data"}

    action_id = engine.submit_action(maker, action, payload)

    print()
    print("Action submitted.")
    print("Action ID:", action_id)

    print()
    print("Pending Actions:")

    for a in engine.list_pending():
        print(a.action_id, a.action_type, a.maker_user)

    print()

    checker = input("Checker User ID: ").strip()

    ok = engine.approve(checker, action_id)

    if ok:
        print("Action approved by:", checker)
    else:
        print("Approval failed (maker cannot approve own action).")


if __name__ == "__main__":
    main()