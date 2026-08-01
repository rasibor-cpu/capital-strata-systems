"""DIP-003 WP-2 — Trade DNA capture from canonical close events."""

from __future__ import annotations

import hashlib
import logging
from datetime import datetime
from typing import Any, Mapping, Optional

from backend.intelligence.trade_dna.close_event import (
    CanonicalCloseEvent,
    CanonicalCloseEventError,
    build_canonical_close_event_from_trade_record,
    deserialize_canonical_close_event,
    validate_canonical_close_event,
)
from backend.intelligence.trade_dna.constants import (
    ANALYSIS_VERSION,
    EVIDENCE_VERSION,
    FIELD_OBSERVED_UNKNOWN,
    FIELD_UNAVAILABLE,
    OUTBOX_COMPLETE,
    OUTBOX_CONFLICT,
    OUTBOX_DNA_COMMITTED,
    OUTBOX_PENDING_DNA,
    SCHEMA_VERSION,
)
from backend.intelligence.trade_dna.derived import DerivedTradeMetrics
from backend.intelligence.trade_dna.durable_store import DurableCaptureStore
from backend.intelligence.trade_dna.evidence_graph import EvidenceGraphNode, build_evidence_graph
from backend.intelligence.trade_dna.schema import (
    BrokerFacts,
    EvidenceCustodyFacts,
    ExecutionFacts,
    GovernanceFacts,
    MarketFacts,
    MetadataFacts,
    OutcomeFacts,
    RevisionFacts,
    StrategyFacts,
    TimingFacts,
    TradeDNARecord,
    TradeIdentityFacts,
)
from backend.intelligence.trade_dna.validation import TradeDNAValidationError


logger = logging.getLogger(__name__)


def deterministic_closed_dna_id(trade_id: str) -> str:
    digest = hashlib.sha256(
        f"{SCHEMA_VERSION}|closed|{trade_id}".encode("utf-8")
    ).hexdigest()[:24]
    return f"dna-{digest}"


def _holding_seconds(opened_at: str, closed_at: str) -> Optional[float]:
    try:
        opened = datetime.fromisoformat(opened_at.replace("Z", "+00:00"))
        closed = datetime.fromisoformat(closed_at.replace("Z", "+00:00"))
        return (closed - opened).total_seconds()
    except Exception:
        return None


def _context_or_none(value: Optional[str]) -> Optional[str]:
    """Preserve OBSERVED_UNKNOWN; never promote bare UNKNOWN placeholders."""
    if value is None:
        return None
    text = str(value).strip()
    upper = text.upper()
    if not text or upper in {"UNKNOWN", FIELD_UNAVAILABLE}:
        return None
    if upper == FIELD_OBSERVED_UNKNOWN:
        return FIELD_OBSERVED_UNKNOWN
    return text


