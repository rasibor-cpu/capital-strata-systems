from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from backend.runtime.operational_proving import (
    certification_history_trend,
    operational_scorecard,
    pre_pilot_gate,
)


PAYLOAD_VERSION = "css.phase164.pre_pilot_certification_gate.v1"


def evaluate_pre_pilot_certification_gate(
    *,
    runtime_metrics: Mapping[str, Any] | None = None,
    runtime_health: Mapping[str, Any] | None = None,
    certification_snapshot: Mapping[str, Any] | None = None,
    certification_history: list[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Evaluate advisory-only pre-pilot eligibility.

    This wrapper exposes the Phase 164 pre-pilot gate as a reusable production
    runtime module. It never grants execution authority.
    """

    metrics = dict(runtime_metrics or {})
    health = dict(runtime_health or {})
    snapshot = dict(certification_snapshot or {})
    trend = certification_history_trend(certification_history or [])
    scorecard = operational_scorecard(
        metrics=metrics,
        runtime_health=health,
        certification_snapshot=snapshot,
        trend=trend,
    )
    gate = pre_pilot_gate(
        metrics=metrics,
        runtime_health=health,
        certification_snapshot=snapshot,
        trend=trend,
        scorecard=scorecard,
    )
    return {
        "payload_version": PAYLOAD_VERSION,
        **gate,
        "operational_scorecard": scorecard,
        "certification_trend": trend,
        "execution_allowed": False,
        "live_trading_blocked": True,
        "broker_execution_armed": False,
        "advisory_only": True,
    }


__all__ = ["PAYLOAD_VERSION", "evaluate_pre_pilot_certification_gate"]
