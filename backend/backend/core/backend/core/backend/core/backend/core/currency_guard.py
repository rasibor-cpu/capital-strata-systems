"""
REA Capital Trading Engine
Currency Consistency Guard

Ensures approval is only possible when currencies are explicitly verified.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class CurrencyContext:
    ticket_currency: str
    debit_currency: str
    credit_currency: str


def currencies_match(ctx: CurrencyContext) -> bool:
    """
    Returns True if all currencies in the posting context match.
    """
    return (
        ctx.ticket_currency == ctx.debit_currency
        and ctx.ticket_currency == ctx.credit_currency
    )
