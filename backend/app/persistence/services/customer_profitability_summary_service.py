from __future__ import annotations

import json
from decimal import Decimal
from typing import Optional

from backend.app.persistence.services.client_earnings_summary_service import (
    ClientEarningsSummaryService,
)
from backend.app.persistence.services.persistence_service import PersistenceService
from backend.commercialization.customer_profitability import (
    CustomerProfitabilitySummary,
    build_customer_profitability_summary,
)
from backend.commercialization.independent_trade_economics import (
    IndependentTradeChargeBasis,
    IndependentTradeEconomics,
)
from backend.commercialization.trade_provenance import AttributionClass


class CustomerProfitabilitySummaryService:
    """Read-only account-period profitability composition from canonical state."""

    def __init__(self, persistence_service: Optional[PersistenceService] = None) -> None:
        self._service = persistence_service or PersistenceService()
        self._css = ClientEarningsSummaryService(self._service)

    def build_summary(
        self,
        *,
        policy_id: str,
        period_start: str,
        period_end: str,
    ) -> CustomerProfitabilitySummary:
        css_summary = self._css.build_summary(policy_id, period_start, period_end)

        independent = []
        for row in self._service.independent_trade_economics.list_for_account_period(
            account_reference=css_summary.account_reference,
            period_start=period_start,
            period_end=period_end,
        ):
            independent.append(
                IndependentTradeEconomics(
                    trade_id=row["trade_id"],
                    account_reference=row["account_reference"],
                    calculation_timestamp=row["calculation_timestamp"],
                    attribution_class=AttributionClass(row["attribution_class"]),
                    realized_pnl=Decimal(row["realized_pnl"]),
                    currency=row["currency"],
                    platform_charge_rate=Decimal(row["platform_charge_rate"]),
                    platform_charge_amount=Decimal(row["platform_charge_amount"]),
                    charge_basis=IndependentTradeChargeBasis(row["charge_basis"]),
                    evidence_refs=tuple(json.loads(row["evidence_refs_json"])),
                )
            )

        return build_customer_profitability_summary(
            css_summary,
            tuple(independent),
        )
