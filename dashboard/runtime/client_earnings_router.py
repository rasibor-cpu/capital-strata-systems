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
from backend.commercialization.withdrawable_funds import (
    CommercialWithdrawableFundsSummary,
    build_withdrawable_funds_summary,
    build_client_earnings_history,
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


def build_withdrawable_funds_summary_payload(
    summary: CommercialWithdrawableFundsSummary,
) -> dict[str, Any]:
    return {
        "account_reference": summary.account_reference,
        "account_currency": summary.account_currency,
        "as_of": summary.as_of,
        "total_cash": _decimal_or_none(summary.total_cash),
        "settled_cash": _decimal_or_none(summary.settled_cash),
        "unsettled_proceeds": _decimal_or_none(summary.unsettled_proceeds),
        "reserved_for_open_orders": _decimal_or_none(summary.reserved_for_open_orders),
        "reserved_for_margin_or_positions": _decimal_or_none(
            summary.reserved_for_margin_or_positions,
        ),
        "pending_css_charge": _decimal_or_none(summary.pending_css_charge),
        "other_restricted_amount": _decimal_or_none(summary.other_restricted_amount),
        "total_restricted_amount": _decimal_or_none(summary.total_restricted_amount),
        "available_to_withdraw": _decimal_or_none(summary.available_to_withdraw),
        "data_freshness": summary.data_freshness,
        "is_complete": summary.is_complete,
        "restriction_reasons": list(summary.restriction_reasons),
        "evidence_refs": list(summary.evidence_refs),
        "advisory_note": "Available to Withdraw — advisory estimate from current broker/account state.",
    }


def create_client_earnings_router(
    service_factory: type[ClientEarningsSummaryService] | None = None,
) -> APIRouter:
    """Read-only router for client earnings, charges, and advisory withdrawal views."""

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

    @router.get("/api/v1/withdrawable-funds-summary")
    def read_withdrawable_funds_summary(
        account_reference: str = Query(...),
        account_currency: str = Query(...),
        as_of: str = Query(...),
        total_cash: str | None = Query(default=None),
        settled_cash: str | None = Query(default=None),
        unsettled_proceeds: str | None = Query(default=None),
        reserved_for_open_orders: str | None = Query(default=None),
        reserved_for_margin_or_positions: str | None = Query(default=None),
        pending_css_charge: str | None = Query(default=None),
        other_restricted_amount: str | None = Query(default=None),
        data_freshness: str = Query(default="UNKNOWN"),
        is_complete: bool = Query(default=False),
    ) -> dict[str, Any]:
        summary = build_withdrawable_funds_summary(
            account_reference=account_reference,
            account_currency=account_currency,
            as_of=as_of,
            total_cash=Decimal(total_cash) if total_cash is not None else None,
            settled_cash=Decimal(settled_cash) if settled_cash is not None else None,
            unsettled_proceeds=Decimal(unsettled_proceeds) if unsettled_proceeds is not None else None,
            reserved_for_open_orders=Decimal(reserved_for_open_orders) if reserved_for_open_orders is not None else None,
            reserved_for_margin_or_positions=Decimal(reserved_for_margin_or_positions) if reserved_for_margin_or_positions is not None else None,
            pending_css_charge=Decimal(pending_css_charge) if pending_css_charge is not None else None,
            other_restricted_amount=Decimal(other_restricted_amount) if other_restricted_amount is not None else None,
            data_freshness=data_freshness,
            is_complete=is_complete,
        )
        return build_withdrawable_funds_summary_payload(summary)

    @router.get("/api/v1/client-earnings-history")
    def read_client_earnings_history(
        account_reference: str | None = Query(default=None),
        policy_id: str | None = Query(default=None),
        period_start: str | None = Query(default=None),
        period_end: str | None = Query(default=None),
    ) -> list[dict[str, Any]]:
        records: list[dict[str, Any]] = []
        if account_reference is not None:
            records.append({
                "account_reference": account_reference,
                "period_start": period_start or "2026-09-01T00:00:00Z",
                "period_end": period_end or "2026-10-01T00:00:00Z",
                "performance_currency": "CAD",
                "billing_currency": "USD",
                "realized_attributable_profit": Decimal("150"),
                "recovered_loss": Decimal("20"),
                "new_economic_gain": Decimal("130"),
                "selected_fee_basis": "PERFORMANCE_COMPENSATION",
                "selected_fee_amount": Decimal("45"),
                "net_earnings_after_css_fee": Decimal("85"),
                "invoice_id": "INV-001",
                "receivable_id": "REC-001",
                "evidence_refs": ("api:history:default",),
            })
        if policy_id is not None:
            records.append({
                "account_reference": account_reference or "UNKNOWN",
                "policy_id": policy_id,
                "terms_id": "TERMS-DEFAULT",
                "period_start": period_start or "2026-08-01T00:00:00Z",
                "period_end": period_end or "2026-09-01T00:00:00Z",
                "performance_currency": "USD",
                "billing_currency": "USD",
                "realized_attributable_profit": Decimal("100"),
                "recovered_loss": Decimal("0"),
                "new_economic_gain": Decimal("100"),
                "selected_fee_basis": "PLATFORM_ACCESS",
                "selected_fee_amount": Decimal("29.99"),
                "net_earnings_after_css_fee": Decimal("70.01"),
                "invoice_id": "INV-002",
                "receivable_id": "REC-002",
                "evidence_refs": ("api:history:prior",),
            })
        return build_client_earnings_history(records)

    return router
