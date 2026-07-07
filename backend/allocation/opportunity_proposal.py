from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


ALLOWED_ASSET_CLASSES: tuple[str, ...] = (
    "CRYPTO",
    "FX",
    "FUTURES",
    "OPTIONS",
    "EQUITIES",
)


def canonical_asset_class(value: Any) -> str:
    text = str(value or "").strip().upper()
    return text


@dataclass(frozen=True)
class OpportunityProposal:
    proposal_id: str
    symbol: str
    asset_class: str
    probability: float
    confidence: float
    expected_drawdown_pct: float
    risk_score: float
    requested_capital: float

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> "OpportunityProposal":
        return cls(
            proposal_id=str(payload["proposal_id"]).strip(),
            symbol=str(payload["symbol"]).strip().upper(),
            asset_class=canonical_asset_class(payload["asset_class"]),
            probability=float(payload["probability"]),
            confidence=float(payload["confidence"]),
            expected_drawdown_pct=float(payload["expected_drawdown_pct"]),
            risk_score=float(payload["risk_score"]),
            requested_capital=float(payload["requested_capital"]),
        )
