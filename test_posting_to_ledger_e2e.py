from decimal import Decimal

from postings.api import PostingStore
from postings.models import PostingType
from postings.ledger_adapter import post_approved_ticket_to_ledger
from posting_ledger import PostingLedger


def main() -> None:
    store = PostingStore()
    ledger = PostingLedger()

    customer_id = "CUST-0001"
    customer_name = "Test Customer"
    account_ref = "BR001-0000000001"

    # Governance requirement: customer must be onboarded BEFORE postings.
    # Ledger exposes is_customer_onboarded(...). If not onboarded, we open the account.
    if not ledger.is_customer_onboarded(customer_id):
        # open_customer_account signature is defined in posting_ledger.py and is the
        # correct onboarding path in this system.
        ledger.open_customer_account(
            customer_id=customer_id,
            customer_name=customer_name,
            account_ref=account_ref,
            approved_by="super1",
            approval_level="SUPER",
        )

    # Maker creates ticket
    t = store.create_ticket(
        posting_type=PostingType.JOURNAL,
        amount=Decimal("2500.00"),
        currency="USD",
        debit_account="CASH_USD",
        credit_account="INCOME_USD",
        maker_user="maker1",
        description="E2E test posting -> ledger",
        approval_level_required=2,  # SUPERVISOR+
    )
    print("CREATED", t.ticket_id, t.status)

    # Submit + approve
    store.submit(t.ticket_id)
    print("SUBMITTED", t.status)

    store.approve(t.ticket_id, approver_user="checker1")
    print("APPROVED", t.status, "approver:", t.approver_user)

    # Post into ledger
    post_approved_ticket_to_ledger(
        ledger=ledger,
        ticket=t,
        customer_id=customer_id,
        customer_name=customer_name,
        account_ref=account_ref,
        customer_type="CUSTOMER",
        ledger_type="CUSTOMER",
        domain="TREASURY",
        transaction_type="POSTING",
        approver_level="SUPERVISOR",
    )
    print("POSTED", t.status)

    last_two = ledger.entries[-2:]
    print("\nLAST TWO LEDGER ENTRIES:")
    for e in last_two:
        print(
            f"- {e.entry_id} | {e.side} | {e.ledger_id} | "
            f"{e.currency} {e.notional} | {e.description}"
        )

    assert last_two[0].side == "DR"
    assert last_two[1].side == "CR"
    assert last_two[0].notional == last_two[1].notional
    assert last_two[0].currency == last_two[1].currency

    print("\nE2E OK ✅")


if __name__ == "__main__":
    main()
