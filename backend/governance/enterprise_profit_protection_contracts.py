"""PPF-001 Adaptive Enterprise Profit Protection contracts."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from decimal import Decimal
from enum import Enum
from typing import Any, Mapping


SCHEMA_VERSION = "css.ppf001.enterprise_profit_protection.v1"


class PPFMaturityTier(str, Enum):
    STARTUP = "STARTUP"
    GROWTH = "GROWTH"
    ESTABLISHED = "ESTABLISHED"
    INSTITUTIONAL = "INSTITUTIONAL"


class PPFEnforcementStatus(str, Enum):
    ADVISORY_APPROVED = "ADVISORY_APPROVED"
    ADVISORY_BLOCKED = "ADVISORY_BLOCKED"
    FAIL_CLOSED = "FAIL_CLOSED"


class PPFPosture(str, Enum):
    PROFIT_PROTECTED = "PROFIT_PROTECTED"
    ZERO_BUDGET = "ZERO_BUDGET"
    REDUCED_BY_ADAPTIVE_RISK = "REDUCED_BY_ADAPTIVE_RISK"
    FAIL_CLOSED = "FAIL_CLOSED"


class PPFReasonCode(str, Enum):
    OK = "OK"
    ADVISORY_ONLY = "ADVISORY_ONLY"
    PRINCIPAL_EXCLUDED = "PRINCIPAL_EXCLUDED"
    ZERO_OR_NEGATIVE_BANKED_PROFIT = "ZERO_OR_NEGATIVE_BANKED_PROFIT"
    MISSING_REQUIRED_DATA = "MISSING_REQUIRED_DATA"
    INPUT_STALE = "INPUT_STALE"
    INPUT_NOT_FINITE = "INPUT_NOT_FINITE"
    NEGATIVE_INPUT = "NEGATIVE_INPUT"
    INPUT_OUT_OF_RANGE = "INPUT_OUT_OF_RANGE"
    CEILING_CLAMPED_TO_CONSTITUTIONAL = "CEILING_CLAMPED_TO_CONSTITUTIONAL"
    BUDGET_REDUCED_BY_ADAPTIVE_MULTIPLIERS = "BUDGET_REDUCED_BY_ADAPTIVE_MULTIPLIERS"
    FINAL_BUDGET_CAPPED_BY_BASE_CEILING = "FINAL_BUDGET_CAPPED_BY_BASE_CEILING"
    RECENT_LOSS_REDUCED_RISK = "RECENT_LOSS_REDUCED_RISK"
    WORSENING_DRAWDOWN_REDUCED_RISK = "WORSENING_DRAWDOWN_REDUCED_RISK"
    POLICY_INVALID = "POLICY_INVALID"


CONSTITUTIONAL_TIER_CEILINGS: dict[PPFMaturityTier, Decimal] = {
    PPFMaturityTier.STARTUP: Decimal("0.80"),
    PPFMaturityTier.GROWTH: Decimal("0.60"),
    PPFMaturityTier.ESTABLISHED: Decimal("0.40"),
    PPFMaturityTier.INSTITUTIONAL: Decimal("0.25"),
}


@dataclass(frozen=True)
class NormalizedEnterpriseRiskSignals:
    drawdown_adjustment: Decimal
    volatility_adjustment: Decimal
    liquidity_adjustment: Decimal
    confidence_adjustment: Decimal
    correlation_adjustment: Decimal
    margin_adjustment: Decimal
    recent_loss_reduces_risk: bool = False
    worsening_drawdown_reduces_risk: bool = False
    advisory_only: bool = True
    execution_allowed: bool = False

    def multipliers(self) -> dict[str, Decimal]:
        return {
            "drawdown_adjustment": self.drawdown_adjustment,
            "volatility_adjustment": self.volatility_adjustment,
            "liquidity_adjustment": self.liquidity_adjustment,
            "confidence_adjustment": self.confidence_adjustment,
            "correlation_adjustment": self.correlation_adjustment,
            "margin_adjustment": self.margin_adjustment,
        }

    def as_dict(self) -> dict[str, Any]:
        return {
            **{key: str(value) for key, value in self.multipliers().items()},
            "recent_loss_reduces_risk": self.recent_loss_reduces_risk,
            "worsening_drawdown_reduces_risk": self.worsening_drawdown_reduces_risk,
            "advisory_only": True,
            "execution_allowed": False,
        }


@dataclass(frozen=True)
class EnterpriseProfitProtectionPolicy:
    """Canonical PPF-001 policy. Ceilings may only tighten constitutional caps."""

    maturity_tier: PPFMaturityTier = PPFMaturityTier.STARTUP
    tier_ceilings: Mapping[PPFMaturityTier | str, Decimal | str | int | float] = field(
        default_factory=lambda: dict(CONSTITUTIONAL_TIER_CEILINGS)
    )
    max_input_age_seconds: int = 300
    money_quantum: Decimal = Decimal("0.01")
    multiplier_quantum: Decimal = Decimal("0.000001")
    advisory_only: bool = True
    execution_allowed: bool = False

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["maturity_tier"] = self.maturity_tier.value
        payload["tier_ceilings"] = {
            _tier_value(key): str(value) for key, value in self.tier_ceilings.items()
        }
        payload["money_quantum"] = str(self.money_quantum)
        payload["multiplier_quantum"] = str(self.multiplier_quantum)
        payload["execution_allowed"] = False
        payload["advisory_only"] = True
        return payload


@dataclass(frozen=True)
class PPFRiskRequest:
    request_id: str
    maturity_tier: PPFMaturityTier | str | None
    banked_net_profit: Decimal | str | int | float | None
    principal_capital: Decimal | str | int | float | None
    current_drawdown_pct: Decimal | str | int | float | None
    previous_drawdown_pct: Decimal | str | int | float | None
    recent_loss_amount: Decimal | str | int | float | None
    volatility_score: Decimal | str | int | float | None
    liquidity_score: Decimal | str | int | float | None
    confidence_score: Decimal | str | int | float | None
    correlation_score: Decimal | str | int | float | None
    margin_utilization: Decimal | str | int | float | None
    observed_at: str | None
    source: str = "PPF001_REQUEST"


@dataclass(frozen=True)
class PPFRiskDecision:
    request_id: str
    enforcement_status: PPFEnforcementStatus
    posture: PPFPosture
    maturity_tier: PPFMaturityTier
    effective_ceiling: Decimal
    base_budget: Decimal
    adjusted_budget: Decimal
    multipliers: Mapping[str, Decimal]
    reason_codes: tuple[PPFReasonCode, ...]
    state: "ProfitProtectionState"
    advisory_only: bool = True
    execution_allowed: bool = False

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "request_id": self.request_id,
            "enforcement_status": self.enforcement_status.value,
            "posture": self.posture.value,
            "maturity_tier": self.maturity_tier.value,
            "effective_ceiling": str(self.effective_ceiling),
            "base_budget": str(self.base_budget),
            "adjusted_budget": str(self.adjusted_budget),
            "multipliers": {key: str(value) for key, value in self.multipliers.items()},
            "reason_codes": [code.value for code in self.reason_codes],
            "state": self.state.as_dict(),
            "advisory_only": True,
            "execution_allowed": False,
        }


@dataclass(frozen=True)
class ProfitProtectionState:
    schema_version: str
    maturity_tier: PPFMaturityTier
    banked_net_profit: Decimal
    principal_capital: Decimal
    constitutional_ceiling: Decimal
    effective_ceiling: Decimal
    base_budget: Decimal
    adjusted_budget: Decimal
    multipliers: Mapping[str, Decimal]
    reason_codes: tuple[PPFReasonCode, ...]
    posture: PPFPosture
    advisory_only: bool = True
    execution_allowed: bool = False

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "maturity_tier": self.maturity_tier.value,
            "banked_net_profit": str(self.banked_net_profit),
            "principal_capital": str(self.principal_capital),
            "constitutional_ceiling": str(self.constitutional_ceiling),
            "effective_ceiling": str(self.effective_ceiling),
            "base_budget": str(self.base_budget),
            "adjusted_budget": str(self.adjusted_budget),
            "multipliers": {key: str(value) for key, value in self.multipliers.items()},
            "reason_codes": [code.value for code in self.reason_codes],
            "posture": self.posture.value,
            "advisory_only": True,
            "execution_allowed": False,
        }


@dataclass(frozen=True)
class ProfitProtectionReservation:
    """Reservation contract only; PPF-001 pass does not create or persist reservations."""

    reservation_id: str
    request_id: str
    amount: Decimal
    status: str = "NOT_CREATED"
    reason_code: PPFReasonCode = PPFReasonCode.ADVISORY_ONLY
    advisory_only: bool = True
    execution_allowed: bool = False

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["amount"] = str(self.amount)
        payload["reason_code"] = self.reason_code.value
        payload["execution_allowed"] = False
        payload["advisory_only"] = True
        return payload


def _tier_value(value: PPFMaturityTier | str) -> str:
    return value.value if isinstance(value, PPFMaturityTier) else str(value)


__all__ = [
    "CONSTITUTIONAL_TIER_CEILINGS",
    "SCHEMA_VERSION",
    "EnterpriseProfitProtectionPolicy",
    "NormalizedEnterpriseRiskSignals",
    "PPFEnforcementStatus",
    "PPFMaturityTier",
    "PPFPosture",
    "PPFReasonCode",
    "PPFRiskDecision",
    "PPFRiskRequest",
    "ProfitProtectionReservation",
    "ProfitProtectionState",
]
