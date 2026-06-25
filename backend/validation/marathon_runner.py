from __future__ import annotations

import json
import subprocess
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping

from backend.intelligence.intelligence_orchestrator import IntelligenceOrchestrator
from backend.validation.historical_replay_engine import HistoricalReplayEngine

from .marathon_certifier import MarathonCertifier, MarathonCertificationReport
from .marathon_readiness import MarathonReadiness, MarathonReadinessError
from .marathon_snapshot import MarathonCyclePlan, MarathonSnapshot
from .marathon_statistics import MarathonStatistics, build_marathon_statistics


class MarathonRunnerError(RuntimeError):
    """Fail-closed exception for marathon runner failures."""


@dataclass(frozen=True)
class MarathonRunResult:
    start_time: str
    end_time: str
    elapsed_time_seconds: float
    stop_reason: str | None
    checkpoints: tuple[dict[str, Any], ...]
    snapshots: tuple[MarathonSnapshot, ...]
    statistics: MarathonStatistics
    certification_report: MarathonCertificationReport
    readiness_report: Any
    resume_state: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "start_time": self.start_time,
            "end_time": self.end_time,
            "elapsed_time_seconds": self.elapsed_time_seconds,
            "stop_reason": self.stop_reason,
            "checkpoints": list(self.checkpoints),
            "snapshots": [snapshot.to_dict() for snapshot in self.snapshots],
            "statistics": self.statistics.to_dict(),
            "certification_report": self.certification_report.to_dict(),
            "readiness_report": self.readiness_report.to_dict() if hasattr(self.readiness_report, "to_dict") else self.readiness_report,
            "resume_state": dict(self.resume_state),
        }


