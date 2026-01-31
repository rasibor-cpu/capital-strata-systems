from decimal import Decimal
from postings.api import PostingStore
from postings.models import PostingType

store = PostingStore()

t = store.create_ticket(
    posting_type=PostingType.JOURNAL,
    amount=Decimal("1000.00"),
    currency="USD",
    debit_account="CASH_USD",
    credit_account="INCOME_USD",
    maker_user="maker1",
    description="Test posting",
    approval_level_required=1,
)

print("CREATED", t.status)
store.submit(t.ticket_id)
print("SUBMITTED", t.status)
store.approve(t.ticket_id, approver_user="checker1")
print("APPROVED", t.status)
print("DICT", store.to_dict(t.ticket_id))
