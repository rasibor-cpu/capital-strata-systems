from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal


@dataclass(frozen=True)
class ResearchEvidence:
    """Immutable research result used for strategy certification review."""

    research_id: str
    strategy_id: str
    dataset_id: str
    asset_class: str
    sample_count: int
    trade_count: int
    total_return_pct: Decimal
    benchmark_return_pct: Decimal
    max_drawdown_pct: Decimal
    sharpe_ratio: Decimal
    profit_factor: Decimal
    win_rate: Decimal
    out_of_sample: bool
    walk_forward_splits: int
    stress_test_passed: bool
    data_quality_passed: bool
    generated_at_utc: datetime
