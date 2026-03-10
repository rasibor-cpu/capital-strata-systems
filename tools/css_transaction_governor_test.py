from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(PROJECT_ROOT))

from backend.security.transaction_governor import TransactionGovernor


def main():

    governor = TransactionGovernor()

    print()
    print("===========================================")
    print(" CSS TRANSACTION GOVERNANCE TEST CONSOLE ")
    print("===========================================")
    print()

    user_id = input("User ID: ").strip()
    role = input("Role: ").strip()
    action = input("Action: ").strip()

    payload = {"example": "data"}

    decision = governor.process(user_id, role, action, payload)

    print()
    print("Allowed:", decision.allowed)
    print("Requires Approval:", decision.requires_approval)
    print("Reason:", decision.reason)

    if decision.action_id:
        print("Pending Action ID:", decision.action_id)

    print()


if __name__ == "__main__":
    main()