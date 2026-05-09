from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class LiveOrderKillSwitchDecision:
    blocked: bool
    reason: str = "live_order_kill_switch_clear"
    source: str = "default"

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def evaluate_live_order_kill_switch(
    controls: Mapping[str, Any] | None = None,
    *,
    env: Mapping[str, str] | None = None,
) -> LiveOrderKillSwitchDecision:
    active_controls = controls or {}
    active_env = env or os.environ

    if _truthy(active_env.get("CSS_LIVE_ORDER_KILL_SWITCH")):
        return LiveOrderKillSwitchDecision(
            blocked=True,
            reason="env_kill_switch_engaged",
            source="CSS_LIVE_ORDER_KILL_SWITCH",
        )

    if _truthy(active_controls.get("live_order_kill_switch")):
        return LiveOrderKillSwitchDecision(
            blocked=True,
            reason="mobile_control_kill_switch_engaged",
            source="mobile_controls",
        )

    if _truthy(active_controls.get("global_live_order_kill_switch")):
        return LiveOrderKillSwitchDecision(
            blocked=True,
            reason="global_control_kill_switch_engaged",
            source="mobile_controls",
        )

    return LiveOrderKillSwitchDecision(blocked=False)


def _truthy(value: Any) -> bool:
    return str(value).strip().lower() in {
        "1",
        "true",
        "yes",
        "y",
        "on",
        "engaged",
        "enabled",
        "block",
        "blocked",
    }


__all__ = [
    "LiveOrderKillSwitchDecision",
    "evaluate_live_order_kill_switch",
]
