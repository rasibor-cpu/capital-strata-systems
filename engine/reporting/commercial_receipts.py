"""Commercial receipt generation with reconciliation gating."""
from datetime import datetime
import uuid

from engine.domain.collections import CollectionTransaction, TransactionReceipt


class ReceiptNotReconciledError(ValueError):
    pass


def generate_paid_receipt(
    collection: CollectionTransaction,
    *,
    instrument: str | None = None,
    fee_schedule_id: str | None = None,
) -> TransactionReceipt:
    """Generate a PAID receipt only from a settled, reconciled collection.

    Historical corrections must be represented by a separate reversal/adjustment
    transaction and receipt; this function never mutates an existing receipt.
    """
    if not collection.may_be_marked_paid:
        raise ReceiptNotReconciledError(
            "Paid receipt requires SETTLED status, settlement reference, "
            "ledger transaction and reconciliation timestamp."
        )

    return TransactionReceipt(
        receipt_id=f"CSS-RCP-{uuid.uuid4()}",
        collection_id=collection.collection_id,
        customer_id=collection.customer_id,
        account_id=collection.account_id,
        amount=collection.amount,
        currency=collection.currency,
        status="PAID",
        generated_at=datetime.utcnow(),
        ledger_txn_id=collection.ledger_txn_id or "",
        reconciliation_reference=collection.settlement_reference or "",
        provider_reference=collection.provider_reference,
        instrument=instrument,
        fee_schedule_id=fee_schedule_id,
    )
