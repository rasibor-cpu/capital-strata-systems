from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any, Mapping


MAX_TOTAL_OPEN_POSITIONS = 10
MAX_OPEN_PER_ASSET_CLASS = 3
MAX_NEW_POSITIONS_PER_CYCLE = 2


@dataclass(frozen=True)
class PositionLimitConfig:
    max_total_open_positions: int = MAX_TOTAL_OPEN_POSITIONS
    max_open_per_asset_class: int = MAX_OPEN_PER_ASSET_CLASS
    max_new_positions_per_cycle: int = MAX_NEW_POSITIONS_PER_CYCLE

    @classmethod
    def from_env(cls) -> "PositionLimitConfig":
        return cls(
            max_total_open_positions=_env_int(
                "CSS_MAX_TOTAL_OPEN_POSITIONS",
                MAX_TOTAL_OPEN_POSITIONS,
            ),
            max_open_per_asset_class=_env_int(
                "CSS_MAX_OPEN_PER_ASSET_CLASS",
                MAX_OPEN_PER_ASSET_CLASS,
            ),
            max_new_positions_per_cycle=_env_int(
                "CSS_MAX_NEW_POSITIONS_PER_CYCLE",
                MAX_NEW_POSITIONS_PER_CYCLE,
            ),
        )


@dataclass(frozen=True)
class PositionLimitDecision:
    allowed: bool
    reason: str
    total_open_positions: int = 0
    open_positions_by_asset_class: dict[str, int] = field(default_factory=dict)
    asset_class: str = ""
    new_positions_requested: int = 0
    max_total_open_positions: int = MAX_TOTAL_OPEN_POSITIONS
    max_open_per_asset_class: int = MAX_OPEN_PER_ASSET_CLASS
    max_new_positions_per_cycle: int = MAX_NEW_POSITIONS_PER_CYCLE

    def as_dict(self) -> dict[str, Any]:
        return {
            "allowed": self.allowed,
            "reason": self.reason,
            "total_open_positions": self.total_open_positions,
            "open_positions_by_asset_class": dict(
                self.open_positions_by_asset_class
            ),
            "asset_class": self.asset_class,
            "new_positions_requested": self.new_positions_requested,
            "max_total_open_positions": self.max_total_open_positions,
            "max_open_per_asset_class": self.max_open_per_asset_class,
            "max_new_positions_per_cycle": self.max_new_positions_per_cycle,
        }


class PositionLimitPolicy:
    def __init__(
        self,
        config: PositionLimitConfig | None = None,
    ) -> None:
        self.config = config or PositionLimitConfig.from_env()

    def evaluate(
        self,
        positions_payload: Mapping[str, Any] | None,
        *,
        asset_class: str | None,
        new_positions_requested: int = 1,
    ) -> PositionLimitDecision:
        requested = _safe_int(new_positions_requested, default=1)
        normalized_asset_class = _normalize_asset_class(asset_class)

        base_decision = {
            "asset_class": normalized_asset_class,
            "new_positions_requested": requested,
            "max_total_open_positions": self.config.max_total_open_positions,
            "max_open_per_asset_class": self.config.max_open_per_asset_class,
            "max_new_positions_per_cycle": self.config.max_new_positions_per_cycle,
        }

        if positions_payload is None:
            return PositionLimitDecision(
                allowed=False,
                reason="positions_payload_missing",
                **base_decision,
            )

        if not isinstance(positions_payload, Mapping):
            return PositionLimitDecision(
                allowed=False,
                reason="positions_payload_invalid",
                **base_decision,
            )

        if not normalized_asset_class:
            return PositionLimitDecision(
                allowed=False,
                reason="asset_class_missing",
                **base_decision,
            )

        if requested < 0:
            return PositionLimitDecision(
                allowed=False,
                reason="new_positions_requested_invalid",
                **base_decision,
            )

        total_open, open_by_asset_class = _extract_position_counts(
            positions_payload
        )
        decision_payload = {
            **base_decision,
            "total_open_positions": total_open,
            "open_positions_by_asset_class": open_by_asset_class,
        }

        if requested == 0:
            return PositionLimitDecision(
                allowed=True,
                reason="no_new_positions_requested",
                **decision_payload,
            )

        if requested > self.config.max_new_positions_per_cycle:
            return PositionLimitDecision(
                allowed=False,
                reason="new_positions_per_cycle_limit_reached",
                **decision_payload,
            )

        if total_open + requested > self.config.max_total_open_positions:
            return PositionLimitDecision(
                allowed=False,
                reason="total_position_limit_reached",
                **decision_payload,
            )

        asset_open = open_by_asset_class.get(normalized_asset_class, 0)
        if asset_open + requested > self.config.max_open_per_asset_class:
            return PositionLimitDecision(
                allowed=False,
                reason="asset_class_position_limit_reached",
                **decision_payload,
            )

        return PositionLimitDecision(
            allowed=True,
            reason="allowed",
            **decision_payload,
        )


