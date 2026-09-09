from __future__ import annotations

import json
from decimal import Decimal
from typing import Optional

from backend.app.persistence.services.persistence_service import PersistenceService
from backend.commercialization.client_earnings_summary import (
    CommercialClientEarningsSummary,
    ClientEarningsSummaryUnavailableError,
    _exact_product,
)
from backend.commercialization.final_fee_selection import FinalFeeBasis
from backend.commercialization.performance_crystallization import CrystallizationStatus


class ClientEarningsSummaryService:
    """Read-only composition of ``CommercialClientEarningsSummary``.

    Every value is projected from already-persisted canonical
    commercialization records (crystallization assessments, final fee
    selections, invoice/receivable chain). No new writable table is
    introduced and no migration is required: this is a pure projection.

    This service performs no writes, no invoicing, no receivable
    recognition, no ledger posting, and no money movement. It fails
    closed when the canonical commercial period cannot be located.
    """

    def __init__(self, persistence_service: Optional[PersistenceService] = None) -> None:
        self._service = persistence_service or PersistenceService()

    def build_summary(
        self,
        policy_id: str,
        period_start: str,
        period_end: str,
    ) -> CommercialClientEarningsSummary:
        service = self._service

        assessment = service.crystallization_assessments.get_by_period(
            policy_id, period_start, period_end,
        )
        if assessment is None:
            raise ClientEarningsSummaryUnavailableError(
                "no canonical crystallization assessment exists for this commercial period"
            )

        terms_id = assessment["terms_id"]
        performance_currency = assessment["currency"]
        status = CrystallizationStatus(assessment["status"])
        evidence_refs = list(json.loads(assessment["evidence_refs_json"]))

        billing_profiles = service.billing_profiles.get_by_terms_id(terms_id)
        if not billing_profiles:
            raise ClientEarningsSummaryUnavailableError(
                "no canonical billing profile exists for this commercial terms"
            )
        account_reference = billing_profiles[0]["bill_to_reference"]

        realized_profit = Decimal("0")
        recovered_loss = Decimal("0")
        new_economic_gain = Decimal("0")
        for entitlement in service.shadow_compensation_entitlements.get_by_terms_id(terms_id):
            timestamp = entitlement["calculation_timestamp"]
            if not (period_start <= timestamp < period_end):
                continue
            transition = service.performance_accounting_transitions.get_by_trade_id(
                entitlement["trade_id"],
            )
            if transition is None:
                raise ClientEarningsSummaryUnavailableError(
                    "shadow entitlement references a missing accounting transition"
                )
            realized_profit += Decimal(transition["attributable_realized_pnl"])
            recovered_loss += Decimal(transition["recovered_loss"])
            new_economic_gain += Decimal(transition["new_economic_gain"])

        if status != CrystallizationStatus.ELIGIBLE:
            return CommercialClientEarningsSummary(
                account_reference=account_reference,
                policy_id=policy_id,
                terms_id=terms_id,
                billing_period_start=period_start,
                billing_period_end=period_end,
                performance_currency=performance_currency,
                billing_currency=performance_currency,
                commercial_status=status,
                realized_attributable_profit=realized_profit,
                recovered_loss=recovered_loss,
                new_economic_gain=new_economic_gain,
                performance_fee_rate=None,
                performance_fee_source_amount=None,
                performance_fee_billing_currency_amount=None,
                platform_access_fee_amount=None,
                access_terms_id=None,
                selected_fee_basis=None,
                selected_fee_amount=None,
                final_fee_selection_id=None,
                net_earnings_after_css_fee=None,
                fx_rate=None,
                fx_conversion_id=None,
                fx_rate_source_reference=None,
                invoice_id=None,
                receivable_id=None,
                evidence_refs=tuple(evidence_refs),
            )

        readiness = service.settlement_readiness.get_by_period(policy_id, period_start, period_end)
        if readiness is None or readiness.get("final_fee_selection_id") is None:
            raise ClientEarningsSummaryUnavailableError(
                "eligible commercial period has no final fee selection readiness recorded"
            )
        selection = service.final_fee_selections.get_by_fee_selection_id(
            readiness["final_fee_selection_id"],
        )
        if selection is None:
            raise ClientEarningsSummaryUnavailableError(
                "readiness references a missing final fee selection"
            )

        terms = service.performance_compensation_terms.get_by_terms_id(terms_id)
        if terms is None:
            raise ClientEarningsSummaryUnavailableError(
                "no canonical performance compensation terms exist for this commercial terms"
            )

        billing_currency = selection["billing_currency"]
        performance_fee_source_amount = Decimal(selection["performance_fee_source_amount"])
        performance_fee_billing_currency_amount = Decimal(
            selection["performance_fee_billing_currency_amount"],
        )
        platform_access_fee_amount = Decimal(selection["platform_access_fee_amount"])
        selected_fee_amount = Decimal(selection["selected_fee_amount"])
        selected_fee_basis = FinalFeeBasis(selection["selected_fee_basis"])

        fx_conversion_id = selection["fx_conversion_id"]
        fx_rate = None
        fx_rate_source_reference = None
        if fx_conversion_id is not None:
            conversion = service.fx_conversion_evidence.get_by_fx_conversion_id(fx_conversion_id)
            if conversion is None:
                raise ClientEarningsSummaryUnavailableError(
                    "final fee selection references missing FX conversion evidence"
                )
            fx_rate = Decimal(conversion["fx_rate"])
            fx_rate_source_reference = conversion["rate_source_reference"]

        normalized_realized_profit = (
            realized_profit if performance_currency == billing_currency
            else _exact_product(realized_profit, fx_rate)
        )
        net_earnings_after_css_fee = normalized_realized_profit - selected_fee_amount

        invoice_id = None
        receivable_id = None
        for issued in service.invoice_issued_records.get_by_terms_id(terms_id):
            if (issued["policy_id"], issued["period_start"], issued["period_end"]) == (
                policy_id, period_start, period_end,
            ):
                invoice_id = issued["invoice_id"]
                recognition = service.receivable_recognitions.get_by_invoice_id(invoice_id)
                if recognition is not None:
                    receivable_id = recognition["receivable_id"]
                break

        evidence_refs = list(dict.fromkeys(evidence_refs + list(json.loads(selection["evidence_refs_json"]))))

        return CommercialClientEarningsSummary(
            account_reference=account_reference,
            policy_id=policy_id,
            terms_id=terms_id,
            billing_period_start=period_start,
            billing_period_end=period_end,
            performance_currency=performance_currency,
            billing_currency=billing_currency,
            commercial_status=status,
            realized_attributable_profit=realized_profit,
            recovered_loss=recovered_loss,
            new_economic_gain=new_economic_gain,
            performance_fee_rate=Decimal(terms["performance_compensation_rate"]),
            performance_fee_source_amount=performance_fee_source_amount,
            performance_fee_billing_currency_amount=performance_fee_billing_currency_amount,
            platform_access_fee_amount=platform_access_fee_amount,
            access_terms_id=selection["access_terms_id"],
            selected_fee_basis=selected_fee_basis,
            selected_fee_amount=selected_fee_amount,
            final_fee_selection_id=selection["fee_selection_id"],
            net_earnings_after_css_fee=net_earnings_after_css_fee,
            fx_rate=fx_rate,
            fx_conversion_id=fx_conversion_id,
            fx_rate_source_reference=fx_rate_source_reference,
            invoice_id=invoice_id,
            receivable_id=receivable_id,
            evidence_refs=tuple(evidence_refs),
        )
