from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any, Mapping


def _decimal(value: Any, field_name: str) -> Decimal | None:
    if value is None:
        return None
    try:
        result = value if isinstance(value, Decimal) else Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise TypeError(f"{field_name} must be Decimal-compatible or None") from exc
    if not result.is_finite():
        raise ValueError(f"{field_name} must be finite")
    return result


@dataclass(frozen=True, slots=True)
class CostToServeTelemetry:
    """Immutable internal cost observation; it has no pricing or execution authority."""

    observation_id: str
    observed_at: str
    request_count: int
    runtime_seconds: Decimal | None
    infrastructure_cost: Decimal | None
    estimated_cost: Decimal | None
    cost_basis_complete: bool
    cost_basis_refs: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.observation_id.strip() or not self.observed_at.strip():
            raise ValueError("observation identity and timestamp are required")
        if self.request_count < 0:
            raise ValueError("request_count cannot be negative")
        for name in ("runtime_seconds", "infrastructure_cost", "estimated_cost"):
            value = _decimal(getattr(self, name), name)
            if value is not None and value < 0:
                raise ValueError(f"{name} cannot be negative")
            object.__setattr__(self, name, value)
        if not isinstance(self.cost_basis_refs, tuple):
            raise TypeError("cost_basis_refs must be a tuple")

    def as_dict(self) -> dict[str, Any]:
        return {
            "observation_id": self.observation_id,
            "observed_at": self.observed_at,
            "request_count": self.request_count,
            "runtime_seconds": self.runtime_seconds,
            "infrastructure_cost": self.infrastructure_cost,
            "estimated_cost": self.estimated_cost,
            "cost_basis_complete": self.cost_basis_complete,
            "cost_basis_refs": list(self.cost_basis_refs),
            "customer_charge_affected": False,
            "performance_fee_affected": False,
            "platform_minimum_affected": False,
            "trade_decision_affected": False,
            "execution_affected": False,
            "read_only": True,
        }


def build_cost_to_serve_telemetry(
    *,
    observation_id: str,
    observed_at: str,
    request_count: int = 0,
    runtime_seconds: Any = None,
    infrastructure_cost: Any = None,
    cost_basis_refs: tuple[str, ...] = (),
) -> CostToServeTelemetry:
    """Build telemetry from caller-supplied observations only.

    Missing cost rates remain unknown; this function never invents infrastructure
    rates or feeds the commercial, decision, or execution paths.
    """
    runtime = _decimal(runtime_seconds, "runtime_seconds")
    cost = _decimal(infrastructure_cost, "infrastructure_cost")
    return CostToServeTelemetry(
        observation_id=observation_id,
        observed_at=observed_at,
        request_count=request_count,
        runtime_seconds=runtime,
        infrastructure_cost=cost,
        estimated_cost=cost,
        cost_basis_complete=cost is not None and bool(cost_basis_refs),
        cost_basis_refs=tuple(cost_basis_refs),
    )


__all__ = ["CostToServeTelemetry", "build_cost_to_serve_telemetry"]