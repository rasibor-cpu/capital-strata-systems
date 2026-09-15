from __future__ import annotations

import json
from decimal import Decimal
from typing import Optional

from backend.app.persistence.services.persistence_service import PersistenceService
from backend.commercialization.advice_profitability import (
    AdviceProfitability,
    AdviceProfitabilityError,
    build_advice_profitability,
)
from backend.commercialization.performance_accounting import (
    PerformanceAccountState,
    PerformanceAccountingTransition,
)
from backend.commercialization.performance_attribution import (
    AttributablePerformance,
)


class AdviceProfitabilityHistoryService:
    """Read-only reconstruction of advice-level profitability history."""

    def __init__(self, persistence_service: Optional[PersistenceService] = None) -> None:
        self._service = persistence_service or PersistenceService()

    def list_by_terms_id(self, terms_id: str) -> list[AdviceProfitability]:
        service = self._service
        terms = service.performance_compensation_terms.get_by_terms_id(terms_id)
        if terms is None:
            raise AdviceProfitabilityError("no canonical compensation terms found")

        rate = Decimal(terms["performance_compensation_rate"])
        items: list[AdviceProfitability] = []

        for entitlement in service.shadow_compensation_entitlements.get_by_terms_id(terms_id):
            trade_id = entitlement["trade_id"]
            performance_row = service.attributable_performance.get_by_trade_id(trade_id)
            transition_row = service.performance_accounting_transitions.get_by_trade_id(trade_id)
            if performance_row is None or transition_row is None:
                raise AdviceProfitabilityError(
                    "canonical advice profitability chain is incomplete"
                )

            performance = AttributablePerformance(
                trade_id=performance_row["trade_id"],
                advice_id=performance_row["advice_id"],
                realized_pnl=Decimal(performance_row["realized_pnl"]),
                currency=performance_row["currency"],
                verification_timestamp=performance_row["verification_timestamp"],
                provenance_evidence_refs=tuple(
                    json.loads(performance_row["provenance_evidence_refs_json"])
                ),
                economics_evidence_refs=tuple(
                    json.loads(performance_row["economics_evidence_refs_json"])
                ),
            )

            previous_state = PerformanceAccountState(
                currency=transition_row["currency"],
                cumulative_attributable_pnl=Decimal(
                    transition_row["previous_cumulative_attributable_pnl"]
                ),
                high_water_mark=Decimal(transition_row["previous_high_water_mark"]),
                loss_carryforward=Decimal(
                    transition_row["previous_loss_carryforward"]
                ),
            )
            new_state = PerformanceAccountState(
                currency=transition_row["currency"],
                cumulative_attributable_pnl=Decimal(
                    transition_row["new_cumulative_attributable_pnl"]
                ),
                high_water_mark=Decimal(transition_row["new_high_water_mark"]),
                loss_carryforward=Decimal(
                    transition_row["new_loss_carryforward"]
                ),
            )
            transition = PerformanceAccountingTransition(
                trade_id=trade_id,
                previous_state=previous_state,
                new_state=new_state,
                attributable_realized_pnl=Decimal(
                    transition_row["attributable_realized_pnl"]
                ),
                recovered_loss=Decimal(transition_row["recovered_loss"]),
                new_economic_gain=Decimal(transition_row["new_economic_gain"]),
            )

            item = build_advice_profitability(
                performance,
                transition,
                performance_fee_rate=rate,
            )

            if item.css_shadow_fee != Decimal(
                entitlement["shadow_compensation_amount"]
            ):
                raise AdviceProfitabilityError(
                    "advice-level fee does not reconcile to canonical entitlement"
                )

            items.append(item)

        return items
