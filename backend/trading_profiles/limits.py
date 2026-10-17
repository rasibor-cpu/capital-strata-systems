"""User-configured risk limits: they can only tighten the selected personality.

Precedence (most restrictive wins): platform eligibility and hard safety limits ->
canonical gates (R7, R14F, AntiBleedGuard, kill switch, margin, caps) -> risk
personality / mandate -> these user limits -> per-order approval (assisted mode).
A limit looser than the personality is rejected, never silently clamped.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, fields, replace
from typing import Any, Mapping

from backend.trading_profiles.risk_personalities import PersonalityPolicy

ASSET_CLASSES = frozenset({"FX", "CRYPTO", "FUTURES", "OPTIONS"})

# Fields where a smaller value is tighter.
_CEILINGS = (
    "risk_per_trade_pct", "max_stop_distance_pct", "max_position_pct_of_equity",
    "max_symbol_exposure_pct_of_equity", "max_total_exposure_pct_of_equity",
    "daily_loss_halt_pct", "max_drawdown_halt_pct", "time_stop_hours",
)
# Fields where a larger value is tighter.
_FLOORS = ("min_trade_quality_score", "min_probability")
_INTEGER_CEILINGS = ("max_open_copied_positions",)


class LimitsError(ValueError):
    """Rejected user limit (looser than the personality, malformed or unknown)."""


@dataclass(frozen=True)
class UserRiskLimits:
    risk_per_trade_pct: float | None = None
    max_stop_distance_pct: float | None = None
    max_position_pct_of_equity: float | None = None
    max_symbol_exposure_pct_of_equity: float | None = None
    max_total_exposure_pct_of_equity: float | None = None
    max_open_copied_positions: int | None = None
    daily_loss_halt_pct: float | None = None
    max_drawdown_halt_pct: float | None = None
    time_stop_hours: float | None = None
    min_trade_quality_score: float | None = None
    min_probability: float | None = None
    allowed_asset_classes: tuple[str, ...] | None = None

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any] | None) -> "UserRiskLimits":
        data = dict(data or {})
        known = {f.name for f in fields(cls)}
        unknown = set(data) - known
        if unknown:
            raise LimitsError(f"unknown limit(s): {sorted(unknown)}")
        values: dict[str, Any] = {}
        for name, value in data.items():
            if value is None:
                continue
            if name == "allowed_asset_classes":
                classes = tuple(sorted({str(v).upper() for v in value}))
                if not classes or not set(classes) <= ASSET_CLASSES:
                    raise LimitsError("allowed_asset_classes invalid")
                values[name] = classes
            elif name in _INTEGER_CEILINGS:
                if isinstance(value, bool) or not isinstance(value, int) or value < 1:
                    raise LimitsError(f"{name} must be a positive integer")
                values[name] = value
            else:
                if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
                    raise LimitsError(f"{name} must be a positive finite number")
                values[name] = float(value)
        return cls(**values)

    def to_dict(self) -> dict[str, Any]:
        out = {}
        for f in fields(self):
            value = getattr(self, f.name)
            if value is not None:
                out[f.name] = list(value) if isinstance(value, tuple) else value
        return out


def effective_policy(policy: PersonalityPolicy, limits: UserRiskLimits | None) -> PersonalityPolicy:
    """Personality policy tightened by user limits. Raises LimitsError if any limit loosens it."""
    if limits is None:
        return policy
    changes: dict[str, Any] = {}
    for name in _CEILINGS + _INTEGER_CEILINGS:
        value = getattr(limits, name)
        if value is None:
            continue
        if value > getattr(policy, name):
            raise LimitsError(f"{name}={value} is looser than the {policy.personality.value} personality ({getattr(policy, name)})")
        changes[name] = value
    for name in _FLOORS:
        value = getattr(limits, name)
        if value is None:
            continue
        if value < getattr(policy, name):
            raise LimitsError(f"{name}={value} is looser than the {policy.personality.value} personality ({getattr(policy, name)})")
        changes[name] = value
    if limits.allowed_asset_classes is not None:
        requested = frozenset(limits.allowed_asset_classes)
        if not requested <= policy.allowed_asset_classes:
            raise LimitsError(f"asset classes {sorted(requested - policy.allowed_asset_classes)} are not allowed by the personality")
        changes["allowed_asset_classes"] = requested
    return replace(policy, **changes)
