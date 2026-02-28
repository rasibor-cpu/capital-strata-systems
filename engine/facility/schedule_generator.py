"""
Capital Strata Systems
Phase 22B – Amortization Schedule Generator (Reducing Balance)

Supports:
- Reducing balance loans
- Monthly repayment schedule
- Equal installment (EMI) computation
- Interest/principal split per period
- Balance tracking

This module does NOT post entries.
It only generates deterministic schedules.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from typing import List


def _d(val) -> Decimal:
    return Decimal(str(val))


@dataclass(frozen=True)
class ScheduleRow:
    installment_no: int
    due_date: str
    principal_component: Decimal
    interest_component: Decimal
    total_payment: Decimal
    balance_after: Decimal


def _monthly_rate(annual_rate: Decimal) -> Decimal:
    return annual_rate / Decimal("12")


def _emi(principal: Decimal, annual_rate: Decimal, months: int) -> Decimal:
    """
    EMI = P * r * (1+r)^n / ((1+r)^n - 1)
    """
    r = _monthly_rate(annual_rate)
    if r == 0:
        return principal / months

    numerator = principal * r * (1 + r) ** months
    denominator = ((1 + r) ** months) - 1
    return (numerator / denominator).quantize(Decimal("0.01"), ROUND_HALF_UP)


def _add_months(start_date: datetime, months: int) -> datetime:
    month = start_date.month - 1 + months
    year = start_date.year + month // 12
    month = month % 12 + 1
    day = min(start_date.day, 28)  # avoid month-end overflow
    return datetime(year, month, day)


def generate_schedule(
    principal: Decimal,
    annual_rate_percent: Decimal,
    tenor_months: int,
    start_date: str,
) -> List[ScheduleRow]:

    principal = _d(principal)
    annual_rate = _d(annual_rate_percent) / Decimal("100")

    start_dt = datetime.strptime(start_date, "%Y-%m-%d")

    emi = _emi(principal, annual_rate, tenor_months)

    balance = principal
    schedule: List[ScheduleRow] = []

    for i in range(1, tenor_months + 1):

        r = _monthly_rate(annual_rate)

        interest = (balance * r).quantize(Decimal("0.01"), ROUND_HALF_UP)
        principal_component = (emi - interest).quantize(Decimal("0.01"), ROUND_HALF_UP)

        # final adjustment
        if i == tenor_months:
            principal_component = balance
            emi = principal_component + interest

        balance = (balance - principal_component).quantize(Decimal("0.01"), ROUND_HALF_UP)

        due_date = _add_months(start_dt, i).strftime("%Y-%m-%d")

        schedule.append(
            ScheduleRow(
                installment_no=i,
                due_date=due_date,
                principal_component=principal_component,
                interest_component=interest,
                total_payment=emi,
                balance_after=balance,
            )
        )

    return schedule