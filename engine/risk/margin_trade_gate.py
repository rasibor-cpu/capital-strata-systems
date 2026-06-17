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
                reason="missing_snapshot",
                margin_state="UNKNOWN",
                escalation_state="UNKNOWN",
                margin_utilization_pct=0.0,
            )

        # 1. New Canonical MarginSnapshot Logic
        if hasattr(margin_snapshot, "buying_power"):
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

            return self._decision(
                allowed=True,
                decision="ALLOW",
                reason="margin_ok",
                margin_state=mstate,
                escalation_state="NORMAL",
                margin_utilization_pct=float(getattr(margin_snapshot, "margin_ratio", 0.0)),
            )

        # 2. Legacy MarginSnapshot Backward Compatibility
        margin_state = self._state_value(getattr(margin_snapshot, "margin_state", "UNKNOWN"))
        escalation_state = self._state_value(getattr(margin_snapshot, "escalation_state", "UNKNOWN"))
        broker_mode_key = str(broker_mode or "PAPER").strip().upper()
        margin_source = str(getattr(margin_snapshot, "margin_source", "UNKNOWN")).strip().upper()

        if margin_state == "UNKNOWN":
            reason = "Margin state UNKNOWN; blocking new risk."
            if broker_mode_key == "LIVE":
                reason = "Fail-closed: LIVE broker mode with UNKNOWN margin state blocks new risk."
            return self._decision(
                allowed=False,
                decision="BLOCK",
                reason=reason,
                margin_state=margin_state,
                escalation_state=escalation_state,
                margin_utilization_pct=float(getattr(margin_snapshot, "margin_utilization_pct", 0.0)),
            )

        if margin_state == "GREEN" and escalation_state == "NORMAL":
            reason = "Margin state GREEN/NORMAL allows new risk."
            if broker_mode_key == "PAPER" and margin_source == "SIMULATED":
                reason = "PAPER simulated margin GREEN/NORMAL allows new risk."
            return self._decision(
                allowed=True,
                decision="ALLOW",
                reason=reason,
                margin_state=margin_state,
                escalation_state=escalation_state,
                margin_utilization_pct=float(getattr(margin_snapshot, "margin_utilization_pct", 0.0)),
            )

        if margin_state == "YELLOW" and escalation_state == "MONITOR":
            reason = "Margin state YELLOW/MONITOR allows new risk with monitoring."
            if broker_mode_key == "PAPER" and margin_source == "SIMULATED":
                reason = "PAPER simulated margin YELLOW/MONITOR allows new risk with monitoring."
            return self._decision(
                allowed=True,
                decision="MONITOR",
                reason=reason,
                margin_state=margin_state,
                escalation_state=escalation_state,
                margin_utilization_pct=float(getattr(margin_snapshot, "margin_utilization_pct", 0.0)),
            )

        if margin_state == "ORANGE" or escalation_state == "RESTRICT_NEW_RISK":
            return self._decision(
                allowed=False,
                decision="RESTRICT_NEW_RISK",
                reason="Margin state ORANGE/RESTRICT_NEW_RISK blocks new exposure.",
                margin_state=margin_state,
                escalation_state=escalation_state,
                margin_utilization_pct=float(getattr(margin_snapshot, "margin_utilization_pct", 0.0)),
            )

        if margin_state == "RED" or escalation_state == "DEFENSIVE_ONLY":
            return self._decision(
                allowed=False,
                decision="DEFENSIVE_ONLY",
                reason="Margin state RED/DEFENSIVE_ONLY permits defensive action only.",
                margin_state=margin_state,
                escalation_state=escalation_state,
                margin_utilization_pct=float(getattr(margin_snapshot, "margin_utilization_pct", 0.0)),
            )

        if margin_state == "BLACK" or escalation_state == "CRITICAL_BLOCK":
            return self._decision(
                allowed=False,
                decision="BLOCK",
                reason="Margin state BLACK/CRITICAL_BLOCK blocks new risk.",
                margin_state=margin_state,
                escalation_state=escalation_state,
                margin_utilization_pct=float(getattr(margin_snapshot, "margin_utilization_pct", 0.0)),
            )

        return self._decision(
            allowed=False,
            decision="BLOCK",
            reason="Unrecognized margin state; blocking new risk.",
            margin_state=margin_state,
            escalation_state=escalation_state,
            margin_utilization_pct=float(getattr(margin_snapshot, "margin_utilization_pct", 0.0)),
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
