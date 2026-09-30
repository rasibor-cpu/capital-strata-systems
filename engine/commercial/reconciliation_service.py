"""Fail-closed commercial reconciliation and exception queue."""
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Dict, Optional
import uuid

from engine.domain.collections import CollectionStatus, CollectionTransaction


class ReconciliationState(str, Enum):
    MATCHED = "MATCHED"
    EXCEPTION = "EXCEPTION"


@dataclass(frozen=True)
class SettlementEvidence:
    collection_id: str
    provider_reference: str
    settlement_reference: str
    amount: Decimal
    currency: str


@dataclass
class ReconciliationException:
    collection_id: str
    reason: str
    expected: str
    observed: str
    exception_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: datetime = field(default_factory=datetime.utcnow)
    resolved_at: Optional[datetime] = None
    resolution_reference: Optional[str] = None
    resolved_by: Optional[str] = None


class ReconciliationService:
    def __init__(self, repository=None):
        self.repository = repository
        self.exceptions: Dict[str, ReconciliationException] = {}
        if repository is not None:
            for item in repository.list_all():
                self.exceptions[self._key(item.collection_id, item.reason, item.expected, item.observed)] = item

    def reconcile(self, collection: CollectionTransaction, evidence: SettlementEvidence) -> ReconciliationState:
        checks = [
            ("collection_id", collection.collection_id, evidence.collection_id),
            ("provider_reference", collection.provider_reference or "", evidence.provider_reference),
            ("settlement_reference", collection.settlement_reference or "", evidence.settlement_reference),
            ("amount", str(collection.amount), str(evidence.amount)),
            ("currency", collection.currency, evidence.currency),
        ]
        if collection.status != CollectionStatus.SETTLED or not collection.ledger_txn_id:
            self._raise(collection, "state", "SETTLED with posted ledger transaction", collection.status.value)
            return ReconciliationState.EXCEPTION
        mismatches = [(name, expected, observed) for name, expected, observed in checks if expected != observed]
        if mismatches:
            name, expected, observed = mismatches[0]
            self._raise(collection, name, expected, observed)
            return ReconciliationState.EXCEPTION
        return ReconciliationState.MATCHED

    def apply_approved_resolution(self, action) -> ReconciliationException:
        """Resolve an exception -- only by executing an approved maker-checker action.

        This is the single way to resolve a reconciliation exception. It is
        called by ``engine.commercial.commercial_controls``'s
        ``RESOLVE_RECONCILIATION_EXCEPTION`` executor after ``CommercialControls``
        has enforced RBAC, maker != checker, payload-hash binding and
        compare-and-set approval. The former public, unchecked
        ``resolve_exception(exception_id, resolved_by=..., ...)`` let any caller
        resolve an exception under any name with no second approver; it has
        been removed rather than kept as an undocumented privileged bypass.
        """
        if getattr(action, "action_type", None) != "RESOLVE_RECONCILIATION_EXCEPTION":
            raise PermissionError("not a reconciliation-resolution controlled action")
        if getattr(action, "status", None) != "APPROVED":
            raise PermissionError("reconciliation exceptions are resolved only by an approved controlled action")
        maker_id, checker_id = getattr(action, "maker_id", None), getattr(action, "checker_id", None)
        if not maker_id or not checker_id or maker_id == checker_id:
            raise PermissionError("resolution requires a distinct maker and checker")
        payload = getattr(action, "payload", None) or {}
        return self._resolve(
            payload.get("exception_id"),
            resolved_by=checker_id,
            resolution_reference=payload.get("resolution_reference"),
        )

    def _resolve(self, exception_id: str, *, resolved_by: str, resolution_reference: str) -> ReconciliationException:
        if not resolved_by or not resolution_reference:
            raise ValueError("resolver and resolution reference required")
        matches = [item for item in self.exceptions.values() if item.exception_id == exception_id]
        if not matches:
            raise KeyError(exception_id)
        item = matches[0]
        if item.resolved_at is not None:
            if item.resolved_by != resolved_by or item.resolution_reference != resolution_reference:
                raise ValueError("resolved exception is immutable")
            return item
        item.resolved_at = datetime.utcnow()
        item.resolved_by = resolved_by
        item.resolution_reference = resolution_reference
        if self.repository is not None:
            self.repository.save(
                item,
                exception_key=self._key(item.collection_id, item.reason, item.expected, item.observed),
            )
        return item

    def open_exceptions(self):
        return [item for item in self.exceptions.values() if item.resolved_at is None]

    @staticmethod
    def _key(collection_id, reason, expected, observed):
        return f"{collection_id}:{reason}:{expected}:{observed}"

    def _raise(self, collection, reason, expected, observed):
        key = self._key(collection.collection_id, reason, expected, observed)
        if key not in self.exceptions:
            item = ReconciliationException(
                collection_id=collection.collection_id, reason=reason,
                expected=str(expected), observed=str(observed),
            )
            self.exceptions[key] = item
            if self.repository is not None:
                self.repository.save(item, exception_key=key)
