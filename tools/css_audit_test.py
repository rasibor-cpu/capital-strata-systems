from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(PROJECT_ROOT))

from backend.security.audit_ledger import AuditLedger


def main():

    ledger = AuditLedger()

    print()
    print("====================================")
    print(" CSS AUDIT LEDGER TEST CONSOLE ")
    print("====================================")
    print()

    user_id = input("User ID: ").strip()
    event_type = input("Event Type: ").strip()

    details = {
        "note": "test event",
        "source": "css_audit_test_console",
    }

    ledger.record(event_type, user_id, details)

    print()
    print("Event recorded successfully.")
    print()

    print("Recent Audit Events:")
    print("--------------------")

    recent = ledger.read_recent(5)

    for event in recent:
        print(event)

    print()


if __name__ == "__main__":
    main()