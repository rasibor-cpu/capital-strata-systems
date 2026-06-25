from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass
from typing import Any, Iterable

from .marathon_snapshot import MarathonSnapshot


@dataclass(frozen=True)
class MarathonStatistics:
    total_cycles: int
    average_cycle_duration_seconds: float
    decision_distribution: dict[str, int]
    strategy_distribution: dict[str, int]
    regime_distribution: dict[str, int]
    portfolio_exposure: float
    alert_counts: int
    recovery_counts: int
    maximum_drawdown: float
    peak_equity: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_marathon_statistics(snapshots: Iterable[MarathonSnapshot]) -> MarathonStatistics:
    snapshot_list = list(snapshots)
    if not snapshot_list:
        return MarathonStatistics(
            total_cycles=0,
            average_cycle_duration_seconds=0.0,
            decision_distribution={},
            strategy_distribution={},
            regime_distribution={},
            portfolio_exposure=0.0,
            alert_counts=0,
            recovery_counts=0,
            maximum_drawdown=0.0,
            peak_equity=0.0,
        )

    decision_counts = Counter(snapshot.decision for snapshot in snapshot_list if snapshot.decision)
    strategy_counts = Counter(snapshot.selected_strategy for snapshot in snapshot_list if snapshot.selected_strategy)
    regime_counts = Counter(snapshot.market_regime for snapshot in snapshot_list if snapshot.market_regime)
    total_duration = sum(float(snapshot.cycle_duration_seconds) for snapshot in snapshot_list)
    peak_equity = max(float(snapshot.equity) for snapshot in snapshot_list)

    drawdown = 0.0
    running_peak = float(snapshot_list[0].equity)
    for snapshot in snapshot_list:
        equity = float(snapshot.equity)
        if equity > running_peak:
            running_peak = equity
        drawdown = max(drawdown, running_peak - equity)

    return MarathonStatistics(
        total_cycles=len(snapshot_list),
        average_cycle_duration_seconds=round(total_duration / len(snapshot_list), 8),
        decision_distribution={key: decision_counts[key] for key in sorted(decision_counts.keys())},
        strategy_distribution={key: strategy_counts[key] for key in sorted(strategy_counts.keys())},
        regime_distribution={key: regime_counts[key] for key in sorted(regime_counts.keys())},
        portfolio_exposure=round(sum(float(snapshot.portfolio_exposure) for snapshot in snapshot_list), 8),
        alert_counts=sum(int(snapshot.alerts) for snapshot in snapshot_list),
        recovery_counts=sum(int(snapshot.recoveries) for snapshot in snapshot_list),
        maximum_drawdown=round(drawdown, 8),
        peak_equity=round(peak_equity, 8),
    )
