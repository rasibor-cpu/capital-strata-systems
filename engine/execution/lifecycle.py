from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class TradeState(str, Enum):
    CANDIDATE = "CANDIDATE"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    REQUIRE_USER_AUTH = "REQUIRE_USER_AUTH"
    SIMULATED = "SIMULATED"
    CLOSED = "CLOSED"
    LOGGED = "LOGGED"


@dataclass(frozen=True)
class TradeLifecycle:
    """
    Minimal state container for trade lifecycle control.
    Transitions will be implemented in later steps.
    """
    trade_id: str
    state: TradeState
    created_ts: float
    updated_ts: float
    rejection_reason: Optional[str] = None