def evaluate_position_limits(
    positions_payload: Mapping[str, Any] | None,
    *,
    asset_class: str | None,
    new_positions_requested: int = 1,
    config: PositionLimitConfig | None = None,
) -> PositionLimitDecision:
    return PositionLimitPolicy(config=config).evaluate(
        positions_payload,
        asset_class=asset_class,
        new_positions_requested=new_positions_requested,
    )


def _extract_position_counts(
    positions_payload: Mapping[str, Any],
) -> tuple[int, dict[str, int]]:
    positions = positions_payload.get("positions")
    if isinstance(positions, list):
        counts: dict[str, int] = {}
        total = 0
        for position in positions:
            if not isinstance(position, Mapping):
                continue
            asset_class = _normalize_asset_class(
                position.get("asset_class", "UNKNOWN")
            )
            counts[asset_class] = counts.get(asset_class, 0) + 1
            total += 1
        return total, counts

    raw_counts = (
        positions_payload.get("asset_counts")
        or positions_payload.get("open_positions_by_asset")
        or _nested_open_positions_by_asset(positions_payload)
        or {}
    )
    counts = _normalize_counts(raw_counts)

    total = _safe_int(
        positions_payload.get(
            "open_count",
            positions_payload.get(
                "total_open_positions",
                _nested_total_open_positions(positions_payload),
            ),
        ),
        default=sum(counts.values()),
    )

    return total, counts


def _normalize_counts(raw_counts: Any) -> dict[str, int]:
    if not isinstance(raw_counts, Mapping):
        return {}

    counts: dict[str, int] = {}
    for key, value in raw_counts.items():
        asset_class = _normalize_asset_class(key)
        if not asset_class:
            continue
        counts[asset_class] = max(0, _safe_int(value, default=0))
    return counts


def _nested_open_positions_by_asset(
    positions_payload: Mapping[str, Any],
) -> Any:
    open_positions = positions_payload.get("open_positions", {})
    if isinstance(open_positions, Mapping):
        return open_positions.get("by_asset")
    return None


def _nested_total_open_positions(
    positions_payload: Mapping[str, Any],
) -> Any:
    open_positions = positions_payload.get("open_positions", {})
    if isinstance(open_positions, Mapping):
        return open_positions.get("total")
    return None


def _normalize_asset_class(value: Any) -> str:
    return str(value or "").strip().upper()


def _safe_int(value: Any, *, default: int) -> int:
    try:
        if value is None:
            return int(default)
        return int(value)
    except (TypeError, ValueError):
        return int(default)


def _env_int(name: str, default: int) -> int:
    return _safe_int(os.getenv(name), default=default)


__all__ = [
    "MAX_NEW_POSITIONS_PER_CYCLE",
    "MAX_OPEN_PER_ASSET_CLASS",
    "MAX_TOTAL_OPEN_POSITIONS",
    "PositionLimitConfig",
    "PositionLimitDecision",
    "PositionLimitPolicy",
    "evaluate_position_limits",
]
