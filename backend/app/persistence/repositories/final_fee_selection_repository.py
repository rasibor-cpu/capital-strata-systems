from __future__ import annotations

import json
from decimal import Decimal
from typing import Any

from backend.app.persistence.repositories.base_repository import BaseRepository
from backend.commercialization.final_fee_selection import (
    CommercialFinalFeeSelection, build_final_fee_selection,
)
from backend.commercialization.platform_access_fee_terms import (
    CommercialPlatformAccessFeeTerms, PlatformAccessBillingFrequency,
)
from backend.commercialization.performance_compensation import PerformanceCompensationTerms
from backend.commercialization.performance_crystallization import (
    CrystallizationAssessment, CrystallizationStatus,
)
from backend.commercialization.fx_conversion import CommercialFxConversionEvidence


class FinalFeeSelectionRepository(BaseRepository):
    """Append-only documentary evidence; duplicate IDs never overwrite history."""

    def create_selection(self, record: CommercialFinalFeeSelection) -> None:
        if not isinstance(record, CommercialFinalFeeSelection):
            raise TypeError("record must be CommercialFinalFeeSelection")
        self._validate_persisted_inputs(record)
        self.execute(
            """
            INSERT INTO commercial_final_fee_selections (
                fee_selection_id, access_terms_id, terms_id, policy_id, billing_currency, period_start, period_end, platform_access_fee_amount, performance_fee_source_currency, performance_fee_source_amount, performance_fee_billing_currency_amount, selected_fee_amount, selected_fee_basis, selected_at, evidence_refs_json, fx_conversion_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                record.fee_selection_id,
                record.access_terms_id,
                record.terms_id,
                record.policy_id,
                record.billing_currency,
                record.period_start,
                record.period_end,
                str(record.platform_access_fee_amount),
                record.performance_fee_source_currency,
                str(record.performance_fee_source_amount),
                str(record.performance_fee_billing_currency_amount),
                str(record.selected_fee_amount),
                record.selected_fee_basis.value,
                record.selected_at,
                json.dumps(list(record.evidence_refs), separators=(",", ":")),
                record.fx_conversion_id,
            ),
        )

    def get_by_fee_selection_id(self, fee_selection_id: str) -> dict[str, Any] | None:
        row = self.fetch_one(
            "SELECT * FROM commercial_final_fee_selections WHERE fee_selection_id = ?",
            (fee_selection_id,),
        )
        return dict(row) if row is not None else None

    def list_all(self) -> list[dict[str, Any]]:
        return [dict(row) for row in self.fetch_all(
            "SELECT * FROM commercial_final_fee_selections ORDER BY created_at, fee_selection_id"
        )]

    def _validate_persisted_inputs(self, record: CommercialFinalFeeSelection) -> None:
        """Fail closed on stale IDs or snapshots that differ from stored evidence."""
        def required(sql, params):
            row = self.fetch_one(sql, params)
            if row is None:
                raise ValueError("missing persisted fee selection input")
            return dict(row)

        access = required("SELECT * FROM platform_access_fee_terms WHERE access_terms_id = ?",
                          (record.access_terms_id,))
        terms = required("SELECT * FROM performance_compensation_terms WHERE terms_id = ?",
                         (record.terms_id,))
        assessment = required(
            "SELECT * FROM crystallization_assessments WHERE policy_id = ? AND period_start = ? AND period_end = ?",
            (record.policy_id, record.period_start, record.period_end),
        )
        access_record = CommercialPlatformAccessFeeTerms(
            access_terms_id=access["access_terms_id"], billing_currency=access["billing_currency"],
            access_fee_amount=Decimal(access["access_fee_amount"]),
            billing_frequency=PlatformAccessBillingFrequency(access["billing_frequency"]),
            effective_from=access["effective_from"], effective_to=access["effective_to"],
            accepted=bool(access["accepted"]), evidence_refs=tuple(json.loads(access["evidence_refs_json"])),
        )
        terms_record = PerformanceCompensationTerms(
            terms_id=terms["terms_id"], currency=terms["currency"],
            performance_compensation_rate=Decimal(terms["performance_compensation_rate"]),
            effective_from=terms["effective_from"], effective_to=terms["effective_to"],
            accepted=bool(terms["accepted"]), evidence_refs=tuple(json.loads(terms["evidence_refs_json"])),
        )
        assessment_record = CrystallizationAssessment(
            policy_id=assessment["policy_id"], terms_id=assessment["terms_id"], currency=assessment["currency"],
            period_start=assessment["period_start"], period_end=assessment["period_end"],
            assessed_at=assessment["assessed_at"],
            shadow_entitlement_total=Decimal(assessment["shadow_entitlement_total"]),
            crystallizable_amount=Decimal(assessment["crystallizable_amount"]),
            status=CrystallizationStatus(assessment["status"]),
            evidence_refs=tuple(json.loads(assessment["evidence_refs_json"])),
        )
        fx_record = None
        if record.fx_conversion_id is not None:
            fx = required("SELECT * FROM commercial_fx_conversion_evidence WHERE fx_conversion_id = ?",
                          (record.fx_conversion_id,))
            fx_record = CommercialFxConversionEvidence(
                fx_conversion_id=fx["fx_conversion_id"], source_currency=fx["source_currency"],
                target_currency=fx["target_currency"], source_amount=Decimal(fx["source_amount"]),
                converted_amount=Decimal(fx["converted_amount"]), fx_rate=Decimal(fx["fx_rate"]),
                rate_effective_at=fx["rate_effective_at"], rate_source_reference=fx["rate_source_reference"],
                evidence_refs=tuple(json.loads(fx["evidence_refs_json"])),
            )
        expected = build_final_fee_selection(
            access_record, terms_record, assessment_record,
            fee_selection_id=record.fee_selection_id, period_start=record.period_start,
            period_end=record.period_end, selected_at=record.selected_at,
            evidence_refs=record.evidence_refs, fx_conversion=fx_record,
        )
        if expected != record:
            raise ValueError("fee selection snapshot differs from persisted inputs")
