from __future__ import annotations

from decimal import Decimal
from typing import Any

from fastapi import APIRouter, HTTPException, Query

from backend.app.persistence.services.client_earnings_summary_service import (
    ClientEarningsSummaryService,
)
from backend.commercialization.client_earnings_summary import (
    ClientEarningsSummaryUnavailableError,
    CommercialClientEarningsSummary,
)


def _decimal_or_none(value: Decimal | None) -> str | None:
    return str(value) if value is not None else None


def build_client_earnings_summary_payload(
    summary: CommercialClientEarningsSummary,
) -> dict[str, Any]:
    """Read-only JSON projection. No invoice/receivable/ledger authority implied."""

    return {
        "account_reference": summary.account_reference,
        "policy_id": summary.policy_id,
        "terms_id": summary.terms_id,
        "billing_period_start": summary.billing_period_start,
        "billing_period_end": summary.billing_period_end,
        "performance_currency": summary.performance_currency,
        "billing_currency": summary.billing_currency,
        "commercial_status": summary.commercial_status.value,
        "is_billable_period": summary.is_billable_period,
        "realized_attributable_profit": str(summary.realized_attributable_profit),
        "recovered_loss": str(summary.recovered_loss),
        "new_economic_gain": str(summary.new_economic_gain),
        "performance_fee_rate": _decimal_or_none(summary.performance_fee_rate),
        "performance_fee_source_amount": _decimal_or_none(summary.performance_fee_source_amount),
        "performance_fee_billing_currency_amount": _decimal_or_none(
            summary.performance_fee_billing_currency_amount,
        ),
        "platform_access_fee_amount": _decimal_or_none(summary.platform_access_fee_amount),
        "access_terms_id": summary.access_terms_id,
        "selected_fee_basis": summary.selected_fee_basis.value if summary.selected_fee_basis else None,
        "selected_fee_amount": _decimal_or_none(summary.selected_fee_amount),
        "final_fee_selection_id": summary.final_fee_selection_id,
        "net_earnings_after_css_fee": _decimal_or_none(summary.net_earnings_after_css_fee),
        "fx_rate": _decimal_or_none(summary.fx_rate),
        "fx_conversion_id": summary.fx_conversion_id,
        "fx_rate_source_reference": summary.fx_rate_source_reference,
        "invoice_id": summary.invoice_id,
        "receivable_id": summary.receivable_id,
        "evidence_refs": list(summary.evidence_refs),
        "fee_rule_language": summary.fee_rule_language,
        "fx_language": summary.fx_language,
        "withdrawable_funds_note": summary.withdrawable_funds_note,
        "explanation": summary.explain(),
    }


def create_client_earnings_router(
    service_factory: type[ClientEarningsSummaryService] | None = None,
) -> APIRouter:
    """Narrowest read-only router for the client earnings/charge explainability projection.

    Grants no invoice, receivable, ledger, tax, or money-movement authority.
    """

    router = APIRouter()
    factory = service_factory or ClientEarningsSummaryService

    @router.get("/api/v1/client-earnings-summary")
    def read_client_earnings_summary(
        policy_id: str = Query(...),
        period_start: str = Query(...),
        period_end: str = Query(...),
    ) -> dict[str, Any]:
        try:
            summary = factory().build_summary(policy_id, period_start, period_end)
        except ClientEarningsSummaryUnavailableError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return build_client_earnings_summary_payload(summary)

    return router
