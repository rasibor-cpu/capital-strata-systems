from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from typing import Any

from backend.allocation.caie_shadow_adapter import CAIEShadowAdapter


logger = logging.getLogger(__name__)


class CAIERuntimeBridge:
    """Runtime boundary for CAIE shadow advisories after trade eligibility checks."""

    def __init__(self, *, shadow_adapter: CAIEShadowAdapter | None = None) -> None:
        self.shadow_adapter = shadow_adapter or CAIEShadowAdapter()

    def run_after_trade_gate(
        self,
        *,
        trade_gate_completed: bool,
        validated_proposals: Sequence[Mapping[str, Any]] | None,
        available_capital: float,
        proposal_contexts: Mapping[str, Mapping[str, Any]] | None = None,
        default_broker: str = "UNKNOWN",
        asset_class_caps: Mapping[str, float] | None = None,
        broker_caps: Mapping[str, float] | None = None,
        min_quality_score: float = 50.0,
        concentration_penalty_weight: float = 20.0,
        diversification_bonus: float = 2.0,
        runtime_timestamp: str | None = None,
    ) -> dict[str, Any]:
        ts = runtime_timestamp or datetime.now(timezone.utc).isoformat()

        if not trade_gate_completed:
            logger.info("CAIE shadow unavailable: trade gate not completed")
            return self._unavailable("trade_gate_not_completed", ts)

        try:
            advisory = self.shadow_adapter.generate_advisory(
                validated_proposals,
                available_capital=available_capital,
                proposal_contexts=proposal_contexts,
                default_broker=default_broker,
                asset_class_caps=asset_class_caps,
                broker_caps=broker_caps,
                min_quality_score=min_quality_score,
                concentration_penalty_weight=concentration_penalty_weight,
                diversification_bonus=diversification_bonus,
                runtime_timestamp=ts,
            )
        except Exception as exc:  # pragma: no cover - exercised in runtime-failure tests
            logger.exception("CAIE shadow integration failed; runtime continues", exc_info=exc)
            return self._unavailable("caie_exception", ts)

        if str(advisory.get("caie_status", "UNAVAILABLE")).upper() == "UNAVAILABLE":
            logger.warning("CAIE shadow unavailable: %s", advisory.get("reason", "unknown"))
        else:
            logger.info("CAIE shadow advisory generated")

        # Enforce execution-inert contract even if downstream payload mutates.
        advisory["advisory_only"] = True
        advisory["shadow_mode"] = True
        advisory["execution_action"] = "NO_EXECUTION"
        advisory["runtime_timestamp"] = ts
        return advisory

    @staticmethod
    def _unavailable(reason: str, timestamp: str) -> dict[str, Any]:
        return {
            "caie_status": "UNAVAILABLE",
            "advisory_only": True,
            "shadow_mode": True,
            "ranked_opportunities": [],
            "selected_opportunities": [],
            "recommended_allocations": [],
            "portfolio_score": None,
            "unused_capital": None,
            "execution_action": "NO_EXECUTION",
            "runtime_timestamp": timestamp,
            "reason": reason,
        }


def run_caie_runtime_shadow(
    *,
    trade_gate_completed: bool,
    validated_proposals: Sequence[Mapping[str, Any]] | None,
    available_capital: float,
    proposal_contexts: Mapping[str, Mapping[str, Any]] | None = None,
    default_broker: str = "UNKNOWN",
    asset_class_caps: Mapping[str, float] | None = None,
    broker_caps: Mapping[str, float] | None = None,
    min_quality_score: float = 50.0,
    concentration_penalty_weight: float = 20.0,
    diversification_bonus: float = 2.0,
    runtime_timestamp: str | None = None,
) -> dict[str, Any]:
    return CAIERuntimeBridge().run_after_trade_gate(
        trade_gate_completed=trade_gate_completed,
        validated_proposals=validated_proposals,
        available_capital=available_capital,
        proposal_contexts=proposal_contexts,
        default_broker=default_broker,
        asset_class_caps=asset_class_caps,
        broker_caps=broker_caps,
        min_quality_score=min_quality_score,
        concentration_penalty_weight=concentration_penalty_weight,
        diversification_bonus=diversification_bonus,
        runtime_timestamp=runtime_timestamp,
    )
