"""
Market State Gate
REA Capital Trading Engine

Institutional Pre-Trade Checks:
- Tradeability
- Spread threshold
- Session window control
"""

from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timezone, time
from typing import Dict, Any, List


ALLOW = "ALLOW"
BLOCK = "BLOCK"


@dataclass(frozen=True)
class MarketPolicy:
    max_spread: float  # in price units
    allow_london: bool
    allow_newyork: bool
    allow_asia: bool


def default_policy() -> MarketPolicy:
    return MarketPolicy(
        max_spread=0.0005,  # adjust later per instrument
        allow_london=True,
        allow_newyork=True,
        allow_asia=False,
    )


def _current_utc() -> datetime:
    return datetime.now(timezone.utc)


def _in_session(policy: MarketPolicy) -> bool:
    now = _current_utc().time()

    london = time(7, 0) <= now <= time(16, 0)
    newyork = time(12, 0) <= now <= time(21, 0)
    asia = time(0, 0) <= now <= time(6, 0)

    if london and policy.allow_london:
        return True
    if newyork and policy.allow_newyork:
        return True
    if asia and policy.allow_asia:
        return True

    return False


class MarketStateGate:

    def __init__(self):
        self.policy = default_policy()

    def evaluate(self, snapshot: Dict[str, Any]) -> Dict[str, Any]:

        reasons: List[str] = []

        # 1. Tradeability
        if not snapshot.get("tradeable", False):
            return {
                "decision": BLOCK,
                "reasons": ["Instrument not tradeable"]
            }

        # 2. Spread
        spread = snapshot.get("spread")
        if spread is None:
            return {
                "decision": BLOCK,
                "reasons": ["Missing spread in snapshot"]
            }

        if spread > self.policy.max_spread:
            return {
                "decision": BLOCK,
                "reasons": [f"Spread too wide ({spread})"]
            }

        # 3. Session Window
        if not _in_session(self.policy):
            return {
                "decision": BLOCK,
                "reasons": ["Outside permitted session window"]
            }

        return {
            "decision": ALLOW,
            "reasons": ["Market state checks passed"]
        }
