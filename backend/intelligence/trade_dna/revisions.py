"""DIP-002 append-only Trade DNA revision chain (in-memory foundation).

Does not capture live executions. Provides immutable revision semantics only.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

from backend.intelligence.trade_dna.schema import RevisionFacts, TradeDNARecord
from backend.intelligence.trade_dna.validation import TradeDNAValidationError, validate_trade_dna


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


class AppendOnlyDNAStore:
    """Append-only store of validated Trade DNA fact records.

    Historical dna_id values are never mutated or removed.
    """

    def __init__(self) -> None:
        self._records: dict[str, TradeDNARecord] = {}
        self._by_trade: dict[str, list[str]] = {}

    def get(self, dna_id: str) -> Optional[TradeDNARecord]:
        return self._records.get(dna_id)

    def list_for_trade(self, trade_id: str) -> list[TradeDNARecord]:
        ids = self._by_trade.get(trade_id, [])
        return [self._records[i] for i in ids if i in self._records]

    def head_for_trade(self, trade_id: str) -> Optional[TradeDNARecord]:
        chain = self.list_for_trade(trade_id)
        return chain[-1] if chain else None

    def commit(self, record: TradeDNARecord) -> TradeDNARecord:
        """Commit a hashed, validated DNA record. Never overwrites an existing dna_id."""
        hashed = record if record.content_hash else record.with_content_hash()
        validated = validate_trade_dna(hashed, require_hash=True)
        if validated.identity.dna_id in self._records:
            raise TradeDNAValidationError("dna_id_already_committed", validated.identity.dna_id)

        if validated.revision.supersedes_dna_id:
            prior = self._records.get(validated.revision.supersedes_dna_id)
            if prior is None:
                raise TradeDNAValidationError(
                    "supersedes_unknown",
                    validated.revision.supersedes_dna_id,
                )
            if prior.identity.trade_id != validated.identity.trade_id:
                raise TradeDNAValidationError(
                    "supersedes_trade_mismatch",
                    f"{prior.identity.trade_id}!={validated.identity.trade_id}",
                )
            if validated.revision.revision != prior.revision.revision + 1:
                raise TradeDNAValidationError(
                    "revision_sequence_gap",
                    f"expected_{prior.revision.revision + 1}",
                )

        self._records[validated.identity.dna_id] = validated
        self._by_trade.setdefault(validated.identity.trade_id, []).append(validated.identity.dna_id)
        return validated

    def supersede(
        self,
        prior_dna_id: str,
        updated: TradeDNARecord,
        *,
        reason: str,
        created_at: Optional[str] = None,
    ) -> TradeDNARecord:
        """Create a new revision that supersedes a prior immutable record."""
        prior = self._records.get(prior_dna_id)
        if prior is None:
            raise TradeDNAValidationError("supersedes_unknown", prior_dna_id)

        new_identity = replace(
            updated.identity,
            trade_id=prior.identity.trade_id,
            dna_id=f"dna-{uuid4().hex}",
        )
        new_revision = RevisionFacts(
            revision=prior.revision.revision + 1,
            supersedes_dna_id=prior.identity.dna_id,
            supersede_reason=reason,
            created_at=created_at or _utc_now_iso(),
        )
        candidate = TradeDNARecord(
            identity=new_identity,
            schema_version=updated.schema_version,
            execution=updated.execution,
            market=updated.market,
            strategy=updated.strategy,
            risk=updated.risk,
            governance=updated.governance,
            liquidity=updated.liquidity,
            volatility=updated.volatility,
            indicators=updated.indicators,
            broker=updated.broker,
            timing=updated.timing,
            outcome=updated.outcome,
            evidence_custody=updated.evidence_custody,
            revision=new_revision,
            metadata=updated.metadata,
            content_hash="",
        ).with_content_hash()
        return self.commit(candidate)
