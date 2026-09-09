from __future__ import annotations

import json
from dataclasses import fields
from decimal import Decimal
from typing import Any

from backend.app.persistence.repositories.base_repository import (
    BaseRepository,
)
from backend.commercialization.final_fee_settlement_readiness import (
    CommercialFinalFeeSettlementReadiness,
)
from backend.commercialization.settlement_readiness import (
    CommercialSettlementReadiness,
)


class SettlementReadinessRepository(BaseRepository):
    """
    Persistence boundary for immutable COM-002F commercial
    settlement-readiness decisions.

    Deliberately exposes no update or delete method.

    One authoritative readiness decision exists per crystallized
    commercial period. Duplicate insertion for the same policy_id +
    period_start + period_end fails at the composite primary-key
    constraint rather than rewriting readiness history.
    """

    def create_readiness(
        self,
        readiness: CommercialSettlementReadiness | CommercialFinalFeeSettlementReadiness,
    ) -> None:
        if not isinstance(readiness, (CommercialSettlementReadiness, CommercialFinalFeeSettlementReadiness)):
            raise TypeError("readiness must be a canonical readiness record")
        # Support legacy migration-010 consumers while using the neutral column
        # after 027. Final-fee readiness always requires migration 027.
        columns = {row["name"] for row in self.fetch_all(
            "PRAGMA table_info(commercial_settlement_readiness)"
        )}
        amount_column = "economic_amount" if "economic_amount" in columns else "crystallizable_amount"
        final_id = None
        if isinstance(readiness, CommercialFinalFeeSettlementReadiness):
            if "final_fee_selection_id" not in columns:
                raise ValueError("final-fee readiness requires migration 027")
            final_id = readiness.final_fee_selection_id
            source = self.fetch_one(
                "SELECT * FROM commercial_final_fee_selections WHERE fee_selection_id = ?",
                (final_id,),
            )
            if source is None:
                raise ValueError("final fee selection is not persisted")
            for name, source_name in (("policy_id", "policy_id"), ("terms_id", "terms_id"),
                                      ("currency", "billing_currency"),
                                      ("period_start", "period_start"), ("period_end", "period_end")):
                if getattr(readiness, name) != source[source_name]:
                    raise ValueError(f"readiness {name} mismatches final selection")
            amount = readiness.selected_fee_amount
            if amount != Decimal(source["selected_fee_amount"]):
                raise ValueError("readiness amount mismatches final selection")
            for field in fields(readiness.selection):
                value = getattr(readiness.selection, field.name)
                if field.name == "evidence_refs":
                    stored = tuple(json.loads(source["evidence_refs_json"]))
                elif isinstance(value, Decimal):
                    stored = Decimal(source[field.name])
                else:
                    stored = source[field.name]
                if value != stored:
                    raise ValueError(f"selection {field.name} mismatches persisted source")
        else:
            amount = readiness.crystallizable_amount
        names = ["policy_id", "terms_id", "currency", "period_start", "period_end",
                 amount_column, "assessed_at", "status", "evidence_refs_json"]
        values = [readiness.policy_id, readiness.terms_id, readiness.currency,
                  readiness.period_start, readiness.period_end, str(amount),
                  readiness.assessed_at, readiness.status.value,
                  json.dumps(list(readiness.evidence_refs), separators=(",", ":"))]
        if "final_fee_selection_id" in columns:
            names.append("final_fee_selection_id")
            values.append(final_id)
        # SQL identifiers above are fixed repository names, never caller input.
        self.execute(
            "INSERT INTO commercial_settlement_readiness (" + ", ".join(names)
            + ") VALUES (" + ", ".join("?" for _ in values) + ")",
            tuple(values),
        )

    @staticmethod
    def _read_record(row) -> dict[str, Any]:
        record = dict(row)
        if "economic_amount" in record:
            if record.get("final_fee_selection_id") is None:
                # Preserve the legacy repository read contract without assigning
                # crystallization semantics to a final-fee source.
                record["crystallizable_amount"] = record.pop("economic_amount")
                record.pop("final_fee_selection_id", None)
            else:
                record["selected_fee_amount"] = record.pop("economic_amount")
        return record

    def get_by_period(
        self,
        policy_id: str,
        period_start: str,
        period_end: str,
    ) -> dict[str, Any] | None:
        row = self.fetch_one(
            """
            SELECT *
            FROM commercial_settlement_readiness
            WHERE policy_id = ?
              AND period_start = ?
              AND period_end = ?
            """,
            (policy_id, period_start, period_end),
        )

        if row is None:
            return None

        return self._read_record(row)

    def get_by_policy_id(
        self,
        policy_id: str,
    ) -> list[dict[str, Any]]:
        rows = self.fetch_all(
            """
            SELECT *
            FROM commercial_settlement_readiness
            WHERE policy_id = ?
            ORDER BY period_start ASC, period_end ASC,
                     created_at ASC
            """,
            (policy_id,),
        )

        return [self._read_record(row) for row in rows]

    def get_by_terms_id(
        self,
        terms_id: str,
    ) -> list[dict[str, Any]]:
        rows = self.fetch_all(
            """
            SELECT *
            FROM commercial_settlement_readiness
            WHERE terms_id = ?
            ORDER BY policy_id ASC, period_start ASC,
                     period_end ASC, created_at ASC
            """,
            (terms_id,),
        )

        return [self._read_record(row) for row in rows]

    def list_all(
        self,
    ) -> list[dict[str, Any]]:
        rows = self.fetch_all(
            """
            SELECT *
            FROM commercial_settlement_readiness
            ORDER BY policy_id ASC, period_start ASC,
                     period_end ASC, created_at ASC
            """
        )

        return [self._read_record(row) for row in rows]
