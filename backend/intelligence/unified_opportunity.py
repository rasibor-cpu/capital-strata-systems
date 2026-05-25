from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict


@dataclass
class UnifiedOpportunity:
    symbol: str = "UNKNOWN"
    asset_class: str = "unknown"
    venue: str = "UNKNOWN"
    direction: str = "neutral"
    signal_strength: float = 0.0
    confidence: float = 0.0
    expected_edge: float = 0.0
    estimated_cost: float = 0.0
    estimated_slippage: float = 0.0
    liquidity_score: float = 0.0
    volatility_score: float = 0.0
    spread_score: float = 0.0
    execution_viable: bool = False
    scanner_source: str = "unknown"
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "symbol": self.symbol,
            "asset_class": self.asset_class,
            "venue": self.venue,
            "direction": self.direction,
            "signal_strength": self.signal_strength,
            "confidence": self.confidence,
            "expected_edge": self.expected_edge,
            "estimated_cost": self.estimated_cost,
            "estimated_slippage": self.estimated_slippage,
            "liquidity_score": self.liquidity_score,
            "volatility_score": self.volatility_score,
            "spread_score": self.spread_score,
            "execution_viable": self.execution_viable,
            "scanner_source": self.scanner_source,
            "timestamp": self.timestamp,
            "metadata": dict(self.metadata),
        }