def project_trade_dna_from_close_event(event: CanonicalCloseEvent) -> TradeDNARecord:
    """Deterministic projection: same close event + schema → identical DNA + hash."""
    validated = validate_canonical_close_event(event)
    dna_id = deterministic_closed_dna_id(validated.trade_id)

    executed_at = validated.executed_at or validated.opened_at
    try:
        opened_dt = datetime.fromisoformat(validated.opened_at.replace("Z", "+00:00"))
        executed_dt = datetime.fromisoformat(str(executed_at).replace("Z", "+00:00"))
        if executed_dt < opened_dt:
            executed_at = validated.opened_at
    except Exception:
        executed_at = validated.opened_at

    record = TradeDNARecord(
        identity=TradeIdentityFacts(
            trade_id=validated.trade_id,
            dna_id=dna_id,
            session_id=validated.session_id,
            instrument=validated.symbol,
            asset_class=_context_or_none(validated.asset_class),
            side=validated.side,
        ),
        schema_version=SCHEMA_VERSION,
        execution=ExecutionFacts(
            order_type=validated.order_type,
            fill_kind=validated.fill_kind,
            entry_price=validated.entry_price,
            exit_price=validated.exit_price,
            requested_quantity=validated.quantity,
            filled_quantity=validated.filled_quantity,
            requested_notional=validated.requested_notional,
            scaled_notional=validated.scaled_notional,
            fees=validated.fees,
            quantity_contract=validated.quantity_contract,
            notional_contract=validated.notional_contract,
            execution_result="CLOSED",
        ),
        market=MarketFacts(
            symbol=validated.symbol,
            market_regime=_context_or_none(validated.market_regime),
        ),
        strategy=StrategyFacts(strategy_id=_context_or_none(validated.strategy_id)),
        governance=GovernanceFacts(
            gate_final=validated.gate_final,
            gate_reason=validated.gate_reason,
        ),
        broker=BrokerFacts(
            broker_name=validated.broker_name,
            broker_mode=validated.broker_mode,
            practice=(str(validated.broker_mode).lower() == "paper"),
        ),
        timing=TimingFacts(
            opened_at=validated.opened_at,
            closed_at=validated.closed_at,
            executed_at=executed_at,
        ),
        outcome=OutcomeFacts(
            status="closed",
            exit_reason=_context_or_none(validated.exit_reason),
            win_loss=None,
            partial=False,
        ),
        evidence_custody=EvidenceCustodyFacts(
            evidence_version=EVIDENCE_VERSION,
            source_event_ids=tuple(validated.source_event_ids) + (validated.event_id,),
            source_artifact_uris=(f"canonical_close_event:{validated.event_id}",),
            writer="dip003_trade_dna_capture",
            captured_at=validated.closed_at,
        ),
        revision=RevisionFacts(
            revision=1,
            created_at=validated.closed_at,
        ),
        metadata=MetadataFacts(
            provenance={
                "close_event_id": validated.event_id,
                "close_event_version": validated.event_version,
                "close_event_hash": validated.content_hash,
            },
            extensions={},
        ),
    )
    return record.with_content_hash()


def project_derived_from_close_event(
    event: CanonicalCloseEvent,
    dna: TradeDNARecord,
) -> DerivedTradeMetrics:
    """Layer-2 metrics from authoritative close PnL + timing (not embedded in facts)."""
    holding = _holding_seconds(event.opened_at, event.closed_at)
    notional = event.scaled_notional or event.requested_notional
    return_pct = None
    if notional and float(notional) != 0:
        return_pct = float(event.realized_pnl) / float(notional)
    return DerivedTradeMetrics(
        dna_id=dna.identity.dna_id,
        trade_id=event.trade_id,
        analysis_version=ANALYSIS_VERSION,
        profit=float(event.realized_pnl),
        return_pct=return_pct,
        holding_period_seconds=holding,
        expectancy_contribution=float(event.realized_pnl),
        extensions={"close_event_id": event.event_id},
    )


def build_capture_evidence(event: CanonicalCloseEvent, dna: TradeDNARecord) -> EvidenceGraphNode:
    return build_evidence_graph(
        trade_ids=[event.trade_id],
        dna_ids=[dna.identity.dna_id],
        evidence_version=EVIDENCE_VERSION,
        analysis_version=ANALYSIS_VERSION,
        sample_size=1,
        confidence=1.0,
        generated_at=event.closed_at,
        notes=f"capture:{event.event_id}",
    )


def build_conflict_evidence(
    *,
    trade_id: str,
    code: str,
    existing_hash: Optional[str],
    candidate_hash: Optional[str],
    detail: Optional[str] = None,
) -> dict[str, Any]:
    return {
        "trade_id": trade_id,
        "code": code,
        "existing_hash": existing_hash,
        "candidate_hash": candidate_hash,
        "detail": detail,
        "layer": "intelligence_capture",
        "execution_allowed": False,
        "recommendations": False,
    }


