"""
Pre-Trade Risk Gate (v1)
------------------------
Central pre-trade limit enforcement that:

- checks trader remaining capacity
- checks institutional remaining capacity
- triggers alert escalation chain:
    user -> supervisor -> department head
- hard-blocks trades that breach limits

This module does NOT execute trades.
It is called BEFORE trade submission.
"""

from dataclasses import dataclass
from decimal import Decimal
from typing import Optional

from engine.security.trade_exposure_tracker import TradeExposureTracker
from engine.security.exposure_alerts import ExposureAlertService, ExposureAlertEvent


@dataclass(frozen=True)
class PreTradeDecision:
    allowed: bool
    reason: str


class PreTradeRiskGate:
    def __init__(
        self,
        *,
        tracker: TradeExposureTracker,
        alerts: ExposureAlertService,
    ):
        self.tracker = tracker
        self.alerts = alerts

    def check_and_alert(
        self,
        *,
        scope_id: str,
        user_id: str,
        session_id: Optional[str],
        currency: str,
        trader_limit: Decimal,
        proposed_amount: Decimal,
    ) -> PreTradeDecision:
        """
        Returns decision; triggers alerts if blocked.
        """

        snap = self.tracker.trader_snapshot(
            scope_id=scope_id,
            user_id=user_id,
            currency=currency,
            trader_limit=trader_limit,
        )

        # Trader limit breach
        if proposed_amount > snap.trader_remaining:
            evt = ExposureAlertEvent(
                alert_type="TRADER_LIMIT_BREACH",
                user_id=user_id,
                session_id=session_id,
                scope_id=scope_id,
                currency=currency,
                proposed_amount=str(proposed_amount),
                reason="Trade exceeds trader remaining limit",
                meta={
                    "trader_used": str(snap.trader_used),
                    "trader_limit": str(snap.trader_limit),
                    "trader_remaining": str(snap.trader_remaining),
                    "aggregate_used": str(snap.aggregate_used),
                    "institutional_cap": str(snap.institutional_cap),
                    "institutional_remaining": str(snap.institutional_remaining),
                },
            )
            self.alerts.escalate_all(evt)
            return PreTradeDecision(allowed=False, reason=evt.reason)

        # Institutional limit breach
        if proposed_amount > snap.institutional_remaining:
            evt = ExposureAlertEvent(
                alert_type="INSTITUTIONAL_LIMIT_BREACH",
                user_id=user_id,
                session_id=session_id,
                scope_id=scope_id,
                currency=currency,
                proposed_amount=str(proposed_amount),
                reason="Trade exceeds institutional remaining capacity",
                meta={
                    "aggregate_used": str(snap.aggregate_used),
                    "institutional_cap": str(snap.institutional_cap),
                    "institutional_remaining": str(snap.institutional_remaining),
                },
            )
            self.alerts.escalate_all(evt)
            return PreTradeDecision(allowed=False, reason=evt.reason)

        return PreTradeDecision(allowed=True, reason="OK")