from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class DecisionType(str, Enum):
    APPROVE = "APPROVE"
    REJECT = "REJECT"
    REQUIRE_USER_AUTH = "REQUIRE_USER_AUTH"


# =========================
# Loss & Risk Gate Policies
# =========================

@dataclass(frozen=True)
class LossGatePolicy:
    """
    Over-trading protection policy.

    Rule (locked v1):
    - If loss_rate over the rolling window exceeds max_loss_rate,
      new trades must NOT proceed automatically.
    - Explicit user authorization is required.
    """
    rolling_window_trades: int = 20
    max_loss_rate: float = 0.25  # 25% loss threshold


@dataclass(frozen=True)
class TradeGateSnapshot:
    """
    Snapshot of recent trade performance used for gating decisions.
    """
    trades_in_window: int
    losses_in_window: int
    loss_rate: float
    consecutive_losses: int
    session_trades_total: int
    session_drawdown_pct: float


@dataclass(frozen=True)
class RiskSnapshot:
    """
    Risk envelope snapshot (simulation-only).
    """
    equity: float
    max_risk_per_trade_pct: float
    max_session_drawdown_pct: float
    max_trades_per_session: int
    cooldown_seconds: int


# ===================================
# Explicit Override & Approval Objects
# ===================================

@dataclass(frozen=True)
class RiskOverrideRequest:
    """
    Raised when a recommended trade exceeds stated risk thresholds.

    This object MUST be shown to the user verbatim before any approval
    can be accepted.
    """
    exceeded_fields: Dict[str, float]  # e.g. {"risk_per_trade_pct": 2.3}
    allowed_limits: Dict[str, float]   # e.g. {"risk_per_trade_pct": 1.0}
    warning_text: str = (
        "WARNING: This trade exceeds defined risk limits and may lead to "
        "accelerated losses, large drawdowns, or account ruin."
    )
    consequence_summary: str = (
        "Possible outcomes include consecutive losses, loss of capital, "
        "and breach of your session drawdown constraints."
    )


@dataclass(frozen=True)
class ApprovalChallenge:
    """
    Triple-confirmation approval challenge for dangerous overrides.

    SECURITY MODEL:
    - Uses a SECOND secret (Override Approval Code), distinct from login password.
    - Only a HASH of the override code is stored/compared by higher layers.
    - Module 7 only enforces the challenge contract (no hashing here).

    RULE (locked v1):
    - User must successfully enter the override code THREE TIMES.
    - No single-click approvals.
    """
    required_entries: int = 3
    entries_received: int = 0
    expected_code_hash: Optional[str] = None  # provided by auth layer
    final_ack_phrase: str = "I UNDERSTAND AND ACCEPT THE RISK"
    final_ack_matched: bool = False

    warning_text: str = (
        "You are attempting to override system safety warnings after a loss streak "
        "or risk breach. This action is intentionally difficult."
    )
    gate_reason: str = "LOSS_RATE_OR_RISK_OVERRIDE"


@dataclass(frozen=True)
class UserAuthorizationRequest:
    """
    Represents a required explicit user authorization when gates are breached.
    """
    gate_name: str
    policy: LossGatePolicy
    snapshot: TradeGateSnapshot

    approval_challenge: ApprovalChallenge
    risk_override: Optional[RiskOverrideRequest] = None

    justification_prompt: str = (
        "Explain why this trade should be taken despite recent losses and/or "
        "risk breaches. Provide concrete evidence of edge."
    )


# ==================
# Final Trade Output
# ==================

@dataclass(frozen=True)
class TradeDecision:
    """
    Final decision object emitted by Module 7.

    IMPORTANT:
    - allowed=False when REQUIRE_USER_AUTH
    - Trade cannot proceed unless approval_challenge is fully satisfied
      (entries_received >= 3 AND final_ack_matched == True)
    """
    decision: DecisionType
    allowed: bool
    reason: str

    requires_user_authorization: bool = False
    auth_request: Optional[UserAuthorizationRequest] = None

    # Simulation-only metadata
    risk_cap_pct: Optional[float] = None
    cooldown_until_ts: Optional[float] = None

    # Mandatory audit trail for overrides
    why_trade_anyway: List[str] = field(default_factory=list)
    debug: Dict[str, Any] = field(default_factory=dict)