class TradeDNACaptureService:
    """Idempotent, deterministic Trade DNA capture with durable outbox reconciliation."""

    def __init__(self, store: DurableCaptureStore) -> None:
        self.store = store

    def _apply_dna_for_event(self, sealed_event: CanonicalCloseEvent) -> dict[str, Any]:
        candidate = project_trade_dna_from_close_event(sealed_event)
        existing = self.store.head_dna_for_trade(sealed_event.trade_id)
        if existing is not None and str(existing.outcome.status).lower() == "closed":
            if existing.content_hash == candidate.content_hash:
                derived = self.store.get_derived(existing.identity.dna_id)
                if derived is None:
                    derived = self.store.commit_derived(
                        project_derived_from_close_event(sealed_event, existing)
                    )
                self.store.mark_outbox_complete(sealed_event.trade_id)
                evidence = build_capture_evidence(sealed_event, existing)
                return {
                    "status": "idempotent_hit",
                    "close_event": sealed_event.to_dict(),
                    "dna": existing.to_dict(),
                    "derived": derived.to_dict() if derived else None,
                    "evidence": evidence.to_dict(),
                }
            evidence = build_conflict_evidence(
                trade_id=sealed_event.trade_id,
                code="duplicate_close_dna_conflict",
                existing_hash=existing.content_hash,
                candidate_hash=candidate.content_hash,
            )
            self.store.mark_outbox_conflict(sealed_event.trade_id, evidence)
            raise TradeDNAValidationError("duplicate_close_dna_conflict", sealed_event.trade_id)

        sealed_close = self.store.commit_close_event(sealed_event)
        committed = self.store.commit_dna(candidate)
        self.store.mark_outbox_dna_committed(sealed_event.trade_id)
        derived = self.store.commit_derived(
            project_derived_from_close_event(sealed_close, committed)
        )
        self.store.mark_outbox_complete(sealed_event.trade_id)
        evidence = build_capture_evidence(sealed_close, committed)
        return {
            "status": "captured",
            "close_event": sealed_close.to_dict(),
            "dna": committed.to_dict(),
            "derived": derived.to_dict(),
            "evidence": evidence.to_dict(),
        }

    def capture_close_event(self, event: CanonicalCloseEvent) -> dict[str, Any]:
        validated = validate_canonical_close_event(event)
        # Durable marker BEFORE DNA write — survives crash without relying on logs.
        outbox = self.store.enqueue_pending_capture(validated)
        if outbox.get("status") == OUTBOX_CONFLICT:
            raise CanonicalCloseEventError("duplicate_close_event_conflict", validated.trade_id)
        if outbox.get("status") == OUTBOX_COMPLETE:
            head = self.store.head_dna_for_trade(validated.trade_id)
            if head is not None:
                derived = self.store.get_derived(head.identity.dna_id)
                return {
                    "status": "idempotent_hit",
                    "close_event": validated.to_dict(),
                    "dna": head.to_dict(),
                    "derived": derived.to_dict() if derived else None,
                    "evidence": build_capture_evidence(validated, head).to_dict(),
                }
        return self._apply_dna_for_event(validated)

    def capture_from_trade_record(
        self,
        trade_record: Mapping[str, Any],
        *,
        exit_price: Any,
        realized_pnl: Any,
        closed_at: str,
    ) -> dict[str, Any]:
        event = build_canonical_close_event_from_trade_record(
            trade_record,
            exit_price=exit_price,
            realized_pnl=realized_pnl,
            closed_at=closed_at,
        )
        return self.capture_close_event(event)

    def recover_pending_captures(self) -> list[dict[str, Any]]:
        """Idempotent recovery from durable outbox and sealed close events without DNA."""
        results: list[dict[str, Any]] = []

        # Promote sealed close events lacking DNA into outbox (store-level reconcile).
        for trade_id, event in list(self.store._close_by_trade.items()):
            head = self.store.head_dna_for_trade(trade_id)
            if head is not None and str(head.outcome.status).lower() == "closed":
                outbox = self.store.get_outbox(trade_id)
                derived = self.store.get_derived(head.identity.dna_id)
                if (
                    outbox
                    and outbox.get("status") in {OUTBOX_PENDING_DNA, OUTBOX_DNA_COMMITTED}
                    and derived is not None
                ):
                    self.store.mark_outbox_complete(trade_id)
                continue
            if self.store.get_outbox(trade_id) is None:
                try:
                    self.store.enqueue_pending_capture(event)
                except CanonicalCloseEventError:
                    continue

        for item in self.store.list_pending_outbox():
            trade_id = str(item.get("trade_id") or "")
            status = item.get("status")
            raw_event = item.get("close_event")
            if not isinstance(raw_event, Mapping):
                evidence = build_conflict_evidence(
                    trade_id=trade_id,
                    code="outbox_missing_close_event",
                    existing_hash=None,
                    candidate_hash=None,
                )
                self.store.mark_outbox_conflict(trade_id, evidence)
                results.append({"trade_id": trade_id, "status": "conflict", "evidence": evidence})
                continue

            event = deserialize_canonical_close_event(raw_event)
            head = self.store.head_dna_for_trade(trade_id)
            if status == OUTBOX_DNA_COMMITTED and head is not None:
                derived = self.store.get_derived(head.identity.dna_id)
                if derived is None:
                    derived = self.store.commit_derived(project_derived_from_close_event(event, head))
                self.store.mark_outbox_complete(trade_id)
                results.append(
                    {
                        "trade_id": trade_id,
                        "status": "recovered_complete",
                        "dna_id": head.identity.dna_id,
                        "derived": derived.to_dict(),
                    }
                )
                continue

            try:
                captured = self._apply_dna_for_event(event)
                results.append(
                    {
                        "trade_id": trade_id,
                        "status": captured["status"],
                        "dna_id": captured["dna"]["identity"]["dna_id"],
                    }
                )
            except (CanonicalCloseEventError, TradeDNAValidationError) as exc:
                evidence = build_conflict_evidence(
                    trade_id=trade_id,
                    code=getattr(exc, "code", type(exc).__name__),
                    existing_hash=None,
                    candidate_hash=None,
                    detail=str(exc),
                )
                current = self.store.get_outbox(trade_id)
                if trade_id and current is not None and current.get("status") != OUTBOX_CONFLICT:
                    self.store.mark_outbox_conflict(trade_id, evidence)
                results.append({"trade_id": trade_id, "status": "conflict", "evidence": evidence})
        return results

    def recover_missing_dna(self) -> list[str]:
        """Compatibility wrapper — recovers pending outbox entries."""
        return [str(r.get("trade_id")) for r in self.recover_pending_captures() if r.get("trade_id")]


