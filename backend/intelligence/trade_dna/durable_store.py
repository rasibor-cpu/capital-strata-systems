"""DIP-003 durable append-only stores: close events, DNA, derived, capture outbox."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Mapping, Optional

from backend.intelligence.trade_dna.close_event import (
    CanonicalCloseEvent,
    CanonicalCloseEventError,
    deserialize_canonical_close_event,
    validate_canonical_close_event,
)
from backend.intelligence.trade_dna.constants import (
    OUTBOX_COMPLETE,
    OUTBOX_CONFLICT,
    OUTBOX_DNA_COMMITTED,
    OUTBOX_PENDING_DNA,
)
from backend.intelligence.trade_dna.derived import DerivedTradeMetrics
from backend.intelligence.trade_dna.revisions import AppendOnlyDNAStore
from backend.intelligence.trade_dna.schema import TradeDNARecord
from backend.intelligence.trade_dna.serialization import deserialize_trade_dna, serialize_trade_dna
from backend.intelligence.trade_dna.validation import TradeDNAValidationError


def _atomic_write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    text = json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    with open(tmp, "w", encoding="utf-8") as handle:
        handle.write(text)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(tmp, path)


def _read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return json.load(handle)
    except Exception:
        return default


class DurableCaptureStore:
    """Crash-safe durable store for close events, DNA, derived metrics, and outbox."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)
        self.close_path = self.root / "canonical_close_events.json"
        self.dna_path = self.root / "trade_dna_records.json"
        self.derived_path = self.root / "derived_metrics.json"
        self.outbox_path = self.root / "capture_outbox.json"
        self.conflict_path = self.root / "capture_conflicts.json"
        self.dna_store = AppendOnlyDNAStore()
        self._close_by_trade: dict[str, CanonicalCloseEvent] = {}
        self._derived_by_dna: dict[str, DerivedTradeMetrics] = {}
        self._outbox_by_trade: dict[str, dict[str, Any]] = {}
        self._conflicts: list[dict[str, Any]] = []
        self._load()

    def _load(self) -> None:
        close_payload = _read_json(self.close_path, [])
        if isinstance(close_payload, list):
            for item in close_payload:
                if isinstance(item, Mapping):
                    event = deserialize_canonical_close_event(item)
                    self._close_by_trade[event.trade_id] = event

        dna_payload = _read_json(self.dna_path, [])
        if isinstance(dna_payload, list):
            for item in dna_payload:
                if isinstance(item, Mapping):
                    record = deserialize_trade_dna(item, validate=True)
                    self.dna_store._records[record.identity.dna_id] = record
                    self.dna_store._by_trade.setdefault(record.identity.trade_id, [])
                    if record.identity.dna_id not in self.dna_store._by_trade[record.identity.trade_id]:
                        self.dna_store._by_trade[record.identity.trade_id].append(record.identity.dna_id)

        derived_payload = _read_json(self.derived_path, [])
        if isinstance(derived_payload, list):
            for item in derived_payload:
                if isinstance(item, Mapping) and item.get("dna_id"):
                    metrics = DerivedTradeMetrics(
                        dna_id=str(item["dna_id"]),
                        trade_id=str(item.get("trade_id") or ""),
                        analysis_version=str(item.get("analysis_version") or ""),
                        profit=item.get("profit"),
                        return_pct=item.get("return_pct"),
                        holding_period_seconds=item.get("holding_period_seconds"),
                        mae=item.get("mae"),
                        mfe=item.get("mfe"),
                        expectancy_contribution=item.get("expectancy_contribution"),
                        edge_contribution=item.get("edge_contribution"),
                        capital_efficiency=item.get("capital_efficiency"),
                        execution_quality=item.get("execution_quality"),
                        sharpe_contribution=item.get("sharpe_contribution"),
                        drawdown_contribution=item.get("drawdown_contribution"),
                        extensions=dict(item.get("extensions") or {}),
                    )
                    self._derived_by_dna[metrics.dna_id] = metrics

        outbox_payload = _read_json(self.outbox_path, [])
        if isinstance(outbox_payload, list):
            for item in outbox_payload:
                if isinstance(item, Mapping) and item.get("trade_id"):
                    self._outbox_by_trade[str(item["trade_id"])] = dict(item)

        conflicts = _read_json(self.conflict_path, [])
        if isinstance(conflicts, list):
            self._conflicts = [dict(c) for c in conflicts if isinstance(c, Mapping)]

    def _persist_close(self) -> None:
        ordered = [self._close_by_trade[k].to_dict() for k in sorted(self._close_by_trade)]
        _atomic_write_json(self.close_path, ordered)

    def _persist_dna(self) -> None:
        records = [serialize_trade_dna(r) for r in self.dna_store._records.values()]
        payload = [json.loads(text) for text in records]
        payload.sort(key=lambda row: row.get("identity", {}).get("dna_id", ""))
        _atomic_write_json(self.dna_path, payload)

    def _persist_derived(self) -> None:
        ordered = [self._derived_by_dna[k].to_dict() for k in sorted(self._derived_by_dna)]
        _atomic_write_json(self.derived_path, ordered)

    def _persist_outbox(self) -> None:
        ordered = [self._outbox_by_trade[k] for k in sorted(self._outbox_by_trade)]
        _atomic_write_json(self.outbox_path, ordered)

    def _persist_conflicts(self) -> None:
        ordered = sorted(self._conflicts, key=lambda c: str(c.get("trade_id") or ""))
        _atomic_write_json(self.conflict_path, ordered)

    def get_close_event(self, trade_id: str) -> Optional[CanonicalCloseEvent]:
        return self._close_by_trade.get(trade_id)

    def commit_close_event(self, event: CanonicalCloseEvent) -> CanonicalCloseEvent:
        validated = validate_canonical_close_event(event)
        existing = self._close_by_trade.get(validated.trade_id)
        if existing is not None:
            if existing.content_hash == validated.content_hash and existing.event_id == validated.event_id:
                return existing
            raise CanonicalCloseEventError("duplicate_close_event_conflict", validated.trade_id)
        self._close_by_trade[validated.trade_id] = validated
        self._persist_close()
        return validated

    def commit_dna(self, record: TradeDNARecord) -> TradeDNARecord:
        committed = self.dna_store.commit(record)
        self._persist_dna()
        return committed

    def get_dna(self, dna_id: str) -> Optional[TradeDNARecord]:
        return self.dna_store.get(dna_id)

    def head_dna_for_trade(self, trade_id: str) -> Optional[TradeDNARecord]:
        return self.dna_store.head_for_trade(trade_id)

    def list_dna(self) -> list[TradeDNARecord]:
        return list(self.dna_store._records.values())

    def commit_derived(self, metrics: DerivedTradeMetrics) -> DerivedTradeMetrics:
        existing = self._derived_by_dna.get(metrics.dna_id)
        if existing is not None:
            if existing.to_dict() == metrics.to_dict():
                return existing
            raise TradeDNAValidationError("derived_conflict", metrics.dna_id)
        self._derived_by_dna[metrics.dna_id] = metrics
        self._persist_derived()
        return metrics

    def get_derived(self, dna_id: str) -> Optional[DerivedTradeMetrics]:
        return self._derived_by_dna.get(dna_id)

    def list_derived(self) -> list[DerivedTradeMetrics]:
        return list(self._derived_by_dna.values())

    def get_outbox(self, trade_id: str) -> Optional[dict[str, Any]]:
        item = self._outbox_by_trade.get(trade_id)
        return dict(item) if item else None

    def list_pending_outbox(self) -> list[dict[str, Any]]:
        return [
            dict(v)
            for k, v in sorted(self._outbox_by_trade.items())
            if v.get("status") in {OUTBOX_PENDING_DNA, OUTBOX_DNA_COMMITTED}
        ]

    def enqueue_pending_capture(self, event: CanonicalCloseEvent) -> dict[str, Any]:
        """Durably record that warehouse close requires DNA (before DNA write)."""
        validated = validate_canonical_close_event(event)
        existing = self._outbox_by_trade.get(validated.trade_id)
        payload = {
            "trade_id": validated.trade_id,
            "status": OUTBOX_PENDING_DNA,
            "close_event_id": validated.event_id,
            "close_event_hash": validated.content_hash,
            "close_event": validated.to_dict(),
            "warehouse_trade_id": validated.trade_id,
        }
        if existing is not None:
            if (
                existing.get("close_event_hash") == validated.content_hash
                and existing.get("close_event_id") == validated.event_id
            ):
                # Already enqueued for same sealed event — keep status unless complete/conflict.
                if existing.get("status") == OUTBOX_COMPLETE:
                    return dict(existing)
                if existing.get("status") == OUTBOX_CONFLICT:
                    return dict(existing)
                return dict(existing)
            # Conflicting outbox intent — fail closed with durable conflict marker.
            evidence = {
                "trade_id": validated.trade_id,
                "code": "outbox_close_event_conflict",
                "existing_hash": existing.get("close_event_hash"),
                "incoming_hash": validated.content_hash,
                "existing_event_id": existing.get("close_event_id"),
                "incoming_event_id": validated.event_id,
            }
            self.record_conflict(evidence)
            self._outbox_by_trade[validated.trade_id] = {
                **existing,
                "status": OUTBOX_CONFLICT,
                "conflict_evidence": evidence,
            }
            self._persist_outbox()
            raise CanonicalCloseEventError("duplicate_close_event_conflict", validated.trade_id)

        self._outbox_by_trade[validated.trade_id] = payload
        self._persist_outbox()
        return dict(payload)

    def mark_outbox_dna_committed(self, trade_id: str) -> None:
        item = self._outbox_by_trade.get(trade_id)
        if item is None:
            return
        if item.get("status") == OUTBOX_CONFLICT:
            return
        item["status"] = OUTBOX_DNA_COMMITTED
        self._outbox_by_trade[trade_id] = item
        self._persist_outbox()

    def mark_outbox_complete(self, trade_id: str) -> None:
        item = self._outbox_by_trade.get(trade_id)
        if item is None:
            return
        if item.get("status") == OUTBOX_CONFLICT:
            return
        item["status"] = OUTBOX_COMPLETE
        self._outbox_by_trade[trade_id] = item
        self._persist_outbox()

    def mark_outbox_conflict(self, trade_id: str, evidence: Mapping[str, Any]) -> None:
        item = self._outbox_by_trade.get(trade_id) or {
            "trade_id": trade_id,
            "close_event": None,
        }
        payload = dict(evidence)
        payload.setdefault("trade_id", trade_id)
        item["status"] = OUTBOX_CONFLICT
        item["conflict_evidence"] = dict(payload)
        self._outbox_by_trade[trade_id] = item
        self._persist_outbox()
        self.record_conflict(payload)

    def record_conflict(self, evidence: Mapping[str, Any]) -> None:
        self._conflicts.append(dict(evidence))
        self._persist_conflicts()

    def list_conflicts(self) -> list[dict[str, Any]]:
        return list(self._conflicts)
