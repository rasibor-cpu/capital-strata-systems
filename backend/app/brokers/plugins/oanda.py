"""OANDA canonical operational-state plugin (source-only)."""

from __future__ import annotations

from typing import Any, Mapping

from backend.app.brokers.operational_adapter import OandaOperationalAdapter


def plugin_info(
    *,
    configuration: Mapping[str, Any] | None = None,
    evidence: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    adapter = OandaOperationalAdapter(configuration=configuration, evidence=evidence)
    return {
        "name": "oanda",
        "role": "PRIMARY_FX_BROKER",
        "operational": adapter.operational_snapshot(),
        "capability_states": adapter.capability_states(),
        "execution_allowed": False,
    }


__all__ = ["plugin_info"]
