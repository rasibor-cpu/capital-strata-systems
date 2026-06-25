from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest

from backend.validation.marathon_checklist import MarathonCheckResult
from backend.validation.marathon_readiness import MarathonReadiness
from backend.validation.marathon_runner import MarathonRunResult, MarathonRunner, MarathonRunnerError
from backend.validation.marathon_snapshot import MarathonCyclePlan


class ReadyMarathonReadiness(MarathonReadiness):
    def certify(self):
        results = [MarathonCheckResult(check_name="repository_clean", passed=True)]
        results.extend(
            MarathonCheckResult(check_name=name, passed=True)
            for name in (
                "replay_engine_available",
                "intelligence_orchestrator_available",
                "learning_pipeline_available",
                "alert_system_available",
                "recovery_manager_available",
                "notification_dispatcher_available",
                "paper_mode_configured",
                "runtime_supervisor_available",
                "portfolio_guard_available",
                "adaptive_exit_available",
            )
        )
        from backend.validation.marathon_report import build_marathon_readiness_report
        from backend.validation.marathon_checklist import MarathonChecklist

        return build_marathon_readiness_report(MarathonChecklist(results=tuple(results)))


class FakeReplayEngine:
    def replay_with_statistics(self, history):
        from backend.validation.replay_models import ReplayDecision, ReplayRunResult

        decisions = [
            ReplayDecision(
                timestamp="2026-06-24T12:00:00+00:00",
                symbol="AAPL",
                market_regime="TRENDING",
                selected_strategy="alpha",
                allocation={"allocation_amount": 1000.0, "allocation_weight": 0.1},
                position_size={"recommended_position_size": 100.0},
                risk_score=0.1,
                confidence=0.9,
                decision="ALLOW",
                exit_plan={"action": "HOLD"},
                diagnostics={"source": "fake"},
            )
        ]
        return ReplayRunResult(
            decisions=decisions,
            statistics={
                "number_of_candidates": 1,
                "number_of_approved_trades": 1,
                "blocked_trades": 0,
                "average_confidence": 0.9,
                "average_allocation": 1000.0,
                "strategy_distribution": {"alpha": 1},
                "regime_distribution": {"TRENDING": 1},
                "decision_distribution": {"ALLOW": 1},
            },
        )


def _clock_factory(start: datetime):
    moments = {"current": start}

    def _clock():
        current = moments["current"]
        moments["current"] = current + timedelta(seconds=1)
        return current

    return _clock


def _runner(
    tmp_path,
    *,
    readiness=None,
    cycle_plan_provider=None,
    status_provider=None,
    paper_mode_probe=None,
    replay_engine=None,
):
    return MarathonRunner(
        readiness=readiness or ReadyMarathonReadiness(),
        replay_engine=replay_engine or FakeReplayEngine(),
        checkpoint_path=tmp_path / "checkpoint.json",
        cycle_interval_seconds=0.0,
        clock=_clock_factory(datetime(2026, 6, 24, 12, 0, 0, tzinfo=timezone.utc)),
        sleep_fn=lambda _: None,
        status_provider=status_provider or (lambda: {
            "runtime_healthy": True,
            "paper_mode_enabled": True,
            "recovery_exhausted": False,
            "critical_alerts": 0,
            "heartbeat_lost_seconds": 0.0,
        }),
        cycle_plan_provider=cycle_plan_provider or (lambda cycle_number: {
            "timestamp": f"2026-06-24T12:00:0{cycle_number}+00:00",
            "paper_balance": 100000.0,
            "equity": 100000.0 + cycle_number,
            "realized_pnl": float(cycle_number),
            "unrealized_pnl": 0.5 * cycle_number,
            "open_positions": cycle_number,
            "alerts": 1,
            "recoveries": 0,
            "heartbeat_status": "OK",
            "runtime_healthy": True,
            "paper_mode_enabled": True,
            "recovery_exhausted": False,
            "critical_alert_threshold_exceeded": False,
            "heartbeat_lost_seconds": 0.0,
            "portfolio_exposure": 1000.0 * cycle_number,
            "cycle_duration_seconds": 0.25,
            "replay_history": ({"timestamp": "2026-06-24T12:00:00+00:00", "trade_id": "t1", "symbol": "AAPL", "asset_class": "EQUITY", "direction": "LONG", "strategy": "alpha", "current_price": 100.0, "market_snapshot": {"candles": [{"close": 100.0, "high": 101.0, "low": 99.0, "volume": 1000.0}, {"close": 101.0, "high": 102.0, "low": 100.0, "volume": 1010.0}, {"close": 102.0, "high": 103.0, "low": 101.0, "volume": 1020.0}]}, "portfolio_snapshot": {"available_capital": 10000.0, "positions": []}},),
        }),
        paper_mode_probe=paper_mode_probe or (lambda: True),
    )


def test_startup_and_snapshot_generation(tmp_path) -> None:
    runner = _runner(tmp_path)

    result = runner.start(cycles=1)

    assert isinstance(result, MarathonRunResult)
    assert result.stop_reason is None
    assert len(result.snapshots) == 1
    assert result.snapshots[0].paper_balance == 100000.0
    assert result.snapshots[0].approved_trades == 1
    assert result.certification_report.go_no_go == "GO"


def test_checkpoint_and_resume(tmp_path) -> None:
    runner = _runner(tmp_path)
    first = runner.start(cycles=1)
    resumed = runner.resume_from_checkpoint(cycles=2)

    assert len(first.snapshots) == 1
    assert len(resumed.snapshots) == 2
    assert resumed.snapshots[1].cycle_number == 2


def test_stop_conditions(tmp_path) -> None:
    runner = _runner(
        tmp_path,
        status_provider=lambda: {
            "runtime_healthy": False,
            "paper_mode_enabled": True,
            "recovery_exhausted": False,
            "critical_alerts": 0,
            "heartbeat_lost_seconds": 0.0,
        },
    )

    result = runner.start(cycles=1)

    assert result.stop_reason == "runtime_unhealthy"
    assert len(result.snapshots) == 0


def test_paper_mode_disabled(tmp_path) -> None:
    runner = _runner(tmp_path, paper_mode_probe=lambda: False)

    with pytest.raises(MarathonRunnerError):
        runner.start(cycles=1)


def test_deterministic_output(tmp_path) -> None:
    first = _runner(tmp_path / "first")
    second = _runner(tmp_path / "second")

    first_result = first.start(cycles=1)
    second_result = second.start(cycles=1)

    assert first_result.snapshots == second_result.snapshots
    assert first_result.statistics == second_result.statistics
    assert first_result.certification_report == second_result.certification_report
