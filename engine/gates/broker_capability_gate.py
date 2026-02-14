"""
Capital Strata Systems
Broker Capability Gate – Phase 2B (Mapping-Aware)

Goal:
Prevent accidental routing of Futures flow into non-futures adapters,
and enforce the 3-layer invariant:

Strategy Concept → Canonical REA Instrument → Broker Symbol

Design:
- Pure python / stdlib only
- Fail-closed by default
- No backend imports
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class CapabilityDecision:
    ok: bool
    decision: str            # "ALLOW" | "BLOCK"
    reasons: List[str]


class BrokerCapabilityGate:
    """
    Gate checks whether the selected adapter/broker is permitted
    to execute a given asset class.

    Expected state keys (fail-closed if missing):
      - adapter_name: str
      - adapter_capabilities: dict[str,bool] OR list[str]
      - asset_class: str (optional; caller may pass separately)
      - strategy_id: str (required for futures mapping-aware validation)

    Notes:
    - For FX: capability-level check is sufficient.
    - For Futures: we also require that strategy_id resolves to a broker symbol
      for the active adapter via instruments mapping.
    """

    def evaluate(
        self,
        *,
        asset_class: str,          # "fx" | "futures" | "equities" | etc
        state: Dict[str, Any],
    ) -> CapabilityDecision:

        reasons: List[str] = []

        adapter_name = state.get("adapter_name")
        if not adapter_name or not isinstance(adapter_name, str):
            return CapabilityDecision(
                ok=False,
                decision="BLOCK",
                reasons=["missing_adapter_name"],
            )

        caps = state.get("adapter_capabilities")

        # First: coarse capability check (fail-closed)
        if not self._capability_allows(asset_class=asset_class, caps=caps):
            return CapabilityDecision(
                ok=False,
                decision="BLOCK",
                reasons=[f"adapter_not_capable:{adapter_name}:{asset_class}"],
            )

        # Second: mapping-aware enforcement for futures
        if str(asset_class).lower() == "futures":
            strategy_id = state.get("strategy_id")
            if not strategy_id or not isinstance(strategy_id, str):
                return CapabilityDecision(
                    ok=False,
                    decision="BLOCK",
                    reasons=["missing_strategy_id_for_futures_mapping"],
                )

            # Mapping resolution hard-fails by design; we convert to BLOCK here.
            try:
                from engine.instruments.mapping import resolve_broker_symbol
                _ = resolve_broker_symbol(strategy_id=strategy_id, adapter_name=adapter_name)
            except Exception as e:
                return CapabilityDecision(
                    ok=False,
                    decision="BLOCK",
                    reasons=[f"mapping_block:{adapter_name}:{strategy_id}:{type(e).__name__}"],
                )

            return CapabilityDecision(
                ok=True,
                decision="ALLOW",
                reasons=[f"adapter_capable_and_mapped:{adapter_name}:{strategy_id}"],
            )

        # Non-futures: capability check is sufficient
        return CapabilityDecision(
            ok=True,
            decision="ALLOW",
            reasons=[f"adapter_capable:{adapter_name}:{asset_class}"],
        )

    def _capability_allows(self, *, asset_class: str, caps: Any) -> bool:
        ac = str(asset_class).lower().strip()

        # dict capabilities
        if isinstance(caps, dict):
            return bool(caps.get(ac, False))

        # list/set/tuple of capability strings
        if isinstance(caps, (list, set, tuple)):
            normalized = [str(x).lower().strip() for x in caps]
            return ac in normalized

        # missing/invalid
        return False
