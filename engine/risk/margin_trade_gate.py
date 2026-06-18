from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from engine.risk.margin_snapshot import MarginSnapshot
from engine.risk.margin_state import MarginState

@dataclass(frozen=True)
class MarginTradeGateDecision:
    allowed: bool
    decision: str
    reason: str
    margin_state: str
    escalation_state: str
    margin_utilization_pct: float


class MarginTradeGate:
    """
    Deterministic margin-aware trade gate.

    The gate consumes already-computed margin state. It does not fetch broker
    data, calculate margin, place orders, or mutate runtime state.
    """

    def evaluate(
        self,
        margin_snapshot: Optional[Any] = None,
        *,
        broker_mode: str = "PAPER",
    ) -> MarginTradeGateDecision:
        if margin_snapshot is None:
            return self._decision(
                allowed=False,
                decision="BLOCK",
                reason="MARGIN_SNAPSHOT_UNAVAILABLE",
                margin_state="UNKNOWN",
                escalation_state="UNKNOWN",
                margin_utilization_pct=0.0,
            )

        # 1. Canonical MarginSnapshot Logic
        if not hasattr(margin_snapshot, "buying_power"):
            return self._decision(
                allowed=False,
                decision="BLOCK",
                reason="MARGIN_SNAPSHOT_UNAVAILABLE",
                margin_state="UNKNOWN",
                escalation_state="UNKNOWN",
                margin_utilization_pct=0.0,
            )

        try:
            buying_power = float(margin_snapshot.buying_power)
            if buying_power < 0:
                return self._decision(
                    allowed=False,
                    decision="BLOCK",
                    reason="negative_buying_power",
                    margin_state=self._state_value(getattr(margin_snapshot, "margin_state", "UNKNOWN")),
                    escalation_state="UNKNOWN",
                    margin_utilization_pct=float(getattr(margin_snapshot, "margin_ratio", 0.0)),
                )
        except (ValueError, TypeError):
            return self._decision(
                allowed=False,
                decision="BLOCK",
                reason="invalid_snapshot",
                margin_state="UNKNOWN",
                escalation_state="UNKNOWN",
                margin_utilization_pct=0.0,
            )

        mstate = self._state_value(getattr(margin_snapshot, "margin_state", "UNKNOWN"))
        if mstate == "LIQUIDATION_RISK":
            return self._decision(
                allowed=False,
                decision="BLOCK",
                reason="liquidation_risk",
                margin_state=mstate,
                escalation_state="UNKNOWN",
                margin_utilization_pct=float(getattr(margin_snapshot, "margin_ratio", 0.0)),
            )

        if mstate in ("CRITICAL", "RESTRICTED"):
            return self._decision(
                allowed=False,
                decision="RESTRICT_NEW_RISK",
                reason=f"{mstate}_blocks_new_risk",
                margin_state=mstate,
                escalation_state="UNKNOWN",
                margin_utilization_pct=float(getattr(margin_snapshot, "margin_ratio", 0.0)),
            )

        if mstate == "WARNING":
            return self._decision(
                allowed=True,
                decision="ALLOW_WITH_WARNING",
                reason="margin_warning",
                margin_state=mstate,
                escalation_state="UNKNOWN",
                margin_utilization_pct=float(getattr(margin_snapshot, "margin_ratio", 0.0)),
            )

        if mstate == "NORMAL":
            return self._decision(
                allowed=True,
                decision="ALLOW",
                reason="margin_ok",
                margin_state=mstate,
                escalation_state="NORMAL",
                margin_utilization_pct=float(getattr(margin_snapshot, "margin_ratio", 0.0)),
            )

        return self._decision(
            allowed=False,
            decision="BLOCK",
            reason="invalid_snapshot",
            margin_state=mstate,
            escalation_state="UNKNOWN",
            margin_utilization_pct=float(getattr(margin_snapshot, "margin_ratio", 0.0)),
        )

    def _decision(
        self,
        *,
        allowed: bool,
        decision: str,
        reason: str,
        margin_state: str,
        escalation_state: str,
        margin_utilization_pct: float,
    ) -> MarginTradeGateDecision:
        return MarginTradeGateDecision(
            allowed=allowed,
            decision=decision,
            reason=reason,
            margin_state=margin_state,
            escalation_state=escalation_state,
            margin_utilization_pct=margin_utilization_pct,
        )

    def _state_value(self, state: object) -> str:
        return str(getattr(state, "value", state) or "UNKNOWN").strip().upper()
