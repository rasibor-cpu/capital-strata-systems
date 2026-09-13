from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal

from .academy import AcademyProgression, default_challenge_catalog
from .benchmark import BenchmarkEngine
from .engine import AcademyScorer
from .models import SimulatedPortfolio
from .profile import LearnerProfile
from .projection import build_simulator_projection
from .scenarios import Scenario


@dataclass(frozen=True)
class SimulatorSessionState:
    learner_id: str
    scenario_id: str
    step_index: int
    total_steps: int
    status: str
    projection: dict


class SimulatorSession:
    """Deterministic mobile-facing simulation session.

    It is deliberately incapable of submitting broker instructions.
    """

    @staticmethod
    def build_state(
        *,
        profile: LearnerProfile,
        scenario: Scenario,
        step_index: int,
        as_of_utc: datetime,
        starting_equity: Decimal | None = None,
        current_equity: Decimal | None = None,
    ) -> SimulatorSessionState:
        if as_of_utc.tzinfo is None or as_of_utc.utcoffset() != timedelta(0):
            raise ValueError("as_of_utc must be timezone-aware UTC")
        if step_index < 0 or step_index >= len(scenario.price_path):
            raise ValueError("step_index outside scenario")

        start = starting_equity if starting_equity is not None else scenario.initial_cash
        current = current_equity if current_equity is not None else start
        if start <= Decimal("0") or current < Decimal("0"):
            raise ValueError("session equity values are invalid")

        benchmark = BenchmarkEngine.compare(
            start,
            current,
            scenario.benchmark_path[: step_index + 1]
            if step_index >= 1
            else scenario.benchmark_path[:2],
        )

        portfolio = SimulatedPortfolio(
            cash=current,
            positions={},
            realized_pnl=Decimal("0"),
            high_water_mark=max(start, current),
            starting_equity=start,
            as_of_utc=as_of_utc,
        )
        accepted_good, rejected_bad, total_decisions = AcademyProgression.decision_quality(
            profile.decisions
        )
        score = AcademyScorer.score(
            portfolio,
            benchmark_return_pct=benchmark.benchmark_return_pct,
            accepted_good_decisions=accepted_good,
            rejected_bad_decisions=rejected_bad,
            total_decisions=total_decisions,
        )

        observation_counts = dict(profile.challenge_observations)
        challenge_progress = tuple(
            AcademyScorer.evaluate_challenge(
                challenge,
                score,
                observations=observation_counts.get(challenge.challenge_id, 0),
            )
            for challenge in default_challenge_catalog()
        )

        payload = build_simulator_projection(
            portfolio=portfolio,
            score=score,
            decisions=profile.decisions,
            challenges=challenge_progress,
            achievements=profile.achievements,
        )
        payload["learner"] = {
            "learner_id": profile.learner_id,
            "completed_lesson_ids": list(profile.completed_lesson_ids),
        }
        payload["scenario"] = {
            "scenario_id": scenario.scenario_id,
            "title": scenario.title,
            "learning_objective": scenario.learning_objective,
            "step_index": step_index,
            "total_steps": len(scenario.price_path),
            "current_price": format(scenario.price_path[step_index], "f"),
            "benchmark_return_pct": format(benchmark.benchmark_return_pct, "f"),
            "learner_return_pct": format(benchmark.learner_return_pct, "f"),
            "excess_return_pct": format(benchmark.excess_return_pct, "f"),
        }

        status = "COMPLETE" if step_index == len(scenario.price_path) - 1 else "IN_PROGRESS"
        return SimulatorSessionState(
            learner_id=profile.learner_id,
            scenario_id=scenario.scenario_id,
            step_index=step_index,
            total_steps=len(scenario.price_path),
            status=status,
            projection=payload,
        )
