"""
tools/run_posting_ledger_smoke.py

Posting → Approval → Ledger Smoke Test (Phase 14a)
Runs in one process so in-memory Journal/GL state is visible.

Expected:
- ENTRY stores ticket as DRAFT
- SUBMIT moves to SUBMITTED
- APPROVE moves to APPROVED + posts to Journal + updates GL
- TRIAL_BALANCE shows balances
"""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.app.screens.posting import posting_entry_handler as entry
from backend.app.screens.posting_lifecycle import posting_submit_handler as sub
from backend.app.screens.posting_approval import posting_approval_handler as app
from backend.app.ledger.ledger_registry import trial_balance


def main() -> None:
    payload = {
        "ticket_id": "T-0006",
        "execution_date": "2026-02-01",
        "value_date": "2026-02-01",
        "lines": [
            {"side": "DR", "account_no": "100", "currency": "USD", "amount": 1000, "narrative": "test"},
            {"side": "CR", "account_no": "200", "currency": "USD", "amount": 1000, "narrative": "test"},
        ],
    }

    print("ENTRY:", entry(payload, user_id="maker_1"))
    print("SUBMIT:", sub({"ticket_id": payload["ticket_id"]}, user_id="maker_1"))
    print("APPROVE:", app({"ticket_id": payload["ticket_id"], "decision": "approve"}, user_id="checker_1"))
    print("TRIAL_BALANCE:", trial_balance())


if __name__ == "__main__":
    main()