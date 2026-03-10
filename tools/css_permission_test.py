from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(PROJECT_ROOT))

from backend.security.permissions import PermissionEngine


def main() -> None:
    engine = PermissionEngine()

    print()
    print("====================================")
    print(" CSS PERMISSION ENGINE TEST CONSOLE ")
    print("====================================")
    print()

    while True:
        role = input("Enter role (or 'exit'): ").strip()

        if role.lower() == "exit":
            break

        action = input("Enter action: ").strip()

        decision = engine.check(role, action)

        print()
        print("Decision:", decision.allowed)
        print("Role:", decision.role)
        print("Action:", decision.action)
        print("Reason:", decision.reason)
        print()


if __name__ == "__main__":
    main()