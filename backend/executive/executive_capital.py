"""Read-only capital allocation projection."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any


def build_capital_view(snapshot: Mapping[str, Any] | None) -> dict[str, Any]:
    source = dict(snapshot or {})
    return {
        "available_cash": source.get("available_cash", source.get("cash", 0.0)),
        "buying_power": source.get("buying_power", 0.0),
        "deployed_capital": source.get("deployed_capital", source.get("capital_used", 0.0)),
        "broker_allocation": dict(source.get("broker_allocation") or {}),
        "strategy_allocation": dict(source.get("strategy_allocation") or {}),
        "asset_allocation": dict(source.get("asset_allocation") or {}),
        "read_only": True,
        "execution_allowed": False,
    }


__all__ = ["build_capital_view"]
