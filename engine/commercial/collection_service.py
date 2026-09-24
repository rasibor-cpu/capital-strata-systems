"""Fail-closed commercial collection orchestration and accounting.

This service has no live provider credentials. It enforces legal state transitions,
idempotency and double-entry economic effects against the existing LedgerStore.
"""
from datetime import datetime
from decimal import Decimal
from typing import Dict, Optional

from engine.domain.collections import CollectionStatus, CollectionTransaction
from engine.ledger.ledger_models import LedgerEntry, LedgerTransaction
from engine.ledger.ledger_store import LedgerStore


class InvalidCollectionTransition(ValueError):
    pass


class DuplicateCollectionConflict(ValueError):
    pass


_ALLOWED = {
    CollectionStatus.OBLIGATION: {CollectionStatus.INITIATED, CollectionStatus.FAILED},
    CollectionStatus.INITIATED: {CollectionStatus.AUTHORIZED, CollectionStatus.FAILED},
    CollectionStatus.AUTHORIZED: {CollectionStatus.SETTLED, CollectionStatus.FAILED},
    CollectionStatus.SETTLED: {CollectionStatus.REFUNDED, CollectionStatus.REVERSED, CollectionStatus.CHARGEBACK},
    CollectionStatus.FAILED: set(),
    CollectionStatus.REVERSED: set(),
    CollectionStatus.REFUNDED: set(),
    CollectionStatus.CHARGEBACK: set(),
}


class CollectionService:
    def __init__(self, ledger: LedgerStore):
        self.ledger = ledger
        self._by_idempotency: Dict[str, CollectionTransaction] = {}

    def register(self, collection: CollectionTransaction) -> CollectionTransaction:
        existing = self._by_idempotency.get(collection.idempotency_key)
        if existing is not None:
            if (
                existing.obligation_id != collection.obligation_id
                or existing.customer_id != collection.customer_id
                or existing.amount != collection.amount
                or existing.currency != collection.currency
            ):
                raise DuplicateCollectionConflict(collection.idempotency_key)
            return existing
        if collection.amount <= Decimal("0"):
            raise ValueError("collection amount must be positive")
        self._by_idempotency[collection.idempotency_key] = collection
        return collection

    def transition(
        self,
        collection: CollectionTransaction,
        new_status: CollectionStatus,
        *,
        provider_reference: Optional[str] = None,
        settlement_reference: Optional[str] = None,
    ) -> CollectionTransaction:
        if new_status == collection.status:
            return collection
        if new_status not in _ALLOWED[collection.status]:
            raise InvalidCollectionTransition(f"{collection.status.value}->{new_status.value}")
        if new_status in {CollectionStatus.INITIATED, CollectionStatus.AUTHORIZED} and not provider_reference:
            raise ValueError("provider reference required")
        if new_status == CollectionStatus.SETTLED and not settlement_reference:
            raise ValueError("settlement reference required")

        collection.status = new_status
        if provider_reference:
            collection.provider_reference = provider_reference
        if new_status == CollectionStatus.INITIATED:
            collection.initiated_at = datetime.utcnow()
        if new_status == CollectionStatus.SETTLED:
            collection.settlement_reference = settlement_reference
            collection.settled_at = datetime.utcnow()
        return collection

    def post_fee_obligation(self, collection: CollectionTransaction) -> LedgerTransaction:
        return self._post_once(
            collection,
            economic_event="FEE_OBLIGATION",
            debit_account=f"AR:CUSTOMER:{collection.customer_id}:{collection.currency}",
            credit_account=f"INCOME:CSS_FEE:{collection.currency}",
            txn_type="FEE",
        )

    def post_settlement(self, collection: CollectionTransaction, settlement_account_id: str) -> LedgerTransaction:
        if collection.status != CollectionStatus.SETTLED or not collection.settlement_reference:
            raise InvalidCollectionTransition("settlement posting requires SETTLED provider state")
        txn = self._post_once(
            collection,
            economic_event="COLLECTION_SETTLEMENT",
            debit_account=f"CASH:{settlement_account_id}:{collection.currency}",
            credit_account=f"AR:CUSTOMER:{collection.customer_id}:{collection.currency}",
            txn_type="SETTLEMENT",
        )
        collection.ledger_txn_id = txn.ledger_txn_id
        return txn

    def post_terminal_adjustment(self, collection: CollectionTransaction) -> LedgerTransaction:
        """Reverse recognized fee/receivable for a settled terminal event."""
        if collection.status not in {
            CollectionStatus.REFUNDED, CollectionStatus.REVERSED, CollectionStatus.CHARGEBACK,
        }:
            raise InvalidCollectionTransition("terminal adjustment requires REFUNDED, REVERSED or CHARGEBACK")
        original_key = f"{collection.collection_id}:FEE_OBLIGATION"
        if not any(txn.meta.get("economic_event_key") == original_key for txn in self.ledger.transactions.values()):
            raise InvalidCollectionTransition("terminal adjustment requires original fee obligation")
        return self._post_once(
            collection,
            economic_event=f"{collection.status.value}_FEE_ADJUSTMENT",
            debit_account=f"INCOME:CSS_FEE:{collection.currency}",
            credit_account=f"AR:CUSTOMER:{collection.customer_id}:{collection.currency}",
            txn_type=collection.status.value,
        )

    def mark_reconciled(self, collection: CollectionTransaction, reconciliation_reference: str) -> None:
        if collection.status != CollectionStatus.SETTLED or not collection.ledger_txn_id:
            raise InvalidCollectionTransition("reconciliation requires posted settlement")
        if not reconciliation_reference:
            raise ValueError("reconciliation reference required")
        collection.reconciled_at = datetime.utcnow()
        collection.meta["reconciliation_reference"] = reconciliation_reference

    def _post_once(
        self,
        collection: CollectionTransaction,
        *,
        economic_event: str,
        debit_account: str,
        credit_account: str,
        txn_type: str,
    ) -> LedgerTransaction:
        event_key = f"{collection.collection_id}:{economic_event}"
        for txn in self.ledger.transactions.values():
            if txn.meta.get("economic_event_key") == event_key:
                return txn
        txn = LedgerTransaction(
            txn_type=txn_type,
            meta={
                "economic_event_key": event_key,
                "collection_id": collection.collection_id,
                "obligation_id": collection.obligation_id,
                "customer_id": collection.customer_id,
            },
        )
        txn.entries = [
            LedgerEntry(
                ledger_txn_id=txn.ledger_txn_id,
                account_id=debit_account,
                debit=collection.amount,
                currency=collection.currency,
                counterparty_id=collection.customer_id,
                memo=economic_event,
            ),
            LedgerEntry(
                ledger_txn_id=txn.ledger_txn_id,
                account_id=credit_account,
                credit=collection.amount,
                currency=collection.currency,
                counterparty_id=collection.customer_id,
                memo=economic_event,
            ),
        ]
        self._assert_balanced(txn)
        self.ledger.add_transaction(txn)
        return txn

    @staticmethod
    def _assert_balanced(txn: LedgerTransaction) -> None:
        debit = sum((e.debit for e in txn.entries), Decimal("0.00"))
        credit = sum((e.credit for e in txn.entries), Decimal("0.00"))
        if debit != credit:
            raise ValueError(f"unbalanced commercial posting: {debit} != {credit}")
