from __future__ import annotations

from datetime import date, datetime
from typing import Any

from backend.options.paper_position_repository import PaperPositionRepository
from backend.options.position_state_machine import ACTIVE, EXPIRING
from backend.options.roll_decision_engine import RollDecision, RollDecisionEngine
from backend.options.rolling_candidates import RollingCandidate, RollingCandidateGenerator


class RollingEngineError(ValueError):
    """Raised when paper rolling evaluation must fail closed."""


class RollingEngine:
    def __init__(
        self,
        *,
        repository: PaperPositionRepository,
        candidate_generator: RollingCandidateGenerator | None = None,
        decision_engine: RollDecisionEngine | None = None,
    ) -> None:
        self.repository = repository
        self.candidate_generator = candidate_generator or RollingCandidateGenerator()
        self.decision_engine = decision_engine or RollDecisionEngine()

    def candidates(
        self,
        position_id: str,
        *,
        as_of: date | datetime | str,
        underlying_price: float,
        delta: float,
        moneyness: str,
        strategy_quality: float = 0.75,
    ) -> list[RollingCandidate]:
        position = self.repository.get(position_id)
        if position.current_state not in {ACTIVE, EXPIRING}:
            raise RollingEngineError("Rolling is only available for active or expiring paper positions")
        return self.candidate_generator.generate(
            position,
            as_of=as_of,
            underlying_price=underlying_price,
            delta=delta,
            moneyness=moneyness,
            strategy_quality=strategy_quality,
        )

    def recommend(
        self,
        position_id: str,
        *,
        as_of: date | datetime | str,
        underlying_price: float,
        delta: float,
        moneyness: str,
        strategy_quality: float = 0.75,
    ) -> RollDecision:
        candidates = self.candidates(
            position_id,
            as_of=as_of,
            underlying_price=underlying_price,
            delta=delta,
            moneyness=moneyness,
            strategy_quality=strategy_quality,
        )
        return self.decision_engine.decide(candidates)


__all__ = ["RollingEngine", "RollingEngineError"]
