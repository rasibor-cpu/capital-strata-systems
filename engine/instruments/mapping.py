"""
Instrument Mapping – Governance Locked
=======================================

Implements the invariant:

Strategy Concept → Canonical REA Instrument → Broker Symbol

Hard rules:
- Missing canonical => raise
- Missing adapter symbol => raise
- Duplicate canonical definitions => raise
- Duplicate strategy concept => raise

This must be validated at startup.
"""

from __future__ import annotations

from typing import Dict
from engine.instruments.canonical import CANONICAL_INSTRUMENTS


# -------------------------------------------------------
# Strategy Concept Layer
# -------------------------------------------------------

# Strategy-level identifiers (engine-facing)
# These are what strategies reference internally.

STRATEGY_TO_CANONICAL: Dict[str, str] = {
    # Phase 2A Futures
    "MEAN_REVERT_FUT_ES": "FUT_ES",
    "MEAN_REVERT_FUT_NQ": "FUT_NQ",
}


# -------------------------------------------------------
# Broker Symbol Layer (Adapter-specific)
# -------------------------------------------------------

# adapter_name → canonical_id → broker_symbol
ADAPTER_SYMBOL_MAP: Dict[str, Dict[str, str]] = {
    # Example adapter
    "alpaca_futures_adapter": {
        "FUT_ES": "ES",
        "FUT_NQ": "NQ",
    },

    # Default FX adapter has no futures capability
    "default_fx_adapter": {
        # Intentionally empty
    },
}


# -------------------------------------------------------
# Validation Logic (Hard-Fail)
# -------------------------------------------------------

def validate_or_raise() -> None:
    """
    Validates mapping integrity.
    Must be called at engine startup.
    """

    # 1️⃣ Ensure all canonical IDs referenced exist
    for strategy_id, canonical_id in STRATEGY_TO_CANONICAL.items():
        if canonical_id not in CANONICAL_INSTRUMENTS:
            raise RuntimeError(
                f"Mapping Error: strategy '{strategy_id}' "
                f"references unknown canonical '{canonical_id}'"
            )

    # 2️⃣ Ensure no duplicate canonical entries in adapter maps
    for adapter, mapping in ADAPTER_SYMBOL_MAP.items():
        seen = set()
        for canonical_id in mapping:
            if canonical_id in seen:
                raise RuntimeError(
                    f"Duplicate canonical '{canonical_id}' "
                    f"in adapter '{adapter}'"
                )
            seen.add(canonical_id)

    # 3️⃣ Ensure no duplicate strategy concepts
    if len(STRATEGY_TO_CANONICAL) != len(set(STRATEGY_TO_CANONICAL.keys())):
        raise RuntimeError("Duplicate strategy concept IDs detected")


def resolve_broker_symbol(
    *,
    strategy_id: str,
    adapter_name: str,
) -> str:
    """
    Resolves:
    Strategy → Canonical → Broker Symbol

    Hard-fails if:
    - strategy not found
    - canonical missing
    - adapter missing
    - adapter lacks symbol
    """

    if strategy_id not in STRATEGY_TO_CANONICAL:
        raise RuntimeError(f"Unknown strategy_id: {strategy_id}")

    canonical_id = STRATEGY_TO_CANONICAL[strategy_id]

    if canonical_id not in CANONICAL_INSTRUMENTS:
        raise RuntimeError(
            f"Canonical instrument missing: {canonical_id}"
        )

    if adapter_name not in ADAPTER_SYMBOL_MAP:
        raise RuntimeError(
            f"Unknown adapter: {adapter_name}"
        )

    adapter_map = ADAPTER_SYMBOL_MAP[adapter_name]

    if canonical_id not in adapter_map:
        raise RuntimeError(
            f"Adapter '{adapter_name}' does not support canonical '{canonical_id}'"
        )

    return adapter_map[canonical_id]
