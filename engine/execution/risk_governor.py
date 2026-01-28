from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict

from .decision import (
    DecisionType,
    LossGatePolicy,
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


def decide_trade(inputs: GovernorInputs) -> TradeDecision:
    """
    Decision stub.

    Logic will be implemented in Step 7.2+:
    - Regime hard gate
    - Cooldown enforcement
    - Max trades per session
    - Session drawdown protection
    - Loss-rate authorization gate (25% rule)
    """
    raise NotImplementedError("Module 7 Step 7.1: decision logic not implemented yet.")