class MarathonRunner:
    """Paper-mode marathon runner for repeated CSS validation cycles."""

    def __init__(
        self,
        *,
        readiness: MarathonReadiness | None = None,
        replay_engine: HistoricalReplayEngine | None = None,
        certifier: MarathonCertifier | None = None,
        checkpoint_path: str | Path | None = None,
        cycle_interval_seconds: float = 1.0,
        clock: Callable[[], datetime] | None = None,
        sleep_fn: Callable[[float], None] | None = None,
        status_provider: Callable[[], Mapping[str, Any]] | None = None,
        cycle_plan_provider: Callable[[int], Mapping[str, Any]] | None = None,
        paper_mode_probe: Callable[[], bool] | None = None,
        max_critical_alerts: int = 5,
        max_heartbeat_lost_seconds: float = 600.0,
        max_recovery_attempts: int = 3,
    ) -> None:
        self.readiness = readiness or MarathonReadiness()
        self.replay_engine = replay_engine or HistoricalReplayEngine()
        self.certifier = certifier or MarathonCertifier()
        self.checkpoint_path = Path(checkpoint_path or (Path(__file__).resolve().parents[2] / "runtime" / "marathon_checkpoint.json"))
        self.cycle_interval_seconds = float(cycle_interval_seconds)
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self.sleep_fn = sleep_fn or time.sleep
        self.status_provider = status_provider or self._default_status_provider
        self.cycle_plan_provider = cycle_plan_provider or self._default_cycle_plan_provider
        self.paper_mode_probe = paper_mode_probe or self._paper_mode_enabled_from_config
        self.max_critical_alerts = int(max_critical_alerts)
        self.max_heartbeat_lost_seconds = float(max_heartbeat_lost_seconds)
        self.max_recovery_attempts = int(max_recovery_attempts)

    def start(
        self,
        *,
        cycles: int,
        resume: bool = False,
    ) -> MarathonRunResult:
        return self.run(cycles=cycles, resume=resume)

    def run(
        self,
        *,
        cycles: int,
        resume: bool = False,
    ) -> MarathonRunResult:
        if cycles <= 0:
            raise MarathonRunnerError("cycles must be positive")

        readiness_report = self._verify_readiness()
        if readiness_report.go_no_go != "GO":
            raise MarathonRunnerError("V2A readiness did not pass")

        if not self.paper_mode_probe():
            raise MarathonRunnerError("paper mode disabled")

        state = self._load_checkpoint() if resume else self._fresh_state()
        snapshots: list[MarathonSnapshot] = list(state.get("snapshots", []))
        checkpoints: list[dict[str, Any]] = list(state.get("checkpoints", []))
        start_time = state.get("start_time") or self._utc_now()
        start_moment = datetime.fromisoformat(start_time)
        stop_reason: str | None = state.get("stop_reason")

        completed_cycles = int(state.get("completed_cycles", 0))
        for cycle_number in range(completed_cycles + 1, cycles + 1):
            cycle_started = time.perf_counter()
            plan = MarathonCyclePlan.from_mapping(self.cycle_plan_provider(cycle_number))
            runtime_status = self.status_provider()
            stop_reason = self._evaluate_stop_conditions(plan, runtime_status)
            if stop_reason:
                break

            replay_summary = self._build_replay_summary(plan.replay_history)
            snapshot = self._build_snapshot(
                cycle_number=cycle_number,
                plan=plan,
                replay_summary=replay_summary,
                uptime_seconds=(self.clock() - start_moment).total_seconds(),
            )
            snapshots.append(snapshot)

            checkpoint = self._build_checkpoint(
                start_time=start_time,
                completed_cycles=len(snapshots),
                snapshots=snapshots,
                stop_reason=None,
            )
            checkpoints.append(checkpoint)
            self._save_checkpoint(checkpoint)

            cycle_duration = time.perf_counter() - cycle_started
            if cycle_number < cycles:
                self.sleep_fn(max(0.0, self.cycle_interval_seconds))

            state = {
                "start_time": start_time,
                "completed_cycles": len(snapshots),
                "snapshots": snapshots,
                "checkpoints": checkpoints,
                "stop_reason": stop_reason,
            }

        end_time = self._utc_now()
        elapsed_time_seconds = (datetime.fromisoformat(end_time) - start_moment).total_seconds()
        statistics = build_marathon_statistics(snapshots)
        replay_summary = self._aggregate_replay_summary(snapshots)
        certification_report = self.certifier.certify(
            start_time=start_time,
            end_time=end_time,
            elapsed_time_seconds=elapsed_time_seconds,
            snapshots=snapshots,
            statistics=statistics,
            readiness_report=readiness_report,
            stop_reason=stop_reason,
            replay_summary=replay_summary,
        )

        result = MarathonRunResult(
            start_time=start_time,
            end_time=end_time,
            elapsed_time_seconds=round(elapsed_time_seconds, 8),
            stop_reason=stop_reason,
            checkpoints=tuple(checkpoints),
            snapshots=tuple(snapshots),
            statistics=statistics,
            certification_report=certification_report,
            readiness_report=readiness_report,
            resume_state={
                "completed_cycles": len(snapshots),
                "checkpoint_path": str(self.checkpoint_path),
            },
        )
        self._save_checkpoint(self._build_checkpoint(start_time, len(snapshots), snapshots, stop_reason))
        return result

    def resume_from_checkpoint(self, *, cycles: int) -> MarathonRunResult:
        return self.run(cycles=cycles, resume=True)

    def _verify_readiness(self):
        report = self.readiness.certify()
        if report.go_no_go != "GO":
            raise MarathonRunnerError("readiness certification did not pass")
        return report

    def _evaluate_stop_conditions(self, plan: MarathonCyclePlan, runtime_status: Mapping[str, Any]) -> str | None:
        runtime_healthy = bool(runtime_status.get("runtime_healthy", plan.runtime_healthy))
        paper_mode_enabled = bool(runtime_status.get("paper_mode_enabled", plan.paper_mode_enabled))
        recovery_exhausted = bool(runtime_status.get("recovery_exhausted", plan.recovery_exhausted))
        critical_alerts = int(runtime_status.get("critical_alerts", plan.alerts))
        heartbeat_lost_seconds = float(runtime_status.get("heartbeat_lost_seconds", plan.heartbeat_lost_seconds))

        if not runtime_healthy:
            return "runtime_unhealthy"
        if not paper_mode_enabled:
            return "paper_mode_disabled"
        if recovery_exhausted:
            return "recovery_exhausted"
        if critical_alerts > self.max_critical_alerts:
            return "critical_alert_threshold_exceeded"
        if heartbeat_lost_seconds > self.max_heartbeat_lost_seconds:
            return "heartbeat_lost"
        return None

    def _build_snapshot(
        self,
        *,
        cycle_number: int,
        plan: MarathonCyclePlan,
        replay_summary: dict[str, Any],
        uptime_seconds: float,
    ) -> MarathonSnapshot:
        latest_canonical = self._latest_canonical_decision(replay_summary)
        allocation = self._safe_float(
            latest_canonical.get("allocation", {}).get("allocation_amount")
            if isinstance(latest_canonical.get("allocation"), Mapping)
            else 0.0,
            0.0,
        )
        position_size = self._safe_float(
            latest_canonical.get("position_size", {}).get("recommended_position_size")
            if isinstance(latest_canonical.get("position_size"), Mapping)
            else 0.0,
            0.0,
        )
        return MarathonSnapshot(
            timestamp=plan.timestamp,
            uptime_seconds=round(float(uptime_seconds), 8),
            cycle_number=cycle_number,
            paper_balance=plan.paper_balance,
            equity=plan.equity,
            realized_pnl=plan.realized_pnl,
            unrealized_pnl=plan.unrealized_pnl,
            approved_trades=int(replay_summary.get("number_of_approved_trades", 0)),
            blocked_trades=int(replay_summary.get("blocked_trades", 0)),
            open_positions=plan.open_positions,
            alerts=plan.alerts,
            recoveries=plan.recoveries,
            heartbeat_status=plan.heartbeat_status,
            decision=str(latest_canonical.get("entry_decision") or self._dominant_value(replay_summary.get("decision_distribution", {}), default="UNKNOWN")),
            selected_strategy=str(latest_canonical.get("selected_strategy") or self._dominant_value(replay_summary.get("strategy_distribution", {}), default="")),
            market_regime=str(latest_canonical.get("market_regime") or self._dominant_value(replay_summary.get("regime_distribution", {}), default="UNKNOWN")),
            confidence=self._safe_float(latest_canonical.get("confidence"), 0.0),
            signal_strength=self._safe_float(latest_canonical.get("signal_strength"), 0.0),
            allocation=allocation,
            position_size=position_size,
            expected_reward=self._safe_float(latest_canonical.get("expected_reward"), 0.0),
            expected_risk=self._safe_float(latest_canonical.get("expected_risk"), 0.0),
            execution_status=str(latest_canonical.get("execution_status") or "UNKNOWN"),
            learning_version=str((latest_canonical.get("learning_context") or {}).get("learning_version") or ""),
            portfolio_exposure=plan.portfolio_exposure,
            cycle_duration_seconds=plan.cycle_duration_seconds,
            drawdown=max(0.0, plan.equity - plan.paper_balance),
            canonical_decision=latest_canonical,
            optimization_summary=dict(plan.optimization_summary),
            learning_feedback_summary=dict(plan.learning_feedback_summary),
            portfolio_optimization_summary=dict(plan.portfolio_optimization_summary),
        )

    def _build_replay_summary(self, replay_history: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
        if not replay_history:
            return {
                "number_of_candidates": 0,
                "number_of_approved_trades": 0,
                "blocked_trades": 0,
                "average_confidence": 0.0,
                "average_allocation": 0.0,
                "strategy_distribution": {},
                "regime_distribution": {},
                "decision_distribution": {},
                "decisions": [],
            }

        result = self.replay_engine.replay_with_statistics(replay_history)
        statistics = result.statistics
        return {
            **statistics,
            "decisions": [decision.to_dict() for decision in result.decisions],
        }

    def _build_checkpoint(
        self,
        start_time: str,
        completed_cycles: int,
        snapshots: list[MarathonSnapshot],
        stop_reason: str | None,
    ) -> dict[str, Any]:
        return {
            "start_time": start_time,
            "completed_cycles": completed_cycles,
            "snapshots": [snapshot.to_dict() for snapshot in snapshots],
            "stop_reason": stop_reason,
            "updated_at": self._utc_now(),
        }

    def _save_checkpoint(self, checkpoint: dict[str, Any]) -> None:
        self.checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
        self.checkpoint_path.write_text(json.dumps(checkpoint, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    def _load_checkpoint(self) -> dict[str, Any]:
        if not self.checkpoint_path.exists():
            raise MarathonRunnerError("checkpoint file does not exist")
        try:
            payload = json.loads(self.checkpoint_path.read_text(encoding="utf-8"))
        except Exception as exc:
            raise MarathonRunnerError(f"checkpoint unreadable: {exc}") from exc

        if not isinstance(payload, dict):
            raise MarathonRunnerError("checkpoint must be a JSON object")

        snapshots_payload = payload.get("snapshots", [])
        if not isinstance(snapshots_payload, list):
            raise MarathonRunnerError("checkpoint snapshots must be a list")

        snapshots = tuple(MarathonSnapshot(**snapshot) for snapshot in snapshots_payload)
        return {
            "start_time": str(payload.get("start_time") or self._utc_now()),
            "completed_cycles": int(payload.get("completed_cycles", len(snapshots))),
            "snapshots": list(snapshots),
            "checkpoints": [payload],
            "stop_reason": payload.get("stop_reason"),
        }

    def _fresh_state(self) -> dict[str, Any]:
        return {
            "start_time": self._utc_now(),
            "completed_cycles": 0,
            "snapshots": [],
            "checkpoints": [],
            "stop_reason": None,
        }

    def _default_status_provider(self) -> dict[str, Any]:
        return {
            "runtime_healthy": True,
            "paper_mode_enabled": self._paper_mode_enabled_from_config(),
            "recovery_exhausted": False,
            "critical_alerts": 0,
            "heartbeat_lost_seconds": 0.0,
        }

    def _default_cycle_plan_provider(self, cycle_number: int) -> dict[str, Any]:
        timestamp = self._utc_now()
        return {
            "timestamp": timestamp,
            "paper_balance": 100000.0,
            "equity": 100000.0,
            "realized_pnl": 0.0,
            "unrealized_pnl": 0.0,
            "open_positions": 0,
            "alerts": 0,
            "recoveries": 0,
            "heartbeat_status": "OK",
            "runtime_healthy": True,
            "paper_mode_enabled": self._paper_mode_enabled_from_config(),
            "recovery_exhausted": False,
            "critical_alert_threshold_exceeded": False,
            "heartbeat_lost_seconds": 0.0,
            "portfolio_exposure": 0.0,
            "cycle_duration_seconds": self.cycle_interval_seconds,
            "replay_history": (),
            "optimization_summary": {},
            "learning_feedback_summary": {},
            "portfolio_optimization_summary": {},
        }

    def _paper_mode_enabled_from_config(self) -> bool:
        config_path = Path(__file__).resolve().parents[2] / "config.json"
        if not config_path.exists():
            return False
        try:
            payload = json.loads(config_path.read_text(encoding="utf-8"))
        except Exception:
            return False
        if not isinstance(payload, dict):
            return False
        system = payload.get("system", {})
        oanda = payload.get("oanda", {})
        mode = str(system.get("mode") or "").strip().lower()
        environment = str(oanda.get("environment") or "").strip().lower()
        return environment in {"practice", "paper", "demo"} or mode in {"paper", "practice", "demo", "live_manual_confirm"}

    def _utc_now(self) -> str:
        return self.clock().astimezone(timezone.utc).isoformat()

    @staticmethod
    def _dominant_value(distribution: Mapping[str, Any], *, default: str) -> str:
        if not isinstance(distribution, Mapping) or not distribution:
            return default
        best_key = sorted(distribution.items(), key=lambda item: (-int(item[1]), str(item[0])))[0][0]
        return str(best_key)

    def _aggregate_replay_summary(self, snapshots: list[MarathonSnapshot]) -> dict[str, Any]:
        decision_counts: dict[str, int] = {}
        strategy_counts: dict[str, int] = {}
        regime_counts: dict[str, int] = {}

        for snapshot in snapshots:
            if snapshot.decision:
                decision_counts[snapshot.decision] = decision_counts.get(snapshot.decision, 0) + 1
            if snapshot.selected_strategy:
                strategy_counts[snapshot.selected_strategy] = strategy_counts.get(snapshot.selected_strategy, 0) + 1
            if snapshot.market_regime:
                regime_counts[snapshot.market_regime] = regime_counts.get(snapshot.market_regime, 0) + 1

        return {
            "decision_distribution": {key: decision_counts[key] for key in sorted(decision_counts.keys())},
            "strategy_distribution": {key: strategy_counts[key] for key in sorted(strategy_counts.keys())},
            "regime_distribution": {key: regime_counts[key] for key in sorted(regime_counts.keys())},
        }

    @staticmethod
    def _latest_canonical_decision(replay_summary: Mapping[str, Any]) -> dict[str, Any]:
        decisions = replay_summary.get("decisions", []) if isinstance(replay_summary, Mapping) else []
        if not isinstance(decisions, list) or not decisions:
            return {}
        last = decisions[-1]
        if not isinstance(last, Mapping):
            return {}
        canonical = last.get("canonical_decision")
        if isinstance(canonical, Mapping):
            return dict(canonical)
        return {}

    @staticmethod
    def _safe_float(value: Any, default: float = 0.0) -> float:
        try:
            if value is None:
                return default
            return float(value)
        except (TypeError, ValueError):
            return default
