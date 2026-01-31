from decimal import Decimal

from postings.api import PostingStore
from postings.mandates import MandateStore, SigningRule
from postings.models import PostingType
from postings.maker_screen_builder import build_maker_screen
from posting_ledger import PostingLedger


def main() -> None:
    s = PostingStore()
    l = PostingLedger()
    m = MandateStore()

    cid = "CUST-X"

    # Onboard customer
    if not l.is_customer_onboarded(cid):
        l.open_customer_account(
            customer_id=cid,
            customer_name="Test",
            account_ref="BR001-0001",
            approved_by="super1",
            approval_level="SUPER",
        )

    # Create + approve signature mandate
    mandate = m.create_signature_mandate(
        customer_id=cid,
        created_by="maker1",
        signing_rule=SigningRule.SINGLE,
        specimen_count=1,
    )
    mandate.approve(approved_by="super1", approval_level="SUPER")

    screen = build_maker_screen(
        store=s,
        ledger=l,
        mandates=m,
        customer_id=cid,
        posting_type=PostingType.JOURNAL,
        amount=Decimal("1000"),
        currency="USD",
        debit_account="CASH_USD",
        credit_account="INCOME_USD",
        maker_user="maker1",
        description="test",
    )

    print("OK", screen.status, screen.guard.can_submit, screen.guard.required_level)


if __name__ == "__main__":
    main()
