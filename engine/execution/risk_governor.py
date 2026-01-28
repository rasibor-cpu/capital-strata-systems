from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any, Dict, Optional, Tuple

from .decision import (
    ApprovalChallenge,
    DecisionType,
    LossGatePolicy,
    RiskOverrideRequest,
    RiskSnapshot,
    TradeDecision,
    TradeGateSnapshot,
    UserAuthorizationRequest,
)


@dataclass(frozen=True)
class GovernorInputs:
    """
    Packed inputs to Module 7 decisioning.
    Simulation-only at this stage.
    """
    signal: Dict[str, Any]
    regime: Dict[str, Any]
    risk: RiskSnapshot
    gate_snapshot: TradeGateSnapshot
    loss_gate_policy: LossGatePolicy = LossGatePolicy()


# =========================
# Internal gate evaluators
# =========================

def _loss_rate_exceeded(snapshot: TradeGateSnapshot, policy: LossGatePolicy) -> bool:
    return snapshot.loss_rate > policy.max_loss_rate


def _risk_thresholds_exceeded(
    risk: RiskSnapshot, signal: Dict[str, Any]
) -> Optional[RiskOverrideRequest]:
    """
    Check if the recommended trade exceeds stated risk thresholds.

    Expected (optional) signal fields:
      - risk_per_trade_pct
    """
    exceeded: Dict[str, float] = {}
    allowed: Dict[str, float] = {}

    risk_per_trade = signal.get("risk_per_trade_pct")
    if risk_per_trade is not None:
        allowed["risk_per_trade_pct"] = risk.max_risk_per_trade_pct
        if risk_per_trade > risk.max_risk_per_trade_pct:
            exceeded["risk_per_trade_pct"] = risk_per_trade

    if not exceeded:
        return None

    return RiskOverrideRequest(
        exceeded_fields=exceeded,
        allowed_limits=allowed,
    )


# =========================
# Approval progression API
# =========================

@dataclass(frozen=True)
class ApprovalAttempt:
    """
    Handoff contract from UI/Auth layer for each approval attempt.
    - code_hash_ok: auth layer validated the override-code hash
    - final_ack_phrase_ok: exact match of final acknowledgement phrase
    """
    code_hash_ok: bool
    final_ack_phrase_ok: bool = False


def advance_approval(
    challenge: ApprovalChallenge,
    attempt: ApprovalAttempt,
) -> Tuple[ApprovalChallenge, bool]:
    """
    Progress the approval challenge state.

    Rules:
    - Each successful override-code entry increments entries_received by 1.
    - Wrong code does NOT increment.
    - Final acknowledgement phrase is only considered on/after the 3rd success.
    - Approval is complete only when:
        entries_received >= required_entries AND final_ack_matched == True
    """
    entries = challenge.entries_received

    if attempt.code_hash_ok:
        entries = min(entries + 1, challenge.required_entries)

    final_ack = challenge.final_ack_matched
    if entries >= challenge.required_entries and attempt.final_ack_phrase_ok:
        final_ack = True

    updated = replace(
        challenge,
        entries_received=entries,
        final_ack_matched=final_ack,
    )

    approved = (
        updated.entries_received >= updated.required_entries
        and updated.final_ack_matched
    )

    return updated, approved


# =========================
# Decision entrypoint
# =========================

def decide_trade(inputs: GovernorInputs) -> TradeDecision:
    """
    Module 7 — Step 7.3 decisioning.

    Behavior:
    - If loss-rate > 25% OR risk thresholds exceeded:
        * Block automatic approval
        * Require explicit user authorization
        * Attach triple-approval challenge
    - Otherwise:
        * Approve (simulation-only)
    """
    snapshot = inputs.gate_snapshot
    policy = inputs.loss_gate_policy

    loss_gate_hit = _loss_rate_exceeded(snapshot, policy)
    risk_override = _risk_thresholds_exceeded(inputs.risk, inputs.signal)

    if loss_gate_hit or risk_override:
        approval_challenge = ApprovalChallenge(
            required_entries=3,
            entries_received=0,
            expected_code_hash=None,  # provided by auth layer
            final_ack_matched=False,
            gate_reason="LOSS_RATE_OR_RISK_OVERRIDE",
        )

        auth_request = UserAuthorizationRequest(
            gate_name="LOSS_RATE_OR_RISK_OVERRIDE",
            policy=policy,
            snapshot=snapshot,
            approval_challenge=approval_challenge,
            risk_override=risk_override,
        )

        reasons = []
        if loss_gate_hit:
            reasons.append("Loss-rate exceeded threshold")
        if risk_override:
            reasons.append("Risk thresholds exceeded")

        return TradeDecision(
            decision=DecisionType.REQUIRE_USER_AUTH,
            allowed=False,
            reason="; ".join(reasons),
            requires_user_authorization=True,
            auth_request=auth_request,
            risk_cap_pct=inputs.risk.max_risk_per_trade_pct,
            cooldown_until_ts=None,
            why_trade_anyway=[],
            debug={
                "loss_rate": snapshot.loss_rate,
                "max_loss_rate": policy.max_loss_rate,
                "risk_override": bool(risk_override),
            },
        )

    # Safe path: approve (simulation-only)
    return TradeDecision(
        decision=DecisionType.APPROVE,
        allowed=True,
        reason="All risk and loss gates satisfied",
        requires_user_authorization=False,
        auth_request=None,
        risk_cap_pct=inputs.risk.max_risk_per_trade_pct,
        cooldown_until_ts=None,
        why_trade_anyway=[],
        debug={"loss_rate": snapshot.loss_rate},
    )