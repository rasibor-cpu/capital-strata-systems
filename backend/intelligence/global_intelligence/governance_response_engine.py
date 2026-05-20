from __future__ import annotations

from .event_models import GovernanceResponse, RegimeState


def build_governance_response(regime: RegimeState) -> GovernanceResponse:
    if regime == RegimeState.NORMAL:
        return GovernanceResponse(
            reduce_allocation_pct=0.0,
            freeze_new_positions=False,
            freeze_options=False,
            suppress_scalping=False,
            max_open_positions=None,
            leverage_multiplier=1.0,
            notes=["Advisory-only stance: normal operations."],
        )

    if regime == RegimeState.CAUTION:
        return GovernanceResponse(
            reduce_allocation_pct=10.0,
            freeze_new_positions=False,
            freeze_options=False,
            suppress_scalping=False,
            max_open_positions=None,
            leverage_multiplier=0.85,
            notes=["Advisory-only caution: moderate capital preservation."],
        )

    if regime == RegimeState.DEFENSIVE:
        return GovernanceResponse(
            reduce_allocation_pct=35.0,
            freeze_new_positions=False,
            freeze_options=False,
            suppress_scalping=True,
            max_open_positions=None,
            leverage_multiplier=0.50,
            notes=["Advisory-only defensive posture: reduce exposure."],
        )

    if regime == RegimeState.PANIC:
        return GovernanceResponse(
            reduce_allocation_pct=75.0,
            freeze_new_positions=True,
            freeze_options=True,
            suppress_scalping=True,
            max_open_positions=0,
            leverage_multiplier=0.10,
            notes=["Advisory-only panic mode: avoid new exposure."],
        )

    if regime == RegimeState.LIQUIDITY_CRISIS:
        return GovernanceResponse(
            reduce_allocation_pct=90.0,
            freeze_new_positions=True,
            freeze_options=True,
            suppress_scalping=True,
            max_open_positions=0,
            leverage_multiplier=0.0,
            notes=["Advisory-only liquidity crisis posture: preserve capital."],
        )

    if regime == RegimeState.OPPORTUNITY_EXPANSION:
        return GovernanceResponse(
            reduce_allocation_pct=0.0,
            freeze_new_positions=False,
            freeze_options=False,
            suppress_scalping=False,
            max_open_positions=None,
            leverage_multiplier=1.10,
            notes=["Controlled opportunity expansion only."],
        )

    return GovernanceResponse()