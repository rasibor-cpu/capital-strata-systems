from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class TradeQualityAssessment:
    trade_id: str
    symbol: str
    asset_class: str
    quality_score: float
    confidence: float
    recommendation: str
    factor_scores: dict[str, float]
    diagnostics: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
