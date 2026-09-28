"""Commercial receipt generation with reconciliation gating.

Receipts are deterministic: the same durable collection data always yields
the same receipt (identifier, timestamp and content), so a receipt can be
regenerated and verified at any time. Corrections never mutate a receipt; a
refund, reversal or chargeback produces a separate adjustment receipt that
references the original PAID receipt.
"""
from datetime import datetime
import uuid

from engine.domain.collections import CollectionStatus, CollectionTransaction, TransactionReceipt

# Fixed namespace so receipt identifiers are stable across processes and hosts.
_RECEIPT_NAMESPACE = uuid.UUID("5b0f5e0e-6c1e-4e5a-9d8e-3c2a1f0b7e44")
_TERMINAL = {CollectionStatus.REFUNDED, CollectionStatus.REVERSED, CollectionStatus.CHARGEBACK}


class ReceiptNotReconciledError(ValueError):
    pass


def _receipt_id(collection_id: str, kind: str) -> str:
    return f"CSS-RCP-{uuid.uuid5(_RECEIPT_NAMESPACE, f'{collection_id}:{kind}')}"


def generate_paid_receipt(
    collection: CollectionTransaction,
    *,
    instrument: str | None = None,
    fee_schedule_id: str | None = None,
) -> TransactionReceipt:
    """Generate a PAID receipt only from a settled, reconciled collection.

    ``generated_at`` is the reconciliation time: the moment the payment became
    evidenced, not the wall-clock time of rendering.
    """
    if not collection.may_be_marked_paid:
        raise ReceiptNotReconciledError(
            "Paid receipt requires SETTLED status, settlement reference, "
            "ledger transaction and reconciliation timestamp."
        )

    return TransactionReceipt(
        receipt_id=_receipt_id(collection.collection_id, "PAID"),
        collection_id=collection.collection_id,
        customer_id=collection.customer_id,
        account_id=collection.account_id,
        amount=collection.amount,
        currency=collection.currency,
        status="PAID",
        generated_at=collection.reconciled_at,
        ledger_txn_id=collection.ledger_txn_id or "",
        reconciliation_reference=collection.settlement_reference or "",
        provider_reference=collection.provider_reference,
        instrument=instrument,
        fee_schedule_id=fee_schedule_id,
    )


def generate_adjustment_receipt(
    collection: CollectionTransaction,
    *,
    original_receipt: TransactionReceipt,
    adjustment_ledger_txn_id: str,
    adjusted_at: datetime,
) -> TransactionReceipt:
    """Receipt for a refund, reversal or chargeback of a previously PAID collection.

    Requires the collection to be in a terminal adjustment state after having
    been settled and reconciled, the original receipt to be this collection's
    PAID receipt, the adjustment to be posted to the ledger, and the durable
    time of the terminal event (from the collection lifecycle history).
    """
    if collection.status not in _TERMINAL:
        raise ReceiptNotReconciledError("adjustment receipt requires a terminal REFUNDED, REVERSED or CHARGEBACK state")
    if not (collection.settled_at and collection.reconciled_at and collection.settlement_reference and collection.ledger_txn_id):
        raise ReceiptNotReconciledError("adjustment receipt requires evidence that the collection was settled and reconciled")
    if (
        original_receipt.status != "PAID"
        or original_receipt.collection_id != collection.collection_id
        or original_receipt.receipt_id != _receipt_id(collection.collection_id, "PAID")
    ):
        raise ReceiptNotReconciledError("adjustment must reference this collection's original PAID receipt")
    if not adjustment_ledger_txn_id:
        raise ReceiptNotReconciledError("adjustment receipt requires the posted adjustment ledger transaction")
    if adjusted_at is None:
        raise ReceiptNotReconciledError("adjustment receipt requires the recorded time of the terminal event")

    return TransactionReceipt(
        receipt_id=_receipt_id(collection.collection_id, collection.status.value),
        collection_id=collection.collection_id,
        customer_id=collection.customer_id,
        account_id=collection.account_id,
        amount=collection.amount,
        currency=collection.currency,
        status=collection.status.value,
        generated_at=adjusted_at,
        ledger_txn_id=adjustment_ledger_txn_id,
        reconciliation_reference=collection.settlement_reference,
        provider_reference=collection.provider_reference,
        instrument=original_receipt.instrument,
        fee_schedule_id=original_receipt.fee_schedule_id,
        reversal_of_receipt_id=original_receipt.receipt_id,
    )
