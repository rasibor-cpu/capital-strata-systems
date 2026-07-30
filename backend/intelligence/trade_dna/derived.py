"""DIP-002 Layer 2 — derived metrics (recomputable; never inside fact DNA)."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Optional

from backend.intelligence.trade_dna.constants import ANALYSIS_VERSION, LAYER_DERIVED


@dataclass(frozen=True)
class DerivedTradeMetrics:
    """Recomputable metrics keyed by dna_id + analysis_version.

    Must never be persisted inside TradeDNARecord fact storage.
    """

    dna_id: str
    trade_id: str
    analysis_version: str = ANALYSIS_VERSION
    layer: str = LAYER_DERIVED
    profit: Optional[float] = None
    return_pct: Optional[float] = None
    holding_period_seconds: Optional[float] = None
    mae: Optional[float] = None
    mfe: Optional[float] = None
    expectancy_contribution: Optional[float] = None
    edge_contribution: Optional[float] = None
    capital_efficiency: Optional[float] = None
    execution_quality: Optional[float] = None
    sharpe_contribution: Optional[float] = None
    drawdown_contribution: Optional[float] = None
    extensions: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def assert_not_embedded_in_facts(payload: dict[str, Any]) -> None:
    """Guard: derived metric keys must not appear as top-level DNA fact fields."""
    forbidden = {
        "profit",
        "return_pct",
        "mae",
        "mfe",
        "expectancy_contribution",
        "edge_contribution",
        "capital_efficiency",
        "execution_quality",
        "sharpe_contribution",
        "drawdown_contribution",
        "derived",
        "advisory",
    }
    overlap = forbidden.intersection(payload.keys())
    if overlap:
        raise ValueError(f"derived_or_advisory_embedded_in_facts:{sorted(overlap)}")