def default_capture_root() -> str:
    return str((__import__("pathlib").Path("artifacts") / "trade_dna_capture").resolve())


def capture_completed_trade(
    trade_record: Mapping[str, Any],
    *,
    exit_price: Any,
    realized_pnl: Any,
    closed_at: str,
    store_root: Optional[str] = None,
) -> Optional[dict[str, Any]]:
    """Best-effort capture used by persistence layer.

    Writes durable outbox before DNA. Operational close must not depend on success.
    """
    store = DurableCaptureStore(store_root or default_capture_root())
    service = TradeDNACaptureService(store)
    try:
        event = build_canonical_close_event_from_trade_record(
            trade_record,
            exit_price=exit_price,
            realized_pnl=realized_pnl,
            closed_at=closed_at,
        )
    except (CanonicalCloseEventError, TradeDNAValidationError, Exception) as exc:
        logger.error("dip003_close_event_build_failed: %s", exc)
        return None

    try:
        # Outbox first — even if DNA write fails next, restart can discover the gap.
        service.store.enqueue_pending_capture(event)
    except CanonicalCloseEventError as exc:
        logger.error("dip003_outbox_conflict: %s", exc)
        return {"status": "conflict", "error": str(exc)}
    except Exception as exc:
        logger.exception("dip003_outbox_persist_failed: %s", exc)
        return None

    try:
        return service.capture_close_event(event)
    except (CanonicalCloseEventError, TradeDNAValidationError) as exc:
        logger.error("dip003_capture_rejected: %s", exc)
        return {"status": "rejected", "error": str(exc)}
    except Exception as exc:
        logger.exception("dip003_capture_failed: %s", exc)
        # Outbox remains PENDING_DNA for recovery.
        return {"status": "pending_recovery", "trade_id": event.trade_id, "error": str(exc)}
