"""
Trade Exposure Tracker (v1)
---------------------------
Tracks exposure utilization per trader and per institutional scope.

Purpose:
- Measure how much of a trader's limit is currently utilized
- Measure aggregate utilization across all traders vs institutional cap
- Provide pre-trade checks to prevent inadvertent erosion of limits

Inputs (v1):
- "Exposure" is approximated from activity ledger actions:
    BUY / SELL or EXECUTE_TRADE events with amount+currency
- This is a control layer, not an accounting layer

Later upgrades:
- Pull true positions from ledger + mark-to-market
- Net/gross exposure, delta-adjusted exposure
- FX-normalized exposure to home currency
"""

from dataclasses import dataclass
from decimal import Decimal
from typing import Dict, Optional

from engine.security.user_activity_ledger import UserActivityLedger
from engine.security.institutional_limit_controller import InstitutionalLimitController


@dataclass(frozen=True)
class ExposureSnapshot:
    scope_id: str
    currency: str
    trader_used: Decimal
    trader_limit: Decimal
    trader_remaining: Decimal

    aggregate_used: Decimal
    institutional_cap: Decimal
    institutional_remaining: Decimal


class TradeExposureTracker:
    """
    Exposure tracker that can be used in pre-trade checks.

    Note: v1 uses activity-derived exposure approximation.
    """

    def __init__(
        self,
        *,
        activity_ledger: UserActivityLedger,
        limits: InstitutionalLimitController,
    ):
        self.ledger = activity_ledger
        self.limits = limits

    def _approx_used_exposure(
        self,
        *,
        user_id: str,
        currency: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> Decimal:
        """
        Approximate used exposure from activity events.

        BUY increases exposure, SELL reduces exposure.
        Only counts records that have amount & currency.
        """
        used = Decimal("0")
        records = self.ledger.by_user(user_id=user_id)

        for r in records:
            if r.currency != currency or r.amount is None:
                continue

            if start_date and r.business_date < start_date:
                continue
            if end_date and r.business_date > end_date:
                continue

            if r.action in {"BUY", "EXECUTE_TRADE", "OPEN_POSITION"}:
                used += Decimal(str(r.amount))
            elif r.action in {"SELL", "CLOSE_POSITION"}:
                used -= Decimal(str(r.amount))

        if used < 0:
            used = Decimal("0")

        return used

    def trader_snapshot(
        self,
        *,
        scope_id: str,
        user_id: str,
        currency: str,
        trader_limit: Decimal,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> ExposureSnapshot:
        """
        Snapshot trader utilization vs trader limit and institutional cap.
        """
        institutional = self.limits.get_institutional_limit(scope_id)
        institutional_cap = institutional.max_limit

        trader_used = self._approx_used_exposure(
            user_id=user_id,
            currency=currency,
            start_date=start_date,
            end_date=end_date,
        )

        trader_remaining = max(Decimal("0"), trader_limit - trader_used)

        # aggregate used = sum of all traders' used exposure (approx)
        aggregate_used = Decimal("0")
        for uid, tlim in self.limits._trader_limits.items():  # v1 internal read
            if tlim.currency != currency:
                continue
            aggregate_used += self._approx_used_exposure(
                user_id=uid,
                currency=currency,
                start_date=start_date,
                end_date=end_date,
            )

        institutional_remaining = max(Decimal("0"), institutional_cap - aggregate_used)

        return ExposureSnapshot(
            scope_id=scope_id,
            currency=currency,
            trader_used=trader_used,
            trader_limit=trader_limit,
            trader_remaining=trader_remaining,
            aggregate_used=aggregate_used,
            institutional_cap=institutional_cap,
            institutional_remaining=institutional_remaining,
        )

    def assert_pretrade_allowed(
        self,
        *,
        scope_id: str,
        user_id: str,
        currency: str,
        trader_limit: Decimal,
        proposed_amount: Decimal,
    ) -> None:
        """
        Hard pre-trade block if:
        - proposed trade exceeds trader remaining capacity OR
        - proposed trade exceeds institutional remaining capacity
        """
        snap = self.trader_snapshot(
            scope_id=scope_id,
            user_id=user_id,
            currency=currency,
            trader_limit=trader_limit,
        )

        if proposed_amount > snap.trader_remaining:
            raise PermissionError("Trade exceeds trader remaining limit")

        if proposed_amount > snap.institutional_remaining:
            raise PermissionError("Trade exceeds institutional remaining capacity")