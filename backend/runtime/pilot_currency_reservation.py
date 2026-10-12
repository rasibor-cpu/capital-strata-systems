"""Non-executing cross-currency pilot reservation adapter.

Requires source-currency metadata and fresh, independently verified FX inputs.
No broker access, order submission, runtime arming or FX rate sourcing.
A reservation is only a preflight capacity claim, not a trade authorization.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from backend.runtime.pilot_currency_conversion import (
    CURRENT_PILOT_BUDGET, PilotCurrencyError, PilotRiskBudget,
    VerifiedRateInput, convert_risk_up,
)
from backend.runtime.pilot_exposure_reservation import (
    PilotExposureReservationLedger, PilotReservationDecision,
)


@dataclass(frozen=True)
class CurrencyReservationResult:
    decision: PilotReservationDecision | None
    reason: str
    risk_amount_budget_currency: Decimal | None


def reserve_converted_pilot_exposure(
    ledger: PilotExposureReservationLedger,
    *,
    parent_id: str,
    child_id: str,
    source_currency: str,
    gross_notional: object,
    cash_commitment: object,
    maximum_loss: object,
    fees: object,
    risk_bounded: bool,
    instrument_verified: bool,
    rate_provenance_verified: bool,
    rate: VerifiedRateInput | None = None,
    now: datetime | None = None,
    budget: PilotRiskBudget = CURRENT_PILOT_BUDGET,
) -> CurrencyReservationResult:
    """Reserve highest of independently supplied notional, cash and max loss.

    No current ledger supports a generic budget denomination. Until refactored,
    non-CAD budgets are explicitly rejected rather than silently assumed CAD.
    The ledger's single reserved amount includes fees once, never twice.
    """
    denied = CurrencyReservationResult(None, "CURRENCY_RESERVATION_NOT_CERTIFIED", None)
    try:
        if type(ledger) is not PilotExposureReservationLedger:
            return denied
        if type(budget) is not PilotRiskBudget or budget != CURRENT_PILOT_BUDGET:
            return denied
        if risk_bounded is not True or instrument_verified is not True or rate_provenance_verified is not True:
            return denied
        amounts = [
            convert_risk_up(v, source_currency=source_currency, budget=budget, rate=rate, now=now)
            for v in (gross_notional, cash_commitment, maximum_loss, fees)
        ]
        # Round each risk measure upward separately; add fees once.
        exposure = max(amounts[:3]) + amounts[3]
        if exposure <= Decimal("0"):
            return denied
        result = ledger.reserve(
            parent_id=parent_id,
            child_id=child_id,
            proposed_child_cad=exposure,
            estimated_fees_cad=Decimal("0.00"),
        )
        return CurrencyReservationResult(result, result.reason, exposure)
    except (PilotCurrencyError, ValueError, TypeError, ArithmeticError):
        return denied
