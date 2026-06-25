from __future__ import annotations

from backend.validation.marathon_snapshot import MarathonSnapshot
from backend.validation.marathon_statistics import build_marathon_statistics


def _snapshot(cycle_number: int, equity: float, decision: str, strategy: str, regime: str, alerts: int, recoveries: int, exposure: float) -> MarathonSnapshot:
    return MarathonSnapshot(
        timestamp=f"2026-06-24T12:00:0{cycle_number}+00:00",
        uptime_seconds=float(cycle_number),
        cycle_number=cycle_number,
        paper_balance=100000.0,
        equity=equity,
        realized_pnl=float(cycle_number),
        unrealized_pnl=float(cycle_number) / 2.0,
        approved_trades=1,
        blocked_trades=0,
        open_positions=cycle_number,
        alerts=alerts,
        recoveries=recoveries,
        heartbeat_status="OK",
        decision=decision,
        selected_strategy=strategy,
        market_regime=regime,
        portfolio_exposure=exposure,
        cycle_duration_seconds=0.25,
        drawdown=max(0.0, 100000.0 - equity),
    )


def test_statistics_generation() -> None:
    stats = build_marathon_statistics([
        _snapshot(1, 100010.0, "ALLOW", "alpha", "TRENDING", 1, 0, 1000.0),
        _snapshot(2, 100020.0, "REDUCE_SIZE", "beta", "RANGING", 2, 1, 1500.0),
        _snapshot(3, 99950.0, "BLOCK", "alpha", "TRENDING", 1, 0, 1750.0),
    ])

    assert stats.total_cycles == 3
    assert stats.average_cycle_duration_seconds == 0.25
    assert stats.decision_distribution == {"ALLOW": 1, "BLOCK": 1, "REDUCE_SIZE": 1}
    assert stats.strategy_distribution == {"alpha": 2, "beta": 1}
    assert stats.regime_distribution == {"RANGING": 1, "TRENDING": 2}
    assert stats.alert_counts == 4
    assert stats.recovery_counts == 1
    assert stats.peak_equity == 100020.0


def test_empty_history() -> None:
    stats = build_marathon_statistics([])

    assert stats.total_cycles == 0
    assert stats.maximum_drawdown == 0.0
    assert stats.decision_distribution == {}


def test_deterministic_output() -> None:
    snapshots = [
        _snapshot(1, 100010.0, "ALLOW", "alpha", "TRENDING", 1, 0, 1000.0),
        _snapshot(2, 100020.0, "REDUCE_SIZE", "beta", "RANGING", 2, 1, 1500.0),
    ]

    assert build_marathon_statistics(snapshots) == build_marathon_statistics(snapshots)
