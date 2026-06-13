"""
Capital Strata Systems
Phase 98

Margin-Aware Trade Gate

Standalone deterministic gate for deciding whether new risk may be opened
from an existing MarginSnapshot.

No broker calls.
No order execution.
No dashboard integration.
"""

from __future__ import annotations

from dataclasses import dataclass

from engine.risk.margin_engine import (
    MarginEscalationState,
    MarginSnapshot,
    MarginState,
)


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
        margin_snapshot: MarginSnapshot,
        *,
        broker_mode: str = "PAPER",
    ) -> MarginTradeGateDecision:
        margin_state = self._state_value(margin_snapshot.margin_state)
        escalation_state = self._state_value(margin_snapshot.escalation_state)
        broker_mode_key = str(broker_mode or "PAPER").strip().upper()
        margin_source = str(margin_snapshot.margin_source or "UNKNOWN").strip().upper()

        if margin_state == MarginState.UNKNOWN.value:
            reason = "Margin state UNKNOWN; blocking new risk."
            if broker_mode_key == "LIVE":
                reason = "Fail-closed: LIVE broker mode with UNKNOWN margin state blocks new risk."
            return self._decision(
                allowed=False,
                decision="BLOCK",
                reason=reason,
                margin_snapshot=margin_snapshot,
                margin_state=margin_state,
                escalation_state=escalation_state,
            )

        if margin_state == MarginState.GREEN.value and escalation_state == MarginEscalationState.NORMAL.value:
            reason = "Margin state GREEN/NORMAL allows new risk."
            if broker_mode_key == "PAPER" and margin_source == "SIMULATED":
                reason = "PAPER simulated margin GREEN/NORMAL allows new risk."
            return self._decision(
                allowed=True,
                decision="ALLOW",
                reason=reason,
                margin_snapshot=margin_snapshot,
                margin_state=margin_state,
                escalation_state=escalation_state,
            )

        if margin_state == MarginState.YELLOW.value and escalation_state == MarginEscalationState.MONITOR.value:
            reason = "Margin state YELLOW/MONITOR allows new risk with monitoring."
            if broker_mode_key == "PAPER" and margin_source == "SIMULATED":
                reason = "PAPER simulated margin YELLOW/MONITOR allows new risk with monitoring."
            return self._decision(
                allowed=True,
                decision="MONITOR",
                reason=reason,
                margin_snapshot=margin_snapshot,
                margin_state=margin_state,
                escalation_state=escalation_state,
            )

        if margin_state == MarginState.ORANGE.value or escalation_state == MarginEscalationState.RESTRICT_NEW_RISK.value:
            return self._decision(
                allowed=False,
                decision="RESTRICT_NEW_RISK",
                reason="Margin state ORANGE/RESTRICT_NEW_RISK blocks new exposure.",
                margin_snapshot=margin_snapshot,
                margin_state=margin_state,
                escalation_state=escalation_state,
            )

        if margin_state == MarginState.RED.value or escalation_state == MarginEscalationState.DEFENSIVE_ONLY.value:
            return self._decision(
                allowed=False,
                decision="DEFENSIVE_ONLY",
                reason="Margin state RED/DEFENSIVE_ONLY permits defensive action only.",
                margin_snapshot=margin_snapshot,
                margin_state=margin_state,
                escalation_state=escalation_state,
            )

        if margin_state == MarginState.BLACK.value or escalation_state == MarginEscalationState.CRITICAL_BLOCK.value:
            return self._decision(
                allowed=False,
                decision="BLOCK",
                reason="Margin state BLACK/CRITICAL_BLOCK blocks new risk.",
                margin_snapshot=margin_snapshot,
                margin_state=margin_state,
                escalation_state=escalation_state,
            )

        return self._decision(
            allowed=False,
            decision="BLOCK",
            reason="Unrecognized margin state; blocking new risk.",
            margin_snapshot=margin_snapshot,
            margin_state=margin_state,
            escalation_state=escalation_state,
        )

    def _decision(
        self,
        *,
        allowed: bool,
        decision: str,
        reason: str,
        margin_snapshot: MarginSnapshot,
        margin_state: str,
        escalation_state: str,
    ) -> MarginTradeGateDecision:
        return MarginTradeGateDecision(
            allowed=allowed,
            decision=decision,
            reason=reason,
            margin_state=margin_state,
            escalation_state=escalation_state,
            margin_utilization_pct=float(margin_snapshot.margin_utilization_pct or 0.0),
        )

    def _state_value(self, state: object) -> str:
        return str(getattr(state, "value", state) or "UNKNOWN").strip().upper()
