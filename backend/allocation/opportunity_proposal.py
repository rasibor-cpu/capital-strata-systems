from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal


@dataclass(frozen=True)
class OpportunityProposal:
    """Canonical CAIE opportunity proposal.

    This is an advisory/shadow data object only. It carries no broker order
    method, no execution route, and no authority to move capital.
    """

    proposal_id: str
    source: str
    broker: str
    symbol: str
    asset_class: str
    side: str
    probability_win: Decimal
    confidence: Decimal
    capital_required: Decimal
    max_drawdown_pct: Decimal
    expected_return_pct: Decimal
    liquidity_score: Decimal
    regime_alignment: Decimal
    observed_at_utc: datetime
