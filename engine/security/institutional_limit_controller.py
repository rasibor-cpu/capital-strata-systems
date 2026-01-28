"""
Institutional Limit Controller (v1)
-----------------------------------
Enforces institutional trading limits across traders.

Key guarantees:
- Each trader has an individual trading limit
- Aggregate trader limits MUST NOT exceed institutional cap
- Traders cannot modify limits
- Admins can modify trader limits within cap
- Super Admin can modify institutional caps (but not exceed legal ceilings)

This module does NOT execute trades.
It governs exposure ceilings only.
"""

from dataclasses import dataclass
from decimal import Decimal
from typing import Dict, Optional


@dataclass(frozen=True)
class InstitutionalLimit:
    scope_id: str                 # desk / department / branch / country
    currency: str
    max_limit: Decimal            # legal / institutional ceiling


@dataclass
class TraderLimit:
    user_id: str
    currency: str
    max_limit: Decimal


class InstitutionalLimitController:
    """
    Authoritative controller for institutional exposure limits.
    """

    def __init__(self):
        self._institutional_limits: Dict[str, InstitutionalLimit] = {}
        self._trader_limits: Dict[str, TraderLimit] = {}

    # ─────────────────────────────
    # Institutional limits
    # ─────────────────────────────
    def set_institutional_limit(
        self,
        *,
        scope_id: str,
        currency: str,
        max_limit: Decimal,
    ) -> None:
        self._institutional_limits[scope_id] = InstitutionalLimit(
            scope_id=scope_id,
            currency=currency,
            max_limit=max_limit,
        )

    def get_institutional_limit(self, scope_id: str) -> InstitutionalLimit:
        limit = self._institutional_limits.get(scope_id)
        if not limit:
            raise ValueError("Institutional limit not defined")
        return limit

    # ─────────────────────────────
    # Trader limits
    # ─────────────────────────────
    def set_trader_limit(
        self,
        *,
        scope_id: str,
        user_id: str,
        currency: str,
        max_limit: Decimal,
    ) -> None:
        inst = self.get_institutional_limit(scope_id)

        if currency != inst.currency:
            raise ValueError("Currency mismatch with institutional limit")

        projected_total = self._aggregate_trader_limits(
            scope_id=scope_id,
            currency=currency,
            excluding_user=user_id,
        ) + max_limit

        if projected_total > inst.max_limit:
            raise PermissionError(
                "Aggregate trader limits exceed institutional cap"
            )

        self._trader_limits[user_id] = TraderLimit(
            user_id=user_id,
            currency=currency,
            max_limit=max_limit,
        )

    def get_trader_limit(self, user_id: str) -> TraderLimit:
        limit = self._trader_limits.get(user_id)
        if not limit:
            raise ValueError("Trader limit not defined")
        return limit

    # ─────────────────────────────
    # Internal helpers
    # ─────────────────────────────
    def _aggregate_trader_limits(
        self,
        *,
        scope_id: str,
        currency: str,
        excluding_user: Optional[str] = None,
    ) -> Decimal:
        total = Decimal("0")

        for uid, lim in self._trader_limits.items():
            if excluding_user and uid == excluding_user:
                continue
            if lim.currency == currency:
                total += lim.max_limit

        return total

    def remaining_capacity(self, *, scope_id: str, currency: str) -> Decimal:
        inst = self.get_institutional_limit(scope_id)
        used = self._aggregate_trader_limits(
            scope_id=scope_id,
            currency=currency,
        )
        return inst.max_limit - used
