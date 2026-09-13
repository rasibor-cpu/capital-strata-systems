from __future__ import annotations

from decimal import Decimal

from .readiness import ReadinessAssessment
from .replay import CheckpointResult, ReplayScore
from .session import SimulatorSessionState


API_SCHEMA_VERSION = "simulator-preview.v1"


def _decimal(value: Decimal) -> str:
    return format(value, "f")


def build_phone_preview_contract(
    *,
    session: SimulatorSessionState,
    readiness: ReadinessAssessment,
    checkpoint_results: tuple[CheckpointResult, ...] = (),
    replay_score: ReplayScore | None = None,
) -> dict:
    """Stable, read-only contract for phone preview clients."""

    payload = {
        "schema_version": API_SCHEMA_VERSION,
        "mode": "SIMULATION",
        "execution_allowed": False,
        "broker_execution_armed": False,
        "money_movement_allowed": False,
        "live_execution_authorized": False,
        "commercialization_attribution_allowed": False,
        "fee_entitlement_allowed": False,
        "live_trading_eligible": False,
        "session": {
            "learner_id": session.learner_id,
            "scenario_id": session.scenario_id,
            "step_index": session.step_index,
            "total_steps": session.total_steps,
            "status": session.status,
            "projection": session.projection,
        },
        "readiness": {
            "level": readiness.level.value,
            "completed_lessons": readiness.completed_lessons,
            "completed_scenarios": readiness.completed_scenarios,
            "decision_quality_pct": _decimal(readiness.decision_quality_pct),
            "max_drawdown_pct": _decimal(readiness.max_drawdown_pct),
            "live_execution_authorized": False,
            "reasons": list(readiness.reasons),
        },
        "checkpoints": [
            {
                "checkpoint_id": item.checkpoint_id,
                "state": item.state.value,
                "earned_weight": _decimal(item.earned_weight),
                "possible_weight": _decimal(item.possible_weight),
                "explanation": item.explanation,
            }
            for item in checkpoint_results
        ],
    }

    if replay_score is not None:
        payload["replay_score"] = {
            "earned_weight": _decimal(replay_score.earned_weight),
            "possible_weight": _decimal(replay_score.possible_weight),
            "score_pct": _decimal(replay_score.score_pct),
            "correct": replay_score.correct,
            "partial": replay_score.partial,
            "incorrect": replay_score.incorrect,
            "pending": replay_score.pending,
        }

    return payload
