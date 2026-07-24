"""PPF-001 adaptive risk signal normalizer."""

from __future__ import annotations

from decimal import Decimal, ROUND_DOWN
from typing import Mapping

from backend.governance.enterprise_profit_protection_contracts import (
    EnterpriseProfitProtectionPolicy,
    NormalizedEnterpriseRiskSignals,
)


class EnterpriseRiskSignalNormalizer:
    """Convert validated governance inputs into bounded non-increasing multipliers."""

    def normalize(
        self,
        values: Mapping[str, Decimal],
        policy: EnterpriseProfitProtectionPolicy,
    ) -> NormalizedEnterpriseRiskSignals:
        current_drawdown = values["current_drawdown_pct"]
        previous_drawdown = values["previous_drawdown_pct"]
        recent_loss = values["recent_loss_amount"]
        worsening = max(current_drawdown - previous_drawdown, Decimal("0"))
        loss_pressure = Decimal("0.10") if recent_loss > Decimal("0") else Decimal("0")
        return NormalizedEnterpriseRiskSignals(
            drawdown_adjustment=_bounded_multiplier(
                Decimal("1") - current_drawdown - worsening - loss_pressure,
                policy,
            ),
            volatility_adjustment=_bounded_multiplier(
                Decimal("1") - values["volatility_score"],
                policy,
            ),
            liquidity_adjustment=_bounded_multiplier(values["liquidity_score"], policy),
            confidence_adjustment=_bounded_multiplier(values["confidence_score"], policy),
            correlation_adjustment=_bounded_multiplier(
                Decimal("1") - values["correlation_score"],
                policy,
            ),
            margin_adjustment=_bounded_multiplier(
                Decimal("1") - values["margin_utilization"],
                policy,
            ),
            recent_loss_reduces_risk=recent_loss > Decimal("0"),
            worsening_drawdown_reduces_risk=current_drawdown > previous_drawdown,
        )


def _bounded_multiplier(
    value: Decimal,
    policy: EnterpriseProfitProtectionPolicy,
) -> Decimal:
    bounded = max(Decimal("0"), min(Decimal("1"), value))
    return bounded.quantize(policy.multiplier_quantum, rounding=ROUND_DOWN)


__all__ = ["EnterpriseRiskSignalNormalizer